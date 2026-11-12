"""Packet u2-loop-finish: the unattended loop finishes a row before it lands it.

R1 the child's prompt; R2 the packet's acceptance lines before a row is built or lands, read
as the relay reads them; R3 one named continuation, twice at most; R4 the limit's
continuation; R5 `--effort` from the row, the defaults, the builder profile. The fake `claude`
and gate of tests/fixtures/unattended/ stand in, through test_unattended's Box: no real
`claude` runs and no request is spent.
"""
import os
import subprocess
import sys
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


def test_f1_only_the_header_table_after_the_title():
    """Review F1: the cell is read only from the header table directly after the title, as the
    relay's `table()` and `header()` read it; a fenced example, a later table, a duplicate or
    an extra row is never read."""
    fence = ("# Packet p: t\n\nProse. Acceptance: the tests pass.\n\n## An example\n\n```\n"
             "| item | value |\n|---|---|\n| acceptance | `true` exits 0 |\n```\n")
    later = ("# Packet p: t\n\n| item | value |\n|---|---|\n| pin | main |\n\n## 5\n\n"
             "| item | value |\n|---|---|\n| acceptance | `true` exits 0 |\n")
    for text, why in ((fence, "no header table"), (later, "no acceptance row"),
                      ("intro\n# Packet p: t\n" + _table("`true` exits 0")[13:], "no title"),
                      ("# Packet p: t\n\n  | item | value |\n  |---|---|\n"
                       "  | acceptance | `true` exits 0 |\n", "no header table"),
                      (_table("`true` exits 0") + "| acceptance | `false` exits 0 |\n", "duplicate"),
                      (_table("`true` exits 0") + "| needs | x |\n", "extra"),
                      (_table("`true` exits 0") + "| wall | a | b |\n", "row wall: 3 cells")):
        with pytest.raises(unattended.AcceptanceError, match=why):
            unattended.acceptance(text)
    full = ("# Packet p: t\n\n| item | value |\n|---|---|\n| from | x |\n| pin | y |\n| wall | z |\n"
            "| may touch | `a` |\n| acceptance | `true` exits 0 |\n| budget | 9 turns, 9k context |\n"
            "| verify | `make check` |\n\n## 1. What the source says\n\n| acceptance | `false` exits 0 |\n")
    assert [ln.shell for ln in unattended.acceptance(full)] == ["true"]
    early = full.replace("| verify | `make check` |\n", "").replace("| budget", "| verify | `v` |\n| budget")
    assert [ln.shell for ln in unattended.acceptance(early)] == ["true"]     # this repo's order


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


def _trees(repo):
    return [ln for ln in _git(repo, "worktree", "list", "--porcelain").splitlines()
            if ln.startswith("worktree ")]


def test_f4_the_baseline_is_main_never_a_reused_tree(box):
    """Review F4: a clean tree an earlier run left on the row's branch, with a commit that
    breaks the line, cannot supply its own baseline: the `as main` line is measured in a
    temporary tree at main's sha, removed after."""
    (box.repo / "check.sh").write_text("echo ok\n")
    _git(box.repo, "add", "check.sh")
    _git(box.repo, "commit", "-q", "-m", "a check")
    main = _git(box.repo, "rev-parse", "main")
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    _git(box.repo, "worktree", "add", "-q", str(wt), "-b", "green-row", "main")
    (wt / "check.sh").write_text("echo BROKEN; exit 3\n")
    _git(wt, "commit", "-q", "-am", "an earlier part")
    _packet(box, "green-row", "`sh check.sh` as main")
    _git(box.repo, "add", "design")
    _git(box.repo, "commit", "-q", "-m", "the packet")
    main = _git(box.repo, "rev-parse", "main")
    before = _trees(box.repo)
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (base,) = box.kind("baseline")
    assert base["pin"] == main and (base["lines"][0]["exit"], base["lines"][0]["last"]) == (0, "ok")
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance")
    assert (row["failing"][0]["exit"], row["failing"][0]["main_exit"]) == (3, 0)
    assert _trees(box.repo) == before


def test_f4_the_pin_tree_goes_on_an_error(box, monkeypatch):
    made = []
    real = unattended.tempfile.mkdtemp
    monkeypatch.setattr(unattended.tempfile, "mkdtemp", lambda **kw: made.append(real(**kw)) or made[-1])
    (box.repo / ".venv").mkdir()
    seen = []

    def boom(wt, lines, env, pick=None):
        seen.append((os.path.realpath(wt), os.path.islink(os.path.join(wt, ".venv")),
                     _git(wt, "rev-parse", "HEAD")))
        raise RuntimeError("boom")
    monkeypatch.setattr(unattended, "run_lines", boom)
    lines = unattended.acceptance(_table("`true` as main"))
    before = _trees(box.repo)
    main = _git(box.repo, "rev-parse", "main")
    with pytest.raises(RuntimeError, match="boom"):
        unattended.pin_baseline(box.repo, main, lines, dict(os.environ))
    ((tree, linked, head),) = seen
    assert linked and head == main and tree.startswith(os.path.realpath(made[0]))
    assert _trees(box.repo) == before and not os.path.exists(made[0])
    got = unattended.pin_baseline(box.repo, None, lines, dict(os.environ))
    assert got[0]["error"] and unattended.judge_line(lines[0], {"exit": 0, "last": "", "cut": False,
                                                                "error": False}, got[0]) == "unrun"


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


