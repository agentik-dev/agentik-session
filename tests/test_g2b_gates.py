"""Packet g2b: the edit gates (hq design/09 §7.2). A file a list names is refused to every edit
tool and to a Bash line that writes it (g3), in every mode; every other file passes in silence;
the lane writes a gated file with `agentik session gates write`."""
from __future__ import annotations

import ast
import builtins
import io
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks, instructionguard, instructions, resolver, shellreader
from test_doctor import machine  # noqa: F401  (the fixture)

ROOT = Path(__file__).resolve().parents[1]
# g7: the gate's code is the guard and the reader it imports; each source scan reads both
GUARD_SRC = [ROOT / "plugin" / "lib" / "claude_session" / f
             for f in ("instructionguard.py", "shellreader.py")]
SKILL = "decision" "s:instruct"            # spelled in two pieces for the hygiene scan
SID = "g2b-sess-0001"
TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
REASON = ("agentik-session: `{}` is gated: an edit of it is refused in every permission mode. "
          "Make the change through the `" + SKILL + "` skill, which shows the owner the change "
          "and its cost and writes it only on the owner's yes. Do not write the file another "
          "way.")
BEGIN = "<!-- BEGIN GENERATED: decisions -->"
END = "<!-- END GENERATED: decisions -->"


@pytest.fixture
def box(tmp_path, monkeypatch):
    class B:
        pass
    b = B()
    b.tmp = tmp_path
    b.home = tmp_path / "home"
    (b.home / ".claude").mkdir(parents=True)
    b.env = {"HOME": str(b.home), "XDG_STATE_HOME": str(tmp_path / "state"),
             "PATH": "/usr/bin:/bin"}
    monkeypatch.setenv("HOME", str(b.home))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    b.state = resolver.state_dir(b.env)
    b.tree = tmp_path / "code" / "tree"
    b.repo = b.tree / "repo"
    (b.repo / ".git").mkdir(parents=True)
    (b.repo / ".claude").mkdir()
    (b.repo / ".claude" / "edit-gates").write_text(
        "# what the edit gates guard here\nCLAUDE.md\nAGENTS.md\n.claude/settings*.json\n"
        "docs/**\n../escape.md\n/abs.md\n" + str(b.repo / "abs2.md") + "\n\n")
    b.wt = b.repo / ".claude" / "worktrees" / "row"
    gitdir = b.repo / ".git" / "worktrees" / "row"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    (b.wt / ".claude").mkdir(parents=True)
    (b.wt / ".git").write_text(f"gitdir: {gitdir}\n")
    (b.wt / ".claude" / "edit-gates").write_text("CLAUDE.md\n")
    (b.home / ".claude" / "edit-gates").write_text(
        "~/.claude/settings.json\n" + str(b.tree / "CLAUDE.md") + "\nrelative.md\n")
    return b


def _payload(tool, path, sid=SID, cwd=None, **more):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    ti = {key: str(path)}
    ti.update({"Edit": {"old_string": "a", "new_string": "b"}, "Write": {"content": "x"},
               "MultiEdit": {"edits": [{"old_string": "a", "new_string": "b"}]},
               "NotebookEdit": {"new_source": "x"}}.get(tool, {}))
    return {"session_id": sid, "transcript_path": "/t.jsonl", "cwd": str(cwd or "/"),
            "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti,
            "tool_use_id": "toolu_g2b_0001", **more}


def _bash(command, cwd, sid=SID, **more):
    return {"session_id": sid, "transcript_path": "/t.jsonl", "cwd": str(cwd),
            "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command}, "tool_use_id": "toolu_g2b_0002", **more}


def _decision(out):
    h = out.get("hookSpecificOutput") or {}
    return h.get("permissionDecision"), h.get("permissionDecisionReason")


def _log(b, sid=SID):
    p = resolver.session_dir(b.state, sid) / instructionguard.LOG
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def _listed(b) -> list:
    return [b.repo / "CLAUDE.md", b.repo / "AGENTS.md", b.repo / ".claude" / "settings.json",
            b.repo / ".claude" / "settings.local.json", b.repo / "docs" / "a" / "b.md",
            b.wt / "CLAUDE.md", b.home / ".claude" / "settings.json", b.tree / "CLAUDE.md"]


def _lists(b) -> list:
    return [b.repo / ".claude" / "edit-gates", b.wt / ".claude" / "edit-gates",
            b.home / ".claude" / "edit-gates"]


# ---- 1: the edit tools ------------------------------------------------------------------

@pytest.mark.parametrize("agent", [None, "a1"])
@pytest.mark.parametrize("tool", TOOLS)
def test_1_each_edit_tool_on_a_listed_path_denies(box, tool, agent):
    more = {"agent_id": agent} if agent else {}
    for p in _listed(box) + _lists(box):
        out = hooks.pre_tool_use(_payload(tool, p, **more), box.env)
        assert _decision(out) == ("deny", REASON.format(os.path.normpath(str(p)))), p
    rows = _log(box)
    assert len(rows) == len(_listed(box)) + len(_lists(box))
    assert {r["decision"] for r in rows} == {"deny"} and {r["tool"] for r in rows} == {tool}
    assert {r["agent_id"] for r in rows} == {agent} and all("run" not in r for r in rows)


def test_1_no_answer_is_ask(box):
    src = "".join(p.read_text() for p in GUARD_SRC)
    assert '"ask"' not in src and "'ask'" not in src
    for p in _listed(box) + [box.repo / "notes.md", "relative", ""]:
        for tool in (*TOOLS, "Bash"):
            pay = _payload(tool, p) if tool != "Bash" else _bash(f"echo x >> {p}", box.repo)
            assert _decision(instructionguard.check(pay, box.env))[0] != "ask"


def test_1_an_unlisted_path_passes_and_logs_nothing(box):
    for p in (box.repo / "notes.md", box.repo / "README.md", box.tree / "escape.md",
              box.repo / "abs.md", box.repo / "abs2.md", box.home / ".claude" / "CLAUDE.md",
              box.wt / "AGENTS.md", box.home / "relative.md", box.tmp / "nowhere" / "CLAUDE.md"):
        for tool in TOOLS:
            assert hooks.pre_tool_use(_payload(tool, p), box.env) == {}, p
    assert _log(box) == []


def test_1_the_user_list_moves_with_the_config_dir(box, monkeypatch):
    moved = box.tmp / "moved"
    moved.mkdir()
    (moved / "edit-gates").write_text(str(box.tmp / "x.json") + "\n")
    env = dict(box.env, CLAUDE_CONFIG_DIR=str(moved))
    for p in (moved / "edit-gates", box.tmp / "x.json"):
        assert _decision(instructionguard.check(_payload("Write", p), env))[0] == "deny", p
    assert instructionguard.check(_payload("Write", box.home / ".claude" / "settings.json"),
                                  env) == {}


# ---- 2: matching ------------------------------------------------------------------------

def test_2_a_worktrees_own_list_applies(box):
    assert _decision(instructionguard.check(_payload("Edit", box.wt / "CLAUDE.md"),
                                            box.env))[0] == "deny"
    assert instructionguard.check(_payload("Edit", box.wt / "AGENTS.md"), box.env) == {}


def test_2_a_relative_or_symlinked_spelling_matches(box):
    link = box.tmp / "link"
    link.symlink_to(box.repo)
    assert _decision(instructionguard.check(_payload("Edit", link / "CLAUDE.md"),
                                            box.env))[0] == "deny"
    assert _decision(instructionguard.check(_payload("Edit", "CLAUDE.md", cwd=box.repo),
                                            box.env))[0] == "deny"
    alias = box.tmp / "alias.md"
    alias.symlink_to(box.repo / "AGENTS.md")
    assert _decision(instructionguard.check(_payload("Write", alias), box.env))[0] == "deny"


def _folds(tmp_path) -> bool:
    (tmp_path / "Probe").write_text("")
    return (tmp_path / "pROBE").exists()


def test_2_a_case_variant_matches_on_a_case_blind_volume(box):
    out = instructionguard.check(_payload("Edit", box.repo / "claude.MD"), box.env)
    if _folds(box.tmp):
        assert _decision(out)[0] == "deny"
    else:
        assert out == {}


def test_2_dotdot_and_absolute_lines_in_a_repo_list_match_nothing(box):
    for p in (box.tree / "escape.md", Path("/abs.md"), box.repo / "abs.md", box.repo / "abs2.md"):
        assert instructionguard.check(_payload("Edit", p), box.env) == {}, p


def test_2_a_glob_line(box):
    for p in (box.repo / "docs" / "x.md", box.repo / ".claude" / "settings.team.json"):
        assert _decision(instructionguard.check(_payload("Edit", p), box.env))[0] == "deny", p


# ---- 3: g3, the Bash gate ---------------------------------------------------------------

DENIED = [
    "printf 'probe\\n' >> CLAUDE.md", "echo x > CLAUDE.md", "echo x >| CLAUDE.md",
    "echo x &> CLAUDE.md", "echo x 2> CLAUDE.md", "echo hi && echo x>>CLAUDE.md",
    "echo x | tee -a CLAUDE.md", "echo x | tee /dev/null CLAUDE.md",
    "sed -i '' 's/a/b/' CLAUDE.md", "sed -i.bak s/a/b/ CLAUDE.md", "sed -n -i s/a/b/ AGENTS.md",
    "perl -pi -e 's/a/b/' CLAUDE.md", "perl -i.bak -pe 's/a/b/' CLAUDE.md",
    "cp /tmp/x CLAUDE.md", "mv /tmp/x CLAUDE.md", "install -m 644 /tmp/x CLAUDE.md",
    "cp -t . /tmp/CLAUDE.md", "cp /tmp/CLAUDE.md .", "mv -t docs /tmp/notes.md",
    "bash -c 'echo x >> CLAUDE.md'", 'sh -c "echo x > CLAUDE.md"',
    "cd docs && echo x > ../CLAUDE.md", "cd .claude; cat x > settings.json",
    "python3 -c \"open('CLAUDE.md', 'a').write('x')\"",
    "python -c \"import pathlib; pathlib.Path('AGENTS.md').write_text('x')\"",
    "cat > CLAUDE.md <<EOF\nline\nEOF", "cat <<'EOF' > CLAUDE.md\nline\nEOF",
    "python3 - <<'EOF'\nopen('CLAUDE.md', 'a').write('x')\nEOF",
    "echo x >> ~/.claude/settings.json", "true; echo x >> .claude/edit-gates",
]


@pytest.mark.parametrize("command", DENIED)
def test_3_each_form_denies_on_a_gated_target(box, command):
    out = instructionguard.check(_bash(command, box.repo, agent_id="a1"), box.env)
    assert _decision(out)[0] == "deny", command
    assert re.fullmatch(re.escape(REASON).replace(re.escape("{}"), "/.+"), _decision(out)[1])
    assert [r["tool"] for r in _log(box)] == ["Bash"]


def test_3_the_reason_names_the_first_gated_target(box):
    out = instructionguard.check(_bash("echo x >> notes.md; echo y > AGENTS.md; echo > CLAUDE.md",
                                       box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "AGENTS.md"))


def test_3_a_cd_from_elsewhere(box):
    out = instructionguard.check(_bash("cd tree/repo && printf x >> CLAUDE.md", box.tmp / "code"),
                                 box.env)
    assert _decision(out)[0] == "deny"
    assert instructionguard.check(_bash("cd /tmp && echo x >> CLAUDE.md", box.repo),
                                  box.env) == {}


REMOVED = ["rm .claude/edit-gates", "rm -rf .claude", "unlink .claude/edit-gates",
           "git rm .claude/edit-gates", "git checkout -- .claude/edit-gates",
           "git checkout HEAD~1 -- .claude/edit-gates", "git restore .claude/edit-gates",
           "git restore --staged --worktree .claude/edit-gates",
           "mv .claude/edit-gates /tmp/x", "rm ~/.claude/edit-gates"]


@pytest.mark.parametrize("command", REMOVED)
def test_3_a_list_files_removal_denies(box, command):
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out)[0] == "deny", command


