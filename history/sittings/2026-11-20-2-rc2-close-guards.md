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
- [x] The failing tests, `tests/test_rc2_close_guards.py`: 32 of 35 red at the pin (the three that pass: markers that give no hold, as at the pin)
- [x] R1: the hold in `chain.py`'s `_watch` (`_unconfirmed`, said only while the watch holds nothing else); NICE n336 leaves; `test_chain.py`, `test_rc1_respawn_confirm.py`, `test_r2.py`, `test_cli.py`, `test_u1.py`, h3, h4 green, 518
- [x] R2 to R4: `_job_open` at PostToolUse, `_jobs_notice` at the prompt, `_jobs_out_line` in `pre_tool_use` after the other Bash guards; NICE n337 leaves, n338 (a mid-turn notice) in; 35 of 35 green, 389 with rc1, hooks, hook_meter, chain, bare_machine
- [x] R5, R6: the runbook, the skill, respawn-r1 §3.3 step 2, §3.9, a change log line; the README left (packet §4); NICE n339 to n343 (rc1's review 1, L1 to L4, L7) and n301's sighting; 1208 green across the tests that read these files
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- Nothing yet.

## Next act
`make stamp`, then `make check`, through the gate.

## Exit
