"""Packet S53: the spend mix, family shares of the week and the Fable resets.

`admission.mix` is a pure function of one login's rows, `now` and `admission.mix`'s
settings; spend reaches the ledger as a `spend` field the `record` verb sets on a `reading`
line from the meter's state (its own turns and its helpers', each under its own model).
Tests 7(a) to 7(f) by name, each on its own ledger and transcript under the test's temp
state root."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, config, meter, resolver, rules

UTC = timezone.utc
A, B = "s53-sess-aaaa-0000-1111", "s53-sess-bbbb-0000-1111"
WEEK = datetime(2026, 11, 16, 23, 0, tzinfo=UTC)          # the week's resetsAt
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
FIVE = NOW + timedelta(hours=2)


def iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds")


def zulu(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def reading(t, seven, sid=A, spend=None, week=WEEK, five=None):
    lim = [{"kind": "seven_day", "percentUsed": seven, "resetsAt": zulu(week)}]
    if five is not None:
        lim.insert(0, {"kind": "five_hour", "percentUsed": five, "resetsAt": zulu(FIVE)})
    r = {"ts": iso(t), "session": sid, "kind": "reading", "rateLimits": lim}
    return {**r, "spend": spend} if spend is not None else r


def settings(**mix):
    s = rules.admission({})
    return {**s, "mix": rules.mix(mix)} if mix else s


def user_mix(**mix):
    """The user layer's `defaults.admission.mix` (F5): every record and band write reads it."""
    p = resolver._user_file(os.environ)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["defaults:", "  admission:", "    mix:"]
    for k, v in mix.items():
        if isinstance(v, dict):
            lines += [f"      {k}:"] + [f"        {f}: {x}" for f, x in v.items()]
        else:
            lines.append(f"      {k}: {v}")
    p.write_text("\n".join(lines) + "\n")


def rec(sid, pct, now):
    admission.record(sid, json.dumps({"kind": "reading", "rateLimits": reading(now, pct)["rateLimits"]}),
                     dict(os.environ), now)


def ledger_lines():
    d = admission.directory(os.environ)
    return [json.loads(x) for p in sorted(d.glob("ledger*.jsonl")) for x in p.read_text().splitlines()]


def band_file():
    return json.loads((admission.directory(os.environ) / "band.json").read_text())


def by_state(sid, by):
    sdir = config.state_dir(os.environ) / "sessions" / sid
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "meter-state.json").write_text(json.dumps({"own": {"by": by}}))


def at(h, m=0):
    return NOW.replace(hour=h, minute=m)


# ---- (a) mix off: the band line and band.json as before ----

GOLDEN_LINE = "5h 40% → 52% · ceiling 97 · resets 14:00 (2h00) · 0 helpers, room for 18 · 0 deferred · 7d 40%"


def test_s53_a_mix_off_band_json_and_line_unchanged():
    rows = [reading(at(11), 40, A, {"fable": 3.0}, five=40),
            reading(at(11, 30), 40, B, {"opus": 1.0}, five=40)]
    off = admission.band(rows, NOW, settings(), tz=UTC)
    assert "mix" not in off and "mix" not in settings()
    assert off == {"P": 40, "peak": 52.0, "ceiling": 97, "resetsAt": "2026-11-12T14:00:00+00:00",
                   "until": "2026-11-12T14:00:00+00:00", "bound": "five_hour", "running": 0,
                   "room": 18, "deferred": 0, "P7": 40, "mode": "observe", "at": iso(NOW),
                   "window": "five_hour", "slot": "Mon-2300Z"}
    assert admission.band_line(off, NOW) == GOLDEN_LINE
    on = admission.band(rows, NOW, settings(shares={"fable": 1, "opus": 1}), tz=UTC)
    assert {k: v for k, v in on.items() if k != "mix"} == off       # the mix only adds
    assert admission.band_line(on, NOW) == GOLDEN_LINE + " · resets 0"     # pl1 R1: the shares are status's
    assert admission.mix_status(on["mix"], NOW) == "mix: fable 30/50 · opus 10/50 · next opus · resets 0"
    assert "spend mix" not in rules.render({})
    assert "spend mix" in rules.render({"admission": {"mix": {"shares": {"opus": 1}}}})


