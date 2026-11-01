# NICE_TO_HAVE: agentik-session

Findings that block nothing, one row each, in agentik-hq design/05 §2's table: `id` is `n<k>`, never reused; `level` is S1 to S4, S4 when unsure; a row leaves when it lands. Everything found before 2026-11-01 is frozen in `history/NICE-2026-11-01.md` and never edited: its four S3 items were answered on main (band-ended, S31, S34, S35), and its S4 and unlevelled items stay there, read by path when a packet touches their area.

## Open findings

| id | level | area | finding | evidence | from |
|---|---|---|---|---|---|
| n1 | S4 | `design/readme/source.md` | The README's source sits 2 B under its 16,384 B ceiling, so no new README line fits (s52's `--continue` line did not) until the source is trimmed or the ceiling moves | 16,382 B at 823003e; `tests/test_readme.py:25` | 2026-11-01, s52's builder |
| n2 | S3 | `DECISIONS.md` | agentik-session has no ledger on main (no `DECISIONS.md`, no `CLAUDE.md` block), against the Mac's ledger, entry 21 (a decision lives in the root `DECISIONS.md` of the repo holding its implementation) | `git ls-tree -r main --name-only \| grep -ci decision` gives 0; `history/NICE-2026-11-01.md` holds "this repo has no ledger" | 2026-11-01, h1's refuter F1 |
