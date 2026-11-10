"""Packet R2 (hq design/08 §4, "Acceptance. R2, config and cadence"): the `session.reconcile`
key, the cadence and the verb `agentik session reconcile [--json] [--force]`, and the
launcher's pass at a respawn close (§11 row C2).

T1 to T3 are items (5) to (7), item (5) with the floor of 24 (fold E4); T4 is §4's "Never"
on the record; T5 the key in the resolver; T6 to T8 the launcher's close. Every world is a
temp hq; `detect` is R1's by its contract, faked where a test needs five detectors."""
import io
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

import pytest

from test_chain import G, T0, _frun, _fx, end, fake, respawn_seq  # noqa: F401  (fixture)

NOW = 1794232800.0                       # 2026-11-09 14:00 UTC
HOUR = 3600
CHARTER = ("# Sitting {name}: hq, x\n\n| item | value |\n|---|---|\n| goal | {goal} |\n"
           "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n## Done-ness\n\n"
           "## Handover\n\n## Next act\nx\n")
IDS = ("churn.a", "churn.b", "eff.idle", "live.goal_unchanged", "live.since_landing")


def hq_world(tmp_path, body="tree: suite.json\n", tree=None):
    """A temp hq: suite.json, and `session.reconcile` as `body` (indented here) in its
    config.yaml; `body` None writes no key."""
    hq = tmp_path / "code" / "hq"
    (hq / ".claude" / "agentik").mkdir(parents=True)
    tree = tree or {"repos": [{"name": "tool"}, {"name": "hq"}]}
    (hq / "suite.json").write_text(json.dumps(tree))
    text = "session:\n  profile: frontier\n"
    if body is not None:
        text += "  reconcile:\n" + "".join(f"    {l}\n" for l in body.splitlines())
    (hq / ".claude" / "agentik" / "config.yaml").write_text(text)
    return hq


def cli(hq, monkeypatch, *argv, now=NOW):
    from claude_session import cli as c
    monkeypatch.chdir(hq)
    monkeypatch.setattr(time, "time", lambda: now)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = c.main(["reconcile", *argv])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def fake_detect(monkeypatch, flagged=(), cmd_bytes=400):
    """R1's `detect` by its contract: five findings, those in `flagged` flagged, each command
    `cmd_bytes` long and holding pipes, as R1's do. Returns the calls."""
    from claude_session import reconcile
    calls = []

    def detect(tree, window, now, roots, *, goal=None, thresholds=None, detectors=None,
               readers=None):
        calls.append({"window": window, "now": now, "roots": roots, "detectors": detectors})
        out = []
        for fid in IDS:
            head = f"cd {roots['hq']} && git log --oneline | grep -c {fid} | sort | uniq -c"
            out.append(reconcile.finding(fid, "hq", 12 if fid in flagged else 1, 10,
                                         (head + " " * cmd_bytes)[:cmd_bytes].rstrip() + " | wc -l",
                                         {"n": 1}, []))
        return out
    monkeypatch.setattr(reconcile, "detect", detect)
    return calls


def folder(d: Path) -> dict:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())} if d.is_dir() else {}


# ---- T1, item (5): the floor and the tree --------------------------------------------------

CONFIG_REDS = {
    "every-3": ("tree: suite.json\nevery: 3\n", ["session.reconcile.every", "floor is 24"]),
    "every-23": ("tree: suite.json\nevery: 23\n", ["session.reconcile.every", "floor is 24"]),
    "tree-missing": ("tree: nowhere.json\n", ["session.reconcile.tree", "nowhere.json"]),
    "no-tree": ("window: 14\n", ["session.reconcile.tree"]),
    "unknown-key": ("tree: suite.json\ncadence: 24\n", ["session.reconcile.cadence"]),
    "detector": ("tree: suite.json\ndetectors: [live.nothing]\n",
                 ["session.reconcile.detectors", "live.nothing"]),
    "threshold": ("tree: suite.json\nthresholds:\n  eff.idle: -1\n",
                  ["session.reconcile.thresholds.eff.idle"]),
    "goal": ("tree: suite.json\ngoal: [elsewhere]\n", ["session.reconcile.goal", "elsewhere"]),
    "read-floor": ("tree: suite.json\nread: {every: 168, floor: 24}\n",
                   ["session.reconcile.read.floor", "floor is 168"]),
    "read-every": ("tree: suite.json\nread: {every: 100}\n",
                   ["session.reconcile.read.every", "168"]),
    "record-outside": ("tree: suite.json\nrecord: ../elsewhere\n", ["session.reconcile.record"]),
    "unset": (None, ["session.reconcile is not set"]),
}


