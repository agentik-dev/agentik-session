"""Packet lh1-land-hygiene: `gate land` and `gate publish` scan by the repo's own hygiene targets.

A tree's scan is `make hygiene` where the Makefile has a line opening `hygiene:`, else the bare
`scripts/hygiene` as before; a range's scan (the branch's span, the merge message's, publish's
`<R>..<S>`) is `make hygiene-range RANGE=<span>` where the Makefile has a line opening
`hygiene-range:`, else the bare script with `--require-private --commits <span>` as before.
Every case is a made-up repo in a temp folder with its own HOME and git identity; publish's
remote is a bare repo beside it. The fakes write one line a call to $LAND_ORDER."""

import os
import re
import subprocess
import unittest

import pytest

from test_land import LandCase
from test_land5_publish import Crate, line

# The bare script: --help names --commits; a range scan exits $SCRIPT_RANGE; the tree's scan
# exits $SCRIPT_TREE, 1 unless set (it counts the product's own words).
SCRIPT = ("#!/bin/sh\necho \"script $*\" >> \"$LAND_ORDER\"\n"
          "case $1 in --help) echo 'usage: hygiene [--require-private] [--commits RANGE]'; "
          "exit 0 ;; esac\n"
          "case \"$*\" in *--commits*) exit \"${SCRIPT_RANGE:-0}\" ;; esac\n"
          "exit \"${SCRIPT_TREE:-1}\"\n")
# A copy from before --commits: its --help names no such flag.
OLD = ("#!/bin/sh\necho \"script $*\" >> \"$LAND_ORDER\"\n"
       "case $1 in --help) echo 'usage: hygiene [--json]'; exit 0 ;; esac\n"
       "exit \"${SCRIPT_TREE:-0}\"\n")
CHECK = ("check:\n"
         "\t@echo check >> \"$$LAND_ORDER\"\n")
# The repo's own wrapper: it passes unless $TREE_RED is set.
TARGET = ("hygiene:  ## the scan with the product's own words left out\n"
          "\t@echo make-hygiene >> \"$$LAND_ORDER\"\n"
          "\t@exit $${TREE_RED:-0}\n")
# The range's wrapper: it records its RANGE; $BRANCH_RED is the exit on the branch's span,
# $MESSAGE_RED on any other (the merge message's).
RANGE = ("hygiene-range:\n"
         "\t@echo \"make-range $(RANGE)\" >> \"$$LAND_ORDER\"\n"
         "\t@case \"$(RANGE)\" in refs/heads/main..*) exit $${BRANCH_RED:-0} ;; "
         "*) exit $${MESSAGE_RED:-0} ;; esac\n")
# A line that opens `hygiene:` and is no rule after all: make cannot run the target.
NO_RULE = "ifeq (a,b)\nhygiene:\n\t@true\nendif\n"
NO_RANGE_RULE = "ifeq (a,b)\nhygiene-range:\n\t@true\nendif\n"
SPAN = re.compile(r"\A([0-9a-f]{40})\.\.([0-9a-f]{40})\Z")


class LandHygiene(LandCase):
    def lines(self):
        if not os.path.exists(self.order):
            return []
        with open(self.order) as fh:
            return [x.strip() for x in fh.read().splitlines()]

    def with_env(self, **names):
        return dict(self.env, **names)

    def ranges(self):
        return [x[len("make-range "):] for x in self.lines() if x.startswith("make-range ")]

    def assertMessageSpan(self, span, sha, before):
        """The merge message's span, as the pin computes it: <sha>..<a dangling commit whose
        parents are main as read and sha, its message the merge file's>."""
        m = SPAN.match(span)
        self.assertTrue(m, span)
        self.assertEqual(m.group(1), sha)
        self.assertEqual(self.git("rev-list", "--parents", "-n1", m.group(2)).split()[1:],
                         [before, sha])
        self.assertEqual(self.git("log", "-1", "--format=%s", m.group(2)),
                         "Merge work: land the branch")


