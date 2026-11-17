"""g8: the stray-write refusals of a Bash line, each with its mark (design/20 §3 items 7 to 13).

`check(payload, env)` judges the commands `shellreader.commands` reads from a line by the rules of
`RULES` and answers `{}` or one `deny`, never anything else. Each rule has a strict judge, which
reads one `Cmd`, and a loose one, which reads the text of an `Unread` part the reader could not
split into commands. A refusal leaves its mark, `sessions/<sid>/refused/<tool_use_id>`, and one
line in the session's guard log. No process is run and no setting turns a rule off: a rule is
armed by the product, or by a title in the `CLAUDE.md` files a checkout reads.
"""

from __future__ import annotations

import os
import re

from . import instructionguard, resolver, shellreader, store

HEAD = "agentik-session: refused by"
PRODUCT = "product"                       # armed in every session (question 53: on everywhere)
PLUGIN = "entry 11 of agentik-session's DECISIONS.md, in every session"   # g10 R7
STRICT, LOOSE = instructionguard.STRICT, instructionguard.LOOSE
ARM_BYTES = 262144                        # R7: the first bytes of each file read for a title
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")

# ---- R5: the first look ---------------------------------------------------------------------


def looks(command: str, helper: bool = False) -> bool:
    """R5: whether a line may hold a rule's command: `git` or `rm` as a substring, case-blind,
    once each backslash-newline is taken out; for a helper's line (g10 R5) `gate` too. A line it
    passes is never read."""
    t = command.replace("\\\n", "").lower()
    return "git" in t or "rm" in t or (helper and "gate" in t)


# ---- R6, R7: the folder, the checkout, the arming ---------------------------------------------


def top_of(folder, seen: dict):
    """R6: the checkout's top for a folder: from its real path, the first folder up that holds an
    entry named `.git`; None for a folder that does not exist or is in no checkout."""
    if folder is None:
        return None
    if folder not in seen:
        p, top = os.path.realpath(folder), None
        if os.path.isdir(p):
            while True:
                if os.path.lexists(os.path.join(p, ".git")):
                    top = p
                    break
                up = os.path.dirname(p)
                if up == p:
                    break
                p = up
        seen[folder] = top
    return seen[folder]


def _fence(line: str):
    """A fence's mark at a line's start, or None; a backtick mark whose rest of line holds a
    backtick is a code span and opens no fence (CommonMark 4.5; review 1 F2)."""
    m = re.match(r" {0,3}(`{3,}|~{3,})", line)
    if not m or (m.group(1)[0] == "`" and "`" in line[m.end():]):
        return None
    return m.group(1)


def _title_in(path: str, title: str):
    """(N, line number) of the first line of a file that arms `title`, or None (R7)."""
    try:
        with open(path, "rb") as f:
            raw = f.read(ARM_BYTES)
    except OSError:
        return None
    entry = re.compile(r"(\d+)\. \*\*" + re.escape(title) + r"\.\*\*")
    short = re.compile(r"- (\d+) " + re.escape(title) + r" \(")
    fence = None
    for n, line in enumerate(raw.decode("utf-8", "replace").split("\n"), 1):
        mark = _fence(line)
        if fence is None and mark:
            fence = mark
            continue
        if fence is not None:
            if mark and mark[0] == fence[0] and len(mark) >= len(fence) \
                    and not line.strip()[len(mark):].strip():
                fence = None
            continue
        m = entry.match(line) or short.match(line)
        if m:
            return m.group(1), n
    return None


def _in_home(d: str, homes: set) -> bool:
    return any(d == h or d.startswith(h.rstrip("/") + "/") for h in homes)


def arming(title: str, top: str, env):
    """R7: (the file, N, the line's number) that arms `title` for a checkout's top, or None: its
    own `CLAUDE.md`, then each folder's above it that is the home folder or inside it, then the
    user's. Read afresh on every call."""
    files = [os.path.join(top, "CLAUDE.md")]
    homes = instructionguard._homes(env)
    d = os.path.dirname(top)
    while True:
        if _in_home(d, homes):
            files.append(os.path.join(d, "CLAUDE.md"))
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    files.append(os.path.join(instructionguard.user_dir(env), "CLAUDE.md"))
    for f in dict.fromkeys(files):
        got = _title_in(f, title)
        if got:
            return (f, got[0], got[1])
    return None


