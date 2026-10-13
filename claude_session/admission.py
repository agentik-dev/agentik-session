"""The admission ledger, in `observe` (design/admission-r1.md §2, §3.1, §5 S25).

`claude-session admission record --session <id>` is what the session plugin's admission
hooks (plugin/hooks/session.ts, the plugin's one module) run at each hook they keep: one JSON object on stdin,
`{kind, ...}`, appended as one line to the machine's ledger,
`<state>/admission/ledger.jsonl`, under one flock waited for at most 2 s. Each kind has a
fixed key list (absent ones null), as ledger.append_chain does; nothing else is kept, so
a spawn's prompt and a message's text never reach the file. `end` sweeps the session's
open spawns (a `done` with `swept: true` each). The ledger rotates when its first parseable
line is older than 24 hours plus one window. Every value is checked by type and bound as
well as its key (M2's fix round, F4): a nested key, an object where a scalar belongs, a
non-finite number or a string that is not UTF-8 is refused, and the file never holds one.
Nothing here decides: S26's `admit` reads it.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import re
import stat
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, rules, store
from .hooks import _SID

DIR = "admission"
LEDGER = "ledger.jsonl"
ROTATED = "ledger.1.jsonl"
LOCK = "ledger.lock"
LOCK_WAIT_S = 2.0
ROTATE_AFTER = timedelta(hours=29)          # 24 hours plus one five-hour window
MAX_STDIN = 64 * 1024

# What stdin may carry per kind; the line is ts, session, kind, then these (null when absent).
INPUT_KEYS = {
    "start": ("interactive",),
    "reading": ("rateLimits",),
    "spawn": ("subagentType", "model", "parentModel", "background", "fork", "description",
              "tool_use_id", "agentId", "context", "rateLimits"),
    "resume": ("to",),
    "done": ("agentId", "tool_use_id", "durationMs", "usage"),
    "end": ("reason",),
}
# Keys the verb sets itself: start's chain (its own environment), done's swept (the sweep).
OWN_KEYS = {"start": ("chain",), "done": ("swept",)}
LINE_KEYS = {k: v + OWN_KEYS.get(k, ()) for k, v in INPUT_KEYS.items()}


# The value checks (M2's fix round, F1 and F4), shared with measure.py: 2.1.296's types, bounded.
MAX_ITEMS = 16            # a list's length (rateLimits, changed) and an object's keys (usage)
NAME_CAP, LIMIT_CAP, DESCRIPTION_CAP = 128, 64, 200
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")


class Shape(ValueError):
    """A value the types do not admit; the message names the field, never the value."""


def key_name(k) -> str:
    return k if isinstance(k, str) and _NAME.match(k) else "<key>"


def text(v, where: str, cap: int, null: bool = True) -> None:
    if v is None and null:
        return
    if not isinstance(v, str) or len(v) > cap:
        raise Shape(f"{where}: not a string of at most {cap} characters")
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        raise Shape(f"{where}: not UTF-8") from None


def number(v, where: str, null: bool = False, low=None, above=None) -> None:
    if v is None and null:
        return
    ok = isinstance(v, (int, float)) and not isinstance(v, bool)
    try:
        ok = ok and math.isfinite(float(v))
    except OverflowError:
        ok = False
    ok = ok and (low is None or v >= low) and (above is None or v > above)
    if not ok:
        bound = f" >= {low}" if low is not None else f" > {above}" if above is not None else ""
        raise Shape(f"{where}: not a finite number{bound}")


def flag(v, where: str) -> None:
    if v is not None and not isinstance(v, bool):
        raise Shape(f"{where}: not true, false or null")


def only(v, where: str, keys) -> dict:
    if not isinstance(v, dict):
        raise Shape(f"{where}: not an object")
    unknown = sorted({key_name(k) for k in v} - set(keys))
    if unknown:
        raise Shape(f"{where}: unknown keys: " + ", ".join(unknown))
    return v


def items(v, where: str) -> list:
    if not isinstance(v, list) or len(v) > MAX_ITEMS:
        raise Shape(f"{where}: not a list of at most {MAX_ITEMS}")
    return v


def context(v, where: str = "context") -> None:
    """SessionContext: tokens? (>= 0), window (> 0), percent?."""
    only(v, where, ("tokens", "window", "percent"))
    number(v.get("tokens"), f"{where}.tokens", null=True, low=0)
    number(v.get("window"), f"{where}.window", above=0)
    number(v.get("percent"), f"{where}.percent", null=True)


def rate_limits(v, where: str = "rateLimits") -> None:
    """SessionRateLimit[]: kind, percentUsed, resetsAt?; at most MAX_ITEMS."""
    for i, r in enumerate(items(v, where)):
        w = f"{where}[{i}]"
        only(r, w, ("kind", "percentUsed", "resetsAt"))
        text(r.get("kind"), f"{w}.kind", LIMIT_CAP, null=False)
        number(r.get("percentUsed"), f"{w}.percentUsed")
        text(r.get("resetsAt"), f"{w}.resetsAt", LIMIT_CAP)


def _scalar(v, where: str) -> None:
    if isinstance(v, str):
        text(v, where, LIMIT_CAP)
    elif v is not None and not isinstance(v, bool):
        number(v, where)


def usage(v, where: str = "usage") -> None:
    """A done's usage: counters, and at most one level of them (cache_creation's)."""
    if v is None:
        return
    if not isinstance(v, dict) or len(v) > MAX_ITEMS:
        raise Shape(f"{where}: not an object of at most {MAX_ITEMS} keys")
    for k, x in v.items():
        w = f"{where}.{key_name(k)}"
        if key_name(k) != k:
            raise Shape(f"{where}: a key that is not a name")
        if isinstance(x, dict):
            if len(x) > MAX_ITEMS or any(isinstance(xx, (dict, list)) for xx in x.values()):
                raise Shape(f"{w}: nested past one level, or over {MAX_ITEMS} keys")
            for kk, xx in x.items():
                if key_name(kk) != kk:
                    raise Shape(f"{w}: a key that is not a name")
                _scalar(xx, f"{w}.{kk}")
        elif isinstance(x, list):
            raise Shape(f"{w}: a list")
        else:
            _scalar(x, w)


def _null_or(check):
    return lambda v, w: None if v is None else check(v, w)


# Each input key's check (F4): a scalar field takes its scalar or null, never an object or list.
VALUE_CHECKS = {
    "interactive": flag, "background": flag, "fork": flag,
    "subagentType": lambda v, w: text(v, w, NAME_CAP), "model": lambda v, w: text(v, w, NAME_CAP),
    "parentModel": lambda v, w: text(v, w, NAME_CAP), "tool_use_id": lambda v, w: text(v, w, NAME_CAP),
    "agentId": lambda v, w: text(v, w, NAME_CAP), "to": lambda v, w: text(v, w, NAME_CAP),
    "reason": lambda v, w: text(v, w, LIMIT_CAP),
    "description": lambda v, w: text(v, w, DESCRIPTION_CAP),
    "durationMs": lambda v, w: number(v, w, null=True, low=0),
    "context": _null_or(context), "rateLimits": _null_or(rate_limits), "usage": usage,
}


def decode(text_in: str) -> object:
    """stdin's text as JSON: over the cap, not UTF-8, a non-finite number, too deep or bad
    JSON raises Shape (a refusal, exit 2)."""
    try:
        n = len(text_in.encode("utf-8"))
    except UnicodeEncodeError:
        raise Shape("stdin is not UTF-8") from None
    if n > MAX_STDIN:
        raise Shape(f"stdin is over {MAX_STDIN} bytes")
    try:
        return json.loads(text_in, parse_constant=_non_finite, parse_float=_finite)
    except _NonFinite as e:
        raise Shape(f"stdin carries a non-finite number: {e}") from None
    except RecursionError:
        raise Shape("stdin is nested too deep") from None
    except ValueError as e:
        raise Shape(f"stdin is not JSON: {e}") from None


class AdmissionError(Exception):
    """A refusal: one line for stderr and the exit code (2 refused, 3 the lock or the disk)."""

    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self.code = code


def directory(env) -> Path:
    return config.state_dir(env) / DIR


def parse(sid, text: str) -> dict:
    """The object stdin carries, checked: a bad id, JSON, kind or key is refused (exit 2)."""
    if not isinstance(sid, str) or not _SID.match(sid):
        raise AdmissionError(f"not a session id: {sid!r}"[:120], 2)
    try:
        obj = decode(text)
    except Shape as e:
        raise AdmissionError(str(e)[:120], 2) from None
    if not isinstance(obj, dict):
        raise AdmissionError("stdin is not one JSON object", 2)
    kind = obj.get("kind")
    if not isinstance(kind, str) or kind not in INPUT_KEYS:
        raise AdmissionError("admission refuses an unknown kind: %r" % str(kind)[:40], 2)
    unknown = sorted(set(obj) - {"kind"} - set(INPUT_KEYS[kind]))
    if unknown:
        raise AdmissionError(f"admission refuses unknown keys for a {kind} line: "
                             + ", ".join(key_name(k)[:40] for k in unknown), 2)
    # The Agent tool sets no length on a description: a long one is clipped, never refused,
    # so observe mode keeps the spawn (M2's verify).
    d = obj.get("description")
    if isinstance(d, str) and len(d) > DESCRIPTION_CAP:
        obj["description"] = d[:DESCRIPTION_CAP]
    try:
        for k in INPUT_KEYS[kind]:
            VALUE_CHECKS[k](obj.get(k), k)
    except Shape as e:
        raise AdmissionError(f"admission refuses a {kind} line: {e}"[:160], 2) from None
    return obj


class _NonFinite(ValueError):
    """NaN, Infinity or a float past the double's range, which json.loads takes by default."""


