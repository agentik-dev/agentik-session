"""Packet in3-line: a line between sittings, a pointer under the tool's state root.

`send` writes `lines/<address>/<id>.json`: the sender's checkout (`from`), the addressee's
(`to`), the file's full path and the text's first line (`head`). The address is a checkout's
top level by its real path, spelled as a folder name here (`<name>-<hash>`), since the gate's
state spells a repo only as the device and inode of its common dir, which a move keeps. On a
volume that folds case the path is folded first, and `to` and `from` are compared that way.

A pointer is never rewritten after it is written (fix 1, C4): each state change is one rename,
and a step reads the pointer before its rename. The take moves a waiting pointer into
`taken/`, a SessionStart a taken one into `again/` (printed once more), a close an open one
into `closing/`, then publishes the closed pointer, its record written before, by a rename
into `closed/`. Two sessions cannot both win a rename. A pointer whose fields are not a
pointer's goes to `aside/`, unprinted, at most ASIDE_MOST a hook. The gate's prune pass removes
a closed pointer after `KEEP`, an open one never. Nothing here writes outside the state root
or reads the network. Packet rr5c R2: a file that is not under its checkout is asked of the
resolver (`records.answer`, its bounded child, once a checkout a process): in `out` a file under
the checkout's records folder passes; no other process is started.
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

from . import gate, records

DIR = "lines"
TAKEN, AGAIN, CLOSING, CLOSED, ASIDE = "taken", "again", "closing", "closed", "aside"
OPEN = ("", TAKEN, AGAIN)                   # the folders of a pointer not closed, in its order
KEEP = gate.KEEP                            # 14 days, as the gate's results (R8)
SHARE = 256                                 # a hook's bytes kept for its line (R4)
HEAD = 120                                  # the printed head's UTF-8 bytes (R5)
STORED = 512                                # the stored head's UTF-8 bytes (C1)
NOTE = 240                                  # a close's note, UTF-8 bytes (C1)
NAME = 40                                   # the printed `from`'s bytes, encoded
ASIDE_MOST = 16                             # pointers one hook sets aside (C6)
HOWS = ("done", "declined", "waits")
LABEL = "another sitting's words, not the owner's"
SHOW = "agentik session line show"
# The sign of a session that is no sitting of the owner's screen: Claude Code sets
# CLAUDE_CODE_ENTRYPOINT to `sdk-cli` in print mode (`claude -p`), rewriting an inherited
# `cli`, and to `sdk-ts` or `sdk-py` under the Agent SDK; a hook inherits its process's env.
# A print-mode child of a session whose entrypoint is not `cli` keeps that value (F8).
CHILD_ENTRYPOINTS = ("sdk-cli", "sdk-ts", "sdk-py")
ID = re.compile(r"^[0-9a-f]{12}\Z")
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")
_FOLDER = re.compile(r"[^A-Za-z0-9._-]")
REQUIRED = {"id": str, "from": str, "to": str, "file": str, "head": str, "sent": (int, float)}
_READ = 65536                               # the bytes of a file `send` reads for its head
_SIDE = 4096                                # the read bound: a pointer past it is no pointer


class Refused(Exception):
    """A verb's refusal: its message, exit 2."""


def _breaks(ch: str) -> bool:
    """A character no printed line may hold: one `str.splitlines` breaks on, a control or
    format character, a lone surrogate."""
    return unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Zl", "Zp") \
        or len(f"a{ch}a".splitlines()) > 1


def _bad(text: str) -> bool:
    return any(_breaks(ch) for ch in text)


def _clean(text: str) -> str:
    """The one cleaner (C2): every character `_breaks` names, taken out."""
    return "".join(ch for ch in text if not _breaks(ch))


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


def _fold(path: str, at: str | None = None) -> str:
    """`path` as the volume of `at` (else its own) compares it: folded where it folds case."""
    probe = at or path
    while probe and not os.path.isdir(probe):
        up = os.path.dirname(probe)
        if up == probe:
            break
        probe = up
    return unicodedata.normalize("NFC", path).casefold() if gate._folds(probe) else path


def same(a: str, b: str) -> bool:
    """Whether two real paths name one checkout by the key that names its box (C5)."""
    return _fold(a) == _fold(b)


