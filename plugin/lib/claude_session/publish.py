"""publish: main's head, proven checked green by the gate, scanned and pushed (packet land5-publish).

  agentik session gate publish <repo>... [--dry-run]
  agentik session gate land --push [--dry-run] <repo> <branch> <sha> <merge-file>

It runs in the caller's own process, never in a gate job, since only a main sitting may push;
it installs nothing and queues nothing. Each <repo> is resolved as `land.resolve_repo` does (a
bare name is that checkout in ~/code, else the one a folder below; a name with a slash is a
path) and taken in turn. Notes go to stderr as `publish-step: ...`; stdout is one line a repo,
each the last of its turn:

  publish <repo>: ok <S>, pushed to <remote>[, range not scanned]    exit 0
  publish <repo>: ok <S>, already pushed                              exit 0
  publish <repo>: would push <S> to <remote>[, range not scanned]     exit 0, --dry-run
  publish <repo>: red <step> exit <code>                              exit <code>

Every repo gets its line, a red one too, and the exit is the first non-zero code, else 0. No
repo, or an unknown flag, is `publish ?: red usage exit 2`.

The caller (step `caller`, before any read of a repo, `--dry-run` too): inside a gate job
(`CLAUDE_SESSION_GATE_JOB` set), a sitting `state.main_sitting` reads as no main one (a helper, a
started or a relay sitting), or `CLAUDE_SESSION_PROFILE=builder` is `publish ?: red caller exit
1`, the note saying which.

A repo's turn. S is the sha of `refs/heads/main`, read once at its start and used by every later
step. `repo`: not the top of a main checkout. `main`: `land.require_main`'s reads (main checked
out; no merge, cherry-pick, revert or rebase under way; nothing staged). `remote`: no
`branch.main.remote`, a `branch.main.merge` other than `refs/heads/main`, a remote whose name
opens with `-`, or one that is no name `git remote` lists (a path or a URL, review 1 lead 2).
R is `refs/remotes/<remote>/main`, read once with S: where it exists and S is R or its
ancestor, nothing more runs and the line is `already pushed`. No fetch is ever made.

`proof`: S is proven checked green by a gate result under the state root (`<root>/gate/<id>/
result.json`), the first of these that holds; a result that is no JSON object, or whose keys are
of the wrong type, is no proof and no error:
- a landing: `exit` 0, `repo` this checkout, `command` the one `gate land` queues, whole:
  this runner's argv (`gate.self_argv()`), then `gate land --in-job <repo> <branch> <sha>
  <merge>` and nothing after, `<repo>` this checkout; and its log's last land line of this repo
  (`gate.last_line`) opens `ok <sha>`, that same `<sha>` (review 1, F1). The sha it proves is
  the one after `, as ` when the line has that part (the head readied from `<sha>`), else
  `<sha>` itself, a prefix allowed; `git rev-parse --verify <it>^{commit}` gives exactly S's
  second parent, so an ambiguous or unknown prefix proves nothing (F3); S has exactly two
  parents, its first is the result's `head`, and the proved sha's tree is S's.
- a check: `exit` 0, `repo` this checkout, `head` S, `dirty` 0 at the start and at the end,
  `make_env` there and empty (none of `gate.MAKE_ENV` set in the job's environment, review 1
  F2, so a result older than the key proves no check), and
  `command` `make check` alone, or `sh -c` (or `/bin/sh -c`) of the one simple command `make
  check` with redirections (`>`, `>>`, `>|`, `<`, each to a plain word, `N>&M`) and nothing else.
With neither, the note gives the line that makes one, `agentik session gate run <repo> -- make
check` on a clean main, none of those four names set; this verb never queues it.

`main` again: a tracked file of the working tree that differs from S, read before the scans and
after them, since the tree's scan would read another tree. `hygiene`: where `scripts/hygiene` is
an executable file, it runs in the checkout, then `scripts/hygiene --require-private --commits
<R's sha>..<S>` when its --help names `--commits` (as land's own step reads it), each one's
output on stderr; a non-zero exit is the line's code. With no R, or a hygiene without
`--commits`, the range is not scanned and the ok line ends `, range not scanned`. `push`: `git
push --no-follow-tags <remote> <S>:refs/heads/main` (so no tag rides it where `push.followTags`
is set, review 1 lead 1), the sha and never main's name, never forced, never `--no-verify`, no
other argument; git's lines on stderr, its exit the line's code. `--dry-run`
runs every step but the push (the scans write nothing) and writes no ref.

`gate land --push` refuses as the caller step above before it queues, as `land ?: red caller
exit 1`; `--in-job` with `--push` is `land ?: red usage exit 2`. The job is `gate land`'s,
unchanged. After its ok land line the caller runs a repo's turn here for that repo, and the
publish line follows the land line; the exit is the land's when it is red, else the publish's.
After a red land line nothing is pushed. With `--dry-run` too, land's dry lines, then the dry
publish line. Any other error is `red <step> exit 1` at the step reached, its reason a note.
"""

from __future__ import annotations

import os
import re
import sys

from . import gate, land, state

