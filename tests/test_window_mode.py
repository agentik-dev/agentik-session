"""Packet S42: a window mode per account. A login whose readings show no five-hour window
while its week rises stops pacing against five hours; every five-hour behaviour stays for
one that has it, but the four mode-free fixes. No test depends on real time: every `now`
is passed in."""
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, cli, config, hooks, measure, resolver, rules, yamlsubset

UTC = timezone.utc
NOW = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
WEEK = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)         # a Friday
OTHER = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)        # a Wednesday, another login
FIVE = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
KEY, KEY2 = "2026-11-06T21:00Z", "2026-11-04T15:00Z"
SID, S2, S3, FRESH = "sess-a-0000", "sess-b-1111", "sess-c-2222", "sess-f-3333"


def iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def at(minutes_ago: float) -> datetime:
    return NOW - timedelta(minutes=minutes_ago)


def L7(p7, week=WEEK):
    return [{"kind": "seven_day", "percentUsed": p7, "resetsAt": iso(week)}]


def L5(p5, p7=None, five=FIVE, week=WEEK):
    out = [{"kind": "five_hour", "percentUsed": p5, "resetsAt": iso(five)}]
    return out + (L7(p7, week) if p7 is not None else [])


def reading(t, lims, sid=SID):
    return {"ts": iso(t), "session": sid, "kind": "reading", "rateLimits": lims}


def spawn(t, aid, lims=None, sid=SID):
    return {"ts": iso(t), "session": sid, "kind": "spawn", "subagentType": "general-purpose",
            "model": None, "parentModel": "claude-opus-5-5", "background": True, "fork": False,
            "description": None, "tool_use_id": f"toolu_{aid}", "agentId": aid,
            "context": None, "rateLimits": lims if lims is not None else []}


def settings(**ad):
    return rules.admission({"admission": ad} if ad else {})


def window(rows, key=KEY, now=NOW, **ad):
    return admission.window(rows, key, now, settings(**ad))


def rising(p0=40.0, p1=41.0, sid=SID):
    """One session, its week up a point across 31 minutes: the rule's plain case."""
    return [reading(at(61), L7(p0), sid), reading(at(45), L7(p0), sid), reading(at(30), L7(p1), sid)]


def ask(**kw):
    return {"subagentType": "general-purpose", "parentModel": "claude-opus-5-5", **kw}


def decide(rows, req=None, sid=SID, now=NOW, **ad):
    return admission.decide(rows, req if req is not None else ask(), sid, now, settings(**ad), tz=UTC)


# ---- §3: the rule, each clause ----------------------------------------------------------

def test_window_none_on_one_session_rising():
    assert window(rising()) == "none"
    assert window(rising(), key=KEY2) == "five_hour"                     # another login has no pair


@pytest.mark.parametrize("rows", [
    [reading(at(61), L7(40)), reading(at(32), L7(41))],                  # 29 minutes apart
    [reading(at(61), L7(40)), reading(at(30), L7(40.9))],                # under a whole point
    [reading(at(61), L7(41)), reading(at(30), L7(40))],                  # falling
    [reading(at(61), L7(40))],                                           # one observation
    [],
], ids=["29-minutes", "under-a-point", "falling", "one", "empty"])
def test_window_short_of_the_rule_stays_five_hour(rows):
    assert window(rows) == "five_hour"


def test_window_exactly_thirty_minutes_and_one_point_fires():
    assert window([reading(at(60), L7(40)), reading(at(30), L7(41))]) == "none"


def test_window_none_across_sessions_is_not_none():
    """The refuter's sequence, F1: an idle Max login's lists differ across sessions while
    nothing has moved; each session's list moves only on that session's own responses."""
    T = lambda h, m: datetime(2026, 10, 30, h, m, tzinfo=UTC)
    rows = [reading(T(11, 40), L5(50, 40, five=T(12, 0)), "A"),
            reading(T(11, 50), L5(55, 41, five=T(12, 0)), "B"),
            reading(T(11, 58), L5(60, 42, five=T(12, 0)), "C"),
            reading(T(12, 1), L7(40), "A"), reading(T(12, 10), L7(41), "B"),
            reading(T(12, 31), L7(42), "C")]
    assert window(rows, now=T(12, 40)) == "five_hour"


def test_window_fires_on_a_sparse_cadence():
    """Any pair 30 minutes apart, not the newest three, which rarely span 30 (F2)."""
    rows = [reading(at(120), L7(40))] + [reading(at(13 - i), L7(41)) for i in range(6)]
    assert window(rows) == "none"


def test_window_five_hour_null_percent_counts():
    """A list carrying five_hour, whatever its percent, through the real record."""
    env = dict(os.environ)
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": L7(40)}), env, at(61))
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": L7(41)}), env, at(30))
    d = admission.directory(env) / admission.LEDGER
    assert window(admission._rows(d)) == "none"
    null = [{"kind": "five_hour", "percentUsed": None, "resetsAt": iso(FIVE)}, *L7(41)]
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": null}), env, at(10))
    assert window(admission._rows(d)) == "five_hour"


def test_window_stateless_after_refill():
    """A `/limit-reset` drops the week without moving its reset: the pair before it stays."""
    refill = [reading(at(20), L7(5)), reading(at(10), L7(5))]
    assert window(rising() + refill) == "none"
    assert window(refill) == "five_hour"                                 # the pair has left the ledger


