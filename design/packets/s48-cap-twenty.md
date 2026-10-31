# Packet S48: the restart cap's default moves from 12 to 20

| item | value |
|---|---|
| from | agentik-hq's design/03-standby-agent.md §10, the owner's answer of 2026-10-30 to its question 2: "entry 22's cap becomes 20, in [the Mac's] ledger and in agentik-session's default (`chain.py`'s DEFAULTS, `profiles.yaml`), this record's pieces the way back under it"; the readings in §1 |
| pin | 3fbaa35 (main, alpha.32); worktree `.claude/worktrees/s48-cap-twenty`, branch `s48-cap-twenty` |
| wall | this repo; no push, `--amend`, rebase, merge, device, `make install`, `make readme`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run a relay verb, or build or run a relay binary; never `pkill` by name or pattern; the Mac's ledger is not this packet's: hq carries it as a line to paste |
| may touch | `claude_session/chain.py` (`DEFAULTS`), `claude_session/profiles.yaml` (`respawn`), `tests/test_chain.py`, `tests/test_resolver.py`, `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `RUNBOOK.md`, `design/respawn-r1.md` (the current-state lines and its change log), this packet, the charter, and the version act's pins |
| acceptance | `.venv/bin/python -B -m pytest tests/test_chain.py tests/test_resolver.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; `.venv/bin/python -B -m pytest tests/test_chain.py -q -k s48 2>&1 \| tail -1` reads `passed` (on 3fbaa35: fails or deselects); `grep -nE 'cap: 12\|"cap": 12\|defaults 12' claude_session/chain.py claude_session/profiles.yaml README.md design/readme/source.md RUNBOOK.md` prints nothing; `make hygiene` exits 0 |
| verify | `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>`, last |
| budget | acts: 0 this packet; 1 the tests, red; 2 the two defaults and the texts; 3 the version, the README count, the sidecar (last, one bump; 694bf81 is the model). 40 tool calls, stop at 80% (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says, and the readings

The owner's answer is the table's first row. Its question read: "entry 22 caps a chain at 12 restarts a day; [two] launchers run `--cap 20` tonight, and both chains were relaunched past 12 today".

Readings at 3fbaa35: `chain.py:53` and `profiles.yaml:51` hold the two defaults; `chain.guards` lays the resolved key over `DEFAULTS`, so the yaml is the one a chain reads and `DEFAULTS` is the floor of a guards dict with no cap. The texts: `README.md:108`, its source's line 108, `RUNBOOK.md:411`, `design/respawn-r1.md` §3.5, §4, §6 criterion 17, §9 C3. The tests that pin the default: `test_s19_respawn_defaults`, `test_s20a_flags_override_config`'s `defaults`. No SKILL states the number.

## 2. Rulings

1. **The default.** `cap: 20` in both homes; `floor` and `settle` do not move.
2. **What overrides stays.** The user's profiles, the repo's `config.yaml`, `config.local.yaml` and `run --cap` each still win; a layer may set it under or over 20. A test says so for each.
3. **Tests.** A test whose subject is "the cap stops the chain" passes its cap explicitly and stays as it is. `FAST` and `G` in `test_chain.py` name a cap that does not bite and are explicit, so they keep their number; so does `_chain_lines`' old ledger line, which is a record of a past restart. Only the two pins above move. Names to write: `test_s48_the_default_is_twenty`; `test_s48_a_chain_with_no_cap_stops_at_twenty`; `test_s48_every_layer_still_overrides`; `test_s48_the_flag_still_overrides`.
4. **Texts.** A text saying what the default is now says 20. `design/respawn-r1.md`'s status, its *Why twelve* reasoning and the dated packets keep their words: *Why twelve* gains a sentence, as C4 gained S37's, and the record's change log gains a line. Packets S13 and S19 are dated and do not move.
5. **The version:** 2.0.0-alpha.33 in all five pins, one bump, last; the README count from the suite; the sidecar re-hashed by hand, as 0483fa8 did.

## 3. Interfaces (signatures, not prose)

None move. `run --cap N` and `session.respawn.cap` keep their reading and their validation.

## 4. Findings that name this row

None. The session-budget ledger's entry carries its own number; hq pastes that line. A plugin bump's marketplace line in commons is hq's too.

## 5. Forbidden reads

Transcripts; `~/.local/state`, every part; every other repo, but the one section of the source named above.

## 6. Report (at most six lines)

The branch and sha; the gate id and exit; the files that stated the default; anything decided; anything left over.
