# Sitting 2026-11-09-3: agentik-session, the wait rule's text and the charter's reds (FW1a)

| item | value |
|---|---|
| goal | packet FW1a (`design/packets/fw1a-wait-rule.md`): R1 to R11, the wait's FULL line and STALLED, the S4 and fill words, the bare close's refusals; alpha.53 |
| budget | builder: 200k window, 140k context, 90 tool calls; one commit per group |
| pin | c1b7359 (S54 landed, alpha.52); branch `fw1a-wait-rule` in `.claude/worktrees/fw1a-wait-rule` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] charter written at open: this file
- [x] the packet committed with this charter
- [ ] tests: T1 to T10 in `tests/test_fw1a.py`, red at c1b7359
- [ ] the code: R1 to R4 and R11 (charter.py, cli.py), R5 to R7 (rules.py, profiles.yaml), R8's edits
- [ ] the texts: R10
- [ ] the bump: R9, alpha.53; NICE rows
- [ ] verify: the gate, once

## Handover

## Next act
the tests of the acceptance table, each shown red
