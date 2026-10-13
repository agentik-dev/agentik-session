# ADV11: the third adversarial review of claude-code-session at 35b5870

One `claude-opus-5-5` reviewer, in the worktree `adv-11-session`. The target is the code landed from ac529ab (the adv-10 merge) to 35b5870: packets S12a, S12b, S13a and S13b (`scripts/bounded`, `doclint`, `hygiene`, the launcher, the depth guard, the doctor). Every finding was reproduced in a temp dir. Nothing was fixed.

## The ADV10 highs and mediums, as shipped

- ADV10-1 holds. A new-session `make` runs `bounded --lock L --wall 600 -- sh -c 'sleep 66.6'`; a SIGKILL to the make's group leaves no `sleep` after 2.5 s. ADV11-1 is the one path left.
- ADV10-2 holds. A second `bounded --lock` beside a live holder exits 2 with `stop: lock`; `flock` leaves no takeover to race.
- ADV10-3 holds. Through `make`, the last line that is not make's trailer is `bounded: stop: ...`, and the relay's reader skips the trailer. ADV11-2 is a wrong unrun by the same door.
- ADV10-4 holds for its ten cells: all ten flag now. The rule is still a denylist; see ADV11-4.
- ADV10-5 holds for the Cellar path (refused at install). The live launcher bakes the checkout's `.venv/bin/python`. ADV11-5 is how it now goes quiet.
- ADV10-6 holds: `make readme` is walled at 600 s, and both collections time out at 120 s.
- ADV10-7 holds: no packet carries a home path, and the packets row no longer admits `home`. Eight older rows files keep a `~`-rooted `repo`, admitted by a noted row.
- No regressions.

## Findings

### ADV11-1: bounded's fallback kills the guardian, not the command's group (medium)
`scripts/bounded:236-251` (`cut`). At the wall, `bounded` closes the lifeline and waits grace plus 1 s for the guardian. If the guardian has not finished, `bounded` sends SIGKILL to the guardian's group. That group is the guardian alone: the command runs in its own group (`process_group=0`, line 208). A guardian that is stopped, or starved on a loaded machine, dies with the command's group still alive and unwalled. The `flock` goes with the guardian, so the next gate starts a second suite beside it: ADV10-1's class. Reproduction (ran): `BOUNDED_GRACE=1 bounded --lock L --wall 3 -- sh -c 'sleep 77.7'`, with the guardian sent SIGSTOP at 1 s. `bounded` exits 124, `stop: wall`. `sleep 77.7` is still alive, and a second `bounded --lock L` runs at once, exit 0. Fix: the guardian reports the command's pgid (on the pipe, or in the owner file), and `cut`'s fallback kills that group before it kills the guardian. Or the command stays in the guardian's group, so one `killpg` reaches both.

### ADV11-2: a nested bounded's stop line reads as the gate's (medium)
`Makefile:60-62` (`validate` runs `scripts/bounded --wall 60`) under `check`'s own `bounded`. When the inner wall fires, its `bounded: stop: wall` is the last line that is not make's trailer, so the relay reads the whole gate as unrun. In fact the suite ran to its end and `validate` failed. Reproduction (ran): an outer `bounded -- $(MAKE) inner`, where `inner` runs `bounded --wall 1 -- sleep 5`. The outer exits 2. Its stderr ends `bounded: stop: wall`, `make[1]: *** ... Error 124`, `make: *** ... Error 2`. A branch that makes `claude plugin validate` hang reads unrun on every gate, never red. Fix: the stop line names its own depth or pid, and only the outermost counts. Or `validate` uses `timeout 60`, so a hang there is a plain red.

### ADV11-3: hygiene reads a file over 4 MiB as clean (medium)
`scripts/hygiene:162-167`. ADV10-9's fix scans an oversize file by its path only and counts it, but the count never fails the scan. Reproduction (ran): a repo whose one untracked file is 4 MiB of `x` followed by a home path gives `oversize (scanned by path only): 1`, `hits outside allowlist: 0`, exit 0. Transcripts, logs and ledgers are the files that pass 4 MiB, and they are full of home paths. Fix: stream the file in 1 MiB chunks, with a line of overlap, so memory stays bounded and coverage is whole. Or make `oversize` a refusal unless an allow row names it.

