# Packet u1: a stale helper call never holds the launcher

| item | value |
|---|---|
| from | the coordinating repo's finding of 2026-11-10, a stale call held the respawn (S2); the coordinator's rulings |
| pin | agentik-session main `36c84ea` (2.0.0-alpha.60). Version: plugin 2.0.0-alpha.61, or the next free. Worktree `.claude/worktrees/u1-stale-call`, branch `u1-stale-call`, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live state or writes under the live home; no relay verb |
| may touch | `plugin/lib/claude_session/{chain,ledger}.py`; `tests/test_u1.py` (new); `tests/test_{chain,ledger}.py` (R4 only); `RUNBOOK.md`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/{source.md,rendered.sha256}` (status line); this packet as `design/packets/u1-stale-call.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| overlap | `chain.py` with `r2-reconcile-verb` (its pass in `_chain`); none in code with `n33-helper-door`; all three touch `plugin.json`, `NICE_TO_HAVE.md`, the status line |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_u1.py`: 12 green (pin: `9 failed, 3 passed`), and under `.venv-floor`; `test_chain.py`, `test_ledger.py` green with R4's edits alone; every other test unedited and green; verify green |
| budget | a commit per group by explicit path, the packet first; stop at 50 tool calls or 100k context. `claude-opus-5-5` |

## 1. What the source says

Outputs: the probes README.
- A helper's PreToolUse writes `sessions/<sid>/calls/<tool_use_id>`, only `{"at": <epoch>}` (`hooks.py:165`, from `:186`; `_call`, `:149`, needs `agent_id`). PostToolUse (`:634`), PostToolUseFailure (`:665`) and PostToolBatch (`:683`) remove it; nothing else does.
- `_ready` is False while any non-dot file stands in `calls/`, reading no age (`chain.py:577-583`).
- `hooks.json` registers ten events, no SubagentStop. `hooks.jsonl` and `.1`: PreToolUse 17,268, PostToolUse 16,983, PostToolBatch 15,173, UserPromptSubmit 354, Stop 279, PostToolUseFailure 186, SessionStart 21, SessionEnd 20, SubagentStop 0. SubagentStop was seen with `agent_id` at a helper's normal end on 2.1.296 (`design/respawn-r1.md:224`), never measured for a helper a rejection ends.
- The night (claude 2.1.322): the call opened 21:03:14.8; 0.6 s later `User rejected tool use`, the helper's last line. On disk: 41 call files, 10 after the s22 fix.
- `p3_ready.sh` (the night's session's stamps, scratch home, both pythons): at 23:20:06, 00:19:05, 02:42:00, `call open: _ready=False  no call: _ready=True`.
- The bound: Bash's ceiling is 600 s; ten days of helper transcripts, 153,889 calls, longest 668 s, 0 over 1,200 s. A call held 20 minutes at a permission prompt after the turn's end reads stale.

## 2. Rulings

- R1. `chain.STALE_CALL = 1200`; `Chain(..., stale_call=STALE_CALL)`, a keyword as `poll`, no config key. `_ready` reads each non-dot call file, `calls/` first as today: stale when `now - max(at, helper stamp) >= stale_call`, `at` the file's, else its mtime; no stamp reads as `at`; a malformed one holds. A live call: False. A True keeps `[{"id", "age"}]`, whole seconds from `at`.
- R1's word. When `_step` ends the child, the list becomes `went_past`. After the exit and `tty_restore` (`respawn-r1.md:132`, silence while a child runs), before the grace line: `<chain>: went on past a stale helper call: <id> open <age // 60> min`, `; ` between calls. The restart line's last key, `stale_calls`: the list or null. The stop line is unchanged.
- R2, the root, a NICE row (S3, `hooks.py`): SubagentStop is neither registered nor seen. Lead: register it, the call file gains `agent_id`, the handler removes that helper's calls; measure first with the owner rejecting a scratch helper's call.
- R3, a NICE row (S4, `chain.py`): a line while the child runs breaks §3.7; lead: `held.json` names the call past 5 minutes, `status` prints it.
- NICE, S4, `chain.py` `_stop`: the no-marker stop line says how to restart the chain.
- R4. `test_s20a_waits_for_the_turn[helper-open-call]` closes its call at 1100, `earliest` 1160; `test_s22_live_call_still_holds_ready` (a day later) builds with `stale_call=2 * 86400`; `test_ledger.py` `S19_KEYS["restart"]` ends `"stale_calls"`. RUNBOOK's respawn paragraph, a sentence with T11's words. Last, the version and the status line. Nothing else: marker, grace, checks, stops, hooks.

`tests/test_u1.py` (probes): red at `36c84ea`, green on `prototype.patch`, 3.12.7 and 3.9.6:

| T | the test shows | item | red at the pin |
|---|---|---|---|
| 1 | the night's session folder at 23:20:06: ready, the call listed | R1 | False |
| 2, 6 | without the call ready; a malformed stamp holds | control | green |
| 3 | `STALE_CALL` 1200: 1199 s held, 1200 s ready | R1 | no attribute |
| 4, 7 | a later stamp, a live call and its Post hold for the bound | R1 | False |
| 5 | an unreadable call reads its mtime (2 cases) | R1 | one False |
| 8 | fake clock: TERM at 1212 s, the line after the tty, `stale_calls` | word | no TERM |
| 9 | a call closed at 1100 s: TERM at 1160, `stale_calls` null | word | no key |
| 10 | `RESTART_KEYS` ends `stale_calls`; `STOP_KEYS` 10 | word | `start_model` |
| 11 | RUNBOOK's sentence | R4 | absent |

## 3. Interfaces

New: `chain.STALE_CALL`, `Chain(stale_call=)`, `went_past`; `RESTART_KEYS` `stale_calls`.

## 4. Findings that name this row

No agentik-session ledger. Bearing, uncrossed: the coordinating repo's 6 (3.9 floor, stdlib) and 17; the machine ledger's 20. Forks: R2 and R3 to NICE (marked, as recommended).

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T11 under both pythons; choices; leftovers.
