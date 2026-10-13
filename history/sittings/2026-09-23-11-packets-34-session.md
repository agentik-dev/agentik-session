# Sitting 2026-09-23-11: claude-code-session, packets-34-session (the ADV10 fix packet)

| item | value |
|---|---|
| goal | one packet, `design/packets/s12-fixes-adv10.md`: ADV10-1 to -11 as acts, each with a test that reproduces it first; two Opus rows off main; the rows file `design/packets/rows-2026-09-23-r7.json`, repo-relative; build nothing |
| budget | `--max-turns` not on the CONTEXT line, taken as 80 (the 80% point at 64), 144k context; one commit (packet, rows file, this charter); `make check` once at the end; never push, amend, rebase, a device |
| pin | main ac529ab (the adv-10-session merge); no branch, no worktree |
| window | 200k |
| agents | 0 (the coordinator reads and writes alone) |

## Done-ness
- [x] read: the review whole, the rulings (none carry this row), D2, the s10 packet as the format
- [x] the packet (9,213 bytes), doclint green, acceptance lines targeted and measured on main
- [x] the rows file, two rows (one per act group, 80 turns each, B after A), worktree, `claude-opus-5-5`
- [x] `make check` once at the end; tree clean; no NEXT; this charter closed

## Handover
- carried: all 11. A (`s12a`): -1 lifeline and wall 840, -2 flock, -3 stop line, -6 readme bounded, -11b. B (`s12b`, act 0 merges s12a): -4, -5, -7, -8, -9, -10, -11a. Deferred: none. Consumer: the builders
- decided: two rows because the prompt caps a row at 80 turns; B merges A so both edit conventions and the Makefile without conflict. Consumer: the orchestrator
- decided: the lock fd passes to the guardian, so the lock lives exactly as long as the group; the load wait counts against the wall. Consumer: the A builder
- for the relay: a gate output holding `bounded: stop: lock|load|wall` is unrun, never red (ADV10-3); `check` walls at 840 s inside its 900 s timeout. Consumer: packets-34-relay, the stand-in
- decided: rows files keep `repo` rooted at `~` (the stand-in reads a bare name against its cwd), so `home` stays on the rows allow row until ruling 8 lands in both drivers. The row is dropped for packets now. Consumer: the orchestrator
- verify row required on every packet outside a grandfathered tuple. Consumer: every packet writer here
- no open fork for the owner
- exit taken: goal met; `make check` exit 0; one commit on main, not pushed; no NEXT; about 25 turns, about 85k context

## Next act
The orchestrator queues `rows-2026-09-23-r7.json`; s12b starts after s12a is green and merges its branch first.
