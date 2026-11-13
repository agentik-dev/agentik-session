---
description: "Give the terminal the CLI: freeze this plugin's code and write the launcher"
argument-hint: "[--prefix DIR]"
allowed-tools: [Bash(*/bin/agentik-session install-cli*)]
---

!`${CLAUDE_PLUGIN_ROOT}/bin/agentik-session install-cli $ARGUMENTS`

The plugin's own launcher runs this, never one on PATH: the one on PATH may be the old one or
the broken one this repairs. It freezes the plugin's lib/ under the user's
.local/share/agentik-session/, writes .local/bin/agentik-session, the old name's link and,
where none or an older one is there, the agentik door (a newer or equal door, a link, or one
with no version to compare is left alone, the last two with a line), and prunes old trees no
live process names. Report the lines it printed, or its error and exit code. Do not retry unless the user asks.
