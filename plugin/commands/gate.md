---
description: "The gate queue: what runs, what waits, the last five done"
argument-hint: "[--json]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session gate status $ARGUMENTS`

The output lists the running gate and its start, each queued gate with its
position and any lock it waits on, the last five results with their exit codes
and minutes, then the runner's pid or `runner: none`. Exit 124 is the wall's
cut, 125 a runner that died, 126 a lock held past the wall.

Queue a gate through Bash, not here: `agentik-session gate run <repo> -- <command>`,
then wake on `agentik-session gate wait <id>` in a background Bash with a
timeout past the gate's length, or on the hook's line at the next prompt.
