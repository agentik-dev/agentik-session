"""Row ss4: five more places stop printing a layer file's value or key (ss2's review 2, R2-F1 to
R2-F5). A `ntfy_topic: <word>` line mis-indented under another key turns the secret into that
key's value: a value of the wrong kind is named by its kind, never shown; a key read from a file
is withheld; what a caller typed still prints. ss2's verb list and driver are reused, never
copied. Every line runs in a temp HOME, state, config and cache folder, and a temp cwd."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_ak5_plug import ROOT, S, SHIPPED, _env, repo_file, user_file
from test_ss2_quiet_errors import EVENTS, VERBS, _DRIVER

TOPIC = "-".join(("v3kp", "made", "up", "word"))       # built at run time, a made-up word
MARK = TOPIC.split("-")[0]
SID = "ss4-sess-0000-1111"
MIS = f"\n      ntfy_topic: {TOPIC}\n"                 # the line, mis-indented under a key
ADMIT = json.dumps({"subagentType": "build", "model": "sonnet"}).encode()


@pytest.fixture
def box(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    return home, cwd


def _run(box, *argv, stdin=b"", **extra):
    home, cwd = box
    p = subprocess.run([str(S), *argv], cwd=str(cwd), input=stdin, capture_output=True,
                       env=_env(home, CLAUDE_PROJECT_DIR=str(cwd), **extra), timeout=120)
    return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")


def _hook(box, event="SessionStart", transcript=None, **extra):
    home, cwd = box
    ev = {"session_id": SID, "hook_event_name": event, "cwd": str(cwd), "source": "startup",
          "transcript_path": transcript or str(home / "none.jsonl"), "permission_mode": "default",
          "tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": {"stdout": ""},
          "prompt": "hello", "trigger": "manual", "reason": "other", "model": "m"}
    return _run(box, "hook", event, stdin=json.dumps(ev).encode(), CLAUDE_CODE_SESSION_ID=SID,
                **extra)


def _overlay(box, doc):
    from claude_session import resolver
    d = resolver.state_dir(_env(box[0])) / "overlays"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{SID}.json").write_text(json.dumps(doc))


# ---- line 1, R1: the window note ------------------------------------------------------------

NOTE = "session.admission.window: is not auto, five_hour or none; read as auto"


@pytest.mark.parametrize("where", ["user", "repo", "overlay"])
@pytest.mark.parametrize("shape", ["mapping", "list", "number", "word"])
def test_the_window_note_names_no_value(box, where, shape):
    home, cwd = box
    val = {"mapping": MIS.rstrip("\n"), "list": f" [{TOPIC}]", "number": " 7",
           "word": f" {TOPIC}"}[shape]
    if where == "user":
        user_file(home, "defaults:\n  admission:\n    window:" + val + "\n")
    elif where == "repo":
        repo_file(cwd, "session:\n  admission:\n    window:" + val + "\n")
    else:
        _overlay(box, {"admission": {"window": {"mapping": {"ntfy_topic": TOPIC}, "list": [TOPIC],
                                                "number": 7, "word": TOPIC}[shape]}})
    if where != "user":
        rc, out, err = _hook(box)
        assert rc == 0 and MARK not in out + err, (out, err)
    rc, out, err = _run(box, "admission", "admit", "--session", SID, stdin=ADMIT,
                        CLAUDE_CODE_SESSION_ID=SID)
    assert MARK not in out and MARK not in err, (out, err)
    assert NOTE in json.loads(out)["notes"], out
    assert f"agentik-session: {NOTE}" in err, err


# ---- line 2, R2: the reconciler's `tree` and `record` ---------------------------------------

KINDS = {"a mapping": MIS.rstrip("\n"), "a list": f" [{TOPIC}]", "a number": " 7"}


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_tree_names_its_kind(box, kind):
    repo_file(box[1], "session:\n  reconcile:\n    tree:" + KINDS[kind] + "\n")
    rc, out, err = _run(box, "reconcile")
    assert rc == 2 and MARK not in out + err, (rc, out, err)
    assert f"session.reconcile.tree must be a file name, not {kind}\n" in err, err


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_the_record_names_its_kind(box, kind):
    (box[1] / "t.json").write_text('{"repos": []}')
    repo_file(box[1], "session:\n  reconcile:\n    tree: t.json\n    record:" + KINDS[kind] + "\n")
    rc, out, err = _run(box, "reconcile")
    assert rc == 2 and MARK not in out + err, (rc, out, err)
    assert (f"session.reconcile.record must be a relative folder inside the repo, not {kind}\n"
            in err), err


def test_a_tree_typed_as_a_string_still_prints(box):
    repo_file(box[1], "session:\n  reconcile:\n    tree: t.json\n    record: /abs\n")
    rc, out, err = _run(box, "reconcile")
    assert rc == 2 and "session.reconcile.tree t.json is not a readable tree file" in err, err
    assert "session.reconcile.record must be a relative folder inside the repo, not '/abs'" \
           in err, err


# ---- line 3, R3: a key from the overlay at SessionStart -------------------------------------

def test_an_overlay_key_is_withheld_at_session_start(box):
    _overlay(box, {"reconcile": {TOPIC: [[1]]}})
    rc, out, err = _hook(box)
    assert rc == 0 and MARK not in out + err, (rc, out, err)
    assert ("agentik-session: SessionStart resolved nothing: a key (withheld): only flat lists "
            "are in the subset") in err, err


# ---- line 4, R4: the gate's log -------------------------------------------------------------

@pytest.mark.parametrize("key,why", [("load_ceiling", "no positive number"),
                                     ("max_running", "no positive whole number")])
def test_the_gate_log_names_no_value(box, key, why):
    from claude_session import resolver
    for val in (MIS.replace("\n  ", "\n").rstrip("\n"), f" [{TOPIC}]", f" {TOPIC}"):
        user_file(box[0], f"gate:\n  {key}:" + val + "\n")
        lines = []
        out = resolver.gate_config(_env(box[0]), lines.append)
        assert lines == [f"gate: {key} is {why}; the default stands"], (val, lines)
        assert key not in out and MARK not in repr(out), out


# ---- line 5, R5: the unknown profile's list -------------------------------------------------

def _shipped():
    from claude_session.yamlsubset import load
    with open(SHIPPED, encoding="utf-8") as f:
        return ", ".join(load(f.read())["profiles"])


@pytest.mark.parametrize("how", ["rules", "profile", "start", "SessionStart"])
def test_an_unknown_profile_lists_the_shipped_names_and_a_count(box, how):
    u = user_file(box[0], f"profiles:\n  {TOPIC}:\n    lane: seat\n")
    if how == "rules":
        rc, out, err = _run(box, "rules", CLAUDE_SESSION_PROFILE="zz-typed")
    elif how == "SessionStart":
        rc, out, err = _hook(box, CLAUDE_SESSION_PROFILE="zz-typed")
    else:
        rc, out, err = _run(box, how, "zz-typed")
    assert MARK not in out + err, (out, err)
    assert "'zz-typed'" in err and f"{_shipped()} and 1 more from {u}" in err, err


def test_bare_profile_still_lists_every_name(box):
    user_file(box[0], f"profiles:\n  {TOPIC}:\n    lane: seat\n")
    rc, out, err = _run(box, "profile")
    assert rc == 0 and TOPIC in out, (out, err)


# ---- line 6: ss2's matrix with the new shapes ------------------------------------------------

SHAPES = {"window-user": ("user", "defaults:\n  admission:\n    window:" + MIS),
          "window-repo": ("repo", "session:\n  admission:\n    window:" + MIS),
          "tree": ("repo", "session:\n  reconcile:\n    tree:" + MIS),
          "record": ("repo", "session:\n  reconcile:\n    tree: t.json\n    record:" + MIS),
          "load_ceiling": ("user", "gate:\n  load_ceiling:" + MIS.replace("\n  ", "\n")),
          "max_running": ("user", "gate:\n  max_running:" + MIS.replace("\n  ", "\n")),
          "profile": ("user", f"profiles:\n  {TOPIC}:\n    lane: seat\n"),
          "overlay": ("overlay", {"reconcile": {TOPIC: [[1]]}})}
# Not errors: a verb that shows a file's values (review 1, N3) or lists every profile's name (R5)
# may hold the word, but never on a line that reports something wrong.
SHOWS = {"profile frontier", "describe config --json"}
LISTS = {"profile", "config", "config list", "doctor", "doctor --json", "describe config --json"}
WRONG = re.compile(r"error|unknown|message|withheld|resolves nothing|Error|not ", re.I)


def _lay(box, case):
    where, body = SHAPES[case]
    (box[1] / "t.json").write_text('{"repos": []}')
    if where == "user":
        user_file(box[0], body)
    elif where == "repo":
        repo_file(box[1], body)
    else:
        _overlay(box, body)


@pytest.mark.parametrize("case", sorted(SHAPES))
def test_no_verb_prints_the_new_shapes(box, case):
    home, cwd = box
    _lay(box, case)
    for extra in ({}, {"CLAUDE_CODE_SESSION_ID": SID}, {"CLAUDE_SESSION_PROFILE": "zz-typed"}):
        p = subprocess.run([sys.executable, "-c", _DRIVER, *VERBS], cwd=str(cwd),
                           env=_env(home, PYTHONPATH=str(ROOT / "plugin" / "lib"), **extra),
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
        text = p.stdout.decode(errors="replace") + p.stderr.decode(errors="replace")
        # the overlay's nested list stops `describe config --json` in a traceback, as at the
        # pin (a NICE row); its message names no key now (R3)
        assert case == "overlay" or "Traceback" not in text, (case, extra, text)
        for part in re.split(r"^== ", text, flags=re.M)[1:]:
            verb = part.split(" rc=", 1)[0]
            free = LISTS if case == "profile" else SHOWS
            for line in part.splitlines():
                if MARK in line:
                    assert verb in free and not WRONG.search(line), (case, extra, verb, line)


@pytest.mark.parametrize("case", sorted(SHAPES))
def test_no_hook_prints_the_new_shapes(box, case):
    _lay(box, case)
    for event in EVENTS:
        rc, out, err = _hook(box, event)
        assert MARK not in out + err and "Traceback" not in err, (case, event, out, err)


# ---- R6: the sweep's places -------------------------------------------------------------------

def test_a_windows_key_from_a_file_is_withheld_and_a_slot_prints(box):
    user_file(box[0], f"defaults:\n  admission:\n    windows:\n      {TOPIC}: auto\n"
                      "      Wed-1500Z: maybe\n")
    rc, out, err = _run(box, "admission", "admit", "--session", SID, stdin=ADMIT,
                        CLAUDE_CODE_SESSION_ID=SID)
    assert MARK not in out + err, (out, err)
    notes = json.loads(out)["notes"]
    assert "session.admission.windows: a key (withheld) is not a slot like Wed-1500Z with " \
           "auto, five_hour or none; ignored" in notes, notes
    assert "session.admission.windows: 'Wed-1500Z' is not a slot like Wed-1500Z with " \
           "auto, five_hour or none; ignored" in notes, notes


def test_a_checkpoint_zone_from_a_file_is_withheld(box):
    from claude_session import sessionconfig
    with pytest.raises(ValueError) as e:
        sessionconfig.SessionConfig(name="x", checkpoint={TOPIC: 1}).validate()
    assert MARK not in str(e.value) and str(e.value).startswith(
        "checkpoint: a key (withheld) is not a zone; zones are "), e.value


def test_config_show_of_an_unknown_name_counts_the_file_names(box):
    u = user_file(box[0], f"profiles:\n  {TOPIC}:\n    lane: seat\n")
    rc, out, err = _run(box, "config", "show", "zz-typed")
    assert rc != 0 and MARK not in out + err, (out, err)
    assert "'zz-typed'" in err and f" and 1 more from {u}" in err, err


# ---- review 1, R1-F1: the charter folder's value is named by its kind ------------------------

CDIR = {"a mapping": (MIS.rstrip("\n"), {"ntfy_topic": TOPIC}),
        "a list": (f" [{TOPIC}]", [TOPIC]), "a number": (" 7", 7)}
LAYERS = {"repo": Path(".claude") / "agentik" / "config.yaml",
          "local": Path(".claude") / "agentik" / "config.local.yaml",
          "old": Path(".claude") / "claude-code-session" / "config.yaml"}


def _charter_dir(box, where, kind):
    text, doc = CDIR[kind]
    if where == "overlay":
        _overlay(box, {"charter": {"required": True, "dir": doc}})
        return
    p = box[1] / LAYERS[where]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("session:\n  charter:\n    required: true\n    dir:" + text + "\n")


@pytest.mark.parametrize("where", ["repo", "local", "old", "overlay"])
@pytest.mark.parametrize("kind", sorted(CDIR))
def test_a_charter_dir_of_another_kind_is_named_by_its_kind(box, tmp_path, where, kind):
    from test_hook_meter import transcript
    _charter_dir(box, where, kind)
    rc, out, err = _hook(box)
    assert rc == 0 and MARK not in out + err, (out, err)
    assert f"charter: none open today under ? (session.charter.dir holds {kind}), run " in out, out
    t = transcript(tmp_path, 179000)
    rc, out, err = _hook(box, "PostToolUse", transcript=str(t))
    assert rc == 0 and MARK not in out + err, (out, err)
    line = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert (f"; charter ? (session.charter.dir holds {kind}); bring the charter current"
            in line), line


@pytest.mark.parametrize("kind", sorted(CDIR))
def test_the_checkpoint_line_under_a_launcher_names_no_value(kind):
    from claude_session import hooks
    from types import SimpleNamespace
    d = hooks._charter({"session": {"charter": {"dir": CDIR[kind][1]}}})
    assert d == f"? (session.charter.dir holds {kind})"
    m = SimpleNamespace(ceilings={"context": 9, "turns": 9}, pct_context=90.0, context=8,
                        pct_turns=1.0, turns=1, used_pct=90.0)
    for files in (None, ["<this sitting's charter>"]):
        line = hooks._checkpoint_out(m, d, files)["hookSpecificOutput"]["additionalContext"]
        assert MARK not in line, line


def test_a_charter_dir_typed_as_a_word_still_reads():
    from claude_session import hooks
    assert hooks._charter({"session": {"charter": {"dir": "h/s"}}}) == "h/s"
    assert hooks._charter({"session": {"charter": {}}}) == "history/sittings"


# ---- review 1, R1-F2: a zone typed on the command line prints ---------------------------------

def test_a_typed_zone_prints(box):
    rc, out, err = _run(box, "set", "checkpoint", '{"wind_down": 3}', CLAUDE_CODE_SESSION_ID=SID)
    assert rc == 1 and "error: checkpoint: unknown zone 'wind_down'; zones are clear" in err, err


def test_a_zone_from_a_file_stays_withheld_under_set(box):
    user_file(box[0], f"profiles:\n  balanced:\n    checkpoint:\n      {TOPIC}: 1\n")
    rc, out, err = _run(box, "set", "effort", "high", CLAUDE_CODE_SESSION_ID=SID)
    assert MARK not in out + err, (rc, out, err)
