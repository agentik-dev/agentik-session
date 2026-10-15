# agentik-session: a fresh relay row is charged its life (fresh-session r1)

**Status:** design r1, 2026-10-15, docs only, before its one refuter round. It amends admission-r1 §3.2 on the owner's answer 6 in `OPEN-QUESTIONS.md` (2026-10-15, 01:2x local; on `main` at 7142648): "Yes, fix it." Inputs: `claude_session/admission.py` at 6e97555 (`project` at :684, `_rise`, `runs`, `lives`, `_active`); agentik-relay band-pacing-r1 §2.2 (the ask) and §4 P1 (its census); the plugin's admission ledger as copied at 2026-10-15 08:45Z (`ledger.1.jsonl`, 2,049 lines from 10-13 22:41Z; `ledger.jsonl`, 264 lines from 10-15 03:55Z); the relay's day ledgers of 10-13 to 10-15. Times are UTC; the owner's clock reads seven hours earlier.

The one-sentence design: a relay row's ask charges the row's own main thread for a row's life, learned from the start and end lines of the rows that asked before it, and no spawn term, where today it charges a main thread to the reset and then the same row again as a spawn.

## §1 The problem

The relay asks `agentik-session admission admit --session <id>` with `{model, subagentType: "relay-row", background: true, fork: false, tool_use_id: "<night>/<row>/<part>"}`, where `<id>` is the part's own `--session-id` (band-pacing-r1 §2.2). That id has no ledger line yet. `project` passes it to `_rise` in `sids`, which joins it to the active main threads and charges it a·T, the whole horizon. `project` then adds b_fam·min(T5, L_t) for the same row as a spawn. L_t is the seed, 15 minutes: a row writes no spawn or done line, so `lives` never learns `relay-row`.

The verdict lines, keyed by `tool_use_id`, with their line numbers in the copy:

| ask | line | P | T | peak | what made the peak |
|---|---|---|---|---|---|
| `2026-10-14-7/us3bfix/1`, first ask, 03:55:55Z (20:55:55 local) | `ledger.jsonl:1` | 2 | 274.1 | 174.09 | a 0.1556 × 4 threads × 274.1 = 170.6, of which the fresh id carries 42.6; the spawn term 0.1017 × 15 = 1.5 |
| the same, its highest, 03:59:55Z | `:10` | 3 | 270.1 | 186.19 | a 0.1682, four threads |
| the same, 04:33:55Z | `:49` | 6 | 236.1 | 124.64 | a 0.1240 |
| the same, admitted at the 54th ask, 04:48:55Z | `:66` | 7 | 221.1 | 90.78 | three threads |
| `2026-10-15-1/po2c/1`, first ask, 08:30:41Z (01:30:41 local) | `:230` | 0 | 299.3 | 141.08 | a 0.1161 × 4 × 299.3 = 139.0, of which the fresh id carries 34.7; the spawn term 1.6; a running helper 0.5 |
| the same, the copy's last line, 08:44:41Z | `:264` | 8 | 285.3 | 183.57 | the 15th ask, still held |

Night 2026-10-14-7 held us3bfix 53 minutes while the window read 2 to 7%. That window closed at 08:30Z at 68 (58 at 08:19Z). Rows lived 13.1, 18.2 and 15.4 minutes that night (us3bfix, us4, us4fix), from start line to end line, and us3b 23.1. The other three threads at both asks were interactive sittings, the observer among them.

## §2 The decision

1. **The row is its own main thread, for a row's life.** When the request's type is `relay-row` and its session is not among the active main threads (no reading in the last 45 minutes, or an end line since its newest), `project` leaves it out of `_rise`'s threads and adds a·min(T5, L_row). A `relay-row` ask adds no spawn term at all. The row is a `claude -p` main thread, and the fit counts a running row in m, not in n_f, so its rate is a, not b_fam. Its own term uses the five-hour T5, as a helper's does (admission-r1 fix round F2), because a row admitted just before a weekly reset still runs inside the five-hour window. Every other request is projected as today, and so is the band, which asks for no spawn:

   peak = P + a·T·|active ∪ ({sid}, unless a relay row)| + Σ (running) b_f·min(T5, max(L_t − age, 5)) + (a relay row not active: a·min(T5, L_row); not a relay row: b_f·min(T5, L_t))

