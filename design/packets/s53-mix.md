# Packet S53: the spend mix, family shares of the week and the Fable resets

| item | value |
|---|---|
| from | the owner's ask of 2026-11-09 (hq sitting 2026-11-09-1): set usage ratios by model family and have the meter steer to them, Fable resets counted; configurable. S3, the owner's word |
| pin | agentik-session main 344818a, alpha.49; worktree `.claude/worktrees/s53-mix`, branch `s53-mix`, `.venv` and `.venv-floor` linked from the main checkout |
| wall | this repo; no push, `--amend`, rebase, merge, real `make install` or `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config/agentik`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME |
| may touch | `plugin/lib/claude_session/admission.py`, `meter.py`, `measure.py`, `hooks.py`, `rules.py`, `resolver.py`, `cli.py`, `tests/`, `README.md`/`design/readme/*` for the settings and the count, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`, this packet as `design/packets/s53-mix.md`, a charter |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log>"`, then `agentik session gate wait <id>` in one background Bash, last; it exits 0 whatever the code: read the code from its line |
| acceptance | rulings 1 to 8 met; tests 7(a) to 7(f) green by name; `scripts/doclint` exits 0 |
| budget | 90 tool calls, 140k context; `claude-opus-5-5` |

## 1. What the source says: the evidence

A login's reading is one all-models figure: `[{"kind": "seven_day", "percentUsed": 0, "resetsAt": "2026-11-16T23:00:00.000Z"}]`, a whole percent, with `five_hour` beside it on some logins. No reading names a model. Fable 5.2 (2026-11-09) is capped at 50% of the weekly limit, and a Fable reset, applied by the owner in Settings, gives back only the Fable usage: the published example is 80% (50 Fable, 30 other) reading 30% after. So a reset shows as the same login's `seven_day` falling with its `resetsAt` unchanged. The owner's plan for a week with N resets: Fable to its cap, a reset, again, N + 1 times, with Opus on the routine work at a set ratio, ending the week at 100%. What the tool lacks is each family's part of `P7`. `meter.py` already reads each turn's `message.model` and `usage` from the transcript; `admission.family()` names the family; `band()` writes `band.json`, and `band_line()` draws the prompt line.

## 2. Rulings

1. **Settings**, under `admission.mix`, in the layers `admission` already resolves through: `shares` (a map of family to a positive number, e.g. `{fable: 3, opus: 1}`), `fable_cap` (points of the week, default 50), `resets` (resets in hand at the week's start, default 0), `until` (an optional zoned ISO time, the owner's own deadline ahead of the week's reset), `prices` (per family, USD per million tokens: `input`, `output`, `cache_write`, `cache_read`; defaults fable 8/40, opus 5/25, sonnet 3/15, haiku 1/5, cache_write 1.25 × input, cache_read 0.1 × input). With no `shares`, the mix is off: no new key in `band.json`, every line byte for byte as today.
2. **Spend by family.** Each session's cumulative spend per family, in USD by `prices`, from the turns the meter reads; a helper's turns count under the helper's own model. It reaches the admission ledger as lines admission can sum (a field on `reading` or a new kind, yours to choose; the ledger's shape checks and caps hold). Admission sums a login's week from its own lines only (`scoped`).
3. **Points.** For a login: `counted` is the non-Fable spend since the week's start plus the Fable spend since the last detected reset; `points[f] = P7 × spend[f] / Σ counted`. With `P7` 0 or no spend, the points are None and the line says `mix no reading`.
4. **A reset is detected**, never typed in: on one login, a `seven_day` reading at least 2 points below the one before it, `resetsAt` the same within `SAME_RESET_S`. It starts a phase: Fable's spend counts from that reading; `resets_left = max(0, resets − detected)`. Record the drop beside the Fable points estimated just before it, so the estimate's error is on file.
5. **Next.** Non-Fable families share `100 − fable_cap` points over the whole week; Fable has `fable_cap` each phase. A family is open while under its budget. `next` is the open family with the lowest `points_in_phase[f] / shares[f]`; None when none is open. `reset` is true when Fable is within 1 point of its cap and `resets_left > 0`.
6. **Out.** `band.json` entries gain `mix`: `{points, budgets, shares, next, reset, resets_left, until, phase}`. The prompt line gains one part after the `7d` part: `mix fable 31/50 · opus 9/50 · next opus · resets 2`, `reset now` in place of `next …` when `reset` is true, and ` by <Day HH:MM>` after the resets count when `until` is set. `agentik session rules` gains one pacing item when the mix is on: a helper takes the family the line's `next` names unless its task needs the other; design, refutation and judgment are Fable's, bounded builds, records and reads are Opus's. Advice only: no verdict changes, nothing is held.
7. **Tests.** (a) mix off: a golden band line and `band.json` unchanged. (b) two sessions, Fable and Opus spend 3:1, `P7` 40: points 30 and 10, `next` by `shares`. (c) Fable at 49 of 50 with `resets` 2: `reset` true and the line says `reset now`. (d) the reading falls 75 to 26 with `resetsAt` unchanged: one reset detected, `resets_left` 1, Fable's phase points restart, Opus's stay. (e) a week's reset (a new `resetsAt`) is not a Fable reset. (f) a helper's turns on Opus inside a Fable session count as Opus.
8. Version `2.0.0-alpha.50`, one bump, last; the README count by hand and the sidecar re-hashed, as the repo does.

## 3. Interfaces

`admission.mix` in settings; `mix` in a `band.json` entry; one ledger field or kind for spend. `band()`, `decide()` and `band_line()` keep their signatures. A pure function gives the mix from the scoped rows, `now` and settings, tested alone.

## 4. Findings that name this row

None. First read `agentik decisions find admission` in this repo and agentik-research's `research/synthesis/tools-session.md`; an entry the rulings cross is the one open fork to name, not to decide.

## 5. Forbidden reads

Live transcripts; `~/.local/state`, every part; relay ledgers. Tests build their own.

## 6. Report (at most six lines)

The head sha; the gate's id and its code from the line; each test's name; where a helper's turns are read and how spend reaches the ledger; the estimate's known error sources; anything left over.
