"""Packet S47: one running per key under a load ceiling. Every effect is faked through Fx
(the clock, spawn, the group kill, the load, the core count); git alone is real, in a
temporary directory, and one end-to-end pair runs real `sh` children under a temporary
state root."""
import json
import os
import signal
import subprocess
import time

import pytest

from claude_session import gate, resolver
from test_gate import ENV, T0, World


class W(World):
    """World with more than one repo, and a load and a core count that a test sets."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        self.tmp = tmp_path
        self.load = 2.0
        self.cores = 16
        self.peak = 0
        self.hooks.append(self._peek)

    def fx(self, **over):
        over.setdefault("load", lambda: self.load)
        over.setdefault("cores", lambda: self.cores)
        return super().fx(**over)

    def _peek(self, world):
        r = gate.runner_info(self.root)
        if r and isinstance(r.get("running"), list):
            self.peak = max(self.peak, len(r["running"]))

    def dir(self, name):
        d = self.tmp / name
        d.mkdir(exist_ok=True)
        return str(d)

    def put_in(self, name, first, locks=(), wall=5400, caller=None, label=""):
        return gate.enqueue(self.root, self.dir(name), [first, "x"], ENV, list(locks), wall,
                            label, caller, self.t)

    def user(self, text):
        p = self.home / ".claude" / "agentik" / "profiles.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def order(self):
        return [s[0][0] for s in self.spawned]


@pytest.fixture
def w(tmp_path):
    return W(tmp_path)


def _git(*argv, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *argv], cwd=cwd, env=env, check=True,
                   capture_output=True)


def _repo_and_worktree(tmp_path):
    repo, tree = tmp_path / "main", tmp_path / "tree"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=repo)
    _git("worktree", "add", "-q", "-b", "side", str(tree), cwd=repo)
    return repo, tree


def _dead_runner(w, running, **more):
    g = w.root / "gate"
    g.mkdir(parents=True, exist_ok=True)
    (g / "runner.json").write_text(json.dumps({"pid": 99999999, "since": T0,
                                               "running": running, **more}))


def _live_runner(w, running, at=T0 - 1000):
    g = w.root / "gate"
    g.mkdir(parents=True, exist_ok=True)
    (g / "runner.json").write_text(json.dumps({"pid": os.getpid(), "since": T0,
                                               "running": running}))
    os.utime(g / "runner.json", (at, at))


# ---- ruling 1: the key ---------------------------------------------------------

def test_s47_a_worktree_shares_its_repos_key(w, tmp_path):
    repo, tree = _repo_and_worktree(tmp_path)
    sub = repo / "deep"
    sub.mkdir()
    want = os.path.realpath(repo / ".git")
    assert gate.repo_key(str(repo)) == want
    assert gate.repo_key(str(tree)) == want
    assert gate.repo_key(str(sub)) == want
    w.plan = {"a": (100, 0), "b": (5, 0)}
    a = gate.enqueue(w.root, str(repo), ["a"], ENV, [], 5400, "", None, w.t)
    b = gate.enqueue(w.root, str(tree), ["b"], ENV, [], 5400, "", None, w.t)
    assert a["key"] == b["key"] == want
    assert gate.serve(w.root, w.fx()) == 0
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"]
    assert w.peak == 1


def test_s47_the_key_ignores_a_git_dir_in_the_environment(tmp_path, monkeypatch):
    repo, _ = _repo_and_worktree(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    assert gate.repo_key(str(repo)) == os.path.realpath(repo / ".git")


def test_s47_no_git_tree_keys_on_the_repo(w, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert gate.repo_key(str(plain)) == os.path.realpath(plain)


@pytest.mark.parametrize("how", [OSError("no git"), subprocess.TimeoutExpired("git", 5),
                                 ValueError("bad"), "rc", "empty"])
def test_s47_git_failing_keys_on_the_repo_and_never_raises(tmp_path, monkeypatch, how):
    def run(*a, **kw):
        if isinstance(how, BaseException):
            raise how
        return subprocess.CompletedProcess(a, 128 if how == "rc" else 0, stdout="\n", stderr="")
    monkeypatch.setattr(gate.subprocess, "run", run)
    assert gate.repo_key(str(tmp_path)) == os.path.realpath(tmp_path)


def test_s47_an_entry_with_no_key_reads_its_repo(w):
    a = w.put_in("r", "a")
    q = w.root / "gate" / "queue" / f"{a['id']}.json"
    old = {k: v for k, v in a.items() if k != "key"}
    q.write_text(json.dumps(old))
    e = gate.entries(w.root)[0]
    assert "key" not in e and gate.entry_key(e) == os.path.realpath(w.dir("r"))
    assert gate.entry_key({"key": "", "repo": "/r/x"}) == os.path.realpath("/r/x")
    assert gate.entry_key({"key": 7, "repo": "/r/x"}) == os.path.realpath("/r/x")
    assert isinstance(gate.entry_key({"id": "x"}), str)            # never raises
    assert isinstance(gate.entry_key({"repo": "a\0b"}), str)
    b = w.put_in("r", "b")
    w.plan = {"a": (30, 0), "b": (1, 0)}
    gate.serve(w.root, w.fx())
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"] and w.peak == 1


# ---- rulings 1 to 3: the choice ------------------------------------------------

def test_s47_two_repos_run_together(w):
    w.plan = {"a": (120, 0), "b": (120, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    assert gate.serve(w.root, w.fx()) == 0
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert rb["started"] < ra["ended"] and w.peak == 2
    assert (ra["exit"], rb["exit"], ra["seconds"], rb["seconds"]) == (0, 0, 120, 120)
    assert gate.entries(w.root) == []


def test_s47_one_key_is_one_running(w):
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("one", "b")
    gate.serve(w.root, w.fx())
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"] and w.peak == 1


def test_s47_one_key_stays_fifo_past_a_lock(w, tmp_path):
    lock = tmp_path / "held.lock"
    lock.mkdir()
    w.plan = {"h": (5, 0), "y": (5, 0), "z": (5, 0)}
    h, y = w.put_in("one", "h", locks=[str(lock)], wall=600), w.put_in("one", "y")
    z = w.put_in("two", "z")

    def free(world):
        if world.t >= T0 + 30 and lock.exists():
            lock.rmdir()
    w.hooks.append(free)
    gate.serve(w.root, w.fx())
    assert w.order() == ["z", "h", "y"]      # z's key is free; y never passes h
    assert w.result(z["id"])["started"] == T0
    assert w.result(h["id"])["started"] >= T0 + 30
    assert w.result(y["id"])["started"] >= w.result(h["id"])["ended"]


def test_s47_a_younger_unlocked_entry_of_another_key_may_pass(w, tmp_path):
    lock = tmp_path / "held.lock"
    lock.mkdir()
    w.plan = {"h": (1, 0), "z": (1, 0)}
    h, z = w.put_in("one", "h", locks=[str(lock)], wall=30), w.put_in("two", "z")
    gate.serve(w.root, w.fx())
    assert w.order() == ["z"]
    assert w.result(h["id"])["exit"] == 126 and w.result(z["id"])["exit"] == 0


def test_s47_a_shared_lock_is_exclusive_across_keys(w, tmp_path):
    lock = str(tmp_path / "tlc.lock")                 # never made: the running entry names it
    w.plan = {"a": (200, 0), "b": (10, 0), "c": (10, 0)}
    a, b = w.put_in("one", "a", locks=[lock]), w.put_in("two", "b", locks=[lock])
    c = w.put_in("three", "c")
    gate.serve(w.root, w.fx())
    ra, rb, rc = w.result(a["id"]), w.result(b["id"]), w.result(c["id"])
    assert rb["started"] >= ra["ended"]
    assert rc["started"] < ra["ended"]                # a free key ran beside it
    assert w.order() == ["a", "c", "b"]


def test_s47_a_lock_a_running_entry_names_is_not_a_held_lock(w, tmp_path):
    # The running command makes its lock; the entry behind it waits on that entry, whose own
    # wall bounds it, so its wall does not tick and it is never cut 126.
    lock = tmp_path / "tlc.lock"
    w.plan = {"a": (300, 0), "b": (1, 0)}
    a = w.put_in("one", "a", locks=[str(lock)])
    b = w.put_in("two", "b", locks=[str(lock)], wall=30)

    def tlc(world):
        if gate.result_path(world.root, a["id"]).exists():
            if lock.exists():
                lock.rmdir()
        elif not lock.exists() and world.spawned:
            lock.mkdir()
    w.hooks.append(tlc)
    gate.serve(w.root, w.fx())
    assert (w.result(a["id"])["exit"], w.result(b["id"])["exit"]) == (0, 0)
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"]


def test_s47_an_entry_behind_its_key_does_not_tick_its_lock_wall(w, tmp_path):
    # As S38's: an entry that could not start anyway is not waiting on the lock.
    lock = tmp_path / "held.lock"
    w.plan = {"a": (300, 0), "b": (1, 0)}
    a, b = w.put_in("one", "a"), w.put_in("one", "b", locks=[str(lock)], wall=30)

    def held(world):
        if world.t < T0 + 200 and not lock.exists() and world.spawned:
            lock.mkdir()
        elif world.t >= T0 + 300 and lock.exists():
            lock.rmdir()
    w.hooks.append(held)
    gate.serve(w.root, w.fx())
    assert w.result(b["id"])["exit"] == 0
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"]


def test_s47_a_held_lock_with_a_free_key_is_cut_past_its_wall_beside_a_runner(w, tmp_path):
    lock = tmp_path / "held.lock"
    lock.mkdir()
    w.plan = {"a": (300, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b", locks=[str(lock)], wall=30)
    gate.serve(w.root, w.fx())
    rb = w.result(b["id"])
    assert (rb["exit"], rb["cut"]) == (126, "lock wait cut") and rb["ended"] - T0 <= 32
    assert w.result(a["id"])["exit"] == 0


# ---- ruling 4: the ceiling -----------------------------------------------------

def test_s47_above_the_ceiling_is_serial(w):
    w.load = 12.0                                     # 0.75 x 16; "under" is strict
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    gate.serve(w.root, w.fx())
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"] and w.peak == 1


def test_s47_nothing_running_starts_whatever_the_load(w, tmp_path):
    w.load = 99.0
    w.plan = {"a": (10, 0)}
    a = w.put_in("one", "a")
    gate.serve(w.root, w.fx())
    assert w.result(a["id"])["started"] == T0
    (tmp_path / "again").mkdir()
    w2 = W(tmp_path / "again")

    def boom():
        raise OSError("no load")
    w2.plan = {"a": (10, 0)}
    a2 = w2.put_in("one", "a")
    gate.serve(w2.root, w2.fx(load=boom))
    assert w2.result(a2["id"])["started"] == T0


def test_s47_settle_between_starts(w):
    w.plan = {"a": (500, 0), "b": (10, 0), "c": (10, 0)}
    a, b, c = w.put_in("one", "a"), w.put_in("two", "b"), w.put_in("three", "c")
    gate.serve(w.root, w.fx())
    ra, rb, rc = w.result(a["id"]), w.result(b["id"]), w.result(c["id"])
    assert rb["started"] - ra["started"] == 60
    assert rc["started"] - rb["started"] == 60        # b ended at 70: the last start counts


def test_s47_a_command_that_cannot_start_is_not_a_start(w):
    w.plan = {"a": (500, 0), "bad": OSError("no such program"), "c": (1, 0)}
    a, bad, c = w.put_in("one", "a"), w.put_in("two", "bad"), w.put_in("three", "c")
    gate.serve(w.root, w.fx())
    assert w.result(bad["id"])["exit"] == 127
    assert w.result(bad["id"])["started"] - T0 == 60
    assert w.result(c["id"])["started"] - T0 == 60     # the failed start set no settle
    assert w.result(a["id"])["exit"] == 0


def test_s47_max_running(w):
    w.plan = {x: (1000, 0) for x in "abcd"}
    d = [w.put_in(n, x) for n, x in zip(("r1", "r2", "r3", "r4"), "abcd")]
    gate.serve(w.root, w.fx())
    assert w.peak == 3
    assert w.result(d[3]["id"])["started"] >= T0 + 1000
    assert gate.MAX_RUNNING == 3


def test_s47_a_failed_load_read_is_over(w):
    def boom():
        raise OSError("no load")
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    gate.serve(w.root, w.fx(load=boom))
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"] and w.peak == 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, None, "2", True])
def test_s47_a_load_that_is_no_number_is_over(w, bad):
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    gate.serve(w.root, w.fx(load=lambda: bad))
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"]


def test_s47_the_ceiling_defaults_to_three_quarters_of_the_cores(w):
    assert gate._ceiling({}, w.fx()) == 12.0
    w.cores = 4
    assert gate._ceiling({}, w.fx()) == 3.0
    assert gate._ceiling({"load_ceiling": 2.5}, w.fx()) == 2.5
    assert gate._ceiling({}, w.fx(cores=lambda: None)) == 0.75


# ---- ruling 8: the config ------------------------------------------------------

def test_s47_the_config_sets_both_keys(w):
    w.user("gate:\n  load_ceiling: 5.5\n  max_running: 2\n")
    env = {"HOME": str(w.home)}
    assert resolver.gate_config(env)["load_ceiling"] == 5.5
    assert resolver.gate_config(env)["max_running"] == 2
    w.plan = {x: (1000, 0) for x in "abc"}
    for n, x in zip(("r1", "r2", "r3"), "abc"):
        w.put_in(n, x)
    gate.serve(w.root, w.fx())
    assert w.peak == 2


def test_s47_the_config_ceiling_holds_a_second_start(w):
    w.user("gate:\n  load_ceiling: 1\n")
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    gate.serve(w.root, w.fx())
    assert w.result(b["id"])["started"] >= w.result(a["id"])["ended"]


@pytest.mark.parametrize("text", [
    "load_ceiling: lots", "load_ceiling: 0", "load_ceiling: -2", "load_ceiling: true",
    "load_ceiling: .inf", "load_ceiling: .nan", "max_running: 0", "max_running: 2.5",
    "max_running: true", "max_running: many"])
def test_s47_a_bad_value_reads_as_the_default_and_one_log_line(w, text):
    w.user(f"gate:\n  {text}\n")
    key = text.split(":")[0]
    env = {"HOME": str(w.home)}
    lines = []
    cfg = resolver.gate_config(env, lines.append)
    assert key not in cfg and len(lines) == 1 and key in lines[0]
    assert resolver.gate_config(env) == {"ntfy_url": None, "ntfy_topic": None, "wall": 5400}
    w.put_in("one", "a")
    gate.serve(w.root, w.fx())
    assert len([x for x in w.logs if key in x]) == 1


# ---- ruling 5: the runner's set ------------------------------------------------

def test_s47_a_wall_cut_leaves_the_other_running(w):
    # a is cut at 100, its grace runs to 105; b ends at 102, inside it, to the second.
    w.plan = {"a": (None, 0), "b": (42, 0)}
    a, b = w.put_in("one", "a", wall=100), w.put_in("two", "b")
    gate.serve(w.root, w.fx())
    ra, rb = w.result(a["id"]), w.result(b["id"])
    pa, pb = w.spawned[0][2].pid, w.spawned[1][2].pid
    assert w.kills == [(pa, signal.SIGTERM), (pa, signal.SIGKILL)]
    assert all(pg != pb for pg, _ in w.kills)
    assert (ra["exit"], ra["cut"], rb["exit"], rb["cut"]) == (124, "wall cut", 0, None)
    assert rb["seconds"] == 42 and rb["ended"] == T0 + 102
    assert rb["ended"] < ra["ended"]


def test_s47_a_start_goes_on_during_a_cut(w):
    # b starts at 60 and c at 120, inside a's grace (118 to 123): the cut holds no start.
    w.plan = {"a": (None, 0), "b": (300, 0), "c": (1, 0)}
    a, b, c = w.put_in("one", "a", wall=118), w.put_in("two", "b"), w.put_in("three", "c")
    gate.serve(w.root, w.fx())
    assert w.result(c["id"])["started"] == T0 + 120
    assert w.result(a["id"])["exit"] == 124


def test_s47_each_child_keeps_its_log_result_inbox_and_ntfy(w):
    w.ntfy()
    w.plan = {"a": (100, 0), "b": (70, 3)}
    a = w.put_in("one", "a", caller="sess-a")
    b = w.put_in("two", "b", caller="sess-b")
    gate.serve(w.root, w.fx())
    for e, first, code in ((a, "a", 0), (b, "b", 3)):
        r = w.result(e["id"])
        assert r["exit"] == code
        with open(r["log"]) as fh:
            lines = fh.read().splitlines()
        assert lines[0] == f"gate {e['id']}: {e['repo']}: {first} x"
        assert f"out of {first}" in lines and lines[-1].startswith(f"gate {e['id']}: exit {code} in")
    assert (w.root / "sessions" / "sess-a" / "inbox" / f"{a['id']}.json").exists()
    assert (w.root / "sessions" / "sess-b" / "inbox" / f"{b['id']}.json").exists()
    assert len(w.posts) == 2
    assert all(s[1]["start_new_session"] is True for s in w.spawned)


def test_s47_runner_json_lists_the_set(w):
    seen = []

    def peek(world):
        r = gate.runner_info(world.root)
        if r:
            seen.append(r)
    w.hooks.append(peek)
    w.plan = {"a": (100, 0), "b": (100, 0)}
    a, b = w.put_in("one", "a"), w.put_in("two", "b")
    gate.serve(w.root, w.fx())
    assert all(list(s) == list(gate.RUNNER_KEYS) == ["pid", "since", "running"] for s in seen)
    pa, pb = w.spawned[0][2].pid, w.spawned[1][2].pid
    assert {"id": a["id"], "pgid": pa} in seen[0]["running"]
    assert any(s["running"] == [{"id": a["id"], "pgid": pa}, {"id": b["id"], "pgid": pb}]
               for s in seen)
    assert any(s["running"] == [{"id": b["id"], "pgid": pb}] for s in seen)
    assert any(s["running"] == [] for s in seen)
    assert all(s["pid"] == 777 for s in seen)


def test_s47_the_idle_exit_waits_for_the_set(w):
    a = w.put_in("one", "a")
    w.plan = {"a": (500, 0)}

    def vanish(world):
        if world.t >= T0 + 10:
            q = world.root / "gate" / "queue" / f"{a['id']}.json"
            if q.exists():
                q.unlink()
    w.hooks.append(vanish)
    gate.serve(w.root, w.fx(idle=60.0))
    assert w.result(a["id"])["exit"] == 0 and w.t >= T0 + 500


def test_s47_position_lists_the_entries_not_running(w):
    a, b, c = w.put_in("one", "a"), w.put_in("two", "b"), w.put_in("three", "c")
    _live_runner(w, [{"id": a["id"], "pgid": 1}, {"id": b["id"], "pgid": 2}])
    assert gate.position(w.root, a["id"]) == 0
    assert gate.position(w.root, c["id"]) == 1


def test_s47_recover_kills_each_of_the_set(w):
    a, b, c = (w.put_in("one", "a", caller="sess-1"), w.put_in("two", "b"),
               w.put_in("three", "c"))
    (w.root / "gate" / c["id"]).mkdir()
    (w.root / "gate" / c["id"] / "result.json").write_text(json.dumps({"id": c["id"], "exit": 0}))
    _dead_runner(w, [{"id": a["id"], "pgid": 4242}, {"id": b["id"], "pgid": 4343},
                     {"id": c["id"], "pgid": 4444}])
    assert gate.serve(w.root, w.fx()) == 0
    assert w.kills == [(4242, signal.SIGTERM), (4242, signal.SIGKILL),
                       (4343, signal.SIGTERM), (4343, signal.SIGKILL),
                       (4444, signal.SIGTERM), (4444, signal.SIGKILL)]
    for e in (a, b):
        r = w.result(e["id"])
        assert (r["exit"], r["cut"]) == (125, "runner died")
    assert w.result(c["id"])["exit"] == 0             # its result stands
    assert w.spawned == [] and gate.entries(w.root) == []
    assert (w.root / "sessions" / "sess-1" / "inbox" / f"{a['id']}.json").exists()
    assert not (w.root / "gate" / "runner.json").exists()


def test_s47_recover_reads_the_old_single_form(w):
    a = w.put_in("one", "a")
    _dead_runner(w, a["id"], pgid=4242)
    assert gate.serve(w.root, w.fx()) == 0
    assert w.kills == [(4242, signal.SIGTERM), (4242, signal.SIGKILL)]
    assert w.result(a["id"])["exit"] == 125 and w.spawned == []


@pytest.mark.parametrize("junk", [None, [], "nonsense", 7, ["x"], [{"id": "../../etc"}], [{}],
                                  [{"id": 3, "pgid": 4}], {"id": "x"}])
def test_s47_recover_skips_what_it_cannot_read(w, junk):
    _dead_runner(w, junk, pgid=4242)
    assert gate.serve(w.root, w.fx()) == 0
    assert w.kills == [] and not (w.root / "gate" / "runner.json").exists()


def test_s47_recover_with_no_group_still_closes_the_entry(w):
    a = w.put_in("one", "a")
    _dead_runner(w, [{"id": a["id"]}])
    assert gate.serve(w.root, w.fx()) == 0
    assert w.kills == [] and w.result(a["id"])["exit"] == 125


# ---- status --------------------------------------------------------------------

def test_s47_status_names_each_wait(w, tmp_path):
    lock = tmp_path / "held.lock"
    lock.mkdir()
    run = w.put_in("one", "r", label="the long one")
    bykey = w.put_in("one", "k")
    bylock = w.put_in("two", "l", locks=[str(lock)])
    byload = w.put_in("three", "n")
    _live_runner(w, [{"id": run["id"], "pgid": 1}])
    w.load = 20.54
    st = gate.status(w.root, T0, fx=w.fx())
    lines = gate.status_lines(st)
    assert lines[0].startswith(f"running {run['id']} {run['repo']} since ")
    assert lines[0].endswith(" the long one")
    assert lines[1:4] == [
        f"queued {bykey['id']} {bykey['repo']} position 1 waits on key one",
        f"queued {bylock['id']} {bylock['repo']} position 2 waits on lock {lock}",
        f"queued {byload['id']} {byload['repo']} position 3 waits on load 20.5 over 12"]


def test_s47_status_names_a_lock_a_running_entry_holds(w, tmp_path):
    lock = str(tmp_path / "tlc.lock")
    run, q = w.put_in("one", "r", locks=[lock]), w.put_in("two", "q", locks=[lock])
    _live_runner(w, [{"id": run["id"], "pgid": 1}])
    lines = gate.status_lines(gate.status(w.root, T0, fx=w.fx()))
    assert lines[1] == f"queued {q['id']} {q['repo']} position 1 waits on lock {lock}"


def test_s47_status_says_a_failed_load_read(w):
    def boom():
        raise OSError("no load")
    run, q = w.put_in("one", "r"), w.put_in("two", "q")
    _live_runner(w, [{"id": run["id"], "pgid": 1}])
    lines = gate.status_lines(gate.status(w.root, T0, fx=w.fx(load=boom)))
    assert lines[1] == f"queued {q['id']} {q['repo']} position 1 waits on load ? over 12"


def test_s47_status_says_the_set_is_full_and_the_settle(w):
    es = [w.put_in(n, "r") for n in ("r1", "r2", "r3")]
    q = w.put_in("r4", "q")
    _live_runner(w, [{"id": e["id"], "pgid": 1} for e in es])
    lines = gate.status_lines(gate.status(w.root, T0, fx=w.fx()))
    assert lines[3] == f"queued {q['id']} {q['repo']} position 1 waits on running 3 of 3"
    _live_runner(w, [{"id": es[0]["id"], "pgid": 1}], at=T0 - 20)
    lines = gate.status_lines(gate.status(w.root, T0, fx=w.fx()))
    assert lines[1].endswith("waits on settle 40 s")


def test_s47_status_with_a_free_entry_says_no_wait(w):
    q = w.put_in("one", "q")
    st = gate.status(w.root, T0, fx=w.fx())
    assert gate.status_lines(st)[0] == f"queued {q['id']} {q['repo']} position 1"
    assert st["queued"][0]["wait"] is None and st["running"] == []


def test_s47_status_json_running_is_a_list(w):
    a, b = w.put_in("one", "a", label="x"), w.put_in("two", "b")
    (w.root / "gate" / a["id"]).mkdir()
    at = T0 - 500
    os.utime(w.root / "gate" / a["id"], (at, at))
    _live_runner(w, [{"id": a["id"], "pgid": 1}, {"id": b["id"], "pgid": 2}], at=T0 - 7)
    st = gate.status(w.root, T0, fx=w.fx())
    assert [x["id"] for x in st["running"]] == [a["id"], b["id"]]
    assert list(st["running"][0]) == ["id", "repo", "label", "since", "seconds"]
    assert (st["running"][0]["since"], st["running"][0]["seconds"]) == (at, 500)
    assert st["running"][1]["since"] == T0 - 7          # no directory yet: the runner's file
    assert st["queued"] == []
    assert json.loads(json.dumps(st)) == st


def test_s47_status_reads_a_live_old_runner(w):
    a, b = w.put_in("one", "a"), w.put_in("one", "b")
    _live_runner(w, a["id"])
    st = gate.status(w.root, T0, fx=w.fx())
    assert [x["id"] for x in st["running"]] == [a["id"]]
    assert [x["id"] for x in st["queued"]] == [b["id"]]


def test_s47_the_key_name_is_the_repos_not_dot_git():
    assert gate.key_name("/x/foo/.git") == "foo"
    assert gate.key_name("/x/foo") == "foo"
    assert gate.key_name("/x/foo.git") == "foo.git"


# ---- the intake's acceptance, and one real pair ---------------------------------

def test_s47_client_gate_behind_a_long_gate_starts_at_once(w):
    # The readings: a two-minute gate waited 64 minutes behind a 96-minute one.
    w.load = 8.0                                      # under the ceiling, 12 on 16 cores
    w.plan = {"long": (96 * 60, 0), "client": (60, 0)}
    long_, client = w.put_in("big", "long", wall=9000), w.put_in("small", "client")
    gate.serve(w.root, w.fx())
    rl, rc = w.result(long_["id"]), w.result(client["id"])
    assert rc["started"] - rl["started"] == gate.START_SETTLE == 60
    assert rc["ended"] < T0 + 5 * 60 < rl["ended"]
    assert (rl["exit"], rc["exit"]) == (0, 0)


def test_s47_two_real_children_each_keep_their_own_log(tmp_path):
    w = W(tmp_path)
    clock = [T0]

    def sleep(s):
        clock[0] += 60.0                               # past the settle at the first poll
        time.sleep(0.01)
    a = gate.enqueue(w.root, w.dir("one"), ["sh", "-c", "echo from-one"], ENV, [], 60, "", None, T0)
    b = gate.enqueue(w.root, w.dir("two"), ["sh", "-c", "echo from-two; exit 4"], ENV, [], 60,
                     "", None, T0)
    fx = gate.Fx(now=lambda: clock[0], sleep=sleep, popen=subprocess.Popen, killpg=w.killpg,
                 post=w.post, log=w.logs.append, env={"HOME": str(w.home)}, idle=0.0,
                 poll=0.01, grace=0.01, load=lambda: 1.0, cores=lambda: 16)
    assert gate.serve(w.root, fx) == 0
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert (ra["exit"], rb["exit"]) == (0, 4)
    with open(ra["log"]) as fh:
        one = fh.read()
    with open(rb["log"]) as fh:
        two = fh.read()
    assert "from-one" in one and "from-two" not in one
    assert "from-two" in two and "from-one" not in two
