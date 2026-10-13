# ADV10: the second adversarial review of claude-code-session at 35a8eb5

One `claude-opus-5-5` reviewer, in the worktree `adv-10-session`. The target is the code landed from cea11b1 (the adv-6 merge) to 35a8eb5. Every finding was reproduced in a temp dir or with a scripted interleaving. Nothing was fixed. This plugin never starts the relay; it starts `claude` only through `start`, and `claude -p` only through `make readme`.

## The ADV6 highs and mediums, as shipped

- ADV6-1 holds. The adv-6 reproduction (keys, a symlink target, a private file name, 172.16/12, a `.local` host, a PNG with a home path) now counts 7 hits and exits 2. ADV10-8 is a gap the fix left.
- ADV6-2 holds only with the relay. The pin test refuses reproduction 1. Reproduction 2 still reads `readme: fresh` once both shas are recomputed. It is closed only by the relay's `GuardedPaths` (the relay's gate package), which refuses a row that touches the sidecar or the allow file.
- ADV6-3 holds for the cwd and the live root. ADV10-5 is a new way for the hooks to go silent.
- ADV6-4 to -8 hold (NEXT exempt, one `git status`, one state root behind a sentinel, parity over fixtures, `record` caps a sum). No regressions.

## Findings

### ADV10-1: the gate's suite outlives the relay's kill (high)
`scripts/bounded:208` starts the command with `start_new_session=True`. The relay's shell runs the verify line in its own group, with a 900 s timeout and a cancel that sends SIGKILL to that group (the relay's effects package, `shell.go:50-51`, `effects.go:133`). The SIGKILL reaches `make` and `bounded`, but not the new session under them. `bounded` cannot forward a SIGKILL, so `make check-unlocked` and pytest run on with no wall. The owner file now names a dead pid, so the next gate takes the lock and a second suite starts beside the first. `bounded` can wait 600 s on load, then 900 s on the wall, so the relay's timer fires first on a loaded machine: the D1 condition. Reproduction (ran): a new-session `make` runs `bounded --wall 600 -- sh -c 'sleep 88.8'`; `killpg(SIGKILL)` on the make's group leaves `sleep 88.8` alive. Fix: give the child a lifeline. `bounded` holds a pipe open to a guardian in the child's group, and EOF on that pipe makes the guardian kill its own group. Also make load wait plus wall plus grace fit inside the caller's timeout (for example, the load wait counted against a wall of 840 s).

### ADV10-2: the check lock is not mutually exclusive (medium)
`scripts/bounded:25,103-126`. There are two failures. (a) The lock treats a holder as stale at 900 s, but a live holder's worst case is 600 + 900 + 5 s, so a second `make check` takes over a live gate. Reproduction: an owner file naming a live `sleep` pid, 901 s old, gives `taking over ... (stale)` and exit 0. (b) The takeover renames the path without re-checking it, so two contenders over one stale lock both hold. Reproduction: B reads the dead holder, A takes over, then B renames A's fresh lock away; both report `held: True`. Fix: use `fcntl.flock` on `.check.lock`. The kernel releases it on any death, including SIGKILL, so there is no staleness guess and no rename.

### ADV10-3: a refused gate reads as a red suite (medium)
`Makefile:43`. `bounded` exits 124 at the wall and 2 on a load or lock refusal, but `make` turns every failing recipe into 2. Reproduction: the wall, a load refusal and a plain `false` all make `make` exit 2. The relay, under ruling 2 (gate reds move on), marks the row red and goes on to spawn the next row on the same loaded machine. A load refusal is `unrun`, never red. Fix: `bounded` prints one last line, `bounded: stop: load|lock|wall`, and the relay reads it as unrun (or the verify line calls `bounded` directly, so its exit survives).

### ADV10-4: the whole-suite acceptance rule is a denylist that 10 of 10 variants pass (medium)
`scripts/doclint:122-164,202`. This is the D1 guard. A temp packet with a `verify` row flags `make check`. It passes all of these: `timeout 900 make check`, `env make check`, `nice make check`, `uv run pytest`, `python3 -m pytest tests`, `pytest .`, `scripts/bounded --wall 900 -- make check`, `sh -c 'make check'`, and `go test -race ./internal/... ./cmd/...`. A packet with no `verify` row is not checked at all. Fix: strip wrapper words (`env`, `nice`, `timeout N`, `uv run`, `bounded ... --`, and the body of `sh -c`) before testing the head. Count a pytest path that is the tests root or `.` as the whole suite. Require the `verify` row on packets dated after today.

