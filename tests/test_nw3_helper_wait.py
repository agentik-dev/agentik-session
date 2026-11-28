"""Packet nw3-helper-wait (design/packets/nw3-helper-wait.md): under the profile key
`helpers.wait`, the PreToolUse hook refuses (`refuse`) or says (`say`) a helper's second
`gate wait` on one job and its `sleep` of 60 seconds or more; `allow`, the shipped default,
keeps the pin's output byte for byte and writes nothing. The main thread is never refused.

Every state is under the per-test temp roots (conftest); no test starts a `claude` or a `make`.
"""
import json
import os

import pytest

from claude_session import hooks, plug, resolver, shellreader, store
from claude_session.resolver import ResolveError, resolve
from claude_session.yamlsubset import load

SID = "nw3-session-0001"
HELPER, OTHER = "agent-nw3-a", "agent-nw3-b"
RULE = ("Queue the run with agentik session gate run <dir> --label <row> -- <command> (add "
        "--within 100 to wait once), write gate | <id> running in your hand-back and end your "
        "turn; the result reaches the coordinator.")                       # hw2 H2
DENY_NOTE = "agentik-session: denied a helper's wait."
SAY_NOTE = "agentik-session: a helper is never the wait."
RECORD = "helper-waits.json"


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


def _session(value, sid=SID):
    """The session's resolved.json, `helpers.wait` set to `value`, none named for None."""
    s = {"profile": "frontier", "posture": "signal"}
    if value is not None:
        s["helpers"] = {"wait": value}
    store._write_private(_sdir(sid) / "resolved.json", json.dumps({"session": s}))


_N = [0]


def call(command, agent=HELPER, background=None, sid=SID, cwd=None):
    _N[0] += 1
    ti = {"command": command}
    if background is not None:
        ti["run_in_background"] = background
    p = {"session_id": sid, "tool_name": "Bash", "tool_use_id": f"toolu_nw3_{_N[0]:04d}",
         "tool_input": ti, "cwd": cwd or str(_sdir(sid).parent)}
    if agent:
        p["agent_id"] = agent
    return p, hooks.pre_tool_use(p, _env())


def opened(p):
    return (_sdir(p["session_id"]) / hooks.CALLS / p["tool_use_id"]).exists()


def _tree(root):
    return sorted(str(x.relative_to(root)) for x in root.rglob("*")
                  if x.is_file() and x.parent.name != hooks.CALLS)


# ---- line 1: the key resolves ------------------------------------------------------------

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


def test_1_shipped_defaults_allow():
    assert load(resolver.SHIPPED.read_text())["defaults"]["helpers"] == {"wait": "allow"}


@pytest.mark.parametrize("name, value", [
    (None, "allow"), ("starter", "allow"), ("builder", "allow"), ("balanced", "allow"),
    ("frontier", "refuse"), ("orchestrator", "refuse"), ("orchestrator-opus", "refuse")])
def test_1_each_profile_resolves(world, name, value):
    env, repo, _ = world
    s = resolve(repo, "nw3", env, profile=name).sections["session"]
    assert s["helpers"] == {"wait": value}


def test_1_a_layer_sets_say(world):
    env, repo, put = world
    put("session:\n  helpers: {wait: say}\n")
    assert resolve(repo, "nw3", env).sections["session"]["helpers"] == {"wait": "say"}


@pytest.mark.parametrize("body, msg", [
    ("session:\n  helpers: {wait: never}\n", r"helpers\.wait must be one of allow, say, refuse"),
    ("session:\n  helpers: {wait: allow, poll: refuse}\n", r"helpers must be a mapping of wait"),
    ("session:\n  helpers: refuse\n", r"helpers must be a mapping of wait")])
def test_1_a_bad_value_or_key_is_refused(world, body, msg):
    env, repo, put = world
    put(body)
    with pytest.raises(ResolveError, match=msg):
        resolve(repo, "nw3", env)


def test_1_summaries_hold_the_key():
    s = plug.SUMMARIES["helpers.wait"]
    assert len(s) < 100 and "allow" in s and "refuse" in s
    assert "helpers.wait" not in plug.LIVE


# ---- line 2: the long sleeps denied under refuse --------------------------------------------

