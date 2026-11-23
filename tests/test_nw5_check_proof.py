"""Packet nw5-check-proof (design/31 items 21 to 24): a landing takes the check its builder
queued on the same tree, and runs its own only where that check does not prove it. Each test is
red at 804eaf9 (alpha.165). Every repo, queue and runner is under the test's temp roots; the
fixture's `check:` appends a line to a file outside the tree, which counts the runs, and reads
its flags there, so a flag never moves the tree."""
import io
import json
import os
import stat
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, land, publish, resolver

from test_land4_ready import Crate, BRANCH

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugin" / "lib" / "agentik-session"
EIGHT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS",
         "MAKEFILES", "MAKELEVEL")
DROP = resolver.GATE_DEFAULTS["check_drop"][0]     # the one name check_drop held at first
# Brief 2, R2: the names that differ by session or by process, patterns among them.
DEFAULT_DROP = [DROP, "CLAUDE_CODE_*", "CLAUDE_SESSION_*", "CLAUDE_PID", "CLAUDE_EFFORT",
                "CLAUDECODE", "AI_AGENT", "*_SESSION_ID", "SSH_AUTH_SOCK", "OLDPWD", "SHLVL", "_"]
KEYS = {"id", "key", "started", "ended", "tree", "head", "main", "worktree", "links", "exit",
        "cut", "clean", "env"}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in EIGHT}
    p = subprocess.run(["git", *args], cwd=cwd, text=True, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


class Box:
    """`scratch` on main, `work` in its worktree; the check's flags and counts in `out`."""

    def __init__(self, tmp):
        self.tmp, self.out = tmp, tmp / "out"
        self.out.mkdir()
        self.root = resolver.state_dir(os.environ)
        self.path = tmp / "scratch"
        self.path.mkdir()
        o, g = self.out, gate.gate_dir(self.root)
        mk = ("check:\n\t@echo run >> %s/count\n"
              "\t@printf '%%s|%%s|%%s|%%s|%%s|%%s|%%s|%%s|%%s\\n' \"$$GIT_DIR\" \"$$GIT_WORK_TREE\" "
              "\"$$GIT_INDEX_FILE\" \"$$MAKEFLAGS\" \"$$MFLAGS\" \"$$GNUMAKEFLAGS\" \"$$MAKEFILES\" "
              "\"$$MAKELEVEL\" \"$$%s\" >> %s/env\n"
              "\t@if [ -e %s/snap ]; then cp %s/$$CLAUDE_SESSION_GATE_JOB/check.json "
              "%s/during.json; fi\n"
              "\t@if [ -e %s/move ]; then git commit -q --allow-empty -m moved; fi\n"
              "\t@if [ -e %s/slow ]; then sleep 20; fi\n"
              "\t@test ! -e %s/red\n"
              "hygiene:\n\t@test ! -e %s/hyg-red\n"
              "hygiene-range:\n\t@true\n") % (o, DROP, o, o, g, o, o, o, o, o)
        git(self.path, "init", "-q", "-b", "main")
        (self.path / "Makefile").write_text(mk)
        (self.path / ".gitignore").write_text(".claude/worktrees/\n.venv\n.venv-floor\n")
        git(self.path, "add", "Makefile", ".gitignore")
        git(self.path, "commit", "-qm", "base")
        self.tree = self.path / ".claude" / "worktrees" / "work"
        git(self.path, "worktree", "add", "-q", "-b", "work", str(self.tree), "main")
        self.sha = self.commit("new.txt", "new\n")
        self.message = tmp / "msg"
        self.message.write_text("Merge work: land the branch\n")

    def commit(self, rel, text, cwd=None):
        cwd = cwd or self.tree
        (cwd / rel).write_text(text)
        git(cwd, "add", rel)
        git(cwd, "commit", "-qm", "work: " + rel)
        return git(cwd, "rev-parse", "HEAD")

    def flag(self, name, on=True):
        p = self.out / name
        p.write_text("x\n") if on else p.unlink()

    def check(self, tree=None, *extra):
        rc, out, err = run("gate", "run", str(tree or self.tree), "--check", *extra)
        assert rc == 0, err
        return out.split()[1]

    def record(self, gid):
        return json.loads((gate.entry_dir(self.root, gid) / "check.json").read_text())

    def rewrite(self, gid, **kw):
        path = gate.entry_dir(self.root, gid) / "check.json"
        path.write_text(json.dumps({**self.record(gid), **kw}))

    def land(self, *flags, sha=None):
        """(exit, stdout, stderr and the job's log): the steps' notes are in the log."""
        argv = ["gate", "land", *flags, str(self.path), "work", sha or self.sha,
                str(self.message)]
        if "--dry-run" in flags:
            # os.environ, not the C environ, which readline gives LINES and COLUMNS
            p = subprocess.run([sys.executable, str(RUNNER), *argv], capture_output=True,
                               text=True, cwd=str(self.tmp), env=dict(os.environ))
            return p.returncode, p.stdout, p.stderr
        rc, out, err = run(*argv)
        words = err.split()
        if words[:1] == ["queued"]:
            log = gate.entry_dir(self.root, words[1]) / "log"
            err += log.read_text() if log.exists() else ""
        return rc, out, err

    def count(self):
        p = self.out / "count"
        return len(p.read_text().split()) if p.exists() else 0

    def main(self):
        return git(self.path, "rev-parse", "main")


@pytest.fixture
def box(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = t\n\temail = t@" + "example.invalid\n"
                   "[commit]\n\tgpgsign = false\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    for name in EIGHT + (DROP, land.FRESH):
        monkeypatch.delenv(name, raising=False)

    def serve_now(root, popen=None):
        if not gate.entries(root):
            return False
        gate.serve(root, gate.Fx(idle=0, poll=0.05))
        return True
    monkeypatch.setattr(gate, "spawn_serve", serve_now)
    return Box(tmp_path)


def ok(box, gid=None):
    return "land scratch: ok %s, main readied%s\n" % (box.sha, gid and ", check " + gid or "")


def as_check_job(root, gid, tree):
    """The result a `--check` job of `tree` leaves, for a record made outside a runner: a
    record is taken only under its own job's command (brief 2, R5)."""
    gate.result_path(root, gid).write_text(json.dumps(
        {"id": gid, "command": [*gate.self_argv(), *gate.CHECK_JOB, str(tree)], "exit": 0}))


def ran_own(err):
    return "land-step: check: runs its own (" in err and "land-step: check: kept " not in err


# 1. The one function.

def test_1_one_function_one_environment(box, monkeypatch):
    box.check()
    clean = (box.out / "env").read_text().splitlines()
    assert box.count() == 1 and len(clean) == 1
    for name in EIGHT:
        monkeypatch.setenv(name, "1" if name == "MAKELEVEL" else
                           "-e" if "FLAGS" in name else str(box.tmp / "nowhere"))
    monkeypatch.setenv(DROP, "base-x")
    gid = box.check()
    rc, out, err = box.land("--fresh")
    for name in EIGHT + (DROP,):
        monkeypatch.delenv(name)
    lines = (box.out / "env").read_text().splitlines()
    assert box.count() == 3 and lines == clean * 3, lines
    assert box.record(gid)["exit"] == 0
    assert (rc, out) == (0, ok(box)), err
    assert "land-step: check: make check in " in err
    # the landing's own run wrote its record through the same function
    (lid, rec), = [(n, r) for n, r in land.check_records(box.root)][:1]
    assert lid != gid and lid == err.split()[1] and rec["exit"] == 0


# 2. The record.

def test_2_the_record_at_its_start_and_its_end(box):
    box.flag("snap")
    gid = box.check()
    during = json.loads((box.out / "during.json").read_text())
    assert during["exit"] is None and during["ended"] is None and set(during) == KEYS
    rec = box.record(gid)
    assert set(rec) == KEYS
    assert rec["id"] == gid and rec["key"] == gate.repo_key(str(box.tree))
    assert rec["tree"] == git(box.tree, "rev-parse", "HEAD^{tree}")
    assert rec["head"] == box.sha and rec["main"] == box.main()
    assert rec["worktree"] == os.path.realpath(box.tree)
    assert rec["links"] == {".venv": False, ".venv-floor": False}
    assert (rec["exit"], rec["cut"], rec["clean"]) == (0, None, True)
    assert rec["started"] <= rec["ended"] and isinstance(rec["ended"], float)
    mode = os.stat(gate.entry_dir(box.root, gid) / "check.json").st_mode
    assert stat.S_IMODE(mode) == 0o600
    assert gate.command_kind(gate.entries(box.root) or
                             [*gate.self_argv(), *gate.CHECK_JOB, "x"]) == "make check"


def late_dirt(box, monkeypatch):
    """Queue with no runner, dirty the tree, then serve: the dirt came after the queue."""
    serve = gate.spawn_serve
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    gid = box.check()
    (box.tree / "late.txt").write_text("late\n")
    gate.serve(box.root, gate.Fx(idle=0, poll=0.05))
    monkeypatch.setattr(gate, "spawn_serve", serve)
    return gid


def test_2_dirt_after_the_queue_and_a_moved_head_are_not_clean(box, monkeypatch):
    gid = late_dirt(box, monkeypatch)
    assert (box.record(gid)["exit"], box.record(gid)["clean"]) == (0, False)
    (box.tree / "late.txt").unlink()
    box.flag("move")
    gid = box.check()
    rec = box.record(gid)
    assert rec["exit"] == 0 and rec["clean"] is False
    assert git(box.tree, "rev-parse", "HEAD") != rec["head"] == box.sha


# 3. The queue.

def test_3_the_queue_refuses_a_dirty_tree_and_a_command(box):
    (box.tree / "new.txt").write_text("edited\n")
    assert run("gate", "run", str(box.tree), "--check")[0] == 2
    git(box.tree, "checkout", "--", "new.txt")
    (box.tree / "stray.txt").write_text("stray\n")
    assert run("gate", "run", str(box.tree), "--check")[0] == 2
    (box.tree / "stray.txt").unlink()
    rc, _, err = run("gate", "run", str(box.tree), "--check", "--", "make", "check")
    assert rc == 2 and "no command after it" in err
    assert not gate.gate_dir(box.root).exists() or not gate.entries(box.root)
    assert not list(land.check_records(box.root))
    rc, _, err = run("gate", "run", "--check", "--in-job", str(box.tree))
    assert rc == 2 and gate.JOB_MARK in err
    gid = box.check()
    assert box.record(gid)["exit"] == 0 and box.count() == 1


# 4. The kept check.

def test_4_a_kept_check_is_taken_and_no_second_run(box):
    gid = box.check()
    rc, out, err = box.land()
    assert (rc, out) == (0, ok(box, gid)), err
    assert box.count() == 1
    assert "land-step: check: kept %s," % gid in err
    # the log's one line that opens `land scratch: ` is the verdict, never the note
    assert [x for x in err.splitlines() if x.startswith("land scratch: ")] == [out.strip()]
    assert git(box.path, "rev-parse", "main^2") == box.sha


def test_4_a_red_line_after_a_kept_record_ends_the_same_way(box):
    gid = box.check()
    box.flag("hyg-red")
    rc, out, err = box.land()
    assert (rc, out) == (2, "land scratch: red hygiene exit 2, check %s\n" % gid), err
    assert box.count() == 1


def test_4_and_9_the_readied_form_takes_a_check_of_the_readied_head(tmp_path):
    c = Crate(tmp_path)
    sha = c.work({"f": "x\n"})
    c.on_main({"g": "y\n"})
    root = resolver.state_dir(c.env)
    a, b, d = "20261122-000000-1", "20261122-000000-2", "20261122-000000-3"
    for gid in (a, b, d):
        gate.entry_dir(root, gid).mkdir(parents=True)
    rc, out, _ = c.land(sha, env={gate.JOB_MARK: a, "CHECK_EXIT": "2"})
    head = c.head()
    assert rc == 2 and head != sha and out.endswith(", as %s\n" % head)
    p = subprocess.run([sys.executable, str(RUNNER), "gate", "run", "--check", "--in-job",
                        str(c.tree)], env={**c.env, gate.JOB_MARK: b}, capture_output=True,
                       text=True, cwd=str(tmp_path))
    assert p.returncode == 0, p.stderr
    rec = json.loads((gate.entry_dir(root, b) / "check.json").read_text())
    assert (rec["head"], rec["exit"], rec["clean"]) == (head, 0, True)
    as_check_job(root, b, c.tree)
    before = c.ran().count("check")
    rc, out, err = c.land(sha, env={gate.JOB_MARK: d})
    version = json.loads(c.show(head, "plugin/.claude-plugin/plugin.json"))["version"]
    assert (rc, out) == (0, "land crate: ok %s, main readied, as %s, plugin %s, check %s\n"
                         % (sha, head, version, b)), err
    assert c.ran().count("check") == before
    assert not (gate.entry_dir(root, d) / "check.json").exists()


# 5. Each condition of item 22.

def test_5_a_red_record(box):
    box.flag("red")
    box.check()
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and ran_own(err) and " exit 2)" in err


def test_5_a_record_with_no_exit(box):
    gid = box.check()
    box.rewrite(gid, exit=None, ended=None, clean=None)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "%s has no exit" % gid in err


def test_5_a_cut_record(box):
    # brief 3, R3: the start record is written before the dirt is read; a first check warms
    # the job's bytecode under the test's fresh HOME, and the wall leaves a loaded machine
    # room for the start, still well short of the check's 20 s
    box.check()
    box.flag("slow")
    gid = box.check(None, "--wall", "8")
    rec = box.record(gid)
    assert (rec["exit"], rec["cut"]) == (124, gate.CUT_WALL)
    box.flag("slow", False)
    rc, out, err = box.land()
    assert (rc, out) == (0, ok(box)) and ran_own(err)


def test_5_a_record_not_clean(box, monkeypatch):
    late_dirt(box, monkeypatch)
    (box.tree / "late.txt").unlink()
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "is not clean" in err


def test_5_a_sibling_worktrees_record(box):
    twin = box.path / ".claude" / "worktrees" / "twin"
    git(box.path, "worktree", "add", "-q", "-b", "twin", str(twin), box.sha)
    box.check(twin)
    # brief 2, R5: a check job of another worktree is no job of this one: its record is skipped
    assert land.kept_check(box.root, str(box.path), str(box.tree), "work", box.sha, box.sha,
                           box.main()) == (None, "no record of this tree")
    gid = box.check()
    box.rewrite(gid, worktree=os.path.realpath(twin))
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3) and "ran in another worktree" in err


def test_5_main_moved_under_the_same_head_and_tree(box):
    """design/30's block 1: main gains a commit the branch holds; same head, same tree."""
    first = box.sha
    box.sha = box.commit("more.txt", "more\n")
    gid = box.check()
    git(box.path, "merge", "-q", "--ff-only", first)
    box.flag("red")
    rc, out, err = box.land()
    assert (rc, out) == (2, "land scratch: red check exit 2\n"), err
    assert "%s ran with main at" % gid in err and box.count() == 2


def test_5_links_changed(box):
    box.check()
    os.symlink(str(box.tmp), str(box.tree / ".venv"))
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "links differ now" in err


def test_5_past_the_age(box):
    gid = box.check()
    box.rewrite(gid, ended=time.time() - 7 * 3600)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "gate.check_age" in err


def test_5_a_newer_red_of_todays_form(box):
    box.check()
    box.flag("red")
    rc, qout, _ = run("gate", "run", str(box.tree), "--", "/bin/sh", "-c",
                      "make check > %s/log 2>&1" % box.out)
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3)
    assert "%s is red after" % qout.split()[1] in err


