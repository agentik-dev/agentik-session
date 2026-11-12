"""`gate land`'s bare name: that checkout in ~/code, else the one a folder below, since a repo
may sit in a folder under ~/code. Kept apart from test_land.py, whose ported count is pinned.
Every path is under a temp HOME; no test reads the owner's checkouts.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "plugin", "lib", "agentik-session")
MARK = "CLAUDE_SESSION_GATE_JOB"


class TestResolveRepo(unittest.TestCase):
    """A bare name: that checkout in ~/code, else the one a folder below; a plain directory never
    matches."""

    def setUp(self):
        from claude_session import land
        self.land = land
        self.home = os.path.realpath(tempfile.mkdtemp(prefix="land-resolve-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        self.code = os.path.join(self.home, "code")
        os.makedirs(self.code)
        old = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        self.addCleanup(lambda: os.environ.__setitem__("HOME", old) if old is not None
                        else os.environ.pop("HOME", None))

    def mkdir(self, *parts):
        path = os.path.join(self.code, *parts)
        os.makedirs(path)
        return path

    def checkout(self, *parts, linked=False):
        """A toy checkout: a .git directory, or a .git file as a linked worktree has."""
        path = self.mkdir(*parts)
        if linked:
            with open(os.path.join(path, ".git"), "w") as fh:
                fh.write("gitdir: elsewhere\n")
        else:
            os.makedirs(os.path.join(path, ".git"))
        return path

    def red(self, name):
        with self.assertRaises(self.land.Red) as caught:
            self.land.resolve_repo(name)
        self.assertEqual((caught.exception.step, caught.exception.code), ("repo", 1))
        return caught.exception.note

    def test_a_directory_at_code_name_wins(self):
        direct = self.checkout("alpha")
        self.checkout("tree", "alpha")
        self.assertEqual(self.land.resolve_repo("alpha"), direct)

    def test_one_level_down(self):
        down = self.checkout("tree", "alpha", linked=True)
        self.assertEqual(self.land.resolve_repo("alpha"), down)

    def test_a_plain_file_at_the_old_name_is_no_match(self):
        with open(os.path.join(self.code, "alpha"), "w") as fh:
            fh.write("moved into the tree folder\n")
        down = self.checkout("tree", "alpha")
        self.assertEqual(self.land.resolve_repo("alpha"), down)

    def test_none_is_red_and_names_what_was_looked_for(self):
        self.checkout("tree", "beta")
        self.checkout(".hidden", "alpha")
        self.mkdir("alpha")
        self.mkdir("plain", "alpha")
        note = self.red("alpha")
        self.assertIn("no checkout", note)
        self.assertIn(os.path.join(self.code, "alpha"), note)
        self.assertIn(os.path.join(self.code, "*", "alpha"), note)

    def test_two_are_red_and_name_each(self):
        one, two = self.checkout("tree", "alpha"), self.checkout("other", "alpha", linked=True)
        self.mkdir("plain", "alpha")
        note = self.red("alpha")
        self.assertIn(one, note)
        self.assertIn(two, note)

    def test_a_name_with_a_slash_stays_a_path(self):
        self.mkdir("tree", "alpha")
        path = os.path.join(self.home, "elsewhere", "alpha")
        self.assertEqual(self.land.resolve_repo(path), path)
        # tree/alpha has a slash: a path from the cwd, never the one in the code folder
        self.assertEqual(self.land.resolve_repo("tree/alpha"), os.path.realpath("tree/alpha"))
        self.assertNotEqual(os.path.realpath("tree/alpha"),
                            os.path.join(self.code, "tree", "alpha"))

    def test_the_queue_form_reads_two_as_a_red_repo_line(self):
        self.checkout("tree", "alpha")
        self.checkout("other", "alpha")
        env = dict(os.environ, XDG_STATE_HOME=os.path.join(self.home, "state"))
        env.pop(MARK, None)
        p = subprocess.run([sys.executable, RUNNER, "gate", "land", "alpha", "work", "abc",
                            os.path.join(self.home, "msg")], env=env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual((p.returncode, p.stdout), (1, "land alpha: red repo exit 1\n"))
        self.assertIn(os.path.join(self.code, "other", "alpha"), p.stderr)

    def test_more_than_one_says_so(self):
        for folder in ("tree", "other", "third"):
            self.checkout(folder, "alpha")
        self.assertIn("more than one checkout", self.red("alpha"))

    def test_a_folder_symlink_reaches_one_checkout_once(self):
        real = self.checkout("beta", "foo")
        os.symlink(os.path.join(self.code, "beta"), os.path.join(self.code, "alias"))
        self.assertEqual(self.land.resolve_repo("foo"), real)

    def test_a_repo_symlink_reaches_one_checkout_once(self):
        real = self.checkout("tree", "bar")
        self.mkdir("other")
        os.symlink(real, os.path.join(self.code, "other", "bar"))
        self.assertEqual(self.land.resolve_repo("bar"), real)

    def test_an_empty_name_dot_and_dot_dot_are_red(self):
        self.checkout("only")       # the one checkout a bare glob one folder down would find
        for name in ("", ".", ".."):
            self.assertIn("no repo name", self.red(name))

    def test_the_in_job_form_reads_none_as_a_red_repo_line(self):
        env = dict(os.environ, XDG_STATE_HOME=os.path.join(self.home, "state"))
        env[MARK] = "20261110-000000-1"
        p = subprocess.run([sys.executable, RUNNER, "gate", "land", "--in-job", "alpha", "work",
                            "abc", os.path.join(self.home, "msg")], env=env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual((p.returncode, p.stdout), (1, "land alpha: red repo exit 1\n"))
        self.assertIn("no checkout", p.stderr)

    def test_a_folder_named_like_its_repo_yields_the_inner_checkout(self):
        self.mkdir("gamma")
        inner = self.checkout("gamma", "gamma")
        self.assertEqual(self.land.resolve_repo("gamma"), inner)

    def test_a_plain_directory_at_the_direct_path_yields_the_checkout_below(self):
        self.mkdir("alpha")
        down = self.checkout("tree", "alpha")
        self.assertEqual(self.land.resolve_repo("alpha"), down)



if __name__ == "__main__":
    unittest.main()
