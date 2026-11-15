"""rw3-gate-repo: `gate status --repo PATH [--json]`, a folder's jobs and every result the gate
keeps for it, each with its head (packet rw3-gate-repo, R1 to R9). Every result is written by
the test in the per-test temp state root; no runner is started (`spawn_serve` is stubbed), and
the repos (`crate`, its worktree `p1-crate`, `basket`) are made up."""
import hashlib
import io
import json
import os
import shutil
import subprocess
import time
from contextlib import redirect_stderr, redirect_stdout

import pytest

from claude_session import cli, gate, resolver


@pytest.fixture
def root(monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return resolver.state_dir(os.environ)


@pytest.fixture
def tree(tmp_path):
    """crate, its worktree folder and basket, as real paths (no git: see `git_tree`)."""
    base = tmp_path.resolve()
    crate = base / "crate"
    wt = crate / ".claude" / "worktrees" / "p1-crate"
    basket = base / "basket"
    for d in (wt, basket):
        d.mkdir(parents=True)
    return {"crate": str(crate), "wt": str(wt), "basket": str(basket), "base": base}


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def sha(n):
    return hashlib.sha1(str(n).encode()).hexdigest()


def gid(n):
    return f"20261114-120000-{n}"


def put(root, n, repo, *, head="auto", key="k", command=None, ended=None, **more):
    """One result.json, as `_finish` writes it; `head="auto"` is `sha(n)`."""
    g = gid(n)
    ended = time.time() - 60 if ended is None else ended
    res = {"id": g, "repo": repo, "command": command or ["make", "check"], "exit": 0,
           "started": ended - 90.0, "ended": ended, "seconds": 90.0,
           "log": str(gate.entry_dir(root, g) / "log"), "caller": None, "cut": None,
           "head": sha(n) if head == "auto" else head, "key": key, **more}
    gate.entry_dir(root, g).mkdir(parents=True, exist_ok=True)
    gate.result_path(root, g).write_text(json.dumps(res, indent=1) + "\n")
    return g


def done_line(n, repo, tail=""):
    return f"done {gid(n)} {repo} exit 0 1.5 min head {sha(n)[:7]}{tail}"


def mixed(root, t):
    """Eight results of the worktree among thirty of the other two folders."""
    mine, n = [], 0
    for i in range(38):
        n += 1
        if i % 5 == 2 and len(mine) < 8:
            put(root, n, t["wt"])
            mine.append(n)
        else:
            put(root, n, t["basket"] if i % 2 else t["crate"])
    assert len(mine) == 8 and n - 8 == 30
    return mine


# ---- 1, 2: the eight, by any spelling of the path ----------------------------

def test_rw3_1_the_worktree_lists_its_eight_newest_first(root, tree):
    mine = mixed(root, tree)
    put(root, 90, tree["wt"], ended=time.time() - gate.KEEP - 100)     # past KEEP: not listed
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"])
    assert rc == 0
    assert out.splitlines() == [done_line(n, tree["wt"]) for n in reversed(mine)] + ["runner: none"]


def test_rw3_2_symlink_trailing_slash_and_removed(root, tree):
    mine = mixed(root, tree)
    want = [done_line(n, tree["wt"]) for n in reversed(mine)] + ["runner: none"]
    link = tree["base"] / "link"
    link.symlink_to(tree["wt"])
    for path in (str(link), tree["wt"] + "/", str(link) + "/"):
        rc, out, _ = run_cli("gate", "status", "--repo", path)
        assert (rc, out.splitlines()) == (0, want), path
    shutil.rmtree(tree["wt"])
    for path in (tree["wt"], tree["wt"] + "/", tree["wt"] + "/./"):
        rc, out, _ = run_cli("gate", "status", "--repo", path)
        assert (rc, out.splitlines()) == (0, want), path


# ---- 3: a main checkout and its worktree share a key, not a list -------------

def test_rw3_3_the_main_checkout_lists_its_own(root, tree):
    put(root, 1, tree["crate"], key="one")
    put(root, 2, tree["wt"], key="one")
    put(root, 3, tree["crate"], key="one")
    rc, out, _ = run_cli("gate", "status", "--repo", tree["crate"])
    assert (rc, out.splitlines()) == (0, [done_line(3, tree["crate"]), done_line(1, tree["crate"]),
                                          "runner: none"])


# ---- 4: a landing filed under the main checkout ------------------------------

def git_env(home):
    return {"PATH": os.environ["PATH"], "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1"}


def git(path, *argv, home):
    g = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@" + "example.invalid"]
    return subprocess.run(g + list(argv), check=True, env=git_env(home), capture_output=True,
                          text=True).stdout.strip()


@pytest.fixture
def git_tree(tmp_path):
    base = tmp_path.resolve()
    crate, basket = base / "crate", base / "basket"
    for d in (crate, basket):
        d.mkdir()
        git(d, "init", "-q", "-b", "main", home=base)
        (d / "base").write_text("b\n")
        git(d, "add", "base", home=base)
        git(d, "commit", "-qm", "base", home=base)
    wt = crate / ".claude" / "worktrees" / "p1-crate"
    loose = crate / ".claude" / "worktrees" / "p3-crate"
    git(crate, "worktree", "add", "-q", "-b", "p1-crate", str(wt), "main", home=base)
    git(crate, "worktree", "add", "-q", "--detach", str(loose), "main", home=base)
    return {"crate": str(crate), "wt": str(wt), "loose": str(loose), "basket": str(basket)}


def landing(repo, branch):
    return [*gate.self_argv(), "gate", "land", "--in-job", repo, branch, "f" * 40, "/x/merge.md"]


def test_rw3_4_a_red_landing_shows_under_its_worktree(root, git_tree):
    t = git_tree
    key = gate.repo_key(t["crate"])
    assert key == gate.repo_key(t["wt"])
    put(root, 1, t["crate"], key=key, command=landing(t["crate"], "p1-crate"), exit=1)
    put(root, 2, t["crate"], key=key, command=landing(t["crate"], "p2-other"), exit=1)
    put(root, 3, t["basket"], key=gate.repo_key(t["basket"]),
        command=landing(t["basket"], "p1-crate"), exit=1)
    put(root, 4, t["crate"], key=key, command=landing(t["crate"], "p3-crate"), exit=1)
    put(root, 5, t["wt"], key=key)
    rc, out, _ = run_cli("gate", "status", "--repo", t["wt"])
    assert rc == 0
    assert out.splitlines() == [
        done_line(5, t["wt"]),
        f"done {gid(1)} {t['crate']} exit 1 1.5 min head {sha(1)[:7]} land p1-crate",
        "runner: none"]
    rc, out, _ = run_cli("gate", "status", "--repo", t["loose"])     # detached: no branch
    assert (rc, out.splitlines()) == (0, [f"none for {t['loose']}", "runner: none"])
    rc, out, _ = run_cli("gate", "status", "--repo", t["crate"])     # its own four, each a land
    assert rc == 0 and [x.split()[1] for x in out.splitlines()[:-1]] == [gid(4), gid(2), gid(1)]
    assert out.splitlines()[0].endswith(" land p3-crate")


def test_rw3_4b_git_that_will_not_run_matches_no_landing(root, git_tree, monkeypatch):
    t = git_tree
    key = gate.repo_key(t["crate"])
    put(root, 1, t["crate"], key=key, command=landing(t["crate"], "p1-crate"), exit=1)
    monkeypatch.setenv("PATH", "/nonexistent")
    rc, out, _ = run_cli("gate", "status", "--repo", t["wt"])
    assert (rc, out.splitlines()) == (0, [f"none for {t['wt']}", "runner: none"])


# ---- 5: dirty ----------------------------------------------------------------

def test_rw3_5_dirty_above_zero_alone(root, tree):
    put(root, 1, tree["wt"], dirty={"start": 3, "end": 4})
    put(root, 2, tree["wt"], dirty={"start": 0, "end": 2})
    put(root, 3, tree["wt"], dirty={"start": None, "end": None})
    put(root, 4, tree["wt"])
    put(root, 5, tree["wt"], dirty=None)
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"])
    assert (rc, out.splitlines()) == (0, [done_line(n, tree["wt"]) for n in (5, 4, 3, 2)]
                                      + [done_line(1, tree["wt"], " dirty 3"), "runner: none"])


# ---- 6: twenty lines, then the rest by --json --------------------------------

def test_rw3_6_twenty_then_the_more_line(root, tree):
    for n in range(1, 26):
        put(root, n, tree["wt"])
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"])
    lines = out.splitlines()
    assert rc == 0 and len(lines) == 22
    assert lines[:20] == [done_line(n, tree["wt"]) for n in range(25, 5, -1)]
    assert lines[20:] == [f"5 more: agentik session gate status --repo {tree['wt']} --json",
                          "runner: none"]
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"], "--json")
    assert rc == 0 and [d["id"] for d in json.loads(out)["done"]] == [gid(n) for n in range(25, 0, -1)]


# ---- 7: nothing for the path -------------------------------------------------

def test_rw3_7_none_for_the_path(root, tree):
    put(root, 1, tree["basket"])
    gone = str(tree["base"] / "nowhere")
    for path, shown in ((tree["wt"], tree["wt"]), (gone, gone)):
        rc, out, _ = run_cli("gate", "status", "--repo", path)
        assert (rc, out) == (0, f"none for {shown}\nrunner: none\n")
    rc, _, err = run_cli("gate", "status", "--repo", "")
    assert rc == 2 and "--repo" in err


# ---- 8: running and queued, as today's lines, first --------------------------

def entry(root, n, repo, key):
    g = gid(n)
    e = {"id": g, "repo": repo, "command": ["make", "check"], "env": {}, "locks": [],
         "wall": 60, "label": f"l{n}", "caller": None, "queued": time.time() - 30, "key": key,
         "key_name": os.path.basename(repo)}
    q = gate.gate_dir(root) / "queue"
    q.mkdir(parents=True, exist_ok=True)
    (q / f"{g}.json").write_text(json.dumps(e))
    return g


def test_rw3_8_running_and_queued_of_the_path_first(root, tree):
    run_w, run_b = entry(root, 11, tree["wt"], "kw"), entry(root, 12, tree["basket"], "kb")
    q_w, q_b = entry(root, 13, tree["wt"], "kw"), entry(root, 14, tree["basket"], "kb")
    gate.entry_dir(root, run_w).mkdir(parents=True)
    gate.entry_dir(root, run_b).mkdir(parents=True)
    (gate.gate_dir(root) / "runner.json").write_text(json.dumps(
        {"pid": os.getpid(), "since": time.time() - 100,
         "running": [{"id": run_w, "pgid": None}, {"id": run_b, "pgid": None}]}))
    put(root, 1, tree["wt"])
    rc, full, _ = run_cli("gate", "status")
    assert rc == 0
    today = {x.split()[1]: x for x in full.splitlines() if x.split()[0] in ("running", "queued")}
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"])
    lines = out.splitlines()
    assert rc == 0 and lines[:2] == [today[run_w], today[q_w]]
    assert lines[2] == done_line(1, tree["wt"]) and lines[3].startswith("runner: pid ")
    assert len(lines) == 4 and run_b not in out and q_b not in out
    rc, out, _ = run_cli("gate", "status", "--repo", tree["wt"], "--json")
    d = json.loads(out)
    assert [x["id"] for x in d["running"]] == [run_w] and [x["id"] for x in d["queued"]] == [q_w]


# ---- 9: --json ---------------------------------------------------------------

def test_rw3_9_json_repo_head_and_land(root, tree):
    put(root, 1, tree["wt"], head=None)
    put(root, 2, tree["crate"], command=landing(tree["crate"], "p9-x"))
    for n in range(3, 9):
        put(root, n, tree["basket"])
    link = tree["base"] / "via"
    link.symlink_to(tree["wt"])
    rc, out, _ = run_cli("gate", "status", "--repo", str(link) + "/", "--json")
    d = json.loads(out)
    assert rc == 0 and d["schema"] == "agentik.session.gate/1" and d["repo"] == tree["wt"]
    assert d["done"] == [{"id": gid(1), "repo": tree["wt"], "exit": 0, "seconds": 90.0,
                          "cut": None, "load": None, "beside": None, "dirty": None,
                          "head": None, "land": None}]
    assert "est" in d and "runner" in d
    rc, out, _ = run_cli("gate", "status", "--json")
    d = json.loads(out)
    assert rc == 0 and "repo" not in d and [x["id"] for x in d["done"]] == [gid(n) for n in (8, 7, 6, 5, 4)]
    assert all(list(x)[-2:] == ["head", "land"] for x in d["done"])
    assert d["done"][0]["head"] == sha(8) and d["done"][0]["land"] is None
    rc, out, _ = run_cli("gate", "status", "--repo", tree["crate"], "--json")
    assert json.loads(out)["done"][0]["land"] == "p9-x"


# ---- 10: without the flag, the pin's bytes; a file that will not read --------

def test_rw3_10_without_the_flag_the_pins_bytes(root, tree):
    for n in range(1, 8):
        put(root, n, tree["wt"] if n % 2 else tree["basket"], exit=n, seconds=60.0 * n,
            dirty={"start": n, "end": 0})
    gate.result_path(root, gid(6)).write_text('{"id": "' + gid(6) + '", "re')     # cut short
    gate.result_path(root, gid(5)).write_text("[1, 2]\n")                        # not an object
    gate.entry_dir(root, gid(8)).mkdir()                                         # no result
    rc, out, _ = run_cli("gate", "status")
    w, b = tree["wt"], tree["basket"]
    assert (rc, out) == (0, f"done {gid(7)} {w} exit 7 7 min\n"
                            f"done {gid(4)} {b} exit 4 4 min\n"
                            f"done {gid(3)} {w} exit 3 3 min\n"
                            f"done {gid(2)} {b} exit 2 2 min\n"
                            f"done {gid(1)} {w} exit 1 1 min\n"
                            "runner: none\n")
    rc, out, _ = run_cli("gate", "status", "--repo", w)
    assert (rc, out.splitlines()) == (0, [
        f"done {gid(7)} {w} exit 7 7.0 min head {sha(7)[:7]} dirty 7",
        f"done {gid(3)} {w} exit 3 3.0 min head {sha(3)[:7]} dirty 3",
        f"done {gid(1)} {w} exit 1 1.0 min head {sha(1)[:7]} dirty 1", "runner: none"])
    rc, out, _ = run_cli("gate", "status", "--repo", w, "--json")
    assert rc == 0 and [x["id"] for x in json.loads(out)["done"]] == [gid(7), gid(3), gid(1)]
