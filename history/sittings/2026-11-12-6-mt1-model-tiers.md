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
- [x] fix round 2 (hq `REFUTE-2026-11-12-mt1-r2.md`): tests aa476d5 (10 red at 731c398); R2-F1 a no-family model skipped and named; R2-F2 the five bodies state build opus; R2-F3 R2-F4 the messages; records; mat.py 68 of 768 differ from the pin (64 `local`, R1; 4 user `defaults.profile`, R3)
- [x] phase 2: main merged (h3, alpha.91) on the coordinator's word; NICE n149 to n152 renumbered, n153 to n157 filed; alpha.92, 3400 tests; post-merge 21 files 1248 passed (.venv), 1245 passed 3 skipped (.venv-floor)
- [x] the gate, once, last: 20261112-195001-1278 exit 0 in 13 min on 0de14d5 (3400 passed; floor 3274 passed, 105 skipped)
- [x] fix round 3 (hq `REFUTE-2026-11-12-mt1-r3.md`; fix builder, about 40 tool calls): tests first, 30 of 32 red at f713a6d (ea0bad3)
- [x] R3-F1 a null model unstated, R3-F4 an effort outside the known or null dropped, each named by the doctor (5d7e8d2); R3-F2 R3-F3 NICE n158 n159, n98 n102 to the overflow (355f0e1); packet §4 and RUNBOOK; the files touching tiers or the resolver 2294 passed (.venv)
- [x] alpha.93 alone under `plugin/` (26c7a8a), 3432 tests; the gate once, last: 20261112-203452-1282 exit 0 in 14 min on 26c7a8a (3432 passed; floor 3306 passed, 105 skipped)

## Handover
- decide, owner: whether `--save` on a non-tier key should write the user's `profiles.yaml` `profiles.<name>.<key>` (today refused, exit 2); consumer: the owner's `set ... --save` habit.
- F6 is NICE n149, so no record claims comments are kept; F8's unknown-role warning is n150.
- The README was edited by hand in source and render (no `make readme`: it runs claude); the sidecar is by shasum.

## While waiting
- none

## Next act
Done: the hand-back to the hq coordinator; the coordinator reads the fix's diff and test and lands it.

## Exit
- 2026-11-12: built; gate 20261112-173918-1238 ran on 212f74e (before the round-2 fixes); the next gate runs on the head
- 2026-11-12: fix rounds 1 and 2 and the merge of main built; gate 20261112-195001-1278 exit 0 on 0de14d5
- 2026-11-12: fix round 3 built (R3-F1, R3-F4; n158, n159); gate 20261112-203452-1282 exit 0 on 26c7a8a
