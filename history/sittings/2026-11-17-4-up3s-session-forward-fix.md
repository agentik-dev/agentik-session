# Sitting 2026-11-17-4: agentik-session, up3s-session-forward, the fix of review 1

| item | value |
|---|---|
| goal | review 1's ruling: F1 (the doctor's newer note names install-cli's keeping only where it keeps), L3 (the command page names `--force` and the kept line), L1 and L2 one NICE row |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `300f905` on this branch (2.0.0-alpha.131) |
| branch | `up3s-session-forward`, worktree `.claude/worktrees/up3s-session-forward`, the two venvs linked |
| level | S3, packet `design/packets/up3s-session-forward.md` (unchanged) |
| agents | 0 |
| exit | every ruling built and committed; the quick gates' job queued behind another worktree's key at the tool-call bound |

## Done-ness
- [x] the first build's third check, job `20261117-060100-2387`, read before the first edit: exit 2, cut at the 1800 s wall in the floor pass, its first pass green (4866 passed), head `300f905`
- [x] F1's tests: three doctor cases, 2 of 3 failing at `300f905` (a hand's file, a runner gone)
- [x] F1's fix: `_check_launcher` prints `install-cli leaves it as it is` only where `install._ahead` is true; the row's, doctor's, install's and cli's files 325 passed under each venv
- [x] L3: `plugin/commands/install-cli.md`
- [x] L1 and L2: one NICE row, n271
- [x] `make stamp`, job `20261117-071238-2406`, exit 0: 4869 tests; n212, n213 to the overflow
- [ ] `make lint doclint hygiene plugin-version-check validate`, job `20261117-081041-2418`: queued (waits on another worktree's key) at the bound
- [x] the hygiene scan, `--require-private --commits main..HEAD`: exit 0, 12 commits, 0 hits

## Handover
- If this sitting is cut: the first unticked line above; `agentik session gate wait 20261117-081041-2418 --strict --timeout 540`, a red is a fix on this branch.
- No full `make check` is queued by this sitting: the landing's own job runs it.

## Next act
The coordinator: the quick gates' line, then review 2.
