# agentik-session

<img src="assets/icon.svg" alt="" width="56" align="left">

`session` is a Claude Code plugin that gives each session a budget it can see: a meter over context and turns, a checkpoint at 80%, and a note of what is done and what is next.

Use it when a session runs long enough to lose its thread.

Install it in a terminal, then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install session@agentik
/session:status
```

It needs Claude Code and the system's Python 3.9+. It refuses Claude Code's Workflow tool. No clone, no package: it works alone.
Part of [agentik](https://github.com/agentik-dev): the other tools, and how to leave.

## Why it exists

The plugin gives each session one named profile, a budget with a stop and a written charter. Its family answers "how much may this session spend, and what happens when it runs out".

## Install

```bash
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install session@agentik
```

- The plugin carries its code (`plugin/lib/claude_session/`) and runs it under `/usr/bin/python3`. Hooks never use PATH, so a session keeps its version until it respawns.
- `/session:install-cli` gives the terminal a CLI. A fresh Mac's relay band needs this: the command freezes the plugin's `lib/` under `~/.local/share/agentik-session/<hash>/` and writes `~/.local/bin/agentik-session`, which runs with `-I` under `/usr/bin/python3`. From a clone, run `make install`; a dirty tree exits 2.
- Then run `agentik session doctor`. It checks the tool, the plugin and the hooks. It notes an absent optional sibling, and lists the instruction files a repo's last session loaded. Exit 2 names the failing check and its remedy.
- To upgrade, run `claude plugin update session@agentik`. New sessions pick it up; live sessions pick it up at their respawn. A new session moves a launcher forward.
- At run time the tool is stdlib Python only.

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
- `read`, invoked as `/session:read <file> [SPEC]`, reads a markdown record by sections, never the whole file. For example: `/session:read design/overhaul-r1.md '§5'`.
- `unattended`, invoked as `/session:unattended [report]`, shows the newest run's status or report; it never starts one.

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

Hooks (`plugin/hooks/hooks.json`) cover SessionStart, PreToolUse on every tool, PostToolUse, PostToolUseFailure, PostToolBatch, UserPromptSubmit, Stop, SessionEnd, and PreCompact. PreToolUse gates `Agent|Task`, denies `Workflow`, and refuses writes to files that the checkout's, a folder's or the user's gate list names, where `*` matches one segment. PreCompact blocks an automatic compaction, never a typed `/compact`; a sitting restarts instead, and `starter` allows it.

## Profiles

Profiles ship in `plugin/lib/claude_session/profiles.yaml`. The `defaults` entry carries every field, and a profile names only what it changes. Each profile holds `tiers`: design fable, build opus, words, mend sonnet, lookup haiku. `start` exports build as `CLAUDE_CODE_SUBAGENT_MODEL`.

| profile | for |
|---|---|
| `starter` | the default when nothing names a profile: the meter is on, and there is no charter, priority, pacing or respawn |
| `frontier` | everything on the seat, full effort |
| `balanced` | Opus main thread, Sonnet subagents |
| `local` | seat main thread, local subagents via `agentik-agents local` |
| `local-only` | main thread and subagents on the local model; posture `off` |
| `scratch` | a test project; posture `off`, no charter required |
| `review` | read-only: Read, Glob, Grep; permission mode `plan` |
| `packets` | writes packets and designs, never builds |
| `builder` | what the relay spawns; posture `deny` |
| `orchestrator` | large, complex work: Fable 5.1 on its 1M window |
| `orchestrator-opus` | small and medium orchestrated projects: Opus 5.5 on its 1M window |

- `agentik session start <profile>` launches Claude Code with that profile, using flags only, never `settings.json`. `--max-turns N` sets `CLAUDE_SESSION_MAX_TURNS`, which caps the turn ceiling. `start` sets `CLAUDE_SESSION_DEPTH` to the parent's depth plus one. A nested `start` exits 2 unless you pass `--nested`.
- `agentik session set <knob> <value>` changes this session only. Launch-time knobs print their in-session equivalent. `set tier.<role> <model>` and `set cap <model>` (each takes `--until`) hold the session's tiers; `--save` writes a tier to a layer file; `posture` applies at once. `set fill <reset|opus> [--until <zoned time>]` is the owner's word alone, for an orchestrator's 1M main thread, this session, never past the week's reset; `run` hands it on; `set fill off` ends it from any seat.
- A session's profile is its role. The SessionStart hook takes the name from `CLAUDE_SESSION_PROFILE` (or `CLAUDE_SESSION_CONFIG`, which `agentik session start` sets). Failing that, it reads `session.profile` from `config.local.yaml`, then from `config.yaml`, then from the user's `defaults.profile`, and else from `starter`. Naming `frontier` there takes up the sitting discipline. A helper (`CLAUDE_SESSION_HELPER=1`) inherits that variable but resolves as `builder`.
- Claude Code's measured window (`context.window`) decides: a model change moves the window, the ceilings and the ctx % at its next measure. Before the first measure, `profiles.yaml`'s `models:` table decides instead: fable and mythos get 1M; a bare `opus` gets 200k, or 1M as `opus[1m]`; sonnet and haiku get 200k. Opus's model comes from the SessionStart payload's `model` field, then the profile's, then `ANTHROPIC_MODEL`, then the settings'.
- The role decides the ceilings: `ceilings` on a 200k window, `ceilings_1m` on 1M. Every role gets 180000 context tokens and 400 turns on both windows, except the two orchestrators, which get 400000 and 400 on 1M.
- Precedence: a user or project layer that sets `ceilings` (for both windows) or `ceilings_1m` (for 1M) wins, field by field. Then the role's ceilings for the resolved window apply. Then the shipped defaults apply. The turn cap (`CLAUDE_SESSION_MAX_TURNS`) applies last.

Start an orchestrator session (quote `opus[1m]`: zsh reads brackets as a glob):

```sh
CLAUDE_SESSION_PROFILE=orchestrator claude --model fable
CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'
```

A repo that always orchestrates names it in `.claude/agentik/config.local.yaml`: `session: {profile: orchestrator-opus}`.

## Budget

- The meter: after every tool, the PostToolUse hook reads the transcript's new lines and writes `meter.json`, which holds the used share of two ceilings, context and turns. It re-picks the window, checking the engine first, and records `window_source` and `limits_source`.
- Zones, by the larger share: clear from 0%, notice from 80%, wind-down from 90%, reserve from 92%, exhausted at 100%.
- `CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80%), then every tenth tool: bring the charter current, commit, run `agentik session checkpoint`.
- `EXIT: ...` arrives at 100%: land the act in flight and exit.
- A RESPAWN close is the sitting's last act, run through Bash: `agentik-session checkpoint --respawn --charter <file>` reads only the charter's `## Next act` section, whose first line must open on `RESPAWN` (otherwise it exits 2 and writes nothing). It then checkpoints and writes `sessions/<session_id>/respawn.json`, and the sitting ends its turn. `--state <s>` hands the successor a checked state file. PostToolUse confirms the mark only for the main thread's own Bash call.
- The `respawn` key (`cap: 20`, `floor: 600`, `settle: 60`) holds a chain's guards and layers like every session key.
- `agentik session run` is the respawn chain: it uses the same `claude` arguments at each start, with a fresh `--session-id`. Once a RESPAWN close is confirmed, and the turn has stood for `settle` seconds with no helper call open, `run` ends the sitting, waits 10 s, writes a restart line, and starts the next one; it never compacts, resumes, or restarts after a crash. A restart can be held by the cap (restarts in any 24 h), the floor (a sitting's minimum age), or a STOP file (`respawn/STOP`, `respawn/<chain>/STOP`), which `status` names. With no first prompt or `--model` given, `run` adds `run.prompt` or `run.model` (`null` meaning the profile's).
- The spawn gate is the PreToolUse hook, by posture: `off` is silent; `signal` (the default) speaks and never blocks; `ask` asks before a spawn from wind-down on; `deny` also refuses a spawn in the reserve.
- `agentik session status` prints the one-line meter. `agentik session report` reads the ledger, `<state>/ledger.jsonl`, one row per ended session (for a resumed session, its last row), from the SessionEnd hook. `report --chains` prints a chain's restart and stop lines. `report --hooks` prints the per-event count, p50, p95 and nonzero exits from `hooks.jsonl`, then `claude_md_bytes`. Only this plugin's hooks are measured.

