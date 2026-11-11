"""Packets wfg and wfd: the Fable spawn rule through the PreToolUse hook, and `family`.

The script checker is gone with the Workflow tool (packet wfd, `tests/test_wfd.py`): what
stays here is the owner's rule that a Fable helper starts only under a Fable session, the
model records it reads (SessionStart and PostModelSwitch), and its failure that denies.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import config, hooks

ROOT = Path(__file__).resolve().parents[1]
SID = "test-sess-0000-1111-2222"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()


def guard():
    from claude_session import workflowguard
    return workflowguard


def sdir():
    import os
    d = hooks._session_dir(SID, os.environ)
    d.mkdir(parents=True, exist_ok=True)
    return d


def parent(model=None, meter=None):
    """Seed the session's two model records: model.json and the meter's."""
    for name, m in (("model.json", model), ("meter.json", meter)):
        p = sdir() / name
        if m is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps({"model": m}))


def reason(out):
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny" and hso["hookEventName"] == "PreToolUse"
    r = hso["permissionDecisionReason"]
    assert "\n" not in r and len(r) < 900, r          # one line an orchestrator can act on
    assert r.startswith("agentik-session: ")
    return r


def spawn(model=None, tool="Agent", **extra):
    ti = {"prompt": "p", "description": "d"}
    if model is not None:
        ti["model"] = model
    return hooks.pre_tool_use({"tool_name": tool, "session_id": SID, "tool_input": ti, **extra})


# --- T7: a Fable helper starts only under a Fable session (the owner's rule) --------------

def test_t7_an_opus_session_cannot_start_a_fable_helper():
    parent("claude-opus-5-5", "claude-opus-5-5")
    for tool in ("Agent", "Task"):
        r = reason(spawn("fable", tool=tool))
        assert "a Fable helper starts only under a Fable session: this one runs opus" in r
    assert "this one runs opus" in reason(spawn("claude-fable-5-2"))
    assert spawn("opus") == {} and spawn("sonnet") == {} and spawn() == {}


def test_t7_a_fable_session_may_start_a_fable_helper():
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {} and spawn("opus") == {} and spawn() == {}
    parent("claude-fable-5-2", None)                    # SessionStart's record, no meter yet
    assert spawn("fable") == {}


def test_t7_a_switch_mid_session_counts(tmp_path):
    start = {"session_id": SID, "model": "claude-fable-5-2", "cwd": str(tmp_path),
             "hook_event_name": "SessionStart", "source": "startup"}
    hooks.session_start(start)
    assert json.loads((sdir() / "model.json").read_text())["model"] == "claude-fable-5-2"
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {}
    switch = {"session_id": SID, "hook_event_name": "PostModelSwitch",
              "from_model": "claude-fable-5-2", "to_model": "claude-opus-5-5"}
    assert hooks.HANDLERS["PostModelSwitch"](switch) == {}
    rec = json.loads((sdir() / "model.json").read_text())
    assert rec["model"] == "claude-opus-5-5" and rec["from"] == "switch"
    # the meter still holds the last Fable line: the two disagree, and the spawn is denied
    assert "the session's model is not known" in reason(spawn("fable"))
    parent("claude-opus-5-5", "claude-opus-5-5")        # the meter has read an Opus line
    assert "this one runs opus" in reason(spawn("fable"))
    # no PostModelSwitch on this CLI: the start's record is stale, the meter says Opus
    parent("claude-fable-5-2", "claude-opus-5-5")
    assert "the session's model is not known" in reason(spawn("fable"))
    # back to Fable: denied until both records say so
    hooks.HANDLERS["PostModelSwitch"]({**switch, "to_model": "claude-fable-5-2"})
    assert "retry after one tool call" in reason(spawn("fable"))
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {}


def test_t7_the_model_unknown_fails_closed_for_fable_only():
    parent()
    assert "the session's model is not known" in reason(spawn("fable"))
    assert spawn("opus") == {} and spawn() == {}
    parent("claude-fable-5-2", "claude-fable-5-2")      # a helper's own model is not the session's
    assert "not known" in reason(spawn("fable", agent_id="a1", tool_use_id="toolu_h1"))
    assert not (sdir() / "calls" / "toolu_h1").exists()         # a denied call opens no call
    hooks.HANDLERS["PostModelSwitch"]({"session_id": SID, "agent_id": "a1", "to_model": "x"})
    assert json.loads((sdir() / "model.json").read_text())["model"] == "claude-fable-5-2"



# --- T10: the event is registered and its hook is silent ---------------------------------

def test_t10_post_model_switch_is_registered_and_silent(tmp_path):
    doc = json.loads((ROOT / "plugin" / "hooks" / "hooks.json").read_text())
    cmd = doc["hooks"]["PostModelSwitch"][0]["hooks"][0]["command"]
    assert cmd.endswith('/hooks/run" PostModelSwitch')
    assert "PostModelSwitch" in hooks.SILENT
    shim = (ROOT / "plugin" / "hooks" / "run").read_text()
    assert "PostToolBatch|PostModelSwitch)" in shim
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, "-I", str(ROOT / "plugin" / "lib" / "agentik-session"),
                        "hook", "PostModelSwitch"], env=env, capture_output=True, text=True,
                       input=json.dumps({"session_id": "sw-1", "to_model": "claude-opus-5-5"}))
    assert (r.returncode, r.stdout) == (0, ""), r
    rec = list((tmp_path / "state").rglob("model.json"))
    assert len(rec) == 1 and json.loads(rec[0].read_text())["model"] == "claude-opus-5-5"



# --- T17: an exception in the agent rule denies ------------------------------------------

def test_t17_an_exception_in_the_agent_rule_denies(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("probe")
    monkeypatch.setattr(hooks, "_session_family", boom)
    assert "fails closed" in reason(spawn("fable"))
    assert "fails closed" in reason(spawn("claude-fable-5-2"))
    monkeypatch.setattr(guard(), "family", boom)
    assert "fails closed" in reason(spawn("opus"))

