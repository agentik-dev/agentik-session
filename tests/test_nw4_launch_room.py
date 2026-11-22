"""Packet nw4-launch-room: at each launch the plugin counts the room left to the line and says
whether the new helper fits (hq design/31 items 14 to 17). Every state is under the test's own
temp root; no test starts a `claude` or a `make`."""
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

import pytest

from claude_session import admission, cli, hooks, resolver, room

SID = "test-session"
OTHER = "a-different-session-9999"
NOW = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)
SEEDS = {"build": {"median": 29.1, "p90": 55.4}, "fix": {"median": 26.2, "p90": 57.6},
         "phase": {"median": 16.9, "p90": 48.0}, "review": {"median": 9.5, "p90": 18.3},
         "refute": {"median": 9.7, "p90": 17.3},
         "general-purpose": {"median": 14.9, "p90": 64.3}, "scribe": {"median": 0.4, "p90": 0.9}}
LAUNCH = {"back": 2.5, "narrow": {"points": 10, "alone": 15}, "kinds": SEEDS}
BUILDER, ADVERSARY = "relay:builder", "relay:adversary"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setattr(room, "_now", lambda: NOW)
    monkeypatch.setattr(room, "TZ", timezone.utc)


def _sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), SID)


def _session(posture="signal", used=51.0, discipline=True, launch=LAUNCH, meter_on=True):
    sdir = _sdir()
    sdir.mkdir(parents=True, exist_ok=True)
    charter = {"dir": "history/sittings", "required": discipline, "discipline": discipline}
    s = {"profile": "frontier" if discipline else "starter", "posture": posture,
         "charter": charter, "checkpoint_at": 0.8}
    if launch is not None:
        s["launch"] = launch
    (sdir / "resolved.json").write_text(json.dumps({"session": s}))
    (sdir / "model.json").write_text(json.dumps({"model": "opus"}))
    if meter_on:
        (sdir / "meter.json").write_text(json.dumps(
            {"session_id": SID, "pct_context": used, "pct_turns": 4.0, "checkpoint_at": 0.8}))


def _spawn(t, aid, typ=BUILDER, desc="build 1 of row-a", sid=SID):
    return {"ts": t.isoformat(), "session": sid, "kind": "spawn", "subagentType": typ,
            "model": "opus", "description": desc, "tool_use_id": f"tu-{aid}", "agentId": aid}


def _done(t, aid, mins, sid=SID, swept=False):
    return {"ts": t.isoformat(), "session": sid, "kind": "done", "agentId": aid,
            "tool_use_id": None, "durationMs": int(mins * 60000), "swept": swept}


def _resume(t, aid, sid=SID):
    return {"ts": t.isoformat(), "session": sid, "kind": "resume", "to": aid}


def _ledger(rows, raw=None):
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    p = d / admission.LEDGER
    p.write_text(raw if raw is not None else "".join(json.dumps(r) + "\n" for r in rows))
    return p


def _call(desc="review 1 of row-a", typ=ADVERSARY, **extra):
    return {"session_id": SID, "tool_name": "Agent", "tool_use_id": "tu-new",
            "tool_input": {"prompt": "the brief", "description": desc, "subagent_type": typ},
            **extra}


def _pre(payload):
    return hooks.pre_tool_use(payload, os.environ)


def ctx(out):
    return (out.get("hookSpecificOutput") or {}).get("additionalContext")


