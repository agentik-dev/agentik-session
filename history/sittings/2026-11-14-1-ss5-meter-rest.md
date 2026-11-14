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
- [x] R1 the tail read: fail only on a tool result stamped past `FRESH_S` after the meter's `ts` (`_missed_call`; an error result and a sidechain line are no missed call)
- [x] R2 the pass's words, and the newest session's note
- [x] R3 an unreadable tail: own session today's verdict, newest a `warn`; the bound `TAIL_MAX` 4 MiB
- [x] R4 the five cases byte-equal to the pin; `test_bare_machine`'s NOT_STATE gains `_missed_call`
- [x] R5 the stamp `2.0.0-alpha.113` (4504 tests); `plugin-version-check` exit 0; README source 16,374 B
- [x] the tree scan 0; the commit scan flags d380f55 (`sibling`, the fake machine's optional plugin rows, fixed forward: the fixture lists this plugin alone): an allow row is the coordinator's
- [ ] the gate once

## Handover

## Next act
The commit scan, then the gate once on this commit.

## Exit