def test_window_idle_max_stays_five_hour():
    """From its five-hour reset to its next response an idle Max login lists seven_day
    alone, flat in each session, for hours."""
    rows = [reading(at(400), L5(50, 40))]
    rows += [reading(at(300 - i * 20), L7(40), SID) for i in range(10)]
    rows += [reading(at(290 - i * 20), L7(40), S2) for i in range(10)]
    assert window(rows) == "five_hour"


def test_window_back_on_one_five_hour():
    rows = rising()
    assert window(rows) == "none"
    back = rows + [reading(at(25), L5(1, 41), S2)]
    assert window(back) == "five_hour"
    assert window(back + [reading(at(24), L7(41)), reading(at(5), L7(41))]) == "five_hour"
    again = back + [reading(at(24), L7(41)), reading(at(-6), L7(42))]
    assert window(again, now=NOW + timedelta(minutes=7)) == "none"       # rule 3: a pair after it


def test_window_pair_before_the_five_hour_list_does_not_count():
    assert window(rising() + [reading(at(29), L5(1, 41))]) == "five_hour"


def test_window_same_second_as_a_five_hour_list_is_not_after_it():
    rows = [reading(at(61), L5(1, 40)), reading(at(61), L7(40)), reading(at(30), L7(41))]
    assert window(rows) == "five_hour"


def test_window_empty_list_not_counted():
    junk = [{"kind": "other", "percentUsed": 3, "resetsAt": iso(WEEK)}]
    rows = rising() + [reading(at(20), []), reading(at(10), junk)]
    assert window(rows) == "none"                                        # neither way
    assert window([reading(at(100), []), reading(at(50), [])]) == "five_hour"


def test_window_a_five_hour_list_with_no_seven_day_counts_for_its_session_s_login():
    assert window(rising() + [reading(at(20), L5(5))]) == "five_hour"


def test_window_a_five_hour_list_of_a_session_with_no_key_counts_for_every_key():
    assert window(rising() + [reading(at(20), L5(5), S3)]) == "five_hour"


def test_window_a_five_hour_list_on_another_login_changes_nothing():
    assert window(rising() + [reading(at(20), L5(5, 3, week=OTHER), S2)]) == "none"


def test_window_a_spawn_row_is_an_observation_and_a_list_carrying_five_hour():
    rows = [spawn(at(61), "h1", L7(40)), spawn(at(30), "h2", L7(41))]
    assert window(rows) == "none"
    assert window(rows + [spawn(at(20), "h3", L5(5, 41))]) == "five_hour"


def test_window_a_week_past_its_reset_is_not_counted():
    assert window(rising(), now=WEEK + timedelta(minutes=1)) == "five_hour"


def test_window_a_row_after_now_is_not_read():
    assert window(rising() + [reading(at(-5), L5(5, 41))]) == "none"


def test_window_a_non_finite_or_null_week_is_not_an_observation():
    assert window([reading(at(61), L7(None)), reading(at(30), L7(41))]) == "five_hour"


def test_admit_request_is_not_evidence():
    """The ask's own list neither makes a pair nor switches a `none` account back."""
    flat = [reading(at(61), L7(40))]
    assert decide(flat, ask(rateLimits=L7(41)))["window"] == "five_hour"
    assert decide(rising(), ask(rateLimits=L5(1, 41)))["window"] == "none"


# ---- §3 rule 6: the override, through a config file ---------------------------------------

def test_slot_is_the_weekday_and_minute_and_loads_as_a_key():
    assert admission.slot(KEY) == "Fri-2100Z" and admission.slot(KEY2) == "Wed-1500Z"
    assert admission.slot(None) is None and admission.slot("soon") is None
    assert yamlsubset.load("Fri-2100Z: none\n") == {"Fri-2100Z": "none"}


def world(tmp_path, text):
    """A repo whose config.yaml is `text`, resolved and written for SID as a session's start."""
    env = dict(os.environ)
    repo = tmp_path / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True)
    (repo / ".claude" / "agentik" / "config.yaml").write_text(text)
    resolver.write(resolver.resolve(repo, SID, env), config.state_dir(env))
    return env


def answer(env, lims, now=NOW):
    return admission.admit(SID, json.dumps({"subagentType": "general-purpose", "rateLimits": lims}),
                           env, now)


def test_window_override_by_slot(tmp_path):
    env = world(tmp_path, "session:\n  admission:\n    windows: {Fri-2100Z: none}\n")
    a = answer(env, L7(50))                                              # no pair, no reading
    assert (a["window"], a["verdict"], a["resume_at"] is not None) == ("none", "admitted", True)
    assert answer(env, L7(50, OTHER))["window"] == "five_hour"           # another login: the rule
    b = json.loads((admission.directory(env) / admission.BAND).read_text())
    assert b["window"] == "five_hour" and b["slot"] is None              # no reading yet


def test_window_override_a_slot_beats_the_window(tmp_path):
    env = world(tmp_path, "session:\n  admission:\n    window: none\n"
                          "    windows: {Fri-2100Z: five_hour}\n")
    assert answer(env, L7(50))["window"] == "five_hour"
    assert answer(env, L7(50, OTHER))["window"] == "none"


@pytest.mark.parametrize("value,want", [("none", "none"), ("five_hour", "five_hour"),
                                        ("auto", "five_hour")])
