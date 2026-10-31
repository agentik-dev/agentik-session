"""`make install` (ADV6-3): a frozen copy of the package, run with `-P`, never the cwd's tree.

Every test runs the install in a temp git repo (a copy of this tree's Makefile, wrapper and
package, committed) into a temp HOME: never this tree, never the real `~/.local`.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = "plugin/lib/claude_session"
MANIFEST = "plugin/.claude-plugin/plugin.json"
DECOY = "import sys\nprint('DECOY')\nsys.exit(7)\n"
# The launcher `make install` writes runs `python -P`, which is 3.11; sc3 moves it. Until then
# the install's own steps run under the floor, and what runs the launcher waits for 3.11.
RUNS_P = sys.version_info >= (3, 11)


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    for f in ("Makefile", "install-wrapper.sh"):
        shutil.copy2(ROOT / f, r / f)
    shutil.copytree(ROOT / "scripts", r / "scripts")       # the install's prune-trees (F8)
    shutil.copytree(ROOT / "plugin" / "lib", r / "plugin" / "lib",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (r / "plugin" / ".claude-plugin").mkdir()
    shutil.copy2(ROOT / MANIFEST, r / MANIFEST)
    (r / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    _git(r, "init", "-q")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    return r


def _env(home, **extra):
    """A temp HOME, and stubs for `claude` and the tool's two names first on PATH: an
    install that shells out to any (doctor) never reaches the real ones."""
    stubs = home / "stubs"
    stubs.mkdir(parents=True, exist_ok=True)
    for name in ("claude", "agentik-session", "claude-session"):
        (stubs / name).write_text("#!/bin/sh\nexit 0\n")
        (stubs / name).chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MAKE", "MFLAGS"))}
    env.update(HOME=str(home), XDG_STATE_HOME=str(home / "state"),
               PATH=f"{stubs}{os.pathsep}{env.get('PATH', '')}", **extra)
    return env


def _install(repo, home, python=sys.executable):
    return subprocess.run(["make", "-s", "install", f"PYTHON={python}", "DOCTOR=0"],
                          cwd=repo, env=_env(home), capture_output=True, text=True, timeout=60)


def _tree(repo):
    """The frozen tree's name, as the Makefile derives it from plugin/lib and plugin.json."""
    both = subprocess.run(["git", "rev-parse", "HEAD:plugin/lib", "HEAD:" + MANIFEST], cwd=repo,
                          capture_output=True, text=True, check=True).stdout
    return subprocess.run(["git", "hash-object", "--stdin"], cwd=repo, input=both,
                          capture_output=True, text=True, check=True).stdout.strip()


def _share(home):
    return home / ".local" / "share" / "agentik-session"


@pytest.mark.skipif(not RUNS_P, reason="the baked launcher's -P is 3.11 (sc3 moves it)")
def test_hook_runs_installed_code_not_cwd(repo, tmp_path):
    home = tmp_path / "home"
    r = _install(repo, home)
    assert r.returncode == 0, r.stderr
    tree = _tree(repo)
    wrapper = (home / ".local" / "bin" / "agentik-session").read_text()
    assert f'CODE="{_share(home) / tree}"' in wrapper
    # the venv's link in its resolved directory, never the link's target (ADV10-5)
    baked = os.path.join(os.path.realpath(os.path.dirname(sys.executable)),
                         os.path.basename(sys.executable))
    assert f'PYTHON="{baked}"' in wrapper
    cwd = tmp_path / "cwd"
    (cwd / "claude_session").mkdir(parents=True)
    for f in ("__init__.py", "__main__.py", "cli.py"):
        (cwd / "claude_session" / f).write_text(DECOY)
    r = subprocess.run([str(home / ".local" / "bin" / "agentik-session"), "hook", "PostToolUse"],
                       cwd=cwd, input="{}", env=_env(home, PYTHONPATH=str(cwd)),
                       capture_output=True, text=True, timeout=30)
    assert "DECOY" not in r.stdout and r.returncode != 7, r.stdout + r.stderr
    assert r.returncode == 0, r.stderr
    # The root checkout cannot change a hook either: the installed copy is not the repo.
    (repo / PKG / "cli.py").write_text(DECOY)
    r = subprocess.run([str(home / ".local" / "bin" / "agentik-session"), "hook", "PostToolUse"],
                       cwd=tmp_path, input="{}", env=_env(home), capture_output=True, text=True,
                       timeout=30)
    assert r.returncode == 0 and "DECOY" not in r.stdout


