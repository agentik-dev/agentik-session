"""Packet land3-stamp: `scripts/stamp` writes the version, the README's count, the sidecar
and the NICE file's size, and reds on a merge whose count is not the branch's plus main's
less the merge base's. Each case runs the script over a made-up temp repo: `main`, a branch
`quince`, a plugin at 2.0.0-alpha.7 with `plugin/lib/pear.py`, three tests in
`tests/test_pear.py`, both README files, the sidecar and both NICE files."""

import hashlib
import importlib.machinery
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_readme import STATUS as README_STATUS

ROOT = Path(__file__).resolve().parents[1]
STAMP = ROOT / "scripts" / "stamp"
SOURCE = "design/readme/source.md"
README = "README.md"
SIDECAR = "design/readme/rendered.sha256"
MANIFEST = "plugin/.claude-plugin/plugin.json"
NICE = "NICE_TO_HAVE.md"
OVERFLOW = "history/NICE-overflow.md"
TESTS = "tests/test_pear.py"
DATE = "2026-01-02"
NICE_HEAD = ("# NICE_TO_HAVE: pear\n\nFindings that block nothing, one row each.\n\n"
             "## Open findings\n\n| id | level | area | finding | evidence | from |\n"
             "|---|---|---|---|---|---|\n")
OVERFLOW_TEXT = ("# NICE overflow: pear\n\nS4 rows moved out of the NICE file.\n\n"
                 "## From the open findings\n\n| id | level | area | finding | evidence | from |\n"
                 "|---|---|---|---|---|---|\n"
                 "| n1 | S4 | `pear.py` | an old row | e | 2026-01-01, a builder |\n\n"
                 "## Borrowed elsewhere\n\n| id | level | area | finding | evidence | from |\n"
                 "|---|---|---|---|---|---|\n"
                 "| n2 | S4 | `pear.py` | a borrowed row | e | 2026-01-01, a builder |\n")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def status(version, count):
    return "Status: version `v%s`, rendered `%s`, `%d` tests in the suite." % (version, DATE, count)


def source_text(version="2.0.0-alpha.7", count=3, prose="Pears, by a made-up plugin."):
    return ("# Pear\n\n%s\n\nA second paragraph.\n\nA third paragraph.\n\n%s\n\nThe tail.\n"
            % (prose, status(version, count)))


def readme_text(version="2.0.0-alpha.7", count=3, prose="Pears, rendered."):
    return source_text(version, count, prose)


def manifest_text(version):
    return '{\n  "name": "pear",\n  "version": "%s",\n  "description": "a made-up plugin"\n}\n' % version


def pear_tests(names=("test_a", "test_b", "test_c")):
    return "".join("def %s():\n    pass\n\n\n" % n for n in names)


