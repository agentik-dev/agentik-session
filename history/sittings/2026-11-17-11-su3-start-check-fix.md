# Sitting 2026-11-17-11: agentik-session, su3-start-check, the fix of review 1

| item | value |
|---|---|
| goal | the review's F1 mended (C1, C2), the allow row moved (C3), three NICE rows (C4), the packet's section (C5) |
| budget | about 90 tool calls, `claude-sonnet-5-5`; checkpoint at 80% |
| pin | `1eb53f8` on `su3-start-check` |
| branch | `su3-start-check`, worktree `.claude/worktrees/su3-start-check` |
| level | S3, packet `design/packets/su3-start-check.md` |
| agents | 0 |

## Done-ness
- [x] C1, C2: three cases red at `1eb53f8`, green after; `hooks._Beyond` counts the rest as it is read
- [x] C3: the su3 allow row and its comment sit after the akt-run row
- [x] C4: n312 to n314 (F2, F3, F4)
- [x] C5: packet section 4a
- [ ] `make stamp`, then `make check`, each through the gate queue

## Handover
- If this sitting is cut: the first unticked line above.
- Choice: past the keep, a line counts when it holds a byte that is no ASCII blank or control; the kept part is counted exactly, decoded.
- Choice: a first line that fills the keep is decoded incrementally, a trailing partial character dropped.

## Next act
The gate; then the coordinator's second review.
