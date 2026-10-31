"""Packet S35: the band per account. A reading's seven-day resetsAt keys its login; with two
or more keys in the ledger each session's band, fit, room and verdict use only its own
account's lines, and band.json carries `accounts` and `sessions` beside its old top level."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, config, hooks, rules

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
SA, SB, SC, SU = "sess-a-0000", "sess-b-1111", "sess-c-2222", "sess-u-3333"
NOW = datetime(2026, 10, 14, 20, 0, tzinfo=UTC)
A5, A7 = datetime(2026, 10, 14, 21, 10, tzinfo=UTC), datetime(2026, 10, 17, 5, 0, 30, tzinfo=UTC)
B5, B7 = datetime(2026, 10, 14, 22, 30, tzinfo=UTC), datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
KA, KB = "2026-10-17T05:00Z", "2026-10-21T22:00Z"


def iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def lims(pct, five, p7=None, seven=None):
    out = [{"kind": "five_hour", "percentUsed": pct, "resetsAt": iso(five)}]
    if seven is not None:
        out.append({"kind": "seven_day", "percentUsed": p7, "resetsAt": iso(seven)})
    return out


def reading(t, sid, pct, five, p7=None, seven=None):
    return {"ts": iso(t), "session": sid, "kind": "reading", "rateLimits": lims(pct, five, p7, seven)}


def spawn(t, sid, aid):
    return {"ts": iso(t), "session": sid, "kind": "spawn", "subagentType": "general-purpose",
            "model": None, "parentModel": "claude-opus-5-5", "background": True, "fork": False,
            "description": None, "tool_use_id": f"toolu_{aid}", "agentId": aid,
            "context": None, "rateLimits": []}


def at(m: int) -> datetime:
    return NOW - timedelta(minutes=m)


def two():
    """Two logins, interleaved: A (5h 21:10Z, 7d 81%) and B (5h 22:30Z, 7d 3%); B wrote last."""
    return [
        reading(at(30), SA, 60, A5, 80, A7), reading(at(25), SB, 10, B5, 3, B7),
        reading(at(10), SA, 70, A5, 81, A7), spawn(at(8), SA, "h1"),
        reading(at(5), SB, 12, B5, 3, B7), spawn(at(4), SB, "h2"), spawn(at(3), SB, "h3"),
    ]


def settings():
    return rules.admission({})


def mine(rows, sid):
    return admission.session_band(admission.bands(rows, NOW, settings(), tz=UTC), sid)


def test_s35_the_key_is_the_seven_day_reset_to_the_minute():
    assert admission.account(lims(1, A5, 80, A7)) == KA                  # 05:00:30 → 05:00
    off = [{"kind": "seven_day", "percentUsed": 3, "resetsAt": "2026-10-21T15:00:59-07:00"}]
    assert admission.account(off) == KB
    assert admission.account(lims(1, A5)) is None                        # no seven-day: unknown
    assert admission.account([{"kind": "seven_day", "percentUsed": 3, "resetsAt": None}]) is None
    assert admission.account(None) is None and admission.account("x") is None


def test_s35_two_accounts_each_session_draws_its_own_window():
    rows = two()
    a, b = mine(rows, SA), mine(rows, SB)
    assert (a["P"], a["resetsAt"], a["P7"], a["running"]) == (70, iso(A5), 81, 1)
    assert (b["P"], b["resetsAt"], b["P7"], b["running"]) == (12, iso(B5), 3, 2)
    acct = lambda key: [r for r in rows if r["session"] == {KA: SA, KB: SB}[key]]
    assert a == admission.band(acct(KA), NOW, settings(), tz=UTC)       # A's lines only
    assert b == admission.band(acct(KB), NOW, settings(), tz=UTC)
    assert a["room"] != b["room"]
    top = admission.bands(rows, NOW, settings(), tz=UTC)
    assert {k: v for k, v in top.items() if k not in ("accounts", "sessions")} == \
        top["accounts"][KB]                                              # the current login's: B wrote last
    assert top["sessions"] == {SA: KA, SB: KB} and set(top["accounts"]) == {KA, KB}


def test_s35_a_verdict_projects_from_its_own_account():
    rows, req = two(), {"subagentType": "general-purpose", "parentModel": "claude-opus-5-5",
                        "rateLimits": []}
    s = settings()
    assert admission.decide(rows, req, SA, NOW, s)["P"] == 70
    assert admission.decide(rows, req, SB, NOW, s)["P"] == 12
    fresh = {**req, "rateLimits": lims(1, B5, 2, B7)}                  # a new B session's own reading
    want = admission.decide([r for r in rows if r["session"] == SB], fresh, SC, NOW, s)
    assert admission.decide(rows, fresh, SC, NOW, s) == want


def test_s35_a_lone_account_is_unchanged():
    rows = [reading(at(30), SA, 60, A5, 80, A7), reading(at(20), SC, 64, A5, 80, A7),
            reading(at(10), SA, 70, A5, 81, A7), spawn(at(8), SA, "h1"),
            reading(at(6), SU, 71, A5)]                                  # an unkeyed one too
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    assert b == admission.band(rows, NOW, settings(), tz=UTC) and "accounts" not in b
    assert admission.session_band(b, SA) is b
    req = {"subagentType": "general-purpose", "rateLimits": []}
    assert admission.decide(rows, req, SA, NOW, settings())["P"] == 71


def test_s35_a_session_with_no_account_draws_the_top_level():
    rows = two() + [reading(at(2), SU, 50, A5), spawn(at(1), SC, "h4")]
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    top = {k: v for k, v in b.items() if k not in ("accounts", "sessions")}
    assert top["P"] == 12                                                # the current login's, B's
    for sid in (SC, SU, "never-seen", None):
        assert admission.session_band(b, sid) is b
    assert admission.band_line(admission.session_band(b, SC), NOW) == admission.band_line(top, NOW)
    assert admission.session_band(None, SA) is None


def test_s35_a_keyed_session_s_unkeyed_reading_stays_in_its_account():
    rows = two() + [reading(at(1), SA, 73, A5)]
    assert mine(rows, SA)["P"] == 73 and mine(rows, SB)["P"] == 12


def test_s35_an_old_shape_or_odd_band_json_reads_as_its_top_level():
    old = {"P": 72, "mode": "observe", "at": iso(NOW)}
    assert admission.session_band(old, SA) is old
    for odd in ({**old, "sessions": {SA: KA}}, {**old, "sessions": [SA], "accounts": {KA: {}}},
                {**old, "sessions": {SA: KA}, "accounts": {KA: [1]}},
                {**old, "sessions": {SA: 3}, "accounts": {"3": {"P": 1}}}):
        assert admission.session_band(odd, SA) is odd


def test_s35_band_json_is_capped():
    rows = []
    for i in range(20):                                                  # 20 keys, 300 sessions
        seven = B7 + timedelta(hours=i)
        for j in range(15):
            rows.append(reading(at(40) + timedelta(seconds=i * 15 + j), f"s{i}-{j}", 5, B5, 1, seven))
    b = admission.bands(rows, NOW, settings(), tz=UTC)
    assert len(b["accounts"]) == admission.MAX_ACCOUNTS
    assert len(b["sessions"]) <= admission.MAX_SESSIONS
    assert set(b["sessions"].values()) <= set(b["accounts"])
    assert len(json.dumps(b)) < admission.BAND_MAX


def test_s35_record_writes_each_session_s_band_and_the_prompt_shows_it(monkeypatch, tmp_path):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 97.0)
    now = datetime.now(UTC)
    for sid, pct, five, p7, seven in ((SA, 70, 2, 81, 50), (SB, 12, 3, 3, 150)):
        obj = {"kind": "reading", "rateLimits": lims(pct, now + timedelta(hours=five), p7,
                                                     now + timedelta(hours=seven))}
        admission.record(sid, json.dumps(obj), dict(os.environ), now)
    b = json.loads((config.state_dir(os.environ) / "admission" / "band.json").read_text())
    assert set(b["sessions"]) == {SA, SB}

    def line(sid):
        ctx = hooks.user_prompt_submit({"session_id": sid})["hookSpecificOutput"]["additionalContext"]
        return [x for x in ctx.split("\n\n") if x.startswith("5h ")]
    assert line(SA)[0].startswith("5h 70% → ") and "7d 81%" in line(SA)[0]
    assert line(SB)[0].startswith("5h 12% → ") and "7d 3%" in line(SB)[0]
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    cwd = str(tmp_path)
    assert hooks._lifetime(cwd, os.environ, SA) == ("1h", "within plan usage, 5h 70%")
    assert hooks._lifetime(cwd, os.environ, SB) == ("1h", "within plan usage, 5h 12%")


def _fixture() -> tuple:
    p = ROOT / "plugin" / "hooks" / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = p.read_text()
    get = lambda name: re.search(rf"^const {name} = '(.*)'$", text, re.M).group(1)
    now = re.search(r"^const NOW = Date\.parse\('(.*)'\)$", text, re.M).group(1)
    return json.loads(get("BAND_TWO")), get("BAND_TWO_LINE"), get("BAND_LINE"), datetime.fromisoformat(now)


def test_s35_python_draws_the_module_s_two_account_fixture():
    b, line, top, now = _fixture()
    assert admission.band_line(admission.session_band(b, "sess-1"), now) == line
    assert admission.band_line(admission.session_band(b, "sess-9"), now) == top
