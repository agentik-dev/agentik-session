# Packet fw4d: commit, add by explicit path, check, commit on green

| item | value |
|---|---|
| from | agentik-hq design/08 §5 row 5 ("`agentik session commit <paths> --check <cmd> --message-file <f>`: add by path, check, commit on green, exit the check's code") and "The four tool asks" (does not exist, S3); §6 item 7 (FW4, a packet each) |
| pin | agentik-session main **after n33, R2 and R3 land** (and fw4c, if it lands first: no code is shared); cut on 36c84ea, so lines are cited by quoted words. Version: the next free alpha, read up by one for each bump landed before it. Worktree `.claude/worktrees/fw4d-commit`, branch `fw4d-commit`, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live state or writes under the live home; no relay verb |
| may touch | `plugin/lib/claude_session/commit.py` (new), `cli.py`; `tests/test_fw4d.py` (new); `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/*` (status line); `design/packets/fw4d-commit.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash; its exit is the job's |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_fw4d.py`: 21 green (pin: `21 failed`), and under `.venv-floor`; `test_cli.py`, `test_argv_forms.py` (with T: 205 green under both), `test_gate.py`, `test_fw2.py`, `test_commands.py` unedited and green; verify green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 60 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

- No verb: `agentik session commit` is `invalid choice: 'commit'` at 36c84ea (every T's red). The one commit the plugin makes, `checkpoint --commit`, runs `"add", "-u"` (cli.py:998) and then a plain commit, so it takes every tracked change and whatever anyone staged.
- hq's rule is prose only: "Commit by explicit path (`git add <paths>`), never `-A` or `-u`" (agentik-hq `CLAUDE.md`:8).
- 2026-11-10: hq's d4a4155 took `history/sessions/REFUTE-2026-11-10-d34-r2-probes/fx` as 141 gitlinks (`git ls-tree -r d4a4155 | grep -c '^160000'`: 141); cc8555a took them out.
- Probe p1 (`p1_git_today.sh`), git 2.54 today:
  a. `ls-files -o` names each nested repo with a trailing slash (`probes/fx/one/ probes/fx/two/`); `git add probes` exits 0 with `gitlinks staged: 2`, a warning only.
  b. after `git add a.txt`, a plain commit takes `a.txt b.txt`, b.txt staged by someone else.
  c. `commit --only -- a.txt` takes `a.txt` and leaves `b.txt` staged.
  d. mid-merge, `commit --only` exits 128 (`cannot do a partial commit during a merge`).
  e. mid-rebase, a commit exits 0 on a detached HEAD, on no branch.
  f. `add ../out.txt` exits 128, outside the repository.

## 2. Rulings

- R1, the verb. `commit <paths...> --check <cmd> --message-file <f> [--session SID]`. The repo is the one holding the cwd; paths are as git takes them from the cwd, literal (`GIT_LITERAL_PATHSPECS=1` on every git call, so `a*` is no glob). `-A`/`--all` and `-u`/`--update` exist only to refuse, naming the flag.
- R2, refusals. Exit 2, `error: commit: <why>` on stderr, nothing on stdout, the index untouched:
  no path; the whole tree (the top by any name: `.` there, `..` below it, its absolute path); a path outside the repo; a path that is, or holds, an untracked nested repo not ignored (`ls-files -o --exclude-standard` entries ending `/`), each named, first twenty;
  a path `git add --dry-run` refuses (its message); a message file missing, unreadable or blank; an empty `--check`; `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge` or `rebase-apply` (named); a detached HEAD; after the add, nothing to commit in the named paths (restored first).
- R3, the flow. Read the named paths' index entries (`ls-files -s --full-name`); `git add -- <paths>`; the check in the repo's top; on green, a named path that changed in the worktree during the check is red `moved`; else `git commit -q --only -F <f> -- <paths>` (p1 c).
  Stdout is one line, last: `commit <repo>: ok <full sha>` exit 0; `commit <repo>: red check exit <code>`, the check's code (127 not found, 126 not runnable, 128+n a signal); `red moved exit 1`; `red add` or `red commit` with git's code. The check's output goes to stderr.
- R4, the index as found (as folded: round 1's snapshot, then the coordinator's read of it). On every red before this call's commit, the index goes back as found only when no other writer touched it or HEAD during the check: HEAD read before the add, the entries (`ls-files -s -z`) right after it, both asked again under `index.lock`, a stat-only refresh no touch; then the index file copied before the add goes back whole, so a path someone staged before the check stays. Otherwise their state stands: nothing is written, and this call says so, `red <step> exit <code>, the index moved under the check: nothing is restored`, its own paths still staged named on stderr. (At the cut: the named paths' entries put back by `update-index`, so a path staged before or during the check stayed.)
- R5, the gate rule. The check is one string split by `shlex.split`, run with no shell. Its first word `make` or `gmake` makes it one gate job in the repo's top (`enqueue`, `spawn_serve`, `wait`, its code `strict_code`), label `commit check`, the wait line on stderr; any other check runs directly.
  Why: the gate holds every `make` on the Mac, and a full check behind another repo's lock and the load ceiling is what it is for; a targeted check (one test file, `scripts/doclint`) takes seconds and would wait in the queue for nothing. A `sh -c` wrapper runs directly.
