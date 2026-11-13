"""Packet ss1-zero: a new session reads 0% from its first moment.

SessionStart, once it has written resolved.json, writes the session's first meter.json by
PostToolUse's own parse and save (R1); a transcript absent or unreadable is zero turns, and a
meter already on disk is replaced only by a parse that succeeded. Any failure there is
swallowed and the context is the pin's, byte for byte (R2). The readers stand (R3): `status`,
doctor's `meter` check and the module's `bandLine` read the meter as written. Each case in a
temp HOME, a made-up session id and a temp repo; no `claude`. The band's line is drawn by
the module itself under node, where node is (its name spelled in pieces, as test_band's)."""
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, doctor, hooks, meter, resolver

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugin" / "hooks" / ("session." + "ts")
SID = "ss1-zero-sess-0000-1111"
NO_METER = "session: no meter · agentik-session doctor"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    return dict(os.environ)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    return r


def sdir(env):
    return resolver.session_dir(resolver.state_dir(env), SID)


def transcript(tmp_path, turns, name="t.jsonl"):
    """`turns` assistant lines at 1000 tokens of context; 0 turns is an empty file."""
    rows = [{"type": "assistant", "requestId": f"r{i}", "timestamp": "2026-11-13T10:00:00Z",
             "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                         "content": [{"type": "text", "text": "<placeholder>"}],
                         "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                   "cache_read_input_tokens": 1000, "output_tokens": 7}}}
            for i in range(turns)]
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def start(env, repo, tp, source="startup"):
    return hooks.session_start({"session_id": SID, "transcript_path": str(tp), "cwd": str(repo),
                                "hook_event_name": "SessionStart", "source": source}, env)


def status():
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(["status"])
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def band(meter_text):
    """The module's own `bandLine(meter, false, now)`, under node; skips without either."""
    if not MOD.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    node = shutil.which("node")
    if node is None:
        pytest.skip("no node on PATH: the module's line is drawn by its own test")
    js = ("const m = await import(process.argv[1]); const t = process.argv[2];"
          "console.log(m.bandLine(t === '-' ? null : t, false, Date.now()))")
    r = subprocess.run([node, "--input-type=module", "-e", js, MOD.as_uri(),
                        "-" if meter_text is None else meter_text],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def zero_reads(env):
    """Acceptance 1 and 2 over the meter written: `status` and the band."""
    rc, out, err = status()
    assert rc == 0, err
    line = out.splitlines()[0]
    assert "0.0% context" in line and "0.0% turns" in line and "zone clear" in line, line
    drawn = band((sdir(env) / meter.METER).read_text())
    assert "ctx 0% · turns 0%" in drawn and "doctor" not in drawn and "no meter" not in drawn, drawn


# ---- acceptance 1, 2: an empty transcript --------------------------------------------

def test_1_2_an_empty_transcript_reads_zero_in_status_and_the_band(env, repo, tmp_path):
    start(env, repo, transcript(tmp_path, 0))
    zero_reads(env)


# ---- acceptance 3: a transcript that does not exist ------------------------------------

def test_3_an_absent_transcript_reads_zero_in_status_and_the_band(env, repo, tmp_path):
    gone = tmp_path / "not-yet.jsonl"
    start(env, repo, gone)
    zero_reads(env)
    m = meter.load(sdir(env))
    assert m["turns"] == 0 and m["transcript"]["path"] == str(gone)


# ---- acceptance 4: a resume reads the transcript's turns, as PostToolUse would ------------

def test_4_a_resume_says_four_turns_as_post_tool_use_would(env, repo, tmp_path):
    tp = transcript(tmp_path, 4)
    start(env, repo, tp, source="resume")
    rc, out, _ = status()
    assert rc == 0 and "turns (4/" in out.splitlines()[0], out
    by_start = meter.load(sdir(env))
    for f in (meter.METER, meter.STATE):
        (sdir(env) / f).unlink()
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp), "tool_name": "Read"}, env)
    by_tool = meter.load(sdir(env))
    for d in (by_start, by_tool):
        d.pop("ts")
    assert by_start == by_tool and by_start["turns"] == 4


def test_r1_a_meter_on_disk_is_replaced_only_by_a_parse_that_succeeded(env, repo, tmp_path):
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(transcript(tmp_path, 4)),
                         "tool_name": "Read"}, env)
    before = (sdir(env) / meter.METER).read_bytes()
    start(env, repo, tmp_path / "gone.jsonl", source="resume")
    assert (sdir(env) / meter.METER).read_bytes() == before


# ---- acceptance 5, 6: the hook never breaks a session; the context is the pin's ------------

def _pin_and_now(env, repo, tmp_path, monkeypatch, tp, source="startup", wrap=None):
    """(the hook's output with R1's writer a no-op, as at the pin; the same with it), each
    over a fresh state root at the same path."""
    outs = []
    for writer in (lambda *a, **k: None, hooks._first_meter):
        root = resolver.state_dir(env)
        for d in (root.rglob("*") if root.exists() else ()):
            if d.is_dir():                      # a folder the last run made read-only
                os.chmod(d, stat.S_IRWXU)
        shutil.rmtree(root, ignore_errors=True)
        with monkeypatch.context() as mp:
            mp.setattr(hooks, "_first_meter", writer)
            if wrap is not None:
                wrap(mp)
            outs.append(start(env, repo, tp, source))
    return outs


