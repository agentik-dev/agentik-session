# Sitting 2026-09-24-1: claude-code-session, packets-36-session (the conventions packet after run 10)

| item | value |
|---|---|
| goal | one packet, `design/packets/s13-conventions-r10.md`: the six rulings of 2026-09-24 as acts, each with a test first; the rows file `design/packets/rows-2026-09-24.json`; build nothing |
| budget | `--max-turns` 80 (the 80% point at 64), 144k context; one commit (packet, rows file, this charter); `make check` once at the end; never push, amend, rebase, a device |
| pin | main 330bded (the s12b merge); no branch, no worktree |
| window | 200k |
| agents | 0 (the coordinator reads and writes alone) |

## Done-ness
- [x] read: run 10's handovers naming the next conventions packet, agent-relay's `packet.Unbounded` and `packet.legacy`
- [x] the packet, doclint green, acceptance lines targeted and measured on main
- [x] the rows file, worktree, `claude-opus-5-5`
- [x] `make check` once at the end; tree clean; no NEXT; this charter closed

## Handover
- carried: all six rulings. A (`s13a`): 17 stems in GRANDFATHERED, doclint mirrors `packet.Unbounded` by shape, hygiene NUL files (ADV10-17). B (`s13b`, act 0 merges s13a): bounded SIGTERM 143 (d12), doctor turn cap and meter-hook line, conventions §5 turns line, README 840 s rendered at close. Consumer: the builders
- decided: a SPENT tuple (agent-relay ar11, ar12) mirrors Go's `spent`. Their `make tla`/`make e2e` acceptance was the only newly refused shape across the four repos' verify-rowed packets (measured). Consumer: the A builder, packets-37
- decided: the doctor drops `--max-turns` from the help probe (a probe spends a turn); `meter-hook` is a report, ok either way. Consumer: the B builder, the owner
- decided: the rows file names a bare repo, as agent-relay's since AR17D; the allow row stays until a hygiene packet drops it. Consumer: the orchestrator
- for packets-37: hygiene, doclint and bounded all move; the three new shas come from the builders' reports (A two, B one)
- no open fork
- exit taken: goal met; `make check` exit 0; one commit on main, not pushed; no NEXT; about 25 turns, about 75k context

## Next act
The orchestrator queues `rows-2026-09-24.json`; s13b starts after s13a is green and merges its branch first.
