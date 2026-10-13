# Sitting 2026-09-24-3: claude-code-session, s13b-conventions-r10 (S13 part B: bounded, doctor, README)

| item | value |
|---|---|
| goal | S13 §2 part B, rulings 6 to 10: `bounded` exits 128+signum on a signal without a traceback (d12); the doctor drops `--max-turns` from its flag list and reports the meter hook; conventions §5 keeps the turns line; the README says 840 s; overhaul-r1 §4 and plan row 23 record it |
| budget | `--max-turns` 80 (the 80% point at 64), 140k context; commit per act; never push, amend, rebase, a device; no `make install` |
| pin | branch s13b-conventions-r10 off main fc49627 (s13a already merged there, so act 0's merge is a no-op); `.venv` a symlink to the main checkout's |
| window | 200k |
| agents | 0 (the builder works alone) |

## Done-ness
- [x] act 1: bounded on a signal (ruling 6)
- [x] act 2: doctor, flags and meter-hook (ruling 7); conventions §5 (ruling 8)
- [x] act 3: the record (overhaul-r1 §4, plan row 23); source 840 s; `make readme` (ruling 9, last)
- [x] `make check` 0 at every act, 447 passed; tree clean

## Handover
- decided: act 0's merge was a no-op: s13a is already on main at fc49627, where this branch starts. Consumer: none
- decided: `bounded` ignores TERM, INT and HUP once the handler starts, so a second signal cannot start a second cut. Every `killpg` in `cut` and `kill_group` tolerates the lookup and permission errors (`kill_group` already caught `OSError`, which covers both). Consumer: packets-37
- decided: the README pins 447 tests and the render comes only at close, so each act held the count by folding: `test_exit_passthrough` into the sigterm test, `test_claude_lacking_a_flag` into the max-turns test, and `test_plugin_without_its_hook` into the meter-hook test. Consumer: none
- decided: the meter-hook line sits after `meter`, so the doctor now prints 14 lines. Its detail starts `live:` or `not live:`. Consumer: the owner, who reads the doctor
- decided: plan row 23's dependency is S13a (main fc49627). Consumer: the owner
- `make readme` rendered in one round. The model reworded 43 of the README's lines; the meaning checks passed and the sha is fresh. Consumer: the owner's merge review
- for packets-37: bounded `e343b094`, hygiene `d63d0ffb`, doclint `d5957c6c`; the tests that travel are `tests/test_bounded.py`, `tests/test_doclint.py` and `tests/test_hygiene.py`. Conventions is 9,018 of 9,216 bytes
- no open fork
- exit taken: goal met; `make check` exit 0; four commits, not pushed; no NEXT; about 30 turns, about 70k context

## Next act
The owner merges s13b-conventions-r10; packets-37 re-syncs the three scripts.
