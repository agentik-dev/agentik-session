# Packet pl1: the line the session plugin prints at each prompt, tidied

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-13, brief pl1; the owner's words below |
| pin | `8a4b593` on main (2.0.0-alpha.93). Worktree `.claude/worktrees/pl1-prompt-line`, branch `pl1-prompt-line`; `.venv`, `.venv-floor` linked from the main checkout. No version bump in phase 1 |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`, no gate job in phase 1; no `claude`; no test reads live state or writes the live home; no relay verb; in `hooks.py` only the lines that build the prompt's text |
| may touch | `plugin/lib/claude_session/{admission.py,cli.py,rules.py,hooks.py}` (hooks: the prompt's text only), `plugin/hooks/session.ts` (the line's twins: `mixPart`, `lineNone`, `lineEnd`, `bandLine`), `plugin/hooks/session.test.ts`, `tests/test_pl1_prompt_line.py` (new) and the tests that pinned a word that left, `RUNBOOK.md`, `plugin/skills/session/SKILL.md`, `README.md`, `design/readme/{source.md,rendered.sha256}`; this packet and the charter |
| verify | phase 1: `python -m pytest` under `.venv` and `.venv-floor` on the changed tests and the files that pin the hook's lines; phase 2, on the coordinator's word: the gate queue's `make check` |
| acceptance | §3; `tests/test_pl1_prompt_line.py` green under both venvs (red at the pin) |
| budget | about 90 tool calls, `claude-opus-5-5` |

## 1. What the source says: the code at the pin

- One function draws the usage line, `admission.band_line` (with `_line_none`, `_mix_part`, `_line_end`); the UserPromptSubmit hook adds it to its context (`hooks._admission_line`), and the mod's `admissionLine` in `plugin/hooks/session.ts` is its twin, both pinned by the one-line fixtures in `session.test.ts` that the Python tests read.
- The zone's word the owner saw is the mod's first line (`bandLine`: `session: … · ctx c% · turns t% · <zone>`). The prompt hook already says no zone in `clear` or `unknown`; SessionStart says none.
- `status` prints the band (`band_status`) on a `none` login only; nothing prints the mix or the mode. `rules.MIX_ITEM` points at "the band line's `next`".
- The RUNBOOK and the skill show the line with `observe` and the band; the README source does not show or describe the line.

### The owner's words

"I think we need to clean this UX up on the claude code screen:

no 5h window · 7d 61% · mix fable 33/50 · opus 27/50 · next fable · resets 1 · week resets Fri 13:00 · band best to 23:00 · 14 helpers · observe

The mix fable opus and band best aren't helpful. next fable isnt that helpful either. I don't know what "observe" means. or "clear" on the first line."

Asked which to keep: "I don't think we need any of those we called out so let's tidy up the output a bit."

## 2. Rulings (brief pl1)

- R1 the line loses `mix <family> N/N` (each family's share), `next <family>`, `band <word> to HH:MM` and the mode's word (`observe`). What stays, in today's order and wording: the 5h window, the 7d percent, the resets, the week's reset, the helpers. The owner's line becomes `no 5h window · 7d 61% · resets 1 · week resets Fri 13:00 · 14 helpers`.
- R2 the session line (the mod's first line) says no zone word when the zone is `clear`; every other zone as today. `status` keeps `zone clear`.
- R3 each fact that left is in `agentik session status`: the mix with each family's share and target, the next family, the band with its time, the mode; `--json` with new keys only.
- R4 the pacing text that pointed at the line's `next` points at `agentik session status`.
- R5 `admission.mix` works as today with no word at the prompt; the RUNBOOK says so.
- R6 the cache line, every refusal, CHECKPOINT and EXIT line untouched.
- R7 the RUNBOOK, the skill and the README source follow; the README source under 16,384 B.

## 3. Interfaces: the acceptance table (baseline at the pin)

| # | line | at the pin |
|---|---|---|
| 1 | the owner's state through the prompt hook: R1's line exactly | the owner's line, word for word (`band_line` on the state at 8a4b593) |
| 2 | zone `clear`: the mod's session line ends `turns N%` with no zone word; `notice` and the others as at the pin | `session: ctx 64% · turns 6% · clear` |
| 3 | `status` on the same state shows the mix, the next family, the band, the mode; `--json` holds them under the new key `admission` | the band alone (`band: best to 23:00`); the mix, the next family and the mode missing, in the text and in `--json` |
| 4 | `rules` with the mix on names `agentik session status` for the next family | names "the band line's `next`" |
| 5 | the line with the mix off reads as with it on (less the resets count R1 keeps) | the mix's words on the line |
| 6 | every other test green, changed only where it pinned a word that left | |

The interfaces: `admission.band_line(b, now=None, columns=0)` unchanged in shape; `admission._mix_part` draws only the line's mix parts (`reset now`, `resets N by Ddd HH:MM`); a new `admission.mix_status(mx, now=None)` draws `status`'s `mix:` line; `admissionLine`, `mixPart` in `session.ts` twin them. `status --json` gains one top-level key, `admission`: `{"mode": ..., "mix": <band.json's mix object>}`, each present only when band.json has it.

## 4. Findings that name this row: the choices inside the rulings

- `reset now` stays on the line: it is not one of R1's four groups (it takes `next`'s place when a Fable reset is due, and `rules.MIX_ITEM` names it as the owner's step).
- `mix no reading` leaves with the shares; with no points the line adds nothing for the mix.
- The mod's line changes with the hook's, the twins kept equal: the owner's screen is the mod's two lines.
- Acceptance 5 is read with R1: the mix's resets count stays on the line, so the line with the mix off equals the line with it on less `resets <n>`; with no resets count the two are equal.
- `status` says `mix: …` and `admission mode: …` after the band's line; `--json` adds `admission: {mode, mix}`, band.json's own objects.
- The README source does not show the line, so it is unchanged and not re-rendered.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the choices made, what was not done; phase 2 on the coordinator's word.
