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
- [x] Act 2: the failing tests (`tests/test_dw1_door.py`): at the pin 11 failed, 2 passed (acceptance 3 holds) under both venvs
- [x] Act 3: R1 to R5 in `install.py` (`_door`, its line first in `pruned`); R6 in `RUNBOOK.md` and `install-cli.md`; the README source unchanged
- [x] R7 proofs: the three files, .venv 170 passed; .venv-floor 167 passed, 3 skipped; test_install.py and test_bare_machine.py unchanged; compileall, scripts/doclint, scripts/hygiene exit 0
- [x] Fix 1, tests: review 1's F1 (a FIFO at the door) and F2 (a 0xff byte, UTF-8 locale) in `tests/test_dw1_door.py`, red at 8636055 under both venvs (a hang; a traceback, exit 1)
- [ ] Fix 1, the change: `_door` opens only a regular file; the line's values escaped
- [ ] Fix 1, records: the packet's review 1 section; the R7 proofs again

## Handover
- Phase 2 (bump, gate job) waits on the coordinator's word.
- Phase 2 renders the README: its status line counts 3432 tests and the suite now collects 3445 (13 new); `test_readme.py`'s status-line test is red until then.

## Next act
- Fix 1: the change in `install._door`, then the packet's section.

## Exit
- Phase 1 built and proven; review 1's fix in flight.
