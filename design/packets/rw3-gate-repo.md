# Packet rw3-gate-repo: the checks of one worktree, found with no job id

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief rw3-gate-repo (S4) |
| pin | `5aaf29f` on main (2.0.0-alpha.122, land5b-install's merge; gl1-gate-record's `dirty` in a result). Worktree `.claude/worktrees/rw3-gate-repo`, branch `rw3-gate-repo`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live gate, state or home, or starts a runner in the live state; no relay verb |
| may touch | `plugin/lib/claude_session/gate.py` (`status`, `status_lines`, a path reader and a branch reader beside `_head`, the constants), `cli.py` (`cmd_gate`'s `status` branch and docstring, the `status` parser under `gate`), `plugin/skills/session/SKILL.md` (one line), `tests/test_rw3_gate_repo.py` (new), `tests/test_gl1_record.py` (one line: a `done` item's keys gain `head` and `land`, R6), `NICE_TO_HAVE.md` (five rows), this packet, `history/sittings/2026-11-14-6-rw3-gate-repo.md`; in the last commit alone, the stamp's files |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3's table; `.venv/bin/python -m pytest -q tests/test_rw3_gate_repo.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `5aaf29f`)

`gate status` shows the last five results of the whole machine (`gate.DONE_SHOWN`). A builder cut before its record leaves no job id, so its finished check cannot be found once five other jobs end. At the pin `gate status --repo /nowhere` is argparse's `unrecognized arguments: --repo /nowhere`, exit 2 (measured under a temp home and state root). A `done` item holds `id`, `repo`, `exit`, `seconds`, `cut`, `load`, `beside`, `dirty`. This row adds one flag that lists a folder's jobs and results; it changes nothing that runs.

## 2. Rulings

- R1, the form. `agentik session gate status --repo PATH [--json]`. A read: exit 0 whatever it finds. An empty PATH is argparse's usage error, exit 2.
- R2, whose a job is. PATH is compared as a path: its real path where it exists, else its absolute, normal form. A queued entry, a running job or a result is PATH's when its `repo`, resolved the same way, is equal. The gate's key is not used: a worktree and its main checkout share one. PATH need not exist.
- R3, a landing's result. A result whose `command` holds `gate`, `land`, `--in-job` in a row, then the repo, the branch, the sha and the merge file, is also PATH's when PATH is a work tree whose checked-out branch is that branch and whose `repo_key` is the result's `key`. The branch: one `git -C PATH symbolic-ref --short -q HEAD`, run as `_head` runs git; no answer, no landing matched.
- R4, what is listed. PATH's running and queued lines, as `status_lines` writes them; then every result of PATH the gate still keeps (`KEEP`), newest first by its counter.
- R5, a result's line, with `--repo` only: `done <id> <repo> exit <code> <m.m> min`, then ` head <7>` when the result holds one, ` dirty <n>` when `dirty.start` is a number above 0, ` land <branch>` for a landing. After 20 such lines: `<n> more: agentik session gate status --repo <PATH> --json`. Nothing for PATH: `none for <PATH>`. The `runner:` line stays last.
- R6, `--json`. The envelope and its schema stand. Each `done` item gains `head` (the full sha or null) and `land` (the branch or null), with or without `--repo`. With `--repo` the envelope gains `repo`, PATH as resolved; `running`, `queued` and `done` hold PATH's alone, `done` all of them.
- R7, without the flag the text is byte-equal to the pin's.
- R8, a result file missing, cut short or not an object is passed over; the read never raises on one.
- R9, the words: the parser's help, `cmd_gate`'s docstring, SKILL.md's `gate status` line. No README line.
- R10, five rows for NICE at S4, what land5b-install's review 2 left; no code here.

## 3. Interfaces, choices and acceptance

- `gate.status(root, now, alive, fx, repo=None)`: with `repo`, the dict opens with `repo` and its lists hold the folder's alone. `gate.repo_path(path)` (R2), `gate.land_branch(command)` (R3), `gate._branch(repo)` beside `_head`; `REPO_SHOWN`, `MORE_REPO`, `LAND_JOB`. `cli`'s `gate status --repo` takes a non-empty word (`_nonempty_path`).

Choices inside the rulings:
- R2: both sides go through `os.path.realpath` of the absolute path; for a path that does not exist that is its absolute, normal form with any existing symlinked parent resolved, so a removed worktree under a symlinked temp folder still matches the real path the gate recorded.
- R3: the landing's branch is the second of the four words after the first `gate land --in-job` triple; fewer than four, no landing. The branch is read once per call, and only when a result is a landing.
- R4: "still keeps" is `_prune`'s rule: a result whose `ended` is more than `KEEP` before now is passed over, though not yet pruned.
- R5: the `<m.m>` is `est_text`'s one decimal; a result whose `seconds` is not a number reads `?`. A path's text in `none for` and the `more` line is PATH as resolved.


Acceptance: all in `tests/test_rw3_gate_repo.py`, on the per-test temp state root holding result files the test writes (a made-up repo `crate`, its worktree `crate/.claude/worktrees/p1-crate`, a second repo `basket`).

| # | line | at `5aaf29f` |
|---|---|---|
| 1 | eight results for the worktree among thirty for other folders: `--repo <worktree>` prints the eight, newest first, each with ` head <7>`, then `runner:`; exit 0 | `unrecognized arguments: --repo`, exit 2 |
| 2 | the path through a symlink, with a trailing slash, after the folder is removed: the same eight | the same |
| 3 | the main checkout lists its own and none of the worktree's, one key for both | the same |
| 4 | a red landing of `p1-crate` under the main checkout: listed under the worktree with ` land p1-crate`; another branch's is not; no branch from `git`, no landing, exit 0 | the same |
| 5 | `dirty.start` 3: ` dirty 3`; 0, null, no key: no `dirty` word | the same |
| 6 | twenty-five results: twenty lines, then `5 more: ...`; `--json` holds twenty-five | the same |
| 7 | no job: `none for <PATH>`, `runner:`, exit 0; an empty PATH exit 2 | the same |
| 8 | a running and a queued job of the path show as today's lines, first; another folder's do not | the same |
| 9 | `--json`: `repo` in the envelope; `done` items hold `head` and `land`; without `--repo` the list stays five | no `head`, no `land` |
| 10 | without `--repo` the text for a fixed state is byte-equal to the pin's; a cut-short result is passed over in both forms | green |
| 11 | the suite under both venvs; `make check` once, last, by the gate queue; the stamp's files the last commit under `plugin/` | green at alpha.122 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names.
