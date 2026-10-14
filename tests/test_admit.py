"""Packet S26: the admission verdict, observed (design/admission-r1.md §3.2, §3.3).

One test per verdict rule (ruling 4) with its text pinned; the peak against a synthetic day
within 1 point of a hand computation; the fit recovering known a and b; the seeds below 20
intervals; the 95th-percentile age-out; `session.admission`'s defaults, an unreadable field
and `enforce` read as `observe`; `admission admit`'s verdict line and its refusals writing
nothing."""
import fcntl
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

import pytest

from claude_session import admission, cli, config, rules

UTC = timezone.utc
SID = "adm-sess-0000-1111"
OTHER = "adm-sess-2222-3333"
WAIT = "admission: not started. The window has no fresh reading yet; retry in a minute."


def iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def at(h: int, m: int = 0, day: int = 12) -> datetime:
    return datetime(2026, 10, day, h, m, tzinfo=UTC)


def reading(t, pct, resets, kind="five_hour", sid=SID, seven=None):
    lim = [{"kind": kind, "percentUsed": pct, "resetsAt": iso(resets)}]
    if seven is not None:
        lim.append({"kind": "seven_day", "percentUsed": seven[0], "resetsAt": iso(seven[1])})
    return {"ts": iso(t), "session": sid, "kind": "reading", "rateLimits": lim}


def start(t, interactive, sid=SID):
    return {"ts": iso(t), "session": sid, "kind": "start", "interactive": interactive, "chain": None}


def spawn(t, aid, model="opus", typ="general-purpose", tid=None, sid=SID, fork=False):
    return {"ts": iso(t), "session": sid, "kind": "spawn", "subagentType": typ, "model": model,
            "parentModel": "claude-opus-5-5", "background": True, "fork": fork,
            "description": None, "tool_use_id": tid or f"toolu_{aid}", "agentId": aid,
            "context": None, "rateLimits": []}


def done(t, aid, minutes, sid=SID):
    return {"ts": iso(t), "session": sid, "kind": "done", "agentId": aid, "tool_use_id": None,
            "durationMs": int(minutes * 60000), "usage": None, "swept": False}


def ask(**kw):
    req = {"subagentType": "general-purpose", "model": "opus", "parentModel": "claude-opus-5-5",
           "background": True, "fork": False, "tool_use_id": "toolu_9", "rateLimits": None,
           "resume": False}
    req.update(kw)
    return req


def decide(rows, now, req=None, session=None):
    return admission.decide(rows, req or ask(), SID, now, rules.admission(session), tz=UTC)


# ---- ruling 4: one test per verdict rule, its text pinned -----------------------------

DEFERRED = ("admission: not started. The five-hour window is at 88% and resets at 14:05. "
            "This spawn projects 7 points, past the ceiling. Do not retry now. It is deferred: "
            "a sitting in this chain is woken when it fits, by 14:06 at the latest. Work in "
            "this thread is fine.")
NOT_STARTED = ("admission: not started. The five-hour window is at 88% and resets at 14:05. "
               "Continue in this thread.")
DENIED = ("admission: not started. The seven-day window is at 98% and resets Mon 00:00. "
          "Spawn nothing more; checkpoint and leave the next step to the owner.")


def test_no_five_hour_reading_is_unread():
    rows = [reading(at(13), 98, at(0, day=19), kind="seven_day")]
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["mode"], v["text"], v["peak"]) == ("unread", "observe", "", None)


def test_a_reading_past_its_reset_is_stale_and_admitted():
    v = decide([reading(at(12, 50), 60, at(13))], at(13, 20))
    assert (v["verdict"], v["text"], v["peak"]) == ("stale", "", None)


