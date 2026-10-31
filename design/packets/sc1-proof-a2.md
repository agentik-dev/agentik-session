# Packet sc1, Amendment 2: the refuter's round 2 on 62a57d8

| item | value |
|---|---|
| from | the refuter's round 2, the last (macbase entry 20: no third round): F1 and F4 of round 1 not closed; the coordinator's rulings below. Parents `design/packets/sc1-proof.md` and `design/packets/sc1-proof-a1.md`, whose rulings stand except where this moves them |
| pin | 62a57d8 (branch `sc1-proof`); worktree `.claude/worktrees/sc1-proof` |
| wall | as the parents'; `claude` only as `claude plugin validate` and `claude plugin test plugin`; the proof and mutants only from a scratch clone or the worktree as it ships; never a gate verb by hand under a temp HOME, never a typed `kill` |
| may touch | `scripts/bare-proof`, `claude_session/cli.py` (`_Parser` only), `tests/` (the parser's table, and any test of the proof), `README.md`, `design/readme/source.md` and the sidecar if the suite's count moves them, `NICE_TO_HAVE.md`, `design/packets/sc1-proof-a2.md` (new), the charter |
| acceptance | §2's mutants each make the proof exit nonzero, each quoted by its failing row; the unmutated proof exits 0 with its last line the go; §3's forms pinned by a test green under the floor and under `.venv`, by the verify row's gates; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make test-floor`, then the same with `make check`; each `agentik session gate wait <id>`. `gate wait` exits 0 whatever the job's code: read the code from its line |
| budget | acts: 0 this amendment; 1 the parser, §3; 2 the proof, §2; 3 the S4s, §4; 4 the rerun and the charter. 60 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act |

Keep load below 20: this Mac is shared.

## 1. What the source says: the refuter's harness, a lead to use

`SP=/private/tmp/claude-501/-Users-kevinteg-code-agentik-hq/6f4a5995-fbe9-456e-a9d2-a02b6a060274/scratchpad`. `/usr/bin/python3 -I -B $SP/mut.py $SP <name>...` applies each named mutant to a scratch clone at `$SP/w/c` on branch `sc1-proof` and runs the proof at `--runs 3`. `$SP/one.py` runs one argv against a tree. Fetch your head into that clone first. It patches by exact strings, so a mutant may need its string updated; a mutant's body does not change. Latency alone going red at 3 runs does not count as caught: read the other rows.

## 2. Rulings: the proof (`scripts/bare-proof`)

**F12 S2, blocks, round-1 F1 not closed, :285-311.** Each effect reads the handler's first write, so an exception after it is still swallowed, in both interpreters at once too. **Ruling:** the mock's runner, the four-line `plugin/lib/agentik-session`, records any exception `hooks.dispatch` swallows into a file under `$T`, and the ten-events row fails if that file exists. This reaches the swallow, so it holds whichever line raises; the effect rows stay beside it. Find the least intrusive seam: a wrapper or a patch applied by the mock's runner only, since sc1 moves no code and the repo's `hooks.py` does not change. The mock stops being quite what sc2 ships in that one way, so say so in a comment. Mutants: `ups_raise_after_stamp` (both interpreters dead), `ptu_tomllib_after_meter`, `gate_lines_tomllib`, `pretool_raise_after_stamp`.

**F13 S3, blocks, round-1 F1's "ignore only what legitimately varies", :497-503, :752-758.** Every state value, all non-JSON content and list lengths are ignored. **Ruling:** diff values, with only named times, ids and the run's own paths masked, each named in a comment; non-JSON state files compare by content under the same masks; list lengths compare. If a value differs legitimately between interpreters, name it in the mask with why. Mutants: `meter_value_39`, `yaml_garbage_39`, `ledger_same_shape_row_39`.

Round 1's and 2's reds stay red: run `launcher_E_s`, `request_gone_312`, `result_absent`, `relative_link`, `stub_claude_exit0_silent`, `module_dead`, `launcher_I_prefix_cwd`, and `baseline` as the control reading `go`.

## 3. Interfaces: the parser (`claude_session/cli.py`)

- **F10 S3, blocks, round-1 F4 not closed, :1013:** under 3.12.7, `gate run R --wa -- -x` prints `ambiguous option: \x00-x could match --wall, --wait`, where base prints `-x`. **Ruling:** strip the mark in an `error()` override, so it holds for any message.
- **F11 S4 by use, blocks under parent ruling 1, :998:** `_get_values` holds `--` only for options, so `set K -- --` reads `value: []` on 3.9.6, 3.9.20 and 3.10.15, where base 3.12.7 reads `'--'`; `set checkpoint -- --` ends in `AttributeError` on 3.9.6. **Ruling:** drop the `option_strings` test. Keep F3's `charter close --exit=-- F` reading `exit taken: --`.
- Pin both in the test, and rerun the table on 3.9.6, 3.9.20, 3.10.15, 3.12.7, 3.14.7, quoting the counts.

## 4. Findings that name this row: the S4s, on this path, so fixed if each stays under five lines, else one NICE line

- F14, :519-547: the decoy row reads only the launcher's flags, so `cd "$HOME"` before the exec goes unseen. Assert the charter lands in the temp repo. Mutant: `launcher_I_cd_home`.
- F15, :147: `Proof.__init__`'s git call is unguarded: outside a git tree, a traceback and exit 1 where the usage says 2. Move it under the setup guard.
- F16, :148-149: in a plain clone the relative `--git-common-dir` makes the clone's parent a "clone". Resolve it against the cwd git ran in.
- `sentinel`'s docstring still says "nothing wrote outside $T", wider than its row: narrow it. `stop_serve` in `main`'s `finally` is unguarded: guard it.
- One NICE line: `_get_values` holds only `nargs=None`, so a synthetic `--o=--` with `?`, `*`, `+` or `1` differs on 3.9; no CLI option has those nargs.

## 5. Forbidden reads

As the parents': transcripts' contents; `~/.local/state`, every part, including a gate job's folder; relay ledgers.

## 6. Report (at most ten lines)

The head sha; each gate's id and its code as the line reads; the mutants, red or not, each by row; the interpreters' counts; the rerun's latency figures and last line; whether §8's go still stands; anything left over.
