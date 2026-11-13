"""Packet ak5: `describe --json`, the config read, and the doctor and status reads in the plug's
envelope (the suite's `agentik config`, `doctor` and `status` read these). Every line runs in a
temp HOME with its XDG_* under it, a temp cwd, and no CLAUDE_* variable but those it names."""
import io
import json
import os
import subprocess
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import cli, doctor, gate, hooks, install, resolver

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "plugin" / "bin" / "agentik-session"
SHIPPED = str(ROOT / "plugin" / "lib" / "claude_session" / "profiles.yaml")
SID = "ak5-sess-0000-1111"
SETTING_KEYS = {"key", "value", "default", "type", "choices", "summary", "source", "change",
                "live", "values"}
DESCRIBE_KEYS = {"schema", "ok", "tool", "version", "summary", "repo", "plugin", "needs",
                 "verbs", "reads"}


@pytest.fixture
def box(tmp_path):
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    return home, cwd


def _env(home, **extra):
    env = {"HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache"),
           "XDG_STATE_HOME": str(home / ".local" / "state"),
           "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_DATA_HOME": str(home / ".local" / "share"),
           "PATH": "/usr/bin:/bin", "TERM": "dumb"}
    env.update(extra)
    return env


def sh(box, *argv, **extra):
    home, cwd = box
    p = subprocess.run([str(S), *argv], cwd=str(cwd), env=_env(home, **extra),
                       capture_output=True, timeout=60)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def user_file(home, text):
    p = home / ".claude" / "agentik" / "profiles.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def repo_file(cwd, text):
    p = cwd / ".claude" / "agentik" / "config.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def config(box, *words, **extra):
    rc, out, err = sh(box, "describe", "config", "--json", *words, **extra)
    return rc, json.loads(out)


def one(box, key, **extra):
    rc, d = config(box, key, **extra)
    assert rc == 0 and d["ok"] is True, d
    assert len(d["settings"]) == 1, d["settings"]
    return d["settings"][0]


# ---- line 1: describe --json ---------------------------------------------------------------

def test_describe_json(box):
    t0 = time.monotonic()
    rc, out, _ = sh(box, "describe", "--json")
    took = time.monotonic() - t0
    assert rc == 0 and "\x1b" not in out and out.endswith("}\n")
    d = json.loads(out)
    assert DESCRIBE_KEYS <= set(d)
    assert d["schema"] == "agentik.describe/1" and d["ok"] is True and d["tool"] == "session"
    assert len(d["summary"]) < 80 and d["plugin"] == "session@agentik"
    man = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    assert man["repository"] == f"https://github.com/{d['repo']}"     # the manifest's names
    assert d["plugin"] == f"{man['name']}@agentik" and d["version"] == man["version"]
    assert [r["name"] for r in d["reads"]] == ["config", "doctor", "meter", "gate", "unattended"]
    assert [r["kind"] for r in d["reads"]] == ["config", "doctor", "status", "status", "status"]
    assert d["reads"][0]["argv"] == ["describe", "config", "--json"]
    assert d["reads"][1]["argv"] == ["doctor", "--json"]
    assert all(v["top"] is False for v in d["verbs"])
    names = [v["name"] for v in d["verbs"]]
    assert "hook" not in names and names[:3] == ["start", "config", "doctor"]
    assert "describe" in names
    assert {"claude", "git"} <= {n["name"] for n in d["needs"] if n["kind"] == "program"}
    plugins = [n for n in d["needs"] if n["kind"] == "plugin"]
    assert len(plugins) == 3 and all(n["optional"] and n["why"] for n in plugins)
    assert [n["name"] for n in plugins] == [f"{x['name']}@agentik" for x in doctor.SIBLINGS]
    assert took < 1.0


def test_describe_refusals(box):
    assert sh(box, "describe")[0] == 2
    assert "describe --json" in sh(box, "describe")[2]
    assert sh(box, "describe", "nosuch", "--json")[0] == 2


# ---- line 2: an empty HOME ------------------------------------------------------------------

