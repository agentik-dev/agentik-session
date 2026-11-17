# Decisions for the owner

## Open

None.

## Answered

- 7. When you switch a launcher-run sitting's model with `/model`, should its respawns keep that model: Yes, and warn about it. Next: packet S34: the launcher passes the model the sitting ended on to its successor and says so in one line and in the restart's ledger entry; the band names `/model` when a rate limit ends a turn (StopFailure). The portfolio ledger's entry 17 ("the same start line") is amended in its own repo. (2026-10-16; the owner's word in the observer session, 10:58, in their words: "yes it should keep the model I switched to but we should warn about it")
- 6. Should the band's projection of a fresh relay row change: Yes, fix it. A row's new session is charged as a main thread over the whole window (a·T) and again as a spawn, so night 2026-10-14-7 held us3bfix 53 minutes at 2-7% used (peak 174 to 186) in a window that closed near 60%, and night 2026-10-15-1 held po2c at 0% used, peak 141, a minute after the reset. Next: a design note amending admission-r1 §3.2, one refuter round, then a packet. (2026-10-15; the owner's word in the observer session, 01:2x, which also kept answer 2 when shown the week at 31% after 10% of it)
- 5. When the weekly limit resets before the five-hour window does, by when should the five-hour window be filled: By the weekly reset, since weekly allowance left at its reset is lost. Next: the band's horizon is the earlier of the two resets (branch band-target); the relay paces its spawns by the band (agentik-relay design band-pacing-r1). (2026-10-14; the owner's word in the observer session, 06:43, in their words: "fill the 5 hour window by 8am … because that is when my weekly limit resets")
- 2. Should the weekly allowance hold back the five-hour target: The five-hour target first; helpers run to 97% of every window whatever the week shows, since the owner moves to a second account when the week runs out. Next: the admission design drops the weekly hold-back and keeps only the refusal near the weekly limit. (2026-10-12; the owner's word in the observer session, 2026-10-12, entered 03:18)
- 3. Should the plugin gain a small JavaScript mod: Small mod, Python rules. Next: the admission meter's packet builds the thin mod. (2026-10-12; the owner's word in the observer session, 2026-10-12, entered 03:18)
- 4. When a night and a sitting want the same room, which one waits: Neither; nights and sittings are the same kind of long-running session that the owner checks on now and then, so nothing is set aside and whoever starts first takes the room. Next: the admission design drops the night/sitting split. (2026-10-12; the owner's word in the observer session, 2026-10-12, entered 03:18, in their words: "we have too much focus on night/day times")
- 1. Should a sitting that reaches its checkpoint start its own successor: The successor starts itself. Next: a design record with one refuter round, then a packet; the portfolio ledger's entry 17 is amended in its own repo. (2026-10-10; the owner's word in the observer session, 2026-10-10 15:37)
- 8. checkpoint --commit takes named paths only: Take it (2026-11-17; the owner's answer to hq's decision 40 on 2026-11-12, moved here by the owner's answer to hq's decision 43)
- 9. set --save for a setting that is not a model tier: Take it (2026-11-17; the owner's answer to hq's decision 41 on 2026-11-12, moved here by the owner's answer to hq's decision 43)
- 10. A machine with no user file runs the starter profile: Take it (2026-11-17; the owner's answer to hq's decision 52 on 2026-11-17)
- 11. Three shell spellings are refused in every session: Take it (2026-11-17; the owner's answer to hq's decision 53 on 2026-11-17)
- 12. A declared watcher that is not running is said at session start: Take it (2026-11-17; the owner's answer to hq's decision 55 on 2026-11-17)
