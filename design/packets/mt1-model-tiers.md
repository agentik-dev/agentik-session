# Packet mt1: model tiers in the profiles, one table for every spawn

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief mt1 (hq `history/sessions/BRIEF-2026-11-12-session-mt1-model-tiers.md`); design of record hq design/13 §3 to §6; the owner's decisions 29 and 30 |
| pin | `33a4d85` on main (g4 merged, 2.0.0-alpha.89). Version 2.0.0-alpha.90, in its own commit (h3 bumps too). Worktree `.claude/worktrees/mt1-model-tiers`, branch `mt1-model-tiers`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `hooks.py`'s `_load_json` untouched (h3's) |
| may touch | `plugin/lib/claude_session/{profiles.yaml,resolver.py,sessionconfig.py,cli.py,hooks.py,chain.py,doctor.py,launch.py}`, a new `tiers.py`; `plugin/.claude-plugin/plugin.json`; `tests/test_mt1_tiers.py` (new) and the tests the fold breaks; `README.md`, `RUNBOOK.md`, `design/readme/{source.md,rendered.sha256}`; this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_mt1_tiers.py` green and under `.venv-floor` (red at the pin) |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- Two tables: `profiles.yaml` (read by the resolver, hence the hooks) and `sessionconfig.DEFAULTS` (six configs, read with `configs.json` by `start`, `config` and `set --save`). `start orchestrator` is refused ("unknown configuration"); `start` exports `CLAUDE_CODE_SUBAGENT_MODEL` from the config's `subagent_model`.
- The resolver already reads the user's `profiles.yaml` (`defaults`, `profiles`, `models`), but the profile name comes from the launch, `config.local.yaml`, `config.yaml`, else `frontier` (resolver.py:466): no user default.
- `run` warns, never refuses, on no first prompt (`chain.prompt_gap`); it passes only the owner's arguments.
- `_spawn_rule` (hooks.py:361) refuses a Fable helper under a non-Fable session in every posture; no role is read.
- Five places in `profiles.yaml` say `xhigh` (defaults, frontier, packets, orchestrator, orchestrator-opus).

## 2. Rulings (brief mt1, R1 to R7)

R1 `tiers` in a profile, design/13 §3's table shipped in `defaults`; `orchestrator-opus` changes `design` alone, `local-only` all five to `local/default`; `subagents` is read as `tiers.build.model` one release. R2 one table: `sessionconfig`'s folds into `profiles.yaml`; `start` exports `tiers.build`; `_FORCE` never set; the doctor names a differing variable. R3 the user layer's `defaults.profile` sits between the repo's file and `frontier`; a `tiers:` block in the user file overrides a role everywhere, the repo's over the user's; `profile <name>` prints the table. R4 `set tier.<role> <model> [--until]`, `set cap <model> [--until]` (never saved, handed to a `run` successor while ahead); `--save` on a tier writes a layer file; no `configs.json`. R5 no `xhigh`. R6 a `tier: <role>` line in an Agent prompt: a model above the role's warns under `signal`, refused under `deny`; the family rule unchanged. R7 a start with no `--model` passes the profile's `--model` and `--effort`; `run` with no prompt refuses; `start <name>` takes every profile.

## 3. Acceptance (brief mt1; baseline at the pin)

| # | line | at the pin |
|---|---|---|
| 1 | `profile orchestrator` prints five tiers as §3; `orchestrator-opus` differs in `design`; `local-only` local in five | no `tiers` key |
| 2 | no `DEFAULTS` table in `sessionconfig.py`; `start -n` exports `tiers.build` in three profiles | the table holds six configs |
| 3 | user `defaults.profile` resolves; a repo's own wins; user `tiers:` overrides; repo's over user's | the user default is not read |
| 4 | `set tier.build sonnet --until`: `rules` shows it, gone after its time and in a new session; `set cap opus` holds a design spawn on fable; `cap --save` refused; a `run` successor keeps it | no verb |
| 5 | `--save` on a tier writes the layer file; no `configs.json` | `--save` writes `configs.json` |
| 6 | the role check by posture; no `tier:` line as at the pin; fable under opus refused always | no role check |
| 7 | `start -n orchestrator` and `run` (dry) pass the profile's `--model`, `--effort`; `--model x` alone wins | `start orchestrator` refused |
| 8 | no shipped profile says `xhigh` | five |

## 4. Decided inside the rulings

Kept in the hand-back, one line each, as the builder brief asks.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout.
