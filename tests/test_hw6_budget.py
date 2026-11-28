"""Packet hw6-budget (design/34 items 8 to 10 and 15): a class for each job, its peak, a budget
of cores and memory, three bounded guards, the grant in the job's environment, an unreadable
gate told from an empty one, and the switch. Each group is red at 047c161a (alpha.188). Every
queue and runner is under the test's temp roots; the snapshot, the clock, the load and the
samples are passed in, and none is this machine's."""
import json
import os
import random

import pytest

from claude_session import cli, gate, land, machine, resolver

from conftest import calm_snapshot
from test_gate import ENV
from test_s47 import T0, W


@pytest.fixture
def w(tmp_path):
    return W(tmp_path)


def put(w, name, first, wall=5400, **cls):
    return gate.enqueue(w.root, w.dir(name), [first, "x"], ENV, [], wall, "", None, w.t, **cls)


def snap_of(**over):
    return lambda paths: calm_snapshot(**over)


def eight(**over):
    """A machine of 8 cores and 16 GB (12 GB after the reserve)."""
    return snap_of(**{"cores": {"total": 8},
                      "memory": {"total_mb": 16384, "free_mb": 9000, "pressure": "normal"}, **over})


# ---- B1: the class -------------------------------------------------------------------------

def test_b1_the_flags_give_the_class_and_a_jvm_heap_is_granted_a_quarter_more(w):
    e = put(w, "one", "a", cpu=2, mem_mb=1000)
    assert {k: e[k] for k in ("cpu", "mem_mb")} == {"cpu": 2, "mem_mb": 1000} and "jvm" not in e
    j = put(w, "two", "tlc", cpu=1, mem_mb=8000, jvm=True)
    assert (j["cpu"], j["mem_mb"], j["jvm"]) == (1, 10000, True)
    body = json.loads((gate._queue(w.root) / f"{j['id']}.json").read_text())
    assert list(body)[-3:] == ["cpu", "mem_mb", "jvm"]


def test_b1_the_profile_s_first_match_then_the_history_then_the_default(w):
    classes = [{"repo": "nothing-*", "command": "*", "cpu": 9, "mem_mb": 9},
               {"repo": "one", "command": "make check*", "cpu": 8, "mem_mb": 6000},
               {"repo": "*", "command": "make check", "cpu": 7, "mem_mb": 7}]
    real = os.path.realpath(w.dir("one"))
    assert gate.job_class(w.root, real, ["/usr/bin/make", "check"], classes) == \
        {"cpu": 8, "mem_mb": 6000}
    assert gate.job_class(w.root, real, ["go", "test"], classes) == machine.DEFAULT_CLASS
    for i, (cpu_s, secs, peak) in enumerate(((50.0, 10.0, 1000), (9.0, 10.0, 2400), (1, 1, None))):
        d = gate.entry_dir(w.root, f"20270101-00000{i}-{i + 1}")
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({
            "repo": real, "command": ["go", "test"], "cpu_seconds": cpu_s, "seconds": secs,
            "peak_mb": peak}))
    assert gate.job_class(w.root, real, ["go", "test"], classes) == {"cpu": 5, "mem_mb": 3000}
    assert gate.job_class(w.root, real, ["go", "test"], classes, cpu=2) == \
        {"cpu": 2, "mem_mb": 3000}


def test_b1_a_light_job_and_an_older_entry(w):
    e = gate.enqueue(w.root, w.dir("one"), ["lint"], ENV, [], 60, "", None, w.t, light=True)
    assert (e["cpu"], e["mem_mb"]) == (1, 512)
    e2 = gate.enqueue(w.root, w.dir("two"), ["lint"], ENV, [], 60, "", None, w.t, light=True,
                      cpu=2)
    assert (e2["cpu"], e2["mem_mb"]) == (2, 512)
    assert gate.entry_class({"id": "x"}) == machine.DEFAULT_CLASS
    assert gate.entry_class({"light": True, "cpu": "2"}) == machine.LIGHT_CLASS