def test_5_a_newer_red_land_script_naming_the_branch(box):
    box.check()
    script = box.out / "land.sh"
    script.write_text("exit 1\n")
    rc, qout, _ = run("gate", "run", str(box.path), "--", "/bin/sh", str(script),
                      str(box.path), "work", box.sha, str(box.message))
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2)
    assert "%s is red after" % qout.split()[1] in err


def test_5_the_landings_own_red_voids_the_green(box):
    """design/30's block 2: a landing's red check is the newest record for its tree."""
    box.check()
    box.flag("red")
    assert box.land("--fresh")[:2] == (2, "land scratch: red check exit 2\n")
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3) and " exit 2)" in err


# 6. Same tree, head past the record's.

def test_6_a_commit_and_its_revert_run_the_landings_check(box):
    gid = box.check()
    box.commit("new.txt", "changed\n")
    git(box.tree, "revert", "--no-edit", "HEAD")
    box.sha = git(box.tree, "rev-parse", "HEAD")
    assert git(box.tree, "rev-parse", "HEAD^{tree}") == box.record(gid)["tree"]
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "not the landing's head" in err


def test_6_an_empty_commit_of_the_landings_own_keeps_the_record(box):
    gid = box.check()
    given = box.sha
    git(box.tree, "commit", "-q", "--allow-empty", "-m", "work: plugin\n\nGate-Land: " + given)
    head = git(box.tree, "rev-parse", "HEAD")
    assert land.kept_check(box.root, str(box.path), str(box.tree), "work", given, head,
                           box.main()) == (gid, "")
    git(box.tree, "commit", "-q", "--allow-empty", "-m", "by hand")
    other = git(box.tree, "rev-parse", "HEAD")
    assert land.kept_check(box.root, str(box.path), str(box.tree), "work", given, other,
                           box.main())[0] is None


