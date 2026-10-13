---
description: "Adjust one setting for this session only"
argument-hint: "<knob> <value> [--save]"
allowed-tools: [Bash(claude-session *)]
---

!`claude-session set $ARGUMENTS`

The output confirms the knob and its new value, and that this session's
resolved file was rewritten. It is session-only unless `--save` was given;
add `--save` only when the user says to keep it. A launch-time knob (model,
effort, tools, plugins) is not applied until the next start: the output names
the in-session equivalent (`/model`, `/effort`); offer to run it. An error
names the knobs that can be set; relay it.
