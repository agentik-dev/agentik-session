# Sitting 2026-11-14-5: agentik-session, land5b `--install` installs what was pushed

| item | value |
|---|---|
| goal | `gate publish ... --install` and `gate land ... --install`: after the publish turn, install the repo's plugin (marketplace update, plugin update) and its `make install`, only where main is pushed, held while a relay run, an unattended run or a gate job of the repo is live (R1 to R9) |
| budget | about 90 tool calls (the second builder's, the first cut after its first commit), `claude-opus-5-5`; checkpoint at 80% |
| pin | main at `45b975d` (land5-publish's merge, alpha.121) |
| branch | `land5b-install`, worktree `.claude/worktrees/land5b-install`, the two venvs linked |
| level | S3: `design/packets/land5b-install.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet and this charter
- [x] the tests (`tests/test_land5b_install.py`), red at the pin: 50 failed of 50
- [x] R1 to R8: `deliver.py`, `publish.main`/`after_land`'s `install`, the parsers and `_gate_land`; 50 of 50 green under both venvs; the packet reshaped to doclint's six sections
- [x] R9: SKILL.md's line
- [ ] the stamp `2.0.0-alpha.122`, its files the last commit
- [ ] both scans exit 0; `make check` once, last

## Handover
- Choices inside the rulings: the packet's §3.

## Next act
The stamp `2.0.0-alpha.122` (its files alone, the last commit), then both scans and `make check` once through the gate queue.

## Exit
(open)
