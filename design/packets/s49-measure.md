# Packet S49: measure the harness

| item | value |
|---|---|
| from | agentik-hq HANDOFF 17, build 4 of the Fable review (`docs/REVIEW-2026-10-31-suite-review.md` §5 item 4, §3.4's hooks row), on the owner's word of 2026-10-31: "the shim appends `{event, ms, exit}` to `hooks.jsonl`; `SessionEnd` writes `claude_md_bytes` and `rate_limits` to the ledger row" |
| pin | 95acb37 (main, alpha.33); worktree `.claude/worktrees/s49-measure`, branch `s49-measure` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`, `claude` but `claude plugin validate`; a test or probe never writes under the live `~/.local/state`; no relay verb, no relay binary built or run; no `pkill` by name or pattern; agentik-observer is read only |
| may touch | `plugin/hooks/run`, `plugin/commands/report.md`, `claude_session/harness.py` (new), `claude_session/hooks.py` (`dispatch`, `_ledger_line`), `claude_session/ledger.py` (`LEDGER_KEYS`, `entry_for`), `claude_session/measure.py` (`stated_limits`), `claude_session/cli.py` (`cmd_report`, its parser), `tests/test_s49.py` (new), `tests/test_ledger.py` (the key count), `tests/test_s34.py` (its pin on the shim's Stop line), `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `.hygiene-allow` (the shim names the tool's old state folder, as `config.py` does), this packet, the charter, and the version act's pins |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s49.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on 95acb37: the file is absent); `.venv/bin/python -B -m pytest tests/test_ledger.py tests/test_precompact.py -q 2>&1 \| tail -1` reads `passed`; `grep -c 'hooks.jsonl' plugin/hooks/run` reads at least 1 (on 95acb37: 0); `grep -c 'exec "$tool"' plugin/hooks/run` reads 0 (on 95acb37: 1); `make hygiene` exits 0 |
| verify | `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet; 1 the tests, red; 2 the shim, its cap and the row's keys; 3 the reader and the texts; 4 the version, the README count, the sidecar (last, one bump; adcb9d8 is the model). 90 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says, and the readings

The review's problem: "hook latency, CLAUDE.md bytes per turn and record cost per landing are unmeasured" and "a `Write` spawns 8 processes; a `Read` spawns 5; none of them is measured". It says itself its facts can be stale, so the readings at 95acb37:

- `plugin/hooks/run` is `#!/bin/sh`, `/bin/sh` here is bash 3.2 (no `EPOCHREALTIME`); `date +%s%N` works on this Mac and on GNU; it `exec`s the tool on every event but the four Stop-likes and PreCompact, which already wait for it.
- `measure.py` already holds the engine's `rateLimits` in `<session>/measure.json` (S45), its shape checked by `admission.rate_limits`, and has `load`. Nothing new reads the engine: the row copies that.
- `ledger.append` writes exactly `LEDGER_KEYS` and refuses others, so the writer is the one strict place. `ledger.read` and `read_chains` are lenient. `tests/test_ledger.py` pins 19 keys.
- `observer/sources.py`'s `ledger()` reads named keys with `.get` and ignores the rest; its `verdict.py` reads only what that returns. No strict reader there. It lists `<root>/sessions`, never the root, so a new root file is unseen. The relay holds no reader of this ledger but a test's fixture.
- Baseline, 95acb37, the shim called from Python with a temp state root: a no-op tool p50 8.9 ms, the real CLI on PreToolUse p50 96 ms.
- `design/readme/source.md` is 16,382 bytes under a 16,384 ceiling: a new line there needs an equal trim, by rewording, no fact dropped.

## 2. Rulings

1. **The shim appends**, as the source says, after the tool ends: `date +%s%N` before and after, the difference in whole ms, one `printf` to `<state>/hooks.jsonl`, the state root picked as `config.state_dir` picks it, the wrapper's own `[ -e ]` shape, with no fork but the two `date`s and no lock. Any failure writes nothing and says nothing: no `date`, no `%N`, no state directory, a file that is not regular (a FIFO would hang), an unwritable file, an event that is not letters.
2. **The hook's exit and stdout do not move.** `exit` in a row is the tool's own, so a Stop an older CLI refused reads 2 there while the hook still exits 0. The shim stops `exec`ing, since it must outlive the tool: on a timeout's kill the tool finishes alone, as Stop's already does, and that call leaves no row. A tool that is not on PATH leaves no row.
3. **The bound.** `hooks.dispatch` stats the file on every hook call: at 1 MiB or more it renames it to `hooks.jsonl.1`, replacing the last. One generation kept, so at most 2 MiB plus lines racing a rename. Rotation lives in the CLI since a size in `sh` costs a fork. It is silent, and a CLI older than the plugin does not rotate, which is the state the README's install order already forbids.
4. **A row is `{"event","ms","exit"}`** and nothing else: no session, time, path, prompt or tool input. So `--since` does not filter it and it is not per session; the window is what the two generations hold.
5. **`claude_md_bytes`** (`harness.claude_md_bytes(cwd, env)`), at SessionEnd, on-disk bytes of each file once by real path: `CLAUDE.md` under `CLAUDE_CONFIG_DIR` or `~/.claude`; `CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md` in the session's `cwd` and each ancestor; and `@` imports of those, to five hops, relative to the importing file, `~/` and absolute too, none inside a code span or fence. Not counted: managed policy, `.claude/rules/`, a subdirectory's file that loads on demand, auto memory, `--add-dir`, a plugin's context, what a hook adds. Capped at 64 files; a file past 1 MiB counts by size and is not scanned. Null with no usable `cwd` or on any error. It is the file state at the end, raw bytes, not tokens.
6. **`rate_limits`** is the session's last `measure.json` `rateLimits`, through `measure.stated_limits(sdir)`, null when absent or when the shape check refuses it. No second reader of the engine. `hooks.py` reaches it through `harness.stated_limits`, since M2's criterion 3 scans that file for any import of measure: the row is a record, and nothing that decides reads it.
7. **Both keys join `LEDGER_KEYS`,** written null when absent as every key is. Old rows read as before; the plain table and `--json` do not change for them. A failure in either never loses the row.
8. **The reader:** `report --hooks`, no new verb. Per event: count, p50, p95 (nearest rank, in ms), nonzero exits, over both generations; then one `claude_md_bytes` line over the rows `--since` leaves: the newest, p50, max, n. `--json` gives the same as an object. Neither source holding anything exits 2, as `--chains` does.
9. **Honesty:** the README says only this plugin's hooks are measured. Claude Code's own per-hook timing, if a debug log or transcript carries it, is a NICE lead, never built here.
10. **The version:** 2.0.0-alpha.34 in all five pins, one bump, last; the README count from the suite; the sidecar re-hashed by hand, as adcb9d8 did.

## 3. Interfaces (signatures, not prose)

- `harness.HOOKS = "hooks.jsonl"`, `harness.HOOKS_CAP = 1048576`; `harness.rotate(state) -> None`, never raises; `harness.read_hooks(state) -> list[dict]`, lenient; `harness.hook_stats(rows) -> dict`; `harness.hooks_table(stats) -> str`.
- `harness.claude_md_bytes(cwd, env) -> int | None`, never raises; `harness.claude_md_stats(rows) -> dict | None`; `harness.claude_md_line(rows) -> str`.
- `measure.stated_limits(sdir) -> list | None`; `harness.stated_limits(sdir)`, the same.
- `ledger.entry_for(m, *, project, profile, cwd, exit_reason, claude_md_bytes=None, rate_limits=None)`.
- `report --hooks [--json] [--since D]`.

## 4. Findings that name this row

None in this repo. The marketplace line in commons at alpha.34 is hq's, as is the hq record of the numbers.

## 5. Forbidden reads

Transcripts; `~/.local/state`, every part; relay ledgers; the review whole. agentik-observer's `observer/` by grep and `sed`, read only.

## 6. Report (at most ten lines)

The branch and sha; the gate id and exit; the measured overhead per hook call; what `claude_md_bytes` counts; anything that reads the row strictly; anything decided or left over.

## 7. Amendment 1 (2026-10-31, refuter round 1 on a1fe45f, the coordinator's ruling; it overrides §2's rulings 1, 2 and 3's first clause)

| item | value |
|---|---|
| pin | a1fe45f, this branch |
| may touch | as above, and `design/mod-r1.md` (one amendment line), `claude_session/cli.py` (`cmd_hook`) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s49.py tests/test_s34.py tests/test_ledger.py tests/test_precompact.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; `grep -c 'hooks.jsonl' plugin/hooks/run` reads 0; `tail -1 plugin/hooks/run` reads `exec "$tool" hook "$1"`; `git diff main -- plugin/hooks/run` shows one variable and its comment and nothing else; `make hygiene` exits 0. These replace the first form's two `grep` lines |
| verify | `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this section; 1 the tests, red; 2 the shim back, the CLI's row; 3 the S4s; 4 the measures, the texts; one commit per act, 90 tool calls |

**Why.** Stopping `exec` changed hook behaviour, which ruling 2 forbids. F1: after a shim-only kill at a timeout the surviving PreToolUse writes `calls/<tid>` after PostToolUse closed it, and that open call holds the launcher. F2: a shim-only kill leaves the tool holding stdout, 3.7 s against 0.03 s for a parent waiting for EOF. F3: a tool killed by a signal moves the hook's status and stderr, -15 to 143 and a `Terminated` line. Whether Claude Code kills the tree or the shim alone is unsettled, so this rules it out rather than depending on it.

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

**Interfaces, added:** `harness.HOOK_T0 = "AGENTIK_SESSION_HOOK_T0"`; `harness.take_t0(env) -> str | None`; `harness.record_hook(t0, event, code, env) -> None`, never raises; `harness.exit_status(code) -> int`; `harness.claude_md_line(rows, since=None)`.

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
