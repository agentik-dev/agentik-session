# Sitting 2026-10-11-2: claude-code-session, C1 (PreCompact) and the siblings made optional (mod-r1 §6, §9)

| item | value |
|---|---|
| goal | §9 finished (doctor treats decisions, respeak, agent-relay as optional; no caret range); C1's PreCompact hook (block `auto`, pass `manual`; the shim maps an old CLI's non-zero exit to 0, N1); 2.0.0-alpha.7; the README source and `make readme` |
| budget | about 90 tool calls, stop at 72; 180k context; one commit per item, a red test first; never push, merge, amend, rebase, `make install`, `claude plugin` install/update, `checkpoint`, relay verbs |
| pin | branch `c1-precompact` off main 2f7f44b, worktree `.claude/worktrees/c1-precompact` |
| window | 1M (a builder keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 0: this charter
- [x] item 1: §9, the siblings optional in doctor (`SIBLINGS`, no range; absent or disabled a `note`; `auto` relay follows agent-relay); red: `5 failed, 60 passed`, `assert ([decisions,...agent-relay] == []`; then 65 passed, lint/doclint/hygiene 0
- [x] item 2: C1, `hooks.pre_compact` (auto: block, one-line reason naming entry 17 and `checkpoint --respawn`; manual or unknown: `{}`), HANDLERS (so the `hook` verb), hooks.json's ninth entry (5 s, no matcher), `HOOK_EVENTS`, the shim's `PreCompact) ...; exit 0` (N1); §6/§8 decided (N2). Red: `28 failed, 50 passed`, `invalid choice: 'PreCompact'`; then 163 passed; gates 0; the README count lines wait for item 4
- [x] item 3: 2.0.0-alpha.7 / 2.0.0a7 in plugin.json, marketplace.json, `__init__`, pyproject; red: `assert ('2.0.0-alpha.6', '2.0.0a6') == ('2.0.0-alpha.7', '2.0.0a7')`; then 79 passed, gates (with validate) 0
- [x] item 4: source.md (siblings optional, no range; the hook list names PostToolBatch and PreCompact; doctor's line); test_readme drops `^0.6`, adds `PreCompact` and an unpinned test; red: `match='ies, by plugin id and range: `decisions ^0.4'`; `make readme`: run 1 (19:26) exit 2, respeak-verify-edit refused (the model dropped the first three headings); run 2 (19:37) exit 0 in 600 s, `PASS (md)`, 822 tests; readme, doctor, precompact tests 136 passed
- [x] verify: `make check` once on the committed tree 2461bd0: exit 0 in 85 s, 822 passed, `readme: fresh`; validate's 9 warnings are the unquoted `${CLAUDE_PLUGIN_ROOT}`, the same shape on every entry

## Handover
- decide, owner: the observer (at landing): RUNBOOK.md §1 step 2 lists the hooks and the shim's dropped exits without PreCompact; outside this packet's files.
- Logged (reversible): doctor's order keeps the siblings where overhaul-r1 §2.4 put them; an unknown plugin list makes a sibling line a note, not a failure (the `plugin` line is already red); `satisfies` stays, unused by doctor, for a later range.
- decide, owner: the observer: NICE_TO_HAVE.md's N1, N2, N3 are done here; strike them at landing (not a file of this packet).
- NICE, for the observer: quote `${CLAUDE_PLUGIN_ROOT}` in every hooks.json command (`claude plugin validate` warns on all nine); the tests pin the commands, so it is one change across them.
- The worktree holds an ignored `.venv` link to the main checkout's venv (the Makefile needs `./.venv`).
- exit taken: done (items 1 to 4 and the verify); never pushed or merged

## Next act
The coordinator: review and merge; the observer: CLI first (`make install`), then `claude plugin update`, then restart.
