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
