---
description: "List the session profiles, or show one resolved for this repo"
argument-hint: "[name]"
allowed-tools: [Bash(claude-session *)]
---

!`claude-session profile $ARGUMENTS`

With no name, the output lists the profiles (frontier, balanced, local,
local-only, scratch, review, packets, builder) with their one-line
descriptions. With a name, it is that profile resolved for this repo: the
model, subagents, posture, ceilings, charter directory and the dependent
plugins' sections. A profile is chosen at launch (`claude-session start
<profile>`); this command only shows it. Summarise what differs from the
current session if the user is choosing one.
