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
- [x] R4: `test_ak5_plug.py::test_describe_json`'s bound on CPU; R6: not found, what was ruled out in the packet's §4
- [x] `make stamp` (job `20261117-123635-2473`): the count 4889 to 4898, committed
- [x] R3: checks at 3, 4 and 6 workers (jobs `20261117-123028-2468`, `20261117-125335-2479`); 4 the fastest, the table in the packet's §4
- [ ] A1: three checks in a row at the default, one gate job running three `make check`
- [x] R7: the Makefile's help lines; the README source names no minutes, so no render

## Handover
- If this sitting is cut: the first unticked line above; its job writes one line per check.
- Choice: `make venv` builds under `VENV_PYTHON ?= python3.12` where `.venv` is absent; else it adds the runner only.
- Choice: `workers: absent in <venv>` is printed per pass after it, as `floor: absent` is.
- Choice: the README source is not edited: its `make test` line stays true and it names no minutes.
- decide, owner: coordinator. The brief's A3 baseline (4,854; 4,704 + 128) is ef0ba32's; at `fd8f3af` the count is 4,889 and the floor 4,740 + 128.

## Next act
Wait on the three-check job; enter its lines in the packet's table and A1.
