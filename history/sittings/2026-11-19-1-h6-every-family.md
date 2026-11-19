# Sitting 2026-11-19-1: agentik-session, h6-every-family, the first build

| item | value |
|---|---|
| goal | the spawn gate refuses every family above the session's, an unknown session still Fable alone (rulings R1 to R6); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `c0bcb94` on main (alpha.140) |
| branch | `h6-every-family`, worktree `.claude/worktrees/h6-every-family`, the two venvs linked |
| level | S3, packet `design/packets/h6-every-family.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet, with the baseline measured at the pin: the table's three cells pass; 211 standing tests green under both venvs
- [x] The failing tests, `tests/test_h6_every_family.py`: 7 of 16 red at the pin (the 9 that pass: D5's helper row, R2's no family, line 3, the Fable bytes, line 6)
- [ ] R1 to R4: the rule and its two lines in `_spawn_rule`
- [ ] R6: `RUNBOOK.md`'s family rule paragraph; NICE n324 (D5's lead)
- [ ] `make stamp` through the gate
- [ ] `make check` through the gate

## Handover
- Choices: none yet.

## Next act
R1 to R4 in `_spawn_rule`.

## Exit
