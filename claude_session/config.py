"""Paths and tunables.

State lives under XDG state, not ~/.claude/cache: a directory named "cache"
invites deletion by the user and by cleanup tools, and nothing else owns that
path.
"""

from __future__ import annotations

import os
from pathlib import Path

APP = "claude-code-session"


def state_dir(env) -> Path:
    """The one state root, the contract path (D9): `${XDG_STATE_HOME:-~/.local/state}/`
    plus APP, `~` read from `env`'s HOME. Every dependent finds the resolved file here,
    and everything this tool keeps (overlays, configs, sessions, the ledger) lives under it.
    `CLAUDE_SESSION_STATE_DIR` is retired (ADV6-6): it moved half the state."""
    xdg = env.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).expanduser() / APP
    home = env.get("HOME")
    return (Path(home) if home else Path.home()) / ".local" / "state" / APP


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
