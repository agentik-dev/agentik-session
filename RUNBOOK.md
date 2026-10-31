# agentik-session Runbook

What the README does not say: setup detail, choosing a profile, what
`local-only` measured on this machine, adjusting a session, and the budget
zones. Two facts govern everything below. First, anything you change with
`set` applies only to the running session unless you pass `--save`. Second,
an unattended run cannot answer a permission prompt, so an unanswered prompt
resolves to deny, even though Claude Code still reports success. Read section
3 and the `local-only` entry in section 2 before you run anything unattended.

## 1. One-time setup

1. Install the launcher: `make install` from the repo root, with
   `claude_session/` committed (a dirty package exits 2). It copies the
   committed package to `~/.local/share/agentik-session/<tree>/` (`<tree>` is
   `git rev-parse HEAD:claude_session`; an older copy is pruned unless a
   running process names it or it is among the newest three) and writes
   `~/.local/bin/agentik-session`, which runs that copy with `python -P`, so
   neither the directory a hook fires in nor the live checkout can change a
   hook. The interpreter is baked in: the repo's `.venv/bin/python` by
   realpath, else homebrew's `python3`, else `python3`; python 3.11 or newer.
   Re-run `make install` after each merge you want the hooks to run, and
   after the baked interpreter is upgraded away. `PREFIX=<dir>` (default
   `~/.local`) moves both paths. Do not `pip install -e .` into a venv
   instead: the hooks spawn with Claude Code's PATH, not your shell's, and a
   venv-only binary leaves every hook silently dead.
