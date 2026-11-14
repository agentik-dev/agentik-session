"""`agentik session doctor`: the checks of overhaul-r1 §2.4, in that order.

Unknown is never a pass: a probe that cannot run, a file that cannot be read,
a version that cannot be parsed, each is a failing check with the reason named.
"""

from __future__ import annotations

import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import (SEMVER, demand, hooks, install, instructionguard, instructions, measure, meter,
               mod, resolver)

PLUGIN_ID = "session@agentik"
# agentik-r1 §6.3 c7: the ID before the switch (§8.3); alone, it is a warn naming the switch.
OLD_PLUGIN_ID = "session@claude-code-session"
# --max-turns is accepted but unlisted in `claude --help`; a probe costs a turn, so none.
# Both --max-turns and --max-budget-usd work in print mode only and default to no limit;
# the budget is a client-side estimate checked after each response, so spend can pass
# it by one response plus any running subagents (Claude Code's "CLI reference" and the
# Agent SDK's "How the agent loop works", as of 2026-10-14).
# --session-id: `agentik session run` starts every sitting with it (respawn-r1 §3.1).
CLAUDE_FLAGS = ("--model", "--effort", "--tools", "--permission-mode",
                "--max-budget-usd", "--output-format", "--session-id")
FRESH_S = 120
# ss5 R3: the most of a transcript's unmetered tail the meter check reads, from its end back.
TAIL_MAX = 4 * 1024 * 1024
HOOK_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure",
               "PostToolBatch", "UserPromptSubmit", "Stop", "StopFailure", "SessionEnd",
               "PreCompact", "PostModelSwitch",               # wfg R7: PostModelSwitch
               "InstructionsLoaded",                          # g1 R1: the instruction log
               "SubagentStop")                                # h4 R1: a helper's end
# The newest release of each supported minor, for when pyenv is absent (offline-safe).
KNOWN_PYTHONS_OF = "2026-09-22"
KNOWN_PYTHONS = ("3.11.16", "3.12.14", "3.13.15", "3.14.7")
_PYENV_LINE = re.compile(r"^\s*3\.\d+\.\d+$")
# The sibling plugins (mod-r1 §9, decided 2026-10-11): each is optional, so absent is a
# note naming what it adds, and any installed version is fine (no range to outgrow).
# `old` is the ID before the switch (agentik-r1 §6.3 c7): alone, a warn naming the switch.
# `row` names the check when the plugin's name is taken (`relay` is the binaries' row).
SIBLINGS = [
    {"name": "decisions", "marketplace": "agentik", "old": "decisions@claude-code-decisions",
     "adds": "the decisions ledger, which reads its section of the resolved configuration"},
    {"name": "respeak", "marketplace": "agentik", "old": "respeak@claude-code-respeak",
     "adds": "the plain-English renderer the built-in profiles load"},
    {"name": "relay", "marketplace": "agentik", "old": "agent-relay@agent-relay",
     "adds": "the relay, and the hook that guards `push: never`", "row": "relay-plugin"},
]
# fk3 R1: which plugin stands for a sibling is the suite's answer, read once a run from the
# launcher's fixed place (never PATH) under a wall (5 s: the suite's own reads end in 2 s).
# A launcher that hangs, floods or lies costs one wall and reads as no answer (R2).
SOURCES_WALL = 5.0
SOURCES_CAP = 1 << 20
SOURCES_SCHEMA = "agentik.sources/1"
SOURCE_KINDS = ("own", "plugin", "folder", "undecided", "absent")
# fk3 R2: with no answer, the installs Claude Code records at these scopes are the candidates.
SOURCE_SCOPES = ("user", "managed")


def _pick_id(plugins, new: str, old: str):
    """(id, entry, is_old): the new ID when it is enabled, else the old when enabled, else
    whichever is installed (new first); (new, None, False) when neither is (c7)."""
    for pid in (new, old):
        p = plugins.get(pid)
        if p and p.get("enabled"):
            return pid, p, pid == old
    for pid in (new, old):
        if plugins.get(pid):
            return pid, plugins[pid], pid == old
    return new, None, False


def _twice(plugins, pid: str, old: str) -> bool:
    """The new ID picked while the old is enabled too: each hook fires twice (fix round F2)."""
    o = plugins.get(old)
    return pid != old and bool(o and o.get("enabled"))


def _twice_note(old: str, new: str) -> str:
    return f"{new} and {old} are both enabled, so each hook fires twice: disable {old} " \
           "(agentik-r1 §8.3 step 3)"


def _switch_note(old: str, new: str) -> str:
    return f"{old} is the ID before the switch: install {new}, then disable {old} " \
           "(agentik-r1 §8.3)"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    note: bool = False          # an optional piece is absent: ok, printed as a note
    warn: bool = False          # worth a look, never a failure: ok, printed as warn
    remedy: str | None = None   # packet ak5 R8: the one command the detail names, or None
    # fk3 R4: a sibling that is not `<name>@agentik`: {kind, plugin, root, version, declared}
    # (and `seen` when undecided); the id, folder and version leave the detail for it.
    source: dict | None = None

    @property
    def status(self) -> str:
        return "fail" if not self.ok else "note" if self.note else "warn" if self.warn else "ok"


@dataclass
class Report:
    checks: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def as_dict(self) -> dict:
        """The plug's doctor read (packet ak5 R8): `ok` says the read ran; `failed` and `warned`
        count the statuses, so "no check failed" is `failed` 0. The exit stays `ok`'s."""
        from .plug import withheld     # plug imports this module; a secret's text stays out
        st = [c.status for c in self.checks]
        return {"schema": "agentik.doctor/1", "ok": True, "tool": "session",
                "failed": st.count("fail"), "warned": st.count("warn"),
                "checks": [{"name": c.name, "ok": c.ok, "status": c.status,
                            "detail": withheld(c.detail), "remedy": c.remedy,
                            "source": c.source}
                           for c in self.checks]}


