"""The ledger: one line per ended session in `<state>/ledger.jsonl` (§2.2).

The line carries burn-report's `per_session` fields plus the sitting's own, and
nothing else: the writer refuses any key outside LEDGER_KEYS, so message content
can never reach the file. A respawn chain adds two closed line kinds, `restart` and
`stop` (respawn-r1 §3.6); session lines carry no `kind`, and `read` returns only them.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import gitinfo

LEDGER = "ledger.jsonl"
# burn-report's per_session fields (share excepted: it is relative to a report).
PER_SESSION_KEYS = ("session", "project", "turns", "sidechain_turns", "tokens",
                    "median_context", "max_context")
LEDGER_KEYS = ("session", "project", "repo", "turns", "sidechain_turns", "tokens",
               "median_context", "max_context", "profile", "model", "sha_at_end", "dirty",
               "started", "ended", "ceilings", "zone_at_end", "exit_reason", "builders",
               "builders_source",
               # S49: the harness's measures, null when the session has none
               "claude_md_bytes", "rate_limits", "rate_limits_at")
# The chain's line kinds (respawn-r1 §3.6), each a closed key set; `kind` names it.
RESTART_KEYS = ("kind", "chain", "seq", "at", "from_session", "to_session", "profile", "repo",
                "charter", "charter_sha256", "sitting_seconds", "ended_by", "restarts_24h",
                "cap", "model", "start_model")       # S34: the carried model and the start line's
STOP_KEYS = ("kind", "chain", "at", "session", "profile", "repo", "reason", "exit_status",
             "sitting_seconds", "restarts")
CHAIN_KEYS = {"restart": RESTART_KEYS, "stop": STOP_KEYS}


class LedgerError(ValueError):
    pass


def path(state: Path) -> Path:
    return Path(state) / LEDGER


def append(state: Path, entry: dict) -> Path:
    """Append one line with exactly LEDGER_KEYS (absent ones null). Refuses others."""
    unknown = sorted(set(entry) - set(LEDGER_KEYS))
    if unknown:
        raise LedgerError("ledger refuses unknown keys: " + ", ".join(unknown))
    return _append_line(state, json.dumps({k: entry.get(k) for k in LEDGER_KEYS},
                                          ensure_ascii=False))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kind(d: dict) -> str | None:
    k = d.get("kind")
    return k if isinstance(k, str) and k in CHAIN_KEYS else None


def append_chain(state: Path, entry: dict) -> Path:
    """Append one restart or stop line with exactly its kind's keys (absent ones null);
    `at`, when the entry has none, is written as `ended` is. Refuses an unknown kind or
    key (LedgerError), and then writes nothing."""
    kind = _kind(entry)
    if kind is None:
        raise LedgerError("ledger refuses an unknown line kind: %r" % str(entry.get("kind"))[:40])
    keys = CHAIN_KEYS[kind]
    unknown = sorted(set(entry) - set(keys))
    if unknown:
        raise LedgerError(f"ledger refuses unknown keys for a {kind} line: " + ", ".join(unknown))
    line = {k: entry.get(k) for k in keys}
    if line["at"] is None:
        line["at"] = _now()
    return _append_line(state, json.dumps(line, ensure_ascii=False))


def _last_byte(p: Path) -> bytes | None:
    """The file's last byte; None when it cannot be read (the caller then writes the
    newline anyway: an empty line is skipped by every reader)."""
    try:
        with open(p, "rb") as f:
            f.seek(-1, os.SEEK_END)
            return f.read(1)
    except OSError:
        return None


def _append_line(state: Path, line: str) -> Path:
    p = path(state)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        data = (line + "\n").encode()
        if os.fstat(fd).st_size and _last_byte(p) != b"\n":
            data = b"\n" + data        # a torn tail never swallows this line (S20a A-F1)
        os.write(fd, data)
    finally:
        os.close(fd)
    return p


def read(state: Path, since: str | None = None) -> list[dict]:
    """The ledger's session lines (those without `kind`), those ended on or after
    `since` (YYYY-MM-DD)."""
    out = []
    try:
        lines = path(state).read_text().splitlines()
    except OSError:
        return out
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(d, dict) or "kind" in d:
            continue
        if since and str(d.get("ended") or "")[:10] < since:
            continue
        out.append(d)
    return out


def read_chains(state: Path, since: str | None = None) -> list[dict]:
    """The chain's restart and stop lines, those at or after `since` (YYYY-MM-DD), for
    `report --chains`; lenient as `read` is. The cap reads `restarts_in`, never this."""
    out = []
    try:
        lines = path(state).read_text().splitlines()
    except (OSError, ValueError):
        return out
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(d, dict) or _kind(d) is None:
            continue
        if since and str(d.get("at") or "")[:10] < since:
            continue
        out.append(d)
    return out


def _epoch(at) -> float | None:
    if not isinstance(at, str):
        return None
    try:
        t = datetime.fromisoformat(at)
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).timestamp()


def restarts_in(state: Path, chain: str, now: float, hours: float = 24) -> int:
    """The chain's restarts in the `hours` before `now` (epoch seconds), for the cap. It
    fails closed: no file is 0, any other read error raises LedgerError; a restart line
    counts when its `at` is in the window or unparsable; a line that is not a JSON object
    counts when it holds the chain's name as JSON (`json.dumps(chain)`)."""
    try:
        raw = path(state).read_bytes()
    except FileNotFoundError:
        return 0
    except OSError as e:
        raise LedgerError(f"the ledger cannot be read: {e}") from None
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as e:
        raise LedgerError(f"the ledger cannot be read: {e}") from None
    name, floor, n = json.dumps(chain), now - hours * 3600, 0
    for line in lines:
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            d = None
        if not isinstance(d, dict):
            n += name in line
        elif d.get("kind") == "restart" and d.get("chain") == chain:
            t = _epoch(d.get("at"))
            n += t is None or t >= floor
    return n


