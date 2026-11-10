# Sitting 2026-11-10-6: agentik-session, wfg (the Workflow guard and R6)

| item | value |
|---|---|
| goal | build packet wfg: `workflowguard.py`, the PreToolUse rule for `SPAWNING_TOOLS` (R1 to R8), R6's `model.json` with PostModelSwitch registered, R9's docs |
| budget | builder: 200k window, 180k context, about 90 tool calls (packet: 60 calls, 120k); doclint's five rows |
| pin | bfc66ae (alpha.63) on `wfg-workflow-guard` in `.claude/worktrees/wfg-workflow-guard` |
| window | 200k |
| agents | 0 |

## Done-ness
- [ ] the packet as `design/packets/wfg-workflow-guard.md` (sections renamed for doclint only) and this charter
- [ ] tests first: `tests/test_wfg.py`, `tests/fixtures/wfg/*.js`; the red count at bfc66ae
- [ ] the guard: `workflowguard.py`, `hooks.py`, `hooks.json`, `hooks/run`; test_doctor, test_precompact event lists
- [ ] green under 3.12 and 3.9.6; the hook's cost on 100 KB
- [ ] version, docs (SKILL, RUNBOOK, README status line), NICE from n58
- [ ] the gate once; the range scan

## Handover
- Rulings (the coordinator): Q1 the ceiling 8; Q2 Fable in a workflow only under a Fable session, labelled design or refutation, two at most; Q3 and Q4 not in this packet; deny, never rewrite input; R6 as written
- exit: open

## Next act
the tests, then the guard
