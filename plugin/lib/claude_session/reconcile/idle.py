"""`eff.idle`: the hq's main-thread ticks that wrote, started and sent nothing, and their
weighted share of the hq's spend in the window.

A tick opens on a prompt (a user line that is no tool result and no meta line) at or after
the window's start and runs to the next prompt; sidechain lines are a helper's and never
count. A call is one `requestId` and `message.id` pair, as the meter keys a turn, priced once
by `weights()`. A tick is idle when no call in it writes outside the charters' folder, runs a
mutating shell line, starts a helper or sends a message. A shell line that only stages or
commits charters (each `git add` or `git commit` naming paths under the folder alone, the
command naming at least one) is a charter write, so idle. A line that cannot be read (bad
JSON, deep nesting, a token count that is no finite number) is skipped and counted in
`unread`. The text read stays in memory: the finding carries numbers only.

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
# a heredoc's body and terminator; the rest of its opening line stays
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1([^\n]*)\n.*?\n[ \t]*\2[ \t]*(?=\n|$)",
                     re.S)
OPS = ("&&", "||", ";;", ">>", "<<", ">&", "<&", ";", "&", "|", "<", ">", "(", ")", "\n")
SEPS = {"&&", "||", ";;", ";", "&", "|", "\n"}
VALUED = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date",
          "--template", "--fixup", "--squash", "--cleanup", "--trailer"}
WHOLE = {"-a", "--all", "--pathspec-from-file"}


class Lines(list):
    """One transcript's objects; `unread` the lines that could not be read."""
    unread = 0


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
            objs = Lines()
            with open(path, "rb") as fh:
                for raw in fh:
                    try:
                        o = json.loads(raw)
                    except Exception:            # bad JSON, deep nesting: skipped, counted
                        objs.unread += 1
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


def _charter(path, folder=False) -> bool:
    """A path under the charters' folder (`folder`: the folder itself too), never through `..`."""
    p = "/" + str(path) + ("/" if folder and not str(path).endswith("/") else "")
    return CHARTERS in p and ".." not in p.split("/")


def _words(cmd):
    """`cmd`'s shell words as (text, is_operator), quotes removed; None when a quote stays
    open. A sketch of `sh`'s rules, enough to read a `git add` or `git commit` line."""
    out, cur, word, i, n = [], [], False, 0, len(cmd)

    def flush():
        if word:
            out.append(("".join(cur), False))
        del cur[:]
    while i < n:
        ch = cmd[i]
        if ch == "'":
            j = cmd.find("'", i + 1)
            if j < 0:
                return None
            cur.append(cmd[i + 1:j])
            word, i = True, j + 1
        elif ch == '"':
            word, i = True, i + 1
            while True:
                if i >= n:
                    return None
                if cmd[i] == "\\" and i + 1 < n and cmd[i + 1] in '"\\$`':
                    cur.append(cmd[i + 1])
                    i += 2
                elif cmd[i] == '"':
                    i += 1
                    break
                else:
                    cur.append(cmd[i])
                    i += 1
        elif ch == "\\":
            if i + 1 < n and cmd[i + 1] != "\n":
                cur.append(cmd[i + 1])
                word = True
            i += 2
        elif ch in " \t\r":
            flush()
            word, i = False, i + 1
        elif ch in "\n;&|<>()":
            flush()
            word = False
            op = next(o for o in OPS if cmd.startswith(o, i))
            out.append((op, True))
            i += len(op)
        else:
            cur.append(ch)
            word, i = True, i + 1
    flush()
    return out


def _git_paths(seg):
    """For a `git add` or `git commit` segment: how many charter paths it names, or False when
    it names another path, stages the whole tree or redirects; None for any other segment."""
    texts = [w for w, _ in seg]
    i = 1
    while i < len(texts) and texts[i] in ("-C", "-c"):
        i += 2
    if not texts or texts[0] != "git" or i >= len(texts) or texts[i] not in ("add", "commit"):
        return None
    if any(op for _, op in seg):
        return False
    sub, paths, skip, rest = texts[i], [], False, False
    for a in texts[i + 1:]:
        if skip:
            skip = False
        elif rest or a == "-" or not a.startswith("-"):
            paths.append(a)
        elif a == "--":
            rest = True
        elif a in WHOLE or (sub == "commit" and re.match(r"^-[A-Za-z]*a", a)):
            return False
        elif a in VALUED:
            skip = True
    if (sub == "add" and not paths) or not all(_charter(p, folder=True) for p in paths):
        return False
    return len(paths)


