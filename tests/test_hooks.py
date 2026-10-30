import json

import pytest

from claude_session import budget, config, hooks, sessionconfig

SID = "test-sess-0000-1111-2222"
_ENV = {}   # the running test's monkeypatch, for use() (ADV6-6: no bare os.environ writes)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    _ENV["mp"] = monkeypatch
    config.ensure_dirs()


def use(posture="signal", checkpoint=None, name="t"):
    cfgs = sessionconfig.load_configs()
    c = sessionconfig.SessionConfig(name=name, posture=posture)
    if checkpoint is not None:
        c.checkpoint = checkpoint
    cfgs[name] = c
    sessionconfig.save_configs(cfgs)
    _ENV["mp"].setenv("CLAUDE_SESSION_CONFIG", name)
    return c


@pytest.fixture
def seed(monkeypatch):
    """Stand in for the meter: the zone's input is the caller's used_pct."""
    def _seed(used_pct):
        monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: used_pct)
    return _seed


# --- posture governs whether anything is ever blocked -----------------------

def test_signal_posture_never_blocks_a_spawn(seed):
    """The default. A full budget is a signal, not an error."""
    use("signal")
    seed(97.0)
    assert hooks.pre_tool_use({"tool_name": "Agent"}) == {}


def test_off_posture_says_nothing_at_all(seed):
    use("off")
    seed(97.0)
    assert hooks.pre_tool_use({"tool_name": "Agent"}) == {}
    assert hooks.user_prompt_submit({}) == {}


def test_deny_posture_blocks_in_reserve_with_the_remedy(seed):
    use("deny")
    seed(97.0)
    out = hooks.pre_tool_use({"tool_name": "Agent"})
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    # A block that does not say what to do instead just gets retried.
    assert "clean stopping point" in hso["permissionDecisionReason"]
    assert "systemMessage" in out


