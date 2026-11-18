# Sitting 2026-11-17-14: agentik-session, st1-starter, the fix of review 1

| item | value |
|---|---|
| goal | the fix of review 1: one waiver field (C1), plain budget lines (C2), the bare-machine proof (C3), a launched chain runs the full profile (C4), the README's lint (C5), NICE rows and the packet (C6) |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `69d0824` on main; branch head at open `efaa255` |
| branch | `st1-starter`, worktree `.claude/worktrees/st1-starter` |
| level | S3, packet `design/packets/st1-starter.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] C1 and C4: `charter.discipline` (starter's alone); a chain with nothing named runs frontier. Probe: the review's 62 fixtures re-run on this tree; every named one equals the pin's outputs but for the shipped file's hash and resolved_at
- [x] C2: plain budget lines under the waiver; the cadence line is not given (one commit with C1 and C4: one function carries all three)
- [ ] C3: the bare-machine proof names no profile
- [ ] C5: README's "Use it when" line, by the source and `make readme`
- [ ] C6: NICE rows for F4, F6, F7; the packet's fix section
- [ ] the gates: lint and doclint, hygiene, `make stamp`, `make check`

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
C1 and C4, tests first.

Exit:
