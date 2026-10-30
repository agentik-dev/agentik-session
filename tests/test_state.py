"""Packet S39: the successor's state file, its shape, its copy and its record."""
import hashlib
import json
import stat
import time

import pytest

try:                                            # absent before act 2: every test fails
    from claude_session import state
except ImportError:                             # pragma: no cover
    state = None
from claude_session import chain

GOOD = ("# State for the successor of 1a2b3c4d, 2026-10-29 21:40\n\n"
        "## Helpers\n- builder s39: scratch /tmp/s39; building act 2; its handback wakes it\n\n"
        "## Gates\n- none\n\n"
        "## Last acts\n- e3d82cb the packet\n- 0123abc: act 1, the tests\n\n"
        "## Read first\n- history/sittings/2026-10-29-2-s39.md lines 1-30\n"
        "- read nothing else before the first act\n")
LAST = "- read nothing else before the first act\n"


def test_the_shape_constants():
    assert state.SECTIONS == ("## Helpers", "## Gates", "## Last acts", "## Read first")
    assert state.CEILING == 8192


def test_a_good_state_has_no_fault():
    assert state.check(GOOD) == []
    bare = ("# State for the successor of x, 2026-10-29 09:05\n## Helpers\n- none\n"
            "## Gates\n- none\n## Last acts\n- none\n## Read first\n" + LAST)
    assert state.check(bare) == []


BAD = [
    (GOOD.replace("of 1a2b3c4d, ", "for 1a2b3c4d, "), "first line"),
    (GOOD.replace("2026-10-29 21:40", "2026-10-29"), "first line"),
    ("\n" + GOOD, "first line"),
    (GOOD.replace("## Gates\n- none\n\n", ""), "sections"),
    (GOOD.replace("## Gates", "## Gates in flight"), "sections"),
    (GOOD.replace("## Helpers", "## Notes\n- x\n\n## Helpers"), "sections"),
    (GOOD + "\n## Extra\n- x\n", "sections"),
    (GOOD.replace("## Gates\n- none\n", "## Gates\n"), "'- none'"),
    (GOOD.replace("## Gates\n- none\n", "## Gates\n- none\n- g1 repo /tmp/r\n"), "'- none'"),
    (GOOD.replace("- none\n", "gate g1 in flight\n"), "bulleted"),
    (GOOD.replace("\n\n## Helpers", "\nsome prose\n\n## Helpers"), "before"),
    (GOOD.replace("- 0123abc: act 1, the tests\n", "- 0123abc a\n- 4567def b\n- 89abcde c\n"),
     "at most 3"),
    (GOOD.replace("- e3d82cb the packet", "- the packet"), "commit sha"),
    (GOOD.replace(LAST, ""), "read nothing else"),
    (GOOD.replace("- history/sittings/2026-10-29-2-s39.md lines 1-30\n" + LAST,
                  LAST + "- history/x.md lines 1-9\n"), "read nothing else"),
    (GOOD.replace("the packet", "the packet \u2014 act 0"), "em-dash"),
]


@pytest.mark.parametrize("text,named", BAD,
                         ids=[f"{i}-{n.strip(chr(39) + chr(32))}" for i, (_, n) in enumerate(BAD)])
def test_a_fault_is_named(text, named):
    faults = state.check(text)
    assert any(named in f for f in faults), faults
    assert all("\n" not in f and "\u2014" not in f for f in faults)


def test_the_ceiling_is_8192_bytes():
    base = len(GOOD.encode())
    pad = lambda n: GOOD.replace("lines 1-30\n", "lines 1-30 " + "x" * n + "\n")
    under, over = pad(8191 - base - 1), pad(8192 - base - 1)
    assert len(under.encode()) == 8191 and state.check(under) == []
    assert len(over.encode()) == 8192
    assert [f for f in state.check(over) if "ceiling" in f] != []


def _written(tmp_path, sid="pred-session-1", when=None):
    src = tmp_path / "s.md"
    src.write_bytes(GOOD.encode())
    home = tmp_path / "state" / "respawn" / "c"
    when = time.time() if when is None else when
    return home, state.write(home, src, sid, when), when


def test_write_copies_the_bytes_and_records_them(tmp_path):
    home, d, when = _written(tmp_path)
    raw = GOOD.encode()
    assert list(d) == ["from_session", "written", "sha256", "bytes"]
    assert d == {"from_session": "pred-session-1", "written": when,
                 "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    assert (home / "state.md").read_bytes() == raw
    assert json.loads((home / "state.json").read_text()) == d
    for name in ("state.md", "state.json"):
        assert stat.S_IMODE((home / name).stat().st_mode) == 0o600


def test_fresh_reads_a_predecessor_s_record_within_a_day(tmp_path):
    home, d, when = _written(tmp_path, when=time.time() - 3600)
    assert state.fresh(home, "succ-session-2", when + 3600) == d
    assert state.fresh(home, "succ-session-2", when + 86400) == d          # at the bound
    assert state.fresh(home, "succ-session-2", when + 86401) is None       # a day old
    assert state.fresh(home, "pred-session-1", when + 3600) is None        # its own writer
    (home / "state.md").write_bytes(b"x")                                  # not the record's
    assert state.fresh(home, "succ-session-2", when + 3600) is None
    (home / "state.md").unlink()
    assert state.fresh(home, "succ-session-2", when + 3600) is None
    (home / "state.json").write_text("garbage")
    assert state.fresh(home, "succ-session-2", when + 3600) is None
    assert state.fresh(tmp_path / "nowhere", "succ-session-2", when) is None


def test_clear_removes_the_copy_and_its_record(tmp_path):
    home, _, _ = _written(tmp_path)
    state.clear(home)
    assert not (home / "state.md").exists() and not (home / "state.json").exists()
    state.clear(home)                                                      # twice is fine


def test_the_chain_home_is_a_function(tmp_path):
    assert chain.home(tmp_path, "orient-a") == tmp_path / "respawn" / "orient-a"
    for bad in ("", "..", "a/b", "x" * 65):
        assert chain.home(tmp_path, bad) is None
