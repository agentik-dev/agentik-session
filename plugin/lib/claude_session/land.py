"""land: one landing as one job (packet FW4c; hq design/08 §5 row 5; hq's scripts/land at 9f394ce).

  agentik session gate land <repo> <branch> <sha> <merge-file>      queues this as one gate job
  agentik session gate land --in-job <repo> <branch> <sha> <merge-file>   the job itself

A bare <repo> is that checkout in ~/code, else the one a folder below; one with a slash is a
path; the cwd never decides. <sha> is a prefix of the commit, never a ref's name. Runs, in
order: the merge message's scan (below), `make check` in the branch's worktree, `scripts/hygiene`
there when present, then
`scripts/hygiene --require-private --commits refs/heads/main..<sha>` there when its --help names
`--commits`, `git merge --no-ff --commit -F <merge-file> <sha>` in the repo's main checkout,
`git worktree remove`, `git branch -D`. Stdout is one line, the verdict, and it comes last:

  land <repo>: ok <sha>, main readied            exit 0
  land <repo>: red <step> exit <code>            exit <code>

A cut that leaves staged paths alone adds to that line: `, staged paths left on main`. A
`scripts/hygiene` that predates `--commits`, its --help failing or not naming the flag, scans the
tree alone: a note says so, and the ok line ends `, range not scanned`. The steps'
own output and these notes go to stderr. In the job both streams reach the job's log, so the
verdict is the job's last line before the gate's own; `gate land` prints that line on its stdout
and exits the job's code (`gate wait --strict`'s). A job's cwd is its repo.

The steps: usage, repo (not the top of a main checkout), merge-file (not readable; line 1 not
`Merge <branch>: ` then a non-space character, or a line 2 that is not blank), main (not checked
out; a merge, cherry-pick, revert or rebase under way there; any staged path, a `git add -N` too; a
dirty path the merge touches; a file the merge would write that main does not track, ignored or
not, or a directory there holding one), worktree (the branch has none of its own, or it is locked,
or another worktree git lists sits under it, clean or dirty, which `worktree remove` would take, or
dirty so a check there would not prove the sha, or its .venv is neither a link nor absent), sha
(not the branch's head, or already on main, or behind main: the merge would make a tree other than
<sha>'s, so the check would not run on what main would hold; merge main into the branch and land
its new head), merge-file again (when `scripts/hygiene --help` names --commits, the merge commit is
made as a dangling object, `git commit-tree <tree> -p refs/heads/main -p <sha> -F <merge-file>`,
and `scripts/hygiene --require-private --commits <sha>..<it>` scans its message in the worktree; no
ref is written), check, hygiene, merge (a conflict, read before the check, and read again after it;
or git merge's own red), remove, branch (its sha is not on main, or it has moved), cut. After the
check, before the merge, the nested worktrees, main's lead and the merge file's text and scan are
read again with main and the worktree, since the check takes minutes. Usage reports 2; a refusal of
this script's own reports 1; a step that ran reports that step's code; any other error reports 1 at
the step reached, its reason on stderr.

A red before the merge leaves main unchanged. A `merge` red almost always does too: `git
merge-tree` reads a conflict before the merge begins, one only git merge finds is aborted, never
resolved, and git's exit is confirmed by HEAD, its second parent and no MERGE_HEAD. The exception
is a `git merge` killed after its commit, in post-merge: its code is the line's, the merge stands,
and the note says so. Only this run's merge is ever aborted; when the abort itself fails, the note
says so and the half merge reads `red main` on a retry. A `remove` or `branch` red comes after the
merge, so main has moved and the merge stands, with a non-zero exit all the same: the note says so.

A cut is the gate's wall: gate.py sends SIGTERM to the job's group, SIGKILL 5 s later, and reports
124 whatever the job exits. On that SIGTERM this run's merge is aborted, `red cut exit 124` is the
line and 124 the exit; a cut after the merge's commit leaves it standing, and the note says so.
The abort takes back only the merge: with HEAD moved, or the index holding anything beyond the
merge's result, such as a sitting's `git add` during a hook, nothing is reset, the line says so,
and a retry reads a loud `red main`. So does a hard kill past the grace, by its half state.

Main's dirt is scoped (§5): a sitting's charter edits live in the same checkout, so an unstaged or
untracked path lands beside the merge unless the merge touches it. The paths touched are the
difference from main to the tree `git merge-tree --write-tree` makes (git 2.38), which reads
merge's config and touches neither index nor worktree: a rename counts both its paths, a
directory-rename target counts. Anything staged is red before the check, since git merge refuses
it whatever it touches. Main and the worktree are read again after the check, since the check takes
minutes. An untracked
`.venv` symlink at the worktree's top is no dirt either: it stays for the check, and only the link
goes, after those reads pass, before `worktree remove`, which would refuse it. Publishing is not
here: that stays with the orchestrator.
"""

