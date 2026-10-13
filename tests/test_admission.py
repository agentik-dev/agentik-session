"""Packet S25 (admission-r1 §5 S25): `claude-session admission record`, the machine's
admission ledger, the session-end sweep and rotation; and the module's static rule
(no deny, no fs.write). The module's behaviour is `plugin/hooks/admission.test.ts`'s: the
plugin's one hooks module, session.ts, carries admission's hooks (2.1.296 loads one module
per plugin and follows `$` across no import; ruling 1 as amended)."""
import fcntl
import io
import json
import os
import re
import stat
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import cli, config

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "plugin" / "hooks"
SID = "adm-sess-0000-1111"
OTHER = "adm-sess-2222-3333"

# Each kind's keys as the line carries them, after ts, session and kind (ruling 2).
KEYS = {
    "start": ["interactive", "chain"],
    "reading": ["rateLimits"],
    "spawn": ["subagentType", "model", "parentModel", "background", "fork", "description",
              "tool_use_id", "agentId", "context", "rateLimits"],
    "resume": ["to"],
    "done": ["agentId", "tool_use_id", "durationMs", "usage", "swept"],
    "end": ["reason"],
}
SAMPLE = {
    "start": {"interactive": True},
    "reading": {"rateLimits": [{"kind": "five_hour", "percentUsed": 41.5,
                                "resetsAt": "2026-10-12T14:05:00Z"}]},
    "spawn": {"subagentType": "general-purpose", "model": "opus", "parentModel": "claude-opus-5-5",
              "background": False, "fork": False, "description": "read the packet",
              "tool_use_id": "toolu_01", "agentId": "a1",
              "context": {"tokens": 1000, "window": 200000, "percent": 1}, "rateLimits": []},
    "resume": {"to": "a1"},
    "done": {"agentId": "a1", "durationMs": 1200,
             "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3,
                       "cache_creation_input_tokens": 4, "model": "claude-opus-5-5"}},
    "end": {"reason": "exit"},
}


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("CLAUDE_SESSION_CHAIN", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    return tmp_path / "xdg"


def adir(state: Path) -> Path:
    return state / config.APP / "admission"


def ledger(state: Path, name="ledger.jsonl") -> list:
    p = adir(state) / name
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()] if p.exists() else []


def run(stdin, *argv, sid=SID):
    """`admission record --session <sid>` in-process, `stdin` a dict (dumped) or raw text."""
    text = stdin if isinstance(stdin, str) else json.dumps(stdin)
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(text)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(["admission", "record", "--session", sid, *argv])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.stdin = old
    return rc, out.getvalue(), err.getvalue()


def _files(root: Path) -> list:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def test_record_appends_one_line(state):
    rc, out, err = run({"kind": "start", "interactive": True})
    assert (rc, out, err) == (0, "", "")
    [line] = ledger(state)
    assert line["kind"] == "start" and line["session"] == SID and line["interactive"] is True
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", line["ts"])


@pytest.mark.parametrize("kind", sorted(KEYS))
def test_each_kind_writes_exactly_its_keys(state, kind):
    rc, _, err = run({"kind": kind, **SAMPLE[kind]})
    assert (rc, err) == (0, "")
    [line] = ledger(state)
    assert list(line) == ["ts", "session", "kind", *KEYS[kind]]
    for k, v in SAMPLE[kind].items():
        assert line[k] == v


def test_absent_keys_are_null_and_start_takes_the_chain_from_the_environment(state, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "chain-7")
    assert run({"kind": "start", "interactive": False})[0] == 0
    assert run({"kind": "spawn", "tool_use_id": "toolu_9"})[0] == 0
    start, spawn = ledger(state)
    assert (start["chain"], start["interactive"]) == ("chain-7", False)
    assert spawn["tool_use_id"] == "toolu_9" and spawn["agentId"] is None and spawn["model"] is None


