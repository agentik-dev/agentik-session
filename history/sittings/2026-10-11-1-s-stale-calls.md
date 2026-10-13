# Sitting 2026-10-11-1: claude-code-session, the stale `calls/` fix (respawn-r1 §3.3 ruling 2)

| item | value |
|---|---|
| goal | a helper's call that another PreToolUse hook blocks (no PostToolUse, no PostToolUseFailure) must not hold `_ready` forever; a live long call still holds it; `_ready`'s other conditions unchanged |
| budget | 70 tool calls (the coordinator's brief), stop at 56; 180k context; one commit per act; never push, amend, rebase, `make check`, `make install`, `claude plugin`, `claude-session run` or `checkpoint`; the live state dir is read only |
| pin | branch `s-stale-calls` off main 4a2e376, worktree `.claude/worktrees/s-stale-calls` |
| window | 1M (a builder keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: 9 red `s22` tests (chain 2, hooks 5, doctor 2); on main 4a2e376 `9 failed`: `_ready` is False a day after the turn ended, `calls/toolu_01blocked` still open; option chosen: PostToolBatch (fires once every call of a batch has resolved, the blocked one included; claude 2.1.296's hook enum and schema carry it with `agent_id` and every `tool_use_id`)
- [x] act 2: `hooks.post_tool_batch` (a helper's batch stamps, then closes each listed `calls/<id>`; the main thread's writes nothing); hooks.json registers PostToolBatch at 5 s; the shim drops its exit as for Stop; `doctor.HOOK_EVENTS` and the pinned lists follow; RUNBOOK §1 step 2 and §4; NICE_TO_HAVE's no-batch gap. Three files: 175 passed; lint exit 0
- [x] act 3: whole suite, the main checkout's `.venv` python, cwd the worktree, `PYTHONPATH=<worktree>` (`claude_session.__file__` printed the worktree's): 791 passed, 2 failed, both `test_status_line_matches_manifest_and_suite` (README says 784, the suite holds 793); doclint 0; hygiene 0 after a sibling name left a test comment

## Handover
- open by level: the no-batch gap (NICE_TO_HAVE.md)
1. decide, owner: the observer (at landing): `make readme` renders the 793 count; design/readme/source.md's hook list also lacks PostToolBatch. Not run here (respeak, a relay night may be live).
2. decide, owner: the observer (at install): CLI first (`make install`), then `claude plugin update`; until then the doctor's `plugin` line names PostToolBatch as unregistered. The plugin's version is not bumped here.
3. Logged (reversible): PostToolBatch over a transcript read (§3.3 and §3.8: the launcher never opens or stats a transcript) and over SubagentStop (a blocked call in a live helper would wait for the helper's end).
- exit taken: done (acts 0 to 3); stopped before `make check`, the observer's

## Next act
The coordinator: review and merge; the observer: `make check`, `make readme`, then the install (CLI first).