def _under(path: str, base: str) -> bool:
    return _fold(path, base).startswith(_fold(base).rstrip(os.sep) + os.sep)


def _records_of(checkout: str) -> str | None:
    """Packet rr5c R2: the real path of the checkout's records folder where the resolver
    answers `out` for it, else None (every other state, a fault, a timeout). Never raises."""
    try:
        a = records.answer(checkout)
        if records.state(a) != "out" or not a.get("records"):
            return None
        return os.path.realpath(a["records"])
    except Exception:                                   # noqa: BLE001 - the pin's verdict
        return None


def _held(path: str, base: str) -> bool:
    """R2: `path` under the checkout `base`, else under its records folder in `out`; the
    resolver is asked only when the first test fails."""
    if _under(path, base):
        return True
    recs = _records_of(base)
    return recs is not None and _under(path, recs)


def address(t: str) -> str:
    """A checkout's folder name: its folded name made safe, then a hash of its folded path."""
    key = _fold(t)
    name = _FOLDER.sub("_", os.path.basename(key))[:NAME].lstrip(".") or "_"
    return f"{name}-{hashlib.sha256(key.encode('utf-8', 'surrogateescape')).hexdigest()[:16]}"


def box(root, t: str) -> Path:
    return Path(root) / DIR / address(t)


def spelling(path: str) -> str:
    """The checkout's own name as its folder spells it, where one listing reads it."""
    name = os.path.basename(path)
    try:
        parent = os.path.dirname(path)
        if gate._folds(parent):
            want = unicodedata.normalize("NFC", name).casefold()
            for e in os.listdir(parent):
                if unicodedata.normalize("NFC", e).casefold() == want:
                    return e
    except (OSError, ValueError):
        pass
    return name


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _pack(ptr: dict, verb: str) -> bytes:
    """A pointer's bytes, ASCII; over the read bound is a refusal, nothing written (C1)."""
    data = (json.dumps(ptr, indent=2) + "\n").encode("ascii")
    if len(data) > _SIDE:
        raise Refused(f"{verb}: the pointer would be {len(data)} bytes, over {_SIDE}")
    return data


def _load(p: Path):
    """The gate's reader, for a file no longer than `_SIDE` bytes; else None."""
    try:
        if os.stat(p).st_size > _SIDE:
            return None
    except OSError:
        return None
    return gate._load(p)


def _pointer(to: str, frm: str, file: str, head: str, closes=None, now=None) -> dict:
    ptr = {"id": "0" * 12, "from": frm, "to": to, "file": file, "head": head,
           "sent": time.time() if now is None else now}
    if closes:
        ptr["closes"] = closes
    return ptr


def _new(root, ptr: dict, verb: str) -> str:
    """Write `ptr` under a fresh id, by a link that never overwrites; the id. Its bytes are
    checked before anything is written."""
    _pack(ptr, verb)
    b = box(root, ptr["to"])
    _mkdir(b)
    tmp = b / f".new.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    for _ in range(8):
        ptr = dict(ptr, id=secrets.token_hex(6))
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(_pack(ptr, verb))
        try:
            os.link(tmp, b / f"{ptr['id']}.json")
        except FileExistsError:
            continue
        finally:
            os.unlink(tmp)
        return ptr["id"]
    raise Refused(f"{verb}: no free id")


def _cut_bytes(text: str, most: int) -> str:
    """`text` cut at a character's end to `most` UTF-8 bytes."""
    data = text.encode("utf-8", "surrogatepass")[:most]
    return data.decode("utf-8", "ignore")


def _first_line(path: str) -> str:
    with open(path, "rb") as fh:
        text = fh.read(_READ).decode("utf-8", "replace")
    for ln in text.splitlines():
        ln = _clean(ln).strip()
        if ln:
            return _cut_bytes(ln, STORED)
    return ""


