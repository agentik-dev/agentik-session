"""Packet land5b-install: `--install` on `gate publish` and `gate land`. After a repo's publish
turn the caller's own process installs what was pushed: the plugin its plugin.json names, by
`claude plugin marketplace update` and `claude plugin update`, then a Makefile's `install` as a
gate job, held while a relay run, an unattended run or a gate job of the repo is live. Each case
is land5-publish's made-up `crate`; `claude` and `ps` are stubs on its PATH, Claude Code's
installed-plugins file is under a made-up config folder, and the gate's queue is the temp state
root's. No case starts a real `claude`, reads the live process list or pushes but to the bare
repo beside the crate."""

import json
import os
import signal
import sys
import time

import pytest

from claude_session import gate
from test_land5_publish import CHECK, Crate, land_argv, lc, line, run  # noqa: F401 (lc: fixture)

PROBE = "AGENTIK_PRUNE_PROBE"
# `claude`: its argv to <tmp>/claude-log and <tmp>/git-argv (so the order against the git
# recorder's push reads), and on `plugin update <id>` the id's entries move to $STUB_NEW.
CLAUDE = r"""import json, os, sys
args = sys.argv[1:]
tmp = os.environ["STUB_TMP"]
for name in ("claude-log", "git-argv"):
    with open(os.path.join(tmp, name), "a") as fh:
        fh.write("claude " + " ".join(args) + "\n")
code = int(os.environ.get("CLAUDE_EXIT") or 0)
if args[:2] == ["plugin", "update"] and code == 0:
    path = os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "plugins", "installed_plugins.json")
    with open(path) as fh:
        doc = json.load(fh)
    for e in doc["plugins"][args[2]]:
        e["version"] = os.environ["STUB_NEW"]
    with open(path, "w") as fh:
        json.dump(doc, fh)
sys.exit(code)
"""
# `ps`: one line holding the probe, so the list reads as one with environments, then $PS_TEXT;
# $PS_FAIL set, the list cannot be read.
PS = """#!/bin/sh
[ -n "${PS_FAIL:-}" ] && exit 1
echo "    1 /sbin/launchd %s=$%s"
[ -f "$PS_TEXT" ] && cat "$PS_TEXT"
exit 0
""" % (PROBE, PROBE)
INSTALL = "install:\n\t@exit $${INSTALL_EXIT:-0}\n"


