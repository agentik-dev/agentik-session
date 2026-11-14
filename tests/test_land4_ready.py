"""Packet land4-ready: `gate land` readies a reviewed branch that main has passed, where the
repo's Makefile has `stamp`: it merges main where every conflict is a derived line, stamps, checks
the new head once and lands it; `--dry-run` says what it would do. Each case is a made-up repo
`crate` in a temp folder (its own HOME, state and git identity), its branch `p1-crate` in its
worktree, run as `gate land --in-job` with a job's mark and nothing queued. The stamp is a stub
that writes the version and Status lines, save two cases that run the repo's own scripts/stamp."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import gate, resolver
from test_land3_stamp import (NICE_HEAD, OVERFLOW_TEXT, manifest_text, pear_tests, readme_text,
                              source_text)

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "plugin" / "lib" / "agentik-session"
STAMP = ROOT / "scripts" / "stamp"
MANIFEST = "plugin/.claude-plugin/plugin.json"
NICE = "NICE_TO_HAVE.md"
OVERFLOW = "history/NICE-overflow.md"
SIDECAR = "design/readme/rendered.sha256"
SOURCE = "design/readme/source.md"
BRANCH = "p1-crate"

STUB = r"""set -e
[ -n "${STAMP_SAY:-}" ] && echo "$STAMP_SAY" >&2
[ -n "${STAMP_EXIT:-}" ] && exit "$STAMP_EXIT"
f=plugin/.claude-plugin/plugin.json
v=$(git show "$1:$f" | sed -n 's/^  "version": "\(.*\)",$/\1/p')
cur=$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$f")
n=${v##*.}; c=${cur##*.}
if [ "$c" -le "$n" ]; then new="${v%.*}.$((n+1))"; else new=$cur; fi
if [ "$new" != "$cur" ]; then
  sed "s/^  \"version\": \".*\",\$/  \"version\": \"$new\",/" "$f" > "$f.t"; mv "$f.t" "$f"
fi
for r in README.md design/readme/source.md; do
  sed "s/^Status: version .*/Status: version $new./" "$r" > "$r.t"
  if cmp -s "$r" "$r.t"; then rm "$r.t"; else mv "$r.t" "$r"; fi
done
if [ -n "${STAMP_EXTRA:-}" ]; then echo extra >> shared.txt; fi
exit 0
"""
CHECK = "check:\n\t@echo check >> \"$$LAND_ORDER\"\n\t@exit $${CHECK_EXIT:-0}\n"
STAMPS = ("STAMP_BASE ?= main\nstamp:\n\t@echo stamp >> \"$$LAND_ORDER\"\n"
          "\t@sh tools/stamp-stub \"$(STAMP_BASE)\"\n")
PVC = "#!/bin/sh\necho version >> \"$LAND_ORDER\"\nexit ${PVC_EXIT:-0}\n"


def row(n, text="a row"):
    return "| n%d | S4 | `crate` | %s | e | 2026-01-01, a builder |\n" % (n, text)


def doc(version):
    return "# Crate\n\nIntro.\n\nOne.\n\nTwo.\n\nStatus: version %s.\n\nThe tail.\n" % version


def manifest(version):
    return '{\n  "name": "crate",\n  "version": "%s",\n  "description": "made up"\n}\n' % version


class Crate:
    """`crate` on main and `p1-crate` in its worktree, cut from main's first commit."""

    def __init__(self, tmp, stamp=True, files=None):
        self.tmp = tmp
        cfg = tmp / "gitconfig"
        cfg.write_text("[user]\n\tname = t\n\temail = t@" + "example.invalid\n"
                       "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        self.order = tmp / "order"
        self.env = {**os.environ, "HOME": str(tmp), "XDG_STATE_HOME": str(tmp / "state"),
                    "XDG_CONFIG_HOME": str(tmp / "config"), "GIT_CONFIG_GLOBAL": str(cfg),
                    "GIT_CONFIG_NOSYSTEM": "1", gate.JOB_MARK: "20261110-000000-1",
                    "LAND_ORDER": str(self.order), "TMPDIR": str(tmp)}
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "CLAUDE_CODE_SESSION_ID",
                     "STAMP_EXIT", "STAMP_EXTRA", "STAMP_SAY", "CHECK_EXIT", "PVC_EXIT"):
            self.env.pop(name, None)
        self.repo = tmp / "crate"
        self.repo.mkdir()
        self.git(self.repo, "init", "-q")
        base = files if files is not None else {
            ".gitignore": ".claude/worktrees/\n",
            "Makefile": CHECK + (STAMPS if stamp else ""),
            "tools/stamp-stub": STUB,
            MANIFEST: manifest("1.0.0-alpha.1"),
            "README.md": doc("1.0.0-alpha.1"),
            SOURCE: doc("1.0.0-alpha.1"),
            SIDECAR: "aaaa  design/readme/source.md\naaaa  README.md\n",
            NICE: NICE_HEAD + "".join(row(n) for n in range(2, 8)),
            OVERFLOW: OVERFLOW_TEXT,
            "shared.txt": "base\n",
        }
        self.put(self.repo, base)
        self.commit(self.repo, "base")
        self.tree = self.repo / ".claude" / "worktrees" / BRANCH
        self.git(self.repo, "worktree", "add", "-q", "-b", BRANCH, str(self.tree), "main")
        self.msg = tmp / "msg"
        self.msg.write_text("Merge p1-crate: a made-up landing\n\nOne line.\n")

    def git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def put(self, cwd, files):
        for rel, text in files.items():
            path = Path(cwd) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                path.unlink()
            else:
                path.write_text(text)

    def commit(self, cwd, message, files=None):
        if files:
            self.put(cwd, files)
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-qm", message)
        return self.git(cwd, "rev-parse", "HEAD")

    def work(self, files, message="the work"):
        return self.commit(self.tree, message, files)

    def on_main(self, files, message="main moves"):
        return self.commit(self.repo, message, files)

    def edit(self, cwd, rel, old, new):
        path = Path(cwd) / rel
        text = path.read_text()
        assert old in text, (rel, old)
        return {rel: text.replace(old, new)}

    def land(self, sha, env=None, extra=(), args=None, in_job=True):
        argv = [sys.executable, str(RUNNER), "gate", "land", *(["--in-job"] if in_job else []),
                *extra, *(args if args is not None else [str(self.repo), BRANCH, sha,
                                                         str(self.msg)])]
        p = subprocess.run(argv, env={**self.env, **(env or {})}, capture_output=True, text=True,
                           timeout=600, cwd=str(self.tmp))
        return p.returncode, p.stdout, p.stderr

    def ran(self):
        return self.order.read_text().split() if self.order.exists() else []

    def head(self):
        return self.git(self.repo, "rev-parse", "refs/heads/" + BRANCH)

    def main(self):
        return self.git(self.repo, "rev-parse", "main")

    def show(self, rev, rel):
        return self.git(self.repo, "show", "%s:%s" % (rev, rel))

    def clean(self):
        return self.git(self.tree, "status", "--porcelain", "--untracked-files=all")

    def body(self, rev):
        return self.git(self.repo, "log", "-1", "--format=%B", rev)


@pytest.fixture
def c(tmp_path):
    return Crate(tmp_path)


def ok(sha, new, version):
    return "land crate: ok %s, main readied, as %s, plugin %s\n" % (sha, new, version)


# 1. No stamp target: the pin's lines, byte for byte.

def test_land4_1_no_stamp_target_a_branch_behind_main_is_red_sha(tmp_path):
    c = Crate(tmp_path, stamp=False)
    sha = c.work({"f": "x\n"})
    before = c.on_main({"g": "y\n"})
    rc, out, err = c.land(sha)
    assert (rc, out) == (1, "land crate: red sha exit 1\n"), err
    assert "main holds what %s does not" % sha in err
    assert "merge main into p1-crate, land its new head" in err
    assert (c.main(), c.head(), c.clean(), c.ran()) == (before, sha, "", [])


# 2. Behind main, no conflict: merge, stamp, one check, land.

def test_land4_2_behind_main_no_conflict_is_readied_and_landed(c):
    sha = c.work({"f": "x\n"})
    main = c.on_main({"g": "y\n"})
    rc, out, err = c.land(sha)
    new = c.git(c.repo, "rev-parse", "main^2")
    assert (rc, out) == (0, ok(sha, new, "1.0.0-alpha.2")), err
    assert c.ran() == ["stamp", "check"]
    merge, stamp = new + "^", new
    assert c.git(c.repo, "log", "-1", "--format=%s", merge) == "p1-crate: merge main"
    assert c.git(c.repo, "rev-parse", merge + "^2") == main
    assert c.git(c.repo, "rev-parse", merge + "^1") == sha
    assert c.git(c.repo, "log", "-1", "--format=%s", stamp) == "p1-crate: plugin 1.0.0-alpha.2"
    for rev in (merge, stamp):
        assert c.body(rev).splitlines()[-1] == "Gate-Land: " + sha
    assert c.git(c.repo, "diff", "--name-only", merge, stamp).split() == sorted(
        [MANIFEST, "README.md", SOURCE])
    assert '"version": "1.0.0-alpha.2"' in c.show("main", MANIFEST)
    assert c.git(c.repo, "branch", "--list", BRANCH) == ""


def test_land4_2_a_stamps_output_is_never_an_unrun(c):
    """gl1's stop line is read from the check's own start: a stamp that writes one is no unrun."""
    sha = c.work({"f": "x\n"})
    c.on_main({"g": "y\n"})
    log = gate.entry_dir(resolver.state_dir(c.env), c.env[gate.JOB_MARK]) / "log"
    log.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    env = {**c.env, "STAMP_SAY": "bounded: stop: load", "CHECK_EXIT": "2"}
    try:
        p = subprocess.Popen([sys.executable, str(RUNNER), "gate", "land", "--in-job",
                              str(c.repo), BRANCH, sha, str(c.msg)], env=env,
                             stdin=subprocess.DEVNULL, stdout=fd, stderr=subprocess.STDOUT)
    finally:
        os.close(fd)
    assert p.wait(timeout=300) == 2
    line = [x for x in log.read_text().splitlines() if x.startswith("land crate: ")][-1]
    assert line == "land crate: red check exit 2, as %s" % c.head()


# 3. Derived conflicts together are readied; one more line is red behind.

def derived_conflicts(c):
    sha = c.work({MANIFEST: manifest("1.0.0-alpha.2"), "README.md": doc("1.0.0-alpha.2"),
                  SOURCE: doc("1.0.0-alpha.2"),
                  SIDECAR: "bbbb  design/readme/source.md\nbbbb  README.md\n",
                  NICE: NICE_HEAD + "".join(row(n) for n in range(2, 8)) + row(8, "the branch's"),
                  "f": "x\n"})
    c.on_main({MANIFEST: manifest("1.0.0-alpha.3"), "README.md": doc("1.0.0-alpha.3"),
               SOURCE: doc("1.0.0-alpha.3"),
               SIDECAR: "cccc  design/readme/source.md\ncccc  README.md\n",
               NICE: NICE_HEAD + "".join(row(n) for n in range(2, 8)) + row(9, "main's")})
    return sha


def test_land4_3_derived_conflicts_are_readied_and_landed(c):
    sha = derived_conflicts(c)
    rc, out, err = c.land(sha)
    new = c.git(c.repo, "rev-parse", "main^2")
    assert (rc, out) == (0, ok(sha, new, "1.0.0-alpha.4")), err
    assert c.show("main", SIDECAR) == "cccc  design/readme/source.md\ncccc  README.md"
    nice = c.show("main", NICE)
    assert nice.endswith(row(9, "main's") + row(8, "the branch's").rstrip("\n"))
    assert "Status: version 1.0.0-alpha.4." in c.show("main", "README.md")


@pytest.mark.parametrize("where", ["readme", "outside"])
def test_land4_3_another_conflicted_line_is_red_behind(c, where):
    derived_conflicts(c)
    if where == "readme":
        sha = c.work(c.edit(c.tree, "README.md", "Intro.", "Intro, the branch's."))
        c.on_main(c.edit(c.repo, "README.md", "Intro.", "Intro, main's."))
        path = "README.md"
    else:
        sha = c.work({"shared.txt": "the branch's\n"})
        c.on_main({"shared.txt": "main's\n"})
        path = "shared.txt"
    before, main = c.head(), c.main()
    rc, out, err = c.land(sha)
    assert (rc, out) == (1, "land crate: red behind exit 1\n"), err
    assert path in err
    assert (c.head(), c.main(), c.clean(), c.ran()) == (before, main, "", [])


# 4. NICE rows merge by id.

def nice(*rows):
    return NICE_HEAD + "".join(rows)


def test_land4_4_a_row_kept_a_row_removed(c):
    base = [row(n) for n in range(2, 8)]
    sha = c.work({NICE: nice(*base, row(8, "the branch's"))})
    c.on_main({NICE: nice(*base[:3], *base[4:])})        # main removes n5
    rc, out, err = c.land(sha)
    assert rc == 0, (out, err)
    text = c.show("main", NICE)
    assert "| n8 | S4 | `crate` | the branch's" in text and "| n5 |" not in text


def test_land4_4_a_row_both_changed_is_red_behind(c):
    base = [row(n) for n in range(2, 8)]
    sha = c.work({NICE: nice(*base[:4], row(6, "the branch's"), base[5])})
    c.on_main({NICE: nice(*base[:4], row(6, "main's"), base[5])})
    rc, out, err = c.land(sha)
    assert (rc, out) == (1, "land crate: red behind exit 1\n"), err
    assert NICE in err and "n6" in err
    assert c.head() == sha and c.clean() == ""


@pytest.mark.parametrize("overflow,new", [(False, (11, 12)), (True, (12, 13))])
def test_land4_4_a_branch_row_under_an_id_main_used_is_renumbered(c, overflow, new):
    base = [row(n) for n in range(2, 8)]
    if overflow:
        c.on_main({OVERFLOW: OVERFLOW_TEXT.replace("| n1 |", "| n11 |")})
    sha = c.work({NICE: nice(*base, row(8, "b8"), row(9, "b9"), row(10, "b10")),
                  "design/packets/p1-crate.md": "Rows n8, n9 and n10; not n80.\n",
                  "shared.txt": "base\nsee n8\n"})
    c.on_main({NICE: nice(*base, row(8, "m8"), row(9, "m9"))})
    rc, out, err = c.land(sha)
    assert rc == 0, (out, err)
    text = c.show("main", NICE)
    for n, t in ((8, "m8"), (9, "m9"), (new[0], "b8"), (new[1], "b9"), (10, "b10")):
        assert row(n, t) in text + "\n", (n, t, text)
    assert c.show("main", "design/packets/p1-crate.md") == (
        "Rows n%d, n%d and n10; not n80." % new)
    assert c.show("main", "shared.txt") == "base\nsee n8"
    assert "shared.txt" in err and "n8" in err


# 5. The stamp's and the version check's reds.

def test_land4_5_a_stamp_that_exits_3_is_red_stamp_and_a_rerun_lands(c):
    sha = c.work({"f": "x\n"})
    c.on_main({"g": "y\n"})
    rc, out, err = c.land(sha, env={"STAMP_EXIT": "3"})
    merge = c.head()
    assert (rc, out) == (3, "land crate: red stamp exit 3, as %s\n" % merge), err
    assert c.clean() == "" and "check" not in c.ran()
    assert c.body(merge).splitlines()[-1] == "Gate-Land: " + sha
    rc, out, err = c.land(sha)                          # a cut between the merge and the stamp
    new = c.git(c.repo, "rev-parse", "main^2")
    assert (rc, out) == (0, ok(sha, new, "1.0.0-alpha.2")), err
    assert c.git(c.repo, "rev-parse", new + "^") == merge


def test_land4_5_a_stamp_that_edits_another_line_is_red_stamp_exit_1(c):
    sha = c.work({"f": "x\n"})
    rc, out, err = c.land(sha, env={"STAMP_EXTRA": "1"})
    assert (rc, out) == (1, "land crate: red stamp exit 1\n"), err
    assert "shared.txt" in err
    assert c.clean() == "" and c.head() == sha and "check" not in c.ran()


def test_land4_5_a_version_check_that_exits_1_is_red_version_before_the_check(c):
    c.put(c.repo, {"scripts/plugin-version-check": PVC})
    os.chmod(str(c.repo / "scripts/plugin-version-check"), 0o755)
    c.commit(c.repo, "a version check")
    sha = c.work({"f": "x\n"})
    rc, out, err = c.land(sha, env={"PVC_EXIT": "1"})
    assert (rc, out) == (1, "land crate: red version exit 1, as %s\n" % c.head()), err
    assert c.ran() == ["stamp", "version"]


# 6. A second call after a red check; a head the rerun does not give.

def test_land4_6_a_second_call_after_a_red_check_takes_the_head(c):
    sha = c.work({"f": "x\n"})
    c.on_main({"g": "y\n"})
    first = c.land(sha, env={"CHECK_EXIT": "2"})
    new = c.head()
    assert first[:2] == (2, "land crate: red check exit 2, as %s\n" % new), first[2]
    second = c.land(sha, env={"CHECK_EXIT": "2"})
    assert second[:2] == first[:2], second[2]
    assert c.head() == new and c.clean() == ""
    rc, out, err = c.land(sha)
    assert (rc, out) == (0, ok(sha, new, "1.0.0-alpha.2")), err


@pytest.mark.parametrize("how", ["foreign", "tree"])
def test_land4_6_a_head_not_the_jobs_is_red_sha(c, how):
    sha = c.work({"f": "x\n"})
    c.on_main({"g": "y\n"})
    c.land(sha, env={"CHECK_EXIT": "2"})
    message = "by hand" if how == "foreign" else "by hand\n\nGate-Land: " + sha
    c.put(c.tree, {"shared.txt": "a hand\n"})
    c.git(c.tree, "commit", "-qam", message)
    head = c.head()
    rc, out, err = c.land(sha)
    assert (rc, out) == (1, "land crate: red sha exit 1\n"), err
    assert "p1-crate's head is %s, not %s" % (head, sha) in err
    assert c.head() == head and c.ran().count("check") == 1


# 7. A branch that holds main and a stamp with nothing to write: the pin's line.

def test_land4_7_holds_main_and_nothing_to_stamp_is_the_pins_line(c):
    sha = c.work({MANIFEST: manifest("1.0.0-alpha.2"), "README.md": doc("1.0.0-alpha.2"),
                  SOURCE: doc("1.0.0-alpha.2")})
    rc, out, err = c.land(sha)
    assert (rc, out) == (0, "land crate: ok %s, main readied\n" % sha), err
    assert c.git(c.repo, "rev-parse", "main^2") == sha
    assert c.ran() == ["stamp", "check"]


# 8. --dry-run: reads only.

def dry(c, sha, in_job):
    queue = gate.gate_dir(resolver.state_dir(c.env))
    before = (c.head(), c.main(), c.clean(), c.git(c.repo, "status", "--porcelain"))
    env = None if in_job else {gate.JOB_MARK: ""}
    rc, out, err = c.land(sha, extra=["--dry-run"], in_job=False, env=env)
    assert (c.head(), c.main(), c.clean(), c.git(c.repo, "status", "--porcelain")) == before
    assert not queue.exists() or not any(queue.iterdir())
    assert c.ran() == []
    return rc, out, err


@pytest.mark.parametrize("in_job", [True, False])
def test_land4_8_dry_run_in_each_state(tmp_path, in_job):
    (tmp_path / "a").mkdir()
    plain = Crate(tmp_path / "a", stamp=False)
    sha = plain.work({"f": "x\n"})
    plain.on_main({"g": "y\n"})
    assert dry(plain, sha, in_job)[:2] == (0, "ready: no stamp target; a branch behind main is "
                                              "red sha\nland crate: dry run, nothing queued\n")
    tail = "ready: would run make stamp and commit its lines\nland crate: dry run, nothing queued\n"
    (tmp_path / "b").mkdir()
    holds = Crate(tmp_path / "b")
    sha = holds.work({"f": "x\n"})
    assert dry(holds, sha, in_job)[:2] == (0, "ready: p1-crate holds main\n" + tail)
    (tmp_path / "c").mkdir()
    behind = Crate(tmp_path / "c")
    sha = behind.work({"f": "x\n"})
    main = behind.on_main({"g": "y\n"})
    assert dry(behind, sha, in_job)[:2] == (
        0, "ready: would merge main %s into p1-crate, no conflict\n" % main[:7] + tail)
    (tmp_path / "d").mkdir()
    derived = Crate(tmp_path / "d")
    sha = derived_conflicts(derived)
    main = derived.main()
    rc, out, err = dry(derived, sha, in_job)
    assert (rc, out) == (0, "ready: would merge main %s into p1-crate, 5 derived hunks: %s\n"
                         % (main[:7], ", ".join([NICE, "README.md", SIDECAR, SOURCE, MANIFEST]))
                         + tail), err


def test_land4_8_dry_run_reds_as_the_read_would(c):
    sha = c.work({"f": "x\n"})
    c.msg.write_text("Merge another: the wrong branch\n")
    assert dry(c, sha, True)[:2] == (1, "land crate: red merge-file exit 1\n")
    c.msg.write_text("Merge p1-crate: x\n")
    c.work({"shared.txt": "the branch's\n"})
    c.on_main({"shared.txt": "main's\n"})
    assert dry(c, c.head(), True)[:2] == (1, "land crate: red behind exit 1\n")
    rc, out, _ = c.land(sha, extra=["--dry-run"], in_job=False,
                        args=[str(c.repo), BRANCH, sha, str(c.msg), "five"])
    assert (rc, out) == (2, "land ?: red usage exit 2\n")


# The repo's own scripts/stamp, twice.

class Pear(Crate):
    """land3's made-up plugin `pear` as `crate`, with the repo's own scripts/stamp."""

    def __init__(self, tmp):
        files = {
            ".gitignore": ".claude/worktrees/\n__pycache__/\n",
            "Makefile": CHECK + "STAMP_BASE ?= main\nstamp:\n\t@\"$$STAMP_PY\" \"$$STAMP_SCRIPT\" "
                                "--base \"$(STAMP_BASE)\"\n",
            MANIFEST: manifest_text("2.0.0-alpha.7"),
            "plugin/lib/pear.py": "def pear():\n    return 1\n",
            "tests/test_pear.py": pear_tests(),
            SOURCE: source_text("2.0.0-alpha.7", 3), "README.md": readme_text("2.0.0-alpha.7", 3),
            NICE: NICE_HEAD + "| n3 | S3 | `pear.py` | a row | e | 2026-01-01, a builder |\n",
            OVERFLOW: OVERFLOW_TEXT,
        }
        files[SIDECAR] = sidecar(files)
        super().__init__(tmp, files=files)
        self.env.update({"STAMP_PY": sys.executable, "STAMP_SCRIPT": str(STAMP)})

    def stamped(self, cwd, version, count, files, row_text):
        files = dict(files, **{MANIFEST: manifest_text(version), SOURCE: source_text(version, count),
                               "README.md": readme_text(version, count),
                               NICE: NICE_HEAD + "| n3 | S3 | `pear.py` | a row | e | 2026-01-01, "
                               "a builder |\n" + row_text})
        files[SIDECAR] = sidecar(files)
        return self.commit(cwd, "landed", files)


def sidecar(files):
    return "".join("%s  %s\n" % (hashlib.sha256(files[p].encode()).hexdigest(), p)
                   for p in (SOURCE, "README.md"))


def pear_behind(p):
    sha = p.stamped(p.tree, "2.0.0-alpha.8", 4, {
        "plugin/lib/pear.py": "def pear():\n    return 2\n",
        "tests/test_pear.py": pear_tests(("test_a", "test_b", "test_c", "test_d"))},
        "| n4 | S4 | `pear.py` | the branch's | e | 2026-01-02, a builder |\n")
    p.stamped(p.repo, "2.0.0-alpha.8", 5, {"tests/test_other.py": pear_tests(("test_x", "test_y"))},
              "| n4 | S4 | `pear.py` | main's | e | 2026-01-02, a builder |\n")
    return sha


def test_land4_3_the_repos_own_stamp_readies_a_branch_behind_main(tmp_path):
    p = Pear(tmp_path)
    sha = pear_behind(p)
    rc, out, err = p.land(sha)
    new = p.git(p.repo, "rev-parse", "main^2")
    assert (rc, out) == (0, ok(sha, new, "2.0.0-alpha.9")), err
    assert "`6` tests" in p.show("main", "README.md")
    text = p.show("main", NICE)
    assert "| n4 | S4 | `pear.py` | main's" in text and "| n5 | S4 | `pear.py` | the branch's" in text
    assert subprocess.run(["shasum", "-a", "256", "-c", "--status", SIDECAR],
                          cwd=str(p.repo)).returncode == 0


def test_land4_6_the_repos_own_stamp_reruns_to_the_heads_tree(tmp_path):
    p = Pear(tmp_path)
    sha = pear_behind(p)
    first = p.land(sha, env={"CHECK_EXIT": "2"})
    new = p.head()
    assert first[:2] == (2, "land crate: red check exit 2, as %s\n" % new), first[2]
    second = p.land(sha, env={"CHECK_EXIT": "2"})
    assert second[:2] == first[:2], second[2]
    assert p.head() == new and [x for x in os.listdir(str(tmp_path)) if "ready" in x] == []
