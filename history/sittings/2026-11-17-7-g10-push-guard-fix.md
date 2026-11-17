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
- [x] Fix 9: the allow rows; fix 10: NICE rows n286 to n296, n230 to n241 (S4) to the overflow; the packet current (§2a, B1 to B5)
- [x] B1, B2, B3 by the review's probes: 270 main-thread lines give the pin's decision, mark, log and `looks` under 3.12 and 3.9.6
- [x] `make stamp` through the gate: job `20261117-133059-2489`, exit 0; the count 4901 to 4909, alpha.134 kept (`cbb7b01`)
- [ ] `make check` through the gate on `cbb7b01`: job `20261117-133338-2490`, running at the tool-call bound

## Handover
- decide, owner: the coordinator; consumer: the landing's `hygiene --commits`. Commit `86aa679` holds one `home` hit in `tests/test_g10_push_guard.py` (a test comment naming the home's code folder, reworded in `2b90758`): a `home` group on that file's row, or a squash at landing. The tree scan is clean.
- Choices: the printers (packet §2a) pass their words; any other command's are read, so `xargs echo git push` refuses. A word with a space is no command word and, at a verb's place, is the push. The door's leading flags are read past.

## Next act
Read job `20261117-133338-2490`: `agentik session gate wait 20261117-133338-2490 --strict`. On a red, read its log and fix; on either of the two known chance failures, run the check once more.

## Exit
Fix 1 to 10 built and committed; the g10 and g8 suites green under both venvs; the check queued on `cbb7b01`, running at the tool-call bound.
