"""Packet hw2-helper-rules: under `helpers.wait`, the PreToolUse hook also refuses (`refuse`) or
says (`say`) a helper's background shell, `gate run --wait`, a `gate wait` with no bound of 100 s
or less, sleeps adding to a minute and a sleep in a loop; SubagentStart says the rule to each
helper; `helpers.heavy` lists a repo's heavy commands. `allow` keeps the pin's output.

Every state is under the per-test temp roots (conftest); no test starts a `claude` or a `make`.
"""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import doctor, harness, hooks, plug, resolver, shellreader, store
from claude_session.resolver import ResolveError, resolve

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SID = "hw2-session-0001"
HELPER = "agent-hw2-a"
RULE = ("Queue the run with agentik session gate run <dir> --label <row> -- <command> (add "
        "--within 100 to wait once), write gate | <id> running in your hand-back and end your "
        "turn; the result reaches the coordinator.")
DENY_NOTE = "agentik-session: denied a helper's wait."
SAY_NOTE = "agentik-session: a helper is never the wait."
UNBOUND = "a wait with no bound of 100 s or less"
LOOP = "a sleep in a loop"
HEAVY = ("agentik-session: this run is listed as heavy for this repo: queue it with agentik "
         "session gate run")
START = (
    "agentik-session: you are a helper, and a helper never waits. Each shell call of yours ends "
    "inside two minutes. A run that may take longer is queued: agentik session gate run "
    "<absolute dir> --label <row> -- <command>, or --check for the repo's full check; add "
    "--within 100 to wait once. Write the job's id in your hand-back and end your turn: the "
    "result reaches your coordinator. Start no background shell and no sleep loop. If the "
    "engine moves a call of yours to the background, never wait on it and never kill by a "
    "command's text: stop it with TaskStop and the id it printed if you have that tool, else "
    "write that id in your hand-back. This overrides a brief that bars the verb.")


def text(clause):
    return f"agentik-session: an agent is never the wait ({clause}). {RULE}"


def denied(clause):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": text(clause)},
            "systemMessage": DENY_NOTE}


def said(clause):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "additionalContext": text(clause)},
            "systemMessage": SAY_NOTE}


def _env():
    return {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}


def _sdir(sid=SID):
    return resolver.session_dir(resolver.state_dir(os.environ), sid)


def _session(value, sid=SID, heavy=None):
    """The session's resolved.json: `helpers.wait` set to `value` (none named for None), and
    `helpers.heavy` where given."""
    s = {"profile": "frontier", "posture": "signal"}
    if value is not None:
        s["helpers"] = {"wait": value}
        if heavy is not None:
            s["helpers"]["heavy"] = heavy
    store._write_private(_sdir(sid) / "resolved.json", json.dumps({"session": s}))


_N = [0]


def call(command, agent=HELPER, background=None, sid=SID):
    _N[0] += 1
    ti = {"command": command}
    if background is not None:
        ti["run_in_background"] = background
    p = {"session_id": sid, "tool_name": "Bash", "tool_use_id": f"toolu_hw2_{_N[0]:04d}",
         "tool_input": ti, "cwd": str(_sdir(sid).parent)}
    if agent:
        p["agent_id"] = agent
    return p, hooks.pre_tool_use(p, _env())


def opened(p):
    return (_sdir(p["session_id"]) / hooks.CALLS / p["tool_use_id"]).exists()


def _tree(root):
    return sorted(str(x.relative_to(root)) for x in root.rglob("*")
                  if x.is_file() and x.parent.name != hooks.CALLS)


# ---- line 1, H1: each new spelling of a wait ------------------------------------------------

REFUSED = [
    ("make test", True, "a background shell"),
    ("echo hi", True, "a background shell"),
    ("agentik session gate run /tmp/w --label x --wait -- make check", None, "gate run --wait"),
    ("agentik-session gate run /tmp/w --wait --check", None, "gate run --wait"),
    ("cd /tmp && agentik session gate run /tmp/w --wai -- make test", None, "gate run --wait"),
    ("agentik session gate wait J1", None, UNBOUND),
    ("agentik session gate wait J1 --strict --timeout 540", None, UNBOUND),
    ("agentik session gate wait --time=101 J1", None, UNBOUND),
    ("agentik session gate wait J1 --timeout 100.5", None, UNBOUND),
    ("agentik session gate wait --chain", None, UNBOUND),
    ('agentik session gate wait "$JOB"', None, UNBOUND),
    ("x=$(agentik session gate wait J1 --timeout inf)", None, UNBOUND),
    ("sleep 30; sleep 30", None, "sleeps of 60 s"),
    ("sleep 20 && git status && sleep 45", None, "sleeps of 65 s"),
    ("sleep 30 & sleep 0.5m", None, "sleeps of 60 s"),
    ("for i in 1 2 3; do sleep 30; done", None, LOOP),
    ("while true; do sleep 5; done", None, LOOP),
    ("until test -f /tmp/done; do sleep 1; done", None, LOOP),
    ("while :; do agentik session gate status; sleep $N; done", None, LOOP),
    ("bash -c 'while :; do sleep 5; done'", None, LOOP),
]


