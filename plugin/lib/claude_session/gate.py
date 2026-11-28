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
(the clock, spawn, flock, the group kill, the POST, the load, the cores, the head and the
machine's reads) is in Fx, so a test fakes each one.

A result also says what the machine was doing (packet gl1): `load`, `{"start": [a, b, c],
"end": [a, b, c]}`, the three load averages read just before the spawn and just after the
child is reaped; `beside`, the ids running when the job started, oldest first; `dirty`,
`{"start": n, "end": n}`, the lines of `git status --porcelain --untracked-files=all` in the
job's folder, read as `_head` reads git, with `-c core.fsmonitor=false` so it starts no daemon
and writes nothing there. A side is null where it was not read (no work tree,
git failing or past `GIT_WAIT`, a read that raised, which logs one line); a job the runner
did not start and end itself (127's end, 125, 126, a caller's 130 before a start) holds the
keys with those sides null, and `beside` null when it was not read. A result older than the
keys holds none, and every reader takes an absent key as null. No read holds a start or
moves a job's `seconds`; `_over` reads the one-minute load apart.

A result's last key, `make_env` (packet land5-publish, review 1 F2), names those of
`MAKEFLAGS`, `MFLAGS`, `GNUMAKEFLAGS` and `MAKEFILES` that are set in the job's environment,
sorted, `[]` when none, null where the entry's env is no mapping: a `make check` run under one
of them may run nothing, and `gate publish` proves a check only where the list is there and
empty. The gate scrubs nothing; a job's environment stays its caller's.

A result follows the chain (packet nw2-chain-inbox, design/31 items 8 to 12). `enqueue` writes
`chain` on every entry (`chain_for`): the chain's name where the caller is a chain's sitting or
its helper and, where the chain's home holds `sitting.json`, the session it names; else null,
and null under `--session`. A chain's result keeps `chain` and `label` and its line goes to
`<state>/respawn/<chain>/inbox/`, never a session's; a result with no chain goes to its
caller's inbox as before, and its keys and line are the pin's. `inbox_take` takes a session's
own lines, then its chain's (`chain_taker`), by the same rename under the same bounds; a
sitting whose respawn mark is confirmed (`sitting_closed`) is shown each chain line once and
leaves the file for the successor; a chain line older than `OLD_LINE` is set aside into
`inbox/old/` and counted. `wait_chain` is `gate wait --chain`. An estimate counts the greens of
one command kind (`command_kind`).

One check proves a landing (packet nw5-check-proof, design/31 items 21 to 24). `gate run
<worktree> --check` queues `CHECK_JOB`, which runs `land.run_check` there: `make check` without
the eight names `land.main` drops and `gate.check_drop`'s, writing `<state>/gate/<id>/check.json`
(0600, written then renamed) at its start with a null `exit` and again at its end. Nothing else
writes that file; `_prune` removes it with its folder. Its kind is `make check`; `gate publish`
reads no such job as a proof, since its command is no `make check` of today's form.
"""

from __future__ import annotations

import fcntl
import fnmatch
import json
import math
import os
import re
import shlex
import shutil
import signal
import stat
import statistics
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import install
from . import machine
from . import state as statefile

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
REPO_SHOWN = 20             # `status --repo`'s done lines before its more line (packet rw3, R5)
CUT_WALL, CUT_DIED, CUT_LOCK = "wall cut", "runner died", "lock wait cut"
CUT_CALLER, CALLER_EXIT = "caller cut", 130     # a cancel mark's cut (fw5 R4)
MORE = "{n} more: agentik session gate status"
MORE_REPO = "{n} more: agentik session gate status --repo {path} --json"
LAND_JOB = ("gate", "land", "--in-job")     # a landing's job, then repo, branch, sha, merge
CHECK_JOB = ("gate", "run", "--check", "--in-job")    # a kept check's job, then its worktree
ENTRY_KEYS = ("id", "repo", "command", "env", "locks", "wall", "label", "caller", "queued",
              "key", "key_name", "chain")
RESULT_KEYS = ("id", "repo", "command", "exit", "started", "ended", "seconds", "log",
               "caller", "cut", "head", "key", "load", "beside", "dirty", "make_env")
MAKE_ENV = ("MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKEFILES")    # land5 review 1, F2
SIDES = ("start", "end")    # the two sides of `load` and `dirty` (packet gl1, R1)
INBOX_KEYS = ("at", "kind", "id", "repo", "exit", "seconds", "log")
RUNNER_KEYS = ("pid", "since", "running")
DONE_KEYS = ("id", "repo", "exit", "seconds", "cut", "load", "beside", "dirty")  # gl1 R4
GATE_DEFAULTS = {"ntfy_url": None, "ntfy_topic": None, "wall": WALL}
MAX_RUNNING = 3             # gate.max_running's default (packet S47, ruling 4)
LOAD_SHARE = 0.75           # gate.load_ceiling's default, as a share of the cores
START_SETTLE = 60.0         # the seconds between two starts, since a load average lags
GIT_WAIT = 10.0
EST_SCAN = 200              # the results an estimate reads, newest first (packet FW2, R4)
EST_GREENS = 5              # the greens of one key it keeps
EST_LEAST = 3               # under this many, a key has no estimate
_HEAD = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
DOT_GIT_MOST = 4096         # a `.git` file or a `commondir` is one short line
CHAIN_VAR = "CLAUDE_SESSION_CHAIN"          # resolver.CHAIN_VAR (a test pins both)
CHAIN_RE = re.compile(r"^(?!\.+\Z)[A-Za-z0-9._-]{1,64}\Z")    # resolver.CHAIN_RE
SITTING = "sitting.json"            # the chain home's word on its live sitting (nw2 R2)
MARKER, CONFIRMED = "respawn.json", "respawn-main.json"     # hooks.MARKER, hooks.CONFIRMED
SHOWN = "gate-shown.json"           # a closed sitting's chain lines already shown, by id
OLD_LINE = 86400.0                  # a chain line older than this is set aside (nw2 R2)
LABEL_MOST = 48                     # a chain line's label, in bytes (nw2 R3)
CHAIN_KEYS = ("chain", "label")     # a chain's result's keys after RESULT_KEYS
MEASURE_KEYS = ("waited", "cpu_seconds", "tree", "peak_mb", "cpu", "mem_mb")    # hw1 W2, hw6 R6
FAIL_MOST = 80                      # a red line's failing text, in bytes (hw1 W5)
FAIL_LINE = re.compile(r"^(?:--- FAIL|FAIL|ERROR|make(?:\[\d+\])?: \*\*\*)"
                       r"|AssertionError|^(?:E\s+)?(?:[A-Za-z_][\w.]*)?Error:")
MAKE_FAIL = re.compile(r"^make(?:\[\d+\])?: \*\*\*")     # make's own; another is said first (R3)
WITHIN_MOST = 100                   # `gate run --within`'s bound, in seconds (hw1 W1)
QUEUED = 75                         # `--within`'s exit when the job is still open
TAIL = 20                           # a red's log lines `--within` prints
CHAIN_INBOX_KEYS = ("chain", "head", "dirty", "label")
CLOSED_WORDS = "this sitting has closed: the line stays for the successor"
OPEN_NAMED = 3                      # the open jobs a start line names, then `and N more`
JOB_MARK = "CLAUDE_SESSION_GATE_JOB"    # each job's env names its own id (packet FW4c, R2)
OLD_ENTRY = 3600.0                  # an entry this old is never passed over (hw5 F1)
LIGHT_WALL = 120                    # a light job's wall, and its most (hw5 F2)
RERUN_WAIT = 1800.0                 # a rerun not started this long after its flake goes (F3)
FLAKE_TAIL = 64 * 1024              # the log's bytes a flake's stop line is looked for in
STOP_LINES = (b"bounded: stop: lock", b"bounded: stop: load", b"bounded: stop: wall",
              b"panic: test timed out")         # land.STOPS's and Go's (a test pins both)
PYTEST_TIMEOUT = re.compile(rb"^(?:\++ Timeout \++|E? *Failed: Timeout >.*)$", re.M)
NOT_FLAKE = (b"--- FAIL", b"AssertionError", b"WARNING: DATA RACE")
RED_KEYS = ("ceiling", "alongside")     # a red that ran, after MEASURE_KEYS (hw5 F3)
MARK_KEYS = ("flake", "rerun", "rerun_of", "dropped", "over", "guard_unread", "would_hold")
CLASS_KEYS = ("cpu", "mem_mb")          # an entry's class, after the pin's keys (hw6 B1, R1)
HISTORY = 5                             # the results of one folder and command a class reads
MEM_PLUS = 1.25                         # a peak's, or a JVM heap's, grant: it plus a quarter
SAMPLE_EVERY = 10.0                     # seconds between two samples of a job's group (B2)
SNAP_EVERY = 10.0                       # the seconds one folder's snapshot is reused (B3, B4)
BUDGET_PASS = 600.0                     # an entry held this long by the budget is not passed
HOLD_MAX = 1200                         # a guard's hold of one entry, at most (B4)
GUARDS = ("load", "pressure", "disk")
GRANT_ENV = ("AGENTIK_CPUS", "AGENTIK_MEM_MB", "GOMAXPROCS")   # B5; no digest counts them
HOLDS = "holds.json"                    # the runner's word on what holds each entry, since when
FLAKE, NOT_RERUN = "load", "load, not rerun"


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


def cancel_path(root, gid: str) -> Path:
    """The cancel mark of entry `gid` (fw5 R4): its caller left the wait with no result."""
    return _queue(root) / f"{gid}.cancel"


def cancel(root, gid: str) -> None:
    """Write `gid`'s cancel mark, atomically. Only the runner acts on it: an entry not started
    is closed unrun, a running one cut as the wall cuts; both read exit 130, `caller cut`."""
    _mkdir(_queue(root))
    _write_private(cancel_path(root, gid), "")


def drop_path(root, gid: str) -> Path:
    """Build 2, S7: the mark of a drop in hand, flocked by its `gate drop` while it works; the
    entry itself is never moved."""
    return _queue(root) / f"{gid}.drop"


def _hand(root, gid: str):
    """Open and flock `gid`'s drop mark, made 0600 where it is not there; the open file. One
    a sweep unlinked while this waited on its flock is opened again."""
    path = drop_path(root, gid)
    for _ in range(5):
        fh = os.fdopen(os.open(path, os.O_RDWR | os.O_CREAT, 0o600), "r+")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            same = os.fstat(fh.fileno()).st_ino == os.stat(path).st_ino
        except OSError:
            same = False
        if same:
            return fh
        fh.close()
    raise OSError(f"the drop mark of {gid} kept moving")


def _sweep_drops(root) -> set:
    """Build 2, S7: the ids a drop has in hand, each mark whose flock is held; a mark whose
    flock is free is a dead drop's and goes, its entry then queued as it was, or, where the
    drop wrote its result, dropped by the step as any entry beside its result is."""
    held = set()
    try:
        names = os.listdir(_queue(root))
    except OSError:
        return held
    for name in names:
        gid = name[:-5] if name.endswith(".drop") else ""
        if not ID.match(gid):
            continue
        try:
            fd = os.open(_queue(root) / name, os.O_RDONLY)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            held.add(gid)
        else:
            _unlink(_queue(root) / name)
        finally:
            os.close(fd)
    return held


def _sweep_marks(root) -> None:
    """A mark whose entry is gone (its job ended before the mark landed) goes."""
    try:
        names = os.listdir(_queue(root))
    except OSError:
        return
    for name in names:
        if name.endswith(".cancel") and ID.match(name[:-7]) \
                and not (_queue(root) / f"{name[:-7]}.json").exists():
            _unlink(_queue(root) / name)


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


def _load(path: Path, strict: bool = False) -> dict | None:
    """The file's mapping, or None. hw6 B6: with `strict`, a file that is there and cannot be
    read, or that is no JSON mapping (fix 1, F3), raises GateError, so an unreadable gate is
    told from an empty one."""
    try:
        d = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    except OSError as err:
        if strict:
            raise GateError(f"{path}: {err.strerror or err}") from err
        return None
    except ValueError as err:
        if strict:
            raise GateError(f"{path}: it does not parse ({err})") from err
        return None
    if strict and not isinstance(d, dict):
        raise GateError(f"{path}: it is no mapping")
    return d if isinstance(d, dict) else None


def _listdir(path, strict: bool = False) -> list[str]:
    """The folder's names, [] where it is not there; hw6 B6: with `strict`, a folder that
    cannot be read raises GateError."""
    try:
        return os.listdir(path)
    except FileNotFoundError:
        return []
    except OSError as err:
        if strict:
            raise GateError(f"{path}: {err.strerror or err}") from err
        return []


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


def _head(repo: str) -> str | None:
    """`git -C <repo> rev-parse HEAD`, with no `GIT_*` from the caller, under `GIT_WAIT`:
    40 or 64 hex digits, else None (packet FW2, R2). Never raises."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=GIT_WAIT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    out = p.stdout.strip() if p.returncode == 0 else ""
    return out if _HEAD.match(out) else None


def _tree(repo: str) -> str | None:
    """`git -C <repo> rev-parse HEAD^{tree}`, run as `_head` runs git: the head's tree, else
    None (hw1 W2). Never raises."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "rev-parse", "-q", "--verify", "HEAD^{tree}"],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=GIT_WAIT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    out = p.stdout.strip() if p.returncode == 0 else ""
    return out if _HEAD.match(out) else None


def clean_tree(repo: str) -> str | None:
    """The head's tree where the folder is a work tree with no status line, untracked files
    counted; None for a dirty tree or one git cannot read, which is never matched (hw1 W4)."""
    return _tree(repo) if _dirty(repo) == 0 else None


def _branch(repo: str) -> str | None:
    """`git -C <repo> symbolic-ref --short -q HEAD`, run as `_head` runs git: the checked-out
    branch, else None (a detached head, no work tree, git failing; packet rw3, R3). Never
    raises."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "symbolic-ref", "--short", "-q", "HEAD"],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=GIT_WAIT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    out = p.stdout.strip() if p.returncode == 0 else ""
    return out or None


def top_level(repo: str) -> str:
    """Build 2, S3: a folder's worktree, `git -C <repo> rev-parse --show-toplevel` resolved;
    the resolved folder where it is in no checkout or git fails. Never raises."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=GIT_WAIT)
        out = p.stdout.rstrip("\n") if p.returncode == 0 else ""
    except (OSError, ValueError, subprocess.SubprocessError):
        out = ""
    return _real(out) if out else _real(repo)


def worktree(e: dict):
    """Build 2, S3: the worktree an entry's light-class tests read, its `top` where the entry
    holds one (its folder was below its worktree's top), else its `repo`."""
    t = e.get("top")
    return t if isinstance(t, str) and t else e.get("repo")


def repo_path(path) -> str | None:
    """A folder as `status --repo` compares it (packet rw3, R2): the real path of its absolute
    form, which for a path that does not exist is its absolute, normal form, any parent that
    exists resolved. None for what is not a non-empty string. Never raises."""
    if not isinstance(path, str) or not path:
        return None
    try:
        return os.path.realpath(os.path.abspath(path))
    except (OSError, ValueError):
        return os.path.normpath(path)


def land_branch(command) -> str | None:
    """The branch of a landing's job, a command holding `gate land --in-job` and then four
    words, repo, branch, sha and merge file (packet rw3, R3); else None."""
    if not isinstance(command, list):
        return None
    for i in range(len(command) - 6):
        if tuple(command[i:i + 3]) == LAND_JOB:
            words = command[i + 3:i + 7]
            return words[1] if all(isinstance(w, str) and w for w in words) else None
    return None


def _runner_argv(words) -> bool:
    """Whether `words` are a runner's argv as `self_argv` writes it: an interpreter's absolute
    path, `-I -X pycache_prefix=...`, and a path ending in this plugin's launcher. The paths
    may differ between installs (packet nw5-check-proof, brief 3, R4)."""
    head = self_argv()
    if len(words) != len(head) or not all(isinstance(w, str) and w for w in words):
        return False
    return os.path.isabs(words[0]) and words[1:3] == head[1:3] \
        and words[3].startswith("pycache_prefix=") \
        and os.path.basename(words[4]) == os.path.basename(head[4])


def check_worktree(command) -> str | None:
    """The worktree of a kept check's job, the whole command a runner's argv, then `gate run
    --check --in-job` and one word (packet nw5-check-proof, brief 2, R4 and R5; brief 3, R4);
    else None."""
    n = len(self_argv())
    if not isinstance(command, list) or len(command) != n + len(CHECK_JOB) + 1:
        return None
    if not _runner_argv(command[:n]) or tuple(command[n:-1]) != CHECK_JOB:
        return None
    where = command[-1]
    return where if isinstance(where, str) and where else None


def _dirty(repo: str) -> int | None:
    """The count of lines of `git -C <repo> --no-optional-locks -c core.fsmonitor=false status
    --porcelain --untracked-files=all`, run as `_head` runs git: no `GIT_*` from the caller,
    under `GIT_WAIT`. None when the folder is in no work tree, git fails or the wait passes
    (packet gl1, R1). Never raises. The read starts no fsmonitor daemon and writes nothing in
    the job's `.git`, whatever the repo's config says (review 1, F2)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        p = subprocess.run(["git", "-C", repo, "--no-optional-locks", "-c",
                            "core.fsmonitor=false", "status", "--porcelain",
                            "--untracked-files=all"], env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=GIT_WAIT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return sum(1 for x in p.stdout.split(b"\n") if x) if p.returncode == 0 else None


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


def chain_home(root, name: str) -> Path:
    return Path(root) / "respawn" / name


def chain_inbox(root, name: str) -> Path:
    return chain_home(root, name) / "inbox"


def sitting_of(root, name: str) -> tuple[bool, str | None]:
    """(whether the chain's home holds `sitting.json`, the session it names or None). A file
    there that does not parse names no session."""
    path = chain_home(root, name) / SITTING
    if not path.exists():
        return False, None
    sid = (_load(path) or {}).get("session")
    return True, sid if isinstance(sid, str) and _SID.match(sid) else None


def write_sitting(root, name: str, sid: str, now) -> None:
    """The launcher's word on the sitting it starts (nw2 R2)."""
    _mkdir(chain_home(root, name))
    _write_private(chain_home(root, name) / SITTING,
                   json.dumps({"session": sid, "at": now}) + "\n")


def _env_chain(env) -> str | None:
    """The chain's name where the environment is a chain's sitting or its helper: no depth
    mark and no relay row (`state.main_sitting`, its helper's test aside)."""
    name = str(env.get(CHAIN_VAR) or "")
    if not CHAIN_RE.match(name):
        return None
    return name if statefile.main_sitting({**env, "CLAUDE_SESSION_HELPER": ""}) else None


def chain_for(root, env, caller, named: bool = False) -> str | None:
    """design/31 item 8: the chain an entry is addressed to, or None. `named`: `--session`
    was given, which names a session and no chain. With `sitting.json` in the chain's home,
    only the session it names queues for the chain."""
    name = None if named else _env_chain(env)
    if name is None:
        return None
    there, sid = sitting_of(root, name)
    if there and (sid is None or sid != caller):
        return None
    return name


def chain_taker(root, env, sid) -> str | None:
    """design/31 item 9: the chain whose inbox this main-thread session takes from, or None.
    With `sitting.json`, the session it names; without, the environment's test of item 8,
    no helper, and `lines.taker`'s test of the entrypoint (no `claude -p` or SDK child)."""
    from . import lines
    name = _env_chain(env)
    if name is None or not isinstance(sid, str) or not _SID.match(sid):
        return None
    there, named = sitting_of(root, name)
    if there:
        return name if named == sid else None
    if env.get("CLAUDE_SESSION_HELPER") == "1" \
            or env.get("CLAUDE_CODE_ENTRYPOINT") in lines.CHILD_ENTRYPOINTS:
        return None
    return name


def sitting_closed(root, sid) -> bool:
    """The session's respawn mark is confirmed: `respawn-main.json` holds the sha256 of
    `respawn.json`'s bytes. Any fault reads as open."""
    import hashlib
    if not isinstance(sid, str) or not _SID.match(sid):
        return False
    d = Path(root) / "sessions" / sid
    try:
        raw = (d / MARKER).read_bytes()
    except OSError:
        return False
    conf = _load(d / CONFIRMED)
    return isinstance(conf, dict) and conf.get("marker_sha256") == hashlib.sha256(raw).hexdigest()


def open_jobs(root, name: str) -> list[dict]:
    """The queued and running entries addressed to the chain, oldest first."""
    return [e for e in entries(root) if e.get("chain") == name]


def chain_count(root, name: str) -> int:
    """The lines the chain's inbox still holds (the launcher's stop line, nw2 R4)."""
    return len(_waiting(chain_inbox(root, name)))


def _label(text, most: int = LABEL_MOST) -> str:
    """A label as a line holds it: one line, each control character and `;` a space (brief
    2, R6: a label adds no field), cut to `most` bytes on a character."""
    t = "".join(" " if c == ";" or unicodedata.category(c) == "Cc" else c
                for c in str(text or ""))
    t = " ".join(t.split())
    return t.encode()[:most].decode("utf-8", "ignore")


def open_line(root, name: str, now, alive=_alive) -> str | None:
    """design/31 item 11: `gate: 2 jobs of this chain are open: <id> <label> running 31 min,
    est 54; <id> <label> queued`, or None with none open."""
    es = open_jobs(root, name)
    if not es:
        return None
    running = set(_running_ids(root, alive))
    parts = []
    for e in es[:OPEN_NAMED]:
        head = " ".join(x for x in (e["id"], _label(e.get("label"))) if x)
        if e["id"] in running:
            at = _started_at(root, e["id"])
            mins = "?" if at is None else str(max(0, round((now - at) / 60)))
            got = key_estimates(root, e.get("command")).get(entry_key(e))
            parts.append(f"{head} running {mins} min"
                         + (f", est {round(got[0] / 60)}" if got else ""))
        else:
            parts.append(f"{head} queued")
    n = len(es)
    more = f"; and {n - OPEN_NAMED} more" if n > OPEN_NAMED else ""
    return (f"gate: {n} {'job' if n == 1 else 'jobs'} of this chain "
            f"{'is' if n == 1 else 'are'} open: " + "; ".join(parts) + more)


def gate_words(n: int) -> str:
    """design/31 item 13's words for the CHECKPOINT line and the close."""
    return (f"{n} gate {'job is' if n == 1 else 'jobs are'} open and cross to the successor: "
            "do not wait for them")


def chain_status_lines(root, name: str, now, alive=_alive) -> list[str]:
    """`gate status --chain`: the chain's open jobs, then its results of the last 24 hours,
    newest first, each `taken` or `waiting`."""
    out = [open_line(root, name, now, alive) or f"gate: no job of chain {name} is open"]
    box = chain_inbox(root, name)
    for n in _result_names(root):
        r = _load(result_path(root, n))
        if r is None or r.get("chain") != name:
            continue
        ended = r.get("ended")
        if not isinstance(ended, (int, float)) or ended < now - OLD_LINE:
            continue
        out.append(wait_line(r) + ("; waiting" if (box / f"{n}.json").exists() else "; taken"))
    return out


def _write_entry(root, now, build) -> dict:
    """Write the entry `build(id)` makes under flock(gate/queue.lock), the counter taken there,
    and return it."""
    g = gate_dir(root)
    _mkdir(_queue(root))
    with open(g / "queue.lock", "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            n = int((g / "counter").read_text().strip()) + 1
        except (OSError, ValueError):
            n = 1 + max((_counter(e["id"]) for e in entries(root)), default=0)
        _write_private(g / "counter", f"{n}\n")
        entry = build(time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + f"-{n}")
        _write_private(_queue(root) / f"{entry['id']}.json", json.dumps(entry, indent=1) + "\n")
    return entry


def enqueue(root, repo, command, env, locks, wall, label, caller, now,
            named: bool = False, tree: str | None = None, priority: bool = False,
            light: bool = False, rerun: bool = False, cpu: int | None = None,
            mem_mb: int | None = None, jvm: bool = False, classes=None) -> dict:
    """Write one entry (mode 0600, written then renamed) and return it. The id is
    `YYYYMMDD-HHMMSS-<counter>`, the counter taken under flock(gate/queue.lock). Its
    `chain` is `chain_for`'s (nw2 R1); `named` is a `--session` the caller gave. `tree`, the
    head's tree of a clean folder at the queue, is written last and only where given (hw1
    W4), so an entry queued without one keeps the pin's keys; so are `priority` and `light`
    (hw5 F1, F2), each `true`, after it, and `rerun` (build 2, S1), the `gate run` verb's
    opt-in to one rerun of a load flake, kept as `may_rerun`: no other caller asks for it.
    hw6 B1: the class, `cpu` and `mem_mb` (and `jvm`), after `tree` and `top`, from
    `job_class`."""
    real = os.path.realpath(str(repo))
    if not os.path.isdir(real):
        raise GateError(f"no such repo directory: {repo}")
    if not command or not all(isinstance(c, str) and c for c in command):
        raise GateError("a command is wanted after --: gate run <repo> -- <command...>")
    if not isinstance(wall, int) or isinstance(wall, bool) or wall <= 0:
        raise GateError(f"the wall is a positive number of seconds, not {wall!r}")
    if light and wall > LIGHT_WALL:
        raise GateError(f"a light job's wall is at most {LIGHT_WALL} seconds, not {wall}")
    if caller is not None and not _SID.match(str(caller)):
        raise GateError(f"the caller is not a session id: {str(caller)[:40]!r}")
    key = repo_key(real)                # outside the queue's lock: git may take its time
    top = top_level(real)               # build 2, S3: kept only where it is not `real`
    cls = job_class(root, real, command, classes, cpu, mem_mb, jvm, light)

    def build(gid):
        entry = {"id": gid, "repo": real, "command": list(command), "env": dict(env),
                 "locks": [lock_path(p) for p in locks], "wall": wall,
                 "label": label or "", "caller": caller, "queued": now, "key": key,
                 "key_name": os.path.basename(real),
                 "chain": chain_for(root, env, caller, named)}
        if _clean_head(tree):
            entry["tree"] = tree
        if top != real:
            entry["top"] = top
        entry.update(cls)
        entry.update({k: True for k, on in (("priority", priority), ("light", light),
                                            ("may_rerun", rerun)) if on})
        return entry
    return _write_entry(root, now, build)


def _requeue(root, e: dict, now) -> dict:
    """hw5 F3: the rerun of flake `e`, the same command for the same chain or session, marked
    `rerun_of` its id and `flaked` at `now`."""
    def build(gid):
        entry = {k: e.get(k) for k in ENTRY_KEYS}
        entry.update({"id": gid, "queued": now})
        entry.update({k: e[k] for k in ("tree", "top", *CLASS_KEYS, "jvm", "priority", "light")
                      if k in e})
        entry.update({"rerun_of": e["id"], "flaked": now})
        return entry
    return _write_entry(root, now, build)


def _whole(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x > 0


def _class_ok(c) -> bool:
    return isinstance(c, dict) and all(_whole(c.get(k)) for k in CLASS_KEYS)


def entry_class(e: dict) -> dict:
    """hw6 B1: the entry's {cpu, mem_mb}; an entry of an older plugin, with none, reads as the
    default, a light one as `machine.LIGHT_CLASS`."""
    if _class_ok(e):
        return {k: e[k] for k in CLASS_KEYS}
    return dict(machine.LIGHT_CLASS if is_light(e) else machine.DEFAULT_CLASS)


def _repo_names(real: str) -> set:
    """What a `gate.classes` item's `repo` pattern is matched against: the folder, its top
    and its main checkout (the common dir's parent), each as a path and a base name."""
    out = {real, os.path.basename(real)}
    top = top_level(real) if os.path.isdir(real) else real
    common = _common_dir(top) if os.path.isdir(top) else None
    for p in (top, os.path.dirname(common) if common else None):
        if p:
            out |= {p, os.path.basename(p)}
    return out


def _command_forms(command) -> set:
    """A command's words joined by one space, as given and with the path dropped from its
    name, as `helpers.heavy` reads one (hooks._heavy_forms); a check job and a landing's job
    read `make check` (fix 1, A3)."""
    words = [w for w in command or [] if isinstance(w, str)]
    if not words:
        return set()
    out = {" ".join(words), " ".join([os.path.basename(words[0]), *words[1:]])}
    if _check_like(words):
        out.add("make check")
    return out


def _check_like(command) -> bool:
    """Fix 1, A3: a check job's or a landing's command, each a `make check` of its repo."""
    return isinstance(command, list) and (check_worktree(command) is not None
                                          or land_branch(command) is not None)


def class_match(classes, real: str, command) -> dict | None:
    """The first item of the profile's `gate.classes` whose `repo` and `command` patterns
    (fnmatch, case kept) match; None for none."""
    names, forms = None, _command_forms(command)
    for c in classes if isinstance(classes, list) else []:
        if not (isinstance(c, dict) and isinstance(c.get("repo"), str)
                and isinstance(c.get("command"), str) and _class_ok(c)):
            continue
        names = _repo_names(real) if names is None else names
        if any(fnmatch.fnmatchcase(n, c["repo"]) for n in names) \
                and any(fnmatch.fnmatchcase(f, c["command"]) for f in forms):
            return {k: c[k] for k in CLASS_KEYS}
    return None


def history_class(root, real: str, command) -> dict:
    """hw6 B1: from the last `HISTORY` results of this folder and command, newest first, the
    largest of their CPU seconds over their run time, rounded up, and the largest peak plus a
    quarter; each part only where a result holds it. Fix 1, A3: a check job's or a landing's
    reads every check job and landing of its repo's key."""
    rows, key = [], repo_key(real) if _check_like(list(command)) else None
    for n in _result_names(root)[:EST_SCAN]:
        r = _load(result_path(root, n))
        if not r:
            continue
        if (r.get("repo") == real and r.get("command") == list(command)) if key is None \
                else (r.get("key") == key and _check_like(r.get("command"))):
            rows.append(r)
            if len(rows) == HISTORY:
                break
    out = {}
    cpu = max((math.ceil(r["cpu_seconds"] / r["seconds"]) for r in rows
               if _number(r.get("cpu_seconds")) and _number(r.get("seconds"))
               and r["seconds"] > 0), default=None)
    peak = max((r["peak_mb"] for r in rows if _number(r.get("peak_mb"))), default=None)
    if cpu is not None:
        out["cpu"] = max(1, int(cpu))
    if peak is not None:
        out["mem_mb"] = max(1, math.ceil(peak * MEM_PLUS))
    return out


def job_class(root, real: str, command, classes=None, cpu=None, mem_mb=None, jvm=False,
              light=False) -> dict:
    """hw6 B1, each part in turn: `--cpu` and `--mem` (a JVM's heap, plus a quarter); then a
    light job's own class; else the profile's first `gate.classes` match, the folder's
    history, and the default. `jvm` is kept, `true`, where given."""
    out = {}
    if _whole(cpu):
        out["cpu"] = cpu
    if _whole(mem_mb):
        out["mem_mb"] = math.ceil(mem_mb * MEM_PLUS) if jvm else mem_mb
    sources = [machine.LIGHT_CLASS] if light else [
        lambda: class_match(classes, real, command), lambda: history_class(root, real, command),
        machine.DEFAULT_CLASS]
    for src in sources:
        if len(out) == len(CLASS_KEYS):
            break
        got = src() if callable(src) else src
        for k in CLASS_KEYS:
            if k not in out and _whole((got or {}).get(k)):
                out[k] = got[k]
    out = {k: out[k] for k in CLASS_KEYS}
    if jvm:
        out["jvm"] = True
    return out


def _old(e: dict, now) -> bool:
    q = e.get("queued")
    return _number(q) and _number(now) and now - q >= OLD_ENTRY


def pick_order(es: list[dict], now) -> list[dict]:
    """hw5 F1, the order the runner picks in. Build 2, S6: the mark orders the entries of one
    key alone. Between keys the order is the pin's, first queued first: each key keeps the
    places its entries hold by counter, and fills them in its own order, an entry queued
    `OLD_ENTRY` or more ago first, oldest first, then those marked `priority`, then the rest,
    each first queued first."""
    def rank(e):
        if _old(e, now):
            return (0, 0, e["queued"], _counter(e["id"]))
        return (1, 0 if e.get("priority") is True else 1, 0, _counter(e["id"]))
    fifo = sorted(es, key=lambda e: _counter(e["id"]))
    keys = [entry_key(e) for e in fifo]
    mine: dict = {}
    for k, e in zip(keys, fifo):
        mine.setdefault(k, []).append(e)
    turns = {k: iter(sorted(v, key=rank)) for k, v in mine.items()}
    return [next(turns[k]) for k in keys]


def is_light(e: dict) -> bool:
    return e.get("light") is True


def open_entry(root, repo, command, tree, alive=_alive) -> tuple[dict, str] | None:
    """hw1 W4: (the oldest open entry of this folder, its state) whose head's tree at its queue
    is `tree` and whose command is `command`, a check job's matched by its worktree alone, since
    the runner's own argv may differ between installs; None for no tree (a dirty folder) or no
    such entry. The state is `running` or `queued position <n>`."""
    if not _clean_head(tree):
        return None
    real = repo_path(repo)
    where = check_worktree(command)
    running = _running_ids(root, alive)
    for e in entries(root):
        if e.get("tree") != tree or repo_path(e.get("repo")) != real \
                or result_path(root, e["id"]).exists():
            continue
        same = repo_path(check_worktree(e.get("command"))) == repo_path(where) \
            if where is not None else e.get("command") == list(command)
        if same:
            state = "running" if e["id"] in running \
                else f"queued position {position(root, e['id'], alive)}"
            return e, state
    return None


def entries(root, strict: bool = False) -> list[dict]:
    """The queue, oldest (lowest counter) first; a file that does not parse is skipped. With
    `strict` (hw6 B6) a queue, a gate folder or an entry file (fix 1, F3) that cannot be read
    or parsed raises GateError."""
    out = []
    if strict:
        _listdir(gate_dir(root), strict)
    names = _listdir(_queue(root), strict)
    for name in names:
        stem = name[:-5] if name.endswith(".json") else ""
        if not ID.match(stem):
            continue
        e = _load(_queue(root) / name, strict)
        if e is not None and e.get("id") == stem:
            out.append(e)
    return sorted(out, key=lambda e: _counter(e["id"]))


def runner_info(root, strict: bool = False) -> dict | None:
    return _load(gate_dir(root) / "runner.json", strict)


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


def running_grants(root, alive=_alive, strict: bool = False) -> list[dict]:
    """Fix 1, A5: each running job's grant, as the live runner's runner.json names it, else
    its entry's class, else the default; [] with no live runner."""
    r = runner_info(root, strict)
    if not (r and alive(r.get("pid"))):
        return []
    run = r.get("running") if isinstance(r.get("running"), list) else []
    grant = {x["id"]: x.get("grant") for x in run if isinstance(x, dict) and "id" in x}
    byid = {e["id"]: e for e in entries(root, strict)}
    out = []
    for gid, _ in _pairs(r):
        g = grant.get(gid)
        out.append({k: g[k] for k in CLASS_KEYS} if _class_ok(g) else entry_class(byid.get(gid, {})))
    return out


def _running_ids(root, alive=_alive, strict: bool = False) -> list[str]:
    r = runner_info(root, strict)
    return [gid for gid, _ in _pairs(r)] if r and alive(r.get("pid")) else []


def position(root, gid: str, alive=_alive, now=None) -> int:
    """The place among the entries not running in the pick's order (1 is next, hw5 F1); 0
    when not queued."""
    run = _running_ids(root, alive)
    now = time.time() if now is None else now
    ids = [e["id"] for e in pick_order([e for e in entries(root) if e["id"] not in run], now)]
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
    and not trusted from the entry, so an older entry's spelling compares too.
    hw5 F2: a light entry is held only by an open entry of its key in its own worktree, and
    holds only that worktree of its key against the entries after it. Build 2, S3: a worktree
    is `worktree(e)`, its folder's top, whatever folder the entry named. S4: a light entry is
    held while a landing of its key is queued or running, since a landing reads and removes a
    worktree of its repo."""
    keys, trees, lands = {}, {}, {}
    for x in running:
        keys.setdefault(entry_key(x), key_name(x))
        trees.setdefault((entry_key(x), worktree(x)), key_name(x))
    for x in [*running, *es]:
        if land_branch(x.get("command")) is not None:
            lands.setdefault(entry_key(x), key_name(x))
    named = _named(running)
    for e in es:
        k = entry_key(e)
        t = (k, worktree(e))
        path = _locked(e) or next((p for p in _locks(e) if _is_named(p, named)), None)
        if path:
            yield e, ("lock", path)
        elif is_light(e) and (t in trees or k in lands):
            yield e, ("key", trees.get(t) or lands[k])
        elif not is_light(e) and (k in keys or t in trees):
            yield e, ("key", keys.get(k) or trees[t])
        else:
            yield e, None
        trees.setdefault(t, key_name(e))
        if not is_light(e):
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
    `last` is the last start. hw6 R5: the load is no longer read here; it is a guard of
    `_admit`, bounded, and binds a first start too."""
    most = cfg.get("max_running", MAX_RUNNING)
    if count >= most:
        return ("running", count, most)
    left = START_SETTLE - (now - last) if isinstance(last, (int, float)) else 0
    return ("settle", left) if left > 0 else None


def _bar(cfg: dict, fx, e: dict, running: list[dict], last, now: float, memo=None):
    """What bars entry `e`, which nothing holds, from starting now, or None. hw5 F3: nothing
    starts beside a running rerun, and a rerun starts only with nothing running. hw5 F2: a
    light entry, and a light one running, are not counted against `max_running`; the settle
    holds every entry and binds only while one runs (the load is `_admit`'s, hw6 R5)."""
    rerun = next((x for x in running if x.get("rerun_of")), None)
    if rerun is not None:
        return ("rerun", rerun.get("id"))
    if not running:
        return None
    if e.get("rerun_of"):
        return ("alone", len(running))
    count = 0 if is_light(e) else sum(1 for x in running if not is_light(x))
    memo = {} if memo is None else memo
    if count not in memo:
        memo[count] = _over(cfg, fx, count, last, now)
    return memo[count]


def self_argv() -> list[str]:
    """This interpreter (never PATH), `-I` and the launcher beside this package, its bytecode
    under the launcher's prefix (design/04 §3): the head of every argv that runs this code."""
    runner = Path(__file__).resolve().parent.parent / "agentik-session"
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.environ.get("HOME", ""), ".cache")
    # The launcher's expression, never sys.pycache_prefix: Apple's 3.9 sets its own by default.
    prefix = os.path.join(cache, "agentik", "pycache")
    return [sys.executable, "-I", "-X", "pycache_prefix=" + prefix, str(runner)]


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
    argv = [*self_argv(), "gate", "serve", "--root", str(root)]
    with open(g / "runner.log", "ab") as log:
        popen(argv, cwd=str(g), env={**os.environ, **install.parent_record()}, stdin=subprocess.DEVNULL, stdout=log,
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


def _snapshot(paths) -> dict:
    """hw6 B3, B4: the machine for a start, the volumes of `paths` read."""
    return machine.snapshot(paths)


def _sample(pgids) -> dict:
    """hw6 B2: {pgid: MB} of each running job's group."""
    return machine.group_rss_mb(pgids)


def _reap_child(proc) -> tuple[int | None, float | None]:
    """One look at a child that never waits (hw1 W2): (its code, as `Popen.poll` gives it, or
    None while it runs; its user plus system seconds from `wait4`, its waited-for descendants
    counted, or None). A child that is no `Popen` of this process, or that something else
    reaped, is polled as before and has no seconds."""
    if not isinstance(proc, subprocess.Popen) or proc.returncode is not None:
        return proc.poll(), None
    try:
        pid, status, usage = os.wait4(proc.pid, os.WNOHANG)
    except ChildProcessError:
        return proc.poll(), None
    if pid == 0:
        return None, None
    proc.returncode = os.waitstatus_to_exitcode(status)
    return proc.returncode, round(usage.ru_utime + usage.ru_stime, 2)

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
    load: Callable[[], float] = lambda: _load_avg()     # each read late, so a test sets one
    cores: Callable[[], int | None] = os.cpu_count
    env: dict = field(default_factory=lambda: dict(os.environ))
    idle: float = IDLE
    poll: float = POLL
    grace: float = GRACE
    pid: int = field(default_factory=os.getpid)
    head: Callable[[str], str | None] = _head
    loads: Callable[[], tuple] = os.getloadavg          # the three, for the result (gl1 R3)
    dirty: Callable[[str], int | None] = _dirty
    tree: Callable[[str], str | None] = _tree           # the head's tree at a clean start (hw1)
    reap: Callable = _reap_child                        # (code, cpu seconds) of one look (hw1)
    snapshot: Callable = lambda paths: _snapshot(paths)  # the machine for a start (hw6)
    sample: Callable = lambda pgids: _sample(pgids)      # {pgid: MB} of the running (hw6 B2)



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
    cut: str | None = None              # CUT_WALL or CUT_CALLER, once a cut began


@dataclass
class _Set:
    """The runner's memory: its children, the id it is about to spawn, its last start, and
    `seen`, when it first saw each head locked."""
    since: float
    running: list = field(default_factory=list)
    starting: str | None = None
    last_start: float | None = None
    seen: dict = field(default_factory=dict)
    budget_since: dict = field(default_factory=dict)    # hw6 B3: id -> first held by it
    snaps: dict = field(default_factory=dict)           # folder -> (at, snapshot)
    last_sample: float | None = None
    holds: dict | None = None                           # what holds.json was last written as


def _runner_write(root, fx: Fx, s: _Set) -> None:
    run = [{"id": c.e["id"], "pgid": c.proc.pid, "grant": c.e.get("grant")} for c in s.running]
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
    """Results past KEEP leave; so do closed lines past theirs, in this pass (packet in3 R8)."""
    try:
        from . import lines
        lines.prune(root, now)
    except Exception:                                   # noqa: BLE001 - the gate's own pass goes on
        pass
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


def _clean_head(h) -> str | None:
    return h if isinstance(h, str) and _HEAD.match(h) else None


def _str_or_none(x) -> str | None:
    return x if isinstance(x, str) and x else None


def _loads_read(fx: Fx, gid: str, side: str) -> list | None:
    """The three load averages, each rounded to two places; None for a read that raised (one
    line in the runner's log) or is not three finite numbers of zero or more."""
    try:
        x = fx.loads()
    except Exception as err:                            # noqa: BLE001 (a null, never a job's)
        fx.log(f"gate {gid}: the load at its {side} was not read: {err}")
        return None
    return _three(x)


def _three(x) -> list | None:
    if not isinstance(x, (tuple, list)) or len(x) != 3:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and 0 <= v < float("inf") for v in x):
        return None
    return [round(float(v), 2) for v in x]


def _dirty_read(fx: Fx, gid: str, repo, side: str) -> int | None:
    """The folder's dirty count; None for a read that raised (one line in the runner's log)
    or is no count."""
    try:
        n = fx.dirty(repo)
    except Exception as err:                            # noqa: BLE001 (a null, never a job's)
        fx.log(f"gate {gid}: the dirt at its {side} was not read: {err}")
        return None
    return _count(n)


def _count(n) -> int | None:
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < float("inf")


def _tree_read(fx: Fx, gid: str, repo) -> str | None:
    """The head's tree; None for a read that raised (one line in the runner's log)."""
    try:
        return _clean_head(fx.tree(repo))
    except Exception as err:                            # noqa: BLE001 (a null, never a job's)
        fx.log(f"gate {gid}: the tree at its start was not read: {err}")
        return None


def _measures(e: dict) -> dict:
    """hw1 W2: the result's `waited`, `cpu_seconds` and `tree`, from what the runner kept on
    the entry in its memory, each null where it was not read; hw6 R6: `peak_mb`, null where no
    sample was taken, and the class as granted, `cpu` and `mem_mb` (an entry not started,
    its class)."""
    grant = e.get("grant") if _class_ok(e.get("grant")) else entry_class(e)
    return {"waited": e.get("waited") if _number(e.get("waited")) else None,
            "cpu_seconds": e.get("cpu_seconds") if _number(e.get("cpu_seconds")) else None,
            "tree": _clean_head(e.get("start_tree")),
            "peak_mb": e.get("peak_mb") if _number(e.get("peak_mb")) else None,
            "cpu": grant["cpu"], "mem_mb": grant["mem_mb"]}


def _machine(e: dict) -> dict:
    """The result's `load`, `beside` and `dirty` from what the runner read into the entry in
    its memory: each side null where it was not read, `beside` null when it was not."""
    load, dirty = e.get("load"), e.get("dirty")
    load, dirty = (x if isinstance(x, dict) else {} for x in (load, dirty))
    beside = e.get("beside")
    ok = isinstance(beside, list) and all(isinstance(g, str) for g in beside)
    return {"load": {k: _three(load.get(k)) for k in SIDES},
            "beside": list(beside) if ok else None,
            "dirty": {k: _count(dirty.get(k)) for k in SIDES}}


def make_env(env) -> list | None:
    """The names of MAKE_ENV set in `env`, sorted; None where `env` is no mapping."""
    return sorted(k for k in MAKE_ENV if k in env) if isinstance(env, dict) else None


def _marks(e: dict) -> dict:
    """hw5 F3, F4: the result's `rerun_of` and `dropped`, each only where it applies."""
    out = {}
    if isinstance(e.get("rerun_of"), str) and ID.match(e["rerun_of"]):
        out["rerun_of"] = e["rerun_of"]
    if e.get("dropped") is True:
        out["dropped"] = True
    for k in ("over", "guard_unread"):                  # hw6 B4, R6
        if isinstance(e.get(k), str) and e[k]:
            out[k] = e[k]
    w = e.get("would_hold")                             # hw6 B7: `observe`'s
    if isinstance(w, dict) and w:
        out["would_hold"] = dict(w)
    return out


def _finish(root, fx: Fx, cfg: dict, e: dict, rc: int, started, ended, cut,
            note: str | None = None, flake: bool | None = None) -> dict:
    """Write result.json last, atomically; drop the entry; tell the inbox and ntfy. hw5 F3:
    a red whose stop line was found (`flake` not None) keeps `RED_KEYS`; a flake's rerun is
    queued before its result is written, which names it, and no line is sent for it."""
    gid = e["id"]
    d = entry_dir(root, gid)
    _mkdir(d)
    if note is not None:
        with _open_log(d / "log") as log:
            log.write(f"gate {gid}: {note}\n".encode())
    seconds = round(ended - started, 1) if isinstance(started, (int, float)) else None
    result = {"id": gid, "repo": e.get("repo"), "command": e.get("command"), "exit": rc,
              "started": started, "ended": ended, "seconds": seconds,
              "log": str(d / "log"), "caller": e.get("caller"), "cut": cut,
              "head": _clean_head(e.get("head")), "key": _str_or_none(e.get("key")),
              **_machine(e), "make_env": make_env(e.get("env"))}
    chain = e.get("chain")
    if isinstance(chain, str) and CHAIN_RE.match(chain):     # nw2 R1: kept, the pin's keys first
        result.update({"chain": chain, "label": e.get("label") or ""})
    result.update(_measures(e))                               # hw1 W2: after every pin's key
    if flake is not None:                     # hw5 F3: a red whose second test was asked
        ceiling, along = e.get("ceiling"), e.get("alongside")
        result.update({"ceiling": ceiling if _number(ceiling) else None,
                       "alongside": [g for g in along if isinstance(g, str)]
                       if isinstance(along, list) else None})
    if flake:
        try:
            rerun = _requeue(root, e, ended)
        except OSError as err:
            fx.log(f"gate {gid}: a load flake, its rerun not queued: {err}")
            flake = False
        else:
            result.update({"flake": FLAKE, "rerun": rerun["id"]})
    result.update(_marks(e))
    _write_private(result_path(root, gid), json.dumps(result, indent=1) + "\n")
    if flake:                                         # its line waits for the rerun's (F3)
        _unlink(_queue(root) / f"{gid}.json")
        _unlink(cancel_path(root, gid))
        _prune(root, ended)
        return result
    _tell(root, fx, cfg, result, lambda: (_unlink(_queue(root) / f"{gid}.json"),
                                          _unlink(cancel_path(root, gid))))
    _prune(root, ended)
    return result


def _tell(root, fx: Fx, cfg: dict, result: dict, between) -> None:
    """A result's line to its chain's inbox, then `between()`, then to its caller's session's
    inbox where it has no chain, then to ntfy."""
    gid = result["id"]
    caller = result.get("caller")
    if "chain" in result:
        # Brief 2, R2: a chain's line is written while its entry is still queued, so a
        # `wait_chain` that reads no open job then reads the line, and never answers 2 in
        # between. A runner that dies here leaves the entry beside its result, which the
        # next one only drops (`_recover`, `_step`): the line is not written twice. One that
        # dies after the result and before the line leaves no line, as before this order.
        try:
            inbox_write(root, caller, result)
        except OSError as err:
            fx.log(f"gate {gid}: the inbox of chain {result['chain']} was not written: {err}")
    between()
    if "chain" not in result and isinstance(caller, str) and caller:
        try:
            inbox_write(root, caller, result)
        except OSError as err:
            fx.log(f"gate {gid}: the inbox of {caller} was not written: {err}")
    err = notify(result, cfg, fx.post)
    if err:
        fx.log(err)


def _left(root, e: dict, now) -> None:
    """Build 2, S2: the result a rerun taken out of the queue leaves under its own id, exit
    130, `flake: load, not rerun` and `rerun_of` the first, so its id is never unknown; a
    reader takes the first's result for it (`resolved`). One already there is kept."""
    gid = e["id"]
    if result_path(root, gid).exists():
        return
    _mkdir(entry_dir(root, gid))
    result = {"id": gid, "repo": e.get("repo"), "command": e.get("command"),
              "exit": CALLER_EXIT, "started": None, "ended": now, "seconds": None,
              "log": str(entry_dir(root, gid) / "log"), "caller": e.get("caller"),
              "cut": CUT_CALLER, "head": None, "key": _str_or_none(e.get("key")),
              "flake": NOT_RERUN, "rerun_of": e.get("rerun_of")}
    _write_private(result_path(root, gid), json.dumps(result, indent=1) + "\n")


def resolved(root, r):
    """Build 2, S2: a result as a wait or a drop answers it: for what a rerun taken out left
    (`_left`), the first's result, where it is still there; else `r`."""
    of = r.get("rerun_of") if isinstance(r, dict) and r.get("flake") == NOT_RERUN else None
    first = _load(result_path(root, of)) if isinstance(of, str) and ID.match(of) else None
    return first if first is not None else r


def _not_rerun(root, fx: Fx, cfg: dict, e: dict) -> dict | None:
    """hw5 F3: rerun `e` has not started `RERUN_WAIT` after its flake, or is dropped (build 2,
    S5): the rerun leaves its result (`_left`, S2) first, then the flake's result reads `flake:
    load, not rerun` as its line is sent and the rerun is taken out of the queue; a pass that
    finds the first still `load` beside that result does it all again (hw5b D1). The first's
    result, or None."""
    gid = e["id"]
    of = e.get("rerun_of")
    first = _load(result_path(root, of)) if isinstance(of, str) and ID.match(of) else None
    _left(root, e, fx.now())
    def take():
        _unlink(_queue(root) / f"{gid}.json")
        _unlink(cancel_path(root, gid))
    if first is None or first.get("flake") != FLAKE:
        take()
        return first
    first["flake"] = NOT_RERUN
    def mark():
        _write_private(result_path(root, first["id"]), json.dumps(first, indent=1) + "\n")
        take()
    _tell(root, fx, cfg, first, mark)
    return first


def grant_env(e: dict) -> dict:
    """hw6 B5: the job's environment, its id, and its class as granted: `AGENTIK_CPUS`,
    `AGENTIK_MEM_MB`, and `GOMAXPROCS` where the job's environment holds none."""
    g = e.get("grant") if _class_ok(e.get("grant")) else entry_class(e)
    env = {**(e.get("env") or {}), JOB_MARK: e["id"], "AGENTIK_CPUS": str(g["cpu"]),
           "AGENTIK_MEM_MB": str(g["mem_mb"])}
    env.setdefault("GOMAXPROCS", str(g["cpu"]))
    return env


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
    if not (_queue(root) / f"{gid}.json").exists() or drop_path(root, gid).exists():
        # hw5 F4, build 2 S7: a drop in hand after the pick; not run, and the drop finishes it
        s.starting = None
        _runner_write(root, fx, s)
        return
    # Packet FW2 R2: the head before the spawn, since a queued entry's repo may move while it
    # waits; kept on the entry in memory for `_finish`. A head that raises reads None.
    try:
        e["head"] = _clean_head(fx.head(e["repo"]))
    except Exception:
        e["head"] = None
    # Packet gl1 R1: the machine just before the spawn, the dirt first so that the load is the
    # last read; neither moves `started`. The end sides are read once the child is reaped.
    e["beside"] = [c.e["id"] for c in s.running]
    e["dirty"] = {"start": _dirty_read(fx, gid, e["repo"], "start"), "end": None}
    e["load"] = {"start": _loads_read(fx, gid, "start"), "end": None}
    # hw1 W2: the head's tree where the folder was clean at the start, read after its dirt.
    e["start_tree"] = _tree_read(fx, gid, e["repo"]) if e["dirty"]["start"] == 0 else None
    started = fx.now()
    q = e.get("queued")
    e["waited"] = round(max(0.0, started - q), 1) if _number(q) and _number(started) else None
    with _open_log(d / "log") as log:
        log.write(f"gate {gid}: {e['repo']}: {shlex.join(e['command'])}\n".encode())
        log.flush()
        try:
            p = fx.popen(e["command"], cwd=e["repo"], env=grant_env(e),
                         stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True, close_fds=True)
        except (OSError, ValueError, subprocess.SubprocessError) as err:
            log.write(f"gate {gid}: cannot start: {err}\n".encode())
            p = None
    s.starting = None
    if p is None:
        _close(root, fx, cfg, e, 127, started, None, s, reaped=False)
        return
    # hw5 F3: what a flake's second test reads, kept on the entry in memory: the ceiling at
    # the start, and every job that ran beside it, at its start or after.
    e["ceiling"] = _ceiling(cfg, fx)
    e["alongside"] = list(e["beside"])
    for c in s.running:
        c.e.setdefault("alongside", []).append(gid)
    s.running.append(_Child(e, p, started))
    s.last_start = started
    _runner_write(root, fx, s)


def _close(root, fx: Fx, cfg: dict, e: dict, rc: int, started, cut, s: _Set,
           reaped: bool = True) -> None:
    """Close a started entry: the end sides of its load and dirt read after `ended`, when a
    child was reaped (a 127 had none, so its end sides stay null)."""
    ended = fx.now()
    if reaped:
        e["load"]["end"] = _loads_read(fx, e["id"], "end")
        e["dirty"]["end"] = _dirty_read(fx, e["id"], e["repo"], "end")
    with _open_log(entry_dir(root, e["id"]) / "log") as log:
        log.write(f"gate {e['id']}: exit {rc} in {round(ended - started)} s\n".encode())
    flake = is_flake(e, rc, entry_dir(root, e["id"]) / "log") if reaped and cut is None \
        else None
    _finish(root, fx, cfg, e, rc, started, ended, cut, flake=flake)
    _runner_write(root, fx, s)


def _tail(path, most: int = FLAKE_TAIL) -> bytes:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - most))
            return fh.read()
    except (OSError, TypeError, ValueError):
        return b""


def is_flake(e: dict, rc, log) -> bool | None:
    """hw5 F3: whether a red closed by its own exit, not cut, is a load flake; None where the
    first test fails, so the second is not asked. Never a landing's job, never a rerun, and
    never a job the `gate run` verb did not queue (build 2, S1: its red is its result). Its
    log's last `FLAKE_TAIL` bytes hold a time bound's stop line, or its exit is a `timeout`'s
    124, and none of `NOT_FLAKE`; and the 1-minute load at its start was at or over its
    ceiling (ruling 4's word for over), or another job ran beside it."""
    if rc == 0 or not isinstance(rc, int) or isinstance(rc, bool) or e.get("rerun_of") \
            or e.get("may_rerun") is not True or land_branch(e.get("command")) is not None:
        return None
    tail = _tail(log)
    stop = rc == 124 or any(s in tail for s in STOP_LINES) or PYTEST_TIMEOUT.search(tail)
    if not stop or any(s in tail for s in NOT_FLAKE):
        return None
    load = (e.get("load") or {}).get("start") if isinstance(e.get("load"), dict) else None
    one, ceiling = (load[0] if isinstance(load, list) and load else None), e.get("ceiling")
    loaded = _number(one) and _number(ceiling) and one >= ceiling
    return bool(loaded or e.get("alongside"))


def _cut_reaped(c: _Child, fx: Fx) -> bool:
    """Whether a child the cut signalled is gone, its seconds kept where `wait4` gave them."""
    code, cpu = fx.reap(c.proc)
    if code is not None:
        c.e["cpu_seconds"] = cpu
    return code is not None


def _peaks(fx: Fx, s: _Set) -> None:
    """hw6 B2: every `SAMPLE_EVERY` seconds one sample of the running jobs' groups, each
    job's `peak_mb` the largest sum seen; a sample that fails is skipped, never raised."""
    if not s.running:
        return
    now = fx.now()
    if s.last_sample is not None and now - s.last_sample < SAMPLE_EVERY:
        return
    s.last_sample = now
    try:
        got = fx.sample([getattr(c.proc, "pid", None) for c in s.running])
    except Exception as err:                            # noqa: BLE001 (a sample is skipped)
        fx.log(f"gate: a sample of the running groups failed: {err}")
        return
    for c in s.running:
        mb = got.get(getattr(c.proc, "pid", None)) if isinstance(got, dict) else None
        if _number(mb):
            was = c.e.get("peak_mb")
            c.e["peak_mb"] = max(mb, was) if _number(was) else mb


def _reap(root, fx: Fx, cfg: dict, s: _Set) -> bool:
    """One look at each child, never waiting on any: a finish kills what its group left
    running, since the key frees here and the next of that key would overlap it, and closes
    it with the command's own code; at its wall, the group's SIGTERM, then at the grace SIGKILL (the child is not polled between them, so its
    group's id stays its own), then 124 once it is gone or a second grace has passed. True
    when one closed."""
    closed = False
    _peaks(fx, s)
    for c in list(s.running):
        now, code, cut = fx.now(), None, None
        if c.term_at is None:
            code, c.e["cpu_seconds"] = fx.reap(c.proc)
            if code is not None:
                code = code if code >= 0 else 128 - code
                _signal_group(c.proc.pid, signal.SIGKILL, fx)
            elif cancel_path(root, c.e["id"]).exists() or now - c.started >= (
                    c.e["wall"] if isinstance(c.e.get("wall"), int) else WALL):
                c.cut = CUT_CALLER if cancel_path(root, c.e["id"]).exists() else CUT_WALL
                c.term_at = now
                if not _signal_group(c.proc.pid, signal.SIGTERM, fx):
                    c.kill_at = now
        elif c.kill_at is None:
            if now - c.term_at >= fx.grace:
                _signal_group(c.proc.pid, signal.SIGKILL, fx)
                c.kill_at = now
        elif _cut_reaped(c, fx) or now - c.kill_at >= fx.grace:
            cut = c.cut or CUT_WALL
            code = CALLER_EXIT if cut == CUT_CALLER else 124
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
    busy = {x["id"] for x in running} | _sweep_drops(root)     # build 2, S7: in a drop's hand
    es = [e for e in entries(root) if e["id"] not in busy]
    for e in es:
        if result_path(root, e["id"]).exists():       # a runner died after its result
            if (_load(result_path(root, e["id"])) or {}).get("flake") == NOT_RERUN:
                _not_rerun(root, fx, cfg, e)          # hw5b D1: a take-out cut short
            else:
                _unlink(_queue(root) / f"{e['id']}.json")
            return True
    _sweep_marks(root)
    for e in es:                                      # fw5 R4: a marked entry never starts
        if cancel_path(root, e["id"]).exists():
            now = fx.now()
            s.seen.pop(e["id"], None)
            _finish(root, fx, cfg, e, CALLER_EXIT, now, now, CUT_CALLER,
                    note="its caller left the wait; not run")
            return True
    now = fx.now()
    for e in es:                                      # hw5 F3: a rerun not started in time
        if _number(e.get("flaked")) and now - e["flaked"] >= RERUN_WAIT:
            s.seen.pop(e["id"], None)
            _not_rerun(root, fx, cfg, e)
            return True
    es = pick_order(es, now)                          # hw5 F1: the head is the pick's
    if not es:
        return False
    head, seen = es[0], s.seen
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
    memo: dict = {}                                   # one load read a pass, as at the pin
    _forget(s, {e["id"] for e in es})
    holds, behind = {}, None
    for e, why in _holds(es, running):
        if why is not None or _bar(cfg, fx, e, running, s.last_start, now, memo) is not None:
            continue
        if behind is not None and not e.get("rerun_of"):     # B3; fix 1, F2: a rerun is hw5's
            holds[e["id"]] = {"what": f"the budget, behind {behind[0]}", "since": behind[1]}
            continue
        held = _admit(root, fx, cfg, e, s, now, memo)
        if held is None:
            _write_holds(root, s, holds)
            _start(root, fx, cfg, e, s)
            return True
        holds[e["id"]] = {"what": "; ".join(w for _, w, _ in held),
                          "since": min(t for _, _, t in held)}
        if any(k == "disk" for k, _, _ in held):      # fix 1, F1: its reader names the largest
            holds[e["id"]]["disk"] = True
        first = next((t for k, _, t in held if k == "budget"), None)
        if first is not None and now - first >= BUDGET_PASS:
            behind = (e["id"], first)
    _write_holds(root, s, holds)
    return False


def _forget(s: _Set, ids: set) -> None:
    """The runner's memory of the budget's holds, kept only for the entries still queued; a
    guard keeps none, since its bound counts from the entry's `queued` (fix 1, A1)."""
    for k in [k for k in s.budget_since if k not in ids]:
        del s.budget_since[k]


def _write_holds(root, s: _Set, holds: dict) -> None:
    """holds.json, what holds each entry the budget or a guard holds and since when, which
    `status` reads; written only when it moved."""
    if holds == s.holds:
        return
    try:
        _write_private(gate_dir(root) / HOLDS, json.dumps(holds) + "\n")
    except OSError:                                     # status then names no hold
        return
    s.holds = dict(holds)


def _machine_config(cfg: dict, fx: Fx) -> dict:
    """What `machine.budget` reads of the gate's profile: the gate's own ceiling (`_ceiling`),
    and the reserve and the floor where set (hw6 R2)."""
    out = {"load_ceiling": _ceiling(cfg, fx)}
    out.update({k: cfg[k] for k in ("mem_reserve_mb", "disk_floor_gb") if k in cfg})
    return out


def _snap_for(fx: Fx, s: _Set, folder, now) -> dict:
    """The machine for a start in `folder`, its volume named `job` (R4); one read a folder per
    `SNAP_EVERY`; a read that raises is an empty snapshot, every part then unread."""
    hit = s.snaps.get(folder)
    if hit is not None and 0 <= now - hit[0] < SNAP_EVERY:
        return hit[1]
    try:
        snap = fx.snapshot({"job": folder, "gocache": None})
    except Exception as err:                            # noqa: BLE001 (each part unread)
        fx.log(f"gate: the machine was not read: {err}")
        snap = None
    snap = snap if isinstance(snap, dict) else {}
    s.snaps[folder] = (now, snap)
    return snap


def _admit(root, fx: Fx, cfg: dict, e: dict, s: _Set, now, memo):
    """hw6 B3, B4, B7: None where `e` may start now, its grant kept on it, else what holds it,
    [(part, why, since)]. The budget (`grant`) holds under `hold` until it fits. Fix 1, A1: a
    guard holds an entry only while less than its bound (`gate.<guard>_hold_max`) has passed
    since the entry's `queued`, then is passed over and named in `over`; the time is on disk,
    so a restart starts no hold over. A part whose reading is a fault holds nothing and is
    named in `guard_unread`. Under `observe` the budget, the pressure and the disk hold
    nothing and `would_hold` names each with its reading at this pass (F6); the load holds
    under both. A rerun is left to hw5's bars by the budget and the load (F2), and a light
    entry by the load (A2). The grant is the class clamped to the budget (N4). The runner
    reads no disk consumer: the reader that prints the hold does (F1)."""
    gid = e["id"]
    snap = dict(_snap_for(fx, s, e.get("repo"), now))
    if "load" not in memo:
        memo["load"] = _load_read(fx)
    x = memo["load"]
    snap["load"] = None if x is None else [x, x, x]
    grants = [c.e.get("grant") if _class_ok(c.e.get("grant")) else entry_class(c.e)
              for c in s.running]
    cls = entry_class(e)
    parts = machine.budget(snap, grants, _machine_config(cfg, fx), cls, volume="job")["parts"]
    mode = cfg.get("budget", "hold")
    q = e.get("queued")
    age = now - q if _number(q) and _number(now) else None
    skip = {"grant", "load"} if e.get("rerun_of") else {"load"} if is_light(e) else set()
    held, unread, over, would = [], [], [], {}
    for name in machine.PARTS:
        part, word = parts[name], "budget" if name == "grant" else name
        if name in skip:
            continue
        if part["state"] == "unread":
            unread.append(word)
            continue
        if part["state"] != "held":
            continue
        if name != "load" and mode != "hold":
            would[word] = part["why"]
            continue
        if name == "grant":
            held.append((word, part["why"], s.budget_since.setdefault(gid, now)))
            continue
        if age is None or age >= cfg.get(f"{name}_hold_max", HOLD_MAX):
            over.append(word)
            continue
        held.append((word, part["why"], q))
    if held:
        return held
    got = parts["grant"]["reading"]
    e["grant"] = {"cpu": max(1, int(round(got["cpu"]))),
                  "mem_mb": max(1, int(round(got["mem_mb"])))} \
        if isinstance(got, dict) and _number(got.get("cpu")) and _number(got.get("mem_mb")) \
        else cls
    e.update({k: ", ".join(v) for k, v in (("over", over), ("guard_unread", unread)) if v})
    if would:
        e["would_hold"] = would
    return None


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

def _start_dirt(d):
    v = d.get("start") if isinstance(d, dict) else d
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def mark_text(result: dict) -> str:
    """hw5 F5: `dropped; `, `flake: load; `, `flake: load, not rerun; ` and `rerun of <id>; `,
    each where the result or its inbox line holds it; "" for an older one."""
    out = "dropped; " if result.get("dropped") is True else ""
    flake = result.get("flake")
    out += f"flake: {flake}; " if flake in (FLAKE, NOT_RERUN) else ""
    of = result.get("rerun_of")
    out += f"rerun of {of}; " if isinstance(of, str) and ID.match(of) else ""
    for k, word in (("over", "over"), ("guard_unread", "guard unread")):     # hw6 B4
        v = result.get(k)
        out += f"{word}: {v[:40]}; " if isinstance(v, str) and v else ""
    return out


def wait_line(result: dict) -> str:
    """The pin's line; a chain's (design/31 item 10) adds the head, the dirt when it is not
    0 and the label cut to `LABEL_MOST` bytes, before the log."""
    head = (f"gate {result.get('id')} {result.get('repo')}: exit {result.get('exit')} in "
            f"{_minutes(result.get('seconds'))} min; ")
    if "chain" in result:
        h, dirt, lab = _clean_head(result.get("head")), _start_dirt(result.get("dirty")), \
            _label(result.get("label"))
        head += f"head {h[:7] if h else '?'}; "
        head += f"dirty {dirt}; " if dirt else ""
        head += f"{lab}; " if lab else ""
    head += mark_text(result)                                 # hw5 F5
    x = result.get("exit")
    fail = fail_text(result.get("log"), result.get("id")) if x != 0 or isinstance(x, bool) \
        else None
    head += f"fail {fail}; " if fail else ""                  # hw1 W5
    return head + f"log {result.get('log')}"


def log_lines(path) -> list[str]:
    """The lines of a job log's last 64 KiB, the first, maybe cut, dropped where the read did
    not start at the top; [] where it is no regular file or cannot be read. Opened so that a
    FIFO cannot block and a link is not followed, since a hook reads it (hw1 W5)."""
    if not isinstance(path, str) or not path:
        return []
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except (OSError, ValueError):
        return []
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return []
        start = max(0, st.st_size - 65536)
        os.lseek(fd, start, os.SEEK_SET)
        data = os.read(fd, 65536)
    except OSError:
        return []
    finally:
        os.close(fd)
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if start and lines else lines


def fail_text(path, gid) -> str | None:
    """hw1 W5: the log's last line that reads as a failure (`FAIL`, `--- FAIL`, `ERROR`, `make:
    ***`, an `AssertionError` or an `Error:` line), the gate's own lines aside, as a label is
    held and cut to `FAIL_MOST` bytes; None where there is none. A line that is not make's own
    is taken before make's, and make's only where there is no other (hw1 review 1, R3)."""
    skip = f"gate {gid}: "
    made = None
    for ln in reversed(log_lines(path)):
        t = ln.strip()
        if t and not t.startswith(skip) and FAIL_LINE.search(t):
            if not MAKE_FAIL.match(t):
                return _json_cut(_label(t, FAIL_MOST), FAIL_MOST) or None
            made = made or t
    return _json_cut(_label(made, FAIL_MOST), FAIL_MOST) or None if made else None


def _json_cut(text: str, most: int) -> str:
    """`text` cut on a character so that its JSON form, the hook's output, adds at most `most`
    bytes: a character JSON escapes counts as its escape (hw1 W5)."""
    out, n = [], 0
    for c in text:
        n += len(json.dumps(c)) - 2
        if n > most:
            break
        out.append(c)
    return "".join(out).rstrip()


MAKES = ("make", "gmake")
SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
MAKE_VALUE = frozenset("CEfIoW")         # make's short options whose value follows
MAKE_NUMBER = frozenset("jl")            # and those whose value, a number, may follow
MAKE_LONG = frozenset(("--directory", "--eval", "--file", "--makefile", "--include-dir",
                       "--old-file", "--assume-old", "--what-if", "--new-file", "--assume-new"))
MAKE_LONG_NUMBER = frozenset(("--jobs", "--load-average", "--max-load"))
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# A make variable's assignment on its command line, in each of GNU make's spellings: `V=x`,
# `V:=x`, `V::=x`, `V:::=x`, `V+=x`, `V?=x`, `V!=x` (nw2 brief 4, R1).
_MAKE_ASSIGN = re.compile(r"[A-Za-z0-9_.-]+(:{1,3}|[+?!])?=")
_NUMBER = re.compile(r"\d+(\.\d+)?$")
_PREFIXES = ("env", "exec", "command", "nohup", "time")


def _make_target(words: list[str]) -> str:
    """make's own target among the words after `make`: the first that is no option, no
    option's value (`-E` and `--eval`'s too) and no variable's assignment in any of make's
    spellings (nw2 brief 2, R3; brief 4, R1); '' with none."""
    i = 0
    while i < len(words):
        w = words[i]
        i += 1
        if w == "--":
            rest = [x for x in words[i:] if not _MAKE_ASSIGN.match(x)]
            return rest[0] if rest else ""
        if w.startswith("--"):
            if w in MAKE_LONG:
                i += 1
            elif w in MAKE_LONG_NUMBER and i < len(words) and _NUMBER.match(words[i]):
                i += 1
            continue
        if w.startswith("-") and len(w) > 1:
            for k, c in enumerate(w[1:], 1):
                if c in MAKE_VALUE or c in MAKE_NUMBER:
                    if k == len(w) - 1 and i < len(words) and (
                            c in MAKE_VALUE or _NUMBER.match(words[i])):
                        i += 1                         # the value is the next word
                    break                              # else the rest of this word is it
            continue
        if not _MAKE_ASSIGN.match(w):
            return w
    return ""


def _simple_commands(argv: list[str]) -> list[list[str]] | None:
    """The argv, or a shell's `-c` string cut at its operators into its simple commands, each
    without its redirections, as the package's one shell reader reads them (`shellreader`'s
    `_commands`; nw2 brief 3, R1); None where that reader cannot read the string (R2).
    Imported here, not at the top: no module of the hooks' path pays for it (R2)."""
    if not (len(argv) >= 3 and os.path.basename(argv[0]) in SHELLS
            and re.fullmatch(r"-[a-z]*c", argv[1])):
        return [argv]
    try:
        from .shellreader import _commands
        return [words for words, outs in _commands(argv[2]) if outs is not None]
    except Exception:                                  # a queued job still gets its entry
        return None


def command_kind(command) -> str:
    """design/31 item 1: an estimate's command. A landing's job is `gate land`. A command
    word `make` (the argv's first, or a shell `-c` string's, after `;`, `&&`, `|` and the
    like) gives `make <target>`, make's own target, with no option's value taken for it
    (brief 2, R3), or `make` with none: a `/bin/sh -c 'make check > log'`, `make -C repo
    check` and `make check` are one. Else the argv, its words joined by one space."""
    if not isinstance(command, list):
        return ""
    argv = [str(c) for c in command]
    if any(tuple(argv[i:i + 3]) == LAND_JOB for i in range(len(argv) - 2)):
        return "gate land"
    if any(tuple(argv[i:i + 4]) == CHECK_JOB for i in range(len(argv) - 3)):
        return "make check"         # nw5 R3: it is that run, and shares its estimate
    for words in _simple_commands(argv) or ():
        while words and (_ASSIGN.match(words[0]) or words[0] in _PREFIXES):
            words = words[1:]
        if words and os.path.basename(words[0]) in MAKES:
            target = _make_target(words[1:])
            return f"make {target}" if target else "make"
    return " ".join(" ".join(argv).split())


def last_line(path, gid: str, prefix: str = "") -> str | None:
    """A job log's last non-empty line that is not the gate's own (`gate <gid>: ...`, which
    `_start`, `_close` and `_finish` write) and starts with `prefix`, read from its last
    64 KiB; None when there is none or the log is unreadable (packet FW4c, R3; `gate land`
    passes `land <name>: `, since a child of the check may write after the land line, F1)."""
    skip = f"gate {gid}: "
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 65536))
            lines = [ln.strip() for ln in fh.read().decode(errors="replace").splitlines()]
    except (OSError, ValueError, TypeError):
        return None
    lines = [ln for ln in lines if ln and not ln.startswith(skip) and ln.startswith(prefix)]
    return lines[-1] if lines else None


