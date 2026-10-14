"""The priority and pacing defaults every sitting meets (packet S21).

Two session keys, `priority` and `pacing`, sit in profiles.yaml's `defaults`; any
layer overrides them field by field, the four level names and their count fixed
(S1 to S4: a layer replaces one level's text, never adds or removes a level), and
`set` never touches them. A key that is absent (a resolved file older than this
module) reads as the default, on.

What a layer may not do: set either key, or `priority.levels`, to null or a
scalar (a merge would delete it: a ResolveError, never a silent delete). What a
layer may do and is dropped: name a field outside them; `normalize` records it
in the resolver's `unknown` list as `<layer>: session.<key>.<field>`, the layer
kept (the doctor reads that list).

The SessionStart block (`clause`) is one line of at most 320 bytes: each label
is its level text to the first colon, at most 24 characters of
`[A-Za-z0-9 '.,-]`, and the integers are bounded (`fallback` 60 to 3600 s,
`waiting` 1 to 9), so four labels at the bound read 319 bytes. No hook enforces
either rule set; `agentik session rules` prints both (`render`).

The prompt cache's lifetime (packet S30) is read, never assumed (`lifetime`): an idle
wait on the 1h lifetime wakes at most 3300 s apart, and on 5m it takes the long fallback,
since any wait past about 270 s misses anyway, as it does with the cache off
(DISABLE_PROMPT_CACHING). The block names it only when it is known
and the whole block still fits BLOCK_MAX; `rules` prints it as pacing item 6, and the
prompt hook as one line (`hint`).
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

LEVELS = ("S1", "S2", "S3", "S4")
PRIORITY = {"enabled": True, "levels": {
    "S1": "harm: a reproduced bug that can do harm (a wrong write, data loss, a leaked "
          "secret, a safety path) or the repo's own gate red on main; it goes first, ahead "
          "of the current goal",
    "S2": "blocks the goal: an unmet acceptance criterion of the current goal, a defect in "
          "a new user's first run, or a dependency that holds the goal",
    "S3": "the build order: the goal's next slice, then the repo's pending list",
    "S4": "the rest: review notes, polish, refactors, docs; filed in NICE_TO_HAVE.md with "
          "its level, taken only when S1 to S3 have nothing ready or on an S3 slice's path; "
          "never ahead of S3"}}
PACING = {"enabled": True, "fallback": 1800, "waiting": 3}
FIELDS = {"priority": ("enabled", "levels"), "pacing": ("enabled", "fallback", "waiting")}
BOUNDS = {"fallback": (60, 3600), "waiting": (1, 9)}
TEXT_MAX = 240
LABEL_MAX = 24
BLOCK_MAX = 320
HANDOVER = "- open by level:"
SEED = HANDOVER + " none yet"

RULES = ("an item gets its level when filed",
         "the Next act is the highest level ready",
         "a signed-off component's finding is work only as a reproduced S1",
         f"each Handover lists the open items by level, highest first (`{HANDOVER} ...`)")
BUGS = ("A bug ranks by harm and what it blocks, never by how sure or cheap its fix is; "
        "with neither it is S4, below S3, however easy.",
        "Met in an S3 slice, it is fixed there only on the slice's path, else filed S4 with "
        "a one-line repro and the slice goes on.",
        "One S4 item a sitting at most, only when S1 to S3 have none ready; a review's notes "
        "are S4 unless they show harm (S1) or an unmet criterion (S2).")
PACE = ("the fallback wakeup rides the message of the act's last tool call, never a turn of "
        "its own",
        "while a helper, a Monitor or a background task is pending, its completion is the "
        "wake: one fallback of {fallback} s or more, never re-armed on a hand-back",
        "an act ready: the minimum delay",
        "waiting on an outside party: the Next act says `WAITING <n>: <what>; <how to "
        "tell>`, a long delay, n the wakes in a row with nothing changed, the loop stopping "
        "at n = {waiting} (a respawn reads n from the charter)",
        "waiting on the usage meter (room for 0, or a usage limit hit) is not WAITING: the "
        "Next act stays the act, the wake is the band's reset or one fallback, whichever is "
        "first, and it never counts toward the stop")
BOUND = ("a packet or brief bounds them: a builder files what lies outside it and takes "
         "none; no hook enforces them")

# The prompt cache's lifetime (packet S30; Claude Code's "How Claude Code uses prompt
# caching"): the main conversation gets 1h only on a subscription within plan usage, else
# 5m. WARM is the longest idle wait that still reads a warm cache: 3300 s leaves 300 under
# the hour for a wakeup's late fire (3600 s was seen to fire at 3636 to 3648).
TTLS = ("5m", "1h")
WARM = {"1h": 3300, "5m": 270}
FORCE_5M = "FORCE_PROMPT_CACHING_5M"
TTL_VAR = "CLAUDE_CODE_PROMPT_CACHE_TTL"
ENABLE_1H = "ENABLE_PROMPT_CACHING_1H"
CLOUD = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
         "CLAUDE_CODE_USE_ANTHROPIC_AWS", "CLAUDE_CODE_USE_MANTLE")   # fix round F2
PLAN = 100                        # a usage reading at or past this is on usage credits
DISABLE = "DISABLE_PROMPT_CACHING"     # and its per-model `_<MODEL>` forms: no cache (F3)
UNKNOWN = "no usage reading and no override"
LIFETIME = {
    "1h": "the prompt cache lives 1h here ({why}): an idle wait (items 2, 4 and 5) wakes at "
          "most {warm} s apart, whatever the fallback, so the cache survives; a wake at 3600 s "
          "lands past the hour and rewrites the whole context",
    "5m": "the prompt cache lives 5m here ({why}): any wait past about {warm} s misses it "
          "anyway, so an idle wait takes the long fallback ({fallback} s or more) and never "
          "wakes early just to keep the cache",
    None: "the prompt cache's lifetime is not known here ({why}): on 1h (a subscription "
          "within plan usage) an idle wait wakes at most {warm1h} s apart; on 5m (usage "
          "credits, an API key, a cloud provider or promptCacheTtl 5m) it takes the long "
          "fallback and never wakes early to keep the cache",
    "off": "the prompt cache is off here ({why}): no wait keeps it warm, so an idle wait "
           "takes the long fallback ({fallback} s or more) and never wakes early to keep a "
           "cache"}
CLAUSE = {"1h": f", cache 1h: idle wakes <={WARM['1h']}s", "5m": ", cache 5m: no keep-warm wakes",
          "off": ", cache off: no keep-warm wakes"}
HINT = {"1h": "cache 1h ({why}): an idle wake waits at most {warm} s, so the cache survives",
        "5m": "cache 5m ({why}): a wait past about {warm} s misses anyway; an idle wait takes "
              "the long fallback, never an early wake to keep the cache",
        "off": "cache off ({why}): no wait keeps it warm; an idle wait takes the long "
               "fallback, never an early wake to keep a cache"}
TAIL = "; agentik-session rules prints both"

_LABEL = re.compile(r"[A-Za-z0-9 '.,-]*")


def normalize(session: dict, unknown: list, layer: str) -> dict:
    """One layer's `session` mapping with its unknown priority and pacing fields
    dropped, each recorded as `<layer>: session.<key>.<field>`. Raises ValueError
    when the layer sets either key, or `priority.levels`, to anything but a mapping."""
    out = dict(session)
    for key, fields in FIELDS.items():
        if key not in out:
            continue
        body = out[key]
        if not isinstance(body, dict):
            raise ValueError(f"{layer}: session.{key} must be a mapping of "
                             f"{', '.join(fields)} (null or a scalar would delete it)")
        body = dict(body)
        for k in list(body):
            if k not in fields:
                unknown.append(f"{layer}: session.{key}.{k}")
                del body[k]
        if key == "priority" and "levels" in body:
            lv = body["levels"]
            if not isinstance(lv, dict):
                raise ValueError(f"{layer}: session.priority.levels must be a mapping of "
                                 f"{', '.join(LEVELS)}")
            for k in list(lv):
                if k not in LEVELS:
                    unknown.append(f"{layer}: session.priority.levels.{k}")
            body["levels"] = {k: v for k, v in lv.items() if k in LEVELS}
        out[key] = body
    return out


def _text_ok(v) -> bool:
    return (isinstance(v, str) and 1 <= len(v) <= TEXT_MAX and bool(v.strip())
            and len(v.splitlines()) == 1)


def _int_ok(v, key: str) -> bool:
    lo, hi = BOUNDS[key]
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def check(session: dict) -> None:
    """The merged values; raises ValueError naming the first bad one."""
    for key, fields in FIELDS.items():
        body = session.get(key)
        if not isinstance(body, dict):
            raise ValueError(f"session.{key} must be a mapping of {', '.join(fields)}")
        if not isinstance(body.get("enabled"), bool):
            raise ValueError(f"{key}.enabled must be true or false")
    for n in LEVELS:
        if not _text_ok(session["priority"].get("levels", {}).get(n)):
            raise ValueError(f"priority.levels.{n} must be one line of 1 to {TEXT_MAX} "
                             "characters")
    for k, (lo, hi) in BOUNDS.items():
        if not _int_ok(session["pacing"].get(k), k):
            raise ValueError(f"pacing.{k} must be an integer from {lo} to {hi}")


def parts(session) -> tuple[dict, dict]:
    """(priority, pacing) as they bind: an absent or unreadable field is its default,
    so a missing key is on."""
    s = session if isinstance(session, dict) else {}
    pr = s.get("priority") if isinstance(s.get("priority"), dict) else {}
    pa = s.get("pacing") if isinstance(s.get("pacing"), dict) else {}
    lv = pr.get("levels") if isinstance(pr.get("levels"), dict) else {}
    levels = {n: lv[n] if _text_ok(lv.get(n)) else PRIORITY["levels"][n] for n in LEVELS}
    pacing = {"enabled": pa.get("enabled") is not False}
    for k in BOUNDS:
        pacing[k] = pa[k] if _int_ok(pa.get(k), k) else PACING[k]
    return {"enabled": pr.get("enabled") is not False, "levels": levels}, pacing


def _label(text: str) -> str:
    return _LABEL.match(text.split(":", 1)[0]).group(0)[:LABEL_MAX].strip()


def clause(session, ttl=None) -> str:
    """The SessionStart block: empty when both are off, else one line of at most
    BLOCK_MAX bytes opening `; `. With pacing on and `ttl` known (`1h`, `5m`), the pacing
    part ends with CLAUSE[ttl] when the whole block still fits; never cut for it (S30)."""
    pr, pa = parts(session)
    out = []
    if pr["enabled"]:
        labels = ", ".join(f"{n} {_label(pr['levels'][n])}".rstrip() for n in LEVELS)
        out.append(f"priority: {labels}; the Next act takes the highest ready")
    if pa["enabled"]:
        out.append(f"pacing: wake in the act's last tool call, a pending helper is the wake "
                   f"(one fallback, {pa['fallback']}s+), WAITING {pa['waiting']} stops the "
                   "loop, a meter wait never")
    if not out:
        return ""
    if pa["enabled"] and ttl in CLAUSE:
        named = "; " + "; ".join(out) + CLAUSE[ttl] + TAIL
        if len(named.encode()) <= BLOCK_MAX:
            return named
    return ("; " + "; ".join(out) + TAIL)[:BLOCK_MAX]


def render(session, life=None) -> str:
    """What `agentik session rules` prints: both parts as resolved, and with pacing on, item
    6: the prompt cache's lifetime `life`, `(ttl, why)` from `lifetime` (unknown when None)."""
    pr, pa = parts(session)
    lines = []
    if pr["enabled"]:
        lines.append("priority: on (session.priority)")
        lines += [f"  {n} {pr['levels'][n]}" for n in LEVELS]
        lines += [f"  - {r}" for r in RULES]
        lines += [f"  - {b}" for b in BUGS]
    else:
        lines.append("priority: off (session.priority.enabled is false)")
    if pa["enabled"]:
        lines.append(f"pacing: on (session.pacing: fallback {pa['fallback']} s, "
                     f"waiting {pa['waiting']})")
        lines += [f"  {i}. " + p.format(**pa) for i, p in enumerate(PACE, 1)]
        ttl, why = life if isinstance(life, tuple) and len(life) == 2 else (None, UNKNOWN)
        ttl = ttl if ttl in LIFETIME else None
        lines.append(f"  {len(PACE) + 1}. " + LIFETIME[ttl].format(
            why=why, warm=WARM.get(ttl), warm1h=WARM["1h"], fallback=pa["fallback"]))
    else:
        lines.append("pacing: off (session.pacing.enabled is false)")
    lines.append(BOUND)
    return "\n".join(lines) + "\n"


