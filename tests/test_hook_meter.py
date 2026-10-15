"""The meter's hooks: PostToolUse by D13, the prompt line, the ledger at SessionEnd."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import charter, config, hooks, ledger, meter, resolver

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "meter"
SID = "meter-sess-1"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    config.ensure_dirs()
    return dict(os.environ)


def sdir(env):
    return resolver.session_dir(resolver.state_dir(env), SID)


def transcript(tmp_path, context, turns=1, name="t.jsonl"):
    """`turns` assistant lines, the last at `context` occupancy."""
    rows = []
    for i in range(turns):
        ctx = context if i == turns - 1 else 1000
        rows.append({"type": "assistant", "requestId": f"r{i}", "timestamp": "2026-09-22T10:00:00Z",
                     "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                                 "content": [{"type": "text", "text": "<placeholder>"}],
                                 "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                           "cache_read_input_tokens": ctx, "output_tokens": 7}}})
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def tool(env, path, **extra):
    return hooks.post_tool_use({"session_id": SID, "transcript_path": str(path),
                                "tool_name": "Read", **extra}, env)


def ctx(out):
    return out["hookSpecificOutput"]["additionalContext"]


# --- D13: stdout and exit per fixture ------------------------------------------

def test_79_percent_is_silent_and_writes_the_meter(env, tmp_path):
    assert tool(env, transcript(tmp_path, 142200)) == {}
    m = meter.load(sdir(env))
    assert m["pct_context"] == 79.0 and m["signal"]["crossed"] is False


@pytest.mark.parametrize("context,pct", [(144000, "80.0"), (145800, "81.0")])
def test_the_first_crossing_speaks_once(env, tmp_path, context, pct):
    out = tool(env, transcript(tmp_path, context))
    line = ctx(out)
    assert line.startswith(f"CHECKPOINT: {pct}% context ({context}/180000), 0.2% turns (1/400); "
                           "charter history/sittings; bring the charter current, commit, then exit")
    assert "EXIT" not in line and out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert meter.load(sdir(env))["signal"] == {"crossed": True, "tools_since": 0}


def test_past_the_crossing_every_tenth_tool(env, tmp_path):
    p = transcript(tmp_path, 150000)
    said = [bool(tool(env, p)) for _ in range(21)]
    assert [i for i, s in enumerate(said) if s] == [0, 10, 20]


def test_at_100_every_tool_with_the_exit_rule(env, tmp_path):
    p = transcript(tmp_path, 180000)
    for _ in range(3):
        out = tool(env, p)
        assert ctx(out).endswith("\n" + hooks.EXIT_RULE)
        assert len(json.dumps(out)) <= 400


def test_s17_exit_rule_never_compacts(env, tmp_path):
    """Entry 17 (amended 2026-09-29): a sitting respawns and never compacts."""
    line = ctx(tool(env, transcript(tmp_path, 180000))).lower()
    assert "exit:" in line and "never compact" in line and "at most once" not in line


def test_s17_profiles_never_compact():
    from claude_session.yamlsubset import load
    profiles = load(resolver.SHIPPED.read_text())["profiles"]
    said = {n: p.get("description", "") for n, p in profiles.items()}
    assert "orchestrator" in said and "orchestrator-opus" in said
    old = ("compacts in place", "compact at most once")
    assert [n for n, d in said.items() if any(o in d.lower() for o in old)] == []


def test_turns_ceiling_counts_too(env, tmp_path):
    out = tool(env, transcript(tmp_path, 1000, turns=400))
    assert "100.0% turns (400/400)" in ctx(out) and hooks.EXIT_RULE in ctx(out)


def test_output_stays_under_400_bytes_with_a_long_charter(env, tmp_path):
    d = sdir(env)
    d.mkdir(parents=True)
    (d / "resolved.json").write_text(json.dumps(
        {"session": {"posture": "signal", "charter": {"dir": "x" * 300}}}))
    out = tool(env, transcript(tmp_path, 180000))
    assert "CHECKPOINT" in ctx(out) and len(json.dumps(out)) <= 400


# --- S33: under a launcher the line names the recorded charter and checkpoint --respawn ---

S33_HEAD = "CHECKPOINT: 80.0% context (144000/180000), 0.2% turns (1/400); charter "
S33_TAIL = ("bring the charter current with a Next act that opens RESPAWN:, commit, then run "
            "`agentik session checkpoint --respawn --charter {f}` and end the turn; "
            "the launcher restarts this sitting")
NONE_FOUND = "<this sitting's charter>"


def chained(env, name="net"):
    return {**env, hooks.CHAIN_VAR: name}


def charters(cwd, d, *names):
    """Each name under <cwd>/<d>, every next one a minute newer by mtime."""
    (cwd / d).mkdir(parents=True, exist_ok=True)
    out = []
    for i, n in enumerate(names):
        f = cwd / d / n
        f.write_text("# sitting\n")
        os.utime(f, (1_000_000 + 60 * i,) * 2)
        out.append(f)
    return out


def record(env, path):
    """What this sitting's `charter open` leaves in its session dir (S33 ruling 2)."""
    s = sdir(env)
    s.mkdir(parents=True, exist_ok=True)
    (s / hooks.CHARTER_REC).write_text(json.dumps({"path": str(path)}))


