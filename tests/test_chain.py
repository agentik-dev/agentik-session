"""S20a: `claude-session run`, the launcher (respawn-r1 §3.1 to §3.9 and §6; packet S20).

Two harnesses. The fake `claude` (tests/fixtures/fake-claude) is a real child the chain
starts, for the argv, the environment, the restart and the printed start line. The fake
effects (`_fx`) put the child and the clock in-process, the clock anchored to the epoch,
so an hour of waiting costs nothing; its child drives the real hooks and the real verb.
"""
import fcntl
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from claude_session import config, hooks, ledger, resolver

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "fixtures" / "fake-claude"
ARGS = ["--model", "opus[1m]", "--effort", "high", "/loop check in, then RESPAWN at 80%"]
RESPAWN_TEXT = "# Sitting\n\n## Next act\nRESPAWN: carry on from the charter\n"
DONE_TEXT = "# Sitting\n\n## Next act\nDone.\n"
SCRUBBED = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_PID",
            "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_SESSION_MAX_TURNS")
FAST = {"cap": 12, "floor": 0, "settle": 0}
G = {"cap": 12, "floor": 0, "settle": 60}
T0 = float(int(time.time()))
TERM, KILL = signal.SIGTERM, signal.SIGKILL


def C():
    from claude_session import chain
    return chain


def _state() -> Path:
    return config.STATE_DIR


def _cli(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _lines(kind=None):
    """The ledger's whole lines (a torn line is skipped), of `kind` when given."""
    p = ledger.path(_state())
    rows = []
    for raw in (p.read_text().splitlines() if p.exists() else []):
        try:
            rows.append(json.loads(raw))
        except ValueError:
            continue
    return [r for r in rows if kind is None or r.get("kind") == kind]


def _stops():
    return [r["reason"] for r in _lines("stop")]


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


class _Fake:
    pass


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """The fake `claude` on PATH, its plan and its log; this tree's package on
    PYTHONPATH; the cwd a temp dir outside any git repository."""
    f = _Fake()
    f.bin = tmp_path / "bin"
    f.bin.mkdir()
    w = f.bin / "claude"
    w.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -B "
                 f"{shlex.quote(str(FAKE))} \"$@\"\n")
    w.chmod(0o755)
    f.work = tmp_path / "work"
    f.work.mkdir()
    monkeypatch.chdir(f.work)
    monkeypatch.setenv("PATH", f"{f.bin}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    f.plan, f.log = tmp_path / "plan.json", tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_CLAUDE_PLAN", str(f.plan))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(f.log))
    f.charter = f.work / "charter.md"
    f.set = lambda *starts: f.plan.write_text(json.dumps(list(starts)))
    f.starts = lambda: ([json.loads(l) for l in f.log.read_text().splitlines()]
                        if f.log.exists() else [])
    f.sigs = lambda: ([json.loads(l) for l in Path(str(f.log) + ".signals").read_text()
                       .splitlines()] if Path(str(f.log) + ".signals").exists() else [])
    f.set([["exit", 0]])
    return f


def _sitting(f, then=("idle", 30)):
    return [["write", str(f.charter), RESPAWN_TEXT], ["respawn", str(f.charter)], list(then)]


def _run(f, args=ARGS, guards=FAST, name="c1", **kw):
    ch = C()
    kw = {"poll": 0.05, "grace": 0.05, "kill_grace": 0.5, **kw}
    return ch.Chain(name, list(args), _state(), ch.Effects(), dict(guards), **kw).run()


# ---- the fake effects: the child and the clock in-process ----------------------------

def _fx(monkeypatch, plans):
    """Effects whose clock starts at T0 and moves only when the chain waits or sleeps;
    start n plays plans[n] (the last plan serves later starts), each action at its own
    time. `time.time` follows the clock, so the hooks' stamps and the verb's marker do."""
    ch = C()

    class Proc:
        def __init__(self, argv, start, plan):
            self.argv, self.start = argv, start
            self.sid = argv[argv.index("--session-id") + 1]
            self.plan = sorted(plan, key=lambda a: a[0])
            self.returncode, self.signals, self.ignore_term = None, [], False

    class Fx(ch.Effects):
        def __init__(self):
            self.t, self.procs, self.said, self.fail_restart = T0, [], [], False

        def now(self):
            return self.t

        def sleep(self, s):
            self._advance(s)

        def uuid(self):
            return str(uuid.uuid4())

        def spawn(self, argv, env):
            p = Proc(list(argv), self.t, plans[min(len(self.procs), len(plans) - 1)])
            p.env = dict(env)
            self.procs.append(p)
            return p

        def wait(self, proc, timeout):
            self._advance(timeout, proc)
            return proc.returncode

        def _advance(self, s, proc=None):
            end = self.t + s
            assert end < T0 + 30 * 86400, "a month of fake clock: the chain never stopped"
            while proc is not None and proc.returncode is None and proc.plan \
                    and proc.start + proc.plan[0][0] <= end:
                dt, act = proc.plan.pop(0)
                self.t = max(self.t, proc.start + dt)
                act(self, proc)
            self.t = end

        def send(self, proc, sig):
            proc.signals.append((self.t, sig))
            if sig == KILL or (sig == TERM and not proc.ignore_term):
                proc.returncode = -sig

        def say(self, line):
            self.said.append(line)

        def tty_save(self):
            return None

        def tty_restore(self, attrs):
            pass

        def append(self, state, entry):
            if self.fail_restart and entry.get("kind") == "restart":
                raise OSError("disk full")
            return super().append(state, entry)

    fx = Fx()
    monkeypatch.setattr(time, "time", fx.now)
    return fx


