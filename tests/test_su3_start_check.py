"""Packet su3-start-check: SessionStart says a declared watcher that is not running (entry 12).

Every test puts a stub `agentik-suite` under a temp HOME; none runs the live launcher, reads
the live user file or starts a `claude` process."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import hooks, resolver

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "session_start.json"
LINE = "watch: not running since 2026-11-17 09:00; start it: watch --serve"
MORE = " and {n} more: agentik status"


def payload(**extra):
    d = json.loads(FIXTURE.read_text())
    d["cwd"] = str(ROOT / d["cwd"])
    d["transcript_path"] = str(ROOT / d["transcript_path"])
    d.update(extra)
    return d


def env_for(tmp_path, **extra):
    return {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "PATH": "/usr/bin:/bin", **extra}


def stub(tmp_path, body: str, mode=0o755) -> Path:
    """The launcher's stand-in at its fixed place; it records its argv in `$HOME/argv`."""
    path = tmp_path / "home" / ".local" / "bin" / "agentik-suite"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOME/argv"\n' + body)
    path.chmod(mode)
    return path


def lines_stub(tmp_path, *lines, code=1):
    body = "".join(f"printf '%s\\n' '{ln}'\n" for ln in lines) + f"exit {code}\n"
    return stub(tmp_path, body)


def ctx(out):
    return out["hookSpecificOutput"]["additionalContext"]


def gone(pid: int, within: float = 1.0) -> bool:
    end = time.monotonic() + within
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        r = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                           text=True)
        if r.stdout.strip().startswith("Z") or not r.stdout.strip():
            return True                                 # killed; its reaper is init's
        if time.monotonic() > end:
            return False
        time.sleep(0.05)


# Acceptance 1: one line on both channels, first in the context.

def test_one_line_on_both_channels_before_the_start_line(tmp_path):
    env = env_for(tmp_path)
    base = json.dumps(hooks.session_start(payload(), env))
    lines_stub(tmp_path, LINE)
    out = hooks.session_start(payload(), env)
    assert out["systemMessage"] == LINE
    start = json.loads(base)["hookSpecificOutput"]["additionalContext"]
    assert ctx(out) == f"{LINE}\n\n{start}"


def test_three_lines_say_the_first_and_how_many_more(tmp_path):
    lines_stub(tmp_path, LINE, "beat: hung", "relay: not running")
    out = hooks.session_start(payload(), env_for(tmp_path))
    want = LINE + MORE.format(n=2)
    assert out["systemMessage"] == want and ctx(out).startswith(want + "\n\n")


def test_a_control_character_is_taken_out_and_stderr_never_shown(tmp_path):
    stub(tmp_path, "printf 'wat\\033[31mch:\\tdown\\r\\n'\necho secret-err >&2\nexit 1\n")
    out = hooks.session_start(payload(), env_for(tmp_path))
    assert out["systemMessage"] == "wat[31mch:down"
    assert "secret-err" not in json.dumps(out)


def test_blank_lines_are_not_counted(tmp_path):
    stub(tmp_path, "printf '\\n%s\\n\\n%s\\n\\n' 'a: down' 'b: down'\nexit 1\n")
    assert hooks.session_start(payload(), env_for(tmp_path))["systemMessage"] == \
        "a: down" + MORE.format(n=1)


@pytest.mark.parametrize("source", ["startup", "resume", "clear", "compact"])
def test_every_start_reason(tmp_path, source):
    lines_stub(tmp_path, LINE)
    out = hooks.session_start(payload(source=source), env_for(tmp_path))
    assert out["systemMessage"] == LINE and ctx(out).startswith(LINE)


def test_the_hooks_own_message_follows_the_line(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.install, "refresh", lambda env: "refresh: failed")
    lines_stub(tmp_path, LINE)
    assert hooks.session_start(payload(), env_for(tmp_path))["systemMessage"] == \
        f"{LINE}\nrefresh: failed"


# Acceptance 2: every other outcome is silence, the output byte for byte the stubless one.

