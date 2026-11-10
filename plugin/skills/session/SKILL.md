---
name: session
description: Session profiles, session-only settings, the sitting's budget (the meter, the zones, CHECKPOINT and EXIT) and the charter (open, check, close).
allowed-tools:
  - Bash(agentik-session *)
  - Read
---

# session

## Profiles

The user starts sessions from named profiles (`frontier`, `balanced`, `local`,
`local-only`, `scratch`, `review`, `packets`, `builder`). At SessionStart the
plugin resolves every layer (the shipped profiles, the user's, the repo's
`.claude/agentik/config.yaml` and `config.local.yaml`, the launch
profile, this session's overlay) into one file. Read it before assuming the
model, subagents, ceilings, posture or tool access:

```bash
agentik-session config show --resolved   # this session's resolved file, provider block first
agentik-session profile                  # the profiles; `profile <name>` shows one resolved here
```

A profile is chosen at launch (`agentik session start <profile>`); in a session,
`/session:profile` only shows them.

## Set

When the user asks to change something for the current session ("drop to
sonnet subagents", "stop nagging me about budget", "ask before spawning"), use:

```bash
agentik-session set <knob> <value>            # this session only; rewrites the resolved file
agentik-session set <knob> <value> --save     # only when they say to keep it
```

**Default to session-only. Add `--save` only when the user says to keep it.**
If the knob is launch-time (model, effort, tools, plugins, lane), a
session-only `set` is informational only: it is NOT applied by the next
`start`. The command prints the in-session equivalent (`/model`, `/effort`);
run that if they want it now, and use `--save` if they want the next `start`
to change. `posture` (`off`, `signal`, `ask`, `deny`) takes effect at once:
the spawn gate reads it from the resolved file.

**Fill is the owner's word alone.** `agentik session set fill <reset|opus>
[--until <zoned time>]` turns on fill (off-path S4 work that uses a window up)
for this session only, and only when the owner says so in this sitting: run it
from the main thread, never from a helper, on an orchestrator's 1M window
(`orchestrator` or `orchestrator-opus`). `opus` needs `--until` with its zone
(`2026-11-10T18:00-08:00`); `reset` alone ends at the week's reset, read from
this session's own seven-day reading, and a later `--until` is cut to it.
`--save`, `--config`, a helper, a relay child, another profile or a 200k window
is refused, and so is a session with no seven-day reading. The word lives in
this session's overlay with its end stamped beside it, is read again at every
read, and ends with the sitting; under `agentik session run` the launcher hands
it to the successor while its time is ahead. `agentik session set fill off`
drops it, the chain's copy first; it is never refused by the seat, only with
`--save`, `--config`, `--until` or no session. A write that fails takes back
what it can and exits 2 with one line saying what stands. `agentik session
rules` prints `fill: <word> to <Ddd HH:MM>` or `fill: off` last. Never put it in a memory, a ledger or a
charter.

## Budget

A sitting has two ceilings, context and turns. Claude Code's measured window decides
the window (the `models:` table only before the engine's first measure), and the
profile (the role) the ceilings within it: 180k context and 400 turns on
either window for every role but the orchestrators, which get 400k and 400 on a
1M window. A model change moves the window, the ceilings and ctx % at the engine's
next measure. A helper (`CLAUDE_SESSION_HELPER=1`) resolves as `builder` whatever
role it inherits, and keeps its 200k ceilings on either window.
`meter.json` names the source (`limits_source`, e.g.
`role:orchestrator window:1000000`). The **meter** is the PostToolUse hook: it reads the
transcript's new lines after every tool and writes `meter.json`, the used share
of each ceiling. `agentik-session status` prints it in one line
(`/session:status`); `agentik-session report` lists ended sessions from the
ledger (`/session:report`).

The used share, the larger of the two, sets the **zone**:

| zone | from | meaning |
|---|---|---|
| clear | 0% | work |
| notice | 80% | the checkpoint point: bring the charter current |
| wind-down | 90% | stop starting what you cannot finish |
| reserve | 92% | the wrap-up reserve: finish, commit, hand off |
| exhausted | 100% | exit |

Two lines arrive as hook context; act on them, do not argue with them:

- **`CHECKPOINT: ...`** at the profile's `checkpoint_at` (80% by default), then
  every tenth tool: bring the charter current, commit, and run
  `agentik-session checkpoint`. The session must be handed off at any moment
  from here. Under `agentik session run`, the sitting runs
  `agentik session checkpoint --respawn --charter <file> --state <s>` and ends the turn,
  and the launcher restarts it.
- **`EXIT: ...`** at or past 100%: land the act in flight at a checkpoint, then
  exit; respawn, never compact. A RESPAWN close (the charter's Next act opens on
  `RESPAWN`) is marked as the sitting's last act: once the charter is current and
  committed, the loop is deleted, and every helper and background job has finished,
  write the state file (a title line, then `## Helpers`, `## Gates`, `## Last acts`
  and `## Read first`, each bulleted or `- none`, under 8,192 bytes; see RUNBOOK
  "Restarting a sitting"), run `agentik-session checkpoint --respawn --charter <file>
  --state <s>` through Bash, then end the turn. The successor's SessionStart line
  names the copy: read it first, then the charter's Next act. Its last line says whether a launcher restarts the sitting; without one,
  print your start line and stop. When the restart does not come,
  `agentik session status` names the hold, `respawn held: <reason> since <HH:MM>`:
  a `floor` or a `cap` lifts with time, a `not-respawn` when the charter opens on
  `RESPAWN` again and the verb runs again; otherwise exit, and the chain stops.

The **posture** decides how loud the budget is. `off` says nothing (`scratch`,
`local-only`); `signal` (the default) speaks on the prompt and after tools and
never blocks; `ask` asks before an Agent, Task or Workflow spawn from the
wind-down zone on; `deny` also refuses such a spawn in the reserve (the
`builder` profile).

**When a `PreToolUse` hook blocks or questions a spawn with a budget reason, do
not retry it or work around it.** The remainder is reserved so that you can
finish cleanly: stop starting new work, commit what is in flight, and write the
handoff.

**The spawn rule** (packet wfg) holds whatever the posture, a helper's call too,
and denies before launch with one line, `Workflow denied before launch: lines
N: <reason>: <rewrite>`. Apply the rewrite and call again; never route around it.
- Every `agent(` names its model in its own options literal:
  `agent(prompt, { label: '...', model: 'opus' })`. No spread, name or helper's
  result; an unnamed agent would run on the session's model.
- A script starts 8 agents at most. A call counts once at the top level or in an
  `if` (both arms of a ternary), or in a callback given directly to `parallel(`,
  `pipeline(`, `.map(`, `.flatMap(` or `.then(`; a `.map(`, `.flatMap(` or
  `pipeline(` multiplies by its list, which must be an inline array, a top-level
  `const` array never changed, or `<list>.slice(0, N)`.
- Denied, with the rewrite: a call in a loop (unroll it, or map a literal list);
  in a named function or another call's callback (write it inline, or give the
  callback directly to `parallel(`); thunks kept in a name (build them inside the
  `parallel(`); a list known at run time (`.slice(0, N)`); `workflow(`, `eval(`,
  `Function(`, `import(`, `require(`, `globalThis` (inline the child's calls); the
  text `agent(` in a string or comment (reword it); a script the guard cannot read
  (simplify the quoting); no `script` and no readable `scriptPath` file (pass the
  script inline).
- Fable: an `Agent` or `Task` with a Fable `model`, or a script's Fable agent,
  starts only under a Fable session, as both `model.json` (SessionStart, then each
  `/model` switch) and the meter read it; else name `model: 'opus'`. In a script,
  a Fable agent needs a label that starts with `design` or `refut`, two at most.
  "Not known" (no record yet, or a switch one record has not seen) clears after
  one tool call.

## The charter

The charter is the sitting's live head: one file per sitting under the
profile's `charter.dir` (default `history/sittings`), named `<date>-<n>.md` (`<date>-<n>-$RELAY_ROW.md` when a relay row sets it).
When `charter.required` is true and none is open today, SessionStart says so:
open one before the first act.

```bash
agentik-session charter open "<goal>"          # writes <dir>/<today>-<n>.md, prints its path
agentik-session charter open --continue "<goal>"  # adopts today's newest of the suffix under 3,584 B, else as open
agentik-session charter check <file>...        # exit 2 names the part that fails, 1 the red
agentik-session charter close --exit "<text>"  # appends the exit line to this sitting's own charter; name the file when another sitting's is the newest, or two of its suffix stand with no record
```

The shape, and nothing else:

1. the title line `# Sitting <date>-<n>: <repo>, <component>`;
2. the table, with the rows goal, budget, pin, window, agents;
3. `## Done-ness`, a checklist whose first item is the charter itself;
4. `## Handover`, each decision for the owner in plain language with its
   consumer;
5. `## While waiting`, `open` writes `- none`; else up to three
   `- ready: <row> (<repo>, S<n>)` lines, off-path rows built without a gate,
   and `- owed: <item>; <what it needs>` lines, owed items that need no gate
   (a runsheet, a refuter round, a draft);
6. `## Next act`, one line.

A wait is legal when no S1 to S3 row is ready and nothing is owed: with a
ready row of S1 to S3 or an owed item there, the Next act is that item, and,
with `session.pacing` on, `check` exits 1 on a Next act of WAITING or STALLED
beside one, or beside a line of neither shape (`WAITING while ready: <the
line>`). S4 rows alone are no red: they run only while fill is on. A Next act
opening STALLED without its parts is the other red (`STALLED without its
parts`). A charter opened before 2.0.0-alpha.24 has no While waiting section; `check` passes it
and warns: add it with `- none`.

The file stays under 4,096 bytes: move text out, never widen the ceiling.
Bring it current at a CHECKPOINT line, when a wait starts or its line
changes, and at close. `close` appends
exactly one line under Handover, `- exit taken: <text>; about <context>
context, <turns> turns` from the meter, and refuses a charter that fails
`check` or would pass the ceiling.
The order at the end is close, commit the charter (`close` prints the line to
run as is, `next: git -C <dir> add -- <name> && git -C <dir> commit -m "charter:
the exit taken" -- <name>`, `<dir>` the charter's absolute directory), then, on
a RESPAWN close, the `then:` line it prints, `agentik-session checkpoint
--respawn --charter <file>`, which refuses (exit 2) a charter git reads as not
committed.

## Priority and pacing

Two session keys every sitting meets, both on in every shipped profile.
SessionStart prints one line of them; `agentik-session rules` prints both
whole, as resolved.

- `session.priority`: S1 harm, S2 blocks the goal, S3 the build order, S4 the
  rest. An item gets its level when filed, and the Next act is the highest
  level ready. A bug ranks by harm and what it blocks, never by how sure or
  cheap its fix is. Each Handover lists the open items by level, highest
  first: `charter open` writes `- open by level: none yet`. S4 is taken on
  an S3 slice's path, or while fill is on. Fill, off-path S4 work that uses
  a window up, is off unless the owner's word turns it on: the main thread,
  never a helper, runs `agentik session set fill <reset|opus> --until <zoned
  time>` on an orchestrator's 1M window (see Set); it ends then, never past
  the week's reset; no memory, ledger or charter turns it on or keeps it.
- `session.pacing`: the fallback wakeup rides the act's last tool call. A
  pending helper, Monitor or background task is the wake, with one fallback
  of `fallback` seconds (1800). Waiting on an outside party, the Next act
  says `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`,
  n the wakes in a row with nothing changed, est the blocker's own estimate
  (a time with its zone, or `none`). The wake, first that applies: est
  within 6 h, a wakeup at est, kept warm before it only on the 1h cache; by
  the owner, no wakeup; else no wakeup and one background task that ends at
  est (6 h on when est is none) or when the event's file moves. STALLED is
  said once, when a wait by the owner starts, when that task ends with
  nothing changed, or at n = `waiting` (3): the Next act becomes
  `STALLED: <what>; by <who>; since <when>` in a turn that ends on text with
  one PushNotification and no ScheduleWakeup, and after it no wakeup is
  armed. A wait never closes the sitting, only the checkpoint does. The
  charter is brought current when a wait starts or its line changes, never
  at each wake; a respawn reads n from the charter. A wait on the
  usage meter (room for 0, a usage limit hit, the week or the band) is not WAITING: the Next
  act stays the act, the wake is the band's reset or one fallback, whichever
  is first, and it never counts toward n.
- The prompt cache's lifetime sets how long an idle wait may be. On 1h (a
  subscription within plan usage) an idle wait wakes at most 3300 s apart, so
  the cache survives. On 5m (usage credits, an API key, a cloud provider, or
  `promptCacheTtl: 5m`) any wait past about 270 s misses anyway, so an idle
  wait takes the long fallback and never wakes early to keep the cache.
  `agentik-session rules` and the prompt line name the lifetime in force.
- A packet or brief bounds both: a builder files what lies outside it and
  takes none. No hook enforces them. `charter check` and `close` warn when
  the Handover line is missing, or a WAITING is misshapen, short of its
  `by` and `est`, or at `waiting` or past it, and their exit is unchanged
  except `check`'s on the two reds, a wait beside a due While waiting line
  and a STALLED without its parts, which exit 1.
- Any layer overrides them, never `set`: `priority: {enabled: false}`, one
  level's quoted text under `priority.levels`, `pacing: {fallback: 2400}`.

## Other verbs

```bash
agentik-session doctor          # the setup, the plugin, its dependencies; exit 2 names the failing check
agentik-session budget          # the zone and checkpoint cadence
agentik-session checkpoint      # mark a handoff-ready point (`-m`, `--commit` stages tracked files only)
agentik-session checkpoint --respawn --charter <file>   # mark a RESPAWN close, through Bash
agentik-session gate run <repo> [--lock PATH] -- <command>   # queue a gate; prints queued <id>, est on stderr
agentik-session gate wait <id> --timeout <s>   # its result line; run it in a background Bash
agentik-session gate wait <id> --strict        # the same, exiting the job's code
agentik-session gate status     # what runs, what waits (each with its est), the last five done
```

The gate queue runs one gate per repo (a repo and its worktrees are one) under a load
ceiling, and a lock path one running gate names holds every other gate that names it.
Its result reaches the caller two ways:
`gate wait <id>` in a background Bash with a timeout past the gate's length, or the
UserPromptSubmit and PostToolUse hooks' line at the next prompt or tool call. A respawn
kills background tasks: list each open gate id in the state file's `## Gates`, and the
successor re-arms `gate wait <id>`. `wait` exits 0 whatever the gate's code; 124 is the
wall's cut, 125 a runner that died, 126 a lock held past the wall. `gate wait <id> --strict`
exits the job's code (0 to 255, else 1); `wait`'s own 2 (no such id) and 1 (the timeout)
print nothing on stdout, so a line there marks the code as the job's. A result keeps the
repo's `head` (its commit before the start, or null) and `key` (a repo and its worktrees
are one). `run` says `est <m> min` on stderr, and `status` ends a line `; est <m> min`:
the median of the key's last five greens, none under three. A WAITING line's `est` on a
gate is worked from it: the gate's start, or now while it queues, plus `est <m> min`.

