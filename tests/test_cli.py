"""The CLI seam had zero coverage; a one-word AttributeError in the flagship
command shipped because of it. These drive main() end to end."""

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from claude_session import budget, cli, config, sessionconfig

SID = "cli-sess-0000-1111-2222"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    config.ensure_dirs()


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture
def seed(monkeypatch):
    """Stand in for the meter: the zone's input is the caller's used_pct."""
    from claude_session import hooks
    def _seed(used_pct):
        monkeypatch.setattr(hooks, "used_pct", lambda *a, **k: used_pct)
    return _seed


# ---- the crash that shipped -------------------------------------------------

@pytest.mark.parametrize("used", [10, 50, 85, 91, 93, 97, 100, None])
def test_budget_renders_in_every_zone(used, seed):
    seed(used)
    rc, out, err = run("budget")
    assert rc == 0, err
    assert "Traceback" not in err
    zone = budget.zone_for(used, budget.effective_policy(8.0, budget.Policy()))
    assert f"zone       {zone}" in out
    assert "%" not in out and "reset" not in out   # no window arithmetic


# ---- one source of truth for the reserve ------------------------------------

def test_reserve_pct_has_one_source_of_truth(seed):
    """budget and the hooks must agree on the reserve floor."""
    from claude_session import hooks
    cfgs = sessionconfig.load_configs()
    cfgs["balanced"].reserve_pct = 15.0
    sessionconfig.save_configs(cfgs)
    seed(86)                                            # floor is now 85
    rc, out, _ = run("budget")
    assert "zone       reserve" in out
    assert hooks.state()[1] == budget.RESERVE


def test_bigger_reserve_is_never_silently_clamped():
    """Asking for reserve 15 used to fail validation against the hardcoded 90
    wind-down and fall back to 8 -- a SMALLER reserve than asked for."""
    pol = budget.effective_policy(15.0, budget.Policy())
    assert pol.reserve_pct == 15.0 and pol.reserve_floor == 85.0
    assert pol.winddown_pct <= 85.0 and pol.notice_pct < pol.winddown_pct


# ---- set semantics ----------------------------------------------------------

def test_set_launch_key_does_not_promise_next_start():
    rc, out, _ = run("set", "model", "opus")
    assert rc == 0
    assert "will NOT be applied by the next `start`" in out
    assert "/model opus" in out


def test_set_config_without_save_is_refused():
    rc, _, err = run("set", "posture", "deny", "--config", "review")
    assert rc == 1 and "--save" in err


def test_set_rejects_non_settable_and_invalid():
    rc, _, err = run("set", "name", "renamed")
    assert rc == 1 and "not a settable key" in err
    rc, _, err = run("set", "permission_mode", "plan-mode", "--save", "--config", "frontier")
    assert rc == 1 and "permission_mode must be one of" in err
    rc, _, err = run("set", "setting_sources", "project", "--save", "--config", "frontier")
    assert rc == 1 and "user" in err
    # and the stored config was not bricked
    assert sessionconfig.load_configs()["frontier"].permission_mode is None


def test_set_notes_none_is_the_literal_string():
    rc, _, _ = run("set", "notes", "none", "--save", "--config", "frontier")
    assert rc == 0
    assert sessionconfig.load_configs()["frontier"].notes == "none"


# ---- checkpoint -------------------------------------------------------------

