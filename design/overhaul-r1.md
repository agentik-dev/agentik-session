# claude-code-session r2: the overhaul (r1 of the design)

**Status:** design r1, 2026-09-22, sitting 2026-09-22-1 (Fable), docs only. §2.7 and D15: the owner's addendum, sitting 2026-09-22-2. Inputs: the brief (example-ops `example-app-v2/design/context-budget/relay-driver-r0.md`, r0), the rulings R25-87, R25-90 and R25-91 quoted in it, the 2026-09-12 window's four measured defects (`bugs/2026-09-12-overnight-window.md`), the two research legs of this sitting (`design/research.md`), and the sibling designs (`claude-code-decisions/design/decisions-r1.md` §4 and §7, respeak's README, layering). Pins: this repo `758b03d` at open; decisions `7e34358`; respeak `55d8826`; example-app `e6d3d13` (read only).

The one-sentence design: claude-code-session becomes the plugin of plugins that binds a launch profile, meters one sitting against two ceilings, writes one resolved configuration file per session that the other plugins may read, and composes claude-code-decisions, claude-code-respeak and claude-code-agent-relay by `dependencies`; nothing depends on it, and it has no lane of its own.

## §1 What it was, what is retired, what stays

### §1.1 What it was (0.1.0, pin `758b03d`)

A stdlib python tool `claude-session` (package `claude_session/`, 15 test files, 184 tests green on main, a fake `claude` so the suite spends no quota) plus a root `SKILL.md` symlinked into `~/.claude/skills`. It is not a plugin: there is no `.claude-plugin/plugin.json`, no marketplace entry, no `hooks/hooks.json`; the hooks in `claude_session/hooks.py` (PreToolUse, UserPromptSubmit, SessionStart, SessionEnd) are wired by hand into `settings.json`. Four things it does:

1. **Configurations** (`frontier`, `balanced`, `local`, `local-only`, `scratch`, `review`): a launch posture applied only through per-session flags (`--model`, `--effort`, `--tools`, `--plugin-dir`, `--permission-mode`, `--setting-sources`, `--settings`, `--append-system-prompt`); nothing is written to `settings.json`; `--dry-run` prints the literal command.
2. **A session-scoped overlay** keyed by `$CLAUDE_CODE_SESSION_ID`: `claude-session set <knob> <value>` for this session, `--save` to promote; `config show` marks what the overlay shadows.
3. **Budget as a signal**: postures `off`, `signal` (default), `ask`, `deny`; zones with a checkpoint cadence that tightens toward a reserve (every 25 prompts with plenty left, every 3 in the reserve); a PreToolUse gate on subagent spawns near the reserve. The sensor was the statusline: one usage sample per render of the five-hour window.
4. **Scheduling into the next window**: `schedulers/launchd.py` and `schedulers/systemd.py` register a job that runs `claude -p --resume <id> --fork-session` when the window resets, with the handoff as the run's structured final output; `runner.py` executes it; `reset.py` computes the reset; a SessionStart notice reports the last run.

### §1.2 What is retired (D6, recommended: retire the chain whole)

The fork-and-resume chain, all of item 4, and the sensor of item 3. The 2026-09-12 window measured four defects and every one is structural, not a bug to fix:

| defect (bugs/2026-09-12) | why it is structural | what replaces it |
|---|---|---|
| 1. the scheduled resume ends the run with agents in flight: the handoff is the final output, emitting it completes `claude -p`, builders are killed mid-edit | a handoff cannot be both the last message and a wait on children; the process model has no "drain" | one packet, one fresh session, one commit per act; the relay gates the tree after exit (brief: the gate) |
| 2. no usage sample on the first prompt after an idle window roll: samples come only from statusline renders | a sensor that depends on rendering measures the UI, not the sitting | the meter reads the session's own transcript: the last `cache_read_input_tokens` and the assistant-message count, exact and always present (example-mac `sitting-meter`, the seed) |
| 3. `--fork-session` is not a resume: the job resumed `50a6c2aa`, the run reported `909fac9e`; the parent never sees the work, the fork queued its own follow-up | chaining sessions is the anti-pattern the brief names ("not `--resume` chaining; fresh context per sitting is the whole point") | the queue (`relay/queue.yaml`); `relay resume` is an intervention door, never a scheduler |
| 4. stale run notices (a 09-08 run announced on 09-11) | state about "the last run" belongs to a ledger with timestamps, not a SessionStart banner | the burn ledger, one line per sitting, and `report` |

Retired with it: the five-hour usage-window model as the primary budget (percent of the window used); the `budget` verb's window arithmetic; the "queue this for the next window" and "what did the scheduled run do?" skill triggers; `install-wrapper.sh` where it exists only to serve the scheduled job. The window is not the constraint that R25-87 measures; the sitting is: 180k context, 400 turns, the 200k window as the ceiling above them.

### §1.3 What stays

Profiles (the six, renamed from configurations, now the top-level object, §2.1); launch by flags only, nothing in `settings.json`, `--dry-run`; the session-scoped overlay and `--save`; budget as a signal with its four postures and the cadence that tightens by zone, now driven by the sitting's own two ceilings; the PreToolUse spawn gate under `ask` and `deny`; the stdlib rule (python 3.10+, no dependency, `#!/usr/bin/python3`); the fake-claude test suite and its 184 tests, minus the chain's.

## §2 The r2 design

### §2.1 Profiles are the top-level configuration

A profile is one named launch posture and everything the sitting is measured against. Shipped in the plugin as `profiles.yaml`; the six of §1.3 keep their names and gain the R25-87 rows. Every field has a default, so a profile may be three lines:

```yaml
profiles:
  frontier:
    model: opus            # --model
    effort: xhigh          # --effort
    subagents: opus        # the builders' model (D5: Opus builds)
    tools: null            # null = the launch's own roster; review: [Read, Glob, Grep]
    permission_mode: auto
    posture: signal        # off | signal | ask | deny  (§1.3)
    ceilings: {context: 180000, turns: 400}   # R25-87 (5)
    ceilings_1m: {context: 180000, turns: 400}   # on a 1M window; the model decides the window (amended 2026-09-28)
    checkpoint_at: 0.8     # the signal; 1.0 is the exit
    builders: {model: opus, max_concurrent: 3}
    push: never            # a guard, not a preference
    device: never          # or the owner's word, quoted verbatim
    charter: {dir: history/sittings, required: true}
    respeak: {narrative: tech}          # a section per dependent plugin, merged into its layer
    decisions: {}
    agent-relay: {enabled: auto}        # auto = on when doctor finds the binary
  packets: {model: fable, effort: xhigh, subagents: opus, posture: signal}   # writes packets and designs, never builds
  builder: {model: opus, effort: high, subagents: opus, posture: deny}      # what the relay spawns
```

Resolution order, lowest first: the plugin's `profiles.yaml`; the user's `~/.claude/claude-code-session/profiles.yaml`; the repo's `.claude/claude-code-session/config.yaml` (§3); the repo's `config.local.yaml` (gitignored); the launch profile (`claude-session start <profile>`); the session overlay (`claude-session set`, this session only); the invocation flag. The overlay sits above the profile because it happens later in time and today's tool already shadows this way (`config show` marks it). This differs from the brief's listing, which named the profile last; D7 puts it to the owner.

**Amended 2026-09-28: the window by model, the ceilings by role** (the owner, 2026-09-28; sitting 2026-09-28-1). A profile is a role. The model decides the window: a `models:` table in `profiles.yaml` maps a family to its window (fable and mythos 1M; opus 200k, `opus-1m` for Claude Code's `opus[1m]` 1M; sonnet and haiku 200k). The window is read from the transcript's `message.model` when that family has one window; Claude Code strips `[1m]` from the API model id, so a 1M Opus session reads `claude-opus-5-5` like a 200k one. For such a family, the window comes from the first model that names the same family: the SessionStart payload's `model` (the session's own, `[1m]` intact), then the profile's declared `model`, then `ANTHROPIC_MODEL` and the settings `model` key. With no model read yet, or one the table does not know, the first of those the table knows decides. The role decides the ceilings: `ceilings` on a 200k window, `ceilings_1m` on 1M. The rule: a user or project layer that sets `ceilings` (both windows) or `ceilings_1m` (1M) wins, field by field, the higher layer last; then the role's ceilings for the resolved window; then the shipped defaults; the launch's turn cap applies last, and the models table decides only the window. Every role ships 180k and 400 on both windows except `orchestrator` (fable) and `orchestrator-opus` (`opus[1m]`), which get 400k and 400 on 1M. `window` is no longer an input. The meter re-picks the window from the model it reads, and `meter.json` records `window_source` and `limits_source` (`role:orchestrator window:1000000`). Builders, helpers and relay children stay on the 200k window by design; an Opus session is on 1M only when the owner chose it. A helper (the helper rule's `CLAUDE_SESSION_HELPER=1`, §2.5) inherits the sitting's `CLAUDE_SESSION_PROFILE` and resolves as `builder` whatever it inherits, so it keeps 180k on either window (fix round F1, sitting 2026-09-28-2: `test_launch_profile_resolves_a_helper_as_a_builder`, `test_meter_a_helper_of_an_orchestrator_is_a_builder_on_1m`).