The band: the plugin's hooks module draws `session: <model> · <window> · ctx <c>% · turns <t>% · <zone>` above the prompt (e.g. `session: opus 5.5 · 1M · ctx 64% · turns 6% · clear`: the window the ceilings apply; `1M (engine 200k)` means the meter has not caught up with the engine's latest reading, and its next tool closes it; `status` prints the same as `model: …`, with the id and the window's source) and, at session start, runs `agentik-session mod start --session <id>` (it writes `mod.json`; `status` and `doctor` then print `mod: seen`, else `mod: not seen`).

Admission, in `observe` (it records and never refuses): the same module hands each session's start, rate-limit readings, helper spawns, SendMessage resumes, helper turns and end to `agentik-session admission record --session <id>` (one JSON object on stdin; exit 0, 2 refused, 3 the lock held past 2 s), one line each in the machine's `<state>/admission/ledger.jsonl` (rotated past 29 h to `ledger.1.jsonl`). An `end` marks that session's open spawns done (`swept`). No prompt or message text is sent; a failed record is one debug-log line.

Before each spawn and each SendMessage resume the module also runs `agentik-session admission admit --session <id>`, which projects the five-hour window's peak, appends one `verdict` line and prints `{verdict, mode, text, peak, window, resume_at}`. In `observe` (the only mode built; `session.admission` sets `ceiling`, `margin`, `ceiling_7d`, `seeds`, `window` and `windows`) the answer is one debug-log line and the spawn always goes ahead.