@pytest.mark.parametrize("case", sorted(CONFIG_REDS))
def test_r2_config_exits_2_naming_the_key(case, tmp_path, monkeypatch):
    body, words = CONFIG_REDS[case]
    hq = hq_world(tmp_path, body)
    calls = fake_detect(monkeypatch)
    rc, out, err = cli(hq, monkeypatch)
    assert (rc, out) == (2, ""), err
    assert "invalid choice" not in err and all(w in err for w in words), err
    assert calls == [] and not (hq / "history").exists()


def test_r2_defaults_and_a_good_config_run(tmp_path, monkeypatch):
    hq = hq_world(tmp_path, "tree: suite.json\nevery: 24\nwindow: 7\n"
                            "read: {every: 336, floor: 168, turns: 40, context: 120000}\n")
    calls = fake_detect(monkeypatch)
    rc, out, err = cli(hq, monkeypatch)
    assert rc == 0, err
    (c,) = calls
    assert (c["window"], c["now"]) == (7, NOW)
    assert c["roots"]["hq"] == str(hq) and c["roots"]["repos"] == str(hq.parent)
    assert c["roots"]["projects"] == str(Path(os.environ["HOME"]) / ".claude" / "projects")
    day = datetime.fromtimestamp(NOW).strftime("%Y-%m-%d")
    assert [p.name for p in (hq / "history" / "reconcile").iterdir()] == [f"{day}.md"]


# ---- T2, item (6): not due inside `every`; --force runs ------------------------------------

def test_r2_a_second_run_inside_every_is_not_due_and_writes_nothing(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    calls = fake_detect(monkeypatch)
    assert cli(hq, monkeypatch)[0] == 0
    rec = hq / "history" / "reconcile"
    before = folder(rec)
    assert len(before) == 1
    for later in (3 * HOUR, 23 * HOUR + 3599):
        rc, out, err = cli(hq, monkeypatch, now=NOW + later)
        when = datetime.fromtimestamp(NOW + 24 * HOUR).astimezone().isoformat(timespec="minutes")
        assert (rc, out.strip()) == (0, f"not due until {when}"), err
        assert folder(rec) == before and len(calls) == 1
    rc, out, _ = cli(hq, monkeypatch, "--json", now=NOW + 3 * HOUR)
    doc = json.loads(out)
    assert (rc, doc["due"], doc["next"]) == (0, False, when) and len(calls) == 1
    assert cli(hq, monkeypatch, "--force", now=NOW + 3 * HOUR)[0] == 0 and len(calls) == 2
    assert cli(hq, monkeypatch, now=NOW + 27 * HOUR + 1)[0] == 0 and len(calls) == 3


# ---- T3, item (7): two flagged of five ------------------------------------------------------

def test_r2_two_flagged_of_five_exit_3_and_a_record_of_five_rows(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    fake_detect(monkeypatch, flagged=("churn.b", "live.since_landing"))
    rc, out, err = cli(hq, monkeypatch)
    assert rc == 1, err  # ruled 2026-11-09: flagged is the guide's "a check said no"
    (path,) = (hq / "history" / "reconcile").iterdir()
    text = path.read_text()
    assert len(text.encode()) < 4096, len(text.encode())
    rows = [l for l in text.splitlines() if l.startswith("| `")]
    assert [r.split("`")[1] for r in rows] == list(IDS)
    assert [r.split(" | ")[3] for r in rows].count("yes") == 2
    for r in rows:
        assert "\\| wc -l`" in r and r.count(" | ") == 4      # each command whole, pipes escaped
    assert "churn.b" in out and "live.since_landing" in out and str(path) in out
    rc, out, _ = cli(hq, monkeypatch, "--json", "--force")
    doc = json.loads(out)
    assert (rc, doc["flagged"], len(doc["findings"]), doc["record"]) == (1, 2, 5, str(path))


# ---- T4, "Never": no charter or transcript text in the record --------------------------------

def test_r2_the_record_holds_no_charter_text(tmp_path, monkeypatch):
    hq = hq_world(tmp_path, "tree: suite.json\ndetectors: [live.goal_unchanged]\n")
    d = hq / "history" / "sittings"
    d.mkdir(parents=True)
    for n in (1, 2, 3):
        name = f"2026-11-0{n}-1"
        (d / f"{name}.md").write_text(CHARTER.format(name=name, goal="SECRET-GOAL-WORDS, here"))
    rc, out, err = cli(hq, monkeypatch, "--force")
    assert rc == 0, err
    (path,) = (hq / "history" / "reconcile").iterdir()
    text = path.read_text()
    assert "live.goal_unchanged" in text and "SECRET" not in text and "SECRET" not in out


# ---- T5: the key is the resolver's, and only the verb validates it ---------------------------

def test_r2_the_key_is_known_and_a_bad_one_never_breaks_a_session(tmp_path):
    from claude_session import resolver
    hq = hq_world(tmp_path, "tree: nowhere.json\nevery: 3\n")
    r = resolver.resolve(hq, "test-session", dict(os.environ), overlay={})
    assert not [u for u in r.unknown if "reconcile" in u], r.unknown
    assert r.sections["session"]["reconcile"] == {"tree": "nowhere.json", "every": 3}


# ---- T6 to T8, §11 C2: the launcher's pass at a respawn close ---------------------------------

def _launcher(fake, monkeypatch, pass_=None, key=True):
    if key:
        cfg = fake.work / ".claude" / "agentik"
        cfg.mkdir(parents=True)
        cfg.joinpath("config.yaml").write_text("session:\n  reconcile:\n    tree: suite.json\n")
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)], [end(1)]])
    fx.passes = []

    def reconcile(cwd, timeout):
        fx.passes.append((fx.t, str(cwd), timeout))
        return (pass_ or (lambda: (0, "reconcile: 0 of 3 flagged")))()
    fx.reconcile = reconcile
    return fx


