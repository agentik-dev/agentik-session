"""Packet g4: the folder layer of the edit gates (hq design/12 §3.2, §3.4, §3.5). A folder's
`.claude/edit-gates` under the home folder covers every repo below it, lines relative to the
folder; one glob grammar holds in every layer: `*` stays in a segment, `**` alone is any depth.
Every test builds its lists in a temp folder with a patched home; none reads a real list."""
from __future__ import annotations

import builtins
import io
import os
import subprocess
from pathlib import Path

import pytest

from claude_session import hooks, instructionguard
from test_g2b_gates import REASON, SID, _bash, _cli, _decision, _hash, _log, _payload

FOLDER_LIST = ("# the edit gates for every repo under this folder\nCLAUDE.md\n*/CLAUDE.md\n"
               "*/DECISIONS.md\n/abs.md\n~/tilde.md\n../up.md\nsub/../x.md\n")


@pytest.fixture
def fb(tmp_path, monkeypatch):
    """home/code/tree holds a folder list; tree/member is a checkout with no list of its own,
    a worktree under it; home/code/sib is a sibling folder with its own list."""
    class B:
        pass
    b = B()
    b.tmp = tmp_path
    b.home = tmp_path / "home"
    (b.home / ".claude").mkdir(parents=True)
    (b.home / ".claude" / "edit-gates").write_text("~/.claude/settings.json\n")
    b.env = {"HOME": str(b.home), "XDG_STATE_HOME": str(tmp_path / "state"),
             "PATH": "/usr/bin:/bin"}
    monkeypatch.setenv("HOME", str(b.home))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    b.code = b.home / "code"
    b.tree = b.code / "tree"
    (b.tree / ".claude").mkdir(parents=True)
    b.flist = b.tree / ".claude" / "edit-gates"
    b.flist.write_text(FOLDER_LIST)
    b.member = b.tree / "member"
    (b.member / ".git").mkdir(parents=True)
    b.wt = b.member / ".claude" / "worktrees" / "row"
    gitdir = b.member / ".git" / "worktrees" / "row"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    b.wt.mkdir(parents=True)
    (b.wt / ".git").write_text(f"gitdir: {gitdir}\n")
    b.sib = b.code / "sib"
    (b.sib / ".claude").mkdir(parents=True)
    (b.sib / ".claude" / "edit-gates").write_text("*/notes.md\nmember/notes.md\n")
    return b


def _denied(b, p, tool="Edit") -> bool:
    out = instructionguard.check(_payload(tool, p), b.env)
    if out == {}:
        return False
    assert _decision(out) == ("deny", REASON.format(os.path.normpath(str(p)))), p
    return True


# ---- 1: a folder list gates each member's top-level files -------------------------------

def test_1_the_folder_list_gates_a_members_top_level_files(fb):
    for p in (fb.member / "CLAUDE.md", fb.member / "DECISIONS.md"):
        out = hooks.pre_tool_use(_payload("Edit", p), fb.env)
        assert _decision(out) == ("deny", REASON.format(p)), p
    for p in (fb.member / "docs" / "x" / "CLAUDE.md", fb.member / "notes.md",
              fb.member / "AGENTS.md"):
        assert hooks.pre_tool_use(_payload("Edit", p), fb.env) == {}, p
    assert [r["decision"] for r in _log(fb)] == ["deny", "deny"]


BASH_DENIED = ["echo x >> CLAUDE.md", "echo x | tee CLAUDE.md", "sed -i '' s/a/b/ DECISIONS.md",
               "cp /tmp/x CLAUDE.md", "bash -c 'echo x > CLAUDE.md'",
               "python3 -c \"open('CLAUDE.md', 'a').write('x')\"",
               "cat > CLAUDE.md <<EOF\nline\nEOF"]


@pytest.mark.parametrize("command", BASH_DENIED)
def test_1_each_bash_form_family_denies(fb, command):
    out = instructionguard.check(_bash(command, fb.member), fb.env)
    assert _decision(out)[0] == "deny", command


@pytest.mark.parametrize("command", ["echo x >> docs/x/CLAUDE.md", "echo x >> notes.md",
                                     "cp /tmp/x docs/x/CLAUDE.md"])
def test_1_a_deeper_or_unlisted_file_passes_bash(fb, command):
    assert instructionguard.check(_bash(command, fb.member), fb.env) == {}, command


