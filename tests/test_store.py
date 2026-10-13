from claude_session import store


def test_writes_are_atomic_and_private(tmp_path):
    p = tmp_path / "state" / "f.json"
    store._write_private(p, "{}")
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    # no temp files left behind
    assert not [x for x in p.parent.iterdir() if x.name.startswith(".")]
