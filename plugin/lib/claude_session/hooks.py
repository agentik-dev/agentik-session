"""Claude Code hook handlers.

Budget is a SIGNAL by default: as the sitting's budget fills, the useful
response is to checkpoint more often so the session is always in a
handoff-ready state, not to block work. Only the "ask" and "deny" postures
interrupt anything, and a config opts into those deliberately.

The zone's input is `used_pct`, a share of the sitting's own ceilings, read
from the session's `meter.json` (the PostToolUse hook writes it). With no meter
the zone is `unknown` and every handler stays silent about budget.

A main thread's spawn is also told its room (packet nw4-launch-room, room.py): in a session
that keeps the sitting discipline, the points left to the checkpoint once every helper out has
handed back, and whether the new helper fits, as context for the model and in `systemMessage`;
refused only under the posture `deny`.

Hook output contract (from the CLI's own documentation):
    {"systemMessage": ..., "continue": bool, "stopReason": ...,
     "hookSpecificOutput": {"hookEventName": ..., "additionalContext": ...,
                            "permissionDecision": "allow"|"deny"|"ask",
                            "permissionDecisionReason": ...}}
"""

from __future__ import annotations

import argparse
import codecs
import copy
import hashlib
import json
import math
import os
import re
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import (budget, charter, gate, harness, install, instructionguard, instructions, ledger,
               lineguard, meter, policystore, records, resolver, rules, sessionconfig,
               shellreader, store, workflowguard)
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
# Packet hk1 R3: the launcher counts only as a command word: never inside a longer path segment
# or as a folder of a path (a checkout of this tool, `plugin/lib/claude_session/`), and still as
# the last name of a path ending `/bin/<name>` or `/lib/<name>` (the runner the launcher execs),
# or a relative `bin/<name>`, `lib/<name>` or `./<name>` standing as a word. Review 1's F1: the
# module also as `claude_session.cli` or `claude_session.__main__` (`-m`'s, or imported in `-c`),
# each of which runs the CLI, as the pin refused them.
CHARTER_READS = ("check", "show")   # `charter`'s verbs that write nothing: never open, never close
_LAUNCHER = re.compile(r"(?:(?<![\w/.-])(?:bin/|lib/|\./)?|(?<=/bin/)|(?<=/lib/))"
                       r"(?:agentik(?:-|\s+)session|claude[-_]session)(?![\w/.-])"
                       r"|(?<![\w/.-])claude_session\.(?:cli|__main__)(?![\w/.-])")
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
    "(a helper's charter calls are `agentik-session charter check <file>` and `charter show`, "
    "the verb first), "
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
# Packet st1-starter D3: the last line where the profile asks no charter, in plain words.
PLAIN_EXIT = "EXIT: the context is full; start a fresh session"

# The respawn's files under `sessions/<sid>/` (respawn-r1 §3.2, §3.3): the verb writes the
# marker; the hooks write the main thread's stamps, a helper's stamp and the confirmation.
CHAIN_VAR = resolver.CHAIN_VAR                  # one spelling, which the resolver reads too
CHAIN_RE = resolver.CHAIN_RE                    # a file name: never . or ..
MARKER = "respawn.json"
CONFIRMED = "respawn-main.json"
FIRST_MARK = "respawn-first.json"   # nw6b H2: the sitting's first confirmed mark, written once
ACTIVITY = "activity.json"
TURN_ENDED = "turn-ended.json"
LIMITED = "limited.json"     # a turn an API error ended (S34 ruling 5); the band reads it
HELPER_ACTIVITY = "helper-activity.json"
CALLS = "calls"         # a helper's open tool calls, one file per `tool_use_id` (S20 ruling 2)
JOBS = "jobs"           # the main thread's background Bash jobs, one file per `tool_use_id` (rc2)


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


# ---- every open sitting (packet su4, R3) ----------------------------------------------------

OPEN_S = 1800       # open: a hook stamped `activity.json` this recently
SMALL = 65536       # an `activity.json` past this many bytes is no stamp: its folder is passed over
SITTING_KEYS = ("session_id", "zone", "pct_context", "pct_turns", "profile", "at")


def _small_json(path: Path) -> dict | None:
    """A regular file of at most SMALL bytes holding a JSON object, else None; never blocks
    on a FIFO and never raises."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = os.read(fd, SMALL + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    if len(raw) > SMALL:
        return None
    try:
        d = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    return d if isinstance(d, dict) else None


def _pct(v):
    return v if _num(v) and math.isfinite(v) else None


def sittings(env, now: float) -> list:
    """Each session under the state root whose `activity.json` holds an `at` within OPEN_S of
    `now`, newest first: {session_id, zone, pct_context, pct_turns, profile, at}. Only that
    file is read before a folder is known open; then its `meter.json` and `resolved.json`, a
    value they do not give null, `zone` as `state` computes it (null with no meter's
    percents). An `at` up to OPEN_S ahead of now counts (a clock step), one further does not.
    A read: nothing written, no process list, never raises on a folder."""
    base = Path(resolver.state_dir(env)) / "sessions"
    try:
        names = [d.name for d in os.scandir(base) if _SID.match(d.name)]
    except OSError:
        return []
    found = []
    for sid in names:
        a = _small_json(base / sid / ACTIVITY)
        at = _pct(a.get("at")) if a else None
        if at is not None and abs(now - at) <= OPEN_S:
            found.append((at, sid))
    rows = []
    for at, sid in sorted(found, reverse=True):
        m = _load_json(base / sid / "meter.json")
        s = _load_json(base / sid / "resolved.json").get("session")
        pc, pt = _pct(m.get("pct_context")), _pct(m.get("pct_turns"))
        zone = state(sid, env)[1] if pc is not None and pt is not None else None
        p = s.get("profile") if isinstance(s, dict) else None
        rows.append(dict(zip(SITTING_KEYS, (sid, zone, pc, pt,
                                            p if isinstance(p, str) else None, at))))
    return rows


def sittings_lines(rows: list) -> list:
    """One line a row: `<id> <zone> context <c>% turns <t>% profile <p> at <HH:MM>`, `-` for
    a null; `no open sitting` with none."""
    if not rows:
        return ["no open sitting"]

    def v(x, tok=False):
        return "-" if x is None else (_token(x) if tok else str(x))
    return [f"{r['session_id']} {v(r['zone'])} context {v(r['pct_context'])}% "
            f"turns {v(r['pct_turns'])}% profile {v(r['profile'], True)} "
            f"at {time.strftime('%H:%M', time.localtime(r['at']))}" for r in rows]


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
    any call is open, so a call never closed holds the sitting. The file holds `at` and,
    when it is id-shaped, the helper's `agent_id`, which its SubagentStop reads (packet h4
    R2). Never raises."""
    try:
        p = _call(payload, env)
        if p is not None:
            aid = payload.get("agent_id")
            doc = {"at": time.time()}
            if isinstance(aid, str) and _SID.match(aid):
                doc["agent_id"] = aid
            store._write_private(p, json.dumps(doc))
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


# Packet nw3-helper-wait: an agent is never the wait. Under the session's resolved
# `helpers.wait` (`allow` ships; `say`, `refuse`), a helper's (agent_id) Bash is judged by the
# commands `shellreader.commands` reads from its line: a `sleep` whose arguments add to
# LONG_SLEEP seconds or more, and this tool's `gate wait <id>` (or `--chain`) on a job this
# helper already waited on, kept in HELPER_WAITS under the session's folder. A heredoc's body,
# a quoted word and a message are no command, so nothing in them counts. A fault says nothing.
HELPER_WAITS = "helper-waits.json"      # {"waits": [[agent_id, id], ...]}, the newest last
HELPER_WAITS_MAX = 256                  # pairs kept; the oldest go first (well under SMALL)
LONG_SLEEP = 60
HELPER_WAIT_RULE = ("Queue the run with agentik session gate run, write gate | <id> running in "
                    "your record and hand back; the result reaches the coordinator.")
HELPER_WAIT_DENY = "agentik-session: denied a helper's wait."
HELPER_WAIT_SAY = "agentik-session: a helper is never the wait."
CHAIN_WAIT = "--chain"                  # the chain stands for the id; no job id is an option
_TOOL_WORDS = frozenset({"agentik-session", "claude-session", "claude_session"})
_DURATION = re.compile(r"(\d+(?:\.\d*)?|\.\d+)([smhd]?)\Z")
_UNIT = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def _regular_json(path: Path) -> dict:
    """`_load_json` of a regular file only, read whole as the hook's other readers of the
    file read it: a FIFO, a folder or anything else is {}, and the read never blocks."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except (OSError, ValueError):
        return {}
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return {}
        chunks = []
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            chunks.append(b)
        d = json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    finally:
        os.close(fd)
    return d if isinstance(d, dict) else {}


def _helper_wait_value(payload: dict, env) -> str:
    """The resolved `helpers.wait` of the payload's session (a helper runs in its
    coordinator's), `allow` where none is read."""
    sdir = _session_dir(payload.get("session_id"), env, fallback=False)
    s = _regular_json(sdir / "resolved.json").get("session") if sdir else None
    h = s.get("helpers") if isinstance(s, dict) else None
    v = h.get("wait") if isinstance(h, dict) else None
    return v if v in ("say", "refuse") else "allow"


def _sleep_seconds(args: list) -> float | None:
    """GNU sleep's sum of its arguments, None where one is not read as a duration."""
    total = 0.0
    for a in args or [None]:
        if a in ("inf", "infinity"):
            return math.inf
        m = _DURATION.match(a) if isinstance(a, str) else None
        if m is None:
            return None
        total += float(m.group(1)) * _UNIT[m.group(2)]
    return total


def _seconds_word(n: float) -> str:
    if math.isinf(n):
        return "infinity"
    return str(int(n)) if n == int(n) else f"{n:.3f}".rstrip("0")


class _WaitWords(argparse.ArgumentParser):
    """`gate wait`'s words, read by argparse's own rules: an error raises, nothing prints."""

    def error(self, message):
        raise ValueError(message)


def _wait_parser() -> argparse.ArgumentParser:
    """The options `cli`'s `gate wait` parser takes (a test holds the two alike), `--help` a
    flag here so that it prints nothing."""
    p = _WaitWords(prog="gate wait", add_help=False)
    p.add_argument("-h", "--help", action="store_true")
    p.add_argument("id", nargs="?")
    p.add_argument("--chain", action="store_true")
    p.add_argument("--timeout", type=float, metavar="SECONDS")
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    return p


