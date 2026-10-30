"""The successor's state file (packet S39): the sitting writes it, the tool checks it.

A RESPAWN close may hand its successor one compact file: who is still out (helpers,
gates), what just landed, and what to read first. No hook sees a helper return or a
gate finish, so the tool writes none of the content; it checks the shape, copies the
bytes to the chain home as `state.md` and records them in `state.json`. At the next
start the launcher stamps the record with the successor's id (`hand`), and SessionStart
names the copy to that session alone (`hooks._state_reminder`; Amendment 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from . import store

SECTIONS = ("## Helpers", "## Gates", "## Last acts", "## Read first")
CEILING = 8192                  # bytes; a state at or over it is refused, never cut
FILE = "state.md"
RECORD = "state.json"
NONE = "- none"
LAST = "- read nothing else before the first act"
MAX_ACTS = 3
TITLE = re.compile(r"^# State for the successor of [A-Za-z0-9_-]{1,128}, "
                   r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\Z")
_ACT = re.compile(r"^- [0-9a-f]{7,40}\b\W*\S")
_PATH = re.compile(r"^- \S*[/.]\S*")          # a path line: its first word holds / or .
_HEX = re.compile(r"^[0-9a-f]{64}\Z")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")
_SHAPE = "'# State for the successor of <sid-short>, <YYYY-MM-DD> <HH:MM>'"


def check(text: str) -> list[str]:
    """The shape faults of a state file's text, one line each; empty is good."""
    faults = []
    size = len(text.encode("utf-8", "surrogatepass"))
    if size >= CEILING:
        faults.append(f"{size} bytes, at or over the {CEILING}-byte ceiling: move text out")
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if "\u2014" in line:
            faults.append(f"an em-dash (U+2014) at line {n}: write a colon, a comma or a "
                          "semicolon")
            break
    title = TITLE.match(lines[0]) if lines else None
    if title is None:
        faults.append(f"the first line is not {_SHAPE}")
    else:
        try:
            datetime.strptime(title.group(1), "%Y-%m-%d %H:%M")
        except ValueError:
            faults.append(f"the first line's date and time do not parse: {title.group(1)}")
    found: list[str] = []
    body: dict[int, list[tuple[int, str]]] = {}
    for n, line in enumerate(lines[1:], 2):
        if line.startswith("#"):
            found.append(line.rstrip())
            body[len(found) - 1] = []
        elif not line.strip():
            continue
        elif not found:
            faults.append(f"text before the first section (line {n}): only blank lines go "
                          "there")
        else:
            body[len(found) - 1].append((n, line.rstrip()))
    if tuple(found) != SECTIONS:
        faults.append("the sections must be exactly " + ", ".join(SECTIONS)
                      + ", in this order; found: " + (", ".join(found)[:120] or "none"))
        return faults
    for i, name in enumerate(SECTIONS):
        faults += _section(name, body[i])
    return faults


def _section(name: str, rows: list[tuple[int, str]]) -> list[str]:
    if not rows:
        return [f"{name} is empty: write '{NONE}'"]
    out = [f"{name}, line {n}: not a bulleted line ('- ...')"
           for n, l in rows if not l.startswith("- ")]
    lines = [l for _, l in rows]
    if NONE in lines and len(lines) > 1:
        out.append(f"{name} holds '{NONE}' and other lines: '{NONE}' stands alone")
    if name == "## Last acts" and lines != [NONE]:
        if len(lines) > MAX_ACTS:
            out.append(f"{name} holds {len(lines)} lines, at most {MAX_ACTS}")
        out += [f"{name}, line {n}: open on a commit sha ('- <sha> what it did')"
                for n, l in rows if l.startswith("- ") and not _ACT.match(l)]
    if name == "## Read first":
        if lines[-1] != LAST or lines.count(LAST) != 1:
            out.append(f"{name} must end on '{LAST}', once")
        if not any(_PATH.match(l) for l in lines if l != LAST):
            out.append(f"{name} holds no path line ('- <path> lines <a>-<b>') before its "
                       "closing line")
    return out


