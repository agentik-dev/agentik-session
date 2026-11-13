# Sitting 2026-11-13-5: agentik-session, ak5 the plug's reads (describe, config, doctor, status)

| item | value |
|---|---|
| goal | brief ak5 phase 1 (packet `design/packets/ak5-plug-session.md`): R1 to R9 |
| budget | builder: about 90 tool calls |
| pin | b92e4e0 on main (2.0.0-alpha.103); worktree `.claude/worktrees/ak5-plug-session`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Packet committed (the contract's sections 2 to 7 condensed into §3: doclint's 9,216 B ceiling)
- [x] `tests/test_ak5_plug.py`, lines 1 to 13 (16 tests), seen red at the pin: 15 fail, line 13 passes there (the pin's describe writes nothing either)
- [ ] `plug.py`, `cmd_describe`, the doctor and status reads (R2 to R9)
- [ ] Acceptance 10 and 14 by hand; acceptance 15 under both venvs

## Handover
- decide, owner: the coordinator (consumer: the packet's reader): the brief asks the contract's sections 2 to 7 copied whole into the packet; doclint holds a packet under 9,216 B, so §3 carries them condensed.

## Next act
- Build `plug.py` and the cli, doctor and status changes.

## Exit
- open