def test_checkpoint_outside_a_session_is_refused(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    rc, _, err = run("checkpoint")
    assert rc == 1 and "no session" in err


def test_checkpoint_help_names_tracked_only():
    rc, out, _ = run("checkpoint", "--help")
    assert rc == 0
    assert "tracked files only" in out and "add -A" not in out


def test_checkpoint_commit_stages_tracked_only(tmp_path, monkeypatch):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    g("init", "-q"); g("config", "user.email", "t@" + "e.com"); g("config", "user.name", "T")
    (repo / "a.py").write_text("x=1\n"); g("add", "-A"); g("commit", "-q", "-m", "init")
    (repo / "a.py").write_text("x=2\n")
    (repo / ".env").write_text("AWS_SECRET=hunter2\n")          # untracked secret
    monkeypatch.chdir(repo)
    rc, out, err = run("checkpoint", "-c", "-m", "cp")
    assert rc == 0
    tracked = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout
    assert ".env" not in tracked
    assert "NOT committed" in err and ".env" in err


# ---- every subcommand has help; every error is actionable ------------------

def test_every_subcommand_has_help_or_is_internal():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    internal = {"hook"}
    for name, sp in sub.choices.items():
        if name in internal:
            continue
        assert any(ch.help for ch in sub._choices_actions if ch.dest == name), name
    for name in sub.choices:
        rc, out, _ = run(name, "--help")
        assert rc == 0 and "usage:" in out


def test_usage_line_hides_internal_subcommands():
    rc, out, _ = run("--help")
    assert "<command>" in out
    assert "{schedule," not in out


def test_docs_match_shipped_defaults():
    """The RUNBOOK's zone table and config table are the most drift-prone
    artefacts here, and the RUNBOOK is machine-rendered."""
    import pathlib, re
    runbook = (pathlib.Path(cli.__file__).parents[3] / "RUNBOOK.md").read_text()
    pol = budget.Policy()
    assert f"notice | {pol.notice_pct:.0f}%" in runbook
    assert f"wind-down | {pol.winddown_pct:.0f}%" in runbook
    assert f"reserve | {pol.reserve_floor:.0f}%" in runbook
    cfgs = sessionconfig.load_configs()
    for name in ("frontier", "balanced", "local", "local-only", "scratch", "review"):
        c = cfgs[name]
        row = next(l for l in runbook.splitlines() if l.startswith(f"| `{name}` |"))
        assert c.lane in row and c.posture in row
        if c.effort:
            assert c.effort in row


# ---- S19: checkpoint --respawn --charter, report --chains (respawn-r1 §3.2, §3.6) ----

import hashlib
import json
import os
import stat
import subprocess
import time
import uuid

from claude_session import charter, ledger, resolver

S19_HEAD = ("# Sitting 2026-10-10-1: r, c\n\n| item | value |\n|---|---|\n| goal | g |\n"
            "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n"
            "## Done-ness\n- [x] a\n\n## Handover\n- h\n\n")
NO_LAUNCHER = "respawn marked; no launcher runs this sitting: print your start line and stop"
LAUNCHER = "respawn marked; the launcher restarts this sitting after this turn ends"


def _charter_file(path, next_act="## Next act\nRESPAWN: the next act\n"):
    path.write_text(S19_HEAD + next_act)
    return path


def _marker():
    return resolver.session_dir(resolver.state_dir(os.environ), SID) / "respawn.json"


def _counter():
    return sessionconfig.load_overlay().get("_prompts_since_checkpoint")


def test_s19_respawn_needs_its_charter(tmp_path):
    f = _charter_file(tmp_path / "c.md")
    rc, _, err = run("checkpoint", "--respawn")
    assert rc == 2 and "--charter" in err and len(err.splitlines()) == 1
    rc, _, err = run("checkpoint", "--charter", str(f))
    assert rc == 2 and "--respawn" in err and len(err.splitlines()) == 1
    assert not _marker().exists()
    rc, _, err = run("checkpoint", "--respawn", "--charter", str(f))  # the positive control
    assert rc == 0 and _marker().exists(), err


@pytest.mark.parametrize("first", ["RESPAWN: x", "RESPAWN. x", "RESPAWN at 80%"])
def test_s19_respawn_writes_the_marker(tmp_path, monkeypatch, first):
    f = _charter_file(tmp_path / "c.md", "## Next act\n%s\n" % first)
    monkeypatch.chdir(tmp_path)
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    rc, out, err = run("checkpoint", "--respawn", "--charter", "c.md")
    assert rc == 0, err
    d = json.loads(_marker().read_text())
    assert list(d) == ["session", "charter", "charter_sha256", "written", "chain"]
    assert (d["session"], d["charter"], d["chain"]) == (SID, str(f), None)
    assert d["charter_sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert isinstance(d["written"], float) and abs(d["written"] - time.time()) < 60
    assert stat.S_IMODE(_marker().stat().st_mode) == 0o600
    lines = out.splitlines()
    assert lines[0].startswith("checkpoint recorded") and lines[-1] == NO_LAUNCHER
    assert _counter() == 0


def test_s19_respawn_names_the_chain(tmp_path, monkeypatch):
    f = str(_charter_file(tmp_path / "c.md"))
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "orient-2026.10_10")
    rc, out, _ = run("checkpoint", "--respawn", "--charter", f)
    assert rc == 0 and out.splitlines()[-1] == LAUNCHER
    assert json.loads(_marker().read_text())["chain"] == "orient-2026.10_10"
    for bad in ("a b", "../x", "x" * 65, ""):
        monkeypatch.setenv("CLAUDE_SESSION_CHAIN", bad)
        rc, out, _ = run("checkpoint", "--respawn", "--charter", f)
        assert rc == 0 and out.splitlines()[-1] == NO_LAUNCHER, bad
        assert json.loads(_marker().read_text())["chain"] is None


# Criterion 3's five refused Next acts, a missing file, and a headless helper.
S19_REFUSED = [
    ("## Next act\nRespawn: x\n", "Respawn: x"),
    ("## Next act\nRESPAWNED\n", "RESPAWNED"),
    ("## Next act\nNext: RESPAWN\n", "Next: RESPAWN"),
    ("## Next act\n\n", "empty"),
    ("## Later\nRESPAWN: x\n", "no '## Next act'"),
    (None, "missing.md"),
    ("helper", "CLAUDE_SESSION_HELPER"),
]


@pytest.mark.parametrize("next_act,named", S19_REFUSED,
                         ids=["Respawn", "RESPAWNED", "later-in-line", "empty", "no-next-act",
                              "missing-file", "helper"])
def test_s19_respawn_refusals_write_nothing(tmp_path, monkeypatch, next_act, named):
    repo = tmp_path / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                  capture_output=True, text=True).stdout
    g("init", "-q"); g("config", "user.email", "t@" + "e.com"); g("config", "user.name", "T")
    (repo / "a.py").write_text("x=1\n"); g("add", "-A"); g("commit", "-q", "-m", "init")
    (repo / "a.py").write_text("x=2\n")
    monkeypatch.chdir(repo)
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    if next_act is None:
        f = tmp_path / "missing.md"
    elif next_act == "helper":
        f = _charter_file(tmp_path / "c.md")
        monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    else:
        f = _charter_file(tmp_path / "c.md", next_act)
    rc, out, err = run("checkpoint", "-c", "--respawn", "--charter", str(f))
    assert rc == 2 and named in err and len(err.splitlines()) == 1, err
    assert not _marker().exists() and _counter() == 5
    assert g("rev-list", "--count", "HEAD").strip() == "1"
    monkeypatch.delenv("CLAUDE_SESSION_HELPER", raising=False)    # the positive control
    rc, out, err = run("checkpoint", "-c", "--respawn", "--charter",
                       str(_charter_file(tmp_path / "good.md")))
    assert rc == 0 and _marker().exists() and _counter() == 0, err
    assert g("rev-list", "--count", "HEAD").strip() == "2"


