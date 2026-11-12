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
import math
import os
import re
import stat
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import (budget, charter, gate, harness, install, ledger, meter, policystore, resolver, rules,
               sessionconfig, store, workflowguard)
from .budget import CLEAR, EXHAUSTED, RESERVE, UNKNOWN, WINDDOWN

SPAWNING_TOOLS = {"Agent", "Task", "Workflow"}

# Packet n33 R6, as the review folded it (fail-closed, linear): the rule reads no flags. In a
# helper's command, a launcher name (a path to bin/agentik-session and `-m claude_session` too)
# followed on the same logical line by the word `charter` is denied unless the word right after
# that `charter` is a verb that only reads; every `charter` after the launcher is read. Quotes
# and backslash-newlines are dropped first (a lone backslash too: it quotes the next byte), so
# a quoted or continued spelling reads as the plain one. Each regex has one repetition at most
# and none nests, so the pass is linear in the command's length. A quoted mention that names
# the launcher is denied too, and the helper rewords it.
CHARTER_READS = ("check",)          # `charter`'s verbs that write nothing: never open, never close
_LAUNCHER = re.compile(r"(?<![\w-])(?:agentik(?:-|\s+)session|claude[-_]session)(?![\w-])")
_CHARTER_WORD = re.compile(r"(?<![\w-])charter(?![\w.-])")
_CHARTER_READ = re.compile(r"[ \t]+(?:" + "|".join(CHARTER_READS) + r")(?![\w.-])")


class _HelperCharter:
    """The rule, with a compiled pattern's `search`: the first `charter` it denies (a match in
    the plain text), else None."""

    @staticmethod
    def plain(cmd: str) -> str:
        return cmd.replace("\\\n", "").replace("'", "").replace('"', "").replace("\\", "")

    def search(self, cmd: str):
        for line in self.plain(cmd).split("\n"):
            launcher = _LAUNCHER.search(line)
            if launcher is None:
                continue
            for word in _CHARTER_WORD.finditer(line, launcher.end()):
                if _CHARTER_READ.match(line, word.end()) is None:
                    return word
        return None


HELPER_CHARTER = _HelperCharter()
HELPER_CHARTER_DENY = (
    "agentik-session: a helper's charter open or close would take or write its sitting's "
    "record (a helper's Bash carries its parent's session id). Write your charter by hand "
    "(a helper's one charter call is `agentik-session charter check <file>`, the verb first), "
    "and put a probe's own call to charter open or close in a script file run under a scratch "
    "state home.")

_TOKEN = re.compile(r"[^A-Za-z0-9_.:-]")


def _token(text: object, limit: int = 64) -> str:
    """Reduce untrusted text to an identifier-shaped token."""
    return _TOKEN.sub("", str(text or ""))[:limit] or "?"


COUNTER = "_prompts_since_checkpoint"
LAST_CHECKPOINT = "_last_checkpoint_at"


_SID = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")      # \Z: a trailing newline never passes
MAX_OUT = 640                                   # S33 ruling 4: at most 640
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
LIMITED = "limited.json"     # a turn an API error ended (S34 ruling 5); the band reads it
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


# Packet b1 (D13 as amended 2026-11-11): in the clear zone the percent line comes on a
# schedule, `session.pacing.meter_line_minutes` (30 by default; 0: every prompt), and from the
# profile's checkpoint_at on every prompt (r1 F1: that share, not the notice zone, whose step is
# the policy's). The stamp is the session's own: {at, shown}. A tool call
# that finds none writes `shown: false`, which starts the clock and says nothing; a prompt that
# finds `shown: false` shows the line, so a session's first prompt with a meter carries it.
METER_LINE = "meter-line.json"


def _now() -> float:
    return time.time()


def _checkpoint_k(m: dict) -> float:
    """The meter's checkpoint_at, in (0, 1]; 0.8 when it is not."""
    try:
        k = float(m.get("checkpoint_at", 0.8))
    except (TypeError, ValueError, OverflowError):
        return 0.8
    return k if 0 < k <= 1 else 0.8


def _past_checkpoint(m: dict) -> bool:
    """r1 F1: is the used share at or past 100 * checkpoint_at? False when it cannot say."""
    try:
        used = max(float(m.get("pct_context")), float(m.get("pct_turns")))
    except (TypeError, ValueError, OverflowError):
        return False
    return used >= 100.0 * _checkpoint_k(m)


