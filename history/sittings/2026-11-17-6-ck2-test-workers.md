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
- [ ] R1, R2: the runner in the dev extra, `make venv`, `make venv-floor`; `-n $(WORKERS)` or `workers: absent`; `tests/test_ck2_workers.py`
- [ ] R1's install through the gate
- [ ] R5: the measure test's stamp and its test of the test
- [ ] R4, R6: what fails on workers; the `git add -A` cause
- [ ] R3: three settings measured, the number set; A1 three green in a row
- [ ] R7: the help lines

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
R1 and R2's commit, then the install through the gate.