def send(root, target: str, file: str, start: str, now=None) -> str:
    """R1: the pointer's id. Refused: the target no checkout's top or a worktree, the sender
    in no checkout or in a worktree, the file no file inside the sender's checkout, a path
    that holds a character no printed line may hold."""
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
    if not os.path.isfile(real) or not _under(real, frm):
        recs = _records_of(frm)                     # rr5c R2: in `out`, its records folder
        if recs is None:
            raise Refused(f"line send: {file} is no file inside this checkout, {frm}")
        if not os.path.isfile(real) or not _under(real, recs):
            raise Refused(f"line send: {file} is no file inside this checkout, {frm}, "
                          f"nor under its records folder, {recs}")
    if _bad(real) or _bad(frm) or _bad(to):
        raise Refused("line send: a path holds a line break, a control or format character, "
                      "or a lone surrogate")
    return _new(root, _pointer(to, frm, real, _first_line(real), now=now), "line send")


def valid(ptr, name: str, to: str | None, from_checkout: bool = True) -> dict | None:
    """The pointer when its fields are a pointer's (R5), else None: each known key of its
    type (an unknown one is ignored, as every reader here ignores one, and never printed),
    `id` the file's name, no path holding a character `_breaks` names, `from` a checkout's
    top and no worktree (unless `from_checkout` is False: a close), `to` the taker's checkout
    by the box's key, `file` under `from` (under `to` for a close's line back), or, rr5c R2,
    under that checkout's records folder where the resolver answers `out` for it."""
    if not isinstance(ptr, dict) or not set(REQUIRED) <= set(ptr):
        return None
    for k, t in REQUIRED.items():
        if not isinstance(ptr[k], t) or isinstance(ptr[k], bool):
            return None
    if not ID.match(ptr["id"]) or ptr["id"] != name:
        return None
    for k in ("from", "to", "file"):
        if _bad(ptr[k]) or not os.path.isabs(ptr[k]) or os.path.normpath(ptr[k]) != ptr[k]:
            return None
    if from_checkout and (top(ptr["from"]) is None or not same(top(ptr["from"]), ptr["from"])):
        return None
    if to is not None and not same(ptr["to"], to):
        return None
    if "closes" in ptr and not (isinstance(ptr["closes"], str) and ID.match(ptr["closes"])):
        return None
    if not _held(ptr["file"], ptr["to"] if "closes" in ptr else ptr["from"]):
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
    """The head as printed: its first line, cleaned, 120 UTF-8 bytes."""
    lines = ptr["head"].splitlines()
    return _cut(_clean(lines[0] if lines else "").strip(), 4 * HEAD, HEAD).strip()


def render(ptr: dict) -> str | None:
    """R5's line, made here, then checked whole (C2): one line by `splitlines`, no character
    `_breaks` names, within SHARE bytes encoded with its separator; else None."""
    lid = _clean(ptr["id"])
    frame = f"line {lid} from  ({LABEL}): ; whole: {SHOW} {lid}"
    name = _cut(_clean(spelling(ptr["from"])), NAME)
    room = SHARE - 4 - _enc(frame) - _enc(name)
    head = _cut(_clean(head_of(ptr)), room)
    line = f"line {lid} from {name} ({LABEL}): {head}; whole: {SHOW} {lid}"
    if len(line.splitlines()) != 1 or _bad(line) or _enc(line) + 4 > SHARE:
        return None
    return line


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
    """`p` renamed into `folder`, the one step a state change is; None when another step
    moved it first."""
    _mkdir(folder)
    dest = folder / p.name
    try:
        os.rename(p, dest)
    except OSError:
        return None
    return dest


def take(root, payload: dict, env, start: bool = False) -> str | None:
    """R3 to R6: one printed line, or None. At SessionStart a taken line not yet printed
    again goes first; then the oldest waiting one. Each pointer is read, then claimed by a
    rename, and nothing is written after: the folder is its state. A pointer that is no
    pointer's goes aside, at most ASIDE_MOST a hook, and the next is tried."""
    t = taker(payload, env)
    if t is None:
        return None
    b = box(root, t)
    if not b.is_dir():
        return None
    aside = 0
    for src, dest in (((b / TAKEN, b / AGAIN),) if start else ()) + ((b, b / TAKEN),):
        for p in _oldest(src):
            ptr = _load(p)
            got = _move(p, dest)
            if got is None:
                continue
            ok = valid(ptr, p.stem, t)
            line = render(ok) if ok is not None and "closed" not in ok else None
            if line is not None:
                return line
            _move(got, b / ASIDE)
            aside += 1
            if aside >= ASIDE_MOST:
                return None
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
    ok = valid(ptr, p.stem, None, from_checkout=False) if f != ASIDE else None
    if ok is None:
        return {"id": _cut(_clean(p.stem), 64), "state": "set aside"}
    c = ok.get("closed")
    return {"id": ok["id"], "state": _state(f, ok), "from": ok["from"], "to": ok["to"],
            "file": ok["file"], "head": head_of(ok), "sent": ok["sent"],
            "closes": ok.get("closes"),
            "closed": None if c is None else {"as": c["as"], "note": c.get("note"),
                                              "at": c["at"]}}


