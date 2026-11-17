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
- [ ] `make stamp` through the gate
- [ ] R3: the README source's needs line gains the Workflow clause
- [ ] `make check` through the gate; hygiene `--require-private --commits main..HEAD`

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
`make stamp` through the gate.
