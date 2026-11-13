"""Packet land2: `gate land` refuses what would lose work or land an unchecked tree. R1 a
worktree nested in the branch's, R2 a branch behind main, R3 the merge file's text, R4 the merge
message's scan, R5 the last two again after the check. Temp repos and a stub check, as
test_land.py's; the stub hygiene reds a made-up term in a range's messages."""

import os
import shutil
import subprocess
import types
from pathlib import Path

from claude_session import unattended
from test_land import LandCase

TERM = "zorblatt"
# A hygiene that knows --commits: each call's argv to $LAND_ORDER.argv; a range whose messages
# hold the term exits 3; the tree scan and --help exit 0.
STUB = ("#!/bin/sh\necho \"$*\" >> \"$LAND_ORDER.argv\"\n"
        "case $1 in --help) echo 'usage: hygiene [--require-private] [--commits RANGE]'; "
        "exit 0 ;; esac\n"
        "[ \"$1\" = --require-private ] && shift\n"
        "if [ \"$1\" = --commits ]; then\n"
        "  git log --format=%%B \"$2\" | grep -q %s && exit 3\nfi\nexit 0\n" % TERM)
OLD = "#!/bin/sh\ncase $1 in --help) echo 'usage: hygiene [--json]'; exit 0 ;; esac\nexit 0\n"


class Land2Case(LandCase):
    def setUp(self):
        super().setUp()
        self.write(self.tmp, "merge-message", "Merge work: land the branch\n\nThe trailer.\n")

    def hand(self, name, body):
        """A script the check runs: a hand on the main checkout while the minutes pass."""
        return self.write(self.tmp, name, "#!/bin/sh\n" + body, 0o755)

    def branch_with_hand(self, name, hand, files=None):
        make = "check:\n\t@echo check >> \"$$LAND_ORDER\"\n\t@%s\n" % hand
        return self.branch(name, dict(files or {}, Makefile=make))

    def nested(self, name="inner"):
        path = os.path.join(self.worktree("work"), ".claude", "worktrees", name)
        self.git("worktree", "add", "-q", "-b", name, path, "main")
        return path

    def argv(self):
        path = self.order + ".argv"
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return fh.read().splitlines()

    def index(self):
        return self.git("ls-files", "-s")


class TestNested(Land2Case):
    """R1: a worktree under the branch's worktree is red, clean or dirty, and is never removed."""

    def test_r1_a_dirty_nested_worktree_is_red_and_kept(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        inner = self.nested()
        self.write(inner, "wip.txt", "uncommitted\n")
        self.write(inner, "shared.txt", "edited\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.ran(), [])
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.exists(os.path.join(inner, "wip.txt")))
        with open(os.path.join(inner, "shared.txt")) as fh:
            self.assertEqual(fh.read(), "edited\n")
        self.assertIn(inner, p.stderr)
        self.assertIn(" M shared.txt", p.stderr)
        self.assertIn("?? wip.txt", p.stderr)

    def test_r1_a_clean_nested_worktree_is_red_too(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        inner = self.nested()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.ran(), [])
        self.assertTrue(os.path.isdir(inner))
        self.assertIn(inner + ": clean", p.stderr)

    def test_r1_a_nested_worktree_whose_directory_is_gone_lands(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        shutil.rmtree(self.nested())
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)

    def test_r1_a_nested_worktree_added_during_the_check_is_red_after_it(self):
        inner = os.path.join(self.worktree("work"), ".claude", "worktrees", "inner")
        hand = self.hand("hand", "git -C \"%s\" worktree add -q -b inner \"%s\" main\n"
                         % (self.repo, inner))
        sha = self.branch_with_hand("work", hand)
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.ran(), ["check"])
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.isdir(inner))


class TestBehind(Land2Case):
    """R2: the check must run on the tree main would hold."""

    def test_r2_main_gaining_a_commit_after_the_cut_is_red_sha_before_the_check(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        self.on_main("other.txt", "other\n")
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "sha", 1)
        self.assertEqual(self.ran(), [])
        self.assertEqual(self.main_sha(), before)
        self.assertIn("%s main moves other.txt" % before[:7], p.stderr)
        self.assertIn("merge main into work", p.stderr)
        tree = self.worktree("work")
        self.git("merge", "-q", "--no-edit", "main", cwd=tree)
        head = self.git("rev-parse", "HEAD", cwd=tree)
        p = self.land("work", head)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % head)
        self.assertEqual(self.git("rev-parse", "main^{tree}"), self.git("rev-parse", head + "^{tree}"))

    def test_r2_main_gaining_a_commit_during_the_check_is_red_sha_before_the_merge(self):
        hand = self.hand("hand", "echo late > \"%s/late.txt\"\ngit -C \"%s\" add late.txt\n"
                         "git -C \"%s\" commit -qm late\n" % (self.repo, self.repo, self.repo))
        sha = self.branch_with_hand("work", hand)
        p = self.land("work", sha)
        self.assertRed(p, "sha", 1)
        self.assertEqual(self.ran(), ["check"])
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "late")
        self.assertEqual(len(self.git("rev-list", "--parents", "-n1", "main").split()), 2)
        self.assertTrue(os.path.isdir(self.worktree("work")))


