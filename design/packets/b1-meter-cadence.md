# Packet b1: the meter speaks on a schedule, not on every prompt

| item | value |
|---|---|
| from | the owner, 2026-11-11, on the management repo's prompting-guide audit of that day (findings B1 to B4 and C3): "Please clean all of this up. I do find the session percentages helpful but maybe we don't update them every turn, maybe every 30 minutes or every N messages?"; "figure out if we can do a scheduled update - I find it helpful to see if something is intentionally winding down"; on the two rules about a helper call's model, "Fix this up as well"; on effort, "set the defaults for these" |
| pin | main c81d898 (2.0.0-alpha.70). Worktree `.claude/worktrees/b1-meter-cadence`, branch `b1-meter-cadence`, the venvs linked from main. The version bump is the coordinator's: row `u2-loop-finish` owns `plugin.json` and the README status line |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no subagent or workflow; no test reads live state, the live process tree included; no relay verb; not `unattended.py`, `plugin.json`, `README.md`, `NICE_TO_HAVE.md`, any ledger |
| may touch | `plugin/lib/claude_session/{hooks,rules,charter,ledger,harness,cli}.py`, `profiles.yaml`; `plugin/skills/session/SKILL.md`, `RUNBOOK.md`; `design/overhaul-r1.md` (§2.2, D13), `design/window-r1.md` (R6, one line); `tests/test_b1.py` (new), `tests/conftest.py`, and the existing tests that pin a text this packet changes; this packet |
| verify | `agentik session gate run <worktree> -- /bin/sh -c 'make check > <log> 2>&1'`, then `gate wait <id> --strict` in one background Bash. `plugin-version-check` is red until the coordinator's bump; the same gate run with `PYTHON=/usr/bin/true` shows every other part |
| acceptance | `tests/test_b1.py` green under `.venv` and `.venv-floor` (pin: every case red); the neighbours (`test_hook_meter`, `test_hook_session_start`, `test_window`, `test_rules`, `test_ledger`, `test_wfd`, `test_wfg`, `test_charter`, `test_s49`, `test_hooks`, `test_resolver`: 708 green at the pin) green, edited only where they pin a replaced text; `git grep 'each naming its model' -- plugin RUNBOOK.md README.md` prints nothing (pin: 3 lines) |
| budget | a commit per ruling group by explicit path, this packet first. `claude-opus-5-5`, effort high |

## 1. What the source says at the pin

