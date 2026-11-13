# Packet h4: a helper's end closes its calls, the relay's limit clears the check's wall, the mix's prices are the page's

| item | value |
|---|---|
| from | the hq coordinator, brief h4 (row `h4-hardening`), 2026-11-12; NICE n51, n57, n85 (and n25 as stale) |
| pin | `8a4b593` on main (mt1 and t2 merged, 2.0.0-alpha.93). Worktree `.claude/worktrees/h4-hardening`, branch `h4-hardening`; `.venv`, `.venv-floor` linked from the main checkout. Phase 1 ends at the commits: no version bump, no merge, no gate job (phase 2, on the coordinator's word, bumps to the next alpha after main's) |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads live state or writes the live home; no relay verb, and the relay is not run (its read of the key is its own code's); `chain.py` unchanged; no old call file swept; in `hooks.py` only `_open_call`, the new handler, `HANDLERS` and `SILENT` |
| may touch | `plugin/lib/claude_session/{hooks,doctor,rules}.py`; `plugin/lib/claude_session/reconcile/__init__.py` (the docstring); `plugin/hooks/{hooks.json,run}`; `.claude/agentik/config.yaml` (new); `Makefile` (the `check` comment); `tests/test_h4_hardening.py` (new); the hook set's pins in `tests/{test_doctor,test_precompact,test_mod,test_s49,test_wfg,test_bare_machine}.py`; `tests/test_r1.py` (R4's two numbers); `RUNBOOK.md`; `NICE_TO_HAVE.md`; this packet; `history/sittings/2026-11-13-2-h4-hardening.md` |
| overlap | `hooks.py` and `rules.py` with g5, pl1 and h5 (other functions); `plugin.json` and the status line with every row (phase 2) |
| verify | phase 1: pytest under `.venv` and `.venv-floor` on the touched files; phase 2: the gate queue's `make check`, once, last |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_h4_hardening.py` green and under `.venv-floor` (red at the pin); every other test green, changed only for R4's numbers |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then each ruling group with its tests |

## 1. What the source says: the code at the pin

- n51. A helper's PreToolUse (`agent_id` `agent-aaa`, `tool_use_id` `toolu_probe01`) writes `sessions/<sid>/calls/toolu_probe01` as `{"at": …}` (`_open_call`). `hook SubagentStop` exits 2, `invalid choice: 'SubagentStop'` (argparse's `choices=sorted(hooks.HANDLERS)`, cli.py); `hooks/run SubagentStop` over a launcher that prints `{}` and exits 2 exits 2 with `{}` on stdout, since the event is not in the shim's fire-and-forget case. The file stays, and `chain._ready` holds on it until `STALE_CALL` (1200 s). Measured under both venvs.
- n57. `git ls-tree -r main --name-only .claude` lists `.claude/respeak/config.yaml` alone; `resolver.resolve` on the checkout gives `relay` `{enabled, queue, merge}` (the shipped defaults) and no `verify_seconds`, so a relay row's verify line is cut at the relay's default, 900 s. The check's wall is 1800 s (`--wall 1800`, the owner's "Raise to 1800 s", commit `f7c6ebc`).
- n85. `rules.mix({"shares": {"opus": 1}})["prices"]`: fable 8/40/10/0.8, opus 5/25/6.25/0.5, sonnet 3/15/3.75/0.3, haiku 1/5/1.25/0.1 (input, output, cache write, cache read per MTok); `reconcile.weights()` 1/5/1.25/0.1. The pricing page of platform.claude.com, read 2026-11-12: Fable 5.2 8/40/10/0.20, Opus 5.5 4/20/5/0.20, Sonnet 5.5 2/10/2.50/0.10, Haiku 5.5 (prompts up to 100,000 tokens) 0.10/0.50/0.125/0.01.

## 2. Rulings: the requirements

