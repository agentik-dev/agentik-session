"""plugin/commands: six files, each one verb, under thirty lines (§2.5)."""
import re
from pathlib import Path

import pytest

from claude_session import cli

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / "plugin" / "commands"
VERBS = ("status", "profile", "set", "checkpoint", "doctor", "report")
SKILL = ROOT / "plugin" / "skills" / "session" / "SKILL.md"


def test_exactly_the_six_commands():
    assert sorted(p.stem for p in COMMANDS.glob("*.md")) == sorted(VERBS)


@pytest.mark.parametrize("verb", VERBS)
def test_command_runs_one_verb_under_thirty_lines(verb):
    text = (COMMANDS / f"{verb}.md").read_text()
    lines = text.splitlines()
    assert len(lines) < 30
    assert lines[0] == "---"
    head = text.split("---")[1]
    assert re.search(r'^description: "[^"]+"$', head, re.M)
    assert "allowed-tools: [Bash(agentik-session *)]" in head
    runs = re.findall(r"agentik-session (\S+) \$ARGUMENTS", text)
    assert runs == [verb]
    assert f"!`agentik session {verb} $ARGUMENTS`" in lines


def test_every_command_verb_is_a_cli_verb():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    assert set(VERBS) <= set(sub.choices)


def test_skill_sections_and_ceiling():
    text = SKILL.read_text()
    heads = [l for l in text.splitlines() if l.startswith("## ")]
    for h in ("## Profiles", "## Set", "## Budget", "## The charter"):
        assert h in heads
    assert len(text.splitlines()) < 500
    head = text.split("---")[1]
    assert "  - Bash(agentik-session *)\n  - Read\n" in head
    for word in ("CHECKPOINT", "EXIT", "charter open", "charter check", "charter close"):
        assert word in text
