"""The gate queue (design/gate-r1.md, packets S38 and S47): one queue per state root, run
by one detached runner, one running per key under a load ceiling.

`enqueue` writes `<state>/gate/queue/<id>.json`, its `key` the device and inode of the repo's
git common dir, so a repo and its worktrees are one key however they are spelled; `serve` is
the runner, which holds a set of children and polls them. It starts the oldest entry whose key is free and none of whose lock paths
exists or is named by a running entry; a second start waits for the ceiling (`_over`). Each
child runs in its own process group in its repo; at its end the runner writes
`<state>/gate/<id>/log` and then `result.json`, drops the entry from the queue, and tells
the caller's inbox (and ntfy when configured). `wait`, `status` and the inbox are reads. The
tool reports exit codes and judges none: 124 is the wall's cut, 125 a runner that died, 126
a lock held past the wall, 127 a command that could not start. Every effect the runner has
(the clock, spawn, flock, the group kill, the POST, the load, the cores) is in Fx, so a test
fakes each one.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ID = re.compile(r"^\d{8}-\d{6}-[1-9]\d{0,11}\Z")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")     # hooks._SID's pattern (a test pins it)
WALL = 5400
IDLE = 60.0
POLL = 1.0
GRACE = 5.0
WAIT_POLL = 5
KEEP = 14 * 86400
TAKE = 3
DONE_SHOWN = 5
CUT_WALL, CUT_DIED, CUT_LOCK = "wall cut", "runner died", "lock wait cut"
MORE = "{n} more: agentik session gate status"
ENTRY_KEYS = ("id", "repo", "command", "env", "locks", "wall", "label", "caller", "queued",
              "key", "key_name")
RESULT_KEYS = ("id", "repo", "command", "exit", "started", "ended", "seconds", "log",
               "caller", "cut")
INBOX_KEYS = ("at", "kind", "id", "repo", "exit", "seconds", "log")
RUNNER_KEYS = ("pid", "since", "running")
GATE_DEFAULTS = {"ntfy_url": None, "ntfy_topic": None, "wall": WALL}
MAX_RUNNING = 3             # gate.max_running's default (packet S47, ruling 4)
LOAD_SHARE = 0.75           # gate.load_ceiling's default, as a share of the cores
START_SETTLE = 60.0         # the seconds between two starts, since a load average lags
GIT_WAIT = 10.0
DOT_GIT_MOST = 4096         # a `.git` file or a `commondir` is one short line


class GateError(Exception):
    """A refusal before anything is queued: the CLI says it and exits 2."""


# ---- paths and files ---------------------------------------------------------

def gate_dir(root) -> Path:
    return Path(root) / "gate"


def _queue(root) -> Path:
    return gate_dir(root) / "queue"


def entry_dir(root, gid: str) -> Path:
    return gate_dir(root) / gid


def result_path(root, gid: str) -> Path:
    return entry_dir(root, gid) / "result.json"


def _inbox(root, sid: str) -> Path:
    return Path(root) / "sessions" / sid / "inbox"


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _write_private(path: Path, text: str) -> None:
    """Mode 0600, written to a dot file beside it, then renamed over it."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _load(path: Path) -> dict | None:
    try:
        d = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _unlink(path: Path) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _counter(gid: str) -> int:
    return int(gid.rsplit("-", 1)[1])


def _hm(ts) -> str:
    return time.strftime("%H:%M", time.localtime(ts)) if isinstance(ts, (int, float)) else "?"


def _minutes(seconds) -> str:
    return str(round(seconds / 60)) if isinstance(seconds, (int, float)) else "?"


def _alive(pid) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                            # a runner that is our own child is a zombie once dead
        reaped, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:       # not our child: kill(0) said enough
        return True
    except OSError:
        return True
    return reaped == 0


def _config(env, log=None) -> dict:
    """The gate section's user layer (packet ruling 4): ntfy_url, ntfy_topic, wall, and
    S47's load_ceiling and max_running when set."""
    from . import resolver
    return resolver.gate_config(env, log)


# ---- the key -----------------------------------------------------------------

_PC_CASE_SENSITIVE = 11


def _real(path: str) -> str:
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def _stat_key(path: str) -> str:
    """`<st_dev>:<st_ino>`, since on a case-insensitive disk realpath keeps the typed case;
    a path that cannot be statted keeps its realpath."""
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return _real(path)
    return f"{st.st_dev}:{st.st_ino}"