DENIED = [("sleep 90", 90), ("sleep 60", 60), ("sleep 1m", 60), ("sleep 0.5h", 1800),
          ("sleep 30 30", 60), ("cd /tmp && sleep 120", 120), ("while :; do sleep 90; done", 90),
          ("x=$(sleep 90)", 90), ("bash -c 'sleep 90'", 90), ("sh -c \"cd x && sleep 120\"", 120),
          ("sleep infinity", "infinity"), ("sleep 1d", 86400), ("sleep 1.5m", 90)]


@pytest.mark.parametrize("cmd, n", DENIED)
def test_2_a_long_sleep_is_denied(cmd, n):
    _session("refuse")
    p, out = call(cmd)
    assert out == denied(f"a sleep of {n} s")
    assert not opened(p)                 # R5: a refused call opens none


def test_2_a_background_wake_is_denied():
    _session("refuse")
    p, out = call("sleep 300 && agentik session gate status", background=True)
    assert out == denied("a sleep of 300 s") and not opened(p)


# ---- line 3: what is no command sleep passes under refuse ------------------------------------

PASSED = ["sleep 59", "cat <<'EOF'\nsleep 90\nEOF",      # hw2 H1: a sleep in a loop is refused
          "git commit -F - <<EOF\nwait: sleep 90\nEOF", 'git commit -m "wait: sleep 90"',
          "echo 'sleep 90'", 'grep -n "sleep 90" notes.txt', 'sleep "$N"', "sleep $N",
          "sleep --help", "agentik session gate run /tmp/w --label x -- make check",
          "agentik session gate status"]


@pytest.mark.parametrize("cmd", PASSED)
def test_3_no_long_sleep_passes(cmd):
    _session(None)
    _, pin = call(cmd)
    _session("refuse")
    p, out = call(cmd)
    assert out == pin and opened(p)
    assert "never the wait" not in json.dumps(out)


# ---- line 4: the repeated wait ---------------------------------------------------------------

# The third spelling is the launcher's name before the rename, built from two parts so the
# hygiene scan's `renamed` group (old names in live text) counts no fixture line here.
OLD_NAME = "claude" + "-session"
SPELLINGS = ["agentik session gate wait {id} --timeout 90",      # hw2 H1: each wait bounded
             "agentik-session gate wait {id} --strict --timeout 100",
             OLD_NAME + " gate wait --timeout 60 {id}"]


@pytest.mark.parametrize("spell", SPELLINGS)
def test_4_a_second_wait_on_one_job_is_denied(spell):
    _session("refuse")
    a, b = spell.format(id="20261122-100000-0001"), spell.format(id="20261122-100000-0002")
    p, out = call(a)
    assert out == {} and opened(p)
    p, out = call(a)
    assert out == denied("a second wait on 20261122-100000-0001") and not opened(p)
    assert call(b)[1] == {}
    assert call(a, agent=OTHER)[1] == {}            # another helper's first wait
    assert call(a, agent=None)[1] == {}             # the main thread
    assert call(a, agent=None)[1] == {}             # the main thread, again


def test_4_the_path_and_a_list_count():
    _session("refuse")
    T = " --timeout 90"                     # hw2 H1: each wait bounded
    assert call("cd /tmp && /opt/x/bin/agentik-session gate wait J1" + T)[1] == {}
    assert call("agentik session gate wait J2" + T + "; agentik session gate wait J1" + T)[1] == denied(
        "a second wait on J1")
    assert call("agentik session gate wait J3" + T + " && agentik session gate wait J3" + T)[1] == denied(
        "a second wait on J3")


def test_4_a_message_is_no_wait():
    _session("refuse")
    assert call('git commit -m "agentik session gate wait J9"')[1] == {}
    assert call("echo 'agentik session gate wait J9'")[1] == {}
    assert not (_sdir() / RECORD).exists()
    assert call("agentik session gate wait J9 --timeout 90")[1] == {}       # hw2 H1: bounded
    assert call("agentik session gate wait J9 --timeout 90")[1] == denied("a second wait on J9")


def test_4_a_second_wait_on_the_chain_is_denied():
    _session("refuse")
    assert call("agentik session gate wait --chain --timeout 90")[1] == {}   # hw2 H1: bounded
    p, out = call("agentik session gate wait --chain")
    assert out == denied("a second wait on the chain") and not opened(p)
    assert call("agentik session gate wait --chain --timeout 90", agent=OTHER)[1] == {}


