# The plan: the packet queue (r1, 2026-09-22)

One packet is one branch, one sitting, one merge decision (the brief). Rows run in order; a row with a dependency waits on that row's green. Budgets are the sitting's ceilings (turns, context); the gate is the packet's acceptance rerun on the branch by the relay, or by hand with the same lines until the relay runs. Model per D5: Opus builds, Fable writes packets and designs. The first four packets are written under `design/packets/`; the rest are written by a packet-writing sitting when their turn nears, never earlier (a packet written against a stale pin is a defect).

| # | packet | repo | model | budget | gate | dependency |
|---|---|---|---|---|---|---|
| 1 | S1 conventions and the hygiene scan land (`scripts/hygiene`, `scripts/doclint`, `make check`, `.hygiene-allow`) | claude-code-session | opus | 80 / 100k | `make check` 0; hygiene 0 hits outside the allowlist | none |
| 2 | S2 retire the fork-and-resume chain and the window sampler (D6) | claude-code-session | opus | 80 / 100k | `make check` 0; no schedulers/, runner, reset; no `fork-session` in the tree | S1 |
| 3 | A1 agent-relay repo birth (git init, Go module, verbs stubbed, `plugin/` skeleton, marketplace, `make check`) | agent-relay (new) | opus | 60 / 80k | `go test ./...`, `make check`, `claude plugin validate plugin/` all 0; no remote; no `push` in Go source | S1 |
| 4 | S3 the session plugin skeleton: `plugin.json` with dependencies, `profiles.yaml`, the YAML subset, the SessionStart resolver and resolved file, `doctor` | claude-code-session | opus | 100 / 120k | `make check` 0; resolved.json byte-stable; doctor names what is missing | S2 |
| 5 | S4 the meter (PostToolUse, UserPromptSubmit) and the ledger (SessionEnd); `status`, `report` (`design/packets/s4-meter.md`) | claude-code-session | opus | 100 / 120k | fixtures at 79/80/100%; meter equals burn-report on one transcript | S3 |
| 6 | D0 decisions: `reference/` and `research/` leave for example-ops (D14) | claude-code-decisions | opus | 40 / 60k | hygiene groups 1 to 4 read 0 | owner rules D14 |
| 7 | D1 decisions: conventions, hygiene, the provider layer in its resolver | claude-code-decisions | opus | 80 / 100k | `make check` 0 | S1, D0 |
| 8 | R1 respeak: conventions (Makefile, design/, history/), hygiene, the provider layer; marketplace name ruled by D11 | claude-code-respeak | opus | 100 / 120k | tests and hygiene 0 | S1 |
| 9 | AR1 agent-relay plugin hooks: deny guards (push, amend, rebase, device), the Stop guard, packet injection at SessionStart; usable in hand-run sittings before the binary (`design/packets/ar1-relay-hooks.md`) | agent-relay | opus | 80 / 100k | stdin-fixture tests per event; `make check` 0 | A1 |
| 10 | A2 agent-relay design r1: state machine, packet and queue schemas, template, ledger, D1 D2 D4 ruled in; writes its own packet queue | agent-relay | fable | 120 / 130k | doclint 0; the queue file validates | A1; owner on D1, D2 |
| 11 | A3 to An: provability (state machine, fakes, invariants, `plan` end to end), then effects (worktrees, gate, spawn and stream, tmux, a push service, report) | agent-relay | opus | per A2 | per A2 | A2 |
| 12 | S5 commands and skill (`/session:*`), the spawn gate, `charter {open,check,close}` (D10) (`design/packets/s5-commands.md`) | claude-code-session | opus | 100 / 120k | `make check` 0; charter-close parity on the sittings in history/ | S4 |
| 13 | `record`, serve sections not files (example-ops packet `context-budget/packets/a2-record-sections.md`, written there, not rewritten; home per D15, recommended claude-code-session: `scripts/record` on PATH, `/session:read`) | the ruled home (D15) | opus | 40 / 80k | the packet's acceptance: the 617 KB seam record's map under one second; `--section` exits 0, 2 and 3 as its §3 says; its test; hygiene 0 | owner rules D15; S1 (hygiene); S3 when the home is the session (the skill needs `plugin/`) |
| 14 | S6, D2, R2, AR2: each README via respeak (`design/readme/source.md`, `make readme`); S6 is `design/packets/s6-readme.md` (50 turns: the render rounds), off `s5-commands`; D2 and R2 are written in their repos by packets-6 and packets-7; AR2 waits on A2 | each | opus | 40 / 60k each | `make check` 0, README fresh, hygiene 0 | S5, R1 (the renderer) |
| 15 | V5 example-app adopts: `scripts/hygiene` in `make check` with its allowlist, the config file (`verify: make check`, `device: never`) | example-app | opus | 60 / 80k | `make check` 0; the scan's counts recorded as the baseline | S3; the owner's word that example-app may be touched |
| 16 | V1 to V4 example-app public-readiness (overhaul-r1 §6): fixtures, addresses, private names, example-ops terms | example-app | opus | 4 to 6 sittings, 100 / 120k each | the scan's counts fall to 0 per group | V5 |
| 17 | the owner pushes, in order: session, decisions, respeak, agent-relay, example-app, each with hygiene green | owner | — | — | `make check` 0 on main | 14, 16 |
| 18 | d-split: `src/decisions.py` (1,321 lines) split into a package by concern, every module under a thousand lines (the owner's ruling C, 2026-09-22); tests unchanged, `--help` and the test count identical; packet not yet written (sitting 2026-09-22-6 exited at its ceiling) | claude-code-decisions | opus | 60 / 100k | `make check` 0; 133 tests; `--help` md5 unchanged | none |
| 19 | S7 conventions amendments (items 23 to 27 of the decisions brief: a packet-authoring §9, the sidecar checked by `shasum -c`, `CLAUDE_CODE_SESSION_ID` only, both scripts' shas, the resolved path), checkpoint's help text (41), RUNBOOK pruned (42), doctor's python check off Apple's python with newer versions from pyenv's offline list (43); optional 21, the row id in the charter file name (`design/packets/s7-conventions-and-doctor.md`); built on branch s7-conventions-and-doctor, 21 included, every acceptance line green, 327 passed (sitting 2026-09-22-11), merged to main at 66c6357 | claude-code-session | opus | 80 / 100k | `make check` 0; the packet's lines; both scripts' shas in conventions §6 | S6 (main 4901b1b) |
| 20 | S8 conventions: the four rulings of 2026-09-23 05:53 (4), settled inside conventions (the plugin rule from agent-relay's `pluginlint` into the canonical `scripts/doclint`, its fixed command set left behind; the `readme` target's shape per repo, the sidecar the invariant; `hooks/run` optional when `hooks.json` names the plugin's own scripts; a second sidecar line may guard `README.md`), and item 30 (the `person` group ignores `history/sittings/` in the canonical `scripts/hygiene`); both scripts' new shas in §6 (`design/packets/s8-conventions-plugins.md`); forces three one-commit re-sync rows in decisions, respeak and agent-relay; built on branch s8-conventions-plugins, every acceptance line green, 331 passed, awaiting merge (sitting 2026-09-23-2) | claude-code-session | opus | 60 / 80k | `make check` 0; the packet's lines; both scripts' shas in conventions §6; the old shas gone | S7 (main 66c6357) |
| 21 | S9 hygiene and charters, the run-5 findings settled inside conventions: the canonical `scripts/hygiene` scans the working tree (`git ls-files -co --exclude-standard`), so an uncommitted packet is caught before its commit; the `sibling` group joins `person` as not evaluated under `history/sittings/` and this repo's allow row shrinks to `private`; §9 says a packet's charter names doclint's five rows at open; §1's SKILL.md limits enforced by the canonical `scripts/doclint`; §7 says a worktree builder symlinks the main checkout's `.venv` (`.gitignore` ignores the link); both scripts' new shas in §6 (`design/packets/s9-hygiene-and-charters.md`); forces three one-commit re-sync rows in decisions, respeak and agent-relay (respeak also trims five skill descriptions); built on branch s9-hygiene-and-charters, every acceptance line green, 334 passed, awaiting merge (sitting 2026-09-23-4) | claude-code-session | opus | 60 / 80k | `make check` 0; the packet's lines; both scripts' shas in conventions §6; the old shas gone | S8 (main 27b22f9) |
| 22 | S10 fixes r6, both reviews folded into one packet: ADV6-1 to -9 (hygiene gains `secret` and `email` groups, scans paths, symlink targets and binaries; the sidecar carries `README.md`'s sha; `make install` freezes the package under `~/.local/share/claude-session/<tree>/` and the wrapper runs it with `-P`; `NEXT` allowed at the relay's path; checkpoint's dirty reading by one git call, null never clean; one state root and an autouse fixture off the user's state; `record` caps a request's total; `charter check` at 4,096), the r6 cycles C1 to C3 (`scripts/bounded`: a per-tree lock, a wall, a load breaker; `validate` bounded; doclint holds acceptance lines targeted when a packet carries a `verify` row; `CLAUDE_SESSION_DEPTH` in `start`; a `timeout` on every hook), E2 and E5 (`CLAUDE_SESSION_MAX_TURNS`), and the charter-only decisions into conventions and overhaul-r1 (`design/packets/s10-fixes-r6.md`); forces three re-sync rows (both scripts, `email` rows, the `verify` row) and three relay consumers (depth 1 and the turns variable for children, the diff guard on `.hygiene-allow` and the sidecar); built on branch s10-fixes-r6, every acceptance line green, 416 passed, awaiting merge (sitting 2026-09-23-7); S12 (ADV10-1 to -11): built on branch s12b-fixes-adv10 (with s12a merged), every acceptance line green, 447 passed, awaiting merge (sitting 2026-09-23-13) | claude-code-session | opus | 120 / 140k | `make check` 0 (the verify line); the packet's targeted lines; both scripts' shas in conventions §6; the old shas gone | S9 (main cea11b1) |
| 23 | S13 conventions after run 10, two rows: s13a (doclint mirrors `packet.Unbounded` by shape, GRANDFATHERED 28, SPENT; hygiene scans a NUL file for home, secret and email) and s13b (`bounded` exits 128+signum on a signal without a traceback; the doctor drops `--max-turns` from its flag list and reports `meter-hook`; conventions §5 keeps the turns line; the README says 840 s): built on branch s13b-conventions-r10 (s13a merged), 447 passed, awaiting merge (sitting 2026-09-24-3) | claude-code-session | opus | 80 / 140k per row | `make check` 0 (the verify line); the packet's targeted lines; the rendered sha fresh | S13a (main fc49627) |
| 24 | S14 fixes of the third adversarial round (ADV11-1 to -5, -10; the sibling review's ADV11-4 and -6): `bounded` kills the reported command group before the guardian, refuses a non-finite wall or load, says `nested stop` below depth 0; hygiene streams a file over 4 MiB; doclint's suite rule fails closed (`MAKE_TARGETED`) and refuses a NEXT naming a missing prompt; the launcher speaks at every SessionStart: built on branch s14-fixes-adv11, 484 passed, awaiting merge (sitting 2026-09-24-6) | claude-code-session | opus | 80 / 140k | `make check` 0 (the verify line); the packet's targeted lines; three shas in conventions §6 | S13b (main d400db0) |
| 25 | S15 the run-12 re-sync: doclint's SPENT mirrors agent-relay's `spent` (13 stems at its main 9b99873) plus ar21; the relay's ADV11-15 pinned by a hygiene test; `start` always opens a sitting (a test); overhaul-r1 §2.5 scopes the Stop guard to a sitting: built on branch s15-resync, 496 passed, awaiting merge (sitting 2026-09-24-8) | claude-code-session | opus | 60 / 120k | `make check` 0 (the verify line); the packet's targeted lines; doclint's sha in conventions §6 | S14 (main 2a1dfcb) |

Rows 1 to 4, 5, 9, 12, 14's S6 and 19 are written (rows 5, 9, 12 by sitting 2026-09-22-6, whose relay rows are `design/packets/rows-2026-09-22.json`; row 19 by sitting 2026-09-22-10, `design/packets/rows-2026-09-22-r4.json`; row 20 by sitting 2026-09-23-1, `design/packets/rows-2026-09-23.json`; row 21 by sitting 2026-09-23-3, `design/packets/rows-2026-09-23-r2.json`; row 22 by sitting 2026-09-23-6, `design/packets/rows-2026-09-23-r5.json`); row 7 is to be cut off row 18 (allowlist `reference/` and `research/` until D0); row 13's packet is written in example-ops and cites this design's D15. Rows 9 and 10 may run in parallel with 5 to 8 (different repos); nothing else overlaps a repo. The queue file (`relay/queue.yaml`) is born in A2 and carries rows 11 onward; until then this table is the queue and a hand-run sitting takes the next row's packet as its prompt.

## Baseline on main (800a4e7, dry-run by sitting 2026-09-22-1; the exit is the line's own)

| line | exit | last output line |
|---|---|---|
| S1: make test | 0 | `184 passed in 7.82s` |
| S1: make lint | 0 | `python3 -m compileall -q claude_session` |
| S1: test -x scripts/hygiene (absent on main) | 1 | `` |
| S2: test ! -e claude_session/schedulers (present on main) | 1 | `` |
| S2: git grep of the chain words, wc -l (must read 0 on the branch) | 0 | `     114` |
| S3: claude plugin validate plugin/ (absent on main) | 1 | `✘ Validation failed` |
| S3: test ! -e SKILL.md (present on main) | 1 | `` |
| A1: go version | 0 | `go version go1.27.0 darwin/arm64` |
| A1, S3: claude --version | 0 | `2.1.278 (Claude Code)` |

## Baseline on main (54f7d42; agent-relay 88d1ed1; measured by sitting 2026-09-22-6)

| line | exit | last output line |
|---|---|---|
| S4, S5: make check | 0 | `readme: skipped, absent design/readme/source.md` |
| S4, S5: make test, tail -1 | 0 | `224 passed in 7.22s` |
| S4, S5: hooks.json events | 0 | `['SessionStart']` |
| S4: doctor --json check count | 0 | `12` (doctor exits 2 on this Mac, S3's handover) |
| S4: status, report (verbs absent) | 2 | `` |
| S5: commands count (`plugin/commands` absent) | 0 | `0` |
| S5: charters failing `charter check` (verb absent) | 0 | `6` |
| S5: SessionStart output grep 'charter open' | 1 | `0` |
| S5: PreToolUse Agent grep '"deny"' | 1 | `0` |
| AR1: make check | 0 | `readme: skipped, absent design/readme/source.md` |
| AR1: go test -race ./... | 0 | `` |
| AR1: grep -c -- '-race' Makefile | 1 | `0` |
| AR1: hooks.json events | 0 | `[]` |
| AR1: the five hook grep lines (push, commit, nasctl, Stop dirty, SessionStart packet) | 1 | `0` each |
| AR1: garbage stdin to hook PreToolUse | 0 | `` |
| AR1: test -d internal/hooks | 1 | `` |

## Baseline on main (a78158d; the base `s5-commands` 95f4e52 where said; measured by sitting 2026-09-22-9)

| line | exit | last output line |
|---|---|---|
| S6: make check | 0 | `readme: skipped, absent design/readme/source.md` |
| S6: make test, tail -1 | 0 | `224 passed in 6.58s` (on the base: `301 passed in 7.31s`) |
| S6: grep -c '^readme:' Makefile | 1 | `0` |
| S6: source.md present and under 6,144 bytes | 1 | `` |
| S6: shebang count, env python3 | 1 | `0` |
| S6: hygiene sha equals conventions §6 | 0 | `` (the old sha on both sides) |
| S6: dependency marketplaces | 0 | `['claude-code-decisions', 'respeak', 'agent-relay']` |
| S6: grep -c CLAUDE_SESSION_ID README, conventions | 1 | `0` |
| S6: grep -c '"provider"' conventions | 1 | `0` |
| S6: README tokens missing, wc -l | 0 | `7` |
| S6: grep -c 'until S6' .hygiene-allow | 0 | `1` |
| S6: grep -c /usr/bin/python3 install-wrapper.sh | 0 | `1` |

## Baseline on main (4901b1b; measured by sitting 2026-09-22-10)

| line | exit | last output line |
|---|---|---|
| S7: make check | 0 | `readme: fresh` |
| S7: make test, tail -1 | 0 | `319 passed in 7.59s` |
| S7: grep -c 'Packet authoring' conventions | 1 | `0` |
| S7: grep -c 'CONVENTIONS_CEILING = 8192' scripts/doclint | 1 | `0` |
| S7: shasum -c --status rendered.sha256 | 1 | `` (the bare hash is not a checksum line) |
| S7: 'shasum -c' in conventions and the Makefile, grep -c | 1 | `0` |
| S7: git grep -l CLAUDE_SESSION_ID in the code, plugin, README, conventions, readme source, wc -l | 0 | `0` |
| S7: grep -c 'the only session variable' conventions | 1 | `0` |
| S7: scripts whose sha is absent from conventions §6, wc -l | 0 | `1` (doclint) |
| S7: checkpoint --help, grep -c 'add -A' | 0 | `1` |
| S7: checkpoint --help, grep -c 'tracked' | 1 | `0` |
| S7: grep -c 'tracked' design/readme/source.md | 1 | `0` |
| S7: RUNBOOK verbs reset and statusline, grep -c | 0 | `2` |
| S7: RUNBOOK stale words, grep -c | 0 | `4` |
| S7: doctor --json, the python check's ok and 'newest' | 0 | `False False` |
| S7: grep -c /usr/bin/python3 claude_session/doctor.py | 0 | `1` |
| S7 (21): charter open with RELAY_ROW=s7 in a temp dir, ls | 0 | `2026-09-22-1.md` |

## Baseline on main (66c6357; measured by sitting 2026-09-23-1)

| line | exit | last output line |
|---|---|---|
| S8: make check | 0 | `readme: fresh` |
| S8: make test, tail -1 | 0 | `327 passed in 6.54s` |
| S8: grep -c 'def check_plugin' scripts/doclint | 1 | `0` |
| S8: grep -c 'COMMAND_CEILING = 31' scripts/doclint | 1 | `0` |
| S8: grep -c 'COMMANDS = ' scripts/doclint | 1 | `0` |
| S8: grep -c 'plugin/commands/\*.md' scripts/doclint | 1 | `0` |
| S8: doclint probe, a command lacking allowed-tools in a temp repo, then echo $? | 0 | `0` (no plugin rule: nothing refused) |
| S8: grep -c 'def test_plugin' tests/test_doclint.py | 1 | `0` |
| S8: grep -c pluginlint conventions | 1 | `0` |
| S8: grep -c 'the invariant' conventions | 1 | `0` |
| S8: hooks/run and optional on one line of conventions, grep -c -E | 1 | `0` |
| S8: grep -c tamper conventions | 1 | `0` |
| S8: hygiene probe, a person fixture under history/sittings/ and at the root, person files and hits | 0 | `2 2` |
| S8: grep -c 'history/sittings' scripts/hygiene | 1 | `0` |
| S8: grep -c sittings tests/test_hygiene.py | 1 | `0` |
| S8: grep -c -E of the two old shas in conventions | 0 | `1` |
| S8: scripts whose sha is absent from conventions §6, wc -l | 0 | `0` |
| S8: git status --short, wc -l | 0 | `1` (this sitting's charter, untracked when measured) |

## Baseline on main (27b22f9; measured by sitting 2026-09-23-3)

| line | exit | last output line |
|---|---|---|
| S9: hygiene probe, a person fixture untracked and another ignored in a temp repo, person files | 0 | `0` (untracked files are not scanned) |
| S9: hygiene probe, a sibling fixture under history/sittings/ and at the root, sibling files and hits | 0 | `2 2` |
| S9: grep -c '^history/sittings/\*.md: private$' .hygiene-allow | 1 | `0` |
| S9: grep -c of the person-and-sibling phrase in conventions | 1 | `0` |
| S9: grep -c exclude-standard conventions | 1 | `0` |
| S9: grep -c 'goal, budget, pin, window, agents' conventions | 1 | `0` |
| S9: doclint probe, a skill with a 201-char description and a 501-line body in a temp repo, then echo $? | 0 | `0` (no skill rule: nothing refused) |
| S9: grep -c 'def test_plugin_skill' tests/test_doclint.py | 1 | `0` |
| S9: grep -c git-common-dir conventions | 1 | `0` |
| S9: grep -c '^\.venv$' .gitignore | 1 | `0` |
| S9: grep -c -E of the two current shas in conventions | 0 | `1` |
| S9: scripts whose sha is absent from conventions §6, wc -l | 0 | `0` |
| S9: git status --short, wc -l | 0 | `3` (this sitting's charter, packet and rows file, untracked when measured) |

## Baseline on main (cea11b1; measured by sitting 2026-09-23-6)

| line | exit | last output line |
|---|---|---|
| S10: hygiene probe, a key prefix, a symlink to a home path and a private-repo file name in a temp repo, hits outside the allowlist | 0 | `0` (no secret group; the symlink and the path are not scanned) |
| S10: pytest tests/test_install.py tests/test_bounded.py, tail -1 | 0 | `no tests ran in 0.00s` (neither file exists) |
| S10: doclint probe, a packet with a `verify` row and whole-suite acceptance lines, NEXT at the relay's path and at the root, count of `runs a whole suite` and `next:` lines | 0 | `2` (both NEXT files refused; no suite rule) |
| S10: pytest tests -k 'nested or max_turns or unknown or stdin_paths or total or over_default or boundary or sidecar or timeout or pins', tail -1 | 0 | `15 passed, 319 deselected in 0.69s` |
| S10: grep -c -E of the two variables, `eight groups` and `verify. row` in conventions | 1 | `0` |
| S10: grep -c -E of the two current shas in conventions | 0 | `1` |
| S10: scripts whose sha is absent from conventions §6, wc -l | 0 | `0` |
| S10: grep -l '(filled at close)' history/sittings/*-s10-fixes-r6.md, wc -l | 0 | `0` (no such charter yet) |
| S10: git status --short, wc -l | 0 | `2` (this sitting's charter and packet, untracked when measured) |
