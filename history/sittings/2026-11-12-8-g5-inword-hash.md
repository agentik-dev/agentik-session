# Sitting 2026-11-12-8: agentik-session, g5 an in-word `#` no longer hides a write from the guard

| item | value |
|---|---|
| goal | brief g5, S1: R1 to R3, phase 1; 1b: round 1's F1 to F4; 1c: round 2's R2-F1 to F4; 1d: round 3's R3-F1 to F7 (rulings R1 to R11); packet `design/packets/g5-inword-hash.md` |
| budget | builder: about 90 tool calls per phase |
| pin | 8153e52 on main (alpha.91); phase 1d from f1f012e; worktree `.claude/worktrees/g5-inword-hash`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] phases 1 to 1c, at f1f012e: `_mask` alone decides a comment; round 1's F1 to F4 (cc4a20a), F5 NICE n161; round 2's four and bash 3.2's reading of `${` in `$(` (faf70cb); the packet's §3a, §3b
- [x] phase 1d measurement: g6's loose prototype lists `CLAUDE.md` on every R3-F line and lead; its accounting passes F1b, F1c (round 3's b, c) and leads 2, 4, where the strict reading read the word in another folder or none
- [x] 1d R1 (R3-F1): `_commands` reads a `case` glued to its opening backtick and (a choice) an `esac` glued to its closing one; R8: the unmasked `)` as proposed passed a line f1f012e denied and zsh writes (a `cd` in a case body in backticks), so the first reading masks it again (c4f6d7d); then, as bash3 left a write in a `${` in a `$(` unread, a third reading that masks no pattern `)` in backticks joins the union, and an escaped or quoted backtick is masked so `_commands` takes no `\`case` for a glued one
- [x] 1d R2 (R3-F2): a backtick opened in a `${` goes on `opened` till it closes (a `)` there pops nothing); fuzz 40k: no line head denied and a shell writes passes
- [x] 1d R3 (R3-F3): the bash3 reading counts no `case`, taken whenever its mask differs
- [x] 1d R4 (R3-F4): a comment in backticks ends at the first backtick, escaped or not, read again from the backslashes before it; F4 without `; echo b`: `[]` at f1f012e, `[(write, None)]` after R4
- [x] 1d R5 (R3-F5): `_KEY` takes a backslash-newline after `case`
- [ ] 1d R6 (R3-F6 a): backticks stripped from a target word's ends
- [ ] 1d R7 (R3-F7): a comment's end searched to its newline only
- [ ] 1d: packet §3c, this record; three guard files green under `.venv`, `.venv-floor`
- [ ] phase 2, on the coordinator's word, after g6's loose reading on this branch

## Handover
- The pin differs from the brief: `echo a\#b; cp a CLAUDE.md` already gave the write.
- NICE id n161: main holds n148, land2 n150, mt1 n159, u3 n160; renumber at merge if one passes it.
- Named `-8`: u3's branch holds `2026-11-12-7-u3-loop-lines.md`.

## Next act
- Phase 1d's rulings in order R1 to R7, each with its tests; then §3c.

## Exit
(open)
