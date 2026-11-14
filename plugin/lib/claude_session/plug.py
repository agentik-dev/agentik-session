"""The plug's reads (packet ak5): what the suite's `agentik config`, `doctor` and `status` read.

`describe --json` names the tool, what it needs, its verbs and its other reads. The config read,
`describe config --json [KEY]`, gives each setting of the resolved `session` section, then the
five roles' tiers, then the gate's keys: its value (`resolver.resolve`'s, or `gate_config`'s),
its value on a machine where nothing is set, every layer that sets it with the file and line it
stands on, and how to change it. Resolution is `resolver.py`'s alone: this module reads the same
files again only to say where each value stands, and a line it cannot find is null, never a
guess. Nothing here writes.
"""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import SEMVER, doctor, hooks, models, resolver, sessionconfig
from . import tiers as tiermod
from .yamlsubset import _KEY, _strip_comment, _value, dump, load

TOOL = "session"
SUMMARY = "Runs Claude Code sittings on named profiles and meters each one's budget."
# The manifest's names (its `repository` and `name`, a test holds them equal), kept here so the
# read adds no JSON reader of its own: `__init__._pin` is the manifest's one reader.
REPO, PLUGIN = "agentik-dev/agentik-session", doctor.PLUGIN_ID
SCHEMAS = {"meter": "agentik.session.meter/1", "gate": "agentik.session.gate/1",
           "unattended": "agentik.session.unattended/1", "doctor": "agentik.doctor/1"}
LAYERS = ("default", "user-defaults", "profile", "user", "repo", "local", "launch", "session")
NOT_SETTINGS = ("description", "subagents", "ceilings_1m", "tiers")
MAPPINGS = ("admission", "reconcile")      # a row a leaf a layer sets, none when unset
GATE_KEYS = ("ntfy_url", "ntfy_topic", "wall", "load_ceiling", "max_running")
SECRETS = ("gate.ntfy_topic",)
LIVE = ("posture",)                        # `set posture`: the next read holds it
LIVE_PREFIX = ("gate.", "reconcile.")      # gate_config and the reconciler read files each run
TYPES = {"checkpoint_at": "number", "tools": "list", "plugins": "list", "verify": "string",
         "charter.dir": "path", "gate.ntfy_url": "string", "gate.ntfy_topic": "secret",
         "gate.wall": "integer", "gate.load_ceiling": "number", "gate.max_running": "integer",
         "ceilings.context": "integer", "ceilings.turns": "integer"}

# R9: one sentence each, under 100 characters; a pattern's `*` is one segment or more.
SUMMARIES = {
    "profile": "The role this session runs as; it fills every field no layer above it sets.",
    "model": "The model the main thread starts on.",
    "effort": "The reasoning effort the session starts at.",
    "permission_mode": "What Claude Code may do without asking, as `start` sets it for the "
                       "session.",
    "posture": "What the budget guard does at a ceiling: off, signal, ask or deny.",
    "lane": "Where the work runs: the seat, the local model for subagents, or the local model "
            "alone.",
    "ceilings.context": "The context, in tokens, this sitting is metered against.",
    "ceilings.turns": "The turns this sitting is metered against.",
    "checkpoint_at": "The share of a ceiling at which the CHECKPOINT line is printed.",
    "tiers.*.model": "The model a subagent in this role runs on.",
    "tiers.*.effort": "The effort a subagent in this role runs at.",
    "charter.dir": "The folder, under the repo, that holds a sitting's charters.",
    "charter.required": "Whether a session is told when no charter is open today.",
    "pacing.meter_line_minutes": "The minutes between the meter's lines while the zone is clear; "
                                 "0 prints one at every prompt.",
    "gate.wall": "The seconds a gate job may run before it is cut.",
    "gate.max_running": "How many gate jobs may run at once on this machine.",
    "gate.load_ceiling": "The load average above which a queued gate job waits.",
    "gate.ntfy_topic": "The topic a gate job's result is sent to as a notice.",
    # written for this row from the code that reads each key
    "tools": "The tools `start` lets the session use; null leaves Claude Code's own set.",
    "plugins": "The plugins `start` loads into the session.",
    "notes": "The words `start` adds to the session's system prompt.",
    "builders.model": "Not read by this tool: the model a sitting's builders are meant to run on.",
    "builders.max_concurrent": "Not read by this tool: how many builders a sitting may run at "
                               "once.",
    "push": "Read by the relay's guard: `never`, or the owner's quoted words that allow a push.",
    "device": "Read by the relay's guard: `never`, or the owner's quoted words that allow a device "
              "write.",
    "verify": "Not read by this tool: the gate command a repo's sittings verify their work with.",
    "respawn.cap": "The restarts in 24 hours after which `run` stops respawning the sitting.",
    "respawn.floor": "The seconds a sitting must have run before `run` respawns it.",
    "respawn.settle": "The seconds `run` waits after a turn ends before it respawns the sitting.",
    "priority.enabled": "Whether the session is given the priority levels S1 to S4.",
    "priority.levels.*": "The words the session is given for this priority level.",
    "pacing.enabled": "Whether the session is given the pacing rules.",
    "pacing.fallback": "The seconds the session waits on a pending subagent before it wakes on "
                       "its own.",
    "pacing.waiting": "The wakes in a row with nothing changed after which a wait is STALLED.",
    # row ss2, R5: kept, since `admission.mix` is advice on the week's spend and decides no fit
    "admission.*": "Read by the admission module; `agentik session rules` says how it binds.",
    # row ss2, R5: kept, since `reconcile.record` names where its records are written
    "reconcile.*": "Read by the reconciler's detectors each time they run.",
    "gate.ntfy_url": "The server a gate job's notice is sent to.",
}