SILENT = {
    "exit 0": lambda t: lines_stub(t, LINE, code=0),
    "exit 2": lambda t: lines_stub(t, LINE, code=2),
    "exit 3": lambda t: lines_stub(t, LINE, code=3),
    "exit 126": lambda t: lines_stub(t, LINE, code=126),
    "exit 127": lambda t: lines_stub(t, LINE, code=127),
    "absent": lambda t: None,
    "not executable": lambda t: stub(t, f"echo '{LINE}'\nexit 1\n", mode=0o644),
    "a folder": lambda t: (t / "home/.local/bin/agentik-suite").mkdir(parents=True),
    "empty exit 1": lambda t: stub(t, "exit 1\n"),
    "blank exit 1": lambda t: stub(t, "printf '\\n \\n'\nexit 1\n"),
    "not text": lambda t: stub(t, "printf '\\377\\376down\\n'\nexit 1\n"),
    "no shebang": lambda t: stub(t, "").write_bytes(b"\x00\x01garbage"),
}


@pytest.mark.parametrize("case", sorted(SILENT))
def test_silence_is_the_stubless_output(tmp_path, case):
    env = env_for(tmp_path)
    base = json.dumps(hooks.session_start(payload(), env))
    SILENT[case](tmp_path)
    assert json.dumps(hooks.session_start(payload(), env)) == base


def test_a_wall_cut_is_silence_and_the_child_is_gone(tmp_path):
    env = env_for(tmp_path)
    t0 = time.monotonic()
    base = json.dumps(hooks.session_start(payload(), env))
    own = time.monotonic() - t0                         # the start's own time, under load
    stub(tmp_path, f"echo '{LINE}'\necho $$ > \"$HOME/pid\"\nexec /bin/sleep 30\n")
    t0 = time.monotonic()
    out = json.dumps(hooks.session_start(payload(), env))
    assert time.monotonic() - t0 - own < 3
    assert out == base
    with pytest.raises(ProcessLookupError):           # killed and reaped
        os.kill(int((tmp_path / "home/pid").read_text()), 0)


@pytest.mark.parametrize("tail", ["wait\nexit 1\n", "exit 1\n"])
def test_a_wall_cut_takes_the_childs_own_children(tmp_path, tail):
    # `exit 1` alone: the stub is gone, its child still holds stdout, and the wall cuts it
    stub(tmp_path, f"echo '{LINE}'\n/bin/sleep 30 &\necho $! > \"$HOME/pid\"\n{tail}")
    t0 = time.monotonic()
    assert hooks.watcher_share(payload(), env_for(tmp_path)) is None
    assert time.monotonic() - t0 < 3
    assert gone(int((tmp_path / "home/pid").read_text()))


def test_the_cli_exits_0_within_the_wall(tmp_path):
    env = {**os.environ, **env_for(tmp_path)}
    for k in ("CLAUDE_SESSION_PROFILE", "CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_HELPER"):
        env.pop(k, None)

    def run():
        t0 = time.monotonic()
        r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "SessionStart"],
                           input=FIXTURE.read_text(), capture_output=True, text=True,
                           cwd=ROOT, env=env, timeout=30)
        return r, time.monotonic() - t0
    base, base_took = run()
    stub(tmp_path, f"echo '{LINE}'\nexec /bin/sleep 30\n")
    r, took = run()
    assert r.returncode == 0 and r.stdout == base.stdout and took - base_took < 3
    lines_stub(tmp_path, LINE, code=127)
    r, _ = run()
    assert r.returncode == 0 and r.stdout == base.stdout


# Acceptance 3: the call's argv; a helper's start makes none; a HOME that is not absolute.

def test_the_call_is_status_check_alone(tmp_path):
    lines_stub(tmp_path, LINE, code=0)
    hooks.session_start(payload(), env_for(tmp_path))
    assert (tmp_path / "home/argv").read_text() == "status\n--check\n"


@pytest.mark.parametrize("helper_env, helper_payload", [
    ({"CLAUDE_SESSION_HELPER": "1"}, {}),
    ({}, {"agent_id": "a1b2c3"}),
])
def test_a_helpers_start_makes_no_call(tmp_path, helper_env, helper_payload):
    lines_stub(tmp_path, LINE)
    out = hooks.session_start(payload(**helper_payload), env_for(tmp_path, **helper_env))
    assert not (tmp_path / "home/argv").exists() and LINE not in json.dumps(out)