def _frun(fx, guards, name="c1", **kw):
    ch = C()
    kw = {"poll": 2, "grace": 10, "kill_grace": 30, **kw}
    return ch.Chain(name, ["--model", "m"], _state(), fx, dict(guards), **kw).run()


def hook(event, **extra):
    fn = {"PreToolUse": hooks.pre_tool_use, "PostToolUse": hooks.post_tool_use,
          "Stop": hooks.stop, "UserPromptSubmit": hooks.user_prompt_submit}[event]

    def act(fx, p):
        try:
            fn({"session_id": p.sid, **extra})
        except Exception:                       # noqa: BLE001  (a stamp lands first)
            pass
    return act


def verb(path):
    def act(fx, p):
        with pytest.MonkeyPatch.context() as m:
            m.setenv("CLAUDE_CODE_SESSION_ID", p.sid)
            assert _cli("checkpoint", "--respawn", "--charter", str(path))[0] == 0
    return act


def write(path, text):
    def act(fx, p):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text)
        os.utime(path, (fx.t, fx.t))
    return act


def end(at, status=0):
    return (at, lambda fx, p: setattr(p, "returncode", status))


def respawn_seq(path, at=10, text=RESPAWN_TEXT, helper=False, write_charter=True):
    """A sitting's close, a second apart: its charter, PreToolUse, the verb, PostToolUse
    (a helper's when `helper`), Stop at at+4."""
    bash = {"tool_name": "Bash",
            "tool_input": {"command": f"claude-session checkpoint --respawn --charter {path}"}}
    seq = [(at, write(path, text))] if write_charter else []
    return seq + [(at + 1, hook("PreToolUse", **bash)), (at + 2, verb(path)),
                  (at + 3, hook("PostToolUse", **bash, **({"agent_id": "a1"} if helper else {}))),
                  (at + 4, hook("Stop"))]


# ---- §3.1: refusals before the first start (criterion 1) -----------------------------

