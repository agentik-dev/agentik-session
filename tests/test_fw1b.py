"""Packet FW1b (`design/packets/fw1b-set-fill.md`): `set fill`, the word, its end and its mark.

T1 to T11, one per row of the packet's table. The launcher's fake effects are
`tests/test_chain.py`'s, imported as `cx`.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import test_chain as cx
from claude_session import admission, config, hooks, resolver

UTC = timezone.utc
SID = "fw1b-sess-0000-1111"
ORCH = {"profile": "orchestrator", "window": 1_000_000}


def F():
    from claude_session import fill
    return fill


def _now():
    return datetime.now(UTC).replace(microsecond=0)


def _iso(t):
    return t.isoformat(timespec="seconds")


def _seat(sid=SID, profile="orchestrator", window=1_000_000):
    """A resolved file: the profile and the window in force."""
    d = resolver.session_dir(config.STATE_DIR, sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "resolved.json").write_text(json.dumps({"session": {"profile": profile,
                                                             "window": window}}))


def _reading(sid=SID, week=None, five=None, at=None):
    """One reading line on the admission ledger."""
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    lims = [{"kind": k, "percentUsed": 40, "resetsAt": _iso(t)}
            for k, t in (("seven_day", week), ("five_hour", five)) if t is not None]
    with open(d / admission.LEDGER, "a") as fh:
        fh.write(json.dumps({"ts": _iso(at or _now() - timedelta(minutes=1)), "session": sid,
                             "kind": "reading", "rateLimits": lims}) + "\n")


def _overlay_path(sid=SID):
    return config.STATE_DIR / "overlays" / f"{sid}.json"


def _fill(sid=SID):
    p = _overlay_path(sid)
    return json.loads(p.read_text()).get("fill") if p.exists() else None


def _rules_last():
    rc, out, err = cx._cli("rules")
    assert rc == 0, err
    return out.splitlines()[-1]


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file()}


@pytest.fixture
def week(monkeypatch):
    """A main-thread orchestrator on a 1M window whose login's week resets in three days
    and whose five-hour window resets in three hours."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    _seat()
    w = _now() + timedelta(days=3)
    _reading(week=w, five=_now() + timedelta(hours=3))
    return w


# T1 (R1, R2): the word, its stamp, the line.
def test_fw1b_set_turns_it_on(week):
    until = _now() + timedelta(hours=2)
    rc, out, err = cx._cli("set", "fill", "opus", "--until", _iso(until))
    assert rc == 0, err
    v = _fill()
    assert sorted(v) == ["set", "until", "week", "word"]
    assert (v["word"], F().when(v["until"]), F().when(v["week"])) == ("opus", until, week)
    want = f"fill: opus to {F().wall(until)}"
    assert out.strip() == want and _rules_last() == want
    _seat(profile="orchestrator-opus")                     # Opus 5.5 on [1m] (the machine ledger's entry 22)
    assert _rules_last() == want


# T2 (R3): who may not, and where it may not go.
@pytest.mark.parametrize("case,word", [
    ("frontier", "orchestrator on a 1M window"), ("200k", "orchestrator on a 1M window"),
    ("helper", "helper"), ("relay", "helper"), ("depth", "helper"), ("save", "--save"),
    ("config", "--config"), ("no-session", "CLAUDE_CODE_SESSION_ID"),
    ("no-reading", "seven-day")])
def test_fw1b_refused(case, word, week, monkeypatch):
    argv = ["set", "fill", "opus", "--until", _iso(_now() + timedelta(hours=2))]
    if case == "frontier":
        _seat(profile="frontier")
    elif case == "200k":
        _seat(window=200_000)
    elif case == "helper":
        monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    elif case == "relay":
        monkeypatch.setenv("RELAY_ROW", "r1")
    elif case == "depth":
        monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "1")
    elif case == "save":                            # with no --until: today's exit is 1 too
        argv = ["set", "fill", "reset", "--save"]
    elif case == "config":
        argv = ["set", "fill", "reset", "--save", "--config", "orchestrator"]
    elif case == "no-session":
        monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    elif case == "no-reading":                      # another session's week is not this one's
        (admission.directory(os.environ) / admission.LEDGER).unlink()
        _reading("another-session-0000", week=week)
    before = _tree(config.STATE_DIR)
    rc, out, err = cx._cli(*argv)
    assert (rc, out) == (1, ""), err
    assert word in err
    assert _tree(config.STATE_DIR) == before and _fill() is None
    assert not (config.STATE_DIR / "configs.json").exists()


