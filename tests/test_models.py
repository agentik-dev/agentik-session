"""The model decides the window; the role decides the ceilings within it."""

import json

import pytest

from claude_session import doctor, models, resolver
from claude_session.resolver import ResolveError, resolve

SID = "test-session"
TABLE = {"fable": 1000000, "mythos": 1000000, "opus": 200000, "opus-1m": 1000000,
         "sonnet": 200000, "haiku": 200000}
K180 = {"context": 180000, "turns": 400}
K400 = {"context": 400000, "turns": 400}


# --- the table and the pick, pure ----------------------------------------------

@pytest.mark.parametrize("model,fam,window", [
    ("claude-fable-5-1", "fable", 1000000),
    ("fable", "fable", 1000000),
    ("claude-mythos-1", "mythos", 1000000),
    ("claude-opus-5-5", "opus", 200000),
    ("opus", "opus", 200000),
    ("opus[1m]", "opus", 1000000),
    ("claude-opus-5-5[1m]", "opus", 1000000),
    ("CLAUDE-OPUS-5-5[1M]", "opus", 1000000),
    ("sonnet[1m]", "sonnet", 200000),           # the table has no sonnet-1m
    ("claude-haiku-4-5-20251001", "haiku", 200000),
    ("local/default", None, None),
    ("<synthetic>", None, None),
    ("opusplan", None, None),
    (None, None, None),
])
def test_family_and_window(model, fam, window):
    assert models.family(model, TABLE) == fam
    assert models.window_of(model, TABLE) == window


@pytest.mark.parametrize("args,want", [
    # the transcript decides a family with one window, whatever the others say
    ({"observed": "claude-fable-5-1", "declared": "opus"}, (1000000, "model:claude-fable-5-1")),
    ({"observed": "claude-sonnet-5", "session": "claude-opus-5-5[1m]"},
     (200000, "model:claude-sonnet-5")),
    # opus has two windows: the transcript names the family, the session its window
    ({"observed": "claude-opus-5-5", "session": "claude-opus-5-5[1m]", "declared": "opus"},
     (1000000, "session:claude-opus-5-5[1m]")),
    ({"observed": "claude-opus-5-5", "session": "claude-opus-5-5", "declared": "opus[1m]"},
     (200000, "session:claude-opus-5-5")),
    # no session model: the declared, then the configured, the first of the same family
    ({"observed": "claude-opus-5-5", "declared": "opus[1m]"}, (1000000, "declared:opus[1m]")),
    ({"observed": "claude-opus-5-5", "declared": "fable", "configured": ["opus[1m]"]},
     (1000000, "configured:opus[1m]")),
    ({"observed": "claude-opus-5-5", "declared": "fable"}, (200000, "model:claude-opus-5-5")),
    # no model read yet, or one the table does not know: the first the table knows
    ({"declared": "fable"}, (1000000, "declared:fable")),
    ({"observed": "<synthetic>", "declared": "opus[1m]"}, (1000000, "declared:opus[1m]")),
    ({"observed": "local/default", "declared": "local/default", "configured": ["sonnet"]},
     (200000, "configured:sonnet")),
    ({}, (200000, "default")),
])
def test_pick(args, want):
    assert models.pick(TABLE, **args) == want


def test_window_class():
    assert [models.window_class(w) for w in (200000, 999999, 1000000, 2000000, None)] == \
        ["200k", "200k", "1m", "1m", "200k"]


def test_configured_reads_the_env_then_the_settings(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "repo"
    (home / ".claude").mkdir(parents=True)
    (cwd / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text(json.dumps({"model": "opus"}))
    (cwd / ".claude/settings.json").write_text(json.dumps({"model": "opus[1m]"}))
    (cwd / ".claude/settings.local.json").write_text("not json")
    env = {"HOME": str(home), "ANTHROPIC_MODEL": "fable"}
    assert models.configured(env, cwd) == ["fable", "opus[1m]", "opus"]
    assert models.configured({"HOME": str(home)}, tmp_path) == ["opus"]


# --- the resolver: roles, windows, precedence ---------------------------------

@pytest.fixture
def world(tmp_path):
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state)}

    def put(layer, text):
        path = {"user": home / ".claude" / resolver.REPO_DIR.name / "profiles.yaml",
                "repo": repo / resolver.REPO_DIR / "config.yaml",
                "local": repo / resolver.REPO_DIR / "config.local.yaml"}[layer]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return env, repo, put