class TestLandRoads(LandHygiene):
    # 1. The repo's hygiene target passes and the bare script counts its own words: the target
    # is the tree's scan and the landing passes (at the pin: red hygiene exit 1).
    def test_lh1_1_the_target_is_the_tree_scan_and_the_landing_passes(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + TARGET, "scripts/hygiene": SCRIPT})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        self.assertIn("make-hygiene", self.lines())
        self.assertNotIn("script", self.lines())    # the bare tree scan never ran
        self.assertIn("land-step: hygiene: make hygiene in %s\n" % self.worktree("work"),
                      p.stderr)
        self.assertEqual(self.git("rev-list", "--parents", "-n1", "main").split()[1:],
                         [before, sha])

    def test_lh1_1_a_red_target_is_red_hygiene_with_makes_code(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + TARGET, "scripts/hygiene": SCRIPT})
        p = self.land("work", sha, env=self.with_env(TREE_RED="1", SCRIPT_TREE="0"))
        self.assertRed(p, "hygiene", 2)     # make's own code for a recipe that failed
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))

    # 2. No target: the bare script, a hit red hygiene with its code.
    def test_lh1_2_no_target_runs_the_bare_script_and_a_hit_is_red_with_its_code(self):
        before = self.main_sha()
        sha = self.branch("work", {"scripts/hygiene": SCRIPT})
        p = self.land("work", sha, env=self.with_env(SCRIPT_TREE="5"))
        self.assertRed(p, "hygiene", 5)
        self.assertEqual(self.main_sha(), before)
        self.assertIn("script", self.lines())
        self.assertNotIn("make-hygiene", self.lines())
        self.assertIn("land-step: hygiene: scripts/hygiene in %s\n" % self.worktree("work"),
                      p.stderr)

    # 3. A hygiene-range target: the message's span, the branch's, the message's again.
    def test_lh1_3_the_range_target_takes_each_span_as_the_pin_computes_it(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + TARGET + RANGE, "scripts/hygiene": SCRIPT})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        spans = self.ranges()
        self.assertEqual(len(spans), 3, spans)
        self.assertEqual(spans[1], "refs/heads/main..%s" % sha)
        for span in (spans[0], spans[2]):
            self.assertMessageSpan(span, sha, before)
        # The message's scan comes before the check and again before the merge.
        order = [x.split()[0] for x in self.lines()]
        self.assertEqual(order, ["make-range", "check", "make-hygiene", "make-range",
                                 "make-range"])
        self.assertFalse([x for x in self.lines() if x.startswith("script")])
        self.assertIn("land-step: hygiene: make hygiene-range RANGE=refs/heads/main..%s in %s\n"
                      % (sha, self.worktree("work")), p.stderr)

    def test_lh1_3_a_red_branch_span_is_red_hygiene_before_the_merge(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + TARGET + RANGE})
        p = self.land("work", sha, env=self.with_env(BRANCH_RED="1"))
        self.assertRed(p, "hygiene", 2)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.lines()[-1], "make-range refs/heads/main..%s" % sha)

    def test_lh1_3_a_red_message_span_is_red_merge_file_before_the_check(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + TARGET + RANGE})
        p = self.land("work", sha, env=self.with_env(MESSAGE_RED="1"))
        self.assertRed(p, "merge-file", 2)
        self.assertEqual(self.main_sha(), before)
        self.assertNotIn("check", self.lines())
        self.assertIn("make hygiene-range exit 2 on the merge message", p.stderr)

    # 4. A hygiene target and no hygiene-range: the range through the bare script, as at the pin.
    def test_lh1_4_no_range_target_scans_the_range_with_the_bare_script(self):
        sha = self.branch("work", {"Makefile": CHECK + TARGET, "scripts/hygiene": SCRIPT})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        calls = [x for x in self.lines() if x.startswith("script --require-private")]
        self.assertEqual(calls[1], "script --require-private --commits refs/heads/main..%s" % sha)
        self.assertEqual(len(calls), 3, calls)

    def test_lh1_4_a_hit_in_the_range_is_red_hygiene_as_at_the_pin(self):
        sha = self.branch("work", {"Makefile": CHECK + TARGET, "scripts/hygiene": SCRIPT})
        p = self.land("work", sha, env=self.with_env(SCRIPT_RANGE="3"))
        # The message's scan before the check reads the range first, as at the pin.
        self.assertRed(p, "merge-file", 3)

    def test_lh1_4_an_older_copy_beside_the_target_says_the_range_was_not_scanned(self):
        sha = self.branch("work", {"Makefile": CHECK + TARGET, "scripts/hygiene": OLD})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied, range not scanned\n" % sha)
        self.assertIn("make-hygiene", self.lines())

    # R3: a target make cannot run is red, never a skipped scan.
    def test_lh1_r3_a_hygiene_line_that_is_no_rule_is_red_hygiene(self):
        before = self.main_sha()
        sha = self.branch("work", {"Makefile": CHECK + NO_RULE, "scripts/hygiene": OLD})
        p = self.land("work", sha)
        self.assertRed(p, "hygiene", 2)
        self.assertEqual(self.main_sha(), before)
        self.assertNotIn("script", self.lines())

    def test_lh1_r3_a_range_line_that_is_no_rule_is_red_merge_file(self):
        sha = self.branch("work", {"Makefile": CHECK + TARGET + NO_RANGE_RULE})
        p = self.land("work", sha)
        self.assertRed(p, "merge-file", 2)


