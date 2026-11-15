"""agentik_install: install-cli, the launcher on PATH with no checkout or venv (hq design/04 §2, §3, §5).

Canonical in agentik-commons; scripts/sync places it at a plugin's lib/agentik_install.py,
byte-identical in every tool, under vendored.sha256. What differs by tool is read from
lib/agentik-tool.conf beside it, the one per-tool place; see names(). It freezes the code this
module runs from, whichever plugin or frozen tree that is, under
<prefix>/share/<tool>/<content hash>/, writes <prefix>/bin/<tool>, its old name's link only where
one stands and the `agentik` door, each by a temp file and a rename, and prunes; `uninstall` takes
back only what reads as that install's. Stdlib, 3.9, and
light at import: a hook imports it for `restore_parent_env`, and no import here reads a file.

The prune: a launcher already running keeps its tree for its whole life, which for a respawn chain
is hours, so deleting every other tree pulls the code out from under it. It keeps the new tree (its
mtime set to now, so a re-install of an old tree counts as newest); every entry a running process
names in its command line or environment, read from `ps -axwwE -o pid=,command=` and compared by
realpath; and the newest KEEP by mtime, which cover a launcher that has read the old file and not
yet exec'd, and any process ps could not see. An entry whose name starts with a dot is the
install's own and no tree. It fails safe: when ps cannot run, exits non-zero, or shows no
environment (a probe variable set in ps's own environment is missing from its output), nothing is
removed. The limit: macOS hides the environment of its platform binaries even from their own user,
so a tree named only in such a process's environment is removed unless it is among the newest KEEP.
"""
import os
import re

MANIFEST = "plugin.json"
DOOR = "agentik"
CONF = "agentik-tool.conf"
KEEP = 3
# What Apple's /usr/bin/python3 adds to the environment (design/04 §3), and the prefix under which
# the launcher records what its parent really had.
APPLE = ("SDKROOT", "CPATH", "LIBRARY_PATH", "MANPATH", "LC_CTYPE")
SAVED = "AGENTIK_PARENT_"
PROBE = "AGENTIK_PRUNE_PROBE"
# SessionStart's own timeout is 10 s: a slow ps costs the prune, never the hook.
REFRESH_PS_TIMEOUT = 3
SKIP_DIRS = ("__pycache__",)
SKIP_FILES = (".DS_Store",)

LAUNCHER = r'''#!/bin/sh
# __NAME__ launcher, written by `__NAME__ install-cli` (hq design/04 §2, §3).
#
# Runs one frozen tree of the plugin's lib/ under /usr/bin/python3. `-I` keeps the cwd,
# PYTHONPATH and the user site off sys.path, so neither the directory a hook fires in nor a
# checkout can change what runs. Run __REMEDY__ to pick up a new plugin, or when the
# interpreter or TREE has gone away: until then a `hook` exits 0, so no event fails; `hook
# SessionStart` says so every time as a JSON `systemMessage` on stdout (a hook's stderr is
# unseen on exit 0), other events once (a marker under the state dir naming the missing
# path, removed by install-cli); other verbs exit 3. Nothing below forks on the way to the exec.
VERSION=__VERSION__
TREE=__TREE__
__OLD_NOTE__
refuse() {   # the path that is gone, then this launcher's own arguments
    gone=$1; shift
    if [ "$1" != hook ]; then
        echo "__NAME__: $gone is gone; run __REMEDY__" >&2
        exit 3
    fi
    state="${XDG_STATE_HOME:-$HOME/.local/state}"
    dir="$state/__NAME__"
__STATE_FALLBACK__
    marker="$dir/install-needed"
    if [ "$2" = SessionStart ]; then
        esc= rest=$gone
        while [ -n "$rest" ]; do
            c=${rest%"${rest#?}"}; rest=${rest#?}
            case $c in \\|\") esc=$esc\\$c ;; [[:cntrl:]]) ;; *) esc=$esc$c ;; esac
        done
        printf '{"systemMessage": "__NAME__: %s is gone; run __REMEDY__"}\n' "$esc"
    else
        seen=; [ ! -r "$marker" ] || read -r seen < "$marker"
        [ "$seen" = "$gone" ] || echo "__NAME__: $gone is gone; run __REMEDY__" >&2
    fi
    /bin/mkdir -p "${marker%/*}" 2>/dev/null && { printf '%s\n' "$gone" > "$marker"; } 2>/dev/null
    exit 0
}
wanted=${AGENTIK_PYTHON:-/usr/bin/python3}; py=$wanted
[ -f "$py" ] && [ -x "$py" ] || py=$(command -v python3) || refuse "$wanted" "$@"
[ -f "$TREE/__RUNNER__" ] && [ -r "$TREE/__RUNNER__" ] || refuse "$TREE" "$@"
cache=${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache
# /usr/bin/python3 adds SDKROOT and LC_CTYPE where unset, and adds to CPATH, LIBRARY_PATH and
# MANPATH even where set. What this tool spawns may see only what this shell saw: record it
# here, and the tool restores it first thing (restore_parent_env).
for v in __APPLE__; do
    unset "AGENTIK_PARENT_$v"
    eval "[ -z \"\${$v+x}\" ] || export AGENTIK_PARENT_$v=\"\$$v\""
done
export AGENTIK_PARENT_ENV=1
# Any other interpreter may be no Python at all, and exit 2 on these flags where a hook's 2 is a
# block, so this shell stays to read its exit, as the plugin's launcher does. From what cannot
# print from Python, a hook's 2, 126 or 127 exits 0 and a verb's failure exits 3. A real Python's
# exit stands. Apple's is execed: with the runner tested above, it reaches the runner or exits 1.
if [ "$py" != /usr/bin/python3 ]; then
    "$py" -I -X pycache_prefix="$cache" "$TREE/__RUNNER__" "$@"; rc=$?
    if [ "$rc" != 0 ] && { [ "$1" != hook ] || [ "$rc" = 2 ] || [ "$rc" = 126 ] || [ "$rc" = 127 ]; }; then
        [ "$("$py" -I -c 'print("python")' 2>/dev/null </dev/null)" = python ] || refuse "$py" "$@"
    fi
    exit "$rc"
fi
exec "$py" -I -X pycache_prefix="$cache" "$TREE/__RUNNER__" "$@"
'''

