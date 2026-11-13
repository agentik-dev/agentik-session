"""`agentik session unattended`: the unattended loop beside the relay.

hq design/07 §2. `run` reads `<repo>/relay/queue.yaml` in the relay's
schema and, for each row in file order, asks admission, stages a worktree, spawns one
`claude -p` builder in it, reads its stream as it comes, and judges the row: `built
<sha>`, `red <reason>`, `skip <reason>`, `refused <reason>` or `limit`. One JSON line per
event goes to the run's `ledger.jsonl`; `status` reads the newest. Standard library,
the 3.9 floor (hq entry 6); every effect is an `Fx` field, as `gate.py`'s.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import admission, gate, resolver, yamlsubset
from .shellreader import _SHELLS, _commands, _substituted  # packet u3 R5: the hook's reader

QUEUE = Path("relay") / "queue.yaml"
CONTEXT_CEILING = 180000          # the builder profile's (hq NICE n3: never budget.context)
STALL = 2700.0                    # the relay's watchdog
POLL = 30.0
WALL = 4 * 3600
ALLOWED_TOOLS = "Bash Edit Write MultiEdit NotebookEdit"     # relay DefaultAllowedTools
DENIED_PUSH_URL = "relay-denies-push"                         # relay DeniedPushURL
# Packet u2 R1: the child's prompt over the packet (the audit's finding C2, verbatim).
PROMPT = (
    "# You are one unattended builder; the packet below is your whole task\n\n"
    "You run headless (`claude -p`): a message with no tool call ends the sitting, and nobody "
    "reads it until the run is over. Build every act the packet lists, one commit per act, and "
    "end your turn only when the last act is committed and the tree is clean, or when nothing "
    "can move; then say why in the charter's handover. An error, a timeout or a failing test is "
    "work: diagnose it and get past it. A hook's denial and the packet's wall are deliberate: "
    "leave them and take another way. Do each act yourself in the foreground: no agent, no "
    "background command, no wait on a notification.")
# Packet u2 R4: what a limit's resume says, sent after the reset.
CONTINUE = (
    "You stopped at the account's usage limit, which has now reset; your commits stand. Read "
    "your charter's done-ness list, finish each unchecked act of the packet, run the packet's "
    "acceptance lines, and commit. End only when every acceptance line passes, or say what "
    "blocks it in the charter's handover.")
# Packet u2 R5: a child's effort, never the interactive default; the relay's queue key and values.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
BUILDER_EFFORT = "high"          # when the builder profile names no level the loop knows
ROW_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}\Z")
RUN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\Z")


class UnattendedError(Exception):
    """A refusal before the first row: `run` exits 2."""


def _say(line: str) -> None:
    print(line, flush=True)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _ps() -> str | None:
    """`ps -axo command=`, every process's command line; None when ps fails."""
    try:
        r = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True,
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def gate_argv() -> list:
    """`gate`, as `gate.spawn_serve` reaches the runner: this interpreter, `-I`, the runner
    beside this package; never PATH."""
    return [sys.executable, "-I", str(Path(__file__).resolve().parent.parent / "agentik-session"),
            "gate"]


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
    ps: Callable[[], str | None] = _ps
    gate: list = field(default_factory=gate_argv)


# ---- the refusals before the run's folder (rulings 2-4) ----------------------

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)\Z")


def _runs_relay(words: list) -> bool:
    """The command's first words run the relay: `agentik relay run`, or an argv[0] whose
    basename is `agentik-relay` or `relay`, then `run`; never a later word (`grep …`)."""
    head = os.path.basename(words[0]) if words else ""
    if head == "agentik":
        return words[1:3] == ["relay", "run"]
    return head in ("agentik-relay", "relay") and words[1:2] == ["run"]


def relay_running(ps_text: str) -> str | None:
    """The first `ps` line running the relay's own run (`_runs_relay`), as 120 chars; None
    when none does."""
    for ln in ps_text.splitlines():
        if _runs_relay(ln.split()):
            return ln.strip()[:120]
    return None


def land_path(repo: Path, land) -> str | None:
    """`--land`, made absolute, which must be an executable file; else `<repo>/scripts/land`
    when it is one; else None (a `merge-on-green` row ends `built`, `no-land`)."""
    if land is not None:
        p = os.path.abspath(land)
        if not (os.path.isfile(p) and os.access(p, os.X_OK)):
            raise UnattendedError(f"land: {p[:200]} is not an executable file")
        return p
    p = repo / "scripts" / "land"
    return str(p) if p.is_file() and os.access(p, os.X_OK) else None


def until_at(text: str, start: float) -> float:
    """`--until`: `HH:MM` is its next local occurrence at or after `start`, and
    `YYYY-MM-DDTHH:MM` is absolute, local; else UnattendedError. `HH:MM` walks forward
    from `start` in whole minutes to the first instant whose local clock reads it, so the
    autumn night's repeated hour is met the first time (mktime's `isdst=-1` may pick
    either); a clock that jumps forward over it (the spring night) takes the jump's end."""
    m = _HHMM.match(text)
    if m:
        want, at, prev = int(m.group(1)) * 60 + int(m.group(2)), -(-int(start) // 60) * 60, None
        if at < start:
            at += 60
        for _ in range(3 * 1440):
            t = time.localtime(at)
            cur = t.tm_hour * 60 + t.tm_min
            step = None if prev is None else (cur - prev) % 1440
            if cur == want or (step is not None and 1 < step < 720
                               and 0 < (want - prev) % 1440 < step):
                return float(at)
            prev, at = cur, at + 60
    try:
        return time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M")[:8] + (-1,))
    except (ValueError, OverflowError):
        raise UnattendedError(f"until: {text[:40]!r} is neither HH:MM nor YYYY-MM-DDTHH:MM") from None


def refusals(repo: Path, fx: Fx, until, land) -> tuple:
    """Ruling 2: (until's epoch or None, the land path or None), or UnattendedError; `ps` read
    once."""
    at = until_at(until, fx.now()) if until is not None else None
    lp = land_path(repo, land)
    text = fx.ps()
    if text is None:
        raise UnattendedError("ps: `ps -axo command=` failed")
    line = relay_running(text)
    if line:
        raise UnattendedError(f"relay-running: {line}")
    return at, lp


def runs_dir(env) -> Path:
    return resolver.state_dir(env) / "unattended"


def _mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True, mode=0o700)


def _key(name: str):
    m = RUN.match(name)
    return (m.group(1), int(m.group(2))) if m else None


def new_run(env, now: float) -> tuple[str, Path]:
    """`<state>/unattended/<date>-<n>/`, n one past today's highest; its id `<date>-<n>`."""
    root = runs_dir(env)
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
        return f"{today}-{n}", d


def newest_run(env) -> Path | None:
    try:
        names = [n for n in os.listdir(runs_dir(env)) if _key(n)]
    except OSError:
        return None
    return runs_dir(env) / max(names, key=_key) if names else None


