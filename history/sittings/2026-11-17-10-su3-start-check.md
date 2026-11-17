# Sitting 2026-11-17-10: agentik-session, su3-start-check

| item | value |
|---|---|
| goal | SessionStart says, in one line on both channels, a declared watcher the launcher's `status --check` finds not running (entry 12); silence otherwise |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `accf29f` on main |
| branch | `su3-start-check`, worktree `.claude/worktrees/su3-start-check`, the two venvs linked |
| level | S3, packet `design/packets/su3-start-check.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, the baseline at the pin, and the four NICE rows that ride it
- [ ] R1 to R7: `hooks.session_start`'s watcher line; `tests/test_su3_start_check.py`
- [ ] `make stamp` through the gate, committed
- [ ] `make check` through the gate, once, last

## Handover
- If this sitting is cut: the first unticked line above.
- Note: `NICE_TO_HAVE.md` is past recordlint's size bound with the four rows (25,514 B); `make stamp` moves the oldest S4 rows, as its target says.

## Next act
R1 to R7: the failing tests, then the change in `hooks.py`.
