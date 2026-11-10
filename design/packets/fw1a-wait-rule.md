# Packet FW1a: the wait rule's text and the charter's reds

| item | value |
|---|---|
| from | hq `design/08-fill-wait-reconciler.md` §2 rows 1 to 5, §3 items 1 and 2, as folded; its refuter's A5, B2, B3, D1. No new key: `set fill` is FW1b |
| pin | agentik-session main **after S54 lands** (plugin 2.0.0-alpha.52); worktree `.claude/worktrees/fw1a-wait-rule`, branch `fw1a-wait-rule`, `.venv` and `.venv-floor` linked from the main checkout. Lines are cba0b70's: find by the quoted words |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude` but `make check`'s; no test writes under the live home; no relay verb; no gate verb under a temp HOME |
| may touch | `plugin/lib/claude_session/{rules.py,charter.py,cli.py,profiles.yaml}`; `plugin/skills/session/SKILL.md`; `RUNBOOK.md`; `README.md`, `design/readme/{source.md,rendered.sha256}`; `tests/test_{fw1a,rules,charter,hook_session_start}.py`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet as `design/packets/fw1a-wait-rule.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id>` in one background Bash; read the job's code from its line |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_fw1a.py`: T1 to T10 green (cba0b70: `20 failed, 3 passed`, all nine red, three control cases); R8's three files green; the verify row green |
| budget | a commit per group by explicit path, the packet and the charter's five doclint rows first; stop at 90 tool calls or 140k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

At cba0b70, read in its worktree `W` (`PYTHONPATH=W/plugin/lib /usr/bin/python3 -B`), `charter.warnings` over the charter of hq `history/sessions/DESIGN-08-scripts/r1-charter.py`. `WAITING 1: the owner's walk; sheet line 12 ticked` beside `- ready: n12 (agentik-session, S4)`, a ready S2 row or an owed line gives the red, `WAITING while ready: <line>; take it, since WAITING is legal only when ...`, exit 1. That line with `; by owner; est none`, `WAITING 2: x; y` and a bare `STALLED:` give exit 0, no warning. `rules.render({})` says "never stops the loop", "legal only when", "nothing ready", "none ready" and "brought current and committed" once each, never `STALLED` or `fill`.

## 2. Rulings

FULL is `WAITING <n>: <what>; <how to tell>; by <who>; est <zoned time|none>`; ST is `STALLED: <what>; by <who>; since <when>`.

