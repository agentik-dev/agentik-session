# Sitting 2026-11-17-8: agentik-session, g10-push-guard, the fix of review 2

| item | value |
|---|---|
| goal | the mend of review 2, each behind `agent_id`: a veiled land word (F1), the file commands and a slashed found word (F2), the one `$HOME` cd (F4), `gate run <repo>`'s folder (F5), the `$HOME` folders once a call (F6), the `home` allow group, the NICE rows, the stamp to alpha.135 |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `c35f75b` on the branch (the fix of review 1; main `fd8f3af`) |
| branch | `g10-push-guard`, worktree `.claude/worktrees/g10-push-guard`, the two venvs linked |
| level | S1, packet `design/packets/g10-push-guard.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The failing tests, 5 of 5 red at `c35f75b` (`13acf0c`)
- [x] Items 1 to 5: F1 `25d274e`, F2 `4ad70be`, F4 `e4341ba`, F5 `02659d6`, F6 `1187428`; the g10 and g8 suites 45 passed under both venvs
- [x] Item 6: the `home` group (`7953fe8`); `hygiene --require-private --commits main..HEAD`: 0 hits outside
- [x] Item 7: NICE rows n297 to n302; the packet's §2a pressed and §2b (L6, L7) to stay under its ceiling
- [x] C1 to C3 by review 2's corpora: c1 refuses F3's two, L3's one, L5's one; the 628 main-thread lines match the pin under both interpreters
- [x] Item 8: `make stamp STAMP_VERSION=2.0.0-alpha.135` through the gate, job `20261117-141106-2513` exit 0: alpha.134 to alpha.135, count 4909 to 4914, n242 to n247 to the overflow
- [ ] `make check` through the gate on the stamp's commit

## Handover
- Choices: a wrapper the reader opens (`nice`) runs its git as the command itself, so `nice /opt/x/git "$V"` stays refused; F2's slash rule is for found words. "The one cd" counts cd, pushd and popd before the command.

## Next act
Read the check's job (`agentik session gate status`, the label `g10-check3`); on a red, read its log and fix; on either known chance failure, run it once more.

## Exit
open
