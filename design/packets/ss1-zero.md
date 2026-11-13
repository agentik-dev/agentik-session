# Packet ss1-zero: a new session reads 0% from its first moment

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief ss1 (a mend, level S2) |
| pin | `3490c08` on main (2.0.0-alpha.104). Worktree `.claude/worktrees/ss1-zero`, branch `ss1-zero`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only, once, last); no `claude`; no test reads live state (temp HOME, temp repo, a made-up session id); no relay verb |
| may touch | `plugin/lib/claude_session/hooks.py` (`session_start` and one new helper beside it; review 1, `user_prompt_submit`'s meter line); review 1, `plugin/lib/claude_session/doctor.py` (`_check_meter`), `plugin/lib/claude_session/measure.py` (`drift`), `tests/test_mod.py` (the module's band over the meter written); `tests/test_ss1_zero.py` (new); this packet; `history/sittings/2026-11-13-5-ss1-zero.md`; in the last commit alone, `plugin/.claude-plugin/plugin.json`, `README.md`'s and `design/readme/source.md`'s Status lines, `design/readme/rendered.sha256` |
| verify | `make check` through the gate queue, once, last |
| acceptance | §3; `.venv/bin/python -m pytest -q tests/test_ss1_zero.py` green, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin (baseline measured at `3490c08`)

- The owner's words: "How close are we to being able to install this on my work computer?" and "I want to use it today." A newcomer's first sight of the suite is the line above the first prompt. Today it says `no meter` and names a doctor, and the first command every page tells them to type, `/session:status`, exits 2.
- `hooks.session_start` resolves the session and writes `resolved.json`; only `_post_tool_use` writes `meter.json` (`meter.parse` over the transcript with `meter.limits_for` and `_policy`, then `meter.save`). Until the first tool call the session folder holds no meter.
- Measured at the pin, a temp HOME, a made-up session id, a temp repo, SessionStart over an empty transcript: `status` prints ``no meter for this session: PostToolUse has not run (see `agentik session doctor`)``, exit 2; the module's `bandLine` over the absent meter is `session: no meter · agentik-session doctor`; doctor's `meter` check fails `... meter.json absent: no PostToolUse has metered this session`. The same over an absent transcript, and over a resumed one of four turns.

## 2. Rulings: the requirements (brief ss1)

- R1 the first meter. SessionStart, once it has resolved the session and written `resolved.json`, writes that session's first `meter.json` by the path PostToolUse uses: `meter.parse` over the payload's `transcript_path` with `meter.limits_for` and the session's policy, then `meter.save`. A transcript absent, empty or unreadable is read as zero turns: the meter is still written, zone `clear`. On `source: resume` the meter says the transcript's turns. A meter already on disk is replaced only by a parse that succeeded.
- R2 the hook never breaks a session. Any failure of R1 is swallowed: SessionStart returns what it returns today. No new line reaches the model: `additionalContext` is byte for byte the pin's.
- R3 the readers stand. `bandLine`, `cmd_status` and `_check_meter` are not changed unless a test shows one cannot read R1's meter. `NO_METER` keeps its words and its two uses.
- R4 a helper and `claude -p`: where SessionStart resolves a session it writes the meter; where it returns early it writes none.
- R5 the tests first, each of lines 1 to 4 red at the pin, in `tests/test_ss1_zero.py`, under both venvs.
- R6 the version: the next free alpha at the pin, alone in the last commit, with the README's and its source's Status lines and the sidecar, by hand as the last version commit on main did.

## 3. Interfaces: the acceptance table, each a case of `tests/test_ss1_zero.py`

The writer is `hooks._first_meter(sdir, transcript_path, env)`, called last in `session_start`, after the context line is built, so nothing it writes can reach that line. An absent or unreadable transcript is parsed as `os.devnull` with a fresh state; the meter's `transcript.path` stays the payload's, its `inode` null. The band's line is drawn by the module itself, `bandLine` imported under node; a case skips where node or the module is absent.

| # | line | at the pin |
|---|---|---|
| 1 | SessionStart over an empty transcript, then `status`: exit 0, `0.0% context`, `0.0% turns`, `zone clear` | exit 2, `no meter for this session` |
| 2 | the same, then `bandLine` over the `meter.json` written: holds `ctx 0% · turns 0%`, neither `doctor` nor `no meter` | no meter written; `session: no meter · agentik-session doctor` |
| 3 | SessionStart over a transcript path that does not exist: as 1 and 2 | as 1 and 2 |
| 4 | SessionStart with `source: resume` over four turns: `status` says `(4/`, and the meter equals PostToolUse's over the same transcript, less `ts` | exit 2 |
| 5 | the session folder read-only once resolved: the output equals the pin path's, no meter, nothing raised; the hook's process over a meter path it cannot replace exits 0 with an empty stderr | the process exits 0; the in-process case red (no writer to patch) |
| 6 | `additionalContext`, empty, absent and resumed transcripts: equal byte for byte to the output with the writer a no-op | red (no writer to compare) |
| 7 | doctor's `_check_meter` after SessionStart, before any tool call: ok, `0.0% context, 0.0% turns, zone clear` | `meter.json absent` |
| 8 | `bandLine(null, false, now)` is `session: no meter · agentik-session doctor` | green |
| 9 | `make check` green through the gate queue | |

Besides: a meter on disk survives a resume whose transcript is gone (R1); `status` with no session folder still exits 2 (R3); a helper's SessionStart writes its meter and an early return writes none (R4).

## 4. Findings that name this row

- None at the cut.
- Review 1 (the coordinator's ruling; tests `test_review1_*`, each red at `c62445c`): F1, SessionStart's zero meter made the first prompt send the meter line the pin never sent; no meter line on a prompt while the meter's `turns` is 0 (R2 holds). F2, only a regular file is parsed, so a FIFO cannot hang the hook. F3 (R3 amended), doctor's `meter` check passes a zero-turn meter whose transcript is absent or not yet metered. F4 (R3 amended), `drift` is not comparable while `turns` is 0. The band's line moves to `tests/test_mod.py`, the one reader of the module's files.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger, no hq checkout beyond the brief.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done.