def s33_lines(f, cwd):
    """The line for either spelling the ladder may choose (F3: whatever the temp root's
    length): absolute, or relative to cwd once the absolute one passes MAX_OUT."""
    return {S33_HEAD + f"{s}; " + S33_TAIL.format(f=s) for s in (str(f), os.path.relpath(f, cwd))}


def test_s33_a_recorded_charter_is_named_beside_a_newer_childs(env, tmp_path):
    t = charter.today()
    mine, child = charters(tmp_path, "h", f"{t}-1-orch.md", f"{t}-2-s33.md")
    record(env, mine)
    line = ctx(tool(chained(env), transcript(tmp_path, 144000), cwd=str(tmp_path)))
    assert line in s33_lines(mine, tmp_path) and child.name not in line
    assert "checkpoint --respawn --charter " in line and "end the turn" in line
    assert hooks._charter_file(str(tmp_path), sdir(env)) == [
        str(mine), f"h/{mine.name}", hooks.NO_CHARTER]


@pytest.mark.parametrize("with_cwd", [True, False])
def test_s33_no_charter_file_names_this_sittings_charter(env, tmp_path, with_cwd):
    extra = {"cwd": str(tmp_path)} if with_cwd else {}
    line = ctx(tool(chained(env), transcript(tmp_path, 144000), **extra))
    assert line == S33_HEAD + f"{NONE_FOUND}; " + S33_TAIL.format(f=NONE_FOUND)
    assert f"--charter {NONE_FOUND}`" in line


@pytest.mark.parametrize("context", [144000, 180000])
def test_s33_a_200_character_cwd_stays_under_the_cap(env, tmp_path, context):
    cwd = tmp_path / ("c" * (199 - len(str(tmp_path))))
    assert len(str(cwd)) == 200
    f, = charters(cwd, "history/sittings", f"{charter.today()}-1-x.md")
    record(env, f)
    out = tool(chained(env), transcript(tmp_path, context), cwd=str(cwd))
    assert len(json.dumps(out)) <= hooks.MAX_OUT and "checkpoint --respawn" in ctx(out)
    assert f"--charter history/sittings/{f.name}`" in ctx(out)
    assert ctx(out).endswith("\n" + hooks.EXIT_RULE) == (context == 180000)


def test_s33_the_tenth_tool_past_the_crossing_repeats_the_line(env, tmp_path):
    f, = charters(tmp_path, "h", f"{charter.today()}-1-x.md")
    record(env, f)
    p = transcript(tmp_path, 144000)
    outs = [tool(chained(env), p, cwd=str(tmp_path)) for _ in range(11)]
    assert [i for i, o in enumerate(outs) if o] == [0, 10]
    assert ctx(outs[10]) == ctx(outs[0]) and ctx(outs[10]) in s33_lines(f, tmp_path)


@pytest.mark.parametrize("chain", [None, "", "a b", ".."])
def test_s33_off_a_launcher_the_pins_line(env, tmp_path, chain):
    """Unset, empty, or a value CHAIN_RE refuses (F4, as cli.py reads it): no launcher."""
    f, = charters(tmp_path, "history/sittings", f"{charter.today()}-1-x.md")
    record(env, f)
    e = {k: v for k, v in env.items() if k != hooks.CHAIN_VAR}
    if chain is not None:
        e[hooks.CHAIN_VAR] = chain
    line = ctx(tool(e, transcript(tmp_path, 144000), cwd=str(tmp_path)))
    assert line == ("CHECKPOINT: 80.0% context (144000/180000), 0.2% turns (1/400); "
                    "charter history/sittings; bring the charter current, commit, then exit")


def test_s33_no_record_names_the_placeholder_beside_todays_charters(env, tmp_path):
    t = charter.today()
    charters(tmp_path, "history/sittings", f"{t}-1-orch.md", f"{t}-2-s33.md", "README.md")
    line = ctx(tool(chained(env), transcript(tmp_path, 144000), cwd=str(tmp_path)))
    assert line == S33_HEAD + f"{NONE_FOUND}; " + S33_TAIL.format(f=NONE_FOUND)


