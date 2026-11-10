"""Packet u1: a stale helper call never holds the launcher (2026-11-10, fd362ce3).

A helper's Bash call was rejected at 21:03:14; a rejected call fires no Post and the
helper ended, so `calls/<id>` stood, and `Chain._ready` held a marked sitting from
23:19 until the owner ended it at 02:42. R1: a call file open `STALE_CALL` (1200 s) with
no helper stamp for as long is stale; the launcher goes on and says so once the terminal
is back, and the restart line names it in `stale_calls`.
"""
import json
import os
import signal
import time
from pathlib import Path

import pytest

from claude_session import config, hooks, ledger, resolver

ROOT = Path(__file__).resolve().parents[1]
G = {"cap": 12, "floor": 0, "settle": 60}
SID = "fd362ce3-2cdb-444c-8e6f-8ad87b5eb363"
CALL = "toolu_01Rf34Z4sSkYoyL1ZKdWyFdC"
OPENED, HELPER = 1794286994.915699, 1794293525.69249        # 21:03:14, 22:52:05
MARKED, ACTED, ENDED = 1794295136.451662, 1794295137.862713, 1794295145.074485
RESPAWN_TEXT = "# Sitting\n\n## Next act\nRESPAWN: carry on from the charter\n"
TERM = signal.SIGTERM


def C():
    from claude_session import chain
    return chain


def _chain(fx=None, **kw):
    ch = C()
    return ch.Chain("c1", ["--model", "m"], config.STATE_DIR, fx or ch.Effects(), dict(G),
                    **{"poll": 2, "grace": 10, "kill_grace": 30, **kw})


def _folder(sid=SID, calls=(), helper=HELPER, marked=MARKED, acted=ACTED, ended=ENDED):
    """A marked session whose turn ended; `calls` are (id, body or bytes) pairs."""
    sdir = resolver.session_dir(config.STATE_DIR, sid)
    (sdir / hooks.CALLS).mkdir(parents=True, exist_ok=True)
    for name, body in ((hooks.MARKER, {"written": marked}), (hooks.ACTIVITY, {"at": acted}),
                       (hooks.TURN_ENDED, {"at": ended}), (hooks.HELPER_ACTIVITY, helper)):
        if body is not None:
            (sdir / name).write_text(json.dumps(body if isinstance(body, dict) else {"at": body}))
    for cid, body in calls:
        (sdir / hooks.CALLS / cid).write_bytes(
            body if isinstance(body, bytes) else json.dumps(body).encode())
    return sdir


# ---- T1, T2: the night's folder ------------------------------------------------------

def test_u1_t1_the_nights_call_is_stale():
    c = _chain()
    sdir = _folder(calls=[(CALL, {"at": OPENED})])
    now = ENDED + 61
    assert c._ready(sdir, now) is True
    assert c._stale == [{"id": CALL, "age": int(now - OPENED)}]


def test_u1_t2_the_same_folder_without_the_call_is_ready():
    assert _chain()._ready(_folder(), ENDED + 61) is True


# ---- T3 to T7: the bound and its edges -----------------------------------------------

def test_u1_t3_the_bound_is_twenty_minutes():
    assert C().STALE_CALL == 1200 and _chain().stale_call == 1200
    a = ENDED - 1000                                    # the turn ends 1000 s after it opens
    sdir = _folder(calls=[("toolu_01a", {"at": a})], helper=a)
    c = _chain()
    assert c._ready(sdir, a + 1199) is False
    assert c._ready(sdir, a + 1200) is True


def test_u1_t4_a_later_helper_stamp_holds_for_the_bound():
    a = ENDED - 600
    sdir = _folder(calls=[("toolu_01a", {"at": a - 7200})], helper=a)
    c = _chain()
    assert c._ready(sdir, a + 1199) is False
    assert c._ready(sdir, a + 1200) is True
    assert c._stale == [{"id": "toolu_01a", "age": 8400}]


@pytest.mark.parametrize("ago, ready", [(7200, True), (30, False)])
def test_u1_t5_an_unreadable_call_reads_its_mtime(ago, ready):
    now = time.time()
    sdir = _folder(calls=[("toolu_01torn", b'{"at": 17')], helper=None,
                   marked=now - 200, acted=now - 190, ended=now - 180)
    p = sdir / hooks.CALLS / "toolu_01torn"
    os.utime(p, (now - ago, now - ago))
    assert _chain()._ready(sdir, now) is ready


def test_u1_t6_a_malformed_helper_stamp_still_holds():
    sdir = _folder(calls=[(CALL, {"at": OPENED})], helper={"at": "x"})
    assert _chain()._ready(sdir, ENDED + 86400) is False


def test_u1_t7_a_live_call_and_its_stamps_hold_beside_a_stale_one():
    a = ENDED + 100                                     # another helper's call opens
    sdir = _folder(calls=[(CALL, {"at": OPENED}), ("toolu_02live", {"at": a})], helper=a)
    c = _chain()
    assert c._ready(sdir, a + 60) is False
    (sdir / hooks.CALLS / "toolu_02live").unlink()      # its Post at a + 60: stamp, close
    (sdir / hooks.HELPER_ACTIVITY).write_text(json.dumps({"at": a + 60}))
    assert c._ready(sdir, a + 60 + 1199) is False
    assert c._ready(sdir, a + 60 + 1200) is True
    assert [s["id"] for s in c._stale] == [CALL]


# ---- T8, T9: the launcher, on the fake clock -----------------------------------------

