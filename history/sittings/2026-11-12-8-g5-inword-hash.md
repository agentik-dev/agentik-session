# Sitting 2026-11-12-8: agentik-session, g5 an in-word `#` no longer hides a write from the guard

| item | value |
|---|---|
| goal | brief g5 (hq `history/sessions/BRIEF-2026-11-12-session-g5-inword-hash.md`), S1: R1 to R3 built, R4 phase 1 only |
| budget | builder: about 90 tool calls |
| pin | 8153e52 on main (alpha.91); worktree `.claude/worktrees/g5-inword-hash`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] tests first: 7 of 16 g5 cases red at the pin (`tests/test_g2b_gates.py`, section g5)
- [x] R1, R2: `_mask` drops a comment (a `#` at a word's start, outside quotes) up to its newline; `_commands` sets `commenters = ""`, so `shlex` never decides a comment
- [x] R3 survey: `shlex.split` in `commit.py`, `install.py`, `agentik_install.py` splits with `comments=False` (no commenter) and refuses no shell line: no other site shares the cause
- [x] phase 1: `test_g2b_gates.py` and `test_g4_folder_gates.py` green under `.venv` and `.venv-floor`; a small change (under 50 changed lines), no packet
- [ ] phase 2, on the coordinator's word: merge main after mt1, the next alpha, README and sidecar, the gate once

## Handover
- The pin differs from the brief: `echo a\#b; cp a CLAUDE.md` already gave the write; `echo x #c` then a newline then `cp a CLAUDE.md` gave `[]` (the comment's `readline` ate the newline, so `cp` joined `echo`'s words), now the write.
- Named `-8`: u3's branch holds `2026-11-12-7-u3-loop-lines.md`.

## Next act
- Phase 2 on the coordinator's word.

## Exit
Phase 1 landed; waits on the coordinator for phase 2.
