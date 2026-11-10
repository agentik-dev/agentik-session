# Packet fw4c: gate land, one landing as one gate job of the plugin

| item | value |
|---|---|
| from | agentik-hq design/08 §5 row 5 ("hq's `scripts/land` in the plugin as `gate land`") and "The four tool asks"; §6 item 7 (FW4, a packet each, S3); this hq's `scripts/land` at 9f394ce and its tests at 16906e0 |
| pin | agentik-session main **after n33, R2 and R3 land**; cut on 36c84ea, so lines are cited by quoted words. Version: the next free alpha, read up by one for each bump landed before it. Worktree `.claude/worktrees/fw4c-gate-land`, branch `fw4c-gate-land`, the venvs linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test reads the live state or writes under the live home; no relay verb |
| may touch | `plugin/lib/claude_session/{gate,cli,land}.py` (land new); `tests/{test_fw4c,test_land,test_land_range}.py` (new); `tests/{conftest,test_gate}.py` (a line each); `plugin/skills/session/SKILL.md`, `RUNBOOK.md`, `NICE_TO_HAVE.md`, `plugin/.claude-plugin/plugin.json`; `README.md`, `design/readme/*`; `design/packets/fw4c-gate-land.md`; `history/sittings/*.md`, `history/sessions/NEXT` |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash; its exit is the job's |
| acceptance | `./.venv/bin/python -m pytest -q tests/test_fw4c.py`: 15 green (pin: `15 failed`), and under `.venv-floor`; `tests/test_land.py tests/test_land_range.py`: 115 green under both; `test_gate.py` green with its one assertion amended; `test_cli.py`, `test_fw2.py`, `test_unattended.py`, `test_argv_forms.py` unedited and green; verify green |
| budget | a commit per group by explicit path, the packet and the charter's doclint rows first; stop at 60 tool calls or 120k context, with a resume line. `claude-opus-5-5` |

## 1. What the source says

- The gate runs a job's argv in its repo with the env `run` saw: `p = fx.popen(e["command"], cwd=e["repo"], env=e.get("env") or {},` (gate.py:680); nothing marks the child as a gate job.
- The log's last line is the gate's own, `gate {e['id']}: exit {rc} in ...` (gate.py:698, `_close`), so a job's verdict is the line before it; the unattended loop reads it so, `_last_nonempty` (unattended.py:687).
- `gate wait --strict` exits the job's code: `return gate.strict_code(result) if strict else 0` (cli.py:1166); `strict_code` (gate.py:840) maps a non-int to 1. `run --wait` returns `_gate_wait(root, e["id"], None, False)` (cli.py:1120), never strict.
- The runner's own argv is built inside `spawn_serve`: `runner = Path(__file__).resolve().parent.parent / "agentik-session"` (gate.py:496), with `-I` and the pycache prefix.
- The loop runs a land script inside `gate run --wait` (unattended.py:847), defaulting to `p = repo / "scripts" / "land"` (unattended.py:120).
- hq's script: one stdout line, `land <repo>: ok <sha>, main readied` or `red <step> exit <code>`, the suffixes `, range not scanned` and `, staged paths left on main`; usage 2, its refusals 1, a step's own code, the cut 124 (its docstring). It resolves the merge file against the job's cwd, the repo: `os.path.abspath(argv[3])` (scripts/land:496).
- Probe p1 (`p1_nested_wait.sh`): a gate job that queues and waits on its own repo never starts the inner job until the wall cuts the outer: `outer strict exit 124`, `inner ran: 1` (after the cut).

## 2. Rulings

- R1, the steps. `land.py` is hq's `scripts/land` at 9f394ce, shebang and `__main__` dropped, its docstring's head naming the two forms below; `main(argv)` and every step, line and exit unchanged; the standard library alone.
  hq's `tests/test_land.py` and `tests/test_land_range.py` at 16906e0 are ported. Only the call changes: `[sys.executable, <plugin/lib/agentik-session>, "gate", "land", "--in-job"]` with the mark in the env; the docstring is read from `land.py`; (d) runs the tree's own launcher; the shebang test becomes a standard-library one (115 stay 115).
- R2, the mark. `gate.JOB_MARK = "CLAUDE_SESSION_GATE_JOB"`; `_start` passes `{**env, JOB_MARK: gid}` to the child. `tests/conftest.py` adds it to `INHERITED`, since the suite itself runs inside a gate job. `test_gate.py`'s `test_serve_runs_fifo_and_writes_the_result_last` expects `{**ENV, gate.JOB_MARK: a["id"]}`.
- R3, the verb. `gate land <repo> <branch> <sha> <merge-file> [--session SID] [--wall S]` resolves the repo as R1 does (a bare name under `~/code`, the cwd never) and the merge file against the caller's cwd. It queues one entry, label `land <branch>`, command `[*gate.self_argv(), "gate", "land", "--in-job", <repo>, <branch>, <sha>, <abs merge-file>]`, and waits with no timeout.
  Stdout is one line, last: the job's last line (`gate.last_line`: the log's last non-empty line not the gate's own) when it reads `land <name>: ok ` with exit 0, or `land <name>: red `; else `land <name>: red gate exit <code>`, the job's code or 1, never ok. The queued and wait lines go to stderr. The exit is `strict_code(result)`.
  Before queueing: not four arguments, `land ?: red usage exit 2`, exit 2; no such directory, `land <name>: red repo exit 1`, exit 1.