def _meter_words(m: dict) -> str:
    """R2: plain words, whole percentages rounded down, nothing else."""
    def pct(v) -> int:
        try:
            return max(0, int(math.floor(float(v))))
        except (TypeError, ValueError, OverflowError):
            return 0
    k = _checkpoint_k(m)
    used = max(pct(m.get("pct_context")), pct(m.get("pct_turns")))
    tense = "came" if used >= round(100 * k) else "comes"
    return (f"session meter: {pct(m.get('pct_context'))}% of context, "
            f"{pct(m.get('pct_turns'))}% of turns; the checkpoint {tense} at {round(100 * k)}%")


def _meter_minutes(sdir: Path | None) -> int:
    """The resolved `session.pacing.meter_line_minutes`, its default when unreadable."""
    s = _load_json(sdir / "resolved.json").get("session") if sdir else None
    return rules.parts(s if isinstance(s, dict) else {})[1]["meter_line_minutes"]


def _meter_due(sdir: Path | None, minutes: int, now: float, prompt: bool) -> bool:
    """R1, the clear zone: is the line due on this event? A tool call that finds no stamp
    starts the clock (a `shown: false` stamp) and is not due."""
    if sdir is None:
        return False
    if minutes == 0:
        return prompt
    st = _load_json(sdir / METER_LINE)
    at = _stamp_at(st.get("at"))
    if at is None:
        if prompt:
            return True
        _meter_stamp(sdir, now, False)
        return False
    if prompt and st.get("shown") is not True:
        return True
    return now - at >= minutes * 60 or now < at


def _stamp_at(v) -> float | None:
    """r1 F3: the stamp's `at` as a finite float; None (no stamp) for anything else, a bool, a
    string, NaN, an infinity or an integer past float range, so the next write replaces it."""
    if not _num(v):
        return None
    try:
        f = float(v)
    except (OverflowError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _meter_stamp(sdir: Path | None, now: float, shown: bool) -> None:
    try:
        if sdir is not None:
            store._write_private(sdir / METER_LINE, json.dumps({"at": now, "shown": shown}))
    except Exception:                                   # noqa: BLE001
        pass


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


def _helper_charter(payload: dict) -> bool:
    """Packet n33 R6: a helper's (agent_id) Bash whose command names this tool's `charter`
    with any word but a read-only verb right after it (HELPER_CHARTER)."""
    if not payload.get("agent_id") or payload.get("tool_name") != "Bash":
        return False
    cmd = (payload.get("tool_input") or {}).get("command")
    return isinstance(cmd, str) and HELPER_CHARTER.search(cmd) is not None


MODEL_REC = "model.json"    # the session's model: SessionStart's, then each PostModelSwitch's
MODEL_UNKNOWN = ("the session's model is not known (no record yet, or a switch its records "
                 "have not both seen: retry after one tool call)")


def _model_stamp(payload: dict, env, model, source: str) -> None:
    if isinstance(model, str) and model.strip() and not payload.get("agent_id"):
        _stamp(payload, env, MODEL_REC, {"model": model.strip()[:128], "from": source,
                                         "at": time.time()})


def post_model_switch(payload: dict, env=None) -> dict:
    """Packet wfg R6: the switch's `to_model` is the session's model from here on."""
    _model_stamp(payload, os.environ if env is None else env, payload.get("to_model"), "switch")
    return {}


def _session_family(payload: dict, env) -> str | None:
    """The session's model family as its records give it: `model.json` and the meter's last
    main-thread line. None for a helper's payload, with no record, or when the two disagree
    (a switch one of them has not seen yet): the caller fails closed on None."""
    if payload.get("agent_id"):
        return None
    sdir = _session_dir(payload.get("session_id"), env, fallback=False)
    if sdir is None:
        return None
    seen = set()
    for name in (MODEL_REC, "meter.json"):
        m = _load_json(sdir / name).get("model")
        if isinstance(m, str) and m:
            seen.add(workflowguard.family(m) or "other")
    return seen.pop() if len(seen) == 1 else None


# Packet b1 R6: a call may name its model or use an agent type that names its own (a caller's
# `model` outranks the agent file); the rule's code already passes a call with none.
WORKFLOW_DENY = ("agentik-session: Workflow denied: this suite runs no workflows. Spawn helpers "
                 "with the Agent tool: name the model, or use an agent type whose definition "
                 "names its own. Do not call Workflow again.")


def _spawn_rule(payload: dict, env) -> str | None:
    """The one line that denies this spawn, else None. Packet wfd: every Workflow call is
    denied, first and unconditionally, its call unread (no script, no path, no name), so the
    rule cannot raise and cannot fail open. Packet wfg R5: a Fable helper on Agent or Task
    starts only under a Fable session, and an unknown session model denies it."""
    tool = payload.get("tool_name")
    if tool == "Workflow":
        return WORKFLOW_DENY
    if tool not in ("Agent", "Task"):
        return None
    ti = payload.get("tool_input")
    ti = ti if isinstance(ti, dict) else {}
    if workflowguard.family(ti.get("model")) != "fable":
        return None
    parent = _session_family(payload, env)
    if parent == "fable":
        return None
    return ("agentik-session: a Fable helper starts only under a Fable session: "
            + (MODEL_UNKNOWN if parent is None else f"this one runs {parent}")
            + ". Name model: 'opus', or use an agent type that names its own model.")


def _deny(reason: str, note: str | None) -> dict:
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                  "permissionDecisionReason": reason}}
    if note:
        out["systemMessage"] = note
    return out