def test_window_override_the_window_itself(tmp_path, value, want):
    env = world(tmp_path, f"session:\n  admission:\n    window: {value}\n")
    assert answer(env, L5(10, 50))["window"] == want
    assert "notes" not in answer(env, L5(10, 50))


def test_window_override_five_hour_keeps_a_rising_login_five_hour():
    assert window(rising(), window="five_hour") == "five_hour"
    assert window(rising(), windows={"Fri-2100Z": "five_hour"}) == "five_hour"
    assert window(rising(), window="none", windows={"Fri-2100Z": "auto"}) == "none"
    assert window([], window="none", windows={"Fri-2100Z": "auto"}) == "five_hour"


@pytest.mark.parametrize("text", [
    "session:\n  admission:\n    windows: {Fri 21:00Z: none}\n",
    "session:\n  admission:\n    windows:\n      Fri-21:00Z: none\n",
], ids=["space-and-colon", "colon"])
def test_bad_slot_key_through_the_file(tmp_path, text):
    """A key the YAML subset cannot read is refused by the loader, naming the file."""
    with pytest.raises(resolver.ResolveError, match="config.yaml"):
        world(tmp_path, text)


@pytest.mark.parametrize("line", ["windows: {Friday-2100Z: none}", "windows: {Fri-2500Z: none}",
                                  "windows: {Fri-2100Z: sometimes}", "windows: {Fri-2100Z: off}",
                                  "windows: fridays", "window: sometimes"])
def test_a_slot_or_window_it_cannot_read_is_noted_and_ignored(tmp_path, line):
    env = world(tmp_path, f"session:\n  admission:\n    {line}\n")
    a = answer(env, L7(50))
    assert a["window"] == "five_hour" and len(a["notes"]) == 1
    assert a["notes"][0].startswith("session.admission.window")


def test_settings_carry_the_override_only_when_set():
    assert "window" not in settings() and "windows" not in settings()
    got = settings(window="none", windows={"Wed-1500Z": "none"})
    assert (got["window"], got["windows"]) == ("none", {"Wed-1500Z": "none"})


# ---- §5: decide, per mode -----------------------------------------------------------------

def test_none_denied_at_ceiling_7d():
    rows = rising(96, 97)
    v = decide(rows)
    assert (v["verdict"], v["window"]) == ("denied", "none")
    assert v["text"] == ("admission: not started. The seven-day window is at 97% and resets "
                         "Fri 21:00. Spawn nothing more; checkpoint and leave the next step to "
                         "the owner.")
    assert v["resume_at"] == iso(WEEK)
    assert decide(rising(95, 96))["verdict"] == "admitted"
    assert decide(rising(95, 96), ceiling_7d=96)["verdict"] == "denied"
    # attended work is judged the same, and the request's own list is the newest
    start = {"ts": iso(at(70)), "session": SID, "kind": "start", "interactive": True, "chain": None}
    assert decide([start] + rising(96, 97))["verdict"] == "denied"
    assert decide(rising(95, 96), ask(rateLimits=L7(99)))["verdict"] == "denied"


def test_none_admits_with_the_week_as_its_horizon():
    v = decide(rising())
    assert (v["verdict"], v["window"], v["resume_at"]) == ("admitted", "none", iso(WEEK))
    assert (v["P"], v["peak"], v["T"], v["text"]) == (None, None, None, "")


@pytest.mark.parametrize("five,name", [(at(200), "stale"), (FIVE, "fresh")])
def test_none_ignores_frozen_five_hour(five, name):
    """A mid-window verification: the old P freezes, and no stale, wait or deferred follows."""
    frozen = [reading(at(300), L5(99, 39, five=five), S2)]
    open_spawn = spawn(at(301), "h1", sid=S2)
    rows = [open_spawn] + frozen + rising()
    v = decide(rows)
    assert (v["verdict"], v["window"], v["P"], v["peak"]) == ("admitted", "none", None, None)
    b = admission.band(rows, NOW, settings(), tz=UTC)
    assert (b["window"], b["P"], b["peak"]) == ("none", None, None)


def test_none_never_runs_the_fit(monkeypatch):
    rows = rising()
    def boom(*a, **k):
        raise AssertionError("the five-hour fit ran on a none account")
    monkeypatch.setattr(admission, "fit", boom)
    monkeypatch.setattr(admission, "project", boom)
    assert decide(rows)["verdict"] == "admitted"
    assert admission.band(rows, NOW, settings(), tz=UTC)["window"] == "none"


def test_none_with_no_fresh_week_admits_and_names_no_reset():
    v = decide([], window="none")
    assert (v["verdict"], v["window"], v["resume_at"]) == ("admitted", "none", None)


def test_denied_weekly_resume_at_is_the_week():
    v = decide([reading(at(10), L5(40, 98))])                            # a Max login, 7d spent
    assert (v["verdict"], v["window"], v["resume_at"]) == ("denied", "five_hour", iso(WEEK))
    v = decide([reading(at(10), L7(98))])                                # no five-hour reading
    assert (v["verdict"], v["window"], v["resume_at"]) == ("denied", "five_hour", iso(WEEK))