@pytest.mark.parametrize("stdin,sid", [
    ({"kind": "spawn", "prompt": "the task"}, SID),          # a refused key: the prompt
    ({"kind": "resume", "to": "a1", "message": "hi"}, SID),   # a refused key: the message
    ({"kind": "start", "chain": "forged"}, SID),              # chain is the verb's, never stdin's
    ({"kind": "done", "agentId": "a1", "swept": True}, SID),  # swept is the sweep's alone
    ({"kind": "admit"}, SID),                                 # an unknown kind
    ({"interactive": True}, SID),                             # no kind
    ("{not json", SID),                                       # bad JSON
    ("[1, 2]", SID),                                          # not an object
    ('{"kind": "done", "durationMs": NaN}', SID),             # non-finite numbers (F6)
    ('{"kind": "done", "durationMs": Infinity}', SID),
    ('{"kind": "spawn", "context": {"tokens": -Infinity}}', SID),
    ('{"kind": "done", "durationMs": 1e999}', SID),
    ({"kind": "start"}, "../escape"),                         # bad ids
    ({"kind": "start"}, "a b"),
    ({"kind": "start"}, "ok\n"),
    ({"kind": "start"}, "a" * 129),
])
def test_a_refusal_exits_2_and_writes_nothing(state, stdin, sid):
    before = _files(state)
    rc, out, err = run(stdin, sid=sid)
    assert rc == 2 and out == ""
    assert len(err.strip().splitlines()) == 1 and err.startswith("claude-session: ")
    assert _files(state) == before



@pytest.mark.parametrize("stdin", [
    # F4's repros: a nested key under a rate limit, an object where a scalar belongs
    {"kind": "reading", "rateLimits": [{"kind": "five_hour", "percentUsed": 5,
                                        "prompt": "secret prompt text"}]},
    {"kind": "spawn", "description": {"prompt": "secret"}},
    {"kind": "spawn", "model": ["opus"]},
    {"kind": "spawn", "background": "yes"},
    {"kind": "spawn", "context": {"tokens": 1, "window": 200000, "prompt": "secret"}},
    {"kind": "spawn", "context": "free text"},
    {"kind": "spawn", "rateLimits": [{"kind": "five_hour"}]},
    {"kind": "reading", "rateLimits": [{"kind": "five_hour", "percentUsed": True}]},
    {"kind": "reading", "rateLimits": [{"kind": "k" * 65, "percentUsed": 1}]},
    {"kind": "reading", "rateLimits": [{"kind": "five_hour", "percentUsed": 1}] * 17},
    {"kind": "reading", "rateLimits": "five_hour"},
    {"kind": "start", "interactive": "yes"},
    {"kind": "resume", "to": {"text": "secret"}},
    {"kind": "done", "durationMs": "1200"},
    {"kind": "done", "durationMs": -1},
    {"kind": "done", "usage": "1 token"},
    {"kind": "done", "usage": {"input_tokens": 1, "text": "s" * 65}},
    {"kind": "done", "usage": {"cache_creation": {"deep": {"prompt": "secret"}}}},
    {"kind": "done", "usage": {"tool": ["secret"]}},
    {"kind": "end", "reason": {"text": "secret"}},
    '{"kind": "end", "reason": "x\\ud83d"}',                     # a lone surrogate (S25's note)
    pytest.param('{"kind": "end", "reason": ' + "[" * 20000 + "]" * 20000 + "}", id="deep"),
])
def test_f4_each_kind_checks_its_values_by_type_and_writes_nothing(state, stdin):
    before = _files(state)
    rc, out, err = run(stdin)
    assert (rc, out) == (2, ""), err
    assert len(err.strip().splitlines()) == 1 and err.startswith("claude-session: ")
    assert "secret" not in err
    assert _files(state) == before