### §2.2 The token manager: one meter, two ceilings, a ledger

**One meter.** The plugin's PostToolUse hook, matcher every tool, is the only reader of the session's spend. It reads `transcript_path` from stdin (research §3: no hook carries usage; the transcript does), parses only the bytes appended since its last run (an offset kept in state), and writes `meter.json` for the session: `session_id, turns, context, ceilings, window, pct_context, pct_turns, zone, ts`. Definitions are burn-report's, stated once and shared by a test: a turn is one deduplicated assistant message (`requestId`, `message.id`); context is the last assistant message's `input + cache_creation + cache_read` tokens (occupancy, output excluded); only assistant lines are read (S4). The ceilings are the role's for the window the session's model runs on (§2.1, amended 2026-09-28: 180k and 400, or 400k and 400 for an orchestrator on 1M), the turn ceiling capped by `CLAUDE_SESSION_MAX_TURNS` when set (`start --max-turns` sets it; `ceilings_source` names which), never the row's argv alone (R6-18, E5). The statusline reads `meter.json` at zero context cost; `claude-session status` prints it; the relay reads the transcript with the same definitions and lands on the same numbers.

**When it speaks.** Under 80% of both ceilings the hook prints nothing (a line every tool is context spent on the meter). At the first crossing of `checkpoint_at` it emits one `additionalContext` line, the CHECKPOINT signal: the numbers, the charter path from §3, and the rule ("bring the charter current, commit, then exit"). Past 80% it repeats every tenth tool; past 100% it speaks on every tool with the exit rule ("land the act in flight at a checkpoint, then exit; respawn, never compact"). UserPromptSubmit adds the same one line to every prompt (a prompt is a turn anyway). Posture `off` silences all of it and still meters (S4); `ask` and `deny` keep the PreToolUse spawn gate of §1.3, now keyed on the same zones. A hook run with `agent_id` on stdin is a subagent's (research §3): it exits silently and writes nothing, so builders never touch the session's meter.

