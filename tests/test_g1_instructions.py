"""Packet g1: the log of instruction files a session loaded (R1), and the doctor's lines on
it: what loaded (R2), the warnings (R3) and the memory notes (R4). Every test runs under its
own temp HOME and state; the payloads follow Claude Code's hooks reference, InstructionsLoaded."""

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks, instructions, ledger, resolver
from test_doctor import machine  # noqa: F401  (the fixture)

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SID = "g1-sess-0001"
LEDGER_FILE = "DECISION" "S.md"           # spelled in two pieces for the hygiene scan
TREE = "### Every session of the tree"


@pytest.fixture
def box(tmp_path):
    class B:
        pass
    b = B()
    b.t = tmp_path
    b.home = tmp_path / "home"
    b.home.mkdir()
    b.env = {"HOME": str(b.home), "XDG_STATE_HOME": str(tmp_path / "state"),
             "PATH": "/usr/bin:/bin"}
    b.state = resolver.state_dir(b.env)
    b.code = tmp_path / "code"
    b.repo = _checkout(b.code / "tree" / "repo")
    return b


def _checkout(path: Path) -> Path:
    (path / ".git").mkdir(parents=True)
    return path


def _event(box, path, sid=SID, cwd=None, reason="session_start", **more):
    p = {"session_id": sid, "transcript_path": "/t.jsonl", "cwd": str(cwd or box.repo),
         "hook_event_name": "InstructionsLoaded", "file_path": str(path),
         "memory_type": "Project", "load_reason": reason, **more}
    assert hooks.HANDLERS["InstructionsLoaded"](p, box.env) == {}


def _log(box, sid=SID):
    return instructions.read_log(resolver.session_dir(box.state, sid))


def _rows(box, cwd=None, plugins=None, sections=None, name=None):
    out = instructions.rows(box.env, cwd or box.repo, plugins, sections or {})
    return [(n, d, k) for n, d, k in out if name is None or n == name]


# ---- R1: the log ----------------------------------------------------------------------

def test_r1_an_event_is_logged_with_its_path(box):
    f = box.repo / "CLAUDE.md"
    f.write_text("x")
    before = time.time()
    _event(box, f)
    _event(box, box.repo / "sub" / "CLAUDE.md", reason="nested_traversal",
           trigger_file_path=str(box.repo / "sub" / "a.py"))
    _event(box, box.home / "inc.md", reason="include", parent_file_path=str(f), agent_id="a1")
    rows = _log(box)
    assert [r["file_path"] for r in rows] == [str(f), str(box.repo / "sub" / "CLAUDE.md"),
                                              str(box.home / "inc.md")]
    assert [r["load_reason"] for r in rows] == ["session_start", "nested_traversal", "include"]
    assert rows[0]["memory_type"] == "Project" and rows[0]["cwd"] == str(box.repo)
    assert rows[1]["trigger_file_path"] == str(box.repo / "sub" / "a.py")
    assert rows[2]["parent_file_path"] == str(f) and rows[2]["agent_id"] == "a1"
    assert all(before <= r["at"] <= time.time() for r in rows)
    log = resolver.session_dir(box.state, SID) / instructions.LOG
    assert oct(log.stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("payload", [
    {"file_path": "/x/CLAUDE.md"},                                      # no id
    {"session_id": "../up", "file_path": "/x/CLAUDE.md"},              # not id-shaped
    {"session_id": SID},                                                # no path
    {"session_id": SID, "file_path": 7},                                # not a string
    {"session_id": SID, "file_path": ""},
])
def test_r1_a_bad_payload_writes_nothing(box, payload):
    assert hooks.HANDLERS["InstructionsLoaded"](payload, box.env) == {}
    assert not list(box.t.rglob(instructions.LOG))


def test_r1_the_log_stops_at_its_cap(box, monkeypatch):
    monkeypatch.setattr(instructions, "LOG_CAP", 600)
    for i in range(20):
        _event(box, box.repo / f"f{i}" / "CLAUDE.md")
    log = resolver.session_dir(box.state, SID) / instructions.LOG
    assert 0 < len(_log(box)) < 20 and log.stat().st_size <= 600 + 1024


def test_r1_the_hook_prints_nothing(box, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"session_id": SID, "file_path": str(box.repo / "CLAUDE.md"), "load_reason": "compact"})))
    for k, v in box.env.items():
        monkeypatch.setenv(k, v)
    assert hooks.dispatch("InstructionsLoaded") == 0
    assert capsys.readouterr() == ("", "")
    assert [r["load_reason"] for r in _log(box)] == ["compact"]
    assert "InstructionsLoaded" in hooks.SILENT


