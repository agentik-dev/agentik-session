"""Packet S45 (design/window-r1.md §7): the engine's measured window is the window pick's
first source, the role still chooses the ceilings within it, and every other figure of the
measure still decides nothing. A1 to A16 name the record's acceptance, one to a test family:
`-k a7`. The state and HOME are conftest's per-test roots, so a user layer never reaches a
test; a test that wants one writes it."""
import ast
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, config, hooks, meter, models, resolver
from claude_session.yamlsubset import load as yaml_load

ROOT = Path(__file__).resolve().parents[1]
SID = "cli-sess-0000-1111-2222"
OPUS = "claude-opus-5-5"
FOUR = ("window", "ceilings", "window_source", "limits_source")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    config.ensure_dirs()
    d = tmp_path / "repo"
    d.mkdir()
    return d


def env():
    return dict(os.environ)


def sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), SID)


def run(*argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(list(argv))
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.stdin = old
    return rc, out.getvalue(), err.getvalue()


def body(window, tokens=20000, percent=2, rate=None, cost=None):
    return {"context": {"tokens": tokens, "window": window, "percent": percent},
            "rateLimits": rate or [], "cost": cost, "changed": ["context"]}


def measured(window, **kw):
    """`measure record` at this window; a raw string goes as it is (a float's spelling)."""
    text = window if isinstance(window, str) else json.dumps(body(window, **kw))
    return run("measure", "record", "--session", SID, stdin=text)


def transcript(tmp_path, *rows, name="t.jsonl"):
    """One assistant line per (model, context)."""
    lines = []
    for i, (model, ctx) in enumerate(rows):
        lines.append({"type": "assistant", "requestId": f"r{i}",
                      "timestamp": "2026-10-30T10:00:00Z",
                      "message": {"id": f"m{i}", "model": model,
                                  "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                            "cache_read_input_tokens": ctx, "output_tokens": 7}}})
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in lines))
    return p


def start(repo, tp=None, model=None):
    payload = {"session_id": SID, "cwd": str(repo)}
    if tp:
        payload["transcript_path"] = str(tp)
    if model:
        payload["model"] = model
    return hooks.session_start(payload, env())


def tool(repo, tp):
    return hooks.post_tool_use({"session_id": SID, "cwd": str(repo), "transcript_path": str(tp),
                                "tool_name": "Read"}, env())


def said(out) -> str:
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


def session():
    return json.loads((sdir() / "resolved.json").read_text())["session"]


def doc():
    return json.loads((sdir() / "resolved.json").read_text())


def bytes_of(*names):
    return {n: (sdir() / n).read_bytes() for n in names}


def assert_resolved(window, context, source=None):
    s = session()
    assert (s["window"], s["ceilings"]["context"]) == (window, context)
    if source:
        assert s["window_source"] == source


def assert_meter(window, context, pct, source=None):
    m = meter.load(sdir())
    assert (m["window"], m["ceilings"]["context"], m["pct_context"]) == (window, context, pct)
    if source:
        assert m["window_source"] == source


def pytest_in_process(*args):
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           *args], cwd=ROOT, capture_output=True, text=True)


# ---- A1, A2: the owner's test ----------------------------------------------------------

def test_a1_owners_test_orchestrator_opus(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 150000))
    start(repo, tp)
    assert_resolved(200000, 180000, f"session:{OPUS}")

    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")
    s = session()
    assert s["ceilings"] == {"context": 400000, "turns": 400}
    assert s["limits_source"] == "role:orchestrator-opus window:1000000"
    out = tool(repo, tp)
    assert_meter(1000000, 400000, 37.5, "engine:1000000")
    assert meter.load(sdir())["limits_source"] == "role:orchestrator-opus window:1000000"
    assert "CHECKPOINT" not in said(out)

    assert measured(200000)[0] == 0
    assert_resolved(200000, 180000, "engine:200000")
    out = tool(repo, tp)
    assert_meter(200000, 180000, 83.3, "engine:200000")
    assert "CHECKPOINT" in said(out)

    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")
    tool(repo, tp)
    assert_meter(1000000, 400000, 37.5, "engine:1000000")


