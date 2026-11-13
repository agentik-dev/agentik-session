# Packet g8a: the reader's new parts, one walk of a line's commands

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief g8a (hq design/20 §3 item 6, §5, §10); the owner's answer of 2026-11-13 to hq question 49 |
| pin | `b92e4e0` on main (2.0.0-alpha.103, the merge of g7-one-reader). No version here: phase 2's. Worktree `.claude/worktrees/g8a-reader-parts`, branch `g8a-reader-parts`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no `make`, no gate job in this phase; no `claude`; no relay verb; probes run as `PY -I` with a temp HOME and write only in a scratch folder |
| may touch | `plugin/lib/claude_session/shellreader.py`, `unattended.py`; `tests/test_g8a_reader.py` (new), `tests/test_g7_reader.py`, `tests/test_u3.py`, `tests/test_g2b_gates.py`; `NICE_TO_HAVE.md`; this packet and the sitting's record |
| verify | pytest under `.venv` and `.venv-floor` on the files of §3; the differential probes of §3 against a `git archive` of the pin; no `make check` (phase 2's) |
| acceptance | §3; `tests/test_g8a_reader.py` red at the pin (its import fails), green now, under both venvs |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet, the failing tests, the reader, the make rule, the records |

## 1. What the source says: the code at the pin

- `shellreader.py` holds the strict reading (`_heredocs`, `_mask`, `_commands`, `_parse`, `_strict`, `_judge`), the loose one (`_loose`, `loose_targets`, `_LOOSE_*`, `_clean`) and `_substituted`. `_loose` reads `_SHELLS` and `_WRAPPERS`, so neither changes: the five shells are a new name.
- `_strict` walks `_commands`' yields itself: wrappers, reserved words, `cd` and the subshell's folder states are in its loop. A bare `$(` is read as a subshell's parens, so `echo a$(x)b c` reads a command `b`; a quoted `$(` and backticks are words.
- `unattended.unbounded` walks `_commands` again with its own `-c` rule (`_DASH_C`, `SHELL_DEPTH`) and `_substituted`'s paren count.
- No `DECISIONS.md` and no `CLAUDE.md` on main (NICE n2): no repo entry binds the row.

## 2. Rulings (brief g8a)

- The owner's words: the suite's guards live in the session plugin (2026-11-13, hq question 49). design/20 §3 item 6 gives the reader the command word past a path, the wrappers and assignments; git's global options set apart; a quoted substitution, backticks and a shell's heredoc script read as a subshell is; a mark for a part it could not read. It refuses nothing new.
- R1, the bound: the reader reads more, nothing else changes; an answer that differs outside a class R4 to R8 names is a defect. `_loose`, `loose_targets`, `_LOOSE_*`, `_clean` and `instructionguard.py` are not touched.
- R2, the surface: `commands(command, cwd, env) -> (cmds, unread)`; `Cmd(name, args, pre, heres, level)`; `Unread(why, text)`, `why` one of `split`, `eval`, `below`, `piped`; `git_words(args) -> (globals, sub, rest)`. `_Bound` past a bound and nothing else; a line `shlex` cannot split is one `Unread("split", line)`.
- R3, one walk: one function turns a line into its commands; `_strict` and `commands` read through it. `_strict` keeps its signature, its result's shape and `_judge`'s rules. Only the module holds `shlex.shlex`.
- R4, the command word: past reserved words, assignments and today's wrappers; a wrapper's option that takes an operand takes it (`sudo -u -g -h -p -C -D -R -T -U -r -t` and long forms, `env -u -C -P`, `nice -n`, `exec -a`, `time -o -f`); `command -v`/`-V` is the `command`. No other runner is followed. A shell's name is matched case-blind.
- R5, a shell's script: `bash`, `sh`, `zsh`, `dash`, `ksh`; a `-c` cluster, its text the first word after it that is no option (operands of `-o`, `+o`, `-O` skipped); a heredoc is the script with `-s` or no operand but `-`. Read at level 1 from level 0; from level 1, `Unread("below")`.
- R6, substitutions: `$(...)` and backticks are commands of the line at their word's level in a subshell's folder scope: bare, double-quoted, in an assignment, in a redirection's word, in an unquoted heredoc's body. Fresh quoting inside `$(`; one level of `\` off inside backticks; none in single quotes, after `\$`, or in `$((`. Nesting past 32 raises `_Bound`. Each read once. The words around a substitution stay with their command.
- R7, unread: `split`, `eval` (`eval`'s arguments; `env -S`), `below`, `piped` (a pipeline's words and heredoc bodies before a shell with no script; a here-string into one).
- R8, git: `git_words` takes an operand for `-C`, `-c`, `--config-env`, `--git-dir`, `--work-tree`, `--namespace`, `--super-prefix`, `--attr-source`; `_git_paths` is rebuilt on it.
- R9, the make rule: `unbounded` reads through `commands`; refuses on a make word of any `Cmd`, a `split`, or another `Unread` whose text holds a make word. `_substituted`, `SHELL_DEPTH`, `_DASH_C` are deleted; the docstring names the module (n203).
- R10, R11: g7's table changes on its 13 named lines and no other; an old test's assertion changes only where it pins an answer R4 to R9 change, each listed in the record.
- R12: NICE n200, n201, n203 leave; n177 leaves if read; n197 shortened to what is left. The file stays under 24,576 B.
- R13, the commits: this packet; `tests/test_g8a_reader.py`, red; the reader with the old tests' edits; the make rule; the NICE rows with the sitting record.

## 3. Interfaces: the acceptance table (brief g8a), with the pin's results

The surface is R2's: `commands`, `Cmd`, `Unread`, `git_words`, `_Bound`. Baselines at the pin, measured in this sitting (`PY` each of `.venv/bin/python`, `.venv-floor/bin/python`):

1. `git merge-base --is-ancestor b92e4e0 main` exits 0 and the four files' diff is empty: green before any work.
2. `PY -m pytest -q tests/test_g8a_reader.py`: at the pin an import error; now all pass.
3. `PY -m pytest -q` on the eight files of the brief: no failure; pin `761 passed`.
4. `PY -m pytest -q tests/test_hooks.py tests/test_bare_machine.py tests/test_install.py`: the pin's counts.
5. `git diff <pin>` leaves `instructionguard.py`, `hooks.py`, `plugin/hooks`, `plugin/.claude-plugin` alone; the stat names only the files of `may touch`.
6. to 11. The differential, gate, make-rule, real-shell and cost probes of the brief, run in a scratch folder; their numbers are in the record.
12. The module imports alone.
13. `scripts/recordlint` exits 0; no row n200, n201, n203.

## 4. Findings that name this row

- NICE n177 (nested escaped backticks), n197 (what the make rule passes), n200 and n201 (`_substituted`'s paren count), n203 (`unbounded`'s docstring): R12.

## 5. Forbidden reads

- A relay ledger or a reference snapshot, whole; a replay line printed or kept outside the scratch folder (counts only in any record).

## 6. Report

- The sitting's record (`history/sittings/2026-11-13-6-g8a-reader-parts.md`): each acceptance line with the pin's result and this head's, the choices made inside the rulings, what differed from the brief and what was not verified.
