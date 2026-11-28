"""Packet nw2-chain-inbox: a gate job's result follows the chain (design/31 items 8 to 13, and
item 1's `est`). Every root is a temp one; no test starts a `claude`, a runner or a `make`."""
import hashlib
import io
import json
import os
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from claude_session import chain, cli, commit, deliver, gate, hooks, resolver

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
NAME = "c1"
SHA = "8e37e4e" + "0" * 33
T0 = time.time()


class Fx:
    """The runner's effects: a clock that moves when it sleeps, every job exiting `rc`."""
    def __init__(self, rc=1):
        self.t, self.rc, self.logs = T0, rc, []

    def make(self):
        class P:
            pid = 4321

            def poll(s):
                return self.rc

            def wait(s, timeout=None):
                return self.rc

        def popen(argv, **kw):
            kw["stdout"].write(b"out\n")
            return P()
        return gate.Fx(now=lambda: self.t, sleep=self.sleep, popen=popen,
                       killpg=lambda *a: None, post=lambda *a: None, log=self.logs.append,
                       env={"HOME": os.environ["HOME"]}, idle=0.0, poll=1.0, grace=1.0, pid=777)

    def sleep(self, s):
        self.t += s


@pytest.fixture
def root():
    return resolver.state_dir(os.environ)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return r


def cenv(sid=A, **more):
    return {"CLAUDE_SESSION_CHAIN": NAME, "CLAUDE_CODE_SESSION_ID": sid, **more}


def put(root, repo, env, caller, named=False, label="row", command=("make", "check")):
    return gate.enqueue(root, str(repo), list(command), env, [], 600, label, caller, T0,
                        named=named)


def close(root, sid, ago=40.0):
    """A sitting's confirmed respawn mark, its turn ended after it, `ago` seconds back."""
    d = resolver.session_dir(root, sid)
    d.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"session": sid, "chain": NAME, "written": time.time() - ago,
                      "charter": "/nowhere/page.md"}).encode()
    (d / hooks.MARKER).write_bytes(raw)
    (d / hooks.CONFIRMED).write_text(json.dumps(
        {"at": time.time() - ago + 1, "marker_sha256": hashlib.sha256(raw).hexdigest()}))
    (d / hooks.ACTIVITY).write_text(json.dumps({"event": "PostToolUse", "at": time.time() - ago + 1}))
    (d / hooks.TURN_ENDED).write_text(json.dumps({"at": time.time() - ago + 2}))
    return d


def prompt(sid, text="go on"):
    out = hooks.user_prompt_submit({"session_id": sid, "hook_event_name": "UserPromptSubmit",
                                    "prompt": text})
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
    return [ln for ln in ctx.splitlines() if ln.startswith(("gate ", "gate:", gate.CLOSED_WORDS))]


def box(root):
    d = gate.chain_inbox(root, NAME)
    return sorted(p.name for p in d.iterdir() if p.suffix == ".json") if d.is_dir() else []


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def chained(monkeypatch, sid):
    for k, v in cenv(sid).items():
        monkeypatch.setenv(k, v)


# ---- 1. each address, by each verb that queues -----------------------------------------

def test_the_address_of_each_caller(root, repo):
    assert gate.ENTRY_KEYS[-1] == "chain" and gate.CHAIN_VAR == resolver.CHAIN_VAR
    assert (gate.MARKER, gate.CONFIRMED) == (hooks.MARKER, hooks.CONFIRMED)
    assert put(root, repo, cenv(), A)["chain"] == NAME               # no sitting.json: the env
    assert put(root, repo, {}, A)["chain"] is None                   # no chain
    assert put(root, repo, cenv(), A, named=True)["chain"] is None   # --session
    assert put(root, repo, cenv(CLAUDE_SESSION_DEPTH="1"), A)["chain"] is None   # a child
    assert put(root, repo, cenv(RELAY_ROW="r1"), A)["chain"] is None
    gate.write_sitting(root, NAME, A, T0)
    assert put(root, repo, cenv(), A)["chain"] == NAME               # the sitting it names
    assert put(root, repo, cenv(CLAUDE_SESSION_HELPER="1"), A)["chain"] == NAME   # its helper
    assert put(root, repo, cenv(C), C)["chain"] is None              # a new id after a clear
    assert put(root, repo, cenv(C), None)["chain"] is None           # an inherited name


