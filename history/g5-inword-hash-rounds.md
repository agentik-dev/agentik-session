# g5-inword-hash: the rounds before review 3

Sections 3a to 3f of `design/packets/g5-inword-hash.md`, moved here whole in phase 2 so the
packet keeps under doclint's 9,216 B ceiling. Their numbers are the packet's, so a
record that cites "packet §3d" finds it here.

## 3a. Round 1's results (cc4a20a, c7130e9)

- F1 to F4: the review's lines give the write and the deny; 10 cases red at d2f89d9.
- Beyond the review's lines: `cp a CLAUDE.md; echo x\` (F3's control, passed at the pin) is now denied, by F3's rule; `cp a CLAU\` newline `DE.md` (g6's lead 3) now reads `CLAUDE.md`, by F4's drop.
- F5 is NICE n173. Leads 1 and 2 stay as at the pin, for g6.

## 3b. Round 2's fixes, phase 1c (brief g5-r2-fixes R1 to R7)

The rule: a line the shell runs as a write of a gated file, which `d2f89d9` or the pin denied, must not pass at the head.

- R2-F1: a bare `(` in `${...}` left the `${` open, and `$${` opened one; now a bare paren in `${` is a word's and `$$` before `{` is the pid.
- R2-F2: a `case` pattern's `)` in `$(` closed the `$(`; now `_mask` counts each bracket's open `case`s, read at a command's start, and a pattern's `)` closes nothing.
- R2-F3: a backslash-escaped backtick ended a comment inside backticks; now it does not.
- R2-F4: a bare `)` in `${...}` was a subshell's edge to `_commands`, so the folder went unknown; now it is masked, as R2-F1's `(` is.
- Beyond the four, by fuzzing pin, 40aee95 and the head against sh, bash, zsh and dash: bash 3.2 opens no `${` inside a `$(`, so `bash_targets` adds that reading's targets where its mask differs; a `case` pattern's `)` in backticks is no subshell's edge.
- Newly over-refused (read as a write, no shell runs it): a line with an unclosed `${` or backtick before the write, as `${v)` newline `cp a CLAUDE.md`; on sh and bash 3.2 alone, R2-F2's lines, which zsh and dash run.

## 3c. Round 3's fixes, phase 1d (brief g5-g6 R1 to R11)

The rule: a line a shell runs as a write of a gated file, denied at the pin, `d2f89d9`, `40aee95` or `f1f012e`, must not pass at the head.