class _Ctx:
    """One call's reading: where the shell stands, the line's commands and assignments, the
    checkouts found so far (this call only), and R12's passes to log."""

    def __init__(self, payload, env, command, here, cmds):
        self.payload, self.env, self.command, self.here, self.cmds = (payload, env, command,
                                                                      here, cmds)
        self.tops, self.arms, self.passes = {}, {}, []
        self.assigns = _assigns(cmds)

    def armed(self, cell: str, top):
        """What arms a rule for a checkout: (`product`,) for a product rule, else the title's
        (file, N, line), or None."""
        if cell == PRODUCT:
            return (PRODUCT,)
        if top is None:
            return None
        if (cell, top) not in self.arms:
            self.arms[cell, top] = arming(cell, top, self.env)
        return self.arms[cell, top]

    def at_here(self, cell: str):
        """The folder test where the shell stands: (top, arming) or None."""
        top = top_of(self.here, self.tops)
        if top is None:
            return None
        got = self.armed(cell, top)
        return (top, got) if got else None


# ---- R8 to R11: the judges ----------------------------------------------------------------------

_RM_SAFE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:\?[^}]*\}")
_RM_VAR = re.compile(r"\$[A-Za-z_{(]")
_ELSEWHERE = ("-C", "--git-dir", "--work-tree")
_ENV_ELSEWHERE = ("GIT_DIR=", "GIT_WORK_TREE=")
_CFG_TAKES = frozenset({"--file", "-f", "--blob", "--type", "--default", "--comment"})
_CFG_READS = frozenset({"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--unset",
                        "--unset-all", "--list", "-l", "--global", "--system", "--file", "-f",
                        "--blob", "--edit", "-e"})
_CFG_FIRST = frozenset({"get", "unset", "list", "edit", "rename-section", "remove-section"})
_IDENTITY = frozenset({"user.name", "user.email"})
_ADD_LONG = frozenset({"--all", "--update"})
_ADD_OPS = frozenset({".", "./", ":/", "*"})
_COMMIT_TAKES = frozenset("mFCct")
_COMMIT_ATTACHED = frozenset("uS")       # an operand only attached: `-uall`, `-S3a5f` (review 1 F3)
_COMMIT_LONG = frozenset({"--message", "--file", "--reuse-message", "--reedit-message",
                          "--template", "--author", "--date", "--fixup", "--squash", "--cleanup",
                          "--trailer", "--pathspec-from-file", "-m", "-F", "-C", "-c", "-t"})


def _recursive(a: str) -> bool:
    return a == "--recursive" or (a.startswith("-") and not a.startswith("--")
                                  and bool(set("rR") & set(a)))


def _rm(c, k, ctx, cell):
    """R8: a recursive `rm` with a word that holds a variable once each `${NAME:?...}` is out."""
    if c.name.lower() != "rm" or not any(_recursive(a) for a in c.args):
        return None
    if not any(_RM_VAR.search(_RM_SAFE.sub("", a)) for a in c.args):
        return None
    if cell == PRODUCT:
        return (None, (PRODUCT,))
    return ctx.at_here(cell)


def _git(c):
    """git's (globals, subcommand, rest) for a `Cmd` named git, case-blind, else None."""
    if c.name.lower() != "git":
        return None
    return shellreader.git_words(c.args)


def _elsewhere(c, globs) -> bool:
    return (any(o.split("=", 1)[0] in _ELSEWHERE for o, _ in globs)
            or any(p.startswith(_ENV_ELSEWHERE) for p in c.pre))


def _init(c, k, ctx, cell):
    """R9: `git init` or `git init-db`, aimed nowhere else, while the shell stands in a
    checkout. A `cd` in the line is not trusted."""
    g = _git(c)
    if g is None or g[1] not in ("init", "init-db") or _elsewhere(c, g[0]):
        return None
    return ctx.at_here(cell)