def test_config_empty_home(box):
    home, _ = box
    rc, d = config(box)
    assert rc == 0 and d["schema"] == "agentik.config/1" and d["ok"] is True
    layers = [x["name"] for x in d["layers"]]
    assert layers[:6] == ["default", "user-defaults", "profile", "user", "repo", "local"]
    keys = [s["key"] for s in d["settings"]]
    assert len(keys) == len(set(keys))
    for s in d["settings"]:
        assert set(s) == SETTING_KEYS, s["key"]
        assert set(s["change"]) == {"kind", "command", "path", "block", "note"}
        assert s["value"] == s["default"], s["key"]
        assert not str(s["source"]["path"] or "").startswith(str(home)), s["key"]
        assert s["source"]["layer"] in layers and all(v["layer"] in layers for v in s["values"])
        assert len(s["summary"]) < 100 and not s["summary"].startswith("This setting")
    eff = next(s for s in d["settings"] if s["key"] == "effort")
    assert eff["value"] == "high"
    assert eff["source"] == {"layer": "profile", "path": SHIPPED, "line": 86}
    assert [v["layer"] for v in eff["values"]] == ["default", "profile"]
    assert {"tiers.build.model", "gate.wall", "ceilings.context", "posture"} <= set(keys)
    assert not {"description", "subagents", "window", "models"} & set(keys)


# ---- line 3: a repo file --------------------------------------------------------------------

def test_config_repo_effort(box):
    home, cwd = box
    f = repo_file(cwd, "# a made-up repo\nsession:\n  effort: medium\n")
    s = one(box, "effort")
    assert s["value"] == "medium" and s["default"] == "high"
    assert s["source"] == {"layer": "repo", "path": str(f), "line": 3}
    assert s["change"]["kind"] == "edit" and s["change"]["path"] == str(f)
    assert s["change"]["block"] == "session:\n  effort: medium"
    assert s["live"] is False
    f.unlink()
    s = one(box, "effort")
    assert s["source"] == {"layer": "profile", "path": SHIPPED, "line": 86}
    assert s["change"]["path"] == str(home / ".claude" / "agentik" / "profiles.yaml")


# ---- line 4: a user file --------------------------------------------------------------------

def test_config_user_effort(box):
    home, _ = box
    f = user_file(home, "defaults:\n  effort: max\nprofiles:\n  frontier:\n    effort: low\n")
    s = one(box, "effort")
    assert s["value"] == "low"
    assert s["source"] == {"layer": "user", "path": str(f), "line": 5}
    assert [v["layer"] for v in s["values"]] == ["default", "user-defaults", "profile", "user"]


# ---- line 5: a user tier --------------------------------------------------------------------

def test_config_user_tier(box):
    home, _ = box
    f = user_file(home, "tiers:\n  build: {model: sonnet}\n")
    s = one(box, "tiers.build.model")
    assert s["value"] == "sonnet"
    assert s["source"] == {"layer": "user", "path": str(f), "line": 2}
    assert s["change"]["kind"] == "command"
    assert s["change"]["command"] == "agentik session set tier.build VALUE --save"


# ---- line 6: a flow map, and the gate -------------------------------------------------------

def test_config_ceilings_and_gate(box):
    home, cwd = box
    f = repo_file(cwd, "session:\n  ceilings: {context: 150000, turns: 300}\n")
    s = one(box, "ceilings.context")
    assert s["value"] == 150000 and s["source"] == {"layer": "repo", "path": str(f), "line": 2}
    u = user_file(home, "gate:\n  wall: 900\n")
    s = one(box, "gate.wall")
    assert s["value"] == 900 and s["source"] == {"layer": "user", "path": str(u), "line": 2}


# ---- review 1, R1-F1: a secret's text is in no output of any read the plug adds --------------

SECRET = "s3cr3t-topic-xyz"
SECRET_FILES = {
    "block": f"gate:\n  ntfy_topic: {SECRET}\n",
    "padded": f"gate:\n  ntfy_url: https://ntfy.example.test\n  ntfy_topic: \"  {SECRET}  \"\n",
    "flow": f"gate: {{ntfy_topic: {SECRET}, wall: 900}}\n",
    "profile": f"profiles:\n  frontier:\n    effort: low\ngate:\n  ntfy_topic: '{SECRET}'\n",
    "misplaced": f"defaults:\n  effort: low\n  gate:\n    ntfy_topic: {SECRET}\n",
    "bad-line": f"gate:\n  ntfy_topic {SECRET}\n",
    "bad-flow": f"gate: {{wall: 900, ntfy_topic {SECRET}}}\n",
}
SECRET_READS = (("describe", "--json"), ("describe", "config", "--json"),
                ("describe", "config", "--json", "gate.ntfy_topic"),
                ("describe", "config", "--json", "GATE.NTFY_TOPIC"), ("describe",),
                ("doctor", "--json"), ("status", "--json"), ("gate", "status", "--json"),
                ("unattended", "status", "--json"),
                # build 3, L1: the text form of each read the plug touches withholds it too
                ("doctor",), ("status",), ("gate", "status"), ("unattended", "status"))


