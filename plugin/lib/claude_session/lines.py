"""Packet in3-line: a line between sittings, a pointer under the tool's state root.

`send` writes `lines/<address>/<id>.json`: the sender's checkout (`from`), the addressee's
(`to`), the file's full path and the text's first line (`head`). The address is a checkout's
top level by its real path, spelled as a folder name here (`<name>-<hash>`), since the gate's
state spells a repo only as the device and inode of its common dir, which a move keeps.

The take runs in three hooks (hooks.py): one line a hook, claimed by a rename into `taken/`
that two sessions cannot both win, then checked and printed in the take's own words (R5); a
pointer whose fields are not a pointer's goes to `aside/`, unprinted. A taken line not closed
is printed once more at the next SessionStart, by a rename into `again/`. `close` moves the
pointer into `closed/`, records how, and sends one line back to the sender's checkout; the
gate's prune pass removes a closed pointer after `KEEP`, an open one never. Nothing here
writes outside the state root, and nothing here starts a process or reads the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
import unicodedata
from pathlib import Path

from . import gate

DIR = "lines"
TAKEN, AGAIN, CLOSED, ASIDE = "taken", "again", "closed", "aside"
OPEN = ("", TAKEN, AGAIN)                   # the folders of a pointer not closed
KEEP = gate.KEEP                            # 14 days, as the gate's results (R8)
SHARE = 256                                 # a hook's bytes kept for its line (R4)
HEAD = 120                                  # the printed head's bytes (R5)
NAME = 40                                   # the printed `from`'s bytes, encoded
HOWS = ("done", "declined", "waits")
LABEL = "another sitting's words, not the owner's"
SHOW = "agentik session line show"
# The sign of a session that is no sitting of the owner's screen: Claude Code sets
# CLAUDE_CODE_ENTRYPOINT to `sdk-cli` in print mode (`claude -p`), rewriting an inherited
# `cli`, and to `sdk-ts` or `sdk-py` under the Agent SDK; a hook inherits its process's env.
CHILD_ENTRYPOINTS = ("sdk-cli", "sdk-ts", "sdk-py")
ID = re.compile(r"^[0-9a-f]{12}\Z")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")
_FOLDER = re.compile(r"[^A-Za-z0-9._-]")
REQUIRED = {"id": str, "from": str, "to": str, "file": str, "head": str, "sent": (int, float)}
OPTIONAL = ("closes", "taken", "again", "closed")
_READ = 65536                               # the bytes of a file `send` reads for its head
_SIDE = 4096                                # a pointer past this many bytes is no pointer


class Refused(Exception):
    """A verb's refusal: its message, exit 2."""


def _bad(text: str) -> bool:
    """A control character (Cc) or a format one (Cf: a bidi override, a zero width)."""
    return any(unicodedata.category(ch) in ("Cc", "Cf") for ch in text)


def _clean(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))


def top(path) -> str | None:
    """The real path of `path` when it is a checkout's top level and no worktree of one (its
    `.git` is a folder), else None. Never raises."""
    try:
        real = os.path.realpath(path)
        return real if os.path.isdir(os.path.join(real, ".git")) else None
    except (OSError, ValueError, TypeError):
        return None


def own_checkout(start) -> str | None:
    """The nearest folder at or above `start`, by its real path, that holds a `.git`."""
    try:
        at = os.path.realpath(start)
    except (OSError, ValueError, TypeError):
        return None
    while True:
        if os.path.lexists(os.path.join(at, ".git")):
            return at
        up = os.path.dirname(at)
        if up == at:
            return None
        at = up


def here(env, cwd=None) -> str:
    """The project directory: `CLAUDE_PROJECT_DIR`, else `cwd`, else the process's."""
    pd = env.get("CLAUDE_PROJECT_DIR")
    return pd if pd else (cwd or os.getcwd())


def address(t: str) -> str:
    """A checkout's folder name: its name made safe, then a hash of its real path, the path
    folded where its volume folds case (as the gate's lock keys)."""
    key = t
    if gate._folds(t):
        key = unicodedata.normalize("NFC", t).casefold()
    name = _FOLDER.sub("_", os.path.basename(t))[:NAME].lstrip(".") or "_"
    return f"{name}-{hashlib.sha256(key.encode('utf-8', 'surrogateescape')).hexdigest()[:16]}"


