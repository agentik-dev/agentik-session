---
description: "Give the terminal the CLI: freeze this plugin's code and write the launcher"
argument-hint: "[--prefix DIR]"
allowed-tools: [Bash(*/bin/agentik-session install-cli*)]
---

!`${CLAUDE_PLUGIN_ROOT}/bin/agentik-session install-cli $ARGUMENTS`

The plugin's own launcher runs this, never one on PATH: the one on PATH may be the old one or
the broken one this repairs. It freezes the plugin's lib/ under
~/.local/share/agentik-session/, writes ~/.local/bin/agentik-session, the claude-session link
and the agentik door, and prunes old trees no live process names. Report the line it printed,
or its error and exit code. Do not retry unless the user asks.
