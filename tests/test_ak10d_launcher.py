"""Row ak10d-session-launcher (hq NICE n22): the launcher this repo's `install.py` writes is read
by commons' canonical `uninstall` as its own, so `agentik remove session` takes back the launcher,
its frozen trees and the `akt` and `claude-session` links. Its line 2 is the canonical template's
for `agentik-session`; the old-name note follows on line 3. A launcher of the old form (the line
2 alpha.126 wrote) is still read as before and the SessionStart refresh moves it to the new form.

Every test installs into a temp prefix or home with a plugin copy; none reads the live state.
"""
import os
import sys
from pathlib import Path

from test_install import (NEW, _bins, _call, _plugin, _session_start, _share,  # noqa: F401
                          _verb, old_install)

ROOT = Path(__file__).resolve().parents[1]
NAME = "agentik-session"
# The two lines alpha.126 and before wrote as the launcher's lines 2 and 3.
OLD_FORM = ("# agentik-session launcher, written by `agentik-session install-cli` (design/04 §2, "
            "§3); its old\n# name, claude-session, is a link to it until r2 (agentik-r1 §4.3).")


def _canonical():
    sys.path.insert(0, str(ROOT / "plugin" / "lib"))
    try:
        import agentik_install
    finally:
        sys.path.pop(0)
    return agentik_install


def _files(top):
    return sorted(str(p.relative_to(top)) for p in Path(top).rglob("*")
                  if p.is_file() or p.is_symlink())


def _old_form(tool):
    """The launcher at `tool` rewritten to the old form: its lines 2 and 3 as alpha.126 wrote
    them, every other byte as install-cli wrote it."""
    lines = tool.read_text().split("\n")
    tool.write_text("\n".join([lines[0], OLD_FORM] + lines[3:]))


def test_ak10d_r1_line_2_is_the_canonicals_and_the_old_name_note_is_line_3():
    from claude_session import install
    canonical = _canonical()
    ours, theirs = install.LAUNCHER.split("\n"), canonical.LAUNCHER.split("\n")
    assert ours[1] == theirs[1].replace("__NAME__", NAME)
    assert ours[1] == ("# agentik-session launcher, written by `agentik-session install-cli` "
                       "(hq design/04 §2, §3).")
    assert ours[2] == "# Its old name, __OLD_NAME__, is a link to it until r2 (agentik-r1 §4.3)."
    text = install.launcher_text("/x/tree", "2.0.0").split("\n")
    assert text[2] == "# Its old name, claude-session, is a link to it until r2 (agentik-r1 §4.3)."


def test_ak10d_r2_the_canonical_plans_every_file_of_a_fresh_install_and_takes_it_back(tmp_path):
    home, prefix = tmp_path / "home", tmp_path / "prefix"
    home.mkdir()
    (prefix / "bin").mkdir(parents=True)
    os.symlink(NAME, prefix / "bin" / "claude-session")    # is1-old-name: one that stood before
    r = _verb(_plugin(tmp_path), home, "--prefix", str(prefix))
    assert r.returncode == 0, r.stderr
    bin_dir, share = prefix / "bin", prefix / "share" / NAME
    trees = sorted(p for p in share.iterdir() if not p.name.startswith("."))
    assert len(trees) == 1 and os.readlink(bin_dir / "akt") == NAME
    assert os.readlink(bin_dir / "claude-session") == NAME
    canonical = _canonical()
    assert canonical._ours(str(bin_dir / NAME), NAME, str(share))
    before = _files(prefix)
    plan = canonical.uninstall(NAME, str(prefix), dry=True)
    assert (str(bin_dir / NAME), "launcher", "would remove") in plan, plan
    assert (str(bin_dir / "akt"), "link", "would remove") in plan, plan
    assert (str(bin_dir / "claude-session"), "link", "would remove") in plan, plan
    for tree in trees:
        assert (str(tree), "tree", "would remove") in plan, plan
    assert (str(share), "share", "would remove") in plan, plan
    assert all(fate == "would remove" for _, _, fate in plan), plan
    assert _files(prefix) == before                            # the dry run moved nothing
    rows = canonical.uninstall(NAME, str(prefix))
    assert [fate for _, _, fate in rows] == ["removed"] * len(plan), rows
    # Nothing of session's is left; the shared `agentik` door stays without `door=True`.
    assert _files(prefix) == ["bin/agentik"], _files(prefix)


def test_ak10d_r2_an_old_form_launcher_reads_as_before_and_the_refresh_moves_it(old_install):
    from claude_session import doctor, install
    home, tool, plugin = old_install
    env = {"HOME": str(home)}
    canonical = _canonical()
    new_read, new_check = install.read_launcher(str(tool)), doctor._check_launcher(env, None)
    assert canonical._ours(str(tool), NAME, str(_share(home)))
    _old_form(tool)
    assert tool.read_text().split("\n")[1:3] == OLD_FORM.split("\n")
    # session's own reads: the same lines read, the same doctor's check, the launcher runs
    assert install.read_launcher(str(tool)) == new_read and new_read["tree"]
    assert vars(doctor._check_launcher(env, None)) == vars(new_check)
    r = _call(tool, home, "--version")
    assert r.returncode == 0 and r.stdout.split()[-1] != NEW, r
    # commons' uninstall keeps it, as at alpha.126
    assert not canonical._ours(str(tool), NAME, str(_share(home)))
    # the SessionStart refresh writes the new form, which commons reads as its own
    r = _session_start(plugin, home)
    assert r.returncode == 0, r
    text = tool.read_text()
    assert "VERSION=%s\n" % NEW in text and text.split("\n")[1:3] != OLD_FORM.split("\n")
    assert text.split("\n")[1] == canonical.LAUNCHER.split("\n")[1].replace("__NAME__", NAME)
    assert canonical._ours(str(tool), NAME, str(_share(home)))
    assert _call(tool, home, "--version").stdout.split()[-1] == NEW
