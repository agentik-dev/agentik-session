"""Claude Code hook handlers.

Budget is a SIGNAL by default: as the sitting's budget fills, the useful
response is to checkpoint more often so the session is always in a
handoff-ready state, not to block work. Only the "ask" and "deny" postures
interrupt anything, and a config opts into those deliberately.

The zone's input is `used_pct`, a share of the sitting's own ceilings, read
from the session's `meter.json` (the PostToolUse hook writes it). With no meter
the zone is `unknown` and every handler stays silent about budget.

Hook output contract (from the CLI's own documentation):
    {"systemMessage": ..., "continue": bool, "stopReason": ...,
     "hookSpecificOutput": {"hookEventName": ..., "additionalContext": ...,
                            "permissionDecision": "allow"|"deny"|"ask",
                            "permissionDecisionReason": ...}}
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import (budget, charter, ledger, meter, policystore, resolver, rules, sessionconfig,
               store)
from .budget import CLEAR, EXHAUSTED, RESERVE, UNKNOWN, WINDDOWN

SPAWNING_TOOLS = {"Agent", "Task", "Workflow"}

_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]")
_WSRC = re.compile(r"[^A-Za-z0-9_.:\[\]-]")       # a window's source keeps `[1m]`


def _token(text: object, limit: int = 64) -> str:
    """Reduce untrusted text to an identifier-shaped token."""
    return _TOKEN.sub("", str(text or ""))[:limit] or "?"


COUNTER = "_prompts_since_checkpoint"
LAST_CHECKPOINT = "_last_checkpoint_at"


_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")      # \Z: a trailing newline never passes
MAX_OUT = 400
CHECKPOINT_EVERY = 10
EXIT_RULE = ("EXIT: land the act in flight at a checkpoint, then exit; "
             "respawn, never compact")

# The respawn's files under `sessions/<sid>/` (respawn-r1 §3.2, §3.3): the verb writes the
# marker; the hooks write the main thread's stamps, a helper's stamp and the confirmation.
CHAIN_VAR = "CLAUDE_SESSION_CHAIN"
CHAIN_RE = re.compile(r"^(?!\.+\Z)[A-Za-z0-9._-]{1,64}\Z")    # a file name: never . or ..
MARKER = "respawn.json"
CONFIRMED = "respawn-main.json"
ACTIVITY = "activity.json"
TURN_ENDED = "turn-ended.json"
HELPER_ACTIVITY = "helper-activity.json"
CALLS = "calls"         # a helper's open tool calls, one file per `tool_use_id` (S20 ruling 2)


def _session_dir(session_id, env, fallback=True) -> Path | None:
    """The session's state directory; the id from stdin, else (for the CLI and
    the tests) $CLAUDE_CODE_SESSION_ID. An id that is not id-shaped: None."""
    sid = session_id or (env.get("CLAUDE_CODE_SESSION_ID") if fallback else None)
    if not sid or not _SID.match(str(sid)):
        return None
    return resolver.session_dir(resolver.state_dir(env), str(sid))


def _meter(session_id=None, env=None) -> dict | None:
    sdir = _session_dir(session_id, os.environ if env is None else env)
    return meter.load(sdir) if sdir else None


def used_pct(session_id=None, env=None) -> float | None:
    """The sitting's used share of its ceilings, max(pct_context, pct_turns),
    from the session's meter.json. No meter yet: None."""
    m = _meter(session_id, env)
    try:
        return max(float(m["pct_context"]), float(m["pct_turns"]))
    except (TypeError, KeyError, ValueError):
        return None


def _policy(cfg):
    return budget.effective_policy(cfg.reserve_pct, policystore.load_policy())


