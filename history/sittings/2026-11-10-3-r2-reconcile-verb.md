# Sitting 2026-11-10-3: agentik-session, R2's review fold (the reconciler's key, cadence and verb)

| item | value |
|---|---|
| goal | fold R2's one review round: F1 to F4 (blocking), F5, F7 to F10 riding, one NICE row for F6; nothing else |
| budget | builder: 200k window, 150k context, 100 tool calls; one commit per act |
| pin | d12ccc5 (R2 built, alpha.61); branch `r2-reconcile-verb` in `.claude/worktrees/r2-reconcile-verb` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [x] tests first: 49 cases added to `tests/test_r2.py` (no existing case edited), red at d12ccc5's code: `30 failed, 43 passed` under 3.12.7 and 3.9.6; the 19 green at d12ccc5 pin surviving mutants (F8)
- [x] the code: `chain.py` (F1, F7), `reconcile/runner.py` (F2, F3, F4, F5, F9, F10), `cli.py` (F4); `73 passed` under 3.12.7 and 3.9.6; test_chain, test_cli, test_launch, test_launch_model, test_r1, test_resolver 343 passed under each
- [x] the texts: RUNBOOK §3 (`false` off, the folder's real path, the ceiling, records ahead, exit 2) and §4 (a stop in the pass); NICE n48 (F6, `tree`); status line 2701 by hand, sidecar re-hashed (`shasum -c` OK); no version bump (alpha.61 stands); readme, doclint, hygiene, r2 215 passed under each python
- [ ] verify: one gate job, `make check`

## Handover
- open by level: none yet
- Choice (consumer: the coordinator): a stop seen during or right after the pass comes after the restart line, so the ledger holds that restart line and then the stop line with the grace's reason, as a spawn that fails after it does
- Choice (consumer: the coordinator): a record is ahead of now when its name's date is after now's or its stamp is after now; the newest by name not ahead is the last run (an unreadable stamp there makes the run due); the ahead line goes to stderr, so `--json` stays JSON
- exit taken: none yet

## While waiting
- none

## Next act
verify: one gate job, `make check`