USAGE = "usage: agentik session gate publish <repo>... [--dry-run]"
MAIN = land.MAIN
FULL = re.compile(r"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
PREFIX = re.compile(r"\A[0-9a-f]{4,64}\Z")
WORD = r"[A-Za-z0-9_./~+,:@%=-]+"
REDIRECT = r"(?:[0-9]*(?:>>|>\||>|<)[ \t]*%s|[0-9]*[<>]&[ \t]*(?:[0-9]+|-))" % WORD
CHECK_SCRIPT = re.compile(r"\A[ \t\n]*make[ \t]+check(?:[ \t]+%s)*[ \t\n]*\Z" % REDIRECT)
SHELLS = ("sh", "/bin/sh")


def note(text):
    print("publish-step: " + text, file=sys.stderr, flush=True)


def refusal(env):
    """Why this caller may not push, or None (R2)."""
    if gate.JOB_MARK in env:
        return ("this is gate job %s: a push runs in a main sitting's own process, never in a "
                "job" % (env.get(gate.JOB_MARK) or "")[:40])
    if not state.main_sitting(env):
        return ("this is no main sitting (a helper, a started or a relay sitting: "
                "CLAUDE_SESSION_HELPER, CLAUDE_SESSION_DEPTH or RELAY_ROW): only a main sitting "
                "pushes")
    if env.get("CLAUDE_SESSION_PROFILE") == "builder":
        return "the builder profile: a builder never pushes"
    return None


def _zero(x):
    return isinstance(x, int) and not isinstance(x, bool) and x == 0


def _same(path, repo):
    return isinstance(path, str) and bool(path) and os.path.realpath(path) == repo


def _strs(x):
    return isinstance(x, list) and all(isinstance(a, str) for a in x)


def _tree(repo, rev):
    code, out = land.read(repo, "rev-parse", "--verify", "-q", rev + "^{tree}")
    return out if code == 0 and out else None


def is_check_command(command):
    """`make check` alone, or `sh -c` of that one simple command with redirections alone."""
    if not _strs(command):
        return False
    if command == ["make", "check"]:
        return True
    return (len(command) == 3 and command[0] in SHELLS and command[1] == "-c"
            and CHECK_SCRIPT.match(command[2]) is not None)


def landing_proves(doc, repo, name, s, parents):
    """A landing's result proves S: see the docstring's `proof`."""
    command, log, gid, head = (doc.get(k) for k in ("command", "log", "id", "head"))
    if not (_zero(doc.get("exit")) and _same(doc.get("repo"), repo) and _strs(command)
            and isinstance(log, str) and isinstance(gid, str) and isinstance(head, str)):
        return False
    own = [*gate.self_argv(), "gate", "land", "--in-job"]
    if not (len(command) == len(own) + 4 and command[:len(own)] == own
            and _same(command[-4], repo)):
        return False
    given = command[-2]
    prefix = "land %s: " % name
    line = gate.last_line(log, gid, prefix) or ""
    if not line.startswith(prefix + "ok "):
        return False
    rest = line[len(prefix + "ok "):]
    if rest.split(",", 1)[0] != given:
        return False
    if ", as " in rest:
        rest = rest.split(", as ", 1)[1]
    proved = rest.split(",", 1)[0].strip().lower()
    if len(parents) != 2 or not PREFIX.match(proved):
        return False
    first, second = parents
    code, named = land.read(repo, "rev-parse", "--verify", "-q", proved + "^{commit}")
    return (first == head and code == 0 and named == second and second.startswith(proved)
            and _tree(repo, second) is not None and _tree(repo, second) == _tree(repo, s))


def check_proves(doc, repo, s):
    """A check's result proves S: see the docstring's `proof`."""
    dirty = doc.get("dirty")
    return (_zero(doc.get("exit")) and _same(doc.get("repo"), repo) and doc.get("head") == s
            and isinstance(dirty, dict) and _zero(dirty.get("start")) and _zero(dirty.get("end"))
            and doc.get("make_env") == [] and is_check_command(doc.get("command")))


def results(root):
    """Each result under the gate that reads as a JSON object, newest id first."""
    try:
        names = [n for n in os.listdir(gate.gate_dir(root)) if gate.ID.match(n)]
    except OSError:
        return
    for n in sorted(names, key=lambda n: (n[:15], int(n[16:])), reverse=True):
        doc = gate._load(gate.result_path(root, n))     # the gate's own reader: a dict or None
        if doc is not None:
            yield n, doc


def proof(root, repo, name, s):
    """What proves S, as a note's text, or None."""
    code, out = land.read(repo, "rev-list", "--parents", "-n", "1", s)
    parents = out.split()[1:] if code == 0 else []
    for gid, doc in results(root):
        if landing_proves(doc, repo, name, s, parents):
            return "the landing %s, main's head its merge" % gid
        if check_proves(doc, repo, s):
            return "the check %s on %s" % (gid, s)
    return None


def require_tree(repo, s):
    """The working tree holds S in every tracked file, or Red at main."""
    code, paths = land.read_z(repo, "diff", "--no-ext-diff", "--name-only", "-z",
                              "--ignore-submodules=none", s, "--")
    if code != 0 or paths:
        raise land.Red("main", note="the working tree differs from %s, so a scan would read "
                       "another tree:\n%s" % (s, "\n".join(paths) or "git diff failed"))


def remote_of(repo):
    """branch.main.remote, its merge refs/heads/main, or Red at remote."""
    code, remote = land.read(repo, "config", "--get", "branch.main.remote")
    if code != 0 or not remote:
        raise land.Red("remote", note="main has no branch.main.remote; set its upstream: git "
                       "branch -u <remote>/main main")
    if remote.startswith("-"):
        raise land.Red("remote", note="branch.main.remote %r opens with -" % remote)
    code, names = land.read(repo, "remote")
    if code != 0 or remote not in names.splitlines():
        raise land.Red("remote", note="branch.main.remote %r is no remote `git remote` lists (a "
                       "path or a URL is refused): git remote add <name> <url>" % remote)
    code, merge = land.read(repo, "config", "--get", "branch.main.merge")
    if code != 0 or merge != MAIN:
        raise land.Red("remote", note="branch.main.merge is %s, not %s" % (merge or "unset", MAIN))
    return remote


def scans(repo, r, s):
    """The hygiene step; what the ok line adds ("" or "range not scanned")."""
    script = os.path.join(repo, "scripts", "hygiene")
    if not (os.path.isfile(script) and os.access(script, os.X_OK)):
        note("hygiene: no executable scripts/hygiene in " + repo)
        return ""
    note("hygiene: scripts/hygiene in " + repo)
    code = land.run(repo, script)
    if code != 0:
        raise land.Red("hygiene", code)
    if r is None:
        note("hygiene: no remote main, so no range is scanned")
        return "range not scanned"
    span = "%s..%s" % (r, s)
    if not land.takes_commits(repo, script):
        note("hygiene: scripts/hygiene has no --commits; %s not scanned" % span)
        return "range not scanned"
    note("hygiene: scripts/hygiene --require-private --commits %s in %s" % (span, repo))
    code = land.run(repo, script, "--require-private", "--commits", span)
    if code != 0:
        raise land.Red("hygiene", code)
    return ""


def turn(arg, root, dry=False):
    """One repo's turn: (its line, its code)."""
    name, step = os.path.basename(os.path.normpath(arg)) or "?", "repo"
    try:
        repo = land.resolve_repo(arg)
        name = os.path.basename(repo)
        land.worktrees(repo)
        step = "main"
        code, s = land.read(repo, "rev-parse", "--verify", "-q", MAIN + "^{commit}")
        if code != 0 or not FULL.match(s):
            raise land.Red("main", note="no %s in %s" % (MAIN, repo))
        land.require_main(repo)
        step = "remote"
        remote = remote_of(repo)
        code, r = land.read(repo, "rev-parse", "--verify", "-q",
                            "refs/remotes/%s/main^{commit}" % remote)
        r = r if code == 0 and FULL.match(r) else None
        if r is not None and (r == s or land.read(repo, "merge-base", "--is-ancestor", s, r)[0] == 0):
            return "publish %s: ok %s, already pushed" % (name, s), 0
        step = "proof"
        why = proof(root, repo, name, s)
        if why is None:
            raise land.Red("proof", note="no gate result proves %s checked green; on a clean main: "
                           "agentik session gate run %s -- make check, with none of %s set"
                           % (s, repo, ", ".join(gate.MAKE_ENV)))
        note("proof: " + why)
        step = "main"
        require_tree(repo, s)
        step = "hygiene"
        ending = scans(repo, r, s)
        ending = ending and ", " + ending
        step = "main"
        require_tree(repo, s)
        if dry:
            return "publish %s: would push %s to %s%s" % (name, s, remote, ending), 0
        step = "push"
        note("push: git push --no-follow-tags %s %s:%s in %s" % (remote, s, MAIN, repo))
        code = land.run(repo, "git", "push", "--no-follow-tags", remote, "%s:%s" % (s, MAIN))
        if code != 0:
            raise land.Red("push", code)
        return "publish %s: ok %s, pushed to %s%s" % (name, s, remote, ending), 0
    except Exception as err:
        red = err if isinstance(err, land.Red) else land.Red(step, 1, "%s: %s"
                                                             % (type(err).__name__, err))
        if red.note:
            note(red.note)
        return "publish %s: red %s exit %d" % (name, red.step, red.code), red.code


def _clean_env():
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        os.environ.pop(name, None)


def main(repos, root, env, dry=False):
    """`gate publish`: each repo's line on stdout, the first non-zero code."""
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")
    if not repos:
        note(USAGE)
        print("publish ?: red usage exit 2", flush=True)
        return 2
    why = refusal(env)
    if why:
        note(why)
        print("publish ?: red caller exit 1", flush=True)
        return 1
    _clean_env()
    first = 0
    for arg in repos:
        text, code = turn(arg, root, dry)
        print(text, flush=True)
        first = first or code
    return first


def after_land(repo, root, dry=False):
    """`gate land --push`'s half after an ok land line: one turn, its line and code."""
    _clean_env()
    text, code = turn(repo, root, dry)
    print(text, flush=True)
    return code
