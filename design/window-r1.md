# agentik-session: the engine's window decides (window r1)

**Status:** design r1, 2026-10-30, docs only. Its one refuter round before code (portfolio entry 20, the exception for an architecture change) ran on a20b8c5: FAIL, 2 blocks and 4 S4s. This text, with R2's helper clause and A15 and A16 among its changes, is that round's answer. Inputs: the owner's acceptance test of 2026-10-30, relayed by the hq sitting; `design/mod-r1.md` §3 to §7; the code at main a633d57 (2.0.0-alpha.27); 776 sessions' `meter.json` and `measure.json`, Claude Code 2.1.314.

The one-sentence design: the engine's measured window becomes the window pick's first source, the role still chooses the ceilings within it, and every other figure of the measure still decides nothing.

## §1 The problem, and the test that binds

The owner's test, in meaning: the plugin takes Claude Code's measured window, so a model change re-resolves the window and the ceilings and recomputes ctx %.

Today the window comes from the `models:` table by the model's family. Claude Code strips `[1m]` before the request, so the table cannot tell a 1M Opus from a 200k one by its id, and reads 200k. The figures, by (model, plugin window, engine window), with `statistics.median` of `max_context` (a re-run of the hq sitting's count; live sessions move the figures a little):

| model | plugin | engine | n | median | max | over 200k |
|---|---|---|---|---|---|---|
| claude-opus-5-5 | 200000 | 1000000 | 214 | 148711 | 312844 | 16 |
| claude-opus-5-5 | 1000000 | 1000000 | 168 | 201108 | 362646 | 85 |
| claude-fable-5-1 | 1000000 | 1000000 | 332 | 315226 | 391847 | 275 |
| claude-sonnet-5 | 200000 | 1000000 | 58 | 61074 | 141770 | 0 |
| claude-haiku-5-5 | 200000 | 1000000 | 4 | 33531 | 33539 | 0 |

What this proves: 16 Opus sessions the plugin held at 200k really ran past 200k, so the engine's 1M is right for Opus and for Fable.

What it does not prove:
- For Sonnet and Haiku the 1M is unproven; no session came near 200k.
- All 776 readings are 1000000. No live sample has ever shown another value, so a real change of value has never been observed here. §6 does not rest on one.
- When the measure fires. `session.measure` fires "after each main-thread turn, and when a rate-limit window moves a whole point" (admission-r1), and at session start: a fresh session's `measure.json` was written about 1 s after `started`, `context.tokens` null, `context.window` set. There is no evidence it fires on `/model`. A 100 s sample of six live sessions saw one move 2 metered turns with 3 measure writes, one move 1 with none, one move none with 2. A measure is not one to one with a metered turn, so every bound below is "the engine's next measure", never a count of tools.

## §2 The reversal, exactly and narrowly

mod-r1 §6 S2 says of `measure.json`: "nothing that decides reads it". That sentence now reads: nothing that decides reads it, except `context.window`, which `models.pick` takes as its first source.

That is the whole reversal. In mod-r1:
- **§2 row M2** ("the budget never reads it"): stands. `budget.py` is untouched.
- **§3** ("Zones come from `meter.json` alone"; the launcher reads no file the mod writes): stands. The ceilings inside `meter.json` may now follow a figure the module carried; the zone is still computed in the classic hook from `meter.json`'s own shares.
- **The one sentence** ("every refusal, stamp, ceiling and restart stays in Python"): stands. The module carries one number; Python validates it and picks.
- **Rule (a)** (a mod hook that times out or is skipped lets the action through): stands, because the guard's code stays classic. With no reading yet the pick is today's, never a missing guard. Once a reading has arrived it stands with no age check: if measures stop, it holds for the rest of the session, and "the engine's next measure" has no upper bound. A wrong reading can raise an orchestrator's ceiling; §5 bounds that.
- **§7 criterion 3**: holds literally; `chain.py`, `hooks.py` and `budget.py` never name the file. Read it for what it is: `hooks.py` now depends on the reading through `meter.limits_for`. Independence from the rest of the measure is proved by criterion 4 and A5, not by criterion 3.
- **§7 criterion 4**: holds. `context.tokens`, `percent`, the rate limits and the cost decide nothing.
- **§7 criterion 5**: holds. With no module, no reading exists, and the pick is today's.
- **§4** ("the CLI owns every file"): holds. `measure record` gains one conditional second write, `resolved.json` (R4).

