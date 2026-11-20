"""Packet rc1-respawn-confirm: a RESPAWN close run in the background is refused at PreToolUse
(R1), a chained marker no confirm names is said at each main-thread prompt (R2), and the
CHECKPOINT line's tail says a foreground call (R4). The band's word (R3) is tested in
plugin/hooks/session.test.ts. `_confirm` and chain.py are as at the pin (R6)."""
import hashlib
import json
import os
import time

import pytest

from claude_session import hooks, meter, resolver, sessionconfig

pytestmark = pytest.mark.usefixtures("frontier_home")

SID = "test-sess-0000-1111-2222"
OTHER = "a-different-session-9999"
CHARTER = "/w/example-app/history/sittings/2026-11-20-1.md"
CLOSE = "agentik session checkpoint --respawn --charter history/sittings/2026-11-20-1.md"
CHAIN = "make check && git commit -m done -- a.md && git push && "
SPELLINGS = [f"{s} --respawn --charter c.md" for s in hooks.RESPAWN_CMDS]
LINE = "RESPAWN unconfirmed: "


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)


def use(monkeypatch, posture):
    cfgs = sessionconfig.load_configs()
    cfgs["t"] = sessionconfig.SessionConfig(name="t", posture=posture)
    sessionconfig.save_configs(cfgs)
    monkeypatch.setenv("CLAUDE_SESSION_CONFIG", "t")


def _sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), SID)


def _bash(command, background=None, **extra):
    ti = {"command": command}
    if background is not None:
        ti["run_in_background"] = background
    return {"session_id": SID, "tool_name": "Bash", "tool_input": ti, **extra}


def _mark(written, chain="net", session=SID, charter=CHARTER):
    """A marker as the verb writes it; returns the sha256 of its bytes."""
    p = _sdir() / hooks.MARKER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"session": session, "charter": charter,
                             "charter_sha256": "0" * 64, "written": written, "chain": chain}))
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _confirmed(sha):
    (_sdir() / hooks.CONFIRMED).write_text(json.dumps({"at": time.time(), "marker_sha256": sha}))


def _activity_at():
    return json.loads((_sdir() / hooks.ACTIVITY).read_text())["at"]


def _said(out):
    """The prompt's `RESPAWN unconfirmed:` lines."""
    ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return [b for b in ctx.split("\n\n") if b.startswith(LINE)]


def _prompt(**extra):
    return hooks.user_prompt_submit({"session_id": SID, "prompt": "go", **extra})


def _is_bg_deny(out):
    h = out.get("hookSpecificOutput") or {}
    r = h.get("permissionDecisionReason") or ""
    return (h.get("permissionDecision") == "deny" and r == hooks.BACKGROUND_CLOSE_DENY
            and r.startswith("agentik-session: ") and "foreground" in r
            and "\n" not in r and len(r) < 900)


# ---- Acceptance 1: the stall, through the hooks -----------------------------------------

def test_1_the_stall_a_background_close_is_never_confirmed(monkeypatch):
    """The measured stall: the background call's PreToolUse and PostToolUse fire before the
    verb writes its marker, so no confirm is ever written. At the pin the PreToolUse passed
    (`{}`); here it is the deny."""
    use(monkeypatch, "signal")
    call = _bash(CHAIN + CLOSE, background=True)
    pre = hooks.pre_tool_use(call)
    hooks.post_tool_use(call)                          # the call returns at once
    _mark(time.time())                                 # the background job writes the marker
    assert not (_sdir() / hooks.CONFIRMED).exists()
    assert _is_bg_deny(pre)


# ---- Acceptance 2: the deny -------------------------------------------------------------

@pytest.mark.parametrize("posture", ["signal", "off", "deny"])
@pytest.mark.parametrize("chained", [False, True])
@pytest.mark.parametrize("cmd", SPELLINGS)
def test_2_a_background_close_is_denied(monkeypatch, posture, chained, cmd):
    use(monkeypatch, posture)
    command = (CHAIN if chained else "") + cmd
    assert _is_bg_deny(hooks.pre_tool_use(_bash(command, background=True)))
    helper = _bash(command, background=True, agent_id="a1", tool_use_id="toolu_01")
    assert _is_bg_deny(hooks.pre_tool_use(helper))
    assert not (_sdir() / hooks.CALLS).exists()        # a denied call opens none
    assert hooks.pre_tool_use(_bash(command)) == {}    # the foreground: as at the pin
    assert hooks.pre_tool_use(_bash(command, background=False)) == {}
    hooks.pre_tool_use(_bash(command, agent_id="a1", tool_use_id="toolu_02"))
    assert sorted(p.name for p in (_sdir() / hooks.CALLS).iterdir()) == ["toolu_02"]


@pytest.mark.parametrize("command", ["agentik session checkpoint",
                                     "agentik-session checkpoint --charter c.md",
                                     "make check > /tmp/x.log 2>&1"])
def test_2_a_background_call_without_respawn_passes(monkeypatch, command):
    use(monkeypatch, "signal")
    assert hooks.pre_tool_use(_bash(command, background=True)) == {}