PASSED = ["echo x >> $X", "echo x >> \"$HOME/CLAUDE.md\"", "echo x >> CLAUDE.m*",
          "echo x >> `pwd`/CLAUDE.md", "echo x >> notes.md",
          "agentik decisions render --into CLAUDE.md",
          "agentik session gates write CLAUDE.md --from /tmp/d.md --expect 0123abcd",
          "cat CLAUDE.md", "grep x CLAUDE.md > /tmp/out.txt", "git status",
          "git checkout -- CLAUDE.md.orig", "cp CLAUDE.md /tmp/x", "mv /tmp/a /tmp/b",
          "python3 -c \"print('CLAUDE.md')\"", "rm notes.md",
          "sed 's/a/b/' CLAUDE.md > /tmp/y", "ls 2>&1 | head", "echo x >&2"]


@pytest.mark.parametrize("command", PASSED)
def test_3_what_g3_cannot_read_or_need_not_passes(box, command):
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command


def test_3_dispatch_on_bash(box, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(
        _bash("printf 'probe\\n' >> CLAUDE.md", box.repo))))
    assert hooks.dispatch("PreToolUse") == 0
    assert _decision(json.loads(capsys.readouterr().out)) == (
        "deny", REASON.format(box.repo / "CLAUDE.md"))


# ---- 4: no process, no argv, no file opened for a line with no write word ---------------

def test_4_no_call_spawns_or_reads_argv(box, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a process or the argv")
    for name in ("Popen", "run", "check_output", "call"):
        monkeypatch.setattr(subprocess, name, boom)
    monkeypatch.setattr(os, "system", boom)
    import ctypes
    monkeypatch.setattr(ctypes, "CDLL", boom)
    monkeypatch.setattr(ctypes, "cdll", None)
    assert _decision(instructionguard.check(_payload("Edit", box.repo / "CLAUDE.md"),
                                            box.env))[0] == "deny"
    assert _decision(instructionguard.check(_bash("echo >> CLAUDE.md", box.repo),
                                            box.env))[0] == "deny"
    assert instructionguard.check(_payload("Edit", box.repo / "x.py"), box.env) == {}
    tree = ast.Module(body=[n for p in GUARD_SRC for n in ast.parse(p.read_text()).body],
                      type_ignores=[])
    names = {getattr(n, "id", getattr(n, "attr", None)) for n in ast.walk(tree)}
    mods = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in n.names} | {n.module for n in ast.walk(tree)
                                 if isinstance(n, ast.ImportFrom) and n.module}
    assert not ({"subprocess", "ctypes", "harness"} & mods), mods
    assert not ({"claude_argv", "headless", "run_kind", "_procargs", "argv"} & names)


def test_4_a_bash_line_with_no_write_word_opens_no_file(box, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("opened a file")
    for mod, name in ((builtins, "open"), (io, "open"), (os, "open"), (os, "scandir"),
                      (os, "listdir")):
        monkeypatch.setattr(mod, name, boom)
    for command in ("ls -la", "cat CLAUDE.md | head -3", "pytest -q tests", "echo hi",
                    "agentik decisions render --into CLAUDE.md"):
        assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command


def test_4_cheap_on_an_ungated_path(box):
    p = _payload("Edit", box.repo / "plugin" / "lib" / "a.py")
    started = time.perf_counter()
    for _ in range(200):
        assert hooks.pre_tool_use(p, box.env) == {}
    assert (time.perf_counter() - started) / 200 < 0.05


# ---- 5: fail open -----------------------------------------------------------------------

@pytest.mark.parametrize("tool", ["Edit", "Bash"])
def test_5_an_exception_returns_nothing_and_one_open_line(box, monkeypatch, tool):
    def boom(*a, **k):
        raise RuntimeError("inside the gate")
    monkeypatch.setattr(instructionguard, "gated", boom)
    pay = (_payload("Edit", box.repo / "CLAUDE.md") if tool == "Edit"
           else _bash("echo x >> CLAUDE.md", box.repo))
    assert hooks.pre_tool_use(pay, box.env) == {}
    rows = _log(box)
    assert len(rows) == 1 and rows[0]["decision"] == "open" and rows[0]["why"] == "RuntimeError"
    monkeypatch.setattr(instructionguard, "check", boom)      # past the gate's own try
    assert hooks.pre_tool_use(pay, box.env) == {}


@pytest.mark.parametrize("target", [None, "", 7, ["a"], "x\0y"])
def test_5_an_unresolvable_target(box, target):
    p = _payload("Write", "/x", cwd="not-absolute")
    p["tool_input"]["file_path"] = target
    assert instructionguard.check(p, box.env) == {}
    p["tool_input"] = "not a dict"
    assert instructionguard.check(p, box.env) == {}


def test_5_the_log_stops_at_its_cap(box, monkeypatch):
    monkeypatch.setattr(instructionguard, "LOG_CAP", 400)
    for _ in range(10):
        instructionguard.check(_payload("Edit", box.repo / "CLAUDE.md"), box.env)
    log = resolver.session_dir(box.state, SID) / instructionguard.LOG
    assert 0 < log.stat().st_size <= 400


def test_5_no_knob(box, monkeypatch):
    for k in ("AGENTIK_GUARD", "AGENTIK_SESSION_GUARD_OFF", "AGENTIK_EDIT_GATES",
              "EDIT_GATES_OFF", "AGENTIK_NO_GATES"):
        monkeypatch.setenv(k, "off")
    env = dict(box.env, AGENTIK_EDIT_GATES="0", AGENTIK_GUARD="off")
    assert _decision(instructionguard.check(_payload("Edit", box.repo / "CLAUDE.md"),
                                            env))[0] == "deny"
    tree = ast.Module(body=[n for p in GUARD_SRC for n in ast.parse(p.read_text()).body],
                      type_ignores=[])
    caps = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str) and re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", n.value)}
    assert caps <= {"HOME", "CLAUDE_CONFIG_DIR"}, caps
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and n.attr in ("environ", "environb")]


# ---- 6: the lane's write ----------------------------------------------------------------

@pytest.fixture
def lane(box, monkeypatch):
    t = box.repo / "CLAUDE.md"
    t.write_text(f"# Repo\n\nA hand line.\n\n{BEGIN}\nrule one\n{END}\n")
    t.chmod(0o640)
    box.target = t
    box.draft = box.tmp / "draft.md"
    box.draft.write_text(f"# Repo\n\nA hand line.\nA second hand line.\n\n{BEGIN}\nrule one\n"
                         f"{END}\n")
    monkeypatch.chdir(box.repo)
    return box


