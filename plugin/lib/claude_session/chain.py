"""`agentik session run`: the launcher that restarts a RESPAWN sitting (respawn-r1 §3).

The launcher is the owner's foreground job. Each start runs `claude --session-id <U>
<the owner's arguments>`, byte for byte the same every time except `--model`, which
follows the model the sitting ended on (its `meter.json`; OPEN-QUESTIONS 7, packet S34),
with the launcher's own environment minus `launch.scrub`'s list plus `CLAUDE_SESSION_CHAIN`. It restarts a
sitting only on a RESPAWN close the main thread confirmed, after the turn has ended
and stood `settle` seconds, under the cap, the floor and the stop files; it never
compacts, resumes, detaches or reads a transcript.

A gate job's result follows the chain (packet nw2-chain-inbox, design/31 items 9, 11 and 13):
before each start the launcher writes the sitting's id into the chain home's `sitting.json`,
which names the one session that takes the chain's inbox, and starts the gate's runner where
the queue holds an entry; `_ready` waits for nothing of the gate; the stop line says how many
lines the chain's inbox still holds.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    import termios
except ImportError:                                     # pragma: no cover  (not POSIX)
    termios = None

from . import charter, gate, hooks, launch, ledger, meter, models, resolver
from . import state as statefile

# §3.1's allowlist; a refused flag is named, and adding one is a one-line change.
ALLOWED = frozenset({
    "--model", "--effort", "--fallback-model", "--permission-mode", "--tools",
    "--allowedTools", "--allowed-tools", "--disallowedTools", "--disallowed-tools",
    "--add-dir", "--plugin-dir", "--settings", "--setting-sources", "--mcp-config",
    "--strict-mcp-config", "--append-system-prompt", "--system-prompt-snapshot", "--name",
    "--verbose"})
# The family that resumes, forks, detaches or prints: never on the allowlist.
FORBIDDEN = ("-p", "--print", "-c", "--continue", "-r", "--resume", "--fork-session",
             "--session-id", "--from-pr", "--teleport", "--bg", "--background", "--tmux",
             "-w")
# What claude reads after each allowlisted option (its 2.1.300 definitions): nothing
# after a bare one; every following non-option argument after a list (`<x...>`)
# written apart; one value after the rest (`--system-prompt-snapshot <on|off>` too).
_BARE = frozenset({"--strict-mcp-config", "--verbose"})
_LISTS = frozenset({"--tools", "--allowedTools", "--allowed-tools", "--disallowedTools",
                    "--disallowed-tools", "--add-dir", "--mcp-config"})
DEFAULTS = {"cap": 20, "floor": 600, "settle": 60}
HOLD_MAX = "hold_max"                # nw6b H1: the held respawn's ceiling, run_guards' fourth key
LAUNCHER_GUARDS = "guards.json"      # nw6b H4: the launcher's resolved settle and hold_max
HELD = "held.json"                   # the chain home's word on a hold (S37 ruling 2)
HELPERS = "helpers"                  # nw6 R3: held.json's reason while the helpers hold it
# u1 R1: a helper call open this long, and no helper stamp as recent, is stale: a rejected
# call fires no Post, so its file would hold the launcher forever. Bash's ceiling is 600 s.
STALE_CALL = 1200
# The fold of u1's round 1: a call's `at` is its opening only when it is a finite time not
# after now and not before this floor (2001-09-09): one before it is in another unit, or no
# stamp of the hooks', which write time.time(). Any other call file is aged from first sight.
AT_FLOOR = 1e9
_GUARD_SESSION = "respawn-chain"     # the id the guards resolve under; no overlay is read
_LOOP = re.compile(r"^/loop\s+(\d+)\s*([smhd])(?![A-Za-z])")
_EVERY = re.compile(r"\bevery\s+(\d+)\s*([smhd])[a-z]*\s*$", re.I)   # `/loop <p> every 2h`
_MINUTES = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}
# Packet R2: the reconciler's pass at a respawn close is cut at this many seconds, the
# launcher's own `kill_grace`, so a successor never waits on it longer.
RECONCILE_WAIT = 30
# R2's review fold, F1: while the pass runs, the launcher's stops are read this often, so a
# Ctrl-C, SIGTERM or STOP file ends the pass's process within a second.
RECONCILE_POLL = 0.2
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")    # C0, DEL and C1: never to the owner's tty
_COMPACT = re.compile(r"(?:^|\s)/compact(?:\s|$)")     # the command, never a path's part


def on_tty() -> bool:
    """stdin and stdout are a terminal (§3.1's first refusal)."""
    return os.isatty(0) and os.isatty(1)


def refusal(args, env, where=True) -> str | None:
    """The first of §3.1's refusals that `args` (claude's arguments) and `env` meet, as
    one line; None when the chain may start. The TTY, the chain's name and its lock are
    checked by the caller and by `Chain.run`. `where` off (packet akt-run R3, the dry run)
    skips what is checked of where it runs: a chain, Claude Code, a depth, `claude` on PATH."""
    if where and env.get(hooks.CHAIN_VAR):
        return (f"already inside a chain ({hooks.CHAIN_VAR} is set); "
                "run akt from a plain terminal")
    if where and env.get("CLAUDECODE"):
        return ("inside a Claude Code session (CLAUDECODE is set); "
                "run akt at a terminal")
    d = launch.depth(env) if where else 0
    if d is None or d >= 1:
        return (f"inside a started session or relay child "
                f"({launch.DEPTH_VAR}={str(env.get(launch.DEPTH_VAR))[:20]!r}); "
                "run akt from a plain terminal")
    prev = None
    for a in args:
        a = str(a)
        if _COMPACT.search(a):
            return "/compact is refused; every start is a fresh context"
        if not a.startswith("-"):
            prev = None
            continue
        flag = a.split("=", 1)[0]
        if flag not in ALLOWED:
            if prev is not None:
                return f"{a[:80]!r} after {prev} reads as a flag; write {prev}={a[:80]}"
            why = ("it resumes, forks, detaches or prints" if flag in FORBIDDEN
                   else "it is not on the launcher's allowlist")
            return f"the flag {flag[:80]} is refused; {why}"
        prev = flag if "=" not in a and flag not in _BARE else None
    if where and shutil.which("claude", path=env.get("PATH")) is None:
        return "no `claude` on PATH; install Claude Code or add it to PATH"
    return None


def start_line(argv, env) -> str:
    """The launcher's own argv re-quoted, with the profile prefix when it is set: a line
    that runs as printed (§3.4)."""
    line = shlex.join(str(a) for a in argv)
    prof = env.get("CLAUDE_SESSION_PROFILE")
    return f"CLAUDE_SESSION_PROFILE={shlex.quote(prof)} {line}" if prof else line


def default_name(cwd, env) -> str:
    """`<cwd basename>-<profile or none>`, cut to the chain-name alphabet and 64."""
    raw = f"{Path(cwd).name}-{env.get('CLAUDE_SESSION_PROFILE') or 'none'}"
    return re.sub(r"[^A-Za-z0-9._-]", "-", raw)[:64] or "chain"


def run_guards(cwd, env, flags) -> dict:
    """The resolved `respawn` (§4: the profiles, the repo's config.yaml, then
    config.local.yaml) with `run`'s flags over it, `hold_max` included (nw6b H1; 0 where
    no layer names it, main's rule): what the launcher reads. Raises
    resolver.ResolveError."""
    r = resolver.resolve(cwd, _GUARD_SESSION, env,
                         profile=env.get("CLAUDE_SESSION_PROFILE") or None, overlay={})
    out = {**DEFAULTS, HOLD_MAX: 0, **(r.sections["session"].get("respawn") or {})}
    for k, v in flags.items():
        if k not in out or not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise resolver.ResolveError(f"respawn.{k} must be a non-negative integer")
        out[k] = v
    return out


def guards(cwd, env, flags) -> dict:
    """run_guards' three guards of respawn-r1 §4, `cap`, `floor` and `settle`."""
    return {k: v for k, v in run_guards(cwd, env, flags).items() if k != HOLD_MAX}


def model_table(cwd, env) -> dict:
    """The models table the resolver builds (shipped plus the user's `models:`), resolved
    as the guards are. Raises resolver.ResolveError."""
    r = resolver.resolve(cwd, _GUARD_SESSION, env,
                         profile=env.get("CLAUDE_SESSION_PROFILE") or None, overlay={})
    table = r.sections["session"].get("models")
    return table if isinstance(table, dict) else {}


def _model_at(args) -> tuple[int, bool] | None:
    """(index, joined) of the last `--model X` (the value's index) or `--model=X` (the
    token's) in the owner's arguments; None without one. A value never begins with '-'
    (`refusal`), so a `--model` token is always the flag."""
    at = None
    for i, a in enumerate(args):
        a = str(a)
        if a == "--model" and i + 1 < len(args):
            at = (i + 1, False)
        elif a.startswith("--model="):
            at = (i, True)
    return at


def carry(args, read, table) -> tuple[list, str | None, str | None]:
    """(the successor's arguments, the carried model or None, the start line's model or
    None) for a sitting whose meter read `read` (S34 rulings 1 and 2). Nothing carries
    without a start `--model`, a read model whose family the table knows, or with one of
    the start line's family; else that one value is replaced in its own position and form,
    with `[1m]` when the start line's window is 1M or more and the table has the read
    family's `-1m` entry."""
    args = [str(a) for a in args]
    at = _model_at(args)
    if at is None:
        return args, None, None
    i, joined = at
    start = args[i][len("--model="):] if joined else args[i]
    if not isinstance(table, dict) or not isinstance(read, str):
        return args, None, start
    fam = models.family(read, table)
    if fam is None or read == meter.SYNTHETIC or fam == models.family(start, table):
        return args, None, start
    one_m = (models.window_of(start, table) or 0) >= models.ONE_M
    value = (f"{read}[1m]" if one_m and f"{fam}{models.SUFFIX}" in table
             and not models.marked(read) else read)
    out = list(args)
    out[i] = f"--model={value}" if joined else value
    return out, value, start


def long_loop(args) -> float | None:
    """The minutes of a last positional `/loop` of 60 minutes or more, else None
    (packet S20 ruling 6: its question waits at every start)."""
    if not args or str(args[-1]).startswith("-"):
        return None
    last = str(args[-1])
    m = _LOOP.match(last) or (_EVERY.search(last) if last.startswith("/loop") else None)
    if not m:
        return None
    minutes = int(m.group(1)) * _MINUTES[m.group(2).lower()]
    return minutes if minutes >= 60 else None


def prompt_gap(args) -> str | None:
    """None when claude's arguments carry a positional first prompt (S31: a chain without
    one restarts into an idle session); else "", or the list option that reads the would-be
    prompt as one more of its values. An option's value is never a prompt: one argument
    after a valued option, and every non-option argument after a list written apart."""
    takes, lst, gap = False, None, ""
    for a in map(str, args):
        if takes:
            takes = False
        elif a.startswith("-"):
            flag, bare = a.split("=", 1)[0], "=" in a
            takes = not bare and flag not in _BARE
            lst = flag if not bare and flag in _LISTS else None
        elif lst:
            gap = lst
        else:
            return None
    return gap


def reconcile_argv() -> list:
    """The close's pass (packet R2): this interpreter and this tree's launcher, as
    `gate.spawn_serve` runs its runner, then the verb with no `--force`."""
    runner = Path(__file__).resolve().parent.parent / "agentik-session"
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.environ.get("HOME", ""), ".cache")
    prefix = os.path.join(cache, "agentik", "pycache")
    return [sys.executable, "-I", "-X", "pycache_prefix=" + prefix, str(runner), "reconcile"]


