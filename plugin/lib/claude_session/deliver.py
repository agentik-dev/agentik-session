"""deliver: `--install` on `gate publish` and `gate land`, what was pushed installed
(packet land5b-install).

  agentik session gate publish <repo>... [--install] [--dry-run]
  agentik session gate land <repo> <branch> <sha> <merge-file> [--push] [--install] [--dry-run]

It runs in the caller's own process after a repo's ok publish line (or, for `gate land
--install` with no `--push`, after an ok land line), never in a gate job; publish's caller
refusal has already held. Stdout is one line a repo, after its publish (or land) line:

  install <repo>: ok <N>@<M> <old> to <new>[, make install]     exit 0
  install <repo>: ok <N>@<M> <new>, already installed           exit 0, nothing run
  install <repo>: ok, make install                              exit 0
  install <repo>: ok, nothing to install here                   exit 0
  install <repo>: would run <command>; <command>...             exit 0, --dry-run
  install <repo>: held install: <what is live>                  exit 1, nothing run
  install <repo>: red unpushed exit 1                           nothing run
  install <repo>: red install exit <code>                       the step's own code

Pushed (R2): main's head S is `refs/remotes/<remote>/main` or its ancestor, read as publish
reads it, no fetch; a dry publish's `would push` line reads as pushed. The hold (R3), read
before anything else, nothing of the repo installed while: a line of the process list names a
relay `run`, `gate` or `plan` (`relay_pid`), or the list cannot be read; this tool's unattended
state names a running row (`unattended.status`); the gate's queue holds an entry, running or
queued, on the repo's key (the checkout or a worktree of it). Held, a note gives the command to
repeat; there is no poll and no relay verb is run.

What is installed (R4), each command a note before it runs: (1) the plugin `<repo>/plugin/
.claude-plugin/plugin.json` names, N, where Claude Code's installed-plugins file has an id
`N@M` with an entry of the user's own scope (`user`, `managed` or none; of several ids, the
first by name): `claude plugin marketplace update M`, then `claude plugin update N@M`, in the
user's home; N or M other than lowercase letters, digits and dashes opening with a letter or a
digit is `red install exit 1`, nothing run, so no word from a file is a command's option. Where
the entry's version is plugin.json's before anything ran, nothing runs at all. (2) a Makefile
whose `make -n install` exits 0 under land.main's cleaned environment: `make install` queued as
a gate job on the repo's key and waited for, its strict code the step's. hq measured twice on a
Mac that `claude plugin update` and `marketplace update` leave Claude Code's user settings file
alone (R8), so no edit-gates list is read.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

from . import gate, land

HOLDS = ("run", "gate", "plan")
PROGRAMS = ("relay", "agent-relay", "agentik-relay")
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")     # where `ps -E` starts a process's environment
PART = re.compile(r"[a-z0-9][a-z0-9-]*\Z")          # a plugin id's name and its marketplace
OWN = ("user", "managed", None)
PS_WALL = 10
DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
        "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "MAKELEVEL")    # land.main's


class Red(Exception):
    def __init__(self, code, note=None):
        super().__init__(note or "")
        self.code, self.note = code, note


def note(text):
    print("install-step: " + text, file=sys.stderr, flush=True)


def relay_pid(text):
    """The pid of the first line whose program's base name is `relay`, `agent-relay` or
    `agentik-relay` with `run`, `gate` or `plan` among its later words, or `agentik relay
    <one of them>`; None when no line holds. The words stop at the first `NAME=value` word, so
    an environment value's text is never a word; each prefix of the words, joined by one space,
    is tried as the program, so a relay under a path with a space holds (agentik-commons'
    update hold, its review 1 F3)."""
    for row in text.splitlines():
        parts = row.split()
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        words = []
        for word in parts[1:]:
            if ASSIGN.match(word):
                break
            words.append(word)
        for k in range(1, len(words) + 1):
            program, rest = os.path.basename(" ".join(words[:k])), words[k:]
            if program in PROGRAMS and any(w in HOLDS for w in rest):
                return parts[0]
            if program == "agentik" and rest[:1] == ["relay"] and len(rest) > 1 \
                    and rest[1] in HOLDS:
                return parts[0]
    return None


def _processes(env):
    """(the list's text, None) or (None, why)."""
    ps = shutil.which("ps", path=env.get("PATH", ""))
    if not ps:
        return None, "no ps on PATH"
    try:
        import agentik_install
    except ImportError:
        return None, "no agentik_install beside the package"
    return agentik_install.processes(ps, timeout=PS_WALL)


def hold(repo, root, env):
    """What is live, as the held line's text, or None (R3)."""
    text, why = _processes(env)
    if text is None:
        return "the process list cannot be read (%s)" % why
    pid = relay_pid(text)
    if pid:
        return "a relay run, pid %s" % pid
    from . import unattended
    try:
        st = unattended.status(env, time.time())
    except Exception as err:        # unreadable: the safe side
        return "the unattended state cannot be read (%s)" % type(err).__name__
    running = (st or {}).get("running")
    if running:
        return "unattended run %s, row %s" % (st.get("run"), running.get("row"))
    key = gate.repo_key(repo)
    for e in gate.entries(root):
        if gate.entry_key(e) == key:
            return "gate job %s on %s" % (e.get("id"), gate.key_name(e))
    return None


def pushed(repo):
    """True where main's head is its remote's main or an ancestor of it (publish's read)."""
    from . import publish
    try:
        remote = publish.remote_of(repo)
    except land.Red:
        return False
    code, s = land.read(repo, "rev-parse", "--verify", "-q", land.MAIN + "^{commit}")
    if code != 0 or not s:
        return False
    code, r = land.read(repo, "rev-parse", "--verify", "-q", "refs/remotes/%s/main^{commit}" % remote)
    if code != 0 or not r:
        return False
    return r == s or land.read(repo, "merge-base", "--is-ancestor", s, r)[0] == 0


def _json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError, RecursionError):
        return {}
    return d if isinstance(d, dict) else {}