2. **Where L_row comes from.** It is the median minutes from start line to end line of the sessions that have a `relay-row` verdict line in the ledger. The verdict's session is the row's own (band-pacing-r1 §2.2). While no such session has ended, the seed life (15) stands. A row never reaches `lives`, which reads only spawn, resume and done lines. Today the four are 23.1, 13.1, 18.2 and 15.4, so the median is 16.8.

3. **A running row stays an active main thread to the reset, and a finished row leaves at its end line.** All 25 relay spawns in the ledger (10-13 23:07Z to 10-15 07:59Z) have a start line (`interactive: false`) and an end line (`reason: other`). Each end line lands within 0.1 minute of the relay's `exit`. `_active` drops a session at an end line later than its newest reading, so no finished row lingers for ACTIVE's 45 minutes. Charging a running row only its life left was measured and rejected (§3 P4).

4. **Rejected.** (b) keeps the spawn term b_opus·min(T5, L) and leaves the id out of the active set. It reads within 5 points of (1) on every ask and gives the same first verdict on all but us1 (94.6 under (b), over the ceiling by 0.6). But it prices a main thread at a helper's rate, which is not what the fit measures. Bounding a running `-p` thread by its life left is rejected in §3 P4. A refit of a over the current window alone is rejected in §3 P5.

5. **Owed to agentik-relay.** An orchestrator sitting asks as `relay-row` too (band-pacing-r1 §2.2), and it may run to its 6-hour wall. It should ask as `relay-orchestrator`, which (1) leaves to today's projection: a main thread to the reset (§5).

## §3 The proof

A read-only replay (Appendix A) runs over copies of the ledgers with `session.admission`'s defaults (observe, ceiling 97, margin 3, the seeds). It sends every relay row since the ledger's start through `decide`, under today's `project` and the proposed one. That is the 5 asks (73 verdict lines), plus, as band-pacing-r1 §4 P1 did, the 21 relay spawns before AR80 that asked nothing, each asked at its spawn. A held row asks again each minute until it is admitted or the five-hour reset comes. The replay leaves the row's own lines out and keeps its burn in P, so each number is an upper bound. A window's highest P is read from the actual path, which already holds the row's own burn.

**P1, fidelity.** From 03:55:55Z, the ask that rotated the ledger, the replay reproduces every logged peak within 0.01: 174.1, 186.19, 124.64 and 90.78 for us3bfix, 141.09 and 183.57 for po2c, and 49.0 and 58.62 for us4 and us4fix. Before that ask, the rotated-away day is missing from the fit, so us3b's logged 96.96 replays as 92.4.

**P2, the holds.**

| row | first ask | P | window's highest | today: verdict, peak, held | proposed: verdict, peak, held |
|---|---|---|---|---|---|
| 2026-10-13-5/po1 | 10-13 23:07 | 66 | 88 | not-started 94.9, 42 min | admitted 87.9 |
| 2026-10-13-5/us1 | 10-13 23:08 | 66 | 88 | not-started 100.8, 41 min | admitted 93.9 |
| 2026-10-13-6/po1b | 10-14 03:46 | 41 | 100 | not-started 235.5, 59 min | not-started 189.7, 59 min |
| 2026-10-13-6/po2 | 10-14 03:46 | 42 | 100 | not-started 284.4, 59 min | not-started 238.7, 59 min |
| 2026-10-13-6/us3a | 10-14 03:47 | 42 | 100 | not-started 332.2, 58 min | not-started 286.5, 58 min |
| 2026-10-13-7/po1bfix | 10-14 06:26 | 100 | 100 | not-started 165.3, to the reset | not-started 148.5, to the reset |
| 2026-10-13-7/po1bfix | 10-14 07:32 | 2 | 79 | admitted 83.0 | admitted 57.3 |
| 2026-10-13-7/po2fix | 10-14 07:32 | 3 | 79 | not-started 110.6, 55 min | admitted 84.9 |
| 2026-10-13-7/us3afix | 10-14 07:33 | 4 | 79 | not-started 138.1, 54 min | not-started 112.4, 8 min |
| 2026-10-13-7/po3 | 10-14 08:15 | 11 | 79 | not-started 258.8, 12 min | not-started 180.9, 12 min |
| 2026-10-14-1/po3fix | 10-14 10:42 | 45 | 79 | admitted 77.9 | admitted 68.3 |
| 2026-10-14-1/usmark | 10-14 10:43 | 45 | 79 | admitted 88.6 | admitted 79.1 |
| 2026-10-14-1/usdoor | 10-14 10:43 | 46 | 79 | not-started 100.2, 22 min | admitted 90.7 |
| 2026-10-14-1/po1c | 10-14 11:43 | 64 | 79 | admitted 66.4 | admitted 65.7 |
| 2026-10-14-2/us2 | 10-14 13:15 | 16 | 100 | admitted 48.8 | admitted 39.3 |
| 2026-10-14-2/po3fixb | 10-14 13:16 | 17 | 100 | admitted 60.3 | admitted 50.9 |
| 2026-10-14-2/po2b | 10-14 14:00 | 58 | 100 | not-started 116.0, 131 min | not-started 107.0, 131 min |
| 2026-10-14-3/us2fix | 10-14 18:38 | 25 | 94 | admitted 76.4 | admitted 63.4 |
| 2026-10-14-3/po2b2 | 10-14 19:22 | 39 | 94 | not-started 94.5, 57 min | admitted 80.9 |
| 2026-10-14-4/us2fix2 | 10-14 21:38 | 76 | 94 | admitted 93.8 | admitted 89.5 |
| 2026-10-14-5/po2b2fix | 10-15 00:12 | 35 | 96 | admitted 84.6 | admitted 72.1 |
| 2026-10-14-6/us3b (asked) | 10-15 01:56 | 65 | 96 | admitted 92.4 | admitted 84.2 |
| 2026-10-14-7/us3bfix (asked) | 10-15 03:55 | 2 | 68 | not-started 174.1, 53 min | not-started 133.5, 48 min |
| 2026-10-14-8/us4 (asked) | 10-15 06:26 | 16 | 68 | admitted 49.0 | admitted 38.5 |
| 2026-10-15-1/us4fix (asked) | 10-15 07:59 | 49 | 68 | admitted 58.6 | admitted 56.0 |
| 2026-10-15-1/po2c (asked) | 10-15 08:30 | 0 | 8, still open | not-started 141.1, 15 min to the copy | not-started 106.7, 15 min to the copy |

