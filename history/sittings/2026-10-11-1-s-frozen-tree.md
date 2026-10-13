# Sitting 2026-10-11-1: claude-code-session, F8 (the frozen tree pruned under live launchers)

| item | value |
|---|---|
| goal | `make install` never deletes a tree a live process runs from (scripts/prune-trees, tested); the shipped profiles read once, at import; a missing shipped file raises a named error, never an empty layer. respawn-r1 §4's hold on a config error is unchanged (design) |
| budget | 70 tool calls, stop at 56; 180k context; one commit per act; never push, amend, rebase, a device, the network; no `make install`, no `make check`, no `claude-session run` or `checkpoint`, no `claude plugin`; never signal a process; the install dirs read only |
| pin | branch `s-frozen-tree` off main 4a2e376; s-stale-calls owns chain.py `_ready` and hooks.py (not touched here) |
| window | 200k (a builder on a 1M window keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 0: this charter
- [x] act 1: red tests (prune keeps a live tree; SHIPPED gone after import still resolves `orchestrator`; a missing shipped file names itself). Red on main 4a2e376: test_resolver `-k f8` 2 failed (`unknown profile 'orchestrator'; known: `, the F8 line); test_install + test_prune_trees 9 failed, 4 passed (the live tree pruned; the script absent)
- [x] act 2: scripts/prune-trees (keeps the new tree, every entry a live process names in `ps -axwwE` output, the newest three by mtime; a probe variable missing from ps's own line, a failed or absent ps: keeps all); the Makefile's install calls it in place of the rm loop (a failed prune keeps every tree); RUNBOOK §install says so. test_install + test_prune_trees: 13 passed
- [x] act 3: resolver: `_SHIPPED_AT_IMPORT` (the bytes of SHIPPED, read once at import); `_read_shipped` serves it (re-reads only when SHIPPED was repointed or had no snapshot) and a missing file raises `ShippedGone` (a ResolveError: the §4 hold unchanged) `the shipped profiles.yaml is gone: <path>; run make install`; user and repo layers unchanged. test_resolver: 53 passed
- [x] act 4: the suite, the Makefile test line from this worktree with it first on PYTHONPATH (`PYTHONPATH=<worktree> ./.venv/bin/python -m pytest -q`; `claude_session.__file__` checked to be the worktree's): 792 passed, 2 failed (test_readme status line: `784` rendered, 794 collected, the 10 new tests); lint, doclint, hygiene clean

- [x] act 5 (round one, F2 red): a holder spelling the share through a symlink or a doubled slash; at 5525a60 `removed 5, kept 1 (0 live, the newest 1)`
- [x] act 6 (round one): F2 fix (each absolute path in ps output compared by realpath, the literal share match kept for a share path with a space) and F1 docstring (platform binaries hide their environment; a launcher's python shows it); prune + install tests 14 passed; the suite 793 passed, 2 failed (test_readme status line, 795 collected now)

## Handover
- open by level: none
1. decide, owner: the observer (at landing): `make readme` re-renders the Status line (784 to the merged count, with s-stale-calls' tests); until then test_readme's two status cases stay red. Not run here: the render is the observer's.
2. decide, owner: the coordinator: no `make install` from main before this merges (main's rm loop repeats F8); the first install after the merge runs the new prune, so it is safe. Live launchers keep their old resolver until their next hand restart; part 1 is what protects them.
3. Logged (reversible): `--keep 3` (the new tree among them); a process ps cannot see (its cwd in a tree, a launcher between reading the old wrapper and its exec) is covered by the newest three, not detected.
- exit taken: F8 done (acts 0 to 6, round one folded); stopped before the gate and `make readme`, the coordinator's and the observer's

## Next act
The coordinator: review and merge; the observer: `make readme`, then `make install`.
