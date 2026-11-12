"""The instruction files a session loaded, and the doctor's lines on them (packet g1).

R1, the log: Claude Code's `InstructionsLoaded` hook fires once for each CLAUDE.md or
`.claude/rules/*.md` file it loads, at session start and for a lazy load. Its payload, beside
the common fields, carries `file_path`, `memory_type`, `load_reason`, `globs`,
`trigger_file_path` and `parent_file_path` (the hooks reference, as of 2026-11-11; Claude Code
2.1.322 builds the same six). The event cannot block and its output is discarded; the hook
appends one line per event to `sessions/<sid>/instructions.jsonl` and prints nothing.

R2 to R4, the doctor: what the newest session of this repo loaded, each file's bytes as it
stands now; then warnings that never fail the doctor, and the memory notes written since the
repo's previous session ended. Every function here reads only, and none raises past `rows`.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from . import ledger, resolver

LOG = "instructions.jsonl"
LOG_CAP = 256 * 1024             # past this a session's log takes no more lines
TEXT_CAP = 4096                  # a path or a token in a line, cut to this
FIELDS = ("file_path", "load_reason", "memory_type", "trigger_file_path", "parent_file_path",
          "cwd", "agent_id")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")

LEDGER_FILE = "DECISION" "S.md"  # spelled in two pieces for the hygiene scan
TREE_HEADING = "### Every session of the tree"     # a tree's section of an hq's ledger
FOLDER_FILES = ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"))
DESC_CAP = 1024                  # a plugin's description bytes, summed (design/09 §7.2)
INDEX_CAP = 8 * 1024             # a project's MEMORY.md
READ_CAP = 1024 * 1024           # a ledger or a frontmatter file read past this is not read
KNOBS = (("effort", "effortLevel"), ("model", "model"))


# ---- R1: the log -----------------------------------------------------------------------

def _text(v) -> str | None:
    return v[:TEXT_CAP] if isinstance(v, str) else None


def record(payload: dict, env) -> None:
    """One line for one event, in the session's own state directory. A payload without an
    id-shaped `session_id` or a non-empty string `file_path` writes nothing; a log at LOG_CAP
    takes no more. It never raises."""
    try:
        sid, path = payload.get("session_id"), payload.get("file_path")
        if not (isinstance(sid, str) and _SID.match(sid) and isinstance(path, str) and path):
            return
        line = {"at": time.time(), **{k: _text(payload.get(k)) for k in FIELDS}}
        globs = payload.get("globs")
        line["globs"] = ([_text(g) for g in globs[:64] if isinstance(g, str)]
                         if isinstance(globs, list) else None)
        sdir = resolver.session_dir(resolver.state_dir(env), sid)
        sdir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(sdir / LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if os.fstat(fd).st_size < LOG_CAP:
                os.write(fd, (json.dumps(line, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
    except Exception:                                   # noqa: BLE001 - a log never fails a hook
        pass


def read_log(sdir, limit: int = LOG_CAP + 64 * 1024) -> list[dict]:
    """The log's lines that parse as objects with a string `file_path`, in order, from its
    first `limit` bytes."""
    try:
        with open(Path(sdir) / LOG, "rb") as f:
            raw = f.read(limit)
    except OSError:
        return []
    out = []
    for text in raw.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(text)
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("file_path"), str):
            out.append(d)
    return out


# ---- where: the repo's main checkout, its project folder, its newest session ------------

def main_checkout(cwd) -> Path:
    """The main checkout of the repo that holds `cwd`, by its real path, read from `.git`
    without running git: a `.git` directory is the main checkout's; a `.git` file (a linked
    worktree's) names its gitdir, whose `commondir` leads to the main one's `.git`. No `.git`
    above `cwd`: `cwd` itself."""
    here = Path(os.path.realpath(str(cwd)))
    for d in (here, *here.parents):
        g = d / ".git"
        if g.is_dir():
            return d
        if g.is_file():
            try:
                first = g.read_text(errors="replace").splitlines()[0]
                gitdir = Path(first.split("gitdir:", 1)[1].strip())
                gitdir = gitdir if gitdir.is_absolute() else d / gitdir
                common = (gitdir / (gitdir / "commondir").read_text().strip())
                common = Path(os.path.realpath(str(common)))
                if common.name == ".git":
                    return common.parent
            except (OSError, IndexError, ValueError):
                pass
            return d
    return here


def _under(path, root: Path) -> bool:
    try:
        p = Path(os.path.realpath(str(path)))
    except (OSError, ValueError, TypeError):
        return False
    return p == root or root in p.parents


def project_dir(env, main: Path) -> Path:
    """Claude Code's project folder for the repo: the main checkout's path with every
    character outside [A-Za-z0-9] made `-`, under the user's `.claude/projects` (the memory
    page: one auto memory directory per repository, its worktrees included)."""
    moved = env.get("CLAUDE_CONFIG_DIR")
    base = Path(moved).expanduser() if moved else Path(env.get("HOME") or Path.home()) / ".claude"
    return base / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(main))


def newest(state: Path, main: Path) -> tuple[str, list[dict]] | None:
    """(session id, its log) of the session whose log's first line has a `cwd` at or under
    the main checkout and the latest `at`; None when no log is the repo's."""
    best = None
    try:
        dirs = list((Path(state) / "sessions").iterdir())
    except OSError:
        return None
    for d in dirs:
        if not (d / LOG).is_file():
            continue
        head = read_log(d, 16 * 1024)[:1]          # the first line decides; the winner is read whole
        if not head or not _under(head[0].get("cwd") or "", main):
            continue
        at = head[0].get("at")
        at = at if isinstance(at, (int, float)) and not isinstance(at, bool) else 0
        if best is None or at > best[0]:
            best = (at, d)
    return None if best is None else (best[1].name, read_log(best[1]))