@pytest.mark.parametrize("cmd, background, clause", REFUSED)
def test_1_each_spelling_passes_at_the_pin_and_is_denied(cmd, background, clause):
    _session(None)                       # the pin's reading: no key, so the pin's output
    p, pin = call(cmd, background=background)
    assert pin == {} and opened(p)
    _session("refuse")
    p, out = call(cmd, background=background)
    assert out == denied(clause) and not opened(p)


@pytest.mark.parametrize("cmd, background, clause", REFUSED)
def test_1_say_passes_and_says_it(cmd, background, clause):
    _session("say")
    p, out = call(cmd, background=background)
    assert out == said(clause) and opened(p)


NO_WAIT = [
    'git commit -m "while waiting, sleep 5"',
    'echo "while x; do"; sleep 5',
    "echo 'until done' && sleep 5",
    "cat <<'EOF'\nwhile :; do sleep 5; done\nEOF",
    "cat <<EOF\nwhile true\nEOF\nsleep 5",
    "# for later\nsleep 5",
    "sleep 5",
    "sleep 59",
    "sleep 30 # for the record",
    "agentik session gate run /tmp/w --label x --within 100 -- make check",
    "agentik session gate run /tmp/w --check --label x --within 100",
    "agentik session gate run /tmp/w --label x -- make test --wait",
    "agentik session gate wait J1 --timeout 100",
    "agentik session gate wait --timeout 0 J2",
    "agentik session gate wait --help",
    "agentik session gate wait",
    "agentik session gate status",
    "echo agentik session gate wait J3",
    "make test",
]


@pytest.mark.parametrize("cmd", NO_WAIT)
def test_1_a_line_that_is_no_wait_keeps_passing(cmd):
    _session(None)
    _, pin = call(cmd)
    _session("refuse")
    p, out = call(cmd)
    assert out == pin == {} and opened(p)


def test_1_the_second_wait_stays_first():
    _session("refuse")
    assert call("agentik session gate wait J7 --timeout 90")[1] == {}
    assert call("agentik session gate wait J7")[1] == denied("a second wait on J7")
    assert call("sleep 90", background=True)[1] == denied("a sleep of 90 s")


def test_1_an_unbounded_first_wait_is_not_recorded_where_refused():
    _session("refuse")
    assert call("agentik session gate wait J8")[1] == denied(UNBOUND)
    assert call("agentik session gate wait J8 --timeout 90")[1] == {}
    assert json.loads((_sdir() / "helper-waits.json").read_text()) == {
        "waits": [[HELPER, "J8"]]}


def test_1_the_main_thread_is_never_told():
    _session("refuse")
    for cmd, background, _ in REFUSED:
        assert call(cmd, agent=None, background=background)[1] == {}


def test_1_a_fault_passes_unsaid(monkeypatch):
    _session("refuse")

    def boom(*a, **k):
        raise RuntimeError("hw2")
    monkeypatch.setattr(shellreader, "commands", boom)
    assert call("make test", background=True)[1] == {}
    assert call("sleep 30; sleep 30")[1] == {}


ALL = [c for c, _, _ in REFUSED] + NO_WAIT


@pytest.mark.parametrize("background", [None, True])
def test_2_allow_is_the_pin_byte_for_byte(background):
    def run(value, sid):
        _session(value, sid, heavy=["make *"] if value else None)
        outs = [json.dumps(call(c, sid=sid, background=background)[1]) for c in ALL]
        return outs, _tree(_sdir(sid))
    pin, pin_tree = run(None, "hw2-pin")
    now, now_tree = run("allow", "hw2-now")
    assert now == pin and now_tree == pin_tree and "helper-waits.json" not in now_tree


# ---- line 1, H2: the rule's text ------------------------------------------------------------

def test_1_the_rule_is_h2s():
    assert hooks.HELPER_WAIT_RULE == RULE


# ---- line 1, H3: the rule said at a helper's start ------------------------------------------

def _start(sid=SID):
    return hooks.subagent_start({"session_id": sid, "agent_id": HELPER,
                                 "agent_type": "general-purpose",
                                 "hook_event_name": "SubagentStart"}, _env())


@pytest.mark.parametrize("value", ["say", "refuse"])
def test_1_subagent_start_says_the_paragraph(value):
    _session(value)
    assert _start() == {"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                               "additionalContext": START}}


@pytest.mark.parametrize("value", [None, "allow"])
def test_2_subagent_start_under_allow_prints_nothing(value, monkeypatch, capsys):
    _session(value)
    assert _start() == {}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"session_id": SID, "agent_id": HELPER, "hook_event_name": "SubagentStart"})))
    assert hooks.dispatch("SubagentStart") == 0
    assert capsys.readouterr() == ("", "")