def test_s19_respawn_takes_a_charter_check_refuses(tmp_path):
    f = tmp_path / "observer.md"
    f.write_text("# Observer\n\nState: kept by hand.\n\n## Next act\nRESPAWN: the next night\n")
    assert charter.check(f)                      # `charter check` refuses this shape
    rc, _, err = run("checkpoint", "--respawn", "--charter", str(f))
    assert rc == 0 and _marker().exists(), err


def test_s19_respawn_marker_holds_no_next_act_text(tmp_path):
    token = "tok-" + uuid.uuid4().hex
    f = _charter_file(tmp_path / "c.md", "## Next act\nRESPAWN: %s\n" % token)
    rc, out, err = run("checkpoint", "--respawn", "--charter", str(f))
    assert rc == 0 and _marker().exists(), err
    assert token not in out + err
    state = resolver.state_dir(os.environ)
    assert not [p for p in state.rglob("*") if p.is_file() and token.encode() in p.read_bytes()]


def _chain_lines(state):
    with ledger.path(state).open("a") as fh:
        fh.write(json.dumps({"kind": "restart", "chain": "orient", "seq": 1,
                             "at": "2026-10-09T23:00:00+00:00", "from_session": "u1",
                             "to_session": "u2", "ended_by": "launcher", "restarts_24h": 1,
                             "cap": 12}) + "\n")
        fh.write(json.dumps({"kind": "stop", "chain": "orient",
                             "at": "2026-10-10T02:00:00+00:00", "session": "u2",
                             "reason": "no-marker", "exit_status": 0, "restarts": 1}) + "\n")


