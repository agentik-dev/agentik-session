"""Packet rc3-respawn-short: pl2 R7's respawn line at PostToolUse is said in the first of
three forms that fits MAX_OUT beside the handler's words (R1), and under a chain the
CHECKPOINT line names the charter by the first spelling that leaves room for the short form
(R2); with no respawn line due every output is the pin's (R3). Every state is made up, under
the per-test temp HOME conftest gives; the pin's `hooks.py` is read from git into a module of
its own for acceptance 7."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import hooks, meter, resolver

ROOT = Path(__file__).resolve().parent.parent
PIN = "d7e53a2"
SID = "test-sess-0000-7777-9999"
SCRIPT = "zsh wind-down.sh"
REL = "history/sittings/2026-11-20-9.md"
FIX = ROOT / "tests" / "fixtures" / "meter"


@pytest.fixture
def hk(frontier_home, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.delenv(hooks.CHAIN_VAR, raising=False)
    return frontier_home


def _sdir() -> Path:
    d = resolver.session_dir(resolver.state_dir(os.environ), SID)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _due(charter: str, due: bool = True) -> None:
    """The main thread's call stamped, then this session's chained marker written after it
    and no confirm: pl2 R7's line is due. `due` False: no marker."""
    s = _sdir()
    (s / hooks.ACTIVITY).write_text(json.dumps({"event": "PreToolUse", "tool": "Bash",
                                                "at": 1000.0}))
    if due:
        (s / hooks.MARKER).write_text(json.dumps(
            {"session": SID, "charter": charter, "charter_sha256": "0" * 64,
             "written": 1001.0, "chain": "net"}))


def _bash(**extra) -> dict:
    return {"session_id": SID, "tool_name": "Bash", "tool_use_id": "toolu_01WindDown",
            "tool_input": {"command": SCRIPT}, **extra}


def _ctx(out) -> str:
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


def _blocks(out) -> list:
    return _ctx(out).split("\n\n")


def _recorded(tmp_path) -> tuple[str, str]:
    """A charter `charter open` recorded under the call's cwd: (cwd, absolute path)."""
    cwd = tmp_path / "w" / "example-app"
    f = cwd / REL
    f.parent.mkdir(parents=True)
    f.write_text("# a charter\n")
    (_sdir() / hooks.CHARTER_REC).write_text(json.dumps({"path": str(f)}))
    return str(cwd), str(f)


def test_the_short_form_is_the_brief_s():
    assert hooks.UNCONFIRMED_SHORT == "RESPAWN unconfirmed: run the close again in the foreground."


# ---- acceptance 1 to 3: the real meter, a recorded charter ----

def test_1_the_crossing_under_a_chain_says_the_short_form(hk, tmp_path, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "net")
    cwd, f = _recorded(tmp_path)
    _due(f)
    out = hooks.post_tool_use(_bash(cwd=cwd, transcript_path=str(FIX / "at-80.jsonl")),
                              os.environ)
    b = _blocks(out)
    assert b[0].startswith("CHECKPOINT: ") and "\nEXIT" not in b[0], b
    assert b[1:] == [hooks.UNCONFIRMED_SHORT], b
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_2_past_100_the_exit_rule_then_the_short_form(hk, tmp_path, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "net")
    cwd, f = _recorded(tmp_path)
    _due(f)
    out = hooks.post_tool_use(_bash(cwd=cwd, transcript_path=str(FIX / "at-100.jsonl")),
                              os.environ)
    b = _blocks(out)
    assert b[0].startswith("CHECKPOINT: ") and b[0].endswith("\n" + hooks.EXIT_RULE), b
    assert b[1:] == [hooks.UNCONFIRMED_SHORT], b
    assert len(json.dumps(out)) <= hooks.MAX_OUT
    # The spelling that leaves the room: the relative one (the pin's) leaves none here.
    assert f"charter {hooks.NO_CHARTER}; " in b[0] and REL not in b[0], b[0]


def test_3_off_a_launcher_past_100_the_pin_s_line_then_the_first_form(hk, tmp_path):
    cwd, f = _recorded(tmp_path)
    _due(f)
    p = _bash(cwd=cwd, transcript_path=str(FIX / "at-100.jsonl"))
    was = _pin_hooks().post_tool_use(p, os.environ)
    assert len(_blocks(was)) == 1                     # the pin: the line dropped
    out = hooks.post_tool_use(p, os.environ)
    b = _blocks(out)
    assert b[0] == _ctx(was) and "bring the charter current, commit, then exit" in b[0], b
    forms = [hooks.UNCONFIRMED.format(f=f), hooks.UNCONFIRMED.format(f=hooks.UNSAFE_CHARTER),
             hooks.UNCONFIRMED_SHORT]
    fits = [x for x in forms if len(json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                "additionalContext": b[0] + "\n\n" + x}})) <= hooks.MAX_OUT]
    assert fits and b[1:] == fits[:1], (b, fits)
    assert len(json.dumps(out)) <= hooks.MAX_OUT


