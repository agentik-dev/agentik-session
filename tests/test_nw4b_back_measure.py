"""Packet nw4b-back-measure: a hand-back's cost is measured, a new line kind in the admission
ledger (hq design/31 item 19). SubagentStop stamps the coordinator's occupancy, the main
thread's next Stop writes one `back` line a stamp, and the room reads each kind's median once
the kind has ten. Every state is under the test's own temp root, every transcript a fixture of
assistant lines with usage; no test starts a `claude` or a `make`."""
import fcntl
import io
import json
import os
import signal
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

import pytest

from claude_session import admission, cli, hooks, resolver, room

SID = "test-session"
OTHER = "a-different-session-9999"
NOW = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)
M = timedelta(minutes=1)
KEYS = ["ts", "session", "kind", "agentId", "done", "before", "after", "tokens", "shared"]
SEEDS = {"build": {"median": 29.1, "p90": 55.4}, "fix": {"median": 26.2, "p90": 57.6},
         "phase": {"median": 16.9, "p90": 48.0}, "review": {"median": 9.5, "p90": 18.3},
         "refute": {"median": 9.7, "p90": 17.3},
         "general-purpose": {"median": 14.9, "p90": 64.3}, "scribe": {"median": 0.4, "p90": 0.9}}
LAUNCH = {"back": 2.5, "narrow": {"points": 10, "alone": 15}, "kinds": SEEDS}
BUILDER, ADVERSARY = "relay:builder", "relay:adversary"


def _sdir(sid=SID):
    return resolver.session_dir(resolver.state_dir(os.environ), sid)


def _turn(i, ctx):
    return {"type": "assistant", "requestId": f"r{i}", "timestamp": "2026-11-22T14:00:00Z",
            "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                        "content": [{"type": "text", "text": "<placeholder>"}],
                        "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": ctx, "output_tokens": 7}}}


class Transcript:
    """A main transcript under the test's temp dir, grown one assistant line at a time."""

    def __init__(self, path):
        self.path, self.n = path, 0
        path.write_text("")

    def grow(self, ctx):
        with open(self.path, "a") as f:
            f.write(json.dumps(_turn(self.n, ctx)) + "\n")
        self.n += 1


@pytest.fixture
def main(tmp_path):
    """A session folder whose meter.json names a fixture transcript, at an occupancy of 1000."""
    _sdir().mkdir(parents=True, exist_ok=True)
    t = Transcript(tmp_path / "main.jsonl")
    t.grow(1000)
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(t.path), "tool_name": "Read"},
                        os.environ)
    assert (_sdir() / "meter.json").is_file()
    return t


def _end(aid, sid=SID):
    return hooks.subagent_stop({"session_id": sid, "agent_id": aid}, os.environ)


def _stop(**extra):
    return hooks.stop({"session_id": SID, **extra}, os.environ)


def _backs():
    d = admission.directory(os.environ)
    rows = [r for n in (admission.ROTATED, admission.LEDGER) for r in admission._rows(d / n)]
    return [r for r in rows if r.get("kind") == "back"]


def _stamps():
    b = _sdir() / "backs"
    return sorted(os.listdir(b)) if b.is_dir() else []


# ---- 1. the stamp ----------------------------------------------------------------------------

def test_1_subagent_stop_stamps_the_transcript_s_last_occupancy(main, monkeypatch):
    main.grow(5000)                       # past the meter's last PostToolUse
    sdir = _sdir()
    meter_bytes = (sdir / "meter.json").read_bytes(), (sdir / "meter-state.json").read_bytes()
    (sdir / hooks.CALLS).mkdir()
    (sdir / hooks.CALLS / "c1.json").write_text(json.dumps({"agent_id": "a1"}))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": SID, "agent_id": "a1"})))
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert hooks.dispatch("SubagentStop") == 0
    assert buf.getvalue() == ""
    st = json.loads((sdir / "backs" / "a1.json").read_text())
    assert set(st) == {"at", "before"} and st["before"] == 5000
    assert isinstance(st["at"], float)
    assert ((sdir / "meter.json").read_bytes(), (sdir / "meter-state.json").read_bytes()) == meter_bytes
    assert not (sdir / hooks.CALLS / "c1.json").exists()


