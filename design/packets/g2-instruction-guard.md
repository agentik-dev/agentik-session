# Packet g2: the prompt before an edit of instruction text

| item | value |
|---|---|
| from | the management sitting's coordinator, 2026-11-11, brief g2; the design is the management repo's design/09 (§7.2 all of it: what the guard is, what it does not do, the guarded files; §1 fact F11). The owner, 2026-11-11: "making sure that the rulings/guidelines/claude configs get updated the correct way through a lane, not ad hoc." |
| pin | main at `9bd9571` (2.0.0-alpha.78, g1 on it). Version 2.0.0-alpha.79 (the code's commit), 2.0.0-alpha.80 (the records' commit, which changes the skill's page). Worktree `.claude/worktrees/g2-instruction-guard`, its branch the same name; `.venv` and `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads live state; no relay verb. HELD after review: it lands only after the owner's attended test that a hook's `ask` reaches the dialog under the `auto` mode |
| may touch | `plugin/lib/claude_session/{instructionguard,hooks,instructions}.py` (`instructionguard.py` new); `plugin/.claude-plugin/plugin.json`; `plugin/skills/session/SKILL.md`; `RUNBOOK.md`, `README.md`, `design/readme/{source.md,rendered.sha256}`; `NICE_TO_HAVE.md`; `tests/test_g2_guard.py` (new); this packet, committed first |
| verify | the gate queue's `make check`; while building, pytest directly under `.venv` and `.venv-floor`, `scripts/hygiene --require-private --commits main..HEAD`, `scripts/plugin-version-check`, `scripts/recordlint` |
| acceptance | `.venv/bin/python -m pytest -q tests/test_g2_guard.py tests/test_g1_instructions.py tests/test_hooks.py tests/test_doctor.py tests/test_wfd.py tests/test_wfg.py tests/test_n33.py` green, and the same under `.venv-floor` (the first file absent at the pin: red); `scripts/hygiene --require-private --commits main..HEAD` exits 0 |
| budget | the packet first, then the failing tests, then the change, by explicit path. `claude-opus-5-5`, about 90 tool calls |

## 1. What the source says: the code at the pin

- `hooks.pre_tool_use` stamps every call, denies a helper's charter open or close (Bash), denies Workflow and a Fable spawn under a non-Fable session, opens a helper's call file, and asks or denies a spawn in the late zones. It reads no `Edit`, `Write`, `MultiEdit` or `NotebookEdit` target.
- A helper is told from the main thread by the payload's `agent_id`, in every handler.
- No hook tells a headless (`-p`) run from an interactive one. The nearest code is `harness.claude_argv`, the walk up to eight ancestors to the nearest `claude` process's argv, which SessionEnd uses for the effort flag; `harness._BARE_OPTS` lists `-p` and `--print`.
- The PreToolUse timeout is 5 s (`plugin/hooks/hooks.json`); `dispatch` prints `{}` on an exception.

## 2. Rulings: the requirements

- **R1, what is guarded.** `Edit`, `Write`, `MultiEdit` and `NotebookEdit` (`file_path`, `notebook_path`) on: the user's `CLAUDE.md`, `rules/**`, `settings.json`, `hooks/**`, `agents/**`, `plugins/**` (under `CLAUDE_CONFIG_DIR`, else `~/.claude`); a tree folder's `CLAUDE.md` (a folder holding a main checkout: a child with a `.git` directory); at a checkout's top level (the nearest folder above the target holding `.git`, a directory or a worktree's file) `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `.claude/rules/**`, the ledger file, `.claude/settings*.json`. A component `tests`, `testdata` or `fixtures` below the matched root exempts the path. No other tool is read; a Bash line never is. The third and fourth groups of §7.2's table are not guarded.
- **R2, what it answers.** A main thread: `ask`. A helper (`agent_id`), a `-p` run, or a run whose `claude` argv cannot be read: `deny`. The reason is §7.2's text word for word, the path filled in: it names the path as instruction text every session pays for, and the ledger plugin's `instruct` skill as the lane (the test holds the text; the word is the hygiene scan's, so this page does not spell it).
- **R3, fails open, stays cheap.** An exception, or a target that is not a non-empty string: the call passes, and one line goes to `sessions/<sid>/guard.jsonl` (0600, capped at 64 KiB). Each ask and deny is a line there too. A target whose name and path cannot be guarded is decided by string tests alone, with no file read.
- **R4, no knob.** The guard reads no profile, session setting or environment variable but `HOME` and `CLAUDE_CONFIG_DIR` (where the user's folder is) and the state root (where its log goes).
- **R5, the doctor.** One `guard` row, after the `instructions` rows: the guard is on, and the prompts and refusals that the repo's newest session (g1's `newest`) logged.
- **R6, records.** The skill's page, the RUNBOOK and the README name the guard; t1 round two's F1 to F3 with two older observations, and g1's F1 to F4, become rows of `NICE_TO_HAVE.md`.

## 3. Interfaces: the acceptance table

| row | requirement | proved by (`tests/test_g2_guard.py`) |
|---|---|---|
| (a) | each guarded file asks in a main thread, for each of the four tools | `test_r2_main_thread_asks` |
| (b) | the same files are denied in a helper and in a `-p` run, and where the argv is unread | `test_r2_helper_denies`, `test_r2_headless_denies`, `test_r2_unknown_run_denies` |
| (c) | a fixture's ledger file, a `tests/` path, `plugin/skills/x/SKILL.md`, a source file: `{}` | `test_r1_not_guarded_passes` |
| (d) | a worktree's top-level `CLAUDE.md` is guarded, and the tree folder's | `test_r1_worktree_top_level`, `test_r1_tree_folder` |
| (e) | a Bash call is never read | `test_r1_bash_never_read` |
| (f) | an exception lets the call through and logs one line | `test_r3_exception_fails_open`, `test_r3_unresolvable_target` |
| (g) | no knob opens it | `test_r4_no_knob` |
| (h) | the reason is §7.2's, word for word | `test_r2_reason_text` |
| (i) | the doctor's one line, with the counts | `test_r5_doctor_line_*` |

### What changes

`instructionguard.py` holds the matcher, the run's kind and the log. `hooks.pre_tool_use` calls it after the spawn rules and before a helper's call opens, so a refused call opens none. `instructions.rows` gains the `guard` row.

## 4. Findings that name this row: ledger, NICE, forks

- The management repo's entries 6 and 17 bind it. Live `auto`-mode behaviour (F11) is not tested here: the wall starts no `claude`.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`.

## 6. Report

At most 45 lines, the management repo's hand-back: the head sha, the gate's job and result line, the acceptance table at the pin and now, the choices made inside the rulings, the owner's attended test, what was not done.
