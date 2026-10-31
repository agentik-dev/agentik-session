---
description: "The ledger: one row per ended session"
argument-hint: "[--since YYYY-MM-DD] [--json] [--hooks]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session report $ARGUMENTS`

The output is a table, one row per session that ended, from the ledger the
SessionEnd hook appends: when it ended, the session, the project, turns,
tokens, the largest context, the zone at the end and the exit reason. "The
ledger is empty" means no session has ended with the plugin's hooks installed. Summarise the totals and the sessions
that ended in the reserve or exhausted zones.

With `--hooks` the output is this plugin's hooks instead, a row per event (count, p50, p95, nonzero
exits), then `claude_md_bytes`; another plugin's hooks are not in it. `--since` filters the ledger's rows only,
never the hook table, and the output says so.
