# claude-code-session: what becomes a mod (mod r1)

**Status:** design r1, 2026-10-11, docs only, unrefuted. Inputs: the observer's mods study of 2026-10-11 (v2.1.296); admission-r1 (open question 3); respawn-r1 §3.3 and §3.4; the code at main 1a42a54 (`hooks.py`, `meter.py`, `budget.py`, `chain.py`, `plugin/hooks/`). Rules from the day's incidents: (a) what guards or holds safety stays a classic hook or a CLI path, since a mod hook that times out or throws is skipped and the action goes ahead; (b) the respawn launcher works where no mod loads (an untrusted folder, a `-p` child). Sibling plugins stay optional (§9, the owner's principle).

The one-sentence design: the mod is a window onto state that the classic hooks and the CLI own; it draws and cross-checks and never decides, so every refusal, stamp, ceiling and restart stays in Python.

## §1 The problem

The plugin speaks only to the model. The owner sees the zone only through `/session:status`, never sees a respawn's settle, and learns of an auto-compaction after it. A mod can draw, receive the engine's usage reading and add rows; it is early access, skipped on a timeout, unloaded after three crashes, absent before workspace trust.

## §2 The candidates

| # | candidate | gains | risks | verdict |
|---|---|---|---|---|
| M1 | the meter as one `AbovePrompt` band line: `ctx 62% · turns 31% · notice · charter <name> · respawn 41/60 s` | zone, charter and the launcher's settle without a command | display, never a sensor (D6 stands); prints its age past 120 s | **mod, first slice** |
| M2 | `session.measure` recorded beside the meter | catches a meter that parses wrong; feeds admission's `rateLimits` | two figures that differ, per turn against per tool | **mod, second slice**; the budget never reads it |
| M3 | a PreCompact block for entry 17's never-compact rule | no sitting is summarised unattended | a guard: a skipped mod hook lets the compaction through | **classic** (§3) |
| M4 | `/config` rows for the live knobs (`posture`, `reserve_pct`, `checkpoint`, `notes`) | typed, discoverable rows | `userConfig` persists machine-wide; the knobs are session overlays | **deferred**; `/session:set` stays; rows only for the band's own preferences |
| M5 | toasts at a zone crossing and at the launcher's grace | heard away from the prompt | noise beside CHECKPOINT | folded into M1, one per crossing |
| M6 | admission at `agent.spawn` | fresh figures at the spawn | fails open by design: a throttle, not a hold | joins the module after question 3 |

## §3 What stays classic, and why

- **The spawn gate** (`pre_tool_use`): a refusal (rule a).
- **The meter and the budget** (`meter.parse`, `budget.zone_for`, `_signal`, `_checkpoint_out`): CHECKPOINT and EXIT hold the sitting's safety (rule a). Zones come from `meter.json` alone.
- **The stamps** (`activity.json`, `turn-ended.json`, `respawn-main.json`, a helper's `calls/`) and **the launcher** (`claude-session run`, `chain.py`): the respawn's readiness (rules a and b). The launcher reads no file the mod writes.
- **SessionStart's resolve, the prompt's context, SessionEnd's ledger line**: needed in `-p` children, where a mod's load is unconfirmed.
- **The never-compact block**: a new classic `PreCompact` entry in `hooks.json` (`hooks/run PreCompact`), answering `decision: block` with a reason naming `checkpoint --respawn` on `trigger: auto`; §8 settles the triggers.

## §4 How the mod and the CLI share state

- The CLI owns every file under `<state>/sessions/<id>/` and writes each atomically. The mod reads with `$.fs.read` and writes none (`$.fs.write` is not atomic).
- At `session.start` the mod runs one new verb through `$.process.run` (5 s): `claude-session mod start --session <id>` prints the session's directory as JSON and writes `mod.json` (`{at, version}`), which `status` and `doctor` print as "mod: seen" or "mod: not seen".
- S2's `claude-session measure record` takes `session.measure`'s input on stdin and writes `measure.json`.
- `$.store` holds only `pref.*` keys; `$.state` the last line drawn. Neither holds a figure a decision reads.

## §5 Failure modes, and what the user sees

The classic path is unchanged in every row.

| failure | the user sees |
|---|---|
| no mod (untrusted folder, refused) | no band; `status` says "mod: not seen" |
| a hook times out or throws | one `hook skipped` line; the band ages |
| throws in every hook | each call skipped, one line each; the band stops drawing; classic intact (P1) |
| no `meter.json` (the CLI is off PATH) | `session: no meter · claude-session doctor` |
| measure and meter differ by over 5 points | `≠` beside the figure; `status` prints both; the meter decides |
| the API moves | `hooks module did not load`; `doctor` names the tested version |

## §6 Staged plan

- **P1, the proof first.** One `hooks.json` holds `modules` and the eight classic events. When the module throws at load, is refused or is unloaded, and in a `-p` child in a fresh worktree, the classic hooks still write `resolved.json`, `meter.json` and the stamps. If P1 fails, the module ships as an optional sibling plugin (reversible, logged here).

  P1's result (2026-10-12, claude 2.1.296, `scripts/p1-proof`): eight children ran a copy of `plugin/` whose `hooks.json` held `modules` beside the nine classic events (C1's PreCompact among them), with `XDG_STATE_HOME` in a scratch dir and the installed plugin off. Five `-p` children in a fresh scratch repo (the module clean, throwing in `register`, throwing in every hook, unloaded by a failed `engine.create`, refused by a sibling's `plugin.register`) and three interactive ones in this worktree (throws at load, refused, throws in every hook) each wrote `resolved.json`, `activity.json`, `turn-ended.json` and the ledger. The interactive three also wrote `meter.json`; only PostToolUse writes it, and the `-p` prompt called no tool, so no `-p` child wrote it, the control included (the script's prompt now reads a file first). The module loads under `-p` (the control wrote its marks), so §5's "no mod (`-p`)" does not hold on this build. There is no three-crash unload: 170 failing hook calls in one interactive session were each skipped and the module stayed loaded; the one unload seen is a failed `engine.create` ("unloaded, $ built again without it"). Not proven: `meter.json` from a `-p` child with a failing module, an unload in an interactive session, and an untrusted folder (accepting its trust dialog writes `~/.claude.json`). Verdict: P1 holds; the module ships in the session plugin.
- **S1, the first slice: M1, a read-only band.** One `ui.render` hook on `AbovePrompt`, redrawn on `turn.complete` and every 5 s; it reads `meter.json`, `respawn.json` and `turn-ended.json`, writes nothing, runs only `mod start`. Offline tests (conventions amended by admission-r1's S25).
- **C1, classic, beside S1:** the PreCompact hook: block `auto`, pass `manual` (§8, decided). The shim maps any non-zero exit of the CLI on PreCompact to 0 and keeps its stdout, so a CLI older than the plugin never blocks a compaction.
- **S2:** M2, `measure record`; `status` and `doctor` print the drift. Built by packet M2 (2026-10-12): every `session.measure` writes `measure.json`; `status` compares its context tokens with the meter's when the two are within 120 s, and `doctor` warns at a drift of 10% or more, never failing; nothing that decides reads it.
- **S3:** admission-r1's spawn hook joins, in `observe` mode, after question 3.

## §7 Acceptance criteria

1. `hooks.json` keeps the eight classic events with their commands and timeouts; S1 adds only `modules`.
2. `grep -nE 'fs\.write|store\.set' plugin/hooks/*.js` finds no write but a `pref.` key.
3. A pytest proves `chain.py`, `hooks.py` and `budget.py` never open `measure.json` or `mod.json`.
4. A pytest: `measure.json` at 99% beside `meter.json` at 10% gives zone `clear` and no CHECKPOINT.
5. The pytest suite passes unchanged with `plugin/hooks/*.js` removed.
6. Module tests: the band reads `ctx 62% · turns 31% · notice` from a fixture, `no meter` without one, its age past 120 s, and fits `bodyColumns`.
7. `grep -nE 'respeak|decisions|agent-relay' plugin/hooks/*.js` finds nothing: the mod works with no sibling installed.
8. P1's result is written into §6 before S1 merges.
9. C1: a `PreCompact` payload on a blocked trigger returns `decision: block`; on the other, nothing on stdout (a passing hook's stdout would become compaction instructions).

## §8 Open risks, and the owner's choice

- Early access: `doctor` warns past the module's tested minor version.
- One hooks worker serves all mods; another mod's hang stalls the band.
- The engine's context is an estimate, the meter's a usage sum; 5 points may be noisy.
- Classic hooks fail open on a timeout too unless `onFailure: "block"` (v2.1.295+) is set; the plugin sets it nowhere (a NICE_TO_HAVE note).
- **Auto-compaction, decided: (a)**, by portfolio entry 17 (a sitting restarts rather than compacts; a compaction needs the owner's hand). Block `auto`; let a `/compact` the owner types pass. The cost stays: a blocked `auto` keeps a sitting whole to its hard limit, where the recovery compaction is refused and that request fails. (b), block both, and (c), block neither, are not taken; (c) contradicts entry 17.

## §9 Item: the hard dependencies

`plugin/.claude-plugin/plugin.json` declares `dependencies` on decisions, respeak and agent-relay ("plugins that must be enabled for this one to work"), against the principle. Without each: **decisions**, nothing (its resolved section goes unread); **respeak**, the built-in profiles' `plugins: ["respeak"]` start with a "not found; skipping" warning, and only the author's `make readme` needs it (the README ships rendered); **agent-relay**, `push: never` loses the guard its hook gives, and under the default `enabled: auto` `doctor`'s relay check is red without `relay` and `tmux`. `doctor` failed each missing one. **Decided** (the owner's word, 2026-10-11 18:10: a user is never forced to install several plugins): `dependencies` is dropped (b671a84), and `doctor` reports each sibling as optional, a note naming what it adds when absent, any version fine when present, no range; under `enabled: auto` the relay check follows agent-relay's presence. Shipping each borrowed behavior as a static include rendered by its sibling stays a recommendation for a later slice.
