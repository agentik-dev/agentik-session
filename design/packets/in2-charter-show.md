# Packet in2: `charter show [REPO...] [--json]`, and a charter's part for what waits on the owner

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief in2 (hq design/17's row in2: §3 items 2, 5 and 6; §6) |
| pin | `148fde3` on main (2.0.0-alpha.98). Worktree `.claude/worktrees/in2-charter-show`, branch `in2-charter-show`; `.venv`, `.venv-floor` linked from the main checkout. No version bump in phase 1 |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`, no gate job in phase 1; no `claude`; no test reads live state or writes the live home; no relay verb; a line naming `charter` with a word but `check` runs from a script file under a temp state home |
| may touch | `plugin/lib/claude_session/{charter.py,cli.py,hooks.py}` (cli: `cmd_charter` and the parser; hooks: `CHARTER_READS`, `HELPER_CHARTER_DENY`), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `NICE_TO_HAVE.md` (one row), `tests/test_in2_charter_show.py` (new), `tests/{test_charter.py,test_fw1a.py,test_rules.py,test_n33.py}` where one pins `open`'s text or the denial's; this packet and the charter |
| verify | phase 1: `python -m pytest -q` under `.venv` and `.venv-floor` on the new file and the four named; phase 2, on the coordinator's word: the gate queue's `make check` |
| acceptance | §3; `tests/test_in2_charter_show.py` green under both venvs (red at the pin) |
| budget | about 90 tool calls, `claude-opus-5-5` |

## 1. What the source says: the code at the pin

- `charter.py` knows six parts; `check_text` refuses the missing ones but While waiting; `warnings` adds While waiting's shape warnings whatever pacing says, and `_near_miss` names a heading that differs by case or a tail. `open` writes four `##` parts.
- `cli.cmd_charter` takes `open`, `check`, `close`; the parser's `action` has those three choices, so `charter show` exits 2 with argparse's `invalid choice: 'show' (choose from 'open', 'check', 'close')`.
- `hooks.CHARTER_READS` is `("check",)`: a helper's Bash that names `charter show` is denied.
- No file of the tool names `Waits on the owner`.

### The owner's words

None bind this row. hq design/17's row in2: the owner's inbox joins reads the tools give, and the charter's grammar is this tool's. What waits on the owner's hand is written under a heading no tool names.

### The ledger

No `DECISIONS.md` at the pin. Cited: hq entry 6 (the 3.9 floor, the standard library alone) and hq entry 37 (made-up names).

## 2. Rulings (brief in2)

- R1, what stands. The six parts and their refusals, the ceiling, every warning and both reds, `close`'s exit line, `check`'s exits: byte for byte. New: a seventh part, optional; the action `show`; `tests/test_in2_charter_show.py`.
- R2, the part. `## Waits on the owner`, anywhere among the `##` parts. No part is legal and warns nothing. Its non-blank lines are `- none` alone, or hand lines, ``- hand: <what>; `<command>` ``: the line ends in one code span that holds no backtick, with `; ` before it; `<what>` is the text between and may hold a `;`.
- R3, `open` writes the part with the one line `- none`, directly before `## While waiting`.
- R4, `check` and `close` warn on stderr, after While waiting's warnings, whatever pacing says, the exit unchanged:
  - `Waits on the owner is empty: write - none, or the hand lines`
  - `Waits on the owner has '- none' beside other lines: drop '- none' or the others`
  - ``Waits on the owner line is not '- hand: <what>; `<command>`' or '- none' alone: <line>``
  - `heading '<line>' is not '## Waits on the owner'`, for a heading that differs by case or a tail, as `_near_miss` reads While waiting's.
- R5, `show`. `agentik-session charter show [REPO...] [--json]`; `--json` with another action exits 2. REPO is a directory; the default is the git top of the working directory, else the working directory. Its charter folder is `--dir` when given, else REPO's own `session.charter.dir` by `resolver.resolve` from REPO (a failed resolve reads as `history/sittings`), under REPO. The newest charter is the file named `<date>-<n>.md` or `<date>-<n>-<suffix>.md` with the greatest date, then the greatest n, then the last name. A REPO is skipped, and the read goes on, as `not a directory`, `no charter` or `unreadable`.
- R6, what it never does. No write: no session record, no `resolved.json`, no lock. No `git` but for the default REPO. Exit 0 whenever the read ran, a charter outside the form included; 2 for usage.
- R7, `--json`: one object and nothing else on stdout, `{"schema": "agentik.charter/1", "ok": true, "repos": [...], "skipped": [{"repo", "why"}]}`. A repo: `repo` and `file` (real paths); `name` (the file's, less `.md`), `date`, `n`; `mtime` (whole epoch seconds); `closed` (it holds an `- exit taken: ` line); `title` (the title line after `: `, else null); `parts` (those present of `title`, `table`, `Done-ness`, `Handover`, `Waits on the owner`, `While waiting`, `Next act`, in this order); `refusals` (`check_text`'s lines, `[]` in the form); `next_act` (`next_act_line`, else null); `waits` (null with no part; else one `{"line", "what", "command"}` for each non-blank line but `- none`, `line` 1-based; a line of another shape gives itself whole as `what`, and `command` null).
- R8, the text view, plain, one block a repo with a blank line between: `== <folder's name>  <name>  <k> for the owner's hand` (`no Waits part` in the count's place where `waits` is null, `  closed` last where it is); `next  <next_act>` or `next  (none)`; ``hand  <what>; `<command>` ``, and for another shape `hand  <the line>  (no command)`; `form  <refusal>`, one each; last, `skipped (<why>): <names>`, one line a reason.
- R9, a helper may call it. `hooks.CHARTER_READS` gains `show`, and `HELPER_CHARTER_DENY`'s parenthesis reads: (a helper's charter calls are `agentik-session charter check <file>` and `charter show`, the verb first).
- R10, the records. `charter.py`'s docstring (seven parts, the seventh optional), the parser's help, the skill's "The charter" (the part in its list, a `show` line), the RUNBOOK's charter paragraphs and its sentence on a helper's calls. The skill's `description` and the README stay. One S4 row in `NICE_TO_HAVE.md` says the README names neither the part nor `show`.

## 3. Interfaces: the acceptance table (baseline at the pin)

Each a case of `tests/test_in2_charter_show.py`, through `cli.main`, in temp repos `pear` and `quince` under a temp HOME and state home.

| # | line | at the pin |
|---|---|---|
| 1 | `charter show pear --json`: R7's object for `2026-11-13-1` (title, seven parts, no refusal, Next act's first line, two `waits`: a hand line split, a prose line whole with `command` null), exit 0 | exit 2, `invalid choice: 'show'`, nothing on stdout |
| 2 | the text view of line 1: the `==`, `next` and two `hand` lines | as line 1 |
| 3 | `2026-11-13-10.md` is newer than `-9.md` and `-2-row.md`; `--dir notes` reads `pear/notes` | as line 1 |
| 4 | `quince`'s prose file: its refusals, `parts` `[]`, `next_act` and `waits` null, `form` lines; `pear quince nowhere bare`: two repos, two skipped, exit 0; no REPO from inside `pear`: `pear`'s top | as line 1 |
| 5 | ``- hand: ask twice; then wait; `a; b | c` ``: `what` `ask twice; then wait`, `command` `a; b | c` | as line 1 |
| 6 | `check` and `close` print R4's four warnings for their cases, the exit kept; no part, `- none` or hand lines alone: no new warning | `check` prints nothing for the prose line, exit 0 |
| 7 | `open` writes the part and `- none` before `## While waiting`; `check` passes it silent; `show` says `0 for the owner's hand` | four `##` parts, no Waits part |
| 8 | every `show` leaves the temp HOME, state home and repos byte for byte, a session id set too | no read |
| 9 | a helper's `charter show` passes the hook; `charter open` is denied with R9's sentence | `show` denied |
| 10 | `charter check --json x.md` exits 2; `charter --help` lists `show` | the first holds; `{open,check,close}` |
| 11 | the new file and `test_charter.py`, `test_fw1a.py`, `test_rules.py`, `test_n33.py` pass under `.venv` and `.venv-floor` | the new file absent |

