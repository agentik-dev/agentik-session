"""The reconciler's runner (packet R2): the `session.reconcile` key, its cadence and its record.

`check` reads the key a repo resolves (every layer, as `respawn` is read) and returns it
whole with its defaults, or raises ConfigError naming each bad key by its path. `run` calls
R1's `detect` when the newest record is older than `every` hours (or `--force`), writes one
record per date under `record`, and returns (exit, stdout lines, the --json document):
0 clean or not due, 1 a finding flagged (the guide's "a check said no"). The record holds
numbers, ids and the commands that reproduce them, never a charter's or a transcript's text.
Imports: the standard library and the package, relatively (R1's T6).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

KEYS = ("tree", "goal", "window", "every", "detectors", "thresholds", "read", "record")
READ_KEYS = ("every", "floor", "turns", "context")
READ_DEFAULTS = {"every": 168, "floor": 168, "turns": 40, "context": 120000}
DEFAULTS = {"window": 14, "every": 24, "record": "history/reconcile"}
EVERY_FLOOR = 24          # hours: the detectors run at most daily (design/08, fold E4)
EVERY_CEILING = 8760      # hours: and at least yearly (R2's review fold, F4)
READ_FLOOR = 168          # hours: R3's reading pass at most weekly
RECORD_CAP = 4096         # bytes: a record past it is written and its summary says so
_PATH = "session.reconcile"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
_RUN = re.compile(r"^run: ([^;\s]+);", re.M)


class ConfigError(ValueError):
    """The key, or the record's folder, is not usable: the verb's exit 2."""


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def raw(cwd, env):
    """The resolved `session.reconcile` (None when no layer sets it). Raises ConfigError
    when the layers do not resolve."""
    from .. import resolver
    try:
        r = resolver.resolve(cwd, "reconcile", env,
                             profile=env.get("CLAUDE_SESSION_PROFILE") or None, overlay={})
    except resolver.ResolveError as e:
        raise ConfigError(f"the config does not resolve: {e}") from None
    return r.sections["session"].get("reconcile")


def wanted(cwd, env) -> bool:
    """True when the repo sets the key and its layers resolve: the launcher's pass runs.
    `reconcile: false` is off, as an absent key is (R2's review fold, F9)."""
    try:
        v = raw(cwd, env)
        return v is not None and v is not False
    except Exception:                    # noqa: BLE001  (the launcher's guard never raises)
        return False


def _inside(base: Path, rel) -> bool:
    """`rel` is relative and its real path (links resolved, the part that exists) lies inside
    the repo's real path and outside its `.git` (R2's review fold, F2 and F10)."""
    if not isinstance(rel, str) or not rel.strip() or os.path.isabs(rel):
        return False
    norm = os.path.normpath(rel)
    if norm in (".", "..") or norm.startswith(".." + os.sep):
        return False
    root = os.path.realpath(str(base))
    real = os.path.realpath(os.path.join(root, norm))
    if real == root or os.path.commonpath([root, real]) != root:
        return False
    return os.path.relpath(real, root).split(os.sep)[0].lower() != ".git"


def _unwritable(folder: Path, path: Path) -> str | None:
    """Why the record cannot be written at `path` in `folder`, or None; read, never written,
    so a refusal comes before the detectors and before any write (R2's review fold, F5)."""
    if os.path.isdir(str(path)):
        return f"{path} is a folder"
    near = Path(folder)
    while not os.path.lexists(str(near)) and near != near.parent:
        near = near.parent
    if not near.is_dir():
        return f"{near} is not a folder"
    if not os.access(str(near), os.W_OK | os.X_OK):
        return f"{near} cannot be written"
    return None


def check(cwd, env, value=None) -> dict:
    """The key with its defaults, plus `tree_doc` (the tree file's JSON). `value` given is
    checked instead of the resolved key. Raises ConfigError, one line per bad key."""
    from . import THRESHOLDS
    cwd = Path(cwd)
    cfg = raw(cwd, env) if value is None else value
    if cfg is None or cfg is False:
        raise ConfigError(f"{_PATH} is not set (in .claude/agentik/config.yaml or a layer "
                          "over it)")
    if not isinstance(cfg, dict):
        raise ConfigError(f"{_PATH} must be a mapping of {', '.join(KEYS)}")
    # ss2 R1-F2: a key's name is the layer file's text, so it is withheld
    bad = [f"{_PATH}: a key (withheld) is not a key ({', '.join(KEYS)})"] \
        if any(k not in KEYS for k in cfg) else []
    out = {**DEFAULTS, **{k: v for k, v in cfg.items() if k in KEYS}}
    tree, names = out.get("tree"), None
    if tree is None:
        bad.append(f"{_PATH}.tree is required: the repo file with a `repos` list")
    elif not isinstance(tree, str) or not tree.strip():
        bad.append(f"{_PATH}.tree must be a file name, not {tree!r}")
    else:
        try:
            doc = json.loads((cwd / tree).read_text(encoding="utf-8"))
            repos = doc.get("repos") if isinstance(doc, dict) else None
            if not isinstance(repos, list):
                raise ValueError("no `repos` list")
            names = [r.get("name") for r in repos if isinstance(r, dict)]
            out["tree_doc"] = doc
        except (OSError, ValueError) as e:
            bad.append(f"{_PATH}.tree {tree} is not a readable tree file ({e})")
    goal = out.get("goal")
    if goal is not None:
        if not isinstance(goal, list) or not all(isinstance(g, str) for g in goal):
            bad.append(f"{_PATH}.goal must be a list of repo names")
        elif names is not None:
            off = [g for g in goal if g not in names]
            if off:
                bad.append(f"{_PATH}.goal names {', '.join(off)}, not in the tree {tree}")
    if not _int(out["window"]) or out["window"] < 1:
        bad.append(f"{_PATH}.window must be a whole number of days, 1 or more")
    every = out["every"]
    if not _int(every):
        bad.append(f"{_PATH}.every must be a whole number of hours")
    elif not EVERY_FLOOR <= every <= EVERY_CEILING:
        bad.append(f"{_PATH}.every is {every} hours; its floor is {EVERY_FLOOR} and its "
                   f"ceiling {EVERY_CEILING} (detectors at most daily, at least yearly)")
    det = out.get("detectors")
    if det is not None:
        if not isinstance(det, list) or not all(isinstance(d, str) for d in det):
            bad.append(f"{_PATH}.detectors must be a list of detector ids")
        else:
            off = [d for d in det if d not in THRESHOLDS]
            if off:
                bad.append(f"{_PATH}.detectors names {', '.join(off)}, not one of "
                           f"{', '.join(sorted(THRESHOLDS))}")
    th = out.get("thresholds")
    if th is not None:
        if not isinstance(th, dict):
            bad.append(f"{_PATH}.thresholds must be a mapping of detector id to a number")
        else:
            for k, v in th.items():
                if k not in THRESHOLDS:
                    bad.append(f"{_PATH}.thresholds: a key (withheld) is not a detector "
                               f"({', '.join(sorted(THRESHOLDS))})")
                elif not _num(v) or v < 0:          # ss2 N1: the reason, never the value
                    why = "is not a number" if not _num(v) else "is below 0"
                    bad.append(f"{_PATH}.thresholds.{k} {why}; a threshold is a number, "
                               "0 or more")
    rd = out.get("read")
    if rd is not None and not isinstance(rd, dict):
        bad.append(f"{_PATH}.read must be a mapping of {', '.join(READ_KEYS)}")
        rd = {}
    rd = {**READ_DEFAULTS, **(rd or {})}
    for k in list(rd):
        if k not in READ_KEYS:
            bad.append(f"{_PATH}.read: a key (withheld) is not a key ({', '.join(READ_KEYS)})")
        elif not _int(rd[k]) or rd[k] < 1:
            bad.append(f"{_PATH}.read.{k} must be a whole number, 1 or more")
    floor_ok = _int(rd.get("floor")) and _int(rd.get("every"))
    if floor_ok and rd["floor"] < READ_FLOOR:
        bad.append(f"{_PATH}.read.floor is {rd['floor']} hours; its floor is {READ_FLOOR} "
                   "(a reading pass at most weekly)")
    elif floor_ok and rd["every"] < rd["floor"]:
        bad.append(f"{_PATH}.read.every is {rd['every']} hours; it is at least read.floor "
                   f"({rd['floor']})")
    out["read"] = {k: rd[k] for k in READ_KEYS}
    if not _inside(cwd, out["record"]):
        bad.append(f"{_PATH}.record must be a relative folder inside the repo, not "
                   f"{out['record']!r}")
    if bad:
        raise ConfigError("\n".join(bad))
    return out


def _stamp(path: Path):
    """A record's `run:` stamp in epoch seconds; None when it has no line that reads as a
    date (R2's review fold, F4)."""
    try:
        m = _RUN.search(path.read_text(encoding="utf-8", errors="replace"))
        return datetime.fromisoformat(m.group(1)).timestamp() if m else None
    except (OSError, ValueError, OverflowError):
        return None


def last_run(folder, now: float) -> tuple:
    """(epoch seconds or None, path or None, the records ahead): the last run is the newest
    `YYYY-MM-DD.md` by name that is not ahead of `now` (named for a date after now's, or
    stamped after now), with its stamp; None when its stamp does not read, so the run is
    due. A record ahead is left out of the cadence and returned to be named (R2's review
    fold, F3): a forced run is the last run from then on."""
    try:
        days = sorted((p for p in os.listdir(str(folder)) if _DAY.match(p)), reverse=True)
    except OSError:
        return None, None, []
    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d") + ".md"
    ahead = []
    for name in days:
        path = Path(folder) / name
        stamp = _stamp(path)
        if name > today or (stamp is not None and stamp > now):
            ahead.append(path)
            continue
        return stamp, path, ahead
    return None, None, ahead


def _iso(t: float, spec: str) -> str:
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec=spec)


