"""Packet S44: the demand bands, reported and never held. The schedule is a file; only
admission reads it, at a band.json write; no verdict moves on a band. No test depends on
real time but the two that drive `status`, whose stamps are built from the clock."""
import ast
import io
import json
import os
import re
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from importlib import resources
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from claude_session import admission, cli, demand, doctor, hooks, resolver, rules

ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc
LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)         # a Friday, 13:00 on the schedule's clock
WEEK = datetime(2026, 11, 6, 21, 0, tzinfo=UTC)
FIVE = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
SID, S2 = "bands-sess-0000-1111", "bands-sess-2222-3333"

SHIPPED = '''tz: America/Los_Angeles   # wall clock, across DST
bands:                    # first match wins; [from, to)
  - {days: Mon-Fri, from: "05:00", to: "11:00", band: avoid,  grade: A}
  - {days: Mon-Fri, from: "11:00", to: "16:00", band: middle, grade: B}
  - {days: Mon-Thu, from: "16:00", to: "23:00", band: best,   grade: B}
  - {days: Fri,     from: "16:00", to: "24:00", band: best,   grade: B}
  - {days: Sat,     from: "00:00", to: "24:00", band: best,   grade: A}
  - {days: Sun,     from: "00:00", to: "20:00", band: best,   grade: A}
  - {days: Sun,     from: "20:00", to: "24:00", band: middle, grade: C}
  - {days: Mon-Sun, from: "00:00", to: "24:00", band: good,   grade: C}   # the nights
'''


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


def rising(p0=40.0, p1=41.0, sid=SID, week=WEEK):
    return [reading(at(61), L7(p0, week), sid), reading(at(45), L7(p0, week), sid),
            reading(at(30), L7(p1, week), sid)]


def spawn(t, aid, sid=SID):
    return {"ts": iso(t), "session": sid, "kind": "spawn", "subagentType": "general-purpose",
            "model": "opus", "parentModel": "claude-opus-5-5", "background": True, "fork": False,
            "description": None, "tool_use_id": f"toolu_{aid}", "agentId": aid,
            "context": None, "rateLimits": []}


def start(interactive, sid=SID):
    return {"ts": iso(at(120)), "session": sid, "kind": "start", "interactive": interactive, "chain": None}


ASK = {"subagentType": "general-purpose", "model": "opus", "parentModel": "claude-opus-5-5",
       "background": True, "fork": False, "tool_use_id": "toolu_9", "rateLimits": None, "resume": False}


def wall(*a, tz=LA, fold=0):
    return datetime(*a, tzinfo=tz, fold=fold)


def rule_file(lines, tz="America/Los_Angeles"):
    return f"tz: {tz}\nbands:\n" + "".join(f"  - {x}\n" for x in lines)


ALL_WEEK = '{days: Mon-Sun, from: "00:00", to: "24:00", band: good}'


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    return os.environ


def user_file(env) -> Path:
    p = Path(env["XDG_CONFIG_HOME"]) / "agentik" / "session" / "bands.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load(env, text):
    user_file(env).write_text(text)
    return demand.schedule(env)


def ledger(env, rows):
    d = admission.directory(env)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    (d / admission.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in rows))


def admit(env, rows):
    ledger(env, rows)
    return admission.admit(SID, json.dumps(ASK), env, NOW)


# ---- the file ---------------------------------------------------------------------------

def test_shipped_file_is_the_record_s_text_and_ships():
    f = resources.files("claude_session").joinpath("bands.yaml")
    assert f.is_file()
    assert f.read_bytes() == SHIPPED.encode()
    data = re.search(r"^\[tool\.setuptools\.package-data\]\n(.*)$", (ROOT / "pyproject.toml").read_text(), re.M)
    assert re.fullmatch(r'claude_session = \[.*"bands\.yaml".*\]', data.group(1))


def test_demand_imports_no_admission():
    tree = ast.parse((ROOT / "claude_session" / "demand.py").read_text())
    names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
    assert "admission" not in names and not any(n.endswith(".admission") for n in names)


