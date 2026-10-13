---
description: "Check the tool, the plugin, its hooks and its dependencies"
argument-hint: "[--json]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session doctor $ARGUMENTS`

Each output line is one check, in order, with ok or FAIL and a detail;
exit 2 means at least one failed, and the failing checks name the remedy.
Report the failing checks first, with their remedies, then the count that
passed. Do not attempt the remedies unless the user asks.
