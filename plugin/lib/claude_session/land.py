"""land: one landing as one job (packet FW4c; hq design/08 §5 row 5; hq's scripts/land at 9f394ce).

  agentik session gate land <repo> <branch> <sha> <merge-file>      queues this as one gate job
  agentik session gate land --in-job <repo> <branch> <sha> <merge-file>   the job itself
  agentik session gate land --dry-run <repo> <branch> <sha> <merge-file>  the reads alone, here

A bare <repo> is that checkout in ~/code, else the one a folder below; one with a slash is a
path; the cwd never decides. <sha> is a prefix of the commit, never a ref's name. Runs, in
order: the merge message's scan (below), `make check` in the branch's worktree, `scripts/hygiene`
there when present, then
`scripts/hygiene --require-private --commits refs/heads/main..<sha>` there when its --help names
`--commits`, `git merge --no-ff --commit -F <merge-file> <sha>` in the repo's main checkout,
`git worktree remove`, `git branch -D`. Stdout is one line, the verdict, and it comes last:

  land <repo>: ok <sha>, main readied            exit 0
  land <repo>: red <step> exit <code>            exit <code>

Ready (packet land4) runs where the worktree's Makefile holds a line that opens `stamp:`; without
one every line and exit is the pin's, a branch behind main red sha. After the worktree's read it
reads `git merge-tree --write-tree` of the head and main, nothing written: main an ancestor of
the head is no merge; a merge with no conflict, or whose every conflict hunk is a derived line, is
made in the worktree; anything else is `red behind exit 1`, nothing written, a note naming each
path. The derived lines (R3): plugin/.claude-plugin/plugin.json's one `"version"` line, a line
opening `Status: version ` in README.md or design/readme/source.md, and any line of
design/readme/rendered.sha256, each taking main's side, the stamp rewriting them; and the rows of
NICE_TO_HAVE.md's and history/NICE-overflow.md's tables, merged by id (R4): main's rows stand, a
row only the branch added is kept, a row one side removed and the other left is removed, a row
both changed is red behind, a repeated id on any side of a hunk is red behind, and a row the
branch added under an id main has since used takes a number above every id on either side. A
renumbered id is rewritten only in `.md` files the branch added (the head has them, main does
not, and they are in the merged tree), as a whole word; a mention anywhere else, code and tests
included, is listed in the note and left. The renumbering writes only regular files (100644 or
100755) of the merged tree, from its text, never through a link. Then `make stamp
STAMP_BASE=<main as read>`: a non-zero exit is `red stamp exit <code>`, and a line written beyond
the derived kinds (NICE rows moved whole to the overflow aside) `red stamp exit 1`, the paths
named, as is a head that moves during `make stamp` (the branch reset to the head read before, the
note naming the commits' subjects); any red or cut between `make stamp` and its commit restores
the stamp's paths, the index too, and removes a file it added. Then
`scripts/plugin-version-check` where it is there: `red version exit <code>`, before the check.
The job's commits are `<branch>: merge main` and `<branch>: plugin <version>`, each closing with
`Gate-Land: <the sha given, whole>`; a stamp that wrote nothing makes none. A head past the sha
given is taken (R8) only when every commit between is the job's by that trailer, on the
first-parent line, a merge's second parent on main, and the job's steps run again from the sha
given in a temp worktree (removed after) give each one's tree; else red sha, the pin's note. Every
later step takes the readied head. Once the head differs from the sha given, the ok line reads
`ok <sha>, main readied, as <head, whole>, plugin <version>` and a red line ends `, as <head>`,
after every other ending, the head read from the worktree, a cut just after a commit of the
job's included. The check's stop line is read from the log's size just before `make
check`, so a stamp's output never makes an unrun. `--dry-run` queues nothing and writes nothing,
in a job or not: the reads up to merge-tree's, then `ready: ...` lines on stdout and `land <repo>:
dry run, nothing queued`, exit 0; a read that reds prints its land line and exits its code. A
head past the sha given whose trailer chain reads true first prints `ready: <branch> is past
<sha7> by its trailers; the rerun is not run dry`; a chain that reads false is red sha.

A cut that leaves staged paths alone adds to that line: `, staged paths left on main`. A red
check adds `, unrun lock|load|wall` (packet gl1, R5, as review 1 amended it) only when all three
hold: the last line of its output that opens `bounded: ` is `bounded: stop: lock`, `... load` or
`... wall`; every non-empty line after it is make's own, opening `make: *** ` or
`make[<n>]: *** `; and make's first `*** [...] Error <n>` line after it carries the code
`scripts/bounded` exits with for that stop, 2 for lock and load, 124 for the wall (no such line,
no unrun). Then `scripts/bounded` refused the check or cut it at its wall, so it did not run to
its end. Anything else is a plain red: a stop line in a failing test's captured output, a stop
line with any other line after it, `bounded: nested stop: <why>` (an inner bound's). The code on the
line is the step's, make's own. The check writes to this run's stderr as at the pin, and the
lines are read from the job's own log (`main`'s `log`, the file that stderr is, by device and
inode), from where the check began, its last 64 KiB, a first line the 64 KiB cut not read; with
no such log the line is the pin's. A
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
or another worktree git lists, the main checkout included, sits under it, a parent of its directory
being this worktree by device and inode, clean or dirty, which `worktree remove` would take, or
dirty so a check there would not prove the sha, or its .venv is neither a link nor absent), sha
(not the branch's head, or already on main, or behind main: the merge would make a tree other than
<sha>'s, so the check would not run on what main would hold; merge main into the branch and land
its new head), merge-file again (when `scripts/hygiene --help` names --commits, the merge commit is
made as a dangling object, `git commit-tree <tree> -p <main as read> -p <sha> -F <merge-file>`, its
stderr to the log, and `scripts/hygiene --require-private --commits <sha>..<it>` scans its message
in the worktree, a non-zero exit red merge-file with hygiene's code; no ref is written), check,
hygiene, merge (a conflict, read before the check, and read again after it; or git merge's own
red), remove, branch (its sha is not on main, or it has moved), cut. After the check, before the
merge, the nested worktrees, main's lead and the merge file's text and scan are read again with
main and the worktree, since the check takes minutes; then main is read once more, and one that
moved since the commit every merged-tree read was given is red sha, so nothing that takes time runs
between the last read of main and the merge. Usage reports 2; a refusal of this script's own
reports 1; a step that ran reports that step's code; any other error reports 1 at the step reached,
its reason on stderr.

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
STOPS = {b"bounded: stop: " + why.encode(): why for why in ("lock", "load", "wall")}  # gl1 R5
CODES = {"lock": 2, "load": 2, "wall": 124}   # scripts/bounded's exit for each stop (gl1 R5)
BOUNDED = b"bounded: "
TAIL = 64 * 1024    # the most of the job's log a red check's stop line is looked for in
READIED = ""        # the head ready gave, whole, once it differs from the sha given (land4 R10)
PLUGIN = ""         # that head's plugin version, for the ok line
TRAILER = "Gate-Land: "
MANIFEST = "plugin/.claude-plugin/plugin.json"
STATUS_FILES = ("README.md", "design/readme/source.md")
STATUS_LINE = "Status: version "
SIDECAR = "design/readme/rendered.sha256"
NICE_FILES = ("NICE_TO_HAVE.md", "history/NICE-overflow.md")
DERIVED = (MANIFEST,) + STATUS_FILES + (SIDECAR,) + NICE_FILES   # land4 R3's files
REGULAR = ("100644", "100755")    # the modes the job writes (review 1, F1 to F3)


class Red(Exception):
    def __init__(self, step, code=1, note="", unrun=""):
        super().__init__(step)
        self.step, self.code, self.note, self.unrun = step, code, note, unrun


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


def log_size(log):
    """The job's log's size when `log` is the file this run's stderr is, by device and
    inode; else None, and no stop line is read."""
    if not log:
        return None
    try:
        sys.stderr.flush()
        mine, there = os.fstat(sys.stderr.fileno()), os.stat(log)
    except (OSError, ValueError):
        return None
    if (mine.st_dev, mine.st_ino) != (there.st_dev, there.st_ino):
        return None
    return there.st_size


def tail_lines(log, begin):
    """The log's lines from `begin`, its last TAIL bytes at most, as bytes, or None. A first
    line the TAIL cut is not read: when the TAIL starts past `begin`, the byte before it is
    read too, and the first line is dropped only when that byte is not a newline (review 1,
    F3: a line that opens the TAIL is whole)."""
    try:
        with open(log, "rb") as fh:
            size = os.fstat(fh.fileno()).st_size
            at = max(begin, size - TAIL)
            edge = at > begin
            fh.seek(at - edge)
            data = fh.read(size - at + edge)
    except (OSError, ValueError):
        return None
    if edge:
        cut = data[:1] != b"\n"
        data = data[1:]
    lines = data.split(b"\n")
    return lines[1:] if edge and cut else lines


def make_says(line):
    """What make's own error line says after its `make: *** ` or `make[<n>]: *** `; else None."""
    if line.startswith(b"make: *** "):
        return line[len(b"make: *** "):]
    head, sep, rest = line.partition(b"]: *** ")
    return rest if sep and head.startswith(b"make[") and head[5:].isdigit() else None


