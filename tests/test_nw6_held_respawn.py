"""Packet nw6-held-respawn: a marked respawn says what holds it, at the mark (R1), on the
prompt's line and in `status` (R2), from the one record the launcher writes (R3).

Every case runs on stand-ins: the fake effects of test_chain, a temp state folder, a
made-up session and helpers; no launcher of this machine is read or signalled."""
import io
import json
import os
import re
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

import pytest

from claude_session import admission, chain, cli, config, hooks, resolver, room
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


def _open(aid, tid, at, sid=SID):
    """A helper's open call, as its PreToolUse leaves it: `calls/<tool_use_id>`."""
    calls = resolver.session_dir(resolver.state_dir(os.environ), sid) / hooks.CALLS
    calls.mkdir(parents=True, exist_ok=True)
    (calls / tid).write_text(json.dumps({"at": at, "agent_id": aid}))


def _stamp(at, sid=SID):
    sdir = resolver.session_dir(resolver.state_dir(os.environ), sid)
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / hooks.HELPER_ACTIVITY).write_text(json.dumps({"event": "PostToolUse", "at": at}))


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
    _open("a1", "toolu_01", time.time() - 50)              # Z2: the launcher waits on its call
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
    for i in (1, 2, 3):
        _open(f"a{i}", f"toolu_0{i}", now - 20)
    line = _mark()
    assert line.startswith('respawn marked; the restart waits on 3 helpers out: '
                           f'"build nw6 part A (background)", "{"x" * 57}...", "relay:reviewer"; ')
    assert "after this turn ends" not in line


# ---- Z2: the mark names what the launcher's rule waits on, the ledger for labels alone ------

def test_z2_a_run_with_no_done_and_no_open_call_is_not_named(cli_env, monkeypatch):
    """Review 1's F2, the crashed helper: a spawn line an hour old, no `done`, no call open."""
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _ledger(_spawn(SID, "a1", "crashed helper", time.time() - 3600))
    assert _mark() == LAUNCHER