def test_five_hour_resume_at_is_the_five_hour_reset():
    v = decide([reading(at(10), L5(40, 50))])
    assert (v["verdict"], v["window"], v["resume_at"]) == ("admitted", "five_hour", iso(FIVE))
    v = decide([reading(at(10), L5(96, 50))])
    assert (v["verdict"], v["resume_at"]) == ("not-started", iso(FIVE))
    start = {"ts": iso(at(70)), "session": SID, "kind": "start", "interactive": True, "chain": None}
    v = decide([start, reading(at(10), L5(96, 50))])
    assert (v["verdict"], v["resume_at"]) == ("deferred", iso(FIVE))


@pytest.mark.parametrize("rows,want", [
    ([], "unread"), ([reading(at(10), L7(50))], "unread"),
    ([reading(at(200), L5(40, 50, five=at(100)))], "stale"),
], ids=["unread", "seven-alone", "stale"])
def test_nothing_to_resume_at_is_null(rows, want):
    v = decide(rows)
    assert (v["verdict"], v["window"], v["resume_at"]) == (want, "five_hour", None)


def test_a_stale_reading_keeps_ruling_4_over_a_spent_week():
    v = decide([reading(at(200), L5(40, 98, five=at(100)))])
    assert v["verdict"] == "stale"                                       # order unchanged: not "no reading"


def test_admit_answers_window_and_resume_at_and_the_ledger_line_is_unchanged():
    env = dict(os.environ)
    a = answer(env, L5(10, 50))
    assert set(a) == {"verdict", "mode", "text", "peak", "window", "resume_at"}
    assert (a["window"], admission._when(a["resume_at"])) == ("five_hour", FIVE)
    rows = admission._rows(admission.directory(env) / admission.LEDGER)
    assert set(rows[-1]) == {"ts", "session", "kind", *admission.VERDICT_KEYS}


# ---- §2: the mode-free fixes -----------------------------------------------------------------

def _two_logins():
    """A (spawning hard, an old reading) and B (quiet, the newest reading): the current."""
    five = FIVE
    rows = [reading(at(40), L5(70, 50, five, OTHER), S2)]
    rows += [spawn(at(5), f"h{i}", sid=S2) for i in range(14)]
    return rows + [reading(at(30), L5(50, 80, five), SID)]


def test_no_rate_limits_judged_on_current_login():
    rows = _two_logins()
    for req in (ask(), ask(rateLimits=None), ask(rateLimits=[])):
        v = admission.decide(rows, req, FRESH, NOW, settings(), tz=UTC)
        want = admission.decide([r for r in rows if r["session"] == SID], req, FRESH, NOW, settings(), tz=UTC)
        assert v == want and v["verdict"] == "admitted"
    mix = admission.decide(rows, ask(rateLimits=L5(50, 80)), FRESH, NOW, settings(), tz=UTC)
    assert mix["verdict"] == "admitted"                                  # its own key, as before


def test_no_rate_limits_a_session_with_a_key_keeps_its_own():
    rows = _two_logins()
    assert admission.decide(rows, ask(), S2, NOW, settings(), tz=UTC)["verdict"] == "not-started"


def test_no_rate_limits_with_one_login_reads_every_line():
    rows = [reading(at(30), L5(70, 80)), reading(at(20), L5(71))]
    assert admission.decide(rows, ask(), FRESH, NOW, settings(), tz=UTC)["P"] == 71


def test_null_entry_skipped_not_refused():
    env = dict(os.environ)
    nulls = [{"kind": None, "percentUsed": 5, "resetsAt": None},
             {"kind": "five_hour", "percentUsed": None, "resetsAt": iso(FIVE)}, *L7(50)]
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": nulls}), env, at(10))
    a = answer(env, nulls)
    assert (a["verdict"], a["window"]) == ("unread", "five_hour")
    good = [{"kind": None, "percentUsed": 5, "resetsAt": None}, *L5(40, 50)]
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": good}), env, at(5))
    assert answer(env, good)["verdict"] == "admitted"
    b = json.loads((admission.directory(env) / admission.BAND).read_text())
    assert (b["P"], b["P7"]) == (40, 50)
    measure.shape({"context": {"window": 200000}, "rateLimits": nulls, "cost": None, "changed": []})


@pytest.mark.parametrize("bad", [{"kind": "five_hour"}, {"percentUsed": 1},
                                 {"kind": 5, "percentUsed": 1},
                                 {"kind": "five_hour", "percentUsed": "full"}])
def test_an_absent_or_wrong_entry_is_still_refused(bad):
    with pytest.raises(admission.AdmissionError):
        admission.record(SID, json.dumps({"kind": "reading", "rateLimits": [bad]}), dict(os.environ), NOW)


def test_top_level_is_current_login():
    rows = _two_logins()
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    top = {k: v for k, v in b.items() if k not in ("accounts", "sessions")}
    assert top == b["accounts"][KEY]                                     # B wrote last
    assert (top["P"], top["running"], top["P7"]) == (50, 0, 80)          # not the mix's 14 helpers
    assert b["accounts"][KEY2]["running"] == 14
    assert admission.session_band(b, FRESH) is b


# ---- §4: band.json -----------------------------------------------------------------------------

def test_five_hour_entry_gains_window_and_slot_and_no_demand():
    b = admission.band([reading(at(10), L5(40, 50))], NOW, settings(), tz=UTC)
    assert (b["window"], b["slot"], b["P"], b["bound"]) == ("five_hour", "Fri-2100Z", 40, "five_hour")
    assert "demand" not in b and "ceiling_7d" not in b