def _clean(line: str) -> str:
    """One line of the pass's output for the owner's terminal: control characters dropped,
    whitespace folded (R2's review fold, F7)."""
    return " ".join(_CONTROL.sub("", line).split())


def home(state, name: str) -> Path | None:
    """The chain `name`'s home, `<state>/respawn/<name>/` (its lock, STOP, held.json and,
    since S39, state.md with state.json); None for a name that is not a chain's."""
    if not (isinstance(name, str) and hooks.CHAIN_RE.match(name)):
        return None
    return Path(state) / "respawn" / name


def held_line(state, name: str, sid: str) -> str | None:
    """S37 ruling 2: `respawn held: <reason> since <HH:MM>` when the chain `name`'s home
    holds held.json naming the session `sid`; None otherwise, or for a name that is not a
    chain's (hooks.CHAIN_RE)."""
    where = home(state, name)
    if not (sid and where):
        return None
    d = _json(where / HELD) or {}
    reason, since = d.get("reason"), d.get("since")
    if (d.get("session") != sid or not isinstance(reason, str) or not reason
            or reason == HELPERS):               # nw6: the helpers' hold is held_by's
        return None
    try:
        at = time.strftime("%H:%M", time.localtime(since)) if _num(since) else "?"
    except (OverflowError, OSError, ValueError):
        at = "?"
    return f"respawn held: {reason} since {at}"


