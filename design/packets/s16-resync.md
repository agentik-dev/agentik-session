# Packet S16: the README renderer runs as a marked helper (relay-r1 §10)

| item | value |
|---|---|
| from | agent-relay `design/relay-r1.md` §10 at its `main` after `ar25c-fixes-adv15` merged; `design/overhaul-r1.md` §2.5; `scripts/readme-render`; `tests/test_readme.py` 144-202 |
| pin | this repo's `main` at the row's start; branch `s16-resync` off `main` (no `base`); worktree `.claude/worktrees/s16-resync` |
| wall | this repo only; agent-relay read only. No push, `--amend`, rebase, device or network. Tests set `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME` to temp dirs; no live `claude` in a test. Never `relay plan` or `run` without `--rows` and a temp `XDG_STATE_HOME`. Logs go to `mktemp` |
| may touch | `design/packets/s16-resync.md`, `scripts/readme-render`, `tests/test_readme.py`, `design/overhaul-r1.md`, `design/readme/source.md`, `README.md`, `design/readme/rendered.sha256` (these three by `make readme`), `history/sittings/*.md`, the `.venv` link. Nothing else |
| acceptance | `grep -c 'CLAUDE_SESSION_HELPER=1' scripts/readme-render` reads 2 or more; `grep -c 'refused past depth 2' scripts/readme-render` reads 1 or more; `grep -c 'env -u RELAY_ROW' scripts/readme-render` reads 0; `grep -cE 'CLAUDE_SESSION_HELPER=1 claude -p.*refused past depth 2' design/overhaul-r1.md` reads 1 or more; `grep -c 'def test_renderer.*helper' tests/test_readme.py` reads 2 or more; `.venv/bin/python -m pytest -q tests/test_readme.py -k 'helper or status_line' 2>&1 \| tail -1 \| grep -cE 'failed\|error\|no tests'` reads 0; `shasum -c --status design/readme/rendered.sha256` exits 0; `make doclint` exits 0; `make hygiene` exits 0; `grep -c '^# Packet S16:' design/packets/s16-resync.md` reads 1; `git diff --name-only --diff-filter=A main...HEAD -- history/sittings \| xargs grep -cE '/Users/[a-z]\|~/cod[e]/\|filled at close'` reads 0; `git status --short \| grep -c .` reads 0 |
| budget | 50 turns, 144k context, `claude-opus-5-5` (`--max-turns 50`); one commit per act; `make check` in the foreground, then commit in the same turn; checkpoint at 40 turns: land the act in flight, close |
| verify | `make check` |

## 1. What the source says (quoted)

relay-r1 §10, expected: "a helper a sitting spawns keeps `RELAY_ROW` and `CLAUDE_SESSION_MAX_TURNS`, runs in the foreground as `CLAUDE_SESSION_DEPTH=$((d+1)) CLAUDE_SESSION_HELPER=1 claude -p … --max-turns N`, and is refused past depth 2; Stop and `start.json` skip it; `DropSitting` is the relay's own helpers' alone". The text on agent-relay's `main` wins where they differ.

## 2. Rulings

You are headless (`claude -p`): the sitting ends the moment your turn ends. Never delegate an act to an agent, never start a background command or a background agent, never end a turn waiting for a notification. Do every act yourself, in the foreground, and commit it before the next act starts.

Paths are repo-relative. `M` is the main checkout (`git rev-parse --path-format=absolute --git-common-dir`, less `/.git`), `P` its parent. No worktree yet (not a relay row): `git worktree add .claude/worktrees/s16-resync -b s16-resync main` in `M`. Before any `make`, `.venv` links to `M`'s (conventions §7). At most ONE fork, for the owner; no NEXT.

0. **Copy-in, first.** Your packet is `relay/prompts/2026-09-24-s16-resync.md` in the orchestrator's private checkout under `P` (the row's `prompt`; `ls "$P"/*/relay/prompts/2026-09-24-s16-resync.md` finds it). Copy it verbatim to `design/packets/s16-resync.md` (`cp`, `cmp`); commit that file alone.
1. **Charter, rule text.** Open `history/sittings/2026-09-24-<n>-s16-resync.md` (next free n), `# Sitting 2026-09-24-<n>: claude-code-session, s16-resync`: doclint's five rows (goal, budget, pin, window, agents), `## Done-ness`, `## Handover`, `## Next act`. In a subshell `cd "$P/agent-relay"` (a relay row refuses `git -C`): `git log -1 --format=%h main -- design/relay-r1.md`; `git show main:design/relay-r1.md` to a `mktemp` file; cut §10's sentence, `a helper a sitting spawns keeps` through `own helpers' alone`, to a `mktemp` file `S`. Record the sha, `S`'s sha256 prefix. `S` empty: close the charter ("no helper rule at <sha>"), stop. Commit.
2. **The rule.** `scripts/readme-render`: the renderer's line drops `env -u` for `CLAUDE_SESSION_DEPTH=$((d + 1)) CLAUDE_SESSION_HELPER=1`, d being `CLAUDE_SESSION_DEPTH` (unset or empty: 0); `RELAY_ROW` and `CLAUDE_SESSION_MAX_TURNS` pass through; the renderer's `claude -p` has `--max-turns`. In setup, before any write: d not a plain non-negative integer, or d + 1 over 2, exits 2. Its comment quotes `S` verbatim on one line, citing relay-r1 §10 at the sha. Tests: `test_renderer_runs_without_the_sitting_markers` becomes `test_renderer_runs_as_a_marked_helper` (d = 1: the fake sees depth 2, `CLAUDE_SESSION_HELPER=1`, `RELAY_ROW` and `CLAUDE_SESSION_MAX_TURNS` as given) and `test_renderer_helper_refused_past_depth_2` (d = 2: exit 2, the fake never runs, nothing written), each red on `main`. overhaul-r1 §2.5: the helper paragraph becomes `S` quoted ("relay-r1 §10 at <sha>") and names the tests; the Stop guard's parenthetical adds "not under `CLAUDE_SESSION_HELPER=1`". One commit.
3. **README, only if act 2 moved the suite's count.** `make readme` once (the new helper); `make check` green; commit. A failed render leaves README.md untouched: commit the source, name it (the fork).
4. **Close.** The charter closed, under 4,096 bytes, no home path, before the last commit. Commit.

## 3. Interfaces (signatures, not prose)

`scripts/readme-render`: exit 2 before any write when d + 1 > 2. Commits `s16 act N: <one line>`.

## 4. Findings that name this row

On `main` `db648f3`: `scripts/readme-render` 77 drops the markers (`env -u`); `tests/test_readme.py` 165 pins it. Since ar25b a row denies that drop; Stop skips a marked helper instead.

## 5. Forbidden reads

Other repos beyond this packet and relay-r1 §10; ledgers, transcripts; `history/` beyond your charter.

## 6. Report (capped)

Each acceptance line's exit and last line; the sha, `S`'s prefix; each test red on `main`; `make readme` or not; the fork. Last: branch, head sha.