def test_ask_posture_asks_rather_than_blocks(seed):
    use("ask")
    seed(97.0)
    out = hooks.pre_tool_use({"tool_name": "Agent"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_deny_posture_still_only_asks_before_the_reserve(seed):
    use("deny")
    seed(90.5)          # wind-down, not reserve
    assert hooks.pre_tool_use({"tool_name": "Agent"})[
        "hookSpecificOutput"]["permissionDecision"] == "ask"


def test_only_spawning_tools_are_gated(seed):
    use("deny")
    seed(97.0)
    for tool in ("Read", "Edit", "Bash", "Grep"):
        assert hooks.pre_tool_use({"tool_name": tool}) == {}
    assert hooks.pre_tool_use({"tool_name": "Workflow"}) != {}


# --- the checkpoint cadence is the real mechanism ---------------------------

def test_checkpoint_nudge_fires_at_the_zone_cadence(seed):
    use("signal", checkpoint={"clear": 3, "notice": 2, "wind-down": 1, "reserve": 1})
    seed(10.0)                                  # clear -> cadence 3
    for _ in range(2):
        assert "checkpoint" not in json.dumps(hooks.user_prompt_submit({}))
    out = hooks.user_prompt_submit({})           # third prompt
    assert "checkpoint" in out["hookSpecificOutput"]["additionalContext"]


def test_cadence_tightens_as_the_budget_fills(seed):
    use("signal", checkpoint={"clear": 25, "notice": 2, "wind-down": 1, "reserve": 1})
    seed(85.0)                                  # notice -> cadence 2
    hooks.user_prompt_submit({})
    ctx = hooks.user_prompt_submit({})["hookSpecificOutput"]["additionalContext"]
    assert "2 prompts since the last checkpoint" in ctx


def test_checkpoint_resets_the_counter(seed):
    use("signal", checkpoint={"clear": 2, "notice": 2, "wind-down": 1, "reserve": 1})
    seed(10.0)
    hooks.user_prompt_submit({})
    sessionconfig.save_overlay({hooks.COUNTER: 0})     # what `checkpoint` does
    assert "checkpoint" not in json.dumps(hooks.user_prompt_submit({}))


def test_zero_cadence_disables_nudging(seed):
    use("signal", checkpoint={"clear": 0, "notice": 0, "wind-down": 0, "reserve": 0})
    seed(10.0)
    for _ in range(10):
        assert hooks.user_prompt_submit({}) == {}


def test_reserve_zone_asks_for_a_handoff_not_a_block(seed):
    use("signal")
    seed(97.0)
    ctx = hooks.user_prompt_submit({})["hookSpecificOutput"]["additionalContext"]
    assert "handoff" in ctx and "clean stopping point" in ctx


# --- refusing to guess ------------------------------------------------------

def test_no_meter_means_no_opinion():
    """Until a meter supplies used_pct the zone is unknown and hooks are silent."""
    use("deny", checkpoint={"clear": 1, "notice": 1, "wind-down": 1, "reserve": 1})
    assert hooks.state()[1] == budget.UNKNOWN
    assert hooks.pre_tool_use({"tool_name": "Agent"}) == {}
    for _ in range(3):
        assert hooks.user_prompt_submit({}) == {}
    assert "budget" not in json.dumps(hooks.session_start({}))


# --- session end drops the overlay ------------------------------------------

def test_session_end_clears_session_only_adjustments():
    sessionconfig.save_overlay({"posture": "deny"})
    assert sessionconfig.load_overlay().get("posture") == "deny"
    hooks.session_end({})
    assert sessionconfig.load_overlay() == {}


# --- never break a session --------------------------------------------------

def test_dispatch_never_crashes_a_tool_call(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("not json{{"))
    assert hooks.dispatch("pre-tool-use") == 0
    assert json.loads(capsys.readouterr().out) == {}


def test_dispatch_survives_a_broken_handler(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("{}"))
    monkeypatch.setitem(hooks.HANDLERS, "pre-tool-use",
                        lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    assert hooks.dispatch("pre-tool-use") == 0
    assert json.loads(capsys.readouterr().out) == {}


# The spawn gate from resolved.json and meter.json (S5): the repo's posture
# reaches pre_tool_use through SessionStart, the zone through PostToolUse.

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AT_100 = ROOT / "tests" / "fixtures" / "meter" / "at-100.jsonl"


def gate(tmp_path, monkeypatch, posture, payload=None):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    repo = tmp_path / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True)
    (repo / ".claude" / "agentik" / "config.yaml").write_text(
        'session: {posture: "%s"}\n' % posture)
    import os
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_CONFIG"}
    assert hooks.session_start({"session_id": "g", "cwd": str(repo)}, env)
    hooks.post_tool_use({"session_id": "g", "transcript_path": str(AT_100),
                         "tool_name": "Read"}, env)
    assert hooks.used_pct("g", env) >= 100.0
    return hooks.pre_tool_use(payload or {"session_id": "g", "tool_name": "Agent",
                                          "tool_input": {}}, env)


@pytest.mark.parametrize("posture, decision", [
    ("off", None), ("signal", None), ("ask", "ask"), ("deny", "deny")])
def test_gate_per_posture_at_100(tmp_path, monkeypatch, posture, decision):
    use("signal")                      # the old store says signal; resolved.json wins
    out = gate(tmp_path, monkeypatch, posture)
    got = (out.get("hookSpecificOutput") or {}).get("permissionDecision")
    assert got == decision
    if decision == "deny":
        assert "[frontier]" in out["systemMessage"]


def test_gate_is_silent_for_a_subagent(tmp_path, monkeypatch):
    out = gate(tmp_path, monkeypatch, "deny",
               {"session_id": "g", "tool_name": "Agent", "agent_id": "a1"})
    assert out == {}


def test_gate_reads_the_environment_id_when_stdin_has_none(tmp_path, monkeypatch):
    gate(tmp_path, monkeypatch, "deny")
    import os
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID="g")
    out = hooks.pre_tool_use({"tool_name": "Workflow"}, env)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---- S19: the stamps, Stop and the main thread's confirmation (respawn-r1 §3.2, §3.3) ----

import hashlib
import io
import os
import time

from claude_session import resolver, store

MARK = "agentik-session checkpoint --respawn --charter history/sittings/2026-10-10-1.md"


def _sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), SID)


