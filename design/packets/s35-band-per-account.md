# Packet S35: the band is drawn per account; a reading's seven-day reset names its login

| item | value |
|---|---|
| from | NICE_TO_HAVE "The band mixes accounts" (2026-10-14, seen live, S3); `design/admission-r1.md` §3.2 (the fit) and §3.5 (the band); packet S27b (band.json and its twins) |
| pin | `main` at d49c2b8; branch `s35-band-per-account`, worktree `.claude/worktrees/s35-band-per-account` |
| wall | this repo; no push, `--amend`, rebase, merge, `git stash`, device, network, real `claude` session, `agentik session run`, `claude plugin install`, `update` or `marketplace`, `make readme`, `make install` or `make check`; one make at a time; `claude plugin test plugin` is allowed under `scripts/bounded --wall 60 --`; tests write in temp dirs only, never in the account's state directory; never run `relay` or `agentik relay` with any verb; never build or run a relay binary; never `pkill -f` |
| may touch | `claude_session/admission.py`, `claude_session/hooks.py` (`_admission_line`, `_lifetime` and their callers' session id), `claude_session/cli.py` (`cmd_rules`' band read only), `plugin/hooks/session.ts` (`admissionLine` and the render's band read), `plugin/hooks/session.test.ts`, a new `tests/test_s35.py`, `RUNBOOK.md` (the band's paragraph), `design/admission-r1.md` (§3.5, one sentence), `NICE_TO_HAVE.md` (a new heading at the end only), `tests/test_mod.py` (criterion 3's `_admission_line` call pin only, act 2), this packet, `history/sittings/2026-10-16-2-s35.md` |
| acceptance | 1: `.venv/bin/python -B -m pytest tests -q -k s35 2>&1 \| tail -1` reads `passed`, no `failed` (pin: the s35 tests fail); 2: `.venv/bin/python -B -m pytest tests -q -k "admission or band or admit" 2>&1 \| tail -1` reads `passed`, no `failed`; 3: `make lint doclint 2>&1 \| tail -2` exits 0 |
| verify | `make check` (it runs the mod's tests), by the coordinator, after this branch |
| budget | acts: 1 this packet; 2 the s35 tests red, then the fix green; 3 the RUNBOOK and admission-r1 text. 50 turns, stop at 42 (commit the act in flight), 150k; one commit per act |

## 1. What the source says

`admission.band()` takes the newest five-hour reading across every session in the ledger, with no account key, and `fit`, `_active` and `_rise` count every session's readings and helpers. Two logins on one Mac therefore share one band. On 2026-10-14 the ledger held two accounts at once: one with its five-hour reset at 21:10Z and its seven-day window at 81%, the other at 22:30Z and 3%. Each session's prompt line showed whichever account wrote last, and the projection and `room` were fitted across both. The owner now switches this Mac's sessions to a second account at a reset, so sessions on both accounts overlap within the hour.

The statusline gives no account id. A reading's reset times fingerprint one: the seven-day `resetsAt` is fixed for an account's week, and the five-hour one moves every window and can coincide across accounts.

## 2. Rulings

1. **The key.** `admission.account(rateLimits)` is the seven-day window's `resetsAt` in UTC, truncated to the minute (`2026-10-20T21:10Z`). A list with no dated seven-day `resetsAt` keys as unknown (`None`). At an account's weekly reset its key moves: the old key stays in the ledger up to 29 hours, and the new key's fit starts from the seeds until `MIN_INTERVALS` accrue. That is accepted.
2. **A line's account.** A reading line with a key belongs to its own key. Every other line belongs to its session's account: spawn, done, end, verdict, start, and a reading with no key. A session's account is the key of its own newest keyed reading. (This refines "newest reading": "keyed" means one reading without a seven-day window does not drop a session to unknown.) A session with no keyed reading has no account.
3. **The scope.** When the ledger's readings hold two or more keys, these use only the lines of the session's account: a session's band (`P`, `resetsAt`, `until`, `P7`, the rise, `fit`, `_active`, `_rise`, `runs`, `room`, the held verdicts), and an `admit` verdict's projection. Its key comes from the request's own `rateLimits` first, else from its session's account. Every line is used, as today, in three cases: the ledger holds fewer than two keys; the session has no account; the session's key is unknown. A lone account's band.json and verdicts therefore stay byte for byte the pin's.
4. **band.json.** The top level stays `band()` over every line, exactly as today. It is the fallback, and what a reader that knows no accounts draws. With two or more keys the file gains two keys. `accounts` maps each key to `band()` over that account's lines, in the same shape as the top level. `sessions` maps each session id to its key. At most 16 keys are kept (newest reading first) and 256 sessions (newest first), so the file stays under `BAND_MAX`; a session beyond the cap draws the top level. With one key, neither key is written. The shape grows. It does not change: every old field keeps its place and meaning.
5. **The readers.** `admission.session_band(b, sid)` returns `accounts[sessions[sid]]` when both are present and the value is an object, else `b` (a `None` stays `None`). These read through it: the prompt hook's band line (`_admission_line`), the cache lifetime (`_lifetime`, both callers) and `cmd_rules`, whose session id comes from `CLAUDE_CODE_SESSION_ID` and falls back to the top level when that is absent. In `session.ts`, `admissionLine(band, nowMs, id)` picks the same object. The id is the session dir's last part, which is what `mod start` prints. One shared fixture in `session.test.ts` (`BAND_TWO`, with a line per id) pins both twins, and the old-shape fixture `BAND` still draws `BAND_LINE`.
6. **Nothing else moves.** These stay as they are: `report`'s windows, `record`'s checks, the ledger's line shapes, the verdict's keys, the mode, and `band_line`'s text for a given object.
7. **Tests**, each name holding `s35`:
   - (a) Two accounts' readings, interleaved (A: five-hour reset 21:10Z, seven-day 81%; B: 22:30Z, 3%), each with a helper in flight. Each session's band, through `session_band`, has its own `P`, `resetsAt`, `P7`, `running` and `room`. A spawn's verdict projects from its own account's `P`. The prompt hook shows each session its own line.
   - (b) A lone account: band.json equals `band()` over every line and has no `accounts`.
   - (c) A session with no reading, and one with only unkeyed readings, both draw the top level.
   - (d) The key: truncated to the minute, and unknown with no seven-day window.
   - (e) The twins: `band_line(session_band(BAND_TWO, id), NOW)` equals the TypeScript fixture's line for each id, an unknown id draws the top level, and the TS tests assert the same.

## 3. Interfaces

band.json gains two optional top-level keys, `accounts` and `sessions`, written only when the ledger holds two or more accounts. A reader that ignores them draws the top level, as before; this repo's readers pick the session's account. `admission` gains `account`, `session_band` and an internal split by account. `session.ts`'s `admissionLine` gains an optional third argument. No ledger line, verb, flag or hook changes. Say in the charter's handover whether the repo's practice moves the version for this, and do not bump it in this branch.

## 4. Findings that name this row

NICE_TO_HAVE's "The band mixes accounts" (2026-10-14): S35 answers it, and the builder's notes go under a new heading at the end, never into the entry itself. The relay's own band pacing reads band.json's top level from its own repo. It keeps working unchanged, and moving it to per-account is that repo's row.

## 5. Forbidden reads

Transcripts; `~/.claude/projects`; the account's state directories (the session plugin's and the relay's), the live ledger and band.json among them. Read no other repo.

## 6. Report (capped)

At most 150 words: each acceptance line's tail, the s35 tests red on the pin, whether band.json's shape changed, any ruling beyond §2, and the head sha.
