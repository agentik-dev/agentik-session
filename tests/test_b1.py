"""Packet b1: the meter's percent line on a schedule, no absolute budget in the model's text,
the helper-model wording, and effort in the session ledger."""

import io
import json
import os
import re
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, config, harness, hooks, ledger, resolver, rules

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SID = "meter-sess-1"
T0 = 1_800_000_000.0
LINE46 = "session meter: 46% of context, 1% of turns; the checkpoint comes at 80%"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    config.ensure_dirs()
    return dict(os.environ)


@pytest.fixture
def clock(monkeypatch):
    now = [T0]
    monkeypatch.setattr(hooks, "_now", lambda: now[0])
    return now


def sdir(env):
    return resolver.session_dir(resolver.state_dir(env), SID)


def transcript(tmp_path, context, turns=4):
    rows = []
    for i in range(turns):
        rows.append({"type": "assistant", "requestId": f"r{i}",
                     "timestamp": "2026-11-11T10:00:00Z",
                     "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                                 "content": [{"type": "text", "text": "<placeholder>"}],
                                 "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                           "cache_read_input_tokens": context,
                                           "output_tokens": 7}}})
    p = tmp_path / "t.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def tool(env, path):
    return hooks.post_tool_use({"session_id": SID, "transcript_path": str(path),
                                "tool_name": "Read"}, env)


def prompt():
    return hooks.user_prompt_submit({"session_id": SID})


def ctx(out):
    return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""


def meter_lines(out):
    return [b for b in ctx(out).split("\n\n") if b.startswith("session meter:")]


def resolved(env, **session):
    d = sdir(env)
    d.mkdir(parents=True, exist_ok=True)
    (d / "resolved.json").write_text(json.dumps({"session": {"posture": "signal", **session}}))


def at(env, tmp_path, context):
    """A meter at `context` of 180000 (the first tool call starts the clock, silently)."""
    assert tool(env, transcript(tmp_path, context)) == {}


# --- R1, R2: the schedule and the wording ---------------------------------------------

def test_t1_the_first_prompt_with_a_meter_shows_the_line(env, tmp_path, clock):
    at(env, tmp_path, 82800)                                  # 46%
    assert meter_lines(prompt()) == [LINE46]


def test_t2_a_prompt_ten_minutes_later_does_not(env, tmp_path, clock):
    at(env, tmp_path, 82800)
    prompt()
    clock[0] += 600
    assert meter_lines(prompt()) == []


