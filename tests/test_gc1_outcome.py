"""Packet gc1: where the edit gate cannot read a Bash line, it holds its rule by the outcome.
Before the line the gated files a list in force names by a plain path are read into
`sessions/<sid>/guard-open/<tool_use_id>.json`; after it, at PostToolUse or PostToolUseFailure,
they are read again; a change is one `changed` log line, said once, and counted by doctor. It
never blocks and never restores. Every write here is the test's own, into a fixture under a
temp dir: no shell line runs."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time

import pytest

from claude_session import doctor, hooks, instructionguard, instructions, resolver
from test_doctor import machine  # noqa: F401  (the fixture)
from test_g2b_gates import REASON, SID, box  # noqa: F401  (the fixture)

UNREAD = 'f=CLAUDE.md; echo x >> "$f"'
MODEL = ("agentik-session: {} is gated and changed during a Bash line the gate could not read. "
         "If that line ran the lane, nothing is wrong. Otherwise restore it and use the "
         "instruct skill.")
OWNER = "agentik-session: a gated file changed during a Bash line the gate could not read: {}"


def _drawn(path):
    """Brief 2 F2: a path as one waiting path alone is drawn beside `{}` at PostToolUse."""
    s = str(path)
    return s if len(s) <= 48 else "\u2026" + s[-47:]


def _names(text, path, more=0):
    """The owner's line names `path`, drawn whole or as a tail, then `(+more more)`."""
    prefix = OWNER.format("")
    tail = f" (+{more} more)" if more else ""
    if not (text.startswith(prefix) and text.endswith(tail)):
        return False
    head = text[len(prefix):len(text) - len(tail)]
    return head == str(path) or (head.startswith("\u2026") and len(head) >= 30
                                 and str(path).endswith(head[1:]))


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
    shown = _drawn(path)
    assert model == MODEL.format(shown) and owner == OWNER.format(shown)
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
    assert _names(owner, gb.repo / "AGENTS.md", 1)
    assert model == MODEL.format(owner[len(OWNER.format("")):])
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_4_a_path_outside_the_calls_folder_is_said_at_its_own_post(gb):
    _, out = _run(gb, UNREAD, lambda: (gb.tree / "CLAUDE.md").write_text("new\n"))
    assert [r["path"] for r in _log(gb)] == [str(gb.tree / "CLAUDE.md")]
    assert _said(out)[1] == OWNER.format(_drawn(gb.tree / "CLAUDE.md"))


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
    assert MODEL.format(_drawn(gb.repo / "CLAUDE.md")) in model and owner
    assert hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_gc1_0003")), gb.env) == {}
    assert _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))[1] == ""
    assert _open_files(gb) == [] and len(_log(gb)) == 1


def test_5_a_prompt_that_comes_first_says_it_instead(gb):
    _fail_change(gb)
    model, owner = _said(hooks.user_prompt_submit({"session_id": SID, "prompt": "go"}))
    assert _names(owner, gb.repo / "CLAUDE.md")
    assert MODEL.format(owner[len(OWNER.format("")):]) in model
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
    assert MODEL.format(_drawn(gb.repo / "CLAUDE.md")) in _said(out)[0]
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
    assert _names(owner, gb.repo / "CLAUDE.md") and model


def test_r3_the_checkpoint_line_comes_first(gb, monkeypatch):
    small = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": "CHECKPOINT: 80%"}}
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: small)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("z\n"))
    model, owner = _said(out)
    assert model.startswith("CHECKPOINT: 80%\n\n") and owner.startswith("agentik-session: ")
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_r3_several_paths_name_the_first_and_how_many_more(gb):
    def act():
        (gb.repo / "CLAUDE.md").write_text("1\n")
        (gb.repo / "AGENTS.md").write_text("2\n")
    _, out = _run(gb, UNREAD, act)
    assert _names(_said(out)[1], gb.repo / "AGENTS.md", 1)


# ---- brief 2, the fix of review 1: the line bounded (F2), held before it is said (F1), the
# path whole (F3) --------------------------------------------------------------------------

