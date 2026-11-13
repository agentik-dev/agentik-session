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

from claude_session import cli, doctor, hooks, instructionguard, instructions, resolver
from test_doctor import machine  # noqa: F401  (the fixture)

ROOT = Path(__file__).resolve().parents[1]
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
    src = (ROOT / "plugin" / "lib" / "claude_session" / "instructionguard.py").read_text()
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
          "echo x >> `pwd`/CLAUDE.md", "echo 'x >> CLAUDE.md", "echo x >> notes.md",
          "agentik decisions render --into CLAUDE.md",
          "agentik session gates write CLAUDE.md --from /tmp/d.md --expect 0123abcd",
          "cat CLAUDE.md", "grep x CLAUDE.md > /tmp/out.txt", "git status",
          "git checkout -- CLAUDE.md.orig", "cp CLAUDE.md /tmp/x", "mv /tmp/a /tmp/b",
          "echo '>> CLAUDE.md'", "python3 -c \"print('CLAUDE.md')\"", "rm notes.md",
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
    tree = ast.parse((ROOT / "plugin" / "lib" / "claude_session" / "instructionguard.py")
                     .read_text())
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
    tree = ast.parse((ROOT / "plugin" / "lib" / "claude_session" / "instructionguard.py")
                     .read_text())
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
    "popd; printf x >> CLAUDE.md", "cd $X; printf x >> CLAUDE.md", "cd - && echo x > CLAUDE.md",
    "echo x >> $X", "echo x >> CLAUDE.m*", "echo 'x >> CLAUDE.md",
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
    command = "cd docs; ) ; printf x >> ../CLAUDE.md"
    assert instructionguard.check(_bash(command, box.repo), box.env) == {}
    assert [r["decision"] for r in _log(box)] == ["open"]


# ---- g5: a `#` inside a word is no comment's start (u3's review, round 1, R1-F2) ----------

G5_INWORD = ["echo x#y; cp a CLAUDE.md", "v=${TAG#v}; cp a CLAUDE.md", "echo $#; cp a CLAUDE.md",
             "echo ${#a[@]}; cp a CLAUDE.md", "echo a\\#b; cp a CLAUDE.md",
             "echo x #c\ncp a CLAUDE.md", "echo \"x #y\"; cp a CLAUDE.md",
             "echo 'a#b'; cp a CLAUDE.md"]


@pytest.mark.parametrize("command", G5_INWORD)
def test_g5_an_inword_or_quoted_hash_hides_no_write(box, command):
    assert instructionguard.bash_targets(command, str(box.repo), box.env) == \
        [("write", str(box.repo / "CLAUDE.md"))], command
    out = instructionguard.check(_bash(command, box.repo), box.env)
    assert _decision(out) == ("deny", REASON.format(box.repo / "CLAUDE.md")), command


@pytest.mark.parametrize("command", ["echo x #y; cp a CLAUDE.md", "# cp a CLAUDE.md",
                                     "echo x;#y\ncd docs; cp a CLAUDE.md\n#z"])
def test_g5_a_comment_stays_one(box, command):
    found = instructionguard.bash_targets(command, str(box.repo), box.env)
    assert found == ([("write", str(box.repo / "docs" / "CLAUDE.md"))] if "docs" in command
                     else []), command


@pytest.mark.parametrize("command,words", [
    ("echo x#y", ["echo", "x#y"]), ("echo a\\#b", ["echo", "a#b"]),
    ("echo ${#a[@]} $# x", ["echo", "${#a[@]}", "$#", "x"]),
    ("echo \"x #y\" 'a#b' z", ["echo", "x #y", "a#b", "z"]), ("echo x #y z", ["echo", "x"])])
def test_g5_the_words_read_back_whole(command, words):
    assert [w for w, _ in instructionguard._commands(command)] == [words]
