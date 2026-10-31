"""What the harness costs a session (packet S49): `hooks.jsonl` and `claude_md_bytes`.

`plugin/hooks/run` appends `{"event","ms","exit"}` to `<state>/hooks.jsonl` after each of
this plugin's hooks, and nothing else: no session, time, path, prompt or tool input. It cannot
size the file without a fork, so `hooks.dispatch` calls `rotate` on every hook: at HOOKS_CAP or
more the file becomes `hooks.jsonl.1`, replacing the last, so the two hold at most twice the
cap plus any line racing the rename. `report --hooks` reads both. Nothing that decides reads
any of this, and no failure here ever reaches a hook.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from .ledger import _columns

HOOKS = "hooks.jsonl"
HOOKS_CAP = 1048576
PROJECT_FILES = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md")
MD_HOPS = 5                 # an import chain's depth, as Claude Code documents it
MD_MAX_FILES = 64           # a floor past this: the walk stops counting
MD_READ_CAP = 1048576       # a file past this counts by its size and is not scanned
_FENCE = re.compile(r"^\s*(```|~~~)")
_SPAN = re.compile(r"`[^`\n]*`")
_IMPORT = re.compile(r"(?:^|(?<=\s))@(\S+)")


def rotate(state) -> None:
    """Past the cap, the file becomes the one generation kept. Silent: never raises."""
    try:
        p = os.path.join(state, HOOKS)
        if os.stat(p).st_size >= HOOKS_CAP:
            os.replace(p, p + ".1")
    except Exception:       # noqa: BLE001 - a measure never fails a hook
        pass


def _whole(v) -> bool:
    return type(v) is int


def read_hooks(state) -> list[dict]:
    """The rows of both generations, oldest first; anything that is not a row is skipped."""
    out = []
    for name in (HOOKS + ".1", HOOKS):
        try:
            text = Path(state, name).read_text(errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if (isinstance(d, dict) and isinstance(d.get("event"), str) and d["event"]
                    and _whole(d.get("ms")) and d["ms"] >= 0 and _whole(d.get("exit"))):
                out.append({"event": d["event"], "ms": d["ms"], "exit": d["exit"]})
    return out


def _rank(ordered: list, q: float):
    """The nearest-rank percentile of a sorted list."""
    return ordered[max(math.ceil(q * len(ordered)), 1) - 1]


def hook_stats(rows: list[dict]) -> dict:
    """`{event: {count, p50, p95, nonzero}}`, events in name order, in whole ms."""
    by = {}
    for r in rows:
        by.setdefault(r["event"], []).append(r)
    out = {}
    for event in sorted(by):
        ms = sorted(r["ms"] for r in by[event])
        out[event] = {"count": len(ms), "p50": _rank(ms, .50), "p95": _rank(ms, .95),
                      "nonzero": sum(r["exit"] != 0 for r in by[event])}
    return out


def hooks_table(stats: dict) -> str:
    if not stats:
        return "hooks.jsonl: no rows"
    return _columns(("event", "count", "p50_ms", "p95_ms", "nonzero"),
                    [(e, str(s["count"]), str(s["p50"]), str(s["p95"]), str(s["nonzero"]))
                     for e, s in stats.items()])


def claude_md_stats(rows: list[dict]) -> dict | None:
    """Over the ledger rows that carry `claude_md_bytes`: the newest, its session, p50, max,
    how many. None when none does (a row before S49, or a null)."""
    have = [r for r in rows if _whole(r.get("claude_md_bytes"))]
    if not have:
        return None
    sizes = sorted(r["claude_md_bytes"] for r in have)
    return {"newest": have[-1]["claude_md_bytes"], "session": have[-1].get("session"),
            "p50": _rank(sizes, .50), "max": sizes[-1], "rows": len(have)}


def claude_md_line(rows: list[dict]) -> str:
    s = claude_md_stats(rows)
    if s is None:
        return "claude_md_bytes: no row carries it"
    return (f"claude_md_bytes: newest {s['newest']} ({str(s['session'] or '')[:8]}), "
            f"p50 {s['p50']}, max {s['max']}, {s['rows']} rows")


def _imports(path: str, text: str, home: str) -> list[str]:
    """The `@` targets of one file, outside code spans and fences, resolved: `~/` from home,
    an absolute path as it stands, any other from the importing file's directory."""
    out, fenced = [], False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for t in _IMPORT.findall(_SPAN.sub("", line)):
            if t.startswith("~/"):
                out.append(os.path.join(home, t[2:]))
            else:
                out.append(os.path.join(os.path.dirname(path), t))     # an absolute t stands
    return out


def _walk(cwd: str, env) -> int:
    home = env.get("HOME") or str(Path.home())
    queue = [(os.path.join(env.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude"),
                           "CLAUDE.md"), 0)]
    d = os.path.abspath(cwd)
    while True:
        queue += [(os.path.join(d, name), 0) for name in PROJECT_FILES]
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    seen = {}
    while queue and len(seen) < MD_MAX_FILES:
        path, hop = queue.pop(0)
        real = os.path.realpath(path)
        if real in seen or not os.path.isfile(real):       # a FIFO is never opened
            continue
        size = os.stat(real).st_size
        if size > MD_READ_CAP:
            seen[real] = size
            continue
        with open(real, "rb") as f:
            data = f.read()
        if b"\0" in data:                                  # not text: Claude Code loads none
            continue
        seen[real] = size
        if hop < MD_HOPS:
            queue += [(t, hop + 1) for t in _imports(path, data.decode(errors="replace"), home)]
    return sum(seen.values())


def stated_limits(sdir) -> list | None:
    """The ledger's `rate_limits`, by measure's own reader: a record, which nothing that decides
    reads, so hooks.py still names no measure (M2's criterion 3). Imported here: measure imports
    hooks, which imports this module."""
    from . import measure
    return measure.stated_limits(sdir)


def claude_md_bytes(cwd, env) -> int | None:
    """The on-disk bytes of the CLAUDE.md files a session at `cwd` loads, each once by real
    path, as they stand at the call: the user's (under CLAUDE_CONFIG_DIR, else ~/.claude); each
    of PROJECT_FILES in `cwd` and every ancestor; their `@` imports, to MD_HOPS hops. Not
    counted: managed policy, `.claude/rules/`, a subdirectory's file that loads on demand, auto
    memory, `--add-dir`, a plugin's or a hook's context. None with no usable `cwd` or on any
    failure; it never raises."""
    try:
        if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
            return None
        return _walk(cwd, env)
    except Exception:       # noqa: BLE001 - a measure never loses the ledger's row
        return None