def test_b1_the_verb_s_flags_and_the_profile_s_classes(w):
    args = cli.build_parser().parse_args(
        ["gate", "run", ".", "--cpu", "2", "--mem", "100", "--jvm", "--", "x"])
    assert (args.cpu, args.mem, args.jvm) == (2, 100, True)
    w.user("gate:\n  classes:\n    - {repo: one, command: 'make *', cpu: 6, mem_mb: 3000}\n"
           "  budget: observe\n")
    cfg = resolver.gate_config({"HOME": str(w.home)})
    assert cfg["classes"] == [{"repo": "one", "command": "make *", "cpu": 6, "mem_mb": 3000}]
    assert cfg["budget"] == "observe"
    said = []
    w.user("gate:\n  classes:\n    - {repo: one, cpu: 0}\n  budget: maybe\n")
    cfg = resolver.gate_config({"HOME": str(w.home)}, said.append)
    assert "classes" not in cfg and "budget" not in cfg and len(said) == 2


# ---- B2: the peak --------------------------------------------------------------------------

def test_b2_the_peak_is_the_largest_group_sum_sampled_and_a_failed_sample_is_skipped(w):
    seen = iter([{4000: 300}, RuntimeError("ps"), {4000: 900}, {4000: 100}] + [{}] * 50)

    def sample(pgids):
        x = next(seen)
        if isinstance(x, Exception):
            raise x
        return x
    w.plan = {"a": (45, 0), "b": (5, 0)}
    a = put(w, "one", "a")
    gate.serve(w.root, w.fx(sample=sample))
    r = w.result(a["id"])
    assert r["peak_mb"] == 900 and list(r)[-6:] == list(gate.MEASURE_KEYS)
    b = put(w, "two", "b")
    gate.serve(w.root, w.fx(sample=lambda pgids: {}))
    assert w.result(b["id"])["peak_mb"] is None


def test_b2_the_sampler_sums_a_group_and_never_raises():
    class P(machine.Probe):
        def __init__(self, out):
            self.out = out

        def run(self, argv, timeout=machine.RUN_BOUND, cwd=None, env=None):
            assert argv[:2] == ["ps", "-A"]
            return self.out
    text = " 10 2048\n10 1024\n 11 500\n junk line\n"
    assert machine.group_rss_mb([10, 11, 12], P((0, text))) == {10: 3, 11: 0}
    assert machine.group_rss_mb([10], P(None)) == {}
    assert machine.group_rss_mb([True, -1, "x"], P((0, text))) == {}


# ---- B3: the budget ------------------------------------------------------------------------

def test_b3_a_class_waits_for_what_is_not_granted(w):
    w.plan = {"a": (500, 0), "b": (500, 0), "c": (10, 0)}
    a, b, c = (put(w, n, x, cpu=4) for n, x in (("one", "a"), ("two", "b"), ("three", "c")))
    gate.serve(w.root, w.fx(snapshot=eight()))
    ra, rb, rc = (w.result(e["id"]) for e in (a, b, c))
    assert rb["started"] == T0 + 60 and rc["started"] == ra["ended"]
    assert (rc["cpu"], rc["mem_mb"]) == (4, 2048)


def test_b3_the_reserve_is_a_quarter_and_at_least_4096_mb():
    def mem(total):
        s = calm_snapshot(memory={"total_mb": total, "pressure": "normal"})
        return machine.budget(s, [])["mem_mb"]
    assert (mem(131072), mem(8192), mem(2048)) == (98304, 4096, 0)


def test_b3_a_class_over_the_budget_is_granted_the_whole_and_runs_alone(w):
    w.plan = {"a": (100, 0), "big": (100, 0)}
    a, big = put(w, "one", "a", cpu=2), put(w, "two", "big", cpu=64, mem_mb=10 ** 6)
    gate.serve(w.root, w.fx(snapshot=eight()))
    rb = w.result(big["id"])
    assert rb["started"] >= w.result(a["id"])["ended"]
    assert (rb["cpu"], rb["mem_mb"]) == (8, 12288)