def test_s53_a_mix_off_records_no_spend(tmp_path):
    sdir = config.state_dir(os.environ) / "sessions" / A
    _meter_state(tmp_path, sdir)
    admission.record(A, json.dumps({"kind": "reading", "rateLimits": reading(NOW, 40)["rateLimits"]}),
                     dict(os.environ), NOW)
    line = json.loads((admission.directory(os.environ) / "ledger.jsonl").read_text().splitlines()[-1])
    assert "spend" not in line and sorted(line) == ["kind", "rateLimits", "session", "ts"]
    band = json.loads((admission.directory(os.environ) / "band.json").read_text())
    assert "mix" not in band


def test_s53_stdin_never_carries_spend():
    text = json.dumps({"kind": "reading", "rateLimits": [], "spend": {"fable": 1}})
    with pytest.raises(admission.AdmissionError) as e:
        admission.record(A, text, dict(os.environ), NOW)
    assert e.value.code == 2


# ---- (b) points from spend: Fable and Opus 3:1 at P7 40 ----

def test_s53_b_points_follow_spend_and_next_follows_shares():
    rows = [reading(at(9), 30, A, {"fable": 1.0}), reading(at(9, 5), 31, B, {"opus": 0.5}),
            reading(at(11), 40, A, {"fable": 3.0}), reading(at(11, 30), 40, B, {"opus": 1.0})]
    m = admission.mix(rows, NOW, settings(shares={"fable": 1, "opus": 1})["mix"], tz=UTC)
    assert m["points"] == {"fable": 30.0, "opus": 10.0}
    assert (m["budgets"], m["next"], m["reset"], m["resets_left"]) == (
        {"fable": 50, "opus": 50.0}, "opus", False, 0)
    m = admission.mix(rows, NOW, settings(shares={"fable": 4, "opus": 1})["mix"], tz=UTC)
    assert m["next"] == "fable"                     # 30 / 4 under 10 / 1
    m = admission.mix(rows[:0], NOW, settings(shares={"fable": 1})["mix"], tz=UTC)
    assert m["points"] is None and m["next"] is None
    assert admission._mix_part(m) == [] and admission.mix_status(m) == "mix: no reading"   # pl1


# ---- (c) Fable at 49 of 50 with two resets in hand: reset now ----

def test_s53_c_fable_at_its_cap_says_reset_now():
    rows = [reading(at(10), 60, A, {"fable": 4.9}), reading(at(10, 1), 60, B, {"opus": 1.1})]
    s = settings(shares={"fable": 3, "opus": 1}, resets=2, until="2026-11-13T18:00:00+00:00")
    m = admission.mix(rows, NOW, s["mix"], tz=UTC)
    assert (m["points"]["fable"], m["reset"], m["resets_left"]) == (49.0, True, 2)
    assert admission._mix_part(m) == ["reset now", "resets 2 by Fri 18:00"]     # pl1 R1
    assert admission.mix_status(m, NOW) == "mix: fable 49/50 · opus 11/50 · reset now · resets 2 by Fri 18:00"
    b = {"P7": 60, "mix": m}
    assert admission.band_line(b, NOW).endswith("7d 60% · reset now · resets 2 by Fri 18:00")


# ---- (d) a Fable reset: 75 to 26, resetsAt unchanged ----

def test_s53_d_a_fable_reset_is_detected_and_starts_a_phase():
    rows = [reading(at(8), 75, A, {"fable": 4.9}), reading(at(8, 1), 75, B, {"opus": 2.6}),
            reading(at(9), 26, A, {"fable": 4.9})]
    s = settings(shares={"fable": 3, "opus": 1}, resets=2)["mix"]
    m = admission.mix(rows, NOW, s, tz=UTC)
    assert (m["phase"]["n"], m["resets_left"]) == (1, 1)
    assert m["phase"]["drops"] == [{"at": "2026-11-12T09:00:00+00:00", "from": 75, "to": 26,
                                    "fable_est": 49.0}]
    assert m["points"] == {"fable": 0.0, "opus": 26.0}
    rows.append(reading(at(11), 36, A, {"fable": 5.9}))     # one more USD of Fable, this phase
    m = admission.mix(rows, NOW, s, tz=UTC)
    assert m["points"] == {"fable": 10.0, "opus": 26.0}      # Fable restarted, Opus stays
    assert (m["phase"]["since"], m["next"]) == ("2026-11-12T09:00:00+00:00", "fable")


# ---- (e) a week's reset (a new resetsAt) is not a Fable reset ----

