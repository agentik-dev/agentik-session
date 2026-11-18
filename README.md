# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin. It gives each session a budget it can see: a meter over context and turns, a checkpoint at 80%, and a note of what is done and what is next. Use it when a session runs long enough that it loses its thread.

Install it in a terminal. Then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install session@agentik
/session:status
```

It needs Claude Code and the system's Python at version 3.9 or newer. It needs no clone and no package: it works on its own.
This plugin is part of [agentik](https://github.com/agentik-dev), which lists the other tools and how to leave.

## Why it exists

The plugin gives each session one named profile, a budget with a stop, and a written charter. It belongs to a small family of plugins that each answer one question: "how much may this session spend, and what happens when it runs out".

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
```

- The plugin carries its own code (`plugin/lib/claude_session/`) and runs it under `/usr/bin/python3`. Hooks never use PATH, so a session keeps the same version until it respawns.
- `/session:install-cli` gives the terminal a CLI. A fresh Mac's relay band needs this CLI. The command freezes the plugin's `lib/` under `~/.local/share/agentik-session/<hash>/` and writes `~/.local/bin/agentik-session`, which runs with `-I` under `/usr/bin/python3`. From a clone, run `make install`; a dirty tree makes the install exit with code 2.
- Then run `agentik session doctor`. It checks the tool, the plugin, and the hooks. It notes any absent optional sibling, and it lists the instruction files that a repo's last session loaded. On exit code 2, it names the failing check and its remedy.
- To upgrade, run `claude plugin update session@agentik`. New sessions pick up the upgrade right away; a live session picks it up at its respawn. A new session also moves a launcher forward.
- At run time, the tool uses only Python's standard library.

## Commands and skills

Each command wraps one CLI verb.

| command | example | what it does |
|---|---|---|
| `/session:status` | `/session:status --json` | this session's meter: context, turns, and zone |
| `/session:profile` | `/session:profile builder` | lists the profiles, or shows one profile resolved for this repo |
| `/session:set` | `/session:set posture ask` | changes one setting for this session |
| `/session:checkpoint` | `/session:checkpoint -m "act 2 landed" --commit a.md` | marks a handoff-ready point; `--commit` takes only the named paths |
| `/session:doctor` | `/session:doctor` | checks the setup |
| `/session:report` | `/session:report --since 2026-09-01` | shows the ledger, one row per ended session |
| `/session:gate` | `/session:gate --json` | shows the gate queue: running, queued, and the last five done |
| `/session:install-cli` | `/session:install-cli` | writes the terminal's launcher |

Skills:

- `session`: profiles, session-only settings, the budget (the meter, the zones, CHECKPOINT and EXIT), the charter, and the priority and pacing rules.
- `read`, invoked as `/session:read <file> [SPEC]`, reads a markdown record by sections, never the whole file. Example: `/session:read design/overhaul-r1.md '§5'`.
- `unattended`, invoked as `/session:unattended [report]`, shows the newest run's status or report. It never starts a run.

CLI verbs (`agentik session --help`):

| verb | example |
|---|---|
| `start` | `agentik session start builder --max-turns 60` |
| `config` | `agentik session config show --resolved` |
| `doctor` | `agentik session doctor --json` |
| `profile` | `agentik session profile balanced` |
| `set` | `agentik session set tier.build haiku --save` |
| `checkpoint` | `agentik session checkpoint -m "tests green"` |
| `status` | `agentik session status` |
| `report` | `agentik session report --since 2026-09-01` |
| `charter` | `agentik session charter open "render the README"` |
| `budget` | `agentik session budget` |
| `rules` | `agentik session rules` |
| `run` | `agentik session run --chain loop -- --model 'opus[1m]' "/loop 30m check in"` |
| `gate` | `agentik session gate run . -- make check` |
| `reconcile` | `agentik session reconcile` |
| `unattended` | `agentik session unattended run . --until 06:30` |
| `akt` | `akt --dry-run`; `akt` is `run --`, alone with `run.prompt` (needs `history/sittings/`) |

Hooks (`plugin/hooks/hooks.json`) run at these points: SessionStart; PreToolUse on every tool, which gates `Agent|Task`, denies `Workflow`, and refuses writes to files that the checkout's, a folder's, or the user's gate list names, or that match `*` in one path segment; PostToolUse; PostToolUseFailure; PostToolBatch; UserPromptSubmit; Stop; SessionEnd; and PreCompact, which blocks an automatic compaction (a sitting restarts instead, and `starter` allows it) but never blocks a typed `/compact`.

## Profiles

Profiles ship in `plugin/lib/claude_session/profiles.yaml`. The `defaults` entry carries every field; a profile names only the fields it changes. Each profile holds `tiers`: design fable, build opus, words, mend sonnet, and lookup haiku. `start` exports the build tier as `CLAUDE_CODE_SUBAGENT_MODEL`.

