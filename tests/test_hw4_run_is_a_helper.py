"""Packet hw4-run-is-a-helper: a helper's run is counted once from its start to its last turn,
a helper that ends a turn over a live shell is recorded as parked and counted as out, and a
switch keeps raw hook payloads (rulings P1 to P6).

The payloads are the shapes the engine's hook pages document (SubagentStop's `agent_id`,
`agent_type`, `stop_hook_active` and `background_tasks`, each task's `id`, `type`, `status`,
`description` and `command`; a Bash PostToolUse's `tool_response.backgroundTaskId`), with
made-up values. Every state is under the test's own temp root; no test starts a `claude` or a
`make`."""
import hashlib
import io
import json
import os
import stat
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

import pytest

from claude_session import admission, chain, cli, hooks, resolver, room, rules, store

UTC = timezone.utc
SID = "hw4-session-0001"
AID, BID = "agent-hw4-aaaa", "agent-hw4-bbbb"
NOW = datetime(2026, 11, 22, 14, 0, tzinfo=UTC)
M = timedelta(minutes=1)
TEST_CMD = "PYTHONPATH=lib python -m pytest -q tests/test_widgets.py"
SEEDS = {"build": {"median": 29.1, "p90": 55.4}, "fix": {"median": 26.2, "p90": 57.6},
         "phase": {"median": 16.9, "p90": 48.0}, "review": {"median": 9.5, "p90": 18.3},
         "refute": {"median": 9.7, "p90": 17.3},
         "general-purpose": {"median": 14.9, "p90": 64.3}, "scribe": {"median": 0.4, "p90": 0.9}}
LAUNCH = {"back": 2.5, "narrow": {"points": 10, "alone": 15}, "kinds": SEEDS}
BUILDER, ADVERSARY = "relay:builder", "relay:adversary"


def _env():
    return {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}


def _sdir(sid=SID):
    return resolver.session_dir(resolver.state_dir(os.environ), sid)


def _session(used=51.0, posture="signal"):
    sdir = _sdir()
    sdir.mkdir(parents=True, exist_ok=True)
    s = {"profile": "frontier", "posture": posture, "checkpoint_at": 0.8, "launch": LAUNCH,
         "charter": {"dir": "history/sittings", "required": True, "discipline": True}}
    (sdir / "resolved.json").write_text(json.dumps({"session": s}))
    (sdir / "model.json").write_text(json.dumps({"model": "opus"}))
    (sdir / "meter.json").write_text(json.dumps(
        {"session_id": SID, "pct_context": used, "pct_turns": 4.0, "checkpoint_at": 0.8}))
    return sdir


def _iso(t):
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _spawn(t, aid, typ=BUILDER, desc="build 1 of row-a", model="opus", sid=SID):
    return {"ts": _iso(t), "session": sid, "kind": "spawn", "subagentType": typ, "model": model,
            "parentModel": "claude-opus-5-5", "description": desc, "tool_use_id": f"toolu_{aid}",
            "agentId": aid}


def _done(t, aid, mins, sid=SID, swept=False):
    return {"ts": _iso(t), "session": sid, "kind": "done", "agentId": aid, "tool_use_id": None,
            "durationMs": int(mins * 60000), "swept": swept}


def _resume(t, aid, sid=SID):
    return {"ts": _iso(t), "session": sid, "kind": "resume", "to": aid}


def _ledger(rows):
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    (d / admission.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in rows))


_N = [0]


def _moved(command=TEST_CMD, aid=AID, task="bg-001", background=None):
    """A helper's Bash PostToolUse: the engine moved it (`backgroundTaskId`), or it was sent
    with `run_in_background`."""
    _N[0] += 1
    ti = {"command": command, "description": "run the widget tests", "timeout": 120000}
    if background is not None:
        ti["run_in_background"] = background
    resp = {"stdout": "", "stderr": "", "interrupted": False, "isImage": False}
    if task is not None:
        resp["backgroundTaskId"] = task
    p = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": "Bash",
         "tool_input": ti, "tool_response": resp, "tool_use_id": f"toolu_hw4_{_N[0]:04d}",
         "agent_id": aid, "agent_type": "general-purpose", "cwd": "/tmp/widgets"}
    return p, hooks.post_tool_use(p, _env())


