"""Packet hw1-gate-within (design/34 items 2, 8, 11 and 13): `gate run --within`, a result's
`waited`, `cpu_seconds` and `tree`, a kept check returned at `gate run --check`, an open job
returned in place of a second, and a red line's `; fail <text>`. Each group is red at 57a2c44a
(alpha.183). Every repo, queue and runner is under the test's temp roots."""
import json
import os
import subprocess
import sys

import pytest

from claude_session import gate, hooks, land, unattended

from test_gate import World
from test_nw5_check_proof import Box, box, git, run  # noqa: F401  (box is a fixture)

SHA, TREE = "a" * 40, "b" * 40
WORDS = "write the id in your hand-back and end your turn"


def idle(monkeypatch):
    """No runner: every job stays queued."""
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)


def jobs(b: Box) -> list[str]:
    d = gate.gate_dir(b.root)
    return sorted(n for n in os.listdir(d) if gate.ID.match(n)) if d.is_dir() else []


def queued_id(text: str) -> str:
    return next(ln.split()[1] for ln in text.splitlines() if ln.startswith("queued "))


# ---- W1: the one bounded wait ------------------------------------------------------------

@pytest.mark.parametrize("bad", ["0", "101", "1.5", "x", "=-3", "100000000000000000000"])
def test_w1_within_is_a_whole_number_from_1_to_100(box, monkeypatch, bad):
    idle(monkeypatch)
    flag = "--within" + bad if bad.startswith("=") else "--within"
    argv = [flag] if bad.startswith("=") else [flag, bad]
    rc, out, err = run("gate", "run", str(box.tree), *argv, "--", "/bin/echo", "hi")
    assert (rc, out, gate.entries(box.root)) == (2, "", []), err


def test_w1_within_beside_wait_is_refused(box, monkeypatch):
    idle(monkeypatch)
    rc, out, err = run("gate", "run", str(box.tree), "--within", "5", "--wait", "--",
                       "/bin/echo", "hi")
    assert (rc, out, gate.entries(box.root)) == (2, "", [])
    assert "--within" in err


def test_w1_a_red_inside_the_bound_prints_its_line_and_tail_and_exits_its_code(box):
    body = "for i in $(seq 1 30); do echo line $i; done; echo 'FAILED t.py::x - boom'; " \
           "echo after; exit 3"
    rc, out, err = run("gate", "run", str(box.tree), "--within", "60", "--", "/bin/sh", "-c",
                       body)
    gid = queued_id(err)
    lines = out.splitlines()
    assert rc == 3, err
    assert lines[0].startswith(f"gate {gid} ") and ": exit 3 in " in lines[0]
    assert "; fail FAILED t.py::x - boom; log " in lines[0]
    assert len(lines) == 1 + gate.TAIL and "after" in lines and "line 1" not in lines
    assert not any(ln.startswith("queued") for ln in lines)


def test_w1_a_green_inside_the_bound_is_its_line_alone(box):
    rc, out, err = run("gate", "run", str(box.tree), "--within", "60", "--", "/bin/echo", "ok")
    gid = queued_id(err)
    assert rc == 0 and out.splitlines() == [gate.wait_line(
        json.loads(gate.result_path(box.root, gid).read_text()))]


def test_w1_l12_a_jobs_own_75_reads_as_its_line(box):
    rc, out, err = run("gate", "run", str(box.tree), "--within", "60", "--", "/bin/sh", "-c",
                       "exit 75")
    assert rc == 75 and out.startswith(f"gate {queued_id(err)} ") and ": exit 75 in " in out


def test_w1_past_the_bound_it_says_queued_and_exits_75(box, monkeypatch):
    idle(monkeypatch)
    rc, out, err = run("gate", "run", str(box.tree), "--within", "1", "--", "/bin/echo", "a")
    gid = queued_id(err)
    assert (rc, out) == (75, f"queued {gid}: {WORDS}\n")
    assert [e["id"] for e in gate.entries(box.root)] == [gid]
    # with an estimate of this command
    command, key = ["/bin/echo", "b"], gate.repo_key(os.path.realpath(box.tree))
    for n in range(1, 4):
        g = f"20261101-000000-{900 + n}"
        gate.entry_dir(box.root, g).mkdir(parents=True)
        gate.result_path(box.root, g).write_text(json.dumps(
            {"id": g, "exit": 0, "cut": None, "seconds": 120.0, "key": key, "command": command}))
    rc, out, err = run("gate", "run", str(box.tree), "--within", "1", "--", *command)
    assert (rc, out) == (75, f"queued {queued_id(err)}, est 2.0 min: {WORDS}\n")