### ADV10-5: the launcher pins a versioned Cellar interpreter (medium)
`Makefile:23` (`realpath $(PYTHON)`), and `tests/test_install.py` asserts it. The live launcher holds `PYTHON=` set to homebrew's `Cellar/python 3.14/3.14.7/...` binary (the checkout's `.venv` is brew 3.14.7, not the ruled pyenv 3.12). A routine `brew upgrade` deletes that directory. After that the launcher prints `is gone` and exits 1 on every hook, so the meter, CHECKPOINT and doctor all go quiet in every session until someone runs `make install` again. Doctor runs through the same launcher. ADV6-3's class by another door. Fix: bake the venv's own `bin/python` path, or homebrew's `opt/` link, never the resolved Cellar path. Have the plugin's `hooks/run` shim say `run make install` once instead of failing on every event.

### ADV10-6: `make readme` spawns `claude -p` with no wall (medium)
`scripts/readme-render:53,71`. Every closing sitting runs `make readme` (ruling 11). It runs pytest's collection with no timeout, then respeak's renderer. The renderer runs `claude -p` for up to 2 rounds, with no wall, no lock and no load check. Reproduction (a temp copy): with a renderer that sleeps and fails, `readme-render` simply waits it out (9 s, exit 1). A hung `claude -p` holds the sitting until the relay's stall watchdog fires at 2,700 s. Fix: `readme: scripts/bounded --wall 600 --load 4 -- scripts/readme-render`, and add `timeout=` to both collection runs (this one and `tests/test_readme.py:107`).

### ADV10-7: the allow file admits 27 home-path lines (medium)
`.hygiene-allow` (`design/packets/*.md` and `design/packets/rows-*.json` carry `home`). Hygiene is green on 27 home-path lines in 14 packet and rows files. Two of those files (`rows-2026-09-23-r5.json`, `-r6.json`) landed since run 6. The repo is private today, but its README is written for strangers. The rule respeak got at run 7 (repo-relative rows, and no `home` or `private` rows) never came here. Fix: repo-relative rows (ruling 8's bare repo name), and drop `home` from both rows.

### ADV10-8: hygiene misses UTF-16 text (low)
`scripts/hygiene:139-141`. A NUL in the first 8 KB marks a file binary, and a binary is scanned only over runs of 8 or more ASCII bytes. UTF-16 text has no such runs. Reproduction: a home path written as UTF-16LE gives `hits outside allowlist: 0`. Fix: detect a BOM or alternating NULs and decode the file as UTF-16.

### ADV10-9: hygiene reads each file whole (low)
`scripts/hygiene:137-138`. Hygiene has no size cap. Reproduction: an untracked 400 MB file makes one scan's resident size 437 MB. Fix: cap the read at 4 MB, scan anything larger by path only, and count it as `oversize`.

### ADV10-10: the depth guard fails open (low)
`claude_session/launch.py:58-61`. When `CLAUDE_SESSION_DEPTH` is `1x` or `-1`, depth reads 0 and `start` goes ahead. Reproduction: `start balanced --dry-run` exits 2 at `1`, but at `1x` and `-1` it goes on to the next check (exit 1, no `claude` on PATH). Fix: a set but unparsable depth refuses with exit 2.

### ADV10-11: the suite leaks a sentinel dir per pytest process, and one test runs in the real checkout (low)
`tests/conftest.py:24` creates a directory with `mkdtemp` and never removes it. Each `make check` leaves at least two, because the collection child imports conftest too. `tests/test_readme.py:143` runs the real `readme-render` with `cwd=ROOT`, and only the renderer guard keeps it from stamping the real source. Fix: remove the dir at session end, and run the refusal test in a temp copy.

## Verdict

The plugin is not ready to carry example-app until ADV10-1 and ADV10-2 are fixed. The wrapper built to stop a fork storm leaves an unwalled suite running whenever the relay's timer fires first, which happens most on a loaded machine. Its lock then lets a second suite start beside the first, because the lock keeps neither a live holder nor a racing contender out. ADV10-3 and -4 belong in the same packet: one is a wrong red that keeps a loaded night spawning, the other is a wrong green on the D1 guard. ADV10-5 comes before the next `make install`. ADV10-6 comes before the next README round, and ADV10-7 before the repo goes public. ADV10-8 to -11 can wait. The account-failure stop is the relay's (ruling 1); this repo has no account path.

## The three tests to add first

1. `test_caller_group_sigkill_reaches_the_suite`: a new-session `make` runs `bounded -- sleep`; a SIGKILL to the make's group leaves no `sleep` after 2 s.
2. `test_lock_exclusive_under_takeover`: the ADV10-2 interleaving leaves one holder, and a live holder at any age refuses.
3. `test_suite_rule_sees_through_wrappers`: each of ADV10-4's ten acceptance cells exits 2.
