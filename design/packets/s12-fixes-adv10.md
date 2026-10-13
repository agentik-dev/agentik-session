# Packet S12: fixes adv10 (ADV10-1 to -11), two rows in order

| item | value |
|---|---|
| from | `design/review-adv10.md` whole (the reproductions and fixes live there); `design/conventions.md` §5 to §7; `record design/overhaul-r1.md --section 4`; the STANDING WORD (decide inside the design, record, escalate only a real fork). Nothing outside this repo |
| pin | `main` at ac529ab or later. Your row is your branch (`git branch --show-current`): `s12a-fixes-adv10` does §2 part A; `s12b-fixes-adv10` does part B, its act 0 `git merge --no-ff s12a-fixes-adv10` (the orchestrator's order, not a rebase). `.venv` by the §7 symlink |
| wall | this repo only. No push, `--amend`, rebase, device, network; no `make install` (the owner's); no `relay` verb; logs to `mktemp` |
| may touch | A: `scripts/bounded`, `scripts/readme-render`, `Makefile` (`check`, `readme`), `.gitignore`, `scripts/doclint` (`CONVENTIONS_CEILING` only), `tests/test_bounded.py`, `tests/test_readme.py`. B: `scripts/{doclint,hygiene}`, `.hygiene-allow`, `Makefile` (`install`), `install-wrapper.sh`, `claude_session/launch.py`, `tests/**`, `design/packets/*.md` and `rows-*.json` (path rewrites only). Both: `design/conventions.md`, `design/overhaul-r1.md` §4, `design/plan.md` (row 22's cell), `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `make check` (the relay's gate line; never an acceptance line) |
| acceptance | A: `.venv/bin/python -m pytest -q tests/test_bounded.py -k 'sigkill or exclusive or stop_line or counts_the_load' 2>&1 \| tail -1` reads passed, 5 or more; `BOUNDED_LOADAVG=999 BOUNDED_LOAD_MAX=0.1 BOUNDED_LOAD_POLL=0.05 scripts/bounded --load 1 -- true 2>&1 \| tail -1` reads `bounded: stop: load`; `grep -c -E 'wall 840\|bounded --wall 600 --load 4 -- scripts/readme-render' Makefile` reads 2; `grep -L 'timeout=' scripts/readme-render tests/test_readme.py \| wc -l` reads 0. B: `.venv/bin/python -m pytest -q tests/test_doclint.py -k wrappers 2>&1 \| tail -1` reads passed; `d=$(mktemp -d); git -C $d init -q; mkdir -p $d/design/packets; printf '\|a\|b\|\n\|-\|-\|\n' > $d/design/packets/s99-x.md; scripts/doclint --repo $d \| grep -c 'verify row missing'; rm -rf $d` reads 1; `d=$(mktemp -d); git -C $d init -q; printf '/Use%s/x/code\n' rs \| iconv -t UTF-16LE > $d/u.md; head -c 5000000 /dev/zero > $d/big.txt; scripts/hygiene --repo $d --json \| python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["hits_outside_allowlist"],d.get("oversize"))'; rm -rf $d` reads `1 1`; `for v in 1x -1; do CLAUDE_SESSION_DEPTH=$v PATH=/usr/bin:/bin .venv/bin/python -m claude_session start balanced --dry-run >/dev/null 2>&1; echo $?; done \| sort -u` reads 2; `grep -cF 'realpath $(PYTHON)' Makefile` reads 0; `.venv/bin/python -m pytest -q tests/test_install.py tests/test_hygiene.py tests/test_launch.py 2>&1 \| tail -1` reads passed; `grep -rlE '/Users/[a-z]+' design/packets \| wc -l` reads 0; `for f in hygiene doclint; do grep -qF "$(shasum -a 256 scripts/$f \| cut -c1-64)" design/conventions.md \|\| echo $f; done \| wc -l` reads 0. Both: `grep -l '(filled at close)' history/sittings/*-s12?-fixes-adv10.md \| wc -l` reads 0; `git status --short \| wc -l` reads 0 at the end |
| budget | 80 turns per row, 140k context; commit per act; checkpoint at 80% (64 turns, 112k); never push, amend or rebase. The charter names doclint's five rows at open; `(filled at close)` gone at close |

## 1. What the source says

ADV10: "not ready to carry example-app until ADV10-1 and ADV10-2 are fixed"; -3 to -7 before the next gate, install, README round and going public; -8 to -11 fit here too. No run-9 ruling names it. D2 applies: fail early, bounded work, group kills, invariants, tests on temp roots only.

## 2. Rulings (decided inside the design; your charter records each with its consumer)

Each act: the test first (it reproduces the finding on main), then the fix, one commit.

**Part A, `s12a-fixes-adv10` (the gate):**
1. ADV10-1, a lifeline: `bounded` opens a pipe and spawns a guardian (`bounded --guard FD -- cmd`) in a new session; the guardian runs `cmd` in its own group and selects on the pipe and the child. On EOF (the parent died, SIGKILL included) it SIGTERMs its group, waits the grace, then SIGKILLs the group and itself. When `cmd` exits it kills the rest of its group, then exits with `cmd`'s code. Invariant: no group member outlives the gate by more than grace plus 1 s. Test `test_caller_group_sigkill_reaches_the_suite`: a new-session `sh` runs `bounded -- sleep`; SIGKILL to the sh's group; the sleep's pid (from a file) is gone within 2 s.
2. ADV10-1, the budget: `--wall S` counts from `bounded`'s start; the load wait ends at 600 s or the deadline, whichever is first; `check` takes `--wall 840`, inside the relay's 900. Test `test_wall_counts_the_load_wait`.
3. ADV10-2: `fcntl.flock(LOCK_EX\|LOCK_NB)` on the file `.check.lock` (pid and start written for the message); the fd passes to the guardian (`pass_fds`), so the lock is held exactly while the group lives. No staleness, no rename. A leftover `mkdir`-era directory is removed when its owner pid is dead, else refused. Tests `test_lock_exclusive_under_takeover`, `test_live_holder_refuses_at_any_age`.
4. ADV10-3: on lock, load and wall, one last stderr line `bounded: stop: lock\|load\|wall`, exits kept (2, 2, 124). Conventions §5: a gate output holding that line is `unrun`, never red; the relay reads it (handover). Test `test_stop_line_names_the_reason`.
5. ADV10-6: `readme: scripts/bounded --wall 600 --load 4 -- scripts/readme-render` (the env kept); `timeout=120` on both collection runs. ADV10-11 (b): the refusal test runs a copy in a temp git repo.
6. The record: conventions §5 (lifeline, flock, stop line, 840 inside 900); overhaul-r1 §4 a row per invariant. `CONVENTIONS_CEILING` 9,216 only if §5 cannot be tightened.

**Part B, `s12b-fixes-adv10` (lint, hygiene, launcher):**
7. ADV10-4: `runs_suite` strips wrappers to a fixed point: assignments, `env` (flags), `nice [-n N]`, `nohup`, `time`, `command`, `exec`, `timeout [opts] N`, `uv run`, `bounded ... --`, and `sh\|bash\|zsh -c BODY` (the body tested before quotes blank). A pytest path `.` or the tests root with no `-k`, `-m` or `::` is whole; `go test` with a `...` package and no `-run` is whole. A packet outside a GRANDFATHERED tuple (those at ac529ab with no `verify` row) needs one (`verify row missing`). Test `test_suite_rule_sees_through_wrappers`: ADV10-4's nine cells plus plain `make check`.
8. ADV10-5: the launcher bakes `$(realpath $(dir $(PYTHON)))/$(notdir $(PYTHON))` (the venv's link, never its target); the fallback bakes homebrew's `bin/python3` unresolved; a `/Cellar/` path is refused (exit 2). `install-wrapper.sh` checks `CODE` too; when either is gone, `hook` prints `run make install` once (a marker under the state dir naming the path, removed by `make install`) and exits 0; other verbs exit 1.
9. ADV10-7: home paths in `design/packets/*.md`, and each rows file's `prompt`, become repo-relative or a bare repo name; `home` leaves the `design/packets/*.md` allow row. The rows files' `repo` stays `~`-rooted (the stand-in resolves a bare name against its cwd) and `home` stays on `rows-*.json` until ruling 8 lands in both drivers (handover).
10. ADV10-8: a BOM, or NULs at 90% or more of the odd or even bytes of the first 8 KB, decodes as UTF-16, scanned as text. ADV10-9: reads cap at 4 MiB; larger is scanned by path only, counted as `oversize` in `--json`.
11. ADV10-10: `depth()` returns None when set but unparsable; `start` refuses it (exit 2). ADV10-11 (a): conftest removes the sentinel dir at exit (`atexit`, after the poison check).
12. The record: conventions §6 (UTF-16, oversize, both new shas), §7 (the interpreter rule, the one-time message), §9 (`verify` required); overhaul-r1 §4 (unparsable depth refuses; the suite leaves no temp root).

## 3. Interfaces

- `bounded`: exits unchanged; new internal `--guard FD`; the stop line the one stderr addition. `hygiene --json` gains `oversize`. doclint gains `verify row missing`.
- Plan row 22's cell (B only): "built on branch s12b-fixes-adv10 (with s12a merged), every acceptance line green, N passed, awaiting merge (sitting <id>)".

## 4. Findings that name this row

On main ac529ab: 447 tests; conventions 8,172 of 8,192; hygiene ca049635..., doclint 3040666c...; the ten cells in a temp packet with a `verify` row: 1 flagged; rowless 0; UTF-16 0; oversize None; depth 1; `realpath $(PYTHON)` 1; 7 packets and 7 rows files with home paths; one sentinel dir leaked per run; `timeout=` missing in 2; A's selection 15 deselected.

## 5. Forbidden reads

Every other repo; `~/.claude/projects/`; `~/.local/state/`; `history/relay/`; `bugs/`; `design/research.md`; `design/plan.md` beyond row 22; other packets (B: to rewrite paths only); any file over 8 KB whole (`record --section`).

## 6. Report (one table, at most six bullets, under 1,500 words)

The table: your row's acceptance lines, each exit and last line. Bullets: every choice inside the design, with its consumer; the stop line and the 840 s wall for the relay (A); the new shas (B); what was skipped; at most one open fork. The last line: the branch and its head sha.
