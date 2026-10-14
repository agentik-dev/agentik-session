"""Packet S27b: the admission meter shown (design/admission-r1.md §3.5, §3.6, §5).

`band()` on a synthetic ledger against a hand count; `band.json` rewritten by `record` and
by `admit`, atomic and 0600, inside the lock; `band_line` pinned at 80 columns, each part
left out when absent, `no reading`, `observe`, the age; the line Python and the module draw
from one shared fixture; the prompt hook's line with and without the file; `report`'s
window rows (`held`, `idle`, `under 90`) and `no ledger`."""
import fcntl
import io
import json
import os
import re
import stat
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, cli, config, hooks, ledger, rules

UTC = timezone.utc
SID = "test-sess-0000-1111-2222"
ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "plugin" / "hooks"


def iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def at(h: int, m: int = 0, s: int = 0) -> datetime:
    return datetime(2026, 10, 12, h, m, s, tzinfo=UTC)


def reading(t, pct, resets, seven=None, sid=SID):
    lim = [{"kind": "five_hour", "percentUsed": pct, "resetsAt": iso(resets)}]
    if seven is not None:
        lim.append({"kind": "seven_day", "percentUsed": seven, "resetsAt": iso(at(23) + timedelta(days=3))})
    return {"ts": iso(t), "session": sid, "kind": "reading", "rateLimits": lim}


def spawn(t, aid, typ="general-purpose", model=None):
    return {"ts": iso(t), "session": SID, "kind": "spawn", "subagentType": typ, "model": model,
            "parentModel": "claude-opus-5-5", "background": True, "fork": False,
            "description": None, "tool_use_id": f"toolu_{aid}", "agentId": aid,
            "context": None, "rateLimits": []}


def done(t, aid, minutes):
    return {"ts": iso(t), "session": SID, "kind": "done", "agentId": aid, "tool_use_id": None,
            "durationMs": int(minutes * 60000), "usage": None, "swept": False}


def verdict(t, v):
    return {"ts": iso(t), "session": SID, "kind": "verdict", "tool_use_id": None, "verdict": v,
            "mode": "observe", "peak": None, "P": None, "T": None, "family": "opus",
            "type": "general-purpose"}


RESETS = at(14, 5)
NOW = at(12, 53)


def synthetic():
    return [
        spawn(at(11), "x1", typ="Explore", model="sonnet"), done(at(11, 10), "x1", 10),
        verdict(at(9), "deferred"),                  # before the window's start: not counted
        reading(at(12), 60, RESETS),
        reading(at(12, 20), 72, RESETS, seven=41),
        verdict(at(12, 25), "deferred"), verdict(at(12, 26), "wait"), verdict(at(12, 27), "admitted"),
        spawn(at(12, 30), "h1"), spawn(at(12, 50), "h2"),
    ]


def test_band_on_a_synthetic_ledger_matches_a_hand_count():
    b = admission.band(synthetic(), NOW, rules.admission({}), tz=UTC)
    T = 72.0                                         # 12:53 to 14:05
    a, b_opus, life = 0.10, 0.15, 15                 # the seeds: one interval, under 20
    rise = a * 1 * T                                 # one main thread read in the last 45 min
    rise += b_opus * min(T, max(life - 23, 5))       # h1, 23 minutes old: the 5-minute floor
    rise += b_opus * min(T, max(life - 3, 5))        # h2, 3 minutes old
    peak = 72 + rise                                 # 81.75
    each = b_opus * min(T, life)                     # one more opus general-purpose spawn
    room = 0
    while peak + (room + 1) * each + 3 <= 97:
        room += 1
    assert (round(peak, 2), room) == (81.75, 5)
    assert b == {"P": 72, "peak": 81.75, "ceiling": 97, "resetsAt": "2026-10-12T14:05:00+00:00",
                 "until": "2026-10-12T14:05:00+00:00", "bound": "five_hour", "running": 2, "room": room, "deferred": 2, "P7": 41, "mode": "observe",
                 "at": iso(NOW)}


def test_room_is_never_below_zero():
    rows = [reading(at(12, 50), 95, RESETS), spawn(at(12, 51), "h1")]
    assert admission.band(rows, NOW, rules.admission({}), tz=UTC)["room"] == 0


