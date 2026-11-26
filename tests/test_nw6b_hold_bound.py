"""Packet nw6b-hold-bound: a held respawn's ceiling (H1, H2), counted from the sitting's
first confirmed mark, the words that say when (H3), the mark's own `settle` (H4) and a
helper stamp's agent id (H5).

Every case runs on stand-ins: the fake effects of test_chain, a temp state folder, a
made-up session and helpers; no launcher of this machine is read or signalled."""
import json
import os
import re
import time

import pytest

from claude_session import chain, hooks, resolver
from test_chain import (G, RESPAWN_TEXT, T0, TERM, _frun, _fx, _held, _peek, _state, end,  # noqa: F401
                        fake, hook, respawn_seq, write)
from test_nw6_r4_signals import _call, _spawn_line
from test_nw6_held_respawn import (LAUNCHER, MARKED, METER, SID, _ledger, _mark, _marked,  # noqa: F401
                                   _open, _prompt, _record, _run, _session, _spawn, _stamp,
                                   cli_env)

AT174 = os.path.join(os.path.dirname(__file__), "fixtures", "nw6b", "at-174.json")
KEYED = "hold_max" in resolver.RESPAWN_KEYS          # False at the pin (alpha.174)


def _signal(fx):
    ((t, sig),) = fx.procs[0].signals
    assert sig == TERM
    return t - T0


def _hm(t):
    return time.strftime("%H:%M", time.localtime(t))


def _hold(env, n):
    """The repo's config names `respawn.hold_max: n`; at the pin no such key exists, so
    nothing is written (its value there is no ceiling)."""
    if KEYED:
        d = env / resolver.REPO_DIR
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.yaml").write_text(f"session:\n  respawn: {{hold_max: {n}}}\n")


def _run_held(fake, monkeypatch, seq, hold_max, plans_after=None):
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + seq + [end(9000)], plans_after or [end(1)]])
    _frun(fx, {**G, "hold_max": hold_max})
    return fx