def test_s19_report_ignores_chain_lines():
    state = resolver.state_dir(os.environ)
    ledger.append(state, {"session": "s1", "ended": "2026-10-10T01:00:00+00:00", "turns": 3})
    before = [run("report"), run("report", "--json")]
    assert before[0][0] == 0 and before[1][0] == 0
    _chain_lines(state)
    assert [run("report"), run("report", "--json")] == before


def test_s19_report_chains():
    state = resolver.state_dir(os.environ)
    ledger.append(state, {"session": "s1", "ended": "2026-10-10T01:00:00+00:00"})
    rc, out, err = run("report", "--chains")
    assert rc == 2 and out == "" and len(err.splitlines()) == 1
    _chain_lines(state)
    rc, out, _ = run("report", "--chains")
    assert rc == 0 and "launcher" in out and "no-marker" in out and "s1" not in out
    rc, out, _ = run("report", "--chains", "--json")
    assert rc == 0 and [r["kind"] for r in json.loads(out)] == ["restart", "stop"]
    rc, out, _ = run("report", "--chains", "--json", "--since", "2026-10-10")
    assert rc == 0 and [r["kind"] for r in json.loads(out)] == ["stop"]


def test_s19_profile_refuses_a_bad_respawn_value(tmp_path, monkeypatch):
    d = tmp_path / resolver.REPO_DIR
    d.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    (d / "config.yaml").write_text("session:\n  respawn: {cap: 3}\n")
    rc, out, err = run("profile", "frontier")             # the positive control
    assert rc == 0 and "respawn" in out and "cap: 3" in out, err
    (d / "config.yaml").write_text("session:\n  respawn: {cap: -1}\n")
    rc, out, err = run("profile", "frontier")
    assert rc == 2 and "respawn.cap" in err and out == ""


# ---- S21: `agentik session rules` --------------------------------------------

def test_s21_verb_prints_both_resolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out, err = run("rules")
    assert rc == 0 and err == "", err
    assert "priority: on" in out and "pacing: on" in out
    assert "S1 harm: a reproduced bug" in out and "S4 the rest: review notes" in out
    assert "never by how sure or cheap its fix is" in out
    assert "WAITING <n>: <what>; <how to tell>" in out and "1800 s or more" in out
    rc, out, _ = run("--help")
    assert "rules" in out


def test_s21_verb_reads_the_layers(tmp_path, monkeypatch):
    d = tmp_path / resolver.REPO_DIR
    d.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    (d / "config.yaml").write_text("session:\n  priority: {enabled: false}\n"
                                   "  pacing: {fallback: 2400}\n")
    rc, out, err = run("rules")
    assert rc == 0 and "priority: off" in out and "S1 harm" not in out, err
    assert "one fallback of 2400 s or more" in out
    (d / "config.yaml").write_text("session:\n  pacing: {waiting: 0}\n")
    rc, out, err = run("rules")
    assert rc == 2 and "pacing.waiting" in err and out == ""


# ---- S30: `rules` names the prompt cache's lifetime ---------------------------

def test_s30_verb_names_the_lifetime(tmp_path, monkeypatch):
    import json
    import os
    from datetime import datetime, timedelta, timezone

    from claude_session import admission
    monkeypatch.chdir(tmp_path)
    rc, out, err = run("rules")
    assert rc == 0 and err == "", err
    assert ("  6. the prompt cache's lifetime is not known here (no usage reading and no "
            "override): on 1h") in out
    monkeypatch.setenv("CLAUDE_CODE_PROMPT_CACHE_TTL", "5m")
    rc, out, _ = run("rules")
    assert ("  6. the prompt cache lives 5m here (CLAUDE_CODE_PROMPT_CACHE_TTL): any wait past "
            "about 270 s misses it anyway") in out
    monkeypatch.delenv("CLAUDE_CODE_PROMPT_CACHE_TTL")
    d = admission.directory(os.environ)
    d.mkdir(parents=True)
    t = datetime.now(timezone.utc) + timedelta(hours=2)
    (d / "band.json").write_text(json.dumps({"mode": "observe", "P": 41,
                                             "resetsAt": t.isoformat(timespec="seconds")}))
    rc, out, _ = run("rules")
    assert ("  6. the prompt cache lives 1h here (within plan usage, 5h 41%): an idle wait "
            "(items 2, 4 and 5) wakes at most 3300 s apart") in out