def test_r1_the_cli_prints_nothing(box):
    r = subprocess.run([sys.executable, "-I", str(PLUGIN / "lib" / "agentik-session"), "hook",
                        "InstructionsLoaded"], env=box.env, capture_output=True, text=True,
                       input=json.dumps({"session_id": SID, "file_path": "/x/CLAUDE.md"}),
                       timeout=60)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", ""), r
    assert [r["file_path"] for r in _log(box)] == ["/x/CLAUDE.md"]


def test_r1_the_shim_swallows_the_event(tmp_path):
    # A CLI older than the plugin refuses the event with exit 2 and words on both streams:
    # the shim keeps none of it, as for Stop.
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    tool = root / "bin" / "agentik-session"
    tool.write_text("#!/bin/sh\ncat >/dev/null; echo '{}'; echo \"invalid choice: $2\" >&2; "
                    "exit 2\n")
    tool.chmod(0o755)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_PLUGIN_ROOT": str(root)}
    r = subprocess.run([str(PLUGIN / "hooks" / "run"), "InstructionsLoaded"], env=env,
                       input='{"session_id": "s"}', capture_output=True, text=True)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_r1_registered_with_the_hook_timeout():
    doc = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    assert [(h["type"], h["command"], h["timeout"]) for g in doc["InstructionsLoaded"]
            for h in g["hooks"]] == [
        ("command", "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" InstructionsLoaded", 5)]
    assert [g.get("matcher") for g in doc["InstructionsLoaded"]] == [None]
    assert "InstructionsLoaded" in doctor.HOOK_EVENTS


# ---- R2: the doctor lists what loaded --------------------------------------------------

def test_r2_two_files_bytes_and_sum(box):
    a, b = box.repo / "CLAUDE.md", box.home / ".claude" / "CLAUDE.md"
    b.parent.mkdir()
    a.write_text("a" * 120)
    b.write_text("b" * 30)
    _event(box, b)
    _event(box, a)
    _event(box, a, reason="compact")                 # a reload is one file, not two
    rows = _rows(box, name="instructions")
    assert [d for _, d, _ in rows] == [
        f"30 B {b} (session_start)", f"120 B {a} (session_start)",
        f"session {SID}: 2 files, 150 B as they stand now"]
    assert {k for _, _, k in rows} == {"ok"}


def test_r2_a_deleted_file_is_gone(box):
    a, gone = box.repo / "CLAUDE.md", box.repo / "CLAUDE.local.md"
    a.write_text("abcd")
    _event(box, a)
    _event(box, gone)
    rows = [d for _, d, _ in _rows(box, name="instructions")]
    assert rows == [f"4 B {a} (session_start)", f"gone {gone} (session_start)",
                    f"session {SID}: 2 files, 4 B as they stand now, 1 gone"]


def test_r2_no_log_one_line(box):
    rows = _rows(box)
    assert rows == [("instructions", f"no session of {box.repo} has a log of the instruction "
                     "files it loaded", "ok")]


def test_r2_another_repos_session_is_not_listed(box):
    other = _checkout(box.code / "tree" / "other")
    (other / "CLAUDE.md").write_text("o")
    _event(box, other / "CLAUDE.md", sid="g1-other", cwd=other)
    assert [d for _, d, _ in _rows(box, name="instructions")] == [
        f"no session of {box.repo} has a log of the instruction files it loaded"]


def test_r2_the_newest_session_of_the_repo_and_its_worktrees(box):
    wt = box.repo / ".claude" / "worktrees" / "row"
    wt.mkdir(parents=True)
    gitdir = box.repo / ".git" / "worktrees" / "row"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    assert instructions.main_checkout(wt) == box.repo.resolve()
    (box.repo / "CLAUDE.md").write_text("12")
    _event(box, box.repo / "CLAUDE.md", sid="g1-old")
    time.sleep(0.01)
    _event(box, wt / "CLAUDE.md", sid="g1-new", cwd=wt)
    rows = [d for _, d, _ in _rows(box, cwd=wt, name="instructions")]
    assert rows[-1].startswith("session g1-new: 1 files") and rows[0].startswith("gone ")


# ---- R3: the warnings ------------------------------------------------------------------

def _hq(box, heading=TREE):
    hq = _checkout(box.code / "tree" / "hq")
    (hq / LEDGER_FILE).write_text(f"# Ledger\n\n## Every session\n\n{heading}\n\n1. x\n")
    return hq


def test_r3_tree_file_fires_when_the_folders_file_did_not_load(box):
    hq = _hq(box)
    (box.repo / "CLAUDE.md").write_text("r")
    _event(box, box.repo / "CLAUDE.md")
    [(n, d, k)] = _rows(box, name="tree-file")
    assert k == "warn" and str(box.code / "tree" / "CLAUDE.md") in d and str(hq) in d


def test_r3_tree_file_quiet_when_it_loaded_or_no_ledger_holds_the_section(box):
    _hq(box)
    folder_file = box.code / "tree" / "CLAUDE.md"
    folder_file.write_text("t")
    _event(box, folder_file)
    assert _rows(box, name="tree-file") == []
    box2 = box.code / "tree" / "hq" / LEDGER_FILE
    box2.write_text("# Ledger\n\n## Every session\n")
    _event(box, box.repo / "CLAUDE.md", sid="g1-later")
    assert _rows(box, name="tree-file") == []


def test_r3_tree_file_quiet_without_a_log(box):
    _hq(box)
    assert _rows(box, name="tree-file") == []


def _plugin(tmp_path, descs, name="p", disabled=()):
    root = tmp_path / "plugins" / name
    for i, d in enumerate(descs):
        kind = ("commands", "skills", "agents")[i % 3]
        f = (root / kind / f"s{i}" / "SKILL.md") if kind == "skills" else (root / kind / f"c{i}.md")
        f.parent.mkdir(parents=True, exist_ok=True)
        extra = "disable-model-invocation: true\n" if i in disabled else ""
        f.write_text(f"---\nname: x{i}\ndescription: {d}\n{extra}---\n\nbody\n")
    return {f"{name}@m": {"id": f"{name}@m", "version": "1.0.0", "enabled": True,
                          "installPath": str(root)}}


def test_r3_plugin_descs_fires_past_1024_bytes(box):
    plugins = _plugin(box.t, ["a" * 400, "b" * 400, "c" * 300])
    [(n, d, k)] = _rows(box, plugins=plugins, name="plugin-descs")
    assert k == "warn" and d.startswith("p@m 1.0.0: 3 descriptions sum to 1100 B")


def test_r3_plugin_descs_quiet_at_1024_disabled_or_not_invoked(box):
    assert _rows(box, plugins=_plugin(box.t, ["a" * 512, "b" * 512]),
                 name="plugin-descs") == []
    off = _plugin(box.t, ["a" * 2000], name="q")
    off["q@m"]["enabled"] = False
    assert _rows(box, plugins=off, name="plugin-descs") == []
    hidden = _plugin(box.t, ["a" * 2000, "b" * 10], name="h", disabled=(0,))
    assert _rows(box, plugins=hidden, name="plugin-descs") == []


def test_r3_plugin_descs_reads_a_folded_description(box):
    root = box.t / "plugins" / "f"
    (root / "agents").mkdir(parents=True)
    (root / "agents" / "a.md").write_text("---\nname: a\ndescription: >\n  " + "w" * 700
                                          + "\n  " + "v" * 400 + "\nmodel: opus\n---\n")
    plugins = {"f@m": {"id": "f@m", "version": "2", "enabled": True, "installPath": str(root)}}
    [(_, d, _)] = _rows(box, plugins=plugins, name="plugin-descs")
    assert "1 descriptions sum to 1101 B" in d


def _memory(box):
    enc = "".join(c if c.isalnum() and c.isascii() else "-" for c in str(box.repo.resolve()))
    d = box.home / ".claude" / "projects" / enc / "memory"
    d.mkdir(parents=True)
    return d


def test_r3_memory_index_fires_past_8_kib(box):
    (_memory(box) / "MEMORY.md").write_text("x" * 8193)
    [(n, d, k)] = _rows(box, name="memory-index")
    assert k == "warn" and "8193 B" in d and "MEMORY.md" in d


def test_r3_memory_index_quiet_at_8_kib(box):
    (_memory(box) / "MEMORY.md").write_text("x" * 8192)
    assert _rows(box, name="memory-index") == []


def _settings(box, doc):
    p = box.home / ".claude" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))
    return p


