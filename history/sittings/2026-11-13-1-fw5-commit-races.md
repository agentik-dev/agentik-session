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
- [x] R1 and R2 (commit.py; the core split as `_core`, `commit_paths` for R3); test_fw4d changed for R2: the three round-2 tests (another writer's commit, staging, SIGTERM: the plain `red check` line or none) and the two r1_f3 tests (the restore that cannot be made now reached by a red commit holding index.lock)
- [x] R3 (cli.py `cmd_checkpoint`, the parser's `paths`); test_cli changed for R3: `test_checkpoint_help_names_tracked_only` and `test_checkpoint_commit_stages_tracked_only` (renamed for the paths), and four respawn tests that ran `-c` with no path (s19's helper refusal and its control, s22's tracked and untracked charter) now name their paths
- [ ] R4 (commit.py `_gate_check`, gate.py runner)
- [ ] R5 (cli.py `cmd_gate`)
- [ ] docs (README, RUNBOOK, SKILL.md, the checkpoint command, help) and the four NICE rows out

## Handover
- Choice: a modified tracked charter passes `--respawn` with `--commit` only when the line names it (or a directory over it); before, `-c` took it by its sweep.
- decide, owner: none.

## Next act
- R4.

## Exit
- (open)
