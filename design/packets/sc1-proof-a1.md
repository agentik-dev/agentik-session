# Packet sc1, Amendment 1: the refuter's round 1 on 8b7297d

| item | value |
|---|---|
| from | the refuter's round 1, FAIL; the coordinator's rulings below. Parent `design/packets/sc1-proof.md`, whose rulings stand except where this moves them |
| pin | 8b7297d (branch `sc1-proof`); worktree `.claude/worktrees/sc1-proof` |
| wall | as the parent's, and `claude plugin test plugin` is allowed: it uses no model |
| may touch | `scripts/bare-proof`, `claude_session/cli.py` (`_Parser` only), `tests/` (the parser's table, and any test of the proof), `NICE_TO_HAVE.md`, the parent packet (this amendment as its last section, or `design/packets/sc1-proof-a1.md` if doclint's ceiling needs it), the charter |
| acceptance | §2's mutants each make `scripts/bare-proof` exit nonzero, each quoted by its failing row; the unmutated proof exits 0 with its last line `bare-proof: go`; §3's forms pinned by a test green under `make test-floor` and under `.venv`; `make hygiene` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- make test-floor`, then the same with `make check`; each `agentik session gate wait <id>`. **`gate wait` exits 0 whatever the job's code: read the code from its line** |
| budget | acts: 0 this amendment; 1 the parser, §3; 2 the proof's reach, §2; 3 the NICE lines, §4; 4 the rerun and the charter. 70 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act |

Mutants run only in a scratch copy, never the worktree; a synthetic transcript will do for them. Keep load below 20: this Mac is shared.

## 1. Why this blocks

The slice proves or kills design/04. The builder's go stands in substance, by the refuter's own diff of 13 hook calls under 3.9 and 3.12, but the proof could not have shown it: `hooks.py:764-767` turns any handler exception into `{}`, exit 0, so the ten-events row passes on a dead handler. sc2 moves this test into the suite, so it must see what it claims.

## 2. The proof's reach (`scripts/bare-proof`)

| finding | ruling | the mutant that must go red |
|---|---|---|
| F1 S2, `events` :233-244, reads only exits and JSON | Assert each event's effect (resolved.json, meter.json, a hooks.jsonl row, whichever that event writes) and diff exits, stdout, stderr, the state files' names and the JSON shapes against 3.12 on one input. Ignore only what legitimately varies (times, ids), and name each ignored field in a comment | `import tomllib` inside `post_tool_use`; `import yaml` inside `session_start`; a `match` statement in a module `session_start` imports late; `dispatch` printing `{}` and returning |
| F2 S2, :53-58, :194-198, the decoy cannot fire | Run `-c 'import claude_session'` from the decoy's cwd under the launcher's exact flags and assert the decoy loses | `-I` swapped for `-u` in the launcher; `-I` dropped, red in this row and not by accident in live state |
| F5 S3, :66-103, a child's write goes unseen | **Narrow the row's text**, do not widen the detector: it says what it sees (in-process writes by the audit hook, `HOME` reaching each child, the sentinel) and names a child process's write as unseen. Sandboxing is macOS-only and sc2's test joins the suite. Amend the parent's §3 live-state row to match | none |
| F6 S3, :360, validate passes when both runs fail alike | Require exit 0 on both and the mock's warning count equal to the live plugin's | a stub `claude` exiting 1 |
| F7 S3, :275-279, the two-forms row never reads the job's result | Assert result.json's `exit` is 0 | the job `true` changed to `false` |
| F8 S4, :301, the clone scan skips symlinks and file names | On the path, so fixed | a hook writing a symlink to the clone |
| F9 S4, :446, a dead tool gives a traceback | On the path, so fixed: a `stop:` line, and the later rows still print | a module-level `import yaml` |

`spawn_serve` (`gate.py:478`) drops `-I` and the prefix, leaving .pyc files under `$T/Library/Caches/com.apple.python`, unseen by the bytecode row. sc1 moves no code: **the row counts .pyc anywhere under `$T` outside the prefix and prints that figure, naming `spawn_serve` as sc2's, without failing on it.** sc2 fixes it and makes the row strict.

## 3. The parser (`claude_session/cli.py`)

- **F3 S3, :981:** under 3.9 and 3.10, `--opt=--` reads as `[]`: `charter close --exit=-- F` writes `exit taken: goal met` against base 3.12's `exit taken: --`. Hold `--` in a `_get_values` override.
- **F4 S3, :1000:** the mark reaches an error message: `config -- -x` prints `invalid choice: '\x00-x'`, where base printed `'-x'`. Strip it in a `_get_value` override. The post-parse loop goes if the two overrides replace it; the refuter's scratch form did so on 3.9.6 alone, so try it on the rest.
- **Pin both** in a test, with parent ruling 1's forms, and assert no value or message holds a NUL. Run the table on each interpreter this Mac has that the refuter named (3.9.6, 3.9.20, 3.10.15, 3.12.7, 3.14.7) and quote the counts; the suite's test need only run under its own interpreter. A form 3.12 accepted at 8ed5667 keeps its meaning.

## 4. The NICE lines, S4, in `NICE_TO_HAVE.md`

- Correct the `-- -- budget` line: base 3.12.7 refuses it; head accepts on 3.12 and refuses on 3.9.
- `mod -- -h` now prints help, exit 0, where base refused: newly accepted, as are the charter's two forms.
- `gate.py:640`: a non-UTF-8 gate command crashes the runner with UnicodeEncodeError, at base too.
- `gate wait` exits 0 whatever the job's code, as the README states, so a background Bash's exit reads green on a red job. Lead: a `--code` flag that exits the job's code.

## 5. Forbidden reads

As the parent's: transcripts' contents; `~/.local/state`, every part, including a gate job's folder (log to a scratchpad and read that); relay ledgers.

## 6. Report (at most twelve lines)

The head sha; each gate's id and its code as the line reads; the mutants, red or not, each by row; the interpreters' counts for §3; the rerun's latency figures and its last line; whether §8's go still stands; anything left over.
