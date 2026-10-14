# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin with a command line tool, `agentik-session`. Together they give each Claude Code session one named profile, a budget with a stop, and a written charter. The plugin is part of a small family that answers "how much may this session spend, and what happens when it runs out".

## Why it exists

Several plugins cooperate in unattended relay runs. A driver spawns builder sessions, each builder may spawn agents, and nobody watches the terminal. Each sitting needs four things: one resolved configuration that every plugin reads the same way; a budget over context and turns whose stop is a signal, a rule, and, under the relay, a kill; a charter that records what the sitting is for and how it ended; and a gate on spawning. Without the gate and the budget, a swarm can fork past its means. With them, every session winds down at a known point and leaves a record a person can read.

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
make install
```

- `make install` (from a clone) freezes the committed `claude_session/` package under `~/.local/share/agentik-session/<tree>/`. It also writes the launcher `~/.local/bin/agentik-session`, which runs that frozen copy with `python -P` (Python 3.11 or newer). A dirty `claude_session/` exits 2, because the install always uses one committed tree.
- Then run `agentik session doctor` (or `/session:doctor` inside Claude Code). It checks the tool, the plugin, and its hooks, one line per check, and notes any optional sibling that is missing. Exit 2 names the failing check and its remedy.
- To upgrade, install the CLI first with `make install`, then run `claude plugin update session@agentik`. That order keeps the CLI current with its plugin's hooks. A CLI older than its plugin exits 2 on a hook event it does not recognize, but the hook shim stops that from blocking a turn. The older CLI's own doctor still reads green. Only `agentik session doctor` at 2.0.0-alpha.4 or later names an event its CLI cannot handle.
- At run time, the tool uses only Python's standard library.

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

Skills:

- `session`: covers profiles, session-only settings, the budget (the meter, the zones, CHECKPOINT and EXIT), the charter, and the priority and pacing rules.
- `read`, invoked as `/session:read <file> [SPEC]`: reads a markdown record by sections, never the whole file. For example, `/session:read design/overhaul-r1.md '§5'`.

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

Hooks (`plugin/hooks/hooks.json`): SessionStart, PreToolUse on every tool (its spawn gate acts only on `Agent|Task|Workflow`), PostToolUse, PostToolUseFailure, PostToolBatch, UserPromptSubmit, Stop, SessionEnd, and PreCompact. PreCompact blocks an automatic compaction (a sitting restarts instead) but still lets a `/compact` you type run.

## Profiles

Profiles ship in `claude_session/profiles.yaml`. The `defaults` entry carries every field, and each profile names only the fields it changes.

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

- `agentik session start <profile>` launches Claude Code with that profile, using flags only; nothing is written to `settings.json`. `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling, while Claude Code's own `--max-turns` is for print mode only. `start` sets `CLAUDE_SESSION_DEPTH` to the parent's depth plus one, and a nested `start` exits 2 unless you pass `--nested`.
- `agentik session set <knob> <value>` changes settings for this session only. Launch-time knobs (model, effort, tools) print the in-session equivalent (`/model`, `/effort`); `posture` applies immediately.
- A session's profile is its role. The SessionStart hook reads the name from `CLAUDE_SESSION_PROFILE` (or `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets); failing that, from `session.profile` in `config.local.yaml`, then in `config.yaml`; failing that, `frontier`. A helper that a session spawns (marked `CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`, so a helper of an orchestrator still keeps 180000 context tokens.
- The model decides the window, based on the `models:` table in `profiles.yaml`: fable and mythos get 1M; opus gets 200k, or 1M as `opus[1m]`; sonnet and haiku get 200k. Be cautious: Claude Code runs Opus 4.7 and later on 1M without marking it. A transcript's `message.model` never carries `[1m]`, so for Opus the window comes from the SessionStart payload's `model`, then the profile's `model`, then `ANTHROPIC_MODEL`, then the settings `model` key.
- The role decides the ceilings: `ceilings` applies on a 200k window, `ceilings_1m` on 1M. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 and 400 on 1M.
- Precedence: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (1M) wins, field by field. Next comes the role's ceilings for the resolved window, then the shipped defaults. The turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

The two orchestrator roles ship in `2.0.0-alpha.2`. Install that version of the launcher and the plugin first, then restart Claude Code. Until you do, `agentik session profile orchestrator` prints `unknown profile`, and the meter falls back to `frontier`.

Start an orchestrator session like this (quote `opus[1m]`, since zsh reads brackets as a glob):

```sh
make install                                          # from the clone: the launcher
claude plugin update session@agentik      # the plugin; restart Claude Code
agentik session profile orchestrator-opus              # prints the role, not unknown profile
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable               # Fable 5.1, 1M
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'     # Opus 5.5, 1M
```

For a repo that always orchestrates, put `session: {profile: orchestrator-opus}` in its `.claude/agentik/config.local.yaml` and run `claude --model 'opus[1m]'`. The SessionStart line names the profile, the ceilings, and the window, and `agentik session status` ends with the source, for example `role:orchestrator-opus window:1000000`. `agentik session start` recognizes only the legacy configurations, not these two roles.

## Budget

