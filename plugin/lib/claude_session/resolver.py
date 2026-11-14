"""Resolve the layers into one file per session (overhaul-r1 §2.1, §2.3).

Layers, lowest first (D7):

  1. the plugin's profiles.yaml (shipped beside this module; read once, at import,
     and a missing one is an error, never an empty layer: F8)
  2. the user's ~/.claude/agentik/profiles.yaml (c5: else the pre-rename folder's)
  3. the repo's .claude/agentik/config.yaml (c4: else the pre-rename folder's)
  4. the repo's .claude/agentik/config.local.yaml (gitignored)
  5. the launch profile, when one was named (`agentik session start <profile>`)
  6. the session overlay (`agentik session set`, this session only)

The invocation flag sits above all of them and belongs to whoever reads the
file. The profile *name* is taken from the highest layer that names one
(launch, then local, then repo, then the user file's `defaults.profile`: packet mt1 R3),
else `frontier`; its values form the base, and a named launch profile re-applies its own
fields above the repo files.

`tiers` (packet mt1) is layered apart, role by role, lowest first (mt1 round 1, F1 F2):
the shipped `defaults`, the user's `defaults`, the shipped profile, the user's body of it,
the user file's top-level `tiers:`, the repo's (`config.yaml`, then `config.local.yaml`,
each its top-level `tiers:` alone: `session.tiers` is not read, F3), then, when the launch
named the profile, its own body again (shipped, then the user's). A layer's old
`subagents` is read as its `tiers.build` model. The session's own words (`set tier.*`,
`set cap`) are read against the clock by each reader (tiers.effective), never written
here; `subagents` is written as `tiers.build`'s model.

The engine's measured window, else the model, decides the window, and the role
the ceilings within it (models.py): the window is the engine's last reading for this
session, else the session's model's (the SessionStart payload's `model`), else
the declared model's (the profile's `model`), else the configured model's
(`ANTHROPIC_MODEL`, the settings), by the `models:` table. The ceilings are,
lowest first, the shipped defaults, the role's key for that window (`ceilings`
on 200k, `ceilings_1m` on 1M), then any user or project layer that sets
`ceilings` (both windows) or `ceilings_1m` (1M), field by field; the launch's
turn cap is last. The meter re-picks the window at each tool, so both windows'
ceilings are written (`windows`); a helper's 1M ceilings equal its 200k ones, so a
reading moves its window and never its ceiling (design/window-r1.md R2).

`resolve`'s output is a pure function of its inputs: `provider.resolved_at` is the
transcript's mtime, not the clock, and every input is listed with its sha256
(null when absent) so a wrong layer is visible in the file itself; the models it
read beside the layers are written as `session_model` (with `session_model_source`,
`payload` or `CLAUDE_SESSION_MODEL`) and `configured_models`; the engine's reading, when
one exists, is the input `engine:context.window`. `rewindow` then moves four keys of the
file at the engine's next measure, and from there `window_source` names the reading, while
`provider.inputs` still lists what the last resolve read.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import SEMVER
from . import config as cfgmod
from . import models, rules, tiers as tiermod
from .yamlsubset import dump, load

PLUGIN = "session"
# S38 ruling 4: `gate` (ntfy_url, ntfy_topic, wall) is a section; the runner reads its user
# layer alone (gate_config), since it serves every repo.
SECTIONS = ("session", "respeak", "decisions", "relay", "gate", "tiers")
GATE_DEFAULTS = {"ntfy_url": None, "ntfy_topic": None, "wall": 5400}
DEPENDENT = ("respeak", "decisions", "relay")
# agentik-r1 §6.3 c6: the relay's section before the rename. A layer's old key is read as
# `relay`, and `relay` wins over it in one layer, with a warning; the resolved file carries
# a copy under the old key until r2 (§8.6), for a relay that still reads it.
OLD_RELAY = "agent-relay"
# `window` is not an input: the model decides it (a layer that sets it is reported).
SESSION_KEYS = ("profile", "description", "model", "effort", "subagents", "tools",
                "permission_mode", "posture", "ceilings", "ceilings_1m", "checkpoint_at",
                "builders", "push", "device", "charter", "verify", "respawn", "priority",
                "pacing", "admission", "reconcile", "tiers", "lane", "plugins", "notes")
# `reconcile` (packet R2) is resolved as `respawn` is and never validated here: its checks
# are the `reconcile` verb's (exit 2), so a bad key never refuses a session.
# The respawn chain's guards (respawn-r1 §4): a mapping of these, each a non-negative int.
RESPAWN_KEYS = ("cap", "floor", "settle")
POSTURES = ("off", "signal", "ask", "deny")
SHIPPED = Path(__file__).with_name("profiles.yaml")
REPO_DIR = Path(".claude") / "agentik"
# agentik-r1 §6.3 c4, c5: the repo's and the user's folders before the rename.
OLD_REPO_DIR = Path(".claude") / "claude-code-session"
DEFAULT_PROFILE = "frontier"

# The overlay keeps its pre-profile knob names; these are the ones that differ.
OVERLAY_RENAMES = {"subagent_model": "subagents"}

LOCK_WAIT = 2.0        # seconds a writer of the resolved file waits for the session's lock
REWOUND = ("window", "ceilings", "window_source", "limits_source")     # what `rewindow` moves
_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")      # \Z: a trailing newline never passes


class ResolveError(ValueError):
    pass


_AT_LINE = re.compile(r": line (\d+): ")
_QUOTED = re.compile(r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*\"""")