def test_s30_f1_verb_reads_the_project_dir_s_settings(tmp_path, monkeypatch):
    import json
    (tmp_path / "sub").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"promptCacheTtl": "5m"}))
    monkeypatch.chdir(tmp_path / "sub")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc, out, _ = run("rules")
    assert rc == 0 and "  6. the prompt cache lives 5m here (promptCacheTtl, project settings)" in out


# ---- S22: a respawn refuses an uncommitted charter (F13) --------------------

def _s22_remedy(f):
    """The refusal's remedy for a plain absolute path (the fix round: F1 and F2)."""
    return (f"git -C {f.parent} add -- {f.name} && "
            f'git -C {f.parent} commit -m "charter: the exit taken" -- {f.name}')


def _s22_repo(tmp_path, monkeypatch):
    """A repo whose charter c.md (RESPAWN Next act) and a.py are committed; the
    checkpoint counter stands at 5."""
    repo = tmp_path / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                  capture_output=True, text=True).stdout
    g("init", "-q"); g("config", "user.email", "t@" + "e.com"); g("config", "user.name", "T")
    (repo / "a.py").write_text("x=1\n")
    f = _charter_file(repo / "c.md")
    g("add", "-A"); g("commit", "-q", "-m", "init")
    monkeypatch.chdir(repo)
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    return repo, g, f


def _s22_closed(f):
    f.write_text(f.read_text().replace("- h\n", "- h\n- exit taken: RESPAWN; meter unknown\n"))


def _s22_refused(rc, err, f, g):
    assert rc == 2 and len(err.splitlines()) == 1, err
    assert err.strip().endswith(f"{f} is not committed; commit it first: {_s22_remedy(f)}"), err
    assert not _marker().exists() and _counter() == 5
    assert g("rev-list", "--count", "HEAD").strip() == "1"


def test_s22_respawn_refuses_a_modified_charter(tmp_path, monkeypatch):
    repo, g, f = _s22_repo(tmp_path, monkeypatch)
    _s22_closed(f)
    rc, _, err = run("checkpoint", "--respawn", "--charter", str(f))
    _s22_refused(rc, err, f, g)
    g("add", "c.md")                                                # staged reads a line too
    rc, _, err = run("checkpoint", "--respawn", "--charter", "c.md")
    _s22_refused(rc, err, f, g)


def test_s22_respawn_refuses_an_untracked_charter(tmp_path, monkeypatch):
    repo, g, _ = _s22_repo(tmp_path, monkeypatch)
    f = _charter_file(repo / "new.md")
    rc, _, err = run("checkpoint", "--respawn", "--charter", str(f))
    _s22_refused(rc, err, f, g)


def test_s22_respawn_takes_a_committed_charter(tmp_path, monkeypatch):
    repo, g, f = _s22_repo(tmp_path, monkeypatch)
    _s22_closed(f)
    g("commit", "-q", "-m", "charter: the exit taken", "--", "c.md")
    rc, out, err = run("checkpoint", "--respawn", "--charter", str(f))
    assert rc == 0 and _marker().exists() and _counter() == 0, err
    assert "unknown" not in err and out.splitlines()[-1] == NO_LAUNCHER


def test_s22_respawn_commit_takes_a_tracked_charter(tmp_path, monkeypatch):
    repo, g, f = _s22_repo(tmp_path, monkeypatch)
    _s22_closed(f)
    rc, out, err = run("checkpoint", "-c", "-m", "cp", "--respawn", "--charter", str(f))
    assert rc == 0 and _marker().exists() and _counter() == 0, err
    assert g("rev-list", "--count", "HEAD").strip() == "2"
    assert g("show", "HEAD:c.md") == f.read_text() and g("status", "--porcelain") == ""