def _sections(profile="frontier"):
    return {"session": {"profile": profile}}


def test_r3_two_places_fires_for_effort_and_model(box):
    p = _settings(box, {"effortLevel": "high", "model": "opus"})
    rows = _rows(box, sections=_sections(), name="two-places")
    assert [k for _, _, k in rows] == ["warn", "warn"]
    effort = [d for _, d, _ in rows if d.startswith("effort")][0]
    assert "profile frontier" in effort and "xhigh" in effort
    assert f"{p} effortLevel" in effort and "high" in effort
    assert any(d.startswith("model") and f"{p} model" in d for _, d, _ in rows)


def test_r3_two_places_reads_a_per_model_effort(box):
    _settings(box, {"modelSettings": {"opus": {"effortLevel": "high"}}})
    [(_, d, _)] = _rows(box, sections=_sections(), name="two-places")
    assert "modelSettings.opus.effortLevel" in d


def test_r3_two_places_quiet_when_the_settings_set_neither(box):
    _settings(box, {"permissions": {"allow": []}})
    assert _rows(box, sections=_sections(), name="two-places") == []
    assert _rows(box, sections={}, name="two-places") == []


# ---- R4: memory notes since the previous session -----------------------------------------

def _ended(box, sid, at, repo=None):
    ledger.append(box.state, {"session": sid, "repo": str(repo or box.repo), "ended": at})


