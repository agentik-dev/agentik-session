"""Row is1-old-name: a person's own file at the old name (`install.OLD_NAME`) survives
`install-cli` and the SessionStart refresh. The old name's link is written only where a link of
ours (its text `agentik-session`) already stands in the bin folder, as the canonical `_old_link`
refreshes one; a regular file of that name, or a link that is not ours, is left byte for byte,
and a new machine gets none. The install's line says `<bin>/<old name> links to it` only where
the link was written.

Every case runs in a temp HOME or prefix with a copy of this tree's plugin; never the real
`~/.local`.
"""
import json
import os
import subprocess

from claude_session.install import OLD_NAME
from test_ak10d_launcher import _canonical
from test_install import (NEW, OLD, _bare, _bins, _plugin, _session_start, _version)

NAME = "agentik-session"
MINE = '#!/bin/sh\n# mine\nexec claude --model opus "$@"\n'


def _verb(plugin, home, *args):
    return subprocess.run([str(plugin / "bin" / NAME), "install-cli", *args], env=_bare(home),
                          capture_output=True, text=True, timeout=60, cwd=home)


def _home(tmp_path):
    home = tmp_path / "home"
    _bins(home).mkdir(parents=True)
    return home


def _mine(bin_dir):
    """A person's own script at the old name: (path, its bytes, its mode)."""
    path = bin_dir / OLD_NAME
    path.write_text(MINE)
    path.chmod(0o750)
    return path, path.read_bytes(), os.lstat(path).st_mode


def _first(r):
    lines = r.stdout.splitlines()
    assert lines and lines[0].startswith("installed "), r.stdout + r.stderr
    return lines[0]


# ---- R1, R4: install-cli ------------------------------------------------------------------

def test_is1_install_cli_keeps_a_persons_own_file_byte_for_byte(tmp_path):
    home = _home(tmp_path)
    path, data, mode = _mine(_bins(home))
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    assert not os.path.islink(path) and path.read_bytes() == data and os.lstat(path).st_mode == mode
    assert "links to it" not in _first(r) and OLD_NAME not in r.stdout, r.stdout
    assert os.access(_bins(home) / NAME, os.X_OK)


def test_is1_install_cli_keeps_a_link_that_is_not_ours(tmp_path):
    home = _home(tmp_path)
    theirs = tmp_path / "elsewhere" / "my-session"
    theirs.parent.mkdir()
    theirs.write_text(MINE)
    for text in (str(theirs), "my-session", "agentik-session-old"):
        path = _bins(home) / OLD_NAME
        if os.path.lexists(path):
            path.unlink()
        os.symlink(text, path)
        seen = os.lstat(path)
        r = _verb(_plugin(tmp_path / text.replace("/", "_")), home)
        assert r.returncode == 0, r.stderr
        assert os.readlink(path) == text and os.lstat(path).st_ino == seen.st_ino, text
        assert "links to it" not in _first(r), r.stdout


def test_is1_install_cli_refreshes_a_standing_link_of_ours(tmp_path):
    home = _home(tmp_path)
    path = _bins(home) / OLD_NAME
    os.symlink(NAME, path)
    r = _verb(_plugin(tmp_path, NEW), home)
    assert r.returncode == 0, r.stderr
    assert os.readlink(path) == NAME
    assert _first(r).split("; ")[1] == "%s links to it" % path, r.stdout
    assert _version(path, home) == NEW              # it reaches the new launcher


def test_is1_a_new_prefix_gets_no_old_name(tmp_path):
    home, prefix = _home(tmp_path), tmp_path / "prefix"
    r = _verb(_plugin(tmp_path), home, "--prefix", str(prefix))
    assert r.returncode == 0, r.stderr
    assert not os.path.lexists(prefix / "bin" / OLD_NAME)
    assert os.access(prefix / "bin" / NAME, os.X_OK) and os.readlink(prefix / "bin" / "akt") == NAME
    first = _first(r)
    assert "links to it" not in first and first.endswith("; %s" % (prefix / "bin" / "agentik")), first
    from claude_session import install
    assert install._old_link(str(prefix / "bin")) is None


def test_is1_old_link_reads_ours_alone(tmp_path):
    from claude_session import install
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    path = bin_dir / OLD_NAME
    assert install._old_link(str(bin_dir)) is None             # none there
    path.write_text(MINE)
    assert install._old_link(str(bin_dir)) is None             # a regular file
    path.unlink()
    os.symlink("/elsewhere/" + OLD_NAME, path)
    assert install._old_link(str(bin_dir)) is None             # a link that is not ours
    path.unlink()
    os.symlink(NAME, path)                                     # ours, dangling or not
    assert install._old_link(str(bin_dir)) == str(path)


# ---- R3: the SessionStart refresh ---------------------------------------------------------

def test_is1_the_refresh_keeps_a_persons_own_file(tmp_path):
    home = _home(tmp_path)
    path, data, mode = _mine(_bins(home))
    assert _verb(_plugin(tmp_path / "old", OLD), home).returncode == 0
    tool = _bins(home) / NAME
    r = _session_start(_plugin(tmp_path / "new", NEW), home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert "VERSION=%s\n" % NEW in tool.read_text() and _version(tool, home) == NEW
    assert not os.path.islink(path) and path.read_bytes() == data and os.lstat(path).st_mode == mode


def test_is1_the_refresh_keeps_a_standing_link_of_ours_and_writes_none(tmp_path):
    for standing in (True, False):
        home = _home(tmp_path / str(standing))
        path = _bins(home) / OLD_NAME
        if standing:
            os.symlink(NAME, path)
        assert _verb(_plugin(tmp_path / str(standing) / "old", OLD), home).returncode == 0
        r = _session_start(_plugin(tmp_path / str(standing) / "new", NEW), home)
        assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
        assert _version(_bins(home) / NAME, home) == NEW
        if standing:
            assert os.readlink(path) == NAME and _version(path, home) == NEW
        else:
            assert not os.path.lexists(path)


# ---- R5: the canonical uninstall takes back our link alone --------------------------------

def test_is1_uninstall_plans_our_link_never_a_persons_file(tmp_path):
    canonical = _canonical()
    for kind in ("file", "theirs", "ours"):
        home, prefix = _home(tmp_path / kind), tmp_path / kind / "prefix"
        bin_dir = prefix / "bin"
        bin_dir.mkdir(parents=True)
        path = bin_dir / OLD_NAME
        if kind == "file":
            path.write_text(MINE)
        else:
            os.symlink(NAME if kind == "ours" else "/elsewhere/" + OLD_NAME, path)
        assert _verb(_plugin(tmp_path / kind), home, "--prefix", str(prefix)).returncode == 0
        plan = canonical.uninstall(NAME, str(prefix), dry=True)
        planned = [row for row in plan if row[0] == str(path)]
        assert planned == ([(str(path), "link", "would remove")] if kind == "ours" else []), plan
