import pytest

from claude_session import launch
from claude_session.sessionconfig import SessionConfig


@pytest.fixture(autouse=True)
def fake_bins(tmp_path, monkeypatch):
    """Pretend both launchers exist, so tests exercise resolution not PATH."""
    bins = {"claude": str(tmp_path / "claude"),
            "claude-local": str(tmp_path / "claude-local")}
    monkeypatch.setattr(launch.shutil, "which", lambda n: bins.get(n))
    return bins


def test_seat_lane_uses_claude_directly(fake_bins):
    l = launch.build(SessionConfig(name="f", model="opus", effort="xhigh"))
    assert l.program == fake_bins["claude"]
    assert "--model" in l.argv and l.argv[l.argv.index("--model") + 1] == "opus"
    assert "--effort" in l.argv
    assert l.env["CLAUDE_SESSION_CONFIG"] == "f"


def test_nothing_is_written_to_settings():
    """Every knob is a per-session flag; a configured session leaves no trace."""
    l = launch.build(SessionConfig(name="f", model="opus", tools="Read"))
    assert "--settings" not in l.argv          # no settings unless asked for
    joined = " ".join(l.argv)
    assert "settings.json" not in joined


def test_tools_not_allowedtools():
    l = launch.build(SessionConfig(name="r", tools="Read,Glob,Grep"))
    assert "--tools" in l.argv and "--allowedTools" not in l.argv


def test_local_lane_delegates_to_claude_local(fake_bins):
    l = launch.build(SessionConfig(name="l", lane="local", subagent_model="sonnet"))
    assert l.program == fake_bins["claude-local"]
    # claude-local owns the router and credential rules; we only pass its knob
    assert l.env["CLAUDE_LOCAL_SUBAGENT"] == "sonnet"
    assert "CLAUDE_CODE_SUBAGENT_MODEL" not in l.env
    assert "ANTHROPIC_BASE_URL" not in l.env


def test_seat_lane_sets_the_subagent_env_var(fake_bins):
    l = launch.build(SessionConfig(name="f", subagent_model="opus"))
    assert l.env["CLAUDE_CODE_SUBAGENT_MODEL"] == "opus"
    assert "CLAUDE_LOCAL_SUBAGENT" not in l.env


def test_local_lane_without_claude_local_fails_clearly(monkeypatch):
    monkeypatch.setattr(launch.shutil, "which", lambda n: None)
    with pytest.raises(launch.LaunchError, match="claude-local"):
        launch.build(SessionConfig(name="l", lane="local"))


def test_local_only_without_a_model_warns(fake_bins):
    l = launch.build(SessionConfig(name="lo", lane="local-only"))
    assert any("main thread on the seat" in w for w in l.warnings)
    l2 = launch.build(SessionConfig(name="lo", lane="local-only",
                                    model="local/default"))
    assert not l2.warnings


def test_plugins_resolve_to_plugin_dir(tmp_path, monkeypatch, fake_bins):
    repo = tmp_path / "code" / "claude-code-respeak"
    repo.mkdir(parents=True)
    monkeypatch.setattr(launch, "PLUGIN_SEARCH", [tmp_path / "code"])
    l = launch.build(SessionConfig(name="f", plugins=["respeak"]))
    assert "--plugin-dir" in l.argv
    assert str(repo) in l.argv


def test_missing_plugin_warns_but_still_launches(monkeypatch, fake_bins):
    monkeypatch.setattr(launch, "PLUGIN_SEARCH", [])
    l = launch.build(SessionConfig(name="f", plugins=["nope"]))
    assert any("nope" in w for w in l.warnings)
    assert "--plugin-dir" not in l.argv


def test_extra_args_are_appended_last(fake_bins):
    l = launch.build(SessionConfig(name="f", model="opus"),
                     extra=["--add-dir", "/tmp/x"])
    assert l.argv[-2:] == ["--add-dir", "/tmp/x"]


def test_system_note_explains_the_checkpoint_cadence(fake_bins):
    l = launch.build(SessionConfig(name="f", checkpoint={"clear": 20, "notice": 10,
                                                         "wind-down": 4, "reserve": 2}))
    note = l.argv[l.argv.index("--append-system-prompt") + 1]
    assert "every 20 prompts" in note and "tightening to 4" in note
    assert "claude-session checkpoint" in note


def test_posture_off_tells_the_model_to_stay_quiet(fake_bins):
    l = launch.build(SessionConfig(name="s", posture="off"))
    note = l.argv[l.argv.index("--append-system-prompt") + 1]
    assert "signalling is off" in note
    assert "checkpoint more often" not in note