# --- the npm-style range matcher -------------------------------------------------

_VER = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def parse_version(text: str):
    """(major, minor, patch, prerelease tuple, parts given); None if not a version."""
    m = _VER.match(str(text).strip())
    if not m:
        return None
    given = sum(1 for g in m.groups()[:3] if g is not None)
    nums = tuple(int(g or 0) for g in m.groups()[:3])
    pre = tuple(int(p) if p.isdigit() else p for p in m.group(4).split(".")) if m.group(4) else ()
    return nums, pre, given


def _key(nums, pre):
    # a release sorts above its prereleases; numeric identifiers below alphanumeric
    return nums, (1,) if not pre else (0,) + tuple(
        (0, p, "") if isinstance(p, int) else (1, 0, p) for p in pre)


def _comparators(rng: str) -> list[tuple[str, tuple, tuple]]:
    out = []
    for tok in rng.split():
        m = re.match(r"^(\^|~|>=|<=|>|<|=)?(.+)$", tok)
        op, v = m.group(1) or "=", parse_version(m.group(2))
        if v is None:
            raise ValueError(f"not a version: {m.group(2)!r}")
        (maj, mnr, pat), pre, given = v
        if op == "^":
            if maj > 0 or given == 1:
                hi = (maj + 1, 0, 0)
            elif mnr > 0 or given == 2:
                hi = (0, mnr + 1, 0)
            else:
                hi = (0, 0, pat + 1)
            out += [(">=", (maj, mnr, pat), pre), ("<", hi, ())]
        elif op == "~":
            hi = (maj + 1, 0, 0) if given == 1 else (maj, mnr + 1, 0)
            out += [(">=", (maj, mnr, pat), pre), ("<", hi, ())]
        elif op == "=" and given < 3:
            hi = (maj + 1, 0, 0) if given == 1 else (maj, mnr + 1, 0)
            out += [(">=", (maj, mnr, pat), ()), ("<", hi, ())]
        else:
            out.append((op, (maj, mnr, pat), pre))
    if not out:
        raise ValueError("empty range")
    return out


def satisfies(version: str, rng: str) -> bool:
    """npm semantics for `^ ~ >= <= > < =` joined by spaces (AND). Raises ValueError."""
    v = parse_version(version)
    if v is None:
        raise ValueError(f"not a version: {version!r}")
    nums, pre, _ = v
    comps = _comparators(rng)
    if pre and not any(cp and cn == nums for _, cn, cp in comps):
        return False                         # npm: a prerelease matches only its own tuple
    have = _key(nums, pre)
    for op, cn, cp in comps:
        want = _key(cn, cp)
        if not {">=": have >= want, "<=": have <= want, ">": have > want,
                "<": have < want, "=": have == want}[op]:
            return False
    return True


# --- probes -----------------------------------------------------------------------

def _run(argv: list[str], env, timeout: float = 20.0):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           env=dict(env))
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    return r, None


def _which(name: str, env) -> str | None:
    return shutil.which(name, path=env.get("PATH"))


def _check_claude(env) -> Check:
    exe = _which("claude", env)
    if not exe:
        return Check("claude", False, "`claude` not on PATH")
    r, err = _run([exe, "--help"], env)
    if r is None or r.returncode != 0:
        return Check("claude", False, f"`claude --help` failed: {err or r.returncode}")
    # a flag is matched whole: `--session-id-file` is not `--session-id` (S20b review F5)
    missing = [f for f in CLAUDE_FLAGS if not re.search(re.escape(f) + r"(?![\w-])", r.stdout)]
    if missing:
        return Check("claude", False, "`claude --help` lacks " + ", ".join(missing))
    return Check("claude", True, f"{exe}; every profile flag listed (--max-turns is "
                 "accepted but unlisted, not probed: a probe costs a turn)")


def _vtuple(text: str) -> tuple:
    return tuple(int(p) for p in text.strip().split("."))


def newest_known(env) -> tuple[str, str]:
    """(version, source): the newest CPython release pyenv knows locally, else the shipped list."""
    exe = _which("pyenv", env)
    if exe:
        r, _ = _run([exe, "install", "--list"], env)
        if r is not None and r.returncode == 0:
            found = [l.strip() for l in r.stdout.splitlines() if _PYENV_LINE.match(l)]
            if found:
                return max(found, key=_vtuple), "pyenv's list"
    return max(KNOWN_PYTHONS, key=_vtuple), f"the shipped list of {KNOWN_PYTHONS_OF}"


def _check_python(env, version=sys.version_info, exe=sys.executable) -> Check:
    """The interpreter doctor runs under: the one the launcher and the hooks resolve."""
    ver = "%d.%d.%d" % tuple(version[:3])
    ok = tuple(version[:2]) >= (3, 9)    # /usr/bin/python3 on a bare Mac (hq entry 6, design/04)
    newest, source = newest_known(env)
    detail = f"{ver} ({exe}); newest known {newest} ({source})"
    runs = _launcher_python(env)
    gone = bool(runs) and not (os.path.isfile(runs) and os.access(runs, os.X_OK))
    if runs:
        detail += f"; the launcher runs {runs}" + (", which is gone" if gone else "")
    return Check("python", ok, detail + ("" if ok else "; needs 3.9+"), warn=ok and gone)


def _launcher_python(env):
    """The interpreter the launcher in ~/.local/bin runs, by its own rule; None with no launcher.
    The old form bakes one; the new form takes AGENTIK_PYTHON, Apple's, then PATH's."""
    found = install.read_launcher(install.launcher_path(env))
    if found is None:
        return None
    if found["python"]:
        return found["python"]
    wanted = env.get("AGENTIK_PYTHON") or "/usr/bin/python3"
    if os.path.isfile(wanted) and os.access(wanted, os.X_OK):
        return wanted
    return _which("python3", env) or wanted


