# Review r6: the session repo's design decisions since 2026-09-22

Relay row review-6-session, 2026-09-23, main c7dbdee. Read: the defect brief D1 to D7 whole, 17 handovers, 11 packets, conventions, the git log, spawn sites in tests and hooks. Builds nothing. Consumers: the owner (§3 first), the next conventions row (S10), the packet writers, the re-sync rows.

## 1. Decisions ledger

"rec" = in the design of record; "charter" = only in a charter, then the section it belongs in.

- R6-1 canonical `hygiene` and `doclint` here, byte-identical, shas in §6 (S1 to S9). rec §1, §6.
- R6-2 the chain retired whole, D6 (S2). rec overhaul-r1 §1; its §7 still says "Recommend" on 14 items ruled since: gap.
- R6-3 ids D8, state path D9, one marketplace per repo D11, YAML subset D12, layer order D7 (S3). rec §2, §3.
- R6-4 `CLAUDE_CODE_SESSION_ID` the only session variable (S6, S7). rec §3.
- R6-5 the meter: burn-report's definitions, assistant lines only, `off` still meters (S4). charter: overhaul-r1 §2.2.
- R6-6 the spawn gate on Agent|Task|Workflow; `deny` only in reserve; an unknown zone allows (S5). rec SKILL.md.
- R6-7 charter tooling in session, D10; doclint refuses at 4,096 bytes, `charter check` above it (S5). charter: §5 (T4).
- R6-8 `record` ships here, sections never whole, D15 (A2). rec §8.
- R6-9 README from `design/readme/source.md`; freshness by content, the sha sidecar, never mtime (S6). rec §5, §6.
- R6-10 shebang `#!/usr/bin/env python3`, the venv first on PATH under `make`, never Apple's (S6, the 12:55 ruling). charter and Makefile: §1 or §7 (E3).
- R6-11 the four ceilings and §9 packet authoring (S7). rec §5, §9.
- R6-12 charter file `<date>-<n>-$RELAY_ROW.md` (S7 item 21). rec SKILL.md; §1 says `<date>-<n>.md` (T2).
- R6-13 `checkpoint --commit` stages tracked files only (S7). rec source.md.
- R6-14 doctor's python: the running interpreter, newest from pyenv's local list else a shipped tuple, a suggestion (S7). charter: overhaul-r1 §2.
- R6-15 the plugin rule in doclint, no fixed verb set; the renderer per repo, the sidecar the invariant; `hooks/run` optional (S8). rec §1, §5, §6.
- R6-16 `person` and `sibling` not evaluated under sittings; hygiene scans the working tree (E1); SKILL.md limits enforced; the worktree `.venv` symlink; the five rows (S8, S9). rec §5, §6, §7, §9.
- R6-17 2.0.0-alpha.1 matches no `^2.0` (S3); no tag exists though §7 says the tag equals `plugin.json`. charter: §7.
- R6-18 the meter's ceilings come from the profile (180k, 400), never the row's `--max-turns` (S4; D4). charter and the relay's prompt: §3 (E5).
- R6-19 `verify: make check` is the gate line, acceptance lines targeted (the run-5 note). Nowhere in the record; §5 says the opposite (T1).

## 2. Reversals and tensions

- T1 §5 "acceptance is `make check` plus its own lines" and every S packet's `make check` and `make test` lines against the run-5 ruling (the parser refuses any whole suite as acceptance). §5, §9 and the packets yield: the verify line is the gate, acceptance is targeted (`pytest tests/test_x.py`), doclint refuses the rest (C1).
- T2 §1 `<date>-<n>.md` against R6-12. §1 yields; doclint already accepts the suffix.
- T3 R6-10 against the owner's global line "stdlib scripts use `#!/usr/bin/python3`, never `env python3`". The ruling wins, the sha fixes it in four repos; the global line names the exception (E3 is the cost).
- T4 doclint refuses a charter at exactly 4,096 bytes, `charter check` only above. `charter.check` yields, one test.
- T5 the installed `claude-session` runs the main checkout (the wrapper bakes REPO): S3's acceptance measured main, a worktree session's hooks run main's code; S4 onward wrote `python3 -m claude_session`. §7 says it.
- T6 R6-18 against the relay's CONTEXT-line workaround (D4): the session owns the fix (E5).

## 3. Fork-storm class

No test here runs the relay, so D5's recursion closes only through the relay's plan. This repo is its amplifier and holds three unbounded edges of its own.

