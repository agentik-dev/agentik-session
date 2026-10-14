"""Named session configurations, and the ephemeral overlay on top of them.

Two layers, deliberately:

  Config   a stable, named starting posture you keep and reuse. Persisted.
  Overlay  what you changed in *this* session. Session-scoped, thrown away when
           the session ends, unless you explicitly promote it with --save.

That split is the whole point. "Start frontier, but drop to sonnet subagents for
this bit" should not quietly become your new default for that project.

Everything a config controls is applied at launch through Claude Code's own
per-session flags -- --model, --effort, --tools, --agents, --plugin-dir,
--settings, --setting-sources, --permission-mode -- so nothing here writes to
your settings.json. A session started this way leaves no trace behind it.
"""

from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from . import config as cfgmod
from . import store

CONFIGS_FILE = "configs.json"
OVERLAY_DIR = "overlays"
ACTIVE_FILE = "active.json"

# Knobs that can only take effect when the process starts. Setting one of these
# mid-session records intent for the next launch; it does not lie about having
# changed the running session.
LAUNCH_ONLY = {
    "lane", "model", "effort", "subagent_model", "tools", "permission_mode",
    "plugins", "setting_sources", "add_dirs", "fallback_model", "settings", "env",
}
# Knobs this tool owns, so they are live the moment they are set.
LIVE = {"posture", "reserve_pct", "checkpoint", "notes"}
# Keys the user may set. `name` is the dict key and `description` is prose that
# lands in the system prompt; neither is a knob.
SETTABLE = frozenset(LAUNCH_ONLY | LIVE)

