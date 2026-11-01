"""install-cli (design/04 §2, §3, §5; packet sc3): the launcher on PATH, with no checkout or venv.

It freezes the code this module runs from, whichever plugin or frozen tree that is, under
<prefix>/share/agentik-session/<content hash>/, writes <prefix>/bin/agentik-session, its link and
the `agentik` door, each by a temp file and a rename, and prunes. Stdlib, 3.9, and light at import:
every hook imports it for `restore_parent_env`.
"""
import os
import re

from . import SEMVER

SHARE = "agentik-session"
NAME = "agentik-session"
MANIFEST = "plugin.json"
DOOR = "agentik"
# What Apple's /usr/bin/python3 adds to the environment (design/04 §3), and the prefix under which
# the launcher records what its parent really had.
APPLE = ("SDKROOT", "CPATH", "LIBRARY_PATH", "MANPATH", "LC_CTYPE")
SAVED = "AGENTIK_PARENT_"
# SessionStart's own timeout is 10 s (hooks.json): a slow ps costs the prune, never the hook.
REFRESH_PS_TIMEOUT = 3
SKIP_DIRS = ("__pycache__",)
SKIP_FILES = (".DS_Store",)
# The launcher's old name: the package's, spelled with a hyphen.
OLD_NAME = __package__.replace("_", "-")

LAUNCHER = r'''#!/bin/sh
# agentik-session launcher, written by `agentik-session install-cli` (design/04 §2, §3); its old
# name, __OLD_NAME__, is a link to it until r2 (agentik-r1 §4.3).
#
# Runs one frozen tree of the plugin's lib/ under /usr/bin/python3. `-I` keeps the cwd,
# PYTHONPATH and the user site off sys.path, so neither the directory a hook fires in nor a
# checkout can change what runs. Run /session:install-cli to pick up a new plugin, or when the
# interpreter or TREE has gone away: until then a `hook` exits 0, so no event fails; `hook
# SessionStart` says so every session as a JSON `systemMessage` on stdout (a hook's stderr is
# unseen on exit 0: ADV11-5), other events once (a marker under the state dir naming the missing
# path, removed by install-cli); other verbs exit 3 (design/04 §2). The marker's folder is
# agentik-r1 §6.3's c1 pick: the new state folder when it exists, else the old one when it
# exists, else new. Nothing below forks on the way to the exec.
VERSION=__VERSION__
TREE=__TREE__
# Under the old name, on a terminal, for a verb other than `hook`: one note (§4.3).
if [ "${0##*/}" = __OLD_NAME__ ] && [ -t 2 ] && [ "$1" != hook ]; then
    echo "__OLD_NAME__: renamed; use 'agentik session …' (ends 2026-12-31)" >&2
fi
refuse() {   # the path that is gone, then this launcher's own arguments
    gone=$1; shift
    if [ "$1" != hook ]; then
        echo "agentik-session: $gone is gone; run /session:install-cli" >&2
        exit 3
    fi
    state="${XDG_STATE_HOME:-$HOME/.local/state}"
    dir="$state/agentik-session"
    [ -e "$dir" ] || [ ! -e "$state/__OLD_APP__" ] || dir="$state/__OLD_APP__"
    marker="$dir/install-needed"
    if [ "$2" = SessionStart ]; then
        esc= rest=$gone
        while [ -n "$rest" ]; do
            c=${rest%"${rest#?}"}; rest=${rest#?}
            case $c in \\|\") esc=$esc\\$c ;; [[:cntrl:]]) ;; *) esc=$esc$c ;; esac
        done
        printf '{"systemMessage": "agentik-session: %s is gone; run /session:install-cli"}\n' "$esc"
    else
        seen=; [ ! -r "$marker" ] || read -r seen < "$marker"
        [ "$seen" = "$gone" ] || echo "agentik-session: $gone is gone; run /session:install-cli" >&2
    fi
    /bin/mkdir -p "${marker%/*}" 2>/dev/null && { printf '%s\n' "$gone" > "$marker"; } 2>/dev/null
    exit 0
}
wanted=${AGENTIK_PYTHON:-/usr/bin/python3}; py=$wanted
[ -f "$py" ] && [ -x "$py" ] || py=$(command -v python3) || refuse "$wanted" "$@"
[ -f "$TREE/agentik-session" ] && [ -r "$TREE/agentik-session" ] || refuse "$TREE" "$@"
cache=${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache
# /usr/bin/python3 adds SDKROOT and LC_CTYPE where unset, and adds to CPATH, LIBRARY_PATH and
# MANPATH even where set (measured, sc3). What a chain's `claude` or a gate job may see is what
# this shell saw: record it here, and the package restores it first thing (restore_parent_env).
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
    "$py" -I -X pycache_prefix="$cache" "$TREE/agentik-session" "$@"; rc=$?
    if [ "$rc" != 0 ] && { [ "$1" != hook ] || [ "$rc" = 2 ] || [ "$rc" = 126 ] || [ "$rc" = 127 ]; }; then
        [ "$("$py" -I -c 'print("python")' 2>/dev/null </dev/null)" = python ] || refuse "$py" "$@"
    fi
    exit "$rc"
fi
exec "$py" -I -X pycache_prefix="$cache" "$TREE/agentik-session" "$@"
'''


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


