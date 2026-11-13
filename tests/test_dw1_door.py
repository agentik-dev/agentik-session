"""Packet dw1s: this tool's install writes the shared `agentik` door forward only, as the canonical
module does: none or an older one there, written; an equal or newer one, left byte for byte; a
link, or a VERSION line here or there that does not read as a version, left alone with one line.

Every case runs in a temp HOME; the verb's under the bare env, with a copy of this tree's plugin.
Never this tree's plugin, never the real `~/.local`.
"""
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BARE = "/usr/bin:/bin"
DOOR = ROOT / "plugin" / "bin" / "agentik"


def _plugin(tmp_path, version=None):
    """This tree's plugin as a marketplace would lay it out, its version as given."""
    import json
    p = tmp_path / "cache" / "session" / "v"
    shutil.copytree(ROOT / "plugin", p, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"))
    if version:
        m = p / ".claude-plugin" / "plugin.json"
        data = json.loads(m.read_text())
        data["version"] = version
        m.write_text(json.dumps(data))
    return p


def _bare(home, **extra):
    return {"HOME": str(home), "PATH": BARE, **extra}


def _verb(plugin, home):
    return subprocess.run([str(plugin / "bin" / "agentik-session"), "install-cli"], env=_bare(home),
                          capture_output=True, text=True, timeout=60, cwd=home)


def _bins(home):
    return home / ".local" / "bin"


def _versioned(text, version):
    """The door's text with its one VERSION= line set to `version`, or gone for None."""
    assert len(re.findall(r"^VERSION=.*$", text, re.M)) == 1
    if version is None:
        return re.sub(r"^VERSION=.*\n", "", text, flags=re.M)
    return re.sub(r"^VERSION=.*$", "VERSION=%s" % version, text, flags=re.M)


def _ours():
    return re.search(r"^VERSION=(.*)$", DOOR.read_text(), re.M).group(1)


def _put(path, text, mode=0o755):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


def _said(r):
    """What install-cli printed under its `installed ...` line."""
    lines = r.stdout.splitlines()
    assert lines and lines[0].startswith("installed "), r.stdout + r.stderr
    return lines[1:]


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


# ---- acceptance 1 and 3: the verb ---------------------------------------------------------

def test_dw1_install_cli_leaves_a_newer_door_byte_for_byte(tmp_path, home):
    plugin = _plugin(tmp_path)
    door = _bins(home) / "agentik"
    newer = _versioned(DOOR.read_text(), "0.2.0")
    _put(door, newer)
    r = _verb(plugin, home)
    assert r.returncode == 0, r.stderr
    assert door.read_text() == newer and "VERSION=0.2.0\n" in door.read_text()
    assert not [line for line in _said(r) if "door" in line], r.stdout
    # the rest of the install as before
    from claude_session import install
    assert os.readlink(_bins(home) / install.OLD_NAME) == "agentik-session"
    assert os.access(_bins(home) / "agentik-session", os.X_OK)


def test_dw1_install_cli_writes_a_door_where_none_is(tmp_path, home):
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    door = _bins(home) / "agentik"
    assert door.read_bytes() == DOOR.read_bytes()
    assert stat.S_IMODE(door.lstat().st_mode) == 0o755
    assert not [line for line in _said(r) if "door" in line], r.stdout


def test_dw1_install_cli_moves_an_older_door_forward(tmp_path, home):
    door = _bins(home) / "agentik"
    _put(door, _versioned(DOOR.read_text(), "0.0.9"), 0o700)
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    assert door.read_bytes() == DOOR.read_bytes()
    assert stat.S_IMODE(door.lstat().st_mode) == 0o755


# ---- acceptance 4: what is left alone, and said -------------------------------------------

def test_dw1_install_cli_leaves_a_link_and_its_target(tmp_path, home):
    target = tmp_path / "elsewhere" / "agentik"
    older = _versioned(DOOR.read_text(), "0.0.9")     # followed, it would be written
    _put(target, older)
    door = _bins(home) / "agentik"
    door.parent.mkdir(parents=True)
    door.symlink_to(target)
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    assert door.is_symlink() and os.readlink(door) == str(target)
    assert target.read_text() == older
    assert _said(r)[:1] == ["the door %s is a link; left alone" % door], r.stdout


def test_dw1_install_cli_leaves_a_door_with_no_version(tmp_path, home):
    door = _bins(home) / "agentik"
    bare = _versioned(DOOR.read_text(), None)
    _put(door, bare)
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    assert door.read_text() == bare
    assert _said(r)[:1] == ["the door %s has no version to compare (None there, %s here); left alone"
                            % (door, _ours())], r.stdout


# ---- review 1: a door that is not a file, a byte the locale cannot print ------------------

def test_dw1_install_cli_leaves_a_fifo_at_the_door_and_never_opens_it(tmp_path, home):
    """F1: a FIFO there is never opened, so the install cannot block on it."""
    door = _bins(home) / "agentik"
    door.parent.mkdir(parents=True)
    os.mkfifo(str(door))
    plugin = _plugin(tmp_path)
    p = subprocess.Popen([str(plugin / "bin" / "agentik-session"), "install-cli"], env=_bare(home),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=home,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        pytest.fail("install-cli hung on a FIFO at the door's path")
    r = subprocess.CompletedProcess(p.args, p.returncode, out, err)
    assert r.returncode == 0, r.stderr
    assert stat.S_ISFIFO(door.lstat().st_mode)
    assert _said(r)[:1] == ["the door %s has no version to compare (None there, %s here); left alone"
                            % (door, _ours())], r.stdout
    from claude_session import install
    assert os.readlink(_bins(home) / install.OLD_NAME) == "agentik-session"
    assert os.access(_bins(home) / "agentik-session", os.X_OK)


def test_dw1_install_cli_says_a_byte_in_the_door_escaped(tmp_path, home):
    """F2: a VERSION value ending in byte 0xff, under a UTF-8 locale: the line shows it escaped."""
    door = _bins(home) / "agentik"
    door.parent.mkdir(parents=True)
    body = _versioned(DOOR.read_text(), "0.2.0").encode().replace(b"VERSION=0.2.0\n", b"VERSION=0.2.0\xff\n")
    door.write_bytes(body)
    door.chmod(0o755)
    r = subprocess.run([str(_plugin(tmp_path) / "bin" / "agentik-session"), "install-cli"],
                       env=_bare(home, LANG="en_US.UTF-8"), capture_output=True, timeout=60, cwd=home)
    out, err = r.stdout.decode("utf-8", "backslashreplace"), r.stderr.decode("utf-8", "backslashreplace")
    assert r.returncode == 0 and "Traceback" not in err, err
    assert door.read_bytes() == body
    said = out.splitlines()[1:2]
    assert said == ["the door %s has no version to compare (0.2.0\\xff there, %s here); left alone"
                    % (door, _ours())], out


# ---- acceptance 2: the SessionStart refresh ------------------------------------------------

def test_dw1_refresh_moves_the_launcher_and_leaves_a_newer_door(tmp_path, home):
    plugin = _plugin(tmp_path, "2.0.0-alpha.40")
    assert _verb(plugin, home).returncode == 0
    tool = _bins(home) / "agentik-session"
    tool.write_text(tool.read_text().replace("VERSION=2.0.0-alpha.40\n", "VERSION=2.0.0-alpha.39\n"))
    assert "VERSION=2.0.0-alpha.39\n" in tool.read_text()
    door = _bins(home) / "agentik"
    newer = _versioned(DOOR.read_text(), "0.2.0")
    _put(door, newer)
    code = ("import os, sys; sys.path.insert(0, %r); from claude_session import install; "
            "print(repr(install.refresh(dict(os.environ))))" % str(plugin / "lib"))
    r = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=home, capture_output=True, text=True,
                       timeout=60, env=_bare(home, CLAUDE_PLUGIN_ROOT=str(plugin)))
    assert (r.returncode, r.stdout) == (0, "None\n"), r.stderr
    assert "VERSION=2.0.0-alpha.40\n" in tool.read_text()
    assert door.read_text() == newer


# ---- acceptance 5: one behaviour with the canonical module --------------------------------

def _case(where, name):
    """Lay out one case under `where`: the door `here` (this copy) and what is at `there`."""
    text = DOOR.read_text()
    here, there = where / "here" / "agentik", where / "bin" / "agentik"
    _put(here, text if name != "no line here" else _versioned(text, None))
    there.parent.mkdir(parents=True)      # as `_locked_install` makes it before the door
    if name == "older" or name == "no line here":
        _put(there, _versioned(text, "0.0.9"), 0o700)
    elif name == "equal, other bytes":
        _put(there, text + "# a hand's line\n", 0o700)
    elif name == "newer":
        _put(there, _versioned(text, "0.2.0"), 0o700)
    elif name == "no line there":
        _put(there, _versioned(text, None), 0o700)
    elif name == "a link":
        _put(where / "target", _versioned(text, "0.0.9"), 0o700)
        there.symlink_to(where / "target")
    return there, here


def _seen(where, there):
    """The case's files afterwards, paths relative to `where`."""
    if there.is_symlink():
        return ("link", os.readlink(there).replace(str(where), "<w>"), (where / "target").read_bytes())
    if not there.exists():
        return ("none",)
    return ("file", there.read_bytes(), stat.S_IMODE(there.lstat().st_mode))


CASES = {
    # name: what this module's _door does, None for written
    "none": ("written", None),
    "older": ("written", None),
    "equal, other bytes": ("kept", None),
    "newer": ("kept", None),
    "no line there": ("kept", "the door <there> has no version to compare (None there, {ours} here); left alone"),
    "no line here": ("kept", "the door <there> has no version to compare (0.0.9 there, None here); left alone"),
    "a link": ("kept", "the door <there> is a link; left alone"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_dw1_door_matches_the_canonical_module(tmp_path, name):
    import agentik_install
    from claude_session import install
    out = {}
    for label, mod in (("session", install), ("canonical", agentik_install)):
        where = tmp_path / label
        there, here = _case(where, name)
        before = _seen(where, there)
        said = mod._door(str(there), str(here))
        out[label] = (_seen(where, there), said and said.replace(str(there), "<there>"))
        if label == "session":
            fate, line = CASES[name]
            if fate == "written":
                assert out[label][0] == ("file", DOOR.read_bytes(), 0o755)
            else:
                assert out[label][0] == before
            assert out[label][1] == (line and line.format(ours=_ours()))
    assert out["session"] == out["canonical"]