def test_z2_a_stale_call_is_not_named_and_a_fresh_stamp_is(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    now = time.time()
    _ledger(_spawn(SID, "a1", "build nw6", now - 3600))
    _open("a1", "toolu_01", now - 1300)                   # past STALE_CALL, no stamp since
    _stamp(now - 1300)
    assert _mark() == LAUNCHER
    _stamp(now - 10)                                      # the helpers' stamp under `settle`
    assert _mark().startswith('respawn marked; the restart waits on 1 helper out: "build nw6"')
    (resolver.session_dir(resolver.state_dir(os.environ), SID) / hooks.CALLS / "toolu_01").unlink()
    assert _mark().startswith('respawn marked; the restart waits on 1 helper out: "a helper"')


def test_z2_an_open_call_with_no_spawn_line_is_a_helper(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _open("a7", "toolu_07", time.time() - 5)
    _open("a8", "toolu_08", time.time() - 5, sid="another-sess-0000")
    assert _mark().startswith('respawn marked; the restart waits on 1 helper out: "a helper"; ')


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


def _record(marked, since, by=("build nw6",), pid=None, session=SID, reason="helpers",
            started=None):
    _marked(marked)
    home = resolver.state_dir(os.environ) / "respawn" / "c1"
    home.mkdir(parents=True, exist_ok=True)
    pid = os.getpid() if pid is None else pid
    (home / "held.json").write_text(json.dumps(
        {"reason": reason, "since": since, "session": session, "by": list(by), "pid": pid,
         "started": chain.proc_started(pid) if started is None else started}))


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
    rec = seen[0]                                 # Z1: said from the first poll that holds
    assert rec == {"reason": "helpers", "since": rec["since"], "session": sid,
                   "by": ["build nw6 (background)"], "pid": os.getpid(),
                   "started": chain.proc_started(os.getpid())}, rec
    assert 12 <= rec["since"] - T0 <= 16 and rec["started"]
    assert seen[1] == seen[2] == rec              # its call open, the sitting's turn or not
    assert seen[3] == {**rec, "by": ["a helper"]}   # the stamp alone: no ended helper named
    assert seen[4] is None and _held() is None    # removed when it signalled


def _prompt_seen(box):
    """The sitting's prompt at this moment: held.json and the hook's words of the hold."""
    def act(fx, p):
        with pytest.MonkeyPatch.context() as m:
            m.setenv(hooks.CHAIN_VAR, "c1")
            out = hooks.user_prompt_submit({"session_id": p.sid, "prompt": "go"})
        text = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        box.append((fx.t - T0, _held(), [b for b in text.split("; ") if "respawn marked" in b]))
    return act


def test_z1_the_record_never_names_a_helper_that_has_ended(fake, monkeypatch):
    """Review 1's F1 (test_probe_c): `build nw6` opens a call at 12 and closes it at 1100;
    the sitting is woken at 1105 and stops at 1800; a peer's prompt comes at 1830."""
    helper = {"agent_id": "a1", "tool_name": "Bash"}
    seen = []

    def spawn_line(fx, p):
        d = _state() / admission.DIR
        d.mkdir(parents=True, exist_ok=True)
        (d / admission.LEDGER).write_text(json.dumps(_spawn(p.sid, "a1", "build nw6", fx.t)) + "\n")

    seq = (respawn_seq(fake.charter)
           + [(11, spawn_line), (12, hook("PreToolUse", tool_use_id="toolu_01", **helper)),
              (600, _prompt_seen(seen)), (650, hook("Stop")),
              (1100, hook("PostToolUse", tool_use_id="toolu_01", **helper)),
              (1105, _prompt_seen(seen)), (1800, hook("Stop")), (1830, _prompt_seen(seen)),
              (1840, hook("Stop")), end(7200)])
    fx = _fx(monkeypatch, [seq, [end(1)]])
    _frun(fx, G)
    ((t, sig),) = fx.procs[0].signals
    assert sig == TERM and 1900 <= t - T0 <= 1902, t - T0      # R4: as at the pin
    (_, rec, words), (_, rec2, words2), (_, rec3, words3) = seen
    assert rec3 is None and words3 == [], (rec3, words3)   # the own turn: no helper holds
    assert rec2["by"] == ["a helper"] and "build nw6" not in str(words2)   # the stamp alone
    assert rec["by"] == ["build nw6"] and words == [
        f'respawn marked at {time.strftime("%H:%M", time.localtime(T0 + 12))}, held 9 min by '
        '1 helper: "build nw6"'], words



def test_r3_a_record_whose_launcher_is_gone_prints_nothing(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _record(MARKED, MARKED + 70, pid=_dead_pid())
    st = resolver.state_dir(os.environ)
    assert chain.held_by(st, "c1", SID, MARKED + 600) is None
    _record(MARKED, MARKED + 70)
    assert chain.held_by(st, "c1", SID, MARKED + 600)["by"] == ["build nw6"]


# ---- Z3: the record's start time beside its pid; the hold from the later of mark and since ---

def test_z3_a_live_pid_under_another_start_time_is_stale(cli_env, monkeypatch):
    """Review 1's N1: a pid reused by another process makes no line."""
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    st, mine = resolver.state_dir(os.environ), chain.proc_started(os.getpid())
    assert mine and chain.proc_started(_dead_pid()) is None
    for pid, started in ((os.getpid(), mine + 1), (1, mine), (os.getpid(), "x")):
        _record(MARKED, MARKED + 70, pid=pid, started=started)
        assert chain.held_by(st, "c1", SID, MARKED + 600) is None, (pid, started)
    _record(MARKED, MARKED + 70)
    home = st / "respawn" / "c1"
    d = json.loads((home / "held.json").read_text())
    del d["started"]
    (home / "held.json").write_text(json.dumps(d))
    assert chain.held_by(st, "c1", SID, MARKED + 600) is None      # no start time: stale
    _record(MARKED, MARKED + 70)
    assert chain.held_by(st, "c1", SID, MARKED + 600)["by"] == ["build nw6"]


def test_z3_the_hold_counts_from_the_later_of_the_mark_and_since(cli_env, monkeypatch):
    """Review 1's N2: a re-mark an hour into a hold; status read 5 minutes after it."""
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _record(MARKED + 3600, MARKED)
    monkeypatch.setattr(time, "time", lambda: MARKED + 3600 + 300)
    rc, out, _ = _run("status")
    assert rc == 0 and 'respawn marked at 12:06, held 5 min by 1 helper: "build nw6"' in out, out


# ---- Z4: a label is read again at each write; only printable ASCII of it prints -------------

def test_z4_only_printable_ascii_of_a_label_prints():
    """Review 1's N4: bidi, C1, zero-width and surrogate characters are `?`."""
    got = [room.label({"description": d}) for d in
           ("a\tb", "a\x00b", "x‮evil", "a\u009bb", "z​​", "\ud800bad",
            "build\nrespawn held: none", 'say "hi"', "café")]
    assert got == ["a b", "a?b", "x?evil", "a?b", "z??", "?bad", "build respawn held: none",
                   "say 'hi'", "caf?"]
    assert all(s.isascii() and s.isprintable() for s in got)


def test_z4_a_foreign_record_prints_in_ascii_and_never_crashes_status(cli_env, monkeypatch):
    """Review 1's N5: a lone surrogate in a foreign record's `by`."""
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _record(MARKED, MARKED + 70, by=("ok\udc80x", "b‮c"))
    monkeypatch.setattr(time, "time", lambda: MARKED + 70 + 60)
    rc, out, err = _run("status")
    assert rc == 0, err
    assert 'held 1 min by 2 helpers: "ok?x", "b?c"' in out, out
    rc, out, _ = _run("status", "--json")
    assert rc == 0 and json.loads(out)["respawn_held"]["by"] == ["ok?x", "b?c"]
    assert '"ok?x", "b?c"' in _prompt()


def test_z4_a_label_is_read_again_at_each_write(fake, monkeypatch):
    """Review 1's N3 (test_probe_d): the spawn line lands at 200, the call is open from 12."""
    helper = {"agent_id": "a1", "tool_name": "Bash"}
    seen = []

    def spawn_line(fx, p):
        d = _state() / admission.DIR
        d.mkdir(parents=True, exist_ok=True)
        (d / admission.LEDGER).write_text(json.dumps(_spawn(p.sid, "a1", "build nw6", fx.t)) + "\n")

    seq = (respawn_seq(fake.charter)
           + [(12, hook("PreToolUse", tool_use_id="toolu_01", **helper)), (100, _peek(seen)),
              (200, spawn_line), (300, _peek(seen)), (900, _peek(seen)),
              (1100, hook("PostToolUse", tool_use_id="toolu_01", **helper)), end(7200)])
    fx = _fx(monkeypatch, [seq, [end(1)]])
    _frun(fx, G)
    assert [r["by"] for r in seen] == [["a helper"], ["build nw6"], ["build nw6"]]
    assert seen[0]["since"] == seen[1]["since"] == seen[2]["since"]   # one hold
    ((t, _),) = fx.procs[0].signals
    assert 1160 <= t - T0 <= 1162                                     # R4: as at the pin


# ---- Z5: the silent case, byte for byte with the outputs captured at main (c218b5b7) --------

SILENT = os.path.join(os.path.dirname(__file__), "fixtures", "nw6", "silent-at-main.json")
NOW = MARKED + 30 * 60
CASES = ["none", "stale", "other-session", "no-chain", "no-marker", "pid-reused", "other-start"]


def _silent(case, env, monkeypatch, record):
    """The prompt's line, `status` and `status --json` in `case`, with no live helpers' hold;
    with `record` False the state holds no held.json, as main's launcher never wrote one for
    the helpers. What varies by run and not by code is named: the temp roots `<home>`,
    `<state>` and `<cwd>`, this checkout `<repo>`, the meter's wall-clock `ts` and the
    transcript's inode."""
    monkeypatch.setattr(time, "time", lambda: NOW)
    if case != "no-chain":
        monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(env)
    if case not in ("none", "no-marker"):
        _marked(MARKED)
    if record and case != "none":
        _record(MARKED, MARKED + 70,
                pid={"stale": _dead_pid(), "pid-reused": 1}.get(case),
                session="another-sess-0000" if case == "other-session" else SID,
                started={"other-start": chain.proc_started(os.getpid()) + 1,      # pid 1 under
                         "pid-reused": chain.proc_started(os.getpid())}.get(case))  # ours
        if case == "no-marker":
            sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
            (sdir / hooks.MARKER).unlink()
            (sdir / hooks.CONFIRMED).unlink()
    out = {"prompt": _prompt(), "status": _run("status")[1], "json": _run("status", "--json")[1]}
    names = sorted(((os.environ["XDG_STATE_HOME"], "<state>"), (os.environ["HOME"], "<home>"),
                    (str(env), "<cwd>"), (os.path.dirname(os.path.dirname(METER)), "<repo>")),
                   key=lambda p: -len(p[0]))
    for k, v in out.items():
        for path, name in names:
            v = v.replace(path, name)
        v = re.sub(r'"ts": "[^"]*"', '"ts": "<ts>"', v)
        out[k] = re.sub(r'"inode": \d+', '"inode": 0', v)
    return out


@pytest.mark.parametrize("case", CASES)
def test_z5_the_silent_case_is_mains_output_byte_for_byte(case, cli_env, monkeypatch):
    """At main the fixture was captured by this test with NW6_CAPTURE naming it."""
    if os.environ.get("NW6_CAPTURE"):
        got = _silent(case, cli_env, monkeypatch, record=False)
        path = os.environ["NW6_CAPTURE"]
        doc = json.load(open(path)) if os.path.exists(path) else {}
        doc[case] = got
        with open(path, "w") as f:
            json.dump(doc, f, indent=1, sort_keys=True)
        return
    with open(SILENT) as f:
        want = json.load(f)[case]
    assert _silent(case, cli_env, monkeypatch, record=True) == want