def _check_launcher(env, plugins) -> Check:
    """The launcher in ~/.local/bin (design/04 §5, §6): optional, and only a gone tree fails, since
    every verb on the terminal then exits 3."""
    path = install.launcher_path(env)
    found = install.read_launcher(path)
    remedy = "run /session:install-cli"
    cmd = "/session:install-cli"              # packet ak5 R8: the command the details name
    if found is None:
        return Check("launcher", True, f"none at {path}; /session:install-cli gives the terminal "
                     "the CLI", note=True, remedy=cmd)
    if found["tree"] and not os.path.isdir(found["tree"]):
        return Check("launcher", False, f"{path} runs {found['tree']}, which is gone; {remedy}",
                     remedy=cmd)
    version = found["version"]
    if not version:
        return Check("launcher", True, f"{path} has no VERSION= line, so no session refreshes it; "
                     + remedy, warn=True, remedy=cmd)
    theirs = install.order(version)
    if theirs is None:
        return Check("launcher", True, f"{path} reads VERSION={version}, which is no version, so "
                     f"no session refreshes it; {remedy}", warn=True, remedy=cmd)
    _, p, _ = _pick_id(plugins, PLUGIN_ID, OLD_PLUGIN_ID) if plugins is not None else (None, None, None)
    plugin = (p or {}).get("version") or SEMVER
    ours = install.order(plugin)
    if ours is not None and theirs < ours:
        return Check("launcher", True, f"{path} is {version}, older than the plugin's {plugin}; the "
                     f"next session's start moves it, or {remedy}", warn=True, remedy=cmd)
    return Check("launcher", True, f"{version} at {path}")


def _check_state(env) -> Check:
    d = resolver.state_dir(env)
    try:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(dir=d, prefix=".doctor-"):
            pass
    except OSError as e:
        return Check("state-dir", False, f"{d} not writable: {e}")
    return Check("state-dir", True, str(d))


def _plugin_list(env):
    exe = _which("claude", env)
    if not exe:
        return None, "`claude` not on PATH"
    r, err = _run([exe, "plugin", "list", "--json"], env)
    if r is None or r.returncode != 0:
        return None, f"`claude plugin list --json` failed: {err or r.stderr.strip()[:120]}"
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return None, "`claude plugin list --json` printed no JSON"
    if not isinstance(data, list):
        return None, "`claude plugin list --json` is not a list"
    return {str(p.get("id")): p for p in data if isinstance(p, dict)}, None


def _check_plugin(plugins, err) -> Check:
    if plugins is None:
        return Check("plugin", False, err)
    pid, p, old = _pick_id(plugins, PLUGIN_ID, OLD_PLUGIN_ID)
    if not p:
        return Check("plugin", False, f"{PLUGIN_ID} not installed")
    if not p.get("enabled"):
        return Check("plugin", False, f"{pid} {p.get('version')} installed, disabled")
    try:
        registered = json.loads((Path(p.get("installPath") or "") / "hooks" / "hooks.json")
                                .read_text()).get("hooks") or {}
    except (OSError, ValueError, AttributeError) as e:
        return Check("plugin", False, f"hooks.json unreadable: {e}")
    missing = [e for e in HOOK_EVENTS if e not in registered]
    if missing:
        return Check("plugin", False, "hooks not registered: " + ", ".join(missing)
                     + f"; update the plugin: `claude plugin update {pid}`, then "
                     "restart Claude Code", remedy=f"claude plugin update {pid}")
    if old:
        return Check("plugin", True, f"{pid} {p.get('version')} enabled; "
                     + _switch_note(pid, PLUGIN_ID), warn=True)
    if _twice(plugins, pid, OLD_PLUGIN_ID):
        return Check("plugin", True, f"{pid} {p.get('version')} enabled; "
                     + _twice_note(OLD_PLUGIN_ID, pid), warn=True)
    return Check("plugin", True, f"{PLUGIN_ID} {p.get('version')} enabled; hooks "
                 + ", ".join(HOOK_EVENTS))


def _check_dependency_by_id(dep: dict, plugins, err) -> Check:
    """A sibling is optional: absent or disabled is a note, any version is fine. With no
    plugin list the `plugin` check is already red; this line only names the unknown.
    fk3 R5: kept for a plugin list that holds the sibling's `old` id alone."""
    name, mkt, adds = dep["name"], dep["marketplace"], dep["adds"]
    new = f"{name}@{mkt}"
    name = dep.get("row", name)
    if plugins is None:
        return Check(name, True, f"optional, not checked: {err}", note=True)
    pid, p, old = _pick_id(plugins, new, dep["old"])
    if not p:
        return Check(name, True, f"not installed, optional: {adds} (`{new}`)", note=True)
    if not p.get("enabled"):
        return Check(name, True, f"{pid} {p.get('version')} installed, disabled, optional: "
                     + adds, note=True)
    if old:
        return Check(name, True, f"{pid} {p.get('version')} installed; "
                     + _switch_note(pid, new), warn=True)
    if _twice(plugins, pid, dep["old"]):
        return Check(name, True, f"{pid} {p.get('version')} installed; "
                     + _twice_note(dep["old"], pid), warn=True)
    return Check(name, True, f"{pid} {p.get('version')} installed")


def _clean(v):
    """A string of the suite's answer or Claude Code's record as a line may print it: no
    control or format character (review 1, F1: C1 controls and bidi overrides too, every
    category `Cc` or `Cf`), at most 200 characters; anything else None."""
    if not isinstance(v, str):
        return None
    return "".join(ch for ch in v
                   if unicodedata.category(ch) not in ("Cc", "Cf"))[:200] or None