def test_s22_respawn_commit_refuses_an_untracked_charter(tmp_path, monkeypatch):
    repo, g, _ = _s22_repo(tmp_path, monkeypatch)
    (repo / "a.py").write_text("x=2\n")                     # a tracked change -c would take
    f = _charter_file(repo / "new.md")
    rc, _, err = run("checkpoint", "-c", "-m", "cp", "--respawn", "--charter", str(f))
    _s22_refused(rc, err, f, g)
    assert g("status", "--porcelain", "--", "a.py").startswith(" M ")



@pytest.mark.parametrize("where", ["untracked", "second-repo"])
def test_s22_refusal_remedy_runs_verbatim(tmp_path, monkeypatch, where):
    """F1 and F2: the remedy the refusal names, run through a shell from the cwd, commits
    the charter (untracked; or modified, from a cwd in a second repo); the respawn then
    passes."""
    repo, g, f = _s22_repo(tmp_path, monkeypatch)
    cwd = repo
    if where == "untracked":
        f = _charter_file(repo / "new.md")
    else:
        _s22_closed(f)
        cwd = tmp_path / "B"
        cwd.mkdir()
        subprocess.run(["git", "init", "-q", str(cwd)], check=True)
        monkeypatch.chdir(cwd)
    rel = os.path.relpath(f, cwd)
    rc, _, err = run("checkpoint", "--respawn", "--charter", rel)
    assert rc == 2 and not _marker().exists(), err
    remedy = err.strip().split("commit it first: ", 1)[1]
    r = subprocess.run(["sh", "-c", remedy], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert g("status", "--porcelain", "--", f.name) == ""
    assert g("log", "-1", "--format=%s").strip() == "charter: the exit taken"
    rc, _, err = run("checkpoint", "--respawn", "--charter", rel)
    assert rc == 0 and _marker().exists(), err

@pytest.mark.parametrize("stub", ["echo 'fatal: broken' >&2; exit 1", "exec sleep 5"],
                         ids=["fails", "times-out"])
def test_s22_respawn_git_unknown_goes_on(tmp_path, monkeypatch, stub):
    from claude_session import gitinfo
    repo, g, f = _s22_repo(tmp_path, monkeypatch)
    _s22_closed(f)                                  # git would read a line, were it asked
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "git").write_text("#!/bin/sh\n" + stub + "\n")
    (bin_ / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    monkeypatch.setattr(gitinfo, "_TIMEOUT", 0.5)
    rc, out, err = run("checkpoint", "--respawn", "--charter", str(f))
    assert rc == 0 and _marker().exists() and _counter() == 0, err
    named = [l for l in err.splitlines() if "unknown" in l]
    assert len(named) == 1 and str(f) in named[0] and "not committed" not in err, err


# ---- S37: status says a respawn hold -------------------------------------------------

@pytest.mark.parametrize("case", ["held", "no-file", "other-session", "no-chain"])
def test_s37_status_says_a_respawn_hold(case, tmp_path, monkeypatch):
    """`status` prints `respawn held: <reason> since <HH:MM>` when this session's chain
    has held.json naming this session, and nothing otherwise."""
    from claude_session import hooks
    env = dict(os.environ)
    repo = tmp_path / "repo"
    repo.mkdir()
    hooks.session_start({"session_id": SID, "cwd": str(repo)}, env)
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "meter", "under-80.jsonl")
    hooks.post_tool_use({"session_id": SID, "transcript_path": fixture}, env)
    if case != "no-chain":
        monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "c1")
    since = time.mktime((2026, 10, 29, 7, 5, 0, 0, 0, -1))
    if case != "no-file":
        home = resolver.state_dir(env) / "respawn" / "c1"
        home.mkdir(parents=True, exist_ok=True)
        who = "someone-else" if case == "other-session" else SID
        (home / "held.json").write_text(json.dumps(
            {"reason": "floor", "since": since, "session": who}))
    rc, out, _ = run("status")
    lines = out.splitlines()
    assert rc == 0 and lines[0].startswith(f"session {SID}"), out
    held = [line for line in lines if line.startswith("respawn held")]
    assert held == (["respawn held: floor since 07:05"] if case == "held" else []), out


