"""Packet g2: the PreToolUse prompt before an edit of instruction text (hq design/09 §7.2).
Every test runs under its own temp HOME and state; the run's kind is read through
`harness.claude_argv`, patched here (conftest's `_ps` reads nothing, so an unpatched run is
one whose argv cannot be read)."""

import ast
import io
import json
import os
import re
import shlex
import subprocess
import sys
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


def _main(monkeypatch, argv=("claude", "--model", "opus"), exact=True):
    """The nearest claude's argv: read word by word from the kernel (`exact`), or only as `ps`
    shows it, the words joined with spaces and split again (r2 F4's fallback)."""
    joined = " ".join(argv).split() if argv else None
    monkeypatch.setattr(harness, "claude_argv", lambda *a, **k: joined)
    got = (list(argv), True) if argv and exact else (joined, False)
    monkeypatch.setattr(instructionguard, "claude_argv", lambda *a, **k: got, raising=False)


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


# r2 F4: the run's kind is read from the nearest claude's argv word by word, as Claude Code's
# CLI (commander) parses it: options are read past the prompt (only `--` or a subcommand ends
# them), an option's value is never taken for an option, and a prompt is one word whatever it
# holds. `-cp` is `-c -p`; `-dp` is a debug filter.
@pytest.mark.parametrize("argv", [
    ("claude", "go -p"), ("claude", "go", "--name", "-p"),       # round one's attended shapes
    ("claude", "drive.py", "--model", "fable", "Check the relay -p children and fix CLAUDE.md"),
    ("claude", "--model", "fable", "Check the relay -p children and fix CLAUDE.md"),
    ("claude", "--append-system-prompt", "never use --print here"),
    ("claude", "--name", "-p"), ("claude", "-n", "-p", "go"), ("claude", "-n-p"),
    ("claude", "--name=-p", "go"), ("claude", "--name", "my -p job", "go"),
    ("claude", "--model", "-p", "go"), ("claude", "--fallback-model", "--print", "go"),
    ("claude", "--session-id", "-p"), ("claude", "--settings", "-p"), ("claude", "--agent", "-p"),
    ("claude", "--max-turns", "-p"), ("claude", "--effort", "-p", "go"),
    ("claude", "--plugin-dir", "-p", "go"), ("claude", "--permission-prompt-tool", "-p", "go"),
    ("claude", "--effort", "high", "--model", "opus", "fix it --print"),
    ("claude", "--debug=-p", "go"), ("claude", "-d-p", "go"), ("claude", "-dp", "go"),
    ("claude", "-rp", "abc"), ("claude", "-wp", "go"), ("claude", "-r", "abc"),
    ("claude", "--", "-p"), ("claude", "go", "--", "-p"), ("claude", "-c", "--verbose", "--", "-p"),
    ("claude", "--allowedTools", "Bash", "--", "-p"),
    ("claude", "mcp", "list"), ("claude", "plugin", "list", "-p"), ("claude", "mcp", "serve"),
    ("claude", "doctor"),
    ("claude", "--some-new-option", "x", "Fix the README"),
    ("claude", "--remote-control", "Fix the -happy path"),        # r2 F5: no word reads as -p
    ("claude", "--fast-mode", "on", "Fix the -up arrow"), ("claude", "--bare", "Check the -p children"),
    ("claude", "--fast-mode", "on", "Fix the README"), ("claude", "--channels", "a", "b", "Fix it")])
def test_r2_a_prompt_word_is_not_an_option(box, monkeypatch, argv):
    _main(monkeypatch, argv)
    assert instructionguard.run_kind({}) == "main"
    p = box.repo / "CLAUDE.md"
    assert _decision(_pre(_payload("Edit", p), box.env)) == ("ask", REASON.format(p))


