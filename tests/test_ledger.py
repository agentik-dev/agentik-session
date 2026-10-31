"""The ledger: exactly LEDGER_KEYS, 0600, no message content, the report's filter."""

import json
import stat
import subprocess
from pathlib import Path

import pytest

from claude_session import ledger, meter

FIX = Path(__file__).resolve().parent / "fixtures" / "meter"


def test_keys_are_a_superset_of_burn_reports_per_session():
    assert set(ledger.PER_SESSION_KEYS) <= set(ledger.LEDGER_KEYS)
    assert len(set(ledger.LEDGER_KEYS)) == len(ledger.LEDGER_KEYS) == 22


def test_unknown_key_is_refused_and_nothing_written(tmp_path):
    with pytest.raises(ledger.LedgerError):
        ledger.append(tmp_path, {"session": "s", "content": "hello"})
    assert not ledger.path(tmp_path).exists()


def _entry(tmp_path, reason="other"):
    m = meter.parse(FIX / "at-80.jsonl").as_dict()
    return ledger.entry_for(m, project="p", profile="frontier", cwd=tmp_path,
                            exit_reason=reason)


def test_line_has_exactly_the_keys_and_mode_0600(tmp_path):
    p = ledger.append(tmp_path, _entry(tmp_path))
    ledger.append(tmp_path, _entry(tmp_path, "clear"))
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    lines = [json.loads(l) for l in p.read_text().splitlines()]
    assert [list(d) for d in lines] == [list(ledger.LEDGER_KEYS)] * 2
    d = lines[0]
    assert (d["session"], d["turns"], d["tokens"], d["max_context"]) == (
        "at-80", 4, 245298, 144000)
    assert (d["exit_reason"], d["builders_source"], d["builders"]) == ("other", "none", [])


def test_no_fixture_text_in_the_line(tmp_path):
    p = ledger.append(tmp_path, _entry(tmp_path))
    assert "placeholder" not in p.read_text()


def test_git_failures_give_null(tmp_path):
    d = _entry(tmp_path)                        # tmp_path is no repo
    assert (d["repo"], d["sha_at_end"], d["dirty"]) == (None, None, None)


def test_git_state_in_a_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    repo, sha, dirty = ledger.git_state(tmp_path)
    assert len(sha) == 40 and dirty is False
    (tmp_path / "f").write_text("x")
    assert ledger.git_state(tmp_path)[2] is True


def test_builders_carry_agent_turns_tokens(tmp_path):
    m = meter.parse(FIX / "with-builders/sess-b.jsonl").as_dict()
    d = ledger.entry_for(m, project="p", profile=None, cwd=None, exit_reason="other")
    assert d["builders"] == [{"agent": "a", "turns": 2, "tokens": 81110}]
    assert (d["turns"], d["builders_source"]) == (4, "subagents")


def test_read_filters_on_ended(tmp_path):
    for day in ("2026-09-01", "2026-09-20"):
        ledger.append(tmp_path, {"session": day, "ended": day + "T10:00:00+00:00"})
    assert [r["session"] for r in ledger.read(tmp_path)] == ["2026-09-01", "2026-09-20"]
    assert [r["session"] for r in ledger.read(tmp_path, "2026-09-10")] == ["2026-09-20"]
    assert ledger.read(tmp_path / "none") == []
    assert "2026-09-20" in ledger.table(ledger.read(tmp_path)).splitlines()[2]


# ---- S19: the chain's line kinds and the cap's strict read (respawn-r1 §3.6) ----

import time
from datetime import datetime, timezone

S19_KEYS = {
    "restart": ("kind", "chain", "seq", "at", "from_session", "to_session", "profile", "repo",
                "charter", "charter_sha256", "sitting_seconds", "ended_by", "restarts_24h",
                "cap", "model", "start_model"),      # S34 ruling 4
    "stop": ("kind", "chain", "at", "session", "profile", "repo", "reason", "exit_status",
             "sitting_seconds", "restarts"),
}


def _ago(hours, now):
    return datetime.fromtimestamp(now - hours * 3600, timezone.utc).isoformat(timespec="seconds")


