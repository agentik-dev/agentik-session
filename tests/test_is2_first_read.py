"""Row is2-first-read: a correct install reads as set up.

R1, the doctor's `mod` row with no session on the machine is a note, and a session whose mod
was never seen stays a warn. R2, `install-cli` with its bin folder off PATH ends on the line that
mends this terminal, one line above it saying why. R4, `prune.processes()` reads the list as
the canonical module does: `ps -axwwE`, and where that exits non-zero procps's BSD form.

Every case runs in a temp HOME, prefix or state root, with a stand-in `ps`; never the real
`~/.local` or `~/.local/state`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import doctor, prune, resolver
from test_install import BARE, _bare, _plugin

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugin" / "lib"
NAME = "agentik-session"


# ---- R1: the doctor's mod row ----------------------------------------------------------------

@pytest.fixture
def bare_state(tmp_path):
    """An env with its own HOME and state root, no session id, no session on the machine."""
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "PATH": BARE, "XDG_STATE_HOME": str(tmp_path / "xdg")}


def test_r1_no_session_on_the_machine_is_a_note(bare_state):
    c = doctor._check_mod(bare_state)
    assert (c.name, c.ok, c.status) == ("mod", True, "note"), c
    assert "no session has run" in c.detail and "yet" in c.detail, c.detail
    assert doctor.render(doctor.Report([c])).splitlines()[0].startswith("note mod ")
    assert doctor.Report([c]).as_dict()["warned"] == 0


def test_r1_the_whole_doctor_counts_no_warn_for_it(bare_state):
    r = subprocess.run([sys.executable, "-m", "claude_session", "doctor", "--json"],
                       env=dict(bare_state, PYTHONPATH=str(LIB)), capture_output=True,
                       text=True, timeout=120, cwd=bare_state["HOME"])
    d = json.loads(r.stdout)
    [row] = [c for c in d["checks"] if c["name"] == "mod"]
    assert row["status"] == "note", row
    assert d["warned"] == sum(c["status"] == "warn" for c in d["checks"])
    assert "mod" not in [c["name"] for c in d["checks"] if c["status"] == "warn"]


@pytest.mark.parametrize("how", ["named", "newest"])
def test_r1_a_session_whose_mod_was_never_seen_stays_a_warn(bare_state, how):
    sid = "is2-sess-0001"
    sdir = resolver.session_dir(resolver.state_dir(bare_state), sid)
    sdir.mkdir(parents=True)
    (sdir / "resolved.json").write_text("{}")
    env = dict(bare_state, CLAUDE_CODE_SESSION_ID=sid) if how == "named" else bare_state
    c = doctor._check_mod(env)
    assert (c.ok, c.status) == (True, "warn"), c
    assert c.detail == f"not seen ({sdir / 'mod.json'})", c.detail


# ---- R2: install-cli's PATH line -------------------------------------------------------------

def _verb(plugin, home, *args, path=BARE):
    return subprocess.run([str(plugin / "bin" / NAME), "install-cli", *args],
                          env=dict(_bare(home), PATH=path), capture_output=True, text=True,
                          timeout=60, cwd=home)


def _paste(line, home):
    """The printed line pasted into a fresh shell of this terminal: (exit, where the name is)."""
    r = subprocess.run(["/bin/sh", "-c", line + "\ncommand -v " + NAME], env=_bare(home),
                       capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout.strip()


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_r2_off_path_the_default_prefix_ends_on_the_line_that_mends_it(tmp_path, home):
    r = _verb(_plugin(tmp_path), home)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    bin_dir = home / ".local" / "bin"
    assert lines[-1] == 'export PATH="$HOME/.local/bin:$PATH"', r.stdout
    assert lines[-2] == (f"{bin_dir} is not on PATH, so this terminal does not find {NAME}; "
                         "this line adds it:"), r.stdout
    assert lines[0].startswith(f"installed {bin_dir / NAME} -> ")
    assert lines[1].startswith("prune-trees: removed 0, kept 1"), r.stdout
    assert len(lines) == 4, r.stdout
    assert _paste(lines[-1], home) == (0, str(bin_dir / NAME))


@pytest.mark.parametrize("folder", ["pfx", "a b", "o'k $x \"q\""])
def test_r2_off_path_a_prefix_names_its_own_bin_folder(tmp_path, home, folder):
    prefix = tmp_path / folder
    r = _verb(_plugin(tmp_path), home, "--prefix", str(prefix))
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[-2].startswith(f"{prefix / 'bin'} is not on PATH"), r.stdout
    assert lines[-1].startswith("export PATH=") and "$HOME" not in lines[-1], r.stdout
    if folder == "pfx":
        assert lines[-1] == f'export PATH="{prefix / "bin"}:$PATH"'
    assert _paste(lines[-1], home) == (0, str(prefix / "bin" / NAME))


@pytest.mark.parametrize("spelled", ["as is", "trailing slash"])
def test_r2_on_path_it_prints_as_today(tmp_path, home, spelled):
    prefix = tmp_path / "pfx"
    entry = str(prefix / "bin") + ("/" if spelled == "trailing slash" else "")
    r = _verb(_plugin(tmp_path), home, "--prefix", str(prefix), path=f"{BARE}:{entry}")
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert len(lines) == 2 and lines[0].startswith(f"installed {prefix / 'bin' / NAME} -> ")
    assert lines[1].startswith("prune-trees: removed 0, kept 1"), r.stdout
    assert "PATH" not in r.stdout


# ---- R4: the process list's two forms --------------------------------------------------------

def _ps(tmp_path, first, second):
    """A stand-in ps: logs each call's arguments, then answers per form; `ok` prints a process
    whose environment holds the probe and names <share>/t1, any other word refuses it."""
    log = tmp_path / "ps.log"
    share = tmp_path / "share"
    answer = {}
    for form, how in (("-axwwE", first), ("axwwe", second)):
        if how == "ok":
            answer[form] = ('printf "  42 /usr/bin/python3 -c x %s=%%s PYTHONPATH=%s/t1\\n" '
                            '"$%s"; exit 0' % (prune.PROBE, share, prune.PROBE))
        else:
            answer[form] = 'echo "error: %s" >&2; exit 1' % how
    ps = tmp_path / "ps"
    ps.write_text("#!/bin/sh\n"
                  'echo "$*" >> "%s"\n'
                  'case "$1" in\n'
                  '  -axwwE) %s ;;\n'
                  '  axwwe) %s ;;\n'
                  'esac\n'
                  'exit 9\n' % (log, answer["-axwwE"], answer["axwwe"]))
    ps.chmod(0o755)
    return str(ps), log


@pytest.fixture
def share(tmp_path):
    s = tmp_path / "share"
    for i, n in enumerate(["t0", "t1", "t2"]):
        (s / n).mkdir(parents=True)
        os.utime(s / n, (1_000_000 + i, 1_000_000 + i))
    return s


def test_r4_a_ps_that_refuses_the_first_form_is_read_in_the_second(tmp_path, share):
    ps, log = _ps(tmp_path, "unsupported option (BSD syntax)", "ok")
    text, why = prune.processes(ps)
    assert why is None and f"{share}/t1" in text
    assert log.read_text().splitlines() == ["-axwwE -o pid=,command=", "axwwe -o pid=,command="]
    # and the prune keeps the tree the second form named: t2 is new, t1 live, t0 goes
    code, lines = prune.prune(share, "t2", keep=1, ps=ps)
    assert code == 0 and sorted(p.name for p in share.iterdir()) == ["t1", "t2"], lines
    assert lines[-1] == "prune-trees: removed 1, kept 2 (1 live, the newest 1)"


def test_r4_a_ps_that_refuses_both_says_why_and_keeps_every_tree(tmp_path, share):
    ps, log = _ps(tmp_path, "unsupported option (BSD syntax)", "must set personality")
    assert prune.processes(ps) == (None, f"{ps} exited 1: error: must set personality")
    assert len(log.read_text().splitlines()) == 2
    code, lines = prune.prune(share, "t2", keep=1, ps=ps)
    assert code == 0 and sorted(p.name for p in share.iterdir()) == ["t0", "t1", "t2"]
    assert lines == [f"prune-trees: {ps} exited 1: error: must set personality; keeping every tree"]


def test_r4_the_first_form_answering_runs_once(tmp_path, share):
    ps, log = _ps(tmp_path, "ok", "ok")
    text, why = prune.processes(ps)
    assert why is None and log.read_text().splitlines() == ["-axwwE -o pid=,command="]


def test_r4_the_second_form_without_the_probe_is_no_read(tmp_path):
    ps = tmp_path / "ps"
    ps.write_text('#!/bin/sh\ncase "$1" in -axwwE) exit 1 ;; esac\necho "  1 /sbin/launchd"\n')
    ps.chmod(0o755)
    assert prune.processes(str(ps)) == (None, "no process environment is visible")


def test_r4_a_ps_that_cannot_start_runs_once(tmp_path):
    gone = str(tmp_path / "no-such-ps")
    text, why = prune.processes(gone)
    assert text is None and why.startswith(f"{gone}: ")