import glob
import os
import signal
import subprocess
import sys

USAGE = "usage: agentik session gate land <repo> <branch> <sha> <merge-file>"
DEVNULL = subprocess.DEVNULL
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")
MAIN = "refs/heads/main"
CUT = 124    # gate.py's code for its wall: SIGTERM to the job's group, SIGKILL at 5 s
STATUS = ("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none")
REACHED = "usage"   # the step this run is at, for an error that is no Red
STANDS = ""         # once main has moved, what any red says beside its line
LEFT = ""           # what the land line adds when a cut leaves staged paths alone
UNSCANNED = ""      # what the ok line adds when the repo's hygiene predates --commits


class Red(Exception):
    def __init__(self, step, code=1, note=""):
        super().__init__(step)
        self.step, self.code, self.note = step, code, note


def on_cut(signum, frame):
    """One cut. What follows is its cleanup, and the cleanup's own children inherit the ignore."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise Red("cut", CUT)


def note(text):
    print("land-step: " + text, file=sys.stderr, flush=True)


def at(step):
    global REACHED
    REACHED = step


def read(cwd, *args):
    """A git read: (exit, stdout), its stderr kept out of the way."""
    p = subprocess.run(("git",) + args, cwd=cwd, stdin=DEVNULL, stdout=subprocess.PIPE,
                       stderr=DEVNULL, universal_newlines=True)
    return p.returncode, p.stdout.strip()


def read_z(cwd, *args):
    """A NUL-separated git read, unquoted and unstripped: (exit, fields)."""
    p = subprocess.run(("git",) + args, cwd=cwd, stdin=DEVNULL, stdout=subprocess.PIPE,
                       stderr=DEVNULL)
    return p.returncode, [os.fsdecode(f) for f in p.stdout.split(b"\0") if f]


def run(cwd, *argv):
    """A step: its output on stderr, its exit a plain number (a signal reads 128 + n)."""
    sys.stderr.flush()
    try:
        child = subprocess.Popen(argv, cwd=cwd, stdin=DEVNULL, stdout=sys.stderr, stderr=sys.stderr)
    except FileNotFoundError:
        return 127
    except PermissionError:
        return 126
    try:
        code = child.wait()
    except Red:
        settle(child)
        raise
    return code if code >= 0 else 128 - code


def settle(child):
    """A cut reached the group, so the child has its signal: give it a second to clean up its
    locks, and only then push. The grace is 5 s and the abort has to fit in it."""
    for push in (child.terminate, child.kill):
        try:
            child.wait(1)
            return
        except subprocess.TimeoutExpired:
            push()
    child.wait()


def worktrees(repo):
    """`git worktree list`'s blocks as dicts, the main checkout first; Red when repo is not it."""
    if not os.path.isdir(repo):
        raise Red("repo", note="no such directory: " + repo)
    code, out = read(repo, "worktree", "list", "--porcelain")
    if code != 0:
        raise Red("repo", note="not a git repo: " + repo)
    blocks = []
    for block in out.split("\n\n"):
        fields = dict((line.split(" ", 1) + [""])[:2] for line in block.splitlines())
        blocks.append(fields)
    if "bare" in blocks[0] or os.path.realpath(blocks[0]["worktree"]) != os.path.realpath(repo):
        raise Red("repo", note="the main checkout is %s, not %s" % (blocks[0]["worktree"], repo))
    return blocks