def test_the_line_lands_in_the_chains_inbox_or_the_callers(root, repo):
    gate.write_sitting(root, NAME, A, T0)
    a = put(root, repo, cenv(), A)
    c = put(root, repo, cenv(C), C)
    gate.serve(root, Fx().make())
    assert box(root) == [f"{a['id']}.json"]
    assert not (root / "sessions" / A / "inbox").exists()
    assert (root / "sessions" / C / "inbox" / f"{c['id']}.json").exists()
    ra = json.loads(gate.result_path(root, a["id"]).read_text())
    rc_ = json.loads(gate.result_path(root, c["id"]).read_text())
    assert list(ra) == [*gate.RESULT_KEYS, *gate.CHAIN_KEYS, *gate.MEASURE_KEYS]   # hw1 W2
    assert ra["chain"] == NAME
    assert list(rc_) == [*gate.RESULT_KEYS, *gate.MEASURE_KEYS]       # R8: the pin's keys


def test_each_verb_that_queues_passes_the_session_flag(root, repo, monkeypatch):
    got, real = [], gate.enqueue

    def spy(*a, **kw):
        got.append(real(*a, **kw)["chain"])
        raise gate.GateError("stopped by the test")
    chained(monkeypatch, A)
    monkeypatch.setattr(gate, "enqueue", spy)
    monkeypatch.setattr(gate, "spawn_serve", lambda r, popen=None: True)
    env = dict(os.environ)
    for named in (False, True):
        commit._gate_check(str(repo), ["make", "check"], env, A, 60, named)
    with pytest.raises(deliver.Red):
        deliver._make_install(str(repo), root, env, "x")
    merge = repo / "merge.txt"
    merge.write_text("m\n")
    for extra in ((), ("--session", A)):
        run("gate", "land", str(repo), "b", SHA, str(merge), *extra)
    monkeypatch.setattr(gate, "enqueue", real)
    rc, out, _ = run("gate", "run", str(repo), "--", "true")
    rc2, out2, _ = run("gate", "run", str(repo), "--session", A, "--", "true")
    ids = [o.split()[1] for o in (out, out2)]
    got += [json.loads((root / "gate" / "queue" / f"{i}.json").read_text())["chain"] for i in ids]
    assert got == [NAME, None, NAME, NAME, None, NAME, None]


# ---- 2 to 4. the take ------------------------------------------------------------------

def test_a_successor_takes_the_line_once_and_the_predecessor_never_held_it(root, repo,
                                                                           monkeypatch):
    gate.write_sitting(root, NAME, A, T0)
    e = put(root, repo, cenv(), A)
    close(root, A)
    gate.write_sitting(root, NAME, B, T0)                    # the launcher starts B
    gate.serve(root, Fx().make())
    chained(monkeypatch, B)
    lines = prompt(B)
    assert len(lines) == 1 and lines[0].startswith(f"gate {e['id']} ") and box(root) == []
    assert prompt(B) == [] and not (root / "sessions" / A / "inbox").exists()


def test_a_line_between_two_sittings_prints_at_the_next_first_prompt(root, repo, monkeypatch):
    gate.write_sitting(root, NAME, A, T0)
    e = put(root, repo, cenv(), A)
    close(root, A)
    gate.serve(root, Fx().make())                            # A closed, B not yet started
    gate.write_sitting(root, NAME, B, T0)
    chained(monkeypatch, B)
    assert [ln.split()[1] for ln in prompt(B)] == [e["id"]] and box(root) == []


