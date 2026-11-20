"""Packet gc1: where the edit gate cannot read a Bash line, it holds its rule by the outcome.
Before the line the gated files a list in force names by a plain path are read into
`sessions/<sid>/guard-open/<tool_use_id>.json`; after it, at PostToolUse or PostToolUseFailure,
they are read again; a change is one `changed` log line, said once, and counted by doctor. It
never blocks and never restores. Every write here is the test's own, into a fixture under a
temp dir: no shell line runs."""
from __future__ import annotations

import json
import os
import time

import pytest

from claude_session import doctor, hooks, instructionguard, instructions, resolver
from test_doctor import machine  # noqa: F401  (the fixture)
from test_g2b_gates import REASON, SID, box  # noqa: F401  (the fixture)

UNREAD = 'f=CLAUDE.md; echo x >> "$f"'
SAID = ("agentik-session: {} is gated and changed during a Bash line the gate could not read. "
        "If that line ran the lane, nothing is wrong. Otherwise restore it and use the "
        "instruct skill.")
SAID_MANY = SAID.replace(" is gated", " are gated").replace("restore it", "restore them")


def _bash(command, cwd, tid="toolu_gc1_0001", **more):
    return {"session_id": SID, "cwd": str(cwd), "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tid, **more}


def _post(p, event="PostToolUse"):
    return {**p, "hook_event_name": event, "tool_response": {}}


def _sdir(b):
    return resolver.session_dir(b.state, SID)


def _log(b):
    p = _sdir(b) / instructionguard.LOG
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines()]


def _open_files(b):
    d = _sdir(b) / instructionguard.OPEN_DIR
    return sorted(os.listdir(d)) if d.is_dir() else []


def _said(out):
    """(the model's text, the owner's text) of one hook output."""
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return ctx, (out or {}).get("systemMessage") or ""


@pytest.fixture
def gb(box, monkeypatch):                       # noqa: F811
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    for name in ("CLAUDE.md", "AGENTS.md"):
        (box.repo / name).write_text(f"# {name}\n")
    return box


def _run(b, command, write=None, event="PostToolUse", **more):
    """PreToolUse, the line's effect (`write`, the test's own), then the Post event."""
    p = _bash(command, b.repo, **more)
    pre = hooks.pre_tool_use(p, b.env)
    if write:
        write()
    post = (hooks.post_tool_use(_post(p), b.env) if event == "PostToolUse"
            else hooks.post_tool_use_failure(_post(p, event), b.env))
    return pre, post


# ---- 1 to 3: the call's file, the change said, the denial before a call --------------------

def test_1_a_change_during_an_unread_line_is_logged_and_said_once(gb):
    p = _bash(UNREAD, gb.repo)
    assert hooks.pre_tool_use(p, gb.env) == {}
    assert _open_files(gb) == ["toolu_gc1_0001.json"]
    with open(gb.repo / "CLAUDE.md", "a") as f:
        f.write("x\n")
    out = hooks.post_tool_use(_post(p), gb.env)
    model, owner = _said(out)
    path = str(gb.repo / "CLAUDE.md")
    assert SAID.format("CLAUDE.md") in model and owner == SAID.format("CLAUDE.md")
    assert len(json.dumps(out)) <= hooks.MAX_OUT
    rows = _log(gb)
    assert [(r["decision"], r["path"], r["call"]) for r in rows] == \
        [("changed", path, "toolu_gc1_0001")]
    assert _open_files(gb) == []
    assert hooks.post_tool_use(_post({**p, "tool_use_id": "toolu_gc1_0002"}), gb.env) == {}


def test_2_an_unread_line_that_changes_nothing_leaves_nothing(gb):
    pre, post = _run(gb, UNREAD)
    assert pre == {} and post == {}
    assert _log(gb) == [] and _open_files(gb) == []


def test_3_a_read_write_is_denied_as_at_the_pin_and_records_nothing(gb):
    out = hooks.pre_tool_use(_bash("echo x >> CLAUDE.md", gb.repo), gb.env)
    hso = out["hookSpecificOutput"]
    assert (hso["permissionDecision"], hso["permissionDecisionReason"]) == \
        ("deny", REASON.format(gb.repo / "CLAUDE.md"))
    assert _open_files(gb) == [] and [r["decision"] for r in _log(gb)] == ["deny"]


def test_3_no_tool_use_id_or_nothing_to_record_writes_nothing(gb, tmp_path):
    p = _bash(UNREAD, gb.repo)
    del p["tool_use_id"]
    assert hooks.pre_tool_use(p, gb.env) == {}
    assert _open_files(gb) == [] and _log(gb) == []
    bare = tmp_path / "bare"                    # outside the home: no list is in force
    (bare / ".git").mkdir(parents=True)
    os.remove(gb.home / ".claude" / "edit-gates")
    assert hooks.pre_tool_use(_bash(UNREAD, bare), gb.env) == {}
    assert _open_files(gb) == [] and _log(gb) == []


# ---- 4: a gated file created, one removed --------------------------------------------------

