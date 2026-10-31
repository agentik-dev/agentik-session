# Packet S42: a window mode per account

| item | value |
|---|---|
| from | the owner, 2026-10-30, "the Max plans still have the 5 hour limit and I still intend to use the Max plans as well as the Ultra plans, so keep the logic"; a private hq's design record; §1 carries its text |
| pin | 76d8e5c (main, alpha.28); worktree `.claude/worktrees/s42-window`, branch `s42-window` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run a relay verb, or build or run a relay binary; not the pacing lines or `lifetime` (S43), `bands.yaml` or `demand` (S44), the relay (AR98); S42 and AR98 install together |
| may touch | `claude_session/admission.py`, `claude_session/rules.py`, `claude_session/resolver.py` (Amendment 1), `tests/test_window_mode.py`, `tests/test_band.py` (three named tests), `tests/test_s35.py` (two named tests), `tests/test_admit.py` (two named tests), `RUNBOOK.md`, `plugin/skills/session/SKILL.md`, `design/admission-r1.md` (amendment lines), `NICE_TO_HAVE.md`, `claude_session/__init__.py` (the version lines), `pyproject.toml` (the version), `plugin/.claude-plugin/plugin.json` (`version`), `tests/test_doctor.py` and `tests/test_install.py` (the pins), `README.md` and `design/readme/source.md` (status and count), `design/readme/rendered.sha256`, `design/packets/s42-window-mode.md`, `history/sittings/*.md`, `history/sessions/NEXT` |
| acceptance | `.venv/bin/python -B -m pytest tests/test_window_mode.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on 76d8e5c: no such file; sixteen new names); `.venv/bin/python -B -m pytest tests/test_admit.py tests/test_admission.py tests/test_band.py tests/test_s35.py tests/test_measure.py tests/test_mod.py tests/test_resolver.py tests/test_rules.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on 76d8e5c: 435 passed); `git diff 76d8e5c -- tests/test_admit.py tests/test_band.py tests/test_s35.py \| grep -c '^@@'` is at most 7; `grep -c '"version": "2.0.0-alpha.29"' plugin/.claude-plugin/plugin.json` reads 1 (on 76d8e5c: 0); `grep -c 'v2.0.0-alpha.29' README.md design/readme/source.md` reads 1 and 1 (on 76d8e5c: 0 and 0); `grep -c 'Amended 2026-10-30 by packet S42' design/admission-r1.md` reads 2 (on 76d8e5c: 0); `grep -c "$(printf '\342\200\224')" design/packets/s42-window-mode.md` reads 0 |
| verify | `make check`, by the coordinator through the gate, one `make` at a time on this Mac |
| budget | acts: 0 this packet; 1 the tests, red; 2 the code; 3 the docs; 4 the version, the README count, the sidecar (last, one bump). 90 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says (a private hq's design record, quoted)

"Each account carries a window mode. **`five_hour`**: every behaviour of today, for Max and unverified Ultra. **`none`**: no five-hour window; it stops pacing against five hours, keeps the weekly guard and reports the demand band. admission.py alone works the mode out and writes it into band.json and every verdict answer. In doubt, `five_hour`."

"**Nothing waits for a band.** Every request is judged on its window and `ceiling_7d` alone."

"**Four mode-free fixes**: with no five_hour reading, a fresh seven_day at or above `ceiling_7d` is `denied`; a request with no rateLimits is judged on the current login (the key of the newest keyed reading); band.json's top level is the current login's band, not a mix; an entry with a null kind or percent is skipped, not refused."

**Detection**, `window(rows, key, now, settings) -> "five_hour" | "none"`: "1. A counted observation is a reading or spawn row for the key whose list holds seven_day at a finite percent and a future `resetsAt`, and no entry of kind five_hour. An admit request is not evidence. 2. A list carrying five_hour is any list for the key with an entry of kind five_hour, whatever its percent, seven_day or not. An empty list, or one with neither kind, counts neither way. 3. `none` when, after the key's newest list carrying five_hour, one session holds two counted observations at least 30 minutes apart with seven_day up by at least one whole point from the earlier to the later. Otherwise `five_hour`. 4. `window` is stateless: recomputed from the rows at each call, with no stored mode. One list carrying five_hour switches back; a refill switches nothing. 5. On `none` the key's earlier five_hour readings are ignored: no frozen P, no `stale`, no `wait`. 6. The override: `session.admission.window: auto | five_hour | none` (default `auto`), and `windows: {Wed-1500Z: none}` per login. The slot is the weekday and minute of the seven_day `resetsAt`."

**band.json**: "Each account entry gains `window` and `slot`. `accounts` is written with two or more keys, as today, or when any key is `none`. The top level is the current login's entry. A `five_hour` entry keeps today's fields and values." A `none` entry: `window, slot, P: null, peak: null, room: null, P7, ceiling_7d, resetsAt, until (each the week's reset), bound: seven_day, running, mode, at`; `fit`, `project` skipped.

**`decide`**: `five_hour`: "ruling 4's order unchanged, plus the fixes; the answer gains `window` and `resume_at` (the five-hour reset; on a weekly denial, the week's reset)". `none`: "`denied` at P7 ≥ `ceiling_7d`, for all work; else `admitted`; the answer gains `window`, `resume_at` (the week's reset). No unread, stale, wait, deferred or band hold".

## 2. Rulings

1. **The tests the record changes**, and no other: `test_band_on_a_synthetic_ledger_matches_a_hand_count`, `test_no_five_hour_reading_is_mode_and_at_only` ([none], [past-reset]), `test_record_rewrites_band_json_atomically_and_0600` for `window` and `slot`; `test_s35_two_accounts_each_session_draws_its_own_window`, `test_s35_a_session_with_no_account_draws_the_top_level` for the top level; `test_no_five_hour_reading_is_unread`: seven_day 98 alone is `denied`, neither window stays `unread`. A seventh the record missed, `test_admit_appends_one_verdict_line_and_prints_the_answer`'s list gains `window`, `resume_at`; `session.ts` reads named keys only.
2. **What a `none` account's line reads until S43**: `5h no reading · week resets HH:MM (h:mm), 5h HH:MM · 3 helpers · 7d 62% · observe` (the week's reset), `band_line` unedited; `rules.lifetime` answers `(None, unknown)`.
3. **The band in the answer** comes with `demand` in S44: S42's answer gains `window` and `resume_at` alone. The `verdict` line is unchanged.
4. **Forks decided here, reversible**.
   - `rules.admission` carries `window` and `windows` only when set, so `test_the_defaults` stays green unchanged; `window()` reads them with defaults [`settings`].
   - "A null kind or percent" is a key present and null; a key absent stays refused, so `test_admission`'s and `test_measure`'s absent-percent cases stay green unchanged. The module sends absent as null [`rate_limits`, `measure.shape`].
   - A request with no rateLimits is judged on its session's own key when it has one, else on the current login, so `test_s35_a_verdict_projects_from_its_own_account` stays green unchanged; a relay ask has no readings [`scoped`].
   - A five_hour list whose session has no key counts for every key: it only delays `none`, and in doubt, `five_hour` [`window`].
   - A pair's earlier observation must fall strictly after the newest five_hour list; one in the same second is not counted [`window`].
   - `resume_at` is null on `unread`, `stale` and `wait`, or on a `none` account with no fresh week; a zoned local ISO time, `band`'s form [AR98's `Reset`].
   - A slot's value wins over `window`; a bad slot or `window` reads unset, with one note. A key the YAML subset cannot read (`Wed 15:00Z`) is refused by the loader [`rules.admission`].
   - An override with no key: `window: none` still reads `none`; `slot` is null [`band`].
5. **The version:** 2.0.0-alpha.29 in all five pins, one bump, last.

## 3. Interfaces (signatures, not prose)

`admission.window(rows, key, now, settings) -> str`; `admission.slot(key) -> str | None`; `admission.band(rows, now, settings, tz=None, key=None, mode=None)`; `admission.admit` answers `{verdict, mode, text, peak, window, resume_at}` (and `notes`); `resolver.window_override(env) -> dict`.

## 4. Findings that name this row

None.

## 5. Forbidden reads

Transcripts; `~/.local/state`, but the live admission ledger, read-only; every other repo, but `GUIDE.md`.

## 6. Report (under 15 lines)

Commits; tests; the live ledger through `window()`; forks; anything unmet.

Amendment 1 (2026-10-30, refuter round 1 on 694bf81): F1 a relay ask's stale gate also reads keyless sessions' lines (`_gate_lines`), so one spawn at a time holds across logins; the projection and keyed sessions do not. F2 a session with no resolved file reads `window` and `windows` alone from the user layer's `defaults.admission`, so band.json stops flipping on that override; a repo-layer one binds only sessions resolved with it. Tests for the rule's five surviving mutants. Nothing under `plugin/`: alpha.29 stands.