def _drain(p, wall: float, cap: int):
    """The child's stdout by the wall, or None (killed with its group) when it runs past the
    wall, writes past the cap, or the pipe fails. The read ends when the child exits, with
    what is buffered (review 1, F2): a background child that holds the pipe open costs no
    wall."""
    deadline = time.monotonic() + wall
    buf = bytearray()
    fd = p.stdout.fileno()
    try:
        os.set_blocking(fd, False)
        with selectors.DefaultSelector() as sel:
            sel.register(p.stdout, selectors.EVENT_READ)
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or len(buf) > cap:
                    raise TimeoutError
                exited = p.poll() is not None
                if exited or sel.select(min(left, 0.05)):
                    chunk = _buffered(fd, cap - len(buf) + 1)
                    buf += chunk or b""
                    if exited or chunk == b"":
                        break
        if len(buf) > cap:
            raise TimeoutError
        p.wait(timeout=max(0.01, deadline - time.monotonic()))
    except (TimeoutError, subprocess.TimeoutExpired, OSError, ValueError):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.kill()
        except OSError:
            pass
        p.wait()
        return None
    finally:
        p.stdout.close()
    return bytes(buf)


def _buffered(fd: int, most: int):
    """What the pipe holds now, up to `most` bytes, without waiting: b"" at its end, None when
    it is empty and still open."""
    got = bytearray()
    while len(got) < most:
        try:
            chunk = os.read(fd, min(65536, most - len(got)))
        except BlockingIOError:
            return bytes(got) if got else None
        if not chunk:
            return bytes(got)
        got += chunk
    return bytes(got)


def _suite_sources(env, cwd):
    """fk3 R1: the suite's rows by tool, from `$HOME/.local/bin/agentik-suite describe sources
    --json`; None when there is no launcher or the answer does not count (exit 0, one object,
    `schema` agentik.sources/1, `ok` true, `tools` a list)."""
    home = env.get("HOME")      # review 1, F4: a HOME that is not absolute names no place
    exe = Path(home) / ".local" / "bin" / "agentik-suite" if home and os.path.isabs(home) \
        else None
    if not exe or not exe.is_file() or not os.access(exe, os.X_OK):
        return None
    try:
        p = subprocess.Popen([str(exe), "describe", "sources", "--json"], cwd=str(cwd),
                             env=dict(env), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, ValueError):
        return None
    out = _drain(p, SOURCES_WALL, SOURCES_CAP)
    if out is None or p.returncode != 0:
        return None
    try:
        data = json.loads(out)
    except (ValueError, RecursionError):
        return None
    if not (isinstance(data, dict) and data.get("schema") == SOURCES_SCHEMA
            and data.get("ok") is True and isinstance(data.get("tools"), list)):
        return None
    rows = {}
    for row in data["tools"]:
        if isinstance(row, dict) and isinstance(row.get("tool"), str):
            rows.setdefault(row["tool"], row)
    return rows


def _answered(row, name: str):
    """fk3 R1: one row of the suite's answer as the check reads it, or None when it says
    nothing this check can use (R2 then): an unknown kind, an id kind with no id, a folder
    with no folder. `own` is the id `<name>@agentik`, whatever kind the row gives it. `id` is
    the id as read, the plugin list's key (review 1, F3); `plugin` the copy a line prints."""
    if not isinstance(row, dict) or row.get("kind") not in SOURCE_KINDS:
        return None
    kind, plugin, root = row["kind"], _clean(row.get("plugin")), _clean(row.get("root"))
    pid = row.get("plugin") if isinstance(row.get("plugin"), str) else None
    if kind in ("own", "plugin"):
        if not plugin:
            return None
        kind = "own" if pid == f"{name}@agentik" else "plugin"
    if kind == "folder" and not root:
        return None
    d = row.get("declared")
    declared = None
    if isinstance(d, dict) and _clean(d.get("path")):
        line = d.get("line")
        declared = {"path": _clean(d["path"]),
                    "line": line if isinstance(line, int) and not isinstance(line, bool) else None}
    seen = [{k: _clean(s.get(k)) for k in ("plugin", "version", "scope", "root")}
            for s in (row.get("seen") if isinstance(row.get("seen"), list) else ())
            if isinstance(s, dict)]
    return {"kind": kind, "plugin": plugin if kind != "folder" else None, "root": root,
            "id": pid if kind != "folder" else None,
            "version": _clean(row.get("version")), "found": row.get("found") is True,
            "declared": declared, "seen": seen, "road": "suite"}


def _installed(env) -> dict:
    """Claude Code's record of the installs, `plugins/installed_plugins.json` under
    `CLAUDE_CONFIG_DIR`, else `~/.claude`; {} when absent or unreadable."""
    user = Path(env.get("CLAUDE_CONFIG_DIR") or Path(env.get("HOME") or Path.home()) / ".claude")
    got = hooks._load_json(user / "plugins" / "installed_plugins.json").get("plugins")
    return got if isinstance(got, dict) else {}