def test_4_a_gated_file_created_and_one_removed_are_each_a_change(gb):
    os.remove(gb.repo / "CLAUDE.md")

    def act():
        os.remove(gb.repo / "AGENTS.md")
        (gb.repo / "CLAUDE.md").write_text("new\n")
    _, out = _run(gb, UNREAD, act)
    paths = sorted(r["path"] for r in _log(gb) if r["decision"] == "changed")
    assert paths == [str(gb.repo / "AGENTS.md"), str(gb.repo / "CLAUDE.md")]
    model, owner = _said(out)
    assert SAID_MANY.format("AGENTS.md, CLAUDE.md") in model
    assert owner == SAID_MANY.format("AGENTS.md, CLAUDE.md")
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_4_a_path_outside_the_calls_folder_is_said_whole(gb):
    _, out = _run(gb, UNREAD, lambda: (gb.tree / "CLAUDE.md").write_text("new\n"))
    assert [r["path"] for r in _log(gb)] == [str(gb.tree / "CLAUDE.md")]
    said = SAID.format(gb.tree / "CLAUDE.md")
    if len(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                              "additionalContext": said},
                       "systemMessage": said})) > hooks.MAX_OUT:     # a long temp path: it waits
        assert out == {}
        out = hooks.user_prompt_submit({"session_id": SID, "prompt": "go"})
    assert _said(out)[1] == said


# ---- 5: PostToolUseFailure: logged then, said once later ------------------------------------

def _fail_change(b, tid="toolu_gc1_0001"):
    def act():
        (b.repo / "CLAUDE.md").write_text("changed\n")
    _, out = _run(b, UNREAD, act, event="PostToolUseFailure", tid=tid)
    assert out == {}
    assert [r["decision"] for r in _log(b)] == ["changed"]


def test_5_a_change_at_a_failure_is_said_by_the_next_post_tool_use(gb):
    _fail_change(gb)
    nxt = _post(_bash("ls", gb.repo, tid="toolu_gc1_0002"))
    out = hooks.post_tool_use(nxt, gb.env)
    model, owner = _said(out)
    assert SAID.format("CLAUDE.md") in model and owner
    assert hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_gc1_0003")), gb.env) == {}
    assert _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))[1] == ""
    assert _open_files(gb) == [] and len(_log(gb)) == 1


def test_5_a_prompt_that_comes_first_says_it_instead(gb):
    _fail_change(gb)
    model, owner = _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))
    assert SAID.format("CLAUDE.md") in model and owner == SAID.format("CLAUDE.md")
    assert hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_gc1_0002")), gb.env) == {}
    assert _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))[1] == ""


# ---- 6: a helper's payload ------------------------------------------------------------------

@pytest.mark.parametrize("event", ["PostToolUse", "PostToolUseFailure"])
def test_6_a_helpers_change_is_logged_and_said_to_the_main_thread_once(gb, event):
    def act():
        (gb.repo / "CLAUDE.md").write_text("helper\n")
    _, out = _run(gb, UNREAD, act, event=event, agent_id="helper-1")
    assert out == {}
    rows = _log(gb)
    assert [(r["decision"], r["agent_id"]) for r in rows] == [("changed", "helper-1")]
    helper_next = _post(_bash("ls", gb.repo, tid="toolu_gc1_0002", agent_id="helper-1"))
    assert hooks.post_tool_use(helper_next, gb.env) == {}          # the helper's: not taken
    out = hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_gc1_0003")), gb.env)
    assert SAID.format("CLAUDE.md") in _said(out)[0]
    assert hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_gc1_0004")), gb.env) == {}


# ---- 7: doctor --------------------------------------------------------------------------------

def _loaded(b, sid=SID):
    d = resolver.session_dir(b.state, sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": 200, "file_path": str(b.repo / "CLAUDE.md"), "cwd": str(b.repo)}) + "\n")


def test_7_doctor_warns_on_one_changed_line(gb):
    _loaded(gb)
    _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("y\n"))
    detail, warn = instructionguard.guard_row(gb.env, gb.repo)
    assert warn and detail.endswith(
        f"session {SID}: 0 refusals, 0 guard errors, 1 gated files changed by an unread line")


def test_7_old_open_lines_alone_are_ok(gb):
    _loaded(gb)
    for why in ("the line cannot be split", "a target cannot be resolved"):
        instructionguard.log({"session_id": SID}, gb.env, "open", None, why=why)
    detail, warn = instructionguard.guard_row(gb.env, gb.repo)
    assert not warn and detail.endswith(
        f"session {SID}: 0 refusals, 0 guard errors, 0 gated files changed by an unread line")
    instructionguard.log({"session_id": SID}, gb.env, "open", None, why="RuntimeError")
    detail, warn = instructionguard.guard_row(gb.env, gb.repo)
    assert warn and "1 guard errors" in detail