# T3 (R2): a word with no time, or a time that is none.
def test_fw1b_a_word_needs_its_time(week):
    t = _now() + timedelta(hours=2)
    for argv, rc_want, word in (
            (["set", "fill", "opus"], 2, "--until <zoned time>"),
            (["set", "fill", "opus", "--until", t.replace(tzinfo=None).isoformat()], 2, "zone"),
            (["set", "fill", "opus", "--until", "tomorrow"], 2, "zone"),
            (["set", "fill", "maybe", "--until", _iso(t)], 2, "reset, opus or off"),
            (["set", "fill", "off", "--until", _iso(t)], 2, "--until goes with"),
            (["set", "posture", "ask", "--until", _iso(t)], 2, "--until goes with fill"),
            (["set", "fill", "opus", "--until", _iso(_now() - timedelta(hours=1))], 1, "passed")):
        rc, _, err = cx._cli(*argv)
        assert (rc, word in err) == (rc_want, True), (argv, rc, err)
    assert _fill() is None and not _overlay_path().exists()


# T4 (R2): never past the week's reset; the five-hour reset is not the week's.
def test_fw1b_never_past_the_weeks_reset(week):
    rc, out, err = cx._cli("set", "fill", "opus", "--until", _iso(week + timedelta(days=1)))
    assert rc == 0, err
    assert F().when(_fill()["until"]) == week and "the week's reset" in out
    assert out.startswith(f"fill: opus to {F().wall(week)}")
    assert cx._cli("set", "fill", "reset")[0] == 0                       # reset names its time
    assert (_fill()["word"], F().when(_fill()["until"])) == ("reset", week)
    assert _rules_last() == f"fill: reset to {F().wall(week)}"
    early = week - timedelta(days=1)
    assert cx._cli("set", "fill", "reset", "--until", _iso(early))[0] == 0
    assert F().when(_fill()["until"]) == early
    _reading("another-session-0000", week=week + timedelta(days=2), at=_now())   # another login
    assert cx._cli("set", "fill", "reset")[0] == 0
    assert F().when(_fill()["until"]) == F().when(_fill()["week"]) == week


# T5 (R4): the seat and the clock are tested at every read.
def test_fw1b_reads_off_at_every_read(week):
    f = F()
    now = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)                 # a Monday
    end = now + timedelta(hours=2)
    v, cut = f.stamp("reset", None, end, now)
    ov = {"fill": v}
    assert cut is False and f.line(ov, ORCH, {}, now, UTC) == "fill: reset to Mon 22:00"
    assert f.line(ov, ORCH, {}, end - timedelta(seconds=1), UTC) == "fill: reset to Mon 22:00"
    assert f.part(ov, ORCH, {}, now, UTC) == "fill reset to Mon 22:00"
    for at in (end, end + timedelta(seconds=1)):
        assert f.line(ov, ORCH, {}, at, UTC) == "fill: off (its time passed, Mon 22:00)"
        assert f.part(ov, ORCH, {}, at, UTC) is None
    for s in ({"profile": "orchestrator", "window": 200_000},
              {"profile": "frontier", "window": 1_000_000}, {"profile": "orchestrator"}, {}, None):
        assert f.line(ov, s, {}, now, UTC).startswith("fill: off (fill is for an orchestrator")
    for env in ({"CLAUDE_SESSION_HELPER": "1"}, {"RELAY_ROW": "r"}, {"CLAUDE_SESSION_DEPTH": "1"}):
        assert f.line(ov, ORCH, env, now, UTC) == "fill: off (a helper or a relay child never fills)"
    assert f.line({}, ORCH, {}, now, UTC) == f.line(None, ORCH, {}, now, UTC) == "fill: off"
    # the verb's read: a /model switch to a 200k window turns it off, and back on
    assert cx._cli("set", "fill", "reset")[0] == 0
    _seat(window=200_000)
    assert _rules_last().startswith("fill: off (fill is for an orchestrator on a 1M window")
    _seat()
    assert _rules_last() == f"fill: reset to {f.wall(week)}"