def _sets_identity(rest: list) -> bool:
    if rest and rest[0] in _CFG_FIRST:
        return False
    if any(w.split("=", 1)[0] in _CFG_READS for w in rest):
        return False
    words = rest[1:] if rest and rest[0] == "set" else rest
    ops, i, done = [], 0, False
    while i < len(words):
        w = words[i]
        if not done and w == "--":
            done = True
        elif not done and w in _CFG_TAKES:
            i += 1
        elif done or not w.startswith("-") or w == "-":
            ops.append(w)
        i += 1
    return len(ops) >= 2 and ops[0].lower() in _IDENTITY


def _identity(c, k, ctx, cell):
    """R10: a `git config` that sets `user.name` or `user.email`, where R9 would judge."""
    g = _git(c)
    if g is None or g[1] != "config" or _elsewhere(c, g[0]) or not _sets_identity(g[2]):
        return None
    return ctx.at_here(cell)


def sweeping(sub: str, rest: list) -> bool:
    """R11: a `git add` or `git stage` of everything, or a `git commit -a`."""
    if sub in ("add", "stage"):
        done, i = False, 0
        while i < len(rest):
            w = rest[i]
            if done or not w.startswith("-") or w == "-":
                if w in _ADD_OPS:
                    return True
            elif w == "--":
                done = True
            elif w in _ADD_LONG:
                return True
            elif w == "--pathspec-from-file":
                i += 1
            elif not w.startswith("--") and set("Au") & set(w[1:]):
                return True
            i += 1
        return False
    if sub == "commit":
        i = 0
        while i < len(rest):
            w = rest[i]
            if w == "--":
                return False
            if w == "--all":
                return True
            if w in _COMMIT_LONG:
                i += 2
                continue
            if w.startswith("-") and not w.startswith("--"):
                for n, ch in enumerate(w[1:]):
                    if ch == "a":
                        return True
                    if ch in _COMMIT_TAKES:
                        i += 1 if n == len(w) - 2 else 0
                        break
                    if ch in _COMMIT_ATTACHED:
                        break
            i += 1
    return False


# ---- R12: the checkout the sweep would write ----------------------------------------------------

_ASSIGN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)\Z", re.S)
_EXPORTS = frozenset({"export", "local", "readonly", "declare", "typeset"})
_ONEVAR = re.compile(r"\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})\Z")
_HOLDS_VAR = re.compile(r"\$(?:[A-Za-z_]|\{)")
_SAFE_VAR = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*:\?")
_MKTEMP = re.compile(r"(?:\$\(|`)\s*mktemp(?:\s|\)|`|\Z)")
_EXPANDS = re.compile(r"[$`]")
# a subshell, a pipe or a background job may hold an assignment the reader gives at level 0, and
# the `Cmd` carries no scope (R1): such a line is read again in its text (`_unsure`, review 1 F1)
_SCOPED = re.compile(r"[(|`]|(?<![&>])&(?![&>])")
_CLOSES = re.compile(r"[)}`|]|(?<![&>|])&(?![&>])")
_PIPE = re.compile(r"(?<!\|)\|(?!\|)")
_BRACED = re.compile(r"\$\{[^{}]*\}")


def _assigns(cmds) -> dict:
    """Each variable's assignments in the line: [(the command's index, the value or None, the
    level, whether it stands alone: in a command of assignments alone, or after `export` and
    its kin, with no reserved word before it)]."""
    out = {}
    for k, c in enumerate(cmds):
        clean = all(_ASSIGN.match(p) for p in c.pre)
        for p in c.pre:
            m = _ASSIGN.match(p)
            if m:
                out.setdefault(m.group(1), []).append((k, m.group(2), c.level,
                                                       clean and c.name == ""))
        if c.name in _EXPORTS:
            for a in c.args:
                m = _ASSIGN.match(a)
                if m:
                    out.setdefault(m.group(1), []).append((k, m.group(2), c.level, clean))
        if c.name in ("for", "select") and c.args:
            out.setdefault(c.args[0], []).append((k, None, c.level, False))
        if c.name in ("read", "mapfile", "readarray", "getopts", "printf"):
            for a in c.args:
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", a):
                    out.setdefault(a, []).append((k, None, c.level, False))
    return out