def test_1_subagent_start_through_dispatch(monkeypatch, capsys):
    _session("refuse")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"session_id": SID, "agent_id": HELPER, "hook_event_name": "SubagentStart"})))
    assert hooks.dispatch("SubagentStart") == 0
    assert json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"] == START


def test_1_subagent_start_on_a_fault_prints_nothing(monkeypatch, capsys):
    _session("refuse")

    def boom(*a, **k):
        raise RuntimeError("hw2")
    monkeypatch.setattr(hooks, "_helper_wait_value", boom)
    assert _start() == {}
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hooks.dispatch("SubagentStart") == 0
    assert capsys.readouterr() == ("", "")


def test_1_subagent_start_is_registered_with_its_timeout():
    doc = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    hs = [h for g in doc["SubagentStart"] for h in g["hooks"]]
    assert [(h["type"], h["command"], h["timeout"]) for h in hs] == [
        ("command", "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" SubagentStart",
         harness.HOOK_WALL["SubagentStart"])]
    assert harness.HOOK_WALL["SubagentStart"] == 5
    assert "SubagentStart" in doctor.HOOK_EVENTS
    assert hooks.HANDLERS["SubagentStart"] is hooks.HANDLERS["subagent-start"]
    assert "SubagentStart" not in hooks.SILENT


def test_1_the_shim_keeps_its_stdout_and_drops_an_older_launchers_exit(tmp_path):
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    tool = root / "bin" / "agentik-session"
    tool.write_text("#!/bin/sh\ncat >/dev/null; echo '{}'; exit 2\n")
    tool.chmod(0o755)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_PLUGIN_ROOT": str(root)}
    r = subprocess.run([str(PLUGIN / "hooks" / "run"), "SubagentStart"], env=env,
                       input='{"session_id": "s"}', capture_output=True, text=True, timeout=60)
    assert (r.returncode, r.stdout) == (0, "{}\n")


# ---- line 1, H4: helpers.heavy ----------------------------------------------------------------

@pytest.fixture
def world(tmp_path):
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state)}

    def put(body):
        p = repo / ".claude/agentik/config.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return env, repo, put


def test_1_heavy_resolves_from_a_layer(world):
    env, repo, put = world
    put("session:\n  helpers:\n    wait: say\n    heavy: [make *, go test ./...]\n")
    assert resolve(repo, "hw2", env).sections["session"]["helpers"] == {
        "wait": "say", "heavy": ["make *", "go test ./..."]}


@pytest.mark.parametrize("body", ["session:\n  helpers:\n    wait: say\n    heavy: make\n",
                                  "session:\n  helpers:\n    wait: say\n    heavy: {a: b}\n"])
def test_1_a_bad_heavy_is_refused(world, body):
    env, repo, put = world
    put(body)
    with pytest.raises(ResolveError, match=r"helpers\.heavy must be a list of strings"):
        resolve(repo, "hw2", env)


def test_1_heavy_has_its_summary():
    s = plug.SUMMARIES["helpers.heavy"]
    assert len(s) < 100 and "helpers.heavy" not in plug.LIVE
    assert plug.TYPES["helpers.heavy"] == "list"
    assert "heavy" in resolver.HELPERS_KEYS


@pytest.mark.parametrize("value", ["say", "refuse"])
@pytest.mark.parametrize("cmd", ["make check", "cd /tmp && make -j4 test", "go test ./...",
                                 "bash -c 'make check'"])
def test_1_a_heavy_run_is_told_and_passes(value, cmd):
    _session(None)
    assert call(cmd)[1] == {}
    _session(value, heavy=["make *", "go test ./..."])
    p, out = call(cmd)
    assert out == {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "additionalContext": HEAVY}} and opened(p)


@pytest.mark.parametrize("cmd", ["echo make check", "make", "go test ./pkg", "git commit -m 'make x'"])
def test_1_no_heavy_run_is_told_nothing(cmd):
    _session("refuse", heavy=["make *", "go test ./..."])
    assert call(cmd)[1] == {}


def test_1_heavy_beside_a_wait():
    _session("say", heavy=["make *"])
    p, out = call("make check; sleep 90")
    assert out == {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "additionalContext": text("a sleep of 90 s") + "\n\n"
                                          + HEAVY},
                   "systemMessage": SAY_NOTE} and opened(p)
    _session("refuse", heavy=["make *"])
    assert call("make check; sleep 90")[1] == denied("a sleep of 90 s")


def test_1_heavy_not_a_list_or_the_main_thread_is_nothing():
    _session("refuse", heavy="make *")
    assert call("make check")[1] == {}
    _session("refuse", heavy=["make *"])
    assert call("make check", agent=None)[1] == {}
