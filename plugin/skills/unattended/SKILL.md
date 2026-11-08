---
name: unattended
description: The unattended loop's state and its report, read from the run's ledger. Use when the user asks how the last run went or what runs now; it never starts a run.
allowed-tools:
  - Bash(agentik-session unattended *)
---

# unattended

`agentik session unattended run <repo>` drives one `claude -p` builder per
row of `<repo>/relay/queue.yaml`, lands each `merge-on-green` row through the
gate queue and stops at the queue's end, `--until`, `--max-rows`, a limit or
the owner's `stop` file. This skill only reads what it wrote.

Arguments: `$ARGUMENTS` is empty, or `report [--run ID]`.

- **Empty:** the newest run's rows by state, the running row and the stop.

  ```bash
  agentik-session unattended status
  ```

- **`report`:** the run's markdown: landed, built, red (with each resume
  line), limited, refused and skipped rows, and the cost per row and in total.

  ```bash
  agentik-session unattended report [--run ID]
  ```

Print the output as it stands. Exit 2 on `report` names an unknown run: say
so. Never run `unattended run`: a run is the owner's to start, from a terminal.
