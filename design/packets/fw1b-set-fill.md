# Packet FW1b: `set fill`, the word, its end and its mark

| item | value |
|---|---|
| from | hq `design/08-fill-wait-reconciler.md` §2 (Mechanism; FW1b's acceptance (1) to (4b)) and §9's question 1, as folded twice 2026-11-09; its refuter's A2, A3, A4, A6. The owner: "Until a time you name", in one terminal, never past the week's reset, never in a memory |
| pin | agentik-session main **after FW2 lands** (plugin 2.0.0-alpha.54); worktree `.claude/worktrees/fw1b-set-fill`, branch `fw1b-set-fill`, `.venv` and `.venv-floor` linked from the main checkout. Lines are S54's ee865ef: find by the quoted words |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude` but `make check`'s; no test writes under the live home; no relay verb; no gate verb under a temp HOME |
| may touch | `plugin/lib/claude_session/{fill.py,cli.py,rules.py,admission.py,hooks.py,chain.py}`; `plugin/skills/session/SKILL.md`; `plugin/commands/set.md`; `RUNBOOK.md`; `README.md`, `design/readme/{source.md,rendered.sha256}`; `tests/test_{fw1b,fw1a,rules,bare_machine}.py`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet as `design/packets/fw1b-set-fill.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id>` in one background Bash; read the job's code from its line |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_fw1b.py`: T1 to T11 green (ee865ef: `19 failed`; T2 is nine cases); an existing test is edited only where it pins `rules.FILL`'s words (R8) or is R9's table; the verify row green |
| budget | a commit per group by explicit path, the packet and the charter's five doclint rows first; stop at 90 tool calls or 140k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

At ee865ef. `set` takes a `SessionConfig` field alone (`cli.py:619`): `set fill opus` exits 1 on `unknown key 'fill'`, and `--until` is argparse's exit 2. A session-only key lands in `overlays/<sid>.json` (`sessionconfig.py:250`); the resolver takes from it only `SESSION_KEYS` (`resolver.py:486`). SessionEnd deletes the overlay (`hooks.py:672`) and a successor starts under a new id (`chain.py:411`), so only the chain home outlives a respawn, as S39's state does (`chain.py:338`). `band.json`'s `resetsAt` is the five-hour reset on a `five_hour` login (`admission.py:1507`); the week's reset is a seven-day reading's `resetsAt` on the admission ledger (`readings`, `:507`). `rules.render` and `clause` (`rules.py:234`, `:212`) take no fill; a spawn line has no own key (`admission.py:52`, `:264`).

## 2. Rulings

V is `{"word", "until", "week", "set"}`, three zoned ISO times; WHEN is `Ddd HH:MM`, local, as the band line writes a week's reset.

- R1, the verb. `agentik session set fill <reset|opus|off> [--until <zoned time>]`, a branch of `cmd_set` ahead of its field check; `fill` joins neither `SessionConfig` nor `SESSION_KEYS` (A2). It writes V under `fill` in this session's overlay and prints `fill: <word> to WHEN`. `off` drops the key, prints `fill: off` and is never refused.
- R2, the end. `--until` is what `rules._zoned` reads. Exit 2: `opus` with no `--until`, a time with no zone, an unknown word, `--until` beside `off` or another key. `reset` alone ends at the week's reset; a later time is cut to it and the line adds ` (the week's reset; --until named <given>)`; a passed time is exit 1. The week's reset is new `admission.week_reset(rows, sid, now)`: this session's own newest seven-day reading's `resetsAt` when ahead of now; with none, exit 1 (A4).
- R3, refused, exit 1, nothing written: `--save` or `--config`; no session id; a session `state.main_sitting` refuses; a resolved profile outside `orchestrator` and `orchestrator-opus`, or a window in force under `models.ONE_M`.
- R4, the read. New `fill.py`: `read(overlay, session, env, now)` gives the word and its end only when V is whole, `now < until <= week` and R3's seat holds, at every read. `line` gives `fill: <word> to WHEN`, `fill: off`, or, for a word held and not in force, `fill: off (<why>)`: `its time passed, WHEN`, `not a stamped word` or the seat's reason. Only this session's overlay is read. `rules` prints `line` last (`render(session, life, fill=None)`).
- R5, that one terminal. Under a launcher (`_chain_name`, `cli.py:825`) `set` also writes `<chain home>/fill.json`, `{"session", "fill": V}`; `off` removes it. Before each start `Chain._hand_fill(prev, sid)`, beside `_hand_state`, calls `fill.hand(home, state, prev, sid, now)`: a copy `prev` held, its time ahead, goes into `sid`'s overlay and names `sid`, and the launcher says `<chain>: fill <word> to WHEN goes to the successor`; any other copy is removed. With no launcher the word ends with the sitting.
- R6, said. `rules.clause(session, ttl, fill=None)`: FW1a's `fill off` becomes `fill.part`, `fill <word> to WHEN`, while on, within `BLOCK_MAX`. The prompt hook adds `fill: <word> to WHEN` as its own part while on, nothing while off.
- R7, the mark. `line_for` sets `fill: <word>` on a spawn line only while the word is in force for that session; `OWN_KEYS["spawn"] = ("fill",)`; a failure leaves the line as it was.
- R8, docs. `rules.FILL`, to the byte: `fill, off-path S4 work that uses a window up, is off unless the owner's word turns it on: the main thread, never a helper, runs agentik session set fill <reset|opus> --until <zoned time> on an orchestrator's 1M window; it ends then, never past the week's reset; no memory, ledger or charter turns it on or keeps it`. `SKILL.md`'s Set section, `commands/set.md`, `RUNBOOK.md:166-187`, `README.md:84` and its source line name `set fill` and `--until`, and say R1 to R5.
- R9. `fill.overlay` and `fill.hand` join `test_bare_machine.py`'s READERS (`:592`). Last, as FW2's R7: `2.0.0-alpha.55`, the status line, the sidecar.

