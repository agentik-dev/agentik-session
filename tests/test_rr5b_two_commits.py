"""Packet rr5b R1 to R5: `checkpoint --commit` where a repo's records live outside its clone, in a
temp clone with a temp holder repository (or a plain folder in none). Every name is made up and
every repository a test commits in is the test's own."""

import fcntl
import io
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, config, gate, records, sessionconfig
from claude_session import commit as core

KEY = "agentik.records"
CHARTER = "history/sittings/2026-11-21-1.md"
SID = "rr5b-sess-0000-1111"


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


class World:
    def __init__(self, root: Path, state: str):
        self.clone = root / "demo"
        self.clone.mkdir()
        git(self.clone, "init", "-q", "-b", "main")
        for n in ("a.py", "s.txt"):
            (self.clone / n).write_text("base\n")
        git(self.clone, "add", "a.py", "s.txt")
        git(self.clone, "commit", "-qm", "base")
        self.hold = None
        if state == "out":
            self.hold = root / "hold"
            self.rec = self.hold / "repos" / "demo"
        elif state == "plain":
            self.rec = root / "plain" / "demo"
        else:
            self.rec = None
        if self.rec is not None:
            (self.rec / "history" / "sittings").mkdir(parents=True)
            self.charter = self.rec / CHARTER
            self.charter.write_text("# Sitting 2026-11-21-1: demo\n")
            (self.rec / "x.txt").write_text("base\n")
            git(self.clone, "config", KEY, str(self.rec))
        if self.hold is not None:
            git(self.hold, "init", "-q", "-b", "main")
            git(self.hold, "add", ".")
            git(self.hold, "commit", "-qm", "base")

    def edit(self):
        """A code edit and a record edit, and a stranger staged in each repository."""
        (self.clone / "a.py").write_text("mine\n")
        (self.clone / "s.txt").write_text("theirs\n")
        git(self.clone, "add", "s.txt")
        if self.rec is not None:
            self.charter.write_text("# Sitting 2026-11-21-1: demo\n\nmore\n")
            (self.rec / "x.txt").write_text("theirs\n")
        if self.hold is not None:
            git(self.hold, "add", "repos/demo/x.txt")

    @staticmethod
    def head(repo):
        return git(repo, "rev-parse", "HEAD")

    @staticmethod
    def took(repo):
        return git(repo, "show", "--name-only", "--format=", "HEAD").split()

    @staticmethod
    def staged(repo):
        return git(repo, "diff", "--cached", "--name-only").split()


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for k, v in (("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@t"),
                 ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@t")):
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(gate.JOB_MARK, raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    records.reset()
    config.ensure_dirs()
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})

    def build(state):
        w = World(Path(os.path.realpath(tmp_path)), state)
        monkeypatch.chdir(w.clone)
        w.edit()
        return w
    yield build
    records.reset()


def counter():
    return sessionconfig.load_overlay().get("_prompts_since_checkpoint")


# ---- acceptance 1 and 2 (R2): one commit in each, each its own paths -------------------------

def test_rr5b_a1_a_code_file_and_the_charter_make_one_commit_in_each(make):
    w = make("out")
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 0, (out, err)
    assert w.took(w.clone) == ["a.py"] and w.staged(w.clone) == ["s.txt"]
    assert w.took(w.hold) == [f"repos/demo/{CHARTER}"] and w.staged(w.hold) == ["repos/demo/x.txt"]
    for repo in (w.clone, w.hold):
        assert git(repo, "log", "-1", "--format=%s") == "cp"
        assert git(repo, "rev-list", "--count", "HEAD") == "2"
    assert f"commit demo: ok {w.head(w.clone)}" in out
    assert f"commit hold: ok {w.head(w.hold)}" in out and counter() == 0


def test_rr5b_a2_only_record_paths_commit_in_the_holder_alone(make):
    w = make("out")
    head = w.head(w.clone)
    rel = os.path.relpath(w.charter, w.clone)                  # a relative spelling sorts too
    rc, out, err = run("checkpoint", "--commit", rel, "-m", "cp")
    assert rc == 0, (out, err)
    assert w.head(w.clone) == head and w.took(w.hold) == [f"repos/demo/{CHARTER}"]
    assert w.staged(w.hold) == ["repos/demo/x.txt"] and counter() == 0


