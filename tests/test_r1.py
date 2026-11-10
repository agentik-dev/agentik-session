"""Packet R1 (hq design/08 §4, "Acceptance. R1, the library"): `claude_session/reconcile/`,
three detectors pure over injected readers, no model.

T1 to T4 are the acceptance's items (1) to (4); each world is built here, in a temp root: git
is real (a temp repo, dates set by the environment), every transcript is synthetic."""
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "plugin" / "lib" / "claude_session" / "reconcile"
NOW = 1794232800.0                       # 2026-11-09 14:00 UTC
DAY = 86400
HEAD = ("# Sitting {name}: hq, x\n\n| item | value |\n|---|---|\n| goal | {goal} |\n"
        "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n## Done-ness\n\n"
        "## Handover\n\n## Next act\nx\n")
KEYS = {"id", "kind", "repo", "value", "threshold", "flagged", "evidence"}


def _rc():
    from claude_session import reconcile
    return reconcile


def git(cwd, *args, at=None):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    if at is not None:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = "@%d +0000" % at
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(cwd),
                           *args], env=env, check=True, capture_output=True, text=True).stdout


def charter(hq, name, goal):
    d = hq / "history" / "sittings"
    d.mkdir(parents=True, exist_ok=True)
    p = d / (name + ".md")
    p.write_text(HEAD.format(name=name, goal=goal))
    return p


def world(tmp_path):
    hq, repos, projects = tmp_path / "code" / "hq", tmp_path / "code", tmp_path / "projects"
    hq.mkdir(parents=True)
    projects.mkdir()
    tree = {"repos": [{"name": "tool"}, {"name": "side"}, {"name": "hq"}]}
    return tree, {"hq": hq, "repos": repos, "projects": projects}


def one(findings, fid):
    [f] = [f for f in findings if f["id"] == fid]
    return f


# ---- (1) live.goal_unchanged ---------------------------------------------------------------

LOOP = ["the standing loop, wake {n} of 12", "the standing loop {n}", "the standing loop, {n}"]


def goal_world(tmp_path):
    tree, roots = world(tmp_path)
    for n in range(1, 11):               # older than the newest 20: all one row, never counted
        charter(roots["hq"], "2026-10-01-%d-hq" % n, "the standing loop, old %d" % n)
    # 2026-11-01-1..22: the newest 20 are 3..22 by number; by name (`ls | tail -20`) they
    # would be 2..9 and 11..22, which holds 2 (a loop row) and drops 10 (a distinct one)
    distinct = {1, 10, 13, 16, 19, 21, 22}
    for n in range(1, 23):
        goal = "goal number %d is its own" % n if n in distinct else LOOP[n % 3].format(n=n)
        goal = goal.replace("number %d" % n, "number " + "abcdefghijklmnopqrstuvwxyz"[n])
        charter(roots["hq"], "2026-11-01-%d%s" % (n, "-hq" if n % 2 else ""), goal)
    return tree, roots


def test_r1_goal_unchanged_counts_the_newest_20_by_number(tmp_path):
    tree, roots = goal_world(tmp_path)
    f = one(_rc().detect(tree, 14, NOW, roots, detectors=["live.goal_unchanged"]),
            "live.goal_unchanged")
    assert (f["value"], f["threshold"], f["flagged"]) == (14, 10, True)
    assert f["evidence"]["numbers"]["charters"] == 20
    assert set(f) == KEYS and f["kind"] == "live" and f["repo"] == "hq"
    g = one(_rc().detect(tree, 14, NOW, roots, detectors=["live.goal_unchanged"],
                         thresholds={"live.goal_unchanged": 15}), "live.goal_unchanged")
    assert (g["value"], g["flagged"]) == (14, False)


# ---- (2) live.since_landing ----------------------------------------------------------------

