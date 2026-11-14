# Packet land5-publish: one call proves main's head green, scans it and pushes that sha

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief land5 (S3) |
| pin | `1dbef66` on main (2.0.0-alpha.118, the merge of fk3-session, after land4-ready). Worktree `.claude/worktrees/land5-publish`, branch `land5-publish`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue, once, last); no `claude`; no test queues in the live gate, reads its results or the live state, or pushes but to a bare repo in its own temp folder; no `gate publish` or `git push` in a real checkout; no relay verb |
| may touch | `plugin/lib/claude_session/publish.py` (new), `plugin/lib/claude_session/cli.py` (`_gate_land`, `cmd_gate`, the `gate` parsers), `tests/test_land5_publish.py` (new), `plugin/skills/session/SKILL.md` (one line), `NICE_TO_HAVE.md` (two rows), this packet, `history/sittings/2026-11-14-4-land5-publish.md`; in the last commit alone, the stamp's files |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_land5_publish.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `1dbef66`)

After a landing prints `main readied`, a person runs two scans by hand and types `git push`. Twice a push has ridden a red check. The session tool gains a verb that does those steps and refuses where the proof is missing. It runs in the caller's own process, never in a gate job, since only a main sitting may push. It installs nothing.

At the pin, by the parsers: `gate publish x` is argparse's `invalid choice: 'publish'`, exit 2; `gate land --push a b c d` is `unrecognized arguments: --push`, exit 2, nothing queued. `land.py` holds no `git push` (`test_land.py`'s `test_e_no_push_in_the_script`), so the push lives in a new module.

## 2. Rulings (brief land5)

S is `refs/heads/main`'s sha, read once at the start of a repo's turn; the remote is `branch.main.remote`; R is `refs/remotes/<remote>/main`. Notes go to stderr as `publish-step: ...`; stdout is one line a repo, last.

- R1. `gate publish <repo>...`, each resolved as `land.resolve_repo`, in turn; every repo gets its line; the exit is the first non-zero code, else 0. No repo or an unknown flag: `publish ?: red usage exit 2`.
- R2. Before any read: inside a gate job, `state.main_sitting(env)` false, or `CLAUDE_SESSION_PROFILE=builder` is `publish ?: red caller exit 1`, a note saying which; `--dry-run` too.
- R3. `require_main`'s reads, else `red main exit 1`. No `branch.main.remote`, a `branch.main.merge` other than `refs/heads/main`, or a remote opening `-`: `red remote exit 1`.
- R4. R exists and S is R or its ancestor: `ok <S>, already pushed`, exit 0, nothing more. No fetch, ever.
- R5. S is proven by a gate result under the state root: a landing (exit 0, this checkout, its log's last land line of this repo opens `ok`; the sha after `, as `, else after `ok `, is S's second parent; S's first parent is the result's `head`; that sha's tree is S's), or a check (exit 0, this checkout, `head` S, `dirty` 0 at both ends, command `make check` alone or `sh -c`/`/bin/sh -c` of `make check` with redirections alone). Else `red proof exit 1`, a note naming `agentik session gate run <repo> -- make check`. Nothing queued. A result not JSON or of the wrong types is no proof and no error.
- R6. Where `scripts/hygiene` is an executable file: it, then `--require-private --commits <R>..<S>` when its `--help` names `--commits`; output to stderr; non-zero is `red hygiene exit <code>`. No R: the range is not scanned, the ok line ends `, range not scanned`. A tracked file that differs from S is `red main exit 1`.
- R7. `git push <remote> <S>:refs/heads/main`, no other argument; non-zero is `red push exit <code>`; 0 is `ok <S>, pushed to <remote>`.
- R8. `--dry-run`: R2 to R6 as written; in place of R7, `would push <S> to <remote>`, exit 0.
- R9. `gate land --push`: refused as R2 before it queues, `land ?: red caller exit 1`; `--in-job --push` is `red usage exit 2`; the job is the pin's. After an ok land line, R3 to R7 for that repo, the publish line after the land line; the exit is the land's when red, else publish's. With `--dry-run`: land's dry lines, then R8's.
- R10. The new module's docstring is the contract; the `gate` help names `publish` and `--push`; SKILL.md one line; NICE rows for `design/readme/source.md`'s line and for the check queued in a clean detached worktree.

## 3. Interfaces

- `publish.py`: `refusal(env)` (R2's note, or None), `turn(repo_arg, root, dry)` (one repo: its line and code), `main(argv, root, env)` (R1), `after_land(repo, root, dry)` (R9's half). `cli._gate_land` calls the last; the `publish` parser's own errors print R1's usage line.
- Choices inside the rulings: a landing proof's command also holds `land --in-job` (as `_gate_land` queues it), so a check's log cannot forge one; the `ok ` sha may be the prefix the landing was given; the range scanned is `<R's sha>..<S>`, read once with S; a hygiene without `--commits` ends the ok line `, range not scanned` too, as land's does; the dry line takes that ending as well; the tree is read against S before the scans and again after them; S needs exactly two parents for a landing's proof.

Acceptance, `tests/test_land5_publish.py` (made-up `crate` with `crate.git` as `origin` in the test's temp folder, a temp state root holding the result files the test writes, the session's env names scrubbed). At the pin every line is red: no such verb, and `--push` unrecognized.

1. A landed merge with its result: `publish crate: ok <S>, pushed to origin`, exit 0; `crate.git`'s main is S.
2. Again: `ok <S>, already pushed`; a recorder first on PATH sees no `git push`.
3. No result; exit 2; a land line naming another sha; `, as <sha>` not S's second parent; another repo's result; a result not JSON: each `red proof exit 1`, `crate.git` unchanged.
4. A check result (`head` S, `dirty` 0 and 0, `make check`) proves; `dirty` 1 at either end, a `head` one back, `make check; true`, `make test`: `red proof`.
5. A forged `land crate: ok <S>` before the job's real red line: `red proof`.
6. `CLAUDE_SESSION_HELPER=1`, `CLAUDE_SESSION_DEPTH=1`, `RELAY_ROW`, the builder profile, a gate job: `publish ?: red caller exit 1`, no git started, `--dry-run` too.
7. Hygiene red on the tree, then on the range: `red hygiene exit 3`, nothing pushed; no `scripts/hygiene`: pushed; a tracked file edited after the check: `red main exit 1`.
8. `crate.git`'s main moved: `red push exit <git's code>`, never forced; main moved locally after S was read: `crate.git` holds S.
9. `--dry-run`: `would push <S> to origin`, exit 0, every ref unchanged.
10. Two repos, the first with no proof: both lines, the second pushed, exit 1.
11. `gate land --push`: the land line, then the publish line; a red landing pushes nothing; refused as line 6 before it queues.
12. `tests/test_land*.py` unedited and green; both venvs; `make check` once, last, by the gate queue; the alpha by `make stamp`, its files the last commit under `plugin/`.

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, no live state root, no live gate result, no file under `~/.claude`, no relay ledger.

## 6. Report

The record the brief names: each acceptance line, its exit and last line; the branch and its head.