def _recorded(installed: dict, name: str):
    """fk3 R2, as amended by review 1 (F5, F6): the installs whose plugin is named `name`, over
    every id, at scope `user` or `managed`. Distinct ids are counted: one id stands (at `user`
    and `managed` both too; no version when its entries differ in it); two or more are
    undecided (the file names no choice). None when the file gives no entry: the pin's read
    of the plugin list for the own id then stands."""
    ids = {}
    for pid, recs in installed.items():
        if not isinstance(pid, str) or pid.partition("@")[0] != name:
            continue
        for rec in (recs if isinstance(recs, list) else ()):
            if isinstance(rec, dict) and rec.get("scope") in SOURCE_SCOPES:
                ids.setdefault(pid, []).append(rec)
    if not ids:
        return None
    base = {"plugin": None, "root": None, "version": None, "found": False, "declared": None,
            "seen": [], "road": "file"}
    if len(ids) > 1:
        return dict(base, kind="undecided", seen=[
            {"plugin": _clean(pid), "version": _clean(recs[0].get("version")),
             "scope": _clean(recs[0].get("scope")), "root": _clean(recs[0].get("installPath"))}
            for pid, recs in ids.items()])
    pid, recs = next(iter(ids.items()))
    versions = {_clean(r.get("version")) for r in recs}
    return dict(base, kind="own" if pid == f"{name}@agentik" else "plugin",
                plugin=_clean(pid), id=pid, root=_clean(recs[0].get("installPath")),
                version=versions.pop() if len(versions) == 1 else None, found=True)


def _source_key(src: dict) -> dict:
    """fk3 R4: the check's `source`; `seen` only for an undecided sibling."""
    out = {k: src[k] for k in ("kind", "plugin", "root", "version", "declared")}
    if src["kind"] == "undecided":
        out["seen"] = src["seen"]
    return out


def _check_dependency(dep: dict, plugins, err, src: dict | None = None) -> Check:
    """fk3 R3: a sibling's line from the plugin that stands (`src`: the suite's answer, else
    Claude Code's record). Optional all through: absent or disabled is a note, any version is
    fine. `enabled` comes from the plugin list by the standing id. A plugin list that holds
    the `old` id is read as before the suite's answer (R5), and so is a sibling neither the
    suite nor the file gives (`src` None; review 1, F6)."""
    if src is None or (plugins is not None and dep["old"] in plugins):
        return _check_dependency_by_id(dep, plugins, err)
    name, adds = dep["name"], dep["adds"]
    own = f"{name}@{dep['marketplace']}"
    row = dep.get("row", name)
    kind = src["kind"]
    if kind == "absent":
        return Check(row, True, f"not installed, optional: {adds} (`{own}`)", note=True)
    cmd = f"agentik config suite.sources.{name}"
    if kind == "undecided":
        n = len(src["seen"])
        if src["road"] == "file":
            return Check(row, True, f"{n} plugins named {name} installed, optional, not "
                         "checked: say which with the suite's sources", note=True,
                         source=_source_key(src))
        return Check(row, True, f"{n} plugins named {name} installed and none chosen: say "
                     f"which, `{cmd}`", warn=True, remedy=cmd, source=_source_key(src))
    is_own = kind == "own"
    source = None if is_own else _source_key(src)
    if not src["found"]:
        d = src["declared"]
        where = (f"{d['path']}:{d['line']}" if d["line"] is not None else d["path"]) if d \
            else "the suite's sources"
        what = ("a folder that is gone" if kind == "folder" else
                f"{own}, which is not installed" if is_own else "a plugin that is not installed")
        return Check(row, True, f"{where} names {what}: `{cmd}`", warn=True, remedy=cmd,
                     source=source)
    if kind == "folder":
        return Check(row, True, "installed", source=source)
    if plugins is None:
        return Check(row, True, f"optional, not checked: {err}", note=True, source=source)
    pid = src["id"]             # review 1, F3: the id as read, never the printed copy
    p = plugins.get(pid)
    if not p:
        return Check(row, True, f"not installed, optional: {adds} (`{own}`)", note=True,
                     source=source)
    if not p.get("enabled"):
        lead = f"{pid} {p.get('version')} " if is_own else ""
        return Check(row, True, f"{lead}installed, disabled, optional: {adds}", note=True,
                     source=source)
    if is_own:
        return Check(row, True, f"{pid} {p.get('version')} installed")
    return Check(row, True, "installed", source=source)


def _sibling_absent(plugins, name: str) -> bool:
    """True only when the plugin list was read and holds no enabled `name`."""
    if plugins is None:
        return False
    dep = next(d for d in SIBLINGS if d["name"] == name)
    _, p, _ = _pick_id(plugins, f"{name}@{dep['marketplace']}", dep["old"])
    return not (p and p.get("enabled"))


def _relay_absent(plugins, src):
    """Review 1, F7: the relay plugin's standing for `relay` and `git`: True absent, False
    present, None unknown. A read plugin list decides as at the pin; else the row's other
    road (the suite's answer, the installs file): `absent` is absent, a plugin or folder
    found is present, anything else (no entry, undecided, a line naming none) unknown."""
    if plugins is not None:
        return _sibling_absent(plugins, "relay")
    if src is None:
        return None
    if src["kind"] == "absent":
        return True
    return False if src["found"] and src["kind"] in ("own", "plugin", "folder") else None


# Build 3, L2: a layer file that cannot be opened, or nests past the parser, is a failed
# check naming the file and why, as the config read names it; never a traceback.
_UNREAD = (resolver.ResolveError, OSError, RecursionError)


def _why(e, env, cwd) -> str:
    from .plug import _failure, layer_files, scrubbed   # plug imports this module
    if isinstance(e, resolver.ResolveError):
        return scrubbed(str(e))    # review 2, R2-F1: no layer file's text
    return _failure(e, layer_files(cwd, env))   # R2-F2: the paths picked without raising


def _check_profiles(env, cwd) -> Check:
    try:
        _, profiles = resolver.load_profiles(env)
        for name in profiles:
            resolver.resolve(cwd, "doctor", env, profile=name, overlay={})
    except _UNREAD as e:
        return Check("profiles", False, _why(e, env, cwd))
    return Check("profiles", True, f"{len(profiles)} resolve: " + ", ".join(profiles))