# Written only when the tool has the name; under the old name, on a terminal, for a verb other
# than `hook`: one note (agentik-r1 §4.3).
OLD_NOTE = '''if [ "${0##*/}" = %(old)s ] && [ -t 2 ] && [ "$1" != hook ]; then
    echo "%(old)s: renamed; use 'agentik %(word)s …' (ends 2026-12-31)" >&2
fi'''
# Written only when the tool has one: the old state folder while the new one does not exist.
STATE_FALLBACK = '''    [ -e "$dir" ] || [ ! -e "$state/%(old)s" ] || dir="$state/%(old)s"'''


# ---- the one per-tool place ----------------------------------------------------------------

KEYS = ("tool_name", "remedy", "runner", "old_name", "old_state")
_CONF_LINE = re.compile(r"^([a-z_]+)=([A-Za-z0-9_./:@-]*)$")
_TOOL = re.compile(r"^agentik-[a-z][a-z0-9-]*$")


def _lib():
    return os.path.dirname(os.path.realpath(__file__))


def names(lib=None):
    """The tool's values, from lib/agentik-tool.conf, every key once as `key=value`, no quotes:
    tool_name, its executable and share folder (`agentik-<tool>`); remedy, the command a refusal
    names (`/<tool>:install-cli`); runner, the file in lib/ a launcher runs; old_name, an old
    executable to keep as a link, or empty; old_state, an old state folder to fall back on, or
    empty. A value is a plain word, so the launcher takes it unquoted. A ValueError or OSError
    when it is absent or malformed."""
    path = os.path.join(lib or _lib(), CONF)
    found = {}
    # Split on LF alone and refuse a line with whitespace or a CR at either end, as the launcher's
    # `read` loop does, so an indented or CRLF file fails here and at sync, never at hook time.
    with open(path, encoding="utf-8", newline="") as fh:
        for line in fh.read().split("\n"):
            if line != line.strip(" \t\r\v\f"):
                raise ValueError("%s: whitespace or a CR around a line: %r" % (CONF, line[:80]))
            if not line or line.startswith("#"):
                continue
            m = _CONF_LINE.match(line)
            if not m or m.group(1) not in KEYS or m.group(1) in found:
                raise ValueError("%s: bad line: %s" % (CONF, line[:80]))
            found[m.group(1)] = m.group(2)
    missing = [k for k in KEYS if k not in found]
    if missing:
        raise ValueError("%s: missing %s" % (CONF, ", ".join(missing)))
    if not _TOOL.match(found["tool_name"]):
        raise ValueError("%s: tool_name %s is not agentik-<tool>" % (CONF, found["tool_name"]))
    if not found["remedy"] or not found["runner"]:
        raise ValueError("%s: remedy and runner want a value" % CONF)
    return found


