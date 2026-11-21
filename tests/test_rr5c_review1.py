"""Packet rr5c, review 1's round: R6 lints exactly the charters the holder's commit would take,
named or through a folder above them (F1, L1, L2). Every name is made up and every repository
a test commits in is the test's own."""

import pytest

from test_rr5b_two_commits import CHARTER, KEY, counter, git, make, run  # noqa: F401

RED = "history/sittings/2026-11-22-1.md"


# ---- R6: the charters the holder's commit would take (F1, L1, L2) ----------------------------

@pytest.mark.parametrize("named", ["history/sittings", "history", "."])
def test_rr5c_r1_a_red_charter_under_a_named_folder_keeps_the_holders_commit_out(make, named):
    w = make("out")
    red = w.rec / RED
    red.write_text("no charter\n" + "x" * 5000 + "\n")
    hold_head = w.head(w.hold)
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.rec / named), "-m", "cp")
    assert rc == 2, (out, err)
    assert w.head(w.hold) == hold_head and w.took(w.clone) == ["a.py"]
    assert f"{red}: refused: " in err and "charter check refused it" in err
    assert f"the clone's commit stands: {w.head(w.clone)}" in err and "nothing recorded" in err
    assert f"{w.charter}: refused" not in err                  # the green one beside it
    assert counter() == 5


@pytest.mark.parametrize("named", ["file", "folder"])
def test_rr5c_r1_a_file_that_is_no_charter_beside_the_charters_commits(make, named):
    w = make("out")
    notes = w.rec / "history" / "sittings" / "notes.txt"
    notes.write_text("free notes\n")
    target = notes if named == "file" else notes.parent
    rc, out, err = run("checkpoint", "--commit", str(target), "-m", "cp")
    assert rc == 0, (out, err)
    took = sorted(w.took(w.hold))
    want = ["repos/demo/history/sittings/notes.txt"]
    assert took == (want if named == "file" else sorted(want + [f"repos/demo/{CHARTER}"]))
    assert "refused" not in err


def test_rr5c_r1_a_red_charter_the_holder_holds_unchanged_gives_the_pins_lines(make):
    w = make("out")
    w.charter.write_text("# an old charter of another shape\n")
    git(w.hold, "add", f"repos/demo/{CHARTER}")
    git(w.hold, "commit", "-qm", "old")
    hold_head, clone_head = w.head(w.hold), w.head(w.clone)
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 0, (out, err)
    assert "nothing to commit in the records' repository" in out
    assert "checkpoint recorded" in out and counter() == 0
    assert w.head(w.hold) == hold_head and w.head(w.clone) != clone_head
    assert w.took(w.clone) == ["a.py"] and "refused" not in err