def test_stale_waits_while_another_stale_spawn_is_in_flight():
    rows = [reading(at(12, 50), 60, at(13)),
            {"ts": iso(at(13, 15)), "session": OTHER, "kind": "verdict", "tool_use_id": "toolu_8",
             "verdict": "stale", "mode": "observe", "peak": None, "P": None, "T": None,
             "family": "opus", "type": "general-purpose"}]
    # fix round 1, F2: it counts while its spawn runs (past GRACE, a verdict with no run is dropped)
    rows.append(spawn(at(13, 15), "a8", tid="toolu_8", sid=OTHER))
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["text"]) == ("wait", WAIT)
    # once that helper is done, the next spawn is admitted under the stale reading again
    rows.append(done(at(13, 18), "a8", 3, sid=OTHER))
    assert decide(rows, at(13, 20))["verdict"] == "stale"


def test_the_seven_day_ceiling_denies():
    rows = [reading(at(13, 19), 50, at(14, 5), seven=(98, at(0, day=19)))]
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["text"]) == ("denied", DENIED)


def test_the_five_hour_peak_defers_an_interactive_spawn():
    # P 88, T 45: a = 0.10 x 1 thread x 45 = 4.5; the opus spawn 0.15 x 15 = 2.25; 94.75 + 3 > 97
    rows = [start(at(13), True), reading(at(13, 19), 88, at(14, 5))]
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["text"]) == ("deferred", DEFERRED)
    assert v["peak"] == pytest.approx(94.75) and (v["P"], v["T"]) == (88, 45)


def test_the_five_hour_peak_does_not_start_a_print_spawn():
    rows = [start(at(13), False), reading(at(13, 19), 88, at(14, 5))]
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["text"]) == ("not-started", NOT_STARTED)


def test_the_request_s_own_reading_counts():
    lim = [{"kind": "five_hour", "percentUsed": 88, "resetsAt": iso(at(14, 5))}]
    v = decide([start(at(13), True)], at(13, 20), ask(rateLimits=lim))
    assert (v["verdict"], v["text"]) == ("deferred", DEFERRED)


def test_under_the_ceiling_is_admitted_and_the_margin_is_inclusive():
    rows = [start(at(13), True), reading(at(13, 19), 80, at(14, 5))]
    v = decide(rows, at(13, 20))
    assert (v["verdict"], v["text"]) == ("admitted", "") and v["peak"] == pytest.approx(86.75)
    assert decide(rows, at(13, 20), session={"admission": {"ceiling": 89.75}})["verdict"] == "admitted"
    assert decide(rows, at(13, 20), session={"admission": {"ceiling": 89.7}})["verdict"] == "deferred"


# ---- §3.2: the fit and the peak against a synthetic day -------------------------------

A, B_OPUS, B_SONNET = 0.12, 0.20, 0.06
OPUS = [(6, 20), (7, 0), (7, 10), (8, 30), (9, 40), (10, 30), (11, 0), (11, 50), (12, 40)]
SONNET = [(6, 0), (7, 30), (8, 40), (10, 10), (11, 20), (12, 0)]
NOW = at(13)


def synthetic_day(since=at(6)):
    """Readings every 5 minutes from 06:00 to 13:00, a reset at 10:00 (the next at 15:00);
    opus `builder`s live 20 minutes and sonnet `Explore`s 40, one of each still running."""
    helpers = ([(at(h, m), 20, "opus", "builder") for h, m in OPUS]
               + [(at(h, m), 40, "sonnet", "Explore") for h, m in SONNET])
    running = [(at(12, 50), "opus", "builder"), (at(12, 30), "sonnet", "Explore")]
    rows = []
    for i, (t0, life, model, typ) in enumerate(helpers):
        rows.append(spawn(t0, f"h{i}", model, typ))
        if t0 + timedelta(minutes=life) <= NOW:
            rows.append(done(t0 + timedelta(minutes=life), f"h{i}", life))
    for j, (t0, model, typ) in enumerate(running):
        rows.append(spawn(t0, f"r{j}", model, typ))
    spans = [(t0, t0 + timedelta(minutes=life), model) for t0, life, model, _ in helpers]
    spans += [(t0, NOW + timedelta(hours=1), model) for t0, model, _ in running]
    pct, t, reset = 3.0, at(6), at(10)
    while t <= NOW:
        if t == at(10):
            pct, reset = 0.0, at(15)
        if t >= since and t.minute % 5 == 0:
            rows.append(reading(t, round(pct, 1), reset))
        mid = t + timedelta(seconds=30)
        n = {f: sum(1 for s, e, m in spans if m == f and s <= mid < e) for f in ("opus", "sonnet")}
        pct += A + B_OPUS * n["opus"] + B_SONNET * n["sonnet"]
        t += timedelta(minutes=1)
    return sorted(rows, key=lambda r: r["ts"])