def version(lib=None):
    """The version, from plugin.json, the one pin (design/04 §6): in the plugin, its manifest; in
    a frozen tree, the copy beside the code. Never raises: an import may lean on it."""
    import json
    lib = lib or _lib()
    for path in (os.path.join(os.path.dirname(lib), ".claude-plugin", MANIFEST),
                 os.path.join(lib, MANIFEST)):
        try:
            with open(path, encoding="utf-8") as fh:
                found = json.load(fh)["version"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(found, str) and found:
            return found
    return "0.0.0-unknown"


# ---- the parent's environment --------------------------------------------------------------

def restore_parent_env(environ=os.environ):
    """The launcher's record, undone: each of APPLE back to what the launcher's shell saw, absent
    where it was absent, and the record gone, so nothing this process spawns sees either. With no
    record (a test, an old launcher) nothing moves. Both launchers write it. True when it restored."""
    if environ.pop(SAVED + "ENV", None) is None:
        return False
    for name in APPLE:
        saved = environ.pop(SAVED + name, None)
        if saved is None:
            environ.pop(name, None)
        else:
            environ[name] = saved
    return True


def parent_record(environ=os.environ):
    """The record for a child Python this process spawns by itself, past the launcher: it may
    add LC_CTYPE again as it starts, and restores from this."""
    record = {SAVED + "ENV": "1"}
    for name in APPLE:
        if name in environ:
            record[SAVED + name] = environ[name]
    return record


# ---- the freeze ----------------------------------------------------------------------------

def is_frozen(lib):
    return os.path.isfile(os.path.join(lib, MANIFEST))


def _source():
    """(lib, manifest, door) of the code this module runs from: the plugin's lib/ with its
    manifest and door elsewhere in the plugin, or a frozen tree holding all three."""
    lib = _lib()
    if is_frozen(lib):
        return lib, os.path.join(lib, MANIFEST), os.path.join(lib, DOOR)
    plugin = os.path.dirname(lib)
    return (lib, os.path.join(plugin, ".claude-plugin", MANIFEST), os.path.join(plugin, "bin", DOOR))


def _walk(root):
    """{path under root: path}, every file but bytecode."""
    found = {}
    for here, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name not in SKIP_FILES and not name.endswith(".pyc"):
                path = os.path.join(here, name)
                found[os.path.relpath(path, root)] = path
    return found


def _hash(files):
    """The tree's name, from its files' names and contents (no git is at hand): a bump alone is
    a new tree, or `--version` would lie."""
    import hashlib
    h = hashlib.sha256()
    for rel in sorted(files):
        with open(files[rel], "rb") as fh:
            data = fh.read()
        h.update(("%s\0%d\0" % (rel, len(data))).encode("utf-8", "surrogateescape"))
        h.update(data)
    return h.hexdigest()[:40]


def _freeze(share, lib, manifest, door, runner):
    """The tree's name, its folder whole under `share`: staged beside it, then one rename."""
    import shutil
    import tempfile
    files = _walk(lib)
    files[MANIFEST] = manifest
    files[DOOR] = door
    name = _hash(files)
    code = os.path.join(share, name)
    if os.path.isdir(code) and _hash(_walk(code)) == name:
        return name
    stage = tempfile.mkdtemp(prefix=".tmp-", dir=share)
    try:
        os.chmod(stage, 0o755)
        new = os.path.join(stage, name)
        for rel, path in files.items():
            to = os.path.join(new, rel)
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.copyfile(path, to)
            os.chmod(to, 0o755 if rel in (DOOR, runner) else 0o644)
        if os.path.lexists(code):    # not what its name says: a prune cut short, or a hand
            os.rename(code, os.path.join(stage, "old"))
        os.rename(new, code)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return name


def _replace(path, write):
    """`write(temp)` beside `path`, then one rename over it; no temp left on a failure."""
    temp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    try:
        if os.path.lexists(temp):
            os.unlink(temp)
        write(temp)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def launcher_text(tree, ver, conf=None):
    """The launcher for one frozen tree. One pass, so a path or a version cannot hold a token
    that a later replacement would read."""
    import shlex
    conf = conf or names()
    word = conf["tool_name"][len("agentik-"):]
    old, old_state = conf["old_name"], conf["old_state"]
    values = {"__NAME__": conf["tool_name"], "__REMEDY__": conf["remedy"], "__RUNNER__": conf["runner"],
              "__OLD_NOTE__": OLD_NOTE % {"old": old, "word": word} if old else "",
              "__STATE_FALLBACK__": STATE_FALLBACK % {"old": old_state} if old_state else "",
              "__APPLE__": " ".join(APPLE), "__VERSION__": shlex.quote(ver),
              "__TREE__": shlex.quote(str(tree))}
    return re.sub(r"__[A-Z_]+__", lambda m: values[m.group(0)], LAUNCHER)


def _write_launcher(path, text):
    def write(temp):
        with open(temp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(temp, 0o755)
    _replace(path, write)


def _write_door(path, door):
    def write(temp):
        import shutil
        shutil.copyfile(door, temp)
        os.chmod(temp, 0o755)
    _replace(path, write)


def _ascii(text):
    """`text` with each byte outside ASCII escaped, so a line prints on any stream."""
    try:
        return str(text).encode("utf-8", "surrogateescape").decode("ascii", "backslashreplace")
    except UnicodeError:
        return str(text).encode("ascii", "backslashreplace").decode("ascii")


def read_regular(path, limit=-1):
    """The bytes of the regular file at `path`, a link followed, at most `limit`; None for a path
    that is absent or no regular file, which is never opened, so a FIFO never blocks. It opens
    without blocking and checks the open file again. Never raises."""
    import stat
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            return None
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except (OSError, ValueError):
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, "rb") as fh:
            fd = None
            return fh.read(limit)
    except (OSError, ValueError):
        return None
    finally:
        if fd is not None:
            os.close(fd)


def _regular_version(path):
    """The VERSION line of the regular file at `path`, or None; never raises."""
    found = read_launcher(path)
    return found["version"] if found else None


def door_fate(path, door):
    """What an install does with the door at `path`, given this tree's `door`: `write` (no file
    there, or an older door), `keep` (equal or newer), `link` (a symlink) or `unversioned` (not a
    regular file, or a VERSION line here or there that reads as no version). It opens a regular
    file only, decided by lstat, and never raises."""
    import stat
    try:
        mode = os.lstat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return "write"
    except OSError:
        return "unversioned"
    if stat.S_ISLNK(mode):
        return "link"
    if not stat.S_ISREG(mode):
        return "unversioned"
    a, b = order(_regular_version(path)), order(_regular_version(door))
    if a is None or b is None:
        return "unversioned"
    return "write" if b > a else "keep"


def _door(path, door):
    """The shared `agentik` door moves forward only, as a launcher does: absent or older, it is
    written; equal or newer, it stays byte for byte; a link, a file that is not a regular one, or
    a VERSION line here or there that does not read as a version, leaves it alone. None, or the
    line that says why it stayed, in ASCII."""
    fate = door_fate(path, door)
    if fate == "write":
        _write_door(path, door)
    if fate == "link":
        return _ascii("the door %s is a link; left alone" % path)
    if fate == "unversioned":
        if not os.path.isfile(path) or os.path.islink(path):
            return _ascii("the door %s is not a regular file; left alone" % path)
        return _ascii("the door %s has no version to compare (%s there, %s here); left alone"
                      % (path, _regular_version(path), _regular_version(door)))
    return None


def _marker(env, conf):
    """The launcher's `install-needed` marker: the tool's state folder, or its old one where only
    that exists."""
    state = env.get("XDG_STATE_HOME") or os.path.join(env.get("HOME", ""), ".local", "state")
    folder = os.path.join(state, conf["tool_name"])
    old = conf["old_state"]
    if old and not os.path.exists(folder) and os.path.exists(os.path.join(state, old)):
        folder = os.path.join(state, old)
    return os.path.join(folder, "install-needed")


def _clear_marker(env, conf):
    try:
        os.unlink(_marker(env, conf))
    except OSError:
        pass


def _sweep(share):
    """Under the lock every staging folder is a crash's."""
    import shutil
    for name in os.listdir(share):
        if name.startswith(".tmp-"):
            shutil.rmtree(os.path.join(share, name), ignore_errors=True)


def _lock(share, wait=True, make=True):
    """The install's one lock, `<share>/.lock` held open for the process's turn; None when
    another holds it and `wait` is off. It opens for writing alone, since `flock` needs neither
    bit. It follows no link and never blocks on the open: a link,
    a FIFO or a folder there is an OSError. Once it holds the lock it checks that the path still
    names the file it holds, and takes it again where it does not, so a waiter on a `.lock` an
    uninstall removed never holds a lock no one else can see. `make` off: the share is not made."""
    import errno
    import fcntl
    import stat
    path = os.path.join(share, ".lock")
    while True:
        if make:
            os.makedirs(share, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o666)
        try:
            held = os.fstat(fd)
            if not stat.S_ISREG(held.st_mode):
                raise OSError(errno.EINVAL, "not a regular file", path)
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        try:
            now = os.lstat(path)
        except FileNotFoundError:
            now = None
        if now is not None and (now.st_dev, now.st_ino) == (held.st_dev, held.st_ino):
            return os.fdopen(fd, "a")
        os.close(fd)


def _old_link(bin_dir, old):
    """<bin>/<old> where a link of that name stands already, to refresh; else None, and nothing there moves."""
    return os.path.join(bin_dir, old) if old and os.path.islink(os.path.join(bin_dir, old)) else None


def _locked_install(prefix, share, env, conf, ps_timeout=60):
    name, old = conf["tool_name"], conf["old_name"]
    bin_dir = os.path.join(prefix, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    _sweep(share)
    lib, manifest, door = _source()
    ver = version()
    tree = _freeze(share, lib, manifest, door, conf["runner"])
    code = os.path.join(share, tree)
    launcher = os.path.join(bin_dir, name)
    note = _door(os.path.join(bin_dir, DOOR), door)
    link = _old_link(bin_dir, old)
    if link:
        _replace(link, lambda temp: os.symlink(name, temp))
    _write_launcher(launcher, launcher_text(code, ver, conf))    # last: what a retry reads
    try:
        pruned, lines = prune(share, tree, ps_timeout=ps_timeout)
    except Exception as e:                                       # noqa: BLE001
        pruned, lines = 1, ["prune-trees: %s" % e]
    if pruned:
        lines.append("the prune failed; every old tree kept")
    if note:
        lines.insert(0, note)
    home = env.get("HOME")
    if home and os.path.realpath(prefix) == os.path.realpath(os.path.join(home, ".local")):
        _clear_marker(env, conf)    # HOME's marker is its own launcher's; another prefix's is not
    return {"launcher": launcher, "tree": code, "version": ver, "door": os.path.join(bin_dir, DOOR),
            "link": link, "pruned": lines}


def install(prefix=None, env=None, dry_run=False):
    """The verb's work; what it wrote, or an OSError, KeyError or ValueError. `door_fate` is read
    before any write; `on_path` is true when <prefix>/bin is an entry of the env's PATH. With
    `dry_run` it takes no lock and writes nothing: `tree` is None and `pruned` empty."""
    env = os.environ if env is None else env
    conf = names()
    if prefix == "~" or (prefix or "").startswith("~/"):    # make quotes PREFIX, so no shell did
        prefix = env["HOME"] + prefix[1:]
    prefix = os.path.abspath(os.path.expanduser(prefix or os.path.join(env["HOME"], ".local")))
    share = os.path.join(prefix, "share", conf["tool_name"])
    bin_dir = os.path.join(prefix, "bin")
    door = os.path.join(bin_dir, DOOR)
    seen = {"door_fate": door_fate(door, _source()[2]),
            "on_path": os.path.normpath(bin_dir) in [
                os.path.normpath(p) for p in (env.get("PATH") or "").split(os.pathsep) if p]}
    if dry_run:
        old = conf["old_name"]
        done = {"launcher": os.path.join(bin_dir, conf["tool_name"]), "tree": None, "version": version(),
                "door": door, "link": _old_link(bin_dir, old), "pruned": []}
    else:
        lock = _lock(share)
        try:
            done = _locked_install(prefix, share, env, conf)
        finally:
            lock.close()
    done.update(seen)
    return done


def shown(path, env=None):
    """A path as a person reads it: from `~` where it is under HOME."""
    home = ((os.environ if env is None else env).get("HOME") or "").rstrip("/")
    return "~" + path[len(home):] if home and path.startswith(home + "/") else path


def prune_news(lines):
    """The lines of `done["pruned"]` worth saying: the prune's summary only where a tree went."""
    return [l for l in lines if not re.fullmatch(r"prune-trees: removed 0, kept \d+ \(\d+ live, the newest \d+\)", l)]


def install_cli(prefix=None, env=None):
    """The verb `<tool> install-cli [--prefix P]`, for a tool's command line to call: its exit
    code. 0 done; 1 it could not (the reason on stderr), nothing moved past what it had written."""
    import sys
    try:
        done = install(prefix, env)
    except (OSError, KeyError, ValueError) as e:
        print("install-cli: %s" % e, file=sys.stderr)
        return 1
    link = " %s links to it." % shown(done["link"], env) if done["link"] else ""
    print("Placed %s %s and %s.%s" % (shown(done["launcher"], env), done["version"], shown(done["door"], env), link))
    for line in prune_news(done["pruned"]):
        print(line)
    if not done["on_path"]:
        bin_dir = os.path.dirname(done["launcher"])
        print('%s is not on PATH; add: export PATH="%s:$PATH"' % (bin_dir, bin_dir))
    return 0


# ---- the prune -----------------------------------------------------------------------------

def processes(ps, timeout=60):
    """(every process's command line and environment as one text, None) or (None, why)."""
    import secrets
    import subprocess
    token = secrets.token_hex(8)
    try:
        r = subprocess.run([ps, "-axwwE", "-o", "pid=,command="], capture_output=True,
                           text=True, errors="replace", timeout=timeout,
                           env=dict(os.environ, **{PROBE: token}))
    except (OSError, subprocess.SubprocessError) as e:
        return None, "%s: %s" % (ps, e)
    if r.returncode != 0:
        return None, "%s exited %d" % (ps, r.returncode)
    if "%s=%s" % (PROBE, token) not in r.stdout:
        return None, "no process environment is visible"
    return r.stdout, None


# An absolute path in ps output: it starts the text, or follows whitespace, `:`, `=` or a
# quote, and runs to the next of those.
_PATHS = r"(?<![^\s:='\"])/[^\s:'\"]*"


_NAME_CHAR = re.compile(r"[A-Za-z0-9._-]")


def named(text, share, entries):
    """Which of `entries`, the names right under `share`, a process text names. Each absolute
    path in the text is compared by realpath (a symlink or a doubled slash still names its
    tree); the share's own spellings are matched literally too, so a share path with a space,
    which no path token can hold, still counts. An entry counts at a path boundary: what
    follows its name is the end, or anything a name does not hold (`,` `;` `)` `=`), so a
    list or an option still names it, and `<share>/<tree>x` does not; on doubt it counts."""
    real = os.path.realpath(share).rstrip("/")
    found = set()
    for root in {str(share).rstrip("/"), real}:
        found.update(re.findall(re.escape(root) + r"/([^/:\s'\"]+)", text))
    for token in set(re.findall(_PATHS, text)):
        try:
            resolved = os.path.realpath(token)
        except (OSError, ValueError):
            continue
        if resolved.startswith(real + "/"):
            found.add(resolved[len(real) + 1:].split("/", 1)[0])
    return {e for e in entries
            if any(f == e or (f.startswith(e) and not _NAME_CHAR.match(f[len(e)])) for f in found)}


def _remove(path):
    import shutil
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def prune(share, new, keep=KEEP, ps="ps", ps_timeout=60):
    """(exit code, the lines to say). Never removes `new`; on doubt removes nothing."""
    share = str(share)
    tree = os.path.join(share, new)
    if keep < 1 or "/" in new or new in ("", ".", "..") or not os.path.isdir(tree):
        return 2, ["prune-trees: %s is not a tree under %s (or keep < 1)" % (new, share)]
    os.utime(tree)
    text, why = processes(ps, ps_timeout)
    if text is None:
        return 0, ["prune-trees: %s; keeping every tree" % why]
    entries = sorted((n for n in os.listdir(share) if not n.startswith(".")),
                     key=lambda n: (os.lstat(os.path.join(share, n)).st_mtime_ns, n), reverse=True)
    live = named(text, share, entries)
    newest = set(entries[:keep]) | {new}
    seen = [n for n in entries if n in live]
    lines = []
    removed, failed = 0, 0
    for name in entries:
        if name in newest or name in live:
            continue
        try:
            _remove(os.path.join(share, name))
            removed += 1
        except OSError as e:
            failed += 1
            lines.append("prune-trees: %s: %s" % (os.path.join(share, name), e))
    lines.append("prune-trees: removed %d, kept %d (%d live, the newest %d)%s"
                 % (removed, len(entries) - removed, len(seen), keep,
                    ", %d failed" % failed if failed else ""))
    return 0, lines


# ---- the uninstall: install-cli reversed ---------------------------------------------------

PS = "ps"                         # what `uninstall` reads the process list with; a test's stub
LAUNCHER_MAX = 65536              # a launcher install-cli wrote is under this many bytes
_TREE_NAME = re.compile(r"^[0-9a-f]{40}$")    # _freeze's name for a tree: _hash()[:40]
DOOR_LINE = "# agentik: the front door"
NOT_OURS = "not the launcher install-cli wrote"


def _homes(env):
    """The home folder's real path, by the env and by the user database."""
    found = set()
    if env.get("HOME"):
        found.add(os.path.realpath(env["HOME"]))
    try:
        import pwd
        found.add(os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir))
    except (ImportError, KeyError, OSError):
        pass
    return found


def _real_dir(path):
    import stat
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def _under(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def _launcher_form(path, name):
    """R3's first three tests: a regular file and no link, under LAUNCHER_MAX bytes, whose second
    line is LAUNCHER's for `name` (the one form that line has had). It reads a regular file only."""
    import stat
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode) or st.st_size >= LAUNCHER_MAX:
        return False
    data = read_regular(path, LAUNCHER_MAX)
    if data is None:
        return False
    lines = data.decode("utf-8", "surrogateescape").split("\n")
    return len(lines) > 1 and lines[1] == LAUNCHER.split("\n")[1].replace("__NAME__", name)


def _ours(path, name, share):
    """The launcher install-cli wrote for `name`: its form; the text `TREE=` and the text
    `VERSION=` each exactly once in the whole file, as the template writes them, so no indented,
    exported or second assignment hides; the `TREE=` line, whole, `TREE=` and its value quoted as
    the template quotes it, nothing after; and that TREE under the share, both made real paths."""
    import shlex
    if not _launcher_form(path, name):
        return False
    data = read_regular(path, LAUNCHER_MAX)
    text = data.decode("utf-8", "surrogateescape") if data is not None else ""
    if text.count("TREE=") != 1 or text.count("VERSION=") != 1:
        return False
    line = re.search(r"(?m)^TREE=(.*)$", text)
    try:
        words = shlex.split(line.group(1)) if line else []
    except ValueError:
        return False
    if len(words) != 1 or shlex.quote(words[0]) != line.group(1):
        return False
    tree = words[0]
    return os.path.realpath(tree).startswith(os.path.realpath(share).rstrip("/") + "/")


def _door_why(path, bin_dir, name, own=()):
    """None where the door at `path` may go (R7), else why it stays: another entry named
    `agentik-<word>` in the bin folder, a file or a link, keeps it; `own`, the tool's links this
    call removes, do not."""
    import stat
    try:
        mode = os.lstat(path).st_mode
    except OSError as e:
        return e.strerror or str(e)
    if stat.S_ISLNK(mode):
        return "a link"
    if not stat.S_ISREG(mode):
        return "not a regular file"
    data = read_regular(path, LAUNCHER_MAX)
    lines = data.decode("utf-8", "surrogateescape").split("\n") if data is not None else []
    if len(lines) < 2 or not lines[1].startswith(DOOR_LINE) or not re.search(r"(?m)^VERSION=", "\n".join(lines)):
        return "not the agentik door"
    try:
        entries = sorted(os.listdir(bin_dir))
    except OSError as e:
        return e.strerror or str(e)
    for entry in entries:
        if entry in (DOOR, name) or entry in own:
            continue
        if _TOOL.match(entry) or _launcher_form(os.path.join(bin_dir, entry), entry):
            return "%s stands" % _ascii(entry)
    return None


def _held(share, entries, spare):
    """None, or what holds the uninstall: a process list that cannot be read, or a process,
    not in `spare`, that names a path under the share (`entries`, every name in it)."""
    text, why = processes(PS)
    if text is None:
        return why
    spare = {str(p) for p in spare}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if not parts or parts[0] in spare:
            continue
        live = named(line, share, entries)
        if live:
            return "pid %s names %s" % (parts[0], sorted(live)[0])
    return None


def _bounded(path, allowed):
    """R8: before each removal, the path, its folder made real, inside what may go."""
    real = os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))
    if not allowed(real):
        raise AssertionError("uninstall: %s lies outside what it may remove" % _ascii(path))