def _wait_id(c) -> str | None:
    """The job a command of this tool's `gate wait` names, its words read as the CLI's parser
    reads them (an abbreviation of an option is that option, so `--time 540` skips its value):
    the id, CHAIN_WAIT for `--chain`; None for any other command, a line the parser refuses
    or asks help of, and an id not read (a variable, a substitution)."""
    args = list(c.args)
    if c.name == "agentik" and args[:1] == ["session"]:
        args = args[1:]
    elif c.name not in _TOOL_WORDS:
        return None
    if args[:2] != ["gate", "wait"]:
        return None
    try:
        ns, extras = _wait_parser().parse_known_intermixed_args(args[2:])
    except (ValueError, TypeError):
        return None
    if extras or ns.help:
        return None
    if ns.chain:
        return CHAIN_WAIT
    job = ns.id
    if not isinstance(job, str) or "$" in job or "`" in job:
        return None
    return _token(job, 96)


def _helper_wait(payload: dict, env) -> dict | None:
    """Packet nw3-helper-wait R2 to R8: a helper's Bash under `say` or `refuse` whose line
    holds a long sleep or a second wait on one job: the denial (`refuse`) or the passing call's
    context (`say`); None otherwise, under `allow`, for the main thread and on any fault. A
    first wait is recorded only where the call passes."""
    if not payload.get("agent_id") or payload.get("tool_name") != "Bash":
        return None
    try:
        value = _helper_wait_value(payload, env)
        if value == "allow":
            return None
        ti = payload.get("tool_input")
        command = ti.get("command") if isinstance(ti, dict) else None
        if not isinstance(command, str):
            return None
        cwd = payload.get("cwd")
        here = cwd if isinstance(cwd, str) and os.path.isabs(cwd) and "\0" not in cwd else None
        cmds, _ = shellreader.commands(command, here, env)
        sdir = _session_dir(payload.get("session_id"), env, fallback=False)
        aid = _token(payload.get("agent_id"))
        doc = _small_json(sdir / HELPER_WAITS) or {}
        waits = [w for w in doc.get("waits") or [] if isinstance(w, list) and len(w) == 2]
        seen = {(a, j) for a, j in waits}
        clause, new = None, []
        for c in cmds:
            if c.name == "sleep":
                n = _sleep_seconds(c.args)
                if clause is None and n is not None and n >= LONG_SLEEP:
                    clause = f"a sleep of {_seconds_word(n)} s"
                continue
            j = _wait_id(c)
            if j is None:
                continue
            if (aid, j) in seen:
                clause = clause or ("a second wait on the chain" if j == CHAIN_WAIT
                                    else f"a second wait on {j}")
                continue
            seen.add((aid, j))
            new.append([aid, j])
        if clause and value == "refuse":
            return _deny(f"agentik-session: an agent is never the wait ({clause}). "
                         + HELPER_WAIT_RULE, HELPER_WAIT_DENY)
        if new:
            store._write_private(sdir / HELPER_WAITS,
                                 json.dumps({"waits": (waits + new)[-HELPER_WAITS_MAX:]}))
        if clause:
            return {"hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": (f"agentik-session: an agent is never the wait "
                                              f"({clause}). " + HELPER_WAIT_RULE)},
                    "systemMessage": HELPER_WAIT_SAY}
    except Exception:                                   # noqa: BLE001  (R8: a fault passes)
        return None
    return None


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
    starts only under a Fable session, and an unknown session model denies it. Packet h6
    R1: under a session of a family `tiers.ORDER` ranks, a helper of a family above it is
    denied too; a session not known, or of no ranked family, denies a Fable helper alone."""
    from . import tiers
    tool = payload.get("tool_name")
    if tool == "Workflow":
        return WORKFLOW_DENY
    if tool not in ("Agent", "Task"):
        return None
    ti = payload.get("tool_input")
    ti = ti if isinstance(ti, dict) else {}
    model = ti.get("model")
    named = isinstance(model, str) and bool(model)      # h5 R1: the call outranks the file
    if not named:
        model = _agent_model(ti, payload, env)
    helper = workflowguard.family(model)
    if helper not in tiers.ORDER:                       # h6 R2: no family passes
        return None
    parent = _session_family(payload, env)
    if helper != "fable":                               # h6 R1, R3: another family's line
        if parent not in tiers.ORDER or tiers.ORDER.index(helper) >= tiers.ORDER.index(parent):
            return None
        names = (f"the call names {_token(model)}" if named else
                 f"agent type {_token(ti.get('subagent_type'))} names {_token(model)}")
        return ("agentik-session: a helper starts only at or below its session's family: "
                f"this one runs {parent}, and {names}, family {helper}. "
                f"Name model: '{parent}' on the call.")
    if parent == "fable":
        return None
    runs = MODEL_UNKNOWN if parent is None else f"this one runs {parent}"
    if not named:                                       # h5 R3: the type named it
        return ("agentik-session: a Fable helper starts only under a Fable session: "
                f"{runs}, and agent type {_token(ti.get('subagent_type'))} names "
                f"{_token(model)}. Name model: 'opus' on the call.")
    return ("agentik-session: a Fable helper starts only under a Fable session: "
            + runs + ". Name model: 'opus', or use an agent type that names its own model.")


_TYPE_PART = re.compile(r"[A-Za-z0-9._-]{1,64}")
_FM_BOUND = 262144                  # review 1 R4: the whole frontmatter, to 256 KB
_LIST_BOUND = 4096                  # entries listed per agents folder, and its depth
_FM_OPEN = re.compile(r"---[ \t\r]*\n")
_FM_CLOSE = re.compile(r"^---[ \t\r]*$", re.M)
_FM_KEY = re.compile(r"(name|model)[ \t]*:[ \t]*(.*)")


def _front(path: str, want: str | None = None) -> tuple:
    """(name, model) of an agent file's frontmatter, None for either it does not state
    (review 1 R4): a byte-order mark, blanks after the opening `---` and before a key's
    colon, a byte that is not UTF-8 (replaced); the block up to its closing line, read to
    256 KB, past which it is what was read. The caller opens only a regular file (R3), and
    without blocking, so a FIFO put in its place since answers at once; a file that
    cannot be read gives (None, None), and so does one whose bytes hold no `want` (it cannot
    name that type), unparsed. Never raises."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    except (OSError, ValueError):
        return None, None
    try:
        raw = os.read(fd, 65536)                        # one read for a common file
        if len(raw) == 65536:
            while len(raw) < _FM_BOUND:
                got = os.read(fd, _FM_BOUND - len(raw))
                if not got:
                    break
                raw += got
    except OSError:
        return None, None
    finally:
        os.close(fd)
    if want is not None and want.encode() not in raw:
        return None, None
    text = raw.decode("utf-8", "replace")
    text = text[1:] if text.startswith("﻿") else text
    m = _FM_OPEN.match(text)
    if not m:
        return None, None
    body = text[m.end():]
    end = _FM_CLOSE.search(body)
    if end is None and len(raw) < _FM_BOUND:
        return None, None                               # no closing line: no frontmatter
    name = model = None
    for line in body[:end.start() if end else len(body)].splitlines():
        k = _FM_KEY.fullmatch(line.rstrip())
        if k is None:
            continue
        if k.group(1) == "model" and model is None:     # the first that states one
            got = re.match(r"['\"]?([^'\"\s]+)", k.group(2))
            model = got.group(1) if got else None
        elif k.group(1) == "name" and name is None:
            v = k.group(2).strip()
            v = v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else \
                re.sub(r"\s+#.*$", "", v)
            name = v or None
    return name, model


def _scan(folder: Path, nested: bool, want: str) -> list:
    """[(type, stem, model)] for each regular `*.md` in an agents folder: the type its
    frontmatter `name:`, else the file's stem, a plugin's subfolders its namespace
    (`team:drafter`, review 1 R1); at most `_LIST_BOUND` entries and that depth. A file
    whose stem is not `want` is parsed only when its bytes hold `want`."""
    out, todo, seen = [], [(str(folder), ())], 0
    while todo:
        where, ns = todo.pop()
        try:
            with os.scandir(where) as it:
                entries = [e for _, e in zip(range(_LIST_BOUND - seen), it)]
        except (OSError, ValueError):
            continue
        seen += len(entries)
        for e in entries:
            try:
                if e.is_dir():
                    if nested and len(ns) < 8 and seen < _LIST_BOUND:
                        todo.append((e.path, ns + (e.name,)))
                    continue
                if not e.name.endswith(".md") or not e.is_file():     # R3: no FIFO, no device
                    continue
            except OSError:
                continue
            stem = e.name[:-3]
            name, model = _front(e.path, None if stem.casefold() == want.casefold() else want)
            out.append((":".join(ns + (name or stem,)), ":".join(ns + (stem,)), model))
    return out


def _rank(model) -> int:
    from . import tiers
    f = tiers.family(model)
    return tiers.ORDER.index(f) if f in tiers.ORDER else len(tiers.ORDER)


def _project_folders(payload: dict, env) -> list:
    """Review 1 R2: the agents folders of the working directory and each ancestor up to the
    repo's root (the folder holding `.git`, else the top), nearest first, then
    `CLAUDE_PROJECT_DIR`'s."""
    out = []
    try:
        cwd = payload.get("cwd") or env.get("CLAUDE_PROJECT_DIR")
        if isinstance(cwd, str) and cwd:
            d = Path(cwd)
            for _ in range(256):
                out.append(d / ".claude" / "agents")
                if os.path.lexists(d / ".git") or d.parent == d:
                    break
                d = d.parent
        pd = env.get("CLAUDE_PROJECT_DIR")
        if isinstance(pd, str) and pd and Path(pd) / ".claude" / "agents" not in out:
            out.append(Path(pd) / ".claude" / "agents")
    except (OSError, ValueError):
        pass
    return out