def _git(cwd, *args) -> str | None:
    rc, out = gitinfo._git(str(cwd), *args)
    return out if rc == 0 else None


def git_state(cwd) -> tuple[str | None, str | None, bool | None]:
    """(repo toplevel, sha, dirty); each null when git cannot say."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    sha = _git(cwd, "rev-parse", "HEAD")
    status = _git(cwd, "status", "--porcelain")
    return ((top or "").strip() or None, (sha or "").strip() or None,
            None if status is None else bool(status.strip()))


def entry_for(m: dict, *, project, profile, cwd, exit_reason, claude_md_bytes=None,
              rate_limits=None, rate_limits_at=None) -> dict:
    """A ledger line from a meter dict (burn-report's numbers are the total's)."""
    repo, sha, dirty = git_state(cwd) if cwd else (None, None, None)
    t = m.get("total") or {}
    return {
        "session": m.get("session_id"), "project": project, "repo": repo,
        "turns": t.get("turns"), "sidechain_turns": t.get("sidechain_turns"),
        "tokens": t.get("tokens"), "median_context": t.get("median_context"),
        "max_context": t.get("max_context"), "profile": profile, "model": m.get("model"),
        "sha_at_end": sha, "dirty": dirty, "started": m.get("started"),
        "ended": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ceilings": m.get("ceilings"), "zone_at_end": m.get("zone"),
        "exit_reason": exit_reason,
        "builders": [{"agent": b.get("agent"), "turns": b.get("turns"),
                      "tokens": b.get("tokens")} for b in m.get("builders") or []],
        "builders_source": m.get("builders_source") or "none",
        "claude_md_bytes": claude_md_bytes, "rate_limits": rate_limits,
        "rate_limits_at": rate_limits_at,
    }


def table(rows: list[dict]) -> str:
    head = ("ended", "session", "project", "turns", "tokens", "max_ctx", "zone", "exit")
    body = [(str(r.get("ended") or "")[:16], str(r.get("session") or "")[:8],
             str(r.get("project") or "")[-24:], str(r.get("turns")), str(r.get("tokens")),
             str(r.get("max_context")), str(r.get("zone_at_end")), str(r.get("exit_reason")))
            for r in rows]
    return _columns(head, body)


def chain_table(rows: list[dict]) -> str:
    """`report --chains`: one row per restart or stop line; `why` is a restart's
    `ended_by` or a stop's `reason`, `restarts` a restart's `restarts_24h/cap`."""
    head = ("at", "kind", "chain", "seq", "session", "why", "secs", "restarts")
    body = []
    for r in rows:
        re_ = r.get("kind") == "restart"
        body.append((str(r.get("at") or "")[:16], str(r.get("kind")),
                     str(r.get("chain") or "")[:24], str(r.get("seq")) if re_ else "-",
                     str((r.get("from_session") if re_ else r.get("session")) or "")[:8],
                     str(r.get("ended_by") if re_ else r.get("reason")),
                     str(r.get("sitting_seconds")),
                     f"{r.get('restarts_24h')}/{r.get('cap')}" if re_ else str(r.get("restarts"))))
    return _columns(head, body)


def _columns(head: tuple, body: list) -> str:
    widths = [max(len(x) for x in col) for col in zip(head, *body)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    return "\n".join(fmt.format(*r).rstrip() for r in [head, *body])
