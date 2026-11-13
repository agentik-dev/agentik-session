"""Packet pl1: the line the plugin prints at each prompt, tidied. The owner's state draws the
owner's tidied line through the prompt hook (R1); no zone word for `clear` (R2); the facts
that left are `status`'s (R3); the pacing text points there (R4); the mix off reads as on (R5).
Every state here is made up, under the per-test temp HOME conftest gives."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, budget, hooks, rules

UTC = timezone.utc
SID = "test-sess-0000-1111-2222"
TS = Path(__file__).resolve().parent.parent / "plugin" / "hooks" / ("session.test." + "ts")
OWNER_LINE = "no 5h window · 7d 61% · resets 1 · week resets Fri 13:00 · 14 helpers"


def _friday_after(now: datetime) -> str:
    d = (now + timedelta(days=1)).date()
    while d.weekday() != 4:
        d += timedelta(days=1)
    return f"{d.isoformat()}T13:00:00+00:00"


def owner_state(now: datetime | None = None, mix: bool = True) -> dict:
    """The owner's state: no 5h window, 7d 61, the mix 33/50 and 27/50 with next fable and one
    reset, the week's reset on a Friday at 13:00, the band best to two hours on, 14 helpers,
    the mode observe."""
    now = now or datetime.now(UTC)
    b = {"window": "none", "P7": 61, "until": _friday_after(now), "bound": "seven_day",
         "running": 14, "mode": "observe", "at": now.isoformat(timespec="seconds"),
         "demand": {"band": "best", "until": (now + timedelta(hours=2)).isoformat(timespec="seconds")}}
    if mix:
        b["mix"] = {"points": {"fable": 33, "opus": 27}, "budgets": {"fable": 50, "opus": 50},
                    "next": "fable", "reset": False, "resets_left": 1, "until": None}
    return b


def write_band(b: dict) -> None:
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    (d / "band.json").write_text(json.dumps(b))


def prompt_bits() -> list:
    out = hooks.user_prompt_submit({"session_id": SID})
    return out["hookSpecificOutput"]["additionalContext"].split("\n\n") if out else []


def _band_bit(bits: list) -> str:
    [line] = [x for x in bits if x.startswith("no 5h window")]
    return line


# ---- acceptance 1: the owner's state, through the prompt hook ----

def test_pl1_1_the_owner_s_state_draws_the_owner_s_tidied_line(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 10.0)
    write_band(owner_state())
    line = _band_bit(prompt_bits())
    assert line == OWNER_LINE
    for word in ("mix", "fable", "opus", "next", "band", "best", "observe"):
        assert word not in line.split(), word


def test_pl1_1_the_module_s_fixture_is_the_same_line():
    """The mod's twin draws PL1_OWNER as PL1_OWNER_LINE; Python draws the same text."""
    if not TS.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = TS.read_text()

    def get(name):
        return re.search(rf"^const {name} = '(.*)'$", text, re.M).group(1)
    now = datetime.fromisoformat(re.search(r"^const NOW = Date\.parse\('(.*)'\)$", text, re.M).group(1))
    assert get("PL1_OWNER_LINE") == OWNER_LINE
    assert admission.band_line(json.loads(get("PL1_OWNER")), now) == OWNER_LINE


# ---- acceptance 2: no zone word for `clear`; every other zone as at the pin ----

@pytest.mark.parametrize("zone,said", [
    (budget.CLEAR, None),
    (budget.UNKNOWN, None),                       # not said at the pin either
    (budget.NOTICE, "Sitting budget: 'notice' zone."),
    (budget.WINDDOWN, "Sitting budget: 'wind-down' zone."),
    (budget.RESERVE, "Sitting budget: 'reserve' zone. The remainder is the wrap-up reserve."),
    (budget.EXHAUSTED, "Sitting budget: 'exhausted' zone. The remainder is the wrap-up reserve."),
])
def test_pl1_2_the_prompt_says_the_zone_unless_clear(monkeypatch, zone, said):
    monkeypatch.setattr(hooks.budget, "zone_for", lambda *a, **k: zone)
    write_band(owner_state())
    text = "\n\n".join(prompt_bits())
    assert "clear" not in text
    if said is None:
        assert "Sitting budget" not in text
    else:
        assert said in text


def test_pl1_2_the_module_s_session_line_drops_clear_alone():
    """The mod's session line: its tests pin each zone; `clear` says no word there."""
    if not TS.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = TS.read_text()
    rest = re.search(r"^const REST = '(.*)'$", text, re.M).group(1)
    assert rest == "ctx 64% · turns 6% · 207s old"
    for zone in ("notice", "wind-down", "reserve", "exhausted", "unknown"):
        assert f"['{zone}', ' · {zone}']" in text
    assert "['clear', '']" in text


# ---- acceptance 5: the mix off reads as on (less the resets count R1 keeps) ----

