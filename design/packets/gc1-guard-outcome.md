# Packet gc1: where the edit gate cannot read a Bash line, it holds its rule by the outcome

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief gc1-guard-outcome; the owner's words below |
| pin | `0f618ff` on main (pl2 landed, 2.0.0-alpha.145). Worktree `.claude/worktrees/gc1-guard-outcome`, branch `gc1-guard-outcome`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; no real shell line writes a gated file of a real checkout (the gate is exercised through the hook functions on fixture repos under a temp dir); `shellreader.py`, `lineguard.py`, the lists' format, the lane, the shim and every denial's reason unchanged |
| may touch | `plugin/lib/claude_session/instructionguard.py` (`_bash_gated`, `log`, `counts`, `doctor_row`, the new outcome functions), `plugin/lib/claude_session/hooks.py` (`post_tool_use`, `_post_tool_use`, `post_tool_use_failure`, `_gate_ups`), `plugin/lib/claude_session/doctor.py` (`_check_guard`); `tests/test_gc1_outcome.py` (new) and the assertions that pinned a retired `open` line or the guard row's words; `RUNBOOK.md` §1's guard lines; `NICE_TO_HAVE.md`, `history/NICE-overflow.md` (six rows tidied, seven in); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file and the guard's files; `scripts/doclint`, `scripts/recordlint`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_bash_gated`'s end: a line the strict reading cannot split or resolve, that the loose reading does not deny, logs `open`, path None, and passes: 18,292 lines in 160 logs. `f=CLAUDE.md; echo x >> "$f"` passes and writes.
- `counts` returns (0, refusals, `open` lines); `doctor_row` says `N refusals, M let through on an error`; `_check_guard` is `ok` whatever the counts.
- The shim drops PostToolUseFailure's output. A helper's PostToolUse returns `{}` before any work but its stamp and close.

The owner's words, 2026-11-20: "Put a new Fable advisor to look for design defects in our suite. Look for the best 3 things to do for our repos and then farm them out to Opus workers when it comes back with a decision." This row is the advisor's pick 2.

## 2. Rulings (brief gc1)

- R1 where the pin logs `open` for the two unread reasons it logs nothing and writes `sessions/<sid>/guard-open/<tool_use_id>.json`: each file a gate list in force here names by a plain path, its sha256 or a mark that it is absent; at most 64; past 1 MiB by size and mtime. Nothing to record, or no id: no file, no line. The line passes; a failed write is a guard error.
- R2 PostToolUse and PostToolUseFailure of a Bash call, a helper's too and before its early return: the call's file read, the same reading taken again, the file removed; each path that differs, appeared or went is one `changed` line with its path and the call's id. No file, no work.
- R3 a change is said once, to the model and in `systemMessage`, within `MAX_OUT`, the checkpoint line first. A change at PostToolUseFailure, or a helper's, waits in a file and is said by the main thread's next PostToolUse or UserPromptSubmit, then removed.
- R4 a call's file older than a day is removed, unread, by the next write into the folder.
- R5 an `open` line for a guard exception alone; the doctor's row `N refusals, M guard errors, K gated files changed by an unread line`, `warn` when M or K is above 0; the two retired reasons count as neither.
- R6 the readings, `lineguard.py`, the lists, the lane, every denial and its reason, the shim stand. It never blocks and never restores.
- R7 the runbook says the outcome check; NICE n175, n179, n180, n189, n141, n118 tidied; pl2 review 1's L1, L2, L4, L6, L7, L9, L11 in, L1 first.

## 3. Interfaces: the acceptance table (baseline measured at `0f618ff`)

Tests in `tests/test_gc1_outcome.py`.

| # | line | at the pin |
|---|---|---|
| 1 | `f=CLAUDE.md; echo x >> "$f"` passes and writes the call's file; Post names the path in the model's line and `systemMessage`; one `changed` line; the file gone | passes; one `open` line, path null; Post says nothing |
| 2 | the same line, nothing changed: no output, no line, no file | one `open` line |
| 3 | `echo x >> CLAUDE.md` denied, the same reason, no file | denied |
| 4 | a gated file created and one removed: a `changed` line each | nothing |
| 5 | seen at PostToolUseFailure: logged; said once by the next PostToolUse, or a UserPromptSubmit first; never twice | nothing |
| 6 | a helper's change logged and said to the main thread once | nothing |
| 7 | doctor: one `changed` line is `warn`, counts 1; old `open` lines alone `ok` | `ok` always |
| 8 | 400 unread lines, nothing changed: `guard.jsonl` +0 B, `guard-open/` empty | +52,873 B |
| 9 | 70 plain paths and a 2 MiB file: 64 recorded, the large by size and mtime, its change seen | nothing recorded |
| 10 | one Pre and one Post for an unread line, five gated files, timed | Pre 0.36 ms, Post 0.11 ms (medians of 200) |
| 11 | `make stamp`, then `make check` green through the gate | |