def make_error(said):
    """The <n> of make's `[<target>] Error <n>`, or None."""
    head, sep, n = said.rpartition(b"] Error ")
    return int(n) if sep and said.startswith(b"[") and n.isdigit() else None


def refused(log, begin):
    """`lock`, `load` or `wall` when scripts/bounded stopped the check, else "" (gl1 R5): the
    last line from `begin` that opens `bounded: ` is that stop's line, every non-empty line
    after it is make's own, and make's first `Error <n>` after it is the stop's code."""
    lines = tail_lines(log, begin) or []
    at = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith(BOUNDED)), None)
    why = STOPS.get(lines[at], "") if at is not None else ""
    said = [make_says(x) for x in lines[at + 1:] if x] if why else [None]
    if None in said:
        return ""
    codes = [n for n in map(make_error, said) if n is not None]
    return why if codes and codes[0] == CODES[why] else ""


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
    # -z: each line ends in a NUL and a block in an empty one, so a newline in a path is a path's.
    p = subprocess.run(("git", "worktree", "list", "--porcelain", "-z"), cwd=repo, stdin=DEVNULL,
                       stdout=subprocess.PIPE, stderr=DEVNULL)
    if p.returncode != 0:
        raise Red("repo", note="not a git repo: " + repo)
    blocks, fields = [], {}
    for line in [os.fsdecode(f) for f in p.stdout.split(b"\0")] + [""]:
        if line:
            key, _, value = line.partition(" ")
            fields[key] = value
        elif fields:
            blocks.append(fields)
            fields = {}
    top = blocks[0].get("worktree", "") if blocks else ""
    if not top or "bare" in blocks[0] or os.path.realpath(top) != os.path.realpath(repo):
        raise Red("repo", note="the main checkout is %s, not %s" % (top or "unknown", repo))
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
    """(main, the merged tree), main read first: a merge that would not conflict, that makes
    <sha>'s own tree, whose paths
    hold no dirty path and no untracked file on the main checkout, or Red with nothing changed.
    The paths are the difference from main to the merge's own tree, so a directory-rename target
    counts; --no-renames lists a rename as its delete and its add, so both its paths do."""
    code, ours = read(repo, "rev-parse", "--verify", "-q", MAIN + "^{commit}")
    if code != 0:
        raise Red("main", note="cannot read " + MAIN)
    # Every read below is of that commit, never the ref's name: one main, whatever the ref does.
    code, tree, conflicted = merge_result(repo, ours, full)
    if code == 1:
        raise Red("merge", 1, "the merge would conflict, nothing begun:\n" + "\n".join(conflicted))
    if code != 0 or not tree:
        raise Red("merge", code or 1, "git merge-tree exit %d: it reads no merge (git 2.38 or later "
                  "is needed; unrelated histories refuse here as in git merge)" % code)
    # The check runs on <sha>'s tree: a merge making any other tree lands what no check ran on.
    own_code, own = read(repo, "rev-parse", "--verify", "-q", full + "^{tree}")
    if own_code != 0 or tree != own:
        _, log = read(repo, "log", "--oneline", "%s..%s" % (full, ours))
        raise Red("sha", note="main holds what %s does not, so the check would not run on the tree "
                  "main would hold:\n%s\nmerge main into %s, land its new head"
                  % (full, log, branch))
    code, touched = read_z(repo, "diff", "--name-only", "-z", "--no-renames", ours, tree)
    if code != 0:
        raise Red("main", note="cannot read the paths the merge touches")
    hit = sorted({d for d in dirty_paths(repo) if any(overlaps(d, t) for t in touched)})
    if hit:
        raise Red("main", note="dirty on main and touched by the merge:\n" + "\n".join(hit))
    # Status never lists an ignored file, and the merge would overwrite it.
    code, written = read_z(repo, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=d",
                           ours, tree)
    tree_code, tracked = read_z(repo, "ls-tree", "-r", "-z", "--name-only", ours)
    if code != 0 or tree_code != 0:
        raise Red("main", note="cannot read the paths the merge writes")
    tracked = set(tracked)
    hit = sorted(path for path in written if stands_untracked(repo, path, tracked))
    if hit:
        raise Red("main", note="on main, untracked, and written by the merge:\n" + "\n".join(hit))
    return ours, tree


