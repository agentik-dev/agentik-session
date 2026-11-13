# Sitting 2026-11-13-1: agentik-session, pl1 the prompt line tidied

| item | value |
|---|---|
| goal | packet pl1 phase 1 (`design/packets/pl1-prompt-line.md`): R1 to R7 built, R8's tests green under both venvs; no bump, no merge, no gate job |
| budget | builder: about 90 tool calls |
| pin | 8a4b593 on main (2.0.0-alpha.93); worktree `.claude/worktrees/pl1-prompt-line`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] act 1: the packet, with the baseline measured at the pin
- [x] act 2: R1, R2, R6: `_mix_part`, `_line_none`, `_line_end` and their `session.ts` twins drop the shares, `next`, the band, the mode's word; `bandLine` says no `clear`; 30 fixture lines rewritten by the strip rule and proven equal to Python's line; the TS twin equal on 78 of 78 fixtures under node; tests 586 passed
- [x] act 3: R3: `status` prints `mix: ...` (`admission.mix_status`) and `admission mode: ...` after the band; `--json` gains `admission` {mode, mix}; at the pin the band alone was there
- [x] act 4: R4: `rules.MIX_ITEM` names `agentik session status` (its `mix:` line's `next`), not the band line; no other rule moved
- [x] act 5: R5, R7: the RUNBOOK (the band, the line, the none line, the demand band) and the skill follow, R5's sentence in the RUNBOOK's line paragraph; the README source does not show the line, unchanged; the packet gains its sections 1, 4, 5, 6 (doclint red at act 1, green now)
- [x] act 6: the README's suite count 3432 to 3447 by hand in the source and the README (same bytes, 16365 B), the sidecar re-hashed, no render; the new test file takes `from __future__ import annotations` for the floor's 3.9
- [x] the suite at eac393b plus act 6: .venv 3445 passed but test_readme's count (fixed by act 6); .venv-floor four chunks green but the count and the floor's import error (both fixed); test_pl1 + test_readme 74 passed under each venv
- [x] acceptance at the pin: tests/test_pl1_prompt_line.py 9 failed, 6 passed (the prompt hook's zone cases held at the pin) on the pin's tree

## Handover
- Phase 2 (bump, gate job, merge) waits on the coordinator's word.
- decide, owner: acceptance 5 and R1 meet at the resets count: R1 keeps `resets <n>`, the mix's own figure, so with the mix off the line lacks it; built as "equal less `resets <n>`". Consumer: the hq coordinator.
- The mod's tests (`claude plugin test plugin`) did not run here; `session.ts` was loaded under node 26 and drew all 78 fixture lines equal.

## Next act
- None for this builder: phase 2 on the coordinator's word.

## Exit
- Phase 1 built: R1 to R7 in five acts and the count's act; both venvs green by chunks (.venv 3447 collected; floor 3319 passed, 105 skipped plus the fixed readme pair); handed back to the coordinator.