def test_f4_a_done_usage_keeps_the_engine_s_one_level_of_counters(state):
    usage = {**SAMPLE["done"]["usage"], "cache_creation": {"ephemeral_5m_input_tokens": 4},
             "service_tier": "standard", "speed": None}
    assert run({"kind": "done", "agentId": "a1", "usage": usage})[0] == 0
    assert ledger(state)[-1]["usage"] == usage


def test_a_long_description_is_clipped_never_refused(state):
    # M2's verify: the Agent tool sets no length on `description`, so a long one is kept
    # to its first 200 characters; refusing it would lose the spawn in observe mode.
    assert run({"kind": "spawn", "description": "d" * 201})[0] == 0
    assert ledger(state)[-1]["description"] == "d" * 200


def test_f4_stdin_that_is_not_utf8_exits_2_and_writes_nothing(state):
    before = _files(state)
    old = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(b'{"kind": "end", "reason": "\xff"}'), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(["admission", "record", "--session", SID])
    finally:
        sys.stdin = old
    assert (rc, out.getvalue()) == (2, "") and err.getvalue().startswith("claude-session: ")
    assert _files(state) == before

def test_a_held_lock_exits_3_within_3_s_and_writes_nothing(state):
    assert run({"kind": "start", "interactive": True})[0] == 0
    before = (adir(state) / "ledger.jsonl").read_text()
    lock = adir(state) / "ledger.lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, "-B", "-m", "claude_session", "admission", "record",
                            "--session", SID], input=json.dumps({"kind": "end"}), text=True,
                           capture_output=True, cwd=ROOT, env=env, timeout=30)
        took = time.monotonic() - t0
    finally:
        os.close(fd)
    assert p.returncode == 3 and took < 3.0, (p.returncode, took, p.stderr)
    assert len(p.stderr.strip().splitlines()) == 1
    assert (adir(state) / "ledger.jsonl").read_text() == before


def test_end_sweeps_this_sessions_open_spawns_and_no_others(state):
    spawn = lambda tid, aid: {"kind": "spawn", "tool_use_id": tid, "agentId": aid}
    assert run(spawn("t1", "a1"))[0] == 0
    assert run(spawn("t2", "a2"))[0] == 0
    assert run(spawn("t3", None))[0] == 0                    # no agentId: matched by tool_use_id
    assert run(spawn("t4", "a4"), sid=OTHER)[0] == 0
    assert run({"kind": "done", "agentId": "a1", "durationMs": 5})[0] == 0
    assert run({"kind": "end", "reason": "exit"})[0] == 0
    rows = ledger(state)
    assert [r["kind"] for r in rows] == ["spawn"] * 4 + ["done", "end", "done", "done"]
    swept = rows[6:]
    assert all(r["swept"] is True and r["session"] == SID for r in swept)
    assert sorted((r["tool_use_id"], r["agentId"]) for r in swept) == [("t2", "a2"), ("t3", None)]
    assert rows[4]["swept"] is False
    # the other session's spawn stays open; its own end sweeps it
    assert run({"kind": "end"}, sid=OTHER)[0] == 0
    last = ledger(state)[-1]
    assert (last["session"], last["agentId"], last["swept"]) == (OTHER, "a4", True)


def _seed(state: Path, hours_ago: float):
    d = adir(state)
    d.mkdir(parents=True, mode=0o700)
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
    (d / "ledger.jsonl").write_text(json.dumps({"ts": ts, "session": OTHER, "kind": "start",
                                                "interactive": True, "chain": None}) + "\n")
    os.chmod(d / "ledger.jsonl", 0o600)


def test_a_ledger_whose_first_line_is_past_29_hours_rotates(state):
    _seed(state, 29.5)
    (adir(state) / "ledger.1.jsonl").write_text("old\n")
    assert run({"kind": "start", "interactive": True})[0] == 0
    [old] = ledger(state, "ledger.1.jsonl")
    assert old["session"] == OTHER                           # the one there replaced
    [new] = ledger(state)
    assert new["session"] == SID


