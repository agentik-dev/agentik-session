# Packet gl1-gate-record: what the machine was doing, in each gate result

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief gl1 (a packet row, a small one, level S4); hq design/19 §3 item 10 and §6's row gl1 |
| pin | `7c1f711` on main (2.0.0-alpha.113, the merge of ss5-meter-rest). Worktree `.claude/worktrees/gl1-gate-record`, branch `gl1-gate-record`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only, once, last); no `claude`; every test fakes its runner in a temp state root, and none starts, stops or signals the installed runner or reads the live gate folder; no relay verb |
| may touch | `plugin/lib/claude_session/gate.py` (`RESULT_KEYS`, `Fx`, `_start`, `_close`, `_finish`, `status`, the module docstring, two readers beside `_head`), `plugin/lib/claude_session/land.py` (the check step, `Red`, the red line, the docstring), `plugin/lib/claude_session/cli.py` (`_gate_land`'s `--in-job` branch passes the job's log), `tests/test_gl1_record.py` (new), `tests/test_fw2.py` (line 78, the count), this packet, `history/sittings/2026-11-14-2-gl1-gate-record.md`; in the last commit alone, the stamp's files |
| verify | `make check` through the gate queue, once, last |
| acceptance | §3; `tests/test_gl1_record.py` green under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline measured at `7c1f711`)

A gate result says what ran and how it ended, and nothing of the machine: design/19 could not say whether a flake met a load of 10 or 18, since no record held it. This row records the load, the jobs running beside the job and the dirt of its folder, and makes a landing whose check was refused before it ran say so on its line. No job waits, starts or ends differently.

- `gate.RESULT_KEYS` holds 12, `id` to `key`; a result a faked runner writes in a temp state root holds the same 12; `tests/test_fw2.py:78` pins the count and `[-2:] == ("head", "key")`.
- `gate status --json` over a temp state root: the envelope's keys are `done`, `est`, `ok`, `queued`, `runner`, `running`, `schema`; a `done` item holds `id`, `repo`, `exit`, `seconds`, `cut`.
- `gate land --in-job` on a made-up repo `crate` whose `check` writes `bounded: stop: load` on stderr and exits 3 (a temp HOME, nothing queued): stderr ends `bounded: stop: load`, `make: *** [check] Error 3`; stdout `land crate: red check exit 2`, exit 2. The same with `bounded: nested stop: wall`, and with no such line. So the stop line is not the output's last line: `make` writes after it, and the rule reads the last line that opens `bounded: `.
- These match the brief's figures, measured at `5890501` (alpha.106).

## 2. Rulings (brief gl1)