def charter_only(cmd: str) -> bool:
    """A shell line whose only writes are charters: each segment matching `MUT` is a `git add`
    or `git commit` naming charter paths alone, and the line names at least one."""
    words = _words(HEREDOC.sub(r"\3", cmd))
    if words is None:
        return False
    segs, named = [[]], 0
    for w in words:
        if w[1] and w[0] in SEPS:
            segs.append([])
        else:
            segs[-1].append(w)
    for seg in segs:
        g = _git_paths(seg)
        if g is None:
            if MUT.search(" ".join(w for w, _ in seg)):
                return False
        elif g is False:
            return False
        else:
            named += g
    return named > 0


def _moves(block) -> bool:
    name, inp = block.get("name"), block.get("input")
    inp = inp if isinstance(inp, dict) else {}
    if name in SPAWN or name in SEND:
        return True
    if name in WRITE:
        return not _charter(inp.get("file_path", ""))
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        return bool(MUT.search(cmd)) and not charter_only(cmd)
    return False


def _price(u, w) -> float:
    """A call's weighted tokens; raises on a count that is no finite number (the line is then
    unread)."""
    return sum(int(u.get(k) or 0) * w[p] for k, p in USAGE)


def ticks(objects, since, w) -> list:
    """[{kind, calls, weighted, idle}] for one transcript's ticks that open at or after
    `since` and hold a call."""
    return _scan(objects, since, w)[0]


def _scan(objects, since, w):
    """(ticks, the lines that could not be read); a line that raises is skipped whole."""
    out, tick, seen, unread = [], None, set(), 0
    for o in objects:
        try:
            tick = _line(o, since, w, tick, seen, out)
        except Exception:
            unread += 1
    kept = [{k: v for k, v in t.items() if k != "in"} for t in out if t["in"] and t["calls"]]
    return kept, unread


def _line(o, since, w, tick, seen, out):
    """Fold one line into the ticks; returns the open tick. Reads before it writes, so a line
    that raises leaves no trace."""
    if o.get("isSidechain"):
        return tick
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    c = msg.get("content")
    if o.get("type") == "user":
        if o.get("isMeta") or (isinstance(c, list) and any(
                isinstance(x, dict) and x.get("type") == "tool_result" for x in c)):
            return tick
        text = c if isinstance(c, str) else " ".join(
            str(x.get("text", "")) for x in (c or []) if isinstance(x, dict))
        t = _epoch(o.get("timestamp"))
        tick = {"kind": _kind(text), "calls": 0, "weighted": 0.0, "idle": True,
                "in": t is not None and t >= since}
        out.append(tick)
    elif o.get("type") == "assistant" and tick is not None:
        mid = msg.get("id")
        key = "%s\t%s" % (o.get("requestId"), mid) if mid else None
        new = key is None or key not in seen          # a split call is priced once
        u = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
        price = _price(u, w) if new else 0.0
        moves = any(isinstance(b, dict) and b.get("type") == "tool_use" and _moves(b)
                    for b in (c if isinstance(c, list) else ()))
        if new:
            if key is not None:
                seen.add(key)
            tick["calls"] += 1
            tick["weighted"] += price
        if moves:
            tick["idle"] = False
    return tick


def numbers(files, since, w) -> dict:
    every, unread = [], 0
    for _, objs in files:
        found, bad = _scan(objs, since, w)
        every += found
        unread += bad + getattr(objs, "unread", 0)
    idle = [t for t in every if t["idle"]]
    total = sum((t["weighted"] for t in every), 0.0)
    spent = sum((t["weighted"] for t in idle), 0.0)
    return {"ticks": len(every), "idle": len(idle),
            "idle_loop": sum(t["kind"] == "loop" for t in idle),
            "idle_helper": sum(t["kind"] == "helper" for t in idle),
            "weighted": round(total, 1), "idle_weighted": round(spent, 1),
            "share": round(100.0 * spent / total, 1) if total else None, "unread": unread}


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
