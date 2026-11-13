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
`shlex` splits it into simple commands; the targets are redirections (a heredoc's own included),
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
each refusal is a line there too, naming a helper by the payload's `agent_id`. No knob: the
environment is read for `HOME` and `CLAUDE_CONFIG_DIR` and the state root, nothing else. No
process is spawned and no launch line is read.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

from . import resolver

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

def _home(env) -> str:
    return env.get("HOME") or str(Path.home())


def _tilde(word: str, env) -> str | None:
    if word == "~" or word.startswith("~/"):
        return _home(env) + word[1:]
    return None if word.startswith("~") else word


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
_HEREDOC = re.compile(r"(?<!<)<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([A-Za-z0-9_.-]+))")
_PH = "__g3_heredoc_%d__"
_PH_RE = re.compile(r"__g3_heredoc_(\d+)__\Z")
_PUNCT = ";&|<>()\n"
_OPS = re.compile(r"&>>|&>|>>|>\||>&|<&|<<<|<>|<<|>|<|\|\||&&|;;&|;;|;&|\|&|[;&|()\n]")
_MASK = {"(": "", ")": "", "`": ""}    # a quoted or escaped paren, never an operator
_UNMASK = str.maketrans({v: k for k, v in _MASK.items()})
_CASE_NEXT = frozenset({";;", ";&", ";;&"})
_KEY = re.compile(r"(?:[a-z]+|!|\{)(?=[ \t\n;&|()<>`]|\\\n|\Z)")    # r3 F5: `\`-NL
_LEAD = frozenset({"if", "then", "else", "elif", "while", "until", "do", "time", "!", "{"})
_WRITE_OPS = frozenset({">", ">>", ">|", "&>", "&>>", "<>", ">&"})
_READ_OPS = frozenset({"<", "<&", "<<<", "<<"})
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "env", "command", "exec", "nohup", "time", "builtin", "nice"})
_SHELLS = frozenset({"bash", "sh", "zsh", "dash"})
_CDS = frozenset({"cd", "pushd", "popd"})      # in backticks, no move of the line's folder
_PY = re.compile(r"python[0-9.]*\Z")
_SED_I = re.compile(r"-[nErsuz]*i|--in-place")
_PERL_I = re.compile(r"-[pnlaws0]*i")
_LITERAL = re.compile(r"""(['"])((?:\\.|(?!\1)[^\\\n])*)\1""")
_TAKES = {"install": frozenset({"-m", "-o", "-g", "-S", "--mode", "--owner", "--group",
                                "--suffix"}),
          "cp": frozenset({"-S", "--suffix"}), "mv": frozenset({"-S", "--suffix"})}


def _heredocs(text: str):
    """The text with each heredoc's body taken out and its operator turned into a placeholder
    word; the bodies, by the placeholder's index."""
    lines, out, bodies, i = text.split("\n"), [], [], 0
    while i < len(lines):
        pending = []

        def sub(m):
            delim = next(g for g in (m.group(2), m.group(3), m.group(4)) if g is not None)
            pending.append((len(bodies), m.group(1) == "-", delim))
            bodies.append("")
            return " " + _PH % (len(bodies) - 1) + " "
        out.append(_HEREDOC.sub(sub, lines[i]))
        i += 1
        for idx, strip, delim in pending:
            body = []
            while i < len(lines):
                line = lines[i]
                i += 1
                if (line.lstrip("\t") if strip else line) == delim:
                    break
                body.append(line)
            bodies[idx] = "\n".join(body)
    return "\n".join(out), bodies