# ---- R2: what loaded --------------------------------------------------------------------

def loaded(found) -> list[tuple[str, str, str]]:
    sid, log = found
    seen, out, total, gone = {}, [], 0, 0
    for r in log:
        seen.setdefault(r["file_path"], r.get("load_reason") or "unknown")
    for path, why in seen.items():
        try:
            size = os.stat(path).st_size if os.path.isfile(path) else None
        except OSError:
            size = None
        if size is None:
            gone += 1
            out.append(("instructions", f"gone {path} ({why})", "ok"))
        else:
            total += size
            out.append(("instructions", f"{size} B {path} ({why})", "ok"))
    tail = f", {gone} gone" if gone else ""
    out.append(("instructions", f"session {sid}: {len(seen)} files, {total} B as they stand "
                f"now{tail}", "ok"))
    return out


# ---- R3: the warnings -------------------------------------------------------------------

def _small(path: Path) -> str | None:
    try:
        if not path.is_file() or path.stat().st_size > READ_CAP:
            return None
        return path.read_text(errors="replace")
    except OSError:
        return None


def tree_file(main: Path, log: list[dict]) -> str | None:
    """A checkout in the folder that holds the main checkout keeps a ledger with the tree's
    section, and no CLAUDE.md of that folder is in the log (design/09 §3)."""
    folder = main.parent
    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return None
    holders = [e for e in entries if (e / ".git").exists()
               and TREE_HEADING in ((_small(e / LEDGER_FILE) or "").splitlines())]
    if not holders:
        return None
    logged = {os.path.realpath(r["file_path"]) for r in log}
    wanted = [folder / f for f in FOLDER_FILES]
    if any(os.path.realpath(str(w)) in logged for w in wanted):
        return None
    return (f"{wanted[0]} did not load in the session listed above, and the ledger of "
            f"{holders[0]} holds \"{TREE_HEADING}\": render the tree's file from that ledger")