REFUSALS = {
    "not-a-tty": ("c1", [], {}, "TTY"),
    "inside-a-chain": ("c1", [], {"CLAUDE_SESSION_CHAIN": "other"}, "CLAUDE_SESSION_CHAIN"),
    "inside-claude-code": ("c1", [], {"CLAUDECODE": "1"}, "CLAUDECODE"),
    "depth-1": ("c1", [], {"CLAUDE_SESSION_DEPTH": "1"}, "CLAUDE_SESSION_DEPTH"),
    "depth-unparsable": ("c1", [], {"CLAUDE_SESSION_DEPTH": "x"}, "CLAUDE_SESSION_DEPTH"),
    "unknown-flag": ("c1", ["--dangerously-skip-permissions"], {}, "--dangerously-skip-permissions"),
    "unknown-flag-value": ("c1", ["--foo=bar"], {}, "--foo"),
    "bare-dash-value": ("c1", ["--append-system-prompt", "- x"], {}, "--append-system-prompt=- x"),
    "no-claude": ("c1", [], {"PATH": "/nonexistent"}, "PATH"),
    "lock-held": ("c1", [], {}, "lock"),
    "bad-chain-name": ("a/b", [], {}, "chain name"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_s20a_refusals(case, fake, monkeypatch):
    name, extra, env, needle = REFUSALS[case]
    ch = C()
    monkeypatch.setattr(ch, "on_tty", lambda: case != "not-a-tty")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    held = None
    if case == "lock-held":
        lock = _state() / "respawn" / "c1" / "lock"
        lock.parent.mkdir(parents=True)
        held = open(lock, "a")
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        rc, _, err = _cli("run", "--chain", name, "--", "--model", "m", *extra)
    finally:
        if held:
            held.close()
    assert rc == 2, err
    assert needle in err and len(err.strip().splitlines()) == 1, err
    assert fake.starts() == []


def test_s20a_forbidden_never_allowed(fake):
    ch = C()
    family = {"-p", "--print", "-c", "--continue", "-r", "--resume", "--fork-session",
              "--session-id", "--from-pr", "--teleport", "--bg", "--background", "--tmux", "-w"}
    assert set(ch.FORBIDDEN) >= family
    assert not set(ch.FORBIDDEN) & set(ch.ALLOWED)
    env = {"PATH": str(fake.bin)}
    assert ch.refusal(list(ARGS), env) is None                       # the positive control
    assert ch.refusal(["--append-system-prompt=- x"], env) is None   # ruling 5's form passes
    for flag in ch.FORBIDDEN:
        for form in ([flag], [flag + "=x"], ["--model", "m", flag, "v"]):
            r = ch.refusal(form, env)
            assert r and flag in r, (flag, form)


# ---- §3.1, §3.8: the starts (criteria 2, 5, 6, 7, 15) ---------------------------------

def test_s20a_same_args_every_start(fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "0")
    monkeypatch.setenv("RELAY_ROW", "row-1")
    for k in SCRUBBED:
        monkeypatch.setenv(k, "x")
    fake.set(_sitting(fake), _sitting(fake), [["exit", 0]])
    assert _run(fake) == 0
    starts = fake.starts()
    assert len(starts) == 3
    for s in starts:
        assert s["argv"][0] == "--session-id" and s["argv"][2:] == ARGS
        assert uuid.UUID(s["argv"][1]).version == 4
        env = s["env"]
        assert env["CLAUDE_SESSION_CHAIN"] == "c1" and env["CLAUDE_SESSION_PROFILE"] == "builder"
        assert not set(SCRUBBED + ("CLAUDE_SESSION_DEPTH", "RELAY_ROW")) & set(env)
    assert len({s["argv"][1] for s in starts}) == 3


def test_s20a_never_compacts_or_resumes(fake):
    fake.set(_sitting(fake), _sitting(fake), _sitting(fake), [["exit", 0]])
    assert _run(fake) == 0
    starts = fake.starts()
    assert len(starts) == 4 and len(_lines("restart")) == 3
    allowed = C().ALLOWED
    for s in starts:
        assert s["argv"][:1] == ["--session-id"]
        assert all(a.split("=", 1)[0] in allowed for a in s["argv"][2:] if a.startswith("-"))
        assert not any("/compact" in a for a in s["argv"])


def test_s20a_restart(fake):
    fake.set(_sitting(fake), [["exit", 0]])
    assert _run(fake) == 0
    s = fake.starts()
    assert len(s) == 2
    (r,) = _lines("restart")
    assert (r["seq"], r["from_session"], r["to_session"], r["ended_by"]) == (
        1, s[0]["argv"][1], s[1]["argv"][1], "launcher")
    assert s[1]["ledger_lines"] == 1                     # written before the successor
    assert fake.sigs() == [{"n": 0, "sig": TERM}]
    assert _stops() == ["no-marker"]


@pytest.mark.parametrize("status", [0, 3])
def test_s20a_no_marker_stops(status, fake):
    fake.set([["exit", status]])
    assert _run(fake) == status
    assert len(fake.starts()) == 1 and _lines("restart") == []
    (stop,) = _lines("stop")
    assert (stop["reason"], stop["exit_status"]) == ("no-marker", status)


def test_s20a_crash_never_restarts(fake):
    fake.set(_sitting(fake, then=("exit", 7)))
    assert _run(fake, guards={"cap": 12, "floor": 0, "settle": 1}) == 7
    assert len(fake.starts()) == 1 and fake.sigs() == [] and _lines("restart") == []
    assert _stops() == ["crash"]


# ---- §3.4: the marker bound to the sitting (criterion 8) ------------------------------

@pytest.mark.parametrize("case", ["not-main", "stale-charter", "rewritten"])
def test_s20a_marker_bound_to_sitting(case, fake, monkeypatch):
    path = fake.charter
    if case == "stale-charter":
        path.write_text(RESPAWN_TEXT)
        os.utime(path, (T0 - 100, T0 - 100))
        seq = respawn_seq(path, write_charter=False)
    elif case == "not-main":
        seq = respawn_seq(path, helper=True)
    else:
        seq = respawn_seq(path) + [(20, write(path, DONE_TEXT))]
    fx = _fx(monkeypatch, [seq + [end(3600)]])
    assert _frun(fx, G) == 0
    assert [p.signals for p in fx.procs] == [[]]
    assert _stops() == [{"not-main": "not-main"}.get(case, "not-respawn")]


# ---- §3.3, ruling 2: the ready condition (criterion 9) --------------------------------

WAITS = ["long-tool", "prompt-after-stop", "tool-after-stop", "helper-open-call",
         "helper-activity"]


@pytest.mark.parametrize("case", WAITS)
def test_s20a_waits_for_the_turn(case, fake, monkeypatch):
    seq = respawn_seq(fake.charter)
    helper = {"agent_id": "a1", "tool_name": "Bash"}
    earliest = None
    if case == "long-tool":
        seq += [(20, hook("PreToolUse", tool_name="AskUserQuestion"))]
    elif case in ("prompt-after-stop", "tool-after-stop"):
        again = (hook("UserPromptSubmit") if case == "prompt-after-stop"
                 else hook("PreToolUse", tool_name="Read"))
        seq += [(40, again), (200, hook("Stop"))]
        earliest = 260
    elif case == "helper-open-call":
        seq += [(12, hook("PreToolUse", tool_use_id="toolu_01", **helper)),
                (3000, hook("PostToolUse", tool_use_id="toolu_01", **helper))]
        earliest = 3060
    else:
        ticks = list(range(15, 3001, 30))
        seq += [(t, hook("PreToolUse", **helper)) for t in ticks]
        earliest = ticks[-1] + 60
    fx = _fx(monkeypatch, [seq + [end(7200)], [end(1)]])
    _frun(fx, G)
    first = fx.procs[0].signals
    if earliest is None:
        assert first == []                  # the owner's /exit at 7200 then restarts it
    else:
        assert first and first[0][1] == TERM
        assert earliest <= first[0][0] - T0 <= earliest + 2, first


def test_s20a_signals_after_settle(fake, monkeypatch):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)], [end(1)]])
    assert _frun(fx, G) == 0
    ((t, sig),) = fx.procs[0].signals
    assert sig == TERM and 14 + 60 <= t - T0 <= 14 + 60 + 2
    assert len(fx.procs) == 2 and fx.procs[1].start - t >= 10


