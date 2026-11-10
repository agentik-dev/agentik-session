# Packet FW2: the gate's `--strict`, `head` and `est`

| item | value |
|---|---|
| from | hq `design/08-fill-wait-reconciler.md` §3 item 3 and acceptance (8) to (10), §4's `eff.red_gates`, §5 row 5, as folded 2026-11-09 |
| pin | agentik-session main **after S54 lands** (plugin 2.0.0-alpha.52); worktree `.claude/worktrees/fw2-gate-strict`, branch `fw2-gate-strict`, `.venv` and `.venv-floor` linked from the main checkout. Lines are S53's cba0b70. It takes alpha.54 and lands after FW1a (§3) |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude` but `make check`'s; no test writes under the live home; no relay verb; no gate verb under a temp HOME but `cli.main` in a test, `spawn_serve` patched |
| may touch | `plugin/lib/claude_session/{gate.py,cli.py}`; `plugin/skills/session/SKILL.md`; `plugin/commands/gate.md`; `RUNBOOK.md`; `README.md`, `design/readme/{source.md,rendered.sha256}`; `design/gate-r1.md`; `tests/test_fw2.py`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet as `design/packets/fw2-gate-strict.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id>` in one background Bash; read the job's code from its line |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_fw2.py`: T1 to T8 green (cba0b70: `8 failed`); no existing test edited; the verify row green |
| budget | a commit per group by explicit path, the packet and the charter's five doclint rows first; stop at 80 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

- **The hidden red.** `cli.py:1014-1024` at cba0b70: `_gate_wait` prints the line and returns 0. Live, 2026-11-09: `agentik session gate wait 20261109-171112-757; echo "exit $?"` printed `gate 20261109-171112-757 <repo>: exit 2 in 14 min; log <path>`, then `exit 0`.
- **The flag is unknown, and exits 2.** At cba0b70, `python3 -B -m claude_session gate wait 20261109-120000-1 --strict`: `error: unrecognized arguments: --strict`, exit 2. A test that wants 2 for a job's 2 is green today by accident: T1 uses 7.
- **No head, no key, no estimate.** A live `result.json` holds `gate.RESULT_KEYS`'s ten keys. The last five greens under agentik-session and its worktrees ran 347.2, 322.3, 310.1, 252.0 and 456.4 s, median 5.4 min; no verb prints it. A removed worktree's path names no repo; the entry's `key` (`gate.py:325`, one for a repo and its worktrees) does, and no result keeps it.
- **What reads the output.** `unattended.py:671`, `:709-711`: `run --wait`'s last stdout line must match `GATE_LINE`, which ends on the log path, and a non-zero rc reads `gate-unrun`. `tests/test_cli.py:704`: `run`'s stdout is the queued line alone. `tests/test_gate.py:417`, `tests/test_s47.py:576`: `status()`'s four keys, a running row's five.

## 2. Rulings

