import pytest

from claude_session.budget import (CLEAR, EXHAUSTED, NOTICE, RESERVE, UNKNOWN,
                                   WINDDOWN, Policy, zone_for)


def test_zones_escalate():
    p = Policy()                      # the shipped defaults
    p.validate()
    assert p.reserve_floor == 92
    assert zone_for(10, p) == CLEAR
    assert zone_for(80, p) == NOTICE
    assert zone_for(90, p) == WINDDOWN
    assert zone_for(92, p) == RESERVE
    assert zone_for(100, p) == EXHAUSTED
    assert zone_for(None, p) == UNKNOWN     # no meter, no opinion


def test_shipped_defaults_are_self_consistent():
    """Every zone must be reachable, or a threshold is decoration."""
    p = Policy()
    p.validate()
    assert {zone_for(u, p) for u in (0, 85, 91, 95, 100)} == {
        CLEAR, NOTICE, WINDDOWN, RESERVE, EXHAUSTED}


def test_reserve_floor_moves_with_the_reserve():
    assert Policy(reserve_pct=25, notice_pct=60, winddown_pct=70).reserve_floor == 75
    assert zone_for(80, Policy(reserve_pct=25, winddown_pct=70)) == RESERVE


def test_policy_validation_rejects_incoherent_thresholds():
    Policy(reserve_pct=10, notice_pct=70, winddown_pct=85).validate()
    with pytest.raises(ValueError):
        Policy(reserve_pct=10, notice_pct=95, winddown_pct=80).validate()
    with pytest.raises(ValueError):
        # wind-down above the reserve floor can never be observed
        Policy(reserve_pct=50, notice_pct=40, winddown_pct=60).validate()
    with pytest.raises(ValueError):
        Policy(reserve_pct=0).validate()
