"""Packet FW2 (hq design/08 section 3 item 3, section 5 row 5): `gate wait --strict`, the
head and key in result.json, and a key's estimate. Each test is red at 942cace (alpha.54)."""
import io
import json
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, gate, resolver
from test_gate import T0, World

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


@pytest.fixture
def w(tmp_path):
    return World(tmp_path)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def plant(root, n, exit=0, seconds=60.0, key="k", cut=None, **more):
    """One result.json, as `_finish` writes it, under counter n."""
    gid = f"20261109-120000-{n}"
    r = {"id": gid, "repo": "/r/x", "command": ["make", "check"], "exit": exit,
         "started": T0, "ended": T0 + seconds, "seconds": seconds,
         "log": str(gate.entry_dir(root, gid) / "log"), "caller": None, "cut": cut,
         "head": SHA, "key": key, **more}
    gate.entry_dir(root, gid).mkdir(parents=True)
    gate.result_path(root, gid).write_text(json.dumps(r))
    return gid


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return resolver.state_dir(os.environ)


def test_fw2_wait_strict_exits_the_jobs_code(state):
    red, green, cut = plant(state, 1, exit=7), plant(state, 2), plant(state, 3, 124, cut="wall cut")
    rc, out, err = run("gate", "wait", red, "--strict")
    assert (rc, err) == (7, "") and out == gate.wait_line(json.loads(
        gate.result_path(state, red).read_text())) + "\n"
    assert run("gate", "wait", red)[0] == 0                     # the default exit, kept
    rc, out, _ = run("gate", "wait", red, "--strict", "--json")
    assert rc == 7 and json.loads(out)["exit"] == 7
    assert run("gate", "wait", green, "--strict")[0] == 0
    assert run("gate", "wait", cut, "--strict")[0] == 124


def test_fw2_wait_strict_keeps_waits_own_codes(state):
    green = plant(state, 1)
    rc, out, _ = run("gate", "wait", green, "--strict")
    assert rc == 0 and out.startswith(f"gate {green} ")
    rc, out, err = run("gate", "wait", "20261109-120000-99", "--strict")
    assert (rc, out) == (2, "") and "no gate" in err           # no result line: wait's own 2
    for n, odd in enumerate((None, "3", True, -1, 256, 2.0), 10):
        gid = plant(state, n, exit=odd)
        assert run("gate", "wait", gid, "--strict")[0] == 1, odd
    assert gate.strict_code({"exit": 255}) == 255 and gate.strict_code({}) == 1


def test_fw2_result_gains_head_and_key(w, tmp_path):
    assert gate.RESULT_KEYS[10:12] == ("head", "key") and len(gate.RESULT_KEYS) == 16
    seen = []
    w.plan = {"a": (3, 0), "b": OSError("no such command")}
    a, b = w.put("a"), w.put("b")
    assert gate.serve(w.root, w.fx(head=lambda repo: seen.append(repo) or SHA)) == 0
    ra, rb = w.result(a["id"]), w.result(b["id"])
    assert list(ra) == list(gate.RESULT_KEYS) == list(rb)
    assert (ra["head"], ra["key"]) == (SHA, a["key"]) and a["key"] == gate.repo_key(str(w.repo))
    assert (rb["exit"], rb["head"]) == (127, SHA)               # read before the spawn
    assert seen == [os.path.realpath(w.repo)] * 2
    assert gate.wait_line(ra).endswith(f"log {ra['log']}")      # the line's shape stands
    lock = tmp_path / "tlc.lock"
    lock.mkdir()
    c = w.put("c", locks=[str(lock)], wall=30)
    assert gate.serve(w.root, w.fx(head=lambda repo: SHA)) == 0
    rc_ = w.result(c["id"])
    assert (rc_["exit"], rc_["head"], rc_["key"]) == (126, None, c["key"])  # never started


def test_fw2_head_is_null_when_unknown_and_never_raises(w, tmp_path, monkeypatch):
    def boom(repo):
        raise RuntimeError("git fell over")
    a = w.put("a")
    assert gate.serve(w.root, w.fx(head=boom)) == 0
    assert w.result(a["id"])["head"] is None and w.result(a["id"])["exit"] == 0
    assert gate._head(str(tmp_path / "gone")) is None and gate._head(str(w.repo)) is None
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}
    g = ["git", "-C", str(w.repo), "-c", "user.name=t", "-c", "user.email=t@" + "example.invalid"]
    subprocess.run(g + ["init", "-q"], check=True, env=env)
    subprocess.run(g + ["commit", "-q", "--allow-empty", "-m", "c"], check=True, env=env)
    want = subprocess.run(g + ["rev-parse", "HEAD"], check=True, env=env, capture_output=True,
                          text=True).stdout.strip()
    assert gate._head(str(w.repo)) == want and len(want) == 40
    other = tmp_path / "other"                                  # the caller's GIT_* is dropped
    g2 = ["git", "-C", str(other), "-c", "user.name=t", "-c", "user.email=t@" + "example.invalid"]
    other.mkdir()
    subprocess.run(g2 + ["init", "-q"], check=True, env=env)
    subprocess.run(g2 + ["commit", "-q", "--allow-empty", "-m", "o"], check=True, env=env)
    subprocess.run(g2 + ["commit", "-q", "--allow-empty", "-m", "p"], check=True, env=env)
    theirs = subprocess.run(g2 + ["rev-parse", "HEAD"], check=True, env=env,
                            capture_output=True, text=True).stdout.strip()
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert theirs != want and gate._head(str(w.repo)) == want