def pre_tool_use(payload: dict, env=None) -> dict:
    """The spawn gate (§2.2): under `ask` or `deny`, a spawn in the late zones
    asks, and under `deny` one in the reserve is refused. A subagent's call: {}.
    Every tool's call is stamped first (respawn-r1 §3.3); the gate acts on spawns only."""
    _tool_stamp(payload, os.environ if env is None else env, "PreToolUse")
    if _helper_charter(payload):     # n33 R6: whatever the posture, and no call opened
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": HELPER_CHARTER_DENY,
            },
            "systemMessage": "agentik-session: denied a helper's charter open or close.",
        }
    tool = payload.get("tool_name") or ""
    if tool in SPAWNING_TOOLS:       # wfd, wfg: any posture, a helper's too, no call opened
        try:
            line = _spawn_rule(payload, os.environ if env is None else env)
        except Exception as e:                          # noqa: BLE001  (wfg r1: R6 too)
            line = (f"agentik-session: {_token(tool)} denied before launch: the guard failed "
                    f"({type(e).__name__}) and fails closed. Retry once; if it repeats, "
                    "report this line.")
        if line == WORKFLOW_DENY:    # wfd: the one line and nothing else
            return _deny(line, None)
        if line:
            return _deny(line, f"agentik-session: denied a {_token(tool)} spawn before launch.")
    _open_call(payload, os.environ if env is None else env)
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
                f"agentik-session [{cfg.name}]: blocked a {tool} spawn: "
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


def _admission_line(sid=None) -> str | None:
    """admission's band line from band.json (packet S27b ruling 4), this session's account's
    (packet S35), display only; None with no file, an unreadable one, or any failure.
    Imported here: admission imports this module."""
    try:
        from . import admission
        b = admission.session_band(admission.read_band(os.environ), sid)
        return admission.band_line(b) if b is not None else None
    except Exception:  # noqa: BLE001 - the line never breaks the prompt hook
        return None


def _fill_part(sid, session, env):
    """`fill <word> to <Ddd HH:MM>` while this session's fill word is in force (packet
    FW1b R6), else None; never raises."""
    try:
        from datetime import datetime, timezone
        from . import fill
        state = resolver.state_dir(env)
        if session is None:                     # the verb's, `rules`' and the mark's seat (F4)
            from . import admission
            session = admission._session_config(env, sid)
        return fill.part(fill.overlay(state, sid), session, env, datetime.now(timezone.utc))
    except Exception:  # noqa: BLE001 - the part never breaks a hook
        return None


def _lifetime(cwd, env, sid=None) -> tuple:
    """`rules.lifetime` from env, the settings under cwd and band.json (packet S30), this
    session's account's (packet S35); display only, as the band line: on any failure,
    unknown. Imported here, as `_admission_line`."""
    try:
        from . import admission
        return rules.lifetime(env, cwd, admission.session_band(admission.read_band(env), sid))
    except Exception:  # noqa: BLE001 - the lifetime never breaks a hook
        return None, rules.UNKNOWN


