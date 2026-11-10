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


# --- a2: a resumed session reads as its last ledger row -------------------------------

SID_C = "cccccccc-0000-0000-0000-000000000003"
FOLD_LINE = "folded: 1 earlier rows; a resumed session reads as its last"


def _fifty_turns(tmp_path):
    """§1's a2 transcript: 50 turns of 100,000 tokens each, 5,000,000 in all."""
    p = tmp_path / "p" / f"{SID_C}.jsonl"
    p.parent.mkdir()
    with p.open("w") as f:
        for i in range(50):
            f.write(json.dumps({"type": "assistant", "timestamp": "2026-11-09T10:00:00Z",
                                "requestId": f"r{i}", "message": {
                                    "id": f"m{i}", "model": "claude-fable-5-2",
                                    "usage": {"input_tokens": 10,
                                              "cache_creation_input_tokens": 0,
                                              "cache_read_input_tokens": 99990,
                                              "output_tokens": 0}}}) + "\n")
    return p


def test_s54_a2_one_row(tmp_path, monkeypatch):
    from claude_session import config, ledger
    config.ensure_dirs()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID_C)
    env = dict(os.environ)
    tp = _fifty_turns(tmp_path)
    payload = {"session_id": SID_C, "cwd": str(tmp_path), "transcript_path": str(tp),
               "model": "claude-fable-5-2"}
    for _ in range(2):                          # the session, then `claude --resume` of it
        hooks.session_start(dict(payload), env)
        hooks.session_end(dict(payload, reason="prompt_input_exit"), env)
    state = resolver.state_dir(env)
    assert len(ledger.path(state).read_text().splitlines()) == 2
    rc, out, err = run("report", "--json")
    rows = json.loads(out)
    assert rc == 0 and len(rows) == 1
    assert (rows[0]["session"], rows[0]["tokens"], rows[0]["turns"]) == (SID_C, 5000000, 50)
    assert err == FOLD_LINE + "\n"
    rc, out, err = run("report")
    assert rc == 0 and FOLD_LINE in out.splitlines() and FOLD_LINE not in err


def _row(session, ended="2026-11-09T10:00:00+00:00", **kw):
    d = {"session": session, "ended": ended, "tokens": 1}
    if session is None:
        del d["session"]
    d.update(kw)
    return d


def test_s54_a2_fold(tmp_path):
    from claude_session import ledger
    state = tmp_path / "state"
    state.mkdir()
    rows = [_row("x", tokens=1), _row(None, tokens=2), _row("y", tokens=3),
            _row(7, tokens=4), _row("x", tokens=5), _row(7, tokens=6),
            _row("z", ended="2026-11-09T09:00:00+00:00"),
            _row("z", ended="2026-11-01T09:00:00+00:00")]
    body = "".join(json.dumps(r) + "\n" for r in rows)
    chain = json.dumps({"kind": "restart", "chain": "c", "seq": 1}) + "\n"
    ledger.path(state).write_text(chain + body + "not json\n" + chain)
    raw = ledger.path(state).read_bytes()
    # lines: every session line as `read` parses it, unfiltered and unfolded.
    assert ledger.lines(state) == rows
    assert ledger.lines(tmp_path / "absent") == []
    # fold: each string session's last row, in that row's place; others kept.
    kept, folded = ledger.fold(rows)
    assert [r["tokens"] for r in kept] == [2, 3, 4, 5, 6, 1]
    assert [r.get("session") for r in kept] == [None, "y", 7, "x", 7, "z"]
    assert kept[-1]["ended"].startswith("2026-11-01")
    assert folded == 2                                  # x's first, z's first
    # then since, as today: z's last ended before it, so z goes, and its earlier row with it.
    kept, folded = ledger.fold(rows, "2026-11-05")
    assert [r.get("session") for r in kept] == [None, "y", 7, "x", 7]
    assert folded == 1                                  # x's first only: z is not kept
    assert ledger.fold([], "2026-11-05") == ([], 0)
    # read is fold(lines(state), since)'s kept rows; the file stands, append-only.
    for since in (None, "2026-11-05", "2026-12-01"):
        assert ledger.read(state, since) == ledger.fold(ledger.lines(state), since)[0]
    assert ledger.path(state).read_bytes() == raw


def test_s54_a2_report_hooks_counts_a_session_once(monkeypatch):
    from claude_session import config, ledger
    config.ensure_dirs()
    state = resolver.state_dir(os.environ)
    for t in (1, 2):
        ledger._append_line(state, json.dumps(_row(SID_C, tokens=t, claude_md_bytes=900 + t)))
    rc, out, _ = run("report", "--hooks", "--json")
    got = json.loads(out)
    assert rc == 0 and got["ledger_rows"] == 1 and got["claude_md_bytes"]["newest"] == 902
