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
- [x] F1: tests red at the pin (`f0147e8`), then the fix: `_unsure` reads the line's text between the assignment and the sweep's word; the assigned folder is judged always, the folder so far beside it where the scope may change
- [x] F2: tests red at the pin (`f0cb6c7`), then the fix in `_fence`
- [x] F3: tests red at the pin (`bac4601`), then the fix: `u` and `S` end a commit cluster and take no next word
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
