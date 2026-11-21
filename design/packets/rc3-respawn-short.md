# Packet rc3: a short respawn form where the full line does not fit beside the CHECKPOINT line

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-20, brief rc3-respawn-short; the owner's words below |
| pin | `d7e53a2` on main (gc1 landed, 2.0.0-alpha.149). Worktree `.claude/worktrees/rc3-respawn-short`, branch `rc3-respawn-short`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state or writes the live home; no relay verb; `_confirm`, UserPromptSubmit's line (rc1 R2), the band, the launcher and `MAX_OUT` (640) unchanged |
| may touch | `plugin/lib/claude_session/hooks.py` (`_checkpoint_out`, `_with_respawn`, `_post_meter`, `_post_tool_use`, a new `_after` and `UNCONFIRMED_SHORT`); `tests/test_rc3_respawn_short.py` (new); `tests/test_pl2_line_dynamic.py`'s test that pinned the drop; `design/respawn-r1.md` §3.3 and its change log; `NICE_TO_HAVE.md` (n346, n347, n352 leave); `.hygiene-allow` (the gc1 pair, the FW4d pair); this packet and the sitting's record; what `make stamp` writes |
| verify | pytest under `.venv` and `.venv-floor` on the new file and the files that pin the checkpoint or the respawn line; `scripts/doclint`, `scripts/recordlint`; `make stamp`, then `make check`, once, last, through the gate queue |
| acceptance | §3 |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_with_respawn` says pl2 R7's line after the handler's context only where the pair fits MAX_OUT, else nothing. `UNCONFIRMED` with `<the charter>` is 293 characters.
- `_checkpoint_out` under a chain takes the first spelling (absolute, relative, `NO_CHARTER`) whose line alone fits; at the crossing it is 478 to 583 B, past 100% 561 to 587 B, so no full respawn line ever fits beside it, and a chained sitting closing from a script at its checkpoint is never told its mark is unconfirmed.
- `_SAFE_PATH` has no length cap: a 700-character path gives `{}` with no CHECKPOINT line due.

The owner's words, 2026-11-20: "continue with the charter". The charter orders this row first: the two allow rows removed and the short respawn form built.

## 2. Rulings (brief rc3)

- R1 where pl2 R7's line is due, the first of three forms whose pair fits MAX_OUT after the handler's context: `_unconfirmed_line`'s line; that line with `UNSAFE_CHARTER` for the path; `UNCONFIRMED_SHORT`, exactly `RESPAWN unconfirmed: run the close again in the foreground.` None fits: the handler's output.
- R2 where a respawn line is due and `_post_meter` says a CHECKPOINT line under a chain, `_checkpoint_out` takes the first spelling of the charter whose line leaves room for the short form; none does: as at the pin. Off a launcher, the pin's line.
- R3 with no respawn line due, every PostToolUse output is the pin's, byte for byte; the CHECKPOINT line first, the whole within MAX_OUT; gc1's `_with_changed` and the gate's lines keep their place.
- R4 respawn-r1 §3.3 gains one sentence for the PostToolUse line and its three forms; NICE n346, n347, n352 leave (n351 stays).
- R5 `.hygiene-allow` loses the gc1 pair and its comment; the FW4d pair and its comment too where both scans exit 0 without them.

## 3. Interfaces: the acceptance table (baseline measured at `d7e53a2`)

Tests in `tests/test_rc3_respawn_short.py`.

| # | line | at the pin |
|---|---|---|
| 1 | chained, the crossing, a close from a script: the CHECKPOINT line, then the short form, within MAX_OUT | the CHECKPOINT line alone |
| 2 | the same past 100%: the EXIT rule, then the short form; the charter named `<this sitting's charter>` | the CHECKPOINT line alone, the relative path named |
| 3 | off a launcher past 100%: the pin's line, then the first form that fits (the short) | the CHECKPOINT line alone |
| 4 | no CHECKPOINT line due: the full line, as at the pin; pl2's drop test now pins the full line giving way to the short form | the same; the pair dropped |
| 5 | a 700-character safe path, no CHECKPOINT line: the line with `<the charter>` | `{}` |
| 6 | a handler's context one byte short of room for the short form: its output unchanged | the same |
| 7 | 48 states (crossing, past 100%; chained or not; a line due or not; paths of 20, 72, 200; ceilings 400,000, 1,000,000) against the pin's module from git: within MAX_OUT, CHECKPOINT first, the short form in every chained due state, the pin's bytes where none is due | 24 due states, 3 of them said (off a launcher at the crossing, a path of 20 or 72 at 400,000) |
| 8 | `.hygiene-allow` holds no gc1 row; both scans exit 0 | the two rows |
| 9 | `make stamp`, then `make check` green through the gate | |

`UNCONFIRMED_SHORT` is 59 characters; `_after(out, line)` is the pair as `_with_respawn` says it, which `_checkpoint_out` measures its room by.

## 4. Findings that name this row: the choices inside the rulings

- The room reaches `_checkpoint_out` as a `room` argument through `_post_meter`; `_post_tool_use` reads `_ran_unconfirmed` before the meter, which it only reads, and after `_confirm`, as at the pin.
- The second form is `UNCONFIRMED.format(f=UNSAFE_CHARTER)`, which is the given line with the path unnamed, since every due line is drawn from `UNCONFIRMED`.
- Under the waiver (`charter` None) and off a launcher `room` is never used: those lines are the pin's.
- NICE n346, n347, n352 leave as rows do when they land; n351 stays.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no relay ledger.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job, the choices made, what was not done.