# 7. --fresh and --dry-run.

def test_7_fresh_runs_its_own_check(box):
    box.check()
    rc, out, err = box.land("--fresh")
    assert (rc, out, box.count()) == (0, ok(box), 2) and "runs its own (--fresh)" in err


def test_7_the_dry_run_says_which_and_writes_nothing(box):
    rc, out, _ = box.land("--dry-run")
    assert out.splitlines()[-2] == "check: would run its own (no record of this tree)"
    gid = box.check()
    names = sorted(os.listdir(gate.gate_dir(box.root)))
    rc, out, _ = box.land("--dry-run")
    assert rc == 0 and out.splitlines()[-2] == "check: would take " + gid
    rc, out, _ = box.land("--dry-run", "--fresh")
    assert out.splitlines()[-2] == "check: would run its own (--fresh)"
    assert sorted(os.listdir(gate.gate_dir(box.root))) == names and box.count() == 1


def test_7_the_dry_run_of_a_stamp_repo(tmp_path):
    c = Crate(tmp_path)
    c.work({"f": "x\n"})
    root = resolver.state_dir(c.env)
    gid = "20261122-000000-5"
    gate.entry_dir(root, gid).mkdir(parents=True)
    subprocess.run([sys.executable, str(RUNNER), "gate", "run", "--check", "--in-job",
                    str(c.tree)], env={**c.env, gate.JOB_MARK: gid}, check=True,
                   capture_output=True, cwd=str(tmp_path))
    as_check_job(root, gid, c.tree)
    rc, out, err = c.land(c.head(), extra=["--dry-run"], in_job=False,
                          env={gate.JOB_MARK: ""})
    assert rc == 0 and out.splitlines()[-2] == (
        "check: would take %s if the stamp writes nothing" % gid), err
    c.on_main({"g": "y\n"})
    rc, out, _ = c.land(c.head(), extra=["--dry-run"], in_job=False, env={gate.JOB_MARK: ""})
    assert out.splitlines()[-2] == "check: would run its own (main merged)"


