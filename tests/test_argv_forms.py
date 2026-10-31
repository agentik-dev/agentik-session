"""sc1 ruling 1: every argv form means one thing on every interpreter.

Before 3.12 argparse spends a `nargs="*"` or `"?"` positional on an empty match at the first
option, so `gate run R --label t -- cmd` and `charter close --exit X FILE` exit 2 under 3.9,
and it strips a later `--` out of a command, so `gate run R -- git log -- path` silently runs
`git log path`. The table is what 3.12.7's stock parser answers. It is read here under the
interpreter the suite runs on and, in a child, under the floor; a refused form is pinned by
its exit alone, since the message varies by version.
"""
import contextlib
import io
import json
import os
import subprocess

import pytest

from claude_session import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = "/usr/bin/python3"

ACCEPTED = [
    # the two named forms
    ("gate run R --label t -- true", {"repo": "R", "label": "t", "command": ["true"]}),
    ("charter close --exit X F", {"action": "close", "exit": "X", "args": ["F"]}),
    # a star positional after an option, before an option, with and without --
    ("gate run --label t R -- true", {"repo": "R", "label": "t", "command": ["true"]}),
    ("gate run R --label t true", {"repo": "R", "label": "t", "command": ["true"]}),
    ("gate run R --label=t -- true", {"repo": "R", "label": "t", "command": ["true"]}),
    ("gate run R --la t -- true", {"repo": "R", "label": "t", "command": ["true"]}),
    ("gate run R --label t -- a b", {"repo": "R", "label": "t", "command": ["a", "b"]}),
    ("gate run R a --label t", {"repo": "R", "label": "t", "command": ["a"]}),
    ("gate run R a b", {"repo": "R", "command": ["a", "b"]}),
    ("gate run R -- true", {"repo": "R", "command": ["true"]}),
    ("gate run -- R true", {"repo": "R", "command": ["true"]}),
    ("gate run R --wait --label t", {"repo": "R", "wait": True, "command": []}),
    ("gate run R --label t --", {"repo": "R", "label": "t", "command": []}),
    ("gate run R --", {"repo": "R", "command": []}),
    ("gate run R --label t -1", {"repo": "R", "label": "t", "command": ["-1"]}),
    ("gate run R --wall 5 --lock a --lock b -- x",
     {"repo": "R", "wall": 5, "lock": ["a", "b"], "command": ["x"]}),
    # after --, an option's name is the command's, and a later -- stays in it
    ("gate run R --label t -- --wait x", {"label": "t", "wait": False, "command": ["--wait", "x"]}),
    ("gate run R -- --wait x", {"repo": "R", "wait": False, "command": ["--wait", "x"]}),
    ("gate run R -- git log -- path", {"repo": "R", "command": ["git", "log", "--", "path"]}),
    ("gate run --label t R -- git log -- path",
     {"repo": "R", "label": "t", "command": ["git", "log", "--", "path"]}),
    ("gate run R --label t -- git log -- path",
     {"repo": "R", "label": "t", "command": ["git", "log", "--", "path"]}),
    ("gate run R a -- b -- c", {"repo": "R", "command": ["a", "b", "--", "c"]}),
    ("gate run R -- --", {"repo": "R", "command": ["--"]}),
    ("gate run R -- -- --", {"repo": "R", "command": ["--", "--"]}),
    ("gate run R --lock a -- x -- --", {"repo": "R", "lock": ["a"], "command": ["x", "--", "--"]}),
    # the verbs with no optional positional
    ("gate wait I", {"id": "I"}),
    ("gate wait --timeout 3 I", {"id": "I", "timeout": 3.0}),
    ("gate wait I --json", {"id": "I", "json": True}),
    ("gate status --json", {"json": True}),
    ("hook Stop", {"event": "Stop"}),
    # charter: any positional, before and after an option
    ("charter close F --exit X", {"action": "close", "exit": "X", "args": ["F"]}),
    ("charter close --exit X", {"action": "close", "exit": "X", "args": []}),
    ("charter close", {"action": "close", "exit": None, "args": []}),
    ("charter close --exit X -- F", {"action": "close", "exit": "X", "args": ["F"]}),
    ("charter close --dir D --exit X F", {"action": "close", "dir": "D", "exit": "X", "args": ["F"]}),
    ("charter close --exit X F G", {"action": "close", "exit": "X", "args": ["F", "G"]}),
    ("charter open goal", {"action": "open", "args": ["goal"]}),
    ("charter open --dir D goal", {"action": "open", "dir": "D", "args": ["goal"]}),
    ("charter open goal --dir D", {"action": "open", "dir": "D", "args": ["goal"]}),
    ("charter check A B", {"action": "check", "args": ["A", "B"]}),
    ("charter check", {"action": "check", "args": []}),
    ("charter check -- -A", {"action": "check", "args": ["-A"]}),
    ("charter --exit X close F", {"action": "close", "exit": "X", "args": ["F"]}),
    ("charter -- close F", {"action": "close", "args": ["F"]}),
    # start and run: claude's arguments
    ("start C", {"config": "C", "claude_args": []}),
    ("start C -n", {"config": "C", "dry_run": True, "claude_args": []}),
    ("start -n C", {"config": "C", "dry_run": True, "claude_args": []}),
    ("start C a b", {"config": "C", "claude_args": ["a", "b"]}),
    ("start C -n a b", {"config": "C", "dry_run": True, "claude_args": ["a", "b"]}),
    ("start C --max-turns 3 a", {"config": "C", "max_turns": 3, "claude_args": ["a"]}),
    ("start C --nested -- --model x", {"config": "C", "nested": True, "claude_args": ["--model", "x"]}),
    ("start C -- --model x -- y", {"config": "C", "claude_args": ["--model", "x", "--", "y"]}),
    ("start -- C --model", {"config": "C", "claude_args": ["--model"]}),
    ("run", {"claude_args": [], "chain": None}),
    ("run a", {"claude_args": ["a"]}),
    ("run -- -p x", {"claude_args": ["-p", "x"]}),
    ("run --chain N", {"chain": "N", "claude_args": []}),
    ("run --chain N -- -p x", {"chain": "N", "claude_args": ["-p", "x"]}),
    ("run --chain N a", {"chain": "N", "claude_args": ["a"]}),
    ("run --cap 3 --chain N -- -p x -- y", {"cap": "3", "chain": "N", "claude_args": ["-p", "x", "--", "y"]}),
    ("run -- --chain N", {"chain": None, "claude_args": ["--chain", "N"]}),
    ("run a --chain N", {"chain": "N", "claude_args": ["a"]}),
    # a -- before the verb
    ("-- gate run R x", {"repo": "R", "command": ["x"]}),
    ("gate -- run R x", {"repo": "R", "command": ["x"]}),
    ("-- budget", {"cmd": "budget"}),
    # a nargs="?" positional has the same bug
    ("config list", {"action": "list", "name": None}),
    ("config show N", {"action": "show", "name": "N"}),
    ("config show --stored N", {"action": "show", "stored": True, "name": "N"}),
    ("config show N --stored", {"action": "show", "stored": True, "name": "N"}),
    ("config show --stored", {"action": "show", "stored": True, "name": None}),
    ("config new N --from M", {"action": "new", "From": "M", "name": "N"}),
    ("config new --from M N", {"action": "new", "From": "M", "name": "N"}),
    ("config new --from M --description D N", {"action": "new", "From": "M", "description": "D", "name": "N"}),
    ("config show -- N", {"action": "show", "name": "N"}),
    # an option's own value is `--`, attached: before 3.11 argparse drops it, and the option
    # reads as [] (Amendment 1, F3)
    ("charter close --exit=-- F", {"action": "close", "exit": "--", "args": ["F"]}),
    ("charter close F --exit=--", {"action": "close", "exit": "--", "args": ["F"]}),
    ("gate run R --label=-- -- x", {"repo": "R", "label": "--", "command": ["x"]}),
    ("gate run R --lock=-- --lock=b x", {"repo": "R", "lock": ["--", "b"], "command": ["x"]}),
    ("gate wait --json I", {"id": "I", "json": True}),
]

