"""Packet h4: a helper's end closes its calls, the relay's limit clears the check's wall, the
mix's prices are the page's.

R1 R2 (NICE n51): a helper's PreToolUse opens `calls/<tool_use_id>`; a call a rejection ended
gets no Post, so the file stood until the stale bound (1200 s). SubagentStop is registered
and removes the files the ending helper opened, by the `agent_id` the file now holds.
R3 (n57): `.claude/agentik/config.yaml` gives the relay's verify line room past the check's
wall. R4 R5 (n85): the mix's prices are the pricing page's of 2026-11-12. Each test runs
under the conftest's own temp HOME and state.
"""
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import config, doctor, hooks, resolver, rules, yamlsubset

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SID = "h4-sess-0001"
A, B = "agent-aaa", "agent-bbb"
G = {"cap": 12, "floor": 0, "settle": 60}


def _sdir(sid=SID):
    return resolver.session_dir(config.STATE_DIR, sid)


def _calls(sid=SID):
    d = _sdir(sid) / hooks.CALLS
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def _pre(agent, tid, sid=SID):
    """A helper's PreToolUse for a Read, as Claude Code sends it."""
    return hooks.pre_tool_use({"session_id": sid, "agent_id": agent, "tool_use_id": tid,
                               "tool_name": "Read", "tool_input": {"file_path": "/x"},
                               "hook_event_name": "PreToolUse"}, dict(os.environ))


def _end(agent, sid=SID, **more):
    return hooks.subagent_stop({"session_id": sid, "agent_id": agent,
                                "hook_event_name": "SubagentStop", **more}, dict(os.environ))


def _cli(event, payload):
    return subprocess.run([sys.executable, "-I", str(PLUGIN / "lib" / "agentik-session"), "hook",
                           event], env=dict(os.environ), capture_output=True, text=True,
                          input=json.dumps(payload), timeout=60)


# ---- R1: the event ----------------------------------------------------------------------

def test_a1_the_hook_takes_the_event_and_prints_nothing():
    r = _cli("SubagentStop", {"session_id": SID, "agent_id": A,
                              "hook_event_name": "SubagentStop"})
    assert (r.returncode, r.stdout) == (0, ""), r
    assert hooks.HANDLERS["SubagentStop"] is hooks.HANDLERS["subagent-stop"]
    assert {"SubagentStop", "subagent-stop"} <= hooks.SILENT


def test_a1_registered_in_stops_shape():
    doc = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
    assert ([(h["type"], h["command"].replace("SubagentStop", "Stop"), h["timeout"])
             for g in doc["SubagentStop"] for h in g["hooks"]]
            == [(h["type"], h["command"], h["timeout"]) for g in doc["Stop"] for h in g["hooks"]]
            == [("command", "\"${CLAUDE_PLUGIN_ROOT}/hooks/run\" Stop", 5)])
    assert [g.get("matcher") for g in doc["SubagentStop"]] == [None]
    assert "SubagentStop" in doctor.HOOK_EVENTS
    assert set(doctor.HOOK_EVENTS) == set(doc)