@pytest.mark.parametrize("fresh", [False, True])
def test_7_the_landings_command_keeps_its_form(box, monkeypatch, fresh):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.setattr(gate, "wait", lambda root, gid, **kw: (1, None))
    box.land(*(["--fresh"] if fresh else []))
    (e,) = gate.entries(box.root)
    own = [*gate.self_argv(), *gate.LAND_JOB]
    assert e["command"] == own + [str(box.path), "work", box.sha, str(box.message)]
    assert gate.land_branch(e["command"]) == "work"
    assert (e["env"].get(land.FRESH) == "1") is fresh


# 8. publish unchanged.

def test_8_a_kept_landing_proves_main_and_a_check_job_proves_no_push(box):
    gid = box.check()
    assert box.land()[:2] == (0, ok(box, gid))
    head = box.main()
    why = publish.proof(box.root, str(box.path), "scratch", head)
    assert why and why.startswith("the landing ")
    (lid, doc), = [(n, d) for n, d in publish.results(box.root)
                   if gate.land_branch(d.get("command"))]
    fake = "20991231-235959-1"
    gate.entry_dir(box.root, fake).mkdir()
    log = gate.entry_dir(box.root, fake) / "log"
    log.write_text("land scratch: ok %s, main readied, as %s, plugin 1.0.0, check %s\n"
                   % (box.sha, box.sha, gid))
    gate.result_path(box.root, fake).write_text(json.dumps({**doc, "id": fake, "log": str(log)}))
    assert publish.landing_proves({**doc, "id": fake, "log": str(log)}, str(box.path),
                                  "scratch", head, git(box.path, "rev-list", "--parents", "-n",
                                                       "1", head).split()[1:])
    for n in (fake, lid):
        gate.result_path(box.root, n).unlink()
    cid = box.check(box.path)
    assert publish.check_proves(dict(publish.results(box.root))[cid], str(box.path),
                                head) is False
    assert publish.proof(box.root, str(box.path), "scratch", head) is None


