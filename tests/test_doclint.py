"""scripts/doclint: each rule refuses its fixture, a clean repo passes."""
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doclint"

CHARTER = """# Sitting 2026-01-01-1: repo, component

| item | value |
|---|---|
| goal | g |
| budget | b |
| pin | p |
| window | w |
| agents | a |

## Done-ness
- [x] done

## Handover
- none

## Next act
none
"""

PACKET = """# Packet X: a fixture

| item | value |
|---|---|
| from | f |
| pin | p |
| wall | w |
| may touch | m |
| acceptance | a |
| budget | b |
| verify | `make check` |

## 1. What the source says (quoted)
## 2. Rulings
## 3. Interfaces (signatures, not prose)
## 4. Findings that name this row
## 5. Forbidden reads
## 6. Report (capped)
"""

COMMAND = "---\ndescription: d\nallowed-tools: Bash\n---\nbody\n"
AGENT = "---\nname: n\ndescription: d\nmodel: m\ntools: Read\n---\nbody\n"


def run(repo, *args):
    p = subprocess.run([str(SCRIPT), "--repo", repo, *args] if repo else [str(SCRIPT), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.splitlines()


class DoclintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        self.write("history/sittings/2026-01-01-1.md", CHARTER)
        self.write("design/packets/x.md", PACKET)
        self.write("design/research.md", "# r\n")
        self.write("design/notes.md", "[ok](research.md) [web](https://x.test/a) "
                   "[anchor](#top) [sec](packets/x.md#1) `[code](nowhere.md)`\n"
                   "```\n[fenced](nowhere.md)\n```\n")

    def tearDown(self):
        self.tmp.cleanup()

    def fresh(self):
        """A new temp repo, so a folded case runs as its own test did (the count stays)."""
        self.tearDown()
        self.setUp()

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def refusals(self):
        code, lines = run(str(self.repo))
        return code, lines

    def test_clean_repo_passes(self):
        self.assertEqual(self.refusals(), (0, []))

    def _charter_over_ceiling(self):
        self.write("history/sittings/2026-01-01-1.md", CHARTER + "x" * 4096)
        code, lines = self.refusals()
        self.assertEqual(code, 2)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("history/sittings/2026-01-01-1.md: charter: "))

    def test_charter_shape(self):
        self._charter_over_ceiling()
        self.fresh()
        bad = CHARTER.replace("| window | w |\n", "").replace("## Next act\n", "")
        self.write("history/sittings/2026-01-01-1.md", bad.replace("# Sitting", "# Sat"))
        code, lines = self.refusals()
        self.assertEqual(code, 2)
        self.assertEqual([l.split(": ", 2)[2].split(":")[0] for l in lines],
                         ["title is not `# Sitting <date>-<n>", "table row missing",
                          "part missing"])

    def test_packet_missing_section_and_row(self):
        self._malformed_packet_does_not_crash()
        self.fresh()
        self.write("design/packets/x.md",
                   PACKET.replace("## 5. Forbidden reads\n", "").replace("| wall | w |\n", ""))
        code, lines = self.refusals()
        self.assertEqual(code, 2)
        self.assertEqual(lines, ["design/packets/x.md: packet: header row missing: wall",
                                 "design/packets/x.md: packet: section missing: "
                                 "## 5. Forbidden reads"])
        # a verify row is required outside GRANDFATHERED (ADV10-4)
        self.write("design/packets/x.md", PACKET)
        self.assertEqual(self.acceptance("`make check; echo $?` reads 0", verify=False),
                         (2, ["design/packets/x.md: packet: verify row missing"]))
        self.write("design/packets/x.md", PACKET)
        self.assertEqual(self.acceptance("`make check` reads 0", verify=False,
                                         name="s1-hygiene.md"), (0, []))

    def test_packet_and_record_ceilings(self):
        self._review_ceiling()
        self.fresh()
        self.write("design/packets/x.md", PACKET + "x" * 9216)
        self.write("design/conventions.md", "x" * 9216)
        code, lines = self.refusals()
        self.assertEqual(code, 2)
        self.assertEqual([l.split(": ")[:2] for l in lines],
                         [["design/packets/x.md", "packet"], ["design/conventions.md", "size"]])

    def _review_ceiling(self):
        self.write("design/review-r9.md", "x" * 9215)
        self.assertEqual(self.refusals(), (0, []))
        self.write("design/review-r9.md", "x" * 9216)
        self.assertEqual(self.refusals(),
                         (2, ["design/review-r9.md: size: 9216 bytes, ceiling 9216"]))

    def acceptance(self, cell, verify=True, name="x.md"):
        text = PACKET.replace("| acceptance | a |", "| acceptance | %s |" % cell)
        if not verify:
            text = text.replace("| verify | `make check` |\n", "")
        self.write("design/packets/" + name, text)
        return self.refusals()

    def _acceptance_suite_refused(self):
        code, lines = self.acceptance(
            "`make check; echo $?` reads 0; `go test ./... 2>&1 \\| tail -1` reads ok; "
            "`.venv/bin/python -m pytest -q` passes; `pytest -x` too; "
            "`relay plan x.md` and `cd a && make -C . test`")
        self.assertEqual(code, 2)
        self.assertEqual([l.rsplit(": ", 1)[1] for l in lines],
                         ["make check", "go test ./... 2>&1", ".venv/bin/python -m pytest -q",
                          "pytest -x", "relay plan x.md", "make -C . test"])
        self.assertTrue(all(": packet: acceptance runs a whole suite: " in l for l in lines))

    def _acceptance_targeted_passes(self):
        cell = ("`pytest -q tests/test_a.py` reads passed; `go test ./cmd/x -run TestX` ok; "
                "`printf '\\|verify\\|make check\\|' > f` ok; "
                "`python -m pytest -k 'x' tests` ok; `grep -c 'make test' Makefile` reads 1")
        self.assertEqual(self.acceptance(cell), (0, []))

    def test_suite_rule_sees_through_wrappers(self):
        self._acceptance_suite_refused()
        self.fresh()
        self._acceptance_targeted_passes()
        self.fresh()
        cells = ["timeout 900 make check", "env make check", "nice make check",
                 "uv run pytest", "python3 -m pytest tests", "pytest .",
                 "scripts/bounded --wall 900 -- make check", "sh -c 'make check'",
                 "go test -race ./internal/... ./cmd/...", "make check",
                 "FOO=1 env -u X nice -n 5 nohup time command exec timeout -s KILL 9 make test",
                 "bash -c \"cd x && pytest ./tests/\""]
        code, lines = self.acceptance("; ".join("`%s`" % c for c in cells))
        self.assertEqual(code, 2)
        self.assertEqual(len(lines), len(cells), lines)
        targeted = ["pytest tests -k x", "pytest tests/test_a.py::T", "pytest tests/test_a.py -m slow",
                    "go test -run TestX ./cmd/x", "sh -c 'pytest tests/test_a.py'",
                    "timeout 9 grep -c 'make' Makefile", "env A=1 printf 'make check'"]
        self.assertEqual(self.acceptance("; ".join("`%s`" % c for c in targeted)), (0, []))

    def _malformed_packet_does_not_crash(self):
        self.write("design/packets/x.md",
                   "|a|b|\n|-|-|\n|verify|make check|\n|acceptance|make check; go test ./...|\n")
        code, lines = self.refusals()
        self.assertEqual(code, 2)
        self.assertEqual(sum("runs a whole suite" in l for l in lines), 2)

    def _plugin_command_refused(self):
        self.write("plugin/commands/a.md", "---\ndescription: d\n---\nbody\n")
        self.write("plugin/commands/b.md", COMMAND + "x\n" * 26)
        code, lines = self.refusals()
        self.assertEqual((code, lines),
                         (2, ["plugin/commands/a.md: plugin: frontmatter lacks allowed-tools",
                              "plugin/commands/b.md: plugin: 31 lines, ceiling 31"]))

    def _plugin_agent_refused(self):
        self.write("plugin/agents/x.md", AGENT.replace("model: m\n", ""))
        code, lines = self.refusals()
        self.assertEqual((code, lines),
                         (2, ["plugin/agents/x.md: plugin: frontmatter lacks model"]))

    def test_plugin_skill(self):
        self._plugin_command_refused()
        self.fresh()
        self._plugin_agent_refused()
        self.fresh()
        self._plugin_clean()
        self.fresh()
        # at the ceilings: a 200-char block description (joined by spaces), 500 body lines
        block = "description: >\n  " + "x" * 99 + "\n  " + "y" * 100 + "\n"
        self.write("plugin/skills/ok/SKILL.md",
                   "---\nname: ok\n" + block + "allowed-tools:\n  - Read\n---\n" + "b\n" * 500)
        self.assertEqual(self.refusals(), (0, []))
        self.write("plugin/skills/a/SKILL.md",
                   "---\nname: a\ndescription: " + "x" * 201 + "\nallowed-tools: x\n---\n"
                   + "b\n" * 501)
        self.write("plugin/skills/b/SKILL.md", "---\nname: b\ndescription: |\n  " + "x" * 150
                   + "\n  " + "y" * 50 + "\n---\nbody\n")
        self.assertEqual(self.refusals(),
                         (2, ["plugin/skills/a/SKILL.md: plugin: description 201 chars, ceiling 200",
                              "plugin/skills/a/SKILL.md: plugin: 501 body lines, ceiling 500",
                              "plugin/skills/b/SKILL.md: plugin: frontmatter lacks allowed-tools",
                              "plugin/skills/b/SKILL.md: plugin: description 201 chars, ceiling 200"]))

    def _plugin_clean(self):
        # a plugin's verb set is its own: any names pass
        self.write("plugin/commands/anything.md", COMMAND + "x\n" * 25)
        self.write("plugin/agents/x.md", AGENT)
        self.assertEqual(self.refusals(), (0, []))

    def test_dangling_link(self):
        self._next_file()
        self.fresh()
        self._next_exempt_under_history_sessions()
        self.fresh()
        self.write("README.md", "see [gone](design/gone.md#x)\n")
        code, lines = self.refusals()
        self.assertEqual((code, lines),
                         (2, ["README.md: link: line 1 does not resolve: design/gone.md"]))

    def _next_file(self):
        self.write("NEXT", "phase\n")
        self.write("history/NEXT", "phase\n")
        code, lines = self.refusals()
        self.assertEqual((code, lines), (2, ["NEXT: next: a NEXT file is present",
                                             "history/NEXT: next: a NEXT file is present"]))

    def _next_exempt_under_history_sessions(self):
        """ADV6-4: the relay's safe-next-phase file, untracked or tracked, is not refused."""
        self.write("history/sessions/NEXT", "phase\n")
        self.assertEqual(self.refusals(), (0, []))
        subprocess.run(["git", "-C", str(self.repo), "add", "history/sessions/NEXT"], check=True)
        self.assertEqual(self.refusals(), (0, []))

    def _ignored_files_are_not_linted(self):
        self.write(".gitignore", "scratch/\n")
        self.write("scratch/NEXT", "x\n")
        self.assertEqual(self.refusals(), (0, []))

    def test_usage_and_git_failure(self):
        self._ignored_files_are_not_linted()
        self.fresh()
        self.assertEqual(run(str(self.repo), "extra")[0], 1)
        with tempfile.TemporaryDirectory() as notgit:
            self.assertEqual(run(notgit)[0], 1)


if __name__ == "__main__":
    unittest.main()


# agent-relay's internal/packet/packet.go `legacy`, the seventeen pre-AR10 stems
RELAY_LEGACY = ("a3-machine", "a4-schemas", "a5-effects-plan", "a6-stage-gate",
                "a7-spawn-stream", "a8-night", "a9-tmux-notify", "ap1-plugin", "ux1-review",
                "ar2-adversarial", "ar3-readme", "ar4-fixes", "ar5-ux",
                "ar6-sync-and-readme", "ar7-fixes", "ar8-resync", "ar9-queue-and-resync")


def doclint_module():
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_loader
    spec = spec_from_loader("doclint", SourceFileLoader("doclint", str(SCRIPT)))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lint_packets(packets):
    """doclint over a temp repo holding {name: (acceptance cell, verify row?)}."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
        (Path(tmp) / "design/packets").mkdir(parents=True)
        for name, (cell, verify) in packets.items():
            text = PACKET.replace("| acceptance | a |", "| acceptance | %s |" % cell)
            if not verify:
                text = text.replace("| verify | `make check` |\n", "")
            (Path(tmp) / "design/packets" / name).write_text(text)
        return run(tmp)


def test_legacy_stems_need_no_verify():
    held = doclint_module().GRANDFATHERED
    assert [s for s in RELAY_LEGACY if s + ".md" not in held] == []
    rowless = {s + ".md": ("`make check` reads 0", False) for s in RELAY_LEGACY}
    assert lint_packets(rowless) == (0, [])
    assert lint_packets({"ar9-queue-and-resync-2.md": ("a", False)}) == (
        2, ["design/packets/ar9-queue-and-resync-2.md: packet: verify row missing"])


# agent-relay's internal/packet/packet.go `spent` on its main (9b99873), in its order
RELAY_SPENT = ("ar11-tla-night", "ar12-e2e-night", "ar10-bounded-night", "ar13-fixes-r6",
               "ar14-resync", "ar15-readme-r7", "ar17a-gate-r10", "ar17b-guards-r10",
               "ar17c-bounds-r10", "ar17d-rulings-r10", "ar18-resync", "ar19-resync",
               "ar20-fixes-adv11")


def test_spent_skips_the_suite_rule():
    assert doclint_module().SPENT == tuple(s + ".md" for s in RELAY_SPENT) + (
        "ar21-fixes-adv12.md",)
    spent = {"ar11-tla-night.md": ("`make tla` reads 0", True),
             "ar12-e2e-night.md": ("`make check` reads 0", True)}
    assert lint_packets(spent) == (0, [])
    code, lines = lint_packets({"ar11-tla-night.md": ("`make tla` reads 0", False)})
    assert (code, lines) == (2, ["design/packets/ar11-tla-night.md: packet: verify row missing"])
    code, lines = lint_packets({"ar13-x.md": ("`make check` reads 0", True)})
    assert code == 2 and lines[0].endswith("acceptance runs a whole suite: make check")


# the relay's acceptance cells the suite rule refuses, as its packets wrote them (9b99873)
SPENT_CELLS = [
    ("ar13-fixes-r6.md", r"`for p in gate night effects hooks packet relay; do go test "
     r"./internal/$p -run TestAR13_ -count=1 >/dev/null 2>&1 \|\| exit 1; done; echo ok`"),
    ("ar21-fixes-adv12.md", r"`grep -rl XDG_CONFIG_HOME internal/effects internal/gate "
     r"internal/night cmd/relay \| wc -l`"),
    ("ar10-bounded-night.md", r"""`t=$(mktemp -d) && RELAY_MEASURE_DEPTH=1 XDG_STATE_HOME="$t" """
     r"""go run ./cmd/relay plan --rows ar10-bounded-night > "$t/o" 2>&1; echo "$? """
     r"""$(grep -c 'would open with 1 row; valid$' "$t/o")"`"""),
    ("ar15-readme-r7.md", r"""`<img src="assets/icon.svg" alt="" width="56" align="left">`""")]


@pytest.mark.parametrize("name,cell", SPENT_CELLS, ids=[n[:-3] for n, _ in SPENT_CELLS])
def test_spent_mirrors_the_relay_stems(name, cell):
    assert lint_packets({name: (cell, True)}) == (0, [])
    code, lines = lint_packets({"ar99-x.md": (cell, True)})
    assert code == 2 and lines, lines
    assert all("ar99-x.md: packet: acceptance runs a whole suite: " in l for l in lines), lines


def test_spent_runner_named_directory_takes_a_slash():
    # a later packet names such a directory with a trailing slash (an empty basename)
    cell = r"`grep -rl XDG_CONFIG_HOME internal/night cmd/relay/ \| wc -l`"
    assert lint_packets({"ar99-x.md": (cell, True)}) == (0, [])


@pytest.mark.parametrize("line", [
    "make e2e", "make vet", "make tla", "make", "gmake check", "$(echo make) check",
    "m=make; $m check", "echo 'make check' \\| sh"],
    ids=["make-e2e", "make-vet", "make-tla", "bare-make", "gmake-check",
         "substituted-word", "variable-word", "piped-shell"])
def test_acceptance_shape_refused(line):
    code, lines = lint_packets({"x.md": ("`%s` reads 0" % line, True)})
    # `$(echo make) check` gives two: `$S check`, and `echo make` (a runner word, no goal)
    assert code == 2 and 1 <= len(lines) <= 2, lines
    assert all(": packet: acceptance runs a whole suite: " in l for l in lines), lines


def test_acceptance_shape_allowed():
    controls = ["make doclint hygiene", "make -n record X=y", "sh -c 'true'",
                "make -j 4 -C sub doclint",
                "bash -o pipefail -c 'grep -c x f'", "d=$(mktemp -d); git -C $d init -q",
                "[ -s f ] && echo ok", "echo \"$HOME\" \\| grep -c x"]
    cell = "; ".join("`%s`" % c for c in controls)
    assert lint_packets({"x.md": (cell, True)}) == (0, [])
    # the other refusals Go's packet.Unbounded names: claude, `go run <pkg>/relay`,
    # a shell fed from stdin by -s, a lone -c, a redirection or a here-string
    for line in ["claude -p hi", "go run ./cmd/relay plan x.md", "bash -s", "sh -c",
                 "sh < f", "bash <<< Q", "\"$m\" check", "make check-unlocked",
                 # fail closed (ADV11-4): shapes the denylist passed, refused now
                 "go test ./cmd/x", "relay gate --rows 3 p.md", "pytest . -m slow",
                 "go test -run X ./...", "timeout 9 grep -c make Makefile",
                 "go run ./cmd/relay plan --rows 2 x.md", "go vet ./...", "go vet ./cmd/x",
                 "go build ./cmd/x", "go list ./...",
                 "tox", "nox -s tests", "python3 -m unittest discover", "pytest -k \"$K\""]:
        code, lines = lint_packets({"x.md": ("`%s`" % line, True)})
        assert code == 2 and len(lines) == 1, (line, lines)
    assert lint_packets({"x.md": ("`go test ./cmd/x -run TestX_`; `python3 -m unittest tests.test_a.T.t`",
                                  True)}) == (0, [])


# ADV11-4: the rule fails closed. Its 18 cells (the review's list, three make lines
# among them), then the packet's three home-writing make lines under their own ids.
FAILS_CLOSED = [
    ("caffeinate -i make check", "caffeinate"), ("stdbuf -oL make check", "stdbuf"),
    ("arch -arm64 make check", "arch"), ("xargs make check", "xargs"),
    ("python3 -I -m pytest", "python-isolated"), ("python3 -X dev -m pytest tests", "python-x-dev"),
    ("py.test", "py-dot-test"), ("pytest tests/test_*.py", "pytest-glob"),
    ("pytest tests/..", "pytest-dotdot"), ("pytest ./tests/../tests", "pytest-dotdot-root"),
    ("pytest -k '' tests", "pytest-empty-k"), ("pytest -k 'not zzz'", "pytest-not-k"),
    ("go test -run . ./...", "go-run-dot"), ("go test $(go list ./...)", "go-list-substituted"),
    ("go test all", "go-test-all"), ("make readme", "adv11-make-readme"),
    ("make install", "adv11-make-install"), ("make skill", "adv11-make-skill"),
    ("make readme", "packet-make-readme"), ("make install", "packet-make-install"),
    ("make skill", "packet-make-skill")]


@pytest.mark.parametrize("line", [c for c, _ in FAILS_CLOSED], ids=[i for _, i in FAILS_CLOSED])
def test_suite_rule_fails_closed(line):
    code, lines = lint_packets({"x.md": ("`%s` reads 0" % line, True)})
    assert code == 2 and lines, lines
    assert all(": packet: acceptance runs a whole suite: " in l for l in lines), lines


@pytest.mark.parametrize("line", [
    "pytest tests/test_x.py", "pytest tests/test_x.py::t", "pytest -k 'shape or spent'",
    "go test ./internal/packet -run TestUnbounded", "make doclint hygiene", "make -n check",
    "sh -c 'true'"],
    ids=["pytest-file", "pytest-node", "pytest-k", "go-test-run", "make-targeted",
         "make-dry-run", "sh-c-true"])
def test_suite_rule_targeted_allowed(line):
    assert lint_packets({"x.md": ("`%s` reads 0" % line, True)}) == (0, [])


def test_next_names_a_missing_prompt(tmp_path):
    # the sibling plugin's review, ADV11-6: a NEXT naming a missing prompt is a stop, not a phase
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / "history" / "sessions").mkdir(parents=True)
    (tmp_path / "history" / "sessions" / "NEXT").write_text("\ndesign/packets/nope.md\n")
    code, lines = run(str(tmp_path))
    assert code == 2 and lines == ["history/sessions/NEXT: next: NEXT names a missing prompt"]
    (tmp_path / "history" / "sessions" / "NEXT").write_text("run `docs/next.md` next\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "next.md").write_text("# x\n")
    assert run(str(tmp_path)) == (0, [])
