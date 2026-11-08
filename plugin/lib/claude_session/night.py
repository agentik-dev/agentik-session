"""`agentik session night`: the overnight loop beside the relay, without its land step.

hq design/07 §2, packet night-1. `run` reads `<repo>/relay/queue.yaml` in the relay's
schema and, for each row in file order, asks admission, stages a worktree, spawns one
`claude -p` builder in it, reads its stream as it comes, and judges the row: `built
<sha>`, `red <reason>`, `skip <reason>`, `refused <reason>` or `limit`. One JSON line per
event goes to the night's `ledger.jsonl`; `status` reads the newest. Standard library,
the 3.9 floor (hq entry 6); every effect is an `Fx` field, as `gate.py`'s.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import admission, gate, resolver, yamlsubset

QUEUE = Path("relay") / "queue.yaml"
CONTEXT_CEILING = 180000          # the builder profile's (hq NICE n3: never budget.context)
STALL = 2700.0                    # the relay's watchdog
POLL = 30.0
WALL = 4 * 3600
ALLOWED_TOOLS = "Bash Edit Write MultiEdit NotebookEdit"     # relay DefaultAllowedTools
DENIED_PUSH_URL = "relay-denies-push"                         # relay DeniedPushURL
HEADING = "# The packet; the repo's CLAUDE.md carries the rules"
CONTINUE = "continue from your charter's act in flight; your commits stand"
ROW_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\Z")
NIGHT = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\Z")


class NightError(Exception):
    """A refusal before the first row: `run` exits 2."""


def _say(line: str) -> None:
    print(line, flush=True)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


@dataclass
class Fx:
    """The loop's effects, each faked in tests. `now` is the wall clock (the ledger's
    stamps, a limit's reset), `mono` the watchdog's; `sleep` is a limit's wait and the
    kill's grace, never the watchdog's poll, which waits on the child itself."""
    now: Callable[[], float] = time.time
    mono: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = _sleep
    popen: Callable = subprocess.Popen
    killpg: Callable = os.killpg
    say: Callable[[str], None] = _say
    env: dict = field(default_factory=lambda: dict(os.environ))
    grace: float = gate.GRACE


def nights_dir(env) -> Path:
    return resolver.state_dir(env) / "nights"


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _key(name: str):
    m = NIGHT.match(name)
    return (m.group(1), int(m.group(2))) if m else None


def new_night(env, now: float) -> tuple[str, Path]:
    """`<state>/nights/<date>-<n>/`, n one past today's highest; its id `night-<date>-<n>`."""
    root = nights_dir(env)
    _mkdir(root)
    os.chmod(root, 0o700)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    n = 1 + max([k[1] for k in map(_key, os.listdir(root)) if k and k[0] == today] or [0])
    while True:
        d = root / f"{today}-{n}"
        try:
            d.mkdir(mode=0o700)
        except FileExistsError:
            n += 1
            continue
        return f"night-{today}-{n}", d


def newest_night(env) -> Path | None:
    try:
        names = [n for n in os.listdir(nights_dir(env)) if _key(n)]
    except OSError:
        return None
    return nights_dir(env) / max(names, key=_key) if names else None


