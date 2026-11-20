# Sitting 2026-11-20-3: agentik-session, pl2-line-dynamic, the first build

| item | value |
|---|---|
| goal | the usage line drops the ceiling and an empty resets or deferred count, closes the week with its reset and time left, says the helpers as `n/m` (R1 to R6, the twins equal); three mends of rc1 and rc2 (R7); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `9d8e0ac` on main (alpha.144) |
| branch | `pl2-line-dynamic`, worktree `.claude/worktrees/pl2-line-dynamic`, the two venvs linked |
| level | S3, packet `design/packets/pl2-line-dynamic.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet, with the pin's line for the owner's entry
- [x] The failing tests, `tests/test_pl2_line_dynamic.py`: 49 of 62 red at the pin (the 10,000-tag scan 5.5 s)
- [x] R1 to R6: `band_line`, `_line_none`, `_mix_resets`, `week_left`, `ceiling_word`; `admissionLine`, `mixPart`, `lineNone`, `weekLeft`; `status`; band.json's `week_resets` written in `band()`; PL2_CASES in the module's tests; pinned lines changed in test_band, test_bands, test_s53, test_window_mode, test_pl1_prompt_line and the module's fixtures; the runbook, the skill. Full suite under `.venv`: 5261 green, red only R7's six and the README's count (the stamp's)
- [ ] R7: the refusal's words, the linear notice scan, the respawn line at PostToolUse; two NICE rows
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- Choices: listed in the packet's §4 as they are made.

## Next act
R7: the refusal's words, the linear scan, the respawn line at PostToolUse; two NICE rows.

## Exit
