# agentik-session: what is settled about this tool alone

This file holds the decisions that bind agentik-session and no other repo. A decision that binds more than one repo of the suite lives in the suite's own ledger. It has no `Every session` section, so no `CLAUDE.md` is rendered from it; `agentik decisions show N` reads an entry.

## In force

### The verbs that write

8. **checkpoint --commit takes named paths only.** `agentik session checkpoint --commit` commits the paths named on its line and nothing else. With no path it refuses with exit 2 and names the form. No flag brings back the sweep of every tracked file, because several sittings write in one checkout and a sweep commits another's files. (2026-11-17; the owner's answer to decision 8, the owner's answer to hq's decision 40 on 2026-11-12, moved here by the owner's answer to hq's decision 43)

9. **set --save for a setting that is not a model tier.** A session setting that is not a model tier is kept by a hand edit of the user's profiles file. `agentik session set <key> <value> --save` writes a model tier alone, to the user's file or the repo's. For any other key it refuses with exit 2 and names the file and the block to edit, so no command an agent can run changes posture for later sessions. (2026-11-17; the owner's answer to decision 9, the owner's answer to hq's decision 41 on 2026-11-12, moved here by the owner's answer to hq's decision 43)

### The profiles

10. **A machine with no user file runs the starter profile.** With no user file the plugin runs the `starter` profile, its shipped default: the meter on, no charter asked, and no priority or pacing text. A first session on a new machine is told nothing of the sitting discipline, which a person takes up by naming the `frontier` profile in the user file. (2026-11-17; the owner's answer to decision 10, the owner's answer to hq's decision 52 on 2026-11-17)

### The refusals

11. **Three shell spellings are refused in every session.** The plugin's PreToolUse hook refuses four shell spellings in every session, on every install, with no entry of any repo arming them: `rm -r` on a bare variable, anywhere; `git init`, and a git identity being set, where the shell stands in a checkout and the line names no other place; and `agentik issue send` in a tool call, which a person types at a terminal, as the refusal says. A `cd` in the line is not trusted for `git init` or the identity. Each refusal names the safe spelling, so the hook refuses a spelling and never the act. (2026-11-17; amended 2026-11-22, the owner's answer to decision 14, the owner's answer on 2026-11-22, given in the hq sitting's one batch)

15. **A helper is never the wait.** Under the profile key `helpers.wait: refuse` the plugin refuses a helper's second wait on one gate job and a helper's `sleep` command of a minute or more, and its refusal says to queue the run, record its id and hand back. The shipped default allows both. (2026-11-22; the owner's answer to decision 15, the owner's answer on 2026-11-22, given in the hq sitting's one batch)

### The session's start

12. **A declared watcher that is not running is said at session start.** Where a watcher the user file declares is not running, a session says so when it starts: one line, printed only while something declared is missing, on the person's screen and to the session itself, which can act on it. When every declared watcher runs, nothing is printed. The prompt band carries no mark for it. (2026-11-17; the owner's answer to decision 12, the owner's answer to hq's decision 55 on 2026-11-17)

### The gate

13. **A gate job's result follows the chain.** A job queued by a chain's sitting or by its helper, through any verb, is addressed to the chain. Its line is taken by a sitting of that chain that has not closed, so a result that lands at or after a close reaches the successor. A job queued outside a chain is addressed to the session that queued it. A respawn never waits for a gate job. A helper's own wait on one holds a restart no longer than the ceiling. (2026-11-22; amended 2026-11-26, the owner's answer to decision 19, the owner's answer to hq question 83, given in hq sitting 2026-11-25-1's one batch)

17. **One check proves a landing.** A landing is proved by one green `make check` of the tree that lands, run by the gate's check function in that branch's worktree with main where the landing reads it: the landing's own run, or one kept for the same tree with no commit since but the landing's own. (2026-11-23; the owner's answer to decision 17, the owner's answer on 2026-11-22, given in the hq sitting's one batch)

### The helpers

16. **A sitting is told its room at each launch.** In a session whose profile asks the sitting discipline, before a helper starts, the plugin says how many points of context are left to the checkpoint once every helper out has handed back, and whether the new helper fits. It refuses only under the posture `deny`. (2026-11-22; the owner's answer to decision 16, the owner's word, given in the coordinating sitting's ask of 2026-11-22)

18. **A held respawn has a ceiling.** The launcher restarts a marked sitting once its helpers are quiet, and thirty minutes after the sitting's first confirmed mark whatever helper is still out (respawn.hold_max, 1800 seconds; 0 means none). A helper still working then loses the item it had not committed, and the successor reads its branch. (2026-11-26; the owner's answer to decision 18, the owner's answer to hq question 83, given in hq sitting 2026-11-25-1's one batch)

## Proposed

## Superseded