@pytest.mark.parametrize("rows", [[], [reading(at(9), 50, at(10))]], ids=["none", "past-reset"])
def test_no_five_hour_reading_is_mode_and_at_only(rows):
    assert admission.band(rows, NOW, rules.admission({}), tz=UTC) == {"mode": "observe",
                                                                         "at": iso(NOW)}


# ---- band.json: rewritten by record and by admit, atomic, 0600, inside the lock ----

def env():
    return dict(os.environ)


def adir() -> Path:
    return config.state_dir(os.environ) / "admission"


def band_file() -> dict:
    return json.loads((adir() / "band.json").read_text())


def record(obj, now):
    return admission.record(SID, json.dumps(obj), env(), now)


def lim(pct, resets=RESETS):
    return [{"kind": "five_hour", "percentUsed": pct, "resetsAt": iso(resets)}]


def test_record_rewrites_band_json_atomically_and_0600():
    record({"kind": "start", "interactive": True}, at(12))
    assert band_file() == {"mode": "observe", "at": iso(at(12))}
    ino = (adir() / "band.json").stat().st_ino
    record({"kind": "reading", "rateLimits": lim(72)}, at(12, 1))
    b = band_file()
    assert (b["P"], b["at"], b["running"], b["deferred"]) == (72, iso(at(12, 1)), 0, 0)
    p = adir() / "band.json"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert p.stat().st_ino != ino                    # replaced by a rename, never rewritten in place
    assert sorted(x.name for x in adir().iterdir()) == ["band.json", "ledger.jsonl", "ledger.lock"]


def test_admit_rewrites_band_json_with_its_verdict():
    record({"kind": "start", "interactive": True}, at(12))
    record({"kind": "reading", "rateLimits": lim(95)}, at(12, 1))
    out = admission.admit(SID, json.dumps({"model": "opus", "rateLimits": lim(95)}), env(), at(12, 2))
    assert out["verdict"] == "deferred"
    b = band_file()
    assert (b["deferred"], b["at"], b["room"]) == (1, iso(at(12, 2)), 0)


