# Sitting 2026-11-10-6: agentik-session, wfg (the Workflow guard and R6)

| item | value |
|---|---|
| goal | build packet wfg: `workflowguard.py`, the PreToolUse rule for `SPAWNING_TOOLS` (R1 to R8), R6's `model.json` with PostModelSwitch registered, R9's docs |
| budget | builder: 200k window, 180k context, about 90 tool calls (packet: 60 calls, 120k); doclint's five rows |
| pin | bfc66ae (alpha.63) on `wfg-workflow-guard` in `.claude/worktrees/wfg-workflow-guard` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet as `design/packets/wfg-workflow-guard.md`, sections renamed for doclint only, no ruling word changed (d9cdad3)
- [x] tests first (15722dd): at bfc66ae `63 failed, 1 passed` under 3.12.7 and 3.9.6
- [x] the guard (ae3fa92): the prototype read and applied; PostModelSwitch registered last; test_doctor (3 tests) and test_precompact (2) amended; RUNBOOK step 2 and the guard's bullet. test_wfg `64 passed`; with hooks, doctor, precompact, readme `279 passed` (both pythons)
- [x] cost, 100,259 B script: `measure` 9.2 ms (3.12), 9.0 ms (3.9); the hook process +18.1 ms, +19.3 ms over a Bash call of the same size (load 13 to 20)
- [x] SKILL, NICE n58 to n60 (844e068, a3d7a30); alpha.64, status line 2741 (30a83b7)
- [ ] the gate once; the range scan

## Handover
- Rulings (the coordinator): Q1 the ceiling 8; Q2 Fable in a workflow only under a Fable session, labelled design or refutation, two at most; Q3 and Q4 not in this packet; deny, never rewrite input; R6 as written
- Choice: PostModelSwitch sits last in hooks.json, so the tests pin `[*doctor.HOOK_EVENTS, "PostModelSwitch"]`
- Choice: `scripts/bare-proof` and test_bare_machine untouched (86 passed with the event registered); n60
- decide, owner: the coordinator: `doctor.HOOK_EVENTS` lacks PostModelSwitch; `doctor.py` is outside may-touch (n59); consumer: the doctor's `plugin` line
- decide, owner: the coordinator: the pin asked for n33 on main; it is not (bfc66ae), so the rule sits first in `pre_tool_use`, and n33's landing meets it there; consumer: whichever lands second
- A single unreproduced red under load (1 failed of 279, both pythons at once, load 18 to 23); five reruns green
- exit: open

## Next act
the gate, then the range scan
