# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin. It gives each session a budget you can see: a meter over context and turns, a checkpoint at 80%, and a note of what is done and what is next.

Use it when a session runs long enough to lose its thread.

Install it in a terminal, then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install session@agentik
/session:status
```

It needs Claude Code and the system's Python, version 3.9 or newer. It works alone: no clone, no package.
Part of [agentik](https://github.com/agentik-dev): the other tools, and how to leave.

## Why it exists

The plugin gives each session one named profile: a budget with a stop, and a written charter. It belongs to a small family of plugins that answers one question: "how much may this session spend, and what happens when it runs out".

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
```

- The plugin carries its own code, in `plugin/lib/claude_session/`, and runs it under `/usr/bin/python3`. Hooks never read PATH, so a session keeps its Python version until it respawns.
- `/session:install-cli` gives the terminal a CLI. A fresh Mac's relay band needs this: the command freezes the plugin's `lib/` under `~/.local/share/agentik-session/<hash>/` and writes `~/.local/bin/agentik-session`, which runs with `-I` under `/usr/bin/python3`. From a clone, run `make install`; a dirty tree exits 2.
- Then run `agentik session doctor`. It checks the tool, the plugin and the hooks; notes any absent optional sibling; and lists the instruction files the repo's last session loaded. Exit 2 names the failing check and its fix.
- To upgrade, run `claude plugin update session@agentik`. New sessions pick up the update right away; live sessions pick it up at their next respawn. A new session also moves the launcher forward.
- At run time, the tool uses only Python's standard library.

## Commands and skills

Each command wraps one CLI verb.

| command | example | what it does |
|---|---|---|
| `/session:status` | `/session:status --json` | this session's meter: context, turns, zone |
| `/session:profile` | `/session:profile builder` | lists the profiles, or shows one resolved for this repo |
| `/session:set` | `/session:set posture ask` | changes one setting for this session |
| `/session:checkpoint` | `/session:checkpoint -m "act 2 landed" --commit a.md` | marks a point ready for handoff; `--commit` takes only the paths you name |
| `/session:doctor` | `/session:doctor` | checks the setup |
| `/session:report` | `/session:report --since 2026-09-01` | the ledger, one row per ended session |
| `/session:gate` | `/session:gate --json` | the gate queue: running, queued, the last five done |
| `/session:install-cli` | `/session:install-cli` | writes the terminal's launcher |

Skills:

- `session`: covers profiles, session-only settings, the budget (the meter, the zones, CHECKPOINT and EXIT), the charter, and the priority and pacing rules.
- `read`, invoked as `/session:read <file> [SPEC]`: reads a markdown record by sections, not the whole file. Example: `/session:read design/overhaul-r1.md '§5'`.
- `unattended`, invoked as `/session:unattended [report]`: shows the newest run's status or report; it never starts a run.

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
| `akt` | `akt --dry-run`; `akt` is `run --`, used alone with `run.prompt` (it needs `history/sittings/`) |

Hooks (`plugin/hooks/hooks.json`): SessionStart; PreToolUse on every tool, which gates `Agent|Task`, denies `Workflow`, and refuses writes to files that the checkout's, a folder's, or the user's gate list names, with `*` matching one path segment; PostToolUse; PostToolUseFailure; PostToolBatch; UserPromptSubmit; Stop; SessionEnd; and PreCompact, which blocks an automatic compaction (a sitting restarts instead; `starter` allows it) but never blocks a typed `/compact`.

## Profiles

Profiles ship in `plugin/lib/claude_session/profiles.yaml`. The `defaults` entry carries every field, and a profile names only the fields it changes. Each profile holds `tiers`: design uses fable, build uses opus, words and mend use sonnet, lookup uses haiku. `start` exports the build tier as `CLAUDE_CODE_SUBAGENT_MODEL`.

| profile | for |
|---|---|
| `starter` | the default profile when nothing else is named; the meter is on, but there is no charter, priority, pacing, or respawn |
| `frontier` | everything on the seat, at full effort |
| `balanced` | Opus main thread, Sonnet subagents |
| `local` | the seat's main thread, with local subagents via `agentik-agents local` |
| `local-only` | main thread and subagents both on the local model; posture `off` |
| `scratch` | a test project; posture `off` and no charter required |
| `review` | read-only: Read, Glob, and Grep; permission mode `plan` |
| `packets` | writes packets and designs, never builds |
| `builder` | what the relay spawns; posture `deny` |
| `orchestrator` | large, complex work, using Fable 5.1 on its 1M window |
| `orchestrator-opus` | small and medium orchestrated projects, using Opus 5.5 on its 1M window |