class Box:
    """The crate's stubs and Claude Code's made-up config folder; `env` the call's additions."""

    def __init__(self, c):
        self.c = c
        stubs = c.tmp / "stubs"
        stubs.mkdir()
        (stubs / "claude.py").write_text(CLAUDE)
        (stubs / "claude").write_text('#!/bin/sh\nexec "%s" -I "%s" "$@"\n'
                                      % (sys.executable, stubs / "claude.py"))
        (stubs / "ps").write_text(PS)
        for name in ("claude", "ps"):
            os.chmod(str(stubs / name), 0o755)
        self.config = c.tmp / "claude-config"
        (self.config / "plugins").mkdir(parents=True)
        self.ps_text = c.tmp / "ps-text"
        self.log = c.tmp / "claude-log"
        rec = c.recorder()["PATH"]
        self.env = {"PATH": str(stubs) + os.pathsep + rec, "CLAUDE_CONFIG_DIR": str(self.config),
                    "PS_TEXT": str(self.ps_text), "STUB_TMP": str(c.tmp), "STUB_NEW": "1.0.1"}

    def plugin(self, name="murmur", pid="murmur@acme", old="1.0.0", new="1.0.1", scope="user"):
        """plugin.json on main, pushed to the bare repo; the installed entry at `old`."""
        self.c.commit("the plugin", {"plugin/.claude-plugin/plugin.json":
                                     json.dumps({"name": name, "version": new}) + "\n"})
        self.c.git(self.c.repo, "push", "-q", "origin", "main")
        self.installed({pid: [{"scope": scope, "version": old, "installPath": "/x/" + name}]})

    def installed(self, plugins):
        (self.config / "plugins" / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": plugins}))

    def makefile(self, text=CHECK + INSTALL):
        self.c.commit("the install target", {"Makefile": text})
        self.c.git(self.c.repo, "push", "-q", "origin", "main")

    def ran(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def publish(self, *args, env=None):
        return self.c.publish(*args, env={**self.env, **(env or {})})


def _stop(c):
    for path in c.root.glob("**/runner.json"):
        try:
            os.kill(int(json.loads(path.read_text())["pid"]), signal.SIGTERM)
        except (OSError, ValueError, KeyError, TypeError):
            pass


@pytest.fixture
def b(tmp_path):
    c = Crate(tmp_path.resolve())
    box = Box(c)
    yield box
    _stop(c)


@pytest.fixture
def lb(lc):
    return Box(lc)


def proven(b):
    """A landed, proven, unpushed main: (main before, S)."""
    before, head, s = b.c.landed()
    b.c.land_result(before, "land crate: ok %s, main readied" % head)
    return before, s


UPDATES = ["claude plugin marketplace update acme", "claude plugin update murmur@acme"]


# 1. A proven, unpushed main, the plugin one version behind: pushed, then installed.

def test_land5b_1_publish_install_pushes_then_updates_the_plugin(b):
    b.plugin()
    before, s = proven(b)
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out) == (0, line(b.c, "ok %s, pushed to origin" % s)
                         + "install crate: ok murmur@acme 1.0.0 to 1.0.1\n"), err
    assert b.c.bare_main() == s
    assert b.ran() == UPDATES
    events = b.c.git_argv()
    push = [i for i, x in enumerate(events) if x.startswith("push ")]
    claude = [i for i, x in enumerate(events) if x.startswith("claude ")]
    assert push and claude and push[-1] < claude[0], events
    assert "keep 1.0.0" in err


# 2. The same again: already pushed, already installed, nothing started.

def test_land5b_2_again_is_already_pushed_and_already_installed(b):
    b.plugin()
    before, s = proven(b)
    assert b.publish(str(b.c.repo), "--install")[0] == 0
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out) == (0, line(b.c, "ok %s, already pushed" % s)
                         + "install crate: ok murmur@acme 1.0.1, already installed\n"), err
    assert b.ran() == UPDATES


# 3. A red publish installs nothing; `gate land --install` with no --push is red unpushed.

def test_land5b_3_a_red_proof_installs_nothing(b):
    b.plugin()
    b.c.landed()
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out) == (1, line(b.c, "red proof exit 1")), err
    assert b.ran() == []


def test_land5b_3_land_install_without_push_is_red_unpushed(lb):
    rc, out, err = run(lb.c, land_argv(lb.c, "--install", sha=lb.c.head), env=lb.env)
    assert (rc, out) == (1, "land crate: ok %s, main readied\n" % lb.c.head
                         + "install crate: red unpushed exit 1\n"), err
    assert lb.ran() == []


def test_land5b_3_land_push_install_lands_pushes_then_installs(lb):
    rc, out, err = run(lb.c, land_argv(lb.c, "--push", "--install", sha=lb.c.head), env=lb.env)
    s = lb.c.sha("main")
    assert (rc, out) == (0, "land crate: ok %s, main readied\n" % lb.c.head
                         + line(lb.c, "ok %s, pushed to origin" % s)
                         + "install crate: ok, nothing to install here\n"), err


# 4. The process list: a relay run holds, under a path with a space too; an environment
# value's words do not; a list that cannot be read holds.

HELD = ["4242 /usr/local/bin/relay run --repo x", "4242 /opt/my tools/relay run --repo x",
        "4242 /usr/local/bin/agentik relay gate x", "4242 agent-relay plan q.yaml",
        "4242 /x/agentik-relay run"]


def test_land5b_4_a_relay_run_holds_after_the_push(b):
    b.plugin()
    before, s = proven(b)
    b.ps_text.write_text("4242 /opt/my tools/relay run --repo x HOME=/x\n")
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert rc == 1, err
    first, second = out.splitlines()
    assert first == line(b.c, "ok %s, pushed to origin" % s).rstrip("\n")
    assert second.startswith("install crate: held install: ") and "4242" in second
    assert "agentik session gate publish %s --install" % b.c.repo in err
    assert b.c.bare_main() == s
    assert b.ran() == []


@pytest.mark.parametrize("text", HELD)
def test_land5b_4_each_relay_form_holds(b, text):
    b.plugin()
    b.ps_text.write_text(text + "\n")
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert rc == 1 and out.splitlines()[-1].startswith("install crate: held install: "), (out, err)
    assert b.ran() == []


