---
status: current
updated: 2026-10-04
owner: owner
audience: owner, agent
---
# claude-code-session: what a review left open, none of it blocking

## S44, the demand bands (2026-10-30)
- S4: `status --transcript` shows no band: it reads a transcript, not this session's band. A reader that wants one takes it from band.json.
- S4: `grade` in `bands.yaml` is the source's text, and nothing reads it.
- S4: the twins differ on stamps `_stamp` never writes, so `wall` could refuse what `_when` refuses.
- S4: `status --json` passes a past-end `demand` raw, where the plain line leaves it out.
- S4: a dangling symlink at the user's `bands.yaml` is silent: it reads as no file, with no `doctor` row.
- S4: no real wheel was built offline; only the package-data line and the frozen tree are checked.

## S43, the lines on a login with no five-hour window (2026-10-30)
- S4: `rules.py`'s rendered waiting rule still reads `(room for 0, or a usage limit hit)`, and `tests/test_rules.py` pins it, while the charter's pattern and the two docs now name the week and the band too; the packet allows only `lifetime` in that file. A packet that touches the rendered rules takes it.
- S4: the twins differ on a stamp at datetime's very ends: Python's `_wall` refuses 0001-01-01 and 9999-12-31, `wall` in `session.ts` takes them. Older than this change and on both lines; `_stamp` never writes one.
- S4: a `next week` wait hits the meter-wait return before `_red`, so a red charter with that wait exits 0; `test_s29_meter_wait_keeps_the_exit` is the pin to revisit.
- S4: hyphens read as boundaries, so `mid-week`, `band-aid` and `7d-old` count as meter waits.
- S4: numeric corners of `_pct` against `whole` differ (`7d 1e+21%`), unreachable from the writer.

## The research site's vendor-docs check (2026-10-14): one behaviour item left
- S4: PreCompact's quiet pass rests on an undocumented reading, that a passing PreCompact's stdout becomes the compaction's custom instructions (observed on claude 2.1.296; `claude_session/hooks.py` `QUIET_PASS`). The "Hooks reference" of 2026-10-14 sends most events' passing stdout to the debug log and does not list PreCompact as an exception. Add a check that fails loudly when the behaviour changes, such as a `doctor` probe or a gated live test that runs a manual `/compact` under a PreCompact hook printing a marker and looks for it in the summary. It needs a real `claude`, so it waits for a sitting that may run one. Source: the research site's fix prompt, item 8.

## band-target's verify round (2026-10-14, the observer): PASS, two notes
- S4: `design/admission-r1.md:44`'s peak formula still writes `min(T, …)` for the helper terms, which keep the five-hour horizon since the fix round. (verify note 1)
- S4: `admission.py:815` and `:958` (older than this change): P7 and the denial check still skip past-reset seven-day readings without first taking the newest, so F1's rule does not reach them; a probe gave `denied` on an older 98% while the band showed P7 60. (verify note 2)

## The observer's check-in 117 (2026-10-14): a lead, not confirmed
- S4: the band's projected peak rose while a session sat idle (a consumer sitting's charter read 286%, then 365%, with no helper running), so the fit may count only active minutes and over-project after a quiet spell. Confirm with the admission ledger's readings over an idle hour before any fix. (the observer's Explore helper, from the sitting's charter and its hook line)

## A helper call no batch resolves (2026-10-11, the stale-call fix)
- PostToolBatch now closes a helper's call that another PreToolUse hook blocked. Unverified with a real `claude`: a helper call whose batch never resolves, such as an owner's denial that aborts the helper or an interrupt before the batch ends, may still leave `calls/<id>` open. A backstop is SubagentStop closing every call of its `agent_id`, which needs the call file to record the id. Claude Code's live calls are the measure: of 2026-10-11's sessions, 13 held call files older than 30 minutes.

Nothing here blocks a review or a merge. An item leaves when it lands, or when a ledger entry retires it. The labels are the model-ceilings refuters' (2026-09-28): r1 is round 1 and r2 is round 2. Their r1 F1, r1 F2, r2 F1 and r2 F2 landed in the fix rounds.

