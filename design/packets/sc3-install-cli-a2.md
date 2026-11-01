# Packet sc3, Amendment 2: the refuter's round 1 on 1fb45c0

| item | value |
|---|---|
| from | the refuter's round 1 and hq's rulings. Parent `design/packets/sc3-install-cli.md` |
| pin | 1fb45c0's line, from 678a21a; branch and worktree `sc3-install-cli` |
| wall | as the parent's |
| may touch | as the parent's, with amendment 1's `plugin/bin/agentik-session` and `.hygiene-allow`; and `plugin/lib/claude_session/launch.py`, `resolver.py`, `__init__.py`, `plugin/hooks/run`, this amendment |
| acceptance | §2's tests green; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last |
| budget | one commit; the parent's 120 tool calls or 140k context |

## 1. What the source says: the blockers

- F1, `install.py`: the frozen launcher tested the runner with `-f` only, so an unreadable runner made a hook exit 2, which denies the tool on PreToolUse. Add `-r`, as the plugin's launcher has.
- F2, `install.py` and `plugin/bin/agentik-session`: an `AGENTIK_PYTHON` that passes `-x` and cannot run made a verb exit 1, not 3. `/usr/bin/false` gave a verb 1 and `hook SessionStart` 1 with no stdout. The hook branch's probe runs for verbs too, exit 3.
- F3, `launch.py`: `_ENV_DENY_EXACT` refused `PYTHONPATH` and not `AGENTIK_PYTHON`, which picks the interpreter under every hook.

## 2. Rulings: the S4s on this path, one commit

- F4, `install.py`: the launcher's JSON escape handled only `\` and `"`: control characters go.
- F5, `Makefile` with `install.py`: the dirty guard could not see ignored files, and `_walk` froze them: `--ignored`; `_walk` skips `__pycache__`.
- F6, `prune.py`: `ps` had 60 s on the hook path, SessionStart's own timeout 10 s: the refresh gets a short one, and a timeout keeps all.
- F7, `resolver.py`: the remedy says `install-cli`; so do the comments in `plugin/hooks/run` and `__init__.py`.

## 3. Interfaces: the version

Whatever `plugin-version-check` requires, one bump, last.

## 4. Findings that name this row

F1 to F7 above; no others.

## 5. Forbidden reads

As the parent's.

## 6. Report (at most eight lines)

The head sha; the gate's id and code; a line per F; why gate 242 exited 2.
