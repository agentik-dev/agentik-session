# Sitting 2026-09-23-8: claude-code-session, packets-29-session (the r7 README packet)

| item | value |
|---|---|
| goal | one packet, `design/packets/s11-readme-r7.md`: the public-facing README source, the contract render path with a status line, a project icon, the public-repo check, one Opus row off main, 60 turns; the rows file `design/packets/rows-2026-09-23-r6.json`; build nothing |
| budget | the row's `--max-turns` (not on the CONTEXT line; taken as 80, the 80% point at 64), 144k context; one commit (packet, rows file, this charter); `make check` once at the end; never push, amend, rebase, a device; no transcript, no `.jsonl` ledger, no whole reference record |
| pin | main 68c76cb (the s10-fixes-r6 merge); no branch, no worktree |
| window | 200k |
| agents | 0 (the coordinator reads and writes alone) |

## Done-ness
- [x] read: respeak's README, its `design/readme/` (source, contract, sidecar) and its two render scripts, the installed renderer's header (0.6.1, ships the verifier); conventions §4 to §7 and §9; the icon family's README and generator; this repo's source, README, Makefile, manifest, `test_readme`, the S6 packet and its report line (a contract-less render cut the README from 117 lines to 55)
- [x] the packet at 9,190 bytes, doclint green, nine acceptance lines, all targeted, measured on main (§4)
- [x] the rows file, one row, `depends_on` this row, worktree, `claude-opus-5-5`, 60 turns
- [x] `make check` once at the end, exit in the exit line; tree clean after the commit; no NEXT; this charter closed

## Handover
- render count: 0 here (the coordinator renders nothing); the packet allows the builder at most two `make readme`, counted, each with the renderer's two rounds. Consumer: the s11-readme-r7 builder
- the icon's glyph: a gauge, a dial with the needle toward the 80% checkpoint, because the meter over two ceilings is the one thing this plugin does that no sibling does; the family is respeak's README icon (a 64-box monoline `currentColor` glyph, width 56 under the title), with the generator's rules carried over (one centered box, filled shapes where a stroke's box would be a line, no gradient, so the zero-extent-stroke gotcha cannot bite); no PNG, the generator makes none. Consumer: the builder, the owner
- decided inside the design: the render gains respeak's contract and the verifier before the README moves (S6's report is the reason); the status line is written by the render script from the manifest, the date and the suite's collected count, and pinned by tests; the source ceiling rises to 16,384 in `test_readme` (the record tool reads it by section); the README and the source keep exactly `sibling,person` in the allow file; no version bump. Consumer: the builder
- the public check: every hygiene group but `sibling` and `person` reads 0 over the README and the source (the repo's own name and the dependency ids are `sibling`; the marketplace account is `person`), and no `../<sibling>` path. Consumer: the builder, the other three README packet writers
- no plan row: the brief names none and the plan's rows end at 22; the orchestrator adds one if the plan is to carry the README round. Consumer: the orchestrator
- open fork for the owner: the plugin icons follow respeak's monoline family, not the household sites' dark-glass masters; if one family across sites and plugins is wanted, a later row adds 1024 px masters for the four plugins to the generator in example-site. Consumer: the owner
- exit taken: goal met; packet (9,190 bytes), rows file, this charter written; make check exit 0 (416 tests collected, readme fresh); one commit on main, not pushed; no NEXT; about 20 turns, about 75k context

## Next act
The orchestrator queues `rows-2026-09-23-r6.json`; the builder reads the packet's `from` row first and renders last.
