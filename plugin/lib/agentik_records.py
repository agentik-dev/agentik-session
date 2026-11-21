"""agentik_records: where a repo's working records are (hq design/28 §3 items 1 to 6, §11;
GUIDE §12). Canonical in agentik-commons; `scripts/sync` places it at plugin/lib/agentik_records.py,
byte-identical in every tool, under vendored.sha256. Standard library, Python 3.9.

`resolve(start)` answers the `agentik.records/1` object for the folder `start`: `repo`, the main
checkout, as git names it; `records`, the folder that holds the records; `holder`, the top of the
git repository whose working folder holds `records`, or None; `prefix`, `records` relative to
`holder`; `state`; and `why`. The states:

- `own`: no key, and the tree does not declare `out`. `records` and `holder` are the top of the
  working tree `start` stands in, so a worktree answers its own top; `prefix` is `.`.
- `out`: the key resolves; `records` is its folder.
- `unset`: the tree declares `out` and the clone has no key; `why` is `no-key`.
- `broken`: the key is set and does not resolve; no records folder is answered, and `why` is one
  of `unread`, `many`, `relative`, `missing`, `inside`, `name` or `holder`.

The key is `agentik.records` in the clone's own config: never the user's file, the environment or
a worktree's own file. It is set when `git config --local --get-all agentik.records` finds it, and
read as `git config --local --path --get agentik.records`; a key that is set and that read cannot
give is `unread`, and a key set more than once is `many`, so a set key is never `own` or `unset`.
It resolves when it is absolute, an existing folder, outside the main checkout and every worktree
of the clone (no folder from it up to the root is the same file as one of their tops, so no
spelling of a path, in case or through a link, gets in), named as the main checkout's folder is
on disk, in no repository that shares the clone's git folder, and in a holder whose tree does not
declare `out` itself. The declaration is the whole line `records: out` in `.hygiene-allow`, read
from the file at HEAD through git; a line in an untracked, uncommitted or local file declares
nothing. Git runs as `git --no-replace-objects -C <folder>`, never in the current directory,
so a replace ref moves no answer, as it moves none of the scanner's, with the repository's
own environment variables dropped. `NoRepo` is raised where `start` is no folder, git is absent,
or `start` stands in no git working tree. `values(start)` gives the key's values as the clone's
config holds them, for a tool to name in its `broken` line. It writes nothing.
"""
import os
import subprocess

SCHEMA = "agentik.records/1"
KEY = "agentik.records"
DECLARED = ((".hygiene-allow", "records: out"),)
# `git rev-parse --local-env-vars`, and the environment's config items: a hook's GIT_DIR would
# answer for another repository than the folder named
LOCAL_ENV = ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
             "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
             "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
             "GIT_INTERNAL_SUPER_PREFIX", "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")


class NoRepo(Exception):
    """`start` is no folder, git is absent, or `start` stands in no git working tree."""


def _env():
    return {k: v for k, v in os.environ.items()
            if k not in LOCAL_ENV and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}


def _git(folder, *args):
    """(exit, stdout less its last newline) of git run in `folder`; (None, "") with no git."""
    try:
        p = subprocess.run(["git", "--no-replace-objects", "-C", folder] + list(args), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_env())
    except OSError:
        return None, ""
    out = os.fsdecode(p.stdout)
    return p.returncode, out[:-1] if out.endswith("\n") else out


def _values(start):
    """(exit, values) of the key in the clone's own config, as written there: exit 1 is no key."""
    code, text = _git(start, "config", "--local", "-z", "--get-all", KEY)
    return code, text.split("\0")[:-1] if code == 0 else []


def values(start):
    """The key's values as the clone's own config holds them, unexpanded; [] with none or no repo."""
    return _values(os.path.realpath(start))[1] if os.path.isdir(start) else []


def _declares(top):
    """True where the tree at `top` declares `out` in a tracked file at HEAD."""
    for path, line in DECLARED:
        code, text = _git(top, "cat-file", "-p", "HEAD:" + path)
        if code == 0 and any(row.rstrip() == line for row in text.splitlines()):
            return True
    return False


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _inside(path, tops):
    """True where `path`, or a folder above it, is the same file as one of `tops`."""
    ids = set()
    for top in tops:
        try:
            st = os.stat(top)
        except OSError:
            continue
        ids.add((st.st_dev, st.st_ino))
    while True:
        try:
            st = os.stat(path)
            if (st.st_dev, st.st_ino) in ids:
                return True
        except OSError:
            pass
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def _name(path):
    """The last name of the folder `path` as its parent lists it: on a file system blind to case,
    a real path keeps the case it was typed in."""
    parent, name = os.path.split(path)
    try:
        names = os.listdir(parent)
    except OSError:
        return name
    if name in names:
        return name
    return next((n for n in names if _same(os.path.join(parent, n), path)), name)


def _answer(repo, state, why=None, records=None, holder=None, prefix=None):
    return {"schema": SCHEMA, "repo": repo, "records": records, "holder": holder, "prefix": prefix,
            "state": state, "why": why}


def resolve(start):
    if not os.path.isdir(start):
        raise NoRepo(start)
    start = os.path.realpath(start)
    code, top = _git(start, "rev-parse", "--show-toplevel")
    if code != 0 or not top:
        raise NoRepo(start)
    top = os.path.realpath(top)
    code, common = _git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    code_list, listing = _git(start, "worktree", "list", "--porcelain", "-z")
    trees = [os.path.realpath(item[len("worktree "):]) for item in listing.split("\0")
             if item.startswith("worktree ")]
    if code != 0 or not common or code_list != 0 or not trees:
        raise NoRepo(start)
    common = os.path.realpath(common)
    repo = trees[0]  # the main checkout, or the bare folder, as git names it
    code, held = _values(start)
    if code == 1:
        if _declares(top):
            return _answer(repo, "unset", "no-key")
        return _answer(repo, "own", records=top, holder=top, prefix=".")
    if code != 0:
        return _answer(repo, "broken", "unread")
    if len(held) > 1:
        return _answer(repo, "broken", "many")
    code, value = _git(start, "config", "--local", "--path", "--get", KEY)
    if code != 0:
        return _answer(repo, "broken", "unread")
    if not os.path.isabs(value):
        return _answer(repo, "broken", "relative")
    records = os.path.realpath(value)
    if not os.path.isdir(records):
        return _answer(repo, "broken", "missing")
    if _inside(records, [repo, top] + trees):
        return _answer(repo, "broken", "inside")
    if _name(records) != _name(repo):
        return _answer(repo, "broken", "name")
    code, holder = _git(records, "rev-parse", "--show-toplevel")
    if code != 0 or not holder:
        return _answer(repo, "out", records=records)
    code, theirs = _git(records, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if code == 0 and theirs and _same(theirs, common):
        return _answer(repo, "broken", "inside")
    holder = os.path.realpath(holder)
    if _declares(holder):
        return _answer(repo, "broken", "holder")
    return _answer(repo, "out", records=records, holder=holder, prefix=os.path.relpath(records, holder))
