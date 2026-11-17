# Sitting 2026-11-17-6: agentik-session, ck2-test-workers

| item | value |
|---|---|
| goal | the suite runs on pytest-xdist workers in both venvs so `make check` falls well under its 1,800 s wall; R5's and R6's tests mended or explained |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `fd8f3af` on main |
| branch | `ck2-test-workers`, worktree `.claude/worktrees/ck2-test-workers`, the two venvs linked |
| level | S2, packet `design/packets/ck2-test-workers.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet
- [x] R1, R2: the runner in the dev extra, `make venv`, `make venv-floor`; `-n $(WORKERS)` or `workers: absent`; `tests/test_ck2_workers.py`
- [x] R1's install through the gate: job `20261117-122828-2466` exit 0; pytest-xdist 3.8.0 in both venvs
- [x] R5: the stamp 300 s before the meter's own `ts`; the test of the test by a fixed clock; 200 of 200 green in each venv
- [ ] R4, R6: what fails on workers; the `git add -A` cause
- [ ] R3: three settings measured, the number set; A1 three green in a row
- [ ] R7: the help lines

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
R4 and R6: a first check on 4 workers, its failures read.