# T6 (R4): only this session's overlay is read, and only a stamped word.
def test_fw1b_only_this_sessions_overlay(week, tmp_path, monkeypatch):
    live = {"word": "opus", "until": _iso(week - timedelta(days=1)), "week": _iso(week),
            "set": _iso(_now())}
    assert _rules_last() == "fill: off"
    (config.STATE_DIR / "configs.json").write_text(json.dumps(
        {"frontier": {"fill": "opus"}, "orchestrator": {"fill": live}}))
    d = resolver.session_dir(config.STATE_DIR, SID)
    (d / "resolved.json").write_text(json.dumps({"session": {**ORCH, "fill": live}}))
    home = Path(os.environ["HOME"]) / ".claude" / "agentik"
    home.mkdir(parents=True)
    (home / "profiles.yaml").write_text("defaults:\n  fill: opus\n")
    repo = tmp_path / "repo" / ".claude" / "agentik"
    repo.mkdir(parents=True)
    (repo / "config.yaml").write_text("session:\n  fill: opus\n")
    (repo / "config.local.yaml").write_text("session:\n  fill: opus\n")
    monkeypatch.chdir(tmp_path / "repo")
    monkeypatch.setenv("CLAUDE_SESSION_FILL", "opus")
    assert _rules_last() == "fill: off"                  # a config, a profile, a layer, the env
    (d / "resolved.json").unlink()                       # and resolved afresh from the layers
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator")
    assert _rules_last() == "fill: off"
    _overlay_path("another-session-0000").parent.mkdir(parents=True, exist_ok=True)
    _overlay_path("another-session-0000").write_text(json.dumps({"fill": live}))
    assert _rules_last() == "fill: off"                  # a new session id beside the old overlay
    for bad in ("opus", {"word": "opus"}, {**live, "until": _iso(week + timedelta(seconds=1))},
                {**live, "word": "all"}, {**live, "until": "2026-11-10T18:00"}):
        _overlay_path().write_text(json.dumps({"fill": bad}))
        assert _rules_last() == "fill: off (not a stamped word)", bad
    _overlay_path().write_text(json.dumps({"fill": live}))
    assert _rules_last() == f"fill: opus to {F().wall(week - timedelta(days=1))}"


# T7 (R5): in that one terminal: the launcher hands the word to its successor.
def test_fw1b_the_launcher_hands_it_on(tmp_path, monkeypatch):
    f = F()
    home, seen = cx._state() / "respawn" / "c1", []
    t0 = datetime.fromtimestamp(cx.T0, UTC)
    wk, until = t0 + timedelta(days=2), t0 + timedelta(hours=2)

    def put(fx, p):                                       # the owner's word, in the sitting
        _seat(p.sid)
        _reading(p.sid, week=wk, at=t0 - timedelta(minutes=1))
        with pytest.MonkeyPatch.context() as m:
            m.setenv("CLAUDE_CODE_SESSION_ID", p.sid)
            m.setenv("CLAUDE_SESSION_CHAIN", "c1")
            rc, _, err = cx._cli("set", "fill", "opus", "--until", _iso(until))
            assert rc == 0, err

    look = lambda fx, p: seen.append(_fill(p.sid))
    fx = cx._fx(monkeypatch, [[(1, look), (5, put)] + cx.respawn_seq(tmp_path / "c.md")
                              + [cx.end(3600)], [(1, look), cx.end(2)]])
    cx._frun(fx, cx.FAST)
    a, b = fx.procs[0].sid, fx.procs[1].sid
    assert seen[0] is None and seen[1]["word"] == "opus" and f.when(seen[1]["until"]) == until
    assert json.loads((home / "fill.json").read_text())["session"] == b
    assert [s for s in fx.said if "fill" in s] == [
        f"c1: fill opus to {f.wall(until)} goes to the successor"]
    fx2 = cx._fx(monkeypatch, [[(1, look), cx.end(2)]])   # a later chain, the same name
    cx._frun(fx2, cx.FAST)
    assert seen[2] is None and not (home / "fill.json").exists()

    def short(fx, p):                                     # a word that ends before the restart
        v, _ = f.stamp("opus", t0 + timedelta(seconds=8), wk, t0)
        _overlay_path(p.sid).parent.mkdir(parents=True, exist_ok=True)
        _overlay_path(p.sid).write_text(json.dumps({"fill": v}))
        f.keep(home, p.sid, v)

    fx3 = cx._fx(monkeypatch, [[(5, short)] + cx.respawn_seq(tmp_path / "c.md")
                               + [cx.end(3600)], [(1, look), cx.end(2)]])
    cx._frun(fx3, cx.FAST)
    assert len(fx3.procs) == 2 and seen[3] is None and not (home / "fill.json").exists()
    assert not [s for s in fx3.said if "fill" in s]
    # and by hand: a copy another session held is never handed
    f.keep(home, "an-earlier-sitting", f.stamp("opus", until, wk, t0)[0])
    assert f.hand(home, cx._state(), a, "next-session-0000", t0) is None
    assert _fill("next-session-0000") is None and not (home / "fill.json").exists()


