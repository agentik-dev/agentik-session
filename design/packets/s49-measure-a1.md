# Packet S49, Amendment 1: the refuter's round 1 on a1fe45f

| item | value |
|---|---|
| from | the refuter's round 1 on a1fe45f, the coordinator's ruling; parent `design/packets/s49-measure.md`, whose rulings stand but where this moves them: it overrides §2's rulings 1 and 2 and ruling 3's first clause |
| pin | a1fe45f (branch `s49-measure`, alpha.34); worktree `.claude/worktrees/s49-measure` |
| wall | as the parent's; `claude` only as `claude plugin validate`; no merge, push or install; a test never writes under the live `~/.local/state` |
| may touch | the parent's row, and `design/mod-r1.md` (one amendment line), `claude_session/cli.py` (`cmd_hook`), this packet |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s49.py tests/test_s34.py tests/test_ledger.py tests/test_precompact.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; `grep -c 'hooks.jsonl' plugin/hooks/run` reads 0; `tail -1 plugin/hooks/run` reads `exec "$tool" hook "$1"`; `git diff main -- plugin/hooks/run` shows one variable and its comment and nothing else; `make hygiene` exits 0. These replace the parent's two `grep` lines |
| verify | `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet; 1 the tests, red; 2 the shim back, the CLI's row; 3 the S4s; 4 the measures, the texts; one commit per act, 90 tool calls |

## 1. What the source says, and the readings

**Why.** Stopping `exec` changed hook behaviour, which ruling 2 forbids. F1: after a shim-only kill at a timeout the surviving PreToolUse writes `calls/<tid>` after PostToolUse closed it, and that open call holds the launcher. F2: a shim-only kill leaves the tool holding stdout, 3.7 s against 0.03 s for a parent waiting for EOF. F3: a tool killed by a signal moves the hook's status and stderr, -15 to 143 and a `Terminated` line. Whether Claude Code kills the tree or the shim alone is unsettled, so this rules it out rather than depending on it.

**Measured** (the first form's method: the shim called from Python, temp state roots, alternating calls, p50; all trees compiled alike; load 4 to 7).

| arm | main | this form | added | the first form added, same run |
|---|---|---|---|---|
| no-op tool, 400 calls | 10.8 ms | 13.7 ms | 2.9 ms | 8.1 ms |
| real CLI, PreToolUse, 100 calls | 56.1 ms | 60.9 ms | 4.8 ms | 9.5 ms |
| real CLI, Stop, 100 calls | 73.9 ms | 76.4 ms | 2.5 ms | |
| real CLI, SessionEnd, 80 calls, three files and a measure.json | 84.1 ms | 88.5 ms | 4.4 ms | |

A real PreToolUse's row reads p50 47 ms against 60.9 ms of wall time: `ms` leaves out the shim's start up to the `date`, and the interpreter's teardown after the append. `harness._walk` on the refuter's three 1 MiB files of `@zz `: 0.23 s against SessionEnd's 15 s; 63 files of 1 MiB of `@\n`: 0.09 s.

**Children.** On the hook path the only spawn is `gitinfo`'s `git`, short-lived and bounded by its timeout; `gate.inbox_take` spawns nothing, and `chain`, `launch` and `doctor` are not on it. The pop in A5 holds whatever a hook comes to spawn, and `tests/test_s49.py` proves it on a real SessionEnd's `git` and on a nested `hook` call.

**Wrong rather than absent.** Three, all reported, none fixable from the CLI: a kill in the teardown after the append reads the code the process would have exited with; a clock stepped forward between the `date` and the append inflates `ms` (one stepped back past the start leaves no row); a shim-only kill on a waiting branch (Stop's four, PreCompact) leaves the tool finishing alone, whose row is true of the tool, with an `ms` that can pass the hook's timeout.

**The README** says nothing this changes: its line on `report --hooks` stands, and only the count moved, 2087 to 2177, at the same width; the source is still 16,377 bytes.

## 2. Rulings

**A1. The shim** is main's flow exactly, `exec "$tool" hook "$1"` last and the two waiting branches as main has them, plus one line before them: `AGENTIK_SESSION_HOOK_T0` exported from one `date +%s%N`, empty if `date` fails. No append, no state path, no second `date`.

**A2. The row is the CLI's**, at the end of `cli.cmd_hook`, the outermost place on the hook path the parser reaches: `harness.record_hook(t0, event, code, env)`. `code` is what the process will exit with: `dispatch`'s return, a `SystemExit`'s code as Python maps it, 1 for an uncaught exception. Nothing it does moves the exit, stdout or stderr, or raises. No row: no variable, not 19 ASCII digits, an event that is not letters, a code outside 0 to 255, a clock that reads earlier than the variable, a `KeyboardInterrupt` (the process dies by the signal).

**A3. The first refused reason is corrected.** The charter's "a CLI-side row could only ever read exit 0" is wrong for this form: the row takes the code from around `dispatch`, so a Stop's real code, which the shim discards, is recorded right. What is genuinely lost, all acceptable and all absent, never wrong: a CLI older than the plugin, an argparse refusal before the handler, an interpreter failure, and a kill.

**A4. Stdout goes first.** Teardown's flush of a closed stdout turns exit 0 into 120. `record_hook` flushes before it writes: a flush that fails writes no row, and teardown fails as it would have. So `ms` includes the flush and excludes only the interpreter's teardown after the append; it also starts after the `date` fork, so the shim's own start is not in it.

**A5. The variable dies with the call.** `cmd_hook` pops it from `os.environ` on entry, before anything can spawn, so no child of a hook inherits it and no nested `hook` call writes a row from it. Only `cmd_hook` reads it.

**A6. The file:** opened `O_APPEND|O_CREAT|O_NOFOLLOW|O_NONBLOCK`, mode 0600, and written only if `fstat` says regular (F4): a dangling link, a link to a file, a FIFO, a directory, an absent state folder write nothing and make nothing. `rotate` takes `lstat`, regular only.

**A7. The S4s.**
- F5: `report --hooks --since X` says the hook table is unfiltered and the ledger filter applied; the bytes line tells "no ledger row since X" from "no row since X carries it". `--json` adds `since`, `events_filtered: false` and `ledger_rows`.
- F6: `harness._walk` runs on a deque, each path queued once, at most `MD_MAX_QUEUE` queued, at most `MD_SCAN_CAP` bytes scanned; past either the figure is a floor, as past `MD_MAX_FILES`. A file that cannot be read is not counted and the rest stand: it no longer nulls the row's figure.
- F7: `read_hooks` reads regular files only, never through a link, never blocks on a FIFO, and skips a line too deep to parse.
- `rate_limits`: `measure.json` carries its own `at`, so the row gains `rate_limits_at`, null when that is not a time (22 keys). `measure.stated_limits(sdir) -> (list | None, str | None)`.
- `design/mod-r1.md` §7.3 gains the line that SessionEnd opens `measure.json` through `harness`: it copies, and decides nothing.
- `.hygiene-allow` and `tests/test_s34.py` go back to main's: the shim no longer names the old folder.

## 3. Interfaces

Added: `harness.HOOK_T0 = "AGENTIK_SESSION_HOOK_T0"`; `harness.take_t0(env) -> str | None`; `harness.record_hook(t0, event, code, env) -> None`, never raises; `harness.exit_status(code) -> int`; `harness.claude_md_line(rows, since=None)`.

## 4. Findings that name this row

The refuter's F1 to F7, above; the two NICE lines this leaves are in `NICE_TO_HAVE.md`, S49's notes.

## 5. Forbidden reads

As the parent's.

## 6. Report (at most eight lines)

The sha; the gate id and exit; `git diff main --stat -- plugin/hooks/run`; the measured overhead; any row that could be wrong rather than absent; anything left over.