def _task(tid="bg-001", command=TEST_CMD, status="running", typ="shell"):
    return {"id": tid, "type": typ, "status": status, "description": "run the widget tests",
            "command": command}


def _stop_payload(aid=AID, tasks=None):
    p = {"session_id": SID, "hook_event_name": "SubagentStop", "stop_hook_active": False,
         "agent_id": aid, "agent_type": "general-purpose",
         "agent_transcript_path": f"/tmp/widgets/{aid}.jsonl",
         "last_assistant_message": "queued the run; ending my turn"}
    if tasks is not None:
        p["background_tasks"] = tasks
    return p


def _stop(aid=AID, tasks=None):
    return hooks.subagent_stop(_stop_payload(aid, tasks), _env())


def parked(aid=AID):
    p = _sdir() / "parked" / f"{aid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def ended(aid=AID):
    return (_sdir() / hooks.ENDED / f"{aid}.json").exists()


def _dispatch(event, payload, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        payload if isinstance(payload, str) else json.dumps(payload)))
    assert hooks.dispatch(event) == 0
    return capsys.readouterr().out


# ---- P1: one run per helper -------------------------------------------------------------------

def test_p1_a_parked_helper_s_wake_is_its_one_run():
    rows = [_spawn(NOW - 60 * M, AID), _done(NOW - 50 * M, AID, 10), _done(NOW - 5 * M, AID, 45)]
    assert len(admission.runs(rows)) == 1 and admission.runs(rows)[0]["minutes"] == 10
    (r,) = admission.helper_runs(rows)
    assert (r["start"], r["end"], r["minutes"]) == (NOW - 60 * M, NOW - 5 * M, 55.0)
    assert (r["agentId"], r["type"], r["family"]) == (AID, BUILDER, "opus")


def test_p1_a_resume_between_opens_no_second_run():
    rows = [_spawn(NOW - 60 * M, AID), _done(NOW - 50 * M, AID, 10),
            _resume(NOW - 40 * M, AID), _done(NOW - 20 * M, AID, 20)]
    assert len(admission.runs(rows)) == 2
    (r,) = admission.helper_runs(rows)
    assert (r["start"], r["end"], r["minutes"]) == (NOW - 60 * M, NOW - 20 * M, 40.0)


def test_p1_a_resume_after_the_last_done_is_open():
    rows = [_spawn(NOW - 60 * M, AID), _done(NOW - 50 * M, AID, 10), _resume(NOW - 40 * M, AID)]
    (r,) = admission.helper_runs(rows)
    assert (r["start"], r["end"], r["minutes"]) == (NOW - 60 * M, None, None)


def test_p1_one_done_keeps_runs_minutes_and_a_run_with_no_agent_is_runs_own():
    rows = [_spawn(NOW - 60 * M, AID), _done(NOW - 50 * M, AID, 7),
            {**_spawn(NOW - 30 * M, "x"), "agentId": None}, _spawn(NOW - 10 * M, BID)]
    assert admission.helper_runs(rows) == admission.runs(rows)


def test_p1_a_swept_last_done_has_no_minutes():
    rows = [_spawn(NOW - 60 * M, AID), _done(NOW - 50 * M, AID, 10),
            _done(NOW - 5 * M, AID, 45, swept=True)]
    (r,) = admission.helper_runs(rows)
    assert r["end"] == NOW - 5 * M and r["minutes"] is None


def test_p1_the_launch_line_s_minutes_by_kind_are_a_helper_s():
    _session()
    rows = []
    for i in range(10):
        t0 = NOW - (300 - 25 * i) * M
        aid = f"rev-{i}"
        rows += [_spawn(t0, aid, ADVERSARY, f"review {i}"), _done(t0 + 2 * M, aid, 2),
                 _done(t0 + 20 * M, aid, 18)]
    _ledger(rows)
    rd = room._reading(SID, os.environ, NOW)
    assert room.minutes(rd["table"], "review")[0] == 20.0          # at the pin: 2
    assert rd["out"] == []