def _check_resolved(env) -> Check:
    state = resolver.state_dir(env)
    sid = env.get("CLAUDE_CODE_SESSION_ID")
    note = ""
    if not sid:
        sid = resolver.newest_session(state)
        note = " ($CLAUDE_CODE_SESSION_ID unset: the newest session)"
        if not sid:
            return Check("resolved", True, "$CLAUDE_CODE_SESSION_ID unset and no session "
                         "resolved yet", note=True)     # fr1: a bare machine is no failure
    path = resolver.session_dir(state, sid) / "resolved.json"
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return Check("resolved", False, f"{path}: {e.__class__.__name__}{note}")
    prof = (doc.get("provider") or {}).get("profile")
    return Check("resolved", True, f"{path}, profile {prof}{note}")


def _epoch(ts) -> float | None:
    """A transcript line's or the meter's ISO-8601 time as seconds; None if it is none."""
    if not isinstance(ts, str):
        return None
    try:
        d = datetime.fromisoformat(ts[:-1] + "+00:00" if ts.endswith("Z") else ts)
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _missed_call(tp, start: int, end: int, since: float):
    """Row ss5 R1 and R3: read the transcript's bytes from `start` to `end`, the last TAIL_MAX
    of them when longer (the window's first, cut line skipped), and find a main-thread tool
    call that ended with no meter: a `user` line holding a `tool_result` that is no error
    (PostToolUseFailure and a helper's PostToolUse never write the meter), stamped more than
    FRESH_S after `since`, the meter's ts. Returns ("missed", stamp, seconds) for the first,
    ("none",) when there is none, ("unread", why) when the tail cannot be judged."""
    try:
        with open(tp, "rb") as f:
            back = end - start > TAIL_MAX
            f.seek(end - TAIL_MAX if back else start)
            data = f.read(min(end - start, TAIL_MAX))
    except OSError as e:
        return ("unread", e.__class__.__name__)
    if back:
        data = data[data.find(b"\n") + 1:] if b"\n" in data else b""
    if not data.endswith(b"\n"):
        return ("unread", "a line cut short")
    for raw in data.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except (ValueError, RecursionError):
            return ("unread", "a line that is not JSON")
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
            return ("unread", "a line with no type")
        msg = obj.get("message")
        items = msg.get("content") if isinstance(msg, dict) else None
        if obj["type"] != "user" or obj.get("isSidechain") or not isinstance(items, list) \
                or not any(isinstance(x, dict) and x.get("type") == "tool_result"
                           and not x.get("is_error") for x in items):
            continue
        t = _epoch(obj.get("timestamp"))
        if t is None:
            return ("unread", "a tool result with no time")
        if t - since > FRESH_S:
            return ("missed", obj["timestamp"], t - since)
    return ("none",)


def _check_meter(env) -> Check:
    """meter.json exists and matches its transcript's size, or its ts is within
    FRESH_S of the transcript's mtime, or no tool call ended in the transcript's
    unmetered tail more than FRESH_S after its ts (row ss5)."""
    state = resolver.state_dir(env)
    own = bool(env.get("CLAUDE_CODE_SESSION_ID"))
    sid = env.get("CLAUDE_CODE_SESSION_ID") or resolver.newest_session(state)
    if not sid:
        return Check("meter", True, "no session to meter ($CLAUDE_CODE_SESSION_ID unset, "
                     "none resolved)", note=True)       # fr1: a bare machine is no failure
    path = resolver.session_dir(state, sid) / meter.METER
    m = meter.load(path.parent)
    if m is None:
        return Check("meter", False, f"{path} absent: no PostToolUse has metered this "
                     "session (the plugin's hook)")
    tr = m.get("transcript") or {}
    tp = tr.get("path")
    summary = f"{m.get('pct_context')}% context, {m.get('pct_turns')}% turns, zone {m.get('zone')}"
    zero = m.get("turns") == 0              # SessionStart's meter, before any tool call (ss1)
    try:
        info = os.stat(tp)
        size = info.st_size
    except (OSError, TypeError) as e:
        if zero and (tp is None or isinstance(e, FileNotFoundError)):
            return Check("meter", True, f"{path}: {summary}; no transcript yet")
        return Check("meter", False, f"{path}: transcript {tp} unreadable: "
                     f"{e.__class__.__name__}")
    if tr.get("size") == size:
        return Check("meter", True, f"{path}: {summary}; transcript size matches")
    if zero:                                # no tool call has metered the transcript yet
        return Check("meter", True, f"{path}: {summary}; no tool call metered yet")
    age = meter.mtime_age(m)
    if age is not None and age <= FRESH_S:
        return Check("meter", True, f"{path}: {summary}; {age:.0f}s from the transcript")
    stale = f"{path} stale: metered {tr.get('size')} bytes of {size}, "
    today = Check("meter", False, stale + ("ts unreadable" if age is None
                                           else f"{age:.0f}s from the transcript's mtime"))
    since, metered, offset = _epoch(m.get("ts")), tr.get("size"), tr.get("offset")
    if age is None or since is None or not isinstance(metered, int) or metered > size \
            or tr.get("inode") not in (None, info.st_ino):
        return today                        # no tail to read: the file shrank or was replaced
    start = offset if isinstance(offset, int) and 0 <= offset <= metered else metered
    found = _missed_call(tp, start, size, since)
    if found[0] == "missed":
        return Check("meter", False, f"{stale}{found[2]:.0f}s from the tool call that ended "
                     f"at {found[1]}")
    note = "" if own else " ($CLAUDE_CODE_SESSION_ID unset: the newest session)"
    ran = (f"{path}: {summary}; the transcript has run {size - metered} bytes and {age:.0f}s "
           "past the meter")
    if found[0] == "none":
        return Check("meter", True, f"{ran} with no tool call ended since, so the meter runs "
                     f"at the next one{note}")
    if own:                                 # R3: the caller's own session keeps the pin's verdict
        return today
    return Check("meter", True, f"{ran} and its tail could not be read ({found[1]}), so nothing "
                 f"shows a missed tool call{note}", warn=True)


