"""Packet rr5c R3: reconcile's record and its charter readers where a repo's records live outside
its clone, in a temp hq with a temp holder. Every name is made up and every repository is the
test's own."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from claude_session import records
from claude_session.reconcile import idle, live

from test_r2 import CHARTER, NOW, cli, fake_detect, hq_world  # noqa: F401
from test_chain import fake  # noqa: F401  (fixture)

KEY = "agentik.records"
DAY = datetime.fromtimestamp(NOW).strftime("%Y-%m-%d") + ".md"


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """(hq, the records folder or None) for a state."""
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = Path(os.path.realpath(tmp_path))

    def make(state):
        hq = hq_world(root)
        git(hq, "init", "-q", "-b", "main")
        git(hq, "add", ".")
        git(hq, "commit", "-qm", "base")
        rec = None
        if state == "out":
            hold = root / "hold"
            rec = hold / "repos" / "hq"
            (rec / "history" / "sittings").mkdir(parents=True)
            git(hold, "init", "-q", "-b", "main")
            git(hq, "config", KEY, str(rec))
        elif state == "unset":
            (hq / ".hygiene-allow").write_text("records: out\n")
            git(hq, "add", ".hygiene-allow")
            git(hq, "commit", "-qm", "declare")
        elif state == "broken":
            git(hq, "config", KEY, str(root / "nowhere" / "hq"))
        records.reset()
        return hq, rec
    yield make
    records.reset()


@pytest.mark.parametrize("state", ["own", "out", "unset", "broken"])
def test_rr5c_a2_the_records_file_in_each_state(world, monkeypatch, state):
    hq, rec = world(state)
    fake_detect(monkeypatch)
    rc, out, err = cli(hq, monkeypatch, "--force")
    if state in ("own", "out"):
        assert rc == 0, err
        want = (hq if state == "own" else rec) / "history" / "reconcile" / DAY
        assert want.is_file() and f"record {want}" in out
        if state == "out":
            assert not (hq / "history").exists()
    else:
        assert rc == 2 and out == "" and "agentik.records" in err
        assert len(err.strip().splitlines()) == 1 and "nothing written" in err
        assert not (hq / "history").exists()


def test_rr5c_a2_out_a_record_folder_outside_the_records_folder_is_refused(world, monkeypatch):
    hq, rec = world("out")
    cfg = hq / ".claude" / "agentik" / "config.yaml"
    cfg.write_text(cfg.read_text() + "    record: ../../elsewhere\n")
    fake_detect(monkeypatch)
    rc, out, err = cli(hq, monkeypatch, "--force")
    assert rc == 2 and f"inside the records folder, {rec}" in err


def charters_in(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("2026-11-21-1.md", "2026-11-21-2.md"):
        (folder / name).write_text(CHARTER.format(name=name[:-3], goal="the same goal"))
    return [str(folder / "2026-11-21-1.md"), str(folder / "2026-11-21-2.md")]


@pytest.mark.parametrize("state", ["own", "out"])
def test_rr5c_a2_live_reads_a_holders_charters(world, state):
    hq, rec = world(state)
    want = charters_in((hq if state == "own" else rec) / "history" / "sittings")
    assert live.charters(str(hq)) == want
    f = live.goal_unchanged({"roots": {"hq": str(hq)}, "hq": "hq", "threshold": 2})
    assert f["value"] == 2 and f["flagged"]
    assert str(Path(want[0]).parent) in f["evidence"]["command"]


def test_rr5c_a2_idle_counts_a_holders_charter_write_as_a_charter(world):
    hq, rec = world("out")
    hold = rec.parent.parent
    charter = rec / "history" / "sittings" / "2026-11-21-1.md"
    assert idle.charter_only(f"git -C {hold} add repos/hq/history/sittings/2026-11-21-1.md")
    assert idle.charter_only(f"git -C {hold} commit -m x -- {charter}")
    assert idle._charter(str(charter))
    assert not idle.charter_only(f"git -C {hold} add repos/hq/HANDOFF.md")
