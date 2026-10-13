# Sitting 2026-09-28-1: claude-code-session, model-ceilings (ceilings by role, window by model)

| item | value |
|---|---|
| goal | the model decides the window (a `models:` table), the role decides the ceilings within it (`ceilings` on 200k, `ceilings_1m` on 1M); two orchestrator profiles (Fable 5.1, Opus 5.5 on 1M); the meter resolves the window from the model it reads and records the source; README steps to start an orchestrator; 2.0.0-alpha.2; `make check` 0 |
| budget | 180k context, 400 turns (the ledger's entry 12); land the act in flight at 80%; commit per act; never push, amend, rebase, a device, the network |
| pin | main 14d1144, worktree `model-ceilings` |
| window | 200k |
| agents | 0 (a helper of a hand-run sitting in the cross-repo ledger's repo) |

## Done-ness
- [x] act 0: this charter; findings on how Claude Code names a 1M Opus session
- [x] act 1: the models table, `ceilings_1m`, the two orchestrator profiles; the resolver picks the window and the ceilings (precedence); tests
- [x] act 2: the meter resolves the window from the transcript's model, then the session's, the declared, the configured model; `limits_source`; tests
- [x] act 3: 2.0.0-alpha.2 (pyproject, `__init__`, plugin.json, marketplace.json), before the render stamps it
- [x] act 4: docs (design §2.1 amended, README source, SKILL) and the steps to start an orchestrator; `make readme` passed in round 1; `make check` after the commit
- [x] close: the handover; the exit line; `make check` 0 on 96dbb47 (564 passed, doclint 0, hygiene 0, validate passed, readme fresh)

## Handover
1. **How Claude Code names a 1M Opus session** (2.1.284, its binary and transcripts' `message.model` only). The aliases are `sonnet`, `opus`, `haiku`, `fable`, `best`, `sonnet[1m]`, `opus[1m]`, `fable[1m]` and `opusplan`. The API id drops `[1m]`, so a transcript cannot show the 1M window: opus-5-5 sessions above 200k context still read `claude-opus-5-5`. The SessionStart payload carries `model`, the main-loop model, with `[1m]` intact. That was read from the binary, not from a live hook run. Consumer: the first orchestrator sitting, which checks `session_model` in resolved.json.
2. decide, owner: the payload's `model` is read before the profile's declared model, and the packet's order (declared, then env and settings) holds below it. It is an observation, like `message.model`, and it makes "opus 200k under orchestrator-opus reads 180k" true when the session starts on plain `opus`. Recommended: keep. Consumer: the owner, via the orchestrator.
3. decide, owner: `claude-session start` knows only the legacy configurations, so `start orchestrator` exits "unknown configuration". The README gives the working steps, `CLAUDE_SESSION_PROFILE=<role> claude --model ...`. Recommended: `start` reads profiles.yaml. Consumer: the next packet writer.
4. `window` is no longer an input. A repo config copied from overhaul-r1 §3's old default (`window: 200000`) now shows the key under doctor's unknown keys, and the key is ignored. Consumer: the owners of repo configs.
5. `claude plugin validate plugin/` warns five times: `${CLAUDE_PLUGIN_ROOT}` is unquoted in hooks.json. This predates the sitting. Consumer: the next packet writer.
- exit taken: goal met. Six commits on `model-ceilings` (charter, acts 1 to 4, this close), not pushed. `make check` 0. About 65 turns and 120k context, under the 80% line.

## Next act
The orchestrator reviews and merges `model-ceilings`. The first orchestrator-opus sitting checks `session_model` and `limits_source` in its resolved.json and meter.json.
