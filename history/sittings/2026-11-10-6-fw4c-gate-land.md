# Sitting 2026-11-10-6: agentik-session, gate land (FW4c)

| item | value |
|---|---|
| goal | packet FW4c (`design/packets/fw4c-gate-land.md`): R1 to R6, `gate land` and `land.py`, the job mark and its two doors |
| budget | builder: 200k window, 120k context, 60 tool calls (the packet's); one commit per group |
| pin | 36c84ea (R1 landed, alpha.60); branch `fw4c-gate-land` in `.claude/worktrees/fw4c-gate-land` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [ ] the packet committed with this charter
- [ ] tests: T1 to T13 in `tests/test_fw4c.py`, red at 36c84ea
- [ ] the verb: R1 to R5 (land.py, the mark, the doors, self_argv), the ported pair, test_gate's one assertion
- [ ] the texts and the bump: R6, NICE rows, the version, the status line, the sidecar
- [ ] verify: one gate run of `make check`

## Handover
- open by level: none yet

## While waiting
- none

## Next act
the packet and this charter, one commit