def _fx(monkeypatch, plans):
    """Effects whose clock moves only when the chain waits or sleeps (test_chain's `_fx`,
    cut down); start n plays plans[n], each action at its own time."""
    ch, t0 = C(), float(int(time.time()))

    class Proc:
        def __init__(self, argv, start, plan):
            self.sid = argv[argv.index("--session-id") + 1]
            self.start, self.plan = start, sorted(plan, key=lambda a: a[0])
            self.returncode, self.signals = None, []

    class Fx(ch.Effects):
        def __init__(self):
            self.t, self.t0, self.procs, self.said = t0, t0, [], []

        def now(self):
            return self.t

        def sleep(self, s):
            self._advance(s)

        def spawn(self, argv, env):
            p = Proc(list(argv), self.t, plans[min(len(self.procs), len(plans) - 1)])
            self.procs.append(p)
            return p

        def wait(self, proc, timeout):
            self._advance(timeout, proc)
            return proc.returncode

        def _advance(self, s, proc=None):
            end = self.t + s
            assert end < self.t0 + 86400, "a day of fake clock: the chain never stopped"
            while proc is not None and proc.returncode is None and proc.plan \
                    and proc.start + proc.plan[0][0] <= end:
                dt, act = proc.plan.pop(0)
                self.t = max(self.t, proc.start + dt)
                act(self, proc)
            self.t = end

        def send(self, proc, sig):
            proc.signals.append((self.t, sig))
            proc.returncode = -sig

        def say(self, line):
            self.said.append(line)

        def tty_save(self):
            return None

        def tty_restore(self, attrs):
            self.said.append("<tty restored>")

    fx = Fx()
    monkeypatch.setattr(time, "time", fx.now)
    return fx


def _hook(fn, **extra):
    return lambda fx, p: fn({"session_id": p.sid, **extra})


def _close(charter, at=10):
    """The sitting's RESPAWN close, a second apart, as test_chain's `respawn_seq`."""
    from claude_session import cli
    bash = {"tool_name": "Bash",
            "tool_input": {"command": f"agentik-session checkpoint --respawn --charter {charter}"}}

    def write(fx, p):
        charter.write_text(RESPAWN_TEXT)
        os.utime(charter, (fx.t, fx.t))

    def verb(fx, p):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        with pytest.MonkeyPatch.context() as m, redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()):
            m.setenv("CLAUDE_CODE_SESSION_ID", p.sid)
            try:
                rc = cli.main(["checkpoint", "--respawn", "--charter", str(charter)])
            except SystemExit as e:
                rc = e.code
        assert rc in (0, None)
    return [(at, write), (at + 1, _hook(hooks.pre_tool_use, **bash)), (at + 2, verb),
            (at + 3, _hook(hooks.post_tool_use, **bash)), (at + 4, _hook(hooks.stop))]


def _end(at):
    return (at, lambda fx, p: setattr(p, "returncode", 0))


def _restart_of(fx, monkeypatch, tmp_path, extra):
    monkeypatch.chdir(tmp_path)
    helper = {"agent_id": "a1", "tool_name": "Bash"}
    seq = [(s[0], _hook(getattr(hooks, s[1]), tool_use_id=s[2], **helper)) for s in extra]
    plans = [_close(tmp_path / "charter.md") + seq + [_end(7200)], [_end(1)]]
    fx = fx(monkeypatch, plans)
    assert _chain(fx).run() == 0
    rows = [json.loads(l) for l in ledger.path(config.STATE_DIR).read_text().splitlines()]
    return fx, [r for r in rows if r.get("kind") == "restart"]


def test_u1_t8_the_launcher_goes_on_past_a_rejected_call(monkeypatch, tmp_path):
    fx, (r,) = _restart_of(_fx, monkeypatch, tmp_path, [(12, "pre_tool_use", "toolu_01rej")])
    (t, sig), = fx.procs[0].signals
    assert sig == TERM and 1212 <= t - fx.t0 <= 1216          # open 12 s in, + 1200 s
    assert r["ended_by"] == "launcher"
    (s,) = r["stale_calls"]
    assert s["id"] == "toolu_01rej" and 1200 <= s["age"] <= 1204
    lines = [l for l in fx.said if "stale" in l]
    assert lines == ["c1: went on past a stale helper call: toolu_01rej open 20 min"]
    first_tty = fx.said.index("<tty restored>")
    assert first_tty < fx.said.index(lines[0]) < next(
        i for i, l in enumerate(fx.said) if "ended on RESPAWN" in l)


def test_u1_t9_a_call_closed_under_the_bound_names_no_stale_call(monkeypatch, tmp_path):
    fx, (r,) = _restart_of(_fx, monkeypatch, tmp_path,
                           [(12, "pre_tool_use", "toolu_01ok"), (1100, "post_tool_use", "toolu_01ok")])
    (t, sig), = fx.procs[0].signals
    assert sig == TERM and 1160 <= t - fx.t0 <= 1162
    assert "stale_calls" in r and r["stale_calls"] is None
    assert not [l for l in fx.said if "stale" in l]


# ---- T10, T11: the ledger's key and the runbook --------------------------------------

def test_u1_t10_the_restart_line_gains_stale_calls_alone():
    assert ledger.RESTART_KEYS[-1] == "stale_calls" and len(ledger.RESTART_KEYS) == 17
    assert "stale_calls" not in ledger.STOP_KEYS and len(ledger.STOP_KEYS) == 10


def test_u1_t11_the_runbook_says_the_bound():
    text = " ".join((ROOT / "RUNBOOK.md").read_text().split())
    assert "open 20 minutes with no helper activity" in text and "`stale_calls`" in text
