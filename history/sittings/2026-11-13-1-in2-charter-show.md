# Sitting 2026-11-13-1: agentik-session, in2 charter show and the Waits part

| item | value |
|---|---|
| goal | packet in2 phase 1 (`design/packets/in2-charter-show.md`): R1 to R10 built, acceptance 11 green under both venvs; no bump, no merge, no gate job |
| budget | builder: about 90 tool calls |
| pin | 148fde3 on main (2.0.0-alpha.98); worktree `.claude/worktrees/in2-charter-show`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] act 1: the packet and this charter
- [x] act 2: the failing tests, measured red at the pin (13 failed of 13 under .venv)
- [x] act 3: R2 to R4: the part, `open`'s line, the four warnings; acceptance 6 green; four tests of `test_charter.py` that pin `open`'s text take the part (close_appends_one_line, s21_open_seeds_the_handover_line, s21_open_seeds_nothing_with_priority_off, s40_open_writes_the_section)
- [ ] act 4: R5 to R8: `show`, its object and its text view
- [ ] act 5: R9: the hook's read and the denial's sentence
- [ ] act 6: R10: the records and one NICE row; both venvs green

## Handover
- open by level: none yet

## Waits on the owner
- none

## While waiting
- none

## Next act
Act 4: `show` in `charter.py` and `cli.py`.