def session(world, **kw):
    env, repo, _ = world
    return resolve(repo, SID, env, overlay=kw.pop("overlay", {}), **kw).sections["session"]


def test_orchestrator_on_fable_is_1m_at_400k(world):
    s = session(world, profile="orchestrator")
    assert (s["model"], s["window"], s["ceilings"]) == ("fable", 1000000, K400)
    assert s["window_source"] == "declared:fable"
    assert s["limits_source"] == "role:orchestrator window:1000000"
    assert s["windows"]["200k"] == {**K180, "source": "role:orchestrator"}


def test_orchestrator_opus_on_opus_1m_is_400k(world):
    s = session(world, profile="orchestrator-opus")
    assert (s["model"], s["window"], s["ceilings"]) == ("opus[1m]", 1000000, K400)
    s = session(world, profile="orchestrator-opus", session_model="claude-opus-5-5[1m]")
    assert (s["window"], s["ceilings"]) == (1000000, K400)
    assert s["window_source"] == "session:claude-opus-5-5[1m]"
    assert s["session_model"] == "claude-opus-5-5[1m]"


def test_orchestrator_opus_on_opus_200k_is_180k(world):
    s = session(world, profile="orchestrator-opus", session_model="claude-opus-5-5")
    assert (s["window"], s["ceilings"]) == (200000, K180)
    assert s["limits_source"] == "role:orchestrator-opus window:200000"
    world[2]("repo", "session: {profile: orchestrator-opus, model: opus}\n")
    s = session(world)
    assert (s["window"], s["ceilings"], s["window_source"]) == (200000, K180, "declared:opus")


@pytest.mark.parametrize("name", ["builder", "frontier", "balanced", "review", "packets",
                                  "local", "local-only", "scratch"])
def test_every_other_role_keeps_180k_on_a_1m_model(world, name):
    s = session(world, profile=name, session_model="claude-fable-5-1")
    assert (s["window"], s["ceilings"]) == (1000000, K180)
    assert s["windows"]["1m"]["context"] == 180000


def test_builder_on_1m_names_the_defaults(world):
    s = session(world, profile="builder", session_model="opus[1m]")
    assert s["limits_source"] == "defaults window:1000000"


def test_a_user_layer_that_sets_ceilings_wins_on_both_windows(world):
    world[2]("user", "defaults:\n  ceilings: {context: 250000}\n")
    s = session(world, profile="orchestrator")
    assert s["ceilings"] == {"context": 250000, "turns": 400}
    assert s["limits_source"] == "user window:1000000"
    assert s["windows"]["200k"] == {"context": 250000, "turns": 400, "source": "user"}


def test_a_project_layer_wins_over_the_launched_role(world):
    world[2]("repo", "session:\n  ceilings: {turns: 120}\n")
    world[2]("local", "session:\n  ceilings_1m: {context: 300000}\n")
    s = session(world, profile="orchestrator")                 # the launch layer
    assert s["ceilings"] == {"context": 300000, "turns": 120}
    assert s["limits_source"] == "config.local.yaml window:1000000"
    assert s["windows"]["200k"] == {"context": 180000, "turns": 120, "source": "config.yaml"}


def test_the_overlay_is_a_user_layer(world):
    s = session(world, profile="orchestrator", overlay={"ceilings": {"context": 200000}})
    assert s["ceilings"]["context"] == 200000 and s["limits_source"] == "overlay window:1000000"


def test_the_turn_cap_is_last_on_both_windows(world):
    env, repo, _ = world
    env["CLAUDE_SESSION_MAX_TURNS"] = "80"
    s = resolve(repo, SID, env, profile="orchestrator", overlay={}).sections["session"]
    assert s["ceilings"] == {"context": 400000, "turns": 80}
    assert s["ceilings_source"] == resolver.MAX_TURNS_VAR
    assert s["windows"]["200k"]["turns"] == 80


def test_an_unknown_model_falls_back_to_the_declared(world):
    s = session(world, profile="orchestrator", session_model="some/local-model")
    assert (s["window"], s["window_source"]) == (1000000, "declared:fable")