def require_main_unmoved(repo, ours, full, branch):
    """Main is still the commit the last merged-tree read began from: anything that took time
    since, the message's scan above all, cannot have slipped a commit under the merge."""
    _, now = read(repo, "rev-parse", "--verify", "-q", MAIN + "^{commit}")
    if now != ours:
        _, log = read(repo, "log", "--oneline", "%s..%s" % (ours, MAIN))
        raise Red("sha", note="main moved from %s to %s during the last reads, so the merge would "
                  "hold what no check ran on:\n%s\nmerge main into %s, land its new head"
                  % (ours, now or "nothing", log, branch))


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
    """Each other worktree git lists, the main checkout included, whose directory is under `tree`,
    its status lines below it or `clean`: `worktree remove` would take it, and a main checkout's
    files with it. A sibling never counts; a clone git does not list is not read."""
    found = []
    for block in blocks:
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


def scan_message(repo, tree, full, ours, merged, message):
    """The merge's message through the worktree's hygiene, when its --help names --commits: the
    merge commit made as a dangling object, scanned as the range <sha>..<that commit>. It writes
    one object and no ref, and touches neither main's index nor its files."""
    script = os.path.join(tree, "scripts", "hygiene")
    if not os.path.lexists(script) or not takes_commits(tree, script):
        return
    # Its stderr goes to the log: an unset identity or a NUL in the file reads its own reason.
    sys.stderr.flush()
    p = subprocess.run(("git", "commit-tree", merged, "-p", ours, "-p", full, "-F", message),
                       cwd=repo, stdin=DEVNULL, stdout=subprocess.PIPE, stderr=sys.stderr,
                       universal_newlines=True)
    code, commit = p.returncode, p.stdout.strip()
    if code != 0 or not commit:
        raise Red("merge-file", note="git commit-tree exit %d: no merge commit to scan; its "
                  "reason is above" % code)
    span = "%s..%s" % (full, commit)
    note("merge-file: scripts/hygiene --require-private --commits %s in %s" % (span, tree))
    code = run(tree, script, "--require-private", "--commits", span)
    if code != 0:
        raise Red("merge-file", code, "scripts/hygiene exit %d on the merge message; see its "
                  "stderr above (%s)" % (code, message))


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


# The ready step (packet land4): main merged into a reviewed branch where every conflict is a
# line a landing derives, then the stamp, each as one commit closing with the trailer.