def test_b3_an_entry_held_ten_minutes_is_not_passed(w):
    w.plan = {"a": (900, 0), "big": (10, 0), "c": (900, 0), "d": (10, 0)}
    a, big = put(w, "one", "a", cpu=4), put(w, "two", "big", cpu=8)
    c, d = put(w, "three", "c", cpu=4), put(w, "four", "d", cpu=2)
    gate.serve(w.root, w.fx(snapshot=eight()))
    ra, rb, rc, rd = (w.result(e["id"]) for e in (a, big, c, d))
    assert rc["started"] == T0 + 60                   # before ten minutes a smaller one passes
    assert rb["started"] == rc["ended"]               # after them, none: d had room at a's end
    assert rd["started"] > rb["started"] > ra["ended"]


# ---- B4: the guards ------------------------------------------------------------------------

def test_b4_the_pressure_guard_holds_to_its_bound_and_the_result_names_it(w):
    w.user("gate:\n  pressure_hold_max: 300\n")
    w.plan = {"a": (10, 0)}
    a = put(w, "one", "a")
    gate.serve(w.root, w.fx(snapshot=snap_of(memory={"total_mb": 65536, "pressure": "warn"})))
    r = w.result(a["id"])
    assert r["started"] == T0 + 300 and r["over"] == "pressure" and "guard_unread" not in r
    assert "over: pressure; " in gate.wait_line(r)


def test_b4_the_disk_guard_reads_the_job_s_volume_and_status_names_the_largest(w):
    low = [{"mount": "/", "free_gb": 10.0, "holds": ["job"]},
           {"mount": "/other", "free_gb": 900.0, "holds": ["home"]}]
    w.plan = {"a": (10, 0)}
    a = put(w, "one", "a")
    stops, asked = [], []

    def largest(folder):                              # fix 1, F4: the reader's, not the runner's
        asked.append(folder)
        return "largest /x/cache 40 GB (idle)"

    def peek(world):
        if not stops and gate.result_path(w.root, a["id"]).exists() is False:
            st = gate.status(w.root, w.t, alive=lambda pid: True, fx=w.fx(), largest=largest)
            stops.append(gate.status_lines(st))
    w.hooks.append(peek)
    gate.serve(w.root, w.fx(snapshot=snap_of(disks=low)))
    r = w.result(a["id"])
    assert r["started"] == T0 + gate.HOLD_MAX and r["over"] == "disk"
    assert f"waits on 10 GB free, under the floor of 25; largest /x/cache 40 GB (idle) " \
           f"since {gate._hm(T0)}" in stops[0][0]
    assert asked == [a["repo"]]
    fine = [{"mount": "/", "free_gb": 5.0, "holds": ["home"]},
            {"mount": "/w", "free_gb": 100.0, "holds": ["job"]}]
    b = put(w, "two", "a")
    gate.serve(w.root, w.fx(snapshot=snap_of(disks=fine)))
    assert "over" not in w.result(b["id"])


def test_b4_a_guard_unread_holds_nothing_and_is_named(w):
    w.plan = {"a": (10, 0)}
    a = put(w, "one", "a")
    gate.serve(w.root, w.fx(snapshot=snap_of(memory={"total_mb": 65536, "pressure": "unknown"},
                                             disks=[])))
    r = w.result(a["id"])
    assert r["started"] == T0 and r["guard_unread"] == "pressure, disk"
    assert "guard unread: pressure, disk; " in gate.wait_line(r)
    b = put(w, "two", "a")
    gate.serve(w.root, w.fx(snapshot=lambda paths: 1 / 0))
    assert w.result(b["id"])["guard_unread"] == "budget, pressure, disk"


@pytest.mark.parametrize("snap,state", [
    (calm_snapshot(load=[12.0, 0, 0]), "held"), (calm_snapshot(load=None), "unread"),
    (calm_snapshot(memory={"total_mb": 1, "pressure": "critical"}), "held"),
    (calm_snapshot(), "ok")])
