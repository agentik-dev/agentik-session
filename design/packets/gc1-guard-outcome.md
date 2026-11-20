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

- `_bash_gated`'s end: a line the strict reading cannot split, or with a target it cannot resolve, and that the loose reading does not deny, logs `open` with path None and passes. 18,292 lines in 160 logs, 18,182 of them `a target cannot be resolved`; every one path null. `f=CLAUDE.md; echo x >> "$f"` passes and writes.
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

The new files under `sessions/<sid>/guard-open/` (0700; each 0600): `<tool_use_id>.json` holds `{"at", "files": [[path, reading], ...]}`, a reading `["sha256", hex]`, `["size", bytes, mtime_ns]`, `["absent"]` or `["other"]`; `<tool_use_id>.said` holds `{"paths": [...]}`, a change waiting to be said. A `changed` log line carries `call`, the tool call's id.

## 4. Findings that name this row: the choices inside the rulings

- The lists in force that exist (the checkout's, each folder's, the user's) are read first, then the files they name by a plain path; the 64 counts both. In a worktree a folder's line is read in the member and in the worktree.
- A reading is `sha256`, `size` past 1 MiB, `absent`, or `other` (no regular file, or one that cannot be opened; opened non-blocking, so a FIFO never hangs).
- The said line names a path relative to the call's folder, `~/` under the home, else whole; several are sorted, comma-joined, with `are` and `them`. The log keeps the whole path.
- It follows the handler's words (the CHECKPOINT line, then pl2's respawn line), and the gate's lines and a sitting's line follow it. Where it does not fit `MAX_OUT` it waits in a `.said` file like a failure's; UserPromptSubmit says it with no cap.
- The call's file is removed before the second reading, so two Posts never log one change twice; the folder goes when empty, so a Post with nothing waiting costs one failed `listdir`. Pre now 0.79 ms, Post 0.37 ms (medians of 400, five gated files).
- The Edit tools' `the target cannot be resolved` line is not named by R1 and stays; doctor counts it a guard error. A `.said` file is not pruned by R4. A call another hook denies after the gate leaves its file, which R4 removes after a day.
- NICE: n141 leaves (no `open` line now); n175 and n118 re-worded to what remains; n179, n180 and n189 say their lines are read, so not held (the packet's probe). n346 to n352 from pl2's review 1.

## 4a. Fix of review 1 (brief 2)

Review 1: B1, the said line named every path twice, so two worktree paths never fit `MAX_OUT`,
waited and swallowed each later change; B2, a corrupt `.said` file lost the change.

- F1: after the `changed` lines the paths join the session's one waiting record,
  `guard-open/waiting.said` (`{"paths": [...]}`, replaced under a lock on the folder), before
  anything else; a hook takes them out only once its line is in its output. Read strictly: not
  a list of strings is corrupt, removed, one `open` line with its `why`, read as empty.
- F2: the model's line `agentik-session: <shown> is gated and changed during a Bash line the
  gate could not read. If that line ran the lane, nothing is wrong. Otherwise restore it and use
  the instruct skill.`; the owner's `agentik-session: a gated file changed during a Bash line
  the gate could not read: <shown>`. `<shown>`: the first path sorted, ` (+N more)`; past 48
  characters `…` and the last 47. The pair beside `{}` at most 480 bytes; said where it fits
  after the handler's words, taking every waiting path.
- F3: a waiting path (and a log line's) is the real path, `~/` under the home; F4: g2b's split
  and unresolved cases assert the call's file; F5: NICE for L4, L6, L7, L9 to L11.
- Choice: the literal drawing with ` (+69 more)` is 488 bytes, so the tail is cut further
  until the pair fits 480 with `UserPromptSubmit`'s name.
- Choice: UserPromptSubmit caps the pair as PostToolUse does; its inbox block stays alone.

## 4b. Fix of review 2 (brief 3)

Review 2: B1, the one waiting record was written under an `flock` on `guard-open/`, which
another main-thread Post removed when empty, so the write failed and a change was logged and
never said; B2, a directory at the record lost every change; B3, a FIFO there hung a Post.
This section replaces F1's one record under a lock; F2's bound and texts, F3 and F4 stand.

- H1: a change that waits is its own file, `sessions/<sid>/guard-said/<ns>-<pid>-<k>.said`
  (`{"paths": [...]}`, 0600), its bytes written to `.<name>.tmp` in that folder and renamed in;
  never rewritten. No lock is taken anywhere in the outcome check.
- H2: a main-thread PostToolUse or UserPromptSubmit lists the folder, reads at most 256
  entries, each only a regular file of at most 65,536 bytes, opened `O_NONBLOCK|O_NOFOLLOW`. F2's
  line is made from every path read; only once it is in the output are the files read removed,
  those alone. At least once is the rule: two hooks at once may each say one change.
- H3: an entry that is no regular file, too large, or no list of strings is one `open` line
  (`a bad waiting entry: <why>`), removed when it can be (`rmdir` for an empty folder) and else
  skipped; nothing raises or waits. A temp older than a minute is removed.
- H4: no hook removes `guard-open/` or `guard-said/`; each is made on demand with its parents.
  A write into either that fails is made again once, its folder first.
- H5: a change that cannot be written is one guard error; a main-thread PostToolUse says it in
  its own output where it fits.
- H6: a control character in a drawn path, a newline included, is drawn `?`.
- H7: NICE for review 2's L1, L5, L6 and L9.
- Choice: the call's file is opened directly (one failed `open` when absent), not found by a
  listing, and read by the same safe reader; a bad one is removed.
- Choice: a non-empty folder planted in `guard-said/` is skipped and logs at each saying Post;
  no tree is removed by a hook.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
