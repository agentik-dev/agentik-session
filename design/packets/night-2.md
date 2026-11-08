# Packet night-2: `agentik session night`, the land step, the stops and the morning report

| item | value |
|---|---|
| from | agentik-hq HANDOFF 22, build 6; hq `design/07-night-loop.md` §2, §8 item 2, §9 risk 4; hq entries 5, 6; relay entries 13, 15; the Mac's ledger, entry 22; hq NICE n4 |
| pin | session main `882d136`, plugin 2.0.0-alpha.47; hq `scripts/land`, read only; worktree `.claude/worktrees/night-2`, branch `night-2`, off main |
| wall | this repo only. No push, merge, `--amend`, rebase, network or install; no `make` (the landing runs `make check` through the gate). Never build or run a relay binary; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never write inside `~/.local/state/agent-relay`. No real `claude`: tests use the fake. `.venv` is a symlink to the main checkout's |
| may touch | `plugin/lib/claude_session/night.py`, `plugin/lib/claude_session/cli.py`, `plugin/skills/night/SKILL.md`, `plugin/.claude-plugin/plugin.json`, `tests/test_night.py`, `tests/fixtures/night/gate`, `tests/test_bare_machine.py` (its reader tables), `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `design/packets/night-2.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `.venv/bin/python -m pytest -q tests/test_night.py -k "land or until or max_rows or stop_file or relay_running or report or queue_quoted or column_zero"` passes, ruling 13's thirteen selected (on main: exit 5, 16 deselected); `.venv/bin/python -m pytest -q tests/test_night.py tests/test_readme.py` passes (on main: 16 and 59 passed); `grep -c -F 'gate-unrun' plugin/lib/claude_session/night.py` reads at least `1` (on main: `0`); `test -f plugin/skills/night/SKILL.md` exits 0 (on main: 1); `grep -c -F '## The night loop' README.md` reads `1` (on main: `0`); `grep -c -F '2.0.0-alpha.48' plugin/.claude-plugin/plugin.json` reads `1` (on main: `0`) |
| budget | One Opus builder, 100 turns, 180k context, `claude-opus-5-5`; its charter opens with doclint's five rows; one commit per act, this packet first |
| verify | `make check` |

Read first, by sections: hq design/07 §2; `gate.py` `wait_line`, `spawn_serve`; `cli.py` `cmd_gate`; night-1's charter, its Handover.

## 1. What the source says

hq design/07 §8 item 2, on night-1 as landed; a row may end `landed <sha>`.

## 2. Rulings