def test_b4_machine_returns_each_part_apart(snap, state):
    parts = machine.budget(snap, [], {"load_ceiling": 12.0}, {"cpu": 1, "mem_mb": 1},
                           volume="job")["parts"]
    assert set(parts) == set(machine.PARTS)
    got = [p["state"] for p in parts.values() if p["state"] != "ok"]
    assert (got[0] if got else "ok") == state


# ---- B5: the grant -------------------------------------------------------------------------

def test_b5_the_grant_goes_down_and_a_set_gomaxprocs_stands(w):
    e = put(w, "one", "a", cpu=3, mem_mb=700)
    env = gate.grant_env({**e, "env": {**ENV, "GOMAXPROCS": "1"}})
    assert (env["AGENTIK_CPUS"], env["AGENTIK_MEM_MB"], env["GOMAXPROCS"]) == ("3", "700", "1")
    w.plan = {"a": (1, 0)}
    gate.serve(w.root, w.fx(snapshot=snap_of(cores={"total": 2})))
    kw = w.spawned[0][1]
    assert (kw["env"]["AGENTIK_CPUS"], kw["env"]["GOMAXPROCS"]) == ("2", "2")
    assert {k: v for k, v in kw["env"].items() if k not in gate.GRANT_ENV} == \
        {**ENV, gate.JOB_MARK: e["id"]}


def test_b5_a_check_kept_at_the_pin_still_proves_its_tree():
    before = land.env_digest({"PATH": "/bin", "A": "1"})
    now = land.env_digest({"PATH": "/bin", "A": "1", "AGENTIK_CPUS": "4",
                           "AGENTIK_MEM_MB": "2048", "GOMAXPROCS": "4"})
    assert before == now and land.env_differs(before, now) is None
    assert land.env_differs({**before, "GOMAXPROCS": "x"}, now) is None
    assert land.env_differs(before, {**now, "A": "2"}) == "A"


# ---- B6: unreadable is not empty -----------------------------------------------------------

def test_b6_a_gate_folder_at_mode_000_is_unreadable_not_empty(w):
    put(w, "one", "a")
    g = gate.gate_dir(w.root)
    os.chmod(g, 0)
    try:
        assert gate.status(w.root, T0)["queued"] == []           # the pin's read, kept
        with pytest.raises(gate.GateError):
            gate.status(w.root, T0, strict=True)
        running, queued, why = cli._machine_gate(w.root, T0)
        assert (running, queued) == (None, None) and "could not be read" in why
    finally:
        os.chmod(g, 0o700)
    assert cli._machine_gate(w.root, T0) == (0, 1, None)


# ---- B7: the switch ------------------------------------------------------------------------

def test_b7_observe_holds_nothing_new_and_says_what_would_have(w):
    w.user("gate:\n  budget: observe\n")
    w.plan = {"a": (100, 0), "b": (10, 0)}
    a, b = put(w, "one", "a", cpu=8), put(w, "two", "b", cpu=8)
    gate.serve(w.root, w.fx(snapshot=eight(
        memory={"total_mb": 16384, "pressure": "warn"})))
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert ra["started"] == T0 and rb["started"] == T0 + 60
    assert ra["would_hold"] == {"pressure": "memory pressure warn"}
    assert set(rb["would_hold"]) == {"budget", "pressure"}
    w.load = 99.0                                     # the load guard holds under both
    c = put(w, "three", "c")
    gate.serve(w.root, w.fx(snapshot=eight()))
    assert w.result(c["id"])["over"] == "load"


