# Sitting 2026-11-14-1: agentik-session, ss5 the doctor's `meter` check fails only on an unmetered tool call

| item | value |
|---|---|
| goal | a session at rest passes `meter`; only a tool call that ended with no meter fails it (R1 to R5) |
| budget | about 90 tool calls; checkpoint at 80% |
| pin | main at `ad8029a` (g8a-reader-parts, alpha.112) |
| branch | `ss5-meter-rest`, worktree `.claude/worktrees/ss5-meter-rest`, the two venvs linked |
| level | S2, a small change: no packet |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] tests first, red at the pin (acceptance 1 to 7): 14 of 31 red at ad8029a; the 17 green are lines 6 and 7 and the own session's unread tails
- [ ] R1 the tail read: fail only on a tool result stamped past `FRESH_S` after the meter's `ts`
- [ ] R2 the pass's words, and the newest session's note
- [ ] R3 an unreadable tail: own session today's verdict, newest a `warn`; the bound
- [ ] R4 the five cases byte-equal to the pin
- [ ] R5 the stamp
- [ ] the commit scan `main..HEAD`: exit 0
- [ ] the gate once

## Handover

## Next act
The change in `doctor._check_meter` (R1 to R3), then the stamp.

## Exit