def test_none_entry_is_the_record_s_shape():
    rows = rising(61, 62) + [spawn(at(5), "h1"), spawn(at(4), "h2"), spawn(at(3), "h3")]
    assert admission.band(rows, NOW, settings(), tz=UTC) == {
        "window": "none", "slot": "Fri-2100Z", "P": None, "peak": None, "room": None, "P7": 62,
        "ceiling_7d": 97, "resetsAt": iso(WEEK), "until": iso(WEEK), "bound": "seven_day",
        "running": 3, "mode": "observe", "at": iso(NOW)}


def test_none_on_one_key_writes_accounts_and_sessions():
    rows = rising()
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    assert set(b["accounts"]) == {KEY} and b["sessions"] == {SID: KEY}
    assert {k: v for k, v in b.items() if k not in ("accounts", "sessions")} == b["accounts"][KEY]
    assert admission.session_band(b, SID) == b["accounts"][KEY]


def test_two_accounts_one_none_one_five_hour():
    rows = rising() + [reading(at(25), L5(30, 10, week=OTHER), S2)]
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    assert (b["accounts"][KEY]["window"], b["accounts"][KEY2]["window"]) == ("none", "five_hour")
    assert (b["accounts"][KEY]["slot"], b["accounts"][KEY2]["slot"]) == ("Fri-2100Z", "Wed-1500Z")
    assert b["window"] == "five_hour" and b["P"] == 30                   # S2 wrote last
    assert admission.decide(rows, ask(), SID, NOW, settings(), tz=UTC)["window"] == "none"
    assert admission.decide(rows, ask(), S2, NOW, settings(), tz=UTC)["window"] == "five_hour"


def test_a_lone_five_hour_login_writes_no_accounts():
    b = admission.bands([reading(at(10), L5(40, 50))], NOW, settings(), tz=UTC)
    assert "accounts" not in b and "sessions" not in b


# ---- Packet S43: the lines on a `none` login: one fixture pins both twins -----------------------

def _ts_fixture(name: str) -> str:
    """One line of the module's test file (its name in pieces, as test_band's reader is)."""
    p = Path(__file__).resolve().parent.parent / "plugin" / "hooks" / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return re.search(rf"^const {name} = '(.*)'$", p.read_text(), re.M).group(1)


def _ts_now() -> datetime:
    p = Path(__file__).resolve().parent.parent / "plugin" / "hooks" / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return datetime.fromisoformat(re.search(r"^const NOW = Date\.parse\('(.*)'\)$", p.read_text(), re.M).group(1))


def test_band_line_none_draws_the_module_s_fixtures():
    now = _ts_now()
    assert admission.band_line(json.loads(_ts_fixture("BAND_NONE")), now) == _ts_fixture("BAND_NONE_LINE")
    assert admission.band_line(json.loads(_ts_fixture("BAND_NONE_BARE")), now) == _ts_fixture("BAND_NONE_BARE_LINE")
    assert _ts_fixture("BAND_NONE_LINE") == "no 5h window · 7d 62% · week resets Fri 13:00 · 3 helpers · observe"
    assert _ts_fixture("BAND_NONE_BARE_LINE") == "no 5h window · 3 helpers · observe"


def test_band_line_none_draws_the_module_s_cases():
    now = _ts_now()
    cases = json.loads(_ts_fixture("BAND_NONE_CASES"))
    assert len(cases) >= 20
    for entry, line in cases:
        assert admission.band_line(entry, now) == line, entry


def test_band_line_none_on_the_entry_decide_writes():
    """The record's entry, from band(), not a fixture: the line S42 pinned as today's is gone."""
    rows = rising(61, 62) + [spawn(at(5), "h1"), spawn(at(4), "h2"), spawn(at(3), "h3")]
    b = admission.band(rows, NOW, settings(), tz=UTC)
    assert admission.band_line(b, NOW) == "no 5h window · 7d 62% · week resets Fri 21:00 · 3 helpers · observe"
    assert admission.band_line(b, NOW, 30) == "no 5h window · 7d 62% · week …"


def test_band_line_none_reads_no_system_zone_or_locale(monkeypatch):
    b = json.loads(_ts_fixture("BAND_NONE"))
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    assert admission.band_line(b, _ts_now()) == _ts_fixture("BAND_NONE_LINE")


def test_band_line_none_in_the_prompt_hook_with_its_cache_clause(monkeypatch):
    """The prompt hook draws the line, then the clause `lifetime` gives. The reset is a fixed
    stamp far ahead and the entry has no `at`, so the real clock moves nothing."""
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    reset = "2099-01-02T13:00:00+00:00"                 # a Friday
    d = config.state_dir(os.environ) / "admission"
    d.mkdir(parents=True, exist_ok=True)
    (d / "band.json").write_text(json.dumps({"window": "none", "P": None, "P7": 62, "resetsAt": reset,
                                             "until": reset, "bound": "seven_day", "running": 3,
                                             "mode": "observe"}))
    out = hooks.user_prompt_submit({"session_id": SID})
    bits = out["hookSpecificOutput"]["additionalContext"].split("\n\n")
    [line] = [x for x in bits if x.startswith("no 5h window")]
    assert line == "no 5h window · 7d 62% · week resets Fri 13:00 · 3 helpers · observe"
    assert bits[bits.index(line) + 1].startswith("cache 1h (within plan usage, 7d 62%): ")