# ---- 2: the layers do not lean on each other ---------------------------------------------

def test_2_the_member_list_alone_and_the_folder_list_alone(fb):
    assert _denied(fb, fb.member / "CLAUDE.md")             # the folder's, no list of its own
    fb.flist.unlink()
    assert not _denied(fb, fb.member / "CLAUDE.md")
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("CLAUDE.md\n")
    assert _denied(fb, fb.member / "CLAUDE.md")             # its own, no folder list


# ---- 3: a worktree is matched by its place in the member ---------------------------------

def test_3_a_worktrees_claude_md_is_denied_by_the_folder_list(fb):
    assert _denied(fb, fb.wt / "CLAUDE.md")
    assert _denied(fb, fb.wt / "DECISIONS.md")
    assert not _denied(fb, fb.wt / "docs" / "CLAUDE.md")
    assert not _denied(fb, fb.wt / "notes.md")
    out = instructionguard.check(_bash("echo x >> CLAUDE.md", fb.wt), fb.env)
    assert _decision(out)[0] == "deny"


# ---- 4: the folder's own file and its list -----------------------------------------------

def test_4_the_folders_own_claude_md(fb):
    assert _denied(fb, fb.tree / "CLAUDE.md")
    assert not _denied(fb, fb.tree / "README.md")


def test_4_the_folder_list_is_gated_unlisted(fb):
    for tool in ("Edit", "Write"):
        assert _denied(fb, fb.flist, tool)
    assert _denied(fb, fb.code / "new" / ".claude" / "edit-gates", "Write")   # absent: still
    assert _denied(fb, fb.sib / ".claude" / "edit-gates")


@pytest.mark.parametrize("command", ["echo x >> .claude/edit-gates", "rm .claude/edit-gates",
                                     "mv .claude/edit-gates /tmp/x", "rm -rf .claude",
                                     "unlink .claude/edit-gates", "mv /tmp/x .claude/edit-gates",
                                     "cd member && rm ../.claude/edit-gates"])
def test_4_the_folder_list_by_bash_and_its_removal(fb, command):
    out = instructionguard.check(_bash(command, fb.tree), fb.env)
    assert _decision(out) == ("deny", REASON.format(fb.flist)), command


def test_4_a_list_inside_a_checkout_is_no_folder_list(fb):
    fx = fb.member / "tests" / "fx"
    (fx / ".claude").mkdir(parents=True)
    (fx / ".claude" / "edit-gates").write_text("CLAUDE.md\n")
    assert not _denied(fb, fx / "CLAUDE.md")
    assert not _denied(fb, fx / ".claude" / "edit-gates")
    assert instructionguard.check(_bash("rm -rf tests/fx/.claude", fb.member), fb.env) == {}


# ---- 5: one grammar in every layer -------------------------------------------------------

def test_5_star_stays_in_a_segment_in_every_layer(fb):
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("*.md\n")
    fb.flist.write_text("*.txt\n")
    (fb.home / ".claude" / "edit-gates").write_text("~/notes/*.md\n")
    assert _denied(fb, fb.member / "top.md")
    assert not _denied(fb, fb.member / "deep" / "a" / "b.md")
    assert _denied(fb, fb.tree / "a.txt")
    assert not _denied(fb, fb.tree / "deep" / "a" / "b.txt")
    assert _denied(fb, fb.home / "notes" / "a.md")
    assert not _denied(fb, fb.home / "notes" / "deep" / "a" / "b.md")


def test_5_double_star_is_any_depth(fb):
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("**/x.md\nhooks/**\n")
    fb.flist.write_text("**/y.md\n")
    (fb.home / ".claude" / "edit-gates").write_text("~/.claude/hooks/**\n")
    for p in (fb.member / "x.md", fb.member / "a" / "b" / "x.md", fb.member / "hooks" / "a",
              fb.member / "hooks" / "a" / "b" / "c.py", fb.tree / "y.md",
              fb.member / "a" / "y.md", fb.home / ".claude" / "hooks" / "a" / "b.sh"):
        assert _denied(fb, p), p
    for p in (fb.member / "xx.md", fb.member / "hook" / "a", fb.member / "a" / "x.md.bak"):
        assert not _denied(fb, p), p


