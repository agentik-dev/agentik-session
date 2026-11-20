# Packet pl2: the usage line drops the ceiling and an empty count, names the week's reset with its time left, and says the helpers as n/m

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief pl2-line-dynamic; the owner's words below |
| pin | `9d8e0ac` on main (rc2 landed, 2.0.0-alpha.144). Worktree `.claude/worktrees/pl2-line-dynamic`, branch `pl2-line-dynamic`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `tests/test_chain.py` unedited, `chain.py` and `_confirm`'s rule unchanged; `tests/test_rc1_respawn_confirm.py` and `tests/test_rc2_close_guards.py` changed only where they pin bytes R7 changes |
| may touch | `plugin/lib/claude_session/admission.py` (`band`, `_band_none`, the line's functions), `plugin/lib/claude_session/cli.py` (`status`'s admission facts), `plugin/hooks/session.ts` (`admissionLine`, `mixPart`, `lineNone`), `plugin/hooks/session.test.ts`; `plugin/lib/claude_session/hooks.py` (`_jobs_notice`, `_jobs_out_line`, `_post_tool_use`); `tests/test_pl2_line_dynamic.py` (new) and the assertions that pinned a changed line; `RUNBOOK.md`, `plugin/skills/session/SKILL.md`; `NICE_TO_HAVE.md` (two rows); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file and the files that pin the line or the hooks; `scripts/doclint`, `scripts/recordlint`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `admission.band_line` draws the five-hour line: `5h P% → peak% · ceiling c · resets HH:MM (h:mm) · n helpers, room for r · d deferred · 7d P7%`, then the mix's parts (`_mix_part`: `reset now`, `resets N` with ` by Ddd HH:MM`), then the age. `_line_none` draws the `none` line and S51's `5h no reading` line. `admissionLine`, `mixPart` and `lineNone` in `session.ts` are the twins; the fixtures in `session.test.ts` are read by the Python tests.
- `_mix_resets` draws `resets N` for any N, so `resets 0` stands on the line when no reset is in hand.
- A five-hour entry of band.json holds the week's reset only as `until` when the week bounds the background term; `band()` reads the newest seven-day reading ahead of now for `P7` alone.
- `status` prints `admission mode: <mode>`; `--json`'s `admission` holds `mode` and `mix`.
- `_jobs_notice` scans the prompt with a lazy regex from each `<task-notification>`; with no closing tag each start scans to the end. `_post_tool_use` says nothing of an unconfirmed marker; rc1's line is the prompt's alone.

The owner's words, 2026-11-20, reading `5h 23% → 192% · ceiling 97 · resets 06:40 (4h39) · 5 helpers, room for 0 · 5 deferred · 7d 41% · resets 1`: "What is resets 1? Is that a cutoff 7d reset date?"; then: "Let's remove that and maybe put the 7d reset in instead. Also I think you can remove "ceiling 97" - and stick to mostly dynamic information in this." Shown the line that gave: "I think you should make it match the 5h reset where you give me number of days/hours remaining in the same short hand. Also "5 helpers, room for 0 · 5 deferred" could likely be expressed with a better short hand (room for 0) is a little too wordy)."

## 2. Rulings (brief pl2)

- R1 no line holds `ceiling`; what the ceiling decides stands. `status`'s `admission mode:` line gains ` · ceiling <c>`; `--json`'s `admission` gains `ceiling`.
- R2 `resets N` only for N of at least 1, with its ` by Ddd HH:MM`; for 0 nothing, the `by` included. `reset now` and `mix_status` as at the pin.
- R3 the five-hour line closes with `week resets Ddd HH:MM (NdHh)`, the time left as `(5d4h)` from a day up, `(4h30)` under one, never below `(0h00)`; left out with no figure and where the slot already says the week's reset; drawn with the mix off. The `none` line's week reset gains the same time left.
- R3b `helpers n/m` with a running count and a room, m the two summed; `n helpers` with no room; no running count, no part. `d deferred` only for d of at least 1.
- R4 the twins draw the same bytes. R5 the runbook, the skill and `band_line`'s docstring say the line as built. R6 the order, `clip`, the age and `_line_end` stand.
- R7 the refusal's line says a job whose notice has come has ended and the close is run again now; the notice scan is linear; a main-thread Bash call that left this session's chained marker, written at or after its own PreToolUse stamp, with no confirm of its bytes, says rc1's `RESPAWN unconfirmed:` line at its PostToolUse, after any checkpoint line and within `MAX_OUT`. Two NICE rows (rc2's review, L3 and L9).

## 3. Interfaces: the acceptance table (baseline measured at `9d8e0ac`)

Tests in `tests/test_pl2_line_dynamic.py`.

| # | line | at the pin |
|---|---|---|
| 1 | the owner's entry draws `5h 23% → 192% · resets HH:MM (4h39) · helpers 5/5 · 5 deferred · 7d 41% · week resets Wed 07:00 (5d4h)` | `5h 23% → 192% · ceiling 97 · resets 07:27 (4h39) · 5 helpers, room for 0 · 5 deferred · 7d 41% · resets 0` |
| 2 | no `ceiling` on any line; `status` says it on `admission mode:`, `--json` holds it | `ceiling 97` on the line; `status` has none |
| 3 | `resets 0` draws nothing, `until` ahead too; 2 and 2 with `by`; `reset now`; `mix_status` keeps `resets 0` | `resets 0`, `resets 0 by …` |
| 4 | the week's reset: no figure no part; the slot's form once; mix off; the `none` line with its time left; `(5d4h)`, `(1d0h)`, `(23h59)`, `(0h00)` | no week part on a five-hour line; the `none` line with no time left |
| 4b | `helpers 5/5`, `helpers 0/6`, `3 helpers`, none; `0 deferred` gone | `5 helpers, room for 0`; `0 deferred` |
| 5 | the `5h no reading` line is chosen as at the pin | the same |
| 6 | the twins equal on every entry above; the parity tests green | |
| 7 | the mends: a close from a script says the respawn line at PostToolUse; the refusal's words; a 200 KB prompt of 10,000 open tags under half a second | none; the pin's words; seconds |
| 8 | `make stamp`, then `make check` green through the gate | |

The new band.json key: a five-hour entry built by `band()` gains `week_resets`, the newest seven-day reading's reset ahead of now as a local zoned stamp (the reading `P7` reads), or null. An entry without it draws no week part.

## 4. Findings that name this row: the choices inside the rulings

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