`sessions/<sid>/guard-open/<tool_use_id>.json` (0600, its folder 0700): `{"at", "files": [[path, reading], ...]}`, a reading `["sha256", hex]`, `["size", bytes, mtime_ns]`, `["absent"]` or `["other"]`. A `changed` line carries `call`.

## 4. Findings that name this row: the choices inside the rulings

- The lists in force that exist (the checkout's, each folder's, the user's) are read first, then the files they name by a plain path; the 64 counts both. In a worktree a folder's line is read in the member and in the worktree.
- A reading is `sha256`, `size` past 1 MiB, `absent`, or `other` (no regular file, or not opened; a FIFO never hangs).
- It follows the handler's words (CHECKPOINT, then the respawn line); the gate's lines follow it.
- The call's file is removed before the second reading: two Posts never log one change twice.
- The Edit tools' `the target cannot be resolved` line stays, a guard error. A call another hook denies leaves its file for R4.
- NICE: n141 leaves; n175, n118 re-worded; n179, n180, n189 say their lines are read. n346 to n352 in.

## 4a. Fix of review 1 (brief 2)

Review 1: B1, two worktree paths never fit and swallowed later changes; B2, a corrupt record.

- F1 (replaced by §4b): one waiting record a session, under a lock, taken once said.
- F2: the model's and the owner's lines are `SAID` and `SAID_OWNER`; `<shown>` the first
  path sorted, ` (+N more)`; past 48 characters `…` and the last 47. The pair beside `{}`
  at most 480 bytes, said where it fits after the handler's words, taking every path.
- F3: a waiting path (and a log line's) is the real path, `~/` under the home; F4: g2b's split
  and unresolved cases assert the call's file; F5: NICE for L4, L6, L7, L9 to L11.
- Choice: ` (+69 more)` drawn literally is 488 bytes, so the tail is cut until it fits 480.
- Choice: UserPromptSubmit caps the pair as PostToolUse does; its inbox block stays alone.

## 4b. Fix of review 2 (brief 3), replacing F1's one record under a lock

Review 2: B1, the lock sat on `guard-open/`, which a Post removed, so a change went unsaid.

- H1: a waiting change is its own `guard-said/<ns>-<pid>-<k>.said` (`{"paths": [...]}`), by
  rename from `.<name>.tmp`, never rewritten; no lock. H4: no hook removes a folder.
- H2: a main-thread Post or prompt reads at most 256 entries, each a regular file of at most
  64 KiB (`O_NONBLOCK|O_NOFOLLOW`); the files read go once F2's line is out. At least once.
- H3 (replaced by J2): any other entry one `open` line. H5: a failed write is tried once more,
  then a guard error, said in its own Post. H6: a control character drawn is `?`. H7: NICE.

Review 3: B1, a call's paths past 64 KiB of JSON made a file the reader refused (brief 4).

- J1: `_hold` splits one call's paths across waiting files, each within 64 KiB; none dropped.
- J2, replacing H3's "removed if it can be": in `guard-said/` the check lists, reads, counts and
  removes only a regular file (`lstat`) named `<ns>-<pid>-<k>.said` or its temp
  `.<that>.<pid>.tmp`; any other entry is left as it is, unread, uncounted, unlogged. A bad file
  of its own naming is one guard error and removed; the minute's sweep takes its own temps only.
- J3: a `guard-said` or `guard-open` that is no real folder by `lstat`, a link included, is not
  used; a change that cannot be held is said at its own main-thread Post with room. One guard
  error a session: the marker `<folder>.unfit` beside it.
- J4: NICE for review 3's B2, L3, L5; `hold()` goes. Choice: `SAID_LOOK` counts own names only.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