def _cli(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    got = capsys.readouterr()
    return code, got.out, got.err


def _hash(out) -> str:
    m = re.search(r"^hash: ([0-9a-f]{16})$", out, re.M)
    assert m, out
    return m.group(1)


def test_6_preview_leaves_the_bytes(lane, capsys):
    before = lane.target.read_bytes()
    code, out, err = _cli(capsys, "gates", "write", str(lane.target), "--from", str(lane.draft),
                          "--preview")
    assert code == 0, err
    assert "+A second hand line." in out and re.search(r"^bytes: \d+ -> \d+ \(\+20\)$", out, re.M)
    _hash(out)
    assert lane.target.read_bytes() == before


def test_6_a_good_expect_writes_and_keeps_the_mode(lane, capsys):
    h = _hash(_cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft))[1])
    code, out, err = _cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft),
                          "--expect", h)
    assert code == 0, err
    assert lane.target.read_text() == lane.draft.read_text()
    assert stat.S_IMODE(lane.target.stat().st_mode) == 0o640


def test_6_a_wrong_or_stale_expect_writes_nothing(lane, capsys):
    before = lane.target.read_bytes()
    h = _hash(_cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft))[1])
    assert _cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft),
                "--expect", "0" * 16)[0] != 0
    lane.draft.write_text(lane.draft.read_text() + "late\n")
    assert _cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft),
                "--expect", h)[0] != 0
    assert lane.target.read_bytes() == before


def test_6_a_changed_block_line_writes_nothing(lane, capsys):
    before = lane.target.read_bytes()
    lane.draft.write_text(f"# Repo\n\nA hand line.\n\n{BEGIN}\nrule two\n{END}\n")
    code, out, err = _cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft))
    assert code != 0 and "generated" in err
    h = instructionguard.lane_hash(before, lane.draft.read_bytes())
    assert _cli(capsys, "gates", "write", "CLAUDE.md", "--from", str(lane.draft),
                "--expect", h)[0] != 0
    assert lane.target.read_bytes() == before


def test_6_bad_json_writes_nothing(lane, capsys):
    s = lane.repo / ".claude" / "settings.json"
    s.write_text("{}\n")
    lane.draft.write_text("{not json\n")
    h = instructionguard.lane_hash(s.read_bytes(), lane.draft.read_bytes())
    code, _, err = _cli(capsys, "gates", "write", str(s), "--from", str(lane.draft),
                        "--expect", h)
    assert code != 0 and "JSON" in err and s.read_text() == "{}\n"


def test_6_an_ungated_target_or_a_gated_draft_writes_nothing(lane, capsys):
    n = lane.repo / "notes.md"
    n.write_text("x\n")
    h = instructionguard.lane_hash(n.read_bytes(), lane.draft.read_bytes())
    code, _, err = _cli(capsys, "gates", "write", str(n), "--from", str(lane.draft),
                        "--expect", h)
    assert code != 0 and "not gated" in err and n.read_text() == "x\n"
    code, _, err = _cli(capsys, "gates", "write", "CLAUDE.md", "--from", "AGENTS.md")
    assert code != 0


def test_6_gates_alone_lists_what_is_gated_here(lane, capsys):
    code, out, _ = _cli(capsys, "gates")
    assert code == 0
    assert str(lane.repo / ".claude" / "edit-gates") in out
    assert str(lane.home / ".claude" / "edit-gates") in out
    for line in ("CLAUDE.md", ".claude/settings*.json", "~/.claude/settings.json"):
        assert line in out


# ---- R4: the doctor's row ---------------------------------------------------------------

