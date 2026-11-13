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
