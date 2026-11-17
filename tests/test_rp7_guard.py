"""rp7-guard: a model's `agentik issue send` is refused in every session (R1 to R9).

Every case is a payload through `hooks.pre_tool_use` under a temp home H: a main thread's call and
a helper's alike, with no rule's title armed anywhere. P is `H/plain` (no checkout), O `H/open`
(a checkout). The launcher's paths (`/opt/x/...`) are made up and never run; no line is run.
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
REASON = (f"{HEAD} the issue rule, a rule of the agentik-session plugin, in every session: "
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


# ---- line 1: each line of R2 and R9 is denied, in the main thread and in a helper ---------------

DENIED = ["agentik issue send", "env -u CLAUDECODE agentik issue send",
          "CLAUDECODE= agentik issue send", "X=1 agentik issue send", "command agentik issue send",
          "exec agentik issue send", "env -u CLAUDECODE CLAUDECODE= agentik issue send",
          "agentik issue send --dry-run", "agentik issue send --web", "agentik issue -y send",
          "agentik issue --dry-run send --yes", "agentik issue send -q --no-color",
          "agentik --x issue send", "agentik-suite issue send", "agentik-suite issue -y send",
          "/opt/x/bin/agentik issue send", "/opt/x/bin/agentik-suite issue send",
          "AGENTIK issue send", "python3 /opt/x/bin/agentik-suite issue send",
          "sh /opt/x/bin/agentik issue send", "true && agentik issue send",
          "cd /opt/x; agentik issue send", "agentik issue send | tee x",
          "echo y | agentik issue send", "agentik issue show || agentik issue send",
          "sh -c 'agentik issue send'", "bash -c 'env -u CLAUDECODE agentik issue send --yes'",
          "(agentik issue send)", "{ agentik issue send; }"]


def test_l1_each_line_is_denied(box):
    for extra in ({}, HELPER):
        for line in DENIED:
            for cwd in (box.p, box.o, None):
                d, reason = _reason(_run(box, line, cwd, **extra))
                assert d == "deny" and reason == REASON, (line, cwd, extra, reason)
                assert (_refused_dir(box) / TUID).read_text() == "issue\n", line


def test_l1_the_mark_and_the_log(box):
    _run(box, "agentik issue send", None)
    rows = [r for r in _log(box) if r.get("decision") == "deny"]
    assert len(rows) == 1 and rows[0]["rule"] == ["issue"] and rows[0]["path"] is None
    assert not [r for r in _log(box) if "cwd" in str(r.get("why"))]


# ---- line 2: each line of R3 and R9 passes ------------------------------------------------------

PASSED = ["agentik issue", "agentik issue new", "agentik issue show", "agentik issue strike send",
          "agentik issue drop send", "agentik issue edit", "agentik issue reword send",
          "agentik issue discard", "agentik issue --check", "agentik issue send --help",
          "agentik issue send -h", "agentik issue -h send", "agentik issue --help send --yes",
          "agentik-suite issue send --help", 'grep -rn "agentik issue send" .',
          "echo agentik issue send", "echo 'agentik issue send'", "gh issue list",
          "gh issue view 1 --comments | grep send", "./send-issue.sh", "sh ./send-issue.sh",
          "agentik issue $VERB", 'agentik issue "$V" send', "agentik $T send", "agentik $T issue send",
          "agentik session issue send", "agentik other issue send", "agentik-suite session issue send",
          "agentik-suite x issue send", "agentik issued send", "agentik issue sender",
          "printf '%s\\n' 'agentik issue send'", "cat > x.md <<'EOF'\nagentik issue send\nEOF",
          'git commit -m "agentik issue send"']


def test_l2_each_line_passes(box):
    for extra in ({}, HELPER):
        for line in PASSED:
            for cwd in (box.p, None):
                out = _run(box, line, cwd, **extra)
                assert out == {}, (line, cwd, extra, out)
                assert not _refused_dir(box).exists(), line


def test_l2_an_unread_part_passes(box):
    for line in ('eval "agentik issue send"', "echo 'agentik issue send' | sh",
                 "bash <<< 'agentik issue send'"):
        for extra in ({}, HELPER):
            d, reason = _reason(_run(box, line, box.p, **extra))
            assert "the issue rule" not in reason, (line, reason)


# ---- R6: the first look -------------------------------------------------------------------------

def test_r6_the_first_look(box):
    for line in ("agentik issue send", "AGENTIK ISSUE SEND", "agentik issue \\\nsend"):
        assert lineguard.looks(line) is True and lineguard.looks(line, helper=True) is True
    for line in ("agentik issue new", "agentik session send", "ls"):
        assert lineguard.looks(line) is False and lineguard.looks(line, helper=True) is False
    line = "agentik 'is'sue send"
    assert lineguard.looks(line) is False and lineguard.looks(line, helper=True) is True
    assert _run(box, "gh issue comment 1 --body 'send it'", box.p) == {}


def test_r6_failed_follows_the_look(box, monkeypatch):
    def boom(*a, **k):
        raise ValueError("x")
    monkeypatch.setattr(shellreader, "commands", boom)
    assert _run(box, "agentik issue new", box.p) == {}
    for extra in ({}, HELPER):
        d, reason = _reason(_run(box, "agentik issue send", box.p, **extra))
        assert d == "deny" and "an error in its own reading" in reason
        assert (_refused_dir(box) / TUID).read_text() == "error\n"


# ---- R7, R8: the reason's by, the table, two rules on one line ----------------------------------

def test_r7_the_reason_cites_no_entry(box):
    assert "entry" not in REASON and "DECISIONS" not in REASON
    assert lineguard.PLUGIN == "entry 11 of agentik-session's DECISIONS.md, in every session"


def test_r8_the_sixth_rule(box):
    assert [(r[0], r[1]) for r in lineguard.RULES][5] == ("issue", "product")
    assert lineguard.RULES[5][3]("agentik issue send") is False
    _, reason = _reason(_run(box, "rm -rf $T; agentik issue send", box.p))
    lines = reason.splitlines()
    assert len(lines) == 2 and "the rm rule" in lines[0] and lines[1] == REASON
    assert (_refused_dir(box) / TUID).read_text() == "rm\nissue\n"
    assert [r for r in _log(box) if r.get("decision") == "deny"][-1]["rule"] == ["rm", "issue"]
