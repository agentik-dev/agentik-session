# Packet M2: the engine's measure beside the meter (mod-r1's S2)

| item | value |
|---|---|
| from | `design/mod-r1.md` §2 (row M2), §4, §6 (S2), §7 criteria 3 and 4; packet S25 (`design/packets/s25-admission-observe.md`: one module per plugin and one unmatched hook per event on 2.1.296, so `session.ts`'s one `session.measure` handler gains this part) |
| pin | branch `s25-admission-observe` at 0eec4af (S25 checked, `make check` 0, not yet merged); worktree `.claude/worktrees/m2-measure`, branch `m2-measure` off it; this packet is on the branch; it merges after S25 |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, `claude-session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; no real model run (`claude plugin test` and `claude plugin validate` run none and are allowed); every python `-B`; tests use temporary state dirs, never the account's; never write `~/.claude*` or `~/.local/state` |
| may touch | `plugin/hooks/session.ts` and `plugin/hooks/session.test.ts` (the measure part of the one `session.measure` handler, and its cases), `plugin/hooks/admission.test.ts` (only if a count must skip the new call), `claude_session/measure.py` (new), `claude_session/cli.py` (the `measure` verb, `status`'s measure line), `claude_session/doctor.py` (a `measure` row), `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `design/mod-r1.md` (§6's S2 line only), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `tests/test_measure.py` (new), `tests/test_mod.py` (criterion 3's scan widened to `measure.json`), `tests/test_doctor.py` (the version literal, the new row), `tests/test_cli.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_measure.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (pin: no file); `.venv/bin/python -B -m pytest tests/test_mod.py tests/test_admission.py tests/test_doctor.py tests/test_cli.py -q 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check`, after the coordinator's `make readme` |
| budget | acts: 0 charter; 1 tests, red; 2 `measure record`, the status line and the doctor row; 3 the module's part and its cases; 4 docs, version. 60 turns, stop at 48 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

mod-r1 §2, row M2: "`session.measure` recorded beside the meter | catches a meter that parses wrong; feeds admission's `rateLimits` | two figures that differ, per turn against per tool | **mod, second slice**; the budget never reads it". §4: "The CLI owns every file under `<state>/sessions/<id>/` and writes each atomically. The mod reads with `$.fs.read` and writes none." "S2's `claude-session measure record` takes `session.measure`'s input on stdin and writes `measure.json`." §6: "S2: M2, `measure record`; `status` and `doctor` print the drift." §7: "3. A pytest proves `chain.py`, `hooks.py` and `budget.py` never open `measure.json` or `mod.json`." "4. A pytest: `measure.json` at 99% beside `meter.json` at 10% gives zone `clear` and no CHECKPOINT." The 2.1.296 types: `SessionMeasureInput` is `{context: {tokens?, window, percent?}, rateLimits: [...], cost?, changed: [...]}`, fired after each main-thread turn and when a rate-limit window moves a whole point.

## 2. Rulings

1. **`measure record`.** `claude-session measure record --session <id>` reads one JSON object on stdin with the keys `context` (`tokens`, `window`, `percent`), `rateLimits` (each `kind`, `percentUsed`, `resetsAt`), `cost` and `changed`, and no others; it validates the id as the hooks do (`_SID`), refuses an unknown key, a non-finite number or bad JSON (exit 2, nothing written), never creates an absent session dir (exit 1, `no session <id>`), and writes `<state>/sessions/<id>/measure.json` `{at, context, rateLimits, cost, changed}` atomically with the CLI's own private writer. It writes nothing else.
2. **The module's part.** `session.ts`'s one `session.measure` handler sends `{context, rateLimits, cost, changed}` to `measure record` on every measure, beside admission's record (which still runs only when `changed` holds `rateLimits`). Each part is bounded and caught as S25's are, neither skips the other, and `next(e)` is always reached.
3. **The drift.** `status` prints `measure: engine <t> tokens / meter <c> tokens, drift <d>% (<age>s apart)` from `measure.json`'s `context.tokens` and `meter.json`'s `context`, or `measure: none` without the file; the drift is `|t − c| / max(t, 1)`, printed only when the two stamps are within 120 s, else `measure: not comparable (<age>s apart)`. `doctor` prints a `measure` row: `ok` with no file or a drift under 10%, `warn` (never `FAIL`) at 10% or more, with both figures. Reversible thresholds, logged in one sentence.
4. **Nothing that decides reads it.** Criterion 3's scan in `tests/test_mod.py` covers `measure.json`; criterion 4 is a pytest in `tests/test_measure.py`.
5. **Version** 2.0.0a11 in the four places, `test_doctor`'s literal with it.
6. **Tests.** `tests/test_measure.py`: `measure record` writes `measure.json` with the four keys and `at`; refused key, number, JSON and id write nothing; an absent session exits 1 and creates nothing; the file's mode 0600; status's three forms (none, a drift, not comparable); doctor's `ok` and `warn`; criterion 4. `session.test.ts`: a measure sends one `measure record` call (with no `prompt` or message text) whether or not `changed` holds `rateLimits`; with `rateLimits` changed it also sends admission's record; either call rejecting or hanging still reaches `next`. Before the report, `claude plugin test plugin` passes every case and `claude plugin validate plugin` reads no error.

## 3. Interfaces

`claude-session measure record --session <id>` (stdin one JSON object; exit 0, 1 no session, 2 refused); `measure.json` `{at, context, rateLimits, cost, changed}`; `status`'s `measure:` line; `doctor`'s `measure` row.

## 4. Findings that name this row

mod-r1 §6 S2; §7 criteria 3 and 4.

## 5. Forbidden reads

Transcripts; other repos; the account's state dir.

## 6. Report (capped)

At most 150 words: the two acceptance lines' last lines and `claude plugin test`'s; the tests red at the pin and why; each existing test changed; the thresholds logged; anything filed. Last line: branch, head sha.
