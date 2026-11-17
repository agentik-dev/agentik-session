# Sitting 2026-11-17-1: agentik-session, ck1-check-fits

| item | value |
|---|---|
| goal | `make test` runs the `.venv` and `.venv-floor` passes side by side, so `make check` fits its 1,800 s wall |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `ef0ba32` on main |
| branch | `ck1-check-fits`, worktree `.claude/worktrees/ck1-check-fits`, the two venvs linked |
| level | S2, no packet: a small change |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] R2, what two passes share: per-test temp roots (conftest), no port, no fixed path; `.pytest_cache` is the one shared file, so the floor pass runs `-p no:cacheprovider`. `bare-proof`'s latency row reads the load and retries once, as at the pin
- [x] R1: `make test` starts `test-floor` in the background to a `mktemp` log, runs the `.venv` pass, waits, prints the floor's log whole, names each failing pass, fails when either fails; `floor: absent` as at the pin
- [x] the first check through the gate on `c2d5094`, `make stamp` first (nothing to write), `PYTEST_ADDOPTS=--durations=25`: job `20261117-081009-2417`, exit 0, 1,572 s, load 11.6 to 37.7; `.venv` 4854 passed in 1490.11 s, floor 4705 passed, 128 skipped in 1555.84 s; the scratch demos after it: a failing pass named, `floor: absent` as at the pin
- [x] R4: the NICE row n271 from the durations
- [ ] `make stamp` (the NICE file is past its size bound with the row), its commit, then the last check

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
`make stamp && make check` through the gate on the NICE row's commit; commit what the stamp leaves.
