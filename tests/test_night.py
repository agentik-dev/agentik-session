"""`agentik session night` (packet night-1, hq design/07 §2): the loop without its land step.

`night.run` drives `tests/fixtures/night/claude`, a fake on PATH that replays one plan step
per start from `$FAKE_NIGHT_PLAN` and logs its argv, cwd, env and stdin to
`$FAKE_NIGHT_LOG`, in a temp repo with a bare `origin`; the wall clock and the sleep are
faked, the watchdog's clock is real. No real `claude` runs and no request is spent.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from claude_session import night

FIX = Path(__file__).parent / "fixtures" / "night"
QUEUE_IDS = ["green-row", "max-row", "limit-row", "orch-row", "parked-row", "dep-row", "big-row"]


def test_queue_read():
    logged = []
    q = night.read_queue((FIX / "queue.yaml").read_text())
    assert q["version"] == 1 and q["defaults"]["wall"] == "4h"
    assert q["defaults"]["verify"] == "auto"            # the two-line flow map, joined
    assert [r["id"] for r in q["rows"]] == QUEUE_IDS
    rows = {p["id"]: p for p in night.plan(q, None, logged.append)}
    assert rows["green-row"]["turns"] == 100 and rows["green-row"]["usd"] == 25
    assert rows["green-row"]["context"] == 144000 and rows["green-row"]["model"] == "claude-opus-5-5"
    assert rows["max-row"]["model"] == "claude-sonnet-5" and rows["max-row"]["usd"] == 8
    assert night.wall_seconds(rows["max-row"]["wall"]) == 5400
    assert rows["limit-row"]["merge"] == "merge-on-green" and rows["limit-row"]["turns"] == 100
    assert rows["dep-row"]["depends_on"] == ["green-row"]
    assert sorted(logged) == sorted(["ignored words", "ignored defaults.device", "ignored green-row.device",
                                     "ignored max-row.harness", "ignored dep-row.may_touch",
                                     "ignored big-row.surprise"])
    assert [p["id"] for p in night.plan(q, ["dep-row", "green-row"], logged.append)] == ["green-row", "dep-row"]
    with pytest.raises(night.NightError, match="no row 'nope'"):
        night.plan(q, ["nope"], logged.append)
    for bad in ("version: 2\nrows: []\n", "version: 1\nrows:\n  - id: a\n    x: [a, [b]]\n",
                "version: 1\nrows: [a]\n"):
        with pytest.raises(night.NightError):
            night.read_queue(bad)


# ---- the harness: a temp repo with a bare origin, the fake on PATH ----------------------

T0 = 1762520400 - 600          # ten minutes before the fixtures' reset


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


class Box:
    def __init__(self, tmp, monkeypatch):
        self.tmp = tmp
        self.repo = tmp / "repo"
        subprocess.run(["git", "init", "-q", "--bare", str(tmp / "origin.git")], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        (self.repo / "relay").mkdir()
        (self.repo / "relay" / "queue.yaml").write_text((FIX / "queue.yaml").read_text())
        (self.repo / "design" / "packets").mkdir(parents=True)
        for rid in QUEUE_IDS:
            (self.repo / "design" / "packets" / f"{rid}.md").write_text(f"# Packet {rid}\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "the queue")
        _git(self.repo, "remote", "add", "origin", str(tmp / "origin.git"))
        _git(self.repo, "push", "-q", "origin", "main")
        self.log, self.plan = tmp / "fake.log", tmp / "plan.json"
        monkeypatch.setenv("PATH", f"{FIX}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("FAKE_NIGHT_LOG", str(self.log))
        monkeypatch.setenv("FAKE_NIGHT_PLAN", str(self.plan))
        self.slept, self.said = [], []

    def go(self, steps, rows, **kw):
        self.plan.write_text(json.dumps(steps))
        fx = night.Fx(now=lambda: T0, sleep=self.slept.append, say=self.said.append,
                      env=dict(os.environ))
        self.rc = night.run(self.repo, rows, fx=fx, **kw)
        self.dir = night.newest_night(fx.env)
        self.ledger = [json.loads(ln) for ln in (self.dir / "ledger.jsonl").read_text().splitlines()]
        self.starts = ([json.loads(ln) for ln in self.log.read_text().splitlines()]
                       if self.log.exists() else [])
        return self

    def kind(self, k):
        return [e for e in self.ledger if e["kind"] == k]


@pytest.fixture
def box(tmp_path, monkeypatch):
    return Box(tmp_path, monkeypatch)


def test_green_built(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert box.rc == 0
    (row,), (stop,) = box.kind("row"), box.kind("stop")
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    assert row["state"] == "built" and row["sha"] == _git(wt, "rev-parse", "HEAD")
    assert row["worktree"] == str(wt) and "resume" not in row and row["merge"] == "branch-only"
    assert stop["reason"] == "queue-spent" and stop["rows"] == {"built": ["green-row"]}
    assert stop["cost"] == 1.25
    (spawn,), (ex,) = box.kind("spawn"), box.kind("exit")
    assert spawn["turns"] == 100 and spawn["usd"] == 25 and spawn["part"] == 1
    assert ex["subtype"] == "success" and ex["num_turns"] == 12 and ex["rc"] == 0
    (start,) = box.starts
    assert start["cwd"] == str(wt)
    a = start["argv"]
    assert a[:4] == ["-p", "--permission-mode", "auto", "--allowedTools"]
    assert a[4] == "Bash Edit Write MultiEdit NotebookEdit"
    assert a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--max-turns") + 1] == "100"
    assert a[a.index("--max-budget-usd") + 1] == "25" and a[a.index("--session-id") + 1] == spawn["session_id"]
    assert start["stdin"] == "# The packet; the repo's CLAUDE.md carries the rules\n\n# Packet green-row\n"
    stream = (box.dir / "green-row.jsonl").read_text().splitlines()
    assert len(stream) == 5 and stream[3] == "not a JSON line"       # every line, as it came
    assert oct((box.dir / "ledger.jsonl").stat().st_mode & 0o777) == "0o600"
    assert oct(box.dir.stat().st_mode & 0o777) == "0o700"


def test_max_turns_no_commit(box):
    box.go([{"stream": "max-turns.jsonl"}], ["max-row"])
    assert box.rc == 0
    (row,) = box.kind("row")
    wt = box.repo / ".claude" / "worktrees" / "max-row"
    assert (row["state"], row["reason"]) == ("red", "no-commit")
    assert row["resume"] == f"cd {wt} && claude --resume 0b5c1c39-7a0e-4a52-9a43-1f2d3c4b5a61"
    assert box.kind("limit") == [] and len(box.starts) == 1       # never a limit, never retried
    a = box.starts[0]["argv"]
    assert a[a.index("--model") + 1] == "claude-sonnet-5" and a[a.index("--max-turns") + 1] == "40"


def test_orchestrator_refused(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["orch-row", "parked-row", "dep-row", "big-row"])
    assert box.rc == 0 and box.starts == [] and box.kind("spawn") == []
    got = {r["row"]: (r["state"], r["reason"]) for r in box.kind("row")}
    assert got == {"orch-row": ("refused", "kind"), "parked-row": ("skip", "parked"),
                   "dep-row": ("skip", "gate-failed-dependency"), "big-row": ("refused", "context")}
    log = (box.dir / "log").read_text()
    assert "ignored dep-row.may_touch" in log and "ignored big-row.surprise" in log
    assert not (box.repo / ".claude" / "worktrees").exists()


def test_child_env(box, monkeypatch):
    monkeypatch.setenv("RELAY_ROW", "outer-row")
    monkeypatch.setenv("RELAY_BIN", "/x/relay")
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "2")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("RELAY_DEVICE_VERBS", "none")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.quotepath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    env = box.starts[0]["env"]
    assert env["CLAUDE_SESSION_PROFILE"] == "builder" and env["CLAUDE_SESSION_MAX_TURNS"] == "100"
    assert env["CLAUDE_SESSION_MODEL"] == "claude-opus-5-5" and env["RELAY_MEASURE_DEPTH"] == "1"
    for gone in ("RELAY_ROW", "RELAY_BIN", "CLAUDE_SESSION_DEPTH", "CLAUDECODE"):
        assert gone not in env
    assert env["RELAY_DEVICE_VERBS"] == "none"
    assert (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == ("core.quotepath", "false")
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("remote.origin.pushurl", "")
    assert (env["GIT_CONFIG_KEY_2"], env["GIT_CONFIG_VALUE_2"]) == ("remote.origin.pushurl",
                                                                    "relay-denies-push")
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert box.starts[0]["pushurl"] == "relay-denies-push"      # what git itself reads


def test_no_result_stops(box):
    box.go([{"stream": "green.jsonl", "commit": True, "no_result": True}], ["green-row", "max-row"])
    assert box.rc == 3 and len(box.starts) == 1                  # max-row never starts
    (row,), (stop,) = box.kind("row"), box.kind("stop")
    assert (row["state"], row["reason"]) == ("red", "sitting-failure")
    assert stop["reason"] == "sitting-failure"
