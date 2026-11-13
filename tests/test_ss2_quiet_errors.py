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
SAVES = ("--save", "--save user", "--save repo")          # every `--save` form of `set`
VERBS = ("profile", "profile frontier", "rules", "reconcile", "status", "config", "config list",
         "budget", "report", "measure", "admission", "mod", "gates", "charter check",
         "checkpoint", "gate status", "unattended status", "start", "start frontier --dry-run",
         "set effort high", "describe --json", "describe config --json", "doctor --json",
         "doctor", "describe", "set effort high --save", "set cap sonnet --save",
         "set fill 50 --save") + tuple(f"set tier.build sonnet {s}" for s in SAVES)
_DRIVER = r"""
import io, sys, traceback
from contextlib import redirect_stderr, redirect_stdout
from claude_session import cli
for argv in sys.argv[1:]:
    out, err, rc = io.StringIO(), io.StringIO(), 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(argv.split())
        except SystemExit as e:
            rc = e.code
        except BaseException:
            print("Traceback " + traceback.format_exc(), file=sys.stderr)
    sys.stdout.write("== " + argv + " rc=" + str(rc) + "\n" + out.getvalue() + "\n"
                     + err.getvalue() + "\n")
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


# ---- R5: seven summaries respoken (design/15 §5.3) -------------------------------------------

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


# ---- review 1, R1-F1: `set ... --save` over a broken file, in each of the five it writes ------

SAVE_FILES = {"user": ".claude/agentik/profiles.yaml", "ccd": "ccd/agentik/profiles.yaml",
              "old-user": ".claude/claude-code-session/profiles.yaml",
              "repo": ".claude/agentik/config.yaml",
              "old-repo": ".claude/claude-code-session/config.yaml"}


def _save_box(tmp_path, n, where, raw: bytes):
    home, cwd = tmp_path / f"h{n}", tmp_path / f"c{n}"
    home.mkdir()
    cwd.mkdir()
    p = (cwd if where.endswith("repo") else home) / SAVE_FILES[where]
    p.parent.mkdir(parents=True)
    p.write_bytes(raw)
    return home, cwd, p, ({"CLAUDE_CONFIG_DIR": str(home / "ccd")} if where == "ccd" else {})


def _drive(home, cwd, argv, **extra):
    p = subprocess.run([sys.executable, "-c", _DRIVER, *argv], cwd=str(cwd),
                       env=_env(home, PYTHONPATH=str(ROOT / "plugin" / "lib"), **extra),
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    return p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace")


@pytest.mark.parametrize("where", sorted(SAVE_FILES))
def test_save_over_a_broken_file_withholds_its_text(tmp_path, where):
    for n, shape in enumerate(BROKEN):
        text = shape.replace("{{", "{").replace("}}", "}").replace(X, TOPIC)
        home, cwd, path, extra = _save_box(tmp_path, n, where, text.encode())
        both = _drive(home, cwd, [f"set tier.build sonnet {s}" for s in SAVES], **extra)
        assert MARK not in both and "Traceback" not in both, (where, shape, both)


@pytest.mark.parametrize("where", sorted(SAVE_FILES))
def test_save_over_a_file_not_utf8_is_that_file_error(tmp_path, where):
    raw = f"gate:\n  ntfy_topic: {TOPIC}".encode() + b"\xff\n"
    home, cwd, path, extra = _save_box(tmp_path, 0, where, raw)
    form = "--save repo" if where.endswith("repo") else "--save user"
    p = subprocess.run([str(S), "set", "tier.build", "sonnet", *form.split()], cwd=str(cwd),
                       env=_env(home, **extra), stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=60)
    err = p.stderr.decode(errors="replace")
    assert p.returncode == 2 and p.stdout == b"", (p.returncode, err)
    assert MARK not in err and "Traceback" not in err, err
    assert err.startswith(f"error: {path}: ") and err.endswith("; nothing written\n"), err
    assert path.read_bytes() == raw


# ---- review 1, R1-F2: a key's name read from a file is the file's text -----------------------

KEY_SHAPES = {"user-models": ("user", f"models:\n  {TOPIC}: 1x\n", "models",
                              "a key (withheld) must be a positive integer (a window in tokens)"),
              "user-respawn": ("user", f"defaults:\n  respawn:\n    {TOPIC}: 1\n", "respawn",
                               "a key (withheld) is not a respawn key (cap, floor, settle)"),
              "repo-respawn": ("repo", f"session:\n  respawn:\n    {TOPIC}: 1\n", "respawn",
                               "a key (withheld) is not a respawn key (cap, floor, settle)"),
              "repo-models": ("repo", f"models:\n  {TOPIC}: 1x\n", None, None)}


@pytest.mark.parametrize("case", sorted(KEY_SHAPES))
def test_a_key_name_from_a_file_is_withheld(box, case):
    home, cwd = box
    where, text, section, why = KEY_SHAPES[case]
    path = user_file(home, text) if where == "user" else repo_file(cwd, text)
    for extra in ({}, {"CLAUDE_CODE_SESSION_ID": SID}):
        both = _drive(home, cwd, VERBS, **extra)
        assert MARK not in both and "Traceback" not in both, (case, extra, both)
    p = subprocess.run([str(S), "rules"], cwd=str(cwd), env=_env(home),
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    if section:
        assert p.returncode == 2 and p.stderr.decode() == f"error: {path}: {section}: {why}\n"
    ev = {"session_id": SID, "hook_event_name": "SessionStart", "cwd": str(cwd),
          "source": "startup", "transcript_path": str(home / "none.jsonl")}
    h = subprocess.run([str(S), "hook", "SessionStart"], cwd=str(cwd), input=json.dumps(ev).encode(),
                       env=_env(home, CLAUDE_CODE_SESSION_ID=SID, CLAUDE_PROJECT_DIR=str(cwd)),
                       capture_output=True, timeout=60)
    both = h.stdout.decode(errors="replace") + h.stderr.decode(errors="replace")
    assert MARK not in both and "Traceback" not in both, (case, both)
    if section:
        assert f"{path}: {section}: {why}" in both, both


# ---- review 1, R1-F3: a profile name not read from a file prints as at the pin ---------------

WORD = "-".join(("zq4k", "typed", "name"))                 # built at run time, a made-up word


@pytest.mark.parametrize("verb", ["rules", "reconcile"])
def test_a_profile_name_from_the_environment_prints(box, verb):
    home, cwd = box
    p = subprocess.run([str(S), verb], cwd=str(cwd),
                       env=_env(home, CLAUDE_SESSION_PROFILE=WORD), stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=60)
    err = p.stderr.decode()
    assert p.returncode == 2 and f"unknown profile '{WORD}'; known: frontier, " in err, err


def test_a_profile_name_from_the_environment_prints_in_session_start(box):
    home, cwd = box
    ev = {"session_id": SID, "hook_event_name": "SessionStart", "cwd": str(cwd),
          "source": "startup", "transcript_path": str(home / "none.jsonl")}
    h = subprocess.run([str(S), "hook", "SessionStart"], cwd=str(cwd), input=json.dumps(ev).encode(),
                       env=_env(home, CLAUDE_CODE_SESSION_ID=SID, CLAUDE_PROJECT_DIR=str(cwd),
                                CLAUDE_SESSION_PROFILE=WORD), capture_output=True, timeout=60)
    assert f"unknown profile '{WORD}'; known: frontier, " in h.stderr.decode(), h.stderr


def test_a_profile_name_from_the_caller_prints(box, monkeypatch):
    from claude_session import resolver
    home, cwd = box
    env = _env(home)
    with pytest.raises(resolver.ResolveError) as e:
        resolver.resolve(cwd, SID, env, profile=WORD, overlay={})
    assert str(e.value).startswith(f"unknown profile '{WORD}'; known: frontier, ")


# ---- review 1, N1: the reconciler's threshold error names the key, never the value -----------

def test_a_threshold_value_is_withheld(box):
    home, cwd = box
    (cwd / "t.json").write_text('{"repos": []}')
    repo_file(cwd, f"session:\n  reconcile:\n    tree: t.json\n    thresholds: {{eff.idle: {TOPIC}}}\n")
    p = subprocess.run([str(S), "reconcile"], cwd=str(cwd), env=_env(home),
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    err = p.stderr.decode()
    assert p.returncode == 2 and MARK not in err, err
    assert "session.reconcile.thresholds.eff.idle is not a number; a threshold is a number, " \
           "0 or more" in err, err
