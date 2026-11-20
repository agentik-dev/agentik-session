# Packet rc1: a RESPAWN close run in the background is refused, and an unconfirmed mark is said

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief rc1-respawn-confirm (a launched chain sat four hours on a mark no hook confirmed) |
| pin | `7db836d` on main (h6 landed, 2.0.0-alpha.142). Worktree `.claude/worktrees/rc1-respawn-confirm`, branch `rc1-respawn-confirm`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `chain.py` and `tests/test_chain.py` untouched; `_confirm`'s rule unchanged; `stop` never blocks |
| may touch | `plugin/lib/claude_session/hooks.py` (`pre_tool_use`, `user_prompt_submit`, `RESPAWN_TAIL`, `_confirm`'s predicate); `plugin/hooks/session.ts`, `plugin/hooks/session.test.ts`; `tests/test_rc1_respawn_confirm.py` (new); a test that pins a changed byte, that assertion alone; `plugin/skills/session/SKILL.md`, `plugin/commands/checkpoint.md`, `RUNBOOK.md`; `design/respawn-r1.md` §3.2, §3.3, change log; `NICE_TO_HAVE.md` (ten rows); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file, `tests/test_hooks.py`, `tests/test_hook_meter.py`, `tests/test_chain.py`, `tests/test_mod.py`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_confirm` (hooks.py:1497) writes `respawn-main.json` {at, marker_sha256} on a main-thread Bash call's PostToolUse when the command holds a `RESPAWN_CMDS` spelling and `--respawn`, and the marker was written at or after that call's PreToolUse stamp. A call run with `run_in_background` returns at once: its PostToolUse fires before the verb writes the marker, so nothing confirms it.
- The launcher (`chain.py`) goes on only when `respawn-main.json` parses and names the marker's bytes; it writes no hold for an unconfirmed marker.
- `pre_tool_use` has no rule on `run_in_background`; `user_prompt_submit` says nothing of the marker; the band reads `respawn marked` whenever `respawn.json` exists.

The owner's words, 2026-11-20: "Can you look into addressing this in agentik session so we avoid this from happening again? It means we missed out on some work for quite some time."

The stall, in made-up names: a launched sitting at its CHECKPOINT ran one background Bash call holding the check, the commit, the push and the close. The call returned in under a second, its PostToolUse found no marker, the verb wrote the marker five minutes later, and the band read `respawn marked` while the launcher polled for four hours.

## 2. Rulings (brief rc1)

- R1 refuse it: a Bash call with `tool_input.run_in_background` true whose command is a respawn close (one predicate, `_confirm`'s test) is denied at PreToolUse in every posture, a helper's too, after the stamp and before `_open_call`; one line under 900 characters opening `agentik-session: ` that says a foreground call alone confirms and names the remedy. The guard's own failure passes the call.
- R2 say it: at each main-thread prompt, every posture, while this session's marker names a chain and `respawn-main.json` names other bytes or none, one line opening `RESPAWN unconfirmed: ` with the close to run again in the foreground; the charter's path only where `_SAFE_PATH` takes it, else `<the charter>`. A fault says nothing.
- R3 show it: the band reads `respawn unconfirmed` for a chained marker whose confirm is absent, does not parse, or holds an `at` before the marker's `written`; else `respawn marked`.
- R4 teach it: `RESPAWN_TAIL` says "in a foreground call of its own"; the skill, the command and the runbook say a foreground call. The README is left (below).
- R5 the record: respawn-r1 §3.2 step 5, §3.3, a change log line.
- R6 what stands: `_confirm`'s rule, `stop`, `chain.py`, `tests/test_chain.py`.
- R7 ten NICE rows: five leads of the starter row's reviews, three findings of h6's review, this row's two leads.

## 3. Interfaces: the acceptance table (baseline measured at `7db836d`)

Tests in `tests/test_rc1_respawn_confirm.py` unless named.

| # | line | at the pin |
|---|---|---|
| 1 | the stall through the hooks: no `respawn-main.json`; the background PreToolUse is a deny | no confirm; the PreToolUse passes (`{}`) |
| 2 | three spellings, alone and at a chain's end, background: denied, one line, under `signal`, `off`, `deny`, a helper's too, no `calls/` file; the foreground passes; a background call without `--respawn` passes | the background passes |
| 3 | the line, every case of the brief; under `off` too; a second prompt | no line |
| 4 | the mend: a foreground close confirms, the next prompt is silent | no line to mend |
| 5 | the band, four cases, `plugin/hooks/session.test.ts` | `respawn marked` throughout |
| 6 | the tail holds `in a foreground call of its own`, at most `MAX_OUT`, a fall-back still a line | the pin's tail |
| 7 | `tests/test_chain.py` unedited and green; `chain.py` unchanged | holds |
| 8 | `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row

- The README's source is ten bytes under its cap and is rendered by a model run this wall forbids; its RESPAWN sentence is left as it is.
- Two leads to NICE: the launcher writes no `held.json` while a marker stands unconfirmed; a mark made while a main-thread background job is out is confirmed, and the launcher's signal ends the job.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
