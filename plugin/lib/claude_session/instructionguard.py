"""The edit gates (packet g2b; hq design/09 §7.2; packet g4, hq design/12 §3.2).

R1: a file is gated when a list names it, in three layers: the checkout's tracked
`.claude/edit-gates` (a path or glob a line, relative to the top level, the nearest folder above
the target holding `.git`, a worktree's own; `#` a comment); g4, each folder's
`<folder>/.claude/edit-gates` above the checkout (or above the file, in no checkout) and strictly
inside the home folder, its lines relative to its folder, a folder inside a checkout holding
none, a path in `<member>/.claude/worktrees/<n>/` matched as `<member>/<rel>`; and the user's
`edit-gates` in `CLAUDE_CONFIG_DIR`, else `~/.claude` (its lines absolute or `~/`). In a
checkout's or a folder's list a line starting with `/` or `~`, or holding a `..` part, matches
nothing. Every list file is always gated. One grammar in every layer (g4, F8): `*`, `?` and a
bracket match within one path segment; a segment that is `**` matches any depth, none included;
a line with no glob is one file. A target's absolute and real paths are both matched, case
folded where the volume folds case. Every other file passes in silence, with no log line.

R2: `Edit`, `Write`, `MultiEdit` and `NotebookEdit` of a gated file, and (g3) a Bash line that
writes one, are denied in every permission mode and every run, with one reason that routes the
model to the instruct skill. The gate never asks: the `auto` mode approved a hook's ask with no
dialog (the owner's test of 2026-11-12). The lane writes a gated file with `gates write`.

R3, g3: a Bash line holding no write word costs one regex search and opens no file. Otherwise
`shlex` splits it into simple commands, in the reader both readings live in since g7
(`shellreader.py`); the targets are redirections (a heredoc's own included),
`tee`, `sed -i`, `perl -i`, `cp`, `mv` and `install` (their last word or `-t` folder), one level
of `bash -c` or `sh -c`, after a literal `cd`, and string literals in `python -c` code, or a
`python -` heredoc body, that also holds `open(` or `write_`. A list file's removal (`rm`,
`unlink`, `git rm`, `git checkout --`, `git restore`, `mv` from it) is refused too. A target
with `$`, a backquote or a glob, and a line `shlex` cannot split, pass: the gate fails open.
g6: a second, loose reading blind to quotes, comments and heredocs (`loose_targets`) lists every
target a line might have; one the strict reading did not resolve to the same path is resolved
against the call's folder, its own (moved by a `cd` only on a plain line) and each folder the
strict reading stood in, and a gated one is denied with its own reason. So a line the strict
reading cannot split, a `cd` it cannot resolve, and text that holds a write (a heredoc body, a
quoted line, a commit message naming the file after a write word) are refused when the loose
reading's word is gated; what passes is a target neither reading resolves, a gated file a
command neither knows writes (`dd`, `ln`, `truncate`, a script, a name in a variable), and a
`cd` the strict reading wrongly follows on a plain line (`false && cd /tmp; ...`).

R4: an exception lets the call through with one `open` line in the session's `guard.jsonl`;
each refusal is a line there too, naming a helper by the payload's `agent_id`.

gc1, the outcome: a line neither reading can read whole (it cannot be split, or a target cannot
be resolved) and that neither denies logs nothing; before it runs, the files the lists in force
at the call's folder name by a plain path, and those lists, are read into
`sessions/<sid>/guard-open/<tool_use_id>.json` (sha256, or size and mtime past 1 MiB, or absent;
at most 64). Its PostToolUse or PostToolUseFailure reads them again and removes the file; each
path that differs is one `changed` line, said once to the model and the owner. It never blocks
and never restores. No knob: the
environment is read for `HOME` and `CLAUDE_CONFIG_DIR` and the state root, nothing else. No
process is spawned and no launch line is read.
"""
from __future__ import annotations

import errno
import fnmatch
import hashlib
import itertools
import json
import os
import re
import shlex
import stat
import sys
import time
from pathlib import Path

from . import resolver

from .shellreader import _Bound, _home, _loose, _resolve, _strict, _tilde
TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
         "NotebookEdit": "notebook_path", "Bash": "command"}
SKILL = "decision" "s:instruct"           # spelled in two pieces for the hygiene scan
REASON = ("agentik-session: `{path}` is gated: an edit of it is refused in every permission "
          "mode. Make the change through the `" + SKILL + "` skill, which shows the owner the "
          "change and its cost and writes it only on the owner's yes. Do not write the file "
          "another way.")
LOOSE_REASON = ("agentik-session: `{path}` is gated, and this Bash line may write it: the line "
                "was not read with confidence. To change the file use the `" + SKILL + "` "
                "skill, which writes it through `agentik session gates write` on the owner's "
                "yes. A line that only carries such text as data keeps the text in a file and "
                "names the file.")
STRICT, LOOSE = "the strict reading", "the loose reading"   # g6 R3: which reading denied
LIST = "edit-gates"
REPO_LIST = ".claude/" + LIST
LOG = "guard.jsonl"
LOG_CAP = 64 * 1024                       # past this a session's guard log takes no more lines
TEXT_CAP = 1024
LIST_CAP = 64 * 1024                      # a list's bytes read, at most
_PC_CASE_SENSITIVE = 11                   # darwin's pathconf name; Python's table lacks it
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")
_GLOB = frozenset("*?[")


# ---- R1: the lists ----------------------------------------------------------------------

def user_dir(env) -> str:
    moved = env.get("CLAUDE_CONFIG_DIR")
    if moved:
        return _tilde(moved, env) or moved
    return os.path.join(_home(env), ".claude")