### ADV11-4: the suite rule still passes 18 new shapes (medium)
`scripts/doclint:163-275`. This is the D1 guard. ADV10-4's ten cells flag now, but the rule still strips a closed list of wrappers and then tests a denylist. Reproduction (ran, through `suite_lines`). These all pass: `caffeinate -i make check`, `stdbuf -oL make check`, `arch -arm64 make check`, `xargs make check`, `python3 -I -m pytest`, `python3 -X dev -m pytest tests`, `py.test`, `pytest tests/test_*.py`, `pytest tests/..`, `pytest ./tests/../tests`, `pytest -k '' tests`, `pytest -k 'not zzz'`, `go test -run . ./...`, `go test $(go list ./...)` and `go test all`. So do `make readme` (two `claude -p`), `make install` and `make skill` (both write the owner's home). Fix: fail closed. An acceptance line passes only when it matches a targeted shape (pytest with a file below the tests root, `::` or a non-empty `-k`; `go test` with named packages and a non-wildcard `-run`; `make` of a target outside the suite and home-writing set). Every other line is refused. The relay's `packet.Unbounded` should be run on the same cells.

### ADV11-5: a gone interpreter silences the hooks for good, and nobody sees it (medium)
`install-wrapper.sh:14-23`. When `PYTHON` or `CODE` is gone, a `hook` writes one stderr line, writes a marker and exits 0. Claude Code does not show a hook's stderr on exit 0, and the marker makes every later session silent. So the meter, CHECKPOINT and the `deny` posture's spawn gate (`hooks.py:121`) all fail open with no signal. The baked `PYTHON` is the live checkout's `.venv/bin/python`, so a `make venv` or a removed `.venv` is enough to trigger it. Reproduction (ran): a wrapper baked with a missing python, called as `hook PreToolUse` in three "sessions", prints the line once and exits 0 each time. Fix: on `SessionStart`, print `{"systemMessage": "claude-session: <path> is gone; run make install"}` in every session (the shell can print JSON). Keep the marker for the other events only.

### ADV11-6: the load breaker admits a herd (low)
`scripts/bounded:131-153`. The per-tree lock bounds one tree. The only bound across trees is the 1-minute load average, which lags by about a minute. Reproduction (ran): on 16 cores at load 7.9, 32 CPU-bound `bounded --lock .check.lock --load 1` in 32 dirs all ran; load rose to 17.6, above the ceiling of 16. Fix: a machine-wide counting semaphore (k `flock` slots under the state dir) taken before the load check.

### ADV11-7: hygiene misses UTF-32, and UTF-16 with non-Latin text (low)
`scripts/hygiene:136-150`. A home path in a UTF-32 file decodes as UTF-16 with NULs between the characters. In a UTF-16LE file with no BOM and 12 CJK characters first, less than 90% of the odd bytes are NUL, so the file is read as binary, with no printable runs. Both read 0 hits. Fix: detect UTF-32 by its NUL pattern and BOM, and lower the parity test to "most NULs on one parity" with no NUL pairs.

### ADV11-8: the grandfathered list goes by basename (low)
`scripts/doclint:66-78,340-343`. A new packet named `a3-machine.md` (an agent-relay stem) with acceptance `make check` and no `verify` row passes. The same packet named `s14-new.md` refuses. Fix: grandfather by path and blob sha, or by the commit that added the file.

### ADV11-9: `start --nested` has no ceiling, and a blank depth reads 0 (low)
`claude_session/cli.py:57-65`, `launch.py:59-65`. `CLAUDE_SESSION_DEPTH=99 start balanced --nested --dry-run` goes ahead at depth 100. A child that sets the variable blank reads as a terminal. Fix: a hard ceiling (3) that `--nested` cannot pass, and a set-but-blank depth refuses like an unparsable one.

### ADV11-10: bounded takes `nan` and `inf` (low)
`scripts/bounded:52-75`. `--wall inf` and `--wall nan` run the command with no wall, exit 0, and `--load inf` turns the breaker off. Fix: refuse a value that is not finite (`math.isfinite`).

## Verdict

The plugin is ready to carry example-app once ADV11-1 and ADV11-4 land; both are small. ADV11-1 is the last way the gate's suite can outlive its wall and its lock: narrow, but exactly the load condition of D1. ADV11-4 is the D1 guard, still a denylist, and it should fail closed. The relay's parser needs the same cells, so its reviewer should run them. ADV11-2, -3 and -5 belong in the same packet: a wrong unrun, a wrong green on the public scan, and a spawn gate that fails open with no signal. ADV11-6 to -10 can wait. This repo has no account path; the account stop is the relay's.

## The three tests to add first

1. `test_stopped_guardian_does_not_leak_the_suite`: SIGSTOP the guardian, reach the wall, and assert that no command survives and that a second `--lock` refuses until the group is gone.
2. `test_suite_rule_fails_closed`: each of ADV11-4's 18 cells exits 2, and a pytest file path, `::` or `go test ./pkg -run TestX` passes.
3. `test_hygiene_oversize_is_scanned`: a 4 MiB + 1 file ending in a home path gives one `home` hit.
