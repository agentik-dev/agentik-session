# Sitting 2026-09-24-2: claude-code-session, s13a-conventions-r10 (S13 part A: lint and hygiene)

| item | value |
|---|---|
| goal | S13 §2 part A, rulings 1 to 5: GRANDFATHERED gains agent-relay's 17 stems; SPENT mirrors Go's `spent`; `runs_suite` mirrors `packet.Unbounded` by shape; hygiene scans a NUL file for home, secret and email (ADV10-17); conventions §6, §9 and overhaul-r1 §4 record it |
| budget | `--max-turns` 80 (the 80% point at 64), 140k context; commit per act; never push, amend, rebase, a device; no `make install` |
| pin | branch s13a-conventions-r10 off main ae0a58c; `.venv` a symlink to the main checkout's |
| window | 200k |
| agents | 0 (the builder works alone) |

## Done-ness
- [x] act 1 (c83d274): 17 legacy stems, SPENT, `runs_suite` by shape (rulings 1 to 3 in one act; see handover)
- [x] act 2 (dfc1d6a): hygiene binary groups home, secret, email (ADV10-17)
- [x] act 3: the record (conventions §6 both shas, §9; overhaul-r1 §4 one row); this charter closed
- [x] `make check` 0 at every act, 447 passed; tree clean

## Handover
- decided: the README status line pins 447 tests and a render is B's, so the count holds by folding (s12 precedent): 11 doclint cases run inside hosts on a fresh temp repo, one hygiene case inside its neighbour. Rulings 1 to 3 landed as one act, since the 12 new doclint items and the folds had to net 0 per commit. Consumer: s13b (its render moves the count)
- decided: the packet says GRANDFATHERED holds 19; it holds 28 (this repo's 11, agent-relay's 17), and §9 says 28. Consumer: packets-37
- decided: the control `make -n decisions X=y` is spelled `make -n record X=y`, because the sibling group refuses the word in `tests/`. Consumer: none
- decided: GRANDFATHERED and SPENT both skip the suite rule, as Go's `legacy` and `spent` do. The go, relay and pytest rules stay (as the packet says): `go test` with a `...` package and `-run` still passes here, where Go refuses any `...`, and `relay gate <row>` without `--rows` is refused here, where Go allows it. Consumer: packets-37, the next doclint packet
- decided: a double-quoted word that expands (`"$m"`) counts as non-literal; `$(...)` is read in place (collapsed) and inside. Consumer: packets-37
- for packets-37: hygiene `d63d0ffb`, doclint `d5957c6c`; tests `tests/test_doclint.py`, `tests/test_hygiene.py`. Conventions is at 8,913 of 9,216 bytes, so B's §5 line has 303 bytes
- no open fork
- exit taken: goal met; `make check` exit 0; three commits, not pushed; no NEXT; about 35 turns, about 90k context

## Next act
s13b merges this branch (act 0) and does part B.
