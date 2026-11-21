"""Packet rr5a: the charter folder through the records resolver (R2 to R5, R7), in a temp clone
with a temp holder. Every name is made up."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import charter, cli, doctor, records

KEY = "agentik.records"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t",
                           *args], check=True, capture_output=True, text=True).stdout


def clone(root, name="demo", declare=False):
    c = root / name
    c.mkdir(parents=True)
    git(c, "init", "-q")
    (c / "README.md").write_text("demo\n")
    if declare:
        (c / ".hygiene-allow").write_text("records: out\n")
    git(c, "add", "-A")
    git(c, "commit", "-q", "-m", "init")
    return c


def holder(root, name="demo"):
    h = root / "hold"
    (h / "repos" / name).mkdir(parents=True)
    git(h, "init", "-q")
    (h / "README.md").write_text("hold\n")
    git(h, "add", "README.md")
    git(h, "commit", "-q", "-m", "init")
    return h / "repos" / name


STATES = ["own", "out", "unset", "relative", "missing", "inside", "name"]


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    records.reset()
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("RELAY_ROW", raising=False)
    yield
    records.reset()


def layout(tmp_path, state):
    """(clone, the records folder or None) for `state`; the broken ones by their reason."""
    real = os.path.realpath(tmp_path)
    c = clone(Path(real), declare=state == "unset")
    rec = None
    if state == "out":
        rec = holder(Path(real))
        git(c, "config", KEY, str(rec))
    elif state == "relative":
        git(c, "config", KEY, "repos/demo")
    elif state == "missing":
        git(c, "config", KEY, str(Path(real) / "nowhere" / "demo"))
    elif state == "inside":
        (c / "sub" / "demo").mkdir(parents=True)
        git(c, "config", KEY, str(c / "sub" / "demo"))
    elif state == "name":
        other = holder(Path(real), "other")
        git(c, "config", KEY, str(other))
    return c, rec


def run(capsys, *argv):
    try:
        code = cli.main(list(argv))
    except SystemExit as e:
        code = e.code
    out, err = capsys.readouterr()
    return code, out, err


def tree(c):
    return sorted(str(p.relative_to(c)) for p in c.rglob("*") if ".git" not in p.parts)


@pytest.mark.parametrize("state", STATES)
def test_open_check_close_show_in_each_state(tmp_path, monkeypatch, capsys, state):
    c, rec = layout(tmp_path, state)
    monkeypatch.chdir(c)
    before = tree(c)
    code, out, err = run(capsys, "charter", "open", "a demo goal")
    if state == "own":
        assert code == 0 and not os.path.isabs(out.strip())
        assert out.strip().startswith("history/sittings/") and (c / out.strip()).is_file()
    elif state == "out":
        f = Path(out.strip())
        assert code == 0 and f.is_absolute() and f.parent == rec / "history" / "sittings"
        assert f.is_file() and tree(c) == before          # nothing written in the clone
    else:
        assert code == 2 and out == "" and tree(c) == before
        assert err.count("\n") == 1 and "git config agentik.records <folder>" in err
        if state == "unset":
            assert "not set" in err
        else:
            assert f"reason {state}" in err and "value " in err
    made = out.strip() if code == 0 else None
    # check: an explicit file, as at the pin, in every state
    probe = tmp_path / "probe.md"
    probe.write_text(Path(c / made if state == "own" else made).read_text() if made else
                     "# Sitting 2026-11-20-1: x\n")
    code_c, _, _ = run(capsys, "charter", "check", str(probe))
    assert code_c in (0, 1, 2)
    # show
    code_s, out_s, _ = run(capsys, "charter", "show", "--json")
    doc = json.loads(out_s)
    assert code_s == 0
    if state in ("own", "out"):
        assert [r["file"] for r in doc["repos"]] == [os.path.realpath(c / made if state == "own"
                                                                      else made)]
    else:
        want = "unset" if state == "unset" else "broken"
        assert doc["repos"] == [] and doc["skipped"][0]["why"] == f"records {want}"
        assert doc["skipped"][0]["records"]["state"] == want
    # close
    code_x, out_x, err_x = run(capsys, "charter", "close")
    if state in ("own", "out"):
        assert code_x == 0 and out_x.splitlines()[0] == made
        assert Path(c / made if state == "own" else made).read_text().count("exit taken") == 1
    else:
        assert code_x == 2 and "git config agentik.records <folder>" in err_x
    if state != "own":
        assert tree(c) == before


def test_show_two_repos_each_by_its_own_state(tmp_path, monkeypatch, capsys):
    a, rec = layout(tmp_path / "a", "out")
    b, _ = layout(tmp_path / "b", "relative")
    (rec / "history" / "sittings").mkdir(parents=True)
    (rec / "history" / "sittings" / "2026-11-20-1.md").write_text("# Sitting 2026-11-20-1: x\n")
    code, out, _ = run(capsys, "charter", "show", "--json", str(a), str(b))
    doc = json.loads(out)
    assert code == 0 and [r["file"] for r in doc["repos"]] == [
        str(rec / "history" / "sittings" / "2026-11-20-1.md")]
    assert doc["skipped"] == [{"repo": str(b), "why": "records broken", "records": {
        "state": "broken", "why": "relative", "line": records.line(records.answer(str(b)))}}]
    code, text, _ = run(capsys, "charter", "show", str(a), str(b))
    assert "skipped (records broken): demo" in text


def test_out_from_a_worktree_and_a_subfolder_is_the_main_checkouts_folder(tmp_path, monkeypatch,
                                                                          capsys):
    c, rec = layout(tmp_path, "out")
    wt = Path(os.path.realpath(tmp_path)) / "wt"
    git(c, "worktree", "add", "-q", str(wt), "-b", "w")
    (c / "sub").mkdir()
    folders = []
    for where in (c, c / "sub", wt):
        records.reset()
        monkeypatch.chdir(where)
        assert cli._records_dir(str(where), None, "history/sittings", "x") == str(
            rec / "history" / "sittings")
        code, out, _ = run(capsys, "charter", "open", "g")
        assert code == 0
        folders.append(Path(out.strip()).parent)
    assert folders == [rec / "history" / "sittings"] * 3
    assert not (wt / "history").exists() and not (c / "sub" / "history").exists()


def test_an_explicit_dir_wins_relative_joined_absolute_as_given(tmp_path, monkeypatch, capsys):
    c, rec = layout(tmp_path, "out")
    monkeypatch.chdir(c)
    code, out, _ = run(capsys, "charter", "open", "--dir", "notes/s", "g")
    assert code == 0 and Path(out.strip()).parent == rec / "notes" / "s"
    mine = Path(os.path.realpath(tmp_path)) / "elsewhere"
    code, out, _ = run(capsys, "charter", "open", "--dir", str(mine), "g")
    assert code == 0 and Path(out.strip()).parent == mine
    code, out, _ = run(capsys, "charter", "show", "--json", "--dir", str(mine))
    assert json.loads(out)["repos"][0]["file"].startswith(str(mine))
    assert not (c / "notes").exists()


def test_respawn_with_no_charter_names_the_key_in_unset_and_broken(tmp_path, monkeypatch, capsys):
    for state, word in (("unset", "not set"), ("missing", "reason missing")):
        records.reset()
        c, _ = layout(tmp_path / state, state)
        monkeypatch.chdir(c)
        code, _, err = run(capsys, "checkpoint", "--respawn")
        assert code == 2 and word in err and "git config agentik.records <folder>" in err


def test_setup_reads_the_records_folder_in_out(tmp_path):
    c, rec = layout(tmp_path, "out")
    assert cli.agentik_setup(c) is False
    (rec / "history" / "sittings").mkdir(parents=True)
    records.reset()
    assert cli.agentik_setup(c) is True
    u, _ = layout(tmp_path / "u", "unset")
    (u / "history" / "sittings").mkdir(parents=True)
    assert cli.agentik_setup(u) is False


# --- R2: the bound -----------------------------------------------------------------------

def test_a_git_that_sleeps_is_broken_timeout_within_six_seconds(tmp_path, monkeypatch):
    c, _ = layout(tmp_path, "own")
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "git").write_text("#!/bin/sh\nsleep 30\n")
    (stub / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub}{os.pathsep}{os.environ['PATH']}")
    pids = []
    real = subprocess.Popen

    def counted(*a, **k):
        p = real(*a, **k)
        pids.append(p.pid)
        return p
    monkeypatch.setattr(records.subprocess, "Popen", counted)
    t = time.monotonic()
    a = records.answer(str(c))
    assert time.monotonic() - t < 6
    assert records.state(a) == "broken" and a["why"] == "timeout"
    assert "reason timeout" in records.line(a)
    gone = False
    for _ in range(50):
        try:
            os.killpg(pids[0], 0)
        except ProcessLookupError:
            gone = True
            break
        except PermissionError:
            pass
        time.sleep(0.02)
    assert gone
    assert records.answer(str(c)) is a and len(pids) == 1          # once a folder a process


@pytest.mark.parametrize("body", ["raise RuntimeError('a made-up fault')",
                                  "import time; time.sleep(30)"])
def test_a_resolver_that_raises_or_sleeps_is_broken_and_never_raises(tmp_path, monkeypatch, body):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "agentik_records.py").write_text(
        f"class NoRepo(Exception):\n    pass\n\ndef resolve(start):\n    {body}\n")
    monkeypatch.setattr(records, "_LIB", str(lib))
    monkeypatch.setattr(records, "BOUND", 0.5)
    a = records.answer(str(tmp_path))
    assert records.state(a) == "broken"
    assert a["why"] == ("timeout" if "sleep" in body else "RuntimeError: a made-up fault")


def test_no_checkout_is_the_pin(tmp_path):
    assert records.answer(str(tmp_path)) is None and records.state(None) == "own"
    assert records.answer(None) is None and records.answer("") is None


# --- R7: doctor's row --------------------------------------------------------------------

@pytest.mark.parametrize("state", ["own", "out", "unset", "relative"])
def test_doctor_row_in_each_state(tmp_path, state):
    c, rec = layout(tmp_path, state)
    row = doctor._check_records(c)
    rep = doctor.Report()
    rep.checks.append(row)
    text = doctor.render(rep).splitlines()[0]
    got = json.loads(json.dumps(rep.as_dict()))
    js = [x for x in json.dumps(got) if x]
    assert row.name == "records" and row.ok and js
    if state == "own":
        assert text.startswith("ok   records") and text.endswith("in the repo") and not row.warn
    elif state == "out":
        assert text.startswith("ok   records") and text.endswith(str(rec)) and not row.warn
    else:
        assert text.startswith("warn records") and row.warn
        assert "git config agentik.records <folder>" in text
        if state == "relative":
            assert "value repos/demo; reason relative" in text
    assert row.detail in json.dumps(got)
    assert doctor._check_records(tmp_path / "nowhere-made-up") is None


# --- review 1's F3: a --dir inside the clone in `unset` and `broken` (GUIDE §12) ----------

@pytest.mark.parametrize("state", ["unset", "missing", "inside"])
def test_a_dir_inside_the_clone_is_refused_for_a_write(tmp_path, monkeypatch, capsys, state):
    c, _ = layout(tmp_path, state)
    monkeypatch.chdir(c)
    (c / "sub").mkdir(exist_ok=True)
    link = Path(os.path.realpath(tmp_path)) / "link"
    link.symlink_to(c / "sub")                         # outside by its spelling, inside by its real path
    before = tree(c)
    for d in ("notes", str(c / "notes"), str(link)):
        records.reset()
        code, out, err = run(capsys, "charter", "open", "--dir", d, "g")
        assert (code, out, err.count("\n")) == (2, "", 1) and KEY in err, (d, err)
        code, out, err = run(capsys, "charter", "close", "--dir", d)
        assert (code, out) == (2, "") and KEY in err, (d, err)
    assert tree(c) == before
    mine = Path(os.path.realpath(tmp_path)) / "elsewhere"      # outside the clone: it stands
    code, out, _ = run(capsys, "charter", "open", "--dir", str(mine), "g")
    assert code == 0 and Path(out.strip()).parent == mine
    code, out, _ = run(capsys, "charter", "close", "--dir", str(mine))
    assert code == 0 and out.splitlines()[0] == out.splitlines()[0].strip()
    assert tree(c) == before


def test_a_dir_inside_the_clone_is_refused_for_a_read_in_broken_alone(tmp_path, monkeypatch,
                                                                       capsys):
    for state in ("missing", "unset"):
        records.reset()
        c, _ = layout(tmp_path / state, state)
        (c / "notes").mkdir()
        f = c / "notes" / "2026-11-20-1.md"
        f.write_text("# Sitting 2026-11-20-1: x\n")
        monkeypatch.chdir(c)
        code, out, _ = run(capsys, "charter", "show", "--json", "--dir", "notes")
        doc = json.loads(out)
        code_c, _, err_c = run(capsys, "charter", "check", "--dir", "notes", str(f))
        if state == "missing":
            assert code == 0 and doc["repos"] == []
            assert doc["skipped"][0]["why"] == "records broken"
            assert code_c == 2 and KEY in err_c and "reason missing" in err_c
        else:                                          # `unset` reads as built
            assert [r["file"] for r in doc["repos"]] == [str(f)]
            assert code_c != 2 or KEY not in err_c
    mine = Path(os.path.realpath(tmp_path)) / "elsewhere"
    mine.mkdir()
    (mine / "2026-11-20-1.md").write_text("# Sitting 2026-11-20-1: x\n")
    records.reset()
    monkeypatch.chdir(tmp_path / "missing" / "demo")
    code, out, _ = run(capsys, "charter", "show", "--json", "--dir", str(mine))
    assert [r["file"] for r in json.loads(out)["repos"]] == [str(mine / "2026-11-20-1.md")]


# --- review 1's F4: where git did not answer, the line says so, and no "set it" -----------

def test_a_git_that_did_not_answer_says_so_and_not_set_it(tmp_path, monkeypatch, capsys):
    c, _ = layout(tmp_path, "own")
    a = records._failed(str(c), "timeout")
    got = records.line(a)
    assert "git did not answer" in got and "reason timeout" in got
    assert "set it" not in got and records.SET_LINE not in got
    broken = layout(tmp_path / "b", "missing")[0]
    assert records.SET_LINE in records.line(records.answer(str(broken)))    # a key set: the advice
    monkeypatch.setattr(records, "_read", lambda folder: records._failed(folder, "timeout"))
    records.reset()
    monkeypatch.chdir(c)
    code, out, err = run(capsys, "charter", "open", "g")
    assert code == 2 and "git did not answer" in err and "set it" not in err

