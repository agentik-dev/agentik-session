# Packet s52, amendment 1: the canonical launcher's message; the ledger lead

| item | value |
|---|---|
| from | s52's stop (gate 20261101-144551-458, exit 2: 5 failed in `tests/test_bare_machine.py:172,186`); hq's ruling, sitting 2026-11-01-2-hq; h1's refuter F1 (agentik-session has no ledger). Parent `design/packets/s52-continue.md` |
| pin | branch `s52-continue` at 715777b, worktree `.claude/worktrees/s52-continue`; continue there |
| wall | the packet's row (`design/packets/s52-continue.md`), unchanged |
| may touch | `tests/test_bare_machine.py`, `NICE_TO_HAVE.md`, this amendment as `design/packets/s52-continue-a1.md` (reshaped to pass doclint and hygiene as the packet was), the branch's charter |
| acceptance | §2's acts; the verify row's check green |
| verify | the packet's row, unchanged: `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line |
| budget | One commit per act. **Stop at 50k context or 30 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

## 1. What the source says

Copied from hq's `history/sessions/BRIEF-2026-11-01-s52-a1.md`; as the packet's copy was, the sections are re-headed to GUIDE §9's six, the `wall, verify` row is split into the packet's `wall` and `verify` rows, an `acceptance` row names the verify row's check, and for hygiene its home paths, the ledger file's name, one sibling's name and one private name are rewritten; the text otherwise as written.

**hq's ruling.** The resync stands: `plugin/bin/agentik-session`, `plugin/lib/agentik_install.py` and `plugin/lib/agentik-tool.conf` are commons' canonical copies (GUIDE §10, hq entry 6), the launcher at the sha the agents and ledger plugins already ship (0c18a31d9fb4...). The five damaged-plugin cases take the canonical launcher's message.

## 2. Rulings

The acts.

0. This amendment, committed first.
1. **The five cases.** In `tests/test_bare_machine.py`, the damaged-plugin cases expect `"no names" if how == "no lib" else "no runner"`; every other expectation unchanged. Run that file under `/usr/bin/python3` and the venv's python.
2. **The ledger lead.** A NICE row, the next id: level `S3`; area the root ledger file; finding: agentik-session has no ledger on main (no root ledger file, no `CLAUDE.md` block), against the Mac's ledger, entry 21 (a decision lives in the root ledger of the repo holding its implementation); evidence: `git ls-tree -r main --name-only \| grep -ci decision` gives 0, and `history/NICE-2026-11-01.md` holds "this repo has no ledger"; from: 2026-11-01, h1's refuter F1. recordlint green.
3. The packet's verify line, last; read the code from the gate's line.

## 3. Interfaces

None beyond the parent's.

## 4. Findings that name this row

h1's refuter F1, act 2's NICE row.

## 5. Forbidden reads

The parent's.

## 6. Report (at most six lines)

The sha; each act's commit; the gate's id and its code from its line; the suite's counts.
