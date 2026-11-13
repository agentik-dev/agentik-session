"""Packet fw5 (NICE n84, n78, n81, n71): `commit`, `checkpoint --commit` and the gate under
several writers. R1: no path of a call is in the shared index while its check runs (a witness
index takes the add). R3: `checkpoint --commit <paths...>` commits the named paths alone. R4: a
`commit` that leaves its wait cancels its job (a mark the runner acts on). R5: inside a gate job,
a wait on the job's own key is refused. Every repo, home and state root is the test's own; the
`make` of R4's test is a stub."""
import contextlib
import io
import os
import shlex
import signal
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, config, gate, resolver, sessionconfig
from claude_session import commit as verb

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugin" / "lib"
OTHER = "git -c user.name=other -c user.email=other@" + "example.invalid"
THEIRS = f"echo theirs > b.txt && git add b.txt && {OTHER} commit -qm theirs"
MAIN = ("import runpy, signal; signal.signal(signal.SIGINT, signal.default_int_handler); "
        "runpy.run_module('claude_session', run_name='__main__', alter_sys=True)")


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
        self.msg.write_text("the work\n")

    def write(self, rel, text):
        (self.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.path / rel).write_text(text)

    def head(self):
        return git(self.path, "rev-parse", "HEAD")

    def commit(self, *argv, check="true"):
        return run("commit", *argv, "--check", check, "--message-file", str(self.msg))

    def took(self, rev="HEAD"):
        return git(self.path, "show", "--name-only", "--format=", rev).split()

    def staged(self):
        return git(self.path, "diff", "--cached", "--name-only").split()

    def witness(self):
        return self.path / ".git" / "agentik-commit.witness"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv(gate.JOB_MARK, raising=False)
    r = Repo(tmp_path)
    monkeypatch.chdir(r.path)
    return r


def until(cond, secs=30):
    end = time.monotonic() + secs
    while not cond():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.05)


# ---- R1 and R2 (n84): the witness index ------------------------------------------------------

def test_fw5_a1_a_plain_commit_during_a_green_check_takes_its_own_path_alone(repo):
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt", check=f"sh -c '{THEIRS}'")
    theirs = repo.took("HEAD~1")
    assert (rc, out, theirs) == (0, f"commit scratch: ok {repo.head()}\n", ["b.txt"]), err
    assert repo.took() == ["a.txt"] and not repo.witness().exists()
    assert git(repo.path, "status", "--porcelain") == ""


def test_fw5_a2_a_plain_commit_during_a_red_check_never_holds_this_calls_path(repo):
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt", check=f"sh -c '{THEIRS} && exit 1'")
    theirs = repo.took()
    assert (rc, out, theirs) == (1, "commit scratch: red check exit 1\n", ["b.txt"]), err
    assert repo.staged() == [] and (repo.path / "a.txt").read_text() == "mine\n"
    assert not repo.witness().exists()


def test_fw5_a3_during_the_check_no_path_of_the_call_is_staged(repo):
    repo.write("a.txt", "mine\n")
    check = ("sh -c 'git diff --cached --name-only > .git/cached; "
             "echo ${GIT_INDEX_FILE-unset} > .git/gif'")
    rc, out, err = repo.commit("a.txt", check=check)
    cached = (repo.path / ".git" / "cached").read_text().split()
    gif = (repo.path / ".git" / "gif").read_text().strip()
    assert (cached, gif) == ([], "unset"), err
    assert rc == 0 and repo.took() == ["a.txt"]


def test_fw5_a4_new_files_commit_on_green_and_a_plain_commit_takes_neither(repo):
    repo.write("c.txt", "new\n")
    repo.write("d/e.txt", "new\n")
    rc, out, err = repo.commit("c.txt", "d", check=f"sh -c '{THEIRS}'")
    assert (rc, out) == (0, f"commit scratch: ok {repo.head()}\n"), err
    assert repo.took("HEAD~1") == ["b.txt"] and repo.took() == ["c.txt", "d/e.txt"]
    assert git(repo.path, "status", "--porcelain") == ""


