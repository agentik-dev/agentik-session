---
name: night
description: The overnight loop's state and its morning report, read from the night's ledger. Use when the user asks how last night went or what runs now; it never starts a night.
allowed-tools:
  - Bash(agentik-session night *)
---

# night

`agentik session night run <repo>` drives one `claude -p` builder per row of
`<repo>/relay/queue.yaml`, lands each `merge-on-green` row through the gate
queue and stops at the queue's end, `--until`, `--max-rows`, a limit or the
owner's `stop` file. This skill only reads what it wrote.

Arguments: `$ARGUMENTS` is empty, or `report [--night ID]`.

- **Empty:** the newest night's rows by state, the running row and the stop.

  ```bash
  agentik-session night status
  ```

- **`report`:** the morning's markdown: landed, built, red (with each resume
  line), limited, refused and skipped rows, and the cost per row and in total.

  ```bash
  agentik-session night report [--night ID]
  ```

Print the output as it stands. Exit 2 on `report` names an unknown night: say
so. Never run `night run`: a night is the owner's to start, from a terminal.
