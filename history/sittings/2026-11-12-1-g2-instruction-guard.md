# Sitting 2026-11-12-1: agentik-session, g2 (the prompt before an edit of instruction text)

| item | value |
|---|---|
| goal | build packet g2 (R1 to R6): the PreToolUse guard on instruction files and prompt-acting settings, `ask` in a main thread and `deny` elsewhere, fail-open, no knob; the doctor's guard line; records and NICE rows |
| budget | builder: about 90 tool calls; held after review for the owner's attended `auto` test |
| pin | 9bd9571 (alpha.78) on `g2-instruction-guard` in `.claude/worktrees/g2-instruction-guard` |
| window | 200k |
| agents | 0 |

## Done-ness
- [ ] packet
- [ ] tests first (red at the pin)
- [ ] R1 to R4: the guard, wired into PreToolUse
- [ ] R5: the doctor's guard line
- [ ] R6: records, version, NICE rows (t1 r2 F1 to F3 and two older; g1 F1 to F4)
- [ ] hygiene over the range; the gate's `make check`

## Handover
- decide, owner: none yet

## Next act
the packet

- exit taken: (open)
