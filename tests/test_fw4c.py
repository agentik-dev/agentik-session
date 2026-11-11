"""Packet FW4c (hq design/08 section 5 row 5, section 6 item 7): `gate land`, hq's land script
as one gate job of the plugin. The steps' own tests are tests/test_land.py and
tests/test_land_range.py, ported; these pin the verb, the job and its mark. Each is red at
36c84ea (alpha.60). Every repo, queue and runner is under the test's temp roots."""
import ast
import io
import os
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, resolver

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugin" / "lib" / "agentik-session"
MARK = "CLAUDE_SESSION_GATE_JOB"
MAKEFILE = "check:\n\t@test ! -e RED\n\t@if [ -e SLOW ]; then sleep 30; fi\n"


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
    """A scratch repo on main, a branch in its worktree, a merge message."""

    def __init__(self, tmp):
        self.path = tmp / "scratch"
        self.path.mkdir()
        git(self.path, "init", "-q", "-b", "main")
        (self.path / "Makefile").write_text(MAKEFILE)
        (self.path / ".gitignore").write_text(".claude/worktrees/\n")
        git(self.path, "add", "Makefile", ".gitignore")
        git(self.path, "commit", "-qm", "base")
        self.message = tmp / "msg"
        self.message.write_text("land the branch\n")

    def branch(self, name, files):
        tree = self.path / ".claude" / "worktrees" / name
        git(self.path, "worktree", "add", "-q", "-b", name, str(tree), "main")
        for rel, (text, mode) in files.items():
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            (tree / rel).write_text(text)
            os.chmod(tree / rel, mode)
        git(tree, "add", *files)
        git(tree, "commit", "-qm", "work of " + name)
        return git(tree, "rev-parse", "HEAD")

    def main(self):
        return git(self.path, "rev-parse", "main")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return Repo(tmp_path)


@pytest.fixture
def served(monkeypatch):
    """The runner in this process, at once: the queue drains before `wait` reads it."""
    def serve_now(root, popen=None):
        if not gate.entries(root):
            return False
        gate.serve(root, gate.Fx(idle=0, poll=0.05))
        return True
    monkeypatch.setattr(gate, "spawn_serve", serve_now)
    return resolver.state_dir(os.environ)


def test_fw4c_t1_a_green_landing_is_one_line_and_exit_0(repo, served, tmp_path, monkeypatch):
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    before = repo.main()
    monkeypatch.chdir(tmp_path)                      # the merge file is relative to the caller
    rc, out, err = run("gate", "land", str(repo.path), "work", sha, "msg")
    assert (rc, out) == (0, f"land scratch: ok {sha}, main readied\n"), err
    assert git(repo.path, "rev-parse", "main^1") == before
    assert git(repo.path, "rev-parse", "main^2") == sha
    assert not (repo.path / ".claude" / "worktrees" / "work").exists()
    assert "work" not in git(repo.path, "branch", "--list", "work")
    assert err.startswith("queued ") and "\ngate " in err and ": exit 0 in " in err


def test_fw4c_t2_a_red_check_keeps_main_and_exits_its_code(repo, served):
    sha = repo.branch("bad", {"RED": ("red\n", 0o644)})
    before = repo.main()
    rc, out, _ = run("gate", "land", str(repo.path), "bad", sha, str(repo.message))
    assert (rc, out) == (2, "land scratch: red check exit 2\n")
    assert repo.main() == before and git(repo.path, "rev-parse", "bad") == sha


def test_fw4c_t3_the_wall_reads_red_cut_124(repo, served):
    sha = repo.branch("slow", {"SLOW": ("slow\n", 0o644)})
    before = repo.main()
    rc, out, _ = run("gate", "land", str(repo.path), "slow", sha, str(repo.message),
                     "--wall", "6")
    assert (rc, out) == (124, "land scratch: red cut exit 124\n")
    assert repo.main() == before


def test_fw4c_t4_the_range_suffix_passes_through(repo, served):
    old = "#!/bin/sh\ncase $1 in --help) echo 'usage: hygiene'; exit 0 ;; esac\nexit 0\n"
    sha = repo.branch("work", {"scripts/hygiene": (old, 0o755)})
    rc, out, _ = run("gate", "land", str(repo.path), "work", sha, str(repo.message))
    assert (rc, out) == (0, f"land scratch: ok {sha}, main readied, range not scanned\n")


