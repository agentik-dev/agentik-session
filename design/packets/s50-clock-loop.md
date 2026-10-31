# Packet S50: the band's loop survives a refused clock

| item | value |
|---|---|
| from | agentik-hq sitting 2026-10-31-3-hq; the flake reddened gates 20261031-…-141 and -158 under load, on main: `session.test.ts` "the file ran to its end", `no implementation for clock.sleep`, session.ts:397; its lead is agentik-session NICE_TO_HAVE.md:275 and :337 |
| pin | 0e93334 (main, alpha.35); worktree `.claude/worktrees/s50-clock`, branch `s50-clock`, cut, its `.venv` a link |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`, `claude` but `claude plugin validate`; a test or probe never writes under the live `~/.local/state`; no relay verb, no relay binary built or run; no `pkill` by name or pattern; a Python probe needs PYTHONPATH=<worktree> |
| may touch | `plugin/hooks/session.ts` (the band's loop only), `plugin/hooks/session.test.ts`, `NICE_TO_HAVE.md`, this packet, the charter, and the version act's pins (adcb9d8 is the model: `README.md`, `claude_session/__init__.py`, `design/readme/rendered.sha256`, `design/readme/source.md`, `plugin/.claude-plugin/plugin.json`, `pyproject.toml`, `tests/test_doctor.py`, `tests/test_install.py`) |
| acceptance | the mod's tests by the Makefile's own line, green; a new test goes red with session.ts's change reverted, and the report quotes that red; `sed -n` of the loop shows a catch on the sleep; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet, as `design/packets/s50-clock-loop.md`, committed first; 1 the test, red; 2 the loop; 3 the NICE lines; 4 the version, last, one bump to 2.0.0-alpha.36, the README count from the suite, the sidecar re-hashed by hand. 40 tool calls, 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says: the defect

`session.ts:396-398` starts the band's tick as `void (async () => { for (;;) { await $.clock.sleep(EVERY_MS); await start(); await $.ui.invalidate('ui.render') } })()`. Nothing catches it. When `$.clock.sleep` rejects (a test's handlers are gone when the loop wakes late; an engine refusing the clock at teardown), the rejection is unhandled: bun fails the file, and in the engine it is a stray rejection from a hook module.

## 2. Rulings

1. **A refused sleep ends the loop**, silently: `try { await $.clock.sleep(EVERY_MS) } catch { return }`. Nothing is left to pace on, and looping on a clock that refuses at once would spin.
2. **A refused `ui.invalidate` does not end it.** It is swallowed and the next tick tries again, so the band does not freeze on one failed redraw. `start()` already catches its own failures, so one `try` around `start` and the invalidate is enough. A swallowed failure writes nothing.
3. **No other line of the loop changes:** `EVERY_MS`, `MAX_TRIES`, the first `start()`, `turn.complete`'s retry stay as they are.
4. **The tests**, in `session.test.ts`, each forcing the case deterministically, with no sleep-based timing: (a) `clock.sleep` rejects on the loop's first call: no unhandled rejection reaches the runner, the loop makes no further call, and `session.start` still answered; (b) `ui.invalidate` rejects once on a tick: a later tick still runs and draws the meter. If bun's own unhandled-rejection failure is what proves (a), say so and quote the red run from the reverted tree.
5. **`retrying`'s comment at session.test.ts:340-342** stays true or is corrected; S41 Amendment 1's parked-loop wait stays, since it keeps the tests' counts deterministic.

## 3. Interfaces

None new: the loop's two `$` calls, as they are.

## 4. Findings that name this row: the NICE lines (act 3)

Move lines 275 and 337 of NICE_TO_HAVE.md to answered, in the file's own way, naming S50. Add, under a heading `## S49's refuter, round 2 (2026-10-31, S4)`, these four as written:

- `harness.py:92` `record_hook`'s flush moves the exit when stdout is a failing regular file, 4097 to 8178+ bytes: main rc 120 against new rc 0; a block only if Claude Code's hook stdout is a regular file, unread.
- `harness.py:136`: a lone-surrogate event crashes `report --hooks`.
- `measure.stated_limits`: RecursionError.
- A directory at `hooks.jsonl.1` stops rotation.

## 5. Forbidden reads

Transcripts; `~/.local/state`, every part; relay ledgers.

## 6. Report (at most ten lines)

The branch and sha; the gate id and exit; the quoted red; anything decided or left over.

## 7. Amendment 1: the refuter's round 1 on c6947b9, the coordinator's ruling

The refuter passed the acceptance row; the coordinator rules its F1 a blocker, since ruling 4(b) is unmet. Test-only: same worktree and wall, one commit per act, no merge or push. The rulings above stand.

**The wall, ruled.** `claude plugin test plugin`, the Makefile's mod line, is allowed in this packet. The refuter found it uses no model or quota. Every other `claude` verb stays barred but `claude plugin validate`.

1. **F1, the blocker.** Test (b) never makes `ui.invalidate` reject, so ruling 2's catch has no test. A test calls the module's `register` directly with a fake `$`, whose `ui.invalidate` rejects on a tick, and asserts a later tick still runs. Test (b) stays only if it still says something true, and its comment does not claim the catch. Acceptance: in a scratch copy, never the worktree, remove session.ts's `try` on that line, and separately change its catch to `return`; each goes red; the report quotes both.
2. **F3.** The comment at session.test.ts:375-376 is corrected: a `catch { continue }` mutant hits the wall (rc 124) rather than failing the count, because earlier tests' loops spin once their handlers are gone. It is still red, and the comment says that.
3. **F2 and one more**, to NICE_TO_HAVE.md as S4: session.ts:395's redraw inside the outer catch, reproduced with a fake `$`; the tick's missing bound, read and not run.
4. **The version.** If `plugin-version-check` refuses a change under plugin/ after the alpha.36 commit, alpha.37 in the same pins, the README count from the suite, the sidecar re-hashed; alpha.36 is then skipped, as alpha.23 was.

Acts: 0 this amendment; 1 F1; 2 F3; 3 the NICE lines; 4 the version, last. Verify as the parent's row. The report is at most eight lines: the head sha, the gate id and exit, the two quoted reds, the version, anything left over.