def state(session_id=None, env=None):
    """(effective config, zone). `posture` and `checkpoint` come from the
    session's resolved.json (the id from stdin, else $CLAUDE_CODE_SESSION_ID)
    when it holds them, else from the stored config. Never raises."""
    env = os.environ if env is None else env
    cfg, _ = sessionconfig.effective()
    sdir = _session_dir(session_id, env)
    s = (_load_json(sdir / "resolved.json").get("session") or {}) if sdir else {}
    if not isinstance(s, dict):
        s = {}
    if s.get("posture") in resolver.POSTURES:
        cfg = replace(cfg, posture=s["posture"], name=_token(s.get("profile") or cfg.name))
    if isinstance(s.get("checkpoint"), dict):
        cfg = replace(cfg, checkpoint=dict(s["checkpoint"]))
    return cfg, budget.zone_for(used_pct(session_id, env), _policy(cfg))


def _budget_line(zone: str) -> str:
    return f"Sitting budget: '{zone}' zone."


def _wrap_up(zone: str) -> str:
    return (
        _budget_line(zone) + " The remainder is the wrap-up reserve.\n"
        "Bring the session to a clean stopping point: finish or safely park what "
        "is in flight, commit it, and write the handoff."
    )


def _stamp(payload: dict, env, name: str, body: dict) -> None:
    """One stamp under `sessions/<sid>/`, keyed on the payload's `session_id` only, never
    the environment's (respawn-r1 §3.3). Blind to the posture; a failed write is swallowed,
    so a stamp never changes a hook's output."""
    try:
        sdir = _session_dir(payload.get("session_id"), env, fallback=False)
        if sdir is not None:
            store._write_private(sdir / name, json.dumps(body))
    except Exception:                                   # noqa: BLE001
        pass


def _tool_stamp(payload: dict, env, event: str) -> None:
    """A tool call's stamp: the main thread's `activity.json`, or a helper's (agent_id)
    `helper-activity.json` only (respawn-r1 ruling 6). PreToolUse writes either; a
    helper's PostToolUse writes its stamp and nothing else."""
    tool = payload.get("tool_name")
    name = HELPER_ACTIVITY if payload.get("agent_id") else ACTIVITY
    _stamp(payload, env, name, {"event": event, "tool": _token(tool) if tool else None,
                                "at": time.time()})


def _call(payload: dict, env) -> Path | None:
    """`sessions/<sid>/calls/<tool_use_id>` for a helper's (agent_id) payload whose id is
    id-shaped; None for the main thread or any other id."""
    tid = payload.get("tool_use_id")
    if not payload.get("agent_id") or not isinstance(tid, str) or not _SID.match(tid):
        return None
    sdir = _session_dir(payload.get("session_id"), env, fallback=False)
    return None if sdir is None else sdir / CALLS / tid


def _open_call(payload: dict, env) -> None:
    """A helper's PreToolUse opens its call; the launcher's ready condition waits while
    any call is open, so a call never closed holds the sitting. Never raises."""
    try:
        p = _call(payload, env)
        if p is not None:
            store._write_private(p, json.dumps({"at": time.time()}))
    except Exception:                                   # noqa: BLE001
        pass


def _close_call(payload: dict, env) -> None:
    """A helper's PostToolUse or PostToolUseFailure closes its call, and its PostToolBatch
    each call the batch lists. Never raises."""
    try:
        p = _call(payload, env)
        if p is not None:
            p.unlink(missing_ok=True)
    except Exception:                                   # noqa: BLE001
        pass


def pre_tool_use(payload: dict, env=None) -> dict:
    """The spawn gate (§2.2): under `ask` or `deny`, a spawn in the late zones
    asks, and under `deny` one in the reserve is refused. A subagent's call: {}.
    Every tool's call is stamped first (respawn-r1 §3.3); the gate acts on spawns only."""
    _tool_stamp(payload, os.environ if env is None else env, "PreToolUse")
    _open_call(payload, os.environ if env is None else env)
    tool = payload.get("tool_name") or ""
    if tool not in SPAWNING_TOOLS or payload.get("agent_id"):
        return {}
    cfg, zone = state(payload.get("session_id"), env)
    if cfg.posture in ("off", "signal"):
        return {}                    # signalling happens on the prompt, not here
    if zone not in (WINDDOWN, RESERVE, EXHAUSTED):
        return {}

    if cfg.posture == "deny" and zone in (RESERVE, EXHAUSTED):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": _wrap_up(zone),
            },
            "systemMessage": (
                f"agentik-session [{cfg.name}]: blocked a {tool} spawn — "
                "the rest is reserved for wrapping up."),
        }

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                _budget_line(zone) + f" Spawning {tool} now may not leave "
                "enough budget to finish and hand off cleanly. Consider a "
                "smaller fan-out."),
        }
    }