def _non_finite(word: str):
    raise _NonFinite(word)


def _finite(text: str) -> float:
    x = float(text)
    if not math.isfinite(x):
        raise _NonFinite(text[:40])
    return x


def _ts(now: datetime) -> str:
    return now.astimezone(timezone.utc).isoformat(timespec="seconds")


def line_for(sid: str, obj: dict, env, now: datetime) -> dict:
    kind = obj["kind"]
    line = {"ts": _ts(now), "session": sid, "kind": kind}
    line.update({k: obj.get(k) for k in INPUT_KEYS[kind]})
    if kind == "start":
        line["chain"] = env.get("CLAUDE_SESSION_CHAIN") or None
    if kind == "done":
        line["swept"] = False
    return line


def _lock(d: Path) -> int:
    """The ledger's one lock, held on its own file (rotation renames the ledger)."""
    fd = os.open(d / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise AdmissionError(f"the admission ledger stayed locked past {LOCK_WAIT_S:.0f} s; "
                                     "nothing written", 3) from None
            time.sleep(0.05)


def _rows(p: Path) -> list:
    try:
        text = p.read_text()
    except OSError:
        return []
    rows = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue                      # a torn line is skipped, as every reader does
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _dated(ln: str):
    """A line's ts, when the line parses and its ts is a dated, zoned time; else None."""
    try:
        then = datetime.fromisoformat(json.loads(ln)["ts"])
    except (ValueError, KeyError, TypeError):
        return None
    return then if then.tzinfo is not None else None


def _rotate(d: Path, now: datetime) -> None:
    """Rename the ledger to ledger.1.jsonl when its first parseable line is past
    ROTATE_AFTER. A torn or unreadable line dates nothing (fix round 1, F5): the file is
    dated by the first line that parses, and a file with none is left as it is."""
    p = d / LEDGER
    then = None
    try:
        with open(p, errors="replace") as f:
            for ln in f:
                then = _dated(ln)
                if then is not None:
                    break
    except OSError:
        return
    if then is not None and now - then > ROTATE_AFTER:
        os.replace(p, d / ROTATED)


def _sweep(d: Path, sid: str, now: datetime) -> list:
    """One swept `done` for each of the session's spawns that has no done of its own."""
    rows = [r for name in (ROTATED, LEDGER) for r in _rows(d / name) if r.get("session") == sid]
    dones = [r for r in rows if r.get("kind") == "done"]
    out = []
    for s in (r for r in rows if r.get("kind") == "spawn"):
        aid, tid = s.get("agentId"), s.get("tool_use_id")
        if any((aid is not None and x.get("agentId") == aid)
               or (tid is not None and x.get("tool_use_id") == tid) for x in dones):
            continue
        out.append({"ts": _ts(now), "session": sid, "kind": "done", "agentId": aid,
                    "tool_use_id": tid, "durationMs": None, "usage": None, "swept": True})
    return out


def _append(d: Path, lines: list) -> None:
    p = d / LEDGER
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        data = "".join(json.dumps(x, ensure_ascii=False, allow_nan=False) + "\n" for x in lines).encode()
        if os.fstat(fd).st_size:
            with open(p, "rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    data = b"\n" + data   # a torn tail never swallows this line
        os.write(fd, data)
    finally:
        os.close(fd)


def record(sid, text: str, env, now: datetime | None = None) -> Path:
    """Check stdin's object, then rotate, append, (on `end`) sweep and rewrite band.json
    inside one lock."""
    obj = parse(sid, text)
    now = now or datetime.now(timezone.utc)
    d = directory(env)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(d, 0o700)
    fd = _lock(d)
    try:
        os.fchmod(fd, 0o600)
        _rotate(d, now)
        line = line_for(sid, obj, env, now)
        swept = _sweep(d, sid, now) if line["kind"] == "end" else []
        _append(d, [line, *swept])
        _write_band(d, now, rules.admission(_session_config(env, sid)))
    finally:
        os.close(fd)
    return d / LEDGER


# ---- The fit and the peak (design/admission-r1.md §3.2; packet S26 ruling 2): pure. ----
# Every function below reads the ledger's rows and a `now` passed in; nothing here writes.
FAMILIES = ("opus", "sonnet", "haiku", "fable")
FIVE, SEVEN = "five_hour", "seven_day"
INTERVAL_MIN, INTERVAL_MAX = 10.0, 20.0   # minutes: an interval's least span, and its longest
MIN_INTERVALS = 20                        # below this the seeds stand
ACTIVE = timedelta(minutes=45)            # a main thread is active with a reading this recent
FLOOR = 5.0                               # a running helper's least minutes left
AGE_OUT_SAMPLES = 5                       # dones a type needs before its 95th percentile ages out
WINDOW_MIN = 300.0                        # the age-out of a type with fewer: one five-hour window
SAME_RESET_S = 60                         # two resetsAt this close are one window
EDGE = timedelta(days=1)                  # a time this close to datetime's ends is no time
GRACE = timedelta(minutes=2)              # a stale verdict with no run yet counts this long


def _when(v):
    """A ts or resetsAt as a zoned datetime, else None."""
    if not isinstance(v, str):
        return None
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return None
    try:                                     # in range: a day either side of it is a date
        u = t.astimezone(timezone.utc)
        u - EDGE, u + EDGE
    except OverflowError:
        return None
    return t


def _real(v):
    ok = isinstance(v, (int, float)) and not isinstance(v, bool)
    return float(v) if ok and math.isfinite(v) else None


def _str(v):
    return v if isinstance(v, str) and v else None


def _minutes(d: timedelta) -> float:
    return d.total_seconds() / 60.0


def family(model, parent) -> str:
    """The model family: the first of `model` and `parentModel` that names one (note 8)."""
    for m in (model, parent):
        if isinstance(m, str):
            low = m.lower()
            for f in FAMILIES:
                if f in low:
                    return f
    return "other"


def helper_type(subagent_type, fork) -> str:
    """A helper's type for its life: a fork is its own type, `fork`."""
    return "fork" if fork is True else (_str(subagent_type) or "other")


def limits(lims, kind: str, t: datetime, sid) -> list:
    """(ts, session, percentUsed, resetsAt) for each `kind` window in one rateLimits list;
    a window without a dated resetsAt or a finite percentUsed is not a reading."""
    out = []
    for lim in lims if isinstance(lims, list) else []:
        if not isinstance(lim, dict) or lim.get("kind") != kind:
            continue
        pct, resets = _real(lim.get("percentUsed")), _when(lim.get("resetsAt"))
        if pct is not None and resets is not None:
            out.append((t, sid, pct, resets))
    return out


def readings(rows, kind: str = FIVE) -> list:
    """Every reading line's `kind` window, oldest first."""
    out = []
    for r in rows:
        t = _when(r.get("ts"))
        if r.get("kind") == "reading" and t is not None:
            out += limits(r.get("rateLimits"), kind, t, r.get("session"))
    return sorted(out, key=lambda x: x[0])


def runs(rows) -> list:
    """Each helper's run, oldest first: a spawn to its first done (by agentId or
    tool_use_id), or a resume of an ended helper to the helper's next done."""
    dones = sorted(((t, r) for r in rows if r.get("kind") == "done"
                    and (t := _when(r.get("ts"))) is not None), key=lambda x: x[0])

    def end(t0, aid, tid):
        for t, d in dones:
            if t >= t0 and ((aid and d.get("agentId") == aid) or (tid and d.get("tool_use_id") == tid)):
                return t, d
        return None, None

    def run(t0, aid, tid, fam, typ):
        t1, d = end(t0, aid, tid)
        mins = None
        if d is not None and d.get("swept") is not True:
            ms = _real(d.get("durationMs"))
            mins = ms / 60000.0 if ms is not None and ms >= 0 else _minutes(t1 - t0)
        return {"start": t0, "end": t1, "minutes": mins, "family": fam, "type": typ,
                "agentId": aid, "tool_use_id": tid}

    out, by_agent = [], {}
    events = sorted(((t, r) for r in rows if r.get("kind") in ("spawn", "resume")
                     and (t := _when(r.get("ts"))) is not None), key=lambda x: x[0])
    for t0, r in events:
        if r["kind"] == "spawn":
            x = run(t0, _str(r.get("agentId")), _str(r.get("tool_use_id")),
                    family(r.get("model"), r.get("parentModel")),
                    helper_type(r.get("subagentType"), r.get("fork")))
        else:
            aid = _str(r.get("to"))
            last = by_agent.get(aid)
            if aid is None or (last is not None and (last["end"] is None or last["end"] > t0)):
                continue                      # a message to a running helper starts nothing
            x = run(t0, aid, None, last["family"] if last else "other",
                    last["type"] if last else "other")
        out.append(x)
        if x["agentId"]:
            by_agent[x["agentId"]] = x
    return out


def _p95(xs: list) -> float:
    s = sorted(xs)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


def lives(rs: list) -> dict:
    """type -> (L_t, age-out): the median of its dones' minutes, and their 95th percentile
    (nearest rank) once it has AGE_OUT_SAMPLES, else one window."""
    by: dict = {}
    for r in rs:
        if r["minutes"] is not None:
            by.setdefault(r["type"], []).append(r["minutes"])
    out = {}
    for t, xs in by.items():
        s = sorted(xs)
        mid = len(s) // 2
        median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
        out[t] = (median, _p95(s) if len(s) >= AGE_OUT_SAMPLES else WINDOW_MIN)
    return out


def _life(lv: dict, typ: str, seeds: dict) -> tuple:
    return lv.get(typ, (float(seeds["life"]), WINDOW_MIN))


def _until(r: dict, now: datetime, lv: dict, seeds: dict) -> datetime:
    """A run's end: its done, else now, or its age-out when that comes first."""
    if r["end"] is not None:
        return r["end"]
    return min(now, r["start"] + timedelta(minutes=_life(lv, r["type"], seeds)[1]))


def _same(a: datetime, b: datetime) -> bool:
    return abs((a - b).total_seconds()) <= SAME_RESET_S


def intervals(reads: list) -> list:
    """(start, end) reading pairs: each end is the first reading at least INTERVAL_MIN after
    its start, within INTERVAL_MAX, in the same window and not below it; chained end to start."""
    out, i = [], 0
    while i < len(reads):
        s, j = reads[i], i + 1
        while j < len(reads) and _minutes(reads[j][0] - s[0]) < INTERVAL_MIN:
            j += 1
        if j >= len(reads):
            break
        e = reads[j]
        if _minutes(e[0] - s[0]) <= INTERVAL_MAX and _same(s[3], e[3]) and e[2] >= s[2]:
            out.append((s, e))
        i = j
    return out


def _active(reads: list, t: datetime) -> set:
    return {x[1] for x in reads if t - ACTIVE < x[0] <= t}


def _solve(X: list, y: list):
    """Least squares by the normal equations, Gauss-Jordan with partial pivots; None when
    singular."""
    k = len(X[0])
    M = [[sum(x[i] * x[j] for x in X) for j in range(k)] + [sum(x[i] * v for x, v in zip(X, y))]
         for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-9:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(k):
            if r != c and M[r][c]:
                f = M[r][c] / M[c][c]
                M[r] = [u - f * w for u, w in zip(M[r], M[c])]
    return [M[i][k] / M[i][i] for i in range(k)]


def fit(rows, now: datetime, seeds: dict) -> dict:
    """r = a·m + Σ b_f·n_f over the five-hour intervals, m the active main threads and n_f
    the helpers of family f in flight (time-weighted); a is then refit over the last 45
    minutes with b held. Below MIN_INTERVALS or a singular system: the seeds; a coefficient
    fit below zero is held at its seed and the rest refit, until none is (fix round 1, F3)."""
    seeded = {"a": seeds["a"], "b": dict(seeds["b"])}
    reads = readings(rows, FIVE)
    pairs = [(s, e) for s, e in intervals(reads) if e[0] <= now]
    if len(pairs) < MIN_INTERVALS:
        return {**seeded, "intervals": len(pairs), "seeded": True}
    rs = runs(rows)
    lv = lives(rs)
    spans = [(r["start"], _until(r, now, lv, seeds), r["family"]) for r in rs]
    names = list(seeds["b"])
    X, y, m_of = [], [], []
    for s, e in pairs:
        span = _minutes(e[0] - s[0])
        n = dict.fromkeys(names, 0.0)
        for t0, t1, f in spans:
            lap = _minutes(min(t1, e[0]) - max(t0, s[0]))
            if lap > 0 and f in n:
                n[f] += lap / span
        m = max(1, len(_active(reads, e[0])))
        X.append([m] + [n[f] for f in names])
        y.append((e[2] - s[2]) / span)
        m_of.append((e[0], m, n))
    used = [0] + [i + 1 for i, f in enumerate(names) if any(row[i + 1] for row in X)]
    seed_of = [seeds["a"]] + [seeds["b"][f] for f in names]
    held: dict = {}                       # column -> its seed: a coefficient fit below zero
    while True:                           # hold the lowest at its seed, refit the rest
        free = [i for i in used if i not in held]
        rest = [v - sum(row[i] * s for i, s in held.items()) for row, v in zip(X, y)]
        beta = _solve([[row[i] for i in free] for row in X], rest) if free else []
        if beta is None:
            return {**seeded, "intervals": len(pairs), "seeded": True}
        got = dict(zip(free, beta))
        low = min((i for i in free if got[i] < 0), key=lambda i: got[i], default=None)
        if low is None:
            break
        held[low] = seed_of[low]
    got.update(held)
    b = {f: got.get(i + 1, seeds["b"][f]) for i, f in enumerate(names)}
    a = got[0]
    recent = [(m, v - sum(b[f] * n[f] for f in names))
              for (t, m, n), v in zip(m_of, y) if t > now - ACTIVE]
    if recent:
        a = sum(m * v for m, v in recent) / sum(m * m for m, _ in recent)
    return {"a": a if a >= 0 else seeds["a"], "b": b, "intervals": len(pairs), "seeded": False}


def _rise(rows, reads: list, now: datetime, T: float, seeds: dict, sids: set) -> tuple:
    """(rise, fit, lives, running) with no new spawn: a·m·T, m the active main threads
    (and `sids`), plus each running helper's b_f·min(T, max(L_t − age, 5)); `running`
    counts the helpers in flight, those with no done and not aged out."""
    f = fit(rows, now, seeds)
    rs = runs(rows)
    lv = lives(rs)
    rise, running = f["a"] * len(_active(reads, now) | sids) * T, 0
    for r in rs:
        if r["end"] is None:
            L, out = _life(lv, r["type"], seeds)
            age = _minutes(now - r["start"])
            if 0 <= age <= out:
                running += 1
                rise += f["b"].get(r["family"], seeds["b"]["other"]) * min(T, max(L - age, FLOOR))
    return rise, f, lv, running


def project(rows, req: dict, sid, now: datetime, seeds: dict):
    """peak = P + a·T + Σ (running) b_f·min(T, max(L_t − age, 5)) + b_f·min(T, L_t) (the
    new spawn), from the newest five-hour reading whose resetsAt is ahead (the request's
    own counts, at `now`); None when there is none."""
    reads = readings(rows, FIVE)
    fresh = [x for x in reads + limits(req.get("rateLimits"), FIVE, now, sid) if x[3] > now]
    if not fresh:
        return None
    _, _, P, resets = max(enumerate(fresh), key=lambda ix: (ix[1][0], ix[0]))[1]
    T = max(0.0, _minutes(resets - now))
    rise, f, lv, _ = _rise(rows, reads, now, T, seeds, {sid})
    fam = family(req.get("model"), req.get("parentModel"))
    typ = helper_type(req.get("subagentType"), req.get("fork"))
    rise += f["b"].get(fam, seeds["b"]["other"]) * min(T, _life(lv, typ, seeds)[0])
    return {"peak": P + rise, "P": P, "T": T, "resets": resets, "fit": f}


# ---- The verdict and its texts (design/admission-r1.md §3.3; packet S26 ruling 4) ----
# In S26 the mode is `observe`: the verdict is recorded and answered, and nothing refuses.
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WAIT = "admission: not started. The window has no fresh reading yet; retry in a minute."


def _pct(x: float) -> str:
    return str(int(math.floor(x + 0.5)))


def _local(t: datetime, tz, plus: timedelta = timedelta(0)) -> datetime:
    """t + plus in tz; at datetime's ends, t as it came (fix round 1, F1: never raises)."""
    try:
        return (t + plus).astimezone(tz)
    except (OverflowError, ValueError):
        return t


def _hm(t: datetime, tz, plus: timedelta = timedelta(0)) -> str:
    return _local(t, tz, plus).strftime("%H:%M")


def texts(verdict: str, P=None, resets=None, rise=None, tz=None) -> str:
    """§3.3's text for a verdict, word for word; the reset is local HH:MM (`tz` for tests)."""
    if verdict == "wait":
        return WAIT
    if verdict == "denied":
        day = DAYS[_local(resets, tz).weekday()]
        return (f"admission: not started. The seven-day window is at {_pct(P)}% and resets "
                f"{day} {_hm(resets, tz)}. Spawn nothing more; checkpoint and leave the next "
                "step to the owner.")
    head = (f"admission: not started. The five-hour window is at {_pct(P)}% and resets at "
            f"{_hm(resets, tz)}.")
    if verdict == "not-started":
        return head + " Continue in this thread."
    if verdict == "deferred":
        return (head + f" This spawn projects {_pct(rise)} points, past the ceiling. Do not "
                "retry now. It is deferred: a sitting in this chain is woken when it fits, by "
                f"{_hm(resets, tz, timedelta(minutes=1))} at the latest. Work in this thread "
                "is fine.")
    return ""                                    # admitted, unread and stale carry no text


def _stale_run(rows, rs: list, v: dict, t: datetime):
    """The run a stale verdict admitted: the spawn with its tool_use_id; else, for a resume
    (a verdict of family and type `other`), the run of the helper that the verdict's session
    next resumed within GRACE (its `to`, once known); None while neither has landed."""
    tid = _str(v.get("tool_use_id"))
    r = next((r for r in rs if tid is not None and r["tool_use_id"] == tid), None)
    if r is not None or v.get("family") != "other" or v.get("type") != "other":
        return r
    sent = sorted(((tx, x) for x in rows if x.get("kind") == "resume"
                   and x.get("session") == v.get("session")
                   and (tx := _when(x.get("ts"))) is not None and t <= tx <= t + GRACE),
                  key=lambda x: x[0])            # by time alone: two in one second (fix round 1, F1)
    if not sent:
        return None
    tx, x = sent[0]
    aid = _str(x.get("to"))
    theirs = [r for r in rs if aid is not None and r["agentId"] == aid and r["start"] <= tx]
    return theirs[-1] if theirs else None


def _stale_in_flight(rows, req: dict, since: datetime, now: datetime, seeds: dict) -> bool:
    """Another spawn admitted under a stale reading (verdict `stale` since the window's
    reset) whose run has no done and has not aged out; one with no run counts only within
    GRACE of its verdict (fix round 1, F2)."""
    rs = runs(rows)
    lv = lives(rs)
    mine = _str(req.get("tool_use_id"))
    for v in rows:
        t = _when(v.get("ts"))
        tid = _str(v.get("tool_use_id"))
        if v.get("kind") != "verdict" or v.get("verdict") != "stale" or t is None or t < since:
            continue
        if tid is not None and tid == mine:
            continue
        r = _stale_run(rows, rs, v, t)
        if r is None:
            if now - t <= GRACE:
                return True
            continue
        if r["end"] is None and _minutes(now - r["start"]) <= _life(lv, r["type"], seeds)[1]:
            return True
    return False


def _interactive(rows, sid) -> bool:
    starts = [r for r in rows if r.get("kind") == "start" and r.get("session") == sid]
    return bool(starts) and starts[-1].get("interactive") is True


def decide(rows, req: dict, sid, now: datetime, settings: dict, tz=None) -> dict:
    """The verdict, in ruling 4's order: unread, stale (or wait), denied, deferred or
    not-started, admitted. `peak` is unrounded; None when no fresh reading projects one."""
    fam = family(req.get("model"), req.get("parentModel"))
    typ = helper_type(req.get("subagentType"), req.get("fork"))
    seeds = settings["seeds"]
    out = {"verdict": "admitted", "mode": settings["mode"], "text": "", "peak": None,
           "P": None, "T": None, "family": fam, "type": typ}
    five = readings(rows, FIVE) + limits(req.get("rateLimits"), FIVE, now, sid)
    if not five:
        return {**out, "verdict": "unread"}
    newest = max(enumerate(five), key=lambda ix: (ix[1][0], ix[0]))[1]
    if newest[3] <= now:
        wait = _stale_in_flight(rows, req, newest[3], now, seeds)
        return {**out, "verdict": "wait" if wait else "stale", "text": texts("wait") if wait else ""}
    p = project(rows, req, sid, now, seeds)
    out.update(peak=p["peak"], P=p["P"], T=p["T"])
    seven = [x for x in readings(rows, SEVEN) + limits(req.get("rateLimits"), SEVEN, now, sid)
             if x[3] > now]
    if seven:
        s = max(enumerate(seven), key=lambda ix: (ix[1][0], ix[0]))[1]
        if s[2] >= settings["ceiling_7d"]:
            return {**out, "verdict": "denied", "text": texts("denied", s[2], s[3], tz=tz)}
    if p["peak"] + settings["margin"] > settings["ceiling"]:
        v = "deferred" if _interactive(rows, sid) else "not-started"
        return {**out, "verdict": v, "text": texts(v, p["P"], p["resets"], p["peak"] - p["P"], tz)}
    return out


# ---- `admission admit` (packet S26 ruling 5): one verdict, one line, inside the lock ----
ADMIT_KEYS = ("subagentType", "model", "parentModel", "background", "fork", "tool_use_id",
              "rateLimits", "resume")
ADMIT_CHECKS = {**VALUE_CHECKS, "resume": flag}
VERDICT_KEYS = ("tool_use_id", "verdict", "mode", "peak", "P", "T", "family", "type")


def parse_admit(sid, text_in: str) -> dict:
    """admit's stdin, checked as `record`'s lines are: a bad id, JSON or key is refused (2)."""
    if not isinstance(sid, str) or not _SID.match(sid):
        raise AdmissionError(f"not a session id: {sid!r}"[:120], 2)
    try:
        obj = decode(text_in)
    except Shape as e:
        raise AdmissionError(str(e)[:120], 2) from None
    if not isinstance(obj, dict):
        raise AdmissionError("stdin is not one JSON object", 2)
    unknown = sorted(set(obj) - set(ADMIT_KEYS))
    if unknown:
        raise AdmissionError("admission admit refuses unknown keys: "
                             + ", ".join(key_name(k)[:40] for k in unknown), 2)
    try:
        for k in ADMIT_KEYS:
            ADMIT_CHECKS[k](obj.get(k), k)
    except Shape as e:
        raise AdmissionError(f"admission admit refuses its object: {e}"[:160], 2) from None
    for i, lim in enumerate(obj.get("rateLimits") or []):
        r = lim.get("resetsAt")
        if r is not None and _when(r) is None:           # fix round 1, F1
            raise AdmissionError(f"admission admit refuses rateLimits[{i}].resetsAt: not a "
                                 "zoned ISO time within datetime's range", 2)
    return obj


def _session_config(env, sid: str) -> dict:
    """The session's resolved `session` section, else {} (the defaults)."""
    try:
        d = json.loads((config.state_dir(env) / "sessions" / sid / "resolved.json").read_text())
    except (OSError, ValueError):
        return {}
    return d.get("session") if isinstance(d, dict) and isinstance(d.get("session"), dict) else {}


def _round(x, n):
    return None if x is None else round(x, n)


def admit(sid, text_in: str, env, now: datetime | None = None) -> dict:
    """Check stdin, then inside the one lock read the ledger, decide and append one
    `verdict` line; the answer is {verdict, mode, text, peak}, and `notes` when the config
    left any (an `enforce` read as `observe`). It never refuses a spawn."""
    req = parse_admit(sid, text_in)
    now = now or datetime.now(timezone.utc)
    notes: list = []
    settings = rules.admission(_session_config(env, sid), notes)
    d = directory(env)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(d, 0o700)
    fd = _lock(d)
    try:
        os.fchmod(fd, 0o600)
        _rotate(d, now)
        rows = [r for name in (ROTATED, LEDGER) for r in _rows(d / name)]
        v = decide(rows, req, sid, now, settings)
        v = {**v, "peak": _round(v["peak"], 2), "T": _round(v["T"], 1),
             "tool_use_id": req.get("tool_use_id")}
        _append(d, [{"ts": _ts(now), "session": sid, "kind": "verdict",
                     **{k: v[k] for k in VERDICT_KEYS}}])
        _write_band(d, now, settings)
    finally:
        os.close(fd)
    out = {k: v[k] for k in ("verdict", "mode", "text", "peak")}
    return {**out, "notes": notes} if notes else out


# ---- The band (design/admission-r1.md §3.5, §3.6; packet S27b): display only ----
# `band()` is pure; `record` and `admit` rewrite band.json from it inside the lock, and the
# module's band and the prompt hook draw `band_line` from that file. Nothing decides on it.
BAND = "band.json"
WINDOW = timedelta(hours=5)
STALE_S = 120                     # the band's age shows past this, as M1's line does
HELD = ("deferred", "wait")       # the verdicts that held a spawn (in observe: would have)
ROOM_CAP = 99                     # room past this reads 99: a pull forward, not a count (F2)
BAND_MAX = 64 * 1024              # band.json past this, or not a regular file, is no band (F4)
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})\Z")


def _newest(xs: list):
    return max(enumerate(xs), key=lambda ix: (ix[1][0], ix[0]))[1]


def _room(peak: float, each: float, T: float, settings: dict):
    """The largest N ≤ ROOM_CAP with peak + N·each + margin ≤ ceiling, at least 0; None when
    one more spawn adds nothing (under a minute to the reset, or b of 0). Counted up, never
    divided, so no b overflows it (fix round 1, F2)."""
    if T < 1 or not each > 0:
        return None
    n = 0
    while n < ROOM_CAP and peak + (n + 1) * each + settings["margin"] <= settings["ceiling"]:
        n += 1
    return n


def band(rows, now: datetime, settings: dict, tz=None) -> dict:
    """{P, peak, ceiling, resetsAt, running, room, deferred, P7, mode, at}: the newest
    five-hour reading not past its reset and its peak with no new spawn, the helpers in
    flight, the room for spawns of the parent's family, the held verdicts since the window's
    start, the seven-day reading; {mode, at} alone with no such reading. resetsAt is local
    (`tz` for tests), so every reader draws the same HH:MM from the file."""
    out = {"mode": settings["mode"], "at": _ts(now)}
    reads = readings(rows, FIVE)
    fresh = [x for x in reads if x[3] > now]
    if not fresh:
        return out
    _, _, P, resets = _newest(fresh)
    seeds = settings["seeds"]
    T = max(0.0, _minutes(resets - now))
    rise, f, lv, running = _rise(rows, reads, now, T, seeds, set())
    spawns = sorted(((t, r) for r in rows if r.get("kind") == "spawn"
                     and (t := _when(r.get("ts"))) is not None),
                    key=lambda x: x[0])            # by time alone: two in one second (fix round 1, F1)
    last = spawns[-1][1] if spawns else {}
    fam = family(last.get("parentModel"), None)
    fam = "opus" if fam == "other" else fam
    typ = helper_type(last.get("subagentType"), last.get("fork")) if last else "other"
    each = f["b"].get(fam, seeds["b"]["other"]) * min(T, _life(lv, typ, seeds)[0])
    held = sum(1 for r in rows if r.get("kind") == "verdict" and r.get("verdict") in HELD
               and (t := _when(r.get("ts"))) is not None and resets - WINDOW <= t <= now)
    seven = [x for x in readings(rows, SEVEN) if x[3] > now]
    return {"P": _round(P, 2), "peak": _round(P + rise, 2), "ceiling": settings["ceiling"],
            "resetsAt": _local(resets, tz).isoformat(timespec="seconds"), "running": running,
            "room": _room(P + rise, each, T, settings), "deferred": held,
            "P7": _round(_newest(seven)[2], 2) if seven else None, **out}


def _write_band(d: Path, now: datetime, settings: dict) -> None:
    """band.json from the whole ledger, inside the caller's lock; atomic and 0600 through
    the private writer. A failure leaves the last band and says so on one stderr line: it is
    display, never the record (fix round 1, F1)."""
    try:
        rows = [r for name in (ROTATED, LEDGER) for r in _rows(d / name)]
        store._write_private(d / BAND, json.dumps(band(rows, now, settings), allow_nan=False) + "\n")
    except Exception as e:  # noqa: BLE001 - the band never fails a record or a verdict
        why = " ".join(f"{type(e).__name__}: {e}".split())[:200]
        print(f"admission: band.json not written ({why}); the ledger line is kept", file=sys.stderr)


def read_band(env):
    """band.json as a dict; None when absent, unreadable, not one object, or not a regular
    file of at most BAND_MAX bytes: opened non-blocking, so a FIFO there never hangs a hook
    (fix round 1, F4)."""
    try:
        fd = os.open(directory(env) / BAND, os.O_RDONLY | os.O_NONBLOCK)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > BAND_MAX:
                return None
            data = os.read(fd, BAND_MAX + 1)
        finally:
            os.close(fd)
        if len(data) > BAND_MAX:
            return None
        b = json.loads(data.decode("utf-8"))
    except (OSError, ValueError):
        return None
    return b if isinstance(b, dict) else None


def _wall(v):
    """A band time: (HH, MM as written, the instant) for a strict zoned ISO string."""
    m = _ISO.match(v) if isinstance(v, str) else None
    t = _when(v) if m else None
    return (m.group(1), m.group(2), t) if t is not None else None


def _count(n: float, one: str, many: str) -> str:
    return f"{_pct(n)} {one if _pct(n) == '1' else many}"


def clip(line: str, columns: int) -> str:
    return line if columns <= 0 or len(line) <= columns else line[:max(1, columns - 1)] + "…"


def band_line(b: dict, now: datetime | None = None, columns: int = 0) -> str:
    """§3.5's line from band.json: `5h P% → peak% · ceiling c · resets HH:MM (h:mm) ·
    n helpers, room for r · d deferred · 7d P7%`, then `observe` and the age past 120 s; a
    part with no figure is left out. The hooks module's admissionLine is its twin."""
    now = now or datetime.now(timezone.utc)
    P, peak, c = _real(b.get("P")), _real(b.get("peak")), _real(b.get("ceiling"))
    parts = ["5h no reading" if P is None
             else f"5h {_pct(P)}%" + (f" → {_pct(peak)}%" if peak is not None else "")]
    if c is not None:
        parts.append(f"ceiling {int(c) if c == int(c) else repr(c)}")
    w = _wall(b.get("resetsAt"))
    if w is not None:
        left = max(0, math.floor((w[2] - now).total_seconds() / 60))
        parts.append(f"resets {w[0]}:{w[1]} ({left // 60}h{left % 60:02d})")
    running, room = _real(b.get("running")), _real(b.get("room"))
    helpers = [_count(running, "helper", "helpers")] if running is not None else []
    helpers += [f"room for {_pct(room)}"] if room is not None else []
    if helpers:
        parts.append(", ".join(helpers))
    d, p7 = _real(b.get("deferred")), _real(b.get("P7"))
    if d is not None:
        parts.append(f"{_pct(d)} deferred")
    if p7 is not None:
        parts.append(f"7d {_pct(p7)}%")
    if b.get("mode") == "observe":
        parts.append("observe")
    a = _wall(b.get("at"))
    age = math.floor((now - a[2]).total_seconds()) if a is not None else None
    if age is not None and age > STALE_S:
        parts.append(f"{age}s old")
    return clip(" · ".join(parts), columns)


# ---- `report`'s window use (design/admission-r1.md §3.6; packet S27b ruling 5) ----
# The target is a floor on use: each five-hour window seen is `held` when a spawn waited in
# it (in observe: would have), else `idle`; a last reading under 90 is marked, never hidden.
FLOOR_PCT = 90


def windows(rows) -> list:
    """One {resetsAt, last, held} per five-hour window in the rows, by resetsAt: its newest
    reading's percentUsed, and whether a `deferred` or `wait` verdict fell inside it, before
    its resetsAt (a verdict at a reset is the next window's)."""
    found: list = []
    for t, _, pct, resets in readings(rows, FIVE):
        w = next((w for w in found if _same(w["resetsAt"], resets)), None)
        if w is None:
            found.append({"resetsAt": resets, "last": pct, "at": t})
        elif t >= w["at"]:
            w.update(last=pct, at=t)
    ws = sorted(found, key=lambda w: w["resetsAt"])
    held = set()                      # each verdict in one window: the earliest whose half-open
    for r in rows:                    # [resetsAt − 5h, resetsAt) holds it (fix round 1, F5)
        t = _when(r.get("ts")) if r.get("kind") == "verdict" and r.get("verdict") in HELD else None
        i = next((i for i, w in enumerate(ws) if t is not None
                  and w["resetsAt"] - WINDOW <= t < w["resetsAt"]), None)
        if i is not None:
            held.add(i)
    return [{"resetsAt": w["resetsAt"], "last": w["last"], "held": i in held}
            for i, w in enumerate(ws)]


def report(env, tz=None) -> str:
    """`report`'s admission section: a row per window, or `admission: no ledger`."""
    d = directory(env)
    if not any((d / name).exists() for name in (ROTATED, LEDGER)):
        return "admission: no ledger"
    ws = windows([r for name in (ROTATED, LEDGER) for r in _rows(d / name)])
    if not ws:
        return "admission: no five-hour reading"
    out = ["admission: five-hour windows"]
    for w in ws:
        row = (f"  {_local(w['resetsAt'], tz).strftime('%Y-%m-%d %H:%M')}  {_pct(w['last'])}%  "
               + ("held" if w["held"] else "idle"))
        out.append(row + ("  under 90" if w["last"] < FLOOR_PCT else ""))
    return "\n".join(out)