# 9. A red hygiene after its own green check.

def test_9_a_red_hygiene_leaves_its_green_newest(box):
    box.flag("hyg-red")
    rc, out, _ = box.land()
    assert (rc, out, box.count()) == (2, "land scratch: red hygiene exit 2\n", 1)
    (gid, rec), = land.check_records(box.root)
    assert rec["exit"] == 0
    box.flag("hyg-red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box, gid), 1), err


# R9: the keys.

def test_r9_the_three_keys_and_a_mistyped_one(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    cfg = resolver.gate_config(os.environ)
    assert (cfg["check_drop"], cfg["check_links"], cfg["check_age"]) == (
        DEFAULT_DROP, [".venv", ".venv-floor"], 21600)
    f = tmp_path / ".claude" / "agentik" / "profiles.yaml"
    f.parent.mkdir(parents=True)
    f.write_text("gate:\n  check_drop: [A, B]\n  check_links: 3\n  check_age: 60\n")
    said = []
    cfg = resolver.gate_config(os.environ, said.append)
    assert (cfg["check_drop"], cfg["check_links"], cfg["check_age"]) == (
        ["A", "B"], [".venv", ".venv-floor"], 60)
    assert said == ["gate: check_links is no list of names; the default stands"]


# ---- brief 2, the fix of review 1 ---------------------------------------------------------

SEEN = ("check:\n\t@echo run >> {o}/count\n\t@env > {o}/seen.$$CLAUDE_SESSION_GATE_JOB\n"
        "\t@{body}\nhygiene:\n\t@true\nhygiene-range:\n\t@true\n")


def remake(box, body="true", extra=None):
    """Commit a Makefile whose check dumps its environment by job id (and files); the box's
    sha follows."""
    (box.tree / "Makefile").write_text(SEEN.format(o=box.out, body=body))
    for rel, text in (extra or {}).items():
        (box.tree / rel).write_text(text)
    git(box.tree, "add", "Makefile", *(extra or {}))
    git(box.tree, "commit", "-qm", "work: makefile")
    box.sha = git(box.tree, "rev-parse", "HEAD")


def seen(box, gid):
    """The names (and their values) the check of job `gid` saw."""
    text = (box.out / ("seen." + gid)).read_text()
    return dict(ln.split("=", 1) for ln in text.splitlines() if "=" in ln)


def digest(value):
    import hashlib
    return hashlib.sha256(value.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def concrete(pattern):
    return pattern.replace("*", "NW5X")


# R2 (F1): what reaches the check is recorded and compared.

@pytest.mark.parametrize("case", ["set at the queue", "set at the landing", "changed"])
def test_b2_r2_a_name_that_differs_runs_the_landings_own(box, monkeypatch, case):
    remake(box)
    at_queue, at_land = {"set at the queue": ("1", None), "set at the landing": (None, "1"),
                         "changed": ("1", "2")}[case]
    monkeypatch.delenv("NW5_KNOB", raising=False)
    if at_queue:
        monkeypatch.setenv("NW5_KNOB", at_queue)
    gid = box.check()
    assert box.record(gid)["exit"] == 0
    monkeypatch.setenv("NW5_KNOB", at_land) if at_land else monkeypatch.delenv("NW5_KNOB")
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2), err
    assert "land-step: check: runs its own (environment: NW5_KNOB differs)" in err


@pytest.mark.parametrize("pattern", DEFAULT_DROP, ids=lambda p: p.replace("*", "x") or "x")
def test_b2_r2_a_name_the_default_drops_takes_the_record(box, monkeypatch, pattern):
    remake(box)
    name = concrete(pattern)
    monkeypatch.setenv(name, "one")
    gid = box.check()
    # make and sh set some of these names afresh (SHLVL, _): the value is never ours
    assert seen(box, gid).get(name) != "one" and name not in box.record(gid)["env"]
    monkeypatch.setenv(name, "two")
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box, gid), 1), err


