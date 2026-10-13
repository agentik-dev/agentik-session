"""Git state, captured *before* the run so the report can tell what changed.

The baseline is the whole point. `git diff HEAD` after the fact is empty for a
run that committed its work -- which is what a good autonomous run does -- so a
report built that way says "no changes detected" for the successful case and
blends the user's pre-existing uncommitted work into the diff for every other.
Diffing against a recorded pre-run sha fixes both.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field

from . import config

# Hooks are killed by the harness at 10s; git must give up well before that.
_TIMEOUT = 5


def _git(workdir: str, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", "-C", workdir, *args],
            capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 127, ""
    return p.returncode, p.stdout


def git_available() -> bool:
    try:
        return subprocess.run(
            ["git", "--version"], capture_output=True, timeout=_TIMEOUT
        ).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def is_repo(workdir: str) -> bool:
    rc, out = _git(workdir, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def canonical_project(workdir: str) -> str:
    """Scoping key: the git toplevel if there is one, else the realpath.

    Deliberately falls back rather than raising -- but note the fallback is a
    *different* key for the same directory, so callers should record which one
    they used if they care about matching later.
    """
    rc, out = _git(workdir, "rev-parse", "--show-toplevel")
    if rc == 0 and out.strip():
        return os.path.realpath(out.strip())
    return os.path.realpath(workdir)


@dataclass
class Baseline:
    head: str | None
    branch: str | None
    # None is UNKNOWN: git status failed or timed out (review r6 E2). A reader
    # must never take it for clean; `if b.dirty` alone would.
    dirty: bool | None
    is_repo: bool
    # What was ALREADY modified/untracked before the run, so the report can
    # subtract it. A bare `dirty` flag cannot: on a dirty tree every run reads
    # as having changed something, and NO-OP becomes unreachable.
    pre_dirty: dict[str, str] = field(default_factory=dict)   # path -> blob sha or "?"


def _run(workdir: str, *args: str, stdin: bytes | None = None) -> tuple[int, bytes, bytes]:
    """(rc, stdout, stderr); rc 127 when git is missing or outlives _TIMEOUT."""
    try:
        p = subprocess.run(["git", "-C", workdir, *args], input=stdin,
                           capture_output=True, timeout=_TIMEOUT)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return 127, b"", b""
    return p.returncode, p.stdout, p.stderr


def _blobs(workdir: str, rels: list[str]) -> dict[str, str]:
    """Content hash of each working-tree file, '?' where unreadable or unknown.

    ONE `git hash-object --stdin-paths` for the lot (ADV6-5: one fork per path
    was 1,500 forks for 1,500 untracked files, each allowed _TIMEOUT).
    """
    out = {rel: "?" for rel in rels}
    ok = [rel for rel in rels if "\n" not in rel and "\r" not in rel
          and os.path.isfile(os.path.join(workdir, rel))]
    if not ok:
        return out
    stdin = "".join(rel + "\n" for rel in ok).encode("utf-8", "surrogateescape")
    rc, stdout, _ = _run(workdir, "hash-object", "--stdin-paths", stdin=stdin)
    shas = stdout.decode("ascii", "replace").split()
    if rc == 0 and len(shas) == len(ok):
        out.update(zip(ok, shas))
    return out


def _blob(workdir: str, rel: str) -> str:
    return _blobs(workdir, [rel])[rel]


_NOT_A_REPO = object()


def _status(workdir: str):
    """`git status --porcelain=v2 --branch -z --untracked-files=all`, parsed once.

    Returns (head, branch, paths); `_NOT_A_REPO`; or None when git failed or
    timed out (unknown, never clean).
    """
    rc, out, err = _run(workdir, "status", "--porcelain=v2", "--branch", "-z",
                        "--untracked-files=all")
    if rc != 0:
        return _NOT_A_REPO if rc == 128 and b"not a git repository" in err else None
    head = branch = None
    paths: list[str] = []
    entries = out.split(b"\0")
    i = 0
    while i < len(entries):
        e = entries[i].decode("utf-8", "surrogateescape")
        i += 1
        if e.startswith("# branch.oid "):
            v = e[len("# branch.oid "):]
            head = None if v == "(initial)" else v
        elif e.startswith("# branch.head "):
            v = e[len("# branch.head "):]
            branch = "HEAD" if v == "(detached)" else v
        elif e[:2] in ("1 ", "u "):
            paths.append(e.split(" ", 8 if e[0] == "1" else 10)[-1])
        elif e[:2] == "2 ":
            paths.append(e.split(" ", 9)[-1])
            i += 1                              # the rename's origin path
        elif e[:2] == "? ":
            paths.append(e[2:])
    return head, branch, paths


def _porcelain_paths(workdir: str) -> list[str]:
    """Every path git status considers changed or untracked, NUL-safe."""
    st = _status(workdir)
    return st[2] if isinstance(st, tuple) else []


def tree_state(workdir: str) -> tuple[str | None, str | None, bool | None] | None:
    """(head, branch, dirty) from ONE git status; dirty None when git could not
    say; None outside a repository. What `checkpoint` prints, and all it needs."""
    st = _status(workdir)
    if st is _NOT_A_REPO:
        return None
    if st is None:
        return None, None, None
    head, branch, paths = st
    return head, branch, bool(paths)


def path_state(path: str):
    """ONE `git status --porcelain -- <path>`, run from the file's own directory (packet
    S22): the XY code of its line ('' when git reads none, '??' untracked); None when
    git failed or timed out (unknown, never clean); `_NOT_A_REPO` outside a work tree."""
    d, name = os.path.split(os.path.abspath(path))
    rc, out, err = _run(d, "status", "--porcelain", "--untracked-files=all", "--",
                        ":(literal)" + name)
    if rc != 0:
        return _NOT_A_REPO if rc == 128 and b"not a git repository" in err else None
    line = out.decode("utf-8", "surrogateescape").split("\n", 1)[0]
    return line[:2] if line else ""


def baseline(workdir: str) -> Baseline:
    """At most two git calls: one status, one hash-object for every dirty file."""
    st = _status(workdir)
    if st is _NOT_A_REPO:
        return Baseline(None, None, False, False)
    if st is None:
        return Baseline(None, None, None, True)
    head, branch, paths = st
    return Baseline(head, branch, bool(paths), True, _blobs(workdir, paths))


def _untracked(workdir: str) -> list[str]:
    """Untracked FILES, recursing into untracked directories.

    Plain --porcelain C-quotes names with spaces or non-ASCII, and collapses a
    new directory to `dir/`, so a run whose whole output is a new package
    reported no new-file content. -z gives NUL-separated raw paths, and
    --untracked-files=all lists the files inside new directories.
    """
    try:
        p = subprocess.run(
            ["git", "-C", workdir, "status", "--porcelain", "-z", "--untracked-files=all"],
            capture_output=True, timeout=_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []
    out: list[str] = []
    for entry in p.stdout.split(b"\0"):
        if entry.startswith(b"?? "):
            out.append(entry[3:].decode("utf-8", "surrogateescape"))
    return out


@dataclass
class Changes:
    patch: str = ""
    stat: str = ""
    commits: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)   # pre-existing, untouched
    truncated: bool = False
    note: str | None = None

    @property
    def empty(self) -> bool:
        return not (self.patch.strip() or self.commits or self.untracked)


def changes_since(workdir: str, pre_sha: str | None,
                  pre_dirty: dict[str, str] | None = None) -> Changes:
    """Everything the RUN did: commits, tracked edits, new files -- minus what
    was already dirty before it started.

    A path that was dirty before and has the same content hash after was the
    user's, not the run's, and is excluded. A path that was dirty before and
    changed is the run's (it edited it). This is what lets NO-OP be true on a
    dirty tree, and keeps the user's half-finished edit out of the report.
    """
    pre_dirty = pre_dirty or {}
    if not is_repo(workdir):
        return Changes(note="not a git repo" if git_available() else "git unavailable")
    if not pre_sha:
        # A repo with no commits yet: everything is untracked.
        return Changes(untracked=_untracked(workdir),
                       note="no pre-run commit to diff against")

    ch = Changes()
    # Paths the user already had dirty and the run did not touch: same blob.
    known = [rel for rel, sha in pre_dirty.items() if sha != "?"]
    now = _blobs(workdir, known)
    unchanged_pre = {rel for rel in known if now[rel] != "?" and now[rel] == pre_dirty[rel]}
    ch.excluded = sorted(unchanged_pre)

    # Diff everything, then exclude those paths with git's own pathspec syntax.
    exclude = [f":(exclude){rel}" for rel in unchanged_pre]
    rc, ch.patch = _git(workdir, "diff", pre_sha, "--", ".", *exclude) if exclude \
        else _git(workdir, "diff", pre_sha)
    if rc != 0:
        ch.note = f"git diff {pre_sha[:8]} failed (commit gone? branch switched?)"
        ch.patch = ""
    _, ch.stat = (_git(workdir, "diff", "--stat", pre_sha, "--", ".", *exclude) if exclude
                  else _git(workdir, "diff", "--stat", pre_sha))
    _, log = _git(workdir, "log", "--oneline", f"{pre_sha}..HEAD")
    ch.commits = [l for l in log.splitlines() if l.strip()]
    ch.untracked = [u for u in _untracked(workdir) if u not in unchanged_pre]

    # `git diff <sha>` never shows untracked content. Append it explicitly --
    # for a run whose whole output is new files, the patch is otherwise empty.
    for rel in ch.untracked:
        path = os.path.join(workdir, rel)
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > config.MAX_UNTRACKED_DIFF_BYTES:
                continue
        except OSError:
            continue
        rc2, extra = _git(workdir, "diff", "--no-index", "--", os.devnull, rel)
        if extra.strip():
            ch.patch += ("\n" if ch.patch and not ch.patch.endswith("\n") else "") + extra

    if len(ch.patch) > config.MAX_PATCH_BYTES:
        ch.patch = ch.patch[: config.MAX_PATCH_BYTES] + "\n... [patch truncated]\n"
        ch.truncated = True
    return ch