def proc_started(pid) -> float | None:
    """nw6 Z3: the process `pid`'s start time in whole seconds since the epoch, as `ps -o
    lstart=` says it; None for no process, or when ps cannot say. Never raises."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        r = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True,
                           text=True, timeout=5, env={**os.environ, "LC_ALL": "C"})
        text = " ".join(r.stdout.split())
        if r.returncode != 0 or not text:
            return None
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y"))
    except (OSError, ValueError, OverflowError, subprocess.SubprocessError):
        return None


def launcher_alive(pid, started) -> bool:
    """nw6 Z3: the launcher that wrote a record is alive: its `pid` is a live process
    (gate._alive) whose start time is the record's `started`. A pid reused by another
    process, or a record with no start time, is stale."""
    return bool(_num(started) and gate._alive(pid) and proc_started(pid) == started)


def held_by(state, name: str, sid: str, now: float, alive=None) -> dict | None:
    """nw6 R2, R3: the helpers' hold of `sid`'s marked respawn, from the chain home's
    held.json as the launcher wrote it, `{marked, since, held_minutes, by}`: None when the
    record is no helpers' hold naming `sid`, its launcher is not alive under the record's
    start time (`alive(pid, started)`, launcher_alive by default: a stale record), or
    `sid` has no marker. The hold counts from the later of the mark and the record's
    `since` (Z3); each label prints in printable ASCII (Z4). A read; never raises."""
    from . import room
    try:
        where = home(state, name)
        if not (sid and where):
            return None
        d = _json(where / HELD) or {}
        since, by = d.get("since"), d.get("by")
        if (d.get("reason") != HELPERS or d.get("session") != sid or not _num(since)
                or not isinstance(by, list) or not by
                or not all(isinstance(b, str) and b for b in by)):
            return None
        if not (alive or launcher_alive)(d.get("pid"), d.get("started")):
            return None
        mk = _json(resolver.session_dir(state, sid) / hooks.MARKER) or {}
        marked = mk.get("written")
        if mk.get("session") != sid or not _num(marked):
            return None
        out = {"marked": marked, "since": since,
               "held_minutes": max(0, int((now - max(since, marked)) // 60)),
               "by": [room.printable(b) for b in by]}
        if _num(d.get("until")):                        # nw6b H3: only under a ceiling
            out["until"] = d["until"]
        return out
    except Exception:                                   # noqa: BLE001 - a read, no line
        return None


TELL = "tell them to commit and hand back, or stop them"   # nw6b H3, from half the ceiling


def _hhmm(t) -> str:
    try:
        return time.strftime("%H:%M", time.localtime(t))
    except (OverflowError, OSError, ValueError, TypeError):
        return "?"


PAST_CEILING = "the restart comes once this turn has ended"   # nw6b Y2: `until` is past


def when_words(until) -> str:
    """nw6b H3: how the lines that say a hold end while a ceiling is set."""
    return f"or at {_hhmm(until)} whatever is out"


def past_until(until, now) -> bool:
    """nw6b Y2: the ceiling's moment has come, so no line names it."""
    return bool(_num(until) and _num(now) and now >= until)


def held_words(d: dict, tell: bool = False, now=None) -> str:
    """nw6 R2: the clause the prompt's line and `status` say while the helpers hold; under
    a ceiling (nw6b H3) it ends with when_words, and `tell` (the prompt's line, from half
    the ceiling on) puts TELL before that. Once `now` is at or past `until` (Y2) it ends
    PAST_CEILING instead, with no TELL."""
    n = len(d["by"])
    out = (f"respawn marked at {_hhmm(d['marked'])}, held {d['held_minutes']} min by {n} "
           f"helper{'' if n == 1 else 's'}: " + ", ".join(f'"{b}"' for b in d["by"]))
    if "until" not in d:
        return out
    if past_until(d["until"], now):
        return f"{out}; {PAST_CEILING}"
    return (out + (f"; {TELL}" if tell else "")
            + f"; the restart comes once they are quiet, {when_words(d['until'])}")


def past_half(state, sid: str, d: dict, now: float) -> bool:
    """nw6b H3: `now` is at or past half the ceiling, counted from the sitting's first
    confirmed mark (first_mark) to held.json's `until`. A read; never raises."""
    try:
        until = d.get("until")
        first = first_mark(resolver.session_dir(state, sid))
        return _num(until) and first is not None and 2 * now >= first + until
    except Exception:                                   # noqa: BLE001
        return False


def helper_hold(sdir: Path, now: float, mono: float, first: dict, settle, stale_call,
                held_calls: list | None = None):
    """§3.3 step 3's helper clause (ruling 2, u1 R1), the one reading of what the launcher
    waits on, for `_ready`, for held.json and for the respawn mark (nw6 Z1, Z2): (open,
    stamp, stale). `open` holds the agent id (None where the file names none) of each call
    that holds: open under `stale_call` seconds, or any open call while a helper stamp is
    that recent. `stamp` is True while the helpers' stamp holds: malformed, or under
    `settle` seconds old. `stale` holds the calls an end would pass, `{"id", "age"}`.
    A call whose `at` is no time (`_opened`) is aged from its first sight, `first[path]` on
    `mono`, which this sets; its age is then None (u1's fold). `held_calls`, where given,
    gains `{"id", "age"}` for each call that holds (nw6b Y3: what a ceiling goes past)."""
    # calls/ first, then the stamp: a helper's Post stamps before it closes (B-F1), so a
    # close between the two reads leaves a fresh stamp, never a gap.
    try:
        paths = sorted(p for p in (sdir / hooks.CALLS).iterdir() if not p.name.startswith("."))
    except FileNotFoundError:
        paths = []
    except OSError:
        paths = [sdir / hooks.CALLS]     # calls/ will not list: aged from first sight
    calls = []                           # (id, age in seconds, from `at` or not, agent)
    for p in paths:
        try:
            doc = _json(p) or {}
            at, aid = doc.get("at"), doc.get("agent_id")
        except Exception:                # one file's error holds a poll at most (fold)
            at = aid = None
        seen = first.get(str(p))
        if _opened(at, now) and (seen is None or now - at >= mono - seen):
            calls.append((p.name, now - at, True, aid))
        else:                            # the older of `at` and first sight counts
            seen = first.setdefault(str(p), mono)
            calls.append((p.name, mono - seen, False, aid))
    helper = _json(sdir / hooks.HELPER_ACTIVITY)
    bad = helper is not None and not _num(helper.get("at"))     # a malformed stamp holds
    # u1 R1: a call is stale once it and every helper stamp are `stale_call` old.
    # A stamp that is no time (`_opened`) counts for neither bound, as NaN always read.
    h = helper["at"] if helper is not None and not bad and _opened(helper["at"], now) else None
    recent = h is not None and h > now - stale_call
    holds = [c for c in calls if c[1] < stale_call or (recent and not bad)]
    if held_calls is not None:
        held_calls.extend({"id": cid, "age": int(age) if timed else None}
                          for cid, age, timed, _ in holds)
    holding = [aid if isinstance(aid, str) else None for _, _, _, aid in holds]
    if bad:
        return holding, True, []
    stale = [] if holding else [{"id": cid, "age": int(age) if timed else None}
                                for cid, age, timed, _ in calls]
    return holding, h is not None and h > now - settle, stale


def first_mark(sdir: Path) -> float | None:
    """nw6b H2: the moment the held respawn's ceiling counts from, the `written` of the
    sitting's first confirmed mark, from `respawn-first.json` (hooks._confirm writes it
    once); else the marker's own `written`, for a confirm older than that file; None for
    neither. A time below AT_FLOOR or past the year 5000 is none. A read; never raises."""
    try:
        for name, key in ((hooks.FIRST_MARK, "at"), (hooks.MARKER, "written")):
            d = _json(sdir / name) or {}
            at = d.get(key)
            if d.get("session") == sdir.name and _num(at) and AT_FLOOR <= at <= 1e11:
                return at
    except Exception:                                   # noqa: BLE001 - no moment
        pass
    return None


