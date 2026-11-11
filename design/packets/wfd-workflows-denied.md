# Packet wfd: no workflows, the Workflow tool denied outright

| item | value |
|---|---|
| from | the owner, 2026-11-10 at about 14:57, on seeing the guard refuse a one-agent script with "add model: 'opus' ... Fix the script and call Workflow again": "Fix that workflow hook bug. we shouldn't even be using workflows" |
| pin | the head of `r2-reconcile-verb` after its merge of main and n33 (2.0.0-alpha.67); the coordinator gives the sha. Version 2.0.0-alpha.68. Worktree `.claude/worktrees/wfd-workflows-denied`, its branch the same name, cut from that sha, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; never the Workflow tool; no test reads live state; no relay verb |
| may touch | `plugin/lib/claude_session/{workflowguard,hooks}.py`; `tests/test_wfd.py` (new), `tests/test_wfg.py`, `tests/fixtures/wfg/*`; `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `README.md`, `design/readme/*`; `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`; `design/packets/wfd-workflows-denied.md` (this packet, committed first); `history/sittings/*.md` |
| verify | the landing's own `make check`, queued by the coordinator; the builder runs the files of §3 (its tests and What changes) under both pythons with pytest directly, the lints alone, and the whole `tests/` once at 3.12 in the background |
| acceptance | `tests/test_wfd.py` green under `.venv` and `.venv-floor` (red at the pin); the Fable rule's tests unedited and green; `git grep -nE 'skeleton|deny_line|MAX_AGENTS|_script_of|Fix the script' -- plugin tests` prints nothing |
| budget | a commit per group by explicit path, the packet first; stop at 60 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says: the code today

- `hooks._spawn_rule` reads a Workflow call's script (`_script_of`: `script` inline, else the file at `scriptPath`) and passes it to `workflowguard.check`. A script whose agents each name a model and number eight or fewer is allowed.
- A refused script gets `workflowguard.deny_line`: `Workflow denied before launch: <reasons>. Fix the script and call Workflow again.` The line teaches the caller to make a workflow that passes. Seen live on 2026-11-10: `line 6: every agent( names its model in its own options: add model: 'opus'`.
- The skill gives the script rules about 30 lines (`**The spawn rule** (packet wfg)` to the section's end).
- `workflowguard.family` also serves the Fable rule on Agent and Task, and the helper-family count near `seen.add(`.

## 2. Rulings: the requirements

- **R1.** PreToolUse on `Workflow` denies every call, under every posture and from a helper too, with one line and nothing else: `agentik-session: Workflow denied: this suite runs no workflows. Spawn helpers with the Agent tool, each naming its model; do not call Workflow again.`
- **R2.** The rule reads nothing of the call: not `script`, not the file at `scriptPath`, not a saved workflow's `name`. A `tool_input` that is absent or not a mapping denies the same. Nothing in the rule can raise, so it cannot fail open.
- **R3.** The Fable rule on Agent and Task is unchanged: a Fable helper starts only under a Fable session, and an unknown session model denies.
- **R4.** What nothing reaches goes. In `workflowguard.py` only `family` and `FAMILIES` stay. In `hooks.py`, `_script_of` and any import that served it alone go. The script checker's tests and `tests/fixtures/wfg/*` go, except a fixture `test_wfd.py` reuses.
- **R5.** The skill's spawn rule shrinks to at most six lines holding the two rules (no workflows; a Fable helper only under a Fable session). `RUNBOOK.md` and `README.md` lines that describe the script rules follow, with the README's source and sidecar.
- **R6.** `NICE_TO_HAVE.md`: each open line about the script checker is closed with the repo's closed marker, citing this packet. The report lists them.

## 3. Interfaces: the tests, `tests/test_wfd.py`

| # | case | expect |
|---|---|---|
| T1 | a script whose every agent names `model: 'opus'`, two agents (allowed at the pin) | deny, the R1 line exactly |
| T2 | `scriptPath` naming a missing file, a directory, a FIFO, a 1 MB file | deny, the same line; the FIFO case returns inside 2 s, so the file is never opened |
| T3 | only `name`; an empty `tool_input`; `tool_input` a list, a string, null | deny, the same line |
| T4 | each posture (`off`, `signal`, `ask`, `deny`); a payload carrying `agent_id` | deny, the same line |
| T5 | the line | one line, under 200 bytes, names the Agent tool, holds neither `Fix the script` nor `before launch` |
| T6 | Agent with `model: 'opus'`; Agent with no model; Task | pass, as at the pin |
| T7 | Agent on Fable under an Opus session, and under an unknown model | deny, the lines as at the pin |
| T8 | a 256 KB `script` | the handler's CPU within 20 ms of an Agent call's |

### What changes

`hooks._spawn_rule`'s Workflow branch returns the R1 line first and unconditionally. `test_wfg.py` keeps its Fable-rule and `family` tests and loses the rest. Run beside it: `tests/test_hooks.py`, `test_doctor.py`, `test_precompact.py`, `test_mod.py`, `test_s49.py`, `test_n33.py`.

## 4. Findings that name this row: ledger, NICE, forks

- The session repo has no ledger. The management repo's entries 6 (the plugin repos' build conventions) and 17 (a small change takes no packet; this one removes more than 50 lines, so it takes this packet) bind it.
- Closed by this packet, never built: the spend mix's count of workflow agents, and a live cut of a running workflow.
- No fork is expected. If the Fable rule's tests need a removed name, keep that name and say so in the report.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`.

## 6. Report

At most twelve lines: the head sha; red at the pin and green after, per python; the lines removed and added (`git diff --shortstat`); the R1 line as built; the NICE lines closed; the neighbours' counts; the whole run's last line; the range scan; anything not done.