def _take(path, allowed, done):
    """`path` removed by a walk that follows no link, in sorted order: a folder's entries, then
    the folder. `done[0]` counts what went, so a walk that fails midway can say so."""
    import stat
    if stat.S_ISDIR(os.lstat(path).st_mode):
        for name in sorted(os.listdir(path)):
            _take(os.path.join(path, name), allowed, done)
        _bounded(path, allowed)
        os.rmdir(path)
    else:
        _bounded(path, allowed)
        os.unlink(path)
    done[0] += 1


SHARE_BAD = "the share is not a real folder"
LOCK_BAD = "the lock is not a regular file"


def _mode(path):
    """os.lstat's mode, None where it cannot be read."""
    try:
        return os.lstat(path).st_mode
    except OSError:
        return None


def _plan(tool_name, prefix, env, door):
    """([(path, what, None to remove, or why it stays)] in the order to act, every name in the
    share, and whether the share passes R5). A share there that fails R5, or a `.lock` there
    that is no regular file, keeps every row."""
    import stat
    bin_dir = os.path.join(prefix, "bin")
    launcher = os.path.join(bin_dir, tool_name)
    share = os.path.join(prefix, "share", tool_name)
    root = _share_real(prefix, tool_name)
    there = os.path.lexists(share)
    ok = there and _real_dir(share) and os.path.realpath(share) == root
    lock_mode = _mode(os.path.join(share, ".lock")) if ok else None
    gate = SHARE_BAD if there and not ok else (
        LOCK_BAD if lock_mode is not None and not stat.S_ISREG(lock_mode) else None)
    plan, names_, foreign = [], [], gate
    if os.path.lexists(launcher):
        foreign = gate or (None if _ours(launcher, tool_name, share) else NOT_OURS)
        plan.append((launcher, "launcher", foreign))
    try:
        entries = sorted(os.listdir(bin_dir))
    except OSError:
        entries = []
    own = set()
    for entry in entries:
        path = os.path.join(bin_dir, entry)
        if entry in (DOOR, tool_name) or not os.path.islink(path):
            continue
        try:
            text = os.readlink(path)
        except OSError:
            continue
        if text == tool_name or (ok and os.path.realpath(path).startswith(root + "/")):
            plan.append((path, "link", foreign))
            own.add(entry)
    if ok:
        names_ = sorted(os.listdir(share))
        trees = [n for n in names_ if _TREE_NAME.match(n) and _real_dir(os.path.join(share, n))]
        temps = [n for n in names_ if n.startswith(".tmp-")]
        lock = [n for n in names_ if n == ".lock"]
        others = [n for n in names_ if n not in trees and n not in temps and n not in lock]
        for n in trees + temps:
            plan.append((os.path.join(share, n), "tree", foreign))
        for n in others:
            plan.append((os.path.join(share, n), "share", gate or "not install-cli's"))
        for n in lock:
            plan.append((os.path.join(share, n), "share", foreign))
        plan.append((share, "share", foreign or ("holds what install-cli did not write" if others else None)))
    elif there:
        plan.append((share, "share", gate))
    home = env.get("HOME")
    if home and os.path.realpath(prefix) == os.path.realpath(os.path.join(home, ".local")):
        old = ""
        try:
            conf = names()
            old = conf["old_state"] if conf["tool_name"] == tool_name else ""
        except (OSError, ValueError):
            pass
        marker = _marker(env, {"tool_name": tool_name, "old_state": old})
        if os.path.lexists(marker):
            plan.append((marker, "marker", foreign))
    if door:
        path = os.path.join(bin_dir, DOOR)
        if os.path.lexists(path):
            plan.append((path, "door", foreign or _door_why(path, bin_dir, tool_name, own)))
    return plan, names_, ok