def summary(key: str) -> str:
    if key in SUMMARIES:
        return SUMMARIES[key]
    for pat, text in SUMMARIES.items():
        if "*" in pat and fnmatch.fnmatchcase(key, pat):
            return text
    return "Read from the resolved configuration by the session's own code."


# ---- the envelope (the contract's §2) --------------------------------------------------------

def envelope(read: str, d):
    """`schema` and `ok` first, every other key as it was; a non-object is left as it is."""
    if not isinstance(d, dict):
        return d
    rest = {k: v for k, v in d.items() if k not in ("schema", "ok")}
    return {"schema": d.get("schema") or SCHEMAS[read], "ok": True, **rest}


def dumps(d) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False).replace("\x1b", "\\u001b")


# ---- describe --json (the contract's §3) ---------------------------------------------------

def describe(parser) -> dict:
    """R3: `parser` is the CLI's own; its first-level verbs in help's order, `hook` left out."""
    act = parser._subparsers._group_actions[0]
    helps = {a.dest: a.help for a in act._choices_actions}
    verbs = [{"name": n, "summary": helps.get(n) or "", "top": False}
             for n in act.choices if n != "hook"]
    needs = [{"name": "claude", "kind": "program", "optional": False,
              "why": "starts the sessions this tool configures, meters and checks"},
             {"name": "git", "kind": "program", "optional": False,
              "why": "reads the cwd's repo for its config, charters and commits"}]
    needs += [{"name": f"{s['name']}@{s['marketplace']}", "kind": "plugin", "why": s["adds"],
               "optional": True} for s in doctor.SIBLINGS]
    reads = [{"kind": "config", "name": "config", "argv": ["describe", "config", "--json"]},
             {"kind": "doctor", "name": "doctor", "argv": ["doctor", "--json"]},
             {"kind": "status", "name": "meter", "argv": ["status", "--json"]},
             {"kind": "status", "name": "gate", "argv": ["gate", "status", "--json"]},
             {"kind": "status", "name": "unattended", "argv": ["unattended", "status", "--json"]}]
    return {"schema": "agentik.describe/1", "ok": True, "tool": TOOL, "version": SEMVER,
            "summary": SUMMARY, "repo": REPO, "plugin": PLUGIN, "needs": needs,
            "verbs": verbs, "reads": reads}


# ---- where a key stands in a file ----------------------------------------------------------

