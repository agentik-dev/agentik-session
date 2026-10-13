import subprocess

import pytest

from claude_session import gitinfo


def git(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    git(d, "init", "-q")
    git(d, "config", "user.email", "t@" + "example.com")
    git(d, "config", "user.name", "T")
    (d / "a.py").write_text("print('one')\n")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "init")
    return d


def test_committed_work_is_visible(repo):
    """The predecessor diffed HEAD *after* the run, so a run that committed its
    work reported 'no changes detected'. Diffing the pre-run sha fixes it."""
    pre = gitinfo.baseline(str(repo)).head
    (repo / "a.py").write_text("print('two')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "the agent's work")

    # Prove the old approach fails on this exact case.
    assert git(repo, "diff", "--stat", "HEAD").stdout.strip() == ""

    ch = gitinfo.changes_since(str(repo), pre)
    assert not ch.empty
    assert len(ch.commits) == 1 and "the agent's work" in ch.commits[0]
    assert "print('two')" in ch.patch


def test_new_file_content_is_captured(repo):
    pre = gitinfo.baseline(str(repo)).head
    (repo / "brand_new.py").write_text("VALUE = 42\n")
    ch = gitinfo.changes_since(str(repo), pre)
    assert ch.untracked == ["brand_new.py"]
    assert "VALUE = 42" in ch.patch      # `git diff <sha>` alone would miss this
    assert not ch.empty


def test_uncommitted_edit_is_visible(repo):
    pre = gitinfo.baseline(str(repo)).head
    (repo / "a.py").write_text("print('edited')\n")
    ch = gitinfo.changes_since(str(repo), pre)
    assert "print('edited')" in ch.patch


def test_no_changes_reports_empty(repo):
    pre = gitinfo.baseline(str(repo)).head
    assert gitinfo.changes_since(str(repo), pre).empty


def test_work_on_a_new_branch_is_visible(repo):
    pre = gitinfo.baseline(str(repo)).head
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / "a.py").write_text("print('branch')\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "on a branch")
    ch = gitinfo.changes_since(str(repo), pre)
    assert not ch.empty and len(ch.commits) == 1


def test_baseline_reports_dirty(repo):
    assert gitinfo.baseline(str(repo)).dirty is False
    (repo / "a.py").write_text("dirty\n")
    b = gitinfo.baseline(str(repo))
    assert b.dirty is True and b.branch in ("main", "master")


def test_non_repo_is_handled(tmp_path):
    ch = gitinfo.changes_since(str(tmp_path), None)
    assert ch.empty and ch.note


def test_canonical_project_is_the_toplevel(repo):
    sub = repo / "pkg" / "deep"
    sub.mkdir(parents=True)
    import os
    assert gitinfo.canonical_project(str(sub)) == os.path.realpath(str(repo))



def test_pre_existing_dirty_edit_is_not_attributed_to_the_run(repo):
    """The scheduled-run premise: you stopped mid-edit because the window
    closed. That edit is yours, not the run's, and NO-OP must stay reachable."""
    (repo / "a.py").write_text("print('my half-finished edit')\n")
    (repo / "scratch.txt").write_text("my notes\n")
    base = gitinfo.baseline(str(repo))
    assert base.dirty and set(base.pre_dirty) == {"a.py", "scratch.txt"}

    # the run does NOTHING
    ch = gitinfo.changes_since(str(repo), base.head, base.pre_dirty)
    assert ch.empty, (ch.patch, ch.untracked)
    assert set(ch.excluded) == {"a.py", "scratch.txt"}


def test_run_editing_an_already_dirty_file_is_attributed(repo):
    (repo / "a.py").write_text("mine\n")
    base = gitinfo.baseline(str(repo))
    (repo / "a.py").write_text("mine\nplus the run's line\n")   # run edits it
    ch = gitinfo.changes_since(str(repo), base.head, base.pre_dirty)
    assert not ch.empty
    assert "plus the run's line" in ch.patch
    assert ch.excluded == []


def test_untracked_files_with_spaces_and_dirs_are_captured(repo):
    pre = gitinfo.baseline(str(repo)).head
    (repo / "new file.py").write_text("SPACED = 1\n")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "mod.py").write_text("NESTED = 2\n")
    ch = gitinfo.changes_since(str(repo), pre)
    assert "new file.py" in ch.untracked and "pkg/mod.py" in ch.untracked
    assert "SPACED = 1" in ch.patch and "NESTED = 2" in ch.patch


# ---- review r6 E2, ADV6-5: unknown is never clean; blobs by one --stdin-paths ----

import io
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout

from claude_session import cli, config, ledger

REAL_GIT = shutil.which("git")


