"""The successor's state file (packet S39): the sitting writes it, the tool checks it.

A RESPAWN close may hand its successor one compact file: who is still out (helpers,
gates), what just landed, and what to read first. No hook sees a helper return or a
gate finish, so the tool writes none of the content; it checks the shape, copies the
bytes to the chain home as `state.md` and records them in `state.json`. SessionStart
names the copy to a successor in the same chain (`hooks._state_reminder`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from . import store

SECTIONS = ("## Helpers", "## Gates", "## Last acts", "## Read first")
CEILING = 8192                  # bytes; a state at or over it is refused, never cut
FILE = "state.md"
RECORD = "state.json"
NONE = "- none"
LAST = "- read nothing else before the first act"
MAX_ACTS = 3
DAY = 86400.0
TITLE = re.compile(r"^# State for the successor of [A-Za-z0-9_-]{1,128}, "
                   r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}\Z")
_ACT = re.compile(r"^- [0-9a-f]{7,40}\b\W*\S")
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
        if "—" in line:
            faults.append(f"an em-dash (U+2014) at line {n}: write a colon, a comma or a "
                          "semicolon")
            break
    if not lines or not TITLE.match(lines[0]):
        faults.append(f"the first line is not {_SHAPE}")
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
    if name == "## Read first" and (lines[-1] != LAST or lines.count(LAST) != 1):
        out.append(f"{name} must end on '{LAST}', once")
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
    """Copy `src`'s bytes to `<home>/state.md`, then describe them in `<home>/state.json`;
    return that record. The caller has checked the text."""
    home, raw = Path(home), Path(src).read_bytes()
    record = {"from_session": sid, "written": now,
              "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    _write_bytes(home / FILE, raw)
    store._write_private(home / RECORD, json.dumps(record) + "\n")
    return record


def fresh(home: Path, sid, now) -> dict | None:
    """The record in `home` when it is another session's, written within 24 h, and its
    copy still holds the recorded size; None otherwise, and on any unreadable part."""
    try:
        d = json.loads((Path(home) / RECORD).read_text(encoding="utf-8"))
        size = (Path(home) / FILE).stat().st_size
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    who, at, n = d.get("from_session"), d.get("written"), d.get("bytes")
    if not (isinstance(who, str) and _SID.match(who) and who != sid):
        return None
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not 0 <= now - at <= DAY:
        return None
    if isinstance(n, bool) or not isinstance(n, int) or n != size:
        return None
    return d


def clear(home: Path) -> None:
    """Remove a copy and its record (record first), so no later successor reads it."""
    for name in (RECORD, FILE):
        try:
            (Path(home) / name).unlink()
        except FileNotFoundError:
            pass