def _loaded(box, sid, at):
    d = resolver.session_dir(box.state, sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": at, "file_path": str(box.repo / "CLAUDE.md"), "cwd": str(box.repo)}) + "\n")


def test_r4_doctor_row_counts_the_newest_session(box):
    _loaded(box, "g2b-old", 100)
    instructionguard.check(_payload("Edit", box.repo / "CLAUDE.md", sid="g2b-old"), box.env)
    _loaded(box, SID, 200)
    for agent in (None, "a1"):
        more = {"agent_id": agent} if agent else {}
        instructionguard.check(_payload("Edit", box.repo / "AGENTS.md", **more), box.env)
    instructionguard.log({"session_id": SID}, box.env, "open", None, why="x")
    assert instructionguard.doctor_row(box.env, box.repo) == (
        f"on; 6 gated here; session {SID}: 2 refusals, 1 let through on an error")


def test_r4_doctor_row_without_a_session(box):
    assert instructionguard.doctor_row(box.env, box.repo) == (
        f"on; 6 gated here; no session of {box.repo.resolve()} has a log to count its refusals")


def test_r4_doctor_row_in_the_report(machine):  # noqa: F811
    env, repo = machine.env, machine.repo
    d = resolver.session_dir(resolver.state_dir(env), SID)
    d.mkdir(parents=True)
    (d / instructions.LOG).write_text(json.dumps(
        {"at": 200, "file_path": str(repo / "CLAUDE.md"), "cwd": str(repo)}) + "\n")
    rep = doctor.run(env, repo)
    rows = [c for c in rep.checks if c.name == "guard"]
    assert rep.ok and len(rows) == 1 and rows[0].ok and not rows[0].warn
    assert re.fullmatch(rf"on; \d+ gated here; session {SID}: 0 refusals, 0 let through on an "
                        r"error", rows[0].detail), rows[0].detail


# ---- review round 1: F1 (a subshell's or a popd's folder), F6 (an unresolved target logs) --

@pytest.mark.parametrize("command", [
    "(cd docs && ls); printf x >> CLAUDE.md",
    "pushd docs; popd; printf x >> CLAUDE.md",
    "cd docs && (cd ..; ls) && printf x >> ../CLAUDE.md",
    "( cd /tmp ) ; echo x > CLAUDE.md",
])
def test_f1_a_subshells_or_a_popds_folder_does_not_outlive_it(box, command):
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


@pytest.mark.parametrize("command", [
    "echo x >> $X", "echo x >> CLAUDE.m*", "cd $X; printf x >> $Y",
])
def test_f6_an_unresolved_bash_target_passes_with_one_open_line(box, command):
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command
    rows = _log(box)
    assert [(r["decision"], r["tool"]) for r in rows] == [("open", "Bash")], rows


def test_f6_a_resolved_ungated_target_logs_nothing(box):
    for command in ("echo x >> notes.md", "sed -i '' s/a/b/ notes.md", "ls 2>&1 | head"):
        assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command
    assert _log(box) == []


# ---- review round 2 (the hardening round): F1 quoted parens, F2 case patterns, F3 pushd ----

R2_DENIED = [
    ("docs", "grep -c '(' a.py; cd ..; grep -c ')' a.py; printf x >> CLAUDE.md"),     # F1
    ("docs", "echo \\(; cd ..; echo \\); printf x >> CLAUDE.md"),                      # F1
    ("", "(cd docs; echo ')'; printf x >> ../CLAUDE.md)"),                             # F1
    ("", "(cd docs && case $x in *) printf x >> ../CLAUDE.md;; esac)"),                # F2
    ("", "(cd docs; case $x in a) ;; esac; cd ..); printf x >> CLAUDE.md"),            # F2
    ("", "pushd docs; (pushd ..); popd; printf x >> CLAUDE.md"),                       # F3
    ("", "pushd docs; (popd); popd; printf x >> CLAUDE.md"),                           # N3, by F3
    ("docs", "echo \"(\"; cd ..; echo \")\"; printf x >> CLAUDE.md"),                  # F1, dquote
    ("", "case $x in (a) cd docs;; esac; cd ..; printf x >> CLAUDE.md"),               # F2, (a)
]


@pytest.mark.parametrize("where,command", R2_DENIED)
def test_r2_each_repro_denies(box, where, command):
    cwd = box.repo / where if where else box.repo
    out = instructionguard.check(_bash(command, cwd), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


def test_r2_an_unmatched_paren_leaves_the_folder_unknown(box):
    command = "cd sub; ) ; printf x >> ../notes.md"
    assert shellreader.bash_targets(command, str(box.repo), box.env) == [("write", None)]
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}
    assert [r["decision"] for r in _log(box)] == ["open"]


# ---- g5: a `#` inside a word is no comment's start (u3's review, round 1, R1-F2) ----------

G5_INWORD = ["echo x#y; cp a CLAUDE.md", "v=${TAG#v}; cp a CLAUDE.md", "echo $#; cp a CLAUDE.md",
             "echo ${#a[@]}; cp a CLAUDE.md", "echo a\\#b; cp a CLAUDE.md",
             "echo x #c\ncp a CLAUDE.md", "echo \"x #y\"; cp a CLAUDE.md",
             "echo 'a#b'; cp a CLAUDE.md"]


@pytest.mark.parametrize("command", G5_INWORD)
def test_g5_an_inword_or_quoted_hash_hides_no_write(box, command):
    assert shellreader.bash_targets(command, str(box.repo), box.env) == \
        [("write", str(box.repo / "CLAUDE.md"))], command
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


@pytest.mark.parametrize("command", ["echo x #y; cp a CLAUDE.md", "# cp a CLAUDE.md",
                                     "echo x;#y\ncd docs; cp a CLAUDE.md\n#z"])
def test_g5_a_comment_stays_one(box, command):
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    assert found == ([("write", str(box.repo / "docs" / "CLAUDE.md"))] if "docs" in command
                     else []), command


@pytest.mark.parametrize("command,words", [
    ("echo x#y", ["echo", "x#y"]), ("echo a\\#b", ["echo", "a#b"]),
    ("echo ${#a[@]} $# x", ["echo", "${#a[@]}", "$#", "x"]),
    ("echo \"x #y\" 'a#b' z", ["echo", "x #y", "a#b", "z"]), ("echo x #y z", ["echo", "x"])])
def test_g5_the_words_read_back_whole(command, words):
    assert [w for w, _ in shellreader._commands(command)] == [words]


# ---- g5 round 1: F1 `$(...)#`, F2 `${` and backticks, F3 a line that stops splitting, F4 ----

W = "; cp a CLAUDE.md"
G5_R1_WRITES = ["echo $(echo a)#c" + W, "x=$(date +%s)#tag" + W, "echo $((1+2))#c" + W,   # F1
                "x=${l%% #*}" + W, "echo ${x:- #y}" + W, "echo `echo a #b`" + W,          # F2
                "# note \\\ncp a CLAUDE.md", "echo x\\\n#y" + W]                          # F4


@pytest.mark.parametrize("command", G5_R1_WRITES)
def test_g5_r1_a_hash_the_shell_reads_in_a_word_hides_no_write(box, command):
    assert shellreader.bash_targets(command, str(box.repo), box.env) == \
        [("write", str(box.repo / "CLAUDE.md"))], command
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


@pytest.mark.parametrize("command", ["(cd x) #c" + W, "(cd x)#c" + W])
def test_g5_r1_a_hash_after_a_subshells_paren_is_a_comment(box, command):
    assert shellreader.bash_targets(command, str(box.repo), box.env) == [], command


@pytest.mark.parametrize("command", ["cp a CLAUDE.md; echo x#y\\", "cp a CLAUDE.md\necho x#'y"])
def test_g5_r1_the_commands_before_a_split_failure_are_judged(box, command):
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


@pytest.mark.parametrize("command", ["cp a notes.md \\", "echo 'a; cp a notes.md",
                                     "cp a notes.md; echo x\\"])
def test_g5_r1_a_line_that_cannot_be_judged_still_passes_with_one_open_line(box, command):
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command
    assert [(r["decision"], r.get("why")) for r in _log(box)] == \
        [("open", "the line cannot be split")]


# The round's "probed and clean" lines: each keeps its result at d2f89d9 (checked against
# /bin/sh and /bin/bash; `$((1#2))` and the `case` line read a write the shell does not run).
G5_R1_CLEAN = [
    ("cat <<EOF > /tmp/x\n# a\n#!/bin/sh\n# don't\nEOF\ncp a CLAUDE.md", ["/tmp/x", "CLAUDE.md"]),
    ("echo $((1#2))" + W, ["CLAUDE.md"]), ("echo ${x##*/}" + W, ["CLAUDE.md"]),
    ("echo ${x%#*}" + W, ["CLAUDE.md"]), ("echo ${x#\"#\"}" + W, ["CLAUDE.md"]),
    ("echo ${#}" + W, ["CLAUDE.md"]), ("echo \\#" + W, ["CLAUDE.md"]), ("a=b#c" + W, ["CLAUDE.md"]),
    ("echo {a,#b}" + W, ["CLAUDE.md"]), ("echo ''#b" + W, ["CLAUDE.md"]),
    ("echo a\\ #b" + W, ["CLAUDE.md"]), ("echo a;#c" + W, []), ("true &&#c" + W, []),
    ("echo a |#c" + W, []), ("echo a &#c" + W, []), ("(#c" + W, []), ("echo a\t#c" + W, []),
    ("echo $(#c\necho a)" + W, ["CLAUDE.md"]), ("echo `#c`" + W, ["CLAUDE.md"]),
    ("echo a #c\r\ncp a CLAUDE.md\r\n", ["CLAUDE.md"]), ("echo a\r#c" + W, ["CLAUDE.md"]),
    ("echo a\x0b#c" + W, ["CLAUDE.md"]), ("echo a\x0c#c" + W, ["CLAUDE.md"]),
    ("echo a\xa0#c" + W, ["CLAUDE.md"]), ("cp a CLAUDE.md #c", ["CLAUDE.md"]),
    ("# don't\ncp a CLAUDE.md", ["CLAUDE.md"]), ("# (\ncp a CLAUDE.md", ["CLAUDE.md"]),
    ("case $x in a) #c\ncp a CLAUDE.md;; esac", ["CLAUDE.md"]),
    ("bash -c 'echo x#y; cp a CLAUDE.md'", ["CLAUDE.md"]),
    ("sh -c 'echo x #y; cp a CLAUDE.md'", []), ("cp a CLAUDE.md#done", ["CLAUDE.md#done"]),
    ("echo x >CLAUDE.md#c", ["CLAUDE.md#c"])]


# ---- g5 round 2: F1 and F4 a bare paren in `${`, F2 a `case` pattern's `)` in `$(`, F3 ----

N = "\ncp a CLAUDE.md"
G5_R2_WRITES = [
    "name=${sig%%(*}\ncase $name in\n  foo) echo yes ;;  # don't care\nesac" + N,   # F1 a
    "x=${l//[(]/}; case $x in a) echo 1;; esac # isn't" + N,                         # F1 b
    "echo $${ # don't" + N,                                                          # F1 c
    "v=${v#(}; v=${v%)}; case $v in a) echo 1;; esac # don't" + N,
    "name=${sig%%\\(*}\ncase $name in\n  foo) echo yes ;;  # don't care\nesac" + N,  # control
    "# strip the paren \\\nv=${v%)}" + N, "x=${l%% #*)}" + N, "v=${v%)}" + N,       # F4
    "echo $(case x in x)#don't\necho a;; esac)" + W,                                 # F2
    "v=$(case x in\n x)# don't\n echo a;;\nesac)" + N,
    "echo $(if true; then case x in x)# don't\necho;; esac; fi)" + W,
    "echo `echo a # \\`x\\` `; echo b # use `cp` here don't" + N,                    # F3
    "echo `echo a # x `; echo b # use `cp` here don't" + N,
    "x=$(${v%) cp a CLAUDE.md\n)", "$(${v%%) cp a CLAUDE.md\n)",                    # bash 3.2
    "$(${v%% case x in x) cp a CLAUDE.md\n # say \"hi${s%%(*}$((1+2)) # use `cp`",
    "x=$(echo ${v%)}); echo ok" + W, "x=$(echo ${v//)/}) && cp a CLAUDE.md",          # zsh
    "${v#(}`case $x in a)case x in (x)`#" + N, "x=`case $x in a) echo;; esac`" + W,    # ticks
    "echo `case $x in a) echo;; esac`" + N]


@pytest.mark.parametrize("command", G5_R2_WRITES)
def test_g5_r2_a_paren_in_a_brace_or_a_pattern_hides_no_write(box, command):
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    want = ("write", str(box.repo / "CLAUDE.md"))      # a `$(`: bash 3.2's reading may add one
    assert (want in found if "$(" in command else found == [want]), (command, found)
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


# Round 2's "probed and clean" lines under F1 and F2, and the fixes' neighbours: each reads as
# at 40aee95 (`(...)#c` a comment, `$(...)#c` a word, as /bin/sh and /bin/bash read them).
G5_R2_CLEAN = [(c + W, t) for c, t in [
    ("echo $(echo $(echo a))#c", ["CLAUDE.md"]), ("echo $(echo $(echo a) b)#c", ["CLAUDE.md"]),
    ("echo $(echo ')')#c", ["CLAUDE.md"]), ("echo $(echo \\))#c", ["CLAUDE.md"]),
    ("echo $(echo \")\")#c", ["CLAUDE.md"]), ("echo $(( (1+2)*3 ))#c", ["CLAUDE.md"]),
    ("echo $( (echo a) )#c", ["CLAUDE.md"]), ("echo $(a)$(b)#c", ["CLAUDE.md"]),
    ("echo ${x:-$(echo a)}#c", ["CLAUDE.md"]), ("echo ${x:-$(echo a # b\n)} # c", []),
    ("echo $(cat <<EOF\n)#\nEOF\n)#c", ["CLAUDE.md"]), ("(echo $(echo a))#c", []),
    ("echo ${x:-\"}\"}", ["CLAUDE.md"]), ("echo ${x:-'}'}", ["CLAUDE.md"]),
    ("echo ${x:-\\}}", ["CLAUDE.md"]), ("echo ${x:-${y:-a #b}}", ["CLAUDE.md"]),
    ("echo ${x:-(none)}", ["CLAUDE.md"]), ("echo ${x:-(none)} #c", []),
    ("echo `echo a # b`", ["CLAUDE.md"]), ("echo `echo a # b\necho c`", ["CLAUDE.md"]),
    ("echo `a` `b #c`", ["CLAUDE.md"]), ("echo \"`echo a # b`\"", ["CLAUDE.md"]),
    ("echo $$(echo a)#c", ["CLAUDE.md"]), ("echo $$${x #y}", ["CLAUDE.md"]),
    ("echo ${x:-$((1+2))}", ["CLAUDE.md"]), ("(case x in x) echo a;; esac)#c", []),
    ("echo $(echo case x)#c", ["CLAUDE.md"]),
    ("case x in x) echo $(echo a)#c;; esac", ["CLAUDE.md"]),
    ("echo $(case x in (x) echo;; esac)#c", ["CLAUDE.md"]),
    ("echo `echo a # \\\\`; echo b", ["CLAUDE.md"])]]


@pytest.mark.parametrize("command,targets", G5_R1_CLEAN + G5_R2_CLEAN)
def test_g5_r1_the_probed_clean_lines_keep_their_result(box, command, targets):
    want = [("write", t if t.startswith("/") else str(box.repo / t)) for t in targets]
    assert shellreader.bash_targets(command, str(box.repo), box.env) == want, command


# ---- g5 round 3: R3-F1 to F7, the strict reader's six regressions and its timing ----------

B = "`"
G5_R3_WRITES = [
    "echo `true; case a in a) cp a CLAUDE.md;; esac`",                               # F1 a
    "x=`\ncase a in\na)cp a CLAUDE.md;;\nesac\n`", "x=`x=$(case a in a) cp a CLAUDE.md;; esac)`",
    "echo `true; case $y in a) (cd sub; echo);; esac`" + W,                          # F1 b
    "x=`(cd sub; [[ $y =~ ^(case|if)$ ]])`" + W,                                    # F1 c
    "x=`case a in a) cp a CLAUDE.md;; esac`",                                         # lead 1
    "echo ${x:-`(cp a CLAUDE.md)`}", "echo ${x:-`case a in (a) cp a CLAUDE.md;; esac`}",  # F2
    "echo `(cp a CLAUDE.md)`",
    "echo $(case x in x)#c" + W, "x=$(case x in esac)#c && cp a CLAUDE.md",          # F3
    "echo $(a=(case); echo x)#c" + W, "echo $(case x in x)#c" + N,
    "x=$(case x in esac)#c" + N, "echo $(a=(case); echo x)#c" + N,
    "echo `echo \\`echo a # c\\`; cp a CLAUDE.md; echo b`",                          # F4
    "echo $(case\\\n x in x)#don't\necho a;; esac)" + W,                             # F5
    "v=$(case\\\n x in\n x)# don't\n echo a;;\nesac)" + N,
    "echo `true;cp a CLAUDE.md #c`"]                                                 # F6 a


@pytest.mark.parametrize("command", G5_R3_WRITES)
def test_g5_r3_a_write_in_backticks_a_brace_or_a_pattern_is_read(box, command):
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    assert ("write", str(box.repo / "CLAUDE.md")) in found, (command, found)
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


def test_g5_r3_a_comment_in_one_backtick_pair_is_masked_in_linear_time(box):
    command = "x=" + B + "\n" + "# a comment\n" * (60 * 1024 // 12) + B + "; echo x > out.txt"
    began = time.monotonic()
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    assert time.monotonic() - began < 1.0
    assert found == [("write", str(box.repo / "out.txt"))]


# R8: the lines the fixes as proposed let pass, which f1f012e denied and the shells write.
G5_R3_R8 = ["x=`case x in x)cd sub;; esac`" + W, "\\` cd sub" + W,
            "(cd sub;\\`case x in esaccase $x in a)  ;" + W[2:],
            "(cd sub;`echo a`case x in x)" + N + ";", "echo `echo a # \\`x\\` don't`" + W,
            "(cd sub; echo ${x:-`echo a)`})" + W]


@pytest.mark.parametrize("command", G5_R3_R8)
def test_g5_r3_the_lines_the_fixes_as_proposed_passed_stay_denied(box, command):
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


# ---- g6 R4 to R6: the strict reader's three fixes (pin a0055da: each passed) --------------

G6_STRICT = [
    "c\\\np a CLAUDE.md",                                                            # R4
    "if true; then cp a CLAUDE.md; fi", "for i in 1; do cp a CLAUDE.md; done",       # R5
    "if false; then :; else cp a CLAUDE.md; fi", "{ cp a CLAUDE.md; }", "! cp a CLAUDE.md",
    "while false; do :; done; until true; do :; done; if cp a CLAUDE.md; then :; fi",
    "{ cd sub; printf x >> ../CLAUDE.md; }",                                         # n138
    "cp a CLAUDE.md; bash -c \"echo 'x\"", "bash -c \"echo 'x\"; cp a CLAUDE.md",    # R6
]


@pytest.mark.parametrize("command", G6_STRICT)
def test_g6_r4_to_r6_the_strict_reading_reads_the_write(box, command):
    (box.repo / "sub").mkdir()
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    assert ("write", str(box.repo / "CLAUDE.md")) in found, found
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


def test_g6_r6_an_unread_inner_line_marks_the_split(box):
    found = shellreader.bash_targets("bash -c \"echo 'x\"; echo y > a.txt", str(box.repo),
                                          box.env)
    assert found == [("split", None), ("write", str(box.repo / "a.txt"))]


# ---- g6 R1 to R3: the loose second reading (packet §3d) -----------------------------------

LOOSE_REASON = ("agentik-session: `{}` is gated, and this Bash line may write it: the line was "
                "not read with confidence. To change the file use the `" + SKILL + "` skill, "
                "which writes it through `agentik session gates write` on the owner's yes. A "
                "line that only carries such text as data keeps the text in a file and names "
                "the file.")


@pytest.fixture
def strict_only(monkeypatch):
    monkeypatch.setattr(instructionguard, "_loose_gated", lambda *a, **k: None)


def _denied(box, command, where=""):
    out = instructionguard.check(_bash(command, box.repo / where if where else box.repo),
                                 box.env)
    return _decision(out)[0] == "deny", out


# g6's 19 lines (a write a shell runs), n131's and n138's: acceptance 1
G6_A1 = [
    "cp a CLAUDE.md \\", "if true; then cp a CLAUDE.md; fi", "for i in 1; do cp a CLAUDE.md; done",
    "if false; then :; else cp a CLAUDE.md; fi", "{ cp a CLAUDE.md; }", "! cp a CLAUDE.md",
    "cat <(echo a)#c" + W, "cat >(echo a)#c" + W, "a=(1 2)#c" + W,
    "echo $(case x in x) echo a;; esac)#c" + W, "cp a CLAUDE.md; bash -c \"echo 'x\"",
    "bash -c \"echo 'x\"" + W, "c\\\np a CLAUDE.md", "cat <<EOF \\\n| cp a CLAUDE.md\nbody\nEOF",
    "echo ${x:-`echo a # don't`}" + W, "echo x # <<EOF" + N, "cat <<EOF#c" + N,
    "echo $'\\' #'" + N, "x=$((1<<2))\nprintf x >> CLAUDE.md",                     # n173, n132
    "bash -lc 'printf x >> CLAUDE.md'", "{ cd sub; printf x >> ../CLAUDE.md; }"]    # n131, n138
G6_A2 = ["cat CLAUDE.md; cat <(echo a)#c" + W,
         "sed -i '' 's/the CLAUDE.md file/x/' notes.md; cat <(echo a)#c" + W,
         "cat <(echo a)#c; cp a CLAUDE.md # note"]
# round 3's lines that a0055da still passed: F6 b and leads 2 to 5
G6_R3 = ["}$(echo a)echo #\\\n{# don't\ncp a CLAUDE.md;}", "(cd sub; case x in esac)" + W,
         "echo $(case x in (case) echo;; esac)#c" + W,
         "echo $(case x\nin x)#don't\necho a;; esac)" + W, "echo a; {# don't\ncp a CLAUDE.md;}"]


@pytest.mark.parametrize("command", G6_A1 + G6_A2 + G6_R3)
def test_g6_a1_a2_round3_each_line_is_denied_by_one_reading(box, command):
    (box.repo / "sub").mkdir()
    denied, out = _denied(box, command)
    assert denied, command
    assert _decision(out)[1] in (REASON.format(box.repo / "CLAUDE.md"),
                                 LOOSE_REASON.format(box.repo / "CLAUDE.md"))


G6_A3 = ["git add CLAUDE.md", "cp CLAUDE.md /tmp/x # a backup of CLAUDE.md",
         "git diff CLAUDE.md > /tmp/d", "wc -c CLAUDE.md | tee /tmp/n",
         "git commit -m 'render -> CLAUDE.md'", "git commit -m 'the list at <folder>/CLAUDE.md'",
         "cd /tmp/box && cp a CLAUDE.md", "grep -n 'a\\|install b' CLAUDE.md",
         "sed -i '' 's/the CLAUDE.md file/x/' notes.md",
         "if test -f CLAUDE.md; then head -3 CLAUDE.md; fi",
         "cd /tmp/box && mv CLAUDE.md CLAUDE.md", "cd /tmp/box; cp a CLAUDE.md 2>&1 | tail -1"]


@pytest.mark.parametrize("command", G6_A3)
def test_g6_a3_ordinary_lines_still_pass(box, command):
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command


# The price: text that holds a write, refused by the loose reading (acceptance 4), and the lines
# a0055da passed with an `open` line that the loose reading now refuses (R2: a raise, and a word
# the strict reading resolved to nothing, stand for no loose target).
G6_PRICE = [
    "cat > /tmp/fix.sh <<'EOF'\ncd \"$T\" && printf x > CLAUDE.md\nEOF",
    "for c in 'printf x >> CLAUDE.md' 'echo ok'; do try \"$c\"; done",
    "git commit -F - <<'EOF'\ncp a CLAUDE.md\nEOF", "echo 'to restore: cd repo; mv /tmp/old CLAUDE.md'",
    "cat > /tmp/cases.txt <<'EOF'\nrm .claude/edit-gates\nEOF", "grep -E 'a|tee' CLAUDE.md",
    "git commit -m 'a; tee b' -- CLAUDE.md"]
G6_WAS_OPEN = ["echo 'x >> CLAUDE.md", "echo '>> CLAUDE.md'", "popd; printf x >> CLAUDE.md",
               "cd $X; printf x >> CLAUDE.md", "cd - && echo x > CLAUDE.md",
               "cd sub; ) ; printf x >> ../CLAUDE.md", "cp a CLAUDE.md \\",
               "echo 'a; cp a CLAUDE.md"]


@pytest.mark.parametrize("command", G6_PRICE + G6_WAS_OPEN)
def test_g6_a4_the_loose_reading_refuses_with_its_own_reason(box, command):
    (box.repo / "sub").mkdir()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    path = box.repo / (".claude/edit-gates" if "edit-gates" in command else "CLAUDE.md")
    path = box.tree / "CLAUDE.md" if ") ;" in command else path     # `../` from the call's folder
    assert _decision(out) == ("deny", LOOSE_REASON.format(path)), command
    assert [(r["decision"], r["why"]) for r in _log(box)] == [("deny", "the loose reading")]


@pytest.mark.parametrize("command", G6_WAS_OPEN)
def test_g6_with_the_loose_reading_off_the_strict_reading_passes_as_at_a0055da(
        box, strict_only, command):
    (box.repo / "sub").mkdir()
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command
    assert [r["decision"] for r in _log(box)] == ([] if command.startswith("echo '>>") else
                                                  ["open"])


@pytest.mark.parametrize("command", G6_A1[1:6] + G6_A1[10:13] + G6_A1[-1:])
def test_g6_with_the_loose_reading_off_r4_to_r6_still_deny(box, strict_only, command):
    (box.repo / "sub").mkdir()
    assert _denied(box, command)[0], command


def test_g6_a_strict_deny_logs_its_reading(box):
    instructionguard.check(_bash("cp a CLAUDE.md", box.repo), box.env)
    assert [(r["decision"], r["why"]) for r in _log(box)] == [("deny", "the strict reading")]


@pytest.mark.parametrize("command", [
    "if false; then cd /tmp/box; fi; cp a CLAUDE.md",     # R5 reads the `cd`; it may not run
    "while false; do cd /tmp/box; done" + W, "(cd /tmp/box; case x in esac)" + W,
    "cd /tmp/box # here\ncp a CLAUDE.md", "cd /tmp/box\\ ; cp a CLAUDE.md",
    "cd sub; echo $(case x in esac); cp a ../CLAUDE.md", "cd /tmp/box && cp a CLAUDE.md & cd -" + W,
    "f() { cd /tmp/box; }" + W, "function f { cd /tmp/box; }" + W,             # R5's neighbours
    "case x in a) cd /tmp/box;; esac" + W, "select x in a; do cd /tmp/box; done" + W,
])
def test_g6_a_cd_the_loose_reading_does_not_follow_leaves_the_call_folder(box, command):
    (box.repo / "sub").mkdir()
    assert _denied(box, command)[0], command


@pytest.mark.parametrize("command,targets", [
    ("cp a b; echo x > c", [("write", "b"), ("write", "c")]),
    ("echo '>> CLAUDE.md' # x > y", [("write", "CLAUDE.md"), ("write", "y")]),
    ("bash -lc 'cp a b'", [("write", "b")]),
    ("x=1 sudo tee -a f g", [("write", "f"), ("write", "g")]),
    ("mv a b c/", [("write", "c/"), ("remove", "a"), ("remove", "b")]),
    ("cp -t d a b", [("write", "d/a"), ("write", "d/b")]),
    ("git -C sub rm -q x; git checkout HEAD -- y", [("remove", "sub/x"), ("remove", "y")]),
    ("echo a->b=>c >&2 2>&1", []), ("grep 'a\\|tee b' f", []), ("rm -rf a #b", [("remove", "a")]),
    ("c\\\np a b", [("write", "b")]), ("eval 'rm x'", [("remove", "x")]),
])
def test_g6_r1_loose_targets_is_pure(monkeypatch, command, targets):
    def boom(*a, **k):
        raise AssertionError("the loose reading opened a file")
    monkeypatch.setattr(os.path, "isdir", boom)
    monkeypatch.setattr(os, "stat", boom)
    assert shellreader.loose_targets(command) == targets


def test_g6_a_100kb_line_is_read_in_time(box):
    for command in ("echo x > a.txt; " * 6000, "cp a b; mv c d; " * 6000):
        began = time.monotonic()
        assert instructionguard.check(_bash(command, box.repo), box.env) == {}
        assert time.monotonic() - began < 2.0


# ---- review 1 of g5-g6, R1: a `cd` behind a reserved word adds a folder, replaces none (F3) ---
# Each line passed at db19d51 and was denied at a0055da; four shells write the gated file.

R1_IF = "if false; then cd sub; fi; "
R1_F3 = [R1_IF + w for w in (
    "\\cp a CLAUDE.md", "cp a CLAU\"\"DE.md", "cp a 'CLAUDE'.md", "cp a ./\"CLAUDE.md\"",  # a, b
    "cp a CLAUDE\\.md", "printf x >> CLAUDE.m'd'", "echo x >&CLAUDE.md",                 # b, c
    "cp 'a # b' CLAUDE.md", "rm -f \"notes #2.md\" .claude/edit-gates",                  # d
    "bash -c \"cp a CLAUDE.md\" x", "X=\"a b\" cp a CLAUDE.md",                          # e, f
    "git -c user.name=\"A B\" rm -q .claude/edit-gates")] + [                            # g
    "if [ -d nosuch ]; then cd nosuch; fi; \\cp -f a CLAUDE.md"]
# the prefixes of the sweep (F3's nine, F1's), and the writes a0055da denies after each
R1_PREFIXES = [
    R1_IF, "for i in; do cd sub; done; ", "while false; do cd sub; done\n",
    "if true; then :; else cd sub; fi; ", "if false; then :; elif true; then cd sub; fi; ",
    "until true; do pushd sub; done; ", "if false; then cd /tmp; fi\n", "false && { cd sub; }; ",
    "if false\nthen cd sub\nfi\n", "! cd sub; ", "x=1 then cd sub; ", "env else cd sub; ",
    "command if cd sub; "]
R1_WRITES = [w[len(R1_IF):] for w in R1_F3[:-1]] + [
    "cp a CLAUDE.md", "cp -f a CLAUDE.md", "mv a CLAUDE.md", "install -m 644 a CLAUDE.md",
    "tee -a CLAUDE.md < a", "sed -i '' s/a/b/ CLAUDE.md", "echo x > CLAUDE.md", ": >CLAUDE.md",
    "echo x 2>/dev/null 1>CLAUDE.md", "rm .claude/edit-gates", "git rm -q .claude/edit-gates",
    "python3 -c \"open('CLAUDE.md','w')\"", "cp -t . a/CLAUDE.md", "unlink .claude/edit-gates",
    "cat a > x.tmp && mv x.tmp CLAUDE.md", "printf '%s\\n' x >> CLAUDE.md"]


def _gated_path(box, command):
    return box.repo / (".claude/edit-gates" if "edit-gates" in command else "CLAUDE.md")


@pytest.mark.parametrize("command", R1_F3)
def test_r1_f3_a_cd_that_may_not_run_leaves_the_folder_before_it(box, command):
    (box.repo / "sub").mkdir()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(_gated_path(box, command))), command


def test_r1_the_property_with_the_loose_reading_off(box, strict_only):
    """Built from parts: each prefix (its `cd` behind a reserved word may not run) before each
    write `a0055da` denies; with the loose reading off every line is denied, and with no prefix
    each write is the strict reading's (the table holds only what a0055da denies)."""
    (box.repo / "sub").mkdir()
    lines = [p + w for p in [""] + R1_PREFIXES for w in R1_WRITES]
    assert len(lines) >= 300
    passed = [c for c in lines if not _denied(box, c)[0]]
    assert passed == []
    # the folder the `cd` names is read too: there the write is not gated, the line passes
    assert not _denied(box, "cd sub; cp a CLAUDE.md")[0]
    assert not _denied(box, "printf x >> ../AGENTS.md")[0]          # the tree's: not gated
    assert _denied(box, "if false; then cd sub; fi; printf x >> ../AGENTS.md")[0]   # sub's: gated


def test_r1_the_folders_are_bounded(box, strict_only):
    line = "".join("if false; then cd d%d; fi; " % i for i in range(40)) + "cp a CLAUDE.md"
    began = time.monotonic()
    assert _denied(box, line)[0]
    assert time.monotonic() - began < 2.0
    st = [(str(box.repo / f"d{i}"), ()) for i in range(40)]
    order, fa = shellreader._states([(str(box.repo), ())] + st, 40)
    assert len(order) == shellreader._CAP_STATES and order[0] == (str(box.repo), ())
    assert order[fa] == st[-1]


# ---- review 1, R2 (F1): a reserved word is skipped only as a command's first word ----------

R2_F1 = ["x=1 then cd sub; cp a CLAUDE.md", "x=1 do cd sub; cp a CLAUDE.md",
         "x=1 elif cd sub\ncp a CLAUDE.md", "x=1 ! cd sub; cp a CLAUDE.md",
         "x=1 then pushd sub; cp a CLAUDE.md", "x=1 while cd sub; printf x >> CLAUDE.md",
         "env else cd sub; cp a CLAUDE.md", "command if cd sub; cp a CLAUDE.md",
         "command until cd sub; cp a CLAUDE.md", "builtin then cd sub; cp a CLAUDE.md",
         "\"x=1\" then cd sub; cp a CLAUDE.md", "x=1 then cd /tmp; rm .claude/edit-gates"]


@pytest.mark.parametrize("command", R2_F1)
def test_r2_f1_a_reserved_word_after_an_assignment_or_a_wrapper_is_a_word(box, command):
    (box.repo / "sub").mkdir()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(_gated_path(box, command))), command
    found = shellreader.bash_targets(command, str(box.repo), box.env)
    assert all(p.startswith(str(box.repo) + os.sep) and "/sub/" not in p and
               not p.startswith("/tmp") for _, p in found), found
    # review 2's R2: the loose reading skips a reserved word wherever its loop meets it, as
    # db19d51 did (an inner line's first word), so it lists the write behind it
    assert any(w.endswith(("CLAUDE.md", "edit-gates")) for _, w, _, _ in
               shellreader._loose(command)), command


