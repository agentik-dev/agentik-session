# claude-code-session: the successor starts itself (respawn r1)

**Status:** design r1, 2026-10-10, docs only. Its one refuter round (portfolio entry 15) gave VERDICT BLOCK at 304a1e7, and this revision folds that round's three findings and four notes: F1 in §3.1 and §8, F2 in §3.2 and §3.4, F3 in §3.3 and §3.9, N4 in §3.3, N5 in §3.1, N6 in §3.5, N7 in §3.2. Inputs: `OPEN-QUESTIONS.md` question 1, answered 2026-10-10 by the owner in the observer session ("the successor starts itself"); the question as asked (3221186); the portfolio ledger's entry 17 (example-ops `DECISIONS.md`); overhaul-r1 §1.2 (the retired chain), §2.2 (the meter and the ledger) and §2.3 (the state path); the code at main 461294c (`charter.py`, `cli.py` `cmd_checkpoint` and `cmd_start`, `launch.py` `exec_launch`, `hooks.py`, `ledger.py`); agent-relay's `internal/hooks/hooks.go` `inSitting`; and one real start line, the Start and Budget sections of example-mac's observer prompt (`history/sessions/PROMPT-2026-09-29-observer.md`).

The one-sentence design: `claude-session run -- <claude args>` runs an interactive `claude` in the owner's terminal under an id it chose. When that sitting's main thread marks a `RESPAWN:` charter with `claude-session checkpoint --respawn`, its turn ends, and nothing starts after, the launcher ends it and starts a fresh session with the same arguments. A daily cap, a floor and a stop file bound the chain, and every restart and every stop leaves a line in the ledger.

## §1 The problem

Today, at 80% of either ceiling, a sitting brings its charter current and writes a Next act that opens with `RESPAWN`. It deletes its loop, prints its start line and stops. The `claude` process then sits idle until the owner closes it, opens a new terminal and pastes the start line: a shell `cd`, then `CLAUDE_SESSION_PROFILE=<profile> claude --model '<model>'`, then a pasted first prompt such as `/loop 3h <read the prompt and the newest charter, and do its Next act>`.