def _tilde(w: str, env):
    if w == "~" or w.startswith("~/"):
        home = env.get("HOME")
        return home + w[1:] if home else None
    return None if w.startswith("~") else w


def _unsure(name: str, text: str) -> bool:
    """Whether something on the line may change the scope of `name`'s assignment before the
    sweep reads it (review 1 F1): a pipe before the sweep's word, or a `)`, a `}`, a backtick or a
    lone `&` between the assignment and that word. The text is read as written, quotes and all,
    so a doubt answers yes; a line with none of `( | ` &` answers no at once."""
    if not _SCOPED.search(text):
        return False
    n = re.escape(name)
    starts = [m.start() for m in re.finditer(r"(?<![\w$])" + n + "=", text)]
    word = r"\$(?:\{" + n + r"\}|" + n + r"(?!\w))"
    ends = [m.start() for m in re.finditer(r"(?<![\w-])-C\s*['\"]?" + word, text)] or \
        [m.start() for m in re.finditer(r"\$(?:\{" + n + r"[}:]|" + n + r"(?!\w))", text)]
    if not starts or not ends or starts[0] > ends[-1]:
        return True
    if _PIPE.search(text, 0, ends[-1]):
        return True
    return bool(_CLOSES.search(_BRACED.sub("", text[starts[0]:ends[-1]])))


def _assigned(name: str, c, k: int, ctx):
    """The one assignment R12 follows: (`literal`, value, unsure), (`mktemp`, None, False) or
    None. `unsure`: the line may run the sweep where the assignment does not hold (`_unsure`)."""
    got = ctx.assigns.get(name, [])
    if len(got) != 1:
        return None
    j, val, level, alone = got[0]
    if j >= k or level != c.level or not alone or val is None:
        return None
    if _MKTEMP.match(val):
        return ("mktemp", None, False)
    if _EXPANDS.search(val):
        return None
    lit = _tilde(val, ctx.env)
    return ("literal", lit, _unsure(name, ctx.command)) if lit is not None else None


def _spelled(v: str, c, k: int, ctx):
    """R12's three spellings of a `-C` word that pass the command, or None."""
    if _SAFE_VAR.search(v):
        return "a -C word that stops on an empty variable, `${NAME:?}`"
    m = _ONEVAR.match(v)
    if m:
        got = _assigned(m.group(1) or m.group(2), c, k, ctx)
        return "a -C variable the line assigns once from mktemp" if got and \
            got[0] == "mktemp" else None
    if _HOLDS_VAR.search(v):
        return "a -C word longer than the variable it holds"
    return None


def _literal(v: str, c, k: int, ctx, beside: bool = False):
    """A `-C`, `--work-tree` or `--git-dir` word as a path, or None to skip it. With `beside`, a
    followed variable whose scope may change is skipped: the folder so far (review 1 F1)."""
    m = _ONEVAR.match(v)
    if m:
        got = _assigned(m.group(1) or m.group(2), c, k, ctx)
        if not got or got[0] != "literal" or (beside and got[2]):
            return None
        return got[1]
    if _EXPANDS.search(v):
        return None
    return _tilde(v, ctx.env)


def _named(globs, c, opt: str, var: str):
    for o, v in globs:
        if o == opt and v is not None:
            return v
        if o.startswith(opt + "="):
            return o.split("=", 1)[1]
    for p in c.pre:
        if p.startswith(var):
            return p[len(var):]
    return None


