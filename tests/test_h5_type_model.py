"""Packet h5: the family rule reads the model an agent type names (brief h5, R1 to R4).

Every test runs in conftest's temp HOME and state root; the project, the user's config
folder (`CLAUDE_CONFIG_DIR`) and the plugins' installs are written under tmp_path, with
made-up plugin, marketplace and type names.
"""
import json
import os
from types import SimpleNamespace

import pytest

from claude_session import config, hooks, resolver

SID = "h5-sess-0000-1111-2222"
OPUS, FABLE = "claude-opus-5-5", "claude-fable-5-2"
TABLE = {"design": "fable", "build": "opus", "words": "sonnet", "mend": "sonnet",
         "lookup": "haiku"}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    for k in ("CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE", "CLAUDE_PROJECT_DIR",
              "CLAUDE_CODE_SUBAGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    repo = tmp_path / "repo"
    repo.mkdir()
    config.ensure_dirs()
    return SimpleNamespace(tmp=tmp_path, cfg=cfg, repo=repo)


def sdir():
    d = hooks._session_dir(SID, os.environ)
    d.mkdir(parents=True, exist_ok=True)
    return d


def parent(model, posture=None):
    """The session's two model records; with a posture, a resolved table as mt1's."""
    for name in ("model.json", "meter.json"):
        (sdir() / name).write_text(json.dumps({"model": model}))
    if posture:
        tab = {r: {"model": m, "effort": "high"} for r, m in TABLE.items()}
        (sdir() / "resolved.json").write_text(json.dumps(
            {"session": {"posture": posture, "tiers": tab}}))


def agent(base, name, text):
    p = base / "agents" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text) if isinstance(text, bytes) else p.write_text(text)
    return p


def fm(model):
    return f"---\nname: x\ndescription: d\nmodel: {model}\n---\nbody\n"


def install(w, key, *models, raw=None):
    """`installed_plugins.json` naming one install of `key` per model, each holding
    `agents/drafter.md`; `raw` writes the record's text as given."""
    rec = w.cfg / "plugins" / "installed_plugins.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        rec.write_bytes(raw) if isinstance(raw, bytes) else rec.write_text(raw)
        return rec
    recs = []
    for i, m in enumerate(models):
        root = w.tmp / "cache" / key.replace("@", "-") / str(i)
        agent(root, "drafter", fm(m))
        recs.append({"scope": "user", "installPath": str(root), "version": f"1.{i}"})
    rec.write_text(json.dumps({"version": 2, "plugins": {key: recs}}))
    return rec


def call(w, ti, **extra):
    payload = {"tool_name": "Agent", "session_id": SID, "cwd": str(w.repo),
               "tool_input": {"prompt": "p", "description": "d", **ti}, **extra}
    return hooks.pre_tool_use(payload, os.environ)


def reason(out):
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny", out
    r = hso["permissionDecisionReason"]
    assert "\n" not in r and r.startswith("agentik-session: ")
    return r


def model_of(w, ti):
    return hooks._agent_model(ti, {"cwd": str(w.repo)}, os.environ)


# ---- 1, 2: the project's and the user's file (R1, R3) ------------------------------------

def test_1_the_project_s_type_naming_fable_is_denied_with_r3_s_line(world):
    parent(OPUS)
    agent(world.repo / ".claude", "designer", fm("fable"))
    r = reason(call(world, {"subagent_type": "designer"}))
    assert r == ("agentik-session: a Fable helper starts only under a Fable session: this one "
                 "runs opus, and agent type designer names fable. Name model: 'opus' on the "
                 "call."), r


def test_2_the_user_s_type_alone_is_denied(world):
    parent(OPUS)
    agent(world.cfg, "sketcher", fm("claude-fable-5-2"))
    r = reason(call(world, {"subagent_type": "sketcher"}))
    assert "agent type sketcher names claude-fable-5-2" in r


# ---- 3: a plugin's type (R2) -------------------------------------------------------------

def test_3_a_plugin_s_type_is_read_from_its_install(world):
    parent(OPUS)
    install(world, "plug@market", "fable")
    assert model_of(world, {"subagent_type": "plug:drafter"}) == "fable"
    r = reason(call(world, {"subagent_type": "plug:drafter"}))
    assert "agent type plug:drafter names fable" in r


@pytest.mark.parametrize("order", [("opus", "fable"), ("fable", "opus")])
def test_3_two_installs_take_the_highest_family(world, order):
    parent(OPUS)
    install(world, "plug@market", *order)
    assert model_of(world, {"subagent_type": "plug:drafter"}) == "fable"
    assert "names fable" in reason(call(world, {"subagent_type": "plug:drafter"}))


def test_3_a_model_naming_no_family_ranks_last(world):
    install(world, "plug@market", "inherit", "sonnet")
    assert model_of(world, {"subagent_type": "plug:drafter"}) == "sonnet"
    install(world, "plug@market", "inherit")
    assert model_of(world, {"subagent_type": "plug:drafter"}) == "inherit"


def test_3_only_the_named_plugin_s_keys_count(world):
    rec = world.cfg / "plugins" / "installed_plugins.json"
    rec.parent.mkdir(parents=True)
    a, b = world.tmp / "a", world.tmp / "b"
    agent(a, "drafter", fm("fable"))
    agent(b, "drafter", fm("opus"))
    rec.write_text(json.dumps({"version": 2, "plugins": {
        "plugx@market": [{"installPath": str(a)}], "plug@other": [{"installPath": str(b)}]}}))
    assert model_of(world, {"subagent_type": "plug:drafter"}) == "opus"
    assert model_of(world, {"subagent_type": "plugx:drafter"}) == "fable"
    assert model_of(world, {"subagent_type": "plug:other"}) is None


