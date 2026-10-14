"""S21: the priority and pacing defaults, the SessionStart block and `rules`' text."""

import json
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
         "helper is the wake (one fallback, 1800s+), WAITING 3 stops the loop, a meter "
         "wait never; agentik-session rules prints both")
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
                     "wake (one fallback, 1800s+), WAITING 3 stops the loop, a meter wait "
                     "never; agentik-session rules prints both"),
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
    assert len(BLOCK.encode()) == 286          # S29: ", a meter wait never", 20 bytes
    levels = {n: "x" * 30 + ": t" for n in r.LEVELS}          # labels cut to 24
    big = session({"levels": levels}, {"fallback": 3600, "waiting": 9})
    line = r.clause(big)
    assert "S1 " + "x" * 24 + ", S2" in line and "x" * 25 not in line
    assert "3600s+" in line and "WAITING 9 stops the loop, a meter wait never" in line
    assert len(line.encode()) == 320 <= 320      # S29: cut at the bound, the tail's name lost
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


METER = ("waiting on the usage meter (room for 0, or a usage limit hit) is not WAITING: the "
         "Next act stays the act, the wake is the band's reset or one fallback, whichever is "
         "first, and it never counts toward the stop")


def test_s29_pace_says_a_meter_wait_is_not_waiting():
    r = rules()
    assert len(r.PACE) == 5 and r.PACE[3].startswith("waiting on an outside party")
    assert r.PACE[4] == METER
    out = r.render(session())
    assert "  4. waiting on an outside party" in out and f"  5. {METER}\n" in out
    assert out.index("  4. ") < out.index("  5. ") < out.index("a packet or brief bounds")
    assert METER not in r.render(session(pacing={"enabled": False}))


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


# ---- S30: the idle wake follows the prompt cache's lifetime in force -------------------

S30_1H = ", cache 1h: idle wakes <=3300s"
S30_5M = ", cache 5m: no keep-warm wakes"
S30_TAIL = "; agentik-session rules prints both"
S30_NONE = "no usage reading and no override"


def _s30_band(p=41, p7=None, ahead=True):
    from datetime import datetime, timedelta, timezone
    t = datetime.now(timezone.utc) + (timedelta(hours=2) if ahead else -timedelta(minutes=5))
    b = {"mode": "observe", "P": p, "peak": p, "resetsAt": t.isoformat(timespec="seconds")}
    return b if p7 is None else {**b, "P7": p7}


@pytest.mark.parametrize("env,settings,band,want", [
    ({"FORCE_PROMPT_CACHING_5M": "1", "CLAUDE_CODE_PROMPT_CACHE_TTL": "1h",
      "ENABLE_PROMPT_CACHING_1H": "1"}, {"local": "1h"}, 41, ("5m", "FORCE_PROMPT_CACHING_5M")),
    ({"FORCE_PROMPT_CACHING_5M": " TRUE "}, {}, 41, ("5m", "FORCE_PROMPT_CACHING_5M")),
    ({"FORCE_PROMPT_CACHING_5M": "0", "CLAUDE_CODE_PROMPT_CACHE_TTL": "1h"}, {"local": "5m"}, 100,
     ("1h", "CLAUDE_CODE_PROMPT_CACHE_TTL")),
    ({"CLAUDE_CODE_PROMPT_CACHE_TTL": "2h"}, {"local": "5m", "user": "1h"}, 41,
     ("5m", "promptCacheTtl, local settings")),
    ({}, {"project": "5m", "user": "1h"}, 41, ("5m", "promptCacheTtl, project settings")),
    ({}, {"local": "1H", "project": "not json", "user": "1h"}, 100,
     ("1h", "promptCacheTtl, user settings")),
    ({"ENABLE_PROMPT_CACHING_1H": "1"}, {"user": "5m"}, 41, ("5m", "promptCacheTtl, user settings")),
    ({"ENABLE_PROMPT_CACHING_1H": "yes"}, {}, 100, ("1h", "ENABLE_PROMPT_CACHING_1H")),
    ({"CLAUDE_CODE_USE_BEDROCK": "1"}, {}, 41, ("5m", "a cloud provider")),
    ({"CLAUDE_CODE_USE_VERTEX": "0"}, {}, 41, ("1h", "within plan usage, 5h 41%")),
    ({}, {}, 72.5, ("1h", "within plan usage, 5h 72.5%")),
    ({}, {}, 100, ("5m", "past plan usage, 5h 100%")),
    ({}, {}, (60, 100), ("5m", "past plan usage, 7d 100%")),
    ({}, {}, (60, 99.5), ("1h", "within plan usage, 5h 60%")),
    ({}, {}, "past", (None, S30_NONE)),
    ({}, {}, "empty", (None, S30_NONE)),
    ({}, {}, None, (None, S30_NONE)),
    ({}, {}, "text", (None, S30_NONE)),
], ids=["force-first", "force-truthy", "env-before-setting", "bad-env-then-local",
        "project-before-user", "bad-values-skipped", "setting-before-enable", "enable-1h",
        "cloud", "cloud-off", "within", "past-5h", "past-7d", "7d-under", "reset-passed",
        "no-reading", "no-band", "not-a-number"])
