"""Packet akt-run: `run`'s default prompt and model (R1), the no-setup line (R2, R2a), `run
--dry-run` and the `akt` link (R3). No test starts `claude` or a chain: `--dry-run`, a stub
`claude` and the launcher's TTY refusal alone. Every test runs under its own temp home, state
root and repo (the made-up repo `crate`); none reads the live state or home.
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from test_install import BARE, OLD, _bins, _plugin, _session_start, _verb

ROOT = Path(__file__).resolve().parents[1]
PROMPT = "Read the newest charter under history/sittings and act from its Next act."
MODEL = "claude-fable-5-2"
NO_SETUP = "no agentik setup found here"
MAKE_ONE = 'agentik session charter open "<goal>"'


def _git_init(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)


@pytest.fixture
def box(tmp_path):
    """A temp home and state root, a stub `claude` first on PATH, and three folders: `crate`
    (a git repo with history/sittings/), `bare` (a git repo without) and `loose` (no repo)."""
    home, stubs = tmp_path / "home", tmp_path / "stubs"
    stubs.mkdir()
    home.mkdir()
    (stubs / "claude").write_text("#!/bin/sh\nexit 0\n")
    (stubs / "claude").chmod(0o755)
    crate, bare, loose = tmp_path / "crate", tmp_path / "bare", tmp_path / "loose"
    for d in (crate, bare, loose):
        d.mkdir()
    _git_init(crate)
    _git_init(bare)
    (crate / "history" / "sittings").mkdir(parents=True)
    env = {"HOME": str(home), "XDG_STATE_HOME": str(tmp_path / "state"),
           "PATH": f"{stubs}{os.pathsep}{BARE}", "PYTHONPATH": str(ROOT / "plugin" / "lib"),
           "PYTHONDONTWRITEBYTECODE": "1", "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    return {"env": env, "crate": crate, "bare": bare, "loose": loose, "stubs": stubs,
            "home": home, "tmp": tmp_path}


def _run(box, cwd, *argv):
    p = subprocess.run([sys.executable, "-m", "claude_session", *argv], cwd=cwd, env=box["env"],
                       capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout, p.stderr


def _argv(out):
    """The dry run's command: its words after the env assignments."""
    words = shlex.split(out.strip().splitlines()[-1])
    while words and "=" in words[0] and not words[0].startswith("/"):
        words.pop(0)
    return words


# ---- R1: the defaults ---------------------------------------------------------------------

def test_akt_1_bare_dry_run_sends_the_default_model_and_prompt(box):
    rc, out, err = _run(box, box["crate"], "run", "--dry-run")
    assert rc == 0, err
    argv = _argv(out)
    assert argv[0].endswith("claude") and argv[1] == "--session-id"
    assert argv[-3:] == ["--model", MODEL, PROMPT]
    assert "CLAUDE_SESSION_CHAIN=crate-none" in out


def test_akt_2_a_given_model_or_prompt_wins(box):
    rc, out, err = _run(box, box["crate"], "run", "--dry-run", "--", "--model", "opus")
    assert rc == 0, err
    assert _argv(out)[3:] == ["--model", "opus", PROMPT]
    rc, out, err = _run(box, box["crate"], "run", "--dry-run", "--", "do X")
    assert rc == 0, err
    assert _argv(out)[3:] == ["--model", MODEL, "do X"]
    rc, out, err = _run(box, box["crate"], "run", "--dry-run", "--", "--model=opus", "do X")
    assert rc == 0, err
    assert _argv(out)[3:] == ["--model=opus", "do X"]


def test_akt_2_a_list_option_that_would_swallow_the_prompt_is_still_refused(box):
    rc, out, err = _run(box, box["crate"], "run", "--dry-run", "--", "--allowedTools", "Bash")
    assert rc == 2 and out == "", (out, err)
    assert len(err.splitlines()) == 1 and "first prompt" in err


# ---- R2, R2a: the no-setup line -----------------------------------------------------------

