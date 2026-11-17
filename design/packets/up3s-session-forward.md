# Packet up3s-session-forward: session's `install-cli` moves its command forward only

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief up3s-session-forward (S3), from the install review's finding 5 |
| pin | `ef0ba32` on main (2.0.0-alpha.130, is2-first-read's merge); commons' copies from its main `626a3f0`. Worktree `.claude/worktrees/up3s-session-forward`, branch `up3s-session-forward`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no `make readme`; no relay verb; every probe in a temp HOME and a temp prefix |
| may touch | what commons' `scripts/sync` places (`scripts/agentik`, `scripts/vendored.sha256`, `plugin/lib/agentik_install.py`, `plugin/bin/agentik`, and the rest of its list where they differ) and any test that pinned an old copy; `plugin/lib/claude_session/install.py` (`install`, `_behind`, new `newer`, `_ours`, `_ahead`), `cli.py` (`cmd_install_cli`, the `install-cli` parser), `doctor.py` (`_check_launcher`), `tests/test_up3s_session_forward.py` (new), any test that pins the doctor's launcher row or install-cli's lines, `make stamp`'s files, this packet, `history/sittings/2026-11-17-1-up3s-session-forward.md` |
| verify | `make stamp`, then `make check`, by the gate queue, last |
| acceptance | §3's table; `.venv/bin/python -m pytest -q tests/test_up3s_session_forward.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the copy, the failing tests, the change |

## 1. What the source says (baseline at `ef0ba32`)

The owner, 2026-11-16: "Use up to 2 Fable agents to review our upgrade/install so far. Use up to 8 opus agents to build anything to help us with install/upgrade concerns." His standing ask: "setup and doctor usable today".

The source is the install review's finding 5 (§4).

Measured at the pin, temp HOME and prefix, a copy of the plugin at a made-up 2.0.0-alpha.999 placed first: the pin's `install-cli` prints `installed <prefix>/bin/agentik-session -> … (2.0.0-alpha.130); …`, exits 0, and the command reads alpha.130; `--force` is argparse's `unrecognized arguments`, exit 2. Over a command at 2.0.0-alpha.1 it places alpha.130 with is2's two PATH lines.

## 2. Rulings

- R1, `install()`: where the command in place is one `install-cli` wrote, its code stands and its version is newer than the tree being placed, nothing is written and the result says which version was kept, as commons' `install()` does with `kept`; `force` places anyway. One comparison, the one `refresh` has (`order`). The check is made again under the lock.
- R2, the verb: `install-cli --force`. Where a newer command is kept it prints one line, in commons' words (`Left <launcher from ~> at <its version>, newer than this plugin's <version>; --force places it.`), moves no link and no door, runs no prune, exits 0. Its other lines, is2's PATH lines among them, are as on main.
- R3, the refresh at SessionStart and every other caller of `install()` keep today's behaviour.
- R4, the copy: commons' `scripts/sync` run with this worktree as its target; every placed file `cmp`-equal to commons' canonical and `scripts/vendored.sha256` as sync wrote it. Its own commit, before R1; a test that pinned an old copy moves in it.
- R5, the doctor: where it compares the command's version with the plugin's, a newer command reads newer, as a note, and `older` only where it is older.

## 3. Interfaces, choices and acceptance

- `install.newer(a, b)`: version `a` sorts above `b` by `order`; equal, absent or unreadable False. `_behind` and `_ahead` both use it: the one comparison.
- `install._ours(path, share)`: install-cli's launcher form (its second line), `TREE=` and `VERSION=` once each, the `TREE=` line quoted as the template quotes it, that tree under the share. `_ahead(path, share)`: its version where `_ours`, `<TREE>/agentik-session` a readable file, and `newer(theirs, SEMVER)`; else None.
- `install.install(prefix=None, env=None, force=False)`: the result gains `kept`, None or the version left; kept, `tree` is None and `pruned` empty.

Acceptance: `tests/test_up3s_session_forward.py`, per-test temp HOME and prefix.

| # | line | at `ef0ba32` |
|---|---|---|
| 1 | an older tree's `install-cli` over a newer command: R2's line, exit 0, the launcher's bytes unchanged; `--force` places it | red: placed, alpha.130; `--force` exit 2 |
| 2 | a command older than the plugin is placed as today, is2's PATH lines off PATH; a newer command whose tree is gone is placed | green / red (no `--force`) |
| 3 | every file sync places `cmp`-equal to commons' canonical; `shasum -a 256 -c scripts/vendored.sha256` exit 0 | four copies behind commons main |
| 4 | `make stamp`, `make check` by the gate; `scripts/hygiene --require-private --commits main..HEAD` exit 0 | green at alpha.130 |

## 4. Findings that name this row

The install review's finding 5: an older plugin's `install-cli` replaces a newer command. That is the line `/session:install-cli` runs in any session started before an update, and the remedy every launcher's `is gone` line names. Commons' `install()` now leaves such a command (`kept`, `--force` to place anyway); session's own `install()` has no such check, though its `refresh` does (`_behind`, by `order`).

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude`, or relay ledger.

## 6. Report

The record the coordinator names.
