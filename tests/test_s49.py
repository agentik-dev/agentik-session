"""Packet S49: the shim's row, its bound, the row's two new keys, and `report --hooks`."""

import io
import json
import os
import subprocess
import sys
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


def _env(box, path=None):
    return {"PATH": path or f"{box / 'bin'}:/usr/bin:/bin", "HOME": str(box / "home"),
            "XDG_STATE_HOME": str(box / "xdg")}


def _shim(box, event="PreToolUse", path=None, stdin='{"session_id": "s"}', timeout=20):
    return subprocess.run([str(SHIM), event], env=_env(box, path), text=True, input=stdin,
                          capture_output=True, timeout=timeout)


def _rows(box, app=config.APP):
    p = box / "xdg" / app / "hooks.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# ---- the shim's row

def test_s49_a_call_appends_one_row_of_exactly_three_keys(box):
    assert _shim(box).returncode == 2
    _shim(box, "SessionStart")
    rows = _rows(box)
    assert [list(r) for r in rows] == [["event", "ms", "exit"]] * 2
    assert [(r["event"], r["exit"]) for r in rows] == [("PreToolUse", 2), ("SessionStart", 2)]
    assert all(type(r["ms"]) is int and r["ms"] >= 0 for r in rows)


def test_s49_ms_is_the_tools_wall_time(box):
    _exe(box / "bin" / "agentik-session", "cat >/dev/null; sleep 0.3\n")
    _shim(box)
    ms = _rows(box)[0]["ms"]
    assert 290 <= ms < 5000, ms


@pytest.mark.parametrize("event,code,out", [
    ("PreToolUse", 2, "{}\n"), ("PostToolUse", 2, "{}\n"), ("SessionStart", 2, "{}\n"),
    ("UserPromptSubmit", 2, "{}\n"), ("SessionEnd", 2, "{}\n"),
    ("Stop", 0, ""), ("StopFailure", 0, ""), ("PostToolUseFailure", 0, ""), ("PostToolBatch", 0, ""),
    ("PreCompact", 0, "{}\n")])
def test_s49_the_hooks_exit_and_stdout_do_not_move_and_the_row_keeps_the_tools(box, event, code, out):
    r = _shim(box, event)
    assert (r.returncode, r.stdout) == (code, out)
    assert r.stderr == ("" if code == 0 and not out else "said\n")
    assert _rows(box)[0]["exit"] == 2


def test_s49_stdin_still_reaches_the_tool(box):
    _exe(box / "bin" / "agentik-session", "cat\n")
    r = _shim(box, stdin='{"tool_input": "abc"}')
    assert (r.returncode, r.stdout) == (0, '{"tool_input": "abc"}')


def test_s49_a_row_carries_no_path_prompt_or_tool_input(box):
    secret = {"cwd": "/secret/path", "prompt": "secret prompt", "tool_input": {"command": "secret"},
              "session_id": "secret-session", "transcript_path": "/secret/t.jsonl"}
    _shim(box, stdin=json.dumps(secret))
    raw = (box / "xdg" / config.APP / "hooks.jsonl").read_text()
    assert "secret" not in raw and str(box) not in raw


def test_s49_the_file_is_private_and_the_tool_keeps_its_umask(box):
    _exe(box / "bin" / "agentik-session", "cat >/dev/null; umask\n")
    r = subprocess.run(["/bin/sh", "-c", 'umask 022; exec "$0" PreToolUse', str(SHIM)],
                       env=_env(box), text=True, input="{}", capture_output=True)
    assert r.stdout.strip() == "0022"
    assert (box / "xdg" / config.APP / "hooks.jsonl").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("new,old", [(True, False), (False, True), (True, True)])
def test_s49_the_shim_picks_the_state_root_config_picks(box, new, old):
    import shutil
    shutil.rmtree(box / "xdg")
    for made, app in ((new, config.APP), (old, config.OLD_APP)):
        if made:
            (box / "xdg" / app).mkdir(parents=True)
    _shim(box)
    picked = config.state_dir(_env(box))
    assert (picked / "hooks.jsonl").exists()
    assert list((box / "xdg").glob("*/hooks.jsonl")) == [picked / "hooks.jsonl"]


def test_s49_home_alone_picks_the_same_root(box):
    state = box / "home" / ".local" / "state" / config.APP
    state.mkdir(parents=True)
    env = {k: v for k, v in _env(box).items() if k != "XDG_STATE_HOME"}
    subprocess.run([str(SHIM), "Stop"], env=env, text=True, input="{}", capture_output=True)
    assert config.state_dir(env) / "hooks.jsonl" == state / "hooks.jsonl"
    assert (state / "hooks.jsonl").exists()