@pytest.mark.parametrize("text", ["4242 /bin/zsh -l NOTE=relay run", "4242 /bin/zsh A=1 relay run",
                                  "4242 /usr/bin/vim notes.txt", "4242 /x/relay status"])
def test_land5b_4_not_a_relay_run_does_not_hold(b, text):
    b.plugin()
    b.ps_text.write_text(text + "\n")
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out.splitlines()[-1]) == (0, "install crate: ok murmur@acme 1.0.0 to 1.0.1"), err


@pytest.mark.parametrize("how", ["fails", "no environment"])
def test_land5b_4_an_unreadable_list_holds(b, how):
    b.plugin()
    env = {"PS_FAIL": "1"} if how == "fails" else {}
    if how == "no environment":
        (b.c.tmp / "stubs" / "ps").write_text("#!/bin/sh\necho '1 /sbin/launchd'\n")
    rc, out, err = b.publish(str(b.c.repo), "--install", env=env)
    assert rc == 1 and out.splitlines()[-1].startswith("install crate: held install: "), (out, err)
    assert b.ran() == []


def test_land5b_4_no_ps_on_path_holds(b):
    from claude_session import deliver
    held = deliver.hold(str(b.c.repo), b.c.root, {**b.c.env, "PATH": str(b.c.tmp / "none")})
    assert held and "process list" in held


def test_land5b_4_relay_pid_unit():
    from claude_session import deliver
    assert deliver.relay_pid("12 /a b/relay run x\n") == "12"
    assert deliver.relay_pid("12 /bin/sh -c X=1\n13 env-free relay\n") is None
    assert deliver.relay_pid("12 /bin/zsh FOO=relay run\n") is None
    assert deliver.relay_pid("12 agentik relay plan\n") == "12"
    assert deliver.relay_pid("12 agentik relay status\n") is None


# 5. A live unattended run holds; a gate job of the crate, or of a worktree of it, holds; one
# of another repo does not.

def test_land5b_5_a_live_unattended_run_holds(b):
    b.plugin()
    d = b.c.root / "unattended" / "2026-11-14-1"
    d.mkdir(parents=True)
    (d / "ledger.jsonl").write_text(json.dumps({"kind": "spawn", "row": "r1"}) + "\n")
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert rc == 1 and out.splitlines()[-1].startswith("install crate: held install: "), (out, err)
    assert "r1" in out
    assert b.ran() == []


@pytest.mark.parametrize("where", ["crate", "worktree", "other"])
def test_land5b_5_a_gate_job_of_the_repo_holds(b, where):
    b.plugin()
    repo = b.c.repo
    if where == "worktree":
        repo = b.c.tmp / "wt"
        b.c.git(b.c.repo, "worktree", "add", "-q", "-b", "w", str(repo))
    if where == "other":
        repo = Crate(b.c.tmp, name="other").repo
    gate.enqueue(b.c.root, str(repo), ["true"], {}, [], 60, "a job", None, time.time())
    rc, out, err = b.publish(str(b.c.repo), "--install")
    last = out.splitlines()[-1]
    if where == "other":
        assert (rc, last) == (0, "install crate: ok murmur@acme 1.0.0 to 1.0.1"), err
    else:
        assert rc == 1 and last.startswith("install crate: held install: "), (out, err)
        assert b.ran() == []


# 6. A Makefile's install target: a gate job on the crate's key, waited for strictly.

def _results(c):
    return [json.loads(p.read_text()) for p in sorted(gate.gate_dir(c.root).glob("*/result.json"))]


def test_land5b_6_make_install_is_a_gate_job(b):
    b.plugin()
    b.makefile()
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out.splitlines()[-1]) == (
        0, "install crate: ok murmur@acme 1.0.0 to 1.0.1, make install"), err
    (result,) = _results(b.c)
    assert (result["command"], result["repo"], result["exit"]) == (
        ["make", "install"], str(b.c.repo), 0)
    assert b.ran() == UPDATES


def test_land5b_6_make_install_alone(b):
    b.makefile()
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out.splitlines()[-1]) == (0, "install crate: ok, make install"), err
    assert b.ran() == []