# ---- §3.5: the guards (criteria 10, 11, 12) -------------------------------------------

def touch(path, at=None):
    def act(fx, p):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        t = fx.t if at is None else at
        os.utime(path, (t, t))
    return act


@pytest.mark.parametrize("case", ["chain-stop", "global-stop", "cap", "floor",
                                  "stop-in-settle", "stale-stop"])
def test_s20a_guards_hold(case, fake, monkeypatch):
    one, every = _state() / "respawn" / "c1" / "STOP", _state() / "respawn" / "STOP"
    g, seq, made = dict(G), respawn_seq(fake.charter), []
    if case in ("chain-stop", "global-stop"):
        made = [one if case == "chain-stop" else every]
        seq.insert(0, (5, touch(made[0])))
    elif case == "cap":
        g["cap"] = 1
        ledger.path(_state()).parent.mkdir(parents=True, exist_ok=True)
        ledger.path(_state()).write_text(
            json.dumps({"kind": "restart", "chain": "c1", "at": _iso(T0 - 60)}) + "\n")
    elif case == "floor":
        g["floor"] = 600
    elif case == "stop-in-settle":
        made = [one]
        seq.append((40, touch(one)))
    else:
        made = [one]
        touch(one, at=T0 - 100)(None, None)
    fx = _fx(monkeypatch, [seq + [end(3600)], [end(1)]])
    _frun(fx, g)
    if case == "stale-stop":
        assert [s for _, s in fx.procs[0].signals] == [TERM] and len(fx.procs) == 2
        assert _stops() == ["no-marker"]
    else:
        assert [p.signals for p in fx.procs] == [[]]
        assert _stops() == [{"cap": "cap", "floor": "floor"}.get(case, "stop-file")]
    assert all(p.exists() for p in made)


@pytest.mark.parametrize("case", ["window", "cap-0", "unreadable", "torn-line", "deleted",
                                  "write-fails"])
def test_s20a_cap_fails_closed(case, fake, monkeypatch):
    g, seq = dict(G), respawn_seq(fake.charter)
    lp = ledger.path(_state())
    lp.parent.mkdir(parents=True, exist_ok=True)

    def line(chain, t):
        return json.dumps({"kind": "restart", "chain": chain, "at": _iso(t)})
    if case == "window":
        g["cap"] = 3
        lp.write_text("\n".join([line("c1", T0 - 3600), line("c1", T0 - 7200),
                                 line("c1", T0 - 25 * 3600), line("other", T0 - 60),
                                 line("other", T0 - 120)]) + "\n")
        expect = 2
    elif case == "cap-0":
        g["cap"] = 0
        expect = 1
    elif case == "unreadable":
        lp.write_text(line("other", T0 - 60) + "\n")
        lp.chmod(0o200)
        expect = 1
    elif case == "torn-line":
        g["cap"] = 2                              # the torn line counts, and never swallows
        lp.write_text('{"kind": "restart", "chain": "c1", "at')       # no newline (A-F1)
        expect = 2
    elif case == "deleted":
        g["cap"] = 2
        seq.insert(0, (5, lambda fx, p: lp.unlink(missing_ok=True)))
        expect = 3
    else:
        expect = 1
    fx = _fx(monkeypatch, [seq + [end(3600)]])
    fx.fail_restart = case == "write-fails"
    _frun(fx, g)
    assert len(fx.procs) == expect
    assert _stops()[-1] == "cap"
    if case == "write-fails":
        assert [s for _, s in fx.procs[0].signals] == [TERM]
        assert any("disk full" in s for s in fx.said)


def test_s20a_kill_after_grace(fake, monkeypatch):
    seq = [(1, lambda fx, p: setattr(p, "ignore_term", True))] + respawn_seq(fake.charter)
    fx = _fx(monkeypatch, [seq + [end(7200)], [end(1)]])
    assert _frun(fx, G) == 0
    sigs = fx.procs[0].signals
    assert [s for _, s in sigs] == [TERM, KILL] and 30 <= sigs[1][0] - sigs[0][0] <= 32
    assert _lines("restart")[0]["ended_by"] == "kill" and len(fx.procs) == 2


# ---- §3.6: the ledger (criterion 13's token) ------------------------------------------