def test_gated_postures_are_announced(fake_bins):
    for posture in ("ask", "deny"):
        l = launch.build(SessionConfig(name="f", posture=posture))
        note = l.argv[l.argv.index("--append-system-prompt") + 1]
        assert f"gated ({posture})" in note


def test_session_is_named_after_the_config(fake_bins):
    l = launch.build(SessionConfig(name="frontier"))
    assert l.argv[l.argv.index("--name") + 1] == "frontier"


def test_invalid_config_is_rejected_before_launching(fake_bins):
    with pytest.raises(ValueError):
        launch.build(SessionConfig(name="x", posture="whatever"))


def test_shell_preview_is_quoted(fake_bins):
    l = launch.build(SessionConfig(name="f", notes="it's got a quote"))
    assert "'" in l.shell_preview()
    assert "\n" not in l.shell_preview().split("--append-system-prompt")[0]



def test_config_env_cannot_redirect_credentials(fake_bins):
    """claude-local unsets these deliberately; the launcher must refuse them."""
    for key in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "PATH", "PYTHONPATH",
                "DYLD_INSERT_LIBRARIES", "CLAUDE_CODE_OAUTH_TOKEN"):
        with pytest.raises(launch.LaunchError, match=key):
            launch.build(SessionConfig(name="x", env={key: "evil"}))
    l = launch.build(SessionConfig(name="x", env={"MY_FLAG": "1"}))
    assert l.env["MY_FLAG"] == "1"


def test_setting_sources_must_keep_user(fake_bins):
    """Dropping `user` removes ~/.claude/settings.json and the break-glass guard.
    validate() catches it at `set --save` time; launch re-checks in case a
    config file was edited by hand."""
    with pytest.raises(ValueError, match="user"):
        launch.build(SessionConfig(name="x", setting_sources="project"))
    l = launch.build(SessionConfig(name="x", setting_sources="user,project"))
    assert l.argv[l.argv.index("--setting-sources") + 1] == "user,project"


def test_snapshot_stays_on_with_the_appended_note(fake_bins):
    l = launch.build(SessionConfig(name="x"))
    assert "--system-prompt-snapshot" in l.argv
    assert l.argv[l.argv.index("--system-prompt-snapshot") + 1] == "on"


def test_empty_tools_means_no_tools(fake_bins):
    l = launch.build(SessionConfig(name="x", tools=""))
    assert l.argv[l.argv.index("--tools") + 1] == ""


def test_missing_claude_fails_clearly(monkeypatch):
    monkeypatch.setattr(launch.shutil, "which", lambda n: None)
    with pytest.raises(launch.LaunchError, match="claude"):
        launch.build(SessionConfig(name="x"))


# ---- nesting depth (review r6 C2) --------------------------------------------

@pytest.fixture
def captured_exec(monkeypatch, fake_bins):
    """`start` end to end, with execvpe captured instead of replacing the test."""
    calls = []
    monkeypatch.setattr(launch.os, "execvpe",
                        lambda prog, argv, env: calls.append((prog, argv, dict(env))))
    for k in ("CLAUDE_SESSION_DEPTH", "CLAUDE_SESSION_MAX_TURNS", "CLAUDE_SESSION_CONFIG"):
        monkeypatch.delenv(k, raising=False)
    return calls