Today's projection holds 14 rows for 722 minutes; the proposed one holds 9 for 454. It removes 5 holds (po1, us1, po2fix, usdoor and po2b2, in windows whose highest reading was 88, 88, 79, 79 and 94) and shortens 2 (us3afix from 54 to 8 minutes, us3bfix from 53 to 48). It admits 7 rows earlier than today, none of them in a window that reached 97. The two windows that reached 100 (10-14, resetting 07:30Z and 17:30Z) give their 7 rows the same verdicts and the same hold lengths under both projections. Neither live hold ends: us3bfix is admitted 5 minutes sooner, and po2c reads 106.7 at the copy's last line.

**P3, the life and the linger.** `lives` at every relay ask holds `Explore`, `general-purpose`, `other`, `claude-code-guide` and the `relay:` and `agent-relay:` `adversary`, `attendant` and `builder`, and never `relay-row`, so `_life` gives every row ask the seed of 15. The 25 rows in the ledger lived from 0 to 52.1 minutes (median 20.5). One of them died in 0.2 minutes at 100% (po1bfix, 10-14 06:26Z). Every one has its end line, so §2.3 holds on this ledger.

**P4, a running row bounded: rejected.** This variant charges a running `interactive: false` thread a·min(T5, max(L_row − age, 5)) in place of a·T. Over the ledger's 211 helper asks it turns 13 from held to admitted. Four of them came at 10-14 13:55-13:59Z (three relay:adversary and one relay:builder, today 100.9-103.9, bounded 89.9-93.5), while the row us2 ran. That window reached 100 at 15:02Z. Today's charge on the running row is what held them.

