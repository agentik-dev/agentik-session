# Sitting 2026-11-12-8: agentik-session, g5 an in-word `#` no longer hides a write; g6 its loose second reading

| item | value |
|---|---|
| goal | brief g5, S1, phases 1 to 1d (round 3's R3-F1 to F7); build 2: brief g6 R1 to R8 with the coordinator's amendments; build 3: review 1's fix; build 4: review 2's fix (R1 to R10); packet `design/packets/g5-inword-hash.md` (§3c to §3f) |
| budget | builder: about 90 tool calls per build |
| pin | 8153e52 on main (alpha.91); phase 1d from f1f012e; g6 from a0055da; worktree `.claude/worktrees/g5-inword-hash`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] phases 1 to 1d, at a0055da: `_mask` alone decides a comment; rounds 1 to 3 fixed (packet §3a to §3c); 341 guard tests green under both venvs; fuzz 2 x 100k vs four commits clean
- [x] g6 packet §3d with a0055da's baseline (a556120)
- [x] g6 R4 to R6 (018e702)
- [x] g6 R1 to R3: `loose_targets` (pure), `_strict` names each target's word and folder, `_loose_gated` accounts by path, the loose folder moves only on a plain prefix; its own reason, `why` in `guard.jsonl`; 441 guard tests green under both venvs; round 3's 27 lines and g6's 41 at six commits: every write denied, REGRESS 0
- [x] tests moved: nine lines a0055da passed with an `open` line (an open quote, `cd $X`, `popd`, `cd -`, a stray `)`, a trailing `\`, `echo '>> CLAUDE.md'`) are now the loose reading's; with it off they pass as at a0055da (a test)
- [x] g6 R8 records: head comment's g6 paragraph, RUNBOOK, NICE (n131, n132, n138, n161 closed; n162 S3, n163 S4); a0055da's 341 guard tests pass at the head with the loose reading off; 14 other files that read the guard or records: 690 passed (.venv)
- [x] g6 checks: round 3's 27 lines at six commits, every write denied, REGRESS 0; fuzz 100k tokens (seed 9802) and 100k valid (seed 9902) vs 8153e52, d2f89d9, 40aee95, f1f012e, a0055da, a stub `cp` that prints nothing: REGRESS-with-a-shell 0 and 0; the replay of 415,408 lines: 72 newly refused, all by the loose reading, none a read or a `git add` (56 text the strict reading does not read as a write, 12 by the amendment's (b), 4 by its (a)): over the brief's 60 by the amendment's 16
- [x] build 3 (review 1's fix, packet §3e): R1 a `cd` behind a reserved word adds a folder state (at most 16); R2 a reserved word only first; R3 a blank word stands only whole; R4 loose time bounded (4,096 pairs); R5 `>&`; 491 guard tests green, both venvs
- [x] build 3 checks vs the six commits: sweeps, hand lines, round 3's and g6's lines REGRESS 0; fuzz 2 x 100k (seeds 80611, 80612) REGRESS 0; loose off vs a0055da 80k lines: 0 deny to pass; replay 72 newly refused, the same 72; NICE n164 to n166
- [x] build 4 R1 (F5, cf603ae): strict bound 65,536 judgements, 4,096 paths; a `-c` line split once
- [x] build 4 R2 (F1): loose skips a reserved word anywhere (db19d51); strict lets `time -p` in the run
- [x] build 4 R3 (F2): loose splits at an `&` whose `<` or `>` is escaped (the second form)
- [ ] build 4 R4, R5 (F3, F4): each mend back to db19d51's reading
- [ ] build 4 records: packet §3f, NICE rows for review 2's leads and F6
- [ ] phase 2, on the coordinator's word

## Handover
- Build 3: recordlint's long n162 and n163 rows and doclint's packet section names (4 to 6) were red at db19d51 already; left for phase 2.
- The pin differs from the brief: `echo a\#b; cp a CLAUDE.md` already gave the write.
- NICE id n161: main holds n148, land2 n150, mt1 n159, u3 n160; renumber at merge if one passes it.
- Named `-8`: u3's branch holds `2026-11-12-7-u3-loop-lines.md`.
- decide, owner: the coordinator: acceptance 5's bound of 60 against the amendment's (a) and (b), which add 16 (72 in all); consumer: the review and phase 2.

## Next act
- Build 4: R1, then R2 to R5, each a commit with its tests, then the records.

## Exit
Build 4 open: review 2's fix in flight.