def test_s30_lifetime_follows_claude_code_s_order(tmp_path, env, settings, band, want):
    home, cwd = tmp_path / "home", tmp_path / "repo"
    paths = {"local": cwd / ".claude/settings.local.json",
             "project": cwd / ".claude/settings.json", "user": home / ".claude/settings.json"}
    for scope, v in settings.items():
        paths[scope].parent.mkdir(parents=True, exist_ok=True)
        paths[scope].write_text(v if v == "not json" else json.dumps({"promptCacheTtl": v}))
    named = {"past": _s30_band(100, ahead=False), "empty": {"mode": "observe"}, None: None,
             "text": {**_s30_band(), "P": "41"}}
    if band is None or isinstance(band, str):
        b = named[band]
    else:
        b = _s30_band(*band) if isinstance(band, tuple) else _s30_band(band)
    assert rules().lifetime({"HOME": str(home), **env}, cwd, b) == want


def test_s30_clause_names_the_lifetime_when_it_fits():
    r = rules()
    head = BLOCK[:-len(S30_TAIL)]
    assert r.clause(session(), "1h") == head + S30_1H + S30_TAIL
    assert r.clause(session(), "5m") == head + S30_5M + S30_TAIL
    assert len((head + S30_1H + S30_TAIL).encode()) == 316 <= r.BLOCK_MAX
    assert r.clause(session(), None) == r.clause(session()) == BLOCK      # unknown: as before
    off = r.clause(session(pacing={"enabled": False}), "1h")
    assert off == r.clause(session(pacing={"enabled": False})) and "cache" not in off
    levels = {n: "x" * 30 + ": t" for n in r.LEVELS}
    big = session({"levels": levels}, {"fallback": 3600, "waiting": 9})
    assert r.clause(big, "1h") == r.clause(big) and len(r.clause(big).encode()) == 320
    near = session({"levels": {**r.PRIORITY["levels"], "S1": "harmful harm: t"}})
    assert len(r.clause(near).encode()) + len(S30_1H) > r.BLOCK_MAX >= len(r.clause(near).encode())
    assert r.clause(near, "1h") == r.clause(near)                  # never cut for the lifetime


def test_s30_render_item_6_names_the_lifetime():
    r = rules()
    assert len(r.PACE) == 5 and r.WARM == {"1h": 3300, "5m": 270}
    out = r.render(session(), ("1h", "within plan usage, 5h 41%"))
    assert ("  6. the prompt cache lives 1h here (within plan usage, 5h 41%): an idle wait "
            "(items 2, 4 and 5) wakes at most 3300 s apart, whatever the fallback, so the "
            "cache survives; a wake at 3600 s lands past the hour and rewrites the whole "
            "context\n") in out
    assert out.index("  5. ") < out.index("  6. ") < out.index("a packet or brief bounds")
    out = r.render(session(pacing={"fallback": 2400}), ("5m", "CLAUDE_CODE_PROMPT_CACHE_TTL"))
    assert ("  6. the prompt cache lives 5m here (CLAUDE_CODE_PROMPT_CACHE_TTL): any wait past "
            "about 270 s misses it anyway, so an idle wait takes the long fallback (2400 s or "
            "more) and never wakes early just to keep the cache\n") in out
    out = r.render(session())
    assert (f"  6. the prompt cache's lifetime is not known here ({S30_NONE}): on 1h (a "
            "subscription within plan usage) an idle wait wakes at most 3300 s apart; on 5m "
            "(usage credits, an API key, a cloud provider or promptCacheTtl 5m) it takes the "
            "long fallback and never wakes early to keep the cache\n") in out
    assert "  6. " not in r.render(session(pacing={"enabled": False}), ("1h", "x"))


def test_s30_hint():
    r = rules()
    assert r.hint("1h", "within plan usage, 5h 41%") == (
        "cache 1h (within plan usage, 5h 41%): an idle wake waits at most 3300 s, so the "
        "cache survives")
    assert r.hint("5m", "past plan usage, 5h 100%") == (
        "cache 5m (past plan usage, 5h 100%): a wait past about 270 s misses anyway; an idle "
        "wait takes the long fallback, never an early wake to keep the cache")
    assert r.hint(None, S30_NONE) is None


