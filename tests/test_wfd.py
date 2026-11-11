"""Packet wfd: the Workflow tool denied outright, through the PreToolUse hook.

The suite runs no workflows: every Workflow call is denied with one line, whatever it
carries, and the rule reads nothing of the call. The Fable rule on Agent and Task stays.
"""
import json
import os
import statistics
import threading
import time

import pytest

from claude_session import config, hooks, sessionconfig

SID = "test-sess-wfd0-1111-2222"
LINE = ("agentik-session: Workflow denied: this suite runs no workflows. Spawn helpers with "
        "the Agent tool, each naming its model; do not call Workflow again.")
DENY = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                               "permissionDecisionReason": LINE}}
META = "export const meta = { name: 'x', description: 'y' }\n"
TWO_OPUS = (META + "await parallel([\n"
            "  () => agent('read the area', { label: 'a', model: 'opus' }),\n"
            "  () => agent('verify the claims', { label: 'b', model: 'opus' }),\n"
            "])\n")
FABLE_UNDER_OPUS = ("agentik-session: a Fable helper starts only under a Fable session: "
                    "this one runs opus. Name model: 'opus'.")
FABLE_UNKNOWN = ("agentik-session: a Fable helper starts only under a Fable session: "
                 "the session's model is not known (no record yet, or a switch its records "
                 "have not both seen: retry after one tool call). Name model: 'opus'.")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()


def sdir():
    d = hooks._session_dir(SID, os.environ)
    d.mkdir(parents=True, exist_ok=True)
    return d


def parent(model=None):
    """Seed the session's two model records, model.json and the meter's, alike."""
    for name in ("model.json", "meter.json"):
        p = sdir() / name
        if model is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps({"model": model}))


def call(tool_input=..., **extra):
    payload = {"tool_name": "Workflow", "session_id": SID, "tool_use_id": "toolu_wfd", **extra}
    if tool_input is not ...:
        payload["tool_input"] = tool_input
    return hooks.pre_tool_use(payload)


def spawn(model=None, tool="Agent"):
    ti = {"prompt": "p", "description": "d"}
    if model is not None:
        ti["model"] = model
    return hooks.pre_tool_use({"tool_name": tool, "session_id": SID, "tool_input": ti})


class Trap(dict):
    """A tool_input that raises on any read: the rule must never touch it."""
    def _boom(self, *a, **k):
        raise AssertionError("the rule read the call")
    __getitem__ = __contains__ = __iter__ = __len__ = get = keys = items = values = _boom


# --- T1: a script the pin allowed -------------------------------------------------------

def test_t1_two_opus_agents_in_one_script_are_denied():
    parent("claude-opus-5-5")
    assert call({"script": TWO_OPUS}) == DENY
    parent("claude-fable-5-2")
    assert call({"script": TWO_OPUS}) == DENY


# --- T2: scriptPath is never opened ------------------------------------------------------

def test_t2_script_path_of_any_kind_is_denied_unread(tmp_path):
    big = tmp_path / "big.js"
    big.write_text(TWO_OPUS + "// " + "x" * (1024 * 1024) + "\n")
    small = tmp_path / "small.js"
    small.write_text(TWO_OPUS)
    for path in (tmp_path / "missing.js", tmp_path, big, small):
        assert call({"scriptPath": str(path)}) == DENY, path


def test_t2_a_fifo_is_never_opened(tmp_path):
    fifo = tmp_path / "script.fifo"
    os.mkfifo(fifo)
    out = {}
    t = threading.Thread(target=lambda: out.update(r=call({"scriptPath": str(fifo)})),
                         daemon=True)
    t.start()
    t.join(2.0)
    if t.is_alive():                                    # opened: release the reader, then fail
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        t.join(2.0)
        pytest.fail("the rule opened the FIFO")
    assert out["r"] == DENY


# --- T3: a name, nothing, or no mapping --------------------------------------------------

@pytest.mark.parametrize("ti", [{"name": "sweep"}, {}, ["script"], "script", None, ...,
                                {"script": TWO_OPUS, "scriptPath": "/nonexistent.js"}],
                         ids=["name", "empty", "list", "string", "null", "absent", "both"])
def test_t3_a_call_of_any_shape_is_denied(ti):
    assert call(ti) == DENY


def test_t3_the_rule_reads_nothing_of_the_call():
    assert call(Trap(script=TWO_OPUS)) == DENY


# --- T4: every posture, and a helper's call ----------------------------------------------

@pytest.mark.parametrize("posture", ["off", "signal", "ask", "deny"])
def test_t4_every_posture_denies(monkeypatch, posture):
    cfgs = sessionconfig.load_configs()
    cfgs["t"] = sessionconfig.SessionConfig(name="t", posture=posture)
    sessionconfig.save_configs(cfgs)
    monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "t")
    assert call({"script": TWO_OPUS}) == DENY


def test_t4_a_helpers_call_is_denied_and_opens_no_call():
    parent("claude-opus-5-5")
    assert call({"script": TWO_OPUS}, agent_id="a1") == DENY
    assert not (sdir() / "calls" / "toolu_wfd").exists()


# --- T5: the line ------------------------------------------------------------------------

def test_t5_the_line_is_one_short_line_naming_the_agent_tool():
    assert "\n" not in LINE and len(LINE.encode()) < 200
    assert "Agent tool" in LINE
    assert "fix the script" not in LINE.lower() and "before launch" not in LINE
    assert hooks._spawn_rule({"tool_name": "Workflow"}, {}) == LINE


# --- T6, T7: the Fable rule on Agent and Task, as at the pin ------------------------------

def test_t6_agent_and_task_pass_as_at_the_pin():
    parent("claude-opus-5-5")
    assert spawn("opus") == {} and spawn() == {} and spawn(tool="Task") == {}
    assert spawn("opus", tool="Task") == {}


def test_t7_a_fable_helper_under_opus_or_unknown_is_denied_as_at_the_pin():
    parent("claude-opus-5-5")
    for tool in ("Agent", "Task"):
        out = spawn("fable", tool=tool)
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == FABLE_UNDER_OPUS
    parent()
    out = spawn("fable")
    assert out["hookSpecificOutput"]["permissionDecisionReason"] == FABLE_UNKNOWN
    assert out["systemMessage"] == "agentik-session: denied a Agent spawn before launch."


# --- T8: the cost does not grow with the script ------------------------------------------

def test_t8_a_256_kb_script_costs_what_an_agent_call_costs():
    parent("claude-opus-5-5")
    pad = "    // Read the area's files and report each claim with the command that shows it.\n"
    src = TWO_OPUS.replace("])\n", pad * ((256_000 - len(TWO_OPUS)) // len(pad)) + "])\n")
    assert 255_000 < len(src) <= 256_000                # 256 KB: under the pin's 256 KiB cap

    def cpu(fn):
        times = []
        for _ in range(9):
            t0 = time.process_time()
            fn()
            times.append(time.process_time() - t0)
        return statistics.median(times)

    wf = cpu(lambda: call({"script": src}))
    agent = cpu(lambda: spawn("opus"))
    assert wf - agent < 0.020, (wf, agent)
