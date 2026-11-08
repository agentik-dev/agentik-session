"""`agentik session night`: the overnight loop beside the relay, without its land step.

hq design/07 §2, packet night-1. `run` reads `<repo>/relay/queue.yaml` in the relay's
schema and, for each row in file order, asks admission, stages a worktree, spawns one
`claude -p` builder in it, reads its stream as it comes, and judges the row: `built
<sha>`, `red <reason>`, `skip <reason>`, `refused <reason>` or `limit`. One JSON line per
event goes to the night's `ledger.jsonl`; `status` reads the newest. Standard library,
the 3.9 floor (hq entry 6); every effect is an `Fx` field, as `gate.py`'s.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import admission, gate, resolver, yamlsubset

QUEUE = Path("relay") / "queue.yaml"
CONTEXT_CEILING = 180000          # the builder profile's (hq NICE n3: never budget.context)
STALL = 2700.0                    # the relay's watchdog
POLL = 30.0
WALL = 4 * 3600
ALLOWED_TOOLS = "Bash Edit Write MultiEdit NotebookEdit"     # relay DefaultAllowedTools
DENIED_PUSH_URL = "relay-denies-push"                         # relay DeniedPushURL
HEADING = "# The packet; the repo's CLAUDE.md carries the rules"
CONTINUE = "continue from your charter's act in flight; your commits stand"
ROW_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\Z")
NIGHT = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\Z")


class NightError(Exception):
    """A refusal before the first row: `run` exits 2."""


def _say(line: str) -> None:
    print(line, flush=True)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


@dataclass
class Fx:
    """The loop's effects, each faked in tests. `now` is the wall clock (the ledger's
    stamps, a limit's reset), `mono` the watchdog's; `sleep` is a limit's wait and the
    kill's grace, never the watchdog's poll, which waits on the child itself."""
    now: Callable[[], float] = time.time
    mono: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = _sleep
    popen: Callable = subprocess.Popen
    killpg: Callable = os.killpg
    say: Callable[[str], None] = _say
    env: dict = field(default_factory=lambda: dict(os.environ))
    grace: float = gate.GRACE


def nights_dir(env) -> Path:
    return resolver.state_dir(env) / "nights"


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _key(name: str):
    m = NIGHT.match(name)
    return (m.group(1), int(m.group(2))) if m else None


def new_night(env, now: float) -> tuple[str, Path]:
    """`<state>/nights/<date>-<n>/`, n one past today's highest; its id `night-<date>-<n>`."""
    root = nights_dir(env)
    _mkdir(root)
    os.chmod(root, 0o700)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    n = 1 + max([k[1] for k in map(_key, os.listdir(root)) if k and k[0] == today] or [0])
    while True:
        d = root / f"{today}-{n}"
        try:
            d.mkdir(mode=0o700)
        except FileExistsError:
            n += 1
            continue
        return f"night-{today}-{n}", d


def newest_night(env) -> Path | None:
    try:
        names = [n for n in os.listdir(nights_dir(env)) if _key(n)]
    except OSError:
        return None
    return nights_dir(env) / max(names, key=_key) if names else None