def test_s20a_ledger_holds_no_next_act(fake, monkeypatch):
    token = "tok-" + uuid.uuid4().hex
    text = f"# Sitting\n\n## Next act\nRESPAWN: {token}\n"
    fx = _fx(monkeypatch, [respawn_seq(fake.charter, text=text) + [end(7200)], [end(1)]])
    _frun(fx, G)
    (r,) = _lines("restart")
    assert r["charter"] == str(fake.charter)
    assert r["charter_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert _stops() == ["no-marker"]
    assert token not in ledger.path(_state()).read_text()


# ---- §3.4: the printed start line (criterion 16) --------------------------------------

def test_s20a_start_line_runs(fake, monkeypatch):
    shim = fake.bin / "claude-session"
    shim.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -B -m claude_session \"$@\"\n")
    shim.chmod(0o755)
    monkeypatch.setattr(C(), "on_tty", lambda: True)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    rc, _, err = _cli("run", "--chain", "c1", "--", *ARGS)
    assert rc == 0, err
    line = err.strip().splitlines()[-1]
    assert line.startswith("CLAUDE_SESSION_PROFILE=builder claude-session run "), line
    monkeypatch.delenv("CLAUDE_SESSION_PROFILE")
    master, slave = os.openpty()
    try:
        p = subprocess.Popen(["/bin/sh", "-c", line], stdin=slave, stdout=slave,
                             stderr=subprocess.PIPE, cwd=fake.work, env=dict(os.environ))
        os.close(slave)
        _, perr = p.communicate(timeout=120)
    finally:
        os.close(master)
    assert p.returncode == 0, perr
    s = fake.starts()
    assert len(s) == 2 and s[1]["argv"][2:] == s[0]["argv"][2:] == ARGS
    assert s[1]["env"]["CLAUDE_SESSION_PROFILE"] == "builder"


# ---- §4, rulings 6 and 8: configuration and the long /loop ----------------------------

@pytest.mark.parametrize("case", ["defaults", "layers", "bad-flag"])
def test_s20a_flags_override_config(case, fake, monkeypatch):
    ch = C()
    if case == "defaults":
        assert ch.guards(fake.work, dict(os.environ), {}) == {"cap": 12, "floor": 600,
                                                                "settle": 60}
    elif case == "layers":
        d = fake.work / resolver.REPO_DIR
        d.mkdir(parents=True)
        (d / "config.yaml").write_text("session:\n  respawn: {cap: 5, settle: 30}\n")
        (d / "config.local.yaml").write_text("session:\n  respawn: {settle: 20}\n")
        assert ch.guards(fake.work, dict(os.environ), {}) == {"cap": 5, "floor": 600,
                                                                "settle": 20}
        assert ch.guards(fake.work, dict(os.environ), {"cap": 2, "floor": 0}) == {
            "cap": 2, "floor": 0, "settle": 20}
    else:
        monkeypatch.setattr(ch, "on_tty", lambda: True)
        for flag, val in (("--cap", "-1"), ("--floor", "x"), ("--settle", "1.5")):
            rc, _, err = _cli("run", flag, val, "--", "--model", "m")
            assert rc == 2 and f"respawn.{flag[2:]}" in err, err
        assert fake.starts() == []


def test_s20a_long_loop_warns(fake, monkeypatch):
    monkeypatch.setattr(C(), "on_tty", lambda: True)
    rc, _, err = _cli("run", "--chain", "c1", "--", "--model", "m", "/loop 3h check in")
    assert rc == 0 and len(fake.starts()) == 1
    warned = [l for l in err.splitlines() if l.startswith("warning:")]
    assert len(warned) == 1 and "60" in warned[0]
    rc, _, err = _cli("run", "--chain", "c1", "--", "--model", "m", "/loop 45m check in")
    assert rc == 0 and len(fake.starts()) == 2
    assert not [l for l in err.splitlines() if l.startswith("warning:")]


# ---- the fix round: the adversaries' blocks and notes ---------------------------------

def _chain(fx, guards, **kw):
    ch = C()
    kw = {"poll": 2, "grace": 10, "kill_grace": 30, **kw}
    return ch.Chain("c1", ["--model", "m"], _state(), fx, guards, **kw)


def test_s20a_torn_tail_never_swallows_a_line(fake):
    lp = ledger.path(_state())
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text('{"kind": "restart", "chain": "c1", "at')            # torn, no newline
    ledger.append_chain(_state(), {"kind": "restart", "chain": "c1"})
    assert ledger.restarts_in(_state(), "c1", time.time()) == 2


def test_s20a_config_edit_holds_before_the_signal(fake, monkeypatch):
    box = dict(G)
    seq = respawn_seq(fake.charter) + [(40, lambda fx, p: box.update(cap=0))]
    fx = _fx(monkeypatch, [seq + [end(3600)], [end(1)]])
    assert _chain(fx, lambda: dict(box)).run() == 0
    assert [p.signals for p in fx.procs] == [[]] and _stops() == ["cap"]


def test_s20a_ctrl_c_before_the_grace_line_ends_the_chain(fake, monkeypatch):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)], [end(1)]])
    c = _chain(fx, dict(G))
    fx.tty_restore = lambda attrs: c.got.append(signal.SIGINT)      # after the child's exit
    assert c.run() == 0
    assert len(fx.procs) == 1 and _stops() == ["interrupted"]