# T8 (R6): the successor is told at its start, and each prompt says it while it is on.
def test_fw1b_session_start_and_prompt(week, tmp_path, monkeypatch):
    until = _now() + timedelta(hours=2)
    assert cx._cli("set", "fill", "opus", "--until", _iso(until))[0] == 0
    part = f"fill opus to {F().wall(until)}"
    env = {**os.environ, "CLAUDE_SESSION_PROFILE": "orchestrator"}
    ctx = hooks.session_start({"session_id": SID, "cwd": str(tmp_path),
                               "model": "claude-fable-5-2"}, env)
    ctx = ctx["hookSpecificOutput"]["additionalContext"]
    assert f"; {part}" in ctx and "fill off" not in ctx
    out = hooks.user_prompt_submit({"session_id": SID})
    assert part.replace("fill ", "fill: ", 1) in out["hookSpecificOutput"]["additionalContext"]
    assert cx._cli("set", "fill", "off")[0] == 0
    ctx = hooks.session_start({"session_id": SID, "cwd": str(tmp_path),
                               "model": "claude-fable-5-2"}, env)
    assert part not in ctx["hookSpecificOutput"]["additionalContext"]
    out = hooks.user_prompt_submit({"session_id": SID})
    assert "fill" not in json.dumps(out)


# T9 (R7): the mark on a spawn line, only while it is on.
def test_fw1b_spawn_mark(week):
    spawn = json.dumps({"kind": "spawn", "subagentType": "Explore", "model": "opus"})

    def last():
        admission.record(SID, spawn, os.environ)
        p = admission.directory(os.environ) / admission.LEDGER
        return json.loads(p.read_text().splitlines()[-1])

    assert admission.OWN_KEYS["spawn"] == ("fill",) and "fill" in admission.LINE_KEYS["spawn"]
    assert "fill" not in last()
    assert cx._cli("set", "fill", "opus", "--until", _iso(_now() + timedelta(hours=2)))[0] == 0
    assert last()["fill"] == "opus"
    _seat(window=200_000)
    assert "fill" not in last()
    _seat()
    assert cx._cli("set", "fill", "reset")[0] == 0 and last()["fill"] == "reset"


# T10 (R1, R3): `off`, and what a word writes: this session's overlay and nothing else.
def test_fw1b_off_and_what_it_writes(week, monkeypatch):
    home = Path(os.environ["HOME"])
    _overlay_path().parent.mkdir(parents=True, exist_ok=True)
    _overlay_path().write_text(json.dumps({"_prompts": 3, "posture": "ask"}))
    before = _tree(home)
    assert cx._cli("set", "fill", "opus", "--until", _iso(_now() + timedelta(hours=2)))[0] == 0
    after = _tree(home)
    rel = str(_overlay_path().relative_to(home))
    assert {k for k in set(before) | set(after) if before.get(k) != after.get(k)} == {rel}
    assert not [k for k in after if "memory" in k or k.endswith("configs.json")]
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "c1")      # under a launcher: the chain's copy
    assert cx._cli("set", "fill", "reset")[0] == 0
    rec = json.loads((config.STATE_DIR / "respawn" / "c1" / "fill.json").read_text())
    assert rec == {"session": SID, "fill": _fill()}
    _seat(profile="frontier")                             # `off` is never refused
    rc, out, err = cx._cli("set", "fill", "off")
    assert (rc, out.strip()) == (0, "fill: off"), err
    left = json.loads(_overlay_path().read_text())
    assert "fill" not in left and (left["_prompts"], left["posture"]) == (3, "ask")
    assert not (config.STATE_DIR / "respawn" / "c1" / "fill.json").exists()
    assert _rules_last() == "fill: off"