def withheld(msg: str) -> str:
    """A parser's message names the file, the line and the reason, and nothing of the line's
    text, whatever it holds (review 2, R2-F1: a rule, not a pattern): what follows the reason,
    the quoted line, key or item, is dropped. A layer file's parse error is raised through it
    (row ss2), and the config read's error and the doctor's details, both forms, pass it."""
    m = _AT_LINE.search(msg) if isinstance(msg, str) else None
    if not m:
        return msg
    reason = re.split(r"""['"]""", msg[m.end():], maxsplit=1)[0].rstrip(": ")
    return msg[:m.end()] + reason


def scrubbed(msg: str) -> str:
    """A resolver's message as a read prints it: a parser's as `withheld` gives it, and any
    other with each quoted span (a value or name taken from a layer file) withheld."""
    return _QUOTED.sub("(withheld)", withheld(msg))


class ShippedGone(ResolveError):
    """The shipped profiles.yaml is missing, so its frozen tree went (F8). A ResolveError, so
    a caller holds on it as on any config error (respawn-r1 §4)."""


def _snapshot(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


# The shipped profiles, read once at import (F8): a launcher runs for hours from a frozen
# tree, and an install that removed the tree's files must not empty its profiles.
_SHIPPED_AT_IMPORT = (SHIPPED, _snapshot(SHIPPED))


@dataclass
class Resolved:
    session_id: str
    sections: dict
    provider: dict
    inputs: list = field(default_factory=list)       # [(path, sha256 | None)]
    unknown: list = field(default_factory=list)      # "layer: key", for doctor
    renamed: list = field(default_factory=list)      # "layer: agent-relay ...", for doctor
    tier_origins: dict = field(default_factory=dict)  # {role: the layer its model is from}

    def as_dict(self) -> dict:
        return {"provider": self.provider, **self.sections,
                OLD_RELAY: copy.deepcopy(self.sections.get("relay") or {})}


def repo_dir(cwd) -> Path:
    """The repo's config folder (c4): `.claude/agentik/`, else the old one when only it exists."""
    return cfgmod.pick(Path(cwd) / REPO_DIR, Path(cwd) / OLD_REPO_DIR)


def _relay_key(doc: dict, layer: str, renamed: list) -> dict:
    """c6: a layer's `agent-relay` read as `relay`; with both, `relay` wins."""
    if not isinstance(doc, dict) or OLD_RELAY not in doc:
        return doc
    out = {k: v for k, v in doc.items() if k != OLD_RELAY}
    if "relay" in doc:
        renamed.append(f"{layer}: {OLD_RELAY} and relay both set; relay wins, "
                       f"remove {OLD_RELAY}")
    else:
        out["relay"] = doc[OLD_RELAY]
        renamed.append(f"{layer}: {OLD_RELAY} is read as relay; rename the key")
    return out


def state_dir(env) -> Path:
    return cfgmod.state_dir(env)


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _read(path: Path, inputs: list) -> dict:
    """One layer: parsed, and listed as an input whether or not it exists."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        inputs.append((str(path), None))
        return {}
    return _parse(path, raw, inputs)


def _read_shipped(inputs: list) -> dict:
    """The shipped layer: the import's snapshot of SHIPPED (read now when SHIPPED was
    repointed or had no snapshot). Missing, it raises ShippedGone, never an empty layer."""
    path, raw = _SHIPPED_AT_IMPORT
    if path != SHIPPED or raw is None:
        path = SHIPPED
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise ShippedGone(f"the shipped profiles.yaml is gone: {path}; run install-cli") \
                from None
    return _parse(path, raw, inputs)


def _parse(path: Path, raw: bytes, inputs: list) -> dict:
    inputs.append((str(path), hashlib.sha256(raw).hexdigest()))
    try:
        doc = load(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ResolveError(withheld(f"{path}: {e}")) from None     # row ss2: never the line
    return doc


def _split(flat: dict, layer: str, unknown: list) -> dict:
    """A profile's flat fields into sections: plugin-named keys go to that plugin."""
    out: dict = {"session": {}}
    for k, v in flat.items():
        if k == OLD_RELAY:                       # c6: read as `relay`, which wins
            if "relay" in flat:
                continue
            k = "relay"
        if k in DEPENDENT:
            if v is not None and not isinstance(v, dict):
                raise ResolveError(f"{layer}: {k} must be a mapping")
            out[k] = v or {}
        elif k in SESSION_KEYS:
            out["session"][k] = v
        else:
            unknown.append(f"{layer}: {k}")
    return out