def listing(root, t: str) -> dict:
    """R2: the lines addressed to checkout `t`, and the lines it sent, oldest first."""
    mine = box(root, t)
    to, sent = [], []
    for f, p, ptr in _all(root):
        if p.parent in (mine, mine / f):
            to.append(_item(f, p, ptr))
        elif f != ASIDE and isinstance(ptr, dict) and isinstance(ptr.get("from"), str) \
                and same(ptr["from"], t):
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


def close(root, t: str, lid: str, how: str, note=None, now=None) -> tuple:
    """R7: (the line back's id, None), or (None, why no line went back). The pointer is read,
    claimed by a rename into `closing/`, then the closed pointer, its record written first,
    is published by a rename into `closed/` (C4). Every byte is checked before the claim
    (C1). A `from` that is no checkout still closes, with no line back (C3)."""
    verb = "line close"
    if how not in HOWS:
        raise Refused(f"{verb}: --as is one of {', '.join(HOWS)}")
    if note is not None:
        n = len(note.encode("utf-8", "surrogatepass"))
        if _bad(note):
            raise Refused(f"{verb}: --note holds a line break, a control or format character, "
                          "or a lone surrogate")
        if n > NOTE:
            raise Refused(f"{verb}: --note is {n} bytes, over {NOTE}")
    if not ID.match(lid or ""):
        raise Refused(f"{verb}: {_cut(_clean(str(lid)), 64)} is no line id")
    b = box(root, t)
    now = time.time() if now is None else now
    for f in OPEN:
        src = (b / f if f else b) / f"{lid}.json"
        if not src.is_file():
            continue
        ok = valid(_load(src), lid, t, from_checkout=False)
        if ok is not None and "closed" not in ok:
            data = _pack(dict(ok, closed={"as": how, "note": note, "at": now}), verb)
            gone = top(ok["from"]) is None or not same(top(ok["from"]), ok["from"])
            back = None if gone else _pointer(
                ok["from"], t, ok["file"], f"line {lid} closed as {how}"
                + (f": {note}" if note else ""), closes=lid, now=now)
            if back is not None:
                _pack(back, verb)
        got = _move(src, b / CLOSING)
        if got is None:
            continue
        if ok is None or "closed" in ok:
            _move(got, b / ASIDE)
            raise Refused(f"{verb}: {lid} is not a pointer; set aside")
        _mkdir(b / CLOSED)
        tmp = b / CLOSED / f".{lid}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.rename(tmp, b / CLOSED / f"{lid}.json")
        os.unlink(got)
        if back is None:
            return None, f"{ok['from']} is no checkout's top"
        return _new(root, back, verb), None
    if (b / CLOSED / f"{lid}.json").exists() or (b / CLOSING / f"{lid}.json").exists():
        raise Refused(f"{verb}: {lid} is already closed")
    raise Refused(f"{verb}: {lid} is not addressed to this checkout, {t}")


def prune(root, now: float) -> None:
    """R8: a closed pointer whose close is older than KEEP leaves; nothing else does. A
    symlinked `lines/`, box or `closed/` is passed over (C6)."""
    top_dir = Path(root) / DIR
    if os.path.islink(top_dir):
        return
    try:
        boxes = [p for p in top_dir.iterdir() if not os.path.islink(p) and p.is_dir()]
    except OSError:
        return
    for b in boxes:
        if os.path.islink(b / CLOSED):
            continue
        for p in _oldest(b / CLOSED):
            ptr = _load(p)
            c = ptr.get("closed") if isinstance(ptr, dict) else None
            at = c.get("at") if isinstance(c, dict) else None
            if isinstance(at, (int, float)) and not isinstance(at, bool) and now - at > KEEP:
                try:
                    os.unlink(p)
                except OSError:
                    pass
