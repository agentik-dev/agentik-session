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

from test_rr5b_two_commits import (CHARTER, KEY, World, counter, git, make,  # noqa: F401
                                   run)


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


# ---- F3: the printed command of `since_landing` is the one it ran ----------------------------

class Git:
    def git(self, repo, *args):
        p = subprocess.run(["git", "-C", repo, *args], text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        return p.stdout if p.returncode == 0 else None


def test_rr5b_f3_the_printed_command_quotes_a_sittings_folder_with_a_space(make, tmp_path):
    root = Path(os.path.realpath(tmp_path))
    make("own")
    clone = root / "my demo"
    clone.mkdir()
    git(clone, "init", "-q", "-b", "main")
    (clone / "a").write_text("x\n")
    git(clone, "add", "a")
    git(clone, "commit", "-qm", "base")
    hold = root / "hold"
    rec = hold / "repos" / "my demo"
    (rec / "history" / "sittings").mkdir(parents=True)
    (rec / "history" / "sittings" / "2026-11-21-1.md").write_text("# c\n")
    git(hold, "init", "-q", "-b", "main")
    git(hold, "add", ".")
    git(hold, "commit", "-qm", "base")
    git(clone, "config", KEY, str(rec))
    records.reset()
    assert records.state(records.answer(str(clone))) == "out"
    ctx = {"hq": "my demo", "roots": {"hq": str(clone), "repos": str(root)}, "window": 14,
           "now": __import__("time").time(), "goal": [], "readers": Git(), "threshold": 5}
    f = live.since_landing(ctx)
    assert f["value"] == 1, f
    p = subprocess.run(["/bin/sh", "-c", f["evidence"]["command"]], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0 and p.stdout.strip() == "1", (f["evidence"]["command"], p.stdout,
                                                            p.stderr)


# ---- F1, ruled: a link in the clone whose real path is under the records folder ------------

@pytest.mark.parametrize("with_code", [False, True])
def test_rr5b_f1_a_link_in_the_clone_to_a_record_is_refused_before_either(make, with_code):
    w = make("out")
    (w.clone / "link.md").symlink_to(w.charter)
    heads = (w.head(w.clone), w.head(w.hold))
    named = ["a.py", "link.md", str(w.charter)] if with_code else ["link.md"]
    rc, out, err = run("checkpoint", "--commit", *named, "-m", "cp")
    assert rc == 2 and out == "", (out, err)
    assert (w.head(w.clone), w.head(w.hold)) == heads and counter() == 5
    assert w.staged(w.clone) == ["s.txt"] and w.staged(w.hold) == ["repos/demo/x.txt"]
    lines = err.strip().splitlines()
    assert len(lines) == 1 and "link.md" in lines[0] and "symbolic link" in lines[0], err
    assert "would publish the records folder's path" in lines[0], err


def test_rr5b_f1_a_link_under_the_records_folder_into_the_clone_commits_in_the_holder(make):
    w = make("out")
    (w.rec / "back.md").symlink_to(w.clone / "a.py")
    rc, out, err = run("checkpoint", "--commit", str(w.rec / "back.md"), "-m", "cp")
    assert rc == 0, (out, err)
    assert w.took(w.hold) == ["repos/demo/back.md"] and w.staged(w.hold) == ["repos/demo/x.txt"]


def test_rr5b_f1_own_commits_a_link_in_the_clone_as_at_the_pin(make, tmp_path):
    w = make("own")
    far = Path(os.path.realpath(tmp_path)) / "far.md"
    far.write_text("x\n")
    (w.clone / "link.md").symlink_to(far)
    rc, out, err = run("checkpoint", "--commit", "link.md", "-m", "cp")
    assert rc == 0 and w.took(w.clone) == ["link.md"], (out, err)