def _got(exit, last="", cut=False, error=False):
    return {"exit": exit, "last": last, "cut": cut, "error": error}


def test_f2_exit_126_127_is_unrun():
    """Review F2: a line that exits 126 or 127, at the pin or after the child, could not run:
    `unrun`, an `as main` line too."""
    (main,) = unattended.acceptance(_table("`nosuchtool --check` as main"))
    (zero,) = unattended.acceptance(_table("`nosuchtool --check` exits 127"))
    j = unattended.judge_line
    for code in (126, 127):
        assert j(main, _got(code, "not found"), _got(code, "not found")) == "unrun"
        assert j(main, _got(0, "ok"), _got(code, "not found")) == "unrun"
        assert j(main, _got(code, "not found"), _got(0, "ok")) == "unrun"
    assert j(zero, _got(127, "not found"), None) == "unrun"
    assert j(main, _got(3, "x"), _got(3, "x")) == "same-as-main"


def test_f2_an_as_main_line_that_cannot_run_is_red(box):
    _packet(box, "green-row", "`./no-such-venv/bin/python -c pass` as main")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance")
    (f,) = row["failing"]
    assert (f["status"], f["exit"], f["main_exit"]) == ("unrun", 127, 127)
    assert "`./no-such-venv/bin/python -c pass` could not run (exit 127: " in box.starts[1]["stdin"]


def test_f3_a_cut_line_is_red_whatever_it_expects():
    """Review F3: a line cut at the limit is red, whatever its expectation; an `as main` line
    cut at the pin and after too."""
    j = unattended.judge_line
    for cell in ("`echo 5; sleep 30` reads 5", "`x` reads 5 or more", "`x` under 9",
                 f"`x` exits {unattended.CUT_EXIT}"):
        (ln,) = unattended.acceptance(_table(cell))
        assert j(ln, _got(unattended.CUT_EXIT, "5", cut=True), None) == "red"
    (main,) = unattended.acceptance(_table("`sleep 30` as main"))
    cut = _got(unattended.CUT_EXIT, "", cut=True)
    assert j(main, cut, cut) == "red"
    assert j(main, _got(0, "ok"), cut) == "unrun"


def test_f3_a_cut_line_reading_its_value_is_red(box, monkeypatch):
    _packet(box, "green-row", "`echo 5; sleep 30` reads 5")
    monkeypatch.setattr(unattended, "LINE_LIMIT", 0.5)
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    (f,) = row["failing"]
    assert (row["reason"], f["last"], f["cut"], f["status"]) == ("acceptance", "5", True, "red")


def test_t5_line_env():
    env = unattended.line_env({"PATH": "/bin", "PYTEST_ADDOPTS": "-x", "CLAUDECODE": "1",
                               "RELAY_ROW": "r", "RELAY_DEVICE_VERBS": "none", "HOME": "/live"},
                              "/s", ["origin"])
    assert (env["HOME"], env["XDG_STATE_HOME"], env["TMPDIR"], env["PYTHONPYCACHEPREFIX"]) == (
        "/s", "/s/state", "/s/tmp", "/s/pycache")
    assert env["PYTEST_ADDOPTS"] == "-x -o cache_dir=/s/pytest-cache"           # review F7
    assert env["RELAY_MEASURE_DEPTH"] == "1"
    assert "CLAUDECODE" not in env and "RELAY_ROW" not in env and env["RELAY_DEVICE_VERBS"] == "none"
    assert env["GIT_CONFIG_VALUE_1"] == "relay-denies-push"


def test_f7_pytest_cache_on_and_the_tree_clean(tmp_path):
    """Review F7: the cache plugin stays on, so a test using the `cache` fixture gives the
    gate's verdict; its directory is in the scratch home, so a repo that does not ignore
    `.pytest_cache` stays clean."""
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "test_c.py").write_text("def test_a(cache):\n    cache.set('k', 1)\n\n"
                                    "def test_b():\n    pass\n")
    _git(repo, "add", "test_c.py")
    _git(repo, "commit", "-q", "-m", "a test")
    lines = unattended.acceptance(_table(f"`{sys.executable} -m pytest -q test_c.py` "
                                         "exits 0; `test -d .pytest_cache` exits 1"))
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    got = unattended.run_lines(repo, lines, env)
    assert [unattended.judge_line(ln, g, None) for ln, g in zip(lines, got)] == ["green", "green"]
    assert "2 passed" in got[0]["last"] and unattended._status(repo) == ""


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
