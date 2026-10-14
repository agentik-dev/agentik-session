"""The suite never reads or writes the user's state (ADV6-6, ADV6's test 3).

At import, before any test module imports `claude_session`, `HOME` and `XDG_STATE_HOME`
point at a sentinel root holding a poisoned `meter.json` for every session id the suite
uses: code that escapes the per-test roots below lands there, reads a sitting past its
ceilings, and the session teardown finds the sentinel changed. Each test then gets its
own temp `HOME` and `XDG_STATE_HOME` (and `config.STATE_DIR` to match). The sentinel
root is removed at interpreter exit, after the session's poison check (ADV10-11 a): no
pytest process, the collection child included, leaves a temp root behind.

The suite is run from inside sittings, so what a sitting exports never reaches a test
(round 2 F2): `INHERITED` is cleared at import and again for every test. A test that
needs a role, a configuration, a helper mark, a depth or a turn cap sets its own.
"""
import atexit
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Every session id a test uses, and the fixture transcripts' own.
SENTINEL_SIDS = ("test-session", "cli-sess-0000-1111-2222", "sess-1", "meter-sess-1", "t",
                 "test-sess-0000-1111-2222", "g", "cfg-sess-0000-1111-2222",
                 "a-different-session-9999")
POISON = (b'{"poisoned": "the suite read the sentinel root, not its temp state",'
          b' "pct_context": 100.0, "pct_turns": 100.0, "turns": 400, "context": 180000}\n')

_SENTINEL = Path(tempfile.mkdtemp(prefix="agentik-session-sentinel-"))
atexit.register(shutil.rmtree, _SENTINEL, ignore_errors=True)
_ENV = pytest.MonkeyPatch()
_ENV.setenv("HOME", str(_SENTINEL))
_ENV.setenv("XDG_STATE_HOME", str(_SENTINEL / ".local" / "state"))
# The configured model (ANTHROPIC_MODEL); the role the README's start steps export
# (CLAUDE_SESSION_PROFILE) and the configuration `agentik session start` sets
# (CLAUDE_SESSION_CONFIG); the helper mark, the depth and the turn cap a sitting's
# helpers and relay children carry; the model a relay child's launcher names (S28); the
# relay's row; a respawn launcher's chain.
INHERITED = ("ANTHROPIC_MODEL", "CLAUDE_SESSION_PROFILE", "CLAUDE_SESSION_CONFIG",
             "CLAUDE_SESSION_HELPER", "CLAUDE_SESSION_DEPTH", "CLAUDE_SESSION_MAX_TURNS",
             "CLAUDE_SESSION_MODEL",
             "RELAY_ROW", "CLAUDE_SESSION_CHAIN",
             # the marks of the Claude Code session the suite runs in, which `run`
             # refuses (S20 ruling 10)
             "CLAUDECODE", "CLAUDE_CODE_SESSION_ID",
             # the prompt cache's lifetime and the provider, which `rules.lifetime` reads (S30)
             "FORCE_PROMPT_CACHING_5M", "CLAUDE_CODE_PROMPT_CACHE_TTL", "ENABLE_PROMPT_CACHING_1H",
             "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
             "CLAUDE_CODE_USE_ANTHROPIC_AWS", "CLAUDE_CODE_USE_MANTLE", "CLAUDE_PROJECT_DIR",
             "DISABLE_PROMPT_CACHING", "DISABLE_PROMPT_CACHING_HAIKU",
             "DISABLE_PROMPT_CACHING_SONNET", "DISABLE_PROMPT_CACHING_OPUS",
             "DISABLE_PROMPT_CACHING_FABLE", "CLAUDE_CONFIG_DIR",
             "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")
for _k in INHERITED:
    _ENV.delenv(_k, raising=False)
from claude_session.config import APP  # noqa: E402  (after the env: STATE_DIR is read at import)

_PLANTED = []
for _sid in SENTINEL_SIDS:
    _p = _SENTINEL / ".local" / "state" / APP / "sessions" / _sid / "meter.json"
    _p.parent.mkdir(parents=True)
    _p.write_bytes(POISON)
    _PLANTED.append(_p)


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


_BEFORE = _tree(_SENTINEL)


@pytest.fixture(scope="session", autouse=True)
def sentinel_state_root():
    """ADV6's test 3: after the whole run, the sentinel root is byte-for-byte as planted."""
    yield _SENTINEL
    try:
        assert _tree(_SENTINEL) == _BEFORE, "a test wrote under the sentinel HOME"
        assert all(p.read_bytes() == POISON for p in _PLANTED)
    finally:
        _ENV.undo()


@pytest.fixture(autouse=True)
def temp_state_roots(tmp_path_factory, monkeypatch):
    """Per test: `HOME` and `XDG_STATE_HOME` at fresh temp roots, `config.STATE_DIR` on
    the same root. A test that needs a narrower root still sets its own."""
    from claude_session import config
    home = tmp_path_factory.mktemp("home")
    xdg = home / ".local" / "state"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg))
    for k in INHERITED:                  # a test before this one may have set one bare
        monkeypatch.delenv(k, raising=False)
    # git reads its identity from HOME; the temp HOME has none.
    for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(k, "test")
    monkeypatch.setattr(config, "STATE_DIR", config.state_dir({"XDG_STATE_HOME": str(xdg)}))
    return home
