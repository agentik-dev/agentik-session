# Packet h5: the family rule reads the model an agent type names

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief h5 (NICE n58; packet wfg §4's lead); agentik-hq entries 2 and 20 |
| pin | `8a4b593` on main (mt1 landed, 2.0.0-alpha.93). Worktree `.claude/worktrees/h5-type-model`, branch `h5-type-model`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `_load_json` untouched |
| may touch | `plugin/lib/claude_session/hooks.py` (`_spawn_rule`, `_agent_model`); `tests/test_h5_type_model.py` (new); `RUNBOOK.md` (the role check's paragraph); `NICE_TO_HAVE.md` (n58 leaves); this packet and the sitting's record. Phase 2: `plugin/.claude-plugin/plugin.json` |
| verify | phase 1: pytest under `.venv` and `.venv-floor` on the new file, `tests/test_wfg.py`, `tests/test_mt1_tiers.py`; phase 2, on the coordinator's word: the version and the gate queue's `make check`, once, last |
| acceptance | §3; `tests/test_wfg.py` and `tests/test_mt1_tiers.py` unedited and green |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. The owner's words

- Entry 2: "The plugin checks each spawn: a helper never runs above its parent's model family, refused in every posture; the role check warns under signal and refuses under deny."
- Entry 20: "each call naming its model or using an agent type whose definition names one, so the spawn rule and the spend mix see every helper."

## 2. Rulings (brief h5)

- R1 `_spawn_rule`: a call whose `model` is not a non-empty string is judged on `_agent_model`'s; a Fable family under a session that is not Fable, or unknown, is denied in every posture. A call naming its model is judged on that alone (the call outranks the file).
- R2 `_agent_model`: `subagent_type` `<plugin>:<name>`, each part `[A-Za-z0-9._-]{1,64}`, reads `plugins/installed_plugins.json` under the config folder (`CLAUDE_CONFIG_DIR`, else `~/.claude`); for each key `<plugin>@<marketplace>` and each install record with a string `installPath`, the `model:` of `<installPath>/agents/<name>.md` by the same frontmatter read. The model whose family ranks highest in `tiers.ORDER` wins, one naming no family last; None when none. A bad record or an unreadable file gives None, never raises. A name with no colon: the project's file, then the user's, as at the pin.
- R3 the line, when the model came from the type's file: `agentik-session: a Fable helper starts only under a Fable session: this one runs <family>, and agent type <type> names <model>. Name model: 'opus' on the call.` (type and model through `_token`; the unknown-session words in the family's place). A call naming its model keeps today's line.
- R4 the role check calls `_agent_model`, so a plugin type's model meets the role's with no code of its own.
- Settled: no file, no frontmatter, no `model:`, `inherit` or another family passes; a built-in type and no `subagent_type` pass; `CLAUDE_CODE_SUBAGENT_MODEL` is not read; nothing cached. An exception outside the reads still denies (T17).

## 3. Interfaces: the acceptance table (baseline measured at `8a4b593`)

Each under an Opus session unless the line says otherwise; tests in `tests/test_h5_type_model.py`.

| # | line | at the pin |
|---|---|---|
| 1 | no `model`, project type `designer` with `model: fable`: deny, R3's line | `{}` |
| 2 | the user's file alone (`sketcher`, `claude-fable-5-2`): deny | `{}` |
| 3 | `plug:drafter`, one install naming fable: deny; two installs, opus and fable, either order: deny | `{}`, `_agent_model` None |
| 4 | 1 to 3 under a Fable session: `{}` | `{}` |
| 5 | `model: opus` on the call, the file naming fable: `{}` in every posture | `{}` |
| 6 | opus, sonnet, `inherit`, no `model:`, no frontmatter; built-in type; no type; a record not JSON, a list, a gone `installPath`: `{}`, no exception | `{}` |
| 7 | a helper's call (`agent_id`) with `designer`: deny, the unknown-session words | `{}` |
| 8 | under `deny`, words tier sonnet, `tier: words`, a plugin type naming opus: refused; under `signal`: warned | no line |
| 9 | `tests/test_wfg.py`, `tests/test_mt1_tiers.py` unedited, green | 102 passed (`.venv` 3.12.7, `.venv-floor` 3.9.6) |

At the pin the new file: 9 failed, 25 passed (lines 4, 5, 6 already hold).

## 4. Findings that name this row

- Fork for the owner (not built): entry 2 reads "a helper never runs above its parent's model family", and the rule refuses Fable alone; at the pin and here a Sonnet session starts an Opus helper (`{}`). Recommended: refuse every family above the session's, in a row of its own, an unknown session still denying Fable only.
- NICE n58 leaves with this row.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job (none in phase 1), the choices made, what was not done.