- **R1, the event.** `SubagentStop` is registered in `hooks.json` in `Stop`'s shape (no matcher, timeout 5) and joins `HANDLERS` (both spellings), `SILENT` and `doctor.HOOK_EVENTS`. In `hooks/run` it joins the fire-and-forget case: its stdout would be read as a decision and an exit 2 would hold the helper's stop, and a launcher older than the plugin refuses the event with exit 2.
- **R2, the call file.** `_open_call` writes `{"at", "agent_id"}`, the id only when it is a string `_SID` matches. The handler, for a payload whose `agent_id` is id-shaped and whose session directory exists (no fallback id), unlinks each file under `calls/` whose JSON object's `agent_id` equals it. Another helper's file, one with no `agent_id` (an older plugin's), one that does not parse and a directory are left; the stale bound still passes them. It writes no stamp and never raises.
- **R3, the relay's limit.** A new tracked `.claude/agentik/config.yaml`: a comment line, then `relay:` with `verify_seconds: 1920`, the check's wall plus two minutes, so `bounded`'s own stop is the one a row reads. A test parses `--wall N` from the Makefile's `check` recipe and the key with `yamlsubset`, and fails unless `N + 60 <= verify_seconds <= 3600` (the relay's bound). The Makefile's `check` comment names the file.
- **R4, the prices.** `MIX_PRICES` becomes fable (8, 40), opus (4, 20), sonnet (2, 10), haiku (0.10, 0.50). A new `MIX_READ` (fable 0.025, opus 0.05, sonnet 0.05, haiku 0.1) replaces the one 0.1 in `mix`; the cache write stays 1.25 for all. A user's `prices` keeps its rule: a given `input` scales that family's cache prices by its own multipliers; a given `cache_read` or `cache_write` wins.
- **R5, what follows.** `reconcile.weights()` keeps its code and reads opus's ratios; its docstring and `tests/test_r1.py`'s two numbers follow (cache read 0.05). Nothing rewrites a ledger's `spend` lines or `mix.json`: spend is cumulative USD per session, so a session that spans the update counts low until its login-week rolls.
- **Records.** RUNBOOK's two event lists gain SubagentStop; n25, n51, n57 and n85 leave `NICE_TO_HAVE.md` (n25 as stale: the wall has been 1800 s since `f7c6ebc`). The README is not re-rendered.

## 3. Interfaces: the acceptance table (`tests/test_h4_hardening.py`)

| # | line | at the pin |
|---|---|---|
| 1 | `hook SubagentStop` on a helper's payload: exit 0, empty stdout; `hooks.json` holds it in `Stop`'s shape; `doctor.HOOK_EVENTS` names it | exit 2, `invalid choice` |
| 2 | a helper's PreToolUse, then its SubagentStop: the file held `agent_id`, `calls/` is empty | the file there, `{"at"}` alone |
| 3 | two helpers' open calls, one's SubagentStop: the other's stays; a file with no `agent_id`, a non-JSON one, a directory: left, exit 0 | no handler |
| 4 | `_ready`, a marker, an ended turn, one open call 30 s old: False; after that helper's SubagentStop, True once `settle` has passed | False until 1200 s |
| 5 | `hooks/run SubagentStop` over a launcher that prints a line and exits 2: exit 0, nothing on stdout | exit 2, `{}` |
| 6 | no `agent_id`, one not id-shaped, a session with no directory: nothing removed or created, exit 0 | no handler |
| 7 | the repo resolves `relay.verify_seconds` 1920 with no unknown key; the tie is red with the key at 1800 or the wall at 1900 | no file |
| 8 | `rules.mix({"shares": {"opus": 1}})["prices"]` is the page's four rows | the pin's four |
| 9 | `prices: {opus: {input: 10}}`: cache read 0.5, write 12.5; `{fable: {cache_read: 0.8}}`: 0.8 | read 1.0 |
| 10 | every other test green, changed only for R4's numbers | the touched set: 812 passed (`.venv`), 809 passed, 3 skipped (`.venv-floor`) |

## 4. Findings that name this row

- No agentik-session ledger. Bearing, uncrossed: the hq's entries 6 (3.9 floor, stdlib) and 17.
- Owed by the coordinator, not buildable here: whether Claude Code fires SubagentStop for a helper a rejection ends (a scratch session after the install).

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers and the relay's code.

## 6. Report

The hq's record: the head sha, the acceptance table with each line's exit, the choices made inside the rulings.
