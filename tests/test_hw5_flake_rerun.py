"""Packet hw5-flake-rerun (design/34 items 12 to 14): a priority, a light class, one rerun of
a load flake, `gate drop`, and the line's marks. Each group is red at 362bcb0d (alpha.184).
Every queue and runner is under the test's temp roots; the clock and the load are passed in."""
import inspect
import json

import pytest

from claude_session import cli, gate, hooks, land, unattended

from test_gate import ENV, World
from test_nw5_check_proof import box, run  # noqa: F401  (box is a fixture)

STOP = b"--- a test\npanic: test timed out after 10m0s\n"
LOW, HIGH = (lambda: (0.5, 0.5, 0.5)), (lambda: (20.0, 9.0, 9.0))


def talking(w: World, said: dict):
    """The world's spawn, writing `said[argv[0]]` into the job's log first."""
    def popen(argv, **kw):
        kw["stdout"].write(said.get(argv[0], b""))
        return w.popen(argv, **kw)
    return popen


def fx(w: World, said=None, loads=LOW, **over):
    return w.fx(idle=0, popen=talking(w, said or {}), loads=loads, load=lambda: 0.0,
                cores=lambda: 4, **over)


@pytest.fixture
def as_the_verb(monkeypatch):
    """Build 2, S1: the World's entries queued as the `gate run` verb queues them, the one
    caller opted in to a load flake's rerun."""
    def put(self, first="a", locks=(), wall=5400, caller=None, label="", at=None):
        return gate.enqueue(self.root, str(self.repo), [first, "x"], ENV, list(locks), wall,
                            label, caller, self.t if at is None else at, rerun=True)
    monkeypatch.setattr(World, "put", put)


def lines(w: World, sid="s1"):
    return gate.inbox_take(w.root, sid, limit=10)


def same_key(w: World, *es):
    """Rewrite each entry's key to the first's: worktrees of one repo."""
    for e in es[1:]:
        p = gate._queue(w.root) / f"{e['id']}.json"
        p.write_text(json.dumps({**json.loads(p.read_text()), "key": es[0]["key"]}))
        e["key"] = es[0]["key"]


def other(w: World, name="repo2"):
    p = w.repo.parent / name
    p.mkdir(exist_ok=True)
    return p


# ---- F1: priority -----------------------------------------------------------------------

def test_f1_a_marked_entry_goes_first_and_position_follows():
    es = [{"id": "20991231-000000-1", "queued": 100.0},
          {"id": "20991231-000000-2", "queued": 101.0, "priority": True},
          {"id": "20991231-000000-3", "queued": 102.0}]
    assert [e["id"][-1] for e in gate.pick_order(es, 200.0)] == ["2", "1", "3"]
    # an hour or more queued is never passed over, whatever the marks
    assert [e["id"][-1] for e in gate.pick_order(es, 100.0 + 3600)] == ["1", "2", "3"]
    # an older entry, with no such key and no `queued`, reads as no priority
    old = [{"id": "20991231-000000-4"}, {"id": "20991231-000000-5", "priority": True}]
    assert [e["id"][-1] for e in gate.pick_order(old, 200.0)] == ["5", "4"]


def test_f1_the_runner_picks_the_marked_one_and_position_says_so(tmp_path):
    w = World(tmp_path)
    a = w.put(first="a")
    b = gate.enqueue(w.root, str(w.repo), ["b", "x"], ENV, [], 5400, "", None, w.t,
                     priority=True)
    assert b["priority"] is True and "priority" not in a and list(a) == list(gate.ENTRY_KEYS)
    alive = lambda pid: False                                       # noqa: E731
    assert (gate.position(w.root, b["id"], alive, now=w.t),
            gate.position(w.root, a["id"], alive, now=w.t)) == (1, 2)
    st = gate.status(w.root, w.t, alive=alive, fx=fx(w))
    assert [q["id"] for q in st["queued"]] == [b["id"], a["id"]]
    gate.serve(w.root, fx(w))
    assert [argv[0] for argv, _, _ in w.spawned] == ["b", "a"]