# ---- W2: the result's three keys -----------------------------------------------------------

def _reap(p):
    code = p.poll()
    return code, (2.5 if code is not None else None)


def test_w2_waited_cpu_seconds_and_tree(tmp_path):
    w = World(tmp_path)
    e = w.put(at=w.t - 30)
    gate.serve(w.root, w.fx(idle=0, reap=_reap, dirty=lambda r: 0, tree=lambda r: TREE))
    r = w.result(e["id"])
    assert list(r)[-3:] == list(gate.MEASURE_KEYS) == ["waited", "cpu_seconds", "tree"]
    assert (r["waited"], r["cpu_seconds"], r["tree"]) == (30.0, 2.5, TREE)


def test_w2_each_key_null_where_not_known(tmp_path):
    w = World(tmp_path)
    a = w.put()
    gate.serve(w.root, w.fx(idle=0, dirty=lambda r: 2, tree=lambda r: TREE))
    r = w.result(a["id"])
    assert (r["cpu_seconds"], r["tree"]) == (None, None)      # a fake child, a dirty tree

    def boom(repo):
        raise OSError("no git")
    b = w.put()
    gate.serve(w.root, w.fx(idle=0, dirty=lambda r: 0, tree=boom))
    assert w.result(b["id"])["tree"] is None
    assert any("the tree at its start was not read" in ln for ln in w.logs)
    w.plan["nope"] = OSError("cannot start")
    c = w.put(first="nope")
    gate.serve(w.root, w.fx(idle=0))
    assert w.result(c["id"])["exit"] == 127 and w.result(c["id"])["cpu_seconds"] is None


def test_w2_cpu_seconds_come_from_wait4(tmp_path):
    w = World(tmp_path)
    e = gate.enqueue(w.root, str(w.repo), [sys.executable, "-c", "sum(i * i for i in "
                                           "range(3 * 10 ** 6))"], dict(os.environ), [], 120,
                     "", None, w.t)
    import time
    gate.serve(w.root, w.fx(idle=0, popen=subprocess.Popen, now=time.time, sleep=time.sleep,
                            poll=0.02, killpg=os.killpg))
    r = w.result(e["id"])
    assert r["exit"] == 0 and isinstance(r["cpu_seconds"], float) and r["cpu_seconds"] > 0


def test_w2_an_older_result_still_reads(tmp_path):
    w = World(tmp_path)
    gid = "20261101-000000-7"
    old = {"id": gid, "repo": "/r", "command": ["make", "check"], "exit": 0, "started": 1.0,
           "ended": 61.0, "seconds": 60.0, "log": "/no/log", "caller": None, "cut": None}
    gate.entry_dir(w.root, gid).mkdir(parents=True)
    gate.result_path(w.root, gid).write_text(json.dumps(old))
    rc, r = gate.wait(w.root, gid, spawn=lambda root: False)
    assert rc == 0 and gate.wait_line(r) == f"gate {gid} /r: exit 0 in 1 min; log /no/log"
    assert gate.status(w.root, 61.0)["done"]


# ---- W3: a kept check at `gate run --check` -----------------------------------------------

def test_w3_a_kept_check_is_returned_and_nothing_queued(box):
    rc, out, err = run("gate", "run", str(box.tree), "--check")
    gid = queued_id(out)
    assert rc == 0 and box.count() == 1, err
    before = jobs(box)
    rc, out, err = run("gate", "run", str(box.tree), "--check", "--within", "5")
    lines = out.splitlines()
    assert (rc, lines[0]) == (0, f"kept {gid}"), err
    assert lines[1] == gate.wait_line(json.loads(gate.result_path(box.root, gid).read_text()))
    assert len(lines) == 2 and jobs(box) == before and box.count() == 1


def test_w3_fresh_skips_the_look(box):
    box.check()
    rc, out, err = run("gate", "run", str(box.tree), "--check", "--fresh")
    assert rc == 0 and out.startswith("queued ") and box.count() == 2, err