def _admission_line() -> str | None:
    """admission's band line from band.json (packet S27b ruling 4), display only; None with
    no file, an unreadable one, or any failure. Imported here: admission imports this module."""
    try:
        from . import admission
        b = admission.read_band(os.environ)
        return admission.band_line(b) if b is not None else None
    except Exception:  # noqa: BLE001 - the line never breaks the prompt hook
        return None


def user_prompt_submit(payload: dict) -> dict:
    """Budget context, and the checkpoint nudge that is the real mechanism."""
    sid = payload.get("session_id")
    if not payload.get("agent_id"):                     # before the posture (respawn-r1 §3.3)
        _stamp(payload, os.environ, ACTIVITY,
               {"event": "UserPromptSubmit", "tool": None, "at": time.time()})
    cfg, zone = state(sid)
    if cfg.posture == "off":
        return {}

    ov = sessionconfig.load_overlay()
    count = int(ov.get(COUNTER) or 0) + 1
    sessionconfig.save_overlay({COUNTER: count})

    cadence = (cfg.checkpoint or {}).get(zone, 0)
    bits: list[str] = []

    m = _meter(sid)
    if m:
        bits.append(f"session: {m.get('pct_context')}% context, "
                    f"{m.get('pct_turns')}% turns, zone {zone}")

    if zone in (RESERVE, EXHAUSTED):
        bits.append(_wrap_up(zone))
    elif zone not in (CLEAR, UNKNOWN):
        bits.append(_budget_line(zone))

    band = _admission_line()
    if band:
        bits.append(band)

    if cadence and count >= cadence:
        bits.append(
            f"{count} prompts since the last checkpoint (cadence is {cadence} in "
            f"the '{zone}' zone). Commit or durably record what is done, then "
            "run `agentik-session checkpoint` — so this session can be handed off "
            "at any moment rather than only when it is convenient.")

    if not bits:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": "\n\n".join(bits)}}


HELPER_PROFILE = "builder"


def launch_profile(env) -> str | None:
    """The profile `agentik session start` exported into this session, if any.

    A helper a sitting spawns (the helper rule's `CLAUDE_SESSION_HELPER=1`) inherits
    the sitting's `CLAUDE_SESSION_PROFILE`; it resolves as `builder`, never as the
    inherited role, so an orchestrator's 1M ceilings stay the orchestrator's (F1).
    """
    if env.get("CLAUDE_SESSION_HELPER") == "1":
        return HELPER_PROFILE
    return env.get("CLAUDE_SESSION_PROFILE") or env.get("CLAUDE_SESSION_CONFIG") or None