def stamps(tree):
    """R1: the worktree's Makefile holds a line that opens `stamp:`."""
    try:
        with open(os.path.join(tree, "Makefile"), encoding="utf-8", errors="replace") as fh:
            return any(line.startswith("stamp:") for line in fh)
    except OSError:
        return False


def git_bytes(cwd, *args):
    """A git read as bytes: (exit, stdout)."""
    p = subprocess.run(("git",) + args, cwd=cwd, stdin=DEVNULL, stdout=subprocess.PIPE,
                       stderr=DEVNULL)
    return p.returncode, p.stdout


def text_of(data):
    return data.decode("utf-8", "surrogateescape")


def lines_of(text):
    """The lines, each with its newline; a last line with none kept as it is."""
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def blob_at(cwd, rev, path):
    """The path's text at rev, or "" where it has none."""
    code, data = git_bytes(cwd, "cat-file", "blob", "%s:%s" % (rev, path))
    return text_of(data) if code == 0 else ""


def is_version(line):
    return line.lstrip().startswith('"version"')


def is_status(line):
    return line.startswith(STATUS_LINE)


def row_id(line):
    """`n<k>` of a NICE table row, else None."""
    if not line.startswith("|"):
        return None
    cell = line.split("|")[1].strip()
    return cell if cell[:1] == "n" and cell[1:].isdigit() else None


def rows(lines):
    """A NICE table's rows by id, in order."""
    out = {}
    for line in lines:
        rid = row_id(line)
        if rid:
            out.setdefault(rid, line)
    return out


def number(rid):
    return int(rid[1:])


def swap_ids(text, renum):
    """Each whole-word `n<k>` that renum names, rewritten in one pass."""
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i] == "n" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            j = i + 1
            while j < n and text[j] in "0123456789":
                j += 1
            if j > i + 1 and (j == n or not (text[j].isalnum() or text[j] == "_")) \
                    and text[i:j] in renum:
                out.append(renum[text[i:j]])
                i = j
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def merge_file(cwd, ours, base, theirs):
    """The three stages through `git merge-file --diff3`, as segments: ("clean", lines) or
    ("conflict", branch's, base's, main's); None when git cannot merge them."""
    marks = ("<" * 40, "|" * 40, "=" * 40, ">" * 40)
    code, data = git_bytes(cwd, "merge-file", "-p", "--diff3", "--marker-size", "40",
                           "--object-id", "-L", "branch", "-L", "base", "-L", "main",
                           ours, base, theirs)
    if code < 0 or code > 127:
        return None

    def mark(line, i):
        return line.startswith(marks[i]) and line[40:41] in ("", " ", "\n")

    segs, part, cur = [], None, []
    for line in lines_of(text_of(data)):
        if part is None and mark(line, 0):
            segs.append(("clean", cur))
            part, cur = [[], [], []], 0
        elif part is not None and cur == 0 and mark(line, 1):
            cur = 1
        elif part is not None and cur in (0, 1) and line.rstrip("\n") == marks[2]:
            cur = 2
        elif part is not None and cur == 2 and mark(line, 3):
            segs.append(("conflict",) + tuple(part))
            part, cur = None, []
        elif part is None:
            cur.append(line)
        else:
            part[cur].append(line)
    if part is not None:
        return None
    segs.append(("clean", cur))
    return segs


class Behind(Exception):
    """A conflict no landing derives: why."""


def new_id(line, rid, renum):
    at_id = line.index(rid)
    return line[:at_id] + renum[rid] + line[at_id + len(rid):]


def merge_rows(o, b, t, renum):
    """R4 on one conflict hunk of NICE rows: the branch's, base's and main's lines. Main's rows
    stand, a change of the branch's to a row main left taken; a row only the branch added kept,
    renumbered where main has since used its id."""
    O, B, T = rows(o), rows(b), rows(t)
    out = []
    for rid, line in T.items():
        if rid in B and line == B[rid]:
            if rid in O:
                out.append(O[rid])
            continue
        if rid in B and (rid not in O or O[rid] not in (B[rid], line)):
            raise Behind("%s changed on both sides" % rid)
        out.append(line)
    for rid, line in B.items():
        if rid not in T and rid in O and O[rid] != line:
            raise Behind("%s removed on main and changed on the branch" % rid)
    for rid, line in O.items():
        if rid in B or T.get(rid) == line:
            continue
        out.append(new_id(line, rid, renum) if rid in renum else line)
    return out


def renumbered(lines, renum, branch_rows):
    """A branch's row under an id main has since used, in a hunk git merged clean."""
    return [new_id(line, row_id(line), renum)
            if row_id(line) in renum and branch_rows.get(row_id(line)) == line else line
            for line in lines]


