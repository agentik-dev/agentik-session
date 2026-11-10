# Sitting 2026-11-10-8: agentik-session, wfd (the Workflow tool denied outright)

| item | value |
|---|---|
| goal | build packet wfd (R1 to R6, tests T1 to T8): every Workflow call denied with one line, the script checker removed, the Fable rule kept |
| budget | builder: 200k window, 180k context; packet: 60 tool calls, 120k; doclint's five rows |
| pin | a300bff (alpha.67) on `wfd-workflows-denied` in `.claude/worktrees/wfd-workflows-denied` |
| window | 200k |
| agents | 0 |

## Done-ness
- [ ] packet (headings reshaped to doclint's six sections, text unchanged) and this charter
- [ ] tests first: `tests/test_wfd.py` red at the pin under both pythons
- [ ] the rule: `_spawn_rule`'s Workflow branch denies first; `workflowguard.py` keeps `family`, `FAMILIES`; test_wfg and fixtures trimmed
- [ ] SKILL, RUNBOOK, README source and sidecar; NICE closed rows
- [ ] alpha.68, the status line's collected count
- [ ] the named files under both pythons; doclint, recordlint, the version check; the whole `tests/` at 3.12

## Handover
- none yet

## Next act
the packet commit, then `tests/test_wfd.py`

- exit taken: (open)