def _truthy(v) -> bool:
    return isinstance(v, str) and v.strip().lower() in ("1", "true", "yes", "on")


def _setting(env, cwd):
    """`promptCacheTtl` from the local, project, then user settings: (ttl, why) or None.
    A value but `5m` or `1h` is skipped, as Claude Code ignores it. The user's settings are
    under CLAUDE_CONFIG_DIR when it is set, else ~/.claude (fix round F4)."""
    moved = env.get("CLAUDE_CONFIG_DIR")
    user = (Path(moved).expanduser() if moved
            else Path(env.get("HOME") or Path.home()) / ".claude")
    here = [] if cwd is None else [("local", Path(cwd) / ".claude" / "settings.local.json"),
                                   ("project", Path(cwd) / ".claude" / "settings.json")]
    for scope, path in [*here, ("user", user / "settings.json")]:
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        v = doc.get("promptCacheTtl") if isinstance(doc, dict) else None
        if v in TTLS:
            return v, f"promptCacheTtl, {scope} settings"
    return None


def _percent(v):
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    return v if ok else None


def _instant(v):
    try:
        t = datetime.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        return None
    return t if t is not None and t.tzinfo is not None else None


def lifetime(env, cwd, band=None, now=None) -> tuple:
    """The main conversation's prompt-cache lifetime, `(ttl, why)`: `off` when
    DISABLE_PROMPT_CACHING or a per-model form is set (fix round F3), else Claude Code's order:
    FORCE_PROMPT_CACHING_5M; CLAUDE_CODE_PROMPT_CACHE_TTL; the `promptCacheTtl` setting;
    ENABLE_PROMPT_CACHING_1H; then the default: 5m on a cloud provider, else band.json's
    five-hour reading while its reset is ahead: 5m past plan usage (5h or 7d at PLAN or
    more), 1h within it. `(None, UNKNOWN)` when nothing says (an API key leaves no reading).
    The project's settings are under CLAUDE_PROJECT_DIR, which Claude's `cd` never moves;
    under `cwd` only when it is unset (fix round F1)."""
    cwd = env.get("CLAUDE_PROJECT_DIR") or cwd
    for k in [DISABLE, *sorted(k for k in env if k.startswith(DISABLE + "_"))]:
        if _truthy(env.get(k)):
            return "off", k
    if _truthy(env.get(FORCE_5M)):
        return "5m", FORCE_5M
    if env.get(TTL_VAR) in TTLS:
        return env[TTL_VAR], TTL_VAR
    found = _setting(env, cwd)
    if found:
        return found
    if _truthy(env.get(ENABLE_1H)):
        return "1h", ENABLE_1H
    if any(_truthy(env.get(k)) for k in CLOUD):
        return "5m", "a cloud provider"
    b = band if isinstance(band, dict) else {}
    p, p7, resets = _percent(b.get("P")), _percent(b.get("P7")), _instant(b.get("resetsAt"))
    if p is None or resets is None or resets <= (now or datetime.now(timezone.utc)):
        return None, UNKNOWN
    if p >= PLAN:
        return "5m", f"past plan usage, 5h {p:g}%"
    if p7 is not None and p7 >= PLAN:
        return "5m", f"past plan usage, 7d {p7:g}%"
    return "1h", f"within plan usage, 5h {p:g}%"