def intent_to_add(repo):
    """`git add -N`'s paths: status writes them ` A`, or ` R` and ` C` once it pairs them, and
    diff --cached never sees them."""
    code, fields = read_z(repo, *STATUS, "-z")
    paths, rest = [], iter(fields)
    for entry in rest:
        if entry[:2] in (" A", " R", " C"):
            paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            next(rest, "")
    return code, paths


def staged(repo):
    """Each path git merge would refuse as staged: (exit, paths)."""
    code, paths = read_z(repo, "diff", "--cached", "--name-only", "-z", "--ignore-submodules=none")
    ita_code, ita = intent_to_add(repo)
    return code or ita_code, paths + ita


def require_main(repo):
    """Main checked out with nothing under way on it, or Red with nothing changed."""
    for name in IN_PROGRESS:
        code, path = read(repo, "rev-parse", "--git-path", name)
        if code != 0 or os.path.lexists(os.path.join(repo, path)):
            raise Red("main", note="%s on the main checkout: someone's work is under way" % name)
    code, head = read(repo, "symbolic-ref", "-q", "--short", "HEAD")
    if code != 0 or head != "main":
        raise Red("main", note="the main checkout is on %s, not main" % (head or "a detached HEAD"))
    # git merge refuses any staged path, so it would only say so after the whole check.
    code, paths = staged(repo)
    if code != 0 or paths:
        raise Red("main", note="staged on main:\n" + "\n".join(paths))


def dirty_paths(repo):
    """Each dirty or untracked path of the main checkout, a rename's or copy's two paths both."""
    code, fields = read_z(repo, *STATUS, "-z")
    if code != 0:
        raise Red("main", note="cannot read the main checkout's status")
    paths, rest = [], iter(fields)
    for entry in rest:
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(next(rest, ""))
    return [path for path in paths if path]


def overlaps(a, b):
    """The same path, or one a directory holding the other."""
    a, b = a.rstrip("/"), b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def merge_result(repo, ours, full):
    """What the merge would make, by the same machinery and config as `git merge`: (exit, tree,
    conflicted paths); 0 is clean, 1 a conflict, anything else a failure. It writes objects only,
    never the index or the worktree, and needs git 2.38."""
    code, fields = read_z(repo, "merge-tree", "--write-tree", "--no-messages", "--name-only", "-z",
                          ours, full)
    return code, (fields[0] if fields else ""), fields[1:]


def require_no_overlap(repo, full, branch):
    """The merged tree: a merge that would not conflict, that makes <sha>'s own tree, whose paths
    hold no dirty path and no untracked file on the main checkout, or Red with nothing changed.
    The paths are the difference from main to the merge's own tree, so a directory-rename target
    counts; --no-renames lists a rename as its delete and its add, so both its paths do."""
    code, tree, conflicted = merge_result(repo, MAIN, full)
    if code == 1:
        raise Red("merge", 1, "the merge would conflict, nothing begun:\n" + "\n".join(conflicted))
    if code != 0 or not tree:
        raise Red("merge", code or 1, "git merge-tree exit %d: it reads no merge (git 2.38 or later "
                  "is needed; unrelated histories refuse here as in git merge)" % code)
    # The check runs on <sha>'s tree: a merge making any other tree lands what no check ran on.
    own_code, own = read(repo, "rev-parse", "--verify", "-q", full + "^{tree}")
    if own_code != 0 or tree != own:
        _, log = read(repo, "log", "--oneline", "%s..%s" % (full, MAIN))
        raise Red("sha", note="main holds what %s does not, so the check would not run on the tree "
                  "main would hold:\n%s\nmerge main into %s, land its new head"
                  % (full, log, branch))
    code, touched = read_z(repo, "diff", "--name-only", "-z", "--no-renames", MAIN, tree)
    if code != 0:
        raise Red("main", note="cannot read the paths the merge touches")
    hit = sorted({d for d in dirty_paths(repo) if any(overlaps(d, t) for t in touched)})
    if hit:
        raise Red("main", note="dirty on main and touched by the merge:\n" + "\n".join(hit))
    # Status never lists an ignored file, and the merge would overwrite it.
    code, written = read_z(repo, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=d",
                           MAIN, tree)
    tree_code, tracked = read_z(repo, "ls-tree", "-r", "-z", "--name-only", MAIN)
    if code != 0 or tree_code != 0:
        raise Red("main", note="cannot read the paths the merge writes")
    tracked = set(tracked)
    hit = sorted(path for path in written if stands_untracked(repo, path, tracked))
    if hit:
        raise Red("main", note="on main, untracked, and written by the merge:\n" + "\n".join(hit))
    return tree