def denied(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


M = timedelta(minutes=1)
THREE = [_spawn(NOW - 5 * M, "a1"), _spawn(NOW - 4 * M, "a2", ADVERSARY, "review 1 of row-b"),
         _spawn(NOW - 1 * M, "a3", "scribe", "notes")]
TWO = [_spawn(NOW - 10 * M, "b1"), _spawn(NOW - 2 * M, "b2", ADVERSARY, "review 1 of row-b")]


# ---- 1. room and ends ------------------------------------------------------------------------

def test_1_room_is_the_line_less_the_meter_less_each_back():
    assert room.room(80, 51, [2.5] * 3) == pytest.approx(21.5)
    assert room.room(80, 78.6, []) == pytest.approx(1.4)


def test_1_ends_by_the_median_the_ninth_decile_and_now():
    s = NOW - 10 * M
    assert room.ends(s, NOW, 29.1, 55.4) == s + timedelta(minutes=29.1)
    assert room.ends(s, NOW + 30 * M, 29.1, 55.4) == s + timedelta(minutes=55.4)
    assert room.ends(s, NOW + 60 * M, 29.1, 55.4) == NOW + 60 * M


# ---- 2. the kinds' table ---------------------------------------------------------------------

@pytest.mark.parametrize("typ,desc,want", [
    (BUILDER, "fix of review 1, row-a", "fix"), (BUILDER, "mend the parser", "fix"),
    (BUILDER, "fixes for row-a", "fix"), (BUILDER, "row-a review-2 brief", "fix"),
    (BUILDER, "build 2 of row-a", "fix"), (BUILDER, "build 1 of row-a", "build"),
    (BUILDER, "phase 2 of row-a", "phase"), (BUILDER, "row-a", "build"),
    (ADVERSARY, "refute design/31", "refute"), (ADVERSARY, "the refuter round", "refute"),
    (ADVERSARY, "review 1 of row-a", "review"), ("general-purpose", "read it", "general-purpose"),
    ("records:scribe", "write it up", "scribe"), (None, "anything", "general-purpose")])
def test_2_each_description_form_gives_its_kind(typ, desc, want):
    assert room.kind(typ, desc) == want


def _reviews(n, swept_one=False):
    rows = []
    for i in range(n):
        t = NOW - timedelta(hours=3) + i * 5 * M
        rows += [_spawn(t, f"r{i}", ADVERSARY, "review 1", sid=OTHER),
                 _done(t + (i + 1) * M, f"r{i}", i + 1, sid=OTHER, swept=swept_one and i == 0)]
    return rows


def test_2_ten_runs_take_the_ledger_s_minutes_nine_keep_the_seeds():
    _session()
    _ledger(_reviews(10))
    assert room._reading(SID, os.environ, NOW)["table"]["review"] == (5.0, 9.0)
    _ledger(_reviews(9))
    assert room._reading(SID, os.environ, NOW)["table"]["review"] == (9.5, 18.3)


def test_2_a_swept_run_is_not_counted():
    _session()
    _ledger(_reviews(10, swept_one=True))
    assert room._reading(SID, os.environ, NOW)["table"]["review"] == (9.5, 18.3)


def test_2_a_kind_with_no_seed_takes_general_purpose_s():
    assert room.minutes(room.table(SEEDS, []), "explorer") == (14.9, 64.3)


# ---- 3. the verdict --------------------------------------------------------------------------

def test_3_each_verdict():
    late = NOW + 30 * M
    assert room.verdict(21.5, 2.5, NOW + 10 * M, [late], NOW, 10, 15) == "wide"
    assert room.verdict(9.0, 2.5, NOW + 10 * M, [late], NOW, 10, 15) == "fits"
    assert room.verdict(9.0, 2.5, NOW + 31 * M, [late], NOW, 10, 15) == "narrow"
    assert room.verdict(9.0, 2.5, NOW + timedelta(minutes=9.5), [], NOW, 10, 15) == "fits"
    assert room.verdict(9.0, 2.5, NOW + timedelta(minutes=29.1), [], NOW, 10, 15) == "narrow"
    assert room.verdict(2.0, 2.5, NOW + M, [late], NOW, 10, 15) == "none"


def test_3_the_live_case_is_none():
    assert room.verdict(room.room(80, 78.6, []), 2.5, NOW + M, [], NOW, 10, 15) == "none"


# ---- 4. the line as the hook emits it --------------------------------------------------------

WIDE = "launch: room 21.5 to the line, 3 out; this review (about 10 min, 2.5) fits, wide"
FITS = ("launch: room 9.0 to the line, 2 out; this review (about 10 min, 2.5) fits, narrow: "
        "it ends about 14:09, by the last one out at 14:19")
NARROW = ("launch: narrow: this builder would end about 14:29, 10 min after the last one out; "
          "start a shorter helper or write its brief for the next sitting")
ALONE_FITS = ("launch: room 8.0 to the line, none out; this review (about 10 min, 2.5) fits, "
              "narrow: it ends about 14:09, within the 15 min a narrow launch may take with "
              "none out")
ALONE_NARROW = ("launch: narrow: this builder would end about 14:29, 14 min past the 15 min a "
                "narrow launch may take with none out; bring the charter current and respawn; "
                "the successor starts it")
NONE_OUT = ("launch: no room: -3.5 to the line, 2 out, and this review takes 2.5; write its brief "
            "for the next sitting")
NONE_ALONE = ("launch: no room: 1.4 to the line, none out, and this builder takes 2.5; bring the "
              "charter current and respawn; the successor starts it")
REVIEW, BUILD = ("review 1 of row-c", ADVERSARY), ("build 1 of row-c", BUILDER)
CASES = [  # (used, ledger, the new helper, the line, held)
    (51.0, THREE, REVIEW, WIDE, False), (66.0, TWO, REVIEW, FITS, False),
    (66.0, TWO, BUILD, NARROW, True), (72.0, [], REVIEW, ALONE_FITS, False),
    (72.0, [], BUILD, ALONE_NARROW, True), (78.5, TWO, REVIEW, NONE_OUT, True),
    (78.6, [], BUILD, NONE_ALONE, True)]


@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_4_the_line_in_additional_context_and_system_message(used, rows, new, want, held):
    _session("signal", used)
    _ledger(rows)
    out = _pre(_call(*new))
    assert ctx(out) == want and out["systemMessage"] == want and not denied(out)
    assert room.told(_call(*new), os.environ, "signal") == (want, held)


def test_4_with_none_out_the_held_forms_end_with_the_respawn_words():
    for line in (ALONE_NARROW, NONE_ALONE):
        assert line.endswith("bring the charter current and respawn; the successor starts it")


# ---- 5. the postures; a helper's own call ----------------------------------------------------

@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_5_off_says_nothing(used, rows, new, want, held):
    _session("off", used)
    _ledger(rows)
    out = _pre(_call(*new))
    assert ctx(out) is None and "launch:" not in json.dumps(out)


@pytest.mark.parametrize("posture", ["signal", "ask"])
@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_5_signal_and_ask_say_and_pass(posture, used, rows, new, want, held):
    _session(posture, used)
    _ledger(rows)
    out = _pre(_call(*new))
    assert ctx(out) == want and not denied(out)


@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_5_deny_refuses_a_held_launch_and_says_a_fit(used, rows, new, want, held):
    _session("deny", used)
    _ledger(rows)
    out = _pre(_call(*new))
    if held:
        assert denied(out) and out["hookSpecificOutput"]["permissionDecisionReason"] == want
    else:
        assert not denied(out) and ctx(out) == want


@pytest.mark.parametrize("posture", ["signal", "ask", "deny"])
@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_5_a_helper_s_own_call_is_told_and_refused_nothing(posture, used, rows, new, want, held):
    _session(posture, used)
    _ledger(rows)
    assert _pre(_call(*new, agent_id="helper-1")) == {}


# ---- 6. starter ------------------------------------------------------------------------------

def _pin(posture, used, new, **extra):
    """The pin's output: the same call with no `launch` section, which the pin never read."""
    _session(posture, used, discipline=False, launch=None)
    return _pre(_call(*new, **extra))


@pytest.mark.parametrize("posture", ["off", "signal", "ask", "deny"])
@pytest.mark.parametrize("used,rows,new,want,held", CASES)
def test_6_starter_s_output_is_the_pin_s(posture, used, rows, new, want, held):
    _ledger(rows)
    for extra in ({}, {"agent_id": "helper-1"}):
        pin = json.dumps(_pin(posture, used, new, **extra), sort_keys=True)
        _session(posture, used, discipline=False)
        assert json.dumps(_pre(_call(*new, **extra)), sort_keys=True) == pin
        assert "launch:" not in pin


def _status():
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(["status"])
    return rc, out.getvalue()


def test_6_starter_s_status_prints_no_launch_line(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    _session("signal", 51.0, discipline=False)
    _ledger(TWO)
    rc, out = _status()
    assert rc == 0 and "launch:" not in out


# ---- 7. the helpers out ----------------------------------------------------------------------

def test_7_the_helpers_out_from_a_fixture_ledger():
    _session()
    rows = [_spawn(NOW - 50 * M, "out1"),
            _spawn(NOW - 40 * M, "back1", ADVERSARY, "review 1"), _done(NOW - 30 * M, "back1", 10),
            _spawn(NOW - 45 * M, "res1", ADVERSARY, "review 2"), _done(NOW - 35 * M, "res1", 10),
            _resume(NOW - 20 * M, "res1"),
            _spawn(NOW - 10 * M, "else1", sid=OTHER)]
    _ledger(rows)
    out = room._reading(SID, os.environ, NOW)["out"]
    assert [k for k, _ in out] == ["build", "review"]
    assert out[0][1] == NOW - 50 * M + timedelta(minutes=55.4)      # past its median
    assert out[1][1] == NOW                                             # past its ninth decile
    _ledger(rows + [_done(NOW - M, "res1", 19)])
    assert [k for k, _ in room._reading(SID, os.environ, NOW)["out"]] == ["build"]


# ---- 8. status -------------------------------------------------------------------------------

def test_8_status_prints_the_launch_line(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    _session("signal", 66.0)
    _ledger(TWO)
    rc, out = _status()
    assert rc == 0 and out.splitlines()[-1] == (
        "launch: room 9.0 to the line, 2 out: a builder about 14:19, a review about 14:07")
    _ledger([])
    rc, out = _status()
    assert out.splitlines()[-1] == "launch: room 14.0 to the line, none out"


# ---- 9. report, and the ledger untouched -----------------------------------------------------

def test_9_report_and_the_ledger_s_bytes_are_unchanged(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    rows = TWO + _reviews(3)
    p = _ledger(rows)
    before = p.read_bytes()

    def report():
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            cli.main(["report"])
        return out.getvalue()

    first = report()
    for posture in ("off", "signal", "ask", "deny"):
        for used, _, new, _, _ in CASES:
            _session(posture, used)
            _pre(_call(*new))
            _pre(_call(*new, agent_id="helper-1"))
    _status()
    assert p.read_bytes() == before and report() == first
    assert not (p.parent / admission.ROTATED).exists()


# ---- 10. a fault -----------------------------------------------------------------------------

@pytest.mark.parametrize("fault", ["ledger", "meter", "section", "kinds"])
def test_10_a_fault_gives_no_line_and_the_call_passes(fault):
    launch = ({k: v for k, v in LAUNCH.items() if k != "kinds"} if fault == "kinds"
              else None if fault == "section" else LAUNCH)
    _session("deny", 78.6, launch=launch, meter_on=fault != "meter")
    _ledger(TWO, raw="not json\n{also not\n" if fault == "ledger" else None)
    out = _pre(_call(*BUILD))
    assert "launch:" not in json.dumps(out) and room.told(_call(*BUILD), os.environ, "deny") is None
    assert room.status_for(SID, os.environ) is None


# ---- brief 2, R1: a ledger file that is no regular file never hangs the read ---------------

class _Hung(BaseException):
    """Raised by the test's own alarm: a BaseException, so no `except Exception` of the code
    under test swallows it, and a hang is a failure, never a hang of the suite."""


@pytest.fixture
def at_once():
    import signal

    def hung(*_):
        raise _Hung("the read blocked")
    old = signal.signal(signal.SIGALRM, hung)
    signal.setitimer(signal.ITIMER_REAL, 3.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


def _odd(where, what):
    """The ledger's file `where` made `what`, the other one holding TWO's rows."""
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True)
    live, rotated = d / admission.LEDGER, d / admission.ROTATED
    other = rotated if where == admission.LEDGER else live
    other.write_text("".join(json.dumps(r) + "\n" for r in TWO))
    p = d / where
    if what == "fifo":
        os.mkfifo(p)
    elif what == "folder":
        p.mkdir()
    elif what == "unreadable":
        p.write_text(json.dumps(TWO[0]) + "\n")
        os.chmod(p, 0)
    elif what == "binary":
        p.write_bytes(b"\xff\xfe\x00garbage\n")
    return p


@pytest.mark.parametrize("what", ["fifo", "folder", "unreadable", "binary"])
@pytest.mark.parametrize("where", [admission.LEDGER, admission.ROTATED])
@pytest.mark.parametrize("posture", ["signal", "ask", "deny"])
def test_r1b2_a_ledger_that_is_no_regular_file_gives_the_pin_s_output_at_once(
        posture, where, what, at_once):
    _odd(where, what)
    for new in (REVIEW, BUILD):
        _session(posture, 66.0)
        out = _pre(_call(*new))
        assert room.told(_call(*new), os.environ, posture) is None
        _session(posture, 66.0, launch=None)          # the pin read no `launch` and no ledger
        assert json.dumps(out, sort_keys=True) == json.dumps(_pre(_call(*new)), sort_keys=True)
        assert "launch:" not in json.dumps(out)


@pytest.mark.parametrize("what", ["fifo", "folder", "unreadable", "binary"])
@pytest.mark.parametrize("where", [admission.LEDGER, admission.ROTATED])
def test_r1b2_status_over_such_a_ledger_prints_at_once_with_no_launch_line(
        monkeypatch, where, what, at_once):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    _odd(where, what)
    _session("deny", 66.0)
    rc, out = _status()
    assert rc == 0 and "launch:" not in out and room.status_for(SID, os.environ) is None


def test_r1b2_a_torn_last_line_is_skipped_as_at_the_first_build(at_once):
    _session("signal", 66.0)
    _ledger(TWO, raw="".join(json.dumps(r) + "\n" for r in TWO) + json.dumps(TWO[0])[:20])
    assert room.told(_call(*REVIEW), os.environ, "signal") == (FITS, False)


# ---- brief 2, R2: beside helpers all past their ninth decile, the bound for none out --------

SCRIBE = ("notes", "records:scribe")
GHOST = [_spawn(NOW - 180 * M, "g1", ADVERSARY, "review 1 of row-g")]    # past 18.3: ends now
FRESH = _spawn(NOW - 10 * M, "f1")                                          # ends about 14:19
OVER = ", within the 15 min a narrow launch may take with every one out overdue"
OVER_SCRIBE = ("launch: room 7.5 to the line, 1 out; this scribe (about 1 min, 2.5) fits, "
               "narrow: it ends about 14:00" + OVER)
OVER_REVIEW = ("launch: room 7.5 to the line, 1 out; this review (about 10 min, 2.5) fits, "
               "narrow: it ends about 14:09" + OVER)
OVER_BUILD = ("launch: narrow: this builder would end about 14:29, 14 min past the 15 min a "
              "narrow launch may take with every one out overdue; start a shorter helper or "
              "write its brief for the next sitting")
FRESH_SCRIBE = ("launch: room 9.0 to the line, 2 out; this scribe (about 1 min, 2.5) fits, "
                "narrow: it ends about 14:00, by the last one out at 14:19")


@pytest.mark.parametrize("after", [0.0, 5.0, 9.9])
def test_r2b2_the_verdict_beside_overdue_helpers(after):
    rm = after + 2.5
    for over in ([NOW], [NOW, NOW]):
        assert room.verdict(rm, 2.5, NOW + timedelta(minutes=0.4), over, NOW, 10, 15) == "fits"
        assert room.verdict(rm, 2.5, NOW + timedelta(minutes=9.5), over, NOW, 10, 15) == "fits"
        assert room.verdict(rm, 2.5, NOW + timedelta(minutes=29.1), over, NOW, 10, 15) == "narrow"
    fresh = [NOW, NOW + 5 * M]                 # one not overdue: R6 as at the first build
    assert room.verdict(rm, 2.5, NOW + timedelta(minutes=0.4), fresh, NOW, 10, 15) == "fits"
    assert room.verdict(rm, 2.5, NOW + timedelta(minutes=9.5), fresh, NOW, 10, 15) == "narrow"
    assert room.verdict(rm, 2.5, NOW + timedelta(minutes=29.1), fresh, NOW, 10, 15) == "narrow"


def test_r2b2_the_line_s_pure_forms_beside_overdue_helpers():
    e = NOW + timedelta(minutes=29.1)
    assert room.line("narrow", 7.5, 1, "build", 29.1, 2.5, e, None, NOW, 15, timezone.utc) == OVER_BUILD
    e = NOW + timedelta(minutes=9.5)
    assert room.line("fits", 7.5, 1, "review", 9.5, 2.5, e, None, NOW, 15, timezone.utc) == OVER_REVIEW


@pytest.mark.parametrize("posture", ["signal", "ask", "deny"])
def test_r2b2_the_line_beside_one_overdue_review(posture):
    _session(posture, 70.0)
    _ledger(GHOST)
    for new, want, held in ((SCRIBE, OVER_SCRIBE, False), (REVIEW, OVER_REVIEW, False),
                            (BUILD, OVER_BUILD, True)):
        assert room.told(_call(*new), os.environ, posture) == (want, held)
        out = _pre(_call(*new))
        if held and posture == "deny":
            assert denied(out) and out["hookSpecificOutput"]["permissionDecisionReason"] == want
        else:
            assert not denied(out) and ctx(out) == want


@pytest.mark.parametrize("posture", ["signal", "ask", "deny"])
def test_r2b2_a_second_helper_not_overdue_keeps_the_first_build_s_verdicts(posture):
    _session(posture, 66.0)
    _ledger(GHOST + [FRESH])
    for new, want, held in ((SCRIBE, FRESH_SCRIBE, False), (REVIEW, FITS, False),
                            (BUILD, NARROW, True)):
        assert room.told(_call(*new), os.environ, posture) == (want, held)
        assert denied(_pre(_call(*new))) == (held and posture == "deny")


# ---- R12: the keys -------------------------------------------------------------------------

def _resolved(tmp_path, profile=None, repo_text=None):
    home, repo = tmp_path / "home", tmp_path / "repo"
    for d in (home, repo, tmp_path / "state"):
        d.mkdir(exist_ok=True)
    if repo_text is not None:
        (repo / ".claude" / "agentik").mkdir(parents=True, exist_ok=True)
        (repo / ".claude" / "agentik" / "config.yaml").write_text(repo_text)
    env = {"HOME": str(home), "XDG_STATE_HOME": str(tmp_path / "state")}
    return resolver.resolve(repo, SID, env, profile=profile).sections["session"]


@pytest.mark.parametrize("profile", [None, "frontier", "orchestrator", "starter"])
def test_r12_every_profile_resolves_the_seeds(tmp_path, profile):
    assert _resolved(tmp_path, profile)["launch"] == LAUNCH


@pytest.mark.parametrize("text", [
    "session:\n  launch:\n    back: 0\n", "session:\n  launch:\n    back: true\n",
    "session:\n  launch:\n    narrow: {points: -1, alone: 15}\n",
    "session:\n  launch:\n    narrow: {points: 10, alone: 0}\n",
    "session:\n  launch:\n    kinds:\n      build: {median: 30, p90: 20}\n",
    "session:\n  launch:\n    kinds:\n      build: {median: 0, p90: 20}\n",
    "session:\n  launch:\n    other: 1\n"])
def test_r12_the_resolver_refuses_a_bad_launch_key(tmp_path, text):
    with pytest.raises(resolver.ResolveError, match="launch"):
        _resolved(tmp_path, None, text)       # a named profile re-applies over the files


def test_r12_a_layer_s_kind_merges_into_the_seeds(tmp_path):
    s = _resolved(tmp_path, None,
                  "session:\n  launch:\n    kinds:\n      explorer: {median: 5, p90: 9}\n")
    assert s["launch"]["kinds"]["explorer"] == {"median": 5, "p90": 9}
    assert s["launch"]["kinds"]["build"] == SEEDS["build"]


def test_r12_each_key_has_its_sentence():
    from claude_session import plug
    keys = ["launch.back", "launch.narrow.points", "launch.narrow.alone",
            "launch.kinds.build.median", "launch.kinds.scribe.p90"]
    fallback = plug.summary("no.such.key")
    for k in keys:
        assert plug.summary(k) != fallback and len(plug.summary(k)) < 100, k
