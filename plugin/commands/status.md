---
description: "This session's meter: context, turns and the budget zone"
argument-hint: "[--json]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session status $ARGUMENTS`

The line above is this session's meter, from the PostToolUse hook's `meter.json`:
context used against the context ceiling, turns against the turn ceiling, and
the zone (clear, notice, wind-down, reserve, exhausted). Past the profile's
checkpoint (80% by default), bring the charter current and commit. An error
saying there is no meter means PostToolUse has not run in this session: suggest
`/session:doctor`. Report the line; do not act on it unless the user asks.