def test_5_a_refused_folder_line_matches_nothing(fb):
    for p in (fb.tree / "abs.md", Path("/abs.md"), fb.tree / "~" / "tilde.md",
              fb.home / "tilde.md", fb.code / "up.md", fb.tree / "up.md", fb.tree / "x.md"):
        assert not _denied(fb, p), p


def test_5_a_tilde_line_in_a_checkout_list_matches_nothing(fb):
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("~/x.md\n")
    assert not _denied(fb, fb.member / "~" / "x.md")
    assert not _denied(fb, fb.home / "x.md")


# ---- 6: which folder lists apply ---------------------------------------------------------

def test_6_two_folder_lists_both_apply(fb):
    (fb.code / ".claude").mkdir()
    (fb.code / ".claude" / "edit-gates").write_text("tree/member/AGENTS.md\n")
    assert _denied(fb, fb.member / "AGENTS.md")
    assert _denied(fb, fb.member / "CLAUDE.md")


def test_6_a_sibling_folders_list_never_applies(fb):
    assert not _denied(fb, fb.member / "notes.md")
    assert _denied(fb, fb.sib / "x" / "notes.md")


def test_6_a_path_outside_home_reads_no_folder_list(fb):
    out_tree = fb.tmp / "elsewhere" / "tree"
    (out_tree / ".claude").mkdir(parents=True)
    (out_tree / ".claude" / "edit-gates").write_text(FOLDER_LIST)
    (out_tree / "member" / ".git").mkdir(parents=True)
    for p in (out_tree / "member" / "CLAUDE.md", out_tree / "CLAUDE.md",
              out_tree / ".claude" / "edit-gates"):
        assert not _denied(fb, p), p


def test_6_the_home_folders_own_list_stays_the_owners(fb):
    (fb.home / ".claude" / "edit-gates").write_text("~/.claude/settings.json\nCLAUDE.md\n")
    assert not _denied(fb, fb.home / "CLAUDE.md")


# ---- 7: the lane writes a folder list ----------------------------------------------------

@pytest.fixture
def flane(fb, monkeypatch):
    fb.draft = fb.tmp / "draft"
    fb.draft.write_text(FOLDER_LIST.split("/abs.md")[0] + "*/AGENTS.md\n")
    monkeypatch.chdir(fb.tree)
    return fb


def test_7_preview_writes_nothing_and_expect_writes(flane, capsys):
    clean = "CLAUDE.md\n*/CLAUDE.md\n"
    flane.flist.write_text(clean)
    before = flane.flist.read_bytes()
    code, out, err = _cli(capsys, "gates", "write", str(flane.flist), "--from", str(flane.draft),
                          "--preview")
    assert code == 0, err
    assert flane.flist.read_bytes() == before
    code, out, err = _cli(capsys, "gates", "write", str(flane.flist), "--from", str(flane.draft),
                          "--expect", _hash(out))
    assert code == 0, err
    assert flane.flist.read_text() == flane.draft.read_text()


@pytest.mark.parametrize("line", ["/abs.md", "~/x.md", "~", "../up.md", "a/../../b.md"])
def test_7_a_refused_line_writes_nothing(flane, capsys, line):
    flane.draft.write_text("CLAUDE.md\n" + line + "\n")
    before = flane.flist.read_bytes()
    h = instructionguard.lane_hash(before, flane.draft.read_bytes())
    for extra in ([], ["--expect", h]):
        code, out, err = _cli(capsys, "gates", "write", ".claude/edit-gates", "--from",
                              str(flane.draft), *extra)
        assert code != 0 and line in err and "nothing written" in err, (extra, err)
    assert flane.flist.read_bytes() == before


def test_7_a_checkout_list_keeps_todays_lane(fb, capsys, monkeypatch):
    (fb.member / ".claude").mkdir(exist_ok=True)
    lf = fb.member / ".claude" / "edit-gates"
    lf.write_text("CLAUDE.md\n")
    draft = fb.tmp / "d2"
    draft.write_text("CLAUDE.md\n/abs.md\n")
    monkeypatch.chdir(fb.member)
    code, out, err = _cli(capsys, "gates", "write", str(lf), "--from", str(draft))
    assert code == 0, err


# ---- 8: `gates` and the doctor's row read three layers -----------------------------------

