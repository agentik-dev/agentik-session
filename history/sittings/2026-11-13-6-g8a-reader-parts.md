# Sitting 2026-11-13-6: agentik-session, g8a the reader's new parts, one walk of a line's commands

| item | value |
|---|---|
| goal | brief g8a phase 1 (packet `design/packets/g8a-reader-parts.md`): R1 to R13 |
| budget | builder: about 90 tool calls |
| pin | b92e4e0 on main (2.0.0-alpha.103); worktree `.claude/worktrees/g8a-reader-parts`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Acceptance 1 at the pin: ancestor (exit 0), the four files' diff empty
- [x] Packet committed (its §3 to §6 headings mended in the records' commit, for doclint)
- [x] `tests/test_g8a_reader.py`, red at the pin (its import fails)
- [x] The reader (R2 to R8, R10's strict column): `_walk`, `commands`, `git_words`
- [x] The make rule (R9); acceptance 2 (77 passed), 3 (761 passed), 4 (210 passed 1 warning; floor 207 passed 3 skipped), the pin's counts, both venvs
- [x] Acceptance 5, 12, 13 (recordlint held 69 rows, 23,297 B; no n200, n201, n203)
- [x] NICE rows (R12): n177, n200, n201, n203 out; n197 shortened
- [x] Probes 6 to 11 run against a `git archive` of the pin (numbers in the hand-back)

## Handover
- Acceptance 11 is red in process: the hand lines through the four readers take 4.94 s against OLD's 3.37 s (1.47x, bound 1.25x). The launcher's median is the pin's (62.0/62.1, 60.6/60.3 ms) and the slowest `commands` call is 0.12 s. The next act: profile `_strict` (each other reading walks again) and `unbounded` (`commands` walks the other readings too).
- decide, owner: the coordinator (consumer: acceptance 6). `_loose` calls `_git_paths`, which R8 rebuilds, so the loose answer changes on a line holding `--namespace`, `--config-env`, `--super-prefix` or `--attr-source` before a git subcommand: 0 differ on the tests, packets and replay, 11,611 of 200,000 fuzz lines (the fuzz holds `git --namespace n rm y`). R1 and R8 cannot both hold there.
- The make rule over the replay: 4,572 refused at OLD, 1,674 now; 2,715 of the 2,902 lost hold make only in a heredoc's body (data, R6); 187 lost by class R4 (16), R5 (144), R6 (27) want a review's eye.
- Three test-corpus lines flip deny to pass at the gate; each names a pytest temp folder that no longer exists, so the folder state differs between the two runs (not traced further).

## Next act
- The in-process cost (above), then phase 2 on the coordinator's word.

## Exit
- Phase 1 committed: R1 to R13 built; acceptance 11 red in process; one decide line for the coordinator.
