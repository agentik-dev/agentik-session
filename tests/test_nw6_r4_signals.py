"""Packet nw6-held-respawn, R4 and fix round 1's Z1: when the launcher signals is the pin's.

Six scenarios on test_chain's fake effects in the temp state, each a control: every assert
here holds at the pin (main before nw6) and at the branch's head alike. Only the moment of
the signal and the starts are asserted, never what held.json says (that is
test_nw6_held_respawn's). No launcher of this machine is read or signalled."""
import json
import os

from claude_session import admission
from test_chain import G, T0, TERM, _frun, _fx, _state, end, fake, hook, respawn_seq  # noqa: F401


def _spawn_line(aid, desc):
    def act(fx, p):
        d = _state() / admission.DIR
        d.mkdir(parents=True, exist_ok=True)
        if (d / admission.LEDGER).is_fifo():
            return
        with open(d / admission.LEDGER, "a") as f:
            f.write(json.dumps({"ts": "2026-11-24T10:00:00+00:00", "session": p.sid,
                                "kind": "spawn", "description": desc, "agentId": aid,
                                "tool_use_id": f"toolu_{aid}"}) + "\n")
    return act


def _call(event, aid, tid):
    return hook(event, tool_use_id=tid, agent_id=aid, tool_name="Bash")


def _signal(fx):
    ((t, sig),) = fx.procs[0].signals
    assert sig == TERM
    return t - T0


BASE = [(11, _spawn_line("a1", "build nw6")), (12, _call("PreToolUse", "a1", "toolu_01")),
        (1100, _call("PostToolUse", "a1", "toolu_01"))]


def test_r4_base(fake, monkeypatch):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + BASE + [end(7200)], [end(1)]])
    _frun(fx, G)
    assert 1160 <= _signal(fx) <= 1162 and len(fx.procs) == 2


def test_r4_a_read_only_chain_home(fake, monkeypatch):
    home = _state() / "respawn" / "c1"

    def lock_up(fx, p):
        os.chmod(home, 0o500)
    try:
        fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [(11, lock_up)] + BASE + [end(7200)],
                               [end(1)]])
        _frun(fx, G)
    finally:
        os.chmod(home, 0o700)
    assert 1160 <= _signal(fx) <= 1162 and len(fx.procs) == 2


def test_r4_the_sittings_own_turn_after_the_helpers_end(fake, monkeypatch):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + BASE
                           + [(1105, hook("UserPromptSubmit", prompt="go")),
                              (1800, hook("Stop")), end(7200)], [end(1)]])
    _frun(fx, G)
    assert 1860 <= _signal(fx) <= 1862 and len(fx.procs) == 2


def test_r4_a_ledger_that_is_a_fifo(fake, monkeypatch):
    d = _state() / admission.DIR
    d.mkdir(parents=True, exist_ok=True)
    os.mkfifo(d / admission.LEDGER)
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + BASE + [end(7200)], [end(1)]])
    _frun(fx, G)
    assert 1160 <= _signal(fx) <= 1162 and len(fx.procs) == 2


def test_r4_two_helpers(fake, monkeypatch):
    seq = [(11, _spawn_line("a1", "build nw6")), (11, _spawn_line("a2", "review nw6")),
           (12, _call("PreToolUse", "a1", "toolu_01")), (20, _call("PreToolUse", "a2", "toolu_02")),
           (700, _call("PostToolUse", "a1", "toolu_01")),
           (900, _call("PostToolUse", "a2", "toolu_02"))]
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + seq + [end(7200)], [end(1)]])
    _frun(fx, G)
    assert 960 <= _signal(fx) <= 962 and len(fx.procs) == 2


def test_r4_a_planted_foreign_record(fake, monkeypatch):
    home = _state() / "respawn" / "c1"
    home.mkdir(parents=True, exist_ok=True)
    (home / "held.json").write_text(json.dumps(
        {"reason": "helpers", "since": T0 - 3600, "session": "another-sess-0000",
         "by": ["build nw6"], "pid": 1, "started": T0 - 86400}))
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)], [end(1)]])
    _frun(fx, G)
    assert 74 <= _signal(fx) <= 76 and len(fx.procs) == 2
    assert not (home / "held.json").exists()   # the record went at the first say
