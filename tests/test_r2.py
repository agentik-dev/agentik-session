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
