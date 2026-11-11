"""commit: add by explicit path, run the check, commit on green (packet FW4d; hq design/08 §5
row 5).

  agentik session commit <paths...> --check <cmd> --message-file <f>

The repo is the one holding the cwd; each path is taken literally (GIT_LITERAL_PATHSPECS), as
git takes it from the cwd. Refused, exit 2, before the index changes: no path, `-A`, `-u`, the
whole tree (its top by any name), a path outside the repo, a path that is an untracked nested
repo or holds one (git would add it as a gitlink), a path git would not add, a message file
missing, unreadable or blank, an empty check, a merge, cherry-pick, revert or rebase under way,
a detached HEAD, and named paths with nothing to commit. Then: the named paths' index entries
are read, `git add -- <paths>`, the check in the repo's top, and on green
`git commit --only -F <f> -- <paths>`, so a path someone else staged stays staged and out of the
commit. The check is one string split by shlex and run with no shell; it goes through the gate
(one job, its code `gate wait --strict`'s) when its first word is `make` or `gmake`, since the
gate queue holds every `make` on the machine; any other check runs here, directly, its output on
stderr. Stdout is one line, last:

  commit <repo>: ok <sha>                       exit 0
  commit <repo>: red check exit <code>          the check's code (127, 126, 128+n a signal)
  commit <repo>: red moved exit 1               a named path changed during the check
  commit <repo>: red <add|commit> exit <code>   git's own red
  commit <repo>: red lock exit 124              another call held the lock past the wall
  commit <repo>: red <step> exit <code>, the commit stands: <sha>
                                                a red or a signal once HEAD moved to this
                                                call's commit: nothing is restored
  commit <repo>: red restore exit 1, the index as found is kept at <snapshot>

One call at a time per work tree: a lock in its git dir is held from before the add until the
line is printed, so the `ok` sha is the commit this call made; a second call waits up to the
gate's wall.

Before the add the index file is copied whole to the git dir (`agentik-commit.index`). On every
other failure (a red, a refusal after the add, any exception, SIGINT, SIGTERM, SIGHUP) that
copy goes back over the index by git's protocol (`index.lock`, then a rename), under the lock,
so the index is as it was found, a path someone staged earlier included. A restore that cannot
be made is `red restore`: the copy stays, and a later call refuses until it is moved back or
removed. SIGKILL is out of reach: the copy is the way back.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import io
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time

IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")
MAKES = ("make", "gmake")
NAMED = 20
DEVNULL = subprocess.DEVNULL
LOCK = "agentik-commit.lock"         # in the git dir: one call at a time (round 1, F1)
LOCK_RED = 124                       # a lock not had within the wall: `red lock exit 124`
SNAP = "agentik-commit.index"        # in the git dir: the index file as found (F3, F4)
RESTORE_WAIT = 2.0                   # seconds a restore waits on another writer's index.lock
MOVED = "the index moved under the check: nothing is restored"     # fold 2: another writer


class Refused(Exception):
    """A refusal before the index changes (or with it restored): exit 2."""


class Red(Exception):
    def __init__(self, step, code):
        super().__init__(step)
        self.step, self.code = step, code


class _Signal(SystemExit):
    """SIGTERM or SIGHUP, raised so the index goes back on the way out (F7); exit 128+n."""

    def __init__(self, signum):
        super().__init__(128 + signum)


@contextlib.contextmanager
def _signals():
    """SIGTERM and SIGHUP raise _Signal for the span (SIGINT is Python's KeyboardInterrupt)."""
    def raise_(signum, frame):
        raise _Signal(signum)
    saved = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            if signal.getsignal(sig) != signal.SIG_IGN:     # nohup's SIGHUP stays ignored
                saved[sig] = signal.signal(sig, raise_)
        except (ValueError, OSError):   # not the main thread: no handler, as before
            pass
    try:
        yield
    finally:
        for sig, was in saved.items():
            signal.signal(sig, signal.SIG_DFL if was is None else was)


@contextlib.contextmanager
def _held():
    """SIGINT, SIGTERM and SIGHUP held while the index goes back, so a second signal cannot cut
    a restore halfway or leave index.lock behind; one sent meanwhile lands after."""
    try:
        was = signal.pthread_sigmask(signal.SIG_BLOCK,
                                     {signal.SIGINT, signal.SIGTERM, signal.SIGHUP})
    except (AttributeError, OSError, ValueError):
        was = None
    try:
        yield
    finally:
        if was is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, was)


def _env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env["GIT_LITERAL_PATHSPECS"] = "1"
    return env