| profile | for |
|---|---|
| `starter` | the default when nothing names a profile: the meter is on, and the charter, priority, pacing, and respawn are off |
| `frontier` | everything on the seat, at full effort |
| `balanced` | Opus on the main thread, Sonnet on subagents |
| `local` | the seat's model on the main thread, local subagents via `agentik-agents local` |
| `local-only` | main thread and subagents both on the local model; posture `off` |
| `scratch` | for a test project; posture `off`, and no charter is required |
| `review` | read-only: Read, Glob, Grep; permission mode `plan` |
| `packets` | writes packets and designs; it never builds |
| `builder` | what the relay spawns; posture `deny` |
| `orchestrator` | for large, complex work: Fable 5.1 on its 1M window |
| `orchestrator-opus` | for small and medium orchestrated projects: Opus 5.5 on its 1M window |

- `agentik session start <profile>` launches Claude Code with that profile, using flags only, never `settings.json`. `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling. `start` also sets `CLAUDE_SESSION_DEPTH` to the parent session's depth plus one. A nested `start` exits 2 unless you pass `--nested`.
- `agentik session set <knob> <value>` changes this session only. A launch-time knob also prints its in-session equivalent. `set tier.<role> <model>` and `set cap <model>` (each takes `--until`) set the session's tiers. `--save` writes a tier to a layer file. `posture` applies at once. `set fill <reset|opus> [--until <zoned time>]` is the owner's word alone: it holds an orchestrator's 1M main thread, in this session, never past the week's reset. `run` hands it on. `set fill off` ends it from any seat.
- A session's profile is its role. The SessionStart hook takes the profile name from `CLAUDE_SESSION_PROFILE` (or from `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets). If neither is set, it reads `session.profile`, first in `config.local.yaml`, then in `config.yaml`, then the user's `defaults.profile`, and falls back to `starter`. Naming `frontier` there takes on the sitting discipline. A helper (`CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`.
- Claude Code's measured window (`context.window`) decides the ceilings. A model change moves the window, the ceilings, and the ctx % at the next measure. Before that first measure, the `models:` table in `profiles.yaml` decides instead: fable and mythos get 1M; a bare `opus` gets 200k, or 1M when written as `opus[1m]`; sonnet and haiku get 200k. Opus itself resolves from the SessionStart payload's `model` field, then the profile's own setting, then `ANTHROPIC_MODEL`, then the settings file.
- The role decides the ceilings: `ceilings` applies on a 200k window, `ceilings_1m` on a 1M window. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 context tokens and 400 turns on the 1M window.
- Precedence runs in this order: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (the 1M window) wins first, field by field; then the role's ceilings for the resolved window; then the shipped defaults. The turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

To start an orchestrator session, quote `opus[1m]`, since zsh reads brackets as a glob:

```sh
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'
```

A repo that always orchestrates names this in `.claude/agentik/config.local.yaml`: `session: {profile: orchestrator-opus}`.

## Budget

- The meter works like this: after every tool call, the PostToolUse hook reads the transcript's new lines and writes `meter.json`, which holds the used share of two ceilings, context and turns. It re-picks the window each time, the engine's choice first, and records `window_source` and `limits_source`.
- Zones run by the larger of the two shares: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, and exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then after every tenth tool after that. At each one, bring the charter current, commit, and run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%. Land the act in flight, then exit.
- A RESPAWN close is the sitting's last act, run through Bash. `agentik-session checkpoint --respawn --charter <file>` reads only the charter's `## Next act` section. Its first line must open on `RESPAWN`, or the command exits 2 and writes nothing. Otherwise it checkpoints, writes `sessions/<session_id>/respawn.json`, and the sitting ends its turn. `--state <s>` hands the successor a checked state file. PostToolUse confirms the mark only for the main thread's own Bash call.
- The `respawn` key (`cap: 20`, `floor: 600`, `settle: 60`) holds a chain's guards. It layers, like every session key.
- `agentik session run` is the respawn chain. It uses the same `claude` arguments at each start, with a fresh `--session-id`. Once a RESPAWN close is confirmed and the turn has stood for `settle` seconds with no helper call open, `run` ends the sitting, waits 10 s, writes a restart line, and starts the next sitting. It never compacts, resumes, or restarts after a crash. A restart can be held by the cap (the number of restarts in any 24 h), the floor (a sitting's minimum age), or a STOP file (`respawn/STOP`, `respawn/<chain>/STOP`); `status` names which one held it. When there is no first prompt or `--model`, `run` adds `run.prompt` or `run.model` (`null` means the profile's own).
- The spawn gate is the PreToolUse hook, and it behaves by posture: `off` stays silent; `signal` (the default) speaks but never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve zone.
- `agentik session status` prints the one-line meter. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, which the SessionEnd hook writes with one row per ended session (a resumed session gets only its last row). `report --chains` prints a chain's restart and stop lines. `report --hooks` prints, per event, the count, p50, p95, and nonzero exits from `hooks.jsonl`, then `claude_md_bytes`. It measures only this plugin's hooks.

