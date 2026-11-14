# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin that gives each session a budget it can see: a meter over context and turns, a checkpoint at 80%, and a note of what is done and what is next.
Use it when a session runs long enough to lose its thread.

Install it in a terminal, then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install session@agentik
/session:status
```

It needs Claude Code and the system's Python at 3.9 or newer. No clone and no package: it works alone.
Part of [agentik](https://github.com/agentik-dev): the other tools, and how to leave.

## Why it exists

The plugin gives each session one named profile, a budget with a stop and a written charter. It is part of a small family of plugins that answers "how much may this session spend, and what happens when it runs out".

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
```

- The plugin carries its code (`plugin/lib/claude_session/`) and runs it under `/usr/bin/python3`. Hooks never use PATH, so a session keeps its version until it respawns.
- `/session:install-cli` gives the terminal a CLI, which a fresh Mac's relay band needs: it freezes the plugin's `lib/` under `~/.local/share/agentik-session/<hash>/` and writes `~/.local/bin/agentik-session`, run with `-I` under `/usr/bin/python3`. From a clone, `make install`; a dirty tree exits 2.
- Then run `agentik session doctor`. It checks the tool, plugin and hooks, notes an absent optional sibling, and lists the instruction files a repo's last session loaded; exit 2 names the failing check and its remedy.
- To upgrade: `claude plugin update session@agentik`; new sessions pick it up, live ones at their respawn; a new session moves a launcher forward.
- At run time, the tool uses only the Python standard library.

## Commands and skills

Each command wraps one CLI verb.

| command | example | what it does |
|---|---|---|
| `/session:status` | `/session:status --json` | this session's meter: context, turns, zone |
| `/session:profile` | `/session:profile builder` | list the profiles, or show one resolved for this repo |
| `/session:set` | `/session:set posture ask` | change one setting for this session |
| `/session:checkpoint` | `/session:checkpoint -m "act 2 landed" --commit a.md` | mark a handoff-ready point; `--commit` takes the named paths alone |
| `/session:doctor` | `/session:doctor` | check the setup |
| `/session:report` | `/session:report --since 2026-09-01` | the ledger, one row per ended session |
| `/session:gate` | `/session:gate --json` | the gate queue: running, queued, the last five done |
| `/session:install-cli` | `/session:install-cli` | write the terminal's launcher |

Skills:

- `session`: profiles, session-only settings, the budget (the meter, the zones, CHECKPOINT and EXIT), the charter, and the priority and pacing rules.
- `read`, invoked as `/session:read <file> [SPEC]`: reads a markdown record by sections, never whole. Example: `/session:read design/overhaul-r1.md '§5'`.
- `unattended`, invoked as `/session:unattended [report]`: the newest run's status or report; it never starts one.

CLI verbs (`agentik session --help`):

| verb | example |
|---|---|
| `start` | `agentik session start builder --max-turns 60` |
| `config` | `agentik session config show --resolved` |
| `doctor` | `agentik session doctor --json` |
| `profile` | `agentik session profile balanced` |
| `set` | `agentik session set tier.build haiku --save` |
| `checkpoint` | `agentik session checkpoint -m "tests green"`; `agentik-session checkpoint --respawn --charter <file>` |
| `status` | `agentik session status` |
| `report` | `agentik session report --since 2026-09-01` |
| `charter` | `agentik session charter open "render the README"` |
| `budget` | `agentik session budget` |
| `rules` | `agentik session rules` |
| `run` | `agentik session run --chain loop -- --model 'opus[1m]' "/loop 30m check in"` |
| `gate` | `agentik session gate run . -- make check` |
| `reconcile` | `agentik session reconcile` |
| `unattended` | `agentik session unattended run . --until 06:30` |

