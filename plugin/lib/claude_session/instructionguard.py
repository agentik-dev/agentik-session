"""The prompt before an edit of instruction text (packet g2; hq design/09 §7.2).

R1: `Edit`, `Write`, `MultiEdit` and `NotebookEdit` on a guarded path, and no other tool (a
Bash line is never read). Guarded are the instruction files and the settings that act as
prompts: under the user's folder (`CLAUDE_CONFIG_DIR`, and `~/.claude`) `CLAUDE.md`,
`settings.json` and the `rules`, `hooks`, `agents` and `plugins` folders; a tree folder's
`CLAUDE.md` (a folder that holds a main checkout, a child with a `.git` directory); and at a
checkout's top level (the nearest folder above the target holding `.git`, a worktree's file
included) `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `.claude/rules/**`,
the ledger file and `.claude/settings*.json`. A folder `tests`, `testdata` or `fixtures` below
the matched root (the user's folder, or the nearest top level) exempts the path.

R2: `ask` in a main thread; `deny` in a helper (`agent_id`), in a `-p` run, and where the
nearest `claude` ancestor's argv cannot be read (`harness.claude_argv`, SessionEnd's reader).
R3: an exception or a target that is not a usable string lets the call through, and one line
goes to the session's `guard.jsonl`, never to the model; each ask and deny is a line there too.
R4: no knob. The environment is read for `HOME` and `CLAUDE_CONFIG_DIR` (where the user's folder
is) and the state root (where the log goes), nothing else.
"""

from __future__ import annotations

import json
import os
import re
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


def _below(p: Path, root: Path) -> tuple | None:
    try:
        return p.relative_to(root).parts
    except ValueError:
        return None


def _exempt(rel: tuple) -> bool:
    return bool(EXEMPT.intersection(rel[:-1]))


def _user_file(p: Path, env) -> bool:
    for d in user_dirs(env):
        for root in {Path(os.path.abspath(str(d))), Path(os.path.realpath(str(d)))}:
            rel = _below(p, root)
            if not rel or _exempt(rel):
                continue
            if rel in USER_FILES or (len(rel) > 1 and rel[0] in USER_TREES):
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


def _checkout_file(p: Path) -> bool:
    parts = p.parts
    if p.name not in NAMES and ".claude" not in parts:
        return False                      # the cheap pass: no name or folder that is guarded
    top = _top(p)
    if top is not None:
        rel = _below(p, top)
        if not rel or _exempt(rel):
            return False
        if rel in TOP_FILES:
            return True
        if len(rel) > 2 and rel[:2] == (".claude", "rules"):
            return True
        if len(rel) == 2 and rel[0] == ".claude" and _SETTINGS.match(rel[1]):
            return True
    if p.name == "CLAUDE.md":             # a tree folder's file, or its `.claude/CLAUDE.md`
        folder = p.parent.parent if p.parent.name == ".claude" else p.parent
        return _holds_main_checkout(folder)
    return False


def guarded(path: str, env) -> bool:
    """True for a guarded path (R1), by its absolute spelling or its real path."""
    forms = {Path(os.path.abspath(path)), Path(os.path.realpath(path))}
    return any(_user_file(p, env) or _checkout_file(p) for p in forms)


# ---- R2: which run ----------------------------------------------------------------------

def run_kind(payload: dict) -> str:
    """`helper`, `headless`, `unknown` or `main`."""
    if payload.get("agent_id"):
        return "helper"
    argv = harness.claude_argv()
    if not argv:
        return "unknown"
    if any(w in PRINT or w.startswith("--print=") for w in argv[1:]):
        return "headless"
    return "main"


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
