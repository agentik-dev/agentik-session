# Sitting 2026-11-20-2: agentik-session, rc2-close-guards, the first build

| item | value |
|---|---|
| goal | the launcher says an unconfirmed mark's hold; a main-thread background job is recorded, closed by its notice, and a foreground RESPAWN close is refused once while one is open (rulings R1 to R6); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `dc6b78d` on main (alpha.143) |
| branch | `rc2-close-guards`, worktree `.claude/worktrees/rc2-close-guards`, the two venvs linked |
| level | S2, packet `design/packets/rc2-close-guards.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet, with the baseline measured at the pin
- [ ] The failing tests, `tests/test_rc2_close_guards.py`: 32 of 35 red at the pin
- [ ] R1: the hold in `chain.py`'s `_watch`; NICE n336 leaves
- [ ] R2 to R4: the records, the notice, the refusal in `hooks.py`; NICE n337 leaves
- [ ] R5, R6: the runbook, the skill, respawn-r1; the NICE rows
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- Nothing yet.

## Next act
Write the failing tests, then R1.

## Exit
