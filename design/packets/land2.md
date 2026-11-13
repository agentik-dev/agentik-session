# Packet land2: `gate land` refuses what would lose work or land an unchecked tree

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief land2 (hq `history/sessions/BRIEF-2026-11-12-session-land2.md`); NICE n77; hq ledger entry 14 |
| pin | `aee2f99` on main (2.0.0-alpha.89). Version 2.0.0-alpha.90 (re-set at the re-cut). Worktree `.claude/worktrees/land2`, branch `land2`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state (temp repos, a stub check, a patched home); no relay verb; `gate land` itself is never called, the tests drive `land.py` |
| may touch | `plugin/lib/claude_session/land.py`; `plugin/.claude-plugin/plugin.json`; the session skill's `gate land` line; `tests/test_land.py`, `tests/test_land_range.py`, `tests/test_fw4c.py` (R2, R3 and R4's order only); `tests/test_land2.py` (new); `.hygiene-allow` (if the scan asks); `README.md`, `RUNBOOK.md` (the `gate land` paragraphs), `design/readme/{source.md,rendered.sha256}`; this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest of the land files under `.venv` and `.venv-floor` |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_land2.py tests/test_land.py tests/test_land_range.py tests/test_fw4c.py tests/test_unattended.py` green, and under `.venv-floor`; `scripts/hygiene --require-private --commits main..HEAD` exits 0 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin (baseline measured on temp repos)

- Nested: `require_worktree` reads the branch's worktree's status only. A worktree added inside it, under its ignored `.claude/worktrees/`, holding an uncommitted `wip.txt`: the outer status is empty, `land scratch: ok <sha>, main readied`, then `nested exists=False wip exists=False` (`worktree remove` took it).
- Message: hygiene scans the tree and `refs/heads/main..<sha>`, never the merge commit. A merge file `zorblatt lands` with a stub hygiene that reds the term in a range's messages: `ok`, main's subject `zorblatt lands`.
- Behind: main deletes `needed.txt` after the cut, and the stub check needs it: `ok` after the one check in the worktree; the same check on main exits 2.
- The loop's merge file (`unattended.py` `merge_file`) writes `Merge <id>: <heading>`, a blank line, a body.

## 2. Rulings: the requirements (brief land2)

- The owner's words, entry 14: "When the trial ends (2026-12-31), an agentik-session packet makes the loop land each green row through the session plugin's own land". The verb is fixed; the loop's merge file must pass it.
- R1 (`require_worktree`): red `worktree` exit 1 when any other block of `git worktree list` has a directory that exists under the branch's worktree (real paths), clean or dirty; the note names each with its status lines (`STATUS`) or `clean`. Nothing moved or removed. Before the check and after it.
- R2 (`require_no_overlap`, after its conflict test): red `sha` exit 1 when the merged tree is not `<sha>^{tree}`; the note lists `git log --oneline <sha>..main` and says: merge main into `<branch>`, land its new head. Before and after the check. No temp merge is checked.
- R3 (step `merge-file`, before `main`): red `merge-file` exit 1 unless line 1 is `Merge <branch>: ` then a non-space character and line 2, when there is one, is blank; a file with no text says `blank`.
- R4 (after R2, before the check): when `scripts/hygiene` takes `--commits`, `git commit-tree <merged tree> -p refs/heads/main -p <sha> -F <merge-file>` makes a dangling commit, and `scripts/hygiene --require-private --commits <sha>..<commit>` runs in the worktree; non-zero is red `merge-file` with its code. No ref written; main's index and files untouched. No hygiene, or one without `--commits`: no scan.
- R5: R3 and R4 again after the check, with the other re-reads, before the merge.
- R6: the docstring's steps, the README, the RUNBOOK's `gate land` paragraph and the skill's line say the four refusals.
- Decided by the brief: no new step name; check, hygiene, merge keep their order; a nested clone git does not list is not read; no read after the merge; `cli.py` unchanged; the tests' default merge file is `Merge <branch>: <text>`; a test landing a branch behind main merges main first or expects the red.

## 3. Interfaces: the acceptance table (brief land2), pin results in brackets

1. A nested worktree, one untracked and one modified file: `red worktree exit 1`, check not run, both files there, the note naming it and both status lines. [`ok`, both gone]
2. A clean nested worktree: the same red; one whose directory is gone: lands. [`ok` twice]
3. A nested worktree added during the check: `red worktree` after it, main unmoved. [`ok`]
4. Main gains a commit after the cut: `red sha exit 1`, check not run, the note naming it; after `git merge main` in the worktree the new head lands `ok`, main's tree that head's. [`ok`]
5. Main gains a commit during the check: `red sha` before the merge. [`ok`]
6. A merge file empty, blank, `Merge other-row: x`, `Merge work:` alone, text on line 2: each `red merge-file exit 1`, check not run. [`red merge exit 1` after the check for the first two, `ok` for the rest]
7. A stub hygiene redding `zorblatt` in a range's messages, the merge file holding it: `red merge-file` with the stub's code, check not run; argv `--commits <sha>..<commit>`; the commit's parents main and `<sha>`, tree the merged tree, message the file's; no ref at it; main's HEAD, index, status as before. [`ok`, the term on main]
8. The merge file rewritten during the check, to the term or to blank: `red merge-file` after it, main unmoved. [`ok`, or `red merge`]
9. No `scripts/hygiene`, and one without `--commits`: lands, the `ok` line as today's.
10. The loop's merge file passes R3.
11. Every other land test green, changed only for R2 or R3.

## 4. Findings that name this row

- R4 changes the order the hygiene stubs see: `--help` is probed before the check (and again before the merge), so `test_land.py`'s two order lists and `test_land_range.py`'s r1 and r6 change for R4 (the range stub passes a `<sha>..<commit>` scan), beside the R2 and R3 changes the brief allows.
- The README source sat at 16380 of its 16384 B ceiling: the gate queue section's wait bullet was tightened to hold the `gate land` line (16381 B); `key` and the stdout-line clause stay in the RUNBOOK.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger, no hq checkout beyond the brief.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made, what was not done.
