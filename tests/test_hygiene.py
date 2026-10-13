"""scripts/hygiene: counts per group, the allowlist, binaries skipped, exits,
the private list read from outside the repo, and no matched text or private
regex ever printed. Fixture strings are assembled at runtime, and the private
list's regexes bracket a letter, so this file stays clean under the scan itself.
Every term of the private list here is invented."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hygiene"
ENV = "AGENTIK_HYGIENE_PRIVATE"

# The tests' private list, invented terms only: comments and blanks are skipped.
REGEXES = ["quuxvill[e]\\.example", "zorbla[x]-ops", "glimmerwic[k]"]
PRIVATE = ("# the tests' private list: invented terms\n\n"
           "domain\t%s\n   \nprivate\t%s\n  # an indented comment\nperson\t%s\n"
           % tuple(REGEXES))
GENERIC = ["home", "lan", "sibling", "secret", "email"]

# One fixture per group; each assembled so the literal never sits in this file.
FIXTURES = {
    "home": "see /Us" + "ers/alice/notes",
    "lan": "host 192." + "168.1.9 and 10." + "0.0.7",
    "domain": "https://wiki.quuxvill" + "e.example/x",
    "private": "the zorbla" + "x-ops mirror",
    "person": "by Glimmer" + "wick",
    "sibling": "load resp" + "eak first",
}
# The text each fixture matches on, lower-cased.
MATCHED = ["/us" + "ers/alice", "192." + "168.", "10." + "0.0.7", "quuxvill" + "e.example",
           "zorbla" + "x-ops", "glimmer" + "wick", "resp" + "eak"]


def setUpModule():
    global PRIVATE_DIR, PRIVATE_FILE
    PRIVATE_DIR = tempfile.TemporaryDirectory()
    PRIVATE_FILE = os.path.join(PRIVATE_DIR.name, "private.tsv")
    Path(PRIVATE_FILE).write_text(PRIVATE)


def tearDownModule():
    PRIVATE_DIR.cleanup()


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def run(repo, *args, env=None):
    """The scan, with the tests' private list unless `env` says otherwise."""
    full = dict(os.environ)
    full[ENV] = PRIVATE_FILE
    full.update(env or {})
    full = {k: v for k, v in full.items() if v is not None}
    p = subprocess.run([str(SCRIPT), "--repo", repo, *args],
                       capture_output=True, text=True, env=full)
    return p.returncode, p.stdout, p.stderr


class HygieneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git(self.repo, "init", "-q")
        for group, text in FIXTURES.items():
            Path(self.repo, group + ".txt").write_text("clean\n" + text + "\n" + text + "\n")
        Path(self.repo, "docs").mkdir()
        Path(self.repo, "docs", "allowed.md").write_text(FIXTURES["sibling"] + "\n")
        Path(self.repo, "docs", "deep").mkdir()
        Path(self.repo, "docs", "deep", "x.md").write_text(FIXTURES["sibling"] + "\n")
        Path(self.repo, "blob.bin").write_bytes(b"\0\1" + FIXTURES["person"].encode())
        Path(self.repo, "untracked.txt").write_text(FIXTURES["domain"] + "\n")
        Path(self.repo, ".hygiene-allow").write_text(
            "# comment\ndocs/*.md: sibling\nlan.txt: lan,home\n")
        git(self.repo, "add", "--", *[p for p in os.listdir(self.repo)
                                      if p not in (".git", "untracked.txt")])

    def tearDown(self):
        self.tmp.cleanup()

    def json_result(self, *args):
        code, out, _ = run(self.repo, "--json", *args)
        return code, json.loads(out)

    def test_counts_per_group(self):
        code, d = self.json_result()
        self.assertEqual(code, 2)
        for group in ("home", "lan", "private", "person"):
            self.assertEqual(d["groups"][group], {"lines": 2, "files": 1}, group)
        self.assertEqual(d["groups"]["domain"], {"lines": 3, "files": 2})
        self.assertEqual(d["groups"]["sibling"], {"lines": 4, "files": 3})

    def test_allowlist_and_binary_and_untracked(self):
        code, d = self.json_result()
        hits = {(f["path"], f["group"]): f["lines"] for f in d["files"]}
        self.assertNotIn(("lan.txt", "lan"), hits)
        self.assertNotIn(("docs/allowed.md", "sibling"), hits)
        # the glob's * stays inside one segment
        self.assertEqual(hits[("docs/deep/x.md", "sibling")], 1)
        self.assertFalse(any(p == "blob.bin" for p, _ in hits))
        # the working tree: an untracked file is scanned before its commit
        self.assertEqual(hits[("untracked.txt", "domain")], 1)
        self.assertEqual(d["hits_outside_allowlist"], sum(hits.values()))
        self.assertEqual(d["hits_outside_allowlist"], 2 * 5 + 1 + 1)

    def test_green_exits_zero(self):
        Path(self.repo, ".hygiene-allow").write_text(
            "*.txt: home,lan,domain,private,person,sibling\ndocs/*.md: sibling\n"
            "docs/*/*.md: sibling\n")
        code, d = self.json_result()
        self.assertEqual((code, d["hits_outside_allowlist"], d["files"]), (0, 0, []))

    def test_never_prints_matched_text(self):
        for args in ((), ("--json",)):
            code, out, err = run(self.repo, *args)
            self.assertEqual(code, 2)
            for token in MATCHED:
                self.assertNotIn(token, (out + err).lower(), args)
        self.check_text_table()  # folded, so the README's test count holds

    def test_nul_file_scans_secret_and_email(self):
        # ADV10-17: a NUL file's printable runs are scanned for home, secret and email
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            data = (b"\0 abcd" + b"@" + b"example.org sk-an" + b"t" + b"-abcdefghij\n"
                    + b"\0" + ("/Us" + "ers/alice/p.png").encode() + b"\0"
                    + FIXTURES["person"].encode() + b"\0\x01")
            Path(repo, "b.bin").write_bytes(data)
            code, d = self.json_in(repo)
            self.assertEqual(code, 2)
            self.assertEqual(sorted((f["path"], f["group"], f["lines"]) for f in d["files"]),
                             [("b.bin", "email", 1), ("b.bin", "home", 1),
                              ("b.bin", "secret", 1)])

    def check_text_table(self):
        code, out, _ = run(self.repo)
        lines = out.splitlines()
        self.assertEqual(lines[0].split(), ["group", "lines", "files"])
        self.assertIn("home.txt  home  2", lines)
        self.assertEqual(lines[-1], "hits outside allowlist: 12")

    def test_working_tree_scanned(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "a.md").write_text(FIXTURES["person"] + "\n")
            Path(repo, "b.md").write_text(FIXTURES["person"] + "\n")
            Path(repo, ".gitignore").write_text("b.md\n")
            code, out, _ = run(repo, "--json")
            d = json.loads(out)
            # untracked a.md is scanned, ignored b.md never
            self.assertEqual((code, d["groups"]["person"]["files"]), (2, 1))
            self.assertEqual([f["path"] for f in d["files"]], ["a.md"])

    def test_person_evaluated_under_sittings(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "history", "sittings").mkdir(parents=True)
            Path(repo, "history", "sittings", "x.md").write_text(
                FIXTURES["person"] + "\n" + FIXTURES["sibling"] + "\n")
            Path(repo, "x.md").write_text(FIXTURES["person"] + "\n")
            git(repo, "add", "-A")
            code, out, _ = run(repo, "--json")
            d = json.loads(out)
            # a charter is scanned for the owner's terms too; sibling alone is skipped there
            self.assertEqual((d["groups"]["person"]["files"], d["hits_outside_allowlist"]),
                             (2, 2))
            self.assertEqual({(f["path"], f["group"]) for f in d["files"]},
                             {("x.md", "person"), ("history/sittings/x.md", "person")})

    def test_sibling_not_evaluated_under_sittings(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "history", "sittings").mkdir(parents=True)
            Path(repo, "history", "sittings", "x.md").write_text(
                FIXTURES["sibling"] + "\n" + FIXTURES["home"] + "\n")
            Path(repo, "x.md").write_text(FIXTURES["sibling"] + "\n")
            git(repo, "add", "-A")
            code, out, _ = run(repo, "--json")
            d = json.loads(out)
            self.assertEqual((d["groups"]["sibling"]["files"], d["groups"]["home"]["files"],
                              d["hits_outside_allowlist"]), (1, 1, 2))
            # a sibling named by path still trips home under the charters
            self.assertEqual({(f["path"], f["group"]) for f in d["files"]},
                             {("x.md", "sibling"), ("history/sittings/x.md", "home")})

    def test_script_scans_itself_clean(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "hygiene").write_bytes(SCRIPT.read_bytes())
            Path(repo, "test_hygiene.py").write_bytes(Path(__file__).read_bytes())
            git(repo, "add", "hygiene", "test_hygiene.py")
            code, out, _ = run(repo, "--json")
            self.assertEqual((code, json.loads(out)["hits_outside_allowlist"]), (0, 0))

    def test_usage_and_git_failure_exit_one(self):
        self.assertEqual(run(self.repo, "--bogus")[0], 1)
        self.assertEqual(run(self.repo, "--allow")[0], 1)
        self.assertEqual(run(self.repo, "--allow", "missing")[0], 1)
        Path(self.repo, ".hygiene-allow").write_text("no-colon-here\n")
        self.assertEqual(run(self.repo)[0], 1)
        with tempfile.TemporaryDirectory() as notgit:
            self.assertEqual(run(notgit)[0], 1)

    def test_hygiene_catches_secret_symlink_and_path(self):
        # ADV6-1: a key, a symlink to a home path, a file named for a private repo.
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "k.md").write_text("sk-an" + "t-x\n")
            os.symlink("/Us" + "ers/x", os.path.join(repo, "l"))
            Path(repo, "zorbla" + "x-ops.md").write_text("")
            code, d = self.json_in(repo)
            self.assertEqual((code, d["hits_outside_allowlist"]), (2, 3))
            self.assertEqual({(f["path"], f["group"]) for f in d["files"]},
                             {("k.md", "secret"), ("l", "home"),
                              ("zorbla" + "x-ops.md", "private")})

    def json_in(self, repo, *args):
        code, out, _ = run(repo, "--json", *args)
        return code, json.loads(out)

    def test_secret_group_catches_each_key_shape(self):
        keys = ["sk-an" + "t-api03-abcDEF_12-x", "gh" + "p_" + "a1B2" * 9,
                "github_" + "pat_" + "11AB" * 6, "AGE-SECRET-" + "KEY-1" + "QZ" * 20,
                "AK" + "IA" + "ABCDEFGH23456789", "-----BEG" + "IN RSA PRIV" + "ATE KEY-----",
                "-----BEG" + "IN PRIV" + "ATE KEY-----"]
        # the prefixes named in prose, and lowercase look-alikes, are not keys
        prose = ["`sk-an" + "t-`", "`gh" + "p_`", "BEG" + "IN .* PRIV" + "ATE KEY",
                 "ak" + "ia" + "abcdefgh23456789"]
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "keys.md").write_text("\n".join(keys) + "\n")
            Path(repo, "prose.md").write_text("\n".join(prose) + "\n")
            code, d = self.json_in(repo)
            self.assertEqual(code, 2)
            self.assertEqual(d["groups"]["secret"], {"lines": len(keys), "files": 1})
            out = run(repo)[1] + run(repo, "--json")[1]
            for key in keys:
                self.assertNotIn(key, out)

    def test_email_and_lan_172_and_local(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "e.md").write_text("mail al" + "ice@" + "example.com\nno at here\n")
            Path(repo, "n.md").write_text(
                "172." + "20.1.2\n172." + "31.0.1\nnas" + ".local here\n"
                "172.32.0.1\n172.15.0.1\n~/.local/state\n")
            code, d = self.json_in(repo)
            self.assertEqual(code, 2)
            self.assertEqual(d["groups"]["email"], {"lines": 1, "files": 1})
            self.assertEqual(d["groups"]["lan"], {"lines": 3, "files": 1})

    def test_binary_scanned_for_home_over_printable_runs(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            png = (b"\x89PNG\0\0" + ("/Us" + "ers/alice/p.png").encode() + b"\0"
                   + FIXTURES["person"].encode() + b"\0" + ("~/co" + "de/").encode()
                   + b"\0\x01")
            Path(repo, "a.png").write_bytes(png)
            code, d = self.json_in(repo)
            # one run of 8+ bytes carries the home path; the 7-byte run and the
            # person text are not evaluated in a binary
            self.assertEqual(code, 2)
            self.assertEqual(d["files"], [{"path": "a.png", "group": "home", "lines": 1}])
            self.assertEqual(d["oversize"], 0)
            # UTF-16 (a BOM, or NULs on 90% of the odd or even bytes) is text (ADV10-8)
            text = "/Us" + "ers/alice/x\n" + FIXTURES["person"] + "\n"
            Path(repo, "le.md").write_bytes(text.encode("utf-16-le"))
            Path(repo, "be.md").write_bytes(text.encode("utf-16"))
            Path(repo, "zeros.bin").write_bytes(b"\0" * 64)
            # a file over 4 MiB is streamed, every line of it (ADV11-3)
            Path(repo, "big.txt").write_bytes(("/Us" + "ers/alice\n").encode() * 500000)
            code, d = self.json_in(repo)
            self.assertEqual(sorted((f["path"], f["group"], f["lines"]) for f in d["files"]),
                             [("a.png", "home", 1), ("be.md", "home", 1), ("be.md", "person", 1),
                              ("big.txt", "home", 500000), ("le.md", "home", 1),
                              ("le.md", "person", 1)])
            self.assertEqual(d["oversize"], 1)

    def test_hygiene_oversize_is_scanned(self):
        # ADV11-3: 4 MiB + 1 of one line, then a home path: streamed, one hit, never a pass
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "f").write_bytes(b"x" * (4 * 1024 * 1024 + 1)
                                        + ("\n/Us" + "ers/me/x\n").encode())
            code, d = self.json_in(repo)
            self.assertEqual(code, 2)
            self.assertEqual(d["groups"]["home"]["lines"], 1)
            self.assertEqual(d["oversize"], 1)
            # a binary and a UTF-16 file over the cap stream too, a run across a chunk seen
            Path(repo, "f").unlink()
            Path(repo, "b.bin").write_bytes(b"\0" + b"y" * (1024 * 1024 - 4)
                                            + ("/Us" + "ers/me/bin").encode() + b"\0" * (4 << 20))
            Path(repo, "w.md").write_bytes(("z" * (5 << 20) + "\n/Us" + "ers/me/w\n")
                                           .encode("utf-16"))
            code, d = self.json_in(repo)
            self.assertEqual(sorted((f["path"], f["group"], f["lines"]) for f in d["files"]),
                             [("b.bin", "home", 1), ("w.md", "home", 1)])
            self.assertEqual(d["oversize"], 2)

    def test_hygiene_relay_adv11_15_first_line(self):
        # agent-relay's ADV11-15: a tracked file over 4 MiB whose first line holds a home
        # path and an email passed by path only, exit 0; streamed now (S14), both counted.
        # Binaries still skip lan, domain, private, person and sibling (ADV10-17, unchanged)
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "big.md").write_bytes(("/Us" + "ers/alice/x mail al" + "ice@"
                                              + "example.com\n").encode() + b"y" * (5 << 20))
            git(repo, "add", "big.md")
            code, d = self.json_in(repo)
            self.assertEqual(code, 2)
            self.assertEqual(sorted((f["path"], f["group"], f["lines"]) for f in d["files"]),
                             [("big.md", "email", 1), ("big.md", "home", 1)])
            self.assertEqual(d["oversize"], 1)

    def test_secret_allow_row_only_under_fixtures(self):
        with tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "tests", "fixtures").mkdir(parents=True)
            Path(repo, "tests", "fixtures", "k.md").write_text("sk-an" + "t-x\n")
            Path(repo, ".hygiene-allow").write_text("tests/fixtures/*.md: secret\n")
            self.assertEqual(self.json_in(repo)[0], 0)
            for row in ("*.md: secret", "tests/*.md: secret,home", "tests/fixture*/k.md: secret"):
                Path(repo, ".hygiene-allow").write_text(row + "\n")
                self.assertEqual(run(repo)[0], 1, row)

    def test_symlink_target_not_followed(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as out:
            git(repo, "init", "-q")
            Path(out, "t.md").write_text(FIXTURES["person"] + "\n")
            os.symlink(os.path.join(out, "t.md"), os.path.join(repo, "link"))
            code, d = self.json_in(repo)
            # the target path is scanned; the target's content is not read
            self.assertEqual(d["groups"]["person"]["files"], 0)

    def test_private_list_loaded_never_printed(self):
        # the list's groups join the generic ones, in its order; no regex is ever printed
        code, d = self.json_result()
        self.assertEqual(list(d["groups"]), sorted(GENERIC + ["domain", "private", "person"]))
        code, out, err = run(self.repo)
        groups = [row.split()[0] for row in out.splitlines()[1:9]]
        self.assertEqual(groups, GENERIC + ["domain", "private", "person"])
        for args in ((), ("--json",), ("--require-private",)):
            code, out, err = run(self.repo, *args)
            self.assertEqual(code, 2)
            for rx in REGEXES:
                self.assertNotIn(rx, out + err, args)
            self.assertEqual(err, "", args)

    def test_private_list_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "none.tsv")
            code, out, err = run(self.repo, "--json", env={ENV: missing})
            self.assertEqual(err, "hygiene: no private list at %s; generic groups only\n"
                             % missing)
            # the scan runs on the generic groups, and its exit follows them
            d = json.loads(out)
            self.assertEqual((code, sorted(d["groups"])), (2, sorted(GENERIC)))
            with tempfile.TemporaryDirectory() as repo:
                git(repo, "init", "-q")
                Path(repo, "p.md").write_text(FIXTURES["person"] + "\n" + FIXTURES["domain"])
                self.assertEqual(run(repo, env={ENV: missing})[0], 0)
                self.assertEqual(run(repo)[0], 2)
                # an allow row naming a group the absent list would add is tolerated
                Path(repo, ".hygiene-allow").write_text("p.md: person\n")
                self.assertEqual(run(repo, env={ENV: missing})[0], 0)
                Path(repo, ".hygiene-allow").write_text("p.md: nosuchgroup\n")
                self.assertEqual(run(repo)[0], 1)

    def test_require_private_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "none.tsv")
            code, out, err = run(self.repo, "--require-private", env={ENV: missing})
            self.assertEqual((code, out), (2, ""))
            self.assertIn(missing, err)
            # unreadable: a directory, and a file that is not UTF-8
            bad = os.path.join(tmp, "bad.tsv")
            Path(bad).write_bytes(b"person\t\xff\xfe\n")
            for path in (tmp, bad):
                code, out, err = run(self.repo, "--require-private", env={ENV: path})
                self.assertEqual((code, out), (2, ""), path)
                code, out, err = run(self.repo, "--json", env={ENV: path})
                self.assertIn("unreadable; generic groups only", err)
                self.assertEqual(sorted(json.loads(out)["groups"]), sorted(GENERIC))
            # present: the flag changes nothing
            self.assertEqual(run(self.repo, "--require-private")[0], 2)
            Path(self.repo, ".hygiene-allow").write_text(
                "*.txt: home,lan,domain,private,person,sibling\ndocs/*.md: sibling\n"
                "docs/*/*.md: sibling\n")
            self.assertEqual(run(self.repo, "--require-private")[0], 0)

    def test_private_new_group_hit_and_default_path(self):
        # a new group name is allowed; a hit prints as any other; a line counts once
        # per group even when an in-file and a private regex both match it
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as repo:
            git(repo, "init", "-q")
            Path(repo, "x.md").write_text("the frobni" + "z board\n" + FIXTURES["home"] + "\n")
            text = "#codename\tx-ops\ncodename\tfrobni[z]\nhome\talic[e]\n"
            xdg = Path(tmp, "xdg", "agentik")
            xdg.mkdir(parents=True)
            Path(xdg, "hygiene-private.tsv").write_text(text)
            home = Path(tmp, "home", ".config", "agentik")
            home.mkdir(parents=True)
            Path(home, "hygiene-private.tsv").write_text(text)
            for env in ({ENV: None, "XDG_CONFIG_HOME": str(Path(tmp, "xdg"))},
                        {ENV: "", "XDG_CONFIG_HOME": "", "HOME": str(Path(tmp, "home"))}):
                code, out, err = run(repo, "--json", env=env)
                d = json.loads(out)
                self.assertEqual((code, err), (2, ""), env)
                self.assertEqual(d["groups"]["codename"], {"lines": 1, "files": 1})
                self.assertEqual(d["groups"]["home"], {"lines": 1, "files": 1})
                code, out, err = run(repo, env=env)
                self.assertIn("x.md  codename  1", out.splitlines())
                self.assertNotIn("frobni[z]", out + err)
            Path(repo, ".hygiene-allow").write_text("x.md: codename,home\n")
            self.assertEqual(run(repo, env={ENV: str(Path(xdg, "hygiene-private.tsv"))})[0], 0)

    def test_private_bad_line_exits_one_unprinted(self):
        with tempfile.TemporaryDirectory() as tmp:
            for line in ("person glimmerwic[k]", "per son\tglimmerwic[k]", "person\t",
                         "person\tglimmer(wic[k]"):
                path = os.path.join(tmp, "p.tsv")
                Path(path).write_text("# ok\n" + line + "\n")
                code, out, err = run(self.repo, env={ENV: path})
                self.assertEqual((code, out), (1, ""), line)
                self.assertIn("%s:2: bad entry" % path, err)
                self.assertNotIn("glimmer", err.lower(), line)


if __name__ == "__main__":
    unittest.main()