PAIR = 480                                      # F2: the pair beside `{}`, at most


def _said_dir(b):
    return _sdir(b) / instructionguard.SAID_DIR


def _said_files(b):
    d = _said_dir(b)
    return sorted(os.listdir(d)) if d.is_dir() else []


def _waiting(b):
    """Brief 3 H1: every path that waits, one small file a change, in the files' order."""
    out = []
    for name in _said_files(b):
        out += json.loads((_said_dir(b) / name).read_text())["paths"]
    return out


def _hold(b, paths):
    instructionguard._hold(_said_dir(b), paths)


OWN = "1700000000000000000-1-0.said"            # brief 4 J2: a name the check gives a waiting file


@pytest.fixture
def deep(tmp_path, monkeypatch):
    """A worktree-shaped checkout under a long home path, its list naming two files."""
    class B:
        pass
    b = B()
    b.home = tmp_path / "home" / "a-rather-long-user-name"
    (b.home / ".claude").mkdir(parents=True)
    b.env = {"HOME": str(b.home), "XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"}
    for k in ("HOME", "XDG_STATE_HOME"):
        monkeypatch.setenv(k, b.env[k])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    b.state = resolver.state_dir(b.env)
    b.wt = b.home / "code" / "suite" / "some-tool" / ".claude" / "worktrees" / "row-with-a-name"
    (b.wt / ".claude").mkdir(parents=True)
    (b.wt / ".git").write_text("gitdir: /nowhere\n")
    (b.wt / ".claude" / "edit-gates").write_text("CLAUDE.md\nAGENTS.md\n")
    for n in ("CLAUDE.md", "AGENTS.md"):
        (b.wt / n).write_text("# x\n")
    (b.wt / "plugin").mkdir()
    return b


def test_f2_two_files_of_a_long_home_worktree_are_said_at_their_own_post(deep):
    p = _bash(UNREAD, deep.wt / "plugin", tid="toolu_f2_1")
    hooks.pre_tool_use(p, deep.env)
    (deep.wt / "CLAUDE.md").write_text("1\n")
    (deep.wt / "AGENTS.md").write_text("1\n")
    out = hooks.post_tool_use(_post(p), deep.env)
    model, owner = _said(out)
    assert _names(owner, "~/" + str((deep.wt / "AGENTS.md").relative_to(deep.home)), 1), owner
    assert model == MODEL.format(owner[len(OWNER.format("")):])
    assert len(json.dumps(out)) <= hooks.MAX_OUT and _waiting(deep) == []
    p2 = _bash(UNREAD, deep.wt, tid="toolu_f2_2")          # a later change: its own Post too
    hooks.pre_tool_use(p2, deep.env)
    (deep.wt / "CLAUDE.md").write_text("2\n")
    out = hooks.post_tool_use(_post(p2), deep.env)
    assert _names(_said(out)[1], "~/" + str((deep.wt / "CLAUDE.md").relative_to(deep.home)))
    assert _open_files(deep) == []


def test_f2_seventy_long_paths_are_one_bounded_pair_and_all_taken(gb):
    paths = [f"/made-up/{i:02d}/" + "p" * 188 for i in range(70)]
    assert {len(p) for p in paths} == {200}
    _hold(gb, paths)
    out = hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_f2_3")), gb.env)
    model, owner = _said(out)
    assert len(json.dumps(out)) <= PAIR
    assert _names(owner, sorted(paths)[0], 69) and "(+69 more)" in model
    assert _waiting(gb) == [] and _open_files(gb) == []


def test_f2_a_handler_that_leaves_no_room_waits_then_one_post_says_it(gb, monkeypatch):
    full = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "additionalContext": "CHECKPOINT: " + "w" * 500}}
    real = hooks._post_tool_use
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: full)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("z\n"))
    assert out == full and _waiting(gb) == [str(gb.repo / "CLAUDE.md")]
    monkeypatch.setattr(hooks, "_post_tool_use", real)
    said = [_said(hooks.post_tool_use(_post(_bash("ls", gb.repo, tid=f"toolu_f2_n{i}")),
                                      gb.env))[1] for i in range(31)]
    assert said[0] == OWNER.format(_drawn(gb.repo / "CLAUDE.md")) and said[1:] == [""] * 30
    assert _open_files(gb) == []