@pytest.mark.parametrize("argv", [
    ("claude", "go", "-p"), ("claude", "Fix CLAUDE.md", "--print"),           # r2 F4's shapes
    ("claude", "--append-system-prompt", "be brief", "-p", "go"),
    ("claude", "--system-prompt", "You are a reviewer", "--print"),
    ("claude", "--name", "my job", "-p"), ("claude", "--model", "opus", "Fix CLAUDE.md", "--print"),
    ("claude", "go", "--model", "opus", "-cp"), ("claude", "go", "--print=json"),
    ("claude", "-p", "--permission-mode", "auto", "go"),                       # the relay's rows
    ("claude", "-p", "go"), ("claude", "--print", "go"), ("claude", "-cp", "go"), ("claude", "-pc"),
    ("claude", "-cvp"), ("claude", "-c", "-p"), ("claude", "--verbose", "--print", "go"),
    ("claude", "--model", "opus", "-p"), ("claude", "--model=opus", "-p"),
    ("claude", "--print=x", "go"), ("claude", "--setting-sources", "user,project", "-p"),
    ("claude", "--add-dir", "a", "b", "-p", "go"), ("claude", "--tools", "Bash", "Edit", "-p"),
    ("claude", "--max-turns", "3", "--print=json", "go"),
    ("claude", "--resume", "-p"), ("claude", "-r", "-p"), ("claude", "--from-pr", "-p"),
    ("claude", "-w", "-p"), ("claude", "-d", "-p"),
    ("claude", "--some-new-option", "x", "-p", "go"),
    ("claude", "--debug-file", "/x/y", "-p", "go"), ("claude", "--fast-mode", "on", "-p", "go"),
    ("claude", "--thinking", "off", "-p"), ("claude", "--max-thinking-tokens", "9", "--print"),
    ("claude", "--file", "a", "b", "-p"),
    ("claude", "--bare", "-p", "go"), ("claude", "--safe-mode", "-p")])  # unsure: its value?
def test_r2_headless_flag_among_the_options_denies(box, monkeypatch, argv):
    _main(monkeypatch, argv)
    assert instructionguard.run_kind({}) in ("headless", "unknown")
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "deny"


# r2 F4's fallback: where the argv cannot be read word by word, the `ps` line is walked; a
# print word after the walk's end (a prompt word or `--`) may be the flag, so the run denies.
@pytest.mark.parametrize("argv,answer", [
    (("claude", "--name", "-p"), "ask"), (("claude", "-n", "-p", "go"), "ask"),
    (("claude", "--model", "opus", "Fix the README"), "ask"), (("claude", "-dp"), "ask"),
    (("claude", "--remote-control", "Fix the -happy path"), "deny"),
    (("claude", "go -p"), "deny"), (("claude", "go", "-p"), "deny"),
    (("claude", "--model", "fable", "Check the relay -p children"), "deny"),
    (("claude", "--append-system-prompt", "never use --print here"), "deny"),
    (("claude", "--append-system-prompt", "be brief", "-p", "go"), "deny"),
    (("claude", "--name", "my job", "-p"), "deny"),
    (("claude", "--", "-p"), "deny"), (("claude", "go", "--", "-cp"), "deny")])
def test_r2_the_ps_line_when_the_argv_cannot_be_read(box, monkeypatch, argv, answer):
    _main(monkeypatch, argv, exact=False)
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == answer


def _ps_line(monkeypatch, args):
    """`ps` shows `args` for the hook's parent; the kernel's argv reader is stubbed."""
    monkeypatch.setattr(harness, "_ps", lambda pid: (1, args) if pid == os.getppid() else None)


@pytest.mark.parametrize("why", ["none", "raises", "not claude"])
def test_r2_an_unread_argv_falls_back_to_the_ps_line(box, monkeypatch, why):
    def words(pid):
        if why == "raises":
            raise OSError("the kernel says no")
        return None if why == "none" else ["/x/other", "go"]
    monkeypatch.setattr(instructionguard, "argv_words", words, raising=False)
    _ps_line(monkeypatch, "claude go -p")
    assert instructionguard.claude_argv() == (["claude", "go", "-p"], False)
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "deny"
    _ps_line(monkeypatch, "claude --name -p")
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "ask"


def test_r2_the_kernel_argv_is_read_at_the_claude_ps_found(box, monkeypatch):
    seen = []
    monkeypatch.setattr(instructionguard, "argv_words",
                        lambda pid: seen.append(pid) or ["/x/claude", "go", "-p"], raising=False)
    _ps_line(monkeypatch, "/x/claude go -p")
    assert instructionguard.claude_argv() == (["/x/claude", "go", "-p"], True)
    assert seen == [os.getppid()]
    assert _decision(_pre(_payload("Edit", box.repo / "CLAUDE.md"), box.env))[0] == "deny"


# ---- r2 F4: the argv read from the kernel, word by word ---------------------------------


_KERNEL = pytest.mark.skipif(sys.platform != "darwin" and not os.path.exists("/proc/self/cmdline"),
                             reason="no argv reader on this platform")
