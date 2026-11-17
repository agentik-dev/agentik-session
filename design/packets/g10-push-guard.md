# Packet g10-push-guard: a helper's push is refused in a tree that says who pushes

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief g10-push-guard (S1), rulings R1 to R8; review 1's ruling, its fix 1 to 10 (§2a) |
| pin | `fd8f3af` on main (g8-refusals' merge, alpha.133). Worktree `.claude/worktrees/g10-push-guard`, branch `g10-push-guard`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; `make` only through the gate queue; no `claude`; no relay verb; no test reads the live state or home; `shellreader.py`, `hooks.py`, `cli.py`, `plugin/hooks`, the manifest and the doctor unchanged |
| may touch | `plugin/lib/claude_session/lineguard.py`, `tests/test_g10_push_guard.py` (new), `tests/test_g8_refusals.py` (R7's words alone), `NICE_TO_HAVE.md` and `history/NICE-overflow.md` (R8, fix 10), `.hygiene-allow` (fix 9, the rows ruled), this packet, `history/sittings/2026-11-17-6-g10-push-guard.md` and `-7-g10-push-guard-fix.md`; the version, the README's count and the sidecar by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_g10_push_guard.py tests/test_g8_refusals.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `fd8f3af`)

The design's words (hq design/20 §3 item 15): "In a checkout armed by the title Pushes, a helper's call, one whose payload carries `agent_id`, is refused when a command of the line is `git push` or its plumbing (`send-pack`, `http-push`, `subtree push`), or the session tool's `gate publish`, or its `gate land` with `--push`, each matched at the verb's position through the reader. The reason: a helper's environment reads as a main sitting to the verb's own check, and `agent_id` is the one mark Claude Code sets that a helper cannot drop." And design/19 §5: "a Bash call that carries an `agent_id` and runs `git push`, `gate publish`, or `gate land` with `--push`, under any spelling of the session tool, is refused."

At the pin `lineguard.RULES` holds four rules (`rm`, `init`, `identity`, `sweep`); `looks` passes unread a line with neither `git` nor `rm`, so `agentik session gate publish` is never read. `hooks.pre_tool_use` already calls `lineguard.check` for every Bash call, a helper's included; it needs no change. `PLUGIN` reads "a rule of the agentik-session plugin, in every session"; the repo's ledger, `DECISIONS.md` entry 11, is on main.

The parser, measured at the pin under 3.12.7 and 3.9.6 (`cli.build_parser().parse_args`): `gate land r b s m` with `--p`, `--pu`, `--pus` or `--push` sets `push`; `--push=1`, `--push=` and `--pus=x` exit 2 ("ignored explicit argument"); `-p` exits 2; `--push` after a `--` is a positional and sets nothing. `gate pub`, `gat publish` and `gate lan` exit 2: a verb is never abbreviated. The tool's global options (`-h`, `--version`) and `gate`'s (`-h`) take no operand and exit before a verb. `land`'s `--session` and `--wall` take one.

## 2. Rulings

- R1: `("push", "Pushes", _push, _loose_push)`, fifth in `RULES`; it judges a payload whose `agent_id` is truthy and no other, and is skipped, as the git rules are, with no absolute `cwd`.
- R2: a `Cmd` named `git`, case-blind, whose subcommand is `push`, `send-pack` or `http-push`, or `subtree` with `push` among its words; the checkout by the sweep's own finding (`_target` over `heres`, followed and beside), without the sweep's three passing spellings of `-C`.
- R3: the session tool by its command word (`agentik-session`, `claude-session`, `agentik` then `session`, case-blind, a path's base name), or by an interpreter's script word (a `python` name, or `sh`, `bash`, `zsh`, `dash` with a script file) or `python -m claude_session`. Past leading option words, `gate`; past option words, `publish`, or `land` with one of `--p`, `--pu`, `--pus`, `--push` among its words before a `--`. The checkout: each folder the command may run in, and the repo operand where it is a path (it holds `/`, or is `.`, `..` or opens with `~`).
- R4, R5, R6 as the brief; R7 `PLUGIN` names entry 11; R8 five NICE rows.

## 2a. Review 1's fix

The bound: the push rule holds what a helper writes in good faith and what one cheap reading closes, and it fails closed for a helper alone. A line built to hide the verb is held by the brief's wall, not by this rule. Every change is behind `agent_id`: a main thread's line is decided, marked, logged and looked at exactly as at `fd8f3af`.

- Fix 1 (F1 to F3): a command that is no printer has each word whose base name is `git`, `agentik`, a tool name, a python or a shell judged, with the words after it, as that command (`timeout`, `xargs`, `find -exec`, `caffeinate`, `noglob`, `gate run`'s argv, `function f {`'s body). A word with a space never starts one. The printers, whose words are data: `echo`, `printf`, `print`, the greps (`grep`, `rg`, `ag`, `ack`), `sed`, `awk`, `cat`, `head`, `tail`, `less`, `more`, `wc`, `sort`, `uniq`, `tee`, `ls`, `test`, `[`, `[[`, `:`, `true`, `false`, `man`, `which`, `type`, `whence`, `where`, `help`, `pbcopy`, `say`, `logger`, `jq`, `printenv`, the declarations, `read`, `alias`, `basename`, `dirname`, `realpath`, `readlink`, `cut`, `tr`, `diff`, `cmp`. Any other command's words are read, so `xargs echo git push` refuses. `shellreader.py` does not change.
- Fix 2 (F4): a word at git's subcommand place, or the tool's `session`, `gate`, verb or flag place, holding `$`, a backtick, a brace list or a space (the reader's text of a backtick substitution) is the push.
- Fix 3 (F5): a helper's `looks` also reads the line with `'`, `"` and `\` taken out.
- Fix 4 (F7): the push judges the git dir (`GIT_DIR`, `--git-dir`, else the folder after `-C`), never the work tree; the sweep's finding is unchanged.
- Fix 5 (F9): `-m claude_session.<x>` reads as the tool. Fix 6 (L1, F10): a bare operand is resolved by `land.resolve_repo` (imported) and judged with the cwd; `$HOME`, `${HOME}` in `-C`, `--git-dir`, `GIT_DIR`, a `cd` or `pushd` word and the operand read from the environment.
- Fix 7 (L9): the loose judge finds each part once per segment, linear. Fix 8 (L10), measured in `plugin/bin/agentik`: the door takes no option before a tool's name (`--version`, `-h`, `--help` stand alone; another leading flag hands the whole line to `agentik-suite`), so flags before `session` are read past.
- Fix 9, 10: the allow rows ruled; NICE rows n286 to n296.

## 3. Interfaces and acceptance

- `lineguard.looks(command, helper=False)`; `check` and `failed` pass `helper` from the payload's `agent_id`. No other interface moves.

| # | line | at the pin |
|---|---|---|
| A1 | helper, armed checkout, `git push`: one deny, R6's words, the mark `push`, one `deny` log line with `rule: ["push"]` | passes |
| A2 | the same line with no `agent_id`: `{}`, no mark, no log line | passes |
| A3 | helper, a checkout no file arms: passes | passes |
| A4 | helper in an open folder, `git -C <armed> push`, `GIT_DIR=<armed>/.git git push`, `T=<armed>; git -C "$T" push`: each refused | passes |
| A5 | `git send-pack`, `git http-push`, `git subtree push --prefix=x r b`, `git push --dry-run`: refused; `git fetch`, `git remote -v`, `git subtree pull`: pass | passes |
| A6 | each spelling of R3 with `gate publish`, and with `gate land r b s m --push`: refused; `gate land r b s m`, `gate status`: pass | not read |
| A7 | R4's quoted and data forms pass; `eval "git push"` and unread `sh -c` text refused where the shell stands armed | passes |
| A8 | a main thread's `agentik session gate publish x`: `looks` is false | not read |
| A9 | R7: the three product refusals read "entry 11 of agentik-session's DECISIONS.md" | the old words |
| A10 | the whole suite green; no test of the four rules changes but for R7's words | green |
| B1 | every pass line of review 1's F1 to F5, F7 (first group), F9's `-m`, L1, F10's `$HOME` lines refused with the mark `push`; F7's reverse lines pass (A4's `--work-tree` line moves to them) | passes |
| B2 | the review's "What held" lines decide as they did | held |
| B3 | a main thread's every probe line: the pin's decision, mark, log and `looks` | held |
| B4 | 16 KB of unread text, with and without the push words, judged in under 0.2 s under both venvs | 8 s |
| B5 | `tests/test_g10_push_guard.py`, `tests/test_g8_refusals.py` green under both venvs; the check green | red at hygiene |

## 4. Findings that name this row

None at the pin. Review 1 of the first build: ten findings and eleven leads; §2a holds the ruling's fixes, the rest are NICE rows n286 to n296.

## 5. Forbidden reads

The wall's: the live state and the real home (each probe in a temp home).

## 6. Report

The sitting's record, `history/sittings/2026-11-17-6-g10-push-guard.md`: the choices inside the rulings are in its handover.
