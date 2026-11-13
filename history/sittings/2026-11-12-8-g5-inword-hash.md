# Sitting 2026-11-12-8: agentik-session, g5 an in-word `#` no longer hides a write; g6 its loose second reading

| item | value |
|---|---|
| goal | brief g5, S1, phases 1 to 1d (round 3's R3-F1 to F7); build 2: brief g6 R1 to R8 with the coordinator's amendments; packet `design/packets/g5-inword-hash.md` (§3c, §3d) |
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
- [ ] g6 checks: round 3's command, 2 x 100k fuzz vs five commits, the replay
- [ ] phase 2, on the coordinator's word

## Handover
- The pin differs from the brief: `echo a\#b; cp a CLAUDE.md` already gave the write.
- NICE id n161: main holds n148, land2 n150, mt1 n159, u3 n160; renumber at merge if one passes it.
- Named `-8`: u3's branch holds `2026-11-12-7-u3-loop-lines.md`.

## Next act
- g6 R1 to R3 on this branch, then R8's records and the checks.

## Exit
Open: g6 build 2 in flight.
