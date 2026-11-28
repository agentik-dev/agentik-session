"""Packet hw3-machine: the `machine` verb (M6) and its skill (M7), on the fake probes of
test_hw3_machine and temp roots: no test reads the live state or runs a `du` on the live
home."""
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, machine
from test_hw3_machine import _repo, mac_probe

SKILL = Path(__file__).resolve().parents[1] / "plugin" / "skills" / "machine" / "SKILL.md"


# ---- M6: the verb ---------------------------------------------------------------------------

def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture
def verb(tmp_path, monkeypatch):
    """The verb on a fake probe and temp roots, with `running` gate jobs and two queued."""
    (tmp_path / "scratch").mkdir()
    (tmp_path / "projects").mkdir()
    (tmp_path / "cache" / "go-build").mkdir(parents=True)
    roots = {"gate": str(tmp_path / "gate"), "home": str(tmp_path), "repos": [],
             "transcripts": str(tmp_path / "projects"), "scratch": str(tmp_path / "scratch"),
             "state_home": str(tmp_path / "nostate")}
    state = {"running": 1, "probe": None, "unread": None}

    def probe():
        state["probe"] = mac_probe(gocache=str(tmp_path / "cache" / "go-build"),
                                   du=(tmp_path, {"projects": 3 * 1024 ** 2}))
        return state["probe"]
    monkeypatch.setattr(machine, "default_probe", probe)
    monkeypatch.setattr(cli, "_machine_roots", lambda env, root: dict(roots))
    monkeypatch.setattr(cli, "_machine_gate", lambda root, now: (
        (None, None, state["unread"]) if state["unread"] else (state["running"], 2, None)))
    return state


def test_status_reads_the_snapshot_the_budget_the_gate_and_the_largest(verb):
    rc, out, err = run("machine", "status")
    assert rc == 0, err
    lines = out.splitlines()
    assert lines[0] == "cores: 16 (12 performance, 4 efficiency); load 3.50 2.00 1.00"
    assert lines[1].startswith("memory: 131072 MB, ") and lines[1].endswith("pressure normal")
    assert "budget: 16 cores, 114688 MB; granted 1 jobs (4 cores, 2048 MB); free 12 cores, " \
           "112640 MB" in lines
    assert "gate: 1 running, 2 queued" in lines
    assert "a 4-core 2048 MB job: fits now" in lines
    largest = [x for x in lines if x.startswith("largest: ")]
    assert len(largest) == 3 and largest[0].startswith("largest: ~/cache/go-build 250 GB (idle: ")
    assert "largest: ~/projects 3 GB (person: the transcripts)" in lines


def test_status_json(verb):
    rc, out, _ = run("machine", "status", "--json")
    doc = json.loads(out)
    assert rc == 0 and doc["schema"] == cli.MACHINE_SCHEMA
    assert doc["snapshot"]["schema"] == machine.SCHEMA
    assert doc["budget"]["granted"]["count"] == 1 and doc["gate"] == {"running": 1, "queued": 2}
    assert len(doc["consumers"]) == 3 and doc["budget"]["fit"]["ok"] is True


def test_fits_exits_0_or_75_with_the_why_on_stderr(verb):
    rc, out, err = run("machine", "fits", "--cpu", "4", "--mem", "2048")
    assert rc == 0 and out.startswith("fits: 4 of 12 cores") and err == ""
    verb["running"] = 3
    rc, out, err = run("machine", "fits", "--cpu", "6", "--mem", "2048")
    assert rc == 75 and out == "" and "6 cores and 2048 MB asked, 4 and" in err
    rc, _, err = run("machine", "fits", "--cpu", "0", "--mem", "1")
    assert rc == 2 and "not a positive integer" in err


def test_reclaim_is_a_dry_run_alone(verb):
    rc, out, err = run("machine", "reclaim")
    assert rc == 2 and "not built" in err and out == ""
    rc, out, err = run("machine", "reclaim", "--dry-run")
    assert rc == 0, err
    assert out.splitlines()[0] == "auto: 0, 0 GB"
    assert "idle: 1, 250 GB" in out and "person: 2, 3 GB" in out
    assert "  ~/projects 3 GB: the transcripts" in out
    assert out.splitlines()[-1] == "would free: 250 GB (auto and idle); a dry run, nothing removed"
    doc = json.loads(run("machine", "reclaim", "--dry-run", "--json")[1])
    assert set(doc["kinds"]) == set(machine.KINDS)


