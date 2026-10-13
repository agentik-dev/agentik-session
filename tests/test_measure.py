"""Packet M2 (mod-r1 S2): `measure record` writes measure.json, `status` and `doctor` print the
drift between the engine's measure and the meter, and nothing that decides reads it (mod-r1 §7
criterion 4)."""
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks, meter, resolver

SID = "measure-sess-0000-1111"
CONTEXT = {"tokens": 20000, "window": 200000, "percent": 10}
LIMITS = [{"kind": "five_hour", "percentUsed": 41.5, "resetsAt": "2026-10-12T14:05:00Z"}]
MEASURE = {"context": CONTEXT, "rateLimits": LIMITS, "cost": {"usd": 1.25},
           "changed": ["context", "rateLimits"]}


def M():
    """The module under test, imported per test so the pin reads red test by test."""
    from claude_session import measure
    return measure


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    return tmp_path / "xdg"


def run(*argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(list(argv))
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.stdin = old
    return rc, out.getvalue(), err.getvalue()


def record(obj, sid=SID):
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return run("measure", "record", "--session", sid, stdin=text)


def _files(root: Path) -> list:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def _transcript(tmp_path, context):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({
        "type": "assistant", "requestId": "r0", "timestamp": "2026-10-12T10:00:00Z",
        "message": {"id": "m0", "model": "claude-opus-5-5",
                    "content": [{"type": "text", "text": "<placeholder>"}],
                    "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                              "cache_read_input_tokens": context, "output_tokens": 7}}}) + "\n")
    return p


def _metered(tmp_path, context=18000):
    """A session the classic hooks resolved and metered at `context` tokens (10% of 180k)."""
    env = dict(os.environ)
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, env)
    tp = _transcript(tmp_path, context)
    out = hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp), "tool_name": "Read"}, env)
    return resolver.session_dir(resolver.state_dir(env), SID), tp, out


# ---- `measure record` (ruling 1) -----------------------------------------------------

def test_record_writes_measure_json_with_the_four_keys_and_at(state, tmp_path):
    sdir, _, _ = _metered(tmp_path)
    before = set(_files(sdir))
    rc, out, err = record(MEASURE)
    assert (rc, out, err) == (0, "", "")
    m = json.loads((sdir / "measure.json").read_text())
    assert set(m) == {"at", "context", "rateLimits", "cost", "changed"}
    assert {k: m[k] for k in MEASURE} == MEASURE
    assert datetime.fromisoformat(m["at"]).tzinfo is not None
    assert set(_files(sdir)) - before == {"measure.json"}          # it writes nothing else
    assert (sdir / "measure.json").stat().st_mode & 0o777 == 0o600
    assert M().MEASURE == "measure.json"


def test_record_an_absent_key_is_null(state, tmp_path):
    sdir, _, _ = _metered(tmp_path)
    assert record({"context": {"window": 200000}, "rateLimits": [], "changed": ["context"]})[0] == 0
    assert json.loads((sdir / "measure.json").read_text())["cost"] is None


@pytest.mark.parametrize("text", [
    json.dumps({**MEASURE, "prompt": "never kept"}),                # an unknown key
    '{"context": {"tokens": NaN, "window": 200000}, "changed": []}',  # a non-finite number
    '{"context": {"tokens": Infinity, "window": 200000}, "changed": []}',
    '{"cost": {"usd": 1e999}, "changed": []}',
    "{not json",                                                    # bad JSON
    "[]",                                                           # not one object
])
def test_record_refuses_and_writes_nothing(state, tmp_path, text):
    _metered(tmp_path)
    before = _files(state)
    rc, out, err = record(text)
    assert (rc, out) == (2, "")
    assert err.startswith("claude-session: ") and len(err.strip().splitlines()) == 1
    assert _files(state) == before


@pytest.mark.parametrize("bad", ["../escape", "a b", "x/y", "", "a" * 129, "ok\n"])
def test_record_bad_id_exits_2_and_writes_nothing(state, tmp_path, bad):
    _metered(tmp_path)
    before = _files(state)
    rc, out, err = record(MEASURE, sid=bad)
    assert (rc, out) == (2, "")
    assert err.startswith("claude-session: ") and len(err.strip().splitlines()) == 1
    assert _files(state) == before


def test_record_absent_session_exits_1_and_creates_nothing(state):
    before = _files(state)
    rc, out, err = record(MEASURE, sid="no-such-session")
    assert (rc, out) == (1, "")
    assert err.strip() == "claude-session: no session no-such-session"
    assert _files(state) == before


# ---- the drift: status and doctor (ruling 3) ------------------------------------------

