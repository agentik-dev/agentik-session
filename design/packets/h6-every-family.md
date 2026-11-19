# Packet h6: the spawn gate refuses every family above the session's

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-19, brief h6-every-family (hq HANDOFF 67; the fork packet h5 §4 named); agentik-hq entry 2 |
| pin | `c0bcb94` on main (sm5 landed, 2.0.0-alpha.140). Worktree `.claude/worktrees/h6-every-family`, branch `h6-every-family`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `workflowguard.family` and `tiers.family` untouched; no profile changed |
| may touch | `plugin/lib/claude_session/hooks.py` (`_spawn_rule`); `tests/test_h6_every_family.py` (new); `RUNBOOK.md` (the role check's paragraph); `NICE_TO_HAVE.md` (one row, D5's lead); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file, `tests/test_wfg.py`, `tests/test_h5_type_model.py`, `tests/test_b1.py`, `tests/test_mt1_tiers.py`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3; the four standing files unedited and green |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_spawn_rule` (hooks.py:451) returns None unless `workflowguard.family` of the helper's model (the call's `model`, else `_agent_model`'s) is `fable`; only then does it read `_session_family`.
- `_session_family` (hooks.py:427): the family where `model.json` and the meter's record agree, `other` for a model naming no family, None for a helper's payload, no record, or records that disagree.
- `tiers.ORDER` ranks fable, opus, sonnet, haiku, local, highest first.

The owner's words, 2026-11-12, to "Should the rule refuse every family above the session's?": **Every family**: "in a row of its own, a Sonnet session no longer starts an Opus helper, nor a Haiku session a Sonnet one; a session whose model is unknown still refuses Fable only."

Entry 2, in part: "The plugin checks each spawn: a helper never runs above its parent's model family, refused in every posture; the role check warns under signal and refuses under deny."

## 2. Rulings (brief h6)

- R1 the rule: for Agent and Task, with the session's family one of `tiers.ORDER`'s, refuse a helper whose family ranks above it; with it None or no family of the order, refuse a Fable helper alone. The helper's model as at the pin.
- R2 one reader: `workflowguard.family` for both, `tiers.ORDER` for the rank; no new reader. A helper's model naming no family passes.
- R3 the lines: the two Fable lines unchanged by a byte. Another family's refusal, a call naming its model: `agentik-session: a helper starts only at or below its session's family: this one runs <session>, and the call names <model>, family <family>. Name model: '<session>' on the call.`; a type naming it: `... and agent type <type> names <model>, family <family>. Name model: '<session>' on the call.` (type and model through `_token`).
- R4 where: in `_spawn_rule`, so every posture, a helper's call too, before the role check, no call file, a failure denies.
- R5 `tests/test_wfg.py`, `tests/test_h5_type_model.py`, `tests/test_b1.py`, `tests/test_mt1_tiers.py` unedited and green.
- R6 `RUNBOOK.md` says the rule as built; D5's lead (a helper's own spawn stays Fable only: its payload carries no model) is a NICE row.

## 3. Interfaces: the acceptance table (baseline measured at `c0bcb94`)

Tests in `tests/test_h6_every_family.py`.

| # | line | at the pin |
|---|---|---|
| 1 | the table, five sessions by four helpers and a helper's own spawn: sonnet/opus, haiku/opus, haiku/sonnet deny; every other cell as at the pin | the three cells pass |
| 2 | a type naming opus, no `model`, Sonnet session: refused in the type's form; `model: 'sonnet'` on the call passes; a plugin's type the same | passes |
| 3 | records disagreeing, a session model naming no family, no record: opus, sonnet, haiku pass, fable denied in the pin's words | holds |
| 4 | the three new cells' lines, both forms: one line under 900, `agentik-session: `, both families, `model: '<session>'`; a Fable line under Sonnet byte for byte the pin's | no line |
| 5 | under `off` and `signal` the three cells deny; a denied call leaves no `calls/` file | pass |
| 6 | a passing spawn meets the role check: `tier: build` above the role's warns under `signal`, denies under `deny` | holds |
| 7 | the standing four files | 211 passed (`.venv` 3.12.7, `.venv-floor`) |

## 4. Findings that name this row

- D5: a helper's own spawn stays Fable only, since its payload carries no model and its records are the session's; NICE n327.
- No shipped profile has a Sonnet or Haiku main model, so none is newly refused here.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
