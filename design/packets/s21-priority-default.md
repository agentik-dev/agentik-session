# Packet S21: the priority and pacing defaults

| item | value |
|---|---|
| from | the owner's asks of 2026-10-10 (§1); `record design/conventions.md --section '§3'` |
| pin | `s20b` at 01247f9 (S19 to S20b, unmerged); worktree and branch `s21` off it; this packet is on `main` |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, real `claude`, `claude-session run`, `claude plugin`, `make readme` or `make install`; every python `-B` |
| may touch | `claude_session/rules.py` (new), `claude_session/resolver.py`, `claude_session/profiles.yaml`, `claude_session/hooks.py`, `claude_session/charter.py`, `claude_session/cli.py`, `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `design/readme/source.md`, `tests/test_rules.py` (new), `tests/test_resolver.py`, `tests/test_hook_session_start.py`, `tests/test_charter.py`, `tests/test_cli.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `history/sessions/NEXT`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_rules.py tests/test_resolver.py tests/test_hook_session_start.py tests/test_charter.py tests/test_cli.py -q -k s21 2>&1 \| tail -1` reads `43 passed` or more (s20b: no tests ran); `.venv/bin/python -B -m pytest tests/test_hook_session_start.py tests/test_charter.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (s20b: the same) |
| verify | `make check` (ruling 7) |
| budget | acts: 0 charter; 1 tests, red; 2 `rules.py`, resolver, `profiles.yaml`; 3 block, verb, charter; 4 skill, docs, version. 60 turns, stop at 50 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

- Priority, the default texts: S1 "harm: a reproduced bug that can do harm (a wrong write, data loss, a leaked secret, a safety path) or the repo's own gate red on main; it goes first, ahead of the current goal"; S2 "blocks the goal: an unmet acceptance criterion of the current goal, a defect in a new user's first run, or a dependency that holds the goal"; S3 "the build order: the goal's next slice, then the repo's pending list"; S4 "the rest: review notes, polish, refactors, docs; filed in NICE_TO_HAVE.md with its level, taken only when S1 to S3 have nothing ready or on an S3 slice's path; never ahead of S3". Rules: an item gets its level when filed; the Next act is the highest level ready; a signed-off component's finding is work only as a reproduced S1; each Handover lists the open items by level, highest first. A bug ranks by harm and what it blocks, never by how sure or cheap its fix is; with neither it is S4, below S3, however easy. Met in an S3 slice, it is fixed there only on the slice's path, else filed S4 with a one-line repro and the slice goes on. One S4 item a sitting at most, only when S1 to S3 have none ready; a review's notes are S4 unless they show harm (S1) or an unmet criterion (S2).
- Pacing (581 of 614 ScheduleWakeup calls took their own turn; 77 fired): (1) the fallback wakeup rides the message of the act's last tool call, never a turn of its own; (2) while a helper, a Monitor or a background task is pending, its completion is the wake: one fallback of 1800 s or more, never re-armed on a hand-back; (3) an act ready: the minimum delay; (4) waiting on an outside party: the Next act says `WAITING`, a long delay, the loop stopping at the third WAITING with nothing changed.

## 2. Rulings

1. **Where.** Two session keys in `profiles.yaml` `defaults` (frontier inherits, as `respawn`). The SessionStart line carries one 265-byte block (about 247 without it) after `resolved config at <path>`, before the charter reminder (its test pins `endswith`); `claude-session rules` prints both resolved. Not the conventions doc: it binds builds, ships nowhere, holds 9,214 of 9,216 bytes. The skill gains `## Priority and pacing` (the verb, the keys).
2. **Override.** `session.priority: {enabled, levels: {S1, S2, S3, S4}}`, `session.pacing: {enabled, fallback, waiting}`, any layer, by `_merge` (`levels: {S4: ...}` replaces S4 alone); never the names or count (checks read S1 to S4; a merge deletes no key); not by `set`. Unknown keys go to `unknown`, dropped (§3); a bad value is a `ResolveError` naming it, as `respawn`'s: `enabled` a bool, a text one line of 1 to 240 characters, `fallback` and `waiting` ints, 60 and 1 or more.
3. **The block,** exactly: `; priority: S1 harm, S2 blocks the goal, S3 the build order, S4 the rest; the Next act takes the highest ready; pacing: wake in the act's last tool call, a pending helper is the wake (one fallback, 1800s+), WAITING 3 stops the loop; claude-session rules prints both`. Labels: a text to its first colon, at most 24 characters of `[A-Za-z0-9 '.,-]`; one line of at most 320 bytes; an off part prints nothing.
4. **The verb** prints the levels, §1's rules and bug sentences, the pacing four, and: a packet or brief bounds them (a builder files what lies outside it, takes none); WAITING's line is `WAITING <n>: <what>; <how to tell>`, n the wakes in a row with nothing changed, stopping at n = `waiting` (a respawn reads n from the charter). Every shipped profile keeps both on; no hook enforces them (a ScheduleWakeup nudge is filed as S4).
5. **Charter.** No sixth part (D10; doclint's rule is pinned). Priority on: `open` writes `- open by level: none yet` first under Handover. `check` and `close` warn on stderr, exit unchanged, when that line is missing (priority on) or the Next act opens `WAITING` misshapen or at n of `waiting` or more (pacing on): a refusal would fail old charters and a close at 80%. `check` resolves from cwd; a failed resolve warns nothing.
6. **Version** `2.0.0-alpha.5`: the CLI first (`make install`, the block), then the plugin (the skill); an alpha.4 CLI prints no block; no new hook.
7. **Docs.** RUNBOOK §3 (keys, override, off), §4 (`### Priority and pacing`); `source.md` names `rules`, the Handover line, WAITING; `README.md`, its sidecar and Status line (red from S20b) wait for one `make readme` after the merge.

## 3. Interfaces

`rules`: `LEVELS`, `PRIORITY`, `PACING`, `HANDOVER`, `normalize(session, unknown)`, `clause(session)`, `render(session)`, `handover_listed(text)`; `charter.waiting(line) -> int | None` (0: misshapen), `charter.warnings(raw, session)`; `cli.cmd_rules`.

## 4. Findings that name this row

Each `test_s21`, red on s20b: rules (13): `_default` 2, `_clause` 3, `_bound`, `_render` 2, `_ranks_bugs`, `_handover` 3, `_docs` (SKILL.md, RUNBOOK.md); resolver (14): `_one_text`, `_local_wins`, `_not_settable`, `_off` 2, `_unknown` 2, `_bad_value` 7; hook (3): `_block`, `_block_off`, `_bytes`; charter (11): `_open_seeds` 2, `_check_warns` 4, `_close_warns`, `_bad_resolve`, `_waiting` 3; CLI: `_verb` 2.

## 5. Forbidden reads

Other repos; the live state root; transcripts; packets but S20's; worktrees.

## 6. Report

At most 150 words: commits, the red run, the acceptance lines' last lines, notes filed, head sha; `make doclint`, `lint` and `hygiene` exit 0 before each commit.
