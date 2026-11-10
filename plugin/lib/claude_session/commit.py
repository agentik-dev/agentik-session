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

One call at a time per work tree: a lock in its git dir is held from before the add until the
line is printed, so the `ok` sha is the commit this call made; a second call waits up to the
gate's wall.

On every red the named paths' index entries are put back as they were read, and no other entry
is touched, so the index is as it was found.
"""

from __future__ import annotations

import fcntl
import io
import os
import shlex
import subprocess
import sys
import time

IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")
MAKES = ("make", "gmake")
NAMED = 20
DEVNULL = subprocess.DEVNULL
LOCK = "agentik-commit.lock"         # in the git dir: one call at a time (round 1, F1)
LOCK_RED = 124                       # a lock not had within the wall: `red lock exit 124`


class Refused(Exception):
    """A refusal before the index changes (or with it restored): exit 2."""


class Red(Exception):
    def __init__(self, step, code):
        super().__init__(step)
        self.step, self.code = step, code


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
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
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


def _entries(cwd: str, paths: list) -> dict:
    """{full name: `mode sha stage`} for the named paths' index entries."""
    _, fields, _ = _git(cwd, "ls-files", "-s", "--full-name", "-z", "--", *paths, z=True)
    out = {}
    for f in fields:
        meta, _, name = f.partition("\t")
        out[name] = meta
    return out


def _restore(top: str, cwd: str, paths: list, before: dict) -> None:
    """Put the named paths' entries back as `before` read them; nothing else."""
    now = _entries(cwd, paths)
    gone = [p for p in now if p not in before]
    back = [p for p in before if now.get(p) != before[p]]
    if gone:
        _git(top, "update-index", "--force-remove", "-z", "--stdin",
             stdin=b"".join(os.fsencode(p) + b"\0" for p in gone))
    if back:
        _git(top, "update-index", "-z", "--index-info",
             stdin=b"".join(os.fsencode(f"{before[p]}\t{p}") + b"\0" for p in back))


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
    fd = _lock(_git_path(top, LOCK), wall)
    if fd is None:
        print(f"commit {name}: red lock exit {LOCK_RED}", flush=True)
        return LOCK_RED
    try:
        return _locked(top, cwd, name, paths, argv, msg, env, gated, caller, wall)
    finally:
        os.close(fd)                    # the lock goes after the line, its sha read under it


def _locked(top, cwd, name, paths, argv, msg, env, gated, caller, wall) -> int:
    _require_state(top)
    _require_paths(top, cwd, paths)
    before = _entries(cwd, paths)
    try:
        code, _, err = _git(cwd, "add", "--", *paths)
        if code != 0:
            sys.stderr.write(err.decode(errors="replace"))
            raise Red("add", code)
        if _git(cwd, "diff", "--cached", "--quiet", "HEAD", "--", *paths)[0] == 0:
            _restore(top, cwd, paths, before)
            raise Refused("nothing to commit in the named paths")
        code = _gate_check(top, argv, env, caller, wall) if gated else _direct_check(top, argv)
        if code != 0:
            raise Red("check", code)
        if _git(cwd, "diff", "--quiet", "--", *paths)[0] != 0:
            print("commit-step: a named path changed during the check; nothing committed",
                  file=sys.stderr)
            raise Red("moved", 1)
        code, _, err = _git(cwd, "commit", "-q", "--only", "-F", msg, "--", *paths)
        if code != 0:
            sys.stderr.write(err.decode(errors="replace"))
            raise Red("commit", code)
        sha = _git(top, "rev-parse", "HEAD")[1]     # this call's commit: no other call holds
    except Red as red:                              # the lock between the commit and here
        _restore(top, cwd, paths, before)
        print(f"commit {name}: red {red.step} exit {red.code}", flush=True)
        return red.code
    except (KeyboardInterrupt, SystemExit):
        _restore(top, cwd, paths, before)
        raise
    print(f"commit {name}: ok {sha}", flush=True)
    return 0
