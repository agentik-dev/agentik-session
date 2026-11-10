# Sitting 2026-11-10-2: agentik-session, the reconciler's key, cadence and verb (R2)

| item | value |
|---|---|
| goal | packet R2 (`design/packets/r2-reconcile-verb.md`): R1 to R7, `session.reconcile`, `reconcile/runner.py`, the verb, the launcher's close pass; alpha.61 |
| budget | builder: 200k window, 140k context, 90 tool calls; one commit per group |
| pin | 36c84ea (R1 landed, alpha.60); branch `r2-reconcile-verb` in `.claude/worktrees/r2-reconcile-verb` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [x] the packet committed with this charter (two sibling names and one ledger file name reworded for the scan, no ruling word moved)
- [x] tests: `tests/test_r2.py` copied as cut (flagged already `rc == 1`), red at 36c84ea: `23 failed, 1 passed` under 3.12.7 and 3.9.6, T8 the control
- [x] the key and the runner: R1, R2, R4, R5 (`resolver.py`, `reconcile/runner.py`); T5 green alone, T1 to T4 with the verb
- [ ] the verb and the close: R3, R6 (`cli.py`, `chain.py`)
- [ ] the texts and the bump: R7, alpha.61, the status line, the sidecar, README row, RUNBOOK §3 and §4; NICE (a record past 4,096 B)
- [ ] verify: the gate's `make check`, once

## Handover
- open by level: none yet
- Choice (consumer: the reviewer): the version reads up to alpha.61 (the packet's alpha.58 moved by R1's three bumps); flagged exits 1 (the orchestrator's ruling of 2026-11-09, packet §4)
- Choice (consumer: the reviewer): `check` reports every bad key, one line each, not the first alone; `tree` is read relative to the repo; `window`, `every` and `read`'s keys are whole numbers; a newest record without a parsable `run:` line makes the run due

## While waiting
- none

## Next act
the verb and the close: `cli.cmd_reconcile`, `chain.RECONCILE_WAIT`, `reconcile_argv`, `Effects.reconcile`, `Chain._reconcile`
