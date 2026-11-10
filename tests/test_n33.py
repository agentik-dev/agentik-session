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


VERB_FIRST = "a helper's one charter call is `agentik-session charter check <file>`, the verb first"


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
        assert "by hand" in why and "script file" in why and VERB_FIRST in why
    assert not (_sdir(A) / hooks.CALLS / "toolu_n33").exists()


@pytest.mark.parametrize("name", NAMES)
def test_n33_t13_main_thread_and_other_verbs_pass(repo, name):
    """T13, R6: the same commands from the main thread pass; a helper's `charter check`, a
    status and a non-Bash tool pass (the fold: `charter --help`, a flag first, is T17's deny)."""
    for run_ in RUNS:
        assert not _denied(hooks.pre_tool_use(_bash(run_.format(n=name), helper=False)))
    for cmd in (f"{name} charter check h.md", f"{name} status", f"{name} -x charter check h.md"):
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


# The review fold (round 1, F1 to F3, F7): the rule reads no flags. A launcher name, then the word
# `charter` on the same logical line, is denied to a helper unless the word right after it is a
# verb that only reads; quotes and backslash-newlines are dropped before the match.
EVASIONS = (
    # p3 and p11: a flag value with a command substitution, a continuation before `charter`
    'agentik-session charter --dir "$(pwd)/history/sittings" close --exit "helper done"',
    "agentik-session charter --dir $(git rev-parse --show-toplevel)/history/sittings close",
    'agentik-session \\\n  charter close --exit "helper done"',
    'agentik-session charter --dir "$(pwd)/history/sittings" open "helper goal"',
    # p1's spellings (F3): quoted names and verbs, continuations, substitutions
    '"agentik-session" charter open g', "agentik-session charter \"open\" g",
    "'agentik-session' 'charter' 'close'", 'agentik-session charter --dir "a b" open g',
    "agentik-session charter \\\n open g", "agentik \\\n session charter open g",
    "$(which agentik-session) charter open g", '"$(command -v agentik-session)" charter open g',
    "T=agentik-session; $T charter open g", "agentik-session charter o''pen g",
    'agentik-session charter "cl"ose', "agentik-session charter o\\pen g",
    'agentik-session ch"art"er open g', "agentik-session ch\\arter close",
)


@pytest.mark.parametrize("cmd", EVASIONS)
def test_n33_t16_the_refuters_spellings_denied(repo, cmd):
    """T16: each spelling the round found past the hook is denied to a helper, the reason
    naming the one charter call; the main thread's same command passes."""
    out = hooks.pre_tool_use(_bash(cmd))
    assert _denied(out), cmd
    assert VERB_FIRST in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert not _denied(hooks.pre_tool_use(_bash(cmd, helper=False))), cmd


@pytest.mark.parametrize("name", NAMES)
def test_n33_t17_a_flag_before_the_verb_is_denied(repo, name):
    """T17: `charter <any flag> ...` is denied to a helper, `check` included (the deny names
    the verb-first call); a flag between the launcher and `charter` changes nothing."""
    for cmd in (f"{name} charter --dir d check f", f"{name} charter --help", f"{name} charter -h",
                f"{name} charter", f"{name} charter; ls", f"{name} charter --exit=x close",
                f"{name} --v charter open g", f"{name} -x charter close"):
        out = hooks.pre_tool_use(_bash(cmd))
        assert _denied(out), cmd
        assert VERB_FIRST in out["hookSpecificOutput"]["permissionDecisionReason"], cmd
    for cmd in (f"{name} charter check open.md", f"{name} charter check a.md b.md",
                f"{name} -x charter check f"):
        assert not _denied(hooks.pre_tool_use(_bash(cmd))), cmd


def test_n33_t18_the_rules_edges(repo):
    """T18, F7's mutants: the launcher's guards (a longer name is not the launcher), the read
    verb's guard (`check.md` is not `check`), the same logical line, every `charter` after
    the launcher read."""
    passes = ("myagentik-session charter open g", "xclaude-session charter close",
              "claude-sessions charter open g", "agentik-session-old charter open g",
              'agentik-session status\ngrep -n "charter open" SKILL.md',
              "agentik-session charter check a.md\necho charter open",
              'agentik-session charter "check" f', "agentik-session charter \\check f",
              "agentik-session status; cat notes-charter", "agentik-session status; cat charters",
              "agentik-session status; cat charter.md charter-open.md",
              "echo charter open; agentik-session status")
    for cmd in passes:
        assert not _denied(hooks.pre_tool_use(_bash(cmd))), cmd
    denied = ("agentik-session charter check.md", "agentik-session charter checkout x",
              "agentik-session charter check-x f", "agentik-session charter openers",
              "agentik-session charter close.md",
              "agentik-session charter check a.md && agentik-session charter close",
              "agentik-session charter check a.md; charter open g",
              "agentik-session charter\ncheck f", "agentik-session charter\rcheck f")
    for cmd in denied:
        assert _denied(hooks.pre_tool_use(_bash(cmd))), cmd


def test_n33_t19_a_quoted_exit_mark_mid_line_still_holds(repo):
    """T19, F7 M7: a line that quotes `- exit taken:` mid-line does not close the charter, so a
    second open still refuses."""
    a = _open("A goal")
    a.write_text(a.read_text() + "- the mark is `- exit taken: x`, written by close\n")
    rc, out, err = run("charter", "open", "helper goal")
    assert rc == 2 and str(a) in err, (rc, out, err)


def test_n33_t20_an_open_that_cannot_record_neither_refuses_nor_records(repo, tmp_path):
    """T20, F7 M10: an open whose directory is no longer the session's recorded cwd's (its
    request.json moved) writes no record, so it takes none and does not refuse: a new file,
    the record unchanged."""
    a = _open("A goal")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    resolver.save_request(_sdir(A), elsewhere, None, None)
    b = _open("helper goal")
    assert b != a and _rec(A) == {"path": str(a)}


_TIMED = r"""
import json, sys, time
from claude_session import hooks
p = json.loads(sys.stdin.read())
t = time.monotonic(); out = hooks.pre_tool_use(p)
h = (out or {}).get("hookSpecificOutput") or {}
print(json.dumps([h.get("permissionDecision") == "deny", time.monotonic() - t]))
"""
SCALE = (  # p4's chains (95 KB, 950 KB), p5's (a real open after a chain; an rg-style heredoc)
    ("agentik-session -x agentik-session -x " * 2500, False),
    ("agentik-session -x agentik-session -x " * 25000, False),
    ("agentik-session -x " * 2000 + "; agentik-session charter open g", True),
    ("cat <<'X'\n" + "rg -e claude-session -e claude-session -e " * 2000 + "\nX", False),
    ("agentik-session -x " * 50000 + "; agentik-session charter open g", True),
    ("agentik-session charter check a " * 30000, False),
    ("agentik-session charter" + " " * 500000 + "open", True),
    ("agentik" + " " * 500000 + "x charter open", False),
)


@pytest.mark.parametrize("cmd,deny", SCALE, ids=[f"s{i}" for i in range(len(SCALE))])
def test_n33_t21_the_rule_is_linear(repo, cmd, deny):
    """T21, F2: the rule takes well under the hook's 5 s on each payload up to 950 KB (a
    generous 2 s bound on the call alone), with the right decision."""
    r = subprocess.run([sys.executable, "-c", _TIMED], input=json.dumps(_bash(cmd)),
                       capture_output=True, text=True, timeout=20, env=dict(os.environ))
    assert r.returncode == 0, r.stderr
    hit, took = json.loads(r.stdout)
    assert hit is deny and took < 2.0, (hit, took)
