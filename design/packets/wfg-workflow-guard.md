# Packet wfg: the Workflow guard, a spawn bounded before it starts

| item | value |
|---|---|
| from | the owner's ask of 2026-11-10 (a sitting ran three workflows at once; one run's record: 53 agents, all on Fable, 2.7M tokens) and the owner's rule of that morning, "do not spawn Fable agents from Opus orchestrator settings" |
| pin | agentik-session main **after n33 and u1 land** (both edit `pre_tool_use`); cut on 36c84ea, so lines are cited by quoted words. Version: the next free alpha. Worktree `.claude/worktrees/wfg-workflow-guard`, its branch the same name, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; never the Workflow tool; no test reads live state; no relay verb |
| may touch | `plugin/lib/claude_session/{workflowguard,hooks}.py` (workflowguard new); `plugin/hooks/{hooks.json,run}`; `tests/test_wfg.py`, `tests/fixtures/wfg/*.js` (new); `tests/{test_doctor,test_precompact,test_bare_machine}.py`, `scripts/bare-proof` (the event list alone); `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/*`; `design/packets/wfg-workflow-guard.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash; its exit is the job's |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_wfg.py`: 64 green (pin: `63 failed, 1 passed`), and under `.venv-floor`; `tests/test_hooks.py` unedited and green; `test_doctor.py` and `test_precompact.py` green with their event lists amended; verify green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 60 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says: the records and the code today

- The hook sees the call: the sitting's transcript holds `"hookName":"PreToolUse:Workflow"` with the call's `toolUseID` and `"stdout":"{}"`, a pass. The input is `script`, or on a resume `scriptPath`.
- A workflow's agents run their tools through the same hook: an agent's transcript holds `"hookName":"PreToolUse:Bash"`, and the plugin's `calls/<tool_use_id>` files (a payload with `agent_id` only) name those calls. No record shows a hook at an agent's start.
- An agent with no `model:` runs on the session's model: one run records `"defaultModel":"claude-fable-5-2"` and 53 agents on it, and its script never holds the word `model`.
- A hook may rewrite: "`updatedInput` ... Replaces the entire input object" (code.claude.com/docs/en/hooks). A timed-out hook "doesn't block the tool call" (same page).
- `pre_tool_use` acts on spawns only under `ask` or `deny` (`if cfg.posture in ("off", "signal"): return {}`), and `dispatch` turns a handler's exception into `{}`, a pass.
- The PreToolUse payload carries no model ("Only `SessionStart` hooks can receive a `model` field ... use a PostModelSwitch hook to follow the model", same page). After a `/model` switch to Opus, one session's `request.json` still reads `claude-fable-5-2` (SessionStart's, written once); `meter.json` reads `claude-opus-5-5`, the meter's last main-thread line.

## 2. Rulings: the requirements