@pytest.mark.parametrize("home", [None, "", "home", "./home"])
def test_a_home_unset_or_not_absolute_is_no_call(tmp_path, monkeypatch, home):
    monkeypatch.chdir(tmp_path)
    lines_stub(tmp_path, LINE)
    env = {"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"}
    if home is not None:
        env["HOME"] = home
    assert hooks.watcher_share(payload(), env) is None
    assert not (tmp_path / "home/argv").exists()


# Acceptance 4: a long first line is whole or cut at its end, never absent, on every road.

def _alone(share: str) -> int:
    return len(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                  "additionalContext": share}}))


@pytest.mark.parametrize("more", [0, 2])
def test_a_long_first_line_is_cut_at_its_end(tmp_path, more):
    first = "w: " + "x" * 597
    lines_stub(tmp_path, first, *["m: down"] * more)
    out = hooks.session_start(payload(), env_for(tmp_path))
    share = out["systemMessage"]
    tail = MORE.format(n=more) if more else ""
    assert share.endswith(tail) and first.startswith(share[:len(share) - len(tail)])
    assert len(share) - len(tail) > 400 and _alone(share) <= hooks.MAX_OUT
    assert ctx(out).startswith(share + "\n\n")


def test_a_wide_first_line_is_cut_by_its_encoded_size(tmp_path):
    lines_stub(tmp_path, "w: " + "\u00e9\U0001f600" * 300)
    share = hooks.session_start(payload(), env_for(tmp_path))["systemMessage"]
    assert share.startswith("w: \u00e9") and _alone(share) <= hooks.MAX_OUT


# Fix of review 1 (C1, C2): a launcher that prints past the keep is answered by what it printed.

def _big_stub(tmp_path, data: bytes, code=1):
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    big = tmp_path / "home" / "big.txt"
    big.write_bytes(data)
    return stub(tmp_path, f'/bin/cat "$HOME/big.txt"\nexit {code}\n')


def test_a_cut_inside_a_character_is_not_silence(tmp_path):
    _big_stub(tmp_path, b"ab\n" + "\u00e9".encode() * 40000 + b"\n")
    start = time.monotonic()
    share = hooks.watcher_share(payload(), env_for(tmp_path))
    assert time.monotonic() - start < hooks.WATCH_WALL
    assert share == "ab" + MORE.format(n=1)


def test_the_count_is_of_every_line_the_launcher_printed(tmp_path):
    _big_stub(tmp_path, b"first: down\n" + b"x: down\n" * 200000)
    start = time.monotonic()
    share = hooks.watcher_share(payload(), env_for(tmp_path))
    assert time.monotonic() - start < hooks.WATCH_WALL
    assert share == "first: down" + MORE.format(n=200000)


def test_a_first_line_longer_than_the_keep_is_cut_and_still_said(tmp_path):
    _big_stub(tmp_path, ("w: " + "\u00e9" * 80000 + "\nm: down\n").encode())
    share = hooks.watcher_share(payload(), env_for(tmp_path))
    assert share.startswith("w: \u00e9") and share.endswith(MORE.format(n=1))


def test_the_unknown_profile_road_says_the_line(tmp_path):
    lines_stub(tmp_path, "w: " + "x" * 597)
    out = hooks.session_start(payload(), env_for(tmp_path, CLAUDE_SESSION_PROFILE="nosuch"))
    share = out["systemMessage"]
    assert share.startswith("w: xxx") and ctx(out).startswith(share + "\n\n")
    assert "unknown profile 'nosuch'" in ctx(out)


def test_the_empty_road_says_the_line(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise resolver.ResolveError("boom")
    monkeypatch.setattr(resolver, "resolve", fail)
    lines_stub(tmp_path, LINE)
    out = hooks.session_start(payload(), env_for(tmp_path))
    assert out == {"systemMessage": LINE, "hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": LINE}}


def test_a_failure_outside_the_start_still_says_the_line(tmp_path, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(hooks, "_tiers_part", fail)
    lines_stub(tmp_path, LINE)
    assert hooks.session_start(payload(), env_for(tmp_path))["systemMessage"] == LINE
    (tmp_path / "home/.local/bin/agentik-suite").unlink()
    with pytest.raises(RuntimeError):                  # no line: the pin's behaviour
        hooks.session_start(payload(), env_for(tmp_path))
