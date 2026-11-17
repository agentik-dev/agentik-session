# Sitting 2026-11-17-7: agentik-session, g10-push-guard, the fix of review 1

| item | value |
|---|---|
| goal | the review's ten fixes on the push rule, each behind `agent_id`: one reading for a push behind any command (F1 to F3), a verb word the shell expands (F4), the look past quotes (F5), the git dir judged (F7), `-m claude_session.<x>` (F9), a bare repo operand and `$HOME` (L1, F10), a linear loose judge (L9), the door's options (L10), the allow rows, the NICE rows |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `62178d8` on the branch (the first build's head; main `fd8f3af`) |
| branch | `g10-push-guard`, worktree `.claude/worktrees/g10-push-guard`, the two venvs linked |
| level | S1, packet `design/packets/g10-push-guard.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The failing tests, seen red: 9 of 20 red at `62178d8` (fix 1 to 8, and A4's moved line)
- [x] Fix 1 to 8: the push rule, one commit each; 40 of 40 green with the g8 suite under both venvs
- [ ] Fix 9: the allow rows; fix 10: the NICE rows; the packet current
- [ ] `make stamp`, then `make check`, through the gate

## Handover
None yet.

## Next act
The failing tests.

## Exit
Open.
