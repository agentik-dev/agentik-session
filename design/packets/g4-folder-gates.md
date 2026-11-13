# Packet g4: the folder layer of the edit gates, and one glob grammar

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief g4 (hq `history/sessions/BRIEF-2026-11-12-session-g4-folder-gates.md`); design of record hq design/12 §3.2, §3.4, §3.5; the owner's decision 31 |
| pin | `8d676ce` on main (g2b merged, 2.0.0-alpha.86). Version 2.0.0-alpha.87. Worktree `.claude/worktrees/g4-folder-gates`, branch `g4-folder-gates`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or a real list (temp folders, a patched home); no relay verb |
| may touch | `plugin/lib/claude_session/instructionguard.py`; `plugin/.claude-plugin/plugin.json`; `tests/test_g4_folder_gates.py` (new); `.hygiene-allow` (a row for the new test if the scan asks); `README.md`, `RUNBOOK.md`, `design/readme/{source.md,rendered.sha256}`; this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | the table in §3; `.venv/bin/python -m pytest -q tests/test_g4_folder_gates.py tests/test_g2b_gates.py` green, and under `.venv-floor` (the g4 file red at the pin); `scripts/hygiene --require-private --commits main..HEAD` exits 0 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- The hook reads two lists: the checkout's `.claude/edit-gates` (the nearest folder above the target holding `.git`; lines relative, a leading `/` or a `..` part matches nothing) and the user's (`CLAUDE_CONFIG_DIR`, else `~/.claude`). `_match` (instructionguard.py:128) is `fnmatchcase` on the whole relative path, so `*` crosses `/` (NICE n136, F8). `_removes_list`, `listing`, `count_here` know the two lists only.

## 2. Rulings: the requirements (brief g4)

- The owner's words, decision 31: "The gate lists are layered as the instruction files are. The owner's list, ~/.claude/edit-gates, holds the user-scoped files, the global CLAUDE.md among them. A folder's list covers every repo under that folder. A checkout's list holds its own files. The agentik tools (render, answer, the instruct skill, gates write) write all three layers and manage them alike; no hq writes a member's list by hand."
- R1, the folder layer: for the path written, each `<folder>/.claude/edit-gates` in a folder above it and strictly below the home folder, other than the path's own checkout's list; lines relative to their folder. A path not under the home folder reads none. A file in no checkout is matched the same way.
- R2, a worktree: a path in `<member>/.claude/worktrees/<n>/` is matched against a folder list as `<member>/<rel>`; the member is found from the path's spelling, no process.
- R3, one grammar, every layer: `*`, `?`, a bracket match within one segment; a segment exactly `**` matches any depth, none included; a line with no glob is one file.
- R4: a folder's or a checkout's line starting with `/` or `~`, or holding a `..` part, matches nothing; `gates write` on a folder list refuses a draft holding one and writes nothing.
- R5: each folder list is gated with no line, by Edit and Bash, and its removal forms.
- R6: `gates` prints the checkout's list, then each folder's from the nearest up, then the user's, each with its file and its lines' count; the doctor's `guard` row counts all layers.
- R7: the deny reason, fail open, no knob, the log and its cap unchanged. R8: the RUNBOOK says a line is a real path, in every layer.
- Decided for the builder: the folder list is `<folder>/.claude/edit-gates`; no constant names a code folder; nothing reads an hq's checkout.

## 3. Interfaces: the acceptance table (brief g4)

1. A folder list `*/CLAUDE.md`, `*/DECISIONS.md`: Edit of `<member>/CLAUDE.md` denied with today's reason; `<member>/docs/x/CLAUDE.md`, `<member>/notes.md` allowed; the same through Bash (redirect, tee, sed -i, cp, bash -c, python).
2. The member with no list of its own; the folder's list absent and the member's present: each gates what it lists.
3. A worktree under `<member>/.claude/worktrees/<n>/`: its `CLAUDE.md` denied by the folder's `*/CLAUDE.md`.
4. `<folder>/CLAUDE.md` with the line `CLAUDE.md`: denied; the folder's list file denied unlisted, by Edit, by Bash, and its `rm` and `mv` from.
5. Grammar: `*.md` does not gate `deep/a/b.md` in any layer; `**/x.md` gates `x.md` and `a/b/x.md`; `hooks/**` every depth; a folder line with `/`, `~` or `..` matches nothing.
6. Two nested folder lists both apply; a sibling folder's never; a path outside home reads none.
7. `gates write <folder>/.claude/edit-gates --from <draft>`: preview writes nothing; `--expect` writes; a refused line exits non-zero, nothing written.
8. `gates` in a member prints three layers; the doctor's row counts them.
9. No spawn, no argv; a Bash line with no write word opens no file; an exception gives `{}` and one `open` line.

## 4. Findings that name this row: ledger, NICE, forks

- R3's question, answered by the round-1 refuter: the gate lists in use when this packet was cut hold no glob, so no line of a list that exists today changes meaning under the one grammar.
- Round 1 (plugin 2.0.0-alpha.89): F1, `gates write` decides a folder's list as `gated()` does (the absolute spelling and the real path, folded where the volume folds case), so a case variant or a link outside home is refused too; F2, the matcher answers each (segment, part) pair once, so many `**` segments no longer take exponential time.
- NICE n135 (F7) and n136 (F8) close with this packet. agentik-decisions' `list_gate` learning the layer is its own change (design/12 §3.5), not this packet's.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout, no real gate list.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made, what was not done.
