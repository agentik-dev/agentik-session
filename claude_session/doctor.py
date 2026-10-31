"""`agentik session doctor`: the checks of overhaul-r1 §2.4, in that order.

Unknown is never a pass: a probe that cannot run, a file that cannot be read,
a version that cannot be parsed, each is a failing check with the reason named.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import demand, hooks, measure, meter, mod, resolver

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
HOOK_EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure",
               "PostToolBatch", "UserPromptSubmit", "Stop", "StopFailure", "SessionEnd",
               "PreCompact")
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


@dataclass
class Report:
    checks: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def as_dict(self) -> dict:
        return {"ok": self.ok,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail}
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
    ok = tuple(version[:2]) >= (3, 11)   # the launcher runs `python -P` (ADV6-3)
    newest, source = newest_known(env)
    detail = f"{ver} ({exe}); newest known {newest} ({source})"
    return Check("python", ok, detail + ("" if ok else "; needs 3.11+"))


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
                     "restart Claude Code")
    # S20 ruling 3: a CLI older than its plugin refuses an event it does not know (exit 2).
    unknown = [e for e in registered if e not in hooks.HANDLERS]
    if unknown:
        return Check("plugin", False, f"{pid} {p.get('version')} registers "
                     + ", ".join(unknown) + ", which this agentik-session does not handle: "
                     "the CLI is older than the plugin's hooks; install the CLI first "
                     "(`make install`), then `claude plugin update`")
    if old:
        return Check("plugin", True, f"{pid} {p.get('version')} enabled; "
                     + _switch_note(pid, PLUGIN_ID), warn=True)
    if _twice(plugins, pid, OLD_PLUGIN_ID):
        return Check("plugin", True, f"{pid} {p.get('version')} enabled; "
                     + _twice_note(OLD_PLUGIN_ID, pid), warn=True)
    return Check("plugin", True, f"{PLUGIN_ID} {p.get('version')} enabled; hooks "
                 + ", ".join(HOOK_EVENTS))


def _check_dependency(dep: dict, plugins, err) -> Check:
    """A sibling is optional: absent or disabled is a note, any version is fine. With no
    plugin list the `plugin` check is already red; this line only names the unknown."""
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


def _sibling_absent(plugins, name: str) -> bool:
    """True only when the plugin list was read and holds no enabled `name`."""
    if plugins is None:
        return False
    dep = next(d for d in SIBLINGS if d["name"] == name)
    _, p, _ = _pick_id(plugins, f"{name}@{dep['marketplace']}", dep["old"])
    return not (p and p.get("enabled"))


def _check_profiles(env, cwd) -> Check:
    try:
        _, profiles = resolver.load_profiles(env)
        for name in profiles:
            resolver.resolve(cwd, "doctor", env, profile=name, overlay={})
    except resolver.ResolveError as e:
        return Check("profiles", False, str(e))
    return Check("profiles", True, f"{len(profiles)} resolve: " + ", ".join(profiles))


def _check_resolved(env) -> Check:
    state = resolver.state_dir(env)
    sid = env.get("CLAUDE_CODE_SESSION_ID")
    note = ""
    if not sid:
        sid = resolver.newest_session(state)
        note = " ($CLAUDE_CODE_SESSION_ID unset: the newest session)"
        if not sid:
            return Check("resolved", False, "$CLAUDE_CODE_SESSION_ID unset and no session "
                         "resolved yet")
    path = resolver.session_dir(state, sid) / "resolved.json"
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return Check("resolved", False, f"{path}: {e.__class__.__name__}{note}")
    prof = (doc.get("provider") or {}).get("profile")
    return Check("resolved", True, f"{path}, profile {prof}{note}")


def _check_meter(env) -> Check:
    """meter.json exists and matches its transcript's size, or its ts is within
    FRESH_S of the transcript's mtime."""
    state = resolver.state_dir(env)
    sid = env.get("CLAUDE_CODE_SESSION_ID") or resolver.newest_session(state)
    if not sid:
        return Check("meter", False, "no session to meter ($CLAUDE_CODE_SESSION_ID unset, "
                     "none resolved)")
    path = resolver.session_dir(state, sid) / meter.METER
    m = meter.load(path.parent)
    if m is None:
        return Check("meter", False, f"{path} absent: no PostToolUse has metered this "
                     "session (the plugin's hook)")
    tp = (m.get("transcript") or {}).get("path")
    try:
        size = os.stat(tp).st_size
    except (OSError, TypeError) as e:
        return Check("meter", False, f"{path}: transcript {tp} unreadable: "
                     f"{e.__class__.__name__}")
    summary = f"{m.get('pct_context')}% context, {m.get('pct_turns')}% turns, zone {m.get('zone')}"
    if (m.get("transcript") or {}).get("size") == size:
        return Check("meter", True, f"{path}: {summary}; transcript size matches")
    age = meter.mtime_age(m)
    if age is not None and age <= FRESH_S:
        return Check("meter", True, f"{path}: {summary}; {age:.0f}s from the transcript")
    return Check("meter", False, f"{path} stale: metered {(m.get('transcript') or {}).get('size')}"
                 f" bytes of {size}, " + ("ts unreadable" if age is None
                                          else f"{age:.0f}s from the transcript's mtime"))


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
    path = resolver.repo_dir(cwd) / "config.yaml"
    sections: dict = {}
    try:
        r = resolver.resolve(cwd, "doctor", env, overlay={})
        sections = r.sections
    except resolver.ResolveError as e:
        return Check("config", False, str(e)), sections
    if not path.exists():
        return Check("config", True, f"no {path}; the defaults"), sections
    detail = f"{path} parses, profile {sections['session']['profile']}"
    if r.unknown:
        detail += "; unknown keys, ignored: " + ", ".join(r.unknown)
    return Check("config", True, detail), sections