def test_the_fit_recovers_a_and_b():
    f = admission.fit(synthetic_day(), NOW, rules.admission(None)["seeds"])
    assert f["intervals"] >= 20 and not f["seeded"]
    assert f["a"] == pytest.approx(A, abs=0.01)
    assert f["b"]["opus"] == pytest.approx(B_OPUS, abs=0.01)
    assert f["b"]["sonnet"] == pytest.approx(B_SONNET, abs=0.01)
    assert f["b"]["haiku"] == 0.02 and f["b"]["fable"] == 0.25   # never seen: the seeds


def test_a_session_that_read_once_and_ended_does_not_halve_a():
    """A respawn: the old sitting's last reading, then its end line. Counted to the end of
    ACTIVE, it doubles m over the last 45 minutes and the refit a falls to about half."""
    rows = synthetic_day()
    last = [r for r in rows if r["kind"] == "reading" and r["ts"] == iso(at(12, 15))][0]
    rows += [{**last, "session": OTHER},
             {"ts": iso(at(12, 16)), "session": OTHER, "kind": "end", "reason": "prompt_input_exit"}]
    f = admission.fit(sorted(rows, key=lambda r: r["ts"]), NOW, rules.admission(None)["seeds"])
    assert f["a"] == pytest.approx(A, abs=0.01)

def test_the_peak_against_a_synthetic_day():
    rows = synthetic_day()
    P = [r for r in rows if r["kind"] == "reading"][-1]["rateLimits"][0]["percentUsed"]
    # By hand at 13:00, T 120: a.T 14.4; the running builder (age 10, L 20) 0.2 x 10 = 2;
    # the running Explore (age 30, L 40) 0.06 x 10 = 0.6; the new builder 0.2 x 20 = 4.
    v = decide(rows, NOW, ask(subagentType="builder"))
    assert v["T"] == 120 and v["P"] == P
    assert abs(v["peak"] - (P + 14.4 + 2 + 0.6 + 4)) <= 1


def test_below_20_intervals_the_seeds_stand():
    seeds = rules.admission(None)["seeds"]
    f = admission.fit(synthetic_day(since=at(11)), NOW, seeds)
    assert f["intervals"] < 20 and f["seeded"]
    assert f["a"] == seeds["a"] and f["b"] == seeds["b"]


@pytest.mark.parametrize("age,counted", [(9, True), (11, False)])
def test_a_helper_past_its_type_s_95th_percentile_life_ages_out(age, counted):
    rows = [reading(NOW - timedelta(minutes=1), 40, NOW + timedelta(hours=2))]
    for i in range(5):
        t0 = at(8, 10 * i)
        rows += [spawn(t0, f"q{i}", "sonnet", "quick"), done(t0 + timedelta(minutes=10), f"q{i}", 10)]
    rows.append(spawn(NOW - timedelta(minutes=age), "q9", "sonnet", "quick"))
    base = decide(rows[:-1], NOW)["peak"]
    # counted: 0.05 x max(10 - 9, 5) = 0.25 points; aged out: none
    assert decide(rows, NOW)["peak"] - base == pytest.approx(0.25 if counted else 0.0)


