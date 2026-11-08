"""`agentik session night` (packet night-1, hq design/07 §2): the loop without its land step.

`night.run` drives `tests/fixtures/night/claude`, a fake on PATH that replays one plan step
per start from `$FAKE_NIGHT_PLAN` and logs its argv, cwd, env and stdin to
`$FAKE_NIGHT_LOG`, in a temp repo with a bare `origin`; the wall clock and the sleep are
faked, the watchdog's clock is real. No real `claude` runs and no request is spent.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from claude_session import night

FIX = Path(__file__).parent / "fixtures" / "night"
QUEUE_IDS = ["green-row", "max-row", "limit-row", "orch-row", "parked-row", "dep-row", "big-row"]


def test_queue_read():
    logged = []
    q = night.read_queue((FIX / "queue.yaml").read_text())
    assert q["version"] == 1 and q["defaults"]["wall"] == "4h"
    assert q["defaults"]["verify"] == "auto"            # the two-line flow map, joined
    assert [r["id"] for r in q["rows"]] == QUEUE_IDS
    rows = {p["id"]: p for p in night.plan(q, None, logged.append)}
    assert rows["green-row"]["turns"] == 100 and rows["green-row"]["usd"] == 25
    assert rows["green-row"]["context"] == 144000 and rows["green-row"]["model"] == "claude-opus-5-5"
    assert rows["max-row"]["model"] == "claude-sonnet-5" and rows["max-row"]["usd"] == 8
    assert night.wall_seconds(rows["max-row"]["wall"]) == 5400
    assert rows["limit-row"]["merge"] == "merge-on-green" and rows["limit-row"]["turns"] == 100
    assert rows["dep-row"]["depends_on"] == ["green-row"]
    assert sorted(logged) == sorted(["ignored words", "ignored defaults.device", "ignored green-row.device",
                                     "ignored max-row.harness", "ignored dep-row.may_touch",
                                     "ignored big-row.surprise"])
    assert [p["id"] for p in night.plan(q, ["dep-row", "green-row"], logged.append)] == ["green-row", "dep-row"]
    with pytest.raises(night.NightError, match="no row 'nope'"):
        night.plan(q, ["nope"], logged.append)
    for bad in ("version: 2\nrows: []\n", "version: 1\nrows:\n  - id: a\n    x: [a, [b]]\n",
                "version: 1\nrows: [a]\n"):
        with pytest.raises(night.NightError):
            night.read_queue(bad)


# ---- the harness: a temp repo with a bare origin, the fake on PATH ----------------------

T0 = 1762520400 - 600          # ten minutes before the fixtures' reset


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


class Box:
    def __init__(self, tmp, monkeypatch):
        self.tmp = tmp
        self.repo = tmp / "repo"
        subprocess.run(["git", "init", "-q", "--bare", str(tmp / "origin.git")], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        (self.repo / "relay").mkdir()
        (self.repo / "relay" / "queue.yaml").write_text((FIX / "queue.yaml").read_text())
        (self.repo / "design" / "packets").mkdir(parents=True)
        for rid in QUEUE_IDS:
            (self.repo / "design" / "packets" / f"{rid}.md").write_text(f"# Packet {rid}\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "the queue")
        _git(self.repo, "remote", "add", "origin", str(tmp / "origin.git"))
        _git(self.repo, "push", "-q", "origin", "main")
        self.log, self.plan = tmp / "fake.log", tmp / "plan.json"
        monkeypatch.setenv("PATH", f"{FIX}{os.pathsep}{os.environ['PATH']}")
        monkeypatch.setenv("FAKE_NIGHT_LOG", str(self.log))
        monkeypatch.setenv("FAKE_NIGHT_PLAN", str(self.plan))
        self.glog, self.gplan = tmp / "gate.log", tmp / "gate-plan.json"
        monkeypatch.setenv("FAKE_GATE_LOG", str(self.glog))
        monkeypatch.setenv("FAKE_GATE_PLAN", str(self.gplan))
        self.slept, self.said = [], []

    def go(self, steps, rows, now=None, ps="", sleep=None, say=None, gate=(), **kw):
        self.plan.write_text(json.dumps(steps))
        self.gplan.write_text(json.dumps(list(gate)))
        for p in (Path(str(self.gplan) + ".n"), self.glog):
            if p.exists():
                p.unlink()
        fx = night.Fx(now=now or (lambda: T0), sleep=sleep or self.slept.append,
                      say=say or self.said.append, env=dict(os.environ), ps=lambda: ps,
                      gate=[str(FIX / "gate")])

        self.fx = fx
        self.rc = night.run(self.repo, rows, fx=fx, **kw)

        self.dir = night.newest_night(fx.env)
        self.ledger = [json.loads(ln) for ln in (self.dir / "ledger.jsonl").read_text().splitlines()]
        self.starts = ([json.loads(ln) for ln in self.log.read_text().splitlines()]
                       if self.log.exists() else [])
        self.gates = ([json.loads(ln) for ln in self.glog.read_text().splitlines()]
                      if self.glog.exists() else [])

        return self

    def kind(self, k):
        return [e for e in self.ledger if e["kind"] == k]


@pytest.fixture
def box(tmp_path, monkeypatch):
    return Box(tmp_path, monkeypatch)


def test_green_built(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    assert box.rc == 0
    (row,), (stop,) = box.kind("row"), box.kind("stop")
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    assert row["state"] == "built" and row["sha"] == _git(wt, "rev-parse", "HEAD")
    assert row["worktree"] == str(wt) and "resume" not in row and row["merge"] == "branch-only"
    assert stop["reason"] == "queue-spent" and stop["rows"] == {"built": ["green-row"]}
    assert stop["cost"] == 1.25
    (spawn,), (ex,) = box.kind("spawn"), box.kind("exit")
    assert spawn["turns"] == 100 and spawn["usd"] == 25 and spawn["part"] == 1
    assert ex["subtype"] == "success" and ex["num_turns"] == 12 and ex["rc"] == 0
    (start,) = box.starts
    assert start["cwd"] == str(wt)
    a = start["argv"]
    assert a[:4] == ["-p", "--permission-mode", "auto", "--allowedTools"]
    assert a[4] == "Bash Edit Write MultiEdit NotebookEdit"
    assert a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--max-turns") + 1] == "100"
    assert a[a.index("--max-budget-usd") + 1] == "25" and a[a.index("--session-id") + 1] == spawn["session_id"]
    assert start["stdin"] == "# The packet; the repo's CLAUDE.md carries the rules\n\n# Packet green-row\n"
    stream = (box.dir / "green-row.jsonl").read_text().splitlines()
    assert len(stream) == 5 and stream[3] == "not a JSON line"       # every line, as it came
    assert oct((box.dir / "ledger.jsonl").stat().st_mode & 0o777) == "0o600"
    assert oct(box.dir.stat().st_mode & 0o777) == "0o700"


def test_max_turns_no_commit(box):
    box.go([{"stream": "max-turns.jsonl"}], ["max-row"])
    assert box.rc == 0
    (row,) = box.kind("row")
    wt = box.repo / ".claude" / "worktrees" / "max-row"
    assert (row["state"], row["reason"]) == ("red", "no-commit")
    assert row["resume"] == f"cd {wt} && claude --resume 0b5c1c39-7a0e-4a52-9a43-1f2d3c4b5a61"
    assert box.kind("limit") == [] and len(box.starts) == 1       # never a limit, never retried
    a = box.starts[0]["argv"]
    assert a[a.index("--model") + 1] == "claude-sonnet-5" and a[a.index("--max-turns") + 1] == "40"


def test_orchestrator_refused(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["orch-row", "parked-row", "dep-row", "big-row"])
    assert box.rc == 0 and box.starts == [] and box.kind("spawn") == []
    got = {r["row"]: (r["state"], r["reason"]) for r in box.kind("row")}
    assert got == {"orch-row": ("refused", "kind"), "parked-row": ("skip", "parked"),
                   "dep-row": ("skip", "gate-failed-dependency"), "big-row": ("refused", "context")}
    log = (box.dir / "log").read_text()
    assert "ignored dep-row.may_touch" in log and "ignored big-row.surprise" in log
    assert not (box.repo / ".claude" / "worktrees").exists()


def test_child_env(box, monkeypatch):
    monkeypatch.setenv("RELAY_ROW", "outer-row")
    monkeypatch.setenv("RELAY_BIN", "/x/relay")
    monkeypatch.setenv("CLAUDE_SESSION_DEPTH", "2")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("RELAY_DEVICE_VERBS", "none")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.quotepath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    env = box.starts[0]["env"]
    assert env["CLAUDE_SESSION_PROFILE"] == "builder" and env["CLAUDE_SESSION_MAX_TURNS"] == "100"
    assert env["CLAUDE_SESSION_MODEL"] == "claude-opus-5-5" and env["RELAY_MEASURE_DEPTH"] == "1"
    for gone in ("RELAY_ROW", "RELAY_BIN", "CLAUDE_SESSION_DEPTH", "CLAUDECODE"):
        assert gone not in env
    assert env["RELAY_DEVICE_VERBS"] == "none"
    assert (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == ("core.quotepath", "false")
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("remote.origin.pushurl", "")
    assert (env["GIT_CONFIG_KEY_2"], env["GIT_CONFIG_VALUE_2"]) == ("remote.origin.pushurl",
                                                                    "relay-denies-push")
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert box.starts[0]["pushurl"] == "relay-denies-push"      # what git itself reads


def test_no_result_stops(box):
    box.go([{"stream": "green.jsonl", "commit": True, "no_result": True}], ["green-row", "max-row"])
    assert box.rc == 3 and len(box.starts) == 1                  # max-row never starts
    (row,), (stop,) = box.kind("row"), box.kind("stop")
    assert (row["state"], row["reason"]) == ("red", "sitting-failure")
    assert stop["reason"] == "sitting-failure"


S2 = "7d2e9f10-3c4b-4e5a-8f6d-2a1b3c4d5e6f"


def test_rate_limit_resumes_once(box):
    box.go([{"stream": "rate-limit.jsonl"}, {"stream": "green.jsonl", "commit": True}], ["limit-row"])
    assert box.rc == 0
    (lim,) = box.kind("limit")
    assert (lim["limit_kind"], lim["resets_at"], lim["source"], lim["action"]) == (
        "five_hour", 1762520400, "event", "resume")
    assert sum(box.slept) == 720 and max(box.slept) <= 60       # the reset plus 120 s
    one, two = box.starts
    a = two["argv"]
    assert a[:3] == ["-p", "--resume", S2] and "--session-id" not in a
    assert a[a.index("--max-turns") + 1] == "70" and a[a.index("--max-budget-usd") + 1] == "11"
    assert two["stdin"] == "continue from your charter's act in flight; your commits stand\n"
    assert two["cwd"] == one["cwd"] and two["env"]["CLAUDE_SESSION_PROFILE"] == "builder"
    assert [s["part"] for s in box.kind("spawn")] == [1, 2]
    (row,) = box.kind("row")
    assert row["state"] == "built"
    assert len((box.dir / "limit-row.jsonl").read_text().splitlines()) == 4 + 5   # one stream


def test_rate_limit_twice_stops(box):
    box.go([{"stream": "rate-limit.jsonl"}], ["limit-row", "green-row"])
    assert box.rc == 3 and len(box.starts) == 2
    assert [e["action"] for e in box.kind("limit")] == ["resume", "stop"]
    (row,), (stop,) = box.kind("row"), box.kind("stop")
    assert (row["state"], row["reason"]) == ("limit", "five_hour") and row["resume"].endswith(S2)
    assert stop["reason"] == "usage-limit"


def test_watchdog_kills(box):
    t = time.monotonic()
    box.go([{"stream": "green.jsonl", "sleep": 60}], ["green-row"], stall=1, poll=0.2)
    assert time.monotonic() - t < 10
    (row,), (ex,) = box.kind("row"), box.kind("exit")
    assert (row["state"], row["reason"]) == ("red", "stalled") and "resume" in row
    assert ex["rc"] < 0 and ex["subtype"] is None               # killed before its result
    assert box.rc == 0 and box.kind("stop")[0]["reason"] == "queue-spent"
    assert "stalled" in (box.dir / "log").read_text()


def test_status_newest(box, capsys):
    from claude_session import cli
    assert cli.main(["night", "status"]) == 0
    assert capsys.readouterr().out == "no night yet\n"
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    box.go([{"stream": "max-turns.jsonl"}], ["max-row"])
    assert cli.main(["night", "status", "--json"]) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["night"] == "night-" + box.dir.name and st["dir"] == str(box.dir)
    assert st["rows"] == {"red": [{"row": "max-row", "reason": "no-commit", "sha": None}]}
    assert st["stop"] == {"reason": "queue-spent", "cost": 3.5} and st["running"] is None
    d = box.dir.with_name(box.dir.name.rsplit("-", 1)[0] + "-10")      # 10 sorts past 2
    d.mkdir(mode=0o700)
    (d / "ledger.jsonl").write_text(json.dumps({"ts": "t", "kind": "spawn", "row": "green-row"})
                                    + "\nnot json\n")
    (d / "green-row.jsonl").write_text('{"type": "system"}\n{"type": "assistant", "x": "' + "y" * 300 + '"}\n')
    assert cli.main(["night", "status"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == f"night-{d.name}: {d}"
    assert out[1].startswith("  running green-row, its last line ") and len(out[1]) < 280
    assert out[1].endswith("y" * (200 - len('{"type": "assistant", "x": "')))  # 200 chars


# ---- the adversary round's fixes (F1, F2, F4, F5, F7) -----------------------------------

def _result(text):
    return {"type": "result", "subtype": "success", "is_error": True, "result": text,
            "session_id": S2, "num_turns": 3, "total_cost_usd": 0.5}


def _read(*events):
    part = night.Part()
    for e in events:
        night.classify(e, part)
    return part


def test_api_status_outranks_needles_whole_words():                       # F1
    p = _read(_result('API Error: 401 {"type":"authentication_error"} rate limit on token refresh'))
    assert p.auth and p.limit is None                     # the status, not the needle
    p = _read(_result("API Error: 500 internal error in the relogin step"))
    assert not p.auth and p.limit is None                 # relogin is not the word login
    p = _read(_result("API Error: 429 Too many requests"))
    assert p.limit == {"kind": "unknown", "resets_at": None, "source": "text"} and not p.auth
    p = _read(_result("Invalid API key. Please run /login"))
    assert p.auth and p.limit is None
    assert night.holds("x rate_limit_error y", "rate_limit") and not night.holds("relogin", "login")
    p = _read({"type": "result", "subtype": "error_max_turns", "is_error": True,
               "result": "API Error: 429 usage limit"})
    assert p.limit is None                                # the sitting's own cap


def test_text_kind_and_top_level_status():                                # F5, F7
    assert _read(_result("API Error: 429 weekly limit reached")).limit["kind"] == "seven_day"
    assert _read(_result("You've hit your session limit, resets 3am")).limit["kind"] == "session"
    assert _read(_result("You've reached your Opus limit")).limit["kind"] == "model_opus"
    assert _read(_result("you've hit your usage limit")).limit["kind"] == "unknown"
    p = _read({"type": "rate_limit_event", "status": "rejected"})
    assert p.limit == {"kind": "unknown", "resets_at": None, "source": "event"}
    p = _read({"type": "rate_limit_event", "status": "rejected", "rate_limit_info": {
        "status": "allowed", "rateLimitType": "five_hour"}})
    assert p.limit is None                                # rate_limit_info's status rules
    assert _read({"type": "rate_limit_event"}).limit is None


def _stream(tmp, name, text):
    path = tmp / name
    path.write_text(json.dumps({"type": "system", "subtype": "init", "session_id": S2}) + "\n"
                    + json.dumps(_result(text)) + "\n")
    return str(path)


def test_unknown_limit_waits_as_fallback(box):                            # F2
    s = _stream(box.tmp, "unknown.jsonl", "API Error: 429 Too many requests")
    box.go([{"stream": s}, {"stream": "green.jsonl", "commit": True}], ["limit-row"])
    (lim,) = box.kind("limit")
    assert (lim["limit_kind"], lim["source"], lim["wait_from"], lim["action"]) == (
        "unknown", "fallback", "fallback", "resume")
    assert sum(box.slept) == 1800 and box.kind("row")[0]["state"] == "built"


def test_weekly_text_stops_at_once(box):                                  # F5
    s = _stream(box.tmp, "weekly.jsonl", "API Error: 429 weekly limit reached")
    box.go([{"stream": s}], ["limit-row", "green-row"])
    assert box.rc == 3 and len(box.starts) == 1 and box.slept == []     # no wait, no resume
    (lim,), (stop,) = box.kind("limit"), box.kind("stop")
    assert (lim["limit_kind"], lim["action"]) == ("seven_day", "stop")
    assert stop["reason"] == "usage-limit"


def test_sigint_ends_the_night_after_the_child(box, monkeypatch):         # F4
    real, sent = night.signals, []

    def once(wt, pgid):
        if not sent:
            sent.append(pgid)
            os.kill(os.getpid(), __import__("signal").SIGINT)
        return real(wt, pgid)
    monkeypatch.setattr(night, "signals", once)
    box.go([{"stream": "green.jsonl", "commit": True, "sleep": 1}], ["green-row", "max-row"],
           poll=0.2)
    assert box.rc == 3 and len(box.starts) == 1
    assert box.kind("row")[0]["state"] == "built" and box.kind("stop")[0]["reason"] == "signal"


def test_a_dying_night_kills_its_child(box, monkeypatch):                 # F4
    seen = []

    def die(wt, pgid):
        if seen:
            raise RuntimeError("the loop broke")
        seen.append(pgid)
        return ("h", 0.0, ())
    monkeypatch.setattr(night, "signals", die)
    with pytest.raises(RuntimeError):
        box.go([{"stream": "green.jsonl", "sleep": 60}], ["green-row"], poll=0.2)
    d = night.newest_night(dict(os.environ))
    stop = [json.loads(ln) for ln in (d / "ledger.jsonl").read_text().splitlines()][-1]
    assert stop["kind"] == "stop" and stop["reason"] == "error" and "the loop broke" in stop["error"]
    with pytest.raises(ProcessLookupError):
        os.killpg(seen[0], 0)                            # the child's group is gone


# ---- night-2: the refusals, the land step, the stops, the report -----------------------

def _no_nights():
    return not night.nights_dir(dict(os.environ)).exists()


def test_relay_running_refused(box):
    for ps, why in (("x\n/opt/homebrew/bin/agentik-relay run --night\n", "relay-running: "
                     "/opt/homebrew/bin/agentik-relay run --night"),
                    ("agentik relay run " + "q" * 200, "relay-running: agentik relay run q"),
                    (None, "ps: ")):
        with pytest.raises(night.NightError, match="^" + why.replace("$", r"\$")) as e:
            box.go([], ["green-row"], ps=ps)
        assert len(str(e.value)) <= len("relay-running: ") + 120
    assert _no_nights() and not box.log.exists()
    for fine in ("agentik session night run x", "grep agentik-relayrun", "agentik relay status"):
        box.go([{"stream": "max-turns.jsonl"}], ["orch-row"], ps=fine + "\n")
        assert box.rc == 0


def test_land_absent_builds(box, capsys):
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("built", "no-land") and box.kind("gate") == []
    assert "limit-row: merge-on-green with no land script" in (box.dir / "log").read_text()
    from claude_session import cli
    nights = sorted(os.listdir(night.nights_dir(dict(os.environ))))
    for bad in (str(box.repo / "relay" / "queue.yaml"), str(box.tmp / "nope")):
        with pytest.raises(SystemExit) as e:
            cli.main(["night", "run", str(box.repo), "--land", bad])
        assert e.value.code == 2
        assert "night run: land: " in capsys.readouterr().err
    for args in (["--until", "25:00"], ["--until", "2026-02-30T06:00"], ["--max-rows", "0"]):
        with pytest.raises(SystemExit) as e:
            cli.main(["night", "run", str(box.repo), *args])
        assert e.value.code == 2
    assert sorted(os.listdir(night.nights_dir(dict(os.environ)))) == nights


def _local(t, fmt="%Y-%m-%dT%H:%M"):
    return time.strftime(fmt, time.localtime(t))


def test_until_past_runs_nothing(box):
    seven = time.mktime(time.localtime(T0)[:3] + (7, 0, 0, 0, 0, -1))
    six = night.until_at("06:00", seven)                                    # tomorrow's
    assert _local(six, "%H:%M") == "06:00" and seven < six < seven + 86400
    assert night.until_at("08:30", seven) == seven + 5400

    assert night.until_at("07:00", seven) == seven                          # at or after
    for until in ("2020-01-01T00:00", _local(T0, "%H:%M")):                 # T0 is a whole minute
        box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"], until=until)
        assert box.rc == 0 and box.kind("row") == [] and not box.log.exists()
        assert box.kind("stop")[0]["reason"] == "until"


def test_until_reset_past_shelves(box):
    box.go([{"stream": "rate-limit.jsonl"}], ["limit-row", "green-row"], until=_local(T0 + 300))
    assert box.rc == 3 and len(box.starts) == 1 and box.slept == []
    (lim,), (row,), (stop,) = box.kind("limit"), box.kind("row"), box.kind("stop")
    assert (lim["action"], lim["limit_kind"], lim["wait_s"]) == ("shelve", "five_hour", 720)
    assert (row["state"], row["reason"]) == ("limit", "five_hour") and row["resume"].endswith(S2)
    assert stop["reason"] == "usage-limit"


def test_max_rows(box):
    q = box.repo / "relay" / "queue.yaml"
    q.write_text(q.read_text().replace("  - id: max-row\n", "  - id: orch-first\n    packet: "
                                       "design/packets/orch-row.md\n    kind: orchestrator\n"
                                       "  - id: max-row\n"))
    box.go([{"stream": "max-turns.jsonl"}], ["orch-first", "max-row", "limit-row"], max_rows=1)
    assert box.rc == 0 and len(box.starts) == 1
    got = [(r["row"], r["state"]) for r in box.kind("row")]
    assert got == [("orch-first", "refused"), ("max-row", "red")]       # a refusal not counted

    assert box.kind("stop")[0]["reason"] == "max-rows"


def _stop_file(*_):
    (night.newest_night(dict(os.environ)) / "stop").write_text("")


def test_stop_file(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"],
           say=lambda line: line.startswith("green-row: built") and _stop_file())
    assert box.rc == 3 and len(box.starts) == 1
    assert [r["row"] for r in box.kind("row")] == ["green-row"]
    assert box.kind("stop")[0]["reason"] == "owner-stop"
    slept = []
    box.go([{"stream": "rate-limit.jsonl"}], ["limit-row"],
           sleep=lambda s: slept.append(s) or _stop_file())
    assert box.rc == 3 and slept == [60.0] and len(box.starts) == 2      # one slice, no resume
    assert box.kind("row")[0]["state"] == "limit" and box.kind("stop")[0]["reason"] == "owner-stop"


OK = {"verdict": "land {repo}: ok {sha}, main readied", "exit": 0}


def _land(box):
    land = box.tmp / "land"
    land.write_text("#!/bin/sh\nexit 9\n")          # never run: the fake gate stands for it
    land.chmod(0o755)
    return str(land)


def _merge_on_green(box):
    q = box.repo / "relay" / "queue.yaml"
    q.write_text(q.read_text().replace("merge: branch-only, device", "merge: merge-on-green, device"))


def test_land_ok(box):
    q = box.repo / "relay" / "queue.yaml"
    q.write_text(q.read_text().replace("depends_on: [green-row]", "depends_on: [limit-row]\n"
                                       "    base: limit-row"))
    (box.repo / "design" / "packets" / "limit-row.md").write_text(
        "intro\n## Packet limit-row: the land step\n")
    (box.repo / "scripts").mkdir()
    land = box.repo / "scripts" / "land"
    land.write_text("#!/bin/sh\nexit 9\n")
    land.chmod(0o755)
    (box.repo / ".venv").mkdir()
    box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row", "dep-row"], gate=[OK])
    assert box.rc == 0
    repo = os.path.realpath(box.repo)
    wt = Path(repo) / ".claude" / "worktrees" / "limit-row"
    (g,), (row, dep) = box.kind("gate"), box.kind("row")
    sha, sid = row["sha"], box.kind("exit")[0]["session_id"]
    assert (row["state"], row["reason"], row["worktree"]) == ("landed", None, None)
    assert "resume" not in row and box.ledger.index(g) < box.ledger.index(row)
    assert (g["row"], g["exit"], g["rc"], g["land_line"]) == ("limit-row", 0, 0,
                                                              f"land repo: ok {sha}, main readied")
    assert g["gate_id"] == "20261107T120000-0" and g["gate_line"].startswith(f"gate {g['gate_id']} {repo}: exit 0")
    merge = box.dir / "limit-row.merge.txt"
    assert merge.read_text() == (f"Merge limit-row: the land step\n\nRow limit-row, packet "
                                 f"design/packets/limit-row.md, built by night-{box.dir.name} in "
                                 f"session {sid} at {sha}.\n")
    assert oct(merge.stat().st_mode & 0o777) == "0o600"
    (call,) = box.gates
    assert call["argv"] == ["run", "--wait", repo, "--", str(Path(repo) / "scripts" / "land"),
                            repo, "limit-row", sha, str(merge)] and call["cwd"] == repo
    assert (dep["row"], dep["state"]) == ("dep-row", "built")          # its dependency landed
    assert os.readlink(wt / ".venv") == os.path.join(repo, ".venv")    # linked, and no dirt
    assert box.kind("stop")[0]["rows"] == {"landed": ["limit-row"], "built": ["dep-row"]}


def test_land_red_step(box):
    _merge_on_green(box)
    box.go([{"stream": "green.jsonl", "commit": True}], ["max-row", "limit-row"], land=_land(box),
           gate=[{"verdict": "land {repo}: red check exit 2", "exit": 2},
                 {"verdict": "land {repo}: red remove exit 1, the merge stands", "exit": 1}])
    assert box.rc == 0 and len(box.gates) == 2
    red, stands = box.kind("row")
    wt = Path(os.path.realpath(box.repo)) / ".claude" / "worktrees" / "max-row"
    assert (red["state"], red["reason"], red["worktree"]) == ("red", "land-check", str(wt))
    assert red["resume"].startswith(f"cd {wt} && claude --resume ") and wt.is_dir()
    assert _git(box.repo, "branch", "--list", "max-row")
    assert (stands["state"], stands["reason"]) == ("landed", "land-remove")
    assert [g["exit"] for g in box.kind("gate")] == [2, 1]


def test_land_gate_unrun(box):
    bad = [{"no_line": True, "rc": 2}, {**OK, "exit": 1}, {**OK, "no_log": True},
           {"verdict": "make: *** [check] Error 2", "exit": 2},
           {"verdict": "land {repo}: ok 0123abc, main readied", "exit": 0}]
    for step in bad:
        box.go([{"stream": "green.jsonl", "commit": True}], ["limit-row"], land=_land(box),
               gate=[step])
        (row,), (g,) = box.kind("row"), box.kind("gate")
        assert (row["state"], row["reason"]) == ("red", "gate-unrun") and "resume" in row
        assert box.rc == 0 and len(box.gates) == 1
        _git(box.repo, "worktree", "remove", "--force", str(box.repo / ".claude" / "worktrees" / "limit-row"))
        _git(box.repo, "branch", "-D", "limit-row")
    assert g["rc"] == 0 and g["land_line"] == "land repo: ok 0123abc, main readied"


def test_land_branch_only_calls_no_gate(box):
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"], land=_land(box), gate=[OK])
    assert box.rc == 0 and box.gates == [] and box.kind("gate") == []
    (row,) = box.kind("row")
    assert (row["state"], row["reason"], row["merge"]) == ("built", None, "branch-only")


def test_report(box, capsys):
    from claude_session import cli
    assert cli.main(["night", "report"]) == 0 and capsys.readouterr().out == "no night yet\n"
    box.go([{"stream": "green.jsonl", "commit": True}, {"stream": "max-turns.jsonl"},
            {"stream": "green.jsonl", "commit": True}],
           ["green-row", "max-row", "limit-row", "orch-row", "parked-row"], land=_land(box), gate=[OK])
    first = box.dir
    rows = {r["row"]: r for r in box.kind("row")}
    d = first.with_name(first.name.rsplit("-", 1)[0] + "-10")
    d.mkdir(mode=0o700)
    (d / "ledger.jsonl").write_text("\n".join(json.dumps(e) for e in (
        {"kind": "spawn", "row": "limit-row"}, {"kind": "exit", "row": "limit-row", "total_cost_usd": 0.5},
        {"kind": "limit", "row": "limit-row", "limit_kind": "seven_day", "resets_at": 1762520400000,
         "action": "stop"},
        {"kind": "row", "row": "limit-row", "state": "limit", "reason": "seven_day"},
        {"kind": "spawn", "row": "green-row"})) + "\nnot json\n")
    assert cli.main(["night", "report", "--night", "night-" + first.name]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# The night night-{first.name}\n\nstop queue-spent\n")
    assert f"| limit-row | {rows['limit-row']['sha'][:12]} | - |" in out
    assert f"| green-row | {rows['green-row']['sha']} | - | {rows['green-row']['worktree']} |" in out
    assert f"| max-row | no-commit | {rows['max-row']['resume']} |" in out
    assert "| orch-row | kind |" in out and "| parked-row | parked |" in out
    assert "## Limited\n\nnone\n" in out
    assert "| green-row | 1.25 |" in out and "| max-row | 3.50 |" in out and "| total | 6.00 |" in out
    assert cli.main(["night", "report"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# The night night-{d.name}\n\nrunning green-row\n")
    reset = time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(1762520400))
    assert f"| limit-row | seven_day | {reset} | stop |" in out and "| total | 0.50 |" in out
    for unknown in ("night-2020-01-01-1", "../x"):
        with pytest.raises(SystemExit) as e:
            cli.main(["night", "report", "--night", unknown])
        assert e.value.code == 2


def test_queue_quoted_values():                                             # hq NICE n4
    q = night.read_queue(
        'version: 1\n'
        'defaults: {model: "claude {opus}", turns: 10,   # a "comment" { with a brace\n'
        '           usd: 5}\n'
        'words: "not # a comment"\n'
        'rows:\n'
        '  - id: a\n'
        "    packet: 'p''s #1 {x}.md'\n"
        '    parked: "waits { on # the owner"\n'
        '  - id: b\n'
        '    packet: "x.md"   # trailing {\n'
        '    budget: {turns: 3, usd: "1 }"}\n')
    assert q["defaults"] == {"model": "claude {opus}", "turns": 10, "usd": 5}
    assert q["words"] == "not # a comment"
    a, b = q["rows"]
    assert a == {"id": "a", "packet": "p's #1 {x}.md", "parked": "waits { on # the owner"}
    assert b == {"id": "b", "packet": "x.md", "budget": {"turns": 3, "usd": "1 }"}}
    assert night._bare("x: 'it''s' # c") == "x: 'it''s'" and night._bare("  # all") == ""


def test_queue_column_zero_items():                                         # hq NICE n4
    q = night.read_queue(
        'version: 1\n'
        'rows:\n'
        '- id: a\n'
        '  packet: a.md\n'
        '# a comment at column 0\n'
        '- id: b\n'
        '  packet: b.md\n'
        '  budget: {turns: 5,\n'
        '           usd: 2}\n'
        'words: after\n')
    assert [r["id"] for r in q["rows"]] == ["a", "b"] and q["words"] == "after"
    assert q["rows"][1]["budget"] == {"turns": 5, "usd": 2}
