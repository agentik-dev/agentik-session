"""What the harness costs a session (packet S49): `hooks.jsonl` and `claude_md_bytes`.

`plugin/hooks/run` exports the start in HOOK_T0 and `exec`s the tool as ever; `cli.cmd_hook`
pops it on entry and ends with `record_hook`, which appends `{"event","ms","exit"}` to
`<state>/hooks.jsonl` and nothing else: no session, time, path, prompt or tool input (Amendment
1). `exit` is the tool's own, and `ms` runs from the shim's `date` to just before the append, so
interpreter teardown is not in it. Lost, and absent rather than wrong: a CLI older than the
plugin, an argparse refusal before the handler, an interpreter failure, a kill.
`hooks.dispatch` calls `rotate` on every hook: at HOOKS_CAP or more the file becomes
`hooks.jsonl.1`, replacing the last, so the two hold at most twice the cap plus any line racing
the rename. `report --hooks` reads both. Nothing that decides reads any of this, and no failure
here ever reaches a hook.
"""
from __future__ import annotations

import json
import math
import os
import re
import stat
import sys
import time
from collections import deque
from pathlib import Path

from . import config
from .ledger import _columns

HOOKS = "hooks.jsonl"
HOOK_T0 = "AGENTIK_SESSION_HOOK_T0"     # the shim's start, in ns: read here and nowhere else
_T0 = re.compile(r"[0-9]{19}")
_EVENT = re.compile(r"[A-Za-z]+")
HOOKS_CAP = 1048576
PROJECT_FILES = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md")
MD_HOPS = 5                 # an import chain's depth, as Claude Code documents it
MD_MAX_FILES = 64           # a floor past this: the walk stops counting
MD_MAX_QUEUE = 1024         # imports queued, each path once: past this the figure is a floor
MD_READ_CAP = 1048576       # a file past this counts by its size and is not scanned
MD_SCAN_CAP = 2097152       # bytes scanned in all: past this a file counts by its size alone
_FENCE = re.compile(r"^\s*(```|~~~)")
_SPAN = re.compile(r"`[^`\n]*`")
_IMPORT = re.compile(r"(?:^|(?<=\s))@(\S+)")


def rotate(state) -> None:
    """Past the cap, the regular file becomes the one generation kept. Silent: never raises."""
    try:
        p = os.path.join(state, HOOKS)
        st = os.lstat(p)
        if stat.S_ISREG(st.st_mode) and st.st_size >= HOOKS_CAP:
            os.replace(p, p + ".1")
    except Exception:       # noqa: BLE001 - a measure never fails a hook
        pass


def take_t0(env) -> str | None:
    """The shim's start, out of the environment, so that nothing a hook spawns inherits it and
    no nested `hook` call writes a row from it. Never raises."""
    try:
        return env.pop(HOOK_T0, None)
    except Exception:       # noqa: BLE001 - a measure never fails a hook
        return None


def exit_status(code) -> int:
    """What Python exits with for `SystemExit(code)`: None is 0, an int is itself, the rest 1
    (and their text on stderr, which is Python's to print)."""
    if code is None:
        return 0
    return int(code) if isinstance(code, int) else 1


def record_hook(t0, event, code, env) -> None:
    """The hook's row, the last thing on its path. Nothing here moves the exit, stdout or stderr,
    or raises; any failure writes nothing and says nothing. No row for a start that is not 19
    ASCII digits or reads ahead of the clock, an event that is not letters, or a code no exit
    status can hold. Stdout is flushed first: teardown's flush of a closed stdout turns the exit
    into 120, so a flush that fails here writes no row, and teardown fails as it would have.
    Regular files only, and no link followed (`lstat`'s semantics, race-free): a dangling link,
    a link to a file, a FIFO, a directory or an absent state folder write nothing, make nothing."""
    try:
        if not (isinstance(t0, str) and _T0.fullmatch(t0)
                and isinstance(event, str) and _EVENT.fullmatch(event)
                and type(code) is int and 0 <= code <= 255):
            return
        if sys.stdout is not None:
            sys.stdout.flush()
        ms = (time.time_ns() - int(t0)) // 1000000
        if ms < 0:
            return
        fd = os.open(os.path.join(config.state_dir(env), HOOKS),
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
                     | os.O_CLOEXEC, 0o600)
        try:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                os.write(fd, b'{"event":"%s","ms":%d,"exit":%d}\n' % (event.encode(), ms, code))
        finally:
            os.close(fd)
    except Exception:       # noqa: BLE001 - a measure never fails a hook
        pass


