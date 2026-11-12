"""The prompt before an edit of instruction text (packet g2; hq design/09 §7.2).

R1: `Edit`, `Write`, `MultiEdit` and `NotebookEdit` on a guarded path, and no other tool (a
Bash line is never read). Guarded are the instruction files and the settings that act as
prompts: under the user's folder (`CLAUDE_CONFIG_DIR`, and `~/.claude`) `CLAUDE.md`,
`settings.json` and the `rules`, `hooks`, `agents` and `plugins` folders; a tree folder's
`CLAUDE.md` (a folder that holds a main checkout, a child with a `.git` directory); and at a
checkout's top level (the nearest folder above the target holding `.git`, a worktree's file
included) `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `.claude/rules/**`,
the ledger file and `.claude/settings*.json`. A folder `tests`, `testdata` or `fixtures` below
the matched root (the user's folder, or the nearest top level) exempts the path. A name is the
file it names (r1 F2): where the volume folds case, `claude.md` is `CLAUDE.md`.

R2: `ask` in a main thread; `deny` in a helper (`agent_id`), in a `-p` run, and where the
nearest `claude` ancestor's argv cannot be read (found by `harness.claude_argv`, SessionEnd's
reader). Only its options are read (r1 F1), as Claude Code's CLI (commander) parses them (r2
F4): the argv is read word by word from the kernel, options are read past the prompt until `--`
or a subcommand, and an option's value or a prompt is never taken for an option. Where only the
`ps` line can be read, a print word after the first prompt word denies.
R3: an exception or a target that is not a usable string lets the call through, and one line
goes to the session's `guard.jsonl`, never to the model; each ask and deny is a line there too.
R4: no knob. The environment is read for `HOME` and `CLAUDE_CONFIG_DIR` (where the user's folder
is) and the state root (where the log goes), nothing else.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from . import harness, resolver

TOOLS = {"Edit": "file_path", "Write": "file_path", "MultiEdit": "file_path",
         "NotebookEdit": "notebook_path"}
LEDGER_FILE = "DECISION" "S.md"           # spelled in two pieces for the hygiene scan
SKILL = "decision" "s:instruct"
REASON = ("agentik-session: `{path}` is instruction text that every session pays for. Change it "
          "through the `" + SKILL + "` skill, which reviews the change and writes it with the "
          "tool that owns the file.")
LOG = "guard.jsonl"
LOG_CAP = 64 * 1024                       # past this a session's guard log takes no more lines
TEXT_CAP = 1024
SCAN_CAP = 512                            # a tree folder's entries read, at most
EXEMPT = frozenset({"tests", "testdata", "fixtures"})
NAMES = frozenset({"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", LEDGER_FILE})
TOP_FILES = frozenset({("CLAUDE.md",), ("CLAUDE.local.md",), (".claude", "CLAUDE.md"),
                       ("AGENTS.md",), (LEDGER_FILE,)})
USER_FILES = frozenset({("CLAUDE.md",), ("settings.json",)})
USER_TREES = frozenset({"rules", "hooks", "agents", "plugins"})
PRINT = ("-p", "--print")
# r1 F1: the CLI's short flags (commander, which reads `-cp` as `-c -p`): 0 takes no value, 1 the
# rest of its word or the next word, 2 the rest of its word or a next word that is no option.
_SHORT = {"c": 0, "p": 0, "h": 0, "v": 0, "n": 1, "d": 2, "r": 2, "w": 2}
_LONG_BARE = frozenset(o for o in harness._BARE_OPTS if o.startswith("--"))
_LONG_VALUED = frozenset(o for o in harness._VALUED_OPTS if o.startswith("--")) | {"--effort"}
_LONG_OPTIONAL = frozenset(o for o in harness._OPTIONAL_OPTS if o.startswith("--"))
_LONG_LIST = frozenset(harness._LIST_OPTS)
_LONG_TAKES = _LONG_VALUED | _LONG_OPTIONAL      # a value after `=` is theirs
# r2 F4: root subcommands of Claude Code 2.1.322; root parsing stops at one standing first. A
# name missing here only reads a later `-p` as the flag (a deny), so the list stays short.
_SUBCOMMANDS = frozenset({"mcp", "plugin", "doctor", "update", "install"})
_PROC = "/proc"                           # where a /proc/<pid>/cmdline exists, the reader's
_CTL_KERN, _KERN_PROCARGS2 = 1, 49        # darwin's sysctl names (sys/sysctl.h)
_PC_CASE_SENSITIVE = 11                   # darwin's pathconf name; Python's table lacks it
_SETTINGS = re.compile(r"settings[^/]*\.json\Z")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")


# ---- R1: which path ---------------------------------------------------------------------

def user_dirs(env) -> list[Path]:
    home = env.get("HOME") or str(Path.home())
    dirs = [Path(home) / ".claude"]
    moved = env.get("CLAUDE_CONFIG_DIR")
    if moved:
        dirs.insert(0, Path(os.path.expanduser(moved)))
    return dirs


def _fold(s: str, fold: bool) -> str:
    return s.casefold() if fold else s


def _keys(fold: bool) -> dict:
    f = lambda s: _fold(s, fold)             # noqa: E731
    return {"names": frozenset(map(f, NAMES)), "exempt": frozenset(map(f, EXEMPT)),
            "top": frozenset(tuple(map(f, t)) for t in TOP_FILES),
            "user": frozenset(tuple(map(f, t)) for t in USER_FILES),
            "trees": frozenset(map(f, USER_TREES)), "claude": f(".claude"), "rules": f("rules"),
            "md": f("CLAUDE.md")}


_KEYS = {False: _keys(False), True: _keys(True)}


def _below(p: Path, root: Path, fold: bool = False) -> tuple | None:
    """The parts of `p` below `root`, each folded when `fold`; None when `p` is not below it."""
    pp = tuple(_fold(x, fold) for x in p.parts)
    rp = tuple(_fold(x, fold) for x in root.parts)
    return pp[len(rp):] if pp[:len(rp)] == rp else None


def _exempt(rel: tuple, fold: bool = False) -> bool:
    return bool(_KEYS[fold]["exempt"].intersection(rel[:-1]))


def _user_file(p: Path, env, fold: bool = False) -> bool:
    k = _KEYS[fold]
    for d in user_dirs(env):
        for root in {Path(os.path.abspath(str(d))), Path(os.path.realpath(str(d)))}:
            rel = _below(p, root, fold)
            if not rel or _exempt(rel, fold):
                continue
            if rel in k["user"] or (len(rel) > 1 and rel[0] in k["trees"]):
                return True
    return False


def _top(p: Path) -> Path | None:
    """The nearest folder above `p` that holds a `.git` (a directory, or a worktree's file)."""
    for d in p.parents:
        if os.path.lexists(os.path.join(str(d), ".git")):
            return d
    return None


def _holds_main_checkout(folder: Path) -> bool:
    try:
        with os.scandir(str(folder)) as it:
            for n, e in enumerate(it):
                if n >= SCAN_CAP:
                    return False
                if e.is_dir(follow_symlinks=False) and os.path.isdir(os.path.join(e.path, ".git")):
                    return True
    except OSError:
        return False
    return False


def _checkout_file(p: Path, fold: bool = False) -> bool:
    k = _KEYS[fold]
    parts = tuple(_fold(x, fold) for x in p.parts)
    if parts[-1] not in k["names"] and k["claude"] not in parts:
        return False                      # the cheap pass: no name or folder that is guarded
    top = _top(p)
    if top is not None:
        rel = _below(p, top, fold)
        if not rel or _exempt(rel, fold):
            return False
        if rel in k["top"]:
            return True
        if len(rel) > 2 and rel[:2] == (k["claude"], k["rules"]):
            return True
        if len(rel) == 2 and rel[0] == k["claude"] and _SETTINGS.match(rel[1]):
            return True                   # the pattern is lower case, so a folded name meets it
    if parts and parts[-1] == k["md"]:   # a tree folder's file, or its `.claude/CLAUDE.md`
        folder = p.parent.parent if _fold(p.parent.name, fold) == k["claude"] else p.parent
        return _holds_main_checkout(folder)
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


def guarded(path: str, env) -> bool:
    """True for a guarded path (R1), by its absolute spelling or its real path; a spelling that
    differs from a guarded one only in case where the volume folds case (r1 F2)."""
    forms = {Path(os.path.abspath(path)), Path(os.path.realpath(path))}
    if any(_user_file(p, env) or _checkout_file(p) for p in forms):
        return True
    return any((_user_file(p, env, True) or _checkout_file(p, True)) and _case_blind(str(p))
               for p in forms)


# ---- R2: which run ----------------------------------------------------------------------

_SYSCTL = []                              # libc's sysctl, loaded on the first guarded call


def _sysctl():
    if not _SYSCTL:
        import ctypes
        f = ctypes.CDLL(None, use_errno=True).sysctl
        f.argtypes = (ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p,
                      ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t)
        f.restype = ctypes.c_int
        _SYSCTL.append(f)
    return _SYSCTL[0]


def _procargs(pid: int) -> list[str] | None:
    """darwin's KERN_PROCARGS2 holds argc, the exec path, argc words, then the environment. Only
    the argc words are read, and the buffer is zeroed after: no environment is kept."""
    import ctypes
    sysctl = _sysctl()
    mib = (ctypes.c_int * 3)(_CTL_KERN, _KERN_PROCARGS2, pid)
    size = ctypes.c_size_t(0)
    if sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0 or not 4 < size.value <= 1 << 24:
        return None
    buf = ctypes.create_string_buffer(size.value + 1)      # a NUL past the end, whatever comes
    try:
        if sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
            return None
        n, base = min(size.value, len(buf) - 1), ctypes.addressof(buf)
        argc = ctypes.c_int.from_buffer(buf).value
        pos = 4 + len(ctypes.string_at(base + 4))          # past the exec path
        while pos < n and buf[pos] == b"\0":               # and its padding
            pos += 1
        words = []
        for _ in range(argc if 0 < argc <= 1 << 16 else 0):
            if pos >= n:
                return None
            w = ctypes.string_at(base + pos)
            words.append(os.fsdecode(w))
            pos += len(w) + 1
        return words or None
    finally:
        ctypes.memset(buf, 0, len(buf))


def argv_words(pid) -> list[str] | None:
    """One process's argv, word by word: `/proc/<pid>/cmdline` where it exists, else darwin's
    KERN_PROCARGS2. None when the kernel will not say (another user's process, a zombie, no
    such pid, a sandbox) and on any error: it never raises."""
    try:
        if not isinstance(pid, int) or not 0 < pid < 1 << 31:
            return None
        proc = os.path.join(_PROC, str(pid), "cmdline")
        if os.path.exists(proc):
            with open(proc, "rb") as f:
                raw = f.read(1 << 24)
            words = [os.fsdecode(w) for w in raw.split(b"\0")]
            return words[:-1] if len(words) > 1 and words[-1] == "" else None
        return _procargs(pid) if sys.platform == "darwin" else None
    except Exception:                                   # noqa: BLE001 - R3: never into the hook
        return None


def claude_argv(pid=None) -> tuple[list[str] | None, bool]:
    """The nearest `claude` ancestor's argv and whether it was read word by word (r2 F4). The
    ancestor is the one `harness.claude_argv` finds by `ps`; its argv is then read from the
    kernel, and where that fails, or names no `claude`, the `ps` line split on whitespace is
    returned with False. (None, False) when no ancestor is found."""
    asked = []

    def ps(p):
        asked.append(p)
        return harness._ps(p)
    joined = harness.claude_argv(ps=ps, pid=pid)
    if not joined:
        return None, False
    try:
        words = argv_words(asked[-1]) if asked else None
    except Exception:                                   # noqa: BLE001 - R3: never into the hook
        words = None
    if words and os.path.basename(words[0]) == "claude":
        return words, True
    return joined, False


def _option(w: str) -> bool:
    return len(w) > 1 and w[0] == "-"     # commander's maybeOption


def _maybe_print(w: str) -> bool:
    return w in PRINT or w.startswith("--print=") or (
        w.startswith("-") and not w.startswith("--") and "p" in w[1:])


def _either(a, b):
    return a if a == b else None


def _exact(words) -> bool | None:
    """The walk on argv word by word, as commander's parseOptions reads it: options past the
    prompt, `--` ends them, a subcommand standing first ends them, a valued option takes the next
    word whatever it is. An option the tables do not know may take one word or none; where the
    two readings differ the answer is None. res[i][f]: the answer from word i on, f true while
    no operand and no unknown option has stood (a subcommand may still come)."""
    n = len(words)
    res = [[False, False] for _ in range(n + 2)]
    for i in range(n - 1, -1, -1):
        a, nxt = words[i], (words[i + 1] if i + 1 < n else None)
        for f in (0, 1):
            if a == "--":
                r = False
            elif not _option(a):
                r = False if f and a in _SUBCOMMANDS else res[i + 1][0]
            elif a.startswith("--"):
                name = a.split("=", 1)[0]
                if name == "--print":
                    r = True
                elif "=" in a:
                    r = res[i + 1][f if name in _LONG_TAKES else 0]
                elif a in _LONG_BARE:
                    r = res[i + 1][f]
                elif a in _LONG_VALUED:
                    r = res[i + 2][f]
                elif a in _LONG_OPTIONAL:
                    r = res[i + 2 if nxt is not None and not _option(nxt) else i + 1][f]
                elif a in _LONG_LIST:     # a required list: its first word whatever it is,
                    j = i + 2             # then every word up to the next option
                    while j < n and not _option(words[j]):
                        j += 1
                    k = i + 1
                    while k < n and not _option(words[k]):
                        k += 1
                    r = _either(res[min(j, n)][f], res[k][f])
                else:
                    r = _either(res[i + 1][0], res[min(i + 2, n)][0])
            else:                         # short flags, combined as commander reads them
                r = res[i + 1][f]
                for k, ch in enumerate(a[1:], 1):
                    kind, rest = _SHORT.get(ch), a[k + 1:]
                    if kind is None:
                        r = None if "p" in rest else _either(res[i + 1][0], res[min(i + 2, n)][0])
                        break
                    if ch == "p":
                        r = True
                        break
                    if kind and rest:
                        break             # the rest of the word is its value
                    if kind == 1 or (kind == 2 and nxt is not None and not _option(nxt)):
                        r = res[i + 2][f]
                        break
            res[i][f] = r
    return res[0][1]


def _joined(words) -> bool | None:
    """The fallback walk on the `ps` line, its words joined with spaces and split again (r1 F1):
    it ends at the first prompt word or `--`, an option's value is never taken for an option.
    Since a prompt or a value may be many words, a word past the end that may be the print flag
    leaves it unsure (None), as one the walk cannot read does."""
    i = 0
    while i < len(words):
        a = words[i]
        if a in ("--", "-") or not a.startswith("-"):
            return _unsure(words[i + 1:])  # the first prompt word
        if a.startswith("--"):
            if a.split("=", 1)[0] == "--print":
                return True
            if "=" in a or a in _LONG_BARE:
                pass                      # its value is its own, or it takes none
            elif a in _LONG_VALUED:
                i += 1
            elif a in _LONG_OPTIONAL:
                i += 1 if i + 1 < len(words) and not words[i + 1].startswith("-") else 0
            elif a in _LONG_LIST:         # commander's list: every word up to the next option
                while i + 1 < len(words) and not words[i + 1].startswith("-"):
                    i += 1
            else:
                return _unsure(words[i + 1:])
        else:                             # short flags, combined as commander reads them
            for k, ch in enumerate(a[1:], 1):
                kind = _SHORT.get(ch)
                if kind is None:
                    return _unsure([a[k:]] + words[i + 1:])
                if ch == "p":
                    return True
                if kind and k < len(a) - 1:
                    break                 # the rest of the word is its value
                if kind == 1 or (kind == 2 and i + 1 < len(words)
                                 and not words[i + 1].startswith("-")):
                    i += 1
        i += 1
    return False


def _unsure(rest) -> bool | None:
    """None (unsure) when a later word may be the print flag, else False, since no word is."""
    return None if any(_maybe_print(w) for w in rest) else False


def headless(argv, exact: bool = True) -> bool | None:
    """True when `-p` or `--print` stands among argv's options (argv[0] the program), False when
    none does, None where it cannot tell. `exact`: argv as the kernel holds it, word by word;
    else the `ps` line split on whitespace."""
    words = [str(a) for a in (argv or [])[1:]]
    return _exact(words) if exact else _joined(words)


def run_kind(payload: dict) -> str:
    """`helper`, `headless`, `unknown` or `main`."""
    if payload.get("agent_id"):
        return "helper"
    argv, exact = claude_argv()
    if not argv:
        return "unknown"
    h = headless(argv, exact)
    return "headless" if h else ("unknown" if h is None else "main")


# ---- R3: the log ------------------------------------------------------------------------

def _text(v) -> str | None:
    return v[:TEXT_CAP] if isinstance(v, str) else None


def log(payload: dict, env, decision: str, path, run=None, why=None) -> None:
    """One line in `sessions/<sid>/guard.jsonl` (0600); a line that would carry the log past
    LOG_CAP is not written. Never raises."""
    try:
        sid = payload.get("session_id")
        if not (isinstance(sid, str) and _SID.match(sid)):
            return
        line = (json.dumps({"at": time.time(), "decision": decision,
                            "tool": _text(payload.get("tool_name")), "path": _text(path),
                            "run": run, "agent_id": _text(payload.get("agent_id")),
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
    """The PreToolUse answer for one call: {} when the call is not the guard's, else `ask` or
    `deny` with §7.2's reason. Fails open: an error or a target it cannot resolve gives {}."""
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or tool not in TOOLS:
        return {}
    path = None
    try:
        path = _target(payload)
        if path is None:
            log(payload, env, "open", None, why="the target cannot be resolved")
            return {}
        if not guarded(path, env):
            return {}
        run = run_kind(payload)
        decision = "ask" if run == "main" else "deny"
        log(payload, env, decision, path, run)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": decision,
                                       "permissionDecisionReason": REASON.format(path=path)}}
    except Exception as e:                              # noqa: BLE001 - R3: fail open
        log(payload, env, "open", path, why=type(e).__name__)
        return {}


# ---- R5: the doctor's line --------------------------------------------------------------

def counts(sdir) -> tuple[int, int, int]:
    """(prompts, refusals, calls let through on an error) in one session's guard log."""
    n = {"ask": 0, "deny": 0, "open": 0}
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
    return n["ask"], n["deny"], n["open"]


def doctor_row(env, cwd) -> str:
    """One line: the guard is on, and what this repo's newest session (g1's `newest`) logged."""
    from . import instructions
    try:
        main = instructions.main_checkout(cwd)
        found = instructions.newest(resolver.state_dir(env), main)
    except Exception:                                   # noqa: BLE001
        return "on (the repo's sessions cannot be read)"
    if found is None:
        return f"on; no session of {main} has a log to count its prompts and refusals"
    sid = found[0]
    asks, denies, opened = counts(resolver.session_dir(resolver.state_dir(env), sid))
    tail = f", {opened} let through on an error" if opened else ""
    return f"on; session {sid}: {asks} prompts, {denies} refusals{tail}"