# T11 (R8): the docs name the verb; the rule names who may say it.
def test_fw1b_docs():
    from claude_session import rules
    root = Path(__file__).resolve().parents[1]
    for rel in ("plugin/skills/session/SKILL.md", "plugin/commands/set.md", "RUNBOOK.md",
                "README.md", "design/readme/source.md"):
        text = (root / rel).read_text()
        assert "set fill" in text and "--until" in text, rel
    fill_rule = getattr(rules, "FILL", "")
    assert "agentik session set fill" in fill_rule and "never a helper" in fill_rule


# The refuter round's fold (F1 to F6): a failure, or a kill between the two writes, leaves
# the successor with less fill, never more; one line on stderr, never a traceback.
class Kill(BaseException):
    """A kill between two writes: nothing after it runs."""


def _run(*argv):
    try:
        return cx._cli(*argv)
    except Exception as e:  # noqa: BLE001 - a traceback is what the fold removes
        return "raised", "", f"{type(e).__name__}: {e}"


def _home_c1():
    return config.STATE_DIR / "respawn" / "c1"


def _one_error_line(rc, out, err):
    assert (rc, out) == (2, ""), (rc, out, err)
    assert err.startswith("error: ") and err.count("\n") == 1 and "Traceback" not in err, err


def _handed():
    return F().hand(_home_c1(), config.STATE_DIR, SID, "successor-0000-1111", _now())


# T12 (F1): `off` removes the chain's copy first, then this session's word.
def test_fw1b_fold_off_takes_the_copy_first(week, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "c1")
    until = _iso(_now() + timedelta(hours=2))
    assert cx._cli("set", "fill", "opus", "--until", until)[0] == 0
    from claude_session import store
    real = store._write_private

    def killed(path, text):
        if Path(path).parent.name == "overlays":
            raise Kill
        return real(path, text)

    with monkeypatch.context() as m:                    # killed at the overlay's write
        m.setattr(store, "_write_private", killed)
        with pytest.raises(Kill):
            cx._cli("set", "fill", "off")
    assert _handed() is None and _fill("successor-0000-1111") is None
    assert cx._cli("set", "fill", "opus", "--until", until)[0] == 0
    os.chmod(_home_c1(), 0o500)                         # the copy cannot be removed
    try:
        rc, out, err = _run("set", "fill", "off")
    finally:
        os.chmod(_home_c1(), 0o700)
    _one_error_line(rc, out, err)
    assert str(_home_c1() / "fill.json") in err and _fill() is None
    assert _rules_last() == "fill: off"


# T13 (F2): a word that cannot be kept in both places stands in neither.
def test_fw1b_fold_a_failed_word_stands_nowhere(week, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "c1")
    until = _iso(_now() + timedelta(hours=2))
    _home_c1().mkdir(parents=True)
    os.chmod(_home_c1(), 0o500)                         # the chain home cannot be written
    try:
        rc, out, err = _run("set", "fill", "opus", "--until", until)
    finally:
        os.chmod(_home_c1(), 0o700)
    _one_error_line(rc, out, err)
    assert _fill() is None and not (_home_c1() / "fill.json").exists()
    assert _rules_last() == "fill: off"
    _overlay_path().parent.mkdir(parents=True, exist_ok=True)
    os.chmod(_overlay_path().parent, 0o500)             # this session's overlay cannot be
    try:
        rc, out, err = _run("set", "fill", "reset")
    finally:
        os.chmod(_overlay_path().parent, 0o700)
    _one_error_line(rc, out, err)
    assert _fill() is None and not (_home_c1() / "fill.json").exists()
    from claude_session import fill
    real = fill.keep

    def killed(home, sid, v):
        if v is not None:
            raise Kill
        return real(home, sid, v)

    with monkeypatch.context() as m:                    # killed before the copy's write
        m.setattr(fill, "keep", killed)
        with pytest.raises(Kill):
            cx._cli("set", "fill", "opus", "--until", until)
    assert _handed() is None and _fill("successor-0000-1111") is None


# T14 (F3): the SessionStart block keeps its cache part with either word on.
def test_fw1b_fold_the_block_fits_with_its_cache_part():
    from claude_session import rules
    for ttl in sorted(rules.CLAUSE):
        for word in F().WORDS:
            part = f"fill {word} to Wed 22:00"
            c = rules.clause({}, ttl, fill=part)
            assert len(c.encode()) <= rules.BLOCK_MAX, (ttl, word, len(c.encode()))
            assert f"; {part}" in c and rules.CLAUSE[ttl] in c, (ttl, word, c)