def _agent_model(ti: dict, payload: dict, env) -> str | None:
    """The `model:` of the agent type the call's `subagent_type` names, found as Claude Code
    names it (review 1 R1): by its file's frontmatter `name:`, else the file's name. A
    type `<name>`: the nearest of the project's agents folders (R2) that defines it, else
    the user's (`CLAUDE_CONFIG_DIR`, else `~/.claude`). A plugin's type
    `<plugin>[:<folder>...]:<name>`: every install of `<plugin>@<marketplace>` in
    `plugins/installed_plugins.json` (h5 R2). Two files claiming one type: the model whose
    family ranks highest in `tiers.ORDER` (the reading that refuses), one naming no family
    last. When no file claims it, a file of its name that claims another counts (a call
    for such a type fails in Claude Code, so refusing it costs nothing). None when none
    is found or it names no model; never raises on a read."""
    name = ti.get("subagent_type")
    if not isinstance(name, str):
        return None
    parts = name.split(":")
    if len(parts) > 10 or not all(_TYPE_PART.fullmatch(p) for p in parts):
        return None
    user = Path(env.get("CLAUDE_CONFIG_DIR") or Path(env.get("HOME") or Path.home()) / ".claude")
    if len(parts) > 1:
        plugins = _load_json(user / "plugins" / "installed_plugins.json").get("plugins")
        group = []
        for key, recs in (plugins.items() if isinstance(plugins, dict) else ()):
            if not isinstance(key, str) or "@" not in key or key.partition("@")[0] != parts[0]:
                continue
            for rec in (recs if isinstance(recs, list) else ()):
                where = rec.get("installPath") if isinstance(rec, dict) else None
                if isinstance(where, str) and where:
                    group += _scan(Path(where) / "agents", True, parts[-1])
        groups, want = [group], ":".join(parts[1:])
    else:
        groups = [_scan(f, False, name) for f in _project_folders(payload, env)
                  + [user / "agents"]]
        want = name
    for col in (0, 1):                                  # by the type's name, then the file's
        for group in groups:
            hits = [g for g in group if (g[0] == want if col == 0 else
                                         g[1].casefold() == want.casefold())]
            if hits:
                models = [g[2] for g in hits if g[2]]
                return min(models, key=_rank) if models else None
    return None


def _role_rule(payload: dict, env) -> tuple:
    """Packet mt1 R6: (posture, line) when an Agent or Task call names its role by a line
    `tier: <role>` in its prompt and its model (the call's, else its agent file's) ranks
    above that role's in the session's table (resolved, with this session's `set tier.*`
    and `set cap` words); else (posture, None). A call that names no role, or whose model or
    session table is unknown, is left to the family rule. Never raises."""
    try:
        from datetime import datetime, timezone
        from . import tiers
        ti = payload.get("tool_input")
        ti = ti if isinstance(ti, dict) else {}
        role = tiers.role(ti.get("prompt"))
        if role is None:
            return None, None
        sid = payload.get("session_id") or env.get("CLAUDE_CODE_SESSION_ID")
        sdir = _session_dir(sid, env, fallback=False) if sid else None
        s = (_load_json(sdir / "resolved.json").get("session") or {}) if sdir else {}
        s = s if isinstance(s, dict) else {}
        table = s.get("tiers")
        if not isinstance(table, dict):
            return s.get("posture"), None
        ov = {} if sdir is None else _load_json(resolver.state_dir(env) / "overlays"
                                                / f"{sdir.name}.json")
        table = tiers.effective(table, ov, datetime.now(timezone.utc))
        want = (table.get(role) or {}).get("model")
        model = ti.get("model") if isinstance(ti.get("model"), str) and ti.get("model") \
            else _agent_model(ti, payload, env)
        if not tiers.above(model, want):
            return s.get("posture"), None
        return s.get("posture"), (
            f"agentik-session: this spawn names tier: {role}, whose model is {want}, and "
            f"runs {_token(str(model))}, above it. Name model: '{want}', or the role the "
            "work is.")
    except Exception:                                   # noqa: BLE001  (a check, never a crash)
        return None, None


def _warned(out: dict, warn: str | None) -> dict:
    """`out` with the role check's warning (posture signal or ask) said beside it."""
    if not warn:
        return out
    out = dict(out)
    out["systemMessage"] = (out["systemMessage"] + " " if out.get("systemMessage") else "") + warn
    return out


def _deny(reason: str, note: str | None) -> dict:
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                  "permissionDecisionReason": reason}}
    if note:
        out["systemMessage"] = note
    return out


def _told(out: dict, told: tuple | None) -> dict:
    """`out` with the launch line (packet nw4-launch-room R9) as context for the model, in
    `hookSpecificOutput.additionalContext`, and said to the person in `systemMessage`."""
    if not told:
        return out
    out = dict(out)
    hso = dict(out.get("hookSpecificOutput") or {"hookEventName": "PreToolUse"})
    hso["additionalContext"] = told[0]
    out["hookSpecificOutput"] = hso
    out["systemMessage"] = (out["systemMessage"] + " " if out.get("systemMessage") else "") + told[0]
    return out


def _held(tool: str, told: tuple | None, posture) -> dict | None:
    """Packet nw4-launch-room R8: under `deny`, a launch the room holds is refused, the line
    its reason; else None."""
    if told and told[1] and posture == "deny":
        return _deny(told[0], f"agentik-session: held a {_token(tool)} spawn for room.")
    return None


def pre_tool_use(payload: dict, env=None) -> dict:
    """The spawn gate (§2.2): under `ask` or `deny`, a spawn in the late zones
    asks, and under `deny` one in the reserve is refused. A subagent's call: {}.
    Every tool's call is stamped first (respawn-r1 §3.3); the gate acts on spawns only.
    The Bash refusals come before the call opens, in this order: a helper's charter open or
    close (n33), a RESPAWN close in the background (rc1), the stray writes (g8, lineguard),
    a gated file's write (g2b), the main thread's close while a job is out (rc2), and, under
    the session's `helpers.wait` (nw3), a helper's second wait on one gate job or its sleep of
    a minute or more: denied under `refuse`, said as context on a passing call under `say`,
    untouched under `allow`, the shipped default.
    A spawn goes through the family rule (wfd, wfg, h6), then the role check (mt1 R6), then, at
    a main thread's Agent or Task call alone, the launch check (nw4): in a session that keeps
    the sitting discipline and under `signal`, `ask` or `deny`, the room left to the line and
    whether the helper fits (room.py) is said as context and to the person; under `deny` a
    narrow launch that does not fit and one with no room are refused, after the zone gate's
    own refusal. A helper's call, the `off` posture and a waived discipline are told nothing,
    and a fault in its reads gives no line."""
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
    warn = None
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
        posture, warn = _role_rule(payload, os.environ if env is None else env)   # mt1 R6
        if warn and posture == "deny":
            return _deny(warn, f"agentik-session: denied a {_token(tool)} spawn before launch.")
        if posture not in ("signal", "ask"):
            warn = None
    if tool == "Bash":               # rc1 R1: any posture, a helper's too, no call opened
        try:
            background = _background_close(payload)
        except Exception:                               # noqa: BLE001  (R1: fails open)
            background = False
        if background:
            return _deny(BACKGROUND_CLOSE_DENY,
                         "agentik-session: denied a RESPAWN close run in the background.")
    if tool == "Bash":               # g8: the stray-write refusals, a helper's too, no call opened
        try:
            line = lineguard.check(payload, os.environ if env is None else env)
        except Exception as e:                          # noqa: BLE001  (R14: an error refuses)
            line = lineguard.failed(payload, os.environ if env is None else env, e)
        if line:
            return line
    if tool in instructionguard.TOOLS:   # g2b: an edit or a Bash write of a gated file is refused
        try:
            guard = instructionguard.check(payload, os.environ if env is None else env)
        except Exception:                               # noqa: BLE001  (R4: fails open)
            guard = {}
        if guard:
            return guard             # a refused call opens none
    if tool == "Bash":               # rc2 R4: any posture, the main thread's alone, no call opened
        line = _jobs_out_line(payload, os.environ if env is None else env)   # never raises
        if line:
            return _deny(line, "agentik-session: asked once before a RESPAWN close while a "
                               "background job is not known to have ended.")
    said = None
    if tool == "Bash":               # nw3: under helpers.wait, a helper's alone; never raises
        said = _helper_wait(payload, os.environ if env is None else env)
        if said and "permissionDecision" in said["hookSpecificOutput"]:
            return said              # refuse: a refused call opens none
    _open_call(payload, os.environ if env is None else env)
    if said:
        return said                  # say: the call passes, and the rule is said
    if tool not in SPAWNING_TOOLS:
        return {}
    if payload.get("agent_id"):
        return _warned({}, warn)
    cfg, zone = state(payload.get("session_id"), env)
    from . import room               # nw4: the launch line; never raises, None outside the rule
    told = room.told(payload, os.environ if env is None else env, cfg.posture)
    if cfg.posture in ("off", "signal"):
        return _told(_warned({}, warn), told)   # signalling happens on the prompt, not here
    if zone not in (WINDDOWN, RESERVE, EXHAUSTED):
        return _held(tool, told, cfg.posture) or _told(_warned({}, warn), told)
    plain = (None if discipline(_session_section(payload.get("session_id"), env))
             else _plain_budget(zone, used_pct(payload.get("session_id"), env)))   # st1 C2

    if cfg.posture == "deny" and zone in (RESERVE, EXHAUSTED):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": plain or _wrap_up(zone),
            },
            "systemMessage": (
                f"agentik-session [{cfg.name}]: blocked a {tool} spawn: "
                "the rest is reserved for wrapping up."),
        }

    held = _held(tool, told, cfg.posture)
    if held:
        return held
    return _told(_warned({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                f"{plain} Spawning {tool} now may not leave enough budget to finish "
                "cleanly. Consider a smaller fan-out." if plain else
                _budget_line(zone) + f" Spawning {tool} now may not leave "
                "enough budget to finish and hand off cleanly. Consider a "
                "smaller fan-out."),
        }
    }, warn), told)


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


def _tiers_part(sid, env) -> str:
    """`; tiers: build sonnet to Ddd HH:MM; cap: opus to Ddd HH:MM` while this session's
    words are in force (mt1 R4), else ""; never raises."""
    try:
        from datetime import datetime, timezone
        from . import fill, tiers
        got = tiers.parts(fill.overlay(resolver.state_dir(env), sid), datetime.now(timezone.utc))
        return "".join("; " + p for p in got)
    except Exception:  # noqa: BLE001 - the part never breaks a hook
        return ""


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