def _source():
    """(lib, manifest, door) of the code this module runs from: the plugin's lib/ with its
    manifest and door elsewhere in the plugin, or a frozen tree holding all three."""
    lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if is_frozen(lib):
        return lib, os.path.join(lib, MANIFEST), os.path.join(lib, DOOR)
    plugin = os.path.dirname(lib)
    return (lib, os.path.join(plugin, ".claude-plugin", MANIFEST), os.path.join(plugin, "bin", DOOR))


def is_frozen(lib):
    return os.path.isfile(os.path.join(lib, MANIFEST))


def _walk(root):
    """{path under root: path}, every file but bytecode."""
    found = {}
    for here, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
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


def _freeze(share, lib, manifest, door):
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
            os.chmod(to, 0o755 if rel in (DOOR, NAME) else 0o644)
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


def launcher_text(tree, version):
    """The launcher for one frozen tree."""
    import shlex
    from . import config
    return (LAUNCHER.replace("__OLD_NAME__", OLD_NAME).replace("__OLD_APP__", config.OLD_APP)
            .replace("__APPLE__", " ".join(APPLE))
            .replace("__VERSION__", shlex.quote(version)).replace("__TREE__", shlex.quote(str(tree))))


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


def _clear_marker(env):
    state = env.get("XDG_STATE_HOME") or os.path.join(env.get("HOME", ""), ".local", "state")
    from . import config
    folder = os.path.join(state, SHARE)
    if not os.path.exists(folder) and os.path.exists(os.path.join(state, config.OLD_APP)):
        folder = os.path.join(state, config.OLD_APP)
    try:
        os.unlink(os.path.join(folder, "install-needed"))
    except OSError:
        pass


def _sweep(share):
    """Under the lock every staging folder is a crash's."""
    import shutil
    for name in os.listdir(share):
        if name.startswith(".tmp-"):
            shutil.rmtree(os.path.join(share, name), ignore_errors=True)


