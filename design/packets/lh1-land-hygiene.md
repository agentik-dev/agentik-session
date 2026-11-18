# Packet lh1-land-hygiene: `gate land` and `gate publish` scan by the repo's own hygiene targets

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief lh1-land-hygiene, rulings R1 to R6 |
| pin | `69d0824` on main (su3-start-check's merge, plugin 2.0.0-alpha.137). Worktree `.claude/worktrees/lh1-land-hygiene`, branch `lh1-land-hygiene`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no relay verb; no `gate land` or `gate publish` on a real repo, every test's landing and publish in a temp repo with a temp remote; the scanner (`scripts/hygiene`) unchanged; the ledger unchanged; no other repo touched |
| may touch | `plugin/lib/claude_session/land.py`, `plugin/lib/claude_session/publish.py`, `Makefile` (the `hygiene-range` target), `tests/test_lh1_land_hygiene.py` (new), this packet, `history/sittings/2026-11-17-12-lh1-land-hygiene.md`; the version, the README's count, the sidecar and `history/NICE-overflow.md` by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_lh1_land_hygiene.py tests/test_land_range.py tests/test_land5_publish.py` under `.venv` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `69d0824`)

A landing in a repo of another product ran a green `make check`, whose `hygiene` target judges the scan through the repo's own wrapper with the product's own words left out. The land step then ran the bare `scripts/hygiene` over the same tree, counted thousands of hits on those words and ended `red hygiene exit 1`. So `gate land` and `gate publish` cannot be used in a repo whose Makefile, not the bare script, is its hygiene gate. Every repo of this suite has a `hygiene` target too, which runs the bare script after its pins.

Measured at the pin, a temp repo whose Makefile's `hygiene` target passes and whose bare `scripts/hygiene` exits 1 on the tree (0 on a range): the landing runs the merge message's scan, `make check`, then the bare script, and ends `land scratch: red hygiene exit 1`; `gate publish` on the same shape ends `publish crate: red hygiene exit 1`. Of the 19 cases of `tests/test_lh1_land_hygiene.py`, 14 are red at the pin and 5 green: the bare script's roads (§3 lines 2 and 4, and publish's), which this packet keeps.

At the pin the merge message's scan runs twice, before the check and again before the merge (land2 R4), each on its own dangling commit; R5 keeps both, so a `hygiene-range` target is called three times a landing: the message's span, the branch's, the message's again.

## 2. Rulings

- R1, the tree's scan, in `land` and in `publish`: where the repo's Makefile has a `hygiene` target, the scan is `make hygiene` in that tree; where it has none, the bare `scripts/hygiene`, as today. Whether the target exists is read without running a recipe. The step's line names what ran.
- R2, the range's scan and the merge message's scan: where the Makefile has a `hygiene-range` target, the scan is `make hygiene-range RANGE=<span>` in that tree, the span as today's (`<main>..<sha>`, and the dangling merge commit's for the message). Where it has none, the bare script with `--require-private --commits <span>`, as today, with today's rule for a script that predates `--commits`.
- R3, a red reads as today: the step's name, the exit code, and nothing merged or pushed. A `make` that cannot run the target (no rule after all, a Makefile that does not parse) is red, never a skipped scan.
- R4, this repo gains the `hygiene-range` target, which runs what the land step runs today for a range, so its own landing takes the new road and proves it.
- R5, nothing else: the order of a landing's steps, the push's proof, the install and the ready step do not change; no scan is dropped anywhere it runs today.
- R6, the convention, for the suite's guide: the hand-back gives the two sentences that say what `hygiene` and `hygiene-range` must do for the land step to use them. No other repo is edited.

## 3. Interfaces and acceptance

- `land.has_target(tree, name) -> bool`: the tree's Makefile holds a line that opens `<name>:`, the rule `stamps` already reads `stamp:` by (now `has_target(tree, "stamp")`); no recipe runs. `land.tree_scan(tree)` gives `(shown, argv, env)` or None, and `land.range_scan(tree)` a function of the span giving the same, or None, its `--help` probe read once where the pin read it: `make hygiene` or `make hygiene-range RANGE=<span>`, run with make's inherited variables (`MAKEFLAGS`, `MFLAGS`, `GNUMAKEFLAGS`, `MAKEFILES`, `MAKELEVEL`) left out, else the bare script's argv. `land.run` gains `env=None`. A `make` road's code on the red line is make's own (2 for a recipe that failed), as the check step's is.
- The step's note names what ran: `land-step: hygiene: make hygiene in <tree>`, `... make hygiene-range RANGE=<span> in <tree>`, `land-step: merge-file: make hygiene-range RANGE=<span> in <tree>`, and publish's `publish-step: hygiene: ...` alike. The bare roads' notes are the pin's.

| # | line | at the pin |
|---|---|---|
| 1 | the same temp repo after the change: the landing's tree scan runs the target and passes | `red hygiene exit 1` |
| 2 | a temp repo with no `hygiene` target and a bare script: the scan runs the script, and a hit is `red hygiene` with its code, as at the pin | held |
| 3 | a temp repo with a `hygiene-range` target that records its `RANGE`: it is called for the branch's span and for the merge message's (twice, §1), each span as the pin computes it; a target that exits 1 is red at the step the pin reds at (`hygiene` for the branch's span, `merge-file` for the message's) | the bare script ran; no target called |
| 4 | a temp repo with `hygiene` and no `hygiene-range`: the range goes through the bare script as at the pin | held for the range; the tree red |
| 5 | `publish` in each of the four temp repos: the same roads, the same reds | 1 and 3 red, 2 and 4 held |
| 6 | every test the repo held before: green, changed only where it asserted a step's printed line, each such change listed here; the repo's `make check`, once through the gate queue, green | green |

R4's target: `hygiene-range` runs `scripts/hygiene --require-private --commits "$(RANGE)"`, and exits 2 with a line naming `RANGE=` when it is empty; the vendored pins stay the `hygiene` target's.

No test runs a landing or a publish outside a temp repo with a temp remote, and none pushes anywhere real.

The tests whose assertion of a printed line changed: none. The pin's 381 land and publish tests (`tests/test_land*.py`) pass unchanged, since every bare road's notes, probes and lines are the pin's.

## 4. Findings that name this row

None at the pin. Not built here: a `hygiene-range` target in any other repo (each repo's own sitting adds it), and any change to the scanner.

## 5. Forbidden reads

The wall's: the live state, the relay's state, and the two branches waiting to land beside this one.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-12-lh1-land-hygiene.md`: the choices inside the rulings are in its handover.
