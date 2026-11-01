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
