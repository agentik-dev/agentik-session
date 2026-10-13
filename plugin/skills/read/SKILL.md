---
name: read
description: Read a markdown record by sections, never whole. Use before opening any design record, packet, charter or long markdown file; prints the section map, or the named sections under a read cap.
argument-hint: <file> [SPEC]
allowed-tools:
  - Bash(${CLAUDE_PLUGIN_ROOT}/scripts/record *)
---

# read

Reading is spend. A long record is served by sections through the plugin's
`record` tool, and the asking is visible in the transcript.

Arguments: `$ARGUMENTS` is `<file> [SPEC]`.

- **No SPEC:** print the map and stop. Do not read further in this turn;
  pick the sections the task needs from the map.

  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/record <file> --sections
  ```

- **With SPEC** (an index `24`, a list `3,5`, a range `3-5`, or a heading
  prefix in quotes `'§24'`):

  ```bash
  ${CLAUDE_PLUGIN_ROOT}/scripts/record <file> --section '<SPEC>'
  ```

Exits: 0 served; 2 no section named, no match, or an ambiguous prefix (the
candidates are named: pick one by index); 3 a section is over the 8 KB cap:
the refusal names its subsections, so ask for those instead. Pass `--force`
only when the task needs the whole section and the user or packet says so.

Never fall back to reading the whole file (no `Read` of the record, no `cat`),
even when the tool refuses. `--json` gives the same output for scripts.