def labelled(adir, ids: list) -> list:
    """nw6 R1, R3: the labels of the helpers whose agent ids hold (helper_hold's `open`),
    each read from its spawn line in the ledger under `adir` (room.labels), room.ANY for a
    miss or a call that names no agent; in agent id order, each label once."""
    from . import room
    want = sorted({i for i in ids if isinstance(i, str)})
    got = room.labels(adir, want) if want else {}
    out = [got.get(i, room.ANY) for i in want] + ([room.ANY] if None in ids else [])
    return list(dict.fromkeys(out))


def _stamp_helper(sdir: Path) -> str | None:
    """nw6b H5, Y1: the id-shaped agent id the helpers' stamp names, None where it names
    none, or names a helper whose end (hooks.ENDED, its SubagentStop) is recorded at or
    after the stamp: an ended helper is never named. A read; never raises."""
    try:
        d = _json(sdir / hooks.HELPER_ACTIVITY) or {}
        aid, at = d.get("agent_id"), d.get("at")
        if not (isinstance(aid, str) and hooks._SID.match(aid)):
            return None
        end = _json(sdir / hooks.ENDED / f"{aid}.json")
        if end is not None and not (_num(end.get("at")) and _num(at) and at > end["at"]):
            return None                  # ended after its stamp, or a record unread as time
        return aid
    except Exception:                                   # noqa: BLE001 - name none
        return None


def launcher_guards(state, name: str, sid: str) -> dict | None:
    """nw6b H4: the `settle` and `hold_max` the launcher of the chain `name` resolved for
    the sitting `sid`, from guards.json beside sitting.json; None where it names another
    sitting, or holds no whole number of 0 or more for either. A read; never raises."""
    try:
        where = home(state, name)
        d = (_json(where / LAUNCHER_GUARDS) or {}) if where and sid else {}
        if d.get("session") != sid or not all(
                isinstance(d.get(k), int) and not isinstance(d.get(k), bool) and d[k] >= 0
                for k in ("settle", HOLD_MAX)):
            return None
        return {"settle": d["settle"], HOLD_MAX: d[HOLD_MAX]}
    except Exception:                                   # noqa: BLE001
        return None


def _mark_guards(state, sid: str, env, cwd) -> dict:
    """nw6b H4: the mark reads the launcher's own values, the config's only where it wrote
    none; the defaults (no ceiling) where the config does not resolve."""
    got = launcher_guards(state, env.get(hooks.CHAIN_VAR) or "", sid)
    if got is not None:
        return got
    try:
        return run_guards(Path.cwd() if cwd is None else cwd, env, {})
    except Exception:                                   # noqa: BLE001 - the default
        return {**DEFAULTS, HOLD_MAX: 0}


def mark_holders(state, sid: str, env, cwd=None) -> list:
    """nw6 Z2: at the respawn mark, the labels of what the launcher's rule would wait on now
    (helper_hold, under the launcher's `settle`, nw6b H4, and STALE_CALL): the session's
    open helper calls by agent id, labelled from the ledger; [] with none, a helper stamp
    alone included (nw6b H5: it lapses inside the turn's own `settle`), or on a fault. A
    call with no `at` counts as just seen."""
    from . import admission
    try:
        settle = _mark_guards(state, sid, env, cwd)["settle"]
        ids, _, _ = helper_hold(resolver.session_dir(state, sid), time.time(),
                                time.monotonic(), {}, settle, STALE_CALL)
        return labelled(admission.directory(env), ids) if ids else []
    except Exception:                                   # noqa: BLE001 - the mark is written
        return []


def mark_until(state, sid: str, env, cwd=None):
    """nw6b H3: at the respawn mark, when the ceiling ends the hold: the sitting's first
    confirmed mark (this one where none was confirmed before) plus `hold_max`, the
    launcher's (H4), else as run_guards resolves it; None with no ceiling, no moment, or on
    a fault."""
    try:
        hm = _mark_guards(state, sid, env, cwd)[HOLD_MAX]
        first = first_mark(resolver.session_dir(state, sid))
        return first + hm if _num(hm) and hm > 0 and first is not None else None
    except Exception:                                   # noqa: BLE001 - the mark is written
        return None


def _json(path: Path):
    """The file's JSON object; None when it is absent; {} when it is not an object."""
    try:
        d = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError):    # too deep to parse (round 1's F3)
        return {}
    return d if isinstance(d, dict) else {}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _opened(at, now: float) -> bool:
    """u1's fold: a call file's `at` is when it opened only as a finite time from
    AT_FLOOR to now; NaN, an infinity, a future stamp or another unit is not. Compared,
    never subtracted: a JSON integer too large for a float compares exactly."""
    return _num(at) and AT_FLOOR <= at <= now


def _status(rc: int) -> int:
    """A child's status as a shell reports it: a signal N is 128+N (ruling 8)."""
    return 128 - rc if rc < 0 else rc