def test_the_configured_model_decides_when_the_declared_cannot(world):
    env, repo, _ = world
    env["ANTHROPIC_MODEL"] = "claude-fable-5-1"
    s = resolve(repo, SID, env, profile="local-only", overlay={}).sections["session"]
    assert (s["window"], s["window_source"]) == (1000000, "configured:claude-fable-5-1")
    assert s["configured_models"] == ["claude-fable-5-1"]


def test_window_is_no_longer_an_input(world):
    world[2]("repo", "session: {window: 1000000}\n")
    env, repo, _ = world
    r = resolve(repo, SID, env, overlay={})
    assert r.sections["session"]["window"] == 200000
    assert r.unknown == ["config.yaml: session.window"]


def test_the_user_extends_the_models_table(world):
    world[2]("user", "models:\n  sonnet-1m: 1000000\n")
    s = session(world, profile="orchestrator", session_model="sonnet[1m]")
    assert (s["window"], s["ceilings"]) == (1000000, K400)


@pytest.mark.parametrize("layer,text,msg", [
    ("user", "models:\n  opus: big\n", "models.opus"),
    ("repo", "session:\n  ceilings_1m: {context: 0}\n", "ceilings_1m.context"),
    ("local", "session: {ceilings: 5}\n", "ceilings must be a mapping"),
])
def test_refusals(world, layer, text, msg):
    world[2](layer, text)
    with pytest.raises(ResolveError, match=msg):
        session(world, profile="orchestrator")


def test_the_yaml_twin_carries_the_windows(world):
    env, repo, _ = world
    r = resolve(repo, SID, env, profile="orchestrator-opus", overlay={})
    path = resolver.write(r, resolver.state_dir(env))
    from claude_session.yamlsubset import load
    assert load(path.with_suffix(".yaml").read_text()) == json.loads(path.read_text())


def test_doctor_resolves_the_new_profiles(world):
    env, repo, _ = world
    c = doctor._check_profiles(env, repo)
    assert c.ok and "orchestrator" in c.detail and "orchestrator-opus" in c.detail
    _, profiles = resolver.load_profiles(env)
    for name in ("orchestrator", "orchestrator-opus"):
        p = profiles[name]
        assert (p["effort"], p["subagents"], p["posture"]) == ("xhigh", "opus", "signal")
        assert p["builders"] == {"model": "opus", "max_concurrent": 3}
        assert p["charter"] == {"required": True} and "respawns" in p["description"]


# --- the meter: the window re-picked from the model it reads -------------------

MSID = "meter-sess-1"


def transcript(tmp_path, model, context=1000, turns=1):
    """`turns` assistant lines on `model`, the last at `context` occupancy."""
    rows = []
    for i in range(turns):
        rows.append({"type": "assistant", "requestId": f"r{i}", "timestamp": "2026-09-28T10:00:00Z",
                     "message": {"id": f"m{i}", "model": model,
                                 "content": [{"type": "text", "text": "<placeholder>"}],
                                 "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                           "cache_read_input_tokens":
                                               context if i == turns - 1 else 1000,
                                           "output_tokens": 7}}})
    p = tmp_path / "t.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def sitting(tmp_path, monkeypatch, profile, observed, session_model=None, context=1000,
            extra=None):
    """SessionStart (the payload's model when given), then one PostToolUse: meter.json."""
    import os
    from claude_session import hooks, meter
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    env = {**os.environ, "CLAUDE_SESSION_PROFILE": profile, **(extra or {})}
    p = transcript(tmp_path, observed, context)
    payload = {"session_id": MSID, "cwd": str(tmp_path), "transcript_path": str(p)}
    if session_model:
        payload["model"] = session_model
    hooks.session_start(payload, env)
    hooks.post_tool_use({"session_id": MSID, "transcript_path": str(p), "tool_name": "Read"}, env)
    return meter.load(resolver.session_dir(resolver.state_dir(env), MSID))


