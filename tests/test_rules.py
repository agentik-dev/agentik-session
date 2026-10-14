"""S21: the priority and pacing defaults, the SessionStart block and `rules`' text."""

import re
from pathlib import Path

import pytest

from claude_session import resolver
from claude_session.yamlsubset import load

ROOT = Path(__file__).resolve().parents[1]

S1 = ("harm: a reproduced bug that can do harm (a wrong write, data loss, a leaked secret, "
      "a safety path) or the repo's own gate red on main; it goes first, ahead of the "
      "current goal")
S2 = ("blocks the goal: an unmet acceptance criterion of the current goal, a defect in a new "
      "user's first run, or a dependency that holds the goal")
S3 = "the build order: the goal's next slice, then the repo's pending list"
S4 = ("the rest: review notes, polish, refactors, docs; filed in NICE_TO_HAVE.md with its "
      "level, taken only when S1 to S3 have nothing ready or on an S3 slice's path; never "
      "ahead of S3")
BLOCK = ("; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest; the Next "
         "act takes the highest ready; pacing: wake in the act's last tool call, a pending "
         "helper is the wake (one fallback, 1800s+), WAITING 3 stops the loop; "
         "agentik-session rules prints both")
BUGS = ("A bug ranks by harm and what it blocks, never by how sure or cheap its fix is; with "
        "neither it is S4, below S3, however easy.",
        "Met in an S3 slice, it is fixed there only on the slice's path, else filed S4 with a "
        "one-line repro and the slice goes on.",
        "One S4 item a sitting at most, only when S1 to S3 have none ready; a review's notes "
        "are S4 unless they show harm (S1) or an unmet criterion (S2).")


def rules():
    from claude_session import rules as mod
    return mod


def resolved(tmp_path, profile=None):
    env = {"HOME": str(tmp_path / "home"), "XDG_STATE_HOME": str(tmp_path / "state")}
    return resolver.resolve(tmp_path, "t", env, profile=profile).sections["session"]


def session(priority=None, pacing=None):
    r = rules()
    pr = {**r.PRIORITY, "levels": dict(r.PRIORITY["levels"]), **(priority or {})}
    return {"priority": pr, "pacing": {**r.PACING, **(pacing or {})}}


def test_s21_default_texts_are_the_shipped_ones(tmp_path):
    r = rules()
    assert r.LEVELS == ("S1", "S2", "S3", "S4")
    assert r.PRIORITY == {"enabled": True, "levels": {"S1": S1, "S2": S2, "S3": S3, "S4": S4}}
    assert r.PACING == {"enabled": True, "fallback": 1800, "waiting": 3}
    s = resolved(tmp_path)
    assert s["priority"] == r.PRIORITY and s["pacing"] == r.PACING


def test_s21_default_every_shipped_profile_keeps_both_on(tmp_path):
    _, profiles = resolver.load_profiles({"HOME": str(tmp_path / "home")})
    assert len(profiles) >= 10
    for name in profiles:
        s = resolved(tmp_path, profile=name)
        assert s["priority"]["enabled"] is True and s["pacing"]["enabled"] is True, name


@pytest.mark.parametrize("sess,want", [
    ("on", BLOCK),
    ("absent", BLOCK),                                   # N6: a missing key is on
    ("priority-off", "; pacing: wake in the act's last tool call, a pending helper is the "
                     "wake (one fallback, 1800s+), WAITING 3 stops the loop; agentik-session "
                     "rules prints both"),
    ("pacing-off", "; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the "
                   "rest; the Next act takes the highest ready; agentik-session rules prints both"),
    ("both-off", ""),
])
def test_s21_clause(sess, want):
    sess = {"on": session(), "absent": {},
            "priority-off": session(priority={"enabled": False}),
            "pacing-off": session(pacing={"enabled": False}),
            "both-off": session({"enabled": False}, {"enabled": False})}[sess]
    assert rules().clause(sess) == want


def test_s21_clause_bound_at_320_bytes():
    r = rules()
    assert len(BLOCK.encode()) == 266          # agentik-r1: the tool's name is one byte longer
    levels = {n: "x" * 30 + ": t" for n in r.LEVELS}          # labels cut to 24
    big = session({"levels": levels}, {"fallback": 3600, "waiting": 9})
    line = r.clause(big)
    assert "S1 " + "x" * 24 + ", S2" in line and "x" * 25 not in line
    assert "3600s+" in line and "WAITING 9 " in line
    assert len(line.encode()) == 320 <= 320      # agentik-r1: one byte longer, at the bound
    odd = session({"levels": {**levels, "S1": "a;bé: t", "S2": ": no label"}})
    line = r.clause(odd)
    assert line.startswith("; priority: S1 a, S2, S3 ") and "é" not in line
    assert "\n" not in line and len(line.encode()) <= 320


def test_s21_render_lists_levels_rules_and_pacing():
    out = rules().render(session())
    for name, text in (("S1", S1), ("S2", S2), ("S3", S3), ("S4", S4)):
        assert f"{name} {text}" in out
    for rule in ("an item gets its level when filed", "the Next act is the highest level ready",
                 "a signed-off component's finding is work only as a reproduced S1",
                 "each Handover lists the open items by level, highest first"):
        assert rule in out
    assert "never a turn of its own" in out and "one fallback of 1800 s or more" in out
    assert "an act ready: the minimum delay" in out
    assert "WAITING <n>: <what>; <how to tell>" in out and "n = 3" in out
    assert "a packet or brief bounds them" in out and "no hook enforces them" in out


def test_s21_render_names_an_off_part():
    out = rules().render(session(priority={"enabled": False}, pacing={"fallback": 2400}))
    assert "priority: off" in out and S1 not in out
    assert "one fallback of 2400 s or more" in out and "pacing: on" in out


def test_s21_ranks_bugs():
    out = rules().render({})
    for sentence in BUGS:
        assert sentence in out


@pytest.mark.parametrize("text,want", [
    ("## Handover\n- open by level: S2 the doctor's remedy\n- exit taken: x\n\n## Next act\n",
     True),
    ("## Handover\n- exit taken: x\n\n## Next act\n- open by level: none yet\n", False),
    ("## Done-ness\n- open by level: none yet\n\n## Handover\n\n## Next act\nx\n", False),
], ids=["listed", "missing", "outside-handover"])
def test_s21_handover(text, want):
    r = rules()
    assert r.HANDOVER == "- open by level:"
    assert r.handover_listed(text) is want


def test_s21_docs_name_the_keys_and_quote_the_texts():
    skill = (ROOT / "plugin/skills/session/SKILL.md").read_text()
    assert "\n## Priority and pacing\n" in skill
    runbook = (ROOT / "RUNBOOK.md").read_text()
    assert "\n### Priority and pacing\n" in runbook
    for doc in (skill, runbook):
        for word in ("agentik-session rules", "session.priority", "session.pacing", "WAITING"):
            assert word in doc
    blocks = [b for b in re.findall(r"```yaml\n(.*?)```", runbook, re.S)
              if "priority:" in b or "pacing:" in b]
    assert blocks                                        # N2: the examples parse
    for b in blocks:
        load(b)