def _append(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as fh:
        fh.write(text)


# ---- the queue (ruling 2) --------------------------------------------------------------

HEAD_KEYS = ("version", "defaults", "rows")
DEFAULT_KEYS = ("model", "turns", "context", "usd", "wall", "merge", "verify", "effort")
ROW_KEYS = ("id", "packet", "model", "budget", "parked", "merge", "base", "depends_on", "kind",
            "verify", "effort")
BUDGET_KEYS = ("turns", "usd", "context", "wall")
_ITEM = re.compile(r"^(\s*)- (.*)$")
_ROWS = re.compile(r"^rows\s*:\s*(#.*)?$")
_WALL = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?\Z")


def _scan(line: str) -> tuple:
    """(the line less its comment, its `{` count less its `}`), by the subset's rule
    (`yamlsubset._strip_comment`): text inside "…" and '…' is skipped, so a `''` inside
    single quotes closes and reopens them; a comment is a `#` at the start or after a space
    or a tab (hq NICE n4)."""
    quote, depth = None, 0
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip(), depth
        elif ch in "{}":
            depth += 1 if ch == "{" else -1
    return line.rstrip(), depth


def _bare(line: str) -> str:
    """The line less a comment, outside quotes."""
    return _scan(line)[0]


def _joined(lines: list) -> list:
    """Each open flow map joined onto its next lines, so the subset reads it as one line;
    a quoted `{` or `}` neither opens nor closes one."""
    out, i = [], 0
    while i < len(lines):
        ln, i = lines[i], i + 1
        bare, depth = _scan(ln)
        if depth > 0:
            ln = bare
            while depth > 0 and i < len(lines):
                (nxt, more), i = _scan(lines[i]), i + 1
                if nxt.strip():
                    ln += " " + nxt.strip()
                    depth += more
        out.append(ln)
    return out


def _load(text: str, where: str) -> dict:
    try:
        return yamlsubset.load(text)
    except yamlsubset.YAMLSubsetError as e:
        raise UnattendedError(f"{where}: {e}") from None


def read_queue(text: str) -> dict:
    """The relay's queue in the subset, `yamlsubset` unchanged: the head is read whole and
    `rows:` is cut at each `- `, every row read on its own with its `- ` blanked. A row is a
    mapping, `version` is 1; else UnattendedError."""
    head, chunks, cur, indent, in_rows = [], [], None, None, False
    for ln in _joined(text.splitlines()):
        if (in_rows and ln.strip() and not ln[:1].isspace() and not ln.startswith("#")
                and not ln.startswith("- ")):
            in_rows = False      # a column-0 line that is neither an item nor a comment

        if in_rows:
            m = _ITEM.match(ln)
            if m and (indent is None or len(m.group(1)) == indent):
                indent = len(m.group(1))
                cur = [" " * (indent + 2) + m.group(2)]
                chunks.append(cur)
            elif not ln.strip() or ln.lstrip().startswith("#"):
                pass
            elif cur is None:
                raise UnattendedError(f"queue: a line under rows: before its first '- ': {ln.strip()[:60]}")
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
        raise UnattendedError(f"queue: version is {v!r}, not 1")
    if chunks:
        q["rows"] = [_load(textwrap.dedent("\n".join(c)) + "\n", f"queue: row {i + 1}")
                     for i, c in enumerate(chunks)]
    rows = q.get("rows") or []
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise UnattendedError("queue: rows is not a list of mappings")
    if not isinstance(q.get("defaults") or {}, dict):
        raise UnattendedError("queue: defaults is not a mapping")
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


def _given(*values):
    """The first value that is neither None nor the empty string, else None."""
    for v in values:
        if v is not None and v != "":
            return v
    return None


def plan(q: dict, keep, log) -> list:
    """Each row with the defaults under it, in file order; every key the loop does not
    honour is one `log` line. `keep` (the `--rows` ids) keeps those; an unknown one is a
    UnattendedError."""
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
                    "kind": r.get("kind"),
                    # R5's order, review F9: an empty or null level is no level; a 0 or a
                    # false is a level, refused by judge_row (second review N2)
                    "effort": _given(r.get("effort"), d.get("effort"))})
    if keep:
        unknown = [k for k in keep if k not in {p["id"] for p in out}]
        if unknown:
            raise UnattendedError("--rows: no row " + ", ".join(repr(k)[:66] for k in unknown))
        out = [p for p in out if p["id"] in keep]
    return out


def _num(v) -> bool:
    return type(v) in (int, float) and v > 0


def _packet_file(repo: Path, pk) -> str | None:
    """The packet's real path: relative, inside the repo, a file; else None."""
    if not isinstance(pk, str) or not pk or os.path.isabs(pk):
        return None
    real, top = os.path.realpath(repo / pk), os.path.realpath(repo)
    return real if real.startswith(top + os.sep) and os.path.isfile(real) else None


def judge_row(p: dict, repo: Path, landed=frozenset()):
    """(state, reason) for a row that does not run, else None: `refused` or `skip`. A `base`
    or a `depends_on` id is good when it landed earlier in this run (`landed`)."""
    rid = p["id"]
    if not isinstance(rid, str) or not ROW_ID.match(rid):
        return "refused", "id"
    if p["parked"]:
        return "skip", "parked"
    if p["kind"] == "orchestrator":
        return "refused", "kind"
    if type(p["context"]) is int and p["context"] > CONTEXT_CEILING:
        return "refused", "context"
    if _packet_file(repo, p["packet"]) is None:
        return "refused", "packet"
    if p["base"] not in (None, "main") and not (isinstance(p["base"], str) and p["base"] in landed):
        return "refused", "base"
    if not isinstance(p["model"], str) or not p["model"]:
        return "refused", "model"
    if p.get("effort") is not None and p["effort"] not in EFFORTS:
        return "refused", "effort"
    if type(p["turns"]) is not int or p["turns"] <= 0 or not _num(p["usd"]):
        return "refused", "budget"
    if wall_seconds(p["wall"]) is None:
        return "refused", "wall"
    deps = [p["depends_on"]] if isinstance(p["depends_on"], str) else p["depends_on"]
    if deps and (not isinstance(deps, list)
                 or any(not isinstance(d, str) or d not in landed for d in deps)):

        return "skip", "gate-failed-dependency"
    return None


# ---- admission (ruling 3) --------------------------------------------------------------

def admit(run_id: str, model: str, env) -> dict:
    """Admission's verdict for one spawn, as a helper's is asked: `mode`, `text`, `peak`.
    Admission observes and never refuses; an error is recorded and the row runs."""
    try:
        v = admission.admit(run_id, json.dumps({"subagentType": "unattended", "model": model}), env)
    except Exception as e:      # noqa: BLE001  (any failure is recorded, never a stop)
        return {"error": f"{type(e).__name__}: {e}"[:200]}
    return {k: v.get(k) for k in ("mode", "text", "peak")}


# ---- the stage (ruling 4) --------------------------------------------------------------

def _git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