def test_dirty_package_refuses(repo, tmp_path):
    home = tmp_path / "home"
    with open(repo / PKG / "meter.py", "a") as f:
        f.write("# half-done\n")
    r = _install(repo, home)
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "dirty" in r.stderr
    assert not (home / ".local" / "bin" / "agentik-session").exists()
    assert not _share(home).exists()
    # a versioned Cellar interpreter is refused too (ADV10-5)
    _git(repo, "checkout", "-q", "--", PKG)
    cellar = tmp_path / "Cellar" / "python@3" / "bin"
    cellar.mkdir(parents=True)
    (cellar / "python3").symlink_to(sys.executable)
    r = _install(repo, home, python=cellar / "python3")
    assert r.returncode == 2 and "Cellar" in r.stderr, (r.stdout, r.stderr)
    assert not (home / ".local" / "bin" / "agentik-session").exists()


def test_untracked_file_in_package_refuses(repo, tmp_path):
    (repo / PKG / "stray.py").write_text("x = 1\n")
    assert _install(repo, tmp_path / "home").returncode == 2


def test_reinstall_prunes_the_old_tree(repo, tmp_path):
    home = tmp_path / "home"
    assert _install(repo, home).returncode == 0
    old = _tree(repo)
    assert sorted(p.name for p in _share(home).iterdir()) == [old]
    with open(repo / PKG / "meter.py", "a") as f:
        f.write("# next\n")
    _git(repo, "commit", "-qam", "next")
    new = _tree(repo)
    assert new != old
    assert _install(repo, home).returncode == 0
    # the newest few are kept (F8); the pruning itself is test_f8_reinstall_keeps_...
    assert sorted(p.name for p in _share(home).iterdir()) == sorted([old, new])
    assert (_share(home) / new / "claude_session" / "meter.py").read_text().endswith("# next\n")
    assert f'CODE="{_share(home) / new}"' in (home / ".local" / "bin" / "agentik-session").read_text()
    # the frozen tree gone: a hook says `run make install` once and exits 0, other
    # verbs exit 1, and the next install removes the marker (ADV10-5)
    shutil.rmtree(_share(home) / new)
    launcher = [str(home / ".local" / "bin" / "agentik-session")]
    hooks = [subprocess.run(launcher + ["hook", "PostToolUse"], input="{}", env=_env(home),
                            capture_output=True, text=True, timeout=30) for _ in range(2)]
    assert [(h.returncode, "run make install" in h.stderr) for h in hooks] == [(0, True), (0, False)]
    r = subprocess.run(launcher + ["status"], env=_env(home), capture_output=True, text=True,
                       timeout=30)
    assert r.returncode == 1 and "run make install" in r.stderr
    marker = home / "state" / "agentik-session" / "install-needed"
    assert marker.read_text().strip() == str(_share(home) / new)
    assert _install(repo, home).returncode == 0
    assert not marker.exists()


def test_gone_interpreter_speaks_at_every_session_start(tmp_path):
    # ADV11-5: a hook's stderr is unseen on exit 0, so SessionStart says it as JSON, every
    # session; the marker keeps the other events quiet
    python = tmp_path / "gone" / "bin" / "python"
    launcher = tmp_path / "agentik-session"
    launcher.write_text((ROOT / "install-wrapper.sh").read_text()
                        .replace("__CODE__", str(tmp_path)).replace("__PYTHON__", str(python)))
    launcher.chmod(0o755)
    env = dict(os.environ, XDG_STATE_HOME=str(tmp_path / "state"))

    def hook(event):
        return subprocess.run([str(launcher), "hook", event], input="{}", env=env,
                              capture_output=True, text=True, timeout=30)

    for _ in range(2):
        r = hook("SessionStart")
        assert r.returncode == 0
        assert json.loads(r.stdout) == {
            "systemMessage": "agentik-session: %s is gone; run make install" % python}
    r = hook("PreToolUse")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


# F8: an install deleted the frozen tree six live launchers ran from (PYTHONPATH named it),
# and each chain stopped at its respawn. The install keeps the new tree, every tree a live
# process names, and the newest three; it prunes the rest.

def _commit_next(repo, n):
    with open(repo / PKG / "meter.py", "a") as f:
        f.write(f"# next {n}\n")
    _git(repo, "commit", "-qam", f"next {n}")
    return _tree(repo)


