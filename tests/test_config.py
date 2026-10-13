"""One state root (ADV6-6): D9's `${XDG_STATE_HOME:-~/.local/state}/` plus `config.APP`."""
import os
import subprocess
import sys
from pathlib import Path

from claude_session import config, resolver, sessionconfig

ROOT = Path(__file__).resolve().parents[1]
PROBE = ("from claude_session import config, resolver, sessionconfig; import os;"
         "print(config.STATE_DIR); print(resolver.state_dir(os.environ));"
         "print(sessionconfig.overlay_path('s').parent.parent)")


def _probe(**env):
    base = {k: v for k, v in os.environ.items() if k not in ("XDG_STATE_HOME",)}
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env={**base, **env},
                       capture_output=True, text=True, timeout=30, check=True)
    return r.stdout.split()


def test_state_dir_env_is_retired(tmp_path):
    xdg = tmp_path / "xdg"
    got = _probe(CLAUDE_SESSION_STATE_DIR=str(tmp_path / "elsewhere"), XDG_STATE_HOME=str(xdg))
    assert got == [str(xdg / config.APP)] * 3


def test_state_dir_defaults_under_home(tmp_path):
    got = _probe(HOME=str(tmp_path))
    assert got == [str(tmp_path / ".local" / "state" / config.APP)] * 3


def test_state_dir_is_the_one_root_function(tmp_path):
    assert config.state_dir({"XDG_STATE_HOME": str(tmp_path)}) == tmp_path / config.APP
    assert config.state_dir({"HOME": "/nonexistent-home"}) != config.state_dir({})  # env's HOME
    assert resolver.state_dir(os.environ) == config.STATE_DIR


def test_the_suite_runs_on_temp_roots(sentinel_state_root, tmp_path):
    home, xdg = Path(os.environ["HOME"]), Path(os.environ["XDG_STATE_HOME"])
    assert home != sentinel_state_root and not str(xdg).startswith(str(sentinel_state_root))
    assert config.STATE_DIR == xdg / config.APP
    assert sessionconfig.overlay_path("s").parent.parent == config.STATE_DIR
    # ADV10-11 (a): a process that imports conftest removes its sentinel root at exit
    tests = Path(__file__).resolve().parent
    r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                        "import conftest; print(conftest._SENTINEL)", str(tests)],
                       env={**os.environ, "TMPDIR": str(tmp_path)}, capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().startswith(str(tmp_path)) and list(tmp_path.iterdir()) == []
