# Packet S30: the idle wake follows the prompt cache's lifetime

| item | value |
|---|---|
| from | `NICE_TO_HAVE.md` "Prompt-cache audit" (the idle-wake row, and the lifetime row that merge 86ac60a added); Claude Code's "How Claude Code uses prompt caching" (code.claude.com/docs/en/prompt-caching) as of 2026-10-14 |
| pin | `main` at 5989005 (alpha.14); worktree `~/.cache/observer-worktrees/session-ttl`, branch `s30-cache-lifetime` off `main` with this packet |
| wall | this repo; no push, `--amend`, rebase, device, real `claude`, `agentik session run`, `claude plugin`, `make readme`, `make install` or `make check`; never write under `~/.local/state`; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; never write in another repo; every python `-B` |
| may touch | `claude_session/rules.py`, `claude_session/hooks.py` (`session_start`, `user_prompt_submit`, one new helper), `claude_session/cli.py` (`cmd_rules`), `tests/test_rules.py`, `tests/test_hook_session_start.py`, `tests/test_band.py`, `tests/test_cli.py`, `tests/conftest.py` (`INHERITED`), `plugin/skills/session/SKILL.md` and `RUNBOOK.md` (their "Priority and pacing" sections), `design/readme/source.md` (the status line's count only), `NICE_TO_HAVE.md` |
| acceptance | 1: `.venv/bin/python -B -m pytest tests/test_rules.py tests/test_hook_session_start.py tests/test_band.py tests/test_cli.py -q -k s30 2>&1 \| tail -1` reads `passed`, no `failed`; 2: `XDG_STATE_HOME=/nonexistent CLAUDE_CODE_PROMPT_CACHE_TTL=5m .venv/bin/python -B -m claude_session rules 2>&1 \| grep -c 'cache lives 5m'` reads `1`; 3 (the control): `.venv/bin/python -B -m pytest tests/test_rules.py tests/test_hook_session_start.py tests/test_band.py tests/test_cli.py tests/test_hooks.py -q 2>&1 \| tail -1` reads `passed`, no `failed`. Before and after: §4 |
| verify | `make check`, by the coordinator |
| budget | acts: 1 tests, red; 2 `rules.py`, the two hooks, `rules`; 3 docs, the count, the NICE row. 40 turns, stop at 32 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

The audit: `rules.PACE` says "a long delay" with no cap, and ScheduleWakeup turns 3600 s into 3636 to 3648 s, past the main loop's 1h lifetime, so each such wake rewrote the whole context (26 misses, about 4.8M tokens, in three days). The docs: the main conversation gets the 1h lifetime only on a Claude subscription within plan usage; on usage credits, an API key or a cloud provider it gets 5m, and a sitting that spills onto credits drops to 5m mid-sitting. Claude Code takes the first of: `FORCE_PROMPT_CACHING_5M=1`; `CLAUDE_CODE_PROMPT_CACHE_TTL`; the `promptCacheTtl` setting (`5m` or `1h`, 2.1.242 or later; any other value ignored); `ENABLE_PROMPT_CACHING_1H=1`; the default. So: on 1h an idle wait wakes at most 3300 s apart and the cache survives; on 5m any wait past about 270 s misses anyway, so an idle wait takes the long fallback and never wakes early to keep the cache.

## 2. Rulings (decided inside the design by the builder; reversible)

1. **Read, not assumed.** `rules.lifetime(env, cwd, band) -> (ttl, why)`. First, `DISABLE_PROMPT_CACHING` or a per-model `DISABLE_PROMPT_CACHING_*` truthy reads `off` (fix round F3). Then Claude Code's order: `FORCE_PROMPT_CACHING_5M` truthy (`1`, `true`, `yes`, `on`); `CLAUDE_CODE_PROMPT_CACHE_TTL`; `promptCacheTtl` in the local, project, then user settings, the project's under `CLAUDE_PROJECT_DIR` (cwd only when it is unset; F1), the user's under `CLAUDE_CONFIG_DIR` (else `~/.claude`; F4), each read only as a regular file of at most 1 MiB, non-blocking (F5); managed settings and `--settings` are not read; `ENABLE_PROMPT_CACHING_1H` truthy; then the default: `CLAUDE_CODE_USE_BEDROCK`, `_VERTEX`, `_FOUNDRY`, `_ANTHROPIC_AWS` or `_MANTLE` truthy is 5m (F2); `ANTHROPIC_API_KEY`, an `apiKeyHelper` or `ANTHROPIC_BASE_URL` reads unknown, never 1h (the review's observation); else band.json's five-hour reading, while its `resetsAt` is ahead: 5h or 7d at 100 or more is 5m (past plan usage, on credits), else 1h (within plan usage). Nothing says: `(None, why)`. A key session that sets none of these, beside a subscription's band, still reads 1h (filed S4).
2. **The numbers** are constants, `WARM = {"1h": 3300, "5m": 270}`, not session keys: they follow the lifetime, not a taste. 3300 leaves 300 s under the hour for the late fire. `PACING` and its bounds do not change.
3. **The SessionStart block.** The pacing part gains `, cache 1h: idle wakes <=3300s`, `, cache 5m: no keep-warm wakes` or `, cache off: no keep-warm wakes` (30 or 31 bytes; the default block reads at most 317 of 320) only when the lifetime is known and the whole block fits `BLOCK_MAX`; otherwise the block is as before, never cut for it. `off` gives no keep-warm advice: an idle wait takes the long fallback. The pinned block (unknown) and the bound case are unchanged.
4. **`rules`** prints pacing item 6, the lifetime in force and why, with what it means for an idle wait; unknown prints both cases. `PACE` keeps five items (S29 pins its length); item 6 is `LIFETIME[ttl]`.
5. **The live hint.** UserPromptSubmit adds one bit after the band line, `cache 1h (<why>): ...` or `cache 5m (<why>): ...`, when pacing is on and the lifetime known; nothing otherwise. Display only, as band.json is. It reads band.json itself, so `_admission_line` stays as S27b pinned it.
6. **Version** stays `2.0.0-alpha.14`, as S29 and band-target left it: the CLI carries the change (`make install`, the owner's). SKILL.md and RUNBOOK.md gain one sentence each.
7. **README.** It is generated. `source.md` sits 5 bytes under its 16,384 ceiling, so it gains no sentence; only its status count moves. `README.md` and the sidecar wait for the owner's `make readme`, so three `test_readme` lines read red until then: `test_status_line_matches_manifest_and_suite[readme]`, `test_sidecar_is_the_shasum_lines_of_the_source_and_the_readme` and `test_hand_edited_readme_fails_the_check` (its precondition is a fresh sidecar).

## 3. Interfaces

`rules.lifetime(env, cwd, band, now=None)`, `rules.WARM`, `rules.LIFETIME`, `rules.clause(session, ttl=None)`, `rules.render(session, life=None)`, `rules.hint(ttl, why)`; `hooks._cache_line(payload)`; `cli.cmd_rules`. Fixtures: `session(...)`, `S21_BLOCK`, `_s21_ctx`, `record`, `lim`, `adir`, `run`.

## 4. Findings that name this row

The NICE row above, and the acceptance lines:

| line | 5989005 (before) | the branch (after) |
|---|---|---|
| 1 | `132 deselected` (exit 5, no `test_s30`) | `passed`, no `failed` |
| 2 | `0` | `1` |
| 3 | `181 passed` (the control) | `passed`, no `failed` |

Each `test_s30` is red on 5989005: `lifetime` (the order, the band, the truthy words), the block (1h, 5m, unknown, the bound), item 6, the hint, the docs, the prompt line, the verb.

Fix round (the review of 1d4baf7: F1 to F5 and the key observation): each new `test_s30_f*` and `test_s30_a_key*` case is red on 1d4baf7 except the controls (Bedrock, Vertex, Foundry; an empty key; a setting or a cloud provider over a key).

## 5. Forbidden reads

Transcripts under `~/.claude/projects`; `~/.local/state` beyond reading; other repos.

## 6. Report

At most 200 words: the packet's commit, the branch head, the acceptance lines before and after, the rulings, the test totals.