def test_bands_default_covers_168_hours(env):
    rules_, tz, notes = demand.schedule(env)
    assert (tz.key, notes) == ("America/Los_Angeles", [])
    slots = demand._slots(rules_)
    assert len(slots) == 168 * 60 and None not in slots
    hour = {}
    for d in range(7):
        for h in range(24):
            hour[(d, h)] = slots[d * 1440 + h * 60]
    for d in range(5):                                     # Mon to Fri, the day
        assert {hour[(d, h)] for h in range(5, 11)} == {"avoid"}
        assert {hour[(d, h)] for h in range(11, 16)} == {"middle"}
    for d in range(4):                                     # Mon to Thu, the evening and the night
        assert {hour[(d, h)] for h in range(16, 23)} == {"best"} and hour[(d, 23)] == "good"
    assert {hour[(4, h)] for h in range(16, 24)} == {"best"}
    assert {hour[(5, h)] for h in range(24)} == {"best"}
    assert {hour[(6, h)] for h in range(20)} == {"best"}
    assert {hour[(6, h)] for h in range(20, 24)} == {"middle"}
    for d in range(5):
        assert {hour[(d, h)] for h in range(5)} == {"good"}


def test_a_good_user_file_replaces_the_shipped_whole(env):
    rules_, tz, notes = load(env, rule_file([ALL_WEEK], "UTC"))
    assert (str(tz), notes) == ("UTC", [])
    d = demand.demand(NOW, rules_, tz, UTC)
    assert d == {"band": "good", "until": None, "next": {}}    # one band all week: no change, no next stretch


def test_xdg_unset_reads_home_config(env, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME")
    p = Path(env["HOME"]) / ".config" / "agentik" / "session" / "bands.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(rule_file([ALL_WEEK], "UTC"))
    assert str(demand.schedule(env)[1]) == "UTC"


BAD = {
    "no-parse": "tz: [\n",
    "empty": "",
    "no-tz": 'bands:\n  - ' + ALL_WEEK + "\n",
    "bad-tz": rule_file([ALL_WEEK], "Mars/Olympus"),
    "dir-tz": rule_file([ALL_WEEK], "America"),
    "climbing-tz": rule_file([ALL_WEEK], "../etc/passwd"),
    "number-tz": "tz: 7\nbands:\n  - " + ALL_WEEK + "\n",
    "no-bands": "tz: UTC\n",
    "bands-scalar": "tz: UTC\nbands: 7\n",
    "rule-scalar": rule_file(["7", ALL_WEEK]),
    "days-word": rule_file(['{days: Funday, from: "00:00", to: "24:00", band: x}', ALL_WEEK]),
    "days-back": rule_file(['{days: Fri-Mon, from: "00:00", to: "24:00", band: x}', ALL_WEEK]),
    "days-same": rule_file(['{days: Mon-Mon, from: "00:00", to: "24:00", band: x}', ALL_WEEK]),
    "days-list": rule_file(['{days: "Mon,Tue", from: "00:00", to: "24:00", band: x}', ALL_WEEK]),
    "days-none": rule_file(['{from: "00:00", to: "24:00", band: x}', ALL_WEEK]),
    "from-short": rule_file(['{days: Mon, from: "5:00", to: "24:00", band: x}', ALL_WEEK]),
    "from-none": rule_file(['{days: Mon, to: "24:00", band: x}', ALL_WEEK]),
    "to-past": rule_file(['{days: Mon, from: "00:00", to: "24:30", band: x}', ALL_WEEK]),
    "to-25": rule_file(['{days: Mon, from: "00:00", to: "25:00", band: x}', ALL_WEEK]),
    "to-minute": rule_file(['{days: Mon, from: "00:00", to: "10:60", band: x}', ALL_WEEK]),
    "from-after": rule_file(['{days: Mon, from: "10:00", to: "09:00", band: x}', ALL_WEEK]),
    "from-same": rule_file(['{days: Mon, from: "10:00", to: "10:00", band: x}', ALL_WEEK]),
    "no-band": rule_file(['{days: Mon, from: "00:00", to: "24:00"}', ALL_WEEK]),
    "band-empty": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: ""}', ALL_WEEK]),
    "band-number": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: 7}', ALL_WEEK]),
    "band-40000": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: %s}' % ("x" * 40000), ALL_WEEK]),
    "band-33": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: %s}' % ("x" * 33), ALL_WEEK]),
    "band-control": rule_file([r'{days: Mon, from: "00:00", to: "24:00", band: "a\nb\u001b[31m"}', ALL_WEEK]),
    "band-trailing-newline": rule_file([r'{days: Mon, from: "00:00", to: "24:00", band: "avoid\n"}', ALL_WEEK]),
    "band-space": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: "a b"}', ALL_WEEK]),
    "band-dot": rule_file(['{days: Mon, from: "00:00", to: "24:00", band: a.b}', ALL_WEEK]),
    "band-not-ascii": rule_file([r'{days: Mon, from: "00:00", to: "24:00", band: "b\u00e4nd"}', ALL_WEEK]),
    "hour-short": rule_file(['{days: Mon-Sun, from: "00:00", to: "23:00", band: good}']),
    "half-hour-short": rule_file(['{days: Mon-Sun, from: "00:00", to: "23:30", band: good}']),
    "a-day-short": rule_file(['{days: Mon-Sat, from: "00:00", to: "24:00", band: good}']),
}


