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

## 3. Interfaces: the acceptance table (brief mt1; baseline at the pin)

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

## 4. Findings that name this row: the choices inside the rulings

- The table's code is `tiers.py`; the resolver writes the layered table (no clock), and each reader (`rules`, SessionStart, the spawn gate) applies the session's `set tier.*` and `set cap` words against the clock, as `fill` is read.
- The user layer's `tiers:` and the repo's are top-level blocks, the one spelling (round 1 F3: `session.tiers` is not read, and is listed unknown); the user layer is `$CLAUDE_CONFIG_DIR/agentik/profiles.yaml` when that file exists, else `~/.claude/agentik/profiles.yaml`, so no file moves.
- `--save` on a tier writes the user file (`--save repo`: the repo's `config.yaml`) by rewriting its `tiers:` block whole (lines outside it stay; comments inside it, blank lines after it and CRLF are not kept: NICE n144), then resolves as the next session would (the hooks' launch profile) and, when the role's model is not the one written, names the layer that holds it and exits 1; `--save` on any other key is refused (exit 2), as are `config new` and `config delete`: no verb writes `configs.json`. A legacy `configs.json` is read only for the hooks' checkpoint cadence (`sessionconfig.stored`), one release.
- `balanced` keeps sonnet as its build tier (its former `subagents`); `scratch` goes local in five as `local-only`; `lookup` ships as haiku (the local lane is a profile's choice). `lane`, `plugins`, `notes` move into `profiles.yaml` with the fold; the shipped `permission_mode: auto` passes no flag, as the old table passed none.
- The role check warns under `signal` and `ask`, refuses under `deny`, is silent under `off`; a call with no model and no agent file model passes. `run` passes the profile's flags on the seat lane only. A cap with no `--until` is the session's alone and is not handed on.

- Round 1 (hq `REFUTE-2026-11-12-mt1-r1.md`, as ruled). The tiers' layers, lowest first: the shipped `defaults`, the user's `defaults`, the shipped profile, the user's body of it, the user's top-level `tiers:`, the repo's then the local file's top-level `tiers:` (an old `session.subagents` beneath each), then a launched profile's own body again (shipped, then the user's: F1, F2). The doctor's row resolves with `hooks.launch_profile` (F4). A model word is `[A-Za-z0-9._/\[\]-]+` naming a family, for `set tier.*` and `set cap` alike, refused before any write, and `--save` writes it quoted (F7; the cap is held to it too, one check for both verbs). The role line matches in any case, with a trailing `\r` or full stop, the first known role winning (F8); an unknown role is not warned (NICE n145). The hints name the user file's `profiles:` block (F5).
- Round 2 (hq `REFUTE-2026-11-12-mt1-r2.md`, as ruled). R2-F1: round 1's F10 is withdrawn in its raising form: a layer's model with no family is dropped, the role keeps the layer below, and `<layer>: tiers.<role>.model` joins the unknown keys (`set tier.*` still refuses such a word). R2-F2: frontier, packets, builder, orchestrator and orchestrator-opus state `tiers: {build: {model: opus}}`, as their pin bodies said `subagents: opus`; one rule stays, a profile named on the start line re-applies the tiers its body states above every file, and `set tier.*` sits above it. The review's `mat.py`, pin against this head: 768 cases, 68 differ, 64 the `local` profile's (R1) and 4 a user `defaults.profile` now read (R3). R2-F3, R2-F4: two messages name the user file's `profiles:` block.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made, what was not done.
