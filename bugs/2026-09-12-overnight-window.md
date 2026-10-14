# Bug report: the 2026-09-12 overnight window (budget reads, hooks, and the scheduled resume)

Filed 2026-09-12 by the example-app v2 coordinator session (Claude Code 2.1.269, claude-code-session at `83d54a6`, wrapper `~/.local/bin/claude-session`). Everything below was measured from `~/.local/state/claude-code-session/` and the session transcript. Times are PDT. The owner disabled the tool at about 04:50 the same morning (status line and the four hooks removed from `~/.claude/settings.json`; backup at `~/.claude/settings.json.bak-2026-09-12-claude-session`).

## Summary

Four defects, in order of damage:

1. **A scheduled resume ends the run while its subagents are still working.** The handoff is the model's structured final output; emitting it completes the `claude -p` process, which kills every background agent. Four builders were cut off mid-edit and their uncommitted work was stranded in worktrees.
   *Dated 2026-10-14:* the premise holds for the Claude Code of the time (2.1.269), not for every version. The changelog's 2.1.292 entry (6 October 2026) reads "Fixed one-shot `claude -p` and Agent SDK runs stopping a background command 5 seconds after the final result, and one-shot `claude -p` runs dropping a scheduled wakeup; both are now waited for". Per the research site's reading of the changelog, 2026-10-14: the stop began at 2.1.163 and ran to 2.1.291, and while a background command runs the 10-minute idle cap does not end the wait. The entry names background commands; whether it also waits for background `Agent` helpers, this bug's case, is not stated.
2. **The first prompt after an idle window roll has no usage sample.** Samples come only from status-line renders. The `UserPromptSubmit` hook and `claude-session budget` both fired before the first render of the new window and reported "no usage sample for a current window", while the account panel read 32 percent used.
3. **`--fork-session` means the resume is never the same session.** The job was told to resume `50a6c2aa`; the run reported `909fac9e`. The parent transcript never sees the work, and the fork queued its own follow-up, which would have forked again beside a live parent.
4. **Stale run notices.** The `SessionStart` hook on 2026-09-11 23:03 announced a run that finished on 2026-09-08 as if it had just finished.

## 1. The run completes with agents in flight

Job `20260912T060405Z-76e61d`, scheduled with `--mode resume --permission-mode bypassPermissions --tools Read,Edit,Write,Glob,Grep,Bash,Agent --model claude-fable-5-1 --grace 120 --timeout 270`.

| measured | value |
|---|---|
| `argv.json` written (start) | 00:16:15 |
| `result.json` and `summary.md` written (end) | 00:55:48 |
| wall clock | 39 minutes of a 270 minute timeout |
| `result.json` | `terminal_reason = completed`, `subtype = success`, `is_error = False`, `num_turns = 104`, `stop_reason = tool_use`, `total_cost_usd = 69.34` |
| list status | `PARTIAL` |

The run's own handoff says the builders "have not reported yet" and lists the merge, gate, and release as not completed. `stop_reason = tool_use` on a completed run is the signature: the model produced the schema-shaped handoff as its final message while four `Agent` tool calls were still running. When the process exited, so did the agents. Measured aftermath in `<code-root>/example-app-wt/row-s1..s4`: each branch had one or two committed entries and 55 to 138 lines of uncommitted diff plus untracked test files.

What would fix it: the runner should not accept a handoff while the session has live subagents, or the instructions should forbid emitting it until every launched agent has reported. A `--drain` option that waits for agents before the handoff is another shape. At minimum `summary.md` should carry a loud line when `stop_reason = tool_use`.

## 2. No usage sample on the first prompt after an idle window roll

The coordinator session (`50a6c2aa`) went idle at 23:29 on 2026-09-11 with the window at 95 to 98 percent (samples at 23:00 to 23:29, `resets_at` 00:10). The window rolled at 00:10. The next prompt in that session was at about 04:27 on 2026-09-12.

