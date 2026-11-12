"""Packet u2-loop-finish: the unattended loop finishes a row before it lands it.

R1 the child's prompt; R2 the packet's acceptance lines before a row is built or lands, read
as the relay reads them; R3 one named continuation, twice at most; R4 the limit's
continuation; R5 `--effort` from the row, the defaults, the builder profile. The fake `claude`
and gate of tests/fixtures/unattended/ stand in, through test_unattended's Box: no real
`claude` runs and no request is spent.
"""
import os
import time

import pytest

from claude_session import resolver, unattended
from test_unattended import OK, S2, _git, _land, box  # noqa: F401  (box is a fixture)

SID = "0b5c1c39-7a0e-4a52-9a43-1f2d3c4b5a61"           # green.jsonl's session
DRAFT = (
    "# You are one unattended builder; the packet below is your whole task\n\n"
    "You run headless (`claude -p`): a message with no tool call ends the sitting, and nobody "
    "reads it until the run is over. Build every act the packet lists, one commit per act, and "
    "end your turn only when the last act is committed and the tree is clean, or when nothing "
    "can move; then say why in the charter's handover. An error, a timeout or a failing test is "
    "work: diagnose it and get past it. A hook's denial and the packet's wall are deliberate: "
    "leave them and take another way. Do each act yourself in the foreground: no agent, no "
    "background command, no wait on a notification.")
TAIL = ("Continue with the acts that make them hold. If one is blocked, say what blocks it in "
        "the charter's handover.")


def _packet(box, rid, cell, title="a row"):
    (box.repo / "design" / "packets" / f"{rid}.md").write_text(
        f"# Packet {rid}: {title}\n\n| item | value |\n|---|---|\n| from | x |\n"
        f"| acceptance | {cell} |\n| budget | 9 turns, 9k context |\n\n## 1. What the source says\n")


def _queue(box, old, new):
    q = box.repo / "relay" / "queue.yaml"
    text = q.read_text()
    assert old in text
    q.write_text(text.replace(old, new, 1))


def _again(box, *rids):
    """A second run in the same box: the rows' trees and branches gone, the fake's log new."""
    for rid in rids:
        _git(box.repo, "worktree", "remove", "--force", str(box.repo / ".claude/worktrees" / rid))
        _git(box.repo, "branch", "-D", rid)
    box.log.unlink()


def _effort(start):
    a = start["argv"]
    return a[a.index("--effort") + 1] if "--effort" in a else None


# ---- R1 -------------------------------------------------------------------------

