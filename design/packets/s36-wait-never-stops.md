# Packet S36: a wait never stops the loop

The brief's text, verbatim but for hygiene: "the sibling umbrella" stands for the private management repo the brief names, and a home path is dropped.

| item | value |
|---|---|
| from | the sibling umbrella's finding of 2026-10-20 by message (its `NICE_TO_HAVE.md`, last line, 5b7f769), on the owner's word of 2026-10-20 05:5x (the sibling umbrella 838edbf); `NICE_TO_HAVE.md:192` (S29's row: "nothing restarts a stopped loop"); `claude_session/chain.py` lines 7 and 502 (a restart only on a RESPAWN close) |
| pin | `main` at dce04b9 (alpha.18); worktree `.claude/worktrees/s36-wait-never-stops`, branch `s36-wait-never-stops` off it; this packet is on the branch |
| wall | this repo; no push, `--amend`, rebase, device, `agentik session run`, `claude plugin install/update/marketplace`, `make readme`, `make install` or `make check`; never write under `~/.local/state`; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; never write in another repo or its worktrees |
| may touch | `claude_session/rules.py` (`PACE` items 4 and 5, `clause`), `claude_session/charter.py` (`warnings` and its docstring only), `plugin/skills/session/SKILL.md` and `RUNBOOK.md` (their "Priority and pacing" sections), `plugin/.claude-plugin/plugin.json` (`version` only), `README.md` and `design/readme/source.md` (lines 113 and 135 and the status line) with `design/readme/rendered.sha256` re-hashed (`shasum -a 256 design/readme/source.md README.md`), `tests/test_rules.py`, `tests/test_charter.py`, `tests/test_hook_session_start.py`, `design/packets/s36-wait-never-stops.md`, `NICE_TO_HAVE.md` (what is filed outside), `history/sittings/*.md`, `history/sessions/NEXT` |
| acceptance | `.venv/bin/python -B -m pytest tests/test_rules.py tests/test_charter.py tests/test_hook_session_start.py tests/test_readme.py -q 2>&1 \| tail -1` reads `passed`, no `failed` (on dce04b9: `227 passed`); the act-1 commit's new tests fail on dce04b9; `grep -HE "stops the loop\|the loop stops\|loop stopping\|toward the stop\|at the stop" claude_session/rules.py claude_session/charter.py plugin/skills/session/SKILL.md RUNBOOK.md README.md design/readme/source.md \| grep -vcE "no wait stops the loop\|never stops the loop"` reads 0 (on dce04b9: 10); `grep -c '"version": "2.0.0-alpha.19"' plugin/.claude-plugin/plugin.json` reads 1 (on dce04b9: 0); `grep -c 'v2.0.0-alpha.19' README.md design/readme/source.md` reads 1 and 1 (on dce04b9: 0 and 0) |
| verify | `make check`, by the coordinator (the hq sitting), one `make` at a time on this Mac |
| budget | acts: 1 tests, red; 2 rules and charter; 3 docs, the version, the README count. 40 turns, stop at 32 (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says (quoted)

`rules.PACE` item 4: "waiting on an outside party: the Next act says `WAITING <n>: <what>; <how to tell>`, a long delay, n the wakes in a row with nothing changed, the loop stopping at n = {waiting} (a respawn reads n from the charter)". `clause()`: "WAITING {waiting} stops the loop, a meter wait never". `charter.warnings` at n >= `waiting`: "the loop stops; close the sitting, the outside party unchanged". `chain.py` line 7: the launcher restarts a "sitting only on a RESPAWN close the main thread confirmed"; a loop that stopped on WAITING 3 leaves its claude at the prompt, which the launcher never reads (NICE:192: "nothing restarts a stopped loop, so example-ops sat idle about four hours until the owner's hand", 2026-10-13). On 2026-10-19 and 20 the sibling umbrella's loop stopped three times on WAITING 3, each read by the owner as something to restart. The owner's word (the sibling umbrella 838edbf): "from the third WAITING in a row the wake is 3300 s (the cache's idle limit) and the charter is brought current and committed, and the loop never stops on a wait: under the launcher only the checkpoint ends a sitting, and nothing is ever the owner's to restart."

## 2. Rulings (the hq sitting's, reversible)

1. `PACE` item 4 reads, exactly: `waiting on an outside party: the Next act says \`WAITING <n>: <what>; <how to tell>\`, n the wakes in a row with nothing changed; from n = {waiting} the wake is the longest idle wait the cache allows (item 6) and the charter is brought current and committed; a wait never stops the loop, since under \`agentik session run\` a stopped loop only idles until a hand, and only the checkpoint ends a sitting (a respawn reads n from the charter)`. `test_s21_render_lists_levels_rules_and_pacing`'s "n = 3" still holds.
2. `PACE` item 5 keeps its text to "whichever is first" and ends `, and it never counts toward n` (there is no stop). `tests/test_rules.py`'s `METER` follows.
3. `clause()`'s pacing part ends `no wait stops the loop; WAITING {waiting}+: idle limit` in place of `WAITING {waiting} stops the loop, a meter wait never` (S29's phrase is subsumed). Measured: `BLOCK` is 288 bytes (was 286) and with `CLAUSE["1h"]` 318, inside the 320 bound, so the 1h tail still names the limit; `test_s21_clause_bound_at_320_bytes`'s pinned length and the two `WAITING 9 stops` assertions (`tests/test_hook_session_start.py` lines 198 and 247, `tests/test_rules.py` line 93) read the new words; `S21_BLOCK` and `BLOCK` likewise.
4. `charter.warnings` at n >= `waiting` prints, exactly: `WAITING {n} is at session.pacing.waiting ({waiting}) or past it: wake at the cache's idle limit, bring the charter current and commit it; a wait never stops the loop or closes the sitting, only the checkpoint does`. One line, exit unchanged; the S29 meter line and the misshapen line stand; the docstring says it. `tests/test_charter.py`'s `S29_STOP` names the new line's `never stops the loop`; the `at-the-stop` id and its wanted phrase `session.pacing.waiting` stand.
5. Docs say rulings 1 to 4 in their own words: SKILL.md's `session.pacing` bullet and its "or at the stop" (now "or at `waiting` or past it"); RUNBOOK §4's Pacing bullet and its "at the stop" sentence (§3's `waiting` 1 to 9 stands); README.md line 113 ("`WAITING <n>` stops the loop at `waiting`" becomes "from `WAITING <n>` at `waiting` the wake is the cache's idle limit, and no wait stops the loop") and line 135, the same in `design/readme/source.md`, the sidecar re-hashed. The status line reads the new version and the suite's new count (`test_status_line_matches_manifest_and_suite`), in both files.
6. The version is 2.0.0-alpha.19 (SKILL.md is under `plugin/`; GUIDE §7): the block's contract, one `; `-opened line of at most 320 bytes, stands, as S29's alpha bump read it. The marketplace line in commons moves at the install, by the hq sitting.

## 3. Interfaces (signatures, not prose)

`rules.PACE` (a tuple of texts, `.format(**pacing)`; items 4 and 5 are `PACE[3]` and `PACE[4]`), `rules.clause(session, ttl=None) -> str`, `rules.render(session, life=None) -> str`, `charter.warnings(raw: bytes, session: dict) -> list[str]`; the fixtures `session(...)`, `rules()`, `BLOCK`, `METER` (`tests/test_rules.py`), `_s21_charter`, `_s29_warns`, `S29_STOP` (`tests/test_charter.py`), `S21_BLOCK`, `_s21_ctx` (`tests/test_hook_session_start.py`).

## 4. Findings that name this row

the sibling umbrella's NICE line (above); `NICE_TO_HAVE.md:192` (S29, landed: its "nothing restarts a stopped loop" is this packet's ground; the row stays, an item leaves when it lands); the research survey's line 188. The README's status line counts the suite: raise its count by the tests added, in both files, and re-hash the sidecar.

## 5. Forbidden reads

Transcripts under `~/.claude/projects` (grep only, and none is needed); `~/.local/state` beyond reading; every other repo (the finding is quoted here).

## 6. Report (one table, at most five bullets, under 600 words)

Acts with commit shas; acceptance output verbatim; the red-before evidence (the act-1 tests failing on dce04b9); the block's byte counts (`BLOCK`, and with the 1h tail); anything filed outside the packet, with its NICE line.

Amendment 1 (2026-10-22, the coordinator's ruling, reversible): `may touch` also covers, for the version only, `claude_session/__init__.py` lines 3 and 5 (`2.0.0a19`, `2.0.0-alpha.19`), `pyproject.toml:7` and the pin at `tests/test_doctor.py:316`, since GUIDE §7 keeps one version, which `test_versions_agree` checks.

Amendment 2 (2026-10-22, the coordinator's ruling, reversible): `may touch` also covers `tests/test_install.py:222`, its version pin only (`agentik-session 2.0.0-alpha.19\n`), the last place the old version is pinned outside history, packets and NICE.
