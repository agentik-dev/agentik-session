# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin, with its `agentik-session` command line tool, that gives each Claude Code session one named profile, a budget with a stop, and a written charter. It is part of a small family of plugins that answers "how much may this session spend, and what happens when it runs out".

## Why it exists

Several plugins cooperate in unattended relay runs: a driver spawns builder sessions, each builder may spawn agents, and nobody watches the terminal. Each sitting then needs four things: one resolved configuration that every plugin reads the same way, a budget over context and turns whose stop is a signal, a rule and, under the relay, a kill, a charter that says what the sitting is for and how it ended, and a gate on spawning. Without the gate and the budget a swarm can fork past its means; with them, every session winds down at a known point and leaves a record a person can read.

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
make install
```

- `make install` (from a clone) freezes the committed `claude_session/` package under `~/.local/share/agentik-session/<tree>/` and writes the launcher `~/.local/bin/agentik-session`, which runs that frozen copy with `python -P` (Python 3.11 or newer). A dirty `claude_session/` exits 2: the install is always one committed tree.
- Then run `agentik session doctor` (or `/session:doctor` inside Claude Code). It checks the tool, the plugin and its hooks, one line per check, and notes each optional sibling that is absent; exit 2 names the failing check and its remedy.
- To upgrade, install the CLI first: `make install`, then `claude plugin update session@agentik`. That order is what keeps the CLI current with its plugin's hooks. A CLI older than its plugin exits 2 on a hook event it does not know, and the hook shim keeps that from blocking a turn. The older CLI's own doctor reads green; only a `agentik session doctor` of 2.0.0-alpha.4 or later names an event its CLI does not handle.
- At run time the tool is stdlib Python only.

## Commands and skills

Each command wraps one CLI verb.

| command | example | what it does |
|---|---|---|
| `/session:status` | `/session:status --json` | this session's meter: context, turns, zone |
| `/session:profile` | `/session:profile builder` | list the profiles, or show one resolved for this repo |
| `/session:set` | `/session:set posture ask` | change one setting for this session; `--save` keeps it |
| `/session:checkpoint` | `/session:checkpoint -m "act 2 landed" --commit` | mark a handoff-ready point; `--commit` stages tracked files only (`git add -u`) |
| `/session:doctor` | `/session:doctor` | check the setup |
| `/session:report` | `/session:report --since 2026-09-01` | the ledger, one row per ended session |
| `/session:gate` | `/session:gate --json` | the gate queue: running, queued, the last five done |

Skills:

- `session`: profiles, session-only settings, the budget (the meter, the zones, CHECKPOINT and EXIT), the charter, and the priority and pacing rules.
- `read`, invoked as `/session:read <file> [SPEC]`: reads a markdown record by sections, never whole. Example: `/session:read design/overhaul-r1.md '§5'`.

CLI verbs (`agentik session --help`):

| verb | example |
|---|---|
| `start` | `agentik session start builder --max-turns 60` |
| `config` | `agentik session config show --resolved` |
| `doctor` | `agentik session doctor --json` |
| `profile` | `agentik session profile balanced` |
| `set` | `agentik session set posture deny --save` |
| `checkpoint` | `agentik session checkpoint -m "tests green"`; `agentik-session checkpoint --respawn --charter <file>` |
| `status` | `agentik session status` |
| `report` | `agentik session report --since 2026-09-01`; `agentik session report --chains --json` |
| `charter` | `agentik session charter open "render the README"` |
| `budget` | `agentik session budget` |
| `rules` | `agentik session rules` |
| `run` | `agentik session run --chain night -- --model 'opus[1m]' "/loop 30m check in"` |
| `gate` | `agentik session gate run . -- make check`; `agentik session gate wait <id>` |

Hooks (`plugin/hooks/hooks.json`): SessionStart, PreToolUse on every tool (its spawn gate acts on `Agent|Task|Workflow` only), PostToolUse, PostToolUseFailure, PostToolBatch, UserPromptSubmit, Stop, SessionEnd, and PreCompact, which blocks an automatic compaction (a sitting restarts instead) and lets a `/compact` you type run.

## Profiles

Profiles ship in `claude_session/profiles.yaml`. The `defaults` entry carries every field; a profile names only what it changes.

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

- `agentik session start <profile>` launches Claude Code with that profile, by flags only (nothing is written to `settings.json`). `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling; Claude Code's own `--max-turns` is print mode only. `start` sets `CLAUDE_SESSION_DEPTH` to the parent's depth plus one; a nested `start` exits 2 without `--nested`.
- `agentik session set <knob> <value>` changes this session only. Launch-time knobs (model, effort, tools) print the in-session equivalent (`/model`, `/effort`); `posture` applies at once.
- A session's profile is its role. The SessionStart hook takes the name from `CLAUDE_SESSION_PROFILE` (or `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets), else `session.profile` in `config.local.yaml`, then in `config.yaml`, else `frontier`. A helper a session spawns (marked `CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`, so a helper of an orchestrator keeps 180000 context tokens.
- Claude Code's measured window (`context.window`) decides: a model change moves window, ceilings and ctx % at its next measure. Before the first, `profiles.yaml`'s `models:` table does: fable and mythos 1M; opus 200k, or 1M as `opus[1m]`; sonnet and haiku 200k; Opus by the SessionStart payload's `model`, the profile's, `ANTHROPIC_MODEL`, the settings'.
- The role decides the ceilings: `ceilings` on a 200k window, `ceilings_1m` on 1M. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 and 400 on 1M.
- Precedence: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (1M) wins, field by field; then the role's ceilings for the resolved window; then the shipped defaults; the turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

