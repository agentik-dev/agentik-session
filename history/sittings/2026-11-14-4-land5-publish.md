# Sitting 2026-11-14-4: agentik-session, land5 one call proves main green, scans and pushes it

| item | value |
|---|---|
| goal | `gate publish <repo>... [--dry-run]` and `gate land --push`: refuse a caller that is no main sitting, prove main's head checked green from the gate's own results, run the scans, push that sha (R1 to R10) |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `1dbef66` (fk3-session, alpha.118) |
| branch | `land5-publish`, worktree `.claude/worktrees/land5-publish`, the two venvs linked |
| level | S3: `design/packets/land5-publish.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet
- [x] the tests, red at the pin: 58 of 58 at 1dbef66 (`invalid choice: 'publish'`, `--push` unrecognized)
- [ ] R1 to R8: `publish.py` and the verb
- [ ] R9: `gate land --push`
- [ ] R10: help, SKILL.md, two NICE rows
- [ ] the stamp, through the gate queue
- [ ] `make check`, once, last; both scans

## Handover
- none yet

## Next act
R1 to R8: `plugin/lib/claude_session/publish.py`, the verb in `cli.py`.

## Exit
Open.