def _share_real(prefix, tool_name):
    return os.path.join(os.path.realpath(os.path.join(prefix, "share")), tool_name)


def uninstall(tool_name, prefix=None, door=False, dry=False, spare=()):
    """install-cli reversed: <prefix>/bin/<tool_name> where it reads as the launcher install-cli
    wrote, the links to it or into its share, the frozen trees, the share, the default prefix's
    `install-needed` marker, and with `door` the `agentik` door where no other `agentik-<word>`
    stands. It removes only what the code can show install-cli wrote; a launcher it did not
    write, a share that is no real folder at its place or a `.lock` that is no regular file
    keeps everything, a process naming a path under the share (not in `spare`) or a process
    list it cannot read holds everything, read before the share's lock and again under it, and
    with `dry` it reads alone. A call that removes nothing leaves the disk as it was, a `.lock`
    it made included. [(path, what, fate)] in the order acted on, `what` launcher, link, tree,
    share, marker or door, `fate` removed, would remove or `kept: <why>` (a tree whose walk
    failed midway `kept: partly removed, <why>`); it prints nothing. A ValueError for a name
    that is no `agentik-<tool>`, before any read of the disk, and for a prefix that is `/` or
    the home folder's parent."""
    if not isinstance(tool_name, str) or "\n" in tool_name or not _TOOL.match(tool_name):
        raise ValueError("uninstall: %s is not agentik-<tool>" % _ascii(repr(tool_name)))
    env = os.environ
    if prefix == "~" or (prefix or "").startswith("~/"):
        prefix = env["HOME"] + prefix[1:]
    prefix = os.path.abspath(os.path.expanduser(prefix or os.path.join(env["HOME"], ".local")))
    real = os.path.realpath(prefix)
    if real == "/" or real in {os.path.dirname(h) for h in _homes(env)}:
        raise ValueError("uninstall: %s is no prefix to remove from" % _ascii(prefix))
    share = os.path.join(prefix, "share", tool_name)
    plan, entries, ok = _plan(tool_name, prefix, env, door)
    if not any(why is None for _, _, why in plan):
        return [(path, what, "kept: " + why) for path, what, why in plan]
    held = _held(share, entries, spare)                         # once before the lock
    if held:
        return [(path, what, "kept: held, " + _ascii(held)) for path, what, _ in plan]
    if dry:
        return [(path, what, "would remove" if why is None else "kept: " + why) for path, what, why in plan]
    lock_path = os.path.join(share, ".lock")
    made, lock = ok and not os.path.lexists(lock_path), None
    if ok:
        try:
            lock = _lock(share, make=False)
        except OSError as e:
            return [(path, what, "kept: the lock, " + _ascii(e.strerror or e)) for path, what, _ in plan]
    state = {"ok": ok, "dropped": not made}
    bin_real = os.path.realpath(os.path.join(prefix, "bin"))

    def allowed(path):
        root = _share_real(prefix, tool_name) if state["ok"] else None
        return (os.path.dirname(path) == bin_real or (root is not None and _under(path, root))
                or path == state.get("mark"))

    def drop():
        """The `.lock` this call made, unlinked where the path still names the file held."""
        if state["dropped"]:
            return
        state["dropped"] = True
        try:
            on_disk, held_file = os.lstat(lock_path), os.fstat(lock.fileno())
            if state["ok"] and (on_disk.st_dev, on_disk.st_ino) == (held_file.st_dev, held_file.st_ino):
                _bounded(lock_path, allowed)
                os.unlink(lock_path)
        except OSError:
            pass
    try:
        if lock is not None:
            plan, entries, state["ok"] = _plan(tool_name, prefix, env, door)    # again, under the lock
            if made:
                plan = [row for row in plan if row[0] != lock_path]             # never a row: not there before
            held = _held(share, entries, spare)
            if held:
                return [(path, what, "kept: held, " + _ascii(held)) for path, what, _ in plan]
        marks = [m for m, what, _ in plan if what == "marker"]
        if marks:
            state["mark"] = os.path.join(os.path.realpath(os.path.dirname(marks[0])), os.path.basename(marks[0]))
        rows = []
        for path, what, why in plan:
            if why is not None:
                rows.append((path, what, "kept: " + why))
                continue
            done = [0]
            try:
                if what == "tree":
                    _take(path, allowed, done)
                elif what == "share" and path == share:
                    drop()
                    _bounded(path, allowed)
                    os.rmdir(path)
                else:
                    _bounded(path, allowed)
                    os.unlink(path)
                rows.append((path, what, "removed"))
            except OSError as e:
                why = _ascii(e.strerror or e)
                rows.append((path, what, ("kept: partly removed, " if done[0] else "kept: ") + why))
        return rows
    finally:
        if lock is not None:
            drop()
            lock.close()