def _cache_line(payload: dict) -> str | None:
    """The prompt cache's lifetime and what it means for an idle wait (packet S30), when this
    session's pacing is on and something names the lifetime; None otherwise."""
    try:
        env = os.environ
        sdir = _session_dir(payload.get("session_id"), env)
        s = (_load_json(sdir / "resolved.json").get("session") or {}) if sdir else {}
        if not rules.parts(s)[1]["enabled"]:
            return None
        cwd = payload.get("cwd") or env.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        return rules.hint(*_lifetime(cwd, env, payload.get("session_id")))
    except Exception:  # noqa: BLE001 - the line never breaks the prompt hook
        return None


def _gate_lines(payload: dict, env, event: str, out: dict, alone: bool) -> list[str]:
    """S38 ruling 3: the main thread's inbox of gate results, whatever the posture. At most
    three files are taken (an atomic rename into `inbox/read/`), each one line (the `wait`
    line), then `<n> more: ...` when any remain. The lines stop where the output would pass
    MAX_OUT: the whole output on PostToolUse (`alone` False, `out` the handler's), the
    inbox block alone on UserPromptSubmit. A helper's payload (agent_id) takes nothing.
    Never raises: a failure is no lines, and the files wait for the next hook."""
    try:
        sid = payload.get("session_id")
        if payload.get("agent_id") or not isinstance(sid, str) or not _SID.match(sid):
            return []
        base = {} if alone else out

        def fits(text: str) -> bool:
            return len(json.dumps(_with_gate(base, event, [text]))) <= MAX_OUT
        return gate.inbox_take(resolver.state_dir(env), sid, fits=fits)
    except Exception:                                   # noqa: BLE001
        return []


def _with_gate(out: dict, event: str, lines: list[str]) -> dict:
    """The gate's lines before the handler's own context; `out` itself without lines."""
    if not lines:
        return out
    new = json.loads(json.dumps(out)) if out else {}
    hso = new.setdefault("hookSpecificOutput", {})
    ctx = hso.get("additionalContext") or ""
    hso["hookEventName"] = event
    hso["additionalContext"] = "\n".join(lines) + (f"\n\n{ctx}" if ctx else "")
    return new


def user_prompt_submit(payload: dict) -> dict:
    """Budget context, and the checkpoint nudge that is the real mechanism. The gate's
    inbox lines (S38 ruling 3) are taken at each return, the posture-off one included,
    after the body, so a body that raises leaves the files for the next hook (F3)."""
    sid = payload.get("session_id")
    if not payload.get("agent_id"):                     # before the posture (respawn-r1 §3.3)
        _stamp(payload, os.environ, ACTIVITY,
               {"event": "UserPromptSubmit", "tool": None, "at": time.time()})
    cfg, zone = state(sid)
    if cfg.posture == "off":
        return _gate_ups(payload, {})

    ov = sessionconfig.load_overlay()
    count = int(ov.get(COUNTER) or 0) + 1
    sessionconfig.save_overlay({COUNTER: count})

    cadence = (cfg.checkpoint or {}).get(zone, 0)
    bits: list[str] = []

    m = _meter(sid)
    if m:
        sdir = _session_dir(sid, os.environ)
        now = _now()
        if (_past_checkpoint(m)
                or _meter_due(sdir, _meter_minutes(sdir), now, prompt=True)):
            bits.append(_meter_words(m))
            _meter_stamp(sdir, now, True)

    if zone in (RESERVE, EXHAUSTED):
        bits.append(_wrap_up(zone))
    elif zone not in (CLEAR, UNKNOWN):
        bits.append(_budget_line(zone))

    band = _admission_line(sid)
    if band:
        bits.append(band)
    word = (_fill_part(sid, None, os.environ)                    # FW1b R6: only while on
            if isinstance(sid, str) and _SID.match(sid) else None)
    if word:
        bits.append(word.replace("fill ", "fill: ", 1))
    cache = _cache_line(payload)            # the prompt cache's lifetime (S30)
    if cache:
        bits.append(cache)

    if cadence and count >= cadence:
        bits.append(
            f"{count} prompts since the last checkpoint (cadence is {cadence} in "
            f"the '{zone}' zone). Commit or durably record what is done, then "
            "run `agentik-session checkpoint`, so this session can be handed off "
            "at any moment rather than only when it is convenient.")

    if not bits:
        return _gate_ups(payload, {})
    return _gate_ups(payload, {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                      "additionalContext": "\n\n".join(bits)}})


