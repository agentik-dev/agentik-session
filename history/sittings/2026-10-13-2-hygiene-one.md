# Sitting 2026-10-13-2: agentik-session, hygiene-one (one scripts/hygiene in five repos)

| item | value |
|---|---|
| goal | one byte-identical `scripts/hygiene` in agentik-session, -agents, -decisions, -respeak, -relay, every pin moved to it |
| budget | 200k window, 180k context, stop at 80%; ~90 tool calls; one commit per repo; no push, amend, rebase, `make install`, relay verbs, `claude plugin` install/update |
| pin | worktree `.claude/worktrees/hygiene-one`, branch `hygiene-one` from main, in each of the five repos |
| window | 1M (a builder keeps 180k) |
| agents | 0 (a builder spawned by the coordinator) |

## Done-ness
- [x] act 1, the diff: session's copy (sha256 `acc3498d…`, conventions §6's) is canonical and unchanged; agents' was already it. decisions', respeak's and relay's copies carried choices session's charter 2026-10-13-1 ruled the other way (sibling out of the file, `person` skipped under sittings, oversize by path only, a non-UTF-8 list a usage error), or wording only; nothing ported
- [x] act 2, decisions: the copy, `HYGIENE_SHA`, `.hygiene-allow` gains the `sibling` rows the in-file group needs (the plugin's own name), two tests adapted (person scanned under sittings; the unreadable message)
- [x] act 3, respeak: the copy and `HYGIENE_SHA` (its comment); tests pass unchanged
- [x] act 4, relay: the copy and `HYGIENE_SHA`; the bad-line test reads `bad entry`
- [x] act 5, agents: nothing to change (no pin); acceptance only
- [x] acceptance: one sha256 in all five; `--require-private` 0 (0 outside) and `make hygiene` 0 in each; `make check` under the lock 0 in session (73 s), decisions (72 s), respeak (139 s); agents `make check && make test` 0 (182 s); relay's targeted lines 0 (`make hygiene doclint`, vet, `go test -race ./internal/hygiene/`, gofmt)

## Handover
- choice: session's copy is canonical as is, so conventions §6 keeps its sha; this charter is session's one commit.
- choice: decisions' sibling exceptions are per directory, as respeak's are, not one `*` row.
- choice: relay's `make check` (10 to 20 min) was not run here, by the 540 s rule; the gate runs it on `hygiene-one`.
- decide, owner: the observer. The packet named session's sha as `2ec2bcaf…`; the tree and §6 say `acc3498d…`, used here. Consumer: the gate's sha check.

## Next act
None: the observer reviews and publishes.

Exit: decisions 12984a6, respeak 0e37ac1, relay 8fadb9c, session this charter; agents unchanged at main; every line run 0; nothing pushed; worktrees left in place.
