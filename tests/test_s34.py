"""S34 act 2: a turn an API error ended (Claude Code's StopFailure) and the band's line
that names `/model` (packet S34 rulings 5, 6 and 8 (g), (h)).

StopFailure writes `limited.json` {at, error} for the main thread only, and never a
`turn-ended.json`: the launcher's RESPAWN logic reads that file, and no turn ended. The
band's limit note is pinned for both twins by one fixture in the mod's test file.
"""
import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from claude_session import hooks, mod, resolver

ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = ROOT / "plugin" / "hooks"
SID = "sess-1"


def _sdir() -> Path:
    return resolver.session_dir(resolver.state_dir(__import__("os").environ), SID)


def _dispatch(event, payload) -> tuple[int, str]:
    import sys
    out, old = io.StringIO(), sys.stdin
    sys.stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
    try:
        with redirect_stdout(out):
            rc = hooks.dispatch(event)
    finally:
        sys.stdin = old
    return rc, out.getvalue()


# ---- (g) StopFailure: limited.json, never turn-ended.json ------------------------------

def test_s34_g_rate_limit_writes_limited_only(monkeypatch):
    monkeypatch.setattr(hooks.time, "time", lambda: 1791806370.25)
    assert hooks.stop_failure({"session_id": SID, "hook_event_name": "StopFailure",
                               "error": "rate_limit", "error_details": "x" * 500}) == {}
    sdir = _sdir()
    assert json.loads((sdir / hooks.LIMITED).read_text()) == {"at": 1791806370.25,
                                                             "error": "rate_limit"}
    assert not (sdir / hooks.TURN_ENDED).exists()


def test_s34_g_a_helper_writes_nothing():
    hooks.stop_failure({"session_id": SID, "agent_id": "a1", "error": "rate_limit"})
    assert not _sdir().exists() or not (_sdir() / hooks.LIMITED).exists()


@pytest.mark.parametrize("payload", [
    None, [], "rate_limit", {}, {"session_id": "../x", "error": "rate_limit"},
    {"session_id": SID, "error": {"type": "rate_limit"}}, {"session_id": SID, "error": 7},
    {"session_id": SID}, {"session_id": [SID], "error": "rate_limit"},
])
def test_s34_g_a_malformed_payload_raises_nothing(payload):
    assert hooks.stop_failure(payload) == {}
    if isinstance(payload, dict) and payload.get("session_id") == SID:
        assert json.loads((_sdir() / hooks.LIMITED).read_text())["error"] is None
    assert not (_sdir() / hooks.TURN_ENDED).exists()


def test_s34_g_the_error_is_capped_at_64():
    hooks.stop_failure({"session_id": SID, "error": "e" * 200})
    assert json.loads((_sdir() / hooks.LIMITED).read_text())["error"] == "e" * 64


@pytest.mark.parametrize("raw", ['{"session_id": "sess-1", "error": "rate_limit"}',
                                 "{not json", '["x"]'])
def test_s34_g_dispatch_is_silent(raw):
    assert _dispatch("StopFailure", raw) == (0, "")
    assert "StopFailure" in hooks.HANDLERS and "stop-failure" in hooks.HANDLERS


def test_s34_g_the_plugin_registers_stopfailure_as_stop():
    reg = json.loads((HOOKS_DIR / "hooks.json").read_text())["hooks"]["StopFailure"]
    assert reg == [{"hooks": [{"type": "command", "timeout": 5,
                               "command": "${CLAUDE_PLUGIN_ROOT}/hooks/run StopFailure"}]}]
    shim = (HOOKS_DIR / "run").read_text()
    case = next(l for l in shim.splitlines() if l.strip().startswith("Stop|"))
    assert "StopFailure" in case.split(")")[0] and ">/dev/null 2>&1; exit 0" in case


# ---- (h) the band's limit note: one fixture, both twins --------------------------------

def _fixture() -> dict:
    text = (HOOKS_DIR / ("session.test." + "ts")).read_text()
    out = {k: re.search(rf"^const {k} = '(.*)'$", text, re.M).group(1)
           for k in ("LIMITED", "OVERLOADED", "ENDED_BEFORE", "ENDED_AFTER")}
    out["LIMIT_NOTE"] = re.search(r'^const LIMIT_NOTE = "(.*)"$', text, re.M).group(1)
    return out


def test_s34_h_the_twins_share_the_note():
    f = _fixture()
    assert f["LIMIT_NOTE"] == mod.LIMIT_NOTE
    assert mod.limit_note(f["LIMITED"], None) == f["LIMIT_NOTE"]
    assert mod.limit_note(f["LIMITED"], f["ENDED_BEFORE"]) == f["LIMIT_NOTE"]
    assert mod.limit_note(f["LIMITED"], f["ENDED_AFTER"]) is None
    assert mod.limit_note(f["OVERLOADED"], None) is None


@pytest.mark.parametrize("limited,ended", [
    (None, None), ("{bad", None), ('{"at": "1", "error": "rate_limit"}', None),
    ('{"at": true, "error": "rate_limit"}', None), ('{"error": "rate_limit"}', None),
    ('["rate_limit"]', None), ('{"at": 5, "error": "rate_limit"}', '{"at": 5}'),
])
def test_s34_h_no_note(limited, ended):
    assert mod.limit_note(limited, ended) is None


@pytest.mark.parametrize("ended", ["{bad", '{"at": null}', "[]"])
def test_s34_h_an_unreadable_turn_end_reads_as_none(ended):
    assert mod.limit_note('{"at": 5, "error": "rate_limit"}', ended) == mod.LIMIT_NOTE


def test_s34_h_the_hooks_feed_the_note(monkeypatch):
    # The next good turn's turn-ended.json clears the note by being later.
    clock = iter([100.0, 200.0])
    monkeypatch.setattr(hooks.time, "time", lambda: next(clock))
    hooks.stop_failure({"session_id": SID, "error": "rate_limit"})
    read = lambda name: ((_sdir() / name).read_text()
                         if (_sdir() / name).exists() else None)
    assert mod.limit_note(read(hooks.LIMITED), read(hooks.TURN_ENDED)) == mod.LIMIT_NOTE
    hooks.stop({"session_id": SID})
    assert mod.limit_note(read(hooks.LIMITED), read(hooks.TURN_ENDED)) is None
