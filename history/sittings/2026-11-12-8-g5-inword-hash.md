# Sitting 2026-11-12-8: agentik-session, g5 an in-word `#` no longer hides a write; g6 its loose second reading

| item | value |
|---|---|
| goal | brief g5, S1, phases 1 to 1d (round 3's R3-F1 to F7); build 2: brief g6 R1 to R8 with the coordinator's amendments; build 3: the fix of review 1 (R1 to R10); packet `design/packets/g5-inword-hash.md` (§3c, §3d) |
| budget | builder: about 90 tool calls per build |
| pin | 8153e52 on main (alpha.91); phase 1d from f1f012e; g6 from a0055da; worktree `.claude/worktrees/g5-inword-hash`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] phases 1 to 1d, at a0055da: `_mask` alone decides a comment; rounds 1 to 3 fixed (packet §3a to §3c); 341 guard tests green under both venvs; fuzz 2 x 100k vs four commits clean
- [x] g6 packet §3d with a0055da's baseline (a556120)
- [x] g6 R4 to R6 (018e702): `_WRITE_WORD` on the joined text; reserved words skipped as a wrapper; an inner `-c` that cannot be split gives the `split` mark
- [x] g6 R1 to R3: `loose_targets` (pure), `_strict` names each target's word and folder, `_loose_gated` accounts by path, the loose folder moves only on a plain prefix; its own reason, `why` in `guard.jsonl`; 441 guard tests green under both venvs; round 3's 27 lines and g6's 41 at six commits: every write denied, REGRESS 0
- [x] tests moved: nine lines a0055da passed with an `open` line (an open quote, `cd $X`, `popd`, `cd -`, a stray `)`, a trailing `\`, `echo '>> CLAUDE.md'`) are now the loose reading's; with it off they pass as at a0055da (a test)
- [x] g6 R8 records: head comment's g6 paragraph, RUNBOOK, NICE (n131, n132, n138, n161 closed; n162 S3, n163 S4); a0055da's 341 guard tests pass at the head with the loose reading off; 14 other files that read the guard or records: 690 passed (.venv)
- [x] g6 checks: round 3's 27 lines at six commits, every write denied, REGRESS 0; fuzz 100k tokens (seed 9802) and 100k valid (seed 9902) vs 8153e52, d2f89d9, 40aee95, f1f012e, a0055da, a stub `cp` that prints nothing: REGRESS-with-a-shell 0 and 0; the replay of 415,408 lines: 72 newly refused, all by the loose reading, none a read or a `git add` (56 text the strict reading does not read as a write, 12 by the amendment's (b), 4 by its (a)): over the brief's 60 by the amendment's 16
- [x] build 3 R1 (review 1's F3): a `cd`, `pushd` or `popd` behind a reserved word adds a folder state and replaces none; the first state moves as a0055da's, one follows every `cd` as db19d51's; at most 16; a test builds 392 lines from 13 prefixes (and none) and 28 writes a0055da denies: with the loose reading off, every one denied
- [x] build 3 R2 (F1): `then`, `do`, `else`, `elif`, `if`, `while`, `until`, `{`, `!` are skipped only as a command's first words, in both readings; after an assignment or a wrapper each is a word; F1's 12 lines denied by the strict reading, neither reading follows their `cd`
- [x] build 3 R3 (F2): a strict word stands for a loose target only whole: a word with a blank stands for the loose targets only where one command lists every piece of it in order, each once (the reviewer's "never by its pieces" alone denied g6's ordinary `sed -i '' 's/the CLAUDE.md file/x/' notes.md`); F2's four lines denied by the strict reading (R1), review 1's lead 2 (two lines, no R5 word) now denied by the loose reading
- [x] build 3 R4 (F4): each `cd` of the loose reading resolved once, each loose target once, targets left times folders at most 4,096, past it the line is denied with the loose reading's refusal (naming its first target); `(?<!\d)\d*`; F4's shapes: 6 KB 7.76 s to 0.02 s, 20 KB of digits 3.78 s to 0.03 s, the `if` line 8.70 s to 0.01 s (denied), 100 KB over 25 s to 0.18 s
- [ ] build 3 R5 (F5), then the records (§3e, NICE)
- [ ] phase 2, on the coordinator's word

## Handover
- The pin differs from the brief: `echo a\#b; cp a CLAUDE.md` already gave the write.
- NICE id n161: main holds n148, land2 n150, mt1 n159, u3 n160; renumber at merge if one passes it.
- Named `-8`: u3's branch holds `2026-11-12-7-u3-loop-lines.md`.
- decide, owner: the coordinator: acceptance 5's bound of 60 against the amendment's (a) and (b), which add 16 (72 in all); consumer: the review and phase 2.

## Next act
- Build 3 goes on at the next unticked ruling, R2 to R5 then the records, each with its tests.
- The review over the whole slice from 8153e52 with both readings on, then phase 2 on the coordinator's word.

## Exit
g6 build 2 landed in phase 1 (R1 to R8, the records, the checks); waits on the coordinator.
