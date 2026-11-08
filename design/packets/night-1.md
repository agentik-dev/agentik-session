# Packet night-1: `agentik session night`, the loop without its land step

| item | value |
|---|---|
| from | agentik-hq HANDOFF 22, build 6; hq `design/07-night-loop.md` §2, §7, §8 item 1; hq entries 5, 6; relay entries 13, 15, 16; the Mac's ledger, entry 22 |
| pin | session main `bd105ab`, plugin 2.0.0-alpha.45; agentik-relay `dc5429e`, read only; worktree `.claude/worktrees/night-1`, branch `night-1`, off main |
| wall | this repo only. No push, merge, `--amend`, rebase, network or install; no `make` (the landing runs `make check` through the gate). Never build or run a relay binary; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never write inside `~/.local/state/agent-relay`. No real `claude`: tests use the fake. `.venv` is a symlink to the main checkout's |
| may touch | `plugin/lib/claude_session/night.py`, `plugin/lib/claude_session/cli.py`, `plugin/.claude-plugin/plugin.json`, `tests/test_night.py`, `tests/fixtures/night/claude`, `tests/fixtures/night/queue.yaml`, `tests/fixtures/night/green.jsonl`, `tests/fixtures/night/max-turns.jsonl`, `tests/fixtures/night/rate-limit.jsonl`, `tests/test_bare_machine.py` (its reader table), `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256` (the status line), `design/packets/night-1.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `.venv/bin/python -m pytest -q tests/test_night.py` passes with ruling 10's nine tests (on main: exit 4); `grep -c -F '"night"' plugin/lib/claude_session/cli.py` reads at least `1` (on main: `0`); `grep -c -F '2.0.0-alpha.46' plugin/.claude-plugin/plugin.json` reads `1` (on main: `0`) |
| budget | One Opus builder, 100 turns, 180k context, `claude-opus-5-5`; its charter opens with doclint's five rows; one commit per act, this packet first |
| verify | `make check` |

Read first, by sections: agentik-research `research/synthesis/tools-session.md` §2, §4; hq design/07 §2; `cli.py` `cmd_gate`; `tests/conftest.py`; agentik-relay `internal/effects/spawn.go`, `internal/stream/account.go:20-30`, `relay/queue.yaml`.

## 1. What the source says

hq design/07 §2 less night-2's part (§8 item 2: the land step, `--until`, `--max-rows`, the stop file, the `ps` refusal, `report`, the skill, the README section). With no gate call a row ends `built <sha>`, `red <reason>`, `skip`, `refused <reason>` or `limit`.

## 2. Rulings

0. This packet, committed first.
1. **Module.** `night.py`, stdlib, 3.9 floor (hq entry 6); each effect (clock, sleep, popen, killpg) in an `Fx` as `gate.py`'s. A night is `resolver.state_dir(env)/nights/<date>-<n>/` (n past today's highest), 0700 and 0600 as `gate.py`; its id `night-<date>-<n>`.
2. **Queue.** `yamlsubset` refuses the relay file's list of mappings and its two-line flow map, so `read_queue` joins an open flow map onto its next lines, cuts `rows:` at each `- `, and reads the head and each row (`- ` blanked) with `yamlsubset.load`, unchanged. Unreadable, or `version` not 1: exit 2. Honoured: `defaults` (`model`, `turns`, `context`, `usd`, `wall`, `merge`); a row's `id`, `packet`, `model`, `budget` (`turns`, `usd`, `context`, `wall`), `parked` (`skip parked`), `merge` (recorded only), `base` (unset or `main`, else `refused base`: nothing lands tonight), `depends_on` (any: `skip gate-failed-dependency`). Refused: `kind: orchestrator` (`kind`), `budget.context` over 180000 (`context`), a packet absolute, climbing out or missing (`packet`), an id outside `^[a-z0-9][a-z0-9._-]{0,63}$` (`id`). `verify` recorded. Ignored, a line each in `<night>/log` and stderr: `device`, `harness`, `prompt`, `sections`, `may_touch`, `measure_seconds`, `words`, any unknown key. `--rows a,b` keeps those ids; an unknown one exits 2.
3. **Admission.** `admission.admit(<night id>, {"subagentType": "night", "model": m}, env)`; `mode`, `text`, `peak` into `spawn`. An error is recorded and the row runs.
4. **Stage.** `git -C <repo> worktree add .claude/worktrees/<id> -b <id> <base>`; a tree there is reused only on branch `<id>` and clean, else `red stage`. Record `head_before`.
5. **Spawn.** In the worktree, own group: `claude -p --permission-mode auto --allowedTools "Bash Edit Write MultiEdit NotebookEdit" --model <m> --max-turns <t> --max-budget-usd <usd> --output-format stream-json --verbose --session-id <uuid4>` (relay `DefaultAllowedTools`). Stdin: `# The packet; the repo's CLAUDE.md carries the rules`, a blank line, the packet. Stderr to `<night>/<id>.stderr`. Env: `os.environ` less every `CLAUDE*` and `RELAY_*` but `RELAY_DEVICE_VERBS`; plus `CLAUDE_SESSION_PROFILE=builder`, `CLAUDE_SESSION_MAX_TURNS=<t>`, `CLAUDE_SESSION_MODEL=<m>`, `RELAY_MEASURE_DEPTH=1`; each `git remote` gets `remote.<r>.pushurl` empty then `relay-denies-push` through `GIT_CONFIG_COUNT`, after any count set (`PushDenyEnv`). Never `RELAY_ROW`, `CLAUDE_SESSION_DEPTH`, `RELAY_BIN`.
6. **Stream.** Each line goes to `<night>/<id>.jsonl` as it comes, then is parsed; non-JSON is skipped. A **limit**: a `rate_limit_event` whose `rate_limit_info.status` does not start `allowed` (kind `rateLimitType`, reset `resetsAt`, source `event`); or an `is_error` result, subtype not `error_max…`, whose text holds `api error: 429` or a usage needle of `account.go:25` (kind `unknown`, no reset, source `text`). `api error: 401` or an auth needle there stops the night `auth`. The last `result` gives ruling 10's `exit` keys and `session_id`. The loop never kills on a limit.
7. **End.** No `result` line, or a signal the loop did not send: stop `sitting-failure`. Else, in order: a limit (ruling 8); no commit past `head_before`, `red no-commit`; a dirty tree, untracked too, `red dirty-tree`; `is_error`, `red stream-error`; else `built <sha>`. A red row neither stops the night nor is retried.
8. **Limits.** `five_hour` or `session` with a reset: sleep to it plus 120 s; `unknown`: one 1,800 s wait (source `fallback`). Then once: `claude -p --resume <session_id>`, ruling 5's other flags but `--session-id`, turns and dollars the row's less the part's (at least 10 and 5), stdin "continue from your charter's act in flight; your commits stand", appended to the same stream, judged by ruling 7. A second limit or any other kind ends the row `limit`; a weekly one (`seven_day*`) or a second stops the night `usage-limit`.
9. **Watchdog.** Every `poll` s (30): HEAD, newest mtime outside `.git`, group CPU (`ps -A -o pgid=,time=`); all unchanged `stall` s (2,700): `gate._kill_group`, `red stalled`. The row's `wall` (default `4h`, `<n>h<n>m<n>s`): the same kill, `red wall`. `stall`, `poll`: `run()` arguments for tests, no flag. SIGTERM ends the night after the child's exit, stop `signal`.
10. **Ledger, status, tests.** `<night>/ledger.jsonl`, each line with `ts`, `kind`: `spawn` (row, part, model, turns, usd, session_id, argv, admission), `exit` (row, rc, subtype, is_error, num_turns, total_cost_usd, duration_ms), `row` (row, state, reason, sha, worktree; red or limit: `resume`, `cd <worktree> && claude --resume <session_id>`), `limit` (row, kind, resets_at, source, action), `stop` (reason, rows by state, cost). `night status [--json]` reads the newest ledger: rows by state, a running row's last stream line (200 chars) and age, the stop, else `no night yet`. Tests drive `night.run` with `tests/fixtures/night/claude` on PATH, replaying one fixture per start from `$FAKE_NIGHT_PLAN` (stream, no_result, commit, dirty, sleep) and logging argv, cwd, env, stdin to `$FAKE_NIGHT_LOG`; a temp repo with a bare `origin`; sleep and clock faked. The nine: `test_queue_read` (the relay's shape), `test_green_built`, `test_max_turns_no_commit`, `test_rate_limit_resumes_once` (a `limit` line), `test_orchestrator_refused`, `test_child_env` (`CLAUDE_SESSION_PROFILE=builder`, the pushurl, no `RELAY_ROW`), `test_watchdog_kills` (a sleeping fake, `stall` 1, under 10 s), `test_no_result_stops`, `test_status_newest`.
11. **Records.** Each `json.loads` in `night.py` joins `test_bare_machine.py`'s table: the stream's `NOT_STATE`, the ledger's `READERS`. Plugin 2.0.0-alpha.46, last; the README's and source's status line take it and the suite's count, `rendered.sha256` re-hashed (s51). doclint asks no README line per verb. Hygiene: no backticked bare `relay <verb>`.

### The stop

Stop, commit and report if a ruling needs `yamlsubset`, `gate.py` or `admission.py` changed, or a test of today's behaviour to change.

## 3. Interfaces

`agentik session night run <repo> [--rows a,b]`: exit 0 on stop `queue-spent`, 3 on another stop, 2 on a refusal before the first row. `agentik session night status [--json]`: exit 0.

## 4. Findings that name this row

hq NICE n3 (S4): a row's context ceiling is the profile's 180k, never `budget.context`; not built here. design/07 §9 risks 6, 7: the charter notes what the fake saw.

## 5. Forbidden reads

Transcripts; anything under `~/.local/state` or `~/.claude/projects`; any other repo but agentik-relay's paths above, read only.

## 6. Report

At most eight lines: branch and head; each act's commit; `tests/test_night.py`'s count; the suite's; the charter's choices; anything left over.