def _lock(share, wait=True):
    """The install's one lock, an open file held for the process's turn; None when another
    holds it and `wait` is off."""
    import fcntl
    os.makedirs(share, exist_ok=True)
    fh = open(os.path.join(share, ".lock"), "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
    except BlockingIOError:
        fh.close()
        return None
    return fh


def _locked_install(prefix, share, env, ps_timeout=60):
    from . import prune
    bin_dir = os.path.join(prefix, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    _sweep(share)
    lib, manifest, door = _source()
    version = SEMVER
    tree = _freeze(share, lib, manifest, door)
    code = os.path.join(share, tree)
    launcher = os.path.join(bin_dir, NAME)
    _write_door(os.path.join(bin_dir, DOOR), door)
    _replace(os.path.join(bin_dir, OLD_NAME), lambda temp: os.symlink(NAME, temp))
    _write_launcher(launcher, launcher_text(code, version))    # last: what a retry reads
    try:
        pruned, lines = prune.prune(share, tree, ps_timeout=ps_timeout)
    except Exception as e:                                     # noqa: BLE001
        pruned, lines = 1, ["prune-trees: %s" % e]
    if pruned:
        lines.append("the prune failed; every old tree kept")
    _clear_marker(env)
    return {"launcher": launcher, "tree": code, "version": version, "door": os.path.join(bin_dir, DOOR),
            "link": os.path.join(bin_dir, OLD_NAME), "pruned": lines}


def install(prefix=None, env=None) -> dict:
    """The verb's work; what it wrote, or an OSError."""
    env = os.environ if env is None else env
    prefix = os.path.abspath(prefix or os.path.join(env["HOME"], ".local"))
    share = os.path.join(prefix, "share", SHARE)
    lock = _lock(share)
    try:
        return _locked_install(prefix, share, env)
    finally:
        lock.close()


# ---- the forward refresh (design/04 §3, §5; packet sc3 ruling 5) ---------------------------

def launcher_path(env):
    return os.path.join(env.get("HOME") or "", ".local", "bin", NAME)


_LINE = re.compile(r"^(VERSION|TREE|CODE|PYTHON)=(.*)$", re.M)


def read_launcher(path):
    """{"version", "tree", "python"} as the launcher's lines say, each None when absent; the
    new form's TREE or the old one's CODE; None when no launcher is there to read. Never raises."""
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read(65536)
    except OSError:
        return None
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


def order(version):
    """What sorts it, by the package's own reading of a version; None for a version it cannot
    read: three parts, an optional prerelease."""
    from .doctor import _key, parse_version
    parsed = parse_version(version) if version else None
    if parsed is None or parsed[2] != 3:
        return None
    return _key(parsed[0], parsed[1])


def _behind(path):
    """The launcher at `path` is older than this plugin. Absent, a link, no line, no reading or
    equal: left alone; the doctor names what wants naming."""
    if os.path.islink(path):
        return False
    found = read_launcher(path)
    version = found and found["version"]
    if not version or version == SEMVER:
        return False
    theirs, ours = order(version), order(SEMVER)
    return theirs is not None and ours is not None and ours > theirs


def _refresh(env):
    home, root = env.get("HOME"), env.get("CLAUDE_PLUGIN_ROOT")
    if not home or not root:
        return None
    prefix = os.path.join(home, ".local")
    path = launcher_path(env)
    if not _behind(path):
        return None
    # Only the plugin Claude Code named refreshes: never a frozen tree (the switch, or a launcher
    # run by hand), never a checkout's suite or a stray root.
    lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if is_frozen(lib) or os.path.realpath(os.path.join(root, "lib")) != lib:
        return None
    share = os.path.join(prefix, "share", SHARE)
    lock = _lock(share, wait=False)
    if lock is None:                    # another session is at it; a later one sees what it left
        return None
    try:
        if _behind(path):
            _locked_install(prefix, share, env, ps_timeout=REFRESH_PS_TIMEOUT)
    finally:
        lock.close()
    return None


def refresh(env=None):
    """On SessionStart, this plugin newer than the launcher that exists: the install, and None.
    It creates no launcher, refuses backward and equal, reads one file on the common path, and
    never raises: a failure is the one line for the hook's systemMessage."""
    env = os.environ if env is None else env
    try:
        return _refresh(env)
    except Exception as e:                                     # noqa: BLE001
        return ("agentik-session: the launcher did not move to %s: %s; run /session:install-cli"
                % (SEMVER, str(e)[:200]))
