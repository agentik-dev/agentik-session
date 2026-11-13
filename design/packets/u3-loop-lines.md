# Packet u3: the loop judges a row at the sha that lands, and refuses a line that runs make

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-12, brief u3 (hq `history/sessions/BRIEF-2026-11-12-session-u3-loop-lines.md`); hq design/07 §2 items 2 and 4; NICE n89, n90, both reproduced at the pin |
| pin | `8153e52` on main (h3 merged, 2.0.0-alpha.91). Version 2.0.0-alpha.92. Worktree `.claude/worktrees/u3-loop-lines`, branch `u3-loop-lines`; `.venv`, `.venv-floor` linked from the main checkout |
| wall | this worktree; no push, `--amend`, rebase, merge or install; no bare `make` (the gate queue only); no `claude`; no test reads live state (temp folders only); no relay verb; no loop run against live state |
| may touch | `plugin/lib/claude_session/unattended.py`; `tests/test_u3.py` (new), `tests/test_u2.py`, `tests/test_unattended.py`; `NICE_TO_HAVE.md` (n89, n90 leave); `plugin/.claude-plugin/plugin.json`, `README.md`, `design/readme/{source.md,rendered.sha256}` (the version's own commit, the status line only); this packet and the sitting's record |
| verify | the gate queue's `make check`, once, last; while building, pytest under `.venv` and `.venv-floor` |
| acceptance | §3; `tests/test_u3.py` red at the pin, green now, under both venvs |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the failing tests, then the change |

## 1. What the source says: the code at the pin

- `_Run.accept` (unattended.py:1295) runs every line in the row's own tree: an ignored or uncommitted file the child left there makes a line hold that fails at the sha that lands (n89).
- `stage` (:476) and `pin_baseline` (:772) each link only `<repo>/.venv`; a line on `./.venv-floor/bin/python` cannot run (127).
- `pin_baseline` (:754) makes and removes a detached tree at main's sha, never a prune (`_drop_records`, second review N1).
- No line is read before it runs: a line that runs `make` runs in the row's tree, outside the gate queue (n90). `instructionguard._commands` (:452) is the hook's reader of a shell line.

## 2. Rulings (brief u3)

- The owner's words: none new; hq entry 14 stands; packet u2 holds the owner's yes to the loop running the lines before it lands a row.
- R1: `accept` runs the lines in a temporary detached tree at the row's head sha, made and removed as the pin tree is (one function, `sha_lines`); the `accept` line gains `sha`.
- R2: `link_venvs` links each directory at the main checkout's top named `.venv*`, absolute, when the tree has nothing by that name; `.venv` always, another only when `git check-ignore -q` says the tree ignores it, else one log line. `stage`, the pin tree and R1's tree use it. No config key.
- R3: a tree that cannot be made: red `stage`, git's last line in the log, no continuation.
- R4: `continuation` names the fresh tree at `<sha>` and says an ignored or uncommitted file is not there.
- R5: `unbounded(shell)`: "" or why. `_commands` reads it (imported, never copied); refused: a line it cannot split, a word whose basename is `make` or `gmake`, the same inside a shell's `-c` text, to depth 3.
- R6: `do_row` refuses such a row `unbounded` right after `acceptance`, before its stage; a log line with the item, the line cut at 80, the reason. The run goes on.
- R7: `run`, after `plan`, says one line for each unparked row whose cell cannot be read or holds an unbounded line. No ledger line.
- Decided for the builder: the relay's allowlist, the 900 s limit, the scratch home, the group kill, the land script, the queue schema and the README's loop section are not touched; the version the next alpha after main's, in its own commit.

## 3. Interfaces: the acceptance table (brief u3), with the pin's results

1. A tracked `tool.sh` runs an ignored `./build/helper.sh` the child's tree holds. Pin: `green`, row `built`, 1 spawn. Now: `unrun` (127), the continuation names the sha's tree, red `acceptance` after two.
2. `pwd`: Pin: its last line is the row's tree. Now: outside it; `accept` holds the row's sha; the temp tree and its record gone.
3. A sha git cannot check out. Pin: `built` (no tree made). Now: red `stage`, one spawn, no `continue` line.
4. `.venv`, `.venv-floor` (ignored), `.venv-old` (not ignored) in the main checkout. Pin: `./.venv-floor/bin/python -c pass` 127, `unrun`, red. Now: the three trees link the first two, absolute; `.venv-old` one log line; not dirty; `built`.
5. `unbounded`: Pin: no such name (AttributeError). Now: the brief's nine lines refused, its three passed.
6. Two rows, the first `make check; echo $?` reads 0, a stub `make` on PATH. Pin: the stub runs, the line `green`, the row `built`. Now: `refused` `unbounded`, no tree, branch, spawn or stub run; R7's line said before the first spawn; the second row runs.
7. `tests/test_u2.py`, `tests/test_unattended.py` green under both venvs.
8. No test runs a real `make`, reads live state or leaves a worktree record.
9. `make check` green through the queue, once, last.

## 4. Findings that name this row

- NICE n89 and n90 close with this packet and leave `NICE_TO_HAVE.md`.

## 5. Forbidden reads

No transcript, no live state root, no file under `~/.claude`, no hq checkout but the two briefs.

## 6. Report

The hand-back to the hq coordinator: the branch tip, the acceptance table at the pin and now, the gate job and its exit, the choices made, what was not done.