class Effects:
    """Everything the launcher does to the world, behind one seam (packet S20 ruling 1):
    the clock, the child, the signals it sends, the terminal, its lines and the ledger."""

    def now(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        """A clock that does not go back: a call file's first sight (u1's fold)."""
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def uuid(self) -> str:
        return str(uuid.uuid4())

    def environ(self) -> dict:
        return dict(os.environ)

    def spawn(self, argv, env):
        # §3.7: the launcher's own process group and fds 0 to 2; no setsid, no pty.
        return subprocess.Popen(list(argv), env=env)

    def wait(self, proc, timeout: float) -> int | None:
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def send(self, proc, sig: int) -> None:
        try:
            os.kill(proc.pid, sig)
        except ProcessLookupError:
            pass

    def gate_start(self, state: Path) -> None:
        """nw2 R4: the gate's runner, as `gate status` starts it, where the queue holds an
        entry, so a job whose runner died is run or closed with 125 between two sittings."""
        if gate.entries(state):
            gate.spawn_serve(state)

    def say(self, line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    def tty_save(self):
        try:
            return termios.tcgetattr(0) if termios else None
        except (OSError, termios.error):
            return None

    def tty_restore(self, attrs) -> None:
        if attrs is None:
            return
        try:
            termios.tcsetattr(0, termios.TCSADRAIN, attrs)
        except (OSError, termios.error):
            pass

    def append(self, state: Path, entry: dict) -> Path:
        return ledger.append_chain(state, entry)

    halt = None     # R2's review fold, F1: the chain's stop check, read while the pass runs

    def reconcile(self, cwd, timeout: float) -> tuple:
        """(the pass's exit, its last line): stdin /dev/null, output captured, cut at
        `timeout`; the exit is None when the pass was cut, stopped or did not start. Every
        RECONCILE_POLL seconds `halt` is read: a stop kills the pass (R2's review fold, F1).
        The line is decoded with replacement and holds no control character (F7)."""
        halt = self.halt or (lambda: None)
        try:
            proc = subprocess.Popen(reconcile_argv(), cwd=str(cwd), stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as e:
            return None, f"did not start ({e})"
        end = time.monotonic() + timeout
        with proc:
            while True:
                left = end - time.monotonic()
                try:
                    out, err = proc.communicate(timeout=max(0.0, min(RECONCILE_POLL, left)))
                    break
                except subprocess.TimeoutExpired:
                    pass
                why = "stopped" if halt() else (f"cut after {timeout:g} s"
                                                if time.monotonic() >= end else None)
                if why is not None:
                    proc.kill()
                    proc.wait()
                    return None, why
        lines = [l for l in map(_clean, out.decode("utf-8", "replace").splitlines()) if l] or \
                [l for l in map(_clean, err.decode("utf-8", "replace").splitlines()) if l]
        return proc.returncode, lines[-1][:300] if lines else ""

    def restarts(self, state: Path, chain: str, now: float) -> int:
        return ledger.restarts_in(state, chain, now)


class Chain:
    """One chain: start, watch, end on a confirmed RESPAWN, restart (respawn-r1 §3.3 to
    §3.7). `guards` is a mapping, or a callable that resolves one, called at the start and
    again before each restart; `poll`, `grace` and `kill_grace` are seconds."""

    def __init__(self, name, args, state, effects, guards, *, poll=2, grace=10,
                 kill_grace=30, argv=None, warnings=(), stale_call=STALE_CALL):
        self.name, self.args, self.state, self.fx = name, list(args), Path(state), effects
        self.warnings = list(warnings)  # said once, after the lock and the guards hold
        self._guards = guards
        self.poll, self.grace, self.kill_grace = poll, grace, kill_grace
        self.stale_call = stale_call    # u1 R1: seconds before an open helper call is stale
        self._stale: list[dict] = []    # the stale calls the last ready read went past
        self._first: dict[str, float] = {}  # a call file's first sight, on fx.monotonic()
        self.went_past: list[dict] = []     # and those of the child the launcher ended
        self.argv = list(argv) if argv else ["agentik", "session", "run", "--chain", name,
                                             "--", *self.args]
        self.home = self.state / "respawn" / name
        self.got: list[int] = []        # the signals the launcher took, in order
        self.restarts = 0               # the restarts this launcher made
        self.tally: list[float] = []    # and when (§3.5: a deleted ledger never resets it)
        self.g = dict(DEFAULTS)
        self.started = 0.0
        self.config_error: str | None = None   # a resolve that failed while a child ran
        self._said: str | None = None   # the reason held.json names; "" before a watch (S37)
        self._by: list = []             # nw6 R3: the labels held.json names for the helpers
        self._since = None              # and since when they hold
        self._until_said = None         # nw6b H3: and the `until` it said
        self._sid = self._guards_said = None    # nw6b H4: the sitting, and guards.json's doc
        self._ids = None                # the ids those labels were last read for (Z4)
        self._want = None               # and the ids of this poll's read
        self._pid_started = None        # this launcher's start time, beside its pid (Z3)

    # ---- the run -----------------------------------------------------------------------

    def _hand_state(self, prev, sid) -> None:
        """S39 Amendment 1, before each start: the state the session that just ended
        copied here is stamped for `sid`; any other (an earlier chain's or sitting's) is
        deleted."""
        try:
            statefile.hand(self.home, prev, sid)
        except OSError as e:
            self.fx.say(f"{self.name}: the successor's state was not handed on ({e})")

    def _hand_fill(self, prev, sid) -> None:
        """Packet FW1b R5, before each start: the fill word the session that just ended
        held, its time still ahead, goes into `sid`'s overlay and is said; any other copy
        in the chain home (an earlier chain's, a passed one) is removed."""
        from datetime import datetime, timezone
        from . import fill
        try:
            now = datetime.fromtimestamp(self.fx.now(), timezone.utc)
            v = fill.hand(self.home, self.state, prev, sid, now)
        except OSError as e:
            self.fx.say(f"{self.name}: the fill word was not handed on ({e})")
            return
        if v:
            self.fx.say(f"{self.name}: fill {v['word']} to {fill.wall(fill.when(v['until']))} "
                        "goes to the successor")

    def _hand_cap(self, prev, sid) -> None:
        """Packet mt1 R4, as `_hand_fill`: the cap the ending session held, its time still
        ahead, goes into `sid`'s overlay and is said; any other copy is removed."""
        from datetime import datetime, timezone
        from . import tiers
        try:
            now = datetime.fromtimestamp(self.fx.now(), timezone.utc)
            v = tiers.hand(self.home, self.state, prev, sid, now)
        except OSError as e:
            self.fx.say(f"{self.name}: the cap was not handed on ({e})")
            return
        if v:
            self.fx.say(f"{self.name}: cap {v['model']} to {tiers.wall(tiers.when(v['until']))} "
                        "goes to the successor")

    def run(self) -> int:
        try:
            self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.home / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as e:
            self.fx.say(f"error: agentik-session run: the chain's lock cannot be opened: {e}")
            return 2
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.fx.say(f"error: agentik-session run: the chain {self.name} already runs "
                            f"(its lock {self.home / 'lock'} is held)")
                return 2
            try:
                self.g = self.guards()
            except resolver.ResolveError as e:
                self.fx.say(f"error: agentik-session run: {e}")
                return 2
            for line in self.warnings:          # a refusal above stays one line (§3.1)
                self.fx.say(line)
            old = self._trap()
            try:
                return self._chain()
            finally:
                self._untrap(old)
        finally:
            os.close(fd)

    def guards(self) -> dict:
        g = self._guards() if callable(self._guards) else self._guards
        return {**DEFAULTS, **(g or {})}

    def _chain(self) -> int:
        env = self.fx.environ()
        self.env = env
        program = shutil.which("claude", path=env.get("PATH")) or "claude"
        child_env = launch.scrub(env)
        for k in (launch.DEPTH_VAR, "RELAY_ROW"):          # §3.8: never a relay sitting
            child_env.pop(k, None)
        child_env[hooks.CHAIN_VAR] = self.name
        self.started = self.fx.now()
        attrs = self.fx.tty_save()
        sid, n, args = self.fx.uuid(), 0, list(self.args)
        prev = None                              # the session that just ended, if any
        while True:
            n += 1
            start = self.fx.now()
            self._hand_state(prev, sid)
            self._hand_fill(prev, sid)
            self._hand_cap(prev, sid)
            self._sitting(sid)
            try:
                proc = self.fx.spawn([program, "--session-id", sid, *args], child_env)
            except OSError as e:                 # A-F6: a stop line, never a traceback
                self.fx.tty_restore(attrs)
                self.fx.say(f"{self.name}: claude did not start ({e})")
                self._stop(sid, "spawn", 1, 0)
                return 1
            rc, ended_by, held = self._watch(proc, sid, start)
            cut = len(self.got)                  # the signals taken while the child ran
            self.fx.tty_restore(attrs)                     # §3.7: before anything prints
            for what, past in (("a stale helper call", [s for s in self.went_past
                                                        if not s.get("ceiling")]),
                               ("a helper call at the ceiling",      # nw6b Y3
                                [s for s in self.went_past if s.get("ceiling")])):
                if past:                         # u1 R1's word, before the grace line
                    self.fx.say(f"{self.name}: went on past {what}: " + "; ".join(
                        f"{s['id']} open {'?' if s['age'] is None else s['age'] // 60} min"
                        for s in past))
            seconds = round(self.fx.now() - start)
            reason, code, marker, count = self._decide(sid, start, rc, ended_by, held)
            if reason is None:
                reason = self._grace(n, marker["charter"], count + 1, cut)
            if reason is None:
                nxt = self.fx.uuid()
                succ, carried, start_model = self._carry(sid)
                entry = {"kind": "restart", "chain": self.name, "seq": self.restarts + 1,
                         "from_session": sid, "to_session": nxt,
                         "profile": env.get("CLAUDE_SESSION_PROFILE") or None,
                         "repo": Path.cwd().name, "charter": marker.get("charter"),
                         "charter_sha256": marker.get("charter_sha256"),
                         "sitting_seconds": seconds, "ended_by": ended_by or "exit",
                         "restarts_24h": count + 1, "cap": self.g["cap"],
                         "model": carried, "start_model": start_model,      # S34 ruling 4
                         "stale_calls": list(self.went_past) or None}       # u1 R1
                try:
                    self.fx.append(self.state, entry)       # §3.5: before the successor
                except (OSError, ledger.LedgerError) as e:
                    self.fx.say(f"{self.name}: the restart line was not written ({e}); "
                                "no successor starts")
                    reason = "cap"
                else:
                    self.restarts += 1
                    self.tally.append(self.fx.now())
                    if carried is not None:                   # S34 ruling 4
                        self.fx.say(f"{self.name}: the successor runs on --model {carried}, "
                                    "the model the sitting ended on; the start line says "
                                    f"--model {start_model}")
                    self._reconcile()             # R2: after the restart line, before the successor
                    reason = self._halted()       # R2's review fold, F1: a stop in the pass
                    if reason is None:
                        prev, sid, args = sid, nxt, succ
                        continue
            self._stop(sid, reason, code, seconds)
            return code

    def _reconcile(self) -> None:
        """Packet R2, the close: the reconciler's pass when the repo sets `session.reconcile`
        (the verb's `every` decides whether it runs the detectors). One line said, cut at
        RECONCILE_WAIT; nothing here stops or holds the successor past that bound."""
        try:
            from .reconcile import runner
            cwd = Path.cwd()
            if not runner.wanted(cwd, getattr(self, "env", None) or {}):
                return
            self.fx.halt = self._halted          # F1: read by the pass while it runs
            try:
                rc, line = self.fx.reconcile(cwd, RECONCILE_WAIT)
            finally:
                self.fx.halt = None
        except Exception as e:                   # noqa: BLE001  (a pass never stops a chain)
            rc, line = None, f"did not run ({e})"
        what = "reconcile" if rc is None else f"reconcile exit {rc}"
        self.fx.say(f"{self.name}: {what}: {line}" if line else f"{self.name}: {what}")

    def _carry(self, sid: str) -> tuple[list, str | None, str | None]:
        """`carry` for the ending sitting, always against the start line (S34 ruling 3):
        its `meter.json`'s model, under the table resolved now; a resolve failure or an
        unreadable meter carries nothing."""
        doc = _json(resolver.session_dir(self.state, sid) / meter.METER) or {}
        try:
            table = model_table(Path.cwd(), getattr(self, "env", {}))
        except (resolver.ResolveError, OSError):
            table = None
        return carry(self.args, doc.get("model"), table)

    # ---- the watch (§3.3) -------------------------------------------------------------

    def _watch(self, proc, sid, start):
        """Wait for the child; end it only when a confirmed marker passes the checks and
        the turn has ended and stood. A hold is re-checked every poll and said in the
        chain home's held.json, which goes when the child ends (S37). Returns (status,
        ended_by, held reason)."""
        sdir = resolver.session_dir(self.state, sid)
        held = ended_by = term_at = seen = None
        forwarded = False
        self.went_past = []                  # u1 R1: the stale calls this child's end passed
        self._first = {}                     # and the first sights of its odd call files
        self._said = ""                      # a file a past watch left goes at the first say
        try:
            while True:
                rc = self.fx.wait(proc, self.poll)
                if rc is not None:
                    return rc, ended_by, held
                if signal.SIGTERM in self.got and not forwarded:
                    self.fx.send(proc, signal.SIGTERM)      # §3.7: forwarded, the chain stops
                    forwarded = True
                now = self.fx.now()
                if term_at is not None:          # §3.3 step 5 holds through a hang-up (A-F4)
                    if ended_by == "launcher" and now - term_at >= self.kill_grace:
                        self.fx.send(proc, signal.SIGKILL)
                        ended_by = "kill"
                    continue
                if self._stopping():
                    continue
                conf = _json(sdir / hooks.CONFIRMED)
                if conf is None:
                    if held is None:             # rc2 R1: said, never signalled
                        self._say_held("not-main" if self._unconfirmed(sdir, sid, now)
                                       else None, sid, now)
                    continue
                held, seen, end = self._step(sdir, sid, start, now, conf, seen, held)
                if held is None and not end:     # nw6 Z1: who holds, read at every poll
                    by = self._holders(sdir, now)
                    if by is not None:
                        self._say_held(HELPERS if by else None, sid, now, by)
                else:
                    self._say_held(held, sid, now)
                if end:
                    self.fx.send(proc, signal.SIGTERM)
                    term_at, ended_by = now, "launcher"
        finally:
            self._say_held(None, sid, None)          # the child ended: the file goes

    def _unconfirmed(self, sdir: Path, sid: str, now: float) -> bool:
        """rc2 R1: no confirm, and the marker parses, names this sitting and was `written`
        at least `settle` ago: the hold `not-main` is said in held.json. The watch's own
        `held` stays None, so `_step` and `_decide` read the confirm as at the pin. A
        marker that does not parse, names another session or is younger says nothing."""
        marker = _json(sdir / hooks.MARKER) or {}
        written = marker.get("written")
        return (marker.get("session") == sid and _num(written)
                and written <= now - self.g["settle"])

    def _step(self, sdir, sid, start, now, conf, seen, held):
        """One poll past a confirmed marker: (held, seen, end the child). A new marker or
        a hold runs the checks again, `None` clearing the hold (S37 ruling 1); a held
        `not-respawn` waits for a new confirmed marker, and a hold re-resolves the guards
        first (Amendment 1, F1 and F4). Then the ready condition, the guards re-resolved
        and the checks right before the signal."""
        fresh, seen = conf != seen, conf
        if held == "not-respawn" and not fresh:
            return held, seen, False             # F1: only the main thread's confirm lifts it
        if held is not None and not self._resolve():
            return "config", seen, False         # F4: a config edit counts on a hold
        if fresh or held is not None:
            held = self._checks(sdir, sid, start, now)
            if held:
                return held, seen, False
        if not self._ready(sdir, now):
            return None, seen, False
        if not self._resolve():                  # §4: a config edit counts before the signal
            return "config", seen, False
        held = self._checks(sdir, sid, start, now)           # N4: again, right before
        if held is None:
            self.went_past = list(self._stale)       # u1 R1: said once the terminal is back
        return held, seen, held is None

    def _say_guards(self) -> None:
        """nw6b H4: guards.json beside sitting.json, `{session, settle, hold_max}`, the
        values this launcher resolved, for the mark to read; written at each sitting's start
        and when a resolve changes them. A failed write is tried at the next change."""
        sid = self._sid
        doc = {"session": sid, "settle": self.g.get("settle"), HOLD_MAX: self.g.get(HOLD_MAX, 0)}
        if sid is None or doc == self._guards_said:
            return
        try:
            gate._write_private(self.home / LAUNCHER_GUARDS, json.dumps(doc) + "\n")
        except OSError:
            return
        self._guards_said = doc

    def _resolve(self) -> bool:
        """The guards resolved again (§4); False on a ResolveError. Its text is kept when
        it first appears and cleared once the config resolves again (Amendment 1, F4);
        §3.7: nothing printed while a child runs, the error prints at the stop (N1)."""
        try:
            self.g = self.guards()
        except resolver.ResolveError as e:
            if self.config_error is None:
                self.config_error = str(e)
            return False
        self.config_error = None
        self._say_guards()
        return True

    def _holders(self, sdir, now) -> list | None:
        """nw6 Z1: what holds the respawn on this poll, by label, read as `_ready`'s helper
        clause reads it (helper_hold, on a copy of the first sights, so the ready condition
        ages no call earlier than at the pin): the open calls' helpers, else [room.ANY] for
        the helpers' stamp alone, else []; None on a fault, which leaves the record as it
        is. Z4: the labels are read again whenever the ids change or one is a miss, so each
        write names what the ledger says at that write."""
        from . import admission, room
        try:
            ids, stamp, _ = helper_hold(sdir, now, self.fx.monotonic(), dict(self._first),
                                        self.g["settle"], self.stale_call)
            aid = _stamp_helper(sdir) if stamp and not ids else None
            if aid is not None:
                ids = [aid]                  # nw6b H5: the stamp names its helper, Y1: a live one
            if not ids:
                self._want = None
                return [room.ANY] if stamp else []
            self._want = (sorted({i for i in ids if isinstance(i, str)}), None in ids)
            if self._said != HELPERS or self._want != self._ids or room.ANY in self._by:
                return labelled(self.state / admission.DIR, ids)
            return self._by
        except Exception:                                   # noqa: BLE001 - said next poll
            return None

    def _say_held(self, reason, sid, now, by=None):
        """S37 ruling 2: a hold is said through the state, never the terminal (§3.7). The
        chain home's held.json, `{reason, since, session}`, is written when a hold begins
        or its reason changes and removed when it clears or the child ends. A write that
        fails is tried again at the next poll; the hold holds either way. nw6 R3: the
        helpers' hold adds `by`, the launcher's `pid` and its start time `started` (Z3),
        rewritten when `by` changes with its first `since` kept; a write or a removal that
        fails changes nothing but the file. nw6b H3: under a ceiling it adds `until`, the
        first mark plus `hold_max`, wall-clock."""
        until = (self._until(resolver.session_dir(self.state, sid))
                 if reason == HELPERS else None)        # nw6b H3: the ceiling's moment
        if reason == self._said and (reason != HELPERS or (by == self._by
                                                           and until == self._until_said)):
            return
        if reason == HELPERS and self._said == HELPERS:
            now = self._since
        path = self.home / HELD
        try:
            if reason is None:
                path.unlink(missing_ok=True)
            else:
                tmp = path.with_name(f".{HELD}.{os.getpid()}")
                try:
                    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    doc = {"reason": reason, "since": now, "session": sid}
                    if reason == HELPERS:
                        if self._pid_started is None:
                            self._pid_started = proc_started(os.getpid()) or 0
                        doc.update(by=by, pid=os.getpid(), started=self._pid_started or None)
                        if until is not None:
                            doc["until"] = until
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(doc, f)
                    os.replace(tmp, path)
                finally:
                    tmp.unlink(missing_ok=True)     # a failed replace leaves nothing behind
        except OSError:
            return
        self._said = reason
        if reason == HELPERS:
            self._by, self._since, self._ids = by, now, self._want
            self._until_said = until

    def _sitting(self, sid: str) -> None:
        """nw2 R2, R4: `sitting.json` names the sitting about to start, then the runner's
        start; a fault in either is no stop (the chain's lines then wait in its inbox)."""
        try:
            gate.write_sitting(self.state, self.name, sid, self.fx.now())
        except OSError as e:
            self.fx.say(f"{self.name}: sitting.json was not written ({e})")
        self._sid, self._guards_said = sid, None
        self._say_guards()
        start = getattr(self.fx, "gate_start", None)
        try:
            if start is not None:
                start(self.state)
        except Exception as e:                           # noqa: BLE001 - never a stop
            self.fx.say(f"{self.name}: the gate's runner did not start ({e})")

    def _ready(self, sdir: Path, now: float, mono: float | None = None) -> bool:
        """§3.3 step 3 and ruling 2: the turn ended after the marker, nothing ran since,
        the end has stood `settle`, the helpers are quiet `settle` and none has a call open,
        but a stale one (u1 R1): open `stale_call` seconds with no helper stamp since; the
        helpers no longer hold past the first mark plus `hold_max` (nw6b H2). A True
        keeps the stale calls in `_stale`, `[{"id", "age"}]`, the age in whole seconds.
        A call whose `at` is no time (`_opened`) is aged from the launcher's first sight of
        its name on `mono`, `fx.monotonic()` by default, and its age is None (u1's fold)."""
        mono = self.fx.monotonic() if mono is None else mono
        settle = self.g["settle"]
        marker, te = _json(sdir / hooks.MARKER) or {}, _json(sdir / hooks.TURN_ENDED) or {}
        written, ended = marker.get("written"), te.get("at")
        # Compared, never subtracted, as `_opened` (NICE n56): a JSON integer past a float's
        # range, in a file the hooks did not write, reads as not ready and never raises; an
        # `ended` below AT_FLOOR (negative, -inf, huge negative) is no time (round 1's F2).
        if (not (_num(written) and _num(ended)) or not AT_FLOOR <= ended
                or ended <= written or not ended <= now - settle):
            return False
        act = _json(sdir / hooks.ACTIVITY)
        if act is not None and not (_num(act.get("at")) and act["at"] <= ended):
            return False
        cut: list = []
        held, stamp, stale = helper_hold(sdir, now, mono, self._first, settle, self.stale_call,
                                         cut)
        if held or stamp:                    # a call open, or the stamp under `settle`
            if not self._past_ceiling(sdir, now):
                return False
            stale = stale + [{**c, "ceiling": True} for c in cut]   # nw6b Y3: what it cut
        self._stale = stale
        return True

    def _until(self, sdir: Path):
        """nw6b H2: the first confirmed mark plus `hold_max`, a wall-clock time; None with
        no ceiling (0, or a guards mapping that names none) or no moment."""
        hm = self.g.get(HOLD_MAX, 0)
        if not (_num(hm) and hm > 0):
            return None
        first = first_mark(sdir)
        return None if first is None else first + hm

    def _past_ceiling(self, sdir: Path, now: float) -> bool:
        """nw6b H2: past the ceiling the helper clause of `_ready` no longer holds."""
        until = self._until(sdir)
        return until is not None and now >= until

    # ---- the checks (§3.4, §3.5) --------------------------------------------------------

    def _checks(self, sdir: Path, sid: str, start: float, now: float,
                which: str = "abcde") -> str | None:
        """The first of checks (a) to (e) that holds the sitting, by its reason."""
        try:
            raw = (sdir / hooks.MARKER).read_bytes()
            marker = json.loads(raw)
        except (OSError, ValueError):
            raw, marker = b"", None
        if "a" in which:
            conf = _json(sdir / hooks.CONFIRMED) or {}
            if (not isinstance(marker, dict) or marker.get("session") != sid
                    or conf.get("marker_sha256") != hashlib.sha256(raw).hexdigest()):
                return "not-main"
        if "b" in which:
            path = marker.get("charter") if isinstance(marker, dict) else None
            try:
                st = os.stat(path)
                line = charter.next_act_line(Path(path).read_bytes().decode("utf-8", "replace"))
            except (OSError, TypeError, ValueError):
                return "not-respawn"
            if line is None or not charter.RESPAWN.match(line) or st.st_mtime < start:
                return "not-respawn"
        if "c" in which and self._stop_file():
            return "stop-file"
        if "d" in which:
            count = self._count(now)
            if count is None or count >= self.g["cap"]:
                return "cap"
        if "e" in which and now - start < self.g["floor"]:
            return "floor"
        return None

    def _stop_file(self) -> bool:
        """A stop file counts when its mtime is at or after the chain's start (§3.5)."""
        for p in (self.state / "respawn" / "STOP", self.home / "STOP"):
            try:
                if os.stat(p).st_mtime >= self.started:
                    return True
            except OSError:
                pass
        return False

    def _count(self, now: float) -> int | None:
        """The restarts in the past 24 h: the larger of the ledger's count and the
        launcher's own tally (ruling 7); None when the ledger cannot be read."""
        try:
            n = self.fx.restarts(self.state, self.name, now)
        except ledger.LedgerError:
            return None
        return max(n, sum(1 for t in self.tally if t > now - 86400))

    def _decide(self, sid, start, rc, ended_by, held):
        """(reason, exit code, marker, count) at the child's exit; reason None restarts."""
        sdir = resolver.session_dir(self.state, sid)
        code = 0 if ended_by else _status(rc)
        if self._stopping():
            return ("hangup" if signal.SIGHUP in self.got else "terminated"), code, None, 0
        marker = _json(sdir / hooks.MARKER)
        if marker is None:
            return "no-marker", code, None, 0
        if not ended_by and rc != 0:
            return "crash", code, None, 0
        if held:
            if held == "config" and self.config_error:
                self.fx.say(f"{self.name}: {self.config_error}")
            return held, code, None, 0
        if not ended_by:                     # the launcher's own end resolved before it
            try:
                self.g = self.guards()                       # §4: again before each restart
            except resolver.ResolveError as e:
                self.fx.say(f"{self.name}: {e}")
                return "config", code, None, 0
        now = self.fx.now()
        # §3.4: after its own signal only (b) and (c); the cap held right before it.
        reason = self._checks(sdir, sid, start, now, "bc" if ended_by else "abcde")
        count = self._count(now)
        if count is None:
            count = sum(1 for t in self.tally if t > now - 86400)
        return reason, code, marker, count

    # ---- the grace, the stop, the signals (§3.4, §3.7) ---------------------------------

    def _grace(self, n: int, charter_path, k: int, cut: int) -> str | None:
        # A Ctrl-C the child took is dropped; one after the child's exit ends the chain.
        self.got = ([s for s in self.got[:cut] if s not in (signal.SIGINT, signal.SIGQUIT)]
                    + self.got[cut:])
        self.fx.say(f"{self.name}: sitting {n} ended on RESPAWN ({charter_path}); restart {k} "
                    f"of {self.g['cap']} in 24 h in {self.grace:g} s; touch "
                    f"{self.home / 'STOP'} or press Ctrl-C to end the chain")
        end = self.fx.now() + self.grace
        while True:
            took = self._signalled()
            if took is not None:
                return took
            left = end - self.fx.now()
            if left <= 0:
                break
            self.fx.sleep(min(self.poll, left))
        return "stop-file" if self._stop_file() else None

    def _signalled(self) -> str | None:
        """The grace's stop by a signal: `interrupted`, `hangup` or `terminated`, or None."""
        if signal.SIGINT in self.got or signal.SIGQUIT in self.got:
            return "interrupted"
        if self._stopping():
            return "hangup" if signal.SIGHUP in self.got else "terminated"
        return None

    def _halted(self) -> str | None:
        """The grace's own checks and reasons, read again during and right after the close's
        pass (R2's review fold, F1): a signal, else the stop file, else None."""
        return self._signalled() or ("stop-file" if self._stop_file() else None)

    def _stop(self, sid: str, reason: str, code: int, seconds: int) -> None:
        env = getattr(self, "env", {})
        entry = {"kind": "stop", "chain": self.name, "session": sid,
                 "profile": env.get("CLAUDE_SESSION_PROFILE") or None,
                 "repo": Path.cwd().name, "reason": reason, "exit_status": code,
                 "sitting_seconds": seconds, "restarts": self.restarts}
        quiet = reason == "hangup"                           # §3.7: nothing more to the tty
        try:
            self.fx.append(self.state, entry)
        except (OSError, ledger.LedgerError) as e:
            if not quiet:
                self.fx.say(f"{self.name}: the stop line was not written ({e})")
        if not quiet:
            try:
                left = gate.chain_count(self.state, self.name)
            except Exception:                            # noqa: BLE001
                left = 0
            if left:                                     # nw2 R4: no sitting takes them now
                self.fx.say(f"{self.name}: the chain's inbox still holds {left} gate "
                            f"{'line' if left == 1 else 'lines'}: "
                            f"{gate.chain_inbox(self.state, self.name)}")
            self.fx.say(f"{self.name}: the chain stopped ({reason}) after {self.restarts} "
                        "restart(s); to start it again:")
            self.fx.say(start_line(self.argv, env))

    def _stopping(self) -> bool:
        return signal.SIGHUP in self.got or signal.SIGTERM in self.got

    def _trap(self) -> dict:
        """§3.7: SIGINT and SIGQUIT only recorded (never SIG_IGN, which exec would pass
        on); SIGHUP and SIGTERM recorded and acted on."""
        def record(signum, frame):
            self.got.append(signum)
        old = {}
        for s in (signal.SIGINT, signal.SIGQUIT, signal.SIGHUP, signal.SIGTERM):
            try:
                old[s] = signal.signal(s, record)
            except (OSError, ValueError):                   # not the main thread
                pass
        return old

    def _untrap(self, old: dict) -> None:
        for s, h in old.items():
            try:
                signal.signal(s, h)
            except (OSError, ValueError, TypeError):
                pass
