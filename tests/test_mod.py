"""Packet M1 (mod-r1 S1): `mod start`, mod.json, the `mod:` line in status and doctor,
and the band module's static criteria (mod-r1 §7: 1, 2, 3, 5, 7)."""
import ast
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import __version__, cli, doctor, hooks, resolver

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / "plugin" / "hooks"
SID = "mod-sess-0000-1111"
CLASSIC = {   # the pin's (1204d4c) classic block: event -> (matcher, timeout); S1 adds only `modules`
    "SessionStart": ("", 10), "PreToolUse": ("*", 5), "PostToolUse": ("*", 5),
    "PostToolUseFailure": ("*", 5), "PostToolBatch": (None, 5), "UserPromptSubmit": (None, 5),
    "Stop": (None, 5), "StopFailure": (None, 5), "SessionEnd": (None, 15),
    "PreCompact": (None, 5),          # S34 adds StopFailure
}

# The three sibling plugins, spelled in pieces so the hygiene scan of this file finds none.
SIBLINGS = "|".join(["re" + "speak", "deci" + "sions", "agent-" + "relay"])


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    return tmp_path / "xdg"


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def _files(root: Path) -> list:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def _metered(tmp_path):
    """A session the classic hooks resolved and metered, as a live session leaves it."""
    env = dict(os.environ)
    repo = tmp_path / "repo"
    repo.mkdir()
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, env)
    hooks.post_tool_use({"session_id": SID, "transcript_path":
                         str(ROOT / "tests/fixtures/meter/under-80.jsonl")}, env)
    return resolver.session_dir(resolver.state_dir(env), SID)


def test_mod_start_writes_mod_json_and_prints_the_dir(state, tmp_path):
    sdir = _metered(tmp_path)
    rc, out, err = run("mod", "start", "--session", SID)
    assert (rc, err) == (0, "")
    assert json.loads(out) == {"dir": str(sdir.resolve())}
    m = json.loads((sdir / "mod.json").read_text())
    assert set(m) == {"at", "version"} and m["version"] == __version__
    assert not list(sdir.glob("*.tmp"))


@pytest.mark.parametrize("bad", ["../escape", "a b", "x/y", "", "a" * 129, "ok\n"])
def test_mod_start_bad_id_exits_2_and_writes_nothing(state, bad):
    before = _files(state)
    rc, out, err = run("mod", "start", "--session", bad)
    assert rc == 2 and out == ""
    assert len(err.strip().splitlines()) == 1
    assert _files(state) == before


def test_mod_start_absent_session_exits_1_and_creates_nothing(state):
    before = _files(state)
    rc, out, err = run("mod", "start", "--session", "no-such-session")
    assert (rc, out) == (1, "")
    assert err.strip() == "agentik-session: no session no-such-session"
    assert _files(state) == before



def test_mod_start_concurrent_runs_all_exit_0_and_leave_one_mod_json(state, tmp_path):
    """Fix round 3: a fixed `mod.json.tmp` lost concurrent runs to FileNotFoundError."""
    sdir = _metered(tmp_path)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    procs = [subprocess.Popen([sys.executable, "-B", "-m", "claude_session", "mod", "start",
                               "--session", SID], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) for _ in range(16)]
    results = [(p.wait(60), p.communicate()[1].decode()[-200:]) for p in procs]
    assert [rc for rc, _ in results] == [0] * 16, results
    assert set(json.loads((sdir / "mod.json").read_text())) == {"at", "version"}
    assert sorted(p.name for p in sdir.iterdir() if "mod.json" in p.name) == ["mod.json"]


@pytest.mark.parametrize("at", ["2026-10-12T12:00:00", "not a time", None])
def test_mod_json_at_of_unknown_age_never_crashes(state, tmp_path, at):
    """Fix round 4: an `at` with no timezone crashed status and doctor (TypeError)."""
    sdir = _metered(tmp_path)
    (sdir / "mod.json").write_text(json.dumps({"at": at, "version": "x"}))
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[-1] == "mod: seen, age unknown"
    c = doctor._check_mod(dict(os.environ))
    assert (c.ok, c.warn) == (True, True) and c.detail.startswith("seen, age unknown")