def resolve(path, segs, sides, renum, branch_rows):
    """A conflicted derived file's text and its hunk count, or Behind (R3, R4)."""
    out, hunks = [], 0
    for seg in segs:
        if seg[0] == "clean":
            out.extend(renumbered(seg[1], renum, branch_rows) if path in NICE_FILES else seg[1])
            continue
        o, b, t = seg[1:]
        hunks += 1
        every = o + b + t
        if path == SIDECAR:
            out.extend(t)
        elif path == MANIFEST and all(len(x) == 1 and is_version(x[0]) for x in (o, b, t)) \
                and all(sum(map(is_version, s)) == 1 for s in sides):
            out.extend(t)
        elif path in STATUS_FILES and o and t and all(map(is_status, every)):
            out.extend(t)
        elif path in NICE_FILES and every and all(map(row_id, every)):
            for name, side in (("branch's", o), ("base's", b), ("main's", t)):
                ids = [row_id(x) for x in side]
                twice = sorted({i for i in ids if ids.count(i) > 1}, key=number)
                if twice:
                    raise Behind("%s repeats on the %s side of a hunk" % (", ".join(twice), name))
            out.extend(merge_rows(o, b, t, renum))
        else:
            raise Behind("a hunk not of a derived kind: %s" % "".join(every).strip()[:200])
    return "".join(out), hunks


def renumbering(cwd, head, ours, base):
    """R4's new numbers: each id the branch added that main has since used for another row,
    above the highest id on either side, the overflow file included. (renum, branch's rows)."""
    def side(rev):
        found = {}
        for path in NICE_FILES:
            for rid, line in rows(lines_of(blob_at(cwd, rev, path))).items():
                found.setdefault(rid, line)
        return found

    B, O, T = side(base), side(head), side(ours)
    added = {rid: line for rid, line in O.items() if rid not in B}
    used = {rid: line for rid, line in T.items() if rid not in B}
    clash = sorted((rid for rid in added if rid in used and used[rid] != added[rid]), key=number)
    ids = [(row_id(line), path) for path in NICE_FILES
           for line in lines_of(blob_at(cwd, head, path))]
    twice = ["%s: %s repeats on the branch, and main has since used it" % (
        ", ".join(sorted({p for i, p in ids if i == rid})), rid)
        for rid in clash if [i for i, _ in ids].count(rid) > 1]
    if twice:
        raise Red("behind", note="main's changes conflict with the branch's beyond the lines a "
                  "landing derives, nothing written:\n" + "\n".join(twice))
    top = max([number(rid) for rid in list(B) + list(O) + list(T)] or [0])
    return {rid: "n%d" % (top + k + 1) for k, rid in enumerate(clash)}, added


def entries(cwd, rev):
    """{path: mode} of every blob and link in rev's tree."""
    out = {}
    for entry in read_z(cwd, "ls-tree", "-r", "-z", rev)[1]:
        info, _, path = entry.partition("\t")
        out[path] = info.split(" ")[0]
    return out


def regular_at(tree, path):
    """The path is a regular file in the worktree, reached through no link below it."""
    cur = tree
    for part in path.split("/"):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            return False
    return os.path.isfile(cur)


def plan_merge(cwd, head, ours):
    """R2's reads, nothing written: None when main's head is the branch's ancestor; else the
    merge's plan (the files to write, the hunks, the conflicted paths, notes); else Red behind."""
    if read(cwd, "merge-base", "--is-ancestor", ours, head)[0] == 0:
        return None
    code, fields = read_z(cwd, "merge-tree", "--write-tree", "--no-messages", "-z", head, ours)
    if code not in (0, 1) or not fields:
        raise Red("behind", code or 1, "git merge-tree exit %d: it reads no merge" % code)
    tree, stages = fields[0], {}
    for entry in fields[1:]:
        info, _, path = entry.partition("\t")
        mode, oid, stage = (info.split() + ["", "", ""])[:3]
        stages.setdefault(path, {})[stage] = (mode, oid)
    _, base = read(cwd, "merge-base", head, ours)
    renum, branch_rows = renumbering(cwd, head, ours, base) if base else ({}, {})
    files, hunks, bad = {}, 0, []
    for path in sorted(stages):
        got = stages[path]
        modes = {m for m, _ in got.values()}
        if path not in DERIVED or set(got) != {"1", "2", "3"} or len(modes) != 1 \
                or modes - set(REGULAR):
            bad.append("%s: %s" % (path, "a conflict outside the derived lines"
                                   if path not in DERIVED else "not a conflict of lines"))
            continue
        segs = merge_file(cwd, got["2"][1], got["1"][1], got["3"][1])
        sides = [lines_of(text_of(git_bytes(cwd, "cat-file", "blob", got[s][1])[1]))
                 for s in ("1", "2", "3")]
        try:
            if segs is None:
                raise Behind("git merge-file reads no merge")
            files[path], n = resolve(path, segs, sides, renum, branch_rows)
            hunks += n
        except Behind as why:
            bad.append("%s: %s" % (path, why))
    if bad:
        raise Red("behind", note="main's changes conflict with the branch's beyond the lines a "
                  "landing derives, nothing written:\n" + "\n".join(bad))
    notes = []
    if renum:
        notes.append("NICE rows renumbered: " + ", ".join(
            "%s -> %s" % kv for kv in sorted(renum.items(), key=lambda kv: number(kv[0]))))
        merged = entries(cwd, tree)
        for path in NICE_FILES:
            if path not in files and merged.get(path) in REGULAR:
                text = blob_at(cwd, tree, path)
                new = "".join(renumbered(lines_of(text), renum, branch_rows))
                if new != text:
                    files[path] = new
        # R4 as review 1 narrowed it: rewritten only in the .md files the branch added, from the
        # merged tree's text; a mention in any other path the branch added or changed is noted.
        theirs = set(read_z(cwd, "ls-tree", "-r", "-z", "--name-only", ours)[1])
        mine = set(read_z(cwd, "ls-tree", "-r", "-z", "--name-only", head)[1])
        changed = set(read_z(cwd, "diff", "--name-only", "-z", "--no-renames", base, head)[1])
        for path in sorted((mine - theirs) | (changed & mine)):
            if path in NICE_FILES or path in files:
                continue
            if path.endswith(".md") and path not in theirs and merged.get(path) in REGULAR:
                code, data = git_bytes(cwd, "cat-file", "blob", "%s:%s" % (tree, path))
                if code == 0 and b"\0" not in data:
                    text = text_of(data)
                    new = swap_ids(text, renum)
                    if new != text:
                        files[path] = new
                    continue
            code, data = git_bytes(cwd, "cat-file", "blob", "%s:%s" % (head, path))
            if code != 0 or b"\0" in data:
                continue
            text = text_of(data)
            for rid in sorted(renum, key=number):
                if swap_ids(text, {rid: "\0"}) != text:
                    notes.append("%s named in %s, left as it is (that row is now %s)"
                                 % (rid, path, renum[rid]))
    return {"files": files, "hunks": hunks, "paths": sorted(stages), "notes": notes}