def strict_code(result) -> int:
    """`wait --strict`'s exit (packet FW2, R1): the result's `exit` when it is an int from 0
    to 255 and no bool, else 1."""
    x = result.get("exit") if isinstance(result, dict) else None
    return x if isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 255 else 1


def _result_names(root, strict: bool = False) -> list[str]:
    """The entry dirs under the gate, newest first by counter."""
    return sorted((n for n in _listdir(gate_dir(root), strict) if ID.match(n)),
                  key=_counter, reverse=True)


def _greens(root, command=None) -> dict:
    """{key: [seconds]}: each key's newest greens, at most `EST_GREENS`, from at most
    `EST_SCAN` results newest first. A green has `exit` 0, a null `cut`, a number of
    `seconds` and a string `key`; a result older than FW2 has no key and is not counted.
    With `command`, only the greens of its `command_kind` (nw2 R7)."""
    kind = None if command is None else command_kind(command)
    out: dict = {}
    read = 0
    for n in _result_names(root):
        if read >= EST_SCAN:
            break
        r = _load(result_path(root, n))
        if r is None:
            continue
        read += 1
        x, sec, k = r.get("exit"), r.get("seconds"), r.get("key")
        if (x == 0 and not isinstance(x, bool) and r.get("cut") is None
                and isinstance(sec, (int, float)) and not isinstance(sec, bool)
                and isinstance(k, str) and k
                and (kind is None or command_kind(r.get("command")) == kind)):
            got = out.setdefault(k, [])
            if len(got) < EST_GREENS:
                got.append(float(sec))
    return out