def test_2_the_guard_failing_passes_the_call(monkeypatch):
    use(monkeypatch, "signal")

    def boom(_):
        raise RuntimeError("x")
    monkeypatch.setattr(hooks, "_respawn_close", boom)
    assert hooks.pre_tool_use(_bash(CLOSE, background=True)) == {}


# ---- Acceptance 3: the line -------------------------------------------------------------

@pytest.mark.parametrize("posture", ["signal", "off"])
def test_3_a_chained_marker_no_confirm_names_says_the_line(monkeypatch, posture):
    use(monkeypatch, posture)
    _mark(time.time())
    for _ in range(2):                                 # at every such prompt
        said = _said(_prompt())
        assert len(said) == 1
        line = said[0]
        assert f"`agentik session checkpoint --respawn --charter {CHARTER}`" in line
        assert "foreground call of its own" in line and "\n" not in line


@pytest.mark.parametrize("case", ["confirmed", "no-chain", "empty-chain", "other-session",
                                  "helper", "no-marker", "not-json", "a-list"])
def test_3_no_line(monkeypatch, case):
    use(monkeypatch, "signal")
    sha = _mark(time.time(), chain={"no-chain": None, "empty-chain": ""}.get(case, "net"),
                session=OTHER if case == "other-session" else SID)
    if case == "confirmed":
        _confirmed(sha)
    if case == "no-marker":
        (_sdir() / hooks.MARKER).unlink()
    if case == "not-json":
        (_sdir() / hooks.MARKER).write_text("{")
    if case == "a-list":
        (_sdir() / hooks.MARKER).write_text("[1]")
    out = _prompt(agent_id="a1") if case == "helper" else _prompt()
    assert _said(out) == []


def test_3_a_confirm_of_other_bytes_says_the_line(monkeypatch):
    use(monkeypatch, "signal")
    _mark(time.time())
    _confirmed("0" * 64)
    assert len(_said(_prompt())) == 1


def test_3_an_unsafe_charter_path_is_not_printed(monkeypatch):
    use(monkeypatch, "off")
    _mark(time.time(), charter="/w/my charter;rm.md")
    line, = _said(_prompt())
    assert "--charter <the charter>`" in line and "my charter" not in line


def test_3_a_fault_says_nothing_and_never_raises(monkeypatch):
    use(monkeypatch, "signal")
    _mark(time.time())
    (_sdir() / hooks.CONFIRMED).mkdir()                 # the confirm cannot be read
    assert _said(_prompt()) == []


# ---- Acceptance 4: the mend -------------------------------------------------------------

def test_4_a_foreground_close_mends_the_mark(monkeypatch):
    use(monkeypatch, "signal")
    _mark(time.time() - 60)
    assert len(_said(_prompt())) == 1
    call = _bash(CLOSE)
    assert hooks.pre_tool_use(call) == {}
    sha = _mark(_activity_at())                        # the verb rewrites the marker
    hooks.post_tool_use(call)
    assert json.loads((_sdir() / hooks.CONFIRMED).read_text())["marker_sha256"] == sha
    assert _said(_prompt()) == []


# ---- Acceptance 6: the tail -------------------------------------------------------------

def _meter(pct):
    return meter.Meter(session_id=SID, turns=1, sidechain_turns=0, tokens=0,
                       context=int(1800 * pct), max_context=0, median_context=0, model=None,
                       started=None, ceilings={"context": 180000, "turns": 400}, window=None,
                       checkpoint_at=0.8, pct_context=pct, pct_turns=0.2, zone="checkpoint",
                       ts="", transcript={})


def _line(out):
    return out["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("pct", [80.0, 100.0])
def test_6_the_tail_says_a_foreground_call(pct):
    rel = "history/sittings/2026-11-20-1.md"
    out = hooks._checkpoint_out(_meter(pct), "history/sittings", [rel, hooks.NO_CHARTER])
    assert "in a foreground call of its own" in _line(out) and f"--charter {rel}`" in _line(out)
    assert len(json.dumps(out)) <= hooks.MAX_OUT


@pytest.mark.parametrize("pct", [80.0, 100.0])
def test_6_a_long_path_still_gets_a_line(pct):
    rel = "history/sittings/2026-11-20-1.md"
    long_abs = "/" + "d" * 180 + "/" + rel
    out = hooks._checkpoint_out(_meter(pct), "h", [long_abs, rel, hooks.NO_CHARTER])
    assert f"--charter {rel}`" in _line(out) and len(json.dumps(out)) <= hooks.MAX_OUT
    long_rel = "h/" + "r" * 200 + ".md"
    out = hooks._checkpoint_out(_meter(pct), "h", [long_abs, long_rel, hooks.NO_CHARTER])
    assert f"--charter {hooks.NO_CHARTER}`" in _line(out)
    assert "in a foreground call of its own" in _line(out)
    assert len(json.dumps(out)) <= hooks.MAX_OUT
