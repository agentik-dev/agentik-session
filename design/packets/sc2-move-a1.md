# Packet sc2, Amendment 1: the refuter's round 1 on cba7d68

| item | value |
|---|---|
| from | the refuter's round 1, FAIL on F1; the coordinator's rulings below. Parent `design/packets/sc2-move.md`, whose rulings stand except where this moves them |
| pin | cba7d68 (branch `sc2-move`); worktree `.claude/worktrees/sc2-move` |
| wall | as the parent's |
| may touch | `plugin/bin/agentik-session`, `plugin/hooks/run`, `plugin/hooks/session.ts`, `plugin/hooks/session.test.ts`, `plugin/.claude-plugin/plugin.json`, `tests/test_bare_machine.py` and the switch's test file, `plugin/lib/claude_session/hooks.py` (the doctor's reading of the switch only, if §2 needs it), the version act's pins, `README.md`, `design/readme/*`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `design/packets/sc2-move-a1.md` (new), the charter |
| acceptance | §1's and §2's tests green, each red on cba7d68's code, each red quoted once; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make check`, then `agentik session gate wait <id>`, last. `gate wait` exits 0 whatever the job's code: read the code from its line |
| budget | acts: 0 this amendment; 1 F1; 2 the S4s on the path; 3 the NICE lines; 4 the version, last, one bump. 50 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act |

Keep load below 20: this Mac is shared. Probes for each finding are in the scratchpad's `sc2r/` folder (`p1.sh`, `p2.sh`, `p5.sh`, `mut.sh`), named in the wall's scratch path of your prompt; read them as leads.

## 1. What the source says: the blocker

**F1 S2, `plugin/bin/agentik-session:11`.** With the runner or all of `lib/` missing, Python's "can't open file" exits 2, and the shim passes that on where it should exit 0. Exit 2 from a PreToolUse hook is a block: a damaged plugin would deny every tool call in a session. `rm $T/p/lib/agentik-session; printf '{}' | env -i HOME=$T PATH=/usr/bin:/bin CLAUDE_PLUGIN_ROOT=$T/p $T/p/hooks/run PreToolUse` gave exit=2; SessionStart, UserPromptSubmit, PostToolUse and SessionEnd also 2. Base's launcher exits 0 when its tree is gone, and design/04 §8 names this loss while calling what landed "harmless".

**Ruling:** in the launcher, for a `hook` verb, a runner that is not a regular file exits 0, and SessionStart says so in a `systemMessage`, as with no Python. Any other verb exits 3 with a one-line reason. A test covers each of the ten events with the runner gone and with all of `lib/` gone, and a mutant dropping the check goes red.

## 2. Rulings: the S4s on this path, fixed

- **F2, `plugin/hooks/run:10`, `plugin/bin/agentik-session:6`:** `[ -x ]` accepts a directory, so a directory at the launcher path with the switch on exits 126, and `AGENTIK_PYTHON=/usr` also 126; `AGENTIK_PYTHON=/usr/bin/grep` gives 2. Test `-f` as well. A hook must never exit 2 for a bad interpreter: when the interpreter cannot start the runner, the hook verb exits 0. Name what that costs in a comment, if anything.
- **F3, `plugin/hooks/run:10`:** a future mtime never lapses: `touch -t 209901010000 "$F"`, then PreToolUse ran the decoy. Refuse a future mtime, in the shim and in the doctor, each by the cheapest form that forks nothing when the file is absent.
- **F5, `plugin/hooks/run:7-10`:** bare `find` comes from PATH, against design/04 §3's "no PATH entry". Use `/usr/bin/find`, a one-word change to the design's verbatim line, recorded in the amendment as such. `date`'s form stays as S49 has it unless it has the same hole, and if it does, do the same.
- **F6, `plugin/lib/agentik-session:4`, `tests/test_bare_machine.py:124`:** the shipped runner can lose every exit code unseen: with `main(); raise SystemExit(0)`, 525 tests passed. Assert a verb's non-zero exit through `plugin/bin/agentik-session`.
- **The mod's root:** the `$.plugin.rootz` mutant gives argv `undefined/bin/agentik-session`, a relative path that could run a file in the cwd if a real host lacked `root`. Guard it: with no absolute root the mod does not spawn, and says `no meter` as it does on a refusal. A test proves no process ran.
- **The switch's `-mmin` bound:** a `-mmin -1499` mutant survives, since only 25 h is pinned. Pin the bound with a file a few minutes past 24 h.

## 3. Interfaces: the version

Any change under `plugin/` after the alpha.38 commit is refused by `plugin-version-check`, so bump to **2.0.0-alpha.39** once, last; alpha.38 is skipped, never released. The README count from the suite, the sidecar re-hashed by hand.

## 4. Findings that name this row: the NICE lines, S4, in `NICE_TO_HAVE.md`

- F4, `hooks.py:372`: the doctor is not "as `find -mmin -1440`" on this Mac: at 1439 m and 1440 m `/usr/bin/find` matched while `follow_launcher_on` said False, so the hooks follow for up to 2 minutes with no warning.
- F7, `pyproject.toml:22`, `gate.py:475`: a built wheel has no `plugin.json` and no runner: `--version` prints `0.0.0-unknown` and `spawn_serve` returns True with no runner. No live path uses a wheel.
- `plugin/scripts/record` writes bytecode under `Library/Caches/com.apple.python`, and the floor suite wrote 75 files for a scratch tree into the real `~/Library/Caches/com.apple.python`.
- `floor: absent` lets a worktree with a dangling link land without the floor.
- A 200,000-`[` `plugin.json` raises RecursionError past "Never raises", so hooks exit 1.
- A `.claude-plugin/plugin.json` beside the frozen trees shadows a tree's own version.
- A cold check's margin to the 840 s wall was 1.76 times under concurrent load; the wall has not been tested at the check's hold-off of load 64.

## 5. Forbidden reads

As the parent's: transcripts' contents; `~/.local/state`, every part, including a gate job's folder; relay ledgers.

## 6. Report (at most ten lines)

The head sha; each gate's id and its code as the line reads; each test's quoted red; the version; the latency figures if the proof ran; anything left over.