- R6, docs. SKILL.md, one line under `gate status`; RUNBOOK, a §6 "Commit by path" (the line forms, the refusals, the gate rule, `--only`, the gitlink); README, the status line only. Last: the version, the status line, the sidecar.

Choices logged (reversible): the refusals past the ask (detached HEAD, nothing to commit) and the `moved` red; the stdout line in `land`'s shape.

## 3. Interfaces

Tests: `tests/test_fw4d.py` (probes).

Red at 36c84ea (`21 failed`), green on `prototype.patch` (`21 passed`), under 3.12.7 and 3.9.6.

| T | the test shows | item |
|---|---|---|
| 1 | two paths, one new: the line, the commit's files and message, a clean status | R1, R3 |
| 2 | b.txt staged by someone: same blob, still staged, not in the commit | R3, R4 |
| 3 | a red check exits 3, a missing one 127; the whole index as found, a partial stage kept | R3, R4 |
| 4 | `probes`, `probes/fx`, `probes/fx/one`: refused naming `probes/fx/one/`, no 160000; ignored, it commits | R2 |
| 5 | `../out.txt`, an absolute path outside, `a.txt/../../out.txt` | R2 |
| 6 | `-A`, `--all`, `-u`, `--update a.txt`, `.`, no path (six) | R1, R2 |
| 6b | the top as its absolute path, `..` from below, `sub/..` | R2 |
| 7 | a message file missing, empty, whitespace (three) | R2 |
| 8 | mid-merge, mid-rebase, detached HEAD | R2 |
| 9 | nothing to commit; `a*` with a1 and a2 changed is no glob | R1, R2 |
| 10 | a check that edits a.txt: `red moved exit 1`, index and HEAD kept | R3 |
| 11 | a pre-commit hook exiting 5: `red commit exit 1`, index kept | R3, R4 |
| 12 | `make check` is one gate job (its command, repo, exit), red `make` exits 2; `sh -c 'make ...'` runs here | R5 |
| 13 | SKILL.md and RUNBOOK name the verb, `--only` and the gitlink | R6 |

## 4. Findings that name this row

agentik-session keeps no ledger of its own: no entry to carry. Bearing, uncrossed: agentik-hq 6, "at a runtime floor of Python 3.9 on the standard library alone"; agentik-hq 5, "helpers never push" (the verb pushes nothing); agentik-hq 17, a verb takes a packet.
NICE, new:
- S3, `cli.py`: `checkpoint --commit` (`"add", "-u"`, :998) sweeps others' staged paths; it could take `commit`'s by-path core.
- S4, `commit.py`: a make check called inside a gate job waits on its own key until the wall (fw4c's p1); with fw4c's mark it could run directly there.
- S4, `commit.py`: a tracked gitlink under a named path is left to git; an intent-to-add entry restored on a red comes back as a plain empty-blob entry; `sh -c 'make ...'` passes the gate rule by.
Fork Q1, marked: the gate rule of R5. Recommended: the first word, `make` or `gmake`.

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T13 under both pythons; choices in a ruling; leftovers.
