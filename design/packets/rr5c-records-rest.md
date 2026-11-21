# Packet rr5c: where a repo's records live outside its clone, the rest of session's record paths go through the resolver

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-21, brief rr5c-records-rest (the last of rr5's three rows; hq design/28 §3 items 13, 18, 19, §11 lead 6; commons GUIDE §12; rr5b review 1's F4, ruled); the owner's words below |
| pin | `5780e9a` on main (rr5b-two-commits landed, plugin 2.0.0-alpha.156). Worktree `.claude/worktrees/rr5c-records-rest`; `.venv`, `.venv-floor` linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; commons and the relay read-only |
| may touch | `plugin/lib/claude_session/lines.py` (`send`, `valid`), `reconcile/runner.py`, `reconcile/live.py`, `reconcile/idle.py`, `cli.py` (`_commit_named`, `line send`'s help), `unattended.py` (`run`), `records.py` (the record names), `scripts/stamp`, `scripts/doclint`, `RUNBOOK.md`, what commons' `scripts/sync` places, `tests/test_rr5c_*.py`, a test that pins the old list of copies, the rr5b tests' fixture charters (R6), this packet, the charter |
| verify | pytest under `.venv` and `.venv-floor` on the new files and the touched modules' tests; `scripts/doclint`; `scripts/hygiene --require-private --commits main..HEAD`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls a build, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `lines.send` refuses a file not under the sender's checkout; `valid` refuses a pointer whose file is not under `from` (under `to` for a close's line back), so the taker drops it.
- The reconcile record is `<cwd>/<record>`, `_inside` judged against the repo; `live.charters` and `goal_unchanged` read `<hq>/history/sittings` by hand; `idle` classifies a command by the segment `/history/sittings/`.
- `scripts/stamp` stops with exit 2 when `NICE_TO_HAVE.md` is absent. `scripts/doclint --repo DIR` runs `git -C DIR ls-files`, which lists a subfolder's files relative to it.
- `_commit_named` commits a record path in the holder unlinted; in `unset` and `broken` it commits a record path in the clone. `unattended.run` reads `relay/queue.yaml` in any state.

The owner's words: the coordinating repo's entry 63, verbatim: "Each of agentik's public tools keeps its working records in agentik-hq. As a tool's row lands, its charters, packets, wish list and questions move to agentik-hq/repos/<tool>/ and leave the public tree in one commit; what is already pushed stays in the public history (design/28)." Entry 65, on the Go relay, whose reason R7 takes for the loop: "The relay does not plan, run or gate in a repo whose records live outside its clone: it says so in one line that names the key, and its doctor shows the state." Entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief rr5c)

- R1, `own` is the pin: every verb and script touched gives the pin's output, exit and writes; no hook starts a process it did not start at the pin.
- R2, a line's file: in `out`, `line send` takes a file in the sender's checkout or under its records folder, and the refusal names both when neither holds. `valid` asks the resolver for `from` (for `to` on a close's line back) only when the pin's test fails; `out` and under its `records` passes; any other answer is the pin's verdict.
- R3, reconcile: in `out` the record is `<records>/<record>`, `_inside` judged against the records folder; `live` reads the charter folder through `records`. `unset` and `broken` refuse with the state's line, exit 2, nothing written.
- R4, `stamp`: a tree that declares `records: out` at `HEAD` (the resolver's reading) moves no wish-list row and does not stop for its absence; else the pin.
- R5, doclint: `--repo` at a subfolder of a work tree lints that folder, paths relative to it; at a top, the pin.
- R6, lead 6: a holder commit's paths under the charter folder are linted by `charter check`'s rules first; a refusal prints the check's lines and refuses the holder's commit in rr5b's half form.
- R7, the loop: `unattended run` refuses a repo not in `own`, before any write or process of the run, in one line that names the key. R7b: in `unset` and `broken`, `checkpoint --commit` refuses a named clone path under a record name (the scanner's list), exit 2, nothing committed.
- R8, the words: `RUNBOOK.md` on the reconcile record; `line send`'s help.

## 3. Interfaces: the acceptance table (baseline read at `5780e9a`)

| # | line | at the pin |
|---|---|---|
| 1 | R2: `out`, a file under the records folder is sent, taken, shown, closed with a line back; under neither refuses naming both; a resolver past its bound gives the pin's verdict in time; `own`, no resolver start for a passing pointer | refused |
| 2 | R3: the record's file in each state; `live` and `idle` over a holder's charters; `unset` and `broken` refused | the clone's folder |
| 3 | R4: a declaring tree with no wish list stamps, exit 0; a tree that does not declare stops | exit 2 |
| 4 | R5: doclint over a subfolder names the red charter by its folder path; a top as at the pin | (measured in the test) |
| 5 | R6: a charter over its bound: the clone's commit stands, the holder's refused with the check's line; a green one commits | committed |
| 6 | R7: `unattended run` refused in `out`, `unset`, `broken`; R7b: a record path with a code path in `unset` and `broken`, exit 2, nothing committed; the code path alone commits | run; committed |
| 7 | every test of the pin passes unchanged; every repository a test writes is a temp one | |
| 8 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row: the choices inside the rulings

(filled as each ruling lands)

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

To the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices, what was not done.
