"""Packet rc2-close-guards: the launcher says an unconfirmed mark's hold (R1), a main-thread
background Bash job is recorded at PostToolUse (R2) and closed by its notice at the prompt
(R3), and a foreground RESPAWN close is refused once while a record is open and not yet
asked about (R4). The chain cases use test_chain.py's fake effects, so no real process runs
and no test reads the live state."""
import hashlib
import json
import os
import stat
import time

import pytest

from claude_session import hooks, resolver, sessionconfig
from test_chain import (G, T0, TERM, C, _frun, _fx, _held, _state, _stops, end,  # noqa: F401
                        fake, hook, respawn_seq)

SID = "test-sess-0000-3333-4444"
CLOSE = "agentik session checkpoint --respawn --charter history/sittings/2026-11-20-2.md"
TID, TASK = "toolu_01ExampleCall", "bkx7q2"
PREFIX = "agentik-session: "


# ---- the chain's harness ---------------------------------------------------------------

def _no_confirm_seq(charter):
    """A sitting's close whose PostToolUse never comes: the marker stands unconfirmed."""
    return [a for a in respawn_seq(charter) if a[0] != 13]


def _peek(box):
    """At the action's time: (held.json, held_line) for the child's session."""
    def act(fx, p):
        box.append((_held(), C().held_line(_state(), "c1", p.sid)))
    return act


def _mark_raw(text):
    def act(fx, p):
        d = resolver.session_dir(_state(), p.sid)
        d.mkdir(parents=True, exist_ok=True)
        (d / hooks.MARKER).write_text(text if isinstance(text, str) else text(p))
    return act


def _confirm_bytes(fx, p):
    """A confirm naming the marker's bytes, as the main thread's PostToolUse writes it."""
    d = resolver.session_dir(_state(), p.sid)
    sha = hashlib.sha256((d / hooks.MARKER).read_bytes()).hexdigest()
    (d / hooks.CONFIRMED).write_text(json.dumps({"at": fx.t, "marker_sha256": sha}))


def _hhmm(t):
    return time.strftime("%H:%M", time.localtime(t))


# ---- Acceptance 1 to 3: the hold is said ------------------------------------------------

def test_1_an_unconfirmed_mark_is_said_after_settle_and_nothing_is_signalled(fake, monkeypatch):
    """The marker (written at +12) with no confirm: nothing before `settle`, then the hold
    `not-main` from the first poll past it (+72). At the pin no file was ever written."""
    seen = []
    seq = _no_confirm_seq(fake.charter) + [(40, _peek(seen)), (100, _peek(seen)),
                                           (3000, _peek(seen)), end(7200)]
    fx = _fx(monkeypatch, [seq, [end(1)]])
    assert _frun(fx, G) == 0
    sid = fx.procs[0].sid
    assert seen[0] == (None, None), seen
    held = {"reason": "not-main", "since": T0 + 72, "session": sid}
    assert seen[1] == (held, f"respawn held: not-main since {_hhmm(T0 + 72)}"), seen
    assert seen[2] == seen[1], "the file keeps its first since"
    assert [p.signals for p in fx.procs] == [[]] and len(fx.procs) == 1


def test_2_a_confirm_clears_the_hold_and_the_restart_runs_as_today(fake, monkeypatch):
    """A confirm naming the marker's bytes, then a ready turn: the hold clears at the next
    poll, the launcher signals after `settle` and restarts; held.json is gone."""
    seen = []
    seq = _no_confirm_seq(fake.charter) + [(199, _peek(seen)), (201, _confirm_bytes),
                                           (202, hook("Stop")), (230, _peek(seen)), end(7200)]
    fx = _fx(monkeypatch, [seq, [end(1)]])
    assert _frun(fx, G) == 0
    assert seen[0][0]["reason"] == "not-main" and seen[1] == (None, None), seen
    ((t, sig),) = fx.procs[0].signals
    assert sig == TERM and 262 <= t - T0 <= 264, t - T0
    assert len(fx.procs) == 2 and _stops() == ["no-marker"] and _held() is None


def test_3_the_exit_while_held_stops_not_main_and_the_file_goes(fake, monkeypatch):
    """The child's exit while the hold stands: the chain stops `not-main`, as at the pin,
    and held.json is removed."""
    seen = []
    seq = _no_confirm_seq(fake.charter) + [(100, _peek(seen)), end(600)]
    fx = _fx(monkeypatch, [seq, [end(1)]])
    assert _frun(fx, G) == 0
    assert seen[0][0]["reason"] == "not-main"
    assert _stops() == ["not-main"] and _held() is None and len(fx.procs) == 1


