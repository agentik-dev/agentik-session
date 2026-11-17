# Packet su3-start-check: SessionStart says a declared watcher that is not running

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief su3-start-check, rulings R1 to R7; hq design/18 §3.2 item 7 and §11's R1-F5, R1-F7, R1-F8, R1-F14; this repo's entry 12 |
| pin | `accf29f` on main (gl2-gate-list's merge). Worktree `.claude/worktrees/su3-start-check`, branch `su3-start-check`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no `claude` started by a test; no relay verb; no test reads the live state, the live user file or runs the live launcher (a stub in a temp `HOME`); `lineguard.py` and `tests/test_rp7_guard.py` untouched (another row's); `DECISIONS.md` unchanged |
| may touch | `plugin/lib/claude_session/hooks.py`, `tests/test_su3_start_check.py` (new), `NICE_TO_HAVE.md` (the four rows below), this packet, `history/sittings/2026-11-17-10-su3-start-check.md`; the version, the README's count, the sidecar and `history/NICE-overflow.md` by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_su3_start_check.py tests/test_hook_session_start.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `accf29f`)

The owner, asked where a declared watcher's absence is said without being asked: "At session start: one line when a session starts, only while something is missing, on your screen and to the sitting, which can act on it."

The ledger, entry 12, carried verbatim: **A declared watcher that is not running is said at session start.** Where a watcher the user file declares is not running, a session says so when it starts: one line, printed only while something declared is missing, on the person's screen and to the session itself, which can act on it. When every declared watcher runs, nothing is printed. The prompt band carries no mark for it. Cited: hq entry 6 (the plugin repos' build conventions), hq entry 37 (made-up names in fixtures and in this packet).

Measured at the pin, the fixture's payload in a temp `HOME` with a stub `agentik-suite` that records its argv, prints one line and exits 1: the hook's output holds the line nowhere and the stub records no call. `session_start` runs no child.

What `MAX_OUT` (640) bounds at SessionStart today: nothing. It caps PostToolUse's whole output, UserPromptSubmit's inbox block alone, and `_checkpoint_out`; no road of `session_start` reads it, and `dispatch` prints the handler's dict as it is. The fixture's SessionStart output is 849 bytes (frontier, its `additionalContext` 765), and 758 to 768 under `builder`, `orchestrator` and `frontier` as launch profiles: past 640 already. Design/18 item 7's "under the hook's one cap (`MAX_OUT`)" names a cap the code does not apply at this event.

The guards' write that R5 puts first (design/20's `guards.json`) is not in the code at the pin: no road writes it, so the watcher's line is SessionStart's first addition.

## 2. Rulings

- R1, the call: at SessionStart the hook runs `$HOME/.local/bin/agentik-suite status --check`, the launcher at its fixed place, never the door and never a PATH lookup, with no shell, under a wall of 2 s. A `HOME` that is unset or not absolute is no call.
- R2, the reading: exit 1 with text on stdout is lines to show; exit 0 is nothing to say; every other outcome is silence and never a failed hook: any other exit (2, 3, 126, 127), a missing or unrunnable file, a wall cut (the child is killed and reaped), exit 1 with empty stdout, bytes that are not text. Its stderr is never shown.
- R3, the share: one line. The first line of stdout whole, and ` and N more: agentik status` after it when stdout holds N more lines. A control character in it is taken out, as the hook does for its other words.
- R4, where it goes: to the owner's screen by `systemMessage` and to the session by `additionalContext`, each as the hook sends its own today, on every `session_start_reason`. The line stands before the hook's own start line in the context, so a cap cuts the plugin's words before the fault; the watcher's line is never the part dropped. Where the hook's start fails (the `{}` and the unknown-profile roads), the watcher's line is still said.
- R5, the order: the guard's own write first where the code has one (none at the pin), then this line, then the inbox's lines when they are built (in3, not this row).
- R6, who runs it: the main thread's start alone. A helper's start (`CLAUDE_SESSION_HELPER=1`, or a payload with an `agent_id`) makes no call.
- R7, nothing else: no new setting, no new file, no cache of the answer, no change to another event's output. The band above the prompt carries no mark for it.

As built: since `MAX_OUT` bounds no SessionStart output today, the plugin's own words stay uncut (R7 and the common brief: today's behaviour where a ruling does not name it). The watcher's share carries its own bound: it is cut at the end of its first line so that an output holding the share alone in `additionalContext` fits `MAX_OUT`, as UserPromptSubmit bounds its inbox block alone; the ` and N more` tail is kept.

## 3. Interfaces and acceptance

- `hooks.WATCH_WALL = 2.0`; `hooks.watcher_share(payload, env) -> str | None`, the one line or None, which never raises. `hooks.session_start(payload, env=None)` keeps its signature; its body at the pin is `hooks._start`. No other interface moves.

| # | line | at the pin |
|---|---|---|
| 1 | a stub at `$HOME/.local/bin/agentik-suite` in a temp `HOME` that prints one line and exits 1: the output holds it in `systemMessage` and first in `additionalContext`; with three lines, the first and ` and 2 more: agentik status` | absent |
| 2 | the stub exiting 0, 2, 3, 126 or 127, absent, not executable, printing nothing with exit 1, bytes that are not UTF-8, or sleeping past the wall: the output byte for byte the stubless one, the CLI exits 0, the sleeping stub gone when the hook returns, within 3 s | held |
| 3 | the stub records its argv: `status --check` alone; a helper's start (either mark) records no call | no call |
| 4 | a 600-byte first line: the watcher's line whole or cut at its end, never absent, on the `{}` and unknown-profile roads too | absent |
| 5 | every test the repo held before unchanged and green; `make check` once through the gate queue, green | green |

That the two channels reach a screen and a model is the owner's look after the install, not this row's: no test starts a `claude` process.

## 4. Findings that name this row

None at the pin. Four leads from the guard table's last review ride this packet as NICE rows (the issue rule's wrappers, `agentik $T issue send`, four harmless wrong refusals, a word split by quotes); this row fixes none.

## 5. Forbidden reads

The wall's: the live state, the live user file, the real home and the live launcher (each probe in a temp home with a stub).

## 6. Report

The sitting's record, `history/sittings/2026-11-17-10-su3-start-check.md`: the choices inside the rulings are in its handover.
