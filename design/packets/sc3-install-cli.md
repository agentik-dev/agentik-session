# Packet sc3: install-cli

| item | value |
|---|---|
| from | agentik-hq HANDOFF 17, build 2 of the Fable review; `agentik-hq design/04-self-contained-plugins.md` §7 item 3, §2, §3, §5 step 3, §6; hq entry 6 at a 3.9 floor; sc2's landing (`design/packets/sc2-move*.md`) |
| pin | main at the cut; worktree `.claude/worktrees/sc3-install-cli`, branch `sc3-install-cli`, its `.venv` and `.venv-floor` links in place |
| wall | this repo; no push, `--amend`, rebase, merge, device, real `make install`, `make readme`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test or proof never writes under the live `~/.local/state`, `~/.local/bin`, `~/.local/share`, the real `~/.claude` or the real `~/.config/agentik`; **no test or probe touches the real `~/.config/agentik/hooks-follow-launcher`**; no relay verb, no relay binary built or run; no `pkill` by name or pattern; never a gate verb by hand under a temp HOME, never a typed `kill`; a Python probe needs PYTHONPATH=<worktree>/plugin/lib |
| may touch | `plugin/lib/claude_session/` (a new `install` module, `cli.py`, `hooks.py`, `doctor.py`, `gate.py`, `chain.py` as named below), `plugin/commands/install-cli.md` (new), `scripts/prune-trees` and its new home, `install-wrapper.sh` (replaced), `Makefile`, `pyproject.toml`, `tests/`, `README.md`, `RUNBOOK.md`, `design/readme/*`, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`, this packet, the charter |
| acceptance | §3's table, each row's figure in the report; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last. `gate wait` exits 0 whatever the job's code: read the code from its line |
| budget | acts below, one commit each. **Stop at 140k context or 120 tool calls:** commit the act in flight, write the resume line in the charter, and report; a fresh builder takes the rest. sc2's builder passed its budget at 227k, so do not read more than the list below and never run the suite in the foreground with its output unbounded. `claude-opus-5-5` |

Read first, by sections, never whole (`/session:read`): design/04 §2, §3, §5, §6, §7 (first paragraph, the bare-machine test, item 3), §9; then `agentik-research research/synthesis/tools-session.md` by its session-install sections. Code: `Makefile:install`, `install-wrapper.sh`, `scripts/prune-trees`, `tests/test_install.py`, `plugin/bin/agentik-session`, `plugin/lib/agentik-session`, `gate.spawn_serve`. agentik-observer's `sources.py:_launcher` is read-only: never write there.

## 1. What this is, and what it is not

The launcher on PATH stops depending on a checkout or venv: `agentik-session install-cli` freezes the plugin's own `plugin/lib` and writes the launcher, on Apple's Python. **Not here:** commons' copy (c1), the next two tools (d25, a-s18), the `suite` plugin (c2), removing `.venv` from the repo's development.

## 2. Acts and rulings

0. This packet as `design/packets/sc3-install-cli.md`, committed first.
1. **The verb.** A stdlib `install` module and `agentik-session install-cli`, with `/session:install-cli`. It freezes the plugin's `lib/` and `plugin.json` to `$HOME/.local/share/agentik-session/<content hash>/`, the name a hash of their contents since no git is at hand; writes `~/.local/bin/agentik-session` with a `VERSION=` line, the link `claude-session`, the door `agentik`, each by a temp file and a rename; then prunes. The verb reads its tree from its own runner's path, whichever plugin or frozen tree it runs from. `prune-trees` moves into the package, or is run from it, so the verb needs no checkout (NICE:363's hash note closes here).
2. **The launcher's form.** Design/04 §2's: `py=${AGENTIK_PYTHON:-/usr/bin/python3}`, fallback `command -v python3`, then `exec "$py" -I -X pycache_prefix=... "<tree>/agentik-session" "$@"`. Keep the old wrapper's behaviours: the `claude-session` terminal note; a gone tree or interpreter on `hook` exits 0, `SessionStart` says so as a `systemMessage`, other events once by the marker; other verbs now **exit 3** (design/04 §2). Its text says to run `install-cli` where it said `make install`. `ps` must read `Python -I …/agentik-session run --chain x`: check against the observer's `_launcher` and `prune-trees`, report what you read.
3. **F8 under the new form.** The prune keeps a tree whose path is on a live process's command line, under `/usr/bin/python3`, and the old `PYTHONPATH` form too, since old launchers run for a day or more. On doubt it keeps all. It never removes the tree it just wrote.
4. **`make install` through the verb.** It keeps its "dirty: commit first" guard, then runs `plugin/bin/agentik-session install-cli` with `HOME`/`PREFIX` honoured so a test can aim it at a temp home. The 3.11 search goes (NICE:354 closes here).
5. **The forward refresh.** On `hook SessionStart` only: if `~/.local/bin/agentik-session` exists, read its `VERSION=`; if this plugin's version is strictly newer by the package's own ordering of `2.0.0-alpha.N`, run the install. Never creates a launcher that does not exist. Refuses backward and equal. No version line, or an unparsable one: left alone, one doctor line. A failure of any kind never fails the hook, costs at most one `systemMessage`, and is atomic, so two sessions starting together leave a whole launcher and a whole tree. It adds no fork and no write on the common path beyond reading that file; report SessionStart's added milliseconds on the no-op and on a real refresh. Under the switch (`hooks-follow-launcher` on) a hook runs the launcher itself: the refresh then does nothing.
6. **Apple's variables.** `/usr/bin/python3` adds `SDKROOT`, `CPATH`, `LIBRARY_PATH`, `MANPATH`, `LC_CTYPE=C.UTF-8` where unset (design/04 §3, `env -i /usr/bin/python3 -I -c "import os;print(dict(os.environ))"`). A launcher's `claude` and a gate job must not see one the parent did not have: the launcher's shell can record what was set before the exec, for the chain and gate spawns to restore. A value the parent set stays. If you cannot, the charter says why, and that is a stop for hq. `gate.spawn_serve`'s `-I` form from sc2 stands.
7. **Doctor.** Names a launcher older than the plugin, a launcher with no `VERSION=`, and a launcher on a gone tree; its `python` row reads the launcher's interpreter. Warnings, not fails, except a gone tree.
8. **Docs and the version.** README, RUNBOOK (install is `install-cli`; the emergency's `make install` line stands or moves as acts 4 and 5 make true; the relay on a fresh Mac needs `install-cli` for its band, named and not changed, design/04 §9); `2.0.0-alpha.40`, one bump, last; the README count from the suite; the sidecar re-hashed by hand. The install is hq's.

## 3. Acceptance

| what | reads |
|---|---|
| bare machine | under the bare-machine env, `plugin/bin/agentik-session install-cli` writes launcher, link, door and tree; `$T/.local/bin/agentik-session --version` reads alpha.40 under `PATH=/usr/bin:/bin` with no clone or venv |
| F8 | a live process under `/usr/bin/python3` with an old tree's path on its command line keeps that tree through a prune; the same for the `PYTHONPATH` form; the oldest other tree goes; a `ps` that fails keeps all |
| T5's decoys | a decoy package in the cwd and a decoy on `PYTHONPATH` change nothing the launcher runs; design/04 §6's retargeted `tests/test_install.py` green |
| a gone interpreter | `AGENTIK_PYTHON` unusable and no `python3` on PATH: a verb exits 3, `hook` exits 0, `hook SessionStart` a valid JSON `systemMessage` |
| a gone tree | the same three reads |
| refresh forward | launcher at alpha.39 form, plugin at alpha.40: one SessionStart moves it; a second is a no-op; launcher and tree whole |
| refresh refuses | equal; newer launcher than plugin (byte-identical after); no launcher (none created); no `VERSION=` (left alone); a read-only bin (hook exits 0, one `systemMessage`) |
| refresh race | two processes at once under a temp HOME, twenty rounds: the launcher runs `--version` each time, no `.tmp` left |
| Apple's variables | `env -i HOME=$T PATH=/usr/bin:/bin` launcher to a stub `claude` under `run` and a gate job under a temp state root by the suite's own harness: none of the five, while a parent-set `MANPATH` survives. Never a gate verb by hand |
| the old launcher to the new tree | an old-plugin shim calling the new launcher, and the new plugin with the old launcher: exits as the shim's rules say (sc2's mixed test extended) |
| `run` | `agentik-session run` under a pty in the temp home reaches its first spawn of a fake `claude` at 3.9 |
| `make install` | under a temp HOME in a test gives the same tree as the verb |
| latency | the bare test's median and p95 of a hook through the new launcher, under 1.25 times build 4's and under 2.5 s |
| floor and wall | `make test` reports both suites' counts; `make check` within its 840 s wall, seconds reported |

## 4. The stop (design/04 §8)

Stop and report, committing what is there, on: a launcher that cannot reach its first spawn at 3.9; the latency bar missed; Apple's variables not stoppable; a prune that can take a live tree. A stop is a result.

## 5. Forbidden reads

Transcripts' contents; `~/.local/state`, every part, including a gate job's folder (wrap a job as `/bin/sh -c "make X > <scratch log>"` and read that); relay ledgers; the review whole.

## 6. Report (at most fifteen lines)

The branch and sha; each gate's id and its code as the line reads; each row of §3 with its figure; the check's seconds; the go or the stop against §8; anything decided or left over, and if you stopped at the budget, the exact resume line.
