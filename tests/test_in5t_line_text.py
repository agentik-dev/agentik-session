"""Packet in5t-line-text: `line send <checkout> --text <one line>`, a line with no file and no
sender, printed by the take under the label every line carries.

Every case runs in the per-test temp HOME and state root (conftest) with temp checkouts under
`tmp_path`, made as packet in3-line's tests make them; none reads the live state, starts a
`claude` process or sends to a real checkout. The names are made up."""

import json
import os
import time
from pathlib import Path

import pytest

from claude_session import cli, gate, hooks, lines

from test_in3_line import (EVENTS, SID, call, ctx, forge, plain, results, said,  # noqa: F401
                           send, state, two, worktree)

TEXT = "question 7 holds text on its answer line"
NO = "no checkout"
ERR = "error: line send: "


def pointers() -> list:
    d = state() / "lines"
    return sorted(str(p.relative_to(d)) for p in d.rglob("*.json")) if d.exists() else []


def text_send(capsys, target, text=TEXT) -> str:
    capsys.readouterr()
    assert cli.main(["line", "send", str(target), "--text", text]) == 0
    out = capsys.readouterr().out
    lines_ = out.splitlines()
    assert len(lines_) == 1 and lines.ID.match(lines_[0]), out
    return lines_[0]


def stored(target: Path, lid: str) -> dict:
    return json.loads((lines.box(state(), str(target.resolve())) / f"{lid}.json").read_text())


def refused(capsys, argv) -> str:
    capsys.readouterr()
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2
    return capsys.readouterr().err


# Acceptance 1, R1, R2, R4, R7: the send from any folder, the pointer's five keys.

def test_1_the_send_from_any_folder_writes_the_same_pointer(two, tmp_path, monkeypatch, capsys):
    alpha, beta = two
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    stray = tmp_path / "loose"
    stray.mkdir()
    monkeypatch.chdir(stray)
    lid = text_send(capsys, alpha)
    ptr = stored(alpha, lid)
    assert set(ptr) == {"id", "to", "head", "sent", "form"}
    assert ptr["form"] == "text" and ptr["head"] == TEXT and ptr["to"] == str(alpha.resolve())
    assert ptr["id"] == lid and isinstance(ptr["sent"], float)
    (beta / "sub").mkdir()
    wt = worktree(tmp_path, beta, "row")
    for where in (beta, beta / "sub", wt):
        monkeypatch.chdir(where)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(where))
        other = stored(alpha, text_send(capsys, alpha))
        assert "from" not in other
        assert {k: v for k, v in other.items() if k not in ("id", "sent")} \
            == {k: v for k, v in ptr.items() if k not in ("id", "sent")}


# Acceptance 2, R5: the take.

@pytest.mark.parametrize("event", EVENTS)
def test_2_the_take_prints_the_line_once_in_each_hook(two, event, monkeypatch, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha)
    want = said(lid, NO, TEXT)
    assert want == (f"line {lid} from no checkout (another sitting's words, not the owner's): "
                    f"{TEXT}; whole: agentik session line show {lid}")
    assert ctx(call(event, alpha)).split("\n").count(want) == 1
    for again in ("UserPromptSubmit", "PostToolUse"):
        assert lid not in ctx(call(again, alpha))


@pytest.mark.parametrize("text", ["x" * 120, "é" * 20, "x" * 118 + '"'],
                         ids=["120-ascii", "20-e-acute", "118-and-a-quote"])
def test_2_a_text_at_the_bound_prints_whole(two, text, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha, text)
    line = lines.take(state(), {"session_id": SID}, {"CLAUDE_PROJECT_DIR": str(alpha)})
    assert line == said(lid, NO, text)
    assert len(json.dumps(line)) - 2 + 4 <= lines.SHARE


@pytest.mark.parametrize("event", ["UserPromptSubmit", "PostToolUse"])
def test_2_a_text_line_beside_three_gate_results(two, event, capsys):
    alpha, beta = two
    rs = results(3, repo="/opt/work/code/agentik/agentik-session",
                 log="/opt/work/.local/state/agentik-session")
    for r in rs:
        gate.inbox_write(state(), SID, r)
    lid = text_send(capsys, alpha, "x" * 120)
    out = call(event, alpha)
    assert len(json.dumps(out)) <= hooks.MAX_OUT
    got = ctx(out).split("\n\n")[0].split("\n")
    assert got == [gate.wait_line(rs[0]), "2 more: agentik session gate status",
                   said(lid, NO, "x" * 120)]