def test_1_a_stamp_already_there_is_kept(main):
    _end("a1")
    first = (_sdir() / "backs" / "a1.json").read_bytes()
    main.grow(9000)
    _end("a1")
    assert (_sdir() / "backs" / "a1.json").read_bytes() == first


def test_1_no_stamp_without_an_id_a_folder_or_a_transcript(main):
    for aid in (None, "", "not an id!", 7):
        hooks.subagent_stop({"session_id": SID, "agent_id": aid}, os.environ)
    assert _stamps() == []
    _end("a1", sid=OTHER)
    assert not _sdir(OTHER).exists()
    m = json.loads((_sdir() / "meter.json").read_text())
    m.pop("transcript")
    (_sdir() / "meter.json").write_text(json.dumps(m))
    _end("a2")
    assert _stamps() == []


# ---- 2. the line -----------------------------------------------------------------------------

def test_2_the_main_thread_s_stop_writes_one_back_line(main):
    _end("a1")
    main.grow(2900)
    assert _stop() == {}
    (line,) = _backs()
    assert list(line) == KEYS
    assert (line["session"], line["kind"], line["agentId"]) == (SID, "back", "a1")
    assert (line["before"], line["after"], line["tokens"], line["shared"]) == (1000, 2900, 1900, 1)
    assert datetime.fromisoformat(line["done"]).tzinfo is not None
    assert datetime.fromisoformat(line["ts"]) >= datetime.fromisoformat(line["done"])
    assert _stamps() == []
    assert isinstance(json.loads((_sdir() / hooks.TURN_ENDED).read_text())["at"], float)


def test_2_a_helper_s_stop_reads_no_stamp_and_writes_no_line(main):
    _end("a1")
    main.grow(2900)
    assert _stop(agent_id="a2") == {}
    assert _backs() == [] and _stamps() == ["a1.json"]
    assert not (_sdir() / hooks.TURN_ENDED).exists()


def test_2_through_dispatch_the_stop_prints_nothing(main, monkeypatch):
    _end("a1")
    main.grow(2900)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": SID})))
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert hooks.dispatch("Stop") == 0
    assert buf.getvalue() == "" and len(_backs()) == 1


# ---- 3. several in one turn ------------------------------------------------------------------

def test_3_three_stamps_share_the_growth_from_the_least_before(main):
    _end("a1")                                   # 1000
    main.grow(6000)
    _end("a2")
    main.grow(7000)
    _end("a3")
    main.grow(6000)
    _stop()
    lines = _backs()
    assert [x["agentId"] for x in lines] == ["a1", "a2", "a3"]
    assert [x["before"] for x in lines] == [1000, 6000, 7000]
    assert {(x["after"], x["tokens"], x["shared"]) for x in lines} == {(6000, 1667, 3)}
    assert _stamps() == []


def test_3_a_growth_of_zero_or_less_writes_no_line_and_removes_the_stamps(main):
    _end("a1")
    _end("a2")
    _stop()
    assert _backs() == [] and _stamps() == []
    main.grow(800)
    _end("a3")
    main.grow(500)
    _stop()
    assert _backs() == [] and _stamps() == []


# ---- 4. faults -------------------------------------------------------------------------------

class Hung(BaseException):
    """Raised by the test's own alarm: no `except Exception` of the code swallows it."""


@pytest.fixture
def alarm():
    def hung(*_):
        raise Hung()
    old = signal.signal(signal.SIGALRM, hung)
    signal.alarm(5)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


def test_4_a_fifo_a_folder_and_a_torn_stamp_give_no_line(main, alarm):
    _end("a1")
    b = _sdir() / "backs"
    os.mkfifo(b / "f1.json")
    (b / "d1.json").mkdir()
    (b / "t1.json").write_text('{"at": 1.0, "bef')
    main.grow(3000)
    _stop()
    assert [x["agentId"] for x in _backs()] == ["a1"]
    assert _stamps() == ["d1.json", "f1.json"]   # the regular files read are removed


def test_4_the_ledger_s_lock_held_writes_no_line_and_never_raises(main, monkeypatch):
    monkeypatch.setattr(admission, "LOCK_WAIT_S", 0.2)
    _end("a1")
    main.grow(3000)
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / admission.LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        assert _stop() == {}
    finally:
        os.close(fd)
    assert _backs() == [] and _stamps() == []