def test_fw5_a4_a_red_pre_commit_hook_leaves_no_intent_to_add_entry(repo):
    hook = repo.path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 5\n")
    hook.chmod(0o755)
    repo.write("c.txt", "new\n")
    head = repo.head()
    rc, out, err = repo.commit("c.txt")
    assert (rc, out) == (1, "commit scratch: red commit exit 1\n"), err
    assert repo.head() == head and git(repo.path, "ls-files", "--", "c.txt") == ""
    assert git(repo.path, "status", "--porcelain", "--", "c.txt") == "?? c.txt"
    assert not repo.witness().exists()


def test_fw5_r2_the_witness_goes_on_a_refusal_and_on_a_red_add(repo):
    rc, out, err = repo.commit("a.txt")                          # nothing to commit
    assert (rc, out) == (2, "") and "nothing to commit" in err
    assert not repo.witness().exists() and repo.staged() == []


# ---- review 1, F1: the index moved between the `add -N` and a red commit --------------------

SPAN = r"""#!/bin/sh
gd=$(git rev-parse --absolute-git-dir); top=$(git rev-parse --show-toplevel)
(
  cd "$top"
  until (set -C; : > "$gd/index.lock") 2>/dev/null; do :; done
  sleep 0.5
  echo other > other.txt
  cp "$gd/index" "$gd/writer.idx"
  GIT_INDEX_FILE="$gd/writer.idx" git add -- %s
  mv "$gd/writer.idx" "$gd/index"; rm -f "$gd/index.lock"
) </dev/null >/dev/null 2>&1 &
exit 1
"""


def moved_span(repo, paths, *names):
    """A red pre-commit hook whose writer, once the commit lets index.lock go, stages `paths`
    by git's protocol: the index moves after the check, during the commit."""
    hook = repo.path / ".git" / "hooks" / "pre-commit"
    hook.write_text(SPAN % paths)
    hook.chmod(0o755)
    rc, out, err = repo.commit(*names)
    gd = repo.path / ".git"
    until(lambda: not (gd / "index.lock").exists() and not (gd / "writer.idx").exists())
    hook.unlink()
    return rc, out, err


def moved_line(err, left):
    return ("commit-step: red commit exit 1; another writer changed the index after the check, "
            f"during the commit, so the index as found is not put back over it: {left}\n") in err


def test_fw5_f1_a_move_during_the_commit_leaves_no_intent_to_add_entry_of_the_call(repo):
    repo.write("n.txt", "new\n")
    rc, out, err = moved_span(repo, "other.txt", "n.txt")
    assert (rc, out) == (1, f"commit scratch: red commit exit 1, {verb.MOVED}\n"), err
    assert git(repo.path, "ls-files", "--", "n.txt") == "" and repo.staged() == ["other.txt"]
    assert moved_line(err, "none of this call's paths is staged or intent-to-add"), err
    git(repo.path, *OTHER.split()[1:], "commit", "-qam", "theirs")      # their sweep
    assert repo.took() == ["other.txt"] and not repo.witness().exists()
    assert git(repo.path, "status", "--porcelain", "--", "n.txt") == "?? n.txt"


def test_fw5_f1_the_moved_line_names_a_path_of_the_call_that_stays_staged(repo):
    repo.write("a.txt", "mine\n")
    repo.write("n.txt", "new\n")
    rc, out, err = moved_span(repo, "a.txt", "a.txt", "n.txt")
    assert (rc, out) == (1, f"commit scratch: red commit exit 1, {verb.MOVED}\n"), err
    assert repo.staged() == ["a.txt"] and git(repo.path, "ls-files", "--", "n.txt") == ""
    top = shlex.quote(git(repo.path, "rev-parse", "--show-toplevel"))
    assert moved_line(err, f"this call's paths still staged or intent-to-add: a.txt; "
                           f"`git -C {top} restore --staged -- a.txt` unstages them"), err


def test_fw5_f1_an_intent_to_add_entry_left_behind_is_named(repo, monkeypatch):
    monkeypatch.setattr(verb, "_unadd", lambda *a: None)                # index.lock not had
    repo.write("n.txt", "new\n")
    rc, out, err = moved_span(repo, "other.txt", "n.txt")
    assert (rc, out) == (1, f"commit scratch: red commit exit 1, {verb.MOVED}\n"), err
    top = shlex.quote(git(repo.path, "rev-parse", "--show-toplevel"))
    assert moved_line(err, f"this call's paths still staged or intent-to-add: n.txt; "
                           f"`git -C {top} restore --staged -- n.txt` unstages them"), err


