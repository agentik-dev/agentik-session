# Packet S32: a fresh relay row is charged its life (fresh-session-r1's S32)

| item | value |
|---|---|
| from | `design/fresh-session-r1.md` §2 (the decision), §4 (the cut), §5 (open risks); `OPEN-QUESTIONS.md` answer 6 (2026-10-15, 01:2x local, "Yes, fix it."); `design/admission-r1.md` §3.2; the refuter's note on fresh-session-r1 (2026-10-15) |
| pin | branch `worktree-agent-a08070024d12961d4` at 325d616 (fresh-session-r1, on 6e97555, alpha.15); worktree `.claude/worktrees/agent-a08070024d12961d4`; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, merge, device, network, real `claude`, `agentik session run`, `claude plugin`, `make readme`, `make install` or `make check`; never write under `~/.local/state`; no `agentik-session` verb that writes (`admission admit` among them); never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; never touch `~/code/syrvis`, `~/code/home-tech` or their worktrees; every python `-B` |
| may touch | `claude_session/admission.py` (`project` and a new `row_life`), `tests/test_admit.py`, `design/admission-r1.md` (one sentence in §3.2 citing fresh-session-r1), `NICE_TO_HAVE.md`, `design/fresh-session-r1.md` (act 2: one sentence in §3, one bullet in §5), this packet, `history/sittings/2026-10-15-1-s32.md` |
| acceptance | 1: `.venv/bin/python -B -m pytest tests/test_admit.py -q -k s32 2>&1 \| tail -1` reads `passed`, no `failed` (pin: 4 failed); 2 (the control, green before and after): `.venv/bin/python -B -m pytest tests/test_admit.py -q -k "synthetic_day or f2_a_spawn or halve" 2>&1 \| tail -1` reads `3 passed`; 3: `.venv/bin/python -B -m pytest tests/test_admit.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; 4: `python3 -m compileall -q claude_session` exits 0 |
| verify | `make check`, by the coordinator, after this branch |
| budget | acts: 0 this packet and the charter; 1 the four tests red, then `project` and `row_life` to green, admission-r1 §3.2's sentence; 2 the refuter's note folded into fresh-session-r1 §3 and §5. 40 turns, stop at 32 (commit the act in flight), 180k; one commit per act; no version bump (conventions §7: no key, hook output or resolved-file contract changes) |

## 1. What the source says

fresh-session-r1 §2.1: "When the request's type is `relay-row` and its session is not among the active main threads (no reading in the last 45 minutes, or an end line since its newest), `project` leaves it out of `_rise`'s threads and adds a·min(T5, L_row). A `relay-row` ask adds no spawn term at all." The peak: P + a·T·|active ∪ ({sid}, unless a relay row)| + Σ (running) b_f·min(T5, max(L_t − age, 5)) + (a relay row not active: a·min(T5, L_row); not a relay row: b_f·min(T5, L_t)). §2.2: L_row "is the median minutes from start line to end line of the sessions that have a `relay-row` verdict line in the ledger. ... While no such session has ended, the seed life (15) stands." §2.3: a running row stays an active main thread to the reset; a finished row leaves at its end line. §4: four tests red at 6e97555, each with the seeds (a 0.10, b_opus 0.15, life 15), a reading of P 2 with the reset 274 minutes ahead, and `ask(subagentType="relay-row")`.

## 2. Rulings

1. **A relay row** is a request whose `helper_type(subagentType, fork)` is `relay-row` (a fork is `fork`, never a row). Every other request, and the band, projects as today.
2. **Active** is `_active` over the ledger's readings and end lines at `now`, as `_rise` reads it; the request's own `rateLimits` give P and T but do not make its session active (the relay's ask carries none, band-pacing-r1 §2.2).
3. **`row_life(rows, seeds) -> float`**: the sessions with a `verdict` line whose `type` is `relay-row`; each one's first `start` line to its first `end` line at or after it, in minutes; the median (even count: the mean of the middle two); `seeds["life"]` when none has ended. A session with no start or no end line is left out.
4. **`project`**: `_rise` gets `{sid}` unless the request is a relay row; a relay row not active adds `a·min(T5, row_life)`, with `a` the fit's; a relay row active adds nothing; any other request adds `b_f·min(T5, L_t)` as today.

## 3. Interfaces

`admission.row_life(rows, seeds)` (new, pure); `admission.project`'s return keys unchanged; the `verdict` line, `admission admit`'s answer and `session.admission` unchanged.

## 4. Tests

Red first (each fails at the pin):

1. `test_s32_a_fresh_relay_row_is_charged_its_life_not_the_window`: another interactive thread's reading, the asking id has no lines: 2 + 0.10 × 274 + 0.10 × 15 = 30.9 (pin: 59.05).
2. `test_s32_a_relay_row_ask_adds_no_spawn_term`: the reading is the asking id's own, active and alone: 2 + 0.10 × 274 = 29.4 (pin: 31.65).
3. `test_s32_the_row_life_is_the_median_of_the_asked_sessions_start_to_end`: as 1, and hours earlier three asked rows ended 10, 20 and 40 minutes after their start lines, one asked row has no end line, one interactive `general-purpose` session ran 90: `row_life` is 20 and the ask reads 2 + 27.4 + 2.0 = 31.4 (pin: no `row_life`; 59.05).
4. `test_s32_a_fresh_relay_row_near_the_weekly_reset_counts_its_life_against_the_five_hour_window`: the other thread reads 40, the week resets in 2 minutes and the window in 150: 40 + 0.10 × 2 + 0.10 × 15 = 41.7 (pin: 42.65).

The control, green before and after: `test_the_peak_against_a_synthetic_day`, `test_f2_a_spawn_near_the_weekly_reset_counts_its_life_against_the_five_hour_window`, `test_a_session_that_read_once_and_ended_does_not_halve_a`.

## 5. Forbidden reads

Transcripts; the account's state dir (the admission ledger among it); other repos (act 2 cites agentik-relay `internal/night/run.go:515` as the coordinator gave it, unread).

## 6. Report (capped)

At most 150 words: commits (sha, one line each); each acceptance line's result; the red lines before the fix; any ruling beyond the note. Last line: branch, head sha.
