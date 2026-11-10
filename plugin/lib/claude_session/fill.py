"""The fill word (packet FW1b, hq design/08 section 2): off-path work that uses a window up.

Off unless the owner's word turns it on, through `agentik session set fill <reset|opus>
[--until <zoned time>]`, in a main-thread orchestrator on a 1M window. The word lives in
this session's overlay with its end stamped beside it; under a launcher `set` also keeps it
in the chain home, from where the launcher hands it to its successor's overlay. Nothing else
is read, so no profile, config layer, memory or ledger turns it on, and every read tests the
seat and the clock again. It is advice: nothing here holds or starts a spawn.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import models, store
from . import state as statefile

KEY = "fill"
WORDS = ("reset", "opus")
ROLES = ("orchestrator", "orchestrator-opus")
RECORD = "fill.json"                      # the chain home's copy: {session, fill}
OFF = "fill: off"
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class Refused(ValueError):
    """`set fill` refused; `code` is the exit (2 for usage, 1 for the rest)."""

    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


def when(v):
    """An ISO time with its zone as a datetime, else None (rules._zoned's reading)."""
    if not isinstance(v, str) or len(v) > 64:
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def stamp(word, until, week, now) -> tuple:
    """(the overlay's value, whether the named time was cut) for a word set at `now`:
    `until` the time the owner named (None for `reset` alone), `week` the login's
    seven-day reset. The end is the named time, never past the week's reset."""
    if word not in WORDS:
        raise Refused("fill takes reset, opus or off", 2)
    if until is None and word != "reset":
        raise Refused(f"fill {word} needs its end: --until <zoned time>", 2)
    if week is None or week <= now:
        raise Refused("no seven-day reading names this session's reset, so nothing bounds "
                      "a fill word; it stays off")
    if until is not None and until <= now:
        raise Refused(f"--until names a time that has passed ({_iso(until)})")
    end = week if until is None else min(until, week)
    return ({"word": word, "until": _iso(end), "week": _iso(week), "set": _iso(now)},
            until is not None and until > week)


def live(v, now):
    """(word, until) for an overlay value that binds by shape and clock alone; else None.
    A bare string, a missing stamp, an end past its week's reset or a past end is off."""
    if not isinstance(v, dict) or v.get("word") not in WORDS:
        return None
    until, week = when(v.get("until")), when(v.get("week"))
    if until is None or week is None or until > week or not now < until:
        return None
    return v["word"], until


def seat(session, env):
    """Why this session may not fill, or None: a main-thread sitting whose resolved profile
    is an orchestrator's and whose window in force is 1M (the machine ledger's entry 22)."""
    if not statefile.main_sitting(env):
        return "a helper or a relay child never fills"
    s = session if isinstance(session, dict) else {}
    prof, win = s.get("profile"), s.get("window")
    if prof in ROLES and models.readable_window(win) and win >= models.ONE_M:
        return None
    return (f"fill is for an orchestrator on a 1M window (profile {str(prof)[:32]!r}, "
            f"window {str(win)[:12]})")


def read(overlay, session, env, now) -> tuple:
    """(word, until, why): the word in force and its end; else (None, its passed end or
    None, why it is off), why None when the overlay holds no word at all."""
    v = overlay.get(KEY) if isinstance(overlay, dict) else None
    if v is None:
        return None, None, None
    got = live(v, now)
    if got is None:
        end = when(v.get("until")) if isinstance(v, dict) and v.get("word") in WORDS else None
        week = when(v.get("week")) if end is not None else None
        if week is not None and end <= week and end <= now:
            return None, end, "its time passed"
        return None, None, "not a stamped word"
    why = seat(session, env)
    return (None, None, why) if why else (got[0], got[1], None)


def wall(t: datetime, tz=None) -> str:
    """`Ddd HH:MM`, local (`tz` for tests), as the band line writes the week's reset."""
    t = t.astimezone(tz)
    return f"{_DAYS[t.weekday()]} {t:%H:%M}"


def part(overlay, session, env, now, tz=None):
    """`fill <word> to <Ddd HH:MM>` while on, else None: the SessionStart block's and the
    prompt hook's part."""
    word, until, _ = read(overlay, session, env, now)
    return f"fill {word} to {wall(until, tz)}" if word else None


def line(overlay, session, env, now, tz=None) -> str:
    """What `rules` prints: `fill: <word> to <Ddd HH:MM>`, `fill: off`, or `fill: off
    (<why>)` when the overlay holds a word that is not in force."""
    word, until, why = read(overlay, session, env, now)
    if word:
        return f"fill: {word} to {wall(until, tz)}"
    if why and until is not None:
        return f"{OFF} ({why}, {wall(until, tz)})"
    return f"{OFF} ({why})" if why else OFF


def overlay(state, sid) -> dict:
    """The session's overlay as a dict; {} when absent or unreadable."""
    try:
        d = json.loads((Path(state) / "overlays" / f"{sid}.json").read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def keep(home, sid, v) -> None:
    """The chain home's copy of the word `sid` holds; None removes it."""
    p = Path(home) / RECORD
    if v is None:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        return
    store._write_private(p, json.dumps({"session": sid, KEY: v}) + "\n")


def hand(home, state, prev, sid, now):
    """At a start: when the chain home's copy is the one `prev` (the session that just
    ended) held and its time is ahead, write it into `sid`'s overlay, name `sid` as its
    holder and return the value; any other copy is removed and None returned."""
    p = Path(home) / RECORD
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        d = None
    v = d.get(KEY) if isinstance(d, dict) else None
    if not prev or not isinstance(d, dict) or d.get("session") != prev or live(v, now) is None:
        keep(home, sid, None)
        return None
    cur = overlay(state, sid)
    cur[KEY] = v
    store._write_private(Path(state) / "overlays" / f"{sid}.json", json.dumps(cur, indent=2))
    keep(home, sid, v)
    return v
