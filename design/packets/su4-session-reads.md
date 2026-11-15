# Packet su4-session-reads: three things the suite's status reads from the session tool

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief su4-session-reads (S4) |
| pin | `95da908` on main (2.0.0-alpha.123, rw3-gate-repo's merge). Worktree `.claude/worktrees/su4-session-reads`, branch `su4-session-reads`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live gate, state or home, or starts the loop outside a test's stub; no relay verb; no `make stamp` (the landing's) |
| may touch | `plugin/lib/claude_session/gate.py` (`status`, `status_lines`), `unattended.py` (`run`, `status`), `hooks.py` (a sittings read beside `state`), `cli.py` (`cmd_status`, the `status` parser), `plug.py` (`SCHEMAS`, `describe`), `plugin/skills/session/SKILL.md` and `plugin/commands/status.md` (their `status` and `gate status` words), `tests/test_su4_session_reads.py` (new), `tests/test_ak5_plug.py` (the describe test's two `reads` lines, R4), `tests/test_u3.py` (one line: the `start` line is not a row's, R2), `NICE_TO_HAVE.md`, this packet, `history/sittings/2026-11-14-7-su4-session-reads.md` |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3's table; `.venv/bin/python -m pytest -q tests/test_su4_session_reads.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `95da908`)

The suite's `agentik status` reads each tool's own JSON. Three things the session tool knows are in none of its reads: who queued a gate job and when; the unattended loop's pid; and the meter of any sitting but the caller's. This row prints them. It changes nothing that runs, and no line of text a person reads today changes except R5's.

At the pin, measured under a temp home and state root: a `gate status --json` running item holds `id, repo, label, since, seconds`, a queued one `id, repo, position, lock, label, key, wait`; the entry holds `caller` and `queued` (`ENTRY_KEYS`) and neither is printed. `unattended status --json` holds `run, dir, rows, running, stop` (`null` with no run); the ledger's kinds are `accept, baseline, continue, exit, gate, limit, row, spawn, stop`. `status --all --json` is argparse's `unrecognized arguments: --all`, exit 2. `describe --json` names the reads `config, doctor, meter, gate, unattended`. `MORE_REPO` writes its path unquoted.

## 2. Rulings

- R1, the gate. In `gate status --json`, with and without `--repo`, each item of `running` and of `queued` gains `caller` and `queued`, the entry's own values, null where the entry holds none. No other key moves and the text form is the pin's bytes.
- R2, the unattended run. `unattended.run` writes one line to the run's ledger at its start, holding its own pid. Choose a `kind` that every reader of the ledger at the pin passes over, and show in the record, reader by reader, that it does. `unattended status --json` gains `pid`: that number, null for a run whose ledger has no such line. The read makes no claim that the process lives. The text form is the pin's bytes.
- R3, the sittings. `agentik session status --all [--json]`: one row for each session whose `activity.json` under the state root holds an `at` within the last 1,800 seconds, newest first. A row holds `session_id`, `zone` (as `status` computes it for that id), `pct_context`, `pct_turns`, `profile` and `at`; a value its files do not give is null, and a folder whose files are missing or are not JSON objects is passed over. The JSON is `{"schema": "agentik.session.sittings/1", "ok": true, "sittings": [...]}`. The text is one line a row. A read: exit 0 whatever it finds, nothing written, no process list read. It reads at most one small file of a folder before it knows the folder is open, and a test holds 2,000 folders under one second.
- R4, describe. `describe`'s `reads` gains `{"kind": "status", "name": "sittings", "argv": ["status", "--all", "--json"]}`; whatever test pins the describe moves by that item alone.
- R5, the lead. `MORE_REPO` quotes its path (`shlex.quote`), so the line pastes for a path with a space; one test.
- R6, the records. The docs that list `status`'s flags and the JSON reads gain the new ones; `make stamp` is the landing's. NICE rows for what is seen and not built.

## 3. Interfaces, choices and acceptance

- `gate.status`: each `running` and `queued` item ends with `caller`, `queued`. `unattended.START = "start"`, the line `{"ts", "kind": "start", "pid"}` written by `run` once its folder exists; `unattended.status` ends with `pid`. `hooks.sittings(env, now) -> list`, `hooks.sittings_lines(rows) -> list`, `hooks.OPEN_S = 1800`, `hooks.SMALL = 65536`; `plug.SCHEMAS["sittings"]`. `cli`'s `status` takes `--all`, exclusive with `--transcript`.

Choices inside the rulings:
- R2: the kind is `start`, which no reader at the pin names (`status` reads `row, spawn, stop`; `report` `row, limit, spawn, exit, stop`; `deliver.hold` reads `status`). `pid` is the first `start` line's, an int alone, else null.
- R3: `activity.json` decides whether a folder is open: missing, over `SMALL` bytes, not an object or with no numeric `at` (a bool is none), the folder is passed over; an `at` past now counts as open. `meter.json` and `resolved.json` are read only for an open folder; one missing or not an object gives null values. `zone` is `hooks.state(id)`'s zone, null where the meter gives no `pct_context` and `pct_turns`. `profile` is `resolved.json`'s `session.profile`. A folder name that is not id-shaped is passed over. The text: `<id> <zone> context <c>% turns <t>% profile <p> at <HH:MM>`, `-` for a null; with no row, `no open sitting`.
- R6: no README line (it is rendered and its sha is checked).

Acceptance: all in `tests/test_su4_session_reads.py`, on the per-test temp state root (made-up repos `crate` and `my crate`, sessions `su4-fresh`, `su4-old`, `su4-broken`).

| # | line | at `95da908` |
|---|---|---|
| 1 | a queued and a running job from a caller: `gate status --json` shows `caller` and `queued` on each, equal to the entry's; an entry with neither: both null | red: no key |
| 2 | the text of `gate status` and of `unattended status` for the pin's fixtures is byte for byte the pin's | green |
| 3 | a run started by the loop under the test's state root: its ledger holds the pid line once, `unattended status --json` shows that pid; a ledger of the pin's shape: `pid` null; every other reader's output for that ledger is unchanged | red: no line, no `pid` |
| 4 | three session folders (one fresh, one 31 minutes old, one with a broken `meter.json`): `status --all --json` lists the fresh ones newest first, the broken one's values null; an empty state root: `sittings` is `[]`, exit 0; 2,000 folders under one second | red: exit 2 |
| 5 | `status` without `--all` prints the pin's bytes for the pin's fixtures | green |
| 6 | `describe --json` names the `sittings` read, and running its argv gives the schema of R3 | red |
| 7 | a `--repo` path with a space: the more line holds the quoted path | red: unquoted |
| 8 | the suite under both venvs; `make check` once, last, by the gate queue | green at alpha.123 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names.