@pytest.mark.parametrize("record", [b'{"paths": 5}', b'{"paths": "abc"}', b'"abc"',
                                    b'\xff\x00garbage{', b'{"paths": ["a", 5]}'])
def test_f1_a_corrupt_waiting_record_loses_no_change(gb, record):
    folder = _said_dir(gb)
    folder.mkdir(parents=True)
    (folder / OWN).write_bytes(record)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("c\n"))
    assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    rows = [(r["decision"], bool(r["why"])) for r in _log(gb)]
    assert sorted(rows) == [("changed", False), ("open", True)]
    assert _open_files(gb) == [] and _said_files(gb) == []


def test_f1_corrupt_records_one_after_another_each_say_their_change(gb):
    folder = _said_dir(gb)
    for i, record in enumerate([b'{"paths": 5}', b'"a string"', b'\x00\x01\x02']):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / OWN).write_bytes(record)
        _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text(f"{i}\n"),
                      tid=f"toolu_f1_{i}")
        assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
        assert [r["decision"] for r in _log(gb)].count("open") == i + 1


def test_f1_a_handler_that_raises_after_the_reading_loses_no_change(gb, monkeypatch):
    def boom(payload, env):
        raise RuntimeError("the handler")
    real = hooks._post_tool_use
    monkeypatch.setattr(hooks, "_post_tool_use", boom)
    p = _bash(UNREAD, gb.repo)
    hooks.pre_tool_use(p, gb.env)
    (gb.repo / "CLAUDE.md").write_text("r\n")
    with pytest.raises(RuntimeError):
        hooks.post_tool_use(_post(p), gb.env)
    assert [r["decision"] for r in _log(gb)] == ["changed"]
    monkeypatch.setattr(hooks, "_post_tool_use", real)
    out = hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_f1_next")), gb.env)
    assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))


def test_f3_a_helpers_worktree_change_is_said_with_the_worktrees_path(gb):
    p = _bash(UNREAD, gb.wt, tid="toolu_f3_1", agent_id="helper-1")
    hooks.pre_tool_use(p, gb.env)
    (gb.wt / "CLAUDE.md").write_text("wt\n")
    assert hooks.post_tool_use(_post(p), gb.env) == {}
    out = hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_f3_2")), gb.env)
    owner = _said(out)[1]
    assert owner == OWNER.format(_drawn(gb.wt / "CLAUDE.md"))
    assert owner != OWNER.format("CLAUDE.md") and "worktrees/row/CLAUDE.md" in owner


def test_f3_one_file_by_two_spellings_waits_once(gb):
    link = gb.tmp / "link"
    link.symlink_to(gb.repo)
    with open(gb.home / ".claude" / "edit-gates", "a") as f:
        f.write(f"{link}/./CLAUDE.md\n{gb.repo}/CLAUDE.md\n")
    with open(gb.repo / ".claude" / "edit-gates", "a") as f:
        f.write("./CLAUDE.md\n")
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("s\n"),
                  event="PostToolUseFailure")
    assert _waiting(gb) == [str(gb.repo / "CLAUDE.md")]
    assert [r["path"] for r in _log(gb)] == [str(gb.repo / "CLAUDE.md")]


def test_f2_a_prompt_with_seventy_waiting_paths_stays_within_max_out(gb):
    _hold(gb, [str(gb.tmp / f"d{i:02d}" / "CLAUDE.md") for i in range(70)])
    out = hooks.user_prompt_submit({"session_id": SID, "prompt": "go"})
    assert len(json.dumps(out)) <= hooks.MAX_OUT
    assert _names(_said(out)[1], gb.tmp / "d00" / "CLAUDE.md", 69)
    assert _waiting(gb) == []