# ---- 4: under a Fable session ------------------------------------------------------------

def test_4_each_passes_under_a_fable_session(world):
    parent(FABLE)
    agent(world.repo / ".claude", "designer", fm("fable"))
    agent(world.cfg, "sketcher", fm("claude-fable-5-2"))
    install(world, "plug@market", "opus", "fable")
    for t in ("designer", "sketcher", "plug:drafter"):
        assert call(world, {"subagent_type": t}) == {}, t


# ---- 5: the call's model outranks the file -----------------------------------------------

@pytest.mark.parametrize("posture", [None, "off", "signal", "deny"])
def test_5_a_call_naming_opus_passes_whatever_the_file_says(world, posture):
    parent(OPUS, posture)
    agent(world.repo / ".claude", "designer", fm("fable"))
    install(world, "plug@market", "fable")
    for t in ("designer", "plug:drafter"):
        assert call(world, {"subagent_type": t, "model": "opus"}) == {}, t


def test_5_a_call_naming_fable_keeps_today_s_line(world):
    parent(OPUS)
    agent(world.repo / ".claude", "designer", fm("opus"))
    r = reason(call(world, {"subagent_type": "designer", "model": "fable"}))
    assert r.endswith("this one runs opus. Name model: 'opus', or use an agent type that "
                      "names its own model."), r


# ---- 6: what passes, and never raises ----------------------------------------------------

@pytest.mark.parametrize("text", [fm("opus"), fm("sonnet"), fm("inherit"),
                                  "---\nname: x\n---\nmodel: fable\n", "model: fable\nbody\n",
                                  "", b"---\nmodel: \xff\xfe\n---\n"])
def test_6_a_type_whose_file_names_no_fable_passes(world, text):
    parent(OPUS)
    agent(world.repo / ".claude", "plain", text)
    agent(world.cfg, "plain", fm("fable"))             # the project's file is read first
    assert call(world, {"subagent_type": "plain"}) == {}


def test_6_a_built_in_type_and_no_type_pass(world):
    parent(OPUS)
    install(world, "plug@market", "fable")
    for ti in ({"subagent_type": "general-purpose"}, {"subagent_type": "Explore"}, {},
               {"subagent_type": None}, {"subagent_type": 7}, {"subagent_type": "a:b:c"},
               {"subagent_type": "../plug:drafter"}, {"subagent_type": ":drafter"},
               {"subagent_type": "plug:"}, {"subagent_type": "plug:dr/after"}):
        assert call(world, ti) == {}, ti


@pytest.mark.parametrize("raw", [
    "{not json", "[]", '"x"', '{"plugins": []}', '{"plugins": {"plug@market": 3}}',
    '{"plugins": {"plug@market": [3, {"installPath": 4}, {"installPath": null}]}}',
    '{"plugins": {"plug@market": [{"installPath": "/nonexistent/h5/gone"}]}}',
    '{"plugins": {"plug@market": [{"installPath": "/nul\\u0000here"}]}}',
    b"\xff\xfe{}"])
def test_6_a_bad_record_gives_none_and_passes(world, raw):
    parent(OPUS)
    install(world, "plug@market", raw=raw)
    assert model_of(world, {"subagent_type": "plug:drafter"}) is None
    assert call(world, {"subagent_type": "plug:drafter"}) == {}


def test_6_no_record_gives_none(world):
    parent(OPUS)
    assert model_of(world, {"subagent_type": "plug:drafter"}) is None
    assert call(world, {"subagent_type": "plug:drafter"}) == {}


def test_6_a_type_file_that_is_a_folder_gives_none(world):
    parent(OPUS)
    (world.repo / ".claude" / "agents" / "odd.md").mkdir(parents=True)
    root = world.tmp / "inst"
    (root / "agents" / "drafter.md").mkdir(parents=True)
    install(world, "plug@market", raw=json.dumps(
        {"plugins": {"plug@market": [{"installPath": str(root)}]}}))
    assert call(world, {"subagent_type": "odd"}) == {}
    assert call(world, {"subagent_type": "plug:drafter"}) == {}


# ---- 7: a helper's own call --------------------------------------------------------------

def test_7_a_helper_s_call_with_a_fable_type_is_denied_as_unknown(world):
    parent(FABLE)                                       # a helper's own model is not the session's
    agent(world.repo / ".claude", "designer", fm("fable"))
    r = reason(call(world, {"subagent_type": "designer"}, agent_id="a1", tool_use_id="tu-h5"))
    assert ("the session's model is not known" in r and "retry after one tool call" in r
            and "agent type designer names fable" in r), r
    assert not (sdir() / "calls" / "tu-h5").exists()


# ---- 8: the role check reads a plugin type (R4) ------------------------------------------

def test_8_a_plugin_type_above_its_role_is_refused_under_deny_and_warned_under_signal(world):
    install(world, "plug@market", "opus")
    ti = {"subagent_type": "plug:drafter", "prompt": "tier: words\nrender"}
    parent(OPUS, "deny")
    r = reason(call(world, ti))
    assert "tier: words" in r and "sonnet" in r and "runs opus" in r, r
    parent(OPUS, "signal")
    out = call(world, ti)
    assert "hookSpecificOutput" not in out and "tier: words" in out["systemMessage"], out