**The exit.** The meter never blocks: it exits 0 always, prints at most 400 bytes, and the model exits by the rule the profile carries. Under the relay the driver kills at the ceiling and records the reason; in a hand-run sitting the charter's exit line is the record.

**The ledger.** SessionEnd appends one line to `ledger.jsonl` in the state directory: burn-report's `per_session` fields (`session, project, turns, sidechain_turns, tokens, median_context, max_context`) plus `profile, model, repo, sha_at_end, dirty, started, ended, ceilings, zone_at_end, exit_reason` and `builders: [{agent, turns, tokens}]` read from the transcript's `subagents/` directory (research §3: undocumented, present on disk, 44 here; when absent the field is an empty list and the line says `builders_source: none`). `claude-session report [--since]` prints the ledger; the relay writes the same fields for the sittings it spawned, so `burn-report` and `relay report` disagree on nothing. The ledger holds no message content, ever.

### §2.3 The binding: the session as an optional provider

Every plugin resolves its own configuration; the session plugin resolves all of them once and offers the result. The contract:

- **Where.** `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/sessions/<session_id>/resolved.json` (and `.yaml` beside it for people). Not `CLAUDE_PLUGIN_DATA`: research §3 found no way for one plugin to find another's data directory, and the CLI runs outside hooks; a fixed path is the whole contract (D9). Hooks take `session_id` from stdin; skills and commands take `$CLAUDE_CODE_SESSION_ID`, which the current overlay already keys on (not in the docs leg's list; packet S3 verifies it before use).
- **When.** The SessionStart hook (every `session_start_reason`) resolves §2.1's layers and writes the file; `claude-session set` rewrites it; nothing else writes it. Idempotent: the same inputs give the same bytes.
- **What.** One section per plugin (`session, respeak, decisions, agent-relay`), each already merged from the layers that plugin's own resolver would read plus the profile's section, and a `provider` block: `{plugin: session, version, profile, resolved_at, inputs: [{path, sha256}]}`.
- **What a dependent does with it.** Its resolver checks the file for its `session_id`; if present and `provider.version` is inside the range it accepts, its own section becomes the override layer directly below its invocation and session toggles (for respeak: below `/respeak:off` and `--mode`); if absent, out of range or unparsable, it resolves exactly as it does today and says so once in its own `doctor`. It never writes the file and never resolves the session's layers itself. Respeak's "no resolved block, approximated from files" (the brief) becomes "resolved by session 2.0.0, profile frontier".
- **Without the session plugin.** Each dependent is complete: its own defaults, its own repo section (a dependent may read its section of `.claude/claude-code-session/config.yaml` directly, §3, so one file serves both worlds), its own checks, its own README. Nothing depends on the session (R25-91 (3)).

### §2.4 `doctor`

