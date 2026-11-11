# Packet n33: a helper's charter open never takes its sitting's record

| item | value |
|---|---|
| from | agentik-session `NICE_TO_HAVE.md` n33 (S1), S54's refuter F1 c11 (the coordinating repo's refutation record of 2026-11-09 and its doors probe); FW1b's A6; the coordinator's rulings of 2026-11-10 (forks a, b; the hook amendment) |
| pin | agentik-session main **after `r1-reconcile-lib` (a76ae35) lands**; its charter and hook code equal a76ae35's. Version: plugin 2.0.0-alpha.61, or the next free, read up by one for each bump landed before it. Worktree `.claude/worktrees/n33-helper-door`, branch `n33-helper-door`, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live state or writes under the live home; no relay verb |
| may touch | `plugin/lib/claude_session/{charter,cli,hooks}.py`; `tests/test_n33.py` (new); `.hygiene-allow`; `plugin/skills/session/SKILL.md`; `RUNBOOK.md`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/{source.md,rendered.sha256}` (status line); this packet as `design/packets/n33-helper-door.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash; its exit is the job's |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_n33.py`: 23 green (pin: `16 failed, 7 passed`), and under `.venv-floor`; `test_fw1a.py`, `test_s54.py`, `test_charter.py`, `test_hook_meter.py`, `test_hooks.py` unedited and green; verify green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 60 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

Observed 2026-11-10 from inside an Agent-tool helper (commands and outputs: the probes README):
- The helper's Bash environment carries the parent's `CLAUDE_CODE_SESSION_ID` and no mark of its own; `launch.py:237` lists the variables the harness puts on every tool subprocess, none per agent.
- (i) A helper's PreToolUse(Bash) payload carries `agent_id` in the installed 2.0.0-alpha.60: this helper's Bash calls stood open as `sessions/<parent's id>/calls/<tool_use_id>`, which `_open_call` writes only when `_call` (`hooks.py:149`, `:153`) finds `agent_id`; `design/research.md:29`; fixtures in `test_hooks.py`, `test_hook_meter.py`, `test_s49.py`.
- (ii) `plugin/hooks/hooks.json:7` registers PreToolUse with matcher `*`, so it sees Bash; `pre_tool_use` (`hooks.py:181`) returns its deny at `:196` to `:205` (`hookSpecificOutput` with `permissionDecision: deny` and a reason, plus `systemMessage`). No new registration. A denied call gets no PostToolUse; `post_tool_batch` (`hooks.py:669`) closes it.
- c11 at a76ae35: `the record: {"path": "<tmp>/c11/history/sittings/2026-11-10-2.md"}`, `exit lines: A 0  B 1`. The helper's open: `cli.py:405` writes `-2.md`, `_record_charter` (`:815`) passes its tests and overwrites `charter.json` at `:837`. The parent's bare close: `_recorded_charter` (`:844`), `charter.bare_target` returns `-2.md` at `charter.py:322`, `charter.close` writes at `:439`.
- A respawned sitting holds no record (`agentik session run` starts each under a fresh `--session-id`, `chain.py:414`), so without the hook a helper's open there takes the record; no legitimate second open under one id was found (README).

## 2. Rulings

- R6, the root door (hooks on). `pre_tool_use`, first after the stamp: a payload with `agent_id`, `tool_name` Bash, whose command matches `HELPER_CHARTER`, is denied in `:196`'s shape whatever the posture, and opens no call.
  The pattern: a launcher name (`agentik-session`, `agentik session`, `claude-session`, `claude_session`, so a path to `bin/agentik-session` and `-m claude_session` too), `charter`, flags, `open` or `close`.
  The reason: write the charter by hand, check it with `agentik-session charter check <file>`, put a probe's own call in a script file. A main-thread payload, a helper's `charter check` and every other verb pass.
