"""S28: a relay child's model, from the launcher's env (the observer's F14).

Under `claude -p` the SessionStart payload carries no `model`, so a relay child on
`claude-opus-5-5[1m]` resolved `declared:opus` and metered at 200k. The relay's spawn
line exports `CLAUDE_SESSION_MODEL=<its --model>` (agent-relay AR74); `session_start`
reads it when the payload has none, never under `CLAUDE_SESSION_HELPER=1`, and
`resolved.json` says which source named the session model.
"""

import json

import pytest

from claude_session import hooks, meter, resolver

SID = "test-session"                  # one of conftest's sentinel ids
ENV_MODEL = "claude-opus-5-5[1m]"
K180 = {"context": 180000, "turns": 400}
K400 = {"context": 400000, "turns": 400}


@pytest.fixture(autouse=True)
def no_launcher_model(monkeypatch):
    """A sitting that runs the suite may carry the variable itself; no test reads it."""
    monkeypatch.delenv("CLAUDE_SESSION_MODEL", raising=False)


@pytest.fixture
def world(tmp_path):
    """A temporary HOME, state dir and repo; `layer` writes the repo's config.yaml."""
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state),
           "CLAUDE_SESSION_PROFILE": "builder"}

    def layer():
        path = repo / resolver.REPO_DIR / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("session:\n  ceilings_1m: {context: 400000}\n")
    return env, repo, layer


def transcript(path, model, context):
    """One assistant line on `model` at `context` occupancy."""
    row = {"type": "assistant", "requestId": "r0", "timestamp": "2026-10-12T10:00:00Z",
           "message": {"id": "m0", "model": model,
                       "content": [{"type": "text", "text": "<placeholder>"}],
                       "usage": {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                 "cache_read_input_tokens": context, "output_tokens": 7}}}
    path.write_text(json.dumps(row) + "\n")
    return path


def start(world, extra=None, model=None, tp=None):
    """SessionStart with no payload `model` unless given; the resolved session section."""
    env, repo, _ = world
    env = {**env, **(extra or {})}
    payload = {"session_id": SID, "cwd": str(repo)}
    if model is not None:
        payload["model"] = model
    if tp is not None:
        payload["transcript_path"] = str(tp)
    out = hooks.session_start(payload, env)
    assert out, "SessionStart resolved nothing"
    sdir = resolver.session_dir(resolver.state_dir(env), SID)
    return json.loads((sdir / "resolved.json").read_text())["session"], sdir, env


def test_a_a_p_child_on_opus_1m_takes_the_repo_1m_ceiling(world):
    world[2]()
    s, sdir, _ = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL})
    assert (s["window"], s["ceilings"]) == (1000000, K400)
    assert s["session_model"] == ENV_MODEL
    assert s["session_model_source"] == "CLAUDE_SESSION_MODEL"
    assert s["window_source"] == f"session:{ENV_MODEL}"
    assert s["limits_source"] == "config.yaml window:1000000"
    # the request `set` re-resolves from keeps the model, so a `set` keeps the window
    assert resolver.load_request(sdir)["model"] == ENV_MODEL


def test_b_without_a_repo_layer_the_builder_keeps_its_own_1m_ceiling(world):
    s, _, _ = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL})
    assert (s["window"], s["ceilings"]) == (1000000, K180)          # entry 17
    assert s["limits_source"] == "defaults window:1000000"
    assert s["session_model_source"] == "CLAUDE_SESSION_MODEL"


def test_c_the_payload_model_wins_over_the_env(world):
    world[2]()
    s, sdir, _ = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL}, model="claude-opus-5-5")
    assert (s["window"], s["ceilings"]) == (200000, K180)
    assert s["session_model"] == "claude-opus-5-5"
    assert s["session_model_source"] == "payload"
    assert s["window_source"] == "session:claude-opus-5-5"
    assert resolver.load_request(sdir)["model"] == "claude-opus-5-5"


def test_c_the_payload_alone_is_the_payload(world):
    s, _, _ = start(world, model=ENV_MODEL)
    assert (s["window"], s["session_model_source"]) == (1000000, "payload")


def test_d_a_helper_ignores_the_inherited_env_model(world):
    world[2]()
    s, sdir, _ = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL,
                               "CLAUDE_SESSION_HELPER": "1", "CLAUDE_SESSION_DEPTH": "1"})
    assert (s["window"], s["window_source"]) == (200000, "declared:opus")
    assert s["ceilings"] == K180
    assert s["session_model"] is None
    assert s["session_model_source"] is None
    assert resolver.load_request(sdir)["model"] is None


@pytest.mark.parametrize("value", ["", "   "])
def test_e_an_empty_env_model_is_no_session_model(world, value):
    s, _, _ = start(world, {"CLAUDE_SESSION_MODEL": value})
    assert (s["window"], s["window_source"]) == (200000, "declared:opus")
    assert s["session_model"] is None
    assert s["session_model_source"] is None


def test_e_an_unknown_env_model_falls_back_to_the_declared(world):
    s, _, _ = start(world, {"CLAUDE_SESSION_MODEL": "some/local-model"})
    assert (s["window"], s["window_source"]) == (200000, "declared:opus")
    assert s["session_model_source"] == "CLAUDE_SESSION_MODEL"