@pytest.mark.parametrize("case", ["gone", "outside", "unsafe", "relative", "junk"])
def test_s33_an_unusable_record_names_the_placeholder(env, tmp_path, case):
    cwd = tmp_path / "repo"
    f, = charters(cwd, "h", f"{charter.today()}-1-x.md")
    if case == "gone":
        record(env, f)
        f.unlink()
    elif case == "outside":
        record(env, charters(tmp_path, "other", "x.md")[0])
    elif case == "unsafe":
        record(env, charters(cwd, "a b", "x.md")[0])
    elif case == "relative":
        record(env, f"h/{f.name}")
    else:
        record(env, f)
        (sdir(env) / hooks.CHARTER_REC).write_text("{not json")
    line = ctx(tool(chained(env), transcript(tmp_path, 144000), cwd=str(cwd)))
    assert line == S33_HEAD + f"{NONE_FOUND}; " + S33_TAIL.format(f=NONE_FOUND)


def test_unreadable_transcript_says_nothing_writes_nothing(env, tmp_path):
    assert tool(env, tmp_path / "absent.jsonl") == {}
    assert not sdir(env).exists()


def test_a_subagent_leaves_the_meter_alone(env, tmp_path):
    # A helper's PostToolUse writes only its stamp (respawn-r1 ruling 6), never the meter.
    assert tool(env, FIX / "at-80.jsonl", agent_id="a1") == {}
    assert sorted(p.name for p in sdir(env).iterdir()) == ["helper-activity.json"]


def test_posture_off_is_silent(env, tmp_path):
    d = sdir(env)
    d.mkdir(parents=True)
    (d / "resolved.json").write_text(json.dumps({"session": {"posture": "off"}}))
    assert tool(env, FIX / "at-100.jsonl") == {}


def test_ceilings_come_from_the_resolved_profile(env, tmp_path):
    d = sdir(env)
    d.mkdir(parents=True)
    (d / "resolved.json").write_text(json.dumps({"session": {
        "posture": "signal", "ceilings": {"context": 1000000, "turns": 400},
        "checkpoint_at": 0.8, "charter": {"dir": "notes"}}}))
    assert tool(env, FIX / "at-100.jsonl") == {}
    assert meter.load(d)["ceilings"]["context"] == 1000000


def test_used_pct_reads_the_meter(env, tmp_path):
    assert hooks.used_pct() is None
    tool(env, transcript(tmp_path, 90000, turns=300))
    assert hooks.used_pct() == 75.0 and hooks.state()[1] == "clear"


# --- the prompt line -------------------------------------------------------------

def test_prompt_line_whenever_a_meter_exists(env, tmp_path):
    assert hooks.user_prompt_submit({"session_id": SID}) == {}
    tool(env, FIX / "at-80.jsonl")
    line = ctx(hooks.user_prompt_submit({"session_id": SID})).splitlines()[0]
    assert line == "session: 80.0% context, 1.0% turns, zone notice"


# --- the ledger ------------------------------------------------------------------

def test_session_end_appends_one_ledger_line(env, tmp_path):
    hooks.session_end({"session_id": SID, "transcript_path": str(FIX / "at-80.jsonl"),
                       "reason": "clear", "cwd": str(tmp_path)}, env)
    lines = ledger.read(resolver.state_dir(env))
    assert len(lines) == 1 and list(lines[0]) == list(ledger.LEDGER_KEYS)
    assert (lines[0]["exit_reason"], lines[0]["turns"], lines[0]["session"]) == ("clear", 4, SID)


def test_session_end_of_a_subagent_or_without_a_transcript(env, tmp_path):
    hooks.session_end({"session_id": SID, "transcript_path": str(FIX / "at-80.jsonl"),
                       "agent_id": "a1"}, env)
    hooks.session_end({"session_id": SID}, env)
    hooks.session_end({"session_id": SID, "transcript_path": str(tmp_path / "gone")}, env)
    assert ledger.read(resolver.state_dir(env)) == []


# --- the hook lines, end to end ----------------------------------------------------

def run(event, payload, xdg):
    r = subprocess.run([sys.executable, "-m", "claude_session", "hook", event],
                       input=json.dumps(payload), capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, "XDG_STATE_HOME": str(xdg)})
    assert r.returncode == 0
    return r.stdout


@pytest.mark.parametrize("name,speaks", [("under-80", False), ("at-80", True), ("at-100", True)])
def test_the_hook_lines(tmp_path, name, speaks):
    out = run("PostToolUse", {"session_id": "t", "tool_name": "Read",
                              "transcript_path": f"tests/fixtures/meter/{name}.jsonl"}, tmp_path)
    assert ("CHECKPOINT" in out) is speaks and len(out) <= 400
    assert out.strip() == "{}" or json.loads(out)["hookSpecificOutput"]


def test_the_hook_line_for_a_subagent(tmp_path):
    out = run("PostToolUse", {"session_id": "t", "agent_id": "a1",
                              "transcript_path": "tests/fixtures/meter/at-80.jsonl"}, tmp_path)
    assert out.strip() == "{}"
    written = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file())
    assert [p.rsplit("/", 1)[-1] for p in written] == ["helper-activity.json"]