- R3-F1: a write in a `case` body in backticks; now `_commands` reads a `case` glued to its opening backtick (real backticks counted, an escaped or quoted one masked), and a third reading that masks no pattern's `)` in backticks joins the union (R8: unmasked in the first reading, a `cd` in the body moved the folder).
- R3-F2: a paren in backticks in a `${` was the brace's; now such a backtick is a bracket of its own; a `)` that closes nothing there stays masked (R8).
- R3-F3: a `)#` sh and bash 3.2 read as the end of a `$(`; now bash 3.2's reading counts no `case` and joins whenever its mask differs.
- R3-F4: a comment in nested escaped backticks; now it ends at an escaped backtick inside an escaped pair, else at the first unescaped one (R8: as proposed, round 2's L5 passed).
- R3-F5: `case` then a backslash-newline went uncounted; now `_KEY` reads it.
- R3-F6 a: a comment's closing backtick was the copy's destination; now a lone closing backtick is dropped and one at a word's end stripped, never into a `cd`. F6 b is the loose reading's.
- R3-F7: the comment's backtick is searched on its own line: 60 KB in one pair 0.012 s (3.6 s at `f1f012e`).
- Left, each passing at `f1f012e` too: R3-F6 b; `cd docs#c` (the guard trusts a `cd`); a comment at the third escaped level; a few token-fuzz lines with a `#` comment or a `${` paren in backticks. All for the loose reading.

## 3d. g6: the loose second reading (brief g6 R1 to R8; build 2 on this branch)

The owner, 2026-11-12: "fix all of these findings in the next session". g6's part is this
section, not a packet file of its own: one branch, one packet, one phase 2. Pin `a0055da`.

- R4 to R6, the strict reader: `_WRITE_WORD` is tried on the joined text too; `then`, `do`,
  `else`, `elif`, `if`, `while`, `until`, `{` and `!` are skipped as a wrapper is; an inner `-c`
  line that cannot be split gives the `split` mark and the outer commands are judged.
- R1: `loose_targets(text)`, pure: `(write or remove, word)` pairs, no list, no folder. It joins
  backslash-newlines, splits at `;&|(){}`, a newline and a backtick (none after a backslash),
  reads no quote, comment or heredoc; lists a write redirect's word (not `->`, `=>`, `>&N`) and
  the targets of `tee`, `sed -i`, `perl -i`, `cp`, `mv`, `install`, `rm`, `unlink` and git's
  three, its words ending at a blank then `#`.
- R2, as amended: the strict reading names each target's word and folder. A strict word, split
  at its blanks, stands for one loose target of its kind only where it resolves to the same
  path; one resolved to nothing stands for none; a raise stands for none. The loose target's
  own folder is the call's, moved by a `cd` or `pushd` only where the text before the target
  holds no paren, brace, backtick, `#`, backslash, `<<`, lone `|` or `&`, or reserved word (the
  amendment's (a) alone denies `cd /tmp/box && cp a CLAUDE.md`, acceptance 3). A target left
  over is resolved against the call's folder, its own and each folder the strict reading stood
  in: a gated path, or a list's removal, is denied. One that cannot be resolved passes.
- R3: the loose refusal is a `deny` with its own reason; `guard.jsonl` says which reading denied.

Acceptance (`tests/test_g2b_gates.py`, through the hook; baseline measured at `a0055da` with the
four shells, a stub `cp` that prints nothing):

1. g6's 19 lines, n131's and n138's: denied. At `a0055da`: 18 pass; `echo $(case x in x) echo
   a;; esac)#c; cp a CLAUDE.md`, ``echo ${x:-`echo a # don't`}; cp a CLAUDE.md`` and n173's
   `$'\' #'` line are denied by the strict reading already.
2. g6's three lines after a read: denied. At `a0055da`: pass.
3. g6's ten ordinary lines: pass, as at `a0055da`.
4. The price, each a named test, denied by the loose reading. At `a0055da`: pass.
5. The replay of the designer's 415,408 lines: at most 60 newly refused, none a read or a
   `git add`; counts only leave the scratch folder.
6. Round 3's lines (R3-F1 to F6 with F6 b, leads 1 to 5): each denied by one reading or the
   other. At `a0055da`: all but F6 b and leads 2 to 5 denied, by the strict reading.
7. With the loose reading off, the strict reading's results are `a0055da`'s but for what R5
   and R6 newly read; with both on, no line a shell runs as a gated write that `8153e52`,
   `d2f89d9`, `40aee95`, `f1f012e` or `a0055da` denied passes (round 3's command, two
   generators of 100,000 lines each, new seeds).

## 3e. Review 1's fixes (brief g5-g6 build 3, R1 to R10)

The rule (R1): a `cd`, `pushd` or `popd` the strict reading reads behind a reserved word adds a
folder and replaces none, so with the loose reading off the head denies every line `a0055da`
denies: a test of 392 lines built from parts; 80,000 fresh generator lines, 0 from deny to pass.

- F3: R5's `cd` replaced the folder. Now the strict reading keeps folder states: the first moves
  as `a0055da`'s, one follows every `cd` as `db19d51`'s, at most 16; each target is judged in each.
- F1: a reserved word was skipped after an assignment or a wrapper; now only as a command's
  first words, in both readings.
- F2: a strict word's pieces were credits a later loose target could spend. Now a word with a
  blank stands for loose targets only where one command lists every piece of it, in order (the
  reviewer's "never by its pieces" alone denied g6's ordinary `sed -i '' 's/the CLAUDE.md
  file/x/' notes.md`). Review 1's lead 2 is denied too.
- F4: the loose reading was quadratic. Now each `cd` and target is resolved once; targets left
  times folders is at most 4,096, and a line past it is denied with the loose refusal;
  `(?<!\d)\d*`. The
  replay's largest product is 286 (one line over 256), so no line of it or of the tests meets
  4,096; at about 0.1 ms a pair the loose reading stays near 0.4 s at the bound.
- F5: `>&` before a word; `_LOOSE_SEP` no longer splits at the `&` of `>&` or `<&`.
- The replay of 415,408 lines: 72 newly refused against `a0055da`, all by the loose reading, the
  same 72 lines as `db19d51`'s (none a read, a `git add` or a commit); R1's reads add none.
- Leads: 1 and 3 are n176 and n177 (design/20's g7), 4 is n178; 5 landed with R1 (0 lines).
  Lead 6's list is empty: rounds 1 and 2's probed-clean lines hold no `cd` behind a reserved word.

## 3f. Review 2's fixes (brief g5-g6 build 4, R1 to R10)

No new rule of reading: F1 to F4 each go back to what `db19d51` read at that point, keeping
the one thing review 1 needed; F5 is a bound.

- F5: one `-c` line was read again in each folder state, 256 paths a target. Now the strict
  reading counts as it reads, over the whole line: past 65,536 judgements or 4,096 distinct
  paths it is denied, never passed unread; a `-c` line read in many folders is split once.
  F5's lines: 7 to 17 s at `6aed3c5`, 0.02 to 0.22 s now, each denied. The tests' largest
  counts are 18,000 and 16; the replay's, 347 and 212.
- F1: the loose reading skips a reserved word wherever its loop meets it, as `db19d51` did;
  review 1's R2 stays in the strict reading, where `time -p` now stands in the run.
- F2: the loose reading splits at an `&` whose `<` or `>` is escaped. Splitting at every `&`
  as `db19d51` did would pass `bash -lc 'cp a >&2 CLAUDE.md'`, which `6aed3c5` denied.
- F3: a word judged in several folder states is one credit, the followed state's entry.
- F4: a run of loose pieces stands for a word with a blank only where its folder resolves
  the run to the path the strict reading judged.
- Checks against the seven commits and `6aed3c5`: review 2's hand lines (k1, k4, k5), review
  1's (c1, c2, c3) and the sweep (k2a, k2b, 1,148 lines) REGRESS 0; fuzz 100,000 token and
  100,000 valid lines (seeds 93111, 93112), four shells: REGRESS 0; with the loose reading off
  against `a0055da`, 80,000 lines (seeds 93121, 93122): 0 from deny to pass.
- The price: of review 2's 63 ordinary lines, 14 are refused that `db19d51` passed, the same 14
  as at `6aed3c5` (review 1's R3 nine and the `sed` script, R5's two `>&`, R1's two `if cd`).
  The replay: 72 newly refused against `a0055da`, the same 72 lines as `db19d51`'s.
- Left: lead 5 (n183) is 6.9 s with a `cp` after it; F4's root in one folder
  (`echo x > "a CLAUDE.md"; bash -lc 'tee a CLAUDE.md'`) passes at every commit.