@pytest.mark.parametrize("window", ["five_hour", "auto", "NONE", None, 7, ["none"]])
def test_band_line_five_hour_bytes_unchanged(window):
    """Packet S43 ruling 3: today's three lines, spelled here as well as in the fixture, and any
    `window` but the string `none` changes nothing."""
    now = _ts_now()
    fives = [("BAND", None, "5h 72% → 91% · ceiling 97 · resets 13:12 (1h12) · 3 helpers, room for 2 · "
                            "1 deferred · 7d 41% · observe"),
             ("BAND_WEEK", None, "5h 72% → 91% · ceiling 97 · week resets 13:17 (1h17), 5h 15:30 · "
                                 "3 helpers, room for 2 · 1 deferred · 7d 41% · observe"),
             ("BAND_TWO", "sess-1", "5h 40% → 55% · ceiling 97 · resets 14:30 (2h30) · 1 helper, room for 9 · "
                                    "0 deferred · 7d 81% · observe")]
    for name, sid, line in fives:
        assert _ts_fixture(f"{name}_LINE") == line
        b = json.loads(_ts_fixture(name))
        assert admission.band_line(admission.session_band(b, sid), now) == line
        marked = {**b, "window": window}
        if "accounts" in marked:
            marked["accounts"] = {k: {**v, "window": window} for k, v in marked["accounts"].items()}
        assert admission.band_line(admission.session_band(marked, sid), now) == line


def _none_entry(p7, reset=WEEK, **kw):
    return {"window": "none", "P": None, "peak": None, "room": None, "P7": p7,
            "resetsAt": iso(reset) if reset is not None else None, "bound": "seven_day", **kw}


@pytest.mark.parametrize("entry,want", [
    (_none_entry(62), ("1h", "within plan usage, 7d 62%")),
    (_none_entry(72.5), ("1h", "within plan usage, 7d 72.5%")),
    (_none_entry(99.5), ("1h", "within plan usage, 7d 99.5%")),
    (_none_entry(100), ("5m", "past plan usage, 7d 100%")),
    (_none_entry(104.5), ("5m", "past plan usage, 7d 104.5%")),
    (_none_entry(62, NOW), (None, rules.UNKNOWN)),
    (_none_entry(62, NOW - timedelta(hours=1)), (None, rules.UNKNOWN)),
    (_none_entry(62, None), (None, rules.UNKNOWN)),
    (_none_entry(None), (None, rules.UNKNOWN)),
    (_none_entry("62"), (None, rules.UNKNOWN)),
    (_none_entry(True), (None, rules.UNKNOWN)),
], ids=["below", "below-fraction", "just-below", "at-plan", "past-plan", "reset-now", "reset-past",
        "no-reset", "p7-null", "p7-string", "p7-bool"])
def test_lifetime_none_by_seven_day(entry, want):
    assert rules.lifetime({}, "/nonexistent", entry, now=NOW) == want


def test_lifetime_none_by_seven_day_on_the_entry_decide_writes():
    """S42's lifetime assertion on this entry, moved here and turned (packet S43 ruling 6)."""
    b = admission.band(rising(61, 62), NOW, settings(), tz=UTC)
    assert b["window"] == "none"
    assert rules.lifetime({}, "/nonexistent", b, now=NOW) == ("1h", "within plan usage, 7d 62%")


def test_lifetime_none_by_seven_day_leaves_every_rule_above_it():
    b = _none_entry(100)
    assert rules.lifetime({"FORCE_PROMPT_CACHING_5M": "1"}, "/nonexistent", b, now=NOW) == ("5m", "FORCE_PROMPT_CACHING_5M")
    assert rules.lifetime({"ENABLE_PROMPT_CACHING_1H": "1"}, "/nonexistent", b, now=NOW) == ("1h", "ENABLE_PROMPT_CACHING_1H")
    assert rules.lifetime({"DISABLE_PROMPT_CACHING": "1"}, "/nonexistent", b, now=NOW) == ("off", "DISABLE_PROMPT_CACHING")
    assert rules.lifetime({"CLAUDE_CODE_USE_BEDROCK": "1"}, "/nonexistent", b, now=NOW) == ("5m", "a cloud provider")
    assert rules.lifetime({"ANTHROPIC_API_KEY": "x"}, "/nonexistent", b, now=NOW)[0] is None


@pytest.mark.parametrize("marks", [{}, {"window": "five_hour"}, {"window": "auto"}, {"window": None}])
def test_lifetime_none_by_seven_day_leaves_a_five_hour_band(marks):
    five = {"P": 41, "P7": 99.5, "resetsAt": iso(FIVE), **marks}
    assert rules.lifetime({}, "/nonexistent", five, now=NOW) == ("1h", "within plan usage, 5h 41%")
    assert rules.lifetime({}, "/nonexistent", {**five, "P7": 100}, now=NOW) == ("5m", "past plan usage, 7d 100%")
    assert rules.lifetime({}, "/nonexistent", {**five, "P": 100}, now=NOW) == ("5m", "past plan usage, 5h 100%")
    assert rules.lifetime({}, "/nonexistent", {**five, "P": None}, now=NOW) == (None, rules.UNKNOWN)


# ---- Amendment 1, F1: the stale gate holds a relay ask across logins ----------------------------