0. This packet, committed first.
1. **Effects, flags.** `Fx` gains `ps` (`ps -axo command=`) and `gate`, the argv `<this interpreter> -I <the runner> gate`, as `spawn_serve`'s, never PATH. `run()` and `cli.py` take `--until`, `--max-rows N` (positive), `--land PATH`.
2. **Refusals before the night's folder** (exit 2): a `ps` line holding the words `agentik relay run` or `agentik-relay run` (a path before the latter allowed), `relay-running: <the line, 120 chars>`; `ps` failing, `ps`; `--land` not an executable file, `land`; `--until` unreadable, `until`. Read once.
3. **The land path.** `--land`, made absolute; else `<repo>/scripts/land` when executable; else none, and a `merge-on-green` row ends `built`, reason `no-land`, logged. Never refused before it runs. No config key (`resolver.py`'s `SECTIONS` is closed); hq passes `--land`.
4. **`--until`.** `HH:MM` is its next local occurrence at or after the start; `YYYY-MM-DDTHH:MM` is absolute. Before each row, now at or past it: stop `until`, so a past one runs nothing. A running row is never killed by it. A limit whose wait would end past it: `limit` line `action: shelve`, the row `limit`, stop `usage-limit` (design/07 §2 Limits).
5. **`--max-rows N`** counts rows spawned, not refused or skipped: with N spawned, the next row to stage stops `max-rows`.
6. **The stop file** `<night>/stop`, read before each row and at each 60 s slice of a limit's wait: stop `owner-stop`.
7. **Stage (design/07 §9 risk 4).** When `<repo>/.venv` exists and the tree has none, stage links it, absolute; `dirty` and the reuse check drop a `?? .venv` line, as `land` does.
8. **Dependencies.** A `depends_on` row runs when every id landed earlier tonight, else `skip gate-failed-dependency`; a `base` naming a row landed tonight is cut from `main`; another stays `refused base`.
9. **The land step.** A `merge-on-green` row judged `built <sha>` with a land path: write `<night>/<id>.merge.txt` (0600): `Merge <id>: <the packet's first heading, less a leading "Packet <id>: ">`, a blank line, `Row <id>, packet <path>, built by <night id> in session <session_id> at <sha>.` Then, in the repo, `<fx.gate> run --wait <repo> -- <land> <repo> <id> <sha> <merge-file>`, stderr to `<night>/<id>.gate.stderr`, no timeout. Its last stdout line is `wait_line`'s; the log's last non-empty line is the verdict. `land <r>: ok <sha>` with exit 0 and the row's sha: `landed <sha>`. `red <step> exit <code>`: `red land-<step>` with the resume line, tree and branch standing; but `remove` or `branch`, whose merge stands: `landed <sha>`, reason `land-<step>`. Anything else (no gate line, a non-zero rc, an unreadable log, another last line, `ok` with exit not 0): `red gate-unrun`, never a pass (relay entry 15). A `gate` line comes first: row, gate_id, gate_line, land_line, exit, rc, log. A SIGTERM lets the job finish.
10. **`report`.** `night report [--night ID]` reads the ledger only (relay entry 13) into markdown: a title, the night and its stop (or `running <row>`); then Landed (row, sha 12, reason), Built (row, sha, reason, worktree), Red (row, reason, resume), Limited (row, `limit_kind`, `resets_at` local, action), Refused and skipped (row, reason); a cost table, each row's `exit` lines' `total_cost_usd` summed, and the total. `no night yet` with none.
11. **n4.** `_bare` and `_joined` skip text inside `"…"` and `'…'` (`''` inside single quotes). Under `rows:` a column-0 `- ` is a row; the block ends at a column-0 line neither `- ` nor a comment.
12. **Skill.** `plugin/skills/night/SKILL.md`, the `session` skill's frontmatter: `name: night`, a description under 200 chars, `allowed-tools` `Bash(agentik-session night *)`; under 40 lines. `/session:night` runs `agentik-session night status`, `/session:night report [--night ID]` the report, never `night run`; a skill, not a command.
13. **Tests.** `tests/fixtures/night/gate`, a fake, a step per call from `$FAKE_GATE_PLAN`, the last repeating (a verdict with `{repo}`, `{sha}` from its argv and an exit, or `no_line` with an rc); it writes the log, prints `queued …`, the gate line, argv to `$FAKE_GATE_LOG`. `Box.go` sets `fx.gate` to it and `fx.ps` to `""`; no night-1 assertion changes. The thirteen: `test_land_ok` (gate line, merge file, argv, a dependent row, the `.venv` link), `test_land_red_step` (`red check exit 2`), `test_land_gate_unrun`, `test_land_branch_only_calls_no_gate`, `test_land_absent_builds` (`no-land`; a bad `--land` exits 2), `test_until_past_runs_nothing` (with `HH:MM`'s next occurrence), `test_until_reset_past_shelves`, `test_max_rows`, `test_stop_file`, `test_relay_running_refused`, `test_report`, `test_queue_quoted_values`, `test_queue_column_zero_items`.
14. **README, records.** In `README.md` and `source.md` alike, by hand: a `night` row in the CLI verbs table, a `night` line under Skills, and `## The night loop` after `## The gate queue`, at most six lines. The source stays under 16,384 bytes: cut the stale `2.0.0-alpha.2` orchestrator paragraph in both, and tighten. A new `json.loads` joins `test_bare_machine.py`'s table. Last commit: plugin 2.0.0-alpha.48, the status line's version and count, `rendered.sha256` re-hashed. Hygiene: no backticked bare `relay <verb>`, no private path.

### The stop

Stop, commit and report if a ruling needs `yamlsubset`, `gate.py` or `admission.py` changed, or today's tests changed.

## 3. Interfaces

`agentik session night run <repo> [--rows a,b] [--until HH:MM] [--max-rows N] [--land PATH]`: exit 0 on stop `queue-spent`, `until`, `max-rows`; 3 on another; 2 on a refusal before the first row. `night status [--json]`: exit 0. `night report [--night ID]`: exit 0, 2 for an unknown night.

## 4. Findings that name this row

hq NICE n4 (S4): built here, ruling 11. hq NICE n3 (S4): a row's context ceiling is the profile's 180k; not built here. design/07 §9 risk 4: ruling 7.

## 5. Forbidden reads

Transcripts; anything under `~/.local/state` or `~/.claude/projects`; any other repo but hq's `scripts/land`, read only.

## 6. Report

At most eight lines: branch and head; each act's commit; `tests/test_night.py`'s count; the suite's; the charter's choices; anything left over.

## Amendment 1 (the owner's word, 2026-11-07): the name

`night` becomes `unattended`, one execution a run: `plugin/lib/claude_session/unattended.py`; `tests/test_unattended.py`; `tests/fixtures/unattended/*`, `FAKE_UNATTENDED_*` (`FAKE_GATE_*` kept); `plugin/skills/unattended/SKILL.md`, `/session:unattended`; `agentik session unattended`; `<state>/unattended/<date>-<n>/`, id `<date>-<n>`; `--run ID`, `no run yet`, `UnattendedError`; `## The unattended loop`. Every word says run or unattended; stop reasons keep their names. May touch adds the four paths; the acceptance lines read the new names; this file keeps its name.