def _p1_rows():
    """A day of readings every five minutes (a reset at 10:00) and helpers, three of them
    parked and woken: the ledger P1's numbers test reads."""
    at = lambda h, m=0: datetime(2026, 11, 20, h, m, tzinfo=UTC)          # noqa: E731
    rows = []
    for i, (h, m) in enumerate([(6, 10), (7, 20), (8, 40), (9, 30), (10, 50), (11, 40)]):
        model = "opus" if i % 2 else "sonnet"
        rows += [_spawn(at(h, m), f"g{i}", "general-purpose", None, model),
                 _done(at(h, m) + 20 * M, f"g{i}", 20)]
    rows += [_spawn(at(7), "p1", BUILDER), _done(at(7, 8), "p1", 8), _done(at(7, 55), "p1", 47),
             _spawn(at(8), "p2", ADVERSARY), _done(at(8, 5), "p2", 5), _resume(at(8, 30), "p2"),
             _done(at(8, 50), "p2", 20),
             _spawn(at(12, 20), "p3", BUILDER), _done(at(12, 25), "p3", 5),
             _spawn(at(12, 40), "o1", "general-purpose"),
             {"ts": _iso(at(12, 41)), "session": SID, "kind": "verdict", "verdict": "stale",
              "tool_use_id": "toolu_o1"}]
    pct, t, reset = 2.0, at(6), at(10)
    while t <= at(13):
        if t == at(10):
            pct, reset = 0.0, at(15)
        if t.minute % 5 == 0:
            rows.append({"ts": _iso(t), "session": SID, "kind": "reading", "rateLimits": [
                {"kind": "five_hour", "percentUsed": round(pct, 1), "resetsAt": _iso(reset)},
                {"kind": "seven_day", "percentUsed": 40.0, "resetsAt": _iso(at(23))}]})
        pct += 0.12 + 0.05 * (t.hour % 3)
        t += M
    return sorted(rows, key=lambda r: r["ts"]), at(13)


def _digest(x) -> str:
    def norm(v):
        if isinstance(v, float):
            return round(v, 9)
        if isinstance(v, dict):
            return {str(k): norm(w) for k, w in v.items()}
        if isinstance(v, (list, tuple)):
            return [norm(w) for w in v]
        return v if v is None or isinstance(v, (bool, int, str)) else str(v)
    return hashlib.sha256(json.dumps(norm(x), sort_keys=True).encode()).hexdigest()[:16]


# Each of admission's own readers on `_p1_rows`, measured at the pin (4e5629a3).
P1_PIN = {"fit": "33c28268b852ba53", "rise": "320cc4e6ddfd513c", "stale": "b5bea41b6c623f7c",
          "band": "fa2f62f313a30bc2", "decide": "1aaf745da38ebc3b", "lives": "26d914a88efb6540"}


def _p1_numbers():
    rows, now = _p1_rows()
    settings = rules.admission(None)
    seeds = settings["seeds"]
    req = {"subagentType": "general-purpose", "model": "opus", "parentModel": "claude-opus-5-5",
           "background": True, "fork": False, "tool_use_id": "toolu_new", "rateLimits": None,
           "resume": False}
    rise = admission._rise(rows, admission.readings(rows), now, 60.0, seeds, set())
    return {"fit": admission.fit(rows, now, seeds), "rise": rise,
            "stale": admission._stale_in_flight(rows, req, now - 120 * M, now, seeds),
            "band": admission.band(rows, now, settings, tz=UTC),
            "decide": admission.decide(rows, req, SID, now, settings, tz=UTC),
            "lives": admission.lives(admission.runs(rows))}


def test_p1_admission_s_numbers_are_the_pin_s():
    got = {k: _digest(v) for k, v in _p1_numbers().items()}
    assert got == P1_PIN
    assert len(admission.helper_runs(_p1_rows()[0])) < len(admission.runs(_p1_rows()[0]))


# ---- P2: the moved call is recorded -----------------------------------------------------------

def _jobs(aid=AID):
    d = _sdir() / "helper-jobs" / aid
    return sorted((json.loads(p.read_text()) for p in d.iterdir()), key=lambda r: r["at"]) \
        if d.is_dir() else []


