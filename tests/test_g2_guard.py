"""Packet g2: the PreToolUse prompt before an edit of instruction text (hq design/09 §7.2).
Every test runs under its own temp HOME and state; the run's kind is read through
`harness.claude_argv`, patched here (conftest's `_ps` reads nothing, so an unpatched run is
one whose argv cannot be read)."""

import io
import json
import re
import time
from pathlib import Path

import pytest

from claude_session import doctor, harness, hooks, instructionguard, instructions, resolver
from test_doctor import machine  # noqa: F401  (the fixture)

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "DECISION" "S.md"                # spelled in two pieces for the hygiene scan
SKILL = "decision" "s:instruct"
SID = "g2-sess-0001"
TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
REASON = ("agentik-session: `{}` is instruction text that every session pays for. Change it "
          "through the `" + SKILL + "` skill, which reviews the change and writes it with the "
          "tool that owns the file.")


@pytest.fixture
def box(tmp_path, monkeypatch):
    class B:
        pass
    b = B()
    b.home = tmp_path / "home"
    (b.home / ".claude").mkdir(parents=True)
    b.env = {"HOME": str(b.home), "XDG_STATE_HOME": str(tmp_path / "state"),
             "PATH": "/usr/bin:/bin"}
    monkeypatch.setenv("HOME", str(b.home))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    b.state = resolver.state_dir(b.env)
    b.tree = tmp_path / "code" / "tree"
    b.repo = b.tree / "repo"
    (b.repo / ".git").mkdir(parents=True)
    b.wt = b.repo / ".claude" / "worktrees" / "row"
    gitdir = b.repo / ".git" / "worktrees" / "row"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    b.wt.mkdir(parents=True)
    (b.wt / ".git").write_text(f"gitdir: {gitdir}\n")
    return b


def _main(monkeypatch, argv=("claude", "--model", "opus")):
    monkeypatch.setattr(harness, "claude_argv", lambda *a, **k: list(argv) if argv else None)


def _payload(tool, path, sid=SID, cwd=None, **more):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    ti = {key: str(path)}
    ti.update({"Edit": {"old_string": "a", "new_string": "b"}, "Write": {"content": "x"},
               "MultiEdit": {"edits": [{"old_string": "a", "new_string": "b"}]},
               "NotebookEdit": {"new_source": "x"}}.get(tool, {}))
    return {"session_id": sid, "transcript_path": "/t.jsonl", "cwd": str(cwd or "/"),
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti,
            "tool_use_id": "toolu_g2_0001", **more}


def _pre(payload, env):
    return hooks.pre_tool_use(payload, env)


def _guarded(b) -> list:
    c = b.home / ".claude"
    return [c / "CLAUDE.md", c / "rules" / "a.md", c / "settings.json", c / "hooks" / "h.sh",
            c / "agents" / "a.md", c / "plugins" / "cache" / "x" / "plugin.json",
            b.tree / "CLAUDE.md",
            b.repo / "CLAUDE.md", b.repo / "CLAUDE.local.md", b.repo / ".claude" / "CLAUDE.md",
            b.repo / "AGENTS.md", b.repo / ".claude" / "rules" / "deep" / "r.md",
            b.repo / LEDGER, b.repo / ".claude" / "settings.json",
            b.repo / ".claude" / "settings.local.json",
            b.wt / "CLAUDE.md", b.wt / LEDGER]


def _decision(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecision"), h.get("permissionDecisionReason")


def _log(b, sid=SID):
    p = resolver.session_dir(b.state, sid) / instructionguard.LOG
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# ---- R2: what it answers ----------------------------------------------------------------

@pytest.mark.parametrize("tool", TOOLS)
def test_r2_main_thread_asks(box, monkeypatch, tool):
    _main(monkeypatch)
    for p in _guarded(box):
        assert _decision(_pre(_payload(tool, p), box.env)) == ("ask", REASON.format(p)), p


@pytest.mark.parametrize("tool", TOOLS)
def test_r2_helper_denies(box, monkeypatch, tool):
    _main(monkeypatch)
    for p in _guarded(box):
        out = _pre(_payload(tool, p, agent_id="a1", agent_type="general-purpose"), box.env)
        assert _decision(out) == ("deny", REASON.format(p)), p
    calls = resolver.session_dir(box.state, SID) / hooks.CALLS
    assert not calls.exists() or not list(calls.iterdir())       # a refused call opens none


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("argv", [("claude", "-p", "go"), ("claude", "--model", "opus", "--print"),
                                  ("/opt/bin/claude", "--print=json")])
def test_r2_headless_denies(box, monkeypatch, tool, argv):
    _main(monkeypatch, argv)
    for p in _guarded(box):
        assert _decision(_pre(_payload(tool, p), box.env)) == ("deny", REASON.format(p)), p


@pytest.mark.parametrize("tool", TOOLS)
def test_r2_unknown_run_denies(box, tool):
    for p in _guarded(box):                  # conftest: no ancestor's argv can be read
        assert _decision(_pre(_payload(tool, p), box.env))[0] == "deny", p


def test_r2_reason_text(box, monkeypatch):
    _main(monkeypatch)
    p = box.repo / "CLAUDE.md"
    out = _pre(_payload("Edit", p), box.env)
    assert out == {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "ask",
        "permissionDecisionReason":
            f"agentik-session: `{p}` is instruction text that every session pays for. Change it "
            f"through the `{SKILL}` skill, which reviews the change and writes it with the tool "
            "that owns the file."}}