def _frontmatter(text: str) -> dict:
    """`description` (a plain, quoted or folded value) and `disable-model-invocation`."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out, i = {}, 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if line[:1] in (" ", "\t") or not _:
            i += 1
            continue
        if key == "description":
            if value in ("", ">", "|", ">-", "|-", ">+", "|+"):
                more = []
                while i + 1 < len(lines) and lines[i + 1][:1] in (" ", "\t"):
                    i += 1
                    more.append(lines[i].strip())
                value = " ".join(more)
            elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out["description"] = value
        elif key == "disable-model-invocation":
            out["hidden"] = value.lower() == "true"
        i += 1
    return out


def description_bytes(root: Path) -> tuple[int, int]:
    """(bytes, count): the descriptions of a plugin's commands, skills and agents that are in
    context (a skill or command with `disable-model-invocation: true` is not)."""
    files = [*sorted(root.glob("commands/*.md")), *sorted(root.glob("skills/*/SKILL.md")),
             *sorted(root.glob("agents/*.md"))]
    total = count = 0
    for f in files:
        fm = _frontmatter(_small(f) or "")
        if "description" in fm and not fm.get("hidden"):
            total += len(fm["description"].encode())
            count += 1
    return total, count


def plugin_descs(plugins) -> list[str]:
    out = []
    for pid, p in sorted((plugins or {}).items()):
        if not isinstance(p, dict) or not p.get("enabled") or not p.get("installPath"):
            continue
        n, count = description_bytes(Path(str(p["installPath"])))
        if n > DESC_CAP:
            out.append(f"{pid} {p.get('version')}: {count} descriptions sum to {n} B, past "
                       f"{DESC_CAP} B, and each is in every session's context")
    return out


def memory_index(env, main: Path) -> str | None:
    p = project_dir(env, main) / "memory" / "MEMORY.md"
    try:
        size = p.stat().st_size
    except OSError:
        return None
    if size <= INDEX_CAP:
        return None
    return f"{p}: {size} B, past {INDEX_CAP} B (8 KiB); every session of the repo loads it"


def _user_settings(env) -> tuple[Path, dict]:
    from . import rules
    moved = env.get("CLAUDE_CONFIG_DIR")
    base = Path(moved).expanduser() if moved else Path(env.get("HOME") or Path.home()) / ".claude"
    docs = [doc for scope, doc in rules._settings(env, None) if scope == "user"]
    return base / "settings.json", (docs[0] if docs else {})


def two_places(env, sections) -> list[str]:
    """A knob set in two places: the repo's profile sets `effort` or `model`, and the user's
    settings set it too (design/09 §7.3). Each place is named with its value."""
    name = ((sections or {}).get("session") or {}).get("profile")
    if not isinstance(name, str):
        return []
    try:
        defaults, profiles = resolver.load_profiles(env)
    except Exception:                                   # noqa: BLE001 - the config row says why
        return []
    body = profiles.get(name) or {}
    path, doc = _user_settings(env)
    out = []
    for knob, key in KNOBS:
        where = f"profile {name}" if knob in body else f"the profiles' defaults (profile {name})"
        mine = body.get(knob, defaults.get(knob))
        if mine is None:
            continue
        theirs = [f"{key} {doc[key]}"] if isinstance(doc.get(key), str) else []
        ms = doc.get("modelSettings") if isinstance(doc.get("modelSettings"), dict) else {}
        per = sorted((m, s["effortLevel"]) for m, s in ms.items()
                     if knob == "effort" and isinstance(s, dict)
                     and isinstance(s.get("effortLevel"), str))
        if len(per) == 1:
            theirs.append(f"modelSettings.{per[0][0]}.effortLevel {per[0][1]}")
        elif per:
            values = ", ".join(sorted({v for _, v in per}))
            theirs.append(f"modelSettings.<model>.effortLevel for {len(per)} models ({values})")
        if theirs:
            out.append(f"{knob} is set in two places: {where} says {mine}; {path} says "
                       + "; ".join(theirs))
    return out


# ---- R4: memory notes since the previous session -----------------------------------------

def _epoch(at) -> float | None:
    try:
        return datetime.fromisoformat(str(at)).timestamp()
    except (TypeError, ValueError):
        return None


def _first_line(path: Path) -> str:
    lines = (_small(path) or "").splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
        lines = lines[end + 1:] if end is not None else []
    return next((l.strip() for l in lines if l.strip()), "")[:160]


def memory_notes(env, state: Path, main: Path, skip) -> list[str]:
    """The project's memory notes (MEMORY.md, the index, aside) written after the newest
    ledger row of this repo whose session is not in `skip`: by name and first line, oldest
    first. No such row: none."""
    ends = [_epoch(r.get("ended")) for r in ledger.lines(state)
            if r.get("session") not in skip and isinstance(r.get("repo"), str)
            and _under(r["repo"], main)]
    ends = [e for e in ends if e is not None]
    if not ends:
        return []
    since = max(ends)
    mem = project_dir(env, main) / "memory"
    try:
        notes = [(p.stat().st_mtime, p) for p in mem.glob("*.md")
                 if p.name != "MEMORY.md" and p.is_file()]
    except OSError:
        return []
    return [f"{p.name}: {_first_line(p)}" for t, p in sorted(notes) if t > since]


# ---- the doctor's rows ------------------------------------------------------------------

def rows(env, cwd, plugins, sections) -> list[tuple[str, str, str]]:
    """(name, detail, kind) for the doctor, kind `ok`, `warn` or `note`; none is a failure.
    A part that cannot be read is left out, and nothing raises."""
    out = []
    try:
        main = main_checkout(cwd)
        state = resolver.state_dir(env)
    except Exception:                                   # noqa: BLE001
        return [("instructions", f"{cwd}: the repo cannot be read", "ok")]
    found = None
    try:
        found = newest(state, main)
    except Exception:                                   # noqa: BLE001
        pass
    if found is None:
        out.append(("instructions", f"no session of {main} has a log of the instruction files "
                    "it loaded", "ok"))
    else:
        out += loaded(found)
    parts = [
        ("tree-file", lambda: [tree_file(main, found[1])] if found else []),
        ("plugin-descs", lambda: plugin_descs(plugins)),
        ("memory-index", lambda: [memory_index(env, main)]),
        ("two-places", lambda: two_places(env, sections)),
    ]
    for name, part in parts:
        try:
            out += [(name, d, "warn") for d in part() if d]
        except Exception:                               # noqa: BLE001
            pass
    try:
        skip = {env.get("CLAUDE_CODE_SESSION_ID"), found[0] if found else None} - {None}
        out += [("memory-notes", d, "note") for d in memory_notes(env, state, main, skip)]
    except Exception:                                   # noqa: BLE001
        pass
    return out