The evidence (the observer's log of 2026-10-05, check-in 51): one repo's orchestrator reached its checkpoint at 00:04, 03:30 and 08:12. The owner restarted it at 01:57, 06:31 and 09:35. The gaps add up to 6 h 17 min (113, 181 and 83 minutes). Each restart went cleanly, because the successor read its charter and carried on. In the gaps nothing happened in the session: from 03:30 to 06:31 the relay night ran, but no review, merge or next night happened until the owner woke. The handover itself already works without the owner. Only the paste is manual, and the paste is what holds work overnight.

## §2 What this is not: the retired chain

overhaul-r1 §1.2 (D6) retired the fork-and-resume chain whole. This design shares none of its mechanism: no `--resume`, no `--fork-session`, no `-p`, no scheduler, no window arithmetic, nothing detached from the terminal. The four measured defects, against this design:

| retired defect (bugs/2026-09-12) | here |
|---|---|
| 1. the handoff ended the run with builders in flight | the launcher ends a sitting only when three things hold: the sitting's main thread has marked it ready (§3.2), the main thread's turn has ended, and nothing has started since (§3.3). The rule that every helper finishes before the RESPAWN close carries over (§3.9) |
| 2. a sensor that measured the UI | no sensor. The marker is a file the sitting writes, and the turn's end is a stamp from this plugin's own Stop hook |
| 3. `--fork-session` is not a resume | every start is a fresh session with a fresh id, and `run` passes no resume flag (§3.1) |
| 4. stale notices about "the last run" | each restart and each stop is a timestamped ledger line (§3.6). No banner exists |

## §3 The design

### §3.1 The command

`claude-session run [--chain NAME] [--cap N] [--floor S] [--settle S] -- <claude args>`

The owner's start line changes by one word. `CLAUDE_SESSION_PROFILE=orchestrator-opus claude --model 'opus[1m]'`, followed by a paste, becomes `CLAUDE_SESSION_PROFILE=orchestrator-opus claude-session run -- --model 'opus[1m]' '/loop 3h Run one observer check-in: …'`. The pasted first prompt becomes the last positional argument. Interactive `claude` takes a positional prompt as its first message, and P2 proves that a `/loop` there arms just as a paste does.

- **Each start** runs `claude --session-id <U> <claude args>`. `U` is a fresh uuid4 the launcher mints, and the owner's arguments follow in their original order, byte for byte, every time. The launcher re-sends the start line's own first prompt and adds nothing to it. The successor reads the newest charter because the start line already tells it to.
- **The environment** is the launcher's own, minus `exec_launch`'s scrub list (`CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_PID`, `CLAUDE_CODE_MESSAGING_TOKEN`, `CLAUDE_SESSION_MAX_TURNS`), plus `CLAUDE_SESSION_CHAIN=<chain>`. It sets no `CLAUDE_SESSION_DEPTH` and no `RELAY_ROW`.
  - agent-relay's hooks (`inSitting`) read a `CLAUDE_SESSION_DEPTH` of 1 or more as a relay sitting. A relay sitting's Stop hook blocks a stop on an uncommitted act. Without the variable, the relay's hooks see the child exactly as they see a hand-started session today, and never block its stops (F1).
  - `CLAUDE_SESSION_PROFILE` passes through untouched, so this plugin's hooks resolve the profile as they do today.
- **The chain** is named by `--chain`. The default is `<cwd basename>-<profile or none>`, limited to `[A-Za-z0-9._-]{1,64}`. Only one launcher runs a chain at a time: it holds a `flock` on `<state>/respawn/<chain>/lock` for its whole life.
- **Refusals before the first start**, each exiting 2 with one line:
  - stdin or stdout is not a TTY;
  - nesting, read from the launcher's own environment and never set by it: `CLAUDE_SESSION_CHAIN` is set (inside a chain), `CLAUDECODE` is set (inside any Claude Code session), or `CLAUDE_SESSION_DEPTH` is 1 or more, or unparsable (inside a started session or a relay child);
  - an argument that begins with `-` and is not on the flag allowlist, bare or as `--flag=value`;
  - no `claude` on PATH;
  - the chain's lock is held;
  - a bad chain name.
- **The flag allowlist** is `--model`, `--effort`, `--fallback-model`, `--permission-mode`, `--tools`, `--allowedTools`, `--allowed-tools`, `--disallowedTools`, `--disallowed-tools`, `--add-dir`, `--plugin-dir`, `--settings`, `--setting-sources`, `--mcp-config`, `--strict-mcp-config`, `--append-system-prompt`, `--system-prompt-snapshot`, `--name` and `--verbose`. It is an allowlist, not a denylist: the refuter found four resume-or-detach flags (`--from-pr`, `--teleport`, `--bg`/`--background` and `--tmux`/`-w`) that a denylist had missed, and `claude` gains flags faster than a denylist can follow them. A refused flag is named, and adding one is a one-line change with its test. The forbidden family can never join the list: `-p`, `--print`, `-c`, `--continue`, `-r`, `--resume`, `--fork-session`, `--session-id`, `--from-pr`, `--teleport`, `--bg`, `--background`, `--tmux` and `-w`.

`<state>` is the contract path, `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/` (overhaul-r1 §2.3, D9).

### §3.2 The marker: `checkpoint --respawn`

The launcher learns that a sitting ended on RESPAWN from a marker the sitting writes, never from the transcript. `claude-session checkpoint --respawn --charter FILE` first does what `checkpoint` does today: it resets the overlay's counter, prints the tree line, and commits when `--commit` is given. Then:

1. **`--charter` is required.** There is no default (N7). Today's newest charter by number would pick a relay row's charter over the orient one: in example-app on 2026-10-10 it returned `2026-10-10-10-example-row.md`, whose Next act is "None", over `2026-10-10-3-orient.md`. And a sitting that crosses midnight would have no charter for today at all.
2. **Only the `## Next act` section is read**, never `charter check`. A hand-kept charter whose shape `check` refuses, like the observer's, can still respawn. The section's first non-blank line must match `^RESPAWN(?=[:.\s]|$)`. The three spellings in use pass: `RESPAWN:`, `RESPAWN.` and `RESPAWN at 80% context.`. `Respawn:`, `RESPAWNED` and a `RESPAWN` later in the line do not.
3. **A refusal** exits 2, names the first 80 characters of the line it found, and writes nothing. `CLAUDE_SESSION_HELPER=1` is also refused, but that catches only a headless helper. An in-process Agent helper's Bash carries the sitting's own `CLAUDE_CODE_SESSION_ID` and no `CLAUDE_SESSION_HELPER`, as the refuter measured (F2). So the verb cannot tell such a helper from the main thread, but the hook in step 5 can.
4. **Otherwise** it writes `<state>/sessions/<sid>/respawn.json` atomically, with exactly `{session, charter, charter_sha256, written, chain}`. `sid` is `$CLAUDE_CODE_SESSION_ID`, `charter` is the absolute path, and `chain` comes from `CLAUDE_SESSION_CHAIN` or is null. Under a launcher it prints `respawn marked; the launcher restarts this sitting after this turn ends`. Without one it prints `respawn marked; no launcher runs this sitting: print your start line and stop`, which is today's path, unchanged.
5. **Only the main thread confirms.** The session's PostToolUse hook already returns at once on a payload that carries `agent_id`, which is a subagent's call. On a main-thread Bash call, it writes `<state>/sessions/<sid>/respawn-main.json` with `{at, marker_sha256}` when two things hold: the call's `tool_input.command` holds `claude-session checkpoint` and `--respawn`, and `respawn.json` was written at or after that call's own PreToolUse stamp (§3.3). The launcher accepts a marker only when `respawn-main.json` names the sha256 of the marker's current bytes. A helper that runs the verb writes a marker that no main-thread hook confirms.

The marker is the sitting's last act. Before it, the charter is current and committed, the loop is deleted, and every helper and background job has finished. Then the sitting ends its turn.

### §3.3 Ending the sitting

A sitting cannot end Claude Code itself: no tool exits the interactive session, so today it stops and idles. The launcher ends it instead, and only when it will restart it. Three hook stamps under `sessions/<U>/` tell it when the main thread's work has ended (F3). Each is written atomically, and only by a main-thread payload: a payload with `agent_id` writes nothing.

- **`activity.json`** (`{event, tool, at}`) is written by PreToolUse and UserPromptSubmit. Its matcher widens from the spawn tools to every tool. The spawn gate still acts on `Agent`, `Task` and `Workflow` only.
- **`turn-ended.json`** (`{at}`) is written by a new Stop hook at every main-thread turn end. Claude Code sends a helper's end to SubagentStop, which this plugin does not register. The hook never blocks: it exits 0 with empty stdout.
- **`respawn-main.json`** is written by PostToolUse, as described in §3.2.

The launcher's steps:

1. While its child runs, the launcher stats these files and the marker every 2 s.
2. When a confirmed marker appears, it runs checks (a) to (e) of §3.4. If any of them holds the sitting back, it records that reason and signals nothing. The sitting stays open exactly as it does today, and the chain stops when the sitting exits.
3. The sitting is **ready** when `turn-ended.json` is newer than the marker, and no `activity.json` is newer than that turn end. Both must stand unchanged for `settle` seconds (default 60). A new turn, tool or prompt starts the wait again. The cases it waits through:
   - the main thread's own long tool call: PreToolUse has stamped and the turn has not ended (the refuter measured Bash calls of 380, 394 and 602 s that wrote nothing);
   - an AskUserQuestion dialog waiting on the owner, which is a tool call too (measured at 6,543 s);
   - a background notice or a `/loop` fire that starts a new turn;
   - a Stop that another plugin's Stop hook blocks: the main thread continues, and its next tool or its next Stop stamps again inside `settle` (P7).
4. Right before the signal, it runs (a) to (e) and the ready condition again (N4). Any failure holds the sitting, so a stop file touched during the settle keeps the sitting open.
5. Then it sends SIGTERM to the child's pid. If the child is still alive 30 s later, it sends SIGKILL, and the restart line says `ended_by: kill`.

The launcher never opens a transcript and never stats one.

### §3.4 The decision

| at the child's exit | the launcher |
|---|---|
| no confirmed marker under `U` | stops (`no-marker`), with the child's status as its own |
| a marker, and the launcher ended the child | rechecks (b) and (c), then restarts after the grace |
| a marker, and the child exited 0 on its own (the owner's `/exit`) | runs checks (a) to (e), then restarts or stops |
| a marker, and the child ended non-zero or by a signal the launcher did not send | stops (`crash`) with the child's status, never restarting |
| a check held at the marker or before the signal | stops with that check's reason |
| the launcher took SIGHUP or SIGTERM | stops (`hangup`, `terminated`) |

The checks bind the marker to this sitting (F2):

- (a) the marker's `session` is `U`, and `respawn-main.json` confirms its current bytes (`not-main`);
- (b) the charter at the marker's path still opens its Next act on RESPAWN, read again at decision time, and its mtime is at or after this child's start (`not-respawn`). A predecessor's charter that was not touched in this sitting never respawns it;
- (c) no fresh stop file (`stop-file`);
- (d) the restarts in the past 24 h are below the cap, failing closed (`cap`, §3.5);
- (e) the sitting has run for at least `floor` seconds (`floor`).

**The grace.** After a child exits and before the next start there are 10 s of grace. The launcher prints one line: `<chain>: sitting <n> ended on RESPAWN (<charter>); restart <k> of <cap> in 24 h in 10 s; touch <state>/respawn/<chain>/STOP or press Ctrl-C to end the chain`. Ctrl-C during the grace ends the chain (`interrupted`).

**On every stop** it prints the reason and a start line that runs as printed: its own argv, re-quoted, with the `CLAUDE_SESSION_PROFILE=` prefix when that is set. It exits 0 when the last child exited 0 or was ended by the launcher. It exits with the child's own status after a crash, 2 on a refusal before the first start, and 1 on usage.

### §3.5 The guards: cap, floor, stop file

- **Cap** (default 12 in any rolling 24 h, per chain).
  - *How it counts.* The count comes from the ledger's restart lines for that chain.
  - *Why twelve.* On the measured night the sittings ran 3 h 34 min (20:30 to 00:04), 1 h 33 min (01:57 to 03:30) and 1 h 41 min (06:31 to 08:12). Once the gaps are gone, a busy orchestrator could restart up to about fifteen times a day. Twelve covers a night and most of a day before the owner's word is needed again. A slow runaway costs at most twelve sittings, and the floor catches a fast one. A cap of 0 means the chain never restarts, so `run` is then a plain wrapper.
  - *It fails closed (N6).* An unreadable ledger (any error but its absence) holds the chain at `cap`. A line that fails to parse but holds the chain's quoted name counts as a restart. The count is never below the launcher's own tally of the restarts it made in the past 24 h, so a deleted or truncated ledger never resets it. The restart line is written before the successor starts. If the write fails, no successor starts, the chain stops at `cap`, and the write's error is printed.
- **Floor** (default 600 s). A sitting that reaches RESPAWN in under ten minutes has done no work. The launcher holds such a sitting rather than delaying it, so a fault loop ends at its first sitting, not at the cap.
- **Stop file.** `<state>/respawn/STOP` ends every chain, and `<state>/respawn/<chain>/STOP` ends one. A stop file counts only when its mtime is at or after the chain's start. So `touch` is the whole verb, a stale file is harmless, and a chain started afterwards ignores it. The launcher never deletes a stop file. A fresh stop file means the launcher does not end the current sitting. The sitting runs on as it does today, and when it exits the chain stops.

### §3.6 The ledger

The ledger gets two new line kinds in `ledger.jsonl`. Each is a closed key set, and the writer refuses unknown keys in both, as it does for `LEDGER_KEYS`. Session lines do not change: they carry no `kind` key.

- **restart**: `kind, chain, seq, at, from_session, to_session, profile, repo, charter, charter_sha256, sitting_seconds, ended_by, restarts_24h, cap`. It is written before the successor starts (§3.5).
- **stop**: `kind, chain, at, session, profile, repo, reason, exit_status, sitting_seconds, restarts`.

By default `ledger.read` returns session lines only, so `report`'s table and `--json` output are byte-identical on a ledger that holds chain lines. `report --chains` prints the chain lines. No content reaches the ledger: the charter appears by path and hash, and its Next act's text never does. The SessionEnd line of the sitting that ended is written by the hook as it is today.

### §3.7 The terminal

The launcher is the shell's foreground job. Its child runs in the launcher's own process group with file descriptors 0 to 2 inherited: no `setsid`, no new process group, no pty of its own. So `claude` owns the same TTY and job control works as it does today.

- **Terminal attributes.** Before the first start, the launcher saves the terminal attributes of fd 0 (`termios.tcgetattr`). After every child exit it restores them, before it prints anything.
- **Ctrl-C and SIGQUIT.** While a child runs, SIGINT and SIGQUIT are caught by a handler that only records them. They are never set to `SIG_IGN`, because `exec` would pass an ignored signal on to `claude`. So `claude` gets Ctrl-C as it does today, and the launcher survives it.
- **Hang-up and termination.** On SIGHUP the launcher stops after the child exits and writes nothing more to the terminal. SIGTERM to the launcher is forwarded to the child, and the chain stops.
- **Silence.** The launcher writes nothing to the terminal while a child runs.

### §3.8 What it never does

- **It never compacts or resumes.** No argv it builds holds a flag outside its allowlist or `/compact`, and every start is a fresh context.
- **It never runs print mode.** `-p` is in the forbidden family (§3.1), so Claude Code 2.1.292's change (6 October 2026: a one-shot `claude -p` run now waits for its background commands rather than stopping them about 5 seconds after the final result; the changelog) does not touch the launcher. It touches the relay's `-p` children, whose design lives in the relay's repository.
- **It never poses as a relay sitting.** It never sets `CLAUDE_SESSION_DEPTH` or `RELAY_ROW`.
- **It restarts only on a confirmed RESPAWN.** It never restarts a sitting whose marker is missing or unconfirmed by the main thread, or whose Next act no longer opens on RESPAWN at decision time, or whose charter was not touched in this sitting.
- **It never restarts after a crash.** That covers a non-zero exit or a signal it did not send, and also a hang-up, and the case where the stop file, the cap or the floor holds.
- **It ends only a sitting it will restart.** It never ends a sitting while the main thread's turn is open. It never loops faster than the floor, and never restarts more often than the cap in 24 h.
- **It never leaves the owner's terminal.** It never runs headless (`-p`), never detaches (no `nohup`, tmux or launchd), and never schedules.
- **It never reads content.** It never reads or stats a transcript, never edits a charter, never commits, and never deletes a stop file.

### §3.9 What it cannot see

- **Work outside the main turn.** Background work can outlive the main thread's turn: Agent helpers run in the background, `run_in_background` jobs, and Monitors. The turn ends while they run. The marker is the sitting's word that none is in flight, which is the rule already kept at a RESPAWN close. A helper's report that wakes the main thread starts a new turn and stamps again, but one that finishes after the signal is lost.
- **The owner typing.** A prompt typed but not yet submitted fires no hook, so the launcher cannot see a draft (P6).
- **A `/clear`.** A `/clear` inside a sitting changes its session id, so its marker would land under an id the launcher did not mint. The chain then stops at that sitting's exit, which is the safe direction.

## §4 Configuration

`respawn: {cap: 12, floor: 600, settle: 60}` goes in `profiles.yaml` `defaults` and becomes a new `SESSION_KEYS` key. It layers like every other session key: the user's profiles, the repo's `config.yaml`, then `config.local.yaml`. `run --cap`, `--floor` and `--settle` are the invocation layer.

- **Validation.** A negative or non-integer value is a `ResolveError` (exit 2, the key named).
- **When it is resolved.** At the chain's start, from the launcher's cwd and `CLAUDE_SESSION_PROFILE`, and again before each restart, so a config edit takes effect at the next sitting.
- **Version.** The key, the Stop hook and the line kinds are additive, so the version moves to the next alpha (conventions §7). Dependents read only their own sections.

## §5 Where it lands (for the packet's drafter)

- **New files.** `claude_session/chain.py` holds the loop. Its effects (spawn, signal, clock, stat, termios) sit behind one small interface, so the table tests run on fakes.
- **Changed files:**
  - `launch.py`: the scrub becomes a shared function, used by both `exec_launch` and the chain.
  - `cli.py`: `run`, `checkpoint --respawn --charter` and `report --chains`.
  - `charter.py`: the Next act's first line, and the RESPAWN pattern.
  - `hooks.py`: the Stop handler, the activity stamps, and the PostToolUse confirmation.
  - `plugin/hooks/hooks.json`: Stop with a timeout, and PreToolUse on every tool.
  - `ledger.py`: the two line kinds, and a strict read for the cap.
  - `resolver.py`: `SESSION_KEYS`.
  - `profiles.yaml`.
  - `doctor.py`: `--session-id` goes in `CLAUDE_FLAGS`, and Stop goes in `HOOK_EVENTS`.
  - `plugin/commands/checkpoint.md`, and the session SKILL.md's CHECKPOINT and EXIT text.
  - `design/readme/source.md`, then `make readme`.
  - RUNBOOK §4.
- **Tests.** A new `tests/test_chain.py`, with additions to `test_charter.py`, `test_ledger.py`, `test_hooks.py` and `test_cli.py`.
- **Packets.** One packet, or two (the marker, the hooks and the ledger kinds, then the launcher). The drafter decides.

## §6 Acceptance criteria

Each criterion is one or more named tests on the fake `claude` (conventions §4). The fake reads a plan from its environment. It drives the hooks as a sitting would, by running `claude-session hook <event>` with a stdin payload, with or without `agent_id`. It can run the verb, idle, ignore SIGTERM, change the tty's attributes, or exit with a given status. It records its argv, its environment, its signal dispositions and the signals it received.

1. **The refusals of §3.1.** Each exits 2 with one stderr line naming it, and the fake records no start. Each member of the forbidden family is refused, and a test asserts that none of them is on the allowlist.
2. **The same arguments every time.** Across three starts the recorded argv is `--session-id <U_n>` followed by the owner's arguments in their original order, byte-equal each time. The `U_n` are distinct uuid4s. The environment has `CLAUDE_SESSION_CHAIN=<chain>` and the given `CLAUDE_SESSION_PROFILE`. It has none of the scrubbed keys, no `CLAUDE_SESSION_DEPTH` and no `RELAY_ROW`.
3. **The marker check.** `checkpoint --respawn` without `--charter` exits 2 naming it. With `--charter F`, it writes `respawn.json` with exactly its five keys when F's Next act opens on `RESPAWN: x`, `RESPAWN. x` or `RESPAWN at 80%`. It exits 2 and writes nothing for `Respawn: x`, `RESPAWNED`, `Next: RESPAWN`, an empty Next act, a charter with no `## Next act`, or `CLAUDE_SESSION_HELPER=1`. A charter that `charter check` refuses, but whose Next act opens on RESPAWN, is accepted.
4. **Only the main thread confirms.** PostToolUse writes `respawn-main.json` with the marker's sha256 for a main-thread Bash call that holds `claude-session checkpoint --respawn`, when the marker was written at or after that call's PreToolUse stamp. It writes nothing for the same payload with an `agent_id`, for a Bash call without the verb, or for a marker older than the call's PreToolUse stamp.
5. **A restart.** The fake runs PreToolUse, then the verb, then PostToolUse, then Stop, and idles. The launcher signals it after `settle` and starts a second fake after the grace. It writes one restart line before that start: `seq` 1, `from_session` U1, `to_session` U2, `ended_by` `launcher`.
6. **No marker, no restart.** A fake that exits 0 with no confirmed marker leaves a stop line with reason `no-marker` and a launcher exit of 0. The same fake exiting 3 makes the launcher exit 3.
7. **A crash is never restarted.** A fake that marks, confirms and then exits 7 on its own leaves a stop line with reason `crash` and a launcher exit of 7.
8. **The marker is bound to this sitting.** None of these is ever signalled:
   - a marker confirmed only through a payload with `agent_id` stops at `not-main`;
   - a marker whose charter's mtime precedes the child's start stops at `not-respawn`;
   - a fake that marks and then rewrites its Next act to `Done.` stops at `not-respawn`.
9. **It waits for the turn.** The launcher sends no signal in each of these cases:
   - while `activity.json` is newer than `turn-ended.json`: a PreToolUse with no Stop for an hour of fake clock (a long Bash, an AskUserQuestion);
   - when a Stop is followed within `settle` by a UserPromptSubmit or a PreToolUse.

   It signals within `settle` plus one poll after a Stop with nothing after it. Hook payloads with `agent_id` write no stamp. The Stop hook always exits 0 with empty stdout.
10. **A held guard ends nothing, and is checked again before the signal.** With a fresh per-chain STOP, a fresh global STOP, the cap reached, or a sitting younger than the floor, the fake receives no signal. At its own exit the chain stops with `stop-file`, `cap` or `floor`. A STOP touched during the settle prevents the signal. A STOP older than the chain's start is ignored, and every STOP still exists after the run.
11. **The cap counts the ledger, and fails closed.**
    - With cap 2 and two restart lines for this chain inside the past 24 h, plus one older line and two lines for another chain, the next sitting is held at `cap`.
    - With cap 0 the chain never restarts.
    - An unreadable ledger holds at `cap`.
    - An unparsable line holding the chain's name counts as a restart.
    - A ledger deleted mid-chain still counts the launcher's own restarts.
    - A failed restart-line write starts no successor and stops the chain at `cap`.
12. **Escalation to SIGKILL.** A fake that ignores SIGTERM is killed after the kill grace, and its restart line says `ended_by: kill`.
13. **The ledger's line kinds.** Restart and stop lines carry exactly their key sets, and the writer refuses an unknown key in each. `report` and `report --json` are byte-identical with and without chain lines, and `report --chains` lists the chain lines. A unique token placed in a charter's Next act appears nowhere in `ledger.jsonl`.
14. **The terminal.** These run under `pty.fork`. A fake that sets raw mode and exits finds the attributes restored before the launcher's next line. The fake reports SIGINT at its default disposition. SIGINT to the group while the child runs leaves the launcher alive. SIGINT in the grace stops the chain with `interrupted` and starts nothing. SIGHUP stops with `hangup` after the child exits.
15. **It never compacts or resumes.** Across a three-restart chain, every recorded argument that begins with `-` is on the allowlist, and none holds `/compact`.
16. **The printed start line runs as printed.** The start line printed at a stop, run with the fake on PATH, starts the same arguments.
17. **The configuration resolves.** `respawn` resolves from the defaults (12, 600, 60), and each layer and flag overrides the one below. A negative or non-integer value exits 2 naming the key.
18. **The doctor and the hooks.** `doctor` checks `--session-id` in `claude --help` and goes red without it. `hooks.json` registers Stop with a timeout and PreToolUse on every tool, and `test_every_hook_command_has_its_events_timeout` covers Stop.

## §7 Proofs owed

These are measured on the installed `claude` by an attended sitting or by the owner, never by the suite, which spends no quota. P1, P2, P4 and P5 come before a packet is cut, because the design changes if any of them is false. P3, P6 and P7 come before the first unattended night.

- **P1. The session id is honoured.** An interactive `claude --session-id <uuid>` uses that id: the SessionStart payload's `session_id` and `$CLAUDE_CODE_SESSION_ID` in a Bash tool both equal it. The flag exists, as the refuter found in `claude --help`.
- **P2. A positional `/loop` arms.** A positional `'/loop 3h <line>'` given to interactive `claude` arms the loop as a paste does: `CronList` shows it.
- **P3. SIGTERM ends it cleanly.** SIGTERM to an idle interactive `claude` ends it within 30 s, fires SessionEnd (the session's ledger line is written), restores the terminal, and leaves no child process (MCP server, background shell) behind.
- **P4. The hooks tell the main thread apart.** Stop fires at each main-thread turn end and never for an in-process helper, which gets SubagentStop. PreToolUse, PostToolUse and UserPromptSubmit payloads from an in-process helper carry `agent_id`.
- **P5. PostToolUse sees the command.** A PostToolUse payload for Bash carries `tool_input.command` as the command ran.
- **P1 and P2, measured 2026-10-10** (claude 2.1.296): both hold. P1: `claude -p --session-id <U>` wrote its transcript as `<U>.jsonl`, and the SessionStart hook made this plugin's `sessions/<U>/`. `$CLAUDE_CODE_SESSION_ID` equals the session id in an interactive sitting. The headless Bash `echo` of it was refused by Claude Code's permission check on a variable, so the interactive reading stands in for it. P2: the owner started an interactive `claude` with the positional `'/loop 30m …'`. It arrived as the session's first prompt, armed a 30-minute job (CronCreate) and ran at once. A `/loop` of 60 minutes or more would first ask its cloud-or-session question (NICE_TO_HAVE).
- **P4 and P5, measured 2026-10-10** (claude 2.1.296, one headless run in a scratch project whose hooks logged each payload; one Agent helper and the main thread each ran one Bash `echo`): both hold. The helper's PreToolUse and PostToolUse carried `agent_id` and the main thread's carried none; the helper ended with SubagentStop carrying `agent_id`; Stop carried none; each Bash PostToolUse carried `tool_input.command`. The main thread's Stop also fired while the helper was still running, before the helper's Bash, as §3.9 says.
- **P6. Owner typing.** No hook fires while the owner types a prompt before Enter, so the launcher cannot see a draft, and a draft is lost at the signal. Measure whether any file Claude Code writes shows a draft. Until then the record claims nothing about typing: an owner at the terminal who wants the sitting kept touches the stop file first. This is unproven and owed.
- **P7. A blocked Stop.** When another plugin's Stop hook blocks a stop, this plugin's Stop hook still stamps, because the hooks run side by side. Measure that the main thread's continuation stamps again (its first tool, or its next Stop) inside `settle`. The doctor names every enabled plugin that registers a Stop hook.

## §8 Owed elsewhere

- **The portfolio ledger.** Entry 17's clause "it respawns and never compacts" is today carried out by the owner's paste. That clause is amended to name the session plugin's launcher, its daily cap and its stop file. example-ops's own sitting enters the amendment there, because entry 16 says a decision that binds more than one repo lives in that ledger. This record does not draft it.
- **The start lines.** Each prompt that prints a start line for the owner (example-mac's observer prompt, and example-app's orient prompt) changes in its own repo, after this ships. Its Start section takes the `claude-session run` form. Its Budget step "print the start lines and stop" becomes "run `claude-session checkpoint --respawn --charter <file>` and end the turn".
- **The relay.** It is untouched. Its hooks see the child exactly as they see a hand-started session today, because the launcher sets no `CLAUDE_SESSION_DEPTH` and no `RELAY_ROW` (F1). Its children are headless, and `run` passes no resume flag, so a `relay resume` line is never chained.

## §9 Choices made inside the owner's answer (for the refuter)

- **C1. Who ends the sitting.** The launcher sends SIGTERM to its own child, because a sitting cannot leave the interactive session itself. It does so only after the main thread's turn has ended and nothing has started since (§3.3).
- **C2. How a RESPAWN exit is detected.** By a marker that `checkpoint --respawn` writes after checking the Next act. The main thread's PostToolUse confirms it, and it is keyed by the session id the launcher minted. The charter must be touched in this sitting, and the launcher reads the Next act again before signalling. It never parses a transcript (§3.2, §3.4).
- **C3. The cap.** It is 12 per chain in any rolling 24 h, counted from the ledger and failing closed. A calendar day would allow twice the cap across midnight (§3.5).
- **C4. The floor holds rather than delays.** A sitting that reaches RESPAWN in under 600 s ends the chain at its exit (§3.5).
- **C5. The stop file.** There is a global path and a per-chain path. A stop file counts by its mtime against the chain's start and is never deleted (§3.5).
- **C6. Degrade to today.** Any check that holds the sitting leaves it open for the owner, as it is today, and the launcher ends only a sitting it will restart (§3.3).
- **C7. The grace.** 10 s of grace before each restart, in which Ctrl-C ends the chain (§3.4).
- **C8. A stop line.** The chain's end gets a ledger line beside the restart lines, so a stop overnight is readable without the terminal (§3.6).
- **C9. One launcher per chain.** A `flock` enforces it, so two orchestrators never run one chain (§3.1).
- **C10. Allow claude flags, do not deny them.** The launcher passes only an allowlist of `claude` flags, so a new resume or detach flag is refused until someone adds it (§3.1).
- **C11. Nesting is read, never set.** The launcher detects nesting from `CLAUDE_SESSION_CHAIN`, `CLAUDECODE` and `CLAUDE_SESSION_DEPTH`, and exports only `CLAUDE_SESSION_CHAIN` (§3.1).
