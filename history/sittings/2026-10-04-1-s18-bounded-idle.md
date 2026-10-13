# Sitting 2026-10-04-1: claude-code-session, packet S18 (bounded's idle confirm and the guardian's -B)

| item | value |
|---|---|
| goal | `scripts/bounded` holds `--load N` only when the CPU's idle share confirms it (the relay's AR48 rule, ported whole around ADV10 and ADV11), its guardian runs `python -B`, and it becomes the canonical `bounded`; six `s18` tests red where expected on main, green after; conventions §1 and §5 name it within 9,216 bytes; `make check` 0 |
| budget | 70 turns, 150k context (the packet); land the act in flight at 80%; one commit per act; never push, amend, rebase, a device, the network, or relay in any form |
| pin | main 6166e8b plus the packet (a4a9ede); branch and worktree `s18-bounded-idle` |
| window | 200k |
| agents | 0 (a builder spawned by the orchestrator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: seven s18 tests in tests/test_bounded.py; on the unchanged file 5 failed, 2 passed: red are high idle, low idle, two polls, the float floor and the guardian's `-B`; green are the two controls (a fake load with no share, an unreadable share), which state today's rule
- [x] act 2: the relay's idle rule whole (docstring, envs, parsers, `kill_reader` in the TERM path) and the guardian's `-B`; its diff to the relay copy is ADV11 plus `-B` only; `-k s18` 7 passed; test_bounded.py 21 passed; the real `top` read here gives 88.1
- [x] act 3: conventions §1 lists `scripts/bounded` beside `scripts/hygiene`; §5's sentence names the idle confirm; wording trims in §3, §4, §6 to §9 keep it at 9,214 bytes; NICE_TO_HAVE gains the README line (ruling 5); acceptance: `7 passed, 14 deselected`, 3, 1, 3
- [x] act 4: `make check` once on the committed tree (ffd86fe): exit 0 in 44 s, 586 passed, `readme: fresh`, no tree note

## Handover
1. Decided (a reversible choice): tests/test_readme.py holds the suite at the README's `586`, and ruling 5 bars a render, so `test_usage_is_1` (6 cases) and `test_bounded_refuses_nonfinite` (3) are folded into one test each (-7), as `test_sigterm_without_wall_exits_143` was, and S18 adds seven tests (+7), the seventh the unreadable-share rule.
2. decide, owner: the orchestrator; consumer: the merge and the row that copies `bounded` to the other plugins. Conventions §6 pins `scripts/bounded` at sha256 `b3c5f7fe…` (main's); this branch's file is `4fdfdc1d…`. §6 is outside may-touch, so it is not changed here; update that one sha at merge.
3. ADV11 and the idle rule did not conflict: the read runs before the guardian exists, `top` stays in bounded's group, and a TERM runs `kill_reader` before ADV11's cut.

- exit taken: goal met; four commits on `s18-bounded-idle` (1e1c07f, 70744ed, ffd86fe, this one), not pushed; `make check` 0

## Next act
The orchestrator reviews and merges `s18-bounded-idle`, and updates §6's `scripts/bounded` sha (handover 2).
