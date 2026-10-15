# Packet S33: under a launcher, the CHECKPOINT line names the charter file and `checkpoint --respawn`

| item | value |
|---|---|
| from | the observer's check-in 126 (2026-10-15 11:37, macbase `history/observer/2026-10-15.md`); `design/respawn-r1.md` §3.2 (the marker) and its files list (the SKILL.md's CHECKPOINT and EXIT text) |
| pin | `main` at a83ce29 plus this packet's commit; branch `s33-checkpoint-respawn`, worktree `.claude/worktrees/s33-checkpoint-respawn` |
| wall | this repo; no push, `--amend`, rebase, merge, device, network, real `claude`, `agentik session run`, `claude plugin`, `make readme`, `make install` or `make check`; never write in the account's state directory (`~/.local/state/claude-code-session`); no `agentik-session` verb that writes; never run `relay` or `agentik relay` with any verb; never build or run a relay binary; never `pkill -f` |
| may touch | `claude_session/hooks.py` (`_checkpoint_out`, its caller in `post_tool_use`, `MAX_OUT`, a new helper that reads the recorded charter), `claude_session/cli.py` (`charter open` and a new helper that records its file; fix round), `tests/test_hook_meter.py`, `tests/test_charter.py` (one s33 test; fix round), `plugin/skills/session/SKILL.md` (the CHECKPOINT bullet only), `NICE_TO_HAVE.md`, this packet, `history/sittings/2026-10-15-1-s33.md` |
| acceptance | 1: `.venv/bin/python -B -m pytest tests/test_hook_meter.py -q -k s33 2>&1 \| tail -1` reads `passed`, no `failed` (pin: (a) to (d) failed); 2: `.venv/bin/python -B -m pytest tests/test_hook_meter.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; 3: `.venv/bin/python -B -m pytest tests -q -k "hook or respawn or chain or charter" 2>&1 \| tail -1` reads `passed`, no `failed`; 4 (fix round): `.venv/bin/python -B -m pytest tests -q -k "charter" 2>&1 \| tail -1` reads `passed`, no `failed` |
| verify | `make check`, by the coordinator, after this branch |
| budget | acts: 1 the tests red, then the line to green; 2 the SKILL.md bullet and NICE. 35 turns, stop at 28 (commit the act in flight), 150k; one commit per act |

## 1. What the source says

The check-in: network-konsume-config's sitting 2026-10-15-4 ran under `agentik-session run --chain network` (launcher pid 64813). At 80.4% its only CHECKPOINT line read `CHECKPOINT: 80.4% context (144757/180000), 8.2% turns (33/400); charter history/sittings; bring the charter current, commit, then exit`. Its brief never names `checkpoint --respawn`; it ran none, wrote no `respawn.json` (its sitting 3 did, at 08:17:19), stopped its loop at 08:28:53, and the launcher has waited on a marker since. The line names a directory, not the charter file, and says "exit" where the launcher needs the marker.

respawn-r1 §3.2: "The launcher learns that a sitting ended on RESPAWN from a marker the sitting writes, never from the transcript. `claude-session checkpoint --respawn --charter FILE` first does what `checkpoint` does today ..." The launcher sets `CLAUDE_SESSION_CHAIN` in the child's environment (`claude_session/chain.py:299`, `hooks.CHAIN_VAR`), which the hooks inherit.

## 2. Rulings

1. **When.** The new text applies when the hook's environment has a `CLAUDE_SESSION_CHAIN` that `hooks.CHAIN_RE` accepts, the check `cli.py` makes (fix round, the adversary's F4); unset, empty or refused, the line is byte-for-byte the pin's (the existing test at `tests/test_hook_meter.py:67` stands as written).
2. **The file.** The hook names a file only when this sitting recorded it: `agentik-session charter open` writes the absolute path of the file it made to `sessions/<sid>/charter.json` {path}, the session dir found as `checkpoint --respawn` finds it and only when the file's directory is exactly `<request.json's cwd>/<charter dir>` (no session id, no session dir, no recorded cwd, another directory, or a helper: nothing written, and open still succeeds; hardening round R1: a helper's Bash carries its parent's id, so its open in a worktree must not take the record); under a launcher the hook reads that record, and when the path is absolute, passes `_SAFE_PATH`, is a file and its directory is exactly `<payload cwd>/<charter dir>` (resolved), the line names it, else `<this sitting's charter>`. No directory is listed. Why (fix round): the first rule, the newest by mtime under the charter dir, named whoever's charter was newest, a merged child's file whose Next act is not RESPAWN, `-orient` over `-gr`, `-9` over `-10`, or `README.md` (the adversary's F1).
3. **The line under a launcher.** `CHECKPOINT: <the pin's two figures>; charter <file>; bring the charter current with a Next act that opens RESPAWN:, commit, then run \`agentik session checkpoint --respawn --charter <file>\` and end the turn; the launcher restarts this sitting`. With no file found, `<file>` reads `<this sitting's charter>`. At or past 100%, `EXIT_RULE` is appended as on the pin.
4. **The cap.** `MAX_OUT` may rise to at most 640. When the absolute path makes the output too long, the line uses the path relative to `cwd`, then `<this sitting's charter>`; never `{}` for a launcher sitting past its checkpoint.
5. **The skill.** SKILL.md's CHECKPOINT bullet gains one sentence: under `agentik session run`, the sitting runs `agentik session checkpoint --respawn --charter <file>` and ends the turn, and the launcher restarts it.
6. **Tests** (in `tests/test_hook_meter.py`, each name holding `s33`): (a) a recorded `<today>-1-orch.md` is named, even with a newer child's `<today>-2-s33.md` beside it; the line holds `charter <file>` and `` `agentik session checkpoint --respawn --charter <file>` `` and `end the turn`, `<file>` absolute or, past `MAX_OUT`, relative (F3: whatever the temp root's length); (b) chain set, no record: `--charter <this sitting's charter>`; (c) chain set, a 200-character cwd: the output's JSON is at most `MAX_OUT` and still holds `checkpoint --respawn`; (d) chain set, the tenth tool past the crossing repeats the same line; (e) chain unset, empty or refused by `CHAIN_RE`: the pin's line exactly; (f) no record: the placeholder, even with today's charters present; (g) a recorded path gone, outside cwd, unsafe, relative or junk: the placeholder. In `tests/test_charter.py`: `charter open` writes the record in a temp state dir, and none without a session dir or in a helper. (a), (b), (c), (d) are red on the pin.

## 3. Interfaces

No new key, verb or resolved-file field; one new file in the session dir, `charter.json` {path}, written only by `charter open` and read only by the PostToolUse hook (fix round). The CHECKPOINT line's text under a launcher is new hook output; say in the charter's handover whether the repo's conventions move the version for it, and do not bump it in this branch.

## 4. Findings that name this row

The check-in's S2. Two live chains lack the verb in their briefs (network-konsume-config, syrvis-konsume-config); this fix reaches them through `make install`, since every hook call runs the installed tree.

## 5. Forbidden reads

Transcripts; `~/.claude/projects`; the account's state directories (the session plugin's and the relay's). Read no other repo.

## 6. Report (capped)

At most 120 words: each acceptance line's tail; `make lint` and `make doclint` exits if they run without the state directory; the red tests on the pin; the line under a launcher as printed for test (a); any ruling beyond §2; the head sha.
