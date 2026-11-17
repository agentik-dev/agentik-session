# Sitting 2026-11-16-2: agentik-session, is2-first-read

| item | value |
|---|---|
| goal | a correct install reads as set up: the doctor's `mod` row, install-cli's PATH line, the README's Workflow clause, the prune's `ps` |
| budget | about 80 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `f6f5d14` on main (2.0.0-alpha.129) |
| branch | `is2-first-read`, worktree `.claude/worktrees/is2-first-read`, the two venvs linked |
| level | S3, no packet: a small row |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] R5, the tests first: `tests/test_is2_first_read.py`, 9 of 15 failing at the pin (the six that pass pin what stays: a session's unseen mod a warn, on PATH as today, the first form alone, a ps that cannot start)
- [x] R1: the doctor's `mod` row with no session on the machine a note (`not seen: no session has run on this machine yet`); a session's unseen mod still a warn, its detail as at the pin
- [x] R2: install-cli off PATH ends on the line that mends this terminal (`export PATH="$HOME/.local/bin:$PATH"` for the default prefix, the prefix's bin folder otherwise, single-quoted where double quotes would not hold it), one line above it saying why; on PATH as at the pin
- [x] R4: `prune.processes()` tries `ps axwwe` where `-axwwE` exits non-zero, as commons main's `processes()`; the probe kept; a list that cannot be read says `<ps> exited <n>: <ps's first stderr line>`
- [x] `make stamp` through the gate (job `20261116-185753-2219`, exit 0): 2.0.0-alpha.130, 4854 tests; before R3, since the stamp reds a source the README was not rendered from
- [x] R3: the README source's needs line gains the Workflow clause, in `design/readme/source.md` alone (conventions: edit the source, never the README); the source had 11 B of room under its 16,384 B ceiling, so the line says `3.9+` and `No clone, no package`, and Why it exists says `Its family answers` for `It is part of a small family of plugins that answers` (line 16 already says it is part of agentik): 16,369 B; README.md waits on `make readme`, a `claude -p` render outside a builder's wall, so the sidecar test and the check's last line read stale until it runs
- [x] `make check` through the gate on `8fa8cb4` (the stamp's commit, before R3): job `20261116-192911-2229`, exit 0 (4854 passed; floor 4705 passed, 128 skipped; lint, README top, doclint, recordlint, hygiene, plugin-version-check, validate, the mod's tests, README fresh). Before it, job `20261116-185815-2220` cut by the 1800 s wall in the floor pass (load near 7; its first pass green, 4854 passed)

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
The coordinator: `make readme` in this worktree, then `make stamp` and `make check`; then review and landing.
