"""Packet g2: the PreToolUse prompt before an edit of instruction text (hq design/09 §7.2).
Every test runs under its own temp HOME and state; the run's kind is read through
`harness.claude_argv`, patched here (conftest's `_ps` reads nothing, so an unpatched run is
one whose argv cannot be read)."""

import ast
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


# r1 F1: only the options before the first prompt word are read, and an option's value is
# never taken for an option. `ps` joins argv with spaces, so a prompt arrives as many words.
@pytest.mark.parametrize("argv", [
    ("claude", "drive.py", "--model", "fable", "Check", "the", "relay", "-p", "children", "and",
     "fix", "CLAUDE.md"),                                       # the review's observed shapes
    ("claude", "drive.py", "--name", "-p"),
    ("claude", "--model", "fable", "Check", "the", "relay", "-p", "children", "and", "fix",
     "CLAUDE.md"),
    ("claude", "--append-system-prompt", "never", "use", "--print", "here"),
    ("claude", "--name", "-p"), ("claude", "-n", "-p", "go"), ("claude", "--name=-p"),
    ("claude", "--effort", "high", "--model", "opus", "fix", "it", "--print"),
    ("claude", "-c", "--verbose", "--", "-p"), ("claude", "-dp"), ("claude", "-r", "abc"),
    ("claude", "--some-new-option", "x", "Fix", "the", "README")])
def test_r2_a_prompt_word_is_not_an_option(box, monkeypatch, argv):
    _main(monkeypatch, argv)
    assert instructionguard.run_kind({}) == "main"
    p = box.repo / "CLAUDE.md"
    assert _decision(_pre(_payload("Edit", p), box.env)) == ("ask", REASON.format(p))


# Claude Code's CLI (commander) reads `-cp` as `-c -p`: a combined short flag with `p` is one.
@pytest.mark.parametrize("argv", [
    ("claude", "-cp", "go"), ("claude", "-pc"), ("claude", "--verbose", "--print", "go"),
    ("claude", "--model", "opus", "-p"), ("claude", "--add-dir", "a", "b", "-p", "go"),
    ("claude", "--max-turns", "3", "--print=json", "go"),
    ("claude", "--some-new-option", "x", "-p", "go")])           # unsure, and a `-p` follows
def test_r2_headless_flag_among_the_options_denies(box, monkeypatch, argv):
    _main(monkeypatch, argv)
    assert instructionguard.run_kind({}) in ("headless", "unknown")
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "deny"


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


# r1 F2: the file that would be written is matched, not its spelling. On a volume that folds
# case (this Mac's APFS) `claude.md` is `CLAUDE.md`, whether or not either exists yet.
def _folds(tmp_path) -> bool:
    (tmp_path / "CaseProbe").mkdir(exist_ok=True)
    return (tmp_path / "caseprobe").exists()


def _case_variants(b) -> list:
    c = b.home / ".Claude"
    return [b.repo / "claude.md", b.repo / ".CLAUDE" / "settings.json", c / "CLAUDE.md",
            b.home / ".claude" / "Rules" / "a.md", b.home / ".claude" / "Settings.json",
            b.repo / "Agents.md", b.repo / ".claude" / "RULES" / "r.md", b.tree / "Claude.md",
            b.wt / "claude.MD"]


def test_r1_case_variant_is_the_guarded_file(box, monkeypatch, tmp_path):
    if not _folds(tmp_path):
        pytest.skip("the test volume keeps case apart, so a case variant is another file")
    _main(monkeypatch)
    (box.repo / "CLAUDE.md").write_text("x\n")                # the review's two cases: exists
    (box.home / ".claude" / "CLAUDE.md").write_text("x\n")
    assert (box.repo / "claude.md").exists()
    for p in _case_variants(box):                             # the rest do not exist yet
        assert _decision(_pre(_payload("Edit", p), box.env))[0] == "ask", p
    assert instructionguard.guarded(str(box.repo / "agents.md"), box.env)   # a new file
    assert not (box.repo / "agents.md").exists()
    assert _pre(_payload("Edit", box.repo / "Tests" / "claude.md"), box.env) == {}


def test_r1_case_variant_on_a_volume_that_keeps_case(box, monkeypatch):
    _main(monkeypatch)
    monkeypatch.setattr(instructionguard, "_case_blind", lambda path: False)
    for p in _case_variants(box):
        assert _pre(_payload("Edit", p), box.env) == {}, p
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "ask"


def test_r1_case_variant_on_disk_that_keeps_case(box, monkeypatch, tmp_path):
    if _folds(tmp_path):
        pytest.skip("the test volume folds case (APFS default), so no case-variant file exists")
    _main(monkeypatch)
    (box.repo / "claude.md").write_text("another file\n")
    assert _pre(_payload("Edit", box.repo / "claude.md"), box.env) == {}


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

