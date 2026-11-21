# Packet rs1: session's gate reads no record of its clone, so its records can move

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-21, brief rs1-session-ready (the records' move: two tests of the gate read a record of the clone; `scripts/stamp`, the third, was rr5c's R4; commons GUIDE §12); the owner's words below |
| pin | `2bfa312` on main (rr5c-records-rest landed, plugin 2.0.0-alpha.158). Worktree `.claude/worktrees/rs1-session-ready`; `.venv`, `.venv-floor` linked |
| wall | this worktree, and a scratch clone outside every checkout for R3, nothing pushed from it; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; commons read-only |
| may touch | `tests/test_g7_reader.py` (`test_5_the_packets_lines_both_sides`), `tests/test_land3_stamp.py` (`test_line9_the_readers_find_this_repos_files`), `tests/fixtures/g7/packet-lines.txt`, `tests/fixtures/land3/NICE-overflow.md`, R3's own mends (a test or script of this repo that reads a record of its clone, one commit each, a line in §4), this packet, the charter |
| verify | pytest under `.venv` and `.venv-floor` on the two tests; `scripts/doclint`; `scripts/hygiene --require-private --commits main..HEAD`; R3's `make check` on the scratch clone, then `make stamp` and `make check` in the worktree, each through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the fixtures and the tests, then the rehearsal |

## 1. What the source says: the code at the pin

- `test_5_the_packets_lines_both_sides` reads every `design/packets/*.md` in sorted order, takes `unattended.acceptance`'s shell lines (a packet that raises `AcceptanceError` is passed over) and asserts: every line `unbounded` refuses names `make` as a word; some are refused; at least 100 are not. At the pin: 135 packets, 110 passed over, 161 lines, 14 refused, no line holding a newline.
- `test_line9_the_readers_find_this_repos_files` reads `history/NICE-overflow.md` (88,885 B) and asserts that `stamp.overflow_insert_at` stops just past a table row under `## From the open findings`, with `\n## ` next. `SOURCE` and `README` are no records.
- Both read a record of the clone; the day the records move to the holder, both go red.

The owner's words: the coordinating repo's entry 63, verbatim: "Each of agentik's public tools keeps its working records in agentik-hq. As a tool's row lands, its charters, packets, wish list and questions move to agentik-hq/repos/<tool>/ and leave the public tree in one commit; what is already pushed stays in the public history (design/28)." Entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief rs1)

- R1, the packets' lines: test 5 reads `tests/fixtures/g7/packet-lines.txt`, every acceptance shell line over the packets at the pin, one a line, in the packets' sorted order, harvested once by a one-off line kept in no script; it asserts what it asserts at the pin and reads nothing under `design/`.
- R2, the overflow's shape: line 9 reads `tests/fixtures/land3/NICE-overflow.md`, a short file of the real one's shape (its head, `## From the open findings` with two rows of made-up text, the section after it), and asserts what it asserts at the pin; `SOURCE` and `README` read as at the pin.
- R3, the rehearsal: a scratch clone of the branch, every tracked path under the record names removed and `records: out` added to `.hygiene-allow`, in one commit of the scratch clone alone; the whole `make check` there through the gate queue. A red that is a test or a script of this repo reading a record of its clone is mended as R1 and R2, one commit each; any other red stops the build.
- R4, what stands: no assertion weakens, none is skipped; in a tree that holds its records every verb, script and test reads as at the pin; the README source within its bound.

## 3. Interfaces: the acceptance table (baseline read at `2bfa312`)

| # | line | at the pin |
|---|---|---|
| 1 | R1, R2: the two tests green; `git grep -n "design.*packets\|NICE-overflow\|history" tests/test_g7_reader.py tests/test_land3_stamp.py` shows no read of the clone's records | green, reading the clone's packets and overflow |
| 2 | R3: the rehearsal's `make check` green through the gate on the scratch clone's head; what else it turned red, each with its commit, or "nothing else" | (measured in the rehearsal) |
| 3 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row: the choices inside the rulings

- R1: the fixture is read with `splitlines()`; no line at the pin holds a newline, so each stands on one line as harvested.
- R2: `OVERFLOW` stays the temp repos' path, where the stamp writes; line 9 reads `OVERFLOW_SHAPE`.
- R3, the rehearsal's reds (job `20261121-091800-3036`, exit 2): three tests ran in the clone's own tree and so read its records state, `unset` there; each now runs outside any checkout (`own`, as at the pin), its assertions unchanged:
  - `test_hook_session_start.py`: the charter reminder and the s39 cases read `payload_outside`, the fixture's cwd copied to the temp folder.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

To the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate jobs, the choices, what was not done.