def test_fw5_f1_gits_reason_on_stdout_reaches_stderr(repo):
    repo.write("a.txt", "mine\n")
    rc, out, err = repo.commit("a.txt", check=f"sh -c 'git add a.txt && {OTHER} commit -qm t'")
    assert (rc, out) == (1, "commit scratch: red commit exit 1\n")
    assert "nothing" in err and repo.took() == ["a.txt"], err


# ---- R3 (n78): checkpoint --commit <paths...> -------------------------------------------------

@pytest.fixture
def session(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "fw5-sess-0000-1111")
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    repo.write("a.txt", "mine\n")
    repo.write("b.txt", "edited\n")
    repo.write("d.txt", "theirs\n")
    git(repo.path, "add", "d.txt")
    return repo


def counter():
    return sessionconfig.load_overlay().get("_prompts_since_checkpoint")


def test_fw5_a5_checkpoint_commit_takes_the_named_paths_alone(session):
    rc, out, err = run("checkpoint", "--commit", "a.txt", "-m", "cp")
    assert rc == 0, err
    assert session.took() == ["a.txt"] and session.staged() == ["d.txt"]
    assert git(session.path, "log", "-1", "--format=%s") == "cp" and counter() == 0
    assert git(session.path, "status", "--porcelain", "--", "b.txt") == "M b.txt"


@pytest.mark.parametrize("argv", [("--commit", "-m", "cp"), ("a.txt",), ("a.txt", "-m", "cp")])
def test_fw5_a6_checkpoint_refuses_the_commit_without_its_paths(session, argv):
    head, index = session.head(), git(session.path, "ls-files", "-s")
    rc, out, err = run("checkpoint", *argv)
    assert (rc, head) == (2, session.head()), (rc, session.took(), err)
    assert git(session.path, "ls-files", "-s") == index and counter() == 5
    assert "checkpoint --commit <paths...>" in err and len(err.strip().splitlines()) == 1


def test_fw5_r3_nothing_to_commit_is_recorded_and_a_red_commit_is_not(session):
    rc, out, err = run("checkpoint", "--commit", "Makefile", "-m", "cp")
    assert (rc, out.splitlines()[0]) == (0, "nothing to commit") and counter() == 0, err
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    hook = session.path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 5\n")
    hook.chmod(0o755)
    head = session.head()
    rc, out, err = run("checkpoint", "--commit", "a.txt", "-m", "cp")
    assert rc == 1 and session.head() == head and counter() == 5, (out, err)


