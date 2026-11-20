# Sitting 2026-11-20-1: agentik-session, rc1-respawn-confirm, the first build

| item | value |
|---|---|
| goal | a RESPAWN close run in the background is refused, an unconfirmed mark is said at each prompt and in the band, the tail teaches a foreground call (rulings R1 to R7); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `7db836d` on main (alpha.142) |
| branch | `rc1-respawn-confirm`, worktree `.claude/worktrees/rc1-respawn-confirm`, the two venvs linked |
| level | S2, packet `design/packets/rc1-respawn-confirm.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet, with the baseline measured at the pin: the stall leaves no confirm and its background PreToolUse passes (`{}`); no prompt line; the pin's tail
- [ ] The failing tests, `tests/test_rc1_respawn_confirm.py`: 29 of 41 red at the pin
- [ ] R1, R2: the deny and the prompt's line in `hooks.py`
- [ ] R3: the band's word in `plugin/hooks/session.ts`
- [ ] R4, R5: the tail, the skill, the command, the runbook; design respawn-r1
- [ ] R7: ten NICE rows
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- (none yet)

## Next act
Commit the failing tests, then R1 and R2 in hooks.py.

## Exit