def test_pl1_5_the_mix_off_reads_as_on(monkeypatch):
    monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: 10.0)
    now = datetime.now(UTC)
    on = owner_state(now)
    write_band(owner_state(now, mix=False))
    off_line = _band_bit(prompt_bits())
    assert off_line == OWNER_LINE.replace(" · resets 1", "")
    write_band(on)
    assert _band_bit(prompt_bits()) == OWNER_LINE
    on["mix"]["resets_left"] = None               # a mix with no resets count: the same line
    write_band(on)
    assert _band_bit(prompt_bits()) == off_line


def test_pl1_5_the_mix_still_counts_and_advises():
    """R5: the mix is computed as before; only its words left the line."""
    m = owner_state()["mix"]
    assert admission.mix_status(m) == "mix: fable 33/50 · opus 27/50 · next fable · resets 1"
    assert "spend mix" in rules.render({"admission": {"mix": {"shares": {"opus": 1}}}})


# ---- acceptance 3: `status` shows what left the line; `--json` holds it under new keys ----

def run(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture
def metered(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    e = dict(os.environ)
    root = Path(__file__).resolve().parent.parent
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, e)
    hooks.post_tool_use({"session_id": SID,
                         "transcript_path": str(root / "tests/fixtures/meter/under-80.jsonl")}, e)


def test_pl1_3_status_shows_the_mix_the_next_family_the_band_and_the_mode(metered):
    rc, plain, _ = run("status")
    assert rc == 0 and plain.splitlines()[0].startswith("session ")
    assert " zone " in plain.splitlines()[0]                  # status keeps the zone's word
    b = owner_state()
    write_band(b)
    rc, out, _ = run("status")
    assert rc == 0 and out.startswith(plain)
    until = datetime.fromisoformat(b["demand"]["until"])
    assert out[len(plain):].splitlines() == [
        f"band: best to {until:%H:%M}",
        "mix: fable 33/50 · opus 27/50 · next fable · resets 1",
        "admission mode: observe",
    ]


def test_pl1_3_status_json_holds_them_under_new_keys(metered):
    plain = json.loads(run("status", "--json")[1])
    assert "admission" not in plain and "band" not in plain
    b = owner_state()
    write_band(b)
    got = json.loads(run("status", "--json")[1])
    assert got == {**plain, "band": {"window": "none", "demand": b["demand"]},
                   "admission": {"mode": "observe", "mix": b["mix"]}}
    assert got["admission"]["mix"]["next"] == "fable"


def test_pl1_3_status_with_the_mix_off_says_no_mix(metered):
    plain = run("status")[1]
    write_band(owner_state(mix=False))
    tail = run("status")[1][len(plain):]
    assert "mix:" not in tail and tail.endswith("admission mode: observe\n")


# ---- acceptance 4: the pacing text names `agentik session status` for the next family ----

def test_pl1_4_rules_name_status_for_the_next_family(monkeypatch):
    from claude_session import resolver
    p = resolver._user_file(os.environ)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("defaults:\n  admission:\n    mix:\n      shares:\n        fable: 3\n        opus: 1\n")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    rc, out, _ = run("rules")
    text = " ".join(out.split())
    assert rc == 0 and "spend mix" in text
    assert "the family `agentik session status` names (its `mix:` line's `next`)" in text
    assert "band line's `next`" not in text
    assert "`reset now` is the owner's Fable reset in Settings" in text      # no other rule moved


# ---- review 1: F1, the band of a five-hour login with no reading yet; F2, a passed `until` ----

def test_pl1_r1_f1_the_band_of_a_five_hour_login_with_no_reading_is_status_s(metered):
    """S51's entry: `window: five_hour`, no P, no ceiling, a `demand`; the line drew the band at
    the pin (`5h no reading · … · band best to HH:MM`); now `status` and `--json` hold it."""
    plain_text = run("status")[1]
    plain = json.loads(run("status", "--json")[1])
    b = {**owner_state(mix=False), "window": "five_hour", "P": None, "peak": None, "ceiling": None}
    until = datetime.fromisoformat(b["demand"]["until"])
    assert admission.band_line(b).startswith("5h no reading · 7d 61% · ")
    assert "band" not in admission.band_line(b) and "best" not in admission.band_line(b)
    write_band(b)
    tail = run("status")[1][len(plain_text):].splitlines()
    assert tail == [f"band: best to {until:%H:%M}", "admission mode: observe"]
    got = json.loads(run("status", "--json")[1])
    assert got == {**plain, "band": {"window": "five_hour", "demand": b["demand"]},
                   "admission": {"mode": "observe"}}


def test_pl1_r1_f2_a_passed_until_prints_no_deadline(metered):
    plain = run("status")[1]
    now = datetime.now(UTC)
    b = owner_state(now)
    b["mix"] = {**b["mix"], "resets_left": 2,
                "until": (now - timedelta(hours=2)).isoformat(timespec="seconds")}
    write_band(b)
    tail = run("status")[1][len(plain):]
    assert "mix: fable 33/50 · opus 27/50 · next fable · resets 2\n" in tail
    assert " by " not in tail
    ahead = (now + timedelta(days=2)).replace(microsecond=0)
    b["mix"]["until"] = ahead.isoformat()
    write_band(b)
    assert f"resets 2 by {ahead:%a} {ahead:%H:%M}\n" in run("status")[1]