@pytest.mark.parametrize("name", sorted(BAD))
def test_bad_bands_file_falls_back(env, name):
    shipped = demand.schedule(env)
    rules_, tz, notes = load(env, BAD[name])
    assert (rules_, tz) == shipped[:2]
    assert len(notes) == 1 and str(user_file(env)) in notes[0]
    rows = doctor._check_bands(env)
    assert [(c.ok, c.warn, c.detail) for c in rows] == [(True, True, notes[0])]


@pytest.mark.parametrize("name", ["band-40000", "band-control"])
def test_a_bad_band_name_stays_out_of_the_note(env, name):
    _, _, notes = load(env, BAD[name])
    assert len(notes) == 1 and len(notes[0]) < 400 + len(str(user_file(env)))
    assert not any(ord(c) < 32 for c in notes[0])


def test_the_longest_band_name_and_its_characters_bind(env):
    name = "aZ09-_" + "x" * 26
    rules_, _, notes = load(env, rule_file(['{days: Mon-Sun, from: "00:00", to: "24:00", band: %s}' % name]))
    assert notes == [] and rules_[0]["band"] == name


def test_bad_bands_not_utf8_too_big_a_dir_or_a_fifo_never_hang(env):
    p = user_file(env)
    p.write_bytes(b"\xff\xfe")
    assert len(demand.schedule(env)[2]) == 1
    p.write_text("# pad\n" * 20000 + rule_file([ALL_WEEK], "UTC"))
    rules_, tz, notes = demand.schedule(env)
    assert tz.key == "America/Los_Angeles" and len(notes) == 1
    p.unlink()
    p.mkdir()
    assert len(demand.schedule(env)[2]) == 1
    p.rmdir()
    os.mkfifo(p)
    rules_, tz, notes = demand.schedule(env)                # a hang here is the failure
    assert tz.key == "America/Los_Angeles" and len(notes) == 1


def test_shipped_gone_is_no_band_anywhere(env, monkeypatch):
    def gone():
        raise FileNotFoundError("bands.yaml")
    monkeypatch.setattr(demand, "_shipped", gone)
    rules_, tz, notes = demand.schedule(env)
    assert (rules_, tz, len(notes)) == ([], None, 1)
    assert demand.demand(NOW, rules_, tz) is None
    answer = admit(env, rising())
    assert (answer["window"], answer["band"]) == ("none", None)
    b = admission.read_band(env)
    assert "demand" not in b and "band" not in admission.band_line(b, NOW)


def test_shipped_zone_gone_is_no_band_either(env, monkeypatch):
    monkeypatch.setattr(demand, "_shipped", lambda: SHIPPED.replace("America/Los_Angeles", "Mars/Olympus"))
    assert demand.schedule(env)[:2] == ([], None)


# ---- demand -----------------------------------------------------------------------------

def shipped(env, t, stamp=LA):
    rules_, tz, _ = demand.schedule(env)
    return demand.demand(t, rules_, tz, stamp)


def test_demand_mon_0700_avoid_until_1100(env):
    assert shipped(env, wall(2026, 10, 26, 7)) == {
        "band": "avoid", "until": "2026-10-26T11:00:00-07:00",
        "next": {"good": "2026-10-26T23:00:00-07:00", "best": "2026-10-26T16:00:00-07:00"}}


def test_until_walks_past_a_rule_with_the_same_band(env):
    d = shipped(env, wall(2026, 10, 24, 9))                # Saturday: midnight is no change
    assert (d["band"], d["until"]) == ("best", "2026-10-25T20:00:00-07:00")
    assert d["next"] == {"good": "2026-10-26T00:00:00-07:00", "best": "2026-10-26T16:00:00-07:00"}
    assert shipped(env, wall(2026, 10, 23, 17))["until"] == "2026-10-25T20:00:00-07:00"   # Friday's too
    assert shipped(env, wall(2026, 10, 25, 22))["until"] == "2026-10-26T00:00:00-07:00"   # Sunday's middle


def test_next_of_the_band_now_in_is_the_stretch_after_this_one(env):
    d = shipped(env, wall(2026, 10, 26, 4))                # Monday's night
    assert (d["band"], d["until"]) == ("good", "2026-10-26T05:00:00-07:00")
    assert d["next"]["good"] == "2026-10-26T23:00:00-07:00"
    d = shipped(env, wall(2026, 10, 26, 17))               # Monday's evening
    assert d["next"]["best"] == "2026-10-27T16:00:00-07:00"