The window: `record` and `admit` rewrite `<state>/admission/band.json`, and the band draws it as a second line, `5h <P>% → <peak>% · ceiling <c> · resets <HH:MM> (<h>h<mm>) · <n> helpers, room for <r> · <d> deferred · 7d <P7>%` (then `observe`); the prompt hook adds the same line to the budget context. `Room for N` means N more helpers fit under the ceiling: pull work forward. `agentik-session report` ends with each five-hour window `held` or `idle`, `under 90` marked.

A login's window mode is read from its readings at every call: `five_hour` by default; `none` when, since its last list carrying a five-hour entry, one session shows the week up a whole point over at least 30 minutes with no five-hour entry. On `none` a verdict is `denied` at `ceiling_7d`, else `admitted`, and no band or peak applies; nothing waits for a band. band.json's entries carry `window` and `slot` (`Wed-1500Z`), and its top level is the current login. Override with `session.admission.window: auto | five_hour | none`, or `windows: {Wed-1500Z: none}` per login. A `none` login's band reads `no 5h window · 7d <P7>% · week resets <Ddd> <HH:MM> · band <name> to <HH:MM> · <n> helpers` (then `observe`), each part left out with no figure, and its prompt cache's lifetime reads the week: 1h under 100%, 5m at 100% or past. The demand band (`avoid`, `middle`, `good`, `best`) is a report and never a hold: quieter hours are preferred when work can move, and no verdict moves on one, attended or not. `status` shows it with the next good and best; the schedule is `agentik/session/bands.yaml` in the user's config directory, else the shipped one, and a bad file is a `doctor` warning.

The measure: the same module hands every `session.measure` (`{context, rateLimits, cost, changed}`) to `agentik-session measure record --session <id>` (exit 0, 1 no session, 2 refused, an unreadable window included), which writes `measure.json` and, when the window has moved, rewrites `resolved.json`; `status` prints `measure: engine <t> tokens / meter <c> tokens, drift <d>%` (or `not comparable`, or `none`) and `doctor` warns at 10%. Its `context.window` is the window pick's first source; its other figures decide nothing, and the budget never reads it.

Each has a command: `/session:status`, `/session:profile`, `/session:set`,
`/session:checkpoint`, `/session:doctor`, `/session:report`, `/session:gate`.