def _start(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(["start", *argv])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def test_nested_depth_absent_starts_the_child_at_1(captured_exec):
    rc, _, err = _start("frontier")
    assert rc == 0, err
    assert captured_exec[0][2]["CLAUDE_SESSION_DEPTH"] == "1"


def test_nested_depth_survives_the_scrub(captured_exec, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "parent")
    rc, _, err = _start("frontier")
    env = captured_exec[0][2]
    assert rc == 0, err
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_SESSION_ID" not in env
    assert env["CLAUDE_SESSION_DEPTH"] == "1"


def test_nested_depth_1_is_refused_without_the_flag(captured_exec, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "1")
    rc, _, err = _start("frontier")
    assert rc == 2
    assert "--nested" in err
    assert captured_exec == []


def test_nested_dry_run_is_refused_too(captured_exec, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "3")
    rc, out, err = _start("frontier", "--dry-run")
    assert rc == 2 and "--nested" in err and out == ""


def test_nested_flag_allows_depth_2(captured_exec, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "1")
    rc, _, err = _start("frontier", "--nested")
    assert rc == 0, err
    assert captured_exec[0][2]["CLAUDE_SESSION_DEPTH"] == "2"
    assert "--nested" not in captured_exec[0][1]


@pytest.mark.parametrize("raw,refused", [("", False), (" ", False), ("x", True),
                                         ("-1", True), ("1x", True)])
def test_nested_unparsable_depth_refuses(captured_exec, monkeypatch, raw, refused):
    """ADV10-10: blank is absent (depth 0); set but unparsable refuses, never 0."""
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", raw)
    rc, _, err = _start("frontier")
    if refused:
        assert rc == 2 and "is not a depth" in err and captured_exec == []
    else:
        assert rc == 0, err
        assert captured_exec[0][2]["CLAUDE_SESSION_DEPTH"] == "1"


@pytest.mark.parametrize("raw,nested", [(None, False), ("", False), (" ", False),
                                        ("0", False), ("1", True), ("2", True)],
                         ids=["unset", "empty", "blank", "zero", "one-nested", "two-nested"])
def test_start_always_opens_a_sitting(captured_exec, monkeypatch, raw, nested):
    """The relay's Stop hook and per-session state act only in a sitting (RELAY_ROW, or
    CLAUDE_SESSION_DEPTH >= 1; the owner, 2026-09-24): every started claude is one."""
    if raw is not None:
        monkeypatch.setenv("CLAUDE_SESSION_DEPTH", raw)
    want = str((int(raw) if (raw or "").strip() else 0) + 1)
    flags = ["--nested"] if nested else []
    for extra in ([], ["--max-turns", "5"]):
        captured_exec.clear()
        rc, _, err = _start("frontier", *flags, *extra)
        assert rc == 0, err
        got = captured_exec[0][2]["CLAUDE_SESSION_DEPTH"]
        assert got.isascii() and got.isdigit() and int(got) >= 1 and got == want
    rc, out, err = _start("frontier", *flags, "--max-turns", "5", "--dry-run")
    assert rc == 0, err
    assert ("CLAUDE_SESSION_DEPTH=%s" % want) in out.split()


def test_nested_depth_cannot_be_set_by_a_config(fake_bins):
    with pytest.raises(launch.LaunchError, match="CLAUDE_SESSION_DEPTH"):
        launch.build(SessionConfig(name="f", env={"CLAUDE_SESSION_DEPTH": "0"}))


# ---- the launch's turn ceiling (review r6 E5) ---------------------------------

def test_max_turns_start_passes_the_flag_and_sets_the_variable(captured_exec):
    rc, _, err = _start("frontier", "--max-turns", "80")
    assert rc == 0, err
    prog, argv, env = captured_exec[0]
    assert argv[-2:] == ["--max-turns", "80"]
    assert env["CLAUDE_SESSION_MAX_TURNS"] == "80"


def test_max_turns_absent_sets_no_variable(captured_exec, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_MAX_TURNS", "12")     # a parent's, not this child's
    rc, _, err = _start("frontier")
    assert rc == 0, err
    assert "CLAUDE_SESSION_MAX_TURNS" not in captured_exec[0][2]
    assert "--max-turns" not in captured_exec[0][1]


@pytest.mark.parametrize("bad", ["0", "-1", "x"])
def test_max_turns_must_be_a_positive_integer(captured_exec, bad):
    rc, _, err = _start("frontier", "--max-turns", bad)
    assert rc == 2 and captured_exec == []


def test_max_turns_cannot_be_set_by_a_config(fake_bins):
    with pytest.raises(launch.LaunchError, match="CLAUDE_SESSION_MAX_TURNS"):
        launch.build(SessionConfig(name="f", env={"CLAUDE_SESSION_MAX_TURNS": "9"}))


def test_s20a_exec_launch_uses_scrub(captured_exec, monkeypatch):
    """`launch.scrub` is the one scrub list; `exec_launch` and the chain both use it."""
    import os
    scrubbed = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
                "CLAUDE_PID", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_SESSION_MAX_TURNS")
    for k in scrubbed:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("KEEP_ME", "1")
    env = launch.scrub(dict(os.environ))
    assert env["KEEP_ME"] == "1" and not set(scrubbed) & set(env)
    seen = []
    real = launch.scrub
    monkeypatch.setattr(launch, "scrub", lambda e: seen.append(1) or real(e))
    rc, _, err = _start("frontier")
    assert rc == 0, err
    assert seen == [1]
    child = captured_exec[0][2]
    assert child["KEEP_ME"] == "1" and not set(scrubbed) & set(child)