def stands_untracked(repo, path, tracked):
    """`path`, or a file or link where it needs a directory, is on disk and not tracked at main;
    a directory stands only if it holds a path not tracked at main, since git replaces the rest."""
    parts = path.split("/")
    for n in range(1, len(parts) + 1):
        here = "/".join(parts[:n])
        whole = os.path.join(repo, here)
        if not os.path.lexists(whole):
            return False
        if os.path.islink(whole) or not os.path.isdir(whole):
            return here not in tracked
        if n == len(parts):
            return holds_untracked(repo, whole, tracked)
    return False


def holds_untracked(repo, directory, tracked):
    """A file or link somewhere under `directory` that is not tracked at main; an empty directory
    holds none."""
    for where, dirs, files in os.walk(directory):
        links = [d for d in dirs if os.path.islink(os.path.join(where, d))]
        for name in files + links:
            if os.path.relpath(os.path.join(where, name), repo) not in tracked:
                return True
    return False


def require_worktree(blocks, branch):
    """The branch's own linked worktree, unlocked and clean, so a check there proves the sha and
    `worktree remove` will take it: a path, or Red."""
    ref = "refs/heads/" + branch
    for block in blocks[1:]:
        if block.get("branch") == ref and os.path.isdir(block["worktree"]):
            tree = block["worktree"]
            if "locked" in block:
                raise Red("worktree", note="%s is locked" % tree)
            inside = nested(blocks, block, tree)
            if inside:
                raise Red("worktree", note="%s holds other worktrees, which `worktree remove` "
                          "would take with it:\n%s" % (tree, "\n".join(inside)))
            venv = os.path.join(tree, ".venv")
            if os.path.lexists(venv) and not os.path.islink(venv):
                raise Red("worktree", note="%s is neither a link nor absent" % venv)
            dirt = worktree_dirt(tree)
            if dirt:
                raise Red("worktree", note="%s is not clean:\n%s" % (tree, "\n".join(dirt)))
            return tree
    raise Red("worktree", note="no linked worktree has %s checked out" % branch)


def under(path, tree):
    """A parent of `path` is the directory `tree`, by device and inode: a case variant or a link
    in either spelling is the same directory, and a sibling such as `<tree>-2` is not."""
    parent, here = os.path.dirname(os.path.realpath(path)), None
    while parent != here:
        try:
            if os.path.samefile(parent, tree):
                return True
        except OSError:
            pass
        parent, here = os.path.dirname(parent), parent
    return False


def nested(blocks, own, tree):
    """Each other linked worktree whose directory is under `tree`, its status lines below it or
    `clean`. The main checkout never counts; a clone git does not list is not read."""
    found = []
    for block in blocks[1:]:
        path = block.get("worktree", "")
        if block is own or not path or not os.path.isdir(path) or not under(path, tree):
            continue
        p = subprocess.run(("git",) + STATUS, cwd=path, stdin=DEVNULL, stdout=subprocess.PIPE,
                           stderr=DEVNULL, universal_newlines=True, errors="replace")
        lines = p.stdout.splitlines()
        if p.returncode != 0:
            found.append("%s: its status cannot be read" % path)
        else:
            held = "\n".join(["holds"] + ["  " + line for line in lines])
            found.append("%s: %s" % (path, held if lines else "clean"))
    return found


