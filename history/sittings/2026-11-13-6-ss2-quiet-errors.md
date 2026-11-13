# Sitting 2026-11-13-6: agentik-session, ss2 an error names the file, the line and the reason

| item | value |
|---|---|
| goal | brief ss2-quiet-errors (a small change, no packet): R1 to R5 |
| budget | builder: about 90 tool calls |
| pin | 5890501 on main (2.0.0-alpha.106); worktree `.claude/worktrees/ss2-quiet-errors`, `.venv`, `.venv-floor` linked |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] Tests first (acceptance 1 to 4), `tests/test_ss2_quiet_errors.py`: 8 of 33 red at the pin (git archive of 5890501): both verb sweeps, the three verbs, SessionStart (user, repo), the unknown-profile control
- [x] R1, R2: scrubbed at the raise, two lines of `resolver.py` (`_parse` through `withheld`; the unknown profile's name withheld); `withheld`, `scrubbed` moved down to the resolver, `plug`'s names kept. No resolver test pinned the old text
- [x] R4: every event of hooks.json fed to `hook <event>`, two shapes, user and repo: SessionStart alone printed the text at the pin
- [ ] R5: seven SUMMARIES sentences, a commit of their own
- [ ] Suite under .venv and .venv-floor; alpha.108 stamped alone, last under `plugin/`; the gate once

## Handover
- (none yet)

## Next act
- R5: the summaries.

## Exit
- (open)
