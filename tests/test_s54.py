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


# --- a3: the band built outside the ledger's lock, under its own --------------------------

def _adir():
    from claude_session import admission, config
    return config.state_dir(os.environ) / admission.DIR


def _five(pct):
    return [{"kind": "five_hour", "percentUsed": pct, "resetsAt": "2026-10-12T14:00:00+00:00"}]


T_A = "test-sess-0000-1111-2222"
T_B = "test-sess-0000-1111-3333"


def test_s54_a3_record_during_build(monkeypatch, capsys):
    from datetime import datetime, timezone
    from claude_session import admission, config
    config.ensure_dirs()
    monkeypatch.setattr(admission, "LOCK_WAIT_S", 0.2)
    now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
    env = dict(os.environ)
    real, calls = admission.bands, []

    def bands(rows, at, settings, tz=None):
        calls.append([r.get("session") for r in rows])
        if len(calls) == 1:            # a second session records while the first build runs
            admission.record(T_B, json.dumps({"kind": "reading", "rateLimits": _five(55)}),
                             env, now)
        return real(rows, at, settings, tz)

    monkeypatch.setattr(admission, "bands", bands)
    admission.record(T_A, json.dumps({"kind": "start", "interactive": True}), env, now)
    lines = [json.loads(x) for x in (_adir() / admission.LEDGER).read_text().splitlines()]
    assert [(x["session"], x["kind"]) for x in lines] == [(T_A, "start"), (T_B, "reading")]
    assert len(calls) == 2 and T_B not in calls[0] and T_B in calls[1]
    band = json.loads((_adir() / admission.BAND).read_text())
    assert band["P"] == 55
    assert "not written" not in capsys.readouterr().err


def test_s54_a3_band_lock_not_waited_for(monkeypatch, capsys):
    import fcntl
    import stat as st
    import time
    from datetime import datetime, timezone
    from claude_session import admission, config
    config.ensure_dirs()
    now = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
    env = dict(os.environ)
    admission.record(T_A, json.dumps({"kind": "start", "interactive": True}), env, now)
    lock = _adir() / "band.lock"
    band = (_adir() / admission.BAND).read_bytes()
    capsys.readouterr()
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        t0 = time.monotonic()
        admission.record(T_B, json.dumps({"kind": "reading", "rateLimits": _five(55)}), env, now)
        took = time.monotonic() - t0
    finally:
        os.close(fd)
    lines = (_adir() / admission.LEDGER).read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["session"] == T_B
    assert (_adir() / admission.BAND).read_bytes() == band
    assert capsys.readouterr().err == ""
    assert took < 1.0                                       # never waited for
    assert admission.BAND_LOCK == "band.lock" and st.S_IMODE(lock.stat().st_mode) == 0o600


class _Counted(dict):
    """A ledger row that counts the `get`s made on it."""
    gets = 0

    def get(self, *a):
        _Counted.gets += 1
        return super().get(*a)


def _old_runs(rows):
    """`runs` at cba0b70, kept to compare: each spawn's end a scan of every done."""
    from claude_session.admission import _minutes, _real, _str, _when, family, helper_type
    dones = sorted(((t, r) for r in rows if r.get("kind") == "done"
                    and (t := _when(r.get("ts"))) is not None), key=lambda x: x[0])

    def end(t0, aid, tid):
        for t, d in dones:
            if t >= t0 and ((aid and d.get("agentId") == aid)
                            or (tid and d.get("tool_use_id") == tid)):
                return t, d
        return None, None

    def run(t0, aid, tid, fam, typ):
        t1, d = end(t0, aid, tid)
        mins = None
        if d is not None and d.get("swept") is not True:
            ms = _real(d.get("durationMs"))
            mins = ms / 60000.0 if ms is not None and ms >= 0 else _minutes(t1 - t0)
        return {"start": t0, "end": t1, "minutes": mins, "family": fam, "type": typ,
                "agentId": aid, "tool_use_id": tid}

    out, by_agent = [], {}
    events = sorted(((t, r) for r in rows if r.get("kind") in ("spawn", "resume")
                     and (t := _when(r.get("ts"))) is not None), key=lambda x: x[0])
    for t0, r in events:
        if r["kind"] == "spawn":
            x = run(t0, _str(r.get("agentId")), _str(r.get("tool_use_id")),
                    family(r.get("model"), r.get("parentModel")),
                    helper_type(r.get("subagentType"), r.get("fork")))
        else:
            aid = _str(r.get("to"))
            last = by_agent.get(aid)
            if aid is None or (last is not None and (last["end"] is None or last["end"] > t0)):
                continue
            x = run(t0, aid, None, last["family"] if last else "other",
                    last["type"] if last else "other")
        out.append(x)
        if x["agentId"]:
            by_agent[x["agentId"]] = x
    return out


def _ts(base, s):
    from datetime import timedelta
    return (base + timedelta(seconds=s)).isoformat()


def test_s54_a3_runs_linear():
    import random
    from datetime import datetime, timezone
    from claude_session import admission
    base = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
    rows = [_Counted(ts=_ts(base, i), kind="spawn", agentId=f"a{i}", tool_use_id=f"t{i}",
                     subagentType="general-purpose", model=None,
                     parentModel="claude-opus-5-5", fork=False) for i in range(1000)]
    rows += [_Counted(ts=_ts(base, 2000 + k), kind="done", agentId=f"a{i}", tool_use_id=None,
                      durationMs=60000, swept=False)
             for k, i in enumerate(reversed(range(1000)))]
    _Counted.gets = 0
    got = admission.runs(rows)
    assert _Counted.gets <= 20 * len(rows), _Counted.gets
    assert len(got) == 1000 and all(r["end"] is not None for r in got)
    assert got == _old_runs(rows)
    # Seeded random ledgers: ids shared and reused, ties in time, torn times, both keys.
    for seed in range(60):
        rnd = random.Random(seed)
        aids = [f"a{k}" for k in range(rnd.randint(1, 6))] + [None, "", 7]
        tids = [f"t{k}" for k in range(rnd.randint(1, 6))] + [None, ""]
        rows = []
        for _ in range(rnd.randint(0, 60)):
            kind = rnd.choice(("spawn", "spawn", "resume", "done", "done", "done", "reading"))
            ts = rnd.choice((_ts(base, rnd.randint(0, 40) * 30), "not a time", None))
            r = {"ts": ts, "kind": kind}
            if kind == "spawn":
                r.update(agentId=rnd.choice(aids), tool_use_id=rnd.choice(tids),
                         subagentType=rnd.choice(("Explore", "general-purpose", None)),
                         model=rnd.choice((None, "claude-sonnet-5")),
                         parentModel="claude-opus-5-5", fork=rnd.random() < .2)
            elif kind == "resume":
                r.update(to=rnd.choice(aids))
            elif kind == "done":
                r.update(agentId=rnd.choice(aids), tool_use_id=rnd.choice(tids),
                         durationMs=rnd.choice((None, -1, 90000, 1.5e6)),
                         swept=rnd.random() < .2)
            rows.append(r)
        assert admission.runs(rows) == _old_runs(rows), seed