def _line(text, path) -> int | None:
    """The 1-based line `path`'s last key stands on in `text`, in the strict subset: mappings
    nested by indentation, and a one-line flow map holding the last key. None when not found."""
    if text is None or not path:
        return None
    want, floor, child = 0, -1, None
    for ln, raw in enumerate(text.splitlines(), 1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        ind = len(body) - len(body.lstrip(" "))
        if ind <= floor:
            return None                          # out of the parent's block
        if child is None:
            child = ind
        if ind != child:
            continue
        m = _KEY.match(body.strip())
        if not m or m.group(1) != path[want]:
            continue
        rest = (m.group(2) or "").strip()
        if want == len(path) - 1:
            return ln
        if rest.startswith("{") and want == len(path) - 2:
            try:
                flow = _value(rest, ln)
            except ValueError:
                return None
            return ln if isinstance(flow, dict) and path[-1] in flow else None
        if rest:
            return None
        want, floor, child = want + 1, ind, None
    return None


def _get(doc, path):
    """(found, value) of `path` in nested mappings."""
    for k in path:
        if not isinstance(doc, dict) or k not in doc:
            return False, None
        doc = doc[k]
    return True, doc


def _leaves(d, pre=()):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _leaves(v, pre + (k,))
        else:
            yield pre + (k,)


def _dict(x) -> dict:
    return x if isinstance(x, dict) else {}


# ---- the files, read again for their lines --------------------------------------------------

class _Files:
    def __init__(self, cwd, env, sid, launch, r):
        self.env, self.sid, self.launch, self.r = env, sid, launch, r
        self.shipped = str(resolver.SHIPPED)
        self.user = str(resolver._user_file(env))
        rdir = resolver.repo_dir(cwd)
        self.repo, self.local_file = str(rdir / "config.yaml"), str(rdir / "config.local.yaml")
        self.overlay = (str(resolver.state_dir(env) / "overlays" / f"{sid}.json")
                        if sid else None)
        self.text, self.doc, self.skipped = {}, {}, []    # skipped: leaves _keyable refuses
        for p in (self.shipped, self.user, self.repo, self.local_file):
            try:
                self.text[p] = Path(p).read_text(encoding="utf-8")
                self.doc[p] = _dict(load(self.text[p]))
            except (OSError, ValueError):
                self.text[p], self.doc[p] = None, {}
        # the overlay as `set` keeps it (sessionconfig's reader; resolve has read it already)
        self.ov_raw = _dict(sessionconfig.load_overlay(sid)) if sid else {}
        ov = self.ov_raw
        self.ov = {resolver.OVERLAY_RENAMES.get(k, k): v for k, v in ov.items()
                   if not k.startswith("_")
                   and resolver.OVERLAY_RENAMES.get(k, k) in resolver.SESSION_KEYS}
        self.name = r.provider["profile"]
        sh, us = self.doc[self.shipped], self.doc[self.user]
        self.sd = _dict(sh.get("defaults"))
        self.sp = _dict(_dict(sh.get("profiles")).get(self.name))
        self.ud = _dict(us.get("defaults"))
        self.up = _dict(_dict(us.get("profiles")).get(self.name))
        frontier = _dict(_dict(sh.get("profiles")).get(resolver.DEFAULT_PROFILE))
        self.default = resolver._merge(self.sd, frontier)
        self.frontier = frontier
        self.session = r.sections["session"]
        cls = models.window_class(self.session.get("window"))
        if env.get("CLAUDE_SESSION_HELPER") == "1":
            cls = "200k"
        self.ckey = models.CLASSES[cls]

    def present(self, p) -> bool:
        return bool(p) and Path(p).is_file()

    def layers(self) -> list:
        return [{"name": "default", "path": self.shipped, "present": True, "travels": False},
                {"name": "user-defaults", "path": self.user, "present": self.present(self.user),
                 "travels": True},
                {"name": "profile", "path": self.shipped, "present": True, "travels": False},
                {"name": "user", "path": self.user, "present": self.present(self.user),
                 "travels": True},
                {"name": "repo", "path": self.repo, "present": self.present(self.repo),
                 "travels": False},
                {"name": "local", "path": self.local_file, "present": self.present(self.local_file),
                 "travels": False},
                {"name": "launch", "path": None, "present": bool(self.launch), "travels": False},
                {"name": "session", "path": self.overlay, "present": self.present(self.overlay),
                 "travels": False}]

    def _row(self, layer, value, path, where):
        return (layer, value, path, _line(self.text.get(path), where) if where else None)

    # -- the session section's keys, R4's order --
    def session_rows(self, key: tuple) -> list:
        us, rp, lc = self.doc[self.user], self.doc[self.repo], self.doc[self.local_file]
        docs = [("default", self.sd, self.shipped, ("defaults",)),
                ("user-defaults", self.ud, self.user, ("defaults",)),
                ("profile", self.sp, self.shipped, ("profiles", self.name)),
                ("user", self.up, self.user, ("profiles", self.name)),
                ("repo", _dict(rp.get("session")), self.repo, ("session",)),
                ("local", _dict(lc.get("session")), self.local_file, ("session",))]
        if key == ("profile",):
            return self._profile_rows(us, rp, lc)
        out = []
        for layer, doc, path, pre in docs:
            found, v = _get(doc, key)
            if found:
                out.append(self._row(layer, v, path, pre + key))
        if self.launch:
            found, v = _get(resolver._merge(self.sp, self.up), key)
            if found:
                out.append(("launch", v, None, None))
        found, v = _get(self.ov, key)
        if found:
            out.append(("session", v, self.overlay, None))
        return out

    def _profile_rows(self, us, rp, lc) -> list:
        out = [("default", resolver.DEFAULT_PROFILE, None, None)]
        if isinstance(self.ud.get("profile"), str) and self.ud["profile"]:
            out.append(self._row("user-defaults", self.ud["profile"], self.user,
                                 ("defaults", "profile")))
        for layer, doc, path in (("repo", rp, self.repo), ("local", lc, self.local_file)):
            v = _dict(doc.get("session")).get("profile")
            if v:
                out.append(self._row(layer, v, path, ("session", "profile")))
        if self.launch:
            out.append(("launch", self.launch, None, None))
        return out

    # -- the ceilings, as _window_ceilings orders them for the window that binds --
    def ceiling_rows(self, field: str) -> list:
        k = self.ckey
        keys = ("ceilings",) + ((k,) if k != "ceilings" else ())
        rp, lc = self.doc[self.repo], self.doc[self.local_file]
        out = []
        for layer, doc, path, pre, ks in (
                ("default", self.sd, self.shipped, ("defaults",), (k,)),
                ("profile", self.sp, self.shipped, ("profiles", self.name), (k,)),
                ("user-defaults", self.ud, self.user, ("defaults",), keys),
                ("user", self.up, self.user, ("profiles", self.name), keys),
                ("repo", _dict(rp.get("session")), self.repo, ("session",), keys),
                ("local", _dict(lc.get("session")), self.local_file, ("session",), keys),
                ("session", self.ov, self.overlay, None, keys)):
            got = None
            for ck in ks:
                found, v = _get(doc, (ck, field))
                if found:
                    got = self._row(layer, v, path, pre + (ck, field) if pre else None)
            if got:
                out.append(got)
        if field == "turns" and self.session.get("ceilings_source") == resolver.MAX_TURNS_VAR:
            out.append(("launch", self.session["ceilings"]["turns"], None, None))
        return out

    # -- the tiers, as _tier_layers orders them --
    @staticmethod
    def _tier(tiers, role, field):
        v = _dict(tiers).get(role)
        if isinstance(v, dict) and field in v and resolver._known(field, v[field]):
            return True, v[field], (role, field)
        if isinstance(v, str) and field == "model" and resolver._known(field, v):
            return True, v, (role,)
        return False, None, None

    def _tier_body(self, body, role, field, path, pre):
        """One body's tiers and its old `subagents` (the build model, when its tiers name none)."""
        found, v, sub = self._tier(body.get("tiers"), role, field)
        if found:
            return self._row(None, v, path, pre + ("tiers",) + sub)
        b = _dict(body.get("tiers")).get("build")
        named = isinstance(b, str) or isinstance(b, dict) and b.get("model")
        s = body.get("subagents")
        if role == "build" and field == "model" and isinstance(s, str) and s and not named \
                and resolver._known("model", s):
            return self._row(None, s, path, pre + ("subagents",))
        return None

    def tier_rows(self, role, field, now) -> list:
        us, rp, lc = self.doc[self.user], self.doc[self.repo], self.doc[self.local_file]
        out = []

        def add(layer, *cands):
            got = [c for c in cands if c]
            if got:
                out.append((layer,) + got[-1][1:])
        add("default", self._tier_body({"tiers": self.sd.get("tiers")}, role, field,
                                       self.shipped, ("defaults",)))
        add("user-defaults", self._tier_body(self.ud, role, field, self.user, ("defaults",)))
        add("profile", self._tier_body(self.sp, role, field, self.shipped,
                                       ("profiles", self.name)))
        add("user", self._tier_body(self.up, role, field, self.user, ("profiles", self.name)),
            self._tier_body({"tiers": us.get("tiers")}, role, field, self.user, ()))
        for layer, doc, path in (("repo", rp, self.repo), ("local", lc, self.local_file)):
            s = _dict(doc.get("session"))
            add(layer, self._tier_body({"subagents": s.get("subagents")}, role, field, path,
                                       ("session",)),
                self._tier_body({"tiers": doc.get("tiers")}, role, field, path, ()))
        if self.launch:
            add("launch", *[(None, r[1], None, None) if r else None for r in (
                self._tier_body(self.sp, role, field, None, ()),
                self._tier_body(self.up, role, field, None, ()))])
        table = _dict(self.session.get("tiers"))
        here = _dict(table.get(role)).get(field)
        if self.sid:
            words, _ = tiermod.words(self.ov_raw, now)
            eff = _dict(tiermod.effective(table, self.ov_raw, now).get(role)).get(field)
            sub = self.ov.get("subagents") if role == "build" and field == "model" else None
            if role in words and field == "model" or eff != here or \
                    isinstance(sub, str) and sub and resolver._known("model", sub):
                out.append(("session", eff, self.overlay, None))
        return out

    def tier_value(self, role, field, now):
        table = _dict(self.session.get("tiers"))
        if self.sid:
            table = tiermod.effective(table, self.ov_raw, now)
        return _dict(table.get(role)).get(field)

    def tier_default(self, role, field):
        t = tiermod.merge(tiermod.merge({}, self.sd.get("tiers")),
                          resolver._tier_layer(self.frontier))
        return _dict(t.get(role)).get(field)


# ---- the settings -------------------------------------------------------------------------

def _type(key, value, default) -> str:
    if key in TYPES:
        return TYPES[key]
    for v in (value, default):
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, int):
            return "integer"
        if isinstance(v, float):
            return "number"
        if isinstance(v, list):
            return "list"
    return "string"