# ---- acceptance 4 to 6: no CHECKPOINT line due ----

def test_4_no_checkpoint_line_the_full_line(hk):
    f = "/w/example-app/" + REL
    _due(f)
    out = hooks.post_tool_use(_bash(), os.environ)
    assert out == {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                          "additionalContext": hooks.UNCONFIRMED.format(f=f)}}


def test_5_a_700_character_path_says_the_line_with_the_charter_unnamed(hk):
    f = "/w/" + "a" * (700 - len("/w/") - len("/" + REL)) + "/" + REL
    assert len(f) == 700 and hooks._SAFE_PATH.match(f)
    _due(f)
    out = hooks.post_tool_use(_bash(), os.environ)
    assert out == {"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": hooks.UNCONFIRMED.format(f=hooks.UNSAFE_CHARTER)}}


def test_6_where_not_even_the_short_form_fits_the_output_is_the_handler_s(hk, monkeypatch):
    _due("/w/example-app/" + REL)

    def said(ctx):
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}}
    k = hooks.MAX_OUT + 1 - len(json.dumps(said("CHECKPOINT: \n\n" + hooks.UNCONFIRMED_SHORT)))
    big = said("CHECKPOINT: " + "x" * k)
    assert len(json.dumps(said(_ctx(big) + "\n\n" + hooks.UNCONFIRMED_SHORT))) == hooks.MAX_OUT + 1
    monkeypatch.setattr(hooks, "_post_meter", lambda *a, **k: big)
    assert hooks.post_tool_use(_bash(), os.environ) == big


# ---- acceptance 7: the table, against the pin's module ----

def _pin_hooks():
    name = "claude_session._hooks_at_pin"
    if name in sys.modules:
        return sys.modules[name]
    src = subprocess.run(["git", "show", f"{PIN}:plugin/lib/claude_session/hooks.py"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "claude_session"
    mod.__file__ = str(ROOT / "plugin" / "lib" / "claude_session" / "hooks_at_pin.py")
    sys.modules[name] = mod
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return mod


def _spellings(n: int) -> list:
    rel = "h/2026-11-20-9.md" if n < 40 else REL
    return ["/" + "w" * (n - 2 - len(rel)) + "/" + rel, rel]


def _meter(pct: float, ceiling: int) -> meter.Meter:
    return meter.Meter(session_id=SID, turns=120, sidechain_turns=0, tokens=0,
                       context=int(ceiling * pct / 100), max_context=0, median_context=0,
                       model=None, started=None, ceilings={"context": ceiling, "turns": 400},
                       window=None, checkpoint_at=0.8, pct_context=pct, pct_turns=30.0,
                       zone="checkpoint", ts="", transcript={})


STATES = [(pct, chained, due, n, ceiling)
          for pct in (80.3, 100.4) for chained in (True, False) for due in (True, False)
          for n in (20, 72, 200) for ceiling in (400_000, 1_000_000)]
TABLE: list = []


@pytest.mark.parametrize("pct,chained,due,n,ceiling", STATES)
def test_7_the_table_of_states(pct, chained, due, n, ceiling, hk, monkeypatch):
    pin = _pin_hooks()
    abs_, rel = _spellings(n)
    assert len(abs_) == n
    if chained:
        monkeypatch.setenv(hooks.CHAIN_VAR, "net")
    for mod in (hooks, pin):
        monkeypatch.setattr(mod, "_charter_file", lambda *a: [abs_, rel, hooks.NO_CHARTER])
    monkeypatch.setattr(meter, "parse", lambda *a, **k: _meter(pct, ceiling))
    p = _bash(cwd="/w/example-app", transcript_path="/w/t.jsonl")
    outs = []
    for mod in (pin, hooks):
        _due(abs_, due)
        outs.append(mod.post_tool_use(p, os.environ))
    was, now = outs
    TABLE.append((pct, chained, due, n, ceiling, len(json.dumps(was)), len(json.dumps(now)),
                  _said_form(now)))
    assert len(json.dumps(now)) <= hooks.MAX_OUT
    assert _blocks(now)[0].startswith("CHECKPOINT: "), now
    if not due:
        assert now == was
    elif chained:
        assert _blocks(now)[1:] == [hooks.UNCONFIRMED_SHORT], now
    else:
        assert _said_form(now) != "none", now


def _said_form(out) -> str:
    b = _blocks(out)[1:]
    if not b:
        return "none"
    if b == [hooks.UNCONFIRMED_SHORT]:
        return "short"
    if b == [hooks.UNCONFIRMED.format(f=hooks.UNSAFE_CHARTER)]:
        return "unnamed"
    return "full"


def test_7_the_table_printed():
    """The lengths for the sitting's record (`pytest -s -k table_printed`), after the table."""
    print()
    for row in TABLE:
        print("| {} | {} | {} | {} | {} | {} | {} | {} |".format(*row))