def test_s20a_kill_follows_a_hangup_in_the_kill_grace(fake, monkeypatch):
    box = {}
    seq = ([(1, lambda fx, p: setattr(p, "ignore_term", True))] + respawn_seq(fake.charter)
           + [(80, lambda fx, p: box["c"].got.append(signal.SIGHUP))])
    fx = _fx(monkeypatch, [seq + [end(7200)]])
    box["c"] = c = _chain(fx, dict(G))
    c.run()
    sigs = fx.procs[0].signals
    assert [s for _, s in sigs] == [TERM, KILL] and sigs[1][0] - sigs[0][0] <= 32
    assert _stops() == ["hangup"]


def test_s20a_long_loop_trailing_every():
    ch = C()
    assert ch.long_loop(["/loop check in every 2h"]) == 120
    assert ch.long_loop(["/loop check in every 2 hours"]) == 120
    assert ch.long_loop(["/loop check in every 30m"]) is None
    assert ch.long_loop(["/loop 3h check in"]) == 180


def test_s20a_spawn_failure_stops_with_a_line(fake, monkeypatch):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)]])
    real = fx.spawn

    def spawn(argv, env):
        if fx.procs:
            raise OSError("no such file: claude")
        return real(argv, env)
    fx.spawn = spawn
    assert _frun(fx, G) == 1
    assert len(_lines("restart")) == 1 and _stops() == ["spawn"]
    assert any("no such file" in s for s in fx.said)


def test_s20a_flag_digits_are_ascii(fake, monkeypatch):
    monkeypatch.setattr(C(), "on_tty", lambda: True)
    for val in ("\u00b2", "\u0661\u0662"):
        rc, _, err = _cli("run", "--cap", val, "--", "--model", "m")
        assert rc == 2 and "respawn.cap" in err, err
    assert fake.starts() == []


def test_s20a_ready_reads_calls_before_helper_stamp(fake, monkeypatch):
    ch = C()
    sdir = resolver.session_dir(_state(), "s20a-ready")
    (sdir / hooks.CALLS).mkdir(parents=True)
    now = time.time()
    for name, at in ((hooks.MARKER, "written"), (hooks.TURN_ENDED, "at"),
                     (hooks.ACTIVITY, "at"), (hooks.HELPER_ACTIVITY, "at")):
        ago = {hooks.MARKER: 100, hooks.TURN_ENDED: 90, hooks.ACTIVITY: 95}.get(name, 80)
        (sdir / name).write_text(json.dumps({at: now - ago}))
    c = _chain(ch.Effects(), dict(G))
    events, real_json, real_iter = [], ch._json, Path.iterdir
    monkeypatch.setattr(ch, "_json", lambda p: (events.append(p.name), real_json(p))[1])
    monkeypatch.setattr(Path, "iterdir",
                        lambda self: (events.append(self.name + "/"), real_iter(self))[1])
    assert c._ready(sdir, now) is True
    assert events.index(hooks.CALLS + "/") < events.index(hooks.HELPER_ACTIVITY)


def test_s20a_ids_and_names_match_whole(fake, monkeypatch):
    assert not hooks._SID.match("toolu_x\n") and not hooks.CHAIN_RE.match("c1\n")
    assert not hooks.CHAIN_RE.match("..") and not hooks.CHAIN_RE.match(".")
    assert hooks.CHAIN_RE.match("a.b") and hooks._SID.match("toolu_x")
    monkeypatch.setattr(C(), "on_tty", lambda: True)
    rc, _, err = _cli("run", "--chain", "..", "--", "--model", "m")
    assert rc == 2 and "chain name" in err and fake.starts() == []


def test_s20a_compact_is_a_token(fake):
    ch, env = C(), {"PATH": str(fake.bin)}
    assert ch.refusal(["--add-dir=/x/compactor"], env) is None
    assert ch.refusal(["--add-dir", "/x/compact"], env) is None
    assert ch.refusal(["/compact"], env) and ch.refusal(["--model", "m", "/compact now"], env)


# ---- the hardening round ---------------------------------------------------------------

def test_s20a_config_error_is_printed_at_the_stop(fake, monkeypatch):
    """N1: a config that stops resolving before the signal holds the sitting at `config`,
    and the resolver's error is printed when the chain stops."""
    ch = C()
    cfg = fake.work / resolver.REPO_DIR / "config.yaml"
    bad = "session:\n  respawn: {cap: 5\n"
    seq = respawn_seq(fake.charter) + [(40, write(cfg, bad))]
    fx = _fx(monkeypatch, [seq + [end(3600)], [end(1)]])
    floor0 = {"floor": 0}                      # the config's floor (600) would hold first
    assert _chain(fx, lambda: ch.guards(fake.work, dict(os.environ), floor0)).run() == 0
    with pytest.raises(resolver.ResolveError) as e:
        ch.guards(fake.work, dict(os.environ), floor0)
    assert [p.signals for p in fx.procs] == [[]] and _stops() == ["config"]
    assert any(str(e.value) in s for s in fx.said), fx.said


def test_s20a_resolver_sid_matches_whole():
    """N2: the resolver's session id refuses a trailing newline, as the hooks' does."""
    assert not resolver._SID.match("sess-1\n") and resolver._SID.match("sess-1")


# ---- S20b: the terminal (§3.7, criterion 14), under pty.fork ------------------------