def test_b2_r2_the_landings_own_run_sees_none_of_the_default(box, monkeypatch):
    remake(box)
    for pattern in DEFAULT_DROP:
        monkeypatch.setenv(concrete(pattern), "nw5-ours")
    rc, out, err = box.land("--fresh")
    assert (rc, out, box.count()) == (0, ok(box), 1), err
    (lid, rec), = land.check_records(box.root)
    env = seen(box, lid)
    assert [p for p in DEFAULT_DROP if env.get(concrete(p)) == "nw5-ours"] == []
    assert not {concrete(p) for p in DEFAULT_DROP} & set(rec["env"])
    # the job's mark is kept and never compared; PWD is the folder the check runs in
    assert env[gate.JOB_MARK] == lid and gate.JOB_MARK not in rec["env"]
    assert env["PWD"] == os.path.realpath(box.tree) and rec["env"]["PWD"] == digest(env["PWD"])


def test_b2_r2_the_record_holds_no_value(box, monkeypatch):
    remake(box)
    monkeypatch.setenv("NW5_KNOB", "a-value-nw5-only")
    gid = box.check()
    text = (gate.entry_dir(box.root, gid) / "check.json").read_text()
    assert "a-value-nw5-only" not in text
    env = box.record(gid)["env"]
    assert env["NW5_KNOB"] == digest("a-value-nw5-only")
    assert gate.JOB_MARK not in env and set(env) <= set(seen(box, gid))
    assert all(isinstance(v, str) and len(v) == 16 for v in env.values())


def test_b2_r2_a_user_pattern_is_honoured_and_a_mistyped_one_is_the_default(box, monkeypatch):
    remake(box)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    f = Path(os.environ["HOME"]) / ".claude" / "agentik" / "profiles.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("gate:\n  check_drop: [NW5_*]\n")
    monkeypatch.setenv("NW5_KNOB", "one")
    gid = box.check()
    assert "NW5_KNOB" not in seen(box, gid)
    monkeypatch.setenv("NW5_KNOB", "two")
    rc, out, err = box.land("--dry-run")
    assert "check: would take " + gid in out.splitlines(), out
    f.write_text("gate:\n  check_drop: NW5_*\n")
    said = []
    cfg = resolver.gate_config(os.environ, said.append)
    assert cfg["check_drop"] == DEFAULT_DROP
    assert said == ["gate: check_drop is no list of names; the default stands"]


