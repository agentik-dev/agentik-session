# Sitting 2026-11-13-7: ss4-quiet-values (builder)

| item | value |
|---|---|
| goal | five more places stop printing a layer file's value or key (R1 to R6) |
| budget | about 90 tool calls; checkpoint at 80% |
| pin | `ss2-quiet-errors` at `5792e6e` |
| branch | `ss4-quiet-values`, worktree `.claude/worktrees/ss4-quiet-values`, the two venvs linked |
| level | S1, a small change: no packet |

## Done-ness per act
- [x] tests first, red at the pin (acceptance 1 to 6): 32 of 43 red at 5792e6e
- [x] R1 the window note withholds its value
- [x] R2 the reconciler's `tree` and `record` name the kind
- [x] R3 the overlay's key withheld where `yamlsubset.dump` raises (no caller needs it)
- [x] R4 the gate's log withholds its value
- [ ] R5 the unknown profile's list: shipped names, then `and N more from <file>`
- [ ] R6 the sweep, NICE rows, the stamp `2.0.0-alpha.110`
- [ ] the gate, once, at the end; the commit scan

## Handover
Next act: R5, the unknown profile's list.

## Exit
(open)
