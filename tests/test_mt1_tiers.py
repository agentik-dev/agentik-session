"""Packet mt1: model tiers in the profiles, one table for every spawn (brief mt1, R1 to R7).

Every test runs in conftest's temp HOME and state root; the user layer, the repo and the
agent files are written under tmp_path. No claude runs: a stub on PATH answers `which`.
"""
import io
import json
import os
import re
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import cli, config, hooks, resolver, sessionconfig, tiers

SID = "mt1-sess-0000-1111-2222"
LIB = Path(__file__).resolve().parents[1] / "plugin" / "lib" / "claude_session"
TABLE = {"design": ("fable", "high"), "build": ("opus", "high"), "words": ("sonnet", "medium"),
         "mend": ("sonnet", "high"), "lookup": ("haiku", "low")}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    stub = bin_ / "claude"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:/usr/bin:/bin")
    monkeypatch.chdir(repo)
    for k in ("CLAUDE_SESSION_CONFIG", "CLAUDE_SESSION_PROFILE", "CLAUDE_CONFIG_DIR",
              "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_SESSION_CHAIN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    config.ensure_dirs()
    return repo


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def user_file(text):
    p = Path(os.environ["HOME"]) / ".claude" / "agentik" / "profiles.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def repo_file(repo, text):
    p = repo / ".claude" / "agentik" / "config.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def table_of(out):
    return {m.group(1): (m.group(2), m.group(3))
            for m in re.finditer(r"^#\s+(\w+)\s+(\S+)\s+(\S+)$", out, re.M)}


def resolved(repo, profile=None):
    return resolver.resolve(repo, "probe", os.environ, profile=profile,
                            overlay={}).sections["session"]


# ---- 1. the profile verb prints the table (R1, R3) ---------------------------------------

def test_1_orchestrator_prints_the_five_tiers():
    rc, out, _ = run("profile", "orchestrator")
    assert rc == 0 and table_of(out) == TABLE


def test_1_orchestrator_opus_differs_in_design_alone():
    _, out, _ = run("profile", "orchestrator-opus")
    t = table_of(out)
    assert t["design"] == ("opus", "high")
    assert {r: v for r, v in t.items() if r != "design"} == \
        {r: v for r, v in TABLE.items() if r != "design"}


def test_1_local_only_is_local_in_five():
    _, out, _ = run("profile", "local-only")
    assert {m for m, _ in table_of(out).values()} == {"local/default"}


# ---- 2. one table; start exports tiers.build (R2) ----------------------------------------

def test_2_sessionconfig_holds_no_table():
    src = (LIB / "sessionconfig.py").read_text()
    assert "DEFAULTS" not in src and 'model="opus"' not in src


@pytest.mark.parametrize("name", ["frontier", "balanced", "orchestrator"])
def test_2_start_exports_the_build_tier(world, name):
    rc, out, _ = run("start", "-n", name)
    want = resolved(world, name)["tiers"]["build"]["model"]
    assert rc == 0 and f"CLAUDE_CODE_SUBAGENT_MODEL={want} " in out
    assert "_FORCE" not in out


def test_2_doctor_names_a_variable_off_the_table(world, monkeypatch):
    from claude_session import doctor
    monkeypatch.setenv("CLAUDE_CODE_SUBAGENT_MODEL", "haiku")
    rows = {c.name: c for c in doctor.run(cwd=world).checks}
    assert rows["subagents"].warn and "tiers.build is opus" in rows["subagents"].detail
    monkeypatch.setenv("CLAUDE_CODE_SUBAGENT_MODEL", "opus")
    assert "subagents" not in {c.name for c in doctor.run(cwd=world).checks}


# ---- 3. the layers (R3) ------------------------------------------------------------------

def test_3_the_user_default_profile(world, tmp_path):
    user_file("defaults:\n  profile: orchestrator\n")
    assert resolved(world)["profile"] == "orchestrator"
    other = tmp_path / "other"
    other.mkdir()
    repo_file(other, "session:\n  profile: balanced\n")
    assert resolved(other)["profile"] == "balanced"


def test_3_user_tiers_everywhere_and_the_repo_over_them(world, tmp_path):
    user_file("tiers:\n  words: {model: haiku}\n")
    for p in ("frontier", "orchestrator-opus", "builder"):
        assert resolved(world, p)["tiers"]["words"] == {"model": "haiku", "effort": "medium"}
    repo_file(world, "tiers:\n  words: {model: opus}\n")
    assert resolved(world)["tiers"]["words"]["model"] == "opus"
    repo_file(world, "session:\n  tiers:\n    words: {model: sonnet}\n")
    assert resolved(world)["tiers"]["words"]["model"] == "sonnet"


def test_3_the_config_dir_s_user_file(world, tmp_path, monkeypatch):
    ccd = tmp_path / "acct"
    (ccd / "agentik").mkdir(parents=True)
    (ccd / "agentik" / "profiles.yaml").write_text("defaults:\n  profile: builder\n")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ccd))
    assert resolved(world)["profile"] == "builder"


