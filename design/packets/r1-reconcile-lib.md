# Packet R1: the reconciler's library, three detectors with no model

| item | value |
|---|---|
| from | hq `design/08-fill-wait-reconciler.md` §4 (a), its detectors table (status R1: `eff.idle`, `live.since_landing`, `live.goal_unchanged`), "Never", and "Acceptance. R1, the library" (1) to (4); §1 and §10 for the hand-run's method |
| pin | agentik-session main **after FW1b lands** (FW2 alpha.55, FW1b alpha.56); worktree `.claude/worktrees/r1-reconcile-lib`, branch `r1-reconcile-lib`, `.venv` and `.venv-floor` linked from the main checkout. Lines are 942cace's: find by the quoted words |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude` but `make check`'s; no test writes under the live home; no relay verb; no model client imported by the package (T6) |
| may touch | `plugin/lib/claude_session/reconcile/{__init__,live,idle}.py` (new); `tests/test_r1.py`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/{source.md,rendered.sha256}` (the status line alone); this packet as `design/packets/r1-reconcile-lib.md`; `history/sittings/*.md`, `history/sessions/NEXT`. Never `cli.py`, a config key, `SKILL.md`, `RUNBOOK.md`: R2 and R3 |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id>` in one background Bash; read the job's code from its line |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_r1.py`: T1 to T6 green (942cace: `6 failed`), and under `.venv-floor`; no existing test edited; the verify row green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 90 tool calls or 140k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

At 942cace, each by its command:
- Weights: `grep -n 'MIX_PRICES = \|("cache_write", 1.25)' plugin/lib/claude_session/rules.py` prints `498:MIX_PRICES = {"fable": (8.0, 40.0), "opus": (5.0, 25.0), ...` and `551:        for k, x in (("cache_write", 1.25), ("cache_read", 0.1)):`. Over input: output 5 for every family, writes 1.25, reads 0.1. (3)'s 40,000 holds: 2 x 200,000 x 0.1. `agg.py` priced 1h writes at 2.0; the code has one write price.
- Git: `gitinfo.py:19` `_TIMEOUT = 5`, `:22` `def _git(workdir: str, *args: str) -> tuple[int, str]`; `ledger.py:218-219` wraps it as `rc, out = gitinfo._git(str(cwd), *args)`.
- Charters: `charter.py:39` `DEFAULT_DIR = "history/sittings"`, `:69` `def _table(lines)`. Names are `<date>-<n>[-<row>].md`; `ls | tail -20` puts `-10` before `-2`, and one hq ran up to 17 a day (§10, `r1-days.py`: `max 17`).
- Transcripts: `meter.py:16` "message content never is" read; `:185` keys a turn `f"{obj.get('requestId')}\t{mid}"`. No lib module finds a project's transcripts (`grep -n projects plugin/lib/claude_session/*.py`: only prose). `design/research.md` §3: `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`; `ls ~/.claude/projects` shows `-Users-<user>-code-<repo>--claude-worktrees-sync-vc1`: every character outside `[A-Za-z0-9]` is `-`.
- No registration: `install.py:137-140` `_walk` is `os.walk`; `pyproject.toml` `include = ["claude_session*"]`; `test_bare_machine.py:584` globs `claude_session/*.py` alone, so the subpackage stays outside READERS (it reads transcripts, not state). No README file table; `git grep -i reconcil -- plugin`: nothing.

## 2. Rulings

- R1, the package. `claude_session/reconcile/`: `__init__.py` (`detect`, `Readers`, `finding`, `weights`, `slug`, `THRESHOLDS`), `live.py`, `idle.py`. Imports: stdlib and `..gitinfo`, `..rules`, `..charter` alone.
- R2, `detect(tree, window, now, roots, *, goal=None, thresholds=None, detectors=None, readers=None) -> [finding]`, sorted by id. `tree` suite.json's shape; `window` days; `now` epoch seconds; `roots` `{"hq", "repos", "projects"}` paths; `goal` names, default every tree repo but the hq; `detectors` default all three. A finding has exactly `id, kind, repo, value, threshold, flagged, evidence: {command, numbers, files}`: `kind` the id's prefix, `repo` the hq's basename, `flagged` `value is not None and value >= threshold`, `numbers` numbers only, never a transcript's or charter's text. A detector that cannot read gives `value` None, unflagged; never raises.
- R3, the readers. `Readers(git=_git, transcripts=idle.read_transcripts)`: `git(cwd, *args) -> stdout | None` through `gitinfo._git`; `transcripts(project_dir, since) -> [(path, [obj])]`, the folder's own `*.jsonl` (no `subagents/`) changed at or after `since`. The filesystem is `roots`, the clock `now`. R3's detectors add a field with a default (an `analyze churn --json` runner) and a root (`state`); nothing here moves.
- R4, `weights()`: `rules.mix({"shares": {"opus": 1}})["prices"]["opus"]` over its input price. No new constant.
- R5, `live.goal_unchanged`: the newest 20 charters by `(date, n)`; the goal row by `charter._table`; cut at its first comma, digits dropped, blanks folded; `value` the largest group's count; numbers `charters`, `distinct`; files the group's oldest and newest. Threshold 10.
- R6, `live.since_landing`: the newest `git log main --merges --first-parent -1 --format=%ct` over `goal` at `<repos>/<name>`; `value` the charters (name shape of R5) added in the hq since it (`--diff-filter=A -- history/sittings`); numbers `landing_at`, `charters`, `hq_commits`. No landing: since the window's start. Threshold 5.
- R7, `eff.idle`, over `<projects>/<slug(hq)>` alone: a tick opens on a user line that is no `tool_result` and not `isMeta`, at or after `now - window`; sidechain lines never count; a call is one `meter.py:185` key. Idle: no `Write`/`Edit`/`NotebookEdit` outside `history/sittings`, no Bash matching `ticks.py`'s `MUT`, no `Agent`/`Task`, no `SendMessage`. `value` the idle weighted share in %, one decimal; numbers `ticks, idle, idle_loop, idle_helper, weighted, idle_weighted, share`. Threshold 5.0.
- R8, commands. Each prints its value: R5 `cd <hq>/history/sittings && ls | grep -E <shape> | sort -t- -k1,3 -k4,4n | tail -20 | xargs grep -h -m1 '^| *goal *|' | sed -E ... | sort | uniq -c | sort -rn | head -1`; R6 the landing's `git log` line, then `git -C <hq> log --since=@<t> --diff-filter=A --name-only --format= -- history/sittings | grep -E <shape> | sort -u | wc -l`; R7 `cd <lib> && /usr/bin/python3 -B -m claude_session.reconcile.idle --since <epoch> <project dir>`, a module entry, no verb.
- R9. Last, as FW2's R7: `2.0.0-alpha.57`, the status line, the sidecar.

Decided at the cut, reversible: thresholds 5 and 5.0 (the design names only 10); `>=`; R6's value is charters, commits ride its numbers ((2) "gives 2"); charter-only writes are idle (agg.py's `idle-charter`); 1h writes at 1.25.

Tests in `tests/test_r1.py` (probes folder), worlds in `tmp_path`, git real with set dates; red at 942cace, `6 failed` under 3.12.7 and 3.9.6; the cutter's prototype (`prototype.patch`) passes all six under both:

| T | test | item | red |
|---|---|---|---|
| 1 | `test_r1_goal_unchanged_counts_the_newest_20_by_number` (32 charters; by name, 15) | (1) | `cannot import name 'reconcile' from 'claude_session'` |
| 2 | `test_r1_since_landing_counts_the_charters_opened_after_the_newest_goal_merge` (a later merge off `goal` ignored) | (2) | as T1 |
| 3 | `test_r1_idle_counts_one_of_three_and_prices_it` (split call, meta line, sidechain, old file) | (3) | as T1 |
| 4 | `test_r1_weights_are_the_mix_prices_ratios` | (3) | as T1 |
| 5 | `test_r1_every_finding_carries_its_command_and_the_command_reproduces_it` (runs each under `/bin/sh`) | (4) | as T1 |
| 6 | `test_r1_the_package_imports_no_model_client` (AST allow-list; a fresh interpreter's `sys.modules`) | (4) | `claude_session/reconcile/ is missing` |

## 3. Interfaces

New: package `reconcile` (R1 to R8). Unchanged: every module, `cli`, every config key. FW2 and FW1b overlap only at R9's three files.

## 4. Findings that name this row

No session ledger file. Bearing, uncrossed: agentik-hq 6 (3.9, stdlib); the machine ledger's entry 20; design/08 §4 "Never" (R2's text rule). The signature in §4 carries no `goal` or thresholds, both R2's keys: R2 adds them keyword-only, a gap, not a fork. Read-only over agentik-hq (`suite.json`, today 21:51): `live.goal_unchanged` 2, as the design's "here 2"; `live.since_landing` 0 charters, 1 hq commit, since another repo's d31 landing today. At the design's moment the same git lines with `--until '2026-11-09 16:00'` give agentik-session 344818a, 2026-11-07 18:37, 2 charters, 19 commits, the design's numbers. NICE to file, S4: `rules.mix` has no 1h write price (2.0 x input), so mix advice under-prices a 1h-cache orchestrator's writes. No fork for the owner.

## 5. Forbidden reads

Live transcripts (`~/.claude/projects/**`); `~/.local/state`; relay ledgers. Tests build their own.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T6 under both pythons; choices inside a ruling; leftovers.
