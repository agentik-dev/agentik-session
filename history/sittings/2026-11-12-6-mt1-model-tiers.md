# Sitting 2026-11-12-6: agentik-session, mt1 model tiers in the profiles

| item | value |
|---|---|
| goal | packet mt1 (`design/packets/mt1-model-tiers.md`): `tiers` in every profile, one table, the user layer's default profile, `set tier.*` and `set cap`, the role check, the start applies the profile; plugin 2.0.0-alpha.90 |
| budget | builder: about 90 tool calls |
| pin | 33a4d85 on main (alpha.89); worktree `.claude/worktrees/mt1-model-tiers`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet committed (03be8af)
- [x] tests first: `tests/test_mt1_tiers.py`, 31 tests, 25 red at the pin (4f408f4)
- [x] R1 R2 R3 R5 (f960869), R6 and the doctor row (8fe727e), R3 R4 R7 (a27cbd9); mt1 31 passed under `.venv` and `.venv-floor`; test_chain 116 passed
- [x] version bump in its own commit: 2.0.0-alpha.90 (651b4db)
- [x] records: RUNBOOK's model tiers section, README source 16376 B and README, sidecar by shasum, the status line
- [ ] the gate, once, last

## Handover
- decide, owner: whether `--save` on a non-tier key should write the user's `profiles.yaml` `profiles.<name>.<key>` (today refused, exit 2); consumer: the owner's `set ... --save` habit.
- The README was edited by hand in source and render (no `make readme`: it runs claude); the sidecar is by shasum.

## While waiting
- none

## Next act
The gate's `make check` on the branch tip, then the hand-back to the hq coordinator.

## Exit
- (open)