def _choices(key, f) -> list | None:
    if key in ("effort",) or fnmatch.fnmatchcase(key, "tiers.*.effort"):
        return list(tiermod.EFFORTS)
    if key == "posture":
        return list(resolver.POSTURES)
    if key == "permission_mode":
        return list(sessionconfig.PERMISSION_MODES)
    if key == "profile":
        return sorted(resolver._profiles(f.doc[f.shipped], f.doc[f.user])[1])
    return None


def _block(path, value) -> str:
    doc: dict = {}
    cur = doc
    for k in path[:-1]:
        cur = cur.setdefault(k, {})
    cur[path[-1]] = value
    return dump(doc).rstrip("\n")


def _change(f, key, path, layer, value) -> tuple[dict, bool]:
    none = {"kind": None, "command": None, "path": None, "block": None, "note": None}
    if key == "profile":
        return {**none, "kind": "launch", "command": "agentik session start VALUE",
                "note": "A repo's own default is `session.profile` in its "
                        ".claude/agentik/config.yaml."}, False
    if key == "posture":
        where = f.overlay or str(resolver.state_dir(f.env) / "overlays")
        return {**none, "kind": "command", "command": "agentik session set posture VALUE",
                "note": f"It holds for this session only, kept in {where}."}, True
    if key.startswith("tiers.") and key.endswith(".model"):
        role = key.split(".")[1]
        return {**none, "kind": "command",
                "command": f"agentik session set tier.{role} VALUE --save",
                "note": "It changes no running session; without --save the word is this "
                        "session's alone."}, False
    file = {"user-defaults": f.user, "user": f.user, "repo": f.repo,
            "local": f.local_file}.get(layer, f.user)
    if key.startswith("gate."):
        file, where = f.user, ("gate",) + path
    elif key.startswith("tiers."):
        where = ("tiers",) + path
    else:
        if path[0] == "ceilings":
            path = (f.ckey,) + path[1:]
        where = (("session",) if file in (f.repo, f.local_file) else ("profiles", f.name)) + path
    note = None
    if key in sessionconfig.IN_SESSION_EQUIVALENT:
        cmd = sessionconfig.IN_SESSION_EQUIVALENT[key].format(value="VALUE")
        note = f"The running session keeps its {key}; `{cmd}` changes it now."
    live = key in LIVE or key.startswith(LIVE_PREFIX)
    return {**none, "kind": "edit", "path": file, "block": _block(where, value),
            "note": note}, live


