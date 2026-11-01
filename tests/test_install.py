"""`make install` through `install-cli`, and the verb on a bare machine (ADV6-3, packet sc3): a
frozen copy of the package, run with `-I`, never the cwd's tree.

The `make` tests install in a temp git repo (a copy of this tree's Makefile and plugin, committed)
into a temp HOME; the verb's tests run a plugin copy under the bare env. Never this tree, never
the real `~/.local`.
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


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    shutil.copy2(ROOT / "Makefile", r / "Makefile")
    (r / "plugin").mkdir()
    for part in ("lib", "bin"):
        shutil.copytree(ROOT / "plugin" / part, r / "plugin" / part,
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


def _install(repo, home, *args):
    return subprocess.run(["make", "-s", "install", "DOCTOR=0", *args], cwd=repo, env=_env(home),
                          capture_output=True, text=True, timeout=60)


def _share(home):
    return home / ".local" / "share" / "agentik-session"


def test_hook_runs_installed_code_not_cwd(repo, tmp_path):
    home = tmp_path / "home"
    r = _install(repo, home)
    assert r.returncode == 0, r.stderr
    [tree] = _trees(home)
    wrapper = (home / ".local" / "bin" / "agentik-session").read_text()
    assert f"TREE={_share(home) / tree}\n" in wrapper
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


def test_untracked_file_in_package_refuses(repo, tmp_path):
    (repo / PKG / "stray.py").write_text("x = 1\n")
    assert _install(repo, tmp_path / "home").returncode == 2


def test_make_install_gives_the_same_tree_as_the_verb(repo, tmp_path):
    made, verbed = tmp_path / "made", tmp_path / "verbed"
    verbed.mkdir()
    r = _install(repo, made)
    assert r.returncode == 0, r.stderr
    r = _verb(repo / "plugin", verbed)
    assert r.returncode == 0, r.stderr
    assert _trees(made) == _trees(verbed)
    [tree] = _trees(made)
    assert sorted(_walked(_share(made) / tree)) == sorted(_walked(_share(verbed) / tree))
    text = (_bins(verbed) / "agentik-session").read_text()
    assert (_bins(made) / "agentik-session").read_text() == text.replace(str(verbed), str(made))


def _walked(top):
    return [(str(p.relative_to(top)), p.read_bytes()) for p in top.rglob("*") if p.is_file()]


def test_make_install_honours_prefix(repo, tmp_path):
    home, prefix = tmp_path / "home", tmp_path / "pfx"
    r = _install(repo, home, "PREFIX=%s" % prefix)
    assert r.returncode == 0, r.stderr
    assert (prefix / "bin" / "agentik-session").is_file()
    assert not (home / ".local").exists()


def _commit_next(repo, n):
    with open(repo / PKG / "meter.py", "a") as f:
        f.write(f"# next {n}\n")
    _git(repo, "commit", "-qam", f"next {n}")


def test_reinstall_keeps_the_newest_and_clears_the_marker(repo, tmp_path):
    home = tmp_path / "home"
    assert _install(repo, home).returncode == 0
    [old] = _trees(home)
    _commit_next(repo, 0)
    assert _install(repo, home).returncode == 0
    assert len(_trees(home)) == 2 and old in _trees(home)
    new = next(t for t in _trees(home) if t != old)
    assert (_share(home) / new / "claude_session" / "meter.py").read_text().endswith("# next 0\n")
    assert f"TREE={_share(home) / new}\n" in (home / ".local" / "bin" / "agentik-session").read_text()
    # the frozen tree gone: the next hook writes the marker, and the next install removes it
    shutil.rmtree(_share(home) / new)
    r = subprocess.run([str(home / ".local" / "bin" / "agentik-session"), "hook", "PostToolUse"],
                       input="{}", env=_env(home), capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and "run /session:install-cli" in r.stderr
    marker = home / "state" / "agentik-session" / "install-needed"
    assert marker.read_text().strip() == str(_share(home) / new)
    assert _install(repo, home).returncode == 0
    assert not marker.exists()


# F8: an install deleted the frozen tree six live launchers ran from, and each chain stopped at
# its respawn. The install keeps the new tree, every tree a live process names, and the newest
# three; it prunes the rest.

def _live(home, tree):
    """A process run from `tree` as the old launcher ran one (PYTHONPATH names it); it reads
    stdin until it is closed, so the test ends it without a signal."""
    return subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                            stdin=subprocess.PIPE,
                            env=_env(home, PYTHONPATH=str(_share(home) / tree)))


def test_f8_reinstall_keeps_a_tree_an_old_launcher_runs_from(repo, tmp_path):
    home = tmp_path / "home"
    assert _install(repo, home).returncode == 0
    [first] = _trees(home)
    live = _live(home, first)
    try:
        for n in range(5):
            _commit_next(repo, n)
            r = _install(repo, home)
            assert r.returncode == 0, r.stderr
        assert first in _trees(home) and len(_trees(home)) == 4
    finally:
        live.stdin.close()
        live.wait(timeout=30)
    # once nothing runs from it, the next install prunes it
    _commit_next(repo, 5)
    assert _install(repo, home).returncode == 0
    assert first not in _trees(home) and len(_trees(home)) == 3


# ---- agentik-r1 ruling 2 and 3: the new name, the old link, the front door, the note ----

def test_r1_install_writes_the_new_name_the_link_and_the_front_door(repo, tmp_path):
    home = tmp_path / "home"
    r = _install(repo, home)
    assert r.returncode == 0, r.stderr
    bin_ = home / ".local" / "bin"
    assert os.readlink(bin_ / "claude-session") == "agentik-session"
    assert (bin_ / "agentik").read_bytes() == (ROOT / "plugin" / "bin" / "agentik").read_bytes()
    assert os.access(bin_ / "agentik", os.X_OK)
    assert [p.name for p in (home / ".local" / "share").iterdir()] == ["agentik-session"]
    v = subprocess.run([str(bin_ / "agentik-session"), "--version"], env=_env(home),
                       capture_output=True, text=True, timeout=30)
    assert (v.returncode, v.stdout, v.stderr) == (
        0, "agentik-session %s\n" % json.loads((repo / MANIFEST).read_text())["version"], "")
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


# sc2: this Mac's sessions depend on `make install` until sc3.
def test_the_moved_tree_installs_and_reads_its_version_from_plugin_json(repo, tmp_path):
    home = tmp_path / "home"
    assert _install(repo, home).returncode == 0
    version = json.loads((repo / MANIFEST).read_text())["version"]
    tool = home / ".local" / "bin" / "agentik-session"
    run = lambda: subprocess.run([str(tool), "--version"], capture_output=True, text=True,
                                 env=_env(home), cwd=tmp_path, timeout=30).stdout.split()[-1]
    assert run() == version
    [tree] = _trees(home)
    code = _share(home) / tree
    assert (code / "plugin.json").is_file() and (code / "agentik-session").is_file()
    r = subprocess.run([sys.executable, "-I", "-B", str(code / "agentik-session"), "--version"],
                       capture_output=True, text=True, env=_env(home), cwd=tmp_path, timeout=30)
    assert r.stdout.split()[-1] == version      # the runner gate.spawn_serve starts
    # A bump alone is a new tree, or `--version` would lie.
    (repo / MANIFEST).write_text((repo / MANIFEST).read_text().replace(version, "9.9.9-alpha.1"))
    _git(repo, "commit", "-qam", "bump")
    assert _install(repo, home).returncode == 0
    assert run() == "9.9.9-alpha.1"


# ---- sc3: the verb, on a bare machine ---------------------------------------------------

BARE = "/usr/bin:/bin"


def _plugin(tmp_path, version=None):
    """This tree's plugin as a marketplace would lay it out, its version as given."""
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


