# Packet S27b: the admission meter shown (admission-r1's S27b)

| item | value |
|---|---|
| from | `design/admission-r1.md` §3.5, §3.6, §5 (S27b); packets S25, M2 and S26 (merged at 541d7fd: the ledger, `admit`'s peak, the module in `session.ts`); M1 (the band) |
| pin | `main` at 541d7fd (alpha.12); worktree `.claude/worktrees/s27b-show`, branch `s27b-show` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, `claude-session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; no real model run (`claude plugin test` and `claude plugin validate` run none and are allowed); every python `-B`; stdlib only; tests use temporary state dirs, never the account's; never write `~/.claude*` or `~/.local/state` |
| may touch | `claude_session/admission.py` (the band's figures and `band.json`), `claude_session/hooks.py` (the prompt line only: read `band.json`, add its line), `claude_session/cli.py` (`report`'s window section), `plugin/hooks/session.ts` and `plugin/hooks/session.test.ts` (the band's second line, the survey yield), `plugin/hooks/admission.test.ts`, `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `design/admission-r1.md` (§5's S27b line only), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `tests/test_band.py` (new), `tests/test_hooks.py`, `tests/test_cli.py`, `tests/test_mod.py` (criterion 3's scan, if `band.json` joins it), `tests/test_doctor.py` (the version literal), `NICE_TO_HAVE.md`, `history/sittings/*.md`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_band.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (pin: no file); `.venv/bin/python -B -m pytest tests/test_admit.py tests/test_admission.py tests/test_hooks.py tests/test_mod.py tests/test_cli.py -q 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check`, after the coordinator's `make readme` |
| budget | acts: 0 charter; 1 tests, red; 2 the band's figures and `band.json`; 3 the band's line in the module and the prompt line; 4 `report`'s window use; 5 docs, version. 70 turns, stop at 56 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

admission-r1 §3.5: "The band is one line in `AbovePrompt`, cut to `bodyColumns`. It yields while `hasSurvey` is true and keeps other mods' lines. For example: `5h 72% → 91% · ceiling 97 · resets 14:05 (1h12) · 3 helpers, room for 2 · 1 deferred · 7d 41%`. The prompt hook adds the same line to the budget context." §3.6: "The target is a floor on use, and the ceiling is a cap. … 'Room for N' tells the orchestrator to pull work forward. `report` prints each window's last reading as `held` (spawns waited) or `idle` (nothing waited). The Mod cannot make work, so an idle window under 90 is reported, never hidden." §5 S27b: "The band, the prompt line, and `report`'s window use. Red: the band's line pinned at 80 columns." §2: "The policy lives in the Python tool, pure and tested by pytest. The Mod is glue: it reads, forwards, draws and wakes."

## 2. Rulings

1. **The figures are Python's.** A pure `band(rows, now, cfg)` in `admission.py` returns `{P, peak, ceiling, resetsAt, running, room, deferred, P7, mode, at}`: P and the peak with no new spawn (S26's fit and peak); `running` the helpers in flight; `room` the largest N whose N spawns of the parent's family (the newest spawn's, else `opus`) keep peak + margin ≤ ceiling, at least 0; `deferred` the `deferred` and `wait` verdicts since the window's start (in `observe` these are spawns that would have waited); P7 the seven-day reading. Every `admission record` and `admission admit` rewrites `admission/band.json` from it, inside the lock, atomically with the CLI's private writer. With no five-hour reading, `band.json` holds `{mode, at}` only.
2. **The line**, one function in Python (`band_line`) and its twin in `session.ts`, the same text from the same file: `5h <P>% → <peak>% · ceiling <c> · resets <HH:MM> (<h>h<mm>) · <n> helpers, room for <r> · <d> deferred · 7d <P7>%`, with `· observe` last while the mode is `observe`; a part with no figure is left out; no reading reads `5h no reading`. Cut to the width (80 in the pinned test). Its age past 120 s adds `· <age>s old`, as M1's line does.
3. **The band** draws it as a second line under M1's `session:` line in the one `ui.render` hook on `AbovePrompt`, from `band.json` read by `$.fs.read` (the module writes nothing). While `props.hasSurvey` is true the hook draws neither line and returns `next(e)`. Other mods' lines are kept: it adds to what `next` gives, never replaces it.
4. **The prompt line.** The classic UserPromptSubmit hook adds `band_line` from `band.json` to its additional context, after the budget line; with no file or an unreadable one it adds nothing. It is display only: nothing in `chain.py`, `budget.py` or the verdict reads `band.json` (criterion 3's scan widened to it).
5. **`report`'s window use.** `claude-session report` gains a section: one row per five-hour window seen in the admission ledger (by `resetsAt`, the current and `ledger.1.jsonl`'s), with its last `percentUsed`, `held` when any `deferred` or `wait` verdict fell in it, else `idle`, and `under 90` marked when the last reading is below 90. With no ledger it prints `admission: no ledger`.
6. **Version** 2.0.0a13 in the four places, `test_doctor`'s literal with it.
7. **Tests.** `tests/test_band.py`: `band()` on a synthetic ledger (P, peak, running, room against a hand count, deferred, P7); `band.json` rewritten by `record` and by `admit`, atomic and 0600; `band_line` pinned at 80 columns for a full figure set, each part left out when absent, `no reading`, `observe`, the age; the prompt hook's line with and without the file; `report`'s window rows (`held`, `idle`, `under 90`) and `no ledger`. `session.test.ts`: the second line drawn from a fixture `band.json`, the same text as Python's for the same file (one shared fixture), neither line while `hasSurvey`, another mod's line kept. Before the report, `claude plugin test plugin` passes every case and `claude plugin validate plugin` reads no error.

## 3. Interfaces

`admission/band.json` `{P, peak, ceiling, resetsAt, running, room, deferred, P7, mode, at}`; the band's second line; the prompt hook's added line; `report`'s admission section.

## 4. Findings that name this row

admission-r1 §5 S27b; §3.6 (the 90% floor reported).

## 5. Forbidden reads

Transcripts; other repos; the account's state dir.

## 6. Report (capped)

At most 150 words: the two acceptance lines' last lines and `claude plugin test`'s; the tests red at the pin and why; each existing test changed; the band's line as drawn from the fixture; anything filed. Last line: branch, head sha.