def test_w3_main_moved_is_kept_here_and_never_for_a_landing(box):
    gid = box.check()
    git(box.path, "commit", "-q", "--allow-empty", "-m", "main moves")
    assert land.kept_for_run(box.root, str(box.tree)) == (gid, "")
    rc, out, _ = run("gate", "run", str(box.tree), "--check")
    assert (rc, out.splitlines()[0], box.count()) == (0, f"kept {gid}", 1)
    # the landing's own test holds as at the pin
    got = land.kept_check(box.root, str(box.path), str(box.tree), "work", box.sha, box.sha,
                          box.main())
    assert got[0] is None and "%s ran with main at" % gid in got[1]


def test_w3_a_red_a_new_head_or_dirt_is_not_kept(box):
    box.flag("red")
    box.check()
    box.flag("red", False)
    rc, out, _ = run("gate", "run", str(box.tree), "--check")
    assert rc == 0 and out.startswith("queued ") and box.count() == 2      # the red voids
    box.commit("two.txt", "two\n")
    rc, out, _ = run("gate", "run", str(box.tree), "--check")
    assert rc == 0 and out.startswith("queued ") and box.count() == 3      # another tree
    (box.tree / "loose.txt").write_text("x\n")
    rc, out, err = run("gate", "run", str(box.tree), "--check")
    assert (rc, out, box.count()) == (2, "", 3) and "is not clean" in err


# ---- W4: an open job is returned ------------------------------------------------------------

def test_w4_the_same_tree_and_command_returns_the_open_job(box, monkeypatch):
    idle(monkeypatch)
    rc, out, _ = run("gate", "run", str(box.tree), "--", "/bin/echo", "hi")
    gid = queued_id(out)
    assert gate.entries(box.root)[0]["tree"] == git(box.tree, "rev-parse", "HEAD^{tree}")
    rc, out, err = run("gate", "run", str(box.tree), "--", "/bin/echo", "hi")
    assert rc == 0 and out.startswith(f"open {gid} queued position 1 repo "), err
    assert [e["id"] for e in gate.entries(box.root)] == [gid]
    rc, out, _ = run("gate", "run", str(box.tree), "--", "/bin/echo", "other")
    assert rc == 0 and out.startswith("queued ") and len(gate.entries(box.root)) == 2
    rc, out, _ = run("gate", "run", str(box.tree), "--fresh", "--", "/bin/echo", "hi")
    assert rc == 0 and out.startswith("queued ") and len(gate.entries(box.root)) == 3


def test_w4_a_check_is_matched_and_within_waits_on_it(box, monkeypatch):
    idle(monkeypatch)
    rc, out, _ = run("gate", "run", str(box.tree), "--check")
    gid = queued_id(out)
    rc, out, err = run("gate", "run", str(box.tree), "--check", "--within", "1")
    lines = out.splitlines()
    assert rc == 75 and lines[0].startswith(f"open {gid} ") and lines[-1] == \
        f"queued {gid}: {WORDS}", err
    assert len(gate.entries(box.root)) == 1


def test_w4_a_running_job_is_named_running(box, monkeypatch):
    idle(monkeypatch)
    rc, out, _ = run("gate", "run", str(box.tree), "--", "/bin/echo", "hi")
    gid = queued_id(out)
    (gate.gate_dir(box.root) / "runner.json").write_text(json.dumps(
        {"pid": os.getpid(), "since": 1.0, "running": [{"id": gid, "pgid": None}]}))
    rc, out, _ = run("gate", "run", str(box.tree), "--", "/bin/echo", "hi")
    assert rc == 0 and out.startswith(f"open {gid} running repo ")


def test_w4_a_dirty_tree_is_never_matched(box, monkeypatch):
    idle(monkeypatch)
    (box.tree / "loose.txt").write_text("x\n")
    for _ in range(2):
        rc, out, _ = run("gate", "run", str(box.tree), "--", "/bin/echo", "hi")
        assert rc == 0 and out.startswith("queued ")
    es = gate.entries(box.root)
    assert len(es) == 2 and not any("tree" in e for e in es)
    assert gate.open_entry(box.root, str(box.tree), ["/bin/echo", "hi"], None) is None


