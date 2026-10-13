"""The model decides the window; the role decides the ceilings within it.

A model string names a family (`claude-opus-5-5` and `opus` are opus) and may
carry Claude Code's 1M marker, `[1m]` (`opus[1m]`, `claude-opus-5-5[1m]`). The
`models:` table in profiles.yaml maps a family to its window; `<family>-1m` is
the family under the marker (a YAML-subset key holds no brackets).

What each source can say (Claude Code 2.1.284, read from its own binary and from
transcripts' `message.model` only), in the order `pick` reads them:

  the transcript   `message.model` is the API model id; Claude Code strips the
                   `[1m]` marker before the request, so a 1M Opus session reads
                   `claude-opus-5-5`, like a 200k one. It names the family, and
                   the window only for a family with one window (fable: 1M).
  the session      the SessionStart payload's `model`: the session's main-loop
                   model as Claude Code resolved `--model`, `/model`, the env and
                   the settings, marker intact (`claude-opus-5-5[1m]`); under
                   `claude -p` the payload has none, and the launcher's env names
                   it: `CLAUDE_SESSION_MODEL`, the spawn line's `--model` (agent-relay
                   AR74), never read by a helper (`CLAUDE_SESSION_HELPER=1`); a later
                   `claude-session set model` drops it until the next SessionStart
  the declared     the resolved profile's `model` (`opus[1m]`), the overlay's included
  the configured   `ANTHROPIC_MODEL`, then the settings `model` key (local,
                   project, user)

`pick` is pure; `configured` reads the settings files' `model` key and nothing else.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ONE_M = 1_000_000
DEFAULT_WINDOW = 200_000
MARKER = re.compile(r"\[1m\]\s*$", re.IGNORECASE)
SUFFIX = "-1m"
# The two classes of window a role carries ceilings for, and the key each reads.
CLASSES = {"200k": "ceilings", "1m": "ceilings_1m"}


def marked(model) -> bool:
    """True when the model string carries the 1M marker."""
    return isinstance(model, str) and bool(MARKER.search(model))


def family(model, table: dict) -> str | None:
    """The table's family a model string names, or None: `claude-opus-5-5` -> `opus`."""
    if not isinstance(model, str) or not isinstance(table, dict):
        return None
    names = {k for k in table if not str(k).endswith(SUFFIX)}
    for token in re.split(r"[^a-z0-9]+", MARKER.sub("", model.strip().lower())):
        if token in names:
            return token
    return None


def window_of(model, table: dict) -> int | None:
    """The window the table gives a model string; None when it knows no family in it."""
    fam = family(model, table)
    if fam is None:
        return None
    if marked(model) and f"{fam}{SUFFIX}" in table:
        return table[f"{fam}{SUFFIX}"]
    return table[fam]


def _one_window(fam: str, table: dict) -> bool:
    """A family whose name alone decides its window (no `-1m` entry that differs)."""
    alt = table.get(f"{fam}{SUFFIX}")
    return alt is None or alt == table[fam]


def pick(table: dict, observed=None, session=None, declared=None,
         configured=()) -> tuple[int, str]:
    """(window, source). The transcript's model (`observed`) when it decides the
    window; for a family with two windows, the first of the session's, the declared
    and the configured models that names the same family; with no model read yet,
    or one the table does not know, the first of those the table knows; else the
    200k default."""
    candidates = [("session", session), ("declared", declared)] + [
        ("configured", c) for c in configured or ()]
    fam = family(observed, table)
    if fam is not None:
        if marked(observed) or _one_window(fam, table):
            return window_of(observed, table), f"model:{observed}"
        for src, m in candidates:
            if family(m, table) == fam:
                return window_of(m, table), f"{src}:{m}"
        return table[fam], f"model:{observed}"
    for src, m in candidates:
        w = window_of(m, table)
        if w is not None:
            return w, f"{src}:{m}"
    return DEFAULT_WINDOW, "default"


def window_class(window) -> str:
    """`1m` for a window of 1M or more, else `200k`."""
    return "1m" if isinstance(window, int) and window >= ONE_M else "200k"


def configured(env, cwd) -> list:
    """The configured model strings, in order: `ANTHROPIC_MODEL`, then the settings
    `model` key (the project's local and shared settings, then the user's)."""
    out = [env.get("ANTHROPIC_MODEL")]
    home = Path(env.get("HOME") or Path.home())
    for path in (Path(cwd) / ".claude" / "settings.local.json",
                 Path(cwd) / ".claude" / "settings.json",
                 home / ".claude" / "settings.json"):
        try:
            doc = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        out.append(doc.get("model") if isinstance(doc, dict) else None)
    keep: list = []
    for m in out:
        if isinstance(m, str) and m.strip() and m not in keep:
            keep.append(m)
    return keep