## §3 The rulings

**R1. The one reader.** `models.engine_window(sdir)` opens `<sdir>/measure.json` and returns `context.window` when it is an `int`, not a `bool`, above 0 and at most `10**9`; otherwise None, for a missing file, a torn one, a non-object, a null `context`, or a value such as `1.5`, `1000000.0` or `"1000000"`. It reads no other field. No other module that decides names the file.

*Changed from the brief:* the read does not sit in `meter.py` or `measure.py`. `measure.py` imports `meter`, `resolver`, `admission` and `hooks`, and `hooks` imports `meter` and `resolver`, so a helper in `measure.py` is a cycle for both callers, and a lazy import would load `admission` on every PostToolUse. `resolver.py` needs the reading too and cannot lean on `meter.py`, which imports it lazily. `models.py` imports nothing of the package and is already read by both, so the reader sits there. `measure.MEASURE` keeps its value, taken from `models`.

**R2. The pick.** `models.pick(table, observed, session, declared, configured, engine=None)`: a readable `engine` returns `(engine, "engine:<n>")` before anything else. `meter.limits_for` adds `engine_window`, and `_limits` passes it. `window_class` then chooses from `windows` as today, so the role still sets the ceilings: a builder on 1M keeps 180k, an orchestrator gets 400k. Portfolio entry 22 is unchanged.

A helper (`CLAUDE_SESSION_HELPER=1`) keeps its 200k class figure whatever a layer sets: at resolve its `windows["1m"]` equals its `windows["200k"]`, so a reading moves its window and never its ceiling. Entry 22's wider budget is for a repo's relay rows, and a relay row that is not a helper keeps it. Without this, a helper on bare Opus under a project layer's `ceilings_1m` would rise from 180k to 400k at the first 1M reading (A15).

**R3. No reading.** With no reading the pick is exactly today's, by the same code path. The `models:` table stays as the fallback.