def session_start(payload: dict, env=None) -> dict:
    """Resolve every layer for this session and write resolved.json (§2.3).

    Every `session_start_reason` lands here. On any failure: nothing written,
    one line on stderr, `{}` returned; the hook never breaks a session.

    The session model is the payload's `model`; under `claude -p` the payload has
    none (a blank one is none), and the launcher's `CLAUDE_SESSION_MODEL` (the spawn
    line's `--model`, agentik-relay AR74) names it (S28). A helper
    (`CLAUDE_SESSION_HELPER=1`) inherits its sitting's env but runs its own
    `claude -p` line: it never reads the variable.
    """
    env = os.environ if env is None else env
    try:
        sid = payload.get("session_id")
        cwd = payload.get("cwd") or env.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        model, source = payload.get("model"), "payload"
        if not (isinstance(model, str) and model.strip()):
            raw = env.get("CLAUDE_SESSION_MODEL")
            helper = env.get("CLAUDE_SESSION_HELPER") == "1"
            model = raw.strip() if isinstance(raw, str) and not helper else ""
            model, source = (model, "CLAUDE_SESSION_MODEL") if model else (None, None)
        r = resolver.resolve(cwd, sid, env, profile=launch_profile(env),
                             transcript_path=payload.get("transcript_path"),
                             session_model=model, session_model_source=source)
        path = resolver.write(r, resolver.state_dir(env))
        resolver.save_request(path.parent, cwd, launch_profile(env),
                              payload.get("transcript_path"), model, source)
    except Exception as e:                              # noqa: BLE001
        print(f"agentik-session: SessionStart resolved nothing: {e}", file=sys.stderr)
        return {}
    s = r.sections["session"]
    c = s["ceilings"]
    src = s.get("ceilings_source")
    capped = f" ({src})" if src and src != "profile" else ""
    line = (f"agentik-session: profile '{_token(s['profile'])}', ceilings "
            f"{c['context']} context / {c['turns']} turns{capped} on a {s['window']} "
            f"window ({_WSRC.sub('', str(s.get('window_source')))[:64]}), checkpoint at "
            f"{s['checkpoint_at']:.0%}; resolved config at {path}")
    line += rules.clause(s)                 # priority and pacing, at most 320 bytes (S21)
    line += _charter_reminder(s, cwd)
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": line}}


def _charter_reminder(session: dict, cwd) -> str:
    """When `charter.required` and no `<dir>/<today>-*.md` exists under cwd."""
    c = session.get("charter")
    if not isinstance(c, dict) or c.get("required") is not True:
        return ""
    d = _charter({"session": session})
    if any((Path(cwd) / d).glob(f"{charter.today()}-*.md")):
        return ""
    return (f"; charter: none open today under {d}, run "
            f'agentik-session charter open "<goal>"')


def _charter(resolved: dict) -> str:
    c = ((resolved.get("session") or {}).get("charter") or {})
    d = c.get("dir") if isinstance(c, dict) else None
    return re.sub(r"[^A-Za-z0-9_./-]", "", str(d or "history/sittings"))[:80] or "?"


def _signal(m: meter.Meter) -> bool:
    """D13: silent under checkpoint_at; the first crossing, then every tenth
    tool; at or past 100% every tool. Updates m.signal; True to speak."""
    sig = m.signal
    pct = m.used_pct
    if pct >= 100.0:
        sig.update(crossed=True, tools_since=0)
        return True
    if pct < 100.0 * float(m.checkpoint_at):
        return False
    if not sig.get("crossed"):
        sig.update(crossed=True, tools_since=0)
        return True
    sig["tools_since"] = int(sig.get("tools_since") or 0) + 1
    if sig["tools_since"] >= CHECKPOINT_EVERY:
        sig["tools_since"] = 0
        return True
    return False


def _checkpoint_out(m: meter.Meter, charter: str) -> dict:
    c = m.ceilings
    for path in (charter, "?"):
        line = (f"CHECKPOINT: {m.pct_context}% context ({m.context}/{c['context']}), "
                f"{m.pct_turns}% turns ({m.turns}/{c['turns']}); charter {path}; "
                "bring the charter current, commit, then exit")
        if m.used_pct >= 100.0:
            line += "\n" + EXIT_RULE
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": line}}
        if len(json.dumps(out)) <= MAX_OUT:
            return out
    return {}


def _load_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# The checkpoint's spellings _confirm accepts (agentik-r1 packet ruling 9): the tool, the
# front door, and the pre-rename alias, which r2 drops.
RESPAWN_CMDS = ("agentik-session checkpoint", "agentik session checkpoint",
                "claude-session checkpoint")