def test_the_stretch_edge_is_half_open(env):
    assert shipped(env, wall(2026, 10, 26, 10, 59))["band"] == "avoid"
    d = shipped(env, wall(2026, 10, 26, 11, 0))
    assert (d["band"], d["until"]) == ("middle", "2026-10-26T16:00:00-07:00")


def test_a_band_the_schedule_lacks_is_an_absent_key(env):
    rules_, tz, _ = load(env, rule_file(['{days: Mon-Fri, from: "00:00", to: "24:00", band: best}',
                                         '{days: Mon-Sun, from: "00:00", to: "24:00", band: avoid}'], "UTC"))
    d = demand.demand(datetime(2026, 10, 24, 9, tzinfo=UTC), rules_, tz, UTC)      # a Saturday
    assert d == {"band": "avoid", "until": "2026-10-26T00:00:00+00:00",
                 "next": {"best": "2026-10-26T00:00:00+00:00"}}


def test_first_match_wins(env):
    rules_, tz, _ = load(env, rule_file(['{days: Mon, from: "00:00", to: "12:00", band: best}',
                                         '{days: Mon, from: "06:00", to: "18:00", band: avoid}', ALL_WEEK], "UTC"))
    d = demand.demand(datetime(2026, 10, 26, 7, tzinfo=UTC), rules_, tz, UTC)
    assert (d["band"], d["until"]) == ("best", "2026-10-26T12:00:00+00:00")


def test_bands_wall_clock_across_2026_11_01(env):
    # Saturday, PDT: the band's end is Sunday's 20:00 on the wall, PST
    assert shipped(env, wall(2026, 10, 31, 9))["until"] == "2026-11-01T20:00:00-08:00"
    assert shipped(env, wall(2026, 10, 31, 9), UTC)["until"] == "2026-11-02T04:00:00+00:00"
    # Friday, PDT, to Monday's night, PST
    d = shipped(env, wall(2026, 10, 30, 7))
    assert (d["band"], d["until"]) == ("avoid", "2026-10-30T11:00:00-07:00")
    assert d["next"] == {"good": "2026-11-02T00:00:00-08:00", "best": "2026-10-30T16:00:00-07:00"}
    # the fold's two passes read the same band and end
    for t in (wall(2026, 11, 1, 1, 30, fold=0), wall(2026, 11, 1, 1, 30, fold=1)):
        d = shipped(env, t)
        assert (d["band"], d["until"]) == ("best", "2026-11-01T20:00:00-08:00")
    # after it, the same wall hours: 07:00 is avoid, to 11:00
    d = shipped(env, wall(2026, 11, 2, 7))
    assert (d["band"], d["until"]) == ("avoid", "2026-11-02T11:00:00-08:00")


def test_a_wall_time_in_a_gap_reads_the_first_instant_after_it(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "02:30", to: "24:00", band: best}', ALL_WEEK]))
    d = demand.demand(wall(2027, 3, 14, 1), rules_, tz, LA)        # the spring gap: 02:00 to 03:00
    assert (d["band"], d["until"]) == ("good", "2027-03-14T03:00:00-07:00")
    assert d["next"]["best"] == "2027-03-14T03:00:00-07:00"


def test_a_stretch_the_gap_swallows_is_no_change(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "02:15", to: "02:45", band: best}', ALL_WEEK]))
    d = demand.demand(wall(2027, 3, 14, 1), rules_, tz, LA)
    assert d["until"] == "2027-03-21T02:15:00-07:00"


def test_a_wall_time_in_a_fold_reads_its_first_instant(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "01:30", to: "24:00", band: best}', ALL_WEEK]))
    d = demand.demand(wall(2026, 11, 1, 0, 30), rules_, tz, LA)
    assert d["until"] == "2026-11-01T01:30:00-07:00"


FOLD_RULES = ['{days: Sun, from: "01:30", to: "24:00", band: best}', ALL_WEEK]
BEFORE_THE_CUT = {"band": "good", "until": "2026-11-01T01:30:00-07:00",
                  "next": {"good": "2026-11-02T00:00:00-08:00", "best": "2026-11-01T01:30:00-07:00"}}
PAST_THE_CUT = {"band": "best", "until": "2026-11-02T00:00:00-08:00",
                "next": {"good": "2026-11-02T00:00:00-08:00", "best": "2026-11-08T01:30:00-08:00"}}


