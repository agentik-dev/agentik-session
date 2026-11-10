"""Packet FW1a (design/packets/fw1a-wait-rule.md): the wait rule's text and the charter's reds.

T1 to T9 were red at S53's cba0b70 (20 failed, 3 passed); T10's four cases (R11, a bare
close with no usable record of this session) at S54's d7a3e38 and c1b7359."""
import io
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, cli, resolver, rules

ROOT = Path(__file__).resolve().parents[1]
SECTION = {"ceilings": {"context": 180000, "turns": 400}, "window": 200000,
           "checkpoint_at": 0.8, "charter": {"dir": "history/sittings"}}
HEAD = ("# Sitting 2026-11-09-4: r, c\n\n| item | value |\n|---|---|\n| goal | g |\n"
        "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n"
        "## Done-ness\n- [x] a\n\n## Handover\n- open by level: S2 the remedy\n\n")
FULL = "WAITING 1: the owner's walk; sheet line 12 ticked; by owner; est none"
S4_ROW = "- ready: n12 (agentik-session, S4)"
S2_ROW = "- ready: a2 (agentik-session, S2)"
OWED = "- owed: the merge message; history/sessions/MERGE.txt"
TAKE = ("WAITING while ready: {}; take it, since a wait is legal only when no S1 to S3 row is "
        "ready and nothing is owed")
ITEM_4 = (
    "waiting on an outside party: the Next act says `WAITING <n>: <what>; <how to tell>; by "
    "<who>; est <zoned time|none>`, n the wakes in a row with nothing changed, est the "
    "blocker's own estimate; a wait is legal when no S1 to S3 row is ready and nothing is "
    "owed, and While waiting's S4 rows run only while fill is on; the wake, first that "
    "applies: est within 6 h, a wakeup at est, kept warm before it only on the 1h cache "
    "(item 6); by the owner, no wakeup; else no wakeup and one background task that ends at "
    "est (6 h on when est is none) or when the event's file moves; STALLED is said once, "
    "when a wait by the owner starts, when that task ends with nothing changed, or at n = "
    "{waiting}: the Next act becomes `STALLED: <what>; by <who>; since <when>` in a turn that "
    "ends on text with one PushNotification and no ScheduleWakeup, and after it no wakeup is "
    "armed; a wait never closes the sitting, only the checkpoint does; the charter is brought "
    "current when a wait starts or its line changes, never at each wake (a respawn reads n "
    "from the charter)")
S4 = ("the rest: review notes, polish, refactors, docs; filed in NICE_TO_HAVE.md with its "
      "level, taken on an S3 slice's path, or while fill is on; never ahead of S3")
BUG_3 = ("One S4 item a sitting at most off a slice's path, and only while fill is on; a "
         "review's notes are S4 unless they show harm (S1) or an unmet criterion (S2).")
# Packet FW1b R8 rewords FILL: the verb, who runs it, and its end.
FILL = ("fill, off-path S4 work that uses a window up, is off unless the owner's word turns it "
        "on: the main thread, never a helper, runs agentik session set fill <reset|opus> "
        "--until <zoned time> on an orchestrator's 1M window; it ends then, never past the "
        "week's reset; no memory, ledger or charter turns it on or keeps it")
BLOCK = ("; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest; the Next "
         "act takes the highest ready; pacing: wake in the act's last tool call, a pending "
         "helper is the wake (one fallback, 1800s+), a wait is said and cheap; fill off; "
         "agentik-session rules prints both")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def raw(next_act, *rows):
    body = "".join(r + "\n" for r in rows) or "- none\n"
    return (HEAD + "## While waiting\n" + body + "\n## Next act\n" + next_act + "\n").encode()


def warns(next_act, *rows, session=SECTION):
    return charter.warnings(raw(next_act, *rows), session)


def checked(tmp_path, monkeypatch, next_act, *rows):
    (tmp_path / resolver.REPO_DIR).mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "c.md"
    p.write_bytes(raw(next_act, *rows))
    assert charter.check(p) == []
    return p, run("charter", "check", str(p))


def test_fw1a_s4_rows_are_no_red(tmp_path, monkeypatch):
    assert warns(FULL, S4_ROW) == [] and warns(FULL, S4_ROW, S4_ROW.replace("n12", "n13")) == []
    _, (rc, out, err) = checked(tmp_path, monkeypatch, FULL, S4_ROW)
    assert (rc, out, err) == (0, "", "")