def _repo_sections(doc: dict, layer: str, unknown: list) -> dict:
    out: dict = {}
    for k, v in doc.items():
        if k not in SECTIONS:
            unknown.append(f"{layer}: {k}")
            continue
        if v is None:
            continue
        if not isinstance(v, dict):
            raise ResolveError(f"{layer}: section {k} must be a mapping")
        if k == "tiers":                  # mt1 R3: a repo's top-level block
            out[k] = v
            continue
        if k == "session":
            for sk in v:
                if sk not in SESSION_KEYS or sk == "tiers":     # mt1 r1 F3: one spelling
                    unknown.append(f"{layer}: session.{sk}")
            v = {sk: sv for sk, sv in v.items() if sk in SESSION_KEYS and sk != "tiers"}
        out[k] = v
    return out


def _user_relay_keys(user: dict, renamed: list) -> dict:
    """c6 in the user's profiles.yaml: each `defaults` and profile body read by _relay_key,
    before the merge, so the user's old key still overrides the shipped `relay`."""
    if not isinstance(user, dict):
        return user
    out = dict(user)
    if isinstance(out.get("defaults"), dict):
        out["defaults"] = _relay_key(out["defaults"], "profiles.yaml: defaults", renamed)
    if isinstance(out.get("profiles"), dict):
        out["profiles"] = {n: _relay_key(b, f"profiles.yaml: {n}", renamed)
                           for n, b in out["profiles"].items()}
    return out


def _profiles(shipped: dict, user: dict) -> tuple[dict, dict]:
    defaults = _merge(shipped.get("defaults") or {}, user.get("defaults") or {})
    profiles = copy.deepcopy(shipped.get("profiles") or {})
    for name, body in (user.get("profiles") or {}).items():
        profiles[name] = _merge(profiles.get(name) or {}, body or {})
    return defaults, profiles


def _models(shipped: dict, user: dict, user_path: Path) -> dict:
    """The models table: the shipped one, the user's entries over it. A bad entry names its
    file and the section and withholds the key, a layer file's text (ss2 R1-F2); the parser
    keeps no line for a key."""
    table = {**(shipped.get("models") or {}), **(user.get("models") or {})}
    for k, v in table.items():
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            src = user_path if k in (user.get("models") or {}) else SHIPPED
            raise ResolveError(f"{src}: models: a key (withheld) must be a positive integer "
                               "(a window in tokens)")
    return table


def _respawn_keys(body, path) -> None:
    """ss2 R1-F2: a `respawn` key that is none of RESPAWN_KEYS is a layer file's text, so
    the file and the section are named and the key withheld."""
    rs = body.get("respawn") if isinstance(body, dict) else None
    if isinstance(rs, dict) and any(k not in RESPAWN_KEYS for k in rs):
        raise ResolveError(f"{path}: respawn: a key (withheld) is not a respawn key "
                           f"({', '.join(RESPAWN_KEYS)})")