def test_4_a_fault_in_the_reader_writes_no_line_and_never_raises(main, monkeypatch):
    _end("a1")
    main.grow(3000)

    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(hooks.meter, "_scan", boom)
    assert _stop() == {}
    assert _backs() == [] and _stamps() == []
    assert hooks.subagent_stop({"session_id": SID, "agent_id": "a2"}, os.environ) == {}
    assert _stamps() == []


def test_4_admission_record_refuses_a_back_kind(monkeypatch):
    with pytest.raises(admission.AdmissionError) as e:
        admission.record(SID, json.dumps({"kind": "back"}), os.environ)
    assert e.value.code == 2
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"kind": "back"})))
    with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
        assert cli.main(["admission", "record", "--session", SID]) == 2
    assert not (admission.directory(os.environ) / admission.LEDGER).exists()


# ---- 5. the kind -----------------------------------------------------------------------------

def _spawn(t, aid, typ=BUILDER, desc="build 1 of row-a", sid=SID):
    return {"ts": t.isoformat(), "session": sid, "kind": "spawn", "subagentType": typ,
            "model": "opus", "description": desc, "tool_use_id": f"tu-{aid}", "agentId": aid}


def _done(t, aid, mins, sid=SID):
    return {"ts": t.isoformat(), "session": sid, "kind": "done", "agentId": aid,
            "tool_use_id": None, "durationMs": int(mins * 60000), "swept": False}


def _resume(t, aid, sid=SID):
    return {"ts": t.isoformat(), "session": sid, "kind": "resume", "to": aid}


def _back(t, aid, tokens, sid=OTHER):
    return {"ts": t.isoformat(), "session": sid, "kind": "back", "agentId": aid,
            "done": t.isoformat(), "before": 1000, "after": 1000 + tokens, "tokens": tokens,
            "shared": 1}


def _ledger(rows):
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    p = d / admission.LEDGER
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_5_a_back_line_takes_its_run_s_kind():
    t = NOW - 90 * M
    rows = [_spawn(t, "a1"), _done(t + M, "a1", 1), _back(t + M, "a1", 100),
            _spawn(t, "a2", desc="build 2 of row-a"), _done(t + M, "a2", 1), _back(t + M, "a2", 200),
            _spawn(t, "a3", ADVERSARY, "refute design 9"), _done(t + M, "a3", 1),
            _back(t + M, "a3", 300),
            _spawn(t, "a4", ADVERSARY, "review 1 of row-a"), _done(t + M, "a4", 1),
            _resume(t + 2 * M, "a4"), _done(t + 3 * M, "a4", 1), _back(t + 3 * M, "a4", 400),
            _back(t + 3 * M, "zz", 500)]
    assert room.back_pairs(rows) == [("build", 100.0), ("fix", 200.0), ("refute", 300.0),
                                     ("review", 400.0)]
    assert room.back_pairs([r for r in rows if r["kind"] != "back"]) == []


# ---- 6. back by kind -------------------------------------------------------------------------

TEN = [5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500]


def test_6_a_kind_with_ten_lines_takes_its_median_in_points():
    pairs = [("build", t) for t in TEN] + [("scribe", 2000)] * 9
    tab = room.backs(2.5, pairs, 400000)
    assert room.cost(tab, "build", 2.5) == pytest.approx(1.75)
    assert room.cost(tab, "scribe", 2.5) == 2.5 and room.cost(tab, "review", 2.5) == 2.5
    assert room._pts(room.cost(room.backs(2.5, pairs, 180000), "build", 2.5)) == "3.9"
    for ceiling in (None, 0, -1, "400000", True, float("nan")):
        tab = room.backs(2.5, pairs, ceiling)
        assert {room.cost(tab, k, 2.5) for k in ("build", "scribe", "fix")} == {2.5}
    assert room.cost(room.backs(2.5, [("build", 100)] * 10, 400000), "build", 2.5) == 0.025


# ---- 7. the room and the line ----------------------------------------------------------------

