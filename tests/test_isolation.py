"""The suite is run from inside sittings: a README-started orchestrator exports its role,
`claude-session start` its configuration, a relay child its depth, turn cap and model. None of
it may reach a test (round 2 F2); conftest clears them for every test."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITTING = {"CLAUDE_SESSION_PROFILE": "orchestrator", "CLAUDE_SESSION_CONFIG": "review",
           "CLAUDE_SESSION_HELPER": "1", "CLAUDE_SESSION_DEPTH": "1",
           "CLAUDE_SESSION_MAX_TURNS": "80", "CLAUDE_SESSION_MODEL": "claude-opus-5-5[1m]",
           "RELAY_ROW": "7",
           "ANTHROPIC_MODEL": "claude-opus-5-5"}


def test_conftest_clears_every_sitting_variable():
    from conftest import INHERITED
    assert set(SITTING) <= set(INHERITED)
    assert not set(INHERITED) & set(os.environ)


def test_a_suite_run_inside_an_orchestrator_sitting_passes():
    # the tests that read a role, a cap or the gate from the environment (review r2 F2)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_hook_meter.py", "tests/test_hooks.py", "tests/test_models.py",
         "-k", "not a_suite_run_inside"],
        cwd=ROOT, env={**os.environ, **SITTING}, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:]
