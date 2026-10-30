"""The mod's one verb and its trace (design/mod-r1.md §4, packet M1).

`agentik-session mod start --session <id>` is the only thing the session plugin's hooks
module (plugin/hooks/session.ts) runs: it writes `mod.json` `{at, version}` into the
directory the classic hooks made for the session, and prints that directory, which the
module reads its band from. `status` and `doctor` print whether the mod has been seen.
Nothing that decides (chain, hooks, budget) reads mod.json: the classic path stands alone.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, resolver
from .hooks import _SID
from .store import _write_private

MOD = "mod.json"
# The band's limit note (packet S34 ruling 6), the twin of `limitNote` in session.ts; one
# fixture in session.test.ts pins both (tests/test_s34.py).
LIMIT_NOTE = "limit: the model's limit ended the last turn; /model to switch"


class ModError(Exception):
    """A refusal: one line for stderr and the exit code (2: a bad id, 1: no session)."""

    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self.code = code


def start(sid, env, now: datetime | None = None) -> Path:
    """Write mod.json in the session's existing directory; return the directory."""
    if not isinstance(sid, str) or not _SID.match(sid):
        raise ModError(f"not a session id: {sid!r}", 2)
    sdir = resolver.session_dir(resolver.state_dir(env), sid)
    if not sdir.is_dir():
        raise ModError(f"no session {sid}", 1)     # never made here: the classic hooks make it
    at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    # a unique temp name: concurrent runs never share one (fix round 3)
    _write_private(sdir / MOD, json.dumps({"at": at, "version": __version__}) + "\n")
    return sdir.resolve()


def age(sdir, now: datetime | None = None) -> tuple[bool, float | None]:
    """(seen, seconds since the mod last started): (False, None) when mod.json is absent,
    (True, None) when its `at` is unreadable or has no timezone (an unknown age, never a crash)."""
    try:
        text = (Path(sdir) / MOD).read_text()
    except OSError:
        return False, None
    try:
        then = datetime.fromisoformat(json.loads(text)["at"])
    except (ValueError, KeyError, TypeError, IndexError):
        return True, None
    if then.tzinfo is None:
        return True, None
    return True, max(0.0, ((now or datetime.now(timezone.utc)) - then).total_seconds())


def _ago(s: float) -> str:
    for unit, size, limit in (("s", 1, 120), ("m", 60, 7200), ("h", 3600, 172800)):
        if s < limit:
            return f"{int(s // size)}{unit}"
    return f"{int(s // 86400)}d"


def line(sdir) -> str:
    """`seen <age> ago`, `seen, age unknown` or `not seen`: what `status` and `doctor` print after `mod:`."""
    seen, a = age(sdir) if sdir else (False, None)
    if not seen:
        return "not seen"
    return "seen, age unknown" if a is None else f"seen {_ago(a)} ago"


def _at(text):
    """A stamp's `at` (a finite number), from the file's text; None when unreadable."""
    try:
        at = json.loads(text)["at"]
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    ok = isinstance(at, (int, float)) and not isinstance(at, bool) and at == at \
        and abs(at) != float("inf")
    return at if ok else None


def limit_note(limited, turn_ended) -> str | None:
    """LIMIT_NOTE when `limited.json`'s text says `rate_limit` at a time later than
    `turn-ended.json`'s (or there is no readable turn end); else None (S34 ruling 6)."""
    try:
        doc = json.loads(limited) if limited is not None else None
    except (TypeError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("error") != "rate_limit":
        return None
    at, ended = _at(limited), _at(turn_ended) if turn_ended is not None else None
    if at is None or (ended is not None and at <= ended):
        return None
    return LIMIT_NOTE


# ---- The model and the window (packet S41) ----------------------------------------------
# The twin of modelName, windowLabel and lineFacts in session.ts; one fixture in
# session.test.ts pins both (tests/test_mod.py). Display only: nothing that decides reads it.
# A minor of one or two ASCII digits (Amendment 1): a dated id with no minor
# (`claude-opus-4-20250514`) is shown as given, and `\d` reads as session.ts reads it.
MODEL_ID = re.compile(r"^claude-([a-z]+)-(\d+)-(\d{1,2})(?:-\d{8})?$", re.ASCII)
MODEL_CLIP = 24
SOURCE_CLIP = 64


def model_name(v) -> str | None:
    """`claude-opus-5-5` -> `opus 5.5`; any other id as given, clipped to MODEL_CLIP."""
    if not isinstance(v, str) or not v:
        return None
    m = MODEL_ID.fullmatch(v)            # whole: `$` alone also matches before a final newline
    if m:
        return f"{m[1]} {m[2]}.{m[3]}"
    return v[:MODEL_CLIP - 1] + "…" if len(v) > MODEL_CLIP else v


def window_label(v) -> str | None:
    """A finite window of 1 or more, read as JSON.parse reads it in the twin (a double, so
    an int past its range is no part): `1M` for exactly 1,000,000, under 1000 the figure
    itself, else `<floor(n/1000)>k`."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except OverflowError:
        return None
    if not math.isfinite(v) or v < 1:
        return None
    return "1M" if v == 1_000_000 else f"{math.floor(v)}" if v < 1000 else f"{math.floor(v / 1000)}k"


def _obj(v) -> dict | None:
    return v if isinstance(v, dict) else None


def facts(meter: dict | None, measure: dict | None) -> str | None:
    """`<model> · <window>`, the window `<resolved> (engine <E>)` when the two labels differ,
    `engine <E>` with no resolved one; each part only when readable; None with neither."""
    m = _obj(meter) or {}
    name = model_name(m.get("model"))
    w = window_label(m.get("window"))
    e = window_label((_obj((_obj(measure) or {}).get("context")) or {}).get("window"))
    win = f"{w} (engine {e})" if w is not None and e is not None and e != w \
        else w if w is not None else f"engine {e}" if e is not None else None
    parts = [p for p in (name, win) if p is not None]
    return " · ".join(parts) if parts else None


def model_line(meter: dict, measure: dict | None) -> str:
    """What `status` prints after `model:`: the band's facts, then the id and the window's
    source when the meter has them; `none` when it has nothing to say."""
    head = facts(meter, measure)
    m = _obj(meter) or {}
    model, src = m.get("model"), m.get("window_source")
    tail = [str(model)[:SOURCE_CLIP]] if isinstance(model, str) and model else []
    if isinstance(src, str) and src:
        tail.append(f"window from {src[:SOURCE_CLIP]}")
    if head is None and not tail:
        return "none"
    return "; ".join(x for x in (head, ", ".join(tail)) if x)