def test_a_fork_is_its_own_type_and_the_family_falls_back_to_the_parent():
    assert admission.helper_type("general-purpose", True) == "fork"
    assert admission.helper_type(None, False) == "other"
    assert admission.family("inherit", "claude-sonnet-5") == "sonnet"
    assert admission.family(None, None) == "other"
    assert admission.family("claude-opus-5-5", "claude-haiku-4") == "opus"


# ---- the config: session.admission ------------------------------------------------------

DEFAULTS = {"mode": "observe", "ceiling": 97, "margin": 3, "ceiling_7d": 97,
            "seeds": {"a": 0.10, "b": {"opus": 0.15, "sonnet": 0.05, "haiku": 0.02,
                                       "fable": 0.25, "other": 0.15}, "life": 15}}


@pytest.mark.parametrize("session", [None, {}, {"admission": None}, {"admission": 5}])
def test_the_defaults(session):
    assert rules.admission(session) == DEFAULTS


def test_an_unreadable_field_is_its_default():
    got = rules.admission({"admission": {"ceiling": "high", "margin": 5, "ceiling_7d": 120,
                                         "seeds": {"a": True, "b": {"opus": -1, "sonnet": 0.07},
                                                   "life": "long"}}})
    assert (got["ceiling"], got["margin"], got["ceiling_7d"]) == (97, 5, 97)
    assert got["seeds"]["a"] == 0.10 and got["seeds"]["life"] == 15
    assert got["seeds"]["b"] == {**DEFAULTS["seeds"]["b"], "sonnet": 0.07}


def test_enforce_is_refused_and_read_as_observe():
    notes = []
    assert rules.admission({"admission": {"mode": "enforce"}}, notes)["mode"] == "observe"
    assert notes == ["session.admission.mode: enforce is not built yet (S27a); read as observe"]


# ---- the verb: admission admit ----------------------------------------------------------