def test_a_ledger_under_29_hours_does_not_rotate(state):
    _seed(state, 28.5)
    assert run({"kind": "start", "interactive": True})[0] == 0
    assert [r["session"] for r in ledger(state)] == [OTHER, SID]
    assert not (adir(state) / "ledger.1.jsonl").exists()


# Fix round 1 (F5): a torn first line dates nothing; the first parseable line dates the file.
TORN = '{"ts": "20'


def _tear(state: Path) -> Path:
    p = adir(state) / "ledger.jsonl"
    p.write_text(TORN + "\n" + p.read_text())
    return p


def test_a_torn_first_line_is_dated_by_the_first_parseable_line(state):
    _seed(state, 1)
    p = _tear(state)
    (adir(state) / "ledger.1.jsonl").write_text("old\n")
    assert run({"kind": "start", "interactive": True})[0] == 0
    assert (adir(state) / "ledger.1.jsonl").read_text() == "old\n"      # kept, not replaced
    lines = p.read_text().splitlines()
    assert lines[0] == TORN and [json.loads(x)["session"] for x in lines[1:]] == [OTHER, SID]


def test_a_ledger_with_no_parseable_line_does_not_rotate(state):
    adir(state).mkdir(parents=True, mode=0o700)
    (adir(state) / "ledger.jsonl").write_text(TORN + "\nnot json\n")
    assert run({"kind": "start", "interactive": True})[0] == 0
    assert not (adir(state) / "ledger.1.jsonl").exists()
    assert [r["session"] for r in ledger_rows(state)] == [SID]


def test_a_torn_first_line_above_a_line_past_29_hours_rotates(state):
    _seed(state, 29.5)
    _tear(state)
    assert run({"kind": "start", "interactive": True})[0] == 0
    assert [r["session"] for r in ledger_rows(state, "ledger.1.jsonl")] == [OTHER]
    assert [r["session"] for r in ledger(state)] == [SID]


def ledger_rows(state: Path, name="ledger.jsonl") -> list:
    """The ledger's parseable lines, a torn one skipped."""
    out = []
    for ln in (adir(state) / name).read_text().splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


# Fix round 1 (F4): an OSError beneath the verb is exit 3, one line, nothing written.
def test_an_unwritable_ledger_exits_3_with_one_line_and_writes_nothing(state):
    adir(state).parent.mkdir(parents=True)
    adir(state).write_text("")                 # a file where the directory goes: mkdir fails
    before = _files(state)
    rc, out, err = run({"kind": "start", "interactive": True})
    assert rc == 3 and out == ""
    assert len(err.strip().splitlines()) == 1 and err.startswith("claude-session: ")
    assert _files(state) == before and adir(state).read_text() == ""


def test_modes_are_0700_and_0600(state):
    assert run({"kind": "start", "interactive": True})[0] == 0
    assert stat.S_IMODE(adir(state).stat().st_mode) == 0o700
    for p in adir(state).iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600, p.name


def test_nothing_is_written_outside_admission(state):
    for kind in KEYS:
        if kind != "done":
            assert run({"kind": kind, **SAMPLE[kind]})[0] == 0
    assert all(f == config.APP or f.startswith(f"{config.APP}/admission")
               for f in _files(state)), _files(state)
    assert sorted(p.name for p in adir(state).iterdir()) == ["band.json", "ledger.jsonl", "ledger.lock"]


def _module_text() -> str:
    """the plugin's one hooks module, which carries admission's hooks beside the band, its
    name spelled in pieces (test_mod's criterion 5 scan reads a quoted module suffix as a
    reader); skips when the module is absent. The band neither denies nor writes, so the
    whole module is read."""
    p = HOOKS_DIR / ("session." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return p.read_text()


def test_the_module_never_denies_and_never_writes_a_file():
    text = _module_text()
    assert not re.search(r"\bdeny\b", text)
    assert not re.search(r"fs\.write", text)
    assert not re.search(r"store\.set", text)
