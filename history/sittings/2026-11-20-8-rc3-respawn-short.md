# Sitting 2026-11-20-8: agentik-session, rc3-respawn-short, build 1

| item | value |
|---|---|
| goal | pl2 R7's respawn line at PostToolUse in three forms, the first that fits (R1); the chained CHECKPOINT line makes room for the short form (R2); every other output the pin's (R3); respawn-r1 §3.3 and NICE n346, n347, n352 (R4); the gc1 allow rows gone (R5); the stamp and one check |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `d7e53a2` on main (gc1 landed, 2.0.0-alpha.149) |
| branch | `rc3-respawn-short`, worktree `.claude/worktrees/rc3-respawn-short`, the two venvs linked |
| level | S3, packet `design/packets/rc3-respawn-short.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [ ] The packet, with the baseline measured at the pin
- [ ] The failing tests in `tests/test_rc3_respawn_short.py`
- [ ] R1 to R3: `hooks.py` `_with_respawn`, `_checkpoint_out`, `_post_meter`, `_post_tool_use`
- [ ] R4: respawn-r1 §3.3's sentence; NICE n346, n347, n352 leave
- [ ] R5: the allow rows
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- Choices: listed in the packet's §4 as they are made.

## Next act
The packet.

## Exit