def test_status_prints_measure_none_without_the_file(state, tmp_path):
    _metered(tmp_path)
    rc, out, _ = run("status")
    lines = out.splitlines()
    assert rc == 0 and lines[1] == "measure: none"
    assert lines[-1].startswith("mod: ")                        # mod's line stays the last
    rc, out, _ = run("status", "--json")
    assert "measure" not in json.loads(out)                    # --json stays meter.json


def test_status_prints_the_drift_when_the_two_are_within_120_s(state, tmp_path):
    _metered(tmp_path, 18000)
    record(MEASURE)
    rc, out, _ = run("status")
    assert rc == 0
    assert re.fullmatch(r"measure: engine 20000 tokens / meter 18000 tokens, drift 10\.0% "
                        r"\(\d+s apart\)", out.splitlines()[1]), out


def test_status_prints_not_comparable_past_120_s(state, tmp_path):
    sdir, _, _ = _metered(tmp_path)
    then = datetime.now(timezone.utc) - timedelta(seconds=300)
    M().record(SID, json.dumps(MEASURE), dict(os.environ), now=then)
    rc, out, _ = run("status")
    assert rc == 0
    assert re.fullmatch(r"measure: not comparable \(3\d\ds apart\)", out.splitlines()[1]), out


def test_doctor_measure_row_ok_without_the_file_or_under_10_percent(state, tmp_path):
    _metered(tmp_path, 18000)
    env = dict(os.environ)
    c = doctor._check_measure(env)
    assert (c.name, c.ok, c.warn) == ("measure", True, False) and c.detail.startswith("none")
    record({**MEASURE, "context": {**CONTEXT, "tokens": 19000}})
    c = doctor._check_measure(env)
    assert (c.ok, c.warn) == (True, False)
    assert "engine 19000 tokens" in c.detail and "meter 18000 tokens" in c.detail
    assert doctor.render(doctor.Report([c])).splitlines()[0].startswith("ok   measure ")


def test_doctor_measure_row_warns_at_10_percent_never_fails(state, tmp_path):
    _metered(tmp_path, 18000)
    record({**MEASURE, "context": {**CONTEXT, "tokens": 30000}})
    c = doctor._check_measure(dict(os.environ))
    assert (c.ok, c.warn) == (True, True)
    assert "engine 30000 tokens" in c.detail and "meter 18000 tokens" in c.detail
    assert "drift 40.0%" in c.detail
    assert doctor.render(doctor.Report([c])).splitlines()[0].startswith("warn measure ")


# ---- criterion 4: nothing that decides reads it -----------------------------------------

def test_criterion_4_measure_at_99_beside_meter_at_10_is_clear_and_silent(state, tmp_path):
    sdir, tp, first = _metered(tmp_path, 18000)
    assert first == {}
    assert record({"context": {"tokens": 198000, "window": 200000, "percent": 99},
                   "rateLimits": [{"kind": "five_hour", "percentUsed": 99, "resetsAt": None}],
                   "cost": {"usd": 99.0}, "changed": ["context", "rateLimits", "cost"]})[0] == 0
    env = dict(os.environ)
    for _ in range(12):                    # past CHECKPOINT_EVERY: no tool speaks
        out = hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp),
                                   "tool_name": "Read"}, env)
        assert "CHECKPOINT" not in json.dumps(out)
    m = meter.load(sdir)
    assert m["pct_context"] == 10.0 and m["zone"] == "clear"
    assert hooks.state(SID, env)[1] == "clear"


# ---- fix round 1 (F1, F2, the drift's figure) ------------------------------------------

def _ok(**over):
    return json.dumps({**MEASURE, **over})


