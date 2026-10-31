# Packet S47: the gate queue, one running per repo under a load ceiling

| item | value |
|---|---|
| from | a private hq's intake of 2026-10-29, its fix 3: "The runner keys its mutex by repo, not by Mac: a one-minute client gate does not wait behind a 40-minute gate. TLC keeps its exclusive lock"; `design/gate-r1.md` ruling 1: "S38 runs one entry at a time and records the key; fix 3 flips to one per key"; the readings in §1 |
| pin | 26362e4 (main, alpha.31); worktree `.claude/worktrees/s47-gate-key`, branch `s47-gate-key` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run a real `gate run` or `gate serve`; tests fake every effect through `Fx`; never run a relay verb, or build or run a relay binary |
| may touch | `claude_session/gate.py`, `claude_session/cli.py` (`gate status` only), `claude_session/resolver.py` (the gate section's two new keys), `tests/test_gate*.py`, `tests/test_s47.py` (new), `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `RUNBOOK.md` §5, `plugin/skills/session/SKILL.md`, `design/gate-r1.md` (its change log), `NICE_TO_HAVE.md`, and the version act's pins as 694bf81 touched them; this packet; the charter, `history/sittings/2026-10-30-4-s47.md` |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s47.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on 26362e4: no such file); `.venv/bin/python -B -m pytest tests/test_gate.py -q 2>&1 \| tail -1` reads `passed`, no `failed`, every S38 test green unchanged but those ruling 7 names; doclint, hygiene and the version check green. The whole suite is the gate's |
| verify | the gate, by the coordinator |
| budget | acts: 0 this packet; 1 the tests, red; 2 the key and the choice; 3 the runner's set; 4 the docs; 5 the version, the README count, the sidecar (last, one bump; 694bf81 is the model). 80 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says, and the readings

The intake's acceptance: "A client gate queued behind a [long, private repo's] gate starts at once; the load average at the 1 min mark stays under the core count during both." Its other line: "One TLC at a time, after the OOM of 2026-10-22."

Readings, 16 cores: the FIFO held a one-minute gate and the eleven behind it an hour (load 20, 41, 43, 2026-10-30 04:17); on 2026-10-30 a two-minute gate waited 64 minutes behind a 96-minute one; on the same evening an 840 s `make check` was cut by its own wall at load 20 with the queue running one entry at a time, so load comes from outside the queue too and more concurrency must never be added on top of it.

## 2. Rulings

1. **The key.** One running per key. The key is the realpath of `git -C <repo> rev-parse --git-common-dir`, taken at `enqueue` and stored in the entry as `key`, so a repo and all its worktrees are one key. Not a git tree, or git failing: the repo's realpath. An entry with no `key`, an older queue's, reads its repo's realpath. Never raises.
2. **A lock is exclusive.** An entry does not start while a running entry names any of the same `locks` paths, whatever its key: the command may not have made its lock yet when the second starts, and the TLC rule is one at a time. Today's rule stands beside it: no start while a named path exists.
3. **The choice.** The oldest entry that passes 1 and 2 and has no lock path existing starts, as today a younger unlocked entry may. FIFO within a key holds: a younger entry of a key never passes an older one of that key that is waiting on a lock.
4. **The ceiling, before a second starts.** With nothing running, an entry starts whatever the load: today's behaviour, so a loaded Mac is never starved. With one or more running, it starts only when all hold: `len(running) < max_running` (default 3); the 1-minute load average is under `load_ceiling` (default 0.75 × `os.cpu_count()`, 12 on this Mac); and at least `start_settle` seconds (60, a constant, tests through `Fx`) have passed since the last start, since a load average lags. A failed read of the load counts as over the ceiling. Above the ceiling the queue behaves exactly as S38's does. `status` says it: `queued <id> <repo> position <n> waits on load <x> over <c>`, and `waits on key <key's basename>`, beside the existing `waits on lock PATH`.
5. **The runner.** One process still, one `runner.lock`; it holds a set of running children and polls them, so a wall cut, a finish or a start of one never waits on another. Each child keeps its own process group, log, wall, `result.json`, inbox line and ntfy. `runner.json` keeps `pid` and `since`; `running` becomes a list of `{id, pgid}`. `_recover` takes a dead runner's list and kills and closes each, and still reads the old single form (`running` a string with `pgid`), since an alpha.31 runner may have died holding one. The 126 cut, `_prune`, and the idle exit (only with nothing running or queued) are unchanged in meaning. A `position` read lists entries not running. `_running_id`'s callers read the list.
6. **`Fx`** gains the load read and the core count; `test_s47.py` fakes both and the clock, with no real spawn but one small end-to-end pair of `sleep`-free child commands if the S38 tests already do so.
7. **S38's tests** that pin `running` as one id, or one child at a time with a free key, are the ones that may change: list each in the report with why. Names to write: `test_s47_two_repos_run_together`; `test_s47_a_worktree_shares_its_repos_key`; `test_s47_one_key_stays_fifo_past_a_lock`; `test_s47_a_shared_lock_is_exclusive_across_keys`; `test_s47_above_the_ceiling_is_serial`; `test_s47_nothing_running_starts_whatever_the_load`; `test_s47_settle_between_starts`; `test_s47_max_running`; `test_s47_a_failed_load_read_is_over`; `test_s47_a_wall_cut_leaves_the_other_running`; `test_s47_recover_kills_each_of_the_set`; `test_s47_recover_reads_the_old_single_form`; `test_s47_an_entry_with_no_key_reads_its_repo`; `test_s47_status_names_each_wait`; `test_s47_client_gate_behind_a_long_gate_starts_at_once`, the intake's acceptance under a load below the ceiling.
8. **Config.** `gate.load_ceiling` and `gate.max_running` in the user layer, read as `gate_config` reads `wall`; a bad value reads as the default, one line in `runner.log`.
9. **The version:** 2.0.0-alpha.32 in all five pins, one bump, last.

## 3. Interfaces (signatures, not prose)

`gate run`, `wait` and `status` keep their flags and their exit codes. An entry gains `key`. `runner.json`'s `running` is `[{id, pgid}]`. `status --json`'s running is a list; name its old shape in the report.

## 4. Findings that name this row

None. A private organisation's sitting consumes this and passes its TLC lock by `--lock`, as today.

## 5. Forbidden reads

Transcripts; `~/.local/state`, every part; every other repo, but `GUIDE.md`.

## 6. Report (under 15 lines)

Commits; tests; S38's tests that moved; the status JSON's shape; forks; anything unmet.