def test_r2_a_reserved_word_first_still_reads_the_cd(box):
    (box.repo / "sub").mkdir()
    found = shellreader.bash_targets("then cd sub; cp a CLAUDE.md", str(box.repo), box.env)
    assert found == [("write", str(box.repo / "sub" / "CLAUDE.md")),
                     ("write", str(box.repo / "CLAUDE.md"))]
    assert [t[:3] for t in shellreader._loose("x=1 cd sub; cp a b")] == [
        ("write", "b", ("sub",))]


# ---- review 1, R3 (F2): a strict word stands for a loose target only whole ---------------

R3_F2 = ["echo x > \"a CLAUDE.md\"; " + R1_IF + "cp a CLAUDE.md",
         "echo x > \"a CLAUDE.md\"; " + R1_IF + "printf x >> CLAUDE.md",
         "echo x > \"a CLAUDE.md\"; for i in; do cd sub; done; cp a CLAUDE.md",
         "python3 -c \"open('x CLAUDE.md','w')\"; " + R1_IF + "cp a CLAUDE.md"]
R3_LEAD2 = ["echo x > \"a CLAUDE.md\"; cp a CLAUDE.md \\",          # review 1's lead 2: no R5 word
            "echo x > \"a CLAUDE.md\"; cat <(echo a)#c; cp a CLAUDE.md"]