- The mention edge, pinned by T14: the words with no launcher name pass (`grep -n "charter open" SKILL.md`); with one (`grep "agentik-session charter open" x.md`) the call is denied. A plain pattern cannot tell a quoted mention from the call; a false deny costs one reworded command, a miss the sitting's record.
- R1, the fallback (hooks off). `charter open` (and `--continue` when it would not adopt the recorded file) refuses, exit 2, before any write, when it would write the record (`_record_charter`'s tests as `_records_here(d, section)`) and the record names an absolute file under the same directory that is still open (no `- exit taken: ` line: `charter.still_open`, `charter.held`).
  The line names the file, `charter close`, a worktree and `--replace`. A gone, closed or outside record holds nothing.
- R2. `charter open --replace` moves the record as `{"path": <new>, "replaced": <old>}`; with nothing held, `{"path"}`. On check or close: `charter --replace is read only with open, not <action>`, exit 2.
- R3. A bare close whose record wins refuses, exit 2, while `replaced` names a still-open file there: `... opened with --replace while <replaced> stood open, and it still does; name the file: charter close <file>`, raised outside `bare_target`'s `try` (`CharterError` is a `ValueError`).
- R4, unchanged: R11's refusals, S33's `{"path"}`, `CLAUDE_SESSION_HELPER`'s skip, `adoptable`, the record written at open time, the spawn gate. No config key or hook registration.
- R5. SKILL.md, one line for `open --replace`; RUNBOOK §4, one bullet (the deny, the fallback, the flag); `.hygiene-allow`, `tests/test_n33.py: renamed` (the alias). No README line: `source.md` is 16,381 of `test_readme.py:25`'s 16,384 bytes. Last: the version, the status line (2,651 tests), the sidecar.

`tests/test_n33.py` (probes): red at a76ae35, green on `prototype.patch`, 3.12.7 and 3.9.6:

| T | the test shows | item | red at the pin |
|---|---|---|---|
| 1 | c11 through `python -m claude_session`: the helper's open exit 2, the close writes A | R1 | exit 0 |
| 2 | the refusal writes nothing, names `--replace` | R1 | exit 0 |
| 3 | `--continue` adopts the recorded file; at the mark, refuses | R1 | exit 0 |
| 4, 7 | `--replace`: `{path, replaced}`; over nothing, `{path}` | R2 | unrecognized `--replace` |
| 5, 6 | the bare close after a replace refuses; once closed or gone, the record wins | R3 | as T4 |
| 8 | `--replace` on close and check | R2 | argparse's line |
| 9, 10 | close then open, a worktree, a marked helper, a successor; gone or outside records | R4 | green |
| 11 | SKILL.md and RUNBOOK | R5 | no line |
| 12 | five names, open and close, flags, chains: denied, no call open | R6 | no deny |
| 13 | five names: the main thread, `check`, `status`, Read pass | R6 | green |
| 14 | the mention edge | R6 | no deny |
| 15 | `python -m claude_session hook PreToolUse`: helper denied, main passes | R6 | no deny |

## 3. Interfaces

New: `hooks.HELPER_CHARTER`, `HELPER_CHARTER_DENY`, `_helper_charter`; `charter.still_open`, `charter.held`, `bare_target(..., replaced=None)`; `cli._records_here`, `_record_charter(..., replaced=None)`, `_recorded_charter(key="path")`; `charter open --replace`. Unchanged: R11's, S33's and design/05 §6's exits and messages.

## 4. Findings that name this row

agentik-session keeps no ledger of its own: no own entry to carry. Bearing, uncrossed: the coordinating repo's entry 6, "at a runtime floor of Python 3.9 on the standard library alone"; the coordinating repo's entry 17, a flag takes a packet; the machine ledger's 20, two review rounds at most. NICE: n33 closes; n38 stands (the same deny would hold `set fill`).
New, S4, `claude_session/cli.py`: with hooks off and no record of the session in that directory (or its charter closed), a helper's open still takes the record and the sitting's later bare close writes it; lead: the record confirmed by a main-thread PostToolUse, as `_confirm` (`hooks.py:600`) does a respawn.

Forks: none open; (a) and (b) ruled 2026-11-10.

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T15 under both pythons; choices in a ruling; leftovers.
