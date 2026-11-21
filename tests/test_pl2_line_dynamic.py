"""Packet pl2-line-dynamic: the usage line drops the ceiling (R1) and an empty resets count
(R2), closes the seven-day part with the week's reset and its time left (R3), says the
helpers as `helpers n/m` and a deferred count only from 1 (R3b), with the module's twin
drawing the same bytes (R4); and three mends of rc1 and rc2 (R7). Every state here is made
up, under the per-test temp HOME conftest gives; every time is fixed, so the cases are the
one fixture both twins read (`PL2_CASES` in plugin/hooks/session.test.ts)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from claude_session import admission, hooks, resolver, sessionconfig

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "plugin" / "hooks" / ("session.test." + "ts")

# The owner's entry: the week's reset a Wednesday at 07:00, 5 d 4 h 12 min ahead of NOW,
# a Friday at 02:48.
WEEK = datetime(2026, 11, 25, 7, 0, tzinfo=UTC)
NOW = WEEK - timedelta(days=5, hours=4, minutes=12)


def at(**kw) -> str:
    return (NOW + timedelta(**kw)).isoformat(timespec="seconds")


MIX = {"points": {"fable": 30, "opus": 10}, "budgets": {"fable": 50, "opus": 50},
       "next": "opus", "reset": False, "resets_left": 0, "until": None}
OWNER = {"window": "five_hour", "P": 23, "peak": 192, "ceiling": 97,
         "resetsAt": at(hours=4, minutes=39, seconds=30),
         "until": at(hours=4, minutes=39, seconds=30), "bound": "five_hour",
         "running": 5, "room": 0, "deferred": 5, "P7": 41, "mode": "observe",
         "at": NOW.isoformat(timespec="seconds"), "slot": "Wed-0700Z",
         "week_resets": WEEK.isoformat(timespec="seconds"), "mix": MIX}
OWNER_LINE = ("5h 23% → 192% · resets 07:27 (4h39) · helpers 5/5 · 5 deferred · 7d 41% · "
              "week resets Wed 07:00 (5d4h)")
PIN_LINE = ("5h 23% → 192% · ceiling 97 · resets 07:27 (4h39) · 5 helpers, room for 0 · "
            "5 deferred · 7d 41% · resets 0")
HEAD = "5h 23% → 192% · resets 07:27 (4h39)"
WEEK_PART = "week resets Wed 07:00 (5d4h)"
NONE = {"window": "none", "P": None, "peak": None, "room": None, "P7": 62, "ceiling_7d": 97,
        "resetsAt": WEEK.isoformat(timespec="seconds"),
        "until": WEEK.isoformat(timespec="seconds"), "bound": "seven_day", "running": 3,
        "mode": "observe", "at": NOW.isoformat(timespec="seconds")}


def mixed(**kw) -> dict:
    return {**OWNER, "mix": {**MIX, **kw}}


def week_at(**kw) -> dict:
    return {**OWNER, "week_resets": at(**kw)}


# [name, entry, now, line]: every entry of acceptance 1 to 5 and 4b, at its own `now`.
CASES = [
    ["1 the owner's entry", OWNER, NOW, OWNER_LINE],
    ["2 the none line holds no ceiling", {**NONE, "ceiling": 97},
     NOW, "no 5h window · 7d 62% · week resets Wed 07:00 (5d4h) · 3 helpers"],
    ["2 the 5h no reading line holds no ceiling",
     {**NONE, "window": "five_hour", "ceiling": None, "P7": 3}, NOW,
     "5h no reading · 7d 3% · week resets Wed 07:00 (5d4h) · 3 helpers"],
    ["2 a five-hour entry with no reading and a ceiling", {**OWNER, "P": None},
     NOW, "5h no reading · resets 07:27 (4h39) · helpers 5/5 · 5 deferred · 7d 41% · " + WEEK_PART],
    ["3 resets 0 with until ahead draws no count",
     mixed(until=at(days=1)), NOW, OWNER_LINE],
    ["3 resets 2", mixed(resets_left=2), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · resets 2 · {WEEK_PART}"],
    ["3 resets 2 with until ahead", mixed(resets_left=2, until="2026-11-21T18:00:00+00:00"), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · resets 2 by Sat 18:00 · {WEEK_PART}"],
    ["3 reset now", mixed(reset=True), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · reset now · {WEEK_PART}"],
    ["3 resets null with until ahead", mixed(resets_left=None, until="2026-11-21T18:00:00+00:00"),
     NOW, f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · by Sat 18:00 · {WEEK_PART}"],
    ["3 the none line, resets 0 with until ahead",
     {**NONE, "mix": {**MIX, "until": at(days=1)}}, NOW,
     "no 5h window · 7d 62% · week resets Wed 07:00 (5d4h) · 3 helpers"],
    ["3 the none line, resets 2", {**NONE, "mix": {**MIX, "resets_left": 2}}, NOW,
     "no 5h window · 7d 62% · resets 2 · week resets Wed 07:00 (5d4h) · 3 helpers"],
    ["4 no figure, no part", {**OWNER, "week_resets": None}, NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41%"],
    ["4 an old band.json without the key", {k: v for k, v in OWNER.items() if k != "week_resets"},
     NOW, f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41%"],
    ["4 a week's reset that does not parse", {**OWNER, "week_resets": "Wednesday"}, NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41%"],
    ["4 the week bounds the term: the slot's form once",
     {**OWNER, "until": at(hours=2, minutes=5), "bound": "seven_day",
      "week_resets": at(hours=2, minutes=5)}, NOW,
     "5h 23% → 192% · week resets 04:53 (2h05), 5h 07:27 · helpers 5/5 · 5 deferred · 7d 41%"],
    ["4 the mix off still draws it", {k: v for k, v in OWNER.items() if k != "mix"}, NOW,
     OWNER_LINE],
    ["4 24 h exactly", week_at(hours=24), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · week resets Sat 02:48 (1d0h)"],
    ["4 23 h 59 min", week_at(hours=23, minutes=59), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · week resets Sat 02:47 (23h59)"],
    ["4 a reset already past", week_at(minutes=-30), NOW,
     f"{HEAD} · helpers 5/5 · 5 deferred · 7d 41% · week resets Fri 02:18 (0h00)"],
    ["4 the none line, a reset already past", {**NONE, "until": at(minutes=-30)}, NOW,
     "no 5h window · 7d 62% · week resets Fri 02:18 (0h00) · 3 helpers"],
    ["4 the none line, resetsAt alone", {**NONE, "until": None, "resetsAt": at(hours=4, minutes=30)},
     NOW, "no 5h window · 7d 62% · week resets Fri 07:18 (4h30) · 3 helpers"],
    ["4b 0 running and room 6", {**OWNER, "running": 0, "room": 6}, NOW,
     f"{HEAD} · helpers 0/6 · 5 deferred · 7d 41% · {WEEK_PART}"],
    ["4b 3 running and no room", {**OWNER, "running": 3, "room": None}, NOW,
     f"{HEAD} · 3 helpers · 5 deferred · 7d 41% · {WEEK_PART}"],
    ["4b 1 running and no room", {**OWNER, "running": 1, "room": None}, NOW,
     f"{HEAD} · 1 helper · 5 deferred · 7d 41% · {WEEK_PART}"],
    ["4b no running figure", {**OWNER, "running": None, "room": 4}, NOW,
     f"{HEAD} · 5 deferred · 7d 41% · {WEEK_PART}"],
    ["4b 0 deferred", {**OWNER, "deferred": 0}, NOW,
     f"{HEAD} · helpers 5/5 · 7d 41% · {WEEK_PART}"],
    ["4b room past 99 reads as written", {**OWNER, "running": 2, "room": 99}, NOW,
     f"{HEAD} · helpers 2/101 · 5 deferred · 7d 41% · {WEEK_PART}"],
    ["5 the age past 120 s stays last", {**OWNER, "at": at(seconds=-180)}, NOW,
     OWNER_LINE + " · 180s old"],
]


def _now(n) -> datetime:
    return n if isinstance(n, datetime) else datetime.fromisoformat(n)


def _fixture() -> list:
    """CASES as session.test.ts holds them: [entry, now, line] with now an ISO string."""
    return [[e, n.isoformat(timespec="seconds"), line] for _, e, n, line in CASES]


@pytest.mark.parametrize("name,entry,now,line", CASES, ids=[c[0] for c in CASES])
def test_the_line(name, entry, now, line):
    assert admission.band_line(entry, now) == line


def test_1_the_owner_s_line_beside_the_pin_s():
    got = admission.band_line(OWNER, NOW)
    assert got == OWNER_LINE and got != PIN_LINE
    assert "ceiling" not in got and "room for" not in got and "resets 0" not in got.split(" · ")


# ---- acceptance 2: the ceiling is `status`'s ----

def test_2_no_line_holds_the_ceiling():
    for _, e, n, line in CASES:
        assert "ceiling" not in admission.band_line(e, n)


def run(*argv):
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from claude_session import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


SID = "test-sess-0000-5555-6666"


def write_band(b: dict) -> None:
    d = admission.directory(os.environ)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    (d / "band.json").write_text(json.dumps(b))


@pytest.fixture
def metered(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    e = dict(os.environ)
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, e)
    hooks.post_tool_use({"session_id": SID,
                         "transcript_path": str(ROOT / "tests/fixtures/meter/under-80.jsonl")}, e)


def test_2_status_says_the_ceiling_on_the_mode_s_line(metered):
    write_band({k: v for k, v in OWNER.items() if k != "mix"})
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[-1] == "admission mode: observe · ceiling 97"
    got = json.loads(run("status", "--json")[1])
    assert got["admission"] == {"mode": "observe", "ceiling": 97}


def test_2_a_fractional_ceiling_is_drawn_as_the_line_drew_it(metered):
    write_band({**OWNER, "ceiling": 97.5})
    assert run("status")[1].splitlines()[-1] == "admission mode: observe · ceiling 97.5"


def test_2_an_entry_with_no_ceiling_prints_the_mode_alone(metered):
    write_band(NONE)
    rc, out, _ = run("status")
    assert rc == 0 and out.splitlines()[-1] == "admission mode: observe"
    assert json.loads(run("status", "--json")[1])["admission"] == {"mode": "observe"}


# ---- acceptance 3: the count ----

def test_3_mix_status_keeps_its_count_at_any_value():
    assert admission.mix_status(MIX, NOW) == "mix: fable 30/50 · opus 10/50 · next opus · resets 0"
    assert admission.mix_status({**MIX, "until": at(days=1)}, NOW) == (
        "mix: fable 30/50 · opus 10/50 · next opus · resets 0 by Sat 02:48")


# ---- acceptance 4: the time left, and the key band() writes ----

@pytest.mark.parametrize("delta,left", [
    (timedelta(days=5, hours=4, minutes=12), "(5d4h)"), (timedelta(hours=24), "(1d0h)"),
    (timedelta(hours=23, minutes=59), "(23h59)"), (timedelta(hours=4, minutes=30), "(4h30)"),
    (timedelta(seconds=59), "(0h00)"), (timedelta(minutes=-1), "(0h00)"),
    (timedelta(days=12, hours=23, minutes=59, seconds=59), "(12d23h)")])
def test_4_the_time_left(delta, left):
    assert admission.week_left(NOW + delta, NOW) == left


def _reading(ts: datetime, five_at: datetime, week_at_: datetime, P=23.0, P7=41.0) -> dict:
    return {"ts": ts.isoformat(timespec="seconds"), "session": SID, "kind": "reading",
            "rateLimits": [
                {"kind": "five_hour", "percentUsed": P, "resetsAt": five_at.isoformat()},
                {"kind": "seven_day", "percentUsed": P7, "resetsAt": week_at_.isoformat()}]}


def test_4_band_writes_the_week_s_reset_on_a_five_hour_entry():
    """`band()` gains `week_resets`, the seven-day reading P7 reads, local as resetsAt is;
    null with no seven-day reading ahead."""
    from claude_session import rules
    rows = [_reading(NOW - timedelta(minutes=1), NOW + timedelta(hours=4), WEEK)]
    b = admission.band(rows, NOW, rules.admission({}), tz=UTC)
    assert b["window"] == "five_hour" and b["week_resets"] == WEEK.isoformat(timespec="seconds")
    assert admission.band_line(b, NOW).endswith(" · 7d 41% · " + WEEK_PART)
    rows = [_reading(NOW - timedelta(minutes=1), NOW + timedelta(hours=4), NOW - timedelta(hours=1))]
    b = admission.band(rows, NOW, rules.admission({}), tz=UTC)
    assert b["week_resets"] is None and "week resets" not in admission.band_line(b, NOW)


# ---- acceptance 5: the `5h no reading` line is chosen as at the pin ----

@pytest.mark.parametrize("entry,chosen,head", [
    ({"window": "five_hour", "P": None, "ceiling": None, "P7": 3}, True, "5h no reading · 7d 3%"),
    ({"window": "five_hour", "P": None, "ceiling": 97, "P7": 3}, False, "5h no reading · 7d 3%"),
    ({"window": "five_hour", "P": 23, "ceiling": None}, False, "5h 23%"),
    ({"P": None, "ceiling": None}, False, "5h no reading"),
    ({"window": "none", "ceiling": 97}, True, "no 5h window")])
def test_5_the_week_line_is_chosen_as_at_the_pin(entry, chosen, head):
    """draws_week picks `_line_none` as at the pin; with no ceiling on any line the two
    `5h no reading` lines read alike here, so the choice is pinned by draws_week."""
    assert admission.draws_week(entry) is chosen
    assert admission.band_line(entry, NOW) == head


# ---- acceptance 6: the twins ----

def _ts_const(name: str) -> str:
    text = TS.read_text()
    m = re.search(rf"^const {name} = '(.*)'$", text, re.M)
    assert m, name
    return m.group(1)


def test_6_the_module_holds_the_same_cases():
    """The module's PL2_CASES are these entries, nows and lines; its test asserts
    admissionLine draws each line, and test_the_line asserts band_line does."""
    if not TS.exists():
        pytest.skip("no plugin/hooks/*.ts: the classic path stands alone")
    assert json.loads(_ts_const("PL2_CASES")) == json.loads(json.dumps(_fixture()))
    assert "PL2_CASES" in TS.read_text().split("const PL2_CASES", 1)[1].split("\n", 1)[1]
    for entry, now, line in json.loads(_ts_const("PL2_CASES")):
        assert admission.band_line(entry, _now(now)) == line


# ---- acceptance 7: the mends ----

RSID = "test-sess-0000-7777-8888"
CHARTER = "/w/example-app/history/sittings/2026-11-20-9.md"
CLOSE = "agentik session checkpoint --respawn --charter history/sittings/2026-11-20-9.md"
SCRIPT = "zsh wind-down.sh"
LINE = "RESPAWN unconfirmed: "


@pytest.fixture
def hk(frontier_home, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", RSID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.delenv(hooks.CHAIN_VAR, raising=False)


def _sdir():
    return resolver.session_dir(resolver.state_dir(os.environ), RSID)


def _bash(command, **extra):
    return {"session_id": RSID, "tool_name": "Bash", "tool_use_id": "toolu_01WindDown",
            "tool_input": {"command": command}, **extra}


def _mark(written, chain="net"):
    p = _sdir() / hooks.MARKER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"session": RSID, "charter": CHARTER, "charter_sha256": "0" * 64,
                             "written": written, "chain": chain}))
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _stamped(command=SCRIPT, **extra) -> float:
    hooks.pre_tool_use(_bash(command, **extra), os.environ)
    return json.loads((_sdir() / hooks.ACTIVITY).read_text())["at"]


def _ctx(out) -> str:
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


def _said(out) -> list:
    return [b for b in _ctx(out).split("\n\n") if b.startswith(LINE)]


def test_7_a_close_from_a_script_says_the_respawn_line(hk):
    t = _stamped()
    _mark(t + 1)
    out = hooks.post_tool_use(_bash(SCRIPT), os.environ)
    assert _said(out) == [hooks.UNCONFIRMED.format(f=CHARTER)], out
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert not (_sdir() / hooks.CONFIRMED).exists()


def test_7_a_marker_written_at_the_stamp_counts(hk):
    t = _stamped()
    _mark(t)
    assert _said(hooks.post_tool_use(_bash(SCRIPT), os.environ))


@pytest.mark.parametrize("case", ["before", "confirmed", "no chain", "helper", "not bash"])
def test_7_no_line(case, hk):
    t = _stamped()
    sha = _mark(t - 1 if case == "before" else t + 1, chain=None if case == "no chain" else "net")
    if case == "confirmed":
        (_sdir() / hooks.CONFIRMED).write_text(json.dumps({"at": time.time(),
                                                            "marker_sha256": sha}))
    p = _bash(SCRIPT)
    if case == "helper":
        p["agent_id"] = "a1"
    if case == "not bash":
        p = {**p, "tool_name": "Read", "tool_input": {"file_path": "/w/a.md"}}
    assert _said(hooks.post_tool_use(p, os.environ)) == []


def test_7_a_foreground_close_that_confirm_confirms_says_nothing(hk):
    t = _stamped(CLOSE)
    _mark(t + 1)
    out = hooks.post_tool_use(_bash(CLOSE), os.environ)
    assert _said(out) == [] and (_sdir() / hooks.CONFIRMED).exists()


def test_7_the_checkpoint_line_comes_first_and_the_pair_fits(hk):
    t = _stamped()
    _mark(t + 1)
    out = hooks.post_tool_use({**_bash(SCRIPT), "transcript_path":
                               str(ROOT / "tests/fixtures/meter/at-80.jsonl")}, os.environ)
    blocks = _ctx(out).split("\n\n")
    assert blocks[0].startswith("CHECKPOINT: ") and blocks[-1].startswith(LINE), blocks
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_7_the_full_respawn_line_is_dropped_where_the_pair_does_not_fit(hk, monkeypatch):
    """Packet rc3 R1: the full line and the one with the charter unnamed are dropped where
    neither pair fits; the short form is said in their place."""
    t = _stamped()
    _mark(t + 1)
    big = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": "CHECKPOINT: " + "x" * 400}}
    monkeypatch.setattr(hooks, "_post_meter", lambda *a, **k: big)
    out = hooks.post_tool_use(_bash(SCRIPT), os.environ)
    assert _ctx(out) == (big["hookSpecificOutput"]["additionalContext"] + "\n\n"
                         + hooks.UNCONFIRMED_SHORT)
    assert len(json.dumps(out)) <= hooks.MAX_OUT


def test_7_the_refusal_says_a_notice_come_means_ended_and_run_again_now(hk):
    d = _sdir() / hooks.JOBS
    d.mkdir(parents=True, exist_ok=True)
    (d / "toolu_01ExampleCall").write_text(json.dumps({"at": time.time() - 600, "task": "bk1"}))
    out = hooks.pre_tool_use(_bash(CLOSE, tool_use_id="toolu_01TheClose"), os.environ)
    r = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert r.startswith("agentik-session: ") and "\n" not in r and len(r) < 900, r
    assert "whose notice has already come has ended" in r, r
    assert "run the close again now" in r, r


def _job(tid):
    d = _sdir() / hooks.JOBS
    d.mkdir(parents=True, exist_ok=True)
    (d / tid).write_text(json.dumps({"at": time.time(), "task": None}))


def _jobs() -> list:
    d = _sdir() / hooks.JOBS
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


def test_7_ten_thousand_open_tags_scan_in_linear_time(hk):
    _job("toolu_01Kept")
    prompt = (hooks.NOTICE_OPEN + "x") * 10_000
    assert len(prompt) == 200_000
    t0 = time.perf_counter()
    hooks.user_prompt_submit({"session_id": RSID, "prompt": prompt})
    assert time.perf_counter() - t0 < 0.5
    assert _jobs() == ["toolu_01Kept"]


def test_7_a_long_run_inside_one_block_scans_in_linear_time(hk):
    _job("toolu_01Kept")
    prompt = (hooks.NOTICE_OPEN + ("<tool-use-id>" + " " * 15 + "x ") * 5_000
              + "</task-notification>")
    t0 = time.perf_counter()
    hooks.user_prompt_submit({"session_id": RSID, "prompt": prompt})
    assert time.perf_counter() - t0 < 0.5
    assert _jobs() == ["toolu_01Kept"]


def test_7_two_whole_blocks_still_remove_two(hk):
    for tid in ("toolu_01One", "toolu_01Two", "toolu_01Three"):
        _job(tid)

    def block(tid):
        return (f"<task-notification>\n<task-id>z</task-id>\n<tool-use-id> {tid} </tool-use-id>"
                "\n<status>completed</status>\n</task-notification>")
    hooks.user_prompt_submit({"session_id": RSID,
                              "prompt": block("toolu_01One") + "\nbetween\n" + block("toolu_01Two")})
    assert _jobs() == ["toolu_01Three"]