def _check_meter_hook(plugins, err) -> Check:
    """A report, ok either way: is the meter's PostToolUse hook live for claude children?"""
    def hooks_of(p):
        try:
            return json.loads((Path(p.get("installPath") or "") / "hooks" / "hooks.json")
                              .read_text()).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            return {}
    pid, p, _ = _pick_id(plugins or {}, PLUGIN_ID, OLD_PLUGIN_ID)
    if plugins is None:
        why = err
    elif not p:
        why = f"{PLUGIN_ID} not installed"
    elif not p.get("enabled"):
        why = f"{pid} disabled"
    elif "PostToolUse" not in hooks_of(p):
        why = f"{pid} registers no PostToolUse"
    else:
        return Check("meter-hook", True, f"live: {pid} registers PostToolUse")
    return Check("meter-hook", True, f"not live: {why}; "
                 "packet prompts keep the turns line (conventions §5)")


def _check_config(env, cwd) -> tuple[Check, dict]:
    sections: dict = {}
    try:
        path = resolver.repo_dir(cwd) / "config.yaml"   # R2-F2: a folder above may refuse
        r = resolver.resolve(cwd, "doctor", env, overlay={})
        sections = r.sections
    except _UNREAD as e:
        return Check("config", False, _why(e, env, cwd)), sections
    if not path.exists():
        return Check("config", True, f"no {path}; the defaults"), sections
    detail = f"{path} parses, profile {sections['session']['profile']}"
    if r.unknown:
        detail += "; unknown keys, ignored: " + ", ".join(r.unknown)
    return Check("config", True, detail), sections


def _renamed(env, cwd) -> list:
    try:
        return resolver.resolve(cwd, "doctor", env, overlay={}).renamed
    except _UNREAD:
        return []


def _check_renamed(cwd, r_renamed) -> list:
    """agentik-r1 §6.3's warn rows: the repo's old folder (c4), the old section key (c6)."""
    rows = []
    old = Path(cwd) / resolver.OLD_REPO_DIR
    try:
        here = old.is_dir() and not old.is_symlink()
    except OSError:    # R2-F2: the folder above cannot be searched; `config` fails naming it
        here = False
    if here:
        new = Path(cwd) / resolver.REPO_DIR
        where = "read" if resolver.repo_dir(cwd) == old else f"unread, {new} wins"
        rows.append(Check("config-dir", True, f"{old} is the folder before the rename "
                          f"({where}): `git mv` it to {new} (agentik-r1 §6.3 c4)", warn=True))
    for line in r_renamed:
        rows.append(Check("config-key", True, f"{line} (agentik-r1 §6.3 c6)", warn=True))
    return rows


def _check_subagent_model(env, sections, cwd=None) -> Check | None:
    """Packet mt1 R2: a row only when `CLAUDE_CODE_SUBAGENT_MODEL` is set and is not the
    resolved `tiers.build` model here, so a spawn that names no model runs off the table.
    Resolved with the launch profile the hooks use (round 1 F4); none when that fails."""
    have = env.get("CLAUDE_CODE_SUBAGENT_MODEL")
    prof = hooks.launch_profile(env)
    if have and prof:
        try:
            sections = resolver.resolve(cwd or os.getcwd(), "doctor", env, profile=prof,
                                        overlay={}).sections
        except _UNREAD:
            return None
    want = ((((sections.get("session") or {}).get("tiers") or {}).get("build")) or {}).get("model")
    if not have or not want or have == want:
        return None
    return Check("subagents", True, f"CLAUDE_CODE_SUBAGENT_MODEL is {have[:40]}, the resolved "
                 f"tiers.build is {want}: a spawn naming no model runs off the table; start "
                 "the session with `agentik session start <profile>`", warn=True)


def _check_git(env, sections, guarded: bool | None = True) -> Check:
    exe = _which("git", env)
    if not exe:
        return Check("git", False, "`git` not on PATH")
    push = (sections.get("session") or {}).get("push", "never")
    extra = ""
    if push == "never":
        extra = ("; push: never, the relay plugin not checked" if guarded is None   # F7
                 else "; push: never, guarded by the relay plugin (its check above)" if guarded
                 else "; push: never, unguarded without the relay plugin")
    return Check("git", True, exe + extra)


def _check_relay(env, sections, sibling_absent: bool | None = False) -> Check | None:
    enabled = (sections.get("relay") or {}).get("enabled", "auto")
    if enabled not in ("auto", "on", True):
        return None
    if enabled == "auto" and sibling_absent:
        return Check("relay", True, "relay.enabled is auto and the relay plugin not "
                     "installed: no relay expected", note=True)
    missing = [b for b in ("relay", "tmux") if not _which(b, env)]
    if missing and enabled == "auto" and sibling_absent is None:     # review 1, F7
        return Check("relay", True, "relay.enabled is auto and the relay plugin was not "
                     "checked: no relay expected", note=True)
    if missing:
        return Check("relay", False, "relay.enabled is "
                     f"{enabled}; not on PATH: " + ", ".join(missing))
    return Check("relay", True, "relay and tmux on PATH")


def _check_mod(env) -> Check:
    """The band's module: seen (mod.json from `mod start`) or not. A `-p` child or a refused
    or absent module is not an error: warn, never FAIL (packet M1 ruling 3)."""
    state = resolver.state_dir(env)
    sid = env.get("CLAUDE_CODE_SESSION_ID") or resolver.newest_session(state)
    sdir = resolver.session_dir(state, sid) if sid else None
    line = mod.line(sdir)
    where = f" ({sdir / mod.MOD})" if sdir else " (no session)"
    return Check("mod", True, line + where, warn=not line.endswith(" ago"))