def _stamp(name):
    p = _sdir() / name
    return json.loads(p.read_text()) if p.exists() else None


def _bash(command=MARK, **extra):
    return {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": command}, **extra}


def _mark(written):
    """A marker as the verb writes it; returns the sha256 of its bytes."""
    p = _sdir() / "respawn.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"session": SID, "charter": "/r/c.md", "charter_sha256": "0" * 64,
                             "written": written, "chain": None}))
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_s19_main_thread_confirms_the_marker():
    use("signal")
    _mark(time.time())
    assert hooks.post_tool_use(_bash()) == {}          # no activity.json: no confirmation
    assert _stamp("respawn-main.json") is None
    assert hooks.pre_tool_use(_bash()) == {}
    at = _stamp("activity.json")["at"]
    sha = _mark(at)                                    # written at the call's own stamp
    assert hooks.post_tool_use(_bash()) == {}
    d = _stamp("respawn-main.json")
    assert sorted(d) == ["at", "marker_sha256"] and d["marker_sha256"] == sha
    assert at <= d["at"] <= time.time()
    assert stat_mode(_sdir() / "respawn-main.json") == 0o600


def stat_mode(p):
    return os.stat(p).st_mode & 0o777


@pytest.mark.parametrize("spelling", ["agentik-session", "agentik session", "claude-session"])
def test_ruling9_each_checkpoint_spelling_confirms(spelling):
    # agentik-r1 packet ruling 9: the tool, the front door and the pre-rename alias
    use("signal")
    cmd = f"{spelling} checkpoint --respawn --charter c.md"
    hooks.pre_tool_use(_bash(cmd))
    sha = _mark(_stamp("activity.json")["at"])
    hooks.post_tool_use(_bash(cmd))
    assert _stamp("respawn-main.json")["marker_sha256"] == sha


@pytest.mark.parametrize("defect", ["agent_id", "no-respawn", "stale"])
def test_s19_unconfirmed_marks(defect):
    use("signal")
    hooks.pre_tool_use(_bash())
    at = _stamp("activity.json")["at"]
    _mark(at - 5 if defect == "stale" else at)
    payload = {"agent_id": _bash(agent_id="a1"),
               "no-respawn": _bash("agentik-session checkpoint --charter c.md"),
               "stale": _bash()}[defect]
    hooks.post_tool_use(payload)
    assert _stamp("respawn-main.json") is None
    sha = _mark(at)                                    # the positive control: no defect
    hooks.post_tool_use(_bash())
    assert _stamp("respawn-main.json")["marker_sha256"] == sha


def _call(event, payload):
    if event == "PreToolUse":
        return hooks.pre_tool_use({**payload, "tool_name": "Read"})
    if event == "UserPromptSubmit":
        return hooks.user_prompt_submit(payload)
    return hooks.stop(payload)


@pytest.mark.parametrize("event", ["PreToolUse", "UserPromptSubmit", "Stop"])
def test_s19_main_thread_stamps(event):
    use("signal")
    name = "turn-ended.json" if event == "Stop" else "activity.json"
    _call(event, {"session_id": SID, "agent_id": "a1"})     # a helper's payload: none
    _call(event, {})                                       # the payload's id only, never the env's
    assert not (_sdir() / name).exists()
    t0 = time.time()
    _call(event, {"session_id": SID})
    d = _stamp(name)
    assert sorted(d) == (["at"] if event == "Stop" else ["at", "event", "tool"])
    assert t0 <= d["at"] <= time.time()
    if event != "Stop":
        assert (d["event"], d["tool"]) == (event, "Read" if event == "PreToolUse" else None)