# ---- acceptance 2: no entry waits for good -------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_hold_ends_by_its_bound_or_the_queue_emptying(w, seed):
    rng = random.Random(seed)
    w.plan, es = {}, []
    for i in range(10):
        name = f"j{i}"
        w.plan[name] = (rng.choice((30, 120, 300)), 0)
        cls = rng.choice(({"cpu": 1}, {"cpu": 4}, {"cpu": 8, "mem_mb": 6000}, {}))
        if i == 5:
            cls = {"cpu": 64, "mem_mb": 10 ** 6}      # over the whole budget
        es.append(put(w, f"r{i % 5}", name, **cls))
    pressures = iter(rng.choice(("normal", "warn")) for _ in range(10 ** 6))
    disks = iter(rng.choice((10.0, 300.0)) for _ in range(10 ** 6))

    def snap(paths):
        return calm_snapshot(cores={"total": 8}, memory={"total_mb": 16384,
                                                         "pressure": next(pressures)},
                             disks=[{"mount": "/", "free_gb": next(disks), "holds": ["job"]}])
    w.load = 20.0
    assert gate.serve(w.root, w.fx(snapshot=snap)) == 0
    assert gate.entries(w.root) == []
    total = sum(s for s, _ in w.plan.values())
    for e in es:
        r = w.result(e["id"])
        assert r["exit"] == 0 and r["cut"] is None
        assert r["started"] - T0 <= total + gate.HOLD_MAX + len(es) * gate.START_SETTLE


@pytest.mark.parametrize("n,cfg", [(3, ""), (4, ""), (4, "gate:\n  load_hold_max: 300\n"
                                                     "  pressure_hold_max: 600\n"
                                                     "  disk_hold_max: 900\n")])
def test_a1_a_guard_s_bound_counts_from_the_queueing_in_one_key(w, n, cfg):
    """Fix 1, A1: one key's entries under a load, a pressure and a disk that never ease; each
    starts by the largest guard's bound from its queueing, or when its key frees after it."""
    if cfg:
        w.user(cfg)
    most = 900 if cfg else gate.HOLD_MAX
    w.plan = {f"j{i}": (300, 0) for i in range(n)}
    es = [put(w, "one", f"j{i}") for i in range(n)]
    w.load = 100.0
    gate.serve(w.root, w.fx(snapshot=snap_of(
        memory={"total_mb": 262144, "pressure": "warn"},
        disks=[{"mount": "/", "free_gb": 1.0, "holds": ["job"]}])))
    ended = None
    for e in es:
        r = w.result(e["id"])
        bound = max(e["queued"] + most, ended or 0)
        assert bound <= r["started"] <= bound + gate.START_SETTLE
        ended = r["ended"]
    assert w.result(es[0]["id"])["over"] == "load, pressure, disk"
    assert w.result(es[1]["id"])["started"] == w.result(es[0]["id"])["ended"]


# ---- fix 1: the review's blocks and the amended rulings ------------------------------------

def test_f1_f4_a_disk_hold_reads_no_consumer_in_the_runner_s_pass(w, monkeypatch):
    """F1: a job's wall is cut on time with four entries held by the disk; the runner reads
    no consumer (a `du` of up to 20 s each), the reader does."""
    def slow(*a, **k):
        w.t += 20.0
        return []
    monkeypatch.setattr(machine, "consumers", slow)
    monkeypatch.setattr(gate, "_largest", lambda root, folder: slow(), raising=False)
    w.load = 0.0
    w.plan = {"long": (None, 0), **{f"j{i}": (10, 0) for i in range(4)}}
    big = put(w, "r0", "long", wall=120)
    w.t += 0.5
    for i in range(4):
        put(w, f"r{i + 1}", f"j{i}")
    gate.serve(w.root, w.fx(snapshot=lambda paths: calm_snapshot(disks=[
        {"mount": "/", "free_gb": 1.0 if w.spawned else 500.0, "holds": ["job"]}])))
    r = w.result(big["id"])
    assert r["exit"] == 124 and r["ended"] - r["started"] <= 120 + gate.GRACE + 3 * gate.POLL


def test_f4_the_reader_names_the_largest_on_the_job_s_volume(tmp_path, monkeypatch):
    rows = [{"path": "/elsewhere", "gb": 300.0, "kind": "idle"},
            {"path": str(tmp_path), "gb": 17.0, "kind": "person"}]
    seen = []
    monkeypatch.setattr(machine, "consumers", lambda roots, **k: seen.append(roots) or rows)
    monkeypatch.setattr(cli, "_machine_roots", lambda env, root: {"repos": ["/r"]})
    monkeypatch.setattr(machine, "gocache", lambda probe: None)
    largest = cli._disk_largest({}, tmp_path)
    assert largest(str(tmp_path)) == f"largest {tmp_path} 17 GB (person)"
    assert largest(str(tmp_path)) and len(seen) == 1            # one read a call of the reader