def test_3_subagents_is_read_as_the_build_tier(world):
    repo_file(world, "session:\n  subagents: sonnet\n")
    s = resolved(world)
    assert s["tiers"]["build"]["model"] == "sonnet" and s["subagents"] == "sonnet"


# ---- 4. the session's words (R4) ---------------------------------------------------------

def _future(hours=2):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")


def test_4_set_tier_shows_in_rules_and_ends(monkeypatch):
    rc, out, err = run("set", "tier.build", "sonnet", "--until", _future())
    assert rc == 0, err
    assert re.search(r"^tiers: build sonnet to \w{3} \d\d:\d\d$", out, re.M)
    _, out, _ = run("rules")
    assert re.search(r"^tiers: build sonnet to \w{3} \d\d:\d\d$", out, re.M)
    ov = sessionconfig.load_overlay(SID)
    ov["tiers"]["build"]["until"] = "2001-01-01T00:00:00+00:00"       # its time passed
    sessionconfig.clear_overlay(SID)
    sessionconfig.save_overlay(ov, SID)
    assert "tiers:" not in run("rules")[1]
    run("set", "tier.build", "sonnet", "--until", _future())
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "a-different-session-9999")
    assert "tiers:" not in run("rules")[1]


def test_4_the_session_start_line_says_the_words():
    run("set", "cap", "opus", "--until", _future())
    assert re.match(r"; cap: opus to \w{3} \d\d:\d\d$", hooks._tiers_part(SID, os.environ))
    assert hooks._tiers_part("no-such-session-1", os.environ) == ""


def test_4_cap_save_is_refused_and_writes_nothing():
    rc, _, err = run("set", "cap", "opus", "--save")
    assert rc == 2 and "never" in err or "refused" in err
    assert sessionconfig.load_overlay(SID) == {}


def test_4_cap_holds_every_tier():
    now = datetime.now(timezone.utc)
    t = tiers.effective({r: {"model": m, "effort": e} for r, (m, e) in TABLE.items()},
                        {"cap": {"model": "opus", "until": None}}, now)
    assert t["design"]["model"] == "opus" and t["words"]["model"] == "sonnet"


def test_4_a_run_successor_inside_the_time_keeps_the_cap(tmp_path):
    state, home = tmp_path / "st", tmp_path / "home"
    (state / "overlays").mkdir(parents=True)
    home.mkdir()
    now = datetime.now(timezone.utc)
    v = {"model": "opus", "until": _future()}
    tiers.keep(home, "s-one", v)
    assert tiers.hand(home, state, "s-one", "s-two", now) == v
    assert json.loads((state / "overlays" / "s-two.json").read_text())["cap"] == v
    assert tiers.hand(home, state, "s-two", "s-three", now + timedelta(hours=3)) is None
    assert not (state / "overlays" / "s-three.json").exists()


# ---- 5. --save writes the layer file, never configs.json (R4) ----------------------------

def test_5_save_writes_the_user_layer(world):
    p = user_file("# the owner's comment\ndefaults:\n  profile: frontier\n")
    rc, out, err = run("set", "tier.mend", "opus", "--save")
    assert rc == 0, err
    assert p.read_text().startswith("# the owner's comment\n")
    assert resolved(world)["tiers"]["mend"] == {"model": "opus", "effort": "high"}
    assert not (config.STATE_DIR / "configs.json").exists()


def test_5_save_repo_writes_the_repo_layer(world):
    rc, _, err = run("set", "tier.words", "haiku", "--save", "repo")
    assert rc == 0, err
    assert "words: {model: haiku}" in (world / ".claude" / "agentik" / "config.yaml").read_text()
    assert resolved(world)["tiers"]["words"]["model"] == "haiku"


