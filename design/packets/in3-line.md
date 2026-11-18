# Packet in3-line: `line send`, `list`, `show`, `close`, and the take in three hooks

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief in3-line, rulings R1 to R9; hq design/17 §3 items 7 to 10, §5, §10's R1-F7, R1-F9, R1-F11, R1-F13; hq entries 6 and 37 |
| pin | `69d0824` on main (plugin 2.0.0-alpha.137). Worktree `.claude/worktrees/in3-line`, branch `in3-line`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no `claude` started by a test; no relay verb; no test reads or writes the live state root or sends to a real checkout; the repo's ledger unchanged |
| may touch | `plugin/lib/claude_session/lines.py` (new), `hooks.py` (`_gate_lines`, `_gate_ups`, `post_tool_use`, `session_start`, a block after `_with_gate`), `cli.py` (the `line` parser and `cmd_line`), `gate.py` (`_prune` calls the lines' prune), `tests/test_in3_line.py` and `tests/fixtures/in3-baseline.json` (new), this packet, `history/sittings/2026-11-17-12-in3-line.md`; the version, the README's count and the sidecar by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_in3_line.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says

At the pin no hook reads a line; the gate's inbox is taken at UserPromptSubmit and PostToolUse (`_gate_lines`, three results and `n more` under `MAX_OUT`, 640), and SessionStart puts the watcher's line first (packet su3).

### The owner's words and the ledger

Asked how a line crosses from one tree's sitting to another's: "The sitting sends it."

Carried verbatim, the entries that bind a hook's output at a session's start:

> 10. **A machine with no user file runs the starter profile.** With no user file the plugin runs the `starter` profile, its shipped default: the meter on, no charter asked, and no priority or pacing text. A first session on a new machine is told nothing of the sitting discipline, which a person takes up by naming the `frontier` profile in the user file.

> 12. **A declared watcher that is not running is said at session start.** Where a watcher the user file declares is not running, a session says so when it starts: one line, printed only while something declared is missing, on the person's screen and to the session itself, which can act on it. When every declared watcher runs, nothing is printed. The prompt band carries no mark for it.

No entry is written or amended. Cited: hq entry 6 (the plugin repos' build conventions), hq entry 37 (made-up names in fixtures and this packet).

## 2. Rulings

- R1, the send: `agentik session line send <checkout> --file <path>`. The address is the named checkout's top level by its real path; a path that is no checkout's top, or is a worktree of one, is exit 2 with the reason. The file is a file inside the sender's own checkout. The verb writes one pointer under the tool's state root, `lines/<address>/<id>.json`: the sender's checkout, the file's full path, and the text's first line. It prints the id. It changes no file of either checkout.
- R2, `line show <id>` prints one pointer whole with the file's path; `line list [--json]` prints the lines addressed to this checkout and the lines it sent, each with its state (waiting, taken, closed and how).
- R3, who takes: a session whose project directory (`CLAUDE_PROJECT_DIR`; the payload's `cwd` only where that is unset), by its real path, is the address's top level and not a worktree of it. Never a helper (a payload with `agent_id`, or `CLAUDE_SESSION_HELPER=1`), never a `claude -p` child. A session that has `cd`'d away still takes.
- R4, when: at UserPromptSubmit and PostToolUse, after the gate's lines, and at SessionStart, after the watcher's line and in `additionalContext`. A hook carries one line; a second waits for the next hook. While a line waits, 256 of the hook's 640 bytes are the line's, so that hook carries the line, one gate result and the gate's count of more; with no line waiting every output is byte for byte what it is at the pin.
- R5, the printed line, made by the take and never by the send: `line <id> from <repo> (another sitting's words, not the owner's): <head>; whole: agentik session line show <id>`. The take writes the label and the id itself, reads `from` as a checkout's name and nothing more, cuts the head to one line of 120 bytes with control bytes taken out, and sets aside, unprinted, a pointer whose fields are not a pointer's.
- R6, once: a line is taken by one session, by a step that two sessions in one checkout cannot both win. A taken line not yet closed is printed once more at the receiver's next SessionStart, and not again.
- R7, the close: `line close <id> --as done|declined|waits [--note T]` records the close on the pointer and sends one line back to the sender's checkout, taken there as any line. A close of a line not addressed to this checkout, or already closed, is exit 2.
- R8, the prune: closed pointers leave after 14 days, by the gate's prune pass; an open pointer never leaves.
- R9, nothing else: no new hook event, no network, no write outside the state root, no change to the gate's lines when no line waits.

Not built: `reply` and the inbox's answer verb; the intake file's form and status; any ledger amendment.

## 3. Interfaces and acceptance

The state, under the root: `lines/<name>-<hash16>/` per address (the checkout's name made safe, then the first 16 hex of the SHA-256 of its real path, case-folded where the volume folds case; the gate keys a repo by the device and inode of its common dir, which a move keeps, so it has no spelling to borrow). In it `<id>.json` waits; `taken/`, `again/` (printed again at a SessionStart), `closed/` and `aside/` hold the rest. A pointer: `id` (12 hex, its file's name), `from` and `to` (checkout tops), `file`, `head`, `sent`; `closes` on a line a close sent back; `taken`, `again` (`at`, `session`) and `closed` (`as`, `note`, `at`) as they happen. Each step is a rename, which one session wins.

The sign of a `claude -p` child: `CLAUDE_CODE_ENTRYPOINT` is `sdk-cli` (Claude Code sets it in print mode, rewriting an inherited `cli`), or `sdk-ts` or `sdk-py` under the Agent SDK; a hook inherits it. The take skips those three.

`line list --json`: `{"checkout": top, "to": [item], "sent": [item]}`, an item `{"id", "state", "from", "to", "file", "head", "sent", "closes", "taken", "closed": null or {"as", "note", "at"}}`, `state` one of `waiting`, `taken`, `closed as <how>`, `set aside` (a set-aside item holds `id` and `state` alone); `head` as the take prints it. The suite's inbox reads `questions`, `backlog` and `charter` and expects no `line` read: this is the shape a later commons row reads.

Baseline at `69d0824`: `tests/fixtures/in3-baseline.json`, the three hooks for a session at a temp checkout with zero, one and three gate results waiting, a line waiting for another checkout and one of its own closed (SessionStart 804 bytes each; UserPromptSubmit 2, 165, 327; PostToolUse 2, 160, 322).

| # | line | at the pin |
|---|---|---|
| 1 | a line sent to a temp checkout is printed once, in R5's words, at that checkout's session's next UserPromptSubmit, PostToolUse or SessionStart, whichever comes first, and `line list` there shows it taken | absent |
| 2 | a hand-written pointer holding a newline, control bytes, words forged as the owner's, or a `from` that is no checkout: one labelled line with none of them in it, or none; the pointer set aside | absent |
| 3 | a helper (each of the two marks), a `claude -p` child and a worktree's session take nothing; a session that has `cd`'d away takes; two sessions in one checkout: one prints it; a checkout moved to a new path takes nothing addressed to the old one | absent |
| 4 | a line beside three gate results: the line, one result and the count of more, the whole within 640 bytes; the next hook carries the rest | absent |
| 5 | with no line waiting: the three hooks' outputs are byte-equal to the pin's baseline | the baseline |
| 6 | at SessionStart with a stub launcher that exits 1 and a line waiting: the watcher's line first on both channels, then the line in `additionalContext`; with each absent, the other as it is alone | absent |
| 7 | a taken, unclosed line is printed once more at the next SessionStart and not at the one after | absent |
| 8 | `line close` in the receiver: the pointer reads closed, and the sender's session prints one line that says how; a closed pointer older than 14 days is pruned, an open one of any age is kept | absent |
| 9 | every test the repo held before: unchanged and green; the repo's `make check`, once through the gate queue, green | green |

## 4. Findings that name this row

None.

## 5. Forbidden reads

Another row's branch (`st1-starter`); the live state root; a relay ledger.

## 6. Report

The builder's record and hand-back to the coordinator.