def test_rr5b_a2_a_records_folder_named_is_sorted_as_a_record(make):
    w = make("out")
    git(w.hold, "restore", "--staged", "repos/demo/x.txt")
    rc, out, err = run("checkpoint", "--commit", str(w.rec / "history"), "-m", "cp")
    assert rc == 0, (out, err)
    assert w.took(w.hold) == [f"repos/demo/{CHARTER}"]


def test_rr5b_a2_only_code_paths_commit_in_the_clone_and_leave_the_holder(make):
    w = make("out")
    head, index = w.head(w.hold), git(w.hold, "ls-files", "-s")
    rc, out, err = run("checkpoint", "--commit", "a.py", "-m", "cp")
    assert rc == 0, (out, err)
    assert w.took(w.clone) == ["a.py"] and w.head(w.hold) == head
    assert git(w.hold, "ls-files", "-s") == index and w.staged(w.hold) == ["repos/demo/x.txt"]


# ---- acceptance 3 (R3): refused before either ------------------------------------------------

@pytest.mark.parametrize("case", ["neither", "merge", "ignored"])
def test_rr5b_a3_a_refusal_before_either_commit_leaves_both(make, tmp_path, case):
    w = make("out")
    if case == "neither":
        bad = Path(os.path.realpath(tmp_path)) / "elsewhere.txt"
        bad.write_text("x\n")
        named = str(bad)
    elif case == "merge":
        (w.hold / ".git" / "MERGE_HEAD").write_text(w.head(w.hold) + "\n")
        named = str(w.charter)
    else:
        (w.hold / ".gitignore").write_text("*.tmp\n")
        git(w.hold, "add", ".gitignore")
        git(w.hold, "commit", "-qm", "ignore", "--", ".gitignore")
        (w.rec / "note.tmp").write_text("x\n")
        named = str(w.rec / "note.tmp")
    heads = (w.head(w.clone), w.head(w.hold))
    rc, out, err = run("checkpoint", "--commit", "a.py", named, "-m", "cp")
    assert rc == 2, (out, err)
    assert (w.head(w.clone), w.head(w.hold)) == heads and counter() == 5
    assert w.staged(w.clone) == ["s.txt"] and w.staged(w.hold) == ["repos/demo/x.txt"]
    # one line (git's own reason, as the pin quotes it, may run on: the ignored case)
    assert [l for l in err.splitlines() if l.startswith("error:")] == [err.splitlines()[0]]
    if case == "neither":                                     # the pin's words, the clone named
        assert err.strip() == f"error: checkpoint --commit: {named} is outside the repo at {w.clone}"
    elif case == "merge":
        assert "the records' repository" in err and str(w.hold) in err and "MERGE_HEAD" in err
    else:
        assert "the records' repository" in err and "git add refuses" in err


def test_rr5b_a3_a_clone_mid_merge_is_named_as_the_clone(make):
    w = make("out")
    (w.clone / ".git" / "MERGE_HEAD").write_text(w.head(w.clone) + "\n")
    heads = (w.head(w.clone), w.head(w.hold))
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 2 and (w.head(w.clone), w.head(w.hold)) == heads
    assert "the clone" in err and str(w.clone) in err and "MERGE_HEAD" in err


# ---- acceptance 4 (R4): the half said, and the second run finishes it ------------------------

def test_rr5b_a4_the_holders_lock_past_the_wall_leaves_the_clones_commit_standing(make,
                                                                                 monkeypatch):
    w = make("out")
    monkeypatch.setattr(gate, "_config", lambda env, log=None: {"wall": 0.3})
    fd = os.open(w.hold / ".git" / core.LOCK, os.O_RDWR | os.O_CREAT, 0o666)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    hold_head = w.head(w.hold)
    try:
        rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    finally:
        os.close(fd)
    assert rc == core.LOCK_RED, (out, err)
    sha = w.head(w.clone)
    assert w.took(w.clone) == ["a.py"] and w.head(w.hold) == hold_head and counter() == 5
    said = [l for l in err.splitlines() if l.startswith("error: checkpoint --commit:")]
    assert len(said) == 1 and sha in said[0] and str(w.charter) in said[0]
    rc, out, err = run("checkpoint", "--commit", str(w.charter), "-m", "cp")
    assert rc == 0 and w.took(w.hold) == [f"repos/demo/{CHARTER}"] and w.head(w.clone) == sha


