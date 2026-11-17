"""Row up3s-session-forward: session's `install-cli` moves its command forward only.

R1, `install()` leaves a command `install-cli` wrote whose code stands and whose version is newer
than the tree being placed, and says which version it kept; `force` places anyway; the check is
made again under the lock. R2, `install-cli --force`, and the one line commons' `install_cli`
prints for a kept command. R3, every other caller keeps today's behaviour. R5, the doctor reads a
newer command as newer, a note.

Every case runs in a temp HOME and a temp prefix with plugin copies at made-up versions; never
the real `~/.local`.
"""
import os
import shutil
import subprocess

import pytest

from claude_session import SEMVER, doctor, install
from test_install import _bare, _plugin

NAME = "agentik-session"
NEWER = "2.0.0-alpha.999"
OLDER = "2.0.0-alpha.1"


def _verb(plugin, home, *args):
    return subprocess.run([str(plugin / "bin" / NAME), "install-cli", *args], env=_bare(home),
                          capture_output=True, text=True, timeout=60, cwd=home)


def _version(launcher):
    return install.read_launcher(str(launcher))["version"]


def _listing(root):
    return sorted(os.path.relpath(os.path.join(d, n), root)
                  for d, dirs, files in os.walk(root) for n in dirs + files)


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def plugins(tmp_path):
    """(this tree's plugin, a copy at NEWER, a copy at OLDER)."""
    return (_plugin(tmp_path / "this"), _plugin(tmp_path / "newer", NEWER),
            _plugin(tmp_path / "older", OLDER))


# ---- R1, R2: a newer command is left ---------------------------------------------------------

def test_r2_an_older_tree_leaves_a_newer_command_and_says_so(tmp_path, home, plugins):
    this, newer, _ = plugins
    prefix = tmp_path / "prefix"
    assert _verb(newer, home, "--prefix", str(prefix)).returncode == 0
    launcher, door, akt = prefix / "bin" / NAME, prefix / "bin" / "agentik", prefix / "bin" / "akt"
    door.unlink()                      # no door and no akt: a kept command writes neither back
    akt.unlink()
    before, files = launcher.read_bytes(), _listing(prefix)
    r = _verb(this, home, "--prefix", str(prefix))
    assert (r.returncode, r.stderr) == (0, ""), r
    assert r.stdout == (f"Left {launcher} at {NEWER}, newer than this plugin's {SEMVER}; "
                        "--force places it.\n"), r.stdout
    assert launcher.read_bytes() == before
    assert _listing(prefix) == files   # no tree frozen, none pruned, no link, no door
    assert _version(launcher) == NEWER


def test_r2_the_default_prefix_names_the_command_from_home(home, plugins):
    this, newer, _ = plugins
    assert _verb(newer, home).returncode == 0
    r = _verb(this, home)
    assert (r.returncode, r.stderr) == (0, ""), r
    assert r.stdout == (f"Left ~/.local/bin/{NAME} at {NEWER}, newer than this plugin's {SEMVER}; "
                        "--force places it.\n"), r.stdout
    assert _version(home / ".local" / "bin" / NAME) == NEWER


def test_r2_force_places_this_tree_over_a_newer_command(tmp_path, home, plugins):
    this, newer, _ = plugins
    prefix = tmp_path / "prefix"
    assert _verb(newer, home, "--prefix", str(prefix)).returncode == 0
    r = _verb(this, home, "--force", "--prefix", str(prefix))
    assert r.returncode == 0, r
    assert r.stdout.startswith(f"installed {prefix / 'bin' / NAME} -> "), r.stdout
    assert _version(prefix / "bin" / NAME) == SEMVER


# ---- R1: what is placed as today -------------------------------------------------------------

def test_r1_a_command_older_than_the_tree_is_placed_with_the_path_lines(home, plugins):
    this, _, older = plugins
    assert _verb(older, home).returncode == 0
    r = _verb(this, home)
    assert r.returncode == 0, r
    lines = r.stdout.splitlines()
    bin_dir = home / ".local" / "bin"
    assert lines[0].startswith(f"installed {bin_dir / NAME} -> ") and f"({SEMVER})" in lines[0]
    assert lines[-2:] == [f"{bin_dir} is not on PATH, so this terminal does not find {NAME}; "
                          "this line adds it:", 'export PATH="$HOME/.local/bin:$PATH"'], r.stdout
    assert _version(bin_dir / NAME) == SEMVER