@pytest.mark.parametrize("case", ["not-json", "another-session", "no-written"])
def test_3_a_marker_that_is_not_this_sittings_gives_no_hold(case, fake, monkeypatch):
    body = {"not-json": "{",
            "another-session": lambda p: json.dumps({"session": "a-different-sitting",
                                                     "charter": "c.md", "written": T0 + 12}),
            "no-written": lambda p: json.dumps({"session": p.sid, "charter": "c.md"})}[case]
    seen = []
    fx = _fx(monkeypatch, [[(12, _mark_raw(body)), (100, _peek(seen)), (3000, _peek(seen)),
                            end(3600)], [end(1)]])
    assert _frun(fx, G) == 0
    assert seen == [(None, None), (None, None)], seen
    assert [p.signals for p in fx.procs] == [[]] and _stops() == ["not-main"]


# ---- the hooks' harness ----------------------------------------------------------------

@pytest.fixture
def hk(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.delenv(hooks.CHAIN_VAR, raising=False)


def use(monkeypatch, posture):
    cfgs = sessionconfig.load_configs()
    cfgs["t"] = sessionconfig.SessionConfig(name="t", posture=posture)
    sessionconfig.save_configs(cfgs)
    monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "t")


def _sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), SID)


def _jobs():
    d = _sdir() / hooks.JOBS
    if not d.is_dir():
        return {}
    return {p.name: json.loads(p.read_text()) for p in d.iterdir()
            if not p.name.startswith(".")}


_DEFAULT = object()


def _post(tid=TID, resp=_DEFAULT, background=None, **extra):
    ti = {"command": "make check > /tmp/check.log 2>&1"}
    if background is not None:
        ti["run_in_background"] = background
    payload = {"session_id": SID, "tool_name": "Bash", "tool_use_id": tid, "tool_input": ti,
               "tool_response": {"stdout": "", "backgroundTaskId": TASK} if resp is _DEFAULT
               else resp, **extra}
    return hooks.post_tool_use(payload, os.environ)


def _job(tid, at, task=None, **more):
    d = _sdir() / hooks.JOBS
    d.mkdir(parents=True, exist_ok=True)
    (d / tid).write_text(json.dumps({"at": at, "task": task, **more}))


def _notice(tid=TID, task=TASK, status="completed"):
    return (f"<task-notification>\n<task-id>{task}</task-id>\n<tool-use-id>{tid}</tool-use-id>\n"
            f"<status>{status}</status>\n<summary>Background command \"make check\" "
            f"completed (exit code 0)</summary>\n</task-notification>")


def _prompt(prompt, **extra):
    return hooks.user_prompt_submit({"session_id": SID, "prompt": prompt, **extra})


def _close(command=CLOSE, background=None, **extra):
    ti = {"command": command}
    if background is not None:
        ti["run_in_background"] = background
    return hooks.pre_tool_use({"session_id": SID, "tool_name": "Bash",
                               "tool_use_id": "toolu_01TheClose", "tool_input": ti, **extra})


