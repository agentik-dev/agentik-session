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


def _installed(tmp_path, ps):
    """The plugin list `claude plugin list --json` prints, and Claude Code's record of the
    same installs (fk3 R2), each entry at scope `user`."""
    (tmp_path / "plugins.json").write_text(json.dumps(ps))
    rec = {}
    for p in ps:
        rec.setdefault(p["id"], []).append({"scope": "user", "version": p.get("version"),
                                            "installPath": p.get("installPath") or str(
                                                tmp_path / "cache" / p["id"])})
    f = tmp_path / "home" / ".claude" / "plugins" / "installed_plugins.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"version": 2, "plugins": rec}))


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
        "PreCompact": [], "PostModelSwitch": [], "InstructionsLoaded": [],   # wfg R7; g1 R1
        "SubagentStop": []}}))                                                 # h4 R1
    plugins = [
        {"id": "session@agentik", "version": "2.0.0", "enabled": True,
         "installPath": str(install)},
        {"id": "decisions@agentik", "version": "0.4.0", "enabled": True},
        {"id": "respeak@agentik", "version": "0.6.0", "enabled": True},
        {"id": "relay@agentik", "version": "0.1.0", "enabled": True},
    ]
    _installed(tmp_path, plugins)
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

    m.set_plugins = lambda ps: _installed(tmp_path, ps)
    m.home = tmp_path / "home"
    return m


def failing(rep):
    return [c.name for c in rep.checks if not c.ok]


def test_green_machine_in_order(machine):
    rep = doctor.run(machine.env, machine.repo)
    assert failing(rep) == [] and rep.ok
    assert [c.name for c in rep.checks] == [
        "claude", "python", "state-dir", "plugin", "decisions", "respeak", "relay-plugin",
        "profiles", "resolved", "meter", "meter-hook", "config", "git", "relay", "mod",
        "measure", "launcher", "instructions", "guard"]         # g1 R2: no log, one row; g2 R5


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
    c = doctor._check_python(machine.env, (3, 8, 12, "final", 0), "/opt/py/bin/python3")
    assert not c.ok and c.detail.startswith("3.8.12 (/opt/py/bin/python3)")
    assert c.detail.endswith("needs 3.9+")


def test_python_floor_is_3_9(machine):
    # /usr/bin/python3 on a bare Mac is 3.9.6 (hq entry 6, design/04 §2).
    assert not doctor._check_python(machine.env, (3, 8, 20, "final", 0), "/p").ok
    assert doctor._check_python(machine.env, (3, 9, 0, "final", 0), "/p").ok
    assert doctor._check_python(machine.env, (3, 9, 6, "final", 0), "/usr/bin/python3").ok


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
    assert list(notes) == ["decisions", "respeak", "relay-plugin", "relay", "launcher"]
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
    # fk3 R2, R4: a sibling installed alone from another marketplace stands; its id is in
    # the check's `source`, never its detail.
    c = next(c for c in rep.checks if c.name == "decisions")
    assert c.status == "ok" and "elsewhere" not in c.detail
    assert c.source["plugin"] == "decisions@elsewhere"


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


def _no_session(machine):
    """The machine with a state root that holds no session and no session id."""
    env = {k: v for k, v in machine.env.items() if k != "CLAUDE_CODE_SESSION_ID"}
    env["XDG_STATE_HOME"] = str(machine.tmp / "bare-state")
    return env


def test_fr1_no_session_at_all_is_two_ok_notes(machine):
    rep = doctor.run(_no_session(machine), machine.repo)
    rows = {c.name: c for c in rep.checks}
    for name in ("resolved", "meter"):
        assert rows[name].ok and rows[name].note, rows[name]
    assert "no session resolved yet" in rows["resolved"].detail
    assert "no session to meter" in rows["meter"].detail
    assert failing(rep) == [] and rep.ok


def test_fr1_cli_doctor_exits_0_with_no_session(machine, monkeypatch, capsys):
    for k, v in _no_session(machine).items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(machine.repo)
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "note resolved" in out and "note meter" in out
    assert out.rstrip().endswith("doctor: green")


