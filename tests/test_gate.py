"""The gate queue (design/gate-r1.md, packet S38): the queue, the runner, wait, status, the
inbox and ntfy, every effect faked (the clock, spawn, flock, the group kill and the POST)."""
import fcntl
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import gate, hooks

T0 = 1_800_000_000.0
ID = re.compile(r"^\d{8}-\d{6}-\d+$")
ENV = {"PATH": "/usr/bin:/bin", "GATE_TEST": "1"}


class Proc:
    def __init__(self, world, pid, seconds, rc):
        self.world, self.pid, self.seconds, self.rc = world, pid, seconds, rc
        self.t0, self.killed = world.t, None

    def poll(self):
        if self.killed is not None:
            return -self.killed
        if self.seconds is not None and self.world.t - self.t0 >= self.seconds:
            return self.rc
        return None

    def wait(self, timeout=None):
        return self.poll()


class World:
    """One state root, a fake clock that moves only when the runner sleeps, a fake spawn."""

    def __init__(self, tmp_path):
        self.root = tmp_path / "state"
        self.home = tmp_path / "home"
        self.repo = tmp_path / "repo"
        self.home.mkdir()
        self.repo.mkdir()
        self.t = T0
        self.plan = {}            # argv[0] -> (seconds or None, exit), or an exception to raise
        self.spawned, self.kills, self.posts, self.logs, self.hooks = [], [], [], [], []

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s
        for h in list(self.hooks):
            h(self)

    def popen(self, argv, **kw):
        how = self.plan.get(argv[0], (0, 0))
        if isinstance(how, BaseException):
            raise how
        kw["stdout"].write(b"out of " + argv[0].encode() + b"\n")
        p = Proc(self, 4000 + len(self.spawned), *how)
        self.spawned.append((list(argv), kw, p))
        return p

    def killpg(self, pgid, sig):
        self.kills.append((pgid, sig))
        for _, _, p in self.spawned:
            if p.pid == pgid and sig == signal.SIGKILL:
                p.killed = sig

    def post(self, url, data, headers, timeout):
        self.posts.append((url, data, headers, timeout))

    def fx(self, **over):
        kw = dict(now=self.now, sleep=self.sleep, popen=self.popen, killpg=self.killpg,
                  post=self.post, log=self.logs.append, env={"HOME": str(self.home)},
                  idle=60.0, poll=1.0, grace=5.0, pid=777)
        kw.update(over)
        return gate.Fx(**kw)

    def put(self, first="a", locks=(), wall=5400, caller=None, label="", at=None):
        return gate.enqueue(self.root, str(self.repo), [first, "x"], ENV, list(locks), wall,
                            label, caller, self.t if at is None else at)

    def result(self, gid):
        return json.loads(gate.result_path(self.root, gid).read_text())

    def ntfy(self):
        cfg = self.home / ".claude" / "agentik" / "profiles.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("gate:\n  ntfy_url: https://ntfy.invalid/\n  ntfy_topic: gates\n")


@pytest.fixture
def w(tmp_path):
    return World(tmp_path)


def _results(n, repo="/r/x", root="/s"):
    return [{"id": f"20261029-120000-{i}", "repo": repo, "exit": i % 2, "seconds": 60.0 * i,
             "log": f"{root}/gate/20261029-120000-{i}/log", "ended": T0 + i}
            for i in range(1, n + 1)]


# ---- the queue ---------------------------------------------------------------

def test_enqueue_writes_a_private_entry_with_its_eleven_keys(w):
    e = w.put(label="land s38", caller="sess-1")
    p = w.root / "gate" / "queue" / f"{e['id']}.json"
    assert ID.match(e["id"]) and e["id"].endswith("-1")
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    body = json.loads(p.read_text())
    assert list(body) == list(gate.ENTRY_KEYS)
    assert body == {"id": e["id"], "repo": os.path.realpath(w.repo), "command": ["a", "x"],
                    "env": ENV, "locks": [], "wall": 5400, "label": "land s38",
                    "caller": "sess-1", "queued": T0, "key": gate.repo_key(str(w.repo)),
                    "key_name": "repo"}
    assert [n for n in os.listdir(p.parent) if n.startswith(".")] == []   # written, renamed


