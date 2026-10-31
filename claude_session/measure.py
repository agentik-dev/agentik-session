"""The engine's measure beside the meter (design/mod-r1.md §2 row M2, §4, §6 S2; packet M2).

`agentik-session measure record --session <id>` is what the session plugin's hooks module
(plugin/hooks/session.ts) runs at every `session.measure`: one JSON object on stdin,
`{context, rateLimits, cost, changed}`, written as `<state>/sessions/<id>/measure.json`
`{at, context, rateLimits, cost, changed}` (an absent cost null), atomically and 0600 by the
CLI's private writer, in the directory the classic hooks made. It catches a meter that parses
wrong: `status` and `doctor` print the drift between the engine's context tokens and the
meter's. What decides reads one figure of it, `context.window`, as the window pick's first
source (design/window-r1.md §2), and only through `models.engine_window`; `record` then moves
the resolved file by `resolver.rewindow`. The other figures decide nothing, and the budget
never reads the file. SessionEnd copies the last `rateLimits` to the ledger row (S49).
The whole shape is checked against 2.1.296's SessionMeasureInput (M2's fix round, F1): an
unknown key at any depth, a wrong type, a non-finite number or an unwritable string is refused,
and so is a window `engine_window` would not read, so it never overwrites a good reading.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from . import admission, meter, models, resolver
from .admission import Shape, context, items, number, only, rate_limits
from .hooks import _SID
from .store import _write_private

MEASURE = models.MEASURE
KEYS = ("context", "rateLimits", "cost", "changed")
CHANGED = ("context", "rateLimits", "cost")     # what `changed` may name
MAX_STDIN = admission.MAX_STDIN
# Reversible thresholds (packet M2 ruling 3): two stamps further apart than COMPARABLE_S are
# not compared, and a drift of WARN_DRIFT or more is doctor's warn, never a failure.
COMPARABLE_S = 120
WARN_DRIFT = 0.10
WARN_TENTHS = round(1000 * WARN_DRIFT)   # the printed figure, in tenths of a percent, is compared


class MeasureError(Exception):
    """A refusal: one line for stderr and the exit code (2 refused, 1 no session)."""

    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self.code = code


def shape(obj: dict) -> None:
    """SessionMeasureInput, whole: context {tokens?, window, percent?}, rateLimits
    [{kind, percentUsed, resetsAt?}], cost? {usd}, changed [one of CHANGED]; lists bounded."""
    for k in ("context", "rateLimits", "changed"):
        if k not in obj:
            raise Shape(f"{k}: absent")
    context(obj["context"])
    if not models.readable_window(obj["context"].get("window")):
        raise Shape("context.window: not a whole number from 1 to 10**9")
    rate_limits(obj["rateLimits"])
    if obj.get("cost") is not None:
        only(obj["cost"], "cost", ("usd",))
        number(obj["cost"].get("usd"), "cost.usd")
    for i, c in enumerate(items(obj["changed"], "changed")):
        if not isinstance(c, str) or c not in CHANGED:
            raise Shape(f"changed[{i}]: not one of " + ", ".join(CHANGED))


def parse(sid, text: str) -> dict:
    """stdin's object, checked: a bad id, JSON, number, key or shape is refused (exit 2)."""
    if not isinstance(sid, str) or not _SID.match(sid):
        raise MeasureError(f"not a session id: {sid!r}"[:120], 2)
    try:
        obj = admission.decode(text)        # the cap, UTF-8, depth, JSON and finite numbers
    except Shape as e:
        raise MeasureError(str(e)[:120], 2) from None
    if not isinstance(obj, dict):
        raise MeasureError("stdin is not one JSON object", 2)
    unknown = sorted({admission.key_name(k) for k in obj} - set(KEYS))
    if unknown:
        raise MeasureError("measure refuses unknown keys: " + ", ".join(k[:40] for k in unknown)[:120], 2)
    try:
        shape(obj)
    except Shape as e:
        raise MeasureError(f"measure refuses {e}"[:160], 2) from None
    return obj


def record(sid, text: str, env, now: datetime | None = None) -> Path:
    """Write measure.json in the session's existing directory, then move the resolved file
    to its window (silent on any failure; the next measure retries); return its path."""
    obj = parse(sid, text)
    sdir = resolver.session_dir(resolver.state_dir(env), sid)
    if not sdir.is_dir():
        raise MeasureError(f"no session {sid}", 1)   # never made here: the classic hooks make it
    at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
    body = {"at": at, **{k: obj.get(k) for k in KEYS}}
    path = sdir / MEASURE
    _write_private(path, json.dumps(body, ensure_ascii=False, allow_nan=False) + "\n")
    n = models.engine_window(sdir)
    if n is not None:
        resolver.rewindow(sdir, n)
    return path


def load(sdir) -> dict | None:
    """measure.json for a session directory, or None (absent, torn or not an object)."""
    try:
        d = json.loads((Path(sdir) / MEASURE).read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def stated_limits(sdir) -> list | None:
    """The session's last rateLimits for the ledger row: None when absent, torn, or anything
    the shape check refuses, so only a checked list reaches the row."""
    m = load(sdir)
    try:
        rate_limits(m.get("rateLimits") if m else None)
    except Shape:
        return None
    return m["rateLimits"]


def _when(v) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def _count(v) -> int | None:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def drift(sdir) -> dict:
    """What `status` and `doctor` print: `{form, engine, meter, drift, apart}`; form is
    `none` (no measure.json), `drift`, or `not comparable` (the reason in `why`)."""
    m = load(sdir) if sdir else None
    if m is None:
        return {"form": "none"}
    ctx = m.get("context") if isinstance(m.get("context"), dict) else {}
    t = _count(ctx.get("tokens"))
    mt = meter.load(sdir) or {}
    c = _count(mt.get("context"))
    a, b = _when(m.get("at")), _when(mt.get("ts"))
    out = {"form": "not comparable", "engine": t, "meter": c}
    if t is None:
        return {**out, "why": "no engine tokens"}
    if c is None:
        return {**out, "why": "no meter"}
    if a is None or b is None:
        return {**out, "why": "age unknown"}
    apart = int(abs((a - b).total_seconds()))
    out["apart"] = apart
    if apart > COMPARABLE_S:
        return {**out, "why": f"{apart}s apart"}
    d = abs(t - c) / max(t, 1)
    return {**out, "form": "drift", "drift": d, "tenths": math.floor(1000 * d)}


def line(sdir) -> str:
    """What `status` and `doctor` print after `measure:`."""
    d = drift(sdir)
    if d["form"] == "none":
        return "none"
    if d["form"] == "not comparable":
        return f"not comparable ({d['why']})"
    return (f"engine {d['engine']} tokens / meter {d['meter']} tokens, "
            f"drift {d['tenths'] // 10}.{d['tenths'] % 10}% ({d['apart']}s apart)")
