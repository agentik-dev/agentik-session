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
- [x] act 3: R2 to R4: the part, `open`'s line, the four warnings; acceptance 6 green; four tests of `test_charter.py` that pin `open`'s text take the part
- [x] act 4: R5 to R8: `show`, its object and its text view; acceptance 1 to 8 and 10 green
- [x] act 5: R9: the hook's read and the denial's sentence; acceptance 9 green; `test_n33.py`'s `VERB_FIRST` takes the new sentence
- [x] act 6: R10: the docstring, the parser's help, the skill's "The charter", the RUNBOOK's charter paragraphs and helper sentence, NICE n191 (24,532 B); recordlint and doclint exit 0
- [x] acceptance 11: the five files 296 passed under `.venv` and under `.venv-floor`; the tests that read the skill, the RUNBOOK or the charter (753) green under both but the docs case, fixed after

## Handover
- open by level: none yet
- Phase 2 waits on the coordinator's word: main merged, the version, NICE n191 renumbered past main's highest.

## Waits on the owner
- none

## While waiting
- none

## Next act
- None for this builder: phase 2 is the coordinator's word.
