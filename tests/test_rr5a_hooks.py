"""Packet rr5a: the hooks through the records resolver (R4 to R6). Every name is made up."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import charter, cli, config, hooks, records, resolver

from test_rr5a_charter_folder import layout

pytestmark = pytest.mark.usefixtures("frontier_home")

SID = "rr5a-sess-1"
STATES = ["own", "out", "unset", "missing"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    records.reset()
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv(hooks.CHAIN_VAR, raising=False)
    config.ensure_dirs()
    yield dict(os.environ)
    records.reset()


def sdir(env):
    s = resolver.session_dir(resolver.state_dir(env), SID)
    s.mkdir(parents=True, exist_ok=True)
    return s


def transcript(tmp_path, context):
    row = {"type": "assistant", "requestId": "r0", "timestamp": "2026-09-22T10:00:00Z",
           "message": {"id": "m0", "model": "claude-opus-5-5",
                       "content": [{"type": "text", "text": "<placeholder>"}],
                       "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                 "cache_read_input_tokens": context, "output_tokens": 7}}}
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(row) + "\n")
    return p


def resolved(env, d="h"):
    (sdir(env) / "resolved.json").write_text(json.dumps(
        {"session": {"posture": "signal", "charter": {"dir": d}}}))


def line(env, tmp_path, c, chained=False):
    e = {**env, hooks.CHAIN_VAR: "net"} if chained else env
    out = hooks.post_tool_use({"session_id": SID, "transcript_path": str(transcript(tmp_path, 144000)),
                               "tool_name": "Read", "cwd": str(c)}, e)
    return out["hookSpecificOutput"]["additionalContext"]


def opened(env, folder):
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{charter.today()}-1.md"
    f.write_text("# sitting\n")
    (sdir(env) / hooks.CHARTER_REC).write_text(json.dumps({"path": str(f)}))
    return f


def required(d="h"):
    return {"charter": {"required": True, "dir": d}}


@pytest.mark.parametrize("state", STATES)
def test_session_start_reminder_in_each_state(env, tmp_path, state):
    c, rec = layout(tmp_path, state)
    got = hooks._charter_reminder(required(), str(c))
    if state == "own":
        assert got == '; charter: none open today under h, run agentik-session charter open "<goal>"'
    elif state == "out":
        assert got == (f"; charter: none open today under {rec / 'h'}, run "
                       'agentik-session charter open "<goal>"')
        opened(env, rec / "h")
        assert hooks._charter_reminder(required(), str(c)) == ""
    elif state == "unset":
        assert got == ""
    else:
        assert got == "; records: " + records.line(records.answer(str(c)))
        assert got.count("agentik.records") == 2 and "reason missing" in got


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("chained", [False, True])
@pytest.mark.parametrize("with_charter", [False, True])
def test_checkpoint_line_in_each_state(env, tmp_path, monkeypatch, state, chained, with_charter):
    c, rec = layout(tmp_path, state)
    resolved(env)
    f = opened(env, (rec if state == "out" else c) / "h") if with_charter else None
    if state == "out" and chained and f:     # a temp root is long: room for the absolute path
        monkeypatch.setattr(hooks, "MAX_OUT", 4000)
    got = line(env, tmp_path, c, chained)
    assert got.startswith("CHECKPOINT: ")
    if state in ("unset", "broken", "missing"):
        assert hooks.PLAIN_TAIL in got and "charter" not in got
    elif state == "own":
        if not chained:
            assert "; charter h; bring the charter current" in got
        else:
            assert (f"--charter {f}`" in got or f"--charter h/{f.name}`" in got) if f else (
                f"--charter {hooks.NO_CHARTER}`" in got)
    else:
        if not chained:
            assert f"; charter {rec / 'h'}; bring the charter current" in got
        else:
            # the absolute path where it fits MAX_OUT (a temp root is long), else NO_CHARTER;
            # never a relative spelling
            assert f"--charter {f if f else hooks.NO_CHARTER}`" in got
            assert f"--charter h/" not in got


def test_out_charter_file_never_relative(env, tmp_path):
    c, rec = layout(tmp_path, "out")
    f = opened(env, rec / "h")
    assert hooks._charter_file_out(sdir(env), str(rec / "h")) == [str(f), hooks.NO_CHARTER]
    assert hooks._charter_file_out(sdir(env), str(rec / "other")) == [hooks.NO_CHARTER]
    sub = rec / "h" / "deeper"
    g = opened(env, sub)
    assert hooks._charter_file_out(sdir(env), str(rec / "h")) == [hooks.NO_CHARTER]
    assert g.is_file()


@pytest.mark.parametrize("state", STATES)
def test_the_record_of_the_open(env, tmp_path, monkeypatch, state):
    c, rec = layout(tmp_path, state)
    s = sdir(env)
    resolver.save_request(s, str(c), None, None, None, None)
    section = {"charter": {"dir": "history/sittings"}}
    here = c / "history" / "sittings"
    there = rec / "history" / "sittings" if rec else None
    got_here = cli._records_here(str(here), section)
    got_there = cli._records_here(str(there), section) if there else None
    if state == "own":
        assert got_here == s
    elif state == "out":
        assert got_here is None and got_there == s
        f = there / "2026-11-20-1.md"
        there.mkdir(parents=True)
        f.write_text("# s\n")
        cli._record_charter(f, section)
        assert json.loads((s / hooks.CHARTER_REC).read_text()) == {"path": str(f)}
    else:                     # only an explicit --dir opens here: the pin's record
        assert got_here == s


@pytest.mark.parametrize("chained", [False, True])
@pytest.mark.parametrize("body", ["raise RuntimeError('made-up')", "import time; time.sleep(30)"])
def test_no_hook_raises_or_refuses_with_a_resolver_that_raises_or_sleeps(env, tmp_path,
                                                                           monkeypatch, body,
                                                                           chained):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "agentik_records.py").write_text(
        f"class NoRepo(Exception):\n    pass\n\ndef resolve(start):\n    {body}\n")
    monkeypatch.setattr(records, "_LIB", str(lib))
    monkeypatch.setattr(records, "BOUND", 0.5)
    c, _ = layout(tmp_path, "own")
    resolved(env)
    got = line(env, tmp_path, c, chained)
    # review 1's F1: a read with no answer costs the path alone, the pin's line where it knows none
    assert f"charter {hooks.NO_CHARTER}; " in got and hooks.PLAIN_TAIL not in got
    records.reset()
    assert hooks._charter_reminder(required(), str(c)).startswith("; records: agentik.records")


# --- R6: the hot path --------------------------------------------------------------------

# Review 1's F2: the resolver's asks are counted by a recorder that raises nothing (so no
# `except Exception` can swallow it) around the real read, and every process started is
# counted, over each hot-hook path; both hold at the pin's count, 0. An ask at the top of
# `pre_tool_use` (the review's mutant) reds it.
PIN_STARTS = 0


def hot_paths(c, tmp_path):
    base = {"session_id": SID, "cwd": str(c)}
    tr = lambda: str(transcript(tmp_path, 1000))                    # noqa: E731
    return [
        ("pre", lambda e: hooks.pre_tool_use(
            {**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, e)),
        ("pre-write", lambda e: hooks.pre_tool_use(
            {**base, "tool_name": "Write",
             "tool_input": {"file_path": str(c / "x.md"), "content": "x"}}, e)),
        ("post-silent", lambda e: hooks.post_tool_use(
            {**base, "tool_name": "Read", "transcript_path": tr()}, e)),
        ("post-no-transcript", lambda e: hooks.post_tool_use(
            {**base, "tool_name": "Read", "transcript_path": str(tmp_path / "none.jsonl")}, e)),
        ("post-no-cwd", lambda e: hooks.post_tool_use(
            {"session_id": SID, "tool_name": "Read", "transcript_path": tr()}, e)),
        ("post-gone-cwd", lambda e: hooks.post_tool_use(
            {"session_id": SID, "cwd": str(tmp_path / "gone"), "tool_name": "Read",
             "transcript_path": tr()}, e)),
        ("stop", lambda e: hooks.stop(base, e)),
        ("stop-no-cwd", lambda e: hooks.stop({"session_id": SID}, e)),
        ("ups", lambda e: hooks.user_prompt_submit({**base, "prompt": "hello"})),
    ]


@pytest.mark.parametrize("state", STATES)
def test_hot_hooks_start_no_resolver(env, tmp_path, monkeypatch, state):
    c, _ = layout(tmp_path, state)
    resolved(env)
    paths = hot_paths(c, tmp_path)
    starts, asks = [], []
    real_popen, real_read = subprocess.Popen, records._read

    def counted(*a, **k):
        starts.append(a[0] if a else k.get("args"))
        return real_popen(*a, **k)

    def recorded(folder):
        asks.append(folder)
        return real_read(folder)
    monkeypatch.setattr(subprocess, "Popen", counted)
    monkeypatch.setattr(records, "_read", recorded)
    got = {}
    for name, f in paths:
        starts.clear()
        asks.clear()
        records.reset()
        f(env)
        got[name] = (len(starts), len(asks))
    assert got == {name: (PIN_STARTS, 0) for name, _ in paths}


# --- review 1's F1: the resolver's bound inside a hook ----------------------------------
# The real `cli.main(['hook', 'PostToolUse'])` in a child, as the shim starts it (HOOK_T0 set,
# so the hook's own cut is armed), in an `own` clone at 80% context, with a `git` on PATH that
# notes its pid and sleeps. At 1b92b2d the resolver's 5 s bound outlived PostToolUse's 4.5 s
# deadline: the cut printed nothing, spent the band, and left the resolver's group alive.

HOOK = ("import json, sys\n"
        "from claude_session import cli, harness, records\n"
        "o = json.loads(sys.argv[2])\n"
        "harness.HOOK_DEADLINE.update(o.get('deadline', {}))\n"
        "if 'margin' in o:\n"
        "    records.HOOK_MARGIN = o['margin']\n"
        "sys.exit(cli.main(['hook', sys.argv[1]]))\n")


def sleepy_git(tmp_path):
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    pids = tmp_path / "git-pids"
    (b / "git").write_text(f'#!/bin/sh\necho $$ >> "{pids}"\nexec /bin/sleep 37\n')
    (b / "git").chmod(0o755)
    return b, pids


def alive(pids) -> list:
    if not pids.exists():
        return []
    left = []
    for p in {int(x) for x in pids.read_text().split()}:
        try:
            os.kill(p, 0)
            left.append(p)
        except ProcessLookupError:
            pass
        except PermissionError:
            left.append(p)
    return left


def gone(pids, within=3.0) -> bool:
    end = time.monotonic() + within
    while alive(pids) and time.monotonic() < end:
        time.sleep(0.05)
    for p in alive(pids):
        os.kill(p, 9)
        return False
    return True


def hook_child(env, tmp_path, c, slow, opts=None, popen=False):
    e = dict(env)
    if slow:
        b, _ = sleepy_git(tmp_path)
        e["PATH"] = f"{b}{os.pathsep}{e['PATH']}"
    e["AGENTIK_SESSION_HOOK_T0"] = str(time.time_ns())
    pl = {"session_id": SID, "transcript_path": str(transcript(tmp_path, 144000)),
          "tool_name": "Read", "cwd": str(c), "hook_event_name": "PostToolUse"}
    argv = [sys.executable, "-c", HOOK, "PostToolUse", json.dumps(opts or {})]
    if popen:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=e)
        p.stdin.write(json.dumps(pl))
        p.stdin.close()
        return p
    t = time.monotonic()
    p = subprocess.run(argv, input=json.dumps(pl), capture_output=True, text=True, env=e,
                       timeout=60)
    return p, time.monotonic() - t


def test_a_slow_git_costs_the_path_alone_inside_the_deadline(env, tmp_path):
    c, _ = layout(tmp_path, "own")
    resolved(env)
    p, dt = hook_child(env, tmp_path, c, slow=True)
    pids = tmp_path / "git-pids"
    assert pids.exists(), p.stderr                     # the resolver did ask git
    assert gone(pids), "a child of the resolver outlived the hook"
    assert p.returncode == 0 and dt < 4.5, (dt, p.stderr)
    got = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert got.startswith("CHECKPOINT: 80.0% context")
    assert f"charter {hooks.NO_CHARTER}; bring the charter current, commit, then exit" in got


def test_the_resolvers_bound_in_a_post_tool_use_is_two_seconds_at_most(monkeypatch):
    monkeypatch.setattr(records, "_END", [])
    assert records.bound() == records.BOUND
    records.within(time.monotonic() + 4.5)             # PostToolUse's own deadline
    try:
        assert records.bound() <= 2.0
        records.within(time.monotonic() + 1.0)         # a hook near its end asks for nothing
        starts = []
        monkeypatch.setattr(records.subprocess, "Popen", lambda *a, **k: starts.append(a))
        assert records._read("/") == records._failed("/", "timeout") and starts == []
    finally:
        records.within(None)


def test_the_cut_kills_the_resolvers_group_and_spends_no_band(env, tmp_path):
    c, _ = layout(tmp_path, "own")
    resolved(env)
    # the deadline brought inside the bound, so the cut (exit 124) falls while git sleeps
    p, dt = hook_child(env, tmp_path, c, slow=True,
                       opts={"deadline": {"PostToolUse": 1.0}, "margin": -10})
    pids = tmp_path / "git-pids"
    assert pids.exists() and p.returncode == 0 and p.stdout == "", (p.stdout, p.stderr)
    assert gone(pids, within=1.0), "the cut left the resolver's group alive"
    pids.unlink()
    p, _ = hook_child(env, tmp_path, c, slow=False)    # the next call, git well: the line
    got = json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    assert got.startswith("CHECKPOINT: 80.0% context"), got


def test_a_term_kills_the_resolvers_group(env, tmp_path):
    c, _ = layout(tmp_path, "own")
    resolved(env)
    p = hook_child(env, tmp_path, c, slow=True, opts={"margin": -10}, popen=True)
    pids = tmp_path / "git-pids"
    end = time.monotonic() + 10
    while not (pids.exists() and pids.read_text().strip()) and time.monotonic() < end:
        time.sleep(0.02)
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=10) == 143
    p.stdout.close()
    p.stderr.close()
    assert gone(pids, within=1.0), "a TERM left the resolver's group alive"