def test_a1_dispatch_prints_nothing(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hooks.dispatch("SubagentStop") == 0
    assert capsys.readouterr() == ("", "")


def test_a5_the_shim_swallows_an_older_launchers_refusal(tmp_path):
    root = tmp_path / "plugin"
    (root / "bin").mkdir(parents=True)
    tool = root / "bin" / "agentik-session"
    tool.write_text("#!/bin/sh\ncat >/dev/null; echo '{}'; echo \"invalid choice: $2\" >&2; "
                    "exit 2\n")
    tool.chmod(0o755)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_PLUGIN_ROOT": str(root)}
    r = subprocess.run([str(PLUGIN / "hooks" / "run"), "SubagentStop"], env=env,
                       input='{"session_id": "s"}', capture_output=True, text=True, timeout=60)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


# ---- R2: the call file ------------------------------------------------------------------

def test_a2_a_helpers_end_closes_its_call():
    _pre(A, "toolu_probe01")
    f = _sdir() / hooks.CALLS / "toolu_probe01"
    doc = json.loads(f.read_text())
    assert doc["agent_id"] == A and isinstance(doc["at"], float)
    assert _end(A) == {}
    assert _calls() == []


def test_a2_through_the_cli():
    assert _cli("PreToolUse", {"session_id": SID, "agent_id": A, "tool_use_id": "toolu_probe01",
                               "tool_name": "Read", "tool_input": {"file_path": "/x"}}
                ).returncode == 0
    assert _calls() == ["toolu_probe01"]
    r = _cli("SubagentStop", {"session_id": SID, "agent_id": A})
    assert (r.returncode, r.stdout, _calls()) == (0, "", [])


@pytest.mark.parametrize("aid", [7, "agent aaa", "a" * 129, "agent-aaa\n", ["agent-aaa"]])
def test_a2_the_file_holds_an_id_only_when_id_shaped(aid):
    hooks._open_call({"session_id": SID, "agent_id": aid, "tool_use_id": "toolu_02"},
                     dict(os.environ))
    doc = json.loads((_sdir() / hooks.CALLS / "toolu_02").read_text())
    assert list(doc) == ["at"]


def test_a3_another_helpers_call_and_strangers_stay():
    _pre(A, "toolu_a1")
    _pre(A, "toolu_a2")
    _pre(B, "toolu_b1")
    d = _sdir() / hooks.CALLS
    (d / "toolu_old").write_text(json.dumps({"at": time.time()}))        # an older plugin's
    (d / "toolu_bad").write_bytes(b"\xff not json")
    (d / "toolu_list").write_text(json.dumps([A]))
    (d / "toolu_dir").mkdir()
    (d / "toolu_dir" / "x").write_text(json.dumps({"at": 1, "agent_id": A}))
    r = _cli("SubagentStop", {"session_id": SID, "agent_id": A})
    assert (r.returncode, r.stdout) == (0, "")
    assert _calls() == ["toolu_b1", "toolu_bad", "toolu_dir", "toolu_list", "toolu_old"]
    assert (d / "toolu_dir" / "x").exists()


def test_a4_the_launcher_goes_on_after_the_helpers_end():
    from claude_session import chain
    now = time.time()
    _pre(A, "toolu_probe01")
    sdir = _sdir()
    (sdir / hooks.CALLS / "toolu_probe01").write_text(json.dumps({"at": now - 30,
                                                                  "agent_id": A}))
    (sdir / hooks.HELPER_ACTIVITY).write_text(json.dumps({"at": now - 30}))
    for name, at in ((hooks.MARKER, now - 200), (hooks.ACTIVITY, now - 190),
                     (hooks.TURN_ENDED, now - 180)):
        (sdir / name).write_text(json.dumps({"written" if name == hooks.MARKER else "at": at}))
    c = chain.Chain("c1", ["--model", "m"], config.STATE_DIR, chain.Effects(), dict(G), poll=2,
                    grace=10, kill_grace=30)
    assert c._ready(sdir, now) is False
    _end(A)
    assert c._ready(sdir, now) is False                  # the helper's stamp is 30 s old
    assert c._ready(sdir, now + 31) is True              # settle (60 s) has passed
    assert c._stale == []


@pytest.mark.parametrize("payload", [
    {"session_id": SID},
    {"session_id": SID, "agent_id": "agent aaa"},
    {"session_id": SID, "agent_id": ["agent-aaa"]},
    {"session_id": "h4-no-such-dir", "agent_id": A},
    {"session_id": "../h4", "agent_id": A},
    {"agent_id": A},
])
def test_a6_a_payload_that_names_no_helper_or_session_does_nothing(payload, monkeypatch):
    _pre(A, "toolu_probe01")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)    # never the fallback id
    root = _sdir().parent                               # every session's folder
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    r = _cli("SubagentStop", payload)
    assert (r.returncode, r.stdout) == (0, "")
    assert hooks.subagent_stop(payload, dict(os.environ)) == {}
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before
    assert not resolver.session_dir(config.STATE_DIR, "h4-no-such-dir").exists()


