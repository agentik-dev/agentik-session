# Packet t1: a bare repo or plugin name found one folder below the code folder

| item | value |
|---|---|
| from | the management sitting's coordinator, 2026-11-11: a repo may sit in a folder under ~/code, and two places build its path from a bare name as if it sat directly there |
| pin | main at `d6188ff` (2.0.0-alpha.73). Version 2.0.0-alpha.76. Worktree `.claude/worktrees/t1-tree-names-2`, its branch the same name, cut from that sha |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads live state; no relay verb |
| may touch | `plugin/lib/claude_session/{land,launch,cli}.py`; `tests/test_land_resolve.py` (new), `tests/test_launch.py`, `tests/test_land.py` (its pinned import list); `plugin/.claude-plugin/plugin.json`, `README.md`, `design/readme/{source.md,rendered.sha256}`; `design/packets/t1-tree-names.md` (this packet, committed first) |
| verify | the landing's own `make check`, queued by the coordinator; the builder runs the files of §3 with pytest directly under `.venv` and `.venv-floor`, `scripts/hygiene` (also with `--commits`) and `scripts/plugin-version-check` |
| acceptance | `.venv/bin/python -m pytest -q tests/test_land_resolve.py tests/test_launch.py tests/test_land.py tests/test_fw4c.py tests/test_readme.py` green; `scripts/hygiene --require-private --commits refs/heads/main..HEAD` exits 0 |
| budget | the packet first, then the change as one commit, by explicit path. `claude-opus-5-5` |

## 1. What the source says: the code at the pin

- `land.resolve_repo` makes a bare name into `~/code` joined with the name; `gate land` then fails on a repo that sits one folder lower. The module docstring and the `gate land` help say the same.
- `launch.resolve_plugin` looks each name and alias up directly in each `PLUGIN_SEARCH` root (`~/code`, then `~/.claude/plugins`), names first and roots inside, so an old name never beats a new one in a later root.

This packet was cut after the build: the change outgrew the small-change rule (entry 17, under 50 changed lines of code) during its review. One review round found three bugs, which rows (c), (d) and (e) below answer.

## 2. Rulings: the requirements

- **R1.** A directory matches a bare repo name only when it is a checkout: it holds a `.git` entry, a directory or a file (a linked worktree's). A plain directory, or a plain file left at an old name, never matches; a folder that shares its repo's name is not the repo.
- **R2.** A checkout is counted by its real path, so one reached through a folder or repo symlink is one match.
- **R3.** The cwd never decides; a name with a slash is a path, as at the pin.
- **R4.** The plugin root under `~/.claude` is never read below its top; a plugin folder found directly need not be a checkout, as at the pin.

## 3. Interfaces: the acceptance table

| row | requirement | proved by |
|---|---|---|
| (a) | `resolve_repo`: a name with a slash is a path; a bare name is the checkout of that name directly in the code folder, else the one checkout a folder below; a directory without a `.git` entry never matches | `tests/test_land_resolve.py`: `test_a_directory_at_code_name_wins`, `test_one_level_down`, `test_a_plain_file_at_the_old_name_is_no_match`, `test_a_folder_named_like_its_repo_yields_the_inner_checkout`, `test_a_plain_directory_at_the_direct_path_yields_the_checkout_below`, `test_a_name_with_a_slash_stays_a_path` |
| (b) | none or more than one is a Red at "repo" whose note says what was looked for and lists the matches; `gate land` prints `land <name>: red repo exit 1` and queues nothing | `test_none_is_red_and_names_what_was_looked_for`, `test_two_are_red_and_name_each`, `test_more_than_one_says_so`, `test_the_queue_form_reads_two_as_a_red_repo_line`, `test_the_in_job_form_reads_none_as_a_red_repo_line`; nothing queues because the name resolves before `gate.enqueue`, which no new test asserts (`tests/test_fw4c.py` t6 asserts the empty queue for a missing path) |
| (c) | an empty name, `.` and `..` are a Red before any lookup | `test_an_empty_name_dot_and_dot_dot_are_red` |
| (d) | one repo reached by two paths counts once, in both resolvers | `test_a_folder_symlink_reaches_one_checkout_once`, `test_a_repo_symlink_reaches_one_checkout_once`; `tests/test_launch.py`: `test_tree_one_checkout_by_two_paths_counts_once` |
| (e) | `resolve_plugin`: every name and alias directly in every root in the pin's order first, and only then one folder below the code folder, where a match must be a checkout; two is a `LaunchError` naming both | `tests/test_launch.py`: `test_tree_a_direct_alias_beats_a_short_name_below`, `test_tree_any_direct_name_beats_every_name_below`, `test_tree_an_alias_below_when_nothing_is_direct`, `test_tree_one_level_down`, `test_tree_a_plain_file_at_the_old_name_is_no_match`, `test_tree_none_is_none_and_the_plugins_root_is_not_read_deeper`, `test_tree_more_than_one_is_an_error_naming_each`, `test_tree_the_error_reaches_build`, `test_tree_a_name_with_a_slash_stays_a_path` |
| (f) | nothing changes for a repo that sits directly in the code folder | `tests/test_land.py`: `test_a_a_bare_name_is_a_repo_under_home_code`, `test_obs_a_bare_name_never_resolves_in_the_cwd`, `test_obs_a_name_with_a_slash_is_a_path`; `tests/test_launch.py`: `test_plugins_resolve_to_plugin_dir`, `test_c13_a_new_name_in_any_folder_beats_an_old_name_in_an_earlier_one`, `test_tree_a_directory_at_code_name_wins` |

### What changes

`land.py` gains `is_checkout` and the new `resolve_repo`; `main` names the repo from its argument before resolving, so a Red at "repo" still prints the name. `cli.py`'s queue form catches that Red before it queues. `launch.py` keeps the pin's direct loop whole and adds the lookup below after it. `test_land_resolve.py` is a file of its own because `tests/test_fw4c.py` t16 pins `test_land.py`'s ported count; `test_land.py` changes only its pinned stdlib import list, which gains `glob`.

## 4. Findings that name this row: ledger, NICE, forks

- The management repo's entries 6 (the plugin repos' build conventions) and 17 (a small change takes no packet; this one passed 50 changed lines of code, so it takes this packet) bind it.
- Settled in the build: an ambiguous plugin name raises the module's `LaunchError`, which both callers of `launch.build` already catch, rather than picking one silently.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`.

## 6. Report

At most ten lines: the head sha; the test line under each python; the range scan and the version check; anything not done.
