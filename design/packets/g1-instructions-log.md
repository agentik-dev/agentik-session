# Packet g1: the log of instruction files a session loaded, and the doctor's lines on them

| item | value |
|---|---|
| from | the management sitting's coordinator, 2026-11-11, brief g1; the design is the management repo's design/09 (§1, §3 "How it is checked" and "What the folder binds", §7.2 "The checks" and the table's last row, §7.3's closing paragraph) |
| pin | main at `ad8cf3c` (2.0.0-alpha.76). Version 2.0.0-alpha.78 (the code's commit set alpha.77; the records' commit, which changes the skill's page, sets alpha.78). Worktree `.claude/worktrees/g1-instructions-log`, its branch the same name, cut from that sha; `.venv` and `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads live state; no relay verb; no PreToolUse behaviour (§7.2's guard is packet g2) |
| may touch | `plugin/lib/claude_session/{instructions,hooks,doctor}.py` (`instructions.py` new); `plugin/hooks/{hooks.json,run}`; `plugin/.claude-plugin/plugin.json`; `plugin/skills/session/SKILL.md`; `RUNBOOK.md`, `README.md`, `design/readme/{source.md,rendered.sha256}`; `tests/test_g1_instructions.py` (new) and the pins of the hook set in `tests/{test_doctor,test_precompact,test_mod,test_s49,test_wfg,test_bare_machine}.py`; this packet, committed first |
| verify | the gate queue's `make check`; while building, the files of §3 with pytest directly under `.venv` and `.venv-floor`, `scripts/hygiene --require-private --commits refs/heads/main..HEAD`, `scripts/plugin-version-check` |
| acceptance | `.venv/bin/python -m pytest -q tests/test_g1_instructions.py tests/test_doctor.py tests/test_precompact.py tests/test_mod.py tests/test_s49.py tests/test_wfg.py tests/test_bare_machine.py` green, and the same under `.venv-floor` (the first file absent at the pin: red); `scripts/hygiene --require-private --commits refs/heads/main..HEAD` exits 0 |
| budget | the packet first, then the failing tests, then the change, by explicit path. `claude-opus-5-5` |

## 1. What the source says: the code at the pin

- The plugin registers eleven hook events (`plugin/hooks/hooks.json`), all through one shim, `plugin/hooks/run`; `doctor.HOOK_EVENTS` is the same list, and the doctor's `plugin` row fails when the installed copy lacks one. `InstructionsLoaded` is not among them, and nothing in the plugin records which instruction files a session loaded.
- `harness.claude_md_bytes` (S49) estimates the loaded bytes for the ledger by walking the cwd's ancestors; it does not know what Claude Code loaded.
- `doctor.run` prints one row per check (`ok`, `warn`, `note`, `FAIL`); only a `FAIL` row moves the exit to 2.

### The event, checked

Claude Code's hooks reference (`code.claude.com/docs/en/hooks.md`, fetched 2026-11-11), "InstructionsLoaded": it fires when a `CLAUDE.md` or `.claude/rules/*.md` file is loaded, at session start and for lazy loads; it is asynchronous, cannot block, and its output is discarded. Input, beside the common fields (`session_id`, `transcript_path`, `cwd`, `hook_event_name`): `file_path`, `memory_type` (`User`, `Project`, `Local`, `Managed`), `load_reason` (`session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact`), `globs`, `trigger_file_path`, `parent_file_path`. The installed Claude Code 2.1.322 holds the same schema and builds the payload from the same six names. No live event was seen: no plugin on this Mac registers the event, and the wall starts no `claude`.

## 2. Rulings: the requirements

- **R1, the log.** The `InstructionsLoaded` hook appends one line per event to `sessions/<sid>/instructions.jsonl` (0600) in that session's state directory: `at`, `file_path`, `load_reason`, `memory_type`, `trigger_file_path`, `parent_file_path`, `globs`, `cwd`, `agent_id`. It prints nothing (the shim sends its stdout and stderr to `/dev/null` and exits 0), writes nothing a model reads, and has the plugin's 5 s hook timeout. A payload without an id-shaped `session_id` or a string `file_path` writes nothing; the log stops growing at 256 KiB.
- **R2, the doctor lists what loaded.** Its `instructions` rows, run in a repo: the newest session whose log's first line has a `cwd` at or under this repo's main checkout, then each distinct file it logged with its bytes counted now (`gone` for a file since deleted), then the files' count and sum. No such session: one row saying so.
- **R3, warnings, one row each, never a failure:** `tree-file` (a checkout in the folder that holds the main checkout has a ledger file whose section `### Every session of the tree` is there, and no `CLAUDE.md` of that folder is in the log; only when a log exists); `plugin-descs` (an enabled plugin whose command, skill and agent descriptions sum past 1,024 B); `memory-index` (the project folder's `MEMORY.md` past 8 KiB); `two-places` (the repo's profile sets `effort` or `model` and `~/.claude/settings.json` sets it too, each place named).
- **R4, memory notes.** `memory-notes` rows: each `*.md` of the project folder's `memory/` but `MEMORY.md` written after the newest ledger row of this repo that is not the logged session's nor the running one's, by name and first line. Read only.
- **R5** is not built: the doctor prints bytes and no ceiling.
- **R6, records.** The skill's page, the RUNBOOK and the README say what the doctor's new rows are; version 2.0.0-alpha.78.

## 3. Interfaces: the acceptance table

| row | requirement | proved by (`tests/test_g1_instructions.py`) |
|---|---|---|
| (a) | an event is logged with its path, reason, origin and time; a bad id or no path writes nothing | `test_r1_an_event_is_logged_with_its_path`, `test_r1_a_bad_payload_writes_nothing` |
| (b) | the hook's output is empty, through the dispatcher, the CLI and the shim | `test_r1_the_hook_prints_nothing`, `test_r1_the_shim_swallows_the_event` |
| (c) | the event is registered, with the 5 s timeout | `test_r1_registered_with_the_hook_timeout` |
| (d) | two logged files with their bytes and sum; a deleted one is `gone` | `test_r2_two_files_bytes_and_sum`, `test_r2_a_deleted_file_is_gone` |
| (e) | no log: one row; another repo's session is not this repo's | `test_r2_no_log_one_line`, `test_r2_another_repos_session_is_not_listed` |
| (f) | each warning fires and stays quiet in its pair of cases | `test_r3_tree_file_*`, `test_r3_plugin_descs_*`, `test_r3_memory_index_*`, `test_r3_two_places_*` |
| (g) | R4's list | `test_r4_memory_notes_since_the_previous_session`, `test_r4_no_earlier_session_lists_nothing` |
| (h) | no new row changes the exit code | `test_no_new_row_changes_the_exit` |

### What changes

`instructions.py` holds the log's writer and reader and the doctor's rows; `hooks.py` gains a thin handler; `doctor.run` puts the rows after `launcher` and before the renamed-config rows, so every row of the pin keeps its place. The hook set's pins in six test files gain the twelfth event.

## 4. Findings that name this row: ledger, NICE, forks

- The management repo's entries 6 (build conventions) and 17 bind it. The main checkout is found from `.git` without git; the project folder is the main checkout's path with every character outside `[A-Za-z0-9]` made `-`.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`; the installed Claude Code binary's text was read once, for §1's check of the event.

## 6. Report

At most 45 lines, the management repo's hand-back: the head sha, the gate's job and result line, the acceptance table at the pin and now, the choices made inside the rulings, what was not done.