def test_the_refuters_proof_a_closed_sitting_leaves_the_line(root, monkeypatch):
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    sdir = close(root, A)

    class Clock:
        def monotonic(self):
            return time.monotonic()
    c = chain.Chain(NAME, [], root, Clock(), dict(chain.DEFAULTS))
    c.g = dict(chain.DEFAULTS)
    assert c._ready(sdir, time.time()) is False              # inside settle
    result = {"id": "20261122-070000-9001", "repo": "/scratch/row", "exit": 1, "seconds": 3240.0,
              "ended": time.time() - 20, "log": "/scratch/log", "chain": NAME, "label": "row",
              "head": SHA, "dirty": {"start": 0, "end": 0}}
    gate.inbox_write(root, A, result)
    shown = prompt(A, "<task-notification><task-id>b1</task-id></task-notification>")
    assert shown == [f"{gate.CLOSED_WORDS}: {gate.wait_line(result)}"]
    assert box(root) == ["20261122-070000-9001.json"]        # left for the successor
    assert prompt(A) == []                                   # shown once
    hooks.stop({"session_id": A})
    assert c._ready(sdir, time.time() + chain.DEFAULTS["settle"] + 1) is True   # the old mark
    gate.write_sitting(root, NAME, B, T0)
    chained(monkeypatch, B)
    assert prompt(B) == [gate.wait_line(result)] and box(root) == []


def test_with_no_sitting_file_a_child_takes_none(root, repo, monkeypatch):
    put(root, repo, cenv(), A)
    gate.serve(root, Fx().make())
    chained(monkeypatch, A)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli")
    assert prompt(A) == [] and len(box(root)) == 1
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    assert len(prompt(A)) == 1 and box(root) == []


# ---- 5. the watcher --------------------------------------------------------------------

def test_wait_chain_codes(root, repo, monkeypatch):
    clock = SimpleNamespace(t=0.0)
    kw = dict(sleep=lambda s: setattr(clock, "t", clock.t + s), clock=lambda: clock.t,
              spawn=lambda r: True, alive=lambda pid: True)
    gate.write_sitting(root, NAME, A, T0)
    assert gate.wait_chain(root, NAME, A, timeout=30, **kw) == (2, 0)
    put(root, repo, cenv(), A)
    assert gate.wait_chain(root, NAME, A, timeout=30, **kw) == (1, 0)
    gate.serve(root, Fx().make())
    assert gate.wait_chain(root, NAME, A, timeout=30, **kw) == (0, 1)
    close(root, A)
    assert gate.wait_chain(root, NAME, A, timeout=30, **kw) == (1, 0)   # after the mark
    chained(monkeypatch, C)
    rc, out, err = run("gate", "wait", "--chain", "--timeout", "1")
    assert rc == 2 and out == "" and "wait by id" in err


def test_the_close_does_not_ask_about_a_watcher(root, monkeypatch):
    chained(monkeypatch, A)
    sdir = resolver.session_dir(root, A)
    sdir.mkdir(parents=True)
    for tid, cmd in (("toolu_w", "agentik session gate wait --chain --timeout 3000"),
                     ("toolu_x", "agentik-session gate wait 20261122-070000-1 --strict"),
                     ("toolu_y", "agentik session gate wait --chain; make check")):
        hooks._job_open({"session_id": A, "tool_name": "Bash", "tool_use_id": tid,
                         "tool_input": {"command": cmd, "run_in_background": True},
                         "tool_response": {"backgroundTaskId": "b" + tid}}, sdir)
    recs = {p.name: r for p, r in hooks._jobs_open(sdir)}
    assert [n for n, r in sorted(recs.items()) if r.get("watcher")] == ["toolu_w", "toolu_x"]
    close_call = {"session_id": A, "tool_name": "Bash",
                  "tool_input": {"command": "agentik session checkpoint --respawn --charter /p.md"}}
    line = hooks._jobs_out_line(close_call, os.environ)
    assert line is not None and line.startswith("agentik-session: 1 background job ")
    (sdir / hooks.JOBS / "toolu_y").unlink()
    assert hooks._jobs_out_line(close_call, os.environ) is None


# ---- 6. the line -----------------------------------------------------------------------

