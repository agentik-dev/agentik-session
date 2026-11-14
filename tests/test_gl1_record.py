"""Packet gl1-gate-record (hq design/19 §3 item 10): a gate result records the load, the jobs
beside it and its folder's dirt (R1 to R4), and a landing whose check `scripts/bounded` refused
says `unrun` on its line (R5). Every runner is faked in a temp state root (test_gate's World);
every repo is made up under the test's temp dir. Lines 1 to 6 are red at 7c1f711 (alpha.113)."""
import io
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate
from test_gate import ENV, T0, World

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugin" / "lib" / "agentik-session"
NEW = ("load", "beside", "dirty")
NULLS = {"load": {"start": None, "end": None}, "beside": None,
         "dirty": {"start": None, "end": None}}


@pytest.fixture
def w(tmp_path, monkeypatch):
    world = World(tmp_path)
    monkeypatch.setenv("HOME", str(world.home))         # the git a read runs sees no one's config
    monkeypatch.setenv("XDG_CONFIG_HOME", str(world.home / ".config"))
    return world


def git_env(tmp_path):
    return {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}


def git_repo(path, tmp_path):
    g = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@" + "example.invalid"]
    subprocess.run(g + ["init", "-q"], check=True, env=git_env(tmp_path))
    (path / "base").write_text("b\n")
    subprocess.run(g + ["add", "base"], check=True, env=git_env(tmp_path))
    subprocess.run(g + ["commit", "-qm", "base"], check=True, env=git_env(tmp_path))


def fake_git(tmp_path, body):
    d = tmp_path / ("bin-" + str(abs(hash(body))))
    d.mkdir()
    (d / "git").write_text("#!/bin/sh\n" + body + "\n")
    (d / "git").chmod(0o755)
    return d


def calls(*values):
    """A fake read that answers `values` in turn, an exception raised, the last repeating."""
    it = list(values)

    def read(*_):
        x = it.pop(0) if len(it) > 1 else it[0]
        if isinstance(x, BaseException):
            raise x
        return x
    return read


# ---- R1: the three keys ------------------------------------------------------

def test_gl1_1_a_job_run_to_its_end_holds_the_machine(w, tmp_path):
    assert len(gate.RESULT_KEYS) == 15 and gate.RESULT_KEYS[-4:] == ("key", *NEW)
    git_repo(w.repo, tmp_path)
    (w.repo / "loose1").write_text("1\n")
    (w.repo / "loose2").write_text("2\n")
    other = tmp_path / "other"
    other.mkdir()
    w.plan = {"a": (200, 0), "b": (10, 4)}

    def popen(argv, **kw):
        if argv[0] == "a":
            (Path(kw["cwd"]) / "third").write_text("3\n")
        return w.popen(argv, **kw)
    a = w.put("a")
    b = gate.enqueue(w.root, str(other), ["b", "x"], ENV, [], 5400, "", None, w.t)
    loads = calls((1.236, 0.5, 0.25), (2.0, 1.004, 0.5), (3, 2, 1), (4.561, 3.339, 2.0))
    assert gate.serve(w.root, w.fx(popen=popen, loads=loads, load=lambda: 0.0,
                                   cores=lambda: 8)) == 0
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert list(ra) == list(gate.RESULT_KEYS) == list(rb)
    assert ra["load"] == {"start": [1.24, 0.5, 0.25], "end": [4.56, 3.34, 2.0]}
    assert rb["load"] == {"start": [2.0, 1.0, 0.5], "end": [3.0, 2.0, 1.0]}
    assert (ra["beside"], rb["beside"]) == ([], [a["id"]])
    assert ra["dirty"] == {"start": 2, "end": 3}
    assert rb["dirty"] == {"start": None, "end": None}        # no work tree there
    assert (ra["exit"], ra["seconds"], rb["exit"], rb["seconds"]) == (0, 200, 4, 10)
    assert w.logs == []


def test_gl1_1_beside_names_each_running_oldest_first(w, tmp_path):
    w.plan = {"a": (300, 0), "b": (300, 0), "c": (5, 0)}
    ids = []
    for name in "abc":
        repo = tmp_path / ("repo-" + name)
        repo.mkdir()
        ids.append(gate.enqueue(w.root, str(repo), [name, "x"], ENV, [], 5400, "", None, w.t)["id"])
    assert gate.serve(w.root, w.fx(loads=calls((0, 0, 0)), dirty=lambda repo: 0,
                                   load=lambda: 0.0, cores=lambda: 8)) == 0
    assert [w.result(g)["beside"] for g in ids] == [[], ids[:1], ids[:2]]
    assert w.result(ids[2])["dirty"] == {"start": 0, "end": 0}


