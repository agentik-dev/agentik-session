"""Packet rr5c R7: the unattended loop refuses a repo whose records are not in `own`, before
any write and before any process of a run, in one line that names the key, as the relay's
refusal reads. Every name is made up and every repository is the test's own."""

import os
import subprocess
from pathlib import Path

import pytest

from claude_session import records, unattended

from test_rr5b_two_commits import KEY, git, run  # noqa: F401

RELAY_WORDS = ("this repo keeps its records outside its clone (git config agentik.records); "
               "the relay does not run in such a repo yet")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = Path(os.path.realpath(tmp_path))
    r = root / "demo"
    (r / "relay").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    (r / "relay" / "queue.yaml").write_text("rows: []\n")
    git(r, "add", ".")
    git(r, "commit", "-qm", "the queue")

    def to(state):
        if state == "out":
            rec = root / "hold" / "repos" / "demo"
            rec.mkdir(parents=True)
            git(root / "hold", "init", "-q", "-b", "main")
            git(r, "config", KEY, str(rec))
        elif state == "unset":
            (r / ".hygiene-allow").write_text("records: out\n")
            git(r, "add", ".hygiene-allow")
            git(r, "commit", "-qm", "declare")
        elif state == "broken":
            git(r, "config", KEY, str(root / "nowhere" / "demo"))
        records.reset()
        return r
    yield to
    records.reset()


def fx(seen):
    def ps():
        seen.append("ps")
        return ""

    def popen(*a, **k):
        seen.append("popen")
        raise AssertionError("no process of a run starts")
    return unattended.Fx(ps=ps, popen=popen, env=dict(os.environ), say=seen.append)


def test_rr5c_a6_the_line_reads_as_the_relays():
    assert unattended.RECORDS_REFUSAL == RELAY_WORDS.replace("the relay does", "the loop does")
    assert records.KEY in unattended.RECORDS_REFUSAL


@pytest.mark.parametrize("state", ["out", "unset", "broken"])
def test_rr5c_a6_run_refuses_before_any_write_or_process(repo, state):
    r = repo(state)
    seen = []
    env = dict(os.environ)
    with pytest.raises(unattended.UnattendedError) as e:
        unattended.run(r, None, fx=fx(seen))
    assert str(e.value) == unattended.RECORDS_REFUSAL and seen == []
    assert not unattended.runs_dir(env).exists()


@pytest.mark.parametrize("state", ["out", "unset", "broken"])
def test_rr5c_a6_the_cli_says_one_line_exit_2(repo, state):
    r = repo(state)
    rc, out, err = run("unattended", "run", str(r))
    assert rc == 2 and out == ""
    assert err.strip().endswith(f"unattended run: {unattended.RECORDS_REFUSAL}")
    assert len(err.strip().splitlines()) == 1


def test_rr5c_a6_own_goes_on_to_the_pins_refusals(repo):
    r = repo("own")
    seen = []
    with pytest.raises(unattended.UnattendedError) as e:
        unattended.run(r, None, fx=unattended.Fx(ps=lambda: seen.append("ps") or None,
                                                 env=dict(os.environ)))
    assert str(e.value).startswith("ps: ") and seen == ["ps"]