@pytest.mark.parametrize("command", R3_F2 + R3_LEAD2)
def test_r3_f2_a_word_split_at_its_blank_leaves_no_credit(box, command):
    (box.repo / "sub").mkdir()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    reason = LOOSE_REASON if command in R3_LEAD2 else REASON
    assert _decision(out) == ("deny", reason.format(box.repo / "CLAUDE.md")), command


R3_WHOLE = ["sed -i '' 's/the CLAUDE.md file/x/' notes.md", "rm -f \"a CLAUDE.md\"",
            "tee 'x CLAUDE.md' < a", "mv \"a CLAUDE.md\" b"]


@pytest.mark.parametrize("command", R3_WHOLE)
def test_r3_a_word_the_loose_reading_lists_whole_stands_for_its_pieces(box, command):
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command


def test_r3_the_loose_reading_alone_spends_no_piece_of_a_word(box):
    found = [("write", str(box.repo / "a CLAUDE.md"), "a CLAUDE.md", str(box.repo))]
    got = instructionguard._loose_gated("cp a CLAUDE.md", str(box.repo), box.env, {}, found, set())
    assert got == str(box.repo / "CLAUDE.md")
    found = [("write", str(box.repo / "CLAUDE.md"), "CLAUDE.md", str(box.repo))]   # whole: spent
    assert instructionguard._loose_gated("cp a CLAUDE.md", str(box.repo), box.env, {}, found,
                                         set()) is None