def _check_measure(env) -> Check:
    """The engine's measure beside the meter (packet M2 ruling 3): ok with no measure.json or
    a drift under measure.WARN_DRIFT, warn at it or past it, never FAIL."""
    state = resolver.state_dir(env)
    sid = env.get("CLAUDE_CODE_SESSION_ID") or resolver.newest_session(state)
    sdir = resolver.session_dir(state, sid) if sid else None
    d = measure.drift(sdir) if sdir else {"form": "none"}
    where = f" ({sdir / measure.MEASURE})" if sdir else " (no session)"
    warn = d["form"] == "drift" and d["tenths"] >= measure.WARN_TENTHS   # the printed figure
    return Check("measure", True, measure.line(sdir) + where, warn=warn)


def _check_bands(env) -> list:
    """A bad user bands file, or a shipped one that does not bind: a warn row each, never a
    failure; no row at all on a good file or none (packet S44)."""
    return [Check("bands", True, note, warn=True) for note in demand.schedule(env)[2]]


def _check_follow(env) -> Check | None:
    """Only while the shim's switch is on (design/04 §3), so no other row moves."""
    if not hooks.follow_launcher_on(env):
        return None
    return Check("hooks-follow-launcher", True,
                 "on: hooks run the launcher, not the plugin's pinned code; it lapses 24 h after "
                 "its mtime; rm ~/.config/agentik/hooks-follow-launcher once sessions have respawned",
                 warn=True)


def _check_instructions(env, cwd, plugins, sections) -> list:
    """Packet g1 R2 to R4: the files the repo's newest session loaded with their bytes, the
    warnings and the memory notes. Each row is ok, warn or note: none moves the exit."""
    return [Check(name, True, detail, note=kind == "note", warn=kind == "warn")
            for name, detail, kind in instructions.rows(env, cwd, plugins, sections)]


def _check_guard(env, cwd) -> Check:
    """Packets g2 R5 and g2b R4: the edit gates are on (they have no knob), how many lines are
    gated here, and the refusals the repo's newest session logged. Never a failure."""
    try:
        detail = instructionguard.doctor_row(env, cwd)
    except Exception:                                   # noqa: BLE001
        detail = "on"
    return Check("guard", True, detail)


class NoCwd(Exception):
    """The working directory is gone (review 2, R2-F3)."""


def run(env=None, cwd=None) -> Report:
    env = os.environ if env is None else env
    try:
        cwd = Path(cwd or env.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    except FileNotFoundError:
        raise NoCwd() from None
    rep = Report()
    add = rep.checks.append
    add(_check_claude(env))
    add(_check_python(env))
    add(_check_state(env))
    plugins, err = _plugin_list(env)
    add(_check_plugin(plugins, err))
    rows = _suite_sources(env, cwd) or {}       # fk3 R1: once a run
    installed, srcs = None, {}
    for dep in SIBLINGS:
        src = _answered(rows.get(dep["name"]), dep["name"])
        if src is None:                         # fk3 R2: no answer for this sibling
            installed = _installed(env) if installed is None else installed
            src = _recorded(installed, dep["name"])    # None: no entry, the pin's read
        srcs[dep["name"]] = src
        add(_check_dependency(dep, plugins, err, src))
    add(_check_profiles(env, cwd))
    add(_check_resolved(env))
    add(_check_meter(env))
    add(_check_meter_hook(plugins, err))
    cfg, sections = _check_config(env, cwd)
    add(cfg)
    no_relay = _relay_absent(plugins, srcs.get("relay"))    # review 1, F7: None unknown
    add(_check_git(env, sections, guarded=None if no_relay is None else not no_relay))
    relay = _check_relay(env, sections, sibling_absent=no_relay)
    if relay:
        add(relay)
    add(_check_mod(env))         # the rows above keep their places
    add(_check_measure(env))     # last (packet M2)
    add(_check_launcher(env, plugins))   # sc3: the rows above keep their places
    for row in _check_instructions(env, cwd, plugins, sections):
        add(row)                 # g1: after launcher, so every row of the pin keeps its place
    add(_check_guard(env, cwd))  # g2 R5: after the instructions rows, one row
    for row in _check_renamed(cwd, _renamed(env, cwd)):
        add(row)                 # agentik-r1 §6.3: after measure, so no row moves
    for row in _check_bands(env):
        add(row)                 # packet S44: only on a bad file
    sub = _check_subagent_model(env, sections, cwd)
    if sub:
        add(sub)                 # mt1 R2: only when the variable is off the table
    follow = _check_follow(env)
    if follow:
        add(follow)              # sc2: last, and only while on
    return rep


def _from(source) -> str:
    """fk3 R4: the id or folder and the version a sibling's text line prints after its detail;
    an undecided sibling's, each one seen."""
    if not source:
        return ""
    each = source.get("seen") if source.get("kind") == "undecided" else [source]
    names = [" ".join(x for x in (s.get("plugin") or s.get("root"), s.get("version")) if x)
             for s in each or ()]
    names = [n for n in names if n]
    if not names:
        return ""
    return (" (seen: " if source.get("kind") == "undecided" else " (from ") \
        + ", ".join(names) + ")"


def render(rep: Report) -> str:
    from .plug import withheld     # build 3, L1: the text withholds a secret as the read does
    lines = [f"{('note' if c.note else 'warn' if c.warn else 'ok  ') if c.ok else 'FAIL'} "
             f"{c.name:<12} {withheld(c.detail)}{withheld(_from(c.source))}"   # review 1, L4
             for c in rep.checks]
    failed = [c.name for c in rep.checks if not c.ok]
    lines.append("doctor: green" if rep.ok else "doctor: failing: " + ", ".join(failed))
    return "\n".join(lines)