def commit_job(tree, subject, given):
    """R6: one commit closing with the trailer; Red at the step reached when git refuses."""
    code = run(tree, "git", "commit", "-q", "-m", subject, "-m", TRAILER + given)
    if code != 0:
        raise Red(REACHED, code, "git commit exit %d in %s" % (code, tree))
    return read(tree, "rev-parse", "HEAD")[1]


def do_merge(tree, branch, given, ours, plan):
    """R2 to R4 written: `git merge --no-commit` of main's commit, the planned files, by name."""
    code = run(tree, "git", "merge", "--no-ff", "--no-commit", "--no-edit", ours)
    try:
        if code not in (0, 1):
            raise Red("behind", code, "git merge exit %d in %s" % (code, tree))
        for path, text in sorted(plan["files"].items()):
            if not regular_at(tree, path):
                raise Red("behind", note="%s is no regular file in %s; nothing written"
                          % (path, tree))
            with open(os.path.join(tree, path), "w", encoding="utf-8",
                      errors="surrogateescape", newline="") as fh:
                fh.write(text)
        if plan["files"]:
            code = run(tree, "git", "add", "--", *sorted(plan["files"]))
            if code != 0:
                raise Red("behind", code, "git add exit %d in %s" % (code, tree))
        left = read_z(tree, "diff", "--name-only", "-z", "--diff-filter=U")[1]
        if left:
            raise Red("behind", note="unresolved after the merge:\n" + "\n".join(left))
        return commit_job(tree, "%s: merge main" % branch, given)
    except BaseException:
        if read(tree, "rev-parse", "-q", "--verify", "MERGE_HEAD")[0] == 0:
            run(tree, "git", "merge", "--abort")
        raise


def changed_paths(tree):
    """The worktree's changes as (status, path), the `.venv` link aside."""
    fields = iter(read_z(tree, *STATUS, "--no-renames", "-z")[1])
    out = []
    for entry in fields:
        if "R" in entry[:2] or "C" in entry[:2]:
            next(fields, "")
        if entry != "?? .venv":
            out.append((entry[:2], entry[3:]))
    return out


def restore(tree, changed):
    """R5: the stamp's paths back as HEAD has them, the index too; a file it added, staged or
    not, is removed (review 1, F4 and F7)."""
    staged = [p for s, p in changed if s != "??"]
    if staged:
        run(tree, "git", "reset", "-q", "--", *staged)
    paths = [p for _, p in changed]
    kept = set(read_z(tree, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *paths)[1]) \
        if paths else set()
    if kept:
        run(tree, "git", "checkout", "-q", "HEAD", "--", *sorted(kept))
    for p in paths:
        if p not in kept and os.path.lexists(os.path.join(tree, p)):
            try:
                os.remove(os.path.join(tree, p))
            except OSError:
                pass


def stamp_diff_off(tree, changed):
    """R5: the paths whose stamped lines are not of R3's kinds, NICE rows moved whole aside."""
    bad, gone, came = [], [], []
    for status, path in changed:
        if status == "??" or path not in DERIVED:
            bad.append(path)
            continue
        data = git_bytes(tree, "diff", "-U0", "--no-color", "--no-ext-diff", "HEAD", "--", path)[1]
        minus, plus, body = [], [], False
        for line in lines_of(text_of(data)):
            if line.startswith("@@"):
                body = True
            elif body and line[:1] == "-":
                minus.append(line[1:])
            elif body and line[:1] == "+":
                plus.append(line[1:])
        every = minus + plus
        if path == MANIFEST:
            fine = all(map(is_version, every))
        elif path in STATUS_FILES:
            fine = all(map(is_status, every))
        elif path == SIDECAR:
            fine = True
        elif path == NICE_FILES[0]:
            fine = not plus and all(map(row_id, minus))
            gone += minus
        else:
            fine = not minus and all(map(row_id, plus))
            came += plus
        if not fine:
            bad.append(path)
    if sorted(gone) != sorted(came):
        bad.extend(p for p in NICE_FILES if p not in bad)
    return bad


