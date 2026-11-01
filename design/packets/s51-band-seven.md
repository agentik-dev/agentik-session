# Packet S51: a new login's week on the band line

| item | value |
|---|---|
| from | the owner's ask of 2026-11-01 10:0xZ, on logging into another account: the status rows must show a new login's weekly window. agentik-hq HANDOFF 17's path, S3 |
| pin | agentik-session main d641fd3, alpha.42; worktree `.claude/worktrees/s51-band-seven`, branch `s51-band-seven`, `.venv` and `.venv-floor` linked |
| wall | this repo; no push, `--amend`, rebase, merge, real `make install` or `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config/agentik`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME |
| may touch | `plugin/lib/claude_session/admission.py`, the hook or module that draws the band and cache lines, `tests/`, `README.md`/`design/readme/*` for the count only, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`, this packet as `design/packets/s51-band-seven.md`, a charter |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log>"`, then `agentik session gate wait <id>` in one background Bash, last; it exits 0 whatever the code: read the code from its line |
| budget | 40 tool calls, 80k context; `claude-opus-5-5` |

## The evidence

At 10:05Z the owner had switched to a Max login. The ledger (`admission/ledger.jsonl`) holds this session's reading `[{"kind": "seven_day", "percentUsed": 3, "resetsAt": "2026-11-02T23:00:00.000Z"}]`, with no `five_hour` item. `band.json`'s `accounts` holds the new key `2026-11-02T23:00Z` as `{"mode": "observe", "at": …, "window": "five_hour", "slot": "Mon-2300Z"}` and nothing else. The prompt line reads `5h no reading · observe`, with no 7d figure, week reset, demand band or cache line. The old login's entry (`window: none`) showed `no 5h window · 7d 100% · week resets Fri 13:00 · band best to …`. So the account switch is detected: a new key, and the session is mapped to it. Its week is dropped.

The cause, read in code: `admission.band()` (about `:1199`) returns `out` alone when a five-hour login has no fresh five-hour reading (`if not fresh: return out`), so `P7`, the seven-day reset and the demand band are never computed for it. `_line` then draws `5h no reading` and finds no `P7`.

## Rulings

1. With no fresh five-hour reading, a five-hour login's entry still carries what its seven-day reading gives: `P7`, `resetsAt`/`until` from the seven-day reset with `bound` seven-day, and `demand` as `_band_none` computes it. `P`, `peak` and `room` stay None. Nothing about admission's verdicts changes: no reading is still `unread`.
2. The line reads `5h no reading · 7d 3% · week resets Mon 15:00 (…) · band …`, the same parts and order `_line_none` uses for the week, with `5h no reading` first.
3. The cache line (`cache 1h (within plan usage, 7d N%)` / `cache 5m (past plan usage …)`) reads that `P7`, so a new login under its plan says `cache 1h` again. Find where it is drawn and say in the report.
4. Tests. (a) A ledger with login A's readings (five-hour and seven-day, 7d 100%) and then, for the same session id, login B's seven-day-only reading at 3%: `session_band` for that session is B's, with `P7` 3, B's week reset, and the line holding `7d 3%` and `week resets`. A's entry is unchanged. (b) The cache line for that session reads within plan. (c) A five-hour login with a fresh five-hour reading draws as before, byte for byte, through a golden or an existing test.
5. Version `2.0.0-alpha.43`, one bump, last; the README count by hand and the sidecar re-hashed, as the repo does.

## Report (at most six lines)

The head sha; the gate's id and its code from the line; each test's name; where the cache line is drawn; anything left over.
