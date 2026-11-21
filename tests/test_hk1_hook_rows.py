"""Packet hk1: a hook cut at its wall leaves a row (R1) and is counted (R2); the helper rule
reads the launcher as a command word (R3); the resolved file holds one relay section (R4)."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import cli, doctor, harness, hooks, resolver

ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = ROOT / "plugin" / "hooks" / "hooks.json"


# ---- R1: the real cmd_hook in a subprocess, its dispatch replaced

def _tool(box: Path, body: str, deadline=None, after="") -> Path:
    """A script running the real `cli.main`, `hooks.dispatch` replaced by `body`; `deadline`
    sets the constant in the child, never by sleeping out the wall."""
    set_deadline = (f"harness.HOOK_DEADLINE['PreToolUse'] = {deadline}\n"
                    if deadline is not None else "")
    p = box / "tool.py"
    p.write_text(
        "import sys, time\nfrom claude_session import cli, harness, hooks\n" + set_deadline
        + f"def dispatch(event):\n    {body}\n"
        "hooks.dispatch = dispatch\ncode = cli.main(sys.argv[1:])\n" + after
        + "raise SystemExit(code)\n")
    return p


def _env(box: Path, t0=True) -> dict:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(box / "home"),
           "XDG_STATE_HOME": str(box / "xdg"), "PYTHONPATH": str(ROOT / "plugin" / "lib")}
    if t0:
        env[harness.HOOK_T0] = str(time.time_ns())
    return env


def _rows(box: Path) -> list:
    p = Path(resolver.state_dir({"XDG_STATE_HOME": str(box / "xdg"), "HOME": str(box / "home")}))
    f = p / harness.HOOKS
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


@pytest.fixture
def box(tmp_path):
    (tmp_path / "home").mkdir()
    resolver.state_dir({"XDG_STATE_HOME": str(tmp_path / "xdg"),
                        "HOME": str(tmp_path / "home")}).mkdir(parents=True)
    return tmp_path


def _spawn(box, tool, t0=True):
    return subprocess.Popen([sys.executable, "-B", str(tool), "hook", "PreToolUse"],
                            env=_env(box, t0), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait_ready(box, p, timeout=20):
    mark = box / "ready"
    end = time.monotonic() + timeout
    while not mark.exists():
        assert p.poll() is None and time.monotonic() < end, p.communicate()
        time.sleep(0.01)


SLEEP = "open(%r, 'w').close(); print('partial'); time.sleep(8); return 0"


def test_hk1_a1_term_writes_a_143_row_and_exits_143(box):
    p = _spawn(box, _tool(box, SLEEP % str(box / "ready")))
    _wait_ready(box, p)
    time.sleep(0.3)
    p.send_signal(signal.SIGTERM)
    out, err = p.communicate(timeout=20)
    assert p.returncode == 143, err
    rows = _rows(box)
    assert [(r["event"], r["exit"]) for r in rows] == [("PreToolUse", 143)]
    assert 300 <= rows[0]["ms"] < 15000, rows
    assert out == ""


def test_hk1_a2_the_deadline_writes_a_124_row_passes_and_prints_nothing(box):
    began = time.monotonic()
    p = _spawn(box, _tool(box, SLEEP % str(box / "ready"), deadline=0.2))
    out, err = p.communicate(timeout=20)
    assert (p.returncode, out) == (0, ""), err
    assert time.monotonic() - began < 7
    rows = _rows(box)
    assert [(r["event"], r["exit"]) for r in rows] == [("PreToolUse", 124)]
    assert 200 <= rows[0]["ms"] < 7000, rows


def test_hk1_a3_a_hook_in_time_is_the_pins(box):
    tool = _tool(box, "print('{\"a\": 1}'); return 2", deadline=0.2,
                 after="time.sleep(0.4)\n")       # past the deadline: the timer is disarmed
    p = _spawn(box, tool)
    out, err = p.communicate(timeout=20)
    assert (p.returncode, out, err) == (2, '{"a": 1}\n', "")
    assert [(r["event"], r["exit"]) for r in _rows(box)] == [("PreToolUse", 2)]


def test_hk1_a3_an_unmeasured_call_arms_nothing(box):
    """No start in the environment: no row, and no deadline, as at the pin."""
    p = _spawn(box, _tool(box, "time.sleep(0.4); print('x'); return 0", deadline=0.1), t0=False)
    out, _ = p.communicate(timeout=20)
    assert (p.returncode, out, _rows(box)) == (0, "x\n", [])


def test_hk1_a3_the_handlers_are_put_back(box):
    """In process: after the call, SIGTERM and SIGALRM are as they were and no timer runs."""
    before = (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGALRM))
    env = _env(box)
    old = hooks.dispatch
    try:
        hooks.dispatch = lambda event: 0
        os.environ[harness.HOOK_T0] = env[harness.HOOK_T0]
        assert cli.cmd_hook(type("A", (), {"event": "PreToolUse"})()) == 0
    finally:
        hooks.dispatch = old
        os.environ.pop(harness.HOOK_T0, None)
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGALRM)) == before
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_hk1_a4_the_constant_is_each_wall_less_half_a_second():
    walls = {e: h["hooks"][0]["timeout"]
             for e, groups in json.loads(HOOKS_JSON.read_text())["hooks"].items()
             for h in groups}
    assert harness.HOOK_WALL == walls
    assert harness.HOOK_DEADLINE == {e: w - 0.5 for e, w in walls.items()}
    assert harness.deadline("NotInTheMap") == harness.HOOK_DEADLINE["PreToolUse"]


# ---- R2: the count

def _plant_hooks(*rows):
    state = Path(resolver.state_dir(os.environ))
    state.mkdir(parents=True, exist_ok=True)
    (state / harness.HOOKS).write_text("".join(
        json.dumps({"event": e, "ms": ms, "exit": x}) + "\n" for e, ms, x in rows))


def test_hk1_a5_report_hooks_shows_the_cut_rows_by_event(capsys):
    _plant_hooks(("PreToolUse", 40, 0), ("PreToolUse", 4500, 124), ("PostToolUse", 3000, 143))
    assert cli.main(["report", "--hooks"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["event", "count", "p50_ms", "p95_ms", "nonzero"]
    assert "cut: PostToolUse 0 at the deadline (124), 1 by TERM (143); " \
           "PreToolUse 1 at the deadline (124), 0 by TERM (143)" in out
    assert cli.main(["report", "--hooks", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["cut"] == {"PostToolUse": {"124": 0, "143": 1}, "PreToolUse": {"124": 1, "143": 0}}


def test_hk1_a5_no_cut_row_no_cut_line(capsys):
    _plant_hooks(("PreToolUse", 40, 0), ("Stop", 30, 3))
    assert cli.main(["report", "--hooks"]) == 0
    assert "cut:" not in capsys.readouterr().out
    assert cli.main(["report", "--hooks", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cut"] == {}


@pytest.mark.parametrize("code", [124, 143])
def test_hk1_a5_doctor_warns_for_a_cut_pre_tool_use(code):
    _plant_hooks(("PreToolUse", 40, 0), ("PreToolUse", 4500, code))
    row = doctor._check_hooks_cut(os.environ)
    assert row is not None and row.ok and row.warn and row.name == "hooks"
    assert "1 PreToolUse" in row.detail


def test_hk1_a5_doctor_has_no_row_for_a_cut_post_tool_use_or_none():
    assert doctor._check_hooks_cut(os.environ) is None
    _plant_hooks(("PostToolUse", 4500, 124), ("PostToolUse", 4500, 143), ("PreToolUse", 9, 2))
    assert doctor._check_hooks_cut(os.environ) is None


# ---- R3: the launcher is a command word

WORD = "chart" + "er"           # spelled apart, so this file's own lines never trip the rule
REFUSED = [f"agentik-session {WORD} close", f"/some/where/bin/agentik-session {WORD} open",
           f"python -m claude_session {WORD} close", f"agentik session {WORD} open x",
           f"bin/agentik-session {WORD} open g", f"cd /w/agentik-session && agentik-session {WORD} close"]
PASSED = [f"cd /w/agentik-session/.claude/worktrees/r1 && grep -n {WORD} plugin/lib/claude_session/hooks.py",
          f"git -C /w/agentik-session commit -m '{WORD} close keeps the sum'",
          f"ls /w/agentik-session/history/sittings && echo {WORD}"]
READS = [f"agentik-session {WORD} show", f"agentik-session {WORD} check f.md"]


def _helper(cmd):
    return {"agent_id": "a1", "tool_name": "Bash", "tool_input": {"command": cmd}}


@pytest.mark.parametrize("cmd,refused", [(c, True) for c in REFUSED] + [(c, False) for c in PASSED]
                         + [(c, False) for c in READS])
def test_hk1_a6_the_launcher_is_a_command_word(cmd, refused):
    assert hooks._helper_charter(_helper(cmd)) is refused, cmd


# ---- R4: one relay section

def test_hk1_a7_as_dict_holds_no_old_section(tmp_path):
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state)}
    r = resolver.resolve(repo, "hk1-sess", env)
    assert resolver.OLD_RELAY not in r.as_dict() and "relay" in r.as_dict()
    (repo / ".claude/agentik").mkdir(parents=True)
    (repo / ".claude/agentik/config.yaml").write_text('agent-relay: {enabled: "off", queue: q.yaml}\n')
    r = resolver.resolve(repo, "hk1-sess", env)
    assert r.sections["relay"]["enabled"] == "off" and r.sections["relay"]["queue"] == "q.yaml"
    assert r.renamed == ["config.yaml: agent-relay is read as relay; rename the key"]
    assert resolver.OLD_RELAY not in r.as_dict()
