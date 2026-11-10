# Sitting 2026-11-10-6: agentik-session, gate land (FW4c)

| item | value |
|---|---|
| goal | packet FW4c (`design/packets/fw4c-gate-land.md`): R1 to R6, `gate land` and `land.py`, the job mark and its two doors |
| budget | builder: 200k window, 120k context, 60 tool calls (the packet's); one commit per group |
| pin | 36c84ea (R1 landed, alpha.60); branch `fw4c-gate-land` in `.claude/worktrees/fw4c-gate-land` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [x] the packet committed with this charter (sections renamed to doclint's packet shape, the Q1 ruling added; no ruling word moved)
- [x] tests: T1 to T13 in `tests/test_fw4c.py`, red at 36c84ea: `15 failed` under 3.12.7 and 3.9.6; the ported pair, conftest's line and test_gate's assertion with them
- [x] the verb: R1 to R5 (land.py, the mark, the doors, self_argv); T1 to T13 `15 passed` under 3.12.7 and 3.9.6; with the ported pair, test_gate and the four unedited neighbours `383 passed` under 3.12.7, under 3.9.6 `381 passed, 2 failed` at load 90 (T3's 2 s wall cut the job before land.py's SIGTERM handler; test_land f4's 30 s subprocess timeout), both green alone after
- [x] the texts and the bump: R6 (SKILL one line, RUNBOOK §5 one bullet), NICE n54 to n56 (the packet's three), alpha.63 (main alpha.60; alpha.61 and .62 held by other branches), status line 2758 (collected) by hand, sidecar re-hashed (`shasum -c` OK), source 16,381 B
- [ ] verify: one gate run of `make check`

## Handover
- open by level: none
- Choice (consumer: the reviewer): land.py is the prototype's, byte-checked against hq's scripts/land at 9f394ce: only the docstring's head and paragraph on the job, the `agentik-hq entry 5` cite, USAGE's command name, shebang and `__main__` differ

- Choice (consumer: the reviewer): T3's wall 2 s -> 6 s, since a cut before land.py's SIGTERM handler reads `red gate exit 124` (right by R3) and Python's start took over 2 s at load 90; the check still sleeps 30 s

## While waiting
- none

## Next act
the texts and the bump, then the gate's one run