- R1, the read. `workflowguard.measure(script, parent)` returns `(count, reasons)`; it never runs the script. One token scan blanks strings, template text, regexes and comments and keeps a template's `${}` as code; then a bracket tree and one upward walk per `agent(` call. It reads 64 calls and 256 KB at most and denies more.
- R2, a model per call. Each `agent(` call's last argument is an object literal holding `model: '<literal>'` of a known family. A spread (`...O`), a name, a helper's result or no options is denied.
- R3, the bound. A call counts once at the top level, in an `if` or a ternary (both arms count), and in a callback given directly to `parallel(`, `pipeline(`, `.map(`, `.flatMap(` or `.then(`. `.map(`, `.flatMap(` and `pipeline(` multiply by their list's length, known only for a top-level `const` array literal only ever read, an inline array literal, or `.slice(0, N)`. The sum is `MAX_AGENTS = 8` at most.
- R4, fail closed. Denied, each with its rewrite: a call in a loop; in a named function, a method or a named arrow; in another call's callback (`Array.from`, `forEach`, an IIFE); thunks kept in a name; a list from a result, `args`, a mutated or shadowed name, a spread; `agent` used other than as a direct call; `workflow(`, `eval(`, `Function(`, `import(`, `require(`, `globalThis`; unpaired brackets; the text `agent(` inside a string or comment. In the hook: a call with neither a `script` nor a regular `scriptPath` file (a saved workflow's `name` too), and any exception inside the rule. It bounds an honest script; it is no sandbox.
- R5, Fable in a script: under a Fable session only, labelled `design...` or `refut...`, two at most (fork Q2).
- R6, the owner's rule. An `Agent` or `Task` call whose `model` names Fable, and a script's Fable agent, are denied unless the session's model is Fable. The session's model is what its records agree on: `sessions/<sid>/model.json` (new: SessionStart's `model`, then each PostModelSwitch's `to_model`, never a helper's payload) and `meter.json`'s `model`. No record, two that disagree, or a helper's own spawn: not known, and a Fable spawn is denied with "retry after one tool call". Any other `Agent` call is untouched.
- R7, the hook. The rule runs for `SPAWNING_TOOLS` whatever the posture, a helper's call too, before `_open_call` (a denied call opens none), after n33's deny. hooks.json registers `PostModelSwitch` (timeout 5, no matcher); the shim treats it as `Stop`, and `SILENT` holds it.
- R8, the line. One line under 900 bytes, `agentik-session: Workflow denied before launch: lines 30, 31: <reason>: <rewrite>; ...`: three reasons at most, equal reasons folded with their lines.
- R9, docs. SKILL.md: the rules and each rewrite. RUNBOOK, one bullet: with the plugin off or its hook timed out nothing denies; the tool's own caps alone hold, 16 at once and 1000 a run. Last: the version, the status line, the sidecar.

Choices logged (reversible): deny, never rewrite through `updatedInput`; any session not on Fable, not Opus alone, is refused a Fable spawn; no off switch or profile key yet.

## 3. Interfaces: the tests, `tests/test_wfg.py` (probes)

Red at 36c84ea, green on `prototype.patch`, under 3.12.7 and 3.9.6. A 100 KB script costs 9.7 ms in process, +8.2 ms for the hook's process (bar: 50 ms).

| T | the test shows | item |
|---|---|---|
| 1 | three of the night's scripts, text replaced: each denied, lines and rewrite named | R2, R3 |
| 2 | six Opus agents, each model named: `(6, [])`, passes under any session model | R3 |
| 3 | eight pass, nine denied; eight shapes counted | R3 |
| 4 | 31 shapes with no bound, each denied; a regex and a nested template hide nothing | R4 |
| 5 | eight calls without a literal model; a full model id passes | R2 |
| 6 | Fable in a script: Opus session, unknown session, wrong label, three | R5 |
| 7 | an Opus session's Fable `Agent` denied, its Opus one allowed; Fable with Fable allowed; a switch each way; the model unknown; a helper | R6 |
| 8 | `scriptPath` read; a missing file, a link, a `name` denied; a raising guard denies | R4 |
| 9 | every posture; `Bash` and `Write` untouched | R7 |
| 10 | the event registered and silent; `model.json` written through the launcher | R7 |
| 11 | 100 KB under 50 ms; 64 calls in 250 KB under 0.5 s; 65 calls denied | R1 |

### What changes

The guard denies 31 of the 37 workflow scripts recorded on the cutting Mac, most for an unnamed model: R8's rewrites are acceptance.

## 4. Findings that name this row: ledger, NICE, forks

agentik-session keeps no ledger: no entry to carry. Bearing, uncrossed: agentik-hq 6, "Python 3.9 on the standard library alone"; agentik-hq 17 (a new hook event: a packet); agentik-hq 2, "A Fable designer with Opus helpers"; the machine ledger's 22, "Up to eight Opus helpers may serve a sitting".
NICE, new:
- S3 lead, `hooks.py`: an `Agent` call with no `model` whose agent type's own definition names Fable is not seen.

Forks, for the owner's batch:
- Q1, the ceiling: 8, or the tool's own 10. Recommended: 8, the machine ledger's number.
- Q2, Fable inside a workflow. Recommended: as R5; "never" is one constant.
- Q3, the spend mix over a workflow (part 3). Recommended: its own packet; `measure` gives it the count.
- Q4, a live cut (part 4), and several workflows at once (three scripts of eight are 24). Recommended: one later packet, in this hook, which an inner agent's every tool call passes with an `agent_id`; first probe whether that payload names its workflow.

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T11 under both pythons; cost; choices; leftovers.
