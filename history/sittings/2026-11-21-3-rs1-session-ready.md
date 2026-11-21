# Sitting 2026-11-21-3: agentik-session, rs1-session-ready, build 1

| item | value |
|---|---|
| goal | session's gate reads no record of its clone: test 5 of g7 and land3's line 9 read fixtures; the whole check rehearsed in a scratch clone with the records gone |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `2bfa312` on main (rr5c landed, plugin 2.0.0-alpha.158) |
| branch | `rs1-session-ready`, worktree `.claude/worktrees/rs1-session-ready`, the two venvs linked |
| level | S3, packet `design/packets/rs1-session-ready.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet
- [x] R1 the packets' lines: `tests/fixtures/g7/packet-lines.txt`, 161 lines (14 refused) from the pin's 135 packets, harvested once from a `git archive` of the pin; test 5 reads it, its count pinned
- [x] R2 the overflow's shape: `tests/fixtures/land3/NICE-overflow.md` (head, `## From the open findings` with two made-up rows, a borrowed section after), line 9 reads it as `OVERFLOW_SHAPE`; `OVERFLOW` stays the temp repos' path
- [ ] R3 the rehearsal: run 1 (`20261121-091800-3036`, exit 2) red on three tests run in the clone's tree (its records state `unset`): mended, the hook's two in one commit, s19 in one; one floor red, `git add` EINVAL in a temp repo, no record read; run 2 to come
- [ ] `make stamp`, `make check` through the gate

## Handover
- The repo has no `CLAUDE.md` at the pin; the brief names one.

## Next act
R3: the scratch clone, its records removed, `make check` through the gate.

## Exit
