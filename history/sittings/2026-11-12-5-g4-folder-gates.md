# Sitting 2026-11-12-5: agentik-session, g4 the folder layer of the edit gates

| item | value |
|---|---|
| goal | packet g4 (`design/packets/g4-folder-gates.md`): the folder layer of the edit gates, one glob grammar for all three layers, refused folder lines, the folder list gated, `gates` prints three layers; plugin 2.0.0-alpha.87 |
| budget | builder: about 90 tool calls |
| pin | 8d676ce on main (alpha.86); worktree `.claude/worktrees/g4-folder-gates`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet committed
- [x] tests first: `tests/test_g4_folder_gates.py`, red at the pin: 36 failed, 10 passed (7a7244a)
- [x] R1 to R7 built (41492b0): g4 + g2b 168 passed (3.12); with hooks, doctor, cli, bare_machine 446 passed, 3 skipped (3.9.6)
- [x] records: RUNBOOK's edit gates section (three layers, the grammar, R8's real-path line), README source 16380 B and README, sidecar by shasum, 3315 tests, plugin alpha.87, `.hygiene-allow` two rows
- [x] the coordinator's ask: main's red mod test (gate 1197) fixed in the test, 7329338, plugin alpha.88
- [x] the gate's `make check`, once, last: 20261112-154703-1214 on 7329338, exit 0 in 12 min (3315 passed; floor 3189 passed, 105 skipped; mod 196 tests, 0 fail; readme fresh)

## Handover
- Choices: the walk starts above the checkout (above the member for a worktree), so a list in a folder inside a checkout (a fixture) is neither read nor gated; a checkout at or above home counts as none for the walk; a `~` line in a checkout's list now matches nothing too (R4's one predicate).
- decide, owner: none.

## Next act
- None for this builder: the coordinator reviews and lands `g4-folder-gates`.

## Exit
- Done: every ruling built, gate 1214 green on 7329338; the hand-back sent to the hq coordinator.
