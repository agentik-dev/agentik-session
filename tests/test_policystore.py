import pytest

from claude_session import budget, config, policystore


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    config.ensure_dirs()


def test_policy_roundtrip_and_privacy():
    policystore.save_policy(budget.Policy(reserve_pct=15, notice_pct=70, winddown_pct=80))
    p = policystore.load_policy()
    assert p.reserve_pct == 15 and p.reserve_floor == 85
    mode = (config.STATE_DIR / policystore.POLICY_FILE).stat().st_mode & 0o777
    assert oct(mode) == "0o600"


def test_invalid_saved_policy_falls_back_to_defaults():
    (config.STATE_DIR / policystore.POLICY_FILE).write_text(
        '{"reserve_pct": 50, "notice_pct": 40, "winddown_pct": 60}')
    p = policystore.load_policy()      # incoherent -> defaults, not a crash
    assert p.reserve_pct == budget.Policy().reserve_pct


def test_corrupt_policy_file_falls_back():
    (config.STATE_DIR / policystore.POLICY_FILE).write_text("{ not json")
    assert policystore.load_policy().reserve_pct == budget.Policy().reserve_pct