def test_f2_a_rerun_is_not_held_by_the_load_guard(tmp_path):
    from test_gate import World
    from test_hw5_flake_rerun import HIGH, STOP, talking
    w = World(tmp_path)
    other = tmp_path / "repo2"
    other.mkdir()
    w.plan["a"], w.plan["b"] = (100, 1), (1200, 0)
    a = gate.enqueue(w.root, str(w.repo), ["a", "x"], ENV, [], 5400, "", "s1", w.t, rerun=True)
    b = gate.enqueue(w.root, str(other), ["b", "x"], ENV, [], 5400, "", None, w.t)
    gate.serve(w.root, w.fx(idle=0, popen=talking(w, {"a": STOP}), loads=HIGH,
                            load=lambda: 100.0, cores=lambda: 4))
    r1, rb = w.result(a["id"]), w.result(b["id"])
    assert r1["flake"] == gate.FLAKE and [x[0][0] for x in w.spawned] == ["a", "b", "a"]
    r2 = w.result(r1["rerun"])
    assert r2["started"] == rb["ended"] and r2["exit"] == 1 and "over" not in r2


def test_a2_a_light_entry_passes_the_load_and_not_the_pressure(w):
    w.load = 100.0
    w.plan = {"s": (5, 0)}
    s = gate.enqueue(w.root, w.dir("one"), ["s", "x"], ENV, [], 60, "", None, w.t, light=True)
    gate.serve(w.root, w.fx())
    assert w.result(s["id"])["started"] == T0 and "over" not in w.result(s["id"])
    t = gate.enqueue(w.root, w.dir("one"), ["s", "x"], ENV, [], 60, "", None, w.t, light=True)
    gate.serve(w.root, w.fx(snapshot=snap_of(memory={"total_mb": 65536, "pressure": "warn"})))
    assert w.result(t["id"])["over"] == "pressure"


def test_a3_a_landing_and_a_check_take_their_repo_s_check_class(w):
    repo = w.dir("one")
    land_cmd = [*gate.self_argv(), *gate.LAND_JOB, repo, "feature", "a" * 40, "/m"]
    check_cmd = [*gate.self_argv(), *gate.CHECK_JOB, repo]
    classes = [{"repo": "one", "command": "make check", "cpu": 12, "mem_mb": 9000}]
    for cmd in (land_cmd, check_cmd):
        assert gate.job_class(w.root, repo, cmd, classes) == {"cpu": 12, "mem_mb": 9000}
    gid = "20261128-000000-1"
    gate._mkdir(gate.result_path(w.root, gid).parent)
    gate._write_private(gate.result_path(w.root, gid), json.dumps(
        {"id": gid, "repo": repo, "key": gate.repo_key(repo), "command": check_cmd,
         "seconds": 100.0, "cpu_seconds": 750.0, "peak_mb": 4000}))
    assert gate.job_class(w.root, repo, land_cmd) == {"cpu": 8, "mem_mb": 5000}


def test_a4_the_held_caller_is_told_what_holds_it(w, capsys):
    e = put(w, "one", "a")
    gate._write_private(gate.gate_dir(w.root) / gate.HOLDS, json.dumps(
        {e["id"]: {"what": "load 14.50 at or over the ceiling 12.00", "since": T0}}))
    import unittest.mock as um
    with um.patch.object(gate, "wait", lambda root, gid, timeout=None: (1, None)):
        assert cli._gate_within_wait(w.root, e, 5) == gate.QUEUED
    line = capsys.readouterr().out.strip()
    assert line.startswith(f"queued {e['id']}, held by load 14.50 at or over the ceiling "
                           f"12.00 since {gate._hm(T0)}: write the id")