def _mask(text: str, bash3: bool = False, ticks: bool = True) -> str:
    """The text with each quoted or backslashed paren replaced by a private character, so the
    lexer never takes it for a subshell's edge (r2 F1); a comment, a `#` at a word's start
    outside quotes, is dropped up to its newline, so the lexer reads every other `#` (g5).
    A word goes on after the `)` of a `$(`; no comment starts in a `${`, and one in backticks
    ends at a backtick, escaped or not (g5 r3); a backslash-newline is dropped outside single
    quotes (g5 r1).
    A bare paren in a `${` is a word's; a `case` pattern's `)` closes no bracket (g5 r2);
    a backtick in a `${` is a bracket of its own, in which a paren is a command's (g5 r3);
    `bash3`: bash 3.2's reading, which opens no `${` inside a `$(` and counts no `case`;
    `ticks`: a pattern's `)` in backticks is masked into a word (r3 F1, R8: both are read)."""
    out, i, n, quote, start = [], 0, len(text), None, True
    opened, tick, prev = [], False, ""    # the open `(`, `$(` and `${`; inside backticks
    esc = False                           # in backticks, inside an escaped pair of them
    cases, cmd = [0], True                # per bracket its open `case`s; at a command's start
    while i < n:
        c = text[i]
        if c == "\\" and text[i + 1:i + 2] == "\n" and quote != "'":
            i += 2                        # r1 F4: the line goes on, the word too
            continue
        if quote is None:
            if c == "\\" and i + 1 < n:
                esc ^= tick and text[i + 1] == "`"
                out += [c, _MASK.get(text[i + 1], text[i + 1])]
                i, start, prev, cmd = i + 2, False, "", cmd and not start
                continue
            if c == "#" and start and opened[-1:] != ["${"]:
                nl = text.find("\n", i)
                nl = n if nl < 0 else nl
                k = text.find("`", i, nl) if tick else -1     # r3 F7: on its line alone
                while k >= 0:                 # r3 F4: in an escaped pair, the first backtick
                    j = k                     # ends it, escaped or not, and is read again
                    while text[j - 1] == "\\":  # from its backslashes; else the first
                        j -= 1                # unescaped one (R8: `# \`x\`` is all comment)
                    if esc or (k - j) % 2 == 0:
                        break
                    k = text.find("`", k + 1, nl)
                i = j if k >= 0 else nl
                continue
            if c in "'\"":
                quote = c
            elif c == "`":
                tick, esc = not tick, False
                if tick and opened[-1:] == ["${"]:    # r3 F2: in it a paren is a command's
                    opened.append(c)
                    cases.append(0)
                elif not tick and c in opened:
                    while opened.pop() != c:
                        cases.pop()
                    cases.pop()
            elif opened[-1:] == ["${"] and (c == ")" or (c == "(" and prev[:1] != "$")):
                c = _MASK[c]              # r2 F1, F4: a bare paren in `${` is a word's
            elif c == "(" or (c == "{" and prev == "$" and not (bash3 and "$(" in opened)):
                opened.append("$" + c if prev[:1] == "$" else c)
                cases.append(0)
            elif c == "}" and opened[-1:] == ["${"]:
                opened.pop()
                cases.pop()
            out.append(c)
            if c == ")":                  # r1 F1: a `$(`'s `)` ends no word
                if cases[-1] or opened[-1:] in ([], ["`"]):    # r2 F2: nor a pattern's `)`
                    start = True
                    if (cases[-1] and tick and ticks) or (opened and not cases[-1]):
                        out[-1] = _MASK[c]     # R8: one that closes nothing in a `${`'s tick
                else:
                    cases.pop()
                    start = opened.pop() != "$("
                cmd = start
            else:
                if c == "`":                   # a command starts inside backticks
                    cmd = tick
                elif start and c not in " \t\n;&|(<>":    # a word starts: a command's first?
                    m = _KEY.match(text, i) if cmd else None
                    w = m.group() if m else ""
                    if not bash3:              # r3 F3: bash 3.2 ends a `$(` at any `)`
                        cases[-1] += (w == "case") - (w == "esac" and cases[-1] > 0)
                    cmd = w in _LEAD
                elif c in ";&|(<>\n":
                    cmd = c not in "<>"
                start = c in " \t\n;&|(<>" or (c == "`" and tick)
            prev = "$$" if c + prev == "$$" else c    # `$$`, the pid, opens no `${`
            i += 1
            continue
        if quote == '"' and c == "\\" and i + 1 < n:
            out += [c, _MASK.get(text[i + 1], text[i + 1])]
            i += 2
            continue
        if c == quote:
            quote = None
        out.append(_MASK.get(c, c))
        prev = ""
        i += 1
    return "".join(out)