def _gate_ups(payload: dict, out: dict) -> dict:
    """UserPromptSubmit's output with the inbox lines first, the block alone under MAX_OUT."""
    return _with_gate(out, "UserPromptSubmit",
                      _gate_lines(payload, os.environ, "UserPromptSubmit", out, alone=True))


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


def follow_launcher_on(env=None, now=None) -> bool:
    """The shim's switch as `plugin/hooks/run` reads it (design/04 §3): the file a regular file,
    never a link, under 24 h by mtime and never in the future, and the launcher there a file.
    Only HOME is read."""
    env = os.environ if env is None else env
    home = env.get("HOME")
    if not home:
        return False
    try:
        st = os.lstat(os.path.join(home, ".config", "agentik", "hooks-follow-launcher"))
    except OSError:
        return False
    age = (time.time() if now is None else now) - st.st_mtime
    launcher = os.path.join(home, ".local", "bin", "agentik-session")
    return (stat.S_ISREG(st.st_mode) and 0 <= age and math.ceil(age / 60) < 1440   # as `find -mmin -1440`
            and os.path.isfile(launcher) and os.access(launcher, os.X_OK))


FOLLOW_NOTE = ("agentik-session: hooks-follow-launcher is on: hooks run the launcher in "
               "~/.local/bin, not this plugin's pinned code; rm "
               "~/.config/agentik/hooks-follow-launcher once sessions have respawned")


def _follow_said(out: dict, env) -> dict:
    """SessionStart's one line while the switch is on, whichever way the handler ended. With it
    off, the launcher's forward refresh (design/04 §3), whose only word is its failure; with it
    on a hook runs the launcher itself, so there is nothing to refresh from."""
    if follow_launcher_on(env):
        out["systemMessage"] = FOLLOW_NOTE
        return out
    said = install.refresh(env)
    if said:
        out["systemMessage"] = said
    return out


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
    _model_stamp(payload, env, payload.get("model"), "start")
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
        return _follow_said({}, env)
    s = r.sections["session"]
    # Packet b1 R3: no ceiling, window or turn cap reaches the model; the band above the
    # prompt, which only the owner sees, keeps every figure.
    line = (f"agentik-session: profile '{_token(s['profile'])}'; {START_METER}; "
            f"resolved config at {path}")
    line += rules.clause(s, _lifetime(cwd, env, sid)[0],     # at most 320 bytes (S21, S30)
                         fill=_fill_part(sid, s, env))     # its fill part (FW1b R6)
    line += _charter_reminder(s, cwd)
    line += _state_reminder(env, time.time(), sid=sid)     # outside the clause's bound
    return _follow_said({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                "additionalContext": line}}, env)


START_METER = ("the meter shows this session's percent on its schedule and prints CHECKPOINT "
               "when it is time to bring the charter current and hand off")


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


def _state_reminder(env, now, sid=None) -> str:
    """S39 ruling 3 and Amendment 1: under a launcher's chain, in a main-thread sitting
    (state.main_sitting), the state the launcher handed to this session is named, to be
    read first, and a copy that does not match its record is said; "" otherwise, and on
    any error. `now` is kept for the interface: no clock rule since Amendment 1."""
    name = str(env.get(CHAIN_VAR) or "")
    if not CHAIN_RE.match(name):
        return ""
    try:
        from . import chain, state
        if not state.main_sitting(env):
            return ""
        home = chain.home(resolver.state_dir(env), name)
        how, d = state.handed(home, sid or env.get("CLAUDE_CODE_SESSION_ID"))
        if how == "mismatch":
            return f"; state: {home / state.FILE} does not match its record"
        if how != "ok":
            return ""
        at = time.strftime("%H:%M", time.localtime(d["written"]))
    except Exception:                                   # noqa: BLE001
        return ""
    return (f"; state: {home / state.FILE} ({d['bytes']} B from {d['from_session'][:8]}, "
            f"{at}): read it first, then the charter's Next act, nothing else before the "
            "first act")


def _charter(resolved: dict) -> str:
    c = ((resolved.get("session") or {}).get("charter") or {})
    d = c.get("dir") if isinstance(c, dict) else None
    return re.sub(r"[^A-Za-z0-9_./-]", "", str(d or "history/sittings"))[:80] or "?"


