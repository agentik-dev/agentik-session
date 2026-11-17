# Packet ck2-test-workers: the suite runs on pytest-xdist workers in both venvs

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief ck2-test-workers, rulings R1 to R7; the owner's answer "Add test workers" |
| pin | `fd8f3af` on main (g8-refusals' merge, alpha.133). Worktree `.claude/worktrees/ck2-test-workers`, branch `ck2-test-workers`; the two venvs linked |
| wall | this worktree, and the runner's install into the main checkout's two venvs by `make venv-floor` and `make venv` (R1); no push, `--amend`, rebase, merge or plugin install; `make` only through the gate queue; no `claude`; no relay verb; no test reads the live state or home; `lineguard.py` and `tests/test_g8_refusals.py` untouched (another row's); `measure.py` unchanged |
| may touch | `Makefile`, `pyproject.toml`, `tests/conftest.py`, `tests/test_ck2_workers.py` (new), `tests/test_measure.py`, a test or fixture R4 finds sharing state, this packet, `history/sittings/2026-11-17-6-ck2-test-workers.md`; for the fix of review 1, also `NICE_TO_HAVE.md`, `history/NICE-overflow.md` and `history/sittings/2026-11-17-8-ck2-test-workers-fix.md` |
| verify | `make check`, by the gate queue, three in a row at the chosen setting, last; the fix of review 1, one |
| acceptance | §3; `PY -m pytest -q tests/test_ck2_workers.py tests/test_measure.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the tests, then the change |

## 1. What the source says (baseline at `fd8f3af`)

The owner, 2026-11-17, asked how the check should get more room: "Add test workers", the option that read: a row adds a parallel test runner to both Python environments, which should bring the check well under 15 minutes; it costs one new test package, also in the environment that matches a fresh Mac.

At the pin `make test` runs `.venv` (3.12.7, pytest 9.1.1) and `.venv-floor` (3.9.6, pytest 8.4.2) side by side, one process each (ck1, `c2d5094`): 4,854 tests, 1,257 to 1,290 s a pass; the check's wall is 1,800 s, the owner's number, unchanged here. Neither venv holds pytest-xdist; the Makefile has `venv-floor` and no target for `.venv`. The coordinator's six checks at the pin took 16 to 23 minutes, two red: `test_measure.py::test_status_prints_not_comparable_past_120_s` by a second's edge (R5) and `test_land3_stamp.py` by `git add -A` failing in its box (R6).

## 2. Rulings

- R1: the runner is `pytest-xdist>=3`, the `dev` extra's second package; `make venv-floor` and the new `make venv` (same shape, `VENV_PYTHON ?= python3.12`) install it beside pytest where it is absent, through the gate.
- R2: `make test` and `make test-floor` pass `-n $(WORKERS)` where `<venv>/bin/python -c 'import xdist'` succeeds; otherwise the pin's command line and one line after the pass, `workers: absent in .venv` or `workers: absent in .venv-floor`. Nothing skipped, deselected or rerun.
- R3: `WORKERS ?=` a fixed measured number, overridable; never `auto`. Since review 1's L1 a plain `WORKERS =`: the command line overrides it, the caller's environment does not. The table of settings is §4.
- R4: a test that fails on workers only is mended at what it shares; a group kept in one process is named in §4 with its reason. No retry.
- R5: the test stamps the measure 300 s before the meter's own `ts`, so both reads truncate on the same second; a test of the test forces the edge with a fixed clock and shows the pin's arithmetic red.
- R6: the cause of `git add -A`'s `Invalid argument`, or what was ruled out, in §4.
- R7: the Makefile's help lines name the workers; `design/readme/source.md` names no minutes and its `make test` line stays true, so the README is not rendered.

## 3. Interfaces and acceptance

- `make test [WORKERS=n]`, `make test-floor [WORKERS=n]`, `make venv`, `make venv-floor`; the line `workers: absent in <venv>`.

| # | line | at the pin |
|---|---|---|
| A1 | `make check` green, three in a row, at the chosen setting; minutes and loads in §4 | 16 to 23 min, two of six red |
| A2 | the check under 10 minutes at a load under 12, or what bounds it | 16 to 23 min |
| A3 | each pass reports the pin's count plus this row's tests; none skipped that ran at the pin | 4,854 passed; 4,704 passed, 128 skipped |
| A4 | a venv without the runner: `make test` green as before, with its one line (`tests/test_ck2_workers.py`) | no such line |
| A5 | R5's test green 200 times in a loop; red at the pin's arithmetic when the edge is forced | fails by chance |
| A6 | R6: the cause, or what was ruled out | not known |
| A7 | `scripts/doclint`, `scripts/recordlint`, hygiene and the version check green | green |

## 4. Findings that name this row

- The pin's counts, read again: the brief's 4,854 and 4,704 + 128 are ef0ba32's (ck1); at `fd8f3af` the README's Status line reads 4,889 collected, and the floor pass 4,740 passed + 128 skipped (this row's first floor pass, 4,749 + 128, less its 9 tests). This row adds 9 tests: 8 in `tests/test_ck2_workers.py`, 1 in `tests/test_measure.py`.
- R4, mended: `test_ak5_plug.py::test_describe_json` bound `describe --json` at 1.0 s of wall and took 1.001 s on 4 workers at a load near 12. It shares the cores: a cold first spawn at a load of 15 took 0.45 s of wall, a warm one 0.08 s (review 1). Its first, cold call is bounded by its own CPU (`RUSAGE_CHILDREN`) under 1 s, and a second, warm call by 1.0 s of wall, ak5's line; a test of the test, a made-up launcher that waits 1.5 s, is red (fix of review 1, F1: the first build's 3 s of wall passed it). No group is kept in one process.
- R6, not found; ruled out: (a) a process removing the box under `git`: creating a file or folder in a removed folder gives `ENOENT`, not `EINVAL` (probed on this Mac), and pytest's retention cleanup of `pytest-of-<user>` skips every numbered folder whose `.lock` is live (`_pytest/pathlib.py` `ensure_deletable`, both venvs), so neither pass removes the other's; (b) a name collision: `git` retries `tmp_obj_XXXXXX` on `EEXIST`; (c) the box's `git` reading the user's config: `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM` isolate it; (d) a shared folder: each test's box is its own `tmp_path`, and xdist gives each worker its own basetemp under its pass's. The test is left as it is.
- R3, the workers' table (one `make check` a row, the 1-, 5- and 15-minute loads before and after). The red rows were red only by `test_ck2_workers.py`'s three cells that read an exported `WORKERS` (3 and 6, mended in `cdca612`) or, at 4, by the count and ak5 (mended after); the three green rows at 4 are A1's, one gate job on `f64adef`, each `4898 passed` and `4749 passed, 128 skipped`:

| workers | check | check s | `.venv` pass s | floor pass s | load before | load after |
|---|---|---|---|---|---|---|
| 3 | red | 469 | 469 | 436 | 6.0 7.8 7.7 | 9.9 11.9 10.3 |
| 4 | red | 284 | 257 | 270 | 8.4 8.0 6.8 | 9.6 10.0 8.1 |
| 6 | red | 329 | 239 | 315 | 4.0 6.1 7.0 | 6.0 7.8 7.7 |
| 8 | green, `cdca612` | 278 | not read | not read | 9.9 | 17.4, the 5-minute 22.6 |
| 4 | green, `f64adef` | 323 | 300 | 301 | 11.5 20.5 15.8 | 13.0 16.2 15.1 |
| 4 | green, `f64adef` | 274 | 251 | 266 | 13.0 16.2 15.1 | 9.6 12.1 13.6 |
| 4 | green, `f64adef` | 305 | 283 | 297 | 9.6 12.1 13.6 | 10.6 12.3 13.3 |

  `WORKERS = 4` stays, though 8's one check was 6 s faster than 4's first, red one and faster than two of its three green ones: the passes at 8 put the load at 22, near twice the 12 above which the gate holds a job (0.75 of 16 cores), so another job queued beside the check would wait on it; the loads at 4 ran 9.6 to 13.0. A1 holds at 4: three green checks in a row, 274 to 323 s, under A2's 10 minutes.

## 5. Forbidden reads

The wall's: the live state and the real home; of the gate's logs, only the one R6 names.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-6-ck2-test-workers.md`: the choices inside the rulings are in its handover.