def hint(ttl, why) -> str | None:
    """The prompt hook's line for a known lifetime; None when it is not known."""
    return HINT[ttl].format(why=why, warm=WARM.get(ttl)) if ttl in HINT else None


def handover_listed(text: str) -> bool:
    """True when the charter's `## Handover` section holds a HANDOVER line."""
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.rstrip() == "## Handover"
        elif inside and line.startswith(HANDOVER):
            return True
    return False


# ---- session.admission (packet S26 ruling 3): the admission verdict's knobs ----
# Read field by field with defaults, as `parts` reads priority and pacing: an absent or
# unreadable field is its default. The seeds stand in for the fit until 20 intervals exist
# (design/admission-r1.md §3.2; reversible, replaced by P3).
ADMISSION = {"mode": "observe", "ceiling": 97, "margin": 3, "ceiling_7d": 97,
             "seeds": {"a": 0.10, "b": {"opus": 0.15, "sonnet": 0.05, "haiku": 0.02,
                                        "fable": 0.25, "other": 0.15}, "life": 15}}
# (low, high, low included): a percent, a margin, points a minute, minutes of life.
ADMISSION_BOUNDS = {"ceiling": (0, 100, False), "margin": (0, 100, True),
                    "ceiling_7d": (0, 100, False), "a": (0, 10, True), "b": (0, 10, True),
                    "life": (0, 300, False)}
