# Sitting 2026-11-14-11: agentik-session, ak10d-session-launcher, first build

| item | value |
|---|---|
| goal | hq NICE n22: commons' `uninstall` takes session's launcher, its trees and `akt` back; session's `LAUNCHER` line 2 is the canonical's for `agentik-session`, the old-name note on line 3 |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `3eb81dd` (2.0.0-alpha.126) |
| branch | `ak10d-session-launcher`, worktree `.claude/worktrees/ak10d-session-launcher`, the two venvs linked |
| level | S3, a small change (entry 17): no packet file |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] (1) R1 the form, R3 the tests, R2 the proof: `install.py` lines 2 and 3; `test_akt_6` at its full assertion (dbcfb9d's branch reverted); `tests/test_ak10d_launcher.py` (3): the canonical's dry plan and real uninstall of a fresh install, the old form's reads and its refresh. The four: 4 failed at the pin's `install.py`, 4 passed now; the install suites (8 files) 398 passed under `.venv`
- [x] (2) R5: `NICE_TO_HAVE.md` row n270 (the switch to the canonical module, and its old-name rule); n211, its first S4 row, moved byte for byte to `history/NICE-overflow.md` as the stamp's `nice_moves` does, so recordlint's size bound holds; `scripts/doclint` and `scripts/recordlint` exit 0
- [x] (3) R4: `make check` once through the gate on `ad60b71`: job `20261115-000432-2059`, exit 2 in 13 min, red on the README's count alone (`test_readme.py::test_status_line_matches_manifest_and_suite` [readme], [source]: 4828 == 4831, the three new tests), the stamp's; 4829 passed. `make` stopped at `test`, so the floor run and the later targets did not run in the gate; by hand: the install suites (8 files) 395 passed, 3 skipped under `.venv-floor`, doclint and recordlint 0. `scripts/hygiene --require-private --commits main..HEAD` exit 0 (2 commits)

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
None: every ruling is built; the review's and the landing's.

## Exit
First build handed back: the change at `ad60b71`, its check red on the README's count alone (the stamp's); this commit holds this file alone.