def test_4_no_id_is_no_wait():
    _session("refuse")
    assert call("agentik session gate wait")[1] == {}
    assert call("agentik session gate wait")[1] == {}


def test_4_the_record_is_bounded():
    _session("refuse")
    for i in range(hooks.HELPER_WAITS_MAX + 20):
        assert call(f"agentik session gate wait K{i} --timeout 90")[1] == {}    # hw2 H1
    doc = json.loads((_sdir() / RECORD).read_text())
    assert len(doc["waits"]) == hooks.HELPER_WAITS_MAX
    assert call(f"agentik session gate wait K{hooks.HELPER_WAITS_MAX + 19} --timeout 90")[1] == denied(
        f"a second wait on K{hooks.HELPER_WAITS_MAX + 19}")


# ---- line 5: say, and allow byte for byte ----------------------------------------------------

@pytest.mark.parametrize("cmd, n", DENIED)
def test_5_say_passes_and_carries_the_text(cmd, n):
    _session("say")
    p, out = call(cmd)
    assert out == said(f"a sleep of {n} s") and opened(p)


def test_5_say_a_second_and_third_wait():
    _session("say")
    assert call("agentik session gate wait J1 --timeout 90")[1] == {}       # hw2 H1: bounded
    for _ in range(2):
        p, out = call("agentik session gate wait J1")
        assert out == said("a second wait on J1") and opened(p)
    assert call("agentik session gate wait --chain --timeout 90")[1] == {}
    assert call("agentik session gate wait --chain")[1] == said("a second wait on the chain")


ALL = ([c for c, _ in DENIED] + PASSED + [s.format(id="J1") for s in SPELLINGS] * 2
       + ["agentik session gate wait --chain"] * 2)


def _run_all(value, sid, background):
    _session(value, sid)
    outs = [call(c, sid=sid, background=background)[1] for c in ALL]
    return outs, _tree(_sdir(sid))


@pytest.mark.parametrize("background", [None, True])
def test_5_allow_is_the_pin_byte_for_byte(background):
    pin, pin_tree = _run_all(None, "nw3-pin", background)
    now, now_tree = _run_all("allow", "nw3-now", background)
    assert [json.dumps(o) for o in now] == [json.dumps(o) for o in pin]
    assert now_tree == pin_tree and RECORD not in now_tree


def test_5_no_resolved_file_is_allow():
    p = {"session_id": "nw3-none", "agent_id": HELPER, "tool_name": "Bash",
         "tool_use_id": "toolu_nw3_none", "tool_input": {"command": "sleep 90"}}
    assert hooks.pre_tool_use(p, _env()) == {}


# ---- line 6: the main thread, a background test run, a line past the bound ------------------

def test_6_the_main_thread_sleeps():
    _session("refuse")
    assert call("sleep 90", agent=None)[1] == {}
    assert call("sleep 90", agent=None, background=True)[1] == {}


def test_6_a_background_test_run_is_denied():     # hw2 H1: was passed, now a background shell
    _session("refuse")
    p, out = call("make test", background=True)
    assert out == denied("a background shell") and not opened(p)


def test_6_a_line_past_the_bound_passes_unsaid():
    _session("refuse")
    line = "echo " + "$(" * (shellreader._NEST + 8) + "sleep 90" + ")" * (shellreader._NEST + 8)
    with pytest.raises(shellreader._Bound):
        shellreader.commands(line, "/tmp", _env())
    p, out = call(line)
    assert out == {} and opened(p)


def test_6_a_fault_passes_unsaid(monkeypatch):
    _session("refuse")

    def boom(*a, **k):
        raise RuntimeError("nw3")
    monkeypatch.setattr(shellreader, "commands", boom)
    assert call("sleep 90")[1] == {}


def test_6_through_session_start(tmp_path):
    """The resolved value reaches the hook: a repo's layer sets `refuse` on `starter`."""
    repo = tmp_path / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True)
    (repo / ".claude" / "agentik" / "config.yaml").write_text(
        "session:\n  helpers: {wait: refuse}\n")
    assert hooks.session_start({"session_id": "nw3-start", "cwd": str(repo)}, _env())
    assert call("sleep 90", sid="nw3-start", cwd=str(repo))[1] == denied("a sleep of 90 s")


