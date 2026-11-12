# Packet g2b: the edit gates (g2 redesigned after the owner's test)

| item | value |
|---|---|
| from | the management sitting's coordinator, 2026-11-12, brief g2b (hq `history/sessions/BRIEF-2026-11-12-session-g2b-edit-gates.md` §5); design of record hq design/09 §7.2 "The edit gates" at hq 39e1a63; refuter r1: proceed |
| pin | `054cfc5` on `g2-instruction-guard` (g2, 2.0.0-alpha.82). Version 2.0.0-alpha.83 (the code), 2.0.0-alpha.84 (the session skill's paragraph, a later change under `plugin/`), 2.0.0-alpha.85 (review r1's F1 and F6). Worktree `.claude/worktrees/g2b-edit-gates`, branch `g2b-edit-gates`; `.venv`, `.venv-floor` linked from the main checkout. Its sister: agentik-decisions branch `g2b-edit-gates` (render and answer list what they write; the instruct skill's steps 6 and 7) |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state; no relay verb |
| may touch | `plugin/lib/claude_session/{instructionguard,hooks,cli,doctor}.py`; `.hygiene-allow` (three rows: the sibling name in this packet, the gate and its tests); `plugin/.claude-plugin/plugin.json`; `tests/test_g2b_gates.py` (new), `tests/test_g2_guard.py` (removed: its ask, run kind and argv reader are dropped), `tests/test_bare_machine.py` (the readers' table), `tests/test_cli.py` if the new verb needs it; `plugin/skills/session/SKILL.md` (its paragraph on the guard); `README.md`, `RUNBOOK.md`, `design/readme/{source.md,rendered.sha256}`; this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | the table in §3; `.venv/bin/python -m pytest -q tests/test_g2b_gates.py` green, and the same under `.venv-floor` (absent at the pin: red); `scripts/hygiene --require-private --commits main..HEAD` exits 0 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then each acceptance item green |

## 1. What the source says: the code at the pin

- `instructionguard.check` answers `ask` in a main thread and `deny` in a helper or a `-p` run for a built-in table of instruction paths, read through the launch line (`claude_argv`, the kernel argv walk); it reads no Bash line. `hooks.pre_tool_use` calls it once, for the four edit tools.

## 2. Rulings: the requirements (brief §5, design/09 §7.2)

- R1: a file is gated when a list names it: the checkout's tracked `.claude/edit-gates` (a path or glob a line, relative to the top level; `#` a comment; a line with `..` or a leading `/` ignored) or the user's `edit-gates` in `CLAUDE_CONFIG_DIR`, else `~/.claude` (lines absolute or `~/`). Both list files are always gated. Absolute and real paths are matched, case folded where the volume folds case. Every other file passes in silence, with no log line.
- R2: `deny` in every mode and run, the reason word for word: "agentik-session: `<path>` is gated: an edit of it is refused in every permission mode. Make the change through the `decisions:instruct` skill, which shows the owner the change and its cost and writes it only on the owner's yes. Do not write the file another way."
- The lane: `agentik session gates` lists what is gated here; `agentik session gates write <file> --from <draft> [--preview | --expect <hash>]`: preview prints the diff, the byte change and a hash and writes nothing; `--expect` writes atomically, keeping the mode, and refuses a changed file or draft, a changed generated-block line, a `.json` draft that does not parse, an ungated target.
- R3, g3 on Bash: a regex pre-filter, then `shlex`; targets of `>`, `>>`, `>|`, `&>`, `N>` (a heredoc's own redirect included), `tee`, `sed -i`, `perl -i`, `cp`/`mv`/`install` (last word or `-t`), one level of `bash -c`/`sh -c`, a literal `cd`, `python -c` literals beside `open(`/`write_` and a `python3 - <<EOF` body; a list file's removal (`rm`, `unlink`, `git rm`, `git checkout --`, `git restore`, `mv` from it) refused; fail open on `$`, a backquote, a glob, an unsplittable line.
- R4: fail open (an exception: `{}` and one `open` log line); no knob; the log and its cap; the doctor's `guard` row "on; N gated here; session S: D refusals, O let through on an error". Dropped: the launch-line reader (`claude_argv`, `headless`, `_procargs`, the sysctl) and `run_kind`; the log names a helper by `agent_id`.

## 3. Interfaces: the acceptance table (brief §5)

1. Each edit tool on a listed path, with and without `agent_id`, returns `deny` and the reason byte for byte; no answer is `ask`; an unlisted path returns `{}` and logs nothing; both list files are denied unlisted.
2. A worktree's own list applies; a symlinked or case-variant spelling matches on a case-blind volume; `..` and absolute lines in a repo list match nothing.
3. Bash: one test per §7.2 form denies on a gated target (`cat > CLAUDE.md <<EOF`, a `python3 - <<EOF` body); `rm`, `mv` from, `git checkout --`, `git restore` of a list file deny; `$X`, a glob, an open quote pass; `agentik decisions render --into CLAUDE.md` and `agentik session gates write` pass.
4. No call spawns a process or reads argv; a Bash line with no write word opens no file.
5. An exception inside the check returns `{}` and one `open` log line.
6. `gates write`: `--preview` leaves the bytes; a wrong `--expect`, a changed block line, bad JSON, an ungated target exit non-zero and write nothing; a good one writes and keeps the mode.
7. (agentik-decisions) `render --into` twice lists its target once; a target under `tests/fixtures/` is never listed.
8. Sign-off: the owner runs §7.2's seven steps under `auto` (held; not this packet's act).

Proof: `.venv/bin/python -m pytest -q tests/test_g2b_gates.py tests/test_hooks.py tests/test_doctor.py tests/test_cli.py tests/test_bare_machine.py` green, and under `.venv-floor`; the gate's `make check` exit 0.

## 4. Findings that name this row: ledger, NICE, forks

- hq entries 6 and 17 bind it. Live `auto`-mode behaviour is the owner's attended test (step 8); the wall starts no `claude`.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`.

## 6. Report

The hq hand-back `history/sessions/HANDBACK-2026-11-12-session-g2b-edit-gates.md`: each repo's tip, the acceptance table and its proof, the gate jobs and their exits, the owner's test step by step, what was not done.