# The launcher, a `Chain` built directly (ruling 10), as the session leader of a new pty.
# Each line it says is logged with the terminal's attributes at that moment.
PTY_LAUNCHER = r'''
import json, sys, termios
from claude_session import chain, config
spec = json.loads(sys.argv[1])


def note(line):
    # PENDIN is the driver's own mark (a BSD tty sets it when canonical mode comes back,
    # to retype pending input), never an attribute the launcher saves or sets.
    t = termios.tcgetattr(0)
    t[3] &= ~getattr(termios, "PENDIN", 0)
    with open(spec["said"], "a") as f:
        f.write(json.dumps({"line": line, "tty": repr(t)}) + "\n")


class FX(chain.Effects):
    def say(self, line):
        note(line)
        super().say(line)


note(None)
sys.exit(chain.Chain("c1", ["--model", "m"], config.STATE_DIR, FX(), spec["guards"],
                     poll=0.05, grace=spec["grace"], kill_grace=0.5).run())
'''


def _pty(f, tmp_path, *, grace=0.05, when=None, act=None, timeout=60):
    """Start the launcher on a pty; once `when(out)` holds, `act(pid)` once. Returns the
    launcher's wait status, every byte the terminal showed, the byte count at `act`, and
    the said log."""
    import pty
    import select
    said = tmp_path / "said.jsonl"
    spec = json.dumps({"guards": FAST, "grace": grace, "said": str(said)})
    pid, fd = pty.fork()
    if pid == 0:                                         # the child: never back into pytest
        try:
            os.execv(sys.executable, [sys.executable, "-B", "-c", PTY_LAUNCHER, spec])
        finally:
            os._exit(127)
    out, mark, status, deadline = b"", None, None, time.monotonic() + timeout
    try:
        while status is None:
            assert time.monotonic() < deadline, out
            if mark is None and when is not None and when(out):
                mark = len(out)
                act(pid)
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:                          # EIO: the slave side closed
                    chunk = b""
                out += chunk
                if chunk:
                    continue
            wpid, st = os.waitpid(pid, os.WNOHANG)
            if wpid:
                status = st
        while select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    finally:
        if status is None:
            os.kill(pid, KILL)
            os.waitpid(pid, 0)
        os.close(fd)
    said_rows = [json.loads(l) for l in said.read_text().splitlines()] if said.exists() else []
    return status, out, mark, said_rows


def _started(f):
    return lambda out: len(f.starts()) >= 1


TERMINAL = ["raw-restored", "sigint-default", "ctrl-c-child", "ctrl-c-grace", "hangup",
            "ctrl-c-taken-then-respawn"]


@pytest.mark.parametrize("case", TERMINAL)
def test_s20b_terminal(case, fake, tmp_path):
    if case == "raw-restored":
        # A fake that sets raw mode and exits finds the attributes restored before the
        # launcher's next line.
        fake.set([["raw"], ["exit", 0]])
        st, out, _, said = _pty(fake, tmp_path)
        assert os.WIFEXITED(st) and os.WEXITSTATUS(st) == 0, out
        raw = [json.loads(l) for l in Path(str(fake.log) + ".tty").read_text().splitlines()]
        saved = said[0]["tty"]
        assert said[0]["line"] is None and raw and raw[0] != saved     # raw mode took
        lines = said[1:]
        assert lines and all(r["tty"] == saved for r in lines), lines
        assert _stops() == ["no-marker"]
    elif case == "sigint-default":
        # The fake reports SIGINT (and SIGQUIT) at the default disposition.
        fake.set([["exit", 0]])
        st, out, _, _ = _pty(fake, tmp_path)
        assert os.WIFEXITED(st), out
        s = fake.starts()
        assert [(r["sigint"], r["sigquit"]) for r in s] == [("default", "default")]
    elif case == "ctrl-c-child":
        # SIGINT to the group while the child runs: the child takes it, the launcher lives,
        # writes its stop line and exits with the child's status as a shell reports it.
        fake.set([["idle", 30]])
        st, out, mark, said = _pty(fake, tmp_path, when=_started(fake),
                                   act=lambda pid: os.killpg(pid, signal.SIGINT))
        assert mark is not None and os.WIFEXITED(st), out
        assert os.WEXITSTATUS(st) == 128 + signal.SIGINT, out
        assert fake.sigs() == [{"n": 0, "sig": int(signal.SIGINT)}]
        assert _stops() == ["no-marker"] and len(fake.starts()) == 1
        assert b"the chain stopped (no-marker)" in out
    elif case == "ctrl-c-grace":
        # SIGINT in the grace stops the chain with `interrupted` and starts nothing.
        fake.set(_sitting(fake))
        st, out, mark, said = _pty(fake, tmp_path, grace=20,
                                   when=lambda out: b"ended on RESPAWN" in out,
                                   act=lambda pid: os.killpg(pid, signal.SIGINT))
        assert mark is not None and os.WIFEXITED(st) and os.WEXITSTATUS(st) == 0, out
        assert _stops() == ["interrupted"] and _lines("restart") == []
        assert len(fake.starts()) == 1
    elif case == "hangup":
        # SIGHUP stops the chain with `hangup` after the child exits, and the launcher
        # writes nothing to the terminal, before the hang-up or after it.
        done = tmp_path / "child-done"
        fake.set([["idle", 1.0], ["write", str(done), "x"], ["exit", 0]])
        seen = {}

        def hang_up(pid):
            os.kill(pid, signal.SIGHUP)
            seen["child_done_at_hup"] = done.exists()
        st, out, mark, said = _pty(fake, tmp_path, when=_started(fake), act=hang_up)
        assert mark is not None and os.WIFEXITED(st) and os.WEXITSTATUS(st) == 0, out
        assert seen == {"child_done_at_hup": False} and done.exists()
        assert _stops() == ["hangup"] and len(fake.starts()) == 1
        assert out == b"" and [r["line"] for r in said] == [None], (out, said)
    elif case == "ctrl-c-taken-then-respawn":
        # S20b's review F3: a Ctrl-C the child took and survived is the child's, never the
        # chain's: its later RESPAWN close restarts it (chain.py's drop at the grace).
        trapped = Path(str(fake.log) + ".trapped")
        fake.set([["trap_int"], ["wait_int", 30], *_sitting(fake)], [["exit", 0]])
        st, out, mark, said = _pty(fake, tmp_path, when=lambda out: trapped.exists(),
                                   act=lambda pid: os.killpg(pid, signal.SIGINT))
        assert mark is not None and os.WIFEXITED(st) and os.WEXITSTATUS(st) == 0, out
        assert {"n": 0, "sig": int(signal.SIGINT)} in fake.sigs()
        assert len(fake.starts()) == 2 and len(_lines("restart")) == 1, out
        assert _stops() == ["no-marker"]


