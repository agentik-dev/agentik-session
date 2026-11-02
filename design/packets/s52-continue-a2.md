# Packet s52, amendment 2: `--continue` adopts only the day's newest; the conf's old names

| item | value |
|---|---|
| from | s52's refuter round 1 (FAIL at 9392445 on F1, S3; F2 S4; F3 waived by hq's cut of act 2), sitting 2026-11-01-2-hq; probes in hq's scratch `probe/cont.sh`. Parent `design/packets/s52-continue.md` |
| pin | branch `s52-continue` at 9392445, worktree `.claude/worktrees/s52-continue`; continue there |
| wall | the packet's row (`design/packets/s52-continue.md`), unchanged |
| may touch | `plugin/lib/claude_session/charter.py`, `plugin/lib/claude_session/cli.py` (the charter verb), `tests/test_charter.py` and the CLI tests of the charter verb, `plugin/lib/agentik-tool.conf`, `plugin/.claude-plugin/plugin.json` and the files a test pins to its version, this amendment as `design/packets/s52-continue-a2.md` (reshaped as a1 was), the branch's charter |
| acceptance | §2's acts; the verify row's check green |
| verify | the packet's row, unchanged: `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line |
| budget | One commit per act. **Stop at 60k context or 40 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

## 1. What the source says

Copied from hq's `history/sessions/BRIEF-2026-11-01-s52-a2.md`; as a1's copy was, the sections are re-headed to GUIDE §9's six, the `wall, verify` row is split into the packet's `wall` and `verify` rows, an `acceptance` row names the verify row's check, and for hygiene its home paths, one private name and the conf's two old names (a sibling's) are rewritten; the text otherwise as written.

**The refuter's round 1.** F1 (S3) blocks: `--continue` adopts a same-suffix charter that is not the day's newest. F2 (S4): the conf's old names are empty. F3 is waived by hq's cut of act 2.

## 2. Rulings

The acts.

0. This amendment, committed first.
1. **F1 (S3, blocks).** `charter.py:260-272` (`adoptable`) adopts the newest charter of the same suffix even when another suffix's charter is newer that day, so a bare `charter close` (`cli.py:404`, `newest_today`) writes into the other chain's file, against the Mac's ledger, entry 22's "the newest is live". `--continue` adopts only when the same-suffix file is also today's newest of any suffix and under 3,584 B; otherwise it writes the next `<today>-<n+1>` as `open` does. Test, the refuter's repro: `RELAY_ROW=hq open` gives -1-hq, `RELAY_ROW=land open` gives -2-land, `RELAY_ROW=hq open --continue` writes -3-hq (not -1-hq), and `close --exit` then writes -3-hq, leaving -1-hq and -2-land byte-unchanged. The earlier `--continue` tests stand.
2. **F2 (S4).** `plugin/lib/agentik-tool.conf`: `old_name` set to the tool's old command name and `old_state` to its old state folder, matching `install.py:25` (`OLD_NAME`) and `config.OLD_APP`. First check agentik-commons' `scripts/sync` writes the conf only when absent (it says "not a vendored copy"); if sync would overwrite it, stop and report instead.
3. **The version**, if `plugin-version-check` asks: alpha.45.
4. The packet's verify line, last; read the code from the gate's line.

## 3. Interfaces

None beyond the parent's: `charter open --continue` keeps its flag and its exits; only the adoption rule narrows.

## 4. Findings that name this row

The refuter's F1 (act 1) and F2 (act 2); F3 waived.

## 5. Forbidden reads

The parent's.

## 6. Report (at most six lines)

The sha; each act's commit; the gate's id and its code from its line; the suite's counts.