- `agentik session start <profile>` launches Claude Code with that profile, using flags only, never `settings.json`. `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling. `start` sets `CLAUDE_SESSION_DEPTH` to the parent's depth plus one. A nested `start` exits 2 unless you pass `--nested`.
- `agentik session set <knob> <value>` changes this session only. Launch-time knobs print their in-session equivalent. `set tier.<role> <model>` and `set cap <model>` (each with `--until`) hold the session's tiers. `--save` writes a tier to a layer file, and `posture` applies at once. `set fill <reset|opus> [--until <zoned time>]` is the owner's word alone: it applies to an orchestrator's 1M main thread, this session only, and never past the week's reset. `run` hands it on; `set fill off` ends it from any seat.
- A session's profile is its role. The SessionStart hook reads the name from `CLAUDE_SESSION_PROFILE` (or `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets); failing that, from `session.profile` in `config.local.yaml`, then in `config.yaml`, then the user's `defaults.profile`, and failing all of those, `starter`. Naming `frontier` there takes on the sitting discipline. A helper (`CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`.
- Claude Code's measured window (`context.window`) decides this: a model change moves the window, the ceilings, and the ctx % at its next measurement. Before the first measurement, `profiles.yaml`'s `models:` table decides instead: fable and mythos get 1M; a bare `opus` gets 200k, or 1M when written as `opus[1m]`; sonnet and haiku get 200k. Opus is set by the SessionStart payload's `model`, then the profile's, then `ANTHROPIC_MODEL`, then the settings'.
- The role decides the ceilings: `ceilings` on a 200k window, `ceilings_1m` on 1M. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 and 400 on 1M.
- Precedence: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (1M) wins, field by field. Next comes the role's ceilings for the resolved window, then the shipped defaults. The turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

Start an orchestrator session like this (quote `opus[1m]`, since zsh reads brackets as a glob):

```sh
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'
```

A repo that always orchestrates names this in `.claude/agentik/config.local.yaml`: `session: {profile: orchestrator-opus}`.

## Budget

- The meter: after every tool call, the PostToolUse hook reads the transcript's new lines and writes `meter.json`, which holds the used share of two ceilings, context and turns. It re-picks the window, the engine's first, and records `window_source` and `limits_source`.
- Zones run by the larger of the two shares: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then every tenth tool call after that: bring the charter current, commit, run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%: land the act in flight, then exit.
- A RESPAWN close is the sitting's last act, done through Bash: `agentik-session checkpoint --respawn --charter <file>` reads only the charter's `## Next act` section, whose first line must open on `RESPAWN` (otherwise it exits 2 and writes nothing). It checkpoints, writes `sessions/<session_id>/respawn.json`, and the sitting ends its turn. `--state <s>` hands the successor a checked state file. PostToolUse confirms the mark only for the main thread's own Bash call.
- The `respawn` key (`cap: 20`, `floor: 600`, `settle: 60`) holds a chain's guards, and it layers like every session key.
- `agentik session run` is the respawn chain: the same `claude` arguments at each start, with a fresh `--session-id`. Once a RESPAWN close is confirmed, and the turn has stood for `settle` seconds with no helper call open, `run` ends the sitting, waits 10 s, writes a restart line, and starts the next one. It never compacts, resumes, or restarts a crash. The cap (restarts in any 24 h), the floor (a sitting's minimum age), or a STOP file (`respawn/STOP`, `respawn/<chain>/STOP`) can hold back a restart, and `status` names which one did. With no first prompt or `--model` given, `run` adds `run.prompt` or `run.model` (`null` means the profile's).
- The spawn gate is the PreToolUse hook, and it acts by posture: `off` stays silent; `signal` (the default) speaks but never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve.
- `agentik session status` prints the one-line meter. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, one row per ended session (for a resumed session, its last row), built from the SessionEnd hook. `report --chains` prints a chain's restart and stop lines. `report --hooks` prints, per event, the count, p50, p95, and nonzero exits from `hooks.jsonl`, then `claude_md_bytes`. Only this plugin's hooks are measured.

## Priority and pacing