def test_the_line_has_head_dirt_and_a_cut_label(root, monkeypatch):
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    long = "x" * 300
    for n, dirt in ((1, {"start": 2, "end": 0}), (2, {"start": 0, "end": 0})):
        gate.inbox_write(root, A, {"id": f"20261122-070000-{n}", "repo": "/r/row", "exit": 1,
                                   "seconds": 3240.0, "ended": time.time(), "log": "/g/log",
                                   "chain": NAME, "label": long, "head": SHA, "dirty": dirt})
    lines = prompt(A)
    assert lines[0] == ("gate 20261122-070000-1 /r/row: exit 1 in 54 min; head 8e37e4e; "
                        f"dirty 2; {'x' * 48}; log /g/log")
    assert lines[1] == ("gate 20261122-070000-2 /r/row: exit 1 in 54 min; head 8e37e4e; "
                        f"{'x' * 48}; log /g/log")
    assert len(json.dumps(hooks._with_gate({}, "UserPromptSubmit", lines))) <= hooks.MAX_OUT
    assert box(root) == []


def test_a_line_older_than_a_day_is_set_aside_and_counted(root, monkeypatch):
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    for n, at in ((1, time.time() - 25 * 3600), (2, time.time() - 26 * 3600), (3, time.time())):
        gate.inbox_write(root, A, {"id": f"20261122-070000-{n}", "repo": "/r", "exit": 0,
                                   "seconds": 60.0, "ended": at, "log": "/l", "chain": NAME})
    lines = prompt(A)
    old = gate.chain_inbox(root, NAME) / "old"
    assert lines[0] == f"gate: 2 lines of this chain older than 24 hours set aside in {old}"
    assert lines[1].startswith("gate 20261122-070000-3 ") and len(lines) == 2
    assert sorted(os.listdir(old)) == ["20261122-070000-1.json", "20261122-070000-2.json"]


# ---- 7. the start, status, the stop line, _ready, the close's words ----------------------

def test_the_start_names_the_open_jobs(root, repo, monkeypatch):
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    a = put(root, repo, cenv(), A, label="row one")
    b = put(root, repo, cenv(), A, label="row two")
    put(root, repo, {}, A, label="no chain")
    gate.entry_dir(root, a["id"]).mkdir(parents=True)
    (root / "gate" / "runner.json").write_text(json.dumps(
        {"pid": os.getpid(), "since": T0, "running": a["id"], "pgid": 1}))
    out = hooks.session_start({"session_id": A, "hook_event_name": "SessionStart",
                               "cwd": str(repo)})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert ctx.splitlines()[0] == (f"gate: 2 jobs of this chain are open: {a['id']} row one "
                                   f"running 0 min; {b['id']} row two queued")
    monkeypatch.setattr(gate, "spawn_serve", lambda r, popen=None: True)
    rc, text, _ = run("gate", "status", "--chain")
    assert rc == 0 and text.splitlines()[0] == ctx.splitlines()[0]
    chained(monkeypatch, C)                                  # another session is told nothing
    out = hooks.session_start({"session_id": C, "hook_event_name": "SessionStart",
                               "cwd": str(repo)})
    assert not (out.get("hookSpecificOutput") or {}).get("additionalContext", "").startswith("gate")


def test_status_chain_lists_the_days_results(root, repo, monkeypatch):
    chained(monkeypatch, A)
    a = put(root, repo, cenv(), A)
    put(root, repo, {}, A)
    gate.serve(root, Fx().make())
    monkeypatch.setattr(gate, "spawn_serve", lambda r, popen=None: True)
    rc, text, _ = run("gate", "status", "--chain", NAME)
    lines = text.splitlines()
    assert rc == 0 and lines[0] == f"gate: no job of chain {NAME} is open" and len(lines) == 2
    assert lines[1].startswith(f"gate {a['id']} ") and lines[1].endswith("; waiting")


def test_the_stop_line_counts_the_chains_inbox(root):
    said = []
    fx = SimpleNamespace(append=lambda *a: None, say=said.append)
    c = chain.Chain(NAME, [], root, fx, dict(chain.DEFAULTS))
    c.argv = ["agentik", "session", "run"]
    c._stop(A, "cap", 1, 10)
    assert not any("inbox" in s for s in said)
    for n in (1, 2):
        gate.inbox_write(root, A, {"id": f"20261122-070000-{n}", "exit": 0, "ended": T0,
                                   "chain": NAME})
    said.clear()
    c._stop(A, "cap", 1, 10)
    assert said[0] == f"{NAME}: the chain's inbox still holds 2 gate lines: {gate.chain_inbox(root, NAME)}"


