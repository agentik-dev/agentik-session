"""Paths and tunables.

State lives under XDG state, not ~/.claude/cache: a directory named "cache"
invites deletion by the user and by cleanup tools, and nothing else owns that
path.
"""

from __future__ import annotations

import os
from pathlib import Path

APP = "agentik-session"
# agentik-r1 §6.3 c1: the state folder's name before the rename, read until r2 removes it.
OLD_APP = "claude-code-session"


def pick(new: Path, old: Path) -> Path:
    """agentik-r1 §6.3's fallback for a renamed path (c1 c4 c5 c8): the new path when it
    exists, else the old when it exists, else the new. A writer writes where this resolved,
    so old and new code share the old folder until the cold window moves it."""
    if new.exists():
        return new
    if old.exists():
        return old
    return new


def state_dir(env) -> Path:
    """The one state root, the contract path (D9): `${XDG_STATE_HOME:-~/.local/state}/`
    plus APP (or OLD_APP, by `pick`), `~` read from `env`'s HOME. Every dependent finds the
    resolved file here, and everything this tool keeps (overlays, configs, sessions, the
    ledger) lives under it. `CLAUDE_SESSION_STATE_DIR` is retired (ADV6-6)."""
    xdg = env.get("XDG_STATE_HOME")
    if xdg:
        base = Path(xdg).expanduser()
    else:
        home = env.get("HOME")
        base = (Path(home) if home else Path.home()) / ".local" / "state"
    return pick(base / APP, base / OLD_APP)


STATE_DIR = state_dir(os.environ)

MAX_UNTRACKED_DIFF_BYTES = 256 * 1024
MAX_PATCH_BYTES = 4 * 1024 * 1024


def ensure_dirs() -> None:
    """Create the state dir 0700."""
    for d in (STATE_DIR,):
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            d.chmod(0o700)
        except OSError:
            pass
