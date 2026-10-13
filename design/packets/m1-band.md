# Packet M1: the read-only band (mod-r1's S1)

| item | value |
|---|---|
| from | `design/mod-r1.md` §4, §5, §6 (S1 and P1's result), §7 criteria 1 to 7; `design/admission-r1.md` note 12 (conventions §1 and §4 name no Mod or `.test.ts`); `design/conventions.md` §1, §4 |
| pin | `main` at 1204d4c (C1, S22 and P1 merged); worktree and branch `m1-band` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, `claude-session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; no real model run (`claude plugin test` runs none and is allowed); every python `-B`; tests use temporary state dirs, never the account's; never write `~/.claude*` |
| may touch | `plugin/hooks/session.ts` (new; the module) and `plugin/hooks/session.test.ts` (new), `plugin/hooks/hooks.json` (`modules` only), `claude_session/cli.py` (the `mod` verb, `status`'s and `doctor`'s mod line), `claude_session/mod.py` (new), `claude_session/doctor.py`, `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `Makefile` (the `claude plugin test` line in the gate), `design/mod-r1.md` (§5's rows only), `design/conventions.md` (§1, §4), `design/admission-r1.md` (note 12's line only), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `tests/test_mod.py` (new), `tests/test_doctor.py`, `tests/test_cli.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_mod.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (pin: no file); `.venv/bin/python -B -m pytest tests/test_doctor.py tests/test_cli.py -q 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check`, after the coordinator's `make readme` |
| budget | acts: 0 charter; 1 tests, red; 2 `mod start` and the status/doctor line; 3 the module and its `.test.ts`; 4 docs, gate line, version. 70 turns, stop at 56 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

mod-r1 §6: "S1, the first slice: M1, a read-only band. One `ui.render` hook on `AbovePrompt`, redrawn on `turn.complete` and every 5 s; it reads `meter.json`, `respawn.json` and `turn-ended.json`, writes nothing, runs only `mod start`." §4: "At `session.start` the mod runs one new verb through `$.process.run` (5 s): `claude-session mod start --session <id>` prints the session's directory as JSON and writes `mod.json` (`{at, version}`), which `status` and `doctor` print as 'mod: seen' or 'mod: not seen'." "`$.store` holds only `pref.*` keys." §7, criteria 1 to 7 (1: hooks.json keeps its classic events, commands and timeouts and adds only `modules`; 2: no `fs.write` or `store.set` but a `pref.` key; 3: `chain.py`, `hooks.py` and `budget.py` never open `measure.json` or `mod.json`; 5: the pytest suite passes with `plugin/hooks/*.ts` removed; 6: the band reads `ctx 62% · turns 31% · notice` from a fixture, `no meter` without one, its age past 120 s, and fits `bodyColumns`; 7: no `respeak`, `decisions` or `agent-relay` in the module). P1's result, merged at d7520cc: on 2.1.296 the module loads under `-p`, and a module throwing in every hook is skipped per call and never unloaded (170 calls).

## 2. Rulings

1. **The module.** `plugin/hooks/session.ts`, declared by `"modules": ["./session.ts"]` in `hooks.json` (P1's `scripts/p1-proof` shows the shape; load the `plugin-authoring` skill for the API). On `session.start` it runs `claude-session mod start --session <id>` through `$.process.run` with a 5 s limit and keeps the printed directory in `$.state`; on failure it draws `session: no meter · claude-session doctor`. Its one `ui.render` hook on `AbovePrompt` reads `meter.json` (and `respawn.json`, `turn-ended.json` when present) with `$.fs.read`, and draws one line `session: ctx <c>% · turns <t>% · <zone>`, plus ` · respawn marked` when `respawn.json` exists, ` · <age>s old` when `meter.json` is older than 120 s, clipped to `bodyColumns`. Redraw on `turn.complete` and every 5 s. It writes nothing; `$.store` only `pref.*`; it names no sibling plugin.
2. **`mod start`.** `claude-session mod start --session <id>` validates the id as the hooks do, writes `<state>/sessions/<id>/mod.json` `{at, version}` atomically (the CLI's own writer), and prints `{"dir": "<abs>"}`; exit 2 with one line on a bad id; it never creates a session dir that is absent (exit 1, `no session <id>`).
3. **The status and doctor line.** `status` prints `mod: seen <age> ago` or `mod: not seen`; `doctor` prints an `ok`/`warn` row `mod` the same way (`warn`, never `FAIL`: a `-p` child or a refused module is not an error).
4. **§5's rows** take P1: the `-p` row loses `-p` (the module loads there); the three-crash row becomes "throws in every hook: each call skipped, one line each; the band stops drawing; classic intact (P1)".
5. **Conventions** §1 and §4 name the module file and its `.test.ts`, run by `claude plugin test`, which runs no model; admission-r1's note 12 line says M1 made the amendment. The gate (`check-unlocked`) gains the `claude plugin test` line.
6. **Version** 2.0.0a9 in the four places (`test_doctor`'s version literal with it).
7. **Tests.** `tests/test_mod.py`: `mod start` writes `mod.json` and prints the dir; a bad id exits 2 and writes nothing; an absent session exits 1 and creates nothing; `status` and `doctor` lines, seen and not seen; criterion 1 (hooks.json's classic block unchanged from the pin's, plus `modules`); criterion 2 and 7 as greps over `plugin/hooks/*.ts`; criterion 3 (an AST or text scan of the three modules); criterion 5 (the suite's collection does not read `plugin/hooks/*.ts`: run pytest on a copy with them removed, or assert no test or module opens them). `session.test.ts`: criterion 6's four cases, and `respawn marked`; before the report, the mod's tests run once under `claude plugin test` (its own `--help` names the argument) and every case reads passed.

## 3. Interfaces

`claude-session mod start --session <id>` → stdout `{"dir": …}`; `mod.json` `{at, version}`; `status`'s `mod:` line; `doctor`'s `mod` row; the band's line.

## 4. Findings that name this row

mod-r1 §6 S1; P1's result (two §5 rows wrong on 2.1.296).

## 5. Forbidden reads

Transcripts; other repos; the account's state dir.

## 6. Report (capped)

At most 150 words: the three acceptance lines' last lines; the tests red at the pin and why; each existing test changed; anything filed; the band's line as drawn from the fixture. Last line: branch, head sha.
