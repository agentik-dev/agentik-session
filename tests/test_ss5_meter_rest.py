"""Row ss5-meter-rest: the doctor's `meter` check fails only when a tool call went unmetered.

The meter runs when a tool call ends; a transcript also grows with no tool call (an answer, a
prompt after a pause, turns of text alone). The check reads the transcript's tail from the
metered offset on and fails only on a tool result stamped more than FRESH_S after the
meter's `ts` (R1); a pass over a tail says how far the transcript ran and that the meter runs
at the next call, with the newest-session note when the id is unset (R2); a tail it cannot
read is today's verdict for the caller's own session and a `warn` for the newest (R3); the
other cases answer as at the pin, byte for byte (R4). Each case in a temp HOME and state
folder, a made-up session and transcript; no `claude`, no live state."""
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks, meter, resolver

ROOT = Path(__file__).resolve().parents[1]
SID = "ss5-rest-sess-0000-1111"
NOTE = " ($CLAUDE_CODE_SESSION_ID unset: the newest session)"


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def box(tmp_path):
    """A green fake machine (test_doctor's shape), one session metered over a copy of a
    shipped fixture transcript."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    install = tmp_path / "install"
    (install / "hooks").mkdir(parents=True)
    (install / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {
        e: [] for e in doctor.HOOK_EVENTS}}))
    plugins = [{"id": "session@agentik", "version": "2.0.0", "enabled": True,
                "installPath": str(install)},
               {"id": "decisions@agentik", "version": "0.4.0", "enabled": True},
               {"id": "respeak@agentik", "version": "0.6.0", "enabled": True},
               {"id": "relay@agentik", "version": "0.1.0", "enabled": True}]
    (tmp_path / "plugins.json").write_text(json.dumps(plugins))
    _exe(bin_ / "claude", f'if [ "$1" = plugin ]; then /bin/cat {tmp_path}/plugins.json; exit 0; fi\n'
         'echo "--model --effort --tools --permission-mode '
         '--max-budget-usd --output-format --session-id"\n')
    for b in ("relay", "tmux", "git"):
        _exe(bin_ / b, "exit 0\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    tp = tmp_path / "transcript.jsonl"
    shutil.copy(ROOT / "tests/fixtures/meter/under-80.jsonl", tp)
    own = {"PATH": str(bin_), "HOME": str(tmp_path / "home"),
           "XDG_STATE_HOME": str(tmp_path / "state"), "CLAUDE_CODE_SESSION_ID": SID}
    hooks.session_start({"session_id": SID, "cwd": str(repo), "transcript_path": str(tp)}, own)
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp)}, own)

    class B:
        pass
    b = B()
    b.own, b.repo, b.tp, b.tmp = own, repo, tp, tmp_path
    b.newest = {k: v for k, v in own.items() if k != "CLAUDE_CODE_SESSION_ID"}
    b.sdir = resolver.session_dir(resolver.state_dir(own), SID)
    b.path = b.sdir / meter.METER
    b.m = meter.load(b.sdir)
    b.ts = datetime.fromisoformat(b.m["ts"]).timestamp()
    b.summary = (f"{b.m['pct_context']}% context, {b.m['pct_turns']}% turns, "
                 f"zone {b.m['zone']}")
    return b


def iso(t: float) -> str:
    """A transcript line's own time: UTC, milliseconds, a trailing Z."""
    return datetime.fromtimestamp(t, timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def result(t, **extra):
    item = {"type": "tool_result", "tool_use_id": "toolu_made_up_1", "content": "<placeholder>"}
    item.update(extra)
    return {"type": "user", "isSidechain": False, "timestamp": iso(t),
            "message": {"role": "user", "content": [item]}, "toolUseResult": "<placeholder>"}


def text(t, n=1):
    return {"type": "assistant", "isSidechain": False, "timestamp": iso(t),
            "requestId": f"req_rest_{n}",
            "message": {"role": "assistant", "id": f"msg_rest_{n}", "model": "claude-opus-5-5",
                        "content": [{"type": "text", "text": "<placeholder>"}],
                        "usage": {"input_tokens": 10, "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": 40000, "output_tokens": 50}}}


def prompt(t):
    return {"type": "user", "isSidechain": False, "timestamp": iso(t),
            "message": {"role": "user", "content": "<placeholder>"}}


def tail(b, rows, raw=b""):
    with open(b.tp, "ab") as f:
        for r in rows:
            f.write(json.dumps(r).encode() + b"\n")
        f.write(raw)


def rest(b, seconds):
    t = b.ts + seconds
    os.utime(b.tp, (t, t))


def check(env):
    return doctor._check_meter(env)


def pin_stale(b):
    """The pin's FAIL line over the box's meter, byte for byte."""
    age = meter.mtime_age(b.m)
    return (f"{b.path} stale: metered {b.m['transcript']['size']} bytes of "
            f"{os.stat(b.tp).st_size}, {age:.0f}s from the transcript's mtime")


def others(env, repo):
    return [(c.name, c.status, c.detail) for c in doctor.run(env, repo).checks if c.name != "meter"]


def cli_doctor(env, repo, monkeypatch, capsys, *args):
    for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(repo)
    rc = cli.main(["doctor", *args])
    return rc, capsys.readouterr().out


# ---- 1: the finding's shape, the newest session --------------------------------------------

def test_1_the_finding_passes_with_the_newest_note(box, monkeypatch, capsys):
    before = others(box.newest, box.repo)
    tail(box, [result(box.ts + 3), text(box.ts + 20)])
    rest(box, 2443)
    c = check(box.newest)
    grown = os.stat(box.tp).st_size - box.m["transcript"]["size"]
    assert c.ok and not c.warn and not c.note, c.detail
    assert c.detail == (f"{box.path}: {box.summary}; the transcript has run {grown} bytes and "
                        f"2443s past the meter with no tool call ended since, so the meter runs "
                        f"at the next one{NOTE}")
    assert others(box.newest, box.repo) == before
    rc, out = cli_doctor(box.newest, box.repo, monkeypatch, capsys)
    assert rc == 0 and "ok   meter " in out and out.rstrip().endswith("doctor: green"), out
    assert "FAIL" not in out


# ---- 2: the same tail, the caller's own session ---------------------------------------------

def test_2_the_same_tail_for_the_own_session_has_no_note(box):
    tail(box, [result(box.ts + 3), text(box.ts + 20)])
    rest(box, 2443)
    c = check(box.own)
    assert c.ok and not c.warn, c.detail
    assert "past the meter with no tool call ended since" in c.detail
    assert "newest session" not in c.detail


# ---- 3: prompts and text alone, three hours on ----------------------------------------------

@pytest.mark.parametrize("who", ("own", "newest"))
def test_3_a_tail_of_prompts_and_text_alone_passes(box, who):
    tail(box, [prompt(box.ts + 600), text(box.ts + 620, 1),
               prompt(box.ts + 10740), text(box.ts + 10800, 2)])
    rest(box, 10800)
    c = check(getattr(box, who))
    assert c.ok and not c.warn and "10800s past the meter" in c.detail, c.detail
    assert c.detail.endswith(NOTE) is (who == "newest")


# ---- 4: a tool call that ended 600 s after the meter fails, naming its time -----------------

@pytest.mark.parametrize("who", ("own", "newest"))
def test_4_an_unmetered_tool_call_fails_naming_its_time(box, who):
    tail(box, [result(box.ts + 3), text(box.ts + 20, 1), result(box.ts + 600),
               text(box.ts + 640, 2)])
    rest(box, 2443)
    c = check(getattr(box, who))
    assert not c.ok
    assert c.detail == (f"{box.path} stale: metered {box.m['transcript']['size']} bytes of "
                        f"{os.stat(box.tp).st_size}, 600s from the tool call that ended at "
                        f"{iso(box.ts + 600)}")
    rep = doctor.run(getattr(box, who), box.repo)
    assert [x.name for x in rep.checks if not x.ok] == ["meter"]
    assert "\nFAIL meter " in doctor.render(rep)


def test_4_the_first_unmetered_call_is_named(box):
    tail(box, [result(box.ts + 600), result(box.ts + 900)])
    rest(box, 2443)
    assert f"600s from the tool call that ended at {iso(box.ts + 600)}" in check(box.own).detail


def test_4_a_failed_call_or_a_helper_s_is_no_missed_call(box):
    # PostToolUseFailure and a helper's PostToolUse never write the meter (hooks.py)
    tail(box, [result(box.ts + 600, is_error=True)])
    side = result(box.ts + 900)
    side["isSidechain"] = True
    tail(box, [side, text(box.ts + 950)])
    rest(box, 2443)
    c = check(box.own)
    assert c.ok and not c.warn, c.detail


# ---- 5: a tail that cannot be read ----------------------------------------------------------

CUT = b'{"type": "assistant", "timestamp": "2026-'
TAILS = {"cut": ([], CUT), "not-json": ([], b"<placeholder> not a line of JSON\n"),
         "no-type": ([], b"{}\n"), "no-time": ("no-time", b"")}


def _unread(box, kind):
    rows, raw = TAILS[kind]
    if rows == "no-time":
        r = result(box.ts + 600)
        del r["timestamp"]
        rows = [r]
    tail(box, [text(box.ts + 20)] + rows, raw)
    rest(box, 2443)


@pytest.mark.parametrize("kind", sorted(TAILS))
def test_5_an_unread_tail_is_today_s_verdict_for_the_own_session(box, kind):
    _unread(box, kind)
    c = check(box.own)
    assert not c.ok and c.detail == pin_stale(box)


@pytest.mark.parametrize("kind", sorted(TAILS))
def test_5_an_unread_tail_is_a_warn_for_the_newest(box, kind, monkeypatch, capsys):
    _unread(box, kind)
    c = check(box.newest)
    grown = os.stat(box.tp).st_size - box.m["transcript"]["size"]
    assert c.ok and c.warn, c.detail
    assert c.detail.startswith(f"{box.path}: {box.summary}; the transcript has run {grown} bytes "
                               f"and 2443s past the meter and its tail could not be read (")
    assert c.detail.endswith(f"), so nothing shows a missed tool call{NOTE}")
    rc, out = cli_doctor(box.newest, box.repo, monkeypatch, capsys)
    assert rc == 0 and "warn meter " in out, out


def test_5_a_tail_past_the_bound_is_read_from_its_end_back(box, monkeypatch):
    monkeypatch.setattr(doctor, "TAIL_MAX", 4096, raising=False)
    tail(box, [prompt(box.ts + 100 + i) for i in range(60)])        # past 4096 bytes
    assert os.stat(box.tp).st_size - box.m["transcript"]["size"] > 4096
    tail(box, [result(box.ts + 3000)])
    rest(box, 3100)
    c = check(box.newest)              # the window's first line is cut: skipped, no warn
    assert not c.ok and f"from the tool call that ended at {iso(box.ts + 3000)}" in c.detail
    assert doctor.TAIL_MAX == 4096


def test_5_the_shipped_bound(box):
    assert doctor.TAIL_MAX == 4 * 1024 * 1024


# ---- 6: R4, byte-equal to the pin -----------------------------------------------------------

@pytest.mark.parametrize("who", ("own", "newest"))
def test_6_sizes_equal(box, who):
    rest(box, 10800)
    c = check(getattr(box, who))
    assert (c.ok, c.status, c.detail) == (True, "ok",
                                          f"{box.path}: {box.summary}; transcript size matches")


@pytest.mark.parametrize("who", ("own", "newest"))
def test_6_the_zero_meter(box, who):
    sid = "ss5-zero-sess-2222-3333"
    env = {**box.own, "CLAUDE_CODE_SESSION_ID": sid}
    tp = box.tmp / "zero.jsonl"
    hooks.session_start({"session_id": sid, "cwd": str(box.repo), "transcript_path": str(tp)}, env)
    path = resolver.session_dir(resolver.state_dir(env), sid) / meter.METER
    m = meter.load(path.parent)
    summary = f"{m['pct_context']}% context, {m['pct_turns']}% turns, zone {m['zone']}"
    env = env if who == "own" else box.newest          # the newest is now the zero session
    assert check(env).detail == f"{path}: {summary}; no transcript yet"
    tp.write_text(json.dumps(prompt(box.ts)) + "\n")
    t = box.ts + 10800
    os.utime(tp, (t, t))
    c = check(env)
    assert (c.ok, c.status, c.detail) == (True, "ok",
                                          f"{path}: {summary}; no tool call metered yet")


@pytest.mark.parametrize("who", ("own", "newest"))
def test_6_the_absent_meter(box, who):
    box.path.unlink()
    c = check(getattr(box, who))
    assert (c.ok, c.status, c.detail) == (
        False, "fail", f"{box.path} absent: no PostToolUse has metered this session (the plugin's hook)")


@pytest.mark.parametrize("who", ("own", "newest"))
def test_6_the_unreadable_transcript(box, who):
    box.tp.unlink()
    c = check(getattr(box, who))
    assert (c.ok, c.status, c.detail) == (
        False, "fail", f"{box.path}: transcript {box.tp} unreadable: FileNotFoundError")


def test_6_the_bare_machine(box):
    env = {**box.newest, "XDG_STATE_HOME": str(box.tmp / "bare-state")}
    c = check(env)
    assert (c.ok, c.status, c.detail) == (
        True, "note", "no session to meter ($CLAUDE_CODE_SESSION_ID unset, none resolved)")


def test_6_controls_the_fresh_meter_and_an_unreadable_ts(box):
    tail(box, [result(box.ts + 600)])
    rest(box, 60)                                       # within FRESH_S of the mtime: the pin's
    assert check(box.newest).detail == f"{box.path}: {box.summary}; 60s from the transcript"
    doc = json.loads(box.path.read_text())
    doc["ts"] = "<placeholder>"
    box.path.write_text(json.dumps(doc))
    c = check(box.newest)
    assert not c.ok and c.detail == (f"{box.path} stale: metered {box.m['transcript']['size']} "
                                     f"bytes of {os.stat(box.tp).st_size}, ts unreadable")


# ---- 7: doctor --json, the meter check's keys -----------------------------------------------

@pytest.mark.parametrize("kind", ("pass", "warn", "fail"))
def test_7_the_json_keys_are_the_pin_s(box, kind, monkeypatch, capsys):
    rows = {"pass": [text(box.ts + 20)], "warn": [], "fail": [result(box.ts + 600)]}[kind]
    tail(box, rows, b"<placeholder>\n" if kind == "warn" else b"")
    rest(box, 2443)
    rc, out = cli_doctor(box.newest, box.repo, monkeypatch, capsys, "--json")
    doc = json.loads(out)
    assert list(doc) == ["schema", "ok", "tool", "failed", "warned", "checks"]
    row = next(c for c in doc["checks"] if c["name"] == "meter")
    assert list(row) == ["name", "ok", "status", "detail", "remedy"]
    assert rc in (0, 2)                 # the statuses and exits: lines 1, 4 and 5