- R1, the red. With a Next act opening WAITING or STALLED, `charter._red` names the first While waiting line that is `- ready:` at S1 to S3 or `- owed:`, ending `take it, since a wait is legal only when no S1 to S3 row is ready and nothing is owed`. Else the first line of neither shape, in today's words. S4 rows alone: no red.
- R2, the line. In FULL no part holds a `;`, and `est` is one token: `none`, or what `rules._zoned` reads. Today's shape short of FULL warns once, naming `; by <who>; est <zoned time|none>`; a bad token warns once, naming it; the misshapen line's warning names FULL. `waiting()` stands.
- R3, STALLED. `charter.stalled(line)`: True for ST, False for another line opening STALLED, else None. ST is a wait under R1. A misshapen one is a second red, `STALLED without its parts: the Next act is not 'ST'` (ST spelled out); `charter.REDS = (RED, STALLED_RED)`, which `cli._warn` (`cli.py:345`) tests. `close` still writes its line.
- R4. At n of `waiting` or more the line ends `say STALLED once, make the Next act 'ST' and arm no wakeup; the sitting stays open`.
- R5, item 4. `rules.PACE[3]`, to the byte, FULL and ST each in backticks, 1,044 characters: `waiting on an outside party: the Next act says FULL, n the wakes in a row with nothing changed, est the blocker's own estimate; a wait is legal when no S1 to S3 row is ready and nothing is owed, and While waiting's S4 rows run only while fill is on; the wake, first that applies: est within 6 h, a wakeup at est, kept warm before it only on the 1h cache (item 6); by the owner, no wakeup; else no wakeup and one background task that ends at est (6 h on when est is none) or when the event's file moves; STALLED is said once, when a wait by the owner starts, when that task ends with nothing changed, or at n = {waiting}: the Next act becomes ST in a turn that ends on text with one PushNotification and no ScheduleWakeup, and after it no wakeup is armed; a wait never closes the sitting, only the checkpoint does; the charter is brought current when a wait starts or its line changes, never at each wake (a respawn reads n from the charter)`. The 6 h is text, no setting (design/08 §10); FW3 names the task's verb; the old aside on ScheduleWakeup goes.
- R6. S4 (`rules.py:47-49`, `profiles.yaml:61`) ends `taken on an S3 slice's path, or while fill is on; never ahead of S3`. `BUGS[2]` opens `One S4 item a sitting at most off a slice's path, and only while fill is on;`. New `rules.FILL`, `render`'s last `  - ` line under priority: `fill, off-path S4 work that uses a window up, is off unless the owner's word in this sitting turns it on, and only for an orchestrator on a 1M window; no memory, ledger or charter turns it on`.
- R7. The clause's pacing part ends `a wait is said and cheap; fill off`: 276 bytes at the defaults.
- R8. An existing test is edited only where it pins replaced words or a fixture line short of FULL (it takes `; by owner; est none`). On the cutter's prototype 52 cases go red: `test_rules.py` 11, `test_charter.py` 34, `test_hook_session_start.py` 7; `test_readme.py`'s 2 wait on R9; eleven other modules none.
- R9. Last, as S54's R11: `2.0.0-alpha.53`, the status line, the sidecar.
- R10, docs. `SKILL.md:126-171`, `RUNBOOK.md:313-362`, `README.md:113` and its source line say R1 to R7; `charter.py:318`'s seed says `at a CHECKPOINT line, when a wait starts or its line changes, and at close`; each doc names `STALLED` and `est <zoned time|none>`, and none keeps §1's five phrases, "no wait stops the loop" or "at every commit".
- R11, a1's other doors (S54's review, F1, S1; added 2026-11-09 by the hq sitting). A bare `charter close` with no usable record of this session refuses, exit 2, when today holds two or more charters of the suffix: it names them and the `close <file>` form and writes nothing. A record that names a file outside the sittings directory refuses the same way. With one charter of the suffix it closes that one, as today. A helper's `open` taking its parent's record is not here.

Tests in `tests/test_fw1a.py`, each with its red at cba0b70:

| T | test | red |
|---|---|---|
| 1 | `test_fw1a_s4_rows_are_no_red` (R1) | `one more item: 'WAITING while ready: ...'` |
| 2 | `test_fw1a_due_rows_are_red` (R1) | `'...WAITING is legal only when...' != ...` |
| 3 | `test_fw1a_line_by_and_est` (R2; FULL passes) | `AssertionError: []` |
| 4 | `test_fw1a_stalled` (R3) | `module 'claude_session.charter' has no attribute 'stalled'` |
| 5 | `test_fw1a_at_n` (R4) | `"...wake at the cache's idle limit..." != ...` |
| 6 | `test_fw1a_item_4` (R5) | `'...n 2026-10-21)' == '... the charter)'` |
| 7 | `test_fw1a_s4_and_fill` (R6) | `+ , taken only when S1 to S3 have nothing ready ...` |
| 8 | `test_fw1a_clause` (R7) | `+ ... no wait stops the loop; WAITING 3+: idle limit; ...` |
| 9 | `test_fw1a_docs` (R10) | `'STALLED' in "--- name: session ...`; the prototype wrote no docs |
| 10 | `test_fw1a_bare_close_refuses_a_guess` (R11), four cases: no session dir, a session started in a parent directory, a Bash in another repo, the helper mark | at d7a3e38 each case: `rc=0`, `exit lines: A 0  B 1` (hq `REFUTE-2026-11-09-s54-probes/p1_a1_doors.sh`, c3 to c6) |

## 3. Interfaces

New: `charter.WAITING_FULL`, `STALLED`, `STALLED_LINE`, `STALLED_RED`, `REDS`, `stalled`; `rules.FILL`. S54 overlaps by file, never by hunk; cut the branch after it lands: `charter.py` (S54: `bare_target`, `:261`; here `:1-48`, `:137-210`, `:318`), `cli.py` (S54 `:403-406`), `SKILL.md` (`:116`), `RUNBOOK.md` (`:255`), the status line, the sidecar, `plugin.json`. T4 closes a named file, as S54 leaves it.

## 4. Findings that name this row

agentik-session keeps no ledger of its own (`ls`: no such file): no own entry to carry. Bearing, uncrossed: agentik-hq 6 (`plugin/lib` on Python 3.9, standard library alone); the Mac's session-budget entry (the 80% checkpoint still brings the charter current; `FILL` reads its Opus 5.5 on `[1m]`). `design/research.md` §3, read first: stdout is context on SessionStart, R7's carrier. No fork for the owner: design/08's question 1 is FW1b's, and until then a fill word ends at the respawn.

## 5. Forbidden reads

Live transcripts; `~/.local/state`; relay ledgers. Tests build their own.

## 6. Report

Six lines at most: the head sha; the gate's id and code; T1 to T9; R8's cases by file; each choice inside a ruling and its consumer; leftovers.