def test_a5_the_verb_reads_the_gate_s_grants_and_the_floor_is_under(w):
    w.plan = {"a": (100, 0)}
    a = put(w, "one", "a", cpu=6, mem_mb=3000)
    got = []
    w.hooks.append(lambda world: got.append(gate.running_grants(w.root, alive=lambda p: True)))
    gate.serve(w.root, w.fx())
    assert [{"cpu": 6, "mem_mb": 3000}] in got
    disk = lambda gb: machine.budget(calm_snapshot(disks=[{"mount": "/", "free_gb": gb,
                                                          "holds": ["job"]}]), [], {},
                                     {"cpu": 1, "mem_mb": 1}, volume="job")["parts"]["disk"]
    assert disk(25.0)["state"] == "ok" and disk(24.9)["state"] == "held"
    assert a["id"]


def test_f3_an_entry_and_a_runner_json_that_cannot_be_read_raise_under_strict(w):
    e = put(w, "one", "a")
    f = gate._queue(w.root) / f"{e['id']}.json"
    os.chmod(f, 0)
    try:
        assert gate.entries(w.root) == []                         # the pin's read, kept
        with pytest.raises(gate.GateError):
            gate.entries(w.root, strict=True)
        assert cli._machine_gate(w.root, T0)[:2] == (None, None)
    finally:
        os.chmod(f, 0o600)
    (gate.gate_dir(w.root) / "runner.json").write_text('{"pid": 1, "running": [{"id": "')
    assert gate.runner_info(w.root) is None
    with pytest.raises(gate.GateError):
        gate.runner_info(w.root, strict=True)
    f.write_text("{")
    assert cli._machine_gate(w.root, T0)[:2] == (None, None)


def test_f6_observe_names_each_reading_and_clamps_the_class(w):
    w.load = 0.0
    w.user("gate:\n  budget: observe\n")
    w.plan = {"a": (600, 0), "b": (600, 0), "c": (100, 0)}
    a, b = put(w, "one", "a", cpu=6, mem_mb=1000), put(w, "two", "b", cpu=6, mem_mb=1000)
    c = put(w, "three", "c", cpu=100, mem_mb=1000)
    gate.serve(w.root, w.fx(snapshot=eight()))
    rb, rc = w.result(b["id"]), w.result(c["id"])
    assert rb["would_hold"] == {"budget": "6 cores and 1000 MB asked, 2 and 11288 MB not granted"}
    assert (rc["cpu"], rc["mem_mb"]) == (8, 1000)
    env = next(kw["env"] for argv, kw, _ in w.spawned if argv[0] == "c")
    assert (env["AGENTIK_CPUS"], env["GOMAXPROCS"]) == ("8", "8")


def test_a5_fits_on_an_unreadable_gate_prints_the_hold_and_no_grant_ok(monkeypatch, capsys):
    monkeypatch.setattr(machine, "snapshot", lambda paths=None, **k: calm_snapshot())
    monkeypatch.setattr(cli, "_machine_roots", lambda env, root: {"home": "/h"})
    monkeypatch.setattr(cli, "_machine_gate", lambda root, now: (
        None, None, "the gate's state could not be read (x)"))
    assert cli.main(["machine", "fits", "--cpu", "1", "--mem", "100"]) == 75
    err = capsys.readouterr().err
    assert err.startswith("the gate's state could not be read (x)\n") and "grant: ok" not in err


# ---- fix 2 (review 2): H1 to H4 ------------------------------------------------------------

def _one_under_load(w, edit, back=0.0):
    w.load, w.cores, w.plan = 100.0, 16, {"j0": (300, 0)}
    e = put(w, "one", "j0")
    p = gate._queue(w.root) / f"{e['id']}.json"
    d = json.loads(p.read_text())
    edit(d)
    p.write_text(json.dumps(d))
    w.t -= back                                       # the clock steps back after the queueing
    t0 = w.t
    gate.serve(w.root, w.fx())
    r = w.result(e["id"])
    return r["started"] - t0, r.get("over")


