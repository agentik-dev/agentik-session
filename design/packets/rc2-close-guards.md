# Packet rc2: the launcher says an unconfirmed mark's hold, and a close with a background job out is refused once

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief rc2-close-guards (rc1's two wish-list leads, NICE n336 and n337) |
| pin | `dc6b78d` on main (rc1 landed, 2.0.0-alpha.143). Worktree `.claude/worktrees/rc2-close-guards`, branch `rc2-close-guards`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `tests/test_chain.py` and `tests/test_rc1_respawn_confirm.py` unedited; `_ready`, `_checks`, `_step`, `_decide` keep their results |
| may touch | `plugin/lib/claude_session/chain.py` (`_watch`); `plugin/lib/claude_session/hooks.py` (`pre_tool_use`, `_post_tool_use`, `user_prompt_submit`, the `jobs/` helpers); `tests/test_rc2_close_guards.py` (new); `plugin/skills/session/SKILL.md`, `RUNBOOK.md`; `design/respawn-r1.md` §3.3, §3.9, change log; `NICE_TO_HAVE.md` (two rows out, six in, one sighting); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file, `tests/test_chain.py`, `tests/test_rc1_respawn_confirm.py`, `tests/test_hooks.py`, `tests/test_hook_meter.py`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `Chain._watch` goes on past a poll only when `respawn-main.json` parses; with no confirm it polls and says nothing, so a marker that stands unconfirmed leaves no `held.json` and `status` prints no hold. At the child's exit `_decide`'s check (a) gives `not-main`.
- `_post_tool_use` confirms a close and runs the meter; it records nothing of a background Bash call. `user_prompt_submit` reads no `<task-notification>` block. `pre_tool_use` refuses a background close (rc1) and passes a foreground one whatever is still running.

The owner's words, 2026-11-20, on the two leads rc1 left in the wish list: "Please take on the wish list items as well".

What was measured, in made-up names: a launched sitting's marker stood four hours with no confirm and no hold was said. In the same sitting a background job (a merge, a check, a push and a tag in one script) started at 20:17 was still out when the mark was written at 21:27 and ended at 21:34; a confirmed mark would have let the launcher's signal end it before its push. The Bash result carries `backgroundTaskId`; the job's end reaches an idle main thread as a `<task-notification>` prompt naming `<tool-use-id>` and `<task-id>`. Not measured: that the hook's `prompt` holds the block.

## 2. Rulings (brief rc2)

- R1 the hold is said: in `_watch`, with no confirm, a marker of the running sitting whose `written` is at least `settle` old is the hold `not-main` through `_say_held`; nothing is signalled; a later confirm runs as today and clears the file; a marker that does not parse, names another session or is younger says nothing.
- R2 a record per job: the main thread's Bash PostToolUse with a non-empty string `backgroundTaskId` in an object `tool_response`, or `run_in_background` true, writes `sessions/<sid>/jobs/<tool_use_id>` `{at, task}`, atomic and private, for an id `calls/` accepts. Never raises.
- R3 the notice closes it: each `<task-notification>` block of a main-thread prompt, every posture, removes the record its `<tool-use-id>` names or whose `task` its `<task-id>` names. No block costs one substring test; a fault leaves the records.
- R4 refused once: a main-thread foreground respawn close (rc1's predicate), every posture, with a record that has no `asked`: one line under 900 characters opening `agentik-session: ` with the count, up to five start times then `and N more`, that the restart ends any still running, and that the close passes when run again; then each record gains `asked`. No `calls/` file; the guard's failure passes.
- R5 the words: the runbook and the skill; respawn-r1 §3.3 step 2, §3.9's first point, a change log line. The README is left (§4).
- R6 the NICE rows: n336 and n337 leave in the commits that build them; one row for a notice that comes mid-turn, five from rc1's review 1, a sighting on n301.

## 3. Interfaces: the acceptance table (baseline measured at `dc6b78d`)

Tests in `tests/test_rc2_close_guards.py`; at the pin 32 of its 35 cases are red, the three that pass being the markers that give no hold.

| # | line | at the pin |
|---|---|---|
| 1 | a marker of the sitting, no confirm: no `held.json` before `settle`, `{reason: "not-main", since, session}` after; `held_line` prints it; no signal | no file is ever written |
| 2 | a confirm naming the marker's bytes, a ready turn: the signal and the restart as today; the file gone | no hold to clear |
| 3 | the exit while held: `not-main`, the file removed; a marker not parsing, of another session, or with no `written`: no hold | `not-main`; no file |
| 4 | the record: with `backgroundTaskId`, `run_in_background` alone; none for a foreground result, a helper, a bad id, a non-object result | no `jobs/` |
| 5 | the notice: by call id, by task id, neither, two blocks, a block cut short, a helper's prompt; under `off` | no `jobs/` |
| 6 | the refusal: asked once then passes, a later job asks again, seven records, none, a background close, a helper, the guard's failure; `signal`, `off`, `deny`; no `calls/` file | the close passes |
| 7 | record, notice, a close that passes first time | passes |
| 8 | `tests/test_chain.py`, `tests/test_rc1_respawn_confirm.py` unedited and green | green |
| 9 | `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row

- The README's source is unchanged since rc1 measured it ten bytes under its cap (16,370 bytes at the pin), and it is rendered by a model run this wall forbids; its RESPAWN sentence is left as it is.
- A notice that arrives mid-turn fires no prompt hook, so its record stays open and the close asks once about a job that has ended (D4: never a hold).

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