- R1, three keys. `result.json` gains `load`, `beside` and `dirty`, in that order after `key`; `RESULT_KEYS` holds 15. `load`: `{"start": [a, b, c], "end": [a, b, c]}`, the three load averages as `os.getloadavg` gives them, each rounded to two places, read just before the spawn and just after the child is reaped; a side that cannot be read is null. `beside`: the ids the runner had running when this job started, oldest first; an empty list when none. `dirty`: `{"start": n, "end": n}`, the count of lines of `git -C <the job's folder> --no-optional-locks status --porcelain --untracked-files=all`, run as `_head` runs git (none of the caller's `GIT_*`, under `GIT_WAIT`, never raising); a side is null when the folder is in no work tree, git fails or the wait passes.
- R2, when they are null. A result the runner writes for a job it did not start and end itself (127, a command that cannot start; `_recover`'s 125) holds each key: `load` and `dirty` are always the two-sided object, a side null where it was not read, and `beside` is null where it was not read, never an empty list.
- R3, effects. Each read goes through `Fx` (`loads` and `dirty`, beside `load` and `head`), so a test fakes it. `_over` keeps reading the one-minute `load`; the two are not merged. A read that raises is a null and one line in the runner's log, never a job's failure, and never more than `GIT_WAIT` added to a job's start or end.
- R4, `status --json`. Each `done` item gains `load`, `beside` and `dirty` as the result holds them, null for a result that predates the keys. The text of `gate status`, `gate wait`'s line and the inbox's keys keep their bytes.
- R5, `unrun`. When the check step exits non-zero and the last line of its output that opens `bounded: ` is `bounded: stop: lock`, `bounded: stop: load` or `bounded: stop: wall`, the land line reads `land <repo>: red check exit <code>, unrun <lock|load|wall>`. The code is the step's. `bounded: nested stop: <why>` is not it, and a line after the stop line changes nothing. The check's output still reaches the job's log as it comes, in order, both streams.
- R6, the words. `gate.py`'s and `land.py`'s docstrings name the keys and the `unrun` part. No README line and no skill line.

## 3. Interfaces and acceptance

- `gate._dirty(repo) -> int | None`, beside `_head`: the git child in a session of its own, so a wait that passes kills its group and never waits on a grandchild's pipe.
- `Fx.loads` (default `os.getloadavg`) and `Fx.dirty` (default `_dirty`). At the start the runner reads `dirty`, then `load`, after the head and before `started`; at the end `load`, then `dirty`, after `ended`. So neither read moves a job's `seconds`.
- 127: the start sides and `beside` as read; the end sides null, since no child was reaped. 125, 126 and a caller's 130 before a start: every side null and `beside` null.
- The stop line is read from the tail of the job's own log, not a tee: `land.main(argv, log=None)`; `gate land --in-job` passes `<state>/gate/<mark>/log`. `land.log_size(log)` takes the log's size just before the check, and only when the log is this run's stderr by device and inode; after a red check, `land.last_bounded(log, begin)` reads from there (its last 64 KiB at most) the last line that opens `bounded: `. So the check writes to stderr exactly as at the pin, and a writer it leaves behind still reaches the log until the runner's close. A tee was built first and refused by two unedited tests: `tests/test_land.py` pins `land.py`'s imports (no `threading`), and `tests/test_fw4c.py`'s t14 needs a leftover writer's lines after the land line, which a tee loses once land exits.

All in `tests/test_gl1_record.py`, a faked runner in a temp state root and made-up repos.

| # | line | at the pin |
|---|---|---|
| 1 | a job that runs to its end: 15 keys in order; `load` the faked three, rounded; `beside` the one job that ran beside it; `dirty` `{"start": 2, "end": 3}` for a folder with two loose paths that the job adds one to | 12 keys, none of the three |
| 2 | a folder in no work tree, a `git` that exits 128 and one that sleeps past the wait: that side of `dirty` null, the job's exit and seconds untouched | no such key |
| 3 | a command that cannot start (127) and a recovered job (125): the three keys present, `beside` null on the recovered one | no such key |
| 4 | a load read that raises: `load.start` null, one line in the runner's log, the job runs | no such key |
| 5 | `status --json`: a new result's `done` item carries the three; a 12-key result's carries three nulls; the text status byte-equal to the pin's | `id`, `repo`, `exit`, `seconds`, `cut` |
| 6 | `crate`'s check writes `bounded: stop: load` and exits 3: `land crate: red check exit 2, unrun load`, exit 2; the same for `lock` and `wall`; `nested stop: wall`, and a red with no such line, give the pin's line | `land crate: red check exit 2` |
| 7 | the check's output in the job's log is the pin's, line for line and in order, and reaches it while the check runs; a writer the check leaves behind holds no landing | the check's lines green; the land line red (no `unrun`) |
| 8 | `tests/test_fw2.py` passes with line 78 edited (the count 12 to 15); `tests/test_gate.py` and the land tests unedited | green |
| 9 | both venvs; `make check` once, last, through the gate queue; the next alpha by `make stamp`, its files alone as the last commit under `plugin/` | green at alpha.113 |

## 4. Left

A hold on a first start (design/19 §4: built only when 14 days of these loads show it is owed); `gate status --repo` and `head` on its lines (rw3); the proof of green that reads `dirty` (land5); the ready step (land4, which keeps `unrun` in the line).

## 5. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.
