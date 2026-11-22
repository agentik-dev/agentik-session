"""in5s-reply-guard: a model's `agentik decisions reply` and `inbox answer`, refused (R1 to R8).

Every case is a payload through `hooks.pre_tool_use` under a temp home H: a main thread's call and
a helper's alike, with no rule's title armed anywhere. P is `H/plain` (no checkout), O `H/open`
(a checkout). The launchers' paths (`/opt/x/...`) and the repo `quince` are made up; no line is
run.
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
REASON = (f"{HEAD} the reply rule, a rule of the agentik-session plugin, in every session: "
          "`reply` and `inbox answer` type the owner's answer onto a question's answer line and "
          "are the owner's alone, at a terminal. Read the line with `agentik decisions "
          "questions` and enter what he typed with `agentik decisions answer N`; to have him "
          "answer, hand him the line to run.")
ISSUE = (f"{HEAD} the issue rule, a rule of the agentik-session plugin, in every session: "
         "`issue send` files a public issue and wants a person's typed word on a terminal. "
         "Hand the user the line to run in a terminal of their own.")


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
    b.p = h / "plain"
    b.p.mkdir()
    b.o = h / "open"
    (b.o / ".git").mkdir(parents=True)
    return b


def _payload(command, cwd, **more):
    p = {"session_id": SID, "transcript_path": "/t.jsonl", "hook_event_name": "PreToolUse",
         "tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": TUID, **more}
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
    out = hooks.pre_tool_use(_payload(command, cwd, **more), b.env)
    assert '"ask"' not in json.dumps(out)
    return out


def _reason(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecision"), h.get("permissionDecisionReason") or ""


# ---- line 1: each line of R2 is denied, in the main thread and in a helper ----------------------

L = "--ledger /opt/x/DECISIONS.md"
DENIED = [
    # (a) the door, then `decisions`, then `reply`
    "agentik decisions reply", "agentik decisions reply 3 --pick a",
    f"agentik decisions {L} reply 3", "agentik decisions --ledger=/opt/x/DECISIONS.md reply 3",
    "agentik decisions --led /opt/x/DECISIONS.md reply 3",
    "agentik decisions reply 3 --dry-run", "agentik decisions reply --yes 3",
    f"agentik decisions {L} reply 3 --dry-run --yes", "agentik decisions -- reply 3",
    "agentik --x decisions reply 3", "/opt/x/bin/agentik decisions reply 3",
    "AGENTIK decisions reply 3", "python3 /opt/x/bin/agentik decisions reply 3",
    # (b) the decisions tool's own launcher
    "agentik-decisions reply 3", f"agentik-decisions {L} reply 3 --dry-run",
    "/opt/x/bin/agentik-decisions reply 3", "sh /opt/x/bin/agentik-decisions reply 3",
    # (c) the door or the suite's launcher, then `inbox answer`
    "agentik inbox answer quince 3", "agentik inbox answer quince 3 --dry-run",
    "agentik inbox --json answer quince 3", "agentik --x inbox answer quince 3",
    "agentik-suite inbox answer quince 3", "/opt/x/bin/agentik-suite inbox answer quince 3",
    "agentik-suite inbox -q answer quince 3",
    # behind an assignment, `env`, `command` or `exec`
    "X=1 agentik decisions reply 3", "CLAUDECODE= agentik-decisions reply 3",
    "env -u CLAUDECODE agentik decisions reply 3", "env agentik inbox answer quince 3",
    "command agentik decisions reply 3", "exec agentik-decisions reply 3",
    "command agentik-suite inbox answer quince 3",
    # one part of a list, and `sh -c`
    "true && agentik decisions reply 3", "cd /opt/x; agentik decisions reply 3",
    "agentik decisions reply 3 | tee x", "echo y | agentik-decisions reply 3",
    "agentik decisions questions && agentik inbox answer quince 3",
    "sh -c 'agentik decisions reply 3'",
    "bash -c 'env -u CLAUDECODE agentik inbox answer quince 3 --yes'",
    "(agentik decisions reply 3)", "{ agentik-decisions reply 3; }"]


def test_l1_each_line_is_denied(box):
    for extra in ({}, HELPER):
        for line in DENIED:
            for cwd in (box.p, box.o, None):
                d, reason = _reason(_run(box, line, cwd, **extra))
                assert d == "deny" and reason == REASON, (line, cwd, extra, reason)
                assert (_refused_dir(box) / TUID).read_text() == "reply\n", line


def test_l1_the_mark_and_the_log(box):
    _run(box, "agentik decisions reply 3", None)
    rows = [r for r in _log(box) if r.get("decision") == "deny"]
    assert len(rows) == 1 and rows[0]["rule"] == ["reply"] and rows[0]["path"] is None
    assert not [r for r in _log(box) if "cwd" in str(r.get("why"))]


# ---- line 2: each line of R3 passes -------------------------------------------------------------

PASSED = [
    # every other verb, and the verb's words elsewhere
    "agentik decisions", "agentik decisions answer 3 --pick a --source s --no-entry",
    "agentik decisions questions", "agentik decisions ask", "agentik decisions show 3",
    "agentik decisions new --title reply", "agentik decisions render",
    "agentik decisions find reply", "agentik decisions show reply", "agentik decisions replyx",
    "agentik-decisions questions", "agentik-decisions show 3 --ledger reply",
    "agentik inbox", "agentik inbox quince 3", "agentik inbox --check", "agentik inbox quince",
    "agentik inbox quince answer", "agentik inbox answers", "agentik-suite inbox",
    "agentik-suite inbox --json",
    # a flag's operand that spells the word
    "agentik decisions --ledger reply show 3", "agentik-decisions --ledger reply questions",
    # help anywhere after the tool word
    "agentik decisions reply --help", "agentik decisions reply 3 -h",
    "agentik decisions -h reply", "agentik decisions --help reply 3 --yes",
    "agentik-decisions reply --help", "agentik inbox answer --help", "agentik inbox -h answer",
    "agentik-suite inbox answer quince 3 -h",
    # the words as data, a path, a commit message
    'grep -rn "agentik decisions reply" .', "echo agentik decisions reply 3",
    "echo 'agentik inbox answer quince 3'", "printf '%s\\n' 'agentik decisions reply'",
    "cat > x.md <<'EOF'\nagentik decisions reply 3\nEOF", "cat /opt/x/reply.md",
    "ls /opt/x/inbox/answer", "/opt/x/inbox/answer", 'git commit -m "agentik decisions reply"',
    'git commit -m "the reply rule"', "gh pr comment 1 --body reply",
    # a script file's name, a variable in the verb's place
    "./reply.sh", "sh ./reply-to-owner.sh", "agentik decisions $VERB 3",
    'agentik decisions "$V" reply', "agentik $T reply", "agentik $T decisions reply",
    "agentik inbox $V quince 3", 'agentik inbox "$V" answer',
    # another tool at the tool's place
    "agentik session reply", "agentik other decisions reply", "agentik-suite x inbox answer",
    "agentik decisions-x reply", "agentik-decision reply"]


def test_l2_each_line_passes(box):
    for extra in ({}, HELPER):
        for line in PASSED:
            for cwd in (box.p, None):
                out = _run(box, line, cwd, **extra)
                assert out == {}, (line, cwd, extra, out)
                assert not _refused_dir(box).exists(), line


def test_l2_an_unread_part_passes(box):
    for line in ('eval "agentik decisions reply 3"', "echo 'agentik inbox answer quince' | sh",
                 "bash <<< 'agentik-decisions reply 3'"):
        for extra in ({}, HELPER):
            d, reason = _reason(_run(box, line, box.p, **extra))
            assert "the reply rule" not in reason, (line, reason)


def test_r3_an_unknown_flag_takes_no_operand(box):
    for extra in ({}, HELPER):
        d, reason = _reason(_run(box, "agentik decisions --foo reply 3", box.p, **extra))
        assert d == "deny" and reason == REASON


# ---- R6: the first look -------------------------------------------------------------------------

def test_r6_the_first_look(box):
    for line in ("agentik decisions reply", "AGENTIK DECISIONS REPLY",
                 "agentik decisions \\\nreply", "agentik inbox answer quince 3",
                 "agentik-decisions reply 3"):
        assert lineguard.looks(line) is True and lineguard.looks(line, helper=True) is True
    for line in ("agentik decisions questions", "agentik inbox quince", "agentik inbox",
                 "agentik decisions answer 3", "ls"):
        assert lineguard.looks(line) is False and lineguard.looks(line, helper=True) is False
    line = "agentik decisions 're'ply 3"
    assert lineguard.looks(line) is False and lineguard.looks(line, helper=True) is True
    assert _run(box, "gh pr comment 1 --body reply", box.p) == {}


def test_r6_failed_follows_the_look(box, monkeypatch):
    def boom(*a, **k):
        raise ValueError("x")
    monkeypatch.setattr(shellreader, "commands", boom)
    assert _run(box, "agentik decisions questions", box.p) == {}
    for line in ("agentik decisions reply 3", "agentik inbox answer quince 3"):
        for extra in ({}, HELPER):
            d, reason = _reason(_run(box, line, box.p, **extra))
            assert d == "deny" and "an error in its own reading" in reason
            assert (_refused_dir(box) / TUID).read_text() == "error\n"


# ---- R5, R7, R8: the reason's by, the table, two rules on one line ------------------------------

def test_r5_the_reason_cites_no_entry(box):
    assert "entry" not in REASON and "DECISIONS" not in REASON
    assert lineguard.PLUGIN == "entry 11 of agentik-session's DECISIONS.md, in every session"
    assert lineguard.PLUGIN_RULE == "a rule of the agentik-session plugin, in every session"
    d, reason = _reason(_run(box, "agentik issue send", box.p))
    assert d == "deny" and reason == ISSUE


def test_r8_the_seventh_rule(box):
    assert [(r[0], r[1]) for r in lineguard.RULES][6] == ("reply", "product")
    assert len(lineguard.RULES) == 7
    assert lineguard.RULES[6][3]("agentik decisions reply 3") is False
    _, reason = _reason(_run(box, "agentik issue send; agentik decisions reply 3", box.p))
    lines = reason.splitlines()
    assert lines == [ISSUE, REASON]
    assert (_refused_dir(box) / TUID).read_text() == "issue\nreply\n"
    assert [r for r in _log(box) if r.get("decision") == "deny"][-1]["rule"] == ["issue", "reply"]