# 5. publish in the four repos: the same roads, the same reds.

def crate(tmp_path, makefile=None, script=True):
    c = Crate(tmp_path.resolve(), hygiene=script)
    if makefile is not None:
        c.commit("the scan's targets", {"Makefile": makefile})
    if script and script is not True:
        c.commit("an older scan", {"scripts/hygiene": script})
    return c


def published(c, env=None):
    before, head, s = c.landed()
    c.land_result(before, "land crate: ok %s, main readied" % head)
    rc, out, err = c.publish(str(c.repo), env=env)
    return rc, out, err, s


def test_lh1_5_publish_the_target_passes_where_the_bare_tree_scan_would_not(tmp_path):
    c = crate(tmp_path, "check:\n\t@true\n" + TARGET)
    r = c.sha("origin/main")
    rc, out, err, s = published(c, {"HYG_TREE": "1"})
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert "make-hygiene" in c.ran()
    assert "hygiene " not in c.ran()      # Crate's fake writes `hygiene $*`
    assert "hygiene --require-private --commits %s..%s" % (r, s) in c.ran()     # 4's road
    assert "publish-step: hygiene: make hygiene in %s\n" % c.repo in err
    assert c.bare_main() == s


def test_lh1_5_publish_without_a_target_runs_the_bare_script_and_reds_with_its_code(tmp_path):
    c = crate(tmp_path)
    rc, out, err, s = published(c, {"HYG_TREE": "5"})
    assert (rc, out) == (5, line(c, "red hygiene exit 5")), err
    assert "hygiene " in c.ran() and "make-hygiene" not in c.ran()
    assert c.bare_main() != s


@pytest.mark.parametrize("red", [None, "1"])
def test_lh1_5_publish_takes_the_range_target_with_its_span(tmp_path, red):
    c = crate(tmp_path, "check:\n\t@true\n" + TARGET + RANGE.replace("refs/heads/main", "none"))
    r = c.sha("origin/main")
    rc, out, err, s = published(c, {"MESSAGE_RED": red} if red else None)
    assert "make-range %s..%s" % (r, s) in c.ran()
    assert not [x for x in c.ran() if x.startswith("hygiene")]
    if red:
        assert (rc, out) == (2, line(c, "red hygiene exit 2")), err
        assert c.bare_main() == r
    else:
        assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err


def test_lh1_5_publish_with_no_range_target_reds_on_the_bare_range(tmp_path):
    c = crate(tmp_path, "check:\n\t@true\n" + TARGET)
    rc, out, err, s = published(c, {"HYG_RANGE": "3"})
    assert (rc, out) == (3, line(c, "red hygiene exit 3")), err
    assert c.bare_main() != s


def test_lh1_5_publish_with_an_older_copy_beside_the_target_is_range_not_scanned(tmp_path):
    c = crate(tmp_path, "check:\n\t@true\n" + TARGET, OLD)
    rc, out, err, s = published(c)
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin, range not scanned" % s)), err


@pytest.mark.parametrize("makefile", [NO_RULE, "hygiene:\n\t@true\nifeq\n"])
def test_lh1_r3_publish_a_target_make_cannot_run_is_red_hygiene(tmp_path, makefile):
    c = crate(tmp_path, makefile)
    rc, out, err, s = published(c)
    assert (rc, out) == (2, line(c, "red hygiene exit 2")), err
    assert c.bare_main() != s


# R4: this repo's own Makefile has both targets, so its own landing takes the target's road.

THIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_lh1_r4_this_repo_lands_by_its_own_targets():
    from claude_session import land
    assert land.has_target(THIS, "hygiene") and land.has_target(THIS, "hygiene-range")
    assert land.tree_scan(THIS)[:2] == ("make hygiene", ("make", "hygiene"))
    assert land.range_scan(THIS)("a..b")[:2] == (
        "make hygiene-range RANGE=a..b", ("make", "hygiene-range", "RANGE=a..b"))


def test_lh1_r4_the_range_target_runs_what_the_land_step_ran_for_a_range(tmp_path):
    """The rule as this Makefile writes it, run in a temp folder beside a fake scripts/hygiene
    that records its argv: the bare script's range call, its exit the target's; no RANGE is 2."""
    with open(os.path.join(THIS, "Makefile")) as fh:
        text = fh.read()
    rule = text[text.index("\nhygiene-range:") + 1:]
    rule = rule[:rule.index("\n", rule.index("\n\tscripts/hygiene") + 1) + 1]
    (tmp_path / "Makefile").write_text(rule)
    fake = tmp_path / "scripts" / "hygiene"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho \"$*\" >> \"%s\"\nexit 3\n" % (tmp_path / "argv"))
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS",
                                                            "GNUMAKEFLAGS", "MAKEFILES",
                                                            "MAKELEVEL")}
    p = subprocess.run(["make", "-s", "hygiene-range", "RANGE=refs/heads/main..abc1234"],
                       cwd=str(tmp_path), env=env, capture_output=True, text=True)
    assert p.returncode == 2, p.stderr      # make's code: the recipe exited 3
    assert (tmp_path / "argv").read_text() == "--require-private --commits refs/heads/main..abc1234\n"
    p = subprocess.run(["make", "-s", "hygiene-range"], cwd=str(tmp_path), env=env,
                       capture_output=True, text=True)
    assert p.returncode == 2 and "RANGE=<a>..<b> names the span" in p.stdout
    assert (tmp_path / "argv").read_text().count("\n") == 1


# The fix of review 1. C1: a make road runs only when `make -q` says a recipe would run; its
# exit 0 (nothing to be done, up to date) is red at the scan's step, nothing merged or pushed.
# At f3405d7 each of these landed and pushed, the scan skipped.

REC = "\t@echo make-hygiene >> \"$$LAND_ORDER\"; exit 1\n"
TREE_SHAPES = {
    "phony-ifeq": ".PHONY: check hygiene\nifeq (a,b)\nhygiene:\n" + REC + "endif\n",
    "phony-define": ".PHONY: check hygiene\ndefine SCAN\nhygiene:\n" + REC + "endef\n",
    "phony-assign": ".PHONY: check hygiene\nhygiene:=x\n",
    "phony-empty": ".PHONY: check hygiene\nhygiene:\n",
    "folder": "hygiene:\n" + REC,
}
RANGE_REC = "\t@echo make-range >> \"$$LAND_ORDER\"; exit 1\n"
RANGE_SHAPES = {
    "phony-ifdef": ".PHONY: hygiene-range\nifdef NEVER\nhygiene-range:\n" + RANGE_REC + "endif\n",
    "folder": "hygiene-range:\n" + RANGE_REC,
}


def shape_files(kind, name, make_check):
    text = (TREE_SHAPES if kind == "tree" else RANGE_SHAPES)[name]
    files = {"Makefile": make_check + text}
    if name == "folder":
        files["%s/notes.txt" % ("hygiene" if kind == "tree" else "hygiene-range")] = "notes\n"
    return files


