# Packet land5b-install: `--install` installs what was pushed, and holds while a run is live

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief land5b-install (S3), HANDOFF 37's second half |
| pin | `45b975d` on main (2.0.0-alpha.121, land5-publish's merge). Worktree `.claude/worktrees/land5b-install`, branch `land5b-install`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test uses the live gate, state, home or process list, or pushes but to a bare repo in its temp folder; no relay verb, run or read but a stub's list |
| may touch | `plugin/lib/claude_session/deliver.py` (new), `publish.py` (`main`, `after_land`, `USAGE`, the docstring's head), `cli.py` (`_gate_land`, `cmd_gate`, the `gate` parsers), `tests/test_land5b_install.py` (new), `plugin/skills/session/SKILL.md` (one line), this packet, `history/sittings/2026-11-14-5-land5b-install.md`; in the last commit alone, the stamp's files |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3's table; `.venv/bin/python -m pytest -q tests/test_land5b_install.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `45b975d`)

After a push the coordinator installs by hand: a read of the process list for a relay run, `claude plugin marketplace update`, `claude plugin update`, or `make install`. At the pin `gate publish x --install` and `gate land --install a b c d` are argparse's `unrecognized arguments`, exit 2. The push and its proof (`publish.turn` up to the push, `proof`, `scans`) stay land5-publish's; `tests/test_land5_publish.py` stays unedited.

## 2. Rulings (brief land5b-install)

- R1. `gate publish <repo>... [--install] [--dry-run]`; `gate land <repo> <branch> <sha> <merge> [--push] [--install] [--dry-run]`. `--install` runs in the caller's process after each repo's publish turn, never in the gate job; `gate land --install` with no `--push` runs it after an ok land line, on R2's rule. Publish's caller refusal holds first; `--in-job --install` is `land ?: red usage exit 2`. Nothing prompts.
- R2. Only what is pushed: main's head S is R or an ancestor of R, `refs/remotes/<remote>/main`, read as publish reads it, no fetch. Else `install <name>: red unpushed exit 1`, nothing runs. A red publish line prints no install line.
- R3. The hold, nothing of a repo installed while: (a) a line of the process list (`agentik_install.processes`) has a program whose base name is `relay`, `agent-relay` or `agentik-relay` and `run`, `gate` or `plan` among its later words, or `agentik relay <one of them>`; each prefix of its words is tried as the program, the words stopping at the first `NAME=value`; no `ps`, or a list that cannot be read, holds; (b) `unattended.status` names a running row; (c) a gate entry, running or queued, is on the repo's key (`gate.repo_key`). Held: `install <name>: held install: <what is live>`, a note with `agentik session gate publish <repo> --install`, exit 1, the push standing; no poll, no relay verb.
- R4. In order, each a note before it runs: (1) `<repo>/plugin/.claude-plugin/plugin.json` names N and the installed-plugins file (`$CLAUDE_CONFIG_DIR`, else `~/.claude`, `/plugins/installed_plugins.json`) has an id `N@M` with an entry of the user's scope (`user`, `managed` or none): `claude plugin marketplace update M`, `claude plugin update N@M`; N or M not `[a-z0-9][a-z0-9-]*` is `red install exit 1`, nothing run. (2) `make -n install` exits 0 under land.main's cleaned environment: `make install`, a gate job on the repo's key, waited for, its strict code. Neither: `install <name>: ok, nothing to install here`.
- R5. `install <name>: ok N@M <old> to <new>[, make install]`; `ok N@M <new>, already installed` where the entry's version is plugin.json's before anything ran, and nothing runs; `ok, make install` with no plugin step; a failed step `red install exit <its code>`. A note says sessions started earlier keep `<old>`. The exit is the first non-zero code of the call's lines.
- R6. `--dry-run`: the pushed read, the hold and the versions run; `install <name>: would run <command>; <command>...`; no `claude`, nothing queued, nothing written.
- R7. Run again on a pushed main: `already pushed`, then the install; with the versions agreeing, `already installed`, nothing started.
- R8. hq measured twice on a Mac that `claude plugin update` and `marketplace update` leave Claude Code's user settings file's time alone, so the verb reads no edit-gates list.
- R9. `make stamp` last; SKILL.md's `gate publish` line gains `--install`; `describe` lists first-level verbs, nothing added.

## 3. Interfaces and choices

- `deliver.py`: `relay_pid(text)` (R3 a), `hold(repo, root, env)` (the held text or None), `turn(arg, root, env, dry, would)` (a repo's line and code), `ids(env, n)`. `publish.main` and `publish.after_land` (`install=`) call `turn` after an ok publish line; `_gate_land` after an ok land line with no `--push`.
- Choices: a dry `would push` reads as pushed; the hold is read before the versions, so a held repo is held where nothing would run; of several user-scope `N@M` ids, the first by name; no `name`, or no such id, is no plugin step; no `claude` on PATH is `red install exit 127`; the job's wall is `gate.wall`, its label `install <name>`; notes go to stderr as `install-step: ...`; `claude` runs in the user's home; a version after the update other than plugin.json's is a note, the line giving the file's; `gate land --install --dry-run` with no `--push` reads main before the landing.

Acceptance, `tests/test_land5b_install.py`: land5-publish's `Crate`, a made-up home and `CLAUDE_CONFIG_DIR`, stubs for `claude` (it logs its argv and moves N's entry on `plugin update`) and `ps`, the temp state root's queue. At the pin every line is red (exit 2).

| # | line |
|---|---|
| 1 | a proven unpushed main, the plugin one behind: the publish line, `ok murmur@acme 1.0.0 to 1.0.1`, the two updates after the push; exit 0 |
| 2 | again: `already pushed`, `already installed`, the log unchanged |
| 3 | a red proof: no install line; `land --install`, no `--push`: `red unpushed exit 1` |
| 4 | a relay `run` (once under a path with a space): held, exit 1, pushed, the log empty; in an environment value: not held; an unreadable list: held |
| 5 | a live unattended run, a job on the crate or on its worktree: held; on another repo: not |
| 6 | a Makefile `install`: a job on the crate's key, `, make install`; a failing one: `red install exit 2` |
| 7 | `murmur@--help`, an uppercase name: `red install exit 1`, the log empty |
| 8 | `--dry-run --install`: `would run`, the log empty, nothing queued, no ref moved |
| 9 | the five refused callers: publish's refusal, no git, no `claude` |
| 10 | the other `tests/test_land*.py` unedited, green under both venvs; the stamp; the check once; both scans exit 0 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, live process list, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names; the merge line in it.

## 7. The fix of review 1

The coordinator's ruling, 2026-11-14: F1 to F3 block; F4, F6, F7 ride; F5 and four leads to NICE at S4 (n257 to n261, in `NICE_TO_HAVE.md`).

- F1 (R2). Before any install step, pushed or already pushed: main checked out at S, each tracked file S (publish's `diff S`), no untracked file git does not ignore, `.claude/` aside; else `red tree exit 1`, the first path in a note, nothing run; an ignored file is the machine's own.
- F2 (R6). No `make` outside the gate job: the `install` target is read from the Makefile's text at S (`git show`), a rule line whose targets hold `install`; a target only an included file gives is not seen. `--dry-run` starts no process but git (and R3's `ps`).
- F3. `already installed` skips the plugin's two commands only; a Makefile's `install` runs on each call not held, not dry. R5 now: `ok N@M <new>, already installed[, make install]`. R7 now: the versions agreeing, `already installed`, no `claude` started.
- F4. A version prints only as one token of letters, digits, `.+-`, at most 64; else `?`.
- F6. A plugin.json `name` present and not a string of R4's form: `red install exit 1`.
- F7. A newest unattended run whose ledger exists and cannot be read holds.

| # | line | at `5dd358d` |
|---|---|---|
| F1 | an uncommitted Makefile edit (already pushed), an untracked include (fresh push): `red tree exit 1`, nothing run; under `.claude/`, ignored: not red | ok, the recipe run |
| F2 | `+`, `$(MAKE)` and `$(shell)` lines: a dry and a held call leave no marker; no `install` rule: nothing queued | the markers written |
| F3 | a red `make install`, then again: the target run twice, `already installed, make install` | one job, `[2]` |
| F4 | a version with a newline: `?`, one install line | three lines |
| F6 | `name` 5, a list, `""`: `red install exit 1` | `nothing to install here` |
| F7 | a ledger of mode 0, a ledger that is a folder: held | updated |