def test_the_gate_s_jobs_are_read_by_the_verb(tmp_path, monkeypatch):
    from claude_session import gate
    monkeypatch.setattr(gate, "status", lambda root, now: {"running": [{}, {}], "queued": [{}]})
    assert cli._machine_gate(tmp_path, 0) == (2, 1, None)

    def broken(root, now):
        raise OSError("no gate")
    monkeypatch.setattr(gate, "status", broken)
    assert cli._machine_gate(tmp_path, 0) == (
        None, None, "the gate's state could not be read (no gate)")
    monkeypatch.setattr(gate, "status", lambda root, now: {"running": 3, "queued": []})
    assert cli._machine_gate(tmp_path, 0)[:2] == (None, None)


# ---- review 1, R4: an unread gate is a fault and a hold; a removed folder exits 2 --------------

def test_an_unread_gate_is_a_fault_in_status_and_a_hold_in_fits(verb):
    verb["unread"] = "the gate's state could not be read (no gate)"
    rc, out, err = run("machine", "status")
    assert rc == 0, err
    lines = out.splitlines()
    assert "gate: unknown running, unknown queued" in lines
    assert "fault: the gate's state could not be read (no gate)" in lines
    assert "a 4-core 2048 MB job: held: the gate's state could not be read (no gate)" in lines
    doc = json.loads(run("machine", "status", "--json")[1])
    assert doc["gate"] == {"running": None, "queued": None}
    assert doc["budget"]["fit"]["ok"] is False
    rc, out, err = run("machine", "fits", "--cpu", "1", "--mem", "1")
    assert rc == 75 and out == "" and "the gate's state could not be read" in err


def test_a_removed_folder_exits_2_with_no_traceback(verb, tmp_path, monkeypatch):
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    for argv in (("machine", "status"), ("machine", "fits", "--cpu", "1", "--mem", "1"),
                 ("machine", "reclaim", "--dry-run")):
        rc, out, err = run(*argv)
        assert rc == 2 and out == "" and "current folder is gone" in err, (argv, err)
        assert "Traceback" not in err


def test_the_roots_skip_a_removed_folder(tmp_path, monkeypatch):
    root = tmp_path / "xdg" / "example-tool"
    (root / "gate" / "queue").mkdir(parents=True)
    gone = tmp_path / "gone"
    gone.mkdir()
    monkeypatch.chdir(gone)
    gone.rmdir()
    roots = cli._machine_roots({"HOME": str(tmp_path / "home")}, root)
    assert roots["repos"] == []


def test_the_roots_name_the_repos_the_gate_names(tmp_path, monkeypatch):
    repo, wts = _repo(tmp_path)
    root = tmp_path / "xdg" / "example-tool"
    (root / "gate" / "queue").mkdir(parents=True)
    (root / "gate" / "queue" / "20260101-000000-1.json").write_text(
        json.dumps({"id": "20260101-000000-1", "repo": str(wts / "ahead")}))
    scratch = tmp_path / "scratch-root"
    (scratch / "throwaway" / ".git").mkdir(parents=True)
    (root / "gate" / "20260101-000000-2").mkdir()
    (root / "gate" / "20260101-000000-2" / "result.json").write_text(
        json.dumps({"id": "20260101-000000-2", "repo": str(scratch / "throwaway")}))
    monkeypatch.setattr(cli, "MACHINE_SCRATCH", str(scratch))
    monkeypatch.chdir(tmp_path)
    roots = cli._machine_roots({"HOME": str(tmp_path / "home")}, root)
    assert roots["repos"] == [os.path.realpath(repo)]       # the scratch root's repo is not
    assert roots["scratch"] == str(scratch)
    assert roots["state_home"] == str(tmp_path / "xdg")
    assert roots["transcripts"] == str(tmp_path / "home" / ".claude" / "projects")
    assert roots["gate"] == str(root / "gate")



def test_the_roots_skip_a_result_that_is_no_dict_or_does_not_parse(tmp_path, monkeypatch):
    root = tmp_path / "xdg" / "example-tool"
    (root / "gate" / "queue").mkdir(parents=True)
    for gid, text in (("20260101-000000-3", "[1, 2]"), ("20260101-000000-4", "{not json")):
        (root / "gate" / gid).mkdir()
        (root / "gate" / gid / "result.json").write_text(text)
    monkeypatch.chdir(tmp_path)
    assert cli._machine_roots({"HOME": str(tmp_path / "home")}, root)["repos"] == []

# ---- M7: the skill --------------------------------------------------------------------------

def test_the_skill_is_short_and_says_the_rules():
    text = SKILL.read_text()
    assert len(text.encode()) < 1200
    head = text.split("---")[1]
    for key in ("name: machine", "description:", "allowed-tools:"):
        assert key in head
    for words in ("agentik session machine status", "agentik session gate run", "429",
                  "backoff", "never clean by hand", "sleep"):
        assert words.lower() in text.lower(), words