def test_p2_a_moved_call_is_recorded_by_agent_and_the_output_is_unchanged():
    _session()
    p, out = _moved()
    assert out == {}
    (rec,) = _jobs()
    assert (rec["task"], rec["command"]) == ("bg-001", TEST_CMD)
    f = _sdir() / "helper-jobs" / AID / p["tool_use_id"]
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_p2_a_background_call_is_recorded_and_a_foreground_one_is_not():
    _session()
    _moved(task=None, background=True)
    _moved(command="ls", task=None)
    assert [(r["task"], r["command"]) for r in _jobs()] == [(None, TEST_CMD)]


def test_p2_the_command_is_kept_to_1000_characters_and_the_main_thread_is_not_a_helper():
    _session()
    long = "echo " + "x" * 1500
    _moved(command=long)
    assert _jobs()[0]["command"] == long[:1000]
    p = {"session_id": SID, "tool_name": "Bash", "tool_use_id": "toolu_main_1",
         "tool_input": {"command": TEST_CMD}, "tool_response": {"backgroundTaskId": "bg-9"}}
    hooks.post_tool_use(p, _env())
    assert not (_sdir() / "helper-jobs" / "toolu_main_1").exists()
    assert (_sdir() / hooks.JOBS / "toolu_main_1").exists()          # the pin's record stands


# ---- P3: the park -----------------------------------------------------------------------------

def test_p3_a_running_shell_of_the_helper_s_record_is_a_park():
    _session()
    _moved()
    assert _stop(tasks=[_task("bg-000", "tail -f /tmp/x.log"), _task()]) == {}
    rec = parked()
    assert (rec["task"], rec["tasks"], rec["command"]) == ("bg-001", ["bg-001"], TEST_CMD)
    assert isinstance(rec["at"], float) and not ended()
    assert stat.S_IMODE((_sdir() / "parked" / f"{AID}.json").stat().st_mode) == 0o600


def test_p3_the_payload_s_text_cut_at_1000_still_matches_and_the_record_keeps_200_bytes():
    _session()
    long = "echo " + "é" * 1200
    _moved(command=long)
    _stop(tasks=[_task(command=long[:1000])])
    rec = parked()
    assert rec["command"] == long.encode()[:200].decode("utf-8", "ignore")
    assert len(rec["command"].encode()) <= 200


@pytest.mark.parametrize("task", [
    _task(status="completed"), _task(typ="subagent"), _task(command="make check"),
    {**_task(), "id": 7}, {**_task(), "command": None}, "bg-001", None])
def test_p3_no_match_is_the_pin_s_stop(task):
    _session()
    _moved()
    assert _stop(tasks=[task]) == {} and parked() is None and ended()


@pytest.mark.parametrize("tasks", [None, {"bg-001": _task()}, "bg-001", 3])
def test_p3_a_payload_with_no_such_array_parks_nobody(tasks):
    _session()
    _moved()
    p = _stop_payload()
    if tasks is not None:
        p["background_tasks"] = tasks
    assert hooks.subagent_stop(p, _env()) == {} and parked() is None and ended()


def test_p3_another_helper_s_record_is_no_match_and_two_with_one_line_both_park():
    _session()
    _moved(aid=BID)
    _stop(tasks=[_task()])
    assert parked() is None and ended()
    _moved(aid=AID, task="bg-002")
    _stop(aid=AID, tasks=[_task()])
    _stop(aid=BID, tasks=[_task()])
    assert parked(AID)["task"] == "bg-001" and parked(BID)["task"] == "bg-001"


def test_p3_dispatch_prints_nothing_at_a_park(monkeypatch, capsys):
    _session()
    _moved()
    assert _dispatch("SubagentStop", _stop_payload(tasks=[_task()]), monkeypatch, capsys) == ""
    assert parked() is not None


def test_p3_the_held_respawn_counts_a_parked_helper_as_not_ended():
    sdir = _session()
    _moved()
    _stop(tasks=[_task()])
    assert chain._stamp_helper(sdir) == AID                    # at the pin: ended, so None


# ---- P4: a park ends --------------------------------------------------------------------------

