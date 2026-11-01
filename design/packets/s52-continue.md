# Packet s52: `charter open --continue`, one charter a day; session's NICE as a table

| item | value |
|---|---|
| from | agentik-hq HANDOFF 18 (build 7, the owner's word of 2026-11-01); `~/code/agentik-hq/design/05-records-as-tables.md` §2, §3, §4, §6, §7 item 5; macbase entry 22 (the charter: name, cap, the newest is live) |
| pin | session main 50cfe87, plugin 2.0.0-alpha.43; commons main 05bc434 (recordlint in `sync`); worktree `~/code/agentik-session/.claude/worktrees/s52-continue`, branch `s52-continue`, cut there |
| wall | this repo; read `~/code/agentik-hq`, `~/code/agentik-commons` and the other `~/code/agentik-*` repos at main, never write there, except that `~/code/agentik-commons/scripts/sync <this worktree>` writes into this worktree; no push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb or binary; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME; zsh here, `bash -c` for bash syntax; `rm -r` only as `"${VAR:?}"` |
| may touch | `plugin/lib/claude_session/charter.py`, `plugin/lib/claude_session/cli.py` (the charter verb's arguments), `tests/test_charter.py` and the CLI tests that pin the charter verb, the charter skill's text where it names `open`, `scripts/` (by `sync` only), `Makefile`, `NICE_TO_HAVE.md`, `history/NICE-2026-11-01.md` (by `git mv` only), `.hygiene-allow`, `plugin/.claude-plugin/plugin.json` and the files a test pins to its version, README's charter lines and their sidecar if they exist, this packet as `design/packets/s52-continue.md`, a charter under `history/sittings/` |
| acceptance | §2's acts; `make check` green, recordlint's line in it |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line |
| budget | One commit per act. **Stop at 120k context or 90 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

Read first, by sections (`record <file> --sections`, then `--section`): design/05 §3, §4, §6; `plugin/lib/claude_session/charter.py:20-60,238-330`; `cli.py:359-420` and the charter parser near `:1158`; `tests/test_charter.py`'s `open` tests; commons `GUIDE.md` §9's rows paragraph.

## 1. What this is

A sitting continues the day's charter instead of opening a new one each respawn; then session converts its NICE. **Not here:** any other repo's conversion; changing plain `open`'s behaviour; the respawn path (`RESPAWN:`, `checkpoint --respawn --charter`, the state file), which design/05 §6 keeps.

## 2. Acts

0. This packet, committed first.
1. **`--continue`.** `charter open --continue "<goal>"`: when today's newest charter of the same suffix (`_numbered`, the suffix as `open` derives it) is under 3,584 B, it records that file as this sitting's (as `cli.py:691` does for a new one), prints it and writes nothing to it; otherwise it writes `<today>-<n+1>` as `open` does. Tests: adopt; spill at exactly 3,584 B (3,583 adopts); none today writes `-1`; another suffix is not adopted; the record written; the adopted file's bytes unchanged.
2. **`--row NAME`** on `charter open` (cuttable): the suffix for a hand-run sitting, so hq writes `<date>-<n>-hq.md` (today `$RELAY_ROW` alone names it; `--row` wins over it). Tests: the name, a bad name ignored as today. If cut, a NICE row and the reason in your charter.
3. **Resync.** `~/code/agentik-commons/scripts/sync <this worktree>`; commit what it places.
4. **Makefile.** The `doclint` target runs `scripts/recordlint` after `scripts/doclint`.
5. **session's NICE.** design/05 §3: `git mv NICE_TO_HAVE.md history/NICE-2026-11-01.md`, and in that commit `history/NICE-2026-11-01.md: sibling` under the `NICE_TO_HAVE.md: sibling` row of `.hygiene-allow` (add the pair if the file allows NICE under another group; keep its group). A new `NICE_TO_HAVE.md`: a title, one head paragraph naming the archive, then the table under a `##`, holding the S1 to S3 items you confirm open on main (design/05 counts 5); ids from `n1`. recordlint green on it.
6. **The version.** Plugin 2.0.0-alpha.44, one bump, last; the files a test pins move with it. If `plugin-version-check` asks again after a later change, bump again.
7. The gate, last.

## 3. The stop

Stop and report, committing what is there, on: `--continue` needing a change to plain `open`'s output; a test of today's behaviour that must change; hygiene red on a file you cannot allow without a new reason row. A stop is a result.

## 4. Report (at most ten lines)

The branch and sha; each act's commit; the gate's id and its code from its line; the suite's counts; `--row` built or cut; the NICE rows kept (ids, levels, one line each); anything left over, and if you stopped, the exact resume line.
