# Sitting 2026-11-12-4: agentik-session, g2b the edit gates

| item | value |
|---|---|
| goal | packet g2b (`design/packets/g2b-edit-gates.md`): the guard rewritten as edit gates (lists, deny in every mode), g3 on Bash, `gates` and `gates write`, the doctor's row; plugin 2.0.0-alpha.86 |
| budget | builder: about 90 tool calls |
| pin | 054cfc5 on `g2-instruction-guard`; worktree `.claude/worktrees/g2b-edit-gates`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet committed
- [x] tests first: `tests/test_g2b_gates.py`, red at 3e1f8ad, 69 failed, 32 passed (04fc06e); g2's guard tests removed
- [x] acceptance 1 to 6 green at once (the module is one rewrite): 101 passed in `tests/test_g2b_gates.py`; with g1, hooks, doctor, cli, bare_machine, wfd, wfg, n33: 3.12 and 3.9.6 green; plugin 2.0.0-alpha.83
- [x] records: RUNBOOK's edit gates section, the session skill's paragraph, README alpha.84 and 3248 tests, `.hygiene-allow` three rows
- [x] the gate: 20261112-095800-1166 exit 2 (README source 16406 B over its ceiling, fixed f67ea6e); 20261112-100428-1168 exit 2 with every test green (3248 passed; floor 3122 passed, 105 skipped) and only plugin-version-check asking a bump for the skill's paragraph: alpha.84 committed, `plugin-version-check` clean, the gate not rerun (the tool-call bound); the next gate runs after me

- [x] review r1 (`REFUTE-2026-11-12-g2b-r1.md`): F1 (a subshell's `cd`, `popd`) and F6 (an unresolved Bash target logs one `open` line) fixed; tests red at f1d4de5 (10 failed), green after (112, 3.12 and 3.9.6); alpha.85; README 3259 tests. Gate 20261112-101647-1169 on f1d4de5 exit 2 (the worktree changed under it: 3248 != 3259); gate 20261112-102746-1170 on 1c101a6, a still worktree: exit 0 in 656 s (3259 passed; floor 3133 passed, 105 skipped)
- [x] hardening round (`REFUTE-2026-11-12-g2b-r2.md`, three regressions): a quoted or escaped paren is masked before the lexer (F1); a `case` pattern's paren is no edge (F2); `pushd`'s stack saved and restored with the folder at `(` and `)` (F3); an unmatched `)` leaves the folder unknown. Tests red at 80203bd (9 failed), green after (122, 3.12 and 3.9.6); alpha.86, README 3269 tests; gate 20261112-104403-1173 on a484316, a still worktree: exit 0 in 650 s

## Handover
- Choice: `popd` returns to its own `pushd`'s folder when the line holds one, else the folder is unknown (the coordinator's None); so `pushd docs; popd; printf x >> CLAUDE.md` denies
- Choice: a Bash target with `$`, a glob or an open quote passes with no log line (a form not named); an Edit target that cannot be resolved keeps g2's `open` line
- Choice: `gates write` with neither flag previews; a gated draft is refused; a new block or a dropped one counts as a changed block line
- Choice: `rm -rf` of a whole checkout (a worktree's cleanup) is not a list file's removal; `rm -rf .claude` inside one is
- decide, owner: none

## Next act
the owner's `auto` test (held); then landing

- exit taken: done at the tool-call bound; acceptance 1 to 6 green, the last gate's tests green, its one red (the version check) fixed and not rerun; nothing pushed, no install