def test_s19_helper_activity_stamp():
    use("signal")
    hooks.pre_tool_use({"session_id": SID, "agent_id": "a1", "tool_name": "Grep"})
    d = _stamp("helper-activity.json")
    assert sorted(d) == ["at", "event", "tool"] and (d["event"], d["tool"]) == ("PreToolUse", "Grep")
    assert [p.name for p in _sdir().iterdir()] == ["helper-activity.json"]
    # A helper's PostToolUse rewrites only its stamp: no meter, no main-thread stamp.
    hooks.post_tool_use({"session_id": SID, "agent_id": "a1", "tool_name": "Grep",
                         "transcript_path": str(AT_100)})
    d = _stamp("helper-activity.json")
    assert (d["event"], d["tool"]) == ("PostToolUse", "Grep")
    assert [p.name for p in _sdir().iterdir()] == ["helper-activity.json"]


def test_s19_stamps_ignore_posture(seed, monkeypatch):
    use("off")
    seed(97.0)
    assert hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent"}) == {}
    assert _stamp("activity.json")["tool"] == "Agent"
    assert hooks.user_prompt_submit({"session_id": SID}) == {}
    assert _stamp("activity.json")["event"] == "UserPromptSubmit"
    assert hooks.stop({"session_id": SID}) == {}
    assert _stamp("turn-ended.json")
    use("deny")                 # a failed stamp is swallowed and changes no output
    want = hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent"})
    assert want["hookSpecificOutput"]["permissionDecision"] == "deny"

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(store, "_write_private", boom)
    assert hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent"}) == want
    assert hooks.stop({"session_id": SID}) == {}


