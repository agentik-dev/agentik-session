# Sitting 2026-11-13-6: agentik-session, g8a the reader's new parts, one walk of a line's commands

| item | value |
|---|---|
| goal | brief g8a phase 1 (packet `design/packets/g8a-reader-parts.md`): R1 to R13; then the fix round on the coordinator's ruling: (a) acceptance 6 narrowed, (b) three early returns, (c) `Unread` kinds `runner` and `data`, (d) the three flips kept, E1; then the fix of review 1 (R1-F1 to F7, N1, a test for (a)) |
| budget | builder: about 90 tool calls a round |
| pin | b92e4e0 on main (2.0.0-alpha.103); build 1 at 9b2c48c; worktree `.claude/worktrees/g8a-reader-parts`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Build 1: R1 to R13 built, five commits to 9b2c48c (acceptance 11 red in process; one decide line, since ruled)
- [x] Fix (a): acceptance 6 narrowed in the packet; with the pin's `_git_paths` put back 0 differ (git fuzz, builder's fuzz, tests, packets, replay); as built 11,611 and 32,574 fuzz lines, each with one of the four
- [x] Fix (c), E1 (4eda8ac, tests 1ed9caa red: 53 fail): replay class A 151 of 151 and class B 26 of 26 refused; refused 3,037; the 20 make lines and 7 Python bodies read; `runner` (a shell's `-c` text behind a command that is no wrapper) and `data` (a heredoc body not read as a script); a command word's substitutions read as empty for its name
- [x] Fix (b): three early returns; 0 answers changed against 4eda8ac over tests, packets, replay, 200,000 fuzz; hand lines 4.86 to 4.99 s against the pin's 5.36 (0.91 to 0.93)
- [x] Fix (d): the three flips kept (packet acceptance 8); E2 into NICE n180; n197 gains `$sh -c`; n204 class C
- [x] The replay counts and the acceptance table at the head (make rule: replay 3,037 refused, packets 13 and 13; gate flips 0 on the replay; acceptance 2 to 5, 12, 13 green both venvs); the gate job 20261113-112930-1563 queued on this commit

- [x] Review 1's fix: tests red at 831110a (d1fa778, section 12: 41 fail, 8 pass)
- [x] F3 `$((` arithmetic only with its `))` adjacent; F4 `_subst`'s arithmetic nest bounded, RecursionError read as `_Bound` in `commands` and `_strict`; F2 `$__g8_out` out of the command word
- [x] F1: an unread text read as a shell spells it: the walk (to `_NEST` texts deep) and a split with `\`-NL, `\` and quotes off
- [ ] Review 1's fix, left: F1; F7; F5, F6; N1; the (a) test; the reruns; the gate once, last

## Handover
- The make rule's class C (a tool's own option holds the make line, 18 replay lines, NICE n204) and a shell's name in a variable (NICE n197) pass, as at the pin. A Python body that shells out a make is refused now, as `data`.
- Not rerun this round: acceptance 7 by the brief's classes, 10 (real shells, 20,000 lines), 11's launcher cold runs.

## Next act
- Review 1's fix, act by act as listed; then the gate job once, last; phase 2 on the coordinator's word.

## Exit
- Review 1's fix: in flight.
- Fix of the read committed: (a) to (d), E1, E2 built; the gate's job queued last; phase 2 (merge of main, version) on the coordinator's word.
