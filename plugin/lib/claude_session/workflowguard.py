"""The model families a spawn names (packets wfg, wfd).

The suite runs no workflows (packet wfd): the PreToolUse hook denies every Workflow call
unread, so no script is checked here. What stays is `family`, which the Fable rule on Agent
and Task reads (a Fable helper starts only under a Fable session) and which the session's
model records are reduced to.
"""
from __future__ import annotations

FAMILIES = ("opus", "sonnet", "haiku", "fable")


def family(model) -> str | None:
    low = model.lower() if isinstance(model, str) else ""
    for f in FAMILIES:
        if f in low:
            return f
    return None
