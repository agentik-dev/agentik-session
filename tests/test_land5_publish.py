"""Packet land5-publish: `gate publish <repo>... [--dry-run]` and `gate land --push`. One call
proves main's head checked green from the gate's own results, runs the scans and pushes that
sha. Each case is a made-up repo `crate` in a temp folder (its own HOME, state root and git
identity) with a bare `crate.git` beside it as `origin`; the gate results are files the test
writes under that temp state root, save line 11's, which a queue of the test's own writes. The
session's own env names are scrubbed, so no case reads the caller's sitting."""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import gate, resolver

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugin" / "lib" / "agentik-session"
SCRUB = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "CLAUDE_CODE_SESSION_ID", gate.JOB_MARK,
         "CLAUDE_SESSION_HELPER", "CLAUDE_SESSION_DEPTH", "RELAY_ROW", "CLAUDE_SESSION_PROFILE",
         "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "MAKELEVEL", "CHECK_EXIT", "HYG_TREE",
         "HYG_RANGE", "HYG_MOVE")
CHECK = "check:\n\t@exit $${CHECK_EXIT:-0}\n"
# A hygiene that knows --commits: its argv to $LAND_ORDER; $HYG_TREE and $HYG_RANGE are the
# exits of the tree's scan and the range's; $HYG_MOVE moves main on the tree's scan, to a new
# commit of the same tree.
HYGIENE = r"""#!/bin/sh
echo "hygiene $*" >> "$LAND_ORDER"
case $1 in --help) echo 'usage: hygiene [--require-private] [--commits RANGE]'; exit 0 ;; esac
if [ "$1" = --require-private ]; then exit "${HYG_RANGE:-0}"; fi
if [ -n "${HYG_MOVE:-}" ]; then
  git update-ref refs/heads/main "$(git commit-tree HEAD^{tree} -p HEAD -m newer)"
fi
exit "${HYG_TREE:-0}"
"""


