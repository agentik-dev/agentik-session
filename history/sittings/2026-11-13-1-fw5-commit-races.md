# Sitting 2026-11-13-1: agentik-session, fw5 commit, checkpoint and the gate under several writers

| item | value |
|---|---|
| goal | packet fw5 (`design/packets/fw5-commit-races.md`): R1 witness index, R2 what stands, R3 `checkpoint --commit <paths...>`, R4 a cut wait cancels its job, R5 no wait on the job's own key; phase 1 ends at the commits |
| budget | builder: about 90 tool calls (build 1); the fix of review 1: about 90 more; phase 2: about 90 more |
| pin | f1cbccd on main (alpha.94); worktree `.claude/worktrees/fw5-commit-races`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the pin measured by `tests/test_fw5.py` (15 failed, 3 passed at f1cbccd)
- [x] the packet
- [x] tests first committed (red at f1cbccd: 15 failed, 3 passed)
- [x] R1 and R2 (commit.py; the core split as `_core`, `commit_paths` for R3); test_fw4d changed for R2: the three round-2 tests (another writer's commit, staging, SIGTERM: the plain `red check` line or none) and the two r1_f3 tests (the restore that cannot be made now reached by a red commit holding index.lock)
- [x] R3 (cli.py `cmd_checkpoint`, the parser's `paths`); test_cli changed for R3: `test_checkpoint_help_names_tracked_only` and `test_checkpoint_commit_stages_tracked_only` (renamed for the paths), and four respawn tests that ran `-c` with no path (s19's helper refusal and its control, s22's tracked and untracked charter) now name their paths
- [x] R4 (commit.py `_gate_check` writes the mark in a `finally`, the signals held; gate.py `cancel`, `cancel_path`, `_step` closes a marked entry unrun, `_reap` cuts a marked child as the wall does, `_finish` and `_sweep_marks` drop marks); test_gate, test_fw2, test_fw4c, test_fw4d, test_s47 green (240)
- [x] R5 (cli.py `cmd_gate`, `_own_entry`): `gate run --wait` of the job's own key and `gate wait` of a queued id of that key exit 2; the six named test files green under `.venv-floor` (175)
- [x] docs (README and source, sidecar by `shasum`, RUNBOOK §checkpoint and §6, SKILL.md, the checkpoint command, help) and n71, n78, n81, n84 out of NICE; doclint and recordlint pass; the README's test count (3455, now 3473 collected) left for phase 2
- [x] review 1's fix, tests first: F1 (the `add -N` span), the moved line asserted, git's reason on stdout; red at 2a9fa14 (4 failed)
- [x] review 1's fix: `_take` (index.lock, out of `_put_back`), `_intent`, `_unadd` and `_tell_moved` (commit.py), git's stdout reason on stderr; the seven named test files 328 green under `.venv` and `.venv-floor`
- [x] review 1's records: the packet's section 7 (F1, the ruling, the `checkout --` sentence); NICE n169 to n173, renumbered n192 to n196 in phase 2, for leads 1 to 3, 5 to 7 and 10 (4, 9 and 11 built; 8 needs no change)
- [x] phase 2: main 807013d merged (dda80cf; NICE n192 to n196), the version alpha.100 and 3958 tests (this commit); the gate's `make check` is the landing's

## Handover
- Choice: a modified tracked charter passes `--respawn` with `--commit` only when the line names it (or a directory over it); before, `-c` took it by its sweep.
- decide, owner: none.

## Next act
- None on the branch: phase 2 is done at the commits. The landing (`gate land`, its `make check` the one check), the push and the install are the coordinator's.

## Exit
- Phase 2 at the commits: main 807013d merged (no code conflict), NICE n192 to n196, plugin 2.0.0-alpha.100 alone last under `plugin/`; nothing pushed, landed or installed, no gate job, no bare `make`. The sitting is closed.
- Review 1's fix at the commits: F1 built, four tests (red at 2a9fa14), the seven named test files 328 green under both venvs; no gate job, no version bump.
- Phase 1 at the commits: R1 to R5 built and the docs, the six named test files green under `.venv` and `.venv-floor`; no gate job, no version bump (the brief's amendments).
