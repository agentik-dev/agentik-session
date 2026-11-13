"""Packet h3: five reproduced faults in the state files (NICE n56, n99, n100, n20).

Each test is built from its row's reproduction, with made-up names, every file under the
test's temp state root (conftest). n86's test is `test_unattended`'s own.
"""
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, config, hooks, resolver

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugin" / "lib"
AT_100 = ROOT / "tests" / "fixtures" / "meter" / "at-100.jsonl"
HUGE = 10 ** 400                          # a JSON integer past a float's range
DEEP = "[" * 200_000                      # nested past the parser's recursion limit


# ---- n56: `_ready` compares, never subtracts --------------------------------------------

SID = "h3aa0000-0000-4000-8000-000000000056"
MARKED, ACTED, ENDED = 1794295136.0, 1794295137.0, 1794295145.0


def _chain():
    from claude_session import chain
    return chain.Chain("c1", ["--model", "m"], config.STATE_DIR, chain.Effects(),
                       {"cap": 12, "floor": 0, "settle": 60}, poll=2, grace=10, kill_grace=30)


def _folder(marked=MARKED, acted=ACTED, ended=ENDED):
    sdir = resolver.session_dir(config.STATE_DIR, SID)
    (sdir / hooks.CALLS).mkdir(parents=True, exist_ok=True)
    for name, body in ((hooks.MARKER, {"written": marked}), (hooks.ACTIVITY, {"at": acted}),
                       (hooks.TURN_ENDED, {"at": ended})):
        (sdir / name).write_text(json.dumps(body))
    return sdir


def test_n56_the_folder_as_written_is_ready():
    assert _chain()._ready(_folder(), ENDED + 61) is True


@pytest.mark.parametrize("field", ["ended", "marked", "acted", "all"])
def test_n56_a_huge_integer_reads_not_ready_and_never_raises(field):
    kw = {"marked": HUGE, "acted": HUGE, "ended": HUGE} if field == "all" else {field: HUGE}
    assert _chain()._ready(_folder(**kw), ENDED + 61) is False


@pytest.mark.parametrize("shape", ["negative", "no activity", "written -inf"])
def test_n56_a_huge_negative_or_infinite_stamp_never_reads_ready(shape):
    """Round 1's F2: `ended` is bounded as `_opened` bounds `at` (AT_FLOOR <= ended)."""
    marked = float("-inf") if shape == "written -inf" else -10 ** 402
    sdir = _folder(marked=marked, acted=-10 ** 401, ended=-10 ** 400)
    if shape == "no activity":
        (sdir / hooks.ACTIVITY).unlink()
    assert _chain()._ready(sdir, ENDED + 61) is False


# ---- n99: a state file too deep to parse reads as one that does not parse ---------------

def test_n99_load_json_of_a_deep_file_is_what_a_bad_file_gives(tmp_path):
    deep, bad = tmp_path / "deep.json", tmp_path / "bad.json"
    deep.write_text(DEEP)
    bad.write_text("not json{")
    assert hooks._load_json(deep) == hooks._load_json(bad) == {}


def test_n99_ready_reads_a_deep_turn_ended_as_one_that_does_not_parse():
    """Round 1's F3: chain._json treats RecursionError as a file that does not parse."""
    sdir = _folder()
    (sdir / hooks.TURN_ENDED).write_text(DEEP)
    assert _chain()._ready(sdir, ENDED + 61) is False


def test_n99_meter_parse_skips_a_deep_transcript_line(tmp_path):
    """Round 1's F3: meter._scan treats RecursionError as a line that does not parse."""
    from claude_session import meter
    t = tmp_path / "t.jsonl"
    t.write_text(AT_100.read_text() + DEEP + "\n")
    assert meter.parse(t) is not None