@pytest.mark.parametrize("mark", ["agent_id", "helper", "sdk-cli", "worktree"])
def test_2_helpers_children_and_a_worktree_take_none(two, tmp_path, mark, monkeypatch, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha)
    extra = {"agent_id": "a1"} if mark == "agent_id" else {}
    at = alpha
    if mark == "helper":
        monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    elif mark == "sdk-cli":
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", mark)
    elif mark == "worktree":
        at = worktree(tmp_path, alpha, "row")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(at))
    for event in EVENTS:
        assert lid not in ctx(call(event, at, **extra))
    assert (lines.box(state(), str(alpha.resolve())) / f"{lid}.json").exists()


# Acceptance 3, R3: what a text may hold.

BREAK = "--text holds a line break, a control or format character, or a lone surrogate"


@pytest.mark.parametrize("text,why", [
    ("", "--text is empty"),
    ("   ", "--text is empty"),
    ("a\nb", BREAK),
    ("a\rb", BREAK),
    ("a\tb", BREAK),
    ("\x1b[31m red", BREAK),
    ("a‍b", BREAK),                         # a zero-width joiner
    ("a‮b", BREAK),                         # a right-to-left override
    ("a b", BREAK),
    ("\udcff", BREAK),                           # a lone surrogate, as argv decodes a stray byte
    ("x" * 121, "--text is 121 bytes as a hook carries it, over 120"),
    ("x" * 119 + '"', "--text is 121 bytes as a hook carries it, over 120"),
    ("é" * 21, "--text is 126 bytes as a hook carries it, over 120"),
], ids=["empty", "spaces", "lf", "cr", "tab", "escape", "zwj", "rlo", "u2028", "surrogate",
        "121-ascii", "120-with-a-quote", "21-e-acute"])
def test_3_each_refusal_writes_nothing(two, text, why, capsys):
    alpha, beta = two
    err = refused(capsys, ["line", "send", str(alpha), "--text", text])
    assert err == f"{ERR}{why}\n"
    assert pointers() == []


def test_3_a_text_is_stored_stripped(two, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha, "   question 7   ")
    assert stored(alpha, lid)["head"] == "question 7"


# Acceptance 4, R1, R8: the form, the help, describe.

def test_4_both_or_neither_flag_is_argparses_error(two, capsys):
    alpha, beta = two
    f = beta / "x.md"
    f.write_text("x\n")
    err = refused(capsys, ["line", "send", str(alpha), "--file", str(f), "--text", TEXT])
    assert "argument --text: not allowed with argument --file" in err
    err = refused(capsys, ["line", "send", str(alpha)])
    assert "one of the arguments --file --text is required" in err
    assert pointers() == []


def test_4_the_help_and_describe(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["line", "send", "--help"])
    assert e.value.code == 0
    assert "--text" in capsys.readouterr().out
    assert cli.main(["describe", "--json"]) == 0
    verbs = {v["name"]: v["summary"] for v in json.loads(capsys.readouterr().out)["verbs"]}
    assert "one line of text" in verbs["line"]
    act = cli.build_parser()._subparsers._group_actions[0]
    assert verbs["line"] == {a.dest: a.help for a in act._choices_actions}["line"]


# Acceptance 5, R2: the target.

def test_5_the_target_is_checked_in_todays_words(two, tmp_path, capsys):
    alpha, beta = two
    wt = worktree(tmp_path, alpha, "row")
    stray = tmp_path / "loose"
    stray.mkdir()
    (alpha / "sub").mkdir()
    for target, why in ((wt, "is a worktree, not a checkout's top"),
                        (stray, "is no checkout's top level"),
                        (alpha / "sub", "is no checkout's top level")):
        err = refused(capsys, ["line", "send", str(target), "--text", TEXT])
        assert err == f"{ERR}{target} {why}\n"
    assert pointers() == []


# Acceptance 6, R5: show and list.