def test_fw5_r3_a_refusal_of_the_core_is_exit_2_and_nothing_recorded(session, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x\n")
    rc, out, err = run("checkpoint", "--commit", str(outside), "-m", "cp")
    assert rc == 2 and "outside the repo" in err and counter() == 5, (out, err)


# ---- R4 (n81): a commit that leaves its wait cancels its job ---------------------------------

def mark(root, gid):
    return gate.gate_dir(root) / "queue" / f"{gid}.cancel"


def test_fw5_a7_a_job_not_yet_started_is_closed_unrun(tmp_path):
    root = resolver.state_dir(os.environ)
    d = tmp_path / "r"
    d.mkdir()
    e = gate.enqueue(root, d, ["/bin/sh", "-c", "touch ran"], {}, [], 60, "x", None, time.time())
    mark(root, e["id"]).write_text("")
    spawned = []
    gate.serve(root, gate.Fx(idle=0, poll=0.01, popen=lambda *a, **k: spawned.append(a)))
    r = gate.wait(root, e["id"], timeout=0)[1]
    assert (r["exit"], r["cut"], spawned) == (130, "caller cut", []), r
    assert not (d / "ran").exists() and not mark(root, e["id"]).exists()


def test_fw5_a7_a_cut_wait_writes_the_mark_and_says_so(repo, monkeypatch, capsys):
    root = resolver.state_dir(os.environ)
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)

    def cut(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(gate, "wait", cut)
    repo.write("a.txt", "mine\n")
    with pytest.raises(KeyboardInterrupt):
        verb.commit(str(repo.path), ["a.txt"], "make check", str(repo.msg), os.environ)
    (e,) = gate.entries(root)
    err = capsys.readouterr().err
    assert mark(root, e["id"]).exists() and f"commit-step: check {e['id']} cut" in err, err


def test_fw5_a7_sigint_to_commit_cuts_its_running_job(repo, tmp_path):
    root = resolver.state_dir(os.environ)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    stub = bin_ / "make"
    stub.write_text("#!/bin/sh\necho $$ > .git/stubpid\nexec sleep 30\n")
    stub.chmod(0o755)
    pidf = repo.path / ".git" / "stubpid"
    repo.write("a.txt", "mine\n")
    env = dict(os.environ, PYTHONPATH=str(LIB), PYTHONDONTWRITEBYTECODE="1",
               PATH=f"{bin_}{os.pathsep}{os.environ['PATH']}")
    p = subprocess.Popen([sys.executable, "-c", MAIN, "commit", "a.txt", "--check",
                          "make check", "--message-file", str(repo.msg)], cwd=repo.path,
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        until(lambda: (pidf.exists() and pidf.read_text().strip()) or p.poll() is not None)
        stubpid = int(pidf.read_text())
        (first,) = [x["id"] for x in gate.entries(root)]
        nxt = gate.enqueue(root, repo.path, ["/bin/echo", "next"], {}, [], 60, "next", None,
                           time.time())
        t0 = time.time()
        p.send_signal(signal.SIGINT)
        out, err = p.communicate(timeout=60)
        until(lambda: gate.result_path(root, nxt["id"]).exists(), secs=45)
        r = gate.wait(root, first, timeout=0)[1]
        n = gate.wait(root, nxt["id"], timeout=0)[1]
        gone = subprocess.run(["kill", "-0", str(stubpid)], capture_output=True).returncode
        code = p.returncode if p.returncode >= 0 else 128 - p.returncode    # a shell's view
        got = (code, r["exit"], r["cut"], round(r["ended"] - t0) < 10,
               round(n["started"] - t0) < 10, gone != 0)
        assert got == (130, 130, "caller cut", True, True, True), (got, r, n, err)
        assert f"commit-step: check {first} cut" in err and not mark(root, first).exists()
    finally:
        p.kill()
        pid = (gate.runner_info(root) or {}).get("pid")
        if isinstance(pid, int) and pid > 1:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)


# ---- R5 (n71): inside a gate job, a wait on its own key is refused ---------------------------

@pytest.fixture
def job(repo, monkeypatch, tmp_path):
    root = resolver.state_dir(os.environ)
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.setattr(gate, "wait", lambda root, gid, **k: (0, {
        "id": gid, "repo": "r", "exit": 0, "seconds": 0.1, "log": "l"}))
    outer = gate.enqueue(root, repo.path, ["make", "check"], {}, [], 60, "outer", None,
                         time.time())
    monkeypatch.setenv(gate.JOB_MARK, outer["id"])
    other = tmp_path / "other"
    other.mkdir()
    return root, outer, other


def test_fw5_a8_gate_run_wait_on_the_jobs_own_repo_is_refused(repo, job):
    root, outer, other = job
    rc, out, err = run("gate", "run", "--wait", str(repo.path), "--", "/bin/echo", "inner")
    assert (rc, out, len(gate.entries(root))) == (2, "", 1), (out, err)
    assert f"this is gate job {outer['id']}" in err


def test_fw5_a8_no_wait_another_repo_or_no_entry_queue_as_today(repo, job, monkeypatch):
    root, outer, other = job
    assert run("gate", "run", str(repo.path), "--", "/bin/echo", "inner")[0] == 0
    assert run("gate", "run", "--wait", str(other), "--", "/bin/echo", "inner")[0] == 0
    monkeypatch.setenv(gate.JOB_MARK, "20200101-000000-999")
    assert run("gate", "run", "--wait", str(repo.path), "--", "/bin/echo", "inner")[0] == 0
    assert len(gate.entries(root)) == 4


def test_fw5_a8_gate_wait_on_a_queued_id_of_the_jobs_key_is_refused(repo, job):
    root, outer, other = job
    mine = gate.enqueue(root, repo.path, ["/bin/echo"], {}, [], 60, "", None, time.time())
    theirs = gate.enqueue(root, other, ["/bin/echo"], {}, [], 60, "", None, time.time())
    rc, out, err = run("gate", "wait", mine["id"])
    assert (rc, out) == (2, ""), err
    assert run("gate", "wait", theirs["id"])[0] == 0