def key_estimates(root, command=None) -> dict:
    """{key: (seconds, greens)} (packet FW2, R4): the median of a key's last `EST_LEAST` to
    `EST_GREENS` greens and how many it used; a key with fewer than `EST_LEAST` has none.
    The one source of an estimate: `estimates`, `entry_estimates` and `run`'s line read it."""
    return {k: (statistics.median(v), len(v)) for k, v in _greens(root, command).items()
            if len(v) >= EST_LEAST}


def estimates(root) -> dict:
    """{key: seconds}: `key_estimates` without the count."""
    return {k: s for k, (s, _) in key_estimates(root).items()}


def entry_estimates(root) -> dict:
    """{entry id: seconds}: the queued and running entries whose key has an estimate, of
    the entry's own command kind (nw2 R7)."""
    out, by = {}, {}
    for e in entries(root):
        kind = command_kind(e.get("command"))
        if kind not in by:
            by[kind] = {k: s for k, (s, _) in key_estimates(root, e.get("command")).items()}
        if entry_key(e) in by[kind]:
            out[e["id"]] = by[kind][entry_key(e)]
    return out


def est_text(s) -> str:
    return f"{s / 60:.1f}"


def followed(root, gid: str) -> str:
    """hw5 F3: the id a wait on `gid` waits on: its rerun's, where `gid`'s result is a load
    flake whose rerun is queued or done; else `gid`."""
    r = _load(result_path(root, gid))
    nxt = r.get("rerun") if isinstance(r, dict) and r.get("flake") == FLAKE else None
    if isinstance(nxt, str) and ID.match(nxt) and nxt != gid and (
            (_queue(root) / f"{nxt}.json").exists() or result_path(root, nxt).exists()):
        return nxt
    return gid