class TestQuestion(LandHygiene):
    def assertNoRecipe(self, p, step, before):
        self.assertRed(p, step, 1)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertIn("the target would run no recipe", p.stderr)
        self.assertNotIn("make-hygiene", self.lines())
        self.assertNotIn("make-range", self.lines())

    def test_lh1_c1_a_tree_target_make_would_skip_is_red_hygiene(self):
        for name in TREE_SHAPES:
            with self.subTest(name):
                self.tearDown_shape()
                before = self.main_sha()
                files = shape_files("tree", name, CHECK)
                files["scripts/hygiene"] = SCRIPT
                sha = self.branch("work", files)
                p = self.land("work", sha)
                self.assertNoRecipe(p, "hygiene", before)
                self.assertIn("land-step: make -q hygiene exit 0 in ", p.stderr)
                self.assertNotIn("script", self.lines())    # never the bare script instead

    def test_lh1_c1_a_range_target_make_would_skip_is_red_merge_file(self):
        for name in RANGE_SHAPES:
            with self.subTest(name):
                self.tearDown_shape()
                before = self.main_sha()
                files = shape_files("range", name, CHECK)
                files["scripts/hygiene"] = SCRIPT
                sha = self.branch("work", files)
                p = self.land("work", sha, env=self.with_env(SCRIPT_TREE="0", SCRIPT_RANGE="1"))
                self.assertNoRecipe(p, "merge-file", before)
                self.assertNotIn("check", self.lines())
                self.assertFalse([x for x in self.lines() if "--commits" in x])

    def tearDown_shape(self):
        """Each subtest from a fresh branch `work` and an empty record."""
        if os.path.isdir(self.worktree("work")):
            self.git("worktree", "remove", "--force", self.worktree("work"))
            self.git("branch", "-D", "work")
        if os.path.exists(self.order):
            os.remove(self.order)

    # C2: the road follows the makefile make reads, GNUmakefile first.
    def test_lh1_c2_a_gnumakefile_target_is_the_road(self):
        sha = self.branch("work", {"GNUmakefile": CHECK + TARGET, "Makefile": CHECK,
                                   "scripts/hygiene": SCRIPT})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("make-hygiene", self.lines())
        self.assertNotIn("script", self.lines())

    def test_lh1_c2_a_makefile_target_make_does_not_read_is_no_road(self):
        sha = self.branch("work", {"GNUmakefile": CHECK, "Makefile": CHECK + TARGET,
                                   "scripts/hygiene": SCRIPT})
        p = self.land("work", sha, env=self.with_env(SCRIPT_TREE="4"))
        self.assertRed(p, "hygiene", 4)       # the bare script, as at the pin
        self.assertIn("script", self.lines())
        self.assertNotIn("make-hygiene", self.lines())


@pytest.mark.parametrize("kind,name", [("tree", n) for n in TREE_SHAPES] +
                         [("range", n) for n in RANGE_SHAPES])
def test_lh1_c1_publish_a_target_make_would_skip_is_red_and_pushes_nothing(tmp_path, kind, name):
    c = crate(tmp_path, None)
    c.commit("the scan's targets", shape_files(kind, name, "check:\n\t@true\n"))
    rc, out, err, s = published(c, {"HYG_TREE": "1"} if kind == "tree" else {"HYG_RANGE": "1"})
    assert (rc, out) == (1, line(c, "red hygiene exit 1")), err
    assert "the target would run no recipe" in err
    assert not [x for x in c.ran() if x.startswith("make-")]
    if kind == "tree":
        assert "hygiene " not in c.ran()
    assert c.bare_main() != s


def test_lh1_c2_publish_follows_the_gnumakefile(tmp_path):
    c = crate(tmp_path, None)
    c.commit("the scan's targets", {"GNUmakefile": "check:\n\t@true\n" + TARGET})
    rc, out, err, s = published(c, {"HYG_TREE": "1"})
    assert (rc, out) == (0, line(c, "ok %s, pushed to origin" % s)), err
    assert "make-hygiene" in c.ran() and "hygiene " not in c.ran()


def test_lh1_c1_this_repos_targets_would_run_a_recipe(tmp_path):
    """Acceptance 3: this Makefile, copied whole into a temp folder, answers `make -q` with 1
    for both scan targets, so its own landing's scans run."""
    with open(os.path.join(THIS, "Makefile")) as fh:
        (tmp_path / "Makefile").write_text(fh.read())
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS",
                                                            "GNUMAKEFLAGS", "MAKEFILES",
                                                            "MAKELEVEL")}
    env["HOME"] = str(tmp_path)
    for call in (["hygiene"], ["hygiene-range", "RANGE=refs/heads/main..abc1234"]):
        p = subprocess.run(["make", "-q", *call], cwd=str(tmp_path), env=env,
                           capture_output=True, text=True)
        assert p.returncode == 1, (call, p.stdout, p.stderr)
    assert sorted(os.listdir(str(tmp_path))) == ["Makefile"]    # no recipe ran


if __name__ == "__main__":
    unittest.main()