def _history():
    """Ten measured hand-backs each of builders (7000), reviews (10000) and scribes (2000), in
    another session, every one ended."""
    rows, t = [], NOW - 300 * M
    for i in range(10):
        for k, typ, desc, mins, tokens in (("b", BUILDER, "build 1 of row-h", 29.1, 7000),
                                           ("r", ADVERSARY, "review 1 of row-h", 9.5, 10000),
                                           ("s", "scribe", "notes", 0.4, 2000)):
            aid = f"h{k}{i}"
            rows += [_spawn(t, aid, typ, desc, sid=OTHER), _done(t + M, aid, mins, sid=OTHER),
                     _back(t + M, aid, tokens)]
    return rows


def _session(used):
    sdir = _sdir()
    sdir.mkdir(parents=True, exist_ok=True)
    s = {"profile": "frontier", "posture": "signal", "checkpoint_at": 0.8, "launch": LAUNCH,
         "charter": {"dir": "history/sittings", "required": True, "discipline": True}}
    (sdir / "resolved.json").write_text(json.dumps({"session": s}))
    (sdir / "model.json").write_text(json.dumps({"model": "opus"}))
    (sdir / "meter.json").write_text(json.dumps(
        {"session_id": SID, "pct_context": used, "pct_turns": 4.0, "checkpoint_at": 0.8,
         "ceilings": {"context": 400000, "turns": 400}}))


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(room, "_now", lambda: NOW)
    monkeypatch.setattr(room, "TZ", timezone.utc)


def test_7_the_room_sums_each_kind_s_cost_and_the_line_shows_the_new_one_s(clock):
    _session(62.0)
    _ledger(_history() + [_spawn(NOW - 5 * M, "o1"), _spawn(NOW - 4 * M, "o2"),
                          _spawn(NOW - 2 * M, "o3", ADVERSARY, "review 1 of row-b")])
    # 80 - 62 - (1.75 + 1.75 + 2.5) = 12.0; the scribe's 0.5 leaves 11.5, wide (2.5 left 9.5)
    out = hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent", "tool_use_id": "tu-new",
                              "tool_input": {"prompt": "p", "description": "notes",
                                             "subagent_type": "scribe"}}, os.environ)
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    assert ("launch: room 12.0 to the line, 3 out; this scribe (about 1 min, 0.5) fits, wide"
            in ctx)
    text, held = room.told({"session_id": SID, "tool_name": "Agent", "tool_input": {
        "description": "build 1 of row-c", "subagent_type": BUILDER}}, os.environ, "deny")
    # the builder's own 1.75 leaves 10.25, wide, where the profile's 2.5 left 9.5, narrow
    assert text == ("launch: room 12.0 to the line, 3 out; this builder (about 29 min, 1.8) "
                    "fits, wide") and not held
    assert room.status_for(SID, os.environ).startswith("launch: room 12.0 to the line, 3 out: ")


def test_7_no_ceiling_counts_the_profile_s_back(clock):
    _session(62.0)
    m = json.loads((_sdir() / "meter.json").read_text())
    m.pop("ceilings")
    (_sdir() / "meter.json").write_text(json.dumps(m))
    _ledger(_history() + [_spawn(NOW - 5 * M, "o1")])
    assert room.status_for(SID, os.environ).startswith("launch: room 15.5 to the line, 1 out: ")


# ---- 8. the report ---------------------------------------------------------------------------

def test_8_report_ends_with_a_hand_back_s_cost_by_kind():
    rows = _history()
    rows = [r for r in rows if not (r["kind"] == "back" and r["agentId"][1] == "s"
                                    and int(r["agentId"][2:]) >= 3)]
    _ledger(rows + [_back(NOW, "nobody", 9999)])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main(["report"])
    tail = buf.getvalue().rstrip("\n").split("\n")[-4:]
    assert tail == ["admission: a hand-back's cost, by kind",
                    "  build  10  median 7.0k tokens",
                    "  review  10  median 10.0k tokens",
                    "  scribe  3  median 2.0k tokens  under 10: the profile's back stands"]


def test_8_no_counted_line_prints_no_section():
    _ledger([_spawn(NOW, "a1"), _back(NOW, "nobody", 9999)])
    assert "hand-back" not in admission.report(os.environ)