def test_7_the_report_row_is_warn(machine):  # noqa: F811
    env, repo = machine.env, machine.repo
    d = resolver.session_dir(resolver.state_dir(env), SID)
    d.mkdir(parents=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": 200, "file_path": str(repo / "CLAUDE.md"), "cwd": str(repo)}) + "\n")
    instructionguard.log({"session_id": SID}, env, "changed", str(repo / "CLAUDE.md"))
    rows = [c for c in doctor.run(env, repo).checks if c.name == "guard"]
    assert len(rows) == 1 and rows[0].ok and rows[0].warn and rows[0].status == "warn"


def test_7_a_failed_write_of_the_calls_file_is_a_guard_error_never_a_refusal(gb, monkeypatch):
    def boom(*a, **k):
        raise PermissionError("no")
    monkeypatch.setattr(instructionguard, "_write_record", boom)
    assert hooks.pre_tool_use(_bash(UNREAD, gb.repo), gb.env) == {}
    assert [(r["decision"], r["why"]) for r in _log(gb)] == [("open", "PermissionError")]


# ---- 8: no noise ----------------------------------------------------------------------------

def test_8_four_hundred_unread_lines_that_change_nothing_grow_no_log(gb):
    for i in range(400):
        _run(gb, UNREAD, tid=f"toolu_gc1_{i:04d}")
    assert not (_sdir(gb) / instructionguard.LOG).exists()
    assert _open_files(gb) == []


# ---- 9: the caps --------------------------------------------------------------------------

def test_9_at_most_64_files_and_a_large_one_by_size_and_mtime(gb):
    (gb.repo / ".claude" / "edit-gates").write_text(
        "BIG.md\n" + "".join(f"f{i:02d}.md\n" for i in range(70)))
    big = gb.repo / "BIG.md"
    big.write_bytes(b"a" * (2 << 20))
    p = _bash(UNREAD, gb.repo)
    hooks.pre_tool_use(p, gb.env)
    rec = json.loads((_sdir(gb) / instructionguard.OPEN_DIR / "toolu_gc1_0001.json").read_text())
    assert len(rec["files"]) == 64
    reading = dict((k, v) for k, v in rec["files"])[str(big)]
    st = big.stat()
    assert reading == ["size", st.st_size, st.st_mtime_ns]
    with open(big, "r+b") as f:
        f.write(b"b")
    os.utime(big, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    hooks.post_tool_use(_post(p), gb.env)
    assert [r["path"] for r in _log(gb)] == [str(big)]


# ---- R4: the leftovers ----------------------------------------------------------------------

def test_r4_a_call_file_older_than_a_day_is_removed_by_the_next_write(gb):
    hooks.pre_tool_use(_bash(UNREAD, gb.repo, tid="toolu_gc1_old"), gb.env)
    hooks.pre_tool_use(_bash(UNREAD, gb.repo, tid="toolu_gc1_young"), gb.env)
    folder = _sdir(gb) / instructionguard.OPEN_DIR
    then = time.time() - 86400 - 60
    os.utime(folder / "toolu_gc1_old.json", (then, then))
    hooks.pre_tool_use(_bash(UNREAD, gb.repo, tid="toolu_gc1_new"), gb.env)
    assert _open_files(gb) == ["toolu_gc1_new.json", "toolu_gc1_young.json"]


def test_r4_a_tool_use_id_that_is_no_file_name_records_nothing(gb):
    hooks.pre_tool_use(_bash(UNREAD, gb.repo, tid="../x"), gb.env)
    assert _open_files(gb) == [] and not (_sdir(gb).parent / "x.json").exists()


# ---- R5: an open line for a guard exception alone ----------------------------------------------

@pytest.mark.parametrize("command", ["echo x >> $X", "cp a notes.md \\", "echo 'a; cp a notes.md"])
def test_r5_the_retired_reasons_log_nothing(gb, command):
    assert instructionguard.check(_bash(command, gb.repo), gb.env) == {}
    assert _log(gb) == []
    assert _open_files(gb) == ["toolu_gc1_0001.json"]


# ---- R3: the fit ----------------------------------------------------------------------------

def test_r3_a_change_that_does_not_fit_beside_the_handlers_words_waits(gb, monkeypatch):
    big = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": "CHECKPOINT: " + "w" * 500}}
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: big)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("z\n"))
    assert out["hookSpecificOutput"]["additionalContext"].startswith("CHECKPOINT: ")
    assert "systemMessage" not in out
    model, owner = _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))
    assert SAID.format("CLAUDE.md") in model and owner


def test_r3_the_checkpoint_line_comes_first(gb, monkeypatch):
    small = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": "CHECKPOINT: 80%"}}
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: small)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("z\n"))
    model, owner = _said(out)
    assert model.startswith("CHECKPOINT: 80%\n\n") and owner.startswith("agentik-session: ")
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_r3_several_paths_are_comma_joined(gb):
    def act():
        (gb.repo / "CLAUDE.md").write_text("1\n")
        (gb.repo / "AGENTS.md").write_text("2\n")
    _, out = _run(gb, UNREAD, act)
    owner = _said(out)[1]
    assert owner.startswith("agentik-session: AGENTS.md, CLAUDE.md are gated and changed ")
