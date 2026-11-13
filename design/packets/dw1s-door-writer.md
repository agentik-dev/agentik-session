# Packet dw1s: the session tool's install leaves a newer `agentik` door in place

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief dw1s; level S2, a mend found by a reproduction; no owner's words |
| pin | `8a4b593` on main (2.0.0-alpha.93). No version in phase 1; phase 2 takes the `2.0.0-alpha.N` the coordinator names, alone in the last commit under `plugin/`. Worktree `.claude/worktrees/dw1s-door-writer`, branch `dw1s-door-writer`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`, no gate job in phase 1; no `claude`; no test reads live state or writes the live home; no relay verb; `plugin/bin/agentik`, `scripts/agentik` and `plugin/lib/agentik_install.py` (vendored) not edited |
| may touch | `plugin/lib/claude_session/install.py`; `tests/test_dw1_door.py` (new); `RUNBOOK.md`, `plugin/commands/install-cli.md` (and `design/readme/source.md` only if it says otherwise); this packet and the sitting's record |
| verify | phase 1: `tests/test_install.py`, `tests/test_bare_machine.py`, `tests/test_dw1_door.py` under `.venv` and `.venv-floor` by `python -m pytest`; `python3 -m compileall -q plugin/lib/claude_session` |
| acceptance | §3; `tests/test_dw1_door.py` red at the pin, green after, under both venvs |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. Why, and the code at the pin

The `agentik` door is one `sh` file every tool carries and installs at `~/.local/bin/agentik`; it reads `VERSION=0.1.0` today and gains a rule at 0.2.0. The canonical install module (`agentik_install._door`) writes the door forward only. This tool's own `install._locked_install` calls `_write_door` unconditionally, at `install-cli` (and `make install`, which runs it) and again from the SessionStart refresh, so a tool one door behind puts the old door back. This row lands before any 0.2.0 door is installed.

## 2. Rulings (brief dw1s, R1 to R7)

- R1 forward only. `install.py` gains `_door(path, door)`; `_locked_install` calls it where it called `_write_door`. Nothing at `path`: written. A link: left alone. A `VERSION` line, there or in this copy, that does not read as a version: left alone. This copy newer: written. Equal or newer there: stays byte for byte. It returns None, or `the door <path> is a link; left alone`, or `the door <path> has no version to compare (<theirs> there, <ours> here); left alone`.
- R2 this module's own readers: `read_launcher` and `order`; no import of `agentik_install` (the package also installs by `pip`, which packages `claude_session*` alone). A test holds the two `_door`s to one behaviour.
- R3 both routes, the verb and the refresh, reach `_locked_install`: one change, a test for each.
- R4 the line goes first in the result's `pruned`, so `install-cli` prints it under its `installed ...` line; the refresh says nothing; exit 0 in every case.
- R5 nothing else moves: the launcher, the old-name link, the frozen tree (still holding this plugin's own door), the prune and the marker; no verb, flag, setting or doctor check.
- R6 the records say the install writes the door where none or an older one is there.
- R7 phase 1 ends at the commits.

## 3. Acceptance (each a test in a temp HOME, the bare env, a plugin copy; "a 0.2.0 door" is the plugin's door with its `VERSION=` line changed)

| # | line | at the pin |
|---|---|---|
| 1 | `install-cli` over a 0.2.0 door: its bytes unchanged, `VERSION=0.2.0`, exit 0, no line about the door | `VERSION=0.1.0`, equal to the plugin's, exit 0 |
| 2 | the same door, the launcher one version behind, `install.refresh(env)` with `CLAUDE_PLUGIN_ROOT` at the plugin: launcher moves, door stays 0.2.0, None | launcher moves, door `VERSION=0.1.0`, None |
| 3 | no door: written, equal to the plugin's, 0755; a door at `0.0.9`: becomes the plugin's | both hold |
| 4 | a link: still that link, its target's bytes unchanged, the link line, exit 0; a versionless door: bytes unchanged, the "no version" line | link replaced by a 0.1.0 file; versionless door overwritten; no line |
| 5 | one table (none, older, equal with other bytes, newer, no line there, no line here, a link) through `install._door` and `agentik_install._door`: the same file and the same return | `install._door` does not exist |
| 6 | the three files green under both venvs, every test in the first two unchanged | first two: .venv 157 passed; .venv-floor 154 passed, 3 skipped |

## 4. Choices inside the rulings

- (filled at the build)

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.