def test_ready_with_only_a_gate_job_open(root, repo):
    sdir = close(root, A, ago=200)
    put(root, repo, cenv(), A)

    class Clock:
        def monotonic(self):
            return time.monotonic()
    c = chain.Chain(NAME, [], root, Clock(), dict(chain.DEFAULTS))
    c.g = dict(chain.DEFAULTS)
    assert gate.open_jobs(root, NAME) and c._ready(sdir, time.time()) is True


def test_the_launcher_names_each_sitting_and_starts_the_runner(root, monkeypatch):
    started = []
    fx = SimpleNamespace(now=lambda: T0, say=lambda s: None, gate_start=started.append)
    c = chain.Chain(NAME, [], root, fx, dict(chain.DEFAULTS))
    c._sitting(B)
    assert gate.sitting_of(root, NAME) == (True, B) and started == [root]


def test_the_close_and_the_checkpoint_say_the_jobs_cross(root, repo, monkeypatch):
    chained(monkeypatch, A)
    put(root, repo, cenv(), A)
    put(root, repo, cenv(), A)
    line = cli._respawn_mark(A, "/nowhere/page.md", "0" * 64)
    assert line.endswith("; 2 gate jobs are open and cross to the successor: do not wait for them")
    sdir = resolver.session_dir(root, A)
    monkeypatch.setattr(hooks.meter, "parse", lambda *a: SimpleNamespace(
        used_pct=60.0, checkpoint_at=0.5, as_dict=lambda: {}))
    monkeypatch.setattr(hooks.meter, "save", lambda *a: None)
    monkeypatch.setattr(hooks, "_signal", lambda m: True)
    monkeypatch.setattr(hooks, "_speaking", lambda *a: {"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": "CHECKPOINT: 60% context"}})
    out = hooks._post_meter({"session_id": A, "transcript_path": "/nowhere/t.jsonl"},
                            os.environ, sdir)
    assert out["hookSpecificOutput"]["additionalContext"] == (
        "CHECKPOINT: 60% context\n\n" + gate.gate_words(2))
    monkeypatch.delenv("CLAUDE_SESSION_CHAIN")
    out = hooks._post_meter({"session_id": A, "transcript_path": "/nowhere/t.jsonl"},
                            os.environ, sdir)
    assert out["hookSpecificOutput"]["additionalContext"] == "CHECKPOINT: 60% context"


# ---- 8. est by command -----------------------------------------------------------------

def test_est_counts_the_greens_of_the_same_command(root, repo):
    k = gate.repo_key(str(repo))
    check = ["/bin/sh", "-c", "make check > /scratch/a.log 2>&1"]
    cmds = [["/bin/sh", "-c", "make stamp > /s.log"], ["make", "install"],
            check, ["/bin/sh", "-c", "make check > /scratch/b.log 2>&1"], ["make", "check"]]
    for n, (cmd, s) in enumerate(zip(cmds, (30.0, 90.0, 480.0, 500.0, 520.0)), 1):
        gid = f"20261109-120000-{n}"
        gate.entry_dir(root, gid).mkdir(parents=True)
        gate.result_path(root, gid).write_text(json.dumps(
            {"id": gid, "command": cmd, "exit": 0, "cut": None, "seconds": s, "key": k}))
    assert gate.key_estimates(root, check) == {k: (500.0, 3)}
    assert gate.key_estimates(root, ["make", "stamp"]) == {}       # one stamp: no estimate
    assert gate.command_kind(["make", "install"]) == "make install"
    assert gate.command_kind(["true"]) == "true"
    e = put(root, repo, {}, None, command=check)
    assert gate.entry_estimates(root) == {e["id"]: 500.0}


# ---- brief 2: review 1's blocks and notes -------------------------------------------------

