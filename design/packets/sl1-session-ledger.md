# Packet sl1-session-ledger: this tool's own ledger, started with five entries

| item | value |
|---|---|
| from | the hq coordinator, brief sl1-session-ledger (2026-11-13, S3) and its brief 2 (2026-11-17) |
| pin | `ef0ba32` on main (2.0.0-alpha.130, is2-first-read's merge). Worktree `.claude/worktrees/sl1-session-ledger`, branch `sl1-session-ledger`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no relay verb; no code and nothing under `plugin/`; no entry, question or answered line written by an edit tool |
| may touch | `DECISIONS.md` (new: the skeleton by hand, every entry by `agentik decisions new` and `answer`), `OPEN-QUESTIONS.md`, this packet, `history/sittings/2026-11-17-3-sl1-session-ledger.md` |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3's table |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then R2, then R1 with R3 |

## 1. What the source says (baseline at `ef0ba32`)

This repo has no ledger. Two decisions that bind this tool alone were kept in the suite's ledger. The owner's answer of 2026-11-12 gives this repo its own ledger, "a DECISIONS.md with no Every session section, so no CLAUDE.md and no cost per turn", and moves the two here, its tails citing no private path. The owner's answers of 2026-11-17 to the suite's decisions 52, 53 and 55 bind this tool alone, and the answer to the suite's decision 58 ("A helper enters them") is the word for a helper to run the tool.

Measured at the pin with decisions 0.23.8: `agentik decisions show 1` prints `decisions: no ledger at <worktree>/DECISIONS.md`, exit 2. On a scratch repo holding R1's skeleton and the pin's `OPEN-QUESTIONS.md`, `agentik decisions render --lint` prints seven lines, `OPEN-QUESTIONS.md:9` to `:15`, `a line under Answered ends in (YYYY-MM-DD; source)`, exit 1: each answered line closes with a `Next:` sentence after its `(date; source)` tail.

## 2. Rulings

- R1, the skeleton: a title, one paragraph and three empty sections (`In force`, `Proposed`, `Superseded`), written as a new file holding no entry. `agentik decisions init` is not used: it writes a `CLAUDE.md` block, and this ledger has none.
- R2, the questions file first: in each of the seven answered lines the `Next:` sentence moves in front of the tail, so the line ends with the tail; no word is dropped or changed. This file is no ledger, so this is an ordinary edit.
- R3, two entries from the suite's ledger, its entries 40 and 41, under `The verbs that write`, each by `new`, then `answer --pick "Take it"` with `--preview` first; the source names the owner's answers to hq's decisions 40 and 41 and 43, the bodies are the suite's word for word.
- R3b, three entries from the owner's answers of 2026-11-17 to the suite's decisions 52, 53 and 55, in that order, under `The profiles`, `The refusals` and `The session's start` (new areas), by the same two commands.
- R4: `answer` prints `CLAUDE.md holds no GENERATED markers; the block is left as it is`; no `CLAUDE.md` is made. The `.claude/edit-gates` list the tool leaves is not committed and no `.gitignore` line is added for it.
- R5: a refusal is mended within R1 to R3b, else the row stops and reports it; nothing is written by hand in its place.
- R6, hygiene: the tails name `hq`, as this repo's code already does.

## 3. Interfaces, choices and acceptance

No interface moves: the row changes no code. The tool writes each entry's tail as `(<date>; the owner's answer to decision <n>, <source>)`, the source given on its line after its own clause.

| # | line | at the pin |
|---|---|---|
| 1 | `agentik decisions show <n>` for each entry: exit 0, under its area, its body byte-equal to the brief's, its tail opening with the day's date and holding the brief's source | `decisions: no ledger at ...`, exit 2 |
| 2 | `agentik decisions render --lint`: exit 0 | seven lines, `OPEN-QUESTIONS.md:9` to `:15`, exit 1 |
| 3 | `OPEN-QUESTIONS.md`: `## Open` still reads `None.`; each of the seven lines holds its words in the new order; five new answered lines, one for each entry | seven lines with `Next:` after the tail |
| 4 | no `CLAUDE.md` at the top; `git status --short` shows nothing but, at most, `?? .claude/edit-gates`; `git diff --stat main...HEAD` names only `DECISIONS.md`, `OPEN-QUESTIONS.md`, this packet and the charter | no ledger, no `CLAUDE.md` |
| 5 | under a temp HOME: `agentik session checkpoint --commit` exits 2 naming the form; `agentik session set checkpoint 70 --save` exits 2 naming the profiles file | both exit 2 |
| 6 | `scripts/hygiene --require-private --commits main..HEAD` exits 0; `make check` through the gate queue, green; `plugin.json`'s version unchanged | green at alpha.130 |

Left, and not this row's: the suite's ledger losing its two entries (the coordinator's, after this lands); whether a tool repo tracks the gate list the decisions tool writes; a lint of this ledger in this repo's `make check`.

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names.
