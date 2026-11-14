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
- [x] act 6: R10: the docstring, the parser's help, the skill's "The charter", the RUNBOOK's charter paragraphs and helper sentence, NICE n191, n204 since phase 2 (24,532 B); recordlint, doclint (the packet trimmed to 9,179 B of 9,216) and hygiene exit 0; the built `check` passes this charter, exit 0
- [x] acceptance 11: the five files 296 passed under `.venv` and under `.venv-floor`; the tests that read the skill, the RUNBOOK or the charter (753) green under both but the docs case, fixed after
- [x] review 1's fix (build 2): tests c0c8bf6 (9 red at f99ec37; the hook's five chained payloads already denied); F1 e84c814, L2 5f8e07d, F2 85c8930, each green after; NICE n192 to n195 (n205 to n208 since phase 2), with n130, n133 and n134 moved to the overflow for recordlint's cap; the five files 313 passed under each venv
- [x] phase 2: main b92e4e0 merged (253f5f8, only `NICE_TO_HAVE.md` in conflict); the three files 222 passed and the tests that read the merged docs plus u3, h4, fw5 868 passed, each venv; recordlint, doclint, hygiene exit 0; the version alpha.104 and 4045 tests (the next commit)

## Handover
- open by level: none yet
- Phase 2 done: main b92e4e0 merged (253f5f8; NICE resolved by hand, n191 to n195 renumbered n204 to n208, n135 moved to the overflow, the packet follows), plugin 2.0.0-alpha.104 alone last under `plugin/`, 4045 tests; nothing pushed, landed or installed, no gate job: the landing's check is the one check.

## Waits on the owner
- none

## While waiting
- none

## Next act
- None for this builder: the landing.