def test_rr5b_a4_a_red_holder_hook_leaves_the_clones_commit_standing(make):
    w = make("out")
    hook = w.hold / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 5\n")
    hook.chmod(0o755)
    hold_head = w.head(w.hold)
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 1 and "commit hold: red commit exit 1" in out, (out, err)   # git's own code
    sha = w.head(w.clone)
    assert w.took(w.clone) == ["a.py"] and w.head(w.hold) == hold_head
    assert w.staged(w.hold) == ["repos/demo/x.txt"] and counter() == 5
    said = [l for l in err.splitlines() if l.startswith("error: checkpoint --commit:")]
    assert len(said) == 1 and f"stands: {sha}" in said[0] and str(w.charter) in said[0]
    hook.unlink()
    rc, out, err = run("checkpoint", "--commit", str(w.charter), "-m", "cp")
    assert rc == 0 and w.took(w.hold) == [f"repos/demo/{CHARTER}"] and counter() == 0


def test_rr5b_a4_nothing_in_the_clone_does_not_stop_the_holder(make):
    w = make("out")
    rc, out, err = run("checkpoint", "--commit", "s.txt", str(w.charter), "-m", "cp")
    # s.txt is staged by another hand but named here: the call takes it, as at the pin
    assert rc == 0 and w.took(w.hold) == [f"repos/demo/{CHARTER}"], (out, err)
    git(w.clone, "checkout", "-q", "HEAD", "--", ".")
    (w.charter).write_text("# again\n")
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 0, (out, err)
    assert "nothing to commit in the clone" in out and w.took(w.hold) == [f"repos/demo/{CHARTER}"]
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 0 and "nothing to commit in the clone" in out
    assert "nothing to commit in the records' repository" in out


# ---- acceptance 5 (R5): no holder -------------------------------------------------------------

def test_rr5b_a5_records_in_no_repository_commit_the_clones_paths_and_say_so(make):
    w = make("plain")
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 0, (out, err)
    assert w.took(w.clone) == ["a.py"] and w.staged(w.clone) == ["s.txt"] and counter() == 0
    said = [l for l in out.splitlines() if "in no repository" in l]
    assert len(said) == 1 and str(w.charter) in said[0] and "nothing" in said[0]


# ---- acceptance 6 (R1): `own` is the pin, one resolver start at most -------------------------

def counted(monkeypatch):
    starts = []
    real = subprocess.Popen

    def popen(argv, *a, **k):
        if isinstance(argv, (list, tuple)) and list(argv[1:3]) == ["-I", "-S"]:
            starts.append(argv)
        return real(argv, *a, **k)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return starts


@pytest.mark.parametrize("state", ["own", "out"])
def test_rr5b_a6_checkpoint_commit_starts_the_resolver_once_at_most(make, monkeypatch, state):
    w = make(state)
    starts = counted(monkeypatch)
    named = ["a.py"] + ([str(w.charter)] if state == "out" else [])
    rc, out, err = run("checkpoint", "--commit", *named, "-m", "cp")
    assert rc == 0, (out, err)
    assert len(starts) <= 1


def test_rr5b_a6_own_prints_the_pins_lines(make):
    w = make("own")
    rc, out, err = run("checkpoint", "--commit", "a.py", "-m", "cp")
    sha = w.head(w.clone)
    assert rc == 0 and err == ""
    assert out == (f"commit demo: ok {sha}\n"
                   f"checkpoint recorded at {sha[:8]} on main  (tree is dirty)\n")
    rc, out, err = run("checkpoint", "--commit", "a.py", "-m", "cp")
    assert (rc, out.splitlines()[0]) == (0, "nothing to commit")
