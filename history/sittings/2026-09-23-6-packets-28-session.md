# Sitting 2026-09-23-6: claude-code-session, packets-28-session (the r6 fix packet)

| item | value |
|---|---|
| goal | one packet, `design/packets/s10-fixes-r6.md`, folding `design/review-adv6.md` (every HIGH, the mediums) and `design/review-r6.md` (the three unbounded cycles, the charter-only decisions into the record) into one Opus row off main; the rows file `design/packets/rows-2026-09-23-r5.json`; plan row 22 with baselines measured on main; build nothing |
| budget | the row's `--max-turns` (not on the CONTEXT line; taken as 80, the 80% point at 64), 144k context; one commit (packet, rows, plan row, this charter); `make check` once at the end; never push, amend, rebase, a device; no transcript, no `.jsonl` ledger |
| pin | main cea11b1 (the adv-6-session merge); no branch, no worktree |
| window | 200k |
| agents | 0 (the coordinator reads and writes alone) |

## Done-ness
- [x] both reviews read whole; the defect brief D1, D2, D4 to D7; S9 as the format; conventions whole; overhaul-r1 §2.2, §2.4, §4, §7; the code sites the findings name
- [x] the packet at 9,199 bytes, doclint green, nine acceptance lines, all targeted, measured on main (plan's baseline table)
- [x] the rows file at 1,225 bytes; plan row 22 and its baseline table
- [x] `make check` once at the end, exit captured in the exit line; tree clean after the commit; no NEXT; this charter closed

## Handover
- carried (eleven acts, 120 turns with the reason): ADV6-1 to -9; R6's C1, C2, C3 each with a test first; E2, E5, E8; the seven charter-only decisions and T1 to T5 into conventions and overhaul-r1. Consumer: the s10-fixes-r6 builder
- deferred: ADV6-10 to -13 (lows), named for a later packet. Consumer: the next packet writer
- R6 §6 decided inside the design (none ruled on the CONTEXT line): 1 to 4 yes as recommended; 5 the shebang stays `env python3`, the global CLAUDE.md line is the owner's to amend. Consumer: the owner (example-mac)
- choices: acceptance lines stay targeted by a `verify` row in the packet table (doclint refuses whole-suite lines only when the row exists, so the nine older packets are grandfathered); `scripts/bounded` carries the lock, the wall and the load breaker (D2.4, D2.5) so `make check` and `validate` need no coreutils; `history/sessions/NEXT` is exempted, tracked or not (the stand-in commits a tracked one); `CLAUDE_SESSION_STATE_DIR` is retired because D9's path is the contract; the python floor rises to 3.11 for `-P`; `make install` freezes the package by tree hash, so hooks follow the install, not the checkout. Consumer: the builder, the owner (a `make install` after each merge the owner wants live)
- the relay's consumers: set `CLAUDE_SESSION_DEPTH=1` and `CLAUDE_SESSION_MAX_TURNS` for its children, drop the CONTEXT-line turns workaround after; the gate refuses a diff touching `.hygiene-allow` or the sidecar unless the packet names it. Consumer: the agent-relay packet writer
- the three re-sync rows (decisions, respeak, agent-relay) after S10 lands: both scripts, `email` allow rows, the `verify` row in new packets. Consumer: the orchestrator
- found: charter 2026-09-23-3 (closed) still reads `exit taken: (filled at close)`; left as a record. Consumer: the owner
- open fork for the owner: none
- exit taken: goal met; packet, rows file, plan row 22 written; make check exit 0 (334 passed); one commit on main, not pushed; no NEXT; about 30 turns, about 95k context

## Next act
The orchestrator queues `rows-2026-09-23-r5.json`; the builder reads the packet's `from` row first.