@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("CLAUDE_SESSION_CHAIN", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    return tmp_path / "xdg"


def adir(state):
    return state / config.APP / "admission"


def lines(state):
    p = adir(state) / "ledger.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()] if p.exists() else []


def run(verb, stdin, sid=SID):
    text = stdin if isinstance(stdin, str) else json.dumps(stdin)
    out, err = io.StringIO(), io.StringIO()
    old, sys.stdin = sys.stdin, io.StringIO(text)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(["admission", verb, "--session", sid])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.stdin = old
    return rc, out.getvalue(), err.getvalue()


def _now_reading(pct=40.0, minutes=60):
    now = datetime.now(UTC)
    return {"kind": "reading", "rateLimits": [{"kind": "five_hour", "percentUsed": pct,
                                               "resetsAt": iso(now + timedelta(minutes=minutes))}]}


def test_admit_appends_one_verdict_line_and_prints_the_answer(state):
    assert run("record", _now_reading())[0] == 0
    rc, out, err = run("admit", ask(tool_use_id="toolu_01"))
    assert (rc, err) == (0, "")
    got = json.loads(out)
    assert list(got) == ["verdict", "mode", "text", "peak"]
    assert (got["verdict"], got["mode"], got["text"]) == ("admitted", "observe", "")
    last = lines(state)[-1]
    assert list(last) == ["ts", "session", "kind", "tool_use_id", "verdict", "mode", "peak",
                          "P", "T", "family", "type"]
    assert (last["kind"], last["session"], last["tool_use_id"], last["verdict"]) == (
        "verdict", SID, "toolu_01", "admitted")
    assert (last["P"], last["family"], last["type"]) == (40.0, "opus", "general-purpose")


def test_admit_reads_the_session_s_resolved_config(state):
    d = state / config.APP / "sessions" / SID
    d.mkdir(parents=True)
    (d / "resolved.json").write_text(json.dumps({"session": {"admission": {"ceiling": 20}}}))
    assert run("record", _now_reading())[0] == 0
    rc, out, _ = run("admit", ask(resume=True, subagentType=None, model=None, parentModel=None))
    assert rc == 0 and json.loads(out)["verdict"] == "not-started"
    assert lines(state)[-1]["family"] == "other"


@pytest.mark.parametrize("sid,stdin", [
    ("../bad", ask()),
    (SID, "not json"),
    (SID, json.dumps([1])),
    (SID, ask(prompt="the whole task")),
    (SID, ask(kind="spawn")),
    (SID, ask(resume="yes")),
    (SID, ask(rateLimits=[{"kind": "five_hour", "percentUsed": "full"}])),
    (SID, ask(model="x" * 129)),
], ids=["sid", "json", "list", "unknown-key", "kind", "resume", "rateLimits", "long-model"])
def test_admit_refuses_and_writes_nothing(state, sid, stdin):
    rc, out, err = run("admit", stdin, sid=sid)
    assert (rc, out) == (2, "") and err.startswith("agentik-session: ")
    assert not (adir(state) / "ledger.jsonl").exists()


def test_admit_under_a_held_lock_exits_3_and_writes_nothing(state, monkeypatch):
    assert run("record", _now_reading())[0] == 0
    before = (adir(state) / "ledger.jsonl").read_text()
    monkeypatch.setattr(admission, "LOCK_WAIT_S", 0.1)
    fd = os.open(adir(state) / "ledger.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        rc, out, err = run("admit", ask())
    finally:
        os.close(fd)
    assert (rc, out) == (3, "") and "locked" in err
    assert (adir(state) / "ledger.jsonl").read_text() == before


# ---- fix round 1: F1 a resetsAt at datetime's end, F2 a stale resume, F3 a held coefficient --

@pytest.mark.parametrize("resets", ["9999-12-31T23:59:30Z", "9999-12-31T23:59:30-08:00", "soon",
                                    "2026-10-12T14:05:00"])
def test_admit_refuses_a_reset_unparseable_or_out_of_range_and_writes_nothing(state, resets):
    assert run("record", {"kind": "start", "interactive": True})[0] == 0
    before = (adir(state) / "ledger.jsonl").read_text()
    lim = [{"kind": "five_hour", "percentUsed": 95, "resetsAt": resets}]
    rc, out, err = run("admit", ask(rateLimits=lim))
    assert (rc, out) == (2, "") and "rateLimits[0].resetsAt" in err
    assert (adir(state) / "ledger.jsonl").read_text() == before


@pytest.mark.parametrize("resets", ["9999-12-31T23:59:30Z", "9999-12-31T23:59:30-08:00"])
def test_a_recorded_reset_out_of_range_is_no_reading(state, resets):
    lim = [{"kind": "five_hour", "percentUsed": 95, "resetsAt": resets},
           {"kind": "seven_day", "percentUsed": 99, "resetsAt": resets}]
    assert run("record", {"kind": "start", "interactive": True})[0] == 0
    assert run("record", {"kind": "reading", "rateLimits": lim})[0] == 0
    rc, out, err = run("admit", ask())
    assert (rc, err) == (0, "") and json.loads(out)["verdict"] == "unread"


@pytest.mark.parametrize("verdict", ["denied", "not-started", "deferred"])
@pytest.mark.parametrize("hours", [0, -8])
def test_the_texts_never_raise_at_datetime_s_end(verdict, hours):
    resets = datetime(9999, 12, 31, 23, 59, 30, tzinfo=timezone(timedelta(hours=hours)))
    got = admission.texts(verdict, 95.0, resets, 5.0, tz=UTC)
    assert got.startswith("admission: not started. The ") and "23:59" in got


def stale(t, tid, sid=OTHER, fam="other", typ="other"):
    return {"ts": iso(t), "session": sid, "kind": "verdict", "tool_use_id": tid, "verdict": "stale",
            "mode": "observe", "peak": None, "P": None, "T": None, "family": fam, "type": typ}


def test_a_stale_resume_counts_only_while_its_helper_runs():
    rows = [spawn(at(12), "a8", sid=OTHER), done(at(12, 30), "a8", 30, sid=OTHER),
            reading(at(12, 50), 60, at(13)), stale(at(13, 15), "toolu_m"),
            {"ts": iso(at(13, 15)), "session": OTHER, "kind": "resume", "to": "a8"}]
    assert decide(rows, at(13, 18))["verdict"] == "wait"          # its target runs
    rows.append(done(at(13, 19), "a8", 4, sid=OTHER))             # the done at +4 min
    got = [decide(rows, at(13, 15) + timedelta(minutes=m))["verdict"] for m in (10, 120, 299)]
    assert got == ["stale", "stale", "stale"]


def test_a_stale_verdict_with_no_run_counts_for_two_minutes():
    rows = [reading(at(12, 50), 60, at(13)), stale(at(13, 15), "toolu_8", fam="opus",
                                                   typ="general-purpose")]
    assert decide(rows, at(13, 17))["verdict"] == "wait"
    assert decide(rows, at(13, 18))["verdict"] == "stale"


def paired_day():
    """Opus `builder`s (20 minutes) and sonnet `Explore`s (25) started together, readings
    every 5 minutes in whole percents: the raw fit puts sonnet below zero."""
    starts = [(6, 0), (7, 30), (8, 40), (10, 10), (11, 20), (12, 0), (12, 45)]
    helpers = [(at(h, m), life, model, typ) for h, m in starts
               for life, model, typ in ((20, "opus", "builder"), (25, "sonnet", "Explore"))]
    rows, spans = [], []
    for i, (t0, life, model, typ) in enumerate(helpers):
        rows.append(spawn(t0, f"p{i}", model, typ))
        end = t0 + timedelta(minutes=life)
        if end <= NOW:
            rows.append(done(end, f"p{i}", life))
        spans.append((t0, end if end <= NOW else NOW + timedelta(hours=1), model))
    pct, t, reset = 3.0, at(6), at(10)
    while t <= NOW:
        if t == at(10):
            pct, reset = 0.0, at(15)
        if t.minute % 5 == 0:
            rows.append(reading(t, float(round(pct)), reset))
        mid = t + timedelta(seconds=30)
        n = {f: sum(1 for s, e, m in spans if m == f and s <= mid < e) for f in ("opus", "sonnet")}
        pct += A + B_OPUS * n["opus"] + B_SONNET * n["sonnet"]
        t += timedelta(minutes=1)
    return sorted(rows, key=lambda r: r["ts"])


def test_a_coefficient_below_zero_is_held_at_its_seed_and_the_rest_refit(monkeypatch):
    rows, seeds = paired_day(), rules.admission(None)["seeds"]
    f = admission.fit(rows, NOW, seeds)
    assert not f["seeded"] and f["b"]["sonnet"] == seeds["b"]["sonnet"]
    assert f["a"] == pytest.approx(A, abs=0.015)
    assert f["b"]["opus"] + f["b"]["sonnet"] == pytest.approx(B_OPUS + B_SONNET, abs=0.03)
    peak = decide(rows, NOW, ask(subagentType="builder"))["peak"]
    true = {"a": A, "b": {**seeds["b"], "opus": B_OPUS, "sonnet": B_SONNET}, "seeded": False}
    monkeypatch.setattr(admission, "fit", lambda *a: true)
    assert abs(peak - decide(rows, NOW, ask(subagentType="builder"))["peak"]) <= 1


def test_admit_puts_the_config_s_notes_in_its_answer_and_on_stderr(state):
    d = state / config.APP / "sessions" / SID
    d.mkdir(parents=True)
    (d / "resolved.json").write_text(json.dumps({"session": {"admission": {"mode": "enforce"}}}))
    assert run("record", _now_reading())[0] == 0
    rc, out, err = run("admit", ask())
    got = json.loads(out)
    assert rc == 0 and (got["mode"], got["notes"]) == ("observe", [rules.ENFORCE])
    assert err == f"agentik-session: {rules.ENFORCE}\n"
