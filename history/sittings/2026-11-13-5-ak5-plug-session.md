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
- [x] `plug.py`, `cmd_describe`, the doctor and status reads (R2 to R9); no old test changed
- [x] Acceptance 10 (four verbs and `doctor`'s text the pin's, byte for byte) and 15 (306 passed; floor 303, 3 skipped)
- [x] Acceptance 14 by hand: the suite reads `ok` true, line 86, `edit`; `session answers 46 settings 0 changed`; `config session` 0.16 s
- [x] The whole suite under .venv once: 3990 passed; `test_hook_meter`'s status pin (and `test_isolation`, which runs it) changed for R8's two keys; `test_readme`'s count (4015 to 4031) is phase 2's

## Handover
- decide, owner: the coordinator (consumer: the packet's reader): the brief asks the contract's sections 2 to 7 copied whole into the packet; doclint holds a packet under 9,216 B, so §3 carries them condensed.
- `repo` and `plugin` are constants a test holds equal to the manifest: a JSON read in `plug.py` is a new reader `test_bare_machine.py` refuses, and that file is outside this row.
- decide, owner: the coordinator (consumer: review 1): `tests/test_hook_meter.py` lies outside the brief's file list; its one line pinned `status --json` equal to meter.json, a status read's first key, which acceptance 15 lets change.

## Next act
- Phase 2 on the coordinator's word: the version, README's status line (the suite's count), `design/readme/`.

## Exit
- Phase 1 done: R1 to R9 built, acceptance 1 to 15 green; no version, no merge, no gate job.
