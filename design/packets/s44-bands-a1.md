# Packet S44, Amendment 1: the refuter's round 1 on 5c1a295

| item | value |
|---|---|
| from | the refuter's round 1 on 5c1a295, the coordinator's rulings; parent `design/packets/s44-bands.md`, whose rulings stand but where this moves them |
| pin | 5c1a295 (branch `s44-bands`, alpha.31); worktree `.claude/worktrees/s44-bands` |
| wall | this worktree only; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`; never write under `~/.local/state`; never run a relay verb, or build or run a relay binary; commit by explicit path; stay at `nice -n 10`; this repo is public, so no private repo names |
| may touch | `claude_session/demand.py`, `claude_session/admission.py` (`read_band`), `tests/test_bands.py`, `NICE_TO_HAVE.md`, `RUNBOOK.md`; the README count and its sidecar, as the parent's version act touched them, since `test_status_line_matches_manifest_and_suite` counts the suite; this packet; the parent's charter, `history/sittings/2026-10-30-4-s44.md`, no new one. Nothing under `plugin/` and no version bump: alpha.31 stands |
| acceptance | `.venv/bin/python -B -m pytest tests/test_bands.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; `.venv/bin/python -B -m pytest tests/test_window_mode.py tests/test_admit.py tests/test_admission.py tests/test_band.py tests/test_s35.py tests/test_mod.py tests/test_rules.py tests/test_doctor.py tests/test_install.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; the plugin's tests pass under a 60 s wall; doclint, hygiene and the version check pass |
| verify | the gate, by the coordinator |
| budget | acts: 0 this packet; 1 the tests, red; 2 the code; 3 NICE and docs. 30 tool calls, stop at 80% (commit the act in flight), `claude-opus-5-5`; one commit per act |

## 1. What the source says (the refuter's round 1 on 5c1a295)

- F1, block, `demand.py:181,190`: in a DST fold's second pass, `band` comes from the wall while the first-instant cut is already past, so `until` and `next` land a week late. Repro: rules `Sun 01:30-24:00 best`, else `good`, `demand(2026-11-01T09:15Z)` gives `band: good, until: 2026-11-08T01:30:00-08:00`, and 15 minutes later `band` is `best`.
- F2, block, `cli.py:123` with `admission.py:1289`: `status` now calls `read_band`, which lets RecursionError escape on nesting under `BAND_MAX`. Repro: band.json = `'['*65000`: at bbb3f90 `status` exits 0 with 4 lines; at 5c1a295 exit 1, RecursionError.
- F4, taken, `demand.py:90-92`: a band name of any length and any characters binds.
- Three surviving mutants: `WALK_WEEKS` at 2; `setdefault` becoming assignment; `next > now` becoming `>=`.

## 2. Rulings

1. **F1.** In the second pass read the band the first pass ended on, so a cut happens once, and `until`, `next` and `band` agree. Test with that schedule at 08:15Z, 08:45Z, 09:15Z and 09:45Z on 2026-11-01, in `tests/test_bands.py`. This moves the parent's ruling 3 only for an instant in a fold's second pass; a stamp still reads a fold's first instant.
2. **F2.** Add RecursionError to `read_band`'s except; test through `status`.
3. **F4.** A band name over 32 characters, or holding a character outside letters, digits, `-` and `_`, makes the file bad, as the parent's ruling 2's others do: one note, the shipped file. Tests: a 40000-character name, and `"a\nb\u001b[31m"`.
4. **Pins for the three mutants.** `WALK_WEEKS` at 2: now 2027-03-07 03:00 with the stretch in the gap, and `until` must read 03-21. `setdefault` becoming assignment. `next > now` becoming `>=`.
5. **To `NICE_TO_HAVE.md`, level S4, one line each, keeping the file's shape.** From S44's round: the twins differ on stamps `_stamp` never writes, so `wall` could refuse what `_when` refuses; `status --json` passes a past-end `demand` raw; a dangling symlink at the user path is silent; no real wheel was built offline, only the package-data line and the frozen tree are checked. From S43's round: a `next week` wait hits the meter-wait return before `_red`, so a red charter with that wait exits 0 (`test_s29_meter_wait_keeps_the_exit` is the pin to revisit); hyphens read as boundaries, so `mid-week`, `band-aid` and `7d-old` count as meter waits; numeric corners of `_pct` against `whole` differ (`7d 1e+21%`), unreachable from the writer.
6. **The version.** No bump: alpha.31 stands, and nothing moves under `plugin/`. If something must, name it, and bump nothing without saying so.

## 3. Interfaces

No signature moves. `demand.demand(now, rules, tz, stamp_tz=None)` answers the same keys; the relay's `plan` still reads `demand.band` and `demand.until`.

## 4. Findings that name this row

F1, F2, F4 and the three mutants of §1; the S4s of ruling 5.

## 5. Forbidden reads

Transcripts; `~/.local/state`; every other repo, but `GUIDE.md`.

## 6. Report (under 10 lines)

Commits; the acceptance lines; forks; anything unmet.