class Box:
    """The made-up repo, on `quince` after main's first commit."""

    def __init__(self, tmp, version="2.0.0-alpha.7"):
        self.tmp = tmp
        self.repo = tmp / "repo"
        self.repo.mkdir()
        config = tmp / "gitconfig"
        config.write_text("[user]\n\tname = Stamp Test\n\temail = stamp@" + "example.invalid\n"
                          "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n")
        self.env = dict(os.environ, HOME=str(tmp), GIT_CONFIG_GLOBAL=str(config),
                        GIT_CONFIG_NOSYSTEM="1", XDG_CONFIG_HOME=str(tmp / "config"))
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(name, None)
        self.git("init", "-q", "-b", "main")
        self.write(".gitignore", "__pycache__/\n")
        self.write(MANIFEST, manifest_text(version))
        self.write("plugin/lib/pear.py", "def pear():\n    return 1\n")
        self.write(TESTS, pear_tests())
        self.write(SOURCE, source_text(version))
        self.write(README, readme_text(version))
        self.seal()
        self.write(NICE, NICE_HEAD + "| n3 | S3 | `pear.py` | a row | e | 2026-01-01, a builder |\n")
        self.write(OVERFLOW, OVERFLOW_TEXT)
        self.commit("base")
        self.git("checkout", "-q", "-b", "quince")

    def git(self, *args, ok=0):
        p = subprocess.run(["git", *args], cwd=self.repo, env=self.env, text=True,
                           capture_output=True)
        assert p.returncode == ok, "git %s: %s" % (" ".join(args), p.stderr)
        return p.stdout.strip()

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def read(self, rel):
        return (self.repo / rel).read_text()

    def seal(self):
        """The sidecar as a render writes it."""
        self.write(SIDECAR, "".join("%s  %s\n" % (hashlib.sha256((self.repo / p).read_bytes())
                                                   .hexdigest(), p) for p in (SOURCE, README)))

    def set_status(self, version, count, seal=True):
        for rel in (SOURCE, README):
            self.write(rel, re.sub(r"^Status: .*$", status(version, count), self.read(rel),
                                   flags=re.M))
        if seal:
            self.seal()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def stamp(self, *args, repo=None):
        return subprocess.run([sys.executable, str(STAMP), "--repo", str(repo or self.repo),
                               *args], env=self.env, capture_output=True, text=True,
                              timeout=600)

    def snapshot(self):
        return {str(p.relative_to(self.repo)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in sorted(self.repo.rglob("*")) if ".git" not in p.parts and p.is_file()}

    def shasum_ok(self):
        return subprocess.run(["shasum", "-a", "256", "-c", "--status", SIDECAR],
                              cwd=self.repo).returncode == 0

    def numstat(self):
        return sorted(self.git("diff", "--numstat").splitlines())


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


def ok_line(version, count, nothing=False):
    return "stamp: ok: plugin %s, %d tests%s" % (version, count, "; nothing to write" if nothing else "")


def exit_two(p):
    assert p.returncode == 2, (p.stdout, p.stderr)
    lines = p.stderr.splitlines()
    assert len(lines) == 1 and lines[0].startswith("stamp: "), lines
    return lines[0]


# 1 and 2: the version, the count and the sidecar; a second run writes nothing.

def test_line1_a_plugin_change_and_a_test_stamp_the_version_count_and_sidecar(box):
    box.write("plugin/lib/pear.py", "def pear():\n    return 2\n")
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_d")))
    box.commit("quince: a change and a test")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: version 2.0.0-alpha.7 -> 2.0.0-alpha.8",
                                     "stamp: count 3 -> 4", "stamp: sidecar written",
                                     ok_line("2.0.0-alpha.8", 4)]
    assert box.numstat() == sorted(["1\t1\t" + MANIFEST, "1\t1\t" + README, "1\t1\t" + SOURCE,
                                    "2\t2\t" + SIDECAR])
    assert box.shasum_ok()
    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "plugin-version-check"),
                            "--repo", str(box.repo)], env=box.env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert README_STATUS.findall(box.read(README)) == [("2.0.0-alpha.8", DATE, "4")]


def test_line2_a_second_run_writes_nothing(box):
    box.write("plugin/lib/pear.py", "def pear():\n    return 2\n")
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_d")))
    box.commit("quince: a change and a test")
    assert box.stamp().returncode == 0
    before = box.snapshot()
    p = box.stamp()
    assert (p.returncode, p.stdout.splitlines(), p.stderr) == (
        0, [ok_line("2.0.0-alpha.8", 4, nothing=True)], "")
    assert box.snapshot() == before


# 3: the version's rule.

def test_line3_a_version_above_main_stays(box):
    box.write(MANIFEST, manifest_text("2.0.0-alpha.9"))
    box.write("plugin/lib/pear.py", "def pear():\n    return 2\n")
    box.commit("quince at alpha.9")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: sidecar written", ok_line("2.0.0-alpha.9", 3)]
    assert box.git("status", "--porcelain", "--", MANIFEST) == ""


def test_line3_a_test_alone_moves_the_count_not_the_version(box):
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_d")))
    box.commit("quince: a test")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: count 3 -> 4", "stamp: sidecar written",
                                     ok_line("2.0.0-alpha.7", 4)]
    assert box.git("status", "--porcelain", "--", MANIFEST) == ""


def test_line3_a_named_version_is_written(box):
    p = box.stamp("--version", "2.1.0")
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: version 2.0.0-alpha.7 -> 2.1.0",
                                     "stamp: sidecar written", ok_line("2.1.0", 3)]
    assert box.read(MANIFEST) == manifest_text("2.1.0")