def _out(cwd, *args) -> str | None:
    r = _git(cwd, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def _status(wt: Path) -> str | None:
    """The tree's porcelain status, untracked files counted, less an untracked `.venv` link
    at its top, as hq's `land` reads it (design/07 §9 risk 4)."""
    out = _out(wt, "status", "--porcelain", "--untracked-files=all")
    return None if out is None else "\n".join(ln for ln in out.splitlines() if ln != "?? .venv")


def _git_why(r: subprocess.CompletedProcess, what: str) -> str:
    """Git's last line on stderr, else `<what> failed`."""
    return (r.stderr.strip().splitlines() or [f"{what} failed"])[-1][:200]


def link_venvs(repo: Path, tree: Path, note: Callable | None = None) -> None:
    """Packet u3 R2: each directory at the top of the main checkout whose name starts with
    `.venv` linked into the tree, absolute, when the tree has nothing by that name. `.venv`
    always (design/07 §9 risk 4: `_status` leaves its link out); another name only when
    `git check-ignore -q` says the tree ignores it, read as the link will stand (a file, not
    a directory), else `note(name)` and no link, so the tree stays clean."""
    try:
        names = sorted(os.listdir(repo))
    except OSError:
        return
    for name in names:
        src = os.path.abspath(os.path.join(repo, name))
        if not name.startswith(".venv") or not os.path.isdir(src) \
                or os.path.lexists(os.path.join(tree, name)):
            continue
        if name != ".venv" and _git(tree, "check-ignore", "-q", name).returncode != 0:
            if note is not None:
                note(name)
            continue
        os.symlink(src, os.path.join(tree, name))


def stage(repo: Path, rid: str, base: str, note: Callable | None = None
          ) -> tuple[Path | None, str | None]:
    """`git -C <repo> worktree add .claude/worktrees/<id> -b <id> <base>`, the hq
    convention; a tree already there is reused only on branch `<id>` and clean, untracked
    files counted. The main checkout's `.venv*` directories linked there (`link_venvs`).
    (worktree, head) or (None, why)."""
    wt = repo / ".claude" / "worktrees" / rid
    if wt.exists():
        if _out(wt, "rev-parse", "--abbrev-ref", "HEAD") != rid:
            return None, f"{wt} is not on branch {rid}"
        if _status(wt) != "":
            return None, f"{wt} is not clean"
    else:
        r = _git(repo, "worktree", "add", str(Path(".claude") / "worktrees" / rid), "-b", rid, base)
        if r.returncode != 0:
            return None, _git_why(r, "git worktree add")
    link_venvs(repo, wt, note)
    head = _out(wt, "rev-parse", "HEAD")
    return (wt, head) if head else (None, "no HEAD in the worktree")


def dirty(wt: Path) -> bool:
    return _status(wt) != ""


# ---- the acceptance lines (packet u2 R2) ---------------------------------------
# The cell as agentik-relay internal/packet/packet.go reads it (`table`, `splitRow`,
# `acceptance`, `expect`), each line judged as night.Holds and gate.rerun judge it.

SH = "/bin/sh"
LINE_LIMIT = 900.0               # effects.Timeout: an acceptance line's limit
CUT_EXIT = 124                   # effects.CutExit: the exit at the limit
UNRUN_EXITS = (126, 127)         # the shell's: not executable, not found (review F2)
LAST_CAP = 200                   # effects.LastCap
OUT_CAP = 65536                  # effects.OutputCap: the tail of each stream read
TEXT_CAP = 400                   # effects.TextCap: a ledger string
PIPE_GRACE = 5.0
CONTINUATIONS = 2                # packet u2 R3: named continuations a row, at most
PASSES = ("green", "same-as-main")
TAIL = ("Continue with the acts that make them hold. If one is blocked, say what blocks it in "
        "the charter's handover.")
_OR_MORE = re.compile(r"^reads (\d+) or more\b", re.A)
_READS = re.compile(r"^reads (`[^`]*`|\S+)", re.A)
_NUMBER = re.compile(r"^(under|exits) (\d+)\b", re.A)
_AS_MAIN = re.compile(r"^as main\b", re.A)
_INT = re.compile(r"^[+-]?\d+\Z", re.A)


class AcceptanceError(ValueError):
    """The packet's acceptance cell cannot be read: the row is refused before its spawn."""


@dataclass(frozen=True)
class Line:
    """One acceptance item: its shell line and what it must show (`reads`, `reads-or-more`,
    `under`, `exits`, `as-main`)."""
    shell: str
    expect: str
    kind: str
    value: str = ""
    n: int = 0


def _split_row(s: str) -> list:
    """`splitRow`: a table row cut at every `|` not escaped as `\\|`."""
    s = s.strip()
    s = s[1:] if s.startswith("|") else s
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    out, start, j = [], 0, 0
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "|":
            out.append(s[start:j])
            start = j + 1
        j += 1
    return out + [s[start:]]


def _unescape(s: str) -> str:
    return s.replace("\\|", "|")


def _expect(shell: str, e: str) -> Line:
    m = _OR_MORE.match(e)
    if m:
        return Line(shell, e, "reads-or-more", m.group(1), int(m.group(1)))
    m = _READS.match(e)
    if m:
        v = _unescape(m.group(1).strip("`"))
        return Line(shell, e, "reads", v, int(v) if _INT.match(v) else 0)
    m = _NUMBER.match(e)
    if m:
        return Line(shell, e, "under" if m.group(1) == "under" else "exits", m.group(2),
                    int(m.group(2)))
    if _AS_MAIN.match(e):
        return Line(shell, e, "as-main")
    raise AcceptanceError(f"`{shell[:80]}`: no expectation (want reads, reads <n> or more, "
                          "under, exits or as main)")


HEADER_ROWS = ("from", "pin", "wall", "may touch", "acceptance", "budget")   # packet.Rows
VERIFY_ROW = "verify"                                                        # packet.VerifyRow


def _header(text: str) -> list:
    """`table`: the header table directly after the title (the first non-blank line, a `# `
    heading), its heading row and rule, then each row's (name, value) while lines open with
    `|`; any other table in the packet is never read."""
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i == len(lines) or not lines[i].startswith("# "):
        raise AcceptanceError("no title: want `# Packet <id>: <title>` as the first line")
    i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i + 1 >= len(lines) or not lines[i].startswith("|") or not lines[i + 1].startswith("|"):
        raise AcceptanceError("no acceptance row: no header table directly after the title")
    rows = []
    for ln in lines[i + 2:]:
        if not ln.startswith("|"):
            break
        c = _split_row(ln)
        name = c[0].strip().lower()
        if len(c) != 2:
            raise AcceptanceError(f"row {name[:40]}: {len(c)} cells, want 2: an unescaped | "
                                  "inside a span splits the row")
        rows.append((name, c[1].strip()))
    return rows


def acceptance(text: str) -> list:
    """The packet's acceptance lines, from its header table's `acceptance` row (`header`: a
    duplicate or an extra row refuses the packet; the rows' order and a missing row other than
    `acceptance` are left to the relay, since they change no cell read): the cell cut at each
    `;` outside a code span, each item a span and an expectation; else AcceptanceError."""
    rows, seen = _header(text), set()
    for name, _ in rows:
        if name not in HEADER_ROWS + (VERIFY_ROW,):
            raise AcceptanceError(f"row {name[:40]}: extra header row")
        if name in seen:
            raise AcceptanceError(f"row {name}: duplicate header row")
        seen.add(name)
    cell = dict(rows).get("acceptance")
    if cell is None:
        raise AcceptanceError("no acceptance row in the packet's header table")
    items, start, inside = [], 0, False
    for j, ch in enumerate(cell):
        if ch == "`":
            inside = not inside
        elif ch == ";" and not inside:
            items.append(cell[start:j])
            start = j + 1
    if inside:
        raise AcceptanceError("unterminated backtick span")
    out = []
    for it in items + [cell[start:]]:
        it = it.strip()
        if not it:
            continue
        if not it.startswith("`"):
            raise AcceptanceError(f"item {len(out) + 1}: no shell span")
        end = it.index("`", 1)
        out.append(_expect(_unescape(it[1:end]), it[end + 1:].strip()))
    if not out:
        raise AcceptanceError("no item")
    return out


# Packet u3 R5: a line that runs make is refused before the row's stage (design/07 §2
# item 4): a make runs only through the gate queue, and the land step runs the check.
MAKES = ("make", "gmake", "gnumake")   # by basename, case-blind (round 1 F5)
SHELL_DEPTH = 3                  # the shells' `-c` texts read, nested
LINE_SHOWN = 80                  # R6: the line in the log, cut
_DASH_C = re.compile(r"^-[A-Za-z]*c[A-Za-z]*\Z")
WHY_MAKE = "a make runs only through the gate queue, and the land step runs the check"


def unbounded(shell: str, depth: int = 0) -> str:
    """Why the line may not run, "" when it may: read with the hook's reader
    (`instructionguard._commands`), it is refused when the reader cannot split it, when a
    word of a simple command, by basename and case-blind, is `make`, `gmake` or `gnumake`
    (round 1 F5; a shell's name is compared case-blind too), or when a shell's `-c` text is,
    to depth SHELL_DEPTH. Once a word after a shell is `-c` (a flag cluster holding `c`),
    every later word of that command is a text, whatever flags sit around it (round 1 F1); a
    word's `$(` text is one too, on the same depth count (F3)."""
    try:
        cmds = list(_commands(shell))
    except ValueError as e:
        return f"the hook's reader cannot split it ({e}), so it may run a make; {WHY_MAKE}"
    for words, outs in cmds:
        if outs is None:                  # a subshell's edge
            continue
        shell_seen = texts = False
        for w in words:
            name = os.path.basename(w).lower()
            if name in MAKES:
                return f"it runs `{os.path.basename(w)}`; {WHY_MAKE}"
            if depth >= SHELL_DEPTH:
                continue
            if texts:
                why = unbounded(w, depth + 1)
                if why:
                    return why
            elif shell_seen and _DASH_C.match(w):
                texts = True
            elif name in _SHELLS:
                shell_seen = True
        if depth >= SHELL_DEPTH:
            continue
        for w in words + outs:            # round 1 F3: a quoted `$(`, a text on the same count
            for text in _substituted(w):
                why = unbounded(text, depth + 1)
                if why:
                    return why
    return ""


def unbounded_item(lines: list) -> str | None:
    """Packet u3 R6: the first unbounded line as the log says it, its item, the line cut at
    LINE_SHOWN and why; else None."""
    for i, ln in enumerate(lines, 1):
        why = unbounded(ln.shell)
        if why:
            return f"item {i} `{ln.shell[:LINE_SHOWN]}`: {why}"
    return None


def early_word(p: dict, repo: Path) -> str | None:
    """Packet u3 R7: why the row's turn will refuse it for its acceptance cell, else None;
    a packet the row's turn refuses for its path is left to that turn."""
    real = _packet_file(repo, p["packet"])
    if real is None:
        return None
    try:
        lines = acceptance(Path(real).read_text(errors="replace"))
    except OSError:
        return None
    except AcceptanceError as e:
        return f"acceptance: {e}"
    why = unbounded_item(lines)
    return f"unbounded: {why}" if why else None


def line_holds(ln: Line, exit_code, last: str) -> bool:
    """`night.Holds`: the expectation against an exit and a last line; `as main` holds on main,
    where a line is its own baseline."""
    t = (last or "").strip()
    n = int(t) if _INT.match(t) else None
    if ln.kind == "reads":
        return t == ln.value
    if ln.kind == "reads-or-more":
        return n is not None and n >= ln.n
    if ln.kind == "under":
        return n is not None and n < ln.n
    if ln.kind == "exits":
        return exit_code == ln.n
    return ln.kind == "as-main"


def _last_of(data: bytes) -> str:
    for ln in reversed(data[-OUT_CAP:].decode(errors="replace").split("\n")):
        if ln.strip():
            return ln.strip()[:LAST_CAP]
    return ""


def _killpg(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_line(cwd: Path, shell: str, env: dict) -> dict:
    """One line under `/bin/sh -c` in cwd, in its own session, cut at LINE_LIMIT (exit 124,
    `cut`), its group killed after; `exit` None and `error` when it could not run."""
    try:
        proc = subprocess.Popen([SH, "-c", shell], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
    except (OSError, ValueError) as e:
        return {"exit": None, "last": f"{type(e).__name__}: {e}"[:LAST_CAP], "cut": False,
                "error": True}
    cut = False
    try:
        out, err = proc.communicate(timeout=LINE_LIMIT)
    except subprocess.TimeoutExpired:
        cut = True
        _killpg(proc.pid)
        try:
            out, err = proc.communicate(timeout=PIPE_GRACE)
        except subprocess.TimeoutExpired:       # a process that left the group holds a pipe
            for fh in (proc.stdout, proc.stderr):
                fh.close()
            proc.wait()
            return {"exit": None, "cut": True, "error": True,
                    "last": f"orphans: the line's output still held {PIPE_GRACE:g} s after its cut"}
    _killpg(proc.pid)                           # whatever it left running in its group
    rc = CUT_EXIT if cut else (proc.returncode if proc.returncode >= 0 else -1)
    return {"exit": rc, "last": _last_of(out) or _last_of(err), "cut": cut, "error": False}


# The relay's scratch home (effects scratchEnv): a line never writes under the live home.
SCRATCH = (("HOME", ""), ("XDG_CONFIG_HOME", "config"), ("XDG_STATE_HOME", "state"),
           ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"), ("GOCACHE", "go-build"),
           ("GOBIN", "bin"), ("GOMODCACHE", "gomod"), ("PYTHONPYCACHEPREFIX", "pycache"))


def line_env(environ: dict, home: str, remotes: list) -> dict:
    """The child's environment less its profile, under a scratch home and TMPDIR, at depth
    1, with the push barrier; pytest's cache plugin kept on (review F7: off, a test using
    the `cache` fixture errors here and passes in the gate), its directory in the scratch
    home, so a line leaves no `.pytest_cache` in a tree that does not ignore it (the
    dirty-tree check reads the tree after a continuation)."""
    out = {k: v for k, v in environ.items() if not k.startswith("CLAUDE") and not (
        k.startswith("RELAY_") and k != "RELAY_DEVICE_VERBS")}
    out.update({k: os.path.join(home, leaf) if leaf else home for k, leaf in SCRATCH})
    cache = "-o cache_dir=" + shlex.quote(os.path.join(home, "pytest-cache"))
    out.update({"TMPDIR": os.path.join(home, "tmp"), "RELAY_MEASURE_DEPTH": "1",
                "PYTEST_ADDOPTS": (out.get("PYTEST_ADDOPTS", "") + " " + cache).strip()})
    return push_deny(out, remotes)


def _unrun(got: dict | None) -> bool:
    """It could not run: no start, or the shell's 126 (not executable) or 127 (not found)."""
    return got is None or bool(got.get("error")) or got.get("exit") in UNRUN_EXITS


def judge_line(ln: Line, got: dict, base: dict | None) -> str:
    """`gate.rerun`, where the loop cannot be sure a line passed it is not a pass: `unrun`
    when it could not run (review F2: exit 126 or 127 too); `red` when it was cut at the
    limit, whatever it expects (F3); an `as main` line `unrun` when its baseline could not run
    or was cut, else `same-as-main` (green at exit 0) when its exit and last line are its
    baseline's, else `red`; every other line `green` when it holds, else `red`."""
    if _unrun(got):
        return "unrun"
    if got.get("cut"):
        return "red"
    if ln.kind == "as-main":
        if _unrun(base) or base.get("cut"):
            return "unrun"
        if (got["exit"], got["last"]) == (base["exit"], base["last"]):
            return "green" if got["exit"] == 0 else "same-as-main"
        return "red"
    return "green" if line_holds(ln, got["exit"], got["last"]) else "red"


def run_lines(wt: Path, lines: list, env: dict, pick=None) -> list:
    """Each line (those `pick` keeps) run in wt under one scratch home, removed after; a
    line left out is None."""
    home = tempfile.mkdtemp(prefix="unattended-lines-")
    try:
        os.mkdir(os.path.join(home, "tmp"))
        e = line_env(env, home, remotes(wt))
        return [run_line(wt, ln.shell, e) if pick is None or pick(ln) else None for ln in lines]
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _as_main(ln: Line) -> bool:
    return ln.kind == "as-main"


def sha_lines(repo: Path, sha: str, lines: list, env: dict, pick=None,
              note: Callable | None = None, prefix: str = "unattended-sha-") -> tuple:
    """Packet u3 R1: the lines (those `pick` keeps) run in a temporary detached tree at `sha`,
    the main checkout's `.venv*` linked there (`link_venvs`); the tree removed after, on an
    error too, never by a prune. (results, None), or (None, git's last line) when the tree
    cannot be made."""
    top = tempfile.mkdtemp(prefix=prefix)
    tree = Path(top) / "tree"
    try:
        r = _git(repo, "worktree", "add", "--detach", str(tree), sha)
        if r.returncode != 0:
            return None, _git_why(r, "git worktree add")
        link_venvs(repo, tree, note)
        return run_lines(tree, lines, env, pick), None
    finally:
        removed = _git(repo, "worktree", "remove", "--force", str(tree)).returncode == 0
        mine = os.path.realpath(top) + os.sep
        shutil.rmtree(top, ignore_errors=True)
        if not removed:                 # never a prune: it drops other sittings' trees (N1)
            _drop_records(repo, mine)


def pin_baseline(repo: Path, sha: str | None, lines: list, env: dict,
                 note: Callable | None = None) -> list:
    """Packet u2 R2, review F4: each `as main` line run once in a temporary detached tree at
    main's sha at the row's pin (`sha_lines`), never in the staged tree (a reused branch tree
    would be its own baseline). A line it cannot measure is an error, so it is `unrun`;
    another line is None."""
    def failed(why: str) -> list:
        return [{"exit": None, "last": why[:LAST_CAP], "cut": False, "error": True}
                if _as_main(ln) else None for ln in lines]
    if not sha:
        return failed("no main sha at the pin")
    got, why = sha_lines(repo, sha, lines, env, _as_main, note, "unattended-pin-")
    return failed("pin tree: " + why) if got is None else got


def _drop_records(repo: Path, inside: str) -> None:
    """Second review N1: the repo's worktree entries whose `gitdir` file points under
    `inside`, read from each entry, never guessed by name, removed; every other record is
    left as it is, since the loop never removes or prunes a tree it did not make."""
    common = _out(repo, "rev-parse", "--git-common-dir")
    if not common:
        return
    d = Path(common) if os.path.isabs(common) else Path(repo) / common
    try:
        entries = list((d / "worktrees").iterdir())
    except OSError:
        return
    for e in entries:
        try:
            gitdir = (e / "gitdir").read_text(errors="replace").strip()
        except OSError:
            continue
        if gitdir and os.path.realpath(gitdir).startswith(inside):
            shutil.rmtree(e, ignore_errors=True)


def _said(c: dict) -> str:
    """One failing line for the child: what it returned and what it wants."""
    if c["status"] == "unrun" and (c["exit"] is None or c["exit"] in UNRUN_EXITS):
        got = "could not run (" + (f"exit {c['exit']}: " if c["exit"] is not None else "") \
            + f"{c['last']})"
    elif c["status"] == "unrun":
        got = "could not be judged: its run at the pin could not run or was cut"
    else:
        got = f"returned exit {c['exit']}" + (f", cut at {LINE_LIMIT:g} s" if c["cut"] else "") \
            + (f", last line \"{c['last']}\"" if c["last"] else ", no output")
    want = c["expect"]
    if c["main_exit"] is not None or c["main_last"] is not None:
        want += f" (at the pin: exit {c['main_exit']}, last line \"{c['main_last']}\")"
    return f"`{c['shell']}` {got}; it wants: {want}"


def continuation(failing: list, sha: str) -> str:
    """Packet u2 R3, u3 R4: the message that names each failing line and where they ran."""
    return ("The packet's acceptance lines do not all hold yet; the loop ran them in a fresh "
            f"tree at {sha} after your turn, where a file left ignored or uncommitted is not "
            "there:\n" + "".join(f"- {_said(c)}\n" for c in failing) + TAIL + "\n")


# ---- the spawn (ruling 5) --------------------------------------------------------------

def _usd(v) -> str:
    return f"{round(float(v), 2):g}"


def builder_effort(env) -> str:
    """The `builder` profile's effort, the user's layer over the shipped one; `high` when it
    names none the loop knows or the profiles cannot be read (packet u2 R5)."""
    try:
        v = (resolver.load_profiles(env)[1].get("builder") or {}).get("effort")
    except Exception:       # noqa: BLE001  (an unreadable layer is the fallback, never a stop)
        v = None
    return v if v in EFFORTS else BUILDER_EFFORT


def spawn_argv(model: str, turns: int, usd, sid: str | None = None,
               resume: str | None = None, effort: str | None = None) -> list:
    """The relay's spawn line (`SpawnArgv`); a resume names its session and no new one; the
    level after the model (packet u2 R5)."""
    a = ["claude", "-p"] + (["--resume", resume] if resume else [])
    a += ["--permission-mode", "auto", "--allowedTools", ALLOWED_TOOLS, "--model", model]
    a += (["--effort", effort] if effort else [])
    a += ["--max-turns", str(turns), "--max-budget-usd", _usd(usd),
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
    return f"{PROMPT}\n\n{packet_text}"


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
    return f"{result.get('result') or ''}\n{more}".lower()


API_STATUS = re.compile(r"(?m)^\s*api error: ([0-9]{3})(?:[^0-9]|$)")
MODEL_WORDS = ("fable", "opus", "sonnet", "haiku")       # relay limit.go modelWords


def _word(c: str) -> bool:
    return c.isascii() and c.isalnum()


def holds(text: str, needle: str) -> bool:
    """The relay's `holds`: text holds needle as a whole word, neither end of a match
    touching a letter or a digit (an underscore is a boundary)."""
    i = text.find(needle)
    while i >= 0:
        j = i + len(needle)
        if (i == 0 or not _word(text[i - 1]) or not _word(needle[0])) and \
                (j == len(text) or not _word(text[j]) or not _word(needle[-1])):
            return True
        i = text.find(needle, i + 1)
    return False


def text_kind(text: str) -> str:
    """The relay's `textKind` in this loop's names: a window's text `session`, a weekly
    one's `seven_day`, a model's `model_<word>`, else `unknown`."""
    if holds(text, "session limit") or holds(text, "5-hour limit"):
        return "session"
    if holds(text, "weekly limit"):
        return "seven_day"
    for m in USAGE_WORDS.finditer(text):
        if m.group(2) in MODEL_WORDS:
            return f"model_{m.group(2)}"
    return "unknown"


def account(text: str) -> str | None:
    """`limit`, `auth` or None for an is_error result's lowered text, as the relay's
    `Account`: a line-start `api error: NNN` outranks any needle (401 auth, 429 a limit);
    then the whole-word needles, usage first."""
    for m in API_STATUS.finditer(text):
        if m.group(1) == "429":
            return "limit"
        if m.group(1) == "401":
            return "auth"
    if any(holds(text, n) for n in USAGE_NEEDLES) or USAGE_WORDS.search(text):
        return "limit"
    if any(holds(text, n) for n in AUTH_NEEDLES):
        return "auth"
    return None


def classify(obj: dict, part: Part) -> None:
    t = obj.get("type")
    if t == "rate_limit_event":
        info = obj.get("rate_limit_info") if isinstance(obj.get("rate_limit_info"), dict) else {}
        st = info.get("status") if isinstance(info.get("status"), str) else obj.get("status")
        if isinstance(st, str) and st and not st.startswith("allowed") and part.limit is None:
            part.limit = {"kind": str(info.get("rateLimitType") or "unknown"),
                          "resets_at": info.get("resetsAt"), "source": "event"}
    elif t == "result":
        part.result = obj
        if obj.get("is_error") is True and not str(obj.get("subtype") or "").startswith("error_max"):
            text = _text(obj)
            said = account(text)
            if said == "limit" and part.limit is None:
                part.limit = {"kind": text_kind(text), "resets_at": None, "source": "text"}
            elif said == "auth":
                part.auth = True


def read_stream(stdout, path: Path, part: Part) -> None:
    """Each line to `<run>/<id>.jsonl` as it comes, then parsed; non-JSON is skipped."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as fh:
        for raw in iter(stdout.readline, b""):
            fh.write(raw if raw.endswith(b"\n") else raw + b"\n")
            fh.flush()
            obj = _parse(raw)
            if obj is not None:
                classify(obj, part)


# ---- the watchdog (ruling 9) -----------------------------------------------------------

def _newest(wt: Path) -> float:
    newest = 0.0
    for top, dirs, files in os.walk(wt):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in dirs + [f for f in files if f != ".git"]:
            try:
                newest = max(newest, os.lstat(os.path.join(top, name)).st_mtime)
            except OSError:
                pass
    return newest


def _cpu(pgid: int) -> tuple:
    r = subprocess.run(["ps", "-A", "-o", "pgid=,time="], capture_output=True, text=True)
    return tuple(sorted(t for g, t in (ln.split(None, 1) for ln in r.stdout.splitlines()
                                       if len(ln.split(None, 1)) == 2) if g == str(pgid)))


def signals(wt: Path, pgid: int) -> tuple:
    """The relay's three signs of work: HEAD, the newest mtime, the group's CPU time."""
    return _out(wt, "rev-parse", "HEAD"), _newest(wt), _cpu(pgid)


# ---- the run: the end of a row (ruling 7) ----------------------------------------------

def _iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t))


# ---- the land step (ruling 9) --------------------------------------------------

GATE_LINE = re.compile(r"^gate (\S+) (.+): exit (-?\d+) in (\S+) min; log (.+)$")  # wait_line
LAND_OK = re.compile(r"^land (\S+): ok (\S+?)(?:,.*)?$")
LAND_RED = re.compile(r"^land (\S+): red (\S+) exit (-?\d+)(?:,.*)?$")
STANDS = ("remove", "branch")       # land's steps after the merge: main has moved


def heading(text: str, rid: str) -> str | None:
    """The packet's first heading, less a leading `Packet <id>: `."""
    for ln in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*\S)", ln)
        if m:
            h, pre = m.group(1), f"Packet {rid}: "
            return h[len(pre):] if h.startswith(pre) else h
    return None


def _last_nonempty(path: str, gate_id: str) -> str | None:
    """A log's last non-empty line not the gate's own trailer, `gate <gate_id>: exit <rc> in
    <N> s` (gate.py `_close`, written after the job ends), read from its last 64 KiB; None
    when unreadable."""
    skip = f"gate {gate_id}: "
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 65536))
            lines = [ln.strip() for ln in fh.read().decode(errors="replace").splitlines()]
    except (OSError, ValueError):
        return None
    lines = [ln for ln in lines if ln and not ln.startswith(skip)]
    return lines[-1] if lines else None


def verdict(rc, out: str, sha: str) -> tuple:
    """(state, reason, the gate's fields) from `gate run --wait`'s rc and stdout: `landed`
    on `ok <sha>` with exit 0, or on a `remove` or `branch` red (`land-<step>`); `red
    land-<step>` on another red; anything else `red gate-unrun`, never a pass."""
    lines = [ln for ln in (out or "").splitlines() if ln.strip()]
    g = GATE_LINE.match(lines[-1].strip()) if lines else None
    rec = {"gate_id": g and g.group(1), "gate_line": g and g.group(0)[:300], "land_line": None,
           "exit": g and int(g.group(3)), "rc": rc, "log": g and g.group(5)}
    if rc != 0 or g is None:
        return "red", "gate-unrun", rec
    land = _last_nonempty(rec["log"], rec["gate_id"]) or ""
    rec["land_line"] = land[:300] or None
    ok, red = LAND_OK.match(land), LAND_RED.match(land)
    if ok and rec["exit"] == 0 and ok.group(2) == sha:
        return "landed", None, rec
    if red:
        step = red.group(2)
        return ("landed" if step in STANDS else "red"), f"land-{step}", rec
    return "red", "gate-unrun", rec


@dataclass
class _Row:
    """One row's running tally (packet u2): its acceptance lines and their baseline at the
    pin, its limits and continuations, and what its parts spent."""
    lines: list
    base: list | None = None
    limits: int = 0
    continues: int = 0
    turns: int = 0
    usd: float = 0.0


def _check(i: int, ln: Line, got: dict, base: dict | None, status: str) -> dict:
    """One line's result, as the ledger keeps it."""
    return {"line": i, "shell": ln.shell[:TEXT_CAP], "expect": ln.expect[:TEXT_CAP],
            "exit": got["exit"], "last": got["last"], "cut": got["cut"], "status": status,
            "main_exit": base and base["exit"], "main_last": base and base["last"]}


@dataclass
class _Run:
    repo: Path
    nid: str
    dir: Path
    fx: Fx
    stall: float
    poll: float
    states: dict = field(default_factory=dict)
    cost: float = 0.0
    term: bool = False
    proc: object = None
    land: str | None = None
    until: float | None = None
    max_rows: int | None = None
    spawned: int = 0
    landed: set = field(default_factory=set)
    effort: dict = field(default_factory=dict)      # row id: the level it ran at
    cur: _Row | None = None                          # the running row's tally
    noted: set = field(default_factory=set)          # u3 R2: the row's unlinked names
    rid: str | None = None

    def unlinked(self, name: str) -> None:
        """Packet u3 R2: a `.venv*` directory a tree does not ignore; one log line a row."""
        if name not in self.noted:
            self.noted.add(name)
            self.log(f"{self.rid}: {name} is not ignored by the tree; not linked")

    def log(self, line: str) -> None:
        _append(self.dir / "log", f"{_iso(self.fx.now())} {line}\n")
        print(f"unattended: {line}", file=sys.stderr, flush=True)

    def record(self, event: str, /, **kw) -> None:
        _append(self.dir / "ledger.jsonl",
                json.dumps({"ts": _iso(self.fx.now()), "kind": event, **kw}) + "\n")

    def limit(self, rid: str, lim: dict, action: str, **kw) -> None:
        """A `limit` line: the limit's kind is `limit_kind`, since every line's `kind` is its
        event's."""
        self.record("limit", row=rid, limit_kind=lim["kind"], resets_at=lim["resets_at"],
                    source=lim["source"], action=action, **kw)

    def row(self, p, state, reason=None, sha=None, wt=None, sid=None, **more) -> None:
        rec = {"row": p["id"], "state": state, "reason": reason, "sha": sha,
               "worktree": str(wt) if wt else None, "merge": p.get("merge"),
               "verify": p.get("verify"), "effort": self.effort.get(p["id"]), **more}
        if state in ("red", "limit") and wt and sid:
            rec["resume"] = f"cd {wt} && claude --resume {sid}"
        self.record("row", **rec)
        self.states.setdefault(state, []).append(p["id"])
        self.fx.say(f"{p['id']}: {state}" + "".join(f" {x}" for x in (reason, sha) if x))

    def part(self, p, wt, n, argv, sid, text, turns, usd):
        """One child to its exit: (Part, rc, the watchdog's cut or None)."""
        rid = p["id"]
        adm = admit(self.nid, p["model"], self.fx.env)
        self.record("spawn", row=rid, part=n, model=p["model"], effort=self.effort.get(rid),
                    turns=turns, usd=usd, session_id=sid, argv=argv, admission=adm)
        env = child_env(self.fx.env, p["model"], turns, remotes(wt))
        part = Part()
        proc = self.proc = start(argv, wt, env, text, self.dir / f"{rid}.stderr", self.fx)
        reader = threading.Thread(target=read_stream, daemon=True,
                                  args=(proc.stdout, self.dir / f"{rid}.jsonl", part))
        reader.start()
        cut = self.watch(proc, wt, wall_seconds(p["wall"]))
        reader.join(5.0)
        if reader.is_alive():           # a grandchild holds the pipe: the group goes
            gate._kill_group(proc.pid, self.fx)
            reader.join(5.0)
        self.proc = None
        r = part.result or {}
        cost, spent = r.get("total_cost_usd"), r.get("num_turns")
        self.cost += cost if type(cost) in (int, float) else 0
        if self.cur is not None:
            self.cur.usd += cost if type(cost) in (int, float) else 0
            self.cur.turns += spent if type(spent) is int else 0
        self.record("exit", row=rid, part=n, rc=proc.returncode, subtype=r.get("subtype"),
                    is_error=r.get("is_error"), num_turns=r.get("num_turns"),
                    total_cost_usd=cost, duration_ms=r.get("duration_ms"),
                    session_id=r.get("session_id"))
        return part, proc.returncode, cut

    def watch(self, proc, wt, wall) -> str | None:
        """Ruling 9: every `poll` s the tree's HEAD, its newest mtime outside `.git` and the
        group's CPU; all three unchanged for `stall` s, or the row's wall passed, and the
        group goes (gate's `_kill_group`): `stalled` or `wall`. None on the child's exit."""
        t0 = last = self.fx.mono()
        seen = signals(wt, proc.pid)
        while True:
            try:
                proc.wait(timeout=self.poll)
                return None
            except subprocess.TimeoutExpired:
                pass
            now = self.fx.mono()
            if wall and now - t0 >= wall:
                cut = "wall"
            else:
                cur = signals(wt, proc.pid)
                if cur != seen:
                    seen, last = cur, now
                    continue
                if now - last < self.stall:
                    continue
                cut = "stalled"
            self.log(f"{wt.name}: {cut} after {now - t0:.0f} s; its group is killed")
            gate._kill_group(proc.pid, self.fx)
            proc.wait()
            return cut

    def stopped(self) -> bool:
        """The owner's stop file, `<run>/stop`."""
        return os.path.lexists(self.dir / "stop")

    def before(self) -> str | None:
        """Ruling 6 and 4, before each row: the stop file, then `--until`."""
        if self.stopped():
            return "owner-stop"
        if self.until is not None and self.fx.now() >= self.until:
            return "until"
        return None

    def merge_file(self, p, sha: str, sid: str) -> Path:
        rid, path = p["id"], self.dir / f"{p['id']}.merge.txt"
        h = heading((self.repo / p["packet"]).read_text(errors="replace"), rid) or p["packet"]
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(f"Merge {rid}: {h}\n\nRow {rid}, packet {p['packet']}, built by {self.nid} "
                     f"in session {sid} at {sha}.\n")
        return path

    def land_row(self, p, wt, sha: str, sid: str) -> None:
        """Ruling 9: one job through the gate queue, `gate run --wait <repo> -- <land> <repo>
        <id> <sha> <merge-file>` in the repo, no timeout, in its own session so a signal
        to the run lets the job finish; a `gate` line, then the row's."""
        rid = p["id"]
        merge = self.merge_file(p, sha, sid)
        argv = [*self.fx.gate, "run", "--wait", str(self.repo), "--", self.land, str(self.repo),
                rid, sha, str(merge)]
        self.fx.say(f"{rid}: built {sha[:12]}; it lands through the gate")
        err = os.fdopen(os.open(self.dir / f"{rid}.gate.stderr",
                                os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "ab")
        try:
            proc = self.fx.popen(argv, cwd=str(self.repo), env=dict(self.fx.env),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
                                 start_new_session=True)
            out, rc = proc.communicate()[0].decode(errors="replace"), proc.returncode
        except OSError as e:
            self.log(f"{rid}: gate: {type(e).__name__}: {e}"[:300])
            out, rc = "", None
        finally:
            err.close()
        state, reason, rec = verdict(rc, out, sha)
        self.record("gate", row=rid, **rec)
        if state == "landed":
            self.landed.add(rid)
            self.row(p, "landed", reason, sha=sha, wt=wt if reason else None)
        else:
            self.row(p, "red", reason, sha=sha, wt=wt, sid=sid)

    def left(self, p) -> tuple:
        """A resume's budget: the row's less what every part spent, never under 10 turns or
        $5."""
        return (max(10, p["turns"] - self.cur.turns),
                max(5, round(p["usd"] - self.cur.usd, 2)))

    def baseline(self, p, pin) -> list:
        """Packet u2 R2: each `as main` line run once at main's sha at the pin, in a tree of
        its own (`pin_baseline`, review F4), before the spawn; a `baseline` line. Another line
        is None: it is judged on its own."""
        got = pin_baseline(self.repo, pin, self.cur.lines, self.fx.env, self.unlinked)
        self.record("baseline", row=p["id"], pin=pin, lines=[
            {"line": i, "exit": g and g["exit"], "last": g and g["last"], "error": g and g["error"]}
            for i, g in enumerate(got, 1)])
        return got

    def accept(self, p, n, sha: str) -> list | None:
        """Packet u2 R2, u3 R1: every line in a fresh tree at the row's head sha
        (`sha_lines`), judged against its baseline; an `accept` line; the checks. None, and
        git's last line in the log, when that tree cannot be made (u3 R3)."""
        base = self.cur.base or [None] * len(self.cur.lines)
        got, why = sha_lines(self.repo, sha, self.cur.lines, self.fx.env, note=self.unlinked)
        if got is None:
            self.log(f"{p['id']}: stage: {why}")
            return None
        checks = [_check(i, ln, g, b, judge_line(ln, g, b))
                  for i, (ln, g, b) in enumerate(zip(self.cur.lines, got, base), 1)]
        self.record("accept", row=p["id"], part=n, sha=sha, lines=checks)
        return checks

    def do_row(self, p) -> str | None:
        """The row, start to end; the run's stop reason, or None to go on."""
        self.cur, self.rid, self.noted = None, p["id"], set()
        j = judge_row(p, self.repo, self.landed)
        if j:
            self.row(p, *j)
            return None
        text = (self.repo / p["packet"]).read_text(errors="replace")
        try:
            lines = acceptance(text)
        except AcceptanceError as e:
            self.log(f"{p['id']}: acceptance: {e}"[:300])
            self.row(p, "refused", "acceptance")
            return None
        why = unbounded_item(lines)
        if why:                                          # packet u3 R6
            self.log(f"{p['id']}: unbounded: {why}")
            self.row(p, "refused", "unbounded")
            return None
        if self.max_rows is not None and self.spawned >= self.max_rows:
            return "max-rows"
        pin = _out(self.repo, "rev-parse", "--verify", "--quiet", "main^{commit}")
        wt, head = stage(self.repo, p["id"], "main", self.unlinked)   # a landed base is on main
        if wt is None:
            self.log(f"{p['id']}: stage: {head}")
            self.row(p, "red", "stage")
            return None
        self.cur = _Row(lines)
        if any(_as_main(ln) for ln in lines):
            self.cur.base = self.baseline(p, pin)
        text = prompt(text)
        sid = str(uuid.uuid4())
        effort = self.effort[p["id"]] = p.get("effort") or builder_effort(self.fx.env)
        argv = spawn_argv(p["model"], p["turns"], p["usd"], sid=sid, effort=effort)
        self.spawned += 1
        part, rc, cut = self.part(p, wt, 1, argv, sid, text, p["turns"], p["usd"])
        return self.end(p, wt, head, part, rc, cut, sid, 1)

    def end(self, p, wt, head, part, rc, cut, sid, n) -> str | None:
        if cut:
            self.row(p, "red", cut, wt=wt, sid=sid)
            return None
        if part.result is None or (rc is not None and rc < 0):
            self.row(p, "red", "sitting-failure", wt=wt, sid=sid)
            return "sitting-failure"
        sid = part.result.get("session_id") or sid
        if part.auth:
            self.row(p, "red", "auth", wt=wt, sid=sid)
            return "auth"
        if part.limit:
            return self.limited(p, wt, head, part, sid, n)
        sha = _out(wt, "rev-parse", "HEAD")
        if not sha or sha == head or _out(wt, "rev-list", "--count", f"{head}..{sha}") in (None, "0"):
            self.row(p, "red", "no-commit", wt=wt, sid=sid)
        elif dirty(wt):
            self.row(p, "red", "dirty-tree", sha=sha, wt=wt, sid=sid)
        elif part.result.get("is_error"):
            self.row(p, "red", "stream-error", sha=sha, wt=wt, sid=sid)
        else:
            return self.finish(p, wt, head, sha, sid, n)
        return None

    def finish(self, p, wt, head, sha, sid, n) -> str | None:
        """Packet u2 R2, R3: a commit, a clean tree, a non-error result; then the acceptance
        lines. All pass: built, or it lands. One fails: a named continuation of the same
        session, two at most, then red `acceptance` with the failing lines."""
        rid = p["id"]
        checks = self.accept(p, n, sha)
        if checks is None:                               # packet u3 R3: no continuation
            self.row(p, "red", "stage", sha=sha, wt=wt, sid=sid)
            return None
        failing = [c for c in checks if c["status"] not in PASSES]
        if not failing:
            if p.get("merge") != "merge-on-green":
                self.row(p, "built", sha=sha, wt=wt)
            elif not self.land:
                self.log(f"{rid}: merge-on-green with no land script; it stays on its branch")
                self.row(p, "built", "no-land", sha=sha, wt=wt)
            else:
                self.land_row(p, wt, sha, sid)
            return None
        stop = "signal" if self.term else "owner-stop" if self.stopped() else None
        if stop or self.cur.continues >= CONTINUATIONS:
            self.row(p, "red", "acceptance", sha=sha, wt=wt, sid=sid, failing=failing)
            return stop
        self.cur.continues += 1
        turns, usd = self.left(p)
        self.record("continue", row=rid, part=n + 1, reason="acceptance",
                    failing=[c["line"] for c in failing])
        self.fx.say(f"{rid}: {len(failing)} acceptance line(s) fail; continuation "
                    f"{self.cur.continues} of {CONTINUATIONS}")
        argv = spawn_argv(p["model"], turns, usd, resume=sid, effort=self.effort.get(rid))
        part2, rc, cut = self.part(p, wt, n + 1, argv, sid, continuation(failing, sha), turns,
                                   usd)
        return self.end(p, wt, head, part2, rc, cut, sid, n + 1)


    def limited(self, p, wt, head, part, sid, n) -> str | None:
        """Ruling 8: a window limit with a reset waits for it plus 120 s, an unknown one
        1,800 s, and the row is resumed once; any other kind ends the row `limit`; a
        weekly limit or a second one stops the run `usage-limit`. Never a kill."""
        lim, rid = part.limit, p["id"]
        kind, reset = lim["kind"], lim["resets_at"]
        self.cur.limits += 1                    # counted by limits, not parts (packet u2 R4)
        if self.cur.limits > 1 or kind.startswith("seven_day"):
            self.limit(rid, lim, "stop")
            self.row(p, "limit", kind, wt=wt, sid=sid)
            return "usage-limit"
        if kind in ("five_hour", "session") and _num(reset):
            at = reset / 1000.0 if reset > 1e12 else float(reset)
            wait, wait_from = max(0.0, at - self.fx.now()) + 120.0, "reset"
        elif kind in ("unknown", "five_hour", "session"):    # no reset to wait for
            wait, wait_from = 1800.0, "fallback"
            lim = {**lim, "source": "fallback"}
        else:
            self.limit(rid, lim, "row-limit")
            self.row(p, "limit", kind, wt=wt, sid=sid)
            return None
        if self.until is not None and self.fx.now() + wait > self.until:
            self.limit(rid, lim, "shelve", wait_s=round(wait), wait_from=wait_from)
            self.row(p, "limit", kind, wt=wt, sid=sid)
            return "usage-limit"
        self.limit(rid, lim, "resume", wait_s=round(wait), wait_from=wait_from)
        self.fx.say(f"{rid}: limit {kind}; resumes in {wait / 60:.0f} min")
        self.wait(wait)
        if self.term or self.stopped():
            self.row(p, "limit", kind, wt=wt, sid=sid)
            return "signal" if self.term else "owner-stop"
        turns, usd = self.left(p)
        argv = spawn_argv(p["model"], turns, usd, resume=sid, effort=self.effort.get(rid))
        part2, rc, cut = self.part(p, wt, n + 1, argv, sid, CONTINUE + "\n", turns, usd)
        return self.end(p, wt, head, part2, rc, cut, sid, n + 1)

    def wait(self, seconds: float) -> None:
        """A limit's wait, in slices of at most 60 s, so a SIGTERM or the stop file ends it."""
        while seconds > 0 and not self.term and not self.stopped():
            step = min(seconds, 60.0)
            self.fx.sleep(step)
            seconds -= step


def run(repo, keep=None, fx: Fx | None = None, stall: float = STALL, poll: float = POLL,
        until: str | None = None, max_rows: int | None = None, land: str | None = None) -> int:
    """The run: 0 on `queue-spent`, `until` or `max-rows`, 3 on another stop; UnattendedError
    before the run's folder."""
    fx = fx or Fx()
    repo = Path(os.path.realpath(repo))
    if max_rows is not None and (type(max_rows) is not int or max_rows <= 0):
        raise UnattendedError(f"max-rows: {max_rows!r} is not a positive count")
    at, lp = refusals(repo, fx, until, land)
    try:
        text = (repo / QUEUE).read_text()
    except (OSError, UnicodeDecodeError) as e:
        raise UnattendedError(f"queue: {repo / QUEUE}: {e.__class__.__name__}") from None
    pending: list = []
    rows = plan(read_queue(text), keep, pending.append)
    nid, d = new_run(fx.env, fx.now())
    N = _Run(repo, nid, d, fx, stall, poll, land=lp, until=at, max_rows=max_rows)


    for line in pending:
        N.log(line)
    fx.say(f"{nid}: {len(rows)} rows from {repo / QUEUE}; ledger {d / 'ledger.jsonl'}")
    for p in rows:                                       # packet u3 R7: the early word
        why = None if p["parked"] else early_word(p, repo)
        if why:
            fx.say(f"{p['id']}: its turn refuses it, {why}")

    def on_term(_sig, _frame):
        N.term = True
    main = threading.current_thread() is threading.main_thread()
    old = {sig: signal.signal(sig, on_term) for sig in (signal.SIGTERM, signal.SIGINT)} \
        if main else {}
    stop = None
    try:
        for p in rows:
            if N.term:
                break
            stop = N.before() or N.do_row(p)
            if stop:
                break
    except BaseException as e:
        # The run dies with a child running: its group goes, and the stop line says so.
        if N.proc is not None and N.proc.poll() is None:
            N.log(f"the run dies ({type(e).__name__}); the running child's group is killed")
            gate._kill_group(N.proc.pid, fx)
            N.proc.wait()
        N.record("stop", reason="error", error=f"{type(e).__name__}: {e}"[:200], rows=N.states,
                 cost=round(N.cost, 4))
        raise
    finally:
        for sig, h in old.items():
            signal.signal(sig, h)
    stop = stop or ("signal" if N.term else "queue-spent")
    N.record("stop", reason=stop, rows=N.states, cost=round(N.cost, 4))
    fx.say(f"{nid}: stop {stop}; " + ", ".join(f"{k} {len(v)}" for k, v in N.states.items())
           + f"; ${N.cost:.2f}")
    return 0 if stop in ("queue-spent", "until", "max-rows") else 3



# ---- the ledger read back, and status (ruling 10) --------------------------------------

def read_ledger(path: Path) -> list:
    """The run's ledger, each line an object; a torn or foreign line is skipped and a
    key it does not know is kept, never read."""
    out = []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _last_line(path: Path) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(path) - 65536))
            lines = fh.read().decode(errors="replace").splitlines()
    except OSError:
        return ""
    return (lines[-1] if lines else "")[:200]