def _gate_lines(payload: dict, env, event: str, out: dict, alone: bool,
                line: str | None = None) -> list[str]:
    """S38 ruling 3: the main thread's inbox of gate results, whatever the posture. At most
    three files are taken (an atomic rename into `inbox/read/`), each one line (the `wait`
    line), then `<n> more: ...` when any remain. The lines stop where the output would pass
    MAX_OUT: the whole output on PostToolUse (`alone` False, `out` the handler's), the
    inbox block alone on UserPromptSubmit. A helper's payload (agent_id) takes nothing.
    With a sitting's `line` (packet in3 R4), one file at most, under MAX_OUT less the
    line's share, and the line after them. Under a chain (packet nw2-chain-inbox R2) the
    chain's inbox after the session's own, where `gate.chain_taker` names this session the
    chain's sitting; from its confirmed respawn mark on, a chain line is shown once and left
    for the successor. Never raises: a failure before any rename is no gate lines, and the
    files wait for the next hook; after one, every line already taken is returned (brief 2,
    R1)."""
    tail = [line] if line else []
    try:
        sid = payload.get("session_id")
        if payload.get("agent_id") or not isinstance(sid, str) or not _SID.match(sid):
            return tail
        base = {} if alone else out
        room = MAX_OUT - (LINE_SHARE if line else 0)

        def fits(text: str) -> bool:
            return len(json.dumps(_with_gate(base, event, [text]))) <= room
        root = resolver.state_dir(env)
        chain = gate.chain_taker(root, env, sid)
        return gate.inbox_take(root, sid, limit=1 if line else gate.TAKE, fits=fits,
                               chain=chain, closed=bool(chain) and gate.sitting_closed(root, sid)
                               ) + tail
    except Exception:                                   # noqa: BLE001
        return tail


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


# Packet in3-line: a line another sitting sent this checkout, taken in three hooks (lines.py).
LINE_SHARE = 256                        # lines.SHARE: a hook's bytes kept for its line (R4)


def _line_take(payload: dict, env, start: bool = False, out: dict | None = None) -> str | None:
    """One line for this session, or None: on PostToolUse only while the handler's own
    output leaves the line its share (`out`). Never raises."""
    try:
        if out is not None and len(json.dumps(out)) > MAX_OUT - LINE_SHARE:
            return None
        from . import lines
        return lines.take(resolver.state_dir(env), payload, env, start=start)
    except Exception:                                   # noqa: BLE001 - never a failed hook
        return None


def user_prompt_submit(payload: dict) -> dict:
    """Budget context, and the checkpoint nudge that is the real mechanism. The gate's
    inbox lines (S38 ruling 3) are taken at each return, the posture-off one included,
    after the body, so a body that raises leaves the files for the next hook (F3)."""
    sid = payload.get("session_id")
    if not payload.get("agent_id"):                     # before the posture (respawn-r1 §3.3)
        _stamp(payload, os.environ, ACTIVITY,
               {"event": "UserPromptSubmit", "tool": None, "at": time.time()})
    _jobs_notice(payload, os.environ)                   # rc2 R3: every posture, never raises
    unconfirmed = _unconfirmed_line(payload, os.environ)  # rc1 R2: every posture, never raises
    cfg, zone = state(sid)
    if cfg.posture == "off":
        return _gate_ups(payload, {} if not unconfirmed else {"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": unconfirmed}})

    ov = sessionconfig.load_overlay()
    count = int(ov.get(COUNTER) or 0) + 1
    sessionconfig.save_overlay({COUNTER: count})

    cadence = (cfg.checkpoint or {}).get(zone, 0)
    bits: list[str] = [unconfirmed] if unconfirmed else []

    m = _meter(sid)
    shown = False
    if m and m.get("turns") != 0:      # ss1 review 1 F1: SessionStart's zero meter says nothing
        sdir = _session_dir(sid, os.environ)
        now = _now()
        if (_past_checkpoint(m)
                or _meter_due(sdir, _meter_minutes(sdir), now, prompt=True)):
            bits.append(_meter_words(m))
            _meter_stamp(sdir, now, True)
            shown = True
    held = _held_clause(sid, os.environ)    # nw6 R2: on the meter's line, else alone
    if held and shown:
        bits[-1] += f"; {held}"
    elif held:
        bits.append(held)

    plain = not discipline(_session_section(sid))          # st1 C2: plain words, no cadence
    if plain:
        if zone not in (CLEAR, UNKNOWN):
            bits.append(_plain_budget(zone, used_pct(sid)))
    elif zone in (RESERVE, EXHAUSTED):
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

    if cadence and count >= cadence and not plain:
        bits.append(
            f"{count} prompts since the last checkpoint (cadence is {cadence} in "
            f"the '{zone}' zone). Commit or durably record what is done, then "
            "run `agentik-session checkpoint`, so this session can be handed off "
            "at any moment rather than only when it is convenient.")

    if not bits:
        return _gate_ups(payload, {})
    return _gate_ups(payload, {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                      "additionalContext": "\n\n".join(bits)}})


def _held_clause(sid, env) -> str | None:
    """nw6 R2: while the helpers hold this sitting's marked respawn, the clause the launcher's
    held.json gives (chain.held_by); None otherwise and on any fault."""
    try:
        name = env.get(CHAIN_VAR) or ""
        if not (CHAIN_RE.match(name) and isinstance(sid, str) and _SID.match(sid)):
            return None
        from . import chain
        state, now = resolver.state_dir(env), _now()
        d = chain.held_by(state, name, sid, now)
        return chain.held_words(d, chain.past_half(state, sid, d, now)) if d else None
    except Exception:                                   # noqa: BLE001
        return None


def _gate_ups(payload: dict, out: dict) -> dict:
    """UserPromptSubmit's output with the inbox lines first, the block alone under MAX_OUT;
    a gated file's change that waits (gc1 R3) said after the body, the two within MAX_OUT."""
    if not payload.get("agent_id"):
        out = _with_changed(payload, os.environ, out, instructionguard.waiting(
            payload, os.environ), event="UserPromptSubmit")
    return _with_gate(out, "UserPromptSubmit",
                      _gate_lines(payload, os.environ, "UserPromptSubmit", out, alone=True,
                                  line=_line_take(payload, os.environ)))


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


def launched(env) -> bool:
    """Row ss3 R1: the launcher set this session's model and effort: a launch profile, or
    `agentik session run`'s chain mark, which passes the profile's flags with none exported."""
    return launch_profile(env) is not None or bool(CHAIN_RE.match(str(env.get(CHAIN_VAR) or "")))


# Row ss3 R1: what a session the launcher did not start is told of its profile.
NOT_LAUNCHED = (" (its limits and rules apply; its model and effort are set only by agentik "
                "session run)")


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


# Packet su3 (entry 12): a declared watcher that is not running, said once at session start.
# The launcher at its fixed place, never the door or PATH (R1); one line of its stdout on exit
# 1, else silence (R2, R3). The share is cut at its first line's end so that an output holding
# it alone fits MAX_OUT, as UserPromptSubmit's inbox block alone does; the plugin's own words
# are not capped at SessionStart, as at the pin.
WATCH_WALL = 2.0
WATCH_ARGS = ("status", "--check")
WATCH_MORE = " and {n} more: agentik status"
_WATCH_READ = 65536                     # stdout kept; the rest is drained, never held
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")    # C0, DEL and C1, as chain._CONTROL
_BLANKS = bytes(b for b in [*range(0x21), 0x7f] if b != 0x0a)   # bytes that make no text


def _watch_stop(p) -> None:
    """The wall cut: the child's process group killed, the child reaped (R2)."""
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        try:
            p.kill()
        except OSError:
            pass
    p.wait()


class _Beyond:
    """The lines of the stdout past the keep, counted as it is read and never held. A line
    counts when it holds a byte that is no ASCII blank or control (the decoded test is made on
    the kept part alone, which is exact there)."""

    def __init__(self) -> None:
        self.head = self.seen = self.cur = False    # the first fragment, a newline seen, open line
        self.done = 0                               # whole lines after the first newline

    def feed(self, chunk: bytes) -> None:
        parts = chunk.translate(None, _BLANKS).split(b"\n")
        self.cur = self.cur or bool(parts[0])
        if len(parts) > 1:
            if self.seen:
                self.done += self.cur
            else:
                self.head, self.seen = self.cur, True
            mid = parts[1:-1]
            self.done += len(mid) - mid.count(b"")
            self.cur = bool(parts[-1])

    def lines_after(self, tail: bytes) -> int:
        """Lines from `tail`, the kept bytes after their last newline, to the stream's end."""
        first = (self.head if self.seen else self.cur) or bool(tail.translate(None, _BLANKS))
        return int(first) + ((self.done + self.cur) if self.seen else 0)


def _watch_run(exe: str, env):
    """The launcher's stdout when it exits 1 within WATCH_WALL, else None: a pair, the first
    _WATCH_READ bytes at most and, when the stream was longer, a _Beyond holding its rest (else
    None). No shell, its stdin empty, its stderr dropped, in a group of its own so a cut takes
    its children too."""
    try:
        p = subprocess.Popen([exe, *WATCH_ARGS], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             close_fds=True, start_new_session=True, env=dict(env))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return None
    end, buf, rest = time.monotonic() + WATCH_WALL, bytearray(), None
    try:
        fd = p.stdout.fileno()
        with selectors.DefaultSelector() as sel:
            sel.register(fd, selectors.EVENT_READ)
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    raise TimeoutError
                if not sel.select(left):
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                room = max(0, _WATCH_READ - len(buf))
                buf += chunk[:room]
                if len(chunk) > room:
                    rest = rest or _Beyond()
                    rest.feed(chunk[room:])
        code = p.wait(timeout=max(end - time.monotonic(), 0.001))
    except Exception:                                   # noqa: BLE001 - a cut is silence
        _watch_stop(p)
        return None
    finally:
        p.stdout.close()
    return (bytes(buf), rest) if code == 1 else None