# ---- review 1, R4 (F4): the loose reading's time is bounded; a line past the bound is denied --

def _units(size):
    out, n = [], 0
    while sum(map(len, out)) < size:
        out.append("(cd d%d; echo '> f%d'); " % (n, n))
        n += 1
    return "".join(out)


R4_F4 = [_units(6 * 1024), _units(100 * 1024), "echo " + "1" * 20 * 1024 + " > /tmp/x",
         "if false; then cd sub; fi; " + _units(6 * 1024) + "cp a CLAUDE.md"]


@pytest.mark.parametrize("command", R4_F4, ids=["6kb", "100kb", "digits", "if-6kb-cp"])
def test_r4_f4_each_shape_returns_in_time(box, command):
    (box.repo / "sub").mkdir()
    began = time.monotonic()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert time.monotonic() - began < 2.0
    if command.endswith("CLAUDE.md"):
        assert _decision(out)[0] == "deny"


def test_r4_a_line_past_the_bound_is_denied_by_the_loose_reading(box, monkeypatch):
    command = "cd a; cd b; echo '> x'; echo '> y'"                 # 2 targets, 4 folders
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}
    monkeypatch.setattr(instructionguard, "_LOOSE_BOUND", 7)
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", LOOSE_REASON.format(box.repo / "a" / "b" / "x"))


def test_r4_the_redirect_digits_cannot_backtrack():
    assert shellreader._LOOSE_REDIR.pattern.startswith(r"(?<!\d)\d*")
    assert shellreader.loose_targets("echo 12>x 3>&1") == [("write", "x")]


# ---- review 1, R5 (F5): the loose reading takes `>&` before a word ------------------------

def test_r5_f5_the_loose_reading_takes_a_dup_redirects_word(box):
    command = "echo a # don't\ncd sub#c\necho x >&CLAUDE.md"
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", LOOSE_REASON.format(box.repo / "CLAUDE.md"))
    assert shellreader.loose_targets("echo x >&CLAUDE.md; echo y >& b") == [
        ("write", "CLAUDE.md"), ("write", "b")]
    assert shellreader.loose_targets("echo x >&2; echo y >&-; echo z >& 1; a 2>&1") == []


# ---- review 2, R1 (F5): the strict reading's product is bounded; a line past it is denied ---

def _fill(unit, size):
    out, n = [], 0
    while sum(map(len, out)) < size:
        out.append(unit.replace("N", str(n)))
        n += 1
    return "".join(out)


def _ifs(k, word="cd dN"):
    return "".join("if false; then %s; fi; " % word.replace("N", str(i)) for i in range(k))


R1_F5 = {
    "nested-3kb": _ifs(4) + "bash -c '" + _ifs(4, "cd eN") + _fill("echo x > fN; ", 3000) + "'",
    "nested-3kb-cp": (_ifs(4) + "bash -c '" + _ifs(4, "cd eN") + _fill("echo x > fN; ", 3000)
                      + "'; cp a CLAUDE.md"),
    "four-forms-2kb": ("while false; do cd d0; done; until true; do cd d1; done; "
                       "false && { cd d2; }; ! cd d3; bash -c '" + _ifs(4, "cd eN")
                       + _fill("echo x > fN; ", 2000) + "'"),
    "fifteen-30kb": _ifs(15) + _fill("echo x > fN; ", 30000),
    # one path, judged again in each folder state of an inner line read in each outer state
    "nested-100kb-one-path": (_ifs(15) + "bash -c '" + _ifs(15, "cd eN")
                              + _fill("echo x > a; ", 100000) + "'")}


@pytest.mark.parametrize("name", list(R1_F5))
def test_r2_r1_f5_each_shape_returns_in_time(box, name):
    command = R1_F5[name]
    assert len(command) > {"nested-3kb": 3200, "nested-3kb-cp": 3240, "four-forms-2kb": 2200,
                           "fifteen-30kb": 30000, "nested-100kb-one-path": 100000}[name]
    began = time.monotonic()
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert time.monotonic() - began < 2.0
    assert _decision(out)[0] == "deny"            # each is past the bound, so none passes unread


def test_r2_r1_a_line_past_the_strict_bound_is_denied(box, monkeypatch):
    """The paths judged on one line, an inner `-c` line's and every folder state's included,
    are counted as the reading goes; past `_STRICT_BOUND` the line is denied, never passed."""
    command = "if false; then cd d; fi; bash -c 'echo x > a; echo x > b'"   # 2 states x 2
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}
    monkeypatch.setattr(shellreader, "_STRICT_BOUND", 3)
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out)[0] == "deny"
    with pytest.raises(shellreader._Bound):
        shellreader.bash_targets(command, str(box.repo), box.env)
    assert not issubclass(shellreader._Bound, ValueError)   # never the loose reading's
    monkeypatch.setattr(shellreader, "_STRICT_BOUND", 4)
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}
    command = "if false; then cd d; fi; bash -c 'echo x > a; echo x > a'"   # 1 path, 2 states
    monkeypatch.setattr(shellreader, "_STRICT_READS", 3)          # 4 judgements
    assert _decision(instructionguard.check(_bash(command, box.repo), box.env))[0] == "deny"
    monkeypatch.setattr(shellreader, "_STRICT_READS", 4)
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}


# ---- review 2, R2 (F1): the loose reading skips a reserved word wherever its loop meets it ---
# (an inner line's first word, as db19d51 did); the strict reading lets `time -p` stand in the
# run of reserved words. Each line was denied at db19d51 and passed at 6aed3c5; shells write.

R2_F1_INNER = [
    "bash -lc 'if cp a CLAUDE.md; then :; fi'", "bash -lc 'if ! cp a CLAUDE.md; then echo failed; fi'",
    "bash -lc \"while ! cp a CLAUDE.md; do sleep 1; done\"", "bash -lc '! cp a CLAUDE.md'",
    "bash -lc '! tee CLAUDE.md < a'", "bash -lc 'time ! cp a CLAUDE.md'", "sh -ec '! cp a CLAUDE.md'",
    "zsh -fc 'if cp a CLAUDE.md; then :; fi'", "zsh -ic 'if cp a CLAUDE.md; then :; fi'",
    "env bash -xc 'while cp a CLAUDE.md; do break; done'",
    "bash -lc 'if rm -f .claude/edit-gates; then :; fi'", "bash -c 'bash -c \"! cp a CLAUDE.md\"'",
    "bash -c 'sh -c \"if cp a CLAUDE.md; then :; fi\"'",
    "env -i bash -c 'bash -c \"if cp a CLAUDE.md; then :; fi\"'",
    "x=1 eval 'if cp a CLAUDE.md; then :; fi'", "FOO=1 eval '! rm -f .claude/edit-gates'",
    "command eval '! cp a CLAUDE.md'", "builtin eval 'until cp a CLAUDE.md; do :; done'",
    "eval -- 'if cp a CLAUDE.md; then :; fi'", "eval time ! cp a CLAUDE.md",
    "eval 'time if cp a CLAUDE.md; then :; fi'", "cat <(echo a)#c; time ! cp a CLAUDE.md"]