def version_in(tree):
    """plugin.json's version as its `"version"` line holds it, or ""."""
    try:
        with open(os.path.join(tree, MANIFEST), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if is_version(line):
                    return line.split(":", 1)[1].strip().rstrip(",").strip().strip('"')
    except OSError:
        pass
    return ""


def do_stamp(tree, branch, given, base):
    """R5: `make stamp` against main's commit as read; its lines as one commit, or none."""
    at("stamp")
    note("stamp: make stamp in " + tree)
    before = read(tree, "rev-parse", "-q", "--verify", "HEAD")[1]
    try:
        code = run(tree, "make", "stamp", "STAMP_BASE=" + base)
        after = read(tree, "rev-parse", "-q", "--verify", "HEAD")[1]
        if after != before:
            # R5, R6: the stamp's lines are the job's to commit (review 1, F6).
            said = read(tree, "log", "--format=%s", "%s..%s" % (before, after))[1]
            run(tree, "git", "reset", "-q", before)
            raise Red("stamp", 1, "make stamp moved the head to %s, its commits: %s; the branch "
                      "reset to %s, the stamp's paths restored"
                      % (after or "none", "; ".join(said.splitlines()) or "none", before))
        changed = changed_paths(tree)
        if code != 0:
            raise Red("stamp", code, "make stamp exit %d; its paths restored" % code)
        bad = stamp_diff_off(tree, changed)
        if bad:
            raise Red("stamp", 1, "make stamp wrote beyond the lines a landing derives; its paths "
                      "restored:\n" + "\n".join(bad))
        if not changed:
            return False
        code = run(tree, "git", "add", "--", *sorted(p for _, p in changed))
        if code != 0:
            raise Red("stamp", code, "git add exit %d in %s" % (code, tree))
        commit_job(tree, "%s: plugin %s" % (branch, version_in(tree) or "?"), given)
        return True
    except BaseException:
        # Any red or cut between `make stamp` and its commit: the next call meets a clean
        # worktree, the index too (review 1, F4 and F7).
        restore(tree, changed_paths(tree))
        raise


def taken_head(repo, tree, branch, sha, dry=False):
    """R8: (the sha given, whole; the branch's head) where the head is that sha, or a head the
    job readied from it; else the pin's red sha."""
    code, full = read(repo, "rev-parse", "--verify", "-q", sha + "^{commit}")
    _, head = read(repo, "rev-parse", "--verify", "-q", "refs/heads/" + branch)
    if code != 0 or not full.startswith(sha.lower()) or head == full \
            or not readied_from(repo, tree, branch, full, head, dry):
        full = require_sha(repo, branch, sha)
    return full, head


def readied_from(repo, tree, branch, full, head, dry):
    """Every commit from the sha given to the head is the job's: on the first-parent line, each
    closing with the trailer naming it, a merge's second parent on main; and the job's merge
    and stamp, run again from the sha given in a temp worktree, give each one's tree."""
    if read(repo, "merge-base", "--is-ancestor", full, head)[0] != 0:
        return False
    steps, prev = [], full
    for commit in read(repo, "rev-list", "--first-parent", "--reverse",
                       "%s..%s" % (full, head))[1].split():
        parents = read(repo, "rev-list", "--parents", "-n", "1", commit)[1].split()[1:]
        body = read(repo, "log", "-1", "--format=%B", commit)[1].strip().split("\n")
        if not parents or parents[0] != prev or len(parents) > 2 or body[-1] != TRAILER + full:
            note("%s is not the job's commit from %s" % (commit, full))
            return False
        if len(parents) == 2 and read(repo, "merge-base", "--is-ancestor", parents[1],
                                      MAIN)[0] != 0:
            note("%s merges %s, which is not on main" % (commit, parents[1]))
            return False
        steps.append((commit, parents[1] if len(parents) == 2 else None))
        prev = commit
    if dry:
        # R11 as review 1 ruled (F8): the rerun writes a temp worktree, so a dry run says the
        # head is taken by its trailers alone.
        print("ready: %s is past %s by its trailers; the rerun is not run dry"
              % (branch, full[:7]), flush=True)
        return True
    return rerun(repo, tree, branch, full, steps)


def rerun(repo, tree, branch, full, steps):
    """The job's steps from the sha given in a temp worktree, removed after: True when each
    gives its commit's tree."""
    global REACHED
    reached, place, root = REACHED, None, os.environ.get("TMPDIR") or "/tmp"
    for k in range(100):
        try:
            place = os.path.join(root, "land-ready-%d-%d" % (os.getpid(), k))
            os.mkdir(place)
            break
        except FileExistsError:
            place = None
    if place is None:
        return False
    try:
        if read(repo, "worktree", "add", "-q", "--detach", place, full)[0] != 0:
            note("cannot add a temp worktree at " + place)
            return False
        venv = os.path.join(tree, ".venv")
        if os.path.islink(venv):
            os.symlink(os.path.realpath(venv), os.path.join(place, ".venv"))
        for commit, second in steps:
            cur = read(place, "rev-parse", "HEAD")[1]
            if second:
                plan = plan_merge(place, cur, second)
                if plan is None:
                    return False
                do_merge(place, branch, full, second, plan)
            else:
                do_stamp(place, branch, full, read(place, "merge-base", cur, MAIN)[1])
            if read(place, "rev-parse", "HEAD^{tree}")[1] != \
                    read(repo, "rev-parse", commit + "^{tree}")[1]:
                note("run again from %s, the job's step does not give %s's tree" % (full, commit))
                return False
        return True
    except Red as red:
        if red.step == "cut":
            raise
        note("run again from %s, the job's step reads red %s: %s" % (full, red.step, red.note))
        return False
    finally:
        if os.path.islink(os.path.join(place, ".venv")):
            os.unlink(os.path.join(place, ".venv"))
        read(repo, "worktree", "remove", "--force", place)
        if os.path.isdir(place):
            subprocess.run(("rm", "-rf", "--", place), stdin=DEVNULL)
        read(repo, "worktree", "prune")
        REACHED = reached


def ready(repo, tree, branch, full, head, dry=False):
    """R2 to R7 in the branch's worktree; the head the rest takes (R9)."""
    global READIED, PLUGIN
    at("behind")
    code, ours = read(repo, "rev-parse", "--verify", "-q", MAIN + "^{commit}")
    if code != 0:
        raise Red("main", note="cannot read " + MAIN)
    plan = plan_merge(tree, head, ours)
    for text in (plan or {}).get("notes", []):
        note(text)
    if dry:
        if plan is None:
            print("ready: %s holds main" % branch, flush=True)
        elif not plan["hunks"]:
            print("ready: would merge main %s into %s, no conflict" % (ours[:7], branch),
                  flush=True)
        else:
            print("ready: would merge main %s into %s, %d derived hunks: %s"
                  % (ours[:7], branch, plan["hunks"], ", ".join(plan["paths"])), flush=True)
        print("ready: would run make stamp and commit its lines", flush=True)
        return head
    if head != full:
        READIED = head
    try:
        if plan is not None:
            note("ready: merge main %s into %s in %s" % (ours, branch, tree))
            READIED = do_merge(tree, branch, full, ours, plan)
        if do_stamp(tree, branch, full, ours):
            READIED = read(tree, "rev-parse", "HEAD")[1]
    except BaseException:
        # R10: a red after the job wrote names the head read from the worktree, a cut just
        # after a commit of the job's included (review 1, F5).
        now = read(tree, "rev-parse", "-q", "--verify", "HEAD")[1]
        READIED = now if now and now != full else READIED
        raise
    at("version")
    script = os.path.join(tree, "scripts", "plugin-version-check")
    if os.path.lexists(script):
        note("version: scripts/plugin-version-check in " + tree)
        code = run(tree, script)
        if code != 0:
            raise Red("version", code)
    if READIED:
        PLUGIN = version_in(tree)
    return read(tree, "rev-parse", "HEAD")[1]


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


def land(repo, branch, sha, message, log=None, dry=False):
    """The steps; True when a dry run stopped after its reads (land4 R11)."""
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
    if stamps(tree):
        given, head = taken_head(repo, tree, branch, sha, dry)
        head = ready(repo, tree, branch, given, head, dry)
        if dry:
            return True
        sha = head
    elif dry:
        print("ready: no stamp target; a branch behind main is red sha", flush=True)
        return True
    at("sha")
    full = require_sha(repo, branch, sha)
    at("main")
    ours, merged = require_no_overlap(repo, full, branch)
    at("merge-file")
    scan_message(repo, tree, full, ours, merged, message)

    at("check")
    note("check: make check in " + tree)
    begin = log_size(log)
    code = run(tree, "make", "check")
    if code != 0:
        raise Red("check", code, unrun=refused(log, begin) if begin is not None else "")
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
    ours, merged = require_no_overlap(repo, full, branch)
    at("worktree")
    tree = require_worktree(worktrees(repo), branch)
    at("merge-file")
    require_merge_text(message, branch)
    scan_message(repo, tree, full, ours, merged, message)
    at("sha")
    require_main_unmoved(repo, ours, full, branch)
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


def main(argv, log=None, dry=False):
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")
    signal.signal(signal.SIGTERM, on_cut)
    # MAKEFILES too (land5 review 2, F1): make reads the files it names before the Makefile.
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "MAKEFLAGS", "MFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "MAKELEVEL"):
        os.environ.pop(name, None)
    name = "?"
    try:
        if len(argv) != 4:
            raise Red("usage", 2, USAGE)
        at("repo")
        name = os.path.basename(os.path.normpath(argv[0]))
        repo = resolve_repo(argv[0])
        name = os.path.basename(repo)
        if land(repo, argv[1], argv[2], os.path.abspath(argv[3]), log, dry):
            print("land %s: dry run, nothing queued" % name, flush=True)
            return 0
    except Exception as err:
        red = err if isinstance(err, Red) else Red(REACHED, 1, "%s: %s" % (type(err).__name__, err))
        for text in (red.note, STANDS):
            if text:
                note(text)
        print("land %s: red %s exit %d%s%s%s" % (name, red.step, red.code,
                                                 red.unrun and ", unrun " + red.unrun,
                                                 LEFT and ", " + LEFT,
                                                 READIED and ", as " + READIED), flush=True)
        return red.code
    print("land %s: ok %s, main readied%s%s" % (
        name, argv[2], UNSCANNED and ", " + UNSCANNED,
        READIED and ", as %s%s" % (READIED, PLUGIN and ", plugin " + PLUGIN)), flush=True)
    return 0
