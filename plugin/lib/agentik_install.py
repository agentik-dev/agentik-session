"""agentik_install: install-cli, the launcher on PATH with no checkout or venv (hq design/04 §2, §3, §5).

Canonical in agentik-commons; scripts/sync places it at a plugin's lib/agentik_install.py,
byte-identical in every tool, under vendored.sha256. What differs by tool is read from
lib/agentik-tool.conf beside it, the one per-tool place; see names(). It freezes the code this
module runs from, whichever plugin or frozen tree that is, under
<prefix>/share/<tool>/<content hash>/, writes <prefix>/bin/<tool>, its old name's link when the
tool has one and the `agentik` door, each by a temp file and a rename, and prunes. Stdlib, 3.9, and
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


def _door(path, door):
    """The shared `agentik` door moves forward only, as a launcher does: absent or older, it is
    written; equal or newer, it stays byte for byte; a link, or a VERSION line here or there that
    does not read as a version, leaves it alone. None, or the line that says why it stayed."""
    if not os.path.lexists(path):
        _write_door(path, door)
        return None
    if os.path.islink(path):
        return "the door %s is a link; left alone" % path
    theirs = (read_launcher(path) or {}).get("version")
    ours = (read_launcher(door) or {}).get("version")
    a, b = order(theirs), order(ours)
    if a is None or b is None:
        return "the door %s has no version to compare (%s there, %s here); left alone" % (path, theirs, ours)
    if b > a:
        _write_door(path, door)
    return None


def _clear_marker(env, conf):
    state = env.get("XDG_STATE_HOME") or os.path.join(env.get("HOME", ""), ".local", "state")
    folder = os.path.join(state, conf["tool_name"])
    old = conf["old_state"]
    if old and not os.path.exists(folder) and os.path.exists(os.path.join(state, old)):
        folder = os.path.join(state, old)
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
    link = os.path.join(bin_dir, old) if old else None
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
    _clear_marker(env, conf)
    return {"launcher": launcher, "tree": code, "version": ver, "door": os.path.join(bin_dir, DOOR),
            "link": link, "pruned": lines}


def install(prefix=None, env=None):
    """The verb's work; what it wrote, or an OSError, KeyError or ValueError."""
    env = os.environ if env is None else env
    conf = names()
    prefix = os.path.abspath(prefix or os.path.join(env["HOME"], ".local"))
    share = os.path.join(prefix, "share", conf["tool_name"])
    lock = _lock(share)
    try:
        return _locked_install(prefix, share, env, conf)
    finally:
        lock.close()


def install_cli(prefix=None, env=None):
    """The verb `<tool> install-cli [--prefix P]`, for a tool's command line to call: its exit
    code. 0 done; 1 it could not (the reason on stderr), nothing moved past what it had written."""
    import sys
    try:
        done = install(prefix, env)
    except (OSError, KeyError, ValueError) as e:
        print("install-cli: %s" % e, file=sys.stderr)
        return 1
    link = "%s links to it; " % done["link"] if done["link"] else ""
    print("installed %s -> %s (%s); %s%s" % (done["launcher"], done["tree"], done["version"], link, done["door"]))
    for line in done["pruned"]:
        print(line)
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


# ---- the forward refresh (design/04 §3, §5) ------------------------------------------------

def launcher_path(env, conf=None):
    conf = conf or names()
    return os.path.join(env.get("HOME") or "", ".local", "bin", conf["tool_name"])


_LINE = re.compile(r"^(VERSION|TREE|CODE|PYTHON)=(.*)$", re.M)


def read_launcher(path):
    """{"version", "tree", "python"} as the launcher's lines say, each None when absent; the
    new form's TREE or an older form's CODE; None when no launcher is there to read. Never raises."""
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