# --- status, report, doctor --------------------------------------------------------

def cli(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli as c
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = c.main(list(argv))
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


def test_status_without_a_meter_exits_2(env):
    assert cli("status")[0] == 2


def test_status_reads_the_meter(env, tmp_path):
    tool(env, FIX / "at-80.jsonl")
    rc, out, _ = cli("status")
    assert rc == 0 and out.startswith(
        f"session {SID}: 80.0% context (144000/180000), 1.0% turns (4/400), zone notice")
    rc, out, _ = cli("status", "--json")
    assert rc == 0 and json.loads(out) == meter.load(sdir(env))


def test_status_transcript_parses_once_and_writes_nothing(env, tmp_path):
    rc, out, _ = cli("status", "--transcript", str(FIX / "with-builders/sess-b.jsonl"), "--json")
    d = json.loads(out)
    assert rc == 0 and d["total"]["turns"] == 4 and d["builders_source"] == "subagents"
    assert not (tmp_path / "xdg").exists()
    assert cli("status", "--transcript", str(tmp_path / "gone.jsonl"))[0] == 2


def test_report(env, tmp_path):
    assert cli("report")[0] == 2
    hooks.session_end({"session_id": SID, "transcript_path": str(FIX / "at-80.jsonl"),
                       "reason": "other", "cwd": str(tmp_path)}, env)
    rc, out, _ = cli("report")
    assert rc == 0 and out.splitlines()[0].split()[:2] == ["ended", "session"]
    assert SID[:8] in out.splitlines()[1]
    rc, out, _ = cli("report", "--json")
    assert json.loads(out)[0]["session"] == SID
    assert cli("report", "--since", "2999-01-01")[0] == 2
    assert cli("report", "--since", "yesterday")[0] == 1


def test_doctor_meter_absent_fresh_and_stale(env, tmp_path):
    from claude_session import doctor
    c = doctor._check_meter(env)
    assert not c.ok and "absent" in c.detail
    p = transcript(tmp_path, 1000)
    tool(env, p)
    assert doctor._check_meter(env).ok
    with open(p, "a") as f:                     # the transcript grew; the meter did not
        f.write("{}\n")
    os.utime(p, (os.stat(p).st_atime, os.stat(p).st_mtime + 600))
    c = doctor._check_meter(env)
    assert not c.ok and "stale" in c.detail


# --- review r6 E5: the turn ceiling follows the smaller of the profile's and the launch's

def _start_then_tool(env, tmp_path, turns):
    p = transcript(tmp_path, 1000, turns=turns)
    hooks.session_start({"session_id": SID, "cwd": str(tmp_path), "transcript_path": str(p)}, env)
    out = tool(env, p)
    resolved = json.loads((sdir(env) / "resolved.json").read_text())["session"]
    return out, meter.load(sdir(env)), resolved


def test_max_turns_80_reads_65_turns_past_the_checkpoint(env, tmp_path):
    env["CLAUDE_SESSION_MAX_TURNS"] = "80"
    out, m, s = _start_then_tool(env, tmp_path, 65)
    assert s["ceilings"] == {"context": 180000, "turns": 80}
    assert s["ceilings_source"] == "CLAUDE_SESSION_MAX_TURNS"
    assert m["ceilings"]["turns"] == 80 and m["pct_turns"] == 81.2
    assert m["zone"] != "clear"
    assert "81.2% turns (65/80)" in ctx(out)


def test_max_turns_absent_the_profiles_400_reads_clear(env, tmp_path):
    env.pop("CLAUDE_SESSION_MAX_TURNS", None)
    out, m, s = _start_then_tool(env, tmp_path, 65)
    assert s["ceilings"]["turns"] == 400 and s["ceilings_source"] == "profile"
    assert m["zone"] == "clear" and out == {}


@pytest.mark.parametrize("raw", ["", "0", "-5", "eighty", "80.5", "1000"])
def test_max_turns_unparsable_nonpositive_or_larger_leaves_the_profile(env, tmp_path, raw):
    env["CLAUDE_SESSION_MAX_TURNS"] = raw
    _, m, s = _start_then_tool(env, tmp_path, 65)
    assert s["ceilings"]["turns"] == 400 and s["ceilings_source"] == "profile"
    assert m["zone"] == "clear"


def test_max_turns_session_start_names_the_source(env, tmp_path):
    env["CLAUDE_SESSION_MAX_TURNS"] = "80"
    out = hooks.session_start({"session_id": SID, "cwd": str(tmp_path)}, env)
    line = out["hookSpecificOutput"]["additionalContext"]
    assert "180000 context / 80 turns (CLAUDE_SESSION_MAX_TURNS)" in line