def test_s30_docs_name_the_lifetime():
    skill = (ROOT / "plugin/skills/session/SKILL.md").read_text()
    runbook = (ROOT / "RUNBOOK.md").read_text()
    for doc in (skill, runbook):
        section = doc.split("Priority and pacing\n", 1)[1].split("\n#", 1)[0]
        for word in ("3300", "270", "promptCacheTtl", "within plan usage"):
            assert word in section, word


@pytest.mark.parametrize("name", ["CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                                  "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS",
                                  "CLAUDE_CODE_USE_MANTLE"])
def test_s30_f2_every_documented_provider_is_5m(tmp_path, name):
    env = {"HOME": str(tmp_path / "home"), name: "1"}
    assert rules().lifetime(env, tmp_path, _s30_band(41)) == ("5m", "a cloud provider")


S30_OFF = ", cache off: no keep-warm wakes"
DISABLES = ["DISABLE_PROMPT_CACHING", "DISABLE_PROMPT_CACHING_HAIKU",
            "DISABLE_PROMPT_CACHING_SONNET", "DISABLE_PROMPT_CACHING_OPUS",
            "DISABLE_PROMPT_CACHING_FABLE"]


@pytest.mark.parametrize("name", DISABLES)
def test_s30_f3_a_disabled_cache_reads_off(tmp_path, name):
    r = rules()
    env = {"HOME": str(tmp_path / "home"), name: "1", "CLAUDE_CODE_PROMPT_CACHE_TTL": "1h",
           "ENABLE_PROMPT_CACHING_1H": "1"}
    assert r.lifetime(env, tmp_path, _s30_band(41)) == ("off", name)
    env = {"HOME": str(tmp_path / "home"), name: "0"}
    assert r.lifetime(env, tmp_path, _s30_band(41))[0] == "1h"          # the control


def test_s30_f3_off_gives_no_keep_warm_advice():
    r = rules()
    assert r.clause(session(), "off") == BLOCK[:-len(S30_TAIL)] + S30_OFF + S30_TAIL
    out = r.render(session(), ("off", "DISABLE_PROMPT_CACHING"))
    assert ("  6. the prompt cache is off here (DISABLE_PROMPT_CACHING): no wait keeps it "
            "warm, so an idle wait takes the long fallback (1800 s or more) and never wakes "
            "early to keep a cache\n") in out
    assert "3300" not in out.split("  6. ", 1)[1]
    assert r.hint("off", "DISABLE_PROMPT_CACHING") == (
        "cache off (DISABLE_PROMPT_CACHING): no wait keeps it warm; an idle wait takes the "
        "long fallback, never an early wake to keep a cache")


def test_s30_f4_user_settings_follow_claude_config_dir(tmp_path):
    r = rules()
    home, cfg = tmp_path / "home", tmp_path / "cfg"
    (home / ".claude").mkdir(parents=True)
    cfg.mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"promptCacheTtl": "1h"}))
    (cfg / "settings.json").write_text(json.dumps({"promptCacheTtl": "5m"}))
    env = {"HOME": str(home), "CLAUDE_CONFIG_DIR": str(cfg)}
    assert r.lifetime(env, tmp_path, _s30_band(41)) == ("5m", "promptCacheTtl, user settings")
    (cfg / "settings.json").unlink()                      # HOME's is not read once it moved
    assert r.lifetime(env, tmp_path, _s30_band(41)) == ("1h", "within plan usage, 5h 41%")
    assert r.lifetime({"HOME": str(home)}, tmp_path, _s30_band(41)) == (
        "1h", "promptCacheTtl, user settings")                          # the control


def test_s30_f5_settings_are_read_from_small_regular_files_only(tmp_path):
    import os
    import threading
    r = rules()
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"promptCacheTtl": "5m"}))
    local = tmp_path / ".claude" / "settings.local.json"
    local.parent.mkdir()
    os.mkfifo(local, 0o600)
    env, got = {"HOME": str(home)}, []
    th = threading.Thread(target=lambda: got.append(r.lifetime(env, tmp_path, _s30_band(41))),
                          daemon=True)
    th.start()
    th.join(3)
    if th.is_alive():                                    # unblock the reader before failing
        os.close(os.open(local, os.O_WRONLY | os.O_NONBLOCK))
        th.join(3)
        pytest.fail("a FIFO at settings.local.json blocked the lifetime")
    assert got == [("5m", "promptCacheTtl, user settings")]
    local.unlink()
    local.write_text(json.dumps({"promptCacheTtl": "1h"}) + " " * (1 << 20))   # over the cap
    assert r.lifetime(env, tmp_path, _s30_band(41)) == ("5m", "promptCacheTtl, user settings")
    local.write_text(json.dumps({"promptCacheTtl": "1h"}))                      # the control
    assert r.lifetime(env, tmp_path, _s30_band(41)) == ("1h", "promptCacheTtl, local settings")
