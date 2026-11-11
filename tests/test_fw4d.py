"""Packet FW4d (hq design/08 section 5 row 5, section 6 item 7): `agentik session commit <paths...>
--check <cmd> --message-file <f>`: add by path, check, commit on green, the check's code on red,
and the index as it was found on every red and refusal. Each test is red at 36c84ea (alpha.60):
the verb does not exist. Every repo and queue is under the test's temp roots."""
import ast
import contextlib
import fcntl
import io
import os
import signal
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, resolver
from claude_session import commit as verb

ROOT = Path(__file__).resolve().parents[1]


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def git(cwd, *args):
    p = subprocess.run(["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


class Repo:
    """A scratch repo on main: a.txt and b.txt committed, a message file beside it."""

    def __init__(self, tmp):
        self.path = tmp / "scratch"
        self.path.mkdir()
        git(self.path, "init", "-q", "-b", "main")
        for n in ("a.txt", "b.txt"):
            (self.path / n).write_text("base\n")
        (self.path / "Makefile").write_text("check:\n\t@test ! -e RED\n")
        git(self.path, "add", "a.txt", "b.txt", "Makefile")
        git(self.path, "commit", "-qm", "base")
        self.msg = tmp / "msg"
        self.msg.write_text("the work\n\nIts body.\n")

    def write(self, rel, text):
        (self.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.path / rel).write_text(text)

    def head(self):
        return git(self.path, "rev-parse", "HEAD")

    def index(self):
        return git(self.path, "ls-files", "-s")

    def commit(self, *argv, check="true"):
        return run("commit", *argv, "--check", check, "--message-file", str(self.msg))

    def nested(self, rel):
        d = self.path / rel
        d.mkdir(parents=True)
        git(d, "init", "-q")
        (d / "f").write_text("x\n")
        git(d, "add", "f")
        git(d, "commit", "-qm", "x")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    r = Repo(tmp_path)
    monkeypatch.chdir(r.path)
    return r


def refused(r, rc, out, err, *words):
    assert (rc, out) == (2, ""), err
    for w in words:
        assert w in err, (w, err)


def test_fw4d_t1_green_commits_the_named_paths_with_the_message(repo):
    repo.write("a.txt", "mine\n")
    repo.write("c.txt", "new\n")
    rc, out, err = repo.commit("a.txt", "c.txt")
    assert (rc, out) == (0, f"commit scratch: ok {repo.head()}\n"), err
    assert git(repo.path, "show", "--name-only", "--format=", "HEAD").split() == ["a.txt", "c.txt"]
    assert git(repo.path, "log", "-1", "--format=%B") == "the work\n\nIts body."
    assert git(repo.path, "status", "--porcelain") == ""


def test_fw4d_t2_a_path_someone_staged_stays_staged_and_out(repo):
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    theirs = git(repo.path, "ls-files", "-s", "b.txt")
    repo.write("a.txt", "mine\n")
    rc, out, _ = repo.commit("a.txt")
    assert rc == 0 and git(repo.path, "show", "--name-only", "--format=", "HEAD") == "a.txt"
    assert git(repo.path, "ls-files", "-s", "b.txt") == theirs
    assert git(repo.path, "diff", "--cached", "--name-only") == "b.txt"


def test_fw4d_t3_a_red_check_exits_its_code_and_leaves_the_index_as_found(repo):
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    repo.write("a.txt", "staged earlier\n")
    git(repo.path, "add", "a.txt")
    repo.write("a.txt", "edited since\n")
    repo.write("c.txt", "new\n")
    before, head = repo.index(), repo.head()
    rc, out, err = repo.commit("a.txt", "c.txt", check="sh -c 'exit 3'")
    assert (rc, out) == (3, "commit scratch: red check exit 3\n"), err
    assert (repo.index(), repo.head()) == (before, head)
    assert (repo.path / "a.txt").read_text() == "edited since\n"
    rc, out, _ = repo.commit("a.txt", check="no-such-command-fw4d")
    assert (rc, out) == (127, "commit scratch: red check exit 127\n") and repo.index() == before


def test_fw4d_t4_a_nested_repo_is_refused_by_name(repo):
    repo.nested("probes/fx/one")
    repo.nested("probes/fx/two")
    repo.write("probes/run.sh", "echo\n")
    before = repo.index()
    for path in ("probes", "probes/fx", "probes/fx/one"):
        rc, out, err = repo.commit(path)
        refused(repo, rc, out, err, "gitlink", "probes/fx/one/")
        assert repo.index() == before and "160000" not in repo.index()
    repo.write(".gitignore", "probes/fx/\n")
    rc, out, err = repo.commit("probes", ".gitignore")       # an ignored one is never added
    assert rc == 0, err
    assert "160000" not in repo.index() and "probes/run.sh" in repo.index()


def test_fw4d_t5_a_path_outside_the_repo_is_refused(repo, tmp_path):
    (tmp_path / "out.txt").write_text("o\n")
    for path in ("../out.txt", str(tmp_path / "out.txt"), "a.txt/../../out.txt"):
        rc, out, err = repo.commit(path)
        refused(repo, rc, out, err, "outside the repo")


@pytest.mark.parametrize("argv,word", [(["-A"], "-A"), (["--all"], "-A"), (["-u"], "-u"),
                                       (["--update", "a.txt"], "-u"), (["."], "whole tree"),
                                       ([], "name each path")])
def test_fw4d_t6_the_sweeping_forms_are_refused(repo, argv, word):
    repo.write("a.txt", "mine\n")
    before = repo.index()
    rc, out, err = repo.commit(*argv)
    refused(repo, rc, out, err, word)
    assert repo.index() == before


def test_fw4d_t6b_the_top_by_any_name_is_the_whole_tree(repo):
    (repo.path / "sub").mkdir()
    for cwd, path in ((repo.path, str(repo.path)), (repo.path / "sub", ".."),
                      (repo.path, "sub/..")):
        os.chdir(cwd)
        rc, out, err = repo.commit(path)
        refused(repo, rc, out, err, "whole tree")


@pytest.mark.parametrize("text", [None, "", " \n\n\t\n"])
def test_fw4d_t7_a_missing_or_empty_message_is_refused(repo, text):
    if text is None:
        repo.msg.unlink()
    else:
        repo.msg.write_text(text)
    repo.write("a.txt", "mine\n")
    before = repo.index()
    rc, out, err = repo.commit("a.txt")
    refused(repo, rc, out, err, "message file")
    assert repo.index() == before


def test_fw4d_t8_mid_merge_mid_rebase_and_detached_are_refused(repo):
    git(repo.path, "checkout", "-qb", "side")
    repo.write("b.txt", "side\n")
    git(repo.path, "commit", "-qam", "side")
    git(repo.path, "checkout", "-q", "main")
    repo.write("b.txt", "main\n")
    git(repo.path, "commit", "-qam", "main")
    subprocess.run(["git", "merge", "-q", "side"], cwd=repo.path, capture_output=True)
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt")
    refused(repo, rc, out, err, "MERGE_HEAD")
    git(repo.path, "merge", "--abort")
    git(repo.path, "checkout", "-q", "--", "a.txt")
    git(repo.path, "checkout", "-q", "side")
    subprocess.run(["git", "rebase", "-q", "main"], cwd=repo.path, capture_output=True)
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt")
    refused(repo, rc, out, err, "rebase-merge")
    git(repo.path, "checkout", "-q", "--", "a.txt")
    git(repo.path, "rebase", "--abort")
    git(repo.path, "checkout", "-q", "--detach", "main")
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt")
    refused(repo, rc, out, err, "detached")


def test_fw4d_t9_nothing_to_commit_and_unmatched_paths_are_refused(repo):
    rc, out, err = repo.commit("a.txt")
    refused(repo, rc, out, err, "nothing to commit")
    repo.write("a1", "1\n")
    repo.write("a2", "2\n")
    before = repo.index()
    rc, out, err = repo.commit("a*")                        # literal: no glob sweeps a1 and a2
    refused(repo, rc, out, err, "git add refuses")
    assert repo.index() == before


def test_fw4d_t10_a_path_moved_by_the_check_is_red_moved(repo):
    repo.write("a.txt", "mine\n")
    before, head = repo.index(), repo.head()
    rc, out, _ = repo.commit("a.txt", check="sh -c 'echo later >> a.txt'")
    assert (rc, out) == (1, "commit scratch: red moved exit 1\n")
    assert (repo.index(), repo.head()) == (before, head)


def test_fw4d_t11_a_red_commit_hook_leaves_the_index_as_found(repo):
    hook = repo.path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 5\n")
    hook.chmod(0o755)
    repo.write("a.txt", "mine\n")
    before, head = repo.index(), repo.head()
    rc, out, _ = repo.commit("a.txt")
    assert (rc, out) == (1, "commit scratch: red commit exit 1\n")
    assert (repo.index(), repo.head()) == (before, head)


@pytest.fixture
def served(monkeypatch):
    def serve_now(root, popen=None):
        if not gate.entries(root):
            return False
        gate.serve(root, gate.Fx(idle=0, poll=0.05))
        return True
    monkeypatch.setattr(gate, "spawn_serve", serve_now)
    return resolver.state_dir(os.environ)


def results(root):
    d = gate.gate_dir(root)
    return [n for n in os.listdir(d) if gate.ID.match(n)] if d.exists() else []


def test_fw4d_t12_a_make_check_is_one_gate_job_and_others_run_here(repo, served):
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt", check="make check")
    (gid,) = results(served)
    r = gate.wait(served, gid)[1]
    assert rc == 0 and out.startswith("commit scratch: ok ") and f"gate {gid} " in err
    assert (r["command"], r["repo"], r["exit"]) == (["make", "check"],
                                                     os.path.realpath(repo.path), 0)
    repo.write("RED", "red\n")
    repo.write("b.txt", "mine\n")
    before = repo.index()
    rc, out, _ = repo.commit("b.txt", check="make check")
    assert (rc, out) == (2, "commit scratch: red check exit 2\n") and repo.index() == before
    repo.write("a.txt", "again\n")
    rc, _, _ = repo.commit("a.txt", check="sh -c 'make check || true'")
    assert rc == 0 and len(results(served)) == 2               # not make's word: run here


def test_fw4d_t13_the_docs_name_the_verb():
    skill = (ROOT / "plugin" / "skills" / "session" / "SKILL.md").read_text()
    runbook = (ROOT / "RUNBOOK.md").read_text()
    line = "agentik-session commit <paths...> --check <cmd> --message-file <f>"
    assert line in skill and "session commit <paths...>" in runbook
    assert "gitlink" in runbook and "--only" in runbook
    tree = ast.parse((ROOT / "plugin" / "lib" / "claude_session" / "commit.py").read_text())
    assert ast.get_docstring(tree).count("make") >= 1


# ---- round 1's fold (hq REFUTE-2026-11-10-fw4d-r1 and its rulings); each red at 30ae6fb ------

LIB = ROOT / "plugin" / "lib"
GITDIR = ".git"


def spawn(repo, *argv, check="true"):
    """The verb in its own process, as a harness runs it (for the races and the signals)."""
    env = dict(os.environ, PYTHONPATH=str(LIB), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.Popen([sys.executable, "-c", MAIN, "commit", *argv, "--check", check,
                             "--message-file", str(repo.msg)], cwd=repo.path, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


# SIGINT at Python's own handler even when the runner started with it ignored (a background job)
MAIN = ("import runpy, signal; signal.signal(signal.SIGINT, signal.default_int_handler); "
        "runpy.run_module('claude_session', run_name='__main__', alter_sys=True)")


def until(cond, secs=30):
    end = time.monotonic() + secs
    while not cond():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.05)


def took(repo, sha):
    return git(repo.path, "show", "--name-only", "--format=", sha)


def test_fw4d_r1_f1_two_calls_at_once_each_ok_names_its_own_commit(repo):
    """F1 (p07, p08): A's post-commit hook holds until HEAD moves past A's commit or 3 s pass,
    and B starts once A is in it. With no lock B commits in that window and A's line names B's
    commit; with the lock B waits for A's line, and each line names the call's own commit."""
    hook = repo.path / GITDIR / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\n[ -e .git/arm ] || exit 0\nrm -f .git/arm\n"
                    "me=$(git rev-parse HEAD)\ntouch .git/inhook\ni=0\n"
                    "while [ $i -lt 30 ]; do\n  [ \"$(git rev-parse HEAD)\" != \"$me\" ] && exit 0\n"
                    "  sleep 0.1; i=$((i+1))\ndone\n")
    hook.chmod(0o755)
    (repo.path / GITDIR / "arm").write_text("")
    repo.write("a.txt", "A\n")
    repo.write("b.txt", "B\n")
    a = spawn(repo, "a.txt")
    until(lambda: (repo.path / GITDIR / "inhook").exists() or a.poll() is not None)
    b = spawn(repo, "b.txt")
    (oa, ea), (ob, eb) = a.communicate(timeout=120), b.communicate(timeout=120)
    assert (a.returncode, b.returncode) == (0, 0), (oa, ea, ob, eb)
    for out, path in ((oa, "a.txt"), (ob, "b.txt")):
        assert out.startswith("commit scratch: ok ") and took(repo, out.split()[-1]) == path, out
    assert git(repo.path, "status", "--porcelain") == ""


def test_fw4d_r1_f1_a_held_lock_waits_to_the_wall_then_reds(repo, monkeypatch):
    """F1: one call at a time per repo; a second waits up to the verb's wall (the gate's), then
    one red line, the index and HEAD as found."""
    monkeypatch.setattr(gate, "_config", lambda env, log=None: {"wall": 0.5})
    fd = os.open(str(repo.path / GITDIR / "agentik-commit.lock"), os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        repo.write("a.txt", "mine\n")
        before, head, t = repo.index(), repo.head(), time.monotonic()
        rc, out, err = repo.commit("a.txt")
        assert (rc, out) == (124, "commit scratch: red lock exit 124\n"), err
        assert time.monotonic() - t >= 0.5 and "waiting" in err
        assert (repo.index(), repo.head()) == (before, head)
    finally:
        os.close(fd)
    rc, out, _ = repo.commit("a.txt")
    assert rc == 0 and out == f"commit scratch: ok {repo.head()}\n"


def test_fw4d_r1_f2_git_killed_after_the_branch_moved_the_commit_stands(repo):
    """F2 (p10): git dies by SIGTERM in its post-commit hook, after the branch moved: nothing is
    restored, the line says the commit stands with its sha, the code is 128+15."""
    hook = repo.path / GITDIR / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\nkill -TERM $PPID\nsleep 1\n")
    hook.chmod(0o755)
    repo.write("a.txt", "mine\n")
    head = repo.head()
    rc, out, err = repo.commit("a.txt")
    now = repo.head()
    assert now != head and took(repo, now) == "a.txt"
    assert (rc, out) == (143, f"commit scratch: red commit exit 143, the commit stands: {now}\n"), err
    assert git(repo.path, "status", "--porcelain") == ""


def test_fw4d_r1_f2_sigint_in_the_post_commit_hook_the_commit_stands(repo):
    """F2 (p02, the post-commit window): SIGINT to the verb while its commit's post-commit hook
    runs: the commit stands, named on the line; the index is the commit's, not the pre-add."""
    pidf = repo.path / GITDIR / "hookpid"
    hook = repo.path / GITDIR / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\necho $$ > .git/hookpid\nexec sleep 30\n")
    hook.chmod(0o755)
    repo.write("a.txt", "mine\n")
    head = repo.head()
    p = spawn(repo, "a.txt")
    try:
        until(lambda: (pidf.exists() and pidf.read_text().strip()) or p.poll() is not None)
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=60)
    finally:
        p.kill()
        if pidf.exists() and pidf.read_text().strip():
            try:
                os.kill(int(pidf.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
    now = repo.head()
    assert now != head and took(repo, now) == "a.txt"
    assert p.returncode in (130, -signal.SIGINT), (p.returncode, out, err)
    assert out == f"commit scratch: red signal exit 130, the commit stands: {now}\n", err
    assert git(repo.path, "status", "--porcelain") == ""


def snapshot(where):
    return where / "agentik-commit.index"


def test_fw4d_r1_f3_a_restore_that_cannot_be_made_is_its_own_red(repo, monkeypatch):
    """F3 (p02): an index.lock present when the red restores. The line names the snapshot, the
    exit is not 0, the snapshot stays and is the index as found; the next call refuses on it."""
    monkeypatch.setattr(verb, "RESTORE_WAIT", 0.2, raising=False)
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    repo.write("a.txt", "mine\n")
    before, head, gd = repo.index(), repo.head(), repo.path / GITDIR
    rc, out, err = repo.commit("a.txt", check="sh -c 'touch .git/index.lock; exit 3'")
    assert (rc, out) == (1, "commit scratch: red restore exit 1, the index as found is kept at "
                            f"{snapshot(gd)}\n"), err
    assert "red check exit 3" in err and repo.head() == head
    os.unlink(str(gd / "index.lock"))
    rc, out, err = repo.commit("b.txt")
    refused(repo, rc, out, err, str(snapshot(gd)))
    os.replace(str(snapshot(gd)), str(gd / "index"))
    assert repo.index() == before


def test_fw4d_r1_f3_in_a_linked_worktree_the_snapshot_is_its_own_git_dir(repo, monkeypatch):
    """The ruling's worktree: a linked worktree's index lives in its own git dir, and so do the
    lock and the snapshot."""
    monkeypatch.setattr(verb, "RESTORE_WAIT", 0.2, raising=False)
    wt = repo.path.parent / "wt"
    git(repo.path, "worktree", "add", "-q", "-b", "wt", str(wt))
    monkeypatch.chdir(wt)
    (wt / "a.txt").write_text("mine\n")
    before, gd = git(wt, "ls-files", "-s"), repo.path / GITDIR / "worktrees" / "wt"
    rc, out, _ = repo.commit("a.txt", check="sh -c 'exit 3'")
    assert (rc, out) == (3, "commit wt: red check exit 3\n") and git(wt, "ls-files", "-s") == before
    assert not snapshot(gd).exists() and (gd / "agentik-commit.lock").exists()
    rc, out, _ = repo.commit("a.txt", check=f"sh -c 'touch {gd}/index.lock; exit 3'")
    assert (rc, out) == (1, f"commit wt: red restore exit 1, the index as found is kept at "
                            f"{snapshot(gd)}\n")
    os.unlink(str(gd / "index.lock"))
    os.replace(str(snapshot(gd)), str(gd / "index"))
    assert git(wt, "ls-files", "-s") == before


def test_fw4d_r1_f4_a_case_folded_path_leaves_the_index_as_found(repo):
    """F4b (p08): on a case-folding disk `SUB/new.txt` adds `sub/new.txt` and the call refuses as
    nothing to commit, or the check reds; the index is as found (a case-keeping disk refuses)."""
    repo.write("sub/s.txt", "base\n")
    git(repo.path, "add", "sub/s.txt")
    git(repo.path, "commit", "-qm", "sub")
    repo.write("sub/new.txt", "n\n")
    before = repo.index()
    rc, out, err = repo.commit("SUB/new.txt", check="false")
    assert (rc, out) in ((2, ""), (1, "commit scratch: red check exit 1\n")), err
    assert repo.index() == before and not snapshot(repo.path / GITDIR).exists()


def test_fw4d_r1_f4_a_file_replaced_by_a_directory_leaves_the_index_as_found(repo):
    """F4a (p02): `d` tracked, then a directory, `d/x` named, a red check: `d` stays in the
    index, as it was found."""
    repo.write("d", "f\n")
    git(repo.path, "add", "d")
    git(repo.path, "commit", "-qm", "d")
    os.unlink(str(repo.path / "d"))
    repo.write("d/x", "x\n")
    before = repo.index()
    rc, out, _ = repo.commit("d/x", check="false")
    assert (rc, out) == (1, "commit scratch: red check exit 1\n") and repo.index() == before


def test_fw4d_r1_f5_unmerged_stages_come_back_as_they_were(repo):
    """F5 (p02): a stash pop's conflict (no MERGE_HEAD), a red check: stages 1, 2, 3 again."""
    repo.write("a.txt", "stash-side\n")
    git(repo.path, "stash", "-q")
    repo.write("a.txt", "main-side\n")
    git(repo.path, "commit", "-qam", "main2")
    subprocess.run(["git", "stash", "pop"], cwd=repo.path, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    repo.write("a.txt", "resolved\n")
    before = repo.index()
    assert " 1\ta.txt" in before and " 3\ta.txt" in before
    rc, out, _ = repo.commit("a.txt", check="false")
    assert (rc, out) == (1, "commit scratch: red check exit 1\n") and repo.index() == before


def test_fw4d_r1_f6_an_exception_that_is_no_red_restores(repo, monkeypatch):
    """F6 (p02): any exception through the call puts the index back, then goes on up."""
    def boom(top, argv):
        raise RuntimeError("boom")
    monkeypatch.setattr(verb, "_direct_check", boom)
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    repo.write("a.txt", "mine\n")
    before, head = repo.index(), repo.head()
    with pytest.raises(RuntimeError):
        repo.commit("a.txt")
    assert (repo.index(), repo.head()) == (before, head)
    assert not snapshot(repo.path / GITDIR).exists()


def test_fw4d_r1_f7_sigterm_to_the_verb_restores_and_ends_the_check(repo):
    """F7 (p02): SIGTERM to the verb during its check: exit 128+15, the index as found, and the
    check does not outlive the verb."""
    pidf = repo.path / GITDIR / "checkpid"
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    repo.write("a.txt", "mine\n")
    before, head = repo.index(), repo.head()
    p = spawn(repo, "a.txt", check="sh -c 'echo $$ > .git/checkpid; exec sleep 30'")
    try:
        until(lambda: (pidf.exists() and pidf.read_text().strip()) or p.poll() is not None)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=60)
    finally:
        p.kill()
    cp = int(pidf.read_text())

    def gone():
        try:
            os.kill(cp, 0)
        except ProcessLookupError:
            return True
        return False
    try:
        until(gone, 10)
    finally:
        if not gone():
            os.kill(cp, signal.SIGKILL)
    assert (p.returncode, out) == (143, ""), err
    assert (repo.index(), repo.head()) == (before, head)
    assert not snapshot(repo.path / GITDIR).exists()


# ---- round 2's ruling (the coordinator's read of fold 1): another writer during a red check ----

OTHER = "git -c user.name=other -c user.email=other@x.invalid"
MOVED = "commit scratch: red {}, the index moved under the check: nothing is restored\n"
THEIRS = f"echo theirs > b.txt && git add b.txt && {OTHER} commit -qm theirs"


def staged(repo):
    return git(repo.path, "diff", "--cached", "--name-only").split()


def next_plain_commit(repo):
    repo.write("c.txt", "next\n")
    git(repo.path, "add", "c.txt")
    git(repo.path, "-c", "user.name=n", "-c", "user.email=n@x.invalid", "commit", "-qm", "next")


def test_fw4d_r2_another_writers_commit_during_a_red_check_stands(repo):
    """The probe (fw4d-probe/probe.sh): the check commits b.txt with plain git, then reds. The
    index as found is not put back over the newer HEAD, so b.txt is no reversal staged against
    it, the line says the index moved, and the next plain commit keeps the other writer's b.txt."""
    repo.write("a.txt", "mine\n")
    head = repo.head()
    rc, out, err = repo.commit("a.txt", check=f"sh -c '{THEIRS} && exit 1'")
    assert (rc, out) == (1, MOVED.format("check exit 1")), err
    assert repo.head() != head and git(repo.path, "show", "HEAD:b.txt") == "theirs"
    assert "b.txt" not in staged(repo) and "mv " not in err
    assert not snapshot(repo.path / GITDIR).exists()
    next_plain_commit(repo)
    assert git(repo.path, "show", "HEAD:b.txt") == "theirs"
    assert took(repo, "HEAD") == "c.txt"


def test_fw4d_r2_another_writers_staging_during_a_red_check_stays(repo):
    """Another writer only stages c.txt during a red check: it stays staged, this call's a.txt
    too (nothing is restored), and stderr names a.txt and the way to unstage it."""
    repo.write("a.txt", "mine\n")
    head = repo.head()
    rc, out, err = repo.commit("a.txt", check="sh -c 'echo c > c.txt && git add c.txt && exit 1'")
    assert (rc, out) == (1, MOVED.format("check exit 1")), err
    assert repo.head() == head and staged(repo) == ["a.txt", "c.txt"]
    assert "restore --staged -- a.txt" in err and "mv " not in err
    assert not snapshot(repo.path / GITDIR).exists()


def test_fw4d_r2_a_status_refresh_during_a_red_check_restores_as_found(repo):
    """A `git status` during a red check, no other writer: it rewrites the index file (a stat
    refresh) and no entry, so the index goes back as found, the line as before."""
    repo.write("b.txt", "theirs\n")
    git(repo.path, "add", "b.txt")
    repo.write("a.txt", "mine\n")
    before, head, gd = repo.index(), repo.head(), repo.path / GITDIR
    check = ("sh -c 'cksum < .git/index > .git/i1 && touch -t 202001010000 b.txt Makefile && "
             "git status --porcelain > /dev/null && cksum < .git/index > .git/i2 && exit 1'")
    rc, out, err = repo.commit("a.txt", check=check)
    assert (rc, out) == (1, "commit scratch: red check exit 1\n"), err
    assert (gd / "i1").read_text() != (gd / "i2").read_text()      # the refresh wrote the index
    assert (repo.index(), repo.head()) == (before, head)
    assert not snapshot(gd).exists()


def test_fw4d_r2_sigterm_after_another_writers_commit_restores_nothing(repo):
    """SIGTERM to the verb during a check that another writer's commit ran in: exit 128+15,
    the line says the index moved, the other writer's b.txt stands in HEAD and in the index."""
    pidf = repo.path / GITDIR / "checkpid"
    repo.write("a.txt", "mine\n")
    head = repo.head()
    p = spawn(repo, "a.txt", check=f"sh -c '{THEIRS} && echo $$ > .git/checkpid && exec sleep 30'")
    try:
        until(lambda: (pidf.exists() and pidf.read_text().strip()) or p.poll() is not None)
        p.send_signal(signal.SIGTERM)
        out, err = p.communicate(timeout=60)
    finally:
        p.kill()
        if pidf.exists() and pidf.read_text().strip():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pidf.read_text()), signal.SIGKILL)      # the check, if it outlived
    assert (p.returncode, out) == (143, MOVED.format("signal exit 143")), err
    assert repo.head() != head and git(repo.path, "show", "HEAD:b.txt") == "theirs"
    assert "b.txt" not in staged(repo) and not snapshot(repo.path / GITDIR).exists()
    next_plain_commit(repo)
    assert git(repo.path, "show", "HEAD:b.txt") == "theirs"