The two orchestrator roles ship in `2.0.0-alpha.2`. Install that version of the launcher and of the plugin first, then restart Claude Code; until then `agentik session profile orchestrator` prints `unknown profile` and the meter falls back to `frontier`.

Start an orchestrator session (quote `opus[1m]`: zsh reads brackets as a glob):

```sh
make install                                          # from the clone: the launcher
claude plugin update session@agentik      # the plugin; restart Claude Code
agentik session profile orchestrator-opus              # prints the role, not unknown profile
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable               # Fable 5.1, 1M
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'     # Opus 5.5, 1M
```

For a repo that always orchestrates, put `session: {profile: orchestrator-opus}` in its `.claude/agentik/config.local.yaml` and run `claude --model 'opus[1m]'`. The SessionStart line names the profile, the ceilings and the window. A bare `opus` reads the table's 200k only until the first measure. `agentik session status` ends with the source, e.g. `role:orchestrator-opus window:1000000`.

## Budget

- The meter: after every tool the PostToolUse hook reads the transcript's new lines and writes `meter.json`, the used share of each of two ceilings, context and turns (`frontier`: 180000 context tokens, 400 turns, on either window). It re-picks the window, engine's first, and records `window_source` and `limits_source`.
- Zones, by the larger share: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then every tenth tool: bring the charter current, commit, run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%: land the act in flight and exit.
- A RESPAWN close is the sitting's last act, run through Bash: `agentik-session checkpoint --respawn --charter <file>`. `--charter` is required. The verb reads only the charter's `## Next act`. Its first line must open on `RESPAWN`, or the verb exits 2 and writes nothing. It then checkpoints and writes `sessions/<session_id>/respawn.json`, and the sitting ends its turn. `--state <s>` hands the successor a checked state file its SessionStart line names. The PostToolUse hook confirms the mark only for the main thread's own Bash call.
- The `respawn` key (`cap: 12`, `floor: 600`, `settle: 60`) holds a chain's guards and layers like every session key.
- `agentik session run` is the respawn chain. It starts `claude` with the same arguments each time, under a fresh `--session-id`. When a sitting's RESPAWN close is confirmed and its turn stood `settle` seconds with no helper call open, `run` ends it. It waits 10 s, writes a restart line and starts the next. It never compacts, resumes or restarts a crash. It holds a restart at the cap (restarts in any 24 h), the floor (a sitting's minimum age) or a STOP file (`respawn/STOP`, `respawn/<chain>/STOP`); `status` names a hold, re-checked each poll. A `/loop` of 60m or more asks at every start, so `run` warns once.
- The spawn gate is the PreToolUse hook, by posture: `off` is silent; `signal` (the default) speaks and never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve.
- `agentik session status` prints the meter in one line. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, one row per ended session, written by the SessionEnd hook. `report --chains` prints a respawn chain's restart and stop lines instead.

