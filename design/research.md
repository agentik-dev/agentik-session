# Research: the four repos as they stand, and the documented facts (2026-09-22)

Two Opus legs, one sitting (2026-09-22-1). Leg 1 scanned git-tracked files of the four repos with `git grep -c -I -E -i`; counts only, never content. Leg 2 read the Claude Code docs (`code.claude.com/docs/en/<slug>`, binary 2.1.278 local) and the local `--help`. Two of leg 2's rows were corrected by the orchestrator on disk (marked *).

## 1. Public hygiene, counts as lines/files

| repo | files | bytes | home path | LAN | domains | private repos | names | siblings named (example-app, respeak, decisions, session, agents) |
|---|---|---|---|---|---|---|---|---|
| claude-code-session | 43 | 289 K | 1/1 | 0 | 0 | 0 | 2/2 | 3/2, 9/6, 0, self 14/8, 3/2 |
| claude-code-decisions | 70 | 851 K | 77/25 | 6/3 | 21/3 | 369/39 | 19/14 | 520/38, 95/18, self 9/7, 1/1, 8/6 |
| claude-code-respeak | 78 | 817 K | 0 | 0 | 1/1 | 0 | 12/6 | 0, self 1103/66, 0, 0, 0 |
| example-app | 1,567 | 25.2 M | 55/31 | 508/125 | 365/68 | 486/162 | 2506/880 * | self 10742/1218, 12/8, 0, 0, 0 |

Readings. **session** is near clean: the two name lines are the author fields (LICENSE, pyproject), allowlisted by design; the sibling references (respeak 9 lines, example-app 3, agents 3) leave with the README rewrite. **decisions** carries its ledger copy and research (`reference/`, `research/`): 77 home-path lines and 520 example-app lines sit there, outside the `plugin/` subtree; they must leave the repo before it goes public (a packet, §plan D0). **respeak** is clean but for one domain line and 12 name lines in 6 files. **example-app** *: 818 of the 880 name files are its own module path `github.com/owner/example-app` (the public handle, allowed); the real load is the LAN (508 lines, 125 files), the domains (365/68), the private repo names (486/162) and the example-ops terms (the NAS's model, example-ops, its API and admin-shell names, and `NAS`: 1,755 lines, 426 files, 12.7 MB of matching files, half the repo by bytes; the two largest are 973 KB production bundles under `testdata/`). Sized in overhaul-r1 §6.

## 2. Plugin layout as it stands

- **session**: no `.claude-plugin/` anywhere (not a plugin); root `SKILL.md`; Makefile help/test/doctor/install/skill/lint/clean; `tests/` 28 files (184 green); `history/sittings/` (this sitting); no design/ before this sitting.
- **decisions**: `plugin/.claude-plugin/plugin.json` (name `decisions` 0.1.0; keys name, version, description, author); root marketplace.json with one plugin, source `./plugin`; `plugin/` otherwise empty (the skill, commands and hook are designed, not built); Makefile check/gates/test; `design/`, `history/sittings/`.
- **respeak**: root `.claude-plugin/plugin.json` (name `respeak` 0.6.0; keys name, displayName, description, version, license, author, homepage, repository, keywords, userConfig); marketplace source `.`; `skills/` 5, `agents/` 1, `hooks/hooks.json`, `scripts/` 17 (one `respeak-check.sh`), `tests/` 11; no Makefile, no design/, no history/sittings/.
- **example-app**: Go, Makefile with check/test/vet/lint/mutate/hooks/verify-spec; no plugin material.

## 3. Documented facts (leg 2; page slug in brackets)

| fact | answer |
|---|---|
| dependencies | `dependencies` in plugin.json or the marketplace entry: names, or `{name, version, marketplace}`; npm semver ranges (`^2.0`, `>=1.4 <2`); auto-installed and enabled with the dependent; a dependency cannot be disabled or uninstalled while an enabled dependent needs it (the error names them); a missing one disables the dependent with `dependency-unsatisfied` [plugin-dependencies] |
| marketplace sources | `"source": "./plugin"` relative to the marketplace root; another repo's subdirectory needs `git-subdir` with `url` and `path` [plugin-marketplaces] |
| hook stdin | every hook: `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `effort`, optional `agent_id`/`agent_type`; no token or context field, read `transcript_path` [hooks] |
| hook output | stdout is context on SessionStart and UserPromptSubmit; `hookSpecificOutput.additionalContext` elsewhere; PreToolUse denies with `permissionDecision: deny` plus reason; Stop blocks with exit 2 (JSON spelling verify-before-use) [hooks] |
| plugin paths | `CLAUDE_PLUGIN_ROOT` is the cache dir, changes on update; `CLAUDE_PLUGIN_DATA` persists across updates; `CLAUDE_PROJECT_DIR` exists; **no way to find another plugin's root or data** [plugins-reference] |
| headless | hooks fire under `claude -p`; `--bare` skips hooks, plugins, skills, CLAUDE.md; hooks fire in subagents, SubagentStart and SubagentStop exist [headless, cli-reference] |
| limits | `--max-turns` and `--max-budget-usd` are print-mode; result subtypes `error_max_turns`, `error_max_budget`, `is_error: true` [cli-reference, agent-sdk] |
| stream-json | `system` init (session_id, model, tools, plugins), `assistant` (with `message.usage.cache_read_input_tokens`, `parent_tool_use_id` marks a subagent's), `user`, `result` (subtype, num_turns, total_cost_usd, usage, session_id, is_error); `--verbose` in every example; `--include-partial-messages` exists [headless] |
| resume | `--resume <id>` keeps the session id; `--fork-session` mints a new one; `--continue` reopens the directory's latest [sessions] |
| transcript * | `~/.claude/projects/<cwd-slug>/<session-id>.jsonl`; the `subagents/` directory is **not documented but exists** here: `<cwd-slug>/<session-id>/subagents/agent-*.jsonl`, 44 on this Mac (burn-report reads it) |
| plugin config | `userConfig` in plugin.json, values in user `settings.json` `pluginConfigs`, exposed as `CLAUDE_PLUGIN_OPTION_<KEY>`; no per-project plugin config convention; `enabledPlugins` in settings [plugins-reference] |
| CLI | `claude plugin` verbs: install, list, enable, disable, update, uninstall, prune, validate, eval, init, marketplace add/list/remove/update [local --help] |