def _window_ceilings(shipped: dict, user: dict, name: str, explicit: list) -> dict:
    """{window class: (ceilings, source)}. Lowest first: the shipped defaults; the
    role's key for the window (`ceilings` on 200k, `ceilings_1m` on 1M); then each
    user or project layer, field by field, where `ceilings` sets both windows and
    `ceilings_1m` the 1M one. The launch layer re-applies the role, which never
    outranks a user or project layer here."""
    sd = shipped.get("defaults") or {}
    role = (shipped.get("profiles") or {}).get(name) or {}
    layers = [("user", user.get("defaults") or {}),
              ("user", (user.get("profiles") or {}).get(name) or {})] + explicit
    out = {}
    for cls, key in models.CLASSES.items():
        base, src = dict(sd.get(key) or {}), "defaults"
        if isinstance(role.get(key), dict):
            base, src = _merge(base, role[key]), f"role:{name}"
        for label, layer in layers:
            for k in ("ceilings",) + ((key,) if key != "ceilings" else ()):
                v = layer.get(k)
                if v is None:
                    continue
                if not isinstance(v, dict):
                    raise ResolveError(f"{label}: {k} must be a mapping")
                base, src = _merge(base, v), label
        for k in ("context", "turns"):
            if not isinstance(base.get(k), int) or isinstance(base.get(k), bool) or base[k] <= 0:
                raise ResolveError(f"{key}.{k} must be a positive integer")
        out[cls] = ({"context": base["context"], "turns": base["turns"]}, src)
    return out


def _tier_layer(body) -> dict:
    """One layer's tiers: its `tiers`, with an old `subagents` as the build model when the
    layer names no build model itself (mt1 R1's read alias)."""
    body = body if isinstance(body, dict) else {}
    t = body.get("tiers")
    if t is not None and not isinstance(t, dict):
        raise ResolveError("tiers must be a mapping of design, build, words, mend, lookup")
    t = dict(t or {})
    sub = body.get("subagents")
    b = t.get("build")
    if isinstance(sub, str) and sub and not (isinstance(b, dict) and b.get("model")
                                             or isinstance(b, str)):
        t["build"] = {**(b if isinstance(b, dict) else {}), "model": sub}
    return t


def _tier_layers(shipped, user, name, repo_s, local_s, launch, ov_sub, where) -> list:
    """[(origin, layer)] for profile `name`, lowest first (the module's docstring); `where`
    names the user's, the repo's and the local file."""
    sp = (shipped.get("profiles") or {}).get(name)
    up = (user.get("profiles") or {}).get(name) if isinstance(user.get("profiles"), dict) \
        else None
    ud = user.get("defaults") if isinstance(user.get("defaults"), dict) else {}
    u = where["user"]
    out = [("the shipped defaults", (shipped.get("defaults") or {}).get("tiers") or {}),
           (f"{u}: defaults", _tier_layer(ud)),
           (f"the shipped profile {name}", _tier_layer(sp)),
           (f"{u}: profiles.{name}", _tier_layer(up)),
           (f"{u}: tiers", _tier_layer({"tiers": user.get("tiers")}))]
    for key, secs in (("repo", repo_s), ("local", local_s)):
        sub = (secs.get("session") or {}).get("subagents")
        out += [(f"{where[key]}: session.subagents", _tier_layer({"subagents": sub})),
                (f"{where[key]}: tiers", _tier_layer({"tiers": secs.get("tiers")}))]
    if launch:
        out += [(f"the launch profile {name} (shipped)", _tier_layer(sp)),
                (f"the launch profile {name} ({u}: profiles.{name})", _tier_layer(up))]
    out.append(("this session's overlay", _tier_layer({"subagents": ov_sub})))
    return out


def _bad_key(origin: str, role: str, field: str = "model") -> str:
    if origin.endswith(": tiers"):
        return f"{origin}.{role}.{field}"
    return origin if origin.endswith("session.subagents") else f"{origin}.tiers.{role}.{field}"


def _known(field: str, x) -> bool:
    """A layer's model names a family; its effort is one of tiers.EFFORTS."""
    return tiermod.family(x) is not None if field == "model" else x in tiermod.EFFORTS


def _tiers(layers, unknown: list) -> tuple[dict, dict]:
    """(the table, {role: the origin of its model}) from _tier_layers' list. A layer's model
    that names no family or is null, and its effort outside tiers.EFFORTS or null, is
    dropped where it stands, the role keeping the lower layer's, and its key joins `unknown`
    (mt1 R2-F1, R3-F1, R3-F4: a typo never fails resolution). A role with no value is
    skipped, unnamed."""
    table: dict = {}
    origins: dict = {}
    for origin, layer in layers:
        layer = dict(layer)
        for r, v in list(layer.items()):
            if r not in tiermod.ROLES or not isinstance(v, (str, dict)):
                continue
            bad = [f for f in ("model", "effort")
                   if (f in v and not _known(f, v[f]) if isinstance(v, dict)
                       else f == "model" and not _known(f, v))]
            for f in bad:
                if _bad_key(origin, r, f) not in unknown:
                    unknown.append(_bad_key(origin, r, f))
            if bad:
                layer[r] = ({k: x for k, x in v.items() if k not in bad}
                            if isinstance(v, dict) else None)
        table = tiermod.merge(table, layer)
        for r, v in layer.items():
            if isinstance(v, str) or isinstance(v, dict) and v.get("model") is not None:
                origins[r] = origin
    try:
        tiermod.check(table)
    except ValueError as e:
        raise ResolveError(str(e)) from None
    return table, origins