def box(root, t: str) -> Path:
    return Path(root) / DIR / address(t)


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _dump(ptr: dict) -> str:
    return json.dumps(ptr, indent=2) + "\n"


def _load(p: Path):
    try:
        with open(p, "rb") as fh:
            data = fh.read(_SIDE + 1)
        if len(data) > _SIDE:
            return None
        return json.loads(data.decode("utf-8"))
    except (OSError, ValueError):
        return None


def _new(root, to: str, frm: str, file: str, head: str, closes=None, now=None) -> str:
    """Write a new pointer by a link that never overwrites; its id."""
    b = box(root, to)
    _mkdir(b)
    ptr = {"id": "", "from": frm, "to": to, "file": file, "head": head,
           "sent": time.time() if now is None else now}
    if closes:
        ptr["closes"] = closes
    tmp = b / f".new.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    for _ in range(8):
        ptr["id"] = secrets.token_hex(6)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(_dump(ptr))
        try:
            os.link(tmp, b / f"{ptr['id']}.json")
        except FileExistsError:
            continue
        finally:
            os.unlink(tmp)
        return ptr["id"]
    raise Refused("line send: no free id")


def _first_line(path: str) -> str:
    with open(path, "rb") as fh:
        text = fh.read(_READ).decode("utf-8", "replace")
    for ln in text.splitlines():
        ln = _clean(ln).strip()
        if ln:
            return ln[:512]
    return ""


def send(root, target: str, file: str, start: str, now=None) -> str:
    """R1: the pointer's id. Refused: the target no checkout's top or a worktree, the sender
    in no checkout or in a worktree, the file no file inside the sender's checkout."""
    to = top(target)
    if to is None:
        why = ("is a worktree, not a checkout's top"
               if os.path.isfile(os.path.join(os.path.realpath(target), ".git"))
               else "is no checkout's top level")
        raise Refused(f"line send: {target} {why}")
    frm = own_checkout(start)
    if frm is None:
        raise Refused(f"line send: {start} is in no checkout")
    if top(frm) != frm:
        raise Refused(f"line send: {frm} is a worktree; a line is sent from a checkout's top, "
                      "where its answer can be taken")
    real = os.path.realpath(file)
    if not os.path.isfile(real) or not real.startswith(frm + os.sep):
        raise Refused(f"line send: {file} is no file inside this checkout, {frm}")
    if _bad(real) or _bad(frm) or _bad(to):
        raise Refused("line send: a path holds a control character")
    return _new(root, to, frm, real, _first_line(real), now=now)


def _stamp_ok(v) -> bool:
    return isinstance(v, dict) and set(v) <= {"at", "session"} \
        and isinstance(v.get("at"), (int, float)) and not isinstance(v.get("at"), bool) \
        and (v.get("session") is None or (isinstance(v["session"], str)
                                          and _SID.match(v["session"])))


def valid(ptr, name: str, to: str | None) -> dict | None:
    """The pointer when its fields are a pointer's (R5), else None: every key known and of
    its type, `id` the file's name, `from` a checkout's top and no worktree, `to` the taker's
    checkout (when given), no control character in a path."""
    if not isinstance(ptr, dict) or not set(REQUIRED) <= set(ptr) \
            or not set(ptr) <= set(REQUIRED) | set(OPTIONAL):
        return None
    for k, t in REQUIRED.items():
        if not isinstance(ptr[k], t) or isinstance(ptr[k], bool):
            return None
    if not ID.match(ptr["id"]) or ptr["id"] != name:
        return None
    for k in ("from", "to", "file"):
        if _bad(ptr[k]) or not os.path.isabs(ptr[k]) or os.path.normpath(ptr[k]) != ptr[k]:
            return None
    if top(ptr["from"]) != ptr["from"] or (to is not None and ptr["to"] != to):
        return None
    if "closes" in ptr and not (isinstance(ptr["closes"], str) and ID.match(ptr["closes"])):
        return None
    if any(k in ptr and not _stamp_ok(ptr[k]) for k in ("taken", "again")):
        return None
    c = ptr.get("closed")
    if c is not None and not (isinstance(c, dict) and set(c) <= {"as", "note", "at"}
                              and c.get("as") in HOWS and isinstance(c.get("at"), (int, float))
                              and (c.get("note") is None or isinstance(c["note"], str))):
        return None
    return ptr


