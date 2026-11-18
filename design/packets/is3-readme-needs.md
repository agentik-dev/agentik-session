# Packet is3-readme-needs: a refused render is tried again with what the verifier said; the README's needs line names the Workflow refusal

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief is3-readme-needs, rulings R1 to R6 |
| pin | `bfcbab7` on main (lh1-land-hygiene's merge, plugin 2.0.0-alpha.139). Worktree `.claude/worktrees/is3-readme-needs`, branch `is3-readme-needs`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no relay verb; no test starts `claude` or the real renderer; respeak unchanged; `design/readme/contract.txt` unchanged; the ledger unchanged; no other repo touched |
| may touch | `scripts/readme-render`, `Makefile` (the `readme` target's wall), `tests/test_is3_readme_retry.py` (new), `design/readme/source.md` (the needs line and its trim), `NICE_TO_HAVE.md` (two rows), this packet, `history/sittings/2026-11-17-13-is3-readme-needs.md`; `README.md`, the source's status line and the sidecar by `make readme` alone; the version, the count and `history/NICE-overflow.md` by `make stamp` alone |
| verify | `make stamp`, `make readme` (at most twice in all), then `make check`, by the gate queue, last |
| acceptance | §3; `PY -m pytest -q tests/test_is3_readme_retry.py tests/test_readme.py tests/test_bounded.py` under `.venv` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `bfcbab7`)

`scripts/readme-render` runs the renderer, then the verifier (`respeak-verify-edit.py`: structure, code spans and numbers byte-identical, prose only). The renderer's own style gate gets a retry inside the renderer; the verifier's refusal does not: it ends the run with exit 2 and gives nothing back to the renderer. Measured 2026-11-17 on one row: of four renders of this README, three were refused by the verifier (a code span, a bullet, a table row or a number gained or lost), each after 457 to 587 s, and each was a whole `make readme` started again blind.

At the pin the wall is 2000 s: 120 s for the collection, 2 rounds of 900 s plus 2 s grace each, and 60 s for the gates, the verifier and the move (1984 s). The verifier prints `FAIL (md): <n> invariant violation(s)` and one `  - <what>` line per violation on stdout, and exits 1; its usage faults exit 2. The renderer reads `--contract <file>` and puts the file's text in its prompt as "Additional contract notes": the retry needs no change in respeak.

Of the 11 cases of `tests/test_is3_readme_retry.py`, 6 are red at the pin (a refusal ends at exit 2 after one call, so lines 2 and 3, the retry's renderer failure and the cut note are red; the header states no sum) and 5 green: a first pass, a first renderer failure, a verifier fault.

## 2. Rulings

- R1, the retry: when the verifier refuses a render, `scripts/readme-render` runs the renderer once more, with a contract made of `design/readme/contract.txt` followed by a short note that the last render was refused and the verifier's own words (what was gained or lost), cut to a stated bound. The second render is verified as the first. A second refusal ends as today: exit 2, `README.md` untouched, and both refusals on stderr.
- R2, where the note lives: the joined contract is a temp file outside the repo, removed by the script's trap; `design/readme/contract.txt` is never written. Nothing of respeak changes: the renderer takes the note through its `--contract` option as it stands.
- R3, the wall: the script's header and the Makefile's `--wall` state the new budget as a sum, and the retry's share of it is the smallest that lets one informed render finish.
- R4, everything else as today: the renderer's exit 1 (the style gate after its rounds) is exit 1 with no verifier retry; a setup fault is exit 2; a passing first render calls the renderer once, with the contract file as given; the status line, the move and the sidecar do not change.
- R5, the README's needs line: in `design/readme/source.md` the line that opens "It needs Claude Code" says that the plugin refuses Claude Code's Workflow tool. The source ends at or under its size at the pin (16,373 bytes), so the clause is paid for by a trim. Then `make readme`, once, through the gate queue.
- R6, two NICE rows from the last row's second review of `claude_session/lines.py`: a close that dies after its claim into `closing/`, and a temp file a crash leaves under `lines/`.

## 3. Interfaces and acceptance

- The constants: `RETRY_ROUNDS=1`, the retry's `--max-rounds` (one informed render; the style gate's second round is the first render's alone), and `NOTE_BYTES=2000`, the bound on the verifier's words in the note. The wall: 120 + (2 + 1) x (900 + 2) + 60 = 2886 s, a 2900 s wall in the header and the Makefile.
- The joined contract is `contract.txt` in the script's temp folder (`mktemp -d`, outside the repo), removed by the trap: the repo's contract, a blank line, a line that the last render was refused, the verifier's output cut to `NOTE_BYTES` bytes, and a line asking for the source's items kept as written. The retry renders into the same temp output, emptied first.
- A refusal is the verifier's exit 1; its output goes to stderr with the refusal's line. Any other verifier exit is exit 2 at once, as at the pin. A passing verifier's line goes to stdout, as at the pin.

| # | line | at the pin |
|---|---|---|
| 1 | the verifier passes the first render: one renderer call, its contract argument the repo's file; README and sidecar written, exit 0 | held |
| 2 | the verifier refuses once, then passes: two renderer calls; the second's contract holds the repo's contract and the verifier's words; README and sidecar written, exit 0; the temp contract is gone afterwards and the repo's contract file is byte-equal | exit 2 after one call |
| 3 | the verifier refuses twice: exit 2, `README.md` byte-equal to before, both refusals on stderr, two renderer calls and no third | exit 2 after one call |
| 4 | the renderer exits 1: exit 1, no second call; a verifier output over the bound is cut to it in the note | the first call held; no note |
| 5 | the header's sum, the Makefile's `--wall` and the script's constants agree, held by a test | no sum stated |
| 6 | R5: the needs line names the Workflow refusal; `README.md` rendered by `make readme` through the gate, the sidecar fresh | the line names no Workflow |
| 7 | every test the repo held before: green, changed only where it asserted the wall's number or the script's rounds; `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp` the last change under `plugin/`; `make check` once through the gate, green | green |

The tests whose assertion changed: none. `tests/test_readme.py`'s wall test asserts the wall covers the first render's rounds, which 2900 s still does; `tests/test_bounded.py` reads the target's shape, not its number. The new file holds the retry's share.

## 4. Findings that name this row

None at the pin. Not built here: any change to respeak's renderer or verifier; a retry of the style gate beyond the renderer's own; the README's verb table (n320).

## 5. Forbidden reads

The wall's: the live state, the relay's state, and the branch `st1-starter` waiting to land beside this one.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-13-is3-readme-needs.md`: the choices inside the rulings are in its handover.