def test_r1_a_newer_command_whose_tree_is_gone_is_placed(tmp_path, home, plugins):
    this, newer, _ = plugins
    prefix = tmp_path / "prefix"
    assert _verb(newer, home, "--prefix", str(prefix)).returncode == 0
    shutil.rmtree(install.read_launcher(str(prefix / "bin" / NAME))["tree"])
    r = _verb(this, home, "--prefix", str(prefix))
    assert r.returncode == 0 and r.stdout.startswith("installed "), r
    assert _version(prefix / "bin" / NAME) == SEMVER


def test_r1_a_newer_file_install_cli_did_not_write_is_placed(tmp_path, home, plugins):
    this, newer, _ = plugins
    prefix = tmp_path / "prefix"
    assert _verb(newer, home, "--prefix", str(prefix)).returncode == 0
    launcher = prefix / "bin" / NAME
    tree = install.read_launcher(str(launcher))["tree"]
    launcher.write_text(f"#!/bin/sh\n# a hand's own\nVERSION={NEWER}\nTREE={tree}\n")
    r = _verb(this, home, "--prefix", str(prefix))
    assert r.returncode == 0 and r.stdout.startswith("installed "), r
    assert _version(launcher) == SEMVER


def test_r1_install_returns_kept_and_force_places(tmp_path, home, plugins):
    _, newer, _ = plugins
    prefix = tmp_path / "prefix"
    assert _verb(newer, home, "--prefix", str(prefix)).returncode == 0
    done = install.install(str(prefix), _bare(home))
    assert done["kept"] == NEWER and done["tree"] is None and done["pruned"] == [], done
    assert done["version"] == SEMVER and done["link"] is None
    done = install.install(str(prefix), _bare(home), force=True)
    assert done["kept"] is None and done["tree"], done
    assert _version(prefix / "bin" / NAME) == SEMVER


def test_r1_the_check_is_made_again_under_the_lock(tmp_path, home, monkeypatch):
    prefix = tmp_path / "prefix"
    seen = []

    def ahead(path, share):
        seen.append(path)
        return None if len(seen) == 1 else NEWER     # a newer command lands while we wait
    monkeypatch.setattr(install, "_ahead", ahead)
    done = install.install(str(prefix), _bare(home))
    assert len(seen) == 2 and done["kept"] == NEWER, (seen, done)
    assert not (prefix / "bin" / NAME).exists()


# ---- R3: the refresh is as today -------------------------------------------------------------

def test_r3_the_refresh_leaves_a_newer_command_and_moves_an_older_one(tmp_path, plugins):
    _, newer, older = plugins
    # the refresh runs only for the plugin Claude Code named: this module's own
    lib = os.path.dirname(os.path.dirname(os.path.realpath(install.__file__)))
    for placed, after in ((newer, NEWER), (older, SEMVER)):
        home = tmp_path / ("home-" + after)
        home.mkdir()
        launcher = home / ".local" / "bin" / NAME
        assert _verb(placed, home).returncode == 0
        assert install._behind(str(launcher)) == (after == SEMVER)
        assert install.refresh(_bare(home, CLAUDE_PLUGIN_ROOT=os.path.dirname(lib))) is None
        assert _version(launcher) == after


# ---- R5: the doctor reads newer as newer -----------------------------------------------------

@pytest.mark.parametrize("version,status,word", [(NEWER, "note", "newer than"),
                                                  (OLDER, "warn", "older than"),
                                                  (SEMVER, "ok", None)])
def test_r5_the_doctor_reads_newer_as_a_note_and_older_as_older(home, version, status, word):
    tree = home / "tree"
    tree.mkdir()
    launcher = home / ".local" / "bin" / NAME
    launcher.parent.mkdir(parents=True)
    launcher.write_text(f"#!/bin/sh\nVERSION={version}\nTREE={tree}\n")
    c = doctor._check_launcher({"HOME": str(home)}, None)
    assert (c.ok, c.status) == (True, status), c
    if word:
        assert f"{launcher} is {version}, {word} the plugin's {SEMVER}" in c.detail, c.detail
    else:
        assert c.detail == f"{version} at {launcher}"
    assert ("older than" in c.detail) == (version == OLDER)