def test_fw2_est_is_the_median_of_the_keys_last_five_greens(w, tmp_path, monkeypatch):
    q = w.put("q")
    k = q["key"]
    for n, s in enumerate((120, 144), 1):
        plant(w.root, n, seconds=float(s), key=k)
    assert gate.estimates(w.root) == {}                         # two greens: none
    st = gate.status(w.root, T0, fx=w.fx())
    assert gate.entry_estimates(w.root) == {} and gate.status_lines(st, {})[0] == (
        f"queued {q['id']} {q['repo']} position 1")
    for n, s in enumerate((150, 140, 160), 3):
        plant(w.root, n, seconds=float(s), key=k)
    plant(w.root, 6, exit=1, seconds=1000.0, key=k)             # a red is not counted
    plant(w.root, 7, exit=0, seconds=9.0, key=k, cut="wall cut")
    plant(w.root, 8, seconds=900.0, key="another")              # nor another key's green
    plant(w.root, 9, seconds=1.0, key=None)                     # nor a result older than FW2
    assert gate.estimates(w.root) == {k: 144.0}
    est = gate.entry_estimates(w.root)
    assert est == {q["id"]: 144.0}
    assert gate.status_lines(st, est)[0] == (
        f"queued {q['id']} {q['repo']} position 1; est 2.4 min")
    assert gate.status_lines(st)[0] == f"queued {q['id']} {q['repo']} position 1"
    plant(w.root, 20, seconds=600.0, key=k)                     # a sixth: the oldest leaves
    assert gate.estimates(w.root) == {k: 150.0}
    assert gate.est_text(144.0) == "2.4" and gate.est_text(322.3) == "5.4"
    scan = tmp_path / "scan"                                    # EST_SCAN: 201 greens of one
    for n in range(1, 202):                                     # key, the oldest not read
        plant(scan, n, seconds=float(n), key="s")
    monkeypatch.setattr(gate, "EST_GREENS", 10 ** 6)
    assert gate._greens(scan) == {"s": [float(n) for n in range(201, 1, -1)]}
    assert gate.key_estimates(scan) == {"s": (101.5, 200)}


def test_fw2_status_keeps_its_shape_and_the_cli_adds_est(w, state):
    q = w.put("q", label="land s38")
    for n in range(1, 4):
        plant(w.root, n, seconds=120.0, key=q["key"])
    g = w.root / "gate"
    (g / "runner.json").write_text(json.dumps({"pid": os.getpid(), "since": T0,
                                               "running": q["id"], "pgid": 1}))
    st = gate.status(w.root, T0, fx=w.fx())
    assert list(st) == ["running", "queued", "done", "runner"]
    assert list(st["running"][0]) == ["id", "repo", "label", "since", "seconds"]
    assert gate.status_lines(st, gate.entry_estimates(w.root))[0].endswith(
        " land s38; est 2.0 min")
    e = gate.enqueue(state, str(w.repo), ["a"], {}, [], 60, "", None, T0)
    for n in range(1, 4):
        plant(state, 50 + n, seconds=120.0, key=e["key"])
    rc, out, _ = run("gate", "status", "--json")
    assert rc == 0 and json.loads(out)["est"] == {e["id"]: 120.0}
    rc, out, _ = run("gate", "status")
    assert out.splitlines()[0].endswith("position 1; est 2.0 min")


def test_fw2_run_says_est_on_stderr(state, tmp_path):
    rc, out, err = run("gate", "run", str(tmp_path), "--", "true")
    gid = out.split()[1]
    assert rc == 0 and err == ""                                # no greens: nothing said
    assert out == (f"queued {gid} position 1 repo {os.path.realpath(tmp_path)} caller none; "
                   f"result {state / 'gate' / gid / 'result.json'}\n")
    k, said = gate.repo_key(str(tmp_path)), []
    for n, s in enumerate((60, 120, 600, 144, 150), 1):    # 3: median 2.0, mean 4.3;
        plant(state, 100 + n, seconds=float(s), key=k)       # 5: median 2.4, mean 3.6
        rc, out, err = run("gate", "run", str(tmp_path), "--", "true")
        assert rc == 0 and out.count("\n") == 1 and out.startswith("queued ")
        said.append(err)
    assert said[:2] == ["", ""]                                 # two greens: nothing said
    assert said[2] == "est 2.0 min: the median of this repo's last 3 greens\n"
    assert said[4] == "est 2.4 min: the median of this repo's last 5 greens\n"


def test_fw2_docs_say_strict_head_and_est():
    for rel in ("plugin/skills/session/SKILL.md", "RUNBOOK.md", "README.md",
                "design/readme/source.md"):
        flat = " ".join((ROOT / rel).read_text().split())
        for word in ("gate wait <id> --strict", "`head`", "est <m> min"):
            assert word in flat, (rel, word)
    doc = " ".join(cli.cmd_gate.__doc__.split())
    assert "exit codes report the task, not the content" in doc and "(entry 25)" not in doc
    gm = " ".join((ROOT / "plugin/commands/gate.md").read_text().split())
    assert "--strict" in gm and "`head`" in gm and "est <m> min" in gm
