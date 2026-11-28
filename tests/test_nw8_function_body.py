"""nw8: `function NAME {` opens its body as `NAME() {` does, for `_commands` and the older rules."""
import pytest

from claude_session import instructionguard, shellreader
from test_g10_push_guard import HEAD, TUID, _reason, _refused_dir, _run, box  # noqa: F401
from test_g2b_gates import _bash, _decision


def _read(text):
    return [c[0] for c in shellreader._commands(text)]


def test_b1_the_body_is_a_command_of_its_own_and_the_other_forms_keep_their_reading():
    assert _read("function f { git add -A; }; f") == [["function", "f"], ["{", "git", "add", "-A"],
                                                      ["}"], ["f"]]
    assert _read("function f() { git add -A; }")[3] == ["{", "git", "add", "-A"]
    assert _read("function f\n{ git add -A; }")[:2] == [["function", "f"], ["{", "git", "add", "-A"]]
    assert _read("echo 'function f { git add -A; }'") == [["echo", "function f { git add -A; }"]]
    for text in ("function f '{' x; }", "function f \\{ x; }", "function { x; }", "function f g { x; }"):
        assert _read(text)[0][-2:] == ["{", "x"], text


def test_b2_the_sweep_rule_refuses_the_body(box):
    for line in ("function f { git add -A; }; f", "git add -A"):
        d, reason = _reason(_run(box, line, box.a))
        assert d == "deny" and reason.startswith(HEAD) and "the sweep rule" in reason, line
        assert (_refused_dir(box) / TUID).read_text() == "sweep\n", line


def test_b2_the_gated_file_rule_strict_reading_refuses_the_body(box, monkeypatch):
    monkeypatch.setattr(instructionguard, "_loose_gated", lambda *a, **k: None)    # g2b's strict_only
    (box.a / ".claude").mkdir(exist_ok=True)
    (box.a / ".claude" / "edit-gates").write_text("CLAUDE.md\n")
    for line in ("function f { cp a CLAUDE.md; }; f", "f() { cp a CLAUDE.md; }; f"):
        assert _decision(instructionguard.check(_bash(line, box.a), box.env))[0] == "deny", line


@pytest.mark.parametrize("line", ["for x in a; do function f { git add -A; }; f; done",
                                  "if true; then function f { git add -A; }; fi",
                                  "function f { function g { git add -A; }; g; }; f",
                                  "echo $(function f { case x in a) git add -A;; esac; }; f)"])
def test_nw9_b1_b2_the_sweep_rule_refuses_the_body_after_a_lead_nested_and_in_a_substitution(box, line):
    d, reason = _reason(_run(box, line, box.a))
    assert d == "deny" and reason.startswith(HEAD) and "the sweep rule" in reason, line


def test_nw9_b3_a_function_word_after_an_argument_or_in_quotes_keeps_its_reading():
    assert _read("echo do function f {") == [["echo", "do", "function", "f", "{"]]


def test_nw9_b3_a_function_in_a_quoted_message_keeps_its_reading():
    assert _read('git commit -m "then function f { git add -A; }"') == [
        ["git", "commit", "-m", "then function f { git add -A; }"]]
