"""Packet st1-starter: the `starter` profile runs when nothing names one (entry 10).

Every case runs in its own temp HOME and state; none reads the live user file."""
import argparse
import json
import os
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
    assert hooks.discipline(s) is False
    line = hooks._checkpoint_out(_meter(pct), None)["hookSpecificOutput"]["additionalContext"]
    assert line.startswith("CHECKPOINT: ") and hooks.PLAIN_TAIL in line
    assert "charter" not in line.lower()


def test_6_frontier_s_checkpoint_line_is_the_pin_s(tmp_path):
    s = resolved_session(tmp_path, env_for(tmp_path), profile="frontier")
    assert hooks.discipline(s) is True
    line = hooks._checkpoint_out(_meter(80.0), "history/sittings")
    assert json.dumps(line).count("charter history/sittings; bring the charter current") == 1


# ---- D3: the two lines a starter session no longer gets ----------------------------------

def _resolve_into_state(tmp_path, env, profile=None):
    cwd = repo(tmp_path)
    resolver.write(resolver.resolve(cwd, SID, env, profile=profile, overlay={}),
                   resolver.state_dir(env))
    return {"session_id": SID, "transcript_path": "/nonexistent/t.jsonl", "cwd": str(cwd),
            "hook_event_name": "PreCompact", "trigger": "auto", "custom_instructions": ""}


def test_d3_starter_s_compaction_is_not_blocked(tmp_path):
    env = env_for(tmp_path)
    p = _resolve_into_state(tmp_path, env)
    assert resolved_session(tmp_path, env)["charter"]["discipline"] is False
    assert hooks.pre_compact(p, env) == {}


@pytest.mark.parametrize("name", PIN_PROFILES)
def test_d3_every_pin_profile_still_blocks_an_automatic_compaction(tmp_path, name):
    env = env_for(tmp_path)
    p = _resolve_into_state(tmp_path, env, profile=name)
    assert hooks.pre_compact(p, env) == {"decision": "block", "reason": hooks.COMPACT_BLOCKED}


def test_d3_no_resolved_file_blocks_as_at_the_pin(tmp_path):
    env = env_for(tmp_path)
    p = {"session_id": SID, "trigger": "auto", "cwd": str(tmp_path)}
    assert hooks.pre_compact(p, env)["decision"] == "block"
    assert hooks.pre_compact({**p, "trigger": "manual"}, env) == {}


def test_d3_starter_s_last_line_says_start_a_fresh_session(tmp_path):
    line = hooks._checkpoint_out(_meter(100.0), None)["hookSpecificOutput"]["additionalContext"]
    assert line.endswith("\n" + hooks.PLAIN_EXIT)
    assert "context is full" in hooks.PLAIN_EXIT and "fresh session" in hooks.PLAIN_EXIT
    for word in ("respawn", "compact", "successor", "charter", "launcher"):
        assert word not in line.lower(), word


def test_d3_frontier_s_last_line_is_the_pin_s(tmp_path):
    line = hooks._checkpoint_out(_meter(100.0), "history/sittings")
    assert line["hookSpecificOutput"]["additionalContext"].endswith("\n" + hooks.EXIT_RULE)


# ---- the fix of review 1: one waiver (C1), plain budget lines (C2), a launched chain (C4) --

def _row(i, context):
    return json.dumps({"type": "assistant", "requestId": f"r{i}",
                       "timestamp": "2026-09-22T10:00:00Z",
                       "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                                   "content": [{"type": "text", "text": "<placeholder>"}],
                                   "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                             "cache_read_input_tokens": context,
                                             "output_tokens": 7}}}) + "\n"


class Road:
    """One session through the real hooks: SessionStart writes its resolved file, then each
    step appends a transcript line and runs the hook events on it."""

    def __init__(self, tmp_path, monkeypatch, config=None, chain=None):
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
        if chain:
            monkeypatch.setenv(hooks.CHAIN_VAR, chain)
        self.env = dict(os.environ)
        self.cwd = repo(tmp_path, config=config)
        self.tp = tmp_path / "t.jsonl"
        self.tp.write_text("")
        self.n = 0
        self.start = hooks.session_start({"session_id": SID, "cwd": str(self.cwd)},
                                         self.env)["hookSpecificOutput"]["additionalContext"]
        self.session = json.loads((resolver.session_dir(resolver.state_dir(self.env), SID)
                                   / "resolved.json").read_text())["session"]

    def payload(self, **extra):
        return {"session_id": SID, "transcript_path": str(self.tp), "cwd": str(self.cwd),
                **extra}

    def at(self, pct):
        self.n += 1
        context = int(self.session["ceilings"]["context"] * pct / 100)
        with open(self.tp, "a") as fh:
            fh.write(_row(self.n, context))
        return self.tool()

    def tool(self):
        out = hooks.post_tool_use(self.payload(tool_name="Read"), self.env)
        return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""

    def prompt(self):
        out = hooks.user_prompt_submit(self.payload(prompt="go on"))
        return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""

    def spawn(self):
        out = hooks.pre_tool_use(self.payload(tool_name="Agent", tool_input={}), self.env)
        return json.dumps(out)

    def compact(self):
        return hooks.pre_compact(self.payload(trigger="auto"), self.env)