def test_the_counter_orders_the_queue_whatever_the_clock(w):
    a, b, c = w.put(at=T0 + 100), w.put(at=T0), w.put(at=T0 + 50)
    assert [x["id"] for x in gate.entries(w.root)] == [a["id"], b["id"], c["id"]]
    assert [x["id"].rsplit("-", 1)[1] for x in (a, b, c)] == ["1", "2", "3"]
    assert [gate.position(w.root, x["id"]) for x in (a, b, c)] == [1, 2, 3]


def test_enqueue_refuses_what_it_cannot_run(w, tmp_path):
    for repo, cmd, wall, caller in ((str(tmp_path / "gone"), ["a"], 60, None),
                                    (str(w.repo), [], 60, None),
                                    (str(w.repo), ["a"], 0, None),
                                    (str(w.repo), ["a"], 60, "../x")):
        with pytest.raises(gate.GateError):
            gate.enqueue(w.root, repo, cmd, ENV, [], wall, "", caller, T0)
    assert gate.entries(w.root) == []


def test_the_repo_is_its_realpath_and_a_lock_is_absolute(w, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(w.repo)
    e = gate.enqueue(w.root, str(link), ["a"], ENV, ["rel/lock"], 60, "", None, T0)
    assert e["repo"] == os.path.realpath(w.repo) and e["locks"] == [os.path.abspath("rel/lock")]


class A:
    def __init__(self, session=None):
        self.session = session


def test_resolve_caller_session_then_the_env_then_none():
    assert gate.resolve_caller(A("sess-1"), {"CLAUDE_CODE_SESSION_ID": "other"}) == "sess-1"
    assert gate.resolve_caller(A(), {"CLAUDE_CODE_SESSION_ID": "other"}) == "other"
    assert gate.resolve_caller(A(), {}) is None
    assert gate.resolve_caller(A(), {"CLAUDE_CODE_SESSION_ID": "../etc"}) is None
    with pytest.raises(gate.GateError):
        gate.resolve_caller(A("../etc"), {})
    assert gate._SID.pattern == hooks._SID.pattern


# ---- the runner --------------------------------------------------------------

def test_serve_runs_fifo_and_writes_the_result_last(w):
    w.plan = {"a": (3, 0), "b": (2, 3)}
    a, b = w.put("a"), w.put("b")
    assert gate.serve(w.root, w.fx()) == 0
    assert [s[0] for s in w.spawned] == [["a", "x"], ["b", "x"]]
    _, kw, _ = w.spawned[0]
    assert (kw["cwd"], kw["env"]) == (os.path.realpath(w.repo), ENV)
    assert kw["start_new_session"] is True and kw["close_fds"] is True
    assert kw["stderr"] == subprocess.STDOUT
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert list(ra) == list(gate.RESULT_KEYS)
    assert (ra["exit"], rb["exit"], ra["cut"], rb["cut"]) == (0, 3, None, None)
    assert rb["started"] >= ra["ended"] and ra["seconds"] == 3
    log = Path(rb["log"]).read_text().splitlines()
    assert log[0] == f"gate {b['id']}: {os.path.realpath(w.repo)}: b x"
    assert "out of b" in log and log[-1] == f"gate {b['id']}: exit 3 in 2 s"
    assert gate.entries(w.root) == [] and not (w.root / "gate" / "runner.json").exists()


def test_runner_json_holds_its_keys_while_an_entry_runs(w):
    seen = []

    def peek(world):
        p = world.root / "gate" / "runner.json"
        if p.exists():
            seen.append(json.loads(p.read_text()))
    w.hooks.append(peek)
    w.plan = {"a": (2, 0)}
    a = w.put("a")
    gate.serve(w.root, w.fx())
    running = [s for s in seen if s["running"]]
    assert running and list(running[0]) == list(gate.RUNNER_KEYS)
    assert (running[0]["running"], running[0]["pid"]) == \
        ([{"id": a["id"], "pgid": w.spawned[0][2].pid}], 777)
    assert any(s["running"] == [] for s in seen)


def test_a_second_serve_exits_0_while_another_holds_the_lock(w):
    w.put("a")

    def busy(fd, op):
        if op & fcntl.LOCK_NB:
            raise BlockingIOError(35, "held")
    assert gate.serve(w.root, w.fx(flock=busy)) == 0
    assert w.spawned == [] and not (w.root / "gate" / "runner.json").exists()
    assert len(gate.entries(w.root)) == 1


def test_the_wall_cuts_the_group_with_124(w):
    w.plan = {"a": (None, 0)}
    a = w.put("a", wall=10)
    gate.serve(w.root, w.fx())
    pid = w.spawned[0][2].pid
    assert w.kills == [(pid, signal.SIGTERM), (pid, signal.SIGKILL)]
    r = w.result(a["id"])
    assert (r["exit"], r["cut"]) == (124, "wall cut") and r["seconds"] >= 10


def test_a_head_locked_past_its_wall_gets_126_and_never_runs(w, tmp_path):
    lock = tmp_path / "tlc.lock"
    lock.mkdir()
    a = w.put("a", locks=[str(lock)], wall=30)
    gate.serve(w.root, w.fx())
    r = w.result(a["id"])
    assert w.spawned == [] and (r["exit"], r["cut"]) == (126, "lock wait cut")
    assert w.t - T0 >= 30 and str(lock) in Path(r["log"]).read_text()


def test_a_younger_unlocked_entry_runs_first_then_the_head_when_its_lock_goes(w, tmp_path):
    lock = tmp_path / "tlc.lock"
    lock.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    a = w.put("a", locks=[str(lock)], wall=600)
    b = gate.enqueue(w.root, str(other), ["b", "x"], ENV, [], 5400, "", None, w.t)

    def free(world):
        if gate.result_path(world.root, b["id"]).exists() and lock.exists():
            lock.rmdir()
    w.hooks.append(free)
    gate.serve(w.root, w.fx())
    assert [s[0][0] for s in w.spawned] == ["b", "a"]
    assert (w.result(a["id"])["exit"], w.result(a["id"])["cut"]) == (0, None)


def test_a_stale_runner_json_kills_its_group_and_writes_125(w):
    a = w.put("a", caller="sess-1")
    g = w.root / "gate"
    (g / "runner.json").write_text(json.dumps({"pid": 99999999, "since": T0,
                                               "running": a["id"], "pgid": 4242}))
    (g / a["id"]).mkdir()
    (g / a["id"] / "log").write_text("half a log\n")
    gate.serve(w.root, w.fx())
    assert w.kills == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]
    r = w.result(a["id"])
    assert (r["exit"], r["cut"]) == (125, "runner died") and w.spawned == []
    assert gate.entries(w.root) == []
    assert (w.root / "sessions" / "sess-1" / "inbox" / f"{a['id']}.json").exists()