def _confirm(payload: dict, sdir: Path) -> None:
    """respawn-r1 §3.2 step 5: a main-thread Bash call that ran `agentik-session checkpoint
    --respawn` (or `agentik session checkpoint`, or the pre-rename spelling: RESPAWN_CMDS)
    writes `respawn-main.json` {at, marker_sha256} when the marker was written at
    or after this call's own PreToolUse stamp; none without `activity.json`. Never raises."""
    try:
        cmd = (payload.get("tool_input") or {}).get("command")
        if (payload.get("tool_name") != "Bash" or not isinstance(cmd, str)
                or not any(c in cmd for c in RESPAWN_CMDS) or "--respawn" not in cmd):
            return
        at = _load_json(sdir / ACTIVITY).get("at")
        raw = (sdir / MARKER).read_bytes()
        written = json.loads(raw).get("written")
        if not (_num(at) and _num(written)) or written < at:
            return
        store._write_private(sdir / CONFIRMED, json.dumps(
            {"at": time.time(), "marker_sha256": hashlib.sha256(raw).hexdigest()}))
    except Exception:                                   # noqa: BLE001
        pass


def post_tool_use(payload: dict, env=None) -> dict:
    """The meter (§2.2): fold the transcript's new bytes into meter.json, and
    speak by D13. A subagent's run (agent_id) writes only `helper-activity.json`, never
    the meter, and says nothing. A main-thread call confirms a respawn marker first (§3.2)."""
    env = os.environ if env is None else env
    if payload.get("agent_id"):
        _tool_stamp(payload, env, "PostToolUse")          # the stamp, then the close (B-F1)
        _close_call(payload, env)
        return {}
    sdir = _session_dir(payload.get("session_id"), env, fallback=False)
    if sdir is not None:
        _confirm(payload, sdir)
    tp = payload.get("transcript_path")
    if sdir is None or not tp:
        return {}
    cfg, _ = sessionconfig.effective()
    resolved = _load_json(sdir / "resolved.json")
    st = meter.load_state(sdir)
    m = meter.parse(tp, st, meter.limits_for(sdir, env), _policy(cfg), sdir.name)
    if m is None:
        return {}
    posture = (resolved.get("session") or {}).get("posture")
    off = "off" in (cfg.posture, posture)
    speak = False if off else _signal(m)
    meter.save(sdir, m, st)
    return _checkpoint_out(m, _charter(resolved)) if speak else {}


def post_tool_use_failure(payload: dict, env=None) -> dict:
    """A failed tool call (S20 ruling 2): a helper's closes its open call and stamps
    `helper-activity.json`; the main thread's writes nothing. It says nothing."""
    env = os.environ if env is None else env
    if payload.get("agent_id"):
        _tool_stamp(payload, env, "PostToolUseFailure")   # the stamp, then the close
        _close_call(payload, env)
    return {}


def post_tool_batch(payload: dict, env=None) -> dict:
    """A helper's batch has resolved (the stale call, 2026-10-11): Claude Code fires
    PostToolBatch once every call of a batch has its result, so each call it lists has
    ended, a call another PreToolUse hook blocked included, which gets no Post and no
    Failure. A helper's stamps `helper-activity.json`, then closes each listed call; a call
    still running is in no resolved batch and stays open. The main thread's writes
    nothing. It says nothing."""
    env = os.environ if env is None else env
    calls = payload.get("tool_calls")
    if not payload.get("agent_id") or not isinstance(calls, list):
        return {}
    _tool_stamp(payload, env, "PostToolBatch")          # the stamp, then the close (B-F1)
    for call in calls:
        if isinstance(call, dict):
            _close_call({**payload, "tool_use_id": call.get("tool_use_id")}, env)
    return {}


def session_end(payload: dict, env=None) -> dict:
    """Drop the overlay (adjustments are session-scoped unless promoted), then
    append the session's line to the ledger."""
    env = os.environ if env is None else env
    try:
        sessionconfig.clear_overlay()
        sessionconfig.prune_overlays()
    except Exception:
        pass
    try:
        _ledger_line(payload, env)
    except Exception as e:                              # noqa: BLE001
        print(f"agentik-session: SessionEnd wrote no ledger line: {e}", file=sys.stderr)
    return {}