## 4. Findings that name this row: the choices inside the rulings

- A hand line is read by hand, not by a regex, so the read is linear: it opens `- hand: `, ends in a backtick, the backtick before that has `; ` before it, and both `<what>` and `<command>` hold something past blanks. A line's trailing blanks are cut first, as While waiting's are.
- `waits[].line` is the line's 1-based number in the file.
- The near-miss heading warns only when the exact part is absent, as While waiting's does.
- "Newest" picks by name among every entry of the folder, so an entry of that name that cannot be read (a folder, no permission) is `unreadable`; a folder that is missing or cannot be listed is `no charter`.
- `skipped[].repo` is the real path; the text view names a repo by its folder's name, and the `skipped` lines are a last block after a blank line, names joined by `, `.
- `--json` prints the object with an indent of 2.
- Each REPO's folder resolves as `check`'s rules do (`resolver.resolve` from the REPO, the session id or `unsaved`, the launch profile); an absolute `--dir` is taken as is.
- `--continue` and `--replace` with `show` keep their refusals (exit 2).
- Old tests changed: `test_charter.py`'s `test_close_appends_one_line`, `test_s21_open_seeds_the_handover_line`, `test_s21_open_seeds_nothing_with_priority_off`, `test_s40_open_writes_the_section` (they pin `open`'s text); `test_n33.py`'s `VERB_FIRST` (the denial's sentence). `test_fw1a.py` and `test_rules.py` unchanged.
- NICE n191 (S4): the README names neither the part nor `show`.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done; phase 2 on the coordinator's word.
