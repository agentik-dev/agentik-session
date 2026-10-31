"""Packet S42: a window mode per account. A login whose readings show no five-hour window
while its week rises stops pacing against five hours; every five-hour behaviour stays for
one that has it, but the four mode-free fixes. No test depends on real time: every `now`
is passed in."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from claude_session import admission, config, measure, resolver, rules, yamlsubset

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


def test_none_line_reads_as_today_until_s43():
    """Packet S42 ruling 2, today's `band_line` on the record's entry; S43 replaces this line."""
    rows = rising(61, 62) + [spawn(at(5), "h1"), spawn(at(4), "h2"), spawn(at(3), "h3")]
    b = admission.band(rows, NOW, settings(), tz=UTC)
    assert admission.band_line(b, NOW) == ("5h no reading · week resets 21:00 (169h00), 5h 21:00 · "
                                           "3 helpers · 7d 62% · observe")
    assert rules.lifetime({}, "/nonexistent", b, now=NOW)[0] is None