def _signal(m: meter.Meter) -> bool:
    """D13: silent under checkpoint_at; the first crossing, then every tenth
    tool; at or past 100% every tool. A share back under checkpoint_at, as a wider
    window gives, clears the latch, so the next crossing speaks at once. Updates
    m.signal; True to speak."""
    sig = m.signal
    pct = m.used_pct
    if pct >= 100.0:
        sig.update(crossed=True, tools_since=0)
        return True
    if pct < 100.0 * float(m.checkpoint_at):
        sig.update(crossed=False, tools_since=0)
        return False
    if not sig.get("crossed"):
        sig.update(crossed=True, tools_since=0)
        return True
    sig["tools_since"] = int(sig.get("tools_since") or 0) + 1
    if sig["tools_since"] >= CHECKPOINT_EVERY:
        sig["tools_since"] = 0
        return True
    return False


# S33: under a launcher (CHAIN_VAR, by CHAIN_RE) the line names the charter this sitting's
# `charter open` recorded in CHARTER_REC, and the marker's verb.
CHARTER_REC = "charter.json"
NO_CHARTER = "<this sitting's charter>"
# Packet b1 R5: the owner tells an intentional wind-down from an early stop by this.
WIND_DOWN = "; tell the owner you are winding down at the meter's line, at {pct}%"
RESPAWN_TAIL = ("bring the charter current with a Next act that opens RESPAWN:, commit, then run "
                "`agentik session checkpoint --respawn --charter {f}` and end the turn; "
                "the launcher restarts this sitting")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_./-]+\Z")    # a path the line may put on a command line


def _charter_file(cwd, sdir: Path, d: str) -> list[str]:
    """S33 rulings 2 and 4: the spellings of the charter this sitting's `charter open`
    recorded (`<sdir>/charter.json` {path}), absolute then relative to cwd, NO_CHARTER last.
    The record is named only when its path is absolute, passes _SAFE_PATH, is a file, and its
    directory is exactly `<cwd>/<d>` (resolved; R1: never a worktree's or a subdirectory's
    charter dir); no directory is listed. A failure reads as none. Never raises."""
    out = []
    try:
        rec = _load_json(sdir / CHARTER_REC).get("path")
        if (isinstance(rec, str) and isinstance(cwd, str) and os.path.isabs(rec)
                and os.path.isabs(cwd) and _SAFE_PATH.match(rec) and os.path.isfile(rec)
                and os.path.realpath(os.path.dirname(rec))
                == os.path.realpath(os.path.join(cwd, d))):
            rel = os.path.relpath(os.path.realpath(rec), os.path.realpath(cwd))
            if rel != os.pardir and not rel.startswith(os.pardir + os.sep):
                out = [rec, rel]
    except Exception:                                   # noqa: BLE001
        out = []
    return [f for f in out if _SAFE_PATH.match(f)] + [NO_CHARTER]


def _checkpoint_out(m: meter.Meter, charter: str, files: list[str] | None = None) -> dict:
    """The pin's line off a launcher (`files` None); under one (S33), a line per spelling
    of the charter file in `files`, the first that fits MAX_OUT."""
    c = m.ceilings
    head = (f"CHECKPOINT: {m.pct_context}% context ({m.context}/{c['context']}), "
            f"{m.pct_turns}% turns ({m.turns}/{c['turns']}); charter ")
    tails = ([f"{f}; " + RESPAWN_TAIL.format(f=f) for f in files] if files is not None else
             [f"{path}; bring the charter current, commit, then exit" for path in (charter, "?")])
    for tail in tails:
        line = head + tail + WIND_DOWN.format(pct=m.used_pct)
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
    """The handler below, then the gate's inbox lines, the whole under MAX_OUT (S38)."""
    env = os.environ if env is None else env
    out = _post_tool_use(payload, env)
    return _with_gate(out, "PostToolUse", _gate_lines(payload, env, "PostToolUse", out, False))


