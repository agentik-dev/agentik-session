"""Packet st1-starter: the `starter` profile runs when nothing names one (entry 10).

Every case runs in its own temp HOME and state; none reads the live user file."""
import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from claude_session import cli, hooks, resolver

SID = "st1-sess-0000-1111"
PIN_PROFILES = ("frontier", "balanced", "local", "local-only", "scratch", "review", "packets",
                "builder", "orchestrator", "orchestrator-opus")
PRIORITY = re.compile(r"\bS[1-4]\b|priority")
PACING = re.compile(r"pacing|fill off|wake|cache 1h|cache 5m")


def env_for(tmp_path, user=None, **extra):
    home = tmp_path / "home"
    if user is not None:
        (home / ".claude" / "agentik").mkdir(parents=True, exist_ok=True)
        (home / ".claude" / "agentik" / "profiles.yaml").write_text(user)
    home.mkdir(parents=True, exist_ok=True)
    return {"HOME": str(home), "XDG_STATE_HOME": str(tmp_path / "state"), **extra}


def repo(tmp_path, config=None, local=None):
    r = tmp_path / "repo"
    (r / ".claude" / "agentik").mkdir(parents=True, exist_ok=True)
    if config:
        (r / ".claude" / "agentik" / "config.yaml").write_text(config)
    if local:
        (r / ".claude" / "agentik" / "config.local.yaml").write_text(local)
    return r


def start(tmp_path, env, cwd=None):
    cwd = cwd or repo(tmp_path)
    out = hooks.session_start({"session_id": SID, "cwd": str(cwd)}, env)
    return out["hookSpecificOutput"]["additionalContext"]


def resolved_session(tmp_path, env, cwd=None, profile=None):
    return resolver.resolve(cwd or repo(tmp_path), SID, env, profile=profile,
                            overlay={}).sections["session"]


def test_1_nothing_names_a_profile_runs_starter_and_says_no_charter(tmp_path):
    ctx = start(tmp_path, env_for(tmp_path))
    assert "profile 'starter'" in ctx and hooks.START_METER_PLAIN in ctx
    assert "charter" not in ctx.lower()
    assert not PRIORITY.search(ctx) and not PACING.search(ctx)
    assert "frontier" not in ctx


def test_2_a_user_file_naming_frontier_is_told_as_frontier(tmp_path):
    env = env_for(tmp_path, "defaults:\n  profile: frontier\n")
    ctx = start(tmp_path, env)
    assert "profile 'frontier'" in ctx and hooks.START_METER in ctx
    assert "priority: S1" in ctx and "pacing:" in ctx and "charter: none open today" in ctx
    s = resolved_session(tmp_path, env)
    named = resolved_session(tmp_path, env_for(tmp_path / "b"), profile="frontier")
    assert s["profile"] == "frontier" and s["charter"]["required"] is True
    assert {k: v for k, v in s.items()} == {k: v for k, v in named.items()}


def test_3_a_user_file_with_defaults_and_no_profile_runs_starter(tmp_path):
    env = env_for(tmp_path, "defaults:\n  effort: high\n")
    assert resolved_session(tmp_path, env)["profile"] == "starter"
    assert "profile 'starter'" in start(tmp_path, env)


@pytest.mark.parametrize("where", ["launch", "repo", "local"])
def test_4_a_layer_that_names_a_profile_wins(tmp_path, where):
    env, cwd = env_for(tmp_path), None
    if where == "launch":
        env["CLAUDE_SESSION_PROFILE"] = "balanced"
    else:
        cwd = repo(tmp_path, **{"config" if where == "repo" else "local":
                                "session:\n  profile: review\n"})
    want = "balanced" if where == "launch" else "review"
    assert resolved_session(tmp_path, env, cwd, hooks.launch_profile(env))["profile"] == want


def test_starter_is_the_defaults_with_three_fields_off(tmp_path):
    s = resolved_session(tmp_path, env_for(tmp_path))
    d = resolved_session(tmp_path, env_for(tmp_path / "b"), profile="balanced")
    assert s["charter"]["required"] is False
    assert s["priority"]["enabled"] is False and s["pacing"]["enabled"] is False
    for k in ("model", "effort", "lane", "posture", "ceilings", "tools",
              "permission_mode", "checkpoint_at"):
        assert s[k] == d[k], k
    assert s["posture"] == "signal"


def _profile_out(capsys, name, shipped=None, monkeypatch=None):
    if shipped is not None:
        monkeypatch.setattr(resolver, "SHIPPED", shipped)
    assert cli.cmd_profile(argparse.Namespace(name=name)) == 0
    return capsys.readouterr().out


def test_5_each_pin_profile_prints_as_with_no_starter(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(repo(tmp_path))
    text = resolver.SHIPPED.read_text()
    cut = text.index("  # What runs when nothing names a profile")
    old = tmp_path / "profiles.yaml"
    old.write_text(text[:cut])
    now = {n: _profile_out(capsys, n) for n in PIN_PROFILES}
    for n in PIN_PROFILES:
        assert _profile_out(capsys, n, old, monkeypatch) == now[n], n
        monkeypatch.setattr(resolver, "SHIPPED", Path(resolver.__file__).with_name(
            "profiles.yaml"))


def test_5_the_list_shows_starter_and_marks_the_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rows = _profile_out(capsys, None).splitlines()
    marked = [r.split()[0] for r in rows if r.endswith(cli.FALLBACK_MARK)]
    assert marked == ["starter"] and rows[-1].startswith("starter ")
    (tmp_path / "home" / ".claude" / "agentik").mkdir(parents=True)
    (tmp_path / "home" / ".claude" / "agentik" / "profiles.yaml").write_text(
        "defaults:\n  profile: frontier\n")
    rows = _profile_out(capsys, None).splitlines()
    assert [r.split()[0] for r in rows if r.endswith(cli.FALLBACK_MARK)] == ["frontier"]


def _meter(pct):
    return SimpleNamespace(ceilings={"context": 180000, "turns": 400}, pct_context=pct,
                           context=int(1800 * pct), pct_turns=0.2, turns=1, used_pct=pct)


@pytest.mark.parametrize("pct", [80.0, 100.0])
def test_6_starter_s_checkpoint_line_names_no_charter(tmp_path, pct):
    s = resolved_session(tmp_path, env_for(tmp_path))
    assert hooks.asks_charter(s) is False
    line = hooks._checkpoint_out(_meter(pct), None)["hookSpecificOutput"]["additionalContext"]
    assert line.startswith("CHECKPOINT: ") and hooks.PLAIN_TAIL in line
    assert "charter" not in line.lower()


def test_6_frontier_s_checkpoint_line_is_the_pin_s(tmp_path):
    s = resolved_session(tmp_path, env_for(tmp_path), profile="frontier")
    assert hooks.asks_charter(s) is True
    line = hooks._checkpoint_out(_meter(80.0), "history/sittings")
    assert json.dumps(line).count("charter history/sittings; bring the charter current") == 1