## Priority and pacing

- Two session keys, on in every shipped profile: `session.priority` (S1 harm, S2 blocks the goal, S3 the build order, S4 the rest) and `session.pacing` (the wakeup rides the act's last tool call; a pending helper is the wake; from `WAITING <n>` at `waiting` the wake is the cache's idle limit, and no wait stops the loop).
- SessionStart's line carries them in one block of at most 320 bytes. `agentik session rules` prints both whole, as resolved.
- Any layer overrides them, field by field; `set` does not. A level's text is quoted, since it holds ": ". No hook enforces either.

## Sharing the resolved configuration

The configuration is layered, lowest first: the shipped profiles; `~/.claude/<plugin>/config.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; the invocation.

At SessionStart the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`, shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`, accepts the file only when `provider.version` is in its range, reads its own section, and never writes the file. When the file is absent, the dependent runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak` and `relay`, are optional: this plugin works with none installed and accepts any version of each, and `agentik session doctor` notes an absent one with what it adds. Nothing else outside the repo.

## The charter

One file per sitting, `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes it.
- `agentik session charter check <file>` exits 2 naming the failing part, 1 on the red.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- With `session.priority` on, `open` writes `- open by level: none yet` under Handover: open items by level, highest first.
- `check` and `close` warn on a missing line or a `WAITING <n>: <what>; <how to tell>` misshapen or at `waiting`.

Six parts, under 4,096 bytes: title; table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; `## While waiting`, `- none` or ready/owed lines (WAITING beside any other line is red); `## Next act`.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named ones: an index `3`, a list `3,5`, a range `3-5`, or a heading prefix `'§5'`.
- Exit 3 past `--max-bytes` (8192) without `--force`; the refusal names the subsections to ask for instead. Stdlib, read-only.
- `/session:read <file> [SPEC]` wraps it: with no SPEC it prints the map and stops; it never reads the whole file.

## The gate queue

A full gate can run an hour behind a lock, so gates queue: one at a time per state root (per Mac), each in its repo, cut at `gate.wall` (5400 s).

- `gate run <repo> [--lock PATH]... -- <command>` prints `queued <id>`; a lock path that exists holds it.
- Wake on `gate wait <id>` in a background Bash (a timeout past the gate) or on the hook's line; after a respawn the successor re-arms the ids in its state file's `## Gates`.
- `wait` exits 0 whatever the code, 2 for an unknown id, 1 on timeout; 124 is the wall's cut, 125 a dead runner, 126 a lock held past the wall.

## Design of record

- `design/overhaul-r1.md`: the design of this version.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its acceptance lines.
- Each sitting's decisions: the `## Handover` of its charter under `history/sittings/`.

## Tests

- `make test`: the whole suite, with a fake `claude` on the PATH and no quota spent.
- Targeted lines: `.venv/bin/python -m pytest -q tests/<file>.py`, a file per area; `tests/test_readme.py` checks this README.
- `make check` is the gate: test, lint, doclint, hygiene, validate (`claude plugin validate`), then README freshness against `design/readme/rendered.sha256` (`readme: stale` is exit 2). It is bounded: one run per tree (`.check.lock`), an 840 s wall, held off above load 4 x cores.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode and writes both sidecar lines. Edit the source, never the README.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak` and `relay` each work alone; a shared set of conventions keeps them consistent.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) are byte-identical across the four repos.
- The README sidecar: `design/readme/rendered.sha256`, two `shasum -a 256` lines, written only by `make readme`.
- The packet shape: six sections, a `verify` row that is the gate line, targeted acceptance lines.
- Siblings are named by plugin id only.

## Status

Status: version `v2.0.0-alpha.31`, rendered `2026-10-14`, `1842` tests in the suite.

## Credit

The two ideas this started from — reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line — come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