class TestMergeFile(Land2Case):
    """R3: line 1 is `Merge <branch>: ` and text, line 2 blank when there is one."""

    def test_r3_a_malformed_merge_file_is_red_before_the_check(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        before = self.main_sha()
        cases = {"empty": "", "blank": "  \n\n", "other": "Merge other-row: x\n",
                 "alone": "Merge work:\n", "bare": "Merge work: \n",
                 "line2": "Merge work: x\nbody straight after\n"}
        for name, text in cases.items():
            with self.subTest(name):
                path = self.write(self.tmp, "mf-" + name, text)
                p = self.land("work", sha, message=path)
                self.assertRed(p, "merge-file", 1)
                self.assertEqual(self.ran(), [])
                self.assertEqual(self.main_sha(), before)
                if name in ("empty", "blank"):
                    self.assertIn("blank", p.stderr)

    def test_r3_one_line_and_a_body_after_a_blank_land(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        path = self.write(self.tmp, "mf-one", "Merge work: one line\n")
        p = self.land("work", sha, message=path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "Merge work: one line")

    def test_r3_the_loops_merge_file_passes(self):
        sha = self.branch("limit-row", {"a.txt": "a\n"})
        self.write(self.repo, "design/packets/limit-row.md", "# Packet limit-row: the step\n")
        run = types.SimpleNamespace(dir=Path(self.tmp), repo=Path(self.repo), nid="n-1")
        p_row = {"id": "limit-row", "packet": "design/packets/limit-row.md"}
        merge = unattended._Run.merge_file(run, p_row, sha, "sess-1")
        os.unlink(os.path.join(self.repo, "design/packets/limit-row.md"))
        p = self.land("limit-row", sha, message=str(merge))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "Merge limit-row: the step")


class TestMessageScan(Land2Case):
    """R4: the merge commit's message is scanned as a dangling commit, before the check."""

    def test_r4_the_term_in_the_merge_file_is_red_before_the_check_and_writes_no_ref(self):
        sha = self.branch("work", {"scripts/hygiene": STUB})
        msg = self.write(self.tmp, "mf-term", "Merge work: %s lands\n\nThe body.\n" % TERM)
        before, index, status = self.main_sha(), self.index(), self.porcelain_lines()
        refs = self.git("for-each-ref")
        p = self.land("work", sha, message=msg)
        self.assertRed(p, "merge-file", 3)
        self.assertEqual(self.ran(), [])
        scans = [a for a in self.argv() if a.startswith("--require-private --commits ")]
        self.assertEqual(len(scans), 1, self.argv())
        span = scans[0].split()[-1]
        low, commit = span.split("..")
        self.assertEqual(low, sha)
        self.assertEqual(self.git("rev-list", "--parents", "-n1", commit).split()[1:],
                         [before, sha])
        merged = self.git("merge-tree", "--write-tree", "main", sha)
        self.assertEqual(self.git("rev-parse", commit + "^{tree}"), merged)
        self.assertEqual(self.git("log", "-1", "--format=%B", commit),
                         "Merge work: %s lands\n\nThe body." % TERM)
        self.assertEqual(self.git("for-each-ref", "--contains", commit), "")
        self.assertEqual(self.git("for-each-ref"), refs)
        self.assertEqual((self.main_sha(), self.index(), self.porcelain_lines()),
                         (before, index, status))

    def test_r4_a_clean_message_lands_after_two_message_scans(self):
        sha = self.branch("work", {"scripts/hygiene": STUB})
        p = self.land("work", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        ranges = [a.split()[-1] for a in self.argv() if " --commits " in " " + a]
        self.assertEqual(len(ranges), 3, self.argv())
        self.assertEqual(ranges[1], "refs/heads/main..%s" % sha)
        for span in (ranges[0], ranges[2]):
            self.assertTrue(span.startswith(sha + ".."), span)

    def test_r4_no_hygiene_and_one_without_commits_land_as_today(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        p = self.land("work", sha)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha)
        self.write(self.tmp, "merge-message", "Merge old: an older hygiene\n")
        sha = self.branch("old", {"scripts/hygiene": OLD})
        p = self.land("old", sha)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied, range not scanned\n" % sha)


class TestAfterTheCheck(Land2Case):
    """R5: the merge file is read and scanned again after the check, before the merge."""

    def test_r5_the_merge_file_rewritten_during_the_check_is_red_after_it(self):
        for name, text, code in (("term", "Merge work: %s\n" % TERM, 3), ("blank", "", 1)):
            with self.subTest(name):
                msg = self.write(self.tmp, "mf-" + name, "Merge work: fine\n")
                hand = self.hand("hand-" + name, "printf '%s' > \"%s\"\n" % (text, msg))
                sha = self.branch_with_hand("work", hand, {"scripts/hygiene": STUB})
                before = self.main_sha()
                p = self.land("work", sha, message=msg)
                self.assertRed(p, "merge-file", code)
                self.assertEqual(self.ran(), ["check"])
                self.assertEqual(self.main_sha(), before)
                self.git("worktree", "remove", "--force", self.worktree("work"))
                self.git("branch", "-D", "work")
                os.unlink(self.order)


class TestRound1(Land2Case):
    """Round 1's findings: F1 a case-variant spelling, F2 main moving during the last scan, F3 a
    newline in a worktree's path, F5 the scan's exit named, F6 commit-tree's own reason."""

    def nested_wip(self, path):
        self.git("worktree", "add", "-q", "-b", "inner", path, "main")
        return self.write(path, "wip.txt", "WIP\n")

    def test_f1_a_nested_worktree_under_a_case_variant_path_is_red_and_kept(self):
        upper = os.path.join(os.path.dirname(self.repo), "SCRATCH")
        if not os.path.isdir(upper):
            self.skipTest("this volume does not fold case, so no case variant reaches the repo")
        sha = self.branch("work", {"a.txt": "a\n"})
        rel = os.path.relpath(self.worktree("work"), self.repo)
        wip = self.nested_wip(os.path.join(upper, rel, ".claude", "worktrees", "inner"))
        before = self.main_sha()
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertEqual(self.ran(), [])
        self.assertEqual(self.main_sha(), before)
        self.assertTrue(os.path.exists(wip))
        self.assertIn("?? wip.txt", p.stderr)

    def test_f1_a_sibling_worktree_never_counts(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        self.git("worktree", "add", "-q", "-b", "sib", self.worktree("work") + "-2", "main")
        p = self.land("work", sha)
        self.assertEqual(p.stdout, "land scratch: ok %s, main readied\n" % sha, p.stderr)

    def test_f2_main_moving_during_the_last_scan_is_red_sha_and_not_buried(self):
        hy = ("#!/bin/sh\ncase $1 in --help) echo '--commits'; exit 0 ;; esac\n"
              "[ \"$1\" = --require-private ] && shift\n"
              "case \"$2\" in refs/heads/main..*|'') exit 0 ;; esac\n"
              "if [ -e \"$LAND_ORDER.checked\" ]; then cd \"%s\" && echo x > raced.txt && "
              "git add raced.txt && git commit -qm raced; fi\nexit 0\n" % self.repo)
        make = "check:\n\t@touch \"$$LAND_ORDER.checked\"\n"
        sha = self.branch("work", {"scripts/hygiene": hy, "Makefile": make})
        p = self.land("work", sha)
        self.assertRed(p, "sha", 1)
        self.assertEqual(self.git("log", "-1", "--format=%s", "main"), "raced")
        self.assertEqual(len(self.git("rev-list", "--parents", "-n1", "main").split()), 2)
        self.assertIn("raced", p.stderr)
        self.assertTrue(os.path.isdir(self.worktree("work")))

    def test_f3_a_nested_worktree_with_a_newline_in_its_path_is_red_and_kept(self):
        sha = self.branch("work", {"a.txt": "a\n"})
        wip = self.nested_wip(os.path.join(self.worktree("work"), ".claude", "worktrees",
                                           "in\nner"))
        p = self.land("work", sha)
        self.assertRed(p, "worktree", 1)
        self.assertTrue(os.path.exists(wip))

    def test_f5_the_message_scans_exit_is_named_and_its_stderr_pointed_at(self):
        hy = ("#!/bin/sh\ncase $1 in --help) echo '--commits'; exit 0 ;; esac\n"
              "[ \"$1\" = --require-private ] && shift\n"
              "case \"$2\" in refs/heads/main..*|'') exit 0 ;; esac\n"
              "echo 'hygiene: no private list' >&2\nexit 2\n")
        sha = self.branch("work", {"scripts/hygiene": hy})
        p = self.land("work", sha)
        self.assertRed(p, "merge-file", 2)
        self.assertIn("scripts/hygiene exit 2 on the merge message; see its stderr", p.stderr)
        self.assertIn("hygiene: no private list", p.stderr)

    def test_f6_commit_trees_own_reason_reaches_the_log(self):
        sha = self.branch("work", {"scripts/hygiene": STUB})
        nul = os.path.join(self.tmp, "mf-nul")
        with open(nul, "wb") as fh:
            fh.write(b"Merge work: x\x00y\n")
        p = self.land("work", sha, message=nul)
        self.assertRed(p, "merge-file", 1)
        self.assertIn("NUL", p.stderr)
        with open(self.env["GIT_CONFIG_GLOBAL"], "w") as fh:
            fh.write("[init]\n\tdefaultBranch = main\n[user]\n\tuseConfigOnly = true\n")
        env = {k: v for k, v in self.env.items()
               if not k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_")) and k != "EMAIL"}
        p = self.land("work", sha, env=env)
        self.assertRed(p, "merge-file", 1)
        self.assertIn("fatal:", p.stderr)
        self.assertEqual(self.ran(), [])