- R1, `--strict`. `gate wait <id> [--timeout S] [--json] --strict` prints what it prints today and exits `gate.strict_code(result)`: the result's `exit` when it is an int from 0 to 255 and no bool, else 1. Without the flag, 0. `wait`'s own 2 (no such id) and 1 (the timeout) print nothing on stdout, so a line there marks the code as the job's, and the help says so. `run --wait` takes no `--strict`, since the unattended loop reads its rc.
- R2, `head`. `Fx.head`, default `gate._head(repo)`: `git -C <repo> rev-parse HEAD` with no `GIT_*` in its environment, under `GIT_WAIT`; 40 or 64 hex digits, else None; a `head` that raises reads None. `_start` reads it before the spawn, since a queued entry's repo may move while it waits, and keeps it on the entry in memory; `_finish` writes it. A result that never started (126, a recovered 125) holds null.
- R3, `key`. `_finish` writes the entry's `key`, a string or null. `RESULT_KEYS` ends `"cut", "head", "key"`.
- R4, `est`. `gate.estimates(root) -> {key: seconds}` reads at most `EST_SCAN = 200` results, newest first by counter. A green has `exit` 0, a null `cut`, a number of `seconds` and a string `key`. A key keeps its first `EST_GREENS = 5`, and their `statistics.median` is its estimate; under `EST_LEAST = 3` it has none. `gate.entry_estimates(root) -> {entry id: seconds}` covers the queued and running entries whose key has one. `gate.est_text(s)` is `f"{s / 60:.1f}"`. An older result has no key and is not counted.
- R5, where it prints. `status()` keeps its shape. `status_lines(st, est=None)` ends a running or queued line `; est <m.m> min` when the entry's id is in `est`, and is today's bytes otherwise. The CLI passes `entry_estimates`; `status --json` gains a top-level `est`. After the queued line `run` prints on stderr `est <m.m> min: the median of this repo's last 5 greens`, or nothing. `wait_line` and `run`'s stdout stand.
- R6, docs. `SKILL.md:199-210`, the gate sections of `RUNBOOK.md`, `README.md` and its source, and `plugin/commands/gate.md` name `gate wait <id> --strict` with R1's stdout rule, `head` and `key`, and `est <m> min` as the estimate a WAITING line's `est` is worked from. `cmd_gate`'s docstring (`cli.py:950`) cites the house configuration ledger's entry 25 for the default exit, not a bare "entry 25" (the copy names it so for the public scan; the docstring names the agentik guide's rule). One line joins `design/gate-r1.md`'s change log.
- R7. Last, as S54's R11: `2.0.0-alpha.54`, the status line, the sidecar.

Tests in `tests/test_fw2.py`, each with its red at cba0b70. They take `World` and `T0` from `tests/test_gate.py`, as `tests/test_s47.py:14` does.

| T | test | red |
|---|---|---|
| 1 | `test_fw2_wait_strict_exits_the_jobs_code` (R1: 7, 124, 0) | `assert ((2, 'usage: a...: --strict\n') == (7, '')` |
| 2 | `test_fw2_wait_strict_keeps_waits_own_codes` (R1: no id, an odd `exit`) | `assert (2 == 0)` |
| 3 | `test_fw2_result_gains_head_and_key` (R2, R3) | `('caller', 'cut') == ('head', 'key')` |
| 4 | `test_fw2_head_is_null_when_unknown_and_never_raises` (R2) | `Fx.__init__() got an unexpected keyword argument 'head'` |
| 5 | `test_fw2_est_is_the_median_of_the_keys_last_five_greens` (R4, R5: 120, 144, 150, 140 and 160 s give `; est 2.4 min`; two greens, nothing) | `module 'claude_session.gate' has no attribute 'estimates'` |
| 6 | `test_fw2_status_keeps_its_shape_and_the_cli_adds_est` (R5) | `... has no attribute 'entry_estimates'` |
| 7 | `test_fw2_run_says_est_on_stderr` (R5) | `assert '' == 'est 2.4 min:...st 5 greens\n'` |
| 8 | `test_fw2_docs_say_strict_head_and_est` (R6) | `('plugin/skills/session/SKILL.md', 'gate wait <id> --strict')`; the prototype wrote no docs |

On the cutter's prototype T1 to T7 are green and `test_gate.py`, `test_s47.py`, `test_unattended.py`, `test_hooks.py`, `test_cli.py` and `test_commands.py` stay green; the rest of the suite was not run.

## 3. Interfaces

New in `gate`: `strict_code`, `_head`, `Fx.head`, `estimates`, `entry_estimates`, `est_text`, `EST_GREENS`, `EST_LEAST`, `EST_SCAN`, `status_lines`' second argument; `result.json`'s `head` and `key`; `status --json`'s `est`; `wait --strict`. Unchanged: `wait_line`, `status()`, the inbox file, `run`'s stdout. FW1a and S54 overlap by file, never by hunk (`cli.py`: S54 `:403-406`, FW1a `:345`, here `:948-1024`, `:1233-1237`; `SKILL.md`, `RUNBOOK.md`, the README). The bump's three files collide with FW1a's bump: R7 is cut on a main that holds alpha.53.

## 4. Findings that name this row

agentik-session keeps no ledger of its own (`ls`: no such file): no own entry to carry. Bearing, uncrossed: agentik-hq 6 (Python 3.9, standard library alone: `statistics` is in it); the house configuration ledger's 25, "Exit codes report the task, not the content", which agentik-hq 4 leaves to that ledger for its own tree: the default exit keeps it and `--strict` is opt-in. `design/research.md` §3, read first, has no fact on the gate; `design/gate-r1.md` §2, rulings 1 to 3, is its design of record. NICE to file: an estimate mixes one key's commands, a land and a check (S4). No fork for the owner.

## 5. Forbidden reads

Live transcripts; `~/.local/state`; relay ledgers. Tests build their own.

## 6. Report

Six lines at most: the head sha; the gate's id and code; T1 to T8; each choice inside a ruling; leftovers.