def run_raw(data: bytes, errors="strict", sid=SID):
    """`measure record` with stdin as bytes through a real text layer (F2)."""
    old = sys.stdin
    sys.stdin = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors=errors)
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(["measure", "record", "--session", sid])
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.stdin = old
    return rc, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("text", [
    # F1's repro: nested unknown keys under context and a rate limit
    '{"context":{"tokens":1,"prompt":"secret prompt text"},"rateLimits":[{"kind":"x","message":"hi"}]}',
    _ok(context="free text"),
    _ok(context={**CONTEXT, "prompt": "secret prompt text"}),
    _ok(context={"tokens": 1, "percent": 1}),                       # window absent
    _ok(context={**CONTEXT, "window": 0}),
    _ok(context={**CONTEXT, "tokens": -1}),
    _ok(context={**CONTEXT, "tokens": "1"}),
    _ok(context={**CONTEXT, "tokens": True}),
    _ok(context={**CONTEXT, "percent": [1]}),
    pytest.param('{"context": {"tokens": 1%s, "window": 1}, "rateLimits": [], "changed": []}'
                 % ("0" * 400), id="int-past-a-double"),
    json.dumps({"rateLimits": [], "changed": []}),                  # context absent
    _ok(rateLimits=[{**LIMITS[0], "message": "hi"}]),
    _ok(rateLimits="five_hour"),
    _ok(rateLimits=[LIMITS[0]] * 17),
    _ok(rateLimits=[{**LIMITS[0], "kind": "k" * 65}]),
    _ok(rateLimits=[{**LIMITS[0], "kind": 5}]),
    _ok(rateLimits=[{**LIMITS[0], "percentUsed": "41"}]),
    _ok(rateLimits=[{"kind": "five_hour"}]),                        # percentUsed absent
    _ok(rateLimits=[{**LIMITS[0], "resetsAt": "r" * 65}]),
    _ok(rateLimits=["five_hour"]),
    _ok(cost={"usd": 1, "prompt": "x"}),
    _ok(cost="1.25"),
    _ok(cost={"usd": "1.25"}),
    _ok(changed=["prompt"]),
    _ok(changed="context"),
    _ok(changed=["context"] * 17),
    _ok(changed=[{"context": 1}]),
])
def test_f1_the_whole_shape_is_checked_and_a_wrong_one_writes_nothing(state, tmp_path, text):
    _metered(tmp_path)
    before = _files(state)
    rc, out, err = record(text)
    assert (rc, out) == (2, ""), err
    assert err.startswith("claude-session: ") and len(err.strip().splitlines()) == 1
    assert "secret" not in err
    assert _files(state) == before


def test_f1_the_optional_figures_may_be_null_or_absent(state, tmp_path):
    sdir, _, _ = _metered(tmp_path)
    assert record({"context": {"tokens": None, "window": 200000}, "cost": None,
                   "rateLimits": [{"kind": "seven_day", "percentUsed": 3, "resetsAt": None},
                                  {"kind": "five_hour", "percentUsed": 0}],
                   "changed": []})[0] == 0
    assert json.loads((sdir / "measure.json").read_text())["context"]["tokens"] is None


@pytest.mark.parametrize("text", [
    '{"changed":["\\ud800"]}',                                      # F2's repro: a lone surrogate
    _ok(rateLimits=[{"kind": "\ud800", "percentUsed": 1}]),
    _ok(rateLimits=[{**LIMITS[0], "resetsAt": "\udc80"}]),
    pytest.param("[" * 20000 + "]" * 20000, id="deep"),              # too deep for the parser
])
def test_f2_a_string_that_cannot_be_written_or_a_deep_nest_exits_2(state, tmp_path, text):
    _metered(tmp_path)
    before = _files(state)
    rc, out, err = record(text)
    assert (rc, out) == (2, "") and err.startswith("claude-session: ")
    assert _files(state) == before


@pytest.mark.parametrize("errors", ["strict", "surrogateescape"])
def test_f2_stdin_that_is_not_utf8_exits_2_and_writes_nothing(state, tmp_path, errors):
    _metered(tmp_path)
    before = _files(state)
    data = _ok(rateLimits=[{"kind": "KIND", "percentUsed": 1}]).encode().replace(b"KIND", b"\xff\xfe")
    rc, out, err = run_raw(data, errors=errors)
    assert (rc, out) == (2, "") and err.startswith("claude-session: "), err
    assert _files(state) == before


def test_f2_the_verb_refuses_bad_utf8_from_a_real_stdin(tmp_path):
    env = {**os.environ, "XDG_STATE_HOME": str(tmp_path / "xdg")}
    env.pop("CLAUDE_SESSION_CONFIG", None)
    p = subprocess.run([sys.executable, "-B", "-m", "claude_session", "measure", "record",
                        "--session", SID], input=b'{"changed": ["\xff"]}', capture_output=True,
                       env=env, timeout=60)
    assert p.returncode == 2, p.stderr
    assert p.stderr.decode().startswith("claude-session: ") and b"Traceback" not in p.stderr
    assert not (tmp_path / "xdg").exists()


def test_the_doctor_row_prints_the_figure_it_compares(state, tmp_path):
    _metered(tmp_path, 18000)
    record({**MEASURE, "context": {**CONTEXT, "tokens": 19998}})      # 1998/19998: 9.99%
    c = doctor._check_measure(dict(os.environ))
    assert c.warn is False and "drift 9.9%" in c.detail, c.detail
    record({**MEASURE, "context": {**CONTEXT, "tokens": 20000}})      # 2000/20000: 10%
    c = doctor._check_measure(dict(os.environ))
    assert c.warn is True and "drift 10.0%" in c.detail, c.detail
