# Packet u2-loop-finish: the unattended loop finishes a row before it lands it

| item | value |
|---|---|
| from | agentik-hq `history/sessions/BRIEF-2026-11-11-session-u2-loop-finish.md` (the owner's words of 2026-11-11, R1 to R6); the audit's findings C2, B2, B6 (`AUDIT-2026-11-11-prompting-guides/`); hq design/07 §2, §4 |
| pin | agentik-session main c81d898 (alpha.70). Worktree `.claude/worktrees/u2-loop-finish`, branch `u2-loop-finish`, the two venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live state or writes under the live home; no relay verb; not `hooks.py`, `charter.py`, `ledger.py`, `profiles.yaml`, `skills/session/SKILL.md`, `design/overhaul-r1.md` (row b1-meter-cadence's) |
| may touch | `plugin/lib/claude_session/unattended.py`; `tests/test_u2.py` (new), `tests/test_unattended.py` (its packets gain an acceptance row; the two prompt asserts); `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/*` (the status line); `design/packets/u2-loop-finish.md` |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_u2.py` exits 0; `./.venv-floor/bin/python -m pytest -q tests/test_u2.py` exits 0; `./.venv/bin/python -m pytest -q tests/test_unattended.py` exits 0; `./.venv-floor/bin/python -m pytest -q tests/test_unattended.py` exits 0; `grep -c 2.0.0-alpha.71 plugin/.claude-plugin/plugin.json` reads 1 |
| budget | 150 turns, 150k context; a commit per ruling group by explicit path, this packet first. `claude-opus-5-5` at `high` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` |

Baseline at c81d898: lines 1 and 2 exit 4 (no such file); 3 and 4 exit 0 (`32 passed`); 5 reads 0.

## 1. What the source says

The owner, 2026-11-11: on the loop merging a half-built row, "fix this now, using opus agents"; on "Have the loop run acceptance lines before landing a row, with one named continuation?", "yes"; on effort, "set the defaults for these. Opus 5.5 can be high starting point."

At the pin, `unattended.py`: the child's prompt is `HEADING` ("The packet; the repo's CLAUDE.md carries the rules") over the packet, and three target repos have no CLAUDE.md; `end` lands a row with a commit, a clean tree and a non-error result, and the packet's acceptance lines never run; `CONTINUE` is "continue from your charter's act in flight; your commits stand", sent only after a limit; `spawn_argv` passes no `--effort`, so the child takes the Mac's `xhigh`. The loop has never run (`unattended report`: "no run yet"): no state to migrate.

The relay reads the acceptance cell in `internal/packet/packet.go` `acceptance` and `expect`, runs each line under `/bin/sh -c` cut at `effects.Timeout` (900 s; exit 124 at the deadline), judges it by `night.Holds`, and in `gate.rerun` compares a line with its baseline on main only when the packet wrote `as main` (relay-r1 §6: "same-as-main only when the packet wrote `as main`, otherwise `red`"); an error running it is `unrun`, never a pass (relay entry 15).

## 2. Rulings

- R1, the prompt. `PROMPT` replaces `HEADING`: finding C2's draft, verbatim; no clause is false against the code.
- R2, acceptance before landing. `acceptance(text)` reads the header table's `acceptance` cell as the relay does: a row split on unescaped `|`, items split on `;` outside backticks, each a code span then `reads <v>`, `reads <n> or more`, `under <n>`, `exits <n>` or `as main`; `\|` unescaped. A packet with no such cell, or one that does not parse, is refused before the spawn, `refused acceptance`, the parser's words in the log: a row that cannot be judged never runs. After a commit, a clean tree and a non-error result, every line runs in the row's worktree, `/bin/sh -c`, its own session, cut at 900 s (exit 124, `cut`), under a scratch home (the relay's `scratchEnv` names) and the push barrier; the last non-empty stdout line, else stderr's, capped at 200. A line that cannot start is `unrun`. An `as main` line is measured once in the staged tree before the spawn (the pin), and on the branch is `same-as-main` (a pass) when exit and last line match, `unrun` when its baseline was; every other line holds or is red. Each run is an `accept` ledger line. Any non-passing line: the row does not land and is not `built`.
- R3, the named continuation. A failing line sends a resume of the same session: each failing line with what it returned and what it wants, then "Continue with the acts that make them hold. If one is blocked, say what blocks it in the charter's handover." The row's checks run again after it. Two such continuations at most; then the row is red `acceptance`, its `row` line carrying `failing`. The budget of a resume is the row's less what every part spent, never under 10 turns or $5.
- R4, the limit continuation. `CONTINUE` says the child stopped at the usage limit, its commits stand, it reads its charter's done-ness list, finishes each unchecked act, runs the acceptance lines, commits, and ends when they pass or says what blocks it. A second limit on a row is counted by limits, not parts.
- R5, effort. `--effort` on every spawn and resume: the row's `effort`, else `defaults.effort`, else the `builder` profile's (`resolver.load_profiles`), else `high`. A value outside `low medium high xhigh max` refuses the row, `refused effort`. The `spawn` and `row` lines carry `effort`; the report's landed, built, red and limited tables gain an `effort` column.
- R6. `plugin.json` 2.0.0-alpha.71; the status line and its sidecar.

Choices logged (reversible): the refusal of a packet with no readable cell; the baseline measured only for `as main` lines, as the relay's hand gate does; acceptance runs for `branch-only` rows too, so `built` means finished.

## 3. Interfaces

Tests: `tests/test_u2.py`, the fake `claude` and gate of `tests/fixtures/unattended/`.

| T | the test shows | item |
|---|---|---|
| 1 | the prompt is the draft over the packet | R1 |
| 2 | the parser: five kinds, `\|`, `;` in a span, the errors | R2 |
| 3 | a failing line: no gate call, red `acceptance` after two continuations, `failing` | R2, R3 |
| 4 | an `as main` line red at the pin, the same on the branch: lands | R2 |
| 5 | a line that cannot start, and a cut one: red | R2 |
| 6 | the continuation's text names the line, its return and its want; the resume argv | R3 |
| 7 | a row green after one continuation lands | R3 |
| 8 | a limit still resumes, with the new text | R4 |
| 9 | `--effort` from the row, the defaults, the profile, `high`; a bad one refused; ledger and report | R5 |
| 10 | a packet with no acceptance cell is refused before any spawn | R2 |

## 4. Findings that name this row

agentik-session keeps no ledger of its own. Bearing: relay entry 15 ("unknown is never a pass"; "a red row is never retried the same day": a continuation is the same attempt, the same session); agentik-hq entry 14 (the loop and the relay's entry 13). hq design/07 §2 step 3 and §4 ("the acceptance table's per-line baseline on main") need the coordinator's amendment.

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

The hand-back of the common brief: head sha; gate id and result; the acceptance lines at the pin and now; choices; leftovers.