@pytest.mark.parametrize("h,m,s,want", [
    (8, 15, 0, BEFORE_THE_CUT),      # the first pass, before the cut
    (8, 45, 0, PAST_THE_CUT),        # the first pass, past it
    (8, 59, 59, PAST_THE_CUT),       # the first pass's last second
    (9, 0, 0, PAST_THE_CUT),         # the second pass's first: the wall reads 01:00 again
    (9, 15, 0, PAST_THE_CUT),        # the refuter's F1: the wall reads before the cut, which is past
    (9, 45, 0, PAST_THE_CUT),
    (10, 0, 0, PAST_THE_CUT),        # the fold is over
])
def test_a_cut_in_a_fold_happens_once(env, h, m, s, want):
    rules_, tz, _ = load(env, rule_file(FOLD_RULES))
    assert demand.demand(datetime(2026, 11, 1, h, m, s, tzinfo=UTC), rules_, tz, LA) == want


def test_a_stretch_inside_a_fold_does_not_come_back(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "01:10", to: "01:20", band: best}', ALL_WEEK]))
    d = demand.demand(datetime(2026, 11, 1, 9, 15, tzinfo=UTC), rules_, tz, LA)
    assert (d["band"], d["until"]) == ("good", "2026-11-08T01:10:00-08:00")


def test_a_cut_at_a_fold_s_end_is_still_ahead_in_the_second_pass(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "02:00", to: "24:00", band: best}', ALL_WEEK]))
    d = demand.demand(datetime(2026, 11, 1, 9, 15, tzinfo=UTC), rules_, tz, LA)
    assert (d["band"], d["until"]) == ("good", "2026-11-01T02:00:00-08:00")


def test_a_half_hour_fold_reads_the_first_pass_s_end_too(env):
    lord_howe = ZoneInfo("Australia/Lord_Howe")          # 02:00 back to 01:30 on 2027-04-04
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "01:45", to: "24:00", band: best}', ALL_WEEK],
                                        "Australia/Lord_Howe"))
    t = datetime(2027, 4, 3, 15, 10, tzinfo=UTC)         # 01:40 on the second pass
    assert t.astimezone(lord_howe).fold == 1
    d = demand.demand(t, rules_, tz, UTC)
    assert (d["band"], d["until"]) == ("best", "2027-04-04T13:30:00+00:00")


def test_the_walk_reaches_a_stretch_past_the_gap_that_swallowed_it(env):
    rules_, tz, _ = load(env, rule_file(['{days: Sun, from: "02:00", to: "03:00", band: best}', ALL_WEEK]))
    d = demand.demand(wall(2027, 3, 7, 3, 0), rules_, tz, LA)     # pins WALK_WEEKS: two weeks read None
    assert d == {"band": "good", "until": "2027-03-21T02:00:00-07:00",
                 "next": {"good": "2027-03-21T03:00:00-07:00", "best": "2027-03-21T02:00:00-07:00"}}


def test_next_keeps_the_first_stretch_when_a_band_comes_twice(env):
    rules_, tz, _ = load(env, rule_file([
        '{days: Mon, from: "00:00", to: "06:00", band: avoid}',
        '{days: Mon, from: "06:00", to: "12:00", band: best}',
        '{days: Mon, from: "12:00", to: "18:00", band: middle}',
        '{days: Mon, from: "18:00", to: "24:00", band: best}',
        ALL_WEEK]))
    d = demand.demand(wall(2026, 10, 26, 1), rules_, tz, LA)
    assert d["next"] == {"good": "2026-10-27T00:00:00-07:00", "best": "2026-10-26T06:00:00-07:00"}


def test_stamps_are_the_band_s_zone_not_the_schedule_s(env):
    rules_, tz, _ = demand.schedule(env)
    d = demand.demand(NOW, rules_, tz, None)               # 13:00 on the schedule's clock
    assert d["until"] == admission._stamp(datetime(2026, 10, 30, 23, tzinfo=UTC), None)
    tokyo = demand.demand(NOW, rules_, tz, ZoneInfo("Asia/Tokyo"))
    assert tokyo["until"] == "2026-10-31T08:00:00+09:00" and tokyo["band"] == "middle"


def test_demand_at_datetime_s_end_is_none(env):
    rules_, tz, _ = demand.schedule(env)
    assert demand.demand(datetime(9999, 12, 31, 12, tzinfo=UTC), rules_, tz, UTC) is None


# ---- band.json ---------------------------------------------------------------------------