def test_a_command_that_cannot_start_is_127(w):
    w.plan = {"a": FileNotFoundError(2, "No such file or directory", "a")}
    a = w.put("a")
    gate.serve(w.root, w.fx())
    r = w.result(a["id"])
    assert r["exit"] == 127 and "cannot start" in Path(r["log"]).read_text()


def test_a_death_by_signal_reads_128_plus_the_signal(w):
    w.plan = {"a": (1, -15)}
    a = w.put("a")
    gate.serve(w.root, w.fx())
    assert w.result(a["id"])["exit"] == 143


def test_results_past_14_days_are_pruned(w):
    w.plan = {"a": (1, 0)}
    old = w.put("a")
    gate.serve(w.root, w.fx())
    w.t += 15 * 86400
    new = w.put("a")
    gate.serve(w.root, w.fx())
    assert not (w.root / "gate" / old["id"]).exists()
    assert gate.result_path(w.root, new["id"]).exists()


def test_the_idle_release_rescans_and_retakes_for_a_late_entry(w):
    late = []

    def flock(fd, op):
        fcntl.flock(fd, op)
        if op == fcntl.LOCK_UN and not late:
            late.append(w.put("b"))
    w.plan = {"a": (1, 0), "b": (1, 0)}
    w.put("a")
    assert gate.serve(w.root, w.fx(flock=flock)) == 0
    assert [s[0][0] for s in w.spawned] == ["a", "b"]
    assert w.result(late[0]["id"])["exit"] == 0


