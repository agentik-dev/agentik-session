# Sitting 2026-11-12-6: agentik-session, mt1 model tiers in the profiles

| item | value |
|---|---|
| goal | packet mt1 (`design/packets/mt1-model-tiers.md`): `tiers` in every profile, one table, the user layer's default profile, `set tier.*` and `set cap`, the role check, the start applies the profile; plugin 2.0.0-alpha.90 |
| budget | builder: about 90 tool calls |
| pin | 33a4d85 on main (alpha.89); worktree `.claude/worktrees/mt1-model-tiers`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet committed
- [ ] tests first: `tests/test_mt1_tiers.py`
- [ ] R1 to R7 built
- [ ] version bump in its own commit
- [ ] records: README source and sidecar, RUNBOOK
- [ ] the gate, once, last

## Handover
- (none yet)

## Exit
- (open)