def _short_read(path: str) -> str | None:
    """A regular file's head, or None: a FIFO at `.git` must not hold the runner."""
    try:
        if not os.path.isfile(path):
            return None
        with open(path, errors="replace") as fh:
            return fh.read(DOT_GIT_MOST)
    except (OSError, ValueError):
        return None


def _common_dir(repo: str) -> str | None:
    """With no git to ask: `<repo>/.git`, or, where that is a file, the common dir its
    `gitdir:` leads to, by the same two reads git makes (`commondir`, relative to the
    gitdir, is absent in a submodule's, which is its own common dir). None for no `.git`,
    or one that leads nowhere."""
    dot = os.path.join(repo, ".git")
    if os.path.isdir(dot):
        return dot
    text = _short_read(dot)
    if text is None or not text.startswith("gitdir:"):
        return None
    gitdir = os.path.join(repo, text[len("gitdir:"):].strip())
    back = (_short_read(os.path.join(gitdir, "commondir")) or "").strip()
    common = os.path.join(gitdir, back) if back else gitdir
    return common if os.path.isdir(common) else None


def _fallback_key(repo: str) -> str:
    """The key with no answer from git, computed as a sibling's was: the common dir's when
    it can be found, else the repo's own."""
    return _stat_key(_common_dir(repo) or repo)


def repo_key(repo: str) -> str:
    """The identity of `git -C <repo> rev-parse --git-common-dir`, so a repo and its
    worktrees are one key; no git tree, or git failing, `_fallback_key`. `GIT_*` in the
    caller's environment would name another tree, so none reaches git. Never raises."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "rev-parse", "--git-common-dir"], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=GIT_WAIT)
        out = p.stdout.rstrip("\n") if p.returncode == 0 else ""
    except (OSError, ValueError, subprocess.SubprocessError):
        out = ""
    return _stat_key(os.path.join(repo, out)) if out else _fallback_key(repo)


def entry_key(e: dict) -> str:
    """The entry's key; an older queue's entry, with none, computes it from its repo."""
    k = e.get("key")
    if isinstance(k, str) and k:
        return k
    repo = e.get("repo")
    return _fallback_key(repo) if isinstance(repo, str) else ""


def key_name(e: dict) -> str:
    """The name of an entry's key in a `waits on key` line, since a device and an inode
    name no repo: its repo's basename, written beside the key, or read from an older
    entry's repo."""
    n = e.get("key_name")
    if isinstance(n, str) and n:
        return n
    repo = e.get("repo")
    return os.path.basename(repo) if isinstance(repo, str) else ""


def lock_path(path: str) -> str:
    """A lock as an entry stores it and `os.path.exists` tests it: its parent resolved, its
    own name as typed, so a lock that is a symlink is the path named, never its target."""
    parent, name = os.path.split(os.path.abspath(path))
    return os.path.join(_real(parent), name)


def _folds(at: str) -> bool:
    """Whether the volume of the existing directory `at` is case-insensitive. Darwin's
    `_PC_CASE_SENSITIVE`, a number no other OS means the same by: elsewhere, or on a failed
    read, False, so a name compares as typed."""
    if sys.platform != "darwin":
        return False
    try:
        return os.pathconf(at, _PC_CASE_SENSITIVE) == 0
    except (AttributeError, OSError, ValueError):
        return False


def lock_key(path: str) -> str:
    """One lock's identity, for comparing: its parent's realpath's nearest part that exists,
    as device and inode, then the rest of the path by name, in NFC and casefolded on a
    case-insensitive volume. So a lock reads the same however it is spelled and the same
    before and after it exists, as a parent is what is statted, never the lock. Comparing
    only: the stored path keeps its case. Never raises."""
    real = lock_path(path)
    at, rest = os.path.dirname(real), [os.path.basename(real)]
    while True:
        try:
            st = os.stat(at)
        except (OSError, ValueError):
            up = os.path.dirname(at)
            if up == at:
                return real
            at, rest = up, [os.path.basename(at), *rest]
            continue
        tail = "/".join(rest)
        if _folds(at):
            tail = unicodedata.normalize("NFC", tail).casefold()
        return f"{st.st_dev}:{st.st_ino}/{tail}"


# ---- the queue ---------------------------------------------------------------

