---
name: machine
description: What the machine has free and what holds its disk. Use when a build is slow, a disk is full, memory is short or an API answers 429, before any fix of your own.
allowed-tools:
  - Bash(agentik-session machine *)
  - Bash(agentik session machine *)
---

# machine

Read the machine first, then act through the tools that own it:

```bash
agentik session machine status
```

It prints the cores, the load, memory and its pressure, each disk's free
space, the gate's running and queued jobs and the three largest consumers.
`agentik session machine fits --cpu N --mem MB` exits 0 where a run fits now,
else 75 with the why.

- Run a build through `agentik session gate run`; it holds every `make` here.
- Never clean by hand: `agentik session machine reclaim --dry-run` lists what
  is safe to free; anything marked `person` is the owner's.
- Never loop on a `sleep` to wait for room: queue the run and hand back.
- For a retry of your own tool's call (a 429), wait `machine.backoff(attempt,
  retry_after)` seconds, at most `machine.ATTEMPTS` tries.
