# Sitting 2026-11-10-8: agentik-session, wfd (the Workflow tool denied outright)

| item | value |
|---|---|
| goal | build packet wfd (R1 to R6, tests T1 to T8): every Workflow call denied with one line, the script checker removed, the Fable rule kept |
| budget | builder: 200k window, 180k context; packet: 60 tool calls, 120k; doclint's five rows |
| pin | a300bff (alpha.67) on `wfd-workflows-denied` in `.claude/worktrees/wfd-workflows-denied` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] packet (526c79a): headings reshaped to doclint's six sections, text kept but one cross-reference (§4 is now "What changes" under §3)
- [x] tests first (767357d): `tests/test_wfd.py`, 20 cases; at the pin `18 failed, 2 passed` under 3.12.7 and 3.9.6 (T6, T7 pass, as they should)
- [x] the rule (44104a5): `_spawn_rule` returns `WORKFLOW_DENY` first; `_script_of` gone; `workflowguard.py` keeps `family`, `FAMILIES`; test_wfg keeps T7 (four), T10, T17 unedited; the 19 fixtures gone. +38, -1189
- [x] SKILL's spawn rule at six lines, RUNBOOK's passage; NICE n61 closed, n68 added (58ab26c)
- [x] alpha.68, README hook line, status line `2836` collected, sidecar re-hashed, `-c` OK (1553f36)
- [x] test_wfd + test_wfg `26 passed`; hooks, doctor, precompact, mod, s49, n33 `469 passed`, both pythons; doclint 0, recordlint 0 (57 rows), version check 0; the acceptance grep empty; hygiene, tree and range, 0
- [x] the whole `tests/` at 3.12.7: `2836 passed, 1 warning in 428.16s`

## Handover
- Choice: the Workflow deny carries no `systemMessage`, so its output is the R1 line and nothing else; Agent and Task denies keep theirs
- Choice: T8's script is 256,000 B, under the pin's 256 KiB cap, so the pin's guard read it (39 ms against 1.6 ms, red)
- Choice: T5 reads `fix the script` case-folded and T1's name avoids the removed helper's, so the acceptance grep stays empty
- Choice: test_wfg had no standalone `family` test; T17 patches `family` and stays; no fixture reused
- Choice: n58 and n60 serve the Fable rule and stay open; the packet's two never-built items (the spend mix's workflow count, a live cut) are no row here
- Choice: README's hook line names the deny (+9 B): the source at 16,379 of 16,384 B, so n1's room is 5 B
- decide, owner: none

## Next act
the coordinator's landing (its `make check`); nothing else

- exit taken: done; the packet built and committed; nothing pushed, no gate, no install