@pytest.mark.parametrize("case", ["payload", "bad-stdin", "raising", "deep-json"])
def test_s19_stop_prints_nothing(case, capsys, monkeypatch):
    stdin = {"bad-stdin": "not json{{", "deep-json": "[" * 100000}.get(
        case, json.dumps({"session_id": SID}))
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    if case == "raising":
        monkeypatch.setitem(hooks.HANDLERS, "Stop",
                            lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    assert hooks.dispatch("Stop") == 0
    assert capsys.readouterr().out == ""
    assert (_sdir() / "turn-ended.json").exists() is (case == "payload")


def test_s19_stop_survives_binary_stdin():
    # Under a UTF-8 locale a non-UTF-8 stdin fails the read itself, before any JSON.
    import subprocess
    import sys
    env = {k: v for k, v in os.environ.items()
           if k not in ("LC_ALL", "LC_CTYPE", "PYTHONIOENCODING", "PYTHONUTF8")}
    r = subprocess.run([sys.executable, "-B", "-m", "claude_session", "hook", "Stop"],
                       input=b"\xff\xfe{\x00", capture_output=True, cwd=ROOT,
                       env={**env, "LANG": "en_US.UTF-8"})
    assert (r.returncode, r.stdout) == (0, b""), r.stderr


# ---- S20a: a helper's open calls (packet S20 ruling 2) --------------------------------

@pytest.mark.parametrize("case", ["post", "failure", "bad-id", "main-thread"])
def test_s20a_open_calls(case):
    """A helper's PreToolUse whose `tool_use_id` is id-shaped opens `calls/<id>`; its
    PostToolUse or PostToolUseFailure removes it; another id opens nothing; the main
    thread opens none. A call never closed holds the sitting."""
    use("signal")
    calls = _sdir() / "calls"
    helper = {"session_id": SID, "agent_id": "a1", "tool_name": "Bash"}

    def names():
        return sorted(p.name for p in calls.iterdir()) if calls.exists() else []
    if case == "bad-id":
        for bad in ("../x", "a b", "", None, 7, "x" * 129):
            hooks.pre_tool_use({**helper, "tool_use_id": bad})
        assert names() == []
        hooks.pre_tool_use({**helper, "tool_use_id": "toolu_ok"})       # the positive control
        assert names() == ["toolu_ok"]
        return
    if case == "main-thread":
        hooks.pre_tool_use({"session_id": SID, "tool_name": "Bash", "tool_use_id": "toolu_01"})
        assert names() == []
        hooks.pre_tool_use({**helper, "tool_use_id": "toolu_01"})       # the positive control
        assert names() == ["toolu_01"]
        return
    hooks.pre_tool_use({**helper, "tool_use_id": "toolu_01"})
    hooks.pre_tool_use({**helper, "tool_use_id": "toolu_02"})
    assert names() == ["toolu_01", "toolu_02"]
    close = hooks.post_tool_use if case == "post" else hooks.post_tool_use_failure
    assert close({**helper, "tool_use_id": "toolu_01"}) == {}
    assert names() == ["toolu_02"]
    close({"session_id": SID, "tool_name": "Bash", "tool_use_id": "toolu_02"})  # main: none
    assert names() == ["toolu_02"]


@pytest.mark.parametrize("close", ["post", "failure"])
def test_s20a_close_stamps_before_it_closes(close, monkeypatch):
    """B-F1: the helper's stamp lands before its call closes, so no reader sees neither."""
    use("signal")
    order = []
    stamp, shut = hooks._tool_stamp, hooks._close_call
    monkeypatch.setattr(hooks, "_tool_stamp", lambda *a: (order.append("stamp"), stamp(*a))[1])
    monkeypatch.setattr(hooks, "_close_call", lambda *a: (order.append("close"), shut(*a))[1])
    fn = hooks.post_tool_use if close == "post" else hooks.post_tool_use_failure
    fn({"session_id": SID, "agent_id": "a1", "tool_name": "Bash", "tool_use_id": "toolu_01"})
    assert order == ["stamp", "close"]


# ---- the stale call (2026-10-11): PostToolBatch closes a blocked helper call ----------

@pytest.mark.parametrize("case", ["blocked", "batch", "main-thread", "bad-calls"])
def test_s22_batch_closes_its_calls(case):
    """A helper's PostToolBatch closes the open call of every `tool_use_id` it lists (a
    call another PreToolUse hook blocked gets no Post and no Failure); a call it does not
    list stays open; the main thread's batch writes nothing; a malformed batch never raises."""
    use("signal")
    calls = _sdir() / "calls"
    helper = {"session_id": SID, "agent_id": "a1", "tool_name": "Bash"}

    def names():
        return sorted(p.name for p in calls.iterdir()) if calls.exists() else []

    def batch(payload, *ids):
        return hooks.HANDLERS["PostToolBatch"]({
            **payload, "hook_event_name": "PostToolBatch",
            "tool_calls": [{"tool_name": "Bash", "tool_input": {}, "tool_use_id": i,
                            "tool_response": "BLOCKED"} for i in ids]})
    for tid in ("toolu_01", "toolu_02", "toolu_03"):
        hooks.pre_tool_use({**helper, "tool_use_id": tid})
    assert names() == ["toolu_01", "toolu_02", "toolu_03"]
    if case == "blocked":
        assert batch({"session_id": SID, "agent_id": "a1"}, "toolu_01") == {}
        assert names() == ["toolu_02", "toolu_03"]
    elif case == "batch":
        batch({"session_id": SID, "agent_id": "a1"}, "toolu_01", "toolu_03", "toolu_09")
        assert names() == ["toolu_02"]
    elif case == "main-thread":
        before = sorted(p.name for p in _sdir().iterdir())
        assert batch({"session_id": SID}, "toolu_01", "toolu_02") == {}
        assert names() == ["toolu_01", "toolu_02", "toolu_03"]
        assert sorted(p.name for p in _sdir().iterdir()) == before          # no activity.json
        batch({"session_id": SID, "agent_id": "a1"}, "toolu_02")        # the positive control
        assert names() == ["toolu_01", "toolu_03"]
    else:
        fn = hooks.HANDLERS["PostToolBatch"]
        for bad in (None, 7, "toolu_01", {"tool_use_id": "toolu_01"}, [None, 7, "toolu_01"],
                    [{"tool_use_id": "../toolu_01"}, {"tool_use_id": None}, {}]):
            assert fn({"session_id": SID, "agent_id": "a1", "tool_calls": bad}) == {}
        assert names() == ["toolu_01", "toolu_02", "toolu_03"]
        batch({"session_id": SID, "agent_id": "a1"}, "toolu_01")        # the positive control
        assert names() == ["toolu_02", "toolu_03"]


def test_s22_batch_stamps_before_it_closes(monkeypatch):
    """B-F1, as for Post and Failure: the helper's stamp lands before its calls close."""
    use("signal")
    hooks.pre_tool_use({"session_id": SID, "agent_id": "a1", "tool_name": "Bash",
                        "tool_use_id": "toolu_01"})
    order = []
    stamp, shut = hooks._tool_stamp, hooks._close_call
    monkeypatch.setattr(hooks, "_tool_stamp", lambda *a: (order.append("stamp"), stamp(*a))[1])
    monkeypatch.setattr(hooks, "_close_call", lambda *a: (order.append("close"), shut(*a))[1])
    hooks.HANDLERS["PostToolBatch"]({"session_id": SID, "agent_id": "a1", "tool_calls": [
        {"tool_name": "Bash", "tool_use_id": "toolu_01"}]})
    assert order == ["stamp", "close"]
    assert json.loads((_sdir() / hooks.HELPER_ACTIVITY).read_text())["event"] == "PostToolBatch"


# --- the gate's inbox (S38 ruling 3) ------------------------------------------

def _gate_results(n, repo="/r/x", log="/s"):
    return [{"id": f"20261029-120000-{i}", "repo": repo, "exit": 0, "seconds": 60.0,
             "log": f"{log}/gate/20261029-120000-{i}/log", "ended": 1.0 + i}
            for i in range(1, n + 1)]


def _inbox(results):
    import os
    from claude_session import gate, resolver
    root = resolver.state_dir(os.environ)
    for r in results:
        gate.inbox_write(root, SID, r)
    return root / "sessions" / SID / "inbox"


def test_gate_inbox_ten_files_stay_under_max_out():
    from claude_session import gate
    rs = _gate_results(10)
    _inbox(rs)
    out = hooks.user_prompt_submit({"session_id": SID})
    block = out["hookSpecificOutput"]["additionalContext"].split("\n\n")[0]
    assert block.splitlines() == [gate.wait_line(r) for r in rs[:3]] + \
        ["7 more: agentik session gate status"]
    assert len(json.dumps(out)) <= hooks.MAX_OUT
    out = hooks.post_tool_use({"session_id": SID})
    assert out["hookSpecificOutput"]["additionalContext"].splitlines() == \
        [gate.wait_line(r) for r in rs[3:6]] + ["4 more: agentik session gate status"]
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_gate_inbox_long_paths_take_fewer_and_still_fit_max_out():
    box = _inbox(_gate_results(10, repo="/r/" + "x" * 150, log="/s/" + "y" * 150))
    for event in (hooks.user_prompt_submit, hooks.post_tool_use):
        out = event({"session_id": SID})
        assert len(json.dumps(out)) <= hooks.MAX_OUT
        lines = out["hookSpecificOutput"]["additionalContext"].split("\n\n")[0].splitlines()
        left = len(list(box.glob("*.json")))
        assert lines[-1] == f"{left} more: agentik session gate status"
    assert len(list((box / "read").glob("*.json"))) + left == 10


def test_gate_inbox_is_read_whatever_the_posture_and_never_by_a_helper():
    from claude_session import gate
    use("off")
    rs = _gate_results(1)
    box = _inbox(rs)
    assert hooks.user_prompt_submit({"session_id": SID, "agent_id": "a1"}) == {}
    assert hooks.post_tool_use({"session_id": SID, "agent_id": "a1"}) == {}
    assert len(list(box.glob("*.json"))) == 1
    out = hooks.user_prompt_submit({"session_id": SID})
    assert out["hookSpecificOutput"]["additionalContext"] == gate.wait_line(rs[0])
    assert hooks.user_prompt_submit({"session_id": SID}) == {}
