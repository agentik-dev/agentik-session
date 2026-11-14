# Sitting 2026-11-13-6: agentik-session, g8a the reader's new parts, one walk of a line's commands

| item | value |
|---|---|
| goal | brief g8a phase 1 (packet `design/packets/g8a-reader-parts.md`): R1 to R13; then the fix round on the coordinator's ruling: (a) acceptance 6 narrowed, (b) three early returns, (c) `Unread` kinds `runner` and `data`, (d) the three flips kept, E1; the fix of review 1 (R1-F1 to F7, N1); the fix of review 2 (R2-F1, R2-F2 in `_braces`) |
| budget | builder: about 90 tool calls a round (review 2's fix: from b8797f6) |
| pin | b92e4e0 on main (2.0.0-alpha.103); build 1 at 9b2c48c; worktree `.claude/worktrees/g8a-reader-parts`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Build 1 (R1 to R13, 9b2c48c); fix of the read (a) to (d), E1, E2; replay and acceptance tables at the head
- [x] Review 1's fix (d1fa778 red): F1 to F7 and N1 built; test 13 holds (a); grid 190 and replay rerun
- [x] Phase 2: main e147e06 merged (n204 is n239), the allow row for e28379e, stamped 2.0.0-alpha.111, gate green
- [x] Review 2's fix: tests red at b8797f6 in 2600b3b (F1 22.6, 14.9, 11.7 CPU s; F2 64 MB; answers as b8797f6's `_braces`)
- [x] R2-F1 one scan of the word's pairs (`_brace_pairs`), no regex; R2-F2 alternatives built one at a time, the cap met first; 727 passed in each venv; 260,000 fuzz words answer as b8797f6
- [x] The stamp at alpha.111 again: 4473 tests (README and source Status lines, sidecar; plugin.json unchanged)
- [ ] The gate once, last; the scans

## Handover
- decide, owner: coordinator. The ruling keeps 2.0.0-alpha.111, but `scripts/plugin-version-check` fails any change under plugin/ after the commit that set the version (b8797f6), so it exits 1 on `unattended.py` and the gate is red there until the version moves. Recommended: 2.0.0-alpha.112 by `scripts/stamp --version 2.0.0-alpha.112` (alpha.111 never reached main), merge.txt's last line to match, one gate. Consumer: the next builder and the landing.
- Review 1: a glued parameter (`${u}make check`, any level) passes, as at the pin (n197's class). N1's sink list is closed (`cat` to a file, `tee`, `git commit -F -`): it returns 2 replay lines; a `cd` before a sink keeps the refusal.
- The make rule's class C (a tool's own option holds the make line, 18 replay lines, NICE n239) and a shell's name in a variable (NICE n197) pass, as at the pin. A Python body that shells out a make is refused now, as `data`.
- Not rerun this round: acceptance 7 by the brief's classes, 10 (real shells, 20,000 lines), 11's launcher cold runs.

## Next act
- Review 2's fix (above), then the coordinator's read and the landing.

## Exit
- Review 1's fix: committed act by act; the gate's job last.
- Fix of the read committed: (a) to (d), E1, E2 built; the gate's job queued last; phase 2 (merge of main, version) on the coordinator's word.
