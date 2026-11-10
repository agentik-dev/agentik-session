"""Packet wfg: the Workflow guard and the Fable spawn rule, through the PreToolUse hook.

Fixtures under tests/fixtures/wfg/ are three of the scripts a sitting ran on 2026-11-10
(their shapes kept, their text replaced) and one fixed sweep of six Opus agents.
"""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import config, hooks

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "wfg"
SID = "test-sess-0000-1111-2222"
META = "export const meta = { name: 'x', description: 'y' }\n"
OPUS = "{ label: 'a', model: 'opus' }"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()


def guard():
    from claude_session import workflowguard
    return workflowguard


def sdir():
    import os
    d = hooks._session_dir(SID, os.environ)
    d.mkdir(parents=True, exist_ok=True)
    return d


def parent(model=None, meter=None):
    """Seed the session's two model records: model.json and the meter's."""
    for name, m in (("model.json", model), ("meter.json", meter)):
        p = sdir() / name
        if m is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps({"model": m}))


def wf(script=None, **ti):
    if script is not None:
        ti["script"] = script
    return hooks.pre_tool_use({"tool_name": "Workflow", "session_id": SID, "tool_input": ti,
                               "tool_use_id": "toolu_wfg"})


def reason(out):
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny" and hso["hookEventName"] == "PreToolUse"
    r = hso["permissionDecisionReason"]
    assert "\n" not in r and len(r) < 900, r          # one line an orchestrator can act on
    assert r.startswith("agentik-session: ")
    return r


def spawn(model=None, tool="Agent", **extra):
    ti = {"prompt": "p", "description": "d"}
    if model is not None:
        ti["model"] = model
    return hooks.pre_tool_use({"tool_name": tool, "session_id": SID, "tool_input": ti, **extra})


# --- T1, T2: the runaway's own shapes are denied; the fixed sweep passes ------------------

@pytest.mark.parametrize("name, words", [
    ("runaway_sweep_verify.js", ("lines 30, 31, 35, 37: every agent( names its model",
                                 "line 31: a list known only at run time", ".slice(0, N)")),
    ("runaway_review_fix.js", ("no spread", "line 35: a list known only at run time")),
    ("runaway_spread_model.js", ("lines 21, 24, 30, 31, 32, 42: an agent's options must be a "
                                 "plain literal, no spread",)),
])
def test_t1_the_runaways_own_shapes_are_denied(name, words):
    parent("claude-fable-5-2", "claude-fable-5-2")     # the model that night's sitting ran
    r = reason(wf((FIX / name).read_text()))
    for w in words:
        assert w in r, r


def test_t2_six_opus_agents_each_model_named_pass():
    src = (FIX / "pass_six_opus.js").read_text()
    assert guard().measure(src, "opus") == (6, [])
    for model in ("claude-opus-5-5", "claude-fable-5-2", None):
        parent(model, model)
        assert wf(src) == {}


# --- T3: the count and the ceiling -------------------------------------------------------

def lits(n):
    return META + "\n".join(f"const r{i} = await agent('p{i}', {OPUS})" for i in range(n))


def test_t3_the_ceiling_is_eight():
    g = guard()
    assert g.MAX_AGENTS == 8
    assert g.measure(lits(8)) == (8, [])
    total, why = g.measure(lits(9))
    assert total == 9 and why == ["the script can start 9 agents and the ceiling is 8: cut the "
                                  "lists, or split the work across turns"]


@pytest.mark.parametrize("body, total", [
    ("const A = ['a', 'b', 'c']\nawait parallel(A.map(a => () => agent(a, %s)))", 3),
    ("const A = ['a', 'b', 'c']\nawait pipeline(A, a => agent(a, %s), (r, a) => agent(r, %s))", 6),
    ("const r = await agent('find', %s)\n"
     "await parallel(r.items.slice(0, 5).map(f => () => agent(f, %s)))", 6),
    ("await parallel([() => agent('a', %s), () => agent('b', %s)])", 2),
    ("await parallel(['a', 'b'].map(x => () => agent(x, %s).then(r => agent(r, %s))))", 4),
    ("const A = ['a', 'b']\nconst B = ['c', 'd']\n"
     "await parallel(A.map(a => () => parallel(B.map(b => () => agent(a + b, %s)))))", 4),
    ("const x = cond ? await agent('a', %s) : await agent('b', %s)\n"
     "if (x) { await agent(`c ${await agent('d', %s)}`, %s) }", 4),
    ("log('no agent at all')", 0),
])
def test_t3_what_the_static_read_counts(body, total):
    assert guard().measure(META + body.replace("%s", OPUS)) == (total, [])


# --- T4: what it cannot bound, it denies, with the rewrite -------------------------------