def _watch_cut(first: str, tail: str) -> str:
    """The share, its first line cut at its end until an output holding it alone fits."""
    room = MAX_OUT - len(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": tail}}))
    kept = 0
    for i, ch in enumerate(first):
        kept += len(json.dumps(ch)) - 2
        if kept > room:
            return first[:i] + tail
    return first + tail


def _watch_lines(text: str) -> list[str]:
    """The non-blank lines of `text`, a control character taken out and the ends stripped."""
    return [ln for ln in (_CONTROL.sub("", raw).strip() for raw in text.split("\n")) if ln]


def watcher_share(payload: dict, env) -> str | None:
    """R1 to R3, R6: the one line, or None for a helper's start, a HOME that is unset or not
    absolute, and every outcome but exit 1 with text. Never raises."""
    try:
        if env.get("CLAUDE_SESSION_HELPER") == "1" or payload.get("agent_id"):
            return None
        home = env.get("HOME")
        if not isinstance(home, str) or not os.path.isabs(home):
            return None
        got = _watch_run(os.path.join(home, ".local", "bin", "agentik-suite"), env)
        if not got or not got[0]:
            return None
        kept, rest = got
        tail = b""
        if rest is not None:            # longer than the keep: cut at the last newline (C1)
            cut = kept.rfind(b"\n") + 1
            kept, tail = kept[:cut], kept[cut:]
        lines = _watch_lines(kept.decode("utf-8"))
        more = len(lines) - 1
        if rest is not None:
            after = rest.lines_after(tail)
            if not lines:               # the first line alone fills the keep: cut where it fits
                lines = _watch_lines(codecs.getincrementaldecoder("utf-8")().decode(tail))
                after -= 1
                more = 0
                after = max(after, 0)
            more += after
        if not lines:
            return None
        return _watch_cut(lines[0], WATCH_MORE.format(n=more) if more > 0 else "")
    except Exception:                                   # noqa: BLE001 - never a failed hook
        return None


def _with_watcher(out: dict, share: str) -> dict:
    """R4: the share on the owner's screen before the hook's own message, and first in the
    session's context, before the start line."""
    out = dict(out)
    said = out.get("systemMessage")
    out["systemMessage"] = share + (f"\n{said}" if said else "")
    hso = dict(out.get("hookSpecificOutput") or {})
    ctx = hso.get("additionalContext") or ""
    hso["hookEventName"] = "SessionStart"
    hso["additionalContext"] = share + (f"\n\n{ctx}" if ctx else "")
    out["hookSpecificOutput"] = hso
    return out


def session_start(payload: dict, env=None) -> dict:
    """SessionStart: the watcher's line (packet su3; R5: first of the additions, since no
    guards' write is built), then the start itself, `_start`. With no line the output is the
    pin's, an exception included; with one, a start that raises reads as `{}`."""
    env = os.environ if env is None else env
    share = watcher_share(payload, env)
    line = _line_take(payload, env, start=True)         # packet in3 R4: after the watcher's
    jobs = _gate_open(payload, env)                     # nw2 R4: the chain's open jobs
    if share is None and line is None and jobs is None:
        return _start(payload, env)
    try:
        out = _start(payload, env)
    except Exception:                                   # noqa: BLE001 - R4: still said
        out = {}
    if line is not None or jobs is not None:
        out = _with_gate(out, "SessionStart", [x for x in (jobs, line) if x is not None])
    return out if share is None else _with_watcher(out, share)


def _gate_open(payload: dict, env) -> str | None:
    """design/31 item 11: the chain sitting's line of its chain's open gate jobs, or None
    (no chain, another session, a helper, none open, any fault)."""
    try:
        sid = payload.get("session_id")
        if payload.get("agent_id"):
            return None
        root = resolver.state_dir(env)
        chain = gate.chain_taker(root, env, sid)
        return gate.open_line(root, chain, time.time()) if chain else None
    except Exception:                                   # noqa: BLE001
        return None


def _gate_open_count(env) -> int:
    """The open gate jobs of the environment's chain (item 13's words), 0 on any fault."""
    try:
        name = str(env.get(CHAIN_VAR) or "")
        return len(gate.open_jobs(resolver.state_dir(env), name)) if CHAIN_RE.match(name) else 0
    except Exception:                                   # noqa: BLE001
        return 0


def _start(payload: dict, env=None) -> dict:
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
                              payload.get("transcript_path"), model, source,
                              launched=launched(env))
    except Exception as e:                              # noqa: BLE001
        print(f"agentik-session: SessionStart resolved nothing: {e}", file=sys.stderr)
        if isinstance(e, resolver.UnknownProfile):      # ss3 R3: the session is told too
            return _follow_said({"hookSpecificOutput": {
                "hookEventName": "SessionStart", "additionalContext": _unknown_line(e)}}, env)
        return _follow_said({}, env)
    s = r.sections["session"]
    # Packet b1 R3: no ceiling, window or turn cap reaches the model; the band above the
    # prompt, which only the owner sees, keeps every figure.
    line = (f"agentik-session: profile '{_token(s['profile'])}'"
            f"{'' if launched(env) else NOT_LAUNCHED}; "
            f"{START_METER if discipline(s) else START_METER_PLAIN}; "
            f"resolved config at {path}")
    line += rules.clause(s, _lifetime(cwd, env, sid)[0],     # at most 320 bytes (S21, S30)
                         fill=_fill_part(sid, s, env))     # its fill part (FW1b R6)
    line += _tiers_part(sid, env)                          # mt1 R4: the session's words
    line += _charter_reminder(s, cwd)
    line += _state_reminder(env, time.time(), sid=sid)     # outside the clause's bound
    _first_meter(path.parent, payload.get("transcript_path"), env)   # ss1 R1, after the line
    return _follow_said({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                "additionalContext": line}}, env)


_PLAIN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _unknown_line(e) -> str:
    """Row ss3 R3: the session's one line on a profile name the tool does not know. The name
    prints when the caller gave it and it is a plain word; a name read from a layer file is
    its text, withheld (ss2), as is one that is no plain word."""
    name = e.name if isinstance(e.name, str) and _PLAIN.match(e.name) else None
    said = f"'{name}'" if name else "(withheld)"
    return (f"agentik-session: unknown profile {said}; nothing of a profile applies to this "
            f"session. Known: {e.known}; start with CLAUDE_SESSION_PROFILE=<one> agentik "
            "session run")


def _first_meter(sdir: Path, tp, env) -> None:
    """Packet ss1-zero R1: the session's first meter.json by PostToolUse's own parse and
    save, so the band, `status` and doctor read 0% before the first tool call. A transcript
    absent or unreadable is zero turns (`os.devnull` parsed, the payload's path kept), written
    only where no meter stands; a meter on disk is replaced only by a parse that succeeded.
    Any failure is swallowed (R2): SessionStart says what it says today."""
    try:
        cfg, _ = sessionconfig.effective()
        limits, policy = meter.limits_for(sdir, env), _policy(cfg)
        st = meter.load_state(sdir)
        try:                                            # review 1 F2: a FIFO never blocks
            regular = bool(tp) and stat.S_ISREG(os.stat(tp).st_mode)
        except (OSError, ValueError):
            regular = False
        m = meter.parse(tp, st, limits, policy, sdir.name) if regular else None
        if m is None:
            if meter.load(sdir) is not None:
                return
            st = {}
            m = meter.parse(os.devnull, st, limits, policy, sdir.name)
            m = replace(m, transcript={**m.transcript, "path": str(tp) if tp else None,
                                       "inode": None})
        meter.save(sdir, m, st)
    except Exception:                                   # noqa: BLE001
        pass


START_METER = ("the meter shows this session's percent on its schedule and prints CHECKPOINT "
               "when it is time to bring the charter current and hand off")
# Packet st1-starter R5: a session under the waiver (`discipline`) is told the meter with no
# word of the sitting discipline.
START_METER_PLAIN = ("the meter shows this session's percent on its schedule and prints "
                     "CHECKPOINT when it is time to commit and stop")


def discipline(session) -> bool:
    """The fix of st1's review 1, C1, the one waiver: False where the resolved `session`
    section's `charter.discipline` is false (the shipped `starter` alone sets it): plain
    start, budget, checkpoint and last lines, and an automatic compaction passes. True
    otherwise, a section that names none or none read included; `charter.required` alone
    changes no line."""
    c = session.get("charter") if isinstance(session, dict) else None
    return not (isinstance(c, dict) and c.get("discipline") is False)


def _session_section(session_id, env=None) -> dict:
    """The session's resolved `session` section; {} when none is read."""
    sdir = _session_dir(session_id, os.environ if env is None else env)
    s = _load_json(sdir / "resolved.json").get("session") if sdir else None
    return s if isinstance(s, dict) else {}


# C2: under the waiver every line about the budget says the percent and what to do.
PLAIN_TODO = {WINDDOWN: "finish the work in hand and commit it; start nothing large",
              RESERVE: "finish or park what is in flight and commit it",
              EXHAUSTED: "commit what is done, then stop"}


def _plain_budget(zone: str, pct) -> str:
    todo = PLAIN_TODO.get(zone, "carry on, and commit each piece of work as it is done")
    used = "" if pct is None else f"{max(0, int(math.floor(pct)))}% used, "
    return f"Session budget: {used}'{zone}' zone; {todo}."


