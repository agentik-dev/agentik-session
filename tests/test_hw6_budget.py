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
    stops = []

    def peek(world):
        if not stops and gate.result_path(w.root, a["id"]).exists() is False:
            st = gate.status(w.root, w.t, alive=lambda pid: True, fx=w.fx())
            stops.append(gate.status_lines(st))
    w.hooks.append(peek)
    gate.serve(w.root, w.fx(snapshot=snap_of(disks=low),
                            largest=lambda root, folder: "largest /x/cache 40 GB (idle)"))
    r = w.result(a["id"])
    assert r["started"] == T0 + gate.HOLD_MAX and r["over"] == "disk"
    assert f"waits on 10 GB free, at or under the floor of 25; largest /x/cache 40 GB (idle) " \
           f"since {gate._hm(T0)}" in stops[0][0]
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
    assert ra["would_hold"] == {"pressure": 0.0} and set(rb["would_hold"]) == {"budget", "pressure"}
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