def test_fr1_a_session_without_its_files_still_fails(machine):
    # an id that names no session's files: as test_no_resolved_file, both stay red
    env = {**_no_session(machine), "CLAUDE_CODE_SESSION_ID": "another"}
    assert failing(doctor.run(env, machine.repo)) == ["resolved", "meter"]
    # a session that resolved and was never metered: meter alone stays red
    bare = {**machine.env, "XDG_STATE_HOME": str(machine.tmp / "bare-state"),
            "CLAUDE_CODE_SESSION_ID": "sess-2"}
    hooks.session_start({"session_id": "sess-2", "cwd": str(machine.repo)}, bare)
    assert failing(doctor.run(_no_session(machine), machine.repo)) == ["meter"]


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
    assert '"version"' in (ROOT / "pyproject.toml").read_text()    # read from the package
    assert manifest["name"] == "session"
    # agentik-r1 §5.2: the marketplace is agentik-commons'; this repo's file is gone.
    assert not (ROOT / ".claude-plugin/marketplace.json").exists()


def test_c1_the_version_moves_with_the_plugin():
    # C1 changes plugin/ (hooks.json, the shim), so the plugin's version moves with it.
    from claude_session import SEMVER, __version__
    assert __version__ == SEMVER.replace("-alpha.", "a")


def test_hooks_json_is_the_shim_on_session_start_only():
    hooks_json = json.loads((PLUGIN / "hooks/hooks.json").read_text())
    assert list(hooks_json["hooks"]) == list(doctor.HOOK_EVENTS) == [
        "SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
        "UserPromptSubmit", "Stop", "StopFailure", "SessionEnd", "PreCompact",
        "PostModelSwitch", "InstructionsLoaded", "SubagentStop"]
    cmd = hooks_json["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert cmd == "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" SessionStart"
    assert os.access(PLUGIN / "hooks/run", os.X_OK)


def test_plugin_is_self_contained():
    """No file under plugin/ names a path outside it; the package, its own home since sc2,
    names the user's own folders in its docs, and never a clone."""
    outside = ("../", "claude_session/", "/Users/", "~/")
    for f in PLUGIN.rglob("*"):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        said = ("/Users/",) if (PLUGIN / "lib") in f.parents else outside
        text = f.read_text()
        assert not [o for o in said if o in text], f


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
    env = {"PATH": "%s:/usr/bin:/bin" % bin_, "CLAUDE_PLUGIN_ROOT": str(tmp_path)}
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
                 "Stop": 5, "StopFailure": 5, "PreCompact": 5, "PostModelSwitch": 5,
                 "InstructionsLoaded": 5,      # g1 R1: the plugin's hook timeout
                 "SubagentStop": 5}            # h4 R1: Stop's


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
              "PreCompact", "PostModelSwitch", "InstructionsLoaded", "SubagentStop"]
# h4 adds SubagentStop (R1); g1 adds InstructionsLoaded (R1); wfg adds PostModelSwitch (R7); S20b adds PostToolUseFailure; the stale-call fix (2026-10-11) adds PostToolBatch; C1 adds
# PreCompact (mod-r1 §6); S34 adds StopFailure (ruling 5)


