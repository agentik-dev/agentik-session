"""g8-refusals: the four stray-write refusals in the hook (brief R1 to R19), each with its mark.

Every case is a payload through `hooks.pre_tool_use` under a temp home H. The box: `H/tree/CLAUDE.md`
arms the sweep by its title; A is `H/tree/armed` (a checkout, with `sub`); W a worktree of A with
a `.git` file; O `H/open` (a checkout no title arms); L `H/lone` (armed by its own file); F
`H/fenced` (the entry in a fence and indented: not armed); P `H/plain` (no checkout); `H/link` a
symlink to A. T and U are variables no test sets.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "lib"))

from claude_session import lineguard  # noqa: E402  (at the pin: an import error, every test red)
from claude_session import hooks, instructionguard, resolver, shellreader  # noqa: E402

SID, TUID = "s1", "toolu_1"
HEAD = "agentik-session: refused by"


@pytest.fixture
def box(tmp_path, monkeypatch):
    class B:
        pass
    b = B()
    h = Path(os.path.realpath(tmp_path)) / "h"
    b.h = h
    (h / ".claude").mkdir(parents=True)
    b.env = {"HOME": str(h), "XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"}
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    b.state = resolver.state_dir(b.env)
    (h / "tree").mkdir()
    (h / "tree" / "CLAUDE.md").write_text("# The tree\n\n36. **Commits.** Commit by explicit path.\n")
    b.a = h / "tree" / "armed"
    (b.a / ".git").mkdir(parents=True)
    (b.a / "sub").mkdir()
    (b.a / ".claude").mkdir()
    (b.a / ".claude" / "edit-gates").write_text("CLAUDE.md\n")
    b.w = b.a / ".claude" / "worktrees" / "w"
    b.w.mkdir(parents=True)
    (b.w / ".git").write_text("gitdir: " + str(b.a / ".git" / "worktrees" / "w") + "\n")
    b.o = h / "open"
    (b.o / ".git").mkdir(parents=True)
    b.l = h / "lone"
    (b.l / ".git").mkdir(parents=True)
    (b.l / "CLAUDE.md").write_text("# Lone\n\n- 36 Commits (2026-11-12)\n")
    b.f = h / "fenced"
    (b.f / ".git").mkdir(parents=True)
    (b.f / "CLAUDE.md").write_text("# Fenced\n\n```\n36. **Commits.** In a fence.\n```\n\n"
                                   "  36. **Commits.** Indented.\n  - 36 Commits (2026-11-12)\n")
    b.p = h / "plain"
    b.p.mkdir()
    (h / "link").symlink_to(b.a)
    return b


def _line(b, text):
    return text.replace("H/", f"{b.h}/").replace("<A>", str(b.a))


def _payload(b, command, cwd, **more):
    p = {"session_id": SID, "transcript_path": "/t.jsonl", "hook_event_name": "PreToolUse",
         "tool_name": "Bash", "tool_input": {"command": _line(b, command)},
         "tool_use_id": TUID, **more}
    if cwd is not None:
        p["cwd"] = str(cwd)
    return p


def _refused_dir(b, sid=SID):
    return resolver.session_dir(b.state, sid) / "refused"


def _run(b, command, cwd, **more):
    shutil.rmtree(_refused_dir(b), ignore_errors=True)
    out = hooks.pre_tool_use(_payload(b, command, cwd, **more), b.env)
    assert '"ask"' not in json.dumps(out)
    return out


def _decision(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecision"), h.get("permissionDecisionReason") or ""


def _refused(b, command, cwd, **more):
    d, reason = _decision(_run(b, command, cwd, **more))
    assert d == "deny", (command, cwd)
    assert reason.startswith(HEAD), (command, reason)
    return reason


def _passed(b, command, cwd, **more):
    out = _run(b, command, cwd, **more)
    assert _decision(out)[0] is None, (command, cwd, out)
    assert not _refused_dir(b).exists(), command


def _log(b):
    p = resolver.session_dir(b.state, SID) / instructionguard.LOG
    if not p.exists():
        return []
    return [json.loads(t) for t in p.read_text().splitlines()]


# ---- the tables -----------------------------------------------------------------------------

SWEEP_IN_A = [
    "git add -A", "git add --all", "git add -u", "git add --update", "git add .", "git add ./",
    "git add :/", "git add *", "git stage -A", "git stage .", "git add -Av", "git add -A -- src",
    "git add --dry-run -A", "git commit -a -m x", "git commit -am x", "git commit --all -m x",
    "git commit -m x -a", "/usr/bin/git add -A", "X=1 git add -A", "env git add -A",
    "git -c a.b=c add -A", "git --no-pager add -A", "(git add -A)", "{ git add -A; }",
    "if true; then git add -A; fi", "bash -c 'git add -A'", "bash -lc 'git add -A'",
    'echo "$(git add -A)"', "git -C . add -A", "git -C sub add -A", "cd sub && git add -A",
    'git -C "$T" add -A', 'cd "$T" && git add -A', "cd /g8-no-such-folder; git add -A",
    "if t; then cd H/open; fi; git add -A", 'T=H/open; T=H/plain; git -C "$T" add -A',
    # what a reviewer will try
    "git -C . -C sub add -A", "git -C H/open -C <A> add -A", "(T=H/open); git -C \"$T\" add -A",
    "if t; then T=H/open; fi; git -C \"$T\" add -A", "true | T=H/open; git -C \"$T\" add -A",
]
SWEEP_IN_O_P = [
    "git -C H/tree/armed add -A", "cd H/tree/armed && git add -A",
    'T=H/tree/armed; git -C "$T" add -A', "git -C H/link add -A",
    "git --git-dir=H/tree/armed/.git --work-tree=H/tree/armed add -A",
    "GIT_WORK_TREE=H/tree/armed git add -A", "git --git-dir=H/tree/armed/.git add -A",
]
SWEEP_PASS_A = [
    "git add src/a.py", "git add src/*", "git add -p", "git commit -m x",
    'git commit -m "fix -a flag"', "git commit -ma", 'git commit -m "git add -A"',
    "git commit -m \"$(cat <<'EOF'\ngit add -A and -a\nEOF\n)\"", "echo 'git add -A'",
    "cat > notes.md <<'EOF'\ngit add -A\nEOF", 'grep -rn "git add -A" .', "git log --all",
    "git diff -u", "git status -u", "git stash -u", "git -C H/open add -A",
    "git -C /g8-no-such-folder add -A", "cd H/open && git add -A", "(cd H/open && git add -A)",
    'T=H/open; git -C "$T" add -A',
]
SWEEP_PASS_LOGGED = ['git -C "${T:?}" add -A', 'T=$(mktemp -d); git -C "$T" add -A',
                     'git -C "$T/repo" add -A']
SWEEP_PASS_OPF = ["git add -A", "git commit -am x", 'git -C "$T" add -A']

RM_REFUSED = [
    "rm -rf $T", 'rm -rf "$T"/x', 'rm -r -- "$T"', "rm -fR ${T}", "rm --recursive $T",
    "/bin/rm -rf $T", "sudo rm -rf $T", 'for d in a b; do rm -rf "$d"; done',
    'if true; then rm -rf "$T"; fi', "bash -c 'rm -rf $T'", 'rm -rf "$(mktemp -d)"/x',
    'rm -rf "${T:?}" $U', "command rm -rf $T", "T=/tmp/x; rm -rf $T",
]
RM_PASSED = [
    'rm -rf "${T:?}"', 'rm -rf "${T:?}/x" "${U:?no U}"', "rm -rf /tmp/g8/x", "rm -f $T", "rm $T",
    "ls -R $T", "cp -r $T /tmp/g8/x", "echo 'rm -rf $T'", "git commit -m 'rm -rf $T'",
    "grep -rn 'rm -rf' .", "cat > run.sh <<'EOF'\nrm -rf $T\nEOF", "cat > run.sh <<EOF\nrm -rf $T\nEOF",
    "find . -name x -exec rm -rf {} +", "ls rm", "touch init",
]
INIT_REFUSED_A = ["git init", "git init -q", "git init sub", "git init-db", "cd /tmp/g8 && git init",
                  "(cd H/plain && git init)", "bash -c 'git init'", "git init /tmp/g8/new"]
INIT_PASSED_A = ["git -C /tmp/g8 init", "git --git-dir=/tmp/g8/.git init",
                 "GIT_DIR=/tmp/g8/.git git init", "git submodule init", "git log --grep init",
                 'git commit -m "git init"', "echo git init"]
ID_REFUSED_A = ["git config user.name x", "git config user.email a@b.invalid",
                "git config --local user.name x", "git config set user.name x",
                "git config --add user.name x", "git config USER.NAME x"]
ID_PASSED_A = ["git config user.name", "git config --get user.email",
               "git config --global user.name x", "git config --unset user.name", "git config -l",
               "git config --file /tmp/g8/c user.name x", "git -C /tmp/g8 config user.name x",
               "git -c user.name=x -c user.email=a@b.invalid commit -m y",
               "git config core.editor vi", 'git config alias.who "config user.name"',
               "git config --get-regexp user", "git config get user.name"]
LOOSE_P = ["eval 'rm -rf $T'", "bash -c \"bash -c 'rm -rf \\$T'\"", "echo 'rm -rf $T' | sh",
           "echo \"it's\" 'rm -rf $T"]
LOOSE_A = ["eval 'git add -A'", "echo 'git init' | sh", "bash <<< 'git commit -am x'"]
LOOSE_PASS_P = ['eval "$CMD"', "cat run.sh | bash", "echo \"it's\" 'rm x", "eval 'echo rm'",
                "eval 'git add -A'"]


# ---- 1, 2: the sweep ------------------------------------------------------------------------

def test_1_the_sweep_refused_by_the_strict_reading(box):
    for line in SWEEP_IN_A:
        assert "the strict reading" in _last_why(box, line, box.a), line
    for cwd in (box.o, box.p):
        for line in SWEEP_IN_O_P:
            _refused(box, line, cwd)
    for cwd in (box.w, box.l):
        _refused(box, "git add -A", cwd)


def _last_why(b, line, cwd):
    _refused(b, line, cwd)
    rows = [r for r in _log(b) if r.get("decision") == "deny"]
    assert rows and rows[-1]["rule"] == ["sweep"], line
    return rows[-1]["why"]


def test_2_the_sweep_passed(box):
    for line in SWEEP_PASS_A:
        _passed(box, line, box.a)
    for line in SWEEP_PASS_LOGGED:
        before = [r for r in _log(box) if r.get("decision") == "pass"]
        _passed(box, line, box.a)
        after = [r for r in _log(box) if r.get("decision") == "pass"]
        assert len(after) == len(before) + 1, line
    for cwd in (box.o, box.p, box.f):
        for line in SWEEP_PASS_OPF:
            _passed(box, line, cwd)


# ---- 3, 4: rm -------------------------------------------------------------------------------

def test_3_rm_refused_by_the_strict_reading(box):
    for line in RM_REFUSED:
        reason = _refused(box, line, box.p)
        assert 'rm -rf "${T:?}"' in reason, line


def test_4_rm_passed(box):
    for cwd in (box.p, box.a):
        for line in RM_PASSED:
            _passed(box, line, cwd)


# ---- 5, 6: git init and the identity ----------------------------------------------------------

def test_5_git_init(box):
    for line in INIT_REFUSED_A:
        reason = _refused(box, line, box.a)
        assert str(box.a) in reason and "git -C <folder> init" in reason, line
    for line in INIT_PASSED_A:
        _passed(box, line, box.a)
    _passed(box, "git init", box.p)


def test_6_the_identity(box):
    for line in ID_REFUSED_A:
        reason = _refused(box, line, box.a)
        assert "git -c user.name=<name> -c user.email=<address> commit" in reason, line
    for line in ID_PASSED_A:
        _passed(box, line, box.a)
    _passed(box, "git config user.name x", box.p)


# ---- 7: unread text ---------------------------------------------------------------------------

def test_7_unread_text(box):
    for line in LOOSE_P:
        assert "write it more simply" in _refused(box, line, box.p), line
    for line in LOOSE_A:
        assert "write it more simply" in _refused(box, line, box.a), line
    for line in LOOSE_PASS_P:
        _passed(box, line, box.p)
    _passed(box, "eval 'git add -A'", box.o)
    assert [r["why"] for r in _log(box) if r.get("decision") == "deny"][-1] == "the loose reading"


# ---- 8: the reason ----------------------------------------------------------------------------

def test_8_the_reason(box):
    reason = _refused(box, "git add -A", box.a)
    lines = reason.splitlines()
    assert len(lines) == 1 and lines[0].startswith(HEAD)
    for want in ("36", "Commits", str(box.h / "tree" / "CLAUDE.md"), str(box.a), "by name"):
        assert want in reason, want
    assert str(box.l / "CLAUDE.md") in _refused(box, "git add -A", box.l)
    two = _refused(box, "git init && git add -A", box.a).splitlines()
    assert len(two) == 2 and all(t.startswith(HEAD) for t in two)
    for line in ("rm -rf $T", "git init", "git config user.name x"):
        r = _refused(box, line, box.a)
        assert "a rule of the agentik-session plugin, in every session" in r
        assert "36" not in r.replace(str(box.h), "")


# ---- 9: the mark ------------------------------------------------------------------------------

def test_9_the_mark(box):
    _refused(box, "git add -A", box.a)
    mark = _refused_dir(box) / TUID
    assert mark.read_text() == "sweep\n"
    assert stat.S_IMODE(mark.stat().st_mode) == 0o600
    _refused(box, "git init && git add -A", box.a)
    assert mark.read_text() == "init\nsweep\n"
    _passed(box, "git status", box.a)
    for tid in (None, "../x", "x" * 129, "a/b"):
        more = {"tool_use_id": tid} if tid is not None else {}
        p = _payload(box, "git add -A", box.a, **more)
        if tid is None:
            p.pop("tool_use_id")
        shutil.rmtree(_refused_dir(box), ignore_errors=True)
        assert _decision(hooks.pre_tool_use(p, box.env))[0] == "deny"
        assert not _refused_dir(box).exists() or not any(_refused_dir(box).iterdir())
    sdir = resolver.session_dir(box.state, SID)
    shutil.rmtree(_refused_dir(box), ignore_errors=True)
    sdir.chmod(0o500)
    try:
        assert _decision(lineguard.check(_payload(box, "git add -A", box.a), box.env))[0] == "deny"
    finally:
        sdir.chmod(0o700)


# ---- 10: the log ------------------------------------------------------------------------------

def test_10_the_log(box):
    _refused(box, "git add -A", box.a)
    _refused(box, "rm -rf $T", box.p)
    rows = [r for r in _log(box) if r.get("decision") == "deny"]
    assert [r["rule"] for r in rows] == [["sweep"], ["rm"]]
    assert rows[0]["path"] == str(box.a) and rows[1]["path"] is None
    assert all(r["why"] == "the strict reading" for r in rows)
    shutil.rmtree(_refused_dir(box), ignore_errors=True)
    out = hooks.pre_tool_use(_payload(box, "echo x >> CLAUDE.md", box.a), box.env)
    assert _decision(out)[0] == "deny" and not _refused_dir(box).exists()
    assert "rule" not in _log(box)[-1]
    sdir = resolver.session_dir(box.state, SID)
    before = instructionguard.counts(sdir)
    for line in SWEEP_PASS_LOGGED:
        _passed(box, line, box.a)
    assert [r["decision"] for r in _log(box)[-3:]] == ["pass"] * 3
    assert instructionguard.counts(sdir) == before


def test_10_no_cwd_judges_no_git_rule_and_logs_one_pass(box):
    _passed(box, "git add -A", None)
    assert [r["decision"] for r in _log(box)] == ["pass"]
    _refused(box, "rm -rf $T", None)


# ---- 11: an error -----------------------------------------------------------------------------

def test_11_an_error_refuses(box, monkeypatch):
    for exc in (RuntimeError("x"), shellreader._Bound("x")):
        def boom(*a, **k):
            raise exc
        monkeypatch.setattr(shellreader, "commands", boom)
        reason = _refused(box, "git status", box.a)
        assert type(exc).__name__ in reason and "retry once" in reason
        assert (_refused_dir(box) / TUID).read_text() == "error\n"
        assert _log(box)[-1]["why"] == "error: " + type(exc).__name__
        _passed(box, "ls -la", box.a)
    monkeypatch.undo()

    def raise_(*a, **k):
        raise ValueError("y")
    monkeypatch.setattr(lineguard, "check", raise_)
    assert "ValueError" in _refused(box, "git status", box.a)
    assert (_refused_dir(box) / TUID).read_text() == "error\n"
    _passed(box, "ls -la", box.a)


# ---- 12: the edit gates are as they were ------------------------------------------------------

def test_12_the_edit_gates(box):
    shutil.rmtree(_refused_dir(box), ignore_errors=True)
    out = hooks.pre_tool_use(_payload(box, "echo x >> CLAUDE.md", box.a), box.env)
    d, reason = _decision(out)
    assert d == "deny" and "is gated" in reason and not _refused_dir(box).exists()
    reason = _refused(box, "echo x >> CLAUDE.md; git add -A", box.a)
    assert (_refused_dir(box) / TUID).read_text() == "sweep\n"


def test_12_a_refused_call_opens_no_call_file(box):
    _refused(box, "git add -A", box.a, agent_id="agent-1")
    calls = resolver.session_dir(box.state, SID) / "calls"
    assert not calls.exists() or not any(calls.iterdir())


# ---- 13: a helper -----------------------------------------------------------------------------

def test_13_a_helper_gets_the_same_answers(box):
    more = {"agent_id": "agent-1"}
    _refused(box, SWEEP_IN_A[0], box.a, **more)
    _passed(box, SWEEP_PASS_A[0], box.a, **more)
    _refused(box, RM_REFUSED[0], box.p, **more)
    _passed(box, RM_PASSED[0], box.p, **more)
    _refused(box, INIT_REFUSED_A[0], box.a, **more)
    _refused(box, ID_REFUSED_A[0], box.a, **more)
    _refused(box, LOOSE_P[0], box.p, **more)


# ---- arming, as a reviewer will try it ---------------------------------------------------------

def test_arming_by_title(box):
    assert lineguard.arming("Commits", str(box.a), box.env)[1:] == ("36", 3)
    assert lineguard.arming("Commits", str(box.f), box.env) is None
    assert lineguard.arming("Commits", str(box.o), box.env) is None
    t = box.h / "tilde"
    (t / ".git").mkdir(parents=True)
    (t / "CLAUDE.md").write_text("~~~\n36. **Commits.** x\n~~~\n")
    assert lineguard.arming("Commits", str(t), box.env) is None
    (t / "CLAUDE.md").write_text("x" * 262144 + "\n36. **Commits.** x\n")
    assert lineguard.arming("Commits", str(t), box.env) is None
    (t / "CLAUDE.md").unlink()
    (t / "CLAUDE.md").symlink_to(box.l / "CLAUDE.md")
    assert lineguard.arming("Commits", str(t), box.env)[1:] == ("36", 3)
    (box.h / ".claude" / "CLAUDE.md").write_text("37. **Commits.** By path.\n")
    assert lineguard.arming("Commits", str(box.o), box.env)[1:] == ("37", 1)


def test_the_table(box):
    assert [(r[0], r[1]) for r in lineguard.RULES] == [
        ("rm", "product"), ("init", "product"), ("identity", "product"), ("sweep", "Commits")]