def test_t1_prompt(box):
    assert unattended.prompt("# Packet x\n") == DRAFT + "\n\n# Packet x\n"
    assert len(DRAFT.split()) < 130
    _packet(box, "green-row", "`true` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (start,) = box.starts
    assert start["stdin"] == DRAFT + "\n\n" + (box.repo / "design/packets/green-row.md").read_text()
    assert box.kind("row")[0]["state"] == "built"


# ---- R2: the cell, as the relay reads it -----------------------------------------

def _table(cell):
    return f"# Packet p: t\n\n| item | value |\n|---|---|\n| pin | main |\n| acceptance | {cell} |\n"


def test_t2_parser():
    got = unattended.acceptance(_table(
        r"`a \| b` reads `x y`; `wc -l f` reads 3 or more (pin: 0); `n` under 5; "
        r"`t; u` exits 2; `m` as main; `k` reads 7"))
    assert [ln.shell for ln in got] == ["a | b", "wc -l f", "n", "t; u", "m", "k"]
    assert [ln.kind for ln in got] == ["reads", "reads-or-more", "under", "exits", "as-main", "reads"]
    assert (got[0].value, got[1].n, got[2].n, got[3].n, got[5].value, got[5].n) == (
        "x y", 3, 5, 2, "7", 7)
    assert got[1].expect == "reads 3 or more (pin: 0)"
    h = unattended.line_holds
    assert h(got[0], 1, "x y") and not h(got[0], 0, "x  y")
    assert h(got[1], 1, " 3 ") and h(got[1], 0, "9") and not h(got[1], 0, "2") and not h(got[1], 0, "x")
    assert h(got[2], 0, "4") and not h(got[2], 0, "5")
    assert h(got[3], 2, "") and not h(got[3], 0, "")
    for text, why in (("# Packet p\n", "no acceptance row"),
                      (_table("foo exits 0"), "no shell span"),
                      (_table("`x` maybe"), "no expectation"),
                      (_table("`x exits 0"), "unterminated"),
                      (_table("`a | b` exits 0"), "cells"),
                      (_table(" ; "), "no item")):
        with pytest.raises(unattended.AcceptanceError, match=why):
            unattended.acceptance(text)


# ---- R2, R3: a failing line ---------------------------------------------------------

def test_t3_failing_line_never_lands(box):
    _packet(box, "limit-row", "`true` exits 0; `test -f never.txt` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box), gate=[OK])
    assert box.rc == 0 and box.gates == [] and box.kind("gate") == []
    assert len(box.starts) == 3                                   # the row, then two continuations
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance") and row["resume"].endswith(SID)
    (f,) = row["failing"]
    assert (f["line"], f["shell"], f["expect"], f["exit"], f["status"]) == (
        2, "test -f never.txt", "exits 0", 1, "red")
    assert [c["part"] for c in box.kind("continue")] == [2, 3]
    accepts = box.kind("accept")
    assert [a["part"] for a in accepts] == [1, 2, 3]
    assert [c["status"] for c in accepts[0]["lines"]] == ["green", "red"]


def test_t3_branch_only_is_not_built_unfinished(box):
    _packet(box, "green-row", "`test -f never.txt` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance") and len(box.starts) == 3


def test_t4_red_at_the_pin_compared(box):
    _packet(box, "limit-row", "`echo broken; exit 3` as main; "
                              "`git remote get-url --push origin` reads relay-denies-push")
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box), gate=[OK])
    (row,) = box.kind("row")
    assert row["state"] == "landed" and len(box.starts) == 1 and len(box.gates) == 1
    (base,) = box.kind("baseline")
    assert [(c["exit"], c["last"]) for c in base["lines"]] == [(3, "broken"), (None, None)]
    (acc,) = box.kind("accept")
    assert [c["status"] for c in acc["lines"]] == ["same-as-main", "green"]


def test_t4_as_main_moved_is_red(box):
    _packet(box, "green-row", "`ls work-0.txt` as main")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance")
    assert row["failing"][0]["main_exit"] != 0 and row["failing"][0]["exit"] == 0


def test_t5_unrun_and_cut_are_red(box, monkeypatch):
    _packet(box, "green-row", "`true` exits 0; `true` as main")
    monkeypatch.setattr(unattended, "SH", str(box.tmp / "no-such-sh"))
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance")
    assert [f["status"] for f in row["failing"]] == ["unrun", "unrun"]
    assert row["failing"][0]["exit"] is None and row["failing"][0]["last"]
    monkeypatch.setattr(unattended, "SH", "/bin/sh")
    _again(box, "green-row")
    _packet(box, "green-row", "`sleep 5; echo late` exits 0")
    monkeypatch.setattr(unattended, "LINE_LIMIT", 0.5)
    t = time.monotonic()
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert time.monotonic() - t < 12
    (row,) = box.kind("row")
    (f,) = row["failing"]
    assert (row["reason"], f["exit"], f["cut"], f["status"]) == ("acceptance", 124, True, "red")


def test_t10_no_cell_refused_before_the_spawn(box):
    (box.repo / "design" / "packets" / "green-row.md").write_text("# Packet green-row\n")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert box.starts == [] and box.kind("spawn") == []
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("refused", "acceptance")
    assert "green-row: acceptance: no acceptance row" in (box.dir / "log").read_text()
    assert not (box.repo / ".claude" / "worktrees" / "green-row").exists()


# ---- R3: the continuation --------------------------------------------------------

