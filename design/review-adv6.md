# ADV6: the adversarial review of claude-code-session at c7dbdee

One `claude-opus-5-5` reviewer, in the worktree `adv-6-session`. I read every module, script, hook, command and skill, and the tests. Each finding below was reproduced in a temp dir or with one targeted test. Nothing was fixed. The fork-storm class (defects D1 to D7) comes first. The plugin never starts `claude`, the relay or `make`, so no process here can start its own ancestor. The unbounded work it does have is one fork per dirty file (ADV6-5).

## Findings

### ADV6-1: hygiene passes secrets, symlinks, file names and binaries (high)
`scripts/hygiene:28-36,106,111`. Reproduction: a temp repo with each of the following committed:
- a symlink whose target is a home path in a private sibling;
- a file named after the owner and a private repo;
- an `sk-ant-` key, a `ghp_` token and an `AGE-SECRET-KEY-1` line;
- a `172.20.x` address and a `nas.local` host;
- a PNG that carries a home path.

`scripts/hygiene` prints `hits outside allowlist: 0`, exit 0 (the symlink's blob is the path, per `git cat-file`). It has no secrets group, no email or RFC 1918 172.16/12 rule, and no `.local` rule. It never scans paths or link targets, and it skips every binary. The scanner is copied byte-identical into respeak, which is public. Fix: add a `secret` group (the key prefixes, `BEGIN .* PRIVATE KEY`), an `email` group and 172.16/12. Scan each path and each symlink target (`readlink`), and scan binaries for the `home` group with `strings`.

### ADV6-2: the gate's own sidecars can be edited to green (high)
`.hygiene-allow`, `design/readme/rendered.sha256`, `Makefile:28-30`. Reproduction 1: add `README.md: home,person` to `.hygiene-allow` and a README that holds a home path goes from exit 2 to exit 0. Reproduction 2: hand-edit `README.md`, append to `source.md`, rerun `shasum -a 256 source.md > rendered.sha256`, and the check prints `readme: fresh`. The sidecar hashes the source, never the rendered README, so a hand-written or stale README passes. Fix: the sidecar also carries README.md's sha. The relay's gate refuses a row whose diff touches `.hygiene-allow` or the sidecar unless its packet names that file.

### ADV6-3: every hook on the Mac runs the live root checkout, or the cwd's tree (medium)
`install-wrapper.sh:9-12`, `Makefile:20`. `~/.local/bin/claude-session` has `REPO=` set to the root checkout. Merges land in that tree, and another sitting reviews there now. Reproduction: add a conflict marker to a copied `meter.py` and the wrapper exits 1 with `SyntaxError` on `hook PostToolUse`. So one bad merge, or a merge caught mid-conflict, silences the meter and CHECKPOINT in every session. Also, `python -m` puts the cwd first on `sys.path`. From any directory that holds `claude_session/` (every worktree of this repo), the hook runs that tree's code instead: reproduced, `shadowed by the cwd tree`. A builder's half-done edit drives the meter that tells the builder when to stop. Fix: install a frozen copy (`~/.local/share/claude-session/<sha>`) and run it with `python -P` (or `-I`), so neither the root nor the cwd can change a hook.

### ADV6-4: a NEXT file makes `make check` red (medium)
`scripts/doclint:236`. The relay tells a sitting to write `history/sessions/NEXT` for a safe next phase. doclint refuses any file named NEXT, tracked or untracked-not-ignored, and `.gitignore` does not cover it. Reproduction: `history/sessions/NEXT` gives `next: a NEXT file is present`, exit 2. So a sitting that follows the contract fails its own verify. Fix: either gitignore `history/sessions/NEXT` or exempt that path. The owner's contract asks for a committed or a working-tree NEXT, and the fix follows whichever it is.

### ADV6-5: checkpoint forks git once per dirty path, with no cap (medium)
`claude_session/gitinfo.py:105-109`, which `cli.py:459` calls only to print "(tree is dirty)". Reproduction: 1,500 untracked files mean 1,500 `git hash-object` runs and 13 s (5 s timeout each, so the worst case is 2 hours). It is the D1 class, work in proportion to the input with no budget. Fix: `checkpoint` needs only `git status --porcelain`. Where blobs are needed, one `git hash-object --stdin-paths`.

### ADV6-6: two state roots, and tests read the user's (medium)
`claude_session/config.py:16-30`. `CLAUDE_SESSION_STATE_DIR` moves the overlays and configs but not `sessions/` or the ledger, which follow `XDG_STATE_HOME` or `~/.local/state`. Reproduction: with that variable set to a temp dir, the overlay lands there, while `resolved.json`, `meter.json` and `meter-state.json` land under `$HOME`. `tests/test_hooks.py` and `tests/test_cli.py` patch `config.STATE_DIR` only. Planting a `meter.json` for the test's SID under `XDG_STATE_HOME` fails `test_no_meter_means_no_opinion` and `test_zero_cadence_disables_nudging`. So the suite reads the real state root. `test_hooks.py:27` and `test_sessionconfig.py:74` also set `os.environ` without monkeypatch, which leaks into later tests. Fix: one root function, plus an autouse conftest fixture that points `HOME`, `XDG_STATE_HOME` and `CLAUDE_SESSION_STATE_DIR` at `tmp_path`.

### ADV6-7: a unit test reads the live `history/sittings/` (medium)
`tests/test_charter.py:15,65-68` (D7 class). Reproduction: my draft charter, untracked, with its title not yet in shape, fails `test_parity_with_doclint_on_every_sitting`. Any sitting's open charter in a shared tree turns `make test` red, and doclint already gates those files. Fix: run the parity check over the fixtures only.

### ADV6-8: `record` serves a whole file through a range (medium)
`scripts/record:183-190` (the plugin's copy is identical). The 8 KB cap applies to each section, never to the total, and `--max-bytes` takes any value without `--force`. Reproduction: a 320 KB file of 40 sections, `--section 1-40`, serves 325,312 bytes at exit 0. `--max-bytes 999999999` does the same as `--force`. Fix: cap the summed bytes of a request, and treat a `--max-bytes` over the default as `--force`.

### ADV6-9: `charter close` writes a file doclint refuses (low)
`claude_session/charter.py:62,168` checks `> 4096`; `scripts/doclint:99` checks `>= 4096`. Reproduction: close a charter to exactly 4,096 bytes. `charter.check` returns `[]` and doclint says `4096 bytes, ceiling 4096`, exit 2. The parity test only covers files that exist. Fix: use `>=` in charter.py and add a boundary case to the parity fixtures.

### ADV6-10: parallel PostToolUse hooks race on a fixed temp name (low)
`meter.py:201-206`, `resolver.py:253-258` (`<name>.tmp`). Reproduction: two processes writing `meter-state.json` 2,000 times each: `os.replace` fails 37 to 127 times per run. `dispatch` swallows the error, so that tool's meter and D13 signal update is lost. Fix: `store._write_private`, which already uses `mkstemp`.

### ADV6-11: the meter state grows without a bound (low)
`meter.py:119,124`. `seen` and `msgs` keep every turn of the session and of every builder, and the whole file is rewritten on every tool call. Measured: 60 builders at 1,000 turns each make a 2.3 MB `meter-state.json`, rewritten per call (35 ms). Fix: keep running sums and the context list's median by a two-heap, not the rows.

### ADV6-12: timeouts kill the child, not its group (low)
`doctor.py:133` (20 s, runs `claude`), `gitinfo.py:25`. `subprocess.run(timeout=)` kills the one process it started, so node's own children can survive (D2.6). Fix: `start_new_session=True` and `os.killpg` on timeout.

### ADV6-13: doclint accepts links that leave the repo; launch loads live checkouts (low)
`scripts/doclint:230`. A relative link to a path outside the repo resolves locally, so it passes, but it is dead on GitHub. Reproduced with `/etc/hosts`, exit 0. Fix: the link must `realpath` under the repo root. Separately, `launch.py:25-28` searches the code directory under `$HOME` before the installed plugins, so a profile's `plugins` loads a sibling's working tree, mid-edit or not. Fix: search the plugin cache first, or name the source in the profile.

## Verdict

Not ready to carry example-app until ADV6-1, -2 and -3 are fixed. With 1 and 2 open, the public-hygiene gate is a wrong green: a builder can publish a secret, a symlink or a personal path in a public repo and pass the gate. With 3 open, the budget signal that bounds every sitting runs code that a merge or the builder itself can break or change. ADV6-4 to -8 should land in the same packet, because each is a wrong red or unbounded work on the relay's path. ADV6-9 to -13 can wait. No fork storm can start here. The one unbounded fan-out is ADV6-5.

## The three tests to add first

1. `test_hygiene_catches_secret_symlink_and_path`: the ADV6-1 temp repo (key prefixes, a symlink to a home path, a file named for a private repo) exits 2.
2. `test_hook_runs_installed_code_not_cwd`: from a cwd holding a decoy `claude_session/`, `hook PostToolUse` returns the installed code's output.
3. `test_suite_never_touches_the_user_state`: an autouse sentinel. `XDG_STATE_HOME` and `HOME` are temp dirs holding a poisoned `meter.json`; the whole module list runs, and the sentinel files are still unread (atime) and unchanged.
