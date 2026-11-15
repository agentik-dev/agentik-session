# Sitting 2026-11-14-7: agentik-session, su4 the suite's three reads

| item | value |
|---|---|
| goal | build 1: gate items' `caller` and `queued` (R1), the loop's pid line and `pid` (R2), `status --all` (R3), describe's `sittings` read (R4), `MORE_REPO` quoted (R5), the words and NICE rows (R6) |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `95da908` (rw3-gate-repo's merge, alpha.123) |
| branch | `su4-session-reads`, worktree `.claude/worktrees/su4-session-reads`, the two venvs linked |
| level | S4: `design/packets/su4-session-reads.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet and this file
- [x] the tests, red at `95da908`: 12 failed of 15; the three pin-bytes lines (2, 5) green
- [ ] R1 and R5, the gate
- [ ] R2, the loop's pid
- [ ] R3 and R4, the sittings read and describe
- [ ] R6, the words and NICE rows
- [ ] check, by the gate queue; `scripts/hygiene --require-private --commits main..HEAD` exit 0

## Handover
- Choices inside the rulings: the packet's §3.
- If this sitting is cut: the first unticked line above.

## Next act
R1 and R5, the gate.

## Exit
Open.
