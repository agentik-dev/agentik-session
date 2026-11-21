# Sitting 2026-11-21-1: agentik-session, rr5b-two-commits, build 1

| item | value |
|---|---|
| goal | `checkpoint --commit` in `out` as two commits (the clone's, then the holder's), refused before either, the half said; `charter check FILE` in `broken`; the close line and reconcile's log in the holder |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `89be323` on main (rr5a landed, plugin 2.0.0-alpha.154) |
| branch | `rr5b-two-commits`, worktree `.claude/worktrees/rr5b-two-commits`, the two venvs linked |
| level | S3, packet `design/packets/rr5b-two-commits.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet
- [x] The failing tests, `tests/test_rr5b_*.py`: 17 red at the pin (`4d356cc`)
- [x] R1 to R5: the split, `commit.precheck` for both before either, the half's line, no holder; fw5 and cli tests unchanged and green
- [ ] R6, R7: `check FILE` in `broken`; the close line; `since_landing`
- [ ] R8: RUNBOOK and help; doclint, hygiene
- [ ] `make stamp`, then `make check` through the gate

## Handover
- The repo has no `CLAUDE.md` at the pin; the brief names one.

## Next act
R6 and R7: `check FILE` in `broken`, the close with no holder, `since_landing` in the holder.

## Exit
