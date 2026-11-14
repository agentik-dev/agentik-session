# Packet land5-publish: one call proves main's head green, scans it and pushes that sha

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief land5 (S3); review 1's ruling (F1 to F3, leads 1, 2); review 2's (F1, F2, lead 1) |
| pin | `1dbef66` on main (2.0.0-alpha.118, fk3-session's merge). Worktree `.claude/worktrees/land5-publish`, branch `land5-publish`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test uses the live gate or state, or pushes but to a bare repo in its temp folder; no `gate publish` or `git push` in a real checkout; no relay verb |
| may touch | `plugin/lib/claude_session/publish.py` (new), `plugin/lib/claude_session/cli.py` (`_gate_land`, `cmd_gate`, the `gate` parsers), `tests/test_land5_publish.py` (new), `plugin/skills/session/SKILL.md` (one line), `NICE_TO_HAVE.md` (two rows; review 1 four, review 2 three), this packet; for review 1 `gate.py` (`make_env`); for review 2 `land.py` (`main`'s drop list) and the key counts of `tests/test_fw2.py`, `tests/test_gl1_record.py`; `history/sittings/2026-11-14-4-land5-publish.md`; in the last commit alone, the stamp's files |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_land5_publish.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `1dbef66`)

After `main readied`, a person runs two scans and types `git push`; twice a push rode a red check. A verb does those steps, refusing where the proof is missing, in the caller's own process (only a main sitting pushes). It installs nothing.

At the pin: `gate publish x` is `invalid choice: 'publish'`, exit 2; `gate land --push a b c d` is `unrecognized arguments: --push`, exit 2. `land.py` holds no `git push` (`test_e_no_push_in_the_script`), so the push is a new module's.

## 2. Rulings (brief land5)

S is `refs/heads/main`'s sha, read once at the start of a repo's turn; the remote is `branch.main.remote`; R is `refs/remotes/<remote>/main`. Notes go to stderr as `publish-step: ...`; stdout is one line a repo, last.

- R1. `gate publish <repo>...`, each resolved as `land.resolve_repo`, in turn; every repo gets its line; the exit is the first non-zero code, else 0. No repo or an unknown flag: `publish ?: red usage exit 2`.
- R2. Before any read: inside a gate job, `state.main_sitting(env)` false, or `CLAUDE_SESSION_PROFILE=builder` is `publish ?: red caller exit 1`, a note saying which; `--dry-run` too.
- R3. `require_main`'s reads, else `red main exit 1`. No `branch.main.remote`, a `branch.main.merge` other than `refs/heads/main`, a remote opening `-`, or one that is no name `git remote` lists (a path or a URL, review 1 lead 2): `red remote exit 1`, before any push.
- R4. R exists and S is R or its ancestor: `ok <S>, already pushed`, exit 0, nothing more. No fetch, ever.
- R5. S is proven by a gate result under the state root: a landing (exit 0, this checkout, its log's last land line of this repo opens `ok`; the sha after `, as `, else after `ok `, is S's second parent; S's first parent is the result's `head`; that sha's tree is S's), or a check (exit 0, this checkout, `head` S, `dirty` 0 at both ends, command `make check` alone or `sh -c`/`/bin/sh -c` of `make check` with redirections alone).
  Review 1: F1, a landing's `command` is `_gate_land`'s, whole (`gate.self_argv()`, `gate land --in-job <repo> <branch> <sha> <merge>`, nothing after, `<repo>` this checkout), and `ok ` names that `<sha>`. F2, a check's `make_env` is there and empty; an older result proves no check. F3, the proved sha must resolve to exactly S's second parent. Review 2: F1, a landing proves only where `make_env` is a list holding no `MAKEFILES` (absent or no list: none, so an older landing proves none); F2, the word resolves as an object name alone, `rev-parse --disambiguate=<word>` giving one object, S's second parent, so a ref of that name changes nothing. Else `red proof exit 1`, a note naming `agentik session gate run <repo> -- make check`. Nothing queued. A result not JSON or ill-typed is no proof, no error.
- R6. No `scripts/hygiene`: no scan. One there but no executable file: `red hygiene exit 126` before any push, a note saying so (review 2 lead 1). Else it, then `--require-private --commits <R>..<S>` when its `--help` names `--commits`; output to stderr; non-zero is `red hygiene exit <code>`. No R: the range is not scanned, the ok line ends `, range not scanned`. A tracked file that differs from S is `red main exit 1`.
- R7. `git push --no-follow-tags <remote> <S>:refs/heads/main` (review 1 lead 1: no tag rides it), no other argument; non-zero is `red push exit <code>`; 0 is `ok <S>, pushed to <remote>`.
- R8. `--dry-run`: R2 to R6 as written; in place of R7, `would push <S> to <remote>`, exit 0.
- R9. `gate land --push`: refused as R2 before it queues, `land ?: red caller exit 1`; `--in-job --push` is `red usage exit 2`; the job is the pin's. After an ok land line, R3 to R7, the publish line after it; the exit is the land's when red, else publish's. With `--dry-run`: land's dry lines, then R8's.
- R10. The module's docstring is the contract; the `gate` help names `publish` and `--push`; SKILL.md one line; two NICE rows.

## 3. Interfaces

- `publish.py`: `refusal(env)` (R2's note, or None), `turn(repo_arg, root, dry)` (one repo: its line and code), `main(argv, root, env)` (R1), `after_land(repo, root, dry)` (R9's half). `cli._gate_land` calls the last; the `publish` parser's own errors print R1's usage line.
- `gate.py`'s result gains `make_env` (review 1 F2), its last key: the names among `MAKEFLAGS`, `MFLAGS`, `GNUMAKEFLAGS` and `MAKEFILES` set in the job's environment, sorted, `[]` when none, null where the entry's env is no mapping. The gate scrubs nothing: a job's environment stays the caller's. `land.main` drops `MAKEFILES` with `MAKEFLAGS`, `MFLAGS`, `GNUMAKEFLAGS` and `MAKELEVEL` (review 2 F1), so `make_env`'s other three names cost a landing no proof; a check still needs `[]`.
- Choices: the `ok ` sha may be the prefix the landing was given; the range is `<R's sha>..<S>`, read with S; a hygiene without `--commits` ends the ok line (and the dry one) `, range not scanned`, as land's does; the tree is read against S before the scans and after; a landing's S has two parents.

Acceptance, `tests/test_land5_publish.py` (made-up `crate`, `crate.git` its `origin`, a temp state root, the session's env names scrubbed). At the pin every line is red.

1. A landed merge with its result: `publish crate: ok <S>, pushed to origin`; `crate.git`'s main is S.
2. Again: `ok <S>, already pushed`, no push.
3. No result; exit 2; a land line naming another sha; `, as <sha>` not S's second parent; another repo's; not JSON: `red proof exit 1`.
4. A check result (`head` S, `dirty` 0 and 0, `make check`) proves; `dirty` 1, a `head` one back, `make check; true`, `make test`: `red proof`.
5. A forged ok line before the real red one: `red proof`.
6. A helper, a depth, `RELAY_ROW`, the builder profile, a gate job: `publish ?: red caller exit 1`, `--dry-run` too.
7. Hygiene red on the tree, then on the range: `red hygiene exit 3`, nothing pushed; no `scripts/hygiene`: pushed; a tracked file edited after the check: `red main exit 1`.
8. `crate.git`'s main moved: `red push`, never forced; main moved after S was read: `crate.git` holds S.
9. `--dry-run`: `would push <S> to origin`, every ref unchanged.
10. Two repos, the first unproven: both lines, the second pushed, exit 1.
11. `gate land --push`: the land line, then the publish line; a red landing pushes nothing; refused as line 6 before it queues.
12. `tests/test_land*.py` unedited and green; both venvs; `make check` once, last; the alpha by `make stamp`, the last commit.
13. F1: the review's forged job, then a hand merge; a landing command with another head, a word after, another repo or sha: `red proof`.
14. F2: `make check` queued with `MAKEFLAGS=n`: `make_env` `["MAKEFLAGS"]`, `red proof`; none: `[]`; no key: `red proof`.
15. F3: an ambiguous prefix: `red proof`.
16. Lead 1: `push.followTags=true`, a tag: none in `crate.git`.
17. Lead 2: a path or a URL as the remote: `red remote exit 1`, no push.
18. Review 2 F1: `gate land --push`, `MAKEFILES` naming `override SHELL := /usr/bin/true`, the check `exit 1`: `land crate: red check exit 2`; a landing's `make_env` holding `MAKEFILES`, absent, null, `""`: `red proof`; the other three: pushed.
19. F2: a branch or tag named as the 4-hex word, on the colliding commit: `red proof`; one named as a good word, elsewhere: pushed.
20. Lead 1: `scripts/hygiene` without the exec bit: `red hygiene exit 126`, nothing pushed.

## 4. Findings that name this row

None at the pin. Review 1: F1 (S1), F2 (S1), F3 (S3), leads 1 and 2; review 2: F1 (S1), F2 (S3), lead 1; their other leads are NICE rows.

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude` or relay ledger.

## 6. Report

Each acceptance line, its exit and last line; the branch and its head.
