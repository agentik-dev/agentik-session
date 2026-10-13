# Packet S14: the fixes of the third adversarial round (ADV11), one row

| item | value |
|---|---|
| from | `design/review-adv11.md` (ADV11-1 to -5, -10); respeak's `design/review-adv11.md` ADV11-4 and -6 (by `grep -n 'ADV11-'`); conventions §5, §6, §9; the STANDING WORD |
| pin | `main` at d400db0 or later; your row is your branch, `s14-fixes-adv11`; `.venv` by the conventions §7 symlink |
| wall | this repo only; other repos read-only, and only by `scripts/doclint --repo <sibling>` (ruling 5). No push, `--amend`, rebase, device; no `make install` or `make readme` (neither is needed); no `relay` verb; logs to `mktemp` |
| may touch | `scripts/{bounded,doclint,hygiene}`, `install-wrapper.sh`, `Makefile` (comments only), `tests/test_{bounded,doclint,hygiene,install}.py`, `design/conventions.md`, `design/overhaul-r1.md` §4, `design/plan.md` (row 24, new), `history/sittings/*.md` |
| verify | `make check` (the relay's gate line; never an acceptance line) |
| acceptance | `.venv/bin/python -m pytest -q tests/test_bounded.py -k 'stopped_guardian or nested_stop or nonfinite' 2>&1 \| tail -1` reads passed, 3 or more; `.venv/bin/python -m pytest -q tests/test_doclint.py -k 'fails_closed or targeted_allowed or missing_prompt' 2>&1 \| tail -1` reads passed, 25 or more; `.venv/bin/python -m pytest -q tests/test_hygiene.py -k oversize 2>&1 \| tail -1` reads passed; `.venv/bin/python -m pytest -q tests/test_install.py -k session_start 2>&1 \| tail -1` reads passed; `scripts/bounded --wall nan -- true; echo $?` reads 1; `d=$(mktemp -d); git -C $d init -q; head -c 4194305 /dev/zero \| tr '\0' x > $d/f; printf '\n/Use%s/me/x\n' rs >> $d/f; scripts/hygiene --repo $d --json \| python3 -c 'import json,sys;print(json.load(sys.stdin)["groups"]["home"]["lines"])'; rm -rf $d` reads 1; `d=$(mktemp -d); git -C $d init -q; mkdir -p $d/history/sessions; echo design/packets/nope.md > $d/history/sessions/NEXT; scripts/doclint --repo $d \| grep -c 'missing prompt'; rm -rf $d` reads 1; `for f in hygiene doclint bounded; do grep -qF "$(shasum -a 256 scripts/$f \| cut -c1-64)" design/conventions.md \|\| echo $f; done \| wc -l` reads 0; `grep -l '(filled at close)' history/sittings/*-s14-fixes-adv11.md \| wc -l` reads 0; `git status --short \| wc -l` reads 0 at the end |
| budget | 80 turns, 140k context; commit per act; checkpoint at 80% (64 turns, 112k); never push, amend or rebase. The charter names doclint's five rows at open, is under 4,096 bytes with no home path, and `(filled at close)` is gone at close. Run `make check` in the foreground and commit in the same turn |

## 1. What the source says

ADV11's verdict: ready to carry example-app once ADV11-1 (a stopped guardian leaves the suite unwalled and drops the lock) and ADV11-4 (the suite rule is a denylist; 18 shapes pass) land; -2, -3, -5 in the same packet. Respeak's review adds its ADV11-4 (survivor tests by pattern) and -6 (a `NEXT` naming a missing prompt passes). D2: fail early, one rule in two languages, temp roots only.

## 2. Rulings (decided inside the design; your charter records each with its consumer)

Each act: the test first (it fails on main), then the fix, one commit.

1. **ADV11-1, bounded.** The guardian writes the command's pgid (`<pgid>\n`) on a report pipe right after `Popen`; `main` reads it before its wall loop (deadline: the wall). `cut`'s fallback, in order: SIGKILL the command's group, SIGKILL the guardian's group, reap the guardian, then poll `killpg(pgid, 0)` until `ProcessLookupError` (at most 2 s; a `PermissionError` counts as gone). Invariant: once the pgid is reported, `bounded` never exits while that group lives, so the lock is never free beside a live suite. Test `test_stopped_guardian_does_not_leak_the_suite`: `BOUNDED_GRACE=1 --lock --wall 3`, the guardian SIGSTOPped at 1 s; exit 124 and the command's pidfile pid gone at exit.
2. **ADV11-10**, next to ruling 1: `parse` refuses a `--wall` or `--load` that is not finite (`math.isfinite`), exit 1, usage line. Test `test_bounded_refuses_nonfinite` (`nan`, `inf`, `-inf`).
3. **ADV11-2, the nested stop line.** `bounded` sets `BOUNDED_DEPTH` (its own depth plus one) in its command's environment; a `bounded` that starts with `BOUNDED_DEPTH` above 0 writes `bounded: nested stop: <why>`, never `bounded: stop: <why>`. Only the outermost stop reads unrun; an inner wall is a plain red. Test `test_nested_stop_line_is_not_the_gates`: an outer `bounded -- sh -c '<inner bounded --wall 1 -- sleep 5>'`; stderr holds `bounded: nested stop: wall` and no `bounded: stop:` line.
4. **ADV11-3, hygiene over 4 MiB.** An oversize file is streamed in 1 MiB chunks, cut at a line boundary, a longer line carried at most 64 KiB with a 4 KiB overlap; the codec is the first chunk's. `oversize` counts streamed files, never a pass by path. Test `test_hygiene_oversize_is_scanned`: 4 MiB + 1 of `x`, a newline, a home path: one `home` hit, exit 2.
5. **ADV11-4, the suite rule fails closed.** A simple command is a runner when any of its words (basename) is `make`, `gmake`, `pytest`, `py.test`, `go`, `tox`, `nox`, `claude`, `relay`, or a `python*` with `-m pytest` or `-m unittest` anywhere after it. The rule reads from that word, so every wrapper (`caffeinate -i`, `stdbuf -oL`, `arch -arm64`, `xargs`, `python3 -I`, `-X dev`) is seen through without a list. A runner passes only in a targeted shape: pytest with a `.py` file below the tests root (no glob character, no `..`), a `::` id, or a `-k` whose value, read before quotes are blanked, is non-empty and does not start with `not`; `-m unittest` with a dotted module; `go test` with named packages (no `...`, not `all`, no `$`) and a `-run` holding a literal identifier of 3 or more characters; `make -n`, or `make` whose every target is in a new `MAKE_TARGETED` (`doclint hygiene lint validate build tree-note`). Everything else from a runner is refused: `claude` always, `tox`, `nox`, `make readme`, `install`, `skill`, the relay's existing shapes. The non-literal command word and stdin-shell rules stay. Parametrized `test_suite_rule_fails_closed`: ADV11-4's 18 cells plus `make readme`, `make install`, `make skill`, one id each. `test_suite_rule_targeted_allowed`: `pytest tests/test_x.py`, `pytest tests/test_x.py::t`, `pytest -k 'shape or spent'`, `go test ./internal/packet -run TestUnbounded`, `make doclint hygiene`, `make -n check`, `sh -c 'true'`. Then run it over this repo and each sibling (`doclint --repo`, read-only): a newly refused packet is fixed here or named in your report; never widen the rule to pass one.
6. **Respeak ADV11-6.** `check_next`: when `history/sessions/NEXT` is present, each non-blank line naming a `.md` path must exist in the repo, else `next: NEXT names a missing prompt`. Test `test_next_names_a_missing_prompt` (missing refuses; present passes).
7. **ADV11-5, the launcher.** `install-wrapper.sh`: on `hook SessionStart` with `PYTHON` or `CODE` gone, print `{"systemMessage": "claude-session: <path> is gone; run make install"}` on stdout in every session, exit 0; the marker keeps the other events quiet. Test `test_gone_interpreter_speaks_at_every_session_start`: a missing python, a temp `XDG_STATE_HOME`; two SessionStarts each print JSON with `systemMessage`; a PreToolUse after them prints nothing.
8. **Respeak ADV11-4** does not reach this repo (survivors by pidfile, never `pgrep`); keep it so: `test_no_survivor_check_greps_the_machine` fails if `pgrep` appears in `tests/`.
9. **The record.** Conventions §5 (the nested stop line; the rule fails closed, `MAKE_TARGETED` named) and §6 (streamed oversize; the three new shas: hygiene, doclint, bounded) inside the 9,216 ceiling (9,018 now; tighten, never raise). overhaul-r1 §4, one row per invariant of rulings 1, 3 and 5. Plan row 24: S14, "built on branch s14-fixes-adv11, N passed, awaiting merge (sitting <id>)".

## 3. Interfaces

- bounded: exits unchanged; new stderr prefix `bounded: nested stop:` at depth above 0; env `BOUNDED_DEPTH`. A relay reading the last `bounded: stop:` line anywhere (respeak ADV11-3) never counts a nested one.
- doclint: refusals only widen (same message, `acceptance runs a whole suite`); one new message, `next: NEXT names a missing prompt`. hygiene `--json` unchanged.
- The next re-sync copies `scripts/{bounded,doclint,hygiene}`; agent-relay's `packet.Unbounded` should take ruling 5's shapes and cells (one rule in two languages). Name the three shas and the tests that travel in your report.

## 4. Findings that name this row

On main d400db0: the nan line reads 0; the oversize line reads 0; the NEXT line reads 0; conventions 9,018 bytes; ADV11-6 (herd), -7 (UTF-32), -8 (grandfather by basename), -9 (nested depth ceiling) are deferred to a later packet.

## 5. Forbidden reads

Other repos beyond the named lines and `doclint --repo`; `~/.claude/projects/`; `~/.local/state/`; `history/relay/`; `bugs/`; `design/plan.md` beyond row 24; other packets; any file over 8 KB whole.

## 6. Report (one table, at most six bullets, under 1,500 words)

Table: acceptance lines, exit, last line. Bullets: choices with consumers; the three shas; sibling packets refused; skips; at most one fork. Last line: branch and head sha.