def test_r2_the_launcher_runs_the_pass_at_a_respawn_close(fake, monkeypatch):
    from claude_session import chain
    fx = _launcher(fake, monkeypatch)
    assert _frun(fx, G) == 0
    assert chain.RECONCILE_WAIT == 30 and len(fx.procs) == 2
    ((t, cwd, timeout),) = fx.passes                 # the restart's close; the stop runs none
    assert (Path(cwd), timeout) == (fake.work.resolve(), 30)
    assert fx.procs[0].returncode is not None and t <= fx.procs[1].start
    assert any("reconcile: 0 of 3 flagged" in s for s in fx.said)


@pytest.mark.parametrize("case", ["exit-2", "cut", "raises", "slow"])
def test_r2_a_failed_or_slow_pass_never_stops_the_respawn(case, fake, monkeypatch):
    from claude_session import chain
    holder = {}

    def pass_():
        fx = holder["fx"]
        if case == "raises":
            raise OSError("no interpreter")
        if case == "slow":                     # the real Effects cuts at the bound (T8)
            fx.t += chain.RECONCILE_WAIT
            return None, f"cut after {chain.RECONCILE_WAIT} s"
        return (2, "error: session.reconcile.tree ...") if case == "exit-2" else (None, "cut")
    fx = holder["fx"] = _launcher(fake, monkeypatch, pass_)
    assert _frun(fx, G) == 0
    assert len(fx.procs) == 2 and len(fx.passes) == 1
    assert fx.procs[1].start - fx.passes[0][0] <= chain.RECONCILE_WAIT + 1
    assert [s for s in fx.said if "reconcile" in s], fx.said
    assert [r for r in __import__("test_chain")._lines("restart")]


def test_r2_no_key_no_pass(fake, monkeypatch):
    fx = _launcher(fake, monkeypatch, key=False)
    assert _frun(fx, G) == 0 and len(fx.procs) == 2 and fx.passes == []


