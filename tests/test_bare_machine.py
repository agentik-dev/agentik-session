"""Packet sc2: the plugin on a bare machine, the switch, state across versions, mixed versions.

Each test takes `git archive HEAD plugin`, the whole plugin, into a temp home, and runs it with
the env exactly HOME, PATH=/usr/bin:/bin, CLAUDE_PLUGIN_ROOT and CLAUDE_PLUGIN_DATA. The previous
tree is PIN, alpha.37, read from git. Nothing here reaches the real home: HOME is always $T.
"""
import ast
import importlib
import importlib.machinery
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugin" / "lib"
PROOF = ROOT / "scripts" / "bare-proof"
FLOOR = "/usr/bin/python3"
PIN = "970fff9"
EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
          "PostToolBatch", "PreCompact", "Stop", "StopFailure", "SessionEnd")
SWALLOWED = ("Stop", "StopFailure", "PostToolUseFailure", "PostToolBatch")
RUNS_P = sys.version_info >= (3, 11)    # the previous launcher's -P, and sc3 moves it
SWITCH = (".config", "agentik", "hooks-follow-launcher")
LAUNCHER = (".local", "bin", "agentik-session")
FUTURE = "zz_future"

pytestmark = pytest.mark.skipif(not os.access(FLOOR, os.X_OK), reason="no %s here" % FLOOR)


def _git(*argv, **kw):
    return subprocess.run(["git", *argv], cwd=ROOT, check=True, capture_output=True, **kw)


def _archive(rev, tree, dest, strip=0):
    dest.mkdir(parents=True, exist_ok=True)
    tar = _git("archive", rev, tree).stdout
    subprocess.run(["tar", "-x", "--strip-components", str(strip), "-C", str(dest)], input=tar,
                   check=True)


def _exe(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


class Box:
    """A temp home holding the plugin as a marketplace would, and a temp git repo as the cwd."""

    def __init__(self, t):
        self.t = t
        self.plugin = t / ".claude" / "plugins" / "cache" / "agentik" / "session" / "v"
        _archive("HEAD", "plugin", self.plugin, 1)
        self.data = t / ".claude" / "plugins" / "data" / "session-agentik"
        self.data.mkdir(parents=True)
        self.repo = t / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, env=self.env())
        self.switch = t.joinpath(*SWITCH)
        self.launcher = t.joinpath(*LAUNCHER)
        self.marker = t / "marker"
        self.script = t / "transcript.jsonl"
        self.script.write_bytes((ROOT / "tests/fixtures/meter/under-80.jsonl").read_bytes())

    def env(self, **extra):
        return {"HOME": str(self.t), "PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(self.plugin),
                "CLAUDE_PLUGIN_DATA": str(self.data), **extra}

    def payload(self, event, sid="sess-bare", **over):
        return {"session_id": sid, "transcript_path": str(self.script), "cwd": str(self.repo),
                "hook_event_name": event, "permission_mode": "default", "tool_name": "Bash",
                "tool_input": {"command": "true"}, "tool_use_id": "t1", **over}

    def hook(self, event, shim=None, env=None, **over):
        return subprocess.run([str(shim or self.plugin / "hooks" / "run"), event],
                              input=json.dumps(self.payload(event, **over)), text=True,
                              capture_output=True, cwd=self.repo, env=env or self.env(), timeout=60)

    def tool(self, *argv, stdin="", env=None):
        return subprocess.run([str(self.plugin / "bin" / "agentik-session"), *argv], input=stdin,
                              text=True, capture_output=True, cwd=self.repo, env=env or self.env(),
                              timeout=60)

    def decoy(self):
        _exe(self.launcher, '#!/bin/sh\ncat >/dev/null\necho "$2" >> "%s"\necho "{}"\nexit 2\n'
             % self.marker)

    def marks(self):
        return self.marker.read_text().split() if self.marker.exists() else []

    def on(self):
        self.switch.parent.mkdir(parents=True, exist_ok=True)
        self.switch.write_text("")


@pytest.fixture
def box(tmp_path):
    t = tmp_path / "t"
    t.mkdir()
    return Box(t)


# ---- the proof, in the suite (ruling 8) ------------------------------------------------

