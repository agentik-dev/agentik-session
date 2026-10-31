"""The demand bands: a schedule from a file, and the band at an instant (packet S44).

The bands are a file, never code: the shipped `bands.yaml`, which the user's
`<config>/agentik/session/bands.yaml` replaces whole. Only admission calls `demand`, at a
band.json write; every other reader reads band.json, and nothing waits for a band. A file
that does not bind is a note (`doctor` warns with it) and the shipped file is used; nothing
here raises. With the shipped file or its zone gone there is no band at all: `demand` is None.

The clock is the schedule's wall clock. A wall time a DST gap skips reads as the first
instant after the gap; a wall time a fold repeats reads its first instant, so a cut inside a
fold happens once, and `now` in the fold's second pass still takes its band from the wall.
"""
from __future__ import annotations

import os
import re
import stat
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from . import yamlsubset

FILE = "bands.yaml"
MAX_BYTES = 64 * 1024                  # a user file past this is a bad one, as band.json's cap
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_M = 24 * 60
WEEK_M = 7 * DAY_M
WALK_WEEKS = 3                         # every cut recurs in a week; a gap or a fold costs one more
REPORTED = ("good", "best")            # the bands `next` names
_HM = re.compile(r"(\d{2}):(\d{2})\Z")
_DAYS = re.compile(r"([A-Z][a-z]{2})(?:-([A-Z][a-z]{2}))?\Z")


class _Bad(ValueError):
    """Why a schedule does not bind; never leaves this module."""


def _user_path(env) -> Path:
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path(env.get("HOME") or Path.home()) / ".config"
    return root / "agentik" / "session" / FILE