def status(env, now: float) -> dict | None:
    """The newest run: its rows by state, a running row's last stream line and its age,
    its stop; None with no run yet."""
    d = newest_run(env)
    if d is None:
        return None
    rows, ended, spawned, stop = {}, set(), [], None
    for e in read_ledger(d / "ledger.jsonl"):
        k = e.get("kind")
        if k == "row" and isinstance(e.get("state"), str):
            rows.setdefault(e["state"], []).append(
                {"row": e.get("row"), "reason": e.get("reason"), "sha": e.get("sha")})
            ended.add(e.get("row"))
        elif k == "spawn":
            spawned.append(e.get("row"))
        elif k == "stop":
            stop = {"reason": e.get("reason"), "cost": e.get("cost")}
    running = None
    live = [r for r in spawned if r not in ended and isinstance(r, str) and ROW_ID.match(r)]
    if live and stop is None:
        path = d / f"{live[-1]}.jsonl"
        try:
            age = round(now - path.stat().st_mtime)
        except OSError:
            age = None
        running = {"row": live[-1], "last": _last_line(path), "age_s": age}
    return {"run": d.name, "dir": str(d), "rows": rows, "running": running,
            "stop": stop}


def _row_word(r: dict) -> str:
    """A status row: its id (`-` when the ledger's is null, a row refused `id`), its reason,
    its sha as 12."""
    words = ["-" if r.get("row") is None else str(r["row"])]
    if r.get("reason"):
        words.append(str(r["reason"]))
    if r.get("sha"):
        words.append(str(r["sha"])[:12])
    return " ".join(words)


