"""The room left to the line at a launch (packet nw4-launch-room; hq design/31 items 14 to 17).

Before a main thread's Agent or Task call, in a session that keeps the sitting discipline, the
PreToolUse hook says how many points of the context ceiling are left to the checkpoint once
every helper out has handed back, and whether the new helper fits; `agentik session status`
prints the same room with each helper out and its expected end.

`room`, `ends`, `kind`, `table`, `minutes`, `verdict`, `line` and `status_line` are pure. `told`
and `status_for` read the session's resolved `session` section (its `launch` keys), its
`meter.json` and the admission ledger's two files; they write nothing and never raise: a fault
in any read gives no line. A hand-back's cost, `back`, is the profile's, the same for every kind,
until a later row measures it. `admission.ends`, a different function, is left as it is.
"""
from __future__ import annotations

import json
import math
import os
import re
import stat
from datetime import datetime, timedelta, timezone

from . import admission, meter

TZ = None                    # the zone a time is shown in: None is the local one; a test names one
LEDGER_RUNS = 10             # R4: a kind with this many ledger runs takes the ledger's minutes
FALLBACK = "general-purpose"  # R3: a kind with no seed and too few runs takes this one's
HELD = ("narrow", "none")    # R8: the verdicts that hold a launch under `deny`
PLAIN = {"build": "builder", "fix": "fix", "phase": "phase 2", "review": "review",
         "refute": "refuter", "scribe": "scribe"}
SHORTER = "start a shorter helper or write its brief for the next sitting"
NEXT = "write its brief for the next sitting"
RESPAWN = "bring the charter current and respawn; the successor starts it"

_FIX = re.compile(r"\b(?:fix|fixes|mend)\b|\breview-\d+", re.I)
_BUILD_N = re.compile(r"\bbuild\s+(\d{1,6})\b", re.I)
_PHASE = re.compile(r"\bphase\s+\d+", re.I)


# ---- pure ------------------------------------------------------------------------------------

def room(line: float, used: float, backs) -> float:
    """R1: `line - meter - the sum of back over the helpers out`, in points of the ceiling."""
    return float(line) - float(used) - sum(float(b) for b in backs)


def ends(start: datetime, now: datetime, median: float, p90: float) -> datetime:
    """R2: the start plus the median; once now is past it, the start plus the ninth decile; once
    now is past that, now."""
    first = start + timedelta(minutes=median)
    if now <= first:
        return first
    second = start + timedelta(minutes=p90)
    return second if now <= second else now


def kind(subagent_type, description) -> str:
    """R3, the measurement's rule (hq design/29 §2 item 3): a relay builder's run is `fix`,
    `phase` or `build` by its description, an adversary's `refute` or `review`; any other type
    is its name after its last colon, and no type is `general-purpose`, Claude Code's own."""
    t = subagent_type.strip() if isinstance(subagent_type, str) else ""
    last = t.rsplit(":", 1)[-1].strip() or FALLBACK
    d = description if isinstance(description, str) else ""
    if last == "builder":
        if _FIX.search(d) or any(int(n) >= 2 for n in _BUILD_N.findall(d)):
            return "fix"
        return "phase" if _PHASE.search(d) else "build"
    if last == "adversary":
        return "refute" if "refut" in d.lower() else "review"
    return last


def _nearest(xs: list, q: float) -> float:
    s = sorted(xs)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def table(seeds: dict, measured) -> dict:
    """R3, R4: kind -> (median, ninth decile) in minutes: the profile's seeds, and for a kind
    with LEDGER_RUNS runs or more in `measured` ((kind, minutes) pairs) the ledger's own, each
    by nearest rank."""
    out = {k: (float(v["median"]), float(v["p90"])) for k, v in seeds.items()}
    by: dict = {}
    for k, m in measured:
        by.setdefault(k, []).append(float(m))
    for k, xs in by.items():
        if len(xs) >= LEDGER_RUNS:
            out[k] = (_nearest(xs, 0.5), _nearest(xs, 0.9))
    return out


