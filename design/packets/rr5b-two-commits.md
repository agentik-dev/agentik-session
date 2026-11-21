# Packet rr5b: where a repo's records live outside its clone, session commits a record in the folder's own repository

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-21, brief rr5b-two-commits (the second of rr5's three rows; hq design/28 §3 items 4, 12, 14 to 16; commons GUIDE §12; rr5a's review 2, its ruling 1); the owner's words below |
| pin | `89be323` on main (rr5a-charter-root landed, plugin 2.0.0-alpha.154). Worktree `.claude/worktrees/rr5b-two-commits`, branch `rr5b-two-commits`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; commons read-only |
| may touch | `plugin/lib/claude_session/cli.py` (`cmd_checkpoint`, `cmd_charter`'s `check` and close, the help of `checkpoint`), `commit.py` (a pre-check and the sha a commit made), `reconcile/live.py` (`since_landing`), `RUNBOOK.md` (one sentence), `tests/test_rr5b_*.py`, this packet, the sitting's charter |
| verify | pytest under `.venv` and `.venv-floor` on the new files and the touched modules' tests; `scripts/doclint`; `scripts/hygiene --require-private --commits main..HEAD`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `checkpoint --commit <paths...>` runs `commit.commit_paths` in the cwd's work tree: one lock, one witness, one `commit --only`. In `out` a record path is refused as `<p> is outside the repo at <top>`, so no record can be committed through the tool.
- The respawn's clean check and the close's commit line run git in the file's folder: the holder in `out`. `charter check FILE` reads FILE in every state. `since_landing` logs `history/sittings` in the hq.

The owner's words: the coordinating repo's entry 63, verbatim: "Each of agentik's public tools keeps its working records in agentik-hq. As a tool's row lands, its charters, packets, wish list and questions move to agentik-hq/repos/<tool>/ and leave the public tree in one commit; what is already pushed stays in the public history (design/28)." 2026-11-21: "Read the newest charter under history/sittings and act from its Next act". Entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief rr5b)

- R1, `own` is the pin: `checkpoint --commit`, the close's commit line, the respawn's clean check and reconcile give the pin's output, exit and writes byte for byte; `checkpoint --commit` starts the resolver at most once.
- R2, the split: in `out` each path on the line is sorted by its real path: under the work tree the call stands in, the clone's; under `records`, a record; under neither, the pin's refusal in the pin's words. The clone's paths make one commit through `commit_paths`; the record paths one in `holder` through the same core (its lock, its witness, `commit --only`). One message for both.
- R3, refuse before either: `_require_state` and `_require_paths` hold for both repositories before the first commit; a refusal names its repository and leaves both untouched.
- R4, the order and the half: the clone's commit, then the holder's, one lock at a time. Where the first stands and the second is red or refused, one line says the clone's commit stands (its sha) and names the record paths not committed; the exit is the second's; the same verb with those paths alone commits them. `nothing to commit` in one does not stop the other, and the line says which.
- R5, no holder: the clone's paths commit; one line says the record paths are in no repository and nothing of them is committed; the exit is the clone's.
- R6, `unset` and `broken`: the clone's paths as at the pin. In `broken`, `charter check FILE` refuses a FILE whose real path lies in the clone, with the state's line, exit 2.
- R7, the readers: `_named` matches a charter under the records folder against the record paths named; the close's commit line commits that file alone in its own repository whatever else is staged there, and with no holder the close says nothing is committed; `since_landing` in `out` runs its log in `holder` over `<prefix>/history/sittings`, and prints the command it ran.
- R8, the words: entry 8 of this repo's ledger is not amended. The two commits are the paths named and nothing else, each in the repository that holds it: "commits the paths named on its line and nothing else" holds of two commits as of one. `RUNBOOK.md` and `checkpoint`'s help say the second commit in one sentence each.
- R9, not this row: `lines`, the reconcile record's path, `stamp`, doclint, `unattended`, the hooks. No `records: out` line.

## 3. Interfaces: the acceptance table (baseline read at `89be323`)

| # | line | at the pin |
|---|---|---|
| 1 | `out`: a code file and the charter make one commit in each, each its own paths; a stranger staged in each stays staged and out | refused: the charter is outside the repo, exit 2 |
| 2 | only record paths: one commit, in the holder; only code paths: one, in the clone, the holder untouched | the first refused; the second as now |
| 3 | R3: a path under neither, a holder mid-merge, a record path `git add` refuses: exit 2, no commit in either, the line names which | each refused as outside the repo |
| 4 | R4: the holder's lock held past the wall, a red holder `pre-commit`: the clone's commit stands and is named with the record paths, exit not 0; a second run with the record paths commits them | refused before the clone's commit |
| 5 | R5: the records folder in no repository: the clone's commit, one line, exit 0 | refused |
| 6 | R1: `own`: the pin's tests of `checkpoint --commit` pass unchanged; a counted `Popen` shows one resolver start at most | no resolver start |
| 7 | R6: `charter check FILE`, each state, FILE in the clone and outside it | read in every state |
| 8 | R7: `--respawn --commit` with the record charter named and not named; the close's line run from another cwd with a stranger staged in the holder; `since_landing` in `own` and `out` | the respawn refused at the commit; the line holds; `since_landing` reads the clone |
| 9 | no test reads the live home, `~/.claude` or live state; every repository a test commits in is a temp one | |
| 10 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row: the choices inside the rulings

- `own`, `unset`, `broken`, and `out` with no record path named run the pin's code (`_commit_one`); the one resolver start is `records.answer(cwd)`.
- A path is the clone's when its real path (`commit._where`) is the work tree's top or under it, else a record when it is the records folder or under it; it goes to the holder relative to the holder's top.
- `commit.precheck(cwd, paths)` makes the core's refusals (a snapshot not put back, `_require_state`, `_require_paths`) with no lock, for each repository, before the first commit; the core makes them again under its lock. The line names `the clone at <top>` or `the records' repository at <holder>`; under neither, the pin's line.
- `commit_paths` gains `got`, a list the `ok` sha is appended to under the lock, so the half's line names the clone's own commit.
- The half's line exits with the holder's code (git's 1 for a red hook, 124 for its lock, 2 for a refusal) and records nothing; the second run records. A red clone exits 1 as at the pin, the holder not tried, the record paths named.
- `nothing to commit in the clone` (or `in the records' repository`) prints, and the checkpoint records.
- No holder: one stdout line, `... the records folder is in no repository, so nothing of the record paths is committed: <paths>`.
- `_named` needs no change: it already matches by real path, so a record charter or a folder holding it passes; a test says so. The close's line (`git -C <dir> add -- <name> && git -C <dir> commit ... -- <name>`) already commits the file alone (a path given to `git commit` is `--only`); a test with a stranger staged in the holder says so. With no holder, `_charter_dirty` reads unknown, and the close then asks the resolver and prints `next: nothing is committed: the records folder is in no repository`.
- `charter check` asks the resolver in every state (as `--dir` did); in `broken` a `--dir` or any FILE in the clone refuses the whole call before a file is read.
- `since_landing` in `out` runs the charters' log in the holder over `<prefix>/history/sittings`; its commit count stays the hq's own log; `out` with no holder reads the hq, as at the pin.
- The README source is unchanged: its line holds, and it is 14 bytes under its bound.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

To the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices, what was not done.