def _park():
    _session()
    _moved()
    _stop(tasks=[_task()])
    assert parked() is not None and not ended()


def test_p4_a_later_payload_that_no_longer_lists_the_task_running_ends_it(monkeypatch, capsys):
    _park()
    _dispatch("Stop", {"session_id": SID, "hook_event_name": "Stop",
                       "background_tasks": [_task()]}, monkeypatch, capsys)
    assert parked() is not None                                 # still running: still parked
    _dispatch("Stop", {"session_id": SID, "hook_event_name": "Stop"}, monkeypatch, capsys)
    assert parked() is not None                                 # no array: nothing learnt
    _dispatch("Stop", {"session_id": SID, "hook_event_name": "Stop",
                       "background_tasks": [_task(status="completed")]}, monkeypatch, capsys)
    assert parked() is None and ended() and _jobs() == []


def test_p4_another_helper_s_stop_ends_a_park_whose_shell_is_gone():
    _park()
    _stop(aid=BID, tasks=[_task(status="running", tid="bg-777", command="sleep 5")])
    assert parked() is None and ended()


def test_p4_the_helper_s_next_stop_with_no_match_ends_it():
    _park()
    _stop(tasks=[])
    assert parked() is None and ended()


@pytest.mark.parametrize("key", ["task_id", "shell_id"])
def test_p4_the_main_thread_s_task_stop_ends_it(key):
    _park()
    other = {"session_id": SID, "tool_name": "TaskStop", "tool_use_id": "toolu_stop_0",
             "tool_input": {key: "bg-999"}, "tool_response": {"message": "stopped"}}
    hooks.post_tool_use(other, _env())
    assert parked() is not None
    p = {**other, "tool_use_id": "toolu_stop_1", "tool_input": {key: "bg-001"}}
    hooks.post_tool_use(p, _env())
    assert parked() is None and ended()


def test_p4_a_helper_s_task_stop_is_not_the_main_thread_s():
    _park()
    hooks.post_tool_use({"session_id": SID, "tool_name": "TaskStop", "tool_use_id": "toolu_s2",
                         "agent_id": BID, "tool_input": {"task_id": "bg-001"}}, _env())
    assert parked() is not None


# ---- P5: a parked helper is out ---------------------------------------------------------------

def _parked_ledger(n, tid=lambda i: f"bg-{i:03d}"):
    sdir = _session()
    rows = []
    for i in range(n):
        aid = f"agent-hw4-{i}"
        rows += [_spawn(NOW - (40 - i) * M, aid), _done(NOW - (30 - i) * M, aid, 10)]
        store._write_private(sdir / "parked" / f"{aid}.json", json.dumps(
            {"at": 1.0, "task": tid(i), "tasks": [tid(i)], "command": TEST_CMD}))
    _ledger(rows)
    return sdir


def test_p5_status_counts_a_parked_helper_and_names_its_shell(monkeypatch):
    _parked_ledger(1)
    rd = room._reading(SID, os.environ, NOW)
    assert [k for k, _ in rd["out"]] == ["build"] and rd["shells"] == ["bg-000"]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        assert cli.main(["status"]) == 0
    assert out.getvalue().splitlines()[-1] == (
        "launch: room 26.5 to the line, 1 out: a builder parked on shell bg-000")


def _launch(desc="review 1 of row-a"):
    return hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent", "tool_use_id": "tu-new",
                               "tool_input": {"prompt": "the brief", "description": desc,
                                              "subagent_type": ADVERSARY}}, os.environ)


def test_p5_the_launch_line_names_the_parks():
    _parked_ledger(1)
    line = _launch()["hookSpecificOutput"]["additionalContext"]
    assert line.startswith("launch: room 26.5 to the line, 1 out;")
    assert line.endswith("; parked on shell bg-000")


