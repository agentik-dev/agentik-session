# Sitting 2026-11-14-7: agentik-session, su4 the suite's three reads

| item | value |
|---|---|
| goal | build 1: gate items' `caller` and `queued` (R1), the loop's pid line and `pid` (R2), `status --all` (R3), describe's `sittings` read (R4), `MORE_REPO` quoted (R5), the words and NICE rows (R6) |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `95da908` (rw3-gate-repo's merge, alpha.123) |
| branch | `su4-session-reads`, worktree `.claude/worktrees/su4-session-reads`, the two venvs linked |
| level | S4: `design/packets/su4-session-reads.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet and this file
- [x] the tests, red at `95da908`: 12 failed of 15; the three pin-bytes lines (2, 5) green
- [x] R1 and R5, the gate: su4 1, 2, 7 green; the gate, rw3, gl1, fw2 and ak5 tests 798 passed (.venv); `tests/test_fw2.py`'s running-keys line moves by the two keys
- [x] R2, the loop's pid: kind `start`, `{ts, kind, pid}` once after the run's folder; su4 3 green; the unattended, u1 to u3, h3, band, admit, bare-machine and land5b tests 406 passed (.venv); `tests/test_u3.py`'s no-other-kind line names `start`
- [x] R3 and R4, the sittings read and describe: `hooks.sittings`, the `status` flag `--all` (exclusive with `--transcript`), `plug.SCHEMAS["sittings"]`, describe's sixth read; su4 15 of 15 (.venv); `tests/test_ak5_plug.py`'s two `reads` lines move by the one item
- [ ] R6, the words and NICE rows
- [ ] check, by the gate queue; `scripts/hygiene --require-private --commits main..HEAD` exit 0

## Handover
- Choices inside the rulings: the packet's §3.
- decide, owner: the coordinator (consumer: review 1): `tests/test_fw2.py` line 165 pins a running item's keys, so it gains `caller` and `queued` (R1); added to the packet's may-touch row.
- If this sitting is cut: the first unticked line above.

## Next act
R6, the words and NICE rows.

## Exit
Open.