def require_merge_text(message, branch):
    """Line 1 is `Merge <branch>: ` then a non-space character; line 2, when there is one, is
    blank. Read again after the check, since the file can change while it runs."""
    try:
        with open(message, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as err:
        raise Red("merge-file", note="cannot read %s: %s" % (message, err))
    if not text.strip():
        raise Red("merge-file", note="%s is blank" % message)
    lines = text.split("\n")
    head = "Merge %s: " % branch
    if not lines[0].startswith(head) or not lines[0][len(head):][:1].strip():
        raise Red("merge-file", note="line 1 of %s is not `%s` and its text: %s"
                  % (message, head, lines[0]))
    if len(lines) > 1 and lines[1].strip():
        raise Red("merge-file", note="line 2 of %s is not blank: %s" % (message, lines[1]))


def scan_message(repo, tree, full, merged, message):
    """The merge's message through the worktree's hygiene, when its --help names --commits: the
    merge commit made as a dangling object, scanned as the range <sha>..<that commit>. It writes
    one object and no ref, and touches neither main's index nor its files."""
    script = os.path.join(tree, "scripts", "hygiene")
    if not os.path.lexists(script) or not takes_commits(tree, script):
        return
    code, commit = read(repo, "commit-tree", merged, "-p", MAIN, "-p", full, "-F", message)
    if code != 0 or not commit:
        raise Red("merge-file", note="git commit-tree exit %d: no merge commit to scan" % code)
    span = "%s..%s" % (full, commit)
    note("merge-file: scripts/hygiene --require-private --commits %s in %s" % (span, tree))
    code = run(tree, script, "--require-private", "--commits", span)
    if code != 0:
        raise Red("merge-file", code, "the merge message of %s fails the scan" % message)


def require_sha(repo, branch, sha):
    """The named sha is the branch's head and not yet on main: its full form, or Red."""
    code, full = read(repo, "rev-parse", "--verify", "-q", sha + "^{commit}")
    if code != 0 or not full.startswith(sha.lower()):
        raise Red("sha", note="no such commit: " + sha)
    _, head = read(repo, "rev-parse", "--verify", "-q", "refs/heads/" + branch)
    if head != full:
        raise Red("sha", note="%s's head is %s, not %s" % (branch, head, full))
    code, _ = read(repo, "merge-base", "--is-ancestor", full, "main")
    if code == 0:
        raise Red("sha", note="%s is already on main" % full)
    return full


def merge_head(repo):
    return read(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD")[1]


def only_the_merge_staged(repo, before, full):
    """The index holds the merge's result from `before` and nothing beyond it, its conflicts
    aside: so a reset would take back this run's merge and no one else's `git add`."""
    code, tree, conflicted = merge_result(repo, before, full)
    if code not in (0, 1) or not tree:
        return False
    code, differs = read_z(repo, "diff", "--cached", "--name-only", "-z", "--no-renames",
                           "--ignore-submodules=none", tree)
    ita_code, ita = intent_to_add(repo)
    return code == 0 and ita_code == 0 and not ita and set(differs) <= set(conflicted)


def abort_merge(repo, full, before, cut):
    """Abort the merge this run began, and nothing else. Git refuses some merges before it starts
    one, and a MERGE_HEAD that is not <sha> is someone's. A merge cut in pre-merge-commit has
    staged its paths with no MERGE_HEAD yet: `merge --abort` refuses that, and `reset --merge` is
    what it runs. Either one drops a sitting's `git add` made since the last read, with its edit:
    so with HEAD moved or anything but the merge staged, it is left, the land line says so, and a
    retry reads `red main`. A merge whose commit stands, killed or cut in post-merge, still has
    its MERGE_HEAD: `merge --quit` clears that and touches nothing else."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    head = merge_head(repo)
    paths = staged(repo)[1]
    if read(repo, "rev-parse", "HEAD")[1] != before:
        undo = ("merge", "--quit") if head == full else None
        if paths:
            leave(paths)
    elif head == full or (cut and not head and paths):
        undo = ("merge", "--abort") if head == full else ("reset", "--merge")
        if paths and not only_the_merge_staged(repo, before, full):
            undo = leave(paths)
    else:
        undo = None
    if undo:
        code = run(repo, "git", *undo)
        if code != 0:
            note("git %s exit %d: a half merge stays on main, by hand from here" % (" ".join(undo), code))


def leave(paths):
    """No reset: these paths may be someone's. The land line carries it."""
    global LEFT
    LEFT = "staged paths left on main"
    note("%s, not undone, by hand from here:\n%s" % (LEFT, "\n".join(paths)))


def merge(repo, full, message):
    """The merge, confirmed: its exit alone proves nothing. A merge that fails is aborted."""
    global STANDS
    _, before = read(repo, "rev-parse", "HEAD")
    try:
        code = run(repo, "git", "merge", "--no-ff", "--commit", "-F", message, full)
        if code != 0:
            raise Red("merge", code)
        _, head = read(repo, "rev-parse", "HEAD")
        _, second = read(repo, "rev-parse", "-q", "--verify", "HEAD^2")
        if head == before or second != full or merge_head(repo):
            raise Red("merge", note="git merge exited 0, and HEAD is no merge commit of " + full)
    except Exception as err:
        abort_merge(repo, full, before, isinstance(err, Red) and err.step == "cut")
        raise
    finally:
        _, head = read(repo, "rev-parse", "HEAD")
        if head != before:
            STANDS = "merged %s as %s; the merge stands" % (full, head)


def worktree_dirt(tree):
    """The worktree's status lines, less an untracked `.venv` symlink at its top."""
    code, status = read(tree, *STATUS)
    if code != 0:
        raise Red("worktree", note="cannot read the status of " + tree)
    return [line for line in status.splitlines() if line != "?? .venv"]


def drop_venv_link(tree):
    """An untracked `.venv` symlink makes `worktree remove` refuse: the link goes, its target
    stays. A tracked one, or a real directory, is left for the refusal to name."""
    link = os.path.join(tree, ".venv")
    if os.path.islink(link) and read(tree, *STATUS, "--", ".venv")[1] == "?? .venv":
        os.unlink(link)
        note("removed the .venv link in " + tree)


def takes_commits(tree, script):
    """The copy scans a commit range: its --help exits 0 and names --commits. An older copy's
    --commits would exit 2, as a git failure does, so that exit cannot tell them apart."""
    try:
        p = subprocess.run((script, "--help"), cwd=tree, stdin=DEVNULL, stdout=subprocess.PIPE,
                           stderr=DEVNULL, universal_newlines=True, errors="replace")
    except OSError:
        return False
    return p.returncode == 0 and "--commits" in p.stdout


def is_checkout(path):
    """A directory holding a .git entry, a directory or a file (a linked worktree's)."""
    return os.path.isdir(path) and os.path.exists(os.path.join(path, ".git"))


def resolve_repo(arg):
    """A bare name is the checkout of that name in ~/code, else the one such checkout a folder
    below (a repo may sit in a folder under ~/code, even one of its own name); a directory that
    is no checkout never matches. A name with a slash is a path; the cwd never decides. None
    found, or more than one (one checkout reached by two paths counts once), is a Red at
    "repo", as is an empty name, "." or ".."."""
    if os.sep in arg:
        return os.path.realpath(arg)
    if arg in ("", ".", ".."):
        raise Red("repo", 1, "%r is no repo name" % arg)
    code = os.path.expanduser("~/code")
    if is_checkout(os.path.join(code, arg)):
        return os.path.realpath(os.path.join(code, arg))
    below = os.path.join(code, "*", arg)
    found = sorted({os.path.realpath(p) for p in
                    glob.glob(os.path.join(glob.escape(code), "*", glob.escape(arg)))
                    if is_checkout(p)})
    if len(found) == 1:
        return found[0]
    raise Red("repo", 1, "more than one checkout at %s: %s" % (below, ", ".join(found)) if found
              else "no checkout (a directory holding .git) at %s or at %s"
              % (os.path.join(code, arg), below))


def land(repo, branch, sha, message):
    global UNSCANNED
    at("repo")
    blocks = worktrees(repo)
    at("merge-file")
    if not (os.path.isfile(message) and os.access(message, os.R_OK)):
        raise Red("merge-file", note="cannot read " + message)
    require_merge_text(message, branch)
    at("main")
    require_main(repo)
    at("worktree")
    tree = require_worktree(blocks, branch)
    at("sha")
    full = require_sha(repo, branch, sha)
    at("main")
    merged = require_no_overlap(repo, full, branch)
    at("merge-file")
    scan_message(repo, tree, full, merged, message)

    at("check")
    note("check: make check in " + tree)
    code = run(tree, "make", "check")
    if code != 0:
        raise Red("check", code)
    at("hygiene")
    script = os.path.join(tree, "scripts", "hygiene")
    if os.path.lexists(script):
        note("hygiene: scripts/hygiene in " + tree)
        code = run(tree, script)
        if code != 0:
            raise Red("hygiene", code)
        span = "%s..%s" % (MAIN, full)
        if takes_commits(tree, script):
            # --require-private: an unreadable private list would otherwise read clean.
            note("hygiene: scripts/hygiene --require-private --commits %s in %s" % (span, tree))
            code = run(tree, script, "--require-private", "--commits", span)
            if code != 0:
                raise Red("hygiene", code)
        else:
            UNSCANNED = "range not scanned"
            note("hygiene: scripts/hygiene has no --commits; %s not scanned" % span)

    at("sha")
    require_sha(repo, branch, sha)
    at("main")
    require_main(repo)
    merged = require_no_overlap(repo, full, branch)
    at("worktree")
    tree = require_worktree(worktrees(repo), branch)
    at("merge-file")
    require_merge_text(message, branch)
    scan_message(repo, tree, full, merged, message)
    at("merge")
    note("merge: %s into main in %s" % (full, repo))
    merge(repo, full, message)
    note(STANDS)
    at("remove")
    drop_venv_link(tree)
    code = run(repo, "git", "worktree", "remove", tree)
    if code != 0:
        raise Red("remove", code, tree + " stays")
    at("branch")
    # `branch -d` tests the branch's upstream, so these two reads are its test here.
    if read(repo, "merge-base", "--is-ancestor", full, "refs/heads/main")[0] != 0:
        raise Red("branch", note="%s is not on main; %s stays" % (full, branch))
    if read(repo, "rev-parse", "--verify", "-q", "refs/heads/" + branch)[1] != full:
        raise Red("branch", note="%s has moved past %s; it stays" % (branch, full))
    code = run(repo, "git", "branch", "-D", branch)
    if code != 0:
        raise Red("branch", code, branch + " stays")


def main(argv):
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")
    signal.signal(signal.SIGTERM, on_cut)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL"):
        os.environ.pop(name, None)
    name = "?"
    try:
        if len(argv) != 4:
            raise Red("usage", 2, USAGE)
        at("repo")
        name = os.path.basename(os.path.normpath(argv[0]))
        repo = resolve_repo(argv[0])
        name = os.path.basename(repo)
        land(repo, argv[1], argv[2], os.path.abspath(argv[3]))
    except Exception as err:
        red = err if isinstance(err, Red) else Red(REACHED, 1, "%s: %s" % (type(err).__name__, err))
        for text in (red.note, STANDS):
            if text:
                note(text)
        print("land %s: red %s exit %d%s" % (name, red.step, red.code, LEFT and ", " + LEFT), flush=True)
        return red.code
    print("land %s: ok %s, main readied%s" % (name, argv[2], UNSCANNED and ", " + UNSCANNED),
          flush=True)
    return 0