def wait(root, gid: str, poll=WAIT_POLL, timeout=None, sleep=None, clock=None, spawn=None,
         alive=_alive, follow: bool = False) -> tuple[int, dict | None]:
    """(0, result) once result.json is there; (2, None) for an id neither queued nor
    done; (1, None) past `timeout` seconds. Spawns `serve` at the first poll, and again
    only when runner.json names no live pid. `follow` (hw5 F3, `gate wait`): a load flake's
    wait is its rerun's, and the flake's own result once its rerun is taken out."""
    sleep, clock = sleep or time.sleep, clock or time.monotonic
    if not isinstance(gid, str) or not ID.match(gid):
        return 2, None
    t0, first = clock(), True
    while True:
        cur = followed(root, gid) if follow else gid
        r = _load(result_path(root, cur))
        if r is not None:
            return 0, resolved(root, r)                 # build 2, S2
        if not (_queue(root) / f"{cur}.json").exists():
            r = _load(result_path(root, cur))           # written between the two reads
            if r is None and cur != gid:                # the rerun taken out: the flake's
                r = _load(result_path(root, gid))
            return (0, resolved(root, r)) if r is not None else (2, None)
        if first or not alive((runner_info(root) or {}).get("pid")):
            (spawn or spawn_serve)(root)
            first = False
        left = None if timeout is None else timeout - (clock() - t0)
        if left is not None and left <= 0:
            return 1, None
        sleep(poll if left is None else min(poll, left))


