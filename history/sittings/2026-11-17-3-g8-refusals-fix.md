# Sitting 2026-11-17-3: agentik-session, g8-refusals, the fix of review 1

| item | value |
|---|---|
| goal | the fix of review 1's three findings in `lineguard.py` (F1 the followed variable, F2 the fence, F3 the commit cluster), each with tests seen red first; nine NICE rows from its leads; the stamp and the quick gates |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `c21446a` on `g8-refusals` |
| branch | `g8-refusals`, worktree `.claude/worktrees/g8-refusals`, the two venvs linked |
| level | S1, packet `design/packets/g8-refusals.md` (unchanged) |
| agents | 0 |

## Done-ness
- [ ] F1: tests red at the pin, then the fix
- [ ] F2: tests red at the pin, then the fix
- [ ] F3: tests red at the pin, then the fix
- [ ] Nine NICE rows from review 1's leads
- [ ] `make stamp` through the gate, its paths committed
- [ ] The quick gates through the gate: `make lint doclint hygiene plugin-version-check validate`
- [ ] `scripts/hygiene --require-private --commits main..HEAD` exits 0

## Handover
- The full `make check` job queued before this fix (`20261117-063929-2397`) is not this builder's; its line is read at the end.

## Next act
F1's tests.

## Exit
(open)
