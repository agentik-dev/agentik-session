# Sitting 2026-10-10-4: claude-code-session, packet S21 (the priority and pacing defaults)

| item | value |
|---|---|
| goal | `session.priority` and `session.pacing` in `profiles.yaml` defaults, resolved and overridable by any layer; the SessionStart block; `claude-session rules`; the charter's Handover seed and WAITING warnings; skill, RUNBOOK and source.md; version 2.0.0-alpha.5; 43 or more `s21` tests red first, then green |
| budget | 60 turns, stop at 50, 180k context (the packet); one commit per act; never push, amend, rebase, a device, the network, or relay in any form; no real `claude`, no `make check`, no whole suite, no `make readme` (a relay night is live) |
| pin | branch `s21` off `s20b` 01247f9 (S19 to S20b, reviewed, unmerged); the packet read from main b43a445; the refuter's N1 to N8 bind over it |
| window | 200k (a builder on a 1M window keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: 50 `s21` tests (rules 15, resolver 19, hook 3, charter 11, CLI 2); red run on s20b `50 failed`; every case has a positive control that fails on s20b (N5)
- [x] act 2: `rules.py`; the resolver normalizes each layer (N3 null or scalar refused, N4 `<layer>: session.<key>.<field>`) and checks the merge (fallback 60 to 3600, waiting 1 to 9, N1); quoted defaults in `profiles.yaml` (N2). rules+resolver `-k s21`: 33 of 34 (the docs test waits on act 4); test_resolver 51, test_doctor 61 passed
- [x] act 3: the block after `resolved config at <path>`; `claude-session rules`; `open` seeds `- open by level: none yet`; `check` and `close` warn (resolved from cwd, a failed resolve silent). N6: test_charter.py's close expectation (`test_close_appends_one_line`) now reads the seed line above the exit line. `-k s21` 49 of 50; acceptance 2: 23 and 39 passed
- [x] act 4: SKILL `## Priority and pacing`; RUNBOOK §3 (keys, override, off, a quoted example) and §4 `### Priority and pacing`; source.md (`rules`, the Handover line, WAITING); NICE_TO_HAVE's S4 nudge; version 2.0.0-alpha.5 in the four files. `-k s21`: 50 passed; acceptance 2: 62 passed

## Handover
- open by level: S4 the ScheduleWakeup nudge (NICE_TO_HAVE.md, ruling 4)
1. decide, owner: the coordinator (at landing): `make readme` is not run (a relay night is live, N7); README.md, its sidecar and the Status line wait for the observer's render, and test_readme's four cases stay red until then.
2. Logged (N1, reversible): `pacing.fallback` 60 to 3600 and `pacing.waiting` 1 to 9, so four 24-character labels read 319 bytes; consumer: the coordinator's review.
3. N6: `test_close_appends_one_line` (test_charter.py) now expects the seed line above the exit line. N4 widened `rules.normalize` to `(session, unknown, layer)`; `rules.check`, `parts` and `SEED` were added beside the packet's names.
4. decide, owner: the coordinator (at merge): `s21` is off `s20b` 01247f9 and merges after S19, S20a and S20b.
- exit taken: S21 done (acts 0 to 4); stopped before `make readme` and the gate, the coordinator's and the observer's

## Next act
The coordinator: review, merge after S20b, `make check`; the observer: `make readme` at landing, then the install (CLI first).