# ---- the caller's inbox and ntfy ---------------------------------------------

def test_a_result_reaches_the_inbox_and_ntfy_once(w):
    w.ntfy()
    w.plan = {"a": (1, 3)}
    a = w.put("a", caller="sess-1")
    gate.serve(w.root, w.fx())
    box = w.root / "sessions" / "sess-1" / "inbox" / f"{a['id']}.json"
    body = json.loads(box.read_text())
    assert list(body) == list(gate.INBOX_KEYS) and (body["kind"], body["exit"]) == ("gate", 3)
    line = gate.wait_line(w.result(a["id"]))
    assert w.posts == [("https://ntfy.invalid/gates", line.encode(),
                        {"Title": f"gate {os.path.realpath(w.repo)}: exit 3"}, 5)]


def test_a_failed_post_is_one_line_in_the_runner_log(w):
    w.ntfy()

    def boom(*a):
        raise OSError("refused")
    w.put("a")
    gate.serve(w.root, w.fx(post=boom))
    hits = [x for x in w.logs if "ntfy" in x]
    assert len(hits) == 1 and "\n" not in hits[0] and "refused" in hits[0]


def test_notify_needs_both_keys():
    posts = []
    r = _results(1)[0]
    assert gate.notify(r, {"ntfy_url": "https://x.invalid", "ntfy_topic": None},
                       lambda *a: posts.append(a)) is None
    assert posts == []


def test_the_wait_line():
    r = {"id": "20261029-120000-4", "repo": "/r/x", "exit": 3, "seconds": 150.0,
         "log": "/s/gate/20261029-120000-4/log"}
    assert gate.wait_line(r) == ("gate 20261029-120000-4 /r/x: exit 3 in 2 min; "
                                 "log /s/gate/20261029-120000-4/log")


def test_inbox_take_three_then_the_count_and_renames_what_it_printed(w):
    for r in _results(5):
        gate.inbox_write(w.root, "sess-1", r)
    lines = gate.inbox_take(w.root, "sess-1")
    assert lines == [gate.wait_line(r) for r in _results(3)] + \
        ["2 more: agentik session gate status"]
    read = w.root / "sessions" / "sess-1" / "inbox" / "read"
    assert sorted(p.name for p in read.iterdir()) == sorted(f"{r['id']}.json" for r in _results(3))
    assert len(gate.inbox_take(w.root, "sess-1")) == 2
    assert gate.inbox_take(w.root, "sess-1") == []


def test_inbox_take_stops_where_the_text_would_not_fit(w):
    for r in _results(4):
        gate.inbox_write(w.root, "sess-1", r)
    one = gate.wait_line(_results(1)[0])
    lines = gate.inbox_take(w.root, "sess-1", fits=lambda t: len(t) <= len(one) + 40)
    assert lines == [one, "3 more: agentik session gate status"]


def test_the_inbox_refuses_a_bad_session_id(w):
    assert gate.inbox_write(w.root, "../x", _results(1)[0]) is None
    assert gate.inbox_take(w.root, "../x") == []
    assert not (w.root / "sessions").exists()


# ---- wait, status, spawn -----------------------------------------------------

def test_wait_reads_a_result_unknown_is_2_and_a_timeout_is_1(w):
    w.plan = {"a": (1, 3)}
    a = w.put("a")
    gate.serve(w.root, w.fx())
    rc, r = gate.wait(w.root, a["id"])
    assert (rc, r["exit"]) == (0, 3)
    assert gate.wait(w.root, "nosuch") == (2, None)
    assert gate.wait(w.root, "20261029-120000-99") == (2, None)
    b = w.put("b")
    spawns, slept, t = [], [], [0.0]

    def sleep(s):
        slept.append(s)
        t[0] += s
    rc = gate.wait(w.root, b["id"], poll=5, timeout=12, sleep=sleep, clock=lambda: t[0],
                   spawn=spawns.append, alive=lambda pid: False)
    assert rc == (1, None) and slept == [5, 5, 2] and spawns[0] == w.root