def _charter_reminder(session: dict, cwd) -> str:
    """When `charter.required` and no `<dir>/<today>-*.md` exists under cwd."""
    c = session.get("charter")
    if not isinstance(c, dict) or c.get("required") is not True:
        return ""
    d = _charter({"session": session})
    a = records.answer(cwd)                         # packet rr5a R4, R5
    s = records.state(a)
    if s == "unset":
        return ""
    if s == "broken":
        return "; records: " + records.line(a)
    if s == "out" and not d.startswith("?"):
        f = records.folder(a, d)
        if any(Path(f).glob(f"{charter.today()}-*.md")):
            return ""
        return (f"; charter: none open today under "
                f"{f if _SAFE_PATH.match(f) else 'the records folder'}, run "
                f'agentik-session charter open "<goal>"')
    if not d.startswith("?") and any((Path(cwd) / d).glob(f"{charter.today()}-*.md")):
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
    """The charter folder a line names: a word, filtered to a path's characters; a value of
    another kind is named by its kind, never turned into text (ss4 review 1, R1-F1: a line
    mis-indented under `dir` makes `gate.ntfy_topic` its value)."""
    c = ((resolved.get("session") or {}).get("charter") or {})
    d = c.get("dir") if isinstance(c, dict) else None
    if d is not None and not isinstance(d, str):
        return f"? (session.charter.dir holds {resolver.kind(d)})"
    return re.sub(r"[^A-Za-z0-9_./-]", "", d or "history/sittings")[:80] or "?"


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
# Packet st1-starter R5: the checkpoint's tail under the waiver (`discipline`), on either road.
PLAIN_TAIL = "commit what is done, then stop"
RESPAWN_TAIL = ("bring the charter current with a Next act that opens RESPAWN:, commit, then run "
                "`agentik session checkpoint --respawn --charter {f}` in a foreground call of "
                "its own and end the turn; "                        # rc1 R4
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


def _charter_file_out(sdir: Path, folder: str) -> list[str]:
    """Packet rr5a R4, in `out`: the recorded charter by its absolute path alone, where it is a
    file directly in `folder` (`<records>/<dir>`) and passes _SAFE_PATH; NO_CHARTER last.
    No relative spelling. A failure reads as none. Never raises."""
    out = []
    try:
        rec = _load_json(sdir / CHARTER_REC).get("path")
        if (isinstance(rec, str) and os.path.isabs(rec) and _SAFE_PATH.match(rec)
                and os.path.isfile(rec)
                and os.path.realpath(os.path.dirname(rec)) == os.path.realpath(folder)):
            out = [rec]
    except Exception:                                   # noqa: BLE001
        out = []
    return out + [NO_CHARTER]


def _checkpoint_out(m: meter.Meter, charter: str | None,
                    files: list[str] | None = None, room: str | None = None) -> dict:
    """The pin's line off a launcher (`files` None); under one (S33), a line per spelling
    of the charter file in `files`, the first that fits MAX_OUT. `charter` None (a profile
    under the waiver, packet st1 R5 and C2): PLAIN_TAIL alone, on either road, with no
    wind-down tail. `room` (packet rc3 R2, under a launcher only): the first spelling whose
    line leaves room for `room` after it, as `_after` puts it; where none does, as above."""
    c = m.ceilings
    head = (f"CHECKPOINT: {m.pct_context}% context ({m.context}/{c['context']}), "
            f"{m.pct_turns}% turns ({m.turns}/{c['turns']}); ")
    tails = ([PLAIN_TAIL] if charter is None else
             [f"charter {f}; " + RESPAWN_TAIL.format(f=f) for f in files] if files is not None
             else [f"charter {path}; bring the charter current, commit, then exit"
                   for path in (charter, "?")])
    outs = []
    for tail in tails:
        line = head + tail + ("" if charter is None else WIND_DOWN.format(pct=m.used_pct))
        if m.used_pct >= 100.0:
            line += "\n" + (PLAIN_EXIT if charter is None else EXIT_RULE)     # st1 D3
        outs.append({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                            "additionalContext": line}})
    if room and charter is not None and files is not None:
        for out in outs:
            if len(json.dumps(_after(out, room))) <= MAX_OUT:
                return out
    for out in outs:
        if len(json.dumps(out)) <= MAX_OUT:
            return out
    return {}


def _load_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError, RecursionError):     # too deep to parse: no parse (n99)
        return {}
    return d if isinstance(d, dict) else {}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# The checkpoint's spellings _confirm accepts (agentik-r1 packet ruling 9): the tool, the
# front door, and the pre-rename alias, which r2 drops.
RESPAWN_CMDS = ("agentik-session checkpoint", "agentik session checkpoint",
                "claude-session checkpoint")

# Packet rc1 R1: a background call's PostToolUse fires before its verb writes the marker, so
# no hook confirms it and the launcher waits on it for good; such a call is refused.
BACKGROUND_CLOSE_DENY = (
    "agentik-session: a RESPAWN close is never run in the background: only the main thread's "
    "foreground call confirms the mark, so a background one leaves the chain waiting on a mark "
    "no hook confirms. Finish the check, commit and push first, then run `agentik session "
    "checkpoint --respawn --charter <file>` in a foreground call of its own as the sitting's "
    "last act.")
# Packet rc1 R2: said at each main-thread prompt while this session's chained marker stands
# unconfirmed; the charter's path only where _SAFE_PATH takes it.
UNCONFIRMED = ("RESPAWN unconfirmed: no foreground Bash call of the main thread confirmed this "
               "sitting's respawn mark, so the launcher will not restart the sitting. A closing "
               "sitting runs `agentik session checkpoint --respawn --charter {f}` again in a "
               "foreground call of its own, then ends the turn.")
UNSAFE_CHARTER = "<the charter>"
# Packet rc3 R1: the last of pl2 R7's three forms at PostToolUse, where neither line fits.
UNCONFIRMED_SHORT = "RESPAWN unconfirmed: run the close again in the foreground."


def _respawn_close(cmd) -> bool:
    """A respawn close: a RESPAWN_CMDS spelling and `--respawn` in a Bash command (the one
    test `_confirm` and the background refusal share)."""
    return isinstance(cmd, str) and any(c in cmd for c in RESPAWN_CMDS) and "--respawn" in cmd


def _background_close(payload: dict) -> bool:
    """rc1 R1: a Bash call run with `run_in_background` true whose command is a respawn close."""
    ti = payload.get("tool_input") or {}
    return (payload.get("tool_name") == "Bash" and isinstance(ti, dict)
            and ti.get("run_in_background") is True and _respawn_close(ti.get("command")))


def _unconfirmed_line(payload: dict, env) -> str | None:
    """rc1 R2: the main thread's line while `respawn.json` parses, names this session and a
    non-empty chain, and `respawn-main.json` is absent, does not parse or names other bytes;
    None otherwise, for a helper's payload, and on any fault reading either file. Never raises."""
    try:
        sid = payload.get("session_id")
        if payload.get("agent_id") or not isinstance(sid, str):
            return None
        sdir = _session_dir(sid, env, fallback=False)
        if sdir is None:
            return None
        raw = (sdir / MARKER).read_bytes()
        mark = json.loads(raw)
        if not isinstance(mark, dict) or mark.get("session") != sid:
            return None
        chain = mark.get("chain")
        if not isinstance(chain, str) or not chain:
            return None
        try:
            conf = json.loads((sdir / CONFIRMED).read_bytes())
        except FileNotFoundError:
            conf = None
        except (ValueError, RecursionError):        # a confirm that does not parse names none
            conf = None
        if (isinstance(conf, dict)
                and conf.get("marker_sha256") == hashlib.sha256(raw).hexdigest()):
            return None
        f = mark.get("charter")
        return UNCONFIRMED.format(
            f=f if isinstance(f, str) and _SAFE_PATH.match(f) else UNSAFE_CHARTER)
    except Exception:                                   # noqa: BLE001
        return None


def _confirm(payload: dict, sdir: Path) -> None:
    """respawn-r1 §3.2 step 5: a main-thread Bash call that ran `agentik-session checkpoint
    --respawn` (or `agentik session checkpoint`, or the pre-rename spelling: RESPAWN_CMDS)
    writes `respawn-main.json` {at, marker_sha256} when the marker was written at
    or after this call's own PreToolUse stamp; none without `activity.json`. The first
    confirm of a sitting writes `respawn-first.json` {session, at: the marker's `written`}
    before it, once (nw6b H2). Never raises."""
    try:
        cmd = (payload.get("tool_input") or {}).get("command")
        if payload.get("tool_name") != "Bash" or not _respawn_close(cmd):
            return
        at = _load_json(sdir / ACTIVITY).get("at")
        raw = (sdir / MARKER).read_bytes()
        written = json.loads(raw).get("written")
        if not (_num(at) and _num(written)) or written < at:
            return
        if not (sdir / FIRST_MARK).exists():    # nw6b H2: the ceiling's moment, never moved
            store._write_private(sdir / FIRST_MARK, json.dumps(
                {"session": sdir.name, "at": written}))
        store._write_private(sdir / CONFIRMED, json.dumps(
            {"at": time.time(), "marker_sha256": hashlib.sha256(raw).hexdigest()}))
    except Exception:                                   # noqa: BLE001
        pass


# Packet rc2 R2 to R4: the main thread's background Bash jobs. A record is written at the
# call's PostToolUse, removed by the prompt that carries the job's notice, and a foreground
# RESPAWN close is refused once while a record stands that no close was yet refused for: the
# launcher's restart ends a job still running, and only the sitting knows whether it ended.
NOTICE_OPEN = "<task-notification>"
NOTICE_CLOSE = "</task-notification>"


def _blocks(text: str, open_: str, close: str, bare: bool = False) -> list:
    """Each span from an `open_` to the first `close` after it, as a lazy regex finds them,
    in time linear in `text` (packet pl2 R7: a prompt of unclosed openings cost seconds).
    With no `close` after an opening none follows either, so the scan stops. `bare`: a span
    holding a `<` is none, the search going on from that `<` (`[^<]*` in a regex)."""
    out, i = [], 0
    while (i := text.find(open_, i)) >= 0:
        start = i + len(open_)
        if bare:
            j = text.find("<", start)
            if j < 0:
                break
            if text.startswith(close, j):
                out.append(text[start:j])
                i = j + len(close)
            else:
                i = j
            continue
        j = text.find(close, start)
        if j < 0:
            break
        out.append(text[start:j])
        i = j + len(close)
    return out


def _tag_values(block: str, tag: str) -> list:
    """`<tag> value </tag>` values in a block, stripped, with no `<` inside (rc2's regex)."""
    return [v.strip() for v in _blocks(block, f"<{tag}>", f"</{tag}>", bare=True)]
JOBS_NAMED = 5                      # the start times the refusal names, then `and N more`


def _job_open(payload: dict, sdir: Path) -> None:
    """rc2 R2: a main-thread Bash call whose `tool_response` is an object with a non-empty
    string `backgroundTaskId`, or whose `tool_input.run_in_background` is true, writes
    `jobs/<tool_use_id>` {at, task}, for an id `calls/` accepts. Never raises."""
    try:
        tid = payload.get("tool_use_id")
        if (payload.get("agent_id") or payload.get("tool_name") != "Bash"
                or not isinstance(tid, str) or not _SID.match(tid)):
            return
        resp, ti = payload.get("tool_response"), payload.get("tool_input")
        task = resp.get("backgroundTaskId") if isinstance(resp, dict) else None
        task = task if isinstance(task, str) and task else None
        if task is None and not (isinstance(ti, dict) and ti.get("run_in_background") is True):
            return
        rec = {"at": time.time(), "task": task}
        if isinstance(ti, dict) and gate_wait_call(ti.get("command")):
            rec["watcher"] = True                       # nw2 R6: never asked about at a close
        store._write_private(sdir / JOBS / tid, json.dumps(rec))
    except Exception:                                   # noqa: BLE001
        pass


_WAIT_WORDS = (("agentik-session", "gate", "wait"), ("claude-session", "gate", "wait"),
               ("agentik", "session", "gate", "wait"))