def minutes(tab: dict, k: str) -> tuple:
    """A kind's (median, ninth decile); a kind the table lacks takes FALLBACK's."""
    return tab[k] if k in tab else tab[FALLBACK]


def verdict(rm: float, back: float, end: datetime, out_ends: list, now: datetime,
            points: float, alone: float) -> str:
    """R6: `wide`, `fits` (narrow, and it ends no later than the latest end out, or with none
    out than now plus `alone` minutes), `narrow` (narrow, and it would end later) or `none`."""
    after = rm - back
    if after >= points:
        return "wide"
    if after < 0:
        return "none"
    last = max(out_ends) if out_ends else now + timedelta(minutes=alone)
    return "fits" if end <= last else "narrow"


def _hm(t: datetime, tz) -> str:
    return (t.astimezone(tz) if tz is not None else t.astimezone()).strftime("%H:%M")


def _whole(m: float) -> int:
    return max(1, int(m + 0.5))


def _out(n: int) -> str:
    return f"{n} out" if n else "none out"


def plain(k: str) -> str:
    return PLAIN.get(k, "helper")


def line(word: str, rm: float, n_out: int, k: str, median: float, back: float, end: datetime,
         last: datetime | None, now: datetime, alone: float, tz=None) -> str:
    """R7: the one line a launch is told, in the verdict's form."""
    this, cost = f"this {plain(k)}", f"{back:.1f}"
    head = f"launch: room {rm:.1f} to the line, {_out(n_out)}; {this} (about {_whole(median)} min, {cost}) fits"
    if word == "wide":
        return head + ", wide"
    alone_w = f"{alone:g}"
    if word == "fits":
        return head + (f", narrow: it ends about {_hm(end, tz)}, by the last one out at "
                       f"{_hm(last, tz)}" if last is not None else
                       f", narrow: it ends about {_hm(end, tz)}, within the {alone_w} min a "
                       "narrow launch may take with none out")
    if word == "narrow":
        if last is not None:
            gap = _whole((end - last).total_seconds() / 60.0)
            return (f"launch: narrow: {this} would end about {_hm(end, tz)}, {gap} min after "
                    f"the last one out; {SHORTER}")
        gap = _whole((end - now).total_seconds() / 60.0 - alone)
        return (f"launch: narrow: {this} would end about {_hm(end, tz)}, {gap} min past the "
                f"{alone_w} min a narrow launch may take with none out; {RESPAWN}")
    return (f"launch: no room: {rm:.1f} to the line, {_out(n_out)}, and {this} takes {cost}; "
            + (NEXT if n_out else RESPAWN))


def status_line(rm: float, out: list, tz=None) -> str:
    """R10: the room, and each helper out ((kind, end) pairs) with its expected end."""
    if not out:
        return f"launch: room {rm:.1f} to the line, none out"
    return (f"launch: room {rm:.1f} to the line, {len(out)} out: "
            + ", ".join(f"a {plain(k)} about {_hm(e, tz)}" for k, e in out))


# ---- the readers: no write, no raise ----------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _positive(v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError("not a positive number")
    return float(v)


def _regular_rows(p) -> list:
    """One ledger file's rows, read as `admission._rows` reads them, but only from a regular
    file opened so that it never blocks (brief 2 R1): a FIFO, a folder or anything else that is
    no regular file is a fault, and so is a file that holds bytes and no row that parses, or
    bytes that are not UTF-8. A missing file has no rows; a torn line is skipped, as every
    reader of the ledger skips one."""
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    except OSError:
        if os.stat(p).st_size > 0:               # unreadable and not empty: as the first build
            raise ValueError("the admission ledger cannot be read") from None
        return []
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("the admission ledger is no regular file")
        chunks = []
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            chunks.append(b)
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    rows = []
    for ln in raw.decode("utf-8").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    if not rows and raw:
        raise ValueError("the admission ledger does not parse")
    return rows


