# Packet in3-line: `line send`, `list`, `show`, `close`, and the take in three hooks

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17: brief in3-line (R1 to R9) and its fix (C1 to C8); hq design/17 §3 items 7 to 10 and §10; hq entries 6 and 37 |
| pin | `69d0824` on main (plugin 2.0.0-alpha.137). Worktree `.claude/worktrees/in3-line`, branch `in3-line`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no `claude` started by a test; no relay verb; no test reads or writes the live state root or sends to a real checkout; the repo's ledger unchanged |
| may touch | `plugin/lib/claude_session/lines.py` (new), `NICE_TO_HAVE.md` and `.hygiene-allow` (fix 1's rows), `hooks.py` (`_gate_lines`, `_gate_ups`, `post_tool_use`, `session_start`, a block after `_with_gate`), `cli.py` (the `line` parser and `cmd_line`), `gate.py` (`_prune` calls the lines' prune), `tests/test_in3_line.py` and `tests/fixtures/in3-baseline.json` (new), this packet, `history/sittings/2026-11-17-12-in3-line.md`; the version, the README's count and the sidecar by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_in3_line.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says

At the pin no hook reads a line; the gate's inbox is taken at UserPromptSubmit and PostToolUse (`_gate_lines`, three results and `n more` under `MAX_OUT`, 640), and SessionStart puts the watcher's line first (packet su3).

### The owner's words and the ledger

Asked how a line crosses from one tree's sitting to another's: "The sitting sends it."

Carried verbatim, the entry that binds a hook's output at a session's start (entry 10 binds the profile's text, untouched here):

> 12. **A declared watcher that is not running is said at session start.** Where a watcher the user file declares is not running, a session says so when it starts: one line, printed only while something declared is missing, on the person's screen and to the session itself, which can act on it. When every declared watcher runs, nothing is printed. The prompt band carries no mark for it.

No entry is written or amended. Cited: hq entries 6 (build conventions) and 37 (made-up names).

## 2. Rulings

- R1: `line send <checkout> --file <path>` addresses a checkout's top by its real path (no top, or a worktree: exit 2 with the reason); the file is inside the sender's checkout; one pointer under the state root, `lines/<address>/<id>.json` (sender, file's path, first line); prints the id; changes no checkout file.
- R2: `line show <id>` prints a pointer whole; `line list [--json]` the lines to and from this checkout, each with its state (waiting, taken, closed and how).
- R3: a session takes when its project directory (`CLAUDE_PROJECT_DIR`, else the payload's `cwd`) is the address's top and no worktree; never a helper (`agent_id`, `CLAUDE_SESSION_HELPER=1`) or a `claude -p` child; a `cd` does not matter.
- R4: at UserPromptSubmit and PostToolUse after the gate's lines, at SessionStart after the watcher's line in `additionalContext`; one line a hook; while a line waits it has 256 of the 640 bytes (the line, one gate result, the count of more); with none, every output is the pin's.
- R5: the take makes `line <id> from <repo> (another sitting's words, not the owner's): <head>; whole: agentik session line show <id>`, `from` read as a name only, the head one line of 120 bytes without control bytes; a pointer whose fields are not a pointer's is set aside.
- R6: one session takes a line; a taken, unclosed line is printed once more at the next SessionStart, not again.
- R7: `line close <id> --as done|declined|waits [--note T]` records the close and sends one line back; not addressed here, or already closed: exit 2.
- R8: closed pointers leave after 14 days in the gate's prune pass; open ones never.
- R9: no new hook event, no network, no write outside the state root.

Not built: `reply`, the inbox's answer verb, the intake file's form, any ledger amendment.

## 3. Interfaces and acceptance

The state: `lines/<name>-<hash16>/` per address (the name made safe, then 16 hex of the SHA-256 of the real path, both folded where the volume folds case; the gate's repo key, device and inode, survives a move). `<id>.json` waits; `taken/`, `again/` (printed again), `closing/`, `closed/` and `aside/` hold the rest. A pointer: `id` (12 hex, its file's name), `from`, `to`, `file`, `head`, `sent`; `closes` on a line back; `closed` (`as`, `note`, `at`). The folder is the state (§4a, C4).

The `claude -p` sign: `CLAUDE_CODE_ENTRYPOINT` `sdk-cli` (print mode, rewriting an inherited `cli`; F8 in §4a), `sdk-ts` or `sdk-py` (the Agent SDK); the take skips them.

`line list --json`: `{"checkout": top, "to": [item], "sent": [item]}`, an item `{"id", "state", "from", "to", "file", "head", "sent", "closes", "closed": null or {"as", "note", "at"}}`, `state` one of `waiting`, `taken`, `closed as <how>`, `set aside` (a set-aside item holds `id` and `state` alone); `head` as the take prints it. The suite's inbox expects no `line` read: a later commons row reads this shape.

Baseline at `69d0824`: `tests/fixtures/in3-baseline.json`, the three hooks with zero, one and three gate results, a line for another checkout and one of the session's own closed.

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

## 4a. The fix of review 1

- C1 (F1, F2): the stored first line is cut to 512 UTF-8 bytes; a `--note` over 240 bytes or holding a break is exit 2. Each verb packs its bytes first and refuses past the 4096-byte read bound, nothing written.
- C2 (F3, F11): one cleaner takes out every character `splitlines` breaks on, every Cc, Cf and lone surrogate, for the id, the name, the head and the note; a checkout path holding one cannot send, a pointer naming one is set aside. The made line is checked whole last: more than one line, or over its share, and it is set aside.
- C3 (F4): a close records itself when `from` is no checkout, sends nothing back, says so in one line, exit 0.
- C4 (F5): a state change is one rename; nothing is written after it. A step reads, then claims by a rename (into `taken/`, `again/`). A close reads, packs the closed pointer with its record, claims into `closing/`, publishes its written temp by a rename into `closed/`, then removes the `closing/` copy. The take keeps no stamp, so `line list --json` has no `taken` field.
- C5 (F6): `to` and `from` compare by the box's key (folded where the volume folds case); the name printed is the folder's own spelling.
- C6 (F7, F9, F11): the prune skips a symlinked `lines/`, box or `closed/`; a hook sets aside 16 at most; `file` must be under `from` (under `to` for a line back).
- F10: acceptance 4's "whole" is the gate's block with the line, measured as the pin measures a block.
- F8, R3's gap: print mode rewrites an inherited entrypoint only when it is `cli`, so a `claude -p` child of a `claude-vscode`, `claude-desktop`, `local-agent`, `remote` or `mcp` session keeps that value and would take.

F1 to F6's payloads are `test_c1_*` to `test_c5_*`, red at `cd16ceb`; C6's are `test_c6_*`.

## 5. Forbidden reads

Another row's branch (`st1-starter`); the live state root; a relay ledger.

## 6. Report

The builder's record and hand-back to the coordinator.