def _exe(path, body):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


@pytest.fixture
def slow_git(tmp_path, monkeypatch):
    """A `git` that outlives the timeout, first on PATH."""
    bin_ = tmp_path / "slowbin"
    bin_.mkdir()
    _exe(bin_ / "git", "exec /bin/sleep 3\n")
    monkeypatch.setattr(gitinfo, "_TIMEOUT", 0.3)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")


@pytest.fixture
def counting_git(tmp_path, monkeypatch):
    """The real git behind a wrapper that logs one line per call."""
    bin_ = tmp_path / "countbin"
    bin_.mkdir()
    log = tmp_path / "git-calls"
    _exe(bin_ / "git", f'echo "$*" >> "{log}"\nexec "{REAL_GIT}" "$@"\n')
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    return lambda: log.read_text().splitlines() if log.exists() else []


def _checkpoint(monkeypatch, cwd):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "cli-sess-0000-1111-2222")
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(["checkpoint"])
    return rc, out.getvalue()


def test_unknown_when_git_status_times_out(repo, slow_git):
    b = gitinfo.baseline(str(repo))
    assert b.dirty is None and b.pre_dirty == {}


def test_unknown_when_git_status_fails(repo, tmp_path, monkeypatch):
    bin_ = tmp_path / "failbin"
    bin_.mkdir()
    _exe(bin_ / "git", 'case "$*" in *status*) echo boom >&2; exit 1;; esac\n'
                       f'exec "{REAL_GIT}" "$@"\n')
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    assert gitinfo.baseline(str(repo)).dirty is None
    assert gitinfo.tree_state(str(repo))[2] is None


def test_unknown_checkpoint_prints_unknown_never_clean(repo, slow_git, monkeypatch):
    rc, out = _checkpoint(monkeypatch, repo)
    assert rc == 0
    assert "unknown" in out
    assert "clean" not in out and "no changes" not in out and "dirty" not in out.replace(
        "unknown", "")


def test_unknown_ledger_dirty_stays_null(repo, slow_git):
    d = ledger.entry_for({"session_id": "g"}, project="p", profile="frontier",
                         cwd=repo, exit_reason="other")
    assert d["dirty"] is None


def test_unknown_checkpoint_on_a_known_tree_says_clean_or_dirty(repo, monkeypatch):
    rc, out = _checkpoint(monkeypatch, repo)
    assert rc == 0 and "tree is clean" in out
    (repo / "a.py").write_text("dirty\n")
    rc, out = _checkpoint(monkeypatch, repo)
    assert "tree is dirty" in out and "unknown" not in out


def test_unknown_outside_a_repo_is_not_a_tree(tmp_path, monkeypatch):
    d = tmp_path / "plain"
    d.mkdir()
    b = gitinfo.baseline(str(d))
    assert (b.is_repo, b.dirty) == (False, False)
    rc, out = _checkpoint(monkeypatch, d)
    assert rc == 0 and "tree" not in out


def test_stdin_paths_baseline_hashes_1500_files_in_at_most_3_git_calls(repo, counting_git):
    (repo / "a.py").write_text("print('edited')\n")
    many = repo / "many"
    many.mkdir()
    for i in range(1500):
        (many / f"f{i:04}.txt").write_text(f"{i}\n")
    b = gitinfo.baseline(str(repo))
    calls = counting_git()
    assert len(calls) <= 3, calls
    assert any("--stdin-paths" in c for c in calls)
    assert len(b.pre_dirty) == 1501 and b.dirty is True
    assert b.pre_dirty["many/f0007.txt"] == git(repo, "hash-object", "many/f0007.txt").stdout.strip()
    assert b.pre_dirty["a.py"] == git(repo, "hash-object", "a.py").stdout.strip()
    assert b.head and b.branch in ("main", "master")


def test_stdin_paths_checkpoint_needs_only_git_status(repo, counting_git, monkeypatch):
    for i in range(1500):
        (repo / f"u{i:04}.txt").write_text(f"{i}\n")
    rc, out = _checkpoint(monkeypatch, repo)
    calls = counting_git()
    assert rc == 0 and "tree is dirty" in out
    assert len(calls) <= 3 and not any("hash-object" in c for c in calls), calls


def test_stdin_paths_changes_since_is_not_one_fork_per_path(repo, counting_git):
    for i in range(200):
        (repo / f"u{i:04}.txt").write_text(f"{i}\n")
    base = gitinfo.baseline(str(repo))
    before = len(counting_git())
    ch = gitinfo.changes_since(str(repo), base.head, base.pre_dirty)
    assert ch.empty and len(ch.excluded) == 200
    assert len(counting_git()) - before < 20
