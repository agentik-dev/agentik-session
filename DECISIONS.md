# agentik-session: what is settled about this tool alone

This file holds the decisions that bind agentik-session and no other repo. A decision that binds more than one repo of the suite lives in the suite's own ledger. It has no `Every session` section, so no `CLAUDE.md` is rendered from it; `agentik decisions show N` reads an entry.

## In force

### The verbs that write

8. **checkpoint --commit takes named paths only.** `agentik session checkpoint --commit` commits the paths named on its line and nothing else. With no path it refuses with exit 2 and names the form. No flag brings back the sweep of every tracked file, because several sittings write in one checkout and a sweep commits another's files. (2026-11-17; the owner's answer to decision 8, the owner's answer to hq's decision 40 on 2026-11-12, moved here by the owner's answer to hq's decision 43)

9. **set --save for a setting that is not a model tier.** A session setting that is not a model tier is kept by a hand edit of the user's profiles file. `agentik session set <key> <value> --save` writes a model tier alone, to the user's file or the repo's. For any other key it refuses with exit 2 and names the file and the block to edit, so no command an agent can run changes posture for later sessions. (2026-11-17; the owner's answer to decision 9, the owner's answer to hq's decision 41 on 2026-11-12, moved here by the owner's answer to hq's decision 43)

### The profiles

10. **A machine with no user file runs the starter profile.** With no user file the plugin runs the `starter` profile, its shipped default: the meter on, no charter asked, and no priority or pacing text. A first session on a new machine is told nothing of the sitting discipline, which a person takes up by naming the `frontier` profile in the user file. (2026-11-17; the owner's answer to decision 10, the owner's answer to hq's decision 52 on 2026-11-17)

### The refusals

11. **Three shell spellings are refused in every session.** The plugin's PreToolUse hook refuses three shell spellings in every session, on every install, with no entry of any repo arming them: `rm -r` on a bare variable, anywhere; `git init`, and a git identity being set, where the shell stands in a checkout and the line names no other place. A `cd` in the line is not trusted for the last two. Each refusal names the safe spelling, so the hook refuses a spelling and never the act. (2026-11-17; the owner's answer to decision 11, the owner's answer to hq's decision 53 on 2026-11-17)

### The session's start

12. **A declared watcher that is not running is said at session start.** Where a watcher the user file declares is not running, a session says so when it starts: one line, printed only while something declared is missing, on the person's screen and to the session itself, which can act on it. When every declared watcher runs, nothing is printed. The prompt band carries no mark for it. (2026-11-17; the owner's answer to decision 12, the owner's answer to hq's decision 55 on 2026-11-17)

## Proposed

13. **A gate job's result follows the chain.** Enter it: the behaviour is built, installed and relied on by every respawn, and an entry is what makes a later change to it a question for the owner. (proposed 2026-11-22; OPEN-QUESTIONS.md)

14. **Entry 11 names the fourth refusal.** Amend entry 11: the refusal is built and guards an act that publishes, and the entry is where a reader looks for what every session is refused. (proposed 2026-11-22; OPEN-QUESTIONS.md)

## Superseded