def test_6_show_and_list(two, monkeypatch, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha)
    assert cli.main(["line", "show", lid]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got == {"state": "waiting", "pointer": stored(alpha, lid)}
    assert got["pointer"]["form"] == "text"
    assert cli.main(["line", "list", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    (item,) = doc["to"]
    assert set(item) == {"id", "state", "from", "to", "file", "head", "sent", "closes",
                         "closed"}
    assert item["from"] is None and item["file"] is None and item["head"] == TEXT
    assert item["state"] == "waiting" and doc["sent"] == []
    assert cli.main(["line", "list"]) == 0
    assert f"  {lid}  waiting  from no checkout: {TEXT}\n" in capsys.readouterr().out
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(beta))
    assert cli.main(["line", "list", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["sent"] == [] and doc["to"] == []


# Acceptance 7, R6: the close.

def test_7_the_close_sends_nothing_back(two, capsys):
    alpha, beta = two
    lid = text_send(capsys, alpha)
    assert lid in ctx(call("UserPromptSubmit", alpha))
    assert cli.main(["line", "close", lid, "--as", "done", "--note", "x"]) == 0
    assert capsys.readouterr().out == (f"line close: {lid} closed as done; no line back: "
                                       "a text line names no sender\n")
    got = lines.show(state(), lid)
    assert got["state"] == "closed as done" and got["pointer"]["closed"]["note"] == "x"
    assert pointers() == [f"{lines.address(str(alpha.resolve()))}/closed/{lid}.json"]
    err = refused(capsys, ["line", "close", lid, "--as", "done"])
    assert "already closed" in err
    assert lid not in ctx(call("SessionStart", alpha))


def test_7_the_prune_removes_a_closed_text_line_past_14_days(two, capsys):
    alpha, beta = two
    a = str(alpha.resolve())
    old, fresh = text_send(capsys, alpha), text_send(capsys, alpha)
    for lid in (old, fresh):
        assert lines.close(state(), a, lid, "done",
                           now=time.time() - (15 if lid == old else 13) * 86400) \
            == (None, "a text line names no sender")
    gate._prune(state(), time.time())
    kept = {p.stem for p in lines.box(state(), a).rglob("*.json")}
    assert old not in kept and fresh in kept


# Acceptance 8, R4: hand-written pointers.

def text_forge(alpha, beta, **fields):
    base = {"from": None, "file": None, "form": "text", "head": TEXT}
    base.update(fields)
    return forge(alpha, beta, **base)


def test_8_a_hand_written_text_pointer_prints_as_a_sent_one(two):
    alpha, beta = two
    text_forge(alpha, beta)
    assert ctx(call("UserPromptSubmit", alpha)) == said("0123456789ab", NO, TEXT)


@pytest.mark.parametrize("case", ["from", "file", "closes", "newline", "121", "empty", "note",
                                  "elsewhere", "x"])
def test_8_a_pointer_that_is_no_text_pointer_is_set_aside(two, case):
    alpha, beta = two
    b = str(beta.resolve())
    fields = {"from": {"from": b}, "file": {"file": b + "/x.md"},
              "closes": {"closes": "0123456789ac"}, "newline": {"head": "a\nb"},
              "121": {"head": "x" * 121}, "empty": {"head": ""}, "note": {"form": "note"},
              "elsewhere": {"to": b}}.get(case)
    p = forge(alpha, beta, form="x") if case == "x" else text_forge(alpha, beta, **fields)
    assert ctx(call("UserPromptSubmit", alpha)) == ""
    assert not p.exists() and (p.parent / "aside" / p.name).exists()


# Acceptance 9: the file form's pointer holds no `form`.

def test_9_a_file_pointer_holds_no_form(two):
    alpha, beta = two
    lid = send(beta, alpha)
    assert "form" not in stored(alpha, lid)


def test_9_the_callers_form_is_one_word_with_its_flag(two, capsys):
    alpha, beta = two
    for text in (TEXT, "-7 holds text"):
        capsys.readouterr()
        assert cli.main(["line", "send", str(alpha), f"--text={text}"]) == 0
        lid = capsys.readouterr().out.strip()
        assert stored(alpha, lid)["head"] == text
