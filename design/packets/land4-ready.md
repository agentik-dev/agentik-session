# Packet land4-ready: the landing job readies the branch itself

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief land4 (S3); hq design/19 §3 items 1 (the dry run), 2, 5, 6, 9; §6's row land4 |
| pin | `d364bf4` on main (2.0.0-alpha.115, the merge of gl1-gate-record). Worktree `.claude/worktrees/land4-ready`, branch `land4-ready`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue, once, last); no `claude`; each test repo made up in a temp folder (its own HOME, state, identity), none queueing in the live gate or reading live state; no relay verb |
| may touch | `plugin/lib/claude_session/land.py`, `plugin/lib/claude_session/cli.py` (`_gate_land`, the `land` parser), `tests/test_land4_ready.py` (new), `plugin/skills/session/SKILL.md` (the `gate land` line), `NICE_TO_HAVE.md` (a row), this packet, `history/sittings/2026-11-14-3-land4-ready.md`; in the last commit alone, the stamp's files |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3; `tests/test_land4_ready.py` green under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet, the failing tests, the change |

## 1. What the source says (baseline measured at `d364bf4`)

A reviewed branch main has passed is `red sha` today, and a hand merges main, stamps and checks again. The job gains a step, **ready**, which does that where safe, in a repo that asks. The owner's word: the job may write on a reviewed branch, "those lines only".

Measured at the pin on a made-up repo `crate` (temp HOME, nothing queued; `check:` and `stamp:` in its Makefile; `p1-crate` one commit behind main, no conflict), by `gate land --in-job`:
- the note `main holds what <sha> does not, so the check would not run on the tree main would hold:`, main's commit, `merge main into p1-crate, land its new head`; then `land crate: red sha exit 1`, exit 1; main and the worktree as they were.
- `--in-job --dry-run` and the four: `unrecognized arguments: --dry-run`, exit 2; a fifth argument: `land ?: red usage exit 2`, exit 2.
- These match the brief's figures at `5890501` (alpha.106).

## 2. Rulings (brief land4)

- R1, where. Ready runs in `land`, after the first `worktree` read and before `sha`'s read of main. It runs only when the worktree's `Makefile` holds a line that opens `stamp:`. Without one, every line and exit is the pin's, byte for byte, a branch behind main included.
- R2, the reads first. With `git merge-tree --write-tree` of the head and main, nothing written: main's head an ancestor of the branch's is no merge (go to R5); no conflict is a merge; conflicts whose every hunk is of a derived kind are a merge resolved as R3 and R4; any other conflicted path or hunk is `land <repo>: red behind exit 1`, nothing written, a note naming each such path.
- R3, the derived kinds. The `"version"` line of `plugin/.claude-plugin/plugin.json`; a line that begins `Status: version ` in `README.md` or `design/readme/source.md`; any line of `design/readme/rendered.sha256`; a row of the table in `NICE_TO_HAVE.md` or `history/NICE-overflow.md`. The first three take main's side, since the stamp rewrites them. The rule is on the hunk, never the file; resolved from the merge's three stages, no merge driver, no git config.
- R4, NICE rows merge by id, from the three versions of the table. Main's rows stand. A row only the branch added is kept. A row one side removed and the other left alone is removed. A row both changed is `red behind`. A row the branch added under an id main has since used takes a new number, above the highest id on either side, the overflow file included. A repeated id on any side of a NICE hunk is `red behind`. A renumbered id is rewritten only in `.md` files the branch added (the head has them, main does not, and they are in the merged tree), as a whole word; a mention anywhere else, code and tests included, is listed in the note and left (review 1's ruling: "those lines only"). The renumbering writes only regular files (mode 100644 or 100755) of the merged tree, from its text, never a path taken from the head's tree and never through a link, so a file main deleted or renamed stays so.
- R5, the stamp. `make stamp` in the worktree. A non-zero exit is `red stamp exit <code>`. Its diff is held to R3's kinds plus whole NICE rows moved to the overflow; anything else is `red stamp exit 1`, the paths named. On either red the job restores the paths the stamp changed. A stamp that wrote nothing makes no commit.
- R6, the job's commits. `<branch>: merge main`, then `<branch>: plugin <version>`, its paths added by name, last; each closes with the trailer `Gate-Land: <the full sha given>`. Nothing else is committed, and no file is written outside the worktree.
- R7, the version. After the stamp, `scripts/plugin-version-check` where the file is there: a non-zero exit is `red version exit <code>`, before the check.
- R8, the head past the sha given. `require_sha` accepts it only when the sha given is its ancestor, every commit between carries R6's trailer naming it, and the job's merge (with the main commit the head's merge names as its second parent) and stamp, run again from the sha given in a temp worktree removed after, give the head's tree. Else `red sha`, the pin's note.
- R9: every later step takes the readied head for the sha given.
- R10, the line. Unchanged when ready wrote nothing. When it wrote: `land <repo>: ok <sha given>, main readied, as <the new head, whole>, plugin <version>`; a red after it wrote ends `, as <the new head>`. The pin's endings (`, range not scanned`, `, staged paths left on main`, gl1's `, unrun <why>`) come first.
- R11, `--dry-run`. Runs in the caller, queues nothing and writes nothing, inside a gate job too; makes every read up to R2's and prints one of `ready: no stamp target; a branch behind main is red sha`, `ready: <branch> holds main`, `ready: would merge main <sha7> into <branch>, no conflict`, `ready: would merge main <sha7> into <branch>, <n> derived hunks: <paths>`; then, with a `stamp` target, `ready: would run make stamp and commit its lines`; last `land <repo>: dry run, nothing queued`, exit 0. A read that reds prints its red line and exits its code; the stamp is not run.
- R12, the words: `land.py`'s docstring, the parser's help, the skill's `gate land` line; a NICE row for the source's line on a branch behind main.

