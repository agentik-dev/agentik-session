# Packet g5: an in-word `#` no longer hides the rest of a line from the instruction guard

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief g5 (S1: a gated write passes the guard) and its round 1 refutation of `d2f89d9` (phase 1b) |
| pin | `8153e52` on main (2.0.0-alpha.91); phase 1 at `d2f89d9`. Worktree `.claude/worktrees/g5-inword-hash`, branch `g5-inword-hash`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads live state (temp folders only); no relay verb; `unattended.py` untouched (another row is in it) |
| may touch | `plugin/lib/claude_session/instructionguard.py` (`_mask`, `_commands`, `bash_targets`, `_bash_gated`); `tests/test_g2b_gates.py` (the g5 section); `NICE_TO_HAVE.md` (one row); this packet and the sitting's record |
| verify | while building, the guard test files under `.venv` and `.venv-floor` and the whole suite under `.venv`; the gate queue's `make check` once, last, in phase 2 |
| acceptance | §3; each line red at its baseline, green now |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet before the fix commits |

## 1. What the source says: the code at the pin

- `_commands` handed `_mask(text)` to `shlex`, whose commenter cut a word at any `#` and, at a comment's end, ate the newline, so the next command joined the one before.
- `_mask` held its own comment rule: a `#` after a blank or an operator character, `)` included, outside quotes; it knew no `$(`, `${` or backtick.
- `bash_targets` turned a backslash-newline into a space before `_mask`, and any `ValueError` from `shlex` passed the whole line (the gate's fail-open).

## 2. Rulings

- R1: a `#` starts a comment only where the shell reads one: at a word's start, outside quotes. `_mask` alone decides; `shlex` gets no commenter.
- R2: the words read back whole: `echo x#y` is `['echo', 'x#y']`.
- R3: the other shell-line splits in `plugin/lib` (`shlex.split` in `commit.py`, `install.py`, `agentik_install.py`) take no commenter and refuse no shell line: nothing to fix.
- Round 1, F1: a `#` straight after the `)` that closes a `$(` or `$((` is in-word; after a subshell's own `)` it starts a comment.
- Round 1, F2: no comment while a `${` is the innermost open bracket; a comment inside open backticks ends at the closing backtick.
- Round 1, F3: when `shlex` stops splitting, the commands read before it are judged; a line whose first command cannot be read keeps the fail-open.
- Round 1, F4: `_mask` drops a backslash-newline outside single quotes and outside a comment; a comment still ends at its newline.
- Round 1, F5: a NICE row widening n132, not built. The round's three leads are row g6, not built here.

## 3. Interfaces: the acceptance table

1. `echo x#y`, `v=${TAG#v}`, `echo $#`, `echo ${#a[@]}`, `echo a\#b`, each then `; cp a CLAUDE.md`: the write, the hook denies. Pin: `[]` but for `a\#b`.
2. `echo x #y; cp a CLAUDE.md`, `# cp a CLAUDE.md`: `[]`; `echo x #c` newline `cp a CLAUDE.md`: the write (pin `[]`).
3. A quoted `#` is its word (pin: already the write).
4. R2's words; every other test green.
5. F1: `echo $(echo a)#c`, `x=$(date +%s)#tag`, `echo $((1+2))#c`, then `; cp a CLAUDE.md`: the write; `(cd x) #c; cp a CLAUDE.md`: `[]`, as `/bin/sh` and `/bin/bash` read it. At `d2f89d9`: `[]`.
6. F2: `x=${l%% #*}`, `echo ${x:- #y}`, ``echo `echo a #b` ``, then `; cp a CLAUDE.md`: the write. At `d2f89d9`: `[]`.
7. F3: `cp a CLAUDE.md; echo x#y\` and `cp a CLAUDE.md` newline `echo x#'y`: denied, one `open` line. At `d2f89d9`: passed. `cp a CLAUDE.md \` still passes.
8. F4: `# note \` newline `cp a CLAUDE.md`, `echo x\` newline `#y; cp a CLAUDE.md`: the write. At `d2f89d9`: `[]`.
9. The round's "probed and clean" lines keep their result, as a table in the tests.

## 3a. Round 1's results (cc4a20a, c7130e9)

- F1 to F4: the review's lines give the write and the deny; 10 cases red at d2f89d9.
- Beyond the review's lines: `cp a CLAUDE.md; echo x\` (F3's control, passed at the pin) is now denied, by F3's rule; `cp a CLAU\` newline `DE.md` (g6's lead 3) now reads `CLAUDE.md`, by F4's drop.
- F5 is NICE n161. Leads 1 and 2 stay as at the pin, for g6.

## 3b. Round 2's fixes, phase 1c (brief g5-r2-fixes R1 to R7)

The rule: a line the shell runs as a write of a gated file, which `d2f89d9` or the pin denied, must not pass at the head.

- R2-F1: a bare `(` in `${...}` left the `${` open, and `$${` opened one; now a bare paren in `${` is a word's and `$$` before `{` is the pid.
- R2-F2: a `case` pattern's `)` in `$(` closed the `$(`; now `_mask` counts each bracket's open `case`s, read at a command's start, and a pattern's `)` closes nothing.
- R2-F3: a backslash-escaped backtick ended a comment inside backticks; now it does not.
- R2-F4: a bare `)` in `${...}` was a subshell's edge to `_commands`, so the folder went unknown; now it is masked, as R2-F1's `(` is.
- Beyond the four, by fuzzing pin, 40aee95 and the head against sh, bash, zsh and dash: bash 3.2 opens no `${` inside a `$(`, so `bash_targets` adds that reading's targets where its mask differs; a `case` pattern's `)` in backticks is no subshell's edge.
- Newly over-refused (read as a write, no shell runs it): a line with an unclosed `${` or backtick before the write, as `${v)` newline `cp a CLAUDE.md`; on sh and bash 3.2 alone, R2-F2's lines, which zsh and dash run.

## 4. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, nothing written in the reviewer's folder.

## 5. Report

The hand-back to the hq coordinator: the head sha, each finding at `d2f89d9` and now, the changed-line count, the choices made.

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
   a;; esac)#c; cp a CLAUDE.md`, ``echo ${x:-`echo a # don't`}; cp a CLAUDE.md`` and n161's
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
- Leads: 1 and 3 are n164 and n165 (design/20's g7), 4 is n166; 5 landed with R1 (0 lines).
  Lead 6's list is empty: rounds 1 and 2's probed-clean lines hold no `cd` behind a reserved word.
