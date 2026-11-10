"""`eff.idle`: the hq's main-thread ticks that wrote, started and sent nothing, and their
weighted share of the hq's spend in the window.

A tick opens on a prompt (a user line that is no tool result and no meta line) at or after
the window's start and runs to the next prompt; sidechain lines are a helper's and never
count. A call is one `requestId` and `message.id` pair, as the meter keys a turn, priced once
by `weights()`. A tick is idle when no call in it writes outside the charters' folder, runs a
mutating shell line, starts a helper or sends a message. The text read stays in memory: the
finding carries numbers only.

`python3 -m claude_session.reconcile.idle --since <epoch> <project dir>` prints the numbers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

from .. import charter

MUT = re.compile(r"git( -C \S+)? (commit|merge|push|add|tag|branch -[dD]|worktree)|gate run"
                 r"|scripts/land|\bmake\b")
SPAWN, SEND, WRITE = ("Agent", "Task"), ("SendMessage",), ("Write", "Edit", "NotebookEdit")
USAGE = (("input_tokens", "input"), ("cache_creation_input_tokens", "cache_write"),
         ("cache_read_input_tokens", "cache_read"), ("output_tokens", "output"))
CHARTERS = "/" + charter.DEFAULT_DIR + "/"


def read_transcripts(project, since):
    """[(path, objects)] for the folder's own `*.jsonl` (never `subagents/`) changed at or
    after `since`, by name; an unreadable folder gives [], an unreadable file or line is
    skipped."""
    try:
        names = sorted(n for n in os.listdir(str(project)) if n.endswith(".jsonl"))
    except OSError:
        return []
    out = []
    for name in names:
        path = os.path.join(str(project), name)
        try:
            if not os.path.isfile(path) or os.path.getmtime(path) < since:
                continue
            objs = []
            with open(path, "rb") as fh:
                for raw in fh:
                    try:
                        o = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(o, dict):
                        objs.append(o)
        except OSError:
            continue
        out.append((path, objs))
    return out


def _epoch(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _kind(text: str) -> str:
    t = text.lstrip()[:400]
    if t.startswith("/loop") or "<command-name>/loop" in t:
        return "loop"
    if "task-notification" in t or "<task_notification" in t:
        return "helper"
    return "other"


def _moves(block) -> bool:
    name, inp = block.get("name"), block.get("input")
    inp = inp if isinstance(inp, dict) else {}
    if name in SPAWN or name in SEND:
        return True
    if name in WRITE:
        return CHARTERS not in "/" + str(inp.get("file_path", ""))
    if name == "Bash":
        return bool(MUT.search(str(inp.get("command", ""))))
    return False


def _int(x) -> int:
    try:
        return int(x or 0)
    except (TypeError, ValueError):
        return 0


def ticks(objects, since, w) -> list:
    """[{kind, calls, weighted, idle}] for one transcript's ticks that open at or after
    `since` and hold a call."""
    out, tick, seen = [], None, set()
    for o in objects:
        if o.get("isSidechain"):
            continue
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        c = msg.get("content")
        if o.get("type") == "user":
            if o.get("isMeta") or (isinstance(c, list) and any(
                    isinstance(x, dict) and x.get("type") == "tool_result" for x in c)):
                continue
            text = c if isinstance(c, str) else " ".join(
                str(x.get("text", "")) for x in (c or []) if isinstance(x, dict))
            t = _epoch(o.get("timestamp"))
            tick = {"kind": _kind(text), "calls": 0, "weighted": 0.0, "idle": True,
                    "in": t is not None and t >= since}
            out.append(tick)
        elif o.get("type") == "assistant" and tick is not None:
            mid = msg.get("id")
            key = "%s\t%s" % (o.get("requestId"), mid) if mid else None
            if key is None or key not in seen:          # a split call is priced once
                if key is not None:
                    seen.add(key)
                u = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
                tick["calls"] += 1
                tick["weighted"] += sum(_int(u.get(k)) * w[p] for k, p in USAGE)
            for b in c if isinstance(c, list) else ():
                if isinstance(b, dict) and b.get("type") == "tool_use" and _moves(b):
                    tick["idle"] = False
    return [{k: v for k, v in t.items() if k != "in"} for t in out if t["in"] and t["calls"]]


def numbers(files, since, w) -> dict:
    every = [t for _, objs in files for t in ticks(objs, since, w)]
    idle = [t for t in every if t["idle"]]
    total = sum((t["weighted"] for t in every), 0.0)
    spent = sum((t["weighted"] for t in idle), 0.0)
    return {"ticks": len(every), "idle": len(idle),
            "idle_loop": sum(t["kind"] == "loop" for t in idle),
            "idle_helper": sum(t["kind"] == "helper" for t in idle),
            "weighted": round(total, 1), "idle_weighted": round(spent, 1),
            "share": round(100.0 * spent / total, 1) if total else None}


def _lib() -> str:
    """The folder holding `claude_session`, the command's working directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def detect(ctx) -> dict:
    from . import finding, sh, slug, weights
    project = os.path.join(str(ctx["roots"]["projects"]), slug(ctx["roots"]["hq"]))
    since = int(ctx["now"] - ctx["window"] * 86400)
    cmd = "cd %s && /usr/bin/python3 -B -m claude_session.reconcile.idle --since %d %s" % (
        sh(_lib()), since, sh(project))
    n = numbers(ctx["readers"].transcripts(project, since), since, weights())
    return finding("eff.idle", ctx["hq"], n["share"], ctx["threshold"], cmd, n, [project])


def main(argv=None) -> int:
    from . import weights
    ap = argparse.ArgumentParser(prog="python3 -m claude_session.reconcile.idle",
                                 description="eff.idle's numbers for one project folder")
    ap.add_argument("--since", type=int, required=True, help="epoch seconds")
    ap.add_argument("project", help="the transcripts' folder")
    a = ap.parse_args(argv)
    n = numbers(read_transcripts(a.project, a.since), a.since, weights())
    print(" ".join("%s %s" % kv for kv in n.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
