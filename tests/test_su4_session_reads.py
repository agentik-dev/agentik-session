"""su4-session-reads: three things the suite's status reads from the session tool (packet
su4-session-reads, R1 to R5). Every fixture is the test's own, under the per-test temp state
root (conftest); no runner starts (`spawn_serve` is stubbed), the loop runs only under
test_unattended's stub, and the repos (`crate`, `my crate`) and sessions are made up."""
import io
import json
import os
import shlex
import subprocess
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, hooks, resolver, unattended
from test_unattended import box  # noqa: F401  (box is a fixture)

T0 = 1763100000.0


@pytest.fixture
def root(monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return resolver.state_dir(os.environ)


def run_cli(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def hm(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def gid(n):
    return f"20261114-120000-{n}"


# ---- the gate: R1 and R5 ------------------------------------------------------------------

def gate_state(root, repo):
    """One job running from a caller, one queued from a caller, one queued with neither key;
    all on one key, so the two wait on it and no load is read."""
    q = gate.gate_dir(root) / "queue"
    q.mkdir(parents=True, exist_ok=True)
    plan = {1: {"caller": "su4-caller-a", "queued": T0 - 300},
            2: {"caller": "su4-caller-b", "queued": T0 - 200}, 3: {}}
    for n, more in plan.items():
        e = {"id": gid(n), "repo": repo, "command": ["make", "check"], "env": {}, "locks": [],
             "wall": 60, "label": f"l{n}", "key": "kc", "key_name": "crate", **more}
        (q / f"{gid(n)}.json").write_text(json.dumps(e))
    d = gate.entry_dir(root, gid(1))
    d.mkdir(parents=True)
    os.utime(d, (T0 - 100, T0 - 100))
    (gate.gate_dir(root) / "runner.json").write_text(json.dumps(
        {"pid": os.getpid(), "since": T0 - 1000, "running": [{"id": gid(1), "pgid": None}]}))
    return plan


GATE_TEXT = ("running 20261114-120000-1 {crate} since {run} l1\n"      # the pin's bytes, from
             "queued 20261114-120000-2 {crate} position 1 waits on key crate\n"   # a run at 95da908
             "queued 20261114-120000-3 {crate} position 2 waits on key crate\n"
             "runner: pid {pid} since {since}\n")


@pytest.fixture
def crate(tmp_path):
    p = tmp_path.resolve() / "crate"
    p.mkdir()
    return str(p)


@pytest.mark.parametrize("repo_flag", [False, True])
def test_su4_1_gate_items_hold_caller_and_queued(root, crate, repo_flag):
    plan = gate_state(root, crate)
    argv = ["gate", "status", "--json"] + (["--repo", crate] if repo_flag else [])
    rc, out, _ = run_cli(*argv)
    d = json.loads(out)
    assert rc == 0
    (r,) = d["running"]
    assert list(r) == ["id", "repo", "label", "since", "seconds", "caller", "queued"]
    assert (r["caller"], r["queued"]) == (plan[1]["caller"], plan[1]["queued"])
    q2, q3 = d["queued"]
    assert list(q2) == ["id", "repo", "position", "lock", "label", "key", "wait", "caller",
                        "queued"]
    assert (q2["caller"], q2["queued"]) == (plan[2]["caller"], plan[2]["queued"])
    assert (q3["caller"], q3["queued"]) == (None, None)


def test_su4_2_gate_text_is_the_pins(root, crate):
    gate_state(root, crate)
    rc, out, _ = run_cli("gate", "status")
    assert rc == 0
    assert out == GATE_TEXT.format(crate=crate, run=hm(T0 - 100), pid=os.getpid(),
                                   since=hm(T0 - 1000))


def put(root, n, repo):
    g = gid(n)
    ended = time.time() - 60
    res = {"id": g, "repo": repo, "command": ["make", "check"], "exit": 0,
           "started": ended - 90.0, "ended": ended, "seconds": 90.0,
           "log": str(gate.entry_dir(root, g) / "log"), "caller": None, "cut": None,
           "head": None, "key": "k"}
    gate.entry_dir(root, g).mkdir(parents=True, exist_ok=True)
    gate.result_path(root, g).write_text(json.dumps(res) + "\n")


def test_su4_7_the_more_line_quotes_a_path_with_a_space(root, tmp_path):
    repo = tmp_path.resolve() / "my crate"
    repo.mkdir()
    for n in range(1, gate.REPO_SHOWN + 3):
        put(root, n, str(repo))
    rc, out, _ = run_cli("gate", "status", "--repo", str(repo))
    more = out.splitlines()[-2]
    assert rc == 0 and more == f"2 more: agentik session gate status --repo {shlex.quote(str(repo))} --json"
    assert shlex.split(more)[7] == str(repo)


# ---- the loop's pid: R2 --------------------------------------------------------------------

def pin_ledger(env, start=False):
    """A finished run's ledger of the pin's shape; with `start`, the pid line first."""
    d = unattended.runs_dir(env) / "2026-11-14-1"
    d.mkdir(parents=True, exist_ok=True)
    lines = ([{"ts": "2026-11-14T10:00:00Z", "kind": "start", "pid": 4242}] if start else []) + [
        {"ts": "2026-11-14T10:00:01Z", "kind": "spawn", "row": "r1-crate", "part": 1},
        {"ts": "2026-11-14T10:20:00Z", "kind": "exit", "row": "r1-crate", "total_cost_usd": 1.25},
        {"ts": "2026-11-14T10:20:01Z", "kind": "row", "row": "r1-crate", "state": "built",
         "reason": None, "sha": "a" * 40, "worktree": "/x/crate/.claude/worktrees/r1-crate"},
        {"ts": "2026-11-14T10:20:02Z", "kind": "spawn", "row": "r2-crate", "part": 1},
        {"ts": "2026-11-14T10:30:00Z", "kind": "row", "row": "r2-crate", "state": "red",
         "reason": "acceptance", "sha": None, "resume": "cd /x && claude --resume s"},
        {"ts": "2026-11-14T10:30:01Z", "kind": "stop", "reason": "queue-spent", "cost": 1.25,
         "rows": {"built": ["r1-crate"], "red": ["r2-crate"]}}]
    (d / "ledger.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    return d


UNATTENDED_TEXT = ("2026-11-14-1: {dir}\n  built 1: r1-crate aaaaaaaaaaaa\n"   # the pin's bytes
                   "  red 1: r2-crate acceptance\n  stop queue-spent, $1.25\n")


def test_su4_2_unattended_text_is_the_pins(root):
    d = pin_ledger(os.environ)
    rc, out, _ = run_cli("unattended", "status")
    assert rc == 0 and out == UNATTENDED_TEXT.format(dir=d)


def test_su4_3_a_ledger_of_the_pins_shape_has_no_pid(root):
    pin_ledger(os.environ)
    rc, out, _ = run_cli("unattended", "status", "--json")
    d = json.loads(out)
    assert rc == 0 and d["pid"] is None
    assert [k for k in d if k not in ("schema", "ok")] == ["run", "dir", "rows", "running",
                                                          "stop", "pid"]


def test_su4_3_every_other_reader_passes_the_start_line_over(root):
    env = os.environ
    d = pin_ledger(env)
    before = (unattended.status(env, T0), unattended.status_lines(unattended.status(env, T0)),
              unattended.report(d))
    pin_ledger(env, start=True)
    st = unattended.status(env, T0)
    assert st.pop("pid") == 4242
    after = (st, unattended.status_lines(unattended.status(env, T0)), unattended.report(d))
    before[0].pop("pid", None)
    assert after == before


def test_su4_3_the_loop_writes_its_pid_once(box):  # noqa: F811
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert box.rc == 0
    (start,) = box.kind("start")
    assert box.ledger[0] is start and start["pid"] == os.getpid()
    assert set(start) == {"ts", "kind", "pid"}
    assert unattended.status(box.fx.env, T0)["pid"] == os.getpid()


# ---- the sittings: R3 and R4 ---------------------------------------------------------------

def session(state, sid, at, meter=None, resolved=None):
    d = resolver.session_dir(state, sid)
    d.mkdir(parents=True)
    if at is not None:
        (d / "activity.json").write_text(json.dumps({"event": "PreToolUse", "tool": "Bash",
                                                     "at": at}))
    for name, body in (("meter.json", meter), ("resolved.json", resolved)):
        if body is not None:
            (d / name).write_text(body if isinstance(body, str) else json.dumps(body))
    return d


def meter_of(pc, pt):
    return {"context": 1000, "turns": 3, "pct_context": pc, "pct_turns": pt, "zone": "clear"}


def three(state, now):
    session(state, "su4-fresh", now - 60, meter_of(41.0, 12.0),
            {"session": {"profile": "frontier", "posture": "steady"}})
    session(state, "su4-old", now - 31 * 60, meter_of(5.0, 1.0), {"session": {"profile": "a"}})
    session(state, "su4-broken", now - 120, "{not json", "[1, 2]")
    session(state, "su4-newest", now - 5, meter_of(85.0, 97.0), {"session": {}})


def _tree(p: Path) -> dict:
    return {str(x): (x.read_bytes() if x.is_file() else None) for x in sorted(p.rglob("*"))}


def test_su4_4_status_all_lists_the_open_sittings(root, monkeypatch):
    now = time.time()
    three(root, now)
    home = Path(os.environ["HOME"])
    snap = (_tree(root), _tree(home))

    def no_ps(*a, **k):
        raise AssertionError("a process list was read")
    monkeypatch.setattr(subprocess, "Popen", no_ps)
    monkeypatch.setattr(subprocess, "run", no_ps)
    rc, out, err = run_cli("status", "--all", "--json")
    assert rc == 0, err
    d = json.loads(out)
    assert list(d) == ["schema", "ok", "sittings"]
    assert d["schema"] == "agentik.session.sittings/1" and d["ok"] is True
    rows = d["sittings"]
    assert [r["session_id"] for r in rows] == ["su4-newest", "su4-fresh", "su4-broken"]
    new, fresh, broken = rows
    assert list(fresh) == ["session_id", "zone", "pct_context", "pct_turns", "profile", "at"]
    zone = hooks.state("su4-fresh", dict(os.environ))[1]
    assert fresh == {"session_id": "su4-fresh", "zone": zone, "pct_context": 41.0,
                     "pct_turns": 12.0, "profile": "frontier", "at": fresh["at"]}
    assert zone not in (None, "unknown") and abs(fresh["at"] - (now - 60)) < 1e-6
    assert new["zone"] == hooks.state("su4-newest", dict(os.environ))[1] != zone
    assert new["profile"] is None
    assert {k: broken[k] for k in ("zone", "pct_context", "pct_turns", "profile")} == dict.fromkeys(
        ("zone", "pct_context", "pct_turns", "profile"))
    rc, text, _ = run_cli("status", "--all")
    assert rc == 0 and [x.split()[0] for x in text.splitlines()] == ["su4-newest", "su4-fresh",
                                                                    "su4-broken"]
    assert text.splitlines()[1] == f"su4-fresh {zone} context 41.0% turns 12.0% profile frontier at {hm(now - 60)}"
    assert text.splitlines()[2] == f"su4-broken - context -% turns -% profile - at {hm(now - 120)}"
    assert (_tree(root), _tree(home)) == snap


def test_su4_4_a_folder_not_open_is_passed_over(root):
    now = time.time()
    session(root, "su4-none", None, meter_of(1.0, 1.0))
    d = session(root, "su4-list", None, meter_of(1.0, 1.0))
    (d / "activity.json").write_text("[1]")
    d = session(root, "su4-big", None, meter_of(1.0, 1.0))
    (d / "activity.json").write_text(json.dumps({"at": now}) + " " * hooks.SMALL)
    session(root, "su4-bool", True, meter_of(1.0, 1.0))
    session(root, "not.an.id", now, meter_of(1.0, 1.0))
    (resolver.session_dir(root, "su4-file")).parent.mkdir(parents=True, exist_ok=True)
    resolver.session_dir(root, "su4-file").write_text("{}")
    assert hooks.sittings(dict(os.environ), now) == []


def test_su4_4_an_empty_state_root(root):
    for _ in range(2):
        rc, out, _ = run_cli("status", "--all", "--json")
        assert rc == 0 and json.loads(out)["sittings"] == []
        (root / "sessions").mkdir(parents=True, exist_ok=True)
    rc, out, _ = run_cli("status", "--all")
    assert rc == 0 and out == "no open sitting\n"


def test_su4_4_two_thousand_folders_under_a_second(root, monkeypatch):
    now = time.time()
    base = root / "sessions"
    base.mkdir(parents=True)
    old = json.dumps({"at": now - 7200}).encode()
    for i in range(2000):
        d = base / f"su4-old-{i:04d}"
        d.mkdir()
        (d / "activity.json").write_bytes(old)
        (d / "meter.json").write_text("{not read}")
    three(root, now)
    seen = []
    real = hooks._load_json
    monkeypatch.setattr(hooks, "_load_json", lambda p: seen.append(p.parent.name) or real(p))
    t0 = time.monotonic()
    rows = hooks.sittings(dict(os.environ), now)
    took = time.monotonic() - t0
    assert [r["session_id"] for r in rows] == ["su4-newest", "su4-fresh", "su4-broken"]
    assert took < 1.0, took
    assert not [n for n in seen if n.startswith("su4-old")]


def test_su4_4_all_and_transcript_are_one_or_the_other(root):
    rc, _, err = run_cli("status", "--all", "--transcript", "/nowhere.jsonl")
    assert rc == 2 and "not allowed with" in err


def test_su4_6_describe_names_the_sittings_read(root):
    rc, out, _ = run_cli("describe", "--json")
    reads = {r["name"]: r for r in json.loads(out)["reads"]}      # ak10c4: charter's comes last
    assert reads["sittings"] == {"kind": "status", "name": "sittings",
                                 "argv": ["status", "--all", "--json"]}
    rc, out, _ = run_cli(*reads["sittings"]["argv"])
    d = json.loads(out)
    assert rc == 0 and d["schema"] == "agentik.session.sittings/1" and d["sittings"] == []


# ---- status without --all: the pin's bytes (line 5) ----------------------------------------

STATUS_TEXT = ("session None: 41.0% context (1000/None), 12.0% turns (3/None), zone clear; "
               "None tokens, None with builders (None); None (limits and rules only)\n"
               "measure: none\nmodel: none\nmod: not seen\n")     # the pin's bytes, at 95da908
STATUS_JSON = ('{\n  "schema": "agentik.session.meter/1",\n  "ok": true,\n  "context": 1000,\n'
               '  "turns": 3,\n  "pct_context": 41.0,\n  "pct_turns": 12.0,\n  "zone": "clear",\n'
               '  "launched": false\n}\n')


def test_su4_5_status_without_all_is_the_pins(root, monkeypatch):
    sid = "su4-mine"
    session(root, sid, T0, meter_of(41.0, 12.0), {"session": {"profile": "frontier"}})
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", sid)
    rc, out, _ = run_cli("status")
    assert rc == 0 and out == STATUS_TEXT
    rc, out, _ = run_cli("status", "--json")
    assert rc == 0 and out == STATUS_JSON
