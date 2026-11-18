# Sitting 2026-11-17-12: agentik-session, lh1-land-hygiene

| item | value |
|---|---|
| goal | `gate land` and `gate publish` scan by the repo's own `hygiene` and `hygiene-range` targets where the Makefile has them, else the bare `scripts/hygiene` as before |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `69d0824` on main (plugin 2.0.0-alpha.137) |
| branch | `lh1-land-hygiene`, worktree `.claude/worktrees/lh1-land-hygiene`, the two venvs linked |
| level | S3, packet `design/packets/lh1-land-hygiene.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, the baseline at the pin (land and publish `red hygiene exit 1`; 14 of the 19 new cases red, the pin's own roads green)
- [ ] R1 to R3, R5: `land.py` and `publish.py` take the target where it is; `tests/test_lh1_land_hygiene.py` green
- [ ] R4: this repo's `hygiene-range` target
- [ ] `make stamp`, then `make check`, once each through the gate queue

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
R1 to R3 in `land.py` and `publish.py`.
