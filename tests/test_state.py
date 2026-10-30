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
            "## Gates\n- none\n## Last acts\n- none\n## Read first\n- README.md\n" + LAST)
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
    (GOOD.replace("- history/sittings/2026-10-29-2-s39.md lines 1-30\n", ""), "path line"),
    (GOOD.replace("- history/sittings/2026-10-29-2-s39.md lines 1-30\n", "- read the charter\n"),
     "path line"),
    (GOOD.replace("2026-10-29 21:40", "2026-13-45 25:99"), "do not parse"),
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


def test_write_checks_the_bytes_it_copies(tmp_path):
    src = tmp_path / "s.md"
    src.write_bytes(GOOD.replace(LAST, "").encode())
    home = tmp_path / "state" / "respawn" / "c"
    with pytest.raises(ValueError, match="read nothing else"):
        state.write(home, src, "pred-session-1", time.time())
    src.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="UTF-8"):
        state.write(home, src, "pred-session-1", time.time())
    assert not home.exists()


def test_hand_stamps_the_successor_and_deletes_a_stale_state(tmp_path):
    home, d, _ = _written(tmp_path)
    assert state.handed(home, "succ-session-2") == ("", None)              # not handed yet
    assert state.hand(home, "pred-session-1", "succ-session-2") is True
    rec = json.loads((home / "state.json").read_text())
    assert rec == {**d, "to_session": "succ-session-2"}
    assert state.handed(home, "succ-session-2") == ("ok", rec)
    assert state.handed(home, "third-session-3") == ("", None)
    assert state.handed(home, None) == ("", None)
    assert state.hand(home, "succ-session-2", "fourth-session-4") is False  # not its own
    assert not (home / "state.json").exists() and not (home / "state.md").exists()
    home, _, _ = _written(tmp_path)
    assert state.hand(home, None, "a-later-chain-1") is False               # a first start
    assert not (home / "state.json").exists() and not (home / "state.md").exists()
    assert state.hand(tmp_path / "nowhere", None, "x") is False


@pytest.mark.parametrize("case", ["altered", "missing", "garbage", "bad-sha"])
def test_handed_says_a_copy_that_does_not_match(tmp_path, case):
    home, d, _ = _written(tmp_path)
    state.hand(home, "pred-session-1", "succ-session-2")
    if case == "altered":
        (home / "state.md").write_bytes(GOOD.replace("e3d82cb", "e3d82cc").encode())
    elif case == "missing":
        (home / "state.md").unlink()
    elif case == "garbage":
        (home / "state.json").write_text("garbage")
    else:
        (home / "state.json").write_text(json.dumps({**d, "sha256": "x",
                                                     "to_session": "succ-session-2"}))
    assert state.handed(home, "succ-session-2") == ("mismatch", None)


@pytest.mark.parametrize("env,main", [
    ({}, True), ({"CLAUDE_SESSION_DEPTH": "0"}, True), ({"CLAUDE_SESSION_DEPTH": "1"}, False),
    ({"CLAUDE_SESSION_DEPTH": "x"}, False), ({"RELAY_ROW": "s39"}, False),
    ({"CLAUDE_SESSION_HELPER": "1"}, False)])
def test_main_sitting(env, main):
    assert state.main_sitting(env) is main


def test_clear_removes_the_copy_and_its_record(tmp_path):
    home, _, _ = _written(tmp_path)
    state.clear(home)
    assert not (home / "state.md").exists() and not (home / "state.json").exists()
    state.clear(home)                                                      # twice is fine


def test_the_chain_home_is_a_function(tmp_path):
    assert chain.home(tmp_path, "orient-a") == tmp_path / "respawn" / "orient-a"
    for bad in ("", "..", "a/b", "x" * 65):
        assert chain.home(tmp_path, bad) is None