# ---- S39: `checkpoint --respawn --state` -------------------------------------

S39_STATE = ("# State for the successor of cli-sess, 2026-10-29 21:40\n\n## Helpers\n- none\n\n"
             "## Gates\n- none\n\n## Last acts\n- e3d82cb the packet\n\n## Read first\n"
             "- RUNBOOK.md lines 320-380\n- read nothing else before the first act\n")
S39_NONE = "no --state: the successor orients from the charter alone"


def _s39_home(name="s39-chain"):
    return resolver.state_dir(os.environ) / "respawn" / name


def _s39_files(tmp_path, monkeypatch, text=S39_STATE):
    for k in ("CLAUDE_SESSION_DEPTH", "RELAY_ROW", "CLAUDE_SESSION_HELPER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    f = _charter_file(tmp_path / "c.md")
    s = tmp_path / "s.md"
    s.write_text(text)
    sessionconfig.save_overlay({"_prompts_since_checkpoint": 5})
    return str(f), str(s)


def test_s39_state_is_copied_to_the_chain_home(tmp_path, monkeypatch):
    f, s = _s39_files(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "s39-chain")
    rc, out, err = run("checkpoint", "--respawn", "--charter", f, "--state", s)
    assert rc == 0, err
    home, raw = _s39_home(), S39_STATE.encode()
    assert (home / "state.md").read_bytes() == raw
    d = json.loads((home / "state.json").read_text())
    assert list(d) == ["from_session", "written", "sha256", "bytes"]
    assert (d["from_session"], d["sha256"], d["bytes"]) == (
        SID, hashlib.sha256(raw).hexdigest(), len(raw))
    assert abs(d["written"] - time.time()) < 60
    m = json.loads(_marker().read_text())                   # the marker's keys stand
    assert list(m) == ["session", "charter", "charter_sha256", "written", "chain"]
    assert out.splitlines()[-1] == LAUNCHER and S39_NONE not in err
    assert f"state copied to {home / 'state.md'} ({len(raw)} B)" in out


@pytest.mark.parametrize("text,named", [
    (S39_STATE.replace("## Gates\n- none\n\n", ""), "sections"),
    (S39_STATE.replace("- e3d82cb the packet", "- the packet"), "commit sha"),
    (S39_STATE + "- " + "x" * 8192 + "\n", "ceiling"),
], ids=["sections", "sha", "ceiling"])
def test_s39_a_faulty_state_refuses_the_checkpoint(tmp_path, monkeypatch, text, named):
    f, s = _s39_files(tmp_path, monkeypatch, text)
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "s39-chain")
    rc, out, err = run("checkpoint", "--respawn", "--charter", f, "--state", s)
    assert rc == 2 and named in err and out == "", err
    assert not _marker().exists() and not _s39_home().exists() and _counter() == 5


def test_s39_state_refusals_write_nothing(tmp_path, monkeypatch):
    f, s = _s39_files(tmp_path, monkeypatch)
    rc, _, err = run("checkpoint", "--state", s)
    assert rc == 2 and "--respawn" in err and len(err.splitlines()) == 1, err
    rc, _, err = run("checkpoint", "--respawn", "--charter", f, "--state",
                     str(tmp_path / "missing.md"))
    assert rc == 2 and "missing.md" in err and len(err.splitlines()) == 1, err
    (tmp_path / "bin.md").write_bytes(b"\xff\xfe")
    rc, _, err = run("checkpoint", "--respawn", "--charter", f, "--state",
                     str(tmp_path / "bin.md"))
    assert rc == 2 and "UTF-8" in err, err
    assert not _marker().exists() and _counter() == 5


