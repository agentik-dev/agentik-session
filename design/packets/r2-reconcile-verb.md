# Packet R2: the reconciler's key, its cadence and its verb

| item | value |
|---|---|
| from | hq `design/08-fill-wait-reconciler.md` §4 (b), Config, Cadence, Never, "Acceptance ... R2" (5) to (7), (5) with the floor of 24 (fold E4); §11 C2, the launcher's close |
| pin | agentik-session main **after R1 lands** (alpha.57); worktree `.claude/worktrees/r2-reconcile-verb`, branch `r2-reconcile-verb`, the two venvs linked from main. Lines are 942cace's: find by the quoted words |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude` but `make check`'s; no test writes under the live home; no relay verb; no `reconcile brief`, skill, Fable read or churn detector (R3's) |
| may touch | `plugin/lib/claude_session/{resolver,cli,chain}.py`; `plugin/lib/claude_session/reconcile/runner.py` (new); `tests/test_r2.py`; `RUNBOOK.md` (§3's keys, §4's launcher); `README.md` and `design/readme/{source.md,rendered.sha256}` (the verb row, the status line); `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet as `design/packets/r2-reconcile-verb.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash; its exit is the job's |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_r2.py`: 24 green (R1 landed: `23 failed, 1 passed`, T8 the control), and under `.venv-floor`; no existing test edited; the verify row green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 90 tool calls or 140k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

At 942cace, each by its command:
- The key's home. `git grep -n '"pacing", "admission")' -- plugin/lib/claude_session/resolver.py`: `73:`, the end of `SESSION_KEYS`; `:224` `unknown.append(f"{layer}: session.{sk}")` reports any other. On R1's base `session.reconcile` reads `unknown == ['config.yaml: session.reconcile']` (T5). The launcher reads `respawn` so: `chain.py:120` `r = resolver.resolve(cwd, _GUARD_SESSION, env,`.
- The parser. `yamlsubset.py:8`: `{k: v}` flow mappings one level deep; a dotted key loads (`live.goal_unchanged: 10`). Stdlib only (the coordinating repo's entry 6).
- The exits (`grep -n 'report the task' GUIDE.md`). `cli.py:385` `return 2 if bad else 1 if red else 0` (`charter check`'s red is 1). The suite guide's `GUIDE.md:84`: "Exit codes report the task, not the content. 0: done. 1: a check said no. 2: usage or a failed precondition. 3: not installed". Design §4 (b): "exit 0 clean or not due, 3 flagged, 2 config". §4 below.
- The launcher. `chain.py:434` `prev, sid, args = sid, nxt, succ`, then `continue`: the restart line is written, the successor not yet spawned. `chain.py:320` `kill_grace=30`; `gate.py:477` `runner = Path(__file__).resolve().parent.parent / "agentik-session"`.

## 2. Rulings

- R1, the key. `session.reconcile` joins `SESSION_KEYS`, resolved through every layer as `respawn` is; `_validate` never reads it: a bad key is the verb's exit 2, never a session's refusal (T5).
- R2, the check (`reconcile/runner.py`, `check`). Keys `tree, goal, window, every, detectors, thresholds, read, record`; any other names itself. `tree` required, a repo file with a `repos` list; `goal` its names; `window` days, default 14; `every` hours, default 24, under 24: `session.reconcile.every is 3 hours; its floor is 24 (detectors at most daily)`; `detectors` and `thresholds`' keys among R1's exported `THRESHOLDS`, a threshold a number 0 or more; `read` ints of `every, floor, turns, context`, default `168, 168, 40, 120000`, `floor` at least 168, `every` at least `floor` (R3 acts on it); `record` a relative folder inside the repo, default `history/reconcile`. A failure: exit 2 naming the key's path, no `detect`, nothing written.
- R3, the verb. `agentik session reconcile [--json] [--force]` beside `unattended`, no positional (R3's `brief`). The repo is the cwd; roots `hq` the cwd, `repos` its parent, `projects` `$HOME/.claude/projects`; it calls `reconcile.detect(tree, window, now, roots, goal=, thresholds=, detectors=)` at call time, R1's contract alone. Exits as the design: 0 clean or not due, 3 flagged, 2 the config or an unwritable record. Stdout: `flagged <id>: <value> >= <threshold>` each, then `reconcile: <k> of <n> flagged; record <path>`; else `not due until <ISO minute, offset>`. `--json`: `{due, record, flagged, findings}`, or `{due: false, last, next}`.
- R4, due. The last run is the newest `<record>/YYYY-MM-DD.md` by name and its `run: <ISO>;` line; inside `every` of it, not due, and the run reads that one file and writes none. Chosen at the cut, reversible: no second store to drift, nothing under the state root; a deleted record makes the next run due. `--force` runs, its stamp the new last run; one date's second run replaces its file (`os.replace`).
- R5, the record. `# reconcile <date>`; `run: <ISO seconds>; tree <t>; window <w> d; every <e> h; <k> of <n> flagged`; one table `| id | value | threshold | flagged | command |`, id and command in backticks, each `\|` escaped, whitespace folded, a non-number `n/a`. Numbers and files: `--json` alone; no charter or transcript text (T4). R1's commands run about 350 B; past 4,096 B it writes and its summary ends `(<n> B, over 4096)`.
- R6, the close. `chain.RECONCILE_WAIT = 30`, the launcher's own `kill_grace`. `reconcile_argv()`: `gate.spawn_serve`'s interpreter, `-I`, pycache prefix and the tree's `agentik-session`, then `reconcile`, no `--force`, so the verb's `every` decides. `Effects.reconcile(cwd, timeout) -> (exit or None, last line)`: `subprocess.run`, the timeout, stdin `/dev/null`, output captured; a cut or `OSError` is None. `Chain._reconcile()` runs after the restart line and before the successor (`:434`), only when `runner.wanted` (the key set and resolvable); one `say` line `<chain>: reconcile exit <n>: <line>`, or `<chain>: reconcile: cut after 30 s`; an exception is that line. Never at a stop close. The successor waits at most 30 s and the kill's reap.
- R7. Last: `2.0.0-alpha.58`, the status line, the sidecar; the README row, RUNBOOK's two paragraphs.

Tests in `tests/test_r2.py` (probes folder), worlds in `tmp_path`, the launcher's on `test_chain`'s `_fx` with a fake `reconcile` effect; reds on R1's base, 3.12.7 and 3.9.6:

| T | test | item | red |
|---|---|---|---|
| 1 | `test_r2_config_exits_2_naming_the_key` (12); `test_r2_defaults_and_a_good_config_run` | (5) | `usage: agentik session ...`: argparse's 2, kept red by the words asserted |
| 2 | `test_r2_a_second_run_inside_every_is_not_due_and_writes_nothing` (3 h and 23:59:59 on; `--json`; `--force`) | (6) | `assert 2 == 0` |
| 3 | `test_r2_two_flagged_of_five_exit_3_and_a_record_of_five_rows` (400 B commands with pipes) | (7) | `usage: ...` |
| 4 | `test_r2_the_record_holds_no_charter_text` (R1's real `live.goal_unchanged`) | Never | `usage: ...` |
| 5 | `test_r2_the_key_is_known_and_a_bad_one_never_breaks_a_session` | R1 | `['config.yaml: session.reconcile']` |
| 6 | `test_r2_the_launcher_runs_the_pass_at_a_respawn_close` (once, before the successor, 30 s) | C2 | `no attribute 'RECONCILE_WAIT'` |
| 7 | `test_r2_a_failed_or_slow_pass_never_stops_the_respawn` (exit 2, cut, raises, 30 s) | C2 | `assert (2 == 2 and 0 == 1)` |
| 8 | `test_r2_no_key_no_pass` | C2 | the control, green |
| 9 | `test_r2_the_real_pass_is_cut_at_its_bound` (a sleeper cut at 1 s) | C2 | `no attribute 'reconcile_argv'` |

The cutter's `prototype.patch` passes all 24 under both; neighbours in the probes' README; `test_readme` reds on the count until R7.

## 3. Interfaces

New: `SESSION_KEYS`' `reconcile`; `reconcile/runner.py` (`KEYS`, `READ_KEYS`, `READ_DEFAULTS`, `EVERY_FLOOR`, `READ_FLOOR`, `RECORD_CAP`, `ConfigError`, `raw`, `wanted`, `check`, `last_run`, `record_text`, `run`); `cli.cmd_reconcile`; `chain.RECONCILE_WAIT`, `chain.reconcile_argv`, `Effects.reconcile`, `Chain._reconcile`. Unchanged: R1's `detect`, `Readers`, the finding's keys, `_validate`, every other verb. R1's T6 allow-list holds (`runner.py`: `json, os, re, datetime, pathlib`, the package relatively).

## 4. Findings that name this row

No session ledger. Bearing, uncrossed: hq 6; the machine ledger's entry 20; §4 Never (R5). **Ruled by the orchestrator, 2026-11-09 23:05: flagged exits 1**, the guide's "a check said no", as `charter check` gives its red; 3 stays "not installed". Wherever this packet, `test_r2.py` (`:154`, now `rc == 1`) or the prototype says 3 for flagged, read 1; design/08 §4 is amended to match. The cutter's fork before the ruling is in the coordinating repo's original. NICE to file, S4: a record past 4,096 B is written and said, not cut.

## 5. Forbidden reads

Live transcripts; `~/.local/state`; relay ledgers. Tests build theirs.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T9 under both pythons; choices inside a ruling; leftovers.
