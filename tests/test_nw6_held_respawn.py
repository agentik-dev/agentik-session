"""Packet nw6-held-respawn: a marked respawn says what holds it, at the mark (R1), on the
prompt's line and in `status` (R2), from the one record the launcher writes (R3).

Every case runs on stand-ins: the fake effects of test_chain, a temp state folder, a
made-up session and helpers; no launcher of this machine is read or signalled."""
import io
import json
import os
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

import pytest

from claude_session import admission, cli, config, hooks, resolver
from test_chain import (G, T0, TERM, _frun, _fx, _held, _peek, _state, end, fake,  # noqa: F401
                        hook, respawn_seq)

SID = "cli-sess-0000-1111-2222"
CHARTER = ("# Sitting 2026-11-24-1: r, c\n\n| item | value |\n|---|---|\n| goal | g |\n"
           "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n"
           "## Done-ness\n- [x] a\n\n## Handover\n- h\n\n## Next act\nRESPAWN: next\n")
LAUNCHER = "respawn marked; the launcher restarts this sitting after this turn ends"
METER = os.path.join(os.path.dirname(__file__), "fixtures", "meter", "under-80.jsonl")


def _run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _ledger(*rows):
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / admission.LEDGER, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _spawn(sid, aid, desc, at, background=None, tid=None):
    return {"ts": _iso(at), "session": sid, "kind": "spawn", "subagentType": "general-purpose",
            "description": desc, "background": background, "agentId": aid,
            "tool_use_id": tid or f"toolu_{aid}"}


def _done(aid, at):
    return {"ts": _iso(at), "session": SID, "kind": "done", "agentId": aid,
            "tool_use_id": f"toolu_{aid}", "durationMs": 1000}


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "c.md").write_text(CHARTER)
    return tmp_path


def _mark():
    rc, out, err = _run("checkpoint", "--respawn", "--charter", "c.md")
    assert rc == 0, err
    return out.splitlines()[-1]


# ---- R1: the mark's line -------------------------------------------------------------------

