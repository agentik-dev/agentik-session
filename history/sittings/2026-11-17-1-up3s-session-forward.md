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
- [x] R1: `install(prefix, env, force=False)` leaves a command install-cli wrote (`_ours`), its runner standing and `newer` than this tree (`_ahead`), checked before the lock and again under it; the result's `kept`; `_behind` and `_ahead` share `newer`, by `order`
- [x] R2: `install-cli --force`; kept, one line in commons' words, exit 0, nothing written
- [x] R3: the one caller of `install()` is `cmd_install_cli` (the verb, behind `/session:install-cli`, `make install`, a launcher's `is gone` remedy); the SessionStart refresh calls `_locked_install`, as today
- [x] R5: the doctor's `launcher` row compares; a newer command is a note, `newer than the plugin's`; older as at the pin
- [x] `make stamp` through the gate (job `20261117-045721-2370`, exit 0): 2.0.0-alpha.131, 4866 tests
- [x] the hygiene scan, `--require-private --commits main..HEAD`: exit 0, 0 hits
- [ ] `make check` through the gate: jobs `20261117-045748-2371` and `20261117-052801-2378` each cut by the 1800 s wall in the floor pass (load 25, then 57), their first pass green (4866 passed); the third, `20261117-060100-2387`, queued sixth when the sitting reached its bound

## Handover
- If this sitting is cut: the first unticked line above.
- decide, owner: the coordinator: the third check's result; a fourth run is past the brief's three.

## Next act
The coordinator: read job `20261117-060100-2387`; green, review and landing.
