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
- [ ] the first check through the gate, `make stamp` first, `PYTEST_ADDOPTS=--durations=25`; the scratch demos (acceptance 3, 4) after it in the same job
- [ ] R4: the NICE row from the durations, then the last check

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
The first check through the gate.