def _write_bytes(path: Path, raw: bytes) -> None:
    """Atomic, 0600, same-directory temp: store._write_private for bytes."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write(home: Path, src: Path, sid: str, now) -> dict:
    """Read `src` once, check those bytes (a fault raises ValueError and writes nothing),
    copy the same bytes to `<home>/state.md`, then describe them in `<home>/state.json`;
    return that record."""
    home, raw = Path(home), Path(src).read_bytes()
    try:
        faults = check(raw.decode("utf-8"))
    except UnicodeDecodeError:
        faults = ["not UTF-8 text"]
    if faults:
        raise ValueError("; ".join(faults))
    record = {"from_session": sid, "written": now,
              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    _write_bytes(home / FILE, raw)
    store._write_private(home / RECORD, json.dumps(record) + "\n")
    return record


def _good(d) -> bool:
    """A record's shape: its four keys typed, and `to_session` a session id when set."""
    if not isinstance(d, dict):
        return False
    who, at, sha, n = (d.get(k) for k in ("from_session", "written", "sha256", "bytes"))
    to = d.get("to_session")
    return (isinstance(who, str) and bool(_SID.match(who))
            and not isinstance(at, bool) and isinstance(at, (int, float))
            and isinstance(sha, str) and bool(_HEX.match(sha))
            and not isinstance(n, bool) and isinstance(n, int)
            and (to is None or (isinstance(to, str) and bool(_SID.match(to)))))


def hand(home: Path, prev, sid: str) -> bool:
    """Amendment 1, at a start: when the record in `home` is the one `prev` (the session
    that just ended) wrote, stamp it `to_session: sid`; delete any other state, an earlier
    chain's or sitting's. True when stamped."""
    home = Path(home)
    try:
        d = json.loads((home / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if prev and isinstance(d, dict) and d.get("from_session") == prev:
        d["to_session"] = sid
        store._write_private(home / RECORD, json.dumps(d) + "\n")
        return True
    clear(home)
    return False


def handed(home: Path, sid) -> tuple[str, dict | None]:
    """("ok", record) when `home` holds a state handed to `sid` whose copy matches its
    record; ("mismatch", None) for a bad record, or a missing or altered copy of one
    handed to `sid`; ("", None) when nothing is handed to `sid`."""
    home = Path(home)
    try:
        text = (home / RECORD).read_text(encoding="utf-8")
    except FileNotFoundError:
        return "", None
    except OSError:
        return "mismatch", None
    try:
        d = json.loads(text)
    except ValueError:
        return "mismatch", None
    if not _good(d):
        return "mismatch", None
    if not sid or d.get("to_session") != sid:
        return "", None
    try:
        raw = (home / FILE).read_bytes()
    except OSError:
        return "mismatch", None
    if len(raw) != d["bytes"] or hashlib.sha256(raw).hexdigest() != d["sha256"]:
        return "mismatch", None
    return "ok", d


def main_sitting(env) -> bool:
    """A main-thread sitting: not a helper (CLAUDE_SESSION_HELPER=1), and neither a
    started nor a relay sitting (CLAUDE_SESSION_DEPTH 1 or more, or unparsable, or
    RELAY_ROW set), as chain.py reads a chain sitting (respawn-r1 §3.8)."""
    if env.get("CLAUDE_SESSION_HELPER") == "1" or env.get("RELAY_ROW"):
        return False
    raw = env.get("CLAUDE_SESSION_DEPTH")
    if raw is None or raw == "":
        return True
    try:
        return int(raw) < 1
    except ValueError:
        return False


def clear(home: Path) -> None:
    """Remove a copy and its record (record first), so no later successor reads it."""
    for name in (RECORD, FILE):
        try:
            (Path(home) / name).unlink()
        except FileNotFoundError:
            pass
