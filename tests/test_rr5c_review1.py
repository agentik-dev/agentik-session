"""Packet rr5c, review 1's round: R6 lints exactly the charters the holder's commit would take,
named or through a folder above them (F1, L1, L2). Every name is made up and every repository
a test commits in is the test's own. R7b judges the paths the clone's commit would take, as the
core spells and takes them (F2, F3)."""

import os
from pathlib import Path

import pytest

from test_rr5b_two_commits import CHARTER, KEY, counter, git, make, run  # noqa: F401
from test_rr5c_commit import declare_or_break

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


# ---- R7b: the paths the clone's commit would take (F2, F3) ------------------------------------

def refused(w, err, head):
    assert w.head(w.clone) == head, err
    assert "a record path in the clone" in err and KEY in err and "nothing committed" in err


@pytest.mark.parametrize("state", ["unset", "broken"])
def test_rr5c_r2_a_record_named_through_a_link_above_the_clone_is_refused(make, tmp_path, state):
    w = make("own")
    root = Path(os.path.realpath(tmp_path))
    declare_or_break(w, state, root)
    (root / "via").symlink_to(root, target_is_directory=True)  # a link above the clone
    f = w.clone / "history" / "x.md"
    f.parent.mkdir(parents=True)
    f.write_text("a record\n")
    spelled = str(root / "via" / "demo" / "history" / "x.md")
    head = w.head(w.clone)
    rc, out, err = run("checkpoint", "--commit", "a.py", spelled, "-m", "cp")
    assert rc == 2, (out, err)
    refused(w, err, head)


@pytest.mark.parametrize("state", ["unset", "broken"])
@pytest.mark.parametrize("name, record", [("design", "design/packets/p.md"),
                                          ("relay", "relay/queue.yaml")])
def test_rr5c_r2_a_folder_named_whole_with_a_record_changed_inside_is_refused(make, tmp_path,
                                                                             state, name, record):
    w = make("own")
    declare_or_break(w, state, Path(os.path.realpath(tmp_path)))
    f = w.clone / record
    f.parent.mkdir(parents=True)
    f.write_text("a record\n")
    head = w.head(w.clone)
    rc, out, err = run("checkpoint", "--commit", "a.py", name, "-m", "cp")
    assert rc == 2, (out, err)
    refused(w, err, head)
    assert record in err


@pytest.mark.parametrize("state", ["unset", "broken"])
def test_rr5c_r2_design_named_whole_with_only_a_file_outside_its_packets_commits(make, tmp_path,
                                                                                state):
    w = make("own")
    old = w.clone / "design" / "packets" / "old.md"           # a record held unchanged
    old.parent.mkdir(parents=True)
    old.write_text("an old packet\n")
    git(w.clone, "add", "design/packets/old.md")
    git(w.clone, "commit", "-qm", "old")
    declare_or_break(w, state, Path(os.path.realpath(tmp_path)))
    (w.clone / "design" / "notes.md").write_text("a design note\n")
    rc, out, err = run("checkpoint", "--commit", "a.py", "design", "-m", "cp")
    assert rc == 0, (out, err)
    assert sorted(w.took(w.clone)) == ["a.py", "design/notes.md"]
