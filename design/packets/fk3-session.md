# Packet fk3: the sibling check takes the suite's answer about which plugin stands

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief fk3 (design/25 §5 item 7, item 15's key for a sibling's line; §2 item 5, the two doctors measured) |
| pin | `5890501` on main (2.0.0-alpha.106). Worktree `.claude/worktrees/fk3-session`, branch `fk3-session`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test starts the real `claude` or the real suite or reads the live home; no relay verb |
| may touch | `plugin/lib/claude_session/doctor.py` (`_check_dependency`, `Check`, `Report.as_dict`, `render`, `run`, two new reads); `tests/test_doctor.py`; `tests/test_bare_machine.py`'s `NOT_STATE` (the suite's answer is no state this tool keeps); this packet and the sitting's record. Last: `plugin/.claude-plugin/plugin.json` and what `scripts/stamp` writes |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_doctor.py tests/test_ak5_plug.py tests/test_bare_machine.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_check_dependency` looks up one fixed id, `<name>@agentik` (or the `old` id), in `claude plugin list --json`. A fork installed alone, `<name>@acme-tools`, reads `not installed, optional`; the ledger tool's doctor takes the highest-versioned cache folder of any marketplace and reads it ok. With both installed each doctor names a different one.
- `Check` has no `source`; a sibling's id and version sit in `detail`.

## 2. Rulings (brief fk3)

- R1, the read. Once a run the doctor starts `$HOME/.local/bin/agentik-suite describe sources --json` (the fixed place, never PATH), with its own environment and cwd, under a wall of 5 s. The answer counts when the exit is 0 and stdout is one object, `schema` `agentik.sources/1`, `ok` true. `tools` rows: `tool`; `kind` (`own`, `plugin`, `folder`, `undecided`, `absent`); `plugin` (null for a folder); `root`; `version`; `found`; `declared` (`{path, line}` or null); `seen` (`[{plugin, version, scope, root}]`). `own` means the id is `<name>@agentik`.
- R2, no read. With no launcher, any other answer, or no row for the sibling: `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/installed_plugins.json`, the entries over every id's list whose plugin is named as the sibling, at scope `user` or `managed`. One: it stands. Two or more: a note, `not checked: say which with the suite's sources`. None: `not installed, optional`. The lookup of one fixed id is gone in both roads.
- R3, the line. `absent`: `not installed, optional`. `undecided`: a warn giving the count, remedy `agentik config suite.sources.<name>`. A line naming a plugin not installed, or a folder gone (`found` false): a warn naming the line's `path:line`. Found, an id: `enabled` from the plugin list by that id; not enabled, `installed, disabled, optional`; no list, `optional, not checked`. Found, a folder: `installed`.
- R4, where a fork's name goes. `Check.source`: None, or `{kind, plugin, root, version, declared}`. `own`: today's detail, `source` None. Any other kind: no id, marketplace, folder or version in `detail`; `as_dict` gives `source` beside it; `render` prints the id or folder and the version after the detail. An `undecided` sibling's `seen` ids go the same way.
- R5 (ruled 2026-11-13). Where the plugin list holds a sibling's `old` id, the check is today's, byte for byte (`_pick_id`, `_switch_note`, `_twice_note` for that case alone).
- R6, not this row: `_check_plugin`, `_check_launcher`, `_sibling_absent` (still `relay@agentik` for the git guard).

## 3. Interfaces

- `doctor --json` (`agentik.doctor/1`): each check gains `source`, null or `{kind, plugin, root, version, declared}` (`seen` added for an undecided one). Nothing else moves.
- The text line: `<status> <name> <detail> (from <id or folder> <version>)` when `source` is set.

Acceptance (the fork `<name>@acme-tools`; a stub launcher at `<home>/.local/bin/agentik-suite` prints a canned answer; the `machine` fixture gains an `installed_plugins.json` matching its plugin list, each entry at scope `user`). At the pin lines 1, 2 (undecided), 4 (fork alone, both), 6 and 7 are red: the pin never reads the suite nor the file.

1. The stub: the fork stands alone (`plugin`, 0.12.6, found), the list has it enabled: the sibling's check ok; `render`'s line holds `<name>@acme-tools 0.12.6`; `detail` and `remedy` hold no `acme`; `as_dict` gives `source.plugin`. At the pin: `not installed, optional`.
2. `absent` (a folder left in the cache): `not installed, optional`. `undecided`, two `seen`: a warn, the remedy above, no `acme` in its detail.
3. Line 1's answer, the fork not enabled: `installed, disabled, optional`.
4. No launcher; exit 2; `ok` false, another schema, no JSON; a sleeper past the wall: the file is read. The fork alone at `user`: line 1's result. Both at `user`: the `not checked` note. None: `not installed, optional`.
5. `own`, by the read and by the file: `<name>@agentik 0.7.0 installed`.
6. `test_wrong_marketplace_is_not_the_sibling` turns: a sibling alone from another marketplace stands, its id in no detail.
7. A recorder: the launcher starts once a run; the sleeper: `doctor.run` returns inside the wall plus 1 s.
8. Every test whose plugin list holds an `old` id passes, no assertion changed.
9. The full suite under both venvs; `make check` green.

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made inside the rulings, what a relay fork reads as in `_sibling_absent`.
