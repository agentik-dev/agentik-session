# Packet S44: the demand bands, reported and never held

| item | value |
|---|---|
| from | the owner's answers, 2026-10-30: quiet bands preferred, never held; attended work never held; no weekly reserve; a private hq's design record; §1 carries its text |
| pin | bbb3f90 (branch `s43-lines`, alpha.30, refuted PASS, its gate queued; it merges to main before this does); worktree `.claude/worktrees/s44-bands`, branch `s44-bands` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run a relay verb, or build or run a relay binary; not `decide`'s judgement, `window()` or `lifetime` (S42, S43, landed), not the relay (AR98) |
| may touch | `claude_session/bands.yaml` (new), `claude_session/demand.py` (new), `claude_session/admission.py` (`_band_none`, `admit`'s answer, `band_line`), `claude_session/cli.py` (`status`), `claude_session/doctor.py`, `pyproject.toml` (package-data), `plugin/hooks/session.ts` (`admissionLine`), `plugin/hooks/session.test.ts`, `tests/test_bands.py` (new), `tests/test_window_mode.py` (the none-line fixture), `RUNBOOK.md`, `plugin/skills/session/SKILL.md`, `design/admission-r1.md` (amendment lines), `NICE_TO_HAVE.md`, and the version act's pins as 694bf81 touched them; this packet; the charter, `history/sittings/2026-10-30-4-s44.md` |
| acceptance | `.venv/bin/python -B -m pytest tests/test_bands.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on the pin: no such file), and holds the seven names of §1; `.venv/bin/python -B -m pytest tests/test_window_mode.py tests/test_admit.py tests/test_admission.py tests/test_band.py tests/test_s35.py tests/test_mod.py tests/test_rules.py tests/test_doctor.py tests/test_install.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; the plugin's tests pass under a 60 s wall; a built wheel holds `claude_session/bands.yaml` (`.venv/bin/python -B -c "import importlib.resources as r; print(r.files('claude_session').joinpath('bands.yaml').is_file())"` reads `True` from the worktree, and `tests/test_bands.py` pins the package-data line). The whole suite is the gate's |
| verify | the gate, by the coordinator |
| budget | acts: 0 this packet; 1 the tests, red; 2 the schedule and `demand`; 3 band.json, the answer, the twins, `status`, `doctor`; 4 the docs; 5 the version, the README count, the sidecar (last, one bump; 694bf81 is the model). 80 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says (a private hq's design record, quoted)

"The bands are a file, never code: the shipped `claude_session/bands.yaml`, which the owner's `~/.config/agentik/session/bands.yaml` replaces whole (GUIDE §3); read by `claude_session/yamlsubset.py`."

```yaml
tz: America/Los_Angeles   # wall clock, across DST
bands:                    # first match wins; [from, to)
  - {days: Mon-Fri, from: "05:00", to: "11:00", band: avoid,  grade: A}
  - {days: Mon-Fri, from: "11:00", to: "16:00", band: middle, grade: B}
  - {days: Mon-Thu, from: "16:00", to: "23:00", band: best,   grade: B}
  - {days: Fri,     from: "16:00", to: "24:00", band: best,   grade: B}
  - {days: Sat,     from: "00:00", to: "24:00", band: best,   grade: A}
  - {days: Sun,     from: "00:00", to: "20:00", band: best,   grade: A}
  - {days: Sun,     from: "20:00", to: "24:00", band: middle, grade: C}
  - {days: Mon-Sun, from: "00:00", to: "24:00", band: good,   grade: C}   # the nights
```

"Only admission reads it, resolving `demand` at each band.json write; the session line, `status`, the relay's plan and the observer read band.json, and nothing waits for a band. A file that does not parse or leaves an hour unmatched is a `doctor` warning, and the shipped file is used. A `five_hour` login ignores it."

"A `five_hour` entry keeps today's fields and values and never carries `demand`. A `none` entry: `"demand": { "band": "avoid", "until": "<band's end>", "next": { "good": "...", "best": "..." } }`."

"`decide`, `none`: the answer gains `window`, `resume_at` and the band. No unread, stale, wait, deferred or band hold."

"The pacing line, `none`: `no 5h window · 7d 62% · week resets Fri 13:00 · band avoid to 11:00 · 3 helpers · observe`." "`status`: the band and its end, from band.json."

"No reserve: attended or not, all work runs to `ceiling_7d`."

"`demand` is resolved only at band.json writes, so an idle login can show a band past its end; a filing for S44."

Tests the record names: `test_bands_default_covers_168_hours`; `test_demand_mon_0700_avoid_until_1100`; `test_band_never_holds` (no verdict waits for a band, attended or not); `test_none_unattended_runs_to_ceiling_7d`; `test_status_shows_band`; `test_bands_wall_clock_across_2026_11_01`; `test_bad_bands_file_falls_back`.

## 2. Rulings

1. **`demand.py`** holds `schedule(env) -> (rules, tz, notes)` and `demand(now, rules, tz, stamp_tz=None) -> dict | None`, with no import of `admission`. `bands.yaml` is the record's text, byte for byte, loaded by `importlib.resources`. The user file sits under `$XDG_CONFIG_HOME` else `~/.config`; `yamlsubset.load` takes the list of flow mappings as written, so the loader is not touched.
2. **A bad file** is any of: no parse; `tz` no `ZoneInfo` can load; a rule with a bad `days` (`Mon`, `Mon-Fri`, a range running forward), a bad `from` or `to` (`HH:MM`, `to` up to `24:00`, `from` before `to`), or no `band`; an hour of the 168 unmatched. It reads as the shipped file, one note naming it; `doctor` warns with that note; nothing raises. If the shipped file or its zone cannot load, `demand` is None and no reader shows a band.
3. **`demand(now)`**: `band`, the band of the first matching rule at the wall clock; `until`, the next instant the band name changes, walking the wall clock, so Saturday at 09:00 reads Sunday 20:00, not midnight; `next`, for each of `good` and `best`, the start of its next stretch after now, an absent key when the schedule has none, and when now is in that band the stretch after this one. Each is a zoned local ISO stamp in the same zone as `band`'s other stamps, `_stamp`'s form, not the schedule's zone. A wall time a DST gap skips reads as the first instant after the gap; a fold reads its first instant. The cost is at most one file read and a bounded walk per band.json write; nothing caches on disk.
4. **band.json.** `_band_none` carries `demand` when it is not None. A `five_hour` entry never reads the file: pin that with a user file that would warn, the entry byte for byte today's and no note. Admission alone calls `demand`.
5. **The answer.** A `none` answer gains `band`, the band name or null. A `five_hour` answer's keys are unchanged. The `verdict` line is unchanged. `test_band_never_holds` drives `decide` across every verdict in both modes with the schedule in each band, attended and unattended, and asserts the verdict never moves; `test_none_unattended_runs_to_ceiling_7d` asserts `admitted` up to `ceiling_7d` and `denied` at it.
6. **The line.** Both twins insert the band part after the week's reset, S43's seam: `band avoid to 11:00` when `until` falls within 24 hours of `at`, else `band best to Sun 20:00`, S43's weekday helper. A `demand` with no band, a stamp `wall` refuses, or an `until` not after now, leaves the part out, which answers the filing. One fixture pins both twins, as S43's `BAND_NONE_CASES` does; add the corners there. A `five_hour` line is byte for byte unchanged, with a stray `demand` in the entry too.
7. **`status`.** On a `none` band with `demand`, one more line after the existing ones: `band: avoid to 11:00; next good 23:00, best 16:00`, in the same time form as ruling 6, listing only a `next` present and in the future, and dropping the clause when none is; on a `five_hour` band, or none, today's bytes. `--json` carries the session band's `window` and `demand` only on `none`.
8. **`doctor`.** A warning, never a failure, for a bad user file; silent with no user file and on a good one.
9. **One leftover rides this packet, S43's refuter F4:** removing S43's pin left no test on a five-hour entry with `P` null and `bound` seven_day, whose line reads `5h no reading · week resets ...`. Add that entry, no `window`, to the fixture in both twins, so a mutant `window == none or (P is None and bound == seven_day)` goes red.
10. **The version:** 2.0.0-alpha.31 in all five pins, one bump, last. Merged and NOT installed: S42 and the relay's AR98 install together.

## 3. Interfaces

`demand.schedule(env) -> (rules, tz, notes)`; `demand.demand(now, rules, tz, stamp_tz=None) -> {band, until, next} | None`; `admission.admit` on `none` answers `{verdict, mode, text, peak, window, resume_at, band}`; band.json's `none` entry gains `demand`.

## 4. Findings that name this row

None. The relay's `plan` reads `demand.band` and `demand.until`: those two keys are a contract.

## 5. Forbidden reads

Transcripts; `~/.local/state`, but the live `admission/band.json`, read-only; every other repo, but `GUIDE.md`.

## 6. Report (under 15 lines)

Commits; tests; forks; anything unmet.
