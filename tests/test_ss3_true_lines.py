"""Row ss3: three first-session lines say the whole truth. A session the launcher did not start
is told that its profile's model and effort were not applied (R1, R2); an unknown profile name
is told to the session, not to stderr alone (R3); `decisions.dir`, which no tool reads, leaves
the shipped file and the resolver, and a layer that sets it is warned as an unknown key (R4).
Every line runs in a temp HOME, state, config and cache folder, and a temp cwd."""
import json
import subprocess

import pytest

from claude_session import hooks, resolver
from test_ak5_plug import S, SHIPPED, _env, repo_file, user_file

SID = "ss3-sess-0000-1111"
R1 = (" (its limits and rules apply; its model and effort are set only by agentik session "
      "run)")
R2 = " (limits and rules only)"
NAME = "-".join(("qx", "made", "up"))                    # a made-up profile name
# SessionStart's whole additionalContext for a launched `frontier` session at the pin
# (de078a9), the box's folder as <T>: acceptance line 5.
PIN_FRONTIER = (
    "agentik-session: profile 'frontier'; the meter shows this session's percent on its "
    "schedule and prints CHECKPOINT when it is time to bring the charter current and hand off; "
    "resolved config at <T>/home/.local/state/agentik-session/sessions/ss3-sess-0000-1111/"
    "resolved.json; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest; "
    "the Next act takes the highest ready; pacing: wake in the act's last tool call, a pending "
    "helper is the wake (one fallback, 1800s+), a wait is said and cheap; fill off; "
    "agentik-session rules prints both; charter: none open today under history/sittings, run "
    'agentik-session charter open "<goal>"')