def drop(root, gid: str, fx: Fx | None = None, alive=_alive) -> tuple[int, str]:
    """hw5 F4, `gate drop <id>`: (0, the result's line) where a queued entry was taken out,
    its result written with exit 130 and `dropped`, or where `gid` already has a result;
    (1, `running <id>: not dropped`) for a running one, untouched; (2, why) for an id the
    queue does not know. Build 2, S7: the drop's mark (`drop_path`) is made and flocked
    before the runner's file is read, and the runner reads the mark after it names its start
    (`_start`), so one of the two sees the other; the entry is never moved, so a waiter reads
    it as open, and a drop that dies leaves its mark unflocked, which the runner's next pass
    sweeps (`_sweep_drops`). S5: a queued rerun is taken out as the 30-minute bound takes it
    (`_not_rerun`), the first's line sent and printed; a drop of a flake whose rerun is
    queued drops that rerun."""
    fx = fx or Fx()
    if not isinstance(gid, str) or not ID.match(gid):
        return 2, f"gate drop: no gate {str(gid)[:40]!r} under {gate_dir(root)}"
    path = _queue(root) / f"{gid}.json"
    r = _load(result_path(root, gid))
    if r is not None:
        nxt = r.get("rerun") if r.get("flake") == FLAKE else None
        if isinstance(nxt, str) and ID.match(nxt) and nxt != gid \
                and (_queue(root) / f"{nxt}.json").exists() \
                and not result_path(root, nxt).exists():
            return drop(root, nxt, fx, alive)               # S5: the flake's queued rerun
        return 0, wait_line(resolved(root, r))               # build 2, S2
    if not path.exists():
        r = _load(result_path(root, gid))                   # it ended between the two reads
        return (0, wait_line(resolved(root, r))) if r is not None \
            else (2, f"gate drop: no gate {gid} under {gate_dir(root)}")
    fh = _hand(root, gid)
    try:
        if gid in _running_ids(root, alive):
            _unlink(drop_path(root, gid))
            return 1, f"running {gid}: not dropped"
        e, r = _load(path), _load(result_path(root, gid))
        if r is not None or e is None:                      # it ended in between
            r = r or _load(result_path(root, gid))
            _unlink(drop_path(root, gid))
            return (0, wait_line(resolved(root, r))) if r is not None \
                else (2, f"gate drop: no gate {gid} under {gate_dir(root)}")
        cfg = _config(fx.env, fx.log)
        if isinstance(e.get("rerun_of"), str) and ID.match(e["rerun_of"]):
            _not_rerun(root, fx, cfg, e)                    # S5: as the 30-minute bound
            out = wait_line(resolved(root, _load(result_path(root, gid))))
        else:
            e.update({"id": gid, "dropped": True})
            now = fx.now()
            out = wait_line(_finish(root, fx, cfg, e, CALLER_EXIT, now, now, CUT_CALLER,
                                    note="dropped by gate drop; not run"))
        _unlink(drop_path(root, gid))
        return 0, out
    finally:
        fh.close()


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
    if kind == "alone":                                     # hw5 F3
        return f"a rerun, alone: {why[1]} running"
    return f"{kind} {why[1]}"


