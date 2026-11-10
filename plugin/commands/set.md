---
description: "Adjust one setting for this session only"
argument-hint: "<knob> <value> [--save] | fill <reset|opus|off> [--until <zoned time>]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session set $ARGUMENTS`

The output confirms the knob and its new value, and that this session's
resolved file was rewritten. It is session-only unless `--save` was given;
add `--save` only when the user says to keep it. A launch-time knob (model,
effort, tools, plugins) is not applied until the next start: the output names
the in-session equivalent (`/model`, `/effort`); offer to run it. An error
names the knobs that can be set; relay it.

`set fill <reset|opus> [--until <zoned time>]` is the owner's word alone:
run it only when they say so, from the main thread of an orchestrator on a
1M window. `opus` needs `--until` with its zone; `reset` alone ends at the
week's reset, and no word outlives it. It is this session's only (`--save`
and `--config` are refused), and `set fill off` ends it. Never keep it in a
memory, a ledger or a charter.