def test_t6_the_continuation_names_the_lines(box):
    _packet(box, "limit-row", "`echo three` reads four; `true` exits 0; `false` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box), gate=[OK])
    one, two, three = box.starts
    text = two["stdin"]
    assert text == three["stdin"] and text.endswith(TAIL + "\n")
    assert "`echo three` returned exit 0, last line \"three\"; it wants: reads four" in text
    assert "`false` returned exit 1, no output; it wants: exits 0" in text
    assert "`true`" not in text
    a = two["argv"]
    assert a[:3] == ["-p", "--resume", SID] and "--session-id" not in a and _effort(two) == "high"
    assert a[a.index("--max-turns") + 1] == "88" and a[a.index("--max-budget-usd") + 1] == "13.75"
    b = three["argv"]
    assert b[b.index("--max-turns") + 1] == "76" and b[b.index("--max-budget-usd") + 1] == "12.5"
    assert two["cwd"] == one["cwd"]


def test_t7_green_after_one_continuation_lands(box):
    _packet(box, "limit-row", "`test -f work-1.txt` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box), gate=[OK])
    assert len(box.starts) == 2 and len(box.gates) == 1
    (row,) = box.kind("row")
    assert row["state"] == "landed" and row["sha"] == box.gates[0]["argv"][-2]
    assert [c["part"] for c in box.kind("continue")] == [2]


# ---- R4: the limit -------------------------------------------------------------

def test_t8_limit_resumes_with_the_new_text(box):
    _packet(box, "limit-row", "`true` exits 0")
    box.go([{"stream": "rate-limit.jsonl"}, {"stream": "green.jsonl", "commit": True}], ["limit-row"])
    one, two = box.starts
    assert two["stdin"] == unattended.CONTINUE + "\n"
    for words in ("usage limit", "commits stand", "done-ness list", "unchecked act",
                  "acceptance lines", "commit", "what blocks"):
        assert words in unattended.CONTINUE
    assert two["argv"][:3] == ["-p", "--resume", S2] and _effort(two) == "high"
    assert box.kind("row")[0]["state"] == "built"


def test_t8_a_limit_inside_a_continuation_resumes_once(box):
    _packet(box, "limit-row", "`test -f work-2.txt` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}, {"stream": "rate-limit.jsonl"},
            {"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box), gate=[OK])
    assert len(box.starts) == 3 and [e["action"] for e in box.kind("limit")] == ["resume"]
    assert box.starts[2]["stdin"] == unattended.CONTINUE + "\n"
    assert box.kind("row")[0]["state"] == "landed"


# ---- R5: effort ------------------------------------------------------------------

def test_t9_effort_row_defaults_profile(box, monkeypatch):
    for rid in ("green-row", "max-row"):
        _packet(box, rid, "`true` exits 0")
    _queue(box, "    merge: branch-only\n    device: never\n",
           "    merge: branch-only\n    effort: max\n    device: never\n")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"])
    assert [_effort(s) for s in box.starts] == ["max", "high"]       # the row; the shipped profile
    assert [s["effort"] for s in box.kind("spawn")] == ["max", "high"]
    assert [r["effort"] for r in box.kind("row")] == ["max", "high"]
    rows = {r["row"]: r for r in box.kind("row")}
    out = unattended.report(box.dir)
    assert f"| green-row | {rows['green-row']['sha']} | - | {rows['green-row']['worktree']} | max |" in out

    prof = box.tmp / "home" / ".claude" / "agentik" / "profiles.yaml"
    prof.parent.mkdir(parents=True)
    prof.write_text("profiles:\n  builder:\n    effort: medium\n")
    monkeypatch.setenv("HOME", str(box.tmp / "home"))
    _again(box, "green-row", "max-row")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"])
    assert [_effort(s) for s in box.starts] == ["max", "medium"]     # the user's builder profile
    _queue(box, "verify: auto}", "verify: auto, effort: low}")
    _again(box, "green-row", "max-row")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"])
    assert [_effort(s) for s in box.starts] == ["max", "low"]        # the queue's defaults


def test_t9_effort_fallback_and_refusal(box, monkeypatch):
    _packet(box, "green-row", "`true` exits 0")
    real = resolver.load_profiles

    def gone(env):
        raise resolver.ResolveError("no profiles")
    monkeypatch.setattr(resolver, "load_profiles", gone)
    assert unattended.builder_effort(dict(os.environ)) == "high"
    monkeypatch.setattr(resolver, "load_profiles", lambda env: ({}, {"builder": {"effort": "lots"}}))
    assert unattended.builder_effort(dict(os.environ)) == "high"
    monkeypatch.setattr(resolver, "load_profiles", real)
    assert unattended.builder_effort(dict(os.environ)) == "high"         # the shipped builder's
    _queue(box, "    merge: branch-only\n    device: never\n",
           "    merge: branch-only\n    effort: huge\n    device: never\n")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert box.starts == []
    assert [(r["state"], r["reason"]) for r in box.kind("row")] == [("refused", "effort")]
    a = unattended.spawn_argv("m", 5, 1, sid="s", effort="low")
    assert a[a.index("--effort") + 1] == "low" and a.index("--effort") == a.index("--model") + 2