Hooks (`plugin/hooks/hooks.json`): SessionStart, PreToolUse on every tool (gates `Agent|Task`, denies `Workflow`, refuses writes to files the checkout's, a folder's or the user's gate list names, `*` in one segment), PostToolUse, PostToolUseFailure, PostToolBatch, UserPromptSubmit, Stop, SessionEnd, and PreCompact. PreCompact blocks an automatic compaction (a sitting restarts instead), never a typed `/compact`.

## Profiles

Profiles ship in `plugin/lib/claude_session/profiles.yaml`. The `defaults` entry carries every field; a profile names only what it changes. Each holds `tiers`: design fable, build opus, words, mend sonnet, lookup haiku; `start` exports build as `CLAUDE_CODE_SUBAGENT_MODEL`.

| profile | for |
|---|---|
| `frontier` | everything on the seat, full effort |
| `balanced` | Opus main thread, Sonnet subagents; the everyday default |
| `local` | seat main thread, local subagents via `agentik-agents local` |
| `local-only` | main thread and subagents on the local model; posture `off` |
| `scratch` | a test project; posture `off`, no charter required |
| `review` | read-only: Read, Glob, Grep; permission mode `plan` |
| `packets` | writes packets and designs, never builds |
| `builder` | what the relay spawns; posture `deny` |
| `orchestrator` | large, complex work: Fable 5.1 on its 1M window |
| `orchestrator-opus` | small and medium orchestrated projects: Opus 5.5 on its 1M window (`opus[1m]`) |

- `agentik session start <profile>` launches Claude Code with that profile, using flags only, never `settings.json`. `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling. Claude Code's own `--max-turns` flag applies in print mode only. `start` sets `CLAUDE_SESSION_DEPTH` to the parent's depth plus one. A nested `start` exits 2 without `--nested`.
- `agentik session set <knob> <value>` changes this session only. Launch-time knobs print their in-session equivalent; `set tier.<role> <model>`, `set cap <model>` (each `--until`) hold the session's tiers; `--save` writes a tier to a layer file. `posture` applies at once. `set fill <reset|opus> [--until <zoned time>]` is the owner's word alone: an orchestrator's main thread on 1M, this session only. It ends at its time or the week's reset, and never takes `--save`. `run` hands it on. `set fill off` ends it from any seat.
- A session's profile is its role. The SessionStart hook takes the profile name from `CLAUDE_SESSION_PROFILE` (or `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets). Failing that, it reads `session.profile` in `config.local.yaml`, then in `config.yaml`, then falls back to `frontier`. A helper (marked `CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`, so an orchestrator's helper keeps 180000 context tokens.
- Claude Code's measured window (`context.window`) decides: a model change moves window, ceilings and ctx % at its next measure. Before the first, `profiles.yaml`'s `models:` table does: fable and mythos 1M; a bare `opus` 200k, or 1M as `opus[1m]`; sonnet and haiku 200k; Opus by the SessionStart payload's `model`, the profile's, `ANTHROPIC_MODEL`, the settings'.
- The role decides the ceilings: `ceilings` on a 200k window, `ceilings_1m` on 1M. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 and 400 on 1M.
- Precedence: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (1M) wins, field by field; then the role's ceilings for the resolved window; then the shipped defaults; the turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

Start an orchestrator session (quote `opus[1m]`: zsh reads brackets as a glob):

```sh
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable               # Fable 5.1, 1M
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'     # Opus 5.5, 1M
```

For a repo that always orchestrates, put `session: {profile: orchestrator-opus}` in its `.claude/agentik/config.local.yaml` and run `claude --model 'opus[1m]'`.

## Budget

- The meter: after every tool, the PostToolUse hook reads the transcript's new lines and writes `meter.json`, which holds the used share of two ceilings, context and turns. It re-picks the window, engine's first, and records `window_source` and `limits_source`.
- Zones, by the larger share: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then every tenth tool: bring the charter current, commit, run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%: land the act in flight and exit.
- A RESPAWN close is the sitting's last act, run through Bash: `agentik-session checkpoint --respawn --charter <file>`. `--charter` is required. The verb reads only the charter's `## Next act`. Its first line opens on `RESPAWN`, or the verb exits 2 and writes nothing. It then checkpoints and writes `sessions/<session_id>/respawn.json`, and the sitting ends its turn. `--state <s>` hands the successor a checked state file its SessionStart line names. The PostToolUse hook confirms the mark only for the main thread's own Bash call.
- The `respawn` key (`cap: 20`, `floor: 600`, `settle: 60`) holds a chain's guards and layers like every session key.
- `agentik session run` is the respawn chain. It starts `claude` with the same arguments each time, under a fresh `--session-id`. When a sitting's RESPAWN close is confirmed and its turn stood `settle` seconds with no helper call open, `run` ends it. It waits 10 s, writes a restart line and starts the next. It never compacts, resumes or restarts a crash. It holds a restart at the cap (restarts in any 24 h), the floor (a sitting's minimum age) or a STOP file (`respawn/STOP`, `respawn/<chain>/STOP`); `status` names a hold, re-checked each poll. With no first prompt `run` refuses; with no `--model` each start passes the profile's `--model` and `--effort`.
- The spawn gate is the PreToolUse hook, by posture: `off` is silent; `signal` (the default) speaks and never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve.
- `agentik session status` prints the one-line meter. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, one row per ended session (a resumed one: its last), written by the SessionEnd hook. `report --chains` prints a respawn chain's restart and stop lines instead. `report --hooks` prints per-event count, p50, p95 and nonzero exits from `hooks.jsonl`, then `claude_md_bytes`. Only this plugin's hooks are measured. Only this plugin's hooks are measured; another's are invisible to it.

