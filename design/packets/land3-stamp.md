# Packet land3-stamp: `make stamp` writes what a landing derives, and reds on a merge that drops a test

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief land3 (hq design/19's land3, §3 item 4, amendment R1-F4) |
| pin | `148fde3` on main (2.0.0-alpha.98). No version move in either phase. Worktree `.claude/worktrees/land3-stamp`, branch `land3-stamp`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (phase 1 runs no `make` at all; phase 2 the gate queue only); no `claude`; no test reads live state (temp repos only); no relay verb; no stamp of this checkout in phase 1 |
| may touch | `scripts/stamp` (new); `Makefile` (`STAMP_BASE`, the `stamp` target, `.PHONY`); `tests/test_land3_stamp.py` (new); `.hygiene-allow` (if the scan asks); this packet and the sitting's record; at phase 2, by the stamp, `README.md`, `design/readme/{source.md,rendered.sha256}`, `NICE_TO_HAVE.md`, `history/NICE-overflow.md`. Nothing under `plugin/` |
| verify | phase 1: `tests/test_land3_stamp.py` under `.venv` and `.venv-floor`, `scripts/doclint`, `scripts/recordlint`, `scripts/hygiene`; phase 2: the gate queue's `make check`, once, last |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_land3_stamp.py` green, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin (baseline measured at `148fde3`)

- The owner's words: "(5) same, fix this too", of the finding that a landing is steps by hand: after a branch merges main, a helper sets the version, the README's count, the sidecar and the NICE file's size. One target writes those lines.
- `scripts/stamp --help` prints `sh: scripts/stamp: No such file or directory`, exit 127; `grep -c '^stamp:' Makefile` prints `0`.
- A merge that drops a test: main and a branch each add `def test_new` at another place of one test file; `git merge main` is clean; the base collects 3, each side 4, the merge 4, where 4 + 4 - 3 is 5. Nothing reds.
- The equation on main's record: 12 of 12 merges of main into a branch since 2026-11-01 held it, and the source's Status line at main's side and at the merge base equalled the collected count in 24 of 24, each base on main's first-parent line.
- The hand's line `shasum -a 256 design/readme/source.md README.md > design/readme/rendered.sha256` over a reworded, unrendered source makes `make check` print `readme: fresh`.
- `NICE_TO_HAVE.md` is 24,330 B of recordlint's 24,576 B bound; the overflow's first table sits under `## From the open findings`.

## 2. Rulings: the requirements (brief land3)

- R1 what is new: `scripts/stamp` (standard library, 3.9 syntax, not vendored, its docstring its contract), the `stamp` target, `tests/test_land3_stamp.py`. Nothing under `plugin/`; `make check` never calls the stamp; no README or RUNBOOK line (the source has 18 B left).
- R2 the call: `scripts/stamp [--repo DIR] [--base REF] [--version X]`, DIR the working directory, REF `main`. Makefile: `STAMP_BASE ?= main`, a one-line recipe `$(PYTHON) scripts/stamp --base "$(STAMP_BASE)"`, `--version "$(STAMP_VERSION)"` where set; in `.PHONY`, a `##` line. Exit 0 stamped or nothing to write, 1 a red, 2 usage, no work tree, no ref, a file absent or misshapen. All is read and decided first: a red or an exit 2 writes nothing.
- R3 the version: the branch's own paths, as the version check's second read takes them against REF (under `plugin/`, less `plugin.json`, uncommitted and untracked included). None: the version stays. Some: a version above REF's stays, else REF's with its last number plus one. `--version X` is written in every case, exit 2 unless semver-shaped and above REF's. A REF version ending in no number, where one is needed, is exit 2 naming `STAMP_VERSION`. Only the value on `plugin.json`'s one `"version"` line changes.
- R4 the count: the last line of `<this interpreter> -m pytest --collect-only -q -p no:cacheprovider` in DIR, under a 120 s wall. `README.md` and `design/readme/source.md` each hold one line `tests/test_readme.py`'s `STATUS` matches, else exit 2; in it the version becomes R3's and the count the collected one; the date and every other byte stay.
- R5 the sidecar: written as `shasum -a 256 design/readme/source.md README.md` prints it, where it does not read so already, and only over fresh files: the sidecar as it stands names the file's sum, or the file differs only in its Status line from the file at HEAD or at a parent of HEAD whose own sidecar names that commit's file. Else `red sidecar`.
- R6 the NICE rows: while `NICE_TO_HAVE.md` is at or over 24,576 B (tied by a test to recordlint's `CAPS`), its first S4 row moves, byte for byte, to the last row of the table under `## From the open findings` in `history/NICE-overflow.md`. No S4 row left: `red nice`. No such table: exit 2.
- R7 the count's equation: asked only while HEAD is a merge of two parents, the second REF's commit or its ancestor. The working tree's count must equal B + M - A: B collected from the first parent in a temp extract; M and A from the source's Status line at the second parent and at the merge base where that commit is on REF's first-parent line, else collected. Unequal: `red count`. Two merge bases: not asked, one stderr note. No override.
- R8 the lines: stdout `stamp: version <old> -> <new>`, `stamp: count <old> -> <new>`, `stamp: moved <ids> to history/NICE-overflow.md`, `stamp: sidecar written`, last `stamp: ok: plugin <version>, <count> tests` (`; nothing to write` when no file changed). stderr, exit 1: `stamp: red count: ...`, `stamp: red sidecar: <file> ...`, `stamp: red nice: ...`. Exit 2: one line `stamp: <what>`.

## 3. Interfaces: the acceptance table (brief land3), each a case of `tests/test_land3_stamp.py` over a made-up temp repo; at the pin every line is red (no `scripts/stamp`, exit 127)

1. `quince` changed `pear.py` and added a test: version 7 -> 8, count 3 -> 4, sidecar written, ok; numstat `1 1` thrice and `2 2`; `shasum -c` and `scripts/plugin-version-check --repo` exit 0.
2. Run again: `; nothing to write`, bytes and mtimes as they were.
3. `quince` at alpha.9 keeps it; a test alone moves the count, not the version; `--version 2.1.0` written; `--version 2.0.0-alpha.7` and `next` exit 2; main at `2.0.0-alpha`: exit 2 naming `STAMP_VERSION`.
4. Both sides add `def test_new`: the merge reds `collects 4 tests; the branch's 4 plus main's 4 less the merge base's 3 is 5`, exit 1, no write; two names, 5 tests: exit 0.
5. The merge with a commit above it: exit 0; main's Status line saying 9: the red reads `main's 9`.
6. The source's prose changed with no render, committed or not: `red sidecar` naming the source; a Status line changed by hand in both files: exit 0, the sidecar written; a merge that took main's Status line and sidecar over the branch's rendered README: exit 0.
7. NICE at 24,576 B or more with S4 rows `n4`, `n6`, `n9`: `moved n4, n6`, each the overflow table's new last row, recordlint passes; at 24,575 B nothing moves; no S4 row: `red nice`.
8. `--base nosuch`, two Status lines, no work tree, an unknown flag: exit 2, one stderr line, no write.
9. The Makefile holds `STAMP_BASE ?= main` and R2's recipe; the readers find this repo's own Status lines and overflow table.
10. `.venv/bin/python -m pytest -q tests/test_land3_stamp.py` passes, and under `.venv-floor`.

## 4. Findings that name this row

- None at the cut.
- Review 1 (the coordinator's ruling; tests `test_review1_*`, each red at `3cd9f28`): F1, a write that failed part-way left `plugin.json` moved with a traceback and exit 1; the new files are staged beside their targets and replaced only once all are staged, an `OSError` unlinks the temps, puts back what was replaced, and is exit 2 `stamp: <file>: <error>`. F2, R5's freshness was asked file by file, so a README fresh against one commit and a source fresh against another got a sidecar; the pair is now fresh against one reference (the sidecar as it stands naming both, or one commit, HEAD or a parent, whose sidecar names both and from which each differs only in its Status line), else `red sidecar` naming each file fresh against none, or the README. L2 rides: `stamp: status version <old> -> <new>` names a Status lines' version move the version line does not. L1 (no own path while HEAD is the merge base) is the ruling as built. L4 to L7 are NICE n191 to n194 (n130, n133, n134 moved to the overflow for the bound).

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger, no hq checkout beyond the brief.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.