def status_lines(st: dict | None) -> list:
    if st is None:
        return ["no run yet"]
    out = [f"{st['run']}: {st['dir']}"]
    for state, rows in st["rows"].items():
        out.append(f"  {state} {len(rows)}: " + ", ".join(_row_word(r) for r in rows))
    if st["running"]:
        r = st["running"]
        out.append(f"  running {r['row']}, its last line {r['age_s']} s ago: {r['last']}")
    if st["stop"]:
        cost = st["stop"]["cost"]
        out.append(f"  stop {st['stop']['reason']}"
                   + (f", ${cost:.2f}" if type(cost) in (int, float) else ""))
    return out


# ---- the report (ruling 10) --------------------------------------------

def find_run(env, nid: str | None) -> Path | None:
    """`--run`'s folder (`<date>-<n>`), else the newest; None when
    there is none."""
    if nid is None:
        return newest_run(env)
    name = nid
    d = runs_dir(env) / name
    return d if _key(name) and d.is_dir() else None


def _cell(v) -> str:
    return "-" if v is None or v == "" else str(v).replace("|", "\\|").replace("\n", " ")


def _table(head: tuple, rows: list) -> list:
    if not rows:
        return ["none"]
    return (["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
            + ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows])


def _local_reset(v) -> str | None:
    if not _num(v):
        return None
    return time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(v / 1000.0 if v > 1e12 else v))


