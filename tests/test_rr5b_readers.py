"""Packet rr5b R6 and R7: `charter check FILE` in each state, the respawn's clean check, the close's
commit line and reconcile's `since_landing` where a repo's records live outside its clone. Every
name is made up and every repository a test commits in is the test's own."""

import os
import subprocess
from pathlib import Path

import pytest

from claude_session import cli, records
from claude_session.reconcile import live

from test_rr5b_two_commits import BODY, CHARTER, KEY, World, git, make, run  # noqa: F401

RESPAWN = "# Sitting 2026-11-21-1: demo\n" + BODY + "\n## Next act\nRESPAWN: go on\n"


# ---- acceptance 7 (R6): `charter check FILE` --------------------------------------------------

def broken(w, root):
    git(w.clone, "config", KEY, str(root / "nowhere" / "demo"))


@pytest.mark.parametrize("state", ["own", "out", "unset", "broken"])
@pytest.mark.parametrize("where", ["clone", "outside"])
def test_rr5b_a7_charter_check_file_in_each_state(make, tmp_path, state, where):
    root = Path(os.path.realpath(tmp_path))
    w = make("out" if state == "out" else "own")
    if state == "unset":
        (w.clone / ".hygiene-allow").write_text("records: out\n")
        git(w.clone, "add", ".hygiene-allow")
        git(w.clone, "commit", "-qm", "declare")
    elif state == "broken":
        broken(w, root)
    records.reset()
    f = (w.clone / "probe.md") if where == "clone" else (root / "probe.md")
    f.write_text("not a charter\n")
    rc, out, err = run("charter", "check", str(f))
    if state == "broken" and where == "clone":
        assert rc == 2 and "refused:" not in err and len(err.strip().splitlines()) == 1
        assert "does not resolve" in err and "git config agentik.records <folder>" in err
    else:                                                     # read, as at the pin
        assert rc == 2 and f"{f}: refused:" in err and "agentik.records" not in err


# ---- acceptance 8 (R7): the respawn's clean check --------------------------------------------

@pytest.mark.parametrize("named", [True, False])
def test_rr5b_a8_respawn_commit_with_the_record_charter_named_and_not(make, named):
    w = make("out")
    w.charter.write_text(RESPAWN)
    git(w.hold, "add", f"repos/demo/{CHARTER}")
    git(w.hold, "commit", "-qm", "open")
    w.charter.write_text(RESPAWN + "\nmore\n")
    heads = (w.head(w.clone), w.head(w.hold))
    line = ["a.py"] + ([str(w.charter)] if named else [])
    rc, out, err = run("checkpoint", "--commit", *line, "-m", "cp", "--respawn",
                       "--charter", str(w.charter))
    if named:
        assert rc == 0 and "respawn marked" in out, (out, err)
        assert w.took(w.hold) == [f"repos/demo/{CHARTER}"] and w.took(w.clone) == ["a.py"]
    else:
        assert rc == 2 and "is not committed" in err, (out, err)
        assert (w.head(w.clone), w.head(w.hold)) == heads


def test_rr5b_a8_named_matches_a_record_charter_by_its_real_path(make):
    w = make("out")
    rel = os.path.relpath(w.charter, w.clone)
    assert cli._named(str(w.charter), [rel]) and cli._named(str(w.charter), [str(w.rec)])
    assert not cli._named(str(w.charter), ["a.py", str(w.clone)])


# ---- acceptance 8 (R7): the close's commit line ----------------------------------------------

def test_rr5b_a8_the_close_line_commits_the_charter_alone_from_another_cwd(make, tmp_path):
    w = make("out")                                   # x.txt is staged in the holder: a stranger
    elsewhere = Path(os.path.realpath(tmp_path)) / "elsewhere"
    elsewhere.mkdir()
    line = cli._commit_line(str(w.charter))           # the pin's line already holds: it stands
    p = subprocess.run(line, shell=True, cwd=elsewhere, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert w.took(w.hold) == [f"repos/demo/{CHARTER}"] and w.staged(w.hold) == ["repos/demo/x.txt"]
    assert w.staged(w.clone) == ["s.txt"]


def test_rr5b_a8_a_close_with_no_holder_says_nothing_is_committed(make):
    w = make("plain")
    rc, out, err = run("charter", "open", "a demo goal")
    assert rc == 0, err
    f = Path(out.strip())
    assert f.parent == w.rec / "history" / "sittings"
    rc, out, err = run("charter", "close", str(f), "--exit", "goal met")
    assert rc == 0, (out, err)
    said = [l for l in out.splitlines() if "nothing is committed" in l]
    assert len(said) == 1 and "no repository" in said[0] and "git -C" not in out


def test_rr5b_a8_a_close_in_own_prints_the_pins_line(make):
    w = make("own")
    rc, out, err = run("charter", "open", "a demo goal")
    f = w.clone / out.strip()
    rc, out, err = run("charter", "close", str(f), "--exit", "goal met")
    assert rc == 0 and out.splitlines()[1] == f"next: {cli._commit_line(str(f))}"
    assert "nothing is committed" not in out


# ---- acceptance 8 (R7): reconcile's since_landing --------------------------------------------

class Readers:
    def __init__(self):
        self.calls = []

    def git(self, repo, *args):
        self.calls.append((str(repo), args))
        return ""


def landing(hq):
    r = Readers()
    ctx = {"hq": os.path.basename(str(hq)), "roots": {"hq": str(hq), "repos": str(hq.parent)},
           "window": 14, "now": 2_000_000_000, "goal": [], "readers": r, "threshold": 5}
    return live.since_landing(ctx), r


def test_rr5b_a8_since_landing_in_own_runs_the_pins_command(make):
    w = make("own")
    f, r = landing(w.clone)
    since = 2_000_000_000 - 14 * 86400
    assert f["evidence"]["command"] == (
        "git -C %s log --since=@%d --diff-filter=A --name-only --format= -- history/sittings"
        " | grep -E '/%s' | sort -u | wc -l" % (live.sh(str(w.clone)), since, live.NAME_ERE))
    assert r.calls[0] == (str(w.clone), ("log", "--since=@%d" % since, "--diff-filter=A",
                                         "--name-only", "--format=", "--", "history/sittings"))


def test_rr5b_a8_since_landing_in_out_runs_its_log_in_the_holder(make):
    w = make("out")
    f, r = landing(w.clone)
    since = 2_000_000_000 - 14 * 86400
    assert f["evidence"]["command"] == (
        "git -C %s log --since=@%d --diff-filter=A --name-only --format= -- "
        "'repos/demo/history/sittings' | grep -E '/%s' | sort -u | wc -l"
        % (live.sh(str(w.hold)), since, live.NAME_ERE))
    assert r.calls[0] == (str(w.hold), ("log", "--since=@%d" % since, "--diff-filter=A",
                                        "--name-only", "--format=", "--",
                                        "repos/demo/history/sittings"))