@pytest.mark.parametrize("by", ["prompt", "tool"])
def test_t3_thirty_minutes_later_the_line_once(env, tmp_path, clock, by):
    p = transcript(tmp_path, 82800)
    at(env, tmp_path, 82800)
    prompt()
    clock[0] += 1800
    first = prompt() if by == "prompt" else tool(env, p)
    assert meter_lines(first) == [LINE46]
    if by == "tool":
        assert first["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    clock[0] += 60
    assert meter_lines(prompt()) == [] and tool(env, p) == {}


def test_t3_a_tool_call_starts_the_clock_and_never_speaks_first(env, tmp_path, clock):
    p = transcript(tmp_path, 82800)
    assert tool(env, p) == {}
    clock[0] += 1799
    assert tool(env, p) == {}
    clock[0] += 1
    assert meter_lines(tool(env, p)) == [LINE46]


def test_t4_zero_shows_it_on_every_prompt_and_never_on_a_tool(env, tmp_path, clock):
    resolved(env, pacing={**rules.PACING, "meter_line_minutes": 0})
    p = transcript(tmp_path, 82800)
    tool(env, p)
    for _ in range(3):
        assert meter_lines(prompt()) == [LINE46]
    clock[0] += 7200
    assert tool(env, p) == {}


def test_t4_the_key_sets_the_interval(env, tmp_path, clock):
    resolved(env, pacing={**rules.PACING, "meter_line_minutes": 5})
    at(env, tmp_path, 82800)
    prompt()
    clock[0] += 299
    assert meter_lines(prompt()) == []
    clock[0] += 1
    assert meter_lines(prompt()) == [LINE46]


def test_t5_from_the_checkpoint_every_prompt_and_d13_unchanged(env, tmp_path, clock):
    p = transcript(tmp_path, 144000)                          # 80%
    out = tool(env, p)
    assert ctx(out).startswith("CHECKPOINT: 80.0% context (144000/180000)")
    for _ in range(3):
        bits = ctx(prompt()).split("\n\n")
        assert bits[0] == "session meter: 80% of context, 1% of turns; the checkpoint came at 80%"
        assert bits[1] == "Sitting budget: 'notice' zone."
    said = [bool(tool(env, p)) for _ in range(10)]
    assert said == [False] * 9 + [True]


def test_f1_below_a_higher_checkpoint_at_the_schedule_holds(env, tmp_path, clock):
    """r1 F1: the profile's checkpoint_at, not the notice zone, ends the schedule."""
    resolved(env, checkpoint_at=0.9)
    p = transcript(tmp_path, 153000)                          # 85%: notice, under 90%
    at(env, tmp_path, 153000)
    line = "session meter: 85% of context, 1% of turns; the checkpoint comes at 90%"
    assert meter_lines(prompt()) == [line]
    for _ in range(4):
        clock[0] += 60
        assert meter_lines(prompt()) == []
    clock[0] += 1800
    assert meter_lines(tool(env, p)) == [line]
    assert meter_lines(prompt()) == []


def test_f1_past_a_lower_checkpoint_at_every_prompt(env, tmp_path, clock):
    resolved(env, checkpoint_at=0.7)
    p = transcript(tmp_path, 135000)                          # 75%: clear, past 70%
    assert ctx(tool(env, p)).startswith("CHECKPOINT: 75.0% context (135000/180000)")
    for _ in range(3):
        clock[0] += 60
        assert meter_lines(prompt()) == [
            "session meter: 75% of context, 1% of turns; the checkpoint came at 70%"]
    said = [bool(tool(env, p)) for _ in range(10)]
    assert said == [False] * 9 + [True]                       # D13, not the schedule


def test_posture_off_and_a_helper_say_nothing(env, tmp_path, clock):
    resolved(env, posture="off")
    p = transcript(tmp_path, 82800)
    assert tool(env, p) == {}
    clock[0] += 7200
    assert tool(env, p) == {} and prompt() == {}
    assert hooks.post_tool_use({"session_id": SID, "transcript_path": str(p), "agent_id": "a",
                                "tool_name": "Read"}, env) == {}


def test_the_stamp_is_the_sessions_own(env, tmp_path, clock):
    at(env, tmp_path, 82800)
    assert json.loads((sdir(env) / hooks.METER_LINE).read_text()) == {"at": T0, "shown": False}
    prompt()
    assert json.loads((sdir(env) / hooks.METER_LINE).read_text()) == {"at": T0, "shown": True}


@pytest.mark.parametrize("bad", ["1" + "0" * 400, "NaN", "Infinity", "-Infinity", '"x"', "true",
                                 "null", None],
                         ids=["huge", "nan", "inf", "-inf", "str", "bool", "null", "missing"])
def test_f3_a_stamp_whose_at_is_no_finite_time_is_no_stamp(env, tmp_path, clock, bad):
    """r1 F3: neither hook raises or goes silent for good; the next write replaces it."""
    p = transcript(tmp_path, 82800)
    at(env, tmp_path, 82800)
    f = sdir(env) / hooks.METER_LINE
    body = '{"shown": true}' if bad is None else '{"at": %s, "shown": true}' % bad
    f.write_text(body)
    assert tool(env, p) == {}                                 # starts the clock
    assert json.loads(f.read_text()) == {"at": T0, "shown": False}
    f.write_text(body)
    assert meter_lines(prompt()) == [LINE46]
    assert json.loads(f.read_text()) == {"at": T0, "shown": True}


# --- T12: the key ------------------------------------------------------------------------

def test_t12_the_key_defaults_to_30_and_is_bounded(tmp_path):
    e = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state")}
    s = resolver.resolve(tmp_path, "t", e).sections["session"]
    assert s["pacing"]["meter_line_minutes"] == 30 == rules.PACING["meter_line_minutes"]
    assert rules.parts({})[1]["meter_line_minutes"] == 30
    for bad in (-1, 1441, True, "30"):
        with pytest.raises(ValueError, match="meter_line_minutes"):
            rules.check({**s, "pacing": {**s["pacing"], "meter_line_minutes": bad}})
    for good in (0, 1440):
        rules.check({**s, "pacing": {**s["pacing"], "meter_line_minutes": good}})


# --- R3: the start line ------------------------------------------------------------------

def start_line(tmp_path, **extra):
    d = json.loads((FIX / "session_start.json").read_text())
    d["cwd"] = str(ROOT / d["cwd"])
    d["transcript_path"] = str(ROOT / d["transcript_path"])
    e = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state"), **extra}
    return hooks.session_start(d, e)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("extra", [{}, {"CLAUDE_SESSION_MAX_TURNS": "80"},
                                   {"CLAUDE_SESSION_PROFILE": "orchestrator"}])
def test_t6_the_start_line_holds_no_absolute_ceiling(tmp_path, extra):
    line = start_line(tmp_path, **extra)
    head = line.split("; resolved config at ")[0]
    note = "" if "CLAUDE_SESSION_PROFILE" in extra else hooks.NOT_LAUNCHED     # ss3 R1
    assert head == (f"agentik-session: profile '{extra.get('CLAUDE_SESSION_PROFILE', 'frontier')}'"
                    f"{note}; the meter shows this session's percent on its schedule and prints "
                    "CHECKPOINT when it is time to bring the charter current and hand off")
    for word in ("180000", "400000", "200000", "1000000", "turns", "window", "ceilings",
                 "CLAUDE_SESSION_MAX_TURNS", "checkpoint at"):
        assert word not in line, word


# --- R4: the charter's budget row ---------------------------------------------------------

def test_t7_a_new_charters_budget_row_holds_no_number(tmp_path):
    section = {"profile": "orchestrator-opus", "ceilings": {"context": 400000, "turns": 400},
               "window": 1000000, "checkpoint_at": 0.8, "charter": {"dir": "history/sittings"}}
    p = charter.open(tmp_path / "h", "g", section, "abc1234", repo="r")
    row = next(l for l in p.read_text().splitlines() if l.startswith("| budget |"))
    assert row == ("| budget | profile orchestrator-opus; the meter's CHECKPOINT line ends the "
                   "sitting |")
    assert not re.search(r"\d", row)
    assert charter.check_text(p.read_bytes()) == []


# --- R5: the wind-down is said ------------------------------------------------------------

WIND = "; tell the owner you are winding down at the meter's line, at "


@pytest.mark.parametrize("chained", [False, True])
def test_t8_the_checkpoint_asks_for_the_wind_down_to_be_said(env, tmp_path, clock, chained):
    if chained:
        env["CLAUDE_SESSION_CHAIN"] = "c1"
    out = tool(env, transcript(tmp_path, 145800))             # 81%
    line = ctx(out)
    assert line.startswith("CHECKPOINT: 81.0% context (145800/180000)")
    assert line.endswith(WIND + "81.0%") and "EXIT" not in line
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_t8_at_100_the_clause_then_the_exit_rule(env, tmp_path, clock):
    line = ctx(tool(env, transcript(tmp_path, 180000)))
    assert line.endswith(WIND + "100.0%\n" + hooks.EXIT_RULE)


# --- R6: a helper call's model -------------------------------------------------------------

def test_t9_no_shipped_text_says_each_naming_its_model():
    r = subprocess.run(["git", "grep", "-n", "each naming its model", "--", "plugin",
                        "RUNBOOK.md", "README.md"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout == ""


def test_t9_the_lines_as_ruled():
    assert hooks.WORKFLOW_DENY == (
        "agentik-session: Workflow denied: this suite runs no workflows. Spawn helpers with "
        "the Agent tool: name the model, or use an agent type whose definition names its own. "
        "Do not call Workflow again.")
    assert len(hooks.WORKFLOW_DENY.encode()) < 200
    out = hooks._spawn_rule({"tool_name": "Agent", "tool_input": {"model": "fable"}}, {})
    assert out.endswith(". Name model: 'opus', or use an agent type that names its own model.")
    skill = (ROOT / "plugin" / "skills" / "session" / "SKILL.md").read_text()
    assert ("Spawn helpers with the Agent tool: name the model, or use an agent type whose "
            "definition names its own.") in " ".join(skill.split())


# --- R7: effort in the session ledger ------------------------------------------------------

def ps_table(rows):
    """A fake `ps`: pid -> (ppid, args)."""
    return lambda pid: rows.get(pid)


def write_settings(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def end(env, tmp_path, monkeypatch, rows=None):
    monkeypatch.setattr(harness, "_ps", ps_table(rows or {}))
    monkeypatch.setattr(os, "getppid", lambda: 100)
    p = transcript(tmp_path, 82800)
    hooks.session_end({"session_id": SID, "transcript_path": str(p), "reason": "other",
                       "cwd": str(tmp_path / "repo")}, env)
    row = ledger.read(resolver.state_dir(env))[-1]
    assert list(row) == list(ledger.LEDGER_KEYS)
    return row["effort"], row["effort_from"]


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "repo").mkdir()
    return tmp_path / "repo"


def test_t10_the_launch_lines_flag(env, tmp_path, monkeypatch, repo):
    write_settings(Path(env["HOME"]) / ".claude" / "settings.json", {"effortLevel": "xhigh"})
    rows = {100: (90, "/bin/sh -c agentik-session hook SessionEnd"),
            90: (80, "claude --model opus --effort high --name x"), 80: (1, "-zsh")}
    assert end(env, tmp_path, monkeypatch, rows) == ("high", "flag")
    rows[90] = (80, "claude --effort=medium")
    assert end(env, tmp_path, monkeypatch, rows) == ("medium", "flag")


def test_t10_the_settings_for_the_model_then_the_top_level(env, tmp_path, monkeypatch, repo):
    user = Path(env["HOME"]) / ".claude" / "settings.json"
    rows = {100: (90, "claude --model opus")}
    write_settings(user, {"effortLevel": "xhigh",
                          "modelSettings": {"claude-opus-5-5": {"effortLevel": "high"},
                                            "claude-fable-5-2": {"effortLevel": "low"}}})
    assert end(env, tmp_path, monkeypatch, rows) == ("high", "settings")
    write_settings(repo / ".claude" / "settings.local.json",
                   {"modelSettings": {"claude-opus-5-5": {"effortLevel": "medium"}}})
    assert end(env, tmp_path, monkeypatch, rows) == ("medium", "settings")
    (repo / ".claude" / "settings.local.json").unlink()
    write_settings(user, {"effortLevel": "xhigh"})
    assert end(env, tmp_path, monkeypatch, rows) == ("xhigh", "settings")


def test_t10_none_and_a_bad_value(env, tmp_path, monkeypatch, repo):
    assert end(env, tmp_path, monkeypatch) == (None, None)
    write_settings(Path(env["HOME"]) / ".claude" / "settings.json", {"effortLevel": "turbo"})
    assert end(env, tmp_path, monkeypatch, {100: (1, "claude --effort ultra")}) == (None, None)


def test_t10_the_walk_stops_and_never_raises():
    assert harness.claude_argv(ps=ps_table({}), pid=100) is None
    loop = {100: (100, "sh")}
    assert harness.claude_argv(ps=ps_table(loop), pid=100) is None
    deep = {n: (n - 1, "sh") for n in range(2, 40)}
    assert harness.claude_argv(ps=ps_table(deep), pid=39) is None
    assert harness.claude_argv(ps=ps_table({5: (1, "/opt/x/claude -p")}), pid=5) == [
        "/opt/x/claude", "-p"]


LIVE = ("/opt/someone/.local/bin/claude --session-id 0a1b --model fable --effort high "
        "Read the newest file and act; never pass --effort low to a helper")


def test_f2_the_flag_not_a_word_of_the_launch_prompt(env, tmp_path, monkeypatch, repo):
    """r1 F2: the last --effort before the first positional word, the flag's own value."""
    assert harness.flag_effort(harness.claude_argv(ps=ps_table({5: (1, LIVE)}), pid=5)) == "high"
    assert end(env, tmp_path, monkeypatch, {100: (1, LIVE)}) == ("high", "flag")
    assert harness.flag_effort("claude --effort=high fix the --effort max bug".split()) == "high"


@pytest.mark.parametrize("line, want", [
    ("claude --model opus fix the --effort max bug", None),       # only the prompt says it
    ("claude -- --effort high", None),                            # past `--`: positional
    ("claude --effort turbo --effort high", None),                # the first one is no level
    ("claude --effort", None),
    ("claude --effort=", None),
    ("claude --frobnicate x --effort high", None),                # an option it cannot read
    ("claude --add-dir /a fix --effort max", None),               # a list's words: no telling
    ("claude --add-dir /a --effort low go", "low"),
    ("claude --verbose -p --permission-mode=auto --effort medium hi", "medium"),
    ("claude --resume abc --effort xhigh", "xhigh"),
    ("claude --debug --effort max", "max"),
    ("claude --append-system-prompt note --effort low", "low"),
    ("claude --append-system-prompt two words --effort low", None),   # the second is positional
    # r2: the launcher's config flag first, the caller's after it; claude takes the last
    ("claude --effort high --effort low", "low"),
    ("claude --effort=high --effort low", "low"),
    ("claude --effort high --model opus --effort=max go --effort low", "max"),
    ("claude --effort high -- --effort low", "high"),
    ("claude --effort high --frobnicate", None),                  # a later one may sit past it
    ("claude --effort high --effort turbo", None),
    ("claude --effort high --effort", None),
    ("claude --effort high --add-dir /a fix", None),
])
def test_f2_the_walk_reads_options_and_stops_at_the_first_word(line, want):
    assert harness.flag_effort(line.split()) == want


def test_t10_the_suite_never_reads_the_live_process_tree():
    assert harness._ps(os.getpid()) is None          # conftest's stub


# --- T11: report --json ---------------------------------------------------------------------

def test_t11_report_json_carries_both_keys_on_a_new_row(env, tmp_path, monkeypatch, repo):
    state = resolver.state_dir(env)
    old = {k: None for k in ledger.LEDGER_KEYS if k not in ("effort", "effort_from")}
    ledger._append_line(state, json.dumps({**old, "session": "old-1",
                                           "ended": "2026-11-01T00:00:00+00:00"}))
    end(env, tmp_path, monkeypatch, {100: (1, "claude --effort low")})
    from claude_session import cli as c
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = c.main(["report", "--json"])
    rows = json.loads(out.getvalue())
    assert rc == 0 and len(rows) == 2
    assert "effort" not in rows[0] and "effort_from" not in rows[0]      # S49: as written
    assert (rows[1]["effort"], rows[1]["effort_from"]) == ("low", "flag")
