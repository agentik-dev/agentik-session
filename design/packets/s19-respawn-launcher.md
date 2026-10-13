# Packet S19: the respawn mark, the hooks' stamps and the chain's ledger lines (respawn-r1, part one)

| item | value |
|---|---|
| from | `record design/respawn-r1.md --section 6,7,10` and `--section 14,15,16`; `NICE_TO_HAVE.md`'s respawn-r1 entries. The builder reads THIS packet and the files it names; nothing outside this repo |
| pin | `main` at 50cbdba plus this packet's own commit; branch and worktree `s19-respawn-launcher`, off main |
| wall | this repo only. No push, `--amend`, rebase or device. Never run `relay` in any form, nor build or run a relay binary. Every python is `python3 -B` or runs with `PYTHONDONTWRITEBYTECODE=1`. No test starts a real `claude`; the one `claude` spend is `make readme`, once, in act 5 |
| may touch | `claude_session/charter.py`, `claude_session/cli.py`, `claude_session/hooks.py`, `claude_session/ledger.py`, `claude_session/resolver.py`, `claude_session/profiles.yaml`, `claude_session/doctor.py`, `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `plugin/hooks/hooks.json`, `plugin/commands/checkpoint.md`, `plugin/skills/session/SKILL.md`, `design/readme/source.md`, `README.md`, `design/readme/rendered.sha256` (these two by `make readme`), `tests/conftest.py`, `tests/test_charter.py`, `tests/test_cli.py`, `tests/test_hooks.py`, `tests/test_ledger.py`, `tests/test_resolver.py`, `tests/test_doctor.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `history/sessions/NEXT`, `.venv` (the link); fix round: `plugin/hooks/run`, `tests/test_hook_meter.py`. Nothing else |
| acceptance | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_charter.py tests/test_cli.py tests/test_hooks.py tests/test_ledger.py tests/test_resolver.py tests/test_doctor.py -q -k s19 2>&1 \| tail -1` reads `62 passed` (any deselected; main: none); `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_readme.py -q 2>&1 \| tail -1` reads `54 passed` (main: the same); `grep -c 'Status: version .v2.0.0-alpha.3.' README.md` reads 1 (main: 0); `shasum -a 256 -c design/readme/rendered.sha256 2>&1 \| grep -c ': OK$'` reads 2 (main: 2) |
| verify | `make check` |
| budget | 70 turns, 180k context; one commit per act; the charter opens with doclint's five rows; never push, amend or rebase |

## 1. What the source says

§5 allows two packets; the whole overruns one sitting:

- **S19:** the mark (§3.2), the stamps and Stop (§3.3), the line kinds, the cap's read and `report --chains` (§3.6), the key (§4), Stop in the doctor, the version, the README. Alone, a sitting marks its close and is told no launcher runs it (today's path).
- **S20:** `chain.py` and `run` (§3.1, §3.3's steps, §3.4, §3.5, §3.7), the scrub in `launch.py`, `--session-id` in `CLAUDE_FLAGS`, the flag layer, RUNBOOK §4 with the start-line guidance (the long-`/loop` note); criteria 1, 2, 5 to 12, 14 to 16, and 13's ledger token.

## 2. Rulings (decided inside the design)

1. **The mark checks first.** `checkpoint --respawn --charter F` runs §3.2's steps 1 to 3 before today's checkpoint, so a refusal (exit 2) writes nothing: no commit, no overlay reset, no marker. Then the checkpoint, the marker, and §3.2's launcher line when `CLAUDE_SESSION_CHAIN` matches `^[A-Za-z0-9._-]{1,64}$`, else its no-launcher line. Either flag without the other exits 2 naming the missing one; an unreadable charter exits 2 naming the path; the id must match `hooks._SID`.
2. **The marker** `sessions/<sid>/respawn.json` is exactly `{session, charter, charter_sha256, written, chain}`: the absolute path, the sha256 of the bytes read, `time.time()`, the chain or null. It and every stamp are written by `store._write_private`.
3. **Stamps** key on the payload's `session_id` only, ignore the posture, and never change a hook's output (a failed write is swallowed); `at` is `time.time()`. PreToolUse stamps `activity.json` `{event, tool, at}` before the spawn gate, which still gates spawns only; UserPromptSubmit stamps it, `tool` null, before its posture check.
4. **Confirmation.** On a main-thread Bash payload whose `tool_input.command` holds `claude-session checkpoint` and `--respawn`, PostToolUse writes `respawn-main.json` `{at, marker_sha256}` when the marker's `written` is at or after `activity.json`'s `at` (none without `activity.json`), before the meter and without `transcript_path`. `/session:checkpoint` makes no tool call, so `checkpoint.md` says the mark goes through Bash.
5. **Stop.** `hooks.stop` writes `turn-ended.json` `{at}` for a payload without `agent_id`; `dispatch` prints nothing for Stop, even when the handler fails, and exits 0. `hooks.json`: Stop (timeout 5) before SessionEnd, and PreToolUse's matcher `*`; `HOOK_EVENTS` and `test_doctor.py` follow.
6. **Helper activity (the P4 note, taken).** A PreToolUse or PostToolUse payload with `agent_id` writes only `helper-activity.json` `{event, tool, at}`; S20's ready condition waits for it to stand `settle` seconds.
7. **Ledger.** `append_chain` writes a restart or stop line with exactly its §3.6 keys (absent ones null) and refuses an unknown kind or key (`LedgerError`, nothing written); `at` is written as `ended` is. `read` returns lines without `kind`. `restarts_in` fails closed: no file is 0, any other read error raises `LedgerError`; the chain's restart line counts when its `at` is in the window or unparsable; a line that is not a JSON object counts when it holds `json.dumps(chain)`. `report --chains` (`--json`, `--since` on `at`) exits 2 on none.
8. **Key.** `respawn: {cap: 12, floor: 600, settle: 60}` goes in `profiles.yaml` `defaults` and `SESSION_KEYS`, layered as `builders`; `_validate` refuses a non-mapping, a stray sub-key, or a negative, non-int or bool value, naming `respawn.<key>`; not `SETTABLE`.
9. **Docs, version.** SKILL.md's EXIT bullet gains §3.2's last paragraph: `claude-session checkpoint --respawn --charter <file>` through Bash, then end the turn. `source.md` names the flags, `--chains`, Stop and PreToolUse on every tool. The version becomes `2.0.0-alpha.3`. `make readme` runs once, after the tests are final; on failure, commit the source; never hand-edit `README.md`.
10. **Tests** hold `s19`, each red on unchanged code (a negative case carries its positive control); ids from `SENTINEL_SIDS`; `CLAUDE_SESSION_CHAIN` joins `INHERITED`. **Acts**, a commit each: 0 charter; 1 tests, red; 2 the mark; 3 hooks, `hooks.json`, doctor; 4 ledger, `--chains`, key; 5 docs, version, `make readme`, acceptance.

## 3. Interfaces

No signature changes. New: `charter.RESPAWN` (§3.2's pattern), `charter.next_act_line(text)` (the Next act's first non-blank line, or None); `hooks.stop`, `hooks.CHAIN_VAR` and the five file names; `ledger.RESTART_KEYS`, `STOP_KEYS`, `append_chain(state, entry)`, `read_chains(state, since=None)`, `restarts_in(state, chain, now, hours=24)`, `chain_table(rows)`.

## 4. Findings that name this row

The 59 cases (62 after the fix round):

- `test_charter.py`: `test_s19_next_act_respawn_spellings` (9: criterion 3's eight Next acts, and a bare `RESPAWN`).
- `test_cli.py`: `test_s19_respawn_needs_its_charter` (1); `test_s19_respawn_writes_the_marker` (3 spellings); `test_s19_respawn_names_the_chain` (1); `test_s19_respawn_refusals_write_nothing` (7: the five, a missing file, `CLAUDE_SESSION_HELPER=1`; one stderr line; the overlay counter kept); `test_s19_respawn_takes_a_charter_check_refuses` (1); `test_s19_respawn_marker_holds_no_next_act_text` (1); `test_s19_report_ignores_chain_lines` (1, plain and `--json`); `test_s19_report_chains` (1); `test_s19_profile_refuses_a_bad_respawn_value` (1, `cap: -1` in `config.yaml`).
- `test_hooks.py`: `test_s19_main_thread_confirms_the_marker` (1); `test_s19_unconfirmed_marks` (3: `agent_id`, no `--respawn`, a stale marker); `test_s19_main_thread_stamps` (3: PreToolUse on `Read`, UserPromptSubmit, Stop; none with `agent_id`); `test_s19_helper_activity_stamp` (1); `test_s19_stamps_ignore_posture` (1); `test_s19_stop_prints_nothing` (3: a payload, bad stdin, a raising handler).
- `test_ledger.py`: `test_s19_chain_lines_have_exactly_their_keys` (2); `test_s19_chain_writer_refuses` (3); `test_s19_read_returns_session_lines_only` (1); `test_s19_restarts_in_counts_the_window` (1, criterion 11's first case); `test_s19_restarts_in_fails_closed` (3: unreadable, a bad line, a bad `at`).
- `test_resolver.py`: `test_s19_respawn_defaults` (1); `test_s19_respawn_layers` (3: user defaults, `config.yaml`, `config.local.yaml`); `test_s19_respawn_refuses_bad_values` (5: `-1`, `"x"`, `1.5`, `true`, a stray sub-key).
- `test_doctor.py`: `test_s19_hooks_register_stop_and_every_tool` (1); `test_s19_doctor_red_without_stop` (1).

## 5. Forbidden reads

Other repos; `~/.local/state/`; `~/.claude/projects/`; `design/respawn-r1.md` beyond `from`; other packets and worktrees.

## 6. Report

At most 200 words: commits by act; act 1's red run; each acceptance line's exit and last line; `make readme`'s exit; anything filed to `NICE_TO_HAVE.md`; last line, branch and head sha. Before each commit run `make doclint`, `make lint` and `make hygiene`; each exits 0.