def test_s39_without_state_says_so_and_clears_a_stale_one(tmp_path, monkeypatch):
    f, s = _s39_files(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "s39-chain")
    assert run("checkpoint", "--respawn", "--charter", f, "--state", s)[0] == 0
    assert (_s39_home() / "state.json").exists()
    rc, out, err = run("checkpoint", "--respawn", "--charter", f)
    assert rc == 0 and out.splitlines()[-1] == LAUNCHER, err
    assert err.splitlines().count(S39_NONE) == 1
    assert not (_s39_home() / "state.json").exists()
    assert not (_s39_home() / "state.md").exists()


@pytest.mark.parametrize("k,v", [("RELAY_ROW", "s39"), ("CLAUDE_SESSION_DEPTH", "1")])
def test_s39_a_relay_or_started_sitting_clears_nothing(tmp_path, monkeypatch, k, v):
    f, s = _s39_files(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_SESSION_CHAIN", "s39-chain")
    assert run("checkpoint", "--respawn", "--charter", f, "--state", s)[0] == 0
    monkeypatch.setenv(k, v)
    rc, _, err = run("checkpoint", "--respawn", "--charter", f)
    assert rc == 0 and err.splitlines().count(S39_NONE) == 1, err
    assert (_s39_home() / "state.json").exists() and (_s39_home() / "state.md").exists()


def test_s39_state_without_a_chain_stays_with_the_session(tmp_path, monkeypatch):
    f, s = _s39_files(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_SESSION_CHAIN", raising=False)
    rc, out, err = run("checkpoint", "--respawn", "--charter", f, "--state", s)
    assert rc == 0 and out.splitlines()[-1] == NO_LAUNCHER, err
    copy = resolver.session_dir(resolver.state_dir(os.environ), SID) / "state.md"
    assert copy.read_bytes() == S39_STATE.encode()
    assert "will not find it" in err and str(copy) in err
    assert not (resolver.state_dir(os.environ) / "respawn").exists()


def test_s39_a_respawn_close_names_the_state_as_optional(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    p = _charter_file(tmp_path / "c.md")
    rc, out, err = run("charter", "close", "--exit", "RESPAWN", "c.md")
    assert rc == 0, err
    assert out.splitlines()[-1] == ("then: agentik-session checkpoint --respawn --charter "
                                    + str(p.resolve()))
    assert "--state <file>" in err and "optional" in err
    assert 'RUNBOOK "Restarting a sitting"' in err and "--help" not in err


# ---- gate run, wait, status (S38) --------------------------------------------

def test_gate_run_wait_status_in_process(tmp_path, monkeypatch):
    import pathlib
    from claude_session import gate, resolver
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    rc, out, _ = run("gate", "run", str(tmp_path), "--label", "t", "--",
                     "sh", "-c", "echo hi; exit 3")
    assert rc == 0 and out.startswith("queued ")
    gid = out.split()[1]
    root = resolver.state_dir(os.environ)
    assert out.strip() == (f"queued {gid} position 1 repo {os.path.realpath(tmp_path)} caller "
                           f"none; result {root / 'gate' / gid / 'result.json'}")
    rc, out, _ = run("gate", "status")
    assert rc == 0 and out.splitlines()[0].startswith(f"queued {gid} ")
    assert out.splitlines()[-1] == "runner: none"
    assert gate.serve(root, gate.Fx(idle=0, poll=0.01, grace=0.01)) == 0
    rc, out, _ = run("gate", "wait", gid)
    assert rc == 0 and out.startswith(f"gate {gid} {os.path.realpath(tmp_path)}: exit 3 in 0 min; log ")
    assert "hi" in pathlib.Path(root / "gate" / gid / "log").read_text()
    rc, out, _ = run("gate", "wait", gid, "--json")
    assert rc == 0 and json.loads(out)["exit"] == 3
    rc, out, _ = run("gate", "status", "--json")
    assert rc == 0 and json.loads(out)["done"][0]["id"] == gid


def test_gate_refusals_exit_2(tmp_path, monkeypatch):
    from claude_session import gate
    monkeypatch.setattr(gate, "spawn_serve", lambda root, popen=None: False)
    assert run("gate", "wait", "nosuch")[0] == 2
    assert run("gate", "run", str(tmp_path / "gone"), "--", "true")[0] == 2
    assert run("gate", "run", str(tmp_path), "--session", "../x", "--", "true")[0] == 2
    assert run("gate", "run", str(tmp_path))[0] == 2
