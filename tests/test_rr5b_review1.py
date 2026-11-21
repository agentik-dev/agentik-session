"""Packet rr5b, review 1's round: `records.inside` judged by the file system (F2), the
printed command of `since_landing` quoted (F3), a link in the clone to a record refused (F1),
and the half's line. Every name is made up and every repository a test commits in is the
test's own."""

import os
import subprocess
from pathlib import Path

import pytest

from claude_session import records
from claude_session.reconcile import live

from test_rr5b_two_commits import CHARTER, KEY, World, git, make, run  # noqa: F401


def broken(w, root):
    git(w.clone, "config", KEY, str(root / "nowhere" / "demo"))
    records.reset()


def refused_by_state(rc, err):
    return (rc == 2 and "refused:" not in err and len(err.strip().splitlines()) == 1
            and "does not resolve" in err)


# ---- F2: `records.inside` by file identity --------------------------------------------------

def test_rr5b_f2_a_clone_folder_spelled_in_another_case_is_inside(make, tmp_path):
    root = Path(os.path.realpath(tmp_path))
    w = make("own")
    if not os.path.exists(str(root / "DEMO")):
        pytest.skip("this file system tells letter case apart, so DEMO is no other spelling")
    broken(w, root)
    (w.clone / "probe.md").write_text("not a charter\n")
    spelled = str(root / "DEMO" / "probe.md")
    assert records.inside(records.answer(str(w.clone)), spelled, str(w.clone))
    rc, out, err = run("charter", "check", spelled)
    assert refused_by_state(rc, err), (rc, out, err)
    rc, out, err = run("charter", "check", "--dir", str(root / "DEMO" / "history"), spelled)
    assert refused_by_state(rc, err), (rc, out, err)


def test_rr5b_f2_a_symlinked_parent_is_judged_by_identity(make, tmp_path):
    root = Path(os.path.realpath(tmp_path))
    w = make("own")
    (root / "alias").symlink_to(w.clone, target_is_directory=True)
    (root / "far").mkdir()
    (root / "far" / "probe.md").write_text("not a charter\n")
    (w.clone / "probe.md").write_text("not a charter\n")
    via = str(root / "alias" / "probe.md")
    assert records.inside(None, via, str(w.clone))
    assert records.inside(None, str(root / "alias" / "missing" / "new.md"), str(w.clone))
    assert not records.inside(None, str(root / "far" / "probe.md"), str(w.clone))
    broken(w, root)
    rc, out, err = run("charter", "check", via)
    assert refused_by_state(rc, err), (rc, out, err)
    rc, out, err = run("charter", "check", str(root / "far" / "probe.md"))
    assert rc == 2 and "refused:" in err and "agentik.records" not in err, (rc, out, err)


def test_rr5b_f2_a_path_whose_stat_fails_all_the_way_up_reads_as_inside(make, tmp_path,
                                                                         monkeypatch):
    root = Path(os.path.realpath(tmp_path))
    w = make("own")
    far = str(root / "far" / "probe.md")
    assert not records.inside(None, far, str(w.clone))
    clone = os.stat(str(w.clone))

    def stat(p, *a, **k):
        if os.path.realpath(str(p)) == str(w.clone):
            return clone
        raise OSError("no stat")
    monkeypatch.setattr(records.os, "stat", stat)
    assert records.inside(None, far, str(w.clone))
