"""SessionStart: the resolver call, the file it writes, and silence on failure."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import hooks

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "session_start.json"


def payload():
    d = json.loads(FIXTURE.read_text())
    d["cwd"] = str(ROOT / d["cwd"])
    d["transcript_path"] = str(ROOT / d["transcript_path"])
    return d


def env_for(tmp_path, **extra):
    return {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state"), **extra}


def test_writes_the_resolved_file_and_one_line(tmp_path):
    env = env_for(tmp_path)
    out = hooks.session_start(payload(), env)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "\n" not in ctx and "'frontier'" in ctx and "180000 context / 400 turns" in ctx
    path = tmp_path / "state/agentik-session/sessions/test-session/resolved.json"
    assert str(path) in ctx
    doc = json.loads(path.read_text())
    assert list(doc)[0] == "provider"
    assert doc["session"]["verify"] == "make check"
    assert (path.parent / "resolved.yaml").exists()


def test_launch_profile_from_the_environment(tmp_path):
    out = hooks.session_start(payload(), env_for(tmp_path, CLAUDE_SESSION_PROFILE="builder"))
    assert "'builder'" in out["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("env, want", [
    ({"CLAUDE_SESSION_PROFILE": "orchestrator"}, "orchestrator"),
    ({"CLAUDE_SESSION_CONFIG": "frontier"}, "frontier"),
    ({}, None),
    ({"CLAUDE_SESSION_PROFILE": "orchestrator", "CLAUDE_SESSION_HELPER": "1"}, "builder"),
    ({"CLAUDE_SESSION_PROFILE": "orchestrator-opus", "CLAUDE_SESSION_HELPER": "1",
      "CLAUDE_SESSION_DEPTH": "2"}, "builder"),
    ({"CLAUDE_SESSION_CONFIG": "frontier", "CLAUDE_SESSION_HELPER": "1"}, "builder"),
    ({"CLAUDE_SESSION_HELPER": "1"}, "builder"),
    ({"CLAUDE_SESSION_PROFILE": "orchestrator", "CLAUDE_SESSION_HELPER": "0"}, "orchestrator"),
])
def test_launch_profile_resolves_a_helper_as_a_builder(env, want):
    # F1: the helper rule's CLAUDE_SESSION_HELPER=1 wins over the role a helper inherits
    assert hooks.launch_profile(env) == want


def test_a_helper_of_an_orchestrator_sitting_starts_as_a_builder(tmp_path):
    env = env_for(tmp_path, CLAUDE_SESSION_PROFILE="orchestrator", CLAUDE_SESSION_HELPER="1",
                  CLAUDE_SESSION_DEPTH="1")
    ctx = hooks.session_start(payload(), env)["hookSpecificOutput"]["additionalContext"]
    assert "'builder'" in ctx and "'orchestrator'" not in ctx


def test_cwd_falls_back_to_the_project_dir(tmp_path):
    p = payload()
    env = env_for(tmp_path, CLAUDE_PROJECT_DIR=p.pop("cwd"))
    hooks.session_start(p, env)
    doc = json.loads((tmp_path / "state/agentik-session/sessions/test-session/"
                      "resolved.json").read_text())
    assert doc["session"]["verify"] == "make check"


def test_failure_writes_nothing_and_says_one_line(tmp_path, capsys):
    env = env_for(tmp_path, CLAUDE_SESSION_PROFILE="no-such-profile")
    assert hooks.session_start(payload(), env) == {}
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "unknown profile" in err
    assert not (tmp_path / "state").exists()


def test_bad_session_id_writes_nothing(tmp_path):
    p = payload()
    p["session_id"] = "../../etc"
    assert hooks.session_start(p, env_for(tmp_path)) == {}
    assert not (tmp_path / "state").exists()


def test_cli_is_byte_stable_and_exits_0(tmp_path):
    env = {**os.environ, **env_for(tmp_path)}
    env.pop("CLAUDE_SESSION_PROFILE", None)
    env.pop("CLAUDE_SESSION_CONFIG", None)
    hashes = []
    for _ in range(2):
        r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "SessionStart"],
                           input=FIXTURE.read_text(), capture_output=True, text=True,
                           cwd=ROOT, env=env)
        assert r.returncode == 0
        assert json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        hashes.append((tmp_path / "state/agentik-session/sessions/test-session/"
                       "resolved.json").read_bytes())
    assert hashes[0] == hashes[1]


def test_cli_garbage_stdin_exits_0(tmp_path):
    env = {**os.environ, **env_for(tmp_path)}
    r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "SessionStart"],
                       input="not json", capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0 and r.stdout.strip() == "{}"


def test_set_rewrites_the_resolved_file(tmp_path, monkeypatch):
    from claude_session import cli, config
    env = env_for(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session")
    monkeypatch.delenv("CLAUDE_SESSION_PROFILE", raising=False)
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state/agentik-session")
    hooks.session_start(payload(), env)
    path = tmp_path / "state/agentik-session/sessions/test-session/resolved.json"
    assert json.loads(path.read_text())["session"]["posture"] == "signal"
    assert cli.main(["set", "posture", "ask"]) == 0
    assert json.loads(path.read_text())["session"]["posture"] == "ask"


def test_charter_reminder_when_required_and_none_open_today(tmp_path):
    ctx = hooks.session_start(payload(), env_for(tmp_path))["hookSpecificOutput"]["additionalContext"]
    assert ctx.endswith('; charter: none open today under history/sittings, '
                        'run agentik-session charter open "<goal>"')


def test_no_charter_reminder_when_one_is_open_today(tmp_path):
    from claude_session import charter
    repo = tmp_path / "repo"
    (repo / "history" / "sittings").mkdir(parents=True)
    (repo / "history" / "sittings" / f"{charter.today()}-1.md").write_text("x")
    p = dict(payload(), cwd=str(repo))
    ctx = hooks.session_start(p, env_for(tmp_path))["hookSpecificOutput"]["additionalContext"]
    assert "charter" not in ctx.split("resolved config at")[0] and "charter open" not in ctx


def test_no_charter_reminder_when_not_required(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True)
    (repo / ".claude" / "agentik" / "config.yaml").write_text(
        "session: {profile: scratch}\n")
    p = dict(payload(), cwd=str(repo))
    ctx = hooks.session_start(p, env_for(tmp_path))["hookSpecificOutput"]["additionalContext"]
    assert "profile 'scratch'" in ctx and "charter open" not in ctx


# ---- S21: the priority and pacing block ---------------------------------------

S21_BLOCK = ("; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest; the "
             "Next act takes the highest ready; pacing: wake in the act's last tool call, a "
             "pending helper is the wake (one fallback, 1800s+), WAITING 3 stops the loop, a meter wait never; "
             "agentik-session rules prints both")
S21_REMINDER = '; charter: none open today under history/sittings, run agentik-session charter open "<goal>"'


def _s21_ctx(tmp_path, config=None):
    repo = tmp_path / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True, exist_ok=True)
    if config is not None:
        (repo / ".claude" / "agentik" / "config.yaml").write_text(config)
    out = hooks.session_start(dict(payload(), cwd=str(repo)), env_for(tmp_path))
    path = tmp_path / "state/agentik-session/sessions/test-session/resolved.json"
    return out["hookSpecificOutput"]["additionalContext"], f"resolved config at {path}"


def test_s21_block(tmp_path):
    ctx, at = _s21_ctx(tmp_path)
    assert ctx.endswith(at + S21_BLOCK + S21_REMINDER) and "\n" not in ctx


def test_s21_block_off(tmp_path):
    ctx, at = _s21_ctx(tmp_path, "session:\n  priority: {enabled: false}\n")
    assert ctx.endswith(at + "; pacing: wake in the act's last tool call, a pending helper is "
                        "the wake (one fallback, 1800s+), WAITING 3 stops the loop, a meter wait never; "
                        "agentik-session rules prints both" + S21_REMINDER)    # the control
    ctx, at = _s21_ctx(tmp_path, "session:\n  priority: {enabled: false}\n"
                                 "  pacing: {enabled: false}\n")
    assert ctx.endswith(at + S21_REMINDER) and "agentik-session rules" not in ctx


def test_s21_bytes_at_the_bound(tmp_path):
    levels = ", ".join(f'{n}: "{"y" * 40}: t"' for n in ("S1", "S2", "S3", "S4"))
    ctx, at = _s21_ctx(tmp_path, "session:\n  priority:\n    levels: {%s}\n"
                                 "  pacing: {fallback: 3600, waiting: 9}\n" % levels)
    block = ctx.split(at, 1)[1][:-len(S21_REMINDER)]
    assert block.startswith("; priority: S1 " + "y" * 24 + ", S2 ")      # the control
    assert "3600s+" in block and "WAITING 9 stops" in block
    assert len(block.encode()) == 320 <= 320    # agentik-r1: one byte longer, at the bound
