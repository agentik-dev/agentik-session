# Sitting 2026-11-10-6: agentik-session, wfg (the Workflow guard and R6)

| item | value |
|---|---|
| goal | build packet wfg (R1 to R9), then fold REFUTE wfg r1's seven dispositions |
| budget | builder: 200k window, 180k context, about 90 tool calls (packet: 60 calls, 120k); doclint's five rows |
| pin | bfc66ae (alpha.63) on `wfg-workflow-guard` in `.claude/worktrees/wfg-workflow-guard` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] packet (d9cdad3); tests (15722dd, red `63 failed, 1 passed`); guard (ae3fa92); SKILL, NICE (844e068, a3d7a30); alpha.64 (30a83b7)
- [x] gate 20261110-075649-887 on b29d2ea (the coordinator's): `3 failed, 2738 passed` (T11 under load, test_mod's CLASSIC, test_s49's MAIN_FLOW)
- [x] fold tests (c4b25bd): T12 to T18 and the probes as fixtures, T11 on process_time; at b29d2ea `42 failed, 70 passed` (3.12.7, T11 among them), `41 failed, 71 passed` (3.9.6)
- [x] fold (7008592): the backstop, plain options, default params, thunks, numeric index, the budget, R6's exception, script with scriptPath; `doctor.HOOK_EVENTS` gains PostModelSwitch. test_wfg `112 passed`; with hooks, doctor, precompact, mod, s49 `524 passed` (both pythons)
- [x] SKILL, NICE n59 closed, n61 (c778be8); alpha.65 as the check asked, status line 2789 (5c8e9d6)
- [x] cost: worst case (64 sites, 250 KB) 0.5 s to 0.04 s CPU (the identifier index); 100 KB `measure` 15.5 ms / 15.9 ms, hook +8.7 / +14.3 ms (load 44 to 65); the refuter's c1, c3, c4 denied at the budget in 1.1 to 1.4 s
- [x] whole tests/, one process each: 3.12.7 `2789 passed` (452 s); 3.9.6 `12 failed, 2774 passed, 3 skipped`, the 12 all test_bounded.py, which `test-floor` ignores (bounded is a 3.11 dev tool)

## Handover
- Choice: `with` is denied as `with (`, not as a word, which every prompt holds
- Choice: the budget reads CPU (1 s) and wall (3 s), so T11 and a loaded Mac agree
- Choice: the shim is right (PostModelSwitch drops its exit as Stop does); test_s49's MAIN_FLOW and test_mod's CLASSIC follow it
- Choice: T3's `log('no agent at all')` reworded: the ruling denies the word in a string
- decide, owner: the coordinator: n33 not on main; the rule sits first in `pre_tool_use`; consumer: whichever lands second
- exit: checkpoint; fold built and committed; the gate left to the coordinator; nothing pushed

## Next act
the coordinator's gate on the head, then its read
