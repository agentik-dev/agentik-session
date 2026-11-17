"""g10-push-guard: a helper's push is refused in a checkout armed by the title `Pushes` (R1 to R7).

Every case is a payload through `hooks.pre_tool_use` under a temp home H. The box: `H/tree/CLAUDE.md`
arms `Pushes` (entry 5, line 3) and `Commits` (entry 36, line 4); A is `H/tree/armed` (a checkout,
with `sub`); W a worktree of A with a `.git` file; O `H/open` (a checkout no title arms); P
`H/plain` (no checkout). The tool's paths (`/opt/x/...`) are made up and never run.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "lib"))

from claude_session import hooks, instructionguard, lineguard, resolver, shellreader  # noqa: E402

SID, TUID = "s1", "toolu_1"
HEAD = "agentik-session: refused by"
HELPER = {"agent_id": "agent-1"}
ENTRY11 = "entry 11 of agentik-session's DECISIONS.md, in every session"


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
    (h / "tree" / "CLAUDE.md").write_text("# The tree\n\n5. **Pushes.** The sitting pushes.\n"
                                          "36. **Commits.** Commit by explicit path.\n")
    b.a = h / "tree" / "armed"
    (b.a / ".git").mkdir(parents=True)
    (b.a / "sub").mkdir()
    b.w = b.a / ".claude" / "worktrees" / "w"
    b.w.mkdir(parents=True)
    (b.w / ".git").write_text("gitdir: " + str(b.a / ".git" / "worktrees" / "w") + "\n")
    b.o = h / "open"
    (b.o / ".git").mkdir(parents=True)
    b.p = h / "plain"
    b.p.mkdir()
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


def _refused_dir(b):
    return resolver.session_dir(b.state, SID) / "refused"


def _log(b):
    p = resolver.session_dir(b.state, SID) / instructionguard.LOG
    return [json.loads(t) for t in p.read_text().splitlines()] if p.exists() else []


def _run(b, command, cwd, **more):
    shutil.rmtree(_refused_dir(b), ignore_errors=True)
    out = hooks.pre_tool_use(_payload(b, command, cwd, **more), b.env)
    assert '"ask"' not in json.dumps(out)
    return out


def _reason(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecision"), h.get("permissionDecisionReason") or ""


def _refused(b, command, cwd, **more):
    d, reason = _reason(_run(b, command, cwd, **more))
    assert d == "deny", (command, cwd)
    assert reason.startswith(HEAD) and "the push rule" in reason, (command, reason)
    assert (_refused_dir(b) / TUID).read_text().splitlines()[-1] == "push", command
    return reason


def _passed(b, command, cwd, **more):
    out = _run(b, command, cwd, **more)
    assert _reason(out)[0] is None, (command, cwd, out)
    assert not _refused_dir(b).exists(), command


def _pushes(b, cwd=None):
    return f"{HEAD} the push rule, entry 5 (`Pushes`) of {b.h}/tree/CLAUDE.md, line 3, " \
        f"arms it for the checkout {cwd or b.a}: a helper never pushes. Hand back the branch " \
        "and its head; the sitting that started you pushes."


# ---- A1, A2, A3: the rule, a helper's alone ----------------------------------------------------

def test_a1_a_helpers_push_in_an_armed_checkout(box):
    assert _refused(box, "git push", box.a, **HELPER) == _pushes(box)
    assert (_refused_dir(box) / TUID).read_text() == "push\n"
    rows = [r for r in _log(box) if r.get("decision") == "deny"]
    assert len(rows) == 1 and rows[0]["rule"] == ["push"] and rows[0]["path"] == str(box.a)
    for line in ("git push origin main", "git push --force-with-lease", "GIT push", "/usr/bin/git push",
                 "git -c a.b=c push", "(git push)", "{ git push; }", "bash -c 'git push'"):
        _refused(box, line, box.a, **HELPER)
    _refused(box, "git push", box.a / "sub", **HELPER)
    assert _refused(box, "git push", box.w, **HELPER) == _pushes(box, box.w)


def test_a2_a_main_threads_push_is_never_judged(box):
    out = _run(box, "git push", box.a)
    assert out == {} and not _refused_dir(box).exists() and _log(box) == []
    for line in ("agentik session gate publish", "agentik session gate land r b s m --push"):
        assert _run(box, line, box.a) == {}
    assert not _refused_dir(box).exists() and _log(box) == []
    assert _run(box, "git push", box.a, agent_id="") == {}


def test_a3_an_unarmed_checkout_passes(box):
    for cwd in (box.o, box.p):
        for line in ("git push", "agentik session gate publish", "git subtree push --prefix=x r b"):
            _passed(box, line, cwd, **HELPER)


# ---- A4: the checkout the command acts on ------------------------------------------------------

def test_a4_the_checkout_the_push_acts_on(box):
    for line in ("git -C <A> push", "GIT_DIR=<A>/.git git push", 'T=<A>; git -C "$T" push',
                 "git --git-dir=<A>/.git push", "git --work-tree <A> push", "cd <A> && git push",
                 "git -C H/tree -C armed push", "git -C <A>/sub push"):
        assert _refused(box, line, box.o, **HELPER).endswith("the sitting that started you pushes."), line
    for line in ("git -C H/open push", "cd H/open && git push", 'T=H/open; git -C "$T" push'):
        _passed(box, line, box.p, **HELPER)


# ---- A5: git's verbs ---------------------------------------------------------------------------

def test_a5_the_push_and_its_plumbing(box):
    for line in ("git send-pack r main", "git http-push r main", "git subtree push --prefix=x r b",
                 "git push --dry-run", "git push --help", "git -C . push -n"):
        _refused(box, line, box.a, **HELPER)
    for line in ("git fetch", "git remote -v", "git subtree pull --prefix=x r b", "git status",
                 "git log --grep push", "git pushx", "git commit -m push", "echo push"):
        _passed(box, line, box.a, **HELPER)


# ---- A6: the session tool's verbs --------------------------------------------------------------

TOOLS = ["agentik session", "agentik-session", "claude-session", "/opt/x/bin/agentik-session",
         "/opt/x/bin/agentik session", "AGENTIK-SESSION", "python3 /opt/x/lib/agentik-session",
         "/usr/bin/python3 -I /opt/x/lib/agentik-session", "env python3 /opt/x/lib/agentik-session",
         "sh /opt/x/bin/agentik-session", "sh /opt/x/bin/agentik session",
         "python3 -m claude_session", "command agentik session", "sudo -u x agentik session",
         "X=1 agentik session"]
REFUSED = ["gate publish", "gate publish --dry-run", "gate publish x y", "gate land r b s m --push",
           "gate land r b s m --pus", "gate land r b s m --pu", "gate land r b s m --p",
           "gate land --push r b s m", "gate land --wall 9 r b s m --push",
           "gate land --session s r b s m --push --install"]
PASSED = ["gate land r b s m", "gate status", "gate wait 1 --strict", "gate run . -- make check",
          "gate land r b s m --push=1", "gate land r b s m -- --push", "gate land r b s m --install",
          "status", "gate publishx", "gate pub"]


def test_a6_each_spelling_of_the_tool(box):
    for tool in TOOLS:
        for verb in REFUSED:
            _refused(box, f"{tool} {verb}", box.a, **HELPER)
        for verb in PASSED:
            _passed(box, f"{tool} {verb}", box.a, **HELPER)
    _refused(box, "bash -c 'agentik session gate publish'", box.a, **HELPER)
    for line in ("agentik other gate publish", "python3 -c 'x' gate publish",
                 "python3 /opt/x/lib/other gate publish", "echo agentik session gate publish",
                 "uvx gate publish"):
        _passed(box, line, box.a, **HELPER)


def test_a6_the_checkout_of_the_tools_verb(box):
    for line in ("agentik session gate publish <A>", "agentik session gate land <A> b s m --push",
                 "agentik session gate publish H/open <A>", "cd <A> && agentik session gate publish",
                 "agentik session gate land --session s <A>/sub b s m --push",
                 "agentik session gate publish ../tree/armed"):
        _refused(box, line, box.p, **HELPER)
    for line in ("agentik session gate publish armed", "agentik session gate publish H/open",
                 "agentik session gate land <A> b s m", "agentik session gate land --session <A> "
                 "H/open b s m --push"):
        _passed(box, line, box.p, **HELPER)


# ---- A7: unread text ---------------------------------------------------------------------------

def test_a7_unread_text_and_data(box):
    for line in ('git commit -m "then git push"', 'echo "gate publish"', "echo 'git push'",
                 "cat > x.md <<'EOF'\ngit push\nagentik session gate publish\nEOF",
                 'grep -rn "git push" .', "printf '%s' 'agentik session gate land r b s m --push'"):
        _passed(box, line, box.a, **HELPER)
    for line in ('eval "git push"', "echo 'git push' | sh", "bash -c \"bash -c 'git push'\"",
                 "bash <<< 'git push'", 'eval "agentik session gate publish"',
                 "eval '/opt/x/bin/agentik-session gate land r b s m --push'"):
        assert "write it more simply" in _refused(box, line, box.a, **HELPER), line
    for line in ('eval "git push"', "eval 'agentik session gate publish'",
                 "eval 'agentik session gate land r b s m'"):
        _passed(box, line, box.o, **HELPER)
    _passed(box, "eval 'agentik session gate land r b s m'", box.a, **HELPER)


# ---- A8: the first look ------------------------------------------------------------------------

def test_a8_the_first_look(box):
    line = "agentik session gate publish x"
    assert lineguard.looks(line) is False and lineguard.looks(line, helper=True) is True
    assert lineguard.looks("ls") is False and lineguard.looks("ls", helper=True) is False
    assert _run(box, line, box.a) == {} and _log(box) == []


def test_a8_failed_follows_the_look(box, monkeypatch):
    def boom(*a, **k):
        raise ValueError("x")
    monkeypatch.setattr(shellreader, "commands", boom)
    line = "agentik session gate publish x"
    assert _run(box, line, box.a) == {}
    d, reason = _reason(_run(box, line, box.a, **HELPER))
    assert d == "deny" and "an error in its own reading" in reason
    assert (_refused_dir(box) / TUID).read_text() == "error\n"


# ---- A9: the product refusals name their entry -------------------------------------------------

def test_a9_the_product_refusals_name_entry_11(box):
    for line, cwd in (("rm -rf $T", box.p), ("git init", box.a), ("git config user.name x", box.a)):
        d, reason = _reason(_run(box, line, cwd))
        assert d == "deny" and ENTRY11 in reason and "a rule of the agentik-session plugin" \
            not in reason, line


# ---- the table and two rules on one line -------------------------------------------------------

def test_the_fifth_rule(box):
    assert [(r[0], r[1]) for r in lineguard.RULES][4] == ("push", "Pushes")
    _, reason = _reason(_run(box, "git add -A && git push", box.a, **HELPER))
    lines = reason.splitlines()
    assert len(lines) == 2 and "the sweep rule" in lines[0] and lines[1] == _pushes(box)
    assert (_refused_dir(box) / TUID).read_text() == "sweep\npush\n"
    assert [r for r in _log(box) if r.get("decision") == "deny"][-1]["rule"] == ["sweep", "push"]
    _, reason = _reason(_run(box, "git add -A && git push", box.a))
    assert "the push rule" not in reason
    _passed(box, "git push", None, **HELPER)