def test_status_prints_mod_not_seen_then_seen(state, tmp_path):
    _metered(tmp_path)
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[-1] == "mod: not seen"
    run("mod", "start", "--session", SID)
    rc, out, _ = run("status")
    assert rc == 0 and re.fullmatch(r"mod: seen \d+s ago", out.splitlines()[-1])
    rc, out, _ = run("status", "--json")
    assert "mod" not in json.loads(out)          # --json stays meter.json


def test_doctor_mod_row_is_ok_or_warn_never_fail(state, tmp_path):
    _metered(tmp_path)
    env = dict(os.environ)
    c = doctor._check_mod(env)
    assert (c.name, c.ok, c.warn) == ("mod", True, True) and "not seen" in c.detail
    assert doctor.render(doctor.Report([c])).splitlines()[0].startswith("warn mod ")
    run("mod", "start", "--session", SID)
    c = doctor._check_mod(env)
    assert (c.ok, c.warn) == (True, False) and re.match(r"seen \d+s ago", c.detail)
    assert doctor.render(doctor.Report([c])).splitlines()[0].startswith("ok   mod ")


def test_criterion_1_hooks_json_keeps_the_classic_block_and_adds_only_modules():
    doc = json.loads((HOOKS_DIR / "hooks.json").read_text())
    assert set(doc) == {"hooks", "modules"} and doc["modules"] == ["./session.ts"]
    assert set(doc["hooks"]) == set(CLASSIC)
    for event, (matcher, timeout) in CLASSIC.items():
        [entry] = doc["hooks"][event]
        assert entry.get("matcher") == matcher
        assert entry["hooks"] == [{"type": "command", "timeout": timeout,
                                   "command": f"${{CLAUDE_PLUGIN_ROOT}}/hooks/run {event}"}]


def _module_lines():
    """(file, line) over plugin/hooks/*.ts; skips when the module is absent (criterion 5)."""
    files = sorted(HOOKS_DIR.glob("*.ts"))
    if not files:
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return [(f.name, ln) for f in files for ln in f.read_text().splitlines()]


def test_criterion_2_the_module_writes_nothing_but_a_pref_key():
    hits = [(f, ln) for f, ln in _module_lines() if re.search(r"fs\.write|store\.set", ln)]
    assert all("pref." in ln for _, ln in hits), hits


def test_criterion_7_the_module_names_no_sibling():
    hits = [(f, ln) for f, ln in _module_lines()
            if re.search(SIBLINGS, ln)]
    assert hits == []


BARRED = ("measure", "mod")


def _reads_measure_or_mod(text: str) -> list:
    """What in `text` names measure.json or mod.json, or imports measure or mod in any form
    (relative, absolute, aliased, parenthesised, or by a module-name string), criterion 3."""
    hits = re.findall(r"\b(?:measure|mod)\.json\b", text)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            base = (node.module or "").split(".") if node.module else []
            ours = node.level > 0 or base[:1] == ["claude_session"]
            paths = [base] + [base + [a.name] for a in node.names]
            if ours and any(set(p[1:] if p[:1] == ["claude_session"] else p) & set(BARRED)
                            for p in paths):
                hits.append(ast.unparse(node))
        elif isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name.split(".")[:1] == ["claude_session"]
                     and set(a.name.split(".")[1:]) & set(BARRED)]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.fullmatch(r"(?:claude_session)?\.(?:measure|mod)", node.value):
                hits.append(node.value)
    return hits


@pytest.mark.parametrize("text", [
    "from .measure import MEASURE",
    "from .measure import load as _e",
    "from claude_session.measure import drift",
    "from . import measure",
    "from . import (meter,\n    measure as m)",
    "from claude_session import mod",
    "from .mod import MOD",
    "import claude_session.measure",
    "import claude_session.mod as m",
    "X = 'measure.json'",
    "p = d / \"mod.json\"",
    "importlib.import_module('.measure', __package__)",
])
def test_criterion_3_the_scan_catches_every_form(text):
    assert _reads_measure_or_mod(text), text


@pytest.mark.parametrize("text", [
    "from . import meter, resolver", "from .meter import load", "import math, os",
    "x = 'measured'", "from .hooks import _SID", "import claude_session.meter",
])
def test_criterion_3_the_scan_passes_what_is_not_them(text):
    assert _reads_measure_or_mod(text) == [], text


