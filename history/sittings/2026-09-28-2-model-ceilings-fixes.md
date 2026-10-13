# Sitting 2026-09-28-2: claude-code-session, model-ceilings fix round

| item | value |
|---|---|
| goal | fix F1 (a helper inherits the orchestrator's role and its 400k on 1M) with a test that fails first; list the non-blocking findings (no NICE_TO_HAVE.md here); `make check` 0 |
| budget | 180k context, 400 turns (the cross-repo ledger's entry 12); land the act in flight at 80%; commit per act; never push, amend, rebase, a device, the network |
| pin | model-ceilings 1e9b493, worktree `model-ceilings` |
| window | 200k |
| agents | 0 (a helper of hand-run sitting 2026-09-28-6) |

## Done-ness
- [x] act 0: this charter (318d322)
- [x] act 1: F1, `launch_profile` returns `builder` under `CLAUDE_SESSION_HELPER=1`; 7 tests red on 1e9b493, green after (ec31285)
- [x] act 2: docs: the helper rule (design §2.1, README source, SKILL), the start steps gain the alpha.2 install; `make readme` round 1 (1926ff2)
- [x] close: this handover; `make check` 0 on 1926ff2 plus this charter (575 passed, doclint, hygiene, validate, readme fresh)
- [x] act 3 (helper of sitting 2026-09-28-6), post-review fixes, each red on its parent, green after: r2 F1 `set model` drops the payload model (88a2cd9, 2 red); r2 F2 conftest clears the sitting variables, 584 passed with them exported (6198499, 2 red); r1 F2 a `<synthetic>` or unknown id keeps the last model and context (eb00559, 4 red); NICE_TO_HAVE.md, measure OK (aed5ba1); `make check` 0 on aed5ba1 (584 passed)

## Handover
1. decide, owner: F1's "or depth >= 1 and no start of its own" is not built: a session cannot tell its own start from an inherited depth. Relay children (depth 1, no helper mark) keep the profile the relay exports; a helper that sets its own profile is still `builder`. Recommended: the relay exports `CLAUDE_SESSION_PROFILE=builder`. Consumer: agent-relay's next packet.
2. Non-blocking: every open item of both rounds is in NICE_TO_HAVE.md (act 3). Consumer: the next packet writer.
3. The installed launcher is alpha.1: the README now puts `make install`, `claude plugin update session@claude-code-session` and a restart before the start steps. Consumer: the owner.
4. Logged: r2 F1 is fixed where the set re-resolves (cli.py), not in `pick`, so a later SessionStart's model wins again; the README status count is set by hand in both files (a code span the render keeps), with no `make readme` (it calls claude -p).
- exit taken: goal met; nine commits on `model-ceilings`, not pushed; `make check` 0.

## Next act
The orchestrator reviews and merges `model-ceilings` (round 2 of 2).
