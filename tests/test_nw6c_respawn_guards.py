"""nw6c-respawn-guards, a small change: every respawn key has one upper bound (G1, wish row
n419), and a first-mark file that does not parse or names another session is written again
at the next confirmed mark (G2, wish row n418). The refuter's probes of nw6b review 1, N5
and N6, are its red cases.

Every case runs on stand-ins: the fake effects of test_chain, a temp state folder and a temp
home, a made-up session; no launcher of this machine is read or signalled."""
import json
import os

import pytest

from claude_session import chain, cli, hooks, resolver
from test_chain import G, T0, _cli, _frun, _fx, _state, end, fake, hook, respawn_seq  # noqa: F401
from test_nw6_r4_signals import _call, _spawn_line

HUGE = 10 ** 400                     # the probe's value: an OverflowError at the pin
TOP = 10_000_000                     # the bound G1 names


def _profile(home, key, v):
    """A user profiles.yaml under a temp home naming `respawn.<key>: v` in profile `mine`."""
    d = home / ".claude" / "agentik"
    d.mkdir(parents=True, exist_ok=True)
    (d / "profiles.yaml").write_text(f"profiles:\n  mine:\n    respawn: {{{key}: {v}}}\n")
    return {**os.environ, "HOME": str(home), "CLAUDE_SESSION_PROFILE": "mine"}


# ---- G1: one upper bound for every respawn key ---------------------------------------------

def test_g1_the_bound_is_one_constant_beside_the_keys():
    assert resolver.RESPAWN_MAX == TOP
    assert float(TOP) == TOP


@pytest.mark.parametrize("key", resolver.RESPAWN_KEYS)
def test_g1_a_profiles_value_above_the_bound_is_refused_naming_it(key, fake, tmp_path):
    env = _profile(tmp_path / "home", key, HUGE)
    with pytest.raises(resolver.ResolveError, match=f"respawn.{key} must be a non-negative "
                                                    f"integer at most {TOP}"):
        chain.run_guards(fake.work, env, {})
    env = _profile(tmp_path / "home", key, TOP + 1)
    with pytest.raises(resolver.ResolveError, match=f"at most {TOP}"):
        chain.run_guards(fake.work, env, {})


@pytest.mark.parametrize("key", resolver.RESPAWN_KEYS)
def test_g1_the_bound_itself_is_accepted(key, fake, tmp_path):
    env = _profile(tmp_path / "home", key, TOP)
    assert chain.run_guards(fake.work, env, {})[key] == TOP


@pytest.mark.parametrize("key", ["settle", "hold_max"])
def test_g1_the_launchers_guards_refuse_a_flag_above_the_bound(key, fake):
    env = dict(os.environ)
    with pytest.raises(resolver.ResolveError, match=f"respawn.{key} must be a non-negative "
                                                    f"integer at most {TOP}"):
        chain.run_guards(fake.work, env, {key: HUGE})
    assert chain.run_guards(fake.work, env, {key: TOP})[key] == TOP


@pytest.mark.parametrize("key", ["settle", "hold_max"])
def test_g1_run_with_a_profile_above_the_bound_exits_2(key, fake, tmp_path, monkeypatch):
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    for k, v in _profile(tmp_path / "home", key, HUGE).items():
        monkeypatch.setenv(k, v)
    rc, _, err = _cli("run", "--chain", "c1", "--", "--model", "m", "go")
    assert rc == 2 and fake.starts() == [], err
    assert f"respawn.{key} must be a non-negative integer at most {TOP}" in err
    assert len(err.splitlines()) == 1


def test_g1_run_settle_above_the_bound_exits_2(fake, monkeypatch):
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    for raw in (str(HUGE), str(TOP + 1), "9" * 5000, "0" * 30 + "1" * 9):
        rc, _, err = _cli("run", "--chain", "c1", "--settle", raw, "--", "--model", "m", "go")
        assert rc == 2 and fake.starts() == [], err
        assert f"respawn.settle must be a non-negative integer at most {TOP}" in err
        assert len(err.splitlines()) == 1 and len(err) < 200, err


def test_g1_run_settle_at_the_bound_is_taken():
    assert cli._respawn_flag("settle", str(TOP)) == TOP
    assert cli._respawn_flag("settle", "0" * 30 + str(TOP)) == TOP


