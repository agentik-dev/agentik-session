"""Packet rr5a: the hooks through the records resolver (R4 to R6). Every name is made up."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from claude_session import charter, cli, config, hooks, records, resolver

from test_rr5a_charter_folder import layout

pytestmark = pytest.mark.usefixtures("frontier_home")

SID = "rr5a-sess-1"
STATES = ["own", "out", "unset", "missing"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    records.reset()
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv(hooks.CHAIN_VAR, raising=False)
    config.ensure_dirs()
    yield dict(os.environ)
    records.reset()


def sdir(env):
    s = resolver.session_dir(resolver.state_dir(env), SID)
    s.mkdir(parents=True, exist_ok=True)
    return s


def transcript(tmp_path, context):
    row = {"type": "assistant", "requestId": "r0", "timestamp": "2026-09-22T10:00:00Z",
           "message": {"id": "m0", "model": "claude-opus-5-5",
                       "content": [{"type": "text", "text": "<placeholder>"}],
                       "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                 "cache_read_input_tokens": context, "output_tokens": 7}}}
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(row) + "\n")
    return p


def resolved(env, d="h"):
    (sdir(env) / "resolved.json").write_text(json.dumps(
        {"session": {"posture": "signal", "charter": {"dir": d}}}))


def line(env, tmp_path, c, chained=False):
    e = {**env, hooks.CHAIN_VAR: "net"} if chained else env
    out = hooks.post_tool_use({"session_id": SID, "transcript_path": str(transcript(tmp_path, 144000)),
                               "tool_name": "Read", "cwd": str(c)}, e)
    return out["hookSpecificOutput"]["additionalContext"]


def opened(env, folder):
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / f"{charter.today()}-1.md"
    f.write_text("# sitting\n")
    (sdir(env) / hooks.CHARTER_REC).write_text(json.dumps({"path": str(f)}))
    return f


def required(d="h"):
    return {"charter": {"required": True, "dir": d}}


@pytest.mark.parametrize("state", STATES)
def test_session_start_reminder_in_each_state(env, tmp_path, state):
    c, rec = layout(tmp_path, state)
    got = hooks._charter_reminder(required(), str(c))
    if state == "own":
        assert got == '; charter: none open today under h, run agentik-session charter open "<goal>"'
    elif state == "out":
        assert got == (f"; charter: none open today under {rec / 'h'}, run "
                       'agentik-session charter open "<goal>"')
        opened(env, rec / "h")
        assert hooks._charter_reminder(required(), str(c)) == ""
    elif state == "unset":
        assert got == ""
    else:
        assert got == "; records: " + records.line(records.answer(str(c)))
        assert got.count("agentik.records") == 2 and "reason missing" in got


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("chained", [False, True])
@pytest.mark.parametrize("with_charter", [False, True])
def test_checkpoint_line_in_each_state(env, tmp_path, monkeypatch, state, chained, with_charter):
    c, rec = layout(tmp_path, state)
    resolved(env)
    f = opened(env, (rec if state == "out" else c) / "h") if with_charter else None
    if state == "out" and chained and f:     # a temp root is long: room for the absolute path
        monkeypatch.setattr(hooks, "MAX_OUT", 4000)
    got = line(env, tmp_path, c, chained)
    assert got.startswith("CHECKPOINT: ")
    if state in ("unset", "broken", "missing"):
        assert hooks.PLAIN_TAIL in got and "charter" not in got
    elif state == "own":
        if not chained:
            assert "; charter h; bring the charter current" in got
        else:
            assert (f"--charter {f}`" in got or f"--charter h/{f.name}`" in got) if f else (
                f"--charter {hooks.NO_CHARTER}`" in got)
    else:
        if not chained:
            assert f"; charter {rec / 'h'}; bring the charter current" in got
        else:
            # the absolute path where it fits MAX_OUT (a temp root is long), else NO_CHARTER;
            # never a relative spelling
            assert f"--charter {f if f else hooks.NO_CHARTER}`" in got
            assert f"--charter h/" not in got


def test_out_charter_file_never_relative(env, tmp_path):
    c, rec = layout(tmp_path, "out")
    f = opened(env, rec / "h")
    assert hooks._charter_file_out(sdir(env), str(rec / "h")) == [str(f), hooks.NO_CHARTER]
    assert hooks._charter_file_out(sdir(env), str(rec / "other")) == [hooks.NO_CHARTER]
    sub = rec / "h" / "deeper"
    g = opened(env, sub)
    assert hooks._charter_file_out(sdir(env), str(rec / "h")) == [hooks.NO_CHARTER]
    assert g.is_file()


@pytest.mark.parametrize("state", STATES)
def test_the_record_of_the_open(env, tmp_path, monkeypatch, state):
    c, rec = layout(tmp_path, state)
    s = sdir(env)
    resolver.save_request(s, str(c), None, None, None, None)
    section = {"charter": {"dir": "history/sittings"}}
    here = c / "history" / "sittings"
    there = rec / "history" / "sittings" if rec else None
    got_here = cli._records_here(str(here), section)
    got_there = cli._records_here(str(there), section) if there else None
    if state == "own":
        assert got_here == s
    elif state == "out":
        assert got_here is None and got_there == s
        f = there / "2026-11-20-1.md"
        there.mkdir(parents=True)
        f.write_text("# s\n")
        cli._record_charter(f, section)
        assert json.loads((s / hooks.CHARTER_REC).read_text()) == {"path": str(f)}
    else:                     # only an explicit --dir opens here: the pin's record
        assert got_here == s


@pytest.mark.parametrize("chained", [False, True])
@pytest.mark.parametrize("body", ["raise RuntimeError('made-up')", "import time; time.sleep(30)"])
def test_no_hook_raises_or_refuses_with_a_resolver_that_raises_or_sleeps(env, tmp_path,
                                                                           monkeypatch, body,
                                                                           chained):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "agentik_records.py").write_text(
        f"class NoRepo(Exception):\n    pass\n\ndef resolve(start):\n    {body}\n")
    monkeypatch.setattr(records, "_LIB", str(lib))
    monkeypatch.setattr(records, "BOUND", 0.5)
    c, _ = layout(tmp_path, "own")
    resolved(env)
    got = line(env, tmp_path, c, chained)
    assert hooks.PLAIN_TAIL in got
    records.reset()
    assert hooks._charter_reminder(required(), str(c)).startswith("; records: agentik.records")


# --- R6: the hot path --------------------------------------------------------------------

@pytest.mark.parametrize("state", ["own", "out"])
def test_hot_hooks_start_no_resolver(env, tmp_path, monkeypatch, state):
    c, _ = layout(tmp_path, state)
    resolved(env)
    starts = []
    real = subprocess.Popen

    def counted(*a, **k):
        starts.append(a[0] if a else k.get("args"))
        return real(*a, **k)
    monkeypatch.setattr(subprocess, "Popen", counted)

    def never(folder):
        raise AssertionError("the resolver was asked on the hot path")
    monkeypatch.setattr(records, "_read", never)
    base = {"session_id": SID, "cwd": str(c)}
    hooks.pre_tool_use({**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, env)
    hooks.post_tool_use({**base, "tool_name": "Read",
                         "transcript_path": str(transcript(tmp_path, 1000))}, env)
    hooks.stop(base, env)
    hooks.user_prompt_submit({**base, "prompt": "hello"})
    assert [s for s in starts if "agentik_records" in json.dumps(s, default=str)] == []
    count = len(starts)
    # the same four in the other state start the same count
    other = "out" if state == "own" else "own"
    d2 = tmp_path / "o"
    c2, _ = layout(d2, other)
    starts.clear()
    base = {"session_id": SID, "cwd": str(c2)}
    hooks.pre_tool_use({**base, "tool_name": "Bash", "tool_input": {"command": "ls"}}, env)
    hooks.post_tool_use({**base, "tool_name": "Read",
                         "transcript_path": str(transcript(tmp_path, 1000))}, env)
    hooks.stop(base, env)
    hooks.user_prompt_submit({**base, "prompt": "hello"})
    assert len(starts) == count