def _post(monkeypatch, capsys, sid, resolved_text):
    repo = Path(os.environ["HOME"]) / "repo"
    (repo / ".claude" / "agentik").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "agentik" / "config.yaml").write_text('session: {posture: "signal"}\n')
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_CONFIG"}
    assert hooks.session_start({"session_id": sid, "cwd": str(repo)}, env)
    sdir = resolver.session_dir(config.STATE_DIR, sid)
    (sdir / "resolved.json").write_text(resolved_text)
    payload = {"session_id": sid, "transcript_path": str(AT_100), "tool_name": "Read"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    assert hooks.dispatch("post-tool-use") == 0
    return json.loads(capsys.readouterr().out)


def test_n99_post_tool_use_still_speaks_over_a_deep_resolved_json(monkeypatch, capsys):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    bad = _post(monkeypatch, capsys, "h3bb0000-0000-4000-8000-000000000099", "not json{")
    deep = _post(monkeypatch, capsys, "h3bb0000-0000-4000-8000-000000000098", DEEP)
    assert bad and deep == bad


# ---- n100: concurrent meter.save calls never raise and leave no temp file ---------------

WRITER = r"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from claude_session import meter

class M:
    signal = None
    def __init__(self, i): self.i = i
    def as_dict(self): return {"writer": sys.argv[3], "n": self.i, "pad": "x" * 4096}

sdir, start = Path(sys.argv[2]), float(sys.argv[4])
while time.time() < start:
    pass
errors = []
for i in range(25):
    try:
        meter.save(sdir, M(i), {"n": i})
        json.loads((sdir / meter.METER).read_text())
        json.loads((sdir / meter.STATE).read_text())
    except Exception as e:
        errors.append(f"{type(e).__name__}: {e}")
print(json.dumps(errors))
"""


def test_n100_two_hundred_concurrent_saves_from_eight_processes(tmp_path):
    import time
    sdir = tmp_path / "sessions" / "h3cc0000-0000-4000-8000-000000000100"
    sdir.mkdir(parents=True)
    start = time.time() + 1.0
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(LIB), str(sdir), f"w{k}",
                               repr(start)], stdout=subprocess.PIPE, text=True)
             for k in range(8)]
    errors = [e for p in procs for e in json.loads(p.communicate(timeout=120)[0])]
    assert errors == []
    from claude_session import meter
    assert json.loads((sdir / meter.METER).read_text())["n"] == 24
    assert sorted(p.name for p in sdir.iterdir()) == sorted([meter.METER, meter.STATE])


# ---- n20: a carry past 64 KiB keeps its newest entries and is written -------------------

UTC = timezone.utc
A, B = "h3dd-sess-aaaa-0000-0020", "h3dd-sess-bbbb-0000-0020"
WEEK = datetime(2026, 11, 16, 23, 0, tzinfo=UTC)


def _entry(week: datetime, tag: str) -> dict:
    last = {f"{tag}-sess-{i:04d}-0000-1111-2222": [admission._ts(week - timedelta(days=1)), 40]
            for i in range(admission.CARRY_SESSIONS)}
    return {"week": admission._ts(week), "drops": [], "last": last, "spend": {}}


def _fill(n: int, room: int, later: bool = False) -> dict:
    """`n` other logins' carries, each a week older than the next, whose text is `room`
    bytes short of BAND_MAX; `later`: their weeks reset 2 to 7 hours after WEEK, the
    current login's (round 1's F1)."""
    c = {f"login-{i:02d}": _entry(WEEK + timedelta(hours=1 + (n - i)) if later
                                  else WEEK - timedelta(hours=24 + 6 * (n - i)), f"o{i:02d}")
         for i in range(n)}
    short = admission.BAND_MAX - room - len(json.dumps(c) + "\n")
    assert short >= 0
    c["login-00"]["pad"] = "p" * max(0, short - len(', "pad": ""'))
    return c


def test_n20_save_carry_past_the_bound_drops_the_oldest_and_writes(tmp_path):
    now = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    old = _fill(6, 100)
    new = {"current": _entry(WEEK, "cur")}
    admission._save_carry(tmp_path, old, new, now)
    p = tmp_path / admission.MIX_FILE
    assert p.exists() and p.stat().st_size <= admission.BAND_MAX
    kept = json.loads(p.read_text())
    assert "current" in kept and "login-00" not in kept
    order = sorted({**old, **new}, key=lambda k: ({**old, **new})[k]["week"])
    assert list(kept) == order[-len(kept):]              # a suffix: the newest, kept


def test_n20_past_the_bound_the_others_go_before_this_calls_own(tmp_path):
    """Round 1's F1: the other logins' weeks reset later than the current one's; the
    others go, oldest first, and the current login's carry is kept."""
    now = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    old = _fill(6, 100, later=True)
    new = {"current": _entry(WEEK, "cur")}
    admission._save_carry(tmp_path, old, new, now)
    p = tmp_path / admission.MIX_FILE
    assert p.exists() and p.stat().st_size <= admission.BAND_MAX
    kept = json.loads(p.read_text())
    assert "current" in kept and len(kept) > 1
    others = sorted(old, key=lambda k: old[k]["week"])
    assert [k for k in kept if k != "current"] == others[-(len(kept) - 1):]


@pytest.mark.parametrize("later", [False, True])
def test_n20_a_reset_survives_rotation_with_the_carry_full(monkeypatch, later):
    p = resolver._user_file(os.environ)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("defaults:\n  admission:\n    mix:\n      shares:\n        fable: 3\n"
                 "        opus: 1\n      resets: 2\n")
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    (d / admission.MIX_FILE).write_text(json.dumps(_fill(6, 50, later)) + "\n")

    def by_state(sid, by):
        sdir = config.state_dir(os.environ) / "sessions" / sid
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "meter-state.json").write_text(json.dumps({"own": {"by": by}}))

    def rec(sid, pct, t):
        lim = [{"kind": "seven_day", "percentUsed": pct,
                "resetsAt": WEEK.strftime("%Y-%m-%dT%H:%M:%S.000Z")}]
        admission.record(sid, json.dumps({"kind": "reading", "rateLimits": lim}),
                         dict(os.environ), t)

    def mix():
        return json.loads((d / "band.json").read_text())["mix"]

    t = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
    by_state(A, {"fable": [0, 122500, 0, 0]})
    by_state(B, {"opus": [0, 104000, 0, 0]})
    rec(A, 75, t), rec(B, 75, t + timedelta(minutes=1)), rec(A, 26, t + timedelta(hours=1))
    assert (mix()["phase"]["n"], mix()["resets_left"]) == (1, 1)
    for h in (30, 60, 90):
        by_state(A, {"fable": [0, 122500 + h * 100, 0, 0]})
        rec(A, 26 + h // 30, t + timedelta(hours=h))
        assert (mix()["phase"]["n"], mix()["resets_left"]) == (1, 1), h
    assert (d / admission.MIX_FILE).stat().st_size <= admission.BAND_MAX
    assert not any(r.get("session") == B for name in ("ledger.jsonl",)
                   for r in map(json.loads, (d / name).read_text().splitlines()))