- R4, the doors. With the mark set, the queue form refuses, exit 2, naming the job and `--in-job` (p1). `--in-job` (help suppressed) runs `land.main` in this process, and without the mark refuses, exit 2, naming it: the gate holds every `make` on the Mac.
- R5. `gate.self_argv()` is the head `spawn_serve` builds today, and `spawn_serve` uses it. The parser's metavar reads `run|wait|status|land`.
- R6, docs. SKILL.md, one line under `gate wait <id> --strict`; RUNBOOK §5, one bullet (the steps, the one line, `red gate`, the two doors). README: the status line only (`source.md` is 16,381 of 16,384 bytes). Last: the version, the status line, the sidecar.

Choices logged (reversible): `red gate` for a log with no land line; a bare name stays under `~/code`.

Tests, `tests/test_fw4c.py` (probes):

Red at 36c84ea and green on `prototype.patch`, under 3.12.7 and 3.9.6.

| T | the test shows | item | red at the pin |
|---|---|---|---|
| 1 | green through the verb: one stdout line, exit 0, merge `--no-ff`, worktree and branch gone, merge file relative to the caller | R3 | invalid choice `land` |
| 2 | a red check: `red check exit 2`, main kept | R3 | as T1 |
| 3 | `--wall 2`: `red cut exit 124` | R3 | as T1 |
| 4 | `, range not scanned` passes through | R3 | as T1 |
| 5 | three jobs with no land line of this repo: `red gate exit 1`, `7`, `1` | R3 | no `self_argv` |
| 6 | usage and a missing repo: their lines, nothing queued | R3 | as T1 |
| 7 | the entry's command and label | R3, R5 | as T1 |
| 8 | `spawn_serve`'s argv starts with `self_argv()` | R5 | no `self_argv` |
| 9 | a `gate run` job sees its own id as the mark | R2 | `mark=` empty |
| 10 | the queue form inside a job: exit 2, nothing queued | R4 | argparse's line |
| 11 | `--in-job` outside a job: exit 2, main kept | R4 | argparse's line |
| 12 | `--in-job` through the launcher is the steps | R1 | argparse's line |
| 13 | `INHERITED` holds the mark; SKILL.md and RUNBOOK name the verb | R2, R6 | no name |

## 3. Interfaces

New: the verb `gate land` (R3, R4), module `land` (R1), `gate.JOB_MARK`, `gate.self_argv`, `gate.last_line` (R2, R3, R5). Unchanged: every other verb, every config key.

What becomes of hq's script:

It stays until the verb is installed. Then hq's flow step 7 calls `agentik session gate land <repo> <branch> <sha> <merge-file>` in one background Bash, its exit the verdict.
And `scripts/land` becomes a thin `exec agentik session gate land --in-job "$@"`, which keeps the loop's default (unattended.py:120) working inside its `gate run --wait`; never a call of the queue form, which waits on its own key (p1). hq's two land test files retire with it. That edit is hq's, outside this packet.

## 4. Findings that name this row

agentik-session keeps no ledger of its own: no entry to carry. Bearing, uncrossed: agentik-hq 6, "at a runtime floor of Python 3.9 on the standard library alone"; agentik-hq 5, "helpers never push" (the verb pushes nothing; R1's no-push test stays); agentik-hq 17, a verb takes a packet.
NICE, new:
- S4, `unattended.py`: the loop's land step could call `gate land` itself, and `_last_nonempty` fold into `gate.last_line`.
- S4, `land.py`: the `~/code` root of a bare name is one owner's layout; a key would serve others.
- S3 lead, `cli.py`: `gate run --wait` of its own key inside a job waits to the wall, as p1 shows; with the mark it could refuse.

Fork Q1, marked: R2 and R4 (the mark and the two doors) go past a straight move. Recommended: keep them; without the mark, hq's thin script or a helper calling the queue form inside a job hangs to the wall.
Ruled by the coordinator: kept; the gate marks every job, `gate land` refuses to queue inside one, `--in-job` is the script's call; the cutter's refusals stand.

## 5. Forbidden reads

Live transcripts; the live state root; relay ledgers.

## 6. Report

Six lines at most: head sha; gate id and code; T1 to T13 and the ported 115 under both pythons; choices in a ruling; leftovers.
