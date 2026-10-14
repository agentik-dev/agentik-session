# Sitting 2026-10-14-2: agentik-session, band-target (the band fills by the weekly reset)

| item | value |
|---|---|
| goal | the owner's word, 2026-10-14 06:43: when the `seven_day` reset falls before the five-hour one, the horizon `T` ends at the weekly reset; `project` and `band` name the bound (`five_hour`/`seven_day`), the band line says `week resets`; `design/admission-r1.md` §3.2 takes one sentence |
| budget | 200k window, 180k context, stop at 80%; ~90 tool calls; one commit per act; no push, amend, rebase, `make install`, relay verbs |
| pin | worktree `.claude/worktrees/band-target`, branch `band-target` at main a738c35 |
| window | 1M (a builder keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 1: red tests: `project` T 77 over 77 (seven-day 77 min, five-hour 226 min), seven-day after, past or within `SAME_RESET_S` keeps today's T, the band line `week resets` (Python and the module's twin): `tests/test_admit.py tests/test_band.py` 11 failed, 86 passed (`assert (226.0 == 77)`); `claude plugin test plugin` 1 fail, 48 pass
- [ ] act 2: `admission.horizon` shared by `project` and `band`; `bound` in both; `band_line` and `admissionLine` say `week resets`; the design sentence; the README count
- [ ] gate: `nice -n 10 make check` once; `scripts/hygiene --require-private`

## Handover
- (open)

## Next act
Act 2.

Exit: (open)