def test_5_an_unwritable_meter_is_swallowed_and_today_s_json_returned(env, repo, tmp_path,
                                                                        monkeypatch):
    real = resolver.save_request
    made = []

    def read_only(d, *a, **k):         # the session folder made read-only once resolved
        real(d, *a, **k)
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR)
        made.append(Path(d))

    try:
        pin, now = _pin_and_now(env, repo, tmp_path, monkeypatch, transcript(tmp_path, 0),
                                wrap=lambda mp: mp.setattr(resolver, "save_request", read_only))
    finally:
        for d in made:
            if d.exists():
                os.chmod(d, stat.S_IRWXU)
    assert now == pin and now["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert not (sdir(env) / meter.METER).exists()


def test_5_the_hook_exits_0_where_the_meter_cannot_be_written(env, repo, tmp_path):
    (sdir(env) / meter.METER).mkdir(parents=True)        # a folder where the file goes
    r = subprocess.run([sys.executable, "-m", "claude_session", "hook", "SessionStart"],
                       input=json.dumps({"session_id": SID, "cwd": str(repo),
                                         "transcript_path": str(transcript(tmp_path, 0)),
                                         "hook_event_name": "SessionStart", "source": "startup"}),
                       capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert r.returncode == 0 and r.stderr == "", r.stderr
    assert hooks.START_METER in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("turns, source", [(0, "startup"), (None, "startup"), (4, "resume")])
def test_6_the_context_is_the_pin_s_byte_for_byte(env, repo, tmp_path, monkeypatch, turns,
                                                 source):
    tp = tmp_path / "gone.jsonl" if turns is None else transcript(tmp_path, turns)
    pin, now = _pin_and_now(env, repo, tmp_path, monkeypatch, tp, source)
    ctx = now["hookSpecificOutput"]["additionalContext"]
    assert ctx.encode() == pin["hookSpecificOutput"]["additionalContext"].encode()
    assert now == pin and meter.load(sdir(env)) is not None


# ---- acceptance 7: doctor's meter check, before any tool call ------------------------------

def test_7_doctor_finds_the_meter_ok_before_any_tool_call(env, repo, tmp_path):
    start(env, repo, transcript(tmp_path, 0))
    c = doctor._check_meter(env)
    assert c.ok and "0.0% context, 0.0% turns, zone clear" in c.detail, c.detail


# ---- acceptance 8 and R3: the readers' fault words stand -----------------------------------

def test_8_no_meter_still_draws_no_meter():
    assert band(None) == NO_METER


def test_r3_status_with_no_session_folder_still_exits_2(env):
    rc, _, err = status()
    assert rc == 2 and "no meter for this session" in err


# ---- R4: where SessionStart resolves it writes the meter; where it returns early, none -------

def test_r4_a_helper_s_session_start_writes_its_meter(env, repo, tmp_path):
    env = {**env, "CLAUDE_SESSION_HELPER": "1", "CLAUDE_SESSION_PROFILE": "orchestrator"}
    start(env, repo, transcript(tmp_path, 0))
    assert meter.load(sdir(env))["zone"] == "clear"


def test_r4_an_early_return_writes_no_meter(env, repo, tmp_path, monkeypatch):
    def fails(*a, **k):
        raise RuntimeError("no layers")
    monkeypatch.setattr(resolver, "resolve", fails)
    out = start(env, repo, transcript(tmp_path, 0))
    assert "hookSpecificOutput" not in out
    root = resolver.state_dir(env)
    assert not root.exists() or not list(root.rglob(meter.METER))



# ---- review 1: each finding's reproduction ---------------------------------------------------

def _prompt(sid=SID):
    return hooks.user_prompt_submit({"session_id": sid, "hook_event_name": "UserPromptSubmit",
                                     "prompt": "<placeholder>"})


def test_review1_f1_no_meter_line_on_a_prompt_before_the_first_tool_call(env, repo, tmp_path,
                                                                          monkeypatch):
    """R2 holds: the first prompt's output is the pin's, byte for byte (no meter line while the
    meter's turns is 0), and so is the first prompt after a tool call."""
    tp = tmp_path / "later.jsonl"
    runs = []
    for writer in (lambda *a, **k: None, hooks._first_meter):
        root = resolver.state_dir(env)
        shutil.rmtree(root, ignore_errors=True)
        if tp.exists():
            tp.unlink()
        with monkeypatch.context() as mp:
            mp.setattr(hooks, "_first_meter", writer)
            start(env, repo, tp)
            first = _prompt()
            transcript(tmp_path, 4, name=tp.name)
            hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp),
                                 "tool_name": "Read"}, env)
            runs.append((json.dumps(first), json.dumps(_prompt())))
    pin, now = runs
    assert now[0].encode() == pin[0].encode() and "session meter" not in now[0], now[0]
    assert now[1].encode() == pin[1].encode() and "session meter" in now[1], now[1]