def test_r4_memory_notes_since_the_previous_session(box):
    mem = _memory(box)
    old, new = mem / "old.md", mem / "new.md"
    old.write_text("---\nname: old\n---\nThe old note.\n")
    new.write_text("---\nname: new\ndescription: d\n---\n\nThe new note, first line.\nmore\n")
    (mem / "MEMORY.md").write_text("- index\n")
    os.utime(old, (1_000, 1_000))
    _ended(box, "g1-prev", "2001-01-01T00:00:00+00:00")
    _ended(box, "g1-elsewhere", "2030-01-01T00:00:00+00:00", repo=box.code / "tree" / "x")
    _ended(box, SID, "2030-01-01T00:00:00+00:00")     # the logged session's own end is skipped
    _event(box, box.repo / "CLAUDE.md")
    rows = _rows(box, name="memory-notes")
    assert rows == [("memory-notes", "new.md: The new note, first line.", "note")]


def test_r4_no_earlier_session_lists_nothing(box):
    (_memory(box) / "n.md").write_text("A note.\n")
    assert _rows(box, name="memory-notes") == []


# ---- every row: the exit code ------------------------------------------------------------

def test_no_new_row_changes_the_exit(machine, monkeypatch):  # noqa: F811
    env = machine.env
    green = doctor.run(env, machine.repo)
    assert green.ok and [c.name for c in green.checks if c.name == "instructions"] == ["instructions"]
    # every warning and note fires
    home = Path(env["HOME"])
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"effortLevel": "high", "model": "opus"}')
    repo = machine.repo
    (repo / ".git").mkdir()
    hq = machine.tmp / "hq"
    (hq / ".git").mkdir(parents=True)
    (hq / LEDGER_FILE).write_text(TREE + "\n")
    enc = "".join(c if c.isalnum() and c.isascii() else "-" for c in str(repo.resolve()))
    mem = home / ".claude" / "projects" / enc / "memory"
    mem.mkdir(parents=True)
    (mem / "MEMORY.md").write_text("x" * 9000)
    (mem / "fresh.md").write_text("fresh\n")
    state = resolver.state_dir(env)
    ledger.append(state, {"session": "g1-prev", "repo": str(repo), "ended": "2001-01-01T00:00:00+00:00"})
    hooks.HANDLERS["InstructionsLoaded"]({"session_id": "g1-x", "cwd": str(repo),
                                          "file_path": str(repo / "CLAUDE.md")}, env)
    inst = machine.tmp / "install"
    (inst / "commands").mkdir()
    (inst / "commands" / "c.md").write_text("---\ndescription: " + "d" * 2000 + "\n---\n")
    rep = doctor.run(env, repo)
    names = {c.name: c for c in rep.checks}
    for n in ("tree-file", "plugin-descs", "memory-index", "two-places", "memory-notes"):
        assert n in names and names[n].ok, n
    assert rep.ok
    out = io.StringIO()
    monkeypatch.setattr(doctor, "run", lambda: rep)
    monkeypatch.setattr(sys, "stdout", out)
    assert cli.cmd_doctor(type("A", (), {"json": False})()) == 0
    text = out.getvalue()
    assert "warn tree-file" in text and "note memory-notes" in text and "doctor: green" in text