def test_none_entry_carries_demand_from_the_write(env):
    answer = admit(env, rising(61, 62))
    assert (answer["window"], answer["band"]) == ("none", "middle")
    b = admission.read_band(env)
    assert b["window"] == "none" and set(b["demand"]) == {"band", "until", "next"}
    assert b["demand"]["band"] == "middle"
    assert b["accounts"][b["sessions"][SID]]["demand"] == b["demand"]
    assert b["demand"]["until"] == admission._stamp(datetime(2026, 10, 30, 23, tzinfo=UTC), None)


def test_the_record_verb_writes_demand_too(env):
    ledger(env, rising(61, 62))
    admission.record(SID, json.dumps({"kind": "end"}), env, NOW)
    assert admission.read_band(env)["demand"]["band"] == "middle"


def test_the_line_on_the_entry_a_write_draws():
    """band()'s entry through the settings a write builds, in a fixed zone."""
    rows = rising(61, 62) + [spawn(at(5), "h1"), spawn(at(4), "h2"), spawn(at(3), "h3")]
    s = {**rules.admission({}), "demand": admission._demand_once({"HOME": "/nonexistent"})}
    b = admission.band(rows, NOW, s, tz=UTC)
    assert b["demand"]["until"] == "2026-10-30T23:00:00+00:00"
    assert admission.band_line(b, NOW) == ("no 5h window · 7d 62% · week resets Fri 21:00 · "
                                           "band middle to 23:00 · 3 helpers · observe")


def test_five_hour_never_reads_the_file(env, monkeypatch):
    rows = [reading(at(10), L5(40, 50))]
    plain = admit(env, rows)
    entry = admission.read_band(env)
    user_file(env).write_text("tz: [\n")                   # it would warn
    calls = []
    real = demand.schedule
    monkeypatch.setattr(demand, "schedule", lambda e: calls.append(1) or real(e))
    again = admit(env, rows)
    assert calls == [] and again == plain and "band" not in again and "notes" not in again
    assert admission.read_band(env) == entry and "demand" not in entry


def test_one_read_for_two_none_logins_and_none_for_a_five_hour_one(env, monkeypatch):
    other = datetime(2026, 11, 4, 15, tzinfo=UTC)
    third = datetime(2026, 11, 3, 15, tzinfo=UTC)
    rows = rising(61, 62) + rising(50, 51, S2, other) + [reading(at(9), L5(40, 50, week=third), "bands-sess-4444-5555")]
    calls = []
    real = demand.schedule
    monkeypatch.setattr(demand, "schedule", lambda e: calls.append(1) or real(e))
    admit(env, rows)
    b = admission.read_band(env)
    assert calls == [1]
    with_demand = [k for k, a in b["accounts"].items() if "demand" in a]
    assert len(b["accounts"]) == 3 and len(with_demand) == 2
    assert all(b["accounts"][k]["window"] == "none" for k in with_demand)


def test_a_none_answer_says_a_bad_file_and_reads_the_shipped(env):
    user_file(env).write_text("tz: [\n")
    answer = admit(env, rising(61, 62))
    assert answer["band"] == "middle" and len(answer["notes"]) == 1


def test_admit_answer_keys(env):
    assert set(admit(env, rising(61, 62))) == {"verdict", "mode", "text", "peak", "window", "resume_at", "band"}
    assert set(admit(env, [reading(at(10), L5(40, 50))])) == {"verdict", "mode", "text", "peak", "window", "resume_at"}


# ---- no hold -----------------------------------------------------------------------------

def _stale_wait():
    return [reading(at(30), L5(60, five=at(20))),
            {"ts": iso(at(5)), "session": S2, "kind": "verdict", "tool_use_id": "toolu_8", "verdict": "stale",
             "mode": "observe", "peak": None, "P": None, "T": None, "family": "opus", "type": "general-purpose"},
            spawn(at(5), "8", S2)]


# scenario -> (its rows, its window, the verdict attended, the verdict unattended)
SCENES = {
    "admitted": ([reading(at(10), L5(10))], "five_hour", "admitted", "admitted"),
    "unread": ([], "five_hour", "unread", "unread"),
    "stale": ([reading(at(30), L5(60, five=at(20)))], "five_hour", "stale", "stale"),
    "wait": (_stale_wait(), "five_hour", "wait", "wait"),
    "denied": ([reading(at(10), L5(50, 98))], "five_hour", "denied", "denied"),
    "hot": ([reading(at(10), L5(96))], "five_hour", "deferred", "not-started"),
    "none-admitted": (rising(61, 62), "none", "admitted", "admitted"),
    "none-denied": (rising(97, 98), "none", "denied", "denied"),
}


