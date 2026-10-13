"""Turn a named config into a `claude` invocation.

Nothing here writes to settings.json. Every knob is applied through a
per-session flag or environment variable, so a configured session is exactly as
disposable as an unconfigured one -- which is what makes "adjust it for this
session only" the default rather than a feature.

For the local lanes this delegates to the user's own `claude-local`, which
already owns the router preflight, the credential rules (never replace the seat
OAuth) and a measured subagent default. Reimplementing that contract here would
mean maintaining two copies of it.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .sessionconfig import SessionConfig

# Where a plugin name is looked up when the config names one. Checked in order.
PLUGIN_SEARCH = [
    Path.home() / "code",
    Path.home() / ".claude" / "plugins",
]
PLUGIN_ALIASES = {
    "respeak": "claude-code-respeak",
    "agents": "claude-code-agents",
}


class LaunchError(RuntimeError):
    pass


# Env keys a config may never set. Each would redirect the seat's credential,
# swap the interpreter under every hook, or replace the auth entirely.
_ENV_DENY_EXACT = {"PATH", "PYTHONPATH", "PYTHONHOME", "HOME", "USER", "LOGNAME",
                   "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                   "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                   "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CONFIG_DIR",
                   # the launcher's own: a config that set them could reset the depth
                   # guard, lift the turn ceiling (review r6 C2, E5) or name a model the
                   # session does not run, and so its window (S28)
                   "CLAUDE_SESSION_DEPTH", "CLAUDE_SESSION_MAX_TURNS",
                   "CLAUDE_SESSION_MODEL"}
_ENV_DENY_PREFIX = ("DYLD_", "LD_", "ANTHROPIC_", "AWS_", "GOOGLE_")


# review r6 C2: `start` execs claude, whose SessionStart hook is a leaf, but a
# child may itself run `start`. The scrub below hides the parent session, so the
# depth rides in its own variable: the parent's plus one, absent or blank = 0; set
# but unparsable is None, and `start` refuses it (ADV10-10: never fail open).
DEPTH_VAR = "CLAUDE_SESSION_DEPTH"
MAX_DEPTH = 1       # a child at 2 or more needs `start --nested`


def depth(environ) -> int | None:
    """This process's nesting depth: 0 at a terminal, 1 in a started child, None
    when the variable is set but is not a decimal count."""
    raw = (environ.get(DEPTH_VAR) or "").strip()
    if not raw:
        return 0
    return int(raw) if raw.isascii() and raw.isdigit() else None


def _env_forbidden(key: str) -> bool:
    return key in _ENV_DENY_EXACT or key.startswith(_ENV_DENY_PREFIX)


@dataclass
class Launch:
    program: str
    argv: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def shell_preview(self) -> str:
        import shlex
        env = " ".join(f"{k}={shlex.quote(v)}" for k, v in sorted(self.env.items()))
        cmd = " ".join(shlex.quote(a) for a in [self.program, *self.argv])
        return (env + " " if env else "") + cmd


def resolve_plugin(name: str) -> Path | None:
    candidates = [name, PLUGIN_ALIASES.get(name, name)]
    for base in PLUGIN_SEARCH:
        for cand in candidates:
            p = base / cand
            if p.is_dir():
                return p
    p = Path(name).expanduser()
    return p if p.is_dir() else None


def build(cfg: SessionConfig, extra: list[str] | None = None,
          cwd: str | None = None) -> Launch:
    cfg.validate()
    warnings: list[str] = []
    argv: list[str] = []
    env: dict[str, str] = {}

    local_lane = cfg.lane in ("local", "local-only")
    claude_local = shutil.which("claude-local")
    if local_lane and not claude_local:
        raise LaunchError(
            f"config {cfg.name!r} uses the {cfg.lane!r} lane, which needs "
            "`claude-local` on PATH (from claude-code-agents). Install it with "
            "`make install` in that repo, or switch the lane to 'seat'."
        )

    if cfg.model:
        argv += ["--model", cfg.model]
    if cfg.effort:
        argv += ["--effort", cfg.effort]
    if cfg.tools is not None:
        # --tools sets the roster ("" means no tools -- honour it). --allowedTools would only add allow rules and
        # leave everything else on the menu to be denied one call at a time.
        argv += ["--tools", cfg.tools]
    if cfg.permission_mode:
        argv += ["--permission-mode", cfg.permission_mode]
    if cfg.fallback_model:
        argv += ["--fallback-model", cfg.fallback_model]
    if cfg.setting_sources is not None:
        # Dropping the `user` source removes ~/.claude/settings.json -- the
        # only place the break-glass PreToolUse guard and these hooks live.
        srcs = {x.strip() for x in cfg.setting_sources.split(",") if x.strip()}
        if "user" not in srcs:
            raise LaunchError(
                f"config {cfg.name!r} has setting_sources={cfg.setting_sources!r}, "
                "which drops user settings and with them every PreToolUse guard "
                "in ~/.claude/settings.json. Include 'user', or unset it.")
        argv += ["--setting-sources", cfg.setting_sources]
    for d in cfg.add_dirs:
        argv += ["--add-dir", os.path.expanduser(d)]

    for name in cfg.plugins:
        p = resolve_plugin(name)
        if p is None:
            warnings.append(f"plugin {name!r} not found; skipping")
            continue
        # Loaded for this session only, and it outranks nothing else -- a plugin
        # already enabled in settings.json still loads.
        argv += ["--plugin-dir", str(p)]

    if cfg.settings:
        argv += ["--settings", json.dumps(cfg.settings)]

    # The config's notes become session guidance rather than documentation
    # nobody reads. This is also where the budget posture is explained.
    note = _system_note(cfg)
    if note:
        # Passing --append-system-prompt turns snapshotting OFF by default,
        # re-rendering the system prompt every launch and losing the cache
        # prefix. An explicit `on` keeps the snapshot with the note included.
        argv += ["--append-system-prompt", note, "--system-prompt-snapshot", "on"]

    argv += ["--name", cfg.name]

    for k, v in (cfg.env or {}).items():
        if _env_forbidden(k):
            raise LaunchError(
                f"config {cfg.name!r} sets env {k}, which is not allowed: it "
                "would redirect credentials, alter the interpreter, or replace "
                "the seat's auth. Remove it with "
                f"`claude-session set env '{{}}' --save --config {cfg.name}`.")
        env[k] = str(v)
    env["CLAUDE_SESSION_CONFIG"] = cfg.name

    if cfg.subagent_model and not local_lane:
        env["CLAUDE_CODE_SUBAGENT_MODEL"] = cfg.subagent_model

    if local_lane:
        # claude-local owns ANTHROPIC_BASE_URL, the router preflight and the
        # credential rules; it forwards every extra argument to claude verbatim.
        if cfg.subagent_model:
            env["CLAUDE_LOCAL_SUBAGENT"] = cfg.subagent_model
        if cfg.lane == "local-only" and not cfg.model:
            warnings.append(
                "lane 'local-only' without an explicit model leaves the main "
                "thread on the seat; set model to something like local/default")
        program = claude_local
    else:
        program = shutil.which("claude")
        if not program:
            raise LaunchError("`claude` is not on PATH")

    return Launch(program, argv + list(extra or []), env, warnings)


def _system_note(cfg: SessionConfig) -> str:
    bits = [f"This session was started with the '{cfg.name}' configuration"
            + (f": {cfg.description}" if cfg.description else ".")]
    if cfg.notes:
        bits.append(cfg.notes)

    if cfg.posture == "off":
        bits.append(
            "Session budget signalling is off for this configuration; do not "
            "raise budget concerns unless asked.")
    else:
        cadence = cfg.checkpoint or {}
        clear = cadence.get("clear") or 0
        if clear:
            bits.append(
                "Session budget is tracked as a signal, not a limit. As the "
                "sitting's budget fills, checkpoint more often: roughly every "
                f"{clear} prompts while there is plenty left, tightening to "
                f"{cadence.get('wind-down', 6)} once the budget is most of the "
                "way spent. A checkpoint means: commit or otherwise durably "
                "record what is done, so the session can be handed off at any "
                "point. Run `claude-session checkpoint` to mark one.")
        if cfg.posture in ("ask", "deny"):
            bits.append(
                f"Subagent spawning is gated ({cfg.posture}) once the budget is "
                "nearly spent, to keep enough budget for a clean handoff.")
    return "\n\n".join(bits)


# Claude Code marks every tool subprocess with these. An interactive claude that
# inherits them disables transcript persistence and history.jsonl -- which is
# everything `--resume` and session discovery depend on. Claude Code scrubs exactly
# these when it spawns a nested claude; so do `start` and `run` (respawn-r1 §3.1).
SCRUB = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
         "CLAUDE_PID", "CLAUDE_CODE_MESSAGING_TOKEN",
         # a parent's turn limit is its own sitting's, not this child's (r6 E5); so is
         # the model its launcher named (S28): this launch carries its own as --model
         "CLAUDE_SESSION_MAX_TURNS", "CLAUDE_SESSION_MODEL")


def scrub(env) -> dict:
    """A copy of `env` without the SCRUB keys: the one scrub list, for `start` and `run`."""
    return {k: v for k, v in env.items() if k not in SCRUB}


def exec_launch(l: Launch) -> None:
    """Replace this process with claude. No wrapper is left in the tree."""
    merged = scrub(os.environ)
    merged.update(l.env)
    os.execvpe(l.program, [l.program, *l.argv], merged)
