"""The mod's one verb and its trace (design/mod-r1.md §4, packet M1).

`claude-session mod start --session <id>` is the only thing the session plugin's hooks
module (plugin/hooks/session.ts) runs: it writes `mod.json` `{at, version}` into the
directory the classic hooks made for the session, and prints that directory, which the
module reads its band from. `status` and `doctor` print whether the mod has been seen.
Nothing that decides (chain, hooks, budget) reads mod.json: the classic path stands alone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, resolver
from .hooks import _SID
from .store import _write_private

MOD = "mod.json"


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
