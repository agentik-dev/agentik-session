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
- [x] R1 to R3, R5: `land.py` and `publish.py` take the target where it is; `tests/test_lh1_land_hygiene.py` 19 green; the pin's 381 land and publish tests unchanged and green; the new file and two publish files green under `.venv-floor` too
- [x] R4: this repo's `hygiene-range` target (`scripts/hygiene --require-private --commits "$(RANGE)"`, no RANGE exit 2); two tests: the land roads read it, and its rule run in a temp folder
- [x] `make stamp` (job `20261117-185426-2590`, exit 0): alpha.138, the count 4975 to 4996
- [ ] `make check` once through the gate queue

## Handover
- If this sitting is cut: the first unticked line above.
- Choice: a target is a Makefile line that opens `hygiene:` (or `hygiene-range:`), the rule `stamps` reads `stamp:` by; a target defined only in an included file is not seen, and the bare script runs.
- Choice: a make road's red carries make's own code (2 for a failed recipe), as the check step's does.
- Choice: make runs without the caller's MAKEFLAGS, MFLAGS, GNUMAKEFLAGS, MAKEFILES, MAKELEVEL (land's job drops them already; publish runs in a sitting's shell).
- Choice: each scan picks its road alone; `range not scanned` is said when a tree scan ran and no range road was there, so a repo with neither scan prints as at the pin.
- Choice: publish's 126 refusal stands wherever `scripts/hygiene` is there and not executable, a target beside it or not, as at the pin.

## Next act
`make check` through the gate queue.
