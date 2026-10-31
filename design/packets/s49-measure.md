# Packet S49: measure the harness

| item | value |
|---|---|
| from | agentik-hq HANDOFF 17, build 4 of the Fable review (`docs/REVIEW-2026-10-31-suite-review.md` §5 item 4, §3.4's hooks row), on the owner's word of 2026-10-31: "the shim appends `{event, ms, exit}` to `hooks.jsonl`; `SessionEnd` writes `claude_md_bytes` and `rate_limits` to the ledger row" |
| pin | 95acb37 (main, alpha.33); worktree `.claude/worktrees/s49-measure`, branch `s49-measure` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`, `claude` but `claude plugin validate`; a test or probe never writes under the live `~/.local/state`; no relay verb, no relay binary built or run; no `pkill` by name or pattern; agentik-observer is read only |
| may touch | `plugin/hooks/run`, `plugin/commands/report.md`, `claude_session/harness.py` (new), `claude_session/hooks.py` (`dispatch`, `_ledger_line`), `claude_session/ledger.py` (`LEDGER_KEYS`, `entry_for`), `claude_session/measure.py` (`stated_limits`), `claude_session/cli.py` (`cmd_report`, its parser), `tests/test_s49.py` (new), `tests/test_ledger.py` (the key count), `tests/test_s34.py` (its pin on the shim's Stop line), `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `.hygiene-allow` (the shim names the tool's old state folder, as `config.py` does), this packet, the charter, and the version act's pins |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s49.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on 95acb37: the file is absent); `.venv/bin/python -B -m pytest tests/test_ledger.py tests/test_precompact.py -q 2>&1 \| tail -1` reads `passed`; `grep -c 'hooks.jsonl' plugin/hooks/run` reads at least 1 (on 95acb37: 0); `grep -c 'exec "$tool"' plugin/hooks/run` reads 0 (on 95acb37: 1); `make hygiene` exits 0 |
| verify | `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet; 1 the tests, red; 2 the shim, its cap and the row's keys; 3 the reader and the texts; 4 the version, the README count, the sidecar (last, one bump; adcb9d8 is the model). 90 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says, and the readings

The review's problem: "hook latency, CLAUDE.md bytes per turn and record cost per landing are unmeasured" and "a `Write` spawns 8 processes; a `Read` spawns 5; none of them is measured". It says itself its facts can be stale, so the readings at 95acb37:

- `plugin/hooks/run` is `#!/bin/sh`, `/bin/sh` here is bash 3.2 (no `EPOCHREALTIME`); `date +%s%N` works on this Mac and on GNU; it `exec`s the tool on every event but the four Stop-likes and PreCompact, which already wait for it.
- `measure.py` already holds the engine's `rateLimits` in `<session>/measure.json` (S45), its shape checked by `admission.rate_limits`, and has `load`. Nothing new reads the engine: the row copies that.
- `ledger.append` writes exactly `LEDGER_KEYS` and refuses others, so the writer is the one strict place. `ledger.read` and `read_chains` are lenient. `tests/test_ledger.py` pins 19 keys.
- `observer/sources.py`'s `ledger()` reads named keys with `.get` and ignores the rest; its `verdict.py` reads only what that returns. No strict reader there. It lists `<root>/sessions`, never the root, so a new root file is unseen. The relay holds no reader of this ledger but a test's fixture.
- Baseline, 95acb37, the shim called from Python with a temp state root: a no-op tool p50 8.9 ms, the real CLI on PreToolUse p50 96 ms.
- `design/readme/source.md` is 16,382 bytes under a 16,384 ceiling: a new line there needs an equal trim, by rewording, no fact dropped.

## 2. Rulings

1. **The shim appends**, as the source says, after the tool ends: `date +%s%N` before and after, the difference in whole ms, one `printf` to `<state>/hooks.jsonl`, the state root picked as `config.state_dir` picks it, the wrapper's own `[ -e ]` shape, with no fork but the two `date`s and no lock. Any failure writes nothing and says nothing: no `date`, no `%N`, no state directory, a file that is not regular (a FIFO would hang), an unwritable file, an event that is not letters.
2. **The hook's exit and stdout do not move.** `exit` in a row is the tool's own, so a Stop an older CLI refused reads 2 there while the hook still exits 0. The shim stops `exec`ing, since it must outlive the tool: on a timeout's kill the tool finishes alone, as Stop's already does, and that call leaves no row. A tool that is not on PATH leaves no row.
3. **The bound.** `hooks.dispatch` stats the file on every hook call: at 1 MiB or more it renames it to `hooks.jsonl.1`, replacing the last. One generation kept, so at most 2 MiB plus lines racing a rename. Rotation lives in the CLI since a size in `sh` costs a fork. It is silent, and a CLI older than the plugin does not rotate, which is the state the README's install order already forbids.
4. **A row is `{"event","ms","exit"}`** and nothing else: no session, time, path, prompt or tool input. So `--since` does not filter it and it is not per session; the window is what the two generations hold.
5. **`claude_md_bytes`** (`harness.claude_md_bytes(cwd, env)`), at SessionEnd, on-disk bytes of each file once by real path: `CLAUDE.md` under `CLAUDE_CONFIG_DIR` or `~/.claude`; `CLAUDE.md`, `.claude/CLAUDE.md` and `CLAUDE.local.md` in the session's `cwd` and each ancestor; and `@` imports of those, to five hops, relative to the importing file, `~/` and absolute too, none inside a code span or fence. Not counted: managed policy, `.claude/rules/`, a subdirectory's file that loads on demand, auto memory, `--add-dir`, a plugin's context, what a hook adds. Capped at 64 files; a file past 1 MiB counts by size and is not scanned. Null with no usable `cwd` or on any error. It is the file state at the end, raw bytes, not tokens.
6. **`rate_limits`** is the session's last `measure.json` `rateLimits`, through `measure.stated_limits(sdir)`, null when absent or when the shape check refuses it. No second reader of the engine. `hooks.py` reaches it through `harness.stated_limits`, since M2's criterion 3 scans that file for any import of measure: the row is a record, and nothing that decides reads it.
7. **Both keys join `LEDGER_KEYS`,** written null when absent as every key is. Old rows read as before; the plain table and `--json` do not change for them. A failure in either never loses the row.
8. **The reader:** `report --hooks`, no new verb. Per event: count, p50, p95 (nearest rank, in ms), nonzero exits, over both generations; then one `claude_md_bytes` line over the rows `--since` leaves: the newest, p50, max, n. `--json` gives the same as an object. Neither source holding anything exits 2, as `--chains` does.
9. **Honesty:** the README says only this plugin's hooks are measured. Claude Code's own per-hook timing, if a debug log or transcript carries it, is a NICE lead, never built here.
10. **The version:** 2.0.0-alpha.34 in all five pins, one bump, last; the README count from the suite; the sidecar re-hashed by hand, as adcb9d8 did.

## 3. Interfaces (signatures, not prose)

- `harness.HOOKS = "hooks.jsonl"`, `harness.HOOKS_CAP = 1048576`; `harness.rotate(state) -> None`, never raises; `harness.read_hooks(state) -> list[dict]`, lenient; `harness.hook_stats(rows) -> dict`; `harness.hooks_table(stats) -> str`.
- `harness.claude_md_bytes(cwd, env) -> int | None`, never raises; `harness.claude_md_stats(rows) -> dict | None`; `harness.claude_md_line(rows) -> str`.
- `measure.stated_limits(sdir) -> list | None`; `harness.stated_limits(sdir)`, the same.
- `ledger.entry_for(m, *, project, profile, cwd, exit_reason, claude_md_bytes=None, rate_limits=None)`.
- `report --hooks [--json] [--since D]`.

## 4. Findings that name this row

None in this repo. The marketplace line in commons at alpha.34 is hq's, as is the hq record of the numbers.

## 5. Forbidden reads

Transcripts; `~/.local/state`, every part; relay ledgers; the review whole. agentik-observer's `observer/` by grep and `sed`, read only.

## 6. Report (at most ten lines)

The branch and sha; the gate id and exit; the measured overhead per hook call; what `claude_md_bytes` counts; anything that reads the row strictly; anything decided or left over.

## 7. Amendment 1

`design/packets/s49-measure-a1.md` (2026-10-31, refuter round 1 on a1fe45f): it overrides §2's rulings 1 and 2 and ruling 3's first clause. A file of its own under doclint's 9,216-byte ceiling, as s47's and s44's.
