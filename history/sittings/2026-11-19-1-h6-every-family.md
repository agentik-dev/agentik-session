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
- [x] R1 to R4: the rule and its two lines in `_spawn_rule`; 247 green under both venvs (the new file and the standing five, `test_wfd.py` too); the probe's three cells deny, every other as at the pin
- [x] R6: `RUNBOOK.md`'s family rule paragraph says the rule as built; NICE n324 (D5's lead); no shipped profile runs a Sonnet or Haiku main model, so none is newly refused
- [x] `make stamp` through the gate: job `20261119-101204-2697`, exit 0; alpha.140 to alpha.141, the count 5079 to 5095
- [ ] `make check` through the gate: job `20261119-101220-2698` exit 2, the tests green (5095 passed; 4931 passed, 143 skipped) and recordlint's 400-character bound on n324; the row shortened, the check again

## Handover
- Choices: one line for both new forms' head (`a helper starts only at or below its session's family`), the helper's family said as `family <f>` after its model; `tiers` imported inside `_spawn_rule`, as `_rank` does; the session is read for an Opus, Sonnet or Haiku helper too, so a failure there now denies those as well (R4).

## Next act
`make check` through the gate.

## Exit