def gate_wait_call(cmd) -> bool:
    """nw2 R6: a command that is one `gate wait`, the watcher: the launcher's name (a path
    to it too) then `gate wait`, after any `NAME=value` words, with no shell operator, no
    redirection and no substitution. Any other command is a job the close asks about."""
    if not isinstance(cmd, str) or any(c in cmd for c in ";&|<>`$()\n\\"):
        return False
    try:
        words = shlex.split(cmd)
    except ValueError:
        return False
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    if not words:
        return False
    words[0] = os.path.basename(words[0])
    return any(tuple(words[:len(w)]) == w for w in _WAIT_WORDS)


def _jobs_open(sdir: Path) -> list:
    """The records under `jobs/`, [(path, the object or {} when it does not parse)], by name;
    a temp file (a leading dot) is none. [] when the folder is absent."""
    try:
        paths = sorted(p for p in (sdir / JOBS).iterdir() if not p.name.startswith("."))
    except FileNotFoundError:
        return []
    return [(p, _load_json(p)) for p in paths]


def _jobs_notice(payload: dict, env) -> None:
    """rc2 R3: each `<task-notification>` block of a main-thread prompt removes the record its
    `<tool-use-id>` names, or whose `task` its `<task-id>` names, whatever its status. A
    prompt with no block costs one substring test, one with blocks a scan linear in its
    length (pl2 R7); a fault leaves the records."""
    try:
        prompt = payload.get("prompt")
        if not (isinstance(prompt, str) and NOTICE_OPEN in prompt) or payload.get("agent_id"):
            return
        sdir = _session_dir(payload.get("session_id"), env, fallback=False)
        if sdir is None:
            return
        calls, tasks = set(), set()
        for block in _blocks(prompt, NOTICE_OPEN, NOTICE_CLOSE):
            calls.update(_tag_values(block, "tool-use-id"))
            tasks.update(_tag_values(block, "task-id"))
        calls.discard("")
        tasks.discard("")
        if not (calls or tasks):
            return
        for p, rec in _jobs_open(sdir):
            if p.name in calls or (isinstance(rec.get("task"), str) and rec["task"] in tasks):
                p.unlink(missing_ok=True)
    except Exception:                                   # noqa: BLE001
        pass


def _hhmm(at) -> str:
    try:
        return time.strftime("%H:%M", time.localtime(at)) if _num(at) else "?"
    except (OverflowError, OSError, ValueError):
        return "?"


def _jobs_out_line(payload: dict, env) -> str | None:
    """rc2 R4: for the main thread's foreground respawn close (rc1's predicate; a background
    one met rc1's refusal first), while a record under `jobs/` has no `asked`: the line, and
    each such record gains `asked`. None for every other call, when every record was asked,
    and on any fault, so this guard's failure passes the call."""
    try:
        ti = payload.get("tool_input")
        if (payload.get("agent_id") or payload.get("tool_name") != "Bash"
                or not isinstance(ti, dict) or ti.get("run_in_background") is True
                or not _respawn_close(ti.get("command"))):
            return None
        sdir = _session_dir(payload.get("session_id"), env, fallback=False)
        if sdir is None:
            return None
        recs = [(p, rec) for p, rec in _jobs_open(sdir) if rec.get("watcher") is not True]
        if not any("asked" not in rec for _, rec in recs):
            return None
        ats = sorted((rec.get("at") for _, rec in recs),
                     key=lambda a: (0, a) if _num(a) and a == a else (1, 0))
        n = len(ats)
        times = ", ".join(_hhmm(a) for a in ats[:JOBS_NAMED])
        if n > JOBS_NAMED:
            times += f" and {n - JOBS_NAMED} more"
        line = (f"agentik-session: {n} background {'job' if n == 1 else 'jobs'} of this "
                f"sitting {'is' if n == 1 else 'are'} not known to have ended (started "
                f"{times}), and the launcher's restart ends any still running. A job whose "
                "notice has already come has ended: where each one's has, run the close again "
                "now rather than wait, since a notice already delivered never comes again and "
                "an unattended sitting that waits for one is never woken. Else wait for each "
                "one's notice; or, where every one has ended or may be cut, run the close "
                "again and it passes.")
        now = time.time()
        for p, rec in recs:
            if "asked" not in rec:
                store._write_private(p, json.dumps({**rec, "asked": now}))
        return line
    except Exception:                                   # noqa: BLE001
        return None


def post_tool_use(payload: dict, env=None) -> dict:
    """The edit gate's outcome (gc1 R2, before a helper's early return), the handler below and
    the outcome said after it (R3), then the gate's inbox lines, the whole under MAX_OUT
    (S38)."""
    env = os.environ if env is None else env
    waiting = instructionguard.post(payload, env)     # held on disk first (brief 3 H1)
    out = _with_changed(payload, env, _post_tool_use(payload, env), waiting)
    return _with_gate(out, "PostToolUse", _gate_lines(payload, env, "PostToolUse", out, False,
                                                      line=_line_take(payload, env, out=out)))


def _with_changed(payload: dict, env, out: dict, waiting: list,
                  event: str = "PostToolUse") -> dict:
    """gc1 R3, brief 2 F2: the gated files' changes that wait, said once after the handler's
    own words (the checkpoint and respawn lines keep their place), to the model and in
    `systemMessage`, where the whole fits MAX_OUT; then their waiting files removed (H2).
    Where it does not fit they wait for the main thread's next PostToolUse or
    UserPromptSubmit."""
    if not waiting or payload.get("agent_id"):
        return out
    try:
        model, owner = instructionguard.said(waiting, env, event)
        new = json.loads(json.dumps(out)) if out else {}
        hso = new.setdefault("hookSpecificOutput", {})
        ctx = hso.get("additionalContext") or ""
        hso["hookEventName"] = event
        hso["additionalContext"] = f"{ctx}\n\n{model}" if ctx else model
        new["systemMessage"] = (new["systemMessage"] + "\n" if new.get("systemMessage")
                                else "") + owner
        if len(json.dumps(new)) <= MAX_OUT:
            instructionguard.taken(payload, env, waiting)     # never raises
            return new
    except Exception:                                   # noqa: BLE001 - held: said later
        pass
    return out


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
        _job_open(payload, sdir)                         # rc2 R2: never raises
    line = _ran_unconfirmed(payload, env, sdir)          # rc3 R2: read first, it only reads
    return _with_respawn(_post_meter(payload, env, sdir,
                                     room=UNCONFIRMED_SHORT if line else None), line)


def _ran_unconfirmed(payload: dict, env, sdir: Path | None) -> str | None:
    """pl2 R7: rc1's `RESPAWN unconfirmed:` line for the main thread's Bash call that left this
    session's chained marker behind, written at or after the call's own PreToolUse stamp,
    with no confirm of its bytes once `_confirm` has run: a close run from a script, whose
    command names no `checkpoint --respawn`, in a foreground call no prompt follows. None
    otherwise and on any fault. Never raises."""
    try:
        if sdir is None or payload.get("agent_id") or payload.get("tool_name") != "Bash":
            return None
        line = _unconfirmed_line(payload, env)
        if line is None:
            return None
        at = _load_json(sdir / ACTIVITY).get("at")
        written = _load_json(sdir / MARKER).get("written")    # the stamp, as _confirm reads it
        return line if _num(at) and _num(written) and written >= at else None
    except Exception:                                   # noqa: BLE001
        return None


def _after(out: dict, line: str) -> dict:
    """The handler's context, then `line` (pl2 R7's pair, as `_with_respawn` says it)."""
    ctx = ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return {"hookSpecificOutput": {**((out or {}).get("hookSpecificOutput") or {}),
                                   "hookEventName": "PostToolUse",
                                   "additionalContext": f"{ctx}\n\n{line}" if ctx else line}}


def _with_respawn(out: dict, line: str | None) -> dict:
    """The handler's context, then the respawn line (pl2 R7) in the first of three forms
    whose pair fits MAX_OUT (packet rc3 R1): the line as given, the line with UNSAFE_CHARTER
    for the path, UNCONFIRMED_SHORT; where none fits, the handler's output."""
    if not line:
        return out
    for form in (line, UNCONFIRMED.format(f=UNSAFE_CHARTER), UNCONFIRMED_SHORT):
        new = _after(out, form)
        if len(json.dumps(new)) <= MAX_OUT:
            return new
    return out


def _post_meter(payload: dict, env, sdir: Path | None, room: str | None = None) -> dict:
    """The main thread's meter at PostToolUse (§2.2), and the CHECKPOINT line by D13; under a
    launcher its line leaves `room` where a spelling of the charter can (packet rc3 R2)."""
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
    if not speak:
        meter.save(sdir, m, st)
        if off or m.used_pct >= 100.0 * float(m.checkpoint_at):    # r1 F1: D13's, as _signal
            return {}
        now = _now()
        if not _meter_due(sdir, _meter_minutes(sdir), now, prompt=False):
            return {}
        _meter_stamp(sdir, now, True)
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                       "additionalContext": _meter_words(m.as_dict())}}
    out = _speaking(payload, env, sdir, m, resolved, room)
    n = _gate_open_count(env) if out and CHAIN_RE.match(str(env.get(CHAIN_VAR) or "")) else 0
    if n and len(json.dumps(_after(out, gate.gate_words(n)))) <= MAX_OUT:
        out = _after(out, gate.gate_words(n))           # nw2 R6: the jobs cross, unwaited
    meter.save(sdir, m, st)                 # rr5a F1: the band is spent once its line is made
    return out


def _speaking(payload: dict, env, sdir: Path, m, resolved: dict, room: str | None) -> dict:
    """The CHECKPOINT line of a PostToolUse that speaks (D13); rr5a R4, R5 and review 1's F1:
    a records read that got no answer costs the charter's path alone."""
    if not discipline(resolved.get("session")):                # st1 R5, C1
        return _checkpoint_out(m, None)
    chained = CHAIN_RE.match(str(env.get(CHAIN_VAR) or ""))       # F4: cli.py's check
    d = _charter(resolved)
    a = records.answer(payload.get("cwd"))            # rr5a R2: only where the line speaks
    s = records.state(a)
    if records.failed(a):                             # F1: the pin's line with no path
        return _checkpoint_out(m, NO_CHARTER, [NO_CHARTER] if chained else None, room=room)
    if s in ("unset", "broken"):                      # rr5a R5: the waiver's form
        return _checkpoint_out(m, None)
    if s == "out" and not d.startswith("?"):          # rr5a R4: the absolute path
        f = records.folder(a, d)
        return _checkpoint_out(m, f if _SAFE_PATH.match(f) else NO_CHARTER,
                               _charter_file_out(sdir, f) if chained else None, room=room)
    return _checkpoint_out(m, d, _charter_file(payload.get("cwd"), sdir, d) if chained else None,
                           room=room)


