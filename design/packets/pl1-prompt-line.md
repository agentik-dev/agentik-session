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

## 1. The owner's words

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
