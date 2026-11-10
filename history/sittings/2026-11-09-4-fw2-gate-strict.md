# Sitting 2026-11-09-4: agentik-session, the gate's --strict, head and est (FW2)

| item | value |
|---|---|
| goal | packet FW2 (`design/packets/fw2-gate-strict.md`): R1 to R7, `gate wait --strict`, the result's head and key, the est; alpha.55 |
| budget | builder: 200k window, 120k context, 80 tool calls; one commit per group |
| pin | 942cace (FW1a landed, alpha.54); branch `fw2-gate-strict` in `.claude/worktrees/fw2-gate-strict` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [x] the packet committed with this charter
- [ ] tests: T1 to T8 in `tests/test_fw2.py`, red at 942cace
- [ ] the code: R1 to R5
- [ ] the texts: R6
- [ ] the bump: R7, alpha.55; NICE row
- [ ] verify: the gate once

## Handover
- open by level: none yet
- decide, owner: the coordinator: R6 asks `cmd_gate`'s docstring to cite the house configuration repo by name, which the public scan's private group refuses; the docstring names the agentik guide's rule "exit codes report the task, not the content" instead, and the packet's copy names the ledger without the repo's name.

## While waiting
- none

## Next act
the tests: add `tests/test_fw2.py` and record its red at 942cace