def test_a_held_lock_writes_no_band_json():
    adir().mkdir(parents=True, mode=0o700)
    fd = os.open(adir() / "ledger.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with pytest.raises(admission.AdmissionError) as e:
            record({"kind": "start", "interactive": True}, at(12))
        assert e.value.code == 3
    finally:
        os.close(fd)
    assert not (adir() / "band.json").exists()


# ---- band_line: pinned at 80 columns; parts left out; no reading; observe; age ----

FULL = {"P": 72, "peak": 91.2, "ceiling": 97, "resetsAt": "2026-10-12T14:05:00+00:00",
        "running": 3, "room": 2, "deferred": 1, "P7": 41, "mode": "observe",
        "at": "2026-10-12T12:52:30+00:00"}
LINE = ("5h 72% → 91% · ceiling 97 · resets 14:05 (1h12) · 3 helpers, room for 2 · "
        "1 deferred · 7d 41% · observe")


def test_band_line_is_pinned_at_80_columns():
    line = admission.band_line(FULL, NOW, 80)
    assert line == "5h 72% → 91% · ceiling 97 · resets 14:05 (1h12) · 3 helpers, room for 2 · 1 def…"
    assert len(line) == 80
    assert admission.band_line(FULL, NOW) == LINE


@pytest.mark.parametrize("key,line", [
    ("peak", LINE.replace(" → 91%", "")),
    ("ceiling", LINE.replace(" · ceiling 97", "")),
    ("resetsAt", LINE.replace(" · resets 14:05 (1h12)", "")),
    ("running", LINE.replace("3 helpers, ", "")),
    ("room", LINE.replace(", room for 2", "")),
    ("deferred", LINE.replace(" · 1 deferred", "")),
    ("P7", LINE.replace(" · 7d 41%", "")),
    ("mode", LINE.replace(" · observe", "")),
])
def test_each_part_is_left_out_when_absent(key, line):
    assert admission.band_line({k: v for k, v in FULL.items() if k != key}, NOW) == line


def test_one_helper_and_enforce_and_a_bad_reset():
    b = {**FULL, "running": 1, "mode": "enforce", "resetsAt": "14:05"}
    assert admission.band_line(b, NOW) == ("5h 72% → 91% · ceiling 97 · 1 helper, room for 2 · "
                                           "1 deferred · 7d 41%")


def test_no_reading():
    assert admission.band_line({"mode": "observe", "at": iso(NOW)}, NOW) == "5h no reading · observe"


def test_the_age_past_120_s():
    assert admission.band_line({**FULL, "at": iso(NOW - timedelta(seconds=120))}, NOW) == LINE
    old = admission.band_line({**FULL, "at": iso(NOW - timedelta(seconds=300))}, NOW)
    assert old == LINE + " · 300s old"


def _fixture() -> tuple:
    """The one fixture both twins read: the module's test (its name spelled in pieces, as
    test_admission's reader is: test_mod's criterion 5 reads a quoted suffix as a reader)."""
    p = HOOKS_DIR / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = p.read_text()
    band = re.search(r"^const BAND = '(.*)'$", text, re.M).group(1)
    line = re.search(r"^const BAND_LINE = '(.*)'$", text, re.M).group(1)
    now = re.search(r"^const NOW = Date\.parse\('(.*)'\)$", text, re.M).group(1)
    return json.loads(band), line, datetime.fromisoformat(now)


def test_python_draws_the_module_s_fixture_line():
    band, line, now = _fixture()
    assert admission.band_line(band, now) == line


# ---- the prompt line: band_line from band.json, after the budget line; display only ----

def _context(out: dict) -> list:
    """The context's bits, less the cadence nudge (its count moves with every prompt)."""
    bits = out["hookSpecificOutput"]["additionalContext"].split("\n\n") if out else []
    return [x for x in bits if "since the last checkpoint" not in x]


def test_the_prompt_hook_adds_the_band_line_after_the_budget_line(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    without = _context(hooks.user_prompt_submit({"session_id": SID}))
    assert without and not any(x.startswith("5h ") for x in without)
    now = datetime.now(UTC)
    record({"kind": "reading", "rateLimits": lim(72, now + timedelta(hours=2))}, now)
    with_ = _context(hooks.user_prompt_submit({"session_id": SID}))
    [line] = [x for x in with_ if x.startswith("5h ")]
    assert line.startswith("5h 72% → ") and line.endswith(" · observe")
    assert [x for x in with_ if x != line and not x.startswith("cache ")] == without   # S30
    assert with_.index(line) == len(without)         # after the budget line


def test_the_prompt_hook_adds_nothing_without_a_readable_file(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    without = _context(hooks.user_prompt_submit({"session_id": SID}))
    adir().mkdir(parents=True, mode=0o700)
    (adir() / "band.json").write_text("{not json")
    assert _context(hooks.user_prompt_submit({"session_id": SID})) == without
    (adir() / "band.json").write_text("[1, 2]")
    assert _context(hooks.user_prompt_submit({"session_id": SID})) == without


# ---- S30: the prompt line names the prompt cache's lifetime, after the band line ----

S30_1H = "cache 1h (within plan usage, 5h 72%): an idle wake waits at most 3300 s, so the cache survives"
S30_5M = ("cache 5m ({why}): a wait past about 270 s misses anyway; an idle wait takes the long "
          "fallback, never an early wake to keep the cache")


def test_s30_the_prompt_line_names_the_lifetime_after_the_band_line(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    now = datetime.now(UTC)
    record({"kind": "reading", "rateLimits": lim(72, now + timedelta(hours=2))}, now)
    bits = _context(hooks.user_prompt_submit({"session_id": SID}))
    [line] = [x for x in bits if x.startswith("5h ")]
    assert bits[bits.index(line) + 1:] == [S30_1H]
    record({"kind": "reading", "rateLimits": lim(100, now + timedelta(hours=2))},
           now + timedelta(seconds=1))
    bits = _context(hooks.user_prompt_submit({"session_id": SID}))
    assert bits[-1] == S30_5M.format(why="past plan usage, 5h 100%")


def test_s30_the_prompt_line_without_a_lifetime_or_with_pacing_off(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    bits = _context(hooks.user_prompt_submit({"session_id": SID}))
    assert bits and not any(x.startswith("cache ") for x in bits)       # unknown: nothing
    monkeypatch.setenv("CLAUDE_CODE_PROMPT_CACHE_TTL", "5m")
    bits = _context(hooks.user_prompt_submit({"session_id": SID}))
    assert [x for x in bits if x.startswith("cache ")] == [
        S30_5M.format(why="CLAUDE_CODE_PROMPT_CACHE_TTL")]              # no band, an override
    sdir = config.state_dir(os.environ) / "sessions" / SID
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "resolved.json").write_text(json.dumps({"session": {"pacing": {"enabled": False}}}))
    bits = _context(hooks.user_prompt_submit({"session_id": SID}))
    assert bits and not any(x.startswith("cache ") for x in bits)       # pacing off: nothing


def test_s30_f1_project_settings_come_from_the_project_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    now = datetime.now(UTC)
    record({"kind": "reading", "rateLimits": lim(72, now + timedelta(hours=2))}, now)
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text(json.dumps({"promptCacheTtl": "5m"}))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))      # Claude's `cd` moves only cwd
    bits = _context(hooks.user_prompt_submit({"session_id": SID, "cwd": str(repo / "sub")}))
    assert bits[-1] == S30_5M.format(why="promptCacheTtl, project settings")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")                 # unset: the payload's cwd
    bits = _context(hooks.user_prompt_submit({"session_id": SID, "cwd": str(repo)}))
    assert bits[-1] == S30_5M.format(why="promptCacheTtl, project settings")
    bits = _context(hooks.user_prompt_submit({"session_id": SID, "cwd": str(repo / "sub")}))
    assert bits[-1] == S30_1H


# ---- report's window use: held, idle, under 90; no ledger ----

def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _write(name: str, rows: list) -> None:
    adir().mkdir(parents=True, exist_ok=True, mode=0o700)
    (adir() / name).write_text("".join(json.dumps(r) + "\n" for r in rows))


def _windows() -> list:
    _write("ledger.1.jsonl", [reading(at(5), 80, at(9, 5)), reading(at(8), 95, at(9, 5)),
                              verdict(at(8, 30), "wait")])
    _write("ledger.jsonl", [reading(at(12), 60, at(14, 5)), verdict(at(12, 10), "deferred"),
                            reading(at(13), 72, at(14, 5)), reading(at(15), 40, at(19, 5)),
                            verdict(at(15, 5), "admitted")])
    rc, out, err = run("report")
    return [ln.split() for ln in out.splitlines()[out.splitlines().index("admission: five-hour windows") + 1:]]


def test_report_prints_each_window_held_or_idle_and_under_90():
    rows = _windows()
    assert [r[2:] for r in rows] == [["95%", "held"], ["72%", "held", "under", "90"],
                                     ["40%", "idle", "under", "90"]]


def test_report_with_a_session_ledger_keeps_its_table_and_exit():
    ledger.append(config.state_dir(os.environ), {"session": "s1", "ended": "2026-10-12T01:00:00+00:00"})
    rc, out, _ = run("report")
    assert rc == 0 and out.splitlines()[-1] == "admission: no ledger" and "s1" in out
    rc, out, _ = run("report", "--json")
    assert rc == 0 and "admission" not in out


def test_report_with_no_admission_ledger():
    rc, out, err = run("report")
    assert rc == 2 and out == "admission: no ledger\n" and err.startswith("the ledger is empty")


# ---- fix round 1: F1 same-second pairs, F2 room's bounds, F4 the file's kind, F5 one window ----

def test_two_spawns_in_one_second_still_rewrite_band_json():
    record({"kind": "reading", "rateLimits": lim(50)}, at(12))
    for tid in ("t1", "t2"):
        record({"kind": "spawn", "parentModel": "claude-opus-5-5", "tool_use_id": tid}, at(12, 0, 10))
    record({"kind": "reading", "rateLimits": lim(60)}, at(12, 0, 40))
    assert (band_file()["P"], band_file()["at"]) == (60, iso(at(12, 0, 40)))
    rows = [reading(at(12, 50), 72, RESETS), spawn(at(12, 51), "h1"), spawn(at(12, 51), "h2")]
    assert admission.band(rows, NOW, rules.admission({}), tz=UTC)["running"] == 2


def test_two_resumes_in_one_second_find_the_stale_run():
    t = at(12)
    rows = [{"ts": iso(t), "session": SID, "kind": "resume", "to": "a1"},
            {"ts": iso(t), "session": SID, "kind": "resume", "to": "a2"}]
    run_ = {"agentId": "a1", "tool_use_id": None, "start": at(11)}
    v = {"session": SID, "family": "other", "type": "other", "tool_use_id": None}
    assert admission._stale_run(rows, [run_], v, t) is run_


def test_a_band_that_cannot_be_written_says_so_on_one_stderr_line(monkeypatch, capsys):
    def boom(*a, **k):
        raise TypeError("two\nlines")
    monkeypatch.setattr(admission, "band", boom)
    record({"kind": "start", "interactive": True}, at(12))
    err = capsys.readouterr().err
    assert len(err.splitlines()) == 1 and "band.json" in err
    assert (adir() / "ledger.jsonl").exists() and not (adir() / "band.json").exists()


@pytest.mark.parametrize("secs", [59, 5, 0.5])
def test_no_room_is_computed_under_a_minute_from_the_reset(secs):
    resets = (NOW + timedelta(seconds=secs)).isoformat()
    rows = [{"ts": iso(NOW - timedelta(minutes=1)), "session": SID, "kind": "reading",
             "rateLimits": [{"kind": "five_hour", "percentUsed": 50, "resetsAt": resets}]}]
    assert admission.band(rows, NOW, rules.admission({}), tz=UTC)["room"] is None


@pytest.mark.parametrize("b", [1e-22, 1e-310, 1e-3])
def test_room_is_capped_and_never_overflows(b):
    cfg = rules.admission({"admission": {"seeds": {"b": {"opus": b}}}})
    out = admission.band([reading(at(12, 50), 50, at(14, 50))], NOW, cfg, tz=UTC)
    assert out["room"] == admission.ROOM_CAP == 99
    assert json.loads(json.dumps(out, allow_nan=False))["room"] == 99


def test_the_prompt_line_reads_only_a_small_regular_file():
    import threading
    adir().mkdir(parents=True, mode=0o700)
    p = adir() / "band.json"
    os.mkfifo(p, 0o600)
    got: list = []
    th = threading.Thread(target=lambda: got.append(hooks._admission_line()), daemon=True)
    th.start()
    th.join(3)
    if th.is_alive():                                # unblock the reader before failing
        os.close(os.open(p, os.O_WRONLY | os.O_NONBLOCK))
        th.join(3)
        pytest.fail("a FIFO at band.json blocked the prompt line")
    assert got == [None]
    p.unlink()
    p.write_text(json.dumps(FULL) + " " * (64 * 1024))
    assert hooks._admission_line() is None
    p.write_text(json.dumps(FULL))
    assert hooks._admission_line().startswith("5h 72% → 91%")


def test_a_verdict_at_a_reset_holds_only_the_next_window():
    rows = [reading(at(9, 30), 95, at(14)), verdict(at(14), "wait"), reading(at(15), 92, at(19))]
    assert [w["held"] for w in admission.windows(rows)] == [False, True]


def test_overlapping_windows_take_a_verdict_once():
    rows = [reading(at(10), 95, at(14)), reading(at(13, 40), 50, at(18, 30)),
            verdict(at(13, 45), "wait")]
    assert [w["held"] for w in admission.windows(rows)] == [True, False]


# ---- a main thread runs from its reading to its end line (the observer, 2026-10-13) ----

def end(t, sid):
    return {"ts": iso(t), "session": sid, "kind": "end", "reason": "prompt_input_exit"}


OTHER = "test-sess-3333-4444-5555"


def test_an_ended_session_is_not_a_running_main_thread():
    rows = [reading(at(12, 20), 72, RESETS), reading(at(12, 30), 72, RESETS, sid=OTHER),
            end(at(12, 31), OTHER)]
    b = admission.band(rows, NOW, rules.admission({}), tz=UTC)
    assert b["peak"] == round(72 + 0.10 * 1 * 72.0, 2)       # SID alone: 79.2


def test_a_resumed_session_reads_again_and_runs_again():
    rows = [reading(at(12, 20), 72, RESETS), reading(at(12, 30), 72, RESETS, sid=OTHER),
            end(at(12, 31), OTHER), reading(at(12, 40), 72, RESETS, sid=OTHER)]
    b = admission.band(rows, NOW, rules.admission({}), tz=UTC)
    assert b["peak"] == round(72 + 0.10 * 2 * 72.0, 2)       # both: 86.4


# ---- the horizon's bound (the owner, 2026-10-14 06:43): the weekly reset, when first ----

def _week_rows(seven_in: float, P: float = 72, five_in: float = 226) -> list:
    """P at 12:50, the five-hour reset `five_in` minutes after NOW, the seven-day one `seven_in`."""
    lim = [{"kind": "five_hour", "percentUsed": P, "resetsAt": iso(NOW + timedelta(minutes=five_in))},
           {"kind": "seven_day", "percentUsed": 41, "resetsAt": iso(NOW + timedelta(minutes=seven_in))}]
    return [{"ts": iso(at(12, 50)), "session": SID, "kind": "reading", "rateLimits": lim}]


def test_the_band_fills_by_a_seven_day_reset_that_comes_first():
    b = admission.band(_week_rows(77), NOW, rules.admission({}), tz=UTC)
    # T 77: one main thread, a 0.10 x 77 = 7.7; room: 79.7 + n x 0.15 x 15 + 3 <= 97, n = 6
    assert (b["P"], b["peak"], b["room"], b["P7"]) == (72, 79.7, 6, 41)
    # resetsAt stays the five-hour reset (the pacing rule wakes there: fix round F3)
    assert (b["resetsAt"], b["until"], b["bound"]) == ("2026-10-12T16:39:00+00:00",
                                                       "2026-10-12T14:10:00+00:00", "seven_day")


def test_the_band_keeps_the_five_hour_reset_when_the_seven_day_one_is_later():
    b = admission.band(_week_rows(300), NOW, rules.admission({}), tz=UTC)
    assert (b["peak"], b["resetsAt"], b["until"], b["bound"]) == (
        94.6, "2026-10-12T16:39:00+00:00", "2026-10-12T16:39:00+00:00", "five_hour")


@pytest.mark.parametrize("P,room", [(95, 0), (50, 19)])
def test_f2_room_near_the_weekly_reset_costs_each_spawn_over_the_five_hour_window(P, room):
    """Fix round F2: the week resets in 2 minutes, the five-hour window in 150. a·T runs to
    the week (0.10 x 2 = 0.2); each spawn costs 0.15 x min(150, 15) = 2.25, not 0.15 x 2.
    P 50: 50.2 + 2.25 n + 3 <= 97 gives 19, where the week-costed spawn gave 99."""
    b = admission.band(_week_rows(2, P=P, five_in=150), NOW, rules.admission({}), tz=UTC)
    assert (b["bound"], b["peak"], b["room"]) == ("seven_day", round(P + 0.2, 2), room)


def test_the_band_line_says_week_resets_when_the_seven_day_reset_bounds_it():
    week = admission.band_line({**FULL, "until": "2026-10-12T14:00:00+00:00", "bound": "seven_day"}, NOW)
    assert week == LINE.replace(" · resets 14:05 (1h12)", " · week resets 14:00 (1h07), 5h 14:05")
    five = {**FULL, "until": FULL["resetsAt"], "bound": "five_hour"}
    assert admission.band_line(five, NOW) == LINE
    # a seven-day bound with no readable until: the five-hour reset as before
    assert admission.band_line({**FULL, "bound": "seven_day"}, NOW) == LINE


def test_python_draws_the_module_s_week_fixture_line():
    _, _, now = _fixture()
    text = (HOOKS_DIR / ("session.test." + "ts")).read_text()
    band = re.search(r"^const BAND_WEEK = '(.*)'$", text, re.M).group(1)
    line = re.search(r"^const BAND_WEEK_LINE = '(.*)'$", text, re.M).group(1)
    assert "week resets" in line and admission.band_line(json.loads(band), now) == line
