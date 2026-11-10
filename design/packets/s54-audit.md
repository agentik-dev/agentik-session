# Packet S54: the audit's a1, a2 and a3

| item | value |
|---|---|
| from | hq `history/sessions/AUDIT-2026-11-09-data-loss-efficiency.md` rows a1 (S1), a2, a3 (S2), reproduced again 2026-11-09 with the probes beside it, `AUDIT-2026-11-09-probes/` (§1) |
| pin | agentik-session main **after S53 lands** (plugin 2.0.0-alpha.51): both change `admission.py`. Worktree `.claude/worktrees/s54-audit`, branch `s54-audit`, `.venv` and `.venv-floor` linked from the main checkout. Line numbers: S53's cba0b70 |
| wall | this repo; no push, `--amend`, rebase, merge, `make install` or `install-cli`; never a bare `make`; no `claude` run but `make check`'s own; a test never writes under the live `~/.local`, `~/.claude`, `~/.config/agentik`; no relay verb; no gate verb under a temp HOME; a `charter close` with no file only in a test's temp directory |
| may touch | in `plugin/lib/claude_session/`: `cli.py`, `charter.py`, `ledger.py`, `admission.py`; `plugin/hooks/session.ts`, `admission.test.ts`; `plugin/skills/session/SKILL.md`; `tests/`; `README.md`, `design/readme/source.md`, `rendered.sha256`; `RUNBOOK.md`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet as `design/packets/s54-audit.md`; a charter |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id>` in one background Bash, last; it exits 0 whatever the job's code: read the code from its line |
| acceptance | T1 to T8 green by name, each red at the pin; no existing test edited but R10's; the verify row green |
| budget | one commit per group (the packet first, then a1, a2, a3, the mod, the bump), by explicit path; stop at 90 tool calls or 140k context with a resume line. `claude-opus-5-5` |

## 1. What the source says

- **a1**, main 344818a, `bash -eu p4_charter_ledger.sh`: A opens `-1.md`, B (`RELAY_ROW=row7`) `-2-row7.md`; A's bare close prints B's path: `exit line in A: 0   exit line in B: 1`. With SessionStart run first, A's `sessions/<sid>/charter.json` names A's file and the close still writes B's: `cli.py:404` reads `charter.newest_today`, never the record.
- **a2**, same run: `report --json: rows 2 summed tokens 10000000 summed turns 100`, one 50-turn transcript (`ledger.py:106`).
- **a3**, S53 cba0b70 (main the same), `p1c_contention.py` on the worktree's launcher: `ledger 20000 lines (6290 KB), 8 at once: written 3, lost 5, exit codes [0, 3]`. One `record` there holds the lock 636 ms: `_write_band` 635.7 (`runs` 398), `_append` 0.1. A scratch copy with R6 to R8: `written 8, lost 0`, `runs` 44 ms, the suite green but for R10's three.

## 2. Rulings

- R1. `charter.bare_target(dir, row, recorded) -> Path`. `recorded` (a string or None) wins when absolute, a file, and its directory resolves to `dir`'s; the target is `Path(dir) / <its name>`, so stdout's first line keeps its spelling. Else today's newest when its name is `<date>-<n><_suffix(row)>.md`. None today: `CharterError`, today's words. Another suffix's newest: a `CharterError` naming it and this suffix's newest today (or `none today`), ending `name the file: charter close <file>`; nothing is written.
- R2. `cli.py:403-406` calls it with `d`, `$RELAY_ROW` and `path` from `sessions/<sid>/charter.json`, read only when `CLAUDE_CODE_SESSION_ID` passes `hooks._SID` and `CLAUDE_SESSION_HELPER` is not `1`; a failure reads as None. A `CharterError` exits 2. A named file is as today.
- R3. `SKILL.md:116`'s comment: `# appends the exit line to this sitting's own charter; name the file when another sitting's is the newest`.
- R4. `ledger.lines(state)`: every session line as `read` parses it, unfiltered. `ledger.fold(rows, since=None) -> (kept, folded)`: each string `session`'s last row, in that row's place (a row without one is kept), then `since` as today; `folded` counts the earlier rows of the sessions kept. `read(state, since)` returns `fold(lines(state), since)[0]`: signature and callers (`cli.py:250`, `:273`) stand, so `report --hooks` counts a session once. The file stays append-only.
- R5. `report`, when `folded > 0`: one line, `folded: <n> earlier rows; a resumed session reads as its last`, on stdout under the table, on stderr with `--json` (still the list). At 0, today's bytes. `README.md:109` and its `source.md` line say so.
- R6. In `record` (`:408`) and `admit` (`:1132`), `_write_band(...)` moves below the `finally` that closes the ledger lock, which then covers rotate, the sweep, the append and the spend line (in `admit`, the read and `decide`).
- R7. `_write_band` (`:1533`) takes `band.lock` (0600) with `LOCK_EX | LOCK_NB`, never waited for: held, it returns silently. The holder reads `ledger.jsonl`'s `(st_ino, st_size)` (None when absent), reads both files, writes `band.json` and `mix.json` as today, closes the lock, reads the mark again and goes round while it moved, at most `BAND_PASSES = 3`. Close before the second mark: then every appended line, and a rotation under the read, meets a build that read it. At the cap the band may trail: it is display.
- R8. `runs` (`:516`): index the dones once by string `agentId` and string `tool_use_id`, each a list of positions in time order; `end` returns the lowest position at or after `t0` over the two keys. Output unchanged.
- R9. The mod's `record()` (`session.ts:304`): exit code 3 (the lock's refusal, nothing written) runs the call once more, `timeoutMs` 3000; no retry on another exit, a rejection or a timeout, since a cut call may have written. One debug line, the last attempt's.
- R10. Words that no longer hold go: "inside the lock" at `admission.py:409`, `:1168`, `:1534`, `session.ts:108`, `RUNBOOK.md:255`; `charter.py:261`'s clause on the bare close. Existing tests edited: `tests/test_admission.py:345` and `tests/test_band.py:145` list `band.lock`; `tests/test_s49.py:801` plants distinct ids; the mod's `refused` case (`admission.test.ts:100`) counts two calls.
- R11. Last: `plugin.json` to `2.0.0-alpha.52`, the last commit under `plugin/` (a later change there bumps again); the status line in `README.md` and `design/readme/source.md` by hand (version, the suite's count), then `design/readme/rendered.sha256` re-hashed (`shasum -a 256`, the two files).

Tests, in `tests/test_s54.py`:
- T1 `test_s54_a1_recorded_charter`: §1's a1 with A's session dir (`request.json`, cwd the repo): the exit line in A's file, B's bytes stand, line 1 `history/sittings/<A's name>`; a record outside `dir` is unused.
- T2 `test_s54_a1_another_suffix_refused`: no session dir: exit 2, stderr names both, no byte changes.
- T3 `test_s54_a2_one_row`: §1's a2: 2 lines in the file; `report --json` 1 row, tokens 5000000, turns 50, R5's line on stderr.
- T4 `test_s54_a2_fold`: R4, clause by clause.
- T5 `test_s54_a3_record_during_build`: `bands` patched to `record` a second session on its first call, `LOCK_WAIT_S` 0.2: both lines kept, `bands` called twice, `band.json` holds the second reading.
- T6 `test_s54_a3_band_lock_not_waited_for`: the test holds `band.lock`: the line appended, `band.json`'s bytes stand, stderr empty.
- T7 `test_s54_a3_runs_linear`: 1,000 spawns, then their dones reversed, rows counting `get`: at most 20 a row (the pin: 1,014,000); `runs` equals the old loop, kept in the test, on seeded random ledgers.
- T8, in `admission.test.ts`: `a record refused with exit 3 runs once more; no other failure does`.

## 3. Interfaces

New: `charter.bare_target`, `ledger.lines`, `ledger.fold`, `admission.BAND_PASSES`, `admission/band.lock`. Nothing else changes shape.

## 4. Findings that name this row

agentik-session keeps no `DECISIONS.md`: no own entry to carry. Bearing, none crossed: agentik-hq 6 (`plugin/lib` on Python 3.9, standard library alone); macbase 22 (which charter is live: unchanged). `design/research.md` §3: `--resume` keeps the session id. NICE: `admit`'s hold still grows with the ledger.

## 5. Forbidden reads

Live transcripts; `~/.local/state`; relay ledgers. Tests build their own.

## 6. Report

Six lines at most: the head sha; the gate's id and its code from its line; T1 to T8 by name; each choice made inside a ruling, with its consumer; leftovers.
