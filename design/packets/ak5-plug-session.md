# Packet ak5: session answers `describe`, and every setting names the file and line that set it

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief ak5 and the plug's contract shared by rows ak5 to ak9; the owner: "Make plugin configuration discoverable and drill down." |
| pin | `b92e4e0` on main (2.0.0-alpha.103). Worktree `.claude/worktrees/ak5-plug-session`, branch `ak5-plug-session`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state; no relay verb; `resolver.py`, `yamlsubset.py`, `sessionconfig.py` read, never edited |
| may touch | `plugin/lib/claude_session/plug.py` (new); `cli.py` (the `describe` parser, `cmd_describe`, three status prints); `doctor.py` (`Check`, `Report.as_dict`, two remedies); `tests/test_ak5_plug.py` (new), `tests/test_doctor.py`, `tests/test_cli.py` where they pin a changed key; `NICE_TO_HAVE.md`; this packet and the sitting's record. Phase 2: `plugin/.claude-plugin/plugin.json`, `README.md`, `design/readme/` |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_ak5_plug.py tests/test_doctor.py tests/test_cli.py tests/test_resolver.py tests/test_bare_machine.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`, high; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `describe` is no verb: argparse's `invalid choice: 'describe'`, exit 2.
- `doctor --json` prints `{ok, checks: [{name, ok, detail}]}`, `ok` "no check failed"; 19 checks in a new HOME, `ok` false, exit 2.
- `status --json` with no meter: one line on stderr, exit 2; `unattended status --json` prints `null`.
- `resolve` (resolver.py) applies, lowest first: the shipped `defaults:`, the user's `defaults:`, the shipped profile's body, the user's body of it (then its top-level `tiers:`), the repo's `session:` and `tiers:`, `config.local.yaml`, a launch profile's body again, the session overlay. `_window_ceilings` orders the ceilings apart (the role's key above the shipped defaults, then the user's and the project's layers); `gate_config` reads the user file's top-level `gate:` alone.

## 2. Rulings (brief ak5)

- R1: `config`, `profile`, `set`, `rules`, `budget` print as at the pin; resolution unchanged; the human `doctor` text and exit unchanged.
- R2: `plug.py` holds the reads; `cli.py` gains the `describe` parser (`--json`, up to two words), `cmd_describe`, and the status prints' two keys.
- R3: `describe --json`: `needs` `claude`, `git` (programs) and each of `doctor.SIBLINGS` (optional plugins); `verbs` every first-level verb but `hook`, help's order and line, `top` false; `reads` `config`, `doctor`, then status reads `meter`, `gate`, `unattended`.
- R4: layers `default`, `user-defaults`, `profile`, `user`, `repo`, `local`, `launch`, `session`; `travels` true for the two user layers alone.
- R5: one setting a leaf of the resolved `session` section a layer can set (less `description`, `subagents`, `ceilings_1m`, `tiers`), then `tiers.<role>.{model,effort}`, then `gate.*`. `value` is `resolve`'s (and `tiers.effective` in a named session); `default` the shipped `defaults:` with the `frontier` body over it; `source` and `values` from a walk of the layers with the line each stands on (null where none can be found, never a wrong one).
- R6: `change`: `profile` a `launch`; `posture` a `command`, live; `tiers.<role>.model` `set tier.<role> VALUE --save`; the rest an `edit` of the layer in force's file when a person edits it, else the user's file.
- R7: a `ResolveError` is the envelope's error, exit 2, `bad_file` when it names a file, else `unresolved`; `resolve`'s unknown keys are `warnings` with file and line; an unlisted key reads `settings: []`.
- R8: `doctor --json` gains `schema`, `ok` true (the read ran), `tool`, `failed`, `warned`, each check's `status` and `remedy`; two remedies (`/session:install-cli`, `claude plugin update <id>`), no new wording. `status --json`, `gate status --json` and `unattended status --json` (when an object) open with `schema` and `ok`.
- R9: one table of summaries in `plug.py`, under 100 characters each.

## 3. Interfaces

