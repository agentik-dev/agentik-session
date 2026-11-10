"""Tests for `gate land`'s steps, `gate land --in-job` (packet FW4c R1): hq's tests/test_land.py at
9f394ce, ported. Only the call changed: the job's argv with the job mark, not scripts/land.

Every effect is on a scratch clone under a temp dir, with HOME, XDG_STATE_HOME and
git's global config pointing into it, so no test reads the owner's checkouts and the
gate jobs of (d) run in a queue of their own, never the live one. No network.
"""

import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "plugin", "lib", "agentik-session")
LAND_PY = os.path.join(ROOT, "plugin", "lib", "claude_session", "land.py")
LAND = [sys.executable, RUNNER, "gate", "land", "--in-job"]
MARK = "CLAUDE_SESSION_GATE_JOB"

MAKEFILE = (
    "check:\n"
    "\t@echo check >> \"$$LAND_ORDER\"\n"
    "\t@test ! -e RED\n"
    "\t@if [ -e LITTER ]; then touch litter.out; fi\n"
)
HYGIENE = "#!/bin/sh\necho hygiene >> \"$LAND_ORDER\"\nexit %d\n"


class LandCase(unittest.TestCase):
    """A scratch repo on main, with its worktrees where the flow puts them."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="land-test-"))
        self.addCleanup(self._teardown)
        gitconfig = os.path.join(self.tmp, "gitconfig")
        with open(gitconfig, "w") as fh:
            fh.write("[user]\n\tname = Land Test\n\temail = land@" + "example.invalid\n"
                     "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        self.order = os.path.join(self.tmp, "order")
        self.env = dict(os.environ)
        self.env.update({
            "HOME": self.tmp,
            "XDG_STATE_HOME": os.path.join(self.tmp, "state"),
            "XDG_CONFIG_HOME": os.path.join(self.tmp, "config"),
            "GIT_CONFIG_GLOBAL": gitconfig,
            "GIT_CONFIG_NOSYSTEM": "1",
            "LAND_ORDER": self.order,
            MARK: "20261110-000000-1",
        })
        # make's own variables stay: a landing inside a `make` run has to shrug them off (F7).
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "CLAUDE_CODE_SESSION_ID"):
            self.env.pop(name, None)
        self.new_repo("scratch")
        self.message = os.path.join(self.tmp, "merge-message")
        self.write(self.tmp, "merge-message", "land the branch\n\nThe trailer line.\n")

    def new_repo(self, name):
        self.repo = os.path.join(self.tmp, name)
        os.makedirs(self.repo)
        self.git("init", "-q")
        self.write(self.repo, "Makefile", MAKEFILE)
        self.write(self.repo, ".gitignore", ".claude/worktrees/\n")
        self.write(self.repo, "shared.txt", "base\n")
        self.git("add", "Makefile", ".gitignore", "shared.txt")
        self.git("commit", "-qm", "base")

    def _teardown(self):
        # A queue's runner idles a while after its last job: end the one this test started,
        # by the pid it wrote under this test's own state root.
        for path in glob.glob(os.path.join(self.tmp, "state", "**", "runner.json"),
                              recursive=True):
            try:
                with open(path) as fh:
                    os.kill(int(json.load(fh)["pid"]), signal.SIGTERM)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args, cwd=None):
        p = subprocess.run(["git", *args], cwd=cwd or self.repo, env=self.env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, "git %s: %s" % (" ".join(args), p.stderr))
        return p.stdout.strip()

    def write(self, where, name, text, mode=None):
        path = os.path.join(where, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        if mode:
            os.chmod(path, mode)
        return path

    def worktree(self, name):
        return os.path.join(self.repo, ".claude", "worktrees", name)

    def branch(self, name, files):
        """A branch in its worktree, one commit of `files`; its sha."""
        tree = self.worktree(name)
        self.git("worktree", "add", "-q", "-b", name, tree, "main")
        for rel, text in files.items():
            self.write(tree, rel, text, 0o755 if rel == "scripts/hygiene" else None)
        self.git("add", *files, cwd=tree)
        self.git("commit", "-qm", "the work of " + name, cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def on_main(self, name, text):
        self.write(self.repo, name, text)
        self.git("add", name)
        self.git("commit", "-qm", "main moves " + name)

    def land(self, branch, sha, message=None, repo=None, env=None, cwd=None):
        p = subprocess.run([*LAND, repo or self.repo, branch, sha, message or self.message],
                           cwd=cwd or self.repo, env=env or self.env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p

    def assertRed(self, p, step, code=None):
        self.assertNotEqual(p.returncode, 0)
        if code is not None:
            self.assertEqual(p.returncode, code)
        self.assertEqual(p.stdout, "land %s: red %s exit %d\n"
                         % (os.path.basename(self.repo), step, p.returncode))

    def main_sha(self):
        return self.git("rev-parse", "main")

    def porcelain(self):
        return self.git("status", "--porcelain")

    def porcelain_lines(self):
        # git() strips its output, which would eat a first line's leading space.
        p = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, env=self.env,
                           text=True, stdout=subprocess.PIPE)
        return p.stdout.splitlines()

    def renamed_branch(self):
        """A branch whose one commit renames shared.txt to moved.txt; its sha."""
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.git("mv", "shared.txt", "moved.txt", cwd=tree)
        self.git("commit", "-qm", "rename", cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def ran(self):
        if not os.path.exists(self.order):
            return []
        with open(self.order) as fh:
            return fh.read().split()


class TestGreen(LandCase):
    def test_a_green_branch_lands_no_ff_and_the_line_is_one(self):
        before = self.main_sha()
        sha = self.branch("work", {"new.txt": "new\n"})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        parents = self.git("rev-list", "--parents", "-n1", "main").split()[1:]
        self.assertEqual(parents, [before, sha])
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "land the branch")
        self.assertEqual(self.porcelain(), "")
        self.assertFalse(os.path.exists(self.worktree("work")))
        self.assertEqual(self.ran(), ["check"])
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("branch", "--list", "work"), "")

    def test_a_the_steps_run_in_order_hygiene_in_the_worktree(self):
        sha = self.branch("work", {"scripts/hygiene": HYGIENE % 0})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        # The tree scan, then the --help probe for --commits (test_land_range.py).
        self.assertEqual(self.ran(), ["check", "hygiene", "hygiene"])

    def test_a_a_repo_outside_the_working_directory_and_a_relative_message(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, ".git/land-msg", "from a relative path\n")
        p = self.land("work", sha, message=".git/land-msg")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "from a relative path")


    def test_a_a_repo_that_does_not_ignore_its_worktrees_still_lands(self):
        # two of the suite's repos keep no ignore line for .claude/worktrees/.
        self.git("rm", "-q", ".gitignore")
        self.git("commit", "-qm", "no ignore line")
        sha = self.branch("work", {"new.txt": "new\n"})
        self.assertNotEqual(self.porcelain(), "")
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)

    def test_a_dirty_unrelated_files_land_and_stay_dirty(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, "shared.txt", "a sitting's charter edit\n")
        self.write(self.repo, "untracked.txt", "and a new file\n")
        self.write(self.repo, "only-here/deep.txt", "beside the merge\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        self.assertEqual(self.git("rev-parse", "main^1"), before)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertEqual(sorted(self.porcelain_lines()),
                         [" M shared.txt", "?? only-here/", "?? untracked.txt"])
        with open(os.path.join(self.repo, "shared.txt")) as fh:
            self.assertEqual(fh.read(), "a sitting's charter edit\n")

    def test_a_an_untracked_file_in_a_directory_the_merge_also_writes_lands(self):
        sha = self.branch("work", {"sub/new.txt": "new\n"})
        self.write(self.repo, "sub/other.txt", "beside it\n")
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.porcelain(), "?? sub/other.txt")

    def test_a_venv_link_in_the_worktree_goes_and_only_the_link(self):
        target = os.path.join(self.tmp, "shared-venv")
        self.write(target, "bin/python", "keep me\n")
        sha = self.branch("work", {"new.txt": "new\n"})
        os.symlink(target, os.path.join(self.worktree("work"), ".venv"))
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertFalse(os.path.lexists(self.worktree("work")))
        self.assertEqual(self.git("branch", "--list", "work"), "")
        with open(os.path.join(target, "bin", "python")) as fh:
            self.assertEqual(fh.read(), "keep me\n")

    def test_a_a_bare_name_is_a_repo_under_home_code(self):
        os.makedirs(os.path.join(self.tmp, "code"))
        os.symlink(self.repo, os.path.join(self.tmp, "code", "scratch"))
        sha = self.branch("work", {"new.txt": "new\n"})
        p = self.land("work", sha, repo="scratch")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)

    def test_a_an_abbreviated_sha_is_printed_as_named_and_merges_the_commit(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        p = self.land("work", sha[:10])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha[:10])
        self.assertEqual(self.git("rev-parse", "main^2"), sha)


class TestRed(LandCase):
    def test_b_a_red_check_leaves_main_and_exits_non_zero(self):
        before = self.main_sha()
        sha = self.branch("work", {"RED": "red\n"})
        p = self.land("work", sha)
        self.assertRed(p, "check", 2)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertEqual(self.ran(), ["check"])

    def test_b_a_red_hygiene_exits_its_code_and_leaves_main(self):
        before = self.main_sha()
        sha = self.branch("work", {"scripts/hygiene": HYGIENE % 5})
        p = self.land("work", sha)
        self.assertRed(p, "hygiene", 5)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertEqual(self.ran(), ["check", "hygiene"])

    def test_c_a_conflict_aborts_and_leaves_the_tree_clean(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.on_main("shared.txt", "main\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "merge")
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(self.main_sha(), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))
        self.assertTrue(os.path.isdir(self.worktree("work")))

    def test_main_not_checked_out_is_red_and_untouched(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.git("checkout", "-q", "-b", "elsewhere")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "main", 1)
        self.assertEqual(self.git("branch", "--show-current"), "elsewhere")
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), [])

    def assertOverlap(self, sha):
        before, status = self.main_sha(), self.porcelain()
        p = self.land("work", sha)
        self.assertRed(p, "main", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), status)
        self.assertEqual(self.ran(), [])
        self.assertTrue(os.path.isdir(self.worktree("work")))

    def test_a_dirty_file_the_merge_touches_is_red_and_untouched(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.write(self.repo, "shared.txt", "a hand's edit\n")
        self.assertOverlap(sha)

    def test_an_untracked_file_the_merge_would_create_is_red(self):
        sha = self.branch("work", {"new.txt": "the branch\n"})
        self.write(self.repo, "new.txt", "a hand's new file\n")
        self.assertOverlap(sha)

    def test_an_untracked_file_under_a_new_directory_the_merge_would_create_is_red(self):
        sha = self.branch("work", {"sub/new.txt": "the branch\n"})
        self.write(self.repo, "sub/new.txt", "a hand's new file\n")
        self.assertOverlap(sha)

    def test_an_untracked_file_where_the_merge_wants_a_directory_is_red(self):
        sha = self.branch("work", {"sub/new.txt": "the branch\n"})
        self.write(self.repo, "sub", "a file, not a directory\n")
        self.assertOverlap(sha)

    def test_a_path_with_a_space_and_an_accent_is_read_unquoted(self):
        name = "a charter \u00e9.txt"
        sha = self.branch("work", {name: "the branch\n"})
        self.write(self.repo, name, "a hand's new file\n")
        self.assertIn('"', self.porcelain())    # git quotes this one in plain porcelain
        self.assertOverlap(sha)

    def test_a_branch_rename_overlaps_on_its_old_path(self):
        sha = self.renamed_branch()
        self.write(self.repo, "shared.txt", "a hand's edit\n")
        self.assertOverlap(sha)

    def test_a_branch_rename_overlaps_on_its_new_path(self):
        sha = self.renamed_branch()
        self.write(self.repo, "moved.txt", "a hand's new file\n")
        self.assertOverlap(sha)

    def test_a_staged_rename_on_main_overlaps_on_its_old_path(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.git("mv", "shared.txt", "kept.txt")
        self.assertIn("R  ", self.porcelain())
        self.assertOverlap(sha)

    def test_a_staged_rename_on_main_overlaps_on_its_new_path(self):
        sha = self.branch("work", {"kept.txt": "the branch\n"})
        self.git("mv", "shared.txt", "kept.txt")
        self.assertOverlap(sha)

    def test_a_conflict_with_unrelated_dirt_aborts_and_keeps_the_dirt(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.on_main("shared.txt", "main\n")
        self.on_main("charter.md", "committed\n")
        self.write(self.repo, "charter.md", "a hand's edit\n")
        self.write(self.repo, "untracked.txt", "and a new file\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "merge")
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(sorted(self.porcelain_lines()), [" M charter.md", "?? untracked.txt"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    def test_main_gone_dirty_on_a_merge_path_during_the_check_is_red_and_untouched(self):
        # The check takes minutes and the main checkout is a sitting's: read it again last.
        tree_make = MAKEFILE + "\t@touch \"%s/new.txt\"\n" % self.repo
        sha = self.branch("work", {"Makefile": tree_make, "new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "main", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), "?? new.txt")
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertEqual(self.ran(), ["check"])

    def test_main_gone_dirty_elsewhere_during_the_check_lands(self):
        tree_make = MAKEFILE + "\t@touch \"%s/late.txt\"\n" % self.repo
        sha = self.branch("work", {"Makefile": tree_make})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(self.porcelain(), "?? late.txt")

    def test_the_named_sha_must_be_the_branch_head(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        tree = self.worktree("work")
        self.write(tree, "more.txt", "more\n")
        self.git("add", "more.txt", cwd=tree)
        self.git("commit", "-qm", "a later commit", cwd=tree)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "sha", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), [])

    def test_a_sha_already_on_main_is_red(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.git("merge", "-q", "--no-ff", "-m", "by hand", sha)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "sha", 1)
        self.assertEqual(self.main_sha(), before)

    def test_a_dirty_worktree_is_red_since_the_check_would_not_prove_the_sha(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.worktree("work"), "uncommitted.txt", "x\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), [])

    def test_a_real_venv_directory_in_the_worktree_is_red_and_stays(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.worktree("work"), ".venv/bin/python", "real\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isfile(os.path.join(self.worktree("work"), ".venv/bin/python")))

    def test_a_venv_link_beside_other_dirt_is_still_red_and_the_link_stays(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        link = os.path.join(self.worktree("work"), ".venv")
        os.symlink(self.tmp, link)
        self.write(self.worktree("work"), "uncommitted.txt", "x\n")
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertTrue(os.path.islink(link))

    def test_a_branch_without_a_worktree_is_red(self):
        tree = self.worktree("work")
        sha = self.branch("work", {"new.txt": "new\n"})
        self.git("worktree", "remove", tree)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.main_sha(), before)

    def test_main_itself_is_not_a_branch_to_land(self):
        sha = self.main_sha()
        p = self.land("main", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.main_sha(), sha)

    def test_a_missing_message_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha, message=os.path.join(self.tmp, "absent"))
        self.assertRed(p, "merge-file", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), [])

    def test_a_repo_that_is_not_the_main_checkout_is_red(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha, repo=self.worktree("work"))
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "land work: red repo exit 1\n")
        self.assertEqual(self.main_sha(), before)

    def test_a_repo_that_is_not_there_or_not_git_is_red(self):
        p = self.land("work", "0" * 40, repo=os.path.join(self.tmp, "absent"))
        self.assertEqual((p.returncode, p.stdout), (1, "land absent: red repo exit 1\n"))
        p = self.land("work", "0" * 40, repo="absent-name")
        self.assertEqual((p.returncode, p.stdout), (1, "land absent-name: red repo exit 1\n"))
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        p = self.land("work", "0" * 40, repo=plain)
        self.assertEqual((p.returncode, p.stdout), (1, "land plain: red repo exit 1\n"))

    def test_a_worktree_that_will_not_go_is_red_and_says_the_merge_stands(self):
        # A hook locks the worktree after the merge, so `worktree remove` refuses it.
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, ".git/hooks/post-merge",
                   "#!/bin/sh\ngit worktree lock \"%s\"\n" % self.worktree("work"), 0o755)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "remove")
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertEqual(self.git("rev-parse", "main^1"), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertIn("merged", p.stderr)
        self.assertEqual(self.git("rev-parse", "work"), sha)

    def test_a_branch_that_will_not_go_is_red_and_the_merge_stands(self):
        # A hook refuses this one ref's deletion, so `branch -d` is the step that fails.
        self.write(self.repo, ".git/hooks/reference-transaction", (
            "#!/bin/sh\n"
            "[ \"$1\" = prepared ] || exit 0\n"
            "while read -r old new ref; do\n"
            "  case \"$ref $new\" in\n"
            "    \"refs/heads/work 0000000000000000000000000000000000000000\") exit 1;;\n"
            "  esac\n"
            "done\n"), 0o755)
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "branch")
        self.assertEqual(self.git("rev-parse", "main^1"), before)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertFalse(os.path.exists(self.worktree("work")))
        self.assertEqual(self.git("rev-parse", "work"), sha)
        self.assertIn("merged", p.stderr)

    def test_usage_is_exit_two(self):
        p = subprocess.run([*LAND, self.repo], cwd=self.repo, env=self.env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, "land ?: red usage exit 2\n")


class TestAmendment2(LandCase):
    """Refuter round 1's findings, F1 to F11 and the observations, each with its repro."""

    def stopped(self, *args):
        p = subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertNotEqual(p.returncode, 0, args)

    def side_that_conflicts(self):
        self.git("checkout", "-q", "-b", "side")
        self.write(self.repo, "shared.txt", "side\n")
        self.git("commit", "-qam", "side")
        self.git("checkout", "-q", "main")
        self.on_main("shared.txt", "main\n")

    def git_wrapped(self, arms):
        """An env whose `git` first runs these `case` arms on "$1 $2", $REAL the real one."""
        bindir = os.path.join(self.tmp, "wrapped")
        self.write(bindir, "git", '#!/bin/sh\nREAL=%s\ncase "$1 $2" in\n%s\nesac\nexec "$REAL" "$@"\n'
                   % (shutil.which("git", path=self.env["PATH"]), arms), 0o755)
        env = dict(self.env)
        env["PATH"] = bindir + os.pathsep + env["PATH"]
        return env

    def exists_on_main(self, name):
        return os.path.lexists(os.path.join(self.repo, name))

    def read_main(self, name):
        with open(os.path.join(self.repo, name)) as fh:
            return fh.read()

    def assertNothingMoved(self, p, before, step="main", ran=()):
        self.assertRed(p, step, 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), list(ran))

    # F1: a merge, a pick, a revert or a rebase in progress on main is someone's.

    def test_f1_a_merge_in_progress_on_main_is_red_and_stands(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.side_that_conflicts()
        self.stopped("merge", "side")
        self.write(self.repo, "shared.txt", "resolved by a hand\n")
        self.git("add", "shared.txt")
        theirs, before = self.git("rev-parse", "MERGE_HEAD"), self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertIn("MERGE_HEAD", p.stderr)
        self.assertEqual(self.git("rev-parse", "MERGE_HEAD"), theirs)
        self.assertEqual(self.read_main("shared.txt"), "resolved by a hand\n")

    def test_f1_a_cherry_pick_in_progress_on_main_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.side_that_conflicts()
        self.stopped("cherry-pick", "side")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertIn("CHERRY_PICK_HEAD", p.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".git", "CHERRY_PICK_HEAD")))

    def test_f1_a_revert_in_progress_on_main_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.on_main("shared.txt", "one\n")
        self.on_main("shared.txt", "two\n")
        self.stopped("revert", "--no-edit", "main~1")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertIn("REVERT_HEAD", p.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".git", "REVERT_HEAD")))

    def test_f1_a_rebase_in_progress_on_main_is_red_and_names_it(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.side_that_conflicts()
        before = self.main_sha()
        self.stopped("rebase", "side")
        p = self.land("work", sha)
        self.assertRed(p, "main", 1)
        self.assertIn("rebase-merge", p.stderr)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.ran(), [])
        self.assertTrue(os.path.isdir(os.path.join(self.repo, ".git", "rebase-merge")))

    def test_f1_a_merge_begun_on_main_during_the_check_is_red_and_stands(self):
        self.git("checkout", "-q", "-b", "side")
        self.write(self.repo, "side.txt", "side\n")
        self.git("add", "side.txt")
        self.git("commit", "-qm", "side")
        self.git("checkout", "-q", "main")
        sha = self.branch("work", {"new.txt": "new\n", "Makefile": MAKEFILE + (
            "\t@git -C \"%s\" merge -q --no-commit --no-ff side\n" % self.repo)})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, ran=["check"])
        self.assertEqual(self.git("rev-parse", "MERGE_HEAD"), self.git("rev-parse", "side"))

    def test_f1_a_merge_not_begun_by_this_run_is_never_aborted(self):
        # The last read is clean, and a hand's merge arrives in the instant before land's.
        self.git("checkout", "-q", "-b", "side")
        self.write(self.repo, "side.txt", "side\n")
        self.git("add", "side.txt")
        self.git("commit", "-qm", "side")
        self.git("checkout", "-q", "main")
        sha = self.branch("work", {"new.txt": "new\n"})
        env = self.git_wrapped('"merge --no-ff") "$REAL" merge -q --no-commit --no-ff side;;')
        p = self.land("work", sha, env=env)
        self.assertRed(p, "merge", 128)
        self.assertEqual(self.git("rev-parse", "MERGE_HEAD"), self.git("rev-parse", "side"))
        self.assertTrue(self.exists_on_main("side.txt"))

    # F2: an ignored file is a file.

    def test_f2_an_ignored_file_the_merge_would_create_is_red_and_kept(self):
        self.on_main(".gitignore", ".claude/worktrees/\nbuild.out\n")
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.write(tree, "build.out", "the branch's\n")
        self.git("add", "-f", "build.out", cwd=tree)
        self.git("commit", "-qm", "forced", cwd=tree)
        sha = self.git("rev-parse", "HEAD", cwd=tree)
        self.write(self.repo, "build.out", "PRECIOUS\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertEqual(self.read_main("build.out"), "PRECIOUS\n")

    def test_f2_an_ignored_file_a_branch_starts_to_track_is_red_and_kept(self):
        self.on_main(".gitignore", ".claude/worktrees/\nlocal.env\n")
        sha = self.branch("work", {".gitignore": ".claude/worktrees/\n", "local.env": "tracked\n"})
        self.write(self.repo, "local.env", "SECRET\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertEqual(self.read_main("local.env"), "SECRET\n")

    def test_f2_an_ignored_file_where_the_merge_wants_a_directory_is_red_and_kept(self):
        self.on_main(".gitignore", ".claude/worktrees/\nlocal\n")
        sha = self.branch("work", {".gitignore": ".claude/worktrees/\n", "local/x.txt": "x\n"})
        self.write(self.repo, "local", "KEEP\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertEqual(self.read_main("local"), "KEEP\n")

    def test_f2_an_ignored_file_found_after_the_check_is_red_and_kept(self):
        self.on_main(".gitignore", ".claude/worktrees/\nlocal.env\n")
        sha = self.branch("work", {".gitignore": ".claude/worktrees/\n", "local.env": "tracked\n",
                                   "Makefile": MAKEFILE + (
                                       "\t@echo SECRET > \"%s/local.env\"\n" % self.repo)})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, ran=["check"])
        self.assertEqual(self.read_main("local.env"), "SECRET\n")

    def test_f2_an_ignored_file_beside_the_merges_paths_lands_and_stays(self):
        self.on_main(".gitignore", ".claude/worktrees/\nbuild/\n")
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.write(tree, "build/b", "the branch's\n")
        self.git("add", "-f", "build/b", cwd=tree)
        self.git("commit", "-qm", "forced", cwd=tree)
        sha = self.git("rev-parse", "HEAD", cwd=tree)
        self.write(self.repo, "build/a", "stays\n")
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.read_main("build/a"), "stays\n")
        self.assertEqual(self.read_main("build/b"), "the branch's\n")

    # F3: the status reads never follow the repo's config.

    def test_f3_status_config_hides_no_untracked_work_in_the_worktree(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.git("config", "status.showUntrackedFiles", "no")
        self.write(self.worktree("work"), "precious.txt", "WORK\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, step="worktree")
        self.assertTrue(os.path.exists(os.path.join(self.worktree("work"), "precious.txt")))

    def test_f3_every_status_read_passes_its_own_flags(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        log = os.path.join(self.tmp, "status.log")
        env = self.git_wrapped('"status --porcelain") echo "$*" >> "%s";;' % log)
        p = self.land("work", sha, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(log) as fh:
            lines = fh.read().splitlines()
        self.assertGreaterEqual(len(lines), 3)    # main twice, the worktree at least once
        for line in lines:
            self.assertIn("--untracked-files=all", line)
            self.assertIn("--ignore-submodules=none", line)

    # F4: a cut, by the gate's own signal to the whole group.

    def cut_at(self, sha, up, during=None):
        p = subprocess.Popen([*LAND, self.repo, "work", sha, self.message], cwd=self.repo,
                             env=self.env, text=True, start_new_session=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(p.wait)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        for _ in range(1200):
            if os.path.exists(up) or p.poll() is not None:
                break
            time.sleep(0.05)
        self.assertIsNone(p.poll(), "land ended before the cut")
        if during:
            during()
        os.killpg(p.pid, signal.SIGTERM)
        out, err = p.communicate(timeout=30)
        return p.returncode, out, err

    def hook_that_stalls(self, hook):
        up = os.path.join(self.tmp, "up")
        self.write(self.repo, ".git/hooks/" + hook, "#!/bin/sh\ntouch \"%s\"\nsleep 60\n" % up, 0o755)
        return up

    def assertCutAndClean(self, hook):
        sha = self.branch("work", {"new.txt": "new\n"})
        up = self.hook_that_stalls(hook)
        before = self.main_sha()
        code, out, err = self.cut_at(sha, up)
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124\n"), err)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), "")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "index.lock")))
        os.unlink(os.path.join(self.repo, ".git", "hooks", hook))
        self.assertEqual(self.land("work", sha).returncode, 0)

    def test_f4_a_cut_in_pre_merge_commit_aborts_this_runs_merge(self):
        self.assertCutAndClean("pre-merge-commit")

    def test_f4_a_cut_in_prepare_commit_msg_aborts_this_runs_merge(self):
        self.assertCutAndClean("prepare-commit-msg")

    def test_f4_a_cut_during_the_check_leaves_main_and_says_cut(self):
        up = os.path.join(self.tmp, "up")
        sha = self.branch("work", {"new.txt": "new\n", "Makefile": (
            "check:\n\t@touch \"%s\"\n\t@sleep 60\n" % up)})
        before = self.main_sha()
        code, out, err = self.cut_at(sha, up)
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124\n"), err)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))

    def test_f4_a_cut_after_the_commit_says_the_merge_stands(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        up = self.hook_that_stalls("post-merge")
        code, out, err = self.cut_at(sha, up)
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124\n"), err)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertEqual(self.porcelain(), "")
        self.assertIn("the merge stands", err)

    # F5: any error is a land line.

    def assertNoTraceback(self, p):
        self.assertNotIn("Traceback", p.stderr)

    def test_f5_a_hygiene_git_cannot_exec_is_a_land_line(self):
        sha = self.branch("work", {"scripts/hygiene": "exit 0\n"})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "hygiene", 1)
        self.assertNoTraceback(p)
        self.assertEqual(self.main_sha(), before)

    def test_f5_a_worktree_that_cannot_be_read_is_a_land_line(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        tree = self.worktree("work")
        os.chmod(tree, 0)
        self.addCleanup(os.chmod, tree, 0o755)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertNoTraceback(p)
        self.assertEqual(self.main_sha(), before)

    def test_f5_a_repo_that_cannot_be_read_is_a_land_line(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        os.chmod(self.repo, 0)
        self.addCleanup(os.chmod, self.repo, 0o755)
        p = self.land("work", sha, cwd=self.tmp)
        self.assertRed(p, "repo", 1)
        self.assertNoTraceback(p)

    def test_f5_the_line_never_fails_on_encoding(self):
        self.new_repo("rél")
        sha = self.branch("work", {"new.txt": "new\n"})
        env = dict(self.env, PYTHONIOENCODING="ascii")
        p = subprocess.run([*LAND, self.repo, "work", sha, self.message], cwd=self.repo, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((p.returncode, p.stdout),
                         (0, b"land r\\xe9l: ok " + sha.encode() + b", main readied\n"), p.stderr)

    # F6.

    def test_f6_a_dangling_hygiene_link_runs_and_goes_red(self):
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        os.makedirs(os.path.join(tree, "scripts"))
        os.symlink("/nonexistent-hygiene", os.path.join(tree, "scripts", "hygiene"))
        self.git("add", "scripts/hygiene", cwd=tree)
        self.git("commit", "-qm", "link", cwd=tree)
        before = self.main_sha()
        p = self.land("work", self.git("rev-parse", "HEAD", cwd=tree))
        self.assertRed(p, "hygiene", 127)
        self.assertEqual(self.main_sha(), before)

    # F7.

    def test_f7_an_inherited_makeflags_never_turns_a_red_check_green(self):
        sha = self.branch("work", {"RED": "red\n"})
        before = self.main_sha()
        p = self.land("work", sha, env=dict(self.env, MAKEFLAGS="n"))
        self.assertRed(p, "check", 2)
        self.assertEqual(self.main_sha(), before)

    def test_f7_the_checks_env_drops_makes_four_variables(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        seen = os.path.join(self.tmp, "seen-env")
        bindir = os.path.join(self.tmp, "fake-make")
        self.write(bindir, "make", "#!/bin/sh\nenv > \"%s\"\n" % seen, 0o755)
        env = dict(self.env, PATH=bindir + os.pathsep + self.env["PATH"], MAKEFLAGS="n",
                   MFLAGS="-n", GNUMAKEFLAGS="-n", MAKELEVEL="3")
        p = self.land("work", sha, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(seen) as fh:
            names = {line.split("=", 1)[0] for line in fh}
        self.assertEqual(names & {"MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"}, set())

    # F8.

    def on_a_branch_cut_from_origin_main(self):
        bare = os.path.join(self.tmp, "origin.git")
        self.git("clone", "-q", "--bare", self.repo, bare)
        self.git("remote", "add", "origin", bare)
        self.git("fetch", "-q", "origin")
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "origin/main")
        self.write(tree, "new.txt", "new\n")
        self.git("add", "new.txt", cwd=tree)
        self.git("commit", "-qm", "work", cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def test_f8_a_branch_that_tracks_origin_main_goes_after_a_good_landing(self):
        sha = self.on_a_branch_cut_from_origin_main()
        p = self.land("work", sha)
        self.assertEqual((p.returncode, p.stdout),
                         (0, "land scratch: ok %s, main readied\n" % sha), p.stderr)
        self.assertEqual(self.git("branch", "--list", "work"), "")
        self.assertEqual(self.git("rev-parse", "main^2"), sha)

    def test_f8_a_sha_no_longer_on_main_keeps_the_branch(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        env = self.git_wrapped('"worktree remove") "$REAL" "$@" || exit $?; '
                               '"$REAL" reset -q --hard HEAD~1; exit 0;;')
        p = self.land("work", sha, env=env)
        self.assertRed(p, "branch", 1)
        self.assertEqual(self.git("rev-parse", "work"), sha)

    def test_f8_a_branch_that_moved_after_the_merge_keeps_its_new_commit(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        moved = self.git("commit-tree", "HEAD^{tree}", "-p", sha, "-m", "later")
        env = self.git_wrapped('"worktree remove") "$REAL" "$@" || exit $?; '
                               '"$REAL" update-ref refs/heads/work %s; exit 0;;' % moved)
        p = self.land("work", sha, env=env)
        self.assertRed(p, "branch", 1)
        self.assertEqual(self.git("rev-parse", "work"), moved)

    # F9.

    def test_f9_an_unrelated_staged_path_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, "staged.txt", "s\n")
        self.git("add", "staged.txt")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertEqual(self.porcelain(), "A  staged.txt")
        self.assertIn("staged.txt", p.stderr)

    def test_f9_a_path_staged_during_the_check_is_red_before_the_merge(self):
        sha = self.branch("work", {"new.txt": "new\n", "Makefile": MAKEFILE + (
            "\t@echo s > \"{0}/staged.txt\"\n\t@git -C \"{0}\" add staged.txt\n".format(self.repo))})
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, ran=["check"])
        self.assertEqual(self.porcelain(), "A  staged.txt")

    # F10: the worktree, read again before main moves.

    def assertCheckLeavesItRed(self, recipe):
        link = os.path.join(self.worktree("work"), ".venv")
        sha = self.branch("work", {"new.txt": "new\n", "Makefile": MAKEFILE + recipe})
        os.symlink(self.tmp, link)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, step="worktree", ran=["check"])
        self.assertTrue(os.path.isdir(self.worktree("work")))
        return link

    def test_f10_a_check_that_litters_is_red_before_main_moves(self):
        link = self.assertCheckLeavesItRed("\t@echo x > out.gen\n")
        self.assertTrue(os.path.islink(link))

    def test_f10_a_check_that_edits_a_tracked_file_is_red_before_main_moves(self):
        link = self.assertCheckLeavesItRed("\t@echo x >> shared.txt\n")
        self.assertTrue(os.path.islink(link))

    def test_f10_a_check_that_locks_the_worktree_is_red_and_the_link_stays(self):
        link = self.assertCheckLeavesItRed("\t@git worktree lock --reason busy \"$$PWD\"\n")
        self.assertTrue(os.path.islink(link))

    def test_f10_a_venv_gone_real_during_the_check_is_red_before_main_moves(self):
        link = self.assertCheckLeavesItRed("\t@rm .venv; echo x > .venv\n")
        self.assertFalse(os.path.islink(link))

    def test_f10_a_locked_worktree_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        link = os.path.join(self.worktree("work"), ".venv")
        os.symlink(self.tmp, link)
        self.git("worktree", "lock", self.worktree("work"))
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, step="worktree")
        self.assertTrue(os.path.islink(link))

    def test_f10_a_regular_file_venv_is_red_before_the_check(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.worktree("work"), ".venv", "a file\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, step="worktree")

    # F11: the merge's exit is not its proof.

    def test_f11_branch_mergeoptions_no_commit_still_commits(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.git("config", "branch.main.mergeoptions", "--no-commit")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.git("rev-parse", "main^1"), before)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)

    def test_f11_a_merge_that_exits_0_and_moves_nothing_is_red(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha, env=self.git_wrapped('"merge --no-ff") exit 0;;'))
        self.assertRed(p, "merge", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.git("rev-parse", "work"), sha)
        self.assertTrue(os.path.isdir(self.worktree("work")))

    def test_f11_a_merge_that_exits_0_and_leaves_merge_head_is_aborted_and_red(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        env = self.git_wrapped('"merge --no-ff") "$REAL" merge -q --no-ff --no-commit %s; exit 0;;'
                               % sha)
        p = self.land("work", sha, env=env)
        self.assertRed(p, "merge", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), "")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    def test_f11_an_abort_that_fails_is_said_and_stays_loud_on_a_retry(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        lock = os.path.join(self.repo, ".git", "index.lock")
        self.write(self.repo, ".git/hooks/pre-merge-commit",
                   "#!/bin/sh\ntouch \"%s\"\nexit 1\n" % lock, 0o755)
        p = self.land("work", sha)
        self.assertRed(p, "merge", 1)
        self.assertIn("land-step: git merge --abort exit", p.stderr)
        os.unlink(lock)
        p = self.land("work", sha)
        self.assertRed(p, "main", 1)
        self.assertIn("MERGE_HEAD", p.stderr)

    # The observations.

    def test_obs_a_branch_name_is_not_a_sha(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        self.assertNothingMoved(self.land("work", "work"), before, step="sha")
        self.git("tag", "abcd", sha)
        self.assertNothingMoved(self.land("work", "abcd"), before, step="sha")

    def test_obs_a_bare_name_never_resolves_in_the_cwd(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        before = self.main_sha()
        p = self.land("work", sha, repo="scratch", cwd=self.tmp)
        self.assertRed(p, "repo", 1)
        self.assertEqual(self.main_sha(), before)

    def test_obs_a_name_with_a_slash_is_a_path(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        p = self.land("work", sha, repo="./scratch", cwd=self.tmp)
        self.assertEqual(p.returncode, 0, p.stderr)


class TestAmendment3(LandCase):
    """Refuter round 2's findings F1 to F4 and F6, each with its probe case named."""

    cut_at = TestAmendment2.cut_at
    hook_that_stalls = TestAmendment2.hook_that_stalls
    git_wrapped = TestAmendment2.git_wrapped
    read_main = TestAmendment2.read_main
    exists_on_main = TestAmendment2.exists_on_main

    # F1: a cut undoes this run's merge and nothing else (p7 Q1, Q2).

    def charter_on_main(self):
        self.on_main("charter.md", "chart0\n")
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.write(tree, "new.txt", "new\n")
        self.git("add", "new.txt", cwd=tree)
        self.git("commit", "-qm", "the work", cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def stage_on_main(self, name, text):
        def during():
            self.write(self.repo, name, text)
            self.git("add", name)
        return during

    def test_f1_q1_a_path_staged_during_post_merge_stays_and_the_merge_stands(self):
        sha = self.charter_on_main()
        up = self.hook_that_stalls("post-merge")
        code, out, err = self.cut_at(sha, up, self.stage_on_main("charter.md", "EDIT\n"))
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124, staged paths left on main\n"), err)
        self.assertEqual(self.read_main("charter.md"), "EDIT\n")
        self.assertEqual(self.porcelain_lines(), ["M  charter.md"])
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertIn("the merge stands", err)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    def assertSiblingKept(self, hook, staged_lines):
        sha = self.charter_on_main()
        up = self.hook_that_stalls(hook)
        before = self.main_sha()
        code, out, err = self.cut_at(sha, up, self.stage_on_main("charter.md", "EDIT\n"))
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124, staged paths left on main\n"), err)
        self.assertEqual(self.read_main("charter.md"), "EDIT\n")
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(sorted(self.porcelain_lines()), staged_lines)
        self.assertIn("charter.md", err)
        os.unlink(os.path.join(self.repo, ".git", "hooks", hook))
        self.assertRed(self.land("work", sha), "main", 1)     # the retry is loud
        self.assertEqual(self.read_main("charter.md"), "EDIT\n")

    def test_f1_q2_a_path_staged_during_pre_merge_commit_stays_and_the_retry_is_red(self):
        self.assertSiblingKept("pre-merge-commit", ["A  new.txt", "M  charter.md"])

    def test_f1_the_same_with_a_merge_head_in_prepare_commit_msg(self):
        self.assertSiblingKept("prepare-commit-msg", ["A  new.txt", "M  charter.md"])

    def test_f1_a_merge_path_staged_with_other_content_during_the_hook_stays(self):
        sha = self.charter_on_main()
        up = self.hook_that_stalls("pre-merge-commit")
        code, out, err = self.cut_at(sha, up, self.stage_on_main("new.txt", "A HAND'S EDIT\n"))
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124, staged paths left on main\n"), err)
        self.assertEqual(self.read_main("new.txt"), "A HAND'S EDIT\n")

    def test_f1_an_intent_to_add_during_the_hook_stays(self):
        sha = self.charter_on_main()
        up = self.hook_that_stalls("pre-merge-commit")

        def during():
            self.write(self.repo, "ita.txt", "wip\n")
            self.git("add", "-N", "ita.txt")
        code, out, err = self.cut_at(sha, up, during)
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124, staged paths left on main\n"), err)
        self.assertEqual(self.read_main("ita.txt"), "wip\n")

    def test_f1_q2b_a_cut_with_only_the_merge_staged_still_goes_and_keeps_the_dirt(self):
        sha = self.charter_on_main()
        up = self.hook_that_stalls("pre-merge-commit")
        before = self.main_sha()
        self.write(self.repo, "charter.md", "dirt\n")
        self.write(self.repo, "un.txt", "un\n")
        self.write(self.repo, ".git/info/exclude", "ign.txt\n")
        self.write(self.repo, "ign.txt", "kept\n")
        code, out, err = self.cut_at(sha, up)
        self.assertEqual((code, out), (124, "land scratch: red cut exit 124\n"), err)
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(sorted(self.porcelain_lines()), [" M charter.md", "?? un.txt"])
        self.assertEqual(self.read_main("charter.md"), "dirt\n")
        self.assertEqual(self.read_main("ign.txt"), "kept\n")
        self.assertFalse(self.exists_on_main("new.txt"))

    def test_f1_a_conflict_only_git_merge_finds_is_still_aborted(self):
        """merge-tree reads clean here by a wrapper, so the conflict reaches git merge. The
        modify/delete is the hard shape: its path equals main in the result tree."""
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.write(self.repo, "shared.txt", "main\n")
        self.git("commit", "-qam", "main")
        tree = self.git("rev-parse", "main^{tree}")
        env = self.git_wrapped('"merge-tree --write-tree") case "$*" in *refs/heads/main*) '
                               'printf "%%s\\0" %s; exit 0;; esac;;' % tree)
        before = self.main_sha()
        p = self.land("work", sha, env=env)
        self.assertRed(p, "merge", 1)
        self.assertEqual(self.ran(), ["check"])
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), "")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    # F2: a directory stands only if it holds a path not tracked at main.

    def tree_on_main(self):
        self.write(self.repo, ".gitignore", ".claude/worktrees/\n*.ign\n")
        self.write(self.repo, "dir/a", "a\n")
        self.write(self.repo, "dir/b", "b\n")
        self.write(self.repo, "dir/sub/c", "c\n")
        self.git("add", ".gitignore", "dir")
        self.git("commit", "-qm", "a tree")

    def branch_replacing_dir(self, link=False):
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.git("rm", "-rq", "dir", cwd=tree)
        if link:
            os.symlink("shared.txt", os.path.join(tree, "dir"))
        else:
            self.write(tree, "dir", "a file now\n")
        self.git("add", "dir", cwd=tree)
        self.git("commit", "-qm", "dir goes", cwd=tree)
        return self.git("rev-parse", "HEAD", cwd=tree)

    def test_f2_o2_a_tracked_directory_replaced_by_a_file_lands(self):
        self.tree_on_main()
        sha = self.branch_replacing_dir()
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.read_main("dir"), "a file now\n")

    def test_f2_o5_a_tracked_directory_replaced_by_a_link_lands(self):
        self.tree_on_main()
        sha = self.branch_replacing_dir(link=True)
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(os.path.islink(os.path.join(self.repo, "dir")))

    def test_f2_o13_an_empty_directory_where_the_merge_writes_a_file_lands(self):
        sha = self.branch("work", {"e": "a file\n"})
        os.makedirs(os.path.join(self.repo, "e", "nested"))
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.read_main("e"), "a file\n")

    def assertDirStands(self, name, text=None, link=None):
        self.tree_on_main()
        sha = self.branch_replacing_dir()
        before = self.main_sha()
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if link:
            os.symlink(link, path)
        else:
            self.write(self.repo, name, text)
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertTrue(os.path.lexists(path))

    assertNothingMoved = TestAmendment2.assertNothingMoved

    def test_f2_an_ignored_file_in_that_directory_stands_and_is_kept(self):
        self.assertDirStands("dir/k.ign", "precious\n")
        self.assertEqual(self.read_main("dir/k.ign"), "precious\n")

    def test_f2_an_ignored_file_deep_in_that_directory_stands_and_is_kept(self):
        self.assertDirStands("dir/sub/deep/k.ign", "precious\n")
        self.assertEqual(self.read_main("dir/sub/deep/k.ign"), "precious\n")

    def test_f2_an_ignored_link_in_that_directory_stands_and_is_kept(self):
        self.assertDirStands("dir/l.ign", link="/nowhere")

    # F3: the written paths are the merge's own, from merge-tree (p7 O11, p8 D3, D4).

    def dir_renamed_on_main(self, name, config=None):
        self.tree_on_main()
        if config:
            self.git("config", "merge.directoryRenames", config)
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "-b", "work", tree, "main")
        self.write(tree, "dir/" + name, "the branch\n")
        self.git("add", "-f", "dir/" + name, cwd=tree)
        self.git("commit", "-qm", "adds in dir", cwd=tree)
        self.git("mv", "dir", "moved")
        self.git("commit", "-qm", "main renames dir")
        self.write(self.repo, "moved/" + name, "PRECIOUS\n")
        return self.git("rev-parse", "HEAD", cwd=tree)

    def test_f3_o11_a_rename_conflict_is_red_merge_before_the_check_and_the_file_is_kept(self):
        sha = self.dir_renamed_on_main("new.ign")
        before = self.main_sha()
        self.assertNothingMoved(self.land("work", sha), before, step="merge")
        self.assertEqual(self.read_main("moved/new.ign"), "PRECIOUS\n")

    def test_f3_d3_an_ignored_file_at_a_rename_target_is_red_main_and_kept(self):
        sha = self.dir_renamed_on_main("new.ign", "true")
        before = self.main_sha()
        self.assertNothingMoved(self.land("work", sha), before)
        self.assertEqual(self.read_main("moved/new.ign"), "PRECIOUS\n")
        self.assertEqual(self.git("rev-parse", "work"), sha)

    def test_f3_d4_an_untracked_file_at_a_rename_target_is_red_main_and_kept(self):
        sha = self.dir_renamed_on_main("new.txt", "true")
        before = self.main_sha()
        self.assertNothingMoved(self.land("work", sha), before)
        self.assertEqual(self.read_main("moved/new.txt"), "PRECIOUS\n")

    def test_f3_a_plain_conflict_is_red_merge_before_the_check(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        self.on_main("shared.txt", "main\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before, step="merge")
        self.assertIn("shared.txt", p.stderr)
        self.assertEqual(self.porcelain(), "")

    def test_f3_a_conflict_main_grows_during_the_check_is_red_merge_after_it(self):
        sha = self.branch("work", {"shared.txt": "the branch\n"})
        tree = self.worktree("work")
        # The check commits on main: a hand on the same checkout, while the minutes pass.
        code = ("#!/bin/sh\necho main > \"%s/shared.txt\"\n"
                "git -C \"%s\" commit -qam moved\n" % (self.repo, self.repo))
        hand = self.write(self.tmp, "hand", code, 0o755)
        self.write(tree, "Makefile", "check:\n\t@echo check >> \"$$LAND_ORDER\"\n\t@%s\n" % hand)
        self.git("add", "Makefile", cwd=tree)
        self.git("commit", "-qm", "a check with a hand in it", cwd=tree)
        sha = self.git("rev-parse", "HEAD", cwd=tree)
        p = self.land("work", sha)
        self.assertRed(p, "merge", 1)
        self.assertEqual(self.ran(), ["check"])
        self.assertEqual(self.porcelain(), "")
        self.assertEqual(self.read_main("shared.txt"), "main\n")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    def test_f3_unrelated_histories_are_red_merge_before_the_check(self):
        tree = self.worktree("work")
        self.git("worktree", "add", "-q", "--orphan", "-b", "work", tree)
        self.write(tree, "Makefile", MAKEFILE)
        self.git("add", "Makefile", cwd=tree)
        self.git("commit", "-qm", "no shared history", cwd=tree)
        sha = self.git("rev-parse", "HEAD", cwd=tree)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "merge", 128)
        self.assertEqual(self.ran(), [])
        self.assertEqual(self.main_sha(), before)
        self.assertIn("git merge-tree exit 128", p.stderr)

    def test_f3_merge_tree_touches_neither_the_index_nor_the_worktree(self):
        """The ruling's premise, on clean and conflicted merges alike."""
        def snapshot():
            index = os.path.join(self.repo, ".git", "index")
            with open(index, "rb") as fh:
                data = fh.read()
            found = {}
            for where, dirs, files in os.walk(self.repo):
                dirs[:] = [d for d in dirs if d != ".git"]
                for name in files:
                    full = os.path.join(where, name)
                    with open(full, "rb") as fh:
                        found[full] = (fh.read(), os.stat(full).st_mtime_ns)
            return data, os.stat(index).st_mtime_ns, found
        clean = self.branch("clean", {"new.txt": "new\n"})
        conflict = self.branch("clash", {"shared.txt": "the branch\n"})
        self.write(self.repo, "shared.txt", "main\n")
        self.git("commit", "-qam", "main")
        self.git("status", "--porcelain")
        before = snapshot()
        self.git("merge-tree", "--write-tree", "--no-messages", "main", clean)
        p = subprocess.run(["git", "merge-tree", "--write-tree", "--no-messages", "main", conflict],
                           cwd=self.repo, env=self.env, stdout=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(snapshot(), before)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))

    def test_the_common_path_lands_with_a_venv_link_and_ignored_caches(self):
        """agentik-session's shape: both ignore patterns, the check writes its caches."""
        for pattern in (".venv/", ".venv"):
            with self.subTest(pattern=pattern):
                name = "w" + str(len(pattern))
                target = os.path.join(self.tmp, "venv" + name)
                self.write(target, "keep", "k\n")
                sha = self.branch(name, {
                    "ign/" + name: "x\n",
                    ".gitignore": ".claude/worktrees/\n__pycache__/\ndist/\n%s\n" % pattern,
                    "Makefile": ("check:\n\t@mkdir -p __pycache__ sub/__pycache__ .pytest_cache "
                                 ".ruff_cache dist\n\t@echo x > __pycache__/a.pyc\n"
                                 "\t@echo x > sub/__pycache__/b.pyc\n"
                                 "\t@echo '*' > .pytest_cache/.gitignore\n"
                                 "\t@echo '*' > .ruff_cache/.gitignore\n"
                                 "\t@echo x > .ruff_cache/c\n\t@echo x > dist/o\n")})
                tree = self.worktree(name)
                os.symlink(target, os.path.join(tree, ".venv"))
                p = self.land(name, sha)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
                self.assertEqual(self.git("rev-parse", "main^2"), sha)
                self.assertFalse(os.path.exists(tree))
                self.assertTrue(os.path.exists(os.path.join(target, "keep")))
                self.assertEqual(self.porcelain(), "")

    # F4: an intent-to-add is staged, though diff --cached does not see it (p7 O12).

    def test_f4_o12_an_intent_to_add_on_main_is_red_before_the_check_and_kept(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, "ita.txt", "wip\n")
        self.git("add", "-N", "ita.txt")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertNothingMoved(p, before)
        self.assertIn("ita.txt", p.stderr)
        self.assertEqual(self.porcelain_lines(), [" A ita.txt"])
        self.assertEqual(self.read_main("ita.txt"), "wip\n")

    def test_f4_an_intent_to_add_that_status_calls_a_rename_is_red_too(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        os.rename(os.path.join(self.repo, "shared.txt"), os.path.join(self.repo, "other.txt"))
        self.git("add", "-N", "other.txt")
        self.assertEqual(self.porcelain_lines(), [" R shared.txt -> other.txt"])
        before = self.main_sha()
        self.assertNothingMoved(self.land("work", sha), before)

    # F6: the docstring (p7 Q7, p8 U1).

    def docstring(self):
        with open(LAND_PY) as fh:
            return " ".join(fh.read().split('"""')[1].split())

    def test_f6_q7_a_merge_killed_after_its_commit_is_red_merge_and_the_docstring_says_it_stands(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        self.write(self.repo, ".git/hooks/post-merge", "#!/bin/sh\nkill -9 $PPID\n", 0o755)
        p = self.land("work", sha)
        self.assertRed(p, "merge", 137)
        self.assertIn("the merge stands", p.stderr)
        self.assertEqual(self.git("rev-parse", "main^2"), sha)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))
        self.assertEqual(self.porcelain(), "")
        self.assertNotIn("a `merge` red is one of those:", self.docstring())
        self.assertIn("killed after its commit", self.docstring())

    def usage(self):
        return subprocess.run(LAND, env=self.env, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)

    def test_f6_u1_the_docstring_says_usage_is_2(self):
        p = self.usage()
        self.assertEqual((p.returncode, p.stdout), (2, "land ?: red usage exit 2\n"))
        self.assertNotIn("A check of its own reports 1;", self.docstring())
        self.assertIn("Usage reports 2", self.docstring())


class TestGate(LandCase):
    """(d): through `agentik session gate run`, in a queue under this test's own state root."""

    WAIT = "600"    # past any load ceiling the queue may wait on

    def agentik(self, *args):
        return subprocess.run([sys.executable, RUNNER, "gate", *args], cwd=self.tmp, env=self.env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def through_the_gate(self, branch, sha, *run_args):
        p = self.agentik("run", self.repo, *run_args, "--", *LAND, self.repo, branch, sha,
                         self.message)
        self.assertEqual(p.returncode, 0, p.stderr)
        gid = re.search(r"\b\d{8}-\d{6}-\d+\b", p.stdout).group(0)
        w = self.agentik("wait", gid, "--timeout", self.WAIT)
        self.assertEqual(w.returncode, 0, w.stderr + w.stdout)
        line = w.stdout.strip()
        found = re.search(r": exit (\d+) in .*; log (\S+)$", line)
        self.assertTrue(found, line)
        self.assertTrue(found.group(2).startswith(self.tmp), "the live queue: " + line)
        with open(found.group(2)) as fh:
            log = fh.read().splitlines()
        # The gate closes its own log with `gate <id>: exit <rc> in <s> s`; the job's last line
        # is the one before it.
        self.assertEqual(log[-1].split(":")[0], "gate " + gid)
        job = [ln for ln in log if not ln.startswith("gate %s:" % gid)]
        return int(found.group(1)), job

    def test_d_green_and_red_through_the_gate(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        code, job = self.through_the_gate("work", sha)
        self.assertEqual(code, 0, job)
        self.assertEqual(job[-1], "land scratch: ok %s, main readied" % sha)
        self.assertEqual(sum(ln.startswith("land scratch:") for ln in job), 1)

        before = self.main_sha()
        sha = self.branch("bad", {"RED": "red\n"})
        code, job = self.through_the_gate("bad", sha)
        self.assertEqual(code, 2, job)
        self.assertEqual(job[-1], "land scratch: red check exit 2")
        self.assertEqual(self.main_sha(), before)

    def test_f4_a_wall_cut_in_a_merge_hook_aborts_and_says_cut(self):
        sha = self.branch("work", {"new.txt": "new\n"})
        hook = self.write(self.repo, ".git/hooks/pre-merge-commit", "#!/bin/sh\nsleep 60\n", 0o755)
        before = self.main_sha()
        code, job = self.through_the_gate("work", sha, "--wall", "3")
        self.assertEqual(code, 124, job)
        self.assertEqual(job[-1], "land scratch: red cut exit 124")
        self.assertEqual(self.main_sha(), before)
        self.assertEqual(self.porcelain(), "")
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "MERGE_HEAD")))
        os.unlink(hook)
        self.assertEqual(self.land("work", sha).returncode, 0)


class TestScript(unittest.TestCase):
    def test_e_no_push_in_the_script(self):
        p = subprocess.run(["grep", "-c", "git push", LAND_PY], text=True, stdout=subprocess.PIPE)
        self.assertEqual(p.stdout.strip(), "0")

    def test_the_module_imports_the_standard_library_alone(self):
        with open(LAND_PY) as fh:
            heads = [ln.split()[1] for ln in fh if ln.startswith(("import ", "from "))]
        self.assertEqual(sorted(heads), ["os", "signal", "subprocess", "sys"])


if __name__ == "__main__":
    unittest.main()