## Priority and pacing

- Two session keys, on in every shipped profile: `session.priority` (S1 harm, S2 blocks the goal, S3 the build order, S4 the rest) and `session.pacing` (the wakeup rides the act's last tool call; a pending helper is the wake; a wait says `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`, STALLED at `waiting`; fill off).
- SessionStart's line carries them in one block of at most 320 bytes. `agentik session rules` prints both whole, as resolved.
- Any layer overrides them, field by field; `set` does not. A level's text is quoted, since it holds ": ". No hook enforces either.

## Sharing the resolved configuration

The configuration is layered, lowest first: the shipped profiles; `~/.claude/agentik/profiles.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; the invocation.

At SessionStart the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`, shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`. It accepts the file only when `provider.version` is in its range, reads its own section, and never writes it. With no file, it runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak` and `relay`, are optional: this plugin works with none and accepts any version of each, and `agentik session doctor` notes an absent one with what it adds. Nothing else outside the repo.

## The charter

One file per sitting, `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes it.
- `agentik session charter check <file>` exits 2 naming the failing part, 1 on the red.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- With `session.priority` on, `open` writes `- open by level: none yet` under Handover: open items by level, highest first.
- `check` and `close` warn on a missing line, or a `WAITING` misshapen or at `waiting`.

Six parts, under 4,096 bytes: title; table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; `## While waiting`, `- none` or ready/owed lines (a wait beside an S1 to S3 or owed line is red); `## Next act`.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named ones: an index `3`, a list `3,5`, a range `3-5`, or a heading prefix `'§5'`.
- Exit 3 past `--max-bytes` (8192) without `--force`; the refusal names the subsections to ask for instead. Stdlib, read-only.
- `/session:read <file> [SPEC]` wraps it: with no SPEC it prints the map and stops; it never reads the whole file.

## The gate queue

Gates queue: one per repo under a load ceiling (RUNBOOK §5), cut at `gate.wall`.

- `gate run <repo> [--lock PATH]... -- <command>` prints `queued <id>`, then `est <m> min` on stderr (the key's last 3 to 5 greens' median; none under 3); an existing lock path, or a running gate's, holds it.
- Wake on a background `gate wait <id>` or the hook's line; successors re-arm `## Gates`. It exits 0, 2 no such id, 1 timeout; `gate wait <id> --strict`, the job's: 124 the wall, 125 a dead runner, 126 a lock past it. Results keep `head`.
- `gate land` reds a nested worktree, a branch behind main, a bad merge file.

## The unattended loop

`agentik session unattended run <repo> [--rows a,b] [--until HH:MM] [--max-rows N] [--land PATH]` runs `relay/queue.yaml`'s rows in order, a `claude -p` builder each in its worktree, never beside a relay run.

- A `merge-on-green` row lands as one gate job through `--land` or `<repo>/scripts/land`; a verdict other than the log's `ok` or `red <step>` reads red `gate-unrun`.
- Exit 0 at the queue's end, `--until` or `--max-rows`; 3 on a limit, an auth error or the run's `stop` file; `status` and `report` read its ledger.

## Design of record

- `design/overhaul-r1.md`: the design of this version.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its acceptance lines.
- Each sitting's decisions: the `## Handover` of its charter under `history/sittings/`.

## Tests

- `make test`: the whole suite, with a fake `claude` on the PATH and no quota spent.
- Targeted lines: `.venv/bin/python -m pytest -q tests/<file>.py`, a file per area; `tests/test_readme.py` checks this README.
- `make check` is the gate: test, lint, doclint, hygiene, validate (`claude plugin validate`), then README freshness against `design/readme/rendered.sha256` (`readme: stale` is exit 2). Bounded: one run per tree (`.check.lock`), a 1800 s wall, held off above load 4 x cores.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode and writes both sidecar lines. Edit the source, never the README.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak` and `relay` each work alone, under shared conventions.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) are byte-identical across the four repos.
- The README sidecar: `design/readme/rendered.sha256`, two `shasum -a 256` lines, written only by `make readme`.
- The packet shape: six sections, a `verify` row that is the gate line, targeted acceptance lines.
- Siblings are named by plugin id only.

## Status

Status: version `v2.0.0-alpha.115`, rendered `2026-11-10`, `4544` tests in the suite.

## Credit

The two ideas this started from — reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line — come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