- S18, 2026-10-04: `README.md:143` says `make check` "holds off when the load rises above 4 x cores" (the source's line 143 likewise); `scripts/bounded` now holds only while the CPU's idle share confirms that load (25% or under, `BOUNDED_IDLE_FLOOR`). Add the clause at the next render; S18's ruling 5 kept the README untouched.
- The observer, 2026-10-01: `charter open` cuts the goal in the title line at 60 characters, in the middle of a word (`claude_session/charter.py:117`, `_one_line(goal, 60)`); two charters' titles end "keeps its umbrell". Cut at the last whole word. The goal row of the table holds the whole text, so nothing is lost. (confirmed in the source and in both charters) Fixed 2026-10-11 at 4aeeec9 (merged 94869be).
- The observer, 2026-09-30: the ledger holds more than one row for a session that was resumed, against "one line per ended session" (`ledger.py:1`). Five of 174 sessions have two or three rows; `2b00cb4a` (example-app) has three with the same 56 turns, so `report` counts its tokens three times. Replace the session's earlier row at SessionEnd, or have `report` keep the last row per session. (confirmed in `ledger.jsonl`)
- The observer, 2026-09-30: fresh evidence for the `--resume` item below. Session `9b6e8f33` ended as `orchestrator`, 400k, zone notice; its resumed row reads `frontier`, 180k, 358k used, zone exhausted.
- The observer, 2026-09-30: the ledger's `max_context` is the total's, helpers included (`ledger.py:94`), and `report` sets it against the main thread's ceiling. Session `8c6fe6f0` (example-app) reads 369k of 400k in the ledger; its main thread peaked at 301,760. Write the main thread's own maximum beside it. (confirmed against the transcript's usage records)

- The relay should export CLAUDE_SESSION_PROFILE=builder to the children it spawns (the depth >= 1 fallback was not built).
- r2 obs: a child session with no helper mark, such as a Workflow script's child, inherits the role the README's start steps export; in an `orchestrator-opus` repo with no payload model it reads 400k on a 200k window (not reproduced).
- r2 obs: the plugin takes a helper only when `CLAUDE_SESSION_HELPER` is `1`, while the relay's hook takes any value that is not empty; agree on one rule.
- r2 F3: `design/readme/source.md:75` says `claude-session start <profile>` launches Claude Code with that profile, but `start` knows only the legacy configurations and exits 1 on both new roles (the refusal predates the branch); write `start <configuration>`, name the legacy ones and point to the `CLAUDE_SESSION_PROFILE` steps.
- r1 obs, r2 obs: the SessionStart payload carries no `model` under `claude -p`, an interactive `--continue` or `--resume` start, or `/clear`; the declared model then decides, so `orchestrator-opus` on plain Opus reads 1M and 400k. `models.py` and the README read as if the payload always carried it, and `save_request` writes null over the startup model on resume.
- r2 obs: `claude --resume` from a shell without `CLAUDE_SESSION_PROFILE` resolves as `frontier` again (180k on 1M); the README gives no warning, and the `config.local.yaml` route avoids it.
- r1 obs, r2 obs: a `/model` switch between `opus` and `opus[1m]` without `set` stays unseen until the next SessionStart, because the transcript's id is the same; this is inherent, and the docs state it.
- The README (source line 78) does not yet say that `claude-session set model` drops the payload's model until the next SessionStart (the r2 F1 fix); say so at the next `make readme`.
- r1 obs: a flow map `session: {profile: orchestrator-opus, model: opus[1m]}` is refused as a nested flow collection; the docs do not say to quote `opus[1m]` there or to use the block form.
- r1 obs, r2 obs: `sonnet[1m]` and `fable[1m]` are Claude Code aliases, and the table has no `sonnet-1m`, so a `sonnet[1m]` session reads 200k and gets 180k (the safe direction); `opusplan` and `best` name no family.
- r1 obs, r2 obs: family matching splits an id on characters that are not letters or digits and lowercases it, so a user table key with a hyphen or capitals (`gpt-5:`, `Opus:`) never matches and gives no warning, a key such as `claude` matches every id, and `qwen3-opus-distill` matches opus.
- r1 obs: `models.configured` reads the settings files from the payload's cwd, not the project root, and those files are not in `provider.inputs` with a sha256.
- r1 obs, r2 obs: a user `defaults.ceilings` that only restates 180k and 400 removes the orchestrators' 400k on 1M, and doctor gives no warning; a user `defaults.ceilings` outranks a role's ceilings while a user `defaults.model` does not outrank a role's model, which the README could state in one sentence.
- r2 obs: `_WSRC` in `hooks.py` strips `/`, so `declared:local/default` prints as `declared:localdefault` in the SessionStart line (cosmetic).
- r2 obs: the marketplace is a directory source at the main checkout, so `claude plugin update` reaches alpha.2 only after the merge; `make install` alone carries the function (not reproduced).
- r1 obs: `claude plugin validate` warns five times that `${CLAUDE_PLUGIN_ROOT}` is unquoted in `hooks.json` (predates the branch).
- sitting 2026-09-28-6: a relay child's meter should take its ceilings from its row. The relay strips `CLAUDE*` variables from its children, so a Fable child resolves the default role and is told to checkpoint at 144k (180k on 1M), while its row allows 400k (an example-app row, 2026-09-29). Read `RELAY_ROW` and the row's budget, or resolve a relay child as a builder with the row's context.

S17 (the EXIT rule says respawn, never compact), review round 1, 2026-09-30:

- `make readme` re-renders the whole README for a one-number source change (584 to 586 reworded 43 lines), and its prose-only verifier passed a changed fact (F1 below). Render only the changed paragraphs, or have the verifier compare zone and verb lists.
- F1: `README.md:102` says `deny` refuses a spawn "during the reserve zone"; the source says "in the reserve", and `hooks.py:122` refuses in reserve and exhausted. Re-render, or say "from the reserve on".
- F2: `README.md:9` orders the source's "four things" as "First … Then …" and drops "one" from "one resolved configuration".
- F3: `test_s17_profiles_never_compact` forbids two exact phrases; "the first checkpoint compacts, the second respawns" passes. Assert ruling 2's exact description text.
- No test pins the new rule's text in `SKILL.md` or `design/overhaul-r1.md`; `design/packets/s4-meter.md:23` (closed) still quotes the old rule.
- S17's `SKILL.md` bullet has not reached the installed plugin: `claude plugin update` compares versions only and S17 kept 2.0.0-alpha.2. The CLI (`make install`, tree a90a0217) carries the new EXIT line, so the hook is right; the skill text lands with the next version bump.

## S18's review round (2026-10-04): two adversaries, nothing blocking
- The two-polls test passes when three polls are needed, because `BOUNDED_IDLE=10,60,60` repeats its last value; end the series with a low share (`10,60,60,10`). (adversary 1, mutant `three_polls`, `tests/test_bounded.py:299`)
- No case puts the idle share exactly at the floor, so `idle >= floor` passes the suite. (adversary 1, mutant `ge_floor`, `tests/test_bounded.py:327`)
- Four ported behaviours have no test here, only in the relay plugin's Go tests: `kill_reader` on TERM, the read capped by the wait's limit, the sliced sleep, and the guard on a poll that is not positive (`scripts/bounded:498`, `:341`, `:356`, `:321`). Each mutant passes this suite. (adversary 1)
- `scripts/bounded:59-60` names the relay's `night.DefaultIdleFloor`; only the relay's tests pin the two floors together. (adversary 2)
- `-B` covers the guardian only, not its command: `make check` left `.pyc` files in `claude_session/__pycache__` (03:50). The Makefile's python lines are the place, as the relay's AR52 did. (adversary 1)
- respawn-r1 left open (the refuter's verify round, 2026-10-10, nothing blocking): (a) `activity.json` is overwritten by every main-thread PreToolUse, so with parallel tool calls the stamp can belong to a sibling call and a true marker stays unconfirmed (fails safe; §3.2 step 5). (b) Widening the PreToolUse matcher to `*` adds a hook process with a 5 s timeout to every tool call. (c) A flag value that begins with `-` (`--append-system-prompt "- x"`) is refused as an unknown flag by the §3.1 allowlist.
- respawn-r1, from the P4 measurement (the observer, 2026-10-10): the main thread's Stop fires while an Agent helper still runs. The PostToolUse hook already sees the helper's `agent_id` payloads, so it could stamp `helper-activity.json` instead of returning at once, and the ready condition could also want that stamp quiet for `settle`. That narrows §3.9's blind spot to a helper that makes no tool call.
- respawn-r1, for the packet (the observer, 2026-10-10; observed, not documented: the "Run prompts on a schedule" page of 2026-10-14 names no such question, and says a self-paced `/loop` waits between 1 minute and 1 hour and `/loop 5m` runs 4 minutes 45 seconds after the last run to keep the 5m cache warm): a `/loop` of 60 minutes or more answers the loop skill's cloud-or-session question (AskUserQuestion) before it arms, so a successor started on such a line waits at that dialog unattended. A `/loop` with no interval asks nothing. P2's measurement uses the real start line. The launcher's start-line guidance names the case, and the observer's `3h` line changes with §8's start lines.
- respawn-r1, for S20 (S19's review, 2026-10-10): a helper's PreToolUse and PostToolUse stamp `helper-activity.json` (ruling 6), but one long helper call (a 9 to 12 min gate) still leaves the stamp older than `settle`. The ready condition needs an open-call record: PreToolUse opens it, PostToolUse or PostToolUseFailure closes it.
- respawn-r1, S19's review notes (2026-10-10), for S20: (a) `restarts_in` counts at most one per unparsable line, so a torn restart line glued to a whole one counts once; S20's own tally covers it. (b) `append_chain` accepts a non-string `at`, which `restarts_in` then counts forever (fails closed); S20 leaves `at` out or passes ISO. (c) RUNBOOK.md still says PreToolUse on `Agent|Task|Workflow` and omits Stop; RUNBOOK is S20's. (d) Cost: PreToolUse on every tool adds about 58 ms per tool call (median of 20), and Stop about 58 ms per turn end.
- respawn-r1, S20a's review (2026-10-10): a helper's tool call that never gets a Post event (a denied tool, say) leaves its `calls/<id>` open and may hold its sitting open until the owner exits; S20b's PostToolUseFailure registration narrows it; unverified without a real `claude`.
- respawn-r1, S20a's round-two review (2026-10-10): (N3) `/loop check every 2 hours.` with a trailing period gets no long-loop warning; (N4) a ledger tail torn inside a UTF-8 character makes `read()` raise UnicodeDecodeError and keeps the cap closed until the file is repaired (predates the round); (N5) `run --cap ' 5'` now exits 2 (it was accepted).
- respawn-r1, S20b (2026-10-10): (a) the doctor's older-CLI check reads its own `hooks.HANDLERS`, so it judges the CLI that runs it; an older installed CLI's own doctor cannot see the gap, and the shim and the install order (CLI first) carry that case. (b) S19's note (c) is done: RUNBOOK §1 step 2 names every tool, Stop and PostToolUseFailure. (c) A BSD tty sets PENDIN when canonical mode comes back, so the terminal test compares attributes without it.
- S21 (2026-10-10), S4: a ScheduleWakeup nudge (a hook that names a wakeup taking its own turn, or one re-armed while a helper is pending) is not built; `claude-session rules` states the pacing and no hook enforces it (the packet's ruling 4).

## s21 round one, 2026-10-10: one adversary, F1 fixed, these notes left
- N1: `fallback` is capped at 3600 and `waiting` at 9, stricter than ruling 2 ("60 and 1 or more"); `waiting: 10` or `fallback: 3601` fails the whole resolve, so SessionStart writes nothing. The cap keeps the block at or under 320 bytes; RUNBOOK §3 and `rules.py` state it.
- N2: `rules` reads this session's resolved.json, while `charter check` and `close` resolve fresh from cwd; with a resolved.json that lacks the keys (alpha.4's, or a config changed mid-session) `rules` prints "priority: on" while `check` reads it as off.
- N3: a level text ending in "\n" passes as one line and `rules` prints a blank line; ESC and TAB pass too and reach the terminal through `rules`. The SessionStart block is safe, since labels keep to the label alphabet.
- N4: launched with a profile, that profile's unknown field is listed twice in `unknown`, under "profiles.yaml:" and "launch:".
- N5: the packet's flow shape `priority: {levels: {S4: "..."}}` is refused as a nested flow collection; the RUNBOOK's block form resolves.
- N7: a Next act opening `RESPAWN: WAITING 3: x; y` is not read as WAITING (`warnings()` returns []), so neither the stop warning nor a respawn sees a waiting sitting that closes at 80%; a design question.
- N8: an alpha.4 CLI under this plugin prints no block, and its `claude-session rules` exits 2 ("invalid choice"); the skill names the verb without a version, and RUNBOOK §4 gives the install order.
- N9: `rules.check` names the key but not the layer ("pacing.waiting must be an integer from 1 to 9"); a bad value drops the whole SessionStart line and resolved.json, as respawn's keys do (ruling 2), and `claude-session run` refuses too.

## admission-r1 verify round (2026-10-10): notes, no block
- A nested helper's spawn gets the wake promise, but the wake goes to the main thread without the deferred prompt.
- "by 14:06 at the latest" fails when the sitting is busy at the reset or was restarted by hand; say "at the next idle turn after 14:06".
- Notes 1 and 5 of the refuter's round were folded but are not listed in the record's fold notes.
- `session.end` hooks get 1.5 s in total, less than the 2 s lock wait: the end hook's clearing of a session's admitted helpers can be cut. Bound the end hook's wait under 1 s, or clear stale entries at the next start.
- The owner questions carry no Proposed line because this repo has no ledger (`decisions render --lint` on a scratch copy says so); by the observer's brief, a plugin repo writes the four parts by hand.

## Observer, 2026-10-11
- `charter open` clips the title's goal at 60 characters and the goal row at 300 with a bare slice (`charter.py` `_one_line`), so both can end mid-word; orient 2026-10-11-1 opened with "…2026-10-1" and "…in stack order w" and fixed them by hand. Clip at a word boundary and mark the cut, or keep the goal whole and clip only the title. Fixed on branch f3-charter-clip: `_one_line` now cuts after the last whole word that fits and marks the cut "…" within the limit, cutting hard only when the window holds no space.
- Idle compaction (Claude Code 2.1.296, setting `idleCompaction`, default on; it fires after about 54 idle minutes above 200k tokens) compacted two sittings overnight, against portfolio entry 17. The "Settings reference" (as of 2026-10-14) adds its conditions: an interactive terminal session, the conversation on the 1h prompt-cache TTL, feature-flag fetching on, the context at or over the threshold (200,000 by default, changeable), and about 54 minutes since the last request with the computer awake. The key needs Claude Code 2.1.290 or later; `autoCompactEnabled: false` also turns idle compaction off, and is the only off switch on an earlier version. So a sitting on the 5m TTL (an API key, usage credits) never idle-compacts. `doctor` could warn when neither `idleCompaction: false` nor `autoCompactEnabled: false` is set. A PreCompact hook cannot tell the idle pass from a normal auto-compact (both carry `trigger: "auto"`, observed on 2.1.296; the "Hooks reference" of 2026-10-14 now lists idle compaction under the `auto` matcher), so a hook block would block both.

## `make readme` fails three times running (2026-10-11, the observer)
- After F3 (94869be) the suite holds 783 tests and the README says 781, so `test_status_line_matches_manifest_and_suite` fails until `make readme` renders. On 2026-10-11, three runs on main all failed: at 13:13 respeak-verify-edit.py refused the render; at 13:23 and 13:36 `scripts/bounded --wall 600` cut it at the wall (load 5 to 9, exit 124). The render prints no progress, so it cannot show which round ran long. It rendered on 2026-10-10. Ideas: print each round's time; give the wall room for the verifier's rounds; let a count-only change to the Status line skip the render.
- The cause (F5, from the runner's transcripts): one round of this 23 KB prompt took 523 s, 529 s and 566 s, nearly all of it the model's thinking, so the 600 s wall left about 30 s; the 13:15 and 13:26 runs were still thinking at the wall. Fixed on branch f5-readme-render: `scripts/readme-render` passes `--max-rounds 2` and `RESPEAK_RENDER_WALL=900` and prints the renderer's time, and `make readme`'s wall is 2000 s, the budget (`test_readme_wall_covers_the_renderer_budget`).
- Left open, respeak's side: the 13:05 round dropped the sentence holding "320" (`numeric tokens: lost {'320': 1}`), and F5's 13:38 round turned the Precedence bullet into a paragraph and added two code spans; the contract forbids both, and respeak-render.sh's rounds retry only its style gate, never the invariants its own verifier checks, so such a round is final. Of the 13 rounds since 2026-09-24 that finished, 10 passed the verifier. A render could retry with the verifier's lines appended to the contract, or a Status-line-only change could skip the render.

## F7 and F8 round one (2026-10-11, the observer): notes, S4
- F7: a call that ends by an interrupt (`aborted_tools`) or a PreToolUse `continue:false` returns before PostToolBatch fires (read from claude 2.1.296), so its `calls/<id>` can still stick and hold RESPAWN. The user's deny hook uses `permissionDecision`, so it is closed. Entries already stuck (example-app orient 543a8b2e) need clearing by hand.
- F8: Makefile:40's "every old tree kept" would be false if prune-trees died partway (not reproduced). A launcher run from the live checkout no longer re-reads an edited shipped profiles.yaml (the snapshot is at import).
- The plugin version must move with any change under plugin/ (hooks.json here): `claude plugin update` caches by version. A check that ties the two would keep a merged hook from never reaching a session (agent-relay's F6 was the same).
- S4, unconfirmed source: at the observer's close of 2026-10-11 18:15 (session cbfe3c4f), two `calls/` entries (toolu_01FZrM… opened 16:17:33, toolu_01S2M3… 17:13:33) appeared in none of that session's transcripts, neither as a tool_use nor as a result. They were removed by hand once nothing could still run. Something opens a call entry for an id the transcript never records; a `calls/` entry could carry its opener (event, agent_id, tool name) so a stuck one can be traced.

## mod-r1 refuter round one (2026-10-11, the observer): PASS, notes S4
- N1, for the slice's packet: in C1's wiring, a CLI older than the plugin blocks every compaction, an owner-typed one too. hooks/run passes the exit code through, and the CLI exits 2 ("invalid choice") on `hook PreCompact`, reproduced at dc8d4d9 and on design-mod. Fix in the shim: map any non-zero exit for PreCompact to 0 and keep its stdout. Done by C1 (`c1-precompact`): hooks/run's `PreCompact) ...; exit 0`.
- N2: §8's question is settled by portfolio entry 17 (a sitting never compacts; a compaction needs the owner's hand), and option (c) contradicts it: mark (a) decided and drop "once §8 is answered". Done by C1: §8 marks (a) decided.
- N3: §9 says "Not decided here", but the owner's word of 2026-10-11 18:10 settles it: no plugin forces its siblings on other users, so the hard `dependencies` go. Done by C1: plugin.json has none, and doctor reports the siblings as optional, with no range.
- N4: S1 "writes nothing", yet `mod start` writes mod.json.
- N5: claude 2.1.296 refuses `$.state.set` during `ui.render`; AC2's grep does not catch `state.set`.
- N6: classic hooks also skip an untrusted folder, so that case is not mod-only.
- N7: the band's "41/60 s" needs the launcher's `settle` value, which none of the three files it reads holds.
- N8, unchecked: no "three crashes" count was found, only a crashed module being unloaded; `userConfig` being machine-wide and the classic-through-mod routing were not resolved (P1 covers the latter).

## `record`'s over-cap refusal says "summed" twice (2026-10-11, the observer; S4)
- `plugin/scripts/record:199` reads `the request's sections sum to {human(total)} summed, over --max-bytes ...`, and `human()` already appends "bytes", so the refusal prints "sum to 8,554 bytes summed". Reproduced by the observer at 20:19 (`--section '3-9'` on the observer prompt) and seen by check-in 97's helper ("sum to 11,615 bytes summed"). Fix: drop the trailing "summed"; a test on the refusal's text.

## Prompt-cache audit (2026-10-12, the observer; S4)
- Idle wakes miss the 1h cache. `rules.py`'s pacing says "a long delay" with no cap, and ScheduleWakeup turns 3600 s into 3636 to 3648 s (observed in the audit's transcripts, 2026-10-09 to 10-12, on the Claude Code of those days; the audit did not record the version, and the "Run prompts on a schedule" page documents no such delay as of 2026-10-14), so the wake lands past the main loop's 1h TTL and rewrites the whole context: 26 such misses over three days wrote about 4.8M tokens (about 235k to 265k each, at the 1h write price of 2x). Fix: pacing caps an idle wake below the lifetime in force, read rather than assumed (3300 s on the 1h TTL; on the 5m TTL no idle wake stays warm), so it reads a warm cache. The repro is the audit script below. Fixed on branch s30-cache-lifetime (packet S30): `rules.lifetime` reads the lifetime in Claude Code's order, and the block, `rules` and the prompt line name it.
- The lifetime in force (Claude Code's "How Claude Code uses prompt caching", as of 2026-10-14): the main conversation, `-p` runs included, gets the 1h TTL only on a Claude subscription within plan usage; on usage credits, an API key or a cloud provider it gets 5m. Subagents and every request outside the main conversation get 5m (bar a few server-controlled helpers). `promptCacheTtl` and `subagentPromptCacheTtl` (`5m` or `1h`, Claude Code 2.1.242 or later; env `CLAUDE_CODE_PROMPT_CACHE_TTL`, `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`) set each bucket, and `FORCE_PROMPT_CACHING_5M=1` overrides both. A sitting that spills onto usage credits drops to 5m mid-sitting.
- The prices (Anthropic's "Pricing" page, as of 2026-10-14): a cache write is 1.25x base input for 5m and 2x for 1h; a read is 0.1x on most models, 0.05x on Opus 5.5 and Sonnet 5.5, and 0.025x on Fable 5.1 and Mythos 5.1. The 4.8M rewritten tokens, at the 1h write against a warm read: Opus 5.5 ($4/MTok base) about $38.40 against $0.96; Fable 5.1 ($10) about $96 against $1.20; Sonnet 5.5 ($2) about $19.20 against $0.48. The audit did not split the misses by model, so the dollar figure is a range across these until it does.
- Nine top-level calls after short gaps (0.1 to 29 min) reread only the system-plus-tools prefix (25,387 or 30,622 tokens) and rewrote the rest: 1.17M tokens, cause unknown. The status line's `prompt_cache.last_miss_cause` (statusline docs) names it, so the meter could log that field into the ledger on a miss.
- The source is the audit (usage fields only, 649 transcripts, 10-09 to 10-12). Read shares were 98% for launcher sittings, 97.6% for relay `-p` children (1h TTL, no gap misses) and 97% for subagents (5m TTL; 14M tokens of misses after 5 to 60 min pauses, kept on 5m since 1h writes would cost more than they save).

## S22, a close names its commit (2026-10-12, the builder): notes, S4

- S4, for the README's next render (`make readme`, a respeak run): its status line reads `v2.0.0-alpha.7` and 838 tests, and it says nothing of close's `next:`/`then:` lines or the respawn's refusal of an uncommitted charter. Repro: `pytest tests/test_readme.py -k status_line` reads `assert 838 == 848`.
- S4: the Stop hook does not see a sitting that closes on RESPAWN and ends its turn without `checkpoint --respawn` (F13, the example-ops orchestrator at 2026-10-12 04:28); close's printed `then:` line is S22's answer. Repro: close a charter whose Next act opens on RESPAWN and end the turn: no `respawn.json`, no hook line.
- S4: `checkpoint -c --respawn` passes a tracked, modified charter that lies in a repo other than the cwd's, whose `add -u` does not take it, so the marker names a charter left uncommitted. Repro: cwd in repo A, `--charter` a modified tracked file of repo B, `-c`: exit 0, B still dirty.
- S4, F4 (fix round, the coordinator's p3.sh): a gitignored charter never committed reads clean, so close prints no `next:` line and `checkpoint --respawn` passes. Fix: `git status --porcelain --ignored`, and treat `!!` as untracked.
- S4, F5 (fix round, the coordinator's p5.sh): a renamed charter (`git mv`): running close's `next:` line commits the new path only and leaves `D <old>` staged, so main stays dirty.
- S4, S22's verify (2026-10-12, the observer's p6.sh): the printed `git -C <dir> add -- <name>` drops the `:(literal)` pathspec that `path_state` reads with, so a charter whose name holds a glob character (`c*.md`) also adds and commits an untracked `c1.md` beside it. Fix: print `add -- ':(literal)<name>'` and the same in the commit's pathspec.
- S4, M1's fix round (the coordinator, 2026-10-12): the band's module never reads turn-ended.json, which packet M1's ruling 1 names "when present"; its line uses nothing from it. Repro: `grep -c turn-ended plugin/hooks/session.ts` reads 0.
- S4, M1's verify (2026-10-12, the observer): a session's first PostToolUse can run before its transcript holds the assistant line, so `meter.json` reads ctx 0% and the band draws `ctx 0%` until the next tool call, where `status --transcript` gives 31.1% (`meter.py`, unchanged by M1; evidence in the verify's m1ver run).

## The band could say a respawn hold (2026-10-29, packet S37; S4)
- S37 says a hold in the chain home's `held.json` (`{reason, since, session}`), and `agentik session status` prints `respawn held: <reason> since <HH:MM>`; the band prints nothing of it. The next band packet could read the same file through `chain.held_line(state, chain, session)` and show the reason beside the mark (this line takes the place of 2026-10-12's "A floor-held respawn is silent", which S37 landed).

## `admission record` on undecodable stdin (2026-10-12, the S25 fix round; S4)
- Stdin that is not UTF-8 raises UnicodeDecodeError in `sys.stdin.read()` (`cli.cmd_admission`), a traceback and exit 1, outside the 0/2/3 interface that F4 closed for OSError; a refusal (exit 2, nothing written) is the matching class. Only `session.ts` writes that stdin, always as `JSON.stringify`, so it is not reachable from the module. Fixed on branch m2-measure (M2's fix round, F2): `cli._stdin` refuses stdin that is not UTF-8 with exit 2 for both record verbs, and `admission.decode` refuses a lone surrogate (`test_f4_stdin_that_is_not_utf8_exits_2_and_writes_nothing`).

## S25's verify notes (2026-10-12, the observer; S4)
- A refused `$.clock` with a usage read that never answers leaves `agent.spawn` pending past 2 s (verify probe P7), as before the fix round: `within` races `$.clock.sleep`, so with no clock nothing bounds the read. Not reachable while the engine grants the clock.
- An undecodable ledger line makes an `end` record raise UnicodeDecodeError in `_rows` (`admission.py` ~131), exit 1 with a traceback; stdin `"x\ud83d"` (UnicodeEncodeError) and stdin nested 20000 deep (RecursionError) do the same. Each should refuse (exit 2) or retry (exit 3), nothing written; the module never sends such input. The two stdin cases are fixed on branch m2-measure (M2's fix round): both refuse with exit 2, nothing written (`test_f4_each_kind_checks_its_values_by_type_and_writes_nothing`); the ledger line in `_rows` stands.
- A ledger whose `ts` values carry no timezone never rotates. The verb always stamps UTC with an offset, so only a hand-written ledger reaches it.

## M2's verify notes (2026-10-12, the observer; S4)
- `done`'s `usage.model` is capped at 64 characters, so an ARN-like model id (a gateway's) is refused and the `done` line lost; d289279 took it. Not seen on this Mac's subscription; S26, which settles `usage`'s keys, should raise it to `NAME_CAP` or clip it as `description` is.
- A list inside `usage` (e.g. `iterations: []`) is refused; 2.1.296's types name none, so a later engine that adds one loses the `done` line until the check learns it.

## S26 fix round 1 notes (2026-10-12)
- A foreground spawn's `next` returns when its helper is done, so its `spawn` line lands after its run (and after its `done`, which `runs` then never pairs with it): its stale verdict drops after GRACE (2 min) while the helper still works. S27a, which refuses, should pair a late spawn line with its done.
- `record` still keeps a `resetsAt` that is unparseable or at datetime's end (S25's contract: refusing it would lose a `spawn` line); the reader reads it as no reading, and only `admit` refuses it.

## S26's verify notes (2026-10-12, the observer; S4)
- A stale-admitted resume whose `to` names no helper on record (a teammate's name) matches the run `runs()` makes for it, which never ends, so `wait` holds for 300 minutes (`admission.py` ~697-713; the verify's p_f2.py: `wait` from +1 to +299 min, `stale` at +301). Observe mode only records it; S27a, which acts on `wait`, should give such a run the two-minute grace F2 gave a verdict with no run.
- An `admit` answer that lands after the module's 3 s cut logs a second line (`session.ts` ~134): `admission: admit: no answer in 3000 ms`, then `admission: admit admitted (observe, peak 1)`. Drop a late answer once the cut has logged.

## S27b's notes (2026-10-12, the builder)
- The band leaves out core's own `engine` ref that `next` gives on `AbovePrompt` (M1 left it out too): if core ever draws in the band without a survey, the two lines would hide it. Keep it as a third child once 2.1.296's renderer is shown to accept a nested ref.
- band.json's figures are those of the last `record` or `admit`: the peak, the room and the helpers in flight do not age between writes (only the countdown and the `<n>s old` do). A quiet machine shows a peak as old as its last reading.

## S27b fix round 1 notes (2026-10-12, the refuter's p2 and round 1; S4)
- F3: the Python `band_line` and its `session.ts` twin disagree on band.json files the writer never makes: a `resetsAt` of `T24:00:00Z`, Feb 31, the years 0001 and 9999, `room` 1e21, `ceiling` 1e-7, NaN (the refuter's p2.py over cases.json). The writer emits none of them; if a hand-written band.json ever matters, both twins should refuse the same set.
- band.json is one file per machine, but each write uses the recording session's config (its ceiling, margin, mode and seeds), so two sessions with different settings rewrite it in turn with different figures.
- `report --since` does not filter the admission section: it prints every window the two ledgers hold.
- The fix round capped `room` at 99 (`ROOM_CAP`): past that the band reads `room for 99`, a pull forward rather than a count, and under a minute to the reset it reads no room at all.

## S27b's verify note (2026-10-12, the observer; S4)
- With half-open windows (fix round F5), a `deferred` or `wait` verdict exactly at a `resetsAt` with no window opening then falls in no window, so `report` shows it nowhere; before the fix it was held. The verify's p10.py gives `[('14:00:00', False)]`. A verdict at the reset could open the next window's row.
- The observer, check-in 107 (2026-10-13), S4, seen once: a sitting under the launcher wrote `RESPAWN` into its charter's Next act and stopped its loop, but never ran `claude-session checkpoint --respawn`, so the chain stalled with its claude idle until the owner looked. Evidence: the example-ops chain's session 25e324fe stopped at 09:28:58Z near its 80% checkpoint (309k of a 400k ceiling); its transcript holds no `checkpoint --respawn` call; `respawn/example-ops/` holds only `lock`; claude pid 76145 sat idle under launcher pid 85935. The brief and `plugin/skills/session/SKILL.md:80` both name the step. The launcher then did as designed: when that claude exited, it logged `{"kind":"stop","chain":"example-ops","reason":"no-marker","restarts":5}` at 11:58:20Z, and the owner started a new launcher by hand. A guard could close it: under a launcher, a Stop past the checkpoint zone with no respawn marked and no wakeup armed prints the one command to run.

## agentik-r1-session's notes (2026-10-13, the builder; S4)
- `plugin/hooks/session.ts`'s `runTool` falls back to the old name on a not-found rejection; no TS test drives that branch yet (the hook shim's is acceptance line 4).
- The README's install bullet names only the launcher; the next `make readme` could name the `claude-session` link and the `agentik` front door, and re-render the hand-renamed text.
- doctor's `relay` row looks for `relay` and `tmux` on PATH; once agentik-r1-relay installs `agentik-relay`, it could accept either name.
- `session.ts`'s fallback is unproven: the test harness never delivers a not-found rejection to `runTool`, so the switch proves it with one `claude plugin test`.
- c4 picks by folder, so a new `.claude/agentik/` holding only `config.local.yaml` skips the committed old `config.yaml` (doctor flags it "unread").
- The respawn match is a substring test (`agentik-session checkpoints --respawn` matches); the marker's timestamp guards it.
- doctor's relay row looks for `relay` only, not `agentik-relay`.
- (observer, 2026-10-13, S4, confirmed) `claude_session/profiles.yaml` lines 49 and 70 ship `respeak: {narrative: tech}`, a string, while respeak's provider layer wants `narrative:` as a mapping. Every `respeak-config.sh resolve` in a session prints `resolved.json#respeak: narrative is a mapping in a lower layer but str here; ignored`, and the profile's tone never reaches respeak. Fix: `respeak: {narrative: {default_mode: technical}}`, with `tests/test_resolver.py:114` updated.

## The band counts ended sessions as running (2026-10-13, the observer; S3)
- `_active` (`claude_session/admission.py`, used by `_rise` and `fit`) counts every session with a five-hour reading in the last 45 minutes as a running main thread, and never reads its `end` line. At 20:44 the band read `5h 41% → 260%` with m = 6: three of the six (`390a6ab4` ended 20:44, `51c254ff` 20:11, `14a7d80e` 20:12, each with an `end` line, `prompt_input_exit`) had left; three ran. The projected rise is a·m·T, so every respawn doubles that session's share for 45 minutes, and the fit's intervals carry the same overcount. With m = 3 the peak reads about 150%, still past the ceiling of 97, so tonight's `room for 0` stands. Fix: a session whose `end` line precedes `t` is not active at `t`; a test with a respawn pair (one ended, one started) in the window. (the observer, from the ledger's readings and end lines) Fixed on branch band-ended, 9333ff9.

## band-ended's refuter notes (2026-10-13, the adversary on 9333ff9; S4)
- F1: a `start` line after an end does not make a session running; only its next reading does, so a resumed, cleared or respawned main thread counts 0 in the band until its first reading (at most 6.9 minutes over 131 end-to-successor cases in the live ledger; the old overcount lasted 45). `decide()` is unaffected, since the requester joins through `sids`. A `start` newer than the end could count as a reading in `_active`.
- F2: `r <= e` drops a session that reads in the same second as its end line; unseen live (resumes took 16 s and 23 s).
- `fit` takes m at each interval's end, so an interval in which a session ended counts it out for the whole span and may bias a upward; not reproduced as harmful.

## band-target's notes (2026-10-14, the builder; S4)
- `plugin/skills/session/SKILL.md` (the window paragraph) and `RUNBOOK.md` (the band paragraph) still give the band line with `resets <HH:MM>` only; neither says it reads `week resets` when the seven-day reset bounds the horizon (outside the change's named files).
- The ledger's `verdict` line records `T` but not `bound` (`VERDICT_KEYS`), so a T cut short by the weekly reset reads unexplained in an audit of the ledger; adding the key changes the ledger's verdict shape (conventions §7).

## S30's notes (2026-10-14, the builder; S4)
- `rules.lifetime` reads the default from band.json, which is one file per machine. Since the fix round, `ANTHROPIC_API_KEY`, an `apiKeyHelper` or `ANTHROPIC_BASE_URL` reads unknown; a key session that shows none of them (managed settings, `--settings`) beside a subscription's sessions still reads 1h. A `rateLimits`-free session could mark itself in its resolved.json.
- Managed settings and a `--settings` file are not read, so a `promptCacheTtl` set only there is missed (the env forms are read). `models.configured` still reads `model` under the cwd and `~/.claude`, not `CLAUDE_PROJECT_DIR` and `CLAUDE_CONFIG_DIR` as `rules.lifetime` now does.
- A per-model `DISABLE_PROMPT_CACHING_<MODEL>` reads the cache off for every model (fix round F3), though Claude Code turns it off only for the model its alias names; a session on another model loses the 3300 s advice and takes the long fallback.
- The prompt line repeats the lifetime on every prompt, as the band line does (about 30 tokens each); it could show only when the lifetime changes.

## The band mixes accounts (2026-10-14, the observer; S3)
- `admission.band()` takes the newest five-hour reading across every session in the ledger, with no account key, so two logins on one Mac share one band. On 2026-10-14 the ledger held two accounts at once: one with its five-hour reset at 21:10Z and seven-day 81% (session 1454f1c7, 17:05Z), the other with 22:30Z and 3% (four sessions to 18:01Z); each session's prompt line showed whichever wrote last, and the projection and `room` were fitted across both. The statusline gives no account id, but the pair of reset times fingerprints one; key readings by it and have each session read its own band.

## A chain started with no first prompt restarts idle (2026-10-14, the observer; S3)
- `agentik session run` takes claude's arguments after `--` and sends them the same at every start, and accepts none at all. A consumer repo's orient chain was started with no first prompt after `--`, so its 14:40 restart opened an empty session that waited for a person (orient charter 2026-10-14-7, act 0: "`agentik session run` carried no first prompt after `--`, so the restart had none to send"). An unattended respawn then stalls until someone types. Candidates: `run` warns at start, and `doctor` flags a chain, when no positional prompt follows `--`; or the restart sends a default resume line naming the charter.

## S31's review (2026-10-14, the observer; S4)
- An empty or blank first prompt (`--model opus ''`, `'   '`) gives no warning, though it likely starts idle; unchecked how claude treats an empty prompt.
- With the prompt before an option (`'/loop 3h go' --model opus`), the long-`/loop` warning is missed: `long_loop` reads only the last argument (the RUNBOOK's form), while `prompt_gap` finds the first prompt anywhere.
- S4 (the observer, 2026-10-14, seen live): the `not-started` and `deferred` texts name the five-hour window's present percentage and reset, not the projected peak and the ceiling that held the spawn, so a relay night's `band` line read "the five-hour window is at 65%, resets 20:30" beside peak 96.96: a reader sees room at 65% and cannot tell why the row waits. The text could add "projected <peak>% past the <ceiling>% ceiling" (s26-admit ruling 4's figures).

## S32's review (2026-10-15, the observer; S4)
- `row_life` counts a row that ends at its own start as 0.0 minutes, so rows killed at once pull L_row toward 0 (the adversary; no such row in the ledger today). A floor (FLOOR, 5) or skipping zero-length rows would hold it.
- An end line whose `session` is a list crashes `ends()` with a TypeError (exit 1, read by the relay as `unchecked`, which spawns); true at 6e97555 too, and `record` validates the session, so no normal write reaches it.
- Live, 2026-10-15 02:30:41: po2c's first ask under the install read peak 133.84 (P 34), against 200.49 a minute before; still held, the window at 34% an hour in.

## S33's notes (2026-10-15, the builder; S4)
- `design/overhaul-r1.md` (§ the exit, and its proof table) still says the meter prints at most 400 bytes; `MAX_OUT` is 640 since S33, as the line under a launcher names the charter path twice.
- Under a launcher at or past 100%, the EXIT rule leaves room for an absolute charter path of about 110 characters; a worktree's charter is near that and falls to the relative spelling, which runs only from the sitting's cwd.
- The line names only the charter `charter open` recorded, absolute and inside `[A-Za-z0-9_./-]`, under the payload's cwd: a sitting that writes its charter by hand, works in a repo whose path holds a space, or whose cwd moved to a subdirectory gets `<this sitting's charter>`.
- A second `charter open` in one sitting moves the record to the newer file; `charter close` leaves it.

## `charter open` under a chain (2026-10-15, the observer; S4, seen live)
- `charter open` names its file `<date>-<n>.md`, or `<date>-<n>-<row>.md` only under `$RELAY_ROW` (`charter.py` `open`), so a chain's sitting started by `agentik session run` (`CLAUDE_SESSION_CHAIN` set) gets no chain suffix; each long loop names its charters `<date>-<n>-<chain>.md` and its start line reads the newest of those, so every such sitting renames the file by hand, and one that forgets is never found by its successor. Candidate: take the suffix from `$CLAUDE_SESSION_CHAIN` when no row names one. Every long loop seen works around it today with `RELAY_ROW=<chain> agentik session charter open` (the orient and platform chains' transcripts), so the fix retires a workaround rather than an outage.
- S33's record skips a sitting started in a parent directory whose charters live in a child repo (cwd `<root>`, charters in `<root>/<repo>/history/sittings`), since `_record_charter` wants the file's dir to be exactly `<cwd>/<charter dir>`; such a sitting's CHECKPOINT line always names the placeholder. Harmless where its brief names `checkpoint --respawn --charter` in full.

## A chain's sitting stalls on its model's limit (2026-10-16, the observer; S3, seen live; answered by S34)
- A consumer repo's orient chain (launcher-run, model Fable) hit "You've reached your Fable limit. Run /usage-credits to continue or switch models with /model." at 08:07:21Z, again at 08:22, 08:24 and 08:45 as its `/loop` wakes retried, and then took no turn: the claude stays up at its prompt, so `run` sees no exit and no respawn mark, and the chain (and the relay nights it starts) stalls until the owner's hand. The message names no reset, and the band reads only the five-hour and seven-day windows, so the meter shows nothing either. Candidates: the Stop hook or the meter reads a limit message as the turn's last text and prints one line naming `/model` (entry 17 allows an orchestrator on Opus at the 1M window); or `run` restarts the sitting on a fallback model the chain's config names. Which is the owner's (UX). Seen again 2026-10-16 in a second consumer repo's umbrella chain (launcher pid 82962, launched `--model fable`): the respawns at 13:48Z and 14:13Z each opened on the limit message and waited for the owner's `/model` (14:24Z, "Set model to Opus 5.5 and saved as your default"); the launcher's explicit `--model fable` overrides that saved default, so every respawn stalls again. Put to the owner as OPEN-QUESTIONS 7.
- Answered by S34 (OPEN-QUESTIONS 7, the owner's word of 2026-10-16): a respawn keeps the model the sitting ended on (its `meter.json`) and the launcher says so in one line; the StopFailure hook writes `limited.json`, and the band's session line names `/model` while a rate limit ended the last turn. A sitting that stalls on its limit still needs the owner's `/model`: the band now says so.

## S35's notes (2026-10-16, the builder; S4)

- At a login's weekly reset its key (the seven-day `resetsAt`) moves, so for up to 29 hours the ledger holds two keys for one login: the per-account split is on, the new week's fit starts from the seeds until 20 intervals accrue, and a session that has not read since the reset draws the old key's band (`5h no reading` once that window passes) until its next reading. Merging a key with its successor a week on would keep the fit's history.
- The relay's band pacing reads band.json's top level, every line, so two logins still share one pace there; reading `accounts` is that repo's row.
- The key assumes the statusline's seven-day `resetsAt` holds still to the minute for a week. If it drifted, each drift would read as a new login and the fit would stay seeded. Not seen; a look at the live ledger's seven-day values would settle it, which this builder may not read.

## sync-vc1's refuter round (2026-10-17, the refuter): PASS, one note

- S4: `make plugin-version-check` is not a goal doclint accepts in an acceptance line: it is not in doclint's `MAKE_TARGETED`, so doclint refuses it as a whole-suite run, and doclint stays byte-identical across the repos, so this repo cannot add it. Until commons' doclint admits the goal, a later packet writes `.venv/bin/python scripts/plugin-version-check` there. The round's F1 (`.PHONY` names the goal) and F2 (`check-unlocked`'s help text names it after `hygiene`) rode in the commit that wrote this note, sync-vc1's Amendment 3.

## README line 135 lost its commit clause to the source ceiling (2026-10-22, S36; S4)
- `design/readme/source.md` sat 5 bytes under `SOURCE_CEILING` (16384) and S36's ruling 5 adds 53 to line 113, so line 135 now reads only "on a missing line or a `WAITING <n>: <what>; <how to tell>` misshapen or at `waiting`" and line 113 "on in every shipped profile" (was "both on in"); source.md is 16381. Restoring "wake at the idle limit, commit the charter" there needs a trim elsewhere in source.md or a higher ceiling; RUNBOOK §4 and SKILL.md carry the whole rule.

## S36's adversary round 1 (2026-10-22, the adversary; S4): PASS, two notes
- F1: the packet's grep acceptance line uses `\|` under `-E`; ugrep and BSD grep both read it as a literal pipe, so the line reads 0 on dce04b9 too. With a bare `|` it reads 10 before and 0 after. No test reads SKILL.md, RUNBOOK.md or README.md for "never stops the loop": a docs test should.
- F2: `claude_session/rules.py:75`, `PACE` item 4, says "the longest idle wait the cache allows (item 6)"; on a 5m or off cache item 6 gives the long fallback (1800 s or more), not `WARM`'s 270 s, so item 4 should name the long fallback there. The code follows ruling 1; the gap is the ruling's.

## The README source gave eight passages to the gate queue's section (2026-10-29, S38; S4)
- `design/readme/source.md` sat 2 bytes under `SOURCE_CEILING` (16384) and S38's ruling 5 adds the gate rows and "The gate queue" (about 800 bytes), so eight passages were tightened or cut in both files to land at 16354: the targeted-tests line, `make check`'s freshness clause, the legacy-roles note, the Stop and stamp sentences of the RESPAWN close, the record-tool hint, `run`'s start-line and Ctrl-C sentences, and the Rulings row; the next README render or a ceiling raise may restore them (packet S38).

## S38's refuter round 1: windows not reproduced (2026-10-29, the refuter; S4)
- Packet S38's runner has five unreproduced windows, no code for them yet: a runner dying between `popen` and the `runner.json` write runs its entry twice; dying after `result.json` but before the inbox write and ntfy drops the message; `_recover` kills the recorded pgid even when a result exists (pid reuse); `inbox/read/` is never pruned; `runner.log` is 0644.

## doclint's docstring still says five parts (2026-10-30, packet S40's refuter round 1; S4)
- `scripts/doclint:5` says "five-part shape", but since packet S40 the charter has six parts (`## While waiting`, optional before alpha.24); doclint is outside S40's may touch, so no code was changed.

## S41's leftovers (2026-10-30, packet S41's builder and refuter round 2; S4)
- The band's width: with the model and window at the head, the line with both windows, `respawn marked` and the age is 82 to 93 characters, so an 80-column band loses the age and under 65 columns the zone is cut (the limit-note line is 119). Lead: drop the model part first, or put it after the zone, when the line overflows bodyColumns (`session.ts` bandLine, `mod.py` facts).
- The band and `status` never check measure.json's `at`, so `(engine 1M)` can come from an old measure, from before a /model switch, or from a resumed session's old one. Lead: leave out the engine part past the meter's STALE_S, or show its age.
- The twins disagree on windows of 1e24 or more: `windowLabel(1e24)` gives `1e+21k`, `mod.window_label(1e24)` gives `1000000000000000000000k`, and WINDOW_CASES pins only 1e400. Lead: no part from 1e21 up, in both twins.
- Ruling 4's `model: none` is never reached from a real meter: `mod.model_line({"model":None,"window":None,"window_source":"default"},None)` returns `window from default`, and the meter always writes `window_source`; the test reaches `none` only with `window_source` None.
- Control characters in a model id pass into the band and `status`: `modelName("claude-opus-5-5\n")` keeps the newline, and `models.family` accepts such an id. The id comes from the API, so this is unlikely.
- `plugin/commands/status.md` still describes one line ("The line above is this session's meter") and says nothing of the `model:` line.

## S45's leftovers (2026-10-30, packet S45; S4)
- `ceilings_source` is left alone by `resolver.rewindow` (design/window-r1.md R4). Only `hooks.session_start` reads it, from its fresh resolve, never from the file; it can be wrong in the file only if a layer gives the two classes different turns and a launch cap falls between them. Lead: move it with the other four when a consumer reads it from the file.
- No clamp on a ceiling above a small measured window (design/window-r1.md §5): a local model behind the router reading 32000 gets `window: 32000` and the 200k class's 180k, so the ceiling never trips, today as after. Lead: `min(ceiling, window)` in `meter._limits` and `resolver`, if a local sitting ever needs it.
- `scripts/p1-proof` no longer runs from a checkout: it reads `.claude-plugin/marketplace.json` at import, and the marketplace line lives in commons now (FileNotFoundError, seen 2026-10-30 when `scripts/window-proof` first loaded it). Outside S45's may touch. Lead: name the marketplace as a constant, as `scripts/window-proof` does.
- `scripts/window-proof` has no `--tty` path, which the record's L1 named for a `-p` child that writes no measure; on 2.1.314 a `-p` child wrote one, so it was not needed.

## S45's refuter round 1, left (2026-10-30, packet S45 Amendment 2; S4)
- A holder stalled past the 2 s lock bound can still undo a `set`: it loaded before the `set` wrote and writes after it (the window moves, the posture returns). The per-process temp name ends the tear, not this. Reproduced with a 3 s stall in `rewindow`. Lead: a re-load under a second lock pass, or `set`'s retry after the bound.
- The SessionStart clause (`the engine's first reading replaces this`) promises a reading that never comes with no hooks module. Lead: say it only when the module was seen last time, or drop the promise's tense.
- `resolved.json` with no `windows` block stays at `200k (engine 1M)` until a SessionStart, since `meter._limits` needs `windows` and `rewindow` finds no class. RUNBOOK says so; SKILL.md's band line and the comment in `session.ts` still say the next tool closes it, left since a file under `plugin/` would bump the version.
- `set` from a shell with no helper mark, using a helper's session id, re-resolves without the mark and widens that helper's `windows["1m"]`. Lead: keep the helper mark in `request.json`.
- A helper under a layer's plain `ceilings` holds what the layer says: `ceilings: {context: 400000}` gave a helper 400000 on both classes, on main at a633d57 before this packet, and still. R2's clause covers `ceilings_1m` only. Lead: decide whether a helper's 180k outranks a project layer.
- A plain `builder` or `frontier` under a project `ceilings_1m` rises to 400k on bare Opus at the first 1M reading. The layer's own comment owns it, and the record's §5 says so; noted so a later reader does not take it for a bug.
- Unseen live, so a later reader knows: no L1 or L2 ran on Opus (both on Haiku), and no live change of value within one session has been observed. The links are proved offline (A1, A2, A13).

## S45's refuter round 2 (2026-10-30; S4)
- `hooks.py:461-463`: a share alternating across `checkpoint_at` now speaks at every crossing, against the README's "then every tenth tool". 143800/144200 for 40 tools through `post_tool_use` spoke 20 times where main's rule speaks at 0 and 20. Replaying 700 real transcripts found no such case (657 passes over 80%, 2 down-crossings, 0 gaps under ten tools). Lead: clear the latch but keep a ten-tool floor since the last speech.
- `tests/test_window.py`, the stale-twin test: four mutants survive (`heal-writes-both`, `rewound-window-only`, `heal-returns-false`, `signal-clear-keeps-count`), since "it is not rewritten" compares bytes. Lead: compare the JSON's mtime and add a twin stale only on `ceilings`.
- `resolver.py:570-572`: a value that does not round-trip through the YAML rewrites the YAML on every measure (a hand-written `ceilings.context` of 1e21: four `rewindow` calls each moved the YAML); U+2028 and U+0085 make the load fail outright. Not reached through a layer. Lead: have `dump` quote those values.
- A measure that moves an older session's window makes it `resolver.newest_session`.
- `meter.py:248` keeps a fixed temp name.
- README:83 "ctx % at its next measure" is loose: ctx % moves at the next tool; resolved.json moves at the measure.
- Unseen live: a change of window within one session, and a non-1M reading on Opus.

## S44's refuter round 2 (2026-10-30; S4)
- A constant band's `until` is null, so a schedule that never changes shows no band in the line, `status` or the relay's plan. Decide whether a constant band shows.
- `doctor` warns on a Max login too when the user's bands file is bad: every other Max output is byte-identical, and the ruling asks for it.
- `admission.py:298-299`, `_rows` lets RecursionError out on a ledger line nested past the stack; `read_band`'s shape on the ledger. A hook path was not traced.
- `demand.py:153`, `_shift`'s 1-second stop is unpinned: a mutant at 120 seconds passes. Pin a mid-gap stamp and a cut at the second pass's last minute.
- `--`, `2026-10-30` and `1e3` bind as band names; `Good` binds and `next` never names it.

## S47's leftovers (2026-10-30, packet S47; S4)

- `plugin/commands/gate.md` says "the running gate" and one at a time; a plugin edit needs a version step, so it waits for the next that moves `plugin/`. Reword it to one per repo under a load ceiling. `cli.py`'s help, one string, moved with Amendment 1.
- `notify`'s POST holds the runner's loop up to its 5 s timeout, against the letter of ruling 5, so another child's wall cut can land 5 s late. Post from a thread if a late cut ever matters.
- A hand-written entry with no `repo` or `command` raises in `_start`, as in S38's `_run`; the respawned runner then kills the running set each time. Close such an entry with 127.
- `_recover` kills a dead runner's groups in turn, a grace each, up to 15 s at three. Signal them together if a cold start ever feels it.
- A crash after the result and before the inbox loses the inbox line, though the result stays readable (same on main).
- `start_settle` with a clock set back an hour waits that hour while something runs.
- A corrupt runner.json with a live child double-runs (same on main).
- A stale pgid after a reboot could hit another group, by reading only.
- A crash after the spawn and before the second runner.json write leaves the child running, unnamed: its entry closes 125 and never runs twice, but its key frees under it. Amendment 1 narrows the double run to this.
- A finish's SIGKILL follows the reap, so an empty group's id could in that instant be another's; pids run in sequence, so a wrap would have to land between two lines.
- With git failing in a subdirectory of a repo, `<repo>/.git` is absent and the entry keys on the subdirectory itself, apart from its siblings until git answers again.
- A finish kills a deliberate same-group helper with no log line, and a `setsid` helper survives it.
- A 61fd2ad-form string key beside a new key does not hold; unreachable, since that form was never merged.
- With git hung, `main/sub` keys apart from `main`.
- A lock's `..` through a symlink collapses lexically.
- The pid is free between `poll` and `killpg` on an empty group, needing a pid wrap between adjacent lines.

## S49's notes (2026-10-31, the builder; S4)

- A lead, not confirmed: Claude Code's own per-hook timing may be readable from a debug log or a transcript, which would cover every plugin's hooks, not this one's alone. Not built; S49 read neither.
- The shim's cost is its one `date` fork, 2.9 ms a call. Sampling by `$$` would cut it, at the price of `count`. Worth it only if the numbers say so.
- A row has no time or session, by the packet, so `--since` cannot filter it and the owner's "per session" is not answerable from it. A session's own row would need a key the packet ruled out.
- A `~` in XDG_STATE_HOME: `config.state_dir` expands it and a shell would not, so a tool that reads the variable by shell lands elsewhere. Amendment 1's row goes through `config`, which closes that split here (the first form's shim did not expand it); `scripts/p1-proof` and `scripts/window-proof` still read it by shell, proof scripts both. Read, not reproduced past the first form.
- Amendment 1 says what `ms` leaves out, and a row written in the milliseconds of teardown before a kill reads the code it would have exited with. Absent would need a write after teardown, which only the shim can do, and the shim stopped being able to on the refuter's F1.

## The band's loop and a refused clock (2026-10-30 and 2026-10-31, packets S41 and S49; S4; answered by S50)
- The band's 5 s loop (`session.ts`, about line 343) has no catch around `$.clock.sleep`, so a refused clock is an unhandled rejection. Lead: `try { await $.clock.sleep(EVERY_MS) } catch { return }`.
- `session.test.ts`'s clock race, seen once at load 80: `no implementation for clock.sleep`, session.ts:397, the band's loop, on a tree that passed unchanged 3 min later. Reading only, not S49's; the line about the 5 s loop's missing catch, above, is its lead.
- Answered by S50: a refused `clock.sleep` ends the loop, silently; a refused `ui.invalidate` waits for the next tick. The race itself is gone: at load 8 to 26 the unchanged suite failed its file with 11 to 67 of those lines, and the changed loop shows none. This engine drops a refused redraw rather than rejecting, so S50's redraw test passes on either loop; its clock test carries the red.

## S49's refuter, round 2 (2026-10-31, S4)
- `harness.py:92` `record_hook`'s flush moves the exit when stdout is a failing regular file, 4097 to 8178+ bytes: main rc 120 against new rc 0; a block only if Claude Code's hook stdout is a regular file, unread.
- `harness.py:136`: a lone-surrogate event crashes `report --hooks`.
- `measure.stated_limits`: RecursionError.
- A directory at `hooks.jsonl.1` stops rotation.