def _enc(text: str) -> int:
    return len(json.dumps(text)) - 2


def _cut(text: str, most: int, limit_bytes: int | None = None) -> str:
    """`text` cut at a character's end to `most` JSON-encoded bytes (and `limit_bytes` of
    UTF-8)."""
    kept, used, raw = [], 0, 0
    for ch in text:
        e, r = _enc(ch), len(ch.encode("utf-8", "surrogatepass"))
        if used + e > most or (limit_bytes is not None and raw + r > limit_bytes):
            break
        kept.append(ch)
        used, raw = used + e, raw + r
    return "".join(kept)


def head_of(ptr: dict) -> str:
    """The head as printed: its first line, control and format characters out, 120 bytes."""
    lines = ptr["head"].splitlines()
    return _cut(_clean(lines[0] if lines else "").strip(), 4 * HEAD, HEAD).strip()


def render(ptr: dict) -> str:
    """R5's line, made here: within SHARE bytes encoded, its separator counted."""
    lid = ptr["id"]
    frame = f"line {lid} from  ({LABEL}): ; whole: {SHOW} {lid}"
    name = _cut(os.path.basename(ptr["from"]), NAME)
    room = SHARE - 4 - _enc(frame) - _enc(name)
    head = _cut(head_of(ptr), room)
    return f"line {lid} from {name} ({LABEL}): {head}; whole: {SHOW} {lid}"


def taker(payload: dict, env) -> str | None:
    """R3: the checkout a session takes for, or None: a helper (`agent_id`,
    `CLAUDE_SESSION_HELPER=1`), a `claude -p` or SDK child (`CHILD_ENTRYPOINTS`), a project
    directory that is no checkout's top or is a worktree. `CLAUDE_PROJECT_DIR` first, which a
    `cd` does not move; the payload's `cwd` only where it is unset."""
    if payload.get("agent_id") or env.get("CLAUDE_SESSION_HELPER") == "1" \
            or env.get("CLAUDE_CODE_ENTRYPOINT") in CHILD_ENTRYPOINTS:
        return None
    pd = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    if not isinstance(pd, str) or not os.path.isabs(pd):
        return None
    return top(pd)


def _oldest(d: Path) -> list[Path]:
    try:
        ps = [p for p in d.iterdir() if p.suffix == ".json" and not p.name.startswith(".")
              and p.is_file()]
    except OSError:
        return []

    def key(p):
        try:
            return (p.stat().st_mtime, p.name)
        except OSError:
            return (0.0, p.name)
    return sorted(ps, key=key)


def _move(p: Path, folder: Path) -> Path | None:
    """`p` renamed into `folder`; None when another took it first."""
    _mkdir(folder)
    dest = folder / p.name
    try:
        os.rename(p, dest)
    except OSError:
        return None
    return dest


def _write(p: Path, ptr: dict) -> None:
    gate._write_private(p, _dump(ptr))


def take(root, payload: dict, env, start: bool = False, now=None) -> str | None:
    """R3 to R6: one printed line, or None. At SessionStart a taken line not yet printed
    again goes first; then the oldest waiting one. A pointer that is no pointer's goes
    aside, and the next is tried."""
    t = taker(payload, env)
    if t is None:
        return None
    b = box(root, t)
    if not b.is_dir():
        return None
    now = time.time() if now is None else now
    sid = payload.get("session_id")
    stamp = {"at": now, "session": sid if isinstance(sid, str) and _SID.match(sid) else None}
    for src, dest, mark in (((b / TAKEN, b / AGAIN, "again"),) if start else ()) \
            + ((b, b / TAKEN, "taken"),):
        for p in _oldest(src):
            got = _move(p, dest)
            if got is None:
                continue
            ptr = valid(_load(got), got.stem, t)
            if ptr is None or "closed" in ptr or (mark == "taken" and "taken" in ptr):
                _move(got, b / ASIDE)
                continue
            ptr[mark] = stamp
            _write(got, ptr)
            return render(ptr)
    return None