2. Install the plugin: `claude plugin marketplace add <clone>`, then
   `claude plugin install session@agentik`. The plugin wires its
   own hooks (`SessionStart`; `PreToolUse`, `PostToolUse` and
   `PostToolUseFailure` on every tool; `PostToolBatch`, `UserPromptSubmit`,
   `Stop`, `StopFailure`, `SessionEnd`, `PreCompact`) through `hooks/run`, which execs
   `agentik-session hook <event>` and exits 0 silently when the CLI is not on
   PATH. Nothing is merged into `~/.claude/settings.json`. To upgrade, the CLI installs
   first: `make install`, then `claude plugin update
   session@agentik`, then restart Claude Code. That order is
   what keeps the CLI current with its plugin's hooks. A CLI older than its
   plugin exits 2 on a hook event it does not know; the shim drops that exit
   on `Stop`, `StopFailure`, `PostToolUseFailure`, `PostToolBatch` and `PreCompact` (keeping
   PreCompact's stdout, its block), so no turn end, no helper's loop and no
   compaction you type is blocked. The older
   CLI's own doctor reads green: only a doctor of 2.0.0-alpha.4 or later
   fails its `plugin` line and names an event its CLI does not handle.
3. Run `agentik session doctor`. It checks the CLI, the python it runs under
   (and the newest known release), the plugin and its dependencies; a failing
   check exits 2 and names itself.

Until the hooks fire, `agentik session status` and `budget` have no samples
and say so.

## 2. Choosing a profile

Four constraints apply before you pick a lane, not after:

- `local`, `local-only`, and `scratch` run through your own `agentik-agents local`,
  which points `ANTHROPIC_BASE_URL` at the router. That disables Remote
  Control and voice dictation for the whole session. Use a seat profile
  (`frontier`, `balanced`, `review`) if you need either.
- The local-agent design names a local model on the main thread as an
  explicit non-goal. `local-only` and `scratch` do exactly that.
- `agentik agents route`'s local policy caps local subagent concurrency at 1. Local
  subagents run one at a time: ten of them is ten sequential runs, not a
  parallel sweep. Local is cheaper, not faster.
- A bare `Bash` allow in a `tools` list is not a sandbox. File tools take
  absolute paths, so a restrictive `cwd` buys nothing. `PreToolUse` hooks
  still fire and still deny.

`local-only` is the outlier: it is the only profile that can leave the seat
completely idle end to end, but the measured cost runs about 65 seconds per
turn (see below), and its own design guidance argues against using it as a
default. `agentik session config list` shows every profile; the shipped ones:

| config | lane | main thread | subagents | effort | tools | posture |
|---|---|---|---|---|---|---|
| `frontier` | seat | opus | opus | xhigh | default | signal |
| `balanced` | seat | opus | sonnet | high | default | signal |
| `local` | local | seat | agentik-agents local routing | high | default | signal |
| `local-only` | local-only | local default (27B) | local default | medium | default | off |
| `scratch` | local-only | local default | local default | low | default | off |
| `review` | seat | opus | opus | xhigh | Read, Glob, Grep + plan mode | signal |

`frontier`, `balanced`, and `review` also load the respeak plugin, via
`--plugin-dir`.

- `agentik session start frontier`: full-effort seat work, opus on both
  threads. Pick it when the task needs the strongest model everywhere. Cost:
  full seat billing at `xhigh` effort.
- `agentik session start balanced`: opus main thread, sonnet subagents. Pick
  it as the default seat config when subagent work does not need opus-grade
  reasoning. Cost: seat billing, lighter than `frontier` on the subagent
  side.
- `agentik session start local`: seat main thread; subagents go through
  `agentik-agents local`'s own router preflight and credential rules, which
  never replace your seat OAuth. Pick it when opus should drive but
  subagent work should stay off the seat. Cost: subagents serialize (see
  above), plus routing overhead per call.
- `agentik session start local-only`: local model on both threads at
  `medium` effort. Pick it only for the mechanical, bounded work the design
  doc scopes to rung 0 (retrieval, summaries, inventories, first-pass
  review, run-the-tests, bulk edits with a test as the contract), entered
  only through a named `local-*` agent with a small tool list. An unnamed
  agent belongs on rung 1 instead. Cost: about 65 seconds per turn measured
  (see below). With no permission mode set, an edit is declined outright.
  Not a daily driver.
- `agentik session start scratch`: same local-only lane, `low` effort. Pick
  it for throwaway exploration you would not run unattended. Cost:
  same serialization and reasoning-speed limits as `local-only`, at a lower
  effort ceiling.
- `agentik session start review`: opus, `xhigh` effort, tools restricted to
  `Read`, `Glob`, `Grep` plus plan mode. Pick it for an audit that cannot
  edit anything by construction. Cost: full seat billing at `xhigh`, same as
  `frontier`.

### What local-only actually measured (2026-09-05, this machine)

- `qwen3.8:27b-mtp-q8_0` is what `local/default` resolves to: 29 GB, already
  pulled.
- `agentik agents route --check`: 8 ok, 0 warn, 0 FAIL.
- Cold start evicts whatever model is resident and loads the 27B: about 25
  seconds.
- 155 s: local-only, tools limited to `Read`, `Glob`, `Grep` (3 tools), 2
  turns, a trivial read-a-file task.
- 327 s (about 65 s/turn): local-only, full default tool roster, 5 turns, a
  real edit task, no permission mode set. This number and the 155 s figure
  above are not interchangeable: different tool counts, different turn
  counts, different task shapes.
- On the 327 s run, the model reasoned correctly: it found `divide()`,
  ruled out the irrelevant file, and wrote the right guard. The `Edit` call
  itself was declined. Nobody was there to answer the prompt, and an
  unanswered ask resolves to deny. Claude Code still reported
  `subtype=success` / `is_error=false`. `agentik session` classified the run
  `PARTIAL`, because it reads `permission_denials` in the transcript rather
  than the process exit code.
- Router ledger for both local-only runs above: every request routed
  `local`, zero non-local. The seat stayed untouched on both.
- `agentik agents route`'s local policy: effort default `low`, max `medium`;
  `max_tokens<=8192`; concurrency 1.
- `[claude-code:unrecognized_model]` on stderr for `local/default` is
  expected and benign; the agents plugin's own end-to-end rigs grep it out.

## 3. Configuring and adjusting sessions

**Every `set` is session-only unless you pass `--save`.**

Applying a config never writes to `~/.claude/settings.json` either. Every
knob becomes a per-session CLI flag: `--model`, `--effort`, `--tools`,
`--permission-mode`, `--plugin-dir`, `--setting-sources`, `--settings`,
`--append-system-prompt`, `--add-dir`, `--name`. A configured session is
exactly as disposable as an unconfigured one. Run
`agentik session start <profile> --dry-run` to see the literal command before
it runs anything.

`set` writes to an overlay keyed by `$CLAUDE_CODE_SESSION_ID`. The
`SessionEnd` hook drops that overlay when the session ends.
`--save` promotes the value to the stored config instead.

Two kinds of key behave differently:

- Launch-time keys (`lane`, `model`, `effort`, `subagent_model`, `tools`,
  `permission_mode`, `plugins`, `setting_sources`, `add_dirs`,
  `fallback_model`, `settings`, `env`) cannot change a process already
  running, and a session-only `set` of one **is not applied by the next
  `start` either**: the overlay dies with this session, and `start` reads the
  stored config. `set` says so, and prints the in-session command that does
  change it now:

  ```
  note: model is a launch-time setting. This session-only record is
  informational -- it will NOT be applied by the next `start` ... To change
  it in this session right now, run  /model opus. To change what `start
  frontier` launches, add --save.
  ```

  `--config NAME` is only accepted together with `--save`: a session-only
  change always lands on the session you are in.

- Live keys (`posture`, `reserve_pct`, `checkpoint`, `notes`) take effect
  immediately, no restart needed.

`agentik session config show [name] [--stored]` marks whatever the overlay
is shadowing:

```
posture   ask   <- session only; stored: signal
```

Three keys are guarded because a typo or a bad value bricks or weakens every
future `start`: `permission_mode` and `effort` must be values the CLI
accepts; `setting_sources` must include `user`, since dropping it removes
`~/.claude/settings.json` and with it the break-glass `PreToolUse` guard and
these hooks. `env` refuses `PATH`, `PYTHONPATH`, `DYLD_*`, `ANTHROPIC_*` and
the credential variables outright. `name` and `description` are not settable.

Commands: `agentik session set <key> <value> [--save] [--config NAME]`,
`agentik session config list`, `agentik session config show [name] [--stored]`,
`agentik session config new <name> --from <base> --description "..."`,
`agentik session config delete <name>`.

An overlay set with `set` is confirmed gone once the `SessionEnd` hook
fires: this is covered by test, not just by design. It depends on the plugin's
hooks firing, per section 1.

**The priority and pacing keys.** `session.priority` and `session.pacing` sit
in the shipped `defaults`, both on in every shipped profile. Any layer
overrides them field by field: the user's `profiles.yaml`, the repo's
`config.yaml` or `config.local.yaml`. `set` does not take them. A layer may
replace one level's text, and the names S1 to S4 and their count stay fixed.
Quote each text, since it holds ": " and a bare scalar is refused:

```yaml
session:
  priority:
    levels:
      S4: "the rest: review notes and polish, filed in NICE_TO_HAVE.md; never ahead of S3"
  pacing: {fallback: 2400, waiting: 2}
```

`enabled: false` turns a part off, and SessionStart then prints nothing of
it. A level text is one line of 1 to 240 characters, `fallback` 60 to 3600
seconds, `waiting` 1 to 9. Anything else, or either key set to null or a
scalar, fails the resolve and names the key. A field outside them is dropped
and listed for the doctor as `<layer>: session.<key>.<field>`.

## 4. Budget and checkpoints as a signal

The band above the prompt (`session: <model> · <window> · ctx <c>% · turns <t>% · <zone>`, e.g. `session: opus 5.5 · 1M · ctx 64% · turns 6% · clear`) is the plugin's hooks module. The model is `meter.json`'s, shortened; the window is the one the ceilings apply; `1M (engine 200k)` means the meter has not caught up with the engine's latest reading (`measure.json`), and its next tool closes it (a session whose `resolved.json` has no `windows` block, written before they existed, stays so until a SessionStart); `status` prints the same in its `model:` line with the id and the window's source. A part it cannot read is left out. At session start the module runs `agentik session mod start --session <id>`, and `status` and `doctor` print `mod: seen` or `mod: not seen` (a `-p` child or a refused module is not an error).

The same module keeps the admission ledger, in `observe`: it records and never refuses. Six hooks (start, a rate-limit reading, a helper's spawn, a SendMessage resume, a helper's turn, the end) each run `agentik session admission record --session <id>` with one JSON object on stdin; the verb appends one line to `${XDG_STATE_HOME:-~/.local/state}/agentik-session/admission/ledger.jsonl` (dir 0700, file 0600) under a lock waited for at most 2 s, exits 2 on a refused kind, key, id or JSON and 3 on the lock, writing nothing then. An `end` adds a `done` with `swept: true` for each of that session's spawns left open; past 29 hours the ledger is renamed `ledger.1.jsonl`. A failed record is one `admission: record <kind>: …` line in the debug log, never an error; a spawn's prompt and a message's text are never sent.

Before each spawn, and each SendMessage resume, the module asks `agentik session admission admit --session <id>` for a verdict (one JSON object on stdin: the spawn's type, model, parent model, background, fork, its `tool_use_id`, the window readings and `resume`). Inside the same lock the verb reads the ledger, projects the five-hour window's peak at its reset (the burn of each active main thread, each running helper's life left and the new spawn's, fit from the ledger once it holds 20 ten-minute intervals, seeded before), appends one `verdict` line and prints `{verdict, mode, text, peak, window, resume_at}`: `admitted`, `unread` (no five-hour reading, and the week under its ceiling), `stale` or `wait` (the reading's reset has passed), `denied` (the seven-day window at its ceiling), `deferred` (interactive) or `not-started` (`-p`), the last three with the text the Agent tool will show once refusals are built. `resume_at` is the reset a holder waits for: the five-hour one, the week's on a weekly denial, null with nothing to name. `session.admission` sets `ceiling` (97), `margin` (3), `ceiling_7d` (97), the `seeds` and the window override below; `mode` is `observe` only, so nothing is refused yet: each answer is one `admission: admit …` line in the debug log, and the spawn goes ahead whatever it says.

The band shows the window: at every `record` and `admit` the verb rewrites `admission/band.json` (0600, inside the same lock) with the newest five-hour reading, its projected peak with no new spawn, the helpers in flight, the room left for spawns of the parent's family under `ceiling` less `margin`, the `deferred` and `wait` verdicts since the window began and the seven-day reading. Two logins on one Mac are told apart by a reading's seven-day `resetsAt`, to the minute, since the statusline names no account: with two or more in the ledger, each session's band (its reading, fit, helpers and room) and each verdict use only its own account's lines, and band.json adds `accounts` and `sessions`, from which each session draws its own (packet S35); its top level is the current login's entry, the key of the newest keyed reading, and a request with no list and no readings of its own is judged on that login too (packet S42); the one-at-a-time gate on a stale reading also counts the verdicts of other sessions with no key, so sibling relay rows still wait for one another. The module draws it as a second line under the session's, cut to the band's width, for example `5h 72% → 91% · ceiling 97 · resets 14:05 (1h12) · 3 helpers, room for 2 · 1 deferred · 7d 41% · observe` (`5h no reading` before the first reading; `· <n>s old` past 120 s). While a survey holds the band it draws neither line; another plugin's line stays under the two. The UserPromptSubmit hook adds the same line to the budget context; nothing that decides reads the file. `agentik session report` ends with `admission: five-hour windows`, one row per window in the ledger: its reset, its last reading, `held` when a spawn waited in it (in observe: would have) or `idle`, and `under 90` when the last reading is below 90, the use the target asks for; `admission: no ledger` without one.

Each login has a window mode, worked out from the readings at every call and stored nowhere (packet S42). `five_hour`, the default, is all of the above. `none` is a login with no five-hour window: after its newest list carrying a five-hour entry, whatever that entry's percent, one session holds two readings or spawns at least 30 minutes apart, each listing a fresh seven-day and no five-hour, with the week up at least one whole point. The pair stays in one session because an idle Max login lists the week alone from its five-hour reset to its next response. One list carrying a five-hour entry switches it back. An idle login whose pair has rotated out of the ledger reads `five_hour` until it is busy again, and a new weekly key detects afresh. On `none` a verdict is `denied` at `ceiling_7d`, else `admitted`, with `resume_at` the week's reset and earlier five-hour readings ignored; nothing waits for a band, attended or not. Its band entry has `P`, `peak` and `room` null, `P7`, `ceiling_7d` and `resetsAt` the week's. Every entry carries `window` and `slot`, the week's reset as weekday and minute (`Wed-1500Z`), and `accounts` is written whenever a key is `none`. To override the rule, set `session.admission.window` to `auto`, `five_hour` or `none`, or `windows: {Wed-1500Z: none}` per login, where a slot beats `window`; a slot it cannot read is one note in the answer and ignored, and a key spelled with a space or colon is refused by the config loader. Set a login's override in the user layer, `defaults.admission` in `~/.claude/agentik/profiles.yaml`: a session with no resolved file, as a relay row's ask is before its child starts, reads `window` and `windows` from there alone, and no other knob, profile or repo layer, so a repo-layer override binds only the sessions resolved with it, and band.json follows whichever session wrote it last. If a verified login reports five_hour at 0% rather than leaving it out, the rule never fires and the override is the switch. Until the pacing line changes, a `none` login's line reads `5h no reading · week resets HH:MM (h:mm), 5h HH:MM · …`, the `5h` time being the week's reset, and the prompt cache's lifetime reads unknown.

The same module records the engine's own measure beside the meter: every `session.measure` runs `agentik session measure record --session <id>` with `{context, rateLimits, cost, changed}` on stdin, which writes `measure.json` (0600) in the session's directory; it exits 2 on a refused key, number, id, JSON or a window that is not a whole number from 1 to 10**9, and 1 when the session's directory is absent, writing nothing then. When the window has moved it also rewrites `resolved.json` and `resolved.yaml` (`window`, `ceilings`, `window_source`, `limits_source`; a failure is silent and the next measure retries). That window is the first source of the window pick (`window_source` `engine:<n>`), and the meter takes it at the next tool; `set` keeps it, and a reading holds for the rest of the session. `status` prints `measure: engine <t> tokens / meter <c> tokens, drift <d>% (<age>s apart)` when the two were written within 120 s, `measure: not comparable (…)` otherwise, and `measure: none` without the file; `doctor`'s `measure` row warns at a drift of 10% or more and never fails. A drift means the meter may parse the transcript wrong: the budget still reads only the meter, and the tokens, percent, rate limits and cost of a measure decide nothing.

Budget is a signal, not a gate. The sitting's two ceilings (context, turns),
chosen by the role within the engine's measured window (the `models:` table only
before the first measure; a helper keeps its 200k ceilings on either window),
drive the meter. Claude Code runs Opus 4.7 and later on 1M unmarked, and a transcript's
`message.model` never carries `[1m]`, so the table reads a bare `opus` as 200k until
the first measure replaces it. The meter and the ceilings then follow the reading; the used share, the larger of the two, sets the zone, as the
`session` skill states it:

| zone | from | meaning |
|---|---|---|
| clear | 0% | work |
| notice | 80% | the checkpoint point: bring the charter current |
| wind-down | 90% | stop starting what you cannot finish |
| reserve | 92% | the wrap-up reserve: finish, commit, hand off |
| exhausted | 100% | exit |

`CHECKPOINT: ...` arrives at the profile's `checkpoint_at` (80% by default),
then every tenth tool; `EXIT: ...` arrives at 100%. `agentik session status`
prints the meter; `agentik session budget` the zone and checkpoint cadence.

Postures, least to most restrictive, all confirmed by test:

- `off`: no signalling.
- `signal` (default): never blocks a spawn, at any zone. It surfaces
  budget state and tightens checkpoint cadence instead.
- `ask`: at wind-down and above, a subagent spawn returns
  `permissionDecision: "ask"`. The reason names the zone.
- `deny`: returns `"deny"` only in the reserve zone; in wind-down it still
  just asks.

A checkpoint is a commit or a durable record: run one and the session is
handoff-ready at that moment. `agentik session checkpoint [-m MSG] [-c]`,
where `-c` runs `git add -u` (tracked files only) and commits. It never
stages untracked files: the wind-down nudge makes an autonomous agent the
likeliest caller, and `add -A` would sweep up a plaintext `.env` or a
tfstate. Untracked files are named on stderr so you can add them yourself.

### Priority and pacing

SessionStart's line carries one block of at most 320 bytes after `resolved
config at <path>`: the four level labels, that the Next act takes the highest
ready, and the pacing. Each label is its level's text to the first colon, at
most 24 characters. `agentik-session rules` prints both whole, as resolved:
the levels, the rules for filing and for bugs, the pacing items, and the
prompt cache's lifetime.

- Priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest. A
  bug ranks by harm and what it blocks, never by how sure or cheap its fix
  is. Each Handover lists the open items by level, highest first, and
  `charter open` writes `- open by level: none yet`. Below the Handover,
  `charter open` writes `## While waiting` with the one line `- none`. Its
  other lines are `- ready: <row> (<repo>, S<n>)`, an off-path row built
  without a gate, at most three, and `- owed: <item>; <what it needs>`, an
  owed item that needs no gate (a runsheet, a refuter round, a draft).
- Pacing: the fallback wakeup rides the act's last tool call. A pending
  helper, Monitor or background task is the wake, with one fallback of
  `fallback` seconds, never re-armed on a hand-back. An act ready takes the
  minimum delay. Waiting on an outside party, the Next act opens
  `WAITING <n>: <what>; <how to tell>`, n the wakes in a row with nothing
  changed. From n = `waiting` the wake is the longest idle wait the cache
  allows (the next bullet), and the charter is brought current and
  committed. A wait never stops the loop: under `agentik session run` a
  stopped loop only idles until a hand, and only the checkpoint ends a
  sitting. A respawn reads n from the charter. WAITING is legal only when
  the charter's While waiting section reads `- none`: with a ready row or
  an owed item listed there, the Next act is that item. What the owner must
  see goes in a file under `history/`, a PushNotification, or a turn that
  ends on text and calls no ScheduleWakeup, since text written before a
  ScheduleWakeup call was not shown at the terminal on 2026-10-21. A wait on
  the usage meter
  (room for 0, or a usage limit hit) is not WAITING: the Next act stays the
  act, the wake is the band's reset or one fallback, whichever is first, and
  it never counts toward n.
- The prompt cache's lifetime: on 1h (a subscription within plan usage) an
  idle wait wakes at most 3300 s apart, so the cache survives; on 5m (usage
  credits, an API key, a cloud provider, or `promptCacheTtl: 5m`) any wait
  past about 270 s misses anyway, so an idle wait takes the long fallback and
  never wakes early to keep the cache. It is read in Claude Code's order:
  `FORCE_PROMPT_CACHING_5M`, `CLAUDE_CODE_PROMPT_CACHE_TTL`, `promptCacheTtl`
  in the local, project (`CLAUDE_PROJECT_DIR`), then user settings
  (`CLAUDE_CONFIG_DIR`, else `~/.claude`), `ENABLE_PROMPT_CACHING_1H`; then
  a cloud provider is 5m; an API key (`ANTHROPIC_API_KEY`, an `apiKeyHelper`)
  or a gateway (`ANTHROPIC_BASE_URL`) is unknown; and the band's five-hour
  reading is 1h under 100%
  and 5m at 100% or past (usage credits). With none of these it is unknown.
  `DISABLE_PROMPT_CACHING` or a per-model form reads off, first of all: no
  wait keeps a cache warm, so an idle wait takes the long fallback.
  `agentik-session rules` prints it as pacing item 6, and the prompt line
  adds it after the band line; SessionStart's block names it only when the
  whole block still fits 320 bytes.
- A packet or brief bounds both: a builder files what lies outside it and
  takes none. No hook enforces them. `charter check` and `charter close` warn
  on stderr, their exit unchanged, when the Handover line is missing or the
  Next act's WAITING is misshapen or at `waiting` or past it, where the line
  says to wake at the idle limit and commit the charter, and on a While
  waiting line of another shape. A charter opened before 2.0.0-alpha.24 has
  no While waiting section: `check` passes it with one warning to add it
  with `- none`. One line is red, with `session.pacing` on: a Next act of
  WAITING while While waiting holds any line but `- none` prints `WAITING
  while ready: <the line>` first, and `charter check` exits 1 on it (2 on
  a refusal); `close`
  keeps its exit. A wait on the usage meter is exempt. `check` resolves
  from the current directory, and a failed resolve warns nothing.
- Upgrade the CLI first (`make install`): it prints the block. The plugin's
  skill names the verb. A 2.0.0-alpha.4 CLI prints no block.

### Restarting a sitting: `agentik session run`

`agentik session run` starts Claude Code and starts it again each time a
sitting closes on RESPAWN, so a sitting near its ceilings restarts rather
than compacts. Run it at a terminal, outside any Claude Code session:

```sh
CLAUDE_SESSION_PROFILE=orchestrator-opus agentik session run --chain night -- \
    --model 'opus[1m]' "/loop 30m check in, then RESPAWN at 80%"
```

Everything after `--` goes to `claude` unchanged at every start, behind a
fresh `--session-id`. Flags that resume, fork, detach or print are refused,
and so is `/compact`. A value that begins with `-` is refused after its
flag; write it as `--flag=value`. The last argument is the first prompt,
sent again at every start. Without one, every restart opens an idle session
that waits for a person, so `run` warns once and still runs. A list flag
(`--add-dir`, `--tools`, `--allowedTools`, `--disallowedTools`,
`--mcp-config`) reads every argument after it, the prompt too, so write it
as `--flag=value`. A sitting restarts only when its charter's
`## Next act` opens on `RESPAWN`, the main thread ran `agentik session
checkpoint --respawn --charter <file>`, and the turn has ended and stood
`settle` seconds with no helper call open. The launcher then ends the
sitting, waits 10 s (Ctrl-C there ends the chain), writes a restart line to
the ledger and starts the next. A sitting that exits without a confirmed
RESPAWN stops the chain, and a crash (a nonzero exit) is never restarted.
Every stop but a hang-up prints a start line that runs as printed (after a
hang-up the launcher writes nothing more to the terminal).

- A RESPAWN close runs in one order: `agentik session charter close --exit
  "<text>" <file>`, then commit the charter (close prints the line, which
  runs as is from any cwd: `next: git -C <dir> add -- <name> && git -C <dir>
  commit -m "charter: the exit taken" -- <name>`, `<dir>` the charter's
  absolute directory), then write the state file, then `agentik session
  checkpoint --respawn --charter <file> --state <s>` (close prints it as its
  `then:` line, without the optional `--state`). The checkpoint refuses, exit 2 and nothing written, a charter that
  `git status --porcelain` reads as modified, staged or untracked: `<file> is
  not committed; commit it first: <the same line>`. With `--commit` a tracked charter passes,
  an untracked one never; a git call that fails or times out goes on with a
  note. An exit line left uncommitted leaves main dirty, and holds every
  sibling that merges only into a clean main.
- The state file is the sitting's own word to its successor, since no hook
  sees a helper return or a gate finish. The checkpoint checks its shape:
  - the first line is `# State for the successor of <sid-short>, <YYYY-MM-DD>
    <HH:MM>`, a date and time that parse;
  - then exactly four sections, in this order, each a bulleted list (every
    line opens on `- `) or the one line `- none`: `## Helpers` (each open
    helper: its name, its scratch directory, what it is doing, what wakes the
    sitting), `## Gates` (each gate in flight: id, repo, result path), `## Last
    acts` (at most three lines, each opening on a commit sha: `- <sha> what it
    did`) and `## Read first` (at least one path line, `- <path> lines <a>-<b>`,
    in reading order, then the closing line `- read nothing else before the
    first act`, once and last);
  - under 8,192 bytes, and no em-dash.

  A fault refuses the checkpoint, exit 2, the faults on stderr. The copy lands
  in `respawn/<chain>/state.md`, `state.json` beside it. At the next start the
  launcher stamps the record with the successor's session id and deletes a
  state any other session left; only that successor's SessionStart line names
  it, and a copy that does not match its record is said so. A main-thread
  sitting's checkpoint without `--state` says `no --state: the successor
  orients from the charter alone` and clears an older copy (a helper, a relay
  row or a started session clears nothing); with no chain the copy stays in
  the session's own directory, where no successor looks.
- The guards are `session: {respawn: {cap, floor, settle}}` in the config
  layers (defaults 12 restarts in any 24 h, 600 s, 60 s); `--cap`,
  `--floor` and `--settle` override them for one chain.
- Two STOP files hold the chain: `respawn/<chain>/STOP` and
  `respawn/STOP` under the state root (the `state-dir` line of
  `agentik session doctor`). Touch one and the running sitting finishes
  without a restart; a STOP older than the chain's start is ignored, and the
  launcher never deletes one.
- A hold is checked again at every poll, so it lifts when its reason does:
  the sitting passes the floor, the charter opens on `RESPAWN` again under a
  new mark, the STOP file goes, or the 24 h count falls under the cap. While
  it stands, `respawn/<chain>/held.json` under the state root names the
  reason, since when and the session, and `agentik session status` prints
  `respawn held: <reason> since <HH:MM>`; the terminal stays silent. A hold
  that never lifts ends with the sitting: exit it, and the chain stops with
  that reason.
- Give a `/loop` an interval under 60m, or none. A `/loop` of 60 minutes or
  more asks its question before it arms, so every restarted sitting would
  wait there; `run` warns once before the first start.
- `run` needs the `Stop`, `PostToolUse`, `PostToolUseFailure` and
  `PostToolBatch` hooks: install the CLI before the plugin update (section 1,
  step 2). Until both are current a helper's failed call, or one another
  PreToolUse hook blocked, stays open and holds the sitting.
- `agentik session report --chains` lists the chain's restart and stop lines.

## 5. The gate queue

A full gate can take an hour behind one lock (the TLC lock is a directory with
a pid file). `agentik session gate` queues gate commands: one runs at a time
per state root, so one per Mac unless `XDG_STATE_HOME` differs, each in its
repo as argv under the environment `run` saw.

```bash
agentik session gate run . --lock <tlc-lock-dir> --label "land s38" -- make check
# queued <id> position 1 repo <realpath> caller <sid-short>; result <state>/gate/<id>/result.json
agentik session gate wait <id> --timeout 6000     # in a background Bash
agentik session gate status                       # running, queued, the last five done, the runner
```

- The caller is `--session SID`, else `$CLAUDE_CODE_SESSION_ID`, else none.
  Its result reaches that session two ways: `gate wait <id>` in a background
  Bash with a timeout past the gate's length prints `gate <id> <repo>: exit
  <code> in <m> min; log <path>`, and the UserPromptSubmit and PostToolUse
  hooks print the same line at the next prompt or tool call (main thread only,
  at most three, then `<n> more: agentik session gate status`).
- The Bash tool's background tasks die when their session respawns: list each
  open gate id in the state file's `## Gates` section, and the successor
  re-arms `gate wait <id>` from there.
- `--lock PATH` (repeatable) holds the entry while PATH exists; a younger entry
  with no lock may run first. `--wall SECONDS` cuts the command (default
  `gate.wall`, 5400). `--wait` waits after queueing.
- Exit codes. `wait` exits 0 whatever the gate's code, 2 for an unknown id, 1
  past `--timeout`. A result holds the command's own code, or 124 (the wall cut
  its process group, SIGTERM then SIGKILL), 125 (its runner died; the next
  runner killed the group), 126 (a lock held past the wall; never run) or 127
  (it could not start).
- ntfy: with `gate: {ntfy_url: <url>, ntfy_topic: <topic>}` in
  `~/.claude/agentik/profiles.yaml` the runner POSTs each result line to
  `<url>/<topic>`, `Title: gate <repo>: exit <code>`; a failure is one line in
  `runner.log`. The runner reads that user layer alone, since it serves every
  repo.

The runner (`gate serve`, internal) is spawned detached by `run`, `wait` and
`status` while the queue is not empty, and exits after 60 s idle. The state,
under `<state>` (`${XDG_STATE_HOME:-~/.local/state}/agentik-session`, or
`claude-code-session` there when only that pre-rename folder exists):

| path | what |
|---|---|
| `gate/queue/<id>.json` | an entry: id, repo, command, env, locks, wall, label, caller, queued (0600) |
| `gate/queue.lock`, `gate/counter` | the id's counter, taken under flock |
| `gate/runner.lock`, `gate/runner.json` | the one runner's flock; its pid, since, running, pgid |
| `gate/runner.log` | the runner's stdout and stderr |
| `gate/<id>/log`, `gate/<id>/result.json` | the command's output; its result, written last, pruned after 14 days |
| `sessions/<sid>/inbox/<id>.json` | the caller's message; a hook moves it to `inbox/read/` |