def user_profile(env) -> str | None:
    """The user file's `defaults.profile` (mt1 R3), else None; never raises."""
    try:
        doc = _read(_user_file(env), [])
    except (ResolveError, OSError, RecursionError):
        return None
    d = doc.get("defaults") if isinstance(doc, dict) else None
    v = d.get("profile") if isinstance(d, dict) else None
    return v if isinstance(v, str) and v else None


def load_profiles(env) -> tuple[dict, dict]:
    """(defaults, profiles) from the shipped and the user's files; for doctor and `profile`."""
    inputs: list = []
    return _profiles(_read_shipped(inputs),
                     _user_relay_keys(_read(_user_file(env), inputs), []))


def _user_file(env) -> Path:
    """The user layer: `$CLAUDE_CONFIG_DIR/agentik/profiles.yaml` when that file exists
    (packet mt1 R3), else `~/.claude/agentik/profiles.yaml` (c5: else the old folder's)."""
    home = Path(env.get("HOME") or Path.home())
    ccd = env.get("CLAUDE_CONFIG_DIR")
    if ccd and (Path(ccd) / "agentik" / "profiles.yaml").is_file():
        return Path(ccd) / "agentik" / "profiles.yaml"
    return cfgmod.pick(home / ".claude" / "agentik" / "profiles.yaml",
                       home / OLD_REPO_DIR / "profiles.yaml")


def window_override(env) -> dict:
    """`window` and `windows` from the user layer's `defaults.admission`, read alone, for a
    session with no resolved file (a relay row's ask before its child starts: packet S42
    Amendment 1). No other knob, no profile, and no repo layer, since such a session names no
    directory. An unreadable file or field is unset; it never raises."""
    try:
        doc = _read(_user_file(env), [])
    except (ResolveError, OSError, RecursionError):     # a file nested past the stack
        return {}
    d = doc.get("defaults") if isinstance(doc, dict) else None
    ad = d.get("admission") if isinstance(d, dict) else None
    return {k: ad[k] for k in ("window", "windows") if k in ad} if isinstance(ad, dict) else {}


def user_mix(env):
    """`mix` from the user layer's `defaults.admission`, read alone (packet S53 F5), as
    `window_override` reads `window`: every record and band write reads the mix here, never
    from the recording session's resolved file. None when unset or unreadable; never raises."""
    try:
        doc = _read(_user_file(env), [])
    except (ResolveError, OSError, RecursionError):
        return None
    d = doc.get("defaults") if isinstance(doc, dict) else None
    ad = d.get("admission") if isinstance(d, dict) else None
    return ad.get("mix") if isinstance(ad, dict) else None


def gate_config(env, log=None) -> dict:
    """The gate section's user layer (design/gate-r1.md ruling 4): the top-level `gate:`
    mapping of the user's profiles.yaml, read alone. A key unset, mistyped or unreadable
    reads as its default (no ntfy, a 5400 s wall); it never raises. `load_ceiling` and
    `max_running` (packet S47) appear only when set well, and the gate holds their defaults,
    since one follows the core count; a bad one is one line through `log`."""
    out = dict(GATE_DEFAULTS)
    try:
        doc = _read(_user_file(env), [])
    except (ResolveError, OSError):
        return out
    g = doc.get("gate") if isinstance(doc, dict) else None
    if not isinstance(g, dict):
        return out
    for k in ("ntfy_url", "ntfy_topic"):
        v = g.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    w = g.get("wall")
    if isinstance(w, int) and not isinstance(w, bool) and w > 0:
        out["wall"] = w
    c = g.get("load_ceiling")
    if isinstance(c, (int, float)) and not isinstance(c, bool) and 0 < c < float("inf"):
        out["load_ceiling"] = c
    elif "load_ceiling" in g and log:
        log(f"gate: load_ceiling {c!r} is no positive number; the default stands")
    m = g.get("max_running")
    if isinstance(m, int) and not isinstance(m, bool) and m > 0:
        out["max_running"] = m
    elif "max_running" in g and log:
        log(f"gate: max_running {m!r} is no positive whole number; the default stands")
    return out