def _installed(env):
    home = env.get("HOME") or ""
    config = env.get("CLAUDE_CONFIG_DIR") or os.path.join(home, ".claude")
    got = _json(os.path.join(config, "plugins", "installed_plugins.json")).get("plugins")
    return got if isinstance(got, dict) else {}


def ids(env, n):
    """[(id, its version)] of N's ids with an entry of the user's own scope, by name."""
    out = []
    for pid, recs in sorted(_installed(env).items()):
        if not isinstance(pid, str) or pid.partition("@")[0] != n or "@" not in pid:
            continue
        for rec in (recs if isinstance(recs, list) else ()):
            if isinstance(rec, dict) and rec.get("scope") in OWN:
                v = rec.get("version")
                out.append((pid, v if isinstance(v, str) else None))
                break
    return out


def plugin(repo, env):
    """None (no plugin step), or (N, M, old, wanted)."""
    doc = _json(os.path.join(repo, "plugin", ".claude-plugin", "plugin.json"))
    n = doc.get("name")
    if not isinstance(n, str) or not n:
        return None
    if not PART.match(n):
        raise Red(1, "plugin.json's name %r is not lowercase letters, digits and dashes, so "
                     "it is never a command's word" % n[:60])
    found = ids(env, n)
    if not found:
        note("no installed id %s@<marketplace> of the user's scope; no plugin step" % n)
        return None
    pid, old = found[0]
    m = pid.partition("@")[2]
    if not PART.match(m):
        raise Red(1, "the installed id %r has a marketplace that is not lowercase letters, "
                     "digits and dashes, so it is never a command's word" % pid[:80])
    wanted = doc.get("version")
    return n, m, old, wanted if isinstance(wanted, str) else None


def _clean(env):
    return {k: v for k, v in env.items() if k not in DROP}


def has_install(repo, env):
    """`make -n install` exits 0 under land.main's cleaned environment."""
    try:
        p = subprocess.run(["make", "-n", "install"], cwd=repo, env=_clean(env),
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def _claude(env, *argv):
    note("claude " + " ".join(argv))
    home = env.get("HOME") or ""
    code = land.run(home if os.path.isdir(home) else "/", "claude", *argv)
    if code != 0:
        raise Red(code)


def _make_install(repo, root, env, name):
    note("make install, a gate job on %s" % repo)
    wall = gate._config(env)["wall"]
    sid = env.get("CLAUDE_CODE_SESSION_ID") or ""
    caller = sid if gate._SID.match(sid) else None
    try:
        e = gate.enqueue(root, repo, ["make", "install"], _clean(env), [], wall,
                         "install " + name, caller, time.time())
    except gate.GateError as err:
        raise Red(1, "gate: %s" % err)
    gate.spawn_serve(root)
    note("queued %s on %s; result %s" % (e["id"], e["repo"], gate.result_path(root, e["id"])))
    rc, result = gate.wait(root, e["id"])
    if rc != 0 or result is None:
        raise Red(1, "%s has no result under %s" % (e["id"], gate.gate_dir(root)))
    note(gate.wait_line(result))
    code = gate.strict_code(result)
    if code != 0:
        raise Red(code)


def turn(arg, root, env, dry=False, would=False):
    """One repo's install: (its line, its code). `would`: the publish line was a dry
    `would push`, read as pushed."""
    name = os.path.basename(os.path.normpath(arg)) or "?"
    try:
        repo = land.resolve_repo(arg)
        name = os.path.basename(repo)
        if not (would or pushed(repo)):
            note("main of %s is not on its remote's main, so nothing is installed: push it "
                 "first, agentik session gate publish %s --install" % (repo, repo))
            return "install %s: red unpushed exit 1" % name, 1
        live = hold(repo, root, env)
        if live:
            note("repeat when it is over: agentik session gate publish %s --install" % repo)
            return "install %s: held install: %s" % (name, live), 1
        plug = plugin(repo, env)
        if plug and plug[3] is not None and plug[2] == plug[3]:
            n, m, old, _ = plug
            return "install %s: ok %s@%s %s, already installed" % (name, n, m, old), 0
        make = has_install(repo, env)
        steps = []
        if plug:
            steps += ["claude plugin marketplace update %s" % plug[1],
                      "claude plugin update %s@%s" % (plug[0], plug[1])]
        if make:
            steps.append("make install")
        if not steps:
            return "install %s: ok, nothing to install here" % name, 0
        if dry:
            return "install %s: would run %s" % (name, "; ".join(steps)), 0
        parts = [""]
        if plug:
            n, m, old, wanted = plug
            _claude(env, "plugin", "marketplace", "update", m)
            _claude(env, "plugin", "update", "%s@%s" % (n, m))
            new = dict(ids(env, n)).get("%s@%s" % (n, m))
            if wanted is not None and new != wanted:
                note("the installed version is %s, not plugin.json's %s" % (new, wanted))
            note("sessions started before this keep %s@%s %s" % (n, m, old))
            parts = [" %s@%s %s to %s" % (n, m, old, new)]
        if make:
            _make_install(repo, root, env, name)
            parts.append(" make install")
        return "install %s: ok%s" % (name, ",".join(parts)), 0
    except Exception as err:
        red = err if isinstance(err, Red) else Red(1, "%s: %s" % (type(err).__name__, err))
        if red.note:
            note(red.note)
        return "install %s: red install exit %d" % (name, red.code), red.code
