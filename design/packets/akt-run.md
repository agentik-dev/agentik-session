# Packet akt-run: `akt` starts a repo's sitting chain with the default prompt

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-14, brief akt-run (S3), with its rulings R2a and R4a |
| pin | `f302327` on main (2.0.0-alpha.124, su4-session-reads' merge). Worktree `.claude/worktrees/akt-run`, branch `akt-run`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make`; no `claude`; no test starts a chain or reads the live state or home; no relay verb; no `make stamp` (the landing's) |
| may touch | `plugin/lib/claude_session/cli.py` (`cmd_run`, the `run` parser), `chain.py` (`refusal`), `install.py` (the launcher text, `_locked_install`, `cmd_install_cli`'s line), `resolver.py` (`SESSION_KEYS`, the `run` check), `profiles.yaml` (`run`'s defaults), `plug.py` (`SUMMARIES`), `plugin/skills/session/SKILL.md`, `README.md` (its list of commands), `tests/test_akt_run.py` (new), any test that pins `SESSION_KEYS`, the settings list or the shipped session block, this packet, `history/sittings/2026-11-14-8-akt-run.md` |
| verify | `make check` by the gate queue, once, last |
| acceptance | §3's table; `.venv/bin/python -m pytest -q tests/test_akt_run.py`, and under `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says (baseline at `f302327`)

The owner, 2026-11-14: "Can you build an agentik session run command that, when run from inside a repo, it does the full line with the default prompt we've been using? Ideally the command is short and memorable so I can type it almost as easily as \"claude\"." The name: "how about akt". Later the same day: "outside a repo or one that hasn't been setup with agentik, give a line saying you couldn't find an agentik setup and the command to run if I want one", and "Respeak the human facing output from akt to be concise and informative."

The line it replaces: `agentik session run -- --model claude-fable-5-2 "Read the newest charter under history/sittings and act from its Next act."`

Measured at the pin under a temp home and state root: `run --dry-run` is argparse's `unrecognized arguments: --dry-run`, exit 2; `run` off a TTY refuses first (`stdin and stdout must be a TTY`); on a TTY, claude arguments with no positional prompt are refused (`chain.prompt_gap`, "carry no first prompt"). `run_args(cwd, env, ["do X"])` gives `--model opus --effort high do X` (the default profile's model and effort, mt1 R7). `install-cli` writes `bin/agentik-session`, the old-name link `claude-session` (always) and the `agentik` door; `akt` is written nowhere. `describe config --json` lists `respawn.cap`, `.floor`, `.settle` from the shipped `session.respawn` block.

## 2. Rulings

- R1, the defaults. `run` with no claude arguments runs as if given `-- --model <run.model> <run.prompt>`. `run.prompt` defaults to `Read the newest charter under history/sittings and act from its Next act.`, `run.model` to `claude-fable-5-2`. With claude arguments, those go as given; where they carry no first prompt `run.prompt` is appended last; where they carry no `--model`, `run.model` is added. A prompt or a model the person gives always wins.
- R2, R2a, the repo. With R1's default prompt in play, `run` exits 2 before anything starts, outside a git repo or where the git top has no `history/sittings/`: one line, no agentik setup found here, the command that makes one (`agentik session charter open "<goal>"`, in the repo), and `run.prompt` as the way to another prompt. A prompt the person gives is not checked.
- R3, `akt`. `akt [ARGS...]` is `agentik session run -- ARGS...`; a first word `--dry-run` is the one exception, `run --dry-run`, which prints the first start's env and argv as `start -n` does and starts nothing. `install-cli` writes `<prefix>/bin/akt`, a link whose text is `agentik-session`, by a temp link and a rename, where `akt` is absent or already such a link; anything else there is kept, with one line. The launcher run as `akt` runs `run`. The SessionStart refresh keeps a standing link and writes none where it was removed.
- R4, R4a, the words. `run`'s help, the session skill's page and the README's list of commands say what `akt` does, one line each. Every line `akt` prints to a person is listed whole in the builder's record for a respeak pass.
- Review 1's ruling (the coordinator, 2026-11-14): that pass's lines, as the tests in `tests/test_akt_run.py` pin them. One prefix, `akt:`, whether `akt` or `run` was typed; the no-setup line no longer names `run.prompt` (it amends R2); the swallowed prompt's line names `akt "<first prompt>"`; the dry run's command line is unchanged. The packet's sibling-group lines get an allow row; R4's README line is rendered by `make readme`.

## 3. Interfaces, choices and acceptance

- `session.run: {prompt, model}` beside `respawn` in `profiles.yaml`; `resolver` checks `run` is a mapping of those two keys, `prompt` a non-empty string, `model` a non-empty string or null. `cli.run_defaults(cwd, env, claude_args) -> (args, defaulted)`.
- `chain.refusal(args, env, where=True)`: `where=False` (the dry run) skips the checks of where it runs (the chain, Claude Code, the depth, `claude` on PATH); the argument checks stand.
- `install.AKT = "akt"`; `_locked_install(..., akt="write"|"keep")`: install-cli writes, the refresh keeps.

Choices inside the rulings:
- R1: `run.model` is added as the person's own `--model`, so mt1 R7's rule then passes no profile model or effort, as the owner's typed line did; `run.model: null` adds none and the profile's model applies, as at the pin.
- R1: where a valued or list option would read the appended prompt as its value (`prompt_gap` of the arguments plus one word is not None), the pin's refusal stands.
- R2: the folder is the literal `history/sittings/`, as ruled, not `charter.dir`.
- R3: the dry run skips the TTY and where-it-runs checks so it reads inside a sitting; the session id it prints is a fresh one, so the line runs as printed.
- R3: a second `install-cli` leaves a standing `akt` link untouched (no rename), so it changes nothing.

Acceptance: all in `tests/test_akt_run.py`, under a per-test temp home, state root and repo (made-up repo `crate`).

| # | line | at `f302327` |
|---|---|---|
| 1 | a repo with `history/sittings/`: `run --dry-run`, no arguments: the argv ends `--model claude-fable-5-2` and the default prompt | red: `--dry-run` unrecognized (on a TTY: no first prompt) |
| 2 | `run --dry-run -- --model opus`: the default prompt last, the model opus; `-- "do X"`: prompt `do X`, `--model claude-fable-5-2` added | red |
| 3 | outside a git repo and in one with no `history/sittings/`: bare `run` exits 2 with the no-setup line; `run --dry-run -- "do X"` there is not refused by R2 | red |
| 4 | `run.prompt` and `run.model` set at the repo layer change the defaults; `describe config --json` lists both | red |
| 5 | `install-cli` into a temp prefix: `akt` links to `agentik-session`; `akt --dry-run` prints R1's command; a hand's file at `akt` is kept, exit 0; a second `install-cli` changes nothing; a refresh writes none where it was removed | red: no `akt` |
| 6 | commons' `uninstall` rule takes the `akt` link back: its text is the tool's name | red: no link |
| 7 | the suite under both venvs; `make check` once, last, by the gate queue (the README's count may red alone: the stamp's) | green at alpha.124 |

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

No transcript, live state root or gate result, file under `~/.claude` or relay ledger.

## 6. Report

The record the coordinator names.
