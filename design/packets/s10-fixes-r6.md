# Packet S10: fixes r6 (ADV6-1 to -9, C1 to C3, E2, E5, E8, the charter-only decisions into the record)

| item | value |
|---|---|
| from | `design/review-adv6.md` and `design/review-r6.md` whole (the reproductions and fixes live there); `design/conventions.md` whole; `record design/overhaul-r1.md --section 2.2,2.4,4,7`; the STANDING WORD (decide inside the design, record, escalate only a real fork). Nothing outside this repo |
| pin | `main` at cea11b1 or later; branch and worktree `s10-fixes-r6`, off main; `.venv` by the §7 symlink |
| wall | this repo only. No push, `--amend`, rebase, device, network; no `make install` (the owner's); no `relay` verb |
| may touch | `scripts/{hygiene,doclint,record,bounded}`, `plugin/scripts/record`, `install-wrapper.sh`, `Makefile`, `.gitignore`, `.hygiene-allow` (new rows), `plugin/hooks/hooks.json`, `claude_session/*.py`, `tests/**`, `design/conventions.md`, `design/overhaul-r1.md` (§2, §4, §7), `design/readme/source.md`, `design/readme/rendered.sha256`, `README.md`, `RUNBOOK.md`, `design/plan.md` (row 22's cell), `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `make check` (the relay's gate line; never an acceptance line) |
| acceptance | `d=$(mktemp -d); git -C $d init -q; printf 'sk-an%s-x\n' t > $d/k.md; ln -s /Us$(printf e)rs/x $d/l; : > $d/home-tec$(printf h).md; scripts/hygiene --repo $d --json \| python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["hits_outside_allowlist"])'; rm -r $d` reads 3; `.venv/bin/python -m pytest -q tests/test_install.py tests/test_bounded.py 2>&1 \| tail -1` reads passed; `d=$(mktemp -d); git -C $d init -q; mkdir -p $d/design/packets $d/history/sessions; printf '\|a\|b\|\n\|-\|-\|\n\|verify\|make check\|\n\|acceptance\|make check; go test ./...\|\n' > $d/design/packets/x.md; : > $d/history/sessions/NEXT; : > $d/NEXT; scripts/doclint --repo $d \| grep -c -E 'runs a whole suite\|next:'; rm -r $d` reads 3; `.venv/bin/python -m pytest -q tests -k 'nested or max_turns or unknown or stdin_paths or total or over_default or boundary or sidecar or timeout or pins' 2>&1 \| tail -1` reads passed, more than 15; `grep -c -E 'CLAUDE_SESSION_DEPTH\|CLAUDE_SESSION_MAX_TURNS\|eight groups\|verify. row' design/conventions.md` reads 4 or more; `grep -c -E 'd9e99149\|4318bc91' design/conventions.md` reads 0; `for f in hygiene doclint; do grep -qF "$(shasum -a 256 scripts/$f \| cut -c1-64)" design/conventions.md \|\| echo $f; done \| wc -l` reads 0; `grep -l '(filled at close)' history/sittings/*-s10-fixes-r6.md \| wc -l` reads 0; `git status --short \| wc -l` reads 0 after the last commit |
| budget | 120 turns (the reason: two reviews, eleven acts), 140k context; commit per act; checkpoint at 80% (96 turns, 112k); never push, amend or rebase. The charter names doclint's five rows at open; `(filled at close)` gone at close |

## 1. What the source says

ADV6: "not ready ... until ADV6-1, -2 and -3 are fixed ... -4 to -8 ... in the same packet". R6 §3: three cycles with NO bound (C1 the gate, C2 nested `start`, C3 hooks); §6: five for the owner, unruled, decided here. D2, D5, D7: fail early, bounded work, group kills; acceptance never runs a whole suite; tests read fixtures under a temp root only.

## 2. Rulings (decided inside the design; the charter records each with its consumer)

Each act: the test first (it reproduces the finding on main), then the fix, one commit. The review's fix is the spec; below, what it left open.
1. ADV6-1: groups `secret` (key prefixes, `BEGIN .* PRIVATE KEY`, spelled not to match itself) and `email`; `lan` adds 172.16/12 and `.local`; each path and symlink target is a scanned line; a binary is scanned for `home` over printable runs of 8+ bytes; a `secret` allow row outside `tests/fixtures/` is a usage error; tests build secrets by concatenation.
2. ADV6-2: the sidecar's second line is `README.md`'s, written by `make readme`, checked by `check` and `test_readme`; a test pins the README and source allow rows to `sibling,person`. The relay's diff guard: handover.
3. ADV6-3: `make install` refuses a dirty `claude_session/` (exit 2), copies it to `~/.local/share/claude-session/<tree>/` (`git rev-parse HEAD:claude_session`; older trees pruned), bakes `CODE=` and `PYTHON=` (make's interpreter by realpath, unprobed; then homebrew's, then `python3`, probed 3.11+), execs `-P -m claude_session`; the floor is 3.11 (doctor, `source.md`, RUNBOOK). Test: a decoy package in the cwd.
4. C1: `scripts/bounded [--lock DIR] [--wall S] [--load N] -- cmd`: own process group, group-killed at the wall (124); the lock a `mkdir` holding pid and start, exit 2 while its pid lives under 900 s, else taken; `--load N` polls 30 s up to 600 s above N x cores, then exit 2. `check` = `scripts/bounded --lock .check.lock --wall 900 --load 4 -- $(MAKE) check-unlocked` (today's `check`, noting a dirty tree first: E1); `validate` under `--wall 60`; `.check.lock` ignored. doclint: with a `verify` row, an acceptance line matching `make (check\|test)`, `go test ./...`, `pytest` without a path or `relay (plan\|run\|gate)` without `--rows` is refused (`acceptance runs a whole suite`); rowless packets grandfathered.
5. C2: `start` sets `CLAUDE_SESSION_DEPTH` (the parent's plus one) after the scrub; at 2 or more it exits 2 unless `--nested`. The relay sets 1 for its children (handover).
6. C3, E8: `timeout` on every `hooks.json` entry: 5 s tool and prompt hooks, 10 SessionStart, 15 SessionEnd; a test walks the file.
7. E5: SessionStart reads `CLAUDE_SESSION_MAX_TURNS`; `ceilings.turns` is the smaller of the profile's and it (`ceilings_source` recorded); `start --max-turns N` sets it. Test: 80 and a 65-turn fixture read past 80%.
8. E2, ADV6-5: a failed `git status` makes `Baseline.dirty` None and checkpoint prints unknown, never clean; blobs by one `git hash-object --stdin-paths`. Tests: a fake git past the timeout; 1,500 untracked files, git called at most 3 times.
9. ADV6-6, -7: `CLAUDE_SESSION_STATE_DIR` retired (D9's path is the contract), `STATE_DIR = state_dir(os.environ)`; an autouse session fixture: `HOME` and `XDG_STATE_HOME` at temp roots, a poisoned `meter.json` under the temp HOME byte-unchanged at teardown (ADV6's test 3); bare `os.environ` writes use monkeypatch; `test_charter` parity over fixtures only.
10. ADV6-4, -8, -9: doclint's `next` rule exempts `history/sessions/NEXT` (the relay's path, tracked or not); `record` caps a request's summed bytes and refuses `--max-bytes` above the default without `--force` (copies identical, asserted); `charter.py` refuses at `>= 4096`, a fixture at exactly 4,096.
11. The record: each R6 §1 `charter` entry into the section the ledger names, T1 to T5 as R6 §2 says (the shebang stays `env python3`), plus conventions §3 the two session variables (dependents still read only `CLAUDE_CODE_SESSION_ID`); §5 the `verify` row, the lock, `validate` bounded, `NEXT` only under `history/sessions/`, `design/review-*.md` under 9,216, the doclint clause a pointer at the docstring (§6's sha pins it); §6 eight groups, the two-line sidecar, the new shas; §7 the frozen install, `-alpha.N` needs no tag, a worktree never writes under `.venv`; overhaul-r1 §4 a row per new invariant (depth at most 1; null never clean; hooks time-bound; one gate per tree; acceptance targeted; the suite never reads `$HOME`), §7 a header line: all ruled by 2026-09-23. Conventions under 8,192: tighten §5; else `CONVENTIONS_CEILING` 9,216, recorded.
R6 §6: 1 to 4 yes (acts 4 to 7); 5 yes, the global CLAUDE.md line is the owner's (handover). ADV6-10 to -13: a later packet. `make readme` at most twice.

## 3. Interfaces

- hygiene: `GROUPS` gains `secret`, `email`; `scan` feeds `path` and `os.readlink(full)` to the same counters; `load_allow` refuses `secret` outside `tests/fixtures/*`; `--json` shape unchanged.
- doclint: `PACKET_SUITE` over the `acceptance` cell when a `verify` row exists; `check_sizes` adds `design/review-*.md` at `PACKET_CEILING`.
- `scripts/bounded`: stdlib; exit the command's, 124 wall, 2 lock or load, 1 usage. New tests `test_install.py`, `test_bounded.py`. Plan row 22's cell: "built on branch s10-fixes-r6, every acceptance line green, N passed, awaiting merge (sitting <id>)".

## 4. Findings that name this row

On main cea11b1: 334 passed; conventions 8,116 bytes; hygiene d9e99149..., doclint 4318bc91...; the hygiene probe reads 0; no `timeout` in hooks.json; `.venv/bin/python` is 3.14 (`-P` exists). C4 to C6 untouched.

## 5. Forbidden reads

Every other repo; `~/.claude/projects/`; `~/.local/state/`; `history/relay/`; `bugs/`; `design/research.md`; `design/plan.md` beyond row 22; the other packets; any file over 8 KB whole (`record --section`).

## 6. Report (one table, at most six bullets, under 1,500 words)

The table: each acceptance line, its exit and last output line. Bullets: every choice inside the design, with its consumer; both new shas for the three re-sync rows (`email` rows; the `verify` row); the relay's consumers (depth 1, `CLAUDE_SESSION_MAX_TURNS`, the diff guard on `.hygiene-allow` and the sidecar); renders and allow rows added; what was skipped; at most one open fork. The last line: the branch and its head sha.
