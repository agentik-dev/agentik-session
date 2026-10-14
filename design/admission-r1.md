# claude-code-session: admission for helper spawns (admission r1)

**Status:** design r1, 2026-10-10, docs only. Its one refuter round gave BLOCK at 1fa12a2: one block and fifteen notes. This revision folds B1 in §3.3, §3.4 and §3.7, all eight §7 answers, and notes 2, 3, 6, 10, 11, 13 and 14. The other notes are in §6. Inputs: the owner's ask of 2026-10-10; the prior observer's sketch (taken as unverified); the Mods reference (as of v2.1.290) and its types file (written by 2.1.277; this Mac runs 2.1.296); the status line, settings, interactive-mode, errors, model-config and subagent docs; overhaul-r1 §1.2 (D6) and §2.2; respawn-r1 §3.1 (the chain); `hooks.py` at b43a445.

The one-sentence design: a thin Mod hands each helper spawn, with the engine's five-hour reading, to a pure `claude-session admit`, which admits it only when the window's projected peak before its reset stays under a ceiling; a refused spawn is deferred in a ledger that outlives the session, a sitting of the same chain is woken when it fits, and a band shows the window and the room left.

## §1 The problem

The owner's ask: a burst of helpers must not fail at the usage limit, and at least 90% of each five-hour window is used.

A sitting spawns up to eight helpers. Helpers "count toward the same usage limits as your main conversation" (subagents doc). At the limit a background helper "is marked failed", and its work is re-sent. The relay's `claude -p` children stop, and a `-p` run is offered no wait. `autoContinueAtUsageLimit` (default `true`) resumes only an open interactive session, and "re-arms the wait on its own at most twice in a row". Fable has its own limit: past it, Fable "uses usage credits", and in `-p` "Claude Code bills it without asking". So a burst that crosses 100% wastes work, and an idle stretch after a reset wastes window.

This does not reopen D6. D6 retired the status line as a sensor (it sampled only on renders) and the window as the sitting's budget. Here the engine pushes the reading to a hook, and the window gates only spawns. The sitting's budget stays the meter's.

## §2 The decision

1. Admission sits at `agent.spawn`, in a Mod. The policy lives in the Python tool, pure and tested by pytest. The Mod is glue: it reads, forwards, draws and wakes.
2. One ledger per machine: `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/admission/ledger.jsonl`. `admit` reads it, decides and appends inside one `flock`, waiting at most 2 s. It rotates at 24 hours plus one window.
3. A spawn is refused on its projected peak, never on pace. A five-hour refusal is deferred. A seven-day refusal is not.
4. It ships in `observe` mode (records and draws, never refuses). `enforce` follows P1 to P3. `-p` sessions stay in `observe` until agent-relay checks rows itself.
5. The sitting's PreToolUse spawn gate stays as it is.

## §3 The seam

### §3.1 What the Mod reads

- `session.measure`: `e.rateLimits`, each `{kind, percentUsed, resetsAt}`, forwarded to `claude-session admission record` when `e.changed` holds `rateLimits`.
- `agent.spawn`: `subagentType`, `model`, `parentModel`, `background`, `fork`, `description`, `tool_use_id`, plus `$.session.usage()` and `$.session.id()`. They go to `claude-session admit`, and the Mod returns `{deny}` or `next(e)`.
- `tool.call` on SendMessage: a resume skips `agent.spawn`, so it goes through the same `admit`.
- `turn.complete` with `agentId`: the helper is done, with its `durationMs` and `usage`.
- `session.start`: `isInteractive`, and `CLAUDE_SESSION_CHAIN` from the environment. `session.end`: the tool marks the session's admitted helpers done.

Every call is `$.process.run(argv, {stdin, timeoutMs: 5000})`. Its wait does not count against a hook's 10-second limit.

### §3.2 How a spawn's burn is projected

The rate model needs no token weights, since the plan's weights are not published.