@pytest.mark.parametrize("kind", ["restart", "stop"])
def test_s19_chain_lines_have_exactly_their_keys(tmp_path, kind):
    assert {"restart": ledger.RESTART_KEYS, "stop": ledger.STOP_KEYS}[kind] == S19_KEYS[kind]
    p = ledger.append_chain(tmp_path, {"kind": kind, "chain": "orient"})
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    line = json.loads(p.read_text())
    assert list(line) == list(S19_KEYS[kind])
    assert (line["kind"], line["chain"]) == (kind, "orient")
    assert all(line[k] is None for k in S19_KEYS[kind] if k not in ("kind", "chain", "at"))
    # `at` is written as `ended` is: an aware UTC time to the second
    at = datetime.fromisoformat(line["at"])
    assert at.utcoffset().total_seconds() == 0 and abs(at.timestamp() - time.time()) < 60


@pytest.mark.parametrize("entry", [
    {"kind": "resume", "chain": "c"},
    {"kind": "restart", "chain": "c", "reason": "cap"},          # a stop line's key
    {"kind": "stop", "chain": "c", "seq": 1},                    # a restart line's key
], ids=["unknown-kind", "restart-key", "stop-key"])
def test_s19_chain_writer_refuses(tmp_path, entry):
    with pytest.raises(ledger.LedgerError):
        ledger.append_chain(tmp_path, entry)
    assert not ledger.path(tmp_path).exists()
    good = {"kind": entry["kind"] if entry["kind"] != "resume" else "restart", "chain": "c"}
    ledger.append_chain(tmp_path, good)                          # the positive control
    assert json.loads(ledger.path(tmp_path).read_text())["kind"] == good["kind"]


def test_s19_read_returns_session_lines_only(tmp_path):
    ledger.append(tmp_path, {"session": "s1", "ended": "2026-10-09T01:00:00+00:00"})
    ledger.append_chain(tmp_path, {"kind": "restart", "chain": "c", "at": "2026-10-09T02:00:00+00:00"})
    ledger.append_chain(tmp_path, {"kind": "stop", "chain": "c", "at": "2026-10-10T03:00:00+00:00"})
    assert [d["session"] for d in ledger.read(tmp_path)] == ["s1"]
    assert [d["kind"] for d in ledger.read_chains(tmp_path)] == ["restart", "stop"]
    assert [d["kind"] for d in ledger.read_chains(tmp_path, since="2026-10-10")] == ["stop"]


def test_s19_restarts_in_counts_the_window(tmp_path):
    # criterion 11's first case: two inside 24 h, one older, two for another chain
    now = time.time()
    for hours, chain in ((1, "orient"), (23, "orient"), (25, "orient"), (2, "night"), (3, "night")):
        ledger.append_chain(tmp_path, {"kind": "restart", "chain": chain, "at": _ago(hours, now)})
    ledger.append_chain(tmp_path, {"kind": "stop", "chain": "orient", "at": _ago(1, now)})
    ledger.append(tmp_path, {"session": "orient", "ended": _ago(1, now)})
    assert ledger.restarts_in(tmp_path, "orient", now) == 2
    assert ledger.restarts_in(tmp_path, "night", now) == 2
    assert ledger.restarts_in(tmp_path, "orient", now, hours=26) == 3


@pytest.mark.parametrize("case", ["unreadable", "bad-line", "bad-at"])
def test_s19_restarts_in_fails_closed(tmp_path, case):
    now = time.time()
    assert ledger.restarts_in(tmp_path, "orient", now) == 0      # no file is 0
    p = ledger.path(tmp_path)
    if case == "unreadable":
        p.mkdir()                                                # a read that fails
        with pytest.raises(ledger.LedgerError):
            ledger.restarts_in(tmp_path, "orient", now)
        return
    if case == "bad-line":     # not a JSON object: counts when it holds the chain's name
        p.write_text('{"kind": "restart", "chain": "orient", "at": \n'
                     '{"kind": "restart", "chain": "night", "at": \n')
    else:                      # an unparsable `at` counts; one outside the window does not
        ledger.append_chain(tmp_path, {"kind": "restart", "chain": "orient", "at": "yesterday"})
        ledger.append_chain(tmp_path, {"kind": "restart", "chain": "orient", "at": _ago(30, now)})
    assert ledger.restarts_in(tmp_path, "orient", now) == 1