def _red_own_and_chain(root, repo):
    """A closed sitting A holding one red of its own (`--session A`) and one of its chain,
    its shown record a folder, so the record's write fails after the own line moved."""
    gate.write_sitting(root, NAME, A, T0)
    own = put(root, repo, cenv(), A, named=True)
    ch = put(root, repo, cenv(), A)
    gate.serve(root, Fx(rc=2).make())
    (close(root, A) / gate.SHOWN).mkdir()
    return own, ch


def test_an_unwritable_shown_record_still_prints_the_own_red_line(root, repo, monkeypatch):
    monkeypatch.setattr(hooks, "MAX_OUT", 10 ** 6)
    own, ch = _red_own_and_chain(root, repo)
    chained(monkeypatch, A)
    first = prompt(A)
    assert [ln for ln in first if own["id"] in ln and "exit 2" in ln]
    assert box(root) == [f"{ch['id']}.json"]                  # the chain's line never moved
    again = prompt(A)                                         # shown again, still left
    assert not [ln for ln in again if own["id"] in ln] and box(root) == [f"{ch['id']}.json"]


def test_inbox_take_returns_what_it_moved_when_the_record_fails(root, repo, monkeypatch):
    own, ch = _red_own_and_chain(root, repo)
    got = gate.inbox_take(root, A, chain=NAME, closed=True)
    assert [ln for ln in got if own["id"] in ln]
    assert [ln for ln in got if ln.startswith(gate.CLOSED_WORDS) and ch["id"] in ln]
    assert box(root) == [f"{ch['id']}.json"]


def test_a_wait_in_the_gap_before_the_line_never_answers_2(root, repo, monkeypatch):
    clock = SimpleNamespace(t=0.0)
    kw = dict(sleep=lambda s: setattr(clock, "t", clock.t + s), clock=lambda: clock.t,
              spawn=lambda r: True, alive=lambda pid: True)
    gate.write_sitting(root, NAME, A, T0)
    put(root, repo, cenv(), A)
    seen, real = {}, gate.inbox_write

    def gap(r, sid, result):
        seen["wait"] = gate.wait_chain(root, NAME, A, timeout=5, **kw)
        return real(r, sid, result)
    monkeypatch.setattr(gate, "inbox_write", gap)
    gate.serve(root, Fx(rc=1).make())
    monkeypatch.setattr(gate, "inbox_write", real)
    assert seen["wait"] != (2, 0)
    assert gate.wait_chain(root, NAME, A, timeout=5, **kw) == (0, 1)
    chained(monkeypatch, A)
    assert prompt(A)                                          # the line taken
    assert gate.wait_chain(root, NAME, A, timeout=5, **kw) == (2, 0)


LAND_A = ["/usr/bin/python3", "/p/cli.py", "gate", "land", "--in-job", "/w/r", "b1", "a" * 40, "/m1"]
LAND_B = ["/usr/bin/python3", "/p/cli.py", "gate", "land", "--in-job", "/w/r", "b2", "b" * 40, "/m2"]


@pytest.mark.parametrize("argv,kind", [
    (["make", "check"], "make check"),
    (["make", "-j", "4", "check"], "make check"),
    (["make", "-j4", "check"], "make check"),
    (["make", "-j", "check"], "make check"),
    (["make", "-C", "/w/repo", "check"], "make check"),
    (["make", "-C", "/w/repo", "stamp"], "make stamp"),
    (["make", "-C/w/repo", "stamp"], "make stamp"),
    (["make", "-f", "ci.mk", "check"], "make check"),
    (["make", "--file", "ci.mk", "check"], "make check"),
    (["make", "--directory=/w/repo", "--file=ci.mk", "check"], "make check"),
    (["make", "--directory", "/w/repo", "check"], "make check"),
    (["make", "-I", "inc", "-o", "a.o", "-W", "b.c", "V=1", "check"], "make check"),
    (["make", "-sC", "/w/repo", "check"], "make check"),
    (["/usr/bin/make", "-C", "/w/repo", "check"], "make check"),
    (["make"], "make"),
    (["make", "-C", "/w/repo"], "make"),
    (["/bin/sh", "-c", "make check > log 2>&1"], "make check"),
    (["/bin/sh", "-c", "make -C /w/repo stamp > log 2>&1"], "make stamp"),
    (["/bin/sh", "-c", "cd /w/repo && make -j 8 check"], "make check"),
    (["/bin/sh", "-c", "make stamp && make check"], "make stamp"),
    (["/bin/sh", "-c", "make > log 2>&1"], "make"),
    (["git", "commit", "-m", "make it so"], "git commit -m make it so"),
    (["/bin/sh", "-c", "echo make it so"], "/bin/sh -c echo make it so"),
    (["cmake", "--build", "."], "cmake --build ."),
    (["true"], "true"),
    (LAND_A, "gate land"),
    (LAND_B, "gate land"),
])
def test_a_jobs_kind_is_makes_own_target(argv, kind):
    assert gate.command_kind(argv) == kind


