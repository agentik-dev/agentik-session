# Sitting 2026-10-13-3: agentik-session, agentik-r1-session (the rename packet)

| item | value |
|---|---|
| goal | packet `design/packets/agentik-r1-session.md`: `agentik-session` + `claude-session` link, `session@agentik`, c1 c4-c8 c11 c13, vendored commons scripts, `renamed` 0 |
| budget | 150 turns, 160k context (caller); ~90 tool calls; stop at 80% |
| pin | worktree `~/.cache/agentik-worktrees/agentik-r1-session`, branch `agentik-r1-session` off main `97cdf39`; agentik-commons main `3d5c0d1` |
| window | 1M (a builder keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 1, vendor + gate: sync (commons 3d5c0d1), `make hygiene` checks `vendored.sha256` first, `validate` drops `.`, marketplace.json gone, test_hygiene is commons' copy
- [x] act 2, paths (c1 c4 c5 c6 c7 c13, ruling 9): `config.pick`, resolver, doctor warn rows, profiles `relay:`, launch, hooks; fixtures moved; suite green but test_readme's count (act 5)
- [ ] act 3, the tool: pyproject, cli/chain names + `--version`, install (ruling 2), alias note (ruling 3), messages
- [ ] act 4, the plugin: commands, skill, `hooks/run`, `session.ts` (c11)
- [ ] act 5, docs: RUNBOOK, readme source + render, test_readme; `.hygiene-allow`; `renamed` 0
- [ ] acceptance + charter close

## Rulings beyond the packet
- R15: `tests/test_hygiene.py` is commons' own suite copied verbatim (30 pass on the vendored copy), since the canonical JSON gained `outside_*` keys and `renamed`, which an exit swap alone cannot meet (ruling 11 amended).
- R16: c4 picks by the repo folder, c5 by the user's `profiles.yaml` file (`~/.claude/agentik/` is shared by name).
- R17: doctor's relay sibling row is named `relay-plugin`, since `relay` is the binaries' row; the c4/c6 warn rows (`config-dir`, `config-key`) come after `measure`.
- R18: a user `profiles.yaml`'s old key is renamed per body before the merge, so it still overrides the shipped `relay`.

## Handover
- (none yet)

## Exit
- open