@pytest.mark.parametrize("where", ["bare", "loose"])
@pytest.mark.parametrize("dry", [[], ["--dry-run"]])
def test_akt_3_no_setup_refuses_the_default_prompt(box, where, dry):
    rc, out, err = _run(box, box[where], "run", *dry)
    assert rc == 2 and out == "", (out, err)
    assert len(err.splitlines()) == 1, err
    assert NO_SETUP in err and MAKE_ONE in err and "run.prompt" in err
    assert "init" not in err


@pytest.mark.parametrize("where", ["bare", "loose"])
def test_akt_3_a_given_prompt_is_not_checked(box, where):
    rc, out, err = _run(box, box[where], "run", "--dry-run", "--", "do X")
    assert rc == 0, err
    assert _argv(out)[-1] == "do X" and NO_SETUP not in err


def test_akt_3_bare_run_in_a_setup_repo_reaches_the_tty_refusal(box):
    rc, _, err = _run(box, box["crate"], "run")
    assert rc == 2 and "TTY" in err and NO_SETUP not in err


# ---- R1: the settings ---------------------------------------------------------------------

def test_akt_4_the_repo_layer_moves_the_defaults_and_describe_lists_them(box):
    d = box["crate"] / ".claude" / "agentik"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text('session:\n  run: {prompt: "Go on.", model: opus}\n')
    rc, out, err = _run(box, box["crate"], "run", "--dry-run")
    assert rc == 0, err
    assert _argv(out)[3:] == ["--model", "opus", "Go on."]
    rc, out, err = _run(box, box["crate"], "describe", "config", "--json")
    assert rc == 0, err
    got = {s["key"]: s for s in json.loads(out)["settings"]}
    assert got["run.prompt"]["value"] == "Go on." and got["run.prompt"]["default"] == PROMPT
    assert got["run.model"]["value"] == "opus" and got["run.model"]["default"] == MODEL
    assert got["run.prompt"]["source"]["layer"] == "repo"


def test_akt_4_the_shipped_defaults_are_listed(box):
    rc, out, err = _run(box, box["loose"], "describe", "config", "--json")
    assert rc == 0, err
    got = {s["key"]: s["value"] for s in json.loads(out)["settings"]}
    assert got["run.prompt"] == PROMPT and got["run.model"] == MODEL


def test_akt_4_a_null_model_adds_none_and_the_profile_applies(box):
    d = box["crate"] / ".claude" / "agentik"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text("session:\n  run: {model: null}\n")
    rc, out, err = _run(box, box["crate"], "run", "--dry-run", "--", "do X")
    assert rc == 0, err
    assert _argv(out)[3:] == ["--model", "opus", "--effort", "high", "do X"]


@pytest.mark.parametrize("text", ['session:\n  run: {prompt: ""}\n',
                                  "session:\n  run: {colour: red}\n",
                                  "session:\n  run: {model: 3}\n"])
def test_akt_4_a_bad_run_block_is_refused(box, text):
    d = box["crate"] / ".claude" / "agentik"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(text)
    rc, out, err = _run(box, box["crate"], "run", "--dry-run")
    assert rc == 2 and out == "" and "run" in err, (out, err)


# ---- R3: the `akt` link -------------------------------------------------------------------

def _akt_env(box):
    return {"HOME": str(box["home"]), "PATH": f"{box['stubs']}{os.pathsep}{BARE}",
            "GIT_CEILING_DIRECTORIES": str(box["tmp"])}


