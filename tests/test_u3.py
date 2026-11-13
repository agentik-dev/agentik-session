"""Packet u3-loop-lines: the loop judges a row at the sha that lands, and refuses a line that
runs make.

R1 the lines run in a temporary detached tree at the row's head sha; R2 the main checkout's
`.venv*` directories linked into each tree the loop makes; R3 a tree that cannot be made is red
`stage`; R4 the continuation names that tree; R5 `unbounded`; R6 the row refused before its
stage; R7 the early word. The fake `claude` and gate of tests/fixtures/unattended/ stand in,
through test_unattended's Box: no real `claude` or `make` runs.
"""
import os

from claude_session import unattended
from test_u2 import _packet, _trees
from test_unattended import _git, box  # noqa: F401  (box is a fixture)


def _main_commit(box, files, msg):
    for name, (text, mode) in files.items():
        p = box.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.chmod(mode)
    _git(box.repo, "add", *files)
    _git(box.repo, "commit", "-q", "-m", msg)


def _real(p):
    return os.path.realpath(str(p))


# ---- R1, R4: the lines run at the sha (acceptance 1, 2) ------------------------------

def test_a1_an_ignored_helper_is_not_in_the_sha_tree(box):
    _main_commit(box, {".gitignore": ("build/\n", 0o644),
                       "tool.sh": ("#!/bin/sh\n./build/helper.sh\n", 0o755)}, "a tool")
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    _git(box.repo, "worktree", "add", "-q", str(wt), "-b", "green-row", "main")
    (wt / "build").mkdir()
    (wt / "build" / "helper.sh").write_text("#!/bin/sh\nexit 0\n")
    (wt / "build" / "helper.sh").chmod(0o755)
    assert unattended._status(wt) == ""                   # ignored: the tree is reused clean
    _packet(box, "green-row", "`./tool.sh` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "acceptance") and len(box.starts) == 3
    (f,) = row["failing"]
    assert (f["status"], f["exit"]) == ("unrun", 127)
    accepts = box.kind("accept")
    sha = accepts[0]["sha"]
    text = box.starts[1]["stdin"]
    assert f"a fresh tree at {sha}" in text and "in this tree" not in text
    assert "ignored or uncommitted" in text
    assert [a["sha"] for a in accepts] == [_git(wt, "rev-parse", f"HEAD~{2 - i}") for i in range(3)]


def test_a2_the_line_runs_outside_the_row_tree_and_the_tree_goes(box):
    _packet(box, "green-row", "`pwd` exits 0")
    before = _trees(box.repo)
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    assert row["state"] == "built"
    (acc,) = box.kind("accept")
    assert acc["sha"] == row["sha"] == _git(wt, "rev-parse", "HEAD")
    where = acc["lines"][0]["last"]
    assert _real(where) != _real(wt) and not _real(where).startswith(_real(wt) + os.sep)
    assert not os.path.exists(where)
    trees = [_real(ln.split(" ", 1)[1]) for ln in _trees(box.repo)]
    assert sorted(trees) == sorted([_real(box.repo), _real(wt)]) and len(before) == 1


def test_a3_a_sha_git_cannot_check_out_is_red_stage(box, monkeypatch):
    real_git = unattended._git

    def no_sha(cwd, *args):
        if args[:3] == ("worktree", "add", "--detach"):
            args = (*args[:-1], "0" * 40)
        return real_git(cwd, *args)
    monkeypatch.setattr(unattended, "_git", no_sha)
    _packet(box, "green-row", "`true` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert (row["state"], row["reason"]) == ("red", "stage")
    assert len(box.starts) == 1 and box.kind("continue") == [] and box.kind("accept") == []
    log = (box.dir / "log").read_text()
    assert "green-row: stage: " in log and "0" * 40 in log.split("green-row: stage: ", 1)[1]
    assert len(_trees(box.repo)) == 2


def test_r4_the_continuation_text():
    c = {"shell": "false", "status": "red", "exit": 1, "cut": False, "last": "",
         "expect": "exits 0", "main_exit": None, "main_last": None}
    text = unattended.continuation([c], "abc123")
    assert text.startswith("The packet's acceptance lines do not all hold yet; the loop ran them "
                           "in a fresh tree at abc123 after your turn")
    assert "- `false` returned exit 1, no output; it wants: exits 0\n" in text
    assert text.endswith(unattended.TAIL + "\n")


# ---- R2: the venv links (acceptance 4) ------------------------------------------------

def test_a4_venv_links_in_each_tree(box, monkeypatch):
    _main_commit(box, {".gitignore": (".venv-floor\n", 0o644)}, "ignores")
    for name in (".venv", ".venv-floor", ".venv-old"):
        (box.repo / name / "bin").mkdir(parents=True)
        py = box.repo / name / "bin" / "python"
        py.write_text("#!/bin/sh\nexit 0\n")
        py.chmod(0o755)
    names = (".venv", ".venv-floor", ".venv-old")
    seen = []
    real_run = unattended.run_lines

    def spy(wt, lines, env, pick=None):
        seen.append({n: os.readlink(os.path.join(wt, n)) if os.path.islink(os.path.join(wt, n))
                     else None for n in names})
        return real_run(wt, lines, env, pick)
    monkeypatch.setattr(unattended, "run_lines", spy)
    _packet(box, "green-row", "`./.venv-floor/bin/python -c pass` exits 0; `true` as main")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    (row,) = box.kind("row")
    assert row["state"] == "built", row
    wt = box.repo / ".claude" / "worktrees" / "green-row"
    want = {".venv": str(box.repo / ".venv"), ".venv-floor": str(box.repo / ".venv-floor"),
            ".venv-old": None}
    staged = {n: os.readlink(wt / n) if os.path.islink(wt / n) else None for n in names}
    assert seen == [want, want] and staged == want            # the pin tree, the sha tree
    assert not unattended.dirty(wt)
    log = (box.dir / "log").read_text().splitlines()
    assert len([ln for ln in log if ".venv-old" in ln]) == 1


def test_r2_a_name_the_tree_holds_is_left(tmp_path):
    repo, tree = tmp_path / "r", tmp_path / "t"
    (repo / ".venv").mkdir(parents=True)
    (repo / ".venv-file").write_text("x")                  # not a directory: never linked
    tree.mkdir()
    (tree / ".venv").write_text("mine")
    noted = []
    unattended.link_venvs(repo, tree, noted.append)
    assert (tree / ".venv").read_text() == "mine" and not os.path.lexists(tree / ".venv-file")
    assert noted == []


# ---- R5: unbounded (acceptance 5) ----------------------------------------------------

REFUSED = ["make check; echo $?", "make test 2>&1 | tail -1", "env X=1 make x", "sh -c 'make x'",
           "for f in a b; do make $f; done", "d=$(make -n x)", "/usr/bin/make x",
           "(cd x && gmake)", "echo 'open", "grep 'make' x",
           "bash -c \"sh -c 'make'\"", "bash -lc 'make x'"]
PASSED = ["grep -c 'make check' README.md", "go test ./cmd/relay -run X",
          "./.venv/bin/python -m pytest -q tests/test_x.py", "true", "echo maker; makefile x"]


def test_a5_unbounded():
    for line in REFUSED:
        why = unattended.unbounded(line)
        assert why and "gate queue" in why and "land step runs the check" in why, line
    for line in PASSED:
        assert unattended.unbounded(line) == "", line
    assert "split" in unattended.unbounded("echo 'open")


def test_r5_depth_three():
    def nest(n):
        s = "make"
        for _ in range(n):
            s = "sh -c " + unattended.shlex.quote(s)
        return s
    assert all(unattended.unbounded(nest(n)) for n in range(4))
    assert unattended.unbounded(nest(4)) == ""                # past depth 3, not read


# ---- R6, R7: the row refused before its stage (acceptance 6) ---------------------------

def test_a6_an_unbounded_row_is_refused_before_its_stage(box, monkeypatch):
    stub = box.tmp / "stub"
    stub.mkdir()
    ran = box.tmp / "make-ran"
    (stub / "make").write_text(f"#!/bin/sh\ntouch {ran}\nexit 0\n")
    (stub / "make").chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub}{os.pathsep}{os.environ['PATH']}")
    _packet(box, "green-row", "`make check; echo $?` reads 0")
    _packet(box, "max-row", "`true` exits 0")
    said = []
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "max-row"],
           say=lambda s: said.append((s, box.log.exists())))
    first, second = box.kind("row")
    assert (first["row"], first["state"], first["reason"]) == ("green-row", "refused", "unbounded")
    assert (second["row"], second["state"]) == ("max-row", "built")
    assert not (box.repo / ".claude" / "worktrees" / "green-row").exists()
    assert _git(box.repo, "branch", "--list", "green-row") == ""
    assert [s["cwd"] for s in box.starts] == [str(box.repo / ".claude" / "worktrees" / "max-row")]
    assert not ran.exists()
    early = [(s, spawned) for s, spawned in said if s.startswith("green-row:") and "unbounded" in s
             and "refused" not in s.split(":", 2)[1]]
    assert len(early) == 1 and early[0][1] is False
    assert [s for s, _ in said if s.startswith("max-row:") and "refused" not in s] == ["max-row: built"]
    log = (box.dir / "log").read_text()
    assert "green-row: unbounded: item 1 `make check; echo $?`: " in log
    assert len(_trees(box.repo)) == 2


def test_r7_an_unreadable_cell_is_said_early(box):
    (box.repo / "design" / "packets" / "green-row.md").write_text("# Packet green-row\n")
    said = []
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row", "parked-row"],
           say=lambda s: said.append((s, box.log.exists())))
    early = [s for s, _ in said if s.startswith("green-row:") and "no acceptance row" in s]
    assert len(early) == 1
    assert not [s for s, _ in said if s.startswith("parked-row:") and "acceptance" in s]
    (row, parked) = box.kind("row")
    assert (row["state"], row["reason"]) == ("refused", "acceptance")
    assert len([e for e in box.ledger if e["kind"] not in ("row", "stop")]) == 0


def test_r6_the_long_line_is_cut_at_80(box):
    long = "make " + "x" * 100
    _packet(box, "green-row", f"`{long}` exits 0")
    box.go([{"stream": "green.jsonl", "commit": True}], ["green-row"])
    log = (box.dir / "log").read_text()
    assert f"item 1 `{long[:80]}`: " in log and long[:81] not in log