def test_meter_fable_under_orchestrator_is_1m_400k(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator", "claude-fable-5-1", context=350000)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (1000000, K400, 87.5)
    assert m["window_source"] == "model:claude-fable-5-1"
    assert m["limits_source"] == "role:orchestrator window:1000000"


def test_meter_opus_1m_under_orchestrator_opus_is_400k(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5",
                "claude-opus-5-5[1m]", context=300000)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (1000000, K400, 75.0)
    assert m["window_source"] == "session:claude-opus-5-5[1m]"
    assert m["limits_source"] == "role:orchestrator-opus window:1000000"
    assert m["zone"] == "clear"


def test_meter_opus_200k_under_orchestrator_opus_is_180k(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5",
                "claude-opus-5-5", context=144000)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (200000, K180, 80.0)
    assert m["limits_source"] == "role:orchestrator-opus window:200000"


def test_meter_builder_on_a_1m_model_keeps_180k(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "builder", "claude-fable-5-1", context=144000)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (1000000, K180, 80.0)
    assert m["limits_source"] == "defaults window:1000000"


# F1: a helper a sitting spawns inherits CLAUDE_SESSION_PROFILE; the helper rule marks
# it CLAUDE_SESSION_HELPER=1, and it is metered as a builder, never as the inherited role.
HELPER = {"CLAUDE_SESSION_HELPER": "1", "CLAUDE_SESSION_DEPTH": "1"}


def test_meter_a_helper_of_an_orchestrator_is_a_builder_on_1m(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator", "claude-fable-5-1", context=144000,
                extra=HELPER)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (1000000, K180, 80.0)
    assert m["limits_source"] == "defaults window:1000000"


def test_meter_a_plain_opus_helper_of_orchestrator_opus_reads_200k(tmp_path, monkeypatch):
    # the -p SessionStart payload carries no model: the declared model decides the window
    m = sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5", context=144000,
                extra=HELPER)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (200000, K180, 80.0)
    assert m["window_source"] == "declared:opus"
    assert m["limits_source"] == "defaults window:200000"