def test_akt_5_install_cli_writes_the_link_and_akt_dry_run_prints_r1s_command(box):
    plugin = _plugin(box["tmp"])
    r = _verb(plugin, box["home"])
    assert r.returncode == 0, r.stderr
    akt = _bins(box["home"]) / "akt"
    assert os.path.islink(akt) and os.readlink(akt) == "agentik-session"
    d = subprocess.run([str(akt), "--dry-run"], cwd=box["crate"], env=_akt_env(box),
                       capture_output=True, text=True, timeout=60)
    assert d.returncode == 0, d.stderr
    assert _argv(d.stdout)[-3:] == ["--model", MODEL, PROMPT]
    # Every other word goes to claude, and the plain form reaches `run` (its TTY refusal).
    d = subprocess.run([str(akt), "--model", "opus"], cwd=box["crate"], env=_akt_env(box),
                       capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert d.returncode == 2 and "agentik-session run:" in d.stderr and "TTY" in d.stderr
    d = subprocess.run([str(akt)], cwd=box["loose"], env=_akt_env(box),
                       capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert d.returncode == 2 and NO_SETUP in d.stderr


def test_akt_5_a_second_install_changes_nothing(box):
    plugin = _plugin(box["tmp"])
    assert _verb(plugin, box["home"]).returncode == 0
    akt = _bins(box["home"]) / "akt"
    before = os.lstat(akt)
    r = _verb(plugin, box["home"])
    assert r.returncode == 0, r.stderr
    after = os.lstat(akt)
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert os.readlink(akt) == "agentik-session" and str(akt) not in r.stdout


@pytest.mark.parametrize("how", ["file", "other-link"])
def test_akt_5_what_a_hand_put_at_akt_is_kept(box, how):
    bins = _bins(box["home"])
    bins.mkdir(parents=True)
    akt = bins / "akt"
    if how == "file":
        akt.write_text("#!/bin/sh\necho mine\n")
    else:
        os.symlink("/usr/bin/true", akt)
    r = _verb(_plugin(box["tmp"]), box["home"])
    assert r.returncode == 0, r.stderr
    if how == "file":
        assert not os.path.islink(akt) and akt.read_text() == "#!/bin/sh\necho mine\n"
    else:
        assert os.readlink(akt) == "/usr/bin/true"
    said = [l for l in r.stdout.splitlines() if str(akt) in l]
    assert len(said) == 1 and "kept" in said[0], r.stdout


@pytest.mark.parametrize("standing", [True, False])
def test_akt_5_the_refresh_keeps_a_standing_link_and_writes_none_where_removed(box, standing):
    home = box["home"]
    assert _verb(_plugin(box["tmp"] / "old", OLD), home).returncode == 0
    akt = _bins(home) / "akt"
    if not standing:
        akt.unlink()
    r = _session_start(_plugin(box["tmp"] / "new", "2.0.0-alpha.40"), home)
    assert r.returncode == 0, r.stderr
    assert "VERSION=2.0.0-alpha.40\n" in (_bins(home) / "agentik-session").read_text()
    if standing:
        assert os.readlink(akt) == "agentik-session"
    else:
        assert not os.path.lexists(akt)


# ---- R3: uninstall takes it back ----------------------------------------------------------

def test_akt_6_uninstall_takes_the_link_back(box):
    """Commons' `uninstall` plans a link in bin/ whose text is the tool's name (its `_plan`).
    Where this repo's copy of the canonical module carries `uninstall`, it is called in its dry
    form; else the rule it reads is checked on the link."""
    prefix = box["tmp"] / "prefix"
    r = subprocess.run([str(_plugin(box["tmp"]) / "bin" / "agentik-session"), "install-cli",
                        "--prefix", str(prefix)], env={"HOME": str(box["home"]), "PATH": BARE},
                       capture_output=True, text=True, timeout=60, cwd=box["home"])
    assert r.returncode == 0, r.stderr
    akt = prefix / "bin" / "akt"
    assert os.readlink(akt) == "agentik-session"
    sys.path.insert(0, str(ROOT / "plugin" / "lib"))
    try:
        import agentik_install
    finally:
        sys.path.pop(0)
    if not hasattr(agentik_install, "uninstall"):
        return
    plan = agentik_install.uninstall("agentik-session", str(prefix), dry=True)
    assert (str(akt), "link", "would remove") in plan, plan