def test_e_no_env_model_is_as_before(world):
    s, _, _ = start(world)
    assert (s["window"], s["window_source"]) == (200000, "declared:opus")
    assert (s["session_model"], s["session_model_source"]) == (None, None)


def test_f_the_meter_keeps_the_1m_window_on_the_unmarked_transcript_model(world, tmp_path):
    world[2]()
    tp = transcript(tmp_path / "t.jsonl", "claude-opus-5-5", 300000)
    _, sdir, env = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL}, tp=tp)
    hooks.post_tool_use({"session_id": SID, "transcript_path": str(tp),
                         "tool_name": "Read"}, env)
    m = meter.load(sdir)
    assert (m["window"], m["ceilings"], m["pct_context"]) == (1000000, K400, 75.0)
    assert m["window_source"] == f"session:{ENV_MODEL}"
    assert m["limits_source"] == "config.yaml window:1000000"


# Fix round 1 F1: the variable is the launcher's, like the turn cap. A `start` nested in
# a relay child carries its own model as --model, never the child's variable, and a
# config's `env:` cannot set it.
def test_f1_a_nested_start_drops_the_inherited_model(monkeypatch, tmp_path):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli, launch
    calls = []
    monkeypatch.setattr(launch.shutil, "which", lambda n: str(tmp_path / n))
    monkeypatch.setattr(launch.os, "execvpe",
                        lambda prog, argv, env: calls.append((prog, argv, dict(env))))
    for k in ("CLAUDE_SESSION_DEPTH", "CLAUDE_SESSION_MAX_TURNS", "CLAUDE_SESSION_CONFIG"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_MODEL", ENV_MODEL)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
        rc = cli.main(["start", "frontier", "--", "-p", "hello"])
    assert rc == 0, err.getvalue()
    assert calls[0][1][-2:] == ["-p", "hello"]
    assert "CLAUDE_SESSION_MODEL" not in calls[0][2]
    assert "CLAUDE_SESSION_MODEL" not in launch.scrub({"CLAUDE_SESSION_MODEL": ENV_MODEL})


def test_f1_a_config_cannot_set_the_model_variable(monkeypatch, tmp_path):
    from claude_session import launch
    from claude_session.sessionconfig import SessionConfig
    monkeypatch.setattr(launch.shutil, "which", lambda n: str(tmp_path / n))
    with pytest.raises(launch.LaunchError, match="CLAUDE_SESSION_MODEL"):
        launch.build(SessionConfig(name="f", env={"CLAUDE_SESSION_MODEL": ENV_MODEL}))


# Fix round 1 F2: a `set` re-resolves from request.json, which keeps the session model's
# source beside the model, so a `set` that is not `set model` keeps both.
def _set(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        assert cli.main(list(argv)) == 0


def test_f2_a_set_keeps_the_env_source(world, monkeypatch):
    import os
    env, repo, layer = world
    layer()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    w = ({**os.environ, "CLAUDE_SESSION_MODEL": ENV_MODEL}, repo, layer)
    s, sdir, _ = start(w)
    assert resolver.load_request(sdir)["model_source"] == "CLAUDE_SESSION_MODEL"
    _set("set", "effort", "high")
    s = json.loads((sdir / "resolved.json").read_text())["session"]
    assert (s["effort"], s["window"], s["ceilings"]) == ("high", 1000000, K400)
    assert (s["session_model"], s["session_model_source"]) == (
        ENV_MODEL, "CLAUDE_SESSION_MODEL")
    _set("set", "model", "opus")              # a model set drops the session's, and its source
    s = json.loads((sdir / "resolved.json").read_text())["session"]
    assert (s["session_model"], s["session_model_source"]) == (None, None)
    assert resolver.load_request(sdir)["model_source"] is None


def test_f2_a_payload_model_keeps_its_source_through_a_set(world, monkeypatch):
    import os
    _, repo, layer = world
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.setenv("CLAUDE_SESSION_PROFILE", "builder")
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    s, sdir, _ = start((dict(os.environ), repo, layer), model=ENV_MODEL)
    _set("set", "effort", "high")
    s = json.loads((sdir / "resolved.json").read_text())["session"]
    assert (s["session_model"], s["session_model_source"]) == (ENV_MODEL, "payload")


# Fix round 1, note 1: a blank payload `model` is no model, so the launcher's names it.
@pytest.mark.parametrize("blank", ["", "  "])
def test_note1_a_blank_payload_model_lets_the_env_name_it(world, blank):
    s, sdir, _ = start(world, {"CLAUDE_SESSION_MODEL": ENV_MODEL}, model=blank)
    assert (s["window"], s["session_model"], s["session_model_source"]) == (
        1000000, ENV_MODEL, "CLAUDE_SESSION_MODEL")
    assert resolver.load_request(sdir)["model_source"] == "CLAUDE_SESSION_MODEL"


def test_note1_a_blank_payload_model_and_no_env_is_no_session_model(world):
    s, _, _ = start(world, model="")
    assert (s["window_source"], s["session_model"], s["session_model_source"]) == (
        "declared:opus", None, None)
