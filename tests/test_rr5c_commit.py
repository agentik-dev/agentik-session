"""Packet rr5c R6 (lead 6) and R7b: `checkpoint --commit` lints a record charter before the
holder's commit, and in `unset` and `broken` refuses a record path in the clone. Every name is
made up and every repository a test commits in is the test's own."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

from claude_session import records

from test_rr5b_two_commits import BODY, CHARTER, KEY, git, make, run  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


# ---- acceptance 5 (R6): the charter's lint before the holder's commit ------------------------

def test_rr5c_a5_a_charter_over_its_bound_is_refused_in_the_holder_the_clones_commit_stands(make):
    w = make("out")
    w.charter.write_text("# Sitting 2026-11-21-1: demo\n" + BODY + "\n## Next act\n"
                         + "x" * 4096 + "\n")
    hold_head = w.head(w.hold)
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), "-m", "cp")
    assert rc == 2, (out, err)
    assert w.took(w.clone) == ["a.py"] and w.head(w.hold) == hold_head
    assert f"{w.charter}: refused: charter is " in err and "4096-byte ceiling" in err
    assert f"the clone's commit stands: {w.head(w.clone)}" in err
    assert "charter check refused it" in err


def test_rr5c_a5_a_red_charter_alone_commits_in_neither(make):
    w = make("out")
    w.charter.write_text("no charter\n")
    heads = (w.head(w.clone), w.head(w.hold))
    rc, out, err = run("checkpoint", "--commit", str(w.charter), "-m", "cp")
    assert rc == 2 and (w.head(w.clone), w.head(w.hold)) == heads
    assert "refused: part 2 (the table) is missing" in err and "nothing recorded" in err


def test_rr5c_a5_a_green_charter_commits_and_a_record_outside_the_folder_is_not_linted(make):
    w = make("out")
    rc, out, err = run("checkpoint", "--commit", "a.py", str(w.charter), str(w.rec / "x.txt"),
                       "-m", "cp")
    assert rc == 0, (out, err)
    assert sorted(w.took(w.hold)) == sorted([f"repos/demo/{CHARTER}", "repos/demo/x.txt"])


# ---- acceptance 6 (R7b): a record path in the clone in `unset` and `broken` -------------------

def declare_or_break(w, state, root):
    if state == "unset":
        (w.clone / ".hygiene-allow").write_text("records: out\n")
        git(w.clone, "add", ".hygiene-allow")
        git(w.clone, "commit", "-qm", "declare")
    else:
        git(w.clone, "config", KEY, str(root / "nowhere" / "demo"))
    records.reset()


@pytest.mark.parametrize("state", ["unset", "broken"])
@pytest.mark.parametrize("name", ["history/sittings/2026-11-21-1.md", "History/x.md",
                                  "design/packets/p.md", "NICE_TO_HAVE.md", "relay/queue.yaml"])
def test_rr5c_a6_r7b_a_record_path_with_a_code_path_is_refused(make, tmp_path, state, name):
    w = make("own")
    declare_or_break(w, state, Path(os.path.realpath(tmp_path)))
    f = w.clone / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("a record\n")
    head = w.head(w.clone)
    rc, out, err = run("checkpoint", "--commit", "a.py", name, "-m", "cp")
    assert rc == 2 and w.head(w.clone) == head, (out, err)
    assert f"{name} is a record path in the clone" in err and "agentik.records" in err
    assert "nothing committed" in err
    rc, out, err = run("checkpoint", "--commit", "a.py", "-m", "cp")
    assert rc == 0 and w.took(w.clone) == ["a.py"], (out, err)


def test_rr5c_a6_r7b_own_commits_a_record_path_in_the_clone_as_at_the_pin(make):
    w = make("own")
    (w.clone / "HANDOFF.md").write_text("the order\n")
    rc, out, err = run("checkpoint", "--commit", "a.py", "HANDOFF.md", "-m", "cp")
    assert rc == 0 and sorted(w.took(w.clone)) == ["HANDOFF.md", "a.py"], (out, err)


def test_rr5c_a6_r7b_the_list_is_the_scanners():
    loader = importlib.machinery.SourceFileLoader("hygiene_r7b", str(ROOT / "scripts" / "hygiene"))
    spec = importlib.util.spec_from_loader("hygiene_r7b", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    assert records.RECORD_DIRS == mod.RECORD_DIRS and records.RECORD_FILES == mod.RECORD_FILES
