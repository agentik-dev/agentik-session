# Sitting 2026-11-17-1: agentik-session, up3s-session-forward

| item | value |
|---|---|
| goal | session's `install-cli` moves its command forward only: a newer command is left, `--force` places it; commons' copies synced |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `ef0ba32` on main (2.0.0-alpha.130); commons main `626a3f0` |
| branch | `up3s-session-forward`, worktree `.claude/worktrees/up3s-session-forward`, the two venvs linked |
| level | S3, packet `design/packets/up3s-session-forward.md` |
| agents | 0 |

## Done-ness
- [x] the packet, its baseline measured at the pin
- [x] R4: commons' `scripts/sync` (main `626a3f0`) against the worktree: four files moved (the door 0.3.0 to 0.3.1 in two places, `agentik_install.py`, the sums), every placed file `cmp`-equal; `test_ak10d_launcher` R2 moved: commons now reads the old form as session's own
- [x] the failing tests: `tests/test_up3s_session_forward.py`, 6 of 12 failing at the pin (the six that pass pin what stays: an older command placed with the PATH lines, a gone tree, a hand's file, the refresh, the doctor's older and equal rows)
- [ ] R1, R2, R3, R5
- [ ] `make stamp`, then `make check`, through the gate; the hygiene scan of the commits

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
R1, R2, R3, R5.
