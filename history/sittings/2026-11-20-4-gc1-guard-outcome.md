# Sitting 2026-11-20-4: agentik-session, gc1-guard-outcome, the first build

| item | value |
|---|---|
| goal | where the edit gate cannot read a Bash line, it records the gated files' hashes before and compares after: a change is one `changed` log line, said once, counted by doctor (R1 to R6); the runbook and the NICE (R7); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `0f618ff` on main (alpha.145) |
| branch | `gc1-guard-outcome`, worktree `.claude/worktrees/gc1-guard-outcome`, the two venvs linked |
| level | S3, packet `design/packets/gc1-guard-outcome.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] The packet, with the pin's figures (Pre 0.37 ms, Post 0.12 ms; 400 unread lines +52,873 B)
- [ ] The failing tests, `tests/test_gc1_outcome.py`
- [ ] R1 to R6: the call's file, the Post compare, said once, the leftovers, the log and doctor
- [ ] R7: the runbook, six NICE rows tidied, seven in
- [ ] `make stamp`, then `make check` through the gate

## Handover
- Choices: the packet's §4.

## Next act
The failing tests.

## Exit