## Priority and pacing

- There are two session keys: `session.priority` (S1 harm, S2 blocks the goal, S3 the build order, S4 the rest) and `session.pacing` (the wakeup rides the act's last tool call; a pending helper is the wake; a wait says `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`; it is STALLED at `waiting`; fill is off).
- SessionStart's line carries them in one block of at most 320 bytes. `agentik session rules` prints both whole, as resolved.
- Any layer overrides them, field by field; `set` does not override them. A level's text is quoted because it holds ": ". No hook enforces either.

## Sharing the resolved configuration

The configuration is layered, from lowest to highest: the shipped profiles; `~/.claude/agentik/profiles.yaml`; the repo's `.claude/agentik/config.yaml`, then `config.local.yaml` beside it (gitignored); the launch profile; the session's overlay; and the invocation.

At SessionStart the plugin writes the result to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/sessions/<session_id>/resolved.json`, shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {...}}`.

A dependent plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`. It accepts the file only when `provider.version` is in its range, reads its own section, and never writes to it; with no file present, it runs alone. `agentik session config show --resolved` prints this session's file.

The sibling plugins, `decisions`, `respeak` and `relay`, are optional. This plugin works with none of them and accepts any version of each; `agentik session doctor` notes an absent sibling and what it adds.


## The charter

One file per sitting, `history/sittings/<date>-<n>.md` (the profile's `charter.dir`).

- `agentik session charter open "<goal>"` writes it.
- `agentik session charter check <file>` exits 2 naming the failing part, 1 on the red.
- `agentik session charter close --exit "<text>"` appends the exit line from the meter.
- With `session.priority` on, `open` writes `- open by level: none yet` under Handover, listing open items by level, highest first.
- `check` and `close` warn on a missing line, or on a `WAITING` line that is misshapen or still at `waiting`.

Six parts, under 4,096 bytes total: title; a table (goal, budget, pin, window, agents); `## Done-ness`; `## Handover`; `## While waiting` (`- none`, or ready/owed lines; a wait beside an S1 to S3 or owed line reads red); and `## Next act`.

## Reading records

- `scripts/record FILE --sections` lists a markdown record's sections. `scripts/record FILE --section SPEC` prints the named ones: an index `3`, a list `3,5`, a range `3-5`, or a heading prefix `'§5'`.
- Past `--max-bytes` (8192) without `--force`, it exits 3; the refusal names the subsections to ask for.

## The gate queue

Gates queue: one per repo under a load ceiling (RUNBOOK §5), cut at `gate.wall`.

- `gate run <repo> [--lock PATH]... -- <command>` prints `queued <id>`, then prints `est <m> min` on stderr (the median of the key's last 3 to 5 greens; never under 3). An existing lock path, or a running gate's lock, holds a new run back.
- Wake on a background `gate wait <id>` or on the hook's line; successors re-arm `## Gates`. It exits 0 on success, 2 if there is no such id, or 1 on timeout. `gate wait <id> --strict` exits with the job's own code: 124 for the wall, 125 for a dead runner, 126 for a lock past its time. Results keep `head`.
- `gate land` reds a nested worktree, a branch behind main, a bad merge file.

## The unattended loop

`agentik session unattended run <repo> [--rows a,b] [--until HH:MM] [--max-rows N] [--land PATH]` runs `relay/queue.yaml`'s rows in order, each as a `claude -p` builder in its own worktree, never beside a relay run.

- A `merge-on-green` row lands as one gate job, through `--land` or `<repo>/scripts/land`. A verdict other than the log's `ok` or `red <step>` reads as red `gate-unrun`.
- It exits 0 at the queue's end, at `--until`, or at `--max-rows`; it exits 3 on a limit, an auth error, or the run's `stop` file. `status` and `report` read its ledger.

## Design of record

- `design/overhaul-r1.md`: the design of this version.
- `design/conventions.md`: the conventions shared by the sibling plugins.
- `design/packets/`: one packet per build row, each with its acceptance lines.
- Each sitting's decisions: the `## Handover` of its charter under `history/sittings/`.

## Tests

- `make test`: the whole suite, with a fake `claude` on PATH and no quota spent.
- Targeted lines: `.venv/bin/python -m pytest -q tests/<file>.py`; `tests/test_readme.py` checks this README.
- `make check` is the gate: test, lint, doclint, hygiene, validate (`claude plugin validate`), then a README-freshness check against `design/readme/rendered.sha256` (`readme: stale` exits 2). It is bounded: one run per tree (`.check.lock`), a 1800 s wall, and it holds off above a load of 4 times the core count.
- `make readme` renders this README from `design/readme/source.md` through respeak's technical mode and writes both sidecar lines. Edit the source, never the README.

## Conventions shared with the sibling plugins

`session`, `decisions`, `respeak` and `relay` each work alone, under shared conventions.

- `scripts/hygiene` (the public-hygiene scan) and `scripts/doclint` (the doc gate) are byte-identical across the four repos.
- The README sidecar: `design/readme/rendered.sha256`, two `shasum -a 256` lines.
- The packet shape: six sections, a `verify` row, the gate line, targeted acceptance lines.
- Siblings are named by plugin id only.

## Status

Status: version `v2.0.0-alpha.164`, rendered `2026-11-17`, `5764` tests in the suite.

## Credit

Two ideas started this: reading the reset time out of Claude Code's statusline `rate_limits` payload, and lifting `session_id` from a headless run's JSON to emit a working `claude --resume` line. Both come from [claude-nextsession](https://github.com/pcx-wave/claude-nextsession) by pcx-wave (MIT). The implementation here is new.

## License

MIT
