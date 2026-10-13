# Packet S20: `claude-session run`, the launcher (respawn-r1, part two)

| item | value |
|---|---|
| from | `record design/respawn-r1.md --section 5,7,8`, `--section 9-13` and `--section 14,16`; S19's packet §2; `NICE_TO_HAVE.md`'s respawn-r1 lines |
| pin | `main` once S19 (`s19-respawn-launcher`, 6d2beba) is merged, plus this packet's commit; worktrees `s20a-run` off main, `s20b-run` off S20a's merge |
| wall | this repo only. No push, `--amend`, rebase or device. Never run `relay`. Every python runs with `-B` or `PYTHONDONTWRITEBYTECODE=1`. No test starts a real `claude`; the one spend is `make readme`, once, in act 5 |
| may touch | `claude_session/chain.py` (new), `claude_session/cli.py`, `claude_session/launch.py`, `claude_session/hooks.py`, `claude_session/doctor.py`, `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `plugin/hooks/hooks.json`, `plugin/hooks/run`, `RUNBOOK.md`, `design/readme/source.md`, `README.md`, `design/readme/rendered.sha256`, `tests/fixtures/fake-claude` (new), `tests/conftest.py`, `tests/test_chain.py` (new), `tests/test_hooks.py`, `tests/test_launch.py`, `tests/test_doctor.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `history/sessions/NEXT`, `.venv` (the link) |
| acceptance | S20a: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_chain.py tests/test_hooks.py tests/test_launch.py -q -k s20a 2>&1 \| tail -1` reads `51 passed` or more (main: none ran). S20b: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_chain.py tests/test_doctor.py -q -k s20b 2>&1 \| tail -1` reads `8 passed` or more (S20a: none ran); `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_doctor.py -q 2>&1 \| tail -1` reads `passed` with no `failed` (S19: the same); `grep -c 'Status: version .v2.0.0-alpha.4.' README.md` reads 1 (main: 0); `grep -c 'claude-session run' RUNBOOK.md` reads 1 or more (main: 0) |
| verify | `make check` |
| budget | S20a: acts 0 to 3, 70 turns, stop at 60. S20b: acts 4 and 5, 50 turns, stop at 42. 180k context each; at the stop turn, commit the act in flight and stop; one commit per act; each charter opens with doclint's five rows |

## 1. What the source says

- §3.1: "Each start runs `claude --session-id <U> <claude args>`", the env "minus `exec_launch`'s scrub list … plus `CLAUDE_SESSION_CHAIN`".
- §3.3: ready "when `turn-ended.json` is newer than the marker, and no `activity.json` is newer than that turn end", standing `settle`; SIGKILL 30 s after SIGTERM.
- §3.4 to §3.7: checks (a) to (e), 10 s of grace, the printed start line, termios, SIGINT. §6: criteria 1, 2, 5 to 12, 14 to 16, 17's flags, 18's `--session-id`, 13's token.

## 2. Rulings (decided inside the design)

