"""Packet FW4d (hq design/08 section 5 row 5, section 6 item 7): `agentik session commit <paths...>
--check <cmd> --message-file <f>`: add by path, check, commit on green, the check's code on red,
and the index as it was found on every red and refusal. Each test is red at 36c84ea (alpha.60):
the verb does not exist. Every repo and queue is under the test's temp roots."""
import ast
import io
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, resolver

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