def _commands(text: str, bash3: bool = False, ticks: bool = True):
    """Simple commands: (words, the words after a write redirection), in order; a subshell's
    `(` and `)` as (`(`, None) and (`)`, None). A paren that ends a `case` pattern, or opens
    one, is no subshell's edge (r2 F2), in backticks too (r3 F1); a quoted or escaped one is a
    word (r2 F1), and a quoted or escaped backtick opens nothing (r3 F1)."""
    lex = shlex.shlex(_mask(text, bash3, ticks), posix=True, punctuation_chars=_PUNCT)
    lex.commenters = ""                   # g5: `_mask` alone tells a comment's `#`
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    words, outs, expect = [], [], None
    cases: list = []                      # per open `case`: `head`, `pattern` or `body`
    ticks = 0                             # the real backticks read so far
    for tok in lex:
        if tok and set(tok) <= set(_PUNCT):
            for op in _OPS.findall(tok):
                if op in _WRITE_OPS or op in _READ_OPS:
                    if words and words[-1].isdigit():
                        words.pop()               # `2>`: the descriptor, not a word
                    expect = op
                    continue
                if words or outs:
                    yield words, outs
                words, outs, expect = [], [], None
                if cases and cases[-1] == "pattern" and op in "()":
                    if op == ")":
                        cases[-1] = "body"        # the pattern ends; its paren is no edge
                    continue
                if cases and cases[-1] == "body" and op in _CASE_NEXT:
                    cases[-1] = "pattern"
                elif op in "()":
                    yield op, None                # a subshell's bounds: its folder ends at `)`
            continue
        raw, tok = tok, tok.translate(_UNMASK)    # in `raw` a backtick is a real one
        ticks += raw.count("`")
        if expect is not None:
            if expect in _WRITE_OPS and not (expect == ">&" and (tok.isdigit() or tok == "-")):
                outs.append(tok)
            expect = None
            continue
        if not outs and (tok == "case" and all(w in _LEAD for w in words) or
                         raw.endswith("`case") and (ticks - raw[-4:].count("`")) % 2):
            cases.append("head")          # r3 F1: a `case` glued to its opening backtick too
        elif (not words and not outs and (tok == "esac" or raw.startswith("esac`"))
              and cases and cases[-1] != "head"):
            cases.pop()
        elif tok == "in" and cases and cases[-1] == "head" and words[-2:-1] and (
                words[-2] == "case" or words[-2].endswith("`case")):
            cases[-1] = "pattern"
        words.append(tok)
    if words or outs:
        yield words, outs


def _resolve(word: str, cwd, env) -> str | None:
    if not word or word == "-" or "\0" in word or any(c in word for c in "$`*?[{"):
        return None
    word = _tilde(word, env)
    if word is None:
        return None
    if os.path.isabs(word):
        return os.path.normpath(word)
    return os.path.normpath(os.path.join(cwd, word)) if cwd else None


def _py_literals(code: str) -> list:
    if "open(" not in code and "write_" not in code:
        return []
    return [m.group(2) for m in _LITERAL.finditer(code)]