# ---- W5: a red's failing line ----------------------------------------------------------------

GID = "20261127-120000-3"


@pytest.mark.parametrize("text,want", [
    ("ok\nFAIL\tgithub.invalid/x/y 0.1s\nok\n", "FAIL github.invalid/x/y 0.1s"),
    ("=== RUN TestX\n--- FAIL: TestX (0.00s)\nPASS\n", "--- FAIL: TestX (0.00s)"),
    ("ERROR tests/a.py - ImportError\n", "ERROR tests/a.py - ImportError"),
    ("make[1]: *** [test] Error 1\ndone\n", "make[1]: *** [test] Error 1"),
    ("E   AssertionError: assert 1 == 2\n", "E AssertionError: assert 1 == 2"),
    ("    raise ValueError('bad')\nValueError: bad\n", "ValueError: bad"),
    ("Error: no such file\n", "Error: no such file"),
    ("FAIL a\nmake: *** [check] Error 2\n", "make: *** [check] Error 2"),
    (f"FAIL a\ngate {GID}: Error: the gate's own\n", "FAIL a"),
    ("all good\nErrors are fine here\n", None),
])
def test_w5_the_last_failing_line(tmp_path, text, want):
    log = tmp_path / "log"
    log.write_text(text)
    assert gate.fail_text(str(log), GID) == want


def test_w5_cut_to_80_bytes_and_read_from_the_last_64k(tmp_path):
    log = tmp_path / "log"
    log.write_text("FAIL " + "x" * 200 + "\n")
    got = gate.fail_text(str(log), GID)
    assert len(got.encode()) == gate.FAIL_MOST == 80 and got.startswith("FAIL x")
    log.write_text("FAIL " + "é" * 100 + "; \"q\"\n")
    got = gate.fail_text(str(log), GID)
    assert len(got.encode()) <= 80 and len(json.dumps(got)) - 2 <= 80 and ";" not in got
    log.write_text("FAIL early\n" + "y" * 70000 + "\nfine\n")
    assert gate.fail_text(str(log), GID) is None
    os.mkfifo(tmp_path / "fifo")
    assert gate.fail_text(str(tmp_path / "fifo"), GID) is None        # never blocks
    assert gate.fail_text(None, GID) is None and gate.fail_text(str(tmp_path / "no"), GID) is None


def test_w5_a_red_line_gains_fail_before_log_and_still_parses(tmp_path):
    log = tmp_path / "log"
    log.write_text("FAIL pkg/x\n")
    r = {"id": GID, "repo": "/r/x", "exit": 1, "seconds": 60.0, "log": str(log)}
    line = gate.wait_line(r)
    assert line == f"gate {GID} /r/x: exit 1 in 1 min; fail FAIL pkg/x; log {log}"
    assert gate.wait_line({**r, "exit": 0}) == f"gate {GID} /r/x: exit 0 in 1 min; log {log}"
    g = unattended.GATE_LINE.match(line)
    assert g and (g.group(1), g.group(3), g.group(5)) == (GID, "1", str(log))
    chained = gate.wait_line({**r, "chain": "c", "head": SHA, "dirty": {"start": 2},
                              "label": "row"})
    assert chained.endswith(f"; dirty 2; row; fail FAIL pkg/x; log {log}")


def test_w5_the_longest_line_fits_a_hooks_room_alone(tmp_path):
    gid = "20991231-235959-" + "9" * 12
    repo = "/Users/" + "u" * 24 + "/code/agentik/agentik-session/.claude/worktrees/" + "r" * 40
    log = tmp_path / "log"
    log.write_text("FAILED " + "é\"" * 100 + "\n")
    r = {"id": gid, "repo": repo, "exit": 255, "seconds": 59994.0, "log": str(log),
         "chain": "c" * 64, "head": SHA, "dirty": {"start": 99999}, "label": "L" * 60}
    shown = "/Users/" + "u" * 24 + "/.local/state/agentik-session/gate/" + gid + "/log"
    line = gate.wait_line(r).replace(str(log), shown)
    assert "; fail FAILED " in line
    out = json.dumps(hooks._with_gate({}, "UserPromptSubmit", [line]))
    assert len(out) <= hooks.MAX_OUT, (len(out), line)