def test_land5b_6_a_failing_target_is_red_install(b):
    b.makefile()
    rc, out, err = b.publish(str(b.c.repo), "--install", env={"INSTALL_EXIT": "3"})
    assert (rc, out.splitlines()[-1]) == (2, "install crate: red install exit 2"), err


def test_land5b_6_a_failing_update_is_its_code(b):
    b.plugin()
    rc, out, err = b.publish(str(b.c.repo), "--install", env={"CLAUDE_EXIT": "5"})
    assert (rc, out.splitlines()[-1]) == (5, "install crate: red install exit 5"), err
    assert b.ran() == UPDATES[:1]


def test_land5b_6_nothing_to_install(b):
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out) == (0, line(b.c, "ok %s, already pushed" % b.c.sha("main"))
                         + "install crate: ok, nothing to install here\n"), err


# 7. No word read from a file is a command's option.

@pytest.mark.parametrize("name,pid", [("murmur", "murmur@--help"), ("Murmur", "Murmur@acme"),
                                      ("murmur", "murmur@Acme")])
def test_land5b_7_a_name_that_is_no_plain_word_is_red(b, name, pid):
    b.plugin(name=name, pid=pid)
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out.splitlines()[-1]) == (1, "install crate: red install exit 1"), err
    assert b.ran() == []


def test_land5b_7_an_entry_of_a_project_scope_is_no_plugin_step(b):
    b.plugin(scope="project")
    rc, out, err = b.publish(str(b.c.repo), "--install")
    assert (rc, out.splitlines()[-1]) == (0, "install crate: ok, nothing to install here"), err
    assert b.ran() == []


# 8. --dry-run: the reads, the would-run line; no claude, nothing queued, no ref moved.

def test_land5b_8_dry_run_would_run(b):
    b.plugin()
    b.makefile()
    before, s = proven(b)
    refs = b.c.refs()
    rc, out, err = b.publish(str(b.c.repo), "--dry-run", "--install")
    assert (rc, out) == (0, line(b.c, "would push %s to origin" % s)
                         + "install crate: would run claude plugin marketplace update acme; "
                         "claude plugin update murmur@acme; make install\n"), err
    assert b.ran() == []
    assert not gate.entries(b.c.root) and not _results(b.c)
    assert b.c.refs() == refs


def test_land5b_8_dry_run_still_holds(b):
    b.plugin()
    b.ps_text.write_text("4242 /usr/local/bin/relay run\n")
    rc, out, err = b.publish(str(b.c.repo), "--dry-run", "--install")
    assert rc == 1 and out.splitlines()[-1].startswith("install crate: held install: "), (out, err)


# 9. Each refused caller: publish's refusal, before any git and any claude.

WHO = [{"CLAUDE_SESSION_HELPER": "1"}, {"CLAUDE_SESSION_DEPTH": "1"}, {"RELAY_ROW": "r1"},
       {"CLAUDE_SESSION_PROFILE": "builder"}, {gate.JOB_MARK: "20261110-000000-1"}]


@pytest.mark.parametrize("who", WHO)
@pytest.mark.parametrize("dry", [False, True])
def test_land5b_9_a_refused_caller_runs_nothing(b, who, dry):
    b.plugin()
    proven(b)
    rc, out, err = b.publish(str(b.c.repo), "--install", *(["--dry-run"] if dry else []), env=who)
    assert (rc, out) == (1, "publish ?: red caller exit 1\n"), err
    assert b.c.git_argv() == [] and b.ran() == []


@pytest.mark.parametrize("who", WHO)
def test_land5b_9_land_install_is_refused_before_it_queues(lb, who):
    rc, out, err = run(lb.c, land_argv(lb.c, "--install", sha=lb.c.head), env={**lb.env, **who})
    assert (rc, out) == (1, "land ?: red caller exit 1\n"), err
    assert not gate.entries(lb.c.root) and lb.ran() == []


def test_land5b_9_in_job_with_install_is_usage(lb):
    rc, out, err = run(lb.c, land_argv(lb.c, "--in-job", "--install", sha=lb.c.head),
                       env={**lb.env, gate.JOB_MARK: "20261110-000000-1"})
    assert (rc, out) == (2, "land ?: red usage exit 2\n"), err