def test_r1_no_helper_out_is_the_pins_line(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    now = time.time()
    _ledger(_spawn(SID, "a1", "an ended one", now - 600), _done("a1", now - 300),
            _spawn("another-sess-0000", "a9", "not this session's", now - 60))
    assert _mark() == LAUNCHER


def test_r1_no_ledger_is_the_pins_line(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    assert _mark() == LAUNCHER


def test_r1_one_helper_out_is_named(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _ledger(_spawn(SID, "a1", "build nw6", time.time() - 60))
    line = _mark()
    assert line == ('respawn marked; the restart waits on 1 helper out: "build nw6"; the '
                    "launcher restarts this sitting once they are quiet and this turn has ended")
    assert "after this turn ends" not in line


def test_r1_each_out_by_label_and_background(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    now = time.time()
    _ledger(_spawn(SID, "a1", "build\tnw6\n part A", now - 90, background=True),
            _spawn(SID, "a2", "x" * 80, now - 60),
            {**_spawn(SID, "a3", None, now - 30), "subagentType": "relay:reviewer"})
    line = _mark()
    assert line.startswith('respawn marked; the restart waits on 3 helpers out: '
                           f'"build nw6 part A (background)", "{"x" * 57}...", "relay:reviewer"; ')
    assert "after this turn ends" not in line


def test_r1_no_launcher_line_is_unchanged(cli_env):
    _ledger(_spawn(SID, "a1", "build nw6", time.time() - 60))
    assert _mark() == "respawn marked; no launcher runs this sitting: print your start line and stop"


# ---- R2: the prompt's line and status, from held.json ---------------------------------------

def _session(env):
    repo = env / "repo"
    repo.mkdir(exist_ok=True)
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, dict(os.environ))
    hooks.post_tool_use({"session_id": SID, "transcript_path": METER}, dict(os.environ))


def _marked(marked):
    """This session's marker and the main thread's confirm of it, as the close leaves them."""
    import hashlib
    sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
    sdir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"session": SID, "charter": "c.md", "charter_sha256": "0" * 64,
                      "written": marked, "chain": "c1"}).encode()
    (sdir / hooks.MARKER).write_bytes(raw)
    (sdir / hooks.CONFIRMED).write_text(json.dumps(
        {"at": marked + 1, "marker_sha256": hashlib.sha256(raw).hexdigest()}))


def _record(marked, since, by=("build nw6",), pid=None, session=SID, reason="helpers"):
    _marked(marked)
    home = resolver.state_dir(os.environ) / "respawn" / "c1"
    home.mkdir(parents=True, exist_ok=True)
    (home / "held.json").write_text(json.dumps(
        {"reason": reason, "since": since, "session": session, "by": list(by),
         "pid": os.getpid() if pid is None else pid}))


def _prompt():
    (resolver.session_dir(resolver.state_dir(os.environ), SID) / hooks.METER_LINE).unlink(
        missing_ok=True)                        # the meter line due on each prompt here
    out = hooks.user_prompt_submit({"session_id": SID, "prompt": "go"})
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


MARKED = time.mktime((2026, 11, 24, 11, 6, 0, 0, 0, -1))
CLAUSE = 'respawn marked at 11:06, held 121 min by 1 helper: "build nw6"'


def test_r2_held_clause_on_the_prompt_and_in_status(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _marked(MARKED)
    plain = _prompt()
    assert "respawn" not in plain and "session meter:" in plain, plain
    now = MARKED + 121 * 60 + 70
    _record(MARKED, MARKED + 70)
    monkeypatch.setattr(time, "time", lambda: now)
    got = _prompt()
    meter = [p for p in got.split("\n\n") if p.startswith("session meter:")]
    assert len(meter) == 1 and meter[0].endswith(f"; {CLAUSE}"), got
    assert got.replace(f"; {CLAUSE}", "") == plain
    rc, out, _ = _run("status")
    assert rc == 0 and CLAUSE in out.splitlines(), out
    assert not [l for l in out.splitlines() if l.startswith("respawn held")], out
    rc, out, _ = _run("status", "--json")
    d = json.loads(out)["respawn_held"]
    assert d == {"marked": MARKED, "since": MARKED + 70, "held_minutes": 121,
                 "by": ["build nw6"], "line": CLAUSE}


def test_r2_two_holders_counted(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _record(MARKED, MARKED + 70, by=("build nw6", "review nw6 (background)"))
    monkeypatch.setattr(time, "time", lambda: MARKED + 70 + 5 * 60)
    assert ('respawn marked at 11:06, held 5 min by 2 helpers: "build nw6", '
            '"review nw6 (background)"') in _prompt()


@pytest.mark.parametrize("case", ["none", "stale", "other-session", "no-chain", "no-marker"])
def test_r2_nothing_new_without_a_live_hold(case, cli_env, monkeypatch):
    if case != "no-chain":
        monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    if case not in ("none", "no-marker"):
        _marked(MARKED)
    plain, (rc0, status0, _), (rc1, json0, _) = _prompt(), _run("status"), _run("status", "--json")
    if case != "none":
        _record(MARKED, MARKED + 70, pid=_dead_pid() if case == "stale" else None,
                session="another-sess-0000" if case == "other-session" else SID)
        if case == "no-marker":
            sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
            (sdir / hooks.MARKER).unlink()
            (sdir / hooks.CONFIRMED).unlink()
    assert _prompt() == plain
    rc, out, _ = _run("status")
    assert rc == rc0 == 0 and out == status0
    rc, out, _ = _run("status", "--json")
    a, b = json.loads(out), json.loads(json0)
    assert "respawn_held" not in a and set(a) == set(b)


def test_r2_a_checks_hold_is_said_as_at_the_pin(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _marked(MARKED)
    plain = _prompt()
    since = time.mktime((2026, 10, 29, 7, 5, 0, 0, 0, -1))
    _record(MARKED, since, reason="floor")
    assert _prompt() == plain
    rc, out, _ = _run("status")
    assert "respawn held: floor since 07:05" in out.splitlines(), out


# ---- R3: the launcher writes the record while the helpers hold, and removes it ---------------

def test_r3_the_launcher_writes_the_record_and_removes_it_at_the_signal(fake, monkeypatch):
    helper = {"agent_id": "a1", "tool_name": "Bash"}
    seen = []

    def spawn_line(fx, p):
        d = _state() / admission.DIR
        d.mkdir(parents=True, exist_ok=True)
        (d / admission.LEDGER).write_text(json.dumps(
            _spawn(p.sid, "a1", "build nw6", fx.t, background=True)) + "\n")

    seq = (respawn_seq(fake.charter)
           + [(11, spawn_line), (12, hook("PreToolUse", tool_use_id="toolu_01", **helper)),
              (60, _peek(seen)), (300, _peek(seen)), (600, hook("UserPromptSubmit")),
              (601, _peek(seen)), (650, hook("Stop")), (1100, hook("PostToolUse", tool_use_id="toolu_01", **helper)),
              (1130, _peek(seen)), end(7200)])
    fx = _fx(monkeypatch, [seq, [(0, _peek(seen)), end(1)]])
    _frun(fx, G)
    sid = fx.procs[0].sid
    ((t, sig),) = fx.procs[0].signals             # R4: the signal as at the pin
    assert sig == TERM and 1160 <= t - T0 <= 1162, t - T0
    assert seen[0] is None                        # the turn has not yet stood `settle`
    rec = seen[1]
    assert rec == {"reason": "helpers", "since": rec["since"], "session": sid,
                   "by": ["build nw6 (background)"], "pid": os.getpid()}, rec
    assert 74 <= rec["since"] - T0 <= 76
    assert seen[2] == rec                         # the sitting's own turn: the record stands
    assert seen[3] == rec                         # the stamp alone: the labels already said
    assert seen[4] is None and _held() is None    # removed when it signalled


def test_r3_a_record_whose_launcher_is_gone_prints_nothing(cli_env, monkeypatch):
    from claude_session import chain
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _record(MARKED, MARKED + 70, pid=_dead_pid())
    st = resolver.state_dir(os.environ)
    assert chain.held_by(st, "c1", SID, MARKED + 600) is None
    _record(MARKED, MARKED + 70)
    assert chain.held_by(st, "c1", SID, MARKED + 600)["by"] == ["build nw6"]