# R3 (F2): an index entry status does not show is no clean tree.

@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_b2_r3_a_marked_index_entry_is_refused_at_the_queue(box, flag):
    remake(box, "grep -q green state.txt", {"state.txt": "red\n"})
    git(box.tree, "update-index", flag, "state.txt")
    (box.tree / "state.txt").write_text("green\n")
    rc, out, err = run("gate", "run", str(box.tree), "--check")
    assert rc == 2 and len(err.strip().splitlines()) == 1 and "state.txt" in err, err
    assert not gate.gate_dir(box.root).exists() or not gate.entries(box.root)
    assert not list(land.check_records(box.root))


@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_b2_r3_a_mark_set_after_the_queue_is_not_clean(box, monkeypatch, flag):
    remake(box, "grep -q red state.txt", {"state.txt": "red\n"})
    serve = gate.spawn_serve
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    gid = box.check()
    git(box.tree, "update-index", flag, "state.txt")
    gate.serve(box.root, gate.Fx(idle=0, poll=0.05))
    rec = box.record(gid)
    assert (rec["exit"], rec["clean"]) == (0, False)
    git(box.tree, "update-index", flag.replace("--", "--no-"), "state.txt")
    monkeypatch.setattr(gate, "spawn_serve", serve)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2) and "is not clean" in err, err


# R4 (F3): a newer red of the check job's own form voids, whatever its record.

@pytest.mark.parametrize("record", ["torn", "absent"])
def test_b2_r4_a_newer_red_check_job_voids_whatever_its_record(box, record):
    g1 = box.check()
    box.flag("red")
    r2 = box.check()
    assert box.record(r2)["exit"] == 2
    path = gate.entry_dir(box.root, r2) / "check.json"
    path.write_text('{"id": "' + r2 + '", "tre') if record == "torn" else path.unlink()
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3), err
    assert "%s is red after %s" % (r2, g1) in err


# R5 (F4): a record is taken only from the check's own job or a landing of the branch.

def test_b2_r5_a_record_of_another_jobs_command_is_skipped(box):
    rc, out, err = run("gate", "run", str(box.tree), "--", "/bin/sh", "-c",
                       '"$0" "$1" gate run "$2" --check --in-job', sys.executable, str(RUNNER),
                       str(box.tree))
    gid = out.split()[1]
    assert box.record(gid)["exit"] == 0 and box.count() == 1
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2), err
    assert "runs its own (no record of this tree)" in err


# R6 (F5): check.json is read only from a regular file, and never blocks.

def test_b2_r6_a_fifo_record_never_holds_the_landing(box):
    g1 = box.check()
    fake = "%s-%d" % (g1[:15], int(g1[16:]) + 40)
    d = gate.entry_dir(box.root, fake)
    d.mkdir()
    os.mkfifo(d / "check.json")
    t = time.time()
    rc, out, err = box.land("--wall", "20")      # a red is a cut, never a hang
    assert (rc, out, box.count()) == (0, ok(box, g1), 1), err
    assert time.time() - t < 15
    assert [n for n, _ in land.check_records(box.root)] == [g1]


# R7 (F6): the no-stamp dry run reads the sha given.

def test_b2_r7_the_no_stamp_dry_run_reads_the_sha(box):
    box.check()
    base = box.main()
    rc, out, err = box.land("--dry-run", sha=base)
    assert "check: would run its own (sha)" in out.splitlines(), out
    assert "would take" not in out
    assert box.land(sha=base)[:2] == (1, "land scratch: red sha exit 1\n")


# ---- brief 3, the fix of review 2 ---------------------------------------------------------

# R1 (F2): the job's form picks the record taken; any newer red of this worktree voids it.

@pytest.mark.parametrize("lost", ["missing", "torn"])
def test_b3_r1_a_newer_red_check_whose_result_is_lost_voids(box, lost):
    g1 = box.check()
    box.flag("red")
    r2 = box.check()
    assert box.record(r2)["exit"] == 2
    res = gate.result_path(box.root, r2)
    res.unlink() if lost == "missing" else res.write_text('{"id": "' + r2 + '", "comm')
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3), err
    assert "%s is red after %s" % (r2, g1) in err