# ---- R1 and R3: a side that cannot be read ----------------------------------

@pytest.mark.parametrize("how", ["no work tree", "git exits 128", "git sleeps past the wait"])
def test_gl1_2_a_dirty_side_unread_is_null_and_the_job_stands(w, tmp_path, monkeypatch, how):
    a = w.put("a")                                           # the key read with the real git
    w.plan = {"a": (3, 5)}
    if how != "no work tree":
        git_repo(w.repo, tmp_path)
        (w.repo / "loose").write_text("x\n")
        body = "exit 128" if how == "git exits 128" else "sleep 5"
        monkeypatch.setenv("PATH", f"{fake_git(tmp_path, body)}:{os.environ['PATH']}")
        monkeypatch.setattr(gate, "GIT_WAIT", 0.5)
    t = time.monotonic()
    assert gate.serve(w.root, w.fx(head=lambda repo: None)) == 0
    took = time.monotonic() - t
    r = w.result(a["id"])
    assert r["dirty"] == {"start": None, "end": None}
    assert (r["exit"], r["seconds"]) == (5, 3)
    assert took < 4, took                                   # two reads, each cut at GIT_WAIT
    assert w.logs == []


def test_gl1_2_dirty_reads_as_head_does(w, tmp_path, monkeypatch):
    assert gate._dirty(str(tmp_path / "gone")) is None and gate._dirty(str(w.repo)) is None
    git_repo(w.repo, tmp_path)
    assert gate._dirty(str(w.repo)) == 0
    (w.repo / "base").write_text("changed\n")
    (w.repo / "sub").mkdir()
    (w.repo / "sub" / "one").write_text("1\n")
    (w.repo / "sub" / "two").write_text("2\n")
    assert gate._dirty(str(w.repo)) == 3                    # every untracked file, not the dir
    other = tmp_path / "elsewhere"                           # the caller's GIT_* is dropped
    other.mkdir()
    git_repo(other, tmp_path)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert gate._dirty(str(w.repo)) == 3
    assert not (w.repo / ".git" / "index.lock").exists()


# ---- R2: a job the runner did not start and end itself ----------------------

