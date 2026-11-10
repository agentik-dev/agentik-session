"""Packet n33 (design/packets/n33-helper-door.md): a helper's `charter open` never takes its
parent's record, and a parent's bare close never writes a file its own open did not name.

A helper's Bash carries its parent's CLAUDE_CODE_SESSION_ID and no mark, so the tool cannot
tell the two apart in the process: R6's PreToolUse hook denies a helper's (agent_id) Bash
that runs this tool's charter open or close; with hooks off, R1 refuses to move a record that names a still-open charter in the same
directory unless `--replace`; R2 records what a replace moved off, and a bare close refuses
while that file stands open. T1 to T8 and T11 to T15 were red at a76ae35 (hq probe c11: `A 0  B 1`)."""
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, cli, hooks, resolver

A = "aaaaaaaa-0000-0000-0000-000000000033"
B = "bbbbbbbb-0000-0000-0000-000000000033"
ASK = "name the file: charter close <file>"
CLEAN = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE",
         "CLAUDE_SESSION_HELPER", "RELAY_ROW")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _sdir(sid):
    return resolver.session_dir(resolver.state_dir(os.environ), sid)


def _rec(sid):
    p = _sdir(sid) / hooks.CHARTER_REC
    return json.loads(p.read_text()) if p.exists() else None


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo whose sitting A started in it (SessionStart's request.json); cwd there, as A."""
    for k in CLEAN:
        monkeypatch.delenv(k, raising=False)
    r = tmp_path / "repo"
    r.mkdir()
    s = _sdir(A)
    s.mkdir(parents=True)
    resolver.save_request(s, r, None, None)
    monkeypatch.chdir(r)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    return r


def _open(*argv):
    rc, out, err = run("charter", "open", *argv)
    assert rc == 0, err
    return Path.cwd() / out.strip()


def _exits(p):
    return p.read_text().count("- exit taken:") if p.exists() else None


def test_n33_t1_c11_end_to_end(tmp_path, monkeypatch):
    """T1, hq probe c11 through the module's own entry: SessionStart, the sitting's open, its
    helper's open (same id, no mark), the sitting's bare close. The helper's open exits 2 and
    writes nothing; the close writes the sitting's file."""
    for k in CLEAN:
        monkeypatch.delenv(k, raising=False)
    r = tmp_path / "c11"
    r.mkdir()
    g = ["git", "-C", str(r), "-c", "user.name=p", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(g + ["commit", "-q", "--allow-empty", "-m", "init"], check=True)
    env = {**os.environ, "CLAUDE_CODE_SESSION_ID": A}

    def tool(*a, stdin=None):
        return subprocess.run([sys.executable, "-m", "claude_session", *a], cwd=r, env=env,
                              input=stdin, capture_output=True, text=True, timeout=60)
    tool("hook", "SessionStart", stdin=json.dumps(
        {"session_id": A, "cwd": str(r), "model": "claude-fable-5-2"}))
    assert (_sdir(A) / "request.json").is_file()
    o = tool("charter", "open", "the sitting's goal")
    assert o.returncode == 0, o.stderr
    a = r / o.stdout.strip()
    h = tool("charter", "open", "its helper's goal")
    assert h.returncode == 2 and h.stdout == "", (h.returncode, h.stdout, h.stderr)
    assert a.name in h.stderr and "--replace" in h.stderr, h.stderr
    assert sorted(p.name for p in a.parent.iterdir()) == [a.name]
    assert _rec(A) == {"path": str(a)}
    c = tool("charter", "close", "--exit", "the sitting is done")
    assert c.returncode == 0 and _exits(a) == 1, c.stderr


def test_n33_t2_refusal_writes_nothing(repo):
    """T2, R1: the refusal names the open file and both ways out, exit 2, before any write:
    no new file, the record's bytes and the open charter's bytes unchanged."""
    a = _open("A goal")
    rec = (_sdir(A) / hooks.CHARTER_REC).read_bytes()
    snap = a.read_bytes()
    rc, out, err = run("charter", "open", "helper goal")
    assert (rc, out) == (2, ""), (rc, out, err)
    assert str(a) in err and "--replace" in err and "charter close" in err, err
    assert sorted(p.name for p in a.parent.iterdir()) == [a.name]
    assert (_sdir(A) / hooks.CHARTER_REC).read_bytes() == rec and a.read_bytes() == snap


def test_n33_t3_continue_moving_the_record_refuses(repo):
    """T3, R1: `open --continue` that would write a new file (the newest at the mark) moves
    the record and refuses as open does; one that adopts the recorded file moves nothing."""
    a = _open("A goal")
    assert _open("--continue", "A again") == a and _rec(A) == {"path": str(a)}
    a.write_text(a.read_text() + "x" * (charter.CONTINUE_BELOW - len(a.read_text())))
    rc, out, err = run("charter", "open", "--continue", "A goal")
    assert rc == 2 and str(a) in err, err
    assert sorted(p.name for p in a.parent.iterdir()) == [a.name]


def test_n33_t4_replace_moves_and_says_what_it_moved_off(repo):
    """T4, R2: `--replace` writes the new file and the record {path, replaced}."""
    a = _open("A goal")
    b = _open("--replace", "a replacing goal")
    assert b != a and _rec(A) == {"path": str(b), "replaced": str(a)}


def test_n33_t5_parent_close_after_a_replace_refuses(repo):
    """T5, R3, the second door: after a replace while A stood open (a helper that took the
    way out), the bare close refuses, exit 2, naming both files, and writes neither; the named
    close writes A."""
    a = _open("A goal")
    b = _open("--replace", "helper goal")
    snap = {p: p.read_bytes() for p in (a, b)}
    rc, out, err = run("charter", "close", "--exit", "A is done")
    assert (rc, out) == (2, ""), (rc, out, err)
    assert "opened with --replace while" in err, err
    assert a.name in err and b.name in err and err.rstrip().endswith(ASK), err
    assert {p: p.read_bytes() for p in (a, b)} == snap
    assert run("charter", "close", "--exit", "A is done", str(a))[0] == 0
    assert (_exits(a), _exits(b)) == (1, 0)


def test_n33_t6_replaced_closed_or_gone_lets_the_record_win(repo):
    """T6, R3: once the replaced file has its exit line, or is gone, the bare close writes
    the record's file."""
    a = _open("A goal")
    b = _open("--replace", "B goal")
    assert run("charter", "close", "--exit", "A done", str(a))[0] == 0
    assert run("charter", "close", "--exit", "B done")[0] == 0 and _exits(b) == 1
    c = _open("C goal")                          # b closed: no refusal, no flag
    d = _open("--replace", "D goal")
    c.unlink()
    assert run("charter", "close", "--exit", "D done")[0] == 0 and _exits(d) == 1


def test_n33_t7_replace_over_nothing_open_is_a_plain_record(repo):
    """T7, R2: `--replace` with no open charter recorded writes the plain {path}."""
    b = _open("--replace", "first goal")
    assert _rec(A) == {"path": str(b)}


def test_n33_t8_replace_is_read_only_with_open(repo):
    """T8, R2: `--replace` on check or close exits 2 with one line, as `--continue` does."""
    a = _open("A goal")
    for action, args in (("close", ["--exit", "x"]), ("check", [str(a)])):
        rc, out, err = run("charter", action, "--replace", *args)
        assert rc == 2 and f"--replace is read only with open, not {action}" in err, err
    assert _exits(a) == 0


def test_n33_t9_close_then_open_keeps_working(repo, monkeypatch):
    """T9, the legitimate flows: close then open with no flag (a second goal), a helper's
    open in its own worktree, a marked helper's open, a successor's `--continue` under its own
    id; each exits 0 and none moves the sitting's record off an open charter."""
    a = _open("A goal")
    assert run("charter", "close", "--exit", "A done")[0] == 0
    b = _open("B goal")
    assert _rec(A) == {"path": str(b)}
    wt = repo / ".claude" / "worktrees" / "row"
    wt.mkdir(parents=True)
    monkeypatch.chdir(wt)
    w = _open("the builder's goal")
    assert w.parent == wt / "history" / "sittings" and _rec(A) == {"path": str(b)}
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    _open("a marked helper's goal")
    monkeypatch.delenv("CLAUDE_SESSION_HELPER")
    assert _rec(A) == {"path": str(b)}
    assert run("charter", "close", "--exit", "B done")[0] == 0 and _exits(b) == 1
    s = _sdir(B)
    s.mkdir(parents=True)
    resolver.save_request(s, repo, None, None)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", B)
    n = _open("--continue", "the successor's goal")
    assert _rec(B) == {"path": str(n)}


def test_n33_t10_outside_or_gone_record_does_not_hold(repo, tmp_path):
    """T10, R1's scope: a record naming a gone file, or a file under another directory, holds
    nothing; the open writes and records as before."""
    a = _open("A goal")
    a.unlink()
    b = _open("B goal")
    assert _rec(A) == {"path": str(b)}
    other = tmp_path / "x" / "history" / "sittings" / f"{charter.today()}-1.md"
    other.parent.mkdir(parents=True)
    other.write_text("open, elsewhere")
    (_sdir(A) / hooks.CHARTER_REC).write_text(json.dumps({"path": str(other)}))
    c = _open("C goal")
    assert _rec(A) == {"path": str(c)}


def test_n33_t11_docs_name_the_flag(tmp_path):
    """T11, R5: the skill's charter block names `--replace`; RUNBOOK, it and the hook's deny."""
    root = Path(__file__).resolve().parents[1]
    skill = (root / "plugin" / "skills" / "session" / "SKILL.md").read_text()
    assert "charter open --replace" in skill
    runbook = (root / "RUNBOOK.md").read_text()
    assert "--replace" in runbook and "PreToolUse hook denies a helper's" in runbook


# R6, the root door: the PreToolUse hook denies a helper's (agent_id) Bash that runs this tool's
# charter open or close; the fallback above holds when hooks are off.
NAMES = ("agentik-session", "agentik session", "claude-session",
         "/x/plugin/bin/agentik-session", "python3 -m claude_session")
RUNS = ['{n} charter open "g"', "{n} charter close --exit done",
        "cd /r && {n} charter --dir d open g", "{n} charter close h.md; ls"]


def _bash(cmd, helper=True):
    p = {"session_id": A, "tool_name": "Bash", "tool_use_id": "toolu_n33",
         "tool_input": {"command": cmd}, "hook_event_name": "PreToolUse"}
    return {**p, "agent_id": "a1b2", "agent_type": "general-purpose"} if helper else p


def _denied(out):
    h = (out or {}).get("hookSpecificOutput") or {}
    return h.get("permissionDecision") == "deny"


@pytest.mark.parametrize("name", NAMES)
def test_n33_t12_helper_open_and_close_denied(repo, name):
    """T12, R6: open and close under each launcher name, flags before the action, in a chain:
    denied, the reason naming the way out, and no call left open."""
    for run_ in RUNS:
        out = hooks.pre_tool_use(_bash(run_.format(n=name)))
        assert _denied(out), run_.format(n=name)
        why = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert "by hand" in why and "charter check <file>" in why and "script file" in why
    assert not (_sdir(A) / hooks.CALLS / "toolu_n33").exists()


@pytest.mark.parametrize("name", NAMES)
def test_n33_t13_main_thread_and_other_verbs_pass(repo, name):
    """T13, R6: the same commands from the main thread pass; a helper's `charter check`, a
    status and a non-Bash tool pass."""
    for run_ in RUNS:
        assert not _denied(hooks.pre_tool_use(_bash(run_.format(n=name), helper=False)))
    for cmd in (f"{name} charter check h.md", f"{name} status", f"{name} charter --help"):
        assert not _denied(hooks.pre_tool_use(_bash(cmd))), cmd
    p = {**_bash(f"{name} charter open g"), "tool_name": "Read"}
    assert not _denied(hooks.pre_tool_use(p))


def test_n33_t14_mentions(repo):
    """T14, R6's pinned edge: the words with no launcher name pass; with one, a plain pattern
    cannot tell a quoted mention from the call, so it is denied (the helper rewords)."""
    for cmd in ('grep -n "charter open" SKILL.md', "echo charter close", "cat charter-open.md",
                "agentik-session charter check open.md"):
        assert not _denied(hooks.pre_tool_use(_bash(cmd))), cmd
    assert _denied(hooks.pre_tool_use(_bash('grep -n "agentik-session charter open" x.md')))


def test_n33_t15_hook_entry_denies(repo):
    """T15, R6 through `python -m claude_session hook PreToolUse`: the deny on stdout."""
    r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "PreToolUse"],
                       input=json.dumps(_bash('agentik-session charter open "g"')),
                       capture_output=True, text=True, timeout=60, env=dict(os.environ))
    assert r.returncode == 0 and _denied(json.loads(r.stdout)), (r.returncode, r.stdout, r.stderr)
    r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "PreToolUse"],
                       input=json.dumps(_bash('agentik-session charter open "g"', helper=False)),
                       capture_output=True, text=True, timeout=60, env=dict(os.environ))
    assert r.returncode == 0 and "deny" not in r.stdout, r.stdout