# ---- the stale call (2026-10-11): a helper's call that another PreToolUse hook blocks ----
# The tool never runs, so neither PostToolUse nor PostToolUseFailure fires and its
# `calls/<id>` stayed open: `_ready` held the sitting forever (an orient sitting, 2026-10-11).
# Claude Code fires PostToolBatch once every call of the batch has resolved, the blocked
# one included; a call still running is in no resolved batch, so it holds.

STALE_SID = "s22-stale-0000-1111"
BLOCKED = "PreToolUse:Bash hook error: BLOCKED by the stray-write guard"


def _batch(helper, *ids):
    """A helper's PostToolBatch through the CLI's entry point, as the shim runs it."""
    import io
    from contextlib import redirect_stdout
    payload = {**helper, "hook_event_name": "PostToolBatch", "tool_calls": [
        {"tool_name": "Bash", "tool_input": {"command": "true"}, "tool_use_id": i,
         "tool_response": BLOCKED} for i in ids]}
    real, sys.stdin = sys.stdin, io.StringIO(json.dumps(payload))
    try:
        with redirect_stdout(io.StringIO()):
            assert hooks.dispatch("PostToolBatch") == 0
    finally:
        sys.stdin = real


def _ended_turn(sdir):
    """The marker, the main thread's last tool before it, then the turn's end: the time
    `_ready` reads from, a day later (the helpers' stamps are older still)."""
    base = time.time()
    (sdir / hooks.MARKER).write_text(json.dumps({"written": base}))
    (sdir / hooks.ACTIVITY).write_text(json.dumps({"at": base + 5}))
    (sdir / hooks.TURN_ENDED).write_text(json.dumps({"at": base + 11}))
    return base + 86400


def test_s22_blocked_call_never_holds_ready(fake):
    ch = C()
    sdir = resolver.session_dir(_state(), STALE_SID)
    helper = {"session_id": STALE_SID, "agent_id": "a1", "agent_type": "general-purpose"}
    hooks.pre_tool_use({**helper, "tool_name": "Bash", "tool_use_id": "toolu_01blocked",
                        "tool_input": {"command": "true"}})
    assert [p.name for p in (sdir / hooks.CALLS).iterdir()] == ["toolu_01blocked"]
    _batch(helper, "toolu_01blocked")               # the guard blocked it: no Post, no Failure
    now = _ended_turn(sdir)
    assert _chain(ch.Effects(), dict(G))._ready(sdir, now) is True


def test_s22_live_call_still_holds_ready(fake):
    # A helper's 10-minute gate is in no resolved batch: it holds until its own Post.
    ch = C()
    sdir = resolver.session_dir(_state(), STALE_SID)
    a1 = {"session_id": STALE_SID, "agent_id": "a1"}
    a2 = {"session_id": STALE_SID, "agent_id": "a2"}
    hooks.pre_tool_use({**a1, "tool_name": "Bash", "tool_use_id": "toolu_01blocked"})
    hooks.pre_tool_use({**a2, "tool_name": "Bash", "tool_use_id": "toolu_02gate"})
    _batch(a1, "toolu_01blocked")
    now = _ended_turn(sdir)
    c = _chain(ch.Effects(), dict(G))
    assert [p.name for p in (sdir / hooks.CALLS).iterdir()] == ["toolu_02gate"]
    assert c._ready(sdir, now) is False
    hooks.post_tool_use({**a2, "tool_name": "Bash", "tool_use_id": "toolu_02gate"})
    assert c._ready(sdir, now) is True                                  # the positive control