def _append(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(text)


# ---- the queue (ruling 2) --------------------------------------------------------------

HEAD_KEYS = ("version", "defaults", "rows")
DEFAULT_KEYS = ("model", "turns", "context", "usd", "wall", "merge", "verify")
ROW_KEYS = ("id", "packet", "model", "budget", "parked", "merge", "base", "depends_on", "kind",
            "verify")
BUDGET_KEYS = ("turns", "usd", "context", "wall")
_ITEM = re.compile(r"^(\s*)- (.*)$")
_ROWS = re.compile(r"^rows\s*:\s*(#.*)?$")
_WALL = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\Z")


def _bare(line: str) -> str:
    """The line less a comment, by the subset's rule: `#` at the start or after a space."""
    if line.lstrip().startswith("#"):
        return ""
    return line.split(" #", 1)[0].rstrip()


def _joined(lines: list) -> list:
    """Each open flow map joined onto its next lines, so the subset reads it as one line."""
    out, i = [], 0
    while i < len(lines):
        ln, i = lines[i], i + 1
        depth = _bare(ln).count("{") - _bare(ln).count("}")
        if depth > 0:
            ln = _bare(ln)
            while depth > 0 and i < len(lines):
                nxt, i = _bare(lines[i]).strip(), i + 1
                if nxt:
                    ln += " " + nxt
                    depth += nxt.count("{") - nxt.count("}")
        out.append(ln)
    return out


def _load(text: str, where: str) -> dict:
    try:
        return yamlsubset.load(text)
    except yamlsubset.YAMLSubsetError as e:
        raise NightError(f"{where}: {e}") from None


def read_queue(text: str) -> dict:
    """The relay's queue in the subset, `yamlsubset` unchanged: the head is read whole and
    `rows:` is cut at each `- `, every row read on its own with its `- ` blanked. A row is a
    mapping, `version` is 1; else NightError."""
    head, chunks, cur, indent, in_rows = [], [], None, None, False
    for ln in _joined(text.splitlines()):
        if in_rows and ln.strip() and not ln[:1].isspace() and not ln.startswith("#"):
            in_rows = False
        if in_rows:
            m = _ITEM.match(ln)
            if m and (indent is None or len(m.group(1)) == indent):
                indent = len(m.group(1))
                cur = [" " * (indent + 2) + m.group(2)]
                chunks.append(cur)
            elif not ln.strip() or ln.lstrip().startswith("#"):
                pass
            elif cur is None:
                raise NightError(f"queue: a line under rows: before its first '- ': {ln.strip()[:60]}")
            else:
                cur.append(ln)
            continue
        if _ROWS.match(ln):
            in_rows = True
            continue
        head.append(ln)
    q = _load("\n".join(head) + "\n", "queue")
    v = q.get("version")
    if type(v) is not int or v != 1:
        raise NightError(f"queue: version is {v!r}, not 1")
    if chunks:
        q["rows"] = [_load(textwrap.dedent("\n".join(c)) + "\n", f"queue: row {i + 1}")
                     for i, c in enumerate(chunks)]
    rows = q.get("rows") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise NightError("queue: rows is not a list of mappings")
    if not isinstance(q.get("defaults") or {}, dict):
        raise NightError("queue: defaults is not a mapping")
    q["rows"] = rows
    return q


def wall_seconds(v):
    """`<n>h<n>m<n>s` or whole seconds; the default 4h; None when unreadable."""
    if v is None:
        return WALL
    if type(v) is int:
        return v if v > 0 else None
    m = _WALL.match(str(v))
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + s or None


def plan(q: dict, keep, log) -> list:
    """Each row with the defaults under it, in file order; every key the loop does not
    honour is one `log` line. `keep` (the `--rows` ids) keeps those; an unknown one is a
    NightError."""
    d = q.get("defaults") or {}
    for k in q:
        if k not in HEAD_KEYS:
            log(f"ignored {k}")
    for k in d:
        if k not in DEFAULT_KEYS:
            log(f"ignored defaults.{k}")
    out = []
    for r in q["rows"]:
        rid = r.get("id")
        b = r.get("budget") if isinstance(r.get("budget"), dict) else {}
        for k in r:
            if k not in ROW_KEYS:
                log(f"ignored {rid}.{k}")
        for k in b:
            if k not in BUDGET_KEYS:
                log(f"ignored {rid}.budget.{k}")
        out.append({"id": rid, "packet": r.get("packet"), "model": r.get("model", d.get("model")),
                    "turns": b.get("turns", d.get("turns")), "usd": b.get("usd", d.get("usd")),
                    "context": b.get("context", d.get("context")),
                    "wall": b.get("wall", d.get("wall")), "merge": r.get("merge", d.get("merge")),
                    "verify": r.get("verify", d.get("verify")), "base": r.get("base"),
                    "depends_on": r.get("depends_on"), "parked": r.get("parked"),
                    "kind": r.get("kind")})
    if keep:
        unknown = [k for k in keep if k not in {p["id"] for p in out}]
        if unknown:
            raise NightError("--rows: no row " + ", ".join(repr(k)[:66] for k in unknown))
        out = [p for p in out if p["id"] in keep]
    return out


def _num(v) -> bool:
    return type(v) in (int, float) and v > 0


def judge_row(p: dict, repo: Path):
    """(state, reason) for a row that does not run, else None: `refused` or `skip`."""
    rid = p["id"]
    if not isinstance(rid, str) or not ROW_ID.match(rid):
        return "refused", "id"
    if p["parked"]:
        return "skip", "parked"
    if p["kind"] == "orchestrator":
        return "refused", "kind"
    if type(p["context"]) is int and p["context"] > CONTEXT_CEILING:
        return "refused", "context"
    pk = p["packet"]
    if not isinstance(pk, str) or not pk or os.path.isabs(pk):
        return "refused", "packet"
    real, top = os.path.realpath(repo / pk), os.path.realpath(repo)
    if not real.startswith(top + os.sep) or not os.path.isfile(real):
        return "refused", "packet"
    if p["base"] not in (None, "main"):
        return "refused", "base"
    if not isinstance(p["model"], str) or not p["model"]:
        return "refused", "model"
    if type(p["turns"]) is not int or p["turns"] <= 0 or not _num(p["usd"]):
        return "refused", "budget"
    if wall_seconds(p["wall"]) is None:
        return "refused", "wall"
    if p["depends_on"]:
        return "skip", "gate-failed-dependency"
    return None


# ---- admission (ruling 3) --------------------------------------------------------------

def admit(night_id: str, model: str, env) -> dict:
    """Admission's verdict for one spawn, as a helper's is asked: `mode`, `text`, `peak`.
    Admission observes and never refuses; an error is recorded and the row runs."""
    try:
        v = admission.admit(night_id, json.dumps({"subagentType": "night", "model": model}), env)
    except Exception as e:      # noqa: BLE001  (any failure is recorded, never a stop)
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return {k: v.get(k) for k in ("mode", "text", "peak")}


# ---- the stage (ruling 4) --------------------------------------------------------------

def _git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _out(cwd, *args) -> str | None:
    r = _git(cwd, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def stage(repo: Path, rid: str, base: str) -> tuple[Path | None, str | None]:
    """`git -C <repo> worktree add .claude/worktrees/<id> -b <id> <base>`, the hq
    convention; a tree already there is reused only on branch `<id>` and clean, untracked
    files counted. (worktree, head) or (None, why)."""
    wt = repo / ".claude" / "worktrees" / rid
    if wt.exists():
        if _out(wt, "rev-parse", "--abbrev-ref", "HEAD") != rid:
            return None, f"{wt} is not on branch {rid}"
        if _out(wt, "status", "--porcelain", "--untracked-files=all") != "":
            return None, f"{wt} is not clean"
    else:
        r = _git(repo, "worktree", "add", str(Path(".claude") / "worktrees" / rid), "-b", rid, base)
        if r.returncode != 0:
            return None, (r.stderr.strip().splitlines() or ["git worktree add failed"])[-1][:200]
    head = _out(wt, "rev-parse", "HEAD")
    return (wt, head) if head else (None, "no HEAD in the worktree")


def dirty(wt: Path) -> bool:
    return _out(wt, "status", "--porcelain", "--untracked-files=all") != ""


# ---- the spawn (ruling 5) --------------------------------------------------------------

def _usd(v) -> str:
    return f"{round(float(v), 2):g}"


def spawn_argv(model: str, turns: int, usd, sid: str | None = None,
               resume: str | None = None) -> list:
    """The relay's spawn line (`SpawnArgv`); a resume names its session and no new one."""
    a = ["claude", "-p"] + (["--resume", resume] if resume else [])
    a += ["--permission-mode", "auto", "--allowedTools", ALLOWED_TOOLS, "--model", model,
          "--max-turns", str(turns), "--max-budget-usd", _usd(usd),
          "--output-format", "stream-json", "--verbose"]
    return a + (["--session-id", sid] if sid else [])


def push_deny(env: dict, remotes: list) -> dict:
    """The relay's `PushDenyEnv`: each remote's pushurl list reset, then set to
    `relay-denies-push`, through GIT_CONFIG_COUNT after any entries already counted."""
    try:
        n = max(int(env.get("GIT_CONFIG_COUNT", "0")), 0)
    except ValueError:
        n = 0
    out = {k: v for k, v in env.items() if k != "GIT_CONFIG_COUNT" and not (
        n == 0 and (k.startswith("GIT_CONFIG_KEY_") or k.startswith("GIT_CONFIG_VALUE_")))}
    for r in remotes:
        for v in ("", DENIED_PUSH_URL):
            out[f"GIT_CONFIG_KEY_{n}"], out[f"GIT_CONFIG_VALUE_{n}"] = f"remote.{r}.pushurl", v
            n += 1
    if n:
        out["GIT_CONFIG_COUNT"] = str(n)
    return out


def child_env(environ: dict, model: str, turns: int, remotes: list) -> dict:
    """The relay child's environment less RELAY_ROW and the depth: no CLAUDE* and no RELAY_*
    but RELAY_DEVICE_VERBS; the builder profile, its turn cap and model; the push barrier."""
    out = {k: v for k, v in environ.items() if not k.startswith("CLAUDE") and not (
        k.startswith("RELAY_") and k != "RELAY_DEVICE_VERBS")}
    out.update({"CLAUDE_SESSION_PROFILE": "builder", "CLAUDE_SESSION_MAX_TURNS": str(turns),
                "CLAUDE_SESSION_MODEL": model, "RELAY_MEASURE_DEPTH": "1"})
    return push_deny(out, remotes)


def remotes(wt: Path) -> list:
    return (_out(wt, "remote") or "").split()


def prompt(packet_text: str) -> str:
    return f"{HEADING}\n\n{packet_text}"


def start(argv: list, cwd: Path, env: dict, text: str, stderr_path: Path, fx: Fx):
    """The child in its own process group, its stdin fed on a thread and closed."""
    err = os.fdopen(os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab")
    try:
        proc = fx.popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=err, start_new_session=True)
    finally:
        err.close()

    def feed():
        try:
            proc.stdin.write(text.encode())
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass
    threading.Thread(target=feed, daemon=True).start()
    return proc


# ---- the stream (ruling 6) -------------------------------------------------------------

# agentik-relay internal/stream/account.go:25-28 and limit.go's worded needle, as measured.
USAGE_NEEDLES = ("usage limit", "rate limit", "rate_limit", "hit your limit", "5-hour limit reached",
                 "weekly limit reached", "session limit reached")
AUTH_NEEDLES = ("/login", "log in", "login", "expired token", "token expired", "token has expired",
                "oauth token", "invalid api key", "authentication", "unauthorized")
USAGE_WORDS = re.compile(r"(?:^|[^a-z0-9])(hit|reached) your ([a-z0-9-]+) limit(?:[^a-z0-9]|$)")


@dataclass
class Part:
    """What one child's stream said: its last result, its first limit, an auth error."""
    result: dict | None = None
    limit: dict | None = None
    auth: bool = False


def _parse(raw: bytes):
    """One stream line as a JSON object, else None: a stream line is never this tool's state."""
    try:
        obj = json.loads(raw)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _text(result: dict) -> str:
    errs = result.get("errors")
    more = " ".join(str(e) for e in errs) if isinstance(errs, list) else ""
    return f"{result.get('result') or ''} {more}".lower()


def classify(obj: dict, part: Part) -> None:
    t = obj.get("type")
    if t == "rate_limit_event":
        info = obj.get("rate_limit_info") if isinstance(obj.get("rate_limit_info"), dict) else {}
        st = info.get("status")
        if isinstance(st, str) and not st.startswith("allowed") and part.limit is None:
            part.limit = {"kind": str(info.get("rateLimitType") or "unknown"),
                          "resets_at": info.get("resetsAt"), "source": "event"}
    elif t == "result":
        part.result = obj
        if obj.get("is_error") is True and not str(obj.get("subtype") or "").startswith("error_max"):
            text = _text(obj)
            if "api error: 429" in text or any(n in text for n in USAGE_NEEDLES) \
                    or USAGE_WORDS.search(text):
                if part.limit is None:
                    part.limit = {"kind": "unknown", "resets_at": None, "source": "text"}
            elif "api error: 401" in text or any(n in text for n in AUTH_NEEDLES):
                part.auth = True


def read_stream(stdout, path: Path, part: Part) -> None:
    """Each line to `<night>/<id>.jsonl` as it comes, then parsed; non-JSON is skipped."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as fh:
        for raw in iter(stdout.readline, b""):
            fh.write(raw if raw.endswith(b"\n") else raw + b"\n")
            fh.flush()
            obj = _parse(raw)
            if obj is not None:
                classify(obj, part)
