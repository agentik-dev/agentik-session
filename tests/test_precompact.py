"""C1 (mod-r1 §6, §7 line 9, §8): the PreCompact hook. A sitting restarts rather than
compacts (portfolio entry 17), so an automatic compaction is blocked; a `/compact` the owner
types passes. An installed CLI older than the plugin never blocks a compaction (NICE N1)."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import doctor, hooks

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
CLASSIC = {"SessionStart": 10, "PreToolUse": 5, "PostToolUse": 5, "PostToolUseFailure": 5,
           "PostToolBatch": 5, "UserPromptSubmit": 5, "Stop": 5, "StopFailure": 5,
           "SessionEnd": 15}       # S34 adds StopFailure


def payload(trigger) -> dict:
    p = {"session_id": "sess-1", "transcript_path": "/nonexistent/t.jsonl", "cwd": "/tmp",
         "hook_event_name": "PreCompact", "trigger": trigger, "custom_instructions": ""}
    if trigger is None:
        del p["trigger"]
    return p


def test_c1_auto_is_blocked_with_one_line():
    out = hooks.pre_compact(payload("auto"))
    assert set(out) == {"decision", "reason"} and out["decision"] == "block"
    assert "\n" not in out["reason"]
    # Fix round N2: plain words, no portfolio cite, and the command in the form the CLI takes.
    assert "restarts a sitting rather than compacting it" in out["reason"]
    assert "entry 17" not in out["reason"] and "portfolio" not in out["reason"]
    assert "`agentik-session checkpoint --respawn --charter <" in out["reason"]


def test_c1_the_reasons_command_passes_checkpoints_flag_checks(tmp_path, monkeypatch):
    # cli.py's `_respawn_check` refuses `--respawn` without `--charter FILE` (exit 2); the
    # reason's command, its placeholder filled, gets past that to the session-id check.
    import contextlib, io, re, shlex
    from claude_session import cli
    cmds = re.findall(r"`([^`]*)`", hooks.COMPACT_BLOCKED)
    assert len(cmds) == 1 and cmds[0].startswith("agentik-session checkpoint ")
    md = tmp_path / "c.md"
    md.write_text("# x\n")
    argv = shlex.split(re.sub(r"<[^>]*>", shlex.quote(str(md)), cmds[0]))[1:]
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        with pytest.raises(SystemExit) as e:
            cli.main(argv)
    assert e.value.code == 2 and "CLAUDE_CODE_SESSION_ID" in err.getvalue(), err.getvalue()


@pytest.mark.parametrize("trigger", ["manual", None, "", "later"])
def test_c1_manual_and_unknown_triggers_pass(trigger):
    # Only `auto` is blocked: the owner's typed /compact, and any trigger not known, pass.
    assert hooks.pre_compact(payload(trigger)) == {}


def _hook(event, stdin):
    return subprocess.run([sys.executable, "-B", "-m", "claude_session", "hook", event],
                          input=stdin, capture_output=True, text=True, cwd=ROOT)


@pytest.mark.parametrize("event", ["PreCompact", "pre-compact"])
def test_c1_the_cli_hook_verb_blocks_auto(event):
    r = _hook(event, json.dumps(payload("auto")))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"decision": "block", "reason": hooks.COMPACT_BLOCKED}


@pytest.mark.parametrize("event", ["PreCompact", "pre-compact"])
@pytest.mark.parametrize("stdin", [json.dumps(payload("manual")), json.dumps(payload(None)),
                                   json.dumps(payload("later")), "", "not json", "[1]"])
def test_c1_a_pass_prints_nothing(event, stdin):
    # Fix round N1: claude 2.1.296 makes a passing PreCompact hook's raw stdout the
    # compaction's custom instructions, so a `{}` would reach every typed /compact.
    r = _hook(event, stdin)
    assert (r.returncode, r.stdout) == (0, ""), r.stderr


def test_c1_a_broken_handler_passes_silently(capsys, monkeypatch):
    # A handler that raises is a pass: nothing on stdout, exit 0.
    def boom(payload):
        raise RuntimeError("x")
    monkeypatch.setitem(hooks.HANDLERS, "PreCompact", boom)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(payload("auto"))))
    assert hooks.dispatch("PreCompact") == 0
    assert capsys.readouterr().out == ""


def test_c1_other_events_still_print_their_json(capsys, monkeypatch):
    # Only PreCompact's pass is quiet: another event's empty reply stays `{}`.
    monkeypatch.setitem(hooks.HANDLERS, "PostToolBatch", lambda payload: {})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{}"))
    assert hooks.dispatch("PostToolBatch") == 0
    assert capsys.readouterr().out == "{}\n"


def test_c1_hooks_json_keeps_the_classic_eight_and_adds_precompact():
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert list(registered) == [*CLASSIC, "PreCompact"] == list(doctor.HOOK_EVENTS)
    for event, timeout in [*CLASSIC.items(), ("PreCompact", 5)]:
        assert [(h["type"], h["command"], h["timeout"]) for g in registered[event]
                for h in g["hooks"]] == [
            ("command", "${CLAUDE_PLUGIN_ROOT}/hooks/run " + event, timeout)], event
    assert [g.get("matcher") for g in registered["PreCompact"]] == [None]
    assert "PreCompact" in hooks.HANDLERS and "pre-compact" in hooks.HANDLERS


def _fake_cli(tmp_path: Path, body: str) -> dict:
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    exe = bin_ / "agentik-session"
    exe.write_text("#!/bin/sh\ncat >/dev/null\n" + body)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return {"PATH": "%s:/usr/bin:/bin" % bin_}


def _shim(event: str, env: dict, trigger="manual"):
    return subprocess.run([str(PLUGIN / "hooks/run"), event], env=env, text=True,
                          input=json.dumps(payload(trigger)), capture_output=True)


@pytest.mark.parametrize("code", [2, 1])
def test_c1_shim_maps_an_old_clis_refusal_to_exit_0(tmp_path, code):
    # An older CLI refuses `hook PreCompact` with exit 2 ("invalid choice"); exit 2 there
    # would block every compaction, the owner's typed one too. Its stdout is kept.
    env = _fake_cli(tmp_path, "echo \"invalid choice: $2\" >&2; echo '{}'; exit %d\n" % code)
    r = _shim("PreCompact", env)
    assert (r.returncode, r.stdout) == (0, "{}\n")
    r = _shim("PreToolUse", env)                               # the positive control
    assert (r.returncode, r.stdout) == (code, "{}\n")


def test_c1_shim_keeps_the_clis_block(tmp_path):
    block = '{"decision": "block", "reason": "r"}'
    env = _fake_cli(tmp_path, "echo '%s'; exit 0\n" % block)
    r = _shim("PreCompact", env, trigger="auto")
    assert (r.returncode, r.stdout) == (0, block + "\n")


def test_c1_shim_is_silent_without_the_tool():
    r = subprocess.run([str(PLUGIN / "hooks/run"), "PreCompact"], input="{}",
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_c1_doctor_names_a_plugin_without_precompact(tmp_path):
    # An installed plugin older than C1 registers the classic eight only: doctor says update.
    install = tmp_path / "install" / "hooks"
    install.mkdir(parents=True)
    (install / "hooks.json").write_text(json.dumps({"hooks": {e: [] for e in CLASSIC}}))
    plugins = {doctor.PLUGIN_ID: {"version": "2.0.0-alpha.6", "enabled": True,
                                  "installPath": str(install.parent)}}
    c = doctor._check_plugin(plugins, None)
    assert not c.ok and c.detail.startswith("hooks not registered: PreCompact;")
    assert os.access(PLUGIN / "hooks/run", os.X_OK)


def test_c1_runbook_step_2_names_every_hook_and_the_shims_exits():
    # RUNBOOK §1 step 2 lists the plugin's hooks and the events whose exit the shim drops.
    runbook = (ROOT / "RUNBOOK.md").read_text()
    step = runbook.split("\n2. Install the plugin", 1)[1].split("\n3. ", 1)[0]
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    hooks_list, shim = step.split("through `hooks/run`", 1)
    assert [e for e in registered if f"`{e}`" not in hooks_list] == []
    assert "`PreCompact`" in shim.split("the shim", 1)[1]
