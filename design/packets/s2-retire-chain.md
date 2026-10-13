# Packet S2: retire the fork-and-resume chain and the window sampler (D6)

| item | value |
|---|---|
| from | `design/overhaul-r1.md` §1.2 and §1.3, D6 in §7; `bugs/2026-09-12-overnight-window.md` §Summary only. The builder reads THIS packet and those sections, not the brief |
| pin | claude-code-session `main` at S1's merge sha; branch `s2-retire-chain`, worktree `../claude-code-session-wt-s2` |
| wall | this repo only; no push; no `--amend`; no other repo read |
| may touch | `claude_session/schedulers/` (delete), `claude_session/runner.py`, `claude_session/reset.py` (delete), `claude_session/launch.py`, `cli.py`, `hooks.py`, `session.py`, `budget.py`, `config.py`, `store.py`, `render.py`, `model.py` (remove what served the chain and the five-hour window; keep §1.3), `install-wrapper.sh` (delete if it serves only the scheduled job, else trim), `tests/` (delete the chain's tests; adjust the rest; add none beyond what a removal needs), `SKILL.md` (the trigger phrases about windows and scheduled runs), `README.md` (delete the sections and rows that describe the chain: "Scheduling", the job commands, the window arithmetic; rewrite nothing else), `RUNBOOK.md` (delete §5; trim §4), `.hygiene-allow` (drop entries that no longer apply). `pyproject.toml` version unchanged (2.0.0 is S3's) |
| acceptance | `make check; echo $?` reads 0; `test ! -e claude_session/schedulers -a ! -e claude_session/runner.py -a ! -e claude_session/reset.py; echo $?` reads 0; `git grep -n -i -E 'fork-session\|launchd\|systemd\|StartCalendarInterval\|resets_at\|next window' -- claude_session tests SKILL.md README.md RUNBOOK.md \| wc -l` reads 0; `make test 2>&1 \| tail -1` reports the passed count and 0 failed; `claude-session start frontier --dry-run` prints one `claude` command line with no `--resume` |
| budget | 80 turns, 100k context; commit per item; checkpoint at 80%; never push, amend or rebase |

## 1. What the source says (quoted)

overhaul-r1 §1.2: "The fork-and-resume chain, all of item 4, and the sensor of item 3. The 2026-09-12 window measured four defects and every one is structural, not a bug to fix". "Retired with it: the five-hour usage-window model as the primary budget (percent of the window used); the `budget` verb's window arithmetic; the 'queue this for the next window' and 'what did the scheduled run do?' skill triggers; `install-wrapper.sh` where it exists only to serve the scheduled job." §1.3: "Profiles (the six, renamed from configurations, now the top-level object, §2.1); launch by flags only, nothing in `settings.json`, `--dry-run`; the session-scoped overlay and `--save`; budget as a signal with its four postures and the cadence that tightens by zone, now driven by the sitting's own two ceilings; the PreToolUse spawn gate under `ask` and `deny`; the stdlib rule; the fake-claude test suite and its 184 tests, minus the chain's."

## 2. Rulings

D6 (recommended retire whole; the owner's word on D6 is read from `design/overhaul-r1.md` §7 at the pin: if the line still reads "Recommend", the packet proceeds on the recommendation and the report says so). R25-87: the two ceilings replace the window. The rename "configurations" to "profiles" is S3's, not this packet's: this packet removes, it does not rename.

## 3. Interfaces (signatures, not prose)

- After this packet, `claude-session` has exactly these verbs: `start <profile> [--dry-run]`, `config {list,show,new}`, `set <knob> <value> [--save]`, `budget` (the zone and cadence only: no window percent, no reset time), `checkpoint`, `hook <event>`. `schedule`, `resume`, `run`, `reset`, `jobs` and any verb that named the next window are gone, and `cli.py` lists no alias for them.
- `budget.py` keeps `Policy`, `zone_for`, `effective_policy`, `reserve_floor`; `Sample`, `current_sample`, `seconds_left`, `resets_at` are removed with their tests. The zone's input becomes a fraction `used_pct` the caller computes; S4's meter is the caller. Until S4 the hooks compute `used_pct` from nothing and report the zone as `unknown`, printing nothing: the hooks stay wired and silent.
- `hooks.py`: `session_start` loses the run notice (defect 4); `user_prompt_submit` keeps the cadence nudge on a `checkpoint` counter, not on window samples; `pre_tool_use` keeps the spawn gate keyed on the zone; `session_end` keeps nothing the chain wrote.
- README: sections deleted whole, not paraphrased; a one-line note under "Budget as a signal": "The sitting's own ceilings drive the zones (see design/overhaul-r1.md)". RUNBOOK §5 deleted; §4's window paragraphs deleted.

## 4. Findings that name this row

bugs/2026-09-12 §Summary, the four defects, each retired here rather than fixed: 1 (agents killed at the handoff), 2 (no sample after the roll), 3 (fork is not resume), 4 (stale notice). research §2: the session repo has 28 test files; the count after the removal is a report line. The 09-12 bug record stays in `bugs/` as history, untouched.

## 5. Forbidden reads

Every other repo; `~/.claude/projects/`; the brief; `design/overhaul-r1.md` beyond §1 and §7's D6 line; `bugs/2026-09-12-overnight-window.md` beyond §Summary; any file over 8 KB whole.

## 6. Report (capped: one table, at most five bullets, under 1,500 words)

The table: each acceptance line, its exit and last output line. Bullets: files deleted and lines removed (counts); the test count before and after; verbs remaining; any place the chain's removal left a hook printing something (it must print nothing until S4); what was left undone. The last line: the branch and its head sha.