POSTURES = ("off", "signal", "ask", "deny")
PERMISSION_MODES = ("acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
SETTING_SOURCES = {"user", "project", "local"}
CHECKPOINT_ZONES = ("clear", "notice", "wind-down", "reserve", "exhausted")


# In-session equivalents, so `set` can tell you how to apply something now
# instead of only at next launch.
IN_SESSION_EQUIVALENT = {
    "model": "/model {value}",
    "effort": "/effort {value}",
    "permission_mode": "/permission-mode {value}",
}


@dataclass
class SessionConfig:
    name: str
    description: str = ""
    # seat        main thread and subagents on the claude.ai seat
    # local       seat main thread, subagents on the local model
    # local-only  everything on the local model, including the main thread
    lane: str = "seat"
    model: str | None = None
    effort: str | None = None
    subagent_model: str | None = None
    tools: str | None = None
    permission_mode: str | None = None
    plugins: list[str] = field(default_factory=list)
    setting_sources: str | None = None
    add_dirs: list[str] = field(default_factory=list)
    fallback_model: str | None = None
    settings: dict = field(default_factory=dict)
    env: dict = field(default_factory=dict)

    # Budget is a signal here, not a gate. "signal" surfaces state and tightens
    # checkpoint cadence as the window fills; only "ask"/"deny" interrupt.
    posture: str = "signal"
    reserve_pct: float = 8.0
    # Prompts between checkpoints, per budget zone. The point of a reserve is a
    # clean handoff; frequent checkpoints are how you stay ready for one.
    checkpoint: dict = field(default_factory=lambda: {
        "clear": 25, "notice": 12, "wind-down": 6, "reserve": 3, "exhausted": 1})
    notes: str = ""

    def merged(self, overlay: dict) -> "SessionConfig":
        known = {f for f in SessionConfig.__dataclass_fields__} - {"name"}
        patch = {k: v for k, v in (overlay or {}).items() if k in known}
        return replace(self, **patch) if patch else self

    def validate(self) -> None:
        if self.posture not in POSTURES:
            raise ValueError(f"posture must be one of {', '.join(POSTURES)}")
        if not 0 < self.reserve_pct < 100:
            raise ValueError("reserve_pct must be between 0 and 100")
        if self.lane not in ("seat", "local", "local-only"):
            raise ValueError("lane must be seat, local or local-only")
        # A typo here bricks every future `start` of this config with a
        # commander error that names no cause. Validate against the CLI's own
        # choice lists.
        if self.permission_mode is not None and self.permission_mode not in PERMISSION_MODES:
            raise ValueError(
                f"permission_mode must be one of {', '.join(PERMISSION_MODES)}")
        if self.effort is not None and self.effort not in EFFORTS:
            raise ValueError(f"effort must be one of {', '.join(EFFORTS)}")
        if self.setting_sources is not None:
            srcs = {x.strip() for x in self.setting_sources.split(",") if x.strip()}
            bad = srcs - SETTING_SOURCES
            if bad:
                raise ValueError(f"setting_sources: unknown {sorted(bad)}; "
                                 f"allowed: {', '.join(sorted(SETTING_SOURCES))}")
            if "user" not in srcs:
                raise ValueError(
                    "setting_sources must include 'user': dropping it removes "
                    "~/.claude/settings.json and every PreToolUse guard in it")
        for zone, n in (self.checkpoint or {}).items():
            if zone not in CHECKPOINT_ZONES:
                raise ValueError(f"checkpoint: unknown zone {zone!r}; "
                                 f"zones are {', '.join(CHECKPOINT_ZONES)}")
            if not isinstance(n, int) or n < 0:
                raise ValueError(f"checkpoint.{zone} must be a non-negative integer")


DEFAULTS: list[SessionConfig] = [
    SessionConfig(
        name="frontier",
        description="Everything on the seat, full effort. For work that matters.",
        lane="seat", model="opus", effort="xhigh", subagent_model="opus",
        plugins=["respeak"], posture="signal",
        checkpoint={"clear": 25, "notice": 12, "wind-down": 6, "reserve": 3, "exhausted": 1},
        notes="Frontier resources. Spend them on judgement, not bulk retrieval.",
    ),
    SessionConfig(
        name="balanced",
        description="Opus main thread, Sonnet subagents. The everyday default.",
        lane="seat", model="opus", effort="high", subagent_model="sonnet",
        plugins=["respeak"], posture="signal",
    ),
    SessionConfig(
        name="local",
        description="Seat main thread, local subagents (serialised) via `agentik-agents local`.",
        # subagent_model is deliberately unset: the local lane already picks the
        # measured default (sonnet for the broad-tool built-ins, local for
        # Explore). Forcing local/default here would re-introduce the exact
        # case that was measured at ~3 minutes of prefill per turn.
        lane="local", effort="high", posture="signal",
        notes=("Subagent routing is the local lane's: Explore runs on the local "
               "27B, broad-tool agents stay on the seat. The local backend runs "
               "at concurrency 1, so local subagents are SERIALISED -- fanning "
               "out ten of them is ten sequential runs, not a parallel sweep. "
               "Send a small number of small-tool-list agents down for bulk "
               "retrieval and summarisation; keep judgement and any real "
               "parallelism on the seat."),
    ),
    SessionConfig(
        name="local-only",
        description="Main thread AND subagents on the local model. Zero seat spend.",
        lane="local-only", model="local/default", effort="medium",
        subagent_model="local/default", posture="off",
        notes=("Everything is running on the local model, including agents "
               "with broad tool lists that are known to be slow there -- that "
               "is the point of this configuration, not an oversight. Nothing "
               "touches the claude.ai seat, so the usage window is not the "
               "constraint; local latency is. The backend is concurrency 1, "
               "so subagents run one at a time. Prefer short turns and small "
               "tool lists, and expect effort to be capped at medium."),
    ),
    SessionConfig(
        name="scratch",
        description="A fun test project. Local, low ceremony, nothing enforced.",
        lane="local-only", model="local/default", effort="low",
        subagent_model="local/default", posture="off",
        checkpoint={"clear": 0, "notice": 0, "wind-down": 0, "reserve": 0, "exhausted": 0},
    ),
    SessionConfig(
        name="review",
        description="Read-only review posture. Investigates, never edits.",
        lane="seat", model="opus", effort="xhigh", subagent_model="opus",
        tools="Read,Glob,Grep", permission_mode="plan", plugins=["respeak"],
        posture="signal",
        notes="Read-only. Produce findings and a plan; do not edit files.",
    ),
]


# --- persistence -------------------------------------------------------------

def _path(name: str) -> Path:
    return cfgmod.STATE_DIR / name


def load_configs() -> dict[str, SessionConfig]:
    # deepcopy, not replace(): a shallow copy shares checkpoint/plugins/env
    # dicts with the module-level DEFAULTS, so one in-place edit would leak
    # into every config for the rest of the process.
    out = {c.name: copy.deepcopy(c) for c in DEFAULTS}
    p = _path(CONFIGS_FILE)
    if p.exists():
        try:
            for name, d in (json.loads(p.read_text()) or {}).items():
                known = {f for f in SessionConfig.__dataclass_fields__}
                d = {k: v for k, v in (d or {}).items() if k in known}
                d["name"] = name
                out[name] = SessionConfig(**d)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return out


def save_configs(configs: dict[str, SessionConfig]) -> None:
    cfgmod.ensure_dirs()
    store._write_private(
        _path(CONFIGS_FILE),
        json.dumps({n: asdict(c) for n, c in sorted(configs.items())}, indent=2),
    )


# --- the ephemeral overlay ---------------------------------------------------

def session_id() -> str | None:
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    return sid if sid and len(sid) >= 8 else None


def overlay_path(sid: str | None = None) -> Path | None:
    sid = sid or session_id()
    if not sid:
        return None
    return cfgmod.STATE_DIR / OVERLAY_DIR / f"{sid}.json"


def load_overlay(sid: str | None = None) -> dict:
    p = overlay_path(sid)
    if not p or not p.exists():
        return {}
    try:
        d = json.loads(p.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_overlay(patch: dict, sid: str | None = None) -> bool:
    p = overlay_path(sid)
    if not p:
        return False
    cur = load_overlay(sid)
    cur.update(patch)
    cur["_updated_at"] = time.time()
    store._write_private(p, json.dumps(cur, indent=2))
    return True


def clear_overlay(sid: str | None = None) -> bool:
    p = overlay_path(sid)
    if not p or not p.exists():
        return False
    p.unlink(missing_ok=True)
    return True


def prune_overlays(max_age_seconds: int = 7 * 86400) -> int:
    """Overlays are session-scoped, but a session that dies hard leaves one."""
    d = cfgmod.STATE_DIR / OVERLAY_DIR
    if not d.is_dir():
        return 0
    now, n = time.time(), 0
    for p in d.glob("*.json"):
        try:
            if now - p.stat().st_mtime > max_age_seconds:
                p.unlink(missing_ok=True)
                n += 1
        except OSError:
            continue
    return n


# --- which config is this session running? -----------------------------------

def set_active(name: str, sid: str | None = None) -> None:
    """Record the last configuration launched, for humans reading state.

    Deliberately NOT keyed to a session id. `start` execs a child that gets its
    own session id, so stamping the *parent's* id here made a headless launch
    from inside a session claim that session was running the launched config.
    The child learns its configuration from CLAUDE_SESSION_CONFIG, which the
    launcher exports into its environment; that is exact, and this file is only
    a breadcrumb.
    """
    cfgmod.ensure_dirs()
    store._write_private(_path(ACTIVE_FILE), json.dumps(
        {"name": name, "t": time.time()}, indent=2))


def last_started() -> str | None:
    """The last configuration `start` launched. Informational only."""
    p = _path(ACTIVE_FILE)
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text()) or {}).get("name")
    except (OSError, json.JSONDecodeError):
        return None


def get_active() -> str | None:
    """The configuration THIS session is running, or None.

    Only the environment variable can answer this. A session not started
    through `agentik session start` has no active configuration, and saying so
    is more useful than guessing from a file that some other process wrote.
    """
    return os.environ.get("CLAUDE_SESSION_CONFIG") or None


def effective(name: str | None = None) -> tuple[SessionConfig, dict]:
    """The config in force for this session, plus the overlay applied to it."""
    configs = load_configs()
    name = name or get_active() or "balanced"
    base = configs.get(name) or SessionConfig(name=name)
    ov = load_overlay()
    return base.merged(ov), ov