def _setting(f, key, path, value, default, rows, src_path) -> dict:
    secret = key in SECRETS
    shown = (lambda v: None if v is None else "(set)") if secret else (lambda v: v)
    if rows:
        layer, _, p, line = rows[-1]
        source = {"layer": layer, "path": p, "line": line}
    else:
        layer, source = "default", {"layer": "default", "path": src_path, "line": None}
    change, live = _change(f, key, path, layer, shown(value))      # a secret's block: (set)
    return {"key": key.lower(), "value": shown(value), "default": shown(default),
            "type": _type(key, value, default), "choices": _choices(key, f),
            "summary": summary(key.lower()), "source": source, "change": change, "live": live,
            "values": [{"layer": la, "value": shown(v), "path": p, "line": ln}
                       for la, v, p, ln in rows]}


_SEGMENT = re.compile(r"[a-z0-9_-]+\Z")


def _keyable(path) -> bool:
    """A leaf whose key is of the contract's segments, so no two leaves share a key (review 1,
    R1-F3). `priority.levels` holds S1 to S4 alone (resolve drops the rest): lowered, as before."""
    return path[:2] == ("priority", "levels") or all(
        isinstance(k, str) and _SEGMENT.match(k) for k in path)


def _settings(f) -> list:
    out = []
    s, now = f.session, datetime.now(timezone.utc)
    for k in resolver.SESSION_KEYS:
        if k in NOT_SETTINGS:
            continue
        if k == "ceilings":
            base = resolver._merge(_dict(f.sd.get(f.ckey)), _dict(f.frontier.get(f.ckey)))
            for fld in ("context", "turns"):
                out.append(_setting(f, f"ceilings.{fld}", ("ceilings", fld),
                                    _dict(s.get("ceilings")).get(fld), base.get(fld),
                                    f.ceiling_rows(fld), f.shipped))
            continue
        val, dfl = s.get(k), f.default.get(k)
        if k == "profile":
            dfl = resolver.DEFAULT_PROFILE
        if isinstance(val, dict) or isinstance(dfl, dict):
            paths = list(_leaves(_dict(dfl), (k,)))
            paths += [p for p in _leaves(_dict(val), (k,)) if p not in paths]
        elif k in MAPPINGS:
            continue
        else:
            paths = [(k,)]
        for p in paths:
            if not _keyable(p):
                rows = f.session_rows(p)
                f.skipped.append({"key": ".".join(p), "reason": "unknown", "value": None,
                                  "path": rows[-1][2] if rows else None,
                                  "line": rows[-1][3] if rows else None})
                continue
            v = _get(s, p)[1]
            d = _get(f.default, p)[1] if k != "profile" else dfl
            out.append(_setting(f, ".".join(p), p, v, d, f.session_rows(p),
                                None if k == "profile" else f.shipped))
    for role in tiermod.ROLES:
        for fld in ("model", "effort"):
            out.append(_setting(f, f"tiers.{role}.{fld}", (role, fld), f.tier_value(role, fld, now),
                                f.tier_default(role, fld), f.tier_rows(role, fld, now),
                                f.shipped))
    g = resolver.gate_config(f.env)
    ug = _dict(f.doc[f.user].get("gate"))
    for k in GATE_KEYS:
        rows = []
        if k in resolver.GATE_DEFAULTS:
            rows.append(("default", resolver.GATE_DEFAULTS[k], None, None))
        raw = ug.get(k)
        if k in ug and k in g and g[k] == (raw.strip() if isinstance(raw, str) else raw):
            rows.append(f._row("user", g[k], f.user, ("gate", k)))
        out.append(_setting(f, f"gate.{k}", (k,), g.get(k), resolver.GATE_DEFAULTS.get(k),
                            rows, None))
    return out


