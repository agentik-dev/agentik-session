---
description: "Mark a handoff-ready point in this session"
argument-hint: "[-m message] [--commit <paths...>]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session checkpoint $ARGUMENTS`

The output confirms the checkpoint and resets the prompt counter behind the
checkpoint nudge. A checkpoint means the work is committed or durably recorded
and the charter is current, so the session can be handed off now. If it
refuses because no session is set, say so; `--commit <paths...>` commits the
named paths and nothing else (another writer's staged file stays out), and
`--commit` with no path is refused.

A RESPAWN close is not marked here: this command makes no tool call, and only a
main-thread Bash call confirms the mark. Run
`agentik-session checkpoint --respawn --charter <file>` through Bash as the
sitting's last act, then end the turn.