@pytest.mark.parametrize("ahead, back", [(3600.0, 0.0), (0.0, 3600.0), (5.0, 0.0)])
def test_h1_a_queued_ahead_of_the_clock_holds_nothing(w, ahead, back):
    t = w.t
    assert _one_under_load(w, lambda d: d.update(queued=t + ahead), back) == (0, "load")


def test_h1_the_guard_s_bound_still_holds_an_entry_queued_now(w):
    t = w.t
    assert _one_under_load(w, lambda d: d.update(queued=t)) == (gate.HOLD_MAX, "load")


def test_h2_a_light_entry_passes_a_full_budget_and_the_ten_minutes(w):
    w.load = 0.0
    w.plan = {"a": (3000, 0), "b": (3000, 0), "c": (10, 0), "s": (20, 0)}
    a = put(w, "one", "a", cpu=4, mem_mb=1000)
    b = put(w, "two", "b", cpu=4, mem_mb=1000)
    w.t += 120
    c = put(w, "three", "c", cpu=4, mem_mb=1000)      # held by the budget, then `behind`
    w.t += 900
    s = put(w, "four", "s", wall=60, light=True)
    gate.serve(w.root, w.fx(snapshot=eight()))
    rs, rc = w.result(s["id"]), w.result(c["id"])
    assert rc["started"] >= a["queued"] + 3000
    assert rs["started"] - s["queued"] <= 2 * gate.START_SETTLE      # the pin's 120 s
    assert {k: rs[k] for k in gate.CLASS_KEYS} == machine.LIGHT_CLASS


def test_h2_a_light_job_running_is_not_counted_against_another_s_grant(w):
    w.load = 0.0
    w.plan = {"s": (100, 0), "a": (10, 0)}
    s = put(w, "one", "s", wall=120, light=True)
    a = put(w, "two", "a", cpu=8, mem_mb=1000)
    gate.serve(w.root, w.fx(snapshot=eight()))
    rs, ra = w.result(s["id"]), w.result(a["id"])
    assert rs["started"] == T0 and ra["started"] < rs["ended"]
    assert ra["cpu"] == 8 and {k: rs[k] for k in gate.CLASS_KEYS} == machine.LIGHT_CLASS


def test_h3_observe_names_no_guard_whose_bound_has_passed(w):
    w.load = 0.0
    w.user("gate:\n  budget: observe\n")
    w.plan = {"j0": (1500, 0), "j1": (10, 0)}
    a, b = put(w, "one", "j0"), put(w, "one", "j1")
    warn = snap_of(memory={"total_mb": 262144, "free_mb": 1, "pressure": "warn"})
    gate.serve(w.root, w.fx(snapshot=warn))
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert ra["would_hold"] == {"pressure": "memory pressure warn"}
    assert rb["started"] - b["queued"] >= gate.HOLD_MAX
    assert "would_hold" not in rb and rb["over"] == "pressure"


def _git(*argv, cwd):
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@" + "example.invalid", *argv],
                   cwd=cwd, check=True, capture_output=True)


def test_h4_a_landing_and_its_worktree_s_check_take_one_class(tmp_path):
    root, repo, wt = tmp_path / "state", tmp_path / "proj", tmp_path / "wt"
    root.mkdir()
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=repo)
    _git("worktree", "add", "-q", "-b", "work", str(wt), "main", cwd=repo)
    repo, wt = os.path.realpath(repo), os.path.realpath(wt)
    check = [*gate.self_argv(), *gate.CHECK_JOB, wt]
    landing = [*gate.self_argv(), *gate.LAND_JOB, repo, "work", "a" * 40, "/m"]
    assert {repo, "proj"} <= gate._repo_names(wt) and ".." not in gate._repo_names(wt)
    classes = [{"repo": "proj", "command": "make check", "cpu": 12, "mem_mb": 9000}]
    for real, cmd in ((wt, check), (repo, landing)):
        assert gate.job_class(root, real, cmd, classes) == {"cpu": 12, "mem_mb": 9000}