def landing_world(tmp_path):
    tree, roots = world(tmp_path)
    T0 = int(NOW) - 5 * DAY
    for name, merge_at in (("tool", T0 + DAY), ("side", T0 + 4 * DAY)):
        r = roots["repos"] / name
        r.mkdir()
        git(r, "init", "-q", "-b", "main")
        (r / "a").write_text("a")
        git(r, "add", "a")
        git(r, "commit", "-q", "-m", "a", at=T0)
        git(r, "checkout", "-q", "-b", "row")
        (r / "b").write_text("b")
        git(r, "add", "b")
        git(r, "commit", "-q", "-m", "b", at=T0 + 60)
        git(r, "checkout", "-q", "main")
        git(r, "merge", "-q", "--no-ff", "-m", "land row", "row", at=merge_at)
    hq = roots["hq"]
    git(hq, "init", "-q", "-b", "main")
    for i, (name, at) in enumerate((("2026-11-04-1-hq", T0 + DAY - 3600),
                                    ("2026-11-05-1-hq", T0 + DAY + 3600),
                                    ("2026-11-06-1-hq", T0 + 2 * DAY))):
        p = charter(hq, name, "g %d" % i)
        git(hq, "add", str(p.relative_to(hq)))
        git(hq, "commit", "-q", "-m", "open " + name, at=at)
    (hq / "HANDOFF.md").write_text("h")
    git(hq, "add", "HANDOFF.md")
    git(hq, "commit", "-q", "-m", "record", at=T0 + 2 * DAY + 60)
    return tree, roots


def test_r1_since_landing_counts_the_charters_opened_after_the_newest_goal_merge(tmp_path):
    tree, roots = landing_world(tmp_path)
    # `side` merged later, but only `tool` is on the goal's path
    f = one(_rc().detect(tree, 14, NOW, roots, goal=["tool"], detectors=["live.since_landing"]),
            "live.since_landing")
    assert f["value"] == 2
    assert f["evidence"]["numbers"]["hq_commits"] == 3
    assert f["evidence"]["numbers"]["landing_at"] == int(NOW) - 4 * DAY
    assert set(f) == KEYS and f["kind"] == "live"


# ---- (3) eff.idle --------------------------------------------------------------------------

def _user(text, ts, **kw):
    return {"type": "user", "isSidechain": False, "timestamp": ts,
            "message": {"role": "user", "content": text}, **kw}


def _call(mid, ts, usage, *blocks, side=False):
    return {"type": "assistant", "isSidechain": side, "timestamp": ts, "requestId": "req_" + mid,
            "message": {"id": mid, "role": "assistant", "model": "claude-opus-5-5",
                        "content": list(blocks), "usage": usage}}


def _tool(name, **inp):
    return {"type": "tool_use", "id": "toolu_" + name, "name": name, "input": inp}


def _u(i=0, cw=0, cr=0, out=0):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
            "output_tokens": out}


def slug(path):
    import re
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(str(path)))


def idle_world(tmp_path):
    tree, roots = world(tmp_path)
    ts = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - 3600 + s))
    a1 = _call("a1", ts(11), _u(1, 100, 200000, 50), {"type": "text", "text": "x"})
    rows = [
        _user("build the parser", ts(0)),
        _call("w1", ts(1), _u(5, 3000, 150000, 900), _tool("Write", file_path="/r/x.py")),
        _user("/loop check the gate", ts(10)),
        _user("<local-command-caveat>", ts(10), isMeta=True),
        a1,
        dict(a1, message=dict(a1["message"], content=[_tool("Bash", command="git status")])),
        _user([{"type": "tool_result", "tool_use_id": "toolu_Bash", "content": "ok"}], ts(12)),
        _call("a2", ts(13), _u(1, 0, 200000, 30), _tool("ScheduleWakeup", delaySeconds=1200)),
        _call("s1", ts(14), _u(9, 9, 9000000, 9), _tool("Write", file_path="/r/y"), side=True),
        _user("<task-notification>helper done</task-notification>", ts(20)),
        _call("h1", ts(21), _u(2, 500, 210000, 400), _tool("Agent", prompt="p")),
    ]
    d = roots["projects"] / slug(roots["hq"])
    d.mkdir(parents=True)
    p = d / "s1.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    os.utime(p, (NOW - 60, NOW - 60))
    old = d / "s0.jsonl"                 # outside the window: never read
    old.write_text(json.dumps(_user("/loop", ts(0))) + "\n" + json.dumps(
        _call("o1", ts(1), _u(0, 0, 999999, 0))) + "\n")
    os.utime(old, (NOW - 30 * DAY, NOW - 30 * DAY))
    return tree, roots


