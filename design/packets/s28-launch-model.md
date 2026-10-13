# Packet S28: a relay child's model, from the launcher's env

| item | value |
|---|---|
| from | the observer's check-in 102 (example-mac `history/observer/2026-10-12.md`, F14); `claude_session/models.py`'s source list; agent-relay's packet AR74 (its writer, `CLAUDE_SESSION_MODEL`); the portfolio ledger's entry 17 (a builder on a 1M window keeps 180k unless its repo's config says more) |
| pin | `main` at 9d78647 (alpha.13); worktree `.claude/worktrees/s28-launch-model`, branch `s28-launch-model` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, `claude-session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; no real model run (`claude plugin test` and `claude plugin validate` run none and are allowed); every python `-B`; stdlib only; tests use temporary state dirs, never the account's; never write `~/.claude*` or `~/.local/state` |
| may touch | `claude_session/hooks.py` (`session_start` only), `claude_session/resolver.py` (the `session_model` record only), `claude_session/models.py` (its docstring's source list only), `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `tests/test_launch_model.py` (new), `tests/test_doctor.py` (the version literal), `RUNBOOK.md`, `plugin/skills/session/SKILL.md` (a sentence each, if they list the env names), `NICE_TO_HAVE.md`, `history/sittings/*.md`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_launch_model.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (pin: no file); `.venv/bin/python -B -m pytest tests/test_models.py tests/test_hook_meter.py tests/test_hooks.py tests/test_resolver.py tests/test_doctor.py -q 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check`, after the coordinator's `make readme` |
| budget | acts: 0 charter; 1 tests, red; 2 the reader; 3 docs, version (2.0.0a14). 50 turns, stop at 40 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

`models.py`: "the session: the SessionStart payload's `model`: the session's main-loop model as Claude Code resolved `--model`, `/model`, the env and the settings, marker intact (`claude-opus-5-5[1m]`)"; "the transcript: `message.model` is the API model id; Claude Code strips the `[1m]` marker before the request, so a 1M Opus session reads `claude-opus-5-5`, like a 200k one". `pick` takes the session's, then the declared, then the configured models.

What happened (F14): every relay child of 2026-10-12 (8 sessions, profile `builder`) resolved `session_model: null`, `window_source: declared:opus`, window 200000, ceiling 180000. The relay spawns `claude -p … --model <row's model>`, and under `-p` the SessionStart payload carries no `model`. An example-app row ran `claude-opus-5-5[1m]` under example-app's `ceilings_1m: {context: 400000}`, and the hook called EXIT near 185k while the relay held it to 400k. agent-relay's AR74 adds `CLAUDE_SESSION_MODEL=<the spawn line's --model>` to the child's env, beside `CLAUDE_SESSION_PROFILE` and `CLAUDE_SESSION_MAX_TURNS`.

## 2. Rulings

The charter is `history/sittings/<the build date>-<n>-s28.md`. Each act's first test is red on the pin.

1. **The reader.** In `session_start`, when the payload has no string `model`, the session model is `CLAUDE_SESSION_MODEL` from the env, when it is a non-empty string; the payload's `model` always wins. Under `CLAUDE_SESSION_HELPER=1` the variable is ignored: a helper inherits its sitting's env but runs its own `claude -p` line, and its window is its own (a 200k helper must never meter at a 1M sitting's ceiling).
2. **The record.** `resolved.json`'s session section gains `session_model_source`: `payload`, `CLAUDE_SESSION_MODEL`, or null when there is no session model. `window_source` stays `session:<model>`; nothing else in `pick` changes.
3. **What follows.** A `-p` child with `CLAUDE_SESSION_MODEL=claude-opus-5-5[1m]` resolves window 1000000 and takes the 1M ceilings of its layers: example-app's config gives 400000; with no repo layer, the builder's own 1M ceiling stands (entry 17). The meter's later picks, which read the transcript's unmarked `claude-opus-5-5`, find the session model's family first and keep the 1M window.
4. **Tests,** `tests/test_launch_model.py` on a temporary repo and state dir: (a) no payload model, `CLAUDE_SESSION_PROFILE=builder`, `CLAUDE_SESSION_MODEL=claude-opus-5-5[1m]`, a repo `config.yaml` with `ceilings_1m: {context: 400000}`: window 1000000, context ceiling 400000, `session_model` `claude-opus-5-5[1m]`, source `CLAUDE_SESSION_MODEL`; (b) the same without the repo layer: window 1000000 and the builder's shipped 1M ceiling; (c) payload `claude-opus-5-5` with the env set: the payload's, source `payload`; (d) `CLAUDE_SESSION_HELPER=1` with the env set and no payload model: `declared:opus`, window 200000, source null; (e) an empty or unknown env model: as today (`declared:opus`); (f) the meter's pick with a transcript reading `claude-opus-5-5` after (a): still 1000000.
5. **Docs.** `models.py`'s source list names the launcher's env as the session's source when the payload has none. RUNBOOK or SKILL gains one sentence only if it lists the env names the plugin reads.

## 3. Interfaces

`hooks.session_start(payload, env)`: unchanged signature. `resolved.json` `session.session_model_source: "payload" | "CLAUDE_SESSION_MODEL" | null`.

## 4. Findings that name this row

The observer's F14 (check-in 102, 2026-10-12 12:39). AR74 writes the variable and merges on its own; this reader is inert until it does.

## 5. Forbidden reads

Transcripts; the account's state directories; any other repo.

## 6. Report (capped)

At most 150 words: both acceptance lines' last lines; the tests red on the pin and why; each existing test changed; anything filed. Last line: branch, head sha.
