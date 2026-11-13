"""Row ss2: an error names the file, the line and the reason, in every verb and every hook. A
layer file that cannot be parsed or resolved is never quoted: no byte of a line's text (a
`gate.ntfy_topic` value among them) reaches stdout or stderr. ak5's broken shapes are reused
from its test, never copied. Every line runs in a temp HOME and a temp cwd."""
import json
import subprocess
import sys

import pytest

from test_ak5_plug import BROKEN, ROOT, S, SID, X, _env, repo_file, user_file

TOPIC = "-".join(("q7vn", "made", "up", "topic"))      # built at run time, a made-up word
MARK = TOPIC.split("-")[0]
VERBS = ("profile", "profile frontier", "rules", "reconcile", "status", "config", "config list",
         "budget", "report", "measure", "admission", "mod", "gates", "charter check",
         "checkpoint", "gate status", "unattended status", "start", "start frontier --dry-run",
         "set effort high", "describe --json", "describe config --json", "doctor --json",
         "doctor", "describe")
_DRIVER = r"""
import io, sys, traceback
from contextlib import redirect_stderr, redirect_stdout
from claude_session import cli
for argv in sys.argv[1:]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            cli.main(argv.split())
        except SystemExit:
            pass
        except BaseException:
            print("Traceback " + traceback.format_exc(), file=sys.stderr)
    sys.stdout.write("== " + argv + "\n" + out.getvalue() + "\n" + err.getvalue() + "\n")
"""


@pytest.fixture
def box(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    return home, cwd


def _place(box, where, shape):
    home, cwd = box
    text = shape.replace("{{", "{").replace("}}", "}").replace(X, TOPIC)
    if where == "user":
        return user_file(home, text)
    return repo_file(cwd, "session:\n" + "".join(
        "  " + ln + "\n" for ln in text.rstrip("\n").split("\n")))


# ---- line 1: every verb, every broken shape, both files --------------------------------------

@pytest.mark.parametrize("where", ["user", "repo"])
def test_no_verb_prints_a_broken_file_text(box, where):
    home, cwd = box
    assert len(BROKEN) == 20
    for shape in BROKEN:
        _place(box, where, shape)
        for extra in ({}, {"CLAUDE_CODE_SESSION_ID": SID}):
            p = subprocess.run([sys.executable, "-c", _DRIVER, *VERBS], cwd=str(cwd),
                               env=_env(home, PYTHONPATH=str(ROOT / "plugin" / "lib"), **extra),
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
            both = p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace")
            assert MARK not in both, (where, shape, extra, both)
            assert "Traceback" not in both, (where, shape, extra, both)


# ---- line 2: profile, rules and reconcile name the file, the line and the reason ------------

@pytest.mark.parametrize("verb", ["profile", "rules", "reconcile"])
def test_the_three_verbs_name_file_line_and_reason(box, verb):
    home, cwd = box
    u = user_file(home, f"gate:\n  ntfy_topic:\n    {TOPIC}")
    p = subprocess.run([str(S), verb], cwd=str(cwd), env=_env(home), stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=60)
    err = p.stderr.decode()
    assert p.returncode == 2, (p.returncode, err)
    assert p.stdout == b"" and MARK not in err, err
    lines = err.splitlines()
    assert lines and lines[-1].startswith("error: ")
    assert lines[-1].endswith(f"{u}: line 3: not a `key: value` line"), err


# ---- line 3: each hook, fed its event over a broken user file -------------------------------

EVENTS = tuple(json.loads((ROOT / "plugin" / "hooks" / "hooks.json").read_text())["hooks"])


@pytest.mark.parametrize("where", ["user", "repo"])
@pytest.mark.parametrize("event", EVENTS)
def test_no_hook_prints_a_broken_file_text(box, event, where):
    home, cwd = box
    for shape in (BROKEN[0], BROKEN[9]):
        _place(box, where, shape)
        ev = {"session_id": SID, "hook_event_name": event, "cwd": str(cwd),
              "transcript_path": str(home / "none.jsonl"), "permission_mode": "default",
              "source": "startup", "tool_name": "Bash", "tool_input": {"command": "true"},
              "tool_response": {"stdout": ""}, "prompt": "hello", "trigger": "manual",
              "reason": "other", "model": "m"}
        p = subprocess.run([str(S), "hook", event], cwd=str(cwd), input=json.dumps(ev).encode(),
                           env=_env(home, CLAUDE_CODE_SESSION_ID=SID, CLAUDE_PROJECT_DIR=str(cwd)),
                           capture_output=True, timeout=60)
        both = p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace")
        assert MARK not in both and "Traceback" not in both, (event, where, shape, both)


# ---- line 4: the control, an unknown profile name -------------------------------------------

def test_an_unknown_profile_from_a_file_is_withheld(box):
    """The name is the repo file's text: withheld, as the plug's reads give it since ak5."""
    home, cwd = box
    repo_file(cwd, f"session: {{profile: {TOPIC}}}\n")
    p = subprocess.run([str(S), "rules"], cwd=str(cwd), env=_env(home),
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    err = p.stderr.decode()
    assert p.returncode == 2 and MARK not in err, err
    assert err.startswith("error: unknown profile (withheld); known: "), err


def test_an_unknown_profile_on_the_line_reads_as_at_the_pin(box):
    """The name is the argument, no file's text: the message is the pin's, the name in it."""
    p = subprocess.run([str(S), "profile", "zz-nope"], cwd=str(box[1]), env=_env(box[0]),
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    assert p.returncode == 1
    assert p.stderr.decode().startswith("error: unknown profile 'zz-nope'. Known: ")


# ---- R5: the respeak of seven summaries (design/15 §5.3) ------------------------------------

def test_the_respoken_summaries():
    from claude_session import plug
    assert plug.SUMMARIES["permission_mode"] == (
        "What Claude Code may do without asking, as `start` sets it for the session.")
    assert plug.SUMMARIES["lane"] == (
        "Where the work runs: the seat, the local model for subagents, or the local model alone.")
    assert plug.SUMMARIES["tiers.*.model"] == "The model a subagent in this role runs on."
    assert plug.SUMMARIES["tiers.*.effort"] == "The effort a subagent in this role runs at."
    assert plug.SUMMARIES["pacing.fallback"] == (
        "The seconds the session waits on a pending subagent before it wakes on its own.")
    # kept: `admission.mix` decides no fit, and `reconcile.record` names where records go
    assert plug.SUMMARIES["admission.*"] == (
        "Read by the admission module; `agentik session rules` says how it binds.")
    assert plug.SUMMARIES["reconcile.*"] == "Read by the reconciler's detectors each time they run."
