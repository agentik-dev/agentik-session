# Packet hk1: a hook cut at its wall leaves a row; the helper rule reads a command word; one relay section

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief hk1-hook-rows (three findings of an advisor's leads that day, each reproduced); the owner's words below |
| pin | `d7e53a2` on main (gc1 landed). Worktree `.claude/worktrees/hk1-hook-rows`, branch `hk1-hook-rows`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb |
| may touch | `plugin/lib/claude_session/cli.py` (`cmd_hook`, `_report_hooks`), `harness.py` (the wall constant, `record_hook`, the cut counts), `hooks.py` (`_LAUNCHER` alone), `resolver.py` (`as_dict`), `doctor.py` (one conditional row), `tests/test_hk1_hook_rows.py`, the tests that pinned the removed copy, `RUNBOOK.md`, this packet, the sitting's record |
| verify | pytest under `.venv` and `.venv-floor` on the new file and the touched tests' files; `scripts/doclint`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `cli.cmd_hook` writes the row in a `finally` after `hooks.dispatch`; a default SIGTERM or a SIGKILL skips it, so a hook cut at its 5 s wall leaves no row and `report --hooks` cannot count it.
- `hooks._LAUNCHER` matched the launcher's names anywhere, path segments included, so a helper's `grep` or `git -C` in a checkout of this tool, with the word that follows, was refused.
- `resolver.Resolved.as_dict` added an `agent-relay` copy of `relay`; the relay warns on every file that holds both.

The owner's words, 2026-11-20: "continue with the charter", and, giving the sitting six workers, "to accelerate your work". The coordinating repo's entry 37, verbatim: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## 2. Rulings (brief hk1)

- R1, a cut hook leaves a row. In `cmd_hook`: on SIGTERM the hook writes its `hooks.jsonl` row with exit 143 and the time so far, then exits 143. Its own deadline is the hook's wall less 0.5 s, the wall read from one constant that a test holds equal to `hooks.json`'s `timeout` for every hook: when it fires, the hook writes its row with exit 124, prints nothing and exits 0, so the call passes as it does when the engine cuts a hook. Neither path raises or writes a partial line. A hook that ends in time is the pin's, in its output, its exit and its row.
- R2, the count. `report --hooks` shows cut hooks, the rows with exit 124 and with exit 143, by event. Doctor warns when the log holds a cut PreToolUse. No new verb or flag.
- R3, the helper rule's launcher is a command word: not inside a longer path segment, not a folder of a path, still the last name of a path that ends `/bin/<name>`. What the rule refuses once the launcher is matched is unchanged.
- R4, one section. `as_dict` no longer adds the `agent-relay` copy; `resolved.yaml` and `resolved.json` hold `relay` alone. The fallbacks that read the old section from a user's or a repo's file, and their doctor lines, stand.
- R5, what stands: every refusal's text, the hooks' outputs, the gate lists, the meter, `MAX_OUT`.

## 3. Interfaces: the acceptance table (baseline read at `d7e53a2`)

| # | line | at the pin |
|---|---|---|
| 1 | the real `cmd_hook` over a sleeping dispatch, TERM at 0.3 s: one row, exit 143, a plausible `ms`; the process exits 143 | no row; dies by the signal (-15) |
| 2 | the same with the deadline at 0.2 s through the constant: one row, exit 124; exit 0, empty stdout | no deadline: sleeps to the end |
| 3 | a hook that ends in time: row, output and exit as at the pin | the pin |
| 4 | the constant is each `hooks.json` `timeout` less 0.5 s | no constant |
| 5 | `report --hooks` over two cut rows shows them by event; doctor warns for a cut PreToolUse, not for a cut PostToolUse | no count; no row |
| 6 | the R3 table: four launcher lines refused, three path, grep and commit lines passed, two read verbs passed | the three path lines refused |
| 7 | `as_dict` holds no `agent-relay`; a repo file naming the old section resolves as at the pin, with its doctor line | the copy present |
| 8 | every test of the pin passes, but those that pinned the copy | |
| 9 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make stamp`, then `make check` green through the gate | |

## 4. Findings that name this row: the choices inside the rulings

- `harness.HOOK_WALL` maps each event to its `hooks.json` timeout in seconds; `harness.HOOK_DEADLINE` is the same map less `HOOK_MARGIN` (0.5 s), read by `cmd_hook` at the call. An event not in the map takes the PreToolUse wall.
- The deadline and the TERM handler are armed only for a call the shim measures (a start in `AGENTIK_SESSION_HOOK_T0`): a bare `hook` call, which writes no row, keeps the pin's behaviour.
- The cut paths write the row without flushing stdout and leave by `os._exit`, so nothing buffered is printed; a flag set before the normal row keeps a late signal from writing a second one.
- `report --hooks` keeps its table; one `cut:` line follows it only when a row was cut, and `--json` gains `cut`, `{event: {"124": n, "143": n}}`, empty when none.
- Doctor's `hooks` row appears only while `hooks.jsonl` holds a cut PreToolUse, as `warn`. The log has no session field (S49 Amendment 1), so the row reads the account's log, both generations.
- R3's pattern is the leads' trial with one addition: a relative `bin/<name>` standing as a word counts too, as it did at the pin.
- R4: the two tests of `tests/test_resolver.py` that pinned the copy (`test_defaults_alone`, `test_c6_the_old_relay_key_is_read_and_relay_wins`) now pin its absence. No `.hygiene-allow` row goes: `resolver.py` and `tests/test_resolver.py` still name the old key in the fallbacks that stand.
- R5: no open NICE row names any of the three findings, so none closes here.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
