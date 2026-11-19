"""Packet h6: the spawn gate refuses every family above the session's (brief h6, R1 to R6).

Every test runs in conftest's temp HOME and state root; the project, the user's config
folder (`CLAUDE_CONFIG_DIR`) and a plugin's install are written under tmp_path, with
made-up plugin, marketplace and type names. A session whose model is not known still
refuses a Fable helper alone, in the pin's words.
"""
import json
import os
from types import SimpleNamespace

import pytest

from claude_session import config, hooks

SID = "h6-sess-0000-1111-2222"
MODELS = {"fable": "claude-fable-5-2", "opus": "claude-opus-5-5",
          "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
HELPERS = ("fable", "opus", "sonnet", "haiku")
NEW = (("sonnet", "opus"), ("haiku", "opus"), ("haiku", "sonnet"))   # the row's three cells

# The table at `c0bcb94` with the three cells turned: every other cell as at the pin.
TABLE = {
    "fable": {"fable": "pass", "opus": "pass", "sonnet": "pass", "haiku": "pass"},
    "opus": {"fable": "deny", "opus": "pass", "sonnet": "pass", "haiku": "pass"},
    "sonnet": {"fable": "deny", "opus": "deny", "sonnet": "pass", "haiku": "pass"},
    "haiku": {"fable": "deny", "opus": "deny", "sonnet": "deny", "haiku": "pass"},
    None: {"fable": "deny", "opus": "pass", "sonnet": "pass", "haiku": "pass"},
}
HELPER_ROW = {"fable": "deny", "opus": "pass", "sonnet": "pass", "haiku": "pass"}

# The pin's two Fable lines, byte for byte (R3).
FABLE_HEAD = "agentik-session: a Fable helper starts only under a Fable session: "
UNKNOWN = ("the session's model is not known (no record yet, or a switch its records have "
           "not both seen: retry after one tool call)")
NAMED_TAIL = ". Name model: 'opus', or use an agent type that names its own model."


def fable_named(runs):
    return FABLE_HEAD + runs + NAMED_TAIL


def fable_typed(runs, typ, model):
    return f"{FABLE_HEAD}{runs}, and agent type {typ} names {model}. Name model: 'opus' on the call."


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
    (repo / ".git").mkdir(parents=True)
    config.ensure_dirs()
    return SimpleNamespace(tmp=tmp_path, cfg=cfg, repo=repo)


def sdir():
    d = hooks._session_dir(SID, os.environ)
    d.mkdir(parents=True, exist_ok=True)
    return d


def parent(model=None, meter="same", posture=None, tiers=None):
    """The session's two model records (None removes one); with a posture, a resolved
    table as mt1's."""
    meter = model if meter == "same" else meter
    for name, m in (("model.json", model), ("meter.json", meter)):
        p = sdir() / name
        if m is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(json.dumps({"model": m}))
    if posture:
        tab = {r: {"model": m, "effort": "high"} for r, m in (tiers or {}).items()}
        (sdir() / "resolved.json").write_text(json.dumps(
            {"session": {"posture": posture, "tiers": tab}}))


def spawn(model=None, tool="Agent", prompt="p", ti=None, **extra):
    t = {"prompt": prompt, "description": "d", **(ti or {})}
    if model is not None:
        t["model"] = model
    return hooks.pre_tool_use({"tool_name": tool, "session_id": SID, "tool_input": t, **extra},
                              os.environ)


def denied(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def reason(out):
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny" and hso["hookEventName"] == "PreToolUse"
    r = hso["permissionDecisionReason"]
    assert "\n" not in r and len(r) < 900, r
    assert r.startswith("agentik-session: ")
    return r


def agent(base, name, model):
    p = base / "agents" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nname: {name}\ndescription: d\nmodel: {model}\n---\nbody\n")
    return p


def install(w, key, model):
    root = w.tmp / "cache" / key.replace("@", "-") / "0"
    agent(root, "drafter", model)
    rec = w.cfg / "plugins" / "installed_plugins.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(json.dumps({"version": 2, "plugins": {
        key: [{"scope": "user", "installPath": str(root), "version": "1.0"}]}}))


# --- 1. the table --------------------------------------------------------------------------

def test_1_the_table_five_sessions_by_four_helpers_and_a_helper_s_own_spawn():
    got = {}
    for session in TABLE:
        parent(MODELS.get(session))
        got[session] = {h: "deny" if denied(spawn(MODELS[h])) else "pass" for h in HELPERS}
    assert got == TABLE
    parent(MODELS["opus"])
    row = {h: "deny" if denied(spawn(MODELS[h], agent_id="a1")) else "pass" for h in HELPERS}
    assert row == HELPER_ROW
    for session, helper in NEW:                         # Task as Agent, the short word too
        parent(MODELS[session])
        assert denied(spawn(helper, tool="Task")) and denied(spawn(MODELS[helper]))