@pytest.mark.parametrize("name", ["chain.py", "hooks.py", "budget.py"])
def test_criterion_3_the_three_never_open_measure_or_mod_json(name):
    text = (ROOT / "plugin" / "lib" / "claude_session" / name).read_text()
    assert "measure.json" not in text and "mod.json" not in text
    # M2's fix round: any import from .measure/.mod or claude_session's, in any form
    assert _reads_measure_or_mod(text) == []
    assert not re.search(r"\bmod\.(MOD|load|seen|line|start)\b", text)
    assert not re.search(r"\bmeasure\.(MEASURE|load|parse|record|drift|line)\b", text)


# Packet S27b ruling 4: band.json is display only. The prompt hook reads it for its line;
# nothing that decides (the chain, the budget, the verdict, the spawn gate) names it.
def test_criterion_3_band_json_is_display_only():
    import inspect
    from claude_session import admission
    pat = re.compile(r"band\.json|\bBAND\b|read_band|band_line|_admission_line|\bband\(")
    for name in ("chain.py", "budget.py"):
        assert not pat.search((ROOT / "plugin" / "lib" / "claude_session" / name).read_text()), name
    for fn in (admission.decide, admission.project, admission.fit, admission._stale_in_flight,
               hooks.pre_tool_use):
        assert not pat.search(inspect.getsource(fn)), fn.__name__
    assert "_admission_line(sid)" in inspect.getsource(hooks.user_prompt_submit)   # S35: its account
    assert "read_band" in inspect.getsource(hooks._admission_line)


def test_criterion_5_no_test_or_module_but_this_one_reads_the_ts_files():
    pat = re.compile(r"\.ts[\"']")     # a string literal naming a .ts file: a reader
    readers = [p.name for p in [*(ROOT / "tests").glob("*.py"), *(ROOT / "plugin" / "lib" / "claude_session").glob("*.py")]
               if p.name != "test_mod.py" and pat.search(p.read_text())]
    assert readers == []
    this = Path(__file__).read_text()
    assert 'pytest.skip("no plugin/hooks/*.ts' in this      # this file's readers skip without them


# ---- Packet S41: the model and the window, in the band and in `status` ----------------

def _facts_fixture() -> tuple:
    """The one fixture both twins read (session.test.ts's FACTS_METER, FACTS_MEASURE and
    FACTS_LINE)."""
    p = HOOKS_DIR / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    text = p.read_text()
    get = lambda name: re.search(rf"^const {name} = '(.*)'$", text, re.M).group(1)  # noqa: E731
    return json.loads(get("FACTS_METER")), json.loads(get("FACTS_MEASURE")), get("FACTS_LINE")


def test_s41_python_draws_the_module_s_facts_fixture():
    from claude_session import mod
    m, x, line = _facts_fixture()
    assert line == "opus 5.5 · 200k (engine 1M)"
    assert mod.facts(m, x) == line


@pytest.mark.parametrize("model,name", [
    ("claude-opus-5-5", "opus 5.5"), ("claude-fable-5-1", "fable 5.1"),
    ("claude-sonnet-5-5", "sonnet 5.5"), ("claude-haiku-4-5-20251001", "haiku 4.5"),
    ("local-model", "local-model"), ("claude-opus-5-5[1m]", "claude-opus-5-5[1m]"),
    ("a-local-model-with-a-long-name-v2", "a-local-model-with-a-lo…"),
    ("", None), (None, None), (7, None), (["x"], None), (True, None),
])
def test_s41_model_name(model, name):
    from claude_session import mod
    assert mod.model_name(model) == name
    assert name is None or len(name) <= 24


@pytest.mark.parametrize("window,label", [
    (200000, "200k"), (1000000, "1M"), (128000, "128k"), (2000000, "2000k"), (200500.0, "200k"),
    (0, None), (-1, None), (None, None), ("200000", None), (True, None), (float("nan"), None),
    (float("inf"), None),
])
def test_s41_window_label(window, label):
    from claude_session import mod
    assert mod.window_label(window) == label