def _reason(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecisionReason") if h.get("permissionDecision") == "deny" else None


def _calls():
    d = _sdir() / hooks.CALLS
    return sorted(os.listdir(d)) if d.is_dir() else []


# ---- Acceptance 4: the record ------------------------------------------------------------

def test_4_a_background_result_writes_the_record(hk):
    before = time.time()
    _post()
    rec = _jobs()
    assert list(rec) == [TID] and rec[TID]["task"] == TASK
    assert before <= rec[TID]["at"] <= time.time()
    mode = stat.S_IMODE(os.stat(_sdir() / hooks.JOBS / TID).st_mode)
    assert mode == 0o600


def test_4_run_in_background_with_no_id_writes_task_null(hk):
    _post(resp={"stdout": ""}, background=True)
    assert _jobs()[TID]["task"] is None


@pytest.mark.parametrize("case", ["foreground", "helper", "bad-id", "dots", "no-id",
                                  "empty-task", "string", "list", "null", "not-bash"])
def test_4_no_record(case, hk):
    if case == "foreground":
        _post(resp={"stdout": "ok", "stderr": ""})
    elif case == "helper":
        _post(agent_id="a1")
    elif case == "bad-id":
        _post(tid="toolu 01/x")
    elif case == "dots":
        _post(tid="..")
    elif case == "no-id":
        _post(tid=None)
    elif case == "empty-task":
        _post(resp={"backgroundTaskId": ""})
    elif case in ("string", "list", "null"):
        _post(resp={"string": "backgroundTaskId", "list": ["backgroundTaskId", TASK],
                    "null": None}[case])
    else:
        hooks.post_tool_use({"session_id": SID, "tool_name": "Read", "tool_use_id": TID,
                             "tool_input": {"run_in_background": True},
                             "tool_response": {"backgroundTaskId": TASK}}, os.environ)
    assert _jobs() == {}


# ---- Acceptance 5: the notice ------------------------------------------------------------

@pytest.mark.parametrize("posture", ["signal", "off"])
def test_5_the_notice_closes_the_record(posture, hk, monkeypatch):
    use(monkeypatch, posture)
    _job(TID, time.time(), TASK)
    _prompt(_notice(task="some-other-task"))            # by the call's id
    assert _jobs() == {}
    _job(TID, time.time(), TASK)
    _prompt("the job ended\n" + _notice(tid="toolu_01Elsewhere", status="failed"))  # by task
    assert _jobs() == {}


def test_5_a_notice_naming_neither_leaves_it(hk):
    _job(TID, time.time(), TASK)
    _prompt(_notice(tid="toolu_01Elsewhere", task="another"))
    _prompt("go on")
    assert list(_jobs()) == [TID]


def test_5_two_blocks_remove_two(hk):
    _job(TID, time.time(), TASK)
    _job("toolu_01Second", time.time(), None)
    _job("toolu_01Third", time.time(), "kept")
    _prompt(_notice() + "\n" + _notice(tid="toolu_01Second", task="zz"))
    assert list(_jobs()) == ["toolu_01Third"]


@pytest.mark.parametrize("cut", ["<task-notification>\n<task-id>bkx7q2</task-id>\n"
                                 "<tool-use-id>toolu_01ExampleCall",
                                 "<task-notification><tool-use-id>toolu_01ExampleCall"
                                 "</tool-use-id>"])
def test_5_a_block_cut_short_removes_nothing(cut, hk):
    _job(TID, time.time(), TASK)
    _prompt(cut)
    assert list(_jobs()) == [TID]


def test_5_a_helpers_prompt_closes_nothing(hk):
    _job(TID, time.time(), TASK)
    _prompt(_notice(), agent_id="a1")
    assert list(_jobs()) == [TID]


# ---- Acceptance 6: the refusal -----------------------------------------------------------

@pytest.mark.parametrize("posture", ["signal", "off", "deny"])
def test_6_one_open_record_is_asked_once(posture, hk, monkeypatch):
    use(monkeypatch, posture)
    at = time.time() - 3600
    _job(TID, at, TASK)
    r = _reason(_close())
    assert r and r.startswith(PREFIX) and "\n" not in r and len(r) < 900, r
    assert " 1 " in r and _hhmm(at) in r and "restart" in r and "again" in r, r
    assert _calls() == []
    rec = _jobs()[TID]
    assert isinstance(rec["asked"], float) and rec["at"] == at and rec["task"] == TASK
    assert _reason(_close()) is None                     # the same close again passes
    _job("toolu_01Later", time.time(), None)             # a job recorded after that
    r = _reason(_close())
    assert r and r.startswith(PREFIX), "the next close is denied once more"
    assert _reason(_close()) is None and _calls() == []


def test_6_seven_records_name_five_times_and_two_more(hk):
    base = time.time() - 7 * 600
    for i in range(7):
        _job(f"toolu_01Job{i}", base + 600 * i, f"t{i}")
    r = _reason(_close())
    assert r and " 7 " in r and r.count(":") >= 5 and "and 2 more" in r and len(r) < 900, r
    for i in range(5):
        assert _hhmm(base + 600 * i) in r
    assert all("asked" in v for v in _jobs().values())


def test_6_no_record_passes_as_at_the_pin(hk):
    assert _reason(_close()) is None
    (_sdir() / hooks.JOBS).mkdir(parents=True, exist_ok=True)
    assert _reason(_close()) is None


def test_6_a_background_close_gets_rc1s_line_and_marks_nothing(hk):
    _job(TID, time.time(), TASK)
    assert _reason(_close(background=True)) == hooks.BACKGROUND_CLOSE_DENY
    assert "asked" not in _jobs()[TID]


def test_6_a_helpers_close_meets_no_refusal_from_this_rule(hk):
    _job(TID, time.time(), TASK)
    assert _reason(_close(agent_id="a1")) is None
    assert "asked" not in _jobs()[TID]


def test_6_a_command_that_is_no_close_is_not_refused(hk):
    _job(TID, time.time(), TASK)
    assert _reason(_close(command="agentik session checkpoint")) is None
    assert _reason(_close(command="git status")) is None
    assert "asked" not in _jobs()[TID]


def test_6_the_guards_failure_passes_the_call(hk, monkeypatch):
    _job(TID, time.time(), TASK)

    def boom(*a, **k):
        raise OSError("read-only")
    monkeypatch.setattr(hooks.store, "_write_private", boom)
    assert _reason(_close()) is None


# ---- Acceptance 7: the whole road --------------------------------------------------------

def test_7_record_notice_then_the_close_passes_first_time(hk):
    _post()
    assert list(_jobs()) == [TID]
    _prompt(_notice())
    assert _jobs() == {}
    assert _reason(_close()) is None