R2_F1_TIME = [
    "time -p if cp a CLAUDE.md; then :; fi", "time -p ! cp a CLAUDE.md",
    "time -p while cp a CLAUDE.md; do break; done", "time -p until cp a CLAUDE.md; do :; done",
    "time -p if ! mv a CLAUDE.md; then :; fi", "time -p while ! rm -f .claude/edit-gates; do :; done",
    "time -p if cd docs; then printf x >> ../CLAUDE.md; fi",
    "time -p ! cd docs; printf x >> ../CLAUDE.md"]
R2_F1_CONTROLS = [
    "eval 'if cp a CLAUDE.md; then :; fi'", "sh -c 'if cp a CLAUDE.md; then :; fi'",
    "bash -lc 'if true; then cp a CLAUDE.md; fi'", "bash -lc 'cp a CLAUDE.md'",
    "time if cp a CLAUDE.md; then :; fi", "time -p cp a CLAUDE.md"]


@pytest.mark.parametrize("command", R2_F1_INNER + R2_F1_TIME + R2_F1_CONTROLS)
def test_r2_r2_f1_a_reserved_word_in_an_inner_line_or_after_time_p(box, command):
    (box.repo / "docs").mkdir(exist_ok=True)
    assert len(R2_F1_INNER + R2_F1_TIME) == 30
    out = instructionguard.check(_bash(command, box.repo), box.env)
    decision, reason = _decision(out)
    assert decision == "deny", command
    assert f"`{_gated_path(box, command)}`" in reason, command
    if command in R2_F1_TIME:                     # the strict reading reads it
        assert reason == REASON.format(_gated_path(box, command)), command


# ---- review 2, R3 (F2): the loose reading splits at an `&` whose `<` or `>` is escaped ------
# There `&` is the shell's background operator and the next word starts a command. Each line
# was denied at db19d51 (which split at every `&`) and passed at 6aed3c5; shells write.

R3_F2_LINES = [
    "bash -lc 'echo \\>& cp a CLAUDE.md'", "bash -lc 'echo \\>\\>& cp a CLAUDE.md'",
    "bash -lc 'echo a\\<&cp a CLAUDE.md'", "eval 'echo \\<& cp a CLAUDE.md'",
    "eval \"echo \\\\>& cp a CLAUDE.md\"", "sh -ec 'echo \\<& rm -f .claude/edit-gates'",
    "cat <(echo a)#c; echo \\>& cp a CLAUDE.md", "cat <(echo a)#c; echo \\<& cp a CLAUDE.md",
    "cat <(echo a)#c\\>& cp a CLAUDE.md"]
R3_F2_CONTROLS = [
    "bash -lc 'echo & cp a CLAUDE.md'", "bash -lc 'echo \\>&& cp a CLAUDE.md'",
    "bash -lc 'echo \"a>\"& cp a CLAUDE.md'", "bash -lc 'echo x >&2& cp a CLAUDE.md'",
    "echo \\>& cp a CLAUDE.md",
    "bash -lc 'cp a >&2 CLAUDE.md'",              # 6aed3c5 denied it: `>&2` is no split
    "bash -lc 'echo x >&CLAUDE.md'"]              # review 1's R5 word


@pytest.mark.parametrize("command", R3_F2_LINES + R3_F2_CONTROLS)
def test_r2_r3_f2_an_escaped_redirect_sign_does_not_hold_the_ampersand(box, command):
    out = instructionguard.check(_bash(command, box.repo), box.env)
    decision, reason = _decision(out)
    assert decision == "deny", command
    assert f"`{_gated_path(box, command)}`" in reason, command


# ---- review 2, R4 (F3): a strict word is one credit however many folder states judged it ----
# A word with an absolute path judged in two states was two credits, and the spare cancelled a
# later loose target in the checkout. Called from a folder outside it (`{x}`); each line was
# denied at db19d51 and passed at 6aed3c5; shells write.

R4_F3 = [
    ("if false; then cd sub; fi; : > {x}/CLAUDE.md; cd {r} && bash -lc 'cp a CLAUDE.md'", "x"),
    ("if [ -d build ]; then cd build; fi; cp a {x}/CLAUDE.md; cd {r} && bash -lc 'cp a CLAUDE.md'",
     "x"),
    ("if false; then cd sub; fi; bash -c ': > {x}/CLAUDE.md'; cd {r} && bash -lc 'cp a CLAUDE.md'",
     "x"),
    ("if false; then cd sub; fi; : > {x}/CLAUDE.md; cd {r}; eval 'cp a CLAUDE.md'", "x"),
    ("if false; then cd sub; fi; rm -f {x}/.claude/edit-gates; cd {r} && "
     "bash -lc 'rm -f .claude/edit-gates'", "x"),
    ("if false; then cd sub; fi; echo x > {x}/CLAUDE.md; cd {r}; cat <(echo a)#c; cp a CLAUDE.md",
     "x"),
    ("false && {{ cd sub; }}; echo x > {x}/CLAUDE.md; cd {r}; cat <(echo a)#c; cp a CLAUDE.md", "x"),
    ("if false; then cd sub; fi; echo x > {x}/notes/CLAUDE.md; cd {r}; cat <(echo a)#c; "
     "cp a CLAUDE.md", "x/notes")]
R4_F3_CONTROLS = [(": > {x}/CLAUDE.md; cd {r} && bash -lc 'cp a CLAUDE.md'", "x"),
                  ("cd {r} && bash -lc 'cp a CLAUDE.md'", "x")]


@pytest.mark.parametrize("line,where", R4_F3 + R4_F3_CONTROLS)
def test_r2_r4_f3_a_word_judged_in_two_states_is_one_credit(box, line, where):
    x = box.tmp / "x"
    (x / "notes").mkdir(parents=True)
    command = line.format(x=x, r=box.repo)
    out = instructionguard.check(_bash(command, box.tmp / where), box.env)
    decision, reason = _decision(out)
    assert decision == "deny", command
    assert f"`{_gated_path(box, command)}`" in reason, command


def test_r2_r4_one_credit_a_word_and_command(box):
    command = f"if false; then cd sub; fi; : > {box.tmp}/CLAUDE.md"
    found = shellreader._strict(command, str(box.repo), box.env, 0, False, True, set())
    assert [(k, p) for k, p, _, _ in found] == [("write", str(box.tmp / "CLAUDE.md"))] * 2
    assert [w for _, _, w, _ in found].count(None) == 1      # the second state's: no credit


# ---- review 2, R5 (F4): a run of loose pieces stands for a strict word only at its path -----
# A redirect to a quoted name with a blank is listed by the loose reading as its first piece
# only, so its want was left for another command's run of the same words in another folder.
# Each line was denied at db19d51 and passed at 6aed3c5; shells write (`sub` stands for the
# reviewer's `docs`, which this box gates).

R5_F4 = [
    ("cd sub; echo x > \"a CLAUDE.md\"; cd ..; bash -lc 'tee a CLAUDE.md'", ""),
    ("echo x > \"a CLAUDE.md\"; cd {r} && bash -lc 'tee a CLAUDE.md'", "x"),
    ("cd sub; echo x > \"a CLAUDE.md\"; cd ..; eval 'tee a CLAUDE.md' </dev/null", ""),
    ("cd sub; echo x > \"a CLAUDE.md\"; cd ..; sh -ec 'tee a CLAUDE.md'", ""),
    ("cd sub; python3 -c \"open('a CLAUDE.md','w')\"; cd ..; bash -lc 'tee a CLAUDE.md'", ""),
    ("cd sub; echo x > \"a CLAUDE.md\"; cd ..; cat <(echo a)#c; tee a CLAUDE.md", ""),
    ("cd sub && : > \"notes CLAUDE.md\" && cd .. && bash -lc 'tee -a notes CLAUDE.md'", ""),
    ("cd sub; echo x > \"s/a/b/ CLAUDE.md\"; cd ..; bash -lc 'sed -i.bak s/a/b/ CLAUDE.md'", "")]
R5_F4_CONTROLS = [
    ("cd sub; cp x \"a CLAUDE.md\"; cd ..; bash -lc 'tee a CLAUDE.md'", ""),
    ("cd sub; echo x > \"a CLAUDE.md\"; cd ..; bash -lc 'cp a CLAUDE.md'", ""),
    ("cd sub; echo x > \"a .claude/edit-gates\"; cd ..; bash -lc 'rm -f a .claude/edit-gates'",
     "")]


@pytest.mark.parametrize("line,where", R5_F4 + R5_F4_CONTROLS)
def test_r2_r5_f4_a_run_stands_for_a_word_only_at_its_path(box, line, where):
    (box.repo / "sub").mkdir()
    (box.tmp / "x").mkdir()
    command = line.format(r=box.repo)
    out = instructionguard.check(_bash(command, box.tmp / where if where else box.repo), box.env)
    decision, reason = _decision(out)
    assert decision == "deny", command
    assert f"`{_gated_path(box, command)}`" in reason, command


def test_r2_r5_the_run_in_the_words_folder_still_stands_for_it(box):
    # g6's ordinary lines (brief 3's R8): the loose reading lists the word's pieces in the
    # folder the strict reading judged it in, so they are spent
    for command in ("sed -i '' 's/the CLAUDE.md file/x/' notes.md", "tee 'x CLAUDE.md' < a",
                    "cd sub; rm -f \"a CLAUDE.md\""):
        assert instructionguard.check(_bash(command, box.repo), box.env) == {}, command