@pytest.mark.parametrize("form", sorted(SECRET_FILES))
def test_a_secret_is_in_no_output(box, form):
    home, _ = box
    u = user_file(home, SECRET_FILES[form])
    for extra in ({}, {"CLAUDE_CODE_SESSION_ID": SID}):
        for argv in SECRET_READS:
            rc, out, err = sh(box, *argv, **extra)
            for part in (SECRET, "s3cr3t"):
                assert part not in out and part not in err, (form, argv, extra, out, err)
    rc, d = config(box, "gate.ntfy_topic")
    if form.startswith("bad-"):
        line = 2 if form == "bad-line" else 1      # the file and the line still named
        assert rc == 2 and d["error"]["code"] == "bad_file", d
        assert d["error"]["message"].startswith(f"{u}: line {line}: "), d
        return
    s = d["settings"][0]
    assert s["type"] == "secret" and s["key"] == "gate.ntfy_topic"
    if form == "misplaced":
        assert s["value"] is None and s["change"]["block"] == "gate:\n  ntfy_topic: null"
        return
    assert s["value"] == "(set)" and s["source"]["layer"] == "user"
    assert [v["value"] for v in s["values"]] == [None, "(set)"]
    assert s["change"]["block"] == 'gate:\n  ntfy_topic: "(set)"', s["change"]


# ---- line 7: the session overlay ------------------------------------------------------------

def test_config_session_posture(box):
    home, _ = box
    env = _env(home, CLAUDE_CODE_SESSION_ID=SID)
    ov = resolver.state_dir(env) / "overlays" / f"{SID}.json"
    ov.parent.mkdir(parents=True)
    ov.write_text(json.dumps({"posture": "deny"}))
    s = one(box, "posture", CLAUDE_CODE_SESSION_ID=SID)
    assert s["value"] == "deny"
    assert s["source"] == {"layer": "session", "path": str(ov), "line": None}
    assert s["change"]["command"] == "agentik session set posture VALUE"
    assert s["live"] is True


# ---- line 8: every value is resolve's -------------------------------------------------------

def _leaf(d, key):
    for seg in key.split("."):
        assert isinstance(d, dict), key
        d = d[next(k for k in d if k.lower() == seg)] if any(k.lower() == seg for k in d) \
            else None
    return d


@pytest.mark.parametrize("fixture", ["empty", "files", "scratch"])
def test_values_are_resolves(box, fixture):
    from claude_session import plug
    home, cwd = box
    extra = {}
    if fixture == "files":
        repo_file(cwd, "session:\n  effort: medium\n  ceilings: {context: 150000, turns: 300}\n")
        user_file(home, "defaults:\n  effort: max\nprofiles:\n  frontier:\n    effort: low\n"
                        "tiers:\n  build: {model: sonnet}\ngate:\n  wall: 900\n")
    if fixture == "scratch":
        extra["CLAUDE_SESSION_PROFILE"] = "scratch"
    env = _env(home, **extra)
    d, rc = plug.config_read(str(cwd), env)
    assert rc == 0 and d["settings"]
    r = resolver.resolve(cwd, "unsaved", env, profile=hooks.launch_profile(env))
    g = resolver.gate_config(env)
    for s in d["settings"]:
        if s["key"].startswith("gate."):
            want = g.get(s["key"][5:])
            if s["type"] == "secret":
                want = None if want is None else "(set)"
        else:
            want = _leaf(r.sections["session"], s["key"])
        assert s["value"] == want, s["key"]


# ---- line 9: an unknown key, an unknown word, a bad file ------------------------------------

def test_config_unknowns_and_bad_file(box):
    home, cwd = box
    rc, d = config(box, "nosuch")
    assert rc == 0 and d["ok"] is True and d["settings"] == []
    f = repo_file(cwd, "session:\n  efort: low\n")
    rc, d = config(box)
    assert rc == 0 and len(d["warnings"]) == 1
    w = d["warnings"][0]
    assert w["reason"] == "unknown" and w["path"] == str(f) and w["line"] == 2
    f.unlink()
    u = user_file(home, "defaults:\n\teffort: low\n")
    rc, d = config(box)
    assert rc == 2 and d["ok"] is False and d["error"]["code"] == "bad_file"
    assert str(u) in d["error"]["message"] and "\n" not in d["error"]["message"]


# ---- review 1, R1-F2: a file that cannot be read is `bad_file`, exit 2, never a traceback ------

def _deep(n):
    return "defaults:\n" + "".join("  " * (i + 1) + f"k{i}:\n" for i in range(n)) + \
        "  " * (n + 1) + "leaf: 1\n"