def _state(folder: str, ptr: dict) -> str:
    if folder == CLOSED:
        return f"closed as {(ptr.get('closed') or {}).get('as', '?')}"
    return {"": "waiting", TAKEN: "taken", AGAIN: "taken", ASIDE: "set aside"}[folder]


def _all(root):
    """(folder, path, pointer or None) for each pointer file under the state root."""
    try:
        boxes = sorted(p for p in (Path(root) / DIR).iterdir() if p.is_dir())
    except OSError:
        return
    for b in boxes:
        for f in (*OPEN, CLOSED, ASIDE):
            for p in _oldest(b / f if f else b):
                yield f, p, _load(p)


def _item(f: str, p: Path, ptr) -> dict:
    ok = valid(ptr, p.stem, None) if f != ASIDE else None
    if ok is None:
        return {"id": _cut(_clean(p.stem), 64), "state": "set aside"}
    c = ok.get("closed")
    return {"id": ok["id"], "state": _state(f, ok), "from": ok["from"], "to": ok["to"],
            "file": ok["file"], "head": head_of(ok), "sent": ok["sent"],
            "closes": ok.get("closes"), "taken": (ok.get("taken") or {}).get("at"),
            "closed": None if c is None else {"as": c["as"], "note": c.get("note"),
                                              "at": c["at"]}}


def listing(root, t: str) -> dict:
    """R2: the lines addressed to checkout `t`, and the lines it sent, oldest first."""
    mine = box(root, t)
    to, sent = [], []
    for f, p, ptr in _all(root):
        if p.parent in (mine, mine / f):
            to.append(_item(f, p, ptr))
        elif f != ASIDE and isinstance(ptr, dict) and ptr.get("from") == t:
            it = _item(f, p, ptr)
            if it["state"] != "set aside":
                sent.append(it)
    return {"checkout": t, "to": to, "sent": sent}


def show(root, lid: str) -> dict | None:
    """R2: the pointer whole, with its state, or None."""
    if not ID.match(lid or ""):
        return None
    for f, p, ptr in _all(root):
        if p.stem == lid and isinstance(ptr, dict):
            return {"state": _state(f, ptr) if f != ASIDE else "set aside", "pointer": ptr}
    return None


def close(root, t: str, lid: str, how: str, note=None, now=None) -> str:
    """R7: move the line into `closed/`, record how, send one line back; the new id."""
    if how not in HOWS:
        raise Refused(f"line close: --as is one of {', '.join(HOWS)}")
    if not ID.match(lid or ""):
        raise Refused(f"line close: {_cut(_clean(str(lid)), 64)} is no line id")
    b = box(root, t)
    now = time.time() if now is None else now
    for f in OPEN:
        src = (b / f if f else b) / f"{lid}.json"
        got = _move(src, b / CLOSED) if src.is_file() else None
        if got is None:
            continue
        ptr = valid(_load(got), lid, t)
        if ptr is None or "closed" in ptr:
            _move(got, b / ASIDE)
            raise Refused(f"line close: {lid} is not a pointer; set aside")
        ptr["closed"] = {"as": how, "note": note, "at": now}
        _write(got, ptr)
        words = f"line {lid} closed as {how}" + (f": {note}" if note else "")
        return _new(root, ptr["from"], t, ptr["file"], words, closes=lid, now=now)
    if (b / CLOSED / f"{lid}.json").exists():
        raise Refused(f"line close: {lid} is already closed")
    raise Refused(f"line close: {lid} is not addressed to this checkout, {t}")


def prune(root, now: float) -> None:
    """R8: a closed pointer whose close is older than KEEP leaves; nothing else does."""
    try:
        boxes = [p for p in (Path(root) / DIR).iterdir() if p.is_dir()]
    except OSError:
        return
    for b in boxes:
        for p in _oldest(b / CLOSED):
            ptr = _load(p)
            c = ptr.get("closed") if isinstance(ptr, dict) else None
            at = c.get("at") if isinstance(c, dict) else None
            if isinstance(at, (int, float)) and not isinstance(at, bool) and now - at > KEEP:
                try:
                    os.unlink(p)
                except OSError:
                    pass