**R4. `resolved.json` follows.** `charter open`, `config show` and the relay's `resolved.yaml` reader take the file, not the meter.
- `resolve()` reads the reading for its session id and passes it to `pick`, so `set` does not undo it, and a resumed session starts on its last reading. Non-session ids (`doctor`, `profile`, `unsaved`, `meter`, the chain's guard) have no directory, so no reading. The reading joins `provider.inputs` as `engine:context.window` with the hash of its value, in the form of `overlay:argument`, only when one exists, so `resolve()`'s output stays a pure function of its listed inputs and fixtures with no reading are byte-identical. After a rewind the file is not that function: `provider.inputs` still lists what the last resolve read, and `window_source` names the reading.
- `measure record`, after writing `measure.json`, calls `resolver.rewindow(sdir, n)` when the reading is readable. Under the lock below: load `resolved.json`; when `session.window` differs from `n` and `session.windows` holds the class, set `window`, `ceilings`, `window_source` (`engine:<n>`) and `limits_source` (`<source> window:<n>`), and write both twins. Nothing else in the document moves. A failure of any kind is silent, exit 0; the next measure retries.
- *Why not re-resolve as `set` does:* it would read the layers again mid-session and depend on the module's process env for `CLAUDE_SESSION_MAX_TURNS`, which nobody has measured. `rewindow` reads no env and no layer.
- *Added to the brief, a lock:* `resolver._write_atomic` uses one fixed temp name, `resolved.json.tmp`, the fault `mod.json` already hit (test_mod, fix round 3), and a load-then-write could undo a concurrent `set`. `resolver.write` and `rewindow` each hold `flock` on the session directory's own descriptor. It creates no file, so "it writes nothing else" (test_measure) holds when the window has not moved. If the lock cannot be taken, `resolver.write` goes on unlocked (the hook never breaks a session) and `rewindow` skips.
- `ceilings_source` is left alone. Only `session_start` reads it, from its fresh resolve, never from the file; it can be wrong in the file only if a layer gives the two classes different turns and a launch cap falls between them. Filed to NICE.
- A source that agrees is not rewritten: a Fable session's `resolved.json` may keep `declared:fable` at 1M while its meter says `engine:1000000`. Both are true, and the file does not change for a word.

The race with SessionStart. The meter is right throughout, since it reads the reading itself at each tool; only `resolved.json` lags.

| order | result |
|---|---|
| measure before the session directory exists | refused, exit 1, one debug line (today's behaviour); a reading from the next measure |
| measure after the directory, before `resolved.json` | `measure.json` written, `rewindow` finds nothing; SessionStart writes the table's figure; the next measure converges |
| SessionStart read no reading, measure rewinds, SessionStart writes last | the table's figure stands until the next measure converges it |
| `set` resolved before a measure, writes after its rewind | the old window stands until the next measure converges it; `set`'s other keys are kept |
| measure rewinds while `set` writes | serialised by the lock; neither loses a key |

A `charter open` in the gap writes the table's figure in its budget row. The charter is a record, not a sensor, and its gap ends at the next measure. Accepted.

**R5. A model change.** The last reading holds until the engine's next measure, then the meter and `resolved.json` move. A change of the transcript's model never falls back to the table: a Fable to bare Opus change would flap to 180k and raise a false EXIT at 300k context (A8).

An unreadable measure must not cause that flap either: today's shape check passes a window of 1.5, which would overwrite the good reading and drop the pick to the table. So `measure.shape` refuses any window `engine_window` would not read (exit 2, as for any refused measure), and the last reading stands (A16). The check sits in `measure.py`, not in `admission.context`, which admission's payloads share.

`measure record` does **not** recompute `meter.json`. Only PostToolUse writes it, and it owns `meter-state.json`, whose `signal` holds the crossing. A second writer would need the zone policy in the verb, and would share the fixed `.tmp` names in `meter._write_atomic` with a hook that must not fail. The cost is a band that waits for the next tool, and the band says so: `1M (engine 200k)`. No budget signal is missed while tools run, because the signal speaks only at PostToolUse, and that write already reads the new window. If a switch to a really smaller window fails the request itself, no tool runs and EXIT never lands; this is untested live. The spawn gate reads `meter.json` and may see the old share for one call, the same one-tool lag the meter has today.

**R6. The SessionStart line.** It prints before the first measure, so with no reading it names the table: `on a 200000 window (table, session:claude-opus-5-5; the engine's first reading replaces this), checkpoint at 80%`. With a reading (a resume) it reads `(engine:1000000)` with no clause. The clause sits outside `_WSRC`'s 64-character clip. The figure stays the table's: the line says what was resolved, and a successor on bare Opus under `orchestrator-opus` is not told a figure nobody has measured yet.

**R7. The table and the user layer.** No shipped value changes. The table now serves only where there is no reading, and there 180k is the safe failure, since it fits under either window, so the cautious `opus: 200000` is right. A user-layer `models:` entry is outranked by a reading and stays a fallback, read by `chain.carry` too. A user who wants other ceilings sets `ceilings` or `ceilings_1m`, which still win field by field.

The stopgap `~/.claude/agentik/profiles.yaml` (`models: opus: 1000000`) is deleted once this is installed, by the owner or the hq sitting, never by the packet. Left in place it does harm only with no reading, where it gives a bare Opus orchestrator 400k.

**R8. `(engine E)` stays.** It will rarely show, but it now means one thing: the meter has not caught up with the engine's latest reading. Removing it would change two twins and their pinned fixture for nothing. The RUNBOOK and SKILL examples stop showing `200k (engine 1M)` as the normal case.

## §4 The consumers found

| reader | what it reads | after this |
|---|---|---|
| `hooks.post_tool_use`, `_ledger_line`, `cli.cmd_status --transcript` | `meter.limits_for` | follow the reading |
| `hooks.session_start` | its fresh `resolve` | R6 |
| `charter.open`, by `cli._session_section` | `resolved.json` | R4 |
| `cli._show_resolved` (`config show`), the relay's `sessionConfig` | `resolved.yaml` | R4; the relay reads its own section, unchanged |
| `cli._rewrite_resolved` (`set`) | `resolve` | keeps the reading; its docstring's "the declared one decides the window" becomes false |
| `chain.carry` | `models.window_of` on the start line | **stays on the table**: it spells the successor's `--model` and its marker, and the ceilings follow the engine whatever the spelling |
| `chain.guards`, `model_table`; `doctor`; `cli.cmd_profile` | `resolve` under a non-session id | no reading: a role's view by the table, by design |
| `resolver.newest_session` (`status`, `doctor` with no id) | `resolved.json`'s mtime | a rewind moves a session up that fallback order; accepted, it applies only with no session id |
| `admission._session_config` | `resolved.json`, no window key | unchanged |
| `session.ts` band, `mod.facts`, the agents plugin's status table | `meter.json`'s window, `measure.json` | display; follow the meter |
| the observer | `resolved.json`'s `respawn`; `_born` takes the earliest mtime | unchanged |

## §5 The bounded risk

If the engine's 1M is wrong for a model, the ceiling moves only where the two classes differ. In `profiles.yaml`, only `orchestrator` and `orchestrator-opus` differ (180k, 400k). `frontier`, `balanced`, `local`, `local-only`, `scratch`, `review`, `packets` and `builder` hold 180k on both, and the shipped orchestrators declare Fable and `opus[1m]`, both proven.

*Narrower than the brief's claim:* a user or project layer that sets `ceilings_1m` makes any role differ, by its own choice, for any session but a helper (R2). This Mac's user layer holds no such key; seven repos' project layers set it to 400k.

The failure, if it happens: an orchestrator on Sonnet or Haiku, with a window really at 200k and a reading of 1M, would hold a 400k ceiling. The sitting never reaches CHECKPOINT before the hard limit, the C1 block keeps it from compacting, and a request fails (mod-r1 §8's stated cost). That needs an orchestrator profile on those models and the engine misreporting its own window. The first has happened: 42 sessions under an orchestrator profile ran on Sonnet or Haiku with no session model, median 2 turns, newest 2026-10-12, probably unmarked `claude -p` children. Nothing shows the second.

A lead, read only from minified names in the 2.1.314 bundle: `_g` returns 200000 (`_V`) when `Oat` holds, and `Oat` follows a credit latch (`Sje`, `longContext1mCreditsBlocked`), so a live drop to 200000 with no `/model` may exist.

A measured window under 200k stays in the 200k class, as a table value would: a local model behind the router reading 32000 gets `window: 32000`, 180k. The `local-only` and `scratch` profiles declare `local/default`, which the table does not know, and hold 180k on both classes, so a small window is reported where today it reads the 200k default, and the ceiling is the same. A ceiling above a small window never trips, today as after. A clamp is out of scope, filed to NICE.

A reading can be forged by anyone who can run the CLI with the session's id, as `set` can; it can raise a ceiling only to the role's `ceilings_1m`.

## §6 The proof strategy

No proof below needs a live change of value.
- **Each link offline.** The module carries the event's window verbatim (A13). `measure record` keeps it and rewinds `resolved.json` (A1, A2, A10). The meter takes it at the next tool (A1, A2).
- **The engine's end, live.** L1 shows a real engine reading deciding, on a session the table would have put at 200k. Its source string, `engine:1000000`, cannot come from the table.
- **What stays unproven, plainly:** that the engine ever reports another value on a live session, and that it does so after `/model`. If it does, the links above carry it. If it never does, the design costs one file read per tool.
- **A real other value, where the engine gives one.** The 2.1.314 bundle reads `believed:YP()?Math.min(h,bxt):h`, where `YP` is `CLAUDE_CODE_DISABLE_1M_CONTEXT` and `bxt` is 200000, so L2 may read 200000. Its effect has never been measured here. If it does, that is the first live sight of a value other than 1M and L2 is the live proof of the owner's test, for a value at start rather than a change within a session. If it reads 1M, nothing fails and the proof rests on the links above.

## §7 Acceptance

Each is offline with fixtures, in a new `tests/test_window.py` unless named: `.venv/bin/python -B -m pytest tests/test_window.py -k <aN>`. A3, A13 and A14 are controls: they pass on today's code too (A14 once `tests/test_s34.py` has its skip, §9) and guard against a regression, so they prove nothing new.

- **A1, the owner's test, `orchestrator-opus`.** A session with `CLAUDE_SESSION_MODEL=claude-opus-5-5`, no user layer, transcript context 150000. A measure at 1000000: `resolved.json` reads window 1000000, ceilings 400000/400, `window_source` `engine:1000000`, `limits_source` `role:orchestrator-opus window:1000000`; the next `post_tool_use` gives `meter.json` the same and `pct_context` 37.5. A measure at 200000: `resolved.json` 200000, 180000; the next tool gives 83.3 and CHECKPOINT speaks. A measure at 1000000: 37.5 again.
- **A2, the owner's test, `builder`.** The same sequence: the window moves in both files each time; the ceilings stay 180000/400; `pct_context` stays 83.3.
- **A3, no reading (control).** No `measure.json`: `resolved.json` and `meter.json` equal today's for the same inputs, with no `engine:` anywhere and no `engine:context.window` input. `git diff --stat main -- tests/test_models.py tests/test_launch_model.py` is empty, and both pass.
- **A4, garbage.** `None`, `0`, `-1`, `True`, `"1000000"`, `1.5`, `1000000.0`, `10**9 + 1`, `[]` in `context.window`; a torn file; a non-object; `context` null: `engine_window` is None, `pick` returns today's answer, `rewindow` is not called. A shape-refused measure leaves the last reading in place.
- **A5, the rest decides nothing.** `tests/test_measure.py -k criterion_4` passes unchanged. With window 1000000, tokens 999999, percent 99, `rateLimits` at 99 and cost 99 beside a transcript at 18000: `pct_context` is 18000 over the ceiling, no CHECKPOINT, `resolved.json`'s keys other than the four are unchanged. A fixture holding only `context.window` gives the same pick as the full one.
- **A6, `set` keeps it.** After a rewind to 1000000, `set posture` and `set model sonnet` each leave window 1000000, the 1M ceilings and `engine:1000000`.
- **A7, the modules.** `tests/test_mod.py -k criterion_3` passes unchanged. `meter.py`, `resolver.py`, `chain.py`, `hooks.py` and `budget.py` do not hold the string `measure.json`; in `models.py` it is one module constant, which `measure.MEASURE` takes, and `engine_window` is its only opener and reads no key but `context` and `window`.
- **A8, no flap.** `orchestrator`, reading 1000000, transcript moves from `claude-fable-5-1` to `claude-opus-5-5` at context 300000: ceiling 400000, 75.0%, no CHECKPOINT. The control with no reading: 180000, 166.7%, the EXIT line, which pins why the fallback must not run while a reading exists.
- **A9, the race.** Each row of R4's table as a fixture: the meter is right in each, and the next measure converges `resolved.json`. Eight processes running `resolver.write` and `rewindow` together end with valid JSON and YAML, no exception and `set`'s key intact.
- **A10, the classes.** 32000 and 999999 fall in the 200k class (180k under `orchestrator-opus`, window as measured); 1000000 and 2000000 in the 1m class (400k).
- **A11, the twin.** After a rewind `resolved.yaml` loads equal to `resolved.json`, `provider` and every section but `session` are unchanged, and in `session` only the four keys differ. `charter open`'s budget row reads `400k context`, and `config show` prints window 1000000.
- **A12, the line.** No reading: the line holds `(table, session:claude-opus-5-5; the engine's first reading replaces this)`. A reading from an earlier measure: `(engine:1000000)` and no clause.
- **A13, the module's link (control).** `claude plugin test plugin`: in `session.test.ts`, an event at window 200000 and one at 1000000 each send that figure on `measure record`'s stdin. It pins a link in `session.ts` the packet does not change.
- **A14, no module (control).** `tests/test_mod.py -k criterion_5` passes unchanged, and the suite passes with `plugin/hooks/*.ts` removed. This needs `tests/test_s34.py`'s `_fixture` to take the skip `tests/test_mod.py` and `tests/test_s35.py` already take: on main, `test_s34_h_the_twins_share_the_note` raises FileNotFoundError without the files.
- **A15, a helper's ceiling.** `CLAUDE_SESSION_HELPER=1`, bare Opus, a project layer with `ceilings_1m: {context: 400000, turns: 400}`, context 190000. No reading: window 200000, ceiling 180000, 105.6%, EXIT. A reading of 1000000: window 1000000, ceiling still 180000, 105.6%, EXIT (without the clause, 400000, 47.5%, clear). The same layer and reading with `CLAUDE_SESSION_PROFILE=builder` and no helper flag, as a relay row runs: 400000, 47.5%.
- **A16, an unreadable measure.** After a reading of 1000000, `orchestrator` on Opus at context 300000: `measure record` with a window of `1.5`, `1000000.0` or `10**9 + 1` exits 2 and leaves `measure.json` and `resolved.json` byte-identical; the next tool reads 400000, 75.0%, no CHECKPOINT.

Live, run by the builder, never by this record's author:
- **L1.** `scripts/window-proof OUT` (new, in `p1-proof`'s shape: a scratch repo, `XDG_STATE_HOME=OUT/state`, the installed plugin off by `--settings`, a copy of `plugin/` as `--plugin-dir`, and `OUT/bin/agentik-session` first on PATH, which runs this branch's code with `HOME=OUT/home`, so the tool sees no user `models:` layer while `claude` keeps its login). It runs `claude -p --model claude-opus-5-5` with `CLAUDE_SESSION_PROFILE=orchestrator-opus` and `CLAUDE_SESSION_MODEL=claude-opus-5-5`, on a prompt that reads a file, then reads it again. Pass: `meter.json` and `resolved.json` each read window 1000000, ceilings.context 400000, `window_source` `engine:1000000`. The control it prints: the same inputs with no `measure.json` resolve to 200000, 180000, `session:claude-opus-5-5`. If a `-p` child writes no measure, `--tty --cwd <a trusted checkout>`, as in `p1-proof`.
- **L2, a gate only where it reads 200000.** `scripts/window-proof OUT --case disable-1m` adds `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` and sets `CLAUDE_SESSION_MODEL='claude-opus-5-5[1m]'`, which only the tool reads, so the table starts at 1000000, 400000 and the move is visible (with L1's bare id the table already agrees, and `resolved.json` would not be rewritten). The builder records the reading in the change log. At 200000 it is the live proof of §6: `meter.json` and `resolved.json` must read 200000, 180000, `engine:200000`. At 1000000 nothing fails and the proof rests on the links.

## §8 Text the change makes false

- **Code headers and docstrings:** `models.py`'s header and `pick`; `meter.py`'s lines 20 to 23, `_limits`, `limits_for`; `resolver.py`'s lines 18 to 26 and its "pure function" paragraph; `measure.py`'s line 9; `cli._rewrite_resolved`; `session.ts` lines 62 to 67 and 281 to 284; `profiles.yaml` lines 1 to 5 and 13 to 24.
- **Docs:** README's "The model decides the window" list and its `opus[1m]` start line (`design/readme/source.md` byte-identical); RUNBOOK §4's band line and the budget section; SKILL.md's ceilings paragraph and band line.
- **`mod.py`'s "Display only" comment stays true**, and stays.
- **`design/mod-r1.md`, amendment lines only, never a rewrite:** after §6 S2, and after §7 criterion 3: `Amended 2026-10-30 by design/window-r1.md §2: context.window alone is read by what decides, as the window pick's first source; tokens, percent, the rate limits and the cost still are not.`

## §9 The packet that follows

One packet in GUIDE §9's shape, under 9,216 bytes, **S45** (S42 to S44 are taken by another record), cut from main: it may touch `claude_session/models.py`, `meter.py`, `resolver.py`, `measure.py`, `hooks.py` (the line only), `cli.py` (the docstring only), `profiles.yaml` (comments only), `plugin/hooks/session.ts` (comments only), `plugin/hooks/session.test.ts`, `tests/test_window.py`, `tests/test_s34.py` (the skip only), `scripts/window-proof`, `RUNBOOK.md`, `plugin/skills/session/SKILL.md`, `design/mod-r1.md` (the two lines), `design/window-r1.md` (a change log), `NICE_TO_HAVE.md`, and the version's places as S41 listed them: `claude_session/__init__.py` (lines 3 and 5), `pyproject.toml` (line 7), `plugin/.claude-plugin/plugin.json` (`version`), `tests/test_doctor.py` and `tests/test_install.py` (the pins), `README.md` and `design/readme/source.md` (the prose above and the status line, byte-identical) with `design/readme/rendered.sha256` re-hashed. Any change under `plugin/` bumps `plugin.json` (GUIDE §7), so all of it moves to 2.0.0-alpha.28. GUIDE §7's major bump for a change to the resolved-file contract does not apply: the keys and types are the same, one source string gains a form, and a `-alpha.N` needs no tag. Its acceptance row is A1 to A16 by name; its verify row is `make check`, one `make` at a time; L1 and L2 are the builder's before hand-back. To `NICE_TO_HAVE.md` it files `ceilings_source` (R4) and the clamp (§5), and appends S41's leftovers verbatim, 1,739 bytes, from the `s41-nice-lines.md` the packet's read list names (the hq sitting's scratchpad; its path stays out of this public record). The commons marketplace line and the install are the hq sitting's, when no relay process runs; the stopgap's deletion follows the install.

## Change log

- 2026-10-30, packet S45 (`design/packets/s45-engine-window.md`), built as written. L1 and L2 ran once each on `claude-haiku-5-5` (the coordinator's cheap model, Claude Code 2.1.314; `CLAUDE_SESSION_MODEL` as §7 names it, which only the tool reads), both `-p`, and each wrote a measure.
  - L1: measure `context.window` 1000000; `meter.json` and `resolved.json` window 1000000, `ceilings.context` 400000, `window_source` `engine:1000000`, `limits_source` `role:orchestrator-opus window:1000000`. Control with no measure: 200000, 180000, `session:claude-opus-5-5`.
  - L2: measure `context.window` 200000; `meter.json` and `resolved.json` window 200000, `ceilings.context` 180000, `window_source` `engine:200000`, `limits_source` `role:orchestrator-opus window:200000`. Control with no measure: 1000000, 400000, `session:claude-opus-5-5[1m]`. This is the first live sight of a value other than 1M, and the live proof of the owner's test for a value at start, on Haiku rather than Opus. A change of value within one session stays unobserved live (§1, §6).
  - The S45 choices, all reversible: the session's lock is polled for at most 2 s (`resolver.LOCK_WAIT`); `models.readable_window` is the one test the reader, the pick and the shape share; A11's `config show` is `config show --resolved`, the verb `_show_resolved` serves; `scripts/window-proof` lays its own repo and has no `--tty`, since p1-proof no longer loads (filed to NICE) and `-p` wrote a measure.
