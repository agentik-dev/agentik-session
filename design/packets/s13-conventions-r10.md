# Packet S13: the conventions packet after run 10 (the rulings of 2026-09-24), two rows in order

| item | value |
|---|---|
| from | the owner's rulings of 2026-09-24 (§1); agent-relay's `internal/packet/packet.go` (`Unbounded`, `makeSuite`, `stdinShell`, `legacy`, `spent`) by `grep -n`/`sed -n` only; conventions §5, §6, §9; the STANDING WORD |
| pin | `main` at 330bded or later. Your row is your branch (`git branch --show-current`): `s13a-conventions-r10` does §2 part A; `s13b-conventions-r10` does part B, its act 0 `git merge --no-ff s13a-conventions-r10`. `.venv` by the §7 symlink |
| wall | this repo only (agent-relay read-only, the file above). No push, `--amend`, rebase, device; no `make install` (the owner's); no `relay` verb; logs to `mktemp`. Network: B's one `make readme` at close only |
| may touch | A: `scripts/{doclint,hygiene}`, `tests/test_doclint.py`, `tests/test_hygiene.py`. B: `scripts/bounded`, `tests/test_bounded.py`, `claude_session/doctor.py`, `tests/test_doctor.py`, `design/readme/source.md`, `README.md`, `design/readme/rendered.sha256`. Both: `design/conventions.md`, `design/overhaul-r1.md` §4, `design/plan.md` (row 23, new), `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `make check` (the relay's gate line; never an acceptance line) |
| acceptance | A: `.venv/bin/python -m pytest -q tests/test_doclint.py -k 'shape or legacy or spent' 2>&1 \| tail -1` reads passed, 11 or more; `d=$(mktemp -d); git -C $d init -q; mkdir -p $d/design/packets; printf '\|a\|b\|\n\|-\|-\|\n' > $d/design/packets/ar9-queue-and-resync.md; scripts/doclint --repo $d \| grep -c 'verify row missing'; rm -rf $d` reads 0; `d=$(mktemp -d); git -C $d init -q; printf '\0 abcd%sexample.org sk-an%s-abcdefghij\n' @ t > $d/b.bin; scripts/hygiene --repo $d --json \| python3 -c 'import json,sys;g=json.load(sys.stdin)["groups"];print(g["email"]["lines"],g["secret"]["lines"])'; rm -rf $d` reads `1 1`; `.venv/bin/python -m pytest -q tests/test_hygiene.py -k nul 2>&1 \| tail -1` reads passed; `for f in hygiene doclint; do grep -qF "$(shasum -a 256 scripts/$f \| cut -c1-64)" design/conventions.md \|\| echo $f; done \| wc -l` reads 0. B: `.venv/bin/python -m pytest -q tests/test_bounded.py -k sigterm 2>&1 \| tail -1` reads passed; `f=$(mktemp); scripts/bounded -- sleep 30 2>$f & p=$!; sleep 1; kill -TERM $p; wait $p; echo $? $(grep -c Traceback $f); rm -f $f` reads `143 0`; `.venv/bin/python -m pytest -q tests/test_doctor.py -k 'max_turns or meter_hook' 2>&1 \| tail -1` reads passed; `grep -c 'turns line' design/conventions.md` reads 1 or more; `grep -c '900 s' README.md design/readme/source.md \| grep -c ':0'` reads 2; `shasum -c --status design/readme/rendered.sha256; echo $?` reads 0. Both: `grep -l '(filled at close)' history/sittings/*-s13?-conventions-r10.md \| wc -l` reads 0; `git status --short \| wc -l` reads 0 at the end |
| budget | 80 turns per row, 140k context; commit per act; checkpoint at 80% (64 turns, 112k); never push, amend or rebase. The charter names doclint's five rows at open; `(filled at close)` gone at close |

## 1. What the source says

The owner, 2026-09-24: grandfather agent-relay's 17 pre-AR10 stems; "please address" the turn cap: the session plugin is not installed here, so its meter hook never runs in relay children and the prompt's "Your `--max-turns` is N" line is their only cap. Run 10's handovers (agent-relay ar17c, packets-35, ar18; decisions d12): doclint passes six shapes the Go relay refuses; hygiene scans a NUL-byte file for `home` only (ADV10-17); `bounded` 63cebd3d exits 1 with a traceback on SIGTERM without `--wall`. D2: fail early, one rule in two languages, temp roots only.

## 2. Rulings (decided inside the design; your charter records each with its consumer)

Each act: the test first (it reproduces the finding on main), then the fix, one commit.

**Part A, `s13a-conventions-r10` (lint and hygiene):**
1. GRANDFATHERED gains agent-relay's 17 stems (`a3-machine` to `a9-tmux-notify`, `ap1-plugin`, `ar2-adversarial` to `ar9-queue-and-resync`, `ux1-review`, each `.md`). Confirm against `packet.legacy` by `grep -n`. Test `test_legacy_stems_need_no_verify`: all 17 are in the list and a rowless temp packet named for one is clean.
2. A new `SPENT = ("ar11-tla-night.md", "ar12-e2e-night.md")` mirrors Go's `spent`: the verify row is still required, but the suite rule is skipped. Else ruling 3 turns their `make tla`/`make e2e` records red (the only two hits across the four repos, §4). Test `test_spent_skips_the_suite_rule`.
3. `runs_suite` mirrors `packet.Unbounded` by shape, not by spelling. A command word that is not a literal word (`$`, backtick, glob or brace chars) is refused. So is a shell fed from stdin: no operand, `-s`, a lone `-c`, `<` or a here-string, or a shell as the last stage of a pipe. `make` or `gmake` with no target is refused, and so is a target in check, `check-*`, test, vet, e2e or tla (make's valued options skipped as `makeValued`). The existing go, relay and pytest rules stay. Parametrized `test_acceptance_shape_refused`, one id per shape: `make e2e`, `make vet`, `make tla`, bare `make`, `gmake check`, `$(echo make) check`, `m=make; $m check`, `echo 'make check' \| sh`. Controls in `test_acceptance_shape_allowed`: `make doclint hygiene`, `make -n decisions X=y`, `sh -c 'true'`. Blanking quotes must not hide the piped shell. Go rules with no twin here (`claude`, `go run .../relay`) are added and named.
4. ADV10-17: `BINARY_GROUPS` becomes home, secret and email, over the same printable runs. Test `test_nul_file_scans_secret_and_email`. `assets/` stays clean; a new hit is named, never allowed without a reason.
5. The record: conventions §6 (binary groups, both new shas) and §9 (GRANDFATHERED holds the 19 unrowed packets, and SPENT is the two that skip the suite rule); overhaul-r1 §4, one row (the two linters agree by shape).

**Part B, `s13b-conventions-r10` (bounded, doctor, README):**
6. d12's finding: `on_signal` never calls `Popen.wait`, because the main thread's blocking `waitpid` holds its lock. It closes the lifeline, then polls `os.waitpid(pid, WNOHANG)` until grace plus 1 s. `ChildProcessError` counts as reaped. Every `killpg` in `cut` and `kill_group` tolerates `ProcessLookupError` and `PermissionError`. Exit `128 + signum`, no traceback, with or without `--wall`. Invariant: no group member outlives the signal by more than grace plus 1 s. Test `test_sigterm_without_wall_exits_143`: exit 143, no `Traceback` on stderr, the sleep's pid gone within 2 s.
7. The doctor: `CLAUDE_FLAGS` drops `--max-turns`, because the flag is accepted but unlisted in `--help`. Not probed (a probe costs a turn); the line says so. A new `meter-hook` line reports live when `session@claude-code-session` is installed, enabled and registers PostToolUse. Otherwise it reports not live, with the reason and "packet prompts keep the turns line (conventions §5)". A report, `ok` either way. Tests `test_claude_check_passes_without_max_turns_listed` and `test_meter_hook_line_live_and_not`, both on fake `claude` binaries.
8. Conventions §5: "packet prompts keep the turns line (`Your --max-turns is N`) until the doctor reads the meter hook live". Room: conventions 8,683 of 9,216. Tighten; never raise the ceiling here.
9. README: `design/readme/source.md` says 840 s where it says 900 s (the relay's own 900 stays where it names the relay). Then `make readme` once at close, the last act, and the rendered sha is fresh. If the renderer is absent (exit 2, `no respeak renderer`), record that and leave the sha stale. Never hand-edit `README.md`.
10. The record: overhaul-r1 §4, one row (a signal never waits under the main thread's lock). Plan row 23: S13, "built on branch s13b-conventions-r10 (s13a merged), N passed, awaiting merge (sitting <id>)".

## 3. Interfaces

- doclint: new refusals only, same message (`acceptance runs a whole suite`). hygiene `--json` unchanged. bounded exits unchanged. doctor: one new line, `meter-hook`.
- The re-sync round (packets-37) copies `scripts/{hygiene,doclint,bounded}` and moves three shas. Name all three, and the tests that travel, in your report.

## 4. Findings that name this row

On main 330bded: a rowless `ar9-queue-and-resync.md` reads 1 `verify row missing`; the NUL line reads `0 0`; the SIGTERM line reads `1 2` (exit 1, two `Traceback` lines); conventions 8,683 bytes, shas efc59152 (hygiene) and b924a7bc (doclint); README and source each say 900 s once (line 123); across the four repos' packets with a verify row, only agent-relay's ar11 and ar12 carry a newly refused shape.

## 5. Forbidden reads

Other repos but the agent-relay file in `from`; `~/.claude/projects/`; `~/.local/state/`; `history/relay/`; `bugs/`; `design/research.md`; `design/plan.md` beyond row 23; other packets; any file over 8 KB whole (`record --section`).

## 6. Report (one table, at most six bullets, under 1,500 words)

Table: your acceptance lines, exit and last line. Bullets: choices with consumers; new shas (A: hygiene, doclint; B: bounded); any stem or shape differing from Go; whether `make readme` rendered; skips; at most one fork. Last line: branch and head sha.