def test_s19_hooks_register_stop_and_every_tool():
    registered = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert list(registered) == list(doctor.HOOK_EVENTS) == S19_EVENTS
    stop = [h for g in registered["Stop"] for h in g["hooks"]]
    assert [(h["command"], h["timeout"]) for h in stop] == [
        ("\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" Stop", 5)]
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
        ("command", "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" PostToolUseFailure", 5)]
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
    env = {"PATH": "%s:/usr/bin:/bin" % bin_, "CLAUDE_PLUGIN_ROOT": str(tmp_path)}
    shim = lambda event: subprocess.run([str(PLUGIN / "hooks/run"), event], env=env, text=True,
                                        input='{"session_id": "s"}', capture_output=True)
    r = shim("PostToolUseFailure")
    assert (r.returncode, r.stdout) == (0, "")
    r = shim("PostToolUse")                                  # the positive control
    assert (r.returncode, r.stdout) == (2, "{}\n")


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
        ("command", "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" PostToolBatch", 5)]
    assert [e for e in registered if e not in hooks.HANDLERS] == []


def test_s22_shim_drops_post_tool_batch(tmp_path):
    # PostToolBatch's exit 2 stops the agentic loop, and an older CLI refuses an event it
    # does not know with exit 2: the shim treats it as Stop (exit 0, nothing on stdout).
    import subprocess
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _exe(bin_ / "agentik-session", "cat >/dev/null; echo \"invalid choice: $2\" >&2; "
                                  "echo '{}'; exit 2\n")
    env = {"PATH": "%s:/usr/bin:/bin" % bin_, "CLAUDE_PLUGIN_ROOT": str(tmp_path)}
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


# ---- sc3: the launcher in ~/.local/bin ----------------------------------------------------

def _launcher_at(tmp_path, *lines):
    path = tmp_path / ".local" / "bin" / "agentik-session"
    path.parent.mkdir(parents=True)
    path.write_text("#!/bin/sh\n" + "".join(line + "\n" for line in lines))
    return {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}


def _row(check):
    return ("FAIL" if not check.ok else "warn" if check.warn else "note" if check.note else "ok")


def test_sc3_no_launcher_is_a_note_naming_the_verb(tmp_path):
    c = doctor._check_launcher({"HOME": str(tmp_path)}, None)
    assert _row(c) == "note" and "/session:install-cli" in c.detail


def test_sc3_a_launcher_older_than_the_plugin_warns(tmp_path):
    env = _launcher_at(tmp_path, "VERSION=2.0.0-alpha.9", "TREE=%s" % tmp_path)
    plugins = {doctor.PLUGIN_ID: {"enabled": True, "version": "2.0.0-alpha.10"}}
    c = doctor._check_launcher(env, plugins)
    assert _row(c) == "warn" and "older than the plugin's 2.0.0-alpha.10" in c.detail
    assert _row(doctor._check_launcher(env, {doctor.PLUGIN_ID: {"enabled": True,
                                                                "version": "2.0.0-alpha.9"}})) == "ok"


def test_sc3_a_launcher_with_no_version_line_warns_and_a_bad_one_too(tmp_path):
    env = _launcher_at(tmp_path, 'CODE="%s"' % tmp_path, 'PYTHON="/venv/bin/python"')
    c = doctor._check_launcher(env, None)
    assert _row(c) == "warn" and "no VERSION=" in c.detail
    (tmp_path / ".local" / "bin" / "agentik-session").write_text("VERSION=banana\n")
    c = doctor._check_launcher(env, None)
    assert _row(c) == "warn" and "banana" in c.detail


@pytest.mark.parametrize("line", ("TREE=%s", 'CODE="%s"'))
def test_sc3_a_launcher_on_a_gone_tree_fails(tmp_path, line):
    env = _launcher_at(tmp_path, "VERSION=2.0.0-alpha.9", line % (tmp_path / "gone"))
    c = doctor._check_launcher(env, None)
    assert _row(c) == "FAIL" and "which is gone" in c.detail and "/session:install-cli" in c.detail


def test_sc3_the_python_row_reads_the_launchers_interpreter(tmp_path):
    version = (3, 9, 6, "final", 0)
    plain = {"HOME": str(tmp_path / "none"), "PATH": "/usr/bin:/bin"}
    assert "the launcher runs" not in doctor._check_python(plain, version, "/p").detail
    env = _launcher_at(tmp_path, "VERSION=2.0.0-alpha.9", "TREE=%s" % tmp_path)
    c = doctor._check_python(env, version, "/p")
    assert "the launcher runs /usr/bin/python3" in c.detail and not c.warn
    (tmp_path / ".local" / "bin" / "agentik-session").write_text('PYTHON="/gone/python"\nCODE="/x"\n')
    c = doctor._check_python(env, version, "/p")
    assert "the launcher runs /gone/python, which is gone" in c.detail and c.ok and c.warn


# ---- fk3: the sibling check takes the suite's answer about which plugin stands -------------

FORK = "respeak@acme-tools"
OWN = {"id": "respeak@agentik", "version": "0.7.0", "enabled": True}


def _src(tool="respeak", kind="plugin", plugin=FORK, version="0.12.6", found=True,
         declared=None, seen=None, root=None):
    return {"tool": tool, "kind": kind, "plugin": plugin, "version": version, "found": found,
            "root": root or f"/cache/{plugin or tool}", "declared": declared,
            "seen": seen if seen is not None else []}


def _answer(*rows, schema="agentik.sources/1", ok=True):
    return {"schema": schema, "ok": ok, "tool": "suite", "tools": list(rows)}


def _suite(machine, body):
    """A stub launcher at the suite's fixed place; `body` a dict prints as its answer."""
    d = machine.home / ".local" / "bin"
    d.mkdir(parents=True, exist_ok=True)
    if isinstance(body, dict):
        (machine.tmp / "answer.json").write_text(json.dumps(body))
        body = f"/bin/cat {machine.tmp}/answer.json\n"
    _exe(d / "agentik-suite", body)


def _with(machine, *extra, drop="respeak@agentik"):
    machine.set_plugins([p for p in machine.plugins if p["id"] != drop] + list(extra))


def _named(rep, name="respeak"):
    return next(c for c in rep.checks if c.name == name)


def _line(rep, name="respeak"):
    return next(ln for ln in doctor.render(rep).splitlines() if ln.split()[1] == name)


def _dict(rep, name="respeak"):
    return next(c for c in rep.as_dict()["checks"] if c["name"] == name)


def _fork_stands(rep):
    c = _named(rep)
    assert (c.status, c.detail) == ("ok", "installed")
    assert "acme" not in c.detail and "acme" not in (c.remedy or "")
    assert f"{FORK} 0.12.6" in _line(rep)
    assert _dict(rep)["source"]["plugin"] == FORK and _dict(rep)["source"]["kind"] == "plugin"
    assert rep.ok


def test_fk3_line1_the_suite_says_a_fork_stands_alone(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    _suite(machine, _answer(_src()))
    _fork_stands(doctor.run(machine.env, machine.repo))


def test_fk3_line2_absent_and_undecided(machine):
    _with(machine)
    _suite(machine, _answer(_src(kind="absent", plugin=None, version=None, found=False)))
    c = _named(doctor.run(machine.env, machine.repo))
    assert c.status == "note" and c.detail.startswith("not installed, optional: ")
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True}, drop=None)
    seen = [{"plugin": "respeak@agentik", "version": "0.7.0", "scope": "user", "root": "/a"},
            {"plugin": FORK, "version": "0.12.6", "scope": "user", "root": "/b"}]
    _suite(machine, _answer(_src(kind="undecided", plugin=None, version=None, found=False,
                                 seen=seen)))
    rep = doctor.run(machine.env, machine.repo)
    c = _named(rep)
    assert c.status == "warn" and c.ok and "2 plugins" in c.detail
    assert c.remedy == "agentik config suite.sources.respeak"
    assert "acme" not in c.detail and "@agentik" not in c.detail
    assert [s["plugin"] for s in _dict(rep)["source"]["seen"]] == ["respeak@agentik", FORK]
    assert FORK in _line(rep) and "respeak@agentik 0.7.0" in _line(rep)


def test_fk3_line2_a_line_naming_a_missing_plugin_or_a_gone_folder_warns(machine):
    _with(machine)
    decl = {"path": "/cfg/config.yaml", "line": 7}
    for row in (_src(found=False, declared=decl),
                _src(kind="folder", plugin=None, found=False, declared=decl, root="/gone")):
        _suite(machine, _answer(row))
        rep = doctor.run(machine.env, machine.repo)
        c = _named(rep)
        assert c.status == "warn" and "/cfg/config.yaml:7" in c.detail and "acme" not in c.detail
        assert "/gone" not in c.detail
    assert "/gone" in _line(rep)


def test_fk3_a_folder_that_stands_is_installed(machine):
    _with(machine)
    _suite(machine, _answer(_src(kind="folder", plugin=None, root="/src/respeak", version="0.9.0",
                                 declared={"path": "/cfg/config.yaml", "line": 3})))
    rep = doctor.run(machine.env, machine.repo)
    assert (_named(rep).status, _named(rep).detail) == ("ok", "installed")
    assert "/src/respeak 0.9.0" in _line(rep)
    assert _dict(rep)["source"]["declared"] == {"path": "/cfg/config.yaml", "line": 3}


def test_fk3_line3_the_fork_not_enabled(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": False})
    _suite(machine, _answer(_src()))
    rep = doctor.run(machine.env, machine.repo)
    c = _named(rep)
    assert c.status == "note" and c.detail.startswith("installed, disabled, optional")
    assert "acme" not in c.detail and f"{FORK} 0.12.6" in _line(rep)


LIARS = {
    "none": None,
    "exit 2": "echo 'usage: agentik-suite describe' >&2\nexit 2\n",
    "ok false": _answer(_src(kind="absent", plugin=None, found=False), ok=False),
    "another schema": _answer(_src(kind="absent", plugin=None, found=False),
                              schema="agentik.sources/2"),
    "no json": "echo ok\n",
    "a bad kind": _answer(_src(kind="whatever")),
    "floods": "exec /usr/bin/yes '{\"schema\": \"agentik.sources/1\"}'\n",
    "sleeps": "sleep 30\n",
}


@pytest.mark.parametrize("liar", sorted(LIARS))
def test_fk3_line4_no_answer_reads_the_file(machine, monkeypatch, liar):
    monkeypatch.setattr(doctor, "SOURCES_WALL", 1.0)
    if LIARS[liar] is not None:
        _suite(machine, LIARS[liar])
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    _fork_stands(doctor.run(machine.env, machine.repo))
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True}, drop=None)
    c = _named(doctor.run(machine.env, machine.repo))
    assert c.status == "note" and "not checked: say which with the suite's sources" in c.detail
    assert "acme" not in c.detail
    _with(machine)
    c = _named(doctor.run(machine.env, machine.repo))
    assert c.status == "note" and c.detail.startswith("not installed, optional: ")


def test_fk3_line4_only_user_and_managed_scopes_count(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    f = machine.home / ".claude" / "plugins" / "installed_plugins.json"
    rec = json.loads(f.read_text())
    rec["plugins"][FORK][0]["scope"] = "project"
    f.write_text(json.dumps(rec))
    assert _named(doctor.run(machine.env, machine.repo)).detail.startswith("not installed")
    rec["plugins"][FORK][0]["scope"] = "managed"
    f.write_text(json.dumps(rec))
    _fork_stands(doctor.run(machine.env, machine.repo))


def test_fk3_line4_the_file_under_claude_config_dir(machine, tmp_path):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    cfg = tmp_path / "cfg"
    (cfg / "plugins").mkdir(parents=True)
    (machine.home / ".claude" / "plugins" / "installed_plugins.json").rename(
        cfg / "plugins" / "installed_plugins.json")
    _fork_stands(doctor.run(dict(machine.env, CLAUDE_CONFIG_DIR=str(cfg)), machine.repo))


def test_fk3_line5_own_by_the_read_and_by_the_file(machine):
    ps = [dict(p) for p in machine.plugins]
    ps[2]["version"] = "0.7.0"
    machine.set_plugins(ps)
    for answer in (None, _answer(_src(kind="own", plugin="respeak@agentik", version="0.7.0"))):
        if answer:
            _suite(machine, answer)
        rep = doctor.run(machine.env, machine.repo)
        assert _named(rep).detail == "respeak@agentik 0.7.0 installed"
        assert _named(rep).source is None and _dict(rep)["source"] is None


def test_fk3_line7_the_launcher_starts_once_a_run(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    (machine.tmp / "answer.json").write_text(json.dumps(_answer(_src())))
    _suite(machine, f"echo started >> {machine.tmp}/starts\n"
                    f"/bin/cat {machine.tmp}/answer.json\n")
    _fork_stands(doctor.run(machine.env, machine.repo))
    assert (machine.tmp / "starts").read_text() == "started\n"


def test_fk3_line7_a_sleeping_launcher_costs_one_wall(machine):
    import time
    assert doctor.SOURCES_WALL == 5.0
    _suite(machine, "sleep 30\n")
    t = time.monotonic()
    rep = doctor.run(machine.env, machine.repo)
    assert time.monotonic() - t < doctor.SOURCES_WALL + 1
    assert _named(rep).detail == "respeak@agentik 0.6.0 installed" and rep.ok


def test_fk3_a_liars_text_reaches_no_line_raw(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    _suite(machine, _answer(_src(version="0.12.6\x1b[2J")))
    line = _line(doctor.run(machine.env, machine.repo))
    assert "\x1b" not in line and FORK in line


# ---- fk3, fix of review 1 ------------------------------------------------------------------

_BAD = "\x9b‮\x07\x1b"


def test_fk3_f1_no_control_or_format_character_reaches_the_line(machine):
    # C1 controls (U+009B is CSI), bidi overrides (U+202E), BEL and ESC: none is printed.
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    _suite(machine, _answer(_src(plugin=f"respeak@acme{_BAD}x", version=f"0.12.6{_BAD}1A")))
    line = _line(doctor.run(machine.env, machine.repo))
    assert not [ch for ch in _BAD if ch in line], repr(line)
    assert "respeak@acmex" in line and "0.12.61A" in line


def test_fk3_f2_a_child_holding_the_pipe_costs_no_wall(machine):
    import time
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    (machine.tmp / "answer.json").write_text(json.dumps(_answer(_src())))
    _suite(machine, f"/bin/sleep 30 &\n/bin/cat {machine.tmp}/answer.json\nexit 0\n")
    t = time.monotonic()
    rep = doctor.run(machine.env, machine.repo)
    took = time.monotonic() - t
    assert "installed (from respeak@acme-tools 0.12.6)" in _line(rep)
    assert took < 3.0, took
    _fork_stands(rep)


def test_fk3_f2_the_wall_and_the_cap_still_hold_for_a_launcher_that_runs_on(machine,
                                                                            monkeypatch):
    import time
    monkeypatch.setattr(doctor, "SOURCES_WALL", 1.0)
    for body in (f"/bin/cat {machine.tmp}/answer.json\nexec /bin/sleep 30\n",
                 "exec /usr/bin/yes '{\"schema\": \"agentik.sources/1\"}'\n"):
        (machine.tmp / "answer.json").write_text(json.dumps(_answer(_src(kind="absent"))))
        _suite(machine, body)
        t = time.monotonic()
        rep = doctor.run(machine.env, machine.repo)
        assert time.monotonic() - t < doctor.SOURCES_WALL + 1
        assert _named(rep).detail == "respeak@agentik 0.6.0 installed"   # the file's road


LONG = "respeak@" + "m" * 240


def test_fk3_f3_a_long_id_that_stands_reads_installed_by_both_roads(machine):
    _with(machine, {"id": LONG, "version": "1.0.0", "enabled": True})
    for answer in (_answer(_src(plugin=LONG, version="1.0.0")), None):
        if answer:
            _suite(machine, answer)
        else:
            (machine.home / ".local" / "bin" / "agentik-suite").unlink()
        rep = doctor.run(machine.env, machine.repo)
        assert (_named(rep).status, _named(rep).detail) == ("ok", "installed")
        line = _line(rep)
        assert LONG[:200] in line and LONG not in line


def test_fk3_f4_no_launcher_under_a_home_that_is_not_absolute(machine, monkeypatch, tmp_path):
    # A relative HOME would be checked against the doctor's cwd and started from the
    # project's: no launcher at all, so no file under the project folder is started.
    elsewhere = tmp_path / "elsewhere"
    for top in (elsewhere, machine.repo):
        d = top / "rh" / ".local" / "bin"
        d.mkdir(parents=True)
        _exe(d / "agentik-suite", f"echo ran > {top}/ran\n/bin/cat {machine.tmp}/answer.json\n")
    (machine.tmp / "answer.json").write_text(json.dumps(_answer(_src(version="6.6.6"))))
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    monkeypatch.chdir(elsewhere)
    for home in ("rh", ""):
        rep = doctor.run(dict(machine.env, HOME=home), machine.repo)
        assert not (machine.repo / "ran").exists() and not (elsewhere / "ran").exists()
        assert "6.6.6" not in _line(rep)


def _recorded_as(machine, pid, *recs):
    f = machine.home / ".claude" / "plugins" / "installed_plugins.json"
    rec = json.loads(f.read_text())
    rec["plugins"][pid] = list(recs)
    f.write_text(json.dumps(rec))


def test_fk3_f5_one_id_at_user_and_managed_stands_its_version_only_when_they_agree(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    _recorded_as(machine, FORK, {"scope": "user", "version": "0.12.6"},
                 {"scope": "managed", "version": "0.13.0"})
    rep = doctor.run(machine.env, machine.repo)
    assert (_named(rep).status, _named(rep).detail) == ("ok", "installed")
    assert _line(rep).endswith(f"installed (from {FORK})")
    _recorded_as(machine, FORK, {"scope": "user", "version": "0.12.6"},
                 {"scope": "managed", "version": "0.12.6"})
    assert _line(doctor.run(machine.env, machine.repo)).endswith(
        f"installed (from {FORK} 0.12.6)")


# The pin's lines (5890501) for the own ids of the machine fixture.
PIN = {"decisions": "decisions@agentik 0.4.0 installed",
       "relay-plugin": "relay@agentik 0.1.0 installed"}


def test_fk3_f6_a_project_scope_relay_reads_as_at_the_pin(machine):
    _recorded_as(machine, "relay@agentik", {"scope": "project", "projectPath": "/r"})
    rep = doctor.run(machine.env, machine.repo)
    c = _named(rep, "relay-plugin")
    assert (c.status, c.detail, c.source) == ("ok", PIN["relay-plugin"], None)
    assert _named(rep, "git").detail.endswith("guarded by the relay plugin (its check above)")


def test_fk3_f6_no_installs_file_reads_as_at_the_pin(machine):
    _with(machine, {"id": FORK, "version": "0.12.6", "enabled": True})
    (machine.home / ".claude" / "plugins" / "installed_plugins.json").unlink()
    rep = doctor.run(machine.env, machine.repo)
    assert _named(rep, "decisions").detail == PIN["decisions"]
    assert _named(rep, "relay-plugin").detail == PIN["relay-plugin"]
    c = _named(rep)
    assert c.status == "note" and c.detail == (
        "not installed, optional: the plain-English renderer the built-in profiles load "
        "(`respeak@agentik`)")
    assert _named(rep, "git").detail.endswith("guarded by the relay plugin (its check above)")


def test_fk3_f6_an_own_id_disabled_with_no_entry_reads_as_at_the_pin(machine):
    ps = [dict(p) for p in machine.plugins]
    ps[1]["enabled"] = False
    machine.set_plugins(ps)
    (machine.home / ".claude" / "plugins" / "installed_plugins.json").write_text("not json")
    c = _named(doctor.run(machine.env, machine.repo), "decisions")
    assert (c.status, c.detail) == ("note", "decisions@agentik 0.4.0 installed, disabled, "
                                    "optional: the decisions ledger, which reads its section "
                                    "of the resolved configuration")


def test_fk3_l4_the_source_text_withholds_a_secret_as_the_detail_does(machine):
    _with(machine)
    root = "/cfg/sources.yaml: line 3: mapping values are not allowed 'not-for-print'"
    _suite(machine, _answer(_src(kind="folder", plugin=None, root=root, version="0.9.0")))
    line = _line(doctor.run(machine.env, machine.repo))
    assert "/cfg/sources.yaml: line 3: mapping values are not allowed" in line
    assert "not-for-print" not in line


# ---- fk3 F7: the relay's standing when the plugin list was not read ------------------------

def _list_unread(machine):
    _exe(machine.bin / "claude", 'if [ "$1" = plugin ]; then echo boom >&2; exit 1; fi\n'
         'echo "--model --effort --tools --permission-mode '
         '--max-budget-usd --output-format --session-id"\n')
    (machine.bin / "relay").unlink()


def test_fk3_f7_an_unread_list_and_no_other_road_leaves_the_relay_unknown(machine):
    _list_unread(machine)
    _with(machine, drop="relay@agentik")        # the installs file holds no relay
    rep = doctor.run(machine.env, machine.repo)
    c = _named(rep, "relay")
    assert (c.status, c.detail) == ("note", "relay.enabled is auto and the relay plugin was "
                                    "not checked: no relay expected")
    assert _named(rep, "git").detail.endswith("; push: never, the relay plugin not checked")
    assert "relay" not in failing(rep)
    _exe(machine.bin / "relay", "exit 0\n")     # both programs there: ok as today
    c = _named(doctor.run(machine.env, machine.repo), "relay")
    assert (c.status, c.detail) == ("ok", "relay and tmux on PATH")


def test_fk3_f7_the_installs_file_answers_for_the_relay(machine):
    _list_unread(machine)
    rep = doctor.run(machine.env, machine.repo)
    assert _named(rep, "git").detail.endswith("guarded by the relay plugin (its check above)")
    assert _named(rep, "relay").detail == "relay.enabled is auto; not on PATH: relay"


def test_fk3_f7_relay_on_still_fails_when_a_program_is_missing(machine):
    _list_unread(machine)
    _with(machine, drop="relay@agentik")
    cfg = machine.repo / ".claude/agentik/config.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('relay: {enabled: "on"}\n')
    c = _named(doctor.run(machine.env, machine.repo), "relay")
    assert (c.ok, c.detail) == (False, "relay.enabled is on; not on PATH: relay")
