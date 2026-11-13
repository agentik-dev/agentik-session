"""scripts/land's range scan (packet h1, Part B): after the tree scan, `scripts/hygiene
--require-private --commits refs/heads/main..<sha>` in the branch's worktree when the copy names
the flag in its --help; red `hygiene` before the merge; an older copy lands with `, range not
scanned` on the line. The fakes record their arguments; no real scan and no private term here."""

import os
import unittest

from test_land import LandCase

# Every fake writes its whole argv to $LAND_ORDER.argv, one line a call, then its step to
# $LAND_ORDER with the first argument past --require-private.
RECORD = "#!/bin/sh\necho \"$*\" >> \"$LAND_ORDER.argv\"\n"
# A copy that knows the flag: --help names it; the range scan exits with the given code.
# land2 R4: the merge message's scan, a range <sha>..<commit>, is in the argv alone and passes.
NEW = (RECORD + "[ \"$1\" = --require-private ] && shift\n"
       "case $2 in refs/heads/main..*|'') ;; *) exit 0 ;; esac\n"
       "echo \"hygiene${1:+ $1}\" >> \"$LAND_ORDER\"\n"
       "case $1 in --help) echo 'usage: hygiene [--json] [--commits RANGE]'; exit 0 ;;\n"
       "--commits) echo \"$2\" > \"$LAND_ORDER.range\"; exit %d ;; esac\nexit 0\n")
# A copy from before the flag: its --help names no --commits.
OLD = (RECORD + "echo \"hygiene${1:+ $1}\" >> \"$LAND_ORDER\"\n"
       "case $1 in --help) echo 'usage: hygiene [--json]'; exit 0 ;; --commits) exit 2 ;; esac\n"
       "exit 0\n")


class TestRange(LandCase):
    def argv(self):
        path = self.order + ".argv"
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return fh.read().splitlines()

    def test_r1_the_range_is_scanned_after_the_tree_and_lands(self):
        before = self.main_sha()
        sha = self.branch("work", {"scripts/hygiene": NEW % 0})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        # land2 R4: --help before the check and after the range, for the message's scan.
        self.assertEqual(self.ran(), ["hygiene", "--help", "check", "hygiene", "hygiene", "--help",
                                      "hygiene", "--commits", "hygiene", "--help"])
        with open(self.order + ".range") as fh:
            self.assertEqual(fh.read().strip(), "refs/heads/main..%s" % sha)
        self.assertEqual(self.git("rev-list", "--parents", "-n1", "main").split()[1:],
                         [before, sha])

    def test_r2_a_hit_in_the_range_is_red_hygiene_before_the_merge(self):
        before = self.main_sha()
        sha = self.branch("work", {"scripts/hygiene": NEW % 1})
        p = self.land("work", sha)
        self.assertRed(p, "hygiene", 1)
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(self.worktree("work")))
        self.assertEqual(self.ran()[-2:], ["hygiene", "--commits"])

    def test_r3_a_git_failure_in_the_range_is_red_with_its_code(self):
        sha = self.branch("work", {"scripts/hygiene": NEW % 2})
        p = self.land("work", sha)
        self.assertRed(p, "hygiene", 2)

    def test_r4_an_older_copy_lands_and_says_the_range_was_not_scanned(self):
        sha = self.branch("work", {"scripts/hygiene": OLD})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied, range not scanned\n" % sha)
        self.assertIn("land-step: hygiene: scripts/hygiene has no --commits; "
                      "refs/heads/main..%s not scanned\n" % sha, p.stderr)
        self.assertNotIn("--commits", self.ran())

    def test_r5_a_help_that_fails_is_an_older_copy_never_a_silent_green(self):
        fake = ("#!/bin/sh\necho \"hygiene${1:+ $1}\" >> \"$LAND_ORDER\"\n"
                "[ \"$1\" = --help ] && { echo '--commits'; exit 3; }\nexit 0\n")
        sha = self.branch("work", {"scripts/hygiene": fake})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.endswith(", range not scanned\n"), p.stdout)

    def test_r6_the_range_scan_requires_the_private_list_and_the_tree_scan_stands(self):
        # An unreadable private list would read clean; the tree scan's call is today's, bare.
        sha = self.branch("work", {"scripts/hygiene": NEW % 0})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        # land2 R4: the message's scans (<sha>..<commit>) and their --help aside.
        calls = [a for a in self.argv() if a != "--help" and sha + ".." not in a]
        self.assertEqual(calls, ["", "--require-private --commits refs/heads/main..%s" % sha])


if __name__ == "__main__":
    unittest.main()
