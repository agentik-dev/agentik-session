"""plugin/scripts/record: the map, sections by index, range, list and prefix,
the read cap and its split, the exits, and fenced code that is not a heading."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugin" / "scripts" / "record"

DOC = """preamble, not a section
# Title
intro
## §1 One
one body
```
## not a heading, fenced
```
## §2 Two
two body
### §2.1 Two point one
deep body
## §24 Twenty-four
tail
## §9 Dup
a
## §9 Dup again
b
"""


def run(*args):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
    return p.returncode, p.stdout.decode("utf-8"), p.stderr.decode("utf-8")


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "r.md")
        Path(self.path).write_text(DOC, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def map(self):
        code, out, _ = run(self.path, "--sections", "--json")
        self.assertEqual(code, 0)
        return json.loads(out)

    def test_map_rows_levels_lines_bytes(self):
        m = self.map()
        heads = [(s["index"], s["level"], s["heading"], s["line"]) for s in m["sections"]]
        self.assertEqual(heads, [(1, 1, "Title", 2), (2, 2, "§1 One", 4), (3, 2, "§2 Two", 9),
                                 (4, 3, "§2.1 Two point one", 11), (5, 2, "§24 Twenty-four", 13),
                                 (6, 2, "§9 Dup", 15), (7, 2, "§9 Dup again", 17)])
        self.assertEqual(m["bytes"], len(DOC.encode("utf-8")))
        one = "## §1 One\none body\n```\n## not a heading, fenced\n```\n"
        self.assertEqual(m["sections"][1]["bytes"], len(one.encode("utf-8")))
        code, out, _ = run(self.path, "--sections")
        self.assertEqual(code, 0)
        self.assertIn("7 sections", out.splitlines()[0])

    def test_section_verbatim_under_one_header(self):
        code, out, _ = run(self.path, "--section", "3")
        self.assertEqual(code, 0)
        header, body = out.split("\n", 1)
        self.assertTrue(header.startswith("==> ") and "section 3" in header)
        self.assertEqual(body, "## §2 Two\ntwo body\n### §2.1 Two point one\ndeep body\n")

    def test_prefix_is_word_bounded(self):
        code, out, _ = run(self.path, "--section", "§2")
        self.assertEqual(code, 0)
        self.assertIn("section 3 ", out)          # §2 and its own §2.1 wins, not §24
        code, out, _ = run(self.path, "--section", "§24")
        self.assertEqual((code, out.count("==>")), (0, 1))
        self.assertIn("tail\n", out)

    def test_list_and_range(self):
        code, out, _ = run(self.path, "--section", "2,5")
        self.assertEqual((code, out.count("==>")), (0, 2))
        code, out, _ = run(self.path, "--section", "2-4", "--json")
        self.assertEqual([s["index"] for s in json.loads(out)["sections"]], [2, 3, 4])

    def test_usage_exits_2(self):
        self.assertIn("name a section", run(self.path)[2])
        self.assertEqual(run(self.path)[0], 2)
        for spec in ("0", "8", "§99", "4-2", "§9 Dup,"):
            self.assertEqual(run(self.path, "--section", spec)[0], 2, spec)
        code, _, err = run(self.path, "--section", "§9")
        self.assertEqual(code, 2)
        self.assertIn("ambiguous", err)
        self.assertEqual(run(self.path + ".missing", "--sections")[0], 2)

    def test_ceiling_exits_3_naming_size_and_split(self):
        code, out, err = run(self.path, "--section", "3", "--max-bytes", "20")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("over --max-bytes 20", err)
        self.assertIn("4 '§2.1 Two point one'", err)
        code, out, _ = run(self.path, "--section", "3", "--max-bytes", "20", "--force")
        self.assertEqual(code, 0)
        self.assertIn("deep body", out)

    def big(self, n=3, each=4000):
        path = Path(self.tmp.name) / "big.md"
        path.write_text("".join("## §%d S\n%s\n" % (i, "z" * each) for i in range(1, n + 1)))
        return str(path)

    def test_request_total_capped(self):
        """ADV6-8: sections each under the cap, summed over it, refused unless --force."""
        path = self.big()
        code, out, err = run(path, "--section", "1-3")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("summed", err)
        self.assertEqual(run(path, "--section", "1,2")[0], 0)
        code, out, _ = run(path, "--section", "1-3", "--force")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("z" * 4000), 3)

    def test_max_bytes_over_default_needs_force(self):
        path = self.big()
        code, out, err = run(path, "--section", "1-3", "--max-bytes", "999999999")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("--force", err)
        self.assertEqual(run(path, "--section", "1-3", "--max-bytes", "999999999",
                             "--force")[0], 0)
        self.assertEqual(run(path, "--section", "1", "--max-bytes", "8192")[0], 0)

    def test_the_two_copies_are_identical(self):
        root = SCRIPT.parents[2]
        self.assertEqual((root / "scripts" / "record").read_bytes(), SCRIPT.read_bytes())


if __name__ == "__main__":
    unittest.main()
