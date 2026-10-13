# Packet S17: the budget's words say respawn, never compact

| item | value |
|---|---|
| from | the portfolio ledger's entry 17 (example-ops `DECISIONS.md`, amended 2026-09-29): "At 80% of either, the sitting brings its charter current, lands the act in flight and exits; it respawns and never compacts". The observation below. The builder reads THIS packet and the files it names; nothing outside this repo |
| pin | `main` at 9f23146 plus this packet's own commit; branch and worktree `s17-exit-rule-respawns`, off main |
| wall | this repo only. No push, no `--amend`, no rebase, no device, no network. Never run `relay` in any form, and never build or run a relay binary |
| may touch | `claude_session/hooks.py` (`EXIT_RULE` only), `claude_session/profiles.yaml` (the two orchestrator `description:` lines only), `plugin/skills/session/SKILL.md` (the `EXIT:` bullet only), `design/overhaul-r1.md` (the one sentence quoted in §1), `tests/test_hook_meter.py`, `history/sittings/*.md`. Nothing else |
| acceptance | `.venv/bin/python -m pytest tests/test_hook_meter.py -q -k s17 2>&1 \| tail -1` reads `2 passed` (with any deselected count); `grep -ci 'compact at most once\|compacts in place' claude_session/hooks.py claude_session/profiles.yaml plugin/skills/session/SKILL.md \| grep -vc ':0$'` reads 0 |
| verify | `make check` |
| budget | 40 turns, 60k context; one commit; the charter names doclint's five rows (goal, budget, pin, window, agents) at open; never push, amend or rebase |

## 1. What the source says

Entry 17 (above). What the plugin says:

- `claude_session/hooks.py:49-50`: `EXIT_RULE = ("EXIT: land the act in flight at a checkpoint, then exit; " "respawn by default, compact at most once")`, printed on every tool at or past 100%.
- `claude_session/profiles.yaml:99` and `:109`, the `orchestrator` and `orchestrator-opus` descriptions: "A continuous loop; the first checkpoint compacts in place, the second respawns."
- `plugin/skills/session/SKILL.md:76-77`: "land the act in flight at a checkpoint, then exit; respawn by default, compact at most once."
- `design/overhaul-r1.md:72`: "(\"land the act in flight at a checkpoint, then exit; respawn by default, compact at most once\")".

The owner ruled on 2026-09-29 that a sitting restarts rather than compacts, since a restart reads its brief fresh and a compaction needs the owner's hand. The plugin's lines still tell a sitting it may compact once.

## 2. Rulings (decided inside the design)

1. `EXIT_RULE` becomes `"EXIT: land the act in flight at a checkpoint, then exit; respawn, never compact"`. It stays within the hook's 400-byte stdout cap (`MAX_OUT`).
2. Both orchestrator descriptions end "A continuous loop; at the checkpoint it brings its charter current and respawns." Nothing else in `profiles.yaml` changes.
3. SKILL.md's `EXIT:` bullet and `overhaul-r1.md:72` quote the new rule verbatim. The design record gains no other change. `README.md` is rendered from `design/readme/source.md`, which says nothing about compaction; leave both alone.
4. Two tests in `tests/test_hook_meter.py`, whose names hold `s17`. `test_s17_exit_rule_never_compacts` puts a session at 100%, reads the hook's context, and asserts that `never compact` is present and `at most once` is absent. `test_s17_profiles_never_compact` loads `profiles.yaml` and asserts that no profile's description holds `compacts in place` or `compact at most once`. Both are red on `main`.
5. Fix round (observer, 2026-09-30): rule 4 first forbade the word `compact`, which rule 1's own text holds, so the tests forbid the old phrases instead. The README's test count (`design/readme/source.md:157`) goes from 584 to 586 through `make readme`, which widens may-touch for this fix only.

## 3. Interfaces

No signature changes. `hooks.EXIT_RULE` keeps its name and stays a module constant, and the existing meter tests keep reading it.

## 4. Findings that name this row

`claude_session/hooks.py:49-50` (`EXIT_RULE`) and `:272-276` (where it is printed); `claude_session/profiles.yaml:99`, `:109`; `plugin/skills/session/SKILL.md:76-77`; `design/overhaul-r1.md:72`; `tests/test_hook_meter.py:82`, `:88` (the existing EXIT assertions).

## 5. Forbidden reads

Other repos; the account's `~/.local/state`, its claude install, its user-level CLAUDE.md, git config, ssh config, transcripts; packets but this; worktrees but yours.

## 6. Report

Capped. The acceptance lines, each with its exit and last line. The red run of the two tests on `main`. Last line: branch, head sha.