def _unreadable(home, cwd, case):
    """Lay out `case`; give the path the read must name."""
    if case == "user-mode-000":
        p = user_file(home, "defaults:\n  effort: low\n")
        p.chmod(0)
    elif case == "repo-mode-000":
        p = repo_file(cwd, "session:\n  effort: low\n")
        p.chmod(0)
    elif case == "user-folder":
        p = home / ".claude" / "agentik" / "profiles.yaml"
        p.mkdir(parents=True)
    elif case == "repo-folder":
        p = cwd / ".claude" / "agentik" / "config.yaml"
        p.mkdir(parents=True)
    elif case == "overlay-folder":
        p = resolver.state_dir(_env(home)) / "overlays" / f"{SID}.json"
        p.mkdir(parents=True)
    elif case == "user-nested-1200":
        p = user_file(home, _deep(1200))
    elif case == "repo-nested-1200":
        p = repo_file(cwd, "session:\n" + _deep(1200)[len("defaults:\n"):])
    elif case == "user-not-utf-8":
        p = user_file(home, "x")
        p.write_bytes(b"defaults:\n  effort: \xff\xfelow\n")
    else:                                               # not the subset: a tab in the indent
        p = user_file(home, "defaults:\n\teffort: low\n")
    return p


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode 000 file")
@pytest.mark.parametrize("case", ["user-mode-000", "repo-mode-000", "user-folder", "repo-folder",
                                  "overlay-folder", "user-nested-1200", "repo-nested-1200",
                                  "user-not-utf-8", "user-tab"])
def test_a_file_that_cannot_be_read_is_bad_file(box, case):
    home, cwd = box
    p = _unreadable(home, cwd, case)
    try:
        for words in ((), ("effort",)):
            rc, out, err = sh(box, "describe", "config", "--json", *words,
                              CLAUDE_CODE_SESSION_ID=SID)
            assert rc == 2 and "Traceback" not in err and err == "", (case, rc, err)
            d = json.loads(out)
            assert list(d) == ["schema", "ok", "tool", "error"] and d["ok"] is False, d
            e = d["error"]
            assert e["code"] == "bad_file" and e["message"].startswith(f"{p}: "), (case, e)
            assert "\n" not in e["message"] and e["remedy"] is None
    finally:
        if p.is_file():
            p.chmod(0o644)


# ---- build 3, L2: the doctor read with a layer file it cannot read is §5's shape, no traceback

@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode 000 file")
@pytest.mark.parametrize("layer", ["user", "repo", "local"])
@pytest.mark.parametrize("how", ["mode-000", "folder"])
def test_doctor_with_a_file_it_cannot_read(box, layer, how):
    home, cwd = box
    p = {"user": home / ".claude" / "agentik" / "profiles.yaml",
         "repo": cwd / ".claude" / "agentik" / "config.yaml",
         "local": cwd / ".claude" / "agentik" / "config.local.yaml"}[layer]
    p.parent.mkdir(parents=True, exist_ok=True)
    if how == "folder":
        p.mkdir()
    else:
        p.write_text(("defaults:\n" if layer == "user" else "session:\n") + "  effort: low\n")
        p.chmod(0)
    why = "Is a directory" if how == "folder" else "Permission denied"
    try:
        rc, out, err = sh(box, "doctor", "--json")
        assert rc == 2 and "Traceback" not in err, (rc, err)
        d = json.loads(out)
        assert d["schema"] == "agentik.doctor/1" and d["ok"] is True and d["tool"] == "session"
        st = [c["status"] for c in d["checks"]]
        assert d["failed"] == st.count("fail") and d["warned"] == st.count("warn")
        named = [c for c in d["checks"] if c["detail"] == f"{p}: {why}"]
        assert named and all(c["status"] == "fail" for c in named), d["checks"]
        rc_text, text, err = sh(box, "doctor")
        assert rc_text == rc and "Traceback" not in err, (rc_text, err)
        lines = text.splitlines()
        assert any(ln.startswith("FAIL ") and ln.endswith(f" {p}: {why}") for ln in lines), text
        assert lines[-1].startswith("doctor: failing: ")
    finally:
        if p.is_file():
            p.chmod(0o644)


# ---- review 1, R1-F3: every key is unique, of [a-z0-9_-] segments ----------------------------