def test_a2_owners_test_builder(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 150000))
    start(repo, tp)
    for w in (1000000, 200000, 1000000):
        assert measured(w)[0] == 0
        assert_resolved(w, 180000, f"engine:{w}")
        assert session()["ceilings"] == {"context": 180000, "turns": 400}
        tool(repo, tp)
        assert_meter(w, 180000, 83.3, f"engine:{w}")


# ---- A3: no reading (control) ----------------------------------------------------------

def test_a3_no_reading_is_todays(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 150000))
    start(repo, tp)
    tool(repo, tp)
    d = doc()
    s = d["session"]
    assert s["window"] == 200000 and s["ceilings"] == {"context": 180000, "turns": 400}
    assert s["window_source"] == f"session:{OPUS}"
    assert s["limits_source"] == "role:orchestrator-opus window:200000"
    assert s["windows"]["1m"]["context"] == 400000 and s["windows"]["200k"]["context"] == 180000
    assert_meter(200000, 180000, 83.3, f"session:{OPUS}")
    text = (sdir() / "resolved.json").read_text() + (sdir() / "meter.json").read_text()
    assert "engine:" not in text
    assert "engine:context.window" not in [i["path"] for i in d["provider"]["inputs"]]


def test_a3_the_table_tests_are_untouched_and_pass():
    r = pytest_in_process("tests/test_models.py", "tests/test_launch_model.py")
    assert r.returncode == 0, r.stdout[-400:]


# ---- A4: garbage -----------------------------------------------------------------------

BAD = [None, 0, -1, True, "1000000", 1.5, 1000000.0, 10**9 + 1, []]
TORN = ['{"context": {"wind', "[1, 2]", '{"context": null}', '{"context": [1]}', "7", ""]


@pytest.mark.parametrize("bad", BAD, ids=repr)
def test_a4_garbage_reads_as_none(tmp_path, bad):
    (tmp_path / models.MEASURE).write_text(json.dumps({"context": {"window": bad}}))
    assert models.engine_window(tmp_path) is None
    table = {"opus": 200000}
    today = models.pick(table, None, OPUS)
    assert today == (200000, f"session:{OPUS}")
    assert models.pick(table, None, OPUS, engine=models.engine_window(tmp_path)) == today
    assert models.pick(table, None, OPUS, engine=bad) == today


@pytest.mark.parametrize("text", TORN)
def test_a4_a_torn_file_reads_as_none(tmp_path, text):
    (tmp_path / models.MEASURE).write_text(text)
    assert models.engine_window(tmp_path) is None


def test_a4_no_file_reads_as_none(tmp_path):
    assert models.engine_window(tmp_path) is None
    assert models.engine_window(tmp_path / "absent") is None


@pytest.mark.parametrize("v", [1, 32000, 1000000, 10**9])
def test_a4_a_good_window_reads(tmp_path, v):
    (tmp_path / models.MEASURE).write_text(json.dumps({"context": {"window": v}}))
    assert models.engine_window(tmp_path) == v
    assert models.pick({"opus": 200000}, OPUS, engine=v) == (v, f"engine:{v}")


@pytest.mark.parametrize("bad", BAD, ids=repr)
def test_a4_a_refused_measure_keeps_the_reading_and_never_rewinds(repo, tmp_path, monkeypatch, bad):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    start(repo)
    assert measured(1000000)[0] == 0
    before = bytes_of("measure.json", "resolved.json")
    called = []
    monkeypatch.setattr(resolver, "rewindow", lambda *a: called.append(a))
    assert measured(bad)[0] == 2
    assert called == []
    assert bytes_of("measure.json", "resolved.json") == before


