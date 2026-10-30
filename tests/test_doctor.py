"""doctor: the range matcher, the check order, and honesty on a fake PATH."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks
from claude_session.doctor import satisfies

ROOT = Path(__file__).resolve().parents[1]

RANGES = [
    ("0.6.0", "^0.6", True), ("0.6.9", "^0.6", True), ("0.7.0", "^0.6", False),
    ("0.2.3", "^0.2", True), ("0.1.9", "^0.2", False), ("1.0.0", "^0.2", False),
    ("2.5.0", "^2.0", True), ("3.0.0", "^2.0", False), ("0.0.3", "^0.0.3", True),
    ("0.0.4", "^0.0.3", False), ("1.2.9", "~1.2", True), ("1.3.0", "~1.2", False),
    ("1.9.0", "~1", True), ("1.2.3", "=1.2.3", True), ("1.2.4", "=1.2.3", False),
    ("1.2.4", "1.2", True), ("1.5.0", ">=1.4 <2", True), ("2.0.0", ">=1.4 <2", False),
    ("1.3.9", ">=1.4", False), ("2.0.0-alpha.1", "^2.0", False),
    ("2.0.0-alpha.2", "^2.0.0-alpha.1", True), ("2.0.0-alpha.0", "^2.0.0-alpha.1", False),
    ("2.0.0-beta", "^2.0.0-alpha.1", True), ("2.1.0", "^2.0.0-alpha.1", True),
]


@pytest.mark.parametrize("version,rng,want", RANGES)
def test_satisfies(version, rng, want):
    assert satisfies(version, rng) is want


@pytest.mark.parametrize("version,rng", [("x", "^1"), ("1.0.0", "^x"), ("1.0.0", "")])
def test_satisfies_refuses_garbage(version, rng):
    with pytest.raises(ValueError):
        satisfies(version, rng)


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A fake PATH that is green unless a test breaks one piece of it."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    install = tmp_path / "install"
    (install / "hooks").mkdir(parents=True)
    (install / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {
        "SessionStart": [], "PreToolUse": [], "PostToolUse": [], "PostToolUseFailure": [],
        "PostToolBatch": [], "UserPromptSubmit": [], "Stop": [], "StopFailure": [], "SessionEnd": [],
        "PreCompact": []}}))
    plugins = [
        {"id": "session@agentik", "version": "2.0.0", "enabled": True,
         "installPath": str(install)},
        {"id": "decisions@agentik", "version": "0.4.0", "enabled": True},
        {"id": "respeak@agentik", "version": "0.6.0", "enabled": True},
        {"id": "relay@agentik", "version": "0.1.0", "enabled": True},
    ]
    (tmp_path / "plugins.json").write_text(json.dumps(plugins))
    _exe(bin_ / "claude", f'if [ "$1" = plugin ]; then /bin/cat {tmp_path}/plugins.json; exit 0; fi\n'
         'echo "--model --effort --tools --permission-mode '
         '--max-budget-usd --output-format --session-id"\n')  # --max-turns: unlisted
    for b in ("relay", "tmux", "git"):
        _exe(bin_ / b, "exit 0\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"PATH": str(bin_), "HOME": str(tmp_path / "home"),
           "XDG_STATE_HOME": str(tmp_path / "state"), "CLAUDE_CODE_SESSION_ID": "sess-1"}
    hooks.session_start({"session_id": "sess-1", "cwd": str(repo)}, env)
    hooks.post_tool_use({"session_id": "sess-1", "transcript_path":
                         str(ROOT / "tests/fixtures/meter/under-80.jsonl")}, env)

    class M:
        pass
    m = M()
    m.env, m.repo, m.bin, m.plugins, m.tmp = env, repo, bin_, plugins, tmp_path

    def set_plugins(ps):
        (tmp_path / "plugins.json").write_text(json.dumps(ps))
    m.set_plugins = set_plugins
    return m


def failing(rep):
    return [c.name for c in rep.checks if not c.ok]


def test_green_machine_in_order(machine):
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    assert [c.name for c in rep.checks] == [
        "claude", "python", "state-dir", "plugin", "decisions", "respeak", "relay-plugin",
        "profiles", "resolved", "meter", "meter-hook", "config", "git", "relay", "mod",
        "measure"]


def test_no_claude_on_path(machine):
    (machine.bin / "claude").unlink()
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep)[:1] == ["claude"] and not rep.ok
    assert "plugin" in failing(rep)          # unknown is never a pass


def test_claude_check_passes_without_max_turns_listed(machine):
    # `claude --help` leaves --max-turns out though claude accepts it; never probed
    c = doctor.run(machine.env, machine.repo).checks[0]
    assert c.ok and "--max-turns" in c.detail and "not probed" in c.detail
    assert "--max-turns" not in doctor.CLAUDE_FLAGS
    _exe(machine.bin / "claude", 'echo "--model"\n')   # a listed flag missing still fails
    c = doctor.run(machine.env, machine.repo).checks[0]
    assert not c.ok and "--effort" in c.detail


def test_old_python(machine):
    c = doctor._check_python(machine.env, (3, 9, 6, "final", 0), "/opt/py/bin/python3")
    assert not c.ok and c.detail.startswith("3.9.6 (/opt/py/bin/python3)")
    assert c.detail.endswith("needs 3.11+")


def test_python_floor_is_3_11(machine):
    # The launcher runs `python -P` (ADV6-3), which 3.10 lacks.
    assert not doctor._check_python(machine.env, (3, 10, 21, "final", 0), "/p").ok
    assert doctor._check_python(machine.env, (3, 11, 0, "final", 0), "/p").ok
    assert min(doctor.KNOWN_PYTHONS, key=doctor._vtuple).startswith("3.11.")


def test_python_is_the_running_interpreter(machine):
    c = doctor._check_python(machine.env, (3, 12, 1, "final", 0), "/opt/py/bin/python3")
    assert c.ok and c.detail.startswith("3.12.1 (/opt/py/bin/python3); newest known")
    assert doctor.run(machine.env, machine.repo).checks[1].detail.startswith(
        "%d.%d.%d" % sys.version_info[:3])


def test_newest_known_from_pyenv(machine):
    _exe(machine.bin / "pyenv", 'printf "Available versions:\\n  2.7.18\\n  3.9.6\\n  3.15.0\\n'
         '  3.15.0a1\\n  3.14.7\\n  pypy3.10-7.3.17\\n"\n')
    assert doctor.newest_known(machine.env) == ("3.15.0", "pyenv's list")
    c = doctor._check_python(machine.env, (3, 14, 7, "final", 0), "/opt/py/bin/python3")
    assert c.detail.endswith("newest known 3.15.0 (pyenv's list)")


def test_newest_known_shipped_list_without_pyenv(machine):
    version, source = doctor.newest_known(machine.env)
    assert version == max(doctor.KNOWN_PYTHONS, key=lambda v: tuple(map(int, v.split("."))))
    assert source == "the shipped list of " + doctor.KNOWN_PYTHONS_OF


def test_newest_known_falls_back_when_pyenv_fails(machine):
    _exe(machine.bin / "pyenv", "exit 1\n")
    assert doctor.newest_known(machine.env)[1].startswith("the shipped list")


def test_c1_a_sibling_at_any_version_is_fine(machine):
    # mod-r1 §9: no caret range a sibling's minor bump can break (decisions 0.5.0 failed ^0.4).
    ps = [dict(p) for p in machine.plugins]
    ps[1]["version"], ps[2]["version"], ps[3]["version"] = "0.5.0", "0.7.0", "1.0.0"
    machine.set_plugins(ps)
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    sib = {c.name: c.detail for c in rep.checks if c.name in ("decisions", "respeak",
                                                             "relay-plugin")}
    assert sib == {"decisions": "decisions@agentik 0.5.0 installed",
                   "respeak": "respeak@agentik 0.7.0 installed",
                   "relay-plugin": "relay@agentik 1.0.0 installed"}


def test_c1_no_sibling_is_a_note_and_doctor_stays_green(machine, monkeypatch, capsys):
    # The owner's word, 2026-10-11 18:10: a user is never forced to install several plugins.
    machine.set_plugins(machine.plugins[:1])
    for b in ("relay", "tmux"):
        (machine.bin / b).unlink()
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    notes = {c.name: c.detail for c in rep.checks if c.note}
    assert list(notes) == ["decisions", "respeak", "relay-plugin", "relay"]
    for name in ("decisions", "respeak", "relay-plugin"):
        assert notes[name].startswith(f"not installed, optional: ")
        assert "^" not in notes[name]
    assert "the relay plugin not installed" in notes["relay"]
    text = doctor.render(rep)
    assert "\nnote decisions " in text and text.endswith("doctor: green")
    for k, v in machine.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(machine.repo)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert cli.main(["doctor"]) == 0


def test_c1_relay_on_without_the_binaries_is_red(machine):
    # `enabled: on` asks for the relay; only `auto` follows the sibling's presence.
    machine.set_plugins(machine.plugins[:1])
    (machine.bin / "relay").unlink()
    cfg = machine.repo / ".claude/agentik/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('relay: {enabled: "on"}\n')
    assert failing(doctor.run(machine.env, machine.repo)) == ["relay"]


def test_wrong_marketplace_is_not_the_sibling(machine):
    ps = [dict(p) for p in machine.plugins]
    ps[1]["id"] = "decisions@elsewhere"
    machine.set_plugins(ps)
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == []
    assert next(c for c in rep.checks if c.name == "decisions").note


def hook_line(env, repo):
    return next(c for c in doctor.run(env, repo).checks if c.name == "meter-hook")


def test_meter_hook_line_live_and_not(machine):
    c = hook_line(machine.env, machine.repo)
    assert c.ok and c.detail.startswith("live:") and "PostToolUse" in c.detail
    ps = [dict(p) for p in machine.plugins]
    ps[0]["enabled"] = False
    machine.set_plugins(ps)
    c = hook_line(machine.env, machine.repo)
    assert c.ok and c.detail.startswith("not live:") and "disabled" in c.detail
    assert c.detail.endswith("packet prompts keep the turns line (conventions §5)")
    machine.set_plugins(ps[1:])
    c = hook_line(machine.env, machine.repo)
    assert c.ok and "not installed" in c.detail
    # a plugin without its hook: the plugin line fails; the meter-hook line reports, ok
    machine.set_plugins(machine.plugins)
    (machine.tmp / "install/hooks/hooks.json").write_text('{"hooks": {}}')
    assert failing(doctor.run(machine.env, machine.repo)) == ["plugin"]
    c = hook_line(machine.env, machine.repo)
    assert c.ok and c.detail.startswith("not live:") and "PostToolUse" in c.detail


def test_no_resolved_file(machine):
    env = {**machine.env, "CLAUDE_CODE_SESSION_ID": "another"}
    assert failing(doctor.run(env, machine.repo)) == ["resolved", "meter"]


def test_newest_session_when_the_variable_is_absent(machine):
    env = {k: v for k, v in machine.env.items() if k != "CLAUDE_CODE_SESSION_ID"}
    rep = doctor.run(env, machine.repo)
    assert rep.ok and "newest session" in rep.checks[8].detail


def test_relay_absent_and_relay_off(machine):
    (machine.bin / "relay").unlink()
    assert failing(doctor.run(machine.env, machine.repo)) == ["relay"]
    cfg = machine.repo / ".claude/agentik/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('relay: {enabled: "off"}\n')
    rep = doctor.run(machine.env, machine.repo)
    assert rep.ok and "relay" not in [c.name for c in rep.checks]


def test_config_unknown_keys_reported_not_fatal(machine):
    cfg = machine.repo / ".claude/agentik/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("session: {colour: blue}\n")
    rep = doctor.run(machine.env, machine.repo)
    assert rep.ok and "session.colour" in rep.checks[11].detail


def test_config_unknown_profile_fails(machine):
    cfg = machine.repo / ".claude/agentik/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("session: {profile: nope}\n")
    assert failing(doctor.run(machine.env, machine.repo)) == ["config"]


def test_cli_exit_codes_and_json(machine, monkeypatch, capsys):
    for k, v in machine.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(machine.repo)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert cli.main(["doctor", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    (machine.bin / "tmux").unlink()
    assert cli.main(["doctor"]) == 2
    assert capsys.readouterr().out.rstrip().endswith("doctor: failing: relay")
    with pytest.raises(SystemExit) as e:
        cli.main(["doctor", "--bogus"])
    assert e.value.code == 2 or e.value.code == 1


def test_c1_manifest_declares_no_hard_dependency():
    # mod-r1 §9, decided: the siblings are optional, so neither the manifest nor doctor
    # holds a version range a sibling's release can break.
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert "dependencies" not in manifest
    assert [s["name"] for s in doctor.SIBLINGS] == ["decisions", "respeak", "relay"]
    assert all({"name", "marketplace", "old", "adds"} <= set(s)
               <= {"name", "marketplace", "old", "adds", "row"} for s in doctor.SIBLINGS)


# --- the plugin subtree ----------------------------------------------------------

PLUGIN = ROOT / "plugin"


def test_versions_agree():
    from claude_session import SEMVER, __version__
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert manifest["version"] == SEMVER
    assert f'version = "{__version__}"' in (ROOT / "pyproject.toml").read_text()
    assert manifest["name"] == "session"
    # agentik-r1 §5.2: the marketplace is agentik-commons'; this repo's file is gone.
    assert not (ROOT / ".claude-plugin/marketplace.json").exists()


def test_c1_the_version_moves_with_the_plugin():
    # C1 changes plugin/ (hooks.json, the shim), so the plugin's version moves with it.
    from claude_session import SEMVER, __version__
    assert (SEMVER, __version__) == ("2.0.0-alpha.27", "2.0.0a27")


def test_hooks_json_is_the_shim_on_session_start_only():
    hooks_json = json.loads((PLUGIN / "hooks/hooks.json").read_text())
    assert list(hooks_json["hooks"]) == list(doctor.HOOK_EVENTS) == [
        "SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
        "UserPromptSubmit", "Stop", "StopFailure", "SessionEnd", "PreCompact"]
    cmd = hooks_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert cmd == "${CLAUDE_PLUGIN_ROOT}/hooks/run SessionStart"
    assert os.access(PLUGIN / "hooks/run", os.X_OK)


def test_plugin_is_self_contained():
    """No file under plugin/ names a path outside it."""
    outside = ("../", "claude_session/", "/Users/", "~/")
    for f in PLUGIN.rglob("*"):
        if f.is_file():
            text = f.read_text()
            assert not [o for o in outside if o in text], f


def test_shim_is_silent_without_the_tool(tmp_path):
    import subprocess
    r = subprocess.run([str(PLUGIN / "hooks/run"), "SessionStart"], input="{}",
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_s19_shim_never_blocks_stop(tmp_path):
    # An older CLI on PATH refuses `hook Stop` with exit 2, and exit 2 on Stop blocks every
    # turn end; the shim swallows Stop's exit and stdout. Other events keep the tool's exit.
    import subprocess
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _exe(bin_ / "agentik-session", "cat >/dev/null; echo \"invalid choice: $2\" >&2; "
                                  "echo '{}'; exit 2\n")
    env = {"PATH": "%s:/usr/bin:/bin" % bin_}
    shim = lambda event: subprocess.run([str(PLUGIN / "hooks/run"), event], env=env, text=True,
                                        input='{"session_id": "s"}', capture_output=True)
    r = shim("Stop")
    assert (r.returncode, r.stdout) == (0, "")
    r = shim("PreToolUse")                                   # the positive control
    assert (r.returncode, r.stdout) == (2, "{}\n")


def test_skill_frontmatter():
    text = (PLUGIN / "skills/session/SKILL.md").read_text()
    head = text.split("---")[1]
    desc = [l for l in head.splitlines() if l.startswith("description:")][0]
    assert len(desc.split(":", 1)[1].strip()) < 200
    assert "Bash(agentik-session *)" in head and len(text.splitlines()) < 500
    assert not (ROOT / "SKILL.md").exists()


# review r6 C3, E8: a hook without a timeout inherits Claude Code's 60 s default, and a
# stall there is silent. Tool and prompt hooks get 5 s, SessionStart 10, SessionEnd 15.
HOOK_TIMEOUTS = {"SessionStart": 10, "SessionEnd": 15, "UserPromptSubmit": 5,
                 "PreToolUse": 5, "PostToolUse": 5, "PostToolUseFailure": 5, "PostToolBatch": 5,
                 "Stop": 5, "StopFailure": 5, "PreCompact": 5}


def test_every_hook_command_has_its_events_timeout():
    hooks_json = json.loads((PLUGIN / "hooks/hooks.json").read_text())
    seen = 0
    for event, groups in hooks_json["hooks"].items():
        assert event in HOOK_TIMEOUTS, f"{event}: no timeout ruled for this event"
        for group in groups:
            for h in group["hooks"]:
                assert h.get("type") == "command"
                assert h.get("timeout") == HOOK_TIMEOUTS[event], (event, h)
                seen += 1
    assert seen == len(doctor.HOOK_EVENTS)


# ---- S19: Stop and PreToolUse on every tool (respawn-r1 §3.3, criterion 18) ----

S19_EVENTS = ["SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure",
              "PostToolBatch", "UserPromptSubmit", "Stop", "StopFailure", "SessionEnd",
              "PreCompact"]
# S20b adds PostToolUseFailure; the stale-call fix (2026-10-11) adds PostToolBatch; C1 adds
# PreCompact (mod-r1 §6); S34 adds StopFailure (ruling 5)


def test_s19_hooks_register_stop_and_every_tool():
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert list(registered) == list(doctor.HOOK_EVENTS) == S19_EVENTS
    stop = [h for g in registered["Stop"] for h in g["hooks"]]
    assert [(h["command"], h["timeout"]) for h in stop] == [
        ("${CLAUDE_PLUGIN_ROOT}/hooks/run Stop", 5)]
    assert [g.get("matcher") for g in registered["PreToolUse"]] == ["*"]
    assert "Stop" in hooks.HANDLERS


def test_s19_doctor_red_without_stop(machine):
    path = machine.tmp / "install" / "hooks" / "hooks.json"
    path.write_text(json.dumps({"hooks": {e: [] for e in S19_EVENTS}}))
    assert failing(doctor.run(machine.env, machine.repo)) == []        # the positive control
    path.write_text(json.dumps({"hooks": {e: [] for e in S19_EVENTS if e != "Stop"}}))
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == ["plugin"]
    assert "Stop" in next(c for c in rep.checks if c.name == "plugin").detail


# ---- S20b: PostToolUseFailure, the shim, `--session-id` (S20 rulings 3 and 4, criterion 18)

def test_s20b_doctor_needs_session_id(machine):
    assert "--session-id" in doctor.CLAUDE_FLAGS
    assert failing(doctor.run(machine.env, machine.repo)) == []        # the positive control
    _exe(machine.bin / "claude", f'if [ "$1" = plugin ]; then /bin/cat {machine.tmp}/plugins.json;'
         ' exit 0; fi\necho "--model --effort --tools --permission-mode --max-budget-usd '
         '--output-format"\n')
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == ["claude"]
    assert "--session-id" in rep.checks[0].detail


def test_s20b_hooks_register_post_tool_use_failure():
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert "PostToolUseFailure" in doctor.HOOK_EVENTS
    groups = registered["PostToolUseFailure"]
    assert [g.get("matcher") for g in groups] == ["*"]
    assert [(h["type"], h["command"], h["timeout"]) for g in groups for h in g["hooks"]] == [
        ("command", "${CLAUDE_PLUGIN_ROOT}/hooks/run PostToolUseFailure", 5)]
    # the CLI handles every event its plugin registers
    assert [e for e in registered if e not in hooks.HANDLERS] == []


def test_s20b_shim_drops_post_tool_use_failure(tmp_path):
    # An older CLI refuses `hook PostToolUseFailure` with exit 2 (an event it does not
    # know); the shim treats it as Stop: exit 0, nothing on stdout. Other events keep theirs.
    import subprocess
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _exe(bin_ / "agentik-session", "cat >/dev/null; echo \"invalid choice: $2\" >&2; "
                                  "echo '{}'; exit 2\n")
    env = {"PATH": "%s:/usr/bin:/bin" % bin_}
    shim = lambda event: subprocess.run([str(PLUGIN / "hooks/run"), event], env=env, text=True,
                                        input='{"session_id": "s"}', capture_output=True)
    r = shim("PostToolUseFailure")
    assert (r.returncode, r.stdout) == (0, "")
    r = shim("PostToolUse")                                  # the positive control
    assert (r.returncode, r.stdout) == (2, "{}\n")


def test_s20b_doctor_names_a_cli_older_than_the_hooks(machine, monkeypatch):
    # The plugin registers an event this CLI does not handle: the CLI is older than the
    # plugin's hooks, and the doctor says to install the CLI first.
    assert failing(doctor.run(machine.env, machine.repo)) == []        # the positive control
    handlers = {k: v for k, v in hooks.HANDLERS.items() if k != "PostToolUseFailure"}
    monkeypatch.setattr(hooks, "HANDLERS", handlers)
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == ["plugin"]
    detail = next(c for c in rep.checks if c.name == "plugin").detail
    assert "PostToolUseFailure" in detail and "make install" in detail, detail


# ---- S20b's review: the mid-upgrade remedy (F4) and a whole flag (F5) --------------

def test_s20b_doctor_names_the_plugin_update_when_a_hook_is_missing(machine):
    path = machine.tmp / "install" / "hooks" / "hooks.json"
    path.write_text(json.dumps({"hooks": {e: [] for e in S19_EVENTS
                                          if e != "PostToolUseFailure"}}))
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == ["plugin"]
    detail = next(c for c in rep.checks if c.name == "plugin").detail
    assert "PostToolUseFailure" in detail, detail
    assert "claude plugin update session@agentik" in detail, detail


def test_s20b_doctor_flag_is_whole(machine):
    # `--session-id-file` is not `--session-id`: a flag is matched whole, never as a prefix.
    _exe(machine.bin / "claude", f'if [ "$1" = plugin ]; then /bin/cat {machine.tmp}/plugins.json;'
         ' exit 0; fi\necho "--model --effort --tools --permission-mode --max-budget-usd '
         '--output-format --session-id-file"\n')
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == ["claude"]
    assert "--session-id" in rep.checks[0].detail


# ---- the stale call (2026-10-11): PostToolBatch, registered and dropped by the shim ----

def test_s22_hooks_register_post_tool_batch():
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert "PostToolBatch" in doctor.HOOK_EVENTS and "PostToolBatch" in hooks.HANDLERS
    groups = registered["PostToolBatch"]
    assert [(h["type"], h["command"], h["timeout"]) for g in groups for h in g["hooks"]] == [
        ("command", "${CLAUDE_PLUGIN_ROOT}/hooks/run PostToolBatch", 5)]
    assert [e for e in registered if e not in hooks.HANDLERS] == []


def test_s22_shim_drops_post_tool_batch(tmp_path):
    # PostToolBatch's exit 2 stops the agentic loop, and an older CLI refuses an event it
    # does not know with exit 2: the shim treats it as Stop (exit 0, nothing on stdout).
    import subprocess
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _exe(bin_ / "agentik-session", "cat >/dev/null; echo \"invalid choice: $2\" >&2; "
                                  "echo '{}'; exit 2\n")
    env = {"PATH": "%s:/usr/bin:/bin" % bin_}
    shim = lambda event: subprocess.run([str(PLUGIN / "hooks/run"), event], env=env, text=True,
                                        input='{"session_id": "s"}', capture_output=True)
    r = shim("PostToolBatch")
    assert (r.returncode, r.stdout) == (0, "")
    r = shim("PostToolUse")                                  # the positive control
    assert (r.returncode, r.stdout) == (2, "{}\n")


# --- agentik-r1 §6.3: the renamed IDs, folder and key ------------------------------


def test_c7_old_ids_alone_are_warns_naming_the_switch(machine):
    # packet ruling 6: an old ID alone is a warn naming the switch, never a FAIL
    old = ["session@claude-code-session", "decisions@claude-code-decisions",
           "respeak@claude-code-respeak", "agent-relay@agent-relay"]
    ps = [dict(p, id=i) for p, i in zip(machine.plugins, old)]
    machine.set_plugins(ps)
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    warns = {c.name: c.detail for c in rep.checks if c.warn}
    for row, pid, new in (("plugin", old[0], "session@agentik"),
                          ("decisions", old[1], "decisions@agentik"),
                          ("respeak", old[2], "respeak@agentik"),
                          ("relay-plugin", old[3], "relay@agentik")):
        assert pid in warns[row] and f"install {new}, then disable {pid}" in warns[row]
    # both installed, the old disabled (the switch, §8.3 step 3): the new ID, no warn
    machine.set_plugins(machine.plugins + [dict(p, enabled=False) for p in ps])
    rep = doctor.run(machine.env, machine.repo)
    assert not [c for c in rep.checks if c.warn and c.name != "mod"]


def test_c4_c6_old_folder_and_key_are_warn_rows(machine):
    old = machine.repo / ".claude/claude-code-session"
    old.mkdir(parents=True)
    (old / "config.yaml").write_text('agent-relay: {enabled: "off"}\n')
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and "relay" not in [c.name for c in rep.checks]
    rows = {c.name: c.detail for c in rep.checks if c.warn}
    assert "(read): `git mv` it to" in rows["config-dir"]
    assert rows["config-key"].startswith("config.yaml: agent-relay is read as relay")
    assert [c.name for c in rep.checks][-2:] == ["config-dir", "config-key"]
    new = machine.repo / ".claude/agentik"
    new.mkdir()
    (new / "config.yaml").write_text("relay: {enabled: auto}\n")
    rows = {c.name: c.detail for c in doctor.run(machine.env, machine.repo).checks if c.warn}
    assert "unread" in rows["config-dir"] and "config-key" not in rows


def test_f2_new_and_old_ids_both_enabled_warn_to_disable_the_old(machine):
    # fix round F2: both IDs enabled fire every hook twice; a warn names the old to disable
    old = [dict(p, id=i) for p, i in zip(machine.plugins, (
        "session@claude-code-session", "decisions@claude-code-decisions"))]
    machine.set_plugins(machine.plugins + old)
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    warns = {c.name: c.detail for c in rep.checks if c.warn}
    assert "disable session@claude-code-session" in warns["plugin"]
    assert "each hook fires twice" in warns["plugin"]
    assert "disable decisions@claude-code-decisions" in warns["decisions"]
    assert "respeak" not in warns
