# Sitting 2026-09-30-1: claude-code-session, packet S17 (respawn, never compact)

| item | value |
|---|---|
| goal | the plugin's exit words follow entry 17 as amended 2026-09-29: `EXIT_RULE`, the two orchestrator descriptions, SKILL.md's `EXIT:` bullet and overhaul-r1.md:72 say respawn, never compact; two `s17` tests red on main, green after; `make check` 0 |
| budget | 40 turns, 60k context (the packet); land the act in flight at 80%; one commit; never push, amend, rebase, a device, the network, or relay in any form |
| pin | main c319f17 (9f23146 plus the packet); branch and worktree `s17-exit-rule-respawns` |
| window | 200k |
| agents | 0 (a builder spawned by the orchestrator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: `test_s17_exit_rule_never_compacts`, `test_s17_profiles_never_compact` in tests/test_hook_meter.py; red on main c319f17 (2 failed, 33 deselected, exit 1)
- [x] act 2: `EXIT_RULE`, both orchestrator descriptions (ruling 2 verbatim), SKILL.md's `EXIT:` bullet and overhaul-r1.md:72 (quoting the rule); `-k s17` 2 passed; the grep line reads 0; test_hook_meter.py 35 passed; `make check` run once: exit 2, 584 passed, 2 failed, both in test_readme.py (the README count, fixed in act 3); lint, doclint, hygiene and validate pass when run by hand (a6adb81)
- [x] act 3 (fix round, the observer's rulings): ruling 1's words exactly; the s17 tests forbid only the old phrases (red on main c319f17 again: 2 failed); the source status line 584 to 586 and `make readme`; `make check` (below)

## Handover
1. Decided (the observer, a reversible choice): the rule is ruling 1's `EXIT: land the act in flight at a checkpoint, then exit; respawn, never compact`, which matches entry 17's "never compacts". The s17 tests and the grep acceptance forbid only `compact at most once` and `compacts in place`.
2. Widened for the fix round only (the observer): may-touch gains `design/readme/source.md`, `README.md` and `design/readme/rendered.sha256`. The source's count became 586, and `make readme` regenerated the other two (exit 0, the verifier's prose-only PASS). The render also dates the status line 2026-09-30 and rewords 43 README lines of prose.
3. Logged: design/packets/s4-meter.md:23 still quotes the old rule. It is a closed packet, so it is left alone.

- exit taken: goal met; two commits on `s17-exit-rule-respawns` (a6adb81, then the fix round), not pushed; `make check` 0 on the fix round's tree.

## Next act
The orchestrator reviews and merges `s17-exit-rule-respawns`.