- C1 relay plan or gate → `make check` → `make test` (334 tests, three spawning the hook on temp state) plus `validate` (two `claude plugin validate`: two node starts, no timeout) plus doclint and hygiene. Bound: NONE: no timeout, lock or load check; 310 concurrent gates were 620 node starts and 310 suites (D5). Fix: acceptance drops the suite (T1); doclint's `check_packets` refuses a line matching `make (check|test)`, `go test ./...`, `pytest` without a file, or `relay (plan|run|gate)` without `--rows` and a temp `XDG_STATE_HOME`, one test; `validate` under `timeout 60`; a per-tree lock (`mkdir .check.lock`, stale at 900 s).
- C2 `claude-session start` → `execvpe claude` → SessionStart → `claude-session hook` (a leaf). `start` scrubs `CLAUDECODE` and `CLAUDE_CODE_SESSION_ID` (launch.py:207), so a nested start cannot see its depth, and the gate skips Bash: a child may `claude-session start builder` without limit. Bound: NONE (the relay's process group holds only its children). Fix: `start` sets `CLAUDE_SESSION_DEPTH` (survives the scrub) and refuses above 1 without `--nested`; one test.
- C3 PostToolUse `*` → sh → a python probe → `python -m claude_session`: three processes per tool call. Leaf; bound: Claude Code's 60 s default (hooks.json declares none). With `.venv` absent the probe's `python3` is pyenv's shim, so D5's rehash lock stalls every tool call 60 s. Fix: `timeout` per hook (5 s); the wrapper tries homebrew's python3 before the bare name.
- C4 `checkpoint --commit` → `git commit` → git hooks: none exist, no `hooksPath`; a future pre-commit running `make check` is a chain, not a cycle. Bounded by design.
- C5 `make readme` → respeak → `claude -p`: outside `check` because R6-9 made the sidecar the invariant; `make install` → doctor → `claude` twice (20 s each). Bounded leaves.
- C6 tests on the live tree (D7's class): `test_charter` checks every real charter under `history/sittings/`; `test_hook_session_start` runs the hook at `ROOT`; `test_doctor` reads `plugin/` and the manifests. Read-only, temp XDG: bounded, but the result depends on untracked files (E1). Fix: fixtures plus tracked charters.

## 4. Timing and edge conditions

- E1 a gate on a dirty tree: hygiene (R6-16) and `test_charter` read untracked files, so `make check` at one HEAD differs by what a builder left (sitting 2026-09-23-3 had three untracked). Invariant: a gate result is a function of HEAD (D2.3's memo key): measure only on `git status --porcelain` empty, or in a fresh worktree. Test: none.
- E2 git under load: `gitinfo._TIMEOUT` is 5 s; `git status` took two minutes in the storm, so SessionEnd's ledger writes `clean` null and `checkpoint` reports no changes. Invariant: null is never read as clean (D2.8's consumer). Test: the write, not the reading.
- E3 the pyenv shim: `env python3` outside `make` (acceptance lines call the scripts directly) resolves through the shim when shims lead PATH; each such line paid D5's 60 s lock. Invariant: no gate line goes through a shim. Test: none.
- E4 charter numbering: `_numbered` takes today's max plus one per working tree; root and worktree collided twice (7/7b, 9/9b); the suffix bounds relay rows only. Invariant: names unique across worktrees (always a suffix). Test: the suffix's parse only.
- E5 the meter's ceiling is 400 turns while a relay child has 80: packets-20 read "clear" at 79 of 80 (D4). Invariant: the zone follows the smaller of the profile's and `--max-turns` (launch.py holds the argv). Test: none.
- E6 the meter sums the transcript, not the window (D3): the gate and the checkpoint nag fire early (fail-closed). Invariant: context is the last assistant message's usage. Test: burn-report parity only.
- E7 root and worktree share one `.venv`: `pip install -e` from a worktree repoints main's editable install. Invariant: a worktree never writes under `.venv`. Test: none.
- E8 no per-hook timeout in hooks.json: a 60 s stall at SessionStart is silent. Invariant: a hook returns under 5 s or exits 0 silent. Test: none.

## 5. TLA+

No protocol here deserves a model: the zone map and the gate are pure functions with table tests. The relay's model takes this repo as environment: a hook may hold a tool call up to 60 s; a ledger line with `child_exit` has `clean` in {true, false}, never null; `CLAUDE_SESSION_DEPTH` at most 1.

## 6. Decisions for the owner

1. Acceptance lines never run the suite: §5 and §9 reworded, doclint refuses (C1), then the re-syncs. Recommend yes, S10 act 1. Consumer: S10, the packet writers.
2. The nesting guard in `start` (C2). Recommend yes, one act. Consumer: S10; the relay sets depth 1 for its children.
3. `validate` under a timeout, the per-tree gate lock, per-hook timeouts (C1, C3, E8). Recommend yes. Consumer: S10 (both files sat outside every wall so far); the siblings' Makefiles.
4. The zone follows `--max-turns` (E5), closed here. Recommend yes. Consumer: S10; the relay drops its workaround after.
5. The shebang stays `env python3` (T3); gate lines run under `make` or `.venv/bin/python`; the global CLAUDE.md line names the exception. Recommend yes. Consumer: the owner (example-mac), the packet writers.