@pytest.mark.parametrize("text", TORN)
def test_a4_a_torn_file_lets_the_meter_read_the_table(repo, tmp_path, monkeypatch, text):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 18000))
    start(repo, tp)
    (sdir() / models.MEASURE).write_text(text)
    tool(repo, tp)
    assert_meter(200000, 180000, 10.0, f"session:{OPUS}")


# ---- A5: the rest decides nothing ------------------------------------------------------

def test_a5_criterion_4_passes():
    r = pytest_in_process("tests/test_measure.py", "-k", "criterion_4")
    assert r.returncode == 0, r.stdout[-400:]


def test_a5_the_other_figures_decide_nothing(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 18000))
    start(repo, tp)
    before = doc()
    assert measured(1000000, tokens=999999, percent=99,
                    rate=[{"kind": "five_hour", "percentUsed": 99}], cost={"usd": 99})[0] == 0
    out = tool(repo, tp)
    assert_meter(1000000, 400000, 4.5)
    assert "CHECKPOINT" not in said(out)
    after = doc()
    assert {k: v for k, v in after["session"].items() if k not in FOUR} == \
        {k: v for k, v in before["session"].items() if k not in FOUR}
    assert {k: v for k, v in after.items() if k != "session"} == \
        {k: v for k, v in before.items() if k != "session"}


def test_a5_only_the_window_is_read(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 18000))
    start(repo, tp)
    (sdir() / models.MEASURE).write_text(json.dumps({"context": {"window": 1000000}}))
    tool(repo, tp)
    thin = meter.load(sdir())
    assert measured(1000000, tokens=999999, percent=99, cost={"usd": 99})[0] == 0
    tool(repo, tp)
    full = meter.load(sdir())
    keys = ("window", "window_source", "limits_source", "ceilings", "pct_context")
    assert {k: thin[k] for k in keys} == {k: full[k] for k in keys}


# ---- A6: `set` keeps it ----------------------------------------------------------------

@pytest.mark.parametrize("verb", [("posture", "deny"), ("model", "sonnet")], ids=["posture", "model"])
def test_a6_set_keeps_the_reading(repo, monkeypatch, verb):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    monkeypatch.chdir(repo)
    start(repo)
    assert measured(1000000)[0] == 0
    rc, _, err = run("set", *verb)
    assert rc == 0, err
    s = session()
    assert s[verb[0]] == verb[1]
    assert_resolved(1000000, 400000, "engine:1000000")
    assert s["ceilings"] == {"context": 400000, "turns": 400}
    paths = [i["path"] for i in doc()["provider"]["inputs"]]
    assert paths.count("engine:context.window") == 1


# ---- A7: the modules -------------------------------------------------------------------

def test_a7_criterion_3_passes():
    r = pytest_in_process("tests/test_mod.py", "-k", "criterion_3")
    assert r.returncode == 0, r.stdout[-400:]


@pytest.mark.parametrize("name", ["meter.py", "resolver.py", "chain.py", "hooks.py", "budget.py"])
def test_a7_what_decides_never_names_the_file(name):
    assert "measure.json" not in (ROOT / "plugin" / "lib" / "claude_session" / name).read_text()


def test_a7_one_constant_one_opener():
    from claude_session import measure
    text = (ROOT / "plugin" / "lib" / "claude_session" / "models.py").read_text()
    assert text.count("measure.json") == 1
    assert models.MEASURE == "measure.json" and measure.MEASURE is models.MEASURE
    tree = ast.parse(text)
    users = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
             and any(isinstance(x, ast.Name) and x.id == "MEASURE" for x in ast.walk(n))]
    assert users == ["engine_window"]
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "engine_window")
    doc_node = fn.body[0].value if isinstance(fn.body[0], ast.Expr) else None
    words = {x.value for x in ast.walk(fn) if isinstance(x, ast.Constant)
             and isinstance(x.value, str) and x is not doc_node}
    assert words == {"context", "window"}


# ---- A8: no flap -----------------------------------------------------------------------