def _verb(plugin, home, *args, **env):
    return subprocess.run([str(plugin / "bin" / "agentik-session"), "install-cli", *args],
                          env=_bare(home, **env), capture_output=True, text=True, timeout=60,
                          cwd=home)


def _bins(home):
    return home / ".local" / "bin"


def _trees(home):
    return sorted(p.name for p in _share(home).iterdir() if not p.name.startswith("."))


def test_sc3_the_verb_on_a_bare_machine_writes_launcher_link_door_and_tree(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    plugin = _plugin(tmp_path, "2.0.0-alpha.77")
    r = _verb(plugin, home)
    assert r.returncode == 0, r.stderr
    tool = _bins(home) / "agentik-session"
    assert os.access(tool, os.X_OK)
    assert "VERSION=2.0.0-alpha.77\n" in tool.read_text()
    assert os.readlink(_bins(home) / "claude-session") == "agentik-session"
    assert (_bins(home) / "agentik").read_bytes() == (plugin / "bin" / "agentik").read_bytes()
    assert os.access(_bins(home) / "agentik", os.X_OK)
    [tree] = _trees(home)
    code = _share(home) / tree
    assert (code / "plugin.json").is_file() and (code / "agentik-session").is_file()
    assert (code / "claude_session" / "install.py").is_file()
    assert not list(code.rglob("__pycache__"))
    # No clone, no venv: the launcher alone, from anywhere, under the bare PATH.
    shutil.rmtree(plugin)
    v = subprocess.run([str(tool), "--version"], env=_bare(home), capture_output=True, text=True,
                       cwd=tmp_path, timeout=30)
    assert (v.returncode, v.stdout, v.stderr) == (0, "agentik-session 2.0.0-alpha.77\n", "")
    d = subprocess.run([str(_bins(home) / "agentik"), "session", "--version"],
                       env={"HOME": str(home), "PATH": "%s:%s" % (_bins(home), BARE)},
                       capture_output=True, text=True, timeout=30)
    assert (d.returncode, d.stdout) == (0, "agentik-session 2.0.0-alpha.77\n"), d.stderr
    assert not list(_bins(home).glob(".*tmp"))


def test_sc3_the_name_is_the_content_and_the_verb_runs_from_a_frozen_tree_too(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    plugin = _plugin(tmp_path, "2.0.0-alpha.77")
    assert _verb(plugin, home).returncode == 0
    [tree] = _trees(home)
    # Its own runner's path, whichever it runs from: the frozen tree gives the same tree.
    before = (_bins(home) / "agentik-session").read_bytes()
    r = subprocess.run([str(_bins(home) / "agentik-session"), "install-cli"], env=_bare(home),
                       capture_output=True, text=True, timeout=60, cwd=home)
    assert r.returncode == 0, r.stderr
    assert _trees(home) == [tree] and (_bins(home) / "agentik-session").read_bytes() == before
    # A bump alone is a new tree, or `--version` would lie.
    assert _verb(_plugin(tmp_path / "next", "2.0.0-alpha.78"), home).returncode == 0
    assert len(_trees(home)) == 2 and tree in _trees(home)


def test_sc3_prefix_aims_it_elsewhere_and_writes_nothing_under_home(tmp_path):
    home, prefix = tmp_path / "home", tmp_path / "pfx"
    home.mkdir()
    r = _verb(_plugin(tmp_path), home, "--prefix", str(prefix))
    assert r.returncode == 0, r.stderr
    assert (prefix / "bin" / "agentik-session").is_file()
    assert not (home / ".local" / "bin").exists() and not (home / ".local" / "share").exists()


def test_sc3_a_failure_says_so_and_exits_non_zero(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".local").write_text("a file where a folder goes")
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 1 and "install-cli" in r.stderr and "Traceback" not in r.stderr


# ---- sc3 act 2: the launcher's form ------------------------------------------------------

@pytest.fixture
def box(tmp_path):
    """A temp home with a launcher `install-cli` wrote from a plugin copy."""
    home = tmp_path / "home"
    home.mkdir()
    plugin = _plugin(tmp_path)
    r = _verb(plugin, home)
    assert r.returncode == 0, r.stderr
    return home, _bins(home) / "agentik-session", plugin


def _call(tool, home, *argv, env=None, stdin="{}", cwd=None):
    return subprocess.run([str(tool), *argv], input=stdin, env=env or _bare(home), cwd=cwd or home,
                          capture_output=True, text=True, timeout=60)


def _the_three_reads(tool, home, env, gone):
    """A verb exits 3; `hook` exits 0; SessionStart a valid JSON systemMessage, every time;
    other events say it once, by the marker."""
    r = _call(tool, home, "status", env=env)
    assert r.returncode == 3 and gone in r.stderr and "/session:install-cli" in r.stderr, r
    for _ in range(2):
        r = _call(tool, home, "hook", "SessionStart", env=env)
        assert r.returncode == 0, r.stderr
        said = json.loads(r.stdout)
        assert list(said) == ["systemMessage"]
        assert gone in said["systemMessage"] and "/session:install-cli" in said["systemMessage"]
    marker = home / ".local" / "state" / "agentik-session" / "install-needed"
    assert marker.read_text().strip() == gone
    r = _call(tool, home, "hook", "PreToolUse", env=env)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    marker.unlink()
    said = [_call(tool, home, "hook", "PostToolUse", env=env) for _ in range(2)]
    assert [(h.returncode, gone in h.stderr) for h in said] == [(0, True), (0, False)]
    assert marker.read_text().strip() == gone


def test_sc3_a_gone_interpreter(box, tmp_path):
    home, tool, _ = box
    empty = tmp_path / "empty"
    empty.mkdir()
    gone = "/nowhere/python3"
    _the_three_reads(tool, home, _bare(home, AGENTIK_PYTHON=gone, PATH=str(empty)), gone)
    # A folder at the path is as gone, and PATH's python3 is the fallback when there is one.
    r = _call(tool, home, "--version", env=_bare(home, AGENTIK_PYTHON="/usr"))
    assert r.returncode == 0 and r.stdout.startswith("agentik-session ")


def test_sc3_an_interpreter_that_is_none_never_blocks_a_hook(box, tmp_path):
    home, tool, _ = box
    fake = tmp_path / "fake-python"
    fake.write_text("#!/bin/sh\nexit 2\n")
    fake.chmod(0o755)
    env = _bare(home, AGENTIK_PYTHON=str(fake))
    r = _call(tool, home, "hook", "PreToolUse", env=env)
    assert r.returncode == 0, r
    r = _call(tool, home, "hook", "SessionStart", env=env)
    assert r.returncode == 0 and "systemMessage" in json.loads(r.stdout)


def test_sc3_a_gone_tree(box):
    home, tool, _ = box
    [tree] = _trees(home)
    shutil.rmtree(_share(home) / tree)
    _the_three_reads(tool, home, _bare(home), str(_share(home) / tree))


def test_sc3_a_path_that_needs_quoting_stays_valid(tmp_path):
    from claude_session import install
    weird = tmp_path / 'we"ird\\ $HOME `x` tree'
    tool = tmp_path / "agentik-session"
    tool.write_text(install.launcher_text(weird, "2.0.0-alpha.1"))
    tool.chmod(0o755)
    r = _call(tool, tmp_path, "hook", "SessionStart")
    assert r.returncode == 0, r.stderr
    assert str(weird) in json.loads(r.stdout)["systemMessage"]


def test_sc3_decoys_change_nothing_the_launcher_runs(box, tmp_path):
    home, tool, _ = box
    cwd, decoys = tmp_path / "cwd", tmp_path / "decoys"
    for d in (cwd, decoys):
        (d / "claude_session").mkdir(parents=True)
        for f in ("__init__.py", "__main__.py", "cli.py"):
            (d / "claude_session" / f).write_text(DECOY)
    real = _call(tool, home, "--version")
    assert real.returncode == 0
    for argv in (("--version",), ("hook", "PostToolUse")):
        r = _call(tool, home, *argv, env=_bare(home, PYTHONPATH=str(decoys), PYTHONHOME=str(decoys)),
                  cwd=cwd)
        assert r.returncode == 0 and "DECOY" not in r.stdout + r.stderr, r
    assert _call(tool, home, "--version", cwd=cwd).stdout == real.stdout
    # The plugin it was frozen from cannot change it either.
    (box[2] / "lib" / "claude_session" / "cli.py").write_text(DECOY)
    assert _call(tool, home, "--version").stdout == real.stdout


def test_sc3_the_old_name_notes_once_on_a_terminal_never_in_a_hook(box):
    home, tool, _ = box
    old = _bins(home) / "claude-session"
    note = "claude-session: renamed; use 'agentik session …' (ends 2026-12-31)"
    code, err = _on_tty([str(old), "--version"], _bare(home))
    assert code == 0 and err.splitlines()[0].strip() == note
    for argv in ([str(tool), "--version"], [str(old), "hook", "PreToolUse"]):
        assert note not in _on_tty(argv, _bare(home))[1], argv
    assert note not in _call(old, home, "--version").stderr


def _launcher_form(words):
    """agentik-observer's sources.py:_launcher, its match copied here (it is read-only and never
    imported): a word whose basename is agentik-session, directly followed by `run`."""
    names = [os.path.basename(w) for w in words]
    return any(n == "agentik-session" and "run" in names[i + 1:i + 2] for i, n in enumerate(names))


def _pty_run(argv, env, cwd, timeout=60):
    """argv on a terminal to its end; (exit, what it wrote)."""
    import pty
    import select
    import time
    master, slave = pty.openpty()
    p = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd)
    os.close(slave)
    out, end = b"", time.time() + timeout
    try:
        while time.time() < end:
            chunk = b""
            if select.select([master], [], [], 0.2)[0]:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    pass
            out += chunk
            if p.poll() is not None and not chunk:
                return p.returncode, out.decode(errors="replace")
        p.terminate()
        p.wait(timeout=30)
        raise AssertionError("no end: " + out.decode(errors="replace"))
    finally:
        os.close(master)


def _stub_claude(stubs, out):
    """A fake `claude`: its own environment, and its parent's command line, then a clean end."""
    stubs.mkdir(parents=True, exist_ok=True)
    (stubs / "claude").write_text(
        '#!/bin/sh\n/usr/bin/env > "%s/env"\n/bin/ps -o command= -p "$PPID" > "%s/parent"\nexit 0\n'
        % (out, out))
    (stubs / "claude").chmod(0o755)


def test_sc3_run_reaches_its_first_spawn_at_3_9_and_ps_reads_the_form(box, tmp_path):
    home, tool, _ = box
    out = tmp_path / "seen"
    out.mkdir()
    _stub_claude(tmp_path / "stubs", out)
    env = _bare(home, PATH="%s:%s" % (tmp_path / "stubs", BARE))
    code, said = _pty_run([str(tool), "run", "--chain", "x"], env, home)
    assert (out / "parent").exists(), (code, said)
    line = (out / "parent").read_text().strip()
    words = line.split()
    assert os.path.basename(words[0]).lower().startswith("python"), line
    assert words[1:3] == ["-I", "-X"] and words[3].startswith("pycache_prefix="), line
    assert str(_share(home)) in words[4] and words[4].endswith("/agentik-session"), line
    assert words[5:8] == ["run", "--chain", "x"], line
    assert _launcher_form(words), line
    assert "3.9" in subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.version)"],
                                   capture_output=True, text=True).stdout


