# Packet S29: a wait on the usage meter is not WAITING

| item | value |
|---|---|
| from | the observer's check-in 114 (example-mac `history/observer/2026-10-14.md`); `NICE_TO_HAVE.md` "A wait on the meter counts as WAITING and stops the loop" (20de033); example-ops's umbrella charter 2026-10-13-13 (WAITING 3 at 20:48 on `room for 0`; room opened 21:47; idle until the owner's hand) |
| pin | `main` at 20de033 (alpha.14); worktree `.claude/worktrees/s29-meter-wait`, branch `s29-meter-wait` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `agentik session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; never write under `~/.local/state`; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; never write in another repo or its worktrees |
| may touch | `claude_session/rules.py` (`PACE`, `clause`), `claude_session/charter.py` (`warnings` only), `plugin/skills/session/SKILL.md` and `RUNBOOK.md` (their "Priority and pacing" sections), `tests/test_rules.py`, `tests/test_charter.py`, and the README's status line in `README.md` and `design/readme/source.md` with `design/readme/rendered.sha256` re-hashed (`shasum -a 256 design/readme/source.md README.md`) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_rules.py tests/test_charter.py tests/test_readme.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; the act-1 commit's new tests fail on 20de033 |
| verify | `make check`, by the coordinator |
| budget | acts: 1 tests, red; 2 rules and charter; 3 docs and the README count. 40 turns, stop at 32 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

`rules.PACE` item 4 says a Next act waiting on an outside party opens `WAITING <n>: <what>; <how to tell>` and the loop stops at n = `pacing.waiting` (3). Sessions also wrote WAITING for the usage meter's `room for 0`, which is no outside party: it frees itself at a known time (band.json's `resetsAt`) or as the rate falls. A loop so stopped stays idle until the owner restarts it.

## 2. Rulings (decided inside the tool by the observer; reversible)

1. `PACE` gains a fifth item, after the WAITING one: `waiting on the usage meter (room for 0, or a usage limit hit) is not WAITING: the Next act stays the act, the wake is the band's reset or one fallback, whichever is first, and it never counts toward the stop`.
2. `clause()`'s pacing part ends `WAITING {waiting} stops the loop, a meter wait never`. Update `test_s21_clause_bound_at_320_bytes`'s pinned length to the new one; the 320-byte bound and its truncation tests stand.
3. `charter.warnings`: when pacing is on and the Next act opens a well-formed WAITING whose `<what>` names the meter (case-insensitive: `room for`, `meter`, `usage limit`, `five-hour`, `5h`), add one line, at any n: `a wait on the usage meter is not WAITING (session.pacing): keep the act as the Next act and wake at the band's reset`. Exit codes do not change. A WAITING on anything else gets no such line.
4. SKILL.md and RUNBOOK.md each say ruling 1 in one sentence in their "Priority and pacing" section.

## 3. Interfaces

`rules.PACE` (a tuple of texts, `.format(**pacing)`), `rules.clause(session)`, `charter.warnings(raw, session)`; the tests' fixtures `_s21_charter`, `S21_LISTED`, `session(...)`.

## 4. Findings that name this row

The NICE row above. The README's status line counts the suite (`tests/test_readme.py::test_status_line_matches_manifest_and_suite`): raise its count by the tests added, in both files, and re-hash the sidecar.

## 5. Forbidden reads

Transcripts under `~/.claude/projects` (grep only, and none is needed); `~/.local/state` beyond reading.

## 6. Report (one table, at most five bullets, under 600 words)

Acts with commit shas; acceptance output verbatim; the red-before evidence (the act-1 tests failing on 20de033); anything filed outside the packet.