def test_s49_lines_from_parallel_calls_stay_whole(box):
    ps = [subprocess.Popen([str(SHIM), "PostToolUse"], env=_env(box), text=True,
                           stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
          for _ in range(24)]
    for p in ps:
        p.communicate("{}")
    assert len(_rows(box)) == 24


def test_s49_no_tool_no_row_and_silent(box):
    (box / "bin" / "agentik-session").unlink()
    r = _shim(box, path="/usr/bin:/bin")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert _rows(box) == []


def _control(box, r):
    """The tool's outcome stands whole: the failure that was planted cost nothing."""
    assert (r.returncode, r.stdout, r.stderr) == (2, "{}\n", "said\n")


def test_s49_no_state_directory_writes_nothing_and_makes_nothing(box):
    import shutil
    shutil.rmtree(box / "xdg")
    _control(box, _shim(box))
    assert not (box / "xdg").exists()


def test_s49_a_directory_where_the_file_goes(box):
    (box / "xdg" / config.APP / "hooks.jsonl").mkdir()
    _control(box, _shim(box))


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes through 000")
def test_s49_an_unwritable_file(box):
    p = box / "xdg" / config.APP / "hooks.jsonl"
    p.write_text("")
    p.chmod(0)
    _control(box, _shim(box))


def test_s49_a_fifo_never_hangs_the_hook(box):
    os.mkfifo(box / "xdg" / config.APP / "hooks.jsonl")
    _control(box, _shim(box, timeout=10))


def test_s49_no_date_on_path(box):
    _exe(box / "bin" / "agentik-session", "echo '{}'; echo said >&2; exit 2\n")
    _control(box, _shim(box, path=str(box / "bin")))
    assert _rows(box) == []


@pytest.mark.parametrize("stamp", ["1793461283N", "1793461283", "not-a-number", ""])
def test_s49_a_date_without_nanoseconds(box, stamp):
    _exe(box / "bin" / "date", f"echo '{stamp}'\n")
    _control(box, _shim(box))
    assert _rows(box) == []


@pytest.mark.parametrize("event", ['Pre"ToolUse', "Pre Tool", "../../x"])
def test_s49_an_event_that_is_not_letters_leaves_no_row(box, event):
    _control(box, _shim(box, event))
    assert _rows(box) == []


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
    (tree / "repo" / "a.md").write_text("@CLAUDE.md\n@a.md\n")
    assert _md(tree) == 6 + 17


def test_s49_imports_stop_at_five_hops(tree):
    for i in range(1, 7):
        (tree / "repo" / f"{i}.md").write_text(f"@{i + 1}.md\n")
    (tree / "repo" / "CLAUDE.md").write_text("@1.md\n")
    assert _md(tree) == 6 * 6                       # the file, then hops 1 to 5; 6.md is not read


def test_s49_a_code_span_a_fence_an_email_and_a_missing_file_import_nothing(tree):
    (tree / "repo" / "no.md").write_text("n" * 1000)
    body = "`@no.md`\n```\n@no.md\n```\nkevin@no.md\n@gone.md\n@name\n@.\n"
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
    assert row["rate_limits"] == LIMITS
    assert row["claude_md_bytes"] == 21 + 0 and list(row) == list(ledger.LEDGER_KEYS)


def test_s49_no_measure_is_a_null_rate_limits_and_the_row_stands(ended, tmp_path):
    env, _ = ended
    row = _end(env, tmp_path)[0]
    assert row["rate_limits"] is None and row["turns"] == 4


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
    assert (row["claude_md_bytes"], row["rate_limits"], row["turns"]) == (None, None, 4)


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


def test_s49_entry_for_takes_the_two_keys_and_defaults_them_null(tmp_path):
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


def test_s49_a_rotation_costs_a_hook_nothing_on_the_shims_side(box):
    # The shim writes on after a rename: the next row starts a new file, 0600.
    p = box / "xdg" / config.APP / "hooks.jsonl"
    _shim(box)
    harness.HOOKS_CAP, cap = 1, harness.HOOKS_CAP
    try:
        harness.rotate(p.parent)
    finally:
        harness.HOOKS_CAP = cap
    _shim(box)
    assert len(harness.read_hooks(p.parent)) == 2 and (p.parent / "hooks.jsonl.1").exists()
    assert p.stat().st_mode & 0o777 == 0o600
