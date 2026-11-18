---
description: "List the session profiles, or show one resolved for this repo"
argument-hint: "[name]"
allowed-tools: [Bash(agentik-session *)]
---

!`agentik-session profile $ARGUMENTS`

With no name, the output lists the profiles (frontier, balanced, local,
local-only, scratch, review, packets, builder, orchestrator,
orchestrator-opus, starter) with their one-line descriptions, and marks the
default: `starter` runs when nothing names a profile; naming `frontier` under
`defaults.profile` in the user file takes up the sitting discipline. With a name, it is that profile resolved for this repo: the
model, subagents, posture, ceilings, charter directory and the dependent
plugins' sections. A profile is chosen at launch (`agentik session start
<profile>`); this command only shows it. Summarise what differs from the
current session if the user is choosing one.