# ---- the forward refresh (design/04 §3, §5) ------------------------------------------------

def launcher_path(env, conf=None):
    conf = conf or names()
    return os.path.join(env.get("HOME") or "", ".local", "bin", conf["tool_name"])


_LINE = re.compile(r"^(VERSION|TREE|CODE|PYTHON)=(.*)$", re.M)


def read_launcher(path):
    """{"version", "tree", "python"} as the launcher's lines say, each None when absent; the
    new form's TREE or an older form's CODE; None when no launcher is there to read, a path that
    is no regular file included. Never raises."""
    data = read_regular(path, 65536)
    if data is None:
        return None
    text = data.decode("utf-8", "surrogateescape")
    lines = {}
    for name, value in _LINE.findall(text):
        lines.setdefault(name, value.strip())
    tree = lines.get("TREE") or lines.get("CODE")
    if tree:
        import shlex
        try:
            tree = "".join(shlex.split(tree))
        except ValueError:
            pass
    python = lines.get("PYTHON")
    return {"version": lines.get("VERSION"), "tree": tree, "python": python.strip('"') if python else None}


_VER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def order(ver):
    """What sorts a version: a release above its prereleases, numeric identifiers below
    alphanumeric. None for a version it cannot read: three parts, an optional prerelease."""
    m = _VER.match(str(ver).strip()) if ver else None
    if not m:
        return None
    nums = tuple(int(g) for g in m.groups()[:3])
    pre = tuple(int(p) if p.isdigit() else p for p in m.group(4).split(".")) if m.group(4) else ()
    return nums, (1,) if not pre else (0,) + tuple(
        (0, p, "") if isinstance(p, int) else (1, 0, p) for p in pre)