@pytest.mark.parametrize("scene", sorted(SCENES))
@pytest.mark.parametrize("attended", [True, False], ids=["attended", "unattended"])
def test_band_never_holds(env, scene, attended):
    rows, mode, *verdicts = SCENES[scene]
    want = verdicts[0] if attended else verdicts[1]
    rows = [start(attended)] + rows
    seen = []
    for name in ("avoid", "middle", "good", "best"):       # NOW is a Friday, in the first rule
        user_file(env).write_text(rule_file(
            [f'{{days: Fri, from: "00:00", to: "24:00", band: {name}}}',
             '{days: Mon-Sun, from: "00:00", to: "24:00", band: other}'], "UTC"))
        answer = admit(env, rows)
        assert (answer["verdict"], answer["window"]) == (want, mode), name
        assert answer.get("band") == (name if mode == "none" else None)
        seen.append({k: v for k, v in answer.items() if k != "band"})
        s = {**rules.admission({}), "demand": admission._demand_once(env)}
        assert admission.decide(rows, ASK, SID, NOW, s, tz=UTC)["verdict"] == want
    assert all(x == seen[0] for x in seen)


@pytest.mark.parametrize("attended", [True, False], ids=["attended", "unattended"])
def test_none_unattended_runs_to_ceiling_7d(env, attended):
    user_file(env).write_text(rule_file(['{days: Mon-Sun, from: "00:00", to: "24:00", band: avoid}'], "UTC"))
    c = rules.admission({})["ceiling_7d"]
    for p, want in ((10, "admitted"), (c - 2, "admitted"), (c - 0.5, "admitted"), (c, "denied"), (c + 1, "denied")):
        answer = admit(env, [start(attended)] + rising(p - 1, p))
        assert (answer["window"], answer["band"], answer["verdict"]) == ("none", "avoid", want), p


# ---- the line's twin pins sit in the module's fixture; these read it ----------------------

def _cases():
    p = ROOT / "plugin" / "hooks" / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = p.read_text()
    now = datetime.fromisoformat(re.search(r"^const NOW = Date\.parse\('(.*)'\)$", text, re.M).group(1))
    return json.loads(re.search(r"^const BAND_NONE_CASES = '(.*)'$", text, re.M).group(1)), now


def test_the_fixture_holds_the_record_s_line_and_the_corners():
    cases, now = _cases()
    lines = [line for _, line in cases]
    assert "no 5h window · 7d 62% · week resets Fri 13:00 · band avoid to 11:00 · 3 helpers · observe" in lines
    assert "no 5h window · band best to Sun 20:00" in lines
    assert sum("demand" in e for e, _ in cases) >= 20
    assert any("demand" in e and "window" not in e and l.startswith("5h ") for e, l in cases)     # a stray
    five = [e for e, l in cases if e.get("P", 0) is None and e.get("bound") == "seven_day"
            and "window" not in e and l.startswith("5h no reading · week resets ")]
    assert five                                            # S43's refuter F4
    for entry, line in cases:
        assert admission.band_line(entry, now) == line, entry


def test_a_five_hour_line_with_a_stray_demand_is_byte_for_byte():
    b = {"window": "five_hour", "P": 72, "peak": 81, "ceiling": 97, "resetsAt": "2026-10-30T22:00:00+00:00",
         "until": "2026-10-30T22:00:00+00:00", "bound": "five_hour", "running": 2, "room": 3, "mode": "observe"}
    stray = {**b, "demand": {"band": "avoid", "until": "2026-10-30T23:00:00+00:00", "next": {}}}
    assert admission.band_line(stray, NOW) == admission.band_line(b, NOW)
    assert admission.band_status(stray, NOW) is None


# ---- status and doctor -------------------------------------------------------------------

def none_band(**demand_):
    return {"window": "none", "at": iso(NOW), "mode": "observe", "demand": demand_}