@pytest.mark.skipif(sys.version_info < (3, 10), reason="one run, under .venv: the proof runs the floor itself")
def test_the_bare_machine_proof_on_the_moved_tree(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    argv = [str(PROOF), "--transcript", str(ROOT / "tests/fixtures/meter/under-80.jsonl")]
    r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    fails = [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
    if fails and all(ln.split()[1] == "latency" for ln in fails):
        # A load on this shared Mac, or the bar? Once more; twice is a stop (design/04 §8).
        r = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and r.stdout.splitlines()[-1] == "bare-proof: go", r.stdout + r.stderr


def test_the_shipped_runner_is_four_lines_and_the_archive_keeps_the_bits(box):
    lines = (box.plugin / "lib" / "agentik-session").read_text().splitlines()
    assert len(lines) == 4 and "from claude_session.cli import main" in lines
    for rel in ("hooks/run", "bin/agentik-session", "bin/agentik", "scripts/record"):
        assert (box.plugin / rel).stat().st_mode & stat.S_IXUSR, rel
    assert (box.plugin / "bin" / "agentik").read_bytes() == (ROOT / "scripts" / "agentik").read_bytes()
    assert (box.plugin / "scripts" / "record").read_text().startswith("#!/usr/bin/python3\n")
    assert box.tool("--version").stdout.split()[-1] == \
        json.loads((box.plugin / ".claude-plugin" / "plugin.json").read_text())["version"]


def test_no_python_a_hook_exits_0_and_says_so_at_start_other_verbs_exit_3(box, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    gone = box.env(AGENTIK_PYTHON="/nowhere/python3", PATH=str(empty))
    argv = ["/bin/sh", str(box.plugin / "bin" / "agentik-session")]
    run = lambda *a: subprocess.run([*argv, *a], env=gone, capture_output=True, text=True,
                                    timeout=20)
    assert "no python3" in json.loads(run("hook", "SessionStart").stdout)["systemMessage"]
    assert (run("hook", "PostToolUse").returncode, run("hook", "PostToolUse").stdout) == (0, "")
    assert run("status").returncode == 3


def test_a_root_with_a_space_runs(tmp_path):
    t = tmp_path / "t with a space"
    t.mkdir()
    b = Box(t)
    assert b.tool("--version").returncode == 0
    assert b.hook("PostToolUse").returncode == 0


# ---- the switch (design/04 §3, both states) --------------------------------------------

def _off(box, events=EVENTS, env=None):
    for event in events:
        r = box.hook(event, env=env)
        assert r.returncode == 0, (event, r.stderr)
    assert box.marks() == []


def test_switch_off_ten_events_no_marker_with_the_decoy_first_on_path_and_xdg_holding_the_file(box):
    box.decoy()
    xdg = box.t / "xdg-config"
    (xdg / "agentik").mkdir(parents=True)
    (xdg / "agentik" / "hooks-follow-launcher").write_text("")
    _off(box, env=box.env(PATH="%s:/usr/bin:/bin" % box.launcher.parent, XDG_CONFIG_HOME=str(xdg),
                          AGENTIK_HOOKS_FOLLOW_LAUNCHER="1"))


def test_switch_on_a_marker_per_event_the_shims_exits_and_after_rm_none(box):
    box.decoy()
    box.on()
    for i, event in enumerate(EVENTS, 1):
        r = box.hook(event)
        assert box.marks()[-1:] == [event] and len(box.marks()) == i
        if event in SWALLOWED:
            assert (r.returncode, r.stdout) == (0, ""), event
        elif event == "PreCompact":
            assert (r.returncode, r.stdout) == (0, "{}\n"), event
        else:
            assert (r.returncode, r.stdout) == (2, "{}\n"), event
    box.switch.unlink()
    box.marker.unlink()
    _off(box)


@pytest.mark.parametrize("state", ["no launcher", "symlink", "dangling symlink", "directory", "25 h"])
def test_switch_still_off(box, state):
    box.decoy()
    box.on()
    if state == "no launcher":
        box.launcher.unlink()
    elif state in ("symlink", "dangling symlink"):
        box.switch.unlink()
        real = box.t / "elsewhere"
        if state == "symlink":
            real.write_text("")
        box.switch.symlink_to(real)
    elif state == "directory":
        box.switch.unlink()
        box.switch.mkdir()
    else:
        old = time.time() - 25 * 3600
        os.utime(box.switch, (old, old))
    _off(box, ("PreToolUse", "Stop"))
    r = subprocess.run(["/usr/bin/python3", "-I", "-c",
                        "import sys; sys.path.insert(0, sys.argv[1])\n"
                        "from claude_session import hooks\n"
                        "print(hooks.follow_launcher_on({'HOME': sys.argv[2]}))",
                        str(box.plugin / "lib"), str(box.t)], capture_output=True, text=True,
                       env=box.env(), timeout=20)
    assert r.stdout.strip() == "False", r.stderr    # the doctor reads what the shim reads


def _through(box):
    """A launcher at the switch's path that is this plugin's own, so its lines can be read."""
    _exe(box.launcher, '#!/bin/sh\nexec "%s" "$@"\n' % (box.plugin / "bin" / "agentik-session"))


def test_doctor_warns_and_session_start_says_so_only_while_on(box):
    _through(box)
    said = lambda: json.loads(box.hook("SessionStart").stdout)
    doctor = lambda: box.tool("doctor").stdout
    assert "systemMessage" not in said() and "hooks-follow-launcher" not in doctor()
    box.on()
    assert "hooks-follow-launcher" in said()["systemMessage"]
    assert re.search(r"warn.*hooks-follow-launcher|hooks-follow-launcher.*\bon\b", doctor())
    old = time.time() - 25 * 3600
    os.utime(box.switch, (old, old))
    assert "systemMessage" not in said() and "hooks-follow-launcher" not in doctor()
    box.switch.unlink()
    assert "systemMessage" not in said() and "hooks-follow-launcher" not in doctor()


def test_the_switch_is_on_when_the_handler_fails_too(monkeypatch, tmp_path):
    from claude_session import hooks, resolver
    home = tmp_path / "home"
    _exe(home.joinpath(*LAUNCHER), "#!/bin/sh\n")
    home.joinpath(*SWITCH).parent.mkdir(parents=True)
    home.joinpath(*SWITCH).write_text("")
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: 1 / 0)
    out = hooks.session_start({"session_id": "s", "cwd": str(tmp_path)}, {"HOME": str(home)})
    assert set(out) == {"systemMessage"}


# ---- state across versions (ruling 10) -------------------------------------------------

def _future_text(path):
    """The file with an unknown key in every JSON object it holds, a line or the whole."""
    def more(doc):
        return dict(doc, **{FUTURE: {"a": 1}}) if isinstance(doc, dict) else doc
    text = path.read_text(errors="strict")
    try:
        return json.dumps(more(json.loads(text)))
    except ValueError:
        pass
    out = []
    for ln in text.splitlines():
        try:
            out.append(json.dumps(more(json.loads(ln))))
        except ValueError:
            out.append(ln)
    return "\n".join(out) + "\n"


def _seed_state(box, old):
    """What the previous tree writes, by the previous tree: every event, then its other writers."""
    env = box.env(PYTHONPATH=str(old))
    run = lambda *a, stdin="{}": subprocess.run([sys.executable, "-B", "-m", "claude_session", *a],
                                                input=stdin, text=True, capture_output=True,
                                                cwd=box.repo, env=env, timeout=60)
    for event in EVENTS:
        assert run("hook", event, stdin=json.dumps(box.payload(event))).returncode == 0, event
    run("mod", "start", "--session", "sess-bare")
    run("admission", "record", "--session", "sess-bare",
        stdin=json.dumps({"kind": "start", "interactive": True}))
    run("measure", "record", "--session", "sess-bare",
        stdin=json.dumps({"context": {"window": 200000}}))
    return env


def _readers_run(box):
    """Every verb that reads state, and the ten events again, under the watch."""
    said = {}
    for argv, stdin in ((("status", "--json"), ""), (("report",), ""),
                        (("report", "--hooks"), ""), (("doctor",), ""), (("rules",), ""),
                        (("budget",), ""), (("gate", "status"), ""),
                        (("mod", "start", "--session", "sess-bare"), ""),
                        (("admission", "record", "--session", "sess-bare"),
                         json.dumps({"kind": "start", "interactive": True})),
                        (("measure", "record", "--session", "sess-bare"),
                         json.dumps({"context": {"window": 200000}}))):
        r = box.tool(*argv, stdin=stdin, env=box.env(CLAUDE_CODE_SESSION_ID="sess-bare"))
        assert "Traceback" not in r.stderr, (argv, r.stderr)
        # Rows add up between runs, and figures move: a line's shape and the exit are what hold.
        keep = (lambda ln: ln.split()[0]) if argv == ("report", "--hooks") else (
            lambda ln: " ".join(re.sub(r"\d+", "N", ln).split()).rstrip(","))
        said[argv] = (r.returncode, {keep(ln) for ln in r.stdout.splitlines()
                                     if ln.strip() and FUTURE not in ln and '"a":' not in ln})
    for event in EVENTS:
        r = box.hook(event)
        assert r.returncode == 0 and "Traceback" not in r.stderr, (event, r.stderr)
    return said


@pytest.mark.skipif(not subprocess.run(["git", "cat-file", "-e", PIN], cwd=ROOT).returncode == 0,
                    reason="no previous tree in this clone's history")
def test_old_format_and_unknown_key_state_through_the_tools_verbs(box, tmp_path):
    proof = importlib.machinery.SourceFileLoader("bare_proof", str(PROOF)).load_module()
    watch = box.t / ".watch"
    (box.plugin / "lib" / "agentik-session").write_text(proof.RUNNER % {"log": str(watch)})
    old = tmp_path / "old"
    _archive(PIN, "claude_session", old)
    _seed_state(box, old)
    state = box.t / ".local" / "state"
    assert list(state.rglob("meter.json")) and list(state.rglob("resolved.json"))
    plain = _readers_run(box)                       # the old format, read by this version
    assert not watch.exists(), watch.read_text()
    for path in sorted(state.rglob("*")):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            path.write_text(_future_text(path))
    future = _readers_run(box)                      # and with keys it has never heard of
    assert not watch.exists(), watch.read_text()
    moved = {k: (plain[k][0], future[k][0], plain[k][1] ^ future[k][1]) for k in plain
             if plain[k] != future[k]}
    assert not moved


def _written(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# Every function of the package that reads a JSON file of the state it keeps, with an old-format
# file and how to read it. `test_the_table_names_every_reader` holds the list to the code.
S = "sess-bare"
RESOLVED = {"session": {"profile": "p", "window": 200000, "ceilings": {"context": 1, "turns": 2},
                        "checkpoint_at": 0.8}, "git": {}, "session_id": S}
NOW_TS = "2026-10-30T10:00:00+00:00"
SETTINGS = {"model": "opus", "env": {"ANTHROPIC_MODEL": "m"}}


def _modules():
    return {n: importlib.import_module("claude_session." + n) for n in (
        "admission", "chain", "cli", "doctor", "gate", "harness", "hooks", "ledger", "measure",
        "meter", "mod", "models", "policystore", "resolver", "rules", "sessionconfig", "state")}


def _state_env(d):
    return {"HOME": str(d / "home"), "XDG_STATE_HOME": str(d / "state")}


READERS = {
    ("admission", "_rows"): ("l.jsonl", {"ts": NOW_TS, "kind": "spawn"},
                             lambda m, d: m["admission"]._rows(d / "l.jsonl")),
    ("admission", "_dated"): ("l.jsonl", {"ts": NOW_TS},
                              lambda m, d: m["admission"]._dated((d / "l.jsonl").read_text().strip())),
    ("admission", "_session_config"): (
        "state/agentik-session/sessions/%s/resolved.json" % S, RESOLVED,
        lambda m, d: m["admission"]._session_config(_state_env(d), S)),
    ("admission", "read_band"): (
        "state/agentik-session/admission/band.json", {"line": "x"},
        lambda m, d: m["admission"].read_band(_state_env(d))),
    ("chain", "_json"): ("c.json", {"a": 1}, lambda m, d: m["chain"]._json(d / "c.json")),
    ("cli", "_session_section"): (
        "state/agentik-session/sessions/%s/resolved.json" % S, RESOLVED, None),
    ("doctor", "_check_resolved"): (
        "state/agentik-session/sessions/%s/resolved.json" % S, RESOLVED,
        lambda m, d: m["doctor"]._check_resolved(_state_env(d)).ok),
    ("gate", "_load"): ("g.json", {"id": "1", "repo": "/r"}, lambda m, d: m["gate"]._load(d / "g.json")),
    ("harness", "read_hooks"): ("hooks.jsonl", {"event": "Stop", "ms": 1, "exit": 0},
                                lambda m, d: m["harness"].read_hooks(d)),
    ("hooks", "_load_json"): ("h.json", {"at": 1.0}, lambda m, d: m["hooks"]._load_json(d / "h.json")),
    ("ledger", "read"): ("ledger.jsonl", {"session": S, "ended": NOW_TS},
                         lambda m, d: m["ledger"].read(d)),
    ("measure", "load"): ("measure.json", {"context": {"window": 200000}, "at": 1.0},
                          lambda m, d: m["measure"].load(d)),
    ("meter", "_load"): ("meter.json", {"turns": 3, "context": 9}, lambda m, d: m["meter"]._load(d / "meter.json")),
    ("mod", "age"): ("mod.json", {"at": NOW_TS, "version": "2.0.0a37"},
                     lambda m, d: m["mod"].age(d)[0]),
    ("mod", "_at"): ("x.json", {"at": 5.0}, lambda m, d: m["mod"]._at((d / "x.json").read_text())),
    ("mod", "limit_note"): ("x.json", {"at": 5.0, "model": "opus"},
                            lambda m, d: m["mod"].limit_note((d / "x.json").read_text(), None)),
    ("models", "engine_window"): ("measure.json", {"context": {"window": 1000000}},
                                  lambda m, d: m["models"].engine_window(d)),
    ("models", "configured"): ("home/.claude/settings.json", SETTINGS,
                               lambda m, d: m["models"].configured(_state_env(d), d)),
    ("policystore", "load_policy"): ("policy.json", {"reserve_pct": 7.0}, None),
    ("resolver", "load_request"): ("request.json", {"cwd": "/r", "profile": None},
                                   lambda m, d: m["resolver"].load_request(d)),
    ("resolver", "rewindow"): ("resolved.json", RESOLVED, lambda m, d: m["resolver"].rewindow(d, 200000)),
    ("rules", "_settings"): ("home/.claude/settings.json", SETTINGS,
                             lambda m, d: m["rules"]._settings(_state_env(d), d)),
    ("sessionconfig", "load_configs"): ("configs.json", {"mine": {"name": "mine"}}, None),
    ("sessionconfig", "load_overlay"): ("o.json", {"a": 1}, None),
    ("sessionconfig", "last_started"): ("l.json", {"name": "mine"}, None),
    ("state", "hand"): ("state.json", {"from_session": "p", "at": 1.0},
                        lambda m, d: m["state"].hand(d, "p", "s")),
    ("state", "handed"): ("state.json", {"from_session": "p", "to_session": "s", "at": 1.0},
                          lambda m, d: m["state"].handed(d, "s")[0]),
}
# What reads JSON that is not this tool's state between versions, or reads it by name in a verb
# the test above drives: a stdin, a transcript, Claude Code's files, this package's manifest.
NOT_STATE = {("__init__", "_pin"), ("admission", "decode"), ("chain", "_checks"), ("cli", "_coerce"),
             ("doctor", "_plugin_list"), ("doctor", "_check_plugin"), ("doctor", "_check_meter_hook"),
             ("doctor", "hooks_of"), ("hooks", "_with_gate"), ("hooks", "dispatch"), ("hooks", "_confirm"),
             ("ledger", "read_chains"), ("ledger", "restarts_in"), ("meter", "_scan"),
             ("resolver", "resolve"), ("yamlsubset", "_scalar")}


def test_the_table_names_every_reader():
    found = set()
    for path in (LIB / "claude_session").glob("*.py"):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and any(
                    isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                    and c.func.attr in ("load", "loads")
                    and getattr(c.func.value, "id", "") == "json" for c in ast.walk(fn)):
                found.add((path.stem, fn.name))
    assert found - set(READERS) - NOT_STATE == set(), "a new reader joins READERS"


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k != FUTURE}
    if isinstance(x, (list, tuple)):
        return [_strip(v) for v in x]
    return x


@pytest.mark.parametrize("key", sorted(k for k, v in READERS.items() if v[2]), ids="-".join)
def test_each_reader_ignores_a_key_it_does_not_know(key, tmp_path):
    rel, doc, read = READERS[key]
    m = _modules()
    results = []
    for name, doc_now in (("old", doc), ("future", dict(doc, **{FUTURE: {"a": 1}}))):
        d = tmp_path / name
        _written(d / rel, json.dumps(doc_now) + ("\n" if rel.endswith("l") else ""))
        results.append(_strip(read(m, d)))
    assert repr(results[0]).replace("/old", "/D") == repr(results[1]).replace("/future", "/D")


@pytest.mark.parametrize("name,rel,doc,call", [
    ("POLICY_FILE", "policy", {"reserve_pct": 7.0}, lambda m: m["policystore"].load_policy().reserve_pct),
    ("CONFIGS_FILE", "configs", {"mine": {"description": "d"}},
     lambda m: repr(m["sessionconfig"].load_configs()["mine"])),
])
def test_the_stores_ignore_a_key_they_do_not_know(name, rel, doc, call, tmp_path, monkeypatch):
    m = _modules()
    mod = m["policystore"] if name == "POLICY_FILE" else m["sessionconfig"]
    results = []
    # A config file's top level is names, so its unknown key goes a level down.
    more = {"mine": dict(doc["mine"], **{FUTURE: 1})} if "mine" in doc else dict(doc, **{FUTURE: 1})
    for tag, d in (("old", doc), ("future", more)):
        p = _written(tmp_path / tag, json.dumps(d))
        monkeypatch.setattr(mod, "_path", lambda _f, p=p: p)
        results.append(call(m))
    assert results[0] == results[1]


# ---- mixed versions (design/04 §5 step 1) ----------------------------------------------

def _frozen(box, rev, tree, strip, name):
    code = box.t / ".local" / "share" / "agentik-session" / name
    _archive(rev, tree, code, strip)
    wrapper = _git("show", "%s:install-wrapper.sh" % rev, text=True).stdout
    return code, wrapper.replace("__CODE__", str(code)).replace("__PYTHON__", sys.executable)


@pytest.mark.skipif(not RUNS_P, reason="the launcher's -P is 3.11 until sc3")
@pytest.mark.skipif(not subprocess.run(["git", "cat-file", "-e", PIN], cwd=ROOT).returncode == 0,
                    reason="no previous tree in this clone's history")
def test_the_new_plugin_with_the_previous_trees_launcher(box):
    _, text = _frozen(box, PIN, "claude_session", 0, "old")
    _exe(box.launcher, text)
    box.on()
    for event in EVENTS:
        r = box.hook(event)
        assert r.returncode == 0 and "Traceback" not in r.stderr, (event, r.stderr)
    assert list((box.t / ".local" / "state").rglob("meter.json"))
    # The session it leaves is read by the plugin's own code, on one state root.
    box.switch.unlink()
    r = box.hook("SessionStart")
    assert "hookSpecificOutput" in json.loads(r.stdout)
    assert box.tool("report").returncode == 0 and "sess-bar" in box.tool("report").stdout


@pytest.mark.skipif(not RUNS_P, reason="the launcher's -P is 3.11 until sc3")
@pytest.mark.skipif(not subprocess.run(["git", "cat-file", "-e", PIN], cwd=ROOT).returncode == 0,
                    reason="no previous tree in this clone's history")
def test_the_previous_plugin_with_the_new_launcher(box, tmp_path):
    old_plugin = tmp_path / "old-plugin"
    _archive(PIN, "plugin", old_plugin, 1)
    code, text = _frozen(box, "HEAD", "plugin/lib", 2, "new")
    (code / "plugin.json").write_bytes(_git("show", "HEAD:plugin/.claude-plugin/plugin.json").stdout)
    _exe(box.launcher, text)
    env = box.env(PATH="%s:/usr/bin:/bin" % box.launcher.parent, CLAUDE_PLUGIN_ROOT=str(old_plugin))
    for event in EVENTS:
        r = box.hook(event, shim=old_plugin / "hooks" / "run", env=env)
        assert r.returncode == 0 and "Traceback" not in r.stderr, (event, r.stderr)
    assert list((box.t / ".local" / "state").rglob("meter.json"))
    version = json.loads((box.plugin / ".claude-plugin" / "plugin.json").read_text())["version"]
    r = subprocess.run([str(box.launcher), "--version"], capture_output=True, text=True, env=env)
    assert r.stdout.split()[-1] == version


# ---- the floor in `make test` (ruling 9) -----------------------------------------------

@pytest.mark.parametrize("floor,said", [(False, "floor: absent"), (True, "floor-suite")])
def test_make_test_runs_the_floor_or_says_it_is_absent(tmp_path, floor, said):
    (tmp_path / "Makefile").write_bytes((ROOT / "Makefile").read_bytes())
    _exe(tmp_path / ".venv" / "bin" / "python", "#!/bin/sh\necho main-suite\n")
    if floor:
        _exe(tmp_path / ".venv-floor" / "bin" / "python", "#!/bin/sh\necho floor-suite \"$@\"\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAKE", "MFLAGS"))}
    r = subprocess.run(["make", "-s", "test"], cwd=tmp_path, env=env, capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0 and "main-suite" in r.stdout and said in r.stdout, r.stdout + r.stderr
    if floor:
        assert "--ignore=tests/test_bounded.py" in r.stdout
