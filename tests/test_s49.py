"""Packet S49 and its Amendment 1: the shim's one variable, the CLI's row, its bound, the ledger
row's new keys, and `report --hooks`."""

import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import cli, config, harness, hooks, ledger, measure, meter, resolver

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / "plugin" / "hooks" / "run"
FIX = ROOT / "tests" / "fixtures" / "meter"
SID = "meter-sess-1"
TOOL = "cat >/dev/null; echo '{}'; echo said >&2; exit 2\n"


def _exe(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


@pytest.fixture
def box(tmp_path):
    """A state root that exists, a tool on PATH that says something and exits 2."""
    state = tmp_path / "xdg" / config.APP
    state.mkdir(parents=True)
    _exe(tmp_path / "bin" / "agentik-session", TOOL)
    return tmp_path


# The events the shim sends to /dev/null, whatever the tool says.
SILENT_IN_SHIM = ("Stop", "StopFailure", "PostToolUseFailure", "PostToolBatch")


@pytest.fixture
def real(box):
    """The same box with the real CLI on PATH: its row is the thing under test."""
    _exe(box / "bin" / "agentik-session",
         f'PYTHONPATH="{ROOT}" exec "{sys.executable}" -B -m claude_session.cli "$@"\n')
    return box


def _scripted(box, body):
    """The real `cli.main`, its `hooks.dispatch` replaced by `body`."""
    (box / "tool.py").write_text(
        "import sys\nfrom claude_session import cli, hooks\n"
        f"def dispatch(event):\n    {body}\n"
        "hooks.dispatch = dispatch\nraise SystemExit(cli.main(sys.argv[1:]))\n")
    _exe(box / "bin" / "agentik-session",
         f'PYTHONPATH="{ROOT}" exec "{sys.executable}" -B "{box / "tool.py"}" "$@"\n')


def _env(box, path=None):
    return {"PATH": path or f"{box / 'bin'}:/usr/bin:/bin", "HOME": str(box / "home"),
            "XDG_STATE_HOME": str(box / "xdg")}


def _shim(box, event="PreToolUse", path=None, stdin='{"session_id": "s"}', timeout=20):
    return subprocess.run([str(SHIM), event], env=_env(box, path), text=True, input=stdin,
                          capture_output=True, timeout=timeout)


def _rows(box, app=config.APP):
    p = box / "xdg" / app / "hooks.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# ---- the shim: main's flow and one variable (Amendment 1)

MAIN_FLOW = '''case "$1" in
  Stop|StopFailure|PostToolUseFailure|PostToolBatch) "$tool" hook "$1" >/dev/null 2>&1; exit 0 ;;
  PreCompact) "$tool" hook "$1"; exit 0 ;;
esac
exec "$tool" hook "$1"
'''
T0 = "AGENTIK_SESSION_HOOK_T0"


def test_s49_the_shim_is_mains_flow_and_one_variable():
    text = SHIM.read_text()
    assert text.endswith(MAIN_FLOW)
    assert "hooks.jsonl" not in text
    code = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert code[5] == f'export {T0}="$(date +%s%N 2>/dev/null)"'
    assert code[1:5] + code[6:] == [
        'if command -v agentik-session >/dev/null 2>&1; then tool=agentik-session',
        'elif command -v claude-session >/dev/null 2>&1; then tool=claude-session',
        'else exit 0', 'fi', *MAIN_FLOW.splitlines()]
    assert sum("date" in ln for ln in code) == 1


def test_s49_the_shim_execs_the_tool(box):
    _exe(box / "bin" / "agentik-session", "cat >/dev/null; echo $$\n")
    p = subprocess.Popen([str(SHIM), "PreToolUse"], env=_env(box), text=True,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = p.communicate("{}", timeout=20)
    assert out.strip() == str(p.pid)


def test_s49_f1_a_kill_at_the_timeout_leaves_no_tool_running_on(box):
    done = box / "survived"
    _exe(box / "bin" / "agentik-session", f"sleep 0.4; touch '{done}'\n")
    p = subprocess.Popen([str(SHIM), "PreToolUse"], env=_env(box), stdin=subprocess.DEVNULL)
    time.sleep(0.1)
    p.kill()
    p.wait(timeout=5)
    time.sleep(0.6)
    assert not done.exists()


def test_s49_f2_a_kill_closes_stdout_at_once(box):
    _exe(box / "bin" / "agentik-session", "exec sleep 8\n")
    p = subprocess.Popen([str(SHIM), "PreToolUse"], env=_env(box), stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE)
    time.sleep(0.2)
    p.kill()
    began = time.monotonic()
    p.communicate(timeout=20)
    assert time.monotonic() - began < 2


def test_s49_f3_a_tool_killed_by_a_signal_moves_neither_status_nor_stderr(box):
    _exe(box / "bin" / "agentik-session", "kill -TERM $$\n")
    r = _shim(box)
    assert (r.returncode, r.stderr) == (-15, "")


@pytest.mark.parametrize("event,code,out", [
    ("PreToolUse", 2, "{}\n"), ("PostToolUse", 2, "{}\n"), ("SessionStart", 2, "{}\n"),
    ("UserPromptSubmit", 2, "{}\n"), ("SessionEnd", 2, "{}\n"),
    ("Stop", 0, ""), ("StopFailure", 0, ""), ("PostToolUseFailure", 0, ""), ("PostToolBatch", 0, ""),
    ("PreCompact", 0, "{}\n")])
def test_s49_the_hooks_exit_and_stdout_do_not_move(box, event, code, out):
    r = _shim(box, event)
    assert (r.returncode, r.stdout) == (code, out)
    assert r.stderr == ("" if code == 0 and not out else "said\n")


def test_s49_stdin_still_reaches_the_tool(box):
    _exe(box / "bin" / "agentik-session", "cat\n")
    r = _shim(box, stdin='{"tool_input": "abc"}')
    assert (r.returncode, r.stdout) == (0, '{"tool_input": "abc"}')


def test_s49_the_variable_is_the_start_in_nanoseconds(box):
    _exe(box / "bin" / "agentik-session", f'cat >/dev/null; printf %s "${T0}"\n')
    before = time.time_ns()
    val = _shim(box).stdout
    assert len(val) == 19 and val.isdigit() and before <= int(val) <= time.time_ns()


def test_s49_no_date_on_path_is_an_empty_variable(box):
    _exe(box / "bin" / "agentik-session",
         f'printf "[%s]" "${T0}"; echo said >&2; exit 2\n')
    r = _shim(box, path=str(box / "bin"))
    assert (r.returncode, r.stdout, r.stderr) == (2, "[]", "said\n")


def test_s49_a_tool_of_the_old_shape_leaves_no_row_and_the_shim_writes_nothing(box):
    r = _shim(box)
    assert (r.returncode, r.stdout, r.stderr) == (2, "{}\n", "said\n")
    assert _rows(box) == []


def test_s49_no_tool_no_row_and_silent(box):
    (box / "bin" / "agentik-session").unlink()
    r = _shim(box, path="/usr/bin:/bin")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert _rows(box) == []


# ---- the CLI's row (Amendment 1)

def _bare(box, event="PreToolUse", stdin="{}", **kw):
    """The tool with no variable: what a hook does when nothing measures it."""
    return subprocess.run([str(box / "bin" / "agentik-session"), "hook", event], env=_env(box),
                          text=True, input=stdin, capture_output=True, timeout=30, **kw)


def _same(a, b):
    assert (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr)


def test_s49_a_call_appends_one_row_of_exactly_three_keys(real):
    assert _shim(real).returncode == 0
    _shim(real, "SessionStart")
    rows = _rows(real)
    assert [list(r) for r in rows] == [["event", "ms", "exit"]] * 2
    assert [(r["event"], r["exit"]) for r in rows] == [("PreToolUse", 0), ("SessionStart", 0)]
    assert all(type(r["ms"]) is int and r["ms"] >= 0 for r in rows)


@pytest.mark.parametrize("event", sorted(e for e in hooks.HANDLERS if e.isalpha()))
def test_s49_every_event_writes_its_row_and_moves_nothing(real, event):
    bare = _bare(real, event)
    assert _rows(real) == []
    r = _shim(real, event, stdin="{}")
    assert (r.stdout, r.stderr) == (bare.stdout if event not in SILENT_IN_SHIM else "",
                                    bare.stderr if event not in SILENT_IN_SHIM else "")
    assert [x["event"] for x in _rows(real)] == [event]


def test_s49_ms_is_the_tools_wall_time(real):
    tool = real / "bin" / "agentik-session"
    tool.write_text(tool.read_text().replace("exec", "sleep 0.3; exec", 1))
    _shim(real)
    ms = _rows(real)[0]["ms"]
    assert 290 <= ms < 5000, ms


@pytest.mark.parametrize("body,code", [
    ("return 7", 7), ("raise SystemExit(3)", 3), ("raise SystemExit", 0),
    ("raise SystemExit('words')", 1), ("raise RuntimeError('boom')", 1), ("return 0", 0)])
def test_s49_the_row_reads_the_processs_own_exit(real, body, code):
    _scripted(real, body)
    r = _shim(real)
    assert r.returncode == code
    assert _rows(real)[0]["exit"] == code


@pytest.mark.parametrize("event", ["Stop", "PreCompact"])
def test_s49_a_stops_real_code_is_in_the_row_though_the_shim_discards_it(real, event):
    _scripted(real, "return 3")
    assert _shim(real, event).returncode == 0
    assert _rows(real)[0]["exit"] == 3


def test_s49_a_code_the_status_cannot_hold_leaves_no_row(real):
    _scripted(real, "raise SystemExit(300)")
    assert _shim(real).returncode == 44
    assert _rows(real) == []


def test_s49_a_keyboard_interrupt_dies_by_the_signal_and_leaves_no_row(real):
    _scripted(real, "raise KeyboardInterrupt")
    assert _shim(real).returncode == -2
    assert _rows(real) == []


def test_s49_a_refusal_before_the_handler_leaves_no_row(real):
    r = _shim(real, "NotAnEvent")
    assert r.returncode == 2 and "invalid choice" in r.stderr
    assert _rows(real) == []


def test_s49_a_broken_stdout_exits_as_it_did_and_leaves_no_row(real):
    def run(argv, env):
        rd, wr = os.pipe()
        os.close(rd)
        try:
            return subprocess.run(argv, env=env, input='{"a": 1}', text=True, stdout=wr,
                                  stderr=subprocess.PIPE, timeout=30)
        finally:
            os.close(wr)
    bare = run([str(real / "bin" / "agentik-session"), "hook", "PreToolUse"], _env(real))
    r = run([str(SHIM), "PreToolUse"], _env(real))
    assert bare.returncode == r.returncode == 120
    assert r.stderr == bare.stderr
    assert _rows(real) == []


def test_s49_a_row_carries_no_path_prompt_or_tool_input(real):
    secret = {"cwd": "/secret/path", "prompt": "secret prompt", "tool_input": {"command": "secret"},
              "session_id": "secret-session", "transcript_path": "/secret/t.jsonl"}
    _shim(real, stdin=json.dumps(secret))
    raw = (real / "xdg" / config.APP / "hooks.jsonl").read_text()
    assert "secret" not in raw and str(real) not in raw


def test_s49_the_file_is_private_whatever_the_umask(real):
    subprocess.run(["/bin/sh", "-c", 'umask 022; exec "$0" PreToolUse', str(SHIM)],
                   env=_env(real), text=True, input="{}", capture_output=True)
    assert (real / "xdg" / config.APP / "hooks.jsonl").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("new,old", [(True, False), (False, True), (True, True)])
def test_s49_the_row_lands_in_the_state_root_config_picks(real, new, old):
    shutil.rmtree(real / "xdg")
    for made, app in ((new, config.APP), (old, config.OLD_APP)):
        if made:
            (real / "xdg" / app).mkdir(parents=True)
    _shim(real, "Stop")
    picked = config.state_dir(_env(real))
    assert list((real / "xdg").glob("*/hooks.jsonl")) == [picked / "hooks.jsonl"]


def test_s49_home_alone_picks_the_same_root(real):
    state = real / "home" / ".local" / "state" / config.APP
    state.mkdir(parents=True)
    env = {k: v for k, v in _env(real).items() if k != "XDG_STATE_HOME"}
    subprocess.run([str(SHIM), "Stop"], env=env, text=True, input="{}", capture_output=True)
    assert (state / "hooks.jsonl").exists()


def test_s49_lines_from_parallel_calls_stay_whole(real):
    ps = [subprocess.Popen([str(SHIM), "PostToolUse"], env=_env(real), text=True,
                           stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
          for _ in range(16)]
    for p in ps:
        p.communicate("{}")
    assert len(_rows(real)) == 16


# ---- nothing the writer meets moves the hook

def test_s49_no_state_directory_writes_nothing_and_makes_nothing(tmp_path, capfd):
    env = {"XDG_STATE_HOME": str(tmp_path / "gone"), "HOME": str(tmp_path)}
    assert harness.record_hook(str(time.time_ns()), "Stop", 0, env) is None
    assert not (tmp_path / "gone").exists()
    assert capfd.readouterr() == ("", "")


def _plant_file(real, how):
    p = real / "xdg" / config.APP / "hooks.jsonl"
    if how == "directory":
        p.mkdir()
    elif how == "unwritable":
        p.write_text("")
        p.chmod(0)
    elif how == "fifo":
        os.mkfifo(p)
    elif how == "dangling":
        p.symlink_to(real / "elsewhere")
    elif how == "link":
        (real / "elsewhere").write_text("kept\n")
        p.symlink_to(real / "elsewhere")


@pytest.mark.parametrize("how", ["directory", "unwritable", "fifo", "dangling", "link"])
@pytest.mark.skipif(os.geteuid() == 0, reason="root writes through 000")
def test_s49_a_file_that_is_not_a_regular_writable_file_writes_nothing(real, how):
    bare = _bare(real)
    _plant_file(real, how)
    p = real / "xdg" / config.APP / "hooks.jsonl"
    r = _shim(real, timeout=10)
    _same(r, bare)
    if how == "dangling":        # F4: the link's target is never made
        assert not (real / "elsewhere").exists() and p.is_symlink()
    if how == "link":
        assert (real / "elsewhere").read_text() == "kept\n"


@pytest.mark.parametrize("t0", [None, "", "1793461283", "1793461283N", "not-a-number",
                                "1" * 18, "1" * 20, "١" * 19, "1" * 18 + "\n",
                                "9" * 19])
def test_s49_a_start_that_is_not_19_digits_or_is_ahead_writes_nothing(tmp_path, t0):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    harness.record_hook(t0, "Stop", 0, env)
    assert list((tmp_path / config.APP).iterdir()) == []


@pytest.mark.parametrize("stamp", ["1793461283N", "1793461283", "not-a-number", ""])
def test_s49_a_date_without_nanoseconds_leaves_no_row_and_moves_nothing(real, stamp):
    bare = _bare(real)
    _exe(real / "bin" / "date", f"echo '{stamp}'\n")
    _same(_shim(real), bare)
    assert _rows(real) == []


def test_s49_no_date_on_path_leaves_no_row(real):
    bare = _bare(real)
    _same(_shim(real, path=str(real / "bin")), bare)
    assert _rows(real) == []


@pytest.mark.parametrize("event", ['Pre"ToolUse', "Pre Tool", "../../x", "", None, 7])
def test_s49_an_event_that_is_not_letters_writes_nothing(tmp_path, event):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    harness.record_hook(str(time.time_ns()), event, 0, env)
    assert list((tmp_path / config.APP).iterdir()) == []


@pytest.mark.parametrize("code", [None, -1, 256, "0", 1.0, True])
def test_s49_a_code_that_is_no_exit_status_writes_nothing(tmp_path, code):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    harness.record_hook(str(time.time_ns()), "Stop", code, env)
    assert list((tmp_path / config.APP).iterdir()) == []


@pytest.mark.parametrize("name", ["open", "write", "fstat"])
def test_s49_a_writer_that_breaks_never_raises(tmp_path, monkeypatch, capfd, name):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    def boom(*_a, **_k):
        raise OSError("nope")
    with monkeypatch.context() as m:
        m.setattr(os, name, boom)
        assert harness.record_hook(str(time.time_ns()), "Stop", 0, env) is None
    assert capfd.readouterr() == ("", "")


def test_s49_a_stdout_that_will_not_flush_writes_no_row(tmp_path, monkeypatch):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    class Broken:
        def flush(self):
            raise BrokenPipeError
    with monkeypatch.context() as m:
        m.setattr(sys, "stdout", Broken())
        harness.record_hook(str(time.time_ns()), "Stop", 0, env)
    assert list((tmp_path / config.APP).iterdir()) == []


def test_s49_no_stdout_at_all_still_writes(tmp_path, monkeypatch):
    env = {"XDG_STATE_HOME": str(tmp_path), "HOME": str(tmp_path)}
    (tmp_path / config.APP).mkdir()
    with monkeypatch.context() as m:
        m.setattr(sys, "stdout", None)
        harness.record_hook(str(time.time_ns()), "Stop", 0, env)
    assert (tmp_path / config.APP / "hooks.jsonl").exists()


@pytest.mark.parametrize("code,want", [(None, 0), (0, 0), (3, 3), (True, 1), ("words", 1), (300, 300)])
def test_s49_exit_status_is_pythons_mapping(code, want):
    assert harness.exit_status(code) == want


# ---- the variable dies with the call

def test_s49_the_hook_pops_the_variable_before_it_runs(monkeypatch):
    monkeypatch.setenv(T0, str(time.time_ns()))
    seen = {}
    def spy(_event):
        seen["env"] = os.environ.get(T0)
        seen["child"] = subprocess.run(["/usr/bin/env"], capture_output=True, text=True).stdout
        return 0
    monkeypatch.setattr(hooks, "dispatch", spy)
    assert cli.main(["hook", "Stop"]) == 0
    assert seen["env"] is None and T0 not in seen["child"]
    assert len(harness.read_hooks(config.state_dir(os.environ))) == 1


def test_s49_a_child_on_the_real_hook_path_does_not_inherit_it(real):
    log = real / "git-env"
    _exe(real / "bin" / "git", f"/usr/bin/env >> '{log}'; exit 1\n")
    state = real / "xdg" / config.APP
    resolver.session_dir(state, SID).mkdir(parents=True, exist_ok=True)
    cwd = real / "work"
    cwd.mkdir()
    payload = {"session_id": SID, "transcript_path": str(FIX / "at-80.jsonl"), "reason": "clear",
               "cwd": str(cwd)}
    assert _shim(real, "SessionEnd", stdin=json.dumps(payload)).returncode == 0
    assert log.exists() and T0 not in log.read_text()
    assert [r["event"] for r in _rows(real)] == ["SessionEnd"]
    assert len(ledger.read(state)) == 1


def test_s49_a_nested_hook_call_writes_no_row_of_its_own(real):
    _scripted(real, 'import subprocess\n    subprocess.run(["agentik-session-real", "hook", "Stop"], '
                    'input="{}", text=True, capture_output=True)\n    return 0')
    _exe(real / "bin" / "agentik-session-real",
         f'PYTHONPATH="{ROOT}" exec "{sys.executable}" -B -m claude_session.cli "$@"\n')
    _shim(real)
    assert [r["event"] for r in _rows(real)] == ["PreToolUse"]


def test_s49_no_other_verb_reads_the_variable(monkeypatch, capsys):
    state = _plant({**OLD_ROW, "claude_md_bytes": 100})
    monkeypatch.setenv(T0, str(time.time_ns()))
    assert cli.main(["report", "--hooks"]) == 0
    assert harness.read_hooks(state) == [] and os.environ.get(T0)


# ---- the bound

def test_s49_rotate_under_the_cap_leaves_the_file(tmp_path):
    (tmp_path / "hooks.jsonl").write_text("x\n")
    harness.rotate(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hooks.jsonl"]


def test_s49_rotate_at_the_cap_keeps_one_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "HOOKS_CAP", 4)
    (tmp_path / "hooks.jsonl").write_text("new1\n")
    (tmp_path / "hooks.jsonl.1").write_text("old\n")
    harness.rotate(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hooks.jsonl.1"]
    assert (tmp_path / "hooks.jsonl.1").read_text() == "new1\n"


def test_s49_rotate_with_nothing_there_is_silent(tmp_path):
    harness.rotate(tmp_path)
    harness.rotate(tmp_path / "gone")
    assert list(tmp_path.iterdir()) == []


def test_s49_the_two_generations_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "HOOKS_CAP", 256)
    line = '{"event":"PreToolUse","ms":90,"exit":0}\n'
    for _ in range(500):
        harness.rotate(tmp_path)
        with open(tmp_path / "hooks.jsonl", "a") as f:
            f.write(line)
    sizes = [p.stat().st_size for p in tmp_path.iterdir()]
    assert len(sizes) == 2 and all(s <= 256 + len(line) for s in sizes), sizes


def test_s49_the_default_cap_is_a_mebibyte():
    assert harness.HOOKS == "hooks.jsonl" and harness.HOOKS_CAP == 1048576


@pytest.mark.parametrize("event", ["Stop", "PreToolUse"])
def test_s49_a_hook_call_rotates(monkeypatch, event):
    state = config.state_dir(os.environ)
    state.mkdir(parents=True, exist_ok=True)
    (state / "hooks.jsonl").write_bytes(b"x" * harness.HOOKS_CAP)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert hooks.dispatch(event) == 0
    assert not (state / "hooks.jsonl").exists() and (state / "hooks.jsonl.1").exists()


def test_s49_a_rotation_that_breaks_never_fails_the_hook(monkeypatch, capsys):
    def boom(_):
        raise OSError("nope")
    monkeypatch.setattr(harness, "rotate", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert hooks.dispatch("PreToolUse") == 0
    assert json.loads(capsys.readouterr().out) == {}


# ---- claude_md_bytes

@pytest.fixture
def tree(tmp_path):
    """A home with a user file, and a project under it with no CLAUDE.md yet."""
    home = tmp_path / "h"
    (home / ".claude").mkdir(parents=True)
    (tmp_path / "h" / "repo" / "sub").mkdir(parents=True)
    return home


def _md(tree, *cwd):
    return harness.claude_md_bytes(str(tree.joinpath(*(cwd or ("repo",)))), {"HOME": str(tree)})


def test_s49_nothing_there_is_zero(tree):
    assert _md(tree) == 0


def test_s49_the_user_project_ancestors_local_and_dot_claude_each_count(tree):
    (tree / ".claude" / "CLAUDE.md").write_text("u" * 3)
    (tree / "repo" / "CLAUDE.md").write_text("p" * 5)
    (tree / "repo" / ".claude").mkdir()
    (tree / "repo" / ".claude" / "CLAUDE.md").write_text("d" * 7)
    (tree / "repo" / "CLAUDE.local.md").write_text("l" * 11)
    (tree / "repo" / "sub" / "CLAUDE.md").write_text("s" * 13)
    assert _md(tree, "repo") == 3 + 5 + 7 + 11
    assert _md(tree, "repo", "sub") == 3 + 5 + 7 + 11 + 13


def test_s49_a_deeper_file_a_rules_dir_and_memory_are_not_counted(tree):
    (tree / "repo" / "sub" / "CLAUDE.md").write_text("s" * 13)
    (tree / "repo" / ".claude" / "rules").mkdir(parents=True)
    (tree / "repo" / ".claude" / "rules" / "a.md").write_text("r" * 17)
    (tree / ".claude" / "MEMORY.md").write_text("m" * 19)
    assert _md(tree) == 0


def test_s49_config_dir_replaces_dot_claude(tree):
    (tree / ".claude" / "CLAUDE.md").write_text("u" * 3)
    moved = tree / "moved"
    moved.mkdir()
    (moved / "CLAUDE.md").write_text("c" * 5)
    env = {"HOME": str(tree), "CLAUDE_CONFIG_DIR": str(moved)}
    # ~/.claude/CLAUDE.md still loads as the home directory's project file, so 3 stays
    assert harness.claude_md_bytes(str(tree / "repo"), env) == 3 + 5
    outside = tree.parent / "elsewhere"
    outside.mkdir()
    assert harness.claude_md_bytes(str(outside), env) == 5


def test_s49_a_symlink_counts_once(tree):
    (tree / "repo" / "CLAUDE.md").write_text("p" * 5)
    (tree / "repo" / "CLAUDE.local.md").symlink_to(tree / "repo" / "CLAUDE.md")
    assert _md(tree) == 5


def test_s49_imports_relative_home_absolute_and_chained(tree, tmp_path):
    (tree / "repo" / "docs").mkdir()
    (tree / "repo" / "docs" / "a.md").write_text("chain @b.md\n")       # 12, relative to itself
    (tree / "repo" / "docs" / "b.md").write_text("b" * 2)
    (tree / "h.md").write_text("h" * 3)
    (tmp_path / "abs.md").write_text("a" * 4)
    head = f"see @docs/a.md and @~/h.md\n@{tmp_path}/abs.md\n"
    (tree / "repo" / "CLAUDE.md").write_text(head)
    assert _md(tree) == len(head) + 12 + 2 + 3 + 4


def test_s49_an_import_cycle_counts_once(tree):
    (tree / "repo" / "CLAUDE.md").write_text("@a.md\n")
    (tree / "repo" / "a.md").write_text("@CLAUDE.md @a.md\n")
    assert _md(tree) == 6 + 17


def test_s49_imports_stop_at_five_hops(tree):
    for i in range(1, 7):
        (tree / "repo" / f"{i}.md").write_text(f"@{i + 1}.md\n")
    (tree / "repo" / "CLAUDE.md").write_text("@1.md\n")
    assert _md(tree) == 6 * 6                       # the file, then hops 1 to 5; 6.md is not read


def test_s49_a_code_span_a_fence_an_email_and_a_missing_file_import_nothing(tree):
    (tree / "repo" / "no.md").write_text("n" * 1000)
    body = "\n".join(["`@no.md`", "```", "@no.md", "```", "someone" + "@" + "no.md", "@gone.md", "@name", "@.", ""])
    (tree / "repo" / "CLAUDE.md").write_text(body)
    assert _md(tree) == len(body)


def test_s49_a_fifo_import_is_skipped_and_never_hangs(tree):
    os.mkfifo(tree / "repo" / "pipe")
    (tree / "repo" / "CLAUDE.md").write_text("@pipe\n")
    assert _md(tree) == 6


def test_s49_a_file_past_the_read_cap_counts_and_is_not_scanned(tree, monkeypatch):
    monkeypatch.setattr(harness, "MD_READ_CAP", 8)
    (tree / "repo" / "no.md").write_text("n" * 5)
    (tree / "repo" / "CLAUDE.md").write_text("@no.md and more\n")
    assert _md(tree) == 16


def test_s49_the_file_count_is_capped(tree, monkeypatch):
    monkeypatch.setattr(harness, "MD_MAX_FILES", 2)
    for i in range(4):
        (tree / "repo" / f"{i}.md").write_text("x")
    (tree / "repo" / "CLAUDE.md").write_text("@0.md @1.md @2.md @3.md\n")
    assert _md(tree) == 24 + 1


@pytest.mark.parametrize("cwd", [None, "", 7, "relative/path", "/no/such/dir/at/all"])
def test_s49_no_usable_cwd_is_null(tree, cwd):
    assert harness.claude_md_bytes(cwd, {"HOME": str(tree)}) is None


def test_s49_a_broken_walk_is_null_never_a_raise(tree, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("nope")
    monkeypatch.setattr(harness, "_walk", boom)
    assert _md(tree) is None


# ---- the row

@pytest.fixture
def ended(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    config.ensure_dirs()
    env = dict(os.environ)
    sdir = resolver.session_dir(resolver.state_dir(env), SID)
    sdir.mkdir(parents=True, exist_ok=True)
    return env, sdir


LIMITS = [{"kind": "seven_day", "percentUsed": 41.0, "resetsAt": "2026-11-04T15:00:00Z"}]


def _end(env, cwd):
    hooks.session_end({"session_id": SID, "transcript_path": str(FIX / "at-80.jsonl"),
                       "reason": "clear", "cwd": str(cwd)}, env)
    return ledger.read(resolver.state_dir(env))


def test_s49_session_end_writes_both_keys(ended, tmp_path):
    env, sdir = ended
    (tmp_path / "CLAUDE.md").write_text("x" * 21)
    (sdir / measure.MEASURE).write_text(json.dumps({"at": "t", "context": None, "rateLimits": LIMITS}))
    row = _end(env, tmp_path)[0]
    assert row["rate_limits"] == LIMITS and row["rate_limits_at"] is None
    assert row["claude_md_bytes"] == 21 + 0 and list(row) == list(ledger.LEDGER_KEYS)


def test_s49_no_measure_is_a_null_rate_limits_and_the_row_stands(ended, tmp_path):
    env, _ = ended
    row = _end(env, tmp_path)[0]
    assert (row["rate_limits"], row["rate_limits_at"], row["turns"]) == (None, None, 4)


@pytest.mark.parametrize("bad", ["not a list", [{"kind": "x", "percentUsed": "many"}],
                                 [{"kind": "x", "percentUsed": 1, "prompt": "words"}]])
def test_s49_a_measure_the_shape_refuses_never_reaches_the_row(ended, tmp_path, bad):
    env, sdir = ended
    (sdir / measure.MEASURE).write_text(json.dumps({"rateLimits": bad}))
    row = _end(env, tmp_path)[0]
    assert row["rate_limits"] is None and row["turns"] == 4


def test_s49_a_torn_measure_is_null(ended, tmp_path):
    env, sdir = ended
    (sdir / measure.MEASURE).write_text('{"rateLimits": [')
    assert _end(env, tmp_path)[0]["rate_limits"] is None


def test_s49_a_failure_in_either_measure_never_loses_the_row(ended, tmp_path, monkeypatch):
    env, _ = ended
    def boom(*_a, **_k):
        raise RuntimeError("nope")
    monkeypatch.setattr(harness, "claude_md_bytes", boom)
    monkeypatch.setattr(measure, "stated_limits", boom)
    row = _end(env, tmp_path)[0]
    assert (row["claude_md_bytes"], row["rate_limits"], row["rate_limits_at"], row["turns"]) == (
        None, None, None, 4)


def test_s49_a_subagents_end_writes_no_row(ended, tmp_path):
    env, _ = ended
    hooks.session_end({"session_id": SID, "agent_id": "a", "cwd": str(tmp_path),
                       "transcript_path": str(FIX / "at-80.jsonl")}, env)
    assert ledger.read(resolver.state_dir(env)) == []


def test_s49_the_row_is_still_closed_to_other_keys(tmp_path):
    with pytest.raises(ledger.LedgerError):
        ledger.append(tmp_path, {"session": "s", "prompt": "hello"})


OLD_ROW = {"session": "old-sess-1", "project": "p", "repo": "/r", "turns": 3, "sidechain_turns": 0,
           "tokens": 9, "median_context": 1, "max_context": 2, "profile": "builder", "model": "m",
           "sha_at_end": "abc", "dirty": False, "started": "2026-10-01T00:00:00+00:00",
           "ended": "2026-10-01T01:00:00+00:00", "ceilings": None, "zone_at_end": "clear",
           "exit_reason": "other", "builders": [], "builders_source": "none"}


def _plant(*rows):
    state = config.state_dir(os.environ)
    state.mkdir(parents=True, exist_ok=True)
    with open(state / ledger.LEDGER, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return state


def test_s49_an_old_row_reads_as_before(capsys):
    _plant(OLD_ROW)
    state = config.state_dir(os.environ)
    assert ledger.read(state) == [OLD_ROW]
    before = ledger.table([OLD_ROW])
    assert before == ledger.table([{**OLD_ROW, "claude_md_bytes": 9, "rate_limits": LIMITS}])
    assert cli.main(["report"]) == 0
    assert before in capsys.readouterr().out
    assert cli.main(["report", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [OLD_ROW]


def test_s49_entry_for_takes_the_keys_and_defaults_them_null(tmp_path):
    m = meter.parse(FIX / "at-80.jsonl").as_dict()
    plain = ledger.entry_for(m, project="p", profile="f", cwd=tmp_path, exit_reason="x")
    assert plain["claude_md_bytes"] is None and plain["rate_limits"] is None
    full = ledger.entry_for(m, project="p", profile="f", cwd=tmp_path, exit_reason="x",
                            claude_md_bytes=5, rate_limits=LIMITS)
    assert (full["claude_md_bytes"], full["rate_limits"]) == (5, LIMITS)


# ---- the reader

def _hooks(state, *rows, name="hooks.jsonl"):
    state.mkdir(parents=True, exist_ok=True)
    with open(state / name, "a") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


def _row(event, ms, code=0):
    return {"event": event, "ms": ms, "exit": code}


def test_s49_stats_are_nearest_rank_per_event():
    rows = [_row("A", ms) for ms in range(1, 101)] + [_row("B", 7, 2)]
    s = harness.hook_stats(rows)
    assert s["A"] == {"count": 100, "p50": 50, "p95": 95, "nonzero": 0}
    assert s["B"] == {"count": 1, "p50": 7, "p95": 7, "nonzero": 1}


def test_s49_read_takes_both_generations_and_skips_what_is_not_a_row(tmp_path):
    _hooks(tmp_path, _row("A", 1), name="hooks.jsonl.1")
    _hooks(tmp_path, _row("A", 2), "torn{", '"a string"', {"event": "A"}, {"event": 1, "ms": 2, "exit": 0},
           {"event": "A", "ms": True, "exit": 0}, {"event": "A", "ms": -1, "exit": 0},
           {"event": "A", "ms": 3, "exit": None})
    assert harness.read_hooks(tmp_path) == [_row("A", 1), _row("A", 2)]


def test_s49_read_with_no_file_is_empty(tmp_path):
    assert harness.read_hooks(tmp_path / "gone") == []


def test_s49_report_hooks_prints_the_table_and_the_bytes(capsys):
    state = _plant({**OLD_ROW, "ended": "2026-10-02T00:00:00+00:00", "claude_md_bytes": 100},
                   OLD_ROW,
                   {**OLD_ROW, "ended": "2026-10-03T00:00:00+00:00", "session": "new-sess-2",
                    "claude_md_bytes": 300})
    _hooks(state, _row("PreToolUse", 90), _row("PreToolUse", 110, 2), _row("Stop", 80))
    assert cli.main(["report", "--hooks"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["event", "count", "p50_ms", "p95_ms", "nonzero"]
    assert out[1].split() == ["PreToolUse", "2", "90", "110", "1"]
    assert out[2].split() == ["Stop", "1", "80", "80", "0"]
    assert out[-1] == "claude_md_bytes: newest 300 (new-sess), p50 100, max 300, 2 rows"


def test_s49_report_hooks_json(capsys):
    state = _plant({**OLD_ROW, "claude_md_bytes": 100})
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["events"] == {"Stop": {"count": 1, "p50": 80, "p95": 80, "nonzero": 0}}
    assert doc["claude_md_bytes"] == {"newest": 100, "session": OLD_ROW["session"],
                                      "p50": 100, "max": 100, "rows": 1}


def test_s49_since_filters_the_rows_and_never_the_hooks(capsys):
    state = _plant({**OLD_ROW, "claude_md_bytes": 100},
                   {**OLD_ROW, "ended": "2026-10-20T00:00:00+00:00", "claude_md_bytes": 300})
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks", "--since", "2026-10-10"]) == 0
    out = capsys.readouterr().out
    assert "Stop" in out and "newest 300" in out and "1 rows" in out


def test_s49_report_hooks_on_old_rows_alone_says_so(capsys):
    state = _plant(OLD_ROW)
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "claude_md_bytes: no row carries it"


def test_s49_report_hooks_with_rows_and_no_hooks_file(capsys):
    _plant({**OLD_ROW, "claude_md_bytes": 100})
    assert cli.main(["report", "--hooks"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("hooks.jsonl: no rows") and "newest 100" in out


def test_s49_report_hooks_with_nothing_exits_2(capsys):
    assert cli.main(["report", "--hooks"]) == 2
    assert "no hook rows" in capsys.readouterr().err


def test_s49_a_torn_ledger_and_a_bad_byte_count_never_break_the_line():
    assert harness.claude_md_line([{"claude_md_bytes": "many"}, {"claude_md_bytes": True},
                                   {"claude_md_bytes": None}, {}]) == "claude_md_bytes: no row carries it"


# ---- the texts

@pytest.mark.parametrize("name", ["README.md", "design/readme/source.md"])
def test_s49_the_readme_says_only_this_plugins_hooks_are_measured(name):
    text = (ROOT / name).read_text()
    assert "report --hooks" in text and "hooks.jsonl" in text and "claude_md_bytes" in text
    assert "only this plugin's hooks" in text.lower()


def test_s49_the_command_names_the_flag():
    assert "--hooks" in (ROOT / "plugin" / "commands" / "report.md").read_text()


def test_s49_an_import_that_is_not_text_does_not_count(tree):
    (tree / "repo" / "logo.png").write_bytes(b"\x89PNG\0\0\0")
    (tree / "repo" / "CLAUDE.md").write_text("@logo.png\n")
    assert _md(tree) == 10


def test_s49_a_rotation_starts_a_new_private_file(real):
    p = real / "xdg" / config.APP / "hooks.jsonl"
    _shim(real, "Stop")
    harness.HOOKS_CAP, cap = 1, harness.HOOKS_CAP
    try:
        harness.rotate(p.parent)
    finally:
        harness.HOOKS_CAP = cap
    _shim(real, "Stop")
    assert len(harness.read_hooks(p.parent)) == 2 and (p.parent / "hooks.jsonl.1").exists()
    assert p.stat().st_mode & 0o777 == 0o600


# ---- Amendment 1: F4 to F7, the reading's time, the design line

def test_s49_f4_rotate_never_takes_a_link_or_a_fifo(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "HOOKS_CAP", 4)
    big = tmp_path / "big"
    big.write_text("x" * 40)
    state = tmp_path / "state"
    state.mkdir()
    (state / "hooks.jsonl").symlink_to(big)
    harness.rotate(state)
    assert sorted(p.name for p in state.iterdir()) == ["hooks.jsonl"]
    (state / "hooks.jsonl").unlink()
    (state / "hooks.jsonl").symlink_to(state / "gone")
    harness.rotate(state)
    assert not (state / "gone").exists()


def _since_rows():
    return _plant({**OLD_ROW, "claude_md_bytes": 100},
                  {**OLD_ROW, "ended": "2026-10-20T00:00:00+00:00"})


def test_s49_f5_since_says_the_table_is_unfiltered_and_the_ledger_is_filtered(capsys):
    state = _plant({**OLD_ROW, "claude_md_bytes": 100},
                   {**OLD_ROW, "ended": "2026-10-20T00:00:00+00:00", "claude_md_bytes": 300})
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks", "--since", "2026-10-10"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-2] == ("hook rows: all of them, unfiltered; a hook row has no time, so --since "
                       "filters the ledger only")
    assert out[-1] == "claude_md_bytes since 2026-10-10: newest 300 (old-sess), p50 300, max 300, 1 rows"


def test_s49_f5_no_since_says_nothing_of_a_filter(capsys):
    state = _plant({**OLD_ROW, "claude_md_bytes": 100})
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks"]) == 0
    assert "unfiltered" not in capsys.readouterr().out


def test_s49_f5_no_row_in_the_period_is_not_no_row_carrying_it(capsys):
    state = _since_rows()
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks", "--since", "2027-01-01"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "claude_md_bytes: no ledger row since 2027-01-01"
    assert cli.main(["report", "--hooks", "--since", "2026-10-10"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "claude_md_bytes: no row since 2026-10-10 carries it, of 1"


def test_s49_f5_an_empty_ledger_is_not_no_row_carrying_it(capsys):
    _hooks(config.state_dir(os.environ), _row("Stop", 80))
    assert cli.main(["report", "--hooks"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "claude_md_bytes: no ledger row"


def test_s49_f5_json_says_the_same(capsys):
    state = _since_rows()
    _hooks(state, _row("Stop", 80))
    assert cli.main(["report", "--hooks", "--json", "--since", "2027-01-01"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["since"], doc["events_filtered"], doc["ledger_rows"], doc["claude_md_bytes"]) == (
        "2027-01-01", False, 0, None)
    assert doc["events"]["Stop"]["count"] == 1


def test_s49_f5_nothing_with_since_says_which_nothing(capsys):
    assert cli.main(["report", "--hooks", "--since", "2027-01-01"]) == 2
    assert "no ledger row since 2027-01-01" in capsys.readouterr().err


@pytest.mark.parametrize("word", [b"@zz ", None])
def test_s49_f6_three_files_of_imports_end_far_inside_the_timeout(tree, word):
    for name in ("CLAUDE.md", "CLAUDE.local.md"):
        body = word * 262144 if word else b" ".join(b"@z%d" % i for i in range(150000))
        (tree / "repo" / name).write_bytes(body)
    (tree / "CLAUDE.md").write_bytes(word * 262144 if word else b"@y " * 262144)
    began = time.monotonic()
    n = _md(tree)
    took = time.monotonic() - began
    assert n is not None and n >= 3 * 1000000 or word is None
    assert took < 3, took


def test_s49_f6_a_scan_past_its_budget_ends_far_inside_the_timeout(tree):
    # 64 files of bare newlines and lone @s: the slowest text for the scan, line by line.
    names = [f"f{i}.md" for i in range(63)]
    (tree / "repo" / "CLAUDE.md").write_text(" ".join("@" + n for n in names) + "\n")
    for n in names:
        (tree / "repo" / n).write_bytes(b"@\n" * 524287)
    began = time.monotonic()
    n = _md(tree)
    assert time.monotonic() - began < 6
    assert n >= 63 * 1048574


def test_s49_f6_the_queue_is_capped(tree, monkeypatch):
    monkeypatch.setattr(harness, "MD_MAX_QUEUE", 8)
    for i in range(40):
        (tree / "repo" / f"{i}.md").write_text("x")
    (tree / "repo" / "CLAUDE.md").write_text(" ".join(f"@{i}.md" for i in range(40)) + "\n")
    base = len((tree / "repo" / "CLAUDE.md").read_text())
    n = _md(tree)
    assert base <= n < base + 8


def test_s49_f6_a_scan_cap_counts_by_size_and_does_not_scan(tree, monkeypatch):
    monkeypatch.setattr(harness, "MD_SCAN_CAP", 4)
    (tree / "repo" / "no.md").write_text("n" * 5)
    (tree / "repo" / "CLAUDE.md").write_text("@no.md and more\n")
    assert _md(tree) == 16


def test_s49_f6_each_path_is_queued_once_and_a_shallow_import_still_scans(tree):
    (tree / "repo" / "a.md").write_text("@b.md\n")
    (tree / "repo" / "b.md").write_text("b")
    (tree / "repo" / "CLAUDE.md").write_text("@a.md @a.md @b.md @a.md\n")
    assert _md(tree) == 24 + 6 + 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads through 000")
def test_s49_f6_a_denied_import_is_left_out_and_the_rest_counts(tree):
    (tree / "repo" / "no.md").write_text("n" * 5)
    (tree / "repo" / "no.md").chmod(0)
    (tree / "repo" / "yes.md").write_text("y" * 3)
    (tree / "repo" / "CLAUDE.md").write_text("@no.md @yes.md\n")
    assert _md(tree) == 15 + 3


def test_s49_f7_read_hooks_never_blocks_on_a_fifo_and_never_follows_a_link(tmp_path):
    os.mkfifo(tmp_path / "hooks.jsonl.1")
    (tmp_path / "real").write_text(json.dumps(_row("Stop", 1)) + "\n")
    (tmp_path / "hooks.jsonl").symlink_to(tmp_path / "real")
    code = ("import sys; from claude_session import harness; "
            f"sys.exit(len(harness.read_hooks({str(tmp_path)!r})))")
    r = subprocess.run([sys.executable, "-B", "-c", code], env={"PYTHONPATH": str(ROOT)}, timeout=10)
    assert r.returncode == 0


def test_s49_f7_a_line_too_deep_to_parse_is_skipped(tmp_path):
    _hooks(tmp_path, "[" * 400000, _row("Stop", 5), '{"a":' * 200000)
    assert harness.read_hooks(tmp_path) == [_row("Stop", 5)]


def test_s49_the_row_keeps_when_the_reading_was_taken(ended, tmp_path):
    env, sdir = ended
    (sdir / measure.MEASURE).write_text(json.dumps(
        {"at": "2020-01-02T03:04:05+00:00", "context": None, "rateLimits": LIMITS}))
    row = _end(env, tmp_path)[0]
    assert row["rate_limits"] == LIMITS and row["rate_limits_at"] == "2020-01-02T03:04:05+00:00"


@pytest.mark.parametrize("at", ["t", 7, None, "2020-01-02T03:04:05"])
def test_s49_an_at_that_is_no_time_is_null_and_the_limits_stand(ended, tmp_path, at):
    env, sdir = ended
    (sdir / measure.MEASURE).write_text(json.dumps({"at": at, "rateLimits": LIMITS}))
    row = _end(env, tmp_path)[0]
    assert row["rate_limits"] == LIMITS and row["rate_limits_at"] is None


def test_s49_no_limits_is_no_at(ended, tmp_path):
    env, sdir = ended
    (sdir / measure.MEASURE).write_text(json.dumps({"at": "2020-01-02T03:04:05+00:00", "context": None}))
    row = _end(env, tmp_path)[0]
    assert (row["rate_limits"], row["rate_limits_at"]) == (None, None)


def test_s49_mod_r1_says_session_end_copies_the_measure():
    lines = (ROOT / "design" / "mod-r1.md").read_text().splitlines()
    at = next(i for i, ln in enumerate(lines) if ln.startswith("3. A pytest proves `chain.py`"))
    near = " ".join(lines[at + 1:at + 3])
    assert "S49" in near and "SessionEnd" in near and "harness" in near and "decides nothing" in near