def _past_reset_logins(env, two=True):
    """The current login's reading past its reset; with `two`, another login's before it."""
    if two:
        admission.record(S2, json.dumps({"kind": "reading", "rateLimits": L5(10, 20, NOW + timedelta(hours=1), OTHER)}),
                         env, at(180))
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": L5(50, 30, at(5))}), env, at(20))


def relay_ask(n):
    return json.dumps({"model": "claude-opus-5-5", "subagentType": "relay-row", "background": True,
                       "fork": False, "tool_use_id": f"n/{n}/1"})


@pytest.mark.parametrize("two", [False, True], ids=["one-login", "two-logins"])
def test_stale_gate_holds_relay_asks_on_any_number_of_logins(two):
    """admission-r1's one spawn at a time: a row's ask has no key, and neither has its verdict
    line, so that line counts for the login the ask was judged on."""
    env = dict(os.environ)
    _past_reset_logins(env, two)
    got = [admission.admit(f"row-{i}-1111", relay_ask(i), env, NOW + timedelta(seconds=5 * i))["verdict"]
           for i in range(4)]
    assert got == ["stale", "wait", "wait", "wait"]


def _verdict(t, sid, tid, v="stale"):
    return {"ts": iso(t), "session": sid, "kind": "verdict", "tool_use_id": tid, "verdict": v,
            "mode": "observe", "peak": None, "P": None, "T": None, "family": "opus", "type": "relay-row"}


def _stale_two():
    return [reading(at(180), L5(10, 20, NOW + timedelta(hours=1), OTHER), S2),
            reading(at(20), L5(50, 30, at(5)), SID)]


def test_stale_gate_a_row_with_a_run_in_flight_holds_past_the_grace():
    row = dict(spawn(at(4), "r1", sid="row-1"), tool_use_id="n/1/1")
    rows = _stale_two() + [_verdict(at(4), "row-1", "n/1/1"), row]
    assert decide(rows, ask(tool_use_id="n/2/1"), "row-2")["verdict"] == "wait"


def test_stale_gate_another_login_s_stale_verdict_holds_no_relay_ask():
    """Corner 3 stands: the ask is judged on the current login, not on every line."""
    rows = _stale_two() + [_verdict(NOW - timedelta(seconds=30), S2, "n/9/1")]
    assert decide(rows, ask(tool_use_id="n/2/1"), "row-2")["verdict"] == "stale"


def test_stale_gate_a_keyed_session_is_as_before():
    """A session with its own key never read the rows' lines: no five-hour verdict moves."""
    rows = _stale_two() + [_verdict(NOW - timedelta(seconds=30), "row-1", "n/1/1")]
    assert decide(rows, ask(tool_use_id="toolu_x"), SID)["verdict"] == "stale"
    given = ask(tool_use_id="toolu_x", rateLimits=L5(50, 30, at(5)))
    assert decide(rows, given, FRESH)["verdict"] == "stale"


def test_a_row_s_lines_stay_out_of_the_projection():
    """Corner 3's other half: only the gate reads a keyless session's lines."""
    rows = _two_logins()
    keyless = [spawn(at(3), f"k{i}", sid="row-1") for i in range(14)]
    alone = decide(rows, ask(), FRESH)
    both = decide(rows + keyless, ask(), FRESH)
    assert both["peak"] == alone["peak"] and both["verdict"] == "admitted"


# ---- Amendment 1, F2: a session with no resolved.json reads the user layer's override -----------

def user_layer(text):
    home = config.Path(os.environ["HOME"]) / ".claude" / "agentik"
    home.mkdir(parents=True, exist_ok=True)
    (home / "profiles.yaml").write_text(text)


def band_file(env):
    return json.loads((admission.directory(env) / admission.BAND).read_text())


def _frozen(env):
    admission.record(SID, json.dumps({"kind": "reading", "rateLimits": L5(50, 50, at(30))}), env, at(60))


def test_no_resolved_file_reads_the_user_layer_window(tmp_path):
    user_layer("defaults:\n  admission:\n    window: none\n")
    env = world(tmp_path, "")
    _frozen(env)
    assert answer(env, [])["window"] == "none"
    assert band_file(env)["window"] == "none"
    row = admission.admit("row-sess-1111", relay_ask(1), env, NOW)
    assert (row["verdict"], row["window"]) == ("admitted", "none")
    assert band_file(env)["window"] == "none"                            # no flip, either writer


def test_no_resolved_file_a_record_writes_the_band_under_it(tmp_path):
    user_layer("defaults:\n  admission:\n    window: none\n")
    env = world(tmp_path, "")
    _frozen(env)
    admission.record("row-sess-1111", json.dumps({"kind": "start", "interactive": False}), env, NOW)
    assert band_file(env)["window"] == "none"


def test_no_resolved_file_reads_the_user_layer_slot_and_brake(tmp_path):
    user_layer("defaults:\n  admission:\n    window: five_hour\n    windows: {Wed-1500Z: none}\n")
    env = dict(os.environ)
    for t, p in ((60, 90), (20, 91)):
        admission.record(SID, json.dumps({"kind": "reading", "rateLimits": L7(p)}), env, at(t))
    assert window(admission._rows(admission.directory(env) / admission.LEDGER)) == "none"
    row = admission.admit("row-sess-1111", relay_ask(1), env, NOW)
    assert row["window"] == "five_hour"                                  # the owner's brake binds the ask
    ask_other = json.dumps({"rateLimits": L7(50, OTHER)})
    assert admission.admit("row-sess-1111", ask_other, env, NOW)["window"] == "none"