`claude-session doctor [--json]`, exit 0 green, 2 with the failing line named, 1 on usage. Checks, in order: `claude` on PATH and `--help` lists every flag a profile uses (`--model`, `--effort`, `--tools`, `--permission-mode`, `--max-turns`, `--max-budget-usd`, `--output-format`); python: the running interpreter, 3.11+ (the launcher runs it with `-P`), with the newest release from pyenv's local list, else a shipped tuple, as a suggestion only (R6-14); the state directory writable; the plugin enabled and each hook registered (`claude plugin list --json`); each dependency installed with a version inside the declared range; the profiles parse and every named profile resolves; for the current session, `resolved.json` exists and `meter.json` is fresh (a transcript was readable); the repo's `config.yaml` parses and names no unknown profile; `git` present, the tree's push guard installed when the profile says `push: never`; when `agent-relay.enabled` is `auto` or `on`, the `relay` binary and `tmux`; then each dependent's own doctor if it ships one, its output indented. Unknown is never a pass.

### §2.5 The plugin surface

The plugin lives in `plugin/` (conventions §1) and the tool on PATH (`make install`, `~/.local/bin/claude-session`); the plugin's hooks are one shim, `plugin/hooks/run <event>`, which execs `claude-session hook <event>` when found and otherwise exits 0 silently (doctor reports the gap). The surface:

| kind | items |
|---|---|
| hooks | SessionStart (the resolver; the charter reminder when `charter.required` and none is open today); PostToolUse (the meter); UserPromptSubmit (the budget line and the cadence nudge); PreToolUse (the spawn gate under `ask`/`deny`); SessionEnd (the ledger) |
| skill | `skills/session/SKILL.md`: profiles, `set`, budget, the charter; under 500 lines, allowed tools `Bash(claude-session *)` |
| commands | `/session:status`, `/session:profile <name>`, `/session:set <knob> <value>`, `/session:checkpoint`, `/session:doctor`, `/session:report`; each runs one verb, under thirty lines |
| agents | none: builders, adversary and attendant are agent-relay's; the renderer is respeak's |
| CLI | `claude-session {start, config, set, status, checkpoint, charter {open,check,close}, doctor, report, hook}`; `charter` ports example-ops's `charter-close` shape check (D10) |

Deny guards (push, amend, rebase, device verbs), the Stop guard on a dirty tree (in a sitting only: `RELAY_ROW` set, or `CLAUDE_SESSION_DEPTH` >= 1, which `start` always sets; the owner, 2026-09-24; not under `CLAUDE_SESSION_HELPER=1`), and packet injection are agent-relay's plugin (R25-90 layer 2), not the session's; the session's profile only states `push: never` and `device: never`, which the relay's guards read from the resolved file.

