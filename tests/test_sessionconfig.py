import json

import pytest

from claude_session import config, sessionconfig
from claude_session.sessionconfig import LAUNCH_ONLY, LIVE, SessionConfig

SID = "cfg-sess-0000-1111-2222"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()


def test_shipped_configs_cover_the_stated_use_cases():
    c = sessionconfig.load_configs()
    assert {"frontier", "local", "local-only", "scratch", "review"} <= set(c)
    assert c["frontier"].lane == "seat" and c["frontier"].model == "opus"
    # "run my entire infrastructure on just the local llm"
    assert c["local-only"].lane == "local-only"
    assert c["local-only"].model == "local/default"
    # a fun test project should not nag about a window it is not using
    assert c["scratch"].posture == "off"


def test_every_shipped_config_validates():
    for name, c in sessionconfig.load_configs().items():
        c.validate()


def test_local_defers_to_claude_locals_measured_subagent_default():
    """Forcing local/default here re-introduces the 54-tool prefill case that
    claude-local deliberately routes to sonnet."""
    assert sessionconfig.load_configs()["local"].subagent_model is None


def test_overlay_is_session_scoped_and_not_persisted():
    cfgs = sessionconfig.load_configs()
    assert cfgs["frontier"].posture == "signal"
    sessionconfig.save_overlay({"posture": "deny"})
    eff, ov = sessionconfig.effective("frontier")
    assert eff.posture == "deny" and ov["posture"] == "deny"
    # the stored config is untouched
    assert sessionconfig.load_configs()["frontier"].posture == "signal"


def test_clearing_the_overlay_restores_the_config():
    sessionconfig.save_overlay({"posture": "deny", "effort": "low"})
    sessionconfig.clear_overlay()
    eff, ov = sessionconfig.effective("frontier")
    assert ov == {} and eff.posture == "signal" and eff.effort == "xhigh"


def test_overlays_from_other_sessions_do_not_leak(monkeypatch):
    sessionconfig.save_overlay({"posture": "deny"})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "a-different-session-9999")
    eff, ov = sessionconfig.effective("frontier")
    assert ov == {} and eff.posture == "signal"


def test_no_session_id_means_no_overlay(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert sessionconfig.overlay_path() is None
    assert sessionconfig.save_overlay({"posture": "deny"}) is False


def test_active_config_from_env_wins(monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "review")
    assert sessionconfig.get_active() == "review"
    eff, _ = sessionconfig.effective()
    assert eff.name == "review" and eff.tools == "Read,Glob,Grep"


def test_a_launch_does_not_claim_the_launching_session(monkeypatch):
    """`start` execs a child with its own session id. Stamping the parent's id
    made a headless launch from inside a session claim that session was running
    the launched config -- observed live: doctor reported 'local-only' for an
    ordinary session because a background smoke test had run from it."""
    sessionconfig.set_active("local-only")
    assert sessionconfig.get_active() is None          # this session: unchanged
    assert sessionconfig.last_started() == "local-only"  # breadcrumb only
    monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "frontier")
    assert sessionconfig.get_active() == "frontier"     # the child knows, exactly


def test_saving_a_config_roundtrips_and_is_private():
    cfgs = sessionconfig.load_configs()
    cfgs["mine"] = SessionConfig(name="mine", description="x", effort="low")
    sessionconfig.save_configs(cfgs)
    back = sessionconfig.load_configs()
    assert back["mine"].effort == "low"
    assert back["frontier"].model == "opus"          # defaults still present
    mode = (config.STATE_DIR / sessionconfig.CONFIGS_FILE).stat().st_mode & 0o777
    assert oct(mode) == "0o600"


def test_corrupt_config_file_falls_back_to_defaults():
    (config.STATE_DIR / sessionconfig.CONFIGS_FILE).write_text("{ not json")
    assert "frontier" in sessionconfig.load_configs()


def test_unknown_fields_in_a_saved_config_are_tolerated():
    p = config.STATE_DIR / sessionconfig.CONFIGS_FILE
    p.write_text(json.dumps({"mine": {"effort": "low", "from_the_future": 1}}))
    assert sessionconfig.load_configs()["mine"].effort == "low"


def test_validation_rejects_nonsense():
    with pytest.raises(ValueError):
        SessionConfig(name="x", posture="maybe").validate()
    with pytest.raises(ValueError):
        SessionConfig(name="x", lane="cloud").validate()
    with pytest.raises(ValueError):
        SessionConfig(name="x", reserve_pct=0).validate()
    with pytest.raises(ValueError):
        SessionConfig(name="x", checkpoint={"clear": -1}).validate()


def test_launch_only_and_live_keys_are_disjoint_and_complete():
    fields = set(SessionConfig.__dataclass_fields__) - {"name", "description"}
    assert not (LAUNCH_ONLY & LIVE)
    assert LAUNCH_ONLY | LIVE == fields


def test_stale_overlays_are_pruned(tmp_path):
    import os, time
    p = sessionconfig.overlay_path()
    sessionconfig.save_overlay({"posture": "deny"})
    old = time.time() - 30 * 86400
    os.utime(p, (old, old))
    assert sessionconfig.prune_overlays() == 1
    assert not p.exists()