def _git(cwd, *args, z=False, stdin=None):
    p = subprocess.run(("git",) + args, cwd=cwd, env=_env(), input=stdin,
                       stdin=None if stdin is not None else DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if z:
        return p.returncode, [os.fsdecode(f) for f in p.stdout.split(b"\0") if f], p.stderr
    return p.returncode, p.stdout.decode(errors="replace").strip(), p.stderr


def uses_gate(argv: list) -> bool:
    """The check is a gate job when its first word is make or gmake (packet FW4d, R5)."""
    return bool(argv) and os.path.basename(argv[0]) in MAKES


def _top(cwd: str) -> str:
    code, top, _ = _git(cwd, "rev-parse", "--show-toplevel")
    if code != 0 or not top:
        raise Refused("not inside a git work tree: " + cwd)
    return os.path.realpath(top)


def _git_path(top: str, name: str) -> str:
    """`name` in the git dir of the work tree at `top` (a linked worktree's own, where its index
    and HEAD live)."""
    code, path, _ = _git(top, "rev-parse", "--git-path", name)
    if code != 0 or not path:
        raise Refused(f"no git dir for {top}")
    return os.path.join(top, path)


def _lock(path: str, wall) -> int | None:
    """The commit lock (an flock on `path`, released when its descriptor closes or the process
    dies; the check never inherits it), waited for up to `wall` seconds; None past it."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    except OSError as err:
        raise Refused(f"the commit lock {path}: {err}") from None
    end, said = time.monotonic() + float(wall), False
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if not said:
                holder = os.pread(fd, 32, 0).decode(errors="replace").strip() or "?"
                print(f"commit-step: waiting for {path}, held by pid {holder}, up to {wall} s",
                      file=sys.stderr, flush=True)
                said = True
            if time.monotonic() >= end:
                os.close(fd)
                return None
            time.sleep(0.1)
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"{os.getpid()}\n".encode(), 0)
    return fd


def _head(top: str) -> str:
    """HEAD's sha, or "" on an unborn branch."""
    return _git(top, "rev-parse", "-q", "--verify", "HEAD")[1]


def _entries(top: str) -> str:
    """A hash of the index's entries (`ls-files -s -z`: mode, blob, stage, path), so a stat-only
    refresh (anyone's `git status`) is no change and a staged path or a commit's is."""
    p = subprocess.run(("git", "ls-files", "-s", "-z"), cwd=top, env=_env(), stdin=DEVNULL,
                       stdout=subprocess.PIPE, stderr=DEVNULL)
    return f"{p.returncode}:{hashlib.sha256(p.stdout).hexdigest()}"


def _code(rc: int) -> int:
    """A child's code as a shell reads it: 128+n for a signal."""
    return rc if rc >= 0 else 128 - rc


def _verdict(exc: BaseException) -> tuple:
    """The step and code a failure's line names."""
    if isinstance(exc, Red):
        return exc.step, exc.code
    if isinstance(exc, KeyboardInterrupt):
        return "signal", 128 + signal.SIGINT
    if isinstance(exc, _Signal):
        return "signal", exc.code
    if isinstance(exc, Refused):
        return "refused", 2
    if isinstance(exc, SystemExit) and isinstance(exc.code, int):
        return "exit", exc.code
    return "error", 1


def _require_state(top: str) -> None:
    for name in IN_PROGRESS:
        code, path, _ = _git(top, "rev-parse", "--git-path", name)
        if code != 0 or os.path.lexists(os.path.join(top, path)):
            raise Refused(f"{name} in {top}: a merge, cherry-pick, revert or rebase is under "
                          "way; finish or abort it first")
    if _git(top, "symbolic-ref", "-q", "HEAD")[0] != 0:
        raise Refused(f"HEAD is detached in {top}: a commit there is on no branch")


def _where(here: str, p: str) -> str:
    """The path as git reads it (`..` folded by text), its directory's symlinks resolved."""
    full = os.path.normpath(os.path.join(here, p))
    if os.path.isdir(full) and not os.path.islink(full):
        return os.path.realpath(full)
    head, tail = os.path.split(full)
    return os.path.join(os.path.realpath(head), tail)


def _require_paths(top: str, cwd: str, paths: list) -> None:
    if not paths:
        raise Refused("name each path to commit")
    here = os.path.realpath(cwd)
    for p in paths:
        full = _where(here, p)
        if full == top:
            raise Refused(f"{p} is the whole tree: name each path to commit")
        if not full.startswith(top + os.sep):
            raise Refused(f"{p} is outside the repo at {top}")
    _, others, _ = _git(cwd, "ls-files", "-o", "--exclude-standard", "-z", "--", *paths, z=True)
    nested = [o for o in others if o.endswith("/")]
    if nested:
        more = f" and {len(nested) - NAMED} more" if len(nested) > NAMED else ""
        raise Refused("a nested git repo, which git would add as a gitlink: "
                      + ", ".join(nested[:NAMED]) + more)
    code, _, err = _git(cwd, "add", "--dry-run", "--", *paths)
    if code != 0:
        raise Refused("git add refuses: " + err.decode(errors="replace").strip()[:400])


def _message(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode(errors="replace")
    except OSError as err:
        raise Refused(f"the message file: {err}") from None
    if not text.strip():
        raise Refused(f"the message file {path} is blank")
    return os.path.abspath(path)


def _snapshot(index: str, snap: str) -> None:
    """The index file copied whole to `snap`, its mtime kept (git's racy-entry test reads it);
    an empty `snap` stands for no index. Written aside, then renamed: never half a snapshot."""
    tmp = snap + ".tmp"
    try:
        try:
            shutil.copy2(index, tmp)
        except FileNotFoundError:
            open(tmp, "wb").close()
        os.replace(tmp, snap)
    except OSError as err:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise Refused(f"the index cannot be copied to {snap}: {err}") from None


def _put_back(index: str, snap: str, unmoved=None):
    """The snapshot back over the index by git's own protocol: `index.lock` taken (O_EXCL, up to
    RESTORE_WAIT behind another writer), the snapshot's bytes and mtime written into it, renamed
    over the index; then the snapshot goes. None when done or never taken, MOVED when
    `unmoved()`, asked under index.lock so no git writes between, says another writer moved HEAD
    or the index (the lock let go, nothing written), else why not, the snapshot left in place."""
    if not os.path.exists(snap):
        return None                     # not taken: the add never ran
    lock = index + ".lock"
    end = time.monotonic() + RESTORE_WAIT
    while True:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            break
        except FileExistsError:
            if time.monotonic() >= end:
                return f"{lock} exists: another git holds the index"
            time.sleep(0.05)
        except OSError as err:
            return f"{lock}: {err}"
    try:
        if unmoved is not None and not unmoved():
            os.close(fd)
            fd = None
            os.unlink(lock)
            return MOVED
        st = os.stat(snap)
        if st.st_size:
            with open(snap, "rb") as src:
                data = src.read()
            with os.fdopen(fd, "wb") as dst:
                fd = None
                dst.write(data)
            os.utime(lock, ns=(st.st_atime_ns, st.st_mtime_ns))
            os.replace(lock, index)
        else:
            os.close(fd)
            fd = None
            with contextlib.suppress(FileNotFoundError):
                os.unlink(index)
            os.unlink(lock)
    except OSError as err:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(lock)             # ours: made O_EXCL above and not renamed
        return f"{index}: {err}"
    with contextlib.suppress(OSError):
        os.unlink(snap)
    return None


def _gate_check(top: str, argv: list, env, caller, wall) -> int:
    from . import gate, resolver
    root = resolver.state_dir(env)
    try:
        e = gate.enqueue(root, top, argv, dict(env), [], wall, "commit check", caller,
                         time.time())
    except gate.GateError as err:
        print(f"commit-step: the gate refuses: {err}", file=sys.stderr, flush=True)
        return 1
    gate.spawn_serve(root)
    print(f"commit-step: check queued {e['id']} in {top}", file=sys.stderr, flush=True)
    rc, result = gate.wait(root, e["id"])
    if rc != 0 or result is None:
        return 1
    print(gate.wait_line(result), file=sys.stderr, flush=True)
    return gate.strict_code(result)


def _direct_check(top: str, argv: list) -> int:
    sys.stderr.flush()
    try:
        fd = sys.stderr.fileno()
    except (AttributeError, ValueError, io.UnsupportedOperation):
        fd = None                       # a stderr with no descriptor: capture, then write
    try:
        p = subprocess.run(argv, cwd=top, stdin=DEVNULL,
                           stdout=subprocess.PIPE if fd is None else fd,
                           stderr=subprocess.STDOUT if fd is None else fd)
    except FileNotFoundError:
        return 127
    except (PermissionError, OSError):
        return 126
    if fd is None:
        sys.stderr.write(p.stdout.decode(errors="replace"))
    return p.returncode if p.returncode >= 0 else 128 - p.returncode


def commit(cwd: str, paths: list, check: str, message: str, env, args=None) -> int:
    """The verb; Refused for a refusal, else the line printed and its code."""
    try:
        argv = shlex.split(check or "")
    except ValueError as err:
        raise Refused(f"--check does not split: {err}") from None
    if not argv:
        raise Refused("--check is empty")
    msg = _message(message)
    from . import gate
    gated, caller = uses_gate(argv), None
    if gated:
        try:
            caller = gate.resolve_caller(args, env)
        except gate.GateError as err:
            raise Refused(str(err)) from None
    wall = gate._config(env)["wall"]
    top = _top(cwd)
    name = os.path.basename(top)
    with _signals():
        fd = _lock(_git_path(top, LOCK), wall)
        if fd is None:
            print(f"commit {name}: red lock exit {LOCK_RED}", flush=True)
            return LOCK_RED
        try:
            return _locked(top, cwd, name, paths, argv, msg, env, gated, caller, wall)
        finally:
            os.close(fd)                # the lock goes after the line, its sha read under it


def _locked(top, cwd, name, paths, argv, msg, env, gated, caller, wall) -> int:
    index, snap = _git_path(top, "index"), _git_path(top, SNAP)
    if os.path.lexists(snap):
        raise Refused(f"{snap} is the index as an earlier call found it, not put back: "
                      f"`mv {snap} {index}` puts it back, or remove it; then call again")
    _require_state(top)
    _require_paths(top, cwd, paths)
    old, done = None, False             # HEAD before this call's `git commit`, once it runs
    base, after = _head(top), None      # HEAD before the add; the entries right after it
    try:
        _snapshot(index, snap)
        code, _, err = _git(cwd, "add", "--", *paths)
        after = _entries(top)
        if code != 0:
            sys.stderr.write(err.decode(errors="replace"))
            raise Red("add", _code(code))
        if _git(cwd, "diff", "--cached", "--quiet", "HEAD", "--", *paths)[0] == 0:
            raise Refused("nothing to commit in the named paths")
        code = _gate_check(top, argv, env, caller, wall) if gated else _direct_check(top, argv)
        if code != 0:
            raise Red("check", code)
        if _git(cwd, "diff", "--quiet", "--", *paths)[0] != 0:
            print("commit-step: a named path changed during the check; nothing committed",
                  file=sys.stderr)
            raise Red("moved", 1)
        old = _head(top)
        code, _, err = _git(cwd, "commit", "-q", "--only", "-F", msg, "--", *paths)
        if code != 0:
            sys.stderr.write(err.decode(errors="replace"))
            raise Red("commit", _code(code))
        sha = _head(top)                # this call's commit: no other call holds the lock
        _drop(snap)
        print(f"commit {name}: ok {sha}", flush=True)
        done = True
        return 0
    except BaseException as exc:
        if done:
            raise
        with _held():
            line = _failed(exc, top, cwd, name, paths, (base, after, old), index, snap)
            if line:
                print(line, flush=True)
        if isinstance(exc, (Red, Refused)) and line.startswith(f"commit {name}: red restore "):
            return 1
        if isinstance(exc, Red):
            return exc.code
        raise


def _drop(snap: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(snap)


def _tell_moved(exc, step, code, top, cwd, paths, base) -> None:
    """Stderr for the index that moved: what moved, and this call's paths still staged against
    HEAD with the way to unstage them; the other writer's state is left as it stands."""
    now = _head(top)
    what = (f"HEAD moved from {base or 'no commit'} to {now or 'no commit'}" if now != base
            else "another writer changed the index")
    _, names, _ = _git(cwd, "diff", "--cached", "--name-only", "-z", "--", *paths, z=True)
    if names:
        quoted = " ".join(shlex.quote(n) for n in names)
        left = (f"this call's paths still staged: {', '.join(names)}; "
                f"`git -C {shlex.quote(top)} restore --staged -- {quoted}` unstages them")
    else:
        left = "none of this call's paths is staged against HEAD"
    red = exc if isinstance(exc, Refused) else f"red {step} exit {code}"
    print(f"commit-step: {red}; {what} during the check, so the index as found is not put back "
          f"over it: {left}", file=sys.stderr, flush=True)


def _failed(exc, top, cwd, name, paths, heads, index, snap):
    """On a failure: the commit stands when HEAD moved to it; else the snapshot goes back only
    when HEAD is still the one read before the add and the entries are those read after it
    (`after` None: the add itself was cut, HEAD alone is asked), since over another writer's
    newer HEAD or index the old index would stage their work's reversal; the line to print
    ("" for a refusal or a signal before the commit, as found)."""
    step, code = _verdict(exc)
    base, after, old = heads
    now = _head(top) if old is not None else None
    if now and now != old:              # HEAD moved to this call's commit: nothing restores
        _drop(snap)
        return f"commit {name}: red {step} exit {code}, the commit stands: {now}"

    def unmoved():
        return _head(top) == base and (after is None or _entries(top) == after)
    why = None
    if os.path.exists(snap):
        why = MOVED if not unmoved() else _put_back(index, snap, unmoved)
    if why is MOVED:
        _drop(snap)                     # stale: putting it back is the harm
        _tell_moved(exc, step, code, top, cwd, paths, base)
        return f"commit {name}: red {step} exit {code}, {MOVED}"
    if why:
        tell = (f"commit-step: {exc if isinstance(exc, Refused) else f'red {step} exit {code}'}"
                f"; the index was not put back ({why}): `mv {snap} {index}` puts it back")
        print(tell, file=sys.stderr, flush=True)
        return f"commit {name}: red restore exit 1, the index as found is kept at {snap}"
    return f"commit {name}: red {step} exit {code}" if isinstance(exc, Red) else ""