def _whole(v) -> bool:
    return type(v) is int


def _read_regular(path, flags=0) -> bytes | None:
    """A regular file's bytes, else None: gone, denied, a directory, a FIFO (never blocks on
    one). Never raises for any of these."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | flags)
    except (OSError, ValueError):
        return None
    try:
        with os.fdopen(fd, "rb") as f:
            return f.read() if stat.S_ISREG(os.fstat(fd).st_mode) else None
    except OSError:
        return None


def read_hooks(state) -> list[dict]:
    """The rows of both generations, oldest first, from regular files and through no link;
    anything that is not a row is skipped, a line too deep to parse among them."""
    out = []
    for name in (HOOKS + ".1", HOOKS):
        data = _read_regular(os.path.join(state, name), os.O_NOFOLLOW)
        if data is None:
            continue
        for raw in data.decode(errors="replace").splitlines():
            try:
                d = json.loads(raw)
            except (ValueError, RecursionError):
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


def claude_md_line(rows: list[dict], since=None) -> str:
    """Over the rows `since` left: a period with no row is not a period whose rows lack the key."""
    s = claude_md_stats(rows)
    within = f" since {since}" if since else ""
    if s is None:
        if not rows:
            return f"claude_md_bytes: no ledger row{within}"
        return (f"claude_md_bytes: no row{within} carries it, of {len(rows)}" if since
                else "claude_md_bytes: no row carries it")
    return (f"claude_md_bytes{within}: newest {s['newest']} ({str(s['session'] or '')[:8]}), "
            f"p50 {s['p50']}, max {s['max']}, {s['rows']} rows")


def _imports(path: str, text: str, home: str):
    """The `@` targets of one file, outside code spans and fences, resolved: `~/` from home,
    an absolute path as it stands, any other from the importing file's directory."""
    base, fenced = os.path.dirname(path), False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced or "@" not in line:
            continue
        for t in _IMPORT.findall(_SPAN.sub("", line)):
            yield os.path.join(home, t[2:]) if t.startswith("~/") else os.path.join(base, t)


