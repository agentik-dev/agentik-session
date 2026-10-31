# Packet sc1: the bare-machine proof

| item | value |
|---|---|
| from | agentik-hq HANDOFF 17, build 2 of the Fable review; `~/code/agentik-hq/design/04-self-contained-plugins.md` §7 item 1, the record of the change, refuted once; hq entry 6 at a 3.9 floor |
| pin | 8ed5667 (main, alpha.37); worktree `.claude/worktrees/sc1-proof`, branch `sc1-proof`, cut, its `.venv` a link |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`, `claude` but `claude plugin validate`; a test or proof never writes under the live `~/.local/state` or the real `~/.claude`; no relay verb, no relay binary built or run; no `pkill` by name or pattern; a Python probe needs PYTHONPATH=<worktree>; **no code moves, no plugin bump, no install** |
| may touch | `claude_session/cli.py` (the argparse fix), `claude_session/doctor.py` (the floor), other non-test code only under §4's count, `tests/` (tests passing `-P` or expecting the baked venv), `Makefile`, `.gitignore`, `scripts/bare-proof` (new), `NICE_TO_HAVE.md`, `README.md` and the sidecar only if the suite's count moves them, this packet, the charter |
| acceptance | §3's table, each row's figure in the report; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet as `design/packets/sc1-proof.md`, committed first; 1 the argparse bug, a test first; 2 the doctor's floor and the tests; 3 `.venv-floor`; 4 `scripts/bare-proof` and its run. 120 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

Read first, by sections, never whole (`/session:read`): design/04 §2, §7 (its first paragraph, the bare-machine test and item 1), §8, §9, §12; then `~/code/agentik-research/research/synthesis/tools-session.md`.

## 1. What the source says: what is already measured (design/04 §2), not to be taken on trust

Session under 3.9.6: 1953 pass, 49 fail: 20 the doctor's floor, 14 one argparse difference, 12 `scripts/bounded`'s 3.11 `process_group=` (a dev tool, never run time), 3 pass `-P` or expect the baked venv. Those figures are from before S49 and S50; read them again.

**The real bug.** Before 3.12 a `nargs="*"` positional after an option is refused, so `gate run <repo> --label t -- cmd` and `charter close --exit X FILE` exit 2 under 3.9.

## 2. Rulings

1. **The argparse fix** keeps today's argv forms on every interpreter; a test runs both named forms and the 36 forms' spirit (any positional, before and after an option) under the floor. Whether by `parse_intermixed_args`, or by the parser's shape, is the builder's call, logged in one sentence; it must not change a form 3.12 accepts today.
2. **The floor:** the doctor passes 3.9 and refuses below. `pyproject.toml`'s `requires-python` moves to `>=3.9` if it says otherwise; that is not a plugin bump.
3. **`.venv-floor`:** built by `/usr/bin/python3 -m venv` with what the suite needs, by a new `make venv-floor`, in the main checkout; a worktree links it there, as with `.venv`. `.gitignore` gets a line with no trailing slash, so a link matches: `scripts/land` exempts only `?? .venv` by name. The worktree's own link is the builder's to make; the main checkout's build is the builder's too, it is ignored and writes no tracked path.
4. **`make test-floor`** runs the suite under `.venv-floor`, `tests/test_bounded.py` excepted. It stays out of `make check` in this packet (the wall is 840 s and the suite is the gate's largest cost); sc2's bare-machine test is what joins the suite. Reversible, decided here.
5. **`scripts/bare-proof`**, stdlib, under `/usr/bin/python3`: `git archive HEAD plugin` into `$T/.claude/plugins/cache/agentik/session/<version>/`, env exactly `HOME=$T`, `PATH=/usr/bin:/bin`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, a decoy package in the cwd. No clone path, no venv, no launcher. Since sc1 moves no code, the mock also needs the package: `git archive HEAD claude_session` into `plugin/lib/` of the mock, a four-line runner `plugin/lib/agentik-session`, and a mock `plugin/bin/agentik-session` holding §2's launcher lines, so that the hook shim under test finds what sc2 will ship. The launcher's flags are design/04 §2's, verbatim: `-I -X pycache_prefix=...`. The real shim's PATH lookup finds it through a `$T/bin` on PATH or an edit in the mock's copy, the builder's call, in one sentence in the report; never an edit of the repo's shim.
6. **The transcript:** `--transcript <path>`, default the newest file over 1 MB under `~/.claude/projects`, copied into `$T` at run time, its contents never printed, never committed. **The charter** runs in a temp git repo.
7. **Timing is from outside the shim**, 25 hooks per interpreter on the same input, 3.9 against 3.12, median and p95. `AGENTIK_PYTHON` picks 3.12: `.venv/bin/python`.

## 3. Interfaces: the acceptance table

| what | reads |
|---|---|
| suite under `/usr/bin/python3` | `make test-floor` green, `test_bounded.py` excepted; the count quoted |
| the two forms | `gate run <repo> --label t -- true` and `charter close --exit X FILE` exit 0 under 3.9, in the proof; state under `$T` |
| ten events | each exits as the shim's rules say, SessionStart's stdout valid JSON |
| admission | `agentik-session admission record` exits 0 and writes its line (admission runs in the mod, `session.ts:229`, not the ten hooks) |
| no clone path | none anywhere under `$T`, by a recursive grep; the copied transcript itself is excepted, and any file that quotes it is named in the report |
| bytecode | under the prefix after the first run, and none beside the sources |
| latency | median and p95, 3.9 against 3.12; the proof exits nonzero past §8's bar: median over 1.25 times, or p95 over 2.5 s |
| validate | `claude plugin validate` of the mock reads as the live plugin's: today 10 warnings on both; the two outputs diffed |
| live state | a snapshot of `ls -la ~/.local/state/claude-code-session/` is not needed: the proof asserts `HOME=$T` reached every child by a sentinel test, and fails if anything wrote outside `$T` |

## 4. Findings that name this row: the stop (design/04 §8)

This slice proves or kills the idea. Stop and report, committing what is there, on any of: a difference needing a design change rather than a small fix; more than five changes to non-test code beyond the known bug (count them in the report); the latency bar missed; a state break an additive rule cannot cover. A stop is a result, not a failure: the report says which and quotes the figure.

## 5. Forbidden reads

Transcripts' contents (the proof copies one by path); `~/.local/state`, every part; relay ledgers; the review whole.

## 6. Report (at most fifteen lines)

The branch and sha; the gate id and exit; each row of §3 with its figure; the non-test change count; the go or the stop against §8; anything decided or left over.