def _post_tool_use(payload: dict, env) -> dict:
    """The meter (§2.2): fold the transcript's new bytes into meter.json, and
    speak by D13. A subagent's run (agent_id) writes only `helper-activity.json`, never
    the meter, and says nothing. A main-thread call confirms a respawn marker first (§3.2)."""
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
    if not speak:
        if off or m.used_pct >= 100.0 * float(m.checkpoint_at):    # r1 F1: D13's, as _signal
            return {}
        now = _now()
        if not _meter_due(sdir, _meter_minutes(sdir), now, prompt=False):
            return {}
        _meter_stamp(sdir, now, True)
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                       "additionalContext": _meter_words(m.as_dict())}}
    chained = CHAIN_RE.match(str(env.get(CHAIN_VAR) or ""))       # F4: cli.py's check
    d = _charter(resolved)
    return _checkpoint_out(m, d, _charter_file(payload.get("cwd"), sdir, d) if chained else None)


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
    limits, limits_at = _measured(lambda: harness.stated_limits(sdir)) or (None, None)
    effort, effort_from = (_measured(lambda: harness.session_effort(payload.get("cwd"), env,
                                                                    m.model))
                           or (None, None))                      # packet b1 R7
    ledger.append(state, ledger.entry_for(
        m.as_dict(), project=Path(tp).parent.name, profile=profile,
        cwd=payload.get("cwd"), exit_reason=payload.get("reason"),
        claude_md_bytes=_measured(lambda: harness.claude_md_bytes(payload.get("cwd"), env)),
        rate_limits=limits, rate_limits_at=limits_at, effort=effort, effort_from=effort_from))


def _measured(read) -> object:
    """A measure on the ledger's row, null on any failure: it never loses the row (S49)."""
    try:
        return read()
    except Exception:                                   # noqa: BLE001
        return None


def stop(payload: dict, env=None) -> dict:
    """The main thread's turn end (respawn-r1 §3.3): `turn-ended.json` {at}. A helper's
    payload (agent_id) writes nothing. It never blocks: dispatch prints nothing for it."""
    if not payload.get("agent_id"):
        _stamp(payload, os.environ if env is None else env, TURN_ENDED, {"at": time.time()})
    return {}


def stop_failure(payload, env=None) -> dict:
    """A turn an API error ended (Claude Code's StopFailure, fired instead of Stop; packet
    S34 ruling 5): `limited.json` {at, error}, the payload's `error` a string cut to 64,
    else null, for the main thread only; a helper's (agent_id) writes nothing. It writes no
    `turn-ended.json`, since no turn ended, and never raises; dispatch prints nothing."""
    try:
        if isinstance(payload, dict) and not payload.get("agent_id"):
            err = payload.get("error")
            _stamp(payload, os.environ if env is None else env, LIMITED,
                   {"at": time.time(), "error": err[:64] if isinstance(err, str) else None})
    except Exception:                                   # noqa: BLE001
        pass
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
    "stop-failure": stop_failure,
    "post-tool-use-failure": post_tool_use_failure,
    "post-tool-batch": post_tool_batch,
    "pre-compact": pre_compact,
    "post-model-switch": post_model_switch,
}
# The plugin's shim passes the event as Claude Code names it.
HANDLERS.update({"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use,
                 "UserPromptSubmit": user_prompt_submit,
                 "SessionStart": session_start, "SessionEnd": session_end, "Stop": stop,
                 "StopFailure": stop_failure,
                 "PostToolUseFailure": post_tool_use_failure, "PostToolBatch": post_tool_batch,
                 "PreCompact": pre_compact, "PostModelSwitch": post_model_switch})
# Stop's stdout is read as a decision, so it gets none: exit 0, empty stdout, always.
SILENT = frozenset({"stop", "Stop", "stop-failure", "StopFailure",
                    "post-model-switch", "PostModelSwitch"})   # StopFailure: fire-and-forget
# A passing PreCompact's raw stdout becomes the compaction's custom instructions: observed
# on claude 2.1.296, not documented. The "Hooks reference" (as of 2026-10-14) sends most
# events' passing stdout to the debug log and does not list PreCompact as an exception.
# Either way, its pass prints nothing; its block still prints its decision.
QUIET_PASS = frozenset({"pre-compact", "PreCompact"})


def dispatch(event: str) -> int:
    """Read the payload on stdin, print JSON on stdout.

    Always exits 0 with valid JSON: a hook that crashes or stalls blocks the
    tool call it was inspecting, and a budget advisor is never worth breaking a
    session over. Stop (SILENT) exits 0 with nothing on stdout, even when it fails;
    PreCompact (QUIET_PASS) prints only a block, and nothing when it passes or fails.
    Every call first bounds hooks.jsonl: one lstat (S49).
    """
    try:
        harness.rotate(resolver.state_dir(os.environ))
    except Exception:            # noqa: BLE001 - a measure never fails a hook
        pass
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