def test_g1_the_probes_case_through_the_guards_never_overflows(fake, monkeypatch):
    """N6's probe, its value now arriving through run_guards as the launcher reads it."""
    seq = (respawn_seq(fake.charter)
           + [(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
              (2000, _call("PostToolUse", "a1", "toolu_01")), end(9000)])
    fx = _fx(monkeypatch, [seq, [end(1)]])
    for key in ("settle", "hold_max"):
        with pytest.raises(resolver.ResolveError, match=f"at most {TOP}"):
            chain.run_guards(fake.work, dict(os.environ), {key: HUGE})
    _frun(fx, {**G, "hold_max": TOP, "settle": 60})            # the bound itself runs
    assert len(fx.procs) == 2


# ---- G2: a spoilt first-mark file is written again at the next confirmed mark ------------

SID = "00000000-0000-4000-8000-00000000c0de"          # a made-up session
BASH = {"tool_name": "Bash",
        "tool_input": {"command": "agentik-session checkpoint --respawn --charter c.md"}}


def _sdir(tmp_path):
    d = tmp_path / "state" / SID
    d.mkdir(parents=True)
    return d


def _mark(sdir, written, confirm_at=None):
    """A mark's files as the verb and the call's PreToolUse leave them, then its confirm,
    with the clock at `confirm_at` (default written + 1)."""
    (sdir / hooks.ACTIVITY).write_text(json.dumps({"at": written - 1}))
    (sdir / hooks.MARKER).write_text(json.dumps({"session": SID, "written": written}))
    t = written + 1 if confirm_at is None else confirm_at
    with pytest.MonkeyPatch.context() as m:
        m.setattr(hooks.time, "time", lambda: t)
        hooks._confirm(BASH, sdir)


def _first(sdir):
    return json.loads((sdir / hooks.FIRST_MARK).read_text())


def test_g2_the_reviews_case_signals_at_the_first_mark_plus_the_ceiling(fake, monkeypatch):
    """N5's probe: the file spoilt at 100 after the first mark (written at 12), a second
    mark at 391, ceiling 600: the signal at 612 to 614, where the pin gives 994."""
    def spoil(fx, p):
        (resolver.session_dir(_state(), p.sid) / hooks.FIRST_MARK).write_text("{")
    seq = ([(11, _spawn_line("a1", "build x")), (12, _call("PreToolUse", "a1", "toolu_01")),
            (4000, _call("PostToolUse", "a1", "toolu_01"))]
           + [(600 * k, _call("PostToolUse", "a1", f"toolu_1{k}")) for k in range(1, 7)]
           + [(100, spoil), (390, hook("UserPromptSubmit", prompt="go"))]
           + respawn_seq(fake.charter, at=391))
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + seq + [end(9000)], [end(1)]])
    _frun(fx, {**G, "hold_max": 600})
    ((t, _),) = fx.procs[0].signals
    assert 612 <= t - T0 <= 614 and len(fx.procs) == 2


@pytest.mark.parametrize("spoilt", ["{", "", "[]", '"x"', "null", '{"at": 1795000000}'])
def test_g2_a_file_that_does_not_parse_is_written_at_the_next_mark(spoilt, tmp_path):
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0)
    (sdir / hooks.FIRST_MARK).write_text(spoilt)
    _mark(sdir, 1795000393.0)
    assert _first(sdir) == {"session": SID, "at": 1795000013.0}     # the first confirm's moment
    assert chain.first_mark(sdir) == 1795000013.0


def test_g2_a_file_naming_another_session_is_replaced(tmp_path):
    sdir = _sdir(tmp_path)
    other = {"session": "00000000-0000-4000-8000-0000000000ff", "at": 1795000005.0}
    (sdir / hooks.FIRST_MARK).write_text(json.dumps(other))
    _mark(sdir, 1795000012.0)                       # no confirm before it: the marker's own
    assert _first(sdir) == {"session": SID, "at": 1795000012.0}
    (sdir / hooks.FIRST_MARK).write_text(json.dumps(other))
    _mark(sdir, 1795000393.0)
    assert _first(sdir) == {"session": SID, "at": 1795000013.0}


def test_g2_a_good_file_is_never_written_again(tmp_path):
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0)
    good = json.dumps({"session": SID, "at": 1795000012.0, "kept": True})
    (sdir / hooks.FIRST_MARK).write_text(good)
    before = (sdir / hooks.FIRST_MARK).stat().st_mtime_ns
    for w in (1795000393.0, 1795000700.0):
        _mark(sdir, w)
        assert (sdir / hooks.FIRST_MARK).read_text() == good
    assert (sdir / hooks.FIRST_MARK).stat().st_mtime_ns == before


def test_g2_an_absent_file_is_written_at_the_marks_own_moment_as_on_main(tmp_path):
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0)
    assert _first(sdir) == {"session": SID, "at": 1795000012.0}
    (sdir / hooks.FIRST_MARK).unlink()
    _mark(sdir, 1795000393.0)
    assert _first(sdir) == {"session": SID, "at": 1795000393.0}


def test_g2_a_last_confirm_later_than_the_mark_is_not_taken(tmp_path):
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0, confirm_at=1795009999.0)
    (sdir / hooks.FIRST_MARK).write_text("{")
    _mark(sdir, 1795000393.0)
    assert _first(sdir) == {"session": SID, "at": 1795000393.0}