def _ledger_line(payload: dict, env) -> None:
    if payload.get("agent_id"):
        return
    sdir = _session_dir(payload.get("session_id"), env, fallback=False)
    tp = payload.get("transcript_path")
    if sdir is None or not tp:
        return
    state = resolver.state_dir(env)
    m = meter.parse(tp, meter.load_state(sdir), meter.limits_for(sdir, env),
                    session_id=sdir.name)
    if m is None:
        return
    resolved = _load_json(sdir / "resolved.json")
    profile = ((resolved.get("provider") or {}).get("profile")
               or (resolved.get("session") or {}).get("profile"))
    ledger.append(state, ledger.entry_for(
        m.as_dict(), project=Path(tp).parent.name, profile=profile,
        cwd=payload.get("cwd"), exit_reason=payload.get("reason")))


def stop(payload: dict, env=None) -> dict:
    """The main thread's turn end (respawn-r1 §3.3): `turn-ended.json` {at}. A helper's
    payload (agent_id) writes nothing. It never blocks: dispatch prints nothing for it."""
    if not payload.get("agent_id"):
        _stamp(payload, os.environ if env is None else env, TURN_ENDED, {"at": time.time()})
    return {}


# C1 (mod-r1 §6, §8): a sitting restarts rather than compacts (portfolio entry 17).
# The reason is user-facing: plain words, no ledger cite; the command is in the form
# checkpoint takes (`--respawn` without `--charter FILE` exits 2).
COMPACT_BLOCKED = ("This setup restarts a sitting rather than compacting it: bring the charter "
                   "current and run `agentik-session checkpoint --respawn --charter <this "
                   "sitting's charter>`; a /compact you type yourself still runs.")


def pre_compact(payload: dict, env=None) -> dict:
    """Block an automatic compaction; an owner-typed `/compact` (trigger `manual`) and any
    trigger not known pass with an empty reply, which dispatch prints as nothing (QUIET_PASS).
    It reads and writes no state."""
    if payload.get("trigger") == "auto":
        return {"decision": "block", "reason": COMPACT_BLOCKED}
    return {}


HANDLERS = {
    "pre-tool-use": pre_tool_use,
    "post-tool-use": post_tool_use,
    "user-prompt-submit": user_prompt_submit,
    "session-start": session_start,
    "session-end": session_end,
    "stop": stop,
    "post-tool-use-failure": post_tool_use_failure,
    "post-tool-batch": post_tool_batch,
    "pre-compact": pre_compact,
}
# The plugin's shim passes the event as Claude Code names it.
HANDLERS.update({"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use,
                 "UserPromptSubmit": user_prompt_submit,
                 "SessionStart": session_start, "SessionEnd": session_end, "Stop": stop,
                 "PostToolUseFailure": post_tool_use_failure, "PostToolBatch": post_tool_batch,
                 "PreCompact": pre_compact})
# Stop's stdout is read as a decision, so it gets none: exit 0, empty stdout, always.
SILENT = frozenset({"stop", "Stop"})
# A passing PreCompact's raw stdout becomes the compaction's custom instructions (claude
# 2.1.296), so its pass prints nothing; its block still prints its decision.
QUIET_PASS = frozenset({"pre-compact", "PreCompact"})


def dispatch(event: str) -> int:
    """Read the payload on stdin, print JSON on stdout.

    Always exits 0 with valid JSON: a hook that crashes or stalls blocks the
    tool call it was inspecting, and a budget advisor is never worth breaking a
    session over. Stop (SILENT) exits 0 with nothing on stdout, even when it fails;
    PreCompact (QUIET_PASS) prints only a block, and nothing when it passes or fails.
    """
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:            # a bad encoding, bad JSON, a payload too deep to parse
        payload = {}
    try:
        out = HANDLERS[event](payload)
    except Exception:
        out = {}
    if event in SILENT or (event in QUIET_PASS and not out):
        return 0
    print(json.dumps(out or {}))
    return 0