## 3. Interfaces and acceptance

- `land.main(argv, log=None, dry=False)`; `gate land --dry-run` calls it with `dry=True` before the `--in-job` branch, so it runs in the caller in or out of a job.
- `land.ready` returns the head; R8's rerun calls the same merge and stamp steps.
- The stamp runs as `make stamp STAMP_BASE=<main's commit as read>`, so a rerun gives the same lines whatever main does after.
- `refused` reads from the log's size just before `make check`: a stamp's output is never an `unrun` (a test holds it).

All in `tests/test_land4_ready.py`: made-up repos `crate`, branch `p1-crate`; a stub stamp, and two tests with the repo's own `scripts/stamp`.

| # | line | at the pin (`d364bf4`) |
|---|---|---|
| 1 | no `stamp` target, a branch one commit behind main: the pin's note and `red sha exit 1`, main and the worktree as they were | green, held |
| 2 | a stamp, behind main, no conflict: the merge and stamp commits with subjects and trailers, the check once on the new head, main holding it, `ok <sha>, main readied, as <new>, plugin <version>`, exit 0 | `red sha exit 1` |
| 3 | conflicts in the version line, a Status line, the sidecar and NICE rows together: readied and landed; one more conflicted line in `README.md`, or a path outside the derived files: `red behind exit 1`, no commit, the path named | `red sha exit 1` |
| 4 | NICE by id: kept, removed, both changed red; n8, n9 under main's n8, n9 become n11, n12 and n10 stays; the packet's mention rewritten, a mention in a file main has noted; with n11 in the overflow, n12 and n13 | none |
| 5 | a stamp that exits 3: `red stamp exit 3`; one that edits a line outside R3: `red stamp exit 1`; both leave the worktree clean; a version check exiting 1: `red version exit 1`, no check run | none |
| 6 | a second call after a red check: the head accepted, no new commit, `red check exit <code>, as <new>` both times; a commit without the trailer, or a head whose tree the rerun does not give: `red sha` | `red sha exit 1` |
| 7 | a branch that holds main, a stamp with nothing to write: the pin's `ok <sha>, main readied`, no commit | green, held |
| 8 | `--dry-run` in R11's four states and on a bad merge file: its lines, its exit, no queue entry, no commit, no file changed; with five other arguments `land ?: red usage exit 2` | argparse refuses `--dry-run`, exit 2 |
| 9 | `test_land{,2,_range,_resolve,3_stamp}.py` and `test_gl1_record.py` pass unedited | green |
| 10 | both venvs; `make check` once, last, through the gate queue; the next alpha by `make stamp`, its files alone as the last commit under `plugin/` | green at alpha.115 |

## 4. Findings that name this row

None at the cut. Left to later rows: `gate publish`, `--push` and `--install` (land5); GUIDE §7's words on the stamp (c8); the rows read of the trailer (a ledger row); a dry form of `scripts/stamp` (a NICE row); `make stamp` in the other tool repos.

## 5. Forbidden reads

No live state root (its gate folder and runner included), no transcript, nothing under `~/.claude`, no relay ledger.

## 6. Report

To the hq coordinator: the branch tip, the table at the pin and now, the choices, what is not done.