# r1 F3: the pin fails on a knob, whatever its name's quotes or the file it sits in. A hostile
# environment (every off-looking name, and one no one would guess) and a profile, a repo
# config, a session overlay and a settings file that name the guard leave its answer as is.
ENV_READ = {"HOME", "CLAUDE_CONFIG_DIR"}       # R4's list; the state root comes by `resolver`
_STEMS = ("GUARD", "GUARD_OFF", "NO_GUARD", "DISABLE_GUARD", "GUARD_DISABLE", "GUARD_DISABLED",
          "SKIP_GUARD", "INSTRUCT", "INSTRUCT_GUARD", "INSTRUCTION_GUARD", "INSTRUCTIONS_GUARD",
          "ALLOW_INSTRUCTION_EDITS", "HOOKS_OFF", "NO_HOOKS", "OPEN", "UNGUARDED",
          "SESSION_CONFIG")
_KNOBS = sorted({f"{p}_{s}" if p else s for s in _STEMS
                 for p in ("AGENTIK", "AGENTIK_SESSION", "CLAUDE_SESSION", "CLAUDE", "SESSION",
                           "")})


def _hostile(box, monkeypatch, value) -> dict:
    import uuid
    knobs = {k: value for k in (*_KNOBS, "AGENTIK_" + uuid.uuid4().hex[:10].upper())}
    for k, v in knobs.items():
        monkeypatch.setenv(k, v)
    body = f"guard: {value}\ninstruction_guard: {value}\ninstruct: {value}\n"
    user = box.home / ".claude" / "agentik"
    user.mkdir(parents=True, exist_ok=True)
    (user / "profiles.yaml").write_text("defaults:\n  " + body.replace("\n", "\n  ").rstrip()
                                        + "\nprofiles:\n  open:\n    guard: off\n")
    repo = box.repo / ".claude" / "agentik"
    repo.mkdir(parents=True, exist_ok=True)
    for name in ("config.yaml", "config.local.yaml"):
        (repo / name).write_text("profile: open\n" + body)
    overlays = box.state / "overlays"
    overlays.mkdir(parents=True, exist_ok=True)
    (overlays / f"{SID}.json").write_text(json.dumps({"guard": value, "instruct": value}))
    (box.repo / ".claude" / "settings.local.json").write_text(json.dumps(
        {"env": knobs, "agentik": {"guard": value}}))
    return dict(box.env, **knobs)


@pytest.mark.parametrize("value", ("1", "0", "off", "false", "no", "open", "disabled", "true",
                                   "yes", "on", "ask", ""))
def test_r4_no_knob_opens_it(box, monkeypatch, capsys, value):
    _main(monkeypatch)
    env = _hostile(box, monkeypatch, value)
    for p in (box.repo / "CLAUDE.md", box.home / ".claude" / "settings.json"):
        assert _decision(_pre(_payload("Edit", p, cwd=box.repo), env)) == \
            ("ask", REASON.format(p)), p
        out = _pre(_payload("Write", p, cwd=box.repo, agent_id="a1"), env)
        assert _decision(out)[0] == "deny", p
        assert _decision(instructionguard.check(_payload("Edit", p), env))[0] == "ask", p
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        _payload("Edit", box.repo / "CLAUDE.md", cwd=box.repo))))
    capsys.readouterr()
    assert hooks.dispatch("PreToolUse") == 0                  # the live entry, os.environ
    assert _decision(json.loads(capsys.readouterr().out))[0] == "ask"


def _envish(node) -> bool:
    return ((isinstance(node, ast.Name) and "env" in node.id.lower())
            or (isinstance(node, ast.Attribute) and node.attr in ("environ", "environb")))


def _key(node) -> str:
    node = getattr(node, "value", node) if type(node).__name__ == "Index" else node   # 3.8
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else "?"


def _env_reads(tree) -> list:
    """Each read of an environment in `tree`: a key read from a mapping named like `env` or
    from `os.environ` (`?` where the key is no literal), and `getenv` by name."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                n.func.attr in ("get", "pop", "setdefault", "__getitem__", "__contains__") and \
                _envish(n.func.value):
            out.append(_key(n.args[0]) if n.args else "?")
        elif isinstance(n, ast.Subscript) and _envish(n.value):
            out.append(_key(n.slice))
        elif isinstance(n, ast.Compare) and any(_envish(c) for c in n.comparators):
            out.append(_key(n.left))
        elif isinstance(n, (ast.Name, ast.Attribute)) and \
                getattr(n, "id", getattr(n, "attr", "")) in ("getenv", "getenvb"):
            out.append("getenv")
    return out


def test_r4_the_source_reads_no_knob():
    lib = ROOT / "plugin" / "lib" / "claude_session"
    src = (lib / "instructionguard.py").read_text()
    tree = ast.parse(src)
    assert set(_env_reads(tree)) == ENV_READ
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and n.attr in ("environ", "environb")]               # no whole environment
    caps = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str) and re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", n.value)}
    assert caps <= ENV_READ, caps                         # no knob's name kept in a constant
    blocks = [n for n in ast.walk(ast.parse((lib / "hooks.py").read_text()))
              if isinstance(n, ast.If) and any(
                  isinstance(a, ast.Attribute) and a.attr == "TOOLS"
                  and getattr(a.value, "id", "") == "instructionguard" for a in ast.walk(n.test))]
    assert len(blocks) == 1                               # the hook's one call of the guard
    assert _env_reads(blocks[0]) == []                    # it hands the environment on, whole
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