## Priority and pacing

- There are two session keys. `session.priority` ranks work as S1 harm, S2 blocks the goal, S3 the build order, or S4 the rest. `session.pacing` governs timing: the wakeup rides the act's last tool call, a pending helper is itself a wake, a wait is stated as `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`, it is STALLED at `waiting`, and fill stays off.
- SessionStart's line carries both in one block of at most 320 bytes. `agentik session rules` prints both in full, as resolved.
- Any layer can override them, field by field; `set` cannot. A level's text is quoted, because it contains ": ".

## Sharing the resolved configuration

The configuration layers, lowest first: the shipped profiles; `~/.claude/agentik/profiles.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; and the invocation.

At SessionStart, the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`. It is shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or from `$CLAUDE_CODE_SESSION_ID`. It accepts the file only when `provider.version` is in its range, reads its own section, and never writes to it. With no file present, it runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak`, and `relay`, are optional. This plugin works with none of them present and accepts any version of each; `agentik session doctor` notes any absent sibling and what it would add.

## The charter

Each sitting gets one file: `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes it.
- `agentik session charter check <file>` exits 2, naming the failing part, or exits 1 on a red check.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- With `session.priority` on, `open` writes `- open by level: none yet` under Handover, which lists open items by level, highest first.
- `check` and `close` warn on a missing line, or on a `WAITING` line that is misshapen or stuck at `waiting`.

The charter has six parts, under 4,096 bytes total: a title; a table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; `## While waiting`, which holds `- none` or ready/owed lines (a wait beside an S1 to S3 line, or an owed line, is red); and `## Next act`.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named ones: an index such as `3`, a list such as `3,5`, a range such as `3-5`, or a heading prefix such as `'§5'`.
- Past `--max-bytes` (8192) without `--force`, it exits 3; the refusal names the subsections to ask for instead.

## The gate queue

Gates queue, one per repo, under a load ceiling (RUNBOOK §5), and are cut at `gate.wall`.

- `gate run <repo> [--lock PATH]... -- <command>` prints `queued <id>`, then prints `est <m> min` on stderr. That estimate is the median of the key's last 3 to 5 green runs (never counting fewer than 3). An existing lock path, or a running gate's own lock, holds the job back.
- Wake on a background `gate wait <id>` or on the hook's line; successors re-arm `## Gates`. It exits 0 on success, 2 when no such id exists, or 1 on timeout. `gate wait <id> --strict` instead exits with the job's own code: 124 for the wall, 125 for a dead runner, 126 for a lock held past it. Results keep `head`.
- `gate land` marks red a nested worktree, a branch behind main, or a bad merge file.

## The unattended loop

`agentik session unattended run <repo> [--rows a,b] [--until HH:MM] [--max-rows N] [--land PATH]` runs the rows in `relay/queue.yaml` in order. Each row runs a `claude -p` builder in its own worktree, and it never runs beside a relay run.

- A `merge-on-green` row lands as one gate job, through `--land` or `<repo>/scripts/land`. A verdict other than the log's `ok` or `red <step>` reads as red `gate-unrun`.
- It exits 0 at the queue's end, at `--until`, or at `--max-rows`. It exits 3 on a limit, an auth error, or the run's `stop` file; `status` and `report` read its ledger.

## Design of record

- `design/overhaul-r1.md`: the design of this version.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its own acceptance lines.
- Each sitting's decisions: the `## Handover` of its charter under `history/sittings/`.

## Tests

- `make test` runs the whole suite, with a fake `claude` on PATH and no quota spent.
- For targeted runs, use `.venv/bin/python -m pytest -q tests/<file>.py`. `tests/test_readme.py` checks this README.
- `make check` is the gate. It runs test, lint, doclint, hygiene, and validate (`claude plugin validate`), then checks README freshness against `design/readme/rendered.sha256` (`readme: stale` exits 2). It is bounded to one run per tree (`.check.lock`), with a 1800 s wall, and holds off above a load of 4 x cores.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode, and writes both sidecar lines. Edit the source file, never the README directly.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak`, and `relay` each work alone, under shared conventions.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) are byte-identical across the four repos.
- The README sidecar is `design/readme/rendered.sha256`, holding two `shasum -a 256` lines.
- The packet shape holds six sections: a `verify` row, the gate line, and targeted acceptance lines.
- Siblings are named by plugin id alone.

## Status

Status: version `v2.0.0-alpha.137`, rendered `2026-11-17`, `5001` tests in the suite.

## Credit

Two ideas started this project: reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line. Both come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