@pytest.mark.parametrize("body,code", [("echo hello; exit 0", 1), ("echo hello; exit 7", 7),
                                       ("echo 'land other: ok x, main readied'", 1)])
def test_fw4c_t5_a_job_with_no_land_line_of_its_repo_is_red_gate(repo, served, monkeypatch,
                                                                  body, code):
    monkeypatch.setattr(gate, "self_argv", lambda: ["/bin/sh", "-c", body, "sh"])
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    rc, out, _ = run("gate", "land", str(repo.path), "work", sha, str(repo.message))
    assert (rc, out) == (code, f"land scratch: red gate exit {code}\n")


def test_fw4c_t6_usage_and_a_missing_repo_queue_nothing(repo, served, tmp_path):
    rc, out, err = run("gate", "land", str(repo.path), "work")
    assert (rc, out) == (2, "land ?: red usage exit 2\n") and "usage:" in err
    rc, out, _ = run("gate", "land", str(tmp_path / "gone"), "work", "abc", str(repo.message))
    assert (rc, out) == (1, "land gone: red repo exit 1\n")
    assert gate.entries(served) == [] and not list(gate.gate_dir(served).glob("2*"))


def test_fw4c_t7_the_job_is_the_in_job_verb_with_absolute_paths(repo, monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.setattr(gate, "wait", lambda root, gid, **kw: (2, None))
    monkeypatch.chdir(tmp_path)
    run("gate", "land", str(repo.path), "work", "abc123", "msg")
    (e,) = gate.entries(resolver.state_dir(os.environ))
    assert e["command"] == [*gate.self_argv(), "gate", "land", "--in-job",
                            os.path.realpath(repo.path), "work", "abc123",
                            str(tmp_path / "msg")]
    assert gate.self_argv()[:2] == [sys.executable, "-I"]
    assert gate.self_argv()[-1] == str(RUNNER.resolve()) and e["label"] == "land work"


def test_fw4c_t8_spawn_serve_starts_the_runner_by_self_argv(repo, monkeypatch):
    seen = []
    root = resolver.state_dir(os.environ)
    gate.enqueue(root, repo.path, ["true"], {}, [], 60, "", None, 1.0)
    gate.spawn_serve(root, popen=lambda argv, **kw: seen.append(argv))
    assert seen == [[*gate.self_argv(), "gate", "serve", "--root", str(root)]]


def test_fw4c_t9_every_job_carries_its_own_id_as_the_mark(repo, served):
    rc, out, _ = run("gate", "run", str(repo.path), "--wait", "--", "/bin/sh", "-c",
                     f'echo "mark=${MARK}"')
    gid = out.split()[1]
    assert rc == 0 and f"mark={gid}\n" in (gate.entry_dir(served, gid) / "log").read_text()


def test_fw4c_t10_the_queue_form_refuses_inside_a_job(repo, served, monkeypatch):
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    monkeypatch.setenv(MARK, "20261110-000000-9")
    rc, out, err = run("gate", "land", str(repo.path), "work", sha, str(repo.message))
    assert (rc, out) == (2, "") and "--in-job" in err and "own repo" in err
    assert gate.entries(served) == []


def test_fw4c_t11_the_in_job_form_refuses_outside_a_job(repo):
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    before = repo.main()
    rc, out, err = run("gate", "land", "--in-job", str(repo.path), "work", sha,
                       str(repo.message))
    assert (rc, out) == (2, "") and MARK in err and repo.main() == before


def test_fw4c_t12_the_in_job_form_is_the_steps(repo):
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    env = dict(os.environ, **{MARK: "20261110-000000-9"})
    p = subprocess.run([sys.executable, str(RUNNER), "gate", "land", "--in-job", str(repo.path),
                        "work", sha, str(repo.message)], cwd=repo.path, env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert (p.returncode, p.stdout) == (0, f"land scratch: ok {sha}, main readied\n"), p.stderr
    assert "land-step: check: make check in " in p.stderr


def test_fw4c_t13_the_suite_clears_the_mark_and_the_docs_name_the_verb():
    tree = ast.parse((ROOT / "tests" / "conftest.py").read_text())
    (inherited,) = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == "INHERITED"]
    assert MARK in inherited and gate.JOB_MARK == MARK
    skill = (ROOT / "plugin" / "skills" / "session" / "SKILL.md").read_text()
    runbook = (ROOT / "RUNBOOK.md").read_text()
    assert "agentik-session gate land <repo> <branch> <sha> <merge-file>" in skill
    assert "gate land <repo> <branch> <sha> <merge-file>" in runbook and "--in-job" in runbook


# ---- fold r1 (the refuter's F1): the verdict is the log's last land line of the repo ----------

def _until(what, seconds=120):
    t0 = time.monotonic()
    while not what():
        assert time.monotonic() - t0 < seconds, "not reached in %d s" % seconds
        time.sleep(0.05)


def test_fw4c_t14_a_writer_the_check_leaves_behind_keeps_the_land_line(repo, monkeypatch,
                                                                        tmp_path):
    # probe r1: the job lands and exits 0; a child of the check writes on after the land line
    # until the runner, at the shipped poll (gate.POLL, 1 s), closes the job and its group.
    def serve_at_the_shipped_poll(root, popen=None):
        if not gate.entries(root):
            return False
        gate.serve(root, gate.Fx(idle=0, poll=gate.POLL))
        return True

    monkeypatch.setattr(gate, "spawn_serve", serve_at_the_shipped_poll)
    stop = tmp_path / "stop"
    (repo.path / "Makefile").write_text(
        "check:\n\t@( i=0; while [ ! -e '%s' ] && [ $$i -lt 600 ]; do echo tick >&2; "
        "sleep 0.1; i=$$((i+1)); done ) &\n" % stop)
    git(repo.path, "commit", "-qam", "a check that leaves a writer behind")
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    try:
        rc, out, err = run("gate", "land", str(repo.path), "work", sha, str(repo.message))
        log = Path(err.split("log ")[-1].strip()).read_text().splitlines()
    finally:
        stop.write_text("")
    ok = f"land scratch: ok {sha}, main readied"
    assert "tick" in log[log.index(ok) + 1:], "no line after the land line"
    assert (rc, out) == (0, ok + "\n"), err
    assert git(repo.path, "rev-parse", "main^2") == sha


def test_fw4c_t15_a_runner_killed_mid_check_and_a_job_that_lands_reads_ok(repo, monkeypatch):
    # probe r15: the runner dies in the check, the job lands, the next runner writes 125.
    (repo.path / "Makefile").write_text("check:\n\t@sleep 2\n")
    git(repo.path, "commit", "-qam", "a two-second check")
    sha = repo.branch("work", {"new.txt": ("new\n", 0o644)})
    spawn, wait, runners = gate.spawn_serve, gate.wait, []

    def popen(argv, **kw):
        runners.append(subprocess.Popen(argv, **kw))
        return runners[-1]

    def the_first_runner_dies(root, popen_=None):
        if runners:                                   # wait found it dead: the next recovers
            return spawn(root, popen=popen)
        (e,) = gate.entries(root)
        log = gate.entry_dir(root, e["id"]) / "log"
        spawn(root, popen=popen)
        _until(lambda: log.exists() and "land-step: check: make check in " in log.read_text())
        runners[0].kill()
        runners[0].wait()
        _until(lambda: f"land scratch: ok {sha}" in log.read_text())
        return True

    monkeypatch.setattr(gate, "spawn_serve", the_first_runner_dies)
    monkeypatch.setattr(gate, "wait", lambda root, gid: wait(root, gid, poll=0.2))
    try:
        rc, out, err = run("gate", "land", str(repo.path), "work", sha, str(repo.message))
    finally:
        for p in runners:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=60)
    assert ": exit 125 in " in err, err
    assert (rc, out) == (0, f"land scratch: ok {sha}, main readied\n"), err
    assert git(repo.path, "rev-parse", "main^2") == sha


def test_fw4c_t16_the_floor_runs_thirteen_of_the_ported_land_tests():
    # fold r1's ruling: under the floor python the cuts, the encoding and one green; the other
    # 102 run once, under .venv.
    import unittest

    import test_land

    class Case:
        def __init__(self, name):
            self._testMethodName = name

        def skipTest(self, why):
            raise unittest.SkipTest(why)

    names = [n.name for f in ("test_land.py", "test_land_range.py")
             for n in ast.walk(ast.parse((ROOT / "tests" / f).read_text()))
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    floor = [n for n in names if test_land.FLOOR.search(n)]
    assert (len(names), len(floor)) == (115, 13)
    for name in names:
        try:
            test_land.one_run_under_312(Case(name))
            skipped = False
        except unittest.SkipTest:
            skipped = True
        assert skipped == (sys.version_info < (3, 10) and name not in floor), name