def _walk(cwd: str, env) -> int:
    """Breadth first, so a path's first hop is its least and queuing it once loses nothing. The
    caps are the floor's: past MD_MAX_FILES, MD_MAX_QUEUE or MD_SCAN_CAP the figure undercounts,
    as it does for a file it cannot read, which Claude Code cannot load either. The caps hold a
    tree's worst far inside SessionEnd's 15 s (packet S49, Amendment 1)."""
    home = env.get("HOME") or str(Path.home())
    roots = [os.path.join(env.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude"), "CLAUDE.md")]
    d = os.path.abspath(cwd)
    while True:
        roots += [os.path.join(d, name) for name in PROJECT_FILES]
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    queue, queued = deque((p, 0) for p in roots), set(roots)
    seen, imported, scanned = {}, 0, 0
    while queue and len(seen) < MD_MAX_FILES:
        path, hop = queue.popleft()
        real = os.path.realpath(path)
        if real in seen or not os.path.isfile(real):       # a FIFO is never opened
            continue
        size = os.stat(real).st_size
        if size > MD_READ_CAP or scanned + size > MD_SCAN_CAP:
            seen[real] = size
            continue
        data = _read_regular(real)
        if data is None or b"\0" in data:                  # denied, or not text: none loads
            continue
        seen[real] = size
        scanned += size
        if hop >= MD_HOPS:
            continue
        for t in _imports(path, data.decode(errors="replace"), home):
            if imported >= MD_MAX_QUEUE:
                break
            if t not in queued:
                queued.add(t)
                imported += 1
                queue.append((t, hop + 1))
    return sum(seen.values())


def stated_limits(sdir) -> tuple[list | None, str | None]:
    """The ledger's `rate_limits` and `rate_limits_at`, by measure's own reader: a copy, which
    nothing that decides reads, so hooks.py still names no measure (M2's criterion 3, mod-r1
    §7.3's amendment). Imported here: measure imports hooks, which imports this module."""
    from . import measure
    return measure.stated_limits(sdir)


def claude_md_bytes(cwd, env) -> int | None:
    """The on-disk bytes of the CLAUDE.md files a session at `cwd` loads, each once by real
    path, as they stand at the call: the user's (under CLAUDE_CONFIG_DIR, else ~/.claude); each
    of PROJECT_FILES in `cwd` and every ancestor; their `@` imports, to MD_HOPS hops. Not
    counted: managed policy, `.claude/rules/`, a subdirectory's file that loads on demand, auto
    memory, `--add-dir`, a plugin's or a hook's context, or a file it cannot read: the rest still
    count. None with no usable `cwd` or on any other failure; it never raises."""
    try:
        if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
            return None
        return _walk(cwd, env)
    except Exception:       # noqa: BLE001 - a measure never loses the ledger's row
        return None


# Packet b1 R7: the session's effort for its ledger row. The launch line's `--effort` (`flag`),
# read from the nearest `claude` ancestor's argv; else the settings' `modelSettings[<model>]
# .effortLevel`, local, project then user, else their top-level `effortLevel` (`settings`);
# else (None, None). A value outside EFFORTS is no value. A mid-session `/effort` is not seen.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
ANCESTOR_HOPS = 8           # the hook's parents to the claude process: a shell or two
PS = "/bin/ps"              # by full path: no PATH entry chooses what reads the tree
PS_WALL = 2.0               # seconds for the whole walk


def _ps(pid: int) -> tuple[int, str] | None:
    """(ppid, args) of one process, None when ps cannot say."""
    import subprocess
    try:
        p = subprocess.run([PS, "-o", "ppid=", "-o", "args=", "-p", str(int(pid))],
                           capture_output=True, text=True, timeout=PS_WALL)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    parts = p.stdout.strip().split(None, 1) if p.returncode == 0 else []
    if not parts or not parts[0].isdigit():
        return None
    return int(parts[0]), parts[1] if len(parts) > 1 else ""


def claude_argv(ps=None, pid=None) -> list[str] | None:
    """The nearest ancestor whose argv[0] is named `claude`, its argv split on whitespace;
    None past ANCESTOR_HOPS, at pid 1, on a loop, after PS_WALL, or when ps cannot say."""
    ps = ps or _ps
    pid = os.getppid() if pid is None else pid
    seen, began = set(), time.monotonic()
    for _ in range(ANCESTOR_HOPS):
        if not isinstance(pid, int) or pid <= 1 or pid in seen:
            return None
        if time.monotonic() - began > PS_WALL:
            return None
        seen.add(pid)
        got = ps(pid)
        if not got:
            return None
        ppid, args = got
        argv = str(args).split()
        if argv and os.path.basename(argv[0]) == "claude":
            return argv
        pid = ppid
    return None


# r1 F2: what claude reads after an option before `--effort` (as chain.py's tables): nothing
# after a bare one, one word after a valued one, one not starting with `-` after an optional
# one, every non-option word after a list. ps joins argv with spaces, so a multi-word value or
# the launch prompt arrives as several words; the first positional word ends the walk.
_BARE_OPTS = frozenset({
    "-p", "--print", "-c", "--continue", "--fork-session", "--verbose", "--strict-mcp-config",
    "--dangerously-skip-permissions", "--allow-dangerously-skip-permissions",
    "--include-partial-messages", "--replay-user-messages", "--no-session-persistence",
    "--ide", "--disable-slash-commands", "--chrome", "--no-chrome", "--mcp-debug",
    "-v", "--version", "-h", "--help"})
_VALUED_OPTS = frozenset({
    "--model", "--fallback-model", "--permission-mode", "--settings", "--setting-sources",
    "--session-id", "--append-system-prompt", "--append-system-prompt-file", "--system-prompt",
    "--system-prompt-file", "--system-prompt-snapshot", "--name", "--output-format",
    "--input-format", "--json-schema", "--max-budget-usd", "--max-turns", "--agent", "--agents",
    "--permission-prompt-tool", "--plugin-dir"})
_OPTIONAL_OPTS = frozenset({"-r", "--resume", "-d", "--debug", "-w", "--worktree", "--from-pr"})
_LIST_OPTS = frozenset({"--tools", "--allowedTools", "--allowed-tools", "--disallowedTools",
                        "--disallowed-tools", "--add-dir", "--mcp-config", "--betas"})


def flag_effort(argv) -> str | None:
    """The last `--effort X` or `--effort=X` among the options of argv (argv[0] the
    program), before the first positional word, as claude takes it (r2: `launch.build` puts
    the config's flag first and the caller's after it). None when there is none, when any
    `--effort` has no level, or where the walk cannot tell an option's words from the prompt's
    (an option not in the tables above; a second word after a list option), even after a valid
    one, since a later flag may sit past the point it cannot read."""
    words = [str(a) for a in (argv or [])[1:]]
    i, seen, lst = 0, None, False
    while i < len(words):
        a = words[i]
        after_list, lst = lst, False
        if a == "--effort":
            if not (i + 1 < len(words) and words[i + 1] in EFFORTS):
                return None
            seen, i = words[i + 1], i + 2
            continue
        if a.startswith("--effort="):
            seen = a.split("=", 1)[1]
            if seen not in EFFORTS:
                return None
            i += 1
            continue
        if a == "--" or not a.startswith("-") or a == "-":
            return None if after_list else seen    # positional; a list's second word: no telling
        if a.startswith("--") and "=" in a:
            pass                        # its value is its own
        elif a in _BARE_OPTS:
            pass
        elif a in _VALUED_OPTS:
            i += 1
        elif a in _OPTIONAL_OPTS:
            i += 1 if i + 1 < len(words) and not words[i + 1].startswith("-") else 0
        elif a in _LIST_OPTS:
            i, lst = i + 1, True        # its first word; a second ends the walk above
        else:
            return None                 # an option the walk cannot read
        i += 1
    return seen


def settings_effort(cwd, env, model) -> str | None:
    """The settings' effort for `model`, else their top-level one; None when neither is set."""
    from . import rules
    here = cwd if isinstance(cwd, str) and os.path.isabs(cwd) else None
    docs = rules._settings(env, here)
    names = [m for m in (model, str(model or "").split("[", 1)[0]) if isinstance(m, str) and m]
    for _, doc in docs:
        ms = doc.get("modelSettings")
        for name in names if isinstance(ms, dict) else ():
            v = ms.get(name).get("effortLevel") if isinstance(ms.get(name), dict) else None
            if v in EFFORTS:
                return v
    for _, doc in docs:
        if doc.get("effortLevel") in EFFORTS:
            return doc["effortLevel"]
    return None


def session_effort(cwd, env, model, ps=None) -> tuple[str | None, str | None]:
    """(effort, effort_from): `flag`, `settings`, or (None, None). Never raises."""
    try:
        v = flag_effort(claude_argv(ps))
        if v:
            return v, "flag"
        v = settings_effort(cwd, env, model)
        return (v, "settings") if v else (None, None)
    except Exception:       # noqa: BLE001 - a measure never loses the ledger's row
        return None, None
