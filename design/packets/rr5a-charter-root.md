# Packet rr5a: session finds a repo's records through the resolver, the charter folder first

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief rr5a-charter-root (the first of rr5's three rows; hq design/28 §3 items 1 to 5 and 18, §11 leads 1 and 9; commons GUIDE §12); the owner's words below |
| pin | `00d96cf` on main (rc3-respawn-short and hk1-hook-rows landed, plugin 2.0.0-alpha.152). Worktree `.claude/worktrees/rr5a-charter-root`, branch `rr5a-charter-root`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; commons read-only but for its `scripts/sync` run into this worktree |
| may touch | `plugin/lib/claude_session/records.py` (new), `cli.py` (the charter verbs, `_records_here`, `agentik_setup`, `_respawn_check`), `hooks.py` (`_charter_reminder`, `_post_meter`, a sibling of `_charter_file`), `charter.py` (`show`'s refusal hook), `doctor.py` (one row), what `scripts/sync` places, `tests/test_rr5a_*.py`, the tests the newer scanner moves, this packet, the sitting's charter |
| verify | pytest under `.venv` and `.venv-floor` on the new files and the touched modules' tests; `scripts/doclint`; `scripts/hygiene --require-private --commits main..HEAD`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the sync, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- The charter folder is `--dir`, else `session.charter.dir`, else `history/sittings`. `open` and a bare `close` take it relative to the working directory; `show` relative to the git top, or to each REPO.
- The record of the open is written only when the folder is `<the session's cwd>/<dir>` (`_records_here`); the hooks' `_charter_file` names the recorded file only when it lies in `<cwd>/<dir>`; SessionStart's reminder globs `<cwd>/<dir>`; `agentik_setup` reads `<top>/history/sittings`, the key ignored.
- No code reads `git config`; session vendors no `agentik_records.py` and no `agentik_term/`.

The owner's words: the coordinating repo's entry 63, verbatim: "Each of agentik's public tools keeps its working records in agentik-hq. As a tool's row lands, its charters, packets, wish list and questions move to agentik-hq/repos/<tool>/ and leave the public tree in one commit; what is already pushed stays in the public history (design/28)." 2026-11-20: "continue with the charter". Entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief rr5a)

- R1, the sync: commons' `scripts/sync` from its main, in a commit of its own; nothing synced is edited here. No `records: out` line.
- R2, one read: `records.answer(folder)` runs `agentik_records.resolve` in a child killed as a process group at `gitinfo`'s 5 s, once a folder a process. Past the bound or on any fault it answers `failed`, which every caller reads as `broken`, with the reason `timeout` or the fault's one line. It never raises.
- R3, `own` is the pin, byte for byte, in every verb's output, exit and writes and every hook's output.
- R4, `out`: the charter folder is `<records>/<dir>` (`--dir` wins as today, and an absolute one is not joined), from the main checkout, a subfolder and a worktree alike, for `open`, `check`, `close`, `show` and each REPO, the record of the open, `agentik_setup`, SessionStart's reminder and the CHECKPOINT line: the absolute path where the recorded file lies directly in `<records>/<dir>` and passes `_SAFE_PATH`, else `<this sitting's charter>`.
- R5, `unset` and `broken`: `open` and `close` with no file and no `--dir`, and `checkpoint --respawn` with no `--charter`, refuse with one line and exit 2: the key to set; for `broken` its value and the reason. `show` reads no charter and says the state beside the repo. The hooks never refuse: SessionStart asks for no charter and says the `broken` line once; the CHECKPOINT line is the waiver's.
- R6, the hot path: PreToolUse, a silent PostToolUse, Stop and UserPromptSubmit start no process they did not start at the pin.
- R7, doctor's `records` row: `ok`, `in the repo` (`own`); `ok`, the folder (`out`); `warn`, the key (`unset`); `warn`, the key, the value and the reason (`broken`).
- R8, not this row: `checkpoint --commit`, the close's commit line, reconcile, `lines`, `stamp`, doclint, `unattended`.

## 3. Interfaces: the acceptance table (baseline read at `00d96cf`)

| # | line | at the pin |
|---|---|---|
| 1 | each state in a temp clone with a temp holder: `open`, `check`, `close`, `show`, `show A B` give R3 to R5; in `out` the file is under the holder, nothing in the clone | the key ignored: every state writes in the clone |
| 2 | `out` from a worktree and a subfolder: the main checkout's folder | the worktree's, the subfolder's |
| 3 | `--dir` relative and absolute in `out`: R4 | relative to cwd |
| 4 | the hooks in each state: the reminder, the CHECKPOINT line off and under a launcher, the record of the open; the resolver stubbed to raise and to sleep | `<cwd>/<dir>` in every state |
| 5 | R6: `subprocess.Popen` counted in four hooks, `own` and `out` | no resolver child |
| 6 | a stub `git` that sleeps 30 s: `broken`, `timeout`, within 6 s, the group gone | no read |
| 7 | doctor's `records` row in each state, text and JSON | no row |
| 8 | every test of the pin passes, but those the newer scanner moves | |
| 9 | the median of 30: a silent PostToolUse process, `charter show` in `own` | 66.6 ms, 74.9 ms |
| 10 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row: the choices inside the rulings

- (filled as the build goes)

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