@pytest.mark.parametrize("rows,first", [
    ([S2_ROW], S2_ROW), ([OWED], OWED), ([S4_ROW, S2_ROW], S2_ROW), ([S4_ROW, OWED], OWED),
    ([S2_ROW.replace("S2", "S1")], S2_ROW.replace("S2", "S1")),
    ([S2_ROW.replace("S2", "S3")], S2_ROW.replace("S2", "S3")),
], ids=["s2", "owed", "s4-then-s2", "s4-then-owed", "s1", "s3"])
def test_fw1a_due_rows_are_red(tmp_path, monkeypatch, rows, first):
    got = warns(FULL, *rows)
    assert got == [TAKE.format(first)]
    _, (rc, out, err) = checked(tmp_path, monkeypatch, FULL, *rows)
    assert rc == 1 and out == "" and err.count("warning") == 1
    assert warns(FULL, S4_ROW, "a line")[0] == (
        "WAITING while ready: a line (not a ready or owed shape: fix the line or take it)")


@pytest.mark.parametrize("line,want", [
    (FULL, None),
    ("WAITING 2: CI; the run's status; by the peer in another repo; est 2026-11-09T18:30-08:00", None),
    ("WAITING 2: x; y", "names no '; by <who>; est <zoned time|none>'"),
    ("WAITING 2: x; y; by owner", "names no '; by <who>; est <zoned time|none>'"),
    ("WAITING 2: x; y; by owner; est tomorrow", "est tomorrow is neither a zoned time"),
    ("WAITING 2: x; y; by owner; est 2026-11-09T18:30", "is neither a zoned time"),
    ("WAITING: x", "'WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>'"),
    # R2: no part of FULL holds a `;`.
    ("WAITING 1: a; b; c; by owner; est none", "names no '; by <who>; est <zoned time|none>'"),
    ("WAITING 1: a; b; by ;; est none", "names no '; by <who>; est <zoned time|none>'"),
    ("WAITING 1: x; y; by owner; est 5pm; est none",
     "names no '; by <who>; est <zoned time|none>'"),
    ("WAITING 1: ;; ;; by ;; est none", "names no '; by <who>; est <zoned time|none>'"),
], ids=["full-none", "full-zoned", "old", "no-est", "est-word", "est-no-zone", "misshapen",
        "five-parts", "who-semicolon", "two-ests", "all-semicolons"])
def test_fw1a_line_by_and_est(line, want):
    got = warns(line)
    assert got == [] if want is None else (len(got) == 1 and want in got[0]), got
    assert charter.waiting(line) == (0 if line == "WAITING: x" else int(line.split()[1][:-1]))
    assert warns(line, session={**SECTION, "pacing": {"enabled": False}}) == []


def test_fw1a_stalled(tmp_path, monkeypatch):
    ok = "STALLED: the owner's walk; by owner; since 2026-11-09T10:00-08:00"
    assert charter.stalled(ok) is True and charter.stalled("STALLED:") is False
    assert charter.stalled(FULL) is None and charter.waiting(ok) is None
    assert warns(ok) == [] and warns(ok, S4_ROW) == []
    assert warns(ok, S2_ROW) == [TAKE.format(S2_ROW)]
    for bad in ("STALLED:", "STALLED: the walk", "STALLED: the walk; by owner",
                "STALLED: the walk; since 10:00", "STALLED: ;; by ;; since x",
                "STALLED: a; b; by owner; since x"):
        assert warns(bad) == ["STALLED without its parts: the Next act is not "
                              "'STALLED: <what>; by <who>; since <when>'"], bad
    assert warns("STALLED:", session={**SECTION, "pacing": {"enabled": False}}) == []
    p, (rc, out, err) = checked(tmp_path, monkeypatch, "STALLED:")
    assert rc == 1 and out == "" and "STALLED without its parts" in err
    rc, out, err = run("charter", "close", "--exit", "goal met", str(p))
    assert rc == 0 and out.splitlines()[0] == str(p) and "STALLED without its parts" in err
    assert charter.REDS == ("WAITING while ready", "STALLED without its parts")


@pytest.mark.parametrize("n,w,said", [(3, 3, True), (4, 3, True), (1, 1, True), (2, 3, False)],
                         ids=["at", "past", "at-one", "under"])
def test_fw1a_at_n(n, w, said):
    got = warns(FULL.replace("WAITING 1", f"WAITING {n}"),
                session={**SECTION, "pacing": {"waiting": w}})
    want = (f"WAITING {n} is at session.pacing.waiting ({w}) or past it: say STALLED once, "
            "make the Next act 'STALLED: <what>; by <who>; since <when>' and arm no wakeup; "
            "the sitting stays open")
    assert got == ([want] if said else [])
    assert not any("idle limit" in g or "commit" in g or "never stops the loop" in g for g in got)


def test_fw1a_item_4():
    assert rules.PACE[3] == ITEM_4 and len(rules.PACE) == 5
    out = rules.render({}, ("1h", "within plan usage, 5h 41%"))
    assert f"  4. {ITEM_4.format(waiting=3)}\n" in out
    assert "est within 6 h" in out and "n = 3" in out
    for gone in ("never stops the loop", "legal only when", "brought current and committed",
                 "the longest idle wait the cache allows"):
        assert gone not in out, gone
    assert "n = 2" in rules.render({"pacing": {"waiting": 2}})


