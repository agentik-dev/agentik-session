"""nw6c-respawn-guards, a small change: every respawn key has one upper bound (G1, wish row
n419), and a first-mark file that does not parse or names another session is written again
at the next confirmed mark (G2, wish row n418). The refuter's probes of nw6b review 1, N5
and N6, are its red cases.

Every case runs on stand-ins: the fake effects of test_chain, a temp state folder and a temp
home, a made-up session; no launcher of this machine is read or signalled."""
import json
import os

import pytest

from claude_session import chain, cli, hooks, resolver
from test_chain import G, T0, _cli, _frun, _fx, _state, end, fake, hook, respawn_seq  # noqa: F401
from test_nw6_r4_signals import _call, _spawn_line

HUGE = 10 ** 400                     # the probe's value: an OverflowError at the pin
TOP = 10_000_000                     # the bound G1 names


def _profile(home, key, v):
    """A user profiles.yaml under a temp home naming `respawn.<key>: v` in profile `mine`."""
    d = home / ".claude" / "agentik"
    d.mkdir(parents=True, exist_ok=True)
    (d / "profiles.yaml").write_text(f"profiles:\n  mine:\n    respawn: {{{key}: {v}}}\n")
    return {**os.environ, "HOME": str(home), "CLAUDE_SESSION_PROFILE": "mine"}


# ---- G1: one upper bound for every respawn key ---------------------------------------------

def test_g1_the_bound_is_one_constant_beside_the_keys():
    assert resolver.RESPAWN_MAX == TOP
    assert float(TOP) == TOP


@pytest.mark.parametrize("key", resolver.RESPAWN_KEYS)
def test_g1_a_profiles_value_above_the_bound_is_refused_naming_it(key, fake, tmp_path):
    env = _profile(tmp_path / "home", key, HUGE)
    with pytest.raises(resolver.ResolveError, match=f"respawn.{key} must be a non-negative "
                                                    f"integer at most {TOP}"):
        chain.run_guards(fake.work, env, {})
    env = _profile(tmp_path / "home", key, TOP + 1)
    with pytest.raises(resolver.ResolveError, match=f"at most {TOP}"):
        chain.run_guards(fake.work, env, {})


@pytest.mark.parametrize("key", resolver.RESPAWN_KEYS)
def test_g1_the_bound_itself_is_accepted(key, fake, tmp_path):
    env = _profile(tmp_path / "home", key, TOP)
    assert chain.run_guards(fake.work, env, {})[key] == TOP


@pytest.mark.parametrize("key", ["settle", "hold_max"])
def test_g1_the_launchers_guards_refuse_a_flag_above_the_bound(key, fake):
    env = dict(os.environ)
    with pytest.raises(resolver.ResolveError, match=f"respawn.{key} must be a non-negative "
                                                    f"integer at most {TOP}"):
        chain.run_guards(fake.work, env, {key: HUGE})
    assert chain.run_guards(fake.work, env, {key: TOP})[key] == TOP


@pytest.mark.parametrize("key", ["settle", "hold_max"])
def test_g1_run_with_a_profile_above_the_bound_exits_2(key, fake, tmp_path, monkeypatch):
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    for k, v in _profile(tmp_path / "home", key, HUGE).items():
        monkeypatch.setenv(k, v)
    rc, _, err = _cli("run", "--chain", "c1", "--", "--model", "m", "go")
    assert rc == 2 and fake.starts() == [], err
    assert f"respawn.{key} must be a non-negative integer at most {TOP}" in err
    assert len(err.splitlines()) == 1


def test_g1_run_settle_above_the_bound_exits_2(fake, monkeypatch):
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    for raw in (str(HUGE), str(TOP + 1), "9" * 5000, "0" * 30 + "1" * 9):
        rc, _, err = _cli("run", "--chain", "c1", "--settle", raw, "--", "--model", "m", "go")
        assert rc == 2 and fake.starts() == [], err
        assert f"respawn.settle must be a non-negative integer at most {TOP}" in err
        assert len(err.splitlines()) == 1 and len(err) < 200, err


def test_g1_run_settle_at_the_bound_is_taken():
    assert cli._respawn_flag("settle", str(TOP)) == TOP
    assert cli._respawn_flag("settle", "0" * 30 + str(TOP)) == TOP


def test_g1_the_probes_case_through_the_guards_never_overflows(fake, monkeypatch):
    """N6's probe, its value now arriving through run_guards as the launcher reads it."""
    seq = (respawn_seq(fake.charter)
           + [(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
              (2000, _call("PostToolUse", "a1", "toolu_01")), end(9000)])
    fx = _fx(monkeypatch, [seq, [end(1)]])
    for key in ("settle", "hold_max"):
        with pytest.raises(resolver.ResolveError, match=f"at most {TOP}"):
            chain.run_guards(fake.work, dict(os.environ), {key: HUGE})
    _frun(fx, {**G, "hold_max": TOP, "settle": 60})            # the bound itself runs
    assert len(fx.procs) == 2