def _validate(s: dict) -> None:
    """The ceilings are checked per window, in _window_ceilings."""
    if s.get("posture") not in POSTURES:
        raise ResolveError(f"posture must be one of {', '.join(POSTURES)}")
    cp = s.get("checkpoint_at")
    if not isinstance(cp, (int, float)) or isinstance(cp, bool) or not 0 < cp <= 1:
        raise ResolveError("checkpoint_at must be in (0, 1]")
    for k in ("push", "device"):          # the relay's guards compare these verbatim
        if not isinstance(s.get(k), str) or not s[k]:
            raise ResolveError(f"{k} must be `never` or the owner's quoted words")
    rs = s.get("respawn")
    if not isinstance(rs, dict):
        raise ResolveError("respawn must be a mapping of " + ", ".join(RESPAWN_KEYS))
    for k, v in rs.items():
        if k not in RESPAWN_KEYS:
            raise ResolveError("respawn: a key (withheld) is not a respawn key "   # ss2 R1-F2
                               f"({', '.join(RESPAWN_KEYS)})")
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ResolveError(f"respawn.{k} must be a non-negative integer")
    try:
        rules.check(s)                    # priority and pacing (S21)
    except ValueError as e:
        raise ResolveError(str(e)) from None


def _normalized(body: dict, unknown: list, layer: str) -> dict:
    """One layer's session keys, priority and pacing checked as that layer's (S21)."""
    try:
        return rules.normalize(body, unknown, layer)
    except ValueError as e:
        raise ResolveError(str(e)) from None


# review r6 E5: a launch's own turn limit (`start --max-turns N`, or the relay's
# per-row max_turns) caps the profile's; the smaller wins and the session records which.
MAX_TURNS_VAR = "CLAUDE_SESSION_MAX_TURNS"