def resolve_caller(args, env) -> str | None:
    """`--session SID` (checked before any path join), else `$CLAUDE_CODE_SESSION_ID`,
    else none. No cwd match."""
    sid = getattr(args, "session", None)
    if sid is not None:
        if not _SID.match(str(sid)):
            raise GateError(f"--session is not a session id: {str(sid)[:40]!r}")
        return sid
    sid = env.get("CLAUDE_CODE_SESSION_ID") or ""
    return sid if _SID.match(sid) else None


def enqueue(root, repo, command, env, locks, wall, label, caller, now) -> dict:
    """Write one entry (mode 0600, written then renamed) and return it. The id is
    `YYYYMMDD-HHMMSS-<counter>`, the counter taken under flock(gate/queue.lock)."""
    real = os.path.realpath(str(repo))
    if not os.path.isdir(real):
        raise GateError(f"no such repo directory: {repo}")
    if not command or not all(isinstance(c, str) and c for c in command):
        raise GateError("a command is wanted after --: gate run <repo> -- <command...>")
    if not isinstance(wall, int) or isinstance(wall, bool) or wall <= 0:
        raise GateError(f"the wall is a positive number of seconds, not {wall!r}")
    if caller is not None and not _SID.match(str(caller)):
        raise GateError(f"the caller is not a session id: {str(caller)[:40]!r}")
    g = gate_dir(root)
    _mkdir(_queue(root))
    key = repo_key(real)                # outside the queue's lock: git may take its time
    with open(g / "queue.lock", "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            n = int((g / "counter").read_text().strip()) + 1
        except (OSError, ValueError):
            n = 1 + max((_counter(e["id"]) for e in entries(root)), default=0)
        _write_private(g / "counter", f"{n}\n")
        gid = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{n}"
        entry = {"id": gid, "repo": real, "command": list(command), "env": dict(env),
                 "locks": [lock_path(p) for p in locks], "wall": wall,
                 "label": label or "", "caller": caller, "queued": now, "key": key,
                 "key_name": os.path.basename(real)}
        _write_private(_queue(root) / f"{gid}.json", json.dumps(entry, indent=1) + "\n")
    return entry


def entries(root) -> list[dict]:
    """The queue, oldest (lowest counter) first; a file that does not parse is skipped."""
    out = []
    try:
        names = os.listdir(_queue(root))
    except OSError:
        return []
    for name in names:
        stem = name[:-5] if name.endswith(".json") else ""
        if not ID.match(stem):
            continue
        e = _load(_queue(root) / name)
        if e is not None and e.get("id") == stem:
            out.append(e)
    return sorted(out, key=lambda e: _counter(e["id"]))


def runner_info(root) -> dict | None:
    return _load(gate_dir(root) / "runner.json")


def _pairs(r: dict | None) -> list[tuple]:
    """A runner.json's running, as (id, pgid): `running` is a list of {id, pgid}, or the
    old single form, an id with `pgid` beside it, which an alpha.31 runner left. What is no
    id is skipped."""
    run = (r or {}).get("running")
    if isinstance(run, str):
        run = [{"id": run, "pgid": r.get("pgid")}]
    if not isinstance(run, list):
        return []
    return [(x["id"], x.get("pgid")) for x in run
            if isinstance(x, dict) and isinstance(x.get("id"), str) and ID.match(x["id"])]


def _running_ids(root, alive=_alive) -> list[str]:
    r = runner_info(root)
    return [gid for gid, _ in _pairs(r)] if r and alive(r.get("pid")) else []


def position(root, gid: str, alive=_alive) -> int:
    """The place among the entries not running (1 is next); 0 when not queued."""
    run = _running_ids(root, alive)
    ids = [e["id"] for e in entries(root) if e["id"] not in run]
    return ids.index(gid) + 1 if gid in ids else 0


def _started_at(root, gid: str):
    """When an entry started: its directory's mtime, made at the start and touched again
    only by its result; a directory not there yet reads the runner's file."""
    for path in (entry_dir(root, gid), gate_dir(root) / "runner.json"):
        try:
            return path.stat().st_mtime
        except OSError:
            continue
    return None


def _locked(e: dict) -> str | None:
    for p in e.get("locks") or []:
        if isinstance(p, str) and os.path.exists(p):
            return p
    return None


def _locks(e: dict) -> list[str]:
    return [p for p in e.get("locks") or [] if isinstance(p, str)]


def _named(running: list[dict]) -> set[str]:
    """What running entries' locks read as: each `lock_key` and its raw string, so a parent
    made between this read and a later one cannot read the same spelling as free."""
    return {s for x in running for p in _locks(x) for s in (p, lock_key(p))}


def _is_named(path: str, named: set[str]) -> bool:
    return path in named or lock_key(path) in named


def _holds(es: list[dict], running: list[dict]):
    """Rulings 1 to 3 over the entries not running, oldest first: each with what holds it,
    (kind, what) or None. A lock path that exists holds its entry, and so does one a running
    entry names, whatever its key, since that command may not have made it yet. An entry
    holds its key against every younger entry of that key, so a key stays FIFO. A wait on a
    key names the repo of the entry that holds it. Locks compare by `lock_key`, read here
    and not trusted from the entry, so an older entry's spelling compares too."""
    keys = {}
    for x in running:
        keys.setdefault(entry_key(x), key_name(x))
    named = _named(running)
    for e in es:
        k = entry_key(e)
        path = _locked(e) or next((p for p in _locks(e) if _is_named(p, named)), None)
        if path:
            yield e, ("lock", path)
        elif k in keys:
            yield e, ("key", keys[k])
        else:
            yield e, None
        keys.setdefault(k, key_name(e))


def _load_read(fx) -> float | None:
    """The 1-minute load average, or None for a read that failed or is no number."""
    try:
        x = fx.load()
    except Exception:                                   # noqa: BLE001 (over the ceiling)
        return None
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return None
    return float(x) if 0 <= x < float("inf") else None


def _ceiling(cfg: dict, fx) -> float:
    set_ = cfg.get("load_ceiling")
    if set_ is not None:
        return set_
    try:
        cores = fx.cores()
    except Exception:                                   # noqa: BLE001 (one core's share)
        cores = None
    return LOAD_SHARE * (cores if isinstance(cores, int) and cores > 0 else 1)


def _over(cfg: dict, fx, count: int, last, now: float):
    """Ruling 4, with `count` > 0 running: what bars a further start, (kind, ...) or None.
    `last` is the last start. A load read that failed is over the ceiling."""
    most = cfg.get("max_running", MAX_RUNNING)
    if count >= most:
        return ("running", count, most)
    x, c = _load_read(fx), _ceiling(cfg, fx)
    if x is None or x >= c:
        return ("load", x, c)
    left = START_SETTLE - (now - last) if isinstance(last, (int, float)) else 0
    return ("settle", left) if left > 0 else None


def spawn_serve(root, popen=None) -> bool:
    """Start `serve` detached when the queue is not empty: this interpreter (never PATH),
    a new session, close_fds, stdio to gate/runner.log, `-I` and the runner beside this package
    so the runner is this code and its bytecode goes under the launcher's prefix (design/04 §3).
    True when it spawned."""
    if not entries(root):
        return False
    popen = popen or subprocess.Popen
    g = gate_dir(root)
    _mkdir(g)
    runner = Path(__file__).resolve().parent.parent / "agentik-session"
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.environ.get("HOME", ""), ".cache")
    prefix = sys.pycache_prefix or os.path.join(cache, "agentik", "pycache")
    argv = [sys.executable, "-I", "-X", "pycache_prefix=" + prefix, str(runner),
            "gate", "serve", "--root", str(root)]
    with open(g / "runner.log", "ab") as log:
        popen(argv, cwd=str(g), env=dict(os.environ), stdin=subprocess.DEVNULL, stdout=log,
              stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    return True


# ---- the runner --------------------------------------------------------------

def _default_post(url, data, headers, timeout):
    import urllib.request
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 (an https URL)
        r.read()


def _log_line(line: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + line, file=sys.stderr, flush=True)


def _load_avg() -> float:
    return os.getloadavg()[0]


@dataclass
class Fx:
    """The runner's effects, each faked in tests."""
    now: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    popen: Callable = subprocess.Popen
    flock: Callable = fcntl.flock
    killpg: Callable = os.killpg
    post: Callable = _default_post
    log: Callable[[str], None] = _log_line
    load: Callable[[], float] = _load_avg
    cores: Callable[[], int | None] = os.cpu_count
    env: dict = field(default_factory=lambda: dict(os.environ))
    idle: float = IDLE
    poll: float = POLL
    grace: float = GRACE
    pid: int = field(default_factory=os.getpid)


def _take(fh, fx: Fx) -> bool:
    try:
        fx.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


@dataclass
class _Child:
    """One running entry. `term_at` and `kill_at` are the wall cut's steps, so that a cut
    waits out its grace at the poll and never in the way of another child."""
    e: dict
    proc: object
    started: float
    term_at: float | None = None
    kill_at: float | None = None


@dataclass
class _Set:
    """The runner's memory: its children, the id it is about to spawn, its last start, and
    `seen`, when it first saw each head locked."""
    since: float
    running: list = field(default_factory=list)
    starting: str | None = None
    last_start: float | None = None
    seen: dict = field(default_factory=dict)


def _runner_write(root, fx: Fx, s: _Set) -> None:
    run = [{"id": c.e["id"], "pgid": c.proc.pid} for c in s.running]
    if s.starting is not None:
        run.append({"id": s.starting, "pgid": None})
    _write_private(gate_dir(root) / "runner.json",
                   json.dumps({"pid": fx.pid, "since": s.since, "running": run}) + "\n")


def _signal_group(pgid, sig, fx: Fx) -> bool:
    """False when there is no group to signal: gone, not ours, or never a group."""
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1 or pgid == os.getpgrp():
        return False
    try:
        fx.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _kill_group(pgid, fx: Fx) -> bool:
    """SIGTERM to the group, the grace, then SIGKILL; a group already gone ends it. False
    when nothing was signalled, as with no pgid: recovery never guesses a group."""
    if not _signal_group(pgid, signal.SIGTERM, fx):
        return False
    fx.sleep(fx.grace)
    _signal_group(pgid, signal.SIGKILL, fx)
    return True


def _prune(root, now: float) -> None:
    try:
        names = os.listdir(gate_dir(root))
    except OSError:
        return
    for name in names:
        if ID.match(name):
            r = _load(result_path(root, name))
            ended = (r or {}).get("ended")
            if isinstance(ended, (int, float)) and now - ended > KEEP:
                shutil.rmtree(entry_dir(root, name), ignore_errors=True)


def _open_log(path: Path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab")


def _finish(root, fx: Fx, cfg: dict, e: dict, rc: int, started, ended, cut,
            note: str | None = None) -> dict:
    """Write result.json last, atomically; drop the entry; tell the inbox and ntfy."""
    gid = e["id"]
    d = entry_dir(root, gid)
    _mkdir(d)
    if note is not None:
        with _open_log(d / "log") as log:
            log.write(f"gate {gid}: {note}\n".encode())
    seconds = round(ended - started, 1) if isinstance(started, (int, float)) else None
    result = {"id": gid, "repo": e.get("repo"), "command": e.get("command"), "exit": rc,
              "started": started, "ended": ended, "seconds": seconds,
              "log": str(d / "log"), "caller": e.get("caller"), "cut": cut}
    _write_private(result_path(root, gid), json.dumps(result, indent=1) + "\n")
    _unlink(_queue(root) / f"{gid}.json")
    caller = e.get("caller")
    if isinstance(caller, str) and caller:
        try:
            inbox_write(root, caller, result)
        except OSError as err:
            fx.log(f"gate {gid}: the inbox of {caller} was not written: {err}")
    err = notify(result, cfg, fx.post)
    if err:
        fx.log(err)
    _prune(root, ended)
    return result


def _start(root, fx: Fx, cfg: dict, e: dict, s: _Set) -> None:
    """Spawn one entry into the set. Its id goes to runner.json first, its `pgid` null until
    the spawn answers, so a runner that dies in between leaves the entry named and the next
    one closes it, 125, and never runs it twice; with no pgid, `_recover` signals nothing.
    The child holds its log; the runner reopens it at the end. A command that cannot start
    is closed here, 127, and counts as no start."""
    gid = e["id"]
    d = entry_dir(root, gid)
    _mkdir(d)
    s.starting = gid
    _runner_write(root, fx, s)
    started = fx.now()
    with _open_log(d / "log") as log:
        log.write(f"gate {gid}: {e['repo']}: {shlex.join(e['command'])}\n".encode())
        log.flush()
        try:
            p = fx.popen(e["command"], cwd=e["repo"], env=e.get("env") or {},
                         stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True, close_fds=True)
        except (OSError, ValueError, subprocess.SubprocessError) as err:
            log.write(f"gate {gid}: cannot start: {err}\n".encode())
            p = None
    s.starting = None
    if p is None:
        _close(root, fx, cfg, e, 127, started, None, s)
        return
    s.running.append(_Child(e, p, started))
    s.last_start = started
    _runner_write(root, fx, s)


def _close(root, fx: Fx, cfg: dict, e: dict, rc: int, started, cut, s: _Set) -> None:
    ended = fx.now()
    with _open_log(entry_dir(root, e["id"]) / "log") as log:
        log.write(f"gate {e['id']}: exit {rc} in {round(ended - started)} s\n".encode())
    _finish(root, fx, cfg, e, rc, started, ended, cut)
    _runner_write(root, fx, s)


def _reap(root, fx: Fx, cfg: dict, s: _Set) -> bool:
    """One look at each child, never waiting on any: a finish kills what its group left
    running, since the key frees here and the next of that key would overlap it, and closes
    it with the command's own code; at its wall, the group's SIGTERM, then at the grace SIGKILL (the child is not polled between them, so its
    group's id stays its own), then 124 once it is gone or a second grace has passed. True
    when one closed."""
    closed = False
    for c in list(s.running):
        now, code, cut = fx.now(), None, None
        if c.term_at is None:
            code = c.proc.poll()
            if code is not None:
                code = code if code >= 0 else 128 - code
                _signal_group(c.proc.pid, signal.SIGKILL, fx)
            elif now - c.started >= (c.e["wall"] if isinstance(c.e.get("wall"), int) else WALL):
                c.term_at = now
                if not _signal_group(c.proc.pid, signal.SIGTERM, fx):
                    c.kill_at = now
        elif c.kill_at is None:
            if now - c.term_at >= fx.grace:
                _signal_group(c.proc.pid, signal.SIGKILL, fx)
                c.kill_at = now
        elif c.proc.poll() is not None or now - c.kill_at >= fx.grace:
            code, cut = 124, CUT_WALL
        if code is not None:
            s.running.remove(c)
            _close(root, fx, cfg, c.e, code, c.started, cut, s)
            closed = True
    return closed


def _recover(root, fx: Fx, cfg: dict) -> None:
    """A runner.json while this runner holds the flock is a dead runner's: for each entry
    it names, kill the group, when it names one, and write 125 unless a result is there;
    drop the file."""
    path = gate_dir(root) / "runner.json"
    r = runner_info(root)
    if r is None:
        _unlink(path)
        return
    for gid, pgid in _pairs(r):
        killed = _kill_group(pgid, fx)
        if result_path(root, gid).exists():
            _unlink(_queue(root) / f"{gid}.json")
        else:
            e = _load(_queue(root) / f"{gid}.json") or {"id": gid}
            e["id"] = gid
            what = "its group was killed" if killed else "no group to kill"
            _finish(root, fx, cfg, e, 125, _started_at(root, gid), fx.now(), CUT_DIED,
                    note=f"the runner (pid {r.get('pid')}) died; {what}")
    _unlink(path)
    fx.log(f"gate: a stale runner.json (pid {r.get('pid')}) was recovered")


def _lock_wait(head: dict, running: list[dict]) -> str | None:
    """The lock that alone keeps the head from starting, for the 126 cut. An entry behind
    its own key could not start anyway, and a path a running entry names is held by a
    command with a wall of its own: neither ticks, which is S38's meaning, where the head's
    wall never ran out on the entry in front of it."""
    if entry_key(head) in {entry_key(x) for x in running}:
        return None
    named = _named(running)
    return next((p for p in _locks(head) if not _is_named(p, named) and os.path.exists(p)), None)


def _step(root, fx: Fx, cfg: dict, s: _Set) -> bool:
    """One pass: True when it started or closed an entry. `s.seen` is the runner's memory of
    when it first saw each head locked: the 126 cut counts the wall from there, never from
    `queued`, and a head seen unlocked starts again (Amendment 1, F1). The head is the
    oldest entry not running."""
    if _reap(root, fx, cfg, s):
        return True
    running = [c.e for c in s.running]
    busy = {x["id"] for x in running}
    es = [e for e in entries(root) if e["id"] not in busy]
    for e in es:
        if result_path(root, e["id"]).exists():       # a runner died after its result
            _unlink(_queue(root) / f"{e['id']}.json")
            return True
    if not es:
        return False
    head, now, seen = es[0], fx.now(), s.seen
    held = _lock_wait(head, running)
    wall = head.get("wall") if isinstance(head.get("wall"), int) else WALL
    for gid in [k for k in seen if k != head["id"] or not held]:
        del seen[gid]
    if held:
        first = seen.setdefault(head["id"], now)
        if now - first > wall:
            del seen[head["id"]]
            _finish(root, fx, cfg, head, 126, first, now, CUT_LOCK,
                    note=f"lock {held} held past the wall ({wall} s); not run")
            return True
    e = next((x for x, why in _holds(es, running) if why is None), None)
    if e is None or (running and _over(cfg, fx, len(running), s.last_start, now)):
        return False
    _start(root, fx, cfg, e, s)
    return True


def serve(root, fx: Fx | None = None) -> int:
    """The runner. Exits 0 when another holds gate/runner.lock; else runs the queue,
    and after `fx.idle` seconds with nothing running or queued removes runner.json, releases
    the lock, rescans, and retakes it when an entry appeared, else exits 0."""
    fx = fx or Fx()
    g = gate_dir(root)
    _mkdir(_queue(root))
    with open(g / "runner.lock", "a+") as fh:
        if not _take(fh, fx):
            return 0
        cfg = _config(fx.env, fx.log)
        _recover(root, fx, cfg)
        _prune(root, fx.now())
        while True:
            s = _Set(fx.now())
            _runner_write(root, fx, s)
            idle_at = fx.now()
            while True:
                if _step(root, fx, cfg, s):
                    idle_at = fx.now()
                    continue
                if not s.running and not entries(root) and fx.now() - idle_at >= fx.idle:
                    break
                fx.sleep(fx.poll)
            _unlink(g / "runner.json")
            fx.flock(fh.fileno(), fcntl.LOCK_UN)
            if not entries(root) or not _take(fh, fx):
                return 0


# ---- the reads ---------------------------------------------------------------

def wait_line(result: dict) -> str:
    return (f"gate {result.get('id')} {result.get('repo')}: exit {result.get('exit')} in "
            f"{_minutes(result.get('seconds'))} min; log {result.get('log')}")


def wait(root, gid: str, poll=WAIT_POLL, timeout=None, sleep=None, clock=None, spawn=None,
         alive=_alive) -> tuple[int, dict | None]:
    """(0, result) once result.json is there; (2, None) for an id neither queued nor
    done; (1, None) past `timeout` seconds. Spawns `serve` at the first poll, and again
    only when runner.json names no live pid."""
    sleep, clock = sleep or time.sleep, clock or time.monotonic
    if not isinstance(gid, str) or not ID.match(gid):
        return 2, None
    t0, first = clock(), True
    while True:
        r = _load(result_path(root, gid))
        if r is not None:
            return 0, r
        if not (_queue(root) / f"{gid}.json").exists():
            r = _load(result_path(root, gid))           # written between the two reads
            return (0, r) if r is not None else (2, None)
        if first or not alive((runner_info(root) or {}).get("pid")):
            (spawn or spawn_serve)(root)
            first = False
        left = None if timeout is None else timeout - (clock() - t0)
        if left is not None and left <= 0:
            return 1, None
        sleep(poll if left is None else min(poll, left))


def _wait_text(why) -> str | None:
    if why is None:
        return None
    kind = why[0]
    if kind == "load":
        x = "?" if why[1] is None else f"{round(why[1], 1):g}"
        return f"load {x} over {round(why[2], 1):g}"
    if kind == "running":
        return f"running {why[1]} of {why[2]}"
    if kind == "settle":
        return f"settle {round(why[1])} s"
    return f"{kind} {why[1]}"


def status(root, now, alive=_alive, fx: Fx | None = None) -> dict:
    """{running, queued, done, runner}: the entries running, a list; the rest in order, each
    with its key and its wait; the last five results newest first; the live runner or None.
    The wait is the runner's own rule, from `_holds` and `_over`; the load is read only for
    an entry nothing else holds, and only with one running."""
    fx = fx or Fx()
    r = runner_info(root)
    live = r if r and alive(r.get("pid")) else None
    run = _running_ids(root, alive)
    es = entries(root)
    byid = {e["id"]: e for e in es}
    running = []
    for gid in run:
        e = byid.get(gid, {})
        at = _started_at(root, gid)
        running.append({"id": gid, "repo": e.get("repo"), "label": e.get("label") or "",
                        "since": at, "seconds": (now - at) if at else None})
    waiting = [e for e in es if e["id"] not in run]
    queued, over, last = [], None, None
    for i, (e, why) in enumerate(_holds(waiting, [byid.get(g, {}) for g in run]), 1):
        if why is None and running:
            if last is None:
                last = max((x["since"] for x in running if x["since"]), default=0)
                over = _over(_config(fx.env), fx, len(running), last, now)
            why = over
        queued.append({"id": e["id"], "repo": e.get("repo"), "position": i, "lock": _locked(e),
                       "label": e.get("label") or "", "key": entry_key(e),
                       "wait": _wait_text(why)})
    done = []
    try:
        names = sorted((n for n in os.listdir(gate_dir(root)) if ID.match(n)),
                       key=_counter, reverse=True)
    except OSError:
        names = []
    for n in names:
        res = _load(result_path(root, n))
        if res is not None:
            done.append({k: res.get(k) for k in ("id", "repo", "exit", "seconds", "cut")})
            if len(done) == DONE_SHOWN:
                break
    runner = {"pid": live.get("pid"), "since": live.get("since")} if live else None
    return {"running": running, "queued": queued, "done": done, "runner": runner}


def status_lines(st: dict) -> list[str]:
    out = []
    for x in st.get("running") or []:
        out.append(f"running {x['id']} {x['repo']} since {_hm(x['since'])} {x['label']}".rstrip())
    for x in st.get("queued") or []:
        wait = f" waits on {x['wait']}" if x.get("wait") else ""
        out.append(f"queued {x['id']} {x['repo']} position {x['position']}{wait}")
    for x in st.get("done") or []:
        out.append(f"done {x['id']} {x['repo']} exit {x['exit']} {_minutes(x['seconds'])} min")
    rn = st.get("runner")
    out.append(f"runner: pid {rn['pid']} since {_hm(rn['since'])}" if rn else "runner: none")
    return out


# ---- the caller's inbox and ntfy ---------------------------------------------

def inbox_write(root, sid: str, result: dict) -> Path | None:
    """`<state>/sessions/<sid>/inbox/<id>.json` {at, kind, id, repo, exit, seconds, log}."""
    if not isinstance(sid, str) or not _SID.match(sid) or not ID.match(str(result.get("id"))):
        return None
    d = _inbox(root, sid)
    _mkdir(d)
    body = {"at": result.get("ended"), "kind": "gate", "id": result["id"],
            "repo": result.get("repo"), "exit": result.get("exit"),
            "seconds": result.get("seconds"), "log": result.get("log")}
    path = d / f"{result['id']}.json"
    _write_private(path, json.dumps(body) + "\n")
    return path


def inbox_take(root, sid: str, limit=TAKE, fits=None) -> list[str]:
    """At most `limit` inbox files, oldest first, each taken by an atomic rename into
    `inbox/read/` and read as its wait line, then `<n> more: ...` when any remain. `fits`
    (the text so far) stops the take where the hook's output would pass its ceiling."""
    if not isinstance(sid, str) or not _SID.match(sid):
        return []
    d = _inbox(root, sid)

    def waiting() -> list[Path]:
        try:
            return sorted((p for p in d.iterdir() if p.suffix == ".json" and ID.match(p.stem)),
                          key=lambda p: _counter(p.stem))
        except OSError:
            return []
    fits = fits or (lambda text: True)
    files, lines = waiting(), []
    for i, p in enumerate(files):
        if len(lines) >= limit:
            break
        body = _load(p)
        if body is None:                               # unreadable: set aside, unprinted
            _mkdir(d / "read")
            try:
                os.rename(p, d / "read" / p.name)
            except OSError:
                pass
            continue
        left = len(files) - i - 1
        line = wait_line(body)
        if not fits("\n".join(lines + [line] + ([MORE.format(n=left)] if left else []))):
            break
        _mkdir(d / "read")
        try:
            os.rename(p, d / "read" / p.name)
        except OSError:
            continue                                   # another hook took it first
        lines.append(line)
    rest = len(waiting())
    if rest and fits("\n".join(lines + [MORE.format(n=rest)])):
        lines.append(MORE.format(n=rest))
    return lines


def notify(result: dict, cfg: dict, post=None) -> str | None:
    """POST the wait line to `ntfy_url/ntfy_topic` when both are set; the error as one
    line when it fails, else None."""
    url, topic = (cfg or {}).get("ntfy_url"), (cfg or {}).get("ntfy_topic")
    if not (isinstance(url, str) and url and isinstance(topic, str) and topic):
        return None
    target = url.rstrip("/") + "/" + topic
    try:
        (post or _default_post)(target, wait_line(result).encode(),
                                {"Title": f"gate {result.get('repo')}: exit {result.get('exit')}"},
                                5)
    except Exception as e:                              # noqa: BLE001
        return " ".join(f"gate {result.get('id')}: ntfy {target}: {type(e).__name__}: "
                        f"{e}".split())
    return None