ENFORCE = "session.admission.mode: enforce is not built yet (S27a); read as observe"


def _real(v, key: str) -> bool:
    lo, hi, closed = ADMISSION_BOUNDS[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        return False
    return (v >= lo if closed else v > lo) and v <= hi and not (key == "margin" and v >= hi)


def admission(session, notes: list | None = None) -> dict:
    """`session.admission` as it binds: `mode` is always `observe` in S26 (`enforce` is
    refused, one note in `notes`, and read as `observe`); every other field is its value
    when in bounds, else its default."""
    s = session if isinstance(session, dict) else {}
    ad = s.get("admission") if isinstance(s.get("admission"), dict) else {}
    sd = ad.get("seeds") if isinstance(ad.get("seeds"), dict) else {}
    bd = sd.get("b") if isinstance(sd.get("b"), dict) else {}
    if ad.get("mode") == "enforce" and notes is not None:
        notes.append(ENFORCE)
    out = {"mode": "observe"}
    for k in ("ceiling", "margin", "ceiling_7d"):
        out[k] = ad[k] if _real(ad.get(k), k) else ADMISSION[k]
    seeds = ADMISSION["seeds"]
    out["seeds"] = {
        "a": sd["a"] if _real(sd.get("a"), "a") else seeds["a"],
        "b": {f: bd[f] if _real(bd.get(f), "b") else v for f, v in seeds["b"].items()},
        "life": sd["life"] if _real(sd.get("life"), "life") else seeds["life"]}
    return out
