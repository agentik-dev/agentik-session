# Packet ck2-test-workers: the suite runs on pytest-xdist workers in both venvs

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief ck2-test-workers, rulings R1 to R7; the owner's answer "Add test workers" |
| pin | `fd8f3af` on main (g8-refusals' merge, alpha.133). Worktree `.claude/worktrees/ck2-test-workers`, branch `ck2-test-workers`; the two venvs linked |
| wall | this worktree, and the runner's install into the main checkout's two venvs by `make venv-floor` and `make venv` (R1); no push, `--amend`, rebase, merge or plugin install; `make` only through the gate queue; no `claude`; no relay verb; no test reads the live state or home; `lineguard.py` and `tests/test_g8_refusals.py` untouched (another row's); `measure.py` unchanged |
| may touch | `Makefile`, `pyproject.toml`, `tests/conftest.py`, `tests/test_ck2_workers.py` (new), `tests/test_measure.py`, a test or fixture R4 finds sharing state, this packet, `history/sittings/2026-11-17-6-ck2-test-workers.md` |
| verify | `make check`, by the gate queue, three in a row at the chosen setting, last |
| acceptance | §3; `PY -m pytest -q tests/test_ck2_workers.py tests/test_measure.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the tests, then the change |

## 1. What the source says (baseline at `fd8f3af`)

The owner, 2026-11-17, asked how the check should get more room: "Add test workers", the option that read: a row adds a parallel test runner to both Python environments, which should bring the check well under 15 minutes; it costs one new test package, also in the environment that matches a fresh Mac.

At the pin `make test` runs `.venv` (3.12.7, pytest 9.1.1) and `.venv-floor` (3.9.6, pytest 8.4.2) side by side, one process each (ck1, `c2d5094`): 4,854 tests, 1,257 to 1,290 s a pass; the check's wall is 1,800 s, the owner's number, unchanged here. Neither venv holds pytest-xdist; the Makefile has `venv-floor` and no target for `.venv`. The coordinator's six checks at the pin took 16 to 23 minutes, two red: `test_measure.py::test_status_prints_not_comparable_past_120_s` by a second's edge (R5) and `test_land3_stamp.py` by `git add -A` failing in its box (R6).

## 2. Rulings

- R1: the runner is `pytest-xdist>=3`, the `dev` extra's second package; `make venv-floor` and the new `make venv` (same shape, `VENV_PYTHON ?= python3.12`) install it beside pytest where it is absent, through the gate.
- R2: `make test` and `make test-floor` pass `-n $(WORKERS)` where `<venv>/bin/python -c 'import xdist'` succeeds; otherwise the pin's command line and one line after the pass, `workers: absent in .venv` or `workers: absent in .venv-floor`. Nothing skipped, deselected or rerun.
- R3: `WORKERS ?=` a fixed measured number, overridable; never `auto`. The table of settings is §4.
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
- R4, mended: `test_ak5_plug.py::test_describe_json` bound `describe --json` at 1.0 s of wall and took 1.001 s on 4 workers at a load near 12. It shares the cores. Its 1 s now reads the launcher's own CPU (`RUSAGE_CHILDREN`), and the wall keeps 3 s, which a wait in `describe` still breaks. No group is kept in one process.
- R6, not found; ruled out: (a) a process removing the box under `git`: creating a file or folder in a removed folder gives `ENOENT`, not `EINVAL` (probed on this Mac), and pytest's retention cleanup of `pytest-of-<user>` skips every numbered folder whose `.lock` is live (`_pytest/pathlib.py` `ensure_deletable`, both venvs), so neither pass removes the other's; (b) a name collision: `git` retries `tmp_obj_XXXXXX` on `EEXIST`; (c) the box's `git` reading the user's config: `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_NOSYSTEM` isolate it; (d) a shared folder: each test's box is its own `tmp_path`, and xdist gives each worker its own basetemp under its pass's. The test is left as it is.
- R3, the workers' table (one `make check` each, the 1-, 5- and 15-minute loads before and after; each red only by `test_ck2_workers.py`'s three cells that read an exported `WORKERS`, mended in `cdca612`, or at 4 by the count and ak5, mended after):

| workers | check s | `.venv` pass s | floor pass s | load before | load after |
|---|---|---|---|---|---|
| 3 | 469 | 469 | 436 | 6.0 7.8 7.7 | 9.9 11.9 10.3 |
| 4 | 284 | 257 | 270 | 8.4 8.0 6.8 | 9.6 10.0 8.1 |
| 6 | 329 | 239 | 315 | 4.0 6.1 7.0 | 6.0 7.8 7.7 |

  4 is the fastest check; 8 ran in the same job, after the record's commit. `WORKERS ?= 4` stays.

## 5. Forbidden reads

The wall's: the live state and the real home; of the gate's logs, only the one R6 names.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-6-ck2-test-workers.md`: the choices inside the rulings are in its handover.