def _read_user(p: Path) -> str:
    """The user's file, opened non-blocking: a FIFO there never hangs a hook, as read_band."""
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise _Bad("not a regular file")
        if st.st_size > MAX_BYTES:
            raise _Bad(f"past {MAX_BYTES} bytes")
        data = os.read(fd, MAX_BYTES + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES:
        raise _Bad(f"past {MAX_BYTES} bytes")
    return data.decode("utf-8")


def _shipped() -> str:
    from importlib import resources    # here, not at the top: a hook on a five-hour login never pays
    return resources.files(__package__).joinpath(FILE).read_text(encoding="utf-8")


def _days(v) -> tuple:
    m = _DAYS.match(v) if isinstance(v, str) else None
    if m is None or m.group(1) not in DAYS or (m.group(2) and m.group(2) not in DAYS):
        raise _Bad(f"days {v!r}")
    a = DAYS.index(m.group(1))
    b = DAYS.index(m.group(2)) if m.group(2) else a
    if m.group(2) and b <= a:
        raise _Bad(f"days {v!r} does not run forward")
    return tuple(range(a, b + 1))


def _minute(v) -> int:
    m = _HM.match(v) if isinstance(v, str) else None
    if m is None or int(m.group(2)) > 59 or int(m.group(1)) * 60 + int(m.group(2)) > DAY_M:
        raise _Bad(f"time {v!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def _rule(r) -> dict:
    if not isinstance(r, dict):
        raise _Bad(f"rule {r!r}")
    start, end = _minute(r.get("from")), _minute(r.get("to"))
    if start >= end:
        raise _Bad(f"from {r.get('from')} is not before to {r.get('to')}")
    band = r.get("band")
    if not isinstance(band, str) or not band:
        raise _Bad(f"band {band!r}")
    return {"days": _days(r.get("days")), "from": start, "to": end, "band": band}


def _slots(rules: list) -> list:
    """The week by the minute, Monday 00:00 first: each minute's first matching band."""
    slots: list = [None] * WEEK_M
    for r in reversed(rules):              # the first match paints last
        n = r["to"] - r["from"]
        for d in r["days"]:
            start = d * DAY_M + r["from"]
            slots[start:start + n] = [r["band"]] * n
    return slots


def _zone(v):
    from zoneinfo import ZoneInfo      # as _shipped's import
    if not isinstance(v, str):
        raise _Bad(f"tz {v!r}")
    try:
        return ZoneInfo(v)
    except (KeyError, ValueError, OSError) as e:   # ZoneInfoNotFoundError is a KeyError
        raise _Bad(f"tz {v!r} does not load") from e


def _compile(text: str) -> tuple:
    data = yamlsubset.load(text)
    tz = _zone(data.get("tz"))
    raw = data.get("bands")
    if not isinstance(raw, list) or not raw:
        raise _Bad("no bands")
    rules = [_rule(r) for r in raw]
    if None in (slots := _slots(rules)):
        i = slots.index(None)
        raise _Bad(f"{DAYS[i // DAY_M]} {i % DAY_M // 60:02d}:{i % 60:02d} is unmatched")
    return rules, tz


def schedule(env) -> tuple:
    """(rules, tz, notes): the user's file when it binds, else the shipped one with one note;
    ([], None, [note]) when the shipped one does not bind either. Never raises."""
    notes: list = []
    p = _user_path(env)
    try:
        return (*_compile(_read_user(p)), notes)
    except FileNotFoundError:
        pass
    except Exception as e:  # noqa: BLE001 - any file is a note, never a raise: this runs in a hook
        why = " ".join(f"{e}".split())[:200]
        notes.append(f"bands: {p}: {why}; the shipped file is used")
    try:
        return (*_compile(_shipped()), notes)
    except Exception as e:  # noqa: BLE001 - as above
        why = " ".join(f"{e}".split())[:200]
        return [], None, [*notes, f"bands: the shipped file does not bind ({why}); no band is shown"]


def _instant(naive: datetime, tz) -> datetime:
    """A wall time as an instant: a fold's first; a gap's first instant after it."""
    first = naive.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    if first.astimezone(tz).replace(tzinfo=None) == naive:
        return first
    lo = naive.replace(tzinfo=tz, fold=1).astimezone(timezone.utc)   # the offset after the gap: before it
    hi = first                                                       # the offset before it: after it
    before = lo.astimezone(tz).utcoffset()
    while hi - lo > timedelta(seconds=1):
        mid = lo + timedelta(seconds=(hi - lo).total_seconds() // 2)
        if mid.astimezone(tz).utcoffset() == before:
            lo = mid
        else:
            hi = mid
    return hi


def _of_week(t: datetime) -> int:
    return t.weekday() * DAY_M + t.hour * 60 + t.minute


def demand(now: datetime, rules: list, tz, stamp_tz=None) -> dict | None:
    """{band, until, next} at `now`: the band of the first matching rule at the wall clock;
    `until`, the next instant the band's name changes (None when no change comes); `next`,
    for each of REPORTED the schedule holds, the start of its next stretch, past the one now
    is in. Stamps are zoned ISO in `stamp_tz` (None is the system's, as band.json's other
    stamps). None with no schedule, or at datetime's ends."""
    if not rules or tz is None:
        return None
    try:
        slots = _slots(rules)
        wall = now.astimezone(tz)
        band = slots[_of_week(wall)]
        if band is None:
            return None
        cuts = [m for m in range(WEEK_M) if slots[m] != slots[m - 1]]
        wanted = [n for n in REPORTED if n in slots]
        monday = datetime.combine(wall.date() - timedelta(days=wall.weekday()), time())
        until, found = None, {}
        for m in (w * WEEK_M + c for w in range(WALK_WEEKS) for c in cuts):
            t = _instant(monday + timedelta(minutes=m), tz)
            if t <= now:
                continue
            name = slots[_of_week(t.astimezone(tz))]   # a gap can swallow a stretch: read what is there
            if until is None:
                if name == band:
                    continue
                until = t
            if name in wanted:
                found.setdefault(name, t)
            if len(found) == len(wanted):
                break

        def stamp(t: datetime) -> str:
            return t.astimezone(stamp_tz).isoformat(timespec="seconds")
        return {"band": band, "until": stamp(until) if until else None,
                "next": {n: stamp(found[n]) for n in REPORTED if n in found}}
    except (OverflowError, ValueError):
        return None
