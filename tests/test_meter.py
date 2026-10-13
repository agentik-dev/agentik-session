"""The meter: burn-report's definitions, incremental parsing, the guards."""

import json
import os
import shutil
from pathlib import Path

import pytest

from claude_session import meter

FIX = Path(__file__).resolve().parent / "fixtures" / "meter"

# What burn-report --json printed in per_session for these fixtures (copied under
# a scratch ~/.claude/projects): turns, sidechain_turns, tokens, max, median.
BURN_REPORT = {
    "under-80": (3, 0, 214460, 100000, 72000),
    "at-80": (4, 1, 245298, 144000, 30005),
    "at-100": (3, 0, 440510, 180000, 155000),
    "with-builders/sess-b": (4, 2, 193330, 70505, 51010),
}


def numbers(m):
    t = m.total
    return (t["turns"], t["sidechain_turns"], t["tokens"], t["max_context"],
            t["median_context"])


@pytest.mark.parametrize("name", sorted(BURN_REPORT))
def test_definitions_equal_burn_report(name):
    assert numbers(meter.parse(FIX / f"{name}.jsonl")) == BURN_REPORT[name]


def test_definitions_on_at_80():
    m = meter.parse(FIX / "at-80.jsonl")
    # 5 assistant lines: one duplicate (dropped), one sidechain, one with no id
    assert (m.turns, m.sidechain_turns, m.tokens) == (4, 1, 245298)
    assert m.context == 100 + 3900 + 140000                 # the last, output excluded
    assert (m.pct_context, m.pct_turns, m.zone) == (80.0, 1.0, "notice")
    assert m.ceilings == {"context": 180000, "turns": 400}
    assert m.model == "claude-opus-5-5" and m.started == "2026-09-22T10:00:00Z"
    assert m.builders == [] and m.builders_source == "none"


def test_builders_fold_into_the_total():
    m = meter.parse(FIX / "with-builders/sess-b.jsonl")
    assert (m.turns, m.context, m.builders_source) == (2, 61010, "subagents")
    assert m.builders == [{"agent": "a", "turns": 2, "tokens": 81110, "max_context": 70505}]
    assert m.total["turns"] == 4 and m.total["max_context"] == 70505


def test_every_meter_field_is_present():
    d = meter.parse(FIX / "at-80.jsonl").as_dict()
    for k in ("session_id", "turns", "sidechain_turns", "tokens", "context", "max_context",
              "median_context", "model", "started", "ceilings", "window", "checkpoint_at",
              "pct_context", "pct_turns", "zone", "ts", "transcript", "signal", "builders",
              "total", "builders_source"):
        assert k in d
    assert set(d["transcript"]) == {"path", "inode", "size", "offset"}
    assert set(d["signal"]) == {"crossed", "tools_since"}


def _stable(m):
    d = m.as_dict()
    d.pop("ts")
    d["transcript"].pop("path"), d["transcript"].pop("inode")
    return d


def test_three_appends_equal_one_parse(tmp_path):
    raw = (FIX / "at-80.jsonl").read_bytes()
    one = meter.parse(FIX / "at-80.jsonl")
    p = tmp_path / "at-80.jsonl"
    cuts = [0, len(raw) // 3 + 7, 2 * len(raw) // 3 - 5, len(raw)]   # mid-line cuts
    state = {}
    p.write_bytes(b"")
    for a, b in zip(cuts, cuts[1:]):
        with open(p, "ab") as f:
            f.write(raw[a:b])
        state = json.loads(json.dumps(state))          # the state survives a file
        m = meter.parse(p, state)
    assert _stable(m) == _stable(one)


def test_a_partial_last_line_is_not_consumed(tmp_path):
    raw = (FIX / "at-80.jsonl").read_bytes()
    p = tmp_path / "t.jsonl"
    p.write_bytes(raw[:-10])
    state = {}
    m = meter.parse(p, state)
    assert m.turns == 3 and m.transcript["offset"] < m.transcript["size"]
    p.write_bytes(raw)
    assert meter.parse(p, state).turns == 4


def test_inode_change_reparses_from_zero(tmp_path):
    p = tmp_path / "t.jsonl"
    shutil.copy(FIX / "at-80.jsonl", p)
    state = {}
    meter.parse(p, state)
    q = tmp_path / "new.jsonl"                          # created while p exists: a new inode
    q.write_bytes((FIX / "under-80.jsonl").read_bytes() + (FIX / "at-100.jsonl").read_bytes())
    assert q.stat().st_size > p.stat().st_size          # so only the inode tells
    os.replace(q, p)
    m = meter.parse(p, state)
    assert (m.turns, m.tokens) == (6, 214460 + 440510)


def test_shrunk_file_reparses_from_zero(tmp_path):
    p = tmp_path / "t.jsonl"
    shutil.copy(FIX / "at-80.jsonl", p)
    state = {}
    meter.parse(p, state)
    with open(p, "r+b") as f:                           # same inode, smaller
        f.truncate(0)
        f.write((FIX / "under-80.jsonl").read_bytes()[:900])
    m = meter.parse(p, state)
    assert m.tokens < 245298 and m.turns == meter.parse(p).turns


def test_unreadable_transcript_is_none(tmp_path):
    assert meter.parse(tmp_path / "absent.jsonl") is None
    assert meter.parse(tmp_path) is None


def test_limits_from_the_resolved_profile(tmp_path):
    lim = {"ceilings": {"context": 288000, "turns": 400}, "checkpoint_at": 0.5}
    m = meter.parse(FIX / "at-80.jsonl", limits=lim)
    assert m.pct_context == 50.0 and m.checkpoint_at == 0.5 and m.window == 200000


def test_no_message_content_is_kept(tmp_path):
    state = {}
    m = meter.parse(FIX / "at-80.jsonl", state)
    meter.save(tmp_path, m, state)
    for f in tmp_path.iterdir():
        assert "placeholder" not in f.read_text()