def max_turns(env) -> int | None:
    """The launch's turn limit, or None when absent, unparsable or not positive."""
    raw = (env.get(MAX_TURNS_VAR) or "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _turn_cap(ceilings: dict, env) -> tuple[dict, str]:
    cap = max_turns(env)
    if cap is not None and cap < ceilings["turns"]:
        return {**ceilings, "turns": cap}, MAX_TURNS_VAR
    return dict(ceilings), "profile"


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def resolve(cwd, session_id: str, env, profile: str | None = None,
            overlay: dict | None = None, transcript_path=None,
            session_model: str | None = None,
            session_model_source: str | None = None) -> Resolved:
    """Resolve every layer for one session. Raises ResolveError; writes nothing.
    `session_model` is the SessionStart payload's `model`, or under `claude -p` the
    launcher's `CLAUDE_SESSION_MODEL`, when the hook has one; `session_model_source`
    names which (`payload` when a caller passes a model without it), null with no model."""
    if not session_id or not _SID.match(str(session_id)):
        raise ResolveError(f"session_id is not an id: {str(session_id)[:40]!r}")
    cwd = Path(cwd)
    inputs: list = []
    unknown: list = []
    renamed: list = []

    shipped = _read_shipped(inputs)
    user = _user_relay_keys(_read(_user_file(env), inputs), renamed)
    rdir = repo_dir(cwd)
    repo = _relay_key(_read(rdir / "config.yaml", inputs), "config.yaml", renamed)
    local = _relay_key(_read(rdir / "config.local.yaml", inputs), "config.local.yaml",
                       renamed)

    ov_path = state_dir(env) / "overlays" / f"{session_id}.json"
    ov_src = ov_path if overlay is None else "the overlay"
    if overlay is None:
        try:
            raw = ov_path.read_bytes()
            inputs.append((str(ov_path), hashlib.sha256(raw).hexdigest()))
            overlay = json.loads(raw)
        except FileNotFoundError:
            inputs.append((str(ov_path), None))
            overlay = {}
        except (OSError, ValueError) as e:
            raise ResolveError(f"{ov_path}: {e}") from None
    else:
        canon = json.dumps(overlay, sort_keys=True).encode()
        inputs.append(("overlay:argument", hashlib.sha256(canon).hexdigest()))
    if not isinstance(overlay, dict):
        raise ResolveError("the overlay must be a mapping")

    defaults, profiles = _profiles(shipped, user)
    repo_s = _repo_sections(repo, "config.yaml", unknown)
    local_s = _repo_sections(local, "config.local.yaml", unknown)

    ud = user.get("defaults") if isinstance(user.get("defaults"), dict) else {}
    name = (profile or (local_s.get("session") or {}).get("profile")
            or (repo_s.get("session") or {}).get("profile")
            or (ud.get("profile") if isinstance(ud.get("profile"), str) else None)
            or DEFAULT_PROFILE)
    if name not in profiles:
        # row ss2: a name read from a layer file (session.profile) is its text, so it is
        # withheld; a name the caller gave (the launch's CLAUDE_SESSION_PROFILE, an
        # argument) prints as it did (R1-F3)
        said = repr(profile) if profile else "(withheld)"
        raise ResolveError(f"unknown profile {said}; known: {', '.join(profiles)}")
    own = profiles[name] or {}

    sections = {s: {} for s in SECTIONS}
    ub = [user.get("defaults"), (user.get("profiles") or {}).get(name)]
    try:                                    # ss2 R1-F2: which file holds a stray respawn key
        for b in ub:
            _respawn_keys(b, "")
        up = SHIPPED
    except ResolveError:
        up = _user_file(env)
    files = {"profiles.yaml": up, "launch": up, "config.yaml": rdir / "config.yaml",
             "config.local.yaml": rdir / "config.local.yaml"}
    for layer, secs in (
            ("profiles.yaml", _split(_merge(defaults, own), "profiles.yaml", unknown)),
            ("config.yaml", repo_s),
            ("config.local.yaml", local_s),
            ("launch", _split(own, "launch", unknown) if profile else {})):
        for s, body in secs.items():
            if s == "session":
                _respawn_keys(body, files[layer])
                body = _normalized(body, unknown, layer)
            sections[s] = _merge(sections[s], body)

    ov_session = {}
    for k, v in overlay.items():
        if k.startswith("_"):
            continue
        k = OVERLAY_RENAMES.get(k, k)
        if k in SESSION_KEYS:
            ov_session[k] = v
    _respawn_keys(ov_session, ov_src)
    ov_session = _normalized(ov_session, unknown, "overlay")
    sections["session"] = _merge(sections["session"], ov_session)
    sections["session"]["profile"] = name
    sections.pop("tiers", None)
    merged = {k: sections["session"].get(k) for k in SESSION_KEYS}
    where = {"user": str(_user_file(env)), "repo": str(rdir / "config.yaml"),
             "local": str(rdir / "config.local.yaml")}
    merged["tiers"], origins = _tiers(_tier_layers(shipped, user, name, repo_s, local_s,
                                                   bool(profile), ov_session.get("subagents"),
                                                   where), unknown)
    merged["subagents"] = merged["tiers"]["build"]["model"]       # mt1 R1's read alias
    _validate(merged)
    per = _window_ceilings(shipped, user, name, [
        ("config.yaml", repo_s.get("session") or {}),
        ("config.local.yaml", local_s.get("session") or {}),
        ("overlay", ov_session)])
    table = _models(shipped, user, _user_file(env))
    session_model = session_model if isinstance(session_model, str) else None
    configured = models.configured(env, cwd)
    engine = models.engine_window(session_dir(state_dir(env), str(session_id)))
    if engine is not None:
        inputs.append(("engine:context.window",
                       hashlib.sha256(json.dumps(engine).encode()).hexdigest()))
    window, window_source = models.pick(table, None, session_model, merged.get("model"),
                                        configured, engine)
    windows, caps = {}, {}
    for cls, (ceil, src) in per.items():
        capped, caps[cls] = _turn_cap(ceil, env)
        windows[cls] = {**capped, "source": src}
    if env.get("CLAUDE_SESSION_HELPER") == "1":     # R2: its 200k class whatever a layer sets
        windows["1m"], caps["1m"] = dict(windows["200k"]), caps["200k"]
    here = models.window_class(window)
    session = {}
    for k in SESSION_KEYS:
        if k == "ceilings":
            session["ceilings"] = {"context": windows[here]["context"],
                                   "turns": windows[here]["turns"]}
            session["window"] = window
        elif k != "ceilings_1m":
            session[k] = merged.get(k)
    session["ceilings_source"] = caps[here]
    session["window_source"] = window_source
    session["limits_source"] = f"{windows[here]['source']} window:{window}"
    session["windows"] = windows
    session["models"] = table
    session["session_model"] = session_model
    session["session_model_source"] = (
        (session_model_source or "payload") if session_model is not None else None)
    session["configured_models"] = configured
    sections["session"] = session

    mtime = None
    if transcript_path:
        try:
            mtime = os.stat(transcript_path).st_mtime
        except OSError:
            mtime = None
    provider = {"plugin": PLUGIN, "version": SEMVER, "profile": name,
                "resolved_at": _iso(mtime),
                "inputs": [{"path": p, "sha256": h} for p, h in inputs]}
    return Resolved(session_id=str(session_id), sections=sections,
                    provider=provider, inputs=inputs, unknown=unknown, renamed=renamed,
                    tier_origins=origins)


def session_dir(state: Path, session_id: str) -> Path:
    return Path(state) / "sessions" / session_id


def _write_atomic(path: Path, text: str) -> None:
    """Whole or not at all. The temp name is this process's: a writer that went on past
    the lock and one stalled on its temp never share a file, so neither can tear the other."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def _session_lock(sdir: Path):
    """`flock` on the session directory's own descriptor, so it creates no file; yields
    whether it is held, after at most LOCK_WAIT seconds. Closing the descriptor frees it."""
    fd = None
    held = False
    try:
        fd = os.open(sdir, os.O_RDONLY)
        give_up = time.monotonic() + LOCK_WAIT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
                break
            except BlockingIOError:
                if time.monotonic() >= give_up:
                    break
                time.sleep(0.005)
    except OSError:
        held = False
    try:
        yield held
    finally:
        if fd is not None:
            os.close(fd)


def _write_doc(d: Path, doc: dict) -> None:
    _write_atomic(d / "resolved.json", json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    _write_atomic(d / "resolved.yaml", dump(doc))


def write(resolved: Resolved, state: Path) -> Path:
    """resolved.json and its .yaml twin, under the session's lock (with no lock it goes on:
    the hook never breaks a session); returns the JSON path."""
    d = session_dir(state, resolved.session_id)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _session_lock(d):
        _write_doc(d, resolved.as_dict())
    return d / "resolved.json"


def _twin_agrees(d: Path, s: dict) -> bool:
    """The YAML twin holds the JSON's REWOUND keys; an absent or unreadable twin does not."""
    try:
        t = load((d / "resolved.yaml").read_text())["session"]
        return all(t[k] == s[k] for k in REWOUND)
    except Exception:                                           # noqa: BLE001
        return False