1. S19's signatures stand. Effects sit behind `chain.Effects`; `poll`, `grace`, `kill_grace` are `Chain` arguments (2, 10, 30), never flags. `guards` is the resolved `respawn` with the flags over it, resolved again before each restart.
2. **Ready** also needs `helper-activity.json` older than `settle` and no open helper call: a helper's PreToolUse whose `tool_use_id` matches `hooks._SID` opens `sessions/<U>/calls/<id>`; its PostToolUse or PostToolUseFailure removes it; any other id opens nothing. The main thread opens none. A call never closed holds the sitting (C6).
3. **The new hook (S20b).** `hooks.json` registers PostToolUseFailure (matcher `*`, timeout 5); `HOOK_EVENTS` follows. An older CLI exits 2 on an event it does not know, so the shim treats it as Stop; RUNBOOK: the CLI installs first.
4. **S19's doctor pins are S20b's to update**: the `machine` fixture's `hooks.json` and `--help` (plus PostToolUseFailure, `--session-id`), `test_hooks_json_is_the_shim_on_session_start_only`, `S19_EVENTS`, `test_s19_doctor_red_without_stop`'s positive control, and `HOOK_TIMEOUTS`.
5. A bare value that begins with `-` is refused, naming the `--flag=value` form, which passes.
6. A last positional `/loop` of 60 minutes or more warns once on stderr before the first start (its question waits); RUNBOOK names an interval under 60m, or none.
7. The cap is the larger of `ledger.restarts_in` and the launcher's 24 h tally; a `LedgerError` holds at `cap`; `at` is left to `append_chain`.
8. A signal N the launcher did not send exits 128+N. A bad `--cap`, `--floor` or `--settle` exits 2 naming `respawn.<key>`.
9. **Open, the owner's: the idle floor** (measured 0.50, coded 0.25). S20 leaves `BOUNDED_IDLE_FLOOR` (25%) as it is; the launcher's `floor` is the sitting's age.
10. **Tests.** `INHERITED` gains `CLAUDECODE` and `CLAUDE_CODE_SESSION_ID`. The fake `claude` (§6) runs `sys.executable -B -m claude_session hook <event>`, never PATH's `claude-session`; `_start_line_runs` puts a shim for it on PATH. The fake clock is anchored to the epoch; criterion 11's first case uses a cap of 3. The pty tests build `Chain` directly, small `poll` and `grace`.
11. **Docs (S20b).** RUNBOOK §1 step 2's hook list (every tool, Stop, PostToolUseFailure) and §4 (`run`, STOP files, rulings 3 and 6). `source.md` names `run`; version `2.0.0-alpha.4`; `make readme` once, last; on failure, commit the source; never hand-edit `README.md`.
12. **Acts.** S20a: 0 charter; 1 tests, red; 2 scrub, refusals; 3 loop, guards, ledger, `run`, open calls. S20b: 4 tests, red, terminal, hooks, shim, doctor; 5 docs.

## 3. Interfaces

`launch.scrub(env) -> dict`; `chain.ALLOWED`, `chain.FORBIDDEN`, `chain.refusal(args, env) -> str | None`, `chain.start_line(argv, env) -> str`, `chain.Chain(name, args, state, effects, guards, *, poll, grace, kill_grace).run() -> int`; `cli.cmd_run(args) -> int`; `hooks.post_tool_use_failure(payload, env=None) -> dict`.

## 4. Findings that name this row

Rulings 1 to 7 and 10 to 12 fold the NICE notes and the refuter's round. Cases:

- S20a (51), each `test_s20a` and: `_refusals` (11), `_forbidden_never_allowed` (1), `_same_args_every_start` (1), `_never_compacts_or_resumes` (1, criterion 15), `_restart` (1), `_no_marker_stops` (2), `_crash_never_restarts` (1), `_marker_bound_to_sitting` (3), `_waits_for_the_turn` (5, two for ruling 2), `_signals_after_settle` (1), `_guards_hold` (6), `_cap_fails_closed` (6), `_kill_after_grace` (1), `_ledger_holds_no_next_act` (1), `_start_line_runs` (1), `_flags_override_config` (3), `_long_loop_warns` (1); `_open_calls` (4, hooks); `_exec_launch_uses_scrub` (1, launch).
- S20b (8), each `test_s20b` and: `_terminal` (5, `pty.fork`); `_doctor_needs_session_id`, `_hooks_register_post_tool_use_failure`, `_shim_drops_post_tool_use_failure` (1 each, doctor).

## 5. Forbidden reads

Other repos; the live state root; transcripts; `design/respawn-r1.md` beyond `from`; packets but S19's; worktrees.

## 6. Report

At most 200 words: commits by act, the red run, each acceptance line's last line, `make readme`'s exit, notes filed, head sha. `make doclint`, `make lint` and `make hygiene` exit 0 before each commit.
