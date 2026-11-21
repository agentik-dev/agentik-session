# Packet rr5b: where a repo's records live outside its clone, session commits a record in the folder's own repository

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-21, brief rr5b-two-commits (the second of rr5's three rows; hq design/28 §3 items 4, 12, 14 to 16; commons GUIDE §12; rr5a's review 2, its ruling 1); review 1's ruling (build 2); the owner's words below |
| pin | `89be323` on main (rr5a-charter-root landed, plugin 2.0.0-alpha.154); build 2 from `10b994f`. Worktree `.claude/worktrees/rr5b-two-commits`; `.venv`, `.venv-floor` linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; commons read-only |
| may touch | `plugin/lib/claude_session/cli.py` (`cmd_checkpoint`, `cmd_charter`'s `check` and close, `checkpoint`'s help), `commit.py` (a pre-check, the sha made), `records.py` (`inside`), `reconcile/live.py` (`since_landing`), `RUNBOOK.md` (one sentence), `NICE_TO_HAVE.md`, `tests/test_rr5b_*.py`, this packet, the charter |
| verify | pytest under `.venv` and `.venv-floor` on the new files and the touched modules' tests; `scripts/doclint`; `scripts/hygiene --require-private --commits main..HEAD`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls a build, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `checkpoint --commit <paths...>` runs `commit.commit_paths` in the cwd's work tree: one lock, one witness, one `commit --only`. In `out` a record path is refused as `<p> is outside the repo at <top>`.
- The respawn's clean check and the close's commit line run git in the file's folder: the holder in `out`. `charter check FILE` reads FILE in every state. `since_landing` logs `history/sittings` in the hq.

The owner's words: the coordinating repo's entry 63, verbatim: "Each of agentik's public tools keeps its working records in agentik-hq. As a tool's row lands, its charters, packets, wish list and questions move to agentik-hq/repos/<tool>/ and leave the public tree in one commit; what is already pushed stays in the public history (design/28)." 2026-11-21: "Read the newest charter under history/sittings and act from its Next act". Entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief rr5b)

- R1, `own` is the pin: `checkpoint --commit`, the close's commit line, the respawn's clean check and reconcile give the pin's output, exit and writes byte for byte; one resolver start at most.
- R2, the split: in `out` each path is sorted by where it is (`commit._where`): under the work tree, the clone's; under `records`, a record; under neither, the pin's refusal in the pin's words. Review 1's F1, ruled: a named link in the clone whose real path is under `records` is refused before either commit, exit 2, since its blob would publish the folder's path; a link under `records` into the clone commits in the holder. One commit each through `commit_paths` (its lock, witness, `commit --only`); one message.
- R3, refuse before either: `_require_state` and `_require_paths` hold for both repositories before the first commit; a refusal names its repository and leaves both untouched.
- R4, the order and the half: the clone's, then the holder's, one lock at a time. Where the first stands and the second is red or refused, one line names the clone's sha and the record paths, absolute, and the line that commits them, with the call's `-m` shell-quoted; the exit is the second's. `nothing to commit` in one does not stop the other, and the line says which.
- R5, no holder: the clone's paths commit; one line says the record paths are in no repository; the exit is the clone's.
- R6, `unset` and `broken`: the clone's paths as at the pin (D5; F4, ruled: a path under a record name there is rr5c's). In `broken`, `charter check FILE` refuses a FILE in the clone, the state's line, exit 2. F2: "in the clone" is `records.inside`, judged by file identity as the resolver judges it, never by spelling.
- R7, the readers: `_named` matches a record charter by its real path; the close's line commits that file alone in its own repository, and with no holder the close says nothing is committed; `since_landing` in `out` logs `<prefix>/history/sittings` in `holder` and prints the command it ran, the folder quoted (F3).
- R8, the words: entry 8 is not amended: "commits the paths named on its line and nothing else" holds of two commits, each in the repository that holds it. `RUNBOOK.md` and `checkpoint`'s help say the second commit in one sentence each.
- R9, not this row: `lines`, the reconcile record's path, `stamp`, doclint, `unattended`, the hooks. No `records: out` line.

## 3. Interfaces: the acceptance table (baseline read at `89be323`; 11 at `10b994f`)

| # | line | at the pin |
|---|---|---|
| 1 | `out`: a code file and the charter make one commit in each, each its own paths; a stranger staged in each stays staged and out | refused, exit 2 |
| 2 | only record paths: one commit, in the holder; only code paths: one, in the clone | the first refused |
| 3 | R3: a path under neither, a holder mid-merge, a record path `git add` refuses: exit 2, no commit in either, the line names which | refused as outside |
| 4 | R4: the holder's lock past the wall, a red holder `pre-commit`: the clone's commit stands and is named with the record paths, exit not 0; a second run commits them | refused first |
| 5 | R5: the records folder in no repository: the clone's commit, one line, exit 0 | refused |
| 6 | R1: `own`: the pin's tests of `checkpoint --commit` unchanged; one resolver start at most | none |
| 7 | R6: `charter check FILE`, each state, FILE in the clone and outside it | read |
| 8 | R7: `--respawn --commit`, record charter named and not; the close's line from another cwd, a stranger staged; `since_landing` in `own` and `out` | the respawn refused |
| 9 | no test reads the live home, `~/.claude` or live state; every repository a test commits in is a temp one | |
| 10 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |
| 11 | review 1: a case-spelled clone folder (skipped where case counts) and a failed stat read as inside; a space in the clone's folder; F1's link refused; the half's line absolute with `-m` | red at `10b994f` |

## 4. Findings that name this row: the choices inside the rulings

- `own`, `unset`, `broken`, and `out` with no record path named run the pin's `_commit_one`; the one resolver start is `records.answer(cwd)`.
- `commit.precheck(cwd, paths)` makes the core's refusals with no lock for each repository before the first commit; the core makes them again under its lock. `commit_paths` gains `got`, the `ok` sha read under the lock.
- The half's line exits with the holder's code (git's 1 for a red hook, 124 for its lock, 2 for a refusal) and records nothing. A red clone exits 1 as at the pin, the holder not tried.
- No holder: one stdout line naming the record paths; the close asks the resolver only where `_charter_dirty` reads unknown.
- `_named` and the close's line already held at the pin; tests say so.
- `charter check` asks the resolver in every state; in `broken` a `--dir` or any FILE in the clone refuses the whole call.
- `inside` walks the spelled and the real path, each folder up to the root, against the tops' (device, inode): no top, not inside; tops none of which stat, inside. F1 is judged on the named path alone, not inside a named folder.
- `since_landing` quotes only the holder's folder; `own` keeps the pin's bare `history/sittings`. Its commit count stays the hq's log.
- The README source is unchanged: its line holds, 14 bytes under its bound.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

To the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices, what was not done.