def test_meter_unknown_model_uses_the_declared(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator-opus", "<synthetic>")
    assert (m["window"], m["ceilings"]) == (1000000, K400)
    assert m["window_source"] == "declared:opus[1m]"


def test_meter_user_layer_wins(tmp_path, monkeypatch):
    import os
    user = os.path.join(os.environ["HOME"], ".claude", resolver.REPO_DIR.name, "profiles.yaml")
    os.makedirs(os.path.dirname(user))
    with open(user, "w") as f:
        f.write("profiles:\n  orchestrator:\n    ceilings: {context: 250000}\n")
    m = sitting(tmp_path, monkeypatch, "orchestrator", "claude-fable-5-1")
    assert m["ceilings"] == {"context": 250000, "turns": 400}
    assert m["limits_source"] == "user window:1000000"


def test_meter_follows_a_model_switch(tmp_path, monkeypatch):
    # declared fable, the transcript on opus with no session model: opus's own 200k
    m = sitting(tmp_path, monkeypatch, "orchestrator", "claude-opus-5-5")
    assert (m["window"], m["ceilings"]) == (200000, K180)
    assert m["window_source"] == "model:claude-opus-5-5"
    assert m["limits_source"] == "role:orchestrator window:200000"


def test_meter_until_a_model_is_known_uses_the_declared(tmp_path):
    from claude_session import meter
    env = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state")}
    s = resolve(tmp_path, SID, env, profile="orchestrator-opus", overlay={}).sections["session"]
    lim = {k: s[k] for k in meter.LIMIT_KEYS}
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    m = meter.parse(empty, {}, lim)
    assert (m.window, m.ceilings, m.window_source) == (1000000, K400, "declared:opus[1m]")
    assert m.limits_source in meter.one_line(m.as_dict())


def test_meter_without_windows_keeps_the_limits_given(tmp_path):
    from claude_session import meter
    p = transcript(tmp_path, "claude-fable-5-1")
    m = meter.parse(p, {}, {"ceilings": {"context": 288000, "turns": 400}})
    assert (m.window, m.ceilings["context"]) == (200000, 288000)
    assert m.limits_source == "default window:200000"


# Round 2 F1: `agentik session set model X` (the overlay) is newer than the SessionStart
# payload's model, so it moves the window; the next SessionStart's model is newer again.
def _set(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        assert cli.main(list(argv)) == 0


def _tool(tmp_path, context, model="claude-opus-5-5"):
    """A new transcript file at `context`, one PostToolUse on it: meter.json."""
    import os
    from claude_session import hooks, meter
    d = tmp_path / f"t{len(list(tmp_path.glob('t[0-9]*')))}"
    d.mkdir()
    p = transcript(d, model, context)
    hooks.post_tool_use({"session_id": MSID, "transcript_path": str(p), "tool_name": "Read"},
                        dict(os.environ))
    return meter.load(resolver.session_dir(resolver.state_dir(os.environ), MSID))


@pytest.mark.parametrize("start,to,context,want", [
    ("claude-opus-5-5[1m]", "opus", 190000, (200000, K180, 105.6, "declared:opus")),
    ("claude-opus-5-5", "opus[1m]", 300000, (1000000, K400, 75.0, "declared:opus[1m]")),
])
def test_meter_a_model_set_mid_session_moves_the_window(tmp_path, monkeypatch, start, to,
                                                       context, want):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", MSID)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5", start)
    _set("set", "model", to)
    m = _tool(tmp_path, context)
    assert (m["window"], m["ceilings"], m["pct_context"], m["window_source"]) == want
    s = json.loads((resolver.session_dir(resolver.state_dir(__import__("os").environ), MSID)
                    / "resolved.json").read_text())["session"]
    assert (s["model"], s["window"], s["window_source"]) == (to, want[0], want[3])
    _set("set", "effort", "high")          # a later `set` keeps the model it was given
    assert _tool(tmp_path, context)["window_source"] == want[3]


def test_meter_the_next_session_start_model_is_newer_than_a_set(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", MSID)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "orchestrator-opus")
    sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5", "claude-opus-5-5")
    _set("set", "model", "opus[1m]")
    # a compact after a plain `/model opus`: the payload names the model in force
    m = sitting(tmp_path, monkeypatch, "orchestrator-opus", "claude-opus-5-5",
                "claude-opus-5-5", context=144000)
    assert (m["window"], m["ceilings"], m["window_source"]) == (
        200000, K180, "session:claude-opus-5-5")


# Round 1 F2: Claude Code writes a `<synthetic>` assistant line (zero usage) on an API
# error. It, or any id the table does not know, never replaces the last known model,
# and a zero-occupancy one never replaces the last context.
def _append(p, model, context=0, n=0):
    row = {"type": "assistant", "requestId": f"rx{n}", "timestamp": "2026-09-28T10:05:00Z",
           "message": {"id": f"mx{n}", "model": model,
                       "content": [{"type": "text", "text": "<placeholder>"}],
                       "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                 "cache_read_input_tokens": context, "output_tokens": 0}}}
    with open(p, "a") as f:
        f.write(json.dumps(row) + "\n")


def _again(p):
    import os
    from claude_session import hooks, meter
    hooks.post_tool_use({"session_id": MSID, "transcript_path": str(p), "tool_name": "Read"},
                        dict(os.environ))
    return meter.load(resolver.session_dir(resolver.state_dir(os.environ), MSID))


def test_meter_a_synthetic_line_keeps_the_last_real_model(tmp_path, monkeypatch):
    m = sitting(tmp_path, monkeypatch, "orchestrator", "claude-opus-5-5", context=150000)
    want = ("claude-opus-5-5", 200000, K180, 150000, "model:claude-opus-5-5")
    assert (m["model"], m["window"], m["ceilings"], m["context"], m["window_source"]) == want
    _append(tmp_path / "t.jsonl", "<synthetic>")
    m = _again(tmp_path / "t.jsonl")
    assert (m["model"], m["window"], m["ceilings"], m["context"], m["window_source"]) == want
    assert m["turns"] == 2                 # it is still a line of the transcript


@pytest.mark.parametrize("context,want_context", [(0, 150000), (120000, 120000)])
def test_meter_an_unknown_id_keeps_the_model_not_a_real_context(tmp_path, monkeypatch,
                                                                context, want_context):
    sitting(tmp_path, monkeypatch, "orchestrator", "claude-opus-5-5", context=150000)
    _append(tmp_path / "t.jsonl", "local/default", context)
    m = _again(tmp_path / "t.jsonl")
    assert (m["model"], m["window"], m["context"]) == ("claude-opus-5-5", 200000, want_context)


def test_meter_a_synthetic_line_without_a_table(tmp_path):
    from claude_session import meter
    p = transcript(tmp_path, "claude-fable-5-1", 150000)
    _append(p, "<synthetic>")
    m = meter.parse(p, {}, {"ceilings": {"context": 180000, "turns": 400}})
    assert (m.model, m.context) == ("claude-fable-5-1", 150000)