def status(root, now, alive=_alive, fx: Fx | None = None, repo: str | None = None,
           strict: bool = False, largest=None) -> dict:
    """{running, queued, done, runner}: the entries running, a list; the rest in order, each
    with its key and its wait; the last five results newest first; the live runner or None.
    The wait is the runner's own rule, from `_holds` and `_over`; the load is read only for
    an entry nothing else holds, and only with one running. A `done` item holds `DONE_KEYS`,
    each as the result holds it: `load`, `beside` and `dirty` are null for a result written
    before them (packet gl1, R4); then `head`, the full sha or null, and `land`, a landing's
    branch or null (packet rw3, R6). With `repo` (packet rw3, R2 to R4) the dict opens with
    `repo`, the folder as `repo_path` resolves it, and each list holds the folder's alone:
    an entry or result whose `repo` resolves to it, or a landing's result of the branch the
    folder has checked out on the folder's key; `done` holds every result `KEEP` keeps.
    A `running` or `queued` item ends with the entry's `caller` and `queued`, null where the
    entry holds none (packet su4, R1). hw6 B4: an entry the budget or a guard holds says what
    and since when, from the runner's holds.json. B6: with `strict`, a gate that cannot be
    read raises GateError and never reads as empty. Fix 1, F1 and F4: `largest`, the reader's
    own call of a folder to its volume's largest consumer, names it after a disk hold, once a
    folder."""
    fx = fx or Fx()
    r = runner_info(root, strict)
    live = r if r and alive(r.get("pid")) else None
    run = [gid for gid, _ in _pairs(r)] if live else []
    es = entries(root, strict)
    names = _result_names(root, strict)
    held = _load(gate_dir(root) / HOLDS) or {}
    byid = {e["id"]: e for e in es}
    running = []
    for gid in run:
        e = byid.get(gid, {})
        at = _started_at(root, gid)
        running.append({"id": gid, "repo": e.get("repo"), "label": e.get("label") or "",
                        "since": at, "seconds": (now - at) if at else None,
                        "caller": e.get("caller"), "queued": e.get("queued")})
    want = repo_path(repo) if repo is not None else None
    seen: dict = {}

    def mine(r) -> bool:
        if want is None:
            return True
        if not isinstance(r, str):
            return False
        if r not in seen:
            seen[r] = repo_path(r) == want
        return seen[r]
    waiting = pick_order([e for e in es if e["id"] not in run], now)     # hw5 F1
    queued, memo, last, cfg, big = [], {}, None, None, {}
    them = [byid.get(g, {"id": g}) for g in run]
    for i, (e, why) in enumerate(_holds(waiting, them), 1):
        if why is None and running:
            if last is None:
                last = max((x["since"] for x in running if x["since"]), default=0)
                cfg = _config(fx.env)
            why = _bar(cfg, fx, e, them, last, now, memo)
        wait = _wait_text(why)
        h = held.get(e["id"]) if why is None else None
        if isinstance(h, dict) and isinstance(h.get("what"), str):        # hw6 B4
            wait = h["what"]
            if h.get("disk") is True and largest is not None:
                folder = e.get("repo")
                if folder not in big:
                    try:
                        big[folder] = largest(folder)
                    except Exception:                   # noqa: BLE001 (the line goes on)
                        big[folder] = None
                wait += f"; {big[folder]}" if big[folder] else ""
            wait += f" since {_hm(h['since'])}" if _number(h.get("since")) else ""
        queued.append({"id": e["id"], "repo": e.get("repo"), "position": i, "lock": _locked(e),
                       "label": e.get("label") or "", "key": entry_key(e),
                       "wait": wait, "caller": e.get("caller"),
                       "queued": e.get("queued")})
    done, tree = [], {}

    def landed(res: dict, branch) -> bool:
        if branch is None:
            return False
        if "branch" not in tree:      # one git read a call, and only for a landing
            tree["branch"] = _branch(want)
            tree["key"] = repo_key(want) if tree["branch"] else None
        return branch == tree["branch"] and res.get("key") == tree["key"]
    for n in names:
        res = _load(result_path(root, n))
        if res is None:
            continue
        item = {**{k: res.get(k) for k in DONE_KEYS}, "head": _clean_head(res.get("head")),
                "land": land_branch(res.get("command"))}
        if want is None:
            done.append(item)
            if len(done) == DONE_SHOWN:
                break
            continue
        ended = res.get("ended")
        if isinstance(ended, (int, float)) and now - ended > KEEP:      # `_prune`'s rule
            continue
        if mine(res.get("repo")) or landed(res, item["land"]):
            done.append(item)
    runner = {"pid": live.get("pid"), "since": live.get("since")} if live else None
    st = {"running": running, "queued": queued, "done": done, "runner": runner}
    if want is None:
        return st
    return {"repo": want, "running": [x for x in running if mine(x.get("repo"))],
            "queued": [x for x in queued if mine(x.get("repo"))], "done": done,
            "runner": runner}


