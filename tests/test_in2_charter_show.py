"""Packet in2 (design/packets/in2-charter-show.md): `charter show [REPO...] [--json]`, and the
charter's seventh part, `## Waits on the owner`, known to `open`, `check` and `close`.

Each case is an acceptance line of the packet's §3, through `cli.main`, in temp repos `pear`
and `quince` under a temp HOME and state home. At 148fde3 `charter show` was argparse's
`invalid choice` (exit 2) and `open` wrote four `##` parts."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, cli, hooks

SID = "cccccccc-0000-0000-0000-0000000000a2"
CLEAN = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE",
         "CLAUDE_SESSION_HELPER", "RELAY_ROW")
SECTION = {"ceilings": {"context": 180000, "turns": 400}, "window": 200000,
           "checkpoint_at": 0.8, "charter": {"dir": "history/sittings"}}

HAND = "- hand: install the press; `make -C pear install`"
PROSE = "- Questions 4 and 5; the barn's key."
NEXT1 = "Prune the north rows first."
NEXT2 = "Then the south rows, after the rain."
SHAPE_W = ("Waits on the owner line is not '- hand: <what>; `<command>`' or '- none' alone: ")
EMPTY_W = "Waits on the owner is empty: write - none, or the hand lines"
BESIDE_W = "Waits on the owner has '- none' beside other lines: drop '- none' or the others"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def form(title="pear, prune the orchard", waits=(HAND, PROSE), next_act=(NEXT1, NEXT2),
         head="## Waits on the owner", date="2026-11-13", n=1):
    part = "" if waits is None else head + "\n" + "".join(l + "\n" for l in waits) + "\n"
    return (f"# Sitting {date}-{n}: {title}\n\n| item | value |\n|---|---|\n| goal | g |\n"
            "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n"
            "## Done-ness\n- [x] a\n\n## Handover\n- open by level: none yet\n\n"
            + part + "## While waiting\n- none\n\n## Next act\n"
            + "".join(l + "\n" for l in next_act))


@pytest.fixture
def box(tmp_path, monkeypatch):
    """HOME, the state home and the repos under one temp root: `pear` (a git repo, two
    charters), `quince` (a prose file), `bare` (no charter); cwd the root."""
    for k in CLEAN:
        monkeypatch.delenv(k, raising=False)
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    repos = tmp_path / "repos"
    pear = repos / "pear"
    sit = pear / "history" / "sittings"
    sit.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(pear)], check=True)
    (sit / "2026-11-12-2.md").write_text(form(date="2026-11-12", n=2, title="pear, older"))
    (sit / "2026-11-13-1.md").write_text(form())
    (pear / "inside").mkdir()
    q = repos / "quince" / "history" / "sittings"
    q.mkdir(parents=True)
    (q / "2026-11-13-1.md").write_text("Some prose about quinces.\nNo heading at all.\n")
    (repos / "bare").mkdir()
    monkeypatch.chdir(repos)
    return tmp_path


def _tree(root: Path) -> dict:
    out = {}
    for d, dirs, files in os.walk(root):
        for x in dirs:
            out[os.path.join(d, x)] = None
        for x in files:
            p = os.path.join(d, x)
            out[p] = Path(p).read_bytes() if not os.path.islink(p) else os.readlink(p)
    return out


def _show(*argv):
    rc, out, err = run("charter", "show", *argv, "--json")
    assert rc == 0, err
    return json.loads(out)


# 1. the object
def test_in2_1_show_json(box):
    pear = box / "repos" / "pear"
    doc = _show(str(pear))
    assert set(doc) == {"schema", "ok", "repos", "skipped"}
    assert doc["schema"] == "agentik.charter/1" and doc["ok"] is True and doc["skipped"] == []
    (r,) = doc["repos"]
    f = pear / "history" / "sittings" / "2026-11-13-1.md"
    assert r["repo"] == os.path.realpath(pear) and r["file"] == os.path.realpath(f)
    assert (r["name"], r["date"], r["n"]) == ("2026-11-13-1", "2026-11-13", 1)
    assert r["mtime"] == int(f.stat().st_mtime) and isinstance(r["mtime"], int)
    assert r["closed"] is False and r["title"] == "pear, prune the orchard"
    assert r["parts"] == ["title", "table", "Done-ness", "Handover", "Waits on the owner",
                          "While waiting", "Next act"]
    assert r["refusals"] == [] and r["next_act"] == NEXT1
    lines = f.read_text().splitlines()
    assert r["waits"] == [
        {"line": lines.index(HAND) + 1, "what": "install the press",
         "command": "make -C pear install"},
        {"line": lines.index(PROSE) + 1, "what": PROSE, "command": None}]


# 2. the text view
def test_in2_2_show_text(box):
    rc, out, err = run("charter", "show", str(box / "repos" / "pear"))
    assert (rc, err) == (0, "")
    assert out.splitlines() == [
        "== pear  2026-11-13-1  2 for the owner's hand",
        f"next  {NEXT1}",
        "hand  install the press; `make -C pear install`",
        f"hand  {PROSE}  (no command)"]


# 3. the newest, and --dir
def test_in2_3_newest_and_dir(box):
    pear = box / "repos" / "pear"
    sit = pear / "history" / "sittings"
    for name in ("2026-11-13-9.md", "2026-11-13-2-row.md", "2026-11-13-10.md"):
        (sit / name).write_text(form())
    (sit / "2026-11-14-1.txt").write_text(form())
    (sit / "notes.md").write_text(form())
    assert _show(str(pear))["repos"][0]["name"] == "2026-11-13-10"
    (pear / "notes").mkdir()
    (pear / "notes" / "2026-11-01-3-a.md").write_text(form())
    (pear / "notes" / "2026-11-01-3.md").write_text(form())
    doc = _show(str(pear), "--dir", "notes")
    assert doc["repos"][0]["file"] == os.path.realpath(pear / "notes" / "2026-11-01-3.md")
    (pear / ".claude" / "agentik").mkdir(parents=True)
    (pear / ".claude" / "agentik" / "config.yaml").write_text(
        "session:\n  charter:\n    dir: notes\n")
    assert _show(str(pear))["repos"][0]["name"] == "2026-11-01-3"


# 4. outside the form, the skips, the default REPO
def test_in2_4_prose_and_skips(box, monkeypatch):
    repos = box / "repos"
    q = repos / "quince" / "history" / "sittings" / "2026-11-13-1.md"
    doc = _show(str(repos / "quince"))
    (r,) = doc["repos"]
    assert r["refusals"] == charter.check_text(q.read_bytes()) and r["refusals"]
    assert r["parts"] == [] and r["next_act"] is None and r["waits"] is None
    assert r["title"] is None and r["closed"] is False
    rc, out, err = run("charter", "show", str(repos / "quince"))
    assert rc == 0
    assert [l for l in out.splitlines() if l.startswith("form  ")] == [
        f"form  {x}" for x in r["refusals"]]
    assert out.splitlines()[:2] == ["== quince  2026-11-13-1  no Waits part", "next  (none)"]
    doc = _show("pear", "quince", "nowhere", "bare")
    assert [x["repo"] for x in doc["repos"]] == [os.path.realpath(repos / "pear"),
                                                 os.path.realpath(repos / "quince")]
    assert doc["skipped"] == [{"repo": os.path.realpath(repos / "nowhere"),
                               "why": "not a directory"},
                              {"repo": os.path.realpath(repos / "bare"), "why": "no charter"}]
    rc, out, _ = run("charter", "show", "pear", "quince", "nowhere", "bare")
    assert rc == 0 and out.splitlines()[-2:] == ["skipped (not a directory): nowhere",
                                                 "skipped (no charter): bare"]
    assert "\n\n== quince" in out
    monkeypatch.chdir(repos / "pear" / "inside")
    assert _show()["repos"][0]["repo"] == os.path.realpath(repos / "pear")


def test_in2_4_unreadable_and_closed(box):
    pear = box / "repos" / "pear"
    f = pear / "history" / "sittings" / "2026-11-13-1.md"
    f.write_text(form().replace("- open by level: none yet\n",
                                "- open by level: none yet\n- exit taken: done; meter unknown\n"))
    r = _show(str(pear))["repos"][0]
    assert r["closed"] is True
    assert run("charter", "show", str(pear))[1].splitlines()[0].endswith("  closed")
    f.unlink()
    f.mkdir()                                  # a folder by the name: not readable as a file
    (pear / "history" / "sittings" / "2026-11-12-2.md").unlink()
    doc = _show(str(pear))
    assert doc["repos"] == [] and doc["skipped"] == [{"repo": os.path.realpath(pear),
                                                      "why": "unreadable"}]


# 5. a `;` inside <what> and the command
def test_in2_5_semicolons(box):
    pear = box / "repos" / "pear"
    line = "- hand: ask twice; then wait; `a; b | c`"
    (pear / "history" / "sittings" / "2026-11-13-1.md").write_text(form(waits=(line,)))
    (w,) = _show(str(pear))["repos"][0]["waits"]
    assert (w["what"], w["command"]) == ("ask twice; then wait", "a; b | c")
    assert charter.hand_line(line) == ("ask twice; then wait", "a; b | c")
    for bad in ("- hand: x; `a`b`", "- hand: x `a`", "- hand: ; `a`", "- hand: x; ``",
                "- hand: x; `a` ", "- hand x; `a`"):
        assert charter.hand_line(bad) is None, bad


# 6. the four warnings, the exits kept
def _warns(text, section=SECTION):
    return charter.warnings(text.encode(), section)


def test_in2_6_check_and_close_warn(box, monkeypatch):
    pear = box / "repos" / "pear"
    f = pear / "history" / "sittings" / "2026-11-13-1.md"
    monkeypatch.chdir(pear)
    rc, out, err = run("charter", "check", str(f))
    assert (rc, out, err) == (0, "", f"{f}: warning: {SHAPE_W}{PROSE}\n")
    c = pear / "c.md"
    shutil.copy(f, c)
    rc, out, err = run("charter", "close", "--exit", "goal met", str(c))
    assert rc == 0 and out.splitlines()[0] == str(c)
    assert err == f"{c}: warning: {SHAPE_W}{PROSE}\n"
    assert _warns(form(waits=("- none", HAND))) == [BESIDE_W]
    assert _warns(form(waits=())) == [EMPTY_W]
    assert _warns(form(head="## Waits on the Owner")) == [
        "heading '## Waits on the Owner' is not '## Waits on the owner'"]
    assert _warns(form(head="## Waits on the owner (in2)")) == [
        "heading '## Waits on the owner (in2)' is not '## Waits on the owner'"]
    for waits in (None, ("- none",), (HAND,), (HAND, "- hand: b; `c`")):
        assert _warns(form(waits=waits)) == [], waits
    off = {**SECTION, "pacing": {"enabled": False}, "priority": {"enabled": False}}
    assert _warns(form(waits=()), off) == [EMPTY_W]
    # after While waiting's warnings
    t = form(waits=()).replace("## While waiting\n- none\n", "## While waiting\n\n")
    assert _warns(t) == ["While waiting is empty: write - none, or the ready rows and owed "
                         "items", EMPTY_W]
    assert charter.check_text(form(waits=("x",)).encode()) == []


# 7. open writes the part
def test_in2_7_open_writes_the_part(box, monkeypatch):
    pear = box / "repos" / "pear"
    monkeypatch.chdir(pear)
    rc, out, err = run("charter", "open", "a made-up goal", "--dir", "fresh")
    assert rc == 0, err
    p = Path(out.strip())
    text = p.read_text()
    assert ("\n## Handover\n- open by level: none yet\n\n## Waits on the owner\n- none\n\n"
            "## While waiting\n- none\n\n## Next act\n") in text
    assert run("charter", "check", str(p)) == (0, "", "")
    rc, out, err = run("charter", "show", str(pear), "--dir", "fresh", "--json")
    r = json.loads(out)["repos"][0]
    assert r["waits"] == [] and r["parts"][4] == "Waits on the owner" and len(r["parts"]) == 7
    rc, out, err = run("charter", "show", str(pear), "--dir", "fresh")
    assert out.splitlines()[0].endswith("  0 for the owner's hand")


# 8. no write
@pytest.mark.parametrize("sid", [None, SID])
def test_in2_8_show_writes_nothing(box, monkeypatch, sid):
    if sid:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", sid)
    before = _tree(box)
    repos = box / "repos"
    for argv in ([], ["pear"], ["pear", "--json"], ["pear", "quince", "nowhere", "bare"],
                 ["pear", "--dir", "notes", "--json"]):
        assert run("charter", "show", *argv)[0] == 0
    monkeypatch.chdir(repos / "pear" / "inside")
    assert run("charter", "show")[0] == 0
    assert run("charter", "show", "--json")[0] == 0
    assert _tree(box) == before


# 9. a helper may call show
def _bash(cmd):
    return {"session_id": SID, "tool_name": "Bash", "tool_use_id": "toolu_in2",
            "tool_input": {"command": cmd}, "hook_event_name": "PreToolUse",
            "agent_id": "a1b2", "agent_type": "general-purpose"}


def _denied(out):
    h = (out or {}).get("hookSpecificOutput") or {}
    return h.get("permissionDecision") == "deny"


def test_in2_9_helper_show(box, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    for cmd in ("agentik-session charter show", "agentik-session charter show pear --json",
                "agentik session charter show . quince"):
        assert not _denied(hooks.pre_tool_use(_bash(cmd))), cmd
    assert "show" in hooks.CHARTER_READS and "check" in hooks.CHARTER_READS
    out = hooks.pre_tool_use(_bash('agentik-session charter open "g"'))
    assert _denied(out)
    assert ("(a helper's charter calls are `agentik-session charter check <file>` and "
            "`charter show`, the verb first)") in out["hookSpecificOutput"][
                "permissionDecisionReason"]
    assert _denied(hooks.pre_tool_use(_bash("agentik-session charter showx")))


# 10. usage
def test_in2_10_usage(box):
    rc, out, err = run("charter", "check", "--json", "x.md")
    assert rc == 2 and out == ""
    for action in ("open", "close"):
        assert run("charter", action, "--json", "x")[0] == 2
    rc, out, _ = run("charter", "--help")
    assert rc == 0 and "show" in out and "{open,check,close,show}" in out


def test_in2_docs_say_the_part_and_show():
    root = Path(__file__).resolve().parents[1]
    for rel in ("RUNBOOK.md", "plugin/skills/session/SKILL.md"):
        text = (root / rel).read_text()
        assert "## Waits on the owner" in text and "charter show" in text, rel
    assert "seven parts" in " ".join(charter.__doc__.split())


# ---- Review 1 (build 2): F1, F2, L2 and the hook's chained payloads ----------------------

_FIFOS: list = []


def _show_bounded(*argv, limit=2.0):
    """`show` in a thread, back within `limit` seconds or the test fails; a FIFO left
    blocking is then opened for writing and closed, so the thread ends."""
    got = {}
    t = threading.Thread(target=lambda: got.update(r=run("charter", "show", *argv)),
                         daemon=True)
    start = time.monotonic()
    t.start()
    t.join(limit)
    took = time.monotonic() - start
    if t.is_alive():
        for fifo in _FIFOS:
            try:
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            except OSError:
                pass
        t.join(5)
        pytest.fail(f"show did not return within {limit} s")
    return got["r"], took


@pytest.mark.parametrize("beside", [False, True], ids=["alone", "beside-a-good-repo"])
def test_in2_r1_f1_a_fifo_newest_is_unreadable(box, beside):
    repos = box / "repos"
    fifo = repos / "quince" / "history" / "sittings" / "2026-11-14-1.md"
    os.mkfifo(fifo)
    _FIFOS.append(str(fifo))
    argv = (["pear"] if beside else []) + ["quince", "--json"]
    (rc, out, err), took = _show_bounded(*argv)
    assert rc == 0 and took < 2.0, err
    doc = json.loads(out)
    assert doc["skipped"] == [{"repo": os.path.realpath(repos / "quince"), "why": "unreadable"}]
    assert [r["name"] for r in doc["repos"]] == (["2026-11-13-1"] if beside else [])


@pytest.mark.parametrize("kind", ["device-link", "over-the-bound"])
def test_in2_r1_f1_a_device_or_a_huge_file_is_unreadable(box, kind):
    repos = box / "repos"
    newest = repos / "quince" / "history" / "sittings" / "2026-11-14-1.md"
    if kind == "device-link":
        os.symlink(os.devnull, newest)
    else:
        newest.write_bytes(b"x" * (getattr(charter, "SHOW_BOUND", 65536) + 1))
    doc = _show("pear", "quince")
    assert [r["name"] for r in doc["repos"]] == ["2026-11-13-1"]
    assert doc["skipped"] == [{"repo": os.path.realpath(repos / "quince"), "why": "unreadable"}]


def test_in2_r1_f1_check_still_reads_the_file_it_is_handed(box):
    big = box / "repos" / "pear" / "big.md"
    big.write_bytes(b"x" * (getattr(charter, "SHOW_BOUND", 65536) + 1))
    rc, _, err = run("charter", "check", str(big))
    assert rc == 2 and "ceiling" in err


@pytest.mark.parametrize("value", ["5", "[a, b]", "''"], ids=["int", "list", "empty"])
@pytest.mark.parametrize("beside", [False, True], ids=["alone", "beside-a-good-repo"])
def test_in2_r1_f2_a_charter_dir_not_a_string_is_the_default(box, value, beside):
    repos = box / "repos"
    cfg = repos / "quince" / ".claude" / "agentik"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text(f"session:\n  charter:\n    dir: {value}\n")
    argv = (["pear"] if beside else []) + ["quince", "--json"]
    rc, out, err = run("charter", "show", *argv)
    assert rc == 0 and "Traceback" not in err, err
    doc = json.loads(out)
    assert doc["repos"][-1]["file"] == os.path.realpath(
        repos / "quince" / "history" / "sittings" / "2026-11-13-1.md")
    assert len(doc["repos"]) == (2 if beside else 1) and doc["skipped"] == []


def test_in2_r1_l2_every_waits_part_is_read(box, monkeypatch):
    pear = box / "repos" / "pear"
    f = pear / "history" / "sittings" / "2026-11-13-1.md"
    text = form(waits=("- none",)).replace(
        "## Next act\n", "## Waits on the owner\n" + HAND + "\n\n## Next act\n")
    f.write_text(text)
    (w,) = _show(str(pear))["repos"][0]["waits"]
    assert (w["line"], w["what"]) == (text.splitlines().index(HAND) + 1, "install the press")
    two = "Waits on the owner has 2 parts: keep one '## Waits on the owner'"
    assert _warns(text) == [two]
    monkeypatch.chdir(pear)
    assert run("charter", "check", str(f)) == (0, "", f"{f}: warning: {two}\n")
    assert _warns(form()) == [SHAPE_W + PROSE]                         # one part: as before


L = "agentik-session"


@pytest.mark.parametrize("cmd", [
    f"{L} charter show; {L} charter close",
    f"{L} charter show && {L} charter open g",
    f"{L} charter show | xargs {L} charter open",
    f"{L} charter show\n{L} charter close",
    f"{L} charter show $({L} charter open g)",
], ids=["semicolon", "and", "pipe-xargs", "newline", "subst"])
def test_in2_r1_the_hook_denies_a_writer_after_show(box, monkeypatch, cmd):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    assert not _denied(hooks.pre_tool_use(_bash(f"{L} charter show")))
    assert not _denied(hooks.pre_tool_use(_bash(f"{L} charter show pear --json")))
    out = hooks.pre_tool_use(_bash(cmd))
    assert _denied(out), cmd
    assert "`charter show`, the verb first" in out["hookSpecificOutput"][
        "permissionDecisionReason"]