@pytest.mark.parametrize("meter,measure,text", [
    ({"model": "claude-opus-5-5", "window": 200000}, None, "opus 5.5 · 200k"),
    ({"model": "claude-opus-5-5", "window": 200000}, {"context": {"window": 200000}}, "opus 5.5 · 200k"),
    ({"model": "claude-opus-5-5", "window": 200000}, {"context": {"window": 200400}}, "opus 5.5 · 200k"),
    ({"model": "claude-opus-5-5", "window": 200000}, {"context": {"window": 1000000}},
     "opus 5.5 · 200k (engine 1M)"),
    ({"model": "claude-opus-5-5"}, {"context": {"window": 1000000}}, "opus 5.5 · engine 1M"),
    ({"window": 1000000}, {"context": None}, "1M"),
    ({"model": 5, "window": "x"}, {"context": "x"}, None),
    ({}, None, None), (None, None, None), ("not a dict", ["x"], None),
])
def test_s41_facts(meter, measure, text):
    from claude_session import mod
    assert mod.facts(meter, measure) == text


def _s41_meter(sdir, **over):
    d = json.loads((sdir / "meter.json").read_text())
    d.update(over)
    (sdir / "meter.json").write_text(json.dumps(d))


def test_s41_status_prints_the_model_line_between_measure_and_mod(state, tmp_path):
    sdir = _metered(tmp_path)
    _s41_meter(sdir, model="claude-opus-5-5", window=200000, window_source="session:claude-opus-5-5")
    rc, out, _ = run("status")
    lines = out.splitlines()
    assert rc == 0 and lines[1].startswith("measure: ") and lines[-1].startswith("mod: "), out
    assert lines[2] == "model: opus 5.5 · 200k; claude-opus-5-5, window from session:claude-opus-5-5"
    (sdir / "measure.json").write_text(json.dumps(
        {"at": "2026-10-30T10:00:00+00:00", "context": {"tokens": 9, "window": 1000000}}))
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[2] == ("model: opus 5.5 · 200k (engine 1M); claude-opus-5-5, "
                                               "window from session:claude-opus-5-5"), out
    rc, out, _ = run("status", "--json")
    assert json.loads(out)["model"] == "claude-opus-5-5"            # --json stays meter.json


def test_s41_status_model_line_leaves_out_what_is_missing(state, tmp_path):
    sdir = _metered(tmp_path)
    _s41_meter(sdir, model=None, window=None, window_source=None)
    (sdir / "measure.json").write_text("{torn")
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[2] == "model: none", out
    _s41_meter(sdir, model=None, window=1000000, window_source="model:claude-fable-5-1")
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[2] == "model: 1M; window from model:claude-fable-5-1", out


# ---- Packet S41 Amendment 1: the cases both twins read ------------------------------------

def _twin_cases(name: str) -> list:
    """One of session.test.ts's case lists (NAME_CASES, WINDOW_CASES), [input, text] each."""
    p = HOOKS_DIR / ("session.test." + "ts")
    if not p.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    return json.loads(re.search(rf"^const {name} = '(.*)'$", p.read_text(), re.M).group(1))


def test_s41_a1_python_names_the_module_s_model_cases():
    from claude_session import mod
    cases = _twin_cases("NAME_CASES")
    assert ["claude-opus-4-20250514", "claude-opus-4-20250514"] in cases      # no 8-digit minor
    assert ["claude-opus-５-５", "claude-opus-５-５"] in cases  # ASCII digits only
    assert [mod.model_name(v) for v, _ in cases] == [n for _, n in cases]


def test_s41_a1_python_labels_the_module_s_window_cases():
    from claude_session import mod
    cases = _twin_cases("WINDOW_CASES")
    assert [500, "500"] in cases and [0.5, None] in cases
    assert [mod.window_label(v) for v, _ in cases] == [t for _, t in cases]


def test_s41_a1_an_int_past_a_double_is_no_part_and_status_prints(state, tmp_path):
    from claude_session import mod
    huge = 10 ** 400
    assert mod.window_label(huge) is None
    assert mod.facts({"model": "claude-opus-5-5", "window": huge},
                     {"context": {"window": huge}}) == "opus 5.5"
    sdir = _metered(tmp_path)
    _s41_meter(sdir, model="claude-opus-5-5", window=huge, window_source="session:claude-opus-5-5")
    rc, out, err = run("status")
    assert rc == 0 and "Traceback" not in err, err
    assert out.splitlines()[2] == "model: opus 5.5; claude-opus-5-5, window from session:claude-opus-5-5", out
