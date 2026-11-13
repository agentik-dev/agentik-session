# Sitting 2026-11-13-1: agentik-session, pl1 the prompt line tidied

| item | value |
|---|---|
| goal | packet pl1 phase 1 (`design/packets/pl1-prompt-line.md`): R1 to R7 built, R8's tests green under both venvs; no bump, no merge, no gate job |
| budget | builder: about 90 tool calls |
| pin | 8a4b593 on main (2.0.0-alpha.93); worktree `.claude/worktrees/pl1-prompt-line`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] act 1: the packet, with the baseline measured at the pin
- [ ] act 2: R1, R2, R6: the line's words (`admission.py`, `session.ts`), the fixtures, `tests/test_pl1_prompt_line.py`
- [ ] act 3: R3: `status` shows the mix, the next family, the band, the mode; `--json` new keys
- [ ] act 4: R4: the pacing text points at `agentik session status`
- [ ] act 5: R5, R7: RUNBOOK, SKILL, README source

## Handover
- Phase 2 (bump, gate job, merge) waits on the coordinator's word.

## Next act
- act 2.

## Exit
- (open)
