# Sitting 2026-11-13-1: agentik-session, dw1s the install writes the `agentik` door forward only

| item | value |
|---|---|
| goal | packet dw1s phase 1 (`design/packets/dw1s-door-writer.md`): R1 to R6 built, R7's three test files green under both venvs; no bump, no gate job |
| budget | builder: about 90 tool calls |
| pin | 8a4b593 on main (alpha.93); worktree `.claude/worktrees/dw1s-door-writer`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Baseline at the pin: test_install.py + test_bare_machine.py, .venv 157 passed; .venv-floor 154 passed, 3 skipped
- [x] Act 1: the packet
- [ ] Act 2: the failing tests (`tests/test_dw1_door.py`)
- [ ] Act 3: R1 to R5 in `install.py`; R6 the records
- [ ] R7 proofs under both venvs

## Handover
- Phase 2 (bump, gate job) waits on the coordinator's word.

## Next act
- Act 2: write `tests/test_dw1_door.py`, red at the pin.

## Exit
- (open)