@pytest.mark.parametrize("argv,kind", [
    (["make", "V=1", "check"], "make check"),
    (["make", "V:=1", "check"], "make check"),
    (["make", "V::=1", "check"], "make check"),
    (["make", "V:::=1", "check"], "make check"),
    (["make", "V+=1", "check"], "make check"),
    (["make", "V?=1", "check"], "make check"),
    (["make", "V!=echo 1", "check"], "make check"),
    (["make", "a.b-c_9:=1", "check"], "make check"),
    (["make", "CFLAGS+=-O2", "stamp"], "make stamp"),
    (["make", "--", "V:=1", "check"], "make check"),
    (["/bin/sh", "-c", "make V:=1 check > log 2>&1"], "make check"),
    (["make", "-E", "x:=1", "check"], "make check"),
    (["make", "--eval", "x:=1", "check"], "make check"),
    (["make", "--eval=x:=1", "check"], "make check"),
    (["make", "-E", "all: ; true", "check"], "make check"),
])
def test_a_make_assignment_in_any_spelling_is_never_the_target(argv, kind):
    """Brief 4, R1: a word that assigns a make variable, in each of GNU make's spellings, and
    the value after `-E` or `--eval` are never the target."""
    assert gate.command_kind(argv) == kind


def test_a_string_the_reader_refuses_gives_the_joined_argv(monkeypatch):
    """Brief 3, R2: the `-c` string is read by the one shell reader; where it cannot read it,
    the kind is the argv joined, and nothing is raised: a queued job still gets its entry."""
    assert gate.command_kind(["/bin/sh", "-c", "make 'check"]) == "/bin/sh -c make 'check"
    from claude_session import shellreader

    def refuses(*a, **kw):
        raise RuntimeError("unreadable")
        yield                                                  # a generator, as the reader is

    monkeypatch.setattr(shellreader, "_commands", refuses)
    assert gate.command_kind(["/bin/sh", "-c", "make check"]) == "/bin/sh -c make check"
    assert gate.command_kind(["make", "check"]) == "make check"


def _greens_of(root, repo, commands, seconds=(6.0, 7.0, 8.0)):
    k = gate.repo_key(str(repo))
    for n, (cmd, s) in enumerate(zip(commands, seconds), 1):
        gid = f"20261101-000000-{n}"
        gate.entry_dir(root, gid).mkdir(parents=True)
        gate.result_path(root, gid).write_text(json.dumps(
            {"id": gid, "repo": str(repo), "command": cmd, "exit": 0, "cut": None,
             "seconds": s, "key": k}))
    return k


def test_three_stamps_under_dash_c_give_a_check_no_estimate(root, repo):
    stamp = ["make", "-C", str(repo), "stamp"]
    k = _greens_of(root, repo, [stamp] * 3)
    assert gate.key_estimates(root, ["make", "-C", str(repo), "check"]) == {}
    assert gate.key_estimates(root, stamp) == {k: (7.0, 3)}