def report(d: Path) -> str:
    """The run's report in markdown, from its ledger alone (relay entry 13): its stop or
    its running row; landed, built, red, limited, refused and skipped rows; each row's cost
    from its `exit` lines, and the total."""
    rows, limits, cost, spawned, stop = {}, {}, {}, [], None
    for e in read_ledger(d / "ledger.jsonl"):
        k, r = e.get("kind"), e.get("row")
        if k == "row":
            rows[r] = e
        elif k == "limit":
            limits[r] = e
        elif k == "spawn":
            spawned.append(r)
        elif k == "exit":
            c = e.get("total_cost_usd")
            cost[r] = cost.get(r, 0.0) + (c if type(c) in (int, float) else 0.0)
        elif k == "stop":
            stop = e
    live = [r for r in spawned if r not in rows]
    head = f"stop {stop.get('reason')}" if stop else "running" + (f" {live[-1]}" if live else "")
    by = {s: [e for e in rows.values() if e.get("state") == s]
          for s in ("landed", "built", "red", "limit")}
    out = [f"# The unattended run {d.name}", "", head]
    for title, cols, items in (
            ("Landed", ("row", "sha", "reason", "effort"),
             [(e["row"], (e.get("sha") or "")[:12], e.get("reason"), e.get("effort"))
              for e in by["landed"]]),
            ("Built", ("row", "sha", "reason", "worktree", "effort"),
             [(e["row"], e.get("sha"), e.get("reason"), e.get("worktree"), e.get("effort"))
              for e in by["built"]]),
            ("Red", ("row", "reason", "resume", "effort"),
             [(e["row"], e.get("reason"), e.get("resume"), e.get("effort")) for e in by["red"]]),
            ("Limited", ("row", "limit_kind", "resets_at", "action", "effort"),
             [(e["row"], limits.get(e["row"], {}).get("limit_kind", e.get("reason")),
               _local_reset(limits.get(e["row"], {}).get("resets_at")),
               limits.get(e["row"], {}).get("action"), e.get("effort")) for e in by["limit"]]),
            ("Refused and skipped", ("row", "reason"),
             [(e["row"], e.get("reason")) for e in rows.values()
              if e.get("state") in ("refused", "skip")])):
        out += ["", f"## {title}", ""] + _table(cols, items)
    total = sum(cost.values())
    out += ["", "## Cost", ""] + _table(("row", "usd"), [(r, f"{c:.2f}") for r, c in cost.items()]
                                        + [("total", f"{total:.2f}")])
    return "\n".join(out) + "\n"