def _live(home, tree):
    """A process run from `tree` as the launcher runs one (PYTHONPATH names it); it reads
    stdin until it is closed, so the test ends it without a signal."""
    return subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                            stdin=subprocess.PIPE,
                            env=_env(home, PYTHONPATH=str(_share(home) / tree)))


def test_f8_reinstall_keeps_a_tree_a_live_process_runs_from(repo, tmp_path):
    home = tmp_path / "home"
    assert _install(repo, home).returncode == 0
    first = _tree(repo)
    trees = [first]
    live = _live(home, first)
    try:
        for n in range(5):
            trees.append(_commit_next(repo, n))
            r = _install(repo, home)
            assert r.returncode == 0, r.stderr
        assert sorted(p.name for p in _share(home).iterdir()) == sorted([first] + trees[-3:])
    finally:
        live.stdin.close()
        live.wait(timeout=30)
    # once nothing runs from it, the next install prunes it
    trees.append(_commit_next(repo, 5))
    assert _install(repo, home).returncode == 0
    assert sorted(p.name for p in _share(home).iterdir()) == sorted(trees[-3:])


# ---- agentik-r1 ruling 2 and 3: the new name, the old link, the front door, the note ----

def test_r1_install_writes_the_new_name_the_link_and_the_front_door(repo, tmp_path):
    home = tmp_path / "home"
    r = _install(repo, home)
    assert r.returncode == 0, r.stderr
    bin_ = home / ".local" / "bin"
    assert os.readlink(bin_ / "claude-session") == "agentik-session"
    assert (bin_ / "agentik").read_bytes() == (ROOT / "scripts" / "agentik").read_bytes()
    assert os.access(bin_ / "agentik", os.X_OK)
    assert [p.name for p in (home / ".local" / "share").iterdir()] == ["agentik-session"]
    if RUNS_P:
        v = subprocess.run([str(bin_ / "agentik-session"), "--version"], env=_env(home),
                           capture_output=True, text=True, timeout=30)
        assert (v.returncode, v.stdout, v.stderr) == (0, "agentik-session 2.0.0-alpha.37\n", "")
    # a reinstall replaces the link in place
    assert _install(repo, home).returncode == 0
    assert os.readlink(bin_ / "claude-session") == "agentik-session"


def test_r1_install_clears_the_old_state_folders_marker_until_the_new_exists(repo, tmp_path):
    # packet ruling 1: the marker is cleared where c1 resolves, the old folder while alone
    home = tmp_path / "home"
    old = home / "state" / "claude-code-session"
    old.mkdir(parents=True)
    (old / "install-needed").write_text("x\n")
    assert _install(repo, home).returncode == 0
    assert not (old / "install-needed").exists()


def _wrapper(tmp_path, name):
    """The launcher as `make install` writes it, its python gone, under `name`."""
    launcher = tmp_path / name
    launcher.write_text((ROOT / "install-wrapper.sh").read_text()
                        .replace("__CODE__", str(tmp_path))
                        .replace("__PYTHON__", str(tmp_path / "gone" / "python")))
    launcher.chmod(0o755)
    return launcher


def _on_tty(argv, env):
    """stderr a terminal: the alias note's one condition a pipe never meets."""
    import pty
    import select
    master, slave = pty.openpty()
    try:
        r = subprocess.run(argv, input="{}", env=env, stdout=subprocess.PIPE, stderr=slave,
                           text=True, timeout=30)
        out = b""
        while select.select([master], [], [], 0.5)[0]:
            chunk = os.read(master, 4096)
            if not chunk:
                break
            out += chunk
        return r.returncode, out.decode()
    finally:
        os.close(slave)
        os.close(master)


def test_r1_the_old_name_notes_once_on_a_terminal_never_in_a_hook(tmp_path):
    # agentik-r1 §4.3 (packet ruling 3)
    env = dict(os.environ, XDG_STATE_HOME=str(tmp_path / "state"))
    new = _wrapper(tmp_path, "agentik-session")
    old = tmp_path / "claude-session"
    old.symlink_to("agentik-session")
    note = "claude-session: renamed; use 'agentik session …' (ends 2026-12-31)"
    code, err = _on_tty([str(old), "status"], env)
    assert code == 1 and err.splitlines()[0].strip() == note
    for argv in ([str(new), "status"], [str(old), "hook", "PreToolUse"]):
        code, err = _on_tty(argv, env)
        assert note not in err, argv
    r = subprocess.run([str(old), "status"], env=env, capture_output=True, text=True,
                       timeout=30)
    assert note not in r.stderr          # a pipe sees nothing
