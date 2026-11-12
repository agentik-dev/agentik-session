# Sitting 2026-11-12-4: agentik-session, g2b the edit gates

| item | value |
|---|---|
| goal | packet g2b (`design/packets/g2b-edit-gates.md`): the guard rewritten as edit gates (lists, deny in every mode), g3 on Bash, `gates` and `gates write`, the doctor's row; plugin 2.0.0-alpha.83 |
| budget | builder: about 90 tool calls |
| pin | 054cfc5 on `g2-instruction-guard`; worktree `.claude/worktrees/g2b-edit-gates`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet committed
- [ ] tests first, red at the pin
- [ ] acceptance 1, 2, 4, 5 (Edit tools, matching, no spawn, fail open)
- [ ] acceptance 3 (g3 on Bash)
- [ ] acceptance 6 (`gates write`) and the doctor's row
- [ ] records (README, RUNBOOK), the gate's `make check`

## Handover
- decide, owner: none yet

## Next act
tests first

- exit taken: (open)