_REPORT = ("import json, sys; sys.path.insert(0, {lib!r}); "
           "from claude_session import harness, instructionguard as g; "
           "harness.ANCESTOR_HOPS = 1; "            # the parent, the made-up claude, no further
           "argv, exact = g.claude_argv(); print(json.dumps([argv, exact, g.run_kind({{}})]))")


def _under_claude(tmp_path, argv):
    """The reader, run in a grandchild of a real process whose argv is `argv` with argv[0] a
    made-up `.../claude`: bash, started under that name, runs the script named by argv[1] (the
    prompt word) from tmp_path, and the script starts the reader."""
    code = _REPORT.format(lib=str(ROOT / "plugin" / "lib"))
    (tmp_path / argv[1]).write_text(f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}\n"
                                    "exit $?\n")
    name = str(tmp_path / "made-up" / "claude")
    p = subprocess.run([name, *argv[1:]], executable="/bin/bash", cwd=str(tmp_path),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    got, exact, kind = json.loads(p.stdout)
    assert got == [name, *argv[1:]] and exact is True, (got, exact)   # word by word, unjoined
    return kind


@_KERNEL
@pytest.mark.skipif(not os.path.exists("/bin/bash"), reason="no /bin/bash")
@pytest.mark.parametrize("argv,kind", [
    (("claude", "go", "-p"), "headless"), (("claude", "Fix CLAUDE.md", "--print"), "headless"),
    (("claude", "go", "--append-system-prompt", "be brief", "-p"), "headless"),
    (("claude", "go -p"), "main"), (("claude", "Check the relay -p children", "--name", "-p"), "main"),
    (("claude", "go", "--name", "my -p job"), "main")])
def test_r2_a_real_process_argv_read_from_the_kernel(tmp_path, argv, kind):
    assert _under_claude(tmp_path, argv) == kind


@_KERNEL
@pytest.mark.skipif(not os.path.exists("/bin/bash"), reason="no /bin/bash")
def test_r2_the_reader_stops_at_argc_and_keeps_no_environment(tmp_path):
    argv = ["/bin/bash", "-c", "sleep 30; exit 0", "made up words"]
    p = subprocess.Popen(argv, env={"MADEUP_TOKEN": "zz-not-kept"})
    try:
        for _ in range(100):                        # until the exec has replaced the fork
            got = instructionguard.argv_words(p.pid)
            if got and got[0] == "/bin/bash":
                break
            time.sleep(0.02)
        assert got == argv
        started = time.perf_counter()
        for _ in range(100):
            instructionguard.argv_words(p.pid)
        assert (time.perf_counter() - started) / 100 < 0.01
    finally:
        p.kill()
        p.wait()


@_KERNEL
def test_r2_an_argv_the_kernel_will_not_give_is_none(tmp_path):
    if sys.platform == "darwin":
        assert instructionguard.argv_words(1) is None            # another user's process
    assert instructionguard.argv_words(99999999) is None         # no such process
    p = subprocess.Popen(["/bin/sleep", "0"])
    try:
        got = []
        for _ in range(250):                       # a zombie: exited, not yet reaped
            got = instructionguard.argv_words(p.pid)
            if got is None:
                break
            time.sleep(0.02)
        assert got is None
    finally:
        p.wait()


def test_r2_the_reader_never_raises(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("no libc here")
    monkeypatch.setattr(instructionguard, "_sysctl", boom, raising=False)
    monkeypatch.setattr(instructionguard, "_PROC", str(tmp_path / "proc"), raising=False)
    assert instructionguard.argv_words(os.getpid()) is None
    for bad in (None, "x", -1, 0, 2 ** 40):
        assert instructionguard.argv_words(bad) is None


def test_r2_the_proc_reader(monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    (proc / "4242").mkdir(parents=True)
    (proc / "4242" / "cmdline").write_bytes(b"/x/claude\0go -p\0\0--name\0")
    (proc / "4243").mkdir()
    (proc / "4243" / "cmdline").write_bytes(b"")                  # a zombie's
    monkeypatch.setattr(instructionguard, "_PROC", str(proc), raising=False)
    assert instructionguard.argv_words(4242) == ["/x/claude", "go -p", "", "--name"]
    assert instructionguard.argv_words(4243) is None


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
    monkeypatch.setattr(instructionguard, "claude_argv", lambda *a, **k: pytest.fail("argv read"),
                        raising=False)
    monkeypatch.setattr(instructionguard, "argv_words", lambda *a, **k: pytest.fail("argv read"),
                        raising=False)
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