def test_5_no_verb_writes_configs_json():
    for argv in (("set", "model", "sonnet", "--save"), ("config", "new", "mine"),
                 ("config", "delete", "frontier")):
        rc, _, _ = run(*argv)
        assert rc == 2
    assert not (config.STATE_DIR / "configs.json").exists()


# ---- 6. the role check (R6) --------------------------------------------------------------

def _session(posture, parent="opus"):
    sdir = resolver.session_dir(resolver.state_dir(os.environ), SID)
    sdir.mkdir(parents=True, exist_ok=True)
    tab = {r: {"model": m, "effort": e} for r, (m, e) in TABLE.items()}
    (sdir / "resolved.json").write_text(json.dumps({"session": {"posture": posture,
                                                                "tiers": tab}}))
    (sdir / "model.json").write_text(json.dumps({"model": parent}))


def spawn(prompt, model=None, **extra):
    ti = {"prompt": prompt, "description": "x", **extra}
    if model:
        ti["model"] = model
    return hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent", "tool_input": ti,
                               "tool_use_id": "tu-1"}, os.environ)


def denied(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def test_6_mend_on_opus_warns_under_signal_and_is_refused_under_deny():
    _session("signal")
    out = spawn("tier: mend\nfix the typo", "opus")
    assert not denied(out) and "tier: mend" in out["systemMessage"]
    _session("deny")
    out = spawn("tier: mend\nfix the typo", "opus")
    assert denied(out) and "sonnet" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_6_build_on_opus_passes_and_no_role_is_as_at_the_pin():
    _session("deny")
    assert not denied(spawn("tier: build\nthe packet", "opus"))
    assert "systemMessage" not in spawn("tier: build\nthe packet", "opus")
    assert not denied(spawn("no role named", "opus"))


def test_6_an_agent_file_s_model_is_read(world):
    _session("deny")
    (world / ".claude" / "agents").mkdir(parents=True)
    (world / ".claude" / "agents" / "big.md").write_text("---\nname: big\nmodel: opus\n---\n")
    out = hooks.pre_tool_use({"session_id": SID, "tool_name": "Agent", "cwd": str(world),
                              "tool_input": {"prompt": "tier: words\nrender",
                                             "subagent_type": "big"}}, os.environ)
    assert denied(out)


@pytest.mark.parametrize("posture", ["off", "signal", "deny"])
def test_6_fable_under_opus_is_refused_in_every_posture(posture):
    _session(posture)
    out = spawn("tier: design\nthe record", "fable")
    assert denied(out) and "Fable" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_6_a_cap_holds_a_design_spawn_on_fable():
    _session("signal", parent="fable")
    assert "systemMessage" not in spawn("tier: design\nthe record", "fable")
    run("set", "cap", "opus", "--until", _future())
    assert "tier: design" in spawn("tier: design\nthe record", "fable")["systemMessage"]
    _session("deny", parent="fable")
    assert denied(spawn("tier: design\nthe record", "fable"))


# ---- 7. the start applies the profile (R7) -----------------------------------------------

def test_7_start_passes_the_profile_s_model_and_effort():
    rc, out, _ = run("start", "-n", "orchestrator")
    assert rc == 0 and "--model fable --effort high" in out
    _, out, _ = run("start", "-n", "orchestrator", "--", "--model", "x")
    assert out.count("--model") == 1 and "--model x" in out and "--effort" not in out


def test_7_run_s_first_command_carries_the_profile(world):
    assert cli.run_args(str(world), dict(os.environ), ["go"]) == \
        ["--model", "opus", "--effort", "high", "go"]
    assert cli.run_args(str(world), dict(os.environ), ["--model", "x", "go"]) == \
        ["--model", "x", "go"]


def test_7_run_with_no_prompt_is_refused(monkeypatch):
    from claude_session import chain
    monkeypatch.setattr(chain, "on_tty", lambda: True)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    rc, _, err = run("run", "--", "--model", "opus")
    assert rc == 2 and "run -- \"<first prompt>\"" in err


# ---- 8. no xhigh -------------------------------------------------------------------------

def test_8_no_shipped_profile_says_xhigh():
    assert "xhigh" not in (LIB / "profiles.yaml").read_text()
