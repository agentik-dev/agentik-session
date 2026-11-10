"""Packet S53 fix round 1, NICE n15: the mod's admissionLine draws the mix part Python's
band_line does. plugin/hooks/session.test.ts holds MIX_CASES, [entry, line] each at its NOW;
the module's tests assert admissionLine gives each line, and these assert band_line does,
and that the line's mix part is _mix_part's, so the two twins draw one text."""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from claude_session import admission

TS = Path(__file__).resolve().parent.parent / "plugin" / "hooks" / ("session.test." + "ts")


def _ts(name: str) -> str:
    if not TS.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return re.search(rf"^const {name} = '(.*)'$", TS.read_text(), re.M).group(1)


def _now() -> datetime:
    if not TS.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return datetime.fromisoformat(re.search(r"^const NOW = Date\.parse\('(.*)'\)$", TS.read_text(), re.M).group(1))


def test_s53_n15_band_line_draws_the_module_s_mix_cases():
    now, cases = _now(), json.loads(_ts("MIX_CASES"))
    assert len(cases) >= 15
    for entry, line in cases:
        assert admission.band_line(entry, now) == line, entry


def test_s53_n15_each_case_s_mix_part_is_python_s():
    now = _now()
    for entry, line in json.loads(_ts("MIX_CASES")):
        part = " · ".join(admission._mix_part(entry.get("mix"), now))
        assert (part in line) if part else (" · mix " not in line), entry


def test_s53_n15_the_cases_cover_on_phase_reset_absent_and_malformed():
    cases = json.loads(_ts("MIX_CASES"))
    mixes = [e.get("mix", "absent") for e, _ in cases]
    assert any(isinstance(m, dict) and m.get("reset") is True for m in mixes)
    assert any(isinstance(m, dict) and (m.get("phase") or {}).get("n") == 1 for m in mixes)
    assert "absent" in mixes and any(m is not None and not isinstance(m, dict) for m in mixes)
    assert any(" by " in line for _, line in cases)
    assert sum(" · mix " not in line for _, line in cases) >= 4


def test_s53_n15_the_module_s_hand_case():
    """The module's own corner (an `until` that is not a stamp, no resets count), drawn alike."""
    entry = {"P7": 26, "mix": {"points": {"fable": 1}, "budgets": {"fable": 50}, "until": 7}}
    assert admission.band_line(entry, _now()) == "5h no reading · 7d 26% · mix fable 1/50 · next none"