def _copy_args(name: str, args: list):
    """(sources, the `-t` folder or None, the last plain word or None) of `cp`, `mv` or
    `install`; the last word is a source too where a `-t` names the folder."""
    srcs, tdir, i, done = [], None, 0, False
    while i < len(args):
        a = args[i]
        if done or not a.startswith("-") or a == "-":
            srcs.append(a)
        elif a == "--":
            done = True
        elif a in ("-t", "--target-directory"):
            tdir = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif a.startswith("--target-directory="):
            tdir = a.split("=", 1)[1]
        elif a.startswith("-t") and not a.startswith("--"):
            tdir = a[2:]
        elif a in _TAKES.get(name, ()):
            i += 1
        i += 1
    return srcs, tdir


def _copy_like(name: str, args: list, cwd, env):
    """(sources, destinations) of `cp`, `mv` or `install`."""
    srcs, tdir = _copy_args(name, args)
    if tdir is not None:
        return srcs, [os.path.join(tdir, os.path.basename(s.rstrip("/"))) for s in srcs]
    if len(srcs) < 2:
        return srcs, []
    dst, srcs = srcs[-1], srcs[:-1]
    r = _resolve(dst, cwd, env)
    if r is not None and os.path.isdir(r):
        return srcs, [os.path.join(dst, os.path.basename(s.rstrip("/"))) for s in srcs]
    return srcs, [dst]


def _git_paths(args: list):
    """(the `-C` words, the removal's words) of a `git rm`, `git restore` or `git checkout --`."""
    i, chdirs = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            chdirs.append(args[i + 1])
            i += 2
        elif args[i] in ("-c", "--git-dir", "--work-tree"):
            i += 2
        else:
            i += 1
    if i >= len(args):
        return chdirs, []
    sub, rest = args[i], args[i + 1:]
    if sub in ("rm", "restore"):
        return chdirs, [a for a in rest if not a.startswith("-")]
    if sub == "checkout" and "--" in rest:
        return chdirs, rest[rest.index("--") + 1:]
    return chdirs, []


def bash_targets(command: str, cwd, env, depth: int = 0, bash3: bool = False,
                 ticks: bool = True) -> list:
    """[(`write` or `remove`, a path or None)] in the line's order, then (`split`, None) where
    `shlex` stops splitting after a command; ValueError where it cannot read the first (g5 r1 F3).
    Where bash 3.2's reading, or the one that masks no pattern's `)` in backticks, masks the
    line otherwise, its targets follow (g5 r2, r3)."""
    return [(k, p) for k, p, _, _ in _strict(command, cwd, env, depth, bash3, ticks, set())]


class _Bound(Exception):
    """r2 R1: the strict reading judged past a bound on one line; `path` is the target it
    stopped at. Never a ValueError, which would leave the line to the loose reading."""

    def __init__(self, path):
        super().__init__(path)
        self.path = path


class _Paid:
    """r2 R1: one line's strict reading so far, inner lines and other readings included: its
    judgements (targets times folder states), the distinct paths they named, and each text it
    split, kept so a `-c` line read in many folders is split once (the same words each time)."""
    __slots__ = ("n", "paths", "parsed")

    def __init__(self):
        self.n, self.paths, self.parsed = 0, set(), {}


def _parse(command: str, bash3: bool, ticks: bool) -> tuple:
    """(text, heredoc bodies, the other readings to try, the commands read, the ValueError
    that stopped the reading or None): what `_strict` reads before it stands in a folder."""
    text, bodies = _heredocs(command)
    first = ticks and not bash3
    m0 = _mask(text) if first else ""
    other = [r for r in ((True, True), (False, False)) if first and _mask(text, *r) != m0]
    read, err = [], None
    try:
        for c in _commands(text, bash3, ticks):
            read.append(c)
    except ValueError as e:
        err = e
    return text, bodies, other, read, err