def _n(v) -> str:
    if not _num(v):
        return "n/a"
    return str(v) if isinstance(v, int) else format(v, "g")


def _cell(text) -> str:
    """One table cell in backticks: whitespace folded, each `|` escaped."""
    s = " ".join(str(text).split()).replace("|", "\\|")
    return f"`` {s} ``" if "`" in s else f"`{s}`"


def record_text(findings, cfg, now: float) -> str:
    """The record: numbers, ids and commands alone (design/08 §4, Never)."""
    k = sum(1 for f in findings if f.get("flagged"))
    head = (f"# reconcile {datetime.fromtimestamp(now).strftime('%Y-%m-%d')}\n\n"
            f"run: {_iso(now, 'seconds')}; tree {cfg['tree']}; window {cfg['window']} d; "
            f"every {cfg['every']} h; {k} of {len(findings)} flagged\n\n"
            "| id | value | threshold | flagged | command |\n|---|---|---|---|---|\n")
    rows = "".join(
        f"| {_cell(f.get('id'))} | {_n(f.get('value'))} | {_n(f.get('threshold'))} | "
        f"{'yes' if f.get('flagged') else 'no'} | "
        f"{_cell((f.get('evidence') or {}).get('command', ''))} |\n" for f in findings)
    return head + rows


def run(cwd, env, now: float, force: bool = False, warn=None) -> tuple:
    """(exit, stdout lines, the --json document). Raises ConfigError for the key or a record
    folder that cannot be written, and OSError when the write fails. `warn` takes the one
    line that names the records ahead of now."""
    cwd = Path(cwd)
    cfg = check(cwd, env)
    folder = cwd / cfg["record"]
    last, _, ahead = last_run(folder, now)
    if ahead and warn is not None:
        warn(f"reconcile: left out of the cadence, stamped after now: "
             f"{', '.join(str(p) for p in ahead)}")
    due_at = None if last is None else last + cfg["every"] * 3600
    if not force and due_at is not None and now < due_at:
        nxt = _iso(due_at, "minutes")
        return 0, [f"not due until {nxt}"], {"due": False, "last": _iso(last, "seconds"),
                                              "next": nxt}
    path = folder / (datetime.fromtimestamp(now).strftime("%Y-%m-%d") + ".md")
    why = _unwritable(folder, path)
    if why is not None:
        raise ConfigError(f"{_PATH}.record {cfg['record']} cannot hold a record: {why}")
    from .. import reconcile as lib      # read at call time: R1's contract alone
    home = env.get("HOME") or os.path.expanduser("~")
    roots = {"hq": str(cwd), "repos": str(cwd.parent),
             "projects": str(Path(home) / ".claude" / "projects")}
    findings = lib.detect(cfg["tree_doc"], cfg["window"], now, roots, goal=cfg.get("goal"),
                          thresholds=cfg.get("thresholds"), detectors=cfg.get("detectors"))
    text = record_text(findings, cfg, now)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".{path.name}.{os.getpid()}.tmp"
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()
    flagged = [f for f in findings if f.get("flagged")]
    size = len(text.encode("utf-8"))
    over = f" ({size} B, over {RECORD_CAP})" if size > RECORD_CAP else ""
    lines = [f"flagged {f['id']}: {_n(f.get('value'))} >= {_n(f.get('threshold'))}"
             for f in flagged]
    lines.append(f"reconcile: {len(flagged)} of {len(findings)} flagged; record {path}{over}")
    doc = {"due": True, "record": str(path), "flagged": len(flagged), "findings": findings}
    return (1 if flagged else 0), lines, doc