def test_h1_each_waiting_change_is_its_own_file_never_rewritten(gb, monkeypatch):
    full = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "additionalContext": "CHECKPOINT: " + "w" * 500}}
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: full)
    _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("1\n"), tid="toolu_f1_a")
    [first] = _said_files(gb)
    stamp = (_said_dir(gb) / first).stat().st_mtime_ns
    for i in range(5):
        hooks.post_tool_use(_post(_bash("ls", gb.repo, tid=f"toolu_f1_l{i}")), gb.env)
    _run(gb, UNREAD, lambda: (gb.repo / "AGENTS.md").write_text("2\n"), tid="toolu_f1_b")
    assert (_said_dir(gb) / first).stat().st_mtime_ns == stamp
    assert len(_said_files(gb)) == 2 and _open_files(gb) == []
    assert _waiting(gb) == [str(gb.repo / "CLAUDE.md"), str(gb.repo / "AGENTS.md")]


# ---- brief 3, the fix of review 2: one small file a change, no lock, no folder removed ---------

LIB = os.path.dirname(os.path.dirname(instructionguard.__file__))
MORE = re.compile(r" \(\+(\d+) more\)\Z")


class _Hung(BaseException):
    """Raised by the alarm into a hook that waits, so a regression fails and never hangs."""


def _bounded(fn, wall=3.0):
    """`fn()` and its seconds; a call still running after `wall` is a failed test."""
    def ring(*_):
        raise _Hung()
    old = signal.signal(signal.SIGALRM, ring)
    signal.setitimer(signal.ITIMER_REAL, wall)
    try:
        t = time.monotonic()
        out = fn()
        return out, time.monotonic() - t
    except _Hung:
        pytest.fail(f"a hook still ran after {wall} s")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _changed(b, tid, name="CLAUDE.md", text=None):
    """One unread line's Pre and its change, the test's own write; the Post's payload."""
    p = _bash(UNREAD, b.repo, tid=tid)
    hooks.pre_tool_use(p, b.env)
    (b.repo / name).write_text(text or tid + "\n")
    return _post(p)


def _count(owner):
    """How many paths one owner's line stands for: the one drawn and its `(+N more)`."""
    if not owner:
        return 0
    m = MORE.search(owner)
    return 1 + (int(m.group(1)) if m else 0)


@pytest.mark.parametrize("when", ["before its write", "after its write"])
def test_h1_review_2_b1_another_post_with_nothing_waiting_loses_no_change(gb, monkeypatch, when):
    """Acceptance 1: another main-thread Post of the session ends with nothing waiting while
    this Post holds its change; the change is said once, at its own Post or the next."""
    real = instructionguard._write_record
    others = []

    def other():
        return hooks.post_tool_use(_post(_bash("ls", gb.repo, tid=f"toolu_h1_o{len(others)}")),
                                   gb.env)

    def racing(folder, name, doc, *a, **k):
        if when == "before its write":
            others.append(other())
        real(folder, name, doc, *a, **k)
        if when == "after its write":
            others.append(other())
    p = _changed(gb, "toolu_h1_b1")
    monkeypatch.setattr(instructionguard, "_write_record", racing)
    out, _ = _bounded(lambda: hooks.post_tool_use(p, gb.env))     # a lock would wait here
    monkeypatch.setattr(instructionguard, "_write_record", real)
    later = [hooks.post_tool_use(_post(_bash("ls", gb.repo, tid=f"toolu_h1_l{i}")), gb.env)
             for i in range(3)]
    owners = [_said(o)[1] for o in [out] + others + later]
    assert others and sum(o == OWNER.format(_drawn(gb.repo / "CLAUDE.md")) for o in owners) == 1
    assert [r["decision"] for r in _log(gb)] == ["changed"]
    assert _waiting(gb) == [] and _said_dir(gb).is_dir()