def test_a8_a_model_change_never_falls_back_with_a_reading(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator")
    tp = transcript(tmp_path, ("claude-fable-5-1", 100000), (OPUS, 300000))
    start(repo, tp)
    assert measured(1000000)[0] == 0
    out = tool(repo, tp)
    assert_meter(1000000, 400000, 75.0, "engine:1000000")
    assert "CHECKPOINT" not in said(out)


def test_a8_the_control_with_no_reading_flaps(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator")
    tp = transcript(tmp_path, ("claude-fable-5-1", 100000), (OPUS, 300000))
    start(repo, tp)
    out = tool(repo, tp)
    assert_meter(200000, 180000, 166.7)
    assert "EXIT" in said(out)


# ---- A9: the race ----------------------------------------------------------------------

def resolved_now(repo, **kw):
    return resolver.resolve(repo, SID, env(), profile="orchestrator-opus", session_model=OPUS,
                            session_model_source="payload", **kw)


def test_a9_measure_before_the_directory(repo, tmp_path, capfd):
    tp = transcript(tmp_path, (OPUS, 150000))
    rc, _, err = measured(1000000)
    assert rc == 1 and "no session" in err
    assert not sdir().exists()
    resolver.write(resolved_now(repo), resolver.state_dir(os.environ))
    assert_resolved(200000, 180000)
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")
    tool(repo, tp)
    assert_meter(1000000, 400000, 37.5)


def test_a9_measure_before_resolved_then_start_writes_the_table(repo, tmp_path):
    tp = transcript(tmp_path, (OPUS, 150000))
    r = resolved_now(repo)                  # SessionStart's resolve read no reading
    sdir().mkdir(parents=True)
    assert measured(1000000)[0] == 0        # rewindow finds nothing
    assert not (sdir() / "resolved.json").exists()
    resolver.write(r, resolver.state_dir(os.environ))
    assert_resolved(200000, 180000)
    tool(repo, tp)
    assert_meter(1000000, 400000, 37.5)     # the meter is right throughout
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")


def test_a9_start_read_no_reading_and_writes_last(repo, tmp_path):
    tp = transcript(tmp_path, (OPUS, 150000))
    resolver.write(resolved_now(repo), resolver.state_dir(os.environ))
    late = resolved_now(repo)               # reads before the measure, writes after its rewind
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000)
    resolver.write(late, resolver.state_dir(os.environ))
    assert_resolved(200000, 180000)
    tool(repo, tp)
    assert_meter(1000000, 400000, 37.5)
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")


def test_a9_set_resolved_before_a_measure_writes_after_its_rewind(repo, tmp_path):
    tp = transcript(tmp_path, (OPUS, 150000))
    resolver.write(resolved_now(repo), resolver.state_dir(os.environ))
    late = resolved_now(repo, overlay={"posture": "deny"})
    assert measured(1000000)[0] == 0
    resolver.write(late, resolver.state_dir(os.environ))
    assert_resolved(200000, 180000)
    assert session()["posture"] == "deny"
    tool(repo, tp)
    assert_meter(1000000, 400000, 37.5)
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")
    assert session()["posture"] == "deny"       # `set`'s other keys are kept


RACER = """
import os, sys
from pathlib import Path
from claude_session import resolver
kind, sid, cwd = sys.argv[1:4]
state = resolver.state_dir(os.environ)
if kind == "write":
    r = resolver.resolve(cwd, sid, os.environ, profile="orchestrator-opus",
                         overlay={"posture": "deny"}, session_model="claude-opus-5-5")
    for _ in range(25):
        resolver.write(r, state)
else:
    sdir = resolver.session_dir(state, sid)
    for i in range(25):
        resolver.rewindow(sdir, 1000000 if i % 2 else 200000)
"""


def test_a9_eight_processes(repo):
    resolver.write(resolved_now(repo, overlay={"posture": "deny"}), resolver.state_dir(os.environ))
    procs = [subprocess.Popen([sys.executable, "-B", "-c", RACER,
                               "write" if i % 2 else "rewind", SID, str(repo)],
                              cwd=ROOT, stderr=subprocess.PIPE, text=True) for i in range(8)]
    errs = [p.communicate()[1] for p in procs]
    assert [p.returncode for p in procs] == [0] * 8, errs
    assert errs == [""] * 8
    d = doc()
    assert yaml_load((sdir() / "resolved.yaml").read_text()) == d
    assert d["session"]["posture"] == "deny"
    assert not list(sdir().glob("*.tmp"))


def test_a9_the_lock_creates_no_file(repo):
    resolver.write(resolved_now(repo), resolver.state_dir(os.environ))
    names = sorted(p.name for p in sdir().iterdir())
    assert resolver.rewindow(sdir(), 200000) is False       # the window has not moved
    assert sorted(p.name for p in sdir().iterdir()) == names


def test_a9_no_lock_write_goes_on_and_rewindow_skips(repo, monkeypatch):
    resolver.write(resolved_now(repo), resolver.state_dir(os.environ))
    def no_lock(*a):
        raise OSError("flock refused")
    monkeypatch.setattr(resolver.fcntl, "flock", no_lock)
    before = bytes_of("resolved.json")
    assert resolver.rewindow(sdir(), 1000000) is False
    assert bytes_of("resolved.json") == before
    resolver.write(resolved_now(repo, overlay={"posture": "deny"}), resolver.state_dir(os.environ))
    assert session()["posture"] == "deny"


@pytest.mark.parametrize("text", ["{torn", "[]", '{"session": 7}', '{"session": {"window": 1}}'])
def test_a9_a_failed_rewind_is_silent(repo, monkeypatch, text):
    start(repo)
    (sdir() / "resolved.json").write_text(text)
    rc, out, err = measured(1000000)
    assert (rc, err) == (0, "")
    assert (sdir() / "resolved.json").read_text() == text
    assert models.engine_window(sdir()) == 1000000


# ---- A10: the classes ------------------------------------------------------------------

@pytest.mark.parametrize("window,ceiling", [(32000, 180000), (999999, 180000),
                                            (1000000, 400000), (2000000, 400000)])
def test_a10_the_classes(repo, tmp_path, monkeypatch, window, ceiling):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 18000))
    start(repo, tp)
    assert measured(window)[0] == 0
    # 200000's own figure is not moved twice: the first measure moves it from the table's
    assert_resolved(window, ceiling, f"engine:{window}")
    tool(repo, tp)
    m = meter.load(sdir())
    assert (m["window"], m["ceilings"]["context"]) == (window, ceiling)