class Crate:
    """A made-up repo on main, `<name>.git` beside it as origin, main's upstream."""

    def __init__(self, tmp, name="crate", hygiene=True):
        self.tmp = tmp
        cfg = tmp / "gitconfig"
        cfg.write_text("[user]\n\tname = t\n\temail = t@" + "example.invalid\n"
                       "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        self.order = tmp / ("order-" + name)
        self.env = {k: v for k, v in os.environ.items() if k not in SCRUB}
        self.env.update({"HOME": str(tmp), "XDG_STATE_HOME": str(tmp / "state"),
                         "XDG_CONFIG_HOME": str(tmp / "config"), "GIT_CONFIG_GLOBAL": str(cfg),
                         "GIT_CONFIG_NOSYSTEM": "1", "LAND_ORDER": str(self.order),
                         "TMPDIR": str(tmp)})
        self.root = resolver.state_dir(self.env)
        self.name = name
        self.repo = tmp / name
        self.bare = tmp / (name + ".git")
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        files = {".gitignore": ".claude/worktrees/\n", "Makefile": CHECK, "shared.txt": "base\n"}
        if hygiene:
            files["scripts/hygiene"] = HYGIENE
        self.put(files)
        if hygiene:
            os.chmod(str(self.repo / "scripts" / "hygiene"), 0o755)
        self.commit("base")
        self.git(self.tmp, "clone", "-q", "--bare", str(self.repo), str(self.bare))
        self.git(self.repo, "remote", "add", "origin", str(self.bare))
        self.git(self.repo, "fetch", "-q", "origin")
        self.git(self.repo, "branch", "-q", "-u", "origin/main", "main")
        self.ids = 0

    def git(self, cwd, *args, input=None):
        return subprocess.run(["git", "-C", str(cwd), *args], env=self.env, check=True,
                              capture_output=True, text=True, input=input).stdout.strip()

    def put(self, files):
        for rel, text in files.items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def commit(self, message, files=None):
        if files:
            self.put(files)
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-qm", message)
        return self.sha("HEAD")

    def sha(self, rev, cwd=None):
        return self.git(cwd or self.repo, "rev-parse", rev)

    def landed(self, branch="p1-crate"):
        """A --no-ff merge on main, as a landing makes: (main before, the branch's head, S)."""
        before = self.sha("main")
        self.git(self.repo, "switch", "-q", "-c", branch)
        head = self.commit("the work", {"f.txt": "work\n"})
        self.git(self.repo, "switch", "-q", "main")
        self.git(self.repo, "merge", "-q", "--no-ff", "-m", "Merge %s: made up" % branch, branch)
        return before, head, self.sha("main")

    def result(self, log_lines=(), raw=None, **over):
        """A result file under the temp state root, and its log; its id."""
        self.ids += 1
        gid = "20261114-000000-%d" % (self.ids + 100 * len(self.name))
        d = gate.entry_dir(self.root, gid)
        d.mkdir(parents=True)
        log = d / "log"
        log.write_text("".join("%s\n" % x for x in
                               ["gate %s: %s: job" % (gid, self.repo), *log_lines,
                                "gate %s: exit 0 in 1 s" % gid]))
        doc = {"id": gid, "repo": str(self.repo), "exit": 0, "log": str(log), "cut": None,
               "head": None, "dirty": {"start": 0, "end": 0}, "command": ["make", "check"],
               "make_env": []}
        doc.update(over)
        gate.result_path(self.root, gid).write_text(raw if raw is not None else json.dumps(doc))
        return gid

    def argv_head(self):
        """`gate.self_argv()` as `gate publish`'s own process reads it under this env."""
        cache = self.env.get("XDG_CACHE_HOME") or os.path.join(self.env["HOME"], ".cache")
        return [sys.executable, "-I", "-X", "pycache_prefix=" + os.path.join(
            cache, "agentik", "pycache"), os.path.realpath(str(RUNNER))]

    def land_command(self, sha, repo=None):
        """The command `_gate_land` queues, whole (review 1 F1)."""
        return [*self.argv_head(), "gate", "land", "--in-job", str(repo or self.repo),
                "p1-crate", sha, str(self.tmp / "msg")]

    def land_result(self, before, line, sha=None, **over):
        """A landing's result; its command carries the sha the ok line names unless given."""
        if sha is None:
            sha = line.split(": ok ", 1)[1].split(",", 1)[0] if ": ok " in line else "x"
        return self.result(["land-step: check: make check", line], **{
            "head": before, "command": self.land_command(sha), **over})

    def check_result(self, head, **over):
        return self.result(["make check"], **{"head": head, **over})

    def publish(self, *args, env=None):
        p = subprocess.run([sys.executable, str(RUNNER), "gate", "publish", *args],
                           env={**self.env, **(env or {})}, capture_output=True, text=True,
                           timeout=600, cwd=str(self.tmp))
        return p.returncode, p.stdout, p.stderr

    def bare_main(self):
        return self.sha("refs/heads/main", cwd=self.bare)

    def refs(self):
        return (self.git(self.repo, "for-each-ref"), self.git(self.bare, "for-each-ref"))

    def ran(self):
        return self.order.read_text().splitlines() if self.order.exists() else []

    def recorder(self):
        """An env whose `git` writes its argv to <tmp>/git-argv, then runs the real one."""
        bindir = self.tmp / "rec"
        bindir.mkdir(exist_ok=True)
        real = shutil.which("git", path=self.env["PATH"])
        rec = bindir / "git"
        rec.write_text('#!/bin/sh\necho "$*" >> "%s"\nexec "%s" "$@"\n'
                       % (self.tmp / "git-argv", real))
        rec.chmod(0o755)
        return {"PATH": str(bindir) + os.pathsep + self.env["PATH"]}

    def git_argv(self):
        path = self.tmp / "git-argv"
        return path.read_text().splitlines() if path.exists() else []


@pytest.fixture
def c(tmp_path):
    return Crate(tmp_path.resolve())


def line(c, text):
    return "publish %s: %s\n" % (c.name, text)


# 1. A landed merge with its result is pushed.

@pytest.mark.parametrize("form", ["plain", "prefix", "as", "unscanned"])
def test_land5_1_a_landed_merge_is_pushed(c, form):
    before, head, s = c.landed()
    given = {"plain": head, "prefix": head[:9], "as": "1" * 40, "unscanned": head}[form]
    tail = {"plain": "", "prefix": "", "as": ", as %s, plugin 1.0.0-alpha.2" % head,
            "unscanned": ", range not scanned"}[form]
    c.land_result(before, "land crate: ok %s, main readied%s" % (given, tail))
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.bare_main() == s
    assert "hygiene --require-private --commits %s..%s" % (before, s) in c.ran()


# 2. The same again: already pushed, no push started.

def test_land5_2_the_same_again_is_already_pushed(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    assert c.publish(str(c.repo))[0] == 0
    rc, out, err = c.publish(str(c.repo), env=c.recorder())
    assert (rc, out) == (0, line(c, "ok %s, already pushed" % s)), err
    argv = c.git_argv()
    assert argv and not [a for a in argv if a.startswith("push")]
    assert not [a for a in argv if a.startswith("fetch")]


# 3. No proof of a landing.

@pytest.mark.parametrize("case", ["none", "exit2", "other-sha", "as-other", "other-repo",
                                  "not-json", "exit-string", "dirty-string"])
def test_land5_3_no_landing_proof_is_red_proof(c, case):
    before, head, s = c.landed()
    bare = c.bare_main()
    ok = "land crate: ok %s, main readied" % head
    if case == "exit2":
        c.land_result(before, ok, exit=2)
    elif case == "other-sha":
        c.land_result(before, "land crate: ok %s, main readied" % before)
    elif case == "as-other":
        c.land_result(before, ok + ", as %s, plugin 1.0.0-alpha.2" % before)
    elif case == "other-repo":
        c.land_result(before, ok, repo=str(c.tmp / "other"))
    elif case == "not-json":
        c.land_result(before, ok, raw="{not json")
    elif case == "exit-string":
        c.land_result(before, ok, exit="0")
    elif case == "dirty-string":
        c.check_result(s, dirty="0")
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert "agentik session gate run %s -- make check" % c.repo in err
    assert c.bare_main() == bare
    assert not gate.entries(c.root)


# 4. A check result proves main's head; its near misses do not.

@pytest.mark.parametrize("cmd", [["make", "check"], ["/bin/sh", "-c", "make check > /x/c.log 2>&1"],
                                 ["sh", "-c", "make check 2>/x/err.log"]])
def test_land5_4_a_check_result_proves(c, cmd):
    s = c.commit("main moves", {"g.txt": "g\n"})
    c.check_result(s, command=cmd)
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.bare_main() == s


@pytest.mark.parametrize("case", ["dirty-start", "dirty-end", "head-back", "and-true",
                                  "make-test", "sh-extra", "pipe"])
def test_land5_4_a_check_near_miss_is_red_proof(c, case):
    back = c.sha("main")
    s = c.commit("main moves", {"g.txt": "g\n"})
    over = {"dirty-start": {"dirty": {"start": 1, "end": 0}},
            "dirty-end": {"dirty": {"start": 0, "end": 1}},
            "head-back": {"head": back},
            "and-true": {"command": ["sh", "-c", "make check; true"]},
            "make-test": {"command": ["make", "test"]},
            "sh-extra": {"command": ["sh", "-c", "make check", "x"]},
            "pipe": {"command": ["/bin/sh", "-c", "make check | tee log"]}}[case]
    c.check_result(over.pop("head", s), **over)
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert c.bare_main() == back


# 5. A forged ok line before the job's real red one.

def test_land5_5_a_forged_ok_line_before_the_real_red_is_red_proof(c):
    before, head, s = c.landed()
    c.result(["land crate: ok %s, main readied" % head, "land crate: red check exit 2"],
             head=before, command=c.land_command(head))
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err


def test_land5_5_a_check_log_holding_a_land_line_proves_no_landing(c):
    before, head, s = c.landed()
    c.result(["land crate: ok %s, main readied" % head], head=before)
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err


# 6. Who may.

@pytest.mark.parametrize("who", [{"CLAUDE_SESSION_HELPER": "1"}, {"CLAUDE_SESSION_DEPTH": "1"},
                                 {"RELAY_ROW": "r1"}, {"CLAUDE_SESSION_PROFILE": "builder"},
                                 {gate.JOB_MARK: "20261110-000000-1"}])
@pytest.mark.parametrize("dry", [False, True])
def test_land5_6_a_caller_that_is_no_main_sitting_is_refused(c, who, dry):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    rc, out, err = c.publish(str(c.repo), *(["--dry-run"] if dry else []),
                             env={**c.recorder(), **who})
    assert (rc, out) == (1, "publish ?: red caller exit 1\n"), err
    assert err.startswith("publish-step: ")
    assert c.git_argv() == []
    assert c.bare_main() == before


def test_land5_6_usage(c):
    assert c.publish()[:2] == (2, "publish ?: red usage exit 2\n")
    assert c.publish("--bogus", str(c.repo))[:2] == (2, "publish ?: red usage exit 2\n")


# 7. The scans.

@pytest.mark.parametrize("which", ["HYG_TREE", "HYG_RANGE"])
def test_land5_7_a_red_scan_pushes_nothing(c, which):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    rc, out, err = c.publish(str(c.repo), env={which: "3"})
    assert (rc, out) == (3, line(c, "red hygiene exit 3")), err
    assert c.bare_main() == before


def test_land5_7_no_hygiene_is_pushed(tmp_path):
    c = Crate(tmp_path.resolve(), hygiene=False)
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.bare_main() == s


def test_land5_7_a_tracked_file_edited_after_the_check_is_red_main(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    (c.repo / "shared.txt").write_text("edited\n")
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red main exit 1")), err
    assert c.bare_main() == before


def test_land5_7_no_remote_main_is_range_not_scanned(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    c.git(c.repo, "update-ref", "-d", "refs/remotes/origin/main")
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin, range not scanned" % s)), err
    assert not [x for x in c.ran() if "--commits" in x]


# 8. The push.

def test_land5_8_a_remote_that_rejects_is_red_push_never_forced(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    moved = c.git(c.bare, "commit-tree", before + "^{tree}", "-p", before, "-m", "elsewhere")
    c.git(c.bare, "update-ref", "refs/heads/main", moved)
    rc, out, err = c.publish(str(c.repo), env=c.recorder())
    assert rc != 0 and out == line(c, "red push exit %d" % rc), err
    assert c.bare_main() == moved
    assert [a for a in c.git_argv() if a.startswith("push")] == [
        "push --no-follow-tags origin %s:refs/heads/main" % s]


def test_land5_8_main_moved_after_s_was_read_pushes_s(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    rc, out, err = c.publish(str(c.repo), env={"HYG_MOVE": "1"})
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.bare_main() == s
    assert c.sha("main") != s


# 9. The dry run.

def test_land5_9_dry_run_would_push_and_writes_nothing(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    refs = c.refs()
    rc, out, err = c.publish(str(c.repo), "--dry-run")
    assert (rc, out) == (0, line(c, "would push %s to origin" % s)), err
    assert c.refs() == refs
    assert c.bare_main() == before


# 3, R3: where main stands, and the remote.

@pytest.mark.parametrize("case", ["no-remote", "dash", "merge", "off-main"])
def test_land5_r3_main_and_the_remote(c, case):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    if case == "no-remote":
        c.git(c.repo, "config", "--unset", "branch.main.remote")
    elif case == "dash":
        c.git(c.repo, "config", "branch.main.remote", "-x")
    elif case == "merge":
        c.git(c.repo, "config", "branch.main.merge", "refs/heads/other")
    else:
        c.git(c.repo, "switch", "-q", "p1-crate")
    rc, out, err = c.publish(str(c.repo))
    step = "main" if case == "off-main" else "remote"
    assert (rc, out) == (1, line(c, "red %s exit 1" % step)), err
    assert c.bare_main() == before


# 10. Two repos.

def test_land5_10_two_repos_the_first_without_proof(tmp_path):
    tmp = tmp_path.resolve()
    a, b = Crate(tmp), Crate(tmp, name="spool")
    a.landed()
    s = b.commit("main moves", {"g.txt": "g\n"})
    b.check_result(s)
    rc, out, err = a.publish(str(a.repo), str(b.repo))
    assert (rc, out) == (1, line(a, "red proof exit 1") + line(b, "ok %s, pushed to origin" % s))
    assert b.bare_main() == s


# 11. gate land --push, through a queue of the test's own.

def land_argv(c, *extra, sha):
    return [sys.executable, str(RUNNER), "gate", "land", *extra, str(c.repo), "p1-crate", sha,
            str(c.tmp / "msg")]


@pytest.fixture
def lc(tmp_path):
    c = Crate(tmp_path.resolve(), hygiene=False)
    tree = c.repo / ".claude" / "worktrees" / "p1-crate"
    c.git(c.repo, "worktree", "add", "-q", "-b", "p1-crate", str(tree), "main")
    (tree / "f.txt").write_text("work\n")
    c.git(tree, "add", "f.txt")
    c.git(tree, "commit", "-qm", "the work")
    c.head = c.sha("HEAD", cwd=tree)
    (c.tmp / "msg").write_text("Merge p1-crate: a made-up landing\n\nOne line.\n")
    yield c
    for path in c.root.glob("**/runner.json"):
        try:
            os.kill(int(json.loads(path.read_text())["pid"]), signal.SIGTERM)
        except (OSError, ValueError, KeyError, TypeError):
            pass


def run(c, argv, env=None):
    p = subprocess.run(argv, env={**c.env, **(env or {})}, capture_output=True, text=True,
                       timeout=900, cwd=str(c.tmp))
    return p.returncode, p.stdout, p.stderr


def test_land5_11_land_push_lands_then_pushes(lc):
    before = lc.sha("main")
    rc, out, err = run(lc, land_argv(lc, "--push", sha=lc.head))
    s = lc.sha("main")
    assert lc.sha("main^2") == lc.head and lc.sha("main^1") == before
    assert (rc, out) == (0, "land crate: ok %s, main readied\n" % lc.head
                         + line(lc, "ok %s, pushed to origin" % s)), err
    assert lc.bare_main() == s


def test_land5_11_a_red_landing_pushes_nothing(lc):
    before = lc.sha("main")
    rc, out, err = run(lc, land_argv(lc, "--push", sha=lc.head), env={"CHECK_EXIT": "2"})
    assert (rc, out) == (2, "land crate: red check exit 2\n"), err
    assert lc.bare_main() == before


@pytest.mark.parametrize("who", [{"CLAUDE_SESSION_HELPER": "1"}, {"CLAUDE_SESSION_DEPTH": "1"},
                                 {"RELAY_ROW": "r1"}, {"CLAUDE_SESSION_PROFILE": "builder"},
                                 {gate.JOB_MARK: "20261110-000000-1"}])
def test_land5_11_land_push_is_refused_before_it_queues(lc, who):
    rc, out, err = run(lc, land_argv(lc, "--push", sha=lc.head), env=who)
    assert (rc, out) == (1, "land ?: red caller exit 1\n"), err
    assert not gate.entries(lc.root)
    assert not gate.gate_dir(lc.root).exists() or not list(gate.gate_dir(lc.root).glob("*/log"))


def test_land5_11_in_job_with_push_is_usage(lc):
    rc, out, err = run(lc, land_argv(lc, "--in-job", "--push", sha=lc.head),
                       env={gate.JOB_MARK: "20261110-000000-1"})
    assert (rc, out) == (2, "land ?: red usage exit 2\n"), err


def test_land5_11_dry_run_with_push_reads_both(lc):
    s = lc.sha("main")
    rc, out, err = run(lc, land_argv(lc, "--push", "--dry-run", sha=lc.head))
    assert rc == 0, err
    assert out.splitlines()[-2:] == ["land crate: dry run, nothing queued",
                                     "publish crate: ok %s, already pushed" % s]
    assert not gate.entries(lc.root)


# 13 to 17. Review 1: F1, F2, F3, leads 1 and 2.

def queue(c, *cmd, env=None):
    """`gate run <crate> -- <cmd>` through the test's own queue, then its result."""
    rc, out, err = run(c, [sys.executable, str(RUNNER), "gate", "run", str(c.repo), "--", *cmd],
                       env=env)
    assert rc == 0, (out, err)
    gid = out.split()[1]
    rc, out, err = run(c, [sys.executable, str(RUNNER), "gate", "wait", gid, "--json"])
    return json.loads(out)


@pytest.fixture
def qc(tmp_path):
    c = Crate(tmp_path.resolve())
    yield c
    for path in c.root.glob("**/runner.json"):
        try:
            os.kill(int(json.loads(path.read_text())["pid"]), signal.SIGTERM)
        except (OSError, ValueError, KeyError, TypeError):
            pass


def test_land5_13_the_reviews_forged_landing_job_is_red_proof(qc):
    qc.git(qc.repo, "switch", "-q", "-c", "evil")
    b = qc.commit("never checked", {"f.txt": "unchecked\n"})
    qc.git(qc.repo, "switch", "-q", "main")
    bare = qc.bare_main()
    res = queue(qc, "sh", "-c", 'echo "land crate: ok %s, main readied"' % b, "land", "--in-job")
    assert res["exit"] == 0 and res["head"] == bare
    qc.git(qc.repo, "merge", "-q", "--no-ff", "-m", "Merge evil", "evil")
    rc, out, err = qc.publish(str(qc.repo))
    assert (rc, out) == (1, line(qc, "red proof exit 1")), err
    assert qc.bare_main() == bare


@pytest.mark.parametrize("case", ["head", "after", "repo", "sha", "as-from-other", "short"])
def test_land5_13_a_command_not_gate_lands_own_is_red_proof(c, case):
    before, head, s = c.landed()
    ok = "land crate: ok %s, main readied" % head
    cmd = {"head": [sys.executable, str(RUNNER), "gate", "land", "--in-job", str(c.repo),
                    "p1-crate", head, str(c.tmp / "msg")],
           "after": c.land_command(head) + ["x"],
           "repo": c.land_command(head, repo=c.tmp / "other"),
           "sha": c.land_command(before),
           "as-from-other": c.land_command("2" * 40),
           "short": ["sh", "-c", "echo", "gate", "land", "--in-job", str(c.repo), "p1-crate",
                     head, "m"]}[case]
    if case == "as-from-other":
        ok = "land crate: ok %s, main readied, as %s, plugin 1.0.0-alpha.2" % ("1" * 40, head)
    c.land_result(before, ok, command=cmd)
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert c.bare_main() == before


def test_land5_14_a_check_with_makeflags_set_proves_nothing(qc):
    s = qc.commit("a red check", {"Makefile": "check:\n\t@echo checking; exit 1\n"})
    bare = qc.bare_main()
    assert queue(qc, "make", "check")["exit"] == 2
    res = queue(qc, "make", "check", env={"MAKEFLAGS": "n"})
    assert (res["exit"], res["head"], res["make_env"]) == (0, s, ["MAKEFLAGS"])
    rc, out, err = qc.publish(str(qc.repo))
    assert (rc, out) == (1, line(qc, "red proof exit 1")), err
    assert qc.bare_main() == bare


def test_land5_14_a_check_with_no_make_env_is_pushed(qc):
    s = qc.commit("main moves", {"g.txt": "g\n"})
    res = queue(qc, "make", "check")
    assert (res["exit"], res["head"], res["make_env"]) == (0, s, [])
    rc, out, err = qc.publish(str(qc.repo))
    assert (rc, out) == (0, line(qc, "ok %s, pushed to origin" % s)), err


def test_land5_14_make_env_names_the_four_set_sorted():
    env = {"PATH": "/bin", "MAKEFILES": "", "MFLAGS": "-n", "GNUMAKEFLAGS": "x", "MAKEFLAGS": "n",
           "MAKELEVEL": "1"}
    assert gate.make_env(env) == ["GNUMAKEFLAGS", "MAKEFILES", "MAKEFLAGS", "MFLAGS"]
    assert gate.make_env({"PATH": "/bin"}) == [] and gate.make_env(None) is None
    assert gate.RESULT_KEYS[-1] == "make_env"


@pytest.mark.parametrize("case", ["absent", "set", "string", "null"])
def test_land5_14_a_check_result_without_an_empty_make_env_is_red_proof(c, case):
    back = c.sha("main")
    s = c.commit("main moves", {"g.txt": "g\n"})
    gid = c.check_result(s, make_env={"set": ["MFLAGS"], "string": "", "null": None}.get(case, []))
    if case == "absent":
        path = gate.result_path(c.root, gid)
        doc = json.loads(path.read_text())
        del doc["make_env"]
        path.write_text(json.dumps(doc))
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert c.bare_main() == back


def _collide(c, base, prefix):
    """A commit on `base` whose sha opens with `prefix`, its tree another than base's."""
    tree = c.git(c.repo, "mktree", input="100644 blob %s\tf.txt\n" % c.git(
        c.repo, "hash-object", "-w", "--stdin", input="other\n"))
    sig = "t <t@%s> 1700000000 +0000" % "example.invalid"
    n = 0
    while True:
        body = ("tree %s\nparent %s\nauthor %s\ncommitter %s\n\nanother %d\n"
                % (tree, base, sig, sig, n)).encode()
        if hashlib.sha1(b"commit %d\0" % len(body) + body).hexdigest().startswith(prefix):
            break
        n += 1
    p = subprocess.run(["git", "-C", str(c.repo), "hash-object", "-t", "commit", "-w", "--stdin"],
                       input=body, capture_output=True, env=c.env, check=True)
    return p.stdout.decode().strip()


def test_land5_15_an_ambiguous_prefix_proves_nothing(c):
    before, head, s1 = c.landed()
    pre = head[:4]
    c.land_result(before, "land crate: ok %s, main readied" % pre)
    c.git(c.repo, "reset", "-q", "--hard", before)
    b2 = _collide(c, before, pre)
    assert b2 != head and b2[:4] == pre
    c.git(c.repo, "update-ref", "refs/heads/evil2", b2)
    c.git(c.repo, "merge", "-q", "--no-ff", "-m", "Merge evil2", "evil2")
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert c.bare_main() == before


def test_land5_16_follow_tags_pushes_no_tag(c):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    c.git(c.repo, "tag", "-a", "a-tag", "-m", "a note", head)
    c.git(c.repo, "config", "push.followTags", "true")
    rc, out, err = c.publish(str(c.repo), env=c.recorder())
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.git(c.bare, "tag", "-l") == "" and c.bare_main() == s
    assert [a for a in c.git_argv() if a.startswith("push")] == [
        "push --no-follow-tags origin %s:refs/heads/main" % s]


@pytest.mark.parametrize("case", ["path", "url", "unlisted"])
def test_land5_17_a_remote_that_is_no_listed_name_is_red_remote(c, case):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    other = c.tmp / "other.git"
    c.git(c.tmp, "clone", "-q", "--bare", str(c.bare), str(other))
    c.git(c.repo, "config", "branch.main.remote",
          {"path": str(other), "url": "file://" + str(other), "unlisted": "upstream"}[case])
    rc, out, err = c.publish(str(c.repo), env=c.recorder())
    assert (rc, out) == (1, line(c, "red remote exit 1")), err
    assert not [a for a in c.git_argv() if a.startswith("push")]
    assert c.sha("refs/heads/main", cwd=other) == before and c.bare_main() == before


# 18 to 20. Review 2: F1, F2, lead 1.

def test_land5_18_makefiles_under_a_landing_runs_the_real_check(lc):
    tree = lc.repo / ".claude" / "worktrees" / "p1-crate"
    (tree / "Makefile").write_text("check:\n\t@echo REAL-CHECK-RAN; exit 1\n")
    lc.git(tree, "commit", "-qam", "a red check")
    lc.head = lc.sha("HEAD", cwd=tree)
    before = lc.sha("main")
    extra = lc.tmp / "extra.mk"
    extra.write_text("override SHELL := /usr/bin/true\n")
    rc, out, err = run(lc, land_argv(lc, "--push", sha=lc.head), env={"MAKEFILES": str(extra)})
    assert (rc, out) == (2, "land crate: red check exit 2\n"), err
    assert lc.sha("main") == before and lc.bare_main() == before
    logs = "".join(p.read_text() for p in lc.root.glob("**/log"))
    assert "REAL-CHECK-RAN" in logs


@pytest.mark.parametrize("case", ["makefiles", "absent", "null", "string", "others"])
def test_land5_18_a_landing_proves_only_with_no_makefiles_in_make_env(c, case):
    before, head, s = c.landed()
    env = {"makefiles": ["MAKEFILES"], "null": None, "string": "",
           "others": ["GNUMAKEFLAGS", "MAKEFLAGS", "MFLAGS"]}.get(case)
    gid = c.land_result(before, "land crate: ok %s, main readied" % head, make_env=env)
    if case == "absent":
        path = gate.result_path(c.root, gid)
        doc = json.loads(path.read_text())
        del doc["make_env"]
        path.write_text(json.dumps(doc))
    rc, out, err = c.publish(str(c.repo))
    if case == "others":
        assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
        assert c.bare_main() == s
    else:
        assert (rc, out) == (1, line(c, "red proof exit 1")), err
        assert c.bare_main() == before


@pytest.mark.parametrize("kind", ["branch", "tag"])
def test_land5_19_a_ref_named_as_the_prefix_proves_nothing(c, kind):
    before, head, s1 = c.landed()
    pre = head[:4]
    c.land_result(before, "land crate: ok %s, main readied" % pre)
    c.git(c.repo, "reset", "-q", "--hard", before)
    b2 = _collide(c, before, pre)
    assert b2 != head and b2[:4] == pre
    c.git(c.repo, kind, pre, b2)
    c.git(c.repo, "update-ref", "refs/heads/evil2", b2)
    c.git(c.repo, "merge", "-q", "--no-ff", "-m", "Merge evil2", "evil2")
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (1, line(c, "red proof exit 1")), err
    assert c.bare_main() == before


@pytest.mark.parametrize("kind", ["branch", "tag"])
def test_land5_19_a_ref_named_as_the_word_changes_nothing(c, kind):
    before, head, s = c.landed()
    c.git(c.repo, kind, head[:9], before)
    c.land_result(before, "land crate: ok %s, main readied" % head[:9])
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert c.bare_main() == s


def test_land5_20_a_hygiene_without_the_exec_bit_is_red_hygiene(c):
    os.chmod(str(c.repo / "scripts" / "hygiene"), 0o644)
    c.git(c.repo, "update-index", "--chmod=-x", "scripts/hygiene")
    c.git(c.repo, "commit", "-qm", "no exec bit")
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    bare = c.bare_main()
    rc, out, err = c.publish(str(c.repo))
    assert (rc, out) == (126, line(c, "red hygiene exit 126")), err
    assert "not executable" in err and not c.ran()
    assert c.bare_main() == bare != s