def test_1_a_helper_s_own_spawn_stays_fable_only_d5():
    for session in ("sonnet", "haiku"):
        parent(MODELS[session])
        assert spawn("opus", agent_id="a1") == {} and spawn("sonnet", agent_id="a1") == {}
        assert denied(spawn("fable", agent_id="a1"))


def test_1_a_model_naming_no_family_passes_r2():
    parent(MODELS["haiku"])
    for m in ("inherit", "local/default", "qwen3-27b"):
        assert spawn(m) == {}
    assert spawn() == {}


# --- 2. a type names it ----------------------------------------------------------------------

def test_2_a_project_type_naming_opus_under_a_sonnet_session(world):
    parent(MODELS["sonnet"])
    agent(world.repo / ".claude", "big", "opus")
    r = reason(spawn(ti={"subagent_type": "big"}, cwd=str(world.repo)))
    assert "agent type big names opus" in r and r.endswith("Name model: 'sonnet' on the call.")
    assert spawn("sonnet", ti={"subagent_type": "big"}, cwd=str(world.repo)) == {}


def test_2_a_plugin_s_type_is_refused_the_same_way(world):
    parent(MODELS["sonnet"])
    install(world, "plug@market", "opus")
    r = reason(spawn(ti={"subagent_type": "plug:drafter"}))
    assert "agent type plug:drafter names opus" in r
    assert r.endswith("Name model: 'sonnet' on the call.")
    assert spawn("sonnet", ti={"subagent_type": "plug:drafter"}) == {}


# --- 3. not known: Fable alone ---------------------------------------------------------------

@pytest.mark.parametrize("records,runs", [
    ((MODELS["sonnet"], MODELS["opus"]), UNKNOWN),      # a switch one record has not seen
    (("local/default", "local/default"), "this one runs other"),
    ((None, None), UNKNOWN),
])
def test_3_a_session_not_known_refuses_fable_alone(records, runs):
    parent(records[0], records[1])
    for h in ("opus", "sonnet", "haiku"):
        assert spawn(h) == {} and spawn(MODELS[h]) == {}
    assert reason(spawn("fable")) == fable_named(runs)


# --- 4. the lines ----------------------------------------------------------------------------

def test_4_the_new_lines_in_both_forms(world):
    for session, helper in NEW:
        parent(MODELS[session])
        agent(world.repo / ".claude", f"by-{helper}", helper)
        for r in (reason(spawn(MODELS[helper])),
                  reason(spawn(ti={"subagent_type": f"by-{helper}"}, cwd=str(world.repo)))):
            assert f"this one runs {session}" in r and f"family {helper}" in r
            assert f"model: '{session}'" in r and r.endswith(f"Name model: '{session}' on the call.")
            assert "Fable" not in r


def test_4_a_fable_helper_s_lines_are_the_pin_s_byte_for_byte(world):
    agent(world.repo / ".claude", "designer", "fable")
    for session in ("opus", "sonnet", "haiku"):
        parent(MODELS[session])
        runs = f"this one runs {session}"
        assert reason(spawn("fable")) == fable_named(runs)
        assert reason(spawn(ti={"subagent_type": "designer"}, cwd=str(world.repo))) \
            == fable_typed(runs, "designer", "fable")
    parent()
    assert reason(spawn(ti={"subagent_type": "designer"}, cwd=str(world.repo))) \
        == fable_typed(UNKNOWN, "designer", "fable")


# --- 5. posture ------------------------------------------------------------------------------

@pytest.mark.parametrize("posture", ["off", "signal", "deny"])
def test_5_every_posture_denies_and_opens_no_call(posture):
    for i, (session, helper) in enumerate(NEW):
        parent(MODELS[session], posture=posture, tiers={"build": "fable"})
        tid = f"toolu_h6_{posture}_{i}"
        assert denied(spawn(helper, tool_use_id=tid))
        assert not (sdir() / "calls" / tid).exists()
    parent(MODELS["sonnet"], posture=posture, tiers={"build": "fable"})
    assert not denied(spawn("sonnet", tool_use_id="toolu_h6_pass"))


# --- 6. a spawn the rule passes meets the role check ----------------------------------------

@pytest.mark.parametrize("session,helper,role_model", [
    ("fable", "fable", "opus"), ("sonnet", "sonnet", "haiku"), ("opus", "opus", "sonnet")])
def test_6_the_role_check_still_warns_and_refuses(session, helper, role_model):
    parent(MODELS[session], posture="signal", tiers={"build": role_model})
    out = spawn(helper, prompt="tier: build\nthe packet")
    assert not denied(out) and "tier: build" in out["systemMessage"]
    parent(MODELS[session], posture="deny", tiers={"build": role_model})
    r = reason(spawn(helper, prompt="tier: build\nthe packet"))
    assert "tier: build" in r and f"Name model: '{role_model}'" in r
