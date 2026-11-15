# Sitting 2026-11-14-5: agentik-session, land5b `--install` installs what was pushed

| item | value |
|---|---|
| goal | build 1: `gate publish ... --install` and `gate land ... --install` (R1 to R9); build 2, the fix of review 1: F1, F2, F3, F4, F6, F7 (packet §7), each with a test red at `5dd358d` |
| budget | about 90 tool calls a builder, `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `45b975d` (land5-publish's merge, alpha.121); build 2 from `5dd358d` |
| branch | `land5b-install`, worktree `.claude/worktrees/land5b-install`, the two venvs linked |
| level | S3: `design/packets/land5b-install.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] build 1: the packet, the tests, R1 to R9, the stamp; its gate `20261114-140514-1981` exit 0 on `5dd358d`
- [x] build 2: the packet's §7, this file current
- [x] build 2: the tests of §7, red at `5dd358d`: 15 failed, 2 passed (the two not-red guards) of 17
- [x] build 2: F1 (red tree), F2 (the Makefile's text at S), F3 (make install on each call): 59 of 67 green, F4, F6, F7's 8 red
- [x] build 2: F4, F6, F7: 67 of 67; the land files 381 passed (.venv), 257 passed 124 skipped (.venv-floor)
- [x] build 2: NICE n257 to n261 at S4 (the stamp moves S4 rows past the bound)
- [x] build 2: the stamp again (job `20261114-150053-1987`), `2.0.0-alpha.122`, 4768 tests, n193 to n197 to the overflow; the last commit under `plugin/`
- [x] build 2: `make check` once, last, through the gate queue: `20261114-150136-1988` exit 0 on `182649f` (4768 passed; floor 4619 passed, 128 skipped)

## Handover
- Choices inside the rulings: the packet's §3 and §7.
- decide, owner: the coordinator (consumer: review 2): F2's "`--dry-run` starts no process but git" is read as no `make` and no `claude`; the `ps` read R3 and R6 name stays, so a dry run still holds.
- If this sitting is cut: the first unticked line above.

## Next act
None: review 2 by a new adversary.

## Exit
Build 2 done: F1, F2, F3, F4, F6, F7 built, the check green on `182649f`; this commit holds this file alone.