# ---- fix round 1 (review 1's F2, F1 and N1) -------------------------------------------------

def test_k1_a_first_mark_path_that_is_a_folder_still_gets_the_confirm(tmp_path):
    """F2's probe: the first-mark path a folder, so its write fails; the confirm is written
    as on main."""
    sdir = _sdir(tmp_path)
    (sdir / hooks.FIRST_MARK).mkdir()
    _mark(sdir, 1795000012.0)
    assert json.loads((sdir / hooks.CONFIRMED).read_text())["at"] == 1795000013.0
    assert (sdir / hooks.FIRST_MARK).is_dir()


def test_k1_a_first_mark_write_that_raises_changes_nothing_else(tmp_path, monkeypatch):
    sdir = _sdir(tmp_path)
    real = hooks.store._write_private

    def write(path, text):
        if path.name == hooks.FIRST_MARK:
            raise OSError("no room")
        return real(path, text)
    monkeypatch.setattr(hooks.store, "_write_private", write)
    _mark(sdir, 1795000012.0)
    assert not (sdir / hooks.FIRST_MARK).exists()
    assert json.loads((sdir / hooks.CONFIRMED).read_text())["at"] == 1795000013.0


@pytest.mark.parametrize("raw, want", [("0" * 5000, 0), ("0" * 4400 + str(TOP), TOP),
                                       ("0" * 4300 + "5", 5), ("0", 0), ("007", 7)],
                         ids=["zeros5000", "zeros4400-top", "zeros4300-5", "zero", "007"])
def test_k2_leading_zeros_of_any_count_never_raise(raw, want):
    assert cli._respawn_flag("settle", raw) == want


@pytest.mark.parametrize("raw", ["0" * 5000, "0" * 4400 + str(TOP)],
                         ids=["zeros5000", "zeros4400-top"])
def test_k2_run_settle_with_zeros_past_the_digit_limit_is_taken(raw, fake, monkeypatch):
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    rc, _, err = _cli("run", "--chain", "c1", "--settle", raw, "--", "--model", "m", "go")
    assert "respawn.settle" not in err and rc != 2, err


def test_k2_zeros_before_a_value_above_the_bound_still_exit_2():
    with pytest.raises(SystemExit) as e:
        cli._respawn_flag("settle", "0" * 4400 + str(TOP + 1))
    assert e.value.code == 2


@pytest.mark.parametrize("bad", [{"at": "x"}, {}, {"at": 5}, {"at": 2e11}, {"at": None}],
                         ids=["text", "missing", "five", "past-range", "null"])
def test_k3_a_file_naming_this_session_with_no_good_moment_is_written_again(bad, tmp_path):
    """N1's probe: the file names this session but its `at` is no moment first_mark reads;
    it is written again at the next mark, and that moment holds across a third."""
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0)
    (sdir / hooks.FIRST_MARK).write_text(json.dumps({"session": SID, **bad}))
    _mark(sdir, 1795000393.0)
    assert _first(sdir) == {"session": SID, "at": 1795000013.0}
    held = (sdir / hooks.FIRST_MARK).read_bytes(), (sdir / hooks.FIRST_MARK).stat().st_mtime_ns
    _mark(sdir, 1795000700.0)
    assert chain.first_mark(sdir) == 1795000013.0
    assert ((sdir / hooks.FIRST_MARK).read_bytes(),
            (sdir / hooks.FIRST_MARK).stat().st_mtime_ns) == held


@pytest.mark.parametrize("text", ['{"session": "%s", "at": Infinity}' % SID,
                                  '{"session": "%s", "at": 1e400}' % SID], ids=["inf", "1e400"])
def test_k3_an_infinite_moment_is_written_again(text, tmp_path):
    sdir = _sdir(tmp_path)
    _mark(sdir, 1795000012.0)
    (sdir / hooks.FIRST_MARK).write_text(text)
    _mark(sdir, 1795000393.0)
    assert chain.first_mark(sdir) == 1795000013.0


def test_k3_one_test_for_the_hook_and_the_reader():
    ok = chain.first_mark_holds
    assert ok({"session": SID, "at": 1795000012.0}, SID)
    assert ok({"session": SID, "at": chain.AT_FLOOR}, SID) and ok({"session": SID, "at": 1e11}, SID)
    for d in ({"session": SID, "at": chain.AT_FLOOR - 1}, {"session": SID, "at": 1e11 + 1},
              {"session": SID, "at": True}, {"session": "other", "at": 1795000012.0},
              {"session": SID, "written": 1795000012.0}, {}):
        assert not ok(d, SID), d
    assert ok({"session": SID, "written": 1795000012.0}, SID, "written")