- r: the window's burn in points a minute, over 10-minute intervals of readings.
- n_f: helpers of model family f in flight in each interval.
- Fit r = a + Σ b_f·n_f by least squares. a is fit over the last 45 minutes, with one term per active main thread: one with a reading in the last 45 minutes and no end line since its newest reading (the observer, 2026-10-13; a respawn's ended sitting no longer counts). Until 20 intervals exist, P3's seeds stand in.
- L_t: the median life of a helper of type t. A fork is its own type. An entry older than its type's 95th-percentile life ages out.
- T: minutes to `resetsAt`. P: the newest five-hour `percentUsed` whose `resetsAt` is still ahead. When the newest seven-day `resetsAt` is ahead and comes before the five-hour one (within 60 s it is the same moment), T runs to it instead and the band names it (`week resets`), since weekly allowance left at its reset is lost (the owner, 2026-10-14 06:43).
- peak = P + a·T + Σ (running) b_f·min(T, max(L_t − age, 5)) + b_f·min(T, L_t) (the new spawn).

### §3.3 Admitted, deferred or denied

- **Admitted** when peak + margin ≤ ceiling. In `observe`, 97 and 3. In `enforce`, the margin is a function of T, fit by P3.
- **Deferred** (interactive) when the five-hour peak crosses. The model reads, as the Agent tool's error: `admission: not started. The five-hour window is at 88% and resets at 14:05. This spawn projects 7 points, past the ceiling. Do not retry now. It is deferred: a sitting in this chain is woken when it fits, by 14:06 at the latest. Work in this thread is fine.`
- **In `-p`** (once enforced), with no wake promised: `admission: not started. The five-hour window is at 88% and resets at 14:05. Continue in this thread.`
- **Denied** when the seven-day reading crosses its own ceiling: `admission: not started. The seven-day window is at 96% and resets Mon 00:00. Spawn nothing more; checkpoint and leave the next step to the owner.`
- **No reading** (off a subscription, or none yet): admitted, recorded `unread`.
- **A stale reading** (its `resetsAt` passed): one spawn at a time across the machine until a fresh reading lands. The others read `admission: not started. The window has no fresh reading yet; retry in a minute.`
- **The hook fails** (a lock wait, a timeout): a `.catch` calls `next(e)` and records `unchecked`, and the band shows it.

### §3.4 The wake

The deferred list lives in the ledger, keyed by the chain (`CLAUDE_SESSION_CHAIN`), or else by the repo root. A respawned sitting is a new session, so each interactive session re-arms at `session.start` for its key. It polls with `$.clock.every(60 s)`. A deferral ends when the projection admits its first entry or the reset passes. Then the Mod calls `$.prompt.submit` once, which "waits until the session is idle". The text lists each deferred spawn (description, type, model) and each failed helper's id, to resume with SendMessage. Past 80% on the meter, it asks for the list to go into the charter's Next act, not for new spawns (entry 17).

### §3.5 The band

The band is one line in `AbovePrompt`, cut to `bodyColumns`. It yields while `hasSurvey` is true and keeps other mods' lines. For example: `5h 72% → 91% · ceiling 97 · resets 14:05 (1h12) · 3 helpers, room for 2 · 1 deferred · 7d 41%`. The prompt hook adds the same line to the budget context.

### §3.6 Using 90% without crossing 100

The target is a floor on use, and the ceiling is a cap. A spawn is refused only at the cap. A deferral ends as soon as it fits. "Room for N" tells the orchestrator to pull work forward. `report` prints each window's last reading as `held` (spawns waited) or `idle` (nothing waited). The Mod cannot make work, so an idle window under 90 is reported, never hidden.

### §3.7 What it never does

It never spawns, changes a model, buys credits, or writes outside its state dir. It never raises entry 17's eight helpers, a doctrine with no counter in code. The Mod loads in every relay child, since the relay passes no flag to turn plugins off. There it records and never refuses until agent-relay checks rows itself, and it never wakes.

## §4 The proof

Verified against the docs:

- `session.measure` fires "after each main-thread turn, and when a rate-limit window moves a whole point". Its `rateLimits` is "empty off a subscription or before the first reading".
- `$.session.usage()` "returns `{ startedAt, context, rateLimits, cost }`". `kind` is "`five_hour`, `seven_day`, or a Claude gateway's `spend_limit`". `percentUsed` runs "0 to 100 with at most one decimal". `resetsAt` is optional, "an ISO 8601 timestamp". "The plain call costs nothing."
- `agent.spawn` returns "`next({ ...e, model })` to choose its model, or `{ deny: reason }`". On a refusal, "nothing starts; the model sees the text as the Agent tool's error". A SendMessage resume does not fire it.
- `AbovePrompt` has `hasSurvey` and `bodyColumns`, and "every mod shares it".
- The status line's `rate_limits.five_hour` runs "from 0 to 100", `resets_at` in "Unix epoch seconds", "after the first API response".
- `$.store`: "A `get` followed by a `set` isn't atomic", hence the ledger. A resumed helper "that had already failed or completed shows as running again".

Unverified, so each is a proof step:

| # | claim | how |
|---|---|---|
| P1 | a helper's responses move the reading (the docs say "the last API response") | observe mode: a sitting idle on three background helpers |
| P2 | `agent.spawn` fires for Workflow agents and forks | observe mode: one of each |
| P3 | the rate model holds, scored at spawn instants by T bucket | one day of observe mode: seeds, margin by T |
| P4 | the engine drops a reading past `resetsAt` | `usage()` after an idle reset |
| P5 | a helper failed at the limit resumes after the reset | one throwaway helper at a limit |
| P6 | a Mod can see the Fable limit (not a documented `kind`; its reset undocumented) | the transcript rows at a Fable limit |

Waiting on their proofs, asked of the owner only then: **a brake** (stop the youngest background helper when running work alone projects past 99%, resume it after the reset) waits on P3 and P5, and until then failed helpers are listed in the wake; **the Fable limit** waits on P6, with the likely answer to refuse Fable spawns and never bill credits. The common case is a helper that inherits Fable through `parentModel`.

## §5 The cut into packets

Each is one sitting with a red test first.

- **S25 observe.** `plugin/hooks/admission.mjs`, `modules` in `hooks.json`, the `admission record` verb, the session-end sweep. It regenerates the types on 2.1.296 and measures the frozen tool's start-up time. Red: `tests/test_admission.py::test_record_appends_one_line`. Its `.test.ts` uses stubs under `claude plugin test`, which runs no model, and `make check` gains that line. Built (2.0.0a10): 2.1.296 loads one hooks module per plugin, one unmatched hook per event, and follows `$` into no imported function, so the six hooks live in `plugin/hooks/session.ts` under their own heading, sharing its `session.start` and `turn.complete` with the band, and `modules` stays `["./session.ts"]`; `plugin/hooks/admission.test.ts` tests them as installed, and `make check` already runs that line (M1).
- **S26 admit.** `claude_session/admission.py` (fit, peak, verdict, texts), the `admit` verb, the one lock, and `session.admission` keys `{mode, ceiling, margin, seeds}`. Red: one test per rule in §3.3, and the peak against a synthetic day. Built (2.0.0a12, observe only): `fit`, `project`, `decide` and `texts` in `admission.py`, `admission admit` appending one `verdict` line inside the one lock, `session.admission` `{mode, ceiling, margin, seeds, ceiling_7d}` read by `rules.admission` with defaults (`enforce` read as `observe`), and the module's call before `next` on a spawn and a SendMessage resume, its answer one debug line.
- **S27a enforce.** The refusal, the SendMessage gate, the ledger's deferred list and the wake. Red: each text pinned, a wake re-armed at `session.start`, none in `-p`.
- **S27b show.** The band, the prompt line, and `report`'s window use. Red: the band's line pinned at 80 columns. Built (2.0.0a13): `band()` in `admission.py` (P and the peak with no new spawn, the helpers in flight, the room for the parent's family, the held verdicts since the window's start, the seven-day reading) rewrites `admission/band.json` at every `record` and `admit`, inside the lock; `band_line` and its twin in `session.ts` draw one fixture's same text; the band draws it as a second line under the session's, yields while `hasSurvey` and keeps another mod's tree; the prompt hook adds it after the budget line; `report` prints each five-hour window `held` or `idle`, `under 90` marked.
- **Owed to agent-relay:** a row check through `claude-session admit --row`.

## §6 Open risks

- Use off this machine shows up only in a, so the fit is cautious after it.
- A burst before the first reading of a fresh window runs unprojected.
- The median undercounts a helper's long tail; the mean life left at its age is better (note 4).
- If P2 fails, Workflow goes ungated; the fallback is a `tool.call` gate on Workflow (note 7).
- `agent.spawn`'s model is unresolved, so the family comes from `parentModel` and the agent's definition, and the resolved model is recorded (note 8).
- `turn.complete` names no error kind; a helper that ends in error at a reading of 99 or more counts as failed at the limit (note 9).
- Conventions §1 and §4 name no Mod or `.test.ts`; M1 (packet m1-band) made the amendment (note 12).
- A `$.clock` poll may run late across a Mac sleep.
- Note 15 is §8's third question.

## §7 Choices for the refuter

The round answered all eight, and each answer is folded: the fit over recent use (§3.2), the bounded lock and fail open (§2, §3.3), stale readings and the margin by T (§3.3), the polled wake (§3.4), `-p` in observe (§2), and the start-up time (S25).

## §8 Choices for the owner

These are also questions 2 to 4 in `OPEN-QUESTIONS.md`.

- **The weekly allowance.** (a, recommended) While the week is being used faster than an even pace, plus 5 points, the five-hour ceiling drops to 90, so a heavy day cannot spend the week. (b) Always aim for 90% of every five-hour window. (c) Ignore the week.
- **The shape.** (a, recommended) A small Mod in JavaScript, with the rules in the Python tool. It also loads in every relay child, where it only records. (b) No Mod: the spawn gate reads a figure the status line writes, the sensor retired in September.
- **Who yields.** (a, recommended) The sitting waits. While a night runs, the sitting's helpers leave room for the running row, because a row that hits the limit stops the night and is re-cut. (b) The night waits: the relay starts a row only when there is room. (c) Whoever asks first.
