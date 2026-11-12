# Sitting 2026-11-12-1: agentik-session, g2 (the prompt before an edit of instruction text)

| item | value |
|---|---|
| goal | build packet g2 (R1 to R6): the PreToolUse guard on instruction files and prompt-acting settings, `ask` in a main thread and `deny` elsewhere, fail-open, no knob; the doctor's guard line; records and NICE rows |
| budget | builder: about 90 tool calls; held after review for the owner's attended `auto` test |
| pin | 9bd9571 (alpha.78) on `g2-instruction-guard` in `.claude/worktrees/g2-instruction-guard` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] packet (2b89c1f)
- [x] tests first (c32b025): `tests/test_g2_guard.py`; at the pin `1 error` (no module) under 3.12 and 3.9.6
- [x] R1 to R5 (4720d11): `instructionguard.py`, the hook's call before a helper's call opens, `doctor._check_guard`; alpha.79; the doctor's row order and the readers' table gain the new names
- [x] R6 (2aa137f): SKILL, RUNBOOK, README (+9 B, source 16,382 of 16,384), alpha.80, status `3193`; NICE n105 to n114; n31 to n42 (S4) moved to the overflow for recordlint's bound
- [x] the gate's `make check`: job 20261112-014933-1136, exit 0 in 13 min (3193 passed; floor 3067 passed, 105 skipped); hygiene over main..HEAD 0

## Handover
- Choice: the headless test is `harness.claude_argv` (SessionEnd's reader): `-p`, `--print`, `--print=` anywhere in the argv denies; an unread argv denies (R2's "deny where unsure")
- Choice: the guard row lives in `doctor.run`, not `instructions.rows`, so g1's rows and tests stay as they are
- Choice: the exemption (`tests`, `testdata`, `fixtures`) reads the path below the nearest top level or the user's folder only
- Choice: a tree folder's `.claude/CLAUDE.md` is guarded beside its `CLAUDE.md` (g1's FOLDER_FILES); both `CLAUDE_CONFIG_DIR` and `~/.claude` are the user's folder
- Choice: "the two older ones" of t1 r2 read as its two Observations on behaviour as on main (n108, n109)
- Choice: no g1 finding fixed: the R5 change rewrites none of their lines
- decide, owner: none

## Next act
review, then HELD for the owner's attended test that an `ask` reaches the dialog under `auto`

- exit taken: done; every ruling built, the gate green; nothing pushed, no install
