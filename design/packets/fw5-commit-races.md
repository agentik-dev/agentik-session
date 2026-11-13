# Packet fw5: commit, checkpoint and the gate under several writers

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief fw5 and its amendments; NICE n84, n78, n81, n71; hq ledger entries 36 and 40 |
| pin | `f1cbccd` on main (2.0.0-alpha.94; the brief's `aee2f99` moved by its amendments). Worktree `.claude/worktrees/fw5-commit-races`, branch `fw5-commit-races`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` and, in phase 1, no gate job; no `claude`; every test in a temp repo, home and state root, `make` a stub; no relay verb |
| may touch | `plugin/lib/claude_session/{commit.py,cli.py,gate.py}`; `tests/test_fw5.py` (new); `tests/test_fw4d.py` (round-2 tests, R2), `tests/test_cli.py` (its checkpoint `-c` tests, R3); `README.md`, `RUNBOOK.md`, the session skill's `SKILL.md`, the `checkpoint` command; `NICE_TO_HAVE.md` (four rows leave); this packet and the sitting's record |
| verify | phase 1: `python -m pytest` of `tests/test_fw5.py test_fw4d.py test_cli.py test_fw4c.py test_gate.py test_fw2.py` under `.venv` and `.venv-floor`; the gate's `make check` and the version are phase 2's |
| acceptance | §3; `tests/test_fw4c.py`, `tests/test_gate.py`, `tests/test_fw2.py` unedited and green |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then one commit per ruling group |

## 1. What the source says: the code at the pin (measured by `tests/test_fw5.py` at `f1cbccd`)

- `commit` runs `git add -- <paths>` in the shared index before the check, so another writer's plain commit during the check takes this call's paths: theirs holds `a.txt b.txt`, this call `red commit exit 1` (a1); on a red check the moved line, `a.txt` in their commit (a2); during the check `git diff --cached` names `a.txt` (a3).
- `checkpoint --commit -m cp` runs `git add -u` and a plain commit: `a.txt b.txt d.txt` (d.txt staged by another); a path on its line is an argparse error, exit 2.
- A `commit` cut by SIGINT while its `make` check runs leaves the job running: the job's result `exit 0`, `cut` None, after the stub's whole sleep; the next job of that repo starts only then. The verb dies by SIGINT (exit 130 to a shell). A marked entry not yet started runs (exit 127 from the fake spawn's refusal in the unit test: it was spawned).
- `gate run --wait <repo>` under `$CLAUDE_SESSION_GATE_JOB` naming an entry of `<repo>`: queued, position 2 (it waits on the outer job until the wall cuts it); `gate wait <id>` of a queued id of the same key waits.

## 2. Rulings (brief fw5, as amended)

- The owner's words, entry 36: "Commit by explicit path (`git add <paths>`), never `-A`, `-u` or `commit -a`, since several sittings and helpers write in one checkout and a sweep commits another's files."
- R1, n84: before the check the index file is copied to `<git dir>/agentik-commit.witness` and `git add -- <paths>` runs on it (`GIT_INDEX_FILE`); "nothing to commit" and, after a green check, `moved` are asked of the witness. Then in the shared index: `git add -N` for each file the witness holds that the shared index lacks, and `git commit --only -F <f> -- <paths>`.
- R2: FW4d's R1, R2, R5, its stdout lines and the lock stand. Its R4 (snapshot, put-back, the `index moved` line) guards only the span from the `add -N` to the commit; a red check reads `red check exit <code>` even when another writer committed meanwhile. The witness goes on every way out and never reaches the check's environment.
- R3, n78, entry 40: `checkpoint --commit <paths...>` commits the named paths through `commit`'s core with no check, `-m`'s message or today's default; no `add -u`, no untracked note. `--commit` with no path, or a path without `--commit`: exit 2, one line naming the form, nothing committed or recorded. The core's refusals exit 2 the same way; nothing to commit prints `nothing to commit`, recorded, exit 0; a red commit exits 1, nothing recorded.
- R4, n81: on any way out of `commit`'s wait with no result, a mark `gate/queue/<id>.cancel` is written atomically, the signals held, and stderr says `commit-step: check <id> cut`; exit and stdout stay. The runner alone acts on a mark: an entry not started is closed unrun; a running one is cut as the wall cuts; both read exit 130, `cut` "caller cut". No `gate cancel` verb.
- R5, n71: under `$CLAUDE_SESSION_GATE_JOB` naming an entry of this state root, `gate run --wait <repo>` of that entry's key and `gate wait <id>` of a queued id of that key exit 2, nothing queued, a line in `gate land`'s words. Another key, no `--wait`, or a mark with no entry here: as today.
- Decided by the brief: n79 stays a row; the fork on a sweep behind an opt-in is settled no by entry 40.

## 3. Interfaces: the acceptance table, pin results in brackets

1. A green check during which another writer stages `b.txt` and commits plainly: theirs `b.txt` alone, this call `ok <sha>`, its commit `a.txt` alone. [theirs `a.txt b.txt`; `red commit exit 1`]
2. The same, the check red: `red check exit 1`; `a.txt` in no commit, not staged. [the moved line; `a.txt` in theirs]
3. During the check `git diff --cached --name-only` names no path of the call, `GIT_INDEX_FILE` unset. [`a.txt`; unset]
4. A new file and a directory holding one commit on green, a plain commit during the check takes neither; a red pre-commit hook leaves no intent-to-add entry. [`red commit`, the moved line]
5. `checkpoint --commit a.txt -m cp`, `b.txt` edited and `d.txt` staged: `a.txt` alone, `d.txt` staged. [argparse exit 2; `--commit -m cp` takes `a.txt b.txt d.txt`]
6. `checkpoint --commit` with no path, `checkpoint a.txt`: exit 2, HEAD and the index unmoved, nothing recorded. [the sweep commits; argparse exit 2]
7. SIGINT to `commit` on a stub `make` sleeping 30: exit 130; within 10 s the result reads 130, `caller cut`, the stub gone, the next job of the repo started. A marked entry not started: a result, never run. [the job runs out its 30 s, `exit 0`, cut None; the marked entry runs]
8. `gate run --wait <repo> -- /bin/echo inner` under the mark of a running entry of `<repo>`: exit 2, no entry. [queued, position 2] Without `--wait`, another repo, a mark with no entry: queued as today.
9. `test_fw4c.py`, `test_gate.py`, `test_fw2.py` unedited, green.

## 4. Findings that name this row

- R2 changes `test_fw4d.py`: its three round-2 tests (another writer's commit or staging during a red check, SIGTERM after another writer's commit) now read the plain `red check` line, or none for the signal, nothing of this call staged; its two r1_f3 tests reach the restore that cannot be made by a red commit holding `index.lock`, since a red check no longer restores.
- R3 changes `test_cli.py` beyond its two checkpoint tests: four respawn tests ran `-c` with no path (s19's helper refusal and its control, s22's tracked and untracked charter) and now name their paths. A modified tracked charter passes `--respawn` with `--commit` only when the line names it.
- `test_readme.py`'s status line (3455 tests, the README's count) reds at 3473 collected: the count is phase 2's, with the version.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger, no hq checkout beyond the brief.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.

## 7. Review 1's fix

- F1: when another writer moved the shared index between this call's `add -N` and a commit that then failed, the call left its intent-to-add entry there (a later `commit -a` took the new file) and stderr said none of its paths was staged.
- Ruling: on that branch the call removes its own entries still intent-to-add, under index.lock and no other entry; `_tell_moved` names every path of the call still staged or intent-to-add with its `restore --staged` line and says the move came after the check, during the commit.
- Another writer's `git checkout -- <path>` during the check now discards this call's change, which follows from R1: nothing of the call is staged while the check runs (NICE n171 holds the way back).