def _renamed(env, cwd) -> list:
    try:
        return resolver.resolve(cwd, "doctor", env, overlay={}).renamed
    except resolver.ResolveError:
        return []


def _check_renamed(cwd, r_renamed) -> list:
    """agentik-r1 §6.3's warn rows: the repo's old folder (c4), the old section key (c6)."""
    rows = []
    old = Path(cwd) / resolver.OLD_REPO_DIR
    if old.is_dir() and not old.is_symlink():
        new = Path(cwd) / resolver.REPO_DIR
        where = "read" if resolver.repo_dir(cwd) == old else f"unread, {new} wins"
        rows.append(Check("config-dir", True, f"{old} is the folder before the rename "
                          f"({where}): `git mv` it to {new} (agentik-r1 §6.3 c4)", warn=True))
    for line in r_renamed:
        rows.append(Check("config-key", True, f"{line} (agentik-r1 §6.3 c6)", warn=True))
    return rows


def _check_git(env, sections, guarded: bool = True) -> Check:
    exe = _which("git", env)
    if not exe:
        return Check("git", False, "`git` not on PATH")
    push = (sections.get("session") or {}).get("push", "never")
    extra = ""
    if push == "never":
        extra = ("; push: never, guarded by the relay plugin (its check above)" if guarded
                 else "; push: never, unguarded without the relay plugin")
    return Check("git", True, exe + extra)


def _check_relay(env, sections, sibling_absent: bool = False) -> Check | None:
    enabled = (sections.get("relay") or {}).get("enabled", "auto")
    if enabled not in ("auto", "on", True):
        return None
    if enabled == "auto" and sibling_absent:
        return Check("relay", True, "relay.enabled is auto and the relay plugin not "
                     "installed: no relay expected", note=True)
    missing = [b for b in ("relay", "tmux") if not _which(b, env)]
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


def run(env=None, cwd=None) -> Report:
    env = os.environ if env is None else env
    cwd = Path(cwd or env.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    rep = Report()
    add = rep.checks.append
    add(_check_claude(env))
    add(_check_python(env))
    add(_check_state(env))
    plugins, err = _plugin_list(env)
    add(_check_plugin(plugins, err))
    for dep in SIBLINGS:
        add(_check_dependency(dep, plugins, err))
    add(_check_profiles(env, cwd))
    add(_check_resolved(env))
    add(_check_meter(env))
    add(_check_meter_hook(plugins, err))
    cfg, sections = _check_config(env, cwd)
    add(cfg)
    no_relay = _sibling_absent(plugins, "relay")
    add(_check_git(env, sections, guarded=not no_relay))
    relay = _check_relay(env, sections, sibling_absent=no_relay)
    if relay:
        add(relay)
    add(_check_mod(env))         # the rows above keep their places
    add(_check_measure(env))     # last (packet M2)
    for row in _check_renamed(cwd, _renamed(env, cwd)):
        add(row)                 # agentik-r1 §6.3: after measure, so no row moves
    for row in _check_bands(env):
        add(row)                 # packet S44: last, and only on a bad file
    return rep


def render(rep: Report) -> str:
    lines = [f"{('note' if c.note else 'warn' if c.warn else 'ok  ') if c.ok else 'FAIL'} "
             f"{c.name:<12} {c.detail}"
             for c in rep.checks]
    failed = [c.name for c in rep.checks if not c.ok]
    lines.append("doctor: green" if rep.ok else "doctor: failing: " + ", ".join(failed))
    return "\n".join(lines)