@pytest.mark.parametrize("body, word", [
    ("for (const x of xs) { await agent(x, %s) }", "inside a loop"),
    ("for (const x of xs)\n  await agent(x, %s)", "inside a loop"),
    ("while (budget.remaining() > 5) { await agent('x', %s) }", "inside a loop"),
    ("do { await agent('x', %s) } while (more)", "inside a loop"),
    ("const mk = x => agent(x, %s)\nawait mk('a')", "helper function"),
    ("const mk = x =>\n  agent(x, %s)\nawait mk('a')", "helper function"),
    ("async function mk(x) { return agent(x, %s) }\nawait mk('a')", "named function"),
    ("await Promise.all(Array.from({ length: 50 }, () => agent('x', %s)))", "another call's callback"),
    ("xs.forEach(x => { agent(x, %s) })", "another call's callback"),
    ("await parallel(args.map(a => () => agent(a, %s)))", "`args` is not a fixed list"),
    ("await parallel(found.items.map(a => () => agent(a, %s)))", "known only at run time"),
    ("await parallel(A.filter(Boolean).map(a => () => agent(a, %s)))", "known only at run time"),
    ("const A = []\nfor (const x of xs) A.push(x)\nawait parallel(A.map(a => () => agent(a, %s)))",
     "`A` is not a fixed list"),
    ("const A = ['a', ...more]\nawait parallel(A.map(a => () => agent(a, %s)))", "spread"),
    ("let A = ['a']\nA = big\nawait parallel(A.map(a => () => agent(a, %s)))", "`A` is not a fixed list"),
    ("const A = ['a']\nawait parallel(xs.map(A => () => parallel(A.map(a => () => agent(a, %s)))))",
     "`A` is not a fixed list"),
    ("const T = [() => agent('a', %s)]\nawait parallel(T)\nawait parallel(T)", "never kept in a name"),
    ("const A = ['a']\nconst T = A.map(a => () => agent(a, %s))\nawait parallel(T)\nawait parallel(T)",
     "never kept in a name"),
    ("const A = ['a']\nawait pipeline(A, a => () => agent(a, %s), t => parallel([t, t, t]))",
     "never kept in a name"),
    ("await (async () => { await agent('x', %s) })()", "another call's callback"),
    ("const o = { run() { return agent('x', %s) } }\nawait o.run()", "named function"),
    ("for (const x of xs)\n  if (x)\n    await agent(x, %s)", "inside a loop"),
    ("const A = ['a']\nA.length = 50\nawait parallel(A.map(a => () => agent(a, %s)))", "`A` is not a fixed list"),
    ("await parallel(Array(50).fill(0).map(() => () => agent('x', %s)))", "known only at run time"),
    ("await workflow('saved-sweep')", "`workflow` hides agents"),
    ("await parallel(['a', 'b'].map(agent))", "other than as a direct call"),
    ("const a = agent\nawait a('x', %s)", "other than as a direct call"),
    ("await agent('say agent(x) twice', %s)", "appears inside a string"),
    ("// agent('old', {})\nawait agent('x', %s)", "appears inside a string"),
    ("await agent(`open ${'x'", "cannot read the script"),
    ("await agent('x', %s))", "cannot read the script"),
])
def test_t4_a_shape_with_no_bound_is_denied(body, word):
    total, why = guard().measure(META + body.replace("%s", OPUS))
    assert why and any(word in w for w in why), why
    assert word in reason(wf(META + body.replace("%s", OPUS)))


def test_t4_a_regex_or_a_nested_template_hides_nothing():
    g = guard()
    src = META + ("const ok = /[\"'`/]\\/x/.test(s)\nconst h = a / b / c\n"
                  f"await agent(`a ${{`b ${{await agent('in', {OPUS})}}`}} c`, {OPUS})")
    assert g.measure(src) == (2, [])


# --- T5: every agent( names its model ----------------------------------------------------

@pytest.mark.parametrize("call, word", [
    ("agent('x')", "names its model in an options literal"),
    ("agent('x', { label: 'a' })", "names its model in its own options"),
    ("agent('x', { label: 'a', ...O })", "no spread"),
    ("agent('x', O)", "names its model in an options literal"),
    ("agent('x', { label: 'a', model: M })", "must be a literal family name"),
    ("agent('x', { label: 'a', model })", "names its model in its own options"),
    ("agent('x', { label: 'a', model: 'inherit' })", "must be a literal family name"),
    ("agent('x', { label: 'a', schema: { properties: { model: 'opus' } } })",
     "names its model in its own options"),
])
def test_t5_an_agent_without_a_literal_model_is_denied(call, word):
    assert word in reason(wf(META + "const r = await " + call))