def test_8_gates_prints_three_layers_in_order(fb, capsys, monkeypatch):
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("AGENTS.md\n")
    (fb.code / ".claude").mkdir()
    (fb.code / ".claude" / "edit-gates").write_text("tree/member/README.md\n")
    monkeypatch.chdir(fb.member)
    code, out, _ = _cli(capsys, "gates")
    assert code == 0
    heads = [line for line in out.splitlines() if not line.startswith("  ")]
    assert len(heads) == 4, out
    want = [fb.member / ".claude" / "edit-gates", fb.flist, fb.code / ".claude" / "edit-gates",
            fb.home / ".claude" / "edit-gates"]
    for head, lf, n in zip(heads, want, (1, 3, 1, 1)):
        assert head.startswith(f"{lf} (") and head.endswith(f": {n} lines"), head
    assert "folder" in heads[1] and "folder" in heads[2]
    assert "  */DECISIONS.md" in out and "  /abs.md" not in out


def test_8_gates_in_a_worktree_reads_the_members_folders(fb, capsys, monkeypatch):
    monkeypatch.chdir(fb.wt)
    code, out, _ = _cli(capsys, "gates")
    assert code == 0 and f"{fb.flist} (" in out


def test_8_the_doctor_row_counts_every_layer(fb):
    (fb.member / ".claude").mkdir(exist_ok=True)
    (fb.member / ".claude" / "edit-gates").write_text("AGENTS.md\n")
    row = instructionguard.doctor_row(fb.env, fb.member)
    assert row.startswith("on; 5 gated here;"), row       # 1 checkout + 3 folder + 1 owner


# ---- 9: no process, no file for a line with no write word, fail open ---------------------

def test_9_no_call_spawns_or_reads_argv(fb, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a process or the argv")
    for name in ("Popen", "run", "check_output", "call"):
        monkeypatch.setattr(subprocess, name, boom)
    monkeypatch.setattr(os, "system", boom)
    import ctypes
    monkeypatch.setattr(ctypes, "CDLL", boom)
    import sys
    monkeypatch.setattr(sys, "argv", None)
    for p in (fb.member / "CLAUDE.md", fb.wt / "CLAUDE.md", fb.tree / "CLAUDE.md", fb.flist):
        assert _denied(fb, p), p
    assert _decision(instructionguard.check(_bash("echo >> CLAUDE.md", fb.wt), fb.env))[0] \
        == "deny"


def test_9_a_bash_line_with_no_write_word_opens_no_file(fb, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("opened a file")
    for mod, name in ((builtins, "open"), (io, "open"), (os, "open"), (os, "scandir"),
                      (os, "listdir"), (os.path, "lexists"), (os.path, "exists")):
        monkeypatch.setattr(mod, name, boom)
    for command in ("ls -la", "cat CLAUDE.md | head -3", "echo hi"):
        for cwd in (fb.member, fb.wt, fb.tree):
            assert instructionguard.check(_bash(command, cwd), fb.env) == {}, command


def test_9_an_exception_in_the_folder_walk_fails_open(fb, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("inside the walk")
    monkeypatch.setattr(instructionguard, "folder_lists", boom)
    assert hooks.pre_tool_use(_payload("Edit", fb.member / "CLAUDE.md"), fb.env) == {}
    rows = _log(fb)
    assert len(rows) == 1 and rows[0]["decision"] == "open" and rows[0]["why"] == "RuntimeError"


# ---- R8: a line is a real path; the owner's list matches the real path ------------------

def test_r8_the_owners_line_naming_a_link_gates_the_real_file(fb):
    real = fb.home / "real.md"
    real.write_text("x\n")
    (fb.home / "alias.md").symlink_to(real)
    (fb.home / ".claude" / "edit-gates").write_text("~/alias.md\n")
    assert _denied(fb, real)
    assert _denied(fb, fb.home / "alias.md")


def test_r7_the_reason_and_the_log_line_are_todays(fb):
    out = hooks.pre_tool_use(_payload("Edit", fb.wt / "CLAUDE.md", agent_id="a1"), fb.env)
    assert _decision(out)[1] == REASON.format(fb.wt / "CLAUDE.md")
    rows = _log(fb, SID)
    assert len(rows) == 1 and rows[0]["decision"] == "deny" and rows[0]["agent_id"] == "a1"
