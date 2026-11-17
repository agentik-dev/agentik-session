# Packet g8-refusals: four stray-write refusals in the hook, read through the one reader, each with its mark

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief g8-refusals (S1), rulings R1 to R19; question 53 answered "On everywhere" |
| pin | `ef0ba32` on main (is2-first-read's merge; `g8a-reader-parts` merged at `ad8029a`). Worktree `.claude/worktrees/g8-refusals`, branch `g8-refusals`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; `make` only through the gate queue; no `claude`; no relay verb; no test reads the live state or home; `shellreader.py`, `unattended.py`, `plugin/hooks`, the manifest and the doctor unchanged; not `install.py` nor `cli.py` (another row's) |
| may touch | `plugin/lib/claude_session/lineguard.py` (new), `hooks.py` (one block in `pre_tool_use`), `instructionguard.py` (`log`'s `rule` argument), `tests/test_g8_refusals.py` (new), `tests/test_g2b_gates.py` (the source scans' list), `NICE_TO_HAVE.md` (a row, by `make stamp`'s numbering), this packet, `history/sittings/2026-11-17-2-g8-refusals.md`; the version by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_g8_refusals.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `ef0ba32`)

The owner, 2026-11-13, question 49: the suite's guards live in the session plugin; design/20 §3 items 7 to 13 settle what moves: four refusals a machine's own hook makes today, rebuilt on the one reader. Question 53, answered 2026-11-17: "On everywhere": the `rm`, `git init` and identity rules hold in every session.

At the pin `hooks.pre_tool_use` (`hooks.py:690`, not `:611` as the brief has it) refuses a helper's charter write, then a spawn by the spawn rule, then an edit or Bash write of a gated file (`instructionguard.check`, failing open). No rule judges a sweep, a recursive `rm` of a variable, a `git init` or an identity set. `instructionguard.log` writes six fixed keys. `shellreader.commands` gives `([Cmd], [Unread])`; a `Cmd` carries no subshell scope.

## 2. Rulings

- `lineguard.RULES`: rows `(name, armed, judge, loose)`. `rm`, `init`, `identity` armed `product`; `sweep` armed by the title `Commits`. Question 53's other answer is three cells, `product` to `Stray writes`.
- R5's first look; R6's folder (the payload's absolute `cwd`, a `.git` entry walked up from the real path); R7's arming (the checkout's `CLAUDE.md`, each above it in the home, the user's; 262,144 bytes; column 0; outside a fence); R8 to R11 the four judges; R12 the checkout the sweep writes; R13 the loose look at unread text; R14 an error refuses; R15 the reasons; R16 the mark `sessions/<sid>/refused/<tool_use_id>`; R17 `guard.jsonl`, with `log(..., rule=[...])`.
- The block in `hooks.pre_tool_use`: for `Bash`, after the helper's charter rule, before the edit gates, a helper's call alike; a refused call opens no call file.

## 3. Interfaces and acceptance (the brief's ten lines)

- `lineguard.check(payload, env) -> dict`: `{}` or one `deny`; never `ask`; no process, no knob. `lineguard.failed(payload, env, exc) -> dict`: R14's answer for an exception that escapes `check`; never raises.
- The mark's path, `sessions/<sid>/refused/<tool_use_id>` (R16), and `instructionguard.log(..., rule=[...])`'s `rule` key in `guard.jsonl` (R17), as in §2.

| # | line | at the pin |
|---|---|---|
| 1 | the merge line and the reader's import | one line; `ok` under both venvs |
| 2 | `tests/test_g8_refusals.py` | no test passes (an import error) |
| 3 | the nine suites named | their counts at the pin, no failure |
| 4 | the launcher in the tests' box | `{}` for each payload; no `refused` folder |
| 5 | design/20 §2 item 4's two probes | the plugin refuses none |
| 6 | the replay, counts only | the plugin refuses none |
| 7 | the cost: launcher median within 10 ms of the pin's; slowest `check` under 0.25 s | measured beside the pin |
| 8 | `git diff <pin>` names only this packet's files | — |
| 9 | no `subprocess`, `environ`, `"ask"` in `lineguard.py`; the g2b scans read it | — |
| 10 | `scripts/recordlint`, `scripts/hygiene` | 0 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

The wall's: the live state and the real home (each probe in a temp home); the replay is read in counts only.

## 6. Report

The sitting's record, `history/sittings/2026-11-17-2-g8-refusals.md`: the choices inside the rulings are in its handover.