def test_t5_a_full_model_id_and_a_nested_schema_pass():
    src = META + ("await agent('x', { schema: { type: 'object', properties: { model: { type: "
                  "'string' } } }, label: `a:${k}`, model: \"claude-opus-5-5\" })")
    assert guard().measure(src) == (1, [])


# --- T6: Fable inside a workflow ---------------------------------------------------------

FABLE = META + "await agent('x', { label: '%s', model: 'fable' })"


def test_t6_fable_in_a_workflow_needs_a_fable_session_and_a_design_or_refute_label():
    parent("claude-opus-5-5", "claude-opus-5-5")
    assert "only under a Fable session (this one runs opus)" in reason(wf(FABLE % "design:api"))
    parent()
    assert "the session's model is not known" in reason(wf(FABLE % "design:api"))
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert wf(FABLE % "design:api") == {} and wf(FABLE % "refute:plan") == {}
    assert "label that starts with design or refute" in reason(wf(FABLE % "verify:1"))
    three = META + "\n".join("await agent('x', { label: 'design:%d', model: 'fable' })" % i
                             for i in range(3))
    assert "3 Fable agents and the ceiling is 2" in reason(wf(three))


# --- T7: a Fable helper starts only under a Fable session (the owner's rule) --------------

def test_t7_an_opus_session_cannot_start_a_fable_helper():
    parent("claude-opus-5-5", "claude-opus-5-5")
    for tool in ("Agent", "Task"):
        r = reason(spawn("fable", tool=tool))
        assert "a Fable helper starts only under a Fable session: this one runs opus" in r
    assert "this one runs opus" in reason(spawn("claude-fable-5-2"))
    assert spawn("opus") == {} and spawn("sonnet") == {} and spawn() == {}


def test_t7_a_fable_session_may_start_a_fable_helper():
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {} and spawn("opus") == {} and spawn() == {}
    parent("claude-fable-5-2", None)                    # SessionStart's record, no meter yet
    assert spawn("fable") == {}


def test_t7_a_switch_mid_session_counts(tmp_path):
    start = {"session_id": SID, "model": "claude-fable-5-2", "cwd": str(tmp_path),
             "hook_event_name": "SessionStart", "source": "startup"}
    hooks.session_start(start)
    assert json.loads((sdir() / "model.json").read_text())["model"] == "claude-fable-5-2"
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {}
    switch = {"session_id": SID, "hook_event_name": "PostModelSwitch",
              "from_model": "claude-fable-5-2", "to_model": "claude-opus-5-5"}
    assert hooks.HANDLERS["PostModelSwitch"](switch) == {}
    rec = json.loads((sdir() / "model.json").read_text())
    assert rec["model"] == "claude-opus-5-5" and rec["from"] == "switch"
    # the meter still holds the last Fable line: the two disagree, and the spawn is denied
    assert "the session's model is not known" in reason(spawn("fable"))
    parent("claude-opus-5-5", "claude-opus-5-5")        # the meter has read an Opus line
    assert "this one runs opus" in reason(spawn("fable"))
    # no PostModelSwitch on this CLI: the start's record is stale, the meter says Opus
    parent("claude-fable-5-2", "claude-opus-5-5")
    assert "the session's model is not known" in reason(spawn("fable"))
    # back to Fable: denied until both records say so
    hooks.HANDLERS["PostModelSwitch"]({**switch, "to_model": "claude-fable-5-2"})
    assert "retry after one tool call" in reason(spawn("fable"))
    parent("claude-fable-5-2", "claude-fable-5-2")
    assert spawn("fable") == {}


def test_t7_the_model_unknown_fails_closed_for_fable_only():
    parent()
    assert "the session's model is not known" in reason(spawn("fable"))
    assert spawn("opus") == {} and spawn() == {}
    parent("claude-fable-5-2", "claude-fable-5-2")      # a helper's own model is not the session's
    assert "not known" in reason(spawn("fable", agent_id="a1", tool_use_id="toolu_h1"))
    assert not (sdir() / "calls" / "toolu_h1").exists()         # a denied call opens no call
    hooks.HANDLERS["PostModelSwitch"]({"session_id": SID, "agent_id": "a1", "to_model": "x"})
    assert json.loads((sdir() / "model.json").read_text())["model"] == "claude-fable-5-2"


# --- T8: the script by path, by name, and a guard that fails -----------------------------