**P5, why the live holds stay.** With (1), us3bfix's first ask reads 133.5 and po2c's 106.7. Three interactive sittings at a, charged to the reset, carry 127.9 and 104.2 points of it. That background term is no outlier on this ledger. In 6 of the 8 windows the ledger opens, the first hour after a reset burned 17 to 40 points (21, 40, 17, 29, 22, 23), which runs to 85-200 over five hours. The other two burned 4 (a window whose highest reading was 9) and 6 (us3bfix's, which closed at 68). A refit of a over the current window's intervals alone, with the seed a when there are none, would admit both live asks and turn 4 of the 78 held first asks (of 216) to admitted, none in a window that reached 97. But both live admits come from the seed a (0.10), because neither window had an interval yet. That is a guess, not a measurement, so it is not taken here.

## §4 The cut into one packet

**S32 fresh row.** It may touch `claude_session/admission.py` (`project` and a new `row_life`), `tests/test_admit.py`, `design/admission-r1.md` (one sentence in §3.2 citing this record) and `NICE_TO_HAVE.md`. Red first: each of these four tests fails at 6e97555. Each uses the seeds (a 0.10, b_opus 0.15, life 15), a reading of P 2 with the reset 274 minutes ahead, and an ask `ask(subagentType="relay-row")`.

- `test_s32_a_fresh_relay_row_is_charged_its_life_not_the_window`: the reading is another interactive thread's, and the asking id has no lines. It reads 2 + 0.10 × 274 + 0.10 × 15 = 30.9. Today it reads 59.05 (0.10 × 2 × 274 + 0.15 × 15).
- `test_s32_a_relay_row_ask_adds_no_spawn_term`: the reading is the asking id's own, so it is active and alone: 2 + 0.10 × 274 = 29.4. Today it reads 31.65.
- `test_s32_the_row_life_is_the_median_of_the_asked_sessions_start_to_end`: as the first test, and hours earlier three asked rows ended 10, 20 and 40 minutes after their start lines. One asked row has no end line, and one interactive session with a `general-purpose` verdict ran 90 minutes. `admission.row_life(rows, seeds)` is 20, and the fresh ask reads 2 + 27.4 + 2.0 = 31.4. Today there is no `row_life`, and the ask reads 59.05.
- `test_s32_a_fresh_relay_row_near_the_weekly_reset_counts_its_life_against_the_five_hour_window`: the other thread reads 40, the week resets in 2 minutes and the window in 150, so 40 + 0.10 × 2 + 0.10 × 15 = 41.7. Today it reads 42.65.

The control stays green before and after: `test_the_peak_against_a_synthetic_day`, `test_f2_a_spawn_near_the_weekly_reset_counts_its_life_against_the_five_hour_window` and `test_a_session_that_read_once_and_ended_does_not_halve_a`, which hold a helper ask's projection where it is. Acceptance is `.venv/bin/python -B -m pytest tests/test_admit.py -q -k s32` reading `passed` with no `failed`, then the control by `-k "synthetic_day or f2_a_spawn or halve"`. Verify is `make check`, run by the coordinator. The budget is 40 turns, one commit per act. The version does not move, since no key, hook output or resolved-file contract changes (conventions §7).

## §5 Open risks

- **The two cited holds stay.** The ruled fix removes the double charge (40.6 points at us3bfix's first ask, 34.4 at po2c's), but both rows stay held. What holds them is the background term: interactive sittings at the fitted a, to the reset. P5 shows that term is not biased high on this ledger, and that the one alternative measured rests on the seed. The next step is admission-r1's P3 (the margin by T, fit from closed windows), or a question to the owner whether a row should wait on sittings that are not gated. This record does not decide either.
- **An orchestrator sitting is under-read at its own ask** until it asks as `relay-orchestrator` (§2.5): a·(T − L_row), up to 35-45 points at a fresh window. From its first reading it is charged a·T. None ran in these ledgers.
- **L_row rests on four rows today.** The median undercounts the long tail (rows ran to 52 minutes, and the 25-row median is 20.5 against the four rows' 16.8), as admission-r1 §6 note 4 says of helpers. The ledger keeps 29 to 58 hours, so the sample turns over.
- **A row that dies without its end line** (SIGKILL, a crash) stays active for 45 minutes after its last reading and is charged a·T. None did in this ledger.
- **A fresh row is charged its life, then a·T from its first reading,** as any active main thread is. A second row's ask in a parallel night, or a sitting's helper, sees it to the reset. That is kept, per P4.
- **po2c's window was still open** at the copy. Its upper bound is unknown, though it read 8 after 14 minutes.
- **The replay before 03:55:55Z lacks the rotated day** (P1). The 21 earlier rows and us3b project from a shorter history than the live `decide` had.

## Appendix A. The replay

Copy the plugin's `ledger.1.jsonl` and `ledger.jsonl` into one scratch folder and the relay's day ledgers into another. Never read the live files in place. Then run `.venv/bin/python -I -B replay.py . <ledger copy> <relay copy>` from the repo root. Its output at 08:45Z is §3's.

```python
"""fresh-session-r1 §3: replay every relay-row ask through `decide`, now and as proposed.

usage: python -I -B replay.py REPO LEDGER_DIR RELAY_DIR
LEDGER_DIR holds copies of the plugin's ledger.1.jsonl and ledger.jsonl; RELAY_DIR copies
of the relay's day ledgers. Read-only: it imports REPO's admission module and writes nothing.
"""
import glob, json, statistics, sys
from datetime import datetime, timedelta

sys.path.insert(0, sys.argv[1])
from claude_session import admission as A, rules  # noqa: E402

LED, REL_DIR = sys.argv[2], sys.argv[3]
ROWS = sorted((json.loads(ln) for f in ("ledger.1.jsonl", "ledger.jsonl")
               for ln in open(f"{LED}/{f}") if ln.strip()), key=lambda r: r["ts"])
for r in ROWS:
    r["_t"] = A._when(r["ts"])
REL = [json.loads(ln) for f in sorted(glob.glob(f"{REL_DIR}/*.jsonl")) for ln in open(f) if ln.strip()]
SET = rules.admission({})                     # the defaults: observe, 97, margin 3, the seeds
HOLD = ("not-started", "deferred", "wait", "denied")
ROW, MIN = "relay-row", timedelta(minutes=1)
CURRENT = A.project


def row_life(rows, seeds):
    """L_row: the median minutes from start line to end line of the sessions that asked as
    a relay row (the verdict's session is the row's own); the seed life with none."""
    asked = {r["session"] for r in rows if r.get("kind") == "verdict" and r.get("type") == ROW}
    starts = {}
    for r in rows:
        if r.get("kind") == "start" and r["session"] in asked and r["_t"]:
            starts.setdefault(r["session"], r["_t"])
    gone, xs = A.ends(rows), []
    for s, t0 in starts.items():
        e = [t for t in gone.get(s, ()) if t >= t0]
        if e:
            xs.append(A._minutes(min(e) - t0))
    return statistics.median(xs) if xs else float(seeds["life"])


def make(bound_running=False):
    """The proposed project (§2); bound_running adds the rejected §2.3 variant."""
    def project(rows, req, sid, now, seeds):
        reads = A.readings(rows, A.FIVE)
        fresh = [x for x in reads + A.limits(req.get("rateLimits"), A.FIVE, now, sid) if x[3] > now]
        if not fresh:
            return None
        _, _, P, resets = max(enumerate(fresh), key=lambda ix: (ix[1][0], ix[0]))[1]
        seven = A.readings(rows, A.SEVEN) + A.limits(req.get("rateLimits"), A.SEVEN, now, sid)
        T, until, bound = A.horizon(resets, seven, now)
        T5 = max(0.0, A._minutes(resets - now))
        row = A.helper_type(req.get("subagentType"), req.get("fork")) == ROW
        rise, f, lv, _ = A._rise(rows, reads, now, T, seeds, set() if row else {sid}, T5)
        act = A._active(reads, now, A.ends(rows))
        L = row_life(rows, seeds)
        if bound_running:                     # §2.3, rejected: a running -p thread to its life
            st = {r["session"]: r for r in rows if r.get("kind") == "start"}
            for m in act:
                s = st.get(m)
                if s is not None and s.get("interactive") is False:
                    age = A._minutes(now - s["_t"])
                    rise -= f["a"] * (T - min(T5, max(L - age, A.FLOOR)))
        if row:
            if sid not in act:
                rise += f["a"] * min(T5, L)    # the row's own main thread, for its life
        else:
            fam = A.family(req.get("model"), req.get("parentModel"))
            typ = A.helper_type(req.get("subagentType"), req.get("fork"))
            rise += f["b"].get(fam, seeds["b"]["other"]) * min(T5, A._life(lv, typ, seeds)[0])
        return {"peak": P + rise, "P": P, "T": T, "resets": resets, "until": until,
                "bound": bound, "fit": f}
    return project


PROPOSED, REJECTED = make(), make(bound_running=True)


def decide(project, rows, req, sid, now):
    A.project = project
    try:
        return A.decide(rows, req, sid, now, SET)
    finally:
        A.project = CURRENT


def before(now, drop=None):
    return [r for r in ROWS if r["_t"] < now and r["session"] != drop]


def window(now):
    """(the window's actual highest P, its reset) for the window open at now."""
    cur = [x for x in A.readings(before(now)) if x[3] > now]
    if not cur:
        return None, None
    resets = max(cur, key=lambda x: x[0])[3]
    return max(x[2] for x in A.readings(ROWS) if A._same(x[3], resets)), resets


def hold(project, req, sid, t0, cap=None):
    """Ask at t0, then each minute as the relay does, until admitted, the five-hour reset or
    cap (an ask still held at the ledger's end); the row's own lines are left out, its burn
    kept in P (an upper bound, as band-pacing-r1 §4 P1). (minutes, first answer, end)."""
    _, resets = window(t0)
    end = min(resets, cap) if cap else resets
    t, first = t0, None
    while t < end:
        v = decide(project, before(t, drop=sid), req, sid, t)
        first = first or v
        if v["verdict"] not in HOLD:
            return A._minutes(t - t0), first, "admitted"
        t += MIN
    return A._minutes(end - t0), first, "open" if cap and end == cap else "reset"


def asks():
    """The relay-row asks (verdict lines) and the relay spawns that asked nothing (before
    AR80), each (kind, tool_use_id, session, first ask, its logged verdicts)."""
    seen = {}
    for r in ROWS:
        if r.get("kind") == "verdict" and r.get("type") == ROW:
            seen.setdefault(r["tool_use_id"], []).append(r)
    out = [("ask", tid, vs[0]["session"], vs[0]["_t"], vs) for tid, vs in seen.items()]
    since = ROWS[0]["_t"]
    for r in REL:
        t = datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) if r.get("event") == "spawn" else None
        if t and t >= since and not r.get("band"):
            out.append(("spawn", f"{r['night']}/{r['row']}/1", r["session_id"], t, None))
    return sorted(out, key=lambda x: x[3])


def main():
    tally = {"cur": [0, 0.0], "new": [0, 0.0], "removed": 0, "earlier": 0, "earlier97": 0}
    for kind, tid, sid, t0, logged in asks():
        req = {"model": "claude-opus-5-5[1m]", "subagentType": ROW, "background": True,
               "fork": False, "tool_use_id": tid}
        top, resets = window(t0)
        cap = logged[-1]["_t"] + MIN if logged and logged[-1]["verdict"] in HOLD else None
        cells, ends = [], []
        for name, project in (("cur", CURRENT), ("new", PROPOSED)):
            mins, first, how = hold(project, req, sid, t0, cap)
            held = first["verdict"] in HOLD
            tally[name][0] += held
            tally[name][1] += mins
            ends.append(mins if how == "admitted" else float("inf"))
            cells.append((held, f"{name} {first['verdict']} {first['peak']:.1f} held {mins:.0f}"
                          + (f" ({how})" if held else "")))
        tally["removed"] += cells[0][0] and not cells[1][0]
        if ends[1] < ends[0]:                 # the proposal admits it earlier than today
            tally["earlier"] += 1
            tally["earlier97"] += top >= 97
        shut = "" if resets <= ROWS[-1]["_t"] else " (open)"
        print(f"{kind:5} {tid:24} {t0:%m-%dT%H:%M} P {first['P']:g} max {top:g}{shut} | "
              + " | ".join(c for _, c in cells))
    print(f"holds now {tally['cur'][0]} ({tally['cur'][1]:.0f} min), proposed {tally['new'][0]} "
          f"({tally['new'][1]:.0f} min); removed {tally['removed']}; admitted earlier "
          f"{tally['earlier']}, of them in a window that reached 97: {tally['earlier97']}")
    # §2.3: the rejected variant over every helper ask in the ledger (its first verdict line)
    flips, seen = [], set()
    for r in ROWS:
        if r.get("kind") != "verdict" or r.get("type") == ROW or r.get("peak") is None:
            continue
        if (r["tool_use_id"], r["type"]) in seen:
            continue
        seen.add((r["tool_use_id"], r["type"]))
        req = {"model": r["family"], "subagentType": r["type"], "fork": r["type"] == "fork",
               "background": True, "tool_use_id": r["tool_use_id"]}
        prior = before(r["_t"])
        a = decide(CURRENT, prior, req, r["session"], r["_t"])
        b = decide(REJECTED, prior, req, r["session"], r["_t"])
        top, _ = window(r["_t"])
        if a["verdict"] in HOLD and b["verdict"] not in HOLD:
            flips.append(f"{r['_t']:%m-%dT%H:%M} {r['type']} {a['peak']:.1f}->{b['peak']:.1f} max {top:g}")
    print(f"rejected variant: {len(seen)} helper asks, {len(flips)} held now and admitted by it;",
          f"{sum(1 for x in flips if float(x.rsplit(' ', 1)[1]) >= 97)} in a window that reached 97")
    for x in flips:
        print("  ", x)


if __name__ == "__main__":
    main()
```
