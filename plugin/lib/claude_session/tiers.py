"""The model tiers (packet mt1, hq design/13 §3 to §6): one table of five roles.

A profile's `tiers` maps each role to `{model, effort}`; the shipped default is in
`profiles.yaml`'s `defaults`. The resolver layers it (its docstring gives the order, a
launched profile's own body last) and writes it with no clock. A session's
own word sits in its overlay and is read here, against the clock, by every reader:
`set tier.<role> <model> [--until]` replaces one role's model, and `set cap <model>
[--until]` holds every tier at that family or below. Neither is saved by a profile; the cap
never is, and a `run` launcher hands it to its successor while its time is ahead.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import store

ROLES = ("design", "build", "words", "mend", "lookup")
# Highest first: a helper never runs above its parent's family, nor above its role's.
ORDER = ("fable", "opus", "sonnet", "haiku", "local")
KEY, CAP = "tiers", "cap"                # the overlay's keys
RECORD = "cap.json"                      # the chain home's copy of the cap: {session, cap}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Round 1 F8: any case, a trailing \r or full stop; the first line naming a known role.
_ROLE_LINE = re.compile(r"^[ \t]*tier:[ \t]*([a-z]+)\.?[ \t]*\r?$", re.M | re.I)
# Round 1 F7: a model word a verb takes, and the one shape `--save` writes quoted.
MODEL_WORD = re.compile(r"[A-Za-z0-9._/\[\]-]+")
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def family(model) -> str | None:
    """The family of a model string, `local` for the local lane's, else None."""
    if not isinstance(model, str) or not model.strip():
        return None
    m = model.strip().lower()
    if m.startswith("local"):
        return "local"
    for token in re.split(r"[^a-z0-9]+", re.sub(r"\[[^\]]*\]", "", m)):
        if token in ORDER:
            return token
    return None


def above(model, limit) -> bool:
    """True when `model`'s family ranks above `limit`'s; False when either is unknown."""
    a, b = family(model), family(limit)
    return a is not None and b is not None and ORDER.index(a) < ORDER.index(b)


def merge(base: dict, over) -> dict:
    """`over`'s roles over `base`'s, field by field; a role outside ROLES is dropped. A bare
    string for a role is its model."""
    out = {r: dict(v) for r, v in (base or {}).items() if r in ROLES and isinstance(v, dict)}
    for r, v in (over or {}).items() if isinstance(over, dict) else ():
        if r not in ROLES or v is None:
            continue
        v = {"model": v} if isinstance(v, str) else v
        if isinstance(v, dict):
            out[r] = {**out.get(r, {}), **{k: v[k] for k in ("model", "effort") if k in v}}
    return out


def check(table) -> None:
    """Raises ValueError unless every role has a model of a known family and a known
    effort."""
    if not isinstance(table, dict):
        raise ValueError("tiers must be a mapping of design, build, words, mend, lookup")
    for r in ROLES:
        v = table.get(r)
        if not isinstance(v, dict) or not isinstance(v.get("model"), str) or not v["model"]:
            raise ValueError(f"tiers.{r} needs a model")
        if family(v["model"]) is None:                  # round 1 F10
            raise ValueError(f"tiers.{r}.model {v['model'][:40]!r} names no model family "
                             f"({', '.join(ORDER)})")
        if v.get("effort") is not None and v["effort"] not in EFFORTS:
            raise ValueError(f"tiers.{r}.effort must be one of {', '.join(EFFORTS)}")


def when(v):
    """An ISO time with its zone as a datetime, else None."""
    if not isinstance(v, str) or len(v) > 64:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def wall(t: datetime, tz=None) -> str:
    """`Ddd HH:MM`, local (`tz` for tests)."""
    t = t.astimezone(tz)
    return f"{_DAYS[t.weekday()]} {t:%H:%M}"


def _live(v, now) -> bool:
    """A word with no end lives as long as its overlay (the session); one with an end, until
    it."""
    if not isinstance(v, dict) or not isinstance(v.get("model"), str):
        return False
    if v.get("until") is None:
        return True
    end = when(v.get("until"))
    return end is not None and now < end


def words(overlay, now) -> tuple[dict, dict | None]:
    """({role: word}, cap word or None) of this session's overlay that are in force."""
    ov = overlay if isinstance(overlay, dict) else {}
    t = ov.get(KEY) if isinstance(ov.get(KEY), dict) else {}
    roles = {r: v for r, v in t.items() if r in ROLES and _live(v, now)}
    cap = ov.get(CAP)
    return roles, (cap if _live(cap, now) else None)


def effective(table, overlay, now) -> dict:
    """The resolved table with this session's live words over it, then its cap: a role
    above the cap's family runs on the cap's model."""
    out = merge(table if isinstance(table, dict) else {}, {})
    roles, cap = words(overlay, now)
    for r, v in roles.items():
        out[r] = {**out.get(r, {}), "model": v["model"]}
    if cap:
        for r, v in out.items():
            if above(v.get("model"), cap["model"]):
                out[r] = {**v, "model": cap["model"]}
    return out


def _to(v, tz) -> str:
    end = when(v.get("until"))
    return f" to {wall(end, tz)}" if end else " this session"


def parts(overlay, now, tz=None) -> list[str]:
    """`tiers: build sonnet to Ddd HH:MM` and `cap: opus to Ddd HH:MM` while in force."""
    roles, cap = words(overlay, now)
    out = []
    if roles:
        out.append("tiers: " + ", ".join(f"{r} {v['model']}{_to(v, tz)}"
                                         for r, v in sorted(roles.items(),
                                                            key=lambda x: ROLES.index(x[0]))))
    if cap:
        out.append(f"cap: {cap['model']}{_to(cap, tz)}")
    return out


def render(table, effort=None) -> list[str]:
    """The table as `agentik session profile <name>` prints it: one line a role."""
    lines = []
    for r in ROLES:
        v = (table or {}).get(r) or {}
        lines.append(f"  {r:<7} {str(v.get('model')):<14} {v.get('effort') or effort or '-'}")
    return lines


def role(prompt) -> str | None:
    """The role a spawn's prompt names by a line `tier: <role>`, else None."""
    if not isinstance(prompt, str):
        return None
    for m in _ROLE_LINE.finditer(prompt[:65536]):
        if m.group(1).lower() in ROLES:
            return m.group(1).lower()
    return None


# ---- the cap's hand to a `run` successor, as fill's (fill.keep, fill.hand) ----------------

def keep(home, sid, v) -> None:
    p = Path(home) / RECORD
    if v is None:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        return
    store._write_private(p, json.dumps({"session": sid, CAP: v}) + "\n")


def hand(home, state, prev, sid, now):
    """At a start: the cap `prev` held, its time ahead, goes into `sid`'s overlay and is
    returned; any other copy is removed and None returned. A cap with no end is the
    session's alone and is never kept, so never handed."""
    p = Path(home) / RECORD
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        d = None
    v = d.get(CAP) if isinstance(d, dict) else None
    if (not prev or not isinstance(d, dict) or d.get("session") != prev
            or not isinstance(v, dict) or when(v.get("until")) is None or not _live(v, now)):
        keep(home, sid, None)
        return None
    op = Path(state) / "overlays" / f"{sid}.json"
    try:
        cur = json.loads(op.read_text())
    except (OSError, ValueError):
        cur = {}
    cur = cur if isinstance(cur, dict) else {}
    cur[CAP] = v
    store._write_private(op, json.dumps(cur, indent=2))
    keep(home, sid, v)
    return v