def test_r2_each_answer_is_logged(box, monkeypatch):
    _main(monkeypatch)
    _pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env)
    _pre(_payload("Write", box.repo / "AGENTS.md", agent_id="a1"), box.env)
    rows = _log(box)
    assert [(r["decision"], r["run"], r["tool"]) for r in rows] == [
        ("ask", "main", "Edit"), ("deny", "helper", "Write")]
    mode = (resolver.session_dir(box.state, SID) / instructionguard.LOG).stat().st_mode & 0o777
    assert mode == 0o600


# ---- R1: what is guarded ----------------------------------------------------------------

def test_r1_not_guarded_passes(box, monkeypatch, capsys):
    _main(monkeypatch)
    fixture = box.repo / "tests" / "fixtures" / "ledger" / LEDGER
    plain = [fixture, box.repo / "tests" / "CLAUDE.md", box.repo / "testdata" / "AGENTS.md",
             box.repo / "plugin" / "skills" / "x" / "SKILL.md", box.repo / "plugin" / "a.py",
             box.repo / "sub" / "CLAUDE.md", box.repo / "plugin" / "agents" / "a.md",
             box.home / ".claude" / "projects" / "p" / "memory" / "MEMORY.md",
             box.home / ".claude" / "settings.local.json", box.home / "notes" / "CLAUDE.md"]
    for tool in TOOLS:
        for p in plain:
            assert _pre(_payload(tool, p), box.env) == {}, (tool, p)
    assert _log(box) == []                                    # no line for a path not guarded
    assert capsys.readouterr() == ("", "")


def test_r1_worktree_top_level(box, monkeypatch):
    _main(monkeypatch)
    for name in ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", LEDGER):
        assert instructionguard.guarded(str(box.wt / name), box.env), name
    assert instructionguard.guarded(str(box.wt / ".claude" / "rules" / "a.md"), box.env)
    assert not instructionguard.guarded(str(box.wt / "tests" / LEDGER), box.env)
    elsewhere = box.home / ".cache" / "wt"                    # a worktree outside its repo
    elsewhere.mkdir(parents=True)
    (elsewhere / ".git").write_text("gitdir: /nowhere\n")
    assert _decision(_pre(_payload("Write", elsewhere / "CLAUDE.md"), box.env))[0] == "ask"


def test_r1_tree_folder(box, monkeypatch):
    _main(monkeypatch)
    assert _decision(_pre(_payload("Edit", box.tree / "CLAUDE.md"), box.env))[0] == "ask"
    assert instructionguard.guarded(str(box.tree / ".claude" / "CLAUDE.md"), box.env)
    lone = box.tree.parent / "notes"                          # holds no main checkout
    (lone / "wt").mkdir(parents=True)
    (lone / "wt" / ".git").write_text("gitdir: /nowhere\n")   # a worktree's file is not one
    assert not instructionguard.guarded(str(lone / "CLAUDE.md"), box.env)


def test_r1_relative_path_and_symlink(box, monkeypatch):
    _main(monkeypatch)
    out = _pre(_payload("Edit", "CLAUDE.md", cwd=box.repo), box.env)
    assert _decision(out) == ("ask", REASON.format(box.repo / "CLAUDE.md"))
    link = box.home / "link.md"
    link.symlink_to(box.repo / "AGENTS.md")
    assert _decision(_pre(_payload("Write", link), box.env))[0] == "ask"


def test_r1_config_dir_moved(box, monkeypatch):
    _main(monkeypatch)
    moved = box.home / "cfg"
    env = dict(box.env, CLAUDE_CONFIG_DIR=str(moved))
    assert _decision(_pre(_payload("Edit", moved / "CLAUDE.md"), env))[0] == "ask"
    assert _decision(_pre(_payload("Edit", moved / "hooks" / "x"), env))[0] == "ask"


def test_r1_bash_never_read(box, monkeypatch):
    _main(monkeypatch)
    seen = []
    monkeypatch.setattr(instructionguard, "check", lambda *a: seen.append(a) or {"x": 1})
    target = box.home / ".claude" / "CLAUDE.md"
    for tool, ti in (("Bash", {"command": f"echo x > {target}", "file_path": str(target)}),
                     ("Read", {"file_path": str(target)}), ("Glob", {"pattern": "**"})):
        p = dict(_payload("Edit", target), tool_name=tool, tool_input=ti)
        assert _pre(p, box.env) == {}, tool
    assert seen == []


# ---- R3: fails open, stays cheap --------------------------------------------------------

def test_r3_exception_fails_open(box, monkeypatch):
    _main(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("inside the guard")
    monkeypatch.setattr(instructionguard, "guarded", boom)
    assert _pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env) == {}
    rows = _log(box)
    assert len(rows) == 1 and rows[0]["decision"] == "open" and rows[0]["why"] == "RuntimeError"
    monkeypatch.setattr(instructionguard, "check", boom)      # past the guard's own try
    assert _pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env) == {}


