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
- [x] R6, R7: `check FILE` in `broken` refused in the clone; the close's pin line stands (a test), with no holder it says nothing is committed; `since_landing` in the holder
- [ ] R8: RUNBOOK and help; doclint, hygiene
- [x] `make stamp` through the gate (`20261121-011449-2961` exit 0): plugin 2.0.0-alpha.155, 5528 tests
- [ ] `make check` through the gate on the stamp's commit: its job is in the coordinator's record

## Handover
- The repo has no `CLAUDE.md` at the pin; the brief names one.

## Next act
R8: RUNBOOK's and the help's sentence; the packet's choices; doclint, hygiene; then the stamp and the check through the gate.

## Exit
Build 1: R1 to R8 built, each acceptance test red at the pin where the pin differs; stamped; this commit is the one `make check` runs on.