Decided at the cut, each reversible. `opus` with no time is refused: the owner names it. A time past the reset is cut and said, not refused. A session with no seven-day reading of its own is refused: another's may be another login's. The chain home carries the word, since SessionEnd deletes the overlay before the launcher reads. The prompt hook says its own part, so the band line and its `session.ts` twin stand. The mark is absent while off, so no ledger test moves.

Tests in `tests/test_fw1b.py`, red at ee865ef; the cutter's prototype passes T1 to T10 and wrote no docs:

| T | test | red |
|---|---|---|
| 1 | `test_fw1b_set_turns_it_on` (R1, R2) | `error: unrecognized arguments: --until ...` |
| 2 | `test_fw1b_refused` (R3; nine cases) | `assert (2, '') == (1, '')`; with `--save`, `'--save' in "error: unknown key 'fill'...` |
| 3 | `test_fw1b_a_word_needs_its_time` (R2) | `(['set', 'fill', 'opus'], 1, "error: unknown key 'fill'...` |
| 4 | `test_fw1b_never_past_the_weeks_reset` (R2) | as T1 |
| 5 | `test_fw1b_reads_off_at_every_read` (R4) | `cannot import name 'fill' from 'claude_session'` |
| 6 | `test_fw1b_only_this_sessions_overlay` (R4) | `'a packet or ...enforces them' == 'fill: off'` |
| 7 | `test_fw1b_the_launcher_hands_it_on` (R5) | as T5 |
| 8 | `test_fw1b_session_start_and_prompt` (R6) | `assert 2 == 0`, T1's refusal |
| 9 | `test_fw1b_spawn_mark` (R7) | `KeyError: 'spawn'` |
| 10 | `test_fw1b_off_and_what_it_writes` (R1, R5) | as T8 |
| 11 | `test_fw1b_docs` (R8) | `'set fill' in "---\nname: session ...` |

## 3. Interfaces

New: module `fill` (`stamp`, `live`, `seat`, `read`, `line`, `part`, `wall`, `when`, `overlay`, `keep`, `hand`, `Refused`); `admission.week_reset`, `OWN_KEYS["spawn"]`; `Chain._hand_fill`; `set --until`; the `fill` argument of `render` and `clause`. Unchanged: the resolver, `SessionConfig`, `band.json`, `session.ts`. FW1a and FW2 overlap by file, never by hunk (`cli.py` here: `:355-363`, `:613-620`, `:1148`); R8 rewords FW1a's `FILL`, R6 its clause.

## 4. Findings that name this row

agentik-session keeps no ledger of its own: no own entry to carry. Bearing, uncrossed: agentik-hq 6 (`plugin/lib` on Python 3.9, standard library alone); the machine ledger's entry 20 (two review rounds at most); the machine ledger's entry 21 (a fill word is a setting, in no ledger); the machine ledger's entry 22 (R3's seat: its orchestrator on a 1M window, Fable or Opus 5.5 on `[1m]`). design/08 §11: A3 lands as R2. A6 is confirmed: an Agent-tool helper's shell carries its parent's `CLAUDE_CODE_SESSION_ID` and no helper mark, so R8's rule is its only guard. NICE to file, both S4: a PreToolUse refusal of `set fill` under `agent_id`; a hard-killed session's overlay, left to its stamp. `design/research.md` §3, read first: stdout is context on SessionStart, R6's carrier. No fork for the owner.

## 5. Forbidden reads

Live transcripts; `~/.local/state`; relay ledgers. Tests build their own.

## 6. Report

Six lines at most: the head sha; the gate's id and code; T1 to T11; R9's rows; each choice inside a ruling and its consumer; leftovers.