def _warnings(f) -> list:
    out, seen = [], set()
    by = {"config.yaml": f.repo, "config.local.yaml": f.local_file, "overlay": f.overlay}
    for u in f.r.unknown:
        where, sep, rest = u.partition(": ")
        if not sep or where == "launch":
            continue
        path, line = by.get(where, where), None
        keys = tuple(rest.split("."))
        if where == "profiles.yaml":
            path = f.user
            for p, pre in ((f.user, ("defaults",)), (f.user, ("profiles", f.name)),
                           (f.shipped, ("defaults",)), (f.shipped, ("profiles", f.name))):
                line = _line(f.text.get(p), pre + keys)
                if line:
                    path = p
                    break
        elif path in f.text:
            line = _line(f.text.get(path), keys)
        elif path != f.overlay:
            continue                    # an origin that is no file of ours: the shipped tree
        row = {"key": rest, "reason": "unknown", "value": None, "path": path, "line": line}
        if (rest, path, line) not in seen:
            seen.add((rest, path, line))
            out.append(row)
    return out + f.skipped


def _sid(env) -> str | None:
    sid = env.get("CLAUDE_CODE_SESSION_ID")
    return sid if sid and len(sid) >= 8 and resolver._SID.match(sid) else None


# Row ss2: the two moved down to the resolver, so every print of its error is scrubbed at the
# raise; the plug's names stay.
withheld = resolver.withheld
scrubbed = resolver.scrubbed