@pytest.mark.parametrize("version", ["2.0.0-alpha.7", "next", "2.0.0-alpha.6", ""])
def test_line3_a_named_version_not_above_main_is_exit_2(box, version):
    before = box.snapshot()
    line = exit_two(box.stamp("--version", version))
    assert "--version" in line
    assert box.snapshot() == before


def test_line3_main_ending_in_no_number_names_stamp_version(tmp_path):
    box = Box(tmp_path, version="2.0.0-alpha")
    box.write("plugin/lib/pear.py", "def pear():\n    return 2\n")
    box.commit("quince: a change")
    before = box.snapshot()
    assert "STAMP_VERSION" in exit_two(box.stamp())
    assert box.snapshot() == before


def test_line3_an_uncommitted_or_untracked_plugin_path_counts(box):
    # as the version check's second read: nothing of the branch's own while HEAD is the base
    box.write("plugin/lib/apple.py", "x = 1\n")
    assert box.stamp().stdout.splitlines() == [ok_line("2.0.0-alpha.7", 3, nothing=True)]
    box.write("notes.txt", "a note\n")
    box.git("add", "notes.txt")
    box.git("commit", "-qm", "quince: a note")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines()[0] == "stamp: version 2.0.0-alpha.7 -> 2.0.0-alpha.8"


# 4 and 5: the count's equation at the merge.

def merged(box, main_name="test_new", quince_name="test_new", main_count=4):
    """Main appends a test and renders its Status line; quince puts one first; quince merges main."""
    box.git("checkout", "-q", "main")
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", main_name)))
    box.set_status("2.0.0-alpha.7", main_count)
    box.commit("main: a test")
    box.git("checkout", "-q", "quince")
    box.write(TESTS, pear_tests((quince_name, "test_a", "test_b", "test_c")))
    box.commit("quince: a test")
    box.git("merge", "-q", "--no-edit", "main")
    assert box.git("status", "--porcelain") == ""


def red_count(t, b, m, a, e):
    return ("stamp: red count: the merge collects %d tests; the branch's %d plus main's %d less "
            "the merge base's %d is %d. Compare pytest --collect-only -q at HEAD and at its two "
            "parents" % (t, b, m, a, e))


def test_line4_a_merge_that_drops_a_test_is_red(box):
    merged(box)
    before = box.snapshot()
    p = box.stamp()
    assert p.returncode == 1, (p.stdout, p.stderr)
    assert p.stderr.splitlines() == [red_count(4, 4, 4, 3, 5)]
    assert p.stdout == ""
    assert box.snapshot() == before


def test_line4_two_names_hold_the_equation(box):
    merged(box, main_name="test_new_main", quince_name="test_new_quince")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: count 4 -> 5", "stamp: sidecar written",
                                     ok_line("2.0.0-alpha.7", 5)]


def test_line5_a_commit_above_the_merge_is_not_asked(box):
    merged(box)
    box.write("notes.txt", "a note\n")
    box.commit("quince: a note above the merge")
    p = box.stamp()
    assert p.returncode == 0, p.stderr


def test_line5_mains_status_line_is_read(box):
    merged(box, main_count=9)
    p = box.stamp()
    assert p.returncode == 1
    assert p.stderr.splitlines() == [red_count(4, 4, 9, 3, 10)]
    assert "main's 9" in p.stderr


def test_line5_a_merge_of_another_branch_is_not_asked(box):
    box.git("checkout", "-q", "-b", "plum", "main")
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_new")))
    box.commit("plum: a test")
    box.git("checkout", "-q", "quince")
    box.write(TESTS, pear_tests(("test_new", "test_a", "test_b", "test_c")))
    box.commit("quince: a test")
    box.git("merge", "-q", "--no-edit", "plum")
    p = box.stamp()
    assert p.returncode == 0, p.stderr


def test_line5_two_merge_bases_are_not_asked_and_noted(box):
    box.write("q1.txt", "q1\n")
    box.commit("quince: q1")
    box.git("checkout", "-q", "main")
    box.write("m1.txt", "m1\n")
    box.commit("main: m1")
    box.git("merge", "-q", "--no-edit", "quince")
    box.git("checkout", "-q", "quince")
    box.git("merge", "-q", "--no-edit", "main~1")
    box.git("checkout", "-q", "main")
    box.write("m3.txt", "m3\n")
    box.commit("main: m3")
    box.git("checkout", "-q", "quince")
    box.git("merge", "-q", "--no-edit", "main")
    assert len(box.git("merge-base", "--all", "HEAD^1", "HEAD^2").split()) == 2
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stderr.splitlines() == ["stamp: note: the merge's parents have 2 merge bases; the "
                                     "count's equation is not asked"]