The envelope: every answer opens `{"schema": "agentik.<read>/1", "ok": true, "tool": "session", ...}`; a read that cannot run prints `{"schema", "ok": false, "tool", "error": {"code", "message", "remedy"}}` on stdout and exits 2. One JSON object and a newline, no escape byte, nothing written outside `$XDG_CACHE_HOME/agentik/`.

- `describe --json` (`agentik.describe/1`): `tool`, `version`, `summary` (under 80), `repo`, `plugin`, `needs` `[{name, kind, why, optional}]`, `verbs` `[{name, summary, top}]`, `reads` `[{kind, name, argv}]`. `describe` with no `--json`, or an unknown word: exit 2.
- `describe config --json [KEY]` (`agentik.config/1`): `layers` `[{name, path, present, travels}]`; `settings` `[{key, value, default, type, choices, summary, source: {layer, path, line}, change: {kind, command, path, block, note}, live, values: [{layer, value, path?, line?}]}]`; `warnings` `[{key, reason, value, path, line}]`. With KEY: that one setting or `[]`, exit 0.
- `doctor --json` (`agentik.doctor/1`): `failed`, `warned`, `checks` `[{name, ok, status, detail, remedy}]`, `status` one of `ok`, `note`, `warn`, `fail`; the exit stays the tool's.
- Status reads: `agentik.session.meter/1`, `agentik.session.gate/1`, `agentik.session.unattended/1`, each object's other keys as they were.

Acceptance (`S` the worktree's `plugin/bin/agentik-session`, a temp HOME with its `XDG_*` under it, a temp cwd, no `CLAUDE_*` but those a line names). At the pin, lines 1 to 9 exit 2 (`invalid choice: 'describe'`).

1. `S describe --json`: exit 0, every key, five reads, `top` false, no ESC, under 1 s; `S describe`, `S describe nosuch --json`: exit 2.
2. `S describe config --json`, nothing in HOME: every key; `effort` `high` from `profile` at the shipped file's line 86, `values` `default`, `profile`; no `source.path` under HOME; nothing changed.
3. A repo file, `  effort: medium` at line 3: `value` `medium`, `source` `repo` line 3, `change` an `edit` of that file, block `session:\n  effort: medium`, `live` false. With none: the user's file.
4. A user file, `effort: low` under `profiles:`/`frontier:`, `max` under `defaults:`: `low` from `user`; `values` `default`, `user-defaults`, `profile`, `user`.
5. A user `tiers:` with `build: {model: sonnet}`: `tiers.build.model` `sonnet` from `user`; `change.command` `agentik session set tier.build VALUE --save`.
6. A repo `ceilings: {context: 150000, turns: 300}`: `ceilings.context` 150000 at that line; a user `gate:` `wall: 900`: `gate.wall` 900 from `user`.
7. A session overlay `{"posture": "deny"}`: `deny` from `session`, line null; `change.command` `agentik session set posture VALUE`, `live` true.
8. In process, four fixtures (empty, lines 3 to 6, `CLAUDE_SESSION_PROFILE=scratch`): every `value` is `resolve`'s (`gate_config`'s).
9. `nosuch`: `[]`, exit 0; `efort` in a repo file: one `unknown` warning with its line; a tab in a user file: exit 2, `bad_file`, the file named.
10. `S config list`, `S profile`, `S profile frontier`, `S rules`: byte for byte the pin's (by hand).
11. `S doctor --json`: `schema`, `ok` true, `tool`, `failed`, `warned`; `resolved` and `meter` `note`; a launcher with its tree gone `fail`, remedy `/session:install-cli`; the text and exit the pin's.
12. A meter: `status --json` opens `schema`, `ok`; none: the pin's stderr line, exit 2. The gate's status object the same; unattended `null` with no run.
13. After lines 1 to 9 the temp HOME outside `$XDG_CACHE_HOME/agentik/` is as it was.
14. By hand: the suite's `config session.effort --json` reads this tool (`ok` true, a line, `edit`).
15. The verify row's pytest line, under both venvs.

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made (each summary written, each key's `live`), what was not done.