def _target(start, globs, c, k: int, ctx, beside: bool = False):
    """The folder a sweep writes from one starting folder, or None where git stops; `beside` as
    in `_literal`."""
    f = start if start is not None and os.path.isdir(start) else ctx.here
    for o, v in globs:
        if o != "-C" or v is None:
            continue
        w = _literal(v, c, k, ctx, beside)
        if w is None:
            continue
        f = os.path.normpath(os.path.join(f, w))
        if not os.path.isdir(f):
            return None
    wt = _named(globs, c, "--work-tree", "GIT_WORK_TREE=")
    gd = _named(globs, c, "--git-dir", "GIT_DIR=")
    wt = None if wt is None else _literal(wt, c, k, ctx, beside)
    gd = None if gd is None else _literal(gd, c, k, ctx, beside)
    if wt is not None:
        return os.path.normpath(os.path.join(f, wt))
    if gd is not None:
        g = os.path.normpath(os.path.join(f, gd))
        return os.path.dirname(g) if os.path.basename(g) == ".git" else g
    return f


def _sweep(c, k, ctx, cell):
    """R11, R12: a sweep whose checkout, from any folder the command may run in, is armed."""
    g = _git(c)
    if g is None or ctx.here is None or not sweeping(g[1], g[2]):
        return None
    for o, v in g[0]:
        if o == "-C" and v is not None:
            why = _spelled(v, c, k, ctx)
            if why:
                ctx.passes.append(why)
                return None
    return _found(c, k, ctx, cell, g[0])


def _found(c, k, ctx, cell, globs):
    """R12's finding: (top, arming) of the first armed checkout a git command may act on, from
    each folder it may run in, the followed variable alone and beside the folder so far."""
    for start in c.heres:
        for beside in (False, True):
            top = top_of(_target(start, globs, c, k, ctx, beside), ctx.tops)
            got = ctx.armed(cell, top) if top else None
            if got:
                return (top, got)
    return None


# ---- g10: the push rule -------------------------------------------------------------------------

_PUSHES = frozenset({"push", "send-pack", "http-push"})
_TOOLS = frozenset({"agentik-session", "claude-session"})
_SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash"})
_PY_NAME = re.compile(r"python[0-9.]*\Z")
_LAND_PUSH = frozenset({"--p", "--pu", "--pus", "--push"})    # what argparse takes, measured
_LAND_TAKES = ("--session", "--wall")                         # land's options with an operand
_BRACE_LIST = re.compile(r"\{[^{}]*(?:,|\.\.)[^{}]*\}")
# review 1 fix 1: a command word another command may run, by its base name (a python name too)
_STARTS = frozenset({"git", "agentik", *_TOOLS, *_SHELL_NAMES})
# the commands whose words are data, never a command they run; any other command's are read
_PRINTERS = frozenset({"echo", "printf", "print", "grep", "egrep", "fgrep", "rg", "ag", "ack",
                       "sed", "awk", "cat", "head", "tail", "less", "more", "wc", "sort", "uniq",
                       "tee", "ls", "test", "[", "[[", ":", "true", "false", "man", "which",
                       "type", "whence", "where", "help", "pbcopy", "say", "logger", "jq",
                       "printenv", "export", "local", "readonly", "declare", "typeset", "read",
                       "alias", "unalias", "basename", "dirname", "realpath", "readlink", "cut",
                       "tr", "diff", "cmp"})


def _py_script(args: list):
    """(the script word, the words after it) of a python's arguments; `-m claude_session` reads
    as the tool. None for `-c`, another module, or a script from the input."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        j = i + 1
        if not a.startswith("--"):
            for n, ch in enumerate(a[1:], 2):
                if ch == "c":
                    return None
                if ch in "mWX":
                    op = a[n:] or (args[j] if j < len(args) else "")
                    j += 0 if a[n:] else 1
                    if ch == "m":
                        return ("agentik-session", args[j:]) if op == "claude_session" else None
                    break
        i = j
    return (args[i], args[i + 1:]) if i < len(args) and args[i] != "-" else None


def _tool_words(c):
    """R3: the words after the session tool's own word(s), or None for a command that runs no
    session tool: its command word, or an interpreter's script word, by its base name."""
    name = c.name.lower()
    if _PY_NAME.match(name):
        got = _py_script(c.args)
    elif name in _SHELL_NAMES:
        how, i = shellreader._script(c.args)
        got = (c.args[i], c.args[i + 1:]) if how == "file" else None
    else:
        got = (c.name, c.args)
    if got is None:
        return None
    base, rest = os.path.basename(got[0]).lower(), got[1]
    if base in _TOOLS:
        return rest
    if base != "agentik" or not rest:
        return None
    if _veiled(rest[0]):                    # review 1 fix 2: at `session`'s place, read as `gate`'s
        return rest
    return rest[1:] if rest[0] == "session" else None


