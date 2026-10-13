# Packet S18: bounded confirms the load by the CPU's idle share, and its guardian runs with `-B`

| item | value |
|---|---|
| from | the relay plugin's AR48 (its `scripts/bounded`, 2026-10-01) and its review's open line: "`scripts/bounded`'s guardian is started as `sys.executable <bounded> --guard` with no `-B` … the file is shared with the plugin repos, so it goes with their copies." The observer, 2026-10-04: this repo's copy becomes the one canonical `bounded`, as `scripts/hygiene` is |
| pin | `main` at 6166e8b plus this packet's own commit; branch and worktree `s18-bounded-idle`, off main |
| wall | this repo only. No push, no `--amend`, no rebase, no device, no network. Never run `relay` in any form, and never build or run a relay binary. Every python is `python3 -B` or runs with `PYTHONDONTWRITEBYTECODE=1` |
| may touch | `scripts/bounded`, `tests/test_bounded.py`, `design/conventions.md` (§1's `scripts/` lines and §5's `bounded` sentence only, plus trims elsewhere to stay within its byte ceiling), `NICE_TO_HAVE.md`, this packet, the row's charter |
| acceptance | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_bounded.py -q -k s18 2>&1 \| tail -1` reads `6 passed` or more (with any deselected count); `grep -c 'BOUNDED_IDLE_FLOOR' scripts/bounded` reads 1 or more; `grep -c '"-B"' scripts/bounded` reads 1 or more; `grep -c 'scripts/bounded' design/conventions.md` reads 2 or more |
| verify | `make check` |
| budget | 70 turns, 150k context; one commit per act; the charter names doclint's five rows (goal, budget, pin, window, agents) at open; never push, amend or rebase |

## 1. What the source says

The relay plugin's copy of `bounded` (given to you read-only at `/private/tmp/claude-501/-Users-you-code/3469df08-e3bf-4c28-ae1f-8f10bc1cf48e/scratchpad/s18ref/bounded-relay-be3f58b`, with its Go tests beside it as `ar48_test.go.txt`) holds `--load N` on the 1-minute load average only when the CPU confirms it. Its docstring states the rule:
- The idle share is read only above the load line, over one second. Above the floor (25%), one line says the load is not confirmed and there is no wait. Two polls in a row above the floor end a wait.
- Unreadable, the share leaves the load alone to decide.
- A read never outlasts the wait or the wall, and its time comes out of the poll's sleep.
- Envs: `BOUNDED_IDLE` (a fake share in percent, or several by commas read in order, the last repeating; a fake load without it reads no share) and `BOUNDED_IDLE_FLOOR` (percent, 25, floats taken).
- Its review rounds added: `top` stays in bounded's group, so a TERM to the group takes it; a poll that is not positive is the default; a slow or hung `top` is held under the wall and the wait's limit.

This repo's copy lacks all of that. The relay's copy lacks this one's ADV11-1 (the guardian reports the command's pgid on RFD, and the fallback kills that group first) and ADV11-2 (`BOUNDED_DEPTH`, `bounded: nested stop:`). Neither copy starts its guardian with `-B`.

## 2. Rulings (decided inside the design)

1. Port the relay's idle rule into this file whole: the docstring's `--load` paragraph, both envs, the parsers (`top -l 2` on macOS, `/proc/stat` elsewhere), and every review-round behaviour listed in §1. Keep ADV10 and ADV11 exactly as they are. Where the two files differ in a shared helper, ADV11's behaviour wins, and the idle read is fitted around it.
2. The guardian's argv takes `-B`: `[sys.executable, "-B", <bounded>, "--guard", …]`.
3. The result is the canonical `bounded`. The other plugins take its bytes later, by copy, so nothing in it may name this repo or read this repo's layout beyond what it reads today.
4. Conventions §1 lists `scripts/bounded` as byte-identical everywhere (canonical: the session's), beside `scripts/hygiene`. §5's `bounded` sentence names the idle confirm in one clause. The file stays within doclint's ceiling for it (9,216 bytes; it is 9,214 today), so trim words elsewhere and change no rule.
5. `README.md` and `design/readme/` are not touched (a render needs `claude -p`). If the README names `--load`, file one line in `NICE_TO_HAVE.md` for the next render.

## 3. Interfaces

The command line, exit codes (2 for lock and load stops, 124 for the wall) and stop lines are unchanged. Additions: the two envs, and one stderr line when the load is above the line but not confirmed.

## 4. Findings that name this row

The relay review's open line on the guardian's `-B` (quoted in `from`). The tests below fail before the fix.

Add to `tests/test_bounded.py`, each name containing `s18`, each fast (fake envs; `BOUNDED_LOAD_POLL` and `BOUNDED_LOAD_MAX` small):
- A high load with a high idle share runs at once, exit 0, with the not-confirmed line.
- A high load with a low share waits and stops with `bounded: stop: load`, exit 2.
- A low share, then two high polls, ends the wait and runs.
- A fake load with no `BOUNDED_IDLE` waits as today (the load decides).
- `BOUNDED_IDLE_FLOOR` takes a float.
- The guardian's argv carries `-B` (for example `bounded --wall 10 -- sh -c 'ps -o args= -p $PPID'`).

Run the six on the unchanged file first and record which fail; only the guardian test and the idle tests are expected red.

## 5. Forbidden reads

Transcripts; `~/.local/state/agent-relay`. Read no other repo; the reference files in §1 are the only outside reads.

## 6. Report

At most 150 words: commits, the six tests red before and green after, acceptance read line by line, `make check`'s exit, the conventions file's bytes, and anything filed to `NICE_TO_HAVE.md`. Run `make doclint` and `make hygiene` before each commit.