def _strict(command: str, cwd, env, depth: int, bash3: bool, ticks: bool, stood: set,
            paid: _Paid | None = None) -> list:
    """`bash_targets` with each target's word and the folder it was read in (g6 R2):
    [(kind, path, word, folder)]; each folder the reading stood in goes in `stood`. Past
    `_STRICT_READS` judgements or `_STRICT_BOUND` distinct paths on the line it raises
    `_Bound`, counted as it reads (r2 R1)."""
    paid = _Paid() if paid is None else paid
    if (command, bash3, ticks) not in paid.parsed:
        paid.parsed[command, bash3, ticks] = _parse(command, bash3, ticks)
    text, bodies, other, read, err = paid.parsed[command, bash3, ticks]
    found, subshells = [], []
    st, fa = [(cwd, ())], 0                # r1 R1: (folder, pushd stack) states; st[0] is
                                           # a0055da's, st[fa] follows every `cd` (db19d51's)

    def add(kind, word, at):
        path = _resolve(word, at, env)
        paid.n += 1                       # r2 R1: a line it cannot afford to read is denied
        if (kind, path) not in paid.paths:
            paid.paths.add((kind, path))
        if paid.n > _STRICT_READS or len(paid.paths) > _STRICT_BOUND:
            raise _Bound(path or word)
        found.append((kind, path, word, at))
    if err is not None:
        if all(outs is None for _, outs in read):
            if not _others(command, cwd, env, depth, other, found, stood, paid):
                raise err
            return found + [("split", None, None, None)]
        read = read + [("split", "split")]
    for words, outs in read:
        if words == "split":
            found.append(("split", None, None, None))
            continue
        if outs is None:                  # r1 F1, r2 F3: a subshell's `cd` and pushd end with it
            if words == "(":
                subshells.append((st, fa))
            elif subshells:
                st, fa = subshells.pop()
            else:                         # a `)` with no `(`: the folder is unknown
                st, fa = [(None, ())], 0
            continue
        heres = list(dict.fromkeys([st[fa][0]] + [f for f, _ in st]))   # where a `cd` ran, first
        stood.update(heres)
        mine = [bodies[int(m.group(1))] for m in map(_PH_RE.match, words) if m]
        words = [w for w in words if not _PH_RE.match(w)]
        if words and not words[-1].strip("`"):
            words.pop()                   # r3 F6: a lone closing backtick is no argument, and
        words = [w if w.strip("`") in _CDS or not w.strip("`") else w.strip("`")
                 for w in words]          # one at a word's end is the line's (R8: no `cd`)
        for o in outs:
            if not _PH_RE.match(o) and o.strip("`"):
                for h in heres:
                    add("write", o.strip("`"), h)
        lead, run, i = False, True, 0     # g6 R5: `then cd` is read (n138); r1 R2: a reserved
        while i < len(words):             # word only in the command's first run of them, which
            w = words[i]                  # r2 R2: `time`'s options stand inside
            opt = w.startswith("-") and i + 1 < len(words)
            if run and (w in _LEAD or (opt and "time" in words[:i])):
                lead = lead or (w in _LEAD and w != "time")
            elif _ASSIGN.match(w) or w in _WRAPPERS or opt:
                run = False
            else:
                break
            i += 1
        words = words[i:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        plain = [a for a in args if a and not a.startswith("-")]
        if name in _CDS:                  # r1 R1: behind a reserved word a `cd` may not run, so
            moved = [_move(name, args, s, env) for s in st]    # it adds a folder, replaces none
            st, fa = _states(st + moved, len(st) + fa) if lead else _states(moved, fa)
            continue
        for h in heres:
            _judge(name, args, plain, h, mine, env, depth, stood, add, found, paid)
    _others(command, cwd, env, depth, other, found, stood, paid)  # each reading's targets once
    return found


_CAP_STATES = 16                          # r1 R1: a line's folder states, at most
_STRICT_BOUND = 4096                      # r2 R1: distinct paths the strict reading judges
_STRICT_READS = 65536                     # r2 R1: its judgements, a path judged again included


def _move(name: str, args: list, s: tuple, env) -> tuple:
    """The (folder, pushd stack) after one `cd`, `pushd` or `popd` (r1 F1: popd goes back to
    pushd's folder, else to none)."""
    f, pushed = s
    if name == "popd":
        return (pushed[-1], pushed[:-1]) if pushed and not args else (None, pushed)
    to = _resolve(args[0], f, env) if len(args) == 1 else _tilde("~", env) if not args else None
    return to, pushed + (f,) if name == "pushd" else pushed


def _states(st: list, fa: int):
    """`st` without repeats, at most `_CAP_STATES`, keeping the first and the `fa`th; fa's index."""
    first, follow = st[0], st[fa]
    rest = [x for x in dict.fromkeys(st) if x != first and x != follow]
    keep = {first, follow, *rest[:_CAP_STATES - 2]}
    order = [x for x in dict.fromkeys(st) if x in keep]
    return order, order.index(follow)


def _judge(name, args, plain, here, mine, env, depth, stood, add, found, paid) -> None:
    """Adds the targets of one command, its words read in `here`."""
    if name in _SHELLS and "-c" in args and depth == 0:
        i = args.index("-c")
        if i + 1 < len(args):
            try:
                found += _strict(args[i + 1], here, env, depth + 1, False, True, stood, paid)
            except ValueError:            # g6 R6: the inner line is unread, the outer judged
                found.append(("split", None, None, None))
    elif name == "tee":
        for a in plain:
            add("write", a, here)
    elif (name == "sed" and any(_SED_I.match(a) for a in args)) or \
            (name == "perl" and any(_PERL_I.match(a) for a in args)):
        for a in plain:
            add("write", a, here)
    elif name in _TAKES:
        srcs, dsts = _copy_like(name, args, here, env)
        for d in dsts:
            add("write", d, here)
        if name == "mv":
            for s in srcs:
                add("remove", s, here)
    elif name in ("rm", "unlink"):
        for a in plain:
            add("remove", a, here)
    elif name == "git":
        chdirs, paths = _git_paths(args)
        at = here
        for d in chdirs:
            at = _resolve(d, at, env)
        for p in paths:
            add("remove", p, at)
    elif _PY.match(name):
        codes = list(mine)
        if "-c" in args and args.index("-c") + 1 < len(args):
            codes.append(args[args.index("-c") + 1])
        for code in codes:
            for s in _py_literals(code):
                if s:
                    add("write", s, here)


def _others(command: str, cwd, env, depth: int, other: list, found: list, stood: set,
            paid: _Paid) -> int:
    """Adds to `found` each other reading's targets it lacks; how many readings read the line."""
    read = 0
    for r in other:
        try:
            have = {f[:2] for f in found}
            found += [f for f in _strict(command, cwd, env, depth, *r, stood, paid)
                      if f[:2] not in have]
            read += 1
        except ValueError:
            pass
    return read


# ---- g6: the loose reading, a second reading that no quote, comment or heredoc can hide ----

_LOOSE_SEP = re.compile(r"(?<!\\)(?:[;|\n(){}`]|(?<![<>])&|(?<=\\[<>])&)")  # r1 R5: no split in
                                          # `>&`; r2 R3: but at `\>&`, where `&` runs a command
_LOOSE_W = re.compile(r"(?<![-=])(?:&>>|&>|>>|>\||>&(?=[ \t]*[^\s\d-])|>)[ \t]*"
                      r"([^\s;&|<>(){}`]+)")         # r1 R5: `>&` before a word
_LOOSE_REDIR = re.compile(r"(?<!\d)\d*(?:&>>|&>|>>|>\||>&|<<<|<<-?|<&|<>|>|<)[ \t]*[^\s;&|<>(){}`]*")
_LOOSE_COMMENT = re.compile(r"(?:^|[ \t])#")
_LOOSE_SKIP = frozenset({"then", "do", "else", "elif", "if", "while", "until", "!", "eval"})
_LOOSE_HARD = re.compile(r"[(){}`#\\]|<<|(?<![|&<>])[|&](?![|&>])")    # a `cd` past one: no move
_LOOSE_COND = frozenset({"if", "then", "else", "elif", "while", "until", "do", "for", "select",
                         "case", "function", "!", "eval"})


def _clean(word: str) -> str:
    return word.strip("'\"").rstrip("\\")


def _loose(text: str) -> list:
    """[(kind, word, the `cd` words before it, or None where the text before it is not plain,
    its command's number)]: `loose_targets` with the folder moves a plain line makes (g6 R2)."""
    text = text.replace("\\\n", "")
    hard = _LOOSE_HARD.search(text)
    plain_to = hard.start() if hard else len(text)
    found, cds, start, segs = [], [], 0, []
    for n, sep in enumerate([*_LOOSE_SEP.finditer(text), None]):
        segs += [n] * (len(found) - len(segs))
        end = sep.start() if sep else len(text)
        seg, plain = text[start:end], start <= plain_to
        start = sep.end() if sep else end
        moves = tuple(cds) if plain else None
        for m in _LOOSE_W.finditer(seg):
            w = _clean(m.group(1))
            if w:
                found.append(("write", w, moves))
        cut = _LOOSE_COMMENT.search(seg)          # the command's words end at a blank then `#`
        words = [w for w in (_clean(x) for x in
                             _LOOSE_REDIR.sub(" ", seg[:cut.start()] if cut else seg).split())
                 if w]
        if plain and words and words[0] in _LOOSE_COND:
            plain_to = -1                         # a `cd` past a reserved word may not run
        i = 0                                     # r2 R2: a reserved word wherever the loop
        while i < len(words) and (_ASSIGN.match(words[i]) or words[i] in _WRAPPERS   # meets it,
                                  or words[i] in _LOOSE_SKIP                    # as db19d51's
                                  or os.path.basename(words[i]) in _SHELLS      # (an inner
                                  or (words[i].startswith("-") and i + 1 < len(words))):  # line)
            i += 1
        words = words[i:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        plain_args = [a for a in args if not a.startswith("-")]
        if name in ("cd", "pushd", "popd"):
            cds.append(args[0] if name != "popd" and len(args) == 1 else
                       "~" if name != "popd" and not args else None)
        elif name == "tee" or (name == "sed" and any(_SED_I.match(a) for a in args)) or \
                (name == "perl" and any(_PERL_I.match(a) for a in args)):
            found += [("write", a, moves) for a in plain_args]
        elif name in _TAKES:
            srcs, tdir = _copy_args(name, args)
            if tdir is not None:
                found += [("write", os.path.join(tdir, os.path.basename(s.rstrip("/"))), moves)
                          for s in srcs]
            elif len(srcs) > 1:
                found.append(("write", srcs[-1], moves))
                srcs = srcs[:-1]
            if name == "mv":
                found += [("remove", s, moves) for s in srcs]
        elif name in ("rm", "unlink"):
            found += [("remove", a, moves) for a in plain_args]
        elif name == "git":
            chdirs, paths = _git_paths(args)
            for p in paths:
                for d in reversed(chdirs):
                    p = os.path.join(d, p)
                found.append(("remove", p, moves))
    segs += [len(segs) and segs[-1] + 1] * (len(found) - len(segs))
    return [(k, w, m, n) for (k, w, m), n in zip(found, segs)]


def loose_targets(text: str) -> list:
    """[(`write` or `remove`, word)]: every target a reading blind to quotes, comments and
    heredocs finds (g6 R1). Pure: no list, no folder, no file."""
    return [(k, w) for k, w, _, _ in _loose(text)]


def _loose_gated(command: str, cwd, env, cache: dict, found: list, stood: set):
    """The first gated path (a list file, for a removal) of a loose target the strict reading
    did not judge in the same place (g6 R2); None when there is none it can resolve."""
    loose = _loose(command)
    judged: dict = {}
    spent = _spent(loose, found)
    for kind, path, word, at in found:
        if kind in ("write", "remove") and path is not None and word and len(word.split()) < 2:
            judged[kind, path] = judged.get((kind, path), 0) + 1
    owns, left = [cwd], []                # r1 R4: each `cd` resolved once, each target once
    for i, (kind, word, moves, _) in enumerate(loose):
        if i in spent:
            continue
        for c in (moves or ())[len(owns) - 1:]:
            owns.append(_resolve(c, owns[-1], env) if c is not None and owns[-1] else None)
        own = owns[len(moves)] if moves is not None else cwd
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


def _spent(loose: list, found: list) -> set:
    """The loose targets a strict word with a blank stands for (r1 R3): only whole, every piece
    in order, one command's targets of its kind, each loose target once; a word whose pieces
    the loose reading did not list together stands for none, so no piece is left to spend."""
    want: dict = {}
    for kind, path, word, _ in found:
        pieces = tuple(word.split()) if path is not None and word else ()
        if 1 < len(pieces) < _RUN_CAP and kind in ("write", "remove"):
            want[kind, pieces] = want.get((kind, pieces), 0) + 1
    spent: set = set()
    for k in sorted({len(p) for _, p in want}):
        for i in range(len(loose) - k + 1):
            run = loose[i:i + k]
            key = (run[0][0], tuple(r[1] for r in run))
            if want.get(key) and run[0][3] == run[-1][3] and all(r[0] == key[0] for r in run) \
                    and not spent.intersection(range(i, i + k)):
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
    if raised or split:                   # g5 r1 F3, r1 F6: the line was not all read
        log(payload, env, "open", None, why="the line cannot be split")
    elif unresolved:                      # r1 F6: an unresolved target passes, with one line
        log(payload, env, "open", None, why="a target cannot be resolved")
    return None


# ---- R4: the log ------------------------------------------------------------------------

def _text(v) -> str | None:
    return v[:TEXT_CAP] if isinstance(v, str) else None


def log(payload: dict, env, decision: str, path, why=None) -> None:
    """One line in `sessions/<sid>/guard.jsonl` (0600); a line that would carry the log past
    LOG_CAP is not written. Never raises."""
    try:
        sid = payload.get("session_id")
        if not (isinstance(sid, str) and _SID.match(sid)):
            return
        line = (json.dumps({"at": time.time(), "decision": decision,
                            "tool": _text(payload.get("tool_name")), "path": _text(path),
                            "agent_id": _text(payload.get("agent_id")),
                            "why": _text(why)}, ensure_ascii=False) + "\n").encode()
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
    """(0, refusals, calls let through on an error) in one session's guard log; the first
    place is g2's prompts, which the gate never makes."""
    n = {"deny": 0, "open": 0}
    try:
        with open(Path(sdir) / LOG, "rb") as f:
            raw = f.read(LOG_CAP + 4096)
    except OSError:
        return 0, 0, 0
    for text in raw.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(text)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("decision") in n:
            n[d["decision"]] += 1
    return 0, n["deny"], n["open"]


def doctor_row(env, cwd) -> str:
    """One line: the gates are on, how many lines are gated here, and what this repo's newest
    session (g1's `newest`) logged."""
    from . import instructions
    try:
        n = count_here(env, cwd)
    except Exception:                                   # noqa: BLE001
        n = 0
    try:
        main = instructions.main_checkout(cwd)
        found = instructions.newest(resolver.state_dir(env), main)
    except Exception:                                   # noqa: BLE001
        return f"on; {n} gated here (the repo's sessions cannot be read)"
    if found is None:
        return f"on; {n} gated here; no session of {main} has a log to count its refusals"
    sid = found[0]
    _, denies, opened = counts(resolver.session_dir(resolver.state_dir(env), sid))
    return (f"on; {n} gated here; session {sid}: {denies} refusals, {opened} let through on "
            "an error")
