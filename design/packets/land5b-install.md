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

After a push the coordinator installs by hand: it reads the process list for a relay run, types `claude plugin marketplace update agentik` and `claude plugin update <name>@agentik`, or `make install`, and reads the versions. `gate publish` and `gate land --push` end at the push. At the pin (hq's measurement): `gate publish x --install` and `gate land --install a b c d` are argparse's `unrecognized arguments`, exit 2. The push and its proof (`publish.turn` up to the push, `proof`, `scans`) are land5-publish's and stay as they are; `tests/test_land5_publish.py` stays unedited and green.

## 2. Rulings (brief land5b-install)

- R1. `gate publish <repo>... [--install] [--dry-run]`; `gate land <repo> <branch> <sha> <merge> [--push] [--install] [--dry-run]`. `--install` runs in the caller's process after each repo's publish turn, never in the gate job; `gate land --install` with no `--push` runs it after an ok land line, on R2's rule. Publish's caller refusal holds for `--install` before any read; `--in-job --install` is `land ?: red usage exit 2`. Nothing prompts.
- R2. Only what is pushed: main's head S is R or an ancestor of R, `refs/remotes/<remote>/main`, read as publish reads it, no fetch. Else `install <name>: red unpushed exit 1`, nothing runs. A red publish line installs nothing for that repo and prints no install line.
- R3. The hold, nothing of a repo installed while: (a) a line of the process list (`agentik_install.processes`, the `ps` on PATH) has a program whose base name is `relay`, `agent-relay` or `agentik-relay` and `run`, `gate` or `plan` among its later words, or `agentik relay <one of them>`; each prefix of the line's words, joined by a space, is tried as the program, and the words stop at the first `NAME=value` word, so a path with a space holds and an environment value does not; no `ps`, or a list that cannot be read, holds; (b) `unattended.status` names a running row; (c) the gate's queue holds an entry, running or queued, whose key is the repo's (`gate.repo_key`: the checkout or a worktree of it). Held: `install <name>: held install: <what is live>`, a note with `agentik session gate publish <repo> --install`, exit 1, the push standing; no poll, no relay verb.
- R4. In order, each a note before it runs: (1) `<repo>/plugin/.claude-plugin/plugin.json` names N and the installed-plugins file (`$CLAUDE_CONFIG_DIR`, else `~/.claude`, `/plugins/installed_plugins.json`) has an id `N@M` with an entry of the user's scope (`user`, `managed` or none): `claude plugin marketplace update M`, `claude plugin update N@M`; N or M not `[a-z0-9][a-z0-9-]*` is `red install exit 1`, nothing run. (2) `make -n install` exits 0 under land.main's cleaned environment: `make install`, a gate job on the repo's key through the gate's queue, waited for, its strict code. Neither: `install <name>: ok, nothing to install here`.
- R5. `install <name>: ok N@M <old> to <new>[, make install]`; `ok N@M <new>, already installed` where the entry's version is plugin.json's before anything ran, and nothing runs; `ok, make install` with no plugin step; a failed step `red install exit <its code>`. A note says sessions started earlier keep `<old>`. The exit is the first non-zero code of the call's lines.
- R6. `--dry-run`: the pushed read, the hold and the versions run; `install <name>: would run <command>; <command>...`; no `claude`, nothing queued, nothing written.
- R7. Run again on a pushed main: `already pushed`, then the install; with the versions agreeing, `already installed`, nothing started.
- R8. hq measured twice on a Mac that `claude plugin update` and `marketplace update` leave Claude Code's user settings file's time alone, so the verb reads no edit-gates list.
- R9. `make stamp` last; SKILL.md's `gate publish` line gains `--install`; `describe` lists first-level verbs, nothing added.

## 3. Interfaces and choices

- `deliver.py`: `relay_pid(text)` (R3 a), `hold(repo, root, env)` (the held text or None), `turn(arg, root, env, dry, would)` (one repo: its line, its code), `ids(env, n)`. `publish.main(..., install=False)` and `publish.after_land(..., install=False)` call `turn` after an ok publish line; `_gate_land` calls it after an ok land line where `--push` is not given.
- Choices: on `--dry-run` a `would push` line reads as pushed, since the dry run shows the real one's commands; the hold is read before the versions (R6's order), so a held repo is held even where nothing would run; of several `N@M` ids of the user's scope, the first by name; a plugin.json with no `name`, or no id of the user's scope, is no plugin step; `already installed` starts no `make install` either (R7's "starts nothing"); no `claude` on PATH is `red install exit 127`; the job's wall is `gate.wall`, its label `install <name>`. Notes go to stderr as `install-step: ...`; `claude` runs in the user's home, so no project's scope is read; where the installed version after the update is not plugin.json's, a note says so and the line still gives what the file reads. `gate land --install --dry-run` with no `--push` reads main as it stands before the landing.

Acceptance, `tests/test_land5b_install.py`: land5-publish's `Crate` (imported), a made-up home with `CLAUDE_CONFIG_DIR` under it, a `claude` stub that logs its argv and moves N's entry to plugin.json's version on `plugin update`, a `ps` stub, the gate's queue under the temp state root. At the pin every line is red (`unrecognized arguments`, exit 2).

| # | line |
|---|---|
| 1 | a proven unpushed main, the plugin one behind: the publish line, `install crate: ok murmur@acme 1.0.0 to 1.0.1`; the stub's log the two updates, after the push; exit 0 |
| 2 | again: `already pushed`, `already installed`, the log unchanged |
| 3 | a red proof: no install line, the log empty; `gate land --install` with no `--push`: `red unpushed exit 1` |
| 4 | a relay `run` in the list (once under a path with a space): `held install:`, exit 1, pushed, the log empty; the words in an environment value: not held; an unreadable list: held |
| 5 | a live unattended run: held; a queued job on the crate, and on a worktree of it: held; on another repo: not held |
| 6 | a Makefile `install`: a job on the crate's key, exit 0, the line ends `, make install`; a failing one: `red install exit 2` |
| 7 | an id `murmur@--help`, a name with an uppercase letter: `red install exit 1`, the log empty |
| 8 | `--dry-run --install`: `would run`, the log empty, nothing queued, no ref moved |
| 9 | each of the five refused callers with `--install`: publish's refusal, no git, no `claude` |
| 10 | `tests/test_land*.py` else unedited and green under both venvs; `make stamp`, `make check` once, green; both scans exit 0 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, live process list, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names; the merge line in it.
