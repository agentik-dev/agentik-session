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