def test_r1_idle_counts_one_of_three_and_prices_it(tmp_path):
    tree, roots = idle_world(tmp_path)
    f = one(_rc().detect(tree, 14, NOW, roots, detectors=["eff.idle"]), "eff.idle")
    n = f["evidence"]["numbers"]
    assert (n["idle"], n["ticks"]) == (1, 3)
    # two calls reading 200,000 cached tokens at 0.1: 40,000, plus outputs at 5, writes at
    # 1.25 and input at 1 (rules.mix's ratios)
    assert n["idle_weighted"] == pytest.approx(40000 + 5 * (50 + 30) + 1.25 * 100 + 2)
    assert set(f) == KEYS and f["kind"] == "eff"


def test_r1_weights_are_the_mix_prices_ratios():
    from claude_session import rules
    w = _rc().weights()
    p = rules.mix({"shares": {"opus": 1}})["prices"]["opus"]
    assert w == {k: v / p["input"] for k, v in p.items()}
    assert w["cache_read"] * 2 * 200000 == pytest.approx(40000)


# ---- (4) every finding carries its command; no model client --------------------------------

def test_r1_every_finding_carries_its_command_and_the_command_reproduces_it(tmp_path):
    tree, roots = landing_world(tmp_path)
    for n in range(1, 23):
        charter(roots["hq"], "2026-11-07-%d" % n, LOOP[0].format(n=n) if n > 8 else "x %s" % n)
    _, r2 = idle_world(tmp_path / "t")
    roots["projects"] = r2["projects"]
    d = r2["projects"] / slug(r2["hq"])
    d.rename(r2["projects"] / slug(roots["hq"]))
    found = _rc().detect(tree, 14, NOW, roots, goal=["tool"])
    assert sorted(f["id"] for f in found) == ["eff.idle", "live.goal_unchanged",
                                              "live.since_landing"]
    for f in found:
        ev = f["evidence"]
        assert set(ev) == {"command", "numbers", "files"}
        assert isinstance(ev["command"], str) and ev["command"].strip()
        assert isinstance(ev["numbers"], dict) and isinstance(ev["files"], list)
        out = subprocess.run(["/bin/sh", "-c", ev["command"]], capture_output=True, text=True,
                             timeout=60)
        assert out.returncode == 0, (f["id"], out.stderr)
        assert str(f["value"]) in out.stdout.split(), (f["id"], ev["command"], out.stdout)


ALLOWED = {"__future__", "json", "os", "re", "time", "glob", "datetime", "pathlib", "dataclasses",
           "typing", "collections", "sys", "argparse"}
MODEL = ("anthropic", "openai", "claude_agent_sdk", "httpx", "requests", "urllib3", "aiohttp")


def test_r1_the_package_imports_no_model_client():
    files = sorted(PKG.glob("*.py"))
    assert files, "claude_session/reconcile/ is missing"
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module.split(".")[0]]
            else:
                continue
            assert set(names) <= ALLOWED, (path.name, names)
    code = ("import sys; import claude_session.reconcile; "
            "print(sorted(m for m in sys.modules if m.split('.')[0] in %r "
            "or m in ('http.client', 'urllib.request', 'socket', 'ssl')))" % (MODEL,))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "plugin" / "lib")})
    assert (r.returncode, r.stdout.strip()) == (0, "[]"), r.stderr
