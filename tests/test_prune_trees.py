"""claude_session.prune (F8): an install keeps the new tree, every tree a live process
names in its environment or command line, and the newest few; it prunes the rest, and when
it cannot see the processes' environments it prunes nothing."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "plugin" / "lib"
NAMES = ["t0", "t1", "t2", "t3", "t4", "t5"]                 # oldest first


@pytest.fixture
def share(tmp_path):
    s = tmp_path / "share"
    for i, n in enumerate(NAMES):
        (s / n / "claude_session").mkdir(parents=True)
        os.utime(s / n, (1_000_000 + i, 1_000_000 + i))
    return s


def _prune(share, new, *extra):
    return subprocess.run([sys.executable, "-m", "claude_session.prune", "--share", str(share),
                           "--new", new, *extra], capture_output=True, text=True, timeout=60,
                          env=dict(os.environ, PYTHONPATH=str(LIB)))


def _left(share):
    return sorted(p.name for p in share.iterdir())


def _stub(tmp_path, body):
    ps = tmp_path / "ps"
    ps.write_text("#!/bin/sh\n" + body)
    ps.chmod(0o755)
    return str(ps)


def test_keeps_new_live_and_newest(share):
    # t1 is named in a live PYTHONPATH (with another entry after it); t2x, a name t2 is a
    # prefix of, is on a live command line and keeps nothing; t0 is the new tree, re-installed
    readers = [
        subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                         stdin=subprocess.PIPE,
                         env=dict(os.environ, PYTHONPATH=f"{share}/t1:{share.parent}/x")),
        subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()", f"{share}/t2x"],
                         stdin=subprocess.PIPE),
    ]
    try:
        r = _prune(share, "t0")
    finally:
        for p in readers:
            p.stdin.close()
            p.wait(timeout=30)
    assert r.returncode == 0, r.stderr
    assert _left(share) == ["t0", "t1", "t4", "t5"]
    assert "removed 2" in r.stdout and "1 live" in r.stdout, r.stdout


def test_keep_count(share):
    r = _prune(share, "t5", "--keep", "1")
    assert r.returncode == 0, r.stderr
    assert _left(share) == ["t5"]


@pytest.mark.parametrize("body", [
    "exit 1\n",                                     # ps fails
    "echo '    1 /sbin/launchd'\n",                 # ps runs, but no environment is seen
    "",                                             # ps prints nothing
])
def test_fails_safe(share, tmp_path, body):
    r = _prune(share, "t5", "--keep", "1", "--ps", _stub(tmp_path, body))
    assert r.returncode == 0, r.stderr
    assert _left(share) == NAMES
    assert "keeping every tree" in r.stderr, r.stderr


def test_missing_ps_fails_safe(share, tmp_path):
    r = _prune(share, "t5", "--keep", "1", "--ps", str(tmp_path / "no-such-ps"))
    assert (r.returncode, _left(share)) == (0, NAMES)
    assert "keeping every tree" in r.stderr


def test_the_new_tree_must_exist(share):
    r = _prune(share, "nope")
    assert r.returncode == 2 and _left(share) == NAMES
    assert "prune-trees: nope is not a tree" in r.stderr, r.stderr


def test_f2_live_paths_are_compared_by_realpath(share, tmp_path):
    # F2 (round one): a holder spells the share through a symlink, or with a doubled slash;
    # --share is the real path. Both trees are live, so both stay.
    (tmp_path / "link").symlink_to(share.parent)
    holder = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE,
        env=dict(os.environ,
                 PYTHONPATH=f"{tmp_path}/link/share/t1:{share.parent}//share/t2/claude_session"))
    try:
        r = _prune(share, "t5", "--keep", "1")
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
    assert r.returncode == 0, r.stderr
    assert _left(share) == ["t1", "t2", "t5"], r.stdout
    assert "2 live" in r.stdout, r.stdout


# ---- sc3 act 3: F8 under the new form ---------------------------------------------------

APPLE = "/usr/bin/python3"
READS = "import sys; sys.stdin.read()"


@pytest.mark.skipif(not os.access(APPLE, os.X_OK), reason="no /usr/bin/python3")
@pytest.mark.parametrize("form", ("command line", "PYTHONPATH"))
def test_a_live_process_under_apples_python_keeps_its_tree(share, form, tmp_path):
    # t0 is the oldest: only a live process can keep it. t1 is next, and goes.
    runner = share / "t0" / "agentik-session"
    runner.write_text(READS + "\n")
    os.utime(share / "t0", (1_000_000, 1_000_000))
    env = dict(os.environ)
    if form == "command line":      # the launcher's own words, `run` and all
        argv = [APPLE, "-I", "-X", f"pycache_prefix={tmp_path}/c", str(runner), "run", "--chain", "x"]
    else:                           # an old launcher, which runs for a day or more
        argv = [APPLE, "-c", READS]
        env["PYTHONPATH"] = str(share / "t0")
    live = subprocess.Popen(argv, stdin=subprocess.PIPE, env=env)
    try:
        assert _wait_for_ps(live.pid, argv[-1] if form == "command line" else "c")
        r = _prune(share, "t5")
        assert r.returncode == 0, r.stderr
        assert _left(share) == ["t0", "t3", "t4", "t5"]
    finally:
        live.stdin.close()
        live.wait(timeout=30)
    assert _prune(share, "t5").returncode == 0
    assert _left(share) == ["t3", "t4", "t5"]


def _wait_for_ps(pid, word):
    """Apple's stub execs the real Python: wait until ps reads the process past it."""
    import time
    for _ in range(100):
        line = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True,
                              text=True).stdout
        if word in line and "/usr/bin/python3" not in line.split()[:1]:
            return True
        time.sleep(0.05)
    return False


def test_a_ps_that_fails_keeps_all(share, tmp_path):
    ps = tmp_path / "ps"
    ps.write_text("#!/bin/sh\nexit 1\n")
    ps.chmod(0o755)
    r = _prune(share, "t5", "--ps", str(ps))
    assert r.returncode == 0 and "keeping every tree" in r.stderr
    assert _left(share) == NAMES


def test_it_never_removes_the_tree_it_just_wrote(share):
    os.utime(share / "t0", (1, 1))      # the oldest of all
    assert _prune(share, "t0", "--keep", "1").returncode == 0
    assert _left(share) == ["t0"]


def test_the_installs_own_dot_entries_are_no_trees(share):
    (share / ".lock").write_text("")
    (share / ".tmp-abc").mkdir()
    os.utime(share / ".lock", (1, 1))
    os.utime(share / ".tmp-abc", (1, 1))
    assert _prune(share, "t5").returncode == 0
    assert sorted(p.name for p in share.iterdir()) == [".lock", ".tmp-abc", "t3", "t4", "t5"]