def _repo_done_line(x: dict) -> str:
    """A result's line under `status --repo` (packet rw3, R5)."""
    s = x.get("seconds")
    m = est_text(s) if isinstance(s, (int, float)) and not isinstance(s, bool) else "?"
    line = f"done {x['id']} {x['repo']} exit {x['exit']} {m} min"
    if x.get("head"):
        line += f" head {x['head'][:7]}"
    d = x.get("dirty")
    start = d.get("start") if isinstance(d, dict) else None
    if isinstance(start, (int, float)) and not isinstance(start, bool) and start > 0:
        line += f" dirty {start}"
    if x.get("land"):
        line += f" land {x['land']}"
    return line


def status_lines(st: dict, est: dict | None = None) -> list[str]:
    """The status as lines; a running or queued entry whose id is in `est` ends
    `; est <m.m> min` (packet FW2, R5), else today's bytes. A status with `repo` (packet
    rw3, R5) writes each result by `_repo_done_line`, the first `REPO_SHOWN` and then a
    `MORE_REPO` line, its path quoted for a shell (packet su4, R5), or `none for <repo>`
    when no line names the folder."""
    est = est or {}

    def tail(gid):
        return f"; est {est_text(est[gid])} min" if gid in est else ""
    out = []
    for x in st.get("running") or []:
        out.append(f"running {x['id']} {x['repo']} since {_hm(x['since'])} {x['label']}".rstrip()
                   + tail(x["id"]))
    for x in st.get("queued") or []:
        wait = f" waits on {x['wait']}" if x.get("wait") else ""
        out.append(f"queued {x['id']} {x['repo']} position {x['position']}{wait}" + tail(x["id"]))
    if "repo" in st:
        done = st.get("done") or []
        out.extend(_repo_done_line(x) for x in done[:REPO_SHOWN])
        if len(done) > REPO_SHOWN:
            out.append(MORE_REPO.format(n=len(done) - REPO_SHOWN, path=shlex.quote(st["repo"])))
        if not out:
            out.append(f"none for {st['repo']}")
    else:
        for x in st.get("done") or []:
            out.append(f"done {x['id']} {x['repo']} exit {x['exit']} {_minutes(x['seconds'])} min")
    rn = st.get("runner")
    out.append(f"runner: pid {rn['pid']} since {_hm(rn['since'])}" if rn else "runner: none")
    return out