- The meter: after every tool call, the PostToolUse hook reads the transcript's new lines and writes `meter.json`, which records the used share of each of two ceilings, context and turns (`frontier`: 180000 context tokens, 400 turns, on either window). It re-picks the window from the model it reads and records `window_source` and `limits_source`.
- Zones are set by the larger share: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, and exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then every tenth tool call after that. At that point, bring the charter current, commit, and run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%. At that point, land the act in flight and exit.
- A RESPAWN close is the sitting's last act, run through Bash: `agentik-session checkpoint --respawn --charter <file>`. `--charter` is required. The verb reads only the charter's `## Next act` section, and its first line must open with `RESPAWN`; otherwise the verb exits 2 and writes nothing. It then checkpoints, writes `sessions/<session_id>/respawn.json`, and ends the sitting's turn. The PostToolUse hook confirms the mark only for the main thread's own Bash call. PreToolUse and UserPromptSubmit stamp the main thread's activity, and the Stop hook stamps each turn's end; it prints nothing and never blocks.
- The `respawn` key (`cap: 12`, `floor: 600`, `settle: 60`) holds a respawn chain's guards, and it layers like every other session key.
- `agentik session run` is the respawn chain. It starts `claude` with the same arguments at every start, each behind a fresh `--session-id`. When a sitting's RESPAWN close is confirmed and its turn has held for `settle` seconds with no helper call open, `run` ends the sitting, waits 10 s, writes a restart line, and starts the next one. It never compacts or resumes, and it never restarts after a crash. It caps the restart rate (restarts in any 24 h), enforces the floor (a sitting's minimum age), and respects a STOP file, either `respawn/STOP` or `respawn/<chain>/STOP` under the state root. Pressing Ctrl-C during the 10 s wait ends the chain. Every stop except a hang-up prints a start line that runs exactly as printed. Give a `/loop` an interval under 60m, or none: a longer one asks its question at every start, so `run` warns once.
- The spawn gate is the PreToolUse hook, and it behaves by posture: `off` stays silent; `signal` (the default) speaks but never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve.
- `agentik session status` prints the meter in one line. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, which holds one row per ended session, written by the SessionEnd hook. `report --chains` prints a respawn chain's restart and stop lines instead.

## Priority and pacing

- Two session keys are on in every shipped profile: `session.priority` (S1 harm, S2 blocks the goal, S3 the build order, S4 the rest) and `session.pacing` (the wakeup rides the act's last tool call; a pending helper is the wake; `WAITING <n>` stops the loop at `waiting`).
- SessionStart's line carries both in one block of at most 320 bytes. `agentik session rules` prints both in full, as resolved.
- Any layer can override them, field by field; `set` cannot. A level's text is quoted, since it holds ": ". No hook enforces either one.

## Sharing the resolved configuration

The configuration is layered, lowest first: the shipped profiles; `~/.claude/<plugin>/config.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; and the invocation.

At SessionStart the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`, shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`, accepts the file only when `provider.version` falls in its supported range, reads its own section, and never writes the file. When the file is absent, the dependent plugin runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak`, and `relay`, are optional. This plugin works with none of them installed, accepts any version of each, and `agentik session doctor` notes any one that is absent, along with what it adds. It needs nothing else outside the repo.

## The charter

There is one file per sitting, `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes the charter file.
- `agentik session charter check <file>` exits 2 and names the failing part.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- While `session.priority` is on, `open` writes `- open by level: none yet` under Handover. Each Handover entry then lists the open items by level, highest first.
- `check` and `close` warn, but leave their exit code unchanged, when that line is missing, when the Next act opens with a malformed `WAITING <n>: <what>; <how to tell>`, or at `session.pacing.waiting`.

The charter has five parts: the title line; the table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; and `## Next act`. A charter stays under 4,096 bytes.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named ones: an index like `3`, a list like `3,5`, a range like `3-5`, or a heading prefix like `'§5'`.
- Past `--max-bytes` (8192), it exits 3 unless you pass `--force`; the refusal names the subsections to request instead. It is stdlib and read-only.
- `/session:read <file> [SPEC]` wraps it: with no SPEC, it prints the map and stops; it never reads the whole file.

## Design of record

- `design/overhaul-r1.md`: the design of this version. Read it with `scripts/record design/overhaul-r1.md --sections`.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its own acceptance lines.
- Each sitting's decisions live in the `## Handover` section of its charter under `history/sittings/`.
- Rulings: recorded in the `decisions` plugin's records.

## Tests

- `make test` runs the whole suite, with a fake `claude` on the PATH and no quota spent.
- Targeted lines, by file: `.venv/bin/python -m pytest -q tests/test_meter.py tests/test_hook_meter.py tests/test_budget.py` (the meter and the zones); `tests/test_hooks.py tests/test_hook_session_start.py` (the hooks per event); `tests/test_resolver.py tests/test_sessionconfig.py` (the layers and `resolved.json`); `tests/test_charter.py`; `tests/test_record.py`; `tests/test_readme.py` (this README).
- `make check` is the gate: it runs test, lint, doclint, hygiene, and validate (`claude plugin validate`), then checks README freshness. It prints `readme: fresh` when `design/readme/rendered.sha256` holds the sha256 of `design/readme/source.md` and of `README.md`; otherwise it prints `readme: stale` and exits 2. It is bounded: one run per tree (`.check.lock`), an 840 s wall, and it holds off above a load of 4 x cores.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode, and writes both sidecar lines. Edit the source file, never the README directly.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak`, and `relay` each work alone, but a shared set of conventions keeps them consistent.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) stay byte-identical across the four repos.
- The README sidecar, `design/readme/rendered.sha256`, holds two `shasum -a 256` lines, written only by `make readme`.
- The packet shape: six sections, a `verify` row that is the gate line, and targeted acceptance lines.
- Siblings are named by plugin id only.

## Status

Status: version `v2.0.0-alpha.14`, rendered `2026-10-14`, `1186` tests in the suite.

## Credit

Two ideas started this project: reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line. Both come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
