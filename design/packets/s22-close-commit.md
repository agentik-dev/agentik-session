# Packet S22: a close names its commit, and a respawn refuses an uncommitted charter

| item | value |
|---|---|
| from | the observer's check-in 99 (2026-10-12 04:37, F13); `plugin/skills/session/SKILL.md` on `close`; `claude_session/cli.py` `_respawn_check` and the charter verb's `close` |
| pin | `c1-precompact` at 0af80b8 (unmerged; it merges first and takes 2.0.0a7); worktree and branch `s22-close-commit` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `relay`, real `claude`, `claude-session run`, `claude plugin`, `make readme` or `make install`; every python `-B`; tests use temporary state dirs and repos, never the account's |
| may touch | `claude_session/cli.py` (the charter verb's `close` branch, `_respawn_check`, one new helper), `claude_session/gitinfo.py` (one helper, if needed), `claude_session/__init__.py`, `plugin/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `pyproject.toml` (these four the version only), `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `tests/test_charter.py`, `tests/test_cli.py`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `.venv` (the link) |
| acceptance | `.venv/bin/python -B -m pytest tests/test_charter.py tests/test_cli.py -q -k s22 2>&1 \| tail -1` reads `8 passed` or more (c1: no tests ran); `.venv/bin/python -B -m pytest tests/test_charter.py tests/test_cli.py -q 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check` |
| budget | acts: 0 charter; 1 tests, red; 2 close's lines and the refusal; 3 skill, runbook, version. 50 turns, stop at 40 (commit the act in flight), 180k; one commit per act |

## 1. What the source says

At 04:28 on 2026-10-12 the example-ops orchestrator, under the launcher (chain `example-ops`), ran `claude-session charter close --exit RESPAWN history/sittings/2026-10-11-12-example-ops.md` after its last commit (7ab752f9, 04:22), cancelled its cron and ended its turn. It never ran `checkpoint --respawn`, so its session dir holds no `respawn.json` and the launcher never restarts it. The exit line stayed uncommitted, so main read dirty, and two sibling sittings that merge only into a clean main (`wait-clean-main.sh`) were held. SKILL.md: "`close` appends exactly one line under Handover, `- exit taken: <text>; about <context> context, <turns> turns` from the meter"; it says nothing of the commit or of the respawn that follows. `_respawn_check`: "Every refusal exits 2 with one line and writes nothing."

## 2. Rulings

1. **close's lines.** After the exit line is written, `charter close` prints the charter's path as its first stdout line, as today (callers read it). When the charter lies in a git work tree and `git status --porcelain -- <path>` reads a line, it prints `next: git -C <dir> add -- <name> && git -C <dir> commit -m "charter: the exit taken" -- <name>`, `<dir>` the charter's absolute directory and `<name>` its basename, each shell-quoted when it needs it, so the line runs verbatim from any cwd on an untracked charter or one in another repo (fix round, F1 and F2). When the charter's Next act opens on RESPAWN (`charter.RESPAWN` on `charter.next_act_line`), it prints `then: claude-session checkpoint --respawn --charter <absolute path>`, inside a tree or not. The exit code is unchanged.
2. **The refusal.** `checkpoint --respawn --charter F` exits 2 and writes nothing when F lies in a git work tree and `git status --porcelain -- F` reads a line (modified, staged, or untracked): `checkpoint --respawn: <path> is not committed; commit it first: git -C <dir> add -- <name> && git -C <dir> commit -m "charter: the exit taken" -- <name>`, the same line as close's `next:` (fix round, F1 and F2). With `--commit`, a tracked charter passes, since the checkpoint's own `add -u` and commit take it; an untracked one is refused with `--commit` too. A git call that fails or times out reads unknown: the respawn goes on, with one stderr line saying the charter's state is unknown. Outside a work tree there is no check. The check runs after the existing Next act checks and before anything is written, in one git call with gitinfo's timeout.
3. **The docs.** SKILL.md's charter part says the order in one sentence: close, commit the charter, then on RESPAWN `checkpoint --respawn`; RUNBOOK's RESPAWN close says the same and names the refusal. The README is not touched (its render is a respeak run); `NICE_TO_HAVE.md` gains one S4 line for its next render.
4. **Version** 2.0.0a8 in the four places.
5. **Tests**, `s22` in every name. In `tests/test_charter.py`: `test_s22_close_names_the_commit` (a repo with the charter committed: the path first, then the `next:` line naming it; a RESPAWN Next act adds the `then:` line with the absolute path; another Next act prints no `then:` line); `test_s22_close_outside_a_tree` (no `next:` line; a RESPAWN Next act still prints `then:`). In `tests/test_cli.py`: `test_s22_respawn_refuses_a_modified_charter` and `test_s22_respawn_refuses_an_untracked_charter` (exit 2, the message names `git commit`, no marker and no checkpoint overlay, as s19's refusals assert); `test_s22_respawn_takes_a_committed_charter` (exit 0, marker written); `test_s22_respawn_commit_takes_a_tracked_charter` (modified and tracked, `--commit`: exit 0, HEAD holds the charter, marker written); `test_s22_respawn_commit_refuses_an_untracked_charter`; `test_s22_respawn_git_unknown_goes_on` (git made to fail: exit 0, the stderr line, marker written).
6. **Left.** A sitting that closes on RESPAWN and ends its turn without `checkpoint` is not detected by the Stop hook; the printed `then:` line is this packet's answer. File the hook as S4.

## 3. Interfaces

`cli._charter_dirty(path: str) -> bool | None`: True a line, False clean, None unknown or no work tree. The charter verb's `close` stdout: the path, then `next: …`, then `then: …`. `_respawn_check(args)` gains the refusal of ruling 2.

## 4. Findings that name this row

F13, the observer's sitting 2026-10-12-1 (example-mac `history/sittings/2026-10-12-1-observer.md`).

## 5. Forbidden reads

Transcripts; other repos; the account's state dir (`~/.local/state/claude-code-session`).

## 6. Report (capped)

At most 150 words: both acceptance lines' last lines; the s22 tests red at the pin and why; each existing test changed; anything filed. Last line: branch, head sha.
