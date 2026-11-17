"""Packet ck2-test-workers: `make test` runs each pass on workers where its venv holds
pytest-xdist, and exactly as before where it does not, saying `workers: absent in <venv>`."""
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# The Makefile's own number (R3), as `make test` reads it with no WORKERS in its environment.
N = re.search(r"^WORKERS \?= (\d+)$", (ROOT / "Makefile").read_text(), re.M).group(1)

# A fake interpreter: `-c 'import xdist'` answers as the venv would, any other call prints its
# name and its arguments, as a pass would run them.
FAKE = "#!/bin/sh\nif [ \"$1\" = -c ]; then exit %d; fi\necho %s \"$@\"\n"


def _exe(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def _make(tmp_path, *args):
    (tmp_path / "Makefile").write_bytes((ROOT / "Makefile").read_bytes())
    # a `make check WORKERS=n` around the suite exports WORKERS; the box reads the default
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MAKE", "MFLAGS")) and k != "WORKERS"}
    return subprocess.run(["make", "-s", "test", *args], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)


def _lines(out, name):
    return [ln for ln in out.splitlines() if ln.startswith(name + " ")]


@pytest.mark.parametrize("main,floor", [(True, True), (False, False), (True, False), (False, True)])
def test_each_pass_runs_on_workers_where_its_venv_holds_the_runner(tmp_path, main, floor):
    _exe(tmp_path / ".venv" / "bin" / "python", FAKE % (0 if main else 1, "main-suite"))
    _exe(tmp_path / ".venv-floor" / "bin" / "python", FAKE % (0 if floor else 1, "floor-suite"))
    r = _make(tmp_path)
    out = r.stdout
    assert r.returncode == 0, out + r.stderr
    (m,), (f,) = _lines(out, "main-suite"), _lines(out, "floor-suite")
    assert m.split()[1:] == ["-m", "pytest", "-q"] + (["-n", N] if main else [])
    assert f.split()[1:] == (["-m", "pytest", "-q", "-p", "no:cacheprovider",
                              "--ignore=tests/test_bounded.py"] + (["-n", N] if floor else []))
    assert ("workers: absent in .venv" in out.splitlines()) is (not main)
    assert ("workers: absent in .venv-floor" in out.splitlines()) is (not floor)


def test_a_venv_without_the_runner_and_no_floor_runs_as_before_with_its_one_line(tmp_path):
    _exe(tmp_path / ".venv" / "bin" / "python", FAKE % (1, "main-suite"))
    r = _make(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == ["main-suite -m pytest -q", "workers: absent in .venv",
                                     "floor: absent"]


def test_workers_is_a_fixed_number_the_caller_overrides(tmp_path):
    _exe(tmp_path / ".venv" / "bin" / "python", FAKE % (0, "main-suite"))
    _exe(tmp_path / ".venv-floor" / "bin" / "python", FAKE % (0, "floor-suite"))
    r = _make(tmp_path, "WORKERS=6")
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(ln.split()[-2:] == ["-n", "6"] for ln in _lines(r.stdout, "main-suite")
               + _lines(r.stdout, "floor-suite"))
    assert "auto" not in [ln for ln in (ROOT / "Makefile").read_text().splitlines()
                          if ln.startswith("WORKERS ?=")][0]


def test_a_failing_pass_on_workers_still_fails_the_target(tmp_path):
    _exe(tmp_path / ".venv" / "bin" / "python", FAKE % (0, "main-suite"))
    _exe(tmp_path / ".venv-floor" / "bin" / "python",
         "#!/bin/sh\nif [ \"$1\" = -c ]; then exit 1; fi\necho floor-suite; exit 1\n")
    r = _make(tmp_path)
    assert r.returncode != 0
    assert "test: the .venv-floor pass failed" in r.stderr
    assert "workers: absent in .venv-floor" in r.stdout


def test_the_dev_extra_and_both_venv_targets_name_the_runner():
    text = (ROOT / "pyproject.toml").read_text()
    dev = [ln for ln in text.splitlines() if ln.startswith("dev = ")][0]
    assert "pytest-xdist" in dev
    mk = (ROOT / "Makefile").read_text()
    assert "RUNNER ?= pytest-xdist" in mk
    for target in ("venv-floor:", "venv:"):
        body = mk[mk.index("\n" + target):].split("\n\techo ", 1)[0]
        assert "'$(RUNNER)'" in body and "import xdist" in body, target