def _ledger(env) -> list:
    """R4: the rotated file's rows, then the live one's, each read once by `_regular_rows`."""
    d = admission.directory(env)
    return _regular_rows(d / admission.ROTATED) + _regular_rows(d / admission.LEDGER)


def _reading(sid: str, env, now: datetime) -> dict | None:
    """The room and the helpers out for one session; None where the session's section is not
    read or waives the discipline. Raises on a fault, which the callers turn into no line."""
    from . import hooks
    s = hooks._session_section(sid, env)
    if not s or not hooks.discipline(s):
        return None
    cfg = s["launch"]
    back, points = _positive(cfg["back"]), _positive(cfg["narrow"]["points"])
    alone = _positive(cfg["narrow"]["alone"])
    seeds = {k: {"median": _positive(v["median"]), "p90": _positive(v["p90"])}
             for k, v in cfg["kinds"].items()}
    sdir = hooks._session_dir(sid, env, fallback=False)
    m = meter.load(sdir) if sdir else None
    if not isinstance(m, dict):
        raise ValueError("no meter")
    used = max(float(m["pct_context"]), float(m["pct_turns"]))
    if not math.isfinite(used):
        raise ValueError("no meter")
    rows = _ledger(env)
    spawns: dict = {}
    for r in rows:
        if r.get("kind") == "spawn":
            for key in (r.get("tool_use_id"), r.get("agentId")):
                if isinstance(key, str) and key:
                    spawns.setdefault(key, r)

    def kind_of(run: dict) -> str:
        sp = spawns.get(run.get("tool_use_id") or "") or spawns.get(run.get("agentId") or "")
        return kind(run["type"] if run["type"] != "other" else None,
                    sp.get("description") if sp else None)

    tab = table(seeds, [(kind_of(r), r["minutes"]) for r in admission.runs(rows)
                        if r["minutes"] is not None])
    minutes(tab, FALLBACK)                       # a table with no fallback is a fault
    own = admission.runs([r for r in rows if r.get("session") == sid or r.get("kind") == "done"])
    out = []
    for r in own:
        if r["end"] is None:
            k = kind_of(r)
            out.append((k, ends(r["start"], now, *minutes(tab, k))))
    return {"room": room(100.0 * hooks._checkpoint_k(m), used, [back] * len(out)), "out": out,
            "table": tab, "back": back, "points": points, "alone": alone}


def told(payload: dict, env, posture) -> tuple | None:
    """R7, R8: (the line, whether it holds the launch) for a main thread's Agent or Task call
    under `signal`, `ask` or `deny` in a session that keeps the discipline; else None. Never
    raises: a fault in reading the ledger, the meter or the profile is None."""
    try:
        if posture not in ("signal", "ask", "deny"):
            return None
        if payload.get("tool_name") not in ("Agent", "Task") or payload.get("agent_id"):
            return None
        sid = payload.get("session_id")
        if not isinstance(sid, str) or not sid:
            return None
        now = _now()
        rd = _reading(sid, env, now)
        if rd is None:
            return None
        ti = payload.get("tool_input")
        ti = ti if isinstance(ti, dict) else {}
        k = kind(ti.get("subagent_type"), ti.get("description"))
        median = minutes(rd["table"], k)[0]
        end = now + timedelta(minutes=median)
        out_ends = [e for _, e in rd["out"]]
        word = verdict(rd["room"], rd["back"], end, out_ends, now, rd["points"], rd["alone"])
        text = line(word, rd["room"], len(out_ends), k, median, rd["back"], end,
                    max(out_ends) if out_ends else None, now, rd["alone"], TZ)
        return text, word in HELD
    except Exception:                                   # noqa: BLE001  (a check, never a crash)
        return None


def status_for(sid, env) -> str | None:
    """R10: the `launch:` line for `status`, under R8's condition; None otherwise or on a fault."""
    try:
        rd = _reading(sid, env, _now()) if isinstance(sid, str) and sid else None
        return status_line(rd["room"], rd["out"], TZ) if rd else None
    except Exception:                                   # noqa: BLE001  (a read, never a crash)
        return None