def test_no_resolved_file_reads_only_the_override():
    """The other knobs stay as they were on such an ask, so no five-hour verdict moves."""
    user_layer("defaults:\n  admission:\n    ceiling: 50\n    ceiling_7d: 10\n")
    env = dict(os.environ)
    a = answer(env, L5(40, 50))
    assert a["verdict"] == "admitted"


def test_no_resolved_file_does_not_guess_a_repo_layer(tmp_path):
    env = world(tmp_path, "session:\n  admission:\n    window: none\n")
    assert answer(env, L7(50))["window"] == "none"                       # the resolved session
    row = admission.admit("row-sess-1111", json.dumps({"rateLimits": L7(50)}), env, NOW)
    assert row["window"] == "five_hour"                                  # a row has no repo to read


@pytest.mark.parametrize("text", ["defaults: [", "defaults: 5\n", "defaults:\n  admission: 5\n", "- a\n"])
def test_no_resolved_file_a_bad_user_layer_reads_as_auto(text):
    user_layer(text)
    env = dict(os.environ)
    a = admission.admit("row-sess-1111", json.dumps({"rateLimits": L5(40, 50)}), env, NOW)
    assert (a["verdict"], a["window"]) == ("admitted", "five_hour")


def test_a_resolved_file_beats_the_user_layer_reading_alone(tmp_path):
    """The session's resolved file already holds the merged layers: a repo over the user's."""
    user_layer("defaults:\n  admission:\n    window: none\n")
    env = world(tmp_path, "session:\n  admission:\n    window: five_hour\n")
    assert answer(env, L7(50))["window"] == "five_hour"


# ---- Amendment 1: the refuter's surviving mutants, §3's rule ------------------------------------

def test_window_last_is_the_newest_five_hour_list_not_the_last_in_the_file():
    rows = [reading(at(20), L5(1, 41)), reading(at(100), L5(1, 39)),
            reading(at(61), L7(40)), reading(at(30), L7(41))]
    assert window(rows) == "five_hour"                                   # the pair is before at(20)


def test_window_observations_are_taken_in_time_not_file_order():
    assert window([reading(at(30), L7(41)), reading(at(61), L7(40))]) == "none"
    assert window([reading(at(30), L7(40)), reading(at(61), L7(41))]) == "five_hour"


def test_window_the_earlier_figure_is_the_lowest_past_the_span():
    rows = [reading(at(120), L7(40)), reading(at(100), L7(41.5)), reading(at(30), L7(41.5))]
    assert window(rows) == "none"                                        # 40 to 41.5, not 41.5 to 41.5


def test_accounts_read_the_mode_over_every_line_not_the_split():
    """A spawn row keyed to one login, its session's newest reading on another: `_split` files
    the line under the session's key, and the rule still counts it for its own."""
    rows = [spawn(at(61), "h1", L7(40), S2), spawn(at(30), "h2", L7(41), S2),
            reading(at(25), L7(41), SID), reading(at(20), L5(30, 10, week=OTHER), S2)]
    assert window(rows) == "none"
    assert admission.bands(rows, NOW, settings(), tz=UTC)["accounts"][KEY]["window"] == "none"


def test_none_entry_reads_only_a_fresh_week():
    rows = [reading(at(60), L7(50, at(10)))]
    b = admission.band(rows, NOW, settings(window="none"), tz=UTC)
    assert (b["window"], b["P7"], b["resetsAt"], b["until"]) == ("none", None, None, None)


# ---- Amendment 2: round 2's regression and three survivors ---------------------------------------

def test_a_user_layer_nested_past_the_stack_does_not_break_admission_admit(capsys, monkeypatch):
    """Through the verb: a session with no resolved file reads the override, and that read
    never raises. Deep enough to pass the interpreter's limit from any caller's stack."""
    nested = "defaults:\n" + "".join(" " * i + f"k{i}:\n" for i in range(1, 1500))
    user_layer(nested)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"rateLimits": L5(40, 50)})))
    assert cli.main(["admission", "admit", "--session", "row-sess-1111"]) == 0
    assert json.loads(capsys.readouterr().out)["window"] == "five_hour"


def test_stale_gate_a_current_login_s_keyed_line_holds_a_row():
    rows = _stale_two() + [_verdict(NOW - timedelta(seconds=30), SID, "n/1/1")]
    assert decide(rows, ask(tool_use_id="n/2/1"), "row-2")["verdict"] == "wait"


def test_no_resolved_file_a_directory_at_the_user_layer_reads_as_auto():
    user_layer("")
    p = config.Path(os.environ["HOME"]) / ".claude" / "agentik" / "profiles.yaml"
    p.unlink()
    p.mkdir()
    a = answer(dict(os.environ), L5(40, 50))
    assert (a["verdict"], a["window"]) == ("admitted", "five_hour")


def test_a_torn_resolved_file_still_reads_the_user_layer_override(tmp_path):
    user_layer("defaults:\n  admission:\n    window: none\n")
    env = world(tmp_path, "")
    p = config.state_dir(env) / "sessions" / SID / "resolved.json"
    p.write_text(p.read_text()[:40])
    assert answer(env, L7(50))["window"] == "none"