# ---- sc3 act 3: F8 through the verb ------------------------------------------------------

def test_sc3_a_chain_under_the_new_form_keeps_its_tree_through_installs(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert _verb(_plugin(tmp_path / "p0", "2.0.0-alpha.1"), home).returncode == 0
    [first] = _trees(home)
    runner = _share(home) / first / "agentik-session"
    # The tree's real runner, as a launcher runs it, sat in `gate serve`'s place: stdin holds it.
    live = subprocess.Popen(["/usr/bin/python3", "-I", "-X", "pycache_prefix=%s" % (tmp_path / "c"),
                             "-c", "import sys; sys.stdin.read()", str(runner), "run", "--chain", "x"],
                            stdin=subprocess.PIPE)
    try:
        for n in range(2, 7):
            assert _verb(_plugin(tmp_path / ("p%d" % n), "2.0.0-alpha.%d" % n), home).returncode == 0
        assert first in _trees(home) and len(_trees(home)) == 4
    finally:
        live.stdin.close()
        live.wait(timeout=30)
    assert _verb(_plugin(tmp_path / "p9", "2.0.0-alpha.9"), home).returncode == 0
    assert first not in _trees(home) and len(_trees(home)) == 3


# ---- sc3 act 5: the forward refresh ------------------------------------------------------

OLD, NEW = "2.0.0-alpha.39", "2.0.0-alpha.40"


def _session_start(plugin, home, **env):
    """The plugin's own shim, as Claude Code fires it, in a temp home."""
    payload = {"session_id": "sess-r", "cwd": str(home), "hook_event_name": "SessionStart"}
    return subprocess.run(
        [str(plugin / "hooks" / "run"), "SessionStart"], input=json.dumps(payload), text=True,
        capture_output=True, cwd=home, timeout=60,
        env=_bare(home, CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PLUGIN_DATA=str(home / "data"), **env))


@pytest.fixture
def old_install(tmp_path):
    """A launcher at OLD's form (the new form's words at OLD: the one from `install-wrapper.sh`
    has no VERSION= line, and is the refusal below), and the plugin at NEW."""
    home = tmp_path / "home"
    home.mkdir()
    assert _verb(_plugin(tmp_path / "old", OLD), home).returncode == 0
    return home, _bins(home) / "agentik-session", _plugin(tmp_path / "new", NEW)


def _version(tool, home):
    r = _call(tool, home, "--version")
    assert r.returncode == 0, r.stderr
    return r.stdout.split()[-1]


def _whole(home):
    """No temp left, and every tree the launcher could name holds its runner."""
    assert not [p.name for p in _bins(home).iterdir() if p.name.endswith(".tmp")]
    assert not [p.name for p in _share(home).iterdir() if p.name.startswith(".tmp")]
    for t in _trees(home):
        assert (_share(home) / t / "agentik-session").is_file()
        assert (_share(home) / t / "plugin.json").is_file()


def test_sc3_one_session_start_moves_the_launcher_forward_and_a_second_is_a_no_op(old_install):
    home, tool, plugin = old_install
    r = _session_start(plugin, home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert "VERSION=%s\n" % NEW in tool.read_text() and _version(tool, home) == NEW
    assert os.readlink(_bins(home) / "claude-session") == "agentik-session"
    _whole(home)
    assert len(_trees(home)) == 2
    seen = (tool.read_bytes(), tool.stat().st_mtime_ns, _trees(home))
    r = _session_start(plugin, home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert (tool.read_bytes(), tool.stat().st_mtime_ns, _trees(home)) == seen


@pytest.mark.parametrize("version", (NEW, "2.0.0-alpha.41", "2.0.1", "3.0.0-alpha.1"))
def test_sc3_refresh_refuses_equal_and_backward(tmp_path, version):
    home = tmp_path / "home"
    home.mkdir()
    assert _verb(_plugin(tmp_path / "there", version), home).returncode == 0
    tool = _bins(home) / "agentik-session"
    seen = (tool.read_bytes(), tool.stat().st_mtime_ns, _trees(home))
    r = _session_start(_plugin(tmp_path / "new", NEW), home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert (tool.read_bytes(), tool.stat().st_mtime_ns, _trees(home)) == seen


def test_sc3_refresh_orders_alpha_10_above_alpha_9(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert _verb(_plugin(tmp_path / "there", "2.0.0-alpha.9"), home).returncode == 0
    assert _session_start(_plugin(tmp_path / "new", "2.0.0-alpha.10"), home).returncode == 0
    assert _version(_bins(home) / "agentik-session", home) == "2.0.0-alpha.10"


def test_sc3_refresh_never_creates_a_launcher(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    r = _session_start(_plugin(tmp_path, NEW), home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert not (home / ".local" / "bin").exists() and not (home / ".local" / "share").exists()


@pytest.mark.parametrize("line", ("", "VERSION=\n", "VERSION=banana\n", "VERSION=2.0\n"))
def test_sc3_refresh_leaves_a_launcher_with_no_version_it_can_read(tmp_path, line):
    # The wrapper of `make install` before sc3 has no VERSION= line: §5 step 3's one `make install`.
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    tool = _bins(home) / "agentik-session"
    tool.write_text('#!/bin/sh\n%sCODE="/x"\nPYTHON="/y"\nexit 0\n' % line)
    tool.chmod(0o755)
    seen = (tool.read_bytes(), tool.stat().st_mtime_ns)
    r = _session_start(_plugin(tmp_path, NEW), home)
    assert r.returncode == 0 and "systemMessage" not in json.loads(r.stdout), r
    assert (tool.read_bytes(), tool.stat().st_mtime_ns) == seen
    assert not (home / ".local" / "share").exists()


def test_sc3_a_read_only_bin_costs_one_system_message_and_never_the_hook(old_install):
    home, tool, plugin = old_install
    before = tool.read_bytes()
    _bins(home).chmod(0o555)
    try:
        r = _session_start(plugin, home)
    finally:
        _bins(home).chmod(0o755)
    assert r.returncode == 0, r.stderr
    said = json.loads(r.stdout)
    assert NEW in said["systemMessage"] and "/session:install-cli" in said["systemMessage"]
    assert "hookSpecificOutput" in said         # the session's own line stands
    assert tool.read_bytes() == before and _version(tool, home) == OLD


def test_sc3_under_the_switch_the_refresh_does_nothing(old_install):
    home, tool, plugin = old_install
    switch = home / ".config" / "agentik" / "hooks-follow-launcher"
    switch.parent.mkdir(parents=True)
    switch.write_text("")
    seen = tool.read_bytes()
    r = _session_start(plugin, home)
    assert r.returncode == 0, r.stderr
    assert "hooks run the launcher" in json.loads(r.stdout)["systemMessage"]
    assert tool.read_bytes() == seen


def test_sc3_only_the_plugin_claude_code_named_refreshes(tmp_path, monkeypatch):
    # A checkout's own suite, a hand-run launcher: nothing moves, whatever the versions.
    from claude_session import install
    home = tmp_path / "home"
    tool = home / ".local" / "bin" / "agentik-session"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\nVERSION=0.0.1\n")
    seen = tool.read_bytes()
    env = {"HOME": str(home)}
    assert install.refresh(env) is None
    assert install.refresh(dict(env, CLAUDE_PLUGIN_ROOT=str(tmp_path))) is None
    assert tool.read_bytes() == seen and not (home / ".local" / "share").exists()
    frozen = _call(_bins_tool(tmp_path), tmp_path, "hook", "SessionStart",
                   env=_bare(tmp_path / "h2", CLAUDE_PLUGIN_ROOT=str(tmp_path)))
    assert frozen.returncode == 0


def _bins_tool(tmp_path):
    h2 = tmp_path / "h2"
    h2.mkdir()
    assert _verb(_plugin(tmp_path / "p2", NEW), h2).returncode == 0
    return _bins(h2) / "agentik-session"


def test_sc3_refresh_race_two_at_once_twenty_rounds(old_install):
    home, tool, plugin = old_install
    older = tool.read_text()
    for round_ in range(20):
        tmp = tool.with_name("x-seed")
        tmp.write_text(older)
        tmp.chmod(0o755)
        os.replace(tmp, tool)
        payload = json.dumps({"session_id": "race-%d" % round_, "cwd": str(home),
                              "hook_event_name": "SessionStart"})
        env = _bare(home, CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PLUGIN_DATA=str(home / "data"))
        both = [subprocess.Popen([str(plugin / "hooks" / "run"), "SessionStart"], cwd=home, env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for _ in range(2)]
        during = _version(tool, home)       # whole at any moment, old or new
        assert during in (OLD, NEW)
        outs = [p.communicate(payload, timeout=60) for p in both]
        assert [p.returncode for p in both] == [0, 0], outs
        for out, _ in outs:
            assert "systemMessage" not in json.loads(out), outs
        assert _version(tool, home) == NEW, "round %d" % round_
        _whole(home)