STRESS = """
import json, os, sys
env = json.loads(sys.argv[1]); os.environ.update(env)
from claude_session import hooks, instructionguard
k, sid, root = int(sys.argv[2]), sys.argv[3], sys.argv[4]
taken, real = [], instructionguard.taken
def counted(payload, e, waiting):
    real(payload, e, waiting)
    taken.extend(waiting)
instructionguard.taken = counted
folder = instructionguard._open_dir({"session_id": sid}, env)
owners = []
for i in range(25):
    tid = "toolu_s%d_%d" % (k, i)
    path = os.path.join(root, "p%d-%d" % (k, i), "CLAUDE.md")
    instructionguard._write_record(folder, tid + ".json", {"at": 0, "files": [[path, ["absent"]]]})
    out = hooks.post_tool_use({"session_id": sid, "cwd": root, "hook_event_name": "PostToolUse",
                               "tool_name": "Bash", "tool_use_id": tid,
                               "tool_input": {"command": "x"}, "tool_response": {}}, env)
    owners.append(out.get("systemMessage") or "")
print(json.dumps({"owners": owners, "taken": taken}))
"""


def test_h2_eight_processes_of_25_posts_say_every_change(gb):
    """Acceptance 2: 200 changes in 8 processes at once; each path in some output's line or
    count, no call raises, and after one last Post nothing waits."""
    root = gb.tmp / "stress"
    every = set()
    for k in range(8):
        for i in range(25):
            d = root / f"p{k}-{i}"
            d.mkdir(parents=True)
            (d / "CLAUDE.md").write_text("x\n")
            every.add(os.path.realpath(d / "CLAUDE.md"))
    env = {**gb.env, "CLAUDE_CODE_SESSION_ID": SID, "PYTHONPATH": LIB}
    procs = [subprocess.Popen([sys.executable, "-c", STRESS, json.dumps(env), str(k), SID,
                               str(root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, text=True) for k in range(8)]
    runs = [p.communicate(timeout=120) for p in procs]
    assert [(p.returncode, err) for p, (_, err) in zip(procs, runs)] == [(0, "")] * 8
    docs = [json.loads(out) for out, _ in runs]
    assert sum(_count(o) for d in docs for o in d["owners"]) >= 200
    assert set().union(*(d["taken"] for d in docs)) == every
    assert [r["decision"] for r in _log(gb)] == ["changed"] * 200
    hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_s_last")), gb.env)
    assert _waiting(gb) == [] and _said_files(gb) == [] and _open_files(gb) == []


def _plant(b, shape):
    d = _said_dir(b)
    d.mkdir(parents=True, exist_ok=True)
    at = d / OWN
    big = b.tmp / "big.bin"
    big.write_bytes(b"a" * (2 << 20))
    if shape == "a directory":
        at.mkdir()
    elif shape == "a FIFO":
        os.mkfifo(at)                   # never opened by the test
    elif shape == "a dangling link":
        at.symlink_to(b.tmp / "nowhere")
    elif shape == "a link to 2 MiB":
        at.symlink_to(big)
    else:
        at.write_bytes({"2 MiB": b"[" * (2 << 20), "garbage": b"\xff\x00\x13garbage{",
                        "paths 5": b'{"paths": 5}', "a string": b'"a string"'}[shape])
    return at


NOT_REGULAR = ("a directory", "a FIFO", "a dangling link", "a link to 2 MiB")


@pytest.mark.parametrize("shape", [*NOT_REGULAR, "2 MiB", "garbage", "paths 5", "a string"])
def test_h3_a_bad_waiting_entry_never_blocks_the_next_change(gb, shape):
    """Acceptance 3: the next change is said at its own Post within half a second. A regular
    file of the check's own naming that is bad is one guard error and gone; an entry that is
    no regular file is left as it is and logged never (brief 4 J2). A later Post logs no more."""
    at = _plant(gb, shape)
    try:
        p = _changed(gb, "toolu_h3")
        out, took = _bounded(lambda: hooks.post_tool_use(p, gb.env))
        assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md")) and took < 0.5
        rows = _log(gb)
        bad = shape not in NOT_REGULAR
        assert sorted(r["decision"] for r in rows) == ["changed"] + ["open"] * bad
        assert all(r["why"] for r in rows if r["decision"] == "open")
        assert os.path.lexists(at) != bad and (gb.tmp / "big.bin").exists()
        _bounded(lambda: hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_h3_n")),
                                             gb.env))
        assert len(_log(gb)) == 1 + bad and _said_files(gb) == ([] if bad else [OWN])
    finally:
        if os.path.lexists(at) and not os.path.isdir(at):
            os.remove(at)


def test_h3_a_temp_older_than_a_minute_is_removed(gb):
    d = _said_dir(gb)
    d.mkdir(parents=True)
    old, young, other = f".{OWN}.1.tmp", f".{OWN}.2.tmp", ".old.said.1.tmp"
    for name in (old, young, other):
        (d / name).write_text("{")
    then = time.time() - 120
    for name in (old, other):
        os.utime(d / name, (then, then))
    hooks.post_tool_use(_changed(gb, "toolu_h3_t"), gb.env)
    assert _said_files(gb) == sorted([young, other]) and _log(gb)[-1]["decision"] == "changed"


def test_h2_one_saying_reads_at_most_256_entries(gb):
    for i in range(300):
        _hold(gb, [str(gb.tmp / f"w{i:03d}" / "CLAUDE.md")])
    assert len(_said_files(gb)) == 300
    first = _said(hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_h2_1")), gb.env))[1]
    assert first.endswith(" (+255 more)") and len(_said_files(gb)) == 44
    second = _said(hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_h2_2")), gb.env))[1]
    assert second.endswith(" (+43 more)") and _said_files(gb) == []


def test_h2_a_line_that_does_not_fit_removes_no_file(gb, monkeypatch):
    _hold(gb, [str(gb.repo / "CLAUDE.md")])
    full = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                   "additionalContext": "CHECKPOINT: " + "w" * 500}}
    monkeypatch.setattr(hooks, "_post_tool_use", lambda payload, env: full)
    assert hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_h2_f")), gb.env) == full
    assert _waiting(gb) == [str(gb.repo / "CLAUDE.md")]


_HOLDER = """
import fcntl, os, sys, time
fds = [os.open(p, os.O_RDONLY) for p in sys.argv[1:]]
for fd in fds:
    fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(3)
"""


def test_h1_a_held_flock_delays_no_hook(gb):
    """Acceptance 4: an exclusive `flock` on the session's folder and both of the gate's, held
    for three seconds, delays neither the Pre nor the Post of an unread line past 0.25 s."""
    folders = [_sdir(gb), _sdir(gb) / instructionguard.OPEN_DIR, _said_dir(gb)]
    for f in folders:
        f.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen([sys.executable, "-c", _HOLDER, *map(str, folders)],
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        p = _bash(UNREAD, gb.repo, tid="toolu_h1_lock")
        pre, pre_took = _bounded(lambda: hooks.pre_tool_use(p, gb.env))
        (gb.repo / "CLAUDE.md").write_text("held\n")
        out, post_took = _bounded(lambda: hooks.post_tool_use(_post(p), gb.env))
        assert holder.poll() is None
        assert pre == {} and pre_took < 0.25 and post_took < 0.25
        assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    finally:
        holder.kill()
        holder.wait()


def test_h4_no_hook_removes_a_folder(gb):
    """Acceptance 5: 400 unread lines that change nothing and 20 that change and are said leave
    both folders, empty."""
    for i in range(400):
        _run(gb, UNREAD, tid=f"toolu_h4_{i:04d}")
    for i in range(20):
        out = hooks.post_tool_use(_changed(gb, f"toolu_h4_c{i:02d}"), gb.env)
        assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    for f in (_sdir(gb) / instructionguard.OPEN_DIR, _said_dir(gb)):
        assert f.is_dir() and os.listdir(f) == []


def test_h5_a_change_that_cannot_wait_is_a_guard_error_said_at_its_own_post(gb, monkeypatch):
    real = instructionguard._write_record

    def refuse(folder, name, doc, *a, **k):
        if name.endswith(".said"):
            raise PermissionError("read-only")
        return real(folder, name, doc, *a, **k)
    p = _changed(gb, "toolu_h5")
    monkeypatch.setattr(instructionguard, "_write_record", refuse)
    out = hooks.post_tool_use(p, gb.env)
    assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    assert [(r["decision"], r["why"]) for r in _log(gb)] == \
        [("changed", None), ("open", "PermissionError")]


def test_h6_a_control_character_in_a_drawn_path_is_a_question_mark(gb):
    """Acceptance 6: a newline and an escape in a path are each `?`; the pair within 480 B."""
    path = "/made-up/a\nb\x1bc/CLAUDE.md"
    _hold(gb, [path])
    out = hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_h6")), gb.env)
    model, owner = _said(out)
    assert owner == OWNER.format("/made-up/a?b?c/CLAUDE.md") and "?b?c" in model
    assert not any(c in model + owner for c in "\n\x1b") and len(json.dumps(out)) <= PAIR


# ---- brief 4, the fix of review 3: a call's paths split; only its own files; no folder no use --

def _posts(b, n, tag):
    """`n` main-thread Posts of a line the gate reads, each's owner line."""
    return [_said(hooks.post_tool_use(_post(_bash("ls", b.repo, tid=f"toolu_{tag}{i}")),
                                      b.env))[1] for i in range(n)]


def _kept(folder):
    """Each entry's name, kind, bytes and mtime, unfollowed: what a test asserts untouched."""
    out = {}
    for name in sorted(os.listdir(folder)):
        st = os.lstat(folder / name)
        body = (folder / name).read_bytes() if os.path.isfile(folder / name) else None
        out[name] = (st.st_mode, st.st_mtime_ns, body)
    return out


def test_j1_sixty_three_paths_past_64_kib_are_said_at_their_own_post(gb):
    """Acceptance 1 (review 3's B1): one unread line changes 63 gated files whose paths make
    more than 64 KiB of JSON; its own Post says the first and `(+62 more)`; nothing waits."""
    deep = os.path.join(*(['"' * 100 + "d" * 150] * 3))
    (gb.repo / deep).mkdir(parents=True)
    names = [f"{deep}/f{i:02d}.md" for i in range(63)]
    (gb.repo / ".claude" / "edit-gates").write_text("".join(n + "\n" for n in names))
    (gb.home / ".claude" / "edit-gates").unlink()      # the list and its 63 make RECORD_CAP
    for n in names:
        (gb.repo / n).write_text("x\n")
    real = [os.path.realpath(gb.repo / n) for n in names]
    assert len(json.dumps({"paths": real}, ensure_ascii=False).encode()) > instructionguard.SAID_CAP
    _, out = _run(gb, UNREAD, lambda: [(gb.repo / n).write_text("y\n") for n in names])
    model, owner = _said(out)
    assert _names(owner, sorted(real)[0], 62) and "(+62 more)" in model
    assert {r["decision"] for r in _log(gb)} == {"changed"}    # as many as LOG_CAP holds
    assert _said_files(gb) == [] and _posts(gb, 2, "j1_") == ["", ""]


def test_j2_fifteen_hundred_folders_hide_no_change_and_are_never_touched(gb):
    """Acceptance 2 (B3): 1500 non-empty folders and 20 held changes; one Post with room says
    all 20; no folder is touched; five more Posts grow the log by 0 bytes."""
    d = _said_dir(gb)
    d.mkdir(parents=True)
    for i in range(1500):                        # half of them named as a waiting file would be
        f = d / (f"1-1-{i}.said" if i % 2 else f"dir{i:04d}")
        f.mkdir()
        (f / "inside").write_text("kept\n")
    paths = [str(gb.tmp / f"c{i:02d}" / "CLAUDE.md") for i in range(20)]
    for p in paths:
        _hold(gb, [p])
    before = _kept(d)
    first = _said(hooks.post_tool_use(_post(_bash("ls", gb.repo, tid="toolu_j2_0")), gb.env))[1]
    assert _names(first, sorted(paths)[0], 19)
    log = _sdir(gb) / instructionguard.LOG
    size = log.stat().st_size if log.exists() else 0
    assert _posts(gb, 5, "j2_") == [""] * 5
    assert (log.stat().st_size if log.exists() else 0) == size == 0
    kept = _kept(d)
    assert len(kept) == 1500 and all(kept[k] == before[k] for k in kept)
    assert all((d / k / "inside").read_text() == "kept\n" for k in kept)


def _user_folder(b):
    """A user's folder of three files: a note, one named as a waiting file would be (whose
    path the check would say), and an old temp of the check's own naming."""
    u = b.tmp / "user-folder"
    u.mkdir()
    (u / "notes.txt").write_text("mine\n")
    (u / OWN).write_text(json.dumps({"paths": ["/made-up/elsewhere/CLAUDE.md"]}))
    (u / f".{OWN}.1.tmp").write_text("{")
    then = time.time() - 3 * 86400
    for name in os.listdir(u):
        os.utime(u / name, (then, then))
    return u


def test_j3_a_waiting_folder_that_is_a_link_is_never_used(gb):
    """Acceptance 3 (L1): `guard-said` a link to a user's folder: after a Pre, a Post that
    finds a change and five more Posts, the folder's three files keep their bytes and mtimes;
    the change is said at its own Post; one guard error, not six."""
    u = _user_folder(gb)
    before = _kept(u)
    _sdir(gb).mkdir(parents=True, exist_ok=True)
    _said_dir(gb).symlink_to(u)
    _, out = _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text("j3\n"))
    assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    assert _posts(gb, 5, "j3_") == [""] * 5
    assert _kept(u) == before and _said_dir(gb).is_symlink()
    rows = [(r["decision"], r["why"]) for r in _log(gb)]
    assert [d for d, _ in rows] == ["changed", "open"] and "guard-said" in rows[1][1]


@pytest.mark.parametrize("shape", ["a link", "a file"])
def test_j3_an_open_folder_that_is_no_folder_is_never_used(gb, shape):
    """J3: `guard-open` a link to a user's folder, or a file: three unread lines write, read
    and remove nothing there; one guard error for the session."""
    _sdir(gb).mkdir(parents=True, exist_ok=True)
    at = _sdir(gb) / instructionguard.OPEN_DIR
    if shape == "a link":
        u = _user_folder(gb)
        (u / "toolu_gc1_0001.json").write_text("{}")
        os.utime(u / "toolu_gc1_0001.json", (time.time() - 3 * 86400,) * 2)
        at.symlink_to(u)
        kept = lambda: _kept(u)                 # noqa: E731
    else:
        at.write_text("a file\n")
        kept = lambda: _kept(_sdir(gb))[instructionguard.OPEN_DIR]     # noqa: E731
    before = kept()
    for i in range(3):
        _run(gb, UNREAD, lambda: (gb.repo / "CLAUDE.md").write_text(f"{i}\n"), tid=f"toolu_j3o{i}")
    assert kept() == before and os.path.lexists(at)
    assert [(r["decision"], "guard-open" in (r["why"] or "")) for r in _log(gb)] == [("open", True)]


def test_j2_a_note_and_a_folder_stay_and_garbage_of_its_own_name_goes(gb):
    """Acceptance 4: in a real waiting folder `notes.txt` and a folder named as a waiting file
    stay, untouched and never logged, through ten sayings; a regular file of the check's own
    naming that holds garbage is removed with one guard error."""
    d = _said_dir(gb)
    d.mkdir(parents=True)
    (d / "notes.txt").write_text("mine\n")
    (d / "1-1-1.said").mkdir()
    keep = _kept(d)
    (d / OWN).write_bytes(b"\xff garbage {")
    for i in range(10):
        out = hooks.post_tool_use(_changed(gb, f"toolu_j2n{i}"), gb.env)
        assert _said(out)[1] == OWNER.format(_drawn(gb.repo / "CLAUDE.md"))
    assert _kept(d) == keep
    rows = [r["decision"] for r in _log(gb)]
    assert rows.count("open") == 1 and rows.count("changed") == 10