@pytest.mark.parametrize("record", ["kept", "absent"])
def test_b3_r1_a_newer_red_of_a_wrapper_job_voids(box, record):
    g1 = box.check()
    box.flag("red")
    rc, out, err = run("gate", "run", str(box.tree), "--", "/bin/sh", "-c",
                       '"$0" "$1" gate run "$2" --check --in-job', sys.executable, str(RUNNER),
                       str(box.tree))
    r2 = out.split()[1]
    assert box.record(r2)["exit"] == 2 and box.count() == 2
    if record == "absent":
        (gate.entry_dir(box.root, r2) / "check.json").unlink()
    box.flag("red", False)
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3), err
    assert "%s is red after %s" % (r2, g1) in err


def test_b3_r1_a_newer_record_with_no_exit_voids(box):
    g1 = box.check()
    r2 = box.check()
    box.rewrite(r2, exit=None, ended=None, clean=None)
    gate.result_path(box.root, r2).unlink()
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 3), err
    assert "%s is red after %s" % (r2, g1) in err


# R2 (F1): an fsmonitor that reports no change hides nothing from the dirt's reads.

def fsmonitor_valid(box, text):
    """A stand-in fsmonitor hook that reports no change, then an edit under its valid bit."""
    hook = box.tmp / "fsmonitor-hook"
    hook.write_text('#!/bin/sh\nprintf "tok\\0"\n')
    hook.chmod(0o755)
    git(box.tree, "config", "core.fsmonitor", str(hook))
    git(box.tree, "status", "--porcelain")
    (box.tree / "state.txt").write_text(text)
    git(box.tree, "update-index", "--fsmonitor-valid", "state.txt")
    assert git(box.tree, "status", "--porcelain") == ""      # git's own read is fooled


def test_b3_r2_an_fsmonitor_valid_edit_is_refused_at_the_queue(box):
    remake(box, "grep -q green state.txt", {"state.txt": "red\n"})
    fsmonitor_valid(box, "green\n")
    rc, out, err = run("gate", "run", str(box.tree), "--check")
    assert rc == 2 and "is not clean" in err and "state.txt" in err, err
    assert not gate.gate_dir(box.root).exists() or not gate.entries(box.root)
    assert not list(land.check_records(box.root))


def test_b3_r2_an_fsmonitor_valid_edit_after_the_queue_is_not_clean(box, monkeypatch):
    remake(box, "grep -q green state.txt", {"state.txt": "red\n"})
    serve = gate.spawn_serve
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    gid = box.check()
    fsmonitor_valid(box, "green\n")
    gate.serve(box.root, gate.Fx(idle=0, poll=0.05))
    rec = box.record(gid)
    assert (rec["exit"], rec["clean"]) == (0, False)
    (box.tree / "state.txt").write_text("red\n")
    monkeypatch.setattr(gate, "spawn_serve", serve)
    rc, out, err = box.land()
    assert (rc, out) == (2, "land scratch: red check exit 2\n"), err
    assert box.count() == 2 and "%s is not clean" % gid in err


# R4 (F4): the check job's form is the whole command, this plugin's runner first.

def test_b3_r4_the_check_jobs_form_is_the_whole_command(box):
    wt = str(box.tree)
    head = gate.self_argv()
    assert gate.check_worktree([*head, *gate.CHECK_JOB, wt]) == wt
    assert gate.check_worktree(["/bin/sh", "-c", "x", *gate.CHECK_JOB, wt]) is None
    assert gate.check_worktree([*head[:-1], "/x/other-tool", *gate.CHECK_JOB, wt]) is None
    assert gate.check_worktree(["x", *head, *gate.CHECK_JOB, wt]) is None
    box.flag("red")
    rc, out, err = run("gate", "run", wt, "--", "/bin/sh", "-c",
                       'rm -f %s/red; "$0" "$1" gate run "$2" --check --in-job; touch %s/red'
                       % (box.out, box.out), sys.executable, str(RUNNER), wt,
                       *gate.CHECK_JOB, wt)
    gid = out.split()[1]
    assert box.record(gid)["exit"] == 0 and box.count() == 1
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (2, "land scratch: red check exit 2\n", 2), err
    assert "runs its own (no record of this tree)" in err


# R5 (F5): a symlink named check.json is skipped, whatever it points to.

def test_b3_r5_a_symlinked_record_is_skipped(box):
    g1 = box.check()
    path = gate.entry_dir(box.root, g1) / "check.json"
    kept = box.tmp / "kept.json"
    kept.write_text(path.read_text())
    path.unlink()
    path.symlink_to(kept)
    assert not list(land.check_records(box.root))
    rc, out, err = box.land()
    assert (rc, out, box.count()) == (0, ok(box), 2), err
    assert ran_own(err)