# ---- A11: the twin ---------------------------------------------------------------------

def test_a11_the_twin(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    monkeypatch.chdir(repo)
    start(repo)
    before = doc()
    assert measured(1000000)[0] == 0
    after = doc()
    assert yaml_load((sdir() / "resolved.yaml").read_text()) == after
    assert list(after) == list(before)
    for k in after:
        if k != "session":
            assert after[k] == before[k], k
    moved = {k for k in after["session"] if after["session"][k] != before["session"].get(k)}
    assert moved == set(FOUR)
    assert list(after["session"]) == list(before["session"])
    rc, out, err = run("charter", "open", "a goal", "--dir", str(repo / "charters"))
    assert rc == 0, err
    row = next(l for l in next((repo / "charters").glob("*.md")).read_text().splitlines()
               if l.startswith("| budget |"))
    assert "400k context" in row
    rc, out, err = run("config", "show", "--resolved")
    assert rc == 0, err
    assert yaml_load(out)["session"]["window"] == 1000000


# ---- A12: the line ---------------------------------------------------------------------

CLAUSE = "the engine's first reading replaces this"


def test_a12_no_reading_names_the_table(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    line = said(start(repo))
    assert f"on a 200000 window (table, session:{OPUS}; {CLAUSE}), checkpoint at 80%" in line


def test_a12_a_reading_names_the_engine(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    start(repo)
    assert measured(1000000)[0] == 0
    line = said(start(repo))
    assert "on a 1000000 window (engine:1000000), checkpoint at 80%" in line
    assert CLAUSE not in line


def test_a12_the_clause_sits_outside_the_clip(repo, monkeypatch):
    long = "claude-opus-" + "x" * 80
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", long)
    line = said(start(repo))
    assert f"(table, {f'session:{long}'[:64]}; {CLAUSE})" in line


# ---- A14: no module (control); A13 is in plugin/hooks/session.test.ts ------------------

def test_a14_criterion_5_passes():
    r = pytest_in_process("tests/test_mod.py", "-k", "criterion_5")
    assert r.returncode == 0, r.stdout[-400:]


def test_a14_s34_skips_with_no_module(tmp_path, monkeypatch):
    import test_s34
    monkeypatch.setattr(test_s34, "HOOKS_DIR", tmp_path)
    with pytest.raises(pytest.skip.Exception):
        test_s34._fixture()


# ---- A15: a helper's ceiling -----------------------------------------------------------

LAYER = "session:\n  ceilings_1m: {context: 400000, turns: 400}\n"


def layered(repo):
    d = repo / ".claude" / "agentik"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(LAYER)


def test_a15_a_helper_with_no_reading(repo, tmp_path, monkeypatch):
    layered(repo)
    monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    tp = transcript(tmp_path, (OPUS, 190000))
    start(repo, tp)
    out = tool(repo, tp)
    assert_meter(200000, 180000, 105.6)
    assert "EXIT" in said(out)


def test_a15_a_helper_with_a_reading_keeps_its_ceiling(repo, tmp_path, monkeypatch):
    layered(repo)
    monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    tp = transcript(tmp_path, (OPUS, 190000))
    start(repo, tp)
    s = session()
    assert s["windows"]["1m"] == s["windows"]["200k"]
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 180000, "engine:1000000")
    out = tool(repo, tp)
    assert_meter(1000000, 180000, 105.6, "engine:1000000")
    assert "EXIT" in said(out)


def test_a15_a_relay_row_keeps_the_wider_budget(repo, tmp_path, monkeypatch):
    layered(repo)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    tp = transcript(tmp_path, (OPUS, 190000))
    start(repo, tp)
    assert measured(1000000)[0] == 0
    assert_resolved(1000000, 400000, "engine:1000000")
    out = tool(repo, tp)
    assert_meter(1000000, 400000, 47.5)
    assert "CHECKPOINT" not in said(out) and "EXIT" not in said(out)


# ---- A16: an unreadable measure --------------------------------------------------------

@pytest.mark.parametrize("window", ["1.5", "1000000.0", str(10**9 + 1)])
def test_a16_an_unreadable_measure_changes_nothing(repo, tmp_path, monkeypatch, window):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator")
    tp = transcript(tmp_path, (OPUS, 300000))
    start(repo, tp)
    assert measured(1000000)[0] == 0
    before = bytes_of("measure.json", "resolved.json")
    text = json.dumps(body("WINDOW")).replace('"WINDOW"', window)
    rc, _, err = measured(text)
    assert rc == 2, err
    assert bytes_of("measure.json", "resolved.json") == before
    out = tool(repo, tp)
    assert_meter(1000000, 400000, 75.0, "engine:1000000")
    assert "CHECKPOINT" not in said(out)


# ---- Amendment 2, refuter round 1 on 6818d45 -------------------------------------------

def real_cli(*argv, stdin=""):
    """The installed shape: the CLI in its own process, this test's state and HOME."""
    return subprocess.run([sys.executable, "-B", "-m", "claude_session", *argv], input=stdin,
                          capture_output=True, text=True, cwd=ROOT, env=env())


def twins():
    return (json.loads((sdir() / "resolved.json").read_text())["session"],
            yaml_load((sdir() / "resolved.yaml").read_text())["session"])


def test_f1_a_failure_between_the_twins_converges_through_the_cli(repo, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    start(repo)
    twin = sdir() / "resolved.yaml"
    old = twin.read_text()
    twin.unlink()
    twin.mkdir()                                    # the YAML's write fails, the JSON's has landed
    r = real_cli("measure", "record", "--session", SID, stdin=json.dumps(body(1000000)))
    assert (r.returncode, r.stderr) == (0, "")
    twin.rmdir()
    twin.write_text(old)
    j, y = twins()
    assert (j["window"], y["window"]) == (1000000, 200000)      # the state a failure leaves
    r = real_cli("measure", "record", "--session", SID, stdin=json.dumps(body(1000000)))
    assert (r.returncode, r.stderr) == (0, "")
    j, y = twins()
    assert y == j and y["window"] == 1000000
    assert y["window_source"] == "engine:1000000" and y["ceilings"]["context"] == 400000
    r = real_cli("config", "show", "--resolved")
    assert yaml_load(r.stdout)["session"]["window"] == 1000000
    assert not list(sdir().glob("*.tmp"))


def test_f1_a_stale_twin_with_a_torn_or_absent_yaml_converges(repo, monkeypatch):
    start(repo)
    assert measured(1000000)[0] == 0
    before = bytes_of("resolved.json")
    for fault in ("{torn: [", None):
        twin = sdir() / "resolved.yaml"
        twin.unlink()
        if fault:
            twin.write_text(fault)
        assert measured(1000000)[0] == 0
        assert yaml_load(twin.read_text()) == json.loads(before["resolved.json"])
        assert bytes_of("resolved.json") == before      # the JSON was right: it is not rewritten


def test_f1_twins_that_agree_are_not_rewritten(repo):
    start(repo)
    assert measured(1000000)[0] == 0
    before = {n: (sdir() / n).stat().st_mtime_ns for n in ("resolved.json", "resolved.yaml")}
    assert resolver.rewindow(sdir(), 1000000) is False
    assert before == {n: (sdir() / n).stat().st_mtime_ns for n in ("resolved.json", "resolved.yaml")}


STALLED = """
import json, os, sys, time
from pathlib import Path
from claude_session import resolver
path, go, doc = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
real = os.fdopen
def stalled(fd, *a, **kw):
    print("in", flush=True)         # its temp file is open, nothing written yet
    for _ in range(12000):
        if go.exists():
            break
        time.sleep(0.01)
    return real(fd, *a, **kw)
os.fdopen = stalled
resolver._write_atomic(path, doc)
"""


def test_f2_a_writer_stalled_on_its_temp_cannot_tear_another(repo, tmp_path):
    """The stall is a real one, in another process, and the file it waits on is the only
    clock: no sleep decides it, so a loaded Mac only makes it slower."""
    start(repo)
    path = sdir() / "resolved.json"
    good = doc()
    theirs = json.dumps({**good, "writer": "stalled"}) + "\n"
    go = tmp_path / "go"
    p = subprocess.Popen([sys.executable, "-B", "-c", STALLED, str(path), str(go), theirs],
                         cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "in"
        ours = {**good, "writer": "ours"}
        resolver._write_atomic(path, json.dumps(ours, indent=2) + "\n")
        assert json.loads(path.read_text()) == ours
    finally:
        go.touch()
    p.communicate(timeout=120)
    assert p.returncode == 0                        # its replace found its own temp
    assert json.loads(path.read_text())["writer"] == "stalled"      # whole, last writer wins
    assert not list(sdir().glob("*.tmp"))


def test_f2_a_failed_write_leaves_no_temp(repo, tmp_path):
    start(repo)
    target = sdir() / "somewhere"
    target.mkdir()                                  # os.replace onto a directory fails
    with pytest.raises(OSError):
        resolver._write_atomic(target, "x\n")
    assert not list(sdir().glob("*.tmp"))


HOLDER = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDONLY)
fcntl.flock(fd, fcntl.LOCK_EX)
print("held", flush=True)
sys.stdin.read()                    # until the test closes it, or dies
"""
MODULE_BOUND = 5.0                  # the hooks module's bound on `measure record`, in seconds
HANG = 60                           # only a blocking lock ever waits this long


class Clock:
    """`resolver`'s own clock, so a 2 s bound takes no 2 s and a loaded Mac cannot move it:
    each poll advances it, and only real seconds in `HANG` could fail a good lock."""

    def __init__(self):
        self.now = 1000.0
        self.polls = 0

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.polls += 1
        self.now += max(s, 0.05)


@pytest.fixture
def held(repo, monkeypatch):
    """The session's lock held by another process; yields the clock `resolver` now reads."""
    start(repo)
    h = subprocess.Popen([sys.executable, "-B", "-c", HOLDER, str(sdir())], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)
    assert h.stdout.readline().strip() == "held"
    clock = Clock()
    monkeypatch.setattr(resolver, "time", clock)
    yield clock
    h.stdin.close()
    h.wait(timeout=120)


def bounded(fn):
    """fn() in a thread, so a lock that blocks is a failed assert here and not a hung suite."""
    import threading
    box = {}
    t = threading.Thread(target=lambda: box.update(out=fn()), daemon=True)
    t.start()
    t.join(HANG)
    assert not t.is_alive(), "the lock blocked: it has no bound"
    return box["out"]


def test_f3_rewindow_gives_up_within_the_bound_and_writes_nothing(held):
    before = bytes_of("resolved.json", "resolved.yaml")
    assert bounded(lambda: resolver.rewindow(sdir(), 1000000)) is False
    assert held.polls > 0                               # it did wait, and then it gave up
    assert 1000.0 + resolver.LOCK_WAIT <= held.now < 1000.0 + MODULE_BOUND
    assert bytes_of("resolved.json", "resolved.yaml") == before


def test_f3_write_goes_on_past_the_bound(held, repo):
    r = resolver.resolve(repo, SID, env(), overlay={"posture": "deny"})
    state = resolver.state_dir(os.environ)
    bounded(lambda: resolver.write(r, state))
    assert held.polls > 0
    assert 1000.0 + resolver.LOCK_WAIT <= held.now < 1000.0 + MODULE_BOUND
    assert session()["posture"] == "deny"


def test_f3_the_bound_is_shorter_than_the_modules_own():
    assert 0 < resolver.LOCK_WAIT < MODULE_BOUND


def test_f4_a_wider_window_clears_the_latch_and_the_next_crossing_speaks(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", OPUS)
    tp = transcript(tmp_path, (OPUS, 150000))
    start(repo, tp)
    assert "CHECKPOINT" in said(tool(repo, tp))         # 83.3% of 180000: the first crossing
    assert meter.load(sdir())["signal"]["crossed"] is True
    assert measured(1000000)[0] == 0
    assert said(tool(repo, tp)) == ""                   # 37.5% of 400000: under, and it clears
    assert meter.load(sdir())["signal"] == {"crossed": False, "tools_since": 0}
    tp = transcript(tmp_path, (OPUS, 150000), (OPUS, 330000))
    out = tool(repo, tp)                                # 82.5% of 400000: speaks at once
    assert "CHECKPOINT" in said(out) and "82.5%" in said(out)
    assert meter.load(sdir())["signal"] == {"crossed": True, "tools_since": 0}


def test_f4_past_the_crossing_it_still_speaks_every_tenth_tool(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    tp = transcript(tmp_path, (OPUS, 150000))
    start(repo, tp)
    spoke = ["CHECKPOINT" in said(tool(repo, tp)) for _ in range(12)]
    assert spoke == [True] + [False] * 9 + [True, False]