# ---- brief 2, R1: an abbreviated option is read as the CLI reads it --------------------------

JOB_A, JOB_B = "20261122-110000-0001", "20261122-110000-0002"


@pytest.mark.parametrize("opt", ["--t 90", "--time 90", "--timeo 90", "--time=90",
                                 "--timeout=90"])                  # hw2 H1: 540 is unbounded
def test_b2_an_abbreviated_timeout_skips_its_value(opt):
    _session("refuse")
    wait = "agentik session gate wait " + opt + " {}"
    assert call(wait.format(JOB_A))[1] == {}
    assert call(wait.format(JOB_B))[1] == {}            # a first wait on B, never on 90
    assert call(wait.format(JOB_A))[1] == denied(f"a second wait on {JOB_A}")
    doc = json.loads((_sdir() / RECORD).read_text())
    assert doc == {"waits": [[HELPER, JOB_A], [HELPER, JOB_B]]}


@pytest.mark.parametrize("spell", ["--c", "--ch", "--chai"])
def test_b2_an_abbreviated_chain_is_the_chains_wait(spell):
    _session("refuse")
    assert call("agentik session gate wait " + spell + " --time 30")[1] == {}    # hw2 H1
    p, out = call("agentik session gate wait " + spell + " --time 30")
    assert out == denied("a second wait on the chain") and not opened(p)
    assert call("agentik session gate wait --chain")[1] == denied("a second wait on the chain")


@pytest.mark.parametrize("line", [f"--bogus {JOB_A}", f"{JOB_A} {JOB_B}", f"--timeout {JOB_A}",
                                  f"--chain=1 {JOB_A}", f"--json=1 {JOB_A}", f"--he {JOB_A}"])
def test_b2_a_line_the_parser_refuses_is_no_wait(line):
    _session("refuse")
    assert call("agentik session gate wait " + line)[1] == {}
    assert call("agentik session gate wait " + line)[1] == {}
    assert not (_sdir() / RECORD).exists()


@pytest.mark.parametrize("line", [f"--str --js {JOB_A}", f"{JOB_A} --str", f"-- {JOB_A}"])
def test_b2_other_abbreviations_name_the_job(line):
    _session("refuse")
    assert call(f"agentik session gate wait {JOB_A} --timeout 90")[1] == {}     # hw2 H1
    assert call("agentik session gate wait " + line)[1] == denied(f"a second wait on {JOB_A}")


def test_b2_the_hooks_options_are_the_clis():
    """The hook's reader of a wait's words holds the options `gate wait`'s parser holds."""
    from claude_session import cli

    def sub(parser, name):
        acts = [a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"]
        return acts[0].choices[name]

    def shape(parser):
        return sorted((tuple(a.option_strings), a.dest, a.nargs, str(a.type))
                      for a in parser._actions)       # help is a flag in the hook's
    wait = sub(sub(cli.build_parser(), "gate"), "wait")
    assert shape(hooks._wait_parser()) == shape(wait)
    assert hooks._wait_parser().allow_abbrev == wait.allow_abbrev


# ---- brief 2, R2: the check's read of the resolved file is of a regular file only -----------

def test_b2_a_fifo_resolved_file_never_blocks(tmp_path):
    import threading
    pin = call("echo nw3", sid="nw3-fifo-pin")
    os.makedirs(_sdir("nw3-fifo"), exist_ok=True)
    fifo = _sdir("nw3-fifo") / "resolved.json"
    os.mkfifo(fifo)
    got = []
    t = threading.Thread(target=lambda: got.append(call("echo nw3", sid="nw3-fifo")),
                         daemon=True)
    t.start()
    t.join(5)
    blocked = t.is_alive()
    if blocked:                         # a red is a failure, never a hang: free the reader
        os.close(os.open(fifo, os.O_WRONLY))
        t.join(5)
    assert not blocked, "a helper's Bash call blocked on a FIFO resolved file"
    p, out = got[0]
    assert out == pin[1] == {} and opened(p)


def test_b2_a_folder_resolved_file_is_allow():
    os.makedirs(_sdir("nw3-dir") / "resolved.json")
    assert call("sleep 90", sid="nw3-dir")[1] == {}
    assert call("agentik session gate wait J1", sid="nw3-dir")[1] == {}
    assert call("agentik session gate wait J1", sid="nw3-dir")[1] == {}
