"""Packet rr5c R4 and R5: `scripts/stamp` in a tree that declares its records out, and
`scripts/doclint --repo` over a subfolder of a work tree. Every name is made up and every
repository is the test's own."""

import subprocess
import sys
from pathlib import Path

from test_doclint import CHARTER
from test_land3_stamp import NICE, OVERFLOW, box, exit_two, ok_line  # noqa: F401  (fixture)

DOCLINT = Path(__file__).resolve().parents[1] / "scripts" / "doclint"


def declare(box):
    box.write(".hygiene-allow", "records: out\n")
    box.git("rm", "-q", NICE, OVERFLOW)
    box.git("add", ".hygiene-allow")
    box.git("commit", "-qm", "the records move out")


# ---- acceptance 3 (R4): stamp -----------------------------------------------------------------

def test_rr5c_a3_a_declaring_tree_with_no_wish_list_stamps_the_rest(box):
    declare(box)
    box.write("plugin/lib/pear.py", "def pear():\n    return 2\n")
    p = box.stamp()
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert p.stdout.splitlines()[0] == "stamp: version 2.0.0-alpha.7 -> 2.0.0-alpha.8"
    assert p.stdout.splitlines()[-1] == ok_line("2.0.0-alpha.8", 3)
    assert "moved" not in p.stdout
    assert not (box.repo / NICE).exists() and not (box.repo / OVERFLOW).exists()


def test_rr5c_a3_a_declaring_tree_moves_no_row_of_a_big_wish_list(box):
    declare(box)
    big = "# NICE_TO_HAVE: pear\n\n| id | sev | where | what | e | when |\n|---|---|---|---|---|---|\n"
    big += "".join(f"| n{i} | S4 | `pear.py` | {'a row ' * 40} | e | 2026-01-01 |\n"
                   for i in range(1, 120))
    box.write(NICE, big)                                  # untracked, over the bound
    p = box.stamp()
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert "moved" not in p.stdout and box.read(NICE) == big


def test_rr5c_a3_a_tree_that_does_not_declare_stops_for_no_wish_list(box):
    box.git("rm", "-q", NICE)
    box.git("commit", "-qm", "no wish list")
    line = exit_two(box.stamp())
    assert line.startswith("stamp: no NICE_TO_HAVE.md")


def test_rr5c_a3_an_uncommitted_declaration_declares_nothing(box):
    box.git("rm", "-q", NICE)
    box.git("commit", "-qm", "no wish list")
    box.write(".hygiene-allow", "records: out\n")
    exit_two(box.stamp())


# ---- acceptance 4 (R5): doclint over a subfolder ----------------------------------------------

def doclint(repo):
    return subprocess.run([sys.executable, str(DOCLINT), "--repo", str(repo)],
                          capture_output=True, text=True, timeout=120)


def test_rr5c_a4_doclint_over_a_holders_subfolder_names_the_red_charter_by_its_path(tmp_path):
    hold = tmp_path / "hold"
    sub = hold / "repos" / "tool"
    sittings = sub / "history" / "sittings"
    sittings.mkdir(parents=True)
    subprocess.run(["git", "-C", str(hold), "init", "-q"], check=True)
    (sittings / "2026-01-01-1.md").write_text(CHARTER)
    (sittings / "2026-01-01-2.md").write_text(CHARTER + "x" * 4096)
    (hold / "history" / "sittings").mkdir(parents=True)
    (hold / "history" / "sittings" / "2026-01-01-3.md").write_text(CHARTER + "x" * 4096)
    p = doclint(sub)
    assert p.returncode == 2, (p.stdout, p.stderr)
    assert p.stdout.splitlines() and all(
        l.startswith("history/sittings/2026-01-01-2.md: charter:") for l in p.stdout.splitlines())
    top = doclint(hold)                                   # the pin: the top's own charters
    assert top.returncode == 2
    assert all(l.startswith("history/sittings/2026-01-01-3.md: charter:")
               for l in top.stdout.splitlines())


def test_rr5c_a4_doclint_in_a_tree_whose_records_are_out_finds_none_and_passes(tmp_path):
    clone = tmp_path / "clone"
    (clone / "plugin").mkdir(parents=True)
    subprocess.run(["git", "-C", str(clone), "init", "-q"], check=True)
    (clone / ".hygiene-allow").write_text("records: out\n")
    (clone / "plugin" / "x.py").write_text("x = 1\n")
    p = doclint(clone)
    assert p.returncode == 0 and p.stdout == "", (p.stdout, p.stderr)
