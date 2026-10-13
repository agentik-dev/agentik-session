# Sitting 2026-10-10-1: claude-code-session, packet S19 (the respawn mark, the hooks' stamps and the chain's ledger lines)

| item | value |
|---|---|
| goal | `checkpoint --respawn --charter F` marks a RESPAWN close (`respawn.json`), the hooks stamp `activity.json`, `turn-ended.json`, `helper-activity.json` and confirm with `respawn-main.json`, Stop is registered, the ledger takes restart and stop lines with `report --chains`, `respawn` is a session key, the version is `2.0.0-alpha.3`; 59 `s19` tests red on main, green after |
| budget | 70 turns, 180k context (the packet); land the act in flight at 80%; one commit per act; never push, amend, rebase, a device, the network, or relay in any form; no real `claude` |
| pin | main 50cbdba plus the packet (8e7f190); branch and worktree `s19-respawn-launcher` |
| window | 200k (a builder on a 1M window keeps 180k) |
| agents | 0 (a builder spawned by a hand-run coordinator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: 59 `s19` tests in six files, `59 failed` on unchanged code; the suite collects 645 (main 586)
- [x] act 2: the mark: `charter.RESPAWN`, `next_act_line`; `checkpoint --respawn --charter` refuses first (exit 2, one line, nothing written), then checkpoints and writes `respawn.json`
- [x] act 3: the stamps (`activity.json`, `helper-activity.json`, `turn-ended.json`), Stop (timeout 5, prints nothing), PreToolUse on `*`, `respawn-main.json`; `HOOK_EVENTS` and test_doctor follow
- [x] act 4: `append_chain`, `read` drops `kind` lines, `read_chains`, `restarts_in` fails closed, `report --chains`; the `respawn` key
- [x] act 5: SKILL.md, checkpoint.md, source.md, 2.0.0-alpha.3; the coordinator rendered README.md (0e2034d)
- [x] fix B1: the shim swallows Stop's exit and stdout (`test_s19_shim_never_blocks_stop`: red at 0e2034d, then green); the packet's may touch widened to `plugin/hooks/run`, `tests/test_hook_meter.py`
- [x] fix B2: `CLAUDE_SESSION_CHAIN` in conftest's `INHERITED`; with it exported, test_cli and test_hooks `-k s19`: `3 failed, 26 passed` before, `29 passed` after
- [x] fix B3: a helper's PostToolUse stamps `helper-activity.json`, never the meter (ruling 6 as written); test_s19_helper_activity_stamp and test_hook_meter's two subagent tests: 3 failed before, green after; NICE_TO_HAVE carries S20's open-call record
- [ ] fix notes: done in the tree, NOT committed (a safety guard stopped the commit call): dispatch catches `Exception` (`stop_prints_nothing[deep-json]` red, then green), a binary-stdin test, NICE_TO_HAVE notes, packet at 62. Acceptance: `62 passed`; test_readme `2 failed, 52 passed` (the status line says 645, the suite 648); README 1; sha 2; the suite without test_readme 594 passed

## Handover
1. `make readme` and `make check` are the coordinator's; a changed test count re-renders the status line.
2. Decided (reversible): `append_chain` writes `at` itself only when the entry has none, so a caller may date a line.

- exit taken: stopped at a safety guard; B1 to B3 committed, the notes act uncommitted in the tree

## Next act
The coordinator commits the notes act (hooks.py, test_hooks.py, NICE_TO_HAVE.md, the packet, this charter), re-renders the README (648 tests), then runs `make check`.