def test_fw1a_s4_and_fill(tmp_path):
    assert rules.PRIORITY["levels"]["S4"] == S4 and len(S4) <= rules.TEXT_MAX
    assert rules.BUGS[2] == BUG_3 and rules.FILL == FILL
    env = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state")}
    assert resolver.resolve(tmp_path, "t", env).sections["session"]["priority"] == rules.PRIORITY
    out = rules.render({})
    assert f"  S4 {S4}\n" in out and f"  - {BUG_3}\n  - {FILL}\n" in out
    assert "nothing ready" not in out and "none ready" not in out
    assert FILL not in rules.render({"priority": {"enabled": False}})


def test_fw1a_clause():
    assert rules.clause({}) == BLOCK and len(BLOCK.encode()) == 276
    line = rules.clause({}, "1h")
    assert line.endswith("a wait is said and cheap; fill off, cache 1h: idle wakes <=3300s; "
                         "agentik-session rules prints both")
    assert len(line.encode()) == 306 <= rules.BLOCK_MAX
    assert "fill" not in rules.clause({"pacing": {"enabled": False}})


def test_fw1a_docs(tmp_path):
    for rel in ("plugin/skills/session/SKILL.md", "RUNBOOK.md", "README.md",
                "design/readme/source.md"):
        flat = " ".join((ROOT / rel).read_text().split())
        assert "STALLED" in flat and "est <zoned time|none>" in flat, rel
        for gone in ("never stops the loop", "no wait stops the loop", "legal only when",
                     "at every commit", "brought current and committed"):
            assert gone not in flat, (rel, gone)
    seeded = charter.open(tmp_path, "g", SECTION, "abc1234", repo="r").read_text()
    assert "at every commit" not in seeded and "when a wait starts or its line changes" in seeded


SID_A = "aaaaaaaa-0000-0000-0000-000000000001"
SID_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _start(sid, cwd):
    """A session's dir with its request.json, as SessionStart leaves it."""
    sdir = resolver.session_dir(resolver.state_dir(os.environ), sid)
    sdir.mkdir(parents=True)
    resolver.save_request(sdir, cwd, None, None)


def _open(monkeypatch, sid, cwd, goal):
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", sid)
    rc, out, err = run("charter", "open", goal)
    assert rc == 0, err
    return Path(cwd) / out.strip()


@pytest.mark.parametrize("case", ["no-session-dir", "parent-dir", "other-repo", "helper-mark"])
def test_fw1a_bare_close_refuses_a_guess(tmp_path, monkeypatch, case):
    """R11 (the S54 review's F1, hq probe p1 cases c3 to c6): sitting A closes bare while B's
    charter of the same suffix is today's newest. With no usable record of A's (no session
    dir; a session started in a parent directory, so its open recorded nothing; a helper's
    mark) and two charters of the suffix, or with a record naming a file outside this
    directory's sittings (a Bash in another repo), the close refuses, exit 2, naming the
    files and `close <file>`, and writes nothing."""
    for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE",
              "CLAUDE_SESSION_HELPER", "RELAY_ROW"):
        monkeypatch.delenv(k, raising=False)
    repo = tmp_path / "parent" / "repo"
    repo.mkdir(parents=True)
    if case == "parent-dir":
        _start(SID_A, tmp_path / "parent")
        _start(SID_B, repo)
    elif case == "helper-mark":
        _start(SID_A, repo)
    if case == "other-repo":
        x = tmp_path / "x"
        x.mkdir()
        _start(SID_A, x)
        _start(SID_B, repo)
        a = _open(monkeypatch, SID_A, x, "A goal")
    else:
        a = _open(monkeypatch, SID_A, repo, "A goal")
    b = _open(monkeypatch, SID_B, repo, "B goal")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID_A)
    if case == "helper-mark":
        monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    snap = {p: p.read_bytes() for p in (a, b)}
    rc, out, err = run("charter", "close", "--exit", "A is done")
    assert (rc, out) == (2, ""), (rc, out, err)
    assert b.name in err and err.rstrip().endswith("name the file: charter close <file>"), err
    assert case == "other-repo" or a.name in err
    assert {p: p.read_bytes() for p in (a, b)} == snap
    # With one charter of the suffix the bare close takes it, as before R11.
    b.unlink()
    if case == "other-repo":
        rc, out, err = run("charter", "close", "--exit", "A is done")
        assert rc == 2 and str(a) in err, err
        return
    rc, out, err = run("charter", "close", "--exit", "A is done")
    assert rc == 0 and out.splitlines()[0] == f"history/sittings/{a.name}", err
    assert "exit taken: A is done" in a.read_text()