# 6: the sidecar only over fresh files.

def red_sidecar(rel):
    return ("stamp: red sidecar: %s is not the file design/readme/rendered.sha256 names; run "
            "make readme" % rel)


@pytest.mark.parametrize("committed", [True, False], ids=["committed", "uncommitted"])
def test_line6_an_unrendered_source_is_red(box, committed):
    box.write(SOURCE, source_text(prose="Pears, reworded and never rendered."))
    if committed:
        box.commit("quince: the source reworded")
    before = box.snapshot()
    p = box.stamp()
    assert p.returncode == 1
    assert p.stderr.splitlines() == [red_sidecar(SOURCE)]
    assert box.snapshot() == before


@pytest.mark.parametrize("committed", [True, False], ids=["committed", "uncommitted"])
def test_line6_a_status_line_by_hand_is_fresh(box, committed):
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_d")))
    box.commit("quince: a test")
    box.set_status("2.0.0-alpha.7", 4, seal=False)
    if committed:
        box.commit("quince: the Status lines by hand")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: sidecar written", ok_line("2.0.0-alpha.7", 4)]
    assert box.shasum_ok()


def test_line6_a_merge_that_took_mains_status_line_over_a_rendered_readme(box):
    box.write(SOURCE, source_text(prose="Pears, reworded."))
    box.write(README, readme_text(prose="Pears, reworded and rendered."))
    box.seal()
    box.commit("quince: a render")
    box.git("checkout", "-q", "main")
    box.write(TESTS, pear_tests(("test_a", "test_b", "test_c", "test_d")))
    box.set_status("2.0.0-alpha.7", 4)
    box.commit("main: a test")
    box.git("checkout", "-q", "quince")
    box.git("merge", "-q", "--no-edit", "main", ok=1)
    box.git("checkout", "--theirs", "--", SIDECAR)
    box.commit("Merge main into quince")
    assert box.read(README) == readme_text(count=4, prose="Pears, reworded and rendered.")
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: sidecar written", ok_line("2.0.0-alpha.7", 4)]
    assert box.shasum_ok()


# 7: the NICE file's size.

def nice_row(ident, level, length):
    row = "| %s | %s | `pear.py` | %%s | e | 2026-01-01, a builder |\n" % (ident, level)
    return row % ("f" * (length - len(row % "")))


def nice_text(size, s4=("n4", "n6", "n9")):
    """NICE_HEAD, S3 rows, then the S4 rows of 300 B each, `size` bytes in all."""
    tail = "".join(nice_row(i, "S4", 300) for i in s4)
    room = size - len(NICE_HEAD) - len(tail)
    rows, k = [], 100
    while room > 600:
        rows.append(nice_row("n%d" % k, "S3", 350))
        room -= 350
        k += 1
    rows.append(nice_row("n%d" % k, "S3", room))
    text = NICE_HEAD + "".join(rows) + tail
    assert len(text.encode()) == size
    return text


def test_line7_s4_rows_move_until_the_file_is_under_the_bound(box):
    # 310 B over: without n4 it is 10 B over the bound, without n6 too it is under
    box.write(NICE, nice_text(24576 + 310))
    box.commit("quince: a full NICE file")
    nice = box.read(NICE)
    n4 = next(l for l in nice.splitlines(True) if l.startswith("| n4 "))
    n6 = next(l for l in nice.splitlines(True) if l.startswith("| n6 "))
    p = box.stamp()
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["stamp: moved n4, n6 to history/NICE-overflow.md",
                                     ok_line("2.0.0-alpha.7", 3)]
    assert box.read(NICE) == nice.replace(n4, "").replace(n6, "")
    assert len(box.read(NICE).encode()) < 24576
    first = OVERFLOW_TEXT.index("\n\n## Borrowed") + 1
    assert box.read(OVERFLOW) == OVERFLOW_TEXT[:first] + n4 + n6 + OVERFLOW_TEXT[first:]
    lint = subprocess.run([sys.executable, str(ROOT / "scripts" / "recordlint")], cwd=box.repo,
                          capture_output=True, text=True)
    assert lint.returncode == 0, lint.stdout