@pytest.fixture
def box(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    return home, cwd


def _run(box, *argv, stdin=b"", **extra):
    home, cwd = box
    p = subprocess.run([str(S), *argv], cwd=str(cwd), input=stdin, capture_output=True,
                       env=_env(home, CLAUDE_PROJECT_DIR=str(cwd), CLAUDE_CODE_SESSION_ID=SID,
                                **extra), timeout=120)
    return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")


def _start(box, **extra):
    home, cwd = box
    ev = {"session_id": SID, "hook_event_name": "SessionStart", "cwd": str(cwd),
          "source": "startup", "transcript_path": str(home / "none.jsonl"), "model": "m"}
    rc, out, err = _run(box, "hook", "SessionStart", stdin=json.dumps(ev).encode(), **extra)
    d = json.loads(out) if out.strip() else {}
    return rc, (d.get("hookSpecificOutput") or {}).get("additionalContext"), err


def _shipped_names():
    return list(resolver.load_profiles({"HOME": "/nonexistent"})[1])


# ---- line 1, R1: the line for a session the launcher did not start --------------------------

@pytest.mark.parametrize("name", ["frontier", "balanced"])
def test_a_plain_session_is_told_its_model_and_effort_were_not_set(box, name):
    if name != "frontier":
        repo_file(box[1], f"session: {{profile: {name}}}\n")
    rc, ctx, _ = _start(box)
    assert rc == 0 and ctx.startswith(f"agentik-session: profile '{name}'{R1}; "), ctx
    assert len(R1.split()) <= 20 and "opus" not in R1 and "sonnet" not in R1


@pytest.mark.parametrize("name", ["frontier", "balanced"])
def test_a_launched_session_keeps_the_pins_line(box, name):
    rc, ctx, _ = _start(box, CLAUDE_SESSION_PROFILE=name)
    assert rc == 0 and ctx.startswith(f"agentik-session: profile '{name}'; the meter "), ctx
    assert R1 not in ctx


def test_a_chain_session_counts_as_launched(box):
    """`agentik session run` with no CLAUDE_SESSION_PROFILE passes the default profile's model
    and effort to claude itself and marks the child with the chain's name alone."""
    rc, ctx, _ = _start(box, CLAUDE_SESSION_CHAIN="cwd-none")
    assert rc == 0 and ctx.startswith("agentik-session: profile 'frontier'; the meter "), ctx


def test_a_helper_counts_as_launched(box):
    rc, ctx, _ = _start(box, CLAUDE_SESSION_HELPER="1")
    assert rc == 0 and ctx.startswith("agentik-session: profile 'builder'; the meter "), ctx


# ---- line 2, R2: status and status --json ---------------------------------------------------

@pytest.mark.parametrize("launched", [False, True])
def test_status_says_once_whether_the_launcher_started_the_session(box, launched):
    extra = {"CLAUDE_SESSION_PROFILE": "frontier"} if launched else {}
    assert _start(box, **extra)[0] == 0
    rc, out, err = _run(box, "status", **extra)
    first = out.splitlines()[0]
    assert rc == 0 and "role:frontier" in first, (out, err)
    assert out.count(R2) == (0 if launched else 1), out
    if not launched:
        assert f"role:frontier{R2}" in first and len(R2.split()) <= 8
    rc, out, err = _run(box, "status", "--json", **extra)
    d = json.loads(out)
    assert rc == 0 and d["launched"] is launched, out


def test_status_json_gains_launched_alone(box):
    assert _start(box, CLAUDE_SESSION_PROFILE="frontier")[0] == 0
    sdir = resolver.session_dir(resolver.state_dir(_env(box[0])), SID)
    from claude_session import meter, plug
    was = plug.envelope("meter", meter.load(sdir))      # what `status --json` printed at the pin
    rc, out, _ = _run(box, "status", "--json")
    d = json.loads(out)
    assert rc == 0 and list(d) == list(was) + ["launched"], out
    assert {k: v for k, v in d.items() if k != "launched"} == was


def test_status_reads_the_mark_the_hook_left(box):
    """A `status` from another shell, without the launcher's variable, reads the session's."""
    assert _start(box, CLAUDE_SESSION_PROFILE="frontier")[0] == 0
    rc, out, _ = _run(box, "status")
    assert rc == 0 and R2 not in out, out


# ---- line 3, R3: an unknown profile told to the session --------------------------------------

def test_an_unknown_plain_name_is_told_to_the_session(box):
    rc, ctx, err = _start(box, CLAUDE_SESSION_PROFILE=NAME)
    names = ", ".join(_shipped_names())
    assert rc == 0, err
    assert ctx == (f"agentik-session: unknown profile '{NAME}'; nothing of a profile applies to "
                   f"this session. Known: {names}; start with CLAUDE_SESSION_PROFILE=<one> "
                   "agentik session run"), ctx
    assert f"SessionStart resolved nothing: unknown profile '{NAME}'" in err


@pytest.mark.parametrize("bad", ["on seat", "it's", 'say "x"', "x" * 65])
def test_a_name_not_a_plain_word_is_withheld(box, bad):
    rc, ctx, err = _start(box, CLAUDE_SESSION_PROFILE=bad)
    assert rc == 0 and ctx.startswith("agentik-session: unknown profile (withheld); "), ctx
    assert bad not in ctx and "resolved nothing" in err


def test_a_name_from_a_layer_file_is_withheld(box):
    repo_file(box[1], f"session: {{profile: {NAME}}}\n")
    rc, ctx, err = _start(box)
    assert rc == 0 and ctx.startswith("agentik-session: unknown profile (withheld); "), ctx
    assert NAME not in ctx + err


def test_a_user_profile_is_counted_never_named(box):
    user_file(box[0], "profiles:\n  zz-own:\n    description: own\n")
    rc, ctx, _ = _start(box, CLAUDE_SESSION_PROFILE=NAME)
    assert rc == 0 and " and 1 more from " in ctx and "zz-own" not in ctx, ctx


# ---- line 4, R4: decisions.dir leaves --------------------------------------------------------

def test_the_resolved_file_holds_no_decisions_key(box):
    assert _start(box)[0] == 0
    sdir = resolver.session_dir(resolver.state_dir(_env(box[0])), SID)
    doc = json.loads((sdir / "resolved.json").read_text())
    assert "decisions" not in doc and "decisions" not in doc["session"], list(doc)
    assert "decisions" not in resolver.SECTIONS and "decisions" not in resolver.DEPENDENT
    assert "decisions" not in open(SHIPPED).read()


PIN_EXITS = {"profile": 0, "rules": 0, "status": 0, "doctor --json": 2,
             "describe --json": 0, "describe config --json": 0,
             "describe config --json session.model": 0}


def test_a_layer_that_sets_decisions_is_warned_and_breaks_no_verb(box):
    repo_file(box[1], "decisions: {dir: ledgers}\n")
    assert _start(box)[0] == 0
    for verb, want in PIN_EXITS.items():
        rc, out, err = _run(box, *verb.split())
        assert rc == want and "Traceback" not in err, (verb, rc, out, err)
    d = json.loads(_run(box, "describe", "config", "--json")[1])
    hits = [w for w in d["warnings"] if w["key"].split(".")[0] == "decisions"]
    assert [(w["key"], w["reason"]) for w in hits] == [("decisions", "unknown")], d["warnings"]
    assert hits[0]["line"] == 1 and "ledgers" not in json.dumps(d)


def test_a_user_profile_that_sets_decisions_is_warned(box):
    user_file(box[0], "defaults:\n  decisions: {dir: ledgers}\n")
    d = json.loads(_run(box, "describe", "config", "--json")[1])
    assert [(w["key"], w["reason"]) for w in d["warnings"]
            if w["key"] == "decisions"] == [("decisions", "unknown")], d["warnings"]


# ---- line 5: a launched frontier session's whole line is the pin's ---------------------------

def test_a_launched_frontier_session_reads_byte_for_byte_as_at_the_pin(box):
    rc, ctx, _ = _start(box, CLAUDE_SESSION_PROFILE="frontier")
    t = str(box[0].parent)
    assert rc == 0 and ctx.replace(t, "<T>") == PIN_FRONTIER, ctx


# ---- R6: no description names a model version ------------------------------------------------

def test_no_description_names_a_model_version():
    import re
    _, profiles = resolver.load_profiles({"HOME": "/nonexistent"})
    for name, body in profiles.items():
        assert not re.search(r"\d\.\d", str((body or {}).get("description"))), name


def test_the_hooks_mark_reads_as_launch_profile():
    assert hooks.launched({}) is False
    assert hooks.launched({"CLAUDE_SESSION_PROFILE": "frontier"}) is True
    assert hooks.launched({"CLAUDE_SESSION_CHAIN": "a-b"}) is True
    assert hooks.launched({"CLAUDE_SESSION_CHAIN": "a b"}) is False
