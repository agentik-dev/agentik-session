# Packet sc2: the move

| item | value |
|---|---|
| from | the suite's build order item 17, build 2 of the Fable review; the suite's design/04, the self-contained plugins ("design/04" below) §7 item 2, §2, §3, §5 step 1, §6; the suite's entry 6 at a 3.9 floor; sc1's go (`design/packets/sc1-proof*.md`) |
| pin | 970fff9 (main, alpha.37); worktree `.claude/worktrees/sc2-move`, branch `sc2-move`, cut, its `.venv` and `.venv-floor` links |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test or proof never writes under the live state folder, the real `~/.claude`, or the real `~/.config/agentik`; **no test or probe touches the real `~/.config/agentik/hooks-follow-launcher`**; no relay verb, no relay binary built or run; no `pkill` by name or pattern; never a gate verb by hand under a temp HOME, never a typed `kill`; a Python probe needs PYTHONPATH=<worktree> |
| may touch | `claude_session/` to `plugin/lib/claude_session/` by `git mv`, `plugin/lib/agentik-session` (new), `plugin/bin/` (new), `plugin/hooks/run`, `plugin/hooks/session.ts` (the mod's root only), `plugin/scripts/record`, `plugin/.claude-plugin/plugin.json`, `plugin/lib/claude_session/{gate,doctor,hooks}.py` as §2 names, `install-wrapper.sh`, `Makefile`, `pyproject.toml`, `scripts/bare-proof`, `scripts/` and `tests/` for the new paths, `tests/test_bare_machine.py` (new), `README.md`, `RUNBOOK.md`, `design/readme/*`, `NICE_TO_HAVE.md`, this packet, the charter |
| acceptance | §3's table, each row's figure in the report; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last. `gate wait` exits 0 whatever the job's code: read the code from its line |
| budget | acts: 0 this packet as `design/packets/sc2-move.md`, committed first; 1 the `git mv` and every path, the suite green, no behaviour change; 2 the runner, `plugin/bin/` and the shim; 3 the switch and its doctor and `systemMessage` lines; 4 `SEMVER` from `plugin.json`, the mod's root, `spawn_serve`, `record`; 5 the tests of §3; 6 the docs; 7 the version, last, one bump. 150 tool calls, stop at 80% (commit the act in flight, name the resume line), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

Read first, by sections, never whole (`/session:read`): design/04 §2, §3, §5, §6, §7 (its first paragraph, the bare-machine test, item 2), §8, §9, §12; `design/packets/sc1-proof-a2.md`; then the research survey of this tool.

## 1. What the source says: what this is, and what it is not

Move the Python package into the plugin as its only home, so the plugin runs with no clone, venv or launcher. Hooks stop using PATH. **Not here:** `install-cli` and the launcher's move to Apple's Python (sc3); commons' copy (c1); the `suite` plugin (c2). `make install` and `install-wrapper.sh` keep today's form except for paths, so this Mac's launcher keeps working until sc3.

## 2. Rulings

1. **The move** is `git mv claude_session plugin/lib/claude_session`, no copy. A synced second tree is what design/04 §2 rejects.
2. **The runner and launcher** are design/04 §2's forms verbatim: `plugin/lib/agentik-session` (four lines: its own directory first on `sys.path`, call `main`) and `plugin/bin/agentik-session` holding `py=${AGENTIK_PYTHON:-/usr/bin/python3}; [ -x "$py" ] || py=$(command -v python3) || <no python>` and `exec "$py" -I -X pycache_prefix="${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache" "$root/lib/agentik-session" "$@"`. With no Python a hook exits 0 and SessionStart says so in a `systemMessage`; other verbs exit 3 (GUIDE §10) is sc3's for the launcher, and this bin may already do it. `agentik` also ships in `plugin/bin/`, per §3 item 2.
3. **The shim** runs `${CLAUDE_PLUGIN_ROOT}/bin/agentik-session`, never `command -v`, with the switch's two lines of design/04 §3 verbatim, off by default. The shim's measuring from S49 stays, exits unchanged.
4. **The switch**, the owner's answer §10 item 2: one file, `~/.config/agentik/hooks-follow-launcher`, its existence the whole state; regular file only, under 24 h by mtime; the target a fixed path; only `HOME` read, no `AGENTIK_*`, no `XDG_CONFIG_HOME`. No verb, profile, `session set` key or config layer creates it. While on, the doctor warns and SessionStart's `systemMessage` says so. RUNBOOK gets the emergency's lines: land the fix, `make install`, `touch` the file, `rm` it once sessions have respawned. **This code has never been refuted** (design/04 §12): say so to the refuter by leaving nothing out.
5. **`SEMVER` and `__version__` read `plugin.json`**, the one pin, in a way that works from a frozen tree too. `pyproject.toml` keeps what `make install` still needs; the builder decides, one sentence.
6. **`spawn_serve`** (`gate.py:478`) moves to the `-I <runner>` form with the prefix, so the gate's runner writes no bytecode elsewhere. **The bytecode row of the bare-machine test goes strict**: any .pyc under `$T` outside the prefix fails it, with no `spawn_serve` exception.
7. **`plugin/scripts/record`** goes to `#!/usr/bin/python3`.
8. **The bare-machine test joins the suite:** `tests/test_bare_machine.py` runs `scripts/bare-proof` or its core on the moved tree. **The mock stops assembling a package**: `git archive HEAD plugin` is now the whole plugin. The runner's one swallow-watch seam stays test-only, and the shipped runner stays four lines.
9. **The floor in `make check`**, design/04 §6: `make test` also runs under `.venv-floor`, `test_bounded.py` excepted. With no `.venv-floor`, it says `floor: absent` and goes on, as agents' `pin: absent` does. The check's wall of 840 s must still hold; report the seconds.
10. **State is additive across one version step, and a reader ignores keys it does not know** (design/04 §3): the new test feeds old-format and unknown-key state to every reader, and a real reader that fails it is a fix on this path.
11. **The version:** 2.0.0-alpha.38, one bump, last; the README count from the suite; the sidecar re-hashed by hand. The install is hq's, and hq reads the canary (§5 step 2) before sc3.

## 3. Interfaces: the acceptance table

| what | reads |
|---|---|
| the bare-machine test | in the suite, green, under `make check`: env exactly `HOME=$T`, `PATH=/usr/bin:/bin`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, a decoy in the cwd; every sc1 row, the 15 mutants of sc1's Amendment 2 still red by `$SP/mut.py` where they still apply, a mutant updated when the move changes its path |
| §3's switch test, both states | a decoy launcher at `$T/.local/bin/agentik-session` writes a marker. Off: ten events, no marker, with the decoy first on PATH and `XDG_CONFIG_HOME` holding the file. On: a marker per event, exits as the shim's rules say; after `rm`, none. Still off: no launcher, a symlink or directory at the path, a 25 h mtime |
| the doctor's warning | present with the file, absent without; SessionStart's `systemMessage` likewise |
| state across versions | a test feeds old-format and unknown-key state to every reader |
| mixed versions | a test runs the new plugin with the previous tree's launcher, and the reverse |
| the mod | `session.test.ts` proves the mod calls under its root; `claude plugin test plugin` green |
| the floor | `make test` reports both suites' counts; `make check` within its wall |
| `make install` on the moved tree | under a temp HOME, in a test, gives a launcher that runs `--version` at alpha.38, since this Mac's sessions depend on it until sc3 |
| validate | `claude plugin validate plugin` reads as before; quote `hooks.json`'s root per design/04 §7 item 1 |
| latency | the bare test's median and p95, 3.9 against 3.12: under 1.25 times and 2.5 s |

## 4. Findings that name this row: the stop (design/04 §8)

Stop and report, committing what is there, on: the package not surviving (`lib/`, exec bits, the runner lost in `git archive`); the latency bar missed; a state break an additive rule cannot cover. A stop is a result.

## 5. Forbidden reads

Transcripts' contents; the live state folder, every part, including a gate job's folder (wrap a job as `/bin/sh -c "make X > <scratch log>"` and read that); relay ledgers; the review whole.

## 6. Report (at most fifteen lines)

The branch and sha; each gate's id and its code as the line reads; each row of §3 with its figure; the check's seconds; the go or the stop against §8; anything decided or left over.
