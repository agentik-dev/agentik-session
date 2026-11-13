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
- [x] records: RUNBOOK tiers section, README source 16380 B, sidecar by shasum, 3350 tests
- [x] round 2 (the full local run, 10 red): READERS row, sc3 prompts, the help text, no-xhigh test, README hooks line
- [x] fix round 1, phase 1 (hq `REFUTE-2026-11-12-mt1-r1.md`; fix builder, about 40 tool calls): tests first (50c7418, 21 red at d4b280e)
- [x] F1 F2 F3 (3ecd8a9), F4 (596922a), F3's save, F5, F7, F8, F10 (ef96726); NICE n149 to n152 (F6, F8's unknown role, two observations), n87 n88 n91 to the overflow; packet §4 and RUNBOOK; 1163 passed under `.venv`
- [ ] phase 2, on the coordinator's word only: merge main, recount, version, then the gate once

## Handover
- decide, owner: whether `--save` on a non-tier key should write the user's `profiles.yaml` `profiles.<name>.<key>` (today refused, exit 2); consumer: the owner's `set ... --save` habit.
- F6 is NICE n149, so no record claims comments are kept; F8's unknown-role warning is n150.
- The README was edited by hand in source and render (no `make readme`: it runs claude); the sidecar is by shasum.

## While waiting
- none

## Next act
Phase 1's fixes by finding, then the hand-back; wait for the coordinator's phase 2 message (h3 landed).

## Exit
- 2026-11-12: built; gate 20261112-173918-1238 ran on 212f74e (before the round-2 fixes); the next gate runs on the head