def test_a6_never_raises(monkeypatch):
    _pre(A, "toolu_probe01")
    with monkeypatch.context() as m:
        m.setattr(hooks.os, "listdir", lambda *_: 1 / 0)
        assert _end(A) == {}
    assert _calls() == ["toolu_probe01"]


# ---- R3: the relay's limit ----------------------------------------------------------------

def _wall(text):
    recipe = re.search(r"^check:.*\n\t(.*)$", text, re.M).group(1)
    return int(re.search(r"--wall (\d+)", recipe).group(1))


def _tie(wall, seconds):
    return wall + 60 <= seconds <= 3600


def test_a7_the_repo_resolves_the_relays_limit(tmp_path):
    env = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state"),
           "PATH": "/usr/bin:/bin"}
    (tmp_path / "home").mkdir()
    r = resolver.resolve(ROOT, "h4-resolve-0001", env)
    assert r.sections["relay"]["verify_seconds"] == 1920
    assert r.unknown == [] and r.renamed == []


def test_a7_the_limit_clears_the_checks_wall():
    makefile = (ROOT / "Makefile").read_text()
    doc = yamlsubset.load((ROOT / ".claude" / "agentik" / "config.yaml").read_text())
    wall, seconds = _wall(makefile), doc["relay"]["verify_seconds"]
    assert (wall, seconds) == (1800, 1920) and _tie(wall, seconds)
    assert not _tie(wall, 1800) and not _tie(1900, seconds) and not _tie(wall, 3601)
    assert _wall(makefile.replace("--wall 1800", "--wall 1900")) == 1900
    assert ".claude/agentik/config.yaml" in re.search(r"^check:.*$", makefile, re.M).group(0)


def test_a7_the_file_is_tracked():
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch",
                        ".claude/agentik/config.yaml"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---- R4 R5: the prices ----------------------------------------------------------------------

PAGE = {"fable": (8, 40, 10, 0.20), "opus": (4, 20, 5, 0.20), "sonnet": (2, 10, 2.50, 0.10),
        "haiku": (0.10, 0.50, 0.125, 0.01)}


def test_a8_the_prices_are_the_pages():
    p = rules.mix({"shares": {"opus": 1}})["prices"]
    assert list(p) == list(PAGE)
    for f, row in p.items():
        assert row == {k: pytest.approx(v) for k, v in zip(
            ("input", "output", "cache_write", "cache_read"), PAGE[f])}


def test_a9_a_users_input_scales_its_cache_prices_and_a_given_price_wins():
    p = rules.mix({"shares": {"opus": 1}, "prices": {"opus": {"input": 10}}})["prices"]
    assert (p["opus"]["cache_read"], p["opus"]["cache_write"]) == (0.5, 12.5)
    assert p["fable"]["cache_read"] == pytest.approx(0.2)
    p = rules.mix({"shares": {"fable": 1}, "prices": {"fable": {"cache_read": 0.8}}})["prices"]
    assert (p["fable"]["cache_read"], p["fable"]["cache_write"]) == (0.8, 10.0)
    p = rules.mix({"shares": {"fable": 1}, "prices": {"haiku": {"input": 1, "cache_write": 2}}})
    assert p["prices"]["haiku"] == {"input": 1, "output": 0.5, "cache_write": 2,
                                    "cache_read": pytest.approx(0.1)}


def test_a8_the_reconcilers_weights_are_opus_ratios():
    from claude_session.reconcile import weights
    assert weights() == pytest.approx({"input": 1, "output": 5, "cache_write": 1.25,
                                       "cache_read": 0.05})