def test_t8_a_resume_by_script_path_is_read(tmp_path):
    bad = tmp_path / "bad.js"
    bad.write_text((FIX / "runaway_sweep_verify.js").read_text())
    assert "names its model" in reason(wf(scriptPath=str(bad), resumeFromRunId="wf_1"))
    good = tmp_path / "good.js"
    good.write_text((FIX / "pass_six_opus.js").read_text())
    assert wf(scriptPath=str(good), resumeFromRunId="wf_1") == {}
    for ti in ({"scriptPath": str(tmp_path / "none.js")}, {"name": "saved-sweep"}, {},
               {"scriptPath": str(tmp_path)}, {"script": 7}):
        assert "names no script the guard can read" in reason(wf(**ti))
    link = tmp_path / "link.js"
    link.symlink_to(good)
    assert "names no script the guard can read" in reason(wf(scriptPath=str(link)))
    big = tmp_path / "big.js"
    big.write_text(META + "// " + "x" * guard().MAX_SCRIPT)
    assert "names no script the guard can read" in reason(wf(scriptPath=str(big)))
    assert "over 256 KB" in reason(wf(META + "// " + "x" * guard().MAX_SCRIPT))


def test_t8_a_guard_that_raises_denies(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(guard(), "check", boom)
    r = reason(wf((FIX / "pass_six_opus.js").read_text()))
    assert "the guard failed (RuntimeError) and fails closed" in r


# --- T9: whatever the posture; other tools untouched --------------------------------------

def test_t9_the_rule_holds_under_every_posture_and_touches_no_other_tool(monkeypatch):
    from claude_session import sessionconfig
    bad = (FIX / "runaway_sweep_verify.js").read_text()
    for posture in ("off", "signal", "ask", "deny"):
        cfgs = sessionconfig.load_configs()
        cfgs["t"] = sessionconfig.SessionConfig(name="t", posture=posture)
        sessionconfig.save_configs(cfgs)
        monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "t")
        reason(wf(bad))
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG")
    assert hooks.pre_tool_use({"tool_name": "Bash", "session_id": SID,
                               "tool_input": {"command": "echo agent( model: 'fable'"}}) == {}
    assert hooks.pre_tool_use({"tool_name": "Write", "session_id": SID,
                               "tool_input": {"script": bad, "model": "fable"}}) == {}


# --- T10: the event is registered and its hook is silent ---------------------------------

def test_t10_post_model_switch_is_registered_and_silent(tmp_path):
    doc = json.loads((ROOT / "plugin" / "hooks" / "hooks.json").read_text())
    cmd = doc["hooks"]["PostModelSwitch"][0]["hooks"][0]["command"]
    assert cmd.endswith('/hooks/run" PostModelSwitch')
    assert "PostModelSwitch" in hooks.SILENT
    shim = (ROOT / "plugin" / "hooks" / "run").read_text()
    assert "PostToolBatch|PostModelSwitch)" in shim
    env = {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, "-I", str(ROOT / "plugin" / "lib" / "agentik-session"),
                        "hook", "PostModelSwitch"], env=env, capture_output=True, text=True,
                       input=json.dumps({"session_id": "sw-1", "to_model": "claude-opus-5-5"}))
    assert (r.returncode, r.stdout) == (0, ""), r
    rec = list((tmp_path / "state").rglob("model.json"))
    assert len(rec) == 1 and json.loads(rec[0].read_text())["model"] == "claude-opus-5-5"


# --- T11: the cost -----------------------------------------------------------------------

def test_t11_a_100_kb_script_costs_under_50_ms():
    src = (FIX / "pass_six_opus.js").read_text()
    pad = "Read the area's files and report each claim with the command that shows it. "
    src = src.replace("Report as verified only what you ran.", pad * 1300)
    assert 100_000 < len(src) < guard().MAX_SCRIPT
    payload = {"tool_name": "Workflow", "session_id": SID, "tool_input": {"script": src}}
    times = []
    for _ in range(9):
        t0 = time.perf_counter()
        assert hooks._spawn_rule(payload, {}) is None
        times.append(time.perf_counter() - t0)
    assert statistics.median(times) < 0.050, times
    g = guard()                                  # the worst case stays far inside the 5 s timeout
    calls = "\n".join(f"await parallel(A{i}.map(a => () => agent(`${{a}} " + "x" * 3500
                      + f"`, {OPUS})))" for i in range(g.MAX_SITES))
    wide = META + "\n".join(f"const A{i} = ['a', 'b']" for i in range(g.MAX_SITES)) + "\n" + calls
    assert 200_000 < len(wide) < g.MAX_SCRIPT
    t0 = time.perf_counter()
    total, why = g.measure(wide)
    assert total == 2 * g.MAX_SITES and "ceiling is 8" in why[0]
    assert time.perf_counter() - t0 < 0.5
    many = META + "\n".join(f"await agent('x', {OPUS})" for _ in range(g.MAX_SITES + 1))
    assert g.measure(many) == (0, ["the script holds 65 agent( calls and the guard reads 64"])