@pytest.mark.parametrize("used", [51.0, 70.0, 79.0])
def test_p5_the_line_with_three_parks_stays_inside_its_bound(used):
    _parked_ledger(5, tid=lambda i: f"shell-{i}-" + "q" * 40)
    sdir = _sdir()
    m = json.loads((sdir / "meter.json").read_text())
    (sdir / "meter.json").write_text(json.dumps({**m, "pct_context": used}))
    out = _launch()
    line = out["hookSpecificOutput"]["additionalContext"]
    assert "parked on shell shell-0-" in line and line.endswith(" and 2 more")
    assert line.count("shell-") == 3 and len(json.dumps(out)) <= hooks.MAX_OUT


def test_p5_with_no_park_the_line_is_the_pin_s():
    _session()
    _ledger([_spawn(NOW - 10 * M, AID)])
    assert _launch()["hookSpecificOutput"]["additionalContext"] == (
        "launch: room 26.5 to the line, 1 out; this review (about 10 min, 2.5) fits, wide")


# ---- P6: the capture --------------------------------------------------------------------------

def _cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def _captures():
    d = _sdir() / "captures"
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def test_p6_one_subagent_stop_payload_is_kept_whole(monkeypatch, capsys):
    _session()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    rc, out, _ = _cli("hook", "capture", "SubagentStop")
    assert rc == 0 and "SubagentStop" in out
    raw = json.dumps(_stop_payload(tasks=[_task()]), indent=1)
    assert _dispatch("SubagentStop", raw, monkeypatch, capsys) == ""
    f = _sdir() / "captures" / "SubagentStop-1.json"
    assert f.read_text() == raw and stat.S_IMODE(f.stat().st_mode) == 0o600
    _dispatch("SubagentStop", raw, monkeypatch, capsys)
    assert _captures() == ["SubagentStop-1.json"]                # the mark is cleared


def test_p6_post_tool_use_keeps_only_bash_and_its_output_is_unchanged(monkeypatch, capsys):
    _session()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    read = {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": "Read",
            "tool_use_id": "toolu_r1", "agent_id": AID, "tool_input": {"file_path": "/tmp/a"}}
    bash = {**read, "tool_name": "Bash", "tool_use_id": "toolu_b1",
            "tool_input": {"command": TEST_CMD}, "tool_response": {"backgroundTaskId": "bg-5"}}
    before = [_dispatch("PostToolUse", p, monkeypatch, capsys) for p in (read, bash)]
    assert _cli("hook", "capture", "PostToolUse", "--count", "2")[0] == 0
    after = [_dispatch("PostToolUse", p, monkeypatch, capsys) for p in (read, bash, bash, bash)]
    assert after[:2] == before
    assert _captures() == ["PostToolUse-1.json", "PostToolUse-2.json"]
    assert json.loads((_sdir() / "captures" / "PostToolUse-1.json").read_text()) == bash


@pytest.mark.parametrize("argv", [("capture", "Stop"), ("capture", "SubagentStop", "--count", "6"),
                                  ("capture", "SubagentStop", "--count", "0"), ("capture",)])
def test_p6_the_verb_refuses_another_event_or_count(argv, monkeypatch):
    _session()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    assert _cli("hook", *argv)[0] == 2 and _captures() == []


def test_p6_show_lists_the_captures_and_the_mark(monkeypatch, capsys):
    _session()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    assert "no capture" in _cli("hook", "capture", "--show")[1]
    _cli("hook", "capture", "SubagentStop", "--count", "2")
    _dispatch("SubagentStop", _stop_payload(), monkeypatch, capsys)
    rc, out, _ = _cli("hook", "capture", "--show")
    assert rc == 0 and "SubagentStop-1.json" in out and "SubagentStop: 1 left" in out


def test_p6_a_fault_in_the_capture_is_swallowed(monkeypatch, capsys):
    _session()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    _cli("hook", "capture", "SubagentStop")
    real = store._write_private

    def boom(path, text):
        if "captures" in str(path):
            raise OSError("hw4")
        return real(path, text)
    monkeypatch.setattr(store, "_write_private", boom)
    _moved()
    assert _dispatch("SubagentStop", _stop_payload(tasks=[_task()]), monkeypatch, capsys) == ""
    assert parked() is not None                                 # the park is still written


def test_p6_the_help_says_the_verb():
    rc, out, _ = _cli("hook", "--help")
    assert rc == 0 and "capture" in out and "--show" in out