# ---- the caller's inbox and ntfy ---------------------------------------------

def inbox_write(root, sid: str, result: dict) -> Path | None:
    """`<state>/sessions/<sid>/inbox/<id>.json` {at, kind, id, repo, exit, seconds, log}; a
    chain's result (nw2 R1) to `<state>/respawn/<chain>/inbox/<id>.json`, whatever `sid`,
    with `chain`, `head`, `dirty` and `label` after those."""
    if not ID.match(str(result.get("id"))):
        return None
    chain = result.get("chain")
    if "chain" in result and not (isinstance(chain, str) and CHAIN_RE.match(chain)):
        return None
    if "chain" not in result and (not isinstance(sid, str) or not _SID.match(sid)):
        return None
    d = chain_inbox(root, chain) if "chain" in result else _inbox(root, sid)
    _mkdir(d)
    body = {"at": result.get("ended"), "kind": "gate", "id": result["id"],
            "repo": result.get("repo"), "exit": result.get("exit"),
            "seconds": result.get("seconds"), "log": result.get("log")}
    if "chain" in result:
        body.update({"chain": chain, "head": _clean_head(result.get("head")),
                     "dirty": _start_dirt(result.get("dirty")),
                     "label": _label(result.get("label"))})
    body.update({k: result[k] for k in ("flake", "rerun_of", "dropped") if k in result})  # F5
    path = d / f"{result['id']}.json"
    _write_private(path, json.dumps(body) + "\n")
    return path


def _waiting(d: Path) -> list[Path]:
    try:
        return sorted((p for p in d.iterdir() if p.suffix == ".json" and ID.match(p.stem)),
                      key=lambda p: _counter(p.stem))
    except OSError:
        return []


def _shown(root, sid: str) -> set:
    got = _load(Path(root) / "sessions" / sid / SHOWN) or {}
    ids = got.get("ids") if isinstance(got, dict) else None
    return {i for i in ids if isinstance(i, str)} if isinstance(ids, list) else set()


def _set_aside(d: Path, now: float) -> tuple[int, set]:
    """nw2 R2: the chain's lines older than `OLD_LINE` (by `at`, else the file's mtime)
    renamed into `inbox/old/`; how many, and the ids of those a failed set-aside left where
    they are (brief 2, R9: `old` not made, a rename refused), which stop no take."""
    n, stuck = 0, set()
    for p in _waiting(d):
        at = (_load(p) or {}).get("at")
        if not isinstance(at, (int, float)) or isinstance(at, bool):
            try:
                at = p.stat().st_mtime
            except OSError:
                continue
        if at < now - OLD_LINE:
            try:
                _mkdir(d / "old")
                os.rename(p, d / "old" / p.name)
                n += 1
            except OSError:
                stuck.add(p.stem)
    return n, stuck


def inbox_take(root, sid: str, limit=TAKE, fits=None, chain: str | None = None,
               closed: bool = False, now=None) -> list[str]:
    """At most `limit` inbox files, oldest first, each taken by an atomic rename into
    `inbox/read/` and read as its wait line, then `<n> more: ...` when any remain. `fits`
    (the text so far) stops the take where the hook's output would pass its ceiling.
    `chain` (nw2 R2, `chain_taker`'s): the chain's inbox after the session's own, by the
    same rename under the same bounds; its lines older than `OLD_LINE` set aside first and
    counted in one line, a line whose set-aside fails left where it is. `closed`
    (`sitting_closed`): each chain line is shown once, after CLOSED_WORDS, remembered in
    `sessions/<sid>/gate-shown.json`, and left where it is, a corrupt one too.
    A failure before any rename is no gate lines, and the files wait for the next hook;
    after one, every line already taken is returned (brief 2, R1). A shown record that
    cannot be written is not one: its lines are shown again at the next hook, never moved."""
    if not isinstance(sid, str) or not _SID.match(sid):
        return []
    d = _inbox(root, sid)
    cd = chain_inbox(root, chain) if chain else None
    now = time.time() if now is None else now
    fits = fits or (lambda text: True)
    lines: list[str] = []
    skip: set = set()                                  # the chain's ids this take passes by
    if cd is not None and not closed:
        old, skip = _set_aside(cd, now)
        if old:
            lines.append(f"gate: {old} {'line' if old == 1 else 'lines'} of this chain older "
                         f"than 24 hours set aside in {cd / 'old'}")
    shown = _shown(root, sid) if cd is not None and closed else set()
    skip |= shown

    def waiting() -> list[Path]:
        own = _waiting(d)
        if cd is None:
            return own
        theirs = [p for p in _waiting(cd) if p.stem not in skip]
        return sorted(own + theirs, key=lambda p: _counter(p.stem))
    files, took, moved = waiting(), 0, False
    newly = []
    try:
        for i, p in enumerate(files):
            if took >= limit:
                break
            home = p.parent
            keep = closed and cd is not None and home == cd
            body = _load(p)
            if body is None:                           # unreadable: set aside, unprinted
                if keep:                               # brief 2, R7: a closed sitting's stays
                    skip.add(p.stem)
                    continue
                try:
                    _mkdir(home / "read")
                    os.rename(p, home / "read" / p.name)
                except OSError:
                    pass
                continue
            left = len(files) - i - 1
            line = wait_line(body)
            if keep:
                line = f"{CLOSED_WORDS}: {line}"
            if not fits("\n".join(lines + [line] + ([MORE.format(n=left)] if left else []))):
                break
            if keep:
                newly.append(p.stem)
            else:
                try:
                    _mkdir(home / "read")
                    os.rename(p, home / "read" / p.name)
                except OSError:
                    continue                           # another hook took it first
                moved = True
            lines.append(line)
            took += 1
        skip |= set(newly)
        if newly:
            try:
                _write_private(Path(root) / "sessions" / sid / SHOWN,
                               json.dumps({"ids": sorted(shown | set(newly))}) + "\n")
            except OSError:
                pass                                   # R1: shown again next time, never moved
        rest = len(waiting())
        if rest and fits("\n".join(lines + [MORE.format(n=rest)])):
            lines.append(MORE.format(n=rest))
    except Exception:                                  # noqa: BLE001
        if not moved:
            raise
    return lines


def wait_chain(root, name: str, sid, poll=WAIT_POLL, timeout=None, sleep=None, clock=None,
               spawn=None, alive=_alive) -> tuple[int, int]:
    """design/31 item 12, `gate wait --chain`: (0, n) once the chain's inbox holds `n` lines
    not yet taken; (2, 0) at once with no open job of the chain and no line; (1, 0) past
    `timeout`. From the session's confirmed mark on, no line returns it: it sleeps until its
    timeout, or until the restart ends it. Spawns `serve` as `wait` does."""
    sleep, clock = sleep or time.sleep, clock or time.monotonic
    t0, first = clock(), True
    box = chain_inbox(root, name)
    while True:
        if not sitting_closed(root, sid):
            n = len(_waiting(box))
            if n:
                return 0, n
            if not open_jobs(root, name):
                n = len(_waiting(box))                 # written between the two reads
                return (0, n) if n else (2, 0)
        if first or not alive((runner_info(root) or {}).get("pid")):
            (spawn or spawn_serve)(root)
            first = False
        left = None if timeout is None else timeout - (clock() - t0)
        if left is not None and left <= 0:
            return 1, 0
        sleep(poll if left is None else min(poll, left))


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