def _append(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(text)


# ---- the queue (ruling 2) --------------------------------------------------------------

HEAD_KEYS = ("version", "defaults", "rows")
DEFAULT_KEYS = ("model", "turns", "context", "usd", "wall", "merge", "verify")
ROW_KEYS = ("id", "packet", "model", "budget", "parked", "merge", "base", "depends_on", "kind",
            "verify")
BUDGET_KEYS = ("turns", "usd", "context", "wall")
_ITEM = re.compile(r"^(\s*)- (.*)$")
_ROWS = re.compile(r"^rows\s*:\s*(#.*)?$")
_WALL = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\Z")


def _bare(line: str) -> str:
    """The line less a comment, by the subset's rule: `#` at the start or after a space."""
    if line.lstrip().startswith("#"):
        return ""
    return line.split(" #", 1)[0].rstrip()


def _joined(lines: list) -> list:
    """Each open flow map joined onto its next lines, so the subset reads it as one line."""
    out, i = [], 0
    while i < len(lines):
        ln, i = lines[i], i + 1
        depth = _bare(ln).count("{") - _bare(ln).count("}")
        if depth > 0:
            ln = _bare(ln)
            while depth > 0 and i < len(lines):
                nxt, i = _bare(lines[i]).strip(), i + 1
                if nxt:
                    ln += " " + nxt
                    depth += nxt.count("{") - nxt.count("}")
        out.append(ln)
    return out


def _load(text: str, where: str) -> dict:
    try:
        return yamlsubset.load(text)
    except yamlsubset.YAMLSubsetError as e:
        raise NightError(f"{where}: {e}") from None


def read_queue(text: str) -> dict:
    """The relay's queue in the subset, `yamlsubset` unchanged: the head is read whole and
    `rows:` is cut at each `- `, every row read on its own with its `- ` blanked. A row is a
    mapping, `version` is 1; else NightError."""
    head, chunks, cur, indent, in_rows = [], [], None, None, False
    for ln in _joined(text.splitlines()):
        if in_rows and ln.strip() and not ln[:1].isspace() and not ln.startswith("#"):
            in_rows = False
        if in_rows:
            m = _ITEM.match(ln)
            if m and (indent is None or len(m.group(1)) == indent):
                indent = len(m.group(1))
                cur = [" " * (indent + 2) + m.group(2)]
                chunks.append(cur)
            elif not ln.strip() or ln.lstrip().startswith("#"):
                pass
            elif cur is None:
                raise NightError(f"queue: a line under rows: before its first '- ': {ln.strip()[:60]}")
            else:
                cur.append(ln)
            continue
        if _ROWS.match(ln):
            in_rows = True
            continue
        head.append(ln)
    q = _load("\n".join(head) + "\n", "queue")
    v = q.get("version")
    if type(v) is not int or v != 1:
        raise NightError(f"queue: version is {v!r}, not 1")
    if chunks:
        q["rows"] = [_load(textwrap.dedent("\n".join(c)) + "\n", f"queue: row {i + 1}")
                     for i, c in enumerate(chunks)]
    rows = q.get("rows") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise NightError("queue: rows is not a list of mappings")
    if not isinstance(q.get("defaults") or {}, dict):
        raise NightError("queue: defaults is not a mapping")
    q["rows"] = rows
    return q


def wall_seconds(v):
    """`<n>h<n>m<n>s` or whole seconds; the default 4h; None when unreadable."""
    if v is None:
        return WALL
    if type(v) is int:
        return v if v > 0 else None
    m = _WALL.match(str(v))
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + s or None


def plan(q: dict, keep, log) -> list:
    """Each row with the defaults under it, in file order; every key the loop does not
    honour is one `log` line. `keep` (the `--rows` ids) keeps those; an unknown one is a
    NightError."""
    d = q.get("defaults") or {}
    for k in q:
        if k not in HEAD_KEYS:
            log(f"ignored {k}")
    for k in d:
        if k not in DEFAULT_KEYS:
            log(f"ignored defaults.{k}")
    out = []
    for r in q["rows"]:
        rid = r.get("id")
        b = r.get("budget") if isinstance(r.get("budget"), dict) else {}
        for k in r:
            if k not in ROW_KEYS:
                log(f"ignored {rid}.{k}")
        for k in b:
            if k not in BUDGET_KEYS:
                log(f"ignored {rid}.budget.{k}")
        out.append({"id": rid, "packet": r.get("packet"), "model": r.get("model", d.get("model")),
                    "turns": b.get("turns", d.get("turns")), "usd": b.get("usd", d.get("usd")),
                    "context": b.get("context", d.get("context")),
                    "wall": b.get("wall", d.get("wall")), "merge": r.get("merge", d.get("merge")),
                    "verify": r.get("verify", d.get("verify")), "base": r.get("base"),
                    "depends_on": r.get("depends_on"), "parked": r.get("parked"),
                    "kind": r.get("kind")})
    if keep:
        unknown = [k for k in keep if k not in {p["id"] for p in out}]
        if unknown:
            raise NightError("--rows: no row " + ", ".join(repr(k)[:66] for k in unknown))
        out = [p for p in out if p["id"] in keep]
    return out


def _num(v) -> bool:
    return type(v) in (int, float) and v > 0


def judge_row(p: dict, repo: Path):
    """(state, reason) for a row that does not run, else None: `refused` or `skip`."""
    rid = p["id"]
    if not isinstance(rid, str) or not ROW_ID.match(rid):
        return "refused", "id"
    if p["parked"]:
        return "skip", "parked"
    if p["kind"] == "orchestrator":
        return "refused", "kind"
    if type(p["context"]) is int and p["context"] > CONTEXT_CEILING:
        return "refused", "context"
    pk = p["packet"]
    if not isinstance(pk, str) or not pk or os.path.isabs(pk):
        return "refused", "packet"
    real, top = os.path.realpath(repo / pk), os.path.realpath(repo)
    if not real.startswith(top + os.sep) or not os.path.isfile(real):
        return "refused", "packet"
    if p["base"] not in (None, "main"):
        return "refused", "base"
    if not isinstance(p["model"], str) or not p["model"]:
        return "refused", "model"
    if type(p["turns"]) is not int or p["turns"] <= 0 or not _num(p["usd"]):
        return "refused", "budget"
    if wall_seconds(p["wall"]) is None:
        return "refused", "wall"
    if p["depends_on"]:
        return "skip", "gate-failed-dependency"
    return None


# ---- admission (ruling 3) --------------------------------------------------------------

def admit(night_id: str, model: str, env) -> dict:
    """Admission's verdict for one spawn, as a helper's is asked: `mode`, `text`, `peak`.
    Admission observes and never refuses; an error is recorded and the row runs."""
    try:
        v = admission.admit(night_id, json.dumps({"subagentType": "night", "model": model}), env)
    except Exception as e:      # noqa: BLE001  (any failure is recorded, never a stop)
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return {k: v.get(k) for k in ("mode", "text", "peak")}
