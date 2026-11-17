# Sitting 2026-11-17-8: agentik-session, ck2-test-workers, the fix of review 1

| item | value |
|---|---|
| goal | review 1's ruling: F1 (ak5's 1.0 s of wall on a warm `describe --json`), L1 (`WORKERS = 4` plain), L6 (help fills in its names), L8 (the packet and the first record current), five rows to NICE |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `f64adef` on `ck2-test-workers` |
| branch | `ck2-test-workers`, worktree `.claude/worktrees/ck2-test-workers`, the two venvs linked |
| level | S2, packet `design/packets/ck2-test-workers.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] F1: the cold call's CPU and a warm call's 1.0 s of wall; the test of the test red at `f64adef`, green after
- [x] L1, L6: `WORKERS = 4`; help names 4 and python3.12; two tests in `tests/test_ck2_workers.py`
- [x] L8: the packet's §4 (each row green or red, the 8 row, A1's three, why 4) and the first record's A1
- [x] NICE: n297 to n301; n231 leaves (F1 lands it); n228, n230 and n232 to n234 moved to `history/NICE-overflow.md`
- [ ] `make stamp`, then one `make check`, through the gate

## Handover
- If this sitting is cut: the first unticked line above.
- Choice: the test of the test is a made-up launcher, `sleep 1.5` then the plugin's own; nothing under `plugin/` is touched.
- Choice: the new ids start at n297, past the n282 to n296 the g10 branch holds; the landing renumbers.
- Choice: help fills in `$(WORKERS)` and `$(VENV_PYTHON)` alone; `$(PREFIX)` in install's line is as before.

## Next act
The stamp and the check, through the gate.