- `hooks.user_prompt_submit` adds `session: <c>% context, <t>% turns, zone <z>` to every prompt once `meter.json` exists, whatever the zone (D13's "one line per prompt").
- `hooks.session_start` tells the model `profile '<p>', ceilings 180000 context / 400 turns (<src>) on a 200000 window (<whence>), checkpoint at 80%`.
- `charter.open` writes `| budget | 400 turns, 180k context; charter current at 80% |`. `scripts/doclint` and `charter check` require a `budget` row, so the row stays.
- `_post_tool_use` is silent below `checkpoint_at`; `_checkpoint_out` writes the CHECKPOINT line.
- `WORKFLOW_DENY`, the Fable rule's tail and the skill say every Agent call names its model; the rule's code already passes a call with none.
- The ledger row has no effort; only `start` passes `--effort`.

## 2. Rulings

- **R1, the schedule.** A new key `session.pacing.meter_line_minutes`, an integer 0 to 1440, default 30. In the clear zone the percent line is shown at most once every that many minutes: the first prompt, or the first main-thread PostToolUse, at least that long after the line was last shown carries it, once. A session's first prompt with a meter carries it. `0`: the line on every prompt and never on a tool call, as at the pin. From the checkpoint zone (`notice` on) the prompt line is on every prompt and PostToolUse is D13's, as at the pin. The stamp is `sessions/<sid>/meter-line.json` `{at, shown}`: a tool call that finds none writes `shown: false` and stays silent, which starts the clock without speaking; a prompt that finds `shown: false` shows the line. Posture `off` and a helper's payload say nothing, as at the pin. The key binds whatever `pacing.enabled` says.
- **R2, the wording.** `session meter: <c>% of context, <t>% of turns; the checkpoint comes at <k>%`, each percent a whole number rounded down; from the checkpoint on, `came at`. Nothing else.
- **R3, the start line.** `agentik-session: profile '<p>'; the meter shows this session's percent on its schedule and prints CHECKPOINT when it is time to bring the charter current and hand off; resolved config at <path>`, then the clauses as at the pin. No ceiling, window or turn cap. The band above the prompt is unchanged.
- **R4, the charter's budget row.** `| budget | profile <p>; the meter's CHECKPOINT line ends the sitting |`. Old charters are not rewritten.
- **R5, the wind-down is said.** The CHECKPOINT line ends `; tell the owner you are winding down at the meter's line, at <pct>%`, `<pct>` the used share. The line keeps its figures and its MAX_OUT bound; EXIT is unchanged.
- **R6, a helper call's model.** `WORKFLOW_DENY`: `... Spawn helpers with the Agent tool: name the model, or use an agent type whose definition names its own. Do not call Workflow again.` The Fable rule's tail: `Name model: 'opus', or use an agent type that names its own model.` The skill and RUNBOOK say the same.
- **R7, effort in the ledger.** `LEDGER_KEYS` gains `effort` and `effort_from`, last. At SessionEnd: the nearest `claude` ancestor's `--effort` (`flag`); else `modelSettings[<model>].effortLevel` in the local, project, then user settings, else their top-level `effortLevel` (`settings`); else both null. A value outside `low medium high xhigh max` is no value. `report --json` prints each row as written (S49), so every row written from here on carries both keys; an older row is not rewritten.
- **R8.** `overhaul-r1.md` §2.2 and D13 amended to the schedule, the owner's words and the date quoted; `window-r1.md` R6 gets one line saying R3 took the window out of the start line.

## 3. Interfaces: the tests, `tests/test_b1.py`

| # | case | expect |
|---|---|---|
| T1 | first prompt with a meter at 46% | the R2 line |
| T2 | a prompt 10 minutes later | no meter line |
| T3 | a prompt, or a tool call, 30 minutes later; then one more | the line once, then none |
| T4 | `meter_line_minutes: 0`, three prompts; a tool call 2 h on | the line on each prompt; the tool call silent |
| T5 | at 80% and past | the line on every prompt, the zone line after it; CHECKPOINT as D13 |
| T6 | the start line, under `CLAUDE_SESSION_MAX_TURNS` too | no digit run of 3 or more but the path's, no `window`, no `ceilings`; the R3 clause |
| T7 | a new charter's budget row | no digit |
| T8 | the CHECKPOINT line, on and off a launcher | holds the R5 clause, within MAX_OUT |
| T9 | `plugin/`, RUNBOOK, README | no `each naming its model`; the R6 lines exactly |
| T10 | the ledger row: `--effort high` on the claude ancestor; settings by model; top-level only; none | `(high, flag)`, `(x, settings)`, `(y, settings)`, `(None, None)` |
| T11 | `report --json` over an old row and a new one | the new row carries both keys; the old row as written |
| T12 | the key's bounds | -1, 1441, `true` refused; default 30 |

## 4. Findings that name this row: forks, and what is left

None expected. Left for later rows: the CHECKPOINT line's absolute figures (R5 keeps them), the charter's `window` row, and the skill's budget section, which states the ceilings in prose.

## 5. Forbidden reads

No transcript, no live state root, no live process tree in a test (conftest stubs the reader), no file under `~/.claude`.

## 6. Report

The hand-back of the management repo's common brief of 2026-11-11: the outcome first, the branch and head, the gate's line, the acceptance table at the pin and now, the choices, what is left, and any sentence a record outside this repo needs.