def test_gl1_3_a_command_that_cannot_start_and_a_recovered_job(w, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    w.plan = {"a": (100, 0), "b": OSError("no such command")}
    a = w.put("a")
    b = gate.enqueue(w.root, str(other), ["b", "x"], ENV, [], 5400, "", None, w.t)
    assert gate.serve(w.root, w.fx(loads=calls((1, 1, 1)), dirty=lambda repo: 7,
                                   load=lambda: 0.0, cores=lambda: 8)) == 0
    rb = w.result(b["id"])
    assert rb["exit"] == 127 and list(rb) == list(gate.RESULT_KEYS)
    assert rb["load"] == {"start": [1.0, 1.0, 1.0], "end": None}   # no child was reaped
    assert rb["dirty"] == {"start": 7, "end": None} and rb["beside"] == [a["id"]]
    c = w.put("c")
    g = w.root / "gate"
    (g / "runner.json").write_text(json.dumps({"pid": 99999999, "since": T0,
                                               "running": [{"id": c["id"], "pgid": None}]}))
    assert gate.serve(w.root, w.fx(loads=calls((1, 1, 1)), dirty=lambda repo: 7)) == 0
    rc_ = w.result(c["id"])
    assert (rc_["exit"], rc_["cut"]) == (125, gate.CUT_DIED) and w.spawned[-1][0][0] != "c"
    assert list(rc_) == list(gate.RESULT_KEYS)
    assert {k: rc_[k] for k in NEW} == NULLS


def test_gl1_3_a_job_never_started_holds_nulls(w, tmp_path):
    lock = tmp_path / "held.lock"
    lock.mkdir()
    a = w.put("a", locks=[str(lock)], wall=30)
    assert gate.serve(w.root, w.fx(loads=calls((1, 1, 1)), dirty=lambda repo: 7)) == 0
    r = w.result(a["id"])
    assert r["exit"] == 126 and {k: r[k] for k in NEW} == NULLS


# ---- R3: a read that raises -------------------------------------------------

def test_gl1_4_a_load_read_that_raises_is_a_null_and_one_log_line(w):
    w.plan = {"a": (3, 0)}
    a = w.put("a")
    loads = calls(OSError("no load here"), (0.5, 0.25, 0.125))
    assert gate.serve(w.root, w.fx(loads=loads, dirty=lambda repo: 1)) == 0
    r = w.result(a["id"])
    assert r["load"] == {"start": None, "end": [0.5, 0.25, 0.12]}
    assert (r["exit"], r["seconds"], len(w.spawned)) == (0, 3, 1)
    assert len(w.logs) == 1 and a["id"] in w.logs[0] and "no load here" in w.logs[0]


def test_gl1_4_a_dirty_read_that_raises_and_odd_values(w):
    w.plan = {"a": (3, 0)}
    a = w.put("a")
    dirty = calls(RuntimeError("git fell over"), 4)
    assert gate.serve(w.root, w.fx(loads=calls((1, 2)), dirty=dirty)) == 0
    r = w.result(a["id"])
    assert r["dirty"] == {"start": None, "end": 4} and r["load"] == NULLS["load"]
    assert r["exit"] == 0 and len(w.logs) == 1 and "git fell over" in w.logs[0]
    for odd in ((1, 2, float("nan")), (1, 2, -1), "1 2 3", (True, 1, 1), None):
        b = w.put("b")
        assert gate.serve(w.root, w.fx(loads=calls(odd), dirty=calls(-1))) == 0
        rb = w.result(b["id"])
        assert rb["load"] == NULLS["load"] and rb["dirty"] == NULLS["dirty"], odd


# ---- R4: status --json ------------------------------------------------------

def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def test_gl1_5_status_json_done_items_carry_the_three(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    from claude_session import resolver
    root = resolver.state_dir(os.environ)
    old, new = "20261109-120000-1", "20261109-120000-2"
    base = {"repo": "/r/crate", "command": ["make", "check"], "exit": 0, "started": T0,
            "ended": T0 + 90.0, "seconds": 90.0, "caller": None, "cut": None,
            "head": "a" * 40, "key": "k"}
    machine = {"load": {"start": [1.5, 1.0, 0.5], "end": [2.0, 1.5, 1.0]},
               "beside": ["20261109-115900-9"], "dirty": {"start": 0, "end": 1}}
    for gid, more in ((old, {}), (new, machine)):
        gate.entry_dir(root, gid).mkdir(parents=True)
        gate.result_path(root, gid).write_text(json.dumps(
            {"id": gid, **base, "log": str(gate.entry_dir(root, gid) / "log"), **more}))
    rc, out, _ = run_cli("gate", "status", "--json")
    done = json.loads(out)["done"]
    assert rc == 0 and [d["id"] for d in done] == [new, old]
    assert list(done[0]) == ["id", "repo", "exit", "seconds", "cut", *NEW]
    assert {k: done[0][k] for k in NEW} == machine
    assert {k: done[1][k] for k in NEW} == {"load": None, "beside": None, "dirty": None}
    rc, out, _ = run_cli("gate", "status")
    assert (rc, out) == (0, f"done {new} /r/crate exit 0 2 min\n"
                            f"done {old} /r/crate exit 0 2 min\nrunner: none\n")


def test_gl1_5_wait_line_and_inbox_keep_their_bytes(w):
    w.plan = {"a": (60, 0)}
    a = w.put("a", caller="sess-1")
    gate.serve(w.root, w.fx(loads=calls((1, 1, 1)), dirty=lambda repo: 2))
    r = w.result(a["id"])
    assert gate.wait_line(r) == (f"gate {a['id']} {a['repo']}: exit 0 in 1 min; "
                                 f"log {r['log']}")
    inbox = json.loads((w.root / "sessions" / "sess-1" / "inbox" / f"{a['id']}.json").read_text())
    assert list(inbox) == list(gate.INBOX_KEYS) == ["at", "kind", "id", "repo", "exit",
                                                    "seconds", "log"]


# ---- R5: unrun on the land line ---------------------------------------------

class Crate:
    """A made-up repo `crate` on main, a branch `work` one commit ahead in its worktree, the
    check's recipe given; temp HOME, state and git config, a job's mark, nothing queued."""

    def __init__(self, tmp, recipe):
        self.tmp = tmp
        cfg = tmp / "gitconfig"
        cfg.write_text("[user]\n\tname = t\n\temail = t@" + "example.invalid\n"
                       "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        self.env = {**os.environ, "HOME": str(tmp), "XDG_STATE_HOME": str(tmp / "state"),
                    "XDG_CONFIG_HOME": str(tmp / "config"), "GIT_CONFIG_GLOBAL": str(cfg),
                    "GIT_CONFIG_NOSYSTEM": "1", gate.JOB_MARK: "20261110-000000-1"}
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "CLAUDE_CODE_SESSION_ID"):
            self.env.pop(name, None)
        self.repo = tmp / "crate"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        (self.repo / ".gitignore").write_text(".claude/worktrees/\n")
        (self.repo / "Makefile").write_text("check:\n" + "".join(f"\t{x}\n" for x in recipe))
        self.git(self.repo, "add", ".gitignore", "Makefile")
        self.git(self.repo, "commit", "-qm", "base")
        self.tree = self.repo / ".claude" / "worktrees" / "work"
        self.git(self.repo, "worktree", "add", "-q", "-b", "work", str(self.tree), "main")
        (self.tree / "f").write_text("x\n")
        self.git(self.tree, "add", "f")
        self.git(self.tree, "commit", "-qm", "f")
        self.sha = self.git(self.tree, "rev-parse", "HEAD")
        self.msg = tmp / "msg"
        self.msg.write_text("Merge work: a made-up landing\n\nOne line.\n")

    def git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def argv(self):
        return [sys.executable, str(RUNNER), "gate", "land", "--in-job", str(self.repo), "work",
                self.sha, str(self.msg)]

    def land(self):
        p = subprocess.run(self.argv(), env=self.env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr


@pytest.mark.parametrize("why", ["lock", "load", "wall"])
def test_gl1_6_a_refused_check_reads_unrun(tmp_path, why):
    crate = Crate(tmp_path, ["@echo one", "@echo two >&2", f"@echo 'bounded: stop: {why}' >&2; exit 3"])
    rc, out, err = crate.land()
    assert (rc, out) == (2, f"land crate: red check exit 2, unrun {why}\n"), err
    tail = err.splitlines()[-2:]
    assert tail[0] == f"bounded: stop: {why}" and tail[1].startswith("make: ")   # make writes after


@pytest.mark.parametrize("lines,want", [
    (["bounded: nested stop: wall"], ""),
    ([], ""),
    (["bounded: stop: load", "bounded: nested stop: wall"], ""),
    (["bounded: nested stop: wall", "bounded: stop: wall"], ", unrun wall"),
    (["bounded: stop: lock", "a test said more"], ", unrun lock"),
    (["bounded: stop: loads"], ""),
    (["  bounded: stop: load"], ""),
], ids=["nested", "none", "nested-last", "stop-last", "a-line-after", "not-a-stop", "indented"])
def test_gl1_6_only_the_last_bounded_line_counts(tmp_path, lines, want):
    recipe = ["@echo one"] + [f"@echo '{x}'" for x in lines] + ["@exit 3"]
    rc, out, err = Crate(tmp_path, recipe).land()
    assert (rc, out) == (2, f"land crate: red check exit 2{want}\n"), err


def test_gl1_6_a_stop_line_on_a_green_check_is_no_red(tmp_path):
    crate = Crate(tmp_path, ["@echo 'bounded: stop: load' >&2"])
    rc, out, err = crate.land()
    assert (rc, out) == (0, f"land crate: ok {crate.sha}, main readied\n"), err


def test_gl1_7_the_checks_output_reaches_the_log_as_it_comes_in_order(tmp_path):
    go = tmp_path / "go"
    recipe = ['@i=1; while [ $$i -le 20 ]; do echo out$$i; echo err$$i >&2; i=$$((i+1)); done',
              "@printf part; sleep 0.2; printf 'ial\\n' >&2",
              f'@echo early >&2; n=0; while [ ! -e "{go}" ] && [ $$n -lt 400 ]; do '
              f'sleep 0.05; n=$$((n+1)); done; [ $$n -lt 400 ] || echo "never went"',
              "@echo late", "@echo last >&2; exit 3"]
    crate = Crate(tmp_path, recipe)
    log = tmp_path / "job.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)  # as the runner opens it
    try:
        p = subprocess.Popen(crate.argv(), env=crate.env, stdin=subprocess.DEVNULL, stdout=fd,
                             stderr=subprocess.STDOUT)
    finally:
        os.close(fd)

    def watch():
        for _ in range(400):
            if "early" in log.read_text():
                go.write_text("")
                return
            time.sleep(0.05)
    t = threading.Thread(target=watch)
    t.start()
    assert p.wait(timeout=120) == 2
    t.join()
    lines = log.read_text().splitlines()
    i = lines.index(f"land-step: check: make check in {crate.tree}")
    want = [x for n in range(1, 21) for x in (f"out{n}", f"err{n}")] + [
        "partial", "early", "late", "last", "make: *** [check] Error 3",
        "land crate: red check exit 2"]
    assert lines[i + 1:] == want