def post_tool_use_failure(payload: dict, env=None) -> dict:
    """A failed tool call (S20 ruling 2): a helper's closes its open call and stamps
    `helper-activity.json`; the main thread's writes nothing. It says nothing."""
    env = os.environ if env is None else env
    instructionguard.post(payload, env, take=False)   # gc1 R2, held (F1); the shim drops output
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
    """The main thread's turn end (respawn-r1 §3.3): `turn-ended.json` {at}; then (packet
    nw4b R3, R4) each helper's stamp under `backs/` is read, and with at least one the
    coordinator's occupancy is read once, one `back` line a stamp is appended to the admission
    ledger and each stamp read is removed. A helper's payload (agent_id) writes nothing and
    reads no stamp. It never blocks and never raises: dispatch prints nothing for it."""
    if not payload.get("agent_id"):
        env = os.environ if env is None else env
        _stamp(payload, env, TURN_ENDED, {"at": time.time()})
        _backs(payload, env)
    return {}


# ---- a hand-back's cost (packet nw4b-back-measure; hq design/31 item 19) --------------------

BACKS = "backs"     # `backs/<agent_id>.json` {at, before}: a helper's end, until the turn's end


def _occupancy(sdir: Path, env) -> int | None:
    """R1: the main thread's context occupancy now, in tokens: the meter's own reader over a
    copy of the saved `own` state, on the transcript `meter.json` names, and its
    `last_context`. It saves nothing, so `meter.json` and `meter-state.json` keep their bytes.
    None where it cannot be read (no meter, no transcript, a fault); never raises."""
    try:
        tp = ((meter.load(sdir) or {}).get("transcript") or {}).get("path")
        if not isinstance(tp, str) or not tp:
            return None
        own = meter.load_state(sdir).get("own")
        st = copy.deepcopy(own) if isinstance(own, dict) else meter._fresh()
        got = meter._scan(Path(tp), st, meter.limits_for(sdir, env).get("models"))
        ctx = got.get("last_context") if isinstance(got, dict) else None
        if isinstance(ctx, bool) or not isinstance(ctx, int) or ctx < 0:
            return None
        return ctx
    except Exception:                                   # noqa: BLE001 - a measure, never a crash
        return None


def _spawned(sid: str, aid: str, env) -> bool:
    """nw4c R1: a `spawn` line of session `sid` names `aid`, in the ledger or its rotated file,
    each a regular file read once from its last 8 MiB, never blocking, on the keys as `_append`
    writes them. The engine's own agents have none; a file not read is no mark. It may raise."""
    from . import admission
    keys = (f'"session": "{sid}"'.encode(), b'"kind": "spawn"', f'"agentId": "{aid}"'.encode())
    for p in (admission.directory(env) / n for n in (admission.LEDGER, admission.ROTATED)):
        if os.path.isfile(p):                           # a FIFO, a folder or none: no read
            fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
            try:
                tail = os.pread(fd, 1 << 23, max(0, os.fstat(fd).st_size - (1 << 23)))
            finally:
                os.close(fd)
            if any(all(k in ln for k in keys) for ln in tail.splitlines()):
                return True
    return False


def _back_stamp(sdir: Path, aid: str, env) -> None:
    """R2: `backs/<aid>.json` {at, before} at a helper's end; one already there is kept, and
    with no reading no stamp is written. Never raises."""
    try:
        p = sdir / BACKS / f"{aid}.json"
        if os.path.lexists(p) or not _spawned(sdir.name, aid, env):
            return
        before = _occupancy(sdir, env)
        if before is not None:
            store._write_private(p, json.dumps({"at": time.time(), "before": before}))
    except Exception:                                   # noqa: BLE001
        pass


def _a_stamp(d: dict) -> tuple | None:
    at, before = d.get("at"), d.get("before")
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) \
            or not 0 < at < 1e11:
        return None
    if isinstance(before, bool) or not isinstance(before, int) or before < 0:
        return None
    return float(at), before


def _backs(payload: dict, env, measure: bool = True) -> None:
    """R3: at the main thread's turn end, every stamp under `backs/` is read from a regular file
    opened so that it never blocks (`_regular_json`); a FIFO, a folder or a name that is not
    `<id>.json` is passed over and left. With at least one stamp the occupancy is read once
    and `admission.record_backs` appends the lines (R4); each regular file read is removed,
    whether or not a line was written. With `measure` false (a turn StopFailure ended, fix of
    review 1 R1) the same files are removed and nothing is read or written. `backs/` is read
    only where it is a folder and no link (R4 of the fix). Never raises."""
    try:
        sdir = _session_dir(payload.get("session_id"), env, fallback=False)
        if sdir is None:
            return
        bdir = sdir / BACKS
        try:
            if not stat.S_ISDIR(os.lstat(bdir).st_mode):
                return
            names = sorted(os.listdir(bdir))
        except OSError:
            return
        stamps, read = [], []
        for name in names:
            aid = name[:-5] if name.endswith(".json") else ""
            p = bdir / name
            try:
                if not _SID.match(aid) or not stat.S_ISREG(os.lstat(p).st_mode):
                    continue
            except OSError:
                continue
            read.append(p)
            got = _a_stamp(_regular_json(p)) if measure else None
            if got is not None:
                stamps.append((aid, *got))
        try:
            after = _occupancy(sdir, env) if stamps else None
            if after is not None:
                from . import admission                 # admission imports hooks: no cycle
                admission.record_backs(sdir.name, stamps, after, env)
        finally:
            for p in read:
                try:
                    p.unlink()
                except OSError:
                    pass
    except Exception:                                   # noqa: BLE001
        pass


def stop_failure(payload, env=None) -> dict:
    """A turn an API error ended (Claude Code's StopFailure, fired instead of Stop; packet
    S34 ruling 5): `limited.json` {at, error}, the payload's `error` a string cut to 64,
    else null, for the main thread only; a helper's (agent_id) writes nothing. It writes no
    `turn-ended.json`, since no turn ended, and never raises; dispatch prints nothing. It drops
    the main thread's stamps under `backs/` as a Stop that read them would, and writes no
    `back` line, so the failed turn is never measured into a later one (nw4b, fix of review 1
    R1)."""
    try:
        if isinstance(payload, dict) and not payload.get("agent_id"):
            env = os.environ if env is None else env
            err = payload.get("error")
            try:
                _stamp(payload, env, LIMITED,
                       {"at": time.time(), "error": err[:64] if isinstance(err, str) else None})
            finally:
                _backs(payload, env, measure=False)
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
    An automatic one passes too where the session's resolved file waives the block
    (`discipline`, st1 D3 and C1); a file not read blocks, as before. It writes no state."""
    if payload.get("trigger") != "auto":
        return {}
    try:
        sdir = _session_dir(payload.get("session_id"), os.environ if env is None else env,
                            fallback=False)
        session = _load_json(sdir / "resolved.json").get("session") if sdir else None
    except Exception:                                   # noqa: BLE001
        session = None
    if not discipline(session):
        return {}
    return {"decision": "block", "reason": COMPACT_BLOCKED}


def subagent_stop(payload: dict, env=None) -> dict:
    """Packet h4 R2: a helper has ended, so every call it opened has ended, a call a
    rejection ended included, which gets no Post. For a payload whose `agent_id` is
    id-shaped and whose session's folder exists (the payload's id alone, never the
    fallback), each regular file under `calls/` whose JSON object's `agent_id` is that id is
    removed. Another helper's file, one with no `agent_id` (an older plugin's), one that does
    not parse and a directory are left to the launcher's stale bound. Then (packet nw4b R2) it
    stamps the coordinator's occupancy at the helper's end, `backs/<agent_id>.json`, for the
    main thread's next Stop to read; with no reading it writes no stamp. It never raises and
    says nothing: dispatch prints nothing for it (SILENT)."""
    try:
        aid = payload.get("agent_id")
        if not isinstance(aid, str) or not _SID.match(aid):
            return {}
        sdir = _session_dir(payload.get("session_id"),
                            os.environ if env is None else env, fallback=False)
        if sdir is None or not sdir.is_dir():
            return {}
        cdir = sdir / CALLS
        for name in os.listdir(cdir) if cdir.is_dir() else ():
            if name.startswith("."):                    # a write in flight, as `_ready` skips
                continue
            p = cdir / name
            try:
                if stat.S_ISREG(os.lstat(p).st_mode) and _load_json(p).get("agent_id") == aid:
                    p.unlink()
            except Exception:                           # noqa: BLE001 - one file, never the rest
                continue
        _back_stamp(sdir, aid, os.environ if env is None else env)
    except Exception:                                   # noqa: BLE001
        pass
    return {}


def instructions_loaded(payload: dict, env=None) -> dict:
    """Packet g1 R1: one line in the session's `instructions.jsonl` for each instruction file
    Claude Code loads. The event cannot block and its output is discarded; dispatch prints
    nothing for it (SILENT), and the shim drops the process's streams."""
    instructions.record(payload, os.environ if env is None else env)
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
    "instructions-loaded": instructions_loaded,
    "subagent-stop": subagent_stop,
}
# The plugin's shim passes the event as Claude Code names it.
HANDLERS.update({"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use,
                 "UserPromptSubmit": user_prompt_submit,
                 "SessionStart": session_start, "SessionEnd": session_end, "Stop": stop,
                 "StopFailure": stop_failure,
                 "PostToolUseFailure": post_tool_use_failure, "PostToolBatch": post_tool_batch,
                 "PreCompact": pre_compact, "PostModelSwitch": post_model_switch,
                 "InstructionsLoaded": instructions_loaded, "SubagentStop": subagent_stop})
# Stop's stdout is read as a decision, so it gets none: exit 0, empty stdout, always.
SILENT = frozenset({"stop", "Stop", "stop-failure", "StopFailure",
                    "post-model-switch", "PostModelSwitch",    # StopFailure: fire-and-forget
                    "instructions-loaded", "InstructionsLoaded",    # g1 R1: a log, no output
                    "subagent-stop", "SubagentStop"})     # h4 R1: read as a decision, as Stop
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