def _guarded(fn, arg, fallback):
    """A path the resolver picks by asking the disk, or its unpicked form when a folder above
    it cannot be searched (review 2, R2-F2)."""
    try:
        return fn(arg)
    except OSError:
        return fallback


def layer_files(cwd, env) -> list:
    """The user, repo and local files, picked as resolve picks them, never raising."""
    home = Path(env.get("HOME") or Path.home())
    user = _guarded(resolver._user_file, env, home / ".claude" / "agentik" / "profiles.yaml")
    rdir = _guarded(resolver.repo_dir, cwd, Path(cwd) / resolver.REPO_DIR)
    return [str(user), str(rdir / "config.yaml"), str(rdir / "config.local.yaml")]


def no_cwd(read: str) -> dict:
    """The envelope's error when the working directory is gone (review 2, R2-F3)."""
    return {"schema": f"agentik.{read}/1", "ok": False, "tool": TOOL,
            "error": {"code": "no_cwd", "message": "the working directory is gone",
                      "remedy": None}}


def _error(msg, files, code=None) -> dict:
    msg = scrubbed(" ".join(str(msg).split()).replace("\x1b", ""))
    named = any(p and p in msg for p in files) or \
        msg.split(":", 1)[0] in ("config.yaml", "config.local.yaml", "profiles.yaml")
    return {"schema": "agentik.config/1", "ok": False, "tool": TOOL,
            "error": {"code": code or ("bad_file" if named else "unresolved"),
                      "message": msg, "remedy": None}}


def _too_deep(paths) -> str | None:
    """The layer file whose nesting the parser cannot follow, read again one by one."""
    for p in paths:
        try:
            raw = Path(p).read_bytes()
            (json.loads if p.endswith(".json") else load)(raw.decode("utf-8", "replace"))
        except RecursionError:
            return p
        except (OSError, ValueError):
            continue
    return None


def _failure(e, paths) -> str:
    """A file that cannot be opened, or nests past the parser, as the file and why."""
    if isinstance(e, OSError):
        return f"{e.filename}: {e.strerror}" if e.filename else str(e)
    if isinstance(e, RecursionError):
        p = _too_deep(paths)
        return f"{p}: nested too deep to read" if p else "a layer file is nested too deep to read"
    return str(e)


def config_read(cwd, env, key: str | None = None) -> tuple[dict, int]:
    """(the config read's object, its exit): 0 when it ran, 2 with the envelope's error."""
    sid, launch = _sid(env), hooks.launch_profile(env)
    try:
        r = resolver.resolve(cwd, sid or "unsaved", env, profile=launch)
        f = _Files(cwd, env, sid, launch, r)
        settings, warnings = _settings(f), _warnings(f)
    except (resolver.ResolveError, OSError, RecursionError) as e:
        state = resolver.state_dir(env)
        files = layer_files(cwd, env) + [str(resolver.SHIPPED), str(state / "overlays")]
        deep = files[:3] + ([str(state / "overlays" / f"{sid}.json")] if sid else [])
        code = None if isinstance(e, resolver.ResolveError) else "bad_file"
        return _error(_failure(e, deep), files, code), 2
    if key is not None:
        settings = [s for s in settings if s["key"] == key.lower()]
    return {"schema": "agentik.config/1", "ok": True, "tool": TOOL, "layers": f.layers(),
            "settings": settings, "warnings": warnings}, 0
