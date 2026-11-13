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
- [x] Fix (a): acceptance 6 narrowed; 0 differ with the pin's `_git_paths` put back
- [x] Fix (c), E1 (4eda8ac; tests 1ed9caa red): `Unread` kinds `runner` and `data`; class A 151 and B 26 refused; a command word's substitutions read as empty
- [x] Fix (b): three early returns, 0 answers changed; 0.91 to 0.93 times the pin
- [x] Fix (d): the three flips kept (packet acceptance 8); E2 into NICE n180; n197 gains `$sh -c`; n204 class C
- [x] The replay counts and the acceptance table at the head (make rule: replay 3,037 refused, packets 13 and 13; gate flips 0 on the replay; acceptance 2 to 5, 12, 13 green both venvs); the gate job 20261113-112930-1563 queued on this commit

- [x] Review 1's fix: tests red at 831110a (d1fa778, section 12: 41 fail, 8 pass)
- [x] F3 `$((` arithmetic only with its `))` adjacent; F4 `_subst`'s arithmetic nest bounded, RecursionError read as `_Bound` in `commands` and `_strict`; F2 `$__g8_out` out of the command word
- [x] F1: an unread text read as a shell spells it: the walk (to `_NEST` texts deep) and a split with `\`-NL, `\` and quotes off
- [x] F7: a here-string's word is `data` unless a shell reads it as its script (`piped`); a pipe into a runner's shell is `piped`
- [x] F5 built (the rule's word test expands braces, bounded); F6 built (an `alias` value is an `eval` text)
- [x] N1: a body's refusal says what is true and the way out; a line of data sinks only (`cat` to a file, `tee`, `git commit -F -`) passes its bodies
- [x] (a) in the tree: test 13 loads the pin's reader from git and finds 0 loose lines differ with its `_git_paths` put back (6,000 fuzz and the hand shapes)
- [x] F1 kept whole (06a225d): build 2's split beside the one with the quotes off (the grid's battery 5 found `["make", "check"]` lost)
- [x] Reruns: grid 190, 0 refused at the pin and passed here, 19 pass (all `${u}make`, held); replay class A 151 of 151, class B 26 of 26, refused 3,036, gate deny to pass 0; acceptance 2 to 5, 12 green
- [ ] The gate once, last F1; F7; F5, F6; N1; the (a) test; the reruns; the gate once, last

## Handover
- Review 1: a glued parameter (`${u}make check`, any level) passes, as at the pin (n197's class). N1's sink list is closed (`cat` to a file, `tee`, `git commit -F -`): it returns 2 replay lines; a `cd` before a sink keeps the refusal.
- The make rule's class C (a tool's own option holds the make line, 18 replay lines, NICE n204) and a shell's name in a variable (NICE n197) pass, as at the pin. A Python body that shells out a make is refused now, as `data`.
- Not rerun this round: acceptance 7 by the brief's classes, 10 (real shells, 20,000 lines), 11's launcher cold runs.

## Next act
- The gate job once, last; phase 2 on the coordinator's word.

## Exit
- Review 1's fix: committed act by act; the gate's job last.
- Fix of the read committed: (a) to (d), E1, E2 built; the gate's job queued last; phase 2 (merge of main, version) on the coordinator's word.
