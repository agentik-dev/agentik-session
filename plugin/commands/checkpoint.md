---
description: "Mark a handoff-ready point in this session"
argument-hint: "[-m message] [--commit]"
allowed-tools: [Bash(claude-session *)]
---

!`claude-session checkpoint $ARGUMENTS`

The output confirms the checkpoint and resets the prompt counter behind the
checkpoint nudge. A checkpoint means the work is committed or durably recorded
and the charter is current, so the session can be handed off now. If it
refuses because no session is set, say so; with `--commit` it stages tracked
files only and commits them.

A RESPAWN close is not marked here: this command makes no tool call, and only a
main-thread Bash call confirms the mark. Run
`claude-session checkpoint --respawn --charter <file>` through Bash as the
sitting's last act, then end the turn.
