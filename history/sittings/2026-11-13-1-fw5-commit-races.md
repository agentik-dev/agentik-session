# Sitting 2026-11-13-1: agentik-session, fw5 commit, checkpoint and the gate under several writers

| item | value |
|---|---|
| goal | packet fw5 (`design/packets/fw5-commit-races.md`): R1 witness index, R2 what stands, R3 `checkpoint --commit <paths...>`, R4 a cut wait cancels its job, R5 no wait on the job's own key; phase 1 ends at the commits |
| budget | builder: about 90 tool calls |
| pin | f1cbccd on main (alpha.94); worktree `.claude/worktrees/fw5-commit-races`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the pin measured by `tests/test_fw5.py` (15 failed, 3 passed at f1cbccd)
- [x] the packet
- [x] tests first committed (red at f1cbccd: 15 failed, 3 passed)
- [ ] R1 and R2 (commit.py), test_fw4d's round-2 tests changed for R2
- [ ] R3 (cli.py checkpoint), test_cli's checkpoint `-c` tests changed
- [ ] R4 (commit.py `_gate_check`, gate.py runner)
- [ ] R5 (cli.py `cmd_gate`)
- [ ] docs (README, RUNBOOK, SKILL.md, the checkpoint command, help) and the four NICE rows out

## Handover
- decide, owner: none.

## Next act
- R1 and R2.

## Exit
- (open)
