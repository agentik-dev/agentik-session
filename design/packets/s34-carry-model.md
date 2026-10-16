# Packet S34: a respawn keeps the model the sitting ended on, and says so; the band names `/model` at a rate limit

| item | value |
|---|---|
| from | OPEN-QUESTIONS 7, answered 2026-10-16 10:58 by the owner: "yes it should keep the model I switched to but we should warn about it"; `design/respawn-r1.md` §3 (each start, the restart's ledger entry); `design/mod-r1.md` (the band) |
| pin | `main` at this packet's commit; branch `s34-carry-model`, worktree `.claude/worktrees/s34-carry-model` |
| wall | this repo; no push, `--amend`, rebase, merge, device, network, real `claude` session, `agentik session run`, `claude plugin install` or `update`, `make readme`, `make install` or `make check`; `claude plugin test plugin` is allowed; never write in the account's state directory (the plugin's, under `~/.local/state`); no `agentik-session` verb that writes; never run `relay` or `agentik relay` with any verb; never build or run a relay binary; never `pkill -f` |
| may touch | `claude_session/chain.py`, `claude_session/hooks.py` (a `stop_failure` handler and its dispatch), `claude_session/mod.py` (the band's Python twin), `claude_session/cli.py` (only the `hook` verb's event list, if StopFailure needs it), `plugin/hooks/hooks.json`, `plugin/hooks/run`, `plugin/hooks/session.ts`, `plugin/hooks/session.test.ts`, `tests/test_chain.py`, `tests/test_hook_meter.py` or a new `tests/test_s34.py`, `design/respawn-r1.md` (§3's "byte for byte" sentence and the ledger entry's fields only), `NICE_TO_HAVE.md`, this packet, `history/sittings/2026-10-16-1-s34.md`; (fix round) RESTART_KEYS, HOOK_EVENTS, their test pins, RUNBOOK step 2 |
| acceptance | 1: `.venv/bin/python -B -m pytest tests -q -k s34 2>&1 \| tail -1` reads `passed`, no `failed` (pin: the s34 tests fail); 2: `.venv/bin/python -B -m pytest tests -q -k "chain or respawn or hook or mod or band" 2>&1 \| tail -1` reads `passed`, no `failed`; 3: `make lint doclint 2>&1 \| tail -2` exits 0 |
| verify | `make check` (it runs the mod's tests), by the coordinator, after this branch |
| budget | acts: 1 the carried model (tests red, then green); 2 StopFailure and the band line (tests red, then green); 3 respawn-r1 and NICE. 45 turns, stop at 36 (commit the act in flight), 150k; one commit per act |

## 1. What the source says

A launcher-run chain was started with `--model fable`. Its sitting met the Fable limit, the owner typed `/model` to an Opus model, and the sitting worked on. At RESPAWN the launcher replayed the start line, so the successor opened on Fable, met the same limit and sat idle until the owner typed `/model` again (twice on 2026-10-16). Nothing told the owner: the band shows only the usage windows.

What the state already holds: `<state>/sessions/<sid>/meter.json` carries `model`, the last real `message.model` the meter read (a `<synthetic>` line, which is what a limit message is, never replaces it; `meter.py` `_known`). On the switched sitting above it reads `claude-opus-5-5`. The transcript strips Claude Code's `[1m]` marker, so the meter cannot tell Opus at 1M from Opus at 200k (`models.py`'s header). The launcher reads no transcript (`chain.py`'s docstring) and keeps that rule: it reads `meter.json`, a state file.

Claude Code 2.1.301 has a `StopFailure` hook: "Fires instead of Stop when an API error (rate limit, auth failure, etc.) ended the turn. Fire-and-forget: hook output and exit codes are ignored." Its matcher field is `error` (`rate_limit`, `overloaded`, `authentication_failed`, `billing_error`, …). The plugin registers no StopFailure today, so a limit-ended turn writes no `turn-ended.json` (seen live).

## 2. Rulings

1. **The carried model.** At a restart, the launcher reads `<state>/sessions/<the ending sid>/meter.json`'s `model`. The start line's model is the value of the last `--model X` or `--model=X` in the owner's arguments. When the start line has no `--model`, when `meter.json` is absent, unreadable or has no `model`, or when the read model names a family the models table does not know, the successor's arguments are the start line's, byte for byte, as today. When the read model names the same family as the start line's model, the same. Otherwise the successor runs with that one value replaced, in its own position and form (`--model X` stays two tokens, `--model=X` one); every other argument stays byte for byte.
2. **The marker.** The carried value is the read model, plus `[1m]` when the start line's model has a window of 1M or more in the models table (marked, or a family with one 1M window, as fable) and the table has a `<family>-1m` entry for the read model's family. A chain started on a 1M window keeps a 1M window. Otherwise the read model is carried bare. The table is the one the resolver builds (shipped plus the user's `models:`); the launcher resolves it as the guards do, and a resolve failure carries nothing.
3. **Each restart compares with the start line.** `self.args` is never rewritten. A successor that did not switch reads the carried model in its own `meter.json`, so the carry holds by itself. A sitting switched back to the start line's family returns the chain to the start line.
4. **The warning.** Before it spawns a successor on a carried model, the launcher says one line: `<chain>: the successor runs on --model <carried>, the model the sitting ended on; the start line says --model <start>`. The restart's ledger entry gains `"model": <carried or null>` and `"start_model": <start or null>`. A restart that carries nothing says nothing new.
5. **StopFailure.** `plugin/hooks/hooks.json` registers `StopFailure` and `plugin/hooks/run` treats it as `Stop` (stdout dropped, exit 0). `hooks.stop_failure` writes `<session dir>/limited.json` {`at` (epoch seconds), `error` (the payload's `error`, a string capped at 64 characters, else null)} for the main thread only (a helper's, as `stop` decides, writes nothing), and never raises. It writes no `turn-ended.json`: the launcher's RESPAWN logic reads that file and must not see a turn end that did not happen.
6. **The band line.** When `limited.json`'s `error` is `rate_limit` and its `at` is later than `turn-ended.json`'s `at` (or there is no `turn-ended.json`), the band's session line says `limit: the model's limit ended the last turn; /model to switch`, in place of the zone word or beside it, as fits the band's width rule. The next good turn's `turn-ended.json` clears it by being later. `session.ts` `bandLine` and its Python twin say the same, and the shared fixture in `session.test.ts` pins both. If the mod draws no band after a StopFailure, say so in the report: the line then shows at the next draw, and that is accepted.
7. **The design text.** respawn-r1 §3's "byte for byte, every time" gains: "except `--model`, which follows the model the sitting ended on (OPEN-QUESTIONS 7, 2026-10-16; packet S34)", and the restart entry's field list gains `model` and `start_model`. `chain.py`'s docstring says the same in one clause.
8. **Tests** (each name holding `s34`): (a) a start line `--model fable` and a `meter.json` reading `claude-opus-5-5`: the spawned argv holds `--model claude-opus-5-5[1m]` in fable's position, the line of ruling 4 is said, and the ledger entry holds both fields; (b) the same with `--model=fable`: one token `--model=claude-opus-5-5[1m]`; (c) a start line `--model 'opus[1m]'` and `meter.json` reading `claude-opus-5-5`: argv unchanged, nothing said; (d) a start line `--model sonnet` (200k) and `meter.json` reading `claude-opus-5-5`: `--model claude-opus-5-5`, bare; (e) no `--model`, no `meter.json`, a `model` of `<synthetic>` or an unknown family: argv unchanged; (f) two restarts in a row: the second compares with the start line, not the first carry; (g) `stop_failure` with `error: rate_limit` writes `limited.json` and no `turn-ended.json`; a helper's writes nothing; a malformed payload raises nothing; (h) the band line: limited later than turn-ended shows the line; earlier, or another error, does not (Python and TypeScript, one fixture).

## 3. Interfaces

One new session-dir file, `limited.json` {at, error}, written only by the StopFailure hook and read only by the band. Two new fields in the restart ledger entry. One new hook registration. The successor's `--model` may differ from the start line's. Say in the charter's handover whether the repo's conventions move the version for these, and do not bump it in this branch.

## 4. Findings that name this row

OPEN-QUESTIONS 7 (answered); NICE_TO_HAVE's entry "a chain's sitting stalls on its model's limit": mark it answered by S34 in act 3. The portfolio ledger's entry 17 ("the same start line") is amended in its own repo, not here.

## 5. Forbidden reads

Transcripts; `~/.claude/projects`; the account's state directories (the session plugin's and the relay's). Read no other repo. Claude Code's binary may be read with `strings` and `grep` for the StopFailure payload and the mod API, never run as a session.

## 6. Report (capped)

At most 150 words: each acceptance line's tail; the s34 tests red on the pin; the warning line as said in test (a); whether the mod draws after a StopFailure, with the evidence; any ruling beyond §2; the head sha.
