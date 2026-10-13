---
description: "The ledger: one row per ended session"
argument-hint: "[--since YYYY-MM-DD] [--json]"
allowed-tools: [Bash(claude-session *)]
---

!`claude-session report $ARGUMENTS`

The output is a table, one row per session that ended, from the ledger the
SessionEnd hook appends: when it ended, the session, the project, turns,
tokens, the largest context, the zone at the end and the exit reason. "The
ledger is empty" means no session has ended with the plugin's hooks installed. Summarise the totals and the sessions
that ended in the reserve or exhausted zones.