REFUSED = [
    "gate run",
    "gate run --label t",
    "gate run R --bogus",
    "gate run R --bogus -- x",
    "gate run R --label t --bogus x",
    "gate run R --label -- x",
    "charter bogus",
    "charter close --exit -- F",
    "charter close --bogus F",
    "start C --model x",
    "run --chain",
    "hook Bogus",
    "config",
    "gate",
    "gate run R --wall=-- x",
    "gate wait --timeout=-- I",
    "config -- -x",
    "config show N -- -x",
    "charter -- -x",
    "gate run --bogus=--",
]

# A refusal's message names the argument as it was typed, on every interpreter (F4).
MESSAGES = [
    ("config -- -x", "'-x'"),
    ("charter -- -x", "'-x'"),
    ("config show N -- -x", "-x"),
    ("gate run R --wall=-- x", "'--'"),
]

# Refused by 3.12's stock parser, a positional on both sides of an option, and read alike on
# every interpreter by the intermixed parse: one reversible widening, in sc1's charter.
WIDER = [
    ("gate run R a --label t b", {"repo": "R", "label": "t", "command": ["a", "b"]}),
    ("charter close F --exit X G", {"action": "close", "exit": "X", "args": ["F", "G"]}),
]

# Read in a child: the argv forms' table, under whichever interpreter runs this script.
CHILD = """
import contextlib, io, json, sys
sys.path.insert(0, sys.argv[1])
from claude_session import cli
out, said = {}, {}
for form in json.loads(sys.stdin.read()):
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            ns = cli.build_parser().parse_args(form.split())
        out[form] = {k: v for k, v in vars(ns).items() if k != "func"}
    except SystemExit as e:
        out[form] = e.code
    said[form] = err.getvalue()
print(json.dumps({"out": out, "said": said, "version": sys.version.split()[0]}))
"""