def test_landings_share_an_estimate(root, repo):
    third = LAND_A[:6] + ["b3", "c" * 40, "/m3"]
    k = _greens_of(root, repo, [LAND_A, LAND_B, third], (60.0, 70.0, 80.0))
    fourth = LAND_A[:6] + ["b4", "d" * 40, "/m4"]
    assert gate.key_estimates(root, fourth) == {k: (70.0, 3)}


def test_a_closed_sittings_wait_says_it_has_closed(root, repo, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda r, popen=None: True)
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    close(root, A)
    rc, out, err = run("gate", "wait", "--chain", "--timeout", "0.1")   # no line waits
    assert rc == 1 and out == "" and "has closed" in err and "successor" in err
    put(root, repo, cenv(), A)
    gate.serve(root, Fx(rc=2).make())
    rc, out, err = run("gate", "wait", "--chain", "--timeout", "0.1")   # a red waits
    assert rc == 1 and out == "" and "has closed" in err and "successor" in err
    assert len(box(root)) == 1


def test_status_chain_refuses_json(root, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda r, popen=None: True)
    chained(monkeypatch, A)
    rc, out, err = run("gate", "status", "--chain", "--json")
    assert rc == 2 and out == "" and "--json" in err
    assert run("gate", "status", "--chain")[0] == 0


def test_a_label_adds_no_field_to_a_line(root, monkeypatch):
    chained(monkeypatch, A)
    gate.write_sitting(root, NAME, A, T0)
    labels = ["row", "a|b\nexit 0 in 1 min; log /fake", "x\x1b[2Jy\x7f\x9b;z", "r;" * 40]
    for n, lab in enumerate(labels, 1):
        gate.inbox_write(root, A, {"id": f"20261122-070000-{n}", "repo": "/r/row", "exit": 1,
                                   "seconds": 60.0, "ended": time.time(), "log": "/g/log",
                                   "chain": NAME, "label": lab, "head": SHA,
                                   "dirty": {"start": 0, "end": 0}})
    got = prompt(A) + prompt(A)                               # three a take, then one
    assert len(got) == 4
    for ln in got:
        assert ln.count(";") == got[0].count(";") and ln.count("; log ") == 1
        assert not [c for c in ln if ord(c) < 32 or 127 <= ord(c) < 160]
    assert gate._label("x\x1b[2Jy\x7f;z") == "x [2Jy z"
    assert len(gate._label("r;" * 40).encode()) <= gate.LABEL_MOST


def test_a_closed_sitting_leaves_a_corrupt_chain_line(root, monkeypatch):
    gate.write_sitting(root, NAME, A, T0)
    close(root, A)
    d = gate.chain_inbox(root, NAME)
    d.mkdir(parents=True)
    (d / "20261122-070000-5.json").write_text("{not json")
    chained(monkeypatch, A)
    assert prompt(A) == [] and box(root) == ["20261122-070000-5.json"]
    assert not (d / "read").exists() or os.listdir(d / "read") == []
    gate.write_sitting(root, NAME, B, T0)                     # a live sitting sets it aside
    chained(monkeypatch, B)
    assert prompt(B) == [] and box(root) == []
    assert os.listdir(d / "read") == ["20261122-070000-5.json"]


def test_a_set_aside_that_fails_stops_no_take(root, repo, monkeypatch):
    monkeypatch.setattr(hooks, "MAX_OUT", 10 ** 6)
    gate.write_sitting(root, NAME, A, T0)
    own = put(root, repo, cenv(), A, named=True)
    fresh = put(root, repo, cenv(), A)
    gate.serve(root, Fx(rc=2).make())
    d = gate.chain_inbox(root, NAME)
    stale = "20261101-000000-9"
    gate.inbox_write(root, A, {"id": stale, "repo": "/r", "exit": 0, "seconds": 1.0,
                               "ended": time.time() - 30 * 3600, "log": "/l", "chain": NAME})
    (d / "old").write_text("not a folder\n")
    chained(monkeypatch, A)
    got = prompt(A)
    assert [ln for ln in got if own["id"] in ln] and [ln for ln in got if fresh["id"] in ln]
    assert box(root) == [f"{stale}.json"]                     # left where it is
    assert os.listdir(root / "sessions" / A / "inbox") == ["read"]