def _lines_of(raw: bytes) -> list:
    out = []
    for line in raw.decode("utf-8", "replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def _read_list(path: str, cache: dict) -> list:
    if path not in cache:
        lines = []
        try:
            with open(path, "rb") as f:
                lines = _lines_of(f.read(LIST_CAP))
        except OSError:
            pass
        cache[path] = lines
    return cache[path]


def _relative(s: str) -> str | None:
    """A checkout's or a folder's line as it matches, or None for a line that matches nothing:
    one starting with `/` or `~`, or holding a `..` part (g4 R4)."""
    while s.startswith("./"):
        s = s[2:]
    if not s or s.startswith("/") or s.startswith("~") or ".." in s.split("/"):
        return None
    return s


def _rel_lines(lf: str, cache: dict) -> list:
    return [r for r in map(_relative, _read_list(lf, cache)) if r is not None]


def repo_lines(top: str, cache: dict) -> list:
    """The repo list's lines that can match: relative, no `~` start, no `..` part."""
    return _rel_lines(os.path.join(top, ".claude", LIST), cache)


def _user_raw(env, cache: dict) -> list:
    return [s for s in _read_list(os.path.join(user_dir(env), LIST), cache)
            if s.startswith("/") or s.startswith("~/")]


def user_lines(env, cache: dict) -> list:
    """The user list's lines, absolute: `~/` read against the home folder."""
    return [os.path.normpath(_tilde(s, env)) for s in _user_raw(env, cache)]


def _top(p: str, itself: bool = False) -> str | None:
    """The nearest folder above `p` (or `p`, with `itself`) that holds a `.git`."""
    d = p if itself else os.path.dirname(p)
    while True:
        if os.path.lexists(os.path.join(d, ".git")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def _segments(name: list, pat: list) -> bool:
    memo: dict = {}                       # r1 F2: each (segment, part) answered once

    def at(i: int, j: int) -> bool:
        if (i, j) not in memo:
            if j == len(pat):
                r = i == len(name)
            elif pat[j] == "**":          # any depth, none included
                r = any(at(k, j + 1) for k in range(i, len(name) + 1))
            else:
                r = (i < len(name) and fnmatch.fnmatchcase(name[i], pat[j])
                     and at(i + 1, j + 1))
            memo[(i, j)] = r
        return memo[(i, j)]
    return at(0, 0)


def _match(name: str, pat: str, fold: bool) -> bool:
    """g4 R3, one grammar: `*`, `?` and a bracket stay in one segment, `**` alone is any depth,
    a line with no glob is one file."""
    if fold:
        name, pat = name.casefold(), pat.casefold()
    return name == pat or (bool(_GLOB & set(pat))
                           and _segments(name.split("/"), pat.split("/")))


def _inside(a: str, b: str, fold: bool) -> bool:
    """True when `a` is strictly inside `b`."""
    if fold:
        a, b = a.casefold(), b.casefold()
    return a.startswith(b.rstrip("/") + "/") and a != b


def _homes(env) -> set:
    h = _home(env)
    return {os.path.abspath(h), os.path.realpath(h)}


def _in_home(p: str, homes: set, fold: bool) -> bool:
    return any(_inside(p, h, fold) for h in homes)


def _same(a: str, b: str, fold: bool) -> bool:
    return a.casefold() == b.casefold() if fold else a == b


def folder_lists(p: str, env, cache: dict, fold: bool = False, itself: bool = False) -> list:
    """g4 R1: the folder lists that apply to `p` (to the folder `p`, with `itself`), nearest
    first, each `(folder, its lines, the path its lines are matched against)`. The walk starts
    above the checkout (above the member, for a path in `<member>/.claude/worktrees/<n>/`,
    matched as `<member>/<rel>`), or above the file in no checkout, and stops below the home
    folder; a folder inside a checkout holds no folder list. Only files that exist are read."""
    homes = _homes(env)
    if not _in_home(p, homes, fold):
        return []
    start, vp = (p if itself else os.path.dirname(p)), p
    top = _top(p, itself)
    if top is not None and _in_home(top, homes, fold):
        start = os.path.dirname(top)
        up = start
        if (_same(os.path.basename(up), "worktrees", fold)
                and _same(os.path.basename(os.path.dirname(up)), ".claude", fold)):
            member = os.path.dirname(os.path.dirname(up))        # g4 R2: by its spelling
            start, vp = os.path.dirname(member), member + p[len(top):]
    dirs = []
    d = start
    while _in_home(d, homes, fold):
        dirs.append(d)
        d = os.path.dirname(d)
    gits = [os.path.lexists(os.path.join(x, ".git")) for x in dirs]
    out = []
    for i, d in enumerate(dirs):
        lf = os.path.join(d, ".claude", LIST)
        if any(gits[i + 1:]) or not os.path.lexists(lf):
            continue
        out.append((d, _rel_lines(lf, cache), vp))
    return out


def _folder_list_at(p: str, env, fold: bool) -> str | None:
    """g4 R5: the folder `d` when `p` is `<d>/.claude/edit-gates`, `d` strictly inside the home
    folder and inside no checkout but its own; None otherwise."""
    up = os.path.dirname(p)
    if not (_same(os.path.basename(p), LIST, fold)
            and _same(os.path.basename(up), ".claude", fold)):
        return None
    d = os.path.dirname(up)
    homes = _homes(env)
    if not _in_home(d, homes, fold):
        return None
    e = os.path.dirname(d)
    while _in_home(e, homes, fold):
        if os.path.lexists(os.path.join(e, ".git")):
            return None
        e = os.path.dirname(e)
    return d


def _folder_list_of(path: str, env) -> str | None:
    """r1 F1: the folder whose list `path` names, by every spelling `gated()` reads: the
    absolute spelling and the real path, each folded where the volume folds case."""
    forms = list(dict.fromkeys((os.path.abspath(path), os.path.realpath(path))))
    for fold in (False, True):
        for p in forms:
            if fold and not _case_blind(p):
                continue
            d = _folder_list_at(p, env, fold)
            if d is not None:
                return d
    return None


def _gated_form(p: str, env, cache: dict, fold: bool) -> bool:
    top = _top(p)
    if top is not None:
        rel = p[len(top):].lstrip("/")
        if _match(rel, REPO_LIST, fold) or any(_match(rel, pat, fold)
                                               for pat in repo_lines(top, cache)):
            return True
    if _folder_list_at(p, env, fold) is not None:
        return True
    for d, lines, vp in folder_lists(p, env, cache, fold):
        rel = vp[len(d):].lstrip("/")
        if any(_match(rel, pat, fold) for pat in lines):
            return True
    ud = user_dir(env)
    for u in {os.path.abspath(ud), os.path.realpath(ud)}:
        if _match(p, os.path.join(u, LIST), fold):
            return True
    for pat in user_lines(env, cache):
        pats = {pat} if _GLOB & set(pat) else {pat, os.path.realpath(pat)}
        if any(_match(p, q, fold) for q in pats):
            return True
    return False


def _case_blind(path: str) -> bool:
    """True where the volume holding `path` (its nearest existing folder) folds case, so two
    spellings that differ only in case name one file; False where it cannot tell."""
    here = path
    while not os.path.lexists(here):
        up = os.path.dirname(here)
        if up == here:
            return False
        here = up
    if sys.platform == "darwin":
        try:
            return os.pathconf(here, _PC_CASE_SENSITIVE) == 0
        except (OSError, ValueError):
            pass
    probe = here                          # elsewhere: the same entry under its other case
    while True:
        up, name = os.path.split(probe)
        other = name.swapcase()
        if other != name:
            try:
                return os.path.samestat(os.lstat(probe), os.lstat(os.path.join(up, other)))
            except OSError:
                return False
        if up == probe:
            return False
        probe = up


def gated(path: str, env, cache: dict | None = None) -> bool:
    """True for a file a list names, or a list file itself, by its absolute spelling or its
    real path; a spelling that differs only in case where the volume folds case."""
    cache = {} if cache is None else cache
    forms = {os.path.abspath(path), os.path.realpath(path)}
    if any(_gated_form(p, env, cache, False) for p in forms):
        return True
    return any(_gated_form(p, env, cache, True) and _case_blind(p) for p in forms)


def _under(a: str, b: str, fold: bool) -> bool:
    """True when `a` is `b` or inside it."""
    if fold:
        a, b = a.casefold(), b.casefold()
    return a == b or a.startswith(b.rstrip("/") + "/")


def _removes_list(t: str, env, cache: dict) -> str | None:
    """The list file that removing or moving `t` takes away, if any: its checkout's list (`t`
    inside that checkout, never the checkout itself), or the user's."""
    for p in {os.path.abspath(t), os.path.realpath(t)}:
        for fold in (False, True):
            if fold and not _case_blind(p):
                continue
            top = _top(p, itself=True)
            if top is not None and not _under(top, p, fold):
                lf = os.path.join(top, ".claude", LIST)
                if _under(lf, p, fold):
                    return lf
            ud = user_dir(env)
            for u in {os.path.abspath(ud), os.path.realpath(ud)}:
                lf = os.path.join(u, LIST)
                if _under(lf, p, fold):
                    return lf
            lf = _folder_list_removed(p, env, fold)
            if lf is not None:
                return lf
    return None


def _folder_list_removed(p: str, env, fold: bool) -> str | None:
    """g4 R5: the folder list that removing `p` takes away, when `p` is the list or its
    `.claude` folder (never the folder itself, as for a checkout) and the list exists."""
    if _same(os.path.basename(p), ".claude", fold):
        d = os.path.dirname(p)
    elif (_same(os.path.basename(p), LIST, fold)
          and _same(os.path.basename(os.path.dirname(p)), ".claude", fold)):
        d = os.path.dirname(os.path.dirname(p))
    else:
        return None
    lf = os.path.join(d, ".claude", LIST)
    if os.path.lexists(lf) and _folder_list_at(lf, env, fold) is not None:
        return lf
    return None


# ---- R3, g3: the Bash line --------------------------------------------------------------

_WRITE_WORD = re.compile(r">|\b(?:tee|sed|perl|cp|mv|install|python[0-9.]*|rm|unlink|git)\b")


def _loose_gated(command: str, cwd, env, cache: dict, found: list, stood: set):
    """The first gated path (a list file, for a removal) of a loose target the strict reading
    did not judge in the same place (g6 R2); None when there is none it can resolve."""
    loose = _loose(command)
    judged: dict = {}
    owns, at = [cwd], []                  # r1 R4: each `cd` resolved once, each target once
    for kind, word, moves, _ in loose:
        for c in (moves or ())[len(owns) - 1:]:
            owns.append(_resolve(c, owns[-1], env) if c is not None and owns[-1] else None)
        at.append(owns[len(moves)] if moves is not None else cwd)
    spent = _spent(loose, at, found, cwd, env)
    for kind, path, word, _ in found:
        if kind in ("write", "remove") and path is not None and word and len(word.split()) < 2:
            judged[kind, path] = judged.get((kind, path), 0) + 1
    left = []
    for i, (kind, word, moves, _) in enumerate(loose):
        if i in spent:
            continue
        own = at[i]
        key = (kind, _resolve(word, own or cwd, env))
        if key[1] is not None and judged.get(key):
            judged[key] -= 1
            continue
        left.append((kind, word, own))
    left = list(dict.fromkeys(left))
    folders = list(dict.fromkeys([cwd] + sorted(f for f in stood if f)))
    if len(left) * (len(folders) + 1) > _LOOSE_BOUND:   # a write it cannot afford to read
        kind, word, own = left[0]
        return _resolve(word, own or cwd, env) or word
    tried: set = set()
    for kind, word, own in left:
        for f in dict.fromkeys([cwd, own] + folders):
            p = _resolve(word, f, env) if f else None
            if p is None or (kind, p) in tried:
                continue
            tried.add((kind, p))
            if kind == "write" and gated(p, env, cache):
                return p
            if kind == "remove":
                lf = _removes_list(p, env, cache)
                if lf is not None:
                    return lf
    return None


_RUN_CAP = 16                             # r1 R3: a word of more pieces stands for none
_LOOSE_BOUND = 4096                       # r1 R4: loose targets left times folders, at most


def _spent(loose: list, at: list, found: list, cwd, env) -> set:
    """The loose targets a strict word with a blank stands for (r1 R3): only whole, every piece
    in order, one command's targets of its kind, each loose target once; a word whose pieces
    the loose reading did not list together stands for none, so no piece is left to spend.
    A run stands for it only where the run's folder (`at`) resolves the run to the path the
    strict reading judged, as db19d51's credit was keyed by the path (r2 R5)."""
    want: dict = {}
    shapes: set = set()
    for kind, path, word, _ in found:
        pieces = tuple(word.split()) if path is not None and word else ()
        if 1 < len(pieces) < _RUN_CAP and kind in ("write", "remove"):
            want[kind, pieces, path] = want.get((kind, pieces, path), 0) + 1
            shapes.add((kind, pieces))
    spent: set = set()
    for k in sorted({len(p) for _, p in shapes}):
        for i in range(len(loose) - k + 1):
            run = loose[i:i + k]
            shape = (run[0][0], tuple(r[1] for r in run))
            if shape not in shapes or run[0][3] != run[-1][3] or \
                    any(r[0] != shape[0] for r in run) or spent.intersection(range(i, i + k)):
                continue
            key = shape + (_resolve(" ".join(shape[1]), at[i] or cwd, env),)
            if want.get(key):
                want[key] -= 1
                spent.update(range(i, i + k))
    return spent


def _bash_gated(payload: dict, env):
    """(the first gated target of a Bash line, a list file for a removal; the reading that
    found it), or None when it has none the gate can read."""
    ti = payload.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(command, str) or not (_WRITE_WORD.search(command) or
                                            _WRITE_WORD.search(command.replace("\\\n", ""))):
        return None                       # g6 R4: `c\` newline `p` is a `cp`
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and os.path.isabs(cwd) and "\0" not in cwd else None
    stood: set = set()
    try:
        found, raised = _strict(command, cwd, env, 0, False, True, stood), False
    except ValueError:                    # an open quote: the loose reading alone (g6 R2)
        found, raised = [], True
    except _Bound as b:                   # r2 R1: past the bound, denied unread
        return b.path, STRICT
    cache: dict = {}
    unresolved = split = False
    seen: set = set()
    for kind, path, _, _ in found:
        if kind == "split":
            split = True
            continue
        if path is None:
            unresolved = True
            continue
        if (kind, path) in seen:          # one answer a path: a long line costs no more
            continue
        seen.add((kind, path))
        if kind == "write" and gated(path, env, cache):
            return path, STRICT
        if kind == "remove":
            lf = _removes_list(path, env, cache)
            if lf is not None:
                return lf, STRICT
    loose = _loose_gated(command, cwd, env, cache, found, stood)
    if loose is not None:
        return loose, LOOSE
    if raised or split or unresolved:     # gc1 R1: not all read; held by the outcome instead
        try:
            before(payload, env, cwd)
        except Exception as e:                          # noqa: BLE001 - R5: a guard error
            log(payload, env, "open", None, why=type(e).__name__)
    return None


# ---- R4: the log ------------------------------------------------------------------------

def _text(v) -> str | None:
    return v[:TEXT_CAP] if isinstance(v, str) else None


def log(payload: dict, env, decision: str, path, why=None, rule=None, call=None) -> None:
    """One line in `sessions/<sid>/guard.jsonl` (0600); a line that would carry the log past
    LOG_CAP is not written. Never raises. `rule` (g8: the rules' names) and `call` (gc1: the
    tool call's id, on a `changed` line) are written only when given."""
    try:
        sid = payload.get("session_id")
        if not (isinstance(sid, str) and _SID.match(sid)):
            return
        row = {"at": time.time(), "decision": decision, "tool": _text(payload.get("tool_name")),
               "path": _text(path), "agent_id": _text(payload.get("agent_id")), "why": _text(why)}
        if rule is not None:
            row["rule"] = [_text(r) for r in rule]
        if call is not None:
            row["call"] = _text(call)
        line = (json.dumps(row, ensure_ascii=False) + "\n").encode()
        sdir = resolver.session_dir(resolver.state_dir(env), sid)
        sdir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(sdir / LOG), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                     0o600)
        try:
            if os.fstat(fd).st_size + len(line) <= LOG_CAP:
                os.write(fd, line)
        finally:
            os.close(fd)
    except Exception:                                   # noqa: BLE001 - a log never fails a hook
        pass


# ---- gc1: the outcome of a line the gate cannot read ----------------------------------------

OPEN_DIR = "guard-open"                   # sessions/<sid>/guard-open/<tool_use_id>.json
RECORD_CAP = 64                           # files read before one line, at most
BIG = 1 << 20                             # past this a file is read by its size and mtime
LEFTOVER = 86400                          # R4: a call's file older than this is removed
RETIRED = ("the line cannot be split", "a target cannot be resolved")   # R5: old logs' reasons
SAID_DIR = "guard-said"                   # brief 3 H1: sessions/<sid>/guard-said/<name>.said
SAID_READ = 256                           # H2: the entries one saying reads, at most
SAID_LOOK = 4 * SAID_READ                 # H2: the entries one saying looks at, temps included
SAID_CAP = 65536                          # H2: a waiting file's bytes, at most
TEMP_AGE = 60                             # H3: a waiting folder's temp older than this goes
_SEQ = itertools.count()                  # H1: a waiting file's name, unique to this process
_OWN = re.compile(r"[0-9]+-[0-9]+-[0-9]+\.said\Z")              # J2: the names the check gives
_OWN_TEMP = re.compile(r"\.[0-9]+-[0-9]+-[0-9]+\.said\.[0-9]+\.tmp\Z")
UNFIT = ".unfit"                          # J3: beside a folder that is no folder, once logged
SAID = ("agentik-session: {shown} is gated and changed during a Bash line the gate could not "
        "read. If that line ran the lane, nothing is wrong. Otherwise restore it and use the "
        "instruct skill.")
SAID_OWNER = "agentik-session: a gated file changed during a Bash line the gate could not read: {shown}"
PAIR_CAP = 480                            # F2: the pair beside an empty output, in JSON bytes
DRAWN = 48                                # F2: a longer path is `…` and its last DRAWN - 1


def _in_force(cwd, env) -> list:
    """The files read before an unread line: the lists in force at `cwd` that exist (the
    checkout's, each folder's, the user's), then each file they name by a plain path, in that
    order, at most RECORD_CAP. In a worktree a folder's line is read in the member and in the
    worktree both."""
    cache: dict = {}
    lists, named = [], []
    here = os.path.abspath(cwd) if cwd else None
    top = _top(here, itself=True) if here else None
    if top is not None:
        lists.append(os.path.join(top, ".claude", LIST))
        named += [os.path.join(top, r) for r in repo_lines(top, cache)]
    for d, lines, vp in (folder_lists(here, env, cache, itself=True) if here else []):
        lists.append(os.path.join(d, ".claude", LIST))
        member = (vp[:len(vp) - (len(here) - len(top))]
                  if top is not None and vp != here else None)
        for r in lines:
            p = os.path.join(d, r)
            named.append(p)
            if member is not None and p.startswith(member.rstrip("/") + "/"):
                named.append(top + p[len(member):])
    lists.append(os.path.join(user_dir(env), LIST))
    named += user_lines(env, cache)
    out = [os.path.normpath(p) for p in lists if os.path.lexists(p)]
    out += [os.path.normpath(p) for p in named if not _GLOB & set(p)]
    return list(dict.fromkeys(out))[:RECORD_CAP]


def _reading(path: str) -> list:
    """One file's reading: `["sha256", hex]`, `["size", bytes, mtime_ns]` past BIG,
    `["absent"]`, or `["other"]` for what is no regular file or cannot be opened."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except (FileNotFoundError, NotADirectoryError):
        return ["absent"]
    except OSError:
        return ["other"]
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return ["other"]
        if st.st_size > BIG:
            return ["size", st.st_size, st.st_mtime_ns]
        h = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                return ["sha256", h.hexdigest()]
            h.update(chunk)
    finally:
        os.close(fd)


def _call_id(payload: dict) -> str | None:
    tid = payload.get("tool_use_id")
    return tid if isinstance(tid, str) and _SID.match(tid) else None


def _open_dir(payload: dict, env) -> Path | None:
    sid = payload.get("session_id")
    if not (isinstance(sid, str) and _SID.match(sid)):
        return None
    return resolver.session_dir(resolver.state_dir(env), sid) / OPEN_DIR


def _prune(folder: Path, now: float) -> None:
    """R4: a call's file (or a temp) older than LEFTOVER is removed, unread."""
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        if name.endswith(".json") or name.endswith(".tmp"):
            try:
                if os.lstat(folder / name).st_mtime < now - LEFTOVER:
                    os.remove(folder / name)
            except OSError:
                pass


def _write_record(folder: Path, name: str, doc: dict, prune: bool = True) -> None:
    """`folder/name` written whole by rename from a temp in the folder (0600, the folder 0700,
    made with its parents), after the leftovers' prune; tried once more, its folder made again,
    where the first try fails (brief 3 H4). Raises on the second failure."""
    data = json.dumps(doc, ensure_ascii=False).encode()
    for again in (False, True):
        tmp = folder / f".{name}.{os.getpid()}.tmp"
        try:
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            if prune:
                _prune(folder, time.time())
            fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
            finally:
                os.close(fd)
            os.replace(tmp, folder / name)
            return
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            if again:
                raise


def before(payload: dict, env, cwd) -> None:
    """R1: the call's file, read before a line the gate cannot read; nothing with no call id
    or nothing to read. Raises on a failed write (the caller's guard error)."""
    tid, folder = _call_id(payload), _open_dir(payload, env)
    if tid is None or folder is None:
        return
    names = _in_force(cwd, env)
    if names and _fit(folder, payload, env):
        _write_record(folder, tid + ".json", {"at": time.time(), "cwd": cwd,
                                              "files": [[p, _reading(p)] for p in names]})


def _small(path, cap: int) -> tuple:
    """(bytes, None) for a regular file of at most `cap` bytes; (None, why) for anything else;
    (None, None) where nothing is there. Opened so it cannot block and follows no link (H2)."""
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except (FileNotFoundError, NotADirectoryError):
        return None, None
    except OSError as e:
        return None, "a link" if e.errno == errno.ELOOP else type(e).__name__
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None, "no regular file"
        if st.st_size > cap:
            return None, "too large"
        raw = b""
        while len(raw) <= cap:
            chunk = os.read(fd, cap + 1 - len(raw))
            if not chunk:
                return raw, None
            raw += chunk
        return None, "too large"
    except OSError as e:
        return None, type(e).__name__
    finally:
        os.close(fd)


def _fit(folder: Path, payload: dict, env) -> bool:
    """J3: whether `folder` may be used: a real folder by `lstat`, or nothing yet (made when
    written). Anything else, a link to a folder included, is never listed, read, written or
    removed, and is one guard error a session: logged by the hook that makes the marker
    `<folder>.unfit` beside it."""
    try:
        if stat.S_ISDIR(os.lstat(folder).st_mode):
            return True
    except FileNotFoundError:
        return True
    except OSError:
        pass
    try:
        os.close(os.open(str(folder) + UNFIT,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
    except FileExistsError:
        return False
    except OSError:
        pass
    log(payload, env, "open", None, why=f"{folder.name} is no folder")
    return False


def _remove(path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _drop(path) -> None:
    """A bad entry removed where it can be: an empty folder by `rmdir`, else by `remove`; a
    folder that holds anything stays (no hook removes a tree)."""
    try:
        if stat.S_ISDIR(os.lstat(path).st_mode):
            os.rmdir(path)
        else:
            os.remove(path)
    except OSError:
        pass


def _compare(payload: dict, env, path: Path) -> list:
    """R2: the call's file claimed (removed), its files read again; each change one `changed`
    line. The changed files' real paths (F3), one a file however it was spelled."""
    raw, why = _small(path, BIG)
    if raw is None:
        if why is not None:
            _drop(path)
        return []
    try:
        os.remove(path)
    except OSError:
        return []
    try:
        doc = json.loads(raw)
    except ValueError:
        return []
    out: list = []
    for row in (doc.get("files") if isinstance(doc, dict) else None) or []:
        if not (isinstance(row, list) and len(row) == 2 and isinstance(row[0], str)):
            continue
        real = os.path.realpath(row[0])
        if real not in out and _reading(row[0]) != row[1]:
            log(payload, env, "changed", real, call=_call_id(payload))
            out.append(real)
    return out


class Waiting(list):
    """The paths that wait to be said, and `files`, the waiting files they were read from: the
    files `taken` removes once the paths are in an output (H2)."""
    files: tuple = ()


def _hold(folder: Path, paths: list) -> None:
    """H1: `paths`, one change, as its own waiting files, each written once by rename; J1: as
    many files as it takes for each to stay within SAID_CAP, so no path is dropped for size.
    Raises."""
    chunks, size = [[]], len(b'{"paths": []}')
    for p in paths:
        n = len(json.dumps(p, ensure_ascii=False).encode()) + 2
        if chunks[-1] and size + n > SAID_CAP:
            chunks.append([])
            size = len(b'{"paths": []}')
        chunks[-1].append(p)
        size += n
    for chunk in chunks:
        name = f"{time.time_ns()}-{os.getpid()}-{next(_SEQ)}.said"
        _write_record(folder, name, {"paths": chunk}, prune=False)


def post(payload: dict, env, take: bool = True) -> list:
    """R2 at a Post: the Bash call's changes logged, then each call's held as its own waiting
    file before anything else (H1). When `take` and the payload is the main thread's, the
    paths that wait (a `Waiting`), still held: `taken` lets their files go once they are in an
    output (H2). A change that cannot be held is a guard error and is said here (H5); a folder
    that is no folder is not used (J3). Never raises: a failure is a guard error."""
    try:
        bash = payload.get("tool_name") == "Bash"
        take = take and not payload.get("agent_id")
        folder = _open_dir(payload, env)
        if folder is None or not (bash or take):
            return []
        tid, said_dir = _call_id(payload), folder.parent / SAID_DIR
        changed = (_compare(payload, env, folder / (tid + ".json"))
                   if bash and tid and _fit(folder, payload, env) else [])
        fit = _fit(said_dir, payload, env)
        stray: list = [] if fit else changed
        if changed and fit:
            try:
                _hold(said_dir, changed)
            except Exception as e:                      # noqa: BLE001 - H5
                log(payload, env, "open", None, why=type(e).__name__)
                stray = changed
        if not take:
            return []
        out = _waiting(said_dir, payload, env) if fit else Waiting()
        out.extend(p for p in stray if p not in out)
        return out
    except Exception as e:                              # noqa: BLE001 - never a failed hook
        log(payload, env, "open", None, why=type(e).__name__)
        return []


def _entry(path, payload: dict, env) -> list | None:
    """H2, J2: one waiting file's paths, read strictly: only `{"paths": [str, ...]}` is one.
    A regular file that is anything else is one guard error and is removed; None. None,
    silently, where it went (another hook took it) or is no longer a regular file."""
    raw, why = _small(path, SAID_CAP)
    if raw is None and why in (None, "a link", "no regular file"):
        return None
    if raw is not None:
        try:
            doc = json.loads(raw)
            paths = doc.get("paths") if isinstance(doc, dict) else None
            if isinstance(paths, list) and all(isinstance(p, str) for p in paths):
                return paths
            why = "no list of paths"
        except ValueError as e:                         # no JSON; no UTF-8
            why = type(e).__name__
    log(payload, env, "open", None, why=f"a bad waiting entry: {why}")
    _remove(path)
    return None


def _waiting(folder: Path, payload: dict, env) -> Waiting:
    """H2: the paths of at most SAID_READ waiting files, and those files; a temp older than
    TEMP_AGE removed on the way. J2: only a regular file (by `lstat`) of the check's own
    naming is looked at, read, counted or removed; every other entry is left as it is, not
    logged. Nothing in the folder can make it wait or raise."""
    out, files = Waiting(), []
    try:
        listing = os.scandir(folder)
    except OSError:
        return out
    now, looked, read = time.time(), 0, 0
    with listing:
        for e in listing:
            if looked >= SAID_LOOK or read >= SAID_READ:
                break
            temp = _OWN_TEMP.match(e.name)
            if not (temp or _OWN.match(e.name)):
                continue
            looked += 1
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            if temp:
                if st.st_mtime < now - TEMP_AGE:
                    _remove(e.path)
                continue
            read += 1
            paths = _entry(e.path, payload, env)
            if paths is not None:
                out.extend(paths)
                files.append(e.path)
    out.files = tuple(files)
    return out


def waiting(payload: dict, env) -> list:
    """The paths that wait to be said, for the main thread's UserPromptSubmit; still held."""
    return post({**payload, "tool_name": None}, env)


def taken(payload: dict, env, paths) -> None:
    """H2: the waiting files `paths` was read from removed, those and no others, once the paths
    are in an output. Never raises: a file another hook took is already gone."""
    for f in getattr(paths, "files", ()):
        try:
            os.remove(f)
        except OSError:
            pass


def _drawn(path: str, env) -> str:
    """F3: a real path, `~/` under the home; H6: a control character `?`; F2: past DRAWN
    characters, `…` and its tail."""
    for home in sorted({os.path.realpath(_home(env)), os.path.abspath(_home(env))}, key=len,
                       reverse=True):
        home = home.rstrip("/")
        if home and path.startswith(home + "/"):
            path = "~/" + path[len(home) + 1:]
            break
    path = "".join("?" if ord(c) < 32 or 127 <= ord(c) < 160 else c for c in path)   # H6
    return path if len(path) <= DRAWN else "\u2026" + path[1 - DRAWN:]


def _pair(model: str, owner: str, event: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": model},
            "systemMessage": owner}


def said(paths: list, env, event: str = "PostToolUse") -> tuple:
    """F2: (the model's line, the owner's line) for the waiting paths: the first sorted, then
    `(+N more)`; the drawn path's tail cut until the pair beside `{}` fits PAIR_CAP."""
    paths = sorted(dict.fromkeys(paths))
    more = f" (+{len(paths) - 1} more)" if len(paths) > 1 else ""
    shown = _drawn(paths[0], env)
    while True:
        text = shown + more
        model, owner = SAID.format(shown=text), SAID_OWNER.format(shown=text)
        if len(json.dumps(_pair(model, owner, event))) <= PAIR_CAP or len(shown) <= 2:
            return model, owner
        shown = "\u2026" + shown[2:]     # one character fewer, the mark kept


# ---- the hook ---------------------------------------------------------------------------

def _target(payload: dict) -> str | None:
    ti = payload.get("tool_input")
    t = ti.get(TOOLS[payload.get("tool_name")]) if isinstance(ti, dict) else None
    if not isinstance(t, str) or not t or "\0" in t:
        return None
    if os.path.isabs(t):
        return os.path.normpath(t)
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and os.path.isabs(cwd) and "\0" not in cwd:
        return os.path.normpath(os.path.join(cwd, t))
    return None


def check(payload: dict, env) -> dict:
    """The PreToolUse answer for one call: {} when it touches no gated file, else `deny` with
    §7.2's reason. Fails open: an error gives {} and one `open` line."""
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or tool not in TOOLS:
        return {}
    path = None
    try:
        reason, why = REASON, None
        if tool == "Bash":
            got = _bash_gated(payload, env)
            if got is None:
                return {}
            path, why = got
            reason = LOOSE_REASON if why == LOOSE else REASON
        else:
            path = _target(payload)
            if path is None:
                log(payload, env, "open", None, why="the target cannot be resolved")
                return {}
            if not gated(path, env):
                return {}
        log(payload, env, "deny", path, why=why)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": "deny",
                                       "permissionDecisionReason": reason.format(path=path)}}
    except Exception as e:                              # noqa: BLE001 - R4: fail open
        log(payload, env, "open", path, why=type(e).__name__)
        return {}


# ---- the lane's write: `agentik session gates write` ------------------------------------

_BEGIN = "<!-- BEGIN GENERATED:"
_END = "<!-- END GENERATED:"


def lane_hash(current: bytes | None, draft: bytes) -> str:
    """The hash the preview prints and `--expect` checks: the file as it stands and the draft."""
    h = hashlib.sha256(b"agentik-session gates write\0")
    h.update(b"absent" if current is None else hashlib.sha256(current).digest())
    h.update(hashlib.sha256(draft).digest())
    return h.hexdigest()[:16]


def _blocks(text: str) -> list:
    out, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(_BEGIN):
            cur = [line]
        elif cur is not None:
            cur.append(line)
            if s.startswith(_END):
                out.append("\n".join(cur))
                cur = None
    if cur is not None:
        out.append("\n".join(cur))
    return out


def gates_write(file: str, draft: str, expect, env, cwd: str, out, err) -> int:
    """Preview (no `expect`): the diff, the byte change and the hash, nothing written. With
    `expect`: the draft written atomically, the file's mode kept, when nothing changed since."""
    import difflib
    import tempfile
    t = os.path.normpath(os.path.join(cwd, _tilde(file, env) or file))
    d = os.path.normpath(os.path.join(cwd, _tilde(draft, env) or draft))
    say = "agentik-session: gates write: "
    if not gated(t, env):
        err.write(f"{say}{t} is not gated, so it takes an ordinary edit; nothing written\n")
        return 1
    if gated(d, env):
        err.write(f"{say}the draft {d} is gated; a draft is an ungated file; nothing written\n")
        return 1
    try:
        with open(d, "rb") as f:
            new = f.read()
    except OSError as e:
        err.write(f"{say}the draft cannot be read ({e.strerror}); nothing written\n")
        return 1
    d_list = _folder_list_of(t, env)
    if d_list is not None and not os.path.lexists(os.path.join(d_list, ".git")):
        for s in _lines_of(new[:LIST_CAP]):       # g4 R4: a folder list's refused line
            if _relative(s) is None:
                err.write(f"{say}the draft's line `{s}` would match nothing in a folder's list "
                          "(a line starting with `/` or `~`, or holding `..`); nothing "
                          "written\n")
                return 1
    real = os.path.realpath(t)
    try:
        with open(real, "rb") as f:
            old = f.read()
    except FileNotFoundError:
        old = None
    except OSError as e:
        err.write(f"{say}{t} cannot be read ({e.strerror}); nothing written\n")
        return 1
    old_text = (old or b"").decode("utf-8", "replace")
    new_text = new.decode("utf-8", "replace")
    if _blocks(old_text) != _blocks(new_text):
        err.write(f"{say}the draft changes a generated block's line in {t}; a block is "
                  "written by `agentik decisions render`; nothing written\n")
        return 1
    if t.lower().endswith(".json"):
        try:
            json.loads(new_text)
        except ValueError as e:
            err.write(f"{say}the draft is not valid JSON ({e}); nothing written\n")
            return 1
    h = lane_hash(old, new)
    was = len(old or b"")
    if expect is None:
        out.writelines(difflib.unified_diff(old_text.splitlines(keepends=True),
                                            new_text.splitlines(keepends=True), t,
                                            t + " (draft)"))
        out.write(f"bytes: {was} -> {len(new)} ({len(new) - was:+d})\n")
        out.write(f"hash: {h}\n")
        out.write(f"on the owner's yes: agentik session gates write {shlex.quote(t)} --from "
                  f"{shlex.quote(d)} --expect {h}\n")
        return 0
    if expect != h:
        err.write(f"{say}the file or the draft changed since the preview (now {h}, expected "
                  f"{expect}); preview again; nothing written\n")
        return 1
    mode = (os.stat(real).st_mode & 0o7777) if old is not None else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".gates-", dir=os.path.dirname(real))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    out.write(f"gates: wrote {t}: {was} -> {len(new)} B ({len(new) - was:+d})\n")
    return 0


def listing(env, cwd: str) -> list:
    """What is gated where `cwd` is, each list with its lines: the checkout's, each folder's from
    the nearest up (g4 R6), the user's."""
    cache: dict = {}
    rows = []
    here = os.path.abspath(cwd)
    top = _top(here, itself=True)
    folders = folder_lists(here, env, cache, itself=True)
    if top is not None:
        lf = os.path.join(top, ".claude", LIST)
        lines = repo_lines(top, cache)
        state = "" if os.path.exists(lf) else ", absent"
        rows.append(f"{lf} (this checkout's list, itself gated{state}): {len(lines)} lines")
        rows += [f"  {s}" for s in lines]
    elif folders:
        rows.append("no checkout here: the folders' lists and the user's apply")
    else:
        rows.append("no checkout here: only the user's list applies")
    for d, lines, _ in folders:
        rows.append(f"{os.path.join(d, '.claude', LIST)} (a folder's list, its lines relative to "
                    f"{d}, itself gated): {len(lines)} lines")
        rows += [f"  {s}" for s in lines]
    lf = os.path.join(user_dir(env), LIST)
    lines = _user_raw(env, cache)
    state = "" if os.path.exists(lf) else ", absent"
    rows.append(f"{lf} (the user's list, itself gated{state}): {len(lines)} lines")
    rows += [f"  {s}" for s in lines]
    return rows


def count_here(env, cwd) -> int:
    cache: dict = {}
    here = os.path.abspath(str(cwd))
    top = _top(here, itself=True)
    folders = sum(len(lines) for _, lines, _ in folder_lists(here, env, cache, itself=True))
    return (len(repo_lines(top, cache)) if top else 0) + folders + len(user_lines(env, cache))


# ---- R4: the doctor's line --------------------------------------------------------------

def counts(sdir) -> tuple:
    """(0, refusals, guard errors, gated files changed by an unread line) in one session's
    guard log; the first place is g2's prompts, which the gate never makes. An `open` line
    with a reason gc1 retired counts as neither (R5)."""
    n = {"deny": 0, "open": 0, "changed": 0}
    try:
        with open(Path(sdir) / LOG, "rb") as f:
            raw = f.read(LOG_CAP + 4096)
    except OSError:
        return 0, 0, 0, 0
    for text in raw.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(text)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("decision") in n:
            if d["decision"] == "open" and d.get("why") in RETIRED:
                continue
            n[d["decision"]] += 1
    return 0, n["deny"], n["open"], n["changed"]


def doctor_row(env, cwd) -> str:
    """One line: the gates are on, how many lines are gated here, and what this repo's newest
    session (g1's `newest`) logged."""
    return guard_row(env, cwd)[0]


def guard_row(env, cwd) -> tuple:
    """(the doctor's line, warn): warn when the newest session logged a guard error or a gated
    file changed by an unread line (gc1 R5)."""
    from . import instructions
    try:
        n = count_here(env, cwd)
    except Exception:                                   # noqa: BLE001
        n = 0
    try:
        main = instructions.main_checkout(cwd)
        found = instructions.newest(resolver.state_dir(env), main)
    except Exception:                                   # noqa: BLE001
        return f"on; {n} gated here (the repo's sessions cannot be read)", False
    if found is None:
        return f"on; {n} gated here; no session of {main} has a log to count its refusals", False
    sid = found[0]
    _, denies, errors, changed = counts(resolver.session_dir(resolver.state_dir(env), sid))
    return (f"on; {n} gated here; session {sid}: {denies} refusals, {errors} guard errors, "
            f"{changed} gated files changed by an unread line"), bool(errors or changed)