| measured | value |
|---|---|
| last sample from this session before the roll | 23:29:40, `used=95`, `resets_at` 00:10 |
| first sample of the new window (`resets_at` 05:10) | 04:27:44 |
| newest sample when `budget` ran at 04:28:01 | 04:27:58, `used=32`, age 3 seconds |
| `claude-session budget` at 04:28:01 | `error: no usage sample for a current window. Point statusLine at ...` |
| `UserPromptSubmit` hook on that prompt | no usage line at all (every earlier prompt carried one) |
| samples by 04:35 | 43 live rows, `used=35` |

Two readings are possible and both are defects. (a) The hook runs before the status line renders, so the first prompt of a window that rolled while the session was idle has no sample; the hook then says nothing rather than saying "no sample yet". (b) `current_sample` at 04:28:01 should have found the 04:27:58 row (window open, age 3 s, within `max_age=3600`) and did not; either the row was appended after its own `t` (the status line writes `captured_at` from the payload, so a late write carries an early timestamp) or the reader loaded a stale file. The code path is `cli.py:470-486` calling `budget.current_sample` (`budget.py:120-140`).

Consequence: the coordinator reported the budget as unreadable and deferred launching agents by 40 minutes until the owner corrected it from the account panel.

What would fix it: on "no sample", fall back to `~/.claude/cache/rate-limits.json` (written by the same status line and present, `captured_at` 04:35:56 when checked) rather than dying; have the hook print "no usage sample yet" instead of silence; and have the status line write `t = time.time()` at append rather than the payload's `captured_at`, or the reader tolerate rows a few seconds in the future.

## 3. `--fork-session` and the chain of forks

`runner.py:52-53`: `argv += ["--resume", job.parent_session_id, "--fork-session"]`. The job for `76e61d` named parent `50a6c2aa` (via `CLAUDE_CODE_SESSION_ID`, as the schedule output printed). The run reported `session_id = 909fac9e-732e-4bfe-8d26-244e1d288e33` and the summary's Resume line names that id.

This is by design, but the design and the hook text disagree: the `UserPromptSubmit` hook says the schedule "resumes this exact session when the window reopens". It does not; it forks. Effects measured this morning:

- The parent session, still open in a terminal, had no knowledge of the fork's work and had to reconstruct it from git, the state directory, and a memory file the fork wrote.
- The fork queued its own continuation (`20260912T071641Z-d7a648`, 05:19) that would have forked `909fac9e` while the parent was live and working on the same trees. The parent cancelled it by hand.

What would fix it: say "forks" in the hook text and the schedule output; refuse to arm a resume for a parent that has a live process (`ps` shows it) unless `--even-if-live`; or, when a fork starts, write its session id back into the parent's state so the parent can find it.

## 4. Stale run notices

`SessionStart` on 2026-09-11 23:03:09 printed: "A scheduled claude-session run finished for this project (20260908T133313Z-8704a9, status CRASHED). Read it with `claude-session show`." That run finished three days earlier and had been shown before. The notice should be acknowledged once (a marker in the run directory) and never repeated.

## Not bugs, recorded for completeness

- The 23:04 reserve readings (97 to 98 percent, "0% of working budget left") match the samples on disk for that window; the first sitting's decision to stop was the tool working as configured. Whether a reserve policy should stop a coordinator that could run shell-time work (gates) is a policy question, not a defect.
- The `PreToolUse` denial in the `76e61d` run ("Bash: cd ... && cat > ds1517/WALK.md <<'EOF' ...") came from `~/.claude/hooks/deny-breakglass-ssh.sh`, not from this tool.
- The `83d54a6` fix held: the 2026-09-12 run did not crash on the schema argument, unlike the three runs of 2026-09-07 and 2026-09-08.

## Repro

1. Open an interactive session with the status line and hooks installed; let it sit idle across a five-hour reset.
2. Type any prompt. Observe: no usage line in the hook context. Run `claude-session budget` within seconds. Observe: "no usage sample for a current window". Wait a minute and run it again: it reads.
3. Schedule `--mode resume` from a session that stays open. When the job fires, `ps` shows both processes; the run's `result.json` carries a different `session_id`.
4. In a scheduled run, launch background `Agent` calls and then let the model write its handoff. Observe `stop_reason = tool_use` in `result.json`, the run marked completed, and the agents gone.