def test_line7_under_the_bound_nothing_moves(box):
    box.write(NICE, nice_text(24575))
    box.commit("quince: a NICE file a byte under")
    before = box.snapshot()
    p = box.stamp()
    assert (p.returncode, p.stdout.splitlines()) == (0, [ok_line("2.0.0-alpha.7", 3, True)])
    assert box.snapshot() == before


def test_line7_no_s4_row_left_is_red(box):
    box.write(NICE, nice_text(24600, s4=()))
    box.commit("quince: a full NICE file, no S4 row")
    before = box.snapshot()
    p = box.stamp()
    assert p.returncode == 1
    assert p.stderr.splitlines() == [
        "stamp: red nice: NICE_TO_HAVE.md is 24,600 B and no S4 row is left to move; the bound "
        "is under 24,576 B"]
    assert box.snapshot() == before


def test_line7_no_overflow_table_is_exit_2(box):
    box.write(NICE, nice_text(24576))
    box.write(OVERFLOW, "# NICE overflow: pear\n\nNo table.\n")
    box.commit("quince: no overflow table")
    before = box.snapshot()
    assert "NICE-overflow.md" in exit_two(box.stamp())
    assert box.snapshot() == before


# 8: exit 2.

def test_line8_no_base_is_exit_2(box):
    before = box.snapshot()
    assert "nosuch" in exit_two(box.stamp("--base", "nosuch"))
    assert box.snapshot() == before


def test_line8_two_status_lines_is_exit_2(box):
    box.write(README, box.read(README) + status("2.0.0-alpha.7", 3) + "\n")
    box.seal()
    box.commit("quince: two Status lines")
    before = box.snapshot()
    assert README in exit_two(box.stamp())
    assert box.snapshot() == before


def test_line8_no_work_tree_is_exit_2(box, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    exit_two(box.stamp(repo=plain))
    assert list(plain.iterdir()) == []


def test_line8_an_unknown_flag_is_exit_2(box):
    before = box.snapshot()
    assert "--frobnicate" in exit_two(box.stamp("--frobnicate"))
    assert box.snapshot() == before


# 9: the Makefile, and this repo's own files read as the stamp reads them.

def test_line9_the_makefile_target():
    make = (ROOT / "Makefile").read_text()
    assert re.search(r"^STAMP_BASE \?= main$", make, re.M)
    recipe = re.search(r"^stamp:.*## .*\n\t(.*)\n", make, re.M)
    assert recipe, "no stamp target with a ## line"
    assert recipe.group(1).startswith('$(PYTHON) scripts/stamp --base "$(STAMP_BASE)"')
    assert '--version "$(STAMP_VERSION)"' in recipe.group(1)
    assert " stamp " in " %s " % make.splitlines()[0].replace(".PHONY:", "")


def test_line9_the_readers_find_this_repos_files():
    stamp = load("stamp_under_test", STAMP)
    recordlint = load("recordlint_under_test", ROOT / "scripts" / "recordlint")
    assert stamp.NICE_CAP == recordlint.CAPS[recordlint.NICE]
    assert stamp.STATUS.pattern == README_STATUS.pattern
    for rel in (SOURCE, README):
        assert stamp.status_match((ROOT / rel).read_text(), rel)
    overflow = (ROOT / OVERFLOW).read_bytes()
    at = stamp.overflow_insert_at(overflow)
    before = overflow[:at].decode().splitlines()
    assert before[-1].startswith("| n") and "## From the open findings" in before
    assert overflow[at:].startswith(b"\n## ")


def test_line9_the_version_order_is_the_checks():
    stamp = load("stamp_under_test", STAMP)
    check = load("pvc_under_test", ROOT / "scripts" / "plugin-version-check")
    versions = ["2.0.0", "2.0.0-alpha", "2.0.0-alpha.7", "2.0.0-alpha.10", "2.0.0-beta",
                "2.1.0", "10.0.0", "2.0.0+b1", "next", "2.0", "2.0.0-alpha.07"]
    for v in versions:
        assert stamp.precedence(v) == check.precedence(v), v