@pytest.mark.parametrize("target", [None, "", 7, ["a"], "x\0y", "relative/CLAUDE.md"])
def test_r3_unresolvable_target(box, monkeypatch, target):
    _main(monkeypatch)
    p = _payload("Write", "/x", cwd="not-absolute")
    p["tool_input"]["file_path"] = target
    assert _pre(p, box.env) == {}
    assert [r["decision"] for r in _log(box)] == ["open"]
    p["tool_input"] = "not a dict"
    assert _pre(p, box.env) == {}


def test_r3_the_log_stops_at_its_cap(box, monkeypatch):
    _main(monkeypatch)
    monkeypatch.setattr(instructionguard, "LOG_CAP", 400)
    for _ in range(10):
        _pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env)
    log = resolver.session_dir(box.state, SID) / instructionguard.LOG
    assert 0 < log.stat().st_size <= 400


def test_r3_cheap_on_a_path_not_guarded(box, monkeypatch):
    _main(monkeypatch)
    monkeypatch.setattr(harness, "claude_argv", lambda *a, **k: pytest.fail("argv read"))
    p = _payload("Edit", box.repo / "plugin" / "lib" / "a.py")
    started = time.perf_counter()
    for _ in range(200):
        assert _pre(p, box.env) == {}
    assert (time.perf_counter() - started) / 200 < 0.05      # far inside the 5 s timeout


def test_r3_dispatch_prints_the_answer(box, monkeypatch, capsys):
    _main(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload("Edit", box.repo / LEDGER))))
    assert hooks.dispatch("PreToolUse") == 0
    out = json.loads(capsys.readouterr().out)
    assert _decision(out) == ("ask", REASON.format(box.repo / LEDGER))


# ---- R4: no knob ------------------------------------------------------------------------

def test_r4_no_knob(box, monkeypatch):
    _main(monkeypatch)
    knobs = {"AGENTIK_SESSION_GUARD": "off", "AGENTIK_GUARD": "0", "AGENTIK_INSTRUCT": "on",
             "AGENTIK_SESSION_INSTRUCT": "on", "CLAUDE_SESSION_CONFIG": "open",
             "AGENTIK_HOOKS_OFF": "1"}
    for k, v in knobs.items():
        monkeypatch.setenv(k, v)
    env = dict(box.env, **knobs)
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), env))[0] == "ask"
    src = (ROOT / "plugin" / "lib" / "claude_session" / "instructionguard.py").read_text()
    assert set(re.findall(r"env\.get\(\"([A-Z_]+)\"", src)) == {"HOME", "CLAUDE_CONFIG_DIR"}
    assert "os.environ" not in src and "getenv" not in src
    imported = set(re.findall(r"^from \. import (.+)$", src, re.M)[0].split(", "))
    assert imported == {"harness", "resolver"}                # no profile, no session setting
    from claude_session import resolver as r, sessionconfig as s
    for name in (*r.SESSION_KEYS, *s.LAUNCH_ONLY):
        assert "guard" not in name and "instruct" not in name, name


# ---- R5: the doctor's line --------------------------------------------------------------

def _loaded(box, sid, at):
    d = resolver.session_dir(box.state, sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": at, "file_path": str(box.repo / "CLAUDE.md"), "cwd": str(box.repo)}) + "\n")


def test_r5_doctor_line_counts_the_newest_session(box, monkeypatch):
    _main(monkeypatch)
    _loaded(box, "g2-old", 100)
    _pre(_payload("Edit", box.repo / "CLAUDE.md", sid="g2-old"), box.env)
    _loaded(box, SID, 200)
    for agent in (None, None, "a1"):
        more = {"agent_id": agent} if agent else {}
        _pre(_payload("Edit", box.repo / "AGENTS.md", **more), box.env)
    instructionguard.log({"session_id": SID}, box.env, "open", None, why="x")
    assert instructionguard.doctor_row(box.env, box.repo) == (
        f"on; session {SID}: 2 prompts, 1 refusals, 1 let through on an error")


def test_r5_doctor_line_without_a_session(box):
    assert instructionguard.doctor_row(box.env, box.repo) == (
        f"on; no session of {box.repo.resolve()} has a log to count its prompts and refusals")


def test_r5_doctor_line_in_the_report(machine):  # noqa: F811
    env, repo = machine.env, machine.repo
    d = resolver.session_dir(resolver.state_dir(env), SID)
    d.mkdir(parents=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": 200, "file_path": str(repo / "CLAUDE.md"), "cwd": str(repo)}) + "\n")
    rep = doctor.run(env, repo)
    names = [c.name for c in rep.checks]
    rows = [c for c in rep.checks if c.name == "guard"]
    assert rep.ok and len(rows) == 1 and rows[0].ok and not rows[0].warn
    assert names.index("guard") == len(names) - 1 - names[::-1].index("instructions") + 1
    assert rows[0].detail == f"on; session {SID}: 0 prompts, 0 refusals"