The helper rule, relay-r1 §10 at agent-relay b8d789b: "a helper a sitting spawns keeps `RELAY_ROW` and `CLAUDE_SESSION_MAX_TURNS`, runs in the foreground as `CLAUDE_SESSION_DEPTH=$((d+1)) CLAUDE_SESSION_HELPER=1 claude -p … --max-turns N`, and is refused past depth 2; Stop and `start.json` skip it; `DropSitting` is the relay's own helpers' alone". `scripts/readme-render` runs respeak's renderer so, with `--max-turns` on its runner's `claude -p`, and refuses past depth 2 in setup, before any write (exit 2): `test_renderer_runs_as_a_marked_helper`, `test_renderer_helper_refused_past_depth_2` (row s16-resync, 2026-09-24; it replaces s15b's `env -u` drop).

### §2.6 `dependencies` with version ranges

`plugin/.claude-plugin/plugin.json`:

```json
{ "name": "session", "version": "2.0.0",
  "dependencies": [
    {"name": "decisions",   "version": "^0.2", "marketplace": "claude-code-decisions"},
    {"name": "respeak",     "version": "^0.6", "marketplace": "respeak"},
    {"name": "agent-relay", "version": "^0.1", "marketplace": "agent-relay"} ] }
```

Research §3: dependencies auto-install and enable with the dependent, cannot be disabled while it is enabled, and a missing one disables the session plugin with `dependency-unsatisfied`; ranges are npm semver. Each repo keeps its own marketplace (as decisions and respeak do today), so the owner adds four marketplaces once and `doctor` checks all four are present (D11; the marketplace names are the repos' names, `claude-code-decisions` and `agent-relay`, except respeak's, which is `respeak` today and is the one exception the conventions list). The ranges are the contract: a dependent's breaking change bumps its major and the session's next release widens the range after its test suite passes against it. The relay dependency is declared even though `agent-relay.enabled: auto` may leave it idle: the plugin is small, the binary is what may be absent, and doctor tells the two apart.

### §2.7 `record`: the disciplined read, and its home (D15; the a2 packet's D8)

"Read the record" becomes a tool. The packet is written, example-ops `example-app-v2/design/context-budget/packets/a2-record-sections.md`, and is not rewritten here; its §3 is the contract and this section restates only the signatures. `record <file> --sections [--json]` prints the section map, one row per `#` heading at any level: index from 1, level, heading text, first line, bytes. `record <file> --section SPEC [--max-bytes B] [--force] [--json]` prints the named sections verbatim under one header line (file, section, bytes) and nothing else; SPEC is an index `24`, a list `3,5`, a range `3-5` or a quoted heading prefix `'§24'`, first match wins. Exit 0; 2 on usage, no section named, no match or ambiguity (the candidates named); 3 over the ceiling (default 8,192 bytes) unless `--force`. Read-only, `#!/usr/bin/python3`, stdlib, one file, imported by nothing, one test beside it. The skill `/<plugin>:read <file> [SPEC]` runs it, prints the map and stops when SPEC is absent, and never falls back to a whole-file read. R25-87 binds the caps the tool enforces; R25-91 (3) binds the shape: the tool ships in ONE plugin and works without the session, so a packet's `record` line runs in a hand sitting with no session plugin installed. Conventions §8 makes the line the only way a packet, a sitting prompt or a README cites a record.

**D15 the home of `record`** (the addendum and the a2 packet call it D8; D8 in §7 is plugin ids). One plugin ships the file; the other two cite the command by name and carry no copy.
- **claude-code-session, recommended.** Reading is spend and the session owns spend: `scripts/record` beside `scripts/hygiene`, on PATH as `record` via `make install`, the skill `/session:read`, usable with the session's hooks off. Consequence: decisions keeps `extract` for rulings only and ships no reader; agent-relay's packet template cites `record` lines and ships no reader, and its builders run them without the relay's plugin being the provider.
- **claude-code-decisions.** Generalises "extract instead of read" from rulings to any markdown record, one extractor for both; the skill is `/decisions:read`. Consequence: the session's skills and every relay packet name the decisions plugin for a design-record read, the coupling conventions §3 avoids; agent-relay ships no reader.
- **agent-relay.** Packets and builders are the readers, so the reader ships with them; the skill is `/agent-relay:read`. Consequence: every hand-run sitting needs the relay plugin installed before the relay binary exists (plan row 9 makes the plugin usable by hand first); the session's `/session:*` skills cite a command another plugin owns, and decisions keeps `extract` beside a second extractor.

Consumer: the a2 packet's builder (its wall and may-touch rows say "the ruled home" and hold under all three), conventions §8, plan row 13.

## §3 The per-repo file and the defaults

`.claude/claude-code-session/config.yaml`, one section per plugin, every key optional; a repo with no file gets exactly this:

```yaml
session:
  profile: frontier                    # what `claude-session start` launches here
  ceilings: {context: 180000, turns: 400}
  ceilings_1m: {context: 180000, turns: 400}
  checkpoint_at: 0.8
  builders: {model: opus, max_concurrent: 3}
  push: never
  device: never
  charter: {dir: history/sittings, required: true}
  verify: null                         # the repo's own line the relay runs after a merge, e.g. "make check"
respeak: {}                            # respeak's own keys, its schema
decisions: {dir: decisions}
agent-relay: {enabled: auto, queue: relay/queue.yaml, merge: merge-on-green}
```

`config.local.yaml` beside it is gitignored and layers above. Unknown keys are reported by `doctor` and ignored, never fatal, so a dependent may add keys before the session learns them. `device` accepts only `never` or a quoted string, which the relay's guard compares verbatim. The file is YAML by ruling (R25-90 (3)); the tool is stdlib, so it ships a strict-subset parser (mappings, scalars, flat lists, comments; a test corpus of accepted and refused documents), the subset respeak's own fallback parser reads when PyYAML is absent (`respeak-config.py`; D12). example-app's first file is three lines: `session: {profile: frontier, verify: make check}`, `agent-relay: {enabled: auto}`, and `device: never` stated although it is the default, because the rule deserves to be visible.

## §4 Provability and the checks

Tests are table-driven and stdlib (`unittest`, the fake `claude`); each invariant is a test, and where it can be, a runtime guard too:

| invariant | test | guard |
|---|---|---|
| layer precedence | fixtures for every layer pair, the resolved value named | the resolver writes `inputs` with hashes, so a wrong layer is visible |
| the meter's definitions equal burn-report's | one test parses the same fixture transcript with both and asserts equality of turns and context | the fields are named in `meter.json` |
| the meter never blocks and never floods | fixtures at 79%, 80%, 81%, 100%, an unreadable transcript, a subagent's stdin | exit 0 always; output capped at 400 bytes; silent under 80% |
| incremental parsing is exact | a transcript appended in three steps gives the same numbers as one parse | the offset is stored with the file's inode and size |
| the ledger schema | the line's keys are a superset of burn-report's `per_session` keys, asserted by importing both lists | the writer refuses an unknown key |
| the resolved file is a pure function of its inputs | resolve twice, byte-equal; change one input, the `inputs` hash changes | nothing else writes the path |
| doctor is honest | fake PATH without `claude`, a dependency out of range, a stale meter: each exits 2 with the line named | "unknown is never a pass" |
| the plugin is self-contained | a test walks `plugin/` and refuses any path that names a file outside it | `claude plugin validate plugin/` in `make check` |
| public hygiene | `scripts/hygiene` green on every tracked file (§5); `test_hygiene.py` `test_binary_scanned_for_home_over_printable_runs` (ADV10-8, -9) | runs in `make check`; nothing is pushed red; UTF-16 (a BOM, or NULs on 90% of the odd or even bytes) scans as text; a file over 4 MiB is its path only, counted `oversize` |
| start depth at least 1 and at most 1 | `test_launch.py` `test_start_always_opens_a_sitting` (unset, blank or 0 gives 1; `--nested` gives the parent's plus one; the `--dry-run` preview agrees, S15) and `test_nested_*`: depth 1 refused, `--nested` allows 2, a config cannot set it, an unparsable depth refused (ADV10-10) | `start` sets `CLAUDE_SESSION_DEPTH` past the scrub, exits 2 at 2 (`MAX_DEPTH`); set but not a count, `depth()` is None and `start` exits 2 |
| a hook outlives a gone interpreter | `test_install.py` `test_hook_runs_installed_code_not_cwd`, `test_dirty_package_refuses`, `test_reinstall_prunes_the_old_tree` (ADV10-5) | the launcher bakes the venv's link, never a `/Cellar/` target (refused); with `PYTHON` or `CODE` gone a hook says `run make install` once (a state-dir marker `make install` removes) and exits 0 |
| a null tree state is never read clean | `test_gitinfo.py` `test_unknown_*`: a timed-out or failed `git status` | `Baseline.dirty` None; checkpoint prints "tree state unknown"; the ledger's `dirty` null |
| hooks are time-bound | `test_doctor.py` `test_every_hook_command_has_its_events_timeout` | a `timeout` on every `hooks.json` entry (5 s, 10 SessionStart, 15 SessionEnd) |
| one gate per tree | `test_bounded.py` `test_lock_exclusive_under_takeover`, `test_live_holder_refuses_at_any_age` (ADV10-2) | `flock` on `.check.lock`, passed to the guardian: the kernel frees it when the group's last holder dies; no staleness, no takeover |
| no suite outlives its gate | `test_caller_group_sigkill_reaches_the_suite` (ADV10-1) | the lifeline: EOF on `bounded`'s pipe makes the guardian kill the command's group; members outlive the gate by at most the grace plus 1 s |
| the gate ends inside the relay's timeout | `test_wall_counts_the_load_wait`, `test_makefile_gate_is_bounded` | the wall counts from `bounded`'s start, the load wait included; `check` 840 s plus a 5 s grace inside 900; `validate` 60 s; `readme` 600 s (ADV10-6) |
| a refused gate is unrun, never red | `test_stop_line_names_the_reason` (ADV10-3) | the last stderr line `bounded: stop: lock\|load\|wall`; exits 2, 2, 124 |
| acceptance is targeted | `test_doclint.py` `test_suite_rule_sees_through_wrappers` (ADV10-4) | doclint refuses a whole-suite acceptance line (it fails closed since ADV11-4, S14); a packet outside GRANDFATHERED without a `verify` row is refused |
| the two linters agree by shape | `test_doclint.py` `test_acceptance_shape_refused` (one id per shape), `test_acceptance_shape_allowed`, `test_legacy_stems_need_no_verify`, `test_spent_skips_the_suite_rule` (S13) | doclint mirrors agent-relay's `packet.Unbounded` (a non-literal command word, a stdin shell, `claude`, `make` with no or a suite target) and its `legacy` and `spent` lists; a new Go refusal is copied here in the same round |
| a signal never waits under the main thread's lock | `test_bounded.py` `test_sigterm_without_wall_exits_143` (d12, S13) | `bounded`'s TERM, INT or HUP handler closes the lifeline and polls `waitpid(WNOHANG)` for the guardian (never `Popen.wait`, whose lock the main thread's blocking wait holds), SIGKILLs its group past the grace plus 1 s, and exits 128+signum without a traceback, wall or not |
| the suite never outlives `bounded` | `test_bounded.py` `test_stopped_guardian_does_not_leak_the_suite`, `test_bounded_refuses_nonfinite` (ADV11-1, -10, S14) | the guardian reports the command's pgid on a pipe; when the guardian does not finish, `cut` SIGKILLs that group, then the guardian's, and polls the group gone (2 s at most): once the pgid is reported, `bounded` never exits while the group lives, so the lock is never free beside a live suite; a `--wall` or `--load` that is not finite is a usage error |
| only the outermost stop reads unrun | `test_bounded.py` `test_nested_stop_line_is_not_the_gates` (ADV11-2, S14) | `bounded` puts `BOUNDED_DEPTH` (its own plus one) in its command's environment; above depth 0 its line is `bounded: nested stop: <why>`, so an inner wall under the gate is a plain red, never unrun |
| the suite rule fails closed | `test_doclint.py` `test_suite_rule_fails_closed` (one id per cell), `test_suite_rule_targeted_allowed` (ADV11-4, S14) | a simple command holding a runner word (`make`, `gmake`, `pytest`, `py.test`, `go`, `tox`, `nox`, `claude`, `relay`, a `python*` with `-m pytest` or `-m unittest`) is read from that word, so wrappers need no list, and passes only in a targeted shape: a test file below the tests root, `::`, a `-k` not empty and not `not`, a dotted unittest module, `go test <pkgs> -run <Name>`, `make -n`, or `make` of `MAKE_TARGETED` targets |
| the suite never reads `$HOME` | `test_config.py` `test_the_suite_runs_on_temp_roots`; conftest's sentinel | temp `HOME` and `XDG_STATE_HOME` per test; a poisoned `meter.json` byte-unchanged at teardown; the sentinel root removed at exit, so the suite leaves no temp root (ADV10-11 a) |

`make check` = `test` + `lint` (byte-compile) + `doclint` (conventions §5) + `hygiene` + `claude plugin validate plugin/`, under `scripts/bounded`. A packet's `verify` row is that gate line; its acceptance lines are targeted (a named test file, never a whole suite: doclint refuses one), and the relay's gate reruns both on the branch (R6 T1).

## §5 The public README via respeak, and the hygiene scan

**The README.** The repo keeps `design/readme/source.md`: the facts in the technical lane, terse, under 6 KB, no prose about the owner's other projects. `make readme` renders `README.md` from it through the respeak agent (`/respeak:respeak tech design/readme/source.md`, the plugin's own README pipeline, the same for the four plugins), and `make check` refuses a README older than its source. The README names its dependencies by plugin name and version range, and nothing else outside the repo. The old README's sections that describe the retired chain (`How it works` items on scheduling, `Commands` for the job) go with the chain; RUNBOOK §5 is deleted, not rewritten.

**The scan.** `scripts/hygiene` (stdlib python, one file, copied byte-identical into each of the four repos; the canonical copy is this repo's, its sha256 in conventions §6): over `git ls-files` only, six pattern groups from research §1 (home paths, LAN addresses, the owner's domains, private repo names, personal names, sibling project names), an allowlist `.hygiene-allow` of `path: group` lines (LICENSE and the author fields for names; plugin.json and README for the dependency names), exit 2 with counts per group and per file and no matched content, `--json` for the relay's gate, exit 0 green. It runs in `make check`, and R25-91 (4) is the rule it enforces: nothing is pushed until it is green, and the owner pushes. The scan is also how §6 was sized: the same groups, run on example-app, are the public-readiness backlog.

## §6 example-app public-readiness, sized and NOT done

From research §1 (example-app `e6d3d13`, 1,567 files, 25.2 MB). The module path `github.com/owner/example-app` accounts for 818 of the 880 name files and stays. What must move or change, by packet, none of it in this phase:

| packet | what | size (lines/files from the scan) | where it goes |
|---|---|---|---|
| V1 fixtures | the two production bundles from the NAS under `testdata/` (2 × 973 KB) and any other captured device output | 2 files, 1.9 MB | replaced by a generator or a scrubbed synthetic bundle in-repo; the originals to example-ops `example-app-v2/reference/` |
| V2 addresses | LAN addresses and the owner's domains in code defaults, tests and docs | 508/125 and 365/68 | code and tests: RFC 5737 and `example.invalid`; docs: example-ops wiki |
| V3 the private names | references to example-ops, example-mac, example-config and the others | 486/162 | the example-ops-specific docs (`docs/architecture.md` 174 KB, `design-*.md` 135 to 145 KB) move whole to example-ops `example-app-v2/`; example-app keeps a public architecture page |
| V4 example-ops terms | the NAS's model, example-ops, its API and admin-shell names, `NAS` in code and docs; `internal/hostmon/catalog.go` (141 KB) is the host catalog and stays as product, scrubbed of owner values | 1,755/426 | word by word: product terms stay (the NAS's host model is a product fact), owner terms move |
| V5 the scan and the file | `scripts/hygiene` in `make check` with example-app's allowlist; `.claude/claude-code-session/config.yaml` (§3); `verify: make check` | new | example-app adopts first (R25-91 (5)) |

Order: V5's scan first (it measures the rest), then V1 to V4 as Opus packets with the scan's counts as their acceptance lines, then the owner's push. Estimated four to six Opus sittings; the two docs moves are the bulk by bytes and the addresses the bulk by files. example-app is not touched in this phase; the counts above are the baseline its packets are gated against.

## §7 The decisions for the owner

All of D1 to D15 were ruled by 2026-09-23; the "Recommend" wording below is historical.

Each with its consumer and a recommendation; nothing is asked that nothing waits on.

- **D1 headless and streamed vs interactive.** Recommend headless (`claude -p --output-format stream-json`), `relay resume` as the door. Consumer: agent-relay design r1. Research §3 confirms the stream carries per-message usage and `parent_tool_use_id`, so the live line needs nothing more.
- **D2 the gate in the driver.** Recommend the driver: deterministic, zero tokens, one code path for `plan` and `run`. Consumer: agent-relay. The session plugin's `make check` is what the gate reruns.
- **D3 the repo name.** Closed by R25-91: `agent-relay`, plugin bundled under `plugin/`.
- **D4 the queue in the target repo** (`relay/queue.yaml`). Recommend yes; §3 names it in the repo file's `agent-relay` section.
- **D5 Opus builds, Fable writes packets.** Recommend yes; the `builder` and `packets` profiles of §2.1 encode it, and `claude-session start packets` is the only launch that picks Fable.
- **D6 retire the fork-and-resume chain.** Recommend retire whole, including the five-hour window sampler (§1.2), keeping profiles and budget-as-signal. Consumer: packet S2.
- **D7 the per-repo file's name and the layering.** Recommend `.claude/claude-code-session/config.yaml` plus `config.local.yaml` as ruled, with the layer order of §2.1: the session overlay above the launch profile (the brief listed the profile last; the overlay is later in time and today's `set` already shadows). Consumer: packet S3 and every dependent's resolver.
- **D8 plugin ids (new).** The ruled label `claude-code-agent-relay` reads as the repo-subtree name; the brief itself writes the skills as `/relay:*`. Recommend the short ids `session`, `decisions`, `respeak`, `agent-relay` as plugin.json names (decisions and respeak already are), the repos `claude-code-*` and `agent-relay`. Consumer: S3's dependencies block and the relay's plugin.json.
- **D9 the state path is the contract (new).** Recommend `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/` over `CLAUDE_PLUGIN_DATA`, because no plugin can find another's data directory (research §3). Consumer: every dependent's resolver.
- **D10 charter tooling moves into the session plugin (new).** Recommend `claude-session charter {open,check,close}` as the port of example-ops's `charter-close` and the §3.1 shape; example-ops keeps its script until S5 lands. Consumer: S5, and every repo that writes charters.
- **D11 one marketplace per repo (new).** Recommend yes, four `marketplace add` once, doctor checks them, against a fifth catalog repo; the marketplace name is the repo name, and respeak's (`respeak` today) is either renamed in R1 or listed as the exception. Recommend the exception: renaming churns `known_marketplaces.json` for nothing.
- **D12 the config format (new).** Recommend YAML as ruled, with a strict subset parser in the stdlib tool and a refusal on anything outside it (anchors, multi-line scalars, nested lists), against JSON. Consumer: S3.
- **D13 the meter's cadence (new).** Recommend silent under 80%, once at the crossing then every tenth tool, every tool past 100%, one line per prompt. Consumer: S4. The alternative, a line every tool, is the meter eating what it meters.
- **D14 decisions' `reference/` and `research/` leave the repo (new).** They carry 77 home-path lines and 520 example-app lines (research §1) and are not the plugin. Recommend moving them to example-ops `example-app-v2/reference/decisions/` in packet D0, before decisions goes public. Consumer: the decisions repo's hygiene green.
- **D15 the home of `record` (new; the addendum's and the a2 packet's D8).** Recommend claude-code-session, `scripts/record` and `/session:read`; the three candidates and the consequence for the other two plugins are §2.7. Consumer: the a2 packet's builder, conventions §8, plan row 13.

## §8 The measure

Cost is turns times context (the brief). Per deliverable, the number to print is `turns × median context`, read from the ledger (§2.2) for a plugin sitting and from `burn-report` for the rest. The targets, from this sitting's own reading and the burn-report of 2026-09-22:

| deliverable | today | target |
|---|---|---|
| a design sitting (Fable, this one): overhaul-r1, conventions, plan, four packets | 134k × 20 turns at the close reading, plus two Opus legs of 53k and 90k tokens | under 130k × 120 |
| a build packet (Opus, one sitting) | prototype rehearsal, sitting 1: not measured | under 100k × 80, the packet's budget row is the ceiling |
| a research leg (Opus subagent) | 53k and 90k tokens, 11 and 16 tools (the two legs) | under 100k tokens each |
| hand-written prompts per week | about one per sitting: the NEXT file, by hand | 0 once the queue runs (the template plus the next packet is the prompt) |
| the largest session's share of a week's burn | 37.6% (e679eb37, 11,744 turns, 211k median) | no sitting above the two ceilings, so no session above 5% |

The measure is printed by `claude-session report` per sitting and by `relay report` per night; a week's `burn-report` is the audit. The design is wrong if a session plugin sitting spends more than the work it manages.