# A helper at work: a call open from 12 to 4000, and a short call's stamp each ten minutes,
# so the stale rule never passes it; at the pin it holds the restart to 4060.
OPEN = ([(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
         (4000, _call("PostToolUse", "a1", "toolu_01"))]
        + [(600 * k, _call("PostToolUse", "a1", f"toolu_1{k}")) for k in range(1, 7)])


# ---- H1: the key -----------------------------------------------------------------------------

def test_h1_the_key_is_shipped_at_1800_and_refused_as_the_others(fake):
    env = dict(os.environ)
    assert chain.run_guards(fake.work, env, {})["hold_max"] == 1800
    assert "hold_max" not in chain.guards(fake.work, env, {})      # the three guards stand
    d = fake.work / resolver.REPO_DIR
    d.mkdir(parents=True)
    (d / "config.yaml").write_text("session:\n  respawn: {hold_max: 0}\n")
    assert chain.run_guards(fake.work, env, {})["hold_max"] == 0
    for bad in ("-1", "1.5", "true", "x"):
        (d / "config.yaml").write_text(f"session:\n  respawn: {{hold_max: {bad}}}\n")
        with pytest.raises(resolver.ResolveError, match="respawn.hold_max must be a non-negative"):
            chain.run_guards(fake.work, env, {})


# ---- H2: the ceiling, from the first confirmed mark --------------------------------------------

@pytest.mark.parametrize("hold_max,want", [(600, 612), (0, 4060)])
def test_h2_an_open_call_is_signalled_at_the_mark_plus_the_ceiling(hold_max, want, fake, monkeypatch):
    fx = _run_held(fake, monkeypatch, OPEN, hold_max)
    assert want <= _signal(fx) <= want + 2 and len(fx.procs) == 2


@pytest.mark.parametrize("hold_max", [1800, 0])
def test_h2_the_stale_rule_still_signals_earlier(hold_max, fake, monkeypatch):
    """A call open from 12 and never closed, no stamp since: stale at 1212, under 1812."""
    seq = [(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01"))]
    fx = _run_held(fake, monkeypatch, seq, hold_max)
    assert 1212 <= _signal(fx) <= 1214


REFUTED = [(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
           (1100, _call("PostToolUse", "a1", "toolu_01")),
           (1105, hook("UserPromptSubmit", prompt="<task-notification>x</task-notification>")),
           (1250, _call("PreToolUse", "a1", "toolu_02")), (1300, hook("Stop")),
           (4000, _call("PostToolUse", "a1", "toolu_02"))]


@pytest.mark.parametrize("hold_max,want", [(1800, 1812), (0, 2450)])
def test_h2_the_refuters_hold_that_lapses_counts_from_the_mark(hold_max, want, fake, monkeypatch):
    """The refuter's test_since_resets_across_a_woken_turn: the hold lapses in the woken
    turn and starts again at 1250; the ceiling counts from the mark at 12, not from 1250
    (3050). Its control, at 0, is main's 2450 (the stale rule)."""
    fx = _run_held(fake, monkeypatch, REFUTED, hold_max)
    assert want <= _signal(fx) <= want + 2


def test_h2_the_sittings_own_turn_past_the_ceiling_is_not_signalled_under(fake, monkeypatch):
    seq = OPEN + [(500, hook("UserPromptSubmit", prompt="go")), (900, hook("Stop"))]
    fx = _run_held(fake, monkeypatch, seq, 600)
    assert 960 <= _signal(fx) <= 962


def test_h2_a_second_mark_keeps_the_first_marks_moment(fake, monkeypatch):
    seq = OPEN + [(390, hook("UserPromptSubmit", prompt="go"))] + respawn_seq(fake.charter, at=391)
    seen = []

    def look(fx, p):
        sdir = resolver.session_dir(_state(), p.sid)
        seen.append((json.loads((sdir / hooks.MARKER).read_text())["written"] - T0,
                     json.loads((sdir / hooks.FIRST_MARK).read_text())["at"] - T0))
    fx = _run_held(fake, monkeypatch, seq + [(500, look)], 600)
    assert seen == [(393, 12)]
    assert 612 <= _signal(fx) <= 614


def test_h2_a_launcher_started_again_mid_hold_reads_the_same_moment(fake, monkeypatch):
    """A second launcher, with no memory of the first, reads the moment from the files."""
    seen = []

    def again(fx, p):
        c = chain.Chain("c1", ["--model", "m"], _state(), fx, {**G, "hold_max": 600})
        c.g = c.guards()
        sdir = resolver.session_dir(_state(), p.sid)
        seen.extend([c._ready(sdir, p.start + 611), c._ready(sdir, p.start + 613)])
    fx = _run_held(fake, monkeypatch, OPEN + [(300, again)], 600)
    assert seen == [False, True]
    assert 612 <= _signal(fx) <= 614


def test_h3_until_is_the_signals_moment_after_the_wall_clock_steps(fake, monkeypatch):
    seen = []

    def step(fx, p):
        fx.t += 200                                   # the wall clock steps forward

    fx = _run_held(fake, monkeypatch, OPEN + [(100, _peek(seen)), (300, step), (305, _peek(seen))],
                   600)
    until = seen[0]["until"]
    assert until == T0 + 12 + 600 and seen[1]["until"] == until
    assert until - T0 <= _signal(fx) <= until - T0 + 2


def test_h3_no_until_and_mains_record_at_zero(fake, monkeypatch):
    seen = []
    _run_held(fake, monkeypatch, OPEN + [(100, _peek(seen))], 0)
    assert set(seen[0]) == {"reason", "since", "session", "by", "pid", "started"}


# ---- H3: the words ------------------------------------------------------------------------------

def test_h3_the_marks_line_says_when(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _ledger(_spawn(SID, "a1", "build nw6", time.time() - 60))
    _open("a1", "toolu_01", time.time() - 50)
    t = time.time()
    line = _mark()
    sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
    written = json.loads((sdir / hooks.MARKER).read_text())["written"]
    assert line == ('respawn marked; the restart waits on 1 helper out: "build nw6"; the '
                    "launcher restarts this sitting once they are quiet and this turn has "
                    f"ended, or at {_hm(written + 1800)} whatever is out"), (line, t)
    (sdir / hooks.FIRST_MARK).write_text(json.dumps({"session": SID, "at": written - 3600}))
    assert _mark().endswith(f"or at {_hm(written - 1800)} whatever is out")   # a second mark


def test_h3_no_helper_at_the_mark_is_the_pins_line(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    assert _mark() == LAUNCHER


def _until_record(until):
    _record(MARKED, MARKED + 70)
    p = resolver.state_dir(os.environ) / "respawn" / "c1" / "held.json"
    p.write_text(json.dumps({**json.loads(p.read_text()), "until": until}))


TELL = "; tell them to commit and hand back, or stop them"


@pytest.mark.parametrize("minutes,tell", [(10, False), (15, True), (40, True)])
def test_h3_the_prompts_line_and_status_say_when(minutes, tell, cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    until = MARKED + 1800
    _until_record(until)
    monkeypatch.setattr(time, "time", lambda: MARKED + minutes * 60 + 5)
    held = (minutes * 60 + 5 - 70) // 60
    base = f'respawn marked at {_hm(MARKED)}, held {held} min by 1 helper: "build nw6"'
    when = f"; the restart comes once they are quiet, or at {_hm(until)} whatever is out"
    got = _prompt()
    assert f"; {base}{TELL if tell else ''}{when}" in got, got
    rc, out, _ = _run("status")
    assert rc == 0 and f"{base}{when}" in out.splitlines(), out
    rc, out, _ = _run("status", "--json")
    assert json.loads(out)["respawn_held"] == {
        "marked": MARKED, "since": MARKED + 70, "held_minutes": held, "by": ["build nw6"],
        "until": until, "line": base + when}


def test_h3_half_counts_from_the_first_mark_not_a_second(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _session(cli_env)
    _until_record(MARKED + 1800)
    sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
    (sdir / hooks.FIRST_MARK).write_text(json.dumps({"session": SID, "at": MARKED}))
    _marked(MARKED + 1000)                           # a second mark, confirmed
    monkeypatch.setattr(time, "time", lambda: MARKED + 16 * 60)
    assert TELL in _prompt()


def _outputs(env, monkeypatch):
    """Alpha.174's outputs with a live helpers' hold, the record as the launcher writes it
    at 0: the mark's line with one call open, the prompt's line, `status` and `--json`; the
    run-varying parts named as test_nw6_held_respawn's Z5 names them."""
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _hold(env, 0)
    _ledger(_spawn(SID, "a1", "build nw6", time.time() - 60))
    _open("a1", "toolu_01", time.time() - 50)
    out = {"mark": _mark()}
    (resolver.session_dir(resolver.state_dir(os.environ), SID) / hooks.CALLS / "toolu_01").unlink()
    monkeypatch.setattr(time, "time", lambda: MARKED + 20 * 60)
    _session(env)
    _record(MARKED, MARKED + 70)
    out.update(prompt=_prompt(), status=_run("status")[1], json=_run("status", "--json")[1])
    names = sorted(((os.environ["XDG_STATE_HOME"], "<state>"), (os.environ["HOME"], "<home>"),
                    (str(env), "<cwd>"), (os.path.dirname(os.path.dirname(METER)), "<repo>")),
                   key=lambda p: -len(p[0]))
    for k, v in out.items():
        for path, name in names:
            v = v.replace(path, name)
        v = re.sub(r'"ts": "[^"]*"', '"ts": "<ts>"', v)
        out[k] = re.sub(r'"inode": \d+', '"inode": 0', v)
    return out


def test_h3_at_zero_every_output_is_alpha_174s_byte_for_byte(cli_env, monkeypatch):
    """At the pin the fixture was captured by this test with NW6B_CAPTURE naming it."""
    got = _outputs(cli_env, monkeypatch)
    if os.environ.get("NW6B_CAPTURE"):
        with open(os.environ["NW6B_CAPTURE"], "w") as f:
            json.dump(got, f, indent=1, sort_keys=True)
        return
    with open(AT174) as f:
        assert got == json.load(f)


# ---- H4, H5: the mark's own settle, a lone stamp, a label between calls -------------------------

def _mark_at(path, box):
    def act(fx, p):
        with pytest.MonkeyPatch.context() as m:
            m.setenv("CLAUDE_CODE_SESSION_ID", p.sid)
            m.setenv(hooks.CHAIN_VAR, "c1")
            rc, out, err = _run("checkpoint", "--respawn", "--charter", str(path))
            box.append(out.strip().splitlines()[-1:])
    return act


def test_h4_the_mark_reads_the_launchers_settle(fake, monkeypatch):
    """Review 2's test_probe_mark.py: a helper's stamp at 1, the mark at 29, `run --settle
    10`. The launcher waits on nothing, so the mark names nothing; the mark's ceiling is the
    launcher's too."""
    box = []
    bash = {"tool_name": "Bash",
            "tool_input": {"command": f"agentik-session checkpoint --respawn --charter {fake.charter}"}}
    seq = [(1, hook("PostToolUse", tool_use_id="toolu_05", agent_id="a1", tool_name="Bash")),
           (27, write(fake.charter, RESPAWN_TEXT)), (28, hook("PreToolUse", **bash)),
           (29, _mark_at(fake.charter, box)), (30, hook("PostToolUse", **bash)),
           (31, hook("Stop")), end(7200)]
    fx = _fx(monkeypatch, [seq, [end(1)]])
    _frun(fx, {**G, "settle": 10, "hold_max": 300})
    assert box == [[LAUNCHER]]
    assert [[t - T0, s] for t, s in fx.procs[0].signals] == [[42.0, TERM]]
    home = _state() / "respawn" / "c1"
    assert json.loads((home / chain.LAUNCHER_GUARDS).read_text())["settle"] == 10


def test_h4_the_marks_ceiling_is_the_launchers(fake, monkeypatch):
    box = []
    bash = {"tool_name": "Bash",
            "tool_input": {"command": f"agentik-session checkpoint --respawn --charter {fake.charter}"}}
    seq = [(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
           (27, write(fake.charter, RESPAWN_TEXT)), (28, hook("PreToolUse", **bash)),
           (29, _mark_at(fake.charter, box)), (30, hook("PostToolUse", **bash)),
           (31, hook("Stop")), (2000, _call("PostToolUse", "a1", "toolu_01")), end(7200)]
    fx = _fx(monkeypatch, [seq, [end(1)]])
    _frun(fx, {**G, "hold_max": 300})
    assert box == [['respawn marked; the restart waits on 1 helper out: "build x"; the launcher '
                    "restarts this sitting once they are quiet and this turn has ended, or at "
                    f"{_hm(T0 + 29 + 300)} whatever is out"]]
    assert 329 <= _signal(fx) <= 331


def test_h5_a_lone_stamp_at_the_mark_is_not_named(cli_env, monkeypatch):
    monkeypatch.setenv(hooks.CHAIN_VAR, "c1")
    _stamp(time.time() - 5)
    assert _mark() == LAUNCHER


def test_h5_a_holding_helpers_label_stands_between_its_calls(fake, monkeypatch):
    seen = []
    seq = [(11, _spawn_line("a1", "build nw6")), (12, _call("PreToolUse", "a1", "toolu_01")),
           (100, _call("PostToolUse", "a1", "toolu_01")), (110, _peek(seen)),
           (130, _call("PreToolUse", "a1", "toolu_02")), (140, _peek(seen)),
           (1100, _call("PostToolUse", "a1", "toolu_02")), (1120, _peek(seen))]
    fx = _run_held(fake, monkeypatch, seq, 0)
    assert [r["by"] for r in seen] == [["build nw6"]] * 3
    assert seen[0]["since"] == seen[1]["since"] == seen[2]["since"]
    assert 1160 <= _signal(fx) <= 1162                               # as at the pin


def test_h5_the_stamp_carries_the_agent_id(fake, monkeypatch):
    seen = {}

    def look(fx, p):
        seen.update(json.loads((resolver.session_dir(_state(), p.sid) / hooks.HELPER_ACTIVITY)
                               .read_text()))
    _run_held(fake, monkeypatch, [(20, _call("PostToolUse", "a1", "toolu_01")), (21, look)], 0)
    assert seen["agent_id"] == "a1" and set(seen) == {"event", "tool", "at", "agent_id"}
