"""The reader of a shell line, both its readings (packets g7, a move, and g8a, the walk).

The strict reading splits a line with `shlex` into simple commands (`_here_scan`, `_subst`,
`_mask`, `_commands`); one walk (`_walk`, packet g8a) turns them into the commands a line runs,
a substitution's and a first-level shell's script's included, and the parts it did not read.
`commands` gives them (`Cmd`, `Unread`; `git_words` sets git's options apart); `bash_targets`
and `_strict` judge them for the paths a line writes: packets g3, g5, g8a. The loose reading,
blind to quotes, comments and heredocs, lists every target a line might have (`_loose`,
`loose_targets`): packet g6. It knows no list, no log and no payload, and imports nothing of the
package: the edit gates (`instructionguard.py`) and the loop's make rule (`unattended.py`) read a
line through it.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import NamedTuple


# ---- g3, g5: the strict reading ---------------------------------------------------------

def _home(env) -> str:
    return env.get("HOME") or str(Path.home())


def _tilde(word: str, env) -> str | None:
    if word == "~" or word.startswith("~/"):
        return _home(env) + word[1:]
    return None if word.startswith("~") else word


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
_SHELLS5 = _SHELLS | {"ksh"}               # g8a R5: the shells whose script the walk reads
_WRAP_TAKES = {"sudo": frozenset("-u -g -h -p -C -D -R -T -U -r -t --user --group --host --prompt "
                                 "--close-from --chdir --chroot --command-timeout --other-user "
                                 "--role --type".split()),
               "env": frozenset({"-u", "-C", "-P"}), "nice": frozenset({"-n"}),
               "exec": frozenset({"-a"}), "time": frozenset({"-o", "-f"})}    # g8a R4
_SUB_PH = "__g8_sub_%d__"                  # g8a R6: a substitution, out of its word
_SUB_RE = re.compile(r"__g8_sub_(\d+)__")
_SUB_OUT = "$__g8_out"                     # a substitution's output, in the script it feeds
_PH_ANY = re.compile(r" ?__g3_heredoc_(\d+)__ ?")
_NEST = 32                                 # g8a R6: substitutions nested, at most
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


def _commands(text: str, bash3: bool = False, ticks: bool = True, ops: bool = False):
    """Simple commands: (words, the words after a write redirection), in order; a subshell's
    `(` and `)` as (`(`, None) and (`)`, None). A paren that ends a `case` pattern, or opens
    one, is no subshell's edge (r2 F2), in backticks too (r3 F1); a quoted or escaped one is a
    word (r2 F1), and a quoted or escaped backtick opens nothing (r3 F1).
    `ops` (g8a R7): each yield gains the operator before it and the command's read
    redirections, [(operator, word)]."""
    lex = shlex.shlex(_mask(text, bash3, ticks), posix=True, punctuation_chars=_PUNCT)
    lex.commenters = ""                   # g5: `_mask` alone tells a comment's `#`
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    words, outs, expect, before, ins = [], [], None, None, []
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
                    yield (words, outs, before, ins) if ops else (words, outs)
                words, outs, expect, before, ins = [], [], None, op, []
                if cases and cases[-1] == "pattern" and op in "()":
                    if op == ")":
                        cases[-1] = "body"        # the pattern ends; its paren is no edge
                    continue
                if cases and cases[-1] == "body" and op in _CASE_NEXT:
                    cases[-1] = "pattern"
                elif op in "()":              # a subshell's bounds: its folder ends at `)`
                    yield (op, None, before, []) if ops else (op, None)
            continue
        raw, tok = tok, tok.translate(_UNMASK)    # in `raw` a backtick is a real one
        ticks += raw.count("`")
        if expect is not None:
            if expect in _WRITE_OPS and not (expect == ">&" and (tok.isdigit() or tok == "-")):
                outs.append(tok)
            elif ops and expect in _READ_OPS:
                ins.append((expect, tok))
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
        yield (words, outs, before, ins) if ops else (words, outs)


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


_GIT_TAKES = frozenset({"-C", "-c", "--config-env", "--git-dir", "--work-tree", "--namespace",
                        "--super-prefix", "--attr-source"})    # g8a R8: each takes an operand


def git_words(args: list) -> tuple:
    """g8a R8: (globals, sub, rest) of git's words: each option before the subcommand with its
    operand or None (one of `_GIT_TAKES` not attached with `=` takes the next word; any other
    word that opens with `-` is a flag alone), the subcommand or "", the words after it."""
    i, globs = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] in _GIT_TAKES and i + 1 < len(args):
            globs.append((args[i], args[i + 1]))
            i += 2
        else:
            globs.append((args[i], None))
            i += 1
    return globs, (args[i] if i < len(args) else ""), args[i + 1:]


def _git_paths(args: list):
    """(the `-C` words, the removal's words) of a `git rm`, `git restore` or `git checkout --`."""
    globs, sub, rest = git_words(args)
    chdirs = [v for o, v in globs if o == "-C" and v is not None]
    if not sub:
        return chdirs, []
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
    stopped at. Never a ValueError, which would leave the line to the loose reading. g8a R6:
    the walk raises it too, for substitutions nested past `_NEST`."""

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
    """(text, heredoc bodies, whether each delimiter is quoted, each heredoc's operator, the other
    readings to try): what the walk reads before it stands in a folder (g8a: the commands are
    split by `_split`, a text at a time, a substitution's included)."""
    text, bodies, quoted, opers = _here_scan(command)
    first = ticks and not bash3
    m0 = _mask(text) if first else ""
    other = [r for r in ((True, True), (False, False)) if first and _mask(text, *r) != m0]
    return text, bodies, quoted, opers, other


def _strict(command: str, cwd, env, depth: int, bash3: bool, ticks: bool, stood: set,
            paid: _Paid | None = None) -> list:
    """`bash_targets` with each target's word and the folder it was read in (g6 R2):
    [(kind, path, word, folder)], `word` None where a folder state other than the followed
    one judged it again (r2 R4); each folder the reading stood in goes in `stood`. Past
    `_STRICT_READS` judgements or `_STRICT_BOUND` distinct paths on the line it raises
    `_Bound`, counted as it reads (r2 R1). g8a R3: it reads the line through `_walk`."""
    paid = _Paid() if paid is None else paid
    if (command, bash3, ticks) not in paid.parsed:
        paid.parsed[command, bash3, ticks] = _parse(command, bash3, ticks)
    text, bodies, quoted, opers, other = paid.parsed[command, bash3, ticks]
    found: list = []

    def add(kind, word, at):
        path = _resolve(word, at, env)
        paid.n += 1                       # r2 R1: a line it cannot afford to read is denied
        if (kind, path) not in paid.paths:
            paid.paths.add((kind, path))
        if paid.n > _STRICT_READS or len(paid.paths) > _STRICT_BOUND:
            raise _Bound(path or word)
        found.append((kind, path, word, at))
    for s in _walk(text, bodies, quoted, opers, [(cwd, ())], 0, env, depth, bash3, ticks,
                   paid.parsed):
        if s.why == "split":
            if s.first:                   # g5 r1 F3: the first command unread
                if not _others(command, cwd, env, depth, other, found, stood, paid):
                    raise s.err
                return found + [("split", None, None, None)]
            found.append(("split", None, None, None))
            continue
        if s.why:                         # g8a R7: `eval`, `below`, `piped`: no word read here
            continue
        heres = s.heres
        stood.update(heres)
        for o in s.outs:
            if o.strip("`"):
                for h in heres:
                    add("write", o.strip("`"), h)
                    if h != heres[0]:     # r2 R4: one credit a word and command (see below)
                        found[-1] = found[-1][:2] + (None,) + found[-1][3:]
        if s.name is None or s.name in _CDS:
            continue
        plain = [a for a in s.args if a and not a.startswith("-")]
        for h in heres:
            n = len(found)
            _judge(s.name, s.args, plain, h, s.mine, env, depth, stood, add, found, paid,
                   s.script)
            if h != heres[0]:             # r2 R4: a word judged in several folder states is one
                found[n:] = [(k, p, None, a) for k, p, _, a in found[n:]]  # credit, the followed
                                          # state's, as db19d51 judged it: never one per state
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


def _judge(name, args, plain, here, mine, env, depth, stood, add, found, paid,
           script=None) -> None:
    """Adds the targets of one command, its words read in `here`; `script` is a shell's, as
    the walk read it (g8a R5)."""
    if script is not None:
        if depth == 0:
            try:
                found += _strict(script, here, env, depth + 1, False, True, stood, paid)
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


# ---- g8a: the one walk of a line's commands ---------------------------------------------

class Cmd(NamedTuple):
    """g8a R2: one command a line runs. `name` is the command word's base name as written, ""
    for a command of assignments alone; `pre` the words before it; `heres` the folders it may
    run in, the followed one first, None for one not resolved; `level` 0, or 1 in a first-level
    shell's script."""
    name: str
    args: list
    pre: list
    heres: list
    level: int


class Unread(NamedTuple):
    """g8a R7: a part not read: `why` is `split`, `eval`, `below` or `piped`."""
    why: str
    text: str


class _Step:
    """One thing the walk met: a command (`why` "") or a part it did not read."""
    __slots__ = ("why", "text", "err", "first", "top", "pre", "name", "args", "outs", "heres",
                 "mine", "script", "level", "st", "fa")

    def __init__(self, why="", **kw):
        self.why = why
        for k in self.__slots__[1:]:
            setattr(self, k, kw.get(k))


def _here_scan(text: str):
    """`_heredocs` for the walk (g8a): a `<<` in quotes, in a comment or in `$((` opens no
    heredoc, and a `$(` in double quotes quotes afresh. (text, bodies, whether each delimiter is
    quoted, each operator as written)."""
    out, bodies, quoted, opers = [], [], [], []
    stack, pending, i, n, word = ["t"], [], 0, len(text), True
    while i < n:
        c, top = text[i], stack[-1]
        if top == "s":
            if c == "'":
                stack.pop()
        elif c == "\\":
            out.append(text[i:i + 2])
            i, word = i + 2, False
            continue
        elif top == "d":
            if c == '"':
                stack.pop()
            elif text.startswith("$(", i) and not text.startswith("$((", i):
                stack.append("u")
                out.append("$(")
                i, word = i + 2, True
                continue
        elif top in "am":                 # arithmetic (`m` its `$((`): no heredoc, no quote
            if c == "(":
                stack.append("a")
            elif c == ")" and top == "a":
                stack.pop()
            elif c == ")" and text.startswith("))", i):
                stack.pop()
                out.append("))")
                i += 2
                continue
        elif c == "#" and word:
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(text[i:j])
            i = j
            continue
        elif c in "'\"":
            stack.append("s" if c == "'" else "d")
        elif text.startswith("$((", i):
            stack.append("m")
            out.append("$((")
            i, word = i + 3, False
            continue
        elif text.startswith("$(", i):
            stack.append("u")
            out.append("$(")
            i, word = i + 2, True
            continue
        elif c == "(":
            stack.append("p")
        elif c == ")" and len(stack) > 1:
            stack.pop()
        elif c == "<":
            m = _HEREDOC.match(text, i)
            if m:
                delim = next(g for g in (m.group(2), m.group(3), m.group(4)) if g is not None)
                pending.append((len(bodies), m.group(1) == "-", delim))
                bodies.append("")
                quoted.append(m.group(4) is None or "\\" in m.group(0))
                opers.append(m.group(0))
                out.append(" " + _PH % (len(bodies) - 1) + " ")
                i, word = m.end(), True
                continue
        if c == "\n" and pending and stack[-1] not in "sd":
            out.append(c)
            i += 1
            for idx, strip, delim in pending:
                body = []
                while i < n:
                    j = text.find("\n", i)
                    j = n if j < 0 else j
                    line, i = text[i:j], j + 1
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
                    body.append(line)
                bodies[idx] = "\n".join(body)
            pending, word = [], True
            continue
        out.append(c)
        word = c in " \t\n;&|()<>"
        i += 1
    return "".join(out), bodies, quoted, opers


def _tick_end(text: str, i: int) -> int:
    """The index of the backtick that closes one opened before `i`, or the text's end."""
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "`":
            return i
        i += 1
    return len(text)


def _arith_end(text: str, i: int) -> int:
    """The index past the `))` that closes a `$((` opened before `i`."""
    d = 2
    while i < len(text):
        d += {"(": 1, ")": -1}.get(text[i], 0)
        i += 1
        if d == 0:
            return i
    return len(text)


def _brace_end(text: str, i: int, bash3: bool, depth: int) -> int:
    """The index past the `}` that closes a `${` opened before `i`: a paren in it is a word's."""
    n, lvl = len(text), 1
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif text.startswith("$((", i):
            i = _arith_end(text, i + 3)
        elif text.startswith("$(", i):
            i = _sub_end(text, i + 2, bash3, depth + 1) + 1
        elif text.startswith("${", i):
            lvl, i = lvl + 1, i + 2
        elif c == "`":
            i = _tick_end(text, i + 1) + 1
        else:
            i += 1
            if c == "}":
                lvl -= 1
                if not lvl:
                    return i
    return n


def _sub_end(text: str, i: int, bash3: bool, depth: int) -> int:
    """The index of the `)` that closes a `$(` opened before `i`, or the text's end (g8a R6):
    quoting starts afresh; a `case` pattern's `)` and one in a `${` close nothing, where bash 3.2
    reads otherwise (`bash3`); past `_NEST` nested substitutions it raises `_Bound`."""
    if depth > _NEST:
        raise _Bound(text[:80])
    n, par, cases, quote, word, cmd = len(text), 0, 0, None, True, True
    while i < n:
        c = text[i]
        if quote in ("'", "$'"):
            if c == "\\" and quote == "$'":
                i += 1
            elif c == "'":
                quote = None
            i += 1
            continue
        if c == "\\":
            i, word = i + 2, False
            continue
        if text.startswith("$((", i):
            i, word = _arith_end(text, i + 3), False
            continue
        if text.startswith("$(", i):
            i, word = _sub_end(text, i + 2, bash3, depth + 1) + 1, False
            continue
        if c == "`":
            i, word = _tick_end(text, i + 1) + 1, False
            continue
        if quote == '"':
            quote = None if c == '"' else quote
            i += 1
            continue
        if text.startswith("${", i) and not bash3:
            i, word = _brace_end(text, i + 2, bash3, depth), False
            continue
        if word and c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if word and c not in " \t\n;&|()<>":
            m = _KEY.match(text, i) if cmd and not bash3 else None
            w = m.group() if m else ""
            cases += (w == "case") - (w == "esac" and cases > 0)
            cmd = w in _LEAD
        if c in "'\"":
            quote = c
        elif c == "$" and text[i + 1:i + 2] == "'":
            quote, i = "$'", i + 1
        elif c == "(":
            par, cmd = par + 1, True
        elif c == ")":
            if par:
                par -= 1
            elif not cases:
                return i
            cmd = True                    # a pattern's `)`: its body starts
        elif c in ";&|\n":
            cmd = True
        word = c in " \t\n;&|()<>"
        i += 1
    return n


def _subst(text: str, body: bool, bash3: bool, depth: int):
    """(the text with each `$(...)`, `$((...))` and backtick pair a placeholder, [(as written,
    the texts to walk)])
    (g8a R6): outside single quotes and comments, in double quotes too; a heredoc's body
    (`body`) knows no quote. `$((` holds none; in backticks one `\\` is taken off."""
    out, subs, i, n, quote, word = [], [], 0, len(text), None, True
    while i < n:
        c = text[i]
        if quote in ("'", "$'"):
            if c == "\\" and quote == "$'":
                out.append(text[i:i + 2])
                i += 2
                continue
            quote = None if c == "'" else quote
            out.append(c)
            i += 1
            continue
        if c == "\\":
            out.append(text[i:i + 2])
            i, word = i + 2, False
            continue
        if text.startswith("$((", i):     # arithmetic: no command, but a `$(` in it runs
            j = _arith_end(text, i + 3)
            subs.append((text[i:j], [t for _, ts in _subst(text[i + 3:j - 2], True, bash3,
                                                            depth)[1] for t in ts]))
            out.append(_SUB_PH % (len(subs) - 1))
            i, word = j, False
            continue
        if text.startswith("$(", i) or c == "`":
            if c == "`":
                j = _tick_end(text, i + 1)
                inner = re.sub(r"\\([\\`$])", r"\1", text[i + 1:j])
            else:
                j = _sub_end(text, i + 2, bash3, depth + 1)
                inner = text[i + 2:j]
            subs.append((text[i:j + 1], [inner]))
            out.append(_SUB_PH % (len(subs) - 1))
            i, word = j + 1, False
            continue
        if body or quote == '"':
            quote = None if c == '"' and not body else quote
            out.append(c)
            i += 1
            continue
        if c == "#" and word:
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(text[i:j])
            i = j
            continue
        if c in "'\"":
            quote = c
        elif c == "$" and text[i + 1:i + 2] == "'":
            quote = "$'"
            out.append("$'")
            i += 2
            continue
        out.append(c)
        word = c in " \t\n;&|()<>"
        i += 1
    return "".join(out), subs


def _split(text: str, bash3: bool, ticks: bool, depth: int) -> tuple:
    """(substitutions, `_commands`' yields with their operators, the ValueError or None)."""
    held, subs = _subst(text, False, bash3, depth)
    read, err = [], None
    try:
        for c in _commands(held, bash3, ticks, ops=True):
            read.append(c)
    except ValueError as e:
        err = e
    return subs, read, err


def _head(words: list, whole: set):
    """g8a R4: (the command word's index, whether a reserved word leads, `env -S`'s text or
    None) past reserved words, assignments and wrappers, an operand-taking option's operand
    taken; `command -v` and `env -S` are the command. A word that is a substitution alone
    (its index in `whole`) is passed too: its output may be empty, as the pin read it."""
    lead, run, i, wrap, at = False, True, 0, None, 0
    while i < len(words):
        w = words[i]
        opt = w.startswith("-") and i + 1 < len(words)
        if wrap == "command" and w in ("-v", "-V"):
            return at, lead, None
        if wrap == "env" and w.startswith(("-S", "--split-string")):
            if w in ("-S", "--split-string"):
                return at, lead, words[i + 1] if i + 1 < len(words) else ""
            return at, lead, w[2:] if w.startswith("-S") else w.partition("=")[2]
        if run and (w in _LEAD or (opt and "time" in words[:i])):
            lead = lead or (w in _LEAD and w != "time")
        elif _ASSIGN.match(w) or w in _WRAPPERS or opt or i in whole:
            run = False
        else:
            break
        if w in _WRAPPERS:
            wrap, at = w, i
        elif opt and w in _WRAP_TAKES.get(wrap, ()):
            i += 1
        i += 1
    return i, lead, None


def _script(args: list):
    """g8a R5: a shell's arguments read: (`c`, the `-c` text's index or None), (`file`, the
    script's index) or (`in`, None) where it reads its script from its input."""
    has_c = has_s = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if len(a) < 2 or a[0] not in "-+":
            break
        if a.startswith("--"):
            i += 2 if a in ("--rcfile", "--init-file") else 1
            continue
        has_c = has_c or (a[0] == "-" and "c" in a)
        has_s = has_s or (a[0] == "-" and "s" in a)
        i += 1 + a[1:].lower().count("o")      # `-o x`, `+o x`, `-O x`: an operand each
    if has_c:
        return "c", (i if i < len(args) else None)
    if "-c" in args:                      # g3: the pin's reading, a `-c` after the operand
        k = args.index("-c") + 1
        return "c", (k if k < len(args) else None)
    if has_s or i >= len(args) or args[i] == "-":
        return "in", None
    return "file", i


def _walk(text: str, bodies: list, quoted: list, opers: list, st: list, fa: int, env,
          level: int, bash3: bool, ticks: bool, cache: dict, depth: int = 0,
          follow: bool = False):
    """g8a R3, the one walk: each command of a text (`_here_scan`'s) and each part not read, in
    the line's order, a substitution's commands right after the command whose word holds them,
    read in a subshell's folder scope at the same level; with `follow` a first-level shell's
    script is walked at level 1 after them. `st`, `fa`: the folder states (r1 R1)."""
    if depth > _NEST:
        raise _Bound(text[:80])
    key = ("split", text, bash3, ticks)
    if key not in cache:
        cache[key] = _split(text, bash3, ticks, depth)
    subs, read, err = cache[key]
    walked, subshells, pipe = set(), [], []

    def put(w):
        w = _SUB_RE.sub(lambda m: subs[int(m.group(1))][0], w)
        return _PH_ANY.sub(lambda m: opers[int(m.group(1))], w) if "__g3_" in w else w

    def under(texts, st, fa):
        for t in texts:
            yield from _walk(t, bodies, quoted, opers, list(st), fa, env, level, bash3, ticks,
                             cache, depth + 1, follow)
    for words, outs, before, ins in read:
        if outs is None:                  # r1 F1, r2 F3: a subshell's `cd` and pushd end with it
            if words == "(":
                subshells.append((st, fa))
            elif subshells:
                st, fa = subshells.pop()
            else:                         # a `)` with no `(`: the folder is unknown
                st, fa = [(None, ())], 0
            continue
        if before not in ("|", "|&", "(", ")"):
            pipe = []
        ids = [int(k) for w in words + outs + [t for _, t in ins] for k in _SUB_RE.findall(w)]
        docs = [int(m.group(1)) for m in map(_PH_RE.match, words) if m]
        mine = [bodies[k] for k in docs]
        raw = [w for w in words if not _PH_RE.match(w)]
        words = [put(w) for w in raw]
        outs = [put(o) for o in outs if not _PH_RE.match(o)]
        if words and not words[-1].strip("`"):
            words.pop()                   # r3 F6: a lone closing backtick is no argument, and
        words = [w if w.strip("`") in _CDS or not w.strip("`") else w.strip("`")
                 for w in words]          # one at a word's end is the line's (R8: no `cd`)
        i, lead, said = _head(words, {j for j, w in enumerate(raw) if _SUB_RE.fullmatch(w)})
        heres = list(dict.fromkeys([st[fa][0]] + [f for f, _ in st]))
        name = os.path.basename(words[i]) if i < len(words) else None
        args, script, why, wtext = words[i + 1:], None, "", None
        if name is not None and name.lower() in _SHELLS5:
            kind, k = _script(args)
            if kind == "c" and k is not None:
                script = _SUB_RE.sub(_SUB_OUT, raw[i + 1 + k])
            elif kind == "in" and docs:
                d = docs[-1]
                script = bodies[d] if quoted[d] else re.sub(
                    r"\\([$`\\])|\\\n", lambda m: m.group(1) or "",
                    _SUB_RE.sub(_SUB_OUT, _body(cache, bodies[d], bash3, depth)[0]))
            elif kind == "in" and any(op == "<<<" for op, _ in ins):
                why, wtext = "piped", put([t for op, t in ins if op == "<<<"][-1])
            elif kind == "in" and before in ("|", "|&") and pipe:
                why, wtext = "piped", " ".join(pipe)
            if script is not None and level >= 1:
                why, wtext, script = "below", script, None
        elif name == "eval":
            why, wtext = "eval", " ".join(args)
        if said is not None:
            why, wtext = "eval", said
        yield _Step("", pre=words[:i], name=name, args=args, outs=outs, heres=heres, mine=mine,
                    script=script, level=level, st=st, fa=fa)
        if why:
            yield _Step(why, text=wtext, level=level)
        pipe.append(" ".join(words + mine))
        st0, fa0 = st, fa
        if name in _CDS:                  # r1 R1: behind a reserved word a `cd` may not run, so
            moved = [_move(name, args, s, env) for s in st]    # it adds a folder, replaces none
            st, fa = _states(st + moved, len(st) + fa) if lead else _states(moved, fa)
        walked.update(ids)
        yield from under([t for k in ids for t in subs[k][1]], st0, fa0)
        for d in docs:
            if not quoted[d]:
                yield from under([t for _, ts in _body(cache, bodies[d], bash3, depth)[1]
                                  for t in ts], st0, fa0)
        if follow and script is not None:
            if ("parse", script) not in cache:
                cache["parse", script] = _parse(script, bash3, ticks)
            t, b, q, o, _ = cache["parse", script]
            yield from _walk(t, b, q, o, list(st0), fa0, env, level + 1, bash3, ticks, cache,
                             0, follow)
    yield from under([t for k, (_, ts) in enumerate(subs) if k not in walked for t in ts],
                     st, fa)
    if err is not None:
        yield _Step("split", text=put(text), err=err, level=level, top=depth == 0,
                    first=depth == 0 and all(outs is None for _, outs, _, _ in read))


def _body(cache: dict, body: str, bash3: bool, depth: int) -> tuple:
    """An unquoted heredoc's body: (its text with placeholders, its substitutions)."""
    if ("body", body, bash3) not in cache:
        cache["body", body, bash3] = _subst(body, True, bash3, depth)
    return cache["body", body, bash3]


def commands(command: str, cwd, env) -> tuple:
    """g8a R2: ([Cmd], [Unread]) of a line, in its order, read by `_walk`; a first-level shell's
    script at level 1. Where bash 3.2's reading, or the one that masks no pattern's `)` in
    backticks, reads the line otherwise, its commands not met follow (as `_others`). Raises
    `_Bound` past a bound and nothing else."""
    cache, cmds, unread, have = {}, [], [], set()
    text, bodies, quoted, opers, other = _parse(command, False, True)

    def take(s, extra):
        if s.why:
            u = Unread(s.why, command if s.top and s.level == 0 else s.text)
            if u not in unread and not (extra and s.why == "split"):
                unread.append(u)
            return
        c = Cmd(s.name or "", s.args, s.pre, s.heres, s.level)
        k = (c.name, tuple(c.args), tuple(c.pre), c.level)
        if not extra or k not in have:
            cmds.append(c)
            have.add(k)
    for s in _walk(text, bodies, quoted, opers, [(cwd, ())], 0, env, 0, False, True, cache, 0,
                   True):
        take(s, False)
    for r in other:
        for s in _walk(text, bodies, quoted, opers, [(cwd, ())], 0, env, 0, *r, cache, 0, True):
            take(s, True)
    return cmds, unread


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