def said(form):
    """(the namespace as a dict, or the exit code of a refusal; what it wrote on stderr)."""
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            ns = cli.build_parser().parse_args(form.split())
    except SystemExit as e:
        return e.code, err.getvalue()
    return vars(ns), err.getvalue()


def parse(form):
    return said(form)[0]


def marked(text):
    """The parser's mark, raw or as a message's repr prints it."""
    return "\0" in text or "\\x00" in text


@pytest.mark.parametrize("form,want", ACCEPTED + WIDER, ids=[f for f, _ in ACCEPTED + WIDER])
def test_a_form_means_what_312_says(form, want):
    got = parse(form)
    assert isinstance(got, dict), "refused, exit %r" % (got,)
    assert {k: got[k] for k in want} == want


@pytest.mark.parametrize("form", REFUSED)
def test_a_refused_form_exits_2(form):
    assert parse(form) == 2


@pytest.mark.skipif(not os.access(FLOOR, os.X_OK), reason="no %s on this machine" % FLOOR)
def test_the_table_holds_under_the_floor():
    """The whole table under /usr/bin/python3, whichever interpreter runs the suite."""
    forms = [f for f, _ in ACCEPTED + WIDER] + REFUSED
    r = subprocess.run([FLOOR, "-I", "-B", "-c", CHILD, ROOT], input=json.dumps(forms),
                       capture_output=True, text=True, timeout=60,
                       cwd=os.path.dirname(ROOT))
    assert r.returncode == 0, r.stderr
    child = json.loads(r.stdout)
    got = child["out"]
    wrong = {f: got[f] for f, want in ACCEPTED + WIDER
             if not isinstance(got[f], dict) or {k: got[f].get(k) for k in want} != want}
    wrong.update({f: got[f] for f in REFUSED if got[f] != 2})
    wrong.update({f: child["said"][f] for f, text in MESSAGES if text not in child["said"][f]})
    wrong.update({f: "the mark" for f in forms if marked(json.dumps(got[f])) or marked(child["said"][f])})
    assert not wrong


@pytest.mark.parametrize("form", [f for f, _ in ACCEPTED + WIDER] + REFUSED)
def test_no_value_or_message_holds_the_mark(form):
    got, err = said(form)
    if isinstance(got, dict):
        got = {k: v for k, v in got.items() if k != "func"}
    assert not marked(repr(got) + json.dumps(err))


@pytest.mark.parametrize("form,text", MESSAGES)
def test_a_refusal_names_the_argument_as_typed(form, text):
    got, err = said(form)
    assert got == 2 and text in err


def test_help_names_the_positionals():
    """The intermixed parse must not lose a positional from a verb's help."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as e:
        cli.build_parser().parse_args(["gate", "run", "--help"])
    assert e.value.code == 0
    assert "repo" in out.getvalue() and "command" in out.getvalue()