def test_band_status_forms():
    b = none_band(band="avoid", until="2026-10-30T23:00:00+00:00",
                  next={"good": "2026-10-31T06:00:00+00:00", "best": "2026-10-30T23:30:00+00:00"})
    assert admission.band_status(b, NOW) == "band: avoid to 23:00; next good 06:00, best 23:30"
    b["demand"]["next"]["good"] = "2026-11-02T06:00:00+00:00"
    assert admission.band_status(b, NOW) == "band: avoid to 23:00; next good Mon 06:00, best 23:30"
    b["demand"]["next"]["good"] = "2026-10-30T19:00:00+00:00"      # past: not listed
    assert admission.band_status(b, NOW) == "band: avoid to 23:00; next best 23:30"
    b["demand"]["next"]["good"] = iso(NOW)                         # now itself is not in the future
    assert admission.band_status(b, NOW) == "band: avoid to 23:00; next best 23:30"
    del b["demand"]["next"]["best"]
    assert admission.band_status(b, NOW) == "band: avoid to 23:00"
    b["demand"]["next"] = "soon"
    assert admission.band_status(b, NOW) == "band: avoid to 23:00"
    del b["demand"]["next"]
    assert admission.band_status(b, NOW) == "band: avoid to 23:00"
    b["demand"]["until"] = iso(NOW)                                # the idle login's filing
    assert admission.band_status(b, NOW) is None
    assert admission.band_status({"window": "none", "at": iso(NOW)}, NOW) is None


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture
def metered(env, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    repo = tmp_path / "repo"
    repo.mkdir()
    e = dict(os.environ)
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, e)
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(ROOT / "tests/fixtures/meter/under-80.jsonl")}, e)
    return resolver.session_dir(resolver.state_dir(e), SID)


def write_band(env, b):
    d = admission.directory(env)
    d.mkdir(parents=True, exist_ok=True)
    (d / admission.BAND).write_text(json.dumps(b))


def test_status_shows_band(env, metered):
    rc, plain, _ = run("status")
    assert rc == 0
    now = datetime.now(UTC).replace(microsecond=0)
    until, best = now + timedelta(hours=2), now + timedelta(hours=3)
    write_band(env, {"window": "none", "at": iso(now), "demand": {
        "band": "avoid", "until": iso(until), "next": {"best": iso(best)}}})
    rc, out, _ = run("status")
    assert rc == 0 and out.startswith(plain)
    assert out[len(plain):] == f"band: avoid to {until:%H:%M}; next best {best:%H:%M}\n"


@pytest.mark.parametrize("b", [
    {"window": "five_hour", "P": 40, "demand": {"band": "avoid", "until": "2099-01-01T00:00:00+00:00"}},
    {"window": "none"},
    {"window": "none", "demand": {"band": "avoid", "until": "2020-01-01T00:00:00+00:00"}},
], ids=["five-hour", "no-demand", "past-its-end"])
def test_status_is_today_s_bytes_with_no_band_to_show(env, metered, b):
    plain = run("status")[1]
    write_band(env, b)
    assert run("status")[1] == plain


def test_status_survives_a_nest_under_band_max(env, metered):
    rc, plain, _ = run("status")
    d = admission.directory(env)
    d.mkdir(parents=True, exist_ok=True)
    (d / admission.BAND).write_text("[" * 65000)
    assert 65000 < admission.BAND_MAX
    assert admission.read_band(env) is None
    assert run("status")[:2] == (rc, plain)
    assert rc == 0


def test_status_json_carries_window_and_demand_only_on_none(env, metered):
    plain = json.loads(run("status", "--json")[1])
    assert "band" not in plain
    dem = {"band": "avoid", "until": "2099-01-01T00:00:00+00:00", "next": {}}
    write_band(env, {"window": "five_hour", "P": 40, "demand": dem})
    assert json.loads(run("status", "--json")[1]) == plain
    write_band(env, {"window": "none", "demand": dem})
    assert json.loads(run("status", "--json")[1]) == {**plain, "band": {"window": "none", "demand": dem}}
    write_band(env, {"window": "none"})
    assert json.loads(run("status", "--json")[1]) == {**plain, "band": {"window": "none"}}


def test_status_reads_the_session_s_account(env, metered):
    dem = {"band": "avoid", "until": "2099-01-01T00:00:00+00:00"}
    write_band(env, {"window": "five_hour", "P": 40, "accounts": {"k": {"window": "none", "demand": dem}},
                     "sessions": {SID: "k"}})
    assert run("status")[1].splitlines()[-1] == "band: avoid to Thu 00:00"


def test_doctor_is_silent_with_no_file_and_on_a_good_one(env):
    assert doctor._check_bands(env) == []
    load(env, rule_file([ALL_WEEK], "UTC"))
    assert doctor._check_bands(env) == []


def test_doctor_run_warns_and_never_fails_on_a_bad_file(env, tmp_path):
    e = {**os.environ, "PATH": str(tmp_path)}
    names = lambda rep: [c.name for c in rep.checks]       # noqa: E731
    clean = doctor.run(e, tmp_path)
    assert "bands" not in names(clean)
    user_file(env).write_text("tz: [\n")
    rep = doctor.run(e, tmp_path)
    [row] = [c for c in rep.checks if c.name == "bands"]
    assert (row.ok, row.warn) == (True, True)
    assert names(rep)[:len(names(clean))] == names(clean)
