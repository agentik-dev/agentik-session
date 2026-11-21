"""Packet rr5c R2: a line's file where the sender's records live outside its clone, in temp
checkouts with a temp holder. Every name is made up and every repository is the test's own."""

import os
import subprocess
import time
from pathlib import Path

import pytest

from claude_session import cli, lines, records

from test_in3_line import call, ctx, plain, state  # noqa: F401

KEY = "agentik.records"


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


@pytest.fixture
def pair(tmp_path, monkeypatch):
    """alpha, the receiver this session sits in; beta, the sender, its records in a holder."""
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = Path(os.path.realpath(tmp_path))
    alpha, beta, hold = root / "code" / "alpha", root / "code" / "beta", root / "hold"
    for r in (alpha, beta, hold):
        r.mkdir(parents=True)
        git(r, "init", "-q", "-b", "main")
    rec = hold / "repos" / "beta"
    (rec / "history" / "sessions").mkdir(parents=True)
    git(beta, "config", KEY, str(rec))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(alpha))
    records.reset()
    yield alpha, beta, rec
    records.reset()


def intake(at: Path, text="fix the gate's wall\nthe rest of it") -> Path:
    f = at / "history" / "sessions" / "INTAKE-2026-11-21-beta-to-alpha.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    return f


def test_rr5c_a1_out_a_record_file_is_sent_taken_shown_and_closed_back(pair, monkeypatch,
                                                                         capsys):
    alpha, beta, rec = pair
    f = intake(rec)
    lid = lines.send(state(), str(alpha), str(f), str(beta))
    assert lid in ctx(call("UserPromptSubmit", alpha))
    shown = lines.show(state(), lid)
    assert shown["pointer"]["file"] == str(f) and shown["state"] == "taken"
    capsys.readouterr()
    assert cli.main(["line", "close", lid, "--as", "done"]) == 0
    back = capsys.readouterr().out.strip()
    assert lines.ID.match(back)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(beta))
    assert f"line {lid} closed as done" in ctx(call("UserPromptSubmit", beta))


def test_rr5c_a1_out_a_file_under_neither_is_refused_naming_both(pair, tmp_path):
    alpha, beta, rec = pair
    f = Path(os.path.realpath(tmp_path)) / "elsewhere.md"
    f.write_text("x\n")
    with pytest.raises(lines.Refused) as e:
        lines.send(state(), str(alpha), str(f), str(beta))
    msg = str(e.value)
    assert f"inside this checkout, {beta}" in msg and f"records folder, {rec}" in msg


def test_rr5c_a1_own_the_pins_refusal_word_for_word(pair, tmp_path):
    alpha, beta, rec = pair
    f = Path(os.path.realpath(tmp_path)) / "elsewhere.md"
    f.write_text("x\n")
    with pytest.raises(lines.Refused) as e:
        lines.send(state(), str(beta), str(f), str(alpha))
    assert str(e.value) == f"line send: {f} is no file inside this checkout, {alpha}"


def test_rr5c_a1_a_resolver_past_its_bound_gives_the_pins_verdict_in_time(pair, tmp_path,
                                                                           monkeypatch):
    alpha, beta, rec = pair
    lid = lines.send(state(), str(alpha), str(intake(rec)), str(beta))
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "agentik_records.py").write_text(
        "class NoRepo(Exception):\n    pass\n\ndef resolve(start):\n"
        "    import time; time.sleep(30)\n")
    records.reset()
    monkeypatch.setattr(records, "_LIB", str(lib))
    monkeypatch.setattr(records, "BOUND", 0.5)
    t0 = time.monotonic()
    assert lid not in ctx(call("UserPromptSubmit", alpha))       # the pin's verdict: aside
    assert time.monotonic() - t0 < 4
    assert lines.show(state(), lid)["state"] != "taken"


def test_rr5c_a1_own_no_resolver_start_for_a_pointer_the_pins_test_passes(pair, monkeypatch):
    alpha, beta, rec = pair
    lid = lines.send(state(), str(beta), str(intake(alpha)), str(alpha))
    records.reset()
    started = []
    real = subprocess.Popen

    def counted(*a, **k):
        started.append(a)
        return real(*a, **k)

    monkeypatch.setattr(records.subprocess, "Popen", counted)
    got = lines.take(state(), {"cwd": str(beta)}, {"CLAUDE_PROJECT_DIR": str(beta)})
    monkeypatch.setattr(records.subprocess, "Popen", real)
    assert got is not None and lid in got
    assert started == []