def rewindow(sdir, n) -> bool:
    """The engine's reading `n` moves the resolved file (window-r1 R4): when `session.window`
    differs and `session.windows` holds its class, `window`, `ceilings`, `window_source` and
    `limits_source` move, in both twins, and nothing else does. It reads no env and no layer.
    A YAML twin that disagrees with the JSON on those keys, as a failure between the two
    writes leaves it, is rewritten from the JSON, so the next measure really retries.
    True when it wrote. A failure of any kind, the lock's included, is False and silent."""
    try:
        if not models.readable_window(n):
            return False
        d = Path(sdir)
        with _session_lock(d) as held:
            if not held:
                return False
            doc = json.loads((d / "resolved.json").read_text())
            s = doc["session"]
            c = s["windows"][models.window_class(n)]
            if s["window"] == n:
                if _twin_agrees(d, s):
                    return False
                _write_atomic(d / "resolved.yaml", dump(doc))
                return True
            s["window"] = n
            s["ceilings"] = {"context": c["context"], "turns": c["turns"]}
            s["window_source"] = f"engine:{n}"
            s["limits_source"] = f"{c['source']} window:{n}"
            _write_doc(d, doc)
            return True
    except Exception:                                           # noqa: BLE001
        return False


def save_request(sdir: Path, cwd, profile, transcript_path, model=None,
                 model_source=None) -> None:
    """What the hook resolved with, so `set` can re-resolve the same inputs: the
    session model with its source (S28), so a re-resolve records the same one."""
    model = model if isinstance(model, str) else None
    _write_atomic(Path(sdir) / "request.json", json.dumps(
        {"cwd": str(cwd), "profile": profile,
         "transcript_path": str(transcript_path) if transcript_path else None,
         "model": model,
         "model_source": model_source if model is not None else None},
        indent=2) + "\n")


def load_request(sdir: Path) -> dict | None:
    try:
        d = json.loads((Path(sdir) / "request.json").read_text())
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def newest_session(state: Path) -> str | None:
    """The most recently resolved session, for callers without an id."""
    root = Path(state) / "sessions"
    try:
        dirs = [p for p in root.iterdir() if (p / "resolved.json").exists()]
    except OSError:
        return None
    if not dirs:
        return None
    return max(dirs, key=lambda p: (p / "resolved.json").stat().st_mtime).name
