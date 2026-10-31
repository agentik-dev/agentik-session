"""The meter: one reader of the session's spend (overhaul-r1 §2.2).

Definitions are burn-report's, shared by a test:

  a turn     one deduplicated assistant line, keyed (requestId, message.id);
             the first line of a key wins, a line with no message.id counts
             once, each; sidechain lines count and are also counted apart
  tokens     input + cache_creation_input + cache_read_input + output, summed
             over the turns
  context    the last non-sidechain turn's input + cache_creation + cache_read
             (occupancy; output excluded); max and median (low) over every turn.
             A zero-occupancy line by a model the table does not know (Claude
             Code's `<synthetic>` one on an API error) is not the last turn

Only `type`, `usage`, `requestId`, `message.id`, `message.model`, `isSidechain`
and `timestamp` are read; message content never is. Parsing is incremental:
the state carries the offset with the file's inode and size, and restarts from
0 when either says the file is not the one it read.

The ceilings follow the engine's measured window, else the model (models.py): the
window is re-picked at each tool from the engine's reading, else the model read
(`message.model`), else the session's, the declared and the configured models the
resolved file carries, and the role's ceilings for that window apply; meter.json names
both (`window_source`, `limits_source`, e.g. `role:orchestrator window:1000000`).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import budget, models

USAGE = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
         "output_tokens")
DEFAULT_LIMITS = {"ceilings": {"context": 180000, "turns": 400}, "window": 200000,
                  "checkpoint_at": 0.8}
METER = "meter.json"
STATE = "meter-state.json"


@dataclass
class Meter:
    session_id: str
    turns: int
    sidechain_turns: int
    tokens: int
    context: int
    max_context: int
    median_context: int
    model: str | None
    started: str | None
    ceilings: dict
    window: int | None
    checkpoint_at: float
    pct_context: float
    pct_turns: float
    zone: str
    ts: str
    transcript: dict
    signal: dict = field(default_factory=lambda: {"crossed": False, "tools_since": 0})
    builders: list = field(default_factory=list)
    total: dict = field(default_factory=dict)
    builders_source: str = "none"
    window_source: str = "default"
    limits_source: str = "default"

    @property
    def used_pct(self) -> float:
        return max(self.pct_context, self.pct_turns)

    def as_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fresh() -> dict:
    return {"inode": None, "size": 0, "offset": 0, "seen": [], "msgs": [],
            "last_context": 0, "model": None, "started": None}


def _median_low(xs: list) -> int:
    if not xs:
        return 0
    s = sorted(xs)
    return s[(len(s) - 1) // 2]


SYNTHETIC = "<synthetic>"      # the model Claude Code writes on a line no API call made


def _known(model, table) -> bool:
    """A model id the models table names a family for (with no table, any id but
    `<synthetic>`): only such an id replaces the last model read."""
    if not isinstance(model, str) or not model or model == SYNTHETIC:
        return False
    return models.family(model, table) is not None if isinstance(table, dict) else True


def _scan(path: Path, st: dict, table=None) -> dict | None:
    """Fold the bytes appended since `st` into it. None when unreadable. A line by a
    model `table` does not know (a `<synthetic>` one among them, round 1 F2) never
    replaces the last known model, and at zero occupancy never the last context."""
    try:
        info = os.stat(path)
        if st.get("inode") != info.st_ino or info.st_size < st.get("size", 0) \
                or st.get("offset", 0) > info.st_size:
            st = _fresh()
        with open(path, "rb") as f:
            f.seek(st["offset"])
            data = f.read()
    except OSError:
        return None
    st["inode"], st["size"] = info.st_ino, st["offset"] + len(data)
    end = data.rfind(b"\n") + 1               # a partial last line waits
    seen = set(st["seen"])
    for raw in data[:end].splitlines():
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        ts = obj.get("timestamp")
        if st["started"] is None and isinstance(ts, str):
            st["started"] = ts
        msg = obj.get("message")
        if obj.get("type") != "assistant" or not isinstance(msg, dict):
            continue
        mid = msg.get("id")
        if mid:
            key = f"{obj.get('requestId')}\t{mid}"
            if key in seen:
                continue
            seen.add(key)
            st["seen"].append(key)
        u = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
        n = {k: int(u.get(k) or 0) for k in USAGE}
        ctx = n["input_tokens"] + n["cache_creation_input_tokens"] + n["cache_read_input_tokens"]
        side = bool(obj.get("isSidechain"))
        st["msgs"].append([ctx + n["output_tokens"], ctx, int(side)])
        if not side:
            m = msg.get("model")
            known = _known(m, table)
            if known or ctx or not m:
                st["last_context"] = ctx
            if known:
                st["model"] = m
    st["offset"] += end
    return st


def _sums(st: dict) -> dict:
    msgs = st["msgs"]
    ctxs = [m[1] for m in msgs]
    return {"turns": len(msgs), "sidechain_turns": sum(m[2] for m in msgs),
            "tokens": sum(m[0] for m in msgs), "max_context": max(ctxs, default=0),
            "median_context": _median_low(ctxs), "contexts": ctxs}


def _pct(n: int, ceiling) -> float:
    return round(100.0 * n / ceiling, 1) if ceiling else 0.0


def parse(path, state=None, limits=None, policy=None, session_id=None) -> Meter | None:
    """Parse the transcript at `path`, continuing from `state` (updated in place).

    `limits` carries ceilings, window, checkpoint_at (the resolved profile's);
    absent, the shipped defaults. Unreadable transcript: None.
    """
    path = Path(path)
    state = {} if state is None else state
    lim = {**DEFAULT_LIMITS, **(limits or {})}
    own = _scan(path, state.get("own") or _fresh(), lim.get("models"))
    if own is None:
        return None
    state["own"] = own
    ceil, window, window_source, limits_source = _limits(lim, own["model"])
    sid = session_id or path.stem

    builders, bstate = [], state.get("builders") or {}
    sub = path.parent / path.stem / "subagents"
    files = sorted(sub.glob("agent-*.jsonl")) if sub.is_dir() else []
    for f in files:
        b = _scan(f, bstate.get(f.name) or _fresh(), lim.get("models"))
        if b is None:
            continue
        bstate[f.name] = b
        s = _sums(b)
        builders.append({"agent": f.stem[len("agent-"):], "turns": s["turns"],
                         "tokens": s["tokens"], "max_context": s["max_context"]})
    state["builders"] = {k: v for k, v in bstate.items() if k in {f.name for f in files}}

    s = _sums(own)
    allctx = s["contexts"] + [c for b in state["builders"].values() for c in _sums(b)["contexts"]]
    total = {"turns": s["turns"] + sum(b["turns"] for b in builders),
             "sidechain_turns": s["sidechain_turns"] + sum(
                 _sums(b)["sidechain_turns"] for b in state["builders"].values()),
             "tokens": s["tokens"] + sum(b["tokens"] for b in builders),
             "max_context": max(allctx, default=0),
             "median_context": _median_low(allctx)}
    context = own["last_context"]
    pc, pt = _pct(context, ceil.get("context")), _pct(s["turns"], ceil.get("turns"))
    zone = budget.zone_for(max(pc, pt), policy or budget.Policy())
    return Meter(
        session_id=sid, turns=s["turns"], sidechain_turns=s["sidechain_turns"],
        tokens=s["tokens"], context=context, max_context=s["max_context"],
        median_context=s["median_context"], model=own["model"], started=own["started"],
        ceilings={"context": ceil.get("context"), "turns": ceil.get("turns")},
        window=window, checkpoint_at=lim["checkpoint_at"],
        pct_context=pc, pct_turns=pt, zone=zone, ts=_now(),
        transcript={"path": str(path), "inode": own["inode"], "size": own["size"],
                    "offset": own["offset"]},
        signal=dict(state.get("signal") or {"crossed": False, "tools_since": 0}),
        builders=builders, total=total,
        builders_source="subagents" if files else "none",
        window_source=window_source, limits_source=limits_source)


def _limits(lim: dict, observed) -> tuple[dict, int | None, str, str]:
    """(ceilings, window, window_source, limits_source). With the resolved file's
    `windows` and `models`, the window is re-picked: the engine's reading, then the
    model read, then the session's, the declared and the configured models; else the
    limits as given."""
    window = lim.get("window")
    wsrc = lim.get("window_source") or "default"
    lsrc = lim.get("limits_source") or f"default window:{window}"
    windows, table = lim.get("windows"), lim.get("models")
    if isinstance(windows, dict) and isinstance(table, dict):
        w, src = models.pick(table, observed, lim.get("session_model"), lim.get("model"),
                             lim.get("configured_models") or (), lim.get("engine_window"))
        c = windows.get(models.window_class(w))
        if isinstance(c, dict):
            return ({"context": c.get("context"), "turns": c.get("turns")}, w, src,
                    f"{c.get('source')} window:{w}")
    return lim["ceilings"], window, wsrc, lsrc


# --- the session directory ------------------------------------------------------

def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _load(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


LIMIT_KEYS = ("ceilings", "window", "checkpoint_at", "windows", "models", "model",
              "session_model", "configured_models", "window_source", "limits_source")


def limits_for(sdir: Path, env) -> dict:
    """The limits from resolved.json (the ceilings of both windows, the models table,
    the declared and the configured models), else the default profile resolved with no
    repo layer; `engine_window` beside them when the engine has given a reading."""
    s = ((_load(Path(sdir) / "resolved.json") or {}).get("session")) or {}
    if not s:
        try:
            from . import resolver
            s = resolver.resolve(Path(sdir), "meter", env, overlay={}).sections["session"]
        except Exception:                                       # noqa: BLE001
            s = {}
    out = dict(DEFAULT_LIMITS)
    for k in LIMIT_KEYS:
        if s.get(k) is not None:
            out[k] = s[k]
    engine = models.engine_window(sdir)
    if engine is not None:
        out["engine_window"] = engine
    return out


def load_state(sdir: Path) -> dict:
    return _load(Path(sdir) / STATE) or {}


def load(sdir: Path) -> dict | None:
    """meter.json for a session directory, or None."""
    return _load(Path(sdir) / METER)


def save(sdir: Path, m: Meter, state: dict) -> Path:
    sdir = Path(sdir)
    sdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    state["signal"] = m.signal
    _write_atomic(sdir / STATE, json.dumps(state))
    path = sdir / METER
    _write_atomic(path, json.dumps(m.as_dict(), indent=2) + "\n")
    return path


def mtime_age(m: dict) -> float | None:
    """Seconds between the meter's ts and its transcript's mtime; None if unknown."""
    try:
        ts = datetime.fromisoformat(m["ts"]).timestamp()
        return abs(os.stat(m["transcript"]["path"]).st_mtime - ts)
    except (KeyError, TypeError, ValueError, OSError):
        return None


def one_line(m: dict) -> str:
    c, t = m.get("ceilings") or {}, m.get("total") or {}
    return (f"session {m.get('session_id')}: {m.get('pct_context')}% context "
            f"({m.get('context')}/{c.get('context')}), {m.get('pct_turns')}% turns "
            f"({m.get('turns')}/{c.get('turns')}), zone {m.get('zone')}; "
            f"{m.get('tokens')} tokens, {t.get('tokens')} with builders "
            f"({m.get('builders_source')}); {m.get('limits_source')}")

