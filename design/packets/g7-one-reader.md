# Packet g7: the strict and the loose reading of a shell line in one module, no answer changed

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief g7 (hq design/20 §3 item 6, §5, §10 R1-F8); the owner's answer of 2026-11-13 to hq question 49 |
| pin | `2aaa789` on main (2.0.0-alpha.101, the merge of u3-loop-lines; its tree is `42e8a7c`'s, `git diff --stat 42e8a7c 2aaa789` empty). No version here: phase 2's. Worktree `.claude/worktrees/g7-one-reader`, branch `g7-one-reader`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no `make`, no gate job in this phase; no `claude`; no relay verb; probes write only in a scratch folder, with a temp HOME |
| may touch | `plugin/lib/claude_session/shellreader.py` (new), `instructionguard.py`, `unattended.py`; `tests/test_g7_reader.py` (new), `tests/test_g2b_gates.py` (the module's name only); `NICE_TO_HAVE.md` (the g7 rows' words and areas); this packet and the sitting's record |
| verify | pytest under `.venv` and `.venv-floor` on the files of §3; the differential probes of §3 against a `git archive` of the pin; no `make check` (phase 2's, after the version) |
| acceptance | §3; `tests/test_g7_reader.py` red at the pin, green now, under both venvs |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet, then the failing tests, then the move, then the records |

## 1. What the source says: the code at the pin

- `instructionguard.py` (1,345 lines) holds both readings: the strict one from `_WRITE_WORD` (:384) to `_others` (:855), the loose one from `_LOOSE_SEP` (:872) to `loose_targets` (:950); `_home` and `_tilde` (:83, :87) serve `_resolve`. What joins them to the lists is `_loose_gated`, `_spent` and `_bash_gated` (:956 to :1076).
- `unattended.py:31` imports `_SHELLS` and `_commands` from the guard; `unbounded` (:675) walks a line's words and `_substituted` (:715) cuts a word's `$(` text by a paren count.
- Three text matches read a Bash line without a reader: `_WRITE_WORD`, `hooks.HELPER_CHARTER` and `hooks.RESPAWN_CMDS`. No other module calls a reader.

## 2. Rulings (brief g7)

- The owner's words: the suite's guards live in the session plugin (2026-11-13, hq question 49). This is design/20's first row: the reader becomes its own module, nothing added, so that the next row's four refusals read through it.
- R1, a move: for every line, each reader's whole answer is the pin's, an exception's type and words included. Anything that changes an answer is a defect, a mend included.
- R2: `plugin/lib/claude_session/shellreader.py` imports `os`, `re`, `shlex` and `pathlib` and nothing of the package; its docstring says what it holds, that it knows no list, log or payload, and its packets (g3, g5, g6, u3).
- R3: 53 statements leave `instructionguard.py`, each whole with the comments on and under it, text and order kept: `_home`, `_tilde`; `_HEREDOC` to `_TAKES`; `_heredocs`, `_mask`, `_commands`; `_resolve`, `_py_literals`, `_copy_args`, `_copy_like`, `_git_paths`; `bash_targets`, `_Bound`, `_Paid`, `_parse`, `_strict`, `_CAP_STATES`, `_STRICT_BOUND`, `_STRICT_READS`, `_move`, `_states`, `_judge`, `_others`; `_LOOSE_SEP` to `_LOOSE_COND`, `_clean`, `_loose`, `loose_targets`.
- R4: what names a list, the log or a payload stays (`_WRITE_WORD`, `_loose_gated`, `_RUN_CAP`, `_LOOSE_BOUND`, `_spent`, `_bash_gated`, `log`, `check`, the lane, the doctor's row). The guard imports `_Bound`, `_home`, `_loose`, `_resolve`, `_strict`, `_tilde` from the module and no other name; its docstring's R3 paragraph names the module.
- R5: `_substituted` moves from `unattended.py` unchanged, the 54th name; its one import line reads `_SHELLS`, `_commands` and `_substituted` from `.shellreader`.
- R6: no rename, no public alias, no new function or parameter, no copy left behind.
- R7: in `tests/test_g2b_gates.py` a line that reaches or patches a moved name through `instructionguard` names `shellreader`; its import line gains `shellreader`. No other line of an existing test changes.
- R8: `_WRITE_WORD`, `hooks.HELPER_CHARTER` and `hooks.RESPAWN_CMDS` stay text matches; `hooks.py`, `hooks.json` and the manifest are not touched.
- R9: nothing is mended: NICE n174 to n190 and n197, and u3 review 2's two findings on `_substituted`, stay; the ten rows that named this row end `left by g7, a move`, their areas name the module where the code moved.
- R10: four commits: this packet; the red test; the move with R7's edits; the NICE rows with the sitting record. R11: no version, no merge of main, no gate job.

## 3. Interfaces: the acceptance table (brief g7), with the pin's results

The pin's tree is `42e8a7c`'s; the numbers in brackets were measured there by the designer.

1. Main holds `42e8a7c` and the reader's four files are its. Pin: `0`, no diff.
2. `tests/test_g7_reader.py`: pin, every test fails (`No module named 'claude_session.shellreader'`); now all pass.
3. `test_g1_instructions`, `test_g2b_gates`, `test_g4_folder_gates`, `test_u2`, `test_u3`, `test_unattended`: [`647 passed`] under each venv, the same now.
4. `test_hooks`, `test_bare_machine`, `test_install`: the pin's counts, no failure: a frozen tree carries the module.
5. `test_g2b_gates.py` with the module's name read back as the guard's differs from the pin's in the import line alone; the tests' diff names that file and the new one.
6. The sorted non-blank lines of the guard and the loop, against the guard, the module and the loop now: only imports, docstring lines and `# ----` rules differ.
7. The syntax trees: each of the 54 statements' `ast.dump` equal, every other top-level statement of the two files equal: `54 of 54`, `0 other`.
8. `/usr/bin/python3` importing the module alone loads `claude_session` and `claude_session.shellreader`.
9. The tests' own lines [891 distinct] and the packets' acceptance lines of the sibling repos [981, 808 distinct], each through `_commands` (three readings), `_heredocs`, `_mask`, `_strict` with `stood`, `_loose` and `unbounded`, pin against now: `0 differ` under both venvs.
10. 200,000 distinct fuzzed lines, two seeds: `0 differ` under both venvs [100,000 in 20 s].
11. Three days of Bash lines, read only, counts only, through `check` in a box gating `CLAUDE.md` and through the readers: `0 differ` [79,146 lines; 112 denied, 23 strict and 89 loose; 4,467 unbounded].
12. The packets' lines: the set `unbounded` refuses is the same both sides, each opening with `make` after its assignments [45 of 981, 13 distinct]; the other 936 pass both sides.
13. The cost: the tree's launcher on one Bash payload, 40 cold runs a tree, interleaved, twice: the median no more than 10 ms above the pin's [61 to 67 ms]; in process the recorded lines within 5% of the pin's [5.0 s].
14. No NICE row names `design/20's g7`; `scripts/recordlint` exits 0.
15. The diff from the pin names only this row's files; the manifest, the hooks and `hooks.py` untouched.

The lines where the readers differ, the new test's table at the pin: M is `make x > CLAUDE.md`. Strict is `bash_targets` in a made-up folder, loose `loose_targets` (it lists `CLAUDE.md` on every line), make `unbounded`. Strict reads and make refuses: `M` bare, behind `bash -c`, `bash -o pipefail -c`, `/bin/bash -c`, `x=1 env`, `sudo`, `time -p`, `if true; then`, `( )`, `{ }`, `echo $(M)`; and `echo make > CLAUDE.md`, `git log -- make > CLAUDE.md`. Strict reads nothing and make refuses: `bash -lc`, `bash -c -e`, `BASH -c`, `bash -c "bash -c '...'"`, `echo "$(M)"`, a heredoc's body to `sh` or `cat`. Strict reads and make passes: ``echo `M` ``, `./make.sh > CLAUDE.md`. Neither: `ksh -c`, `eval`, `echo 'M' | sh`, `echo 'M'`, `git commit -m "M"`, `echo ok # M`, u3 review 2's two `$(case ...)` and `${y:-a)}` lines. Make cannot split what strict reads: `n="$(grep -c ')' f.txt)"; echo "$n" > CLAUDE.md`. Strict raises `ValueError` and make cannot split: `echo "it's" 'x > CLAUDE.md`. The next row changes each knowingly.

## 4. Findings that name this row

- NICE n176, n177, n179, n180, n181 and n186 to n190 named design/20's g7: they stay, ending `left by g7, a move`; the area of n174 to n178 and n180 to n188 is the module, n179, n189 and n190 keep the guard's; n186's and n190's line numbers are the new files'. No row is added and none leaves.
- u3 review 2's two findings on `_substituted` (R2-F1, R2-F2: its paren count knows no quote, `case` pattern or `${`) stay as they read: the table above pins both. They enter NICE with in2's phase 2; their area is the module.

## 5. Forbidden reads

No live state root, no file under `~/.claude` but the replay's read-only pass (counts only, nothing copied out of the scratch folder), no hq checkout but the brief.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.
