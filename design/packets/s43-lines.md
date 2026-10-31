# Packet S43: the lines on a login with no five-hour window

| item | value |
|---|---|
| from | the owner, 2026-10-30, "the Max plans still have the 5 hour limit and I still intend to use the Max plans as well as the Ultra plans, so keep the logic"; a private hq's design record; §1 carries its text |
| pin | a99a238 (main, alpha.29); worktree `.claude/worktrees/s43-lines`, branch `s43-lines` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run a relay verb, or build or run a relay binary; not `bands.yaml`, `demand` or the band in `status` (S44), not `decide` or `window()` (S42, landed), not the relay (AR98) |
| may touch | `claude_session/admission.py` (`band_line` and its helpers only), `claude_session/rules.py` (`lifetime` and its docstring), `claude_session/charter.py` (the meter-wait pattern), `plugin/hooks/session.ts` (`admissionLine` and its helpers), `plugin/hooks/session.test.ts`, `tests/test_window_mode.py`, each charter test file for one new test, `RUNBOOK.md`, `plugin/skills/session/SKILL.md`, `design/admission-r1.md` (amendment lines), `NICE_TO_HAVE.md`, and act 4's pins as 694bf81 touched them: `claude_session/__init__.py`, `pyproject.toml`, `plugin/.claude-plugin/plugin.json`, `tests/test_doctor.py`, `tests/test_install.py`, `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`; this packet; the charter |
| acceptance | `.venv/bin/python -B -m pytest tests/test_window_mode.py -q 2>&1 \| tail -1` reads `passed`, no `failed`, and `-k 'test_band_line_none or test_band_line_five_hour_bytes_unchanged or test_lifetime_none_by_seven_day'` selects at least three (on a99a238: none of the names); `.venv/bin/python -B -m pytest tests -q -k test_charter_week_wait_is_meter_wait 2>&1 \| tail -1` reads `1 passed`; `.venv/bin/python -B -m pytest tests/test_admit.py tests/test_admission.py tests/test_band.py tests/test_s35.py tests/test_mod.py tests/test_rules.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; each test file that imports `claude_session.charter` green; `grep -c test_none_line_reads_as_today_until_s43 tests/test_window_mode.py` reads 0; `plugin/hooks/session.test.ts` passes under the runtime the repo runs it with (name the line in the report; if `make check` never executes it, say so as a finding, and run it by hand if `bun` is on PATH) |
| verify | `make check`, by the coordinator through the gate, one `make` at a time on this Mac |
| budget | acts: 0 this packet; 1 the tests, red; 2 the code; 3 the docs; 4 the version, the README count, the sidecar (last, one bump; 694bf81 is the model). 70 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter, `history/sittings/2026-10-30-4-s43.md`, opens with doclint's five rows |

## 1. What the source says (a private hq's design record, quoted)

"The pacing line, both twins: `five_hour` byte for byte as today. `none`: `no 5h window · 7d 62% · week resets Fri 13:00 · band avoid to 11:00 · 3 helpers · observe`."

"The prompt hook: `five_hour` unchanged; `none`: the line above; the cache clause from `lifetime`."

"`rules.lifetime`: `five_hour` unchanged. `none`: `5m "past plan usage, 7d N%"` at PLAN, else `1h "within plan usage, 7d N%"` while the week's reset is ahead."

"Meter-wait rule (`charter.py`): gains `week`, `weekly`, `7d`, `seven-day`, `band` (mode-free)."

"S43's line omits the band part until S44 writes `demand`."

Tests the record names: `test_band_line_none` with its `session.test.ts` fixture; `test_band_line_five_hour_bytes_unchanged`; `test_lifetime_none_by_seven_day`; `test_charter_week_wait_is_meter_wait`.

## 2. Rulings

1. **The none line.** `band_line` and `admissionLine` take the none branch when the entry's `window` is the string `none`, and only then: an entry with `five_hour`, with no `window`, or with any other value draws today's line, byte for byte. Parts in order, each left out with no figure: `no 5h window`; `7d N%`; `week resets Ddd HH:MM`; `n helper(s)`; `observe`; `Ns old` (the same STALE_S rule). No countdown in parentheses, no `ceiling`, no `room`, no `deferred`: a `none` entry carries none of them, and the owner's line has none. S44 inserts its band part after the week's reset; leave that seam plain.
2. **The weekday** comes from the stamp's own date digits, as HH and MM already do, in fixed English three-letter names, in both twins: no locale, no system zone. `until` first, else `resetsAt` (both the week's on a `none` entry). A stamp `wall` refuses reads as no figure.
3. **The fixture.** Two new constants in `session.test.ts`, `BAND_NONE` and `BAND_NONE_LINE`, in the same one-line shape as `BAND_WEEK`; `test_band_line_none` reads them the way `tests/test_band.py` reads `BAND_LINE`, so one fixture pins both twins. A second fixture for a `none` entry with no week reading: `no 5h window · 3 helpers · observe`. `test_band_line_five_hour_bytes_unchanged` asserts today's `BAND_LINE`, `BAND_WEEK_LINE` and `BAND_TWO_LINE`, and that adding `"window": "five_hour"` to each changes nothing.
4. **`lifetime`.** The none branch sits exactly where the band reading is taken today: every environment and settings rule above it is unchanged. `window == none`: `P7` a finite percent and `resetsAt` ahead of now, else `(None, UNKNOWN)`. `P7 >= PLAN` is `5m` with `past plan usage, 7d N%`; else `1h` with `within plan usage, 7d N%`, N formatted as the five-hour branch formats it. A `five_hour` band reads exactly as today. `test_lifetime_none_by_seven_day` covers below PLAN, at PLAN, a reset in the past, and P7 null.
5. **The meter-wait pattern.** The new words are whole words: `week`, `weekly`, `7d`, `seven-day`, `band`, bounded on both sides, so `week's reset` matches and `weekend`, `banded`, `bandwidth` do not. The old alternatives keep their prefix match unchanged. `test_charter_week_wait_is_meter_wait` pins one positive line per word and those three negatives, each through the charter check's real entry.
6. **`test_none_line_reads_as_today_until_s43`** is removed; `test_band_line_none` replaces it. Its `lifetime` assertion moves to `test_lifetime_none_by_seven_day`. No other existing test changes but the version pins; if one must, it is a fork for the report.
7. **The version:** 2.0.0-alpha.30 in all five pins, one bump, last. The branch is merged and NOT installed: S42 and the relay's AR98 install together, and this sits on S42.

## 3. Interfaces (signatures, not prose)

`admission.band_line(b, now=None, columns=0) -> str` and `admissionLine(band, nowMs, id='')` unchanged in shape. `rules.lifetime(env, cwd, band=None, now=None) -> (ttl, why)` unchanged in shape.

## 4. Findings that name this row

None. Read `GUIDE.md` §9 for the packet's shape only.

## 5. Forbidden reads

Transcripts; `~/.local/state`, but the live `admission/band.json`, read-only; every other repo, but `GUIDE.md`.

## 6. Report (under 15 lines)

Commits; tests; how `session.test.ts` was run; forks; anything unmet.