C1_REPO = "session:\n  profile: {p}\n  charter: {{required: false}}\n"


@pytest.mark.parametrize("chain", [None, "net"])
@pytest.mark.parametrize("name", ["orchestrator", "frontier"])
def test_c1_charter_required_false_alone_changes_no_line(tmp_path, monkeypatch, name, chain):
    road = Road(tmp_path, monkeypatch, C1_REPO.format(p=name), chain)
    assert road.session["profile"] == name and road.session["charter"]["required"] is False
    assert hooks.START_METER in road.start and hooks.START_METER_PLAIN not in road.start
    line = road.at(80)
    assert ("RESPAWN:" in line) == bool(chain) and "charter " in line
    assert "winding down at the meter's line" in line and hooks.PLAIN_TAIL not in line
    assert road.at(100).endswith("\n" + hooks.EXIT_RULE)
    assert road.compact() == {"decision": "block", "reason": hooks.COMPACT_BLOCKED}


def test_c1_scratch_reads_as_at_the_pin(tmp_path, monkeypatch):
    road = Road(tmp_path, monkeypatch, "session:\n  profile: scratch\n")
    assert hooks.START_METER in road.start and hooks.START_METER_PLAIN not in road.start
    assert road.compact()["decision"] == "block"


def test_c1_only_starter_ships_the_waiver(tmp_path):
    shipped = resolver.load_profiles(env_for(tmp_path))[1]
    waived = [n for n, b in shipped.items() if "discipline" in ((b or {}).get("charter") or {})]
    assert waived == ["starter"]
    assert hooks.discipline({}) is True and hooks.discipline(None) is True
    assert hooks.discipline({"charter": {"required": False}}) is True


def test_c4_a_launched_chain_with_nothing_named_runs_the_full_profile(tmp_path, monkeypatch):
    road = Road(tmp_path, monkeypatch, chain="net")
    assert road.session["profile"] == resolver.FULL_PROFILE == "frontier"
    assert hooks.START_METER in road.start
    assert "RESPAWN:" in road.at(80)
    assert road.compact()["decision"] == "block"


def test_c4_the_launcher_resolves_as_its_chain_does(tmp_path, monkeypatch):
    cwd, env = repo(tmp_path), env_for(tmp_path)
    s = resolver.resolve(cwd, SID, env, profile="frontier", overlay={}).sections["session"]
    seen, real = [], resolver.resolve
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: seen.append(k.get("chain"))
                        or real(*a, **k))
    assert cli.run_args(cwd, env, ["hi"])[:4] == ["--model", s["model"], "--effort", s["effort"]]
    cli.run_defaults(cwd, env, ["hi"])
    monkeypatch.setattr(resolver, "resolve", real)
    assert seen == [True, True]
    assert resolver.resolve(cwd, SID, env, overlay={}, chain=True
                            ).sections["session"]["profile"] == "frontier"
    assert resolver.resolve(cwd, SID, env, overlay={}).sections["session"]["profile"] == "starter"


BUDGET_WORDS = ("handoff", "hand off", "handed off", "checkpoint verb", "session checkpoint",
                "agentik-session checkpoint", "owner", "winding down", "wind down", "charter",
                "respawn", "successor")
PCT = re.compile(r"\b\d+(\.\d+)?%")


def test_c2_a_starter_session_s_budget_lines_name_no_discipline(tmp_path, monkeypatch):
    road = Road(tmp_path, monkeypatch)
    assert road.session["profile"] == "starter"
    said = [road.start]
    for pct in (50, 60, 70, 75, 80, 85, 90, 93, 95, 97, 99, 100, 101, 103):
        lines = [road.at(pct)] + [road.tool() for _ in range(10)] + [road.prompt(),
                                                                     road.prompt()]
        said += lines + [road.spawn(), json.dumps(road.compact())]
        for line in lines:
            if "budget" in line.lower() or "CHECKPOINT" in line:
                assert PCT.search(line), line
    text = "\n".join(said)
    assert "CHECKPOINT: " in text and hooks.PLAIN_EXIT in text and "budget" in text.lower()
    low = text.lower()
    for word in BUDGET_WORDS:
        assert word not in low, word
    assert road.compact() == {}
