# Sitting 2026-11-17-13: agentik-session, is3-readme-needs

| item | value |
|---|---|
| goal | a render the verifier refuses is tried once more with the verifier's words in its contract; the README's needs line names the Workflow refusal |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `bfcbab7` on main (plugin 2.0.0-alpha.139) |
| branch | `is3-readme-needs`, worktree `.claude/worktrees/is3-readme-needs`, the two venvs linked |
| level | S4, packet `design/packets/is3-readme-needs.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, the baseline at the pin (6 of the 11 retry cases red, 5 held)
- [x] R1 to R4: the retry in `scripts/readme-render`, the wall 2900 s in its header and the Makefile; 11 cases appended to `tests/test_readme.py`, green under both venvs
- [x] R6: NICE n322 (a close dead after its claim) and n323 (a crash's temp file); the file past recordlint's size bound until `make stamp` moves the oldest S4 rows
- [x] R5: the needs line in the source (c738c82's wording), paid by the family sentence's trim: 16,373 to 16,369 bytes; a test on both docs, the README's red until the render
- [x] `make stamp` (job `20261117-194732-2607`, exit 2): red sidecar, the source changed; the render goes first
- [x] `make readme` (job `20261117-194740-2608`, exit 0, 12 min): two renders, the retry fired; render 1 (316 s) refused, 13 code spans and a number lost; render 2 (407 s, one round) passed
- [x] `make stamp` (job `20261117-200104-2612`, exit 0): alpha.139 kept, 5078 tests, n268 and n269 moved to the overflow; nothing under `plugin/` changes on this branch, so the version needs no move
- [ ] `make check` through the gate, green

## Handover
- If this sitting is cut: the first unticked line above.
- Choice: the retry's cases sit in `tests/test_readme.py`, whose allow row covers the renderer's names; a new test file would need a `sibling` row.
- Choice: a refusal is the verifier's exit 1 alone; any other exit is exit 2 at once, as at the pin.
- Choice: the note's bound is bytes (`head -c`), so a cut may split a multibyte character; the renderer reads it into a prompt.
- Choice: the retry renders into the same temp output, emptied first; one round (`RETRY_ROUNDS=1`), as R3 asks.
- decide, owner: the coordinator; consumer: the landing's range scan. Commit `8c4d1fe` holds the packet's first text, which names the renderer's plugin five times (`sibling`); the tree's text names it no more. A row `design/packets/is3-readme-needs.md: sibling`, as `s11-readme-r7.md` has, clears the range scan.

## Next act
`make check`, through the gate.

## Exit
Open.