def test_s53_e_a_new_week_is_not_a_fable_reset():
    old, new = WEEK - timedelta(days=7), WEEK
    now = old + timedelta(hours=1)
    rows = [reading(old - timedelta(hours=2), 75, A, {"fable": 4.9}, week=old),
            reading(old + timedelta(minutes=30), 3, A, {"fable": 5.0}, week=new)]
    m = admission.mix(rows, now, settings(shares={"fable": 1, "opus": 1}, resets=2)["mix"], tz=UTC)
    assert (m["phase"]["n"], m["phase"]["drops"], m["resets_left"]) == (0, [], 2)
    assert m["phase"]["since"] == "2026-11-09T23:00:00+00:00"
    assert m["points"] == {"fable": 3.0, "opus": 0.0}        # 0.1 of the session's 5.0 is this week's


# ---- (f) a helper's Opus turns inside a Fable session count as Opus ----

def _turn(i, model, side=False, inp=1000, out=100, cw=0, cr=0):
    return json.dumps({"type": "assistant", "requestId": f"r{i}", "isSidechain": side,
                       "timestamp": "2026-11-12T10:00:00Z",
                       "message": {"id": f"m{i}", "model": model, "usage": {
                           "input_tokens": inp, "output_tokens": out,
                           "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr}}})


def _meter_state(tmp_path: Path, sdir: Path) -> dict:
    tp = tmp_path / f"{A}.jsonl"
    tp.write_text("\n".join([_turn(1, "claude-fable-5-2", cw=1_000_000),
                             _turn(2, "claude-opus-5-5", side=True)]) + "\n")
    sub = tmp_path / A / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-h1.jsonl").write_text(_turn(3, "claude-opus-5-5", inp=1_000_000, out=0) + "\n")
    st: dict = {}
    m = meter.parse(tp, st, session_id=A)
    meter.save(sdir, m, st)
    return st


def test_s53_f_a_helper_s_opus_turns_count_as_opus(tmp_path):
    sdir = config.state_dir(os.environ) / "sessions" / A
    st = _meter_state(tmp_path, sdir)
    prices = settings(shares={"fable": 1})["mix"]["prices"]
    fable = (1000 * 8 + 100 * 40 + 1_000_000 * 10) / 1e6              # cache_write 1.25 x 8
    opus = (1000 * 5 + 100 * 25) / 1e6 + 5.0                           # the sidechain, the helper
    assert meter.spend(st, prices) == {"fable": round(fable, 6), "opus": round(opus, 6)}
    user_mix(shares={"fable": 1, "opus": 1})
    rec(A, 40, NOW)
    d = admission.directory(os.environ)
    line = ledger_lines()[-1]
    assert (line["kind"], line["account"]) == ("spend", "2026-11-16T23:00Z")
    assert line["spend"] == {"fable": round(fable, 6), "opus": round(opus, 6)}
    band = json.loads((d / "band.json").read_text())
    total = fable + opus
    assert band["mix"]["points"] == {"fable": round(40 * fable / total, 2),
                                     "opus": round(40 * opus / total, 2)}


# ---- fix round 1 (F1 to F8) ----

def test_s53_f1_a_huge_value_loses_no_line_and_renders_mix_off():
    sdir = config.state_dir(os.environ) / "sessions" / A
    sdir.mkdir(parents=True)
    (sdir / "resolved.json").write_text(json.dumps({"session": {"admission": {"ceiling": 10**400}}}))
    user_mix(shares={"fable": 10**400})
    rec(A, 40, NOW)
    assert [r["kind"] for r in ledger_lines()] == ["reading"]
    assert rules.mix({"shares": {"fable": 10**400}}) is None
    assert "spend mix" not in rules.render({"admission": {"mix": {"shares": {"fable": 10**400}}}})


def test_s53_f2_the_week_survives_the_ledger_s_rotation():
    user_mix(shares={"fable": 3, "opus": 1}, resets=2)
    t = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    by_state(A, {"fable": [0, 122500, 0, 0]})
    by_state(B, {"opus": [0, 104000, 0, 0]})
    rec(A, 75, t), rec(B, 75, t + timedelta(minutes=1)), rec(A, 26, t + timedelta(hours=1))
    assert band_file()["mix"]["points"] == {"fable": 0.0, "opus": 26.0}
    for h in (30, 60, 90):
        by_state(A, {"fable": [0, 122500 + h * 100, 0, 0]})
        rec(A, 26 + h // 30, t + timedelta(hours=h))
        m = band_file()["mix"]
        assert (m["phase"]["n"], m["resets_left"]) == (1, 1), h
        assert 25 < m["points"]["opus"] <= 26, h                 # B's spend kept past rotation
    assert not any(r["session"] == B for r in ledger_lines())   # B's lines are gone
    p = admission.directory(os.environ) / "mix.json"
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_s53_f3_a_reset_is_one_session_s_fall():
    s = settings(shares={"fable": 3, "opus": 1}, resets=3)["mix"]
    rows = [reading(at(8), 40, A, {"fable": 4.0}), reading(at(8, 1), 40, B, {"opus": 1.0})]
    for i in range(3):                                           # B's cached, stale list
        rows += [reading(at(9 + i), 43 + i, A, {"fable": 4.5 + i}), reading(at(9 + i, 1), 40, B)]
    assert admission.mix(rows, NOW, s, tz=UTC)["phase"]["n"] == 0
    rows = [reading(at(8), 75, A, {"fable": 4.9}), reading(at(8, 1), 75, B, {"opus": 2.6}),
            reading(at(9), 26, A), reading(at(9, 30), 27, B)]    # both see the one reset
    m = admission.mix(rows, NOW, s, tz=UTC)
    assert (m["phase"]["n"], m["resets_left"]) == (1, 2)


def test_s53_f4_spend_counts_from_the_last_reading_on_another_login():
    def rd(t, pct, sid, week, spend):
        return {**reading(t, pct, sid, spend, week=week)}
    w2 = WEEK + timedelta(hours=10)
    rows = [rd(NOW - timedelta(hours=5), 70, "sess-x", WEEK, {"fable": 10}),
            rd(NOW - timedelta(hours=4), 70, "sess-y", WEEK, {"opus": 1}),
            rd(NOW - timedelta(hours=3), 5, "sess-x", w2, {"fable": 10.5}),
            rd(NOW - timedelta(hours=2), 5, "sess-z", w2, {"opus": 0.5})]
    b = admission.bands(rows, NOW, settings(shares={"fable": 1, "opus": 1}), tz=UTC)
    assert b["accounts"]["2026-11-17T09:00Z"]["mix"]["points"] == {"fable": 2.5, "opus": 2.5}


def test_s53_f5_the_mix_comes_from_the_user_layer():
    user_mix(shares={"fable": 3, "opus": 1})
    sdir = config.state_dir(os.environ) / "sessions" / A
    sdir.mkdir(parents=True)
    (sdir / "resolved.json").write_text(json.dumps({"session": {"admission": {}}}))
    by_state(A, {"fable": [0, 100000, 0, 0]})
    by_state(B, {"opus": [0, 100000, 0, 0]})              # B has no resolved file
    rec(A, 40, NOW), rec(B, 40, NOW + timedelta(minutes=1))
    assert "mix" in band_file()
    assert [r["session"] for r in ledger_lines() if r["kind"] == "spend"] == [A, B]


def test_s53_f6_a_turn_counts_once_and_spend_never_falls(tmp_path):
    p = tmp_path / f"{A}.jsonl"
    p.write_text(_turn(1, "claude-fable-5-2") + "\n" + _turn(2, "claude-opus-5-5", side=True) + "\n")
    (tmp_path / A / "subagents").mkdir(parents=True)
    (tmp_path / A / "subagents" / "agent-h1.jsonl").write_text(_turn(2, "claude-opus-5-5", side=True) + "\n")
    prices = settings(shares={"opus": 1})["mix"]["prices"]
    st: dict = {}
    meter.parse(p, st, session_id=A)
    assert meter.spend(st, prices)["opus"] == round((1000 * 5 + 100 * 25) / 1e6, 6)
    before = meter.spend(st, prices)["fable"]
    p.write_text(_turn(7, "claude-fable-5-2") + "\n")                # rewritten, shorter
    meter.parse(p, st, session_id=A)
    assert meter.spend(st, prices)["fable"] >= before


def test_s53_f7_reset_needs_fable_in_shares_and_above_zero():
    rows = [reading(at(10), 60, A, {"opus": 1.0})]
    m = admission.mix(rows, NOW, settings(shares={"fable": 1, "opus": 1}, fable_cap=0.5, resets=2)["mix"])
    assert m["reset"] is False
    rows = [reading(at(10), 60, A, {"fable": 4.9}), reading(at(10, 1), 60, B, {"opus": 1.1})]
    assert admission.mix(rows, NOW, settings(shares={"opus": 1}, resets=2)["mix"])["reset"] is False


def test_s53_f8_an_until_past_is_not_drawn():
    rows = [reading(at(10), 60, A, {"fable": 1.0})]
    m = admission.mix(rows, NOW, settings(shares={"fable": 1}, until="2026-11-12T11:00:00+00:00")["mix"])
    assert m["until"] is None
    m["until"] = "2026-11-12T11:00:00+00:00"
    assert " by " not in " · ".join(admission._mix_part(m, NOW))
