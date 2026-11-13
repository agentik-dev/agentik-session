# Packet h3: five reproduced faults in the state files and one test

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief h3 (hq `history/sessions/BRIEF-2026-11-12-session-h3-hardening.md`); NICE n20, n56, n86, n99, n100, each a reproduced correctness bug |
| pin | `33a4d85` on main (g4 merged, 2.0.0-alpha.89). Version 2.0.0-alpha.90. Worktree `.claude/worktrees/h3-hardening`, branch `h3-hardening`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state (temp folders only); no relay verb |
| may touch | `plugin/lib/claude_session/{chain,meter,admission}.py`; `plugin/lib/claude_session/hooks.py` (`_load_json` only: `mt1-model-tiers` works in that file); `tests/test_h3_hardening.py` (new); `tests/test_unattended.py` (n86's test only); `NICE_TO_HAVE.md` (the five rows leave); `plugin/.claude-plugin/plugin.json`, `README.md`, `design/readme/{source.md,rendered.sha256}` (the version's own commit); this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | §3; `tests/test_h3_hardening.py` red at the pin, green now, under both venvs |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `chain.Chain._ready` (chain.py:682) computes `now - ended < settle`: a JSON integer past a float's range in `turn-ended.json` raises OverflowError out of `_ready` and `run()`. `_opened` (:282) already compares, never subtracts.
- `hooks._load_json` (hooks.py:824) catches `OSError, ValueError`; a deeply nested file raises RecursionError. `meter._load` (meter.py:311) reads the same `resolved.json` in the same PostToolUse and has the same catch.
- `meter._write_atomic` (meter.py:303) writes through the fixed name `<file>.tmp`; two writers race on it.
- `admission._save_carry` (admission.py:1466) writes nothing when the text passes `BAND_MAX` (64 KiB).
- `test_a_dying_run_kills_its_child` asks `os.killpg(pgid, 0)` once, right after the run dies; a grandchild of the killed group may not yet be reaped.

## 2. Rulings (brief h3)

- The owner's words: none new; each row is a reproduced correctness bug.
- R1 n56: `_ready` compares as `_opened` does; a value the hooks did not write cannot raise and reads as not ready, never ready.
- R2 n99: `_load_json` treats RecursionError as a file that does not parse. Nothing else in `hooks.py` changes.
- R3 n100: `meter.save` writes through a temp name unique to the writer, in the same folder, then the atomic replace; a lost race is one stale write, never an exception, no temp file left.
- R4 n20: `_save_carry` drops the oldest entries until the text fits, and writes.
- R5 n86: the test polls the group's absence with a bound of a few seconds; the product is unchanged.
- Decided for the builder: no new knob, flag or log line; version the next alpha after main's, in its own commit.

## 3. Interfaces: the acceptance table (brief h3)

1. n56: `_ready` with `ended`, the marker's and the activity's value each `10 ** 400` returns without raising and reads not ready. Pin: OverflowError.
2. n99: a state file of 200,000 `[` through `_load_json` returns what a file that does not parse returns, and the PostToolUse dispatch still gives its output. Pin: RecursionError.
3. n100: 200 concurrent `meter.save` calls from 8 processes: no exception, the file parses after each, no `.tmp` left. Pin: red.
4. n20: a carry that would pass 64 KiB is written under the bound, its newest entries kept; a reset at the next rotation is honoured. Pin: not rewritten.
5. n86: the test passes 20 of 20 under a load of several busy processes; with the product's kill removed it goes red.
6. `make check` green through the queue, once, last.

## 4. Findings that name this row

- NICE n20, n56, n86, n99, n100 close with this packet and leave `NICE_TO_HAVE.md` in its last commit.

## 4a. Round 1 (the hq's refutation of 3c14608, 2026-11-12)

- Main (aee2f99) merged on the coordinator's word; NICE keeps neither n86 nor n87.
- F1 blocked acceptance 4, R4 re-ruled: past BAND_MAX the other logins' weeks go first, oldest first, then this call's own (`out`); the current login's carry is the last to go. Red at 3c14608: others resetting 2 to 7 h later gave `(0, 2)` for `(1, 1)`.
- F2: `_ready` bounds `ended` as `_opened` does (`AT_FLOOR <= ended`); a huge negative, `-inf` or negative end reads not ready. `ended=0, written=-1` now reads not ready (it read ready).
- F3: `chain._json` and `meter._scan` treat RecursionError as a file or line that does not parse.
- F4 filed as NICE n148, not built. Version 2.0.0-alpha.91 in its own commit (3335 tests).

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made, what was not done.