# T15 (F4): one seat for every reader: with no resolved file, the verb, `rules`, the
# prompt hook and the spawn mark all read off.
def test_fw1b_fold_one_seat_for_every_reader(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-fable-5-1")
    w = _now() + timedelta(days=3)
    _reading(week=w)
    assert not (resolver.session_dir(config.STATE_DIR, SID) / "resolved.json").exists()
    rc, out, err = cx._cli("set", "fill", "reset")
    assert (rc, out) == (1, "") and "orchestrator on a 1M window" in err, (rc, out, err)
    assert _fill() is None
    _overlay_path().parent.mkdir(parents=True, exist_ok=True)
    _overlay_path().write_text(json.dumps({"fill": F().stamp("reset", None, w, _now())[0]}))
    assert _rules_last().startswith("fill: off (fill is for an orchestrator")
    assert "fill" not in json.dumps(hooks.user_prompt_submit({"session_id": SID}))
    admission.record(SID, json.dumps({"kind": "spawn", "subagentType": "Explore"}), os.environ)
    p = admission.directory(os.environ) / admission.LEDGER
    assert "fill" not in json.loads(p.read_text().splitlines()[-1])


# T16 (F5): the texts say what `off` refuses and what `--until` takes, as the code does.
def test_fw1b_fold_the_texts_say_what_off_refuses(week, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    for rel in ("plugin/skills/session/SKILL.md", "plugin/commands/set.md", "RUNBOOK.md",
                "README.md", "design/readme/source.md"):
        text = " ".join((root / rel).read_text().split())
        assert "<reset|opus|off> --until" not in text, rel
        assert "<reset|opus|off> [--until" not in text, rel
        assert text.count("never refused") == text.count("never refused by the seat"), rel
        assert "set fill off" in text, rel
    rc, out, _ = cx._cli("set", "--help")
    assert rc == 0 and "never with fill off" in " ".join(out.split())
    assert cx._cli("set", "fill", "off", "--save")[0] == 1
    monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")    # never by the seat
    assert cx._cli("set", "fill", "off")[:2] == (0, "fill: off\n")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    assert cx._cli("set", "fill", "off")[0] == 1


# T17 (F6): one case for each mutant the round saw survive.
def test_fw1b_fold_the_ends_at_their_edges(week):
    f = F()
    now = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)
    wk = now + timedelta(days=3)
    with pytest.raises(f.Refused) as e:                 # until equal to now has passed
        f.stamp("opus", now, wk, now)
    assert e.value.code == 1 and "passed" in str(e.value)
    with pytest.raises(f.Refused):                      # a week that resets now bounds nothing
        f.stamp("reset", None, now, now)
    assert f.stamp("opus", wk, wk, now) == (
        {"word": "opus", "until": _iso(wk), "week": _iso(wk), "set": _iso(now)}, False)
    rc, out, err = cx._cli("set", "fill", "opus", "--until", _iso(week))
    assert (rc, out) == (0, f"fill: opus to {f.wall(week)}\n"), err   # not cut: no cut text
    long = "2026-11-10T18:00:00." + "1" * 50 + "+00:00"
    assert len(long) > 64 and f.when(long) is None
    _reading(week=_now() - timedelta(minutes=5), at=_now())   # a passed reading, the newest
    d = admission.directory(os.environ)
    rows = [r for n in (admission.ROTATED, admission.LEDGER) for r in admission._rows(d / n)]
    assert admission.week_reset(rows, SID, _now()) is None


def test_fw1b_fold_the_verb_and_the_prompt_refuse_odd_input(week):
    sid = "fw1b.sess.0000"                              # a prompt id the hook's shape refuses
    _seat(sid)
    _overlay_path(sid).parent.mkdir(parents=True, exist_ok=True)
    _overlay_path(sid).write_text(json.dumps(
        {"fill": F().stamp("reset", None, week, _now())[0]}))
    assert "fill" not in json.dumps(hooks.user_prompt_submit({"session_id": sid}))
    rc, out, err = cx._cli("set", "fill", "reset", "--config", "orchestrator")
    assert (rc, out) == (1, "") and "--config" in err and _fill() is None
