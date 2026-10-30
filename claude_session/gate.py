"""The gate queue (design/gate-r1.md, packet S38): one FIFO per state root, run by one
detached runner, a command at a time.

`enqueue` writes `<state>/gate/queue/<id>.json`; `serve` is the runner, which takes the
oldest entry none of whose lock paths exists, runs it in its own process group in its
repo, writes `<state>/gate/<id>/log` and then `result.json`, drops the entry from the
queue, and tells the caller's inbox (and ntfy when configured). `wait`, `status` and the
inbox are reads. The tool reports exit codes and judges none: 124 is the wall's cut, 125
a runner that died, 126 a lock held past the wall, 127 a command that could not start.
Every effect the runner has (the clock, spawn, flock, the group kill, the POST) is in Fx,
so a test fakes each one.
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
ENTRY_KEYS = ("id", "repo", "command", "env", "locks", "wall", "label", "caller", "queued")
RESULT_KEYS = ("id", "repo", "command", "exit", "started", "ended", "seconds", "log",
               "caller", "cut")
INBOX_KEYS = ("at", "kind", "id", "repo", "exit", "seconds", "log")
RUNNER_KEYS = ("pid", "since", "running", "pgid")
GATE_DEFAULTS = {"ntfy_url": None, "ntfy_topic": None, "wall": WALL}


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


def _config(env) -> dict:
    """The gate section's user layer (packet ruling 4): ntfy_url, ntfy_topic, wall."""
    from . import resolver
    return resolver.gate_config(env)


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
    with open(g / "queue.lock", "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            n = int((g / "counter").read_text().strip()) + 1
        except (OSError, ValueError):
            n = 1 + max((_counter(e["id"]) for e in entries(root)), default=0)
        _write_private(g / "counter", f"{n}\n")
        gid = time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{n}"
        entry = {"id": gid, "repo": real, "command": list(command), "env": dict(env),
                 "locks": [os.path.abspath(p) for p in locks], "wall": wall,
                 "label": label or "", "caller": caller, "queued": now}
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


def _running_id(root, alive=_alive) -> str | None:
    r = runner_info(root)
    gid = (r or {}).get("running")
    return gid if r and alive(r.get("pid")) and isinstance(gid, str) and ID.match(gid) else None


def position(root, gid: str, alive=_alive) -> int:
    """The place among the entries not yet started (1 is next); 0 when not queued."""
    run = _running_id(root, alive)
    ids = [e["id"] for e in entries(root) if e["id"] != run]
    return ids.index(gid) + 1 if gid in ids else 0


def _locked(e: dict) -> str | None:
    for p in e.get("locks") or []:
        if isinstance(p, str) and os.path.exists(p):
            return p
    return None


def spawn_serve(root, popen=None) -> bool:
    """Start `serve` detached when the queue is not empty: this interpreter (never PATH),
    a new session, close_fds, stdio to gate/runner.log, PYTHONPATH led by this package's
    parent so the runner is this code. True when it spawned."""
    if not entries(root):
        return False
    popen = popen or subprocess.Popen
    g = gate_dir(root)
    _mkdir(g)
    here = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ)
    rest = [p for p in (env.get("PYTHONPATH") or "").split(os.pathsep) if p and p != here]
    env["PYTHONPATH"] = os.pathsep.join([here, *rest])
    flags = (["-P"] if getattr(sys.flags, "safe_path", False) else []) + \
        (["-B"] if sys.flags.dont_write_bytecode else [])
    argv = [sys.executable, *flags, "-m", "claude_session", "gate", "serve", "--root", str(root)]
    with open(g / "runner.log", "ab") as log:
        popen(argv, cwd=str(g), env=env, stdin=subprocess.DEVNULL, stdout=log,
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


def _runner_write(root, fx: Fx, since: float, running, pgid) -> None:
    _write_private(gate_dir(root) / "runner.json",
                   json.dumps({"pid": fx.pid, "since": since, "running": running,
                               "pgid": pgid}) + "\n")


def _kill_group(pgid, fx: Fx) -> None:
    """SIGTERM to the group, the grace, then SIGKILL; a group already gone ends it."""
    if not isinstance(pgid, int) or isinstance(pgid, bool) or pgid <= 1 or pgid == os.getpgrp():
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            fx.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            return
        if sig == signal.SIGTERM:
            fx.sleep(fx.grace)


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


def _run(root, fx: Fx, cfg: dict, e: dict, since: float) -> None:
    gid = e["id"]
    d = entry_dir(root, gid)
    _mkdir(d)
    started = fx.now()
    cut = None
    with _open_log(d / "log") as log:
        log.write(f"gate {gid}: {e['repo']}: {shlex.join(e['command'])}\n".encode())
        log.flush()
        try:
            p = fx.popen(e["command"], cwd=e["repo"], env=e.get("env") or {},
                         stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True, close_fds=True)
        except (OSError, ValueError, subprocess.SubprocessError) as err:
            log.write(f"gate {gid}: cannot start: {err}\n".encode())
            rc = 127
        else:
            _runner_write(root, fx, since, gid, p.pid)
            while True:
                code = p.poll()
                if code is not None:
                    rc = code if code >= 0 else 128 - code
                    break
                if fx.now() - started >= e["wall"]:
                    _kill_group(p.pid, fx)
                    try:
                        p.wait(timeout=fx.grace)
                    except Exception:                       # noqa: BLE001
                        pass
                    rc, cut = 124, CUT_WALL
                    break
                fx.sleep(fx.poll)
        ended = fx.now()
        log.write(f"gate {gid}: exit {rc} in {round(ended - started)} s\n".encode())
    _finish(root, fx, cfg, e, rc, started, ended, cut)
    _runner_write(root, fx, since, None, None)


def _recover(root, fx: Fx, cfg: dict) -> None:
    """A runner.json while this runner holds the flock is a dead runner's: kill its
    group, write 125 for its entry unless a result is there, drop the file."""
    path = gate_dir(root) / "runner.json"
    r = runner_info(root)
    if r is None:
        _unlink(path)
        return
    gid = r.get("running")
    if isinstance(gid, str) and ID.match(gid):
        _kill_group(r.get("pgid"), fx)
        if result_path(root, gid).exists():
            _unlink(_queue(root) / f"{gid}.json")
        else:
            try:
                started = path.stat().st_mtime        # rewritten when the entry started
            except OSError:
                started = None
            e = _load(_queue(root) / f"{gid}.json") or {"id": gid}
            e["id"] = gid
            _finish(root, fx, cfg, e, 125, started, fx.now(), CUT_DIED,
                    note=f"the runner (pid {r.get('pid')}) died; its group was killed")
    _unlink(path)
    fx.log(f"gate: a stale runner.json (pid {r.get('pid')}) was recovered")


def _step(root, fx: Fx, cfg: dict, since: float, seen: dict | None = None) -> bool:
    """One pass: True when it ran or closed an entry. `seen` is the runner's memory of
    when it first saw each head locked: the 126 cut counts the wall from there, never
    from `queued`, and a head seen unlocked starts again (Amendment 1, F1)."""
    seen = {} if seen is None else seen
    es = entries(root)
    for e in es:
        if result_path(root, e["id"]).exists():       # a runner died after its result
            _unlink(_queue(root) / f"{e['id']}.json")
            return True
    if not es:
        return False
    head, now = es[0], fx.now()
    held = _locked(head)
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
    for e in es:
        if not _locked(e):
            _run(root, fx, cfg, e, since)
            return True
    return False


def serve(root, fx: Fx | None = None) -> int:
    """The runner. Exits 0 when another holds gate/runner.lock; else runs the queue,
    and after `fx.idle` seconds with nothing queued removes runner.json, releases the
    lock, rescans, and retakes it when an entry appeared, else exits 0."""
    fx = fx or Fx()
    g = gate_dir(root)
    _mkdir(_queue(root))
    with open(g / "runner.lock", "a+") as fh:
        if not _take(fh, fx):
            return 0
        cfg = _config(fx.env)
        _recover(root, fx, cfg)
        _prune(root, fx.now())
        while True:
            since = fx.now()
            _runner_write(root, fx, since, None, None)
            idle_at, seen = fx.now(), {}
            while True:
                if _step(root, fx, cfg, since, seen):
                    idle_at = fx.now()
                    continue
                if not entries(root) and fx.now() - idle_at >= fx.idle:
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


def status(root, now, alive=_alive) -> dict:
    """{running, queued, done, runner}: the entry running, the rest in order with the
    lock each waits on, the last five results newest first, the live runner or None."""
    r = runner_info(root)
    live = r if r and alive(r.get("pid")) else None
    run = _running_id(root, alive)
    es = entries(root)
    running = None
    if run:
        e = next((x for x in es if x["id"] == run), {})
        try:
            at = (gate_dir(root) / "runner.json").stat().st_mtime
        except OSError:
            at = None
        running = {"id": run, "repo": e.get("repo"), "label": e.get("label") or "",
                   "since": at, "seconds": (now - at) if at else None}
    queued = [{"id": e["id"], "repo": e.get("repo"), "position": i, "lock": _locked(e),
               "label": e.get("label") or ""}
              for i, e in enumerate((x for x in es if x["id"] != run), 1)]
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
    if st.get("running"):
        x = st["running"]
        out.append(f"running {x['id']} {x['repo']} since {_hm(x['since'])} {x['label']}".rstrip())
    for x in st.get("queued") or []:
        lock = f" waits on lock {x['lock']}" if x.get("lock") else ""
        out.append(f"queued {x['id']} {x['repo']} position {x['position']}{lock}")
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
