# Packet rp7-guard: a rule of the guard table that denies a model `agentik issue send`

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief rp7 (S3), rulings R1 to R9 |
| pin | `fd0a435` on main (g10-push-guard's merge, alpha.135). Worktree `.claude/worktrees/rp7-guard`, branch `rp7-guard`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; `make` only through the gate queue; no `claude`; no relay verb; no test reads the live state or home; `agentik issue send` is never run, a test feeds the hook a payload; `shellreader.py`, `hooks.py`, `cli.py`, `plugin/hooks`, the manifest and the doctor unchanged |
| may touch | `plugin/lib/claude_session/lineguard.py`, `tests/test_rp7_guard.py` (new), `tests/test_g8_refusals.py` (`test_the_table`'s list alone), `.hygiene-allow` (beside its nearest kin, where needed), this packet, `history/sittings/2026-11-17-9-rp7-guard.md`; the version, the README's count and the sidecar by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_rp7_guard.py tests/test_g10_push_guard.py tests/test_g8_refusals.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `fd0a435`)

The owner: "...and approved by the user submitting the issue." The suite's `issue send` asks a person for a typed word on a terminal and refuses inside a Claude Code tool call. This rule is the same refusal one step earlier, at the hook, so a call made by reflex is denied with its reason before it starts.

The design's words (hq design/20 §3 item 16, for a rule of this kind): it is read through the reader, never matched as text, so a `grep` for the word passes; it stops a call made by reflex and nothing more: a script file and a variable in the verb's place pass, and an unread line passes. hq design/22 §3 item 8: the guard table gains a rule denying the door or the suite's launcher with `issue send` at the verb's position, in the main thread and in a helper.

The ledger, `DECISIONS.md` entry 11, verbatim: "**Three shell spellings are refused in every session.** The plugin's PreToolUse hook refuses three shell spellings in every session, on every install, with no entry of any repo arming them: `rm -r` on a bare variable, anywhere; `git init`, and a git identity being set, where the shell stands in a checkout and the line names no other place. A `cd` in the line is not trusted for the last two. Each refusal names the safe spelling, so the hook refuses a spelling and never the act." This rule is none of the three, so its reason does not cite it. Cited: hq entry 6 (the plugin repos' build conventions), hq entry 37 (made-up names in fixtures and this packet).

At the pin `lineguard.looks` passes unread every line with neither `git` nor `rm` (for a helper's, nor `gate`), so no line of R2 is read: the 19 lines of §3's line 1, each as a main thread's call and as a helper's, 38 payloads, are all passed. `tests/test_g8_refusals.py` holds 20 tests and `tests/test_g10_push_guard.py` 25: 45 pass under both venvs. The suite's verb: `agentik issue [new|show|strike WORD|drop SECTION|edit|reword FILE|send|discard]`, its flags `--dry-run`, `-y`, `--yes`, `--check`, `--web`, `--not-a-duplicate`, `--render`, `--json`, `-q`, `--quiet`, `--no-color`, none with an operand.

## 2. Rulings

- R1, R8: `("issue", "product", _issue, <matches nothing>)`, sixth in `RULES`, in neither `_GIT_RULES` nor `_HELPER_RULES`: judged with no `cwd`, in the main thread and in a helper. A `Cmd` whose launcher word, by its base name, is `agentik` (past its leading flags, as g10 reads the door) or `agentik-suite`, through a python or a shell that runs a script word as g10 reads it, has `issue` next and `send` as the next word after it that does not open with `-`. The door's reading is g10's, split into a shared function; a word the shell expands is no verb (g10's `veil` off).
- R2, R3: read through `shellreader.commands`, which opens `env -u`, `command`, `exec`, an assignment, a list and `sh -c '...'`. Passed by design (design/20 item 16's limit for this kind of rule): a script file that runs the line, a variable in the verb's place, an unread part.
- R4, R7: the reason, "the issue rule, a rule of the agentik-session plugin, in every session: this files a public issue, which wants a person's typed word on a terminal. Hand the user the line to run in a terminal of their own." It cites no entry; `PLUGIN` and the three product reasons keep their text.
- R6, the first look: a line is read also when it holds both `issue` and `send`, case-blind (for a helper's, once its quotes and backslashes are out). Newly read: a main thread's line holding both words and neither `git` nor `rm` nor (for a helper) `gate`, as `gh issue comment 1 --body 'send it'`. Such a line no rule refuses passes as before, but an error in its reading now refuses it (g8's R14).
- R9: `-h` or `--help` anywhere after `issue` passes; `--dry-run`, `--web` and every other flag around `send` do not.

## 3. Interfaces and acceptance

- No interface moves: `looks(command, helper=False)`, `check`, `failed`; the mark and the log line carry the name `issue`.

| # | line | at the pin |
|---|---|---|
| 1 | each command of R2, as a Bash payload: denied with R4's reason; marked as a helper's: denied | 0 of 38 denied |
| 2 | each command of R3: not denied by this rule | passes |
| 3 | `tests/test_rp7_guard.py` green; the 45 tests of the two files unchanged and green, but `test_the_table`'s list | 45 green |
| 4 | `make check` through the gate queue: green | not run at the pin |
| 5 | a `.hygiene-allow` line, where needed, beside its nearest kin | none |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

The wall's: the live state and the real home; `agentik issue send` is never run.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-9-rp7-guard.md`: the choices inside the rulings are in its handover.