def test_status_lines_running_queued_done_and_the_runner(w, tmp_path):
    lock = tmp_path / "tlc.lock"
    lock.mkdir()
    w.plan = {"d": (60, 1)}
    done = [w.put("d") for _ in range(6)]
    gate.serve(w.root, w.fx())
    run, q1, q2 = w.put("r", label="land s38"), w.put("q"), w.put("q", locks=[str(lock)])
    g = w.root / "gate"
    (g / "runner.json").write_text(json.dumps({"pid": os.getpid(), "since": T0,
                                               "running": run["id"], "pgid": 1}))
    os.utime(g / "runner.json", (T0, T0))
    lines = gate.status_lines(gate.status(w.root, T0))
    hm = time.strftime("%H:%M", time.localtime(T0))
    repo = os.path.realpath(w.repo)
    assert lines[:3] == [f"running {run['id']} {repo} since {hm} land s38",
                         f"queued {q1['id']} {repo} position 1 waits on key repo",
                         f"queued {q2['id']} {repo} position 2 waits on lock {lock}"]
    assert lines[3:8] == [f"done {d['id']} {repo} exit 1 1 min" for d in reversed(done[1:])]
    assert lines[8:] == [f"runner: pid {os.getpid()} since {time.strftime('%H:%M', time.localtime(T0))}"]


def test_status_with_nothing_says_runner_none(w):
    st = gate.status(w.root, T0)
    assert list(st) == ["running", "queued", "done", "runner"]
    assert gate.status_lines(st) == ["runner: none"]


def test_spawn_serve_runs_this_python_detached_and_only_for_a_queue(w):
    calls = []

    def popen(argv, **kw):
        calls.append((argv, kw))
    assert gate.spawn_serve(w.root, popen=popen) is False and calls == []
    w.put("a")
    assert gate.spawn_serve(w.root, popen=popen) is True
    argv, kw = calls[0]
    assert argv[0] == sys.executable and argv[-6:] == ["-m", "claude_session", "gate", "serve",
                                                       "--root", str(w.root)]
    assert kw["start_new_session"] is True and kw["close_fds"] is True
    assert kw["stdin"] == subprocess.DEVNULL and kw["stderr"] == subprocess.STDOUT
    assert kw["stdout"].name == str(w.root / "gate" / "runner.log")
    assert kw["env"]["PYTHONPATH"].split(os.pathsep)[0] == \
        str(Path(gate.__file__).resolve().parent.parent)


# ---- Amendment 1 (refuter round 1) -------------------------------------------

def test_the_lock_wait_counts_from_the_locked_head_not_from_queued(w, tmp_path):
    # F1's repro: A sleeps 6 s; B (--lock L --wall 3) waits behind it; L is made at 5 s and
    # gone at 7 s, so B's lock was held about 2 s as the head: B runs, never cut.
    lock = tmp_path / "tlc.lock"
    w.plan = {"a": (6, 0), "b": (1, 0)}
    w.put("a")
    b = w.put("b", locks=[str(lock)], wall=3)

    def tlc(world):
        if T0 + 5 <= world.t < T0 + 7 and not lock.exists():
            lock.mkdir()
        elif world.t >= T0 + 7 and lock.exists():
            lock.rmdir()
    w.hooks.append(tlc)
    gate.serve(w.root, w.fx())
    assert [s[0][0] for s in w.spawned] == ["a", "b"]
    assert (w.result(b["id"])["exit"], w.result(b["id"])["cut"]) == (0, None)


def test_a_dead_child_runner_reads_as_dead_not_as_its_zombie():
    # F2: a runner the waiter spawned is its child; dead, it is a zombie that kill(0)
    # still finds, so _alive reaps it to tell.
    p = subprocess.Popen(["sh", "-c", "exit 0"])
    deadline = time.time() + 5
    while gate._alive(p.pid) and time.time() < deadline:
        time.sleep(0.05)
    assert gate._alive(p.pid) is False
    assert gate._alive(os.getpid()) is True