# ---- build 2, the fix of review 1: rulings T1 to T7 -------------------------------------------

def _bounded(fn, fifos, secs=5.0):
    """T1: `fn()` in a thread, under a bound this test enforces: past `secs` the FIFOs are
    opened for writing, which frees a reader blocked on one, and the test fails."""
    import threading
    box = []
    t = threading.Thread(target=lambda: box.append(fn()), daemon=True)
    t.start()
    t.join(secs)
    if not t.is_alive():
        return box
    for f in fifos:
        try:
            os.close(os.open(f, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass
    t.join(secs)
    pytest.fail(f"the hook was still reading after {secs} s: {[str(f) for f in fifos]}")


def _fifo(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.mkfifo(path)
    return path


def _bash_post(**extra):
    return {"session_id": SID, "hook_event_name": "PostToolUse", "tool_name": "Bash",
            "tool_use_id": "toolu_hw4_main", "tool_input": {"command": "true"},
            "tool_response": {"stdout": ""}, **extra}


@pytest.mark.parametrize("where", ["captures/PostToolUse.mark.json",
                                   "captures/SubagentStop.mark.json",
                                   f"parked/{BID}.json", f"helper-jobs/{AID}/toolu_hw4_fifo"])
def test_t1_a_fifo_at_a_state_file_is_read_as_absent_and_the_hook_returns(where, monkeypatch,
                                                                          capsys):
    sdir = _session()
    _ledger([_spawn(NOW - 10 * M, AID)])
    f = _fifo(sdir / where)
    post = json.dumps(_bash_post(background_tasks=[]))
    stop = json.dumps(_stop_payload(tasks=[_task()]))
    stopped = json.dumps(_bash_post(tool_name="TaskStop", tool_input={"task_id": "bg-001"}))

    def run():
        for event, raw in (("PostToolUse", post), ("SubagentStop", stop),
                           ("PostToolUse", stopped)):
            monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
            hooks.dispatch(event)
        _launch()
        return hooks.parks(sdir), hooks.captures(sdir)

    got_parks, (_, marks) = _bounded(run, [f])[0]
    capsys.readouterr()
    assert got_parks == {} and marks == {}                        # read as absent
    assert not (sdir / hooks.ENDED / f"{BID}.json").exists()      # an absent park never ends


_ODD = "\\" * 30 + "\x01\x1b\n\t\"é—\x7f" + "\\" * 8                 # 46 characters


@pytest.mark.parametrize("posture", ["off", "signal", "ask", "deny"])
@pytest.mark.parametrize("used", [65.0, 95.0])
@pytest.mark.parametrize("ids", [lambda i: f"shell-{i}-" + "q" * 38, lambda i: _ODD[:-1] + str(i)])
def test_t2_the_whole_output_with_parks_stays_inside_640_bytes(posture, used, ids):
    assert len(ids(0)) == 46
    _parked_ledger(5, tid=ids)
    sdir = _session(used=used, posture=posture)
    out = _launch()
    whole = json.dumps(out)
    assert len(whole) <= hooks.MAX_OUT, (len(whole), whole)
    said = [out.get("systemMessage") or "", (out.get("hookSpecificOutput") or {}).get(
        "additionalContext") or "", (out.get("hookSpecificOutput") or {}).get(
        "permissionDecisionReason") or ""]
    for text in said:
        clause = text[text.find("; parked on"):] if "; parked on" in text else ""
        assert "\\" not in clause and all(" " <= c <= "~" for c in clause), clause
    if posture != "off" and not (posture == "deny" and "reserved" in whole):
        assert "; parked on" in whole                             # the parks are still said
    assert sdir.is_dir()


def test_t3_a_parked_helper_s_stop_with_no_list_leaves_the_park_and_writes_no_end():
    _park()
    before = parked()
    _stop(tasks=None)                                           # no `background_tasks` key
    assert parked() == before and not ended()
    _stop(tasks=[])                                             # the list: the park ends
    assert parked() is None and ended()


def test_t3_a_stop_with_no_list_of_a_helper_with_no_park_is_the_pin_s():
    _session()
    _stop(tasks=None)
    assert parked() is None and ended()