def _veiled(w: str) -> bool:
    """Review 1 fix 2: a word the shell expands at a verb's place: it holds `$`, a backtick or a
    brace list, or a space (the reader's text of a backtick substitution)."""
    return bool(_EXPANDS.search(w) or _BRACE_LIST.search(w)) or any(ch.isspace() for ch in w)


def _takes(w: str) -> bool:
    return len(w) > 2 and "=" not in w and any(o.startswith(w) for o in _LAND_TAKES)


def _pushing_verb(words: list):
    """R3: the repo operands of `gate publish`, or of `gate land` with `--push` (or an
    abbreviation argparse takes) before a `--`, each at the verb's position as the tool's parser
    places it; None for any other verb."""
    i = 0
    for want in ("gate", None):
        while i < len(words) and words[i].startswith("-"):
            if _veiled(words[i]):
                return []                               # review 1 fix 2: a word the shell expands
            i += 1                                      # global and gate's options: no operand
        if i < len(words) and _veiled(words[i]):
            return []
        if i >= len(words) or (want and words[i] != want):
            return None
        i += 1
    verb, rest = words[i - 1], words[i:]
    if verb not in ("publish", "land"):
        return None
    ops, push, done, j = [], False, False, 0
    while j < len(rest):
        w = rest[j]
        if done or not w.startswith("-") or w == "-":
            ops.append(w)
        elif w == "--":
            done = True
        elif w in _LAND_PUSH:
            push = True
        if not done and _veiled(w):
            push = True                                 # review 1 fix 2: it may expand to --push
        elif verb == "land" and _takes(w):
            j += 1
        j += 1
    if verb == "publish":
        return ops
    return ops[:1] if push else None


def _pathlike(w: str) -> bool:
    return "/" in w or w in (".", "..") or w.startswith("~")


def _starts(w: str) -> bool:
    """Review 1 fix 1: whether a word may be the command word of a command another one runs: by
    its base name git, the tool, the door, a python or a shell; a word with a space never is."""
    if not w or any(ch.isspace() for ch in w):
        return False
    b = os.path.basename(w).lower()
    return b in _STARTS or bool(_PY_NAME.match(b))


def _push(c, k, ctx, cell):
    """g10 R2, R3, review 1 fix 1: the command itself, then, unless it prints its words, each of
    its words that may start a command, judged with the words after it as that command."""
    got = _pushes(c, k, ctx, cell)
    if got or c.name.lower() in _PRINTERS:
        return got
    for i, w in enumerate(c.args):
        if _starts(w):
            got = _pushes(c._replace(name=os.path.basename(w), args=c.args[i + 1:]), k, ctx, cell)
            if got:
                return got
    return None


def _pushes(c, k, ctx, cell):
    """g10 R2, R3: a git push or its plumbing, or the tool's `gate publish` or `gate land
    --push`, in an armed checkout."""
    g = _git(c)
    if g is not None:
        sub = g[1].lower()
        if _veiled(sub) or sub in _PUSHES or (sub == "subtree" and "push" in g[2]):
            return _found(c, k, ctx, cell, g[0])
        return None
    words = _tool_words(c)
    ops = _pushing_verb(words) if words is not None else None
    if ops is None:
        return None
    starts = [s if s is not None else ctx.here for s in c.heres] + [ctx.here]
    folders = list(starts)
    for op in ops:
        w = _literal(op, c, k, ctx)
        if w is not None and _pathlike(w):
            folders += [os.path.normpath(os.path.join(s, w)) for s in starts if s is not None]
    for f in dict.fromkeys(folders):
        top = top_of(f, ctx.tops)
        got = ctx.armed(cell, top) if top else None
        if got:
            return (top, got)
    return None


# ---- R13: unread text ---------------------------------------------------------------------------