def test_keys_are_unique_and_a_key_out_of_the_set_is_warned(box):
    home, cwd = box
    u = user_file(home, "defaults:\n  admission:\n    Mode: off\n    mode: on\n"
                        "    a.b: 1\n    a:\n      b: 2\n")
    r = repo_file(cwd, "session:\n  reconcile:\n    Stale: 3\n")
    rc, d = config(box)
    assert rc == 0 and d["ok"] is True
    keys = [s["key"] for s in d["settings"]]
    assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)
    seg = __import__("re").compile(r"[a-z0-9_-]+\Z")
    assert all(seg.match(part) for k in keys for part in k.split(".")), keys
    by = {s["key"]: s for s in d["settings"]}
    assert by["admission.mode"]["value"] == "on" and by["admission.a.b"]["value"] == 2
    assert by["admission.mode"]["source"] == {"layer": "user-defaults", "path": str(u), "line": 4}
    assert {f"priority.levels.s{n}" for n in range(1, 5)} <= set(by)   # S1 to S4, as before
    w = {(x["key"], x["path"], x["line"]) for x in d["warnings"] if x["reason"] == "unknown"}
    assert {("admission.Mode", str(u), 3), ("admission.a.b", str(u), 5),
            ("reconcile.Stale", str(r), 3)} <= w, d["warnings"]
    s = one(box, "admission.mode")
    assert s["value"] == "on"


# ---- line 11: doctor --json -----------------------------------------------------------------

def test_doctor_json(box):
    home, _ = box
    rc, out, _ = sh(box, "doctor", "--json")
    d = json.loads(out)
    assert d["schema"] == "agentik.doctor/1" and d["ok"] is True and d["tool"] == "session"
    st = [c["status"] for c in d["checks"]]
    assert d["failed"] == st.count("fail") and d["warned"] == st.count("warn")
    for c in d["checks"]:
        assert {"name", "status", "detail", "remedy", "ok"} <= set(c)
        assert c["status"] in ("ok", "note", "warn", "fail")
        assert (c["status"] == "fail") == (not c["ok"])
    by = {c["name"]: c for c in d["checks"]}
    assert by["resolved"]["status"] == "note" and by["meter"]["status"] == "note"
    rc_text = sh(box, "doctor")[0]
    assert rc == rc_text
    path = Path(install.launcher_path(_env(home)))
    path.parent.mkdir(parents=True)
    path.write_text(f"#!/bin/sh\nVERSION=2.0.0\nTREE={home / 'gone-tree'}\n")
    d = json.loads(sh(box, "doctor", "--json")[1])
    lau = next(c for c in d["checks"] if c["name"] == "launcher")
    assert lau["status"] == "fail" and lau["remedy"] == "/session:install-cli"


# ---- line 12: the status reads --------------------------------------------------------------

def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


def test_status_meter(box, monkeypatch):
    home, _ = box
    rc, out, err = sh(box, "status", "--json")
    assert rc == 2 and out == "" and err.startswith("no meter for this session")
    env = _env(home, CLAUDE_CODE_SESSION_ID=SID)
    sdir = resolver.session_dir(resolver.state_dir(env), SID)
    sdir.mkdir(parents=True)
    (sdir / "meter.json").write_text(json.dumps({"context": 12, "turns": 3, "zone": "clear"}))
    rc, out, _ = sh(box, "status", "--json", CLAUDE_CODE_SESSION_ID=SID)
    d = json.loads(out)
    assert rc == 0 and list(d)[:2] == ["schema", "ok"]
    assert d["schema"] == "agentik.session.meter/1" and d["ok"] is True
    assert {"context": 12, "turns": 3, "zone": "clear"}.items() <= d.items()


def test_status_gate_and_unattended(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    rc, out, _ = run("gate", "status", "--json")          # the temp state root (conftest)
    d = json.loads(out)
    assert rc == 0 and list(d)[:2] == ["schema", "ok"]
    assert d["schema"] == "agentik.session.gate/1" and "est" in d
    rc, out, _ = run("unattended", "status", "--json")
    assert rc == 0 and out.strip() == "null"


# ---- line 13: nothing written under HOME but the cache -------------------------------------

def _tree(home: Path) -> dict:
    out = {}
    for p in sorted(home.rglob("*")):
        rel = p.relative_to(home)
        if rel.parts[:2] == (".cache", "agentik") or rel.parts == (".cache",):
            continue
        out[str(rel)] = p.read_bytes() if p.is_file() and not p.is_symlink() else None
    return out


def test_reads_write_nothing(box):
    home, cwd = box
    user_file(home, "defaults:\n  effort: max\ntiers:\n  build: {model: sonnet}\n")
    repo_file(cwd, "session:\n  efort: low\n")
    before = _tree(home)
    for argv in (("describe", "--json"), ("describe", "config", "--json"),
                 ("describe", "config", "--json", "effort"),
                 ("describe", "config", "--json", "nosuch"), ("describe",)):
        sh(box, *argv)
    sh(box, "describe", "config", "--json", CLAUDE_CODE_SESSION_ID=SID)
    assert _tree(home) == before