def _behind(path):
    """The launcher at `path` is older than this plugin. Absent, a link, no line, no reading or
    equal: left alone."""
    if os.path.islink(path):
        return False
    found = read_launcher(path)
    theirs = found and found["version"]
    ours = version()
    if not theirs or theirs == ours:
        return False
    theirs, ours = order(theirs), order(ours)
    return theirs is not None and ours is not None and ours > theirs


def _refresh(env, conf):
    home, root = env.get("HOME"), env.get("CLAUDE_PLUGIN_ROOT")
    if not home or not root:
        return None
    prefix = os.path.join(home, ".local")
    path = launcher_path(env, conf)
    if not _behind(path):
        return None
    # Only the plugin Claude Code named refreshes: never a frozen tree (a launcher run by hand),
    # never a checkout's suite or a stray root.
    lib = _lib()
    if is_frozen(lib) or os.path.realpath(os.path.join(root, "lib")) != lib:
        return None
    share = os.path.join(prefix, "share", conf["tool_name"])
    lock = _lock(share, wait=False)
    if lock is None:                    # another process is at it; a later one sees what it left
        return None
    try:
        if _behind(path):
            _locked_install(prefix, share, env, conf, ps_timeout=REFRESH_PS_TIMEOUT)
    finally:
        lock.close()
    return None


def refresh(env=None):
    """On SessionStart, this plugin newer than the launcher that exists: the install, and None.
    It creates no launcher, refuses backward and equal, reads its names and one launcher on the
    common path, and never raises: a failure is the one line for the hook's systemMessage."""
    env = os.environ if env is None else env
    conf = None
    try:
        conf = names()
        return _refresh(env, conf)
    except Exception as e:                                     # noqa: BLE001
        who, remedy = (conf["tool_name"], conf["remedy"]) if conf else (CONF, "install-cli")
        return "%s: the launcher did not move to %s: %s; run %s" % (who, version(), str(e)[:200], remedy)