_W = r"(?:^|(?<=[\s/'\"(`{]))"
_LOOSE_RM = re.compile(_W + r"(?i:rm)(?=\s)(?=.*?(?:^|\s)['\"]?"
                       r"(?:--recursive|-[A-Za-z]*[rR][A-Za-z]*)(?:\s|['\"]|\Z))"
                       r"(?=.*?\$(?!\{[A-Za-z_][A-Za-z0-9_]*:\?))", re.S)
_LOOSE_INIT = re.compile(_W + r"(?i:git)\s.*?(?<![\w-])(?i:init)(?![\w-])", re.S)
_LOOSE_IDENTITY = re.compile(_W + r"(?i:git)\s.*?(?<![\w-])(?i:config)\s.*?"
                             r"(?<![\w.-])(?i:user\.(?:name|email))(?![\w-])", re.S)
_LOOSE_SWEEP = re.compile(
    _W + r"(?i:git)\s.*?(?:(?<![\w-])(?i:add|stage)\s(?:.*?\s)?(?:-A|--all|-u|--update|"
    r"-[A-Za-z]*[Au][A-Za-z]*|\.|\./|:/|\*)(?=[\s'\"]|\Z)|(?<![\w-])(?i:commit)\s(?:.*?\s)?"
    r"(?:--all|-[A-Za-z]*a[A-Za-z]*)(?=[\s'\"]|\Z))", re.S)
_LOOSE_PUSH = re.compile(
    _W + r"(?:(?i:git)\s.*?(?<![\w-])(?i:push|send-pack|http-push)(?![\w-])|"
    r"(?i:agentik(?:-|\s+)session|claude[-_]session)\s.*?(?<![\w-])gate\s+(?:-\S*\s+)*"
    r"(?:publish(?![\w-])|land\s(?:.*?\s)?--p(?:u(?:sh?)?)?(?=[\s'\"]|\Z)))", re.S)
_SEP = re.compile(r"[;&|\n]")


def _loosely(pattern):
    def judge(text: str) -> bool:
        return any(pattern.search(seg) for seg in _SEP.split(text))
    return judge


# ---- R3: the table --------------------------------------------------------------------------------

RULES = (
    ("rm", PRODUCT, _rm, _loosely(_LOOSE_RM)),
    ("init", PRODUCT, _init, _loosely(_LOOSE_INIT)),
    ("identity", PRODUCT, _identity, _loosely(_LOOSE_IDENTITY)),
    ("sweep", "Commits", _sweep, _loosely(_LOOSE_SWEEP)),
    ("push", "Pushes", _push, _loosely(_LOOSE_PUSH)),         # g10: a helper's call alone (R1)
)
_GIT_RULES = frozenset({"init", "identity", "sweep", "push"})
_HELPER_RULES = frozenset({"push"})


# ---- R15: the reasons -----------------------------------------------------------------------------

def _armed_by(got) -> str:
    if got[0] == PRODUCT:
        return PLUGIN
    f, n, line = got
    return f"entry {n} (`{{}}`) of {f}, line {line}"


def _reason(name: str, cell: str, top, got, how: str) -> str:
    by = _armed_by(got).replace("{}", cell)
    if name == "rm":
        text = (f"{HEAD} the rm rule, {by}: a recursive rm of a variable that may be empty "
                "removes from where the shell stands. Write `rm -rf \"${T:?}\"`, which stops "
                "when T is empty.")
    elif name == "init":
        text = (f"{HEAD} the git init rule, {by}: the shell stands in the checkout {top}, "
                "where a new repository would be made. Name the folder: `git -C <folder> init`.")
    elif name == "identity":
        text = (f"{HEAD} the identity rule, {by}: this sets a git identity in the checkout "
                f"{top}. Pass it per command: `git -c user.name=<name> -c user.email=<address> "
                "commit ...`.")
    elif name == "push":
        text = (f"{HEAD} the push rule, {by}, arms it for the checkout {top}: a helper never "
                "pushes. Hand back the branch and its head; the sitting that started you pushes.")
    else:
        text = (f"{HEAD} the sweep rule, {by}, arms it for the checkout {top}: this adds or "
                "commits every changed file there, another sitting's included. Add paths by "
                "name: `git add <path> ...`, then `git commit -m ...`.")
    if how == LOOSE:
        text += (" Part of the line could not be read as commands and holds the rule's words: "
                 "write it more simply.")
    return text


