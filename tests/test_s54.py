"""Packet S54 (design/packets/s54-audit.md): the audit's a1, a2 and a3.

a1: a bare `charter close` writes this sitting's own charter (its session dir's record), else
today's newest of its suffix, else refuses. a2: a resumed session reads as its last ledger
row. a3: the band is built outside the ledger lock, under its own non-waiting lock."""
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, cli, hooks, resolver

SID_A = "aaaaaaaa-0000-0000-0000-000000000001"
SID_B = "bbbbbbbb-0000-0000-0000-000000000002"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE",
              "CLAUDE_SESSION_HELPER", "RELAY_ROW"):
        monkeypatch.delenv(k, raising=False)


def _two_sittings(tmp_path, monkeypatch, a_dir: bool):
    """§1's a1: A opens `-1.md`, then B (RELAY_ROW=row7) opens `-2-row7.md`, in one repo.
    With `a_dir`, A's session dir exists first (request.json, cwd the repo), as SessionStart
    leaves it, so A's open records its file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    if a_dir:
        sdir = resolver.session_dir(resolver.state_dir(os.environ), SID_A)
        sdir.mkdir(parents=True)
        resolver.save_request(sdir, repo, None, None)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID_A)
    rc, out_a, _ = run("charter", "open", "sitting A goal")
    assert rc == 0
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID_B)
    monkeypatch.setenv("RELAY_ROW", "row7")
    rc, out_b, _ = run("charter", "open", "relay row B goal")
    assert rc == 0
    monkeypatch.delenv("RELAY_ROW")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID_A)
    a, b = repo / out_a.strip(), repo / out_b.strip()
    t = charter.today()
    assert (a.name, b.name) == (f"{t}-1.md", f"{t}-2-row7.md")
    return repo, a, b


def test_s54_a1_recorded_charter(tmp_path, monkeypatch):
    repo, a, b = _two_sittings(tmp_path, monkeypatch, a_dir=True)
    rec = resolver.session_dir(resolver.state_dir(os.environ), SID_A) / hooks.CHARTER_REC
    assert json.loads(rec.read_text()) == {"path": str(a)}
    before_b = b.read_bytes()
    rc, out, err = run("charter", "close", "--exit", "A is done")
    assert rc == 0, err
    assert out.splitlines()[0] == f"history/sittings/{a.name}"
    assert "exit taken: A is done" in a.read_text()
    assert b.read_bytes() == before_b
    # A record outside `dir` is unused: today's newest is B's, another suffix's, so refused.
    other = tmp_path / "elsewhere" / a.name
    other.parent.mkdir()
    other.write_bytes(a.read_bytes())
    rec.write_text(json.dumps({"path": str(other)}) + "\n")
    snap = {p: p.read_bytes() for p in (a, b, other)}
    rc, out, err = run("charter", "close", "--exit", "again")
    assert rc == 2 and out == "" and b.name in err
    assert {p: p.read_bytes() for p in (a, b, other)} == snap
    # The same at the function: an outside record falls through, an inside one wins.
    d = repo / "history" / "sittings"
    with pytest.raises(charter.CharterError):
        charter.bare_target(d, None, str(other))
    assert charter.bare_target(d, None, str(a)) == d / a.name
    assert charter.bare_target("history/sittings", None, str(a)) == Path(
        "history/sittings") / a.name
    with pytest.raises(charter.CharterError):                 # a relative record is unused
        charter.bare_target(d, None, f"history/sittings/{a.name}")


def test_s54_a1_another_suffix_refused(tmp_path, monkeypatch):
    repo, a, b = _two_sittings(tmp_path, monkeypatch, a_dir=False)
    assert not resolver.session_dir(resolver.state_dir(os.environ), SID_A).exists()
    snap = {p: p.read_bytes() for p in (a, b)}
    rc, out, err = run("charter", "close", "--exit", "A is done")
    assert rc == 2 and out == ""
    assert b.name in err and a.name in err
    assert err.rstrip().endswith("name the file: charter close <file>")
    assert {p: p.read_bytes() for p in (a, b)} == snap
    assert sorted(p.name for p in a.parent.iterdir()) == sorted((a.name, b.name))
    # None of this suffix today: the refusal says so.
    monkeypatch.setenv("RELAY_ROW", "row9")
    rc, _, err = run("charter", "close", "--exit", "x")
    assert rc == 2 and "none today" in err and b.name in err
    # None at all today: today's words, exit 2.
    empty = tmp_path / "empty"
    empty.mkdir()
    rc, _, err = run("charter", "close", "--dir", str(empty), "--exit", "x")
    assert (rc, err) == (2, f"error: no charter for today under {empty}\n")