def test_f1_an_hour_old_entry_is_not_passed_over(tmp_path):
    w = World(tmp_path)
    a = w.put(first="a", at=w.t - 3600)
    gate.enqueue(w.root, str(w.repo), ["b", "x"], ENV, [], 5400, "", None, w.t, priority=True)
    gate.serve(w.root, fx(w))
    assert [argv[0] for argv, _, _ in w.spawned] == ["a", "b"] and w.result(a["id"])


def test_f1_a_landing_is_queued_with_the_mark():
    assert "priority=True" in inspect.getsource(cli._gate_land)


# ---- F2: the light class ----------------------------------------------------------------

def test_f2_refusals_and_the_wall(box, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    tree = str(box.tree)
    for argv in (["--light", "--check"], ["--light", "--wall", "121", "--", "true"],
                 ["--light", "--", *gate.self_argv(), *gate.LAND_JOB, tree, "b", "a" * 40, "m"]):
        rc, out, err = run("gate", "run", tree, *argv)
        assert (rc, out) == (2, "") and "--light" in err, argv
    rc, out, err = run("gate", "run", tree, "--light", "--", "true")
    gid = out.split()[1]
    e = next(e for e in gate.entries(box.root) if e["id"] == gid)
    assert rc == 0 and (e["wall"], e["light"]) == (120, True), err
    with pytest.raises(gate.GateError):
        gate.enqueue(box.root, tree, ["true"], {}, [], 121, "", None, 1.0, light=True)


def test_f2_held_only_by_its_own_worktree():
    run_ = [{"id": "20991231-000000-1", "key": "K", "repo": "/w1"}]
    es = [{"id": "20991231-000000-2", "key": "K", "repo": "/w2", "light": True},
          {"id": "20991231-000000-3", "key": "K", "repo": "/w2", "light": True},
          {"id": "20991231-000000-4", "key": "K", "repo": "/w1", "light": True},
          {"id": "20991231-000000-5", "key": "K", "repo": "/w3"}]
    got = [why for _, why in gate._holds(es, run_)]
    assert got[0] is None                      # another worktree's job does not hold it
    assert got[1] is not None                  # two light jobs of one worktree, one at a time
    assert got[2] is not None                  # its own worktree's open job holds it
    assert got[3] is not None                  # a job not light is held by its key, as before
    # a queued light job holds only its worktree against the entries after it
    es2 = [{"id": "20991231-000000-6", "key": "J", "repo": "/w1", "light": True},
           {"id": "20991231-000000-7", "key": "J", "repo": "/w2"},
           {"id": "20991231-000000-8", "key": "J", "repo": "/w1"}]
    assert [why is None for _, why in gate._holds(es2, [])] == [True, True, False]


def test_f2_not_counted_against_max_running(tmp_path):
    w = World(tmp_path)
    f = fx(w)
    run_ = [{"id": f"20991231-000000-{i}", "key": f"K{i}"} for i in range(3)]
    cfg = {"max_running": 3}
    assert gate._bar(cfg, f, {"id": "x"}, run_, 0.0, w.t) == ("running", 3, 3)
    assert gate._bar(cfg, f, {"id": "x", "light": True}, run_, 0.0, w.t) is None
    lit = run_[:2] + [{**run_[2], "light": True}]
    assert gate._bar(cfg, f, {"id": "x"}, lit, 0.0, w.t) is None        # a light one is not counted


def test_f2_a_light_job_runs_beside_its_keys_job_of_another_worktree(tmp_path):
    w = World(tmp_path)
    w.plan.update({"a": (300, 0), "b": (10, 0)})
    a = w.put(first="a")
    b = gate.enqueue(w.root, str(other(w)), ["b", "x"], ENV, [], 120, "", None, w.t,
                     light=True)
    same_key(w, a, b)
    gate.serve(w.root, fx(w))
    rb = w.result(b["id"])
    assert rb["beside"] == [a["id"]] and rb["ended"] < w.result(a["id"])["ended"]


@pytest.mark.usefixtures("as_the_verb")
# ---- F3: one rerun of a load flake -------------------------------------------------------

def test_f3_a_flake_under_load_is_rerun_alone_and_only_its_line_is_sent(tmp_path):
    w = World(tmp_path)
    w.plan["a"] = (100, 1)
    a = w.put(first="a", caller="s1")
    gate.serve(w.root, fx(w, {"a": STOP}, loads=HIGH))
    r1 = w.result(a["id"])
    assert (r1["flake"], r1["ceiling"], r1["alongside"]) == ("load", 3.0, [])
    rid = r1["rerun"]
    r2 = w.result(rid)
    assert r2["rerun_of"] == a["id"] and "flake" not in r2 and "rerun" not in r2   # never again
    assert [argv[0] for argv, _, _ in w.spawned] == ["a", "a"]
    got = lines(w)
    assert len(got) == 1 and got[0].startswith(f"gate {rid} ") and f"rerun of {a['id']}; " in got[0]


@pytest.mark.parametrize("said,loads,rc", [
    (STOP + b"--- FAIL: TestX\n", HIGH, 1),            # an assertion is never a flake
    (STOP + b"AssertionError\n", HIGH, 1),
    (STOP + b"WARNING: DATA RACE\n", HIGH, 1),
    (STOP, LOW, 1),                                    # alone and under the ceiling
    (b"ok\n", HIGH, 1),                                # no stop line
])
def test_f3_not_a_flake_is_told_at_once(tmp_path, said, loads, rc):
    w = World(tmp_path)
    w.plan["a"] = (100, rc)
    a = w.put(first="a", caller="s1")
    gate.serve(w.root, fx(w, {"a": said}, loads=loads))
    r = w.result(a["id"])
    assert "flake" not in r and len(w.spawned) == 1 and len(lines(w)) == 1


@pytest.mark.usefixtures("as_the_verb")
@pytest.mark.parametrize("said", [b"bounded: stop: load\n", b"+++++++ Timeout +++++++\n",
                                  b"E   Failed: Timeout >10.0s\n"])
def test_f3_each_stop_line_and_a_timeouts_124(tmp_path, said):
    w = World(tmp_path)
    w.plan.update({"a": (100, 1), "t": (100, 124)})
    a, t = w.put(first="a"), w.put(first="t")
    gate.serve(w.root, fx(w, {"a": said}, loads=HIGH))
    assert w.result(a["id"])["flake"] == "load" and w.result(t["id"])["flake"] == "load"
    assert set(land.STOPS) <= set(gate.STOP_LINES)


@pytest.mark.usefixtures("as_the_verb")
def test_f3_a_job_beside_it_makes_a_flake_at_low_load(tmp_path):
    w = World(tmp_path)
    w.plan.update({"a": (200, 1), "b": (10, 0)})
    a = w.put(first="a")
    b = gate.enqueue(w.root, str(other(w)), ["b", "x"], ENV, [], 5400, "", None, w.t)
    gate.serve(w.root, fx(w, {"a": STOP}))
    r1 = w.result(a["id"])
    assert r1["beside"] == [] and r1["alongside"] == [b["id"]] and r1["flake"] == "load"
    r2 = w.result(r1["rerun"])
    assert r2["beside"] == [] and r2["started"] >= w.result(b["id"])["ended"]


def test_f3_a_wall_cut_and_a_landing_are_never_rerun(tmp_path):
    w = World(tmp_path)
    w.plan["a"] = (None, 0)
    a = w.put(first="a", wall=5)
    lj = [*gate.self_argv(), *gate.LAND_JOB, str(w.repo), "b", "a" * 40, "m"]
    w.plan[lj[0]] = (100, 1)
    b = gate.enqueue(w.root, str(other(w)), lj, ENV, [], 5400, "", None, w.t)
    gate.serve(w.root, fx(w, {"a": STOP, lj[0]: STOP}, loads=HIGH))
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert (ra["exit"], ra["cut"]) == (124, gate.CUT_WALL) and "flake" not in ra
    assert rb["exit"] == 1 and "flake" not in rb and len(w.spawned) == 2


@pytest.mark.usefixtures("as_the_verb")
def test_f3_a_rerun_not_started_in_30_minutes_goes_and_the_first_line_is_sent(tmp_path):
    w = World(tmp_path)
    w.plan.update({"a": (100, 1), "b": (3000, 0)})
    a = w.put(first="a", caller="s1")
    gate.enqueue(w.root, str(other(w)), ["b", "x"], ENV, [], 5400, "", None, w.t)
    gate.serve(w.root, fx(w, {"a": STOP}))
    r1 = w.result(a["id"])
    assert r1["flake"] == "load, not rerun" and w.result(r1["rerun"])["exit"] == 130   # S2
    assert not gate.entries(w.root) and [argv[0] for argv, _, _ in w.spawned] == ["a", "b"]
    got = lines(w)
    assert len(got) == 1 and got[0].startswith(f"gate {a['id']} ") \
        and "; flake: load, not rerun; " in got[0]


def _flaked(w: World, rerun_done: bool):
    a, r = "20991231-000000-1", "20991231-000000-2"
    for gid, body in ((a, {"exit": 1, "flake": "load", "rerun": r}),
                      (r, {"exit": 0, "rerun_of": a})):
        if gid == r and not rerun_done:
            gate._mkdir(gate._queue(w.root))
            (gate._queue(w.root) / f"{r}.json").write_text(json.dumps(
                {"id": r, "repo": str(w.repo), "command": ["a"], "rerun_of": a, "chain": "c1"}))
            continue
        gate.entry_dir(w.root, gid).mkdir(parents=True)
        gate.result_path(w.root, gid).write_text(json.dumps(
            {"id": gid, "repo": "/r", "seconds": 60.0, "log": "/no/log", **body}))
    return a, r


def test_f3_gate_wait_follows_and_within_is_told_queued(tmp_path, monkeypatch, capsys):
    w = World(tmp_path)
    a, r = _flaked(w, rerun_done=False)
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    assert cli._gate_within_wait(w.root, {"id": a, "command": ["a"]}, 5) == gate.QUEUED
    assert capsys.readouterr().out.startswith(f"queued {r}")
    assert gate.followed(w.root, a) == r and gate.open_jobs(w.root, "c1")[0]["id"] == r
    rc, got = gate.wait(w.root, a, timeout=0, spawn=lambda root: False, follow=True)
    assert (rc, got) == (1, None)                         # it waits on the queued rerun
    (gate._queue(w.root) / f"{r}.json").unlink()          # taken out: the flake's own result
    rc, got = gate.wait(w.root, a, spawn=lambda root: False, follow=True)
    assert rc == 0 and got["id"] == a
    (tmp_path / "two").mkdir()
    w2 = World(tmp_path / "two")
    a, r = _flaked(w2, rerun_done=True)
    rc, got = gate.wait(w2.root, a, spawn=lambda root: False, follow=True)
    assert rc == 0 and got["id"] == r
    assert gate.wait(w2.root, a, spawn=lambda root: False)[1]["id"] == a     # unfollowed


def test_f3_a_rerun_keeps_the_chain_and_session():
    e = {"id": "20991231-000000-1", "repo": "/r", "command": ["a"], "env": {}, "locks": [],
         "wall": 60, "label": "row", "caller": "s1", "queued": 1.0, "key": "K",
         "key_name": "r", "chain": "c1", "tree": "b" * 40, "load": {}, "beside": []}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = gate._requeue(d, e, 50.0)
        assert {k: r[k] for k in ("command", "caller", "chain", "label", "tree", "rerun_of",
                                  "flaked")} == {"command": ["a"], "caller": "s1",
                                                 "chain": "c1", "label": "row",
                                                 "tree": "b" * 40, "rerun_of": e["id"],
                                                 "flaked": 50.0}
        assert "load" not in r and gate.open_jobs(d, "c1")[0]["id"] == r["id"]


# ---- F4: gate drop -----------------------------------------------------------------------

def test_f4_a_queued_job_is_dropped_and_its_line_sent(tmp_path):
    w = World(tmp_path)
    a = w.put(caller="s1")
    rc, text = gate.drop(w.root, a["id"], fx=w.fx())
    r = w.result(a["id"])
    assert (rc, r["exit"], r["dropped"], r["cut"]) == (0, 130, True, gate.CUT_CALLER)
    assert "; dropped; " in text and not gate.entries(w.root)
    assert lines(w) == [text]
    assert gate.drop(w.root, a["id"], fx=w.fx()) == (0, text)           # done: its line


def test_f4_running_is_not_touched_and_unknown_is_2(tmp_path):
    w = World(tmp_path)
    a = w.put()
    (gate.gate_dir(w.root) / "runner.json").write_text(json.dumps(
        {"pid": 1, "running": [{"id": a["id"], "pgid": 9}]}))
    got = gate.drop(w.root, a["id"], fx=w.fx(), alive=lambda pid: True)
    assert got == (1, f"running {a['id']}: not dropped") and gate.entries(w.root)[0]["id"] == a["id"]
    assert gate.drop(w.root, "20991231-000000-99", fx=w.fx())[0] == 2
    assert gate.drop(w.root, "nope", fx=w.fx())[0] == 2


def test_f4_a_drop_after_the_pick_is_never_run(tmp_path):
    w = World(tmp_path)
    a = w.put()
    (gate._queue(w.root) / f"{a['id']}.json").rename(gate._queue(w.root) / f"{a['id']}.drop")
    s = gate._Set(w.t)
    gate._start(w.root, w.fx(), {}, a, s)
    assert w.spawned == [] and s.running == [] and s.starting is None


def test_f4_the_verb(box):
    rc, out, err = run("gate", "drop", "20991231-000000-99")
    assert (rc, out) == (2, "") and "no gate" in err
    rc, out, err = run("gate", "run", str(box.tree), "--", "true")
    gid = out.split()[1]
    rc, out, err = run("gate", "drop", gid)
    assert rc == 0 and "; dropped; " not in out and f"gate {gid} " in out   # it ran first


def test_f4_the_cancel_mark_still_works(tmp_path):
    w = World(tmp_path)
    a = w.put()
    gate.cancel(w.root, a["id"])
    gate.serve(w.root, fx(w))
    r = w.result(a["id"])
    assert (r["exit"], r["cut"]) == (130, gate.CUT_CALLER) and "dropped" not in r


# ---- F5: the line and the records ---------------------------------------------------------

GID = "20991231-235959-1"


@pytest.mark.parametrize("marks,text", [
    ({"flake": "load"}, "flake: load; "), ({"flake": "load, not rerun"}, "flake: load, not rerun; "),
    ({"rerun_of": "20991231-000000-7"}, "rerun of 20991231-000000-7; "),
    ({"dropped": True}, "dropped; "), ({}, "")])
def test_f5_each_mark_in_the_line_and_it_still_parses(marks, text):
    r = {"id": GID, "repo": "/r/x", "exit": 1, "seconds": 60.0, "log": "/no/log", **marks}
    line = gate.wait_line(r)
    assert line == f"gate {GID} /r/x: exit 1 in 1 min; {text}log /no/log"
    g = unattended.GATE_LINE.match(line)
    assert g and (g.group(1), g.group(3), g.group(5)) == (GID, "1", "/no/log")


def test_f5_the_inbox_line_holds_the_marks(tmp_path):
    r = {"id": GID, "repo": "/r", "exit": 0, "seconds": 1.0, "log": "/l", "ended": 1.0,
         "rerun_of": "20991231-000000-7"}
    p = gate.inbox_write(tmp_path, "s1", r)
    body = json.loads(p.read_text())
    assert list(body) == [*gate.INBOX_KEYS, "rerun_of"]
    assert gate.wait_line(body) == gate.wait_line(r)


def test_f5_the_longest_line_fits_a_hooks_room_alone(tmp_path):
    gid = "20991231-235959-" + "9" * 12
    repo = "/Users/" + "u" * 24 + "/code/agentik/agentik-session/.claude/worktrees/" + "r" * 40
    log = tmp_path / "log"
    log.write_text("FAILED " + "é\"" * 100 + "\n")
    r = {"id": gid, "repo": repo, "exit": 255, "seconds": 59994.0, "log": str(log),
         "chain": "c" * 64, "head": "a" * 40, "dirty": {"start": 99999}, "label": "L" * 60,
         "dropped": True, "flake": "load, not rerun", "rerun_of": gid}
    shown = "/Users/" + "u" * 24 + "/.local/state/agentik-session/gate/" + gid + "/log"
    line = gate.wait_line(r).replace(str(log), shown)
    assert f"; dropped; flake: load, not rerun; rerun of {gid}; fail FAILED " in line
    out = json.dumps(hooks._with_gate({}, "UserPromptSubmit", [line]))
    assert len(out) <= hooks.MAX_OUT, (len(out), line)


def test_f5_an_older_entry_and_result_still_read(tmp_path):
    w = World(tmp_path)
    old = {"id": "20261101-000000-7", "repo": str(w.repo), "command": ["a", "x"], "env": ENV,
           "locks": [], "wall": 60, "label": "", "caller": None, "queued": w.t}
    gate._mkdir(gate._queue(w.root))
    (gate._queue(w.root) / f"{old['id']}.json").write_text(json.dumps(old))
    gate.serve(w.root, fx(w))
    r = w.result(old["id"])
    assert r["exit"] == 0 and list(r) == [*gate.RESULT_KEYS, *gate.MEASURE_KEYS]
    assert gate.wait_line({"id": old["id"], "repo": "/r", "exit": 0, "seconds": 60.0,
                           "log": "/l"}) == f"gate {old['id']} /r: exit 0 in 1 min; log /l"


def test_f5_a_flakes_red_then_its_reruns_green_is_kept(box):
    box.flag("red")
    first = box.check()
    box.flag("red", False)
    second = box.check()
    for gid, marks in ((first, {"flake": "load", "rerun": second}), (second, {"rerun_of": first})):
        p = gate.result_path(box.root, gid)
        p.write_text(json.dumps({**json.loads(p.read_text()), **marks}))
    rc, out, err = run("gate", "run", str(box.tree), "--check")
    assert (rc, out.splitlines()[0]) == (0, f"kept {second}"), err
    assert f"; rerun of {first}; " in out.splitlines()[1]


# ---- build 2: review 1's blocks F1 to F5 and notes N3, N4, N5, N7 ------------------------

def test_s1_a_job_the_plugin_queues_for_itself_is_never_rerun(tmp_path):
    w = World(tmp_path)
    w.plan["a"] = (100, 1)
    a = w.put(first="a", caller="s1")                 # enqueue's default: no opt-in
    assert "may_rerun" not in a
    gate.serve(w.root, fx(w, {"a": STOP}, loads=HIGH))
    r = w.result(a["id"])
    assert r["exit"] == 1 and not {"flake", "rerun", "ceiling", "alongside"} & set(r)
    assert [argv[0] for argv, _, _ in w.spawned] == ["a"] and not gate.entries(w.root)
    got = lines(w)
    assert len(got) == 1 and got[0].startswith(f"gate {a['id']} ") and "flake" not in got[0]


def test_s1_the_opt_in_is_the_verbs_alone(box, monkeypatch, tmp_path):
    from claude_session import commit, deliver
    asked = []

    def record(*a, **k):
        asked.append(k.get("rerun", False))
        raise gate.GateError("recorded")
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    rc, out, err = run("gate", "run", str(box.tree), "--", "true")
    gid = out.split()[1]
    assert rc == 0 and next(e for e in gate.entries(box.root)
                            if e["id"] == gid)["may_rerun"] is True
    monkeypatch.setattr(gate, "enqueue", record)
    assert commit._gate_check(str(box.tree), ["make", "check"], {"HOME": str(tmp_path)},
                              None, 600) == 1
    with pytest.raises(deliver.Red):
        deliver._make_install(str(box.tree), box.root, {"HOME": str(tmp_path)}, "x")
    assert asked == [False, False] and "rerun=" not in inspect.getsource(cli._gate_land)


@pytest.mark.usefixtures("as_the_verb")
def test_s2_a_rerun_taken_out_leaves_its_id_readable(tmp_path, monkeypatch, capsys):
    w = World(tmp_path)
    w.plan.update({"a": (100, 1), "b": (3000, 0)})
    a = w.put(first="a", caller="s1")
    gate.enqueue(w.root, str(other(w)), ["b", "x"], ENV, [], 5400, "", None, w.t)
    gate.serve(w.root, fx(w, {"a": STOP}))           # b holds the machine past 30 minutes
    r1 = w.result(a["id"])
    rid = r1["rerun"]
    left = w.result(rid)
    assert (left["exit"], left["flake"], left["rerun_of"]) == (130, "load, not rerun", a["id"])
    line = gate.wait_line(r1)
    assert "; flake: load, not rerun; " in line and lines(w) == [line]
    for follow in (False, True):
        rc, got = gate.wait(w.root, rid, spawn=lambda root: False, follow=follow)
        assert rc == 0 and got["id"] == a["id"] and gate.wait_line(got) == line
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    assert cli._gate_wait(w.root, rid, None, False, strict=True) == 1    # the first's code
    assert capsys.readouterr().out.strip() == line
    assert gate.drop(w.root, rid, fx=w.fx()) == (0, line)                # done
    assert lines(w) == []                                                # nothing sent twice


def test_s3_a_light_job_reads_its_folders_worktree(box):
    for name in ("sub", "two"):
        (box.tree / name).mkdir()
    root = box.root
    c = gate.enqueue(root, str(box.tree), ["make", "check"], ENV, [], 600, "", None, 1.0)
    li = gate.enqueue(root, str(box.tree / "sub"), ["make", "stamp"], ENV, [], 120, "", None,
                      2.0, light=True)
    li2 = gate.enqueue(root, str(box.tree / "two"), ["make", "x"], ENV, [], 120, "", None,
                       3.0, light=True)
    assert "top" not in c and li["top"] == li2["top"] == c["repo"] == gate.worktree(li)
    assert [why is None for _, why in gate._holds([li], [c])] == [False]    # beside its check
    assert [why is None for _, why in gate._holds([c, li], [])] == [True, False]
    assert [why is None for _, why in gate._holds([li, li2], [])] == [True, False]
    assert [why is None for _, why in gate._holds([li2], [li])] == [False]  # one at a time
    assert gate.top_level(str(box.root)) == gate._real(str(box.root))       # in no checkout


def test_s4_a_light_job_is_held_while_a_landing_of_its_key_is_open():
    land_job = [*gate.self_argv(), *gate.LAND_JOB, "/main", "b", "a" * 40, "/m"]
    landing = {"id": "20991231-000000-1", "key": "K", "repo": "/main", "command": land_job}
    li = {"id": "20991231-000000-2", "key": "K", "repo": "/wt", "light": True}
    other_key = {"id": "20991231-000000-3", "key": "J", "repo": "/wt2", "light": True}
    assert [why for _, why in gate._holds([li], [landing])] == [("key", "main")]   # running
    for order in ([landing, li], [li, landing]):                                 # queued
        got = dict((e["id"], why) for e, why in gate._holds(order, []))
        assert got[li["id"]] == ("key", "main") and got[landing["id"]] is None
    assert [why for _, why in gate._holds([other_key], [landing])] == [None]


def test_s6_the_mark_orders_one_keys_entries_alone(tmp_path):
    es = [{"id": "20991231-000000-1", "key": "A", "queued": 100.0},
          {"id": "20991231-000000-2", "key": "B", "queued": 101.0, "priority": True},
          {"id": "20991231-000000-3", "key": "A", "queued": 102.0, "priority": True},
          {"id": "20991231-000000-4", "key": "B", "queued": 103.0}]
    assert [e["id"][-1] for e in gate.pick_order(es, 200.0)] == ["3", "2", "1", "4"]
    assert [e["id"][-1] for e in gate.pick_order(es, 100.0 + 3600)] == ["1", "2", "3", "4"]
    w = World(tmp_path)                               # review 1's probe: max_running 1
    cfg = w.home / ".claude" / "agentik" / "profiles.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("gate:\n  max_running: 1\n")
    w.plan.update({"a": (100, 0), "b": (100, 0)})
    a = w.put(first="a")
    b = gate.enqueue(w.root, str(other(w)), ["b", "x"], ENV, [], 5400, "", None, w.t + 1,
                     priority=True)
    assert a["key"] != b["key"]
    alive = lambda pid: False                                       # noqa: E731
    assert (gate.position(w.root, a["id"], alive, now=w.t + 2),
            gate.position(w.root, b["id"], alive, now=w.t + 2)) == (1, 2)
    st = gate.status(w.root, w.t + 2, alive=alive, fx=fx(w))
    assert [q["id"] for q in st["queued"]] == [a["id"], b["id"]]
    gate.serve(w.root, fx(w))
    assert [argv[0] for argv, _, _ in w.spawned] == ["a", "b"]