- Two session keys apply here: `session.priority` (S1 harm, S2 blocks the goal, S3 the build order, S4 the rest) and `session.pacing` (the wakeup rides the act's last tool call; a pending helper counts as the wake; a wait is stated as `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`, and it is STALLED at `waiting`; fill is off).
- SessionStart's line carries both in one block of at most 320 bytes. `agentik session rules` prints both in full, as resolved.
- Any layer can override them, field by field, but `set` cannot. A level's text is quoted, because it holds ": ".

## Sharing the resolved configuration

The configuration is layered, lowest first: the shipped profiles; `~/.claude/agentik/profiles.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; the invocation.

At SessionStart, the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`, shaped as `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`. It accepts the file only when `provider.version` is in its range, reads its own section, and never writes to it. With no file present, it runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak` and `relay`, are optional. This plugin works with none of them and accepts any version of each; `agentik session doctor` notes when one is absent and what it would add.

## The charter

There is one file per sitting, `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes it.
- `agentik session charter check <file>` exits 2 and names the failing part, or exits 1 when the charter is red.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- With `session.priority` on, `open` writes `- open by level: none yet` under Handover, listing open items by level, highest first.
- `check` and `close` warn on a missing line, or on a `WAITING` line that is misshapen or stuck at `waiting`.

It has six parts, under 4,096 bytes: a title; a table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; `## While waiting`, which holds `- none` or ready/owed lines (a wait next to an S1 to S3 item, or an owed line, is red); and `## Next act`.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named sections: an index like `3`, a list like `3,5`, a range like `3-5`, or a heading prefix like `'§5'`.
- It exits 3 past `--max-bytes` (8192) without `--force`; the refusal names the subsections to ask for instead.

## The gate queue

Gates queue one per repo, under a load ceiling (RUNBOOK §5), and cut at `gate.wall`.

- `gate run <repo> [--lock PATH]... -- <command>` prints `queued <id>`, then prints `est <m> min` on stderr, which is the key's last 3 to 5 greens' median (none under 3). An existing lock path, or a running gate's own lock, holds the job back.
- Wake on a background `gate wait <id>` or on the hook's line; successors re-arm `## Gates`. It exits 0 normally, 2 when there is no such id, or 1 on timeout. `gate wait <id> --strict` reports the job's own exit: 124 for the wall, 125 for a dead runner, 126 for a lock held past it. Results keep `head`.
- `gate land` marks red a nested worktree, a branch behind main, or a bad merge file.

## The unattended loop

`agentik session unattended run <repo> [--rows a,b] [--until HH:MM] [--max-rows N] [--land PATH]` runs `relay/queue.yaml`'s rows in order, each as a `claude -p` builder in its own worktree, and never alongside a relay run.

- A `merge-on-green` row lands as one gate job, through `--land` or `<repo>/scripts/land`. A verdict other than the log's `ok` or `red <step>` reads as red `gate-unrun`.
- It exits 0 at the queue's end, at `--until`, or at `--max-rows`; it exits 3 on a limit, an auth error, or the run's `stop` file. `status` and `report` read its ledger.

## Design of record

- `design/overhaul-r1.md`: the design of this version.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its acceptance lines.
- Each sitting's decisions: the `## Handover` of its charter under `history/sittings/`.

## Tests

- `make test`: the whole suite, with a fake `claude` on PATH and no quota spent.
- For targeted lines, run `.venv/bin/python -m pytest -q tests/<file>.py`; `tests/test_readme.py` checks this README.
- `make check` is the gate: it runs test, lint, doclint, hygiene, and validate (`claude plugin validate`), then checks README freshness against `design/readme/rendered.sha256` (`readme: stale` exits 2). It is bounded: one run per tree (`.check.lock`), a 1800 s wall, and it holds off above a load of 4 x cores.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode, and writes both sidecar lines. Edit the source file, never the README directly.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak` and `relay` each work alone, under shared conventions.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) are byte-identical across the four repos.
- The README sidecar: `design/readme/rendered.sha256`, two `shasum -a 256` lines.
- The packet shape: six sections, a `verify` row, the gate line, targeted acceptance lines.
- Siblings are named by plugin id only.

## Status

Status: version `v2.0.0-alpha.139`, rendered `2026-11-17`, `5010` tests in the suite.

## Credit

Two ideas started this project: reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line. Both come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
