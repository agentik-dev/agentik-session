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

## 4. Findings that name this row

Round 1 to review 2, each finding, its fix, the checks and the price, are in
`history/g5-inword-hash-rounds.md`, moved there whole in phase 2 with their numbers: §3a round 1's
results (cc4a20a, c7130e9); §3b round 2's fixes (phase 1c); §3c round 3's (phase 1d); §3d g6, the
loose second reading; §3e review 1's fixes (build 3); §3f review 2's fixes (build 4).

Review 3, of `4a66730`:

- Ruling: closed. The row lands as it stands and is mended no further: every finding passes on main today, so none is a regression against what is landed. The price stands: 72 of 415,408 replayed lines newly refused, none a read, a `git add` or a commit.
- F1 (R3): after an even run of backslashes `\\>&` is a redirect, but the loose split cuts R5's word off it; 10 lines. NICE n186, with lead 3.
- F2 (R3): the split hands `cp a \>& ln -f a CLAUDE.md` to `ln`, which no reading reads; 3 lines. NICE n187, with lead 1.
- F3 (R2): a `cd` behind `time -p` adds a 17th folder state, and the cap of 16 drops the followed one; 4 lines. NICE n188, with lead 2.
- F4 (R2): the strict word's credit is keyed by path, not by folder; 1 line, which `db19d51` passes too. NICE n189.
- F5 (review 1's R3): `_spent` keys a run's whole path, the same in every folder when its first piece is absolute; 1 line. NICE n190, with lead 4.
- Lead 5: the 100 KB `pushd` shape takes 2.2 s at the head, not build 4's 6.9 s; folded into n183.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, nothing written in the reviewer's folder.

## 6. Report

The hand-back to the hq coordinator: the head sha, each finding at `d2f89d9` and now, the changed-line count, the choices made.
