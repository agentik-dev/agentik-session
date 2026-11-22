---
description: "The gate queue: what runs, what waits, the last five done"
argument-hint: "[--json]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session gate status $ARGUMENTS`

The output lists the running gate and its start, each queued gate with its
position and any lock it waits on, the last five results with their exit codes
and minutes, then the runner's pid or `runner: none`. A running or queued line
ends `; est <m> min` when its repo has three greens or more of the same command
(`make check` beside `make check`, never a stamp's or an install's): the median of
its last five. Exit 124 is the wall's cut, 125 a runner that died, 126 a lock held
past the wall. A result keeps the repo's `head` and `key`.

Queue a gate through Bash, not here: `agentik-session gate run <repo> -- <command>`,
then wake on `agentik-session gate wait <id>` in a background Bash with a
timeout past the gate's length, or on the hook's line at the next prompt.
`wait` exits 0 whatever the job's code; `agentik-session gate wait <id> --strict`
exits the job's code, and a line on stdout marks the code as the job's.

Under a chain the result follows the chain: a job queued by the chain's sitting or its
helper, by any verb, lands in the chain's inbox, and the chain's live sitting takes it,
the successor where the queuing sitting has closed. Its line adds the head, the dirt
when not 0, and the label cut to 48 bytes. `agentik-session gate wait --chain` wakes
on the chain's next line (0), exits 2 with no open job and no line, and 1 past
`--timeout`; `agentik-session gate status --chain` lists the chain's open jobs and its
results of the last day. A job outside a chain reaches its caller as before.