# ---- R16, R17: the mark, the log, the answer --------------------------------------------------------

def _mark(payload: dict, env, names: list) -> None:
    """R16: `sessions/<sid>/refused/<tool_use_id>`, the rules' names a line. Never raises."""
    try:
        sid, tid = payload.get("session_id"), payload.get("tool_use_id")
        if not (isinstance(sid, str) and _ID.match(sid) and isinstance(tid, str)
                and _ID.match(tid)):
            return
        sdir = resolver.session_dir(resolver.state_dir(env), sid)
        store._write_private(sdir / "refused" / tid, "".join(n + "\n" for n in names))
    except Exception:                                   # noqa: BLE001 - a mark never changes it
        pass


def _deny(text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": text}}


def _command(payload) -> str | None:
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return None
    ti = payload.get("tool_input")
    c = ti.get("command") if isinstance(ti, dict) else None
    return c if isinstance(c, str) else None


def failed(payload: dict, env, exc: BaseException) -> dict:
    """R14: an error refuses a line R5's look does not pass, with its mark `error` and one log
    line; a line the look passes is passed. Never raises."""
    try:
        command = _command(payload)
        if command is None or not looks(command, bool(payload.get("agent_id"))):
            return {}
        name = type(exc).__name__
        _mark(payload, env, ["error"])
        instructionguard.log(payload, env, "deny", None, why=f"error: {name}", rule=["error"])
        return _deny(f"{HEAD} an error in its own reading of this line ({name}): retry once, "
                     "then write the command more simply and report this line.")
    except Exception:                                   # noqa: BLE001 - R14: it still refuses
        return _deny(f"{HEAD} an error in its own reading of this line: retry once, then "
                     "write the command more simply and report this line.")


def _judge(payload: dict, env, command: str) -> list:
    """[(rule, cell, top, arming, how)] of the rules a line breaks, in the table's order."""
    cwd = payload.get("cwd")
    here = cwd if isinstance(cwd, str) and os.path.isabs(cwd) and "\0" not in cwd else None
    cmds, unread = shellreader.commands(command, here, env)
    ctx = _Ctx(payload, env, command, here, cmds)
    if here is None and "git" in command.lower():
        ctx.passes.append("no absolute cwd: the git rules judge nothing")
    hits, helper = [], bool(payload.get("agent_id"))
    for name, cell, judge, loose in RULES:
        if (name in _GIT_RULES and here is None) or (name in _HELPER_RULES and not helper):
            continue
        got = None
        for k, c in enumerate(cmds):
            got = judge(c, k, ctx, cell)
            if got:
                hits.append((name, cell, got[0], got[1], STRICT))
                break
        if got:
            continue
        texts = [u.text for u in unread if u.why != "data" and loose(u.text)]
        if not texts:
            continue
        if name == "rm" and cell == PRODUCT:
            hits.append((name, cell, None, (PRODUCT,), LOOSE))
            continue
        at = ctx.at_here(cell)
        if at:
            hits.append((name, cell, at[0], at[1], LOOSE))
    for why in ctx.passes:
        instructionguard.log(payload, env, "pass", here, why=why)
    return hits


def check(payload: dict, env) -> dict:
    """The rules' answer for one call: {} or one `deny` (R2). An error refuses (R14)."""
    command = _command(payload)
    if command is None or not looks(command, bool(payload.get("agent_id"))):
        return {}
    try:
        hits = _judge(payload, env, command)
    except Exception as e:                              # noqa: BLE001 - R14: an error refuses
        return failed(payload, env, e)
    if not hits:
        return {}
    names = [h[0] for h in hits]
    _mark(payload, env, names)
    path = next((h[2] for h in hits if h[2] is not None), None)
    instructionguard.log(payload, env, "deny", path, why=hits[0][4], rule=names)
    return _deny("\n".join(_reason(*h) for h in hits))
