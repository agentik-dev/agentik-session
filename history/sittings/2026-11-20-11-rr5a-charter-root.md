# Sitting 2026-11-20-11: agentik-session, rr5a-charter-root, build 2 (review 1's round)

| item | value |
|---|---|
| goal | review 1's round: F1 the resolver's bound inside a hook, F2 the hot-path test that can fail, F3 a `--dir` inside the clone, F4 the line where git did not answer, F5 `records` an absolute path, doctor's `broken` a `fail`, the wish list's rows |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `91212ad` on the branch (checked head `1b92b2d`) |
| branch | `rr5a-charter-root`, worktree `.claude/worktrees/rr5a-charter-root`, the two venvs linked |
| level | S3, packet `design/packets/rr5a-charter-root.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] F1: the bound under the hook's deadline (2 s at most in PostToolUse), the group killed by the bound, the cut and TERM, the band spent after its line; four tests, red at `1b92b2d`
- [x] F2: the hot-path test counts asks (a recorder that raises nothing) and processes over nine paths in four states, against the pin's 0; the review's mutant (an ask atop `pre_tool_use`) reds it, `{'pre': (1, 1)}`
- [x] F3: a `--dir` whose real path is in the clone refused for `open` and `close` in `unset` and `broken`, for `show` and `check` in `broken`; outside it stands
- [x] F4: where git did not answer, the line says so and its reason, with no "set it"
- [x] F5: `_read` takes `records` only as an absolute path (or none outside `out`), else a failed read with its reason
- [x] Doctor: the `records` row is `fail` in `broken` (GUIDE §12), `warn` in `unset`, `ok` in `own` and `out`, text and JSON
- [x] NICE rows n370 to n375 (`0932695`); the packet true to the build; doclint silent; hygiene `--commits main..HEAD` 0 hits
- [ ] `make stamp`, then `make check`, through the gate

## Handover
- Choices: the packet's §4. F1: the resolver is asked before `meter.save` (the band spent once the line is made); a `failed` read gives `<this sitting's charter>`; HOOK_MARGIN 2.5 s.
- decide, owner: the coordinator. `charter check FILE` in `broken` still reads a file inside the clone (the brief names `--dir` alone; GUIDE §12 says refuse each read); consumer: rr5b.
- decide, owner: the coordinator. A `failed` read (git timed out) fails doctor's row, as R2 reads it `broken`; consumer: the suite's doctor.

## Next act
`make stamp` through the gate, then `make check`.

## Exit