def test_r2_the_real_pass_is_cut_at_its_bound(tmp_path, monkeypatch):
    from claude_session import chain
    a = chain.reconcile_argv()          # this interpreter, this tree's launcher, the verb
    assert a[0] == sys.executable and a[-1] == "reconcile"
    assert Path(a[-2]).name == "agentik-session"
    monkeypatch.setattr(chain, "reconcile_argv",
                        lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    t = time.monotonic()
    rc, line = chain.Effects().reconcile(tmp_path, 1)
    assert rc is None and "cut" in line and time.monotonic() - t < 5
    monkeypatch.setattr(chain, "reconcile_argv",
                        lambda: [sys.executable, "-c", "print('a'); print('reconcile: done')"])
    assert chain.Effects().reconcile(tmp_path, 5) == (0, "reconcile: done")


# ---- The review fold (round 1): F1 to F5, F7 to F10 -------------------------------------------
# F1: a stop that arrives during or right after the close's pass is honoured as the grace
# honours it; F2, F5, F10: the record folder; F3: the cadence; F4: the exits; F7: the line;
# F8: the surviving mutants; F9: `reconcile: false` is off.

DAY = 86400


def _day(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d")


def _record(hq: Path, name_t: float, stamp=None) -> Path:
    """A record by hand: named for `name_t`'s date, its `run:` line `stamp` (a time, or
    the text itself), the folder made."""
    rec = hq / "history" / "reconcile"
    rec.mkdir(parents=True, exist_ok=True)
    stamp = name_t if stamp is None else stamp
    run = stamp if isinstance(stamp, str) else \
        datetime.fromtimestamp(stamp).astimezone().isoformat(timespec="seconds")
    p = rec / f"{_day(name_t)}.md"
    p.write_text(f"# reconcile {_day(name_t)}\n\nrun: {run}; tree suite.json; window 14 d; "
                 "every 24 h; 0 of 5 flagged\n")
    return p


def _say_lines(fx):
    return [s for s in fx.said if ": reconcile" in s]


STOPS = {"sigint": "interrupted", "sigquit": "interrupted", "sigterm": "terminated",
         "stop-file": "stop-file"}


def _halt_now(act):
    import signal
    from claude_session import chain
    from test_chain import _state
    if act == "stop-file":
        (chain.home(_state(), "c1") / "STOP").touch()
    else:
        os.kill(os.getpid(), {"sigint": signal.SIGINT, "sigquit": signal.SIGQUIT,
                              "sigterm": signal.SIGTERM}[act])


@pytest.mark.parametrize("act", sorted(STOPS))
def test_r2_fold_a_stop_right_after_the_pass_starts_no_successor(act, fake, monkeypatch):
    from test_chain import _stops
    holder = {}

    def pass_():
        holder["fx"].t += 20                 # the pass runs 20 s of its 30
        _halt_now(act)
        return 0, "reconcile: 0 of 3 flagged"
    fx = holder["fx"] = _launcher(fake, monkeypatch, pass_)
    _frun(fx, G)
    assert len(fx.procs) == 1, fx.said
    assert _stops() == [STOPS[act]], fx.said


@pytest.mark.parametrize("act", ["sigterm", "sigint", "stop-file"])
def test_r2_fold_a_stop_during_the_real_pass_ends_it_within_a_second(act, fake, monkeypatch):
    import threading
    from claude_session import chain
    from test_chain import _stops
    cfg = fake.work / ".claude" / "agentik"
    cfg.mkdir(parents=True)
    cfg.joinpath("config.yaml").write_text("session:\n  reconcile:\n    tree: suite.json\n")
    monkeypatch.setattr(chain, "reconcile_argv",
                        lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    fx = _fx(monkeypatch, [respawn_seq(fake.charter) + [end(7200)], [end(1)]])
    timer = threading.Timer(0.3, _halt_now, (act,))
    t = time.monotonic()
    timer.start()
    try:
        _frun(fx, G)
    finally:
        timer.cancel()
    took = time.monotonic() - t
    assert len(fx.procs) == 1 and _stops() == [STOPS[act]], fx.said
    assert took < 0.3 + 1.5, took


def test_r2_fold_effects_reconcile_polls_its_halt_and_ends_the_pass(tmp_path, monkeypatch):
    from claude_session import chain
    monkeypatch.setattr(chain, "reconcile_argv",
                        lambda: [sys.executable, "-c", "import time; time.sleep(30)"])
    fx = chain.Effects()
    t = time.monotonic()
    fx.halt = lambda: time.monotonic() - t > 0.3
    rc, line = fx.reconcile(tmp_path, 30)
    assert rc is None and time.monotonic() - t < 1.5, line


def _links(tmp_path, hq):
    out = tmp_path / "elsewhere"
    out.mkdir()
    (hq / "outlink").symlink_to(out)
    (hq / "history").mkdir()
    (hq / "history" / "lp").symlink_to(out)
    return out


@pytest.mark.parametrize("record", ["outlink", "outlink/reconcile", "history/lp/r",
                                    ".git/hooks", ".git", "./.git/x"])
def test_r2_fold_a_record_folder_outside_the_repo_or_in_git_exits_2(record, tmp_path,
                                                                     monkeypatch):
    hq = hq_world(tmp_path, f"tree: suite.json\nrecord: {record}\n")
    out = _links(tmp_path, hq)
    (hq / ".git").mkdir()
    calls = fake_detect(monkeypatch)
    rc, so, err = cli(hq, monkeypatch)
    assert (rc, so) == (2, ""), err
    assert "session.reconcile.record" in err and calls == []
    assert list(out.iterdir()) == [] and list((hq / ".git").iterdir()) == []


def test_r2_fold_a_link_that_stays_inside_the_repo_is_a_record_folder(tmp_path, monkeypatch):
    hq = hq_world(tmp_path, "tree: suite.json\nrecord: inlink\n")
    (hq / "real").mkdir()
    (hq / "inlink").symlink_to(hq / "real")
    fake_detect(monkeypatch)
    assert cli(hq, monkeypatch)[0] == 0
    assert [p.name for p in (hq / "real").iterdir()] == [f"{_day(NOW)}.md"]


@pytest.mark.parametrize("case", ["read-only", "a-file", "day-a-folder", "parent-a-file"])
def test_r2_fold_an_unwritable_record_folder_exits_2_before_the_detectors(case, tmp_path,
                                                                        monkeypatch):
    rec_key = "history/f/reconcile" if case == "parent-a-file" else "history/reconcile"
    hq = hq_world(tmp_path, f"tree: suite.json\nrecord: {rec_key}\n")
    rec = hq / "history" / "reconcile"
    if case == "read-only":
        rec.mkdir(parents=True)
        rec.chmod(0o555)
    elif case == "a-file":
        (hq / "history").mkdir()
        rec.write_text("x")
    elif case == "day-a-folder":
        (rec / f"{_day(NOW)}.md").mkdir(parents=True)
    else:
        (hq / "history").mkdir()
        (hq / "history" / "f").write_text("x")
    calls = fake_detect(monkeypatch)
    try:
        for later in (0, HOUR):
            rc, so, err = cli(hq, monkeypatch, now=NOW + later)
            assert (rc, so) == (2, ""), err
            assert "session.reconcile.record" in err and "Traceback" not in err
        assert calls == []
    finally:
        if rec.is_dir():
            rec.chmod(0o755)


def test_r2_fold_a_record_stamped_after_now_is_named_and_left_out(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    ahead = _record(hq, NOW + 30 * DAY)
    calls = fake_detect(monkeypatch)
    rc, so, err = cli(hq, monkeypatch)
    assert rc == 0 and len(calls) == 1, (so, err)
    assert [l for l in (so + err).splitlines() if ahead.name in l].__len__() == 1, (so, err)
    rc, so, _ = cli(hq, monkeypatch, now=NOW + 60)
    assert rc == 0 and so.startswith("not due until") and len(calls) == 1, so
    assert cli(hq, monkeypatch, now=NOW + 24 * HOUR)[0] == 0 and len(calls) == 2


def test_r2_fold_a_forced_run_is_the_last_run_whatever_lies_ahead(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    _record(hq, NOW + 30 * DAY)
    calls = fake_detect(monkeypatch)
    assert cli(hq, monkeypatch, "--force", now=NOW + 5 * DAY)[0] == 0 and len(calls) == 1
    rc, so, _ = cli(hq, monkeypatch, now=NOW + 5 * DAY + 60)
    when = datetime.fromtimestamp(NOW + 6 * DAY).astimezone().isoformat(timespec="minutes")
    assert (rc, so.strip().splitlines()[-1]) == (0, f"not due until {when}") and len(calls) == 1


def test_r2_fold_a_clock_moved_back_holds_nothing_off(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    calls = fake_detect(monkeypatch)
    assert cli(hq, monkeypatch)[0] == 0 and len(calls) == 1
    assert cli(hq, monkeypatch, now=NOW - 10 * DAY)[0] == 0 and len(calls) == 2
    rc, so, _ = cli(hq, monkeypatch, now=NOW - 10 * DAY + 60)
    assert rc == 0 and "not due until" in so and len(calls) == 2, so


@pytest.mark.parametrize("every,rc", [(8760, 0), (8761, 2), (80000000, 2), (23, 2)])
def test_r2_fold_every_has_a_ceiling_of_a_year(every, rc, tmp_path, monkeypatch):
    hq = hq_world(tmp_path, f"tree: suite.json\nevery: {every}\n")
    calls = fake_detect(monkeypatch)
    got, so, err = cli(hq, monkeypatch)
    assert got == rc, err
    if rc == 2:
        assert "floor is 24" in err and "8760" in err and calls == [], err
    else:
        assert cli(hq, monkeypatch, now=NOW + 8759 * HOUR)[1].startswith("not due until")


@pytest.mark.parametrize("stamp", ["2026-13-45T00:00:00", "9999-12-31T23:59:59", "0001-01-01",
                                   "not-a-date", "9999-12-31T23:59:59+14:00"])
def test_r2_fold_an_unreadable_stamp_is_a_record_with_no_run_line(stamp, tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    _record(hq, NOW - HOUR, stamp)
    calls = fake_detect(monkeypatch)
    rc, so, err = cli(hq, monkeypatch)
    assert rc == 0 and len(calls) == 1 and "Traceback" not in err, (so, err)
    assert cli(hq, monkeypatch, "--json", now=NOW + 60)[0] == 0 and len(calls) == 1


def test_r2_fold_any_other_error_is_one_line_and_exit_2(tmp_path, monkeypatch):
    from claude_session import reconcile

    def boom(*a, **k):
        raise RuntimeError("detector broke")
    hq = hq_world(tmp_path)
    monkeypatch.setattr(reconcile, "detect", boom)
    rc, so, err = cli(hq, monkeypatch)
    assert (rc, so) == (2, "") and len(err.strip().splitlines()) == 1, err
    assert "detector broke" in err and "Traceback" not in err


def test_r2_fold_a_failed_write_is_exit_2_and_leaves_no_tmp(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    fake_detect(monkeypatch)

    def no(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", no)
    rc, so, err = cli(hq, monkeypatch)
    assert rc == 2 and "disk full" in err, err
    assert list((hq / "history" / "reconcile").iterdir()) == []


def test_r2_fold_the_record_is_written_whole_then_moved(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    fake_detect(monkeypatch)
    moves, real = [], os.replace

    def spy(src, dst):
        moves.append((Path(src), Path(dst), Path(src).read_text()))
        return real(src, dst)
    monkeypatch.setattr(os, "replace", spy)
    assert cli(hq, monkeypatch)[0] == 0
    ((src, dst, text),) = moves
    assert dst.name == f"{_day(NOW)}.md" and src.parent == dst.parent and src != dst
    assert dst.read_text() == text and text.startswith("# reconcile ")


def test_r2_fold_due_at_exactly_every_and_the_newest_record_counts(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    _record(hq, NOW - 3 * DAY)
    _record(hq, NOW - HOUR)
    calls = fake_detect(monkeypatch)
    rc, so, _ = cli(hq, monkeypatch)
    assert rc == 0 and so.startswith("not due until") and calls == [], so
    assert cli(hq, monkeypatch, now=NOW - HOUR + 24 * HOUR)[0] == 0 and len(calls) == 1


@pytest.mark.parametrize("body,rc,word", [
    ("thresholds: {eff.idle: 0}", 0, None),
    ("window: 0", 2, "session.reconcile.window"),
    ("read: {bogus: 1}", 2, "session.reconcile.read.bogus"),
])
def test_r2_fold_config_edges(body, rc, word, tmp_path, monkeypatch):
    hq = hq_world(tmp_path, f"tree: suite.json\n{body}\n")
    fake_detect(monkeypatch)
    got, _, err = cli(hq, monkeypatch)
    assert got == rc, err
    assert word is None or word in err


def test_r2_fold_a_record_past_4096_bytes_says_so(tmp_path, monkeypatch):
    from claude_session.reconcile import runner
    hq = hq_world(tmp_path)
    fake_detect(monkeypatch)
    monkeypatch.setattr(runner, "RECORD_CAP", 200)
    rc, so, _ = cli(hq, monkeypatch)
    assert rc == 0 and "B, over 200)" in so.strip().splitlines()[-1], so


def test_r2_fold_wanted_never_raises(tmp_path, monkeypatch):
    from claude_session.reconcile import runner

    def boom(cwd, env):
        raise RuntimeError("x")
    monkeypatch.setattr(runner, "raw", boom)
    assert runner.wanted(tmp_path, {}) is False


def test_r2_fold_the_pass_reads_its_env(fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "no-such-profile")
    fx = _launcher(fake, monkeypatch)
    _frun(fx, G)
    assert fx.passes == []


@pytest.mark.parametrize("value", ["false", "null"])
def test_r2_fold_reconcile_false_is_off(value, fake, monkeypatch):
    from claude_session.reconcile import runner
    fx = _launcher(fake, monkeypatch, key=False)
    cfg = fake.work / ".claude" / "agentik"
    cfg.mkdir(parents=True)
    cfg.joinpath("config.yaml").write_text(f"session:\n  reconcile: {value}\n")
    assert runner.wanted(fake.work, dict(os.environ)) is False
    assert _frun(fx, G) == 0 and len(fx.procs) == 2 and fx.passes == []
    assert _say_lines(fx) == []


def test_r2_fold_the_pass_argv_is_isolated(tmp_path):
    from claude_session import chain
    a = chain.reconcile_argv()
    assert a[1] == "-I" and a[2] == "-X" and a[3].startswith("pycache_prefix=")


@pytest.mark.parametrize("code,want", [
    ("import os, sys; print(os.path.samestat(os.fstat(0), os.stat(os.devnull)))", (0, "True")),
    ("import sys; sys.stderr.write('error: the key\\n'); sys.exit(2)", (2, "error: the key")),
    ("print('x' * 400)", (0, "x" * 300)),
    ("import sys; sys.stdout.buffer.write(b'bad \\xff\\xfe line\\n')", (0, "bad �� line")),
    ("print('ok \\x1b[31mred\\x07\\x08 done\\x9b \\x7f end')", (0, "ok [31mred done end")),
])
def test_r2_fold_the_pass_line(code, want, tmp_path, monkeypatch):
    from claude_session import chain
    monkeypatch.setattr(chain, "reconcile_argv", lambda: [sys.executable, "-c", code])
    rc, line = chain.Effects().reconcile(tmp_path, 10)
    assert (rc, line) == want
    assert not [c for c in line if ord(c) < 32 or 127 <= ord(c) < 160], repr(line)


def test_r2_fold_a_record_named_ahead_holds_nothing_off(tmp_path, monkeypatch):
    hq = hq_world(tmp_path)
    _record(hq, NOW + 30 * DAY, "not-a-date")
    calls = fake_detect(monkeypatch)
    assert cli(hq, monkeypatch)[0] == 0 and len(calls) == 1
    rc, so, _ = cli(hq, monkeypatch, now=NOW + 60)
    assert rc == 0 and so.startswith("not due until") and len(calls) == 1, so


def test_r2_fold_reconcile_false_at_the_verb_is_not_set(tmp_path, monkeypatch):
    hq = hq_world(tmp_path, None)
    (hq / ".claude" / "agentik" / "config.yaml").write_text("session:\n  reconcile: false\n")
    calls = fake_detect(monkeypatch)
    rc, so, err = cli(hq, monkeypatch)
    assert (rc, so, calls) == (2, "", []) and "session.reconcile is not set" in err, err


def test_r2_fold_the_pass_never_reads_the_launchers_stdin(tmp_path, monkeypatch):
    from claude_session import chain
    monkeypatch.setattr(chain, "reconcile_argv", lambda: [
        sys.executable, "-c",
        "import os; print(os.path.samestat(os.fstat(0), os.stat(os.devnull)))"])
    saved, (r, w) = os.dup(0), os.pipe()
    os.dup2(r, 0)
    try:
        assert chain.Effects().reconcile(tmp_path, 10) == (0, "True")
    finally:
        os.dup2(saved, 0)
        for fd in (saved, r, w):
            os.close(fd)
