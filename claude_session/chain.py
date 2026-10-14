"""`agentik session run`: the launcher that restarts a RESPAWN sitting (respawn-r1 §3).

The launcher is the owner's foreground job. Each start runs `claude --session-id <U>
<the owner's arguments>`, byte for byte the same every time, with the launcher's own
environment minus `launch.scrub`'s list plus `CLAUDE_SESSION_CHAIN`. It restarts a
sitting only on a RESPAWN close the main thread confirmed, after the turn has ended
and stood `settle` seconds, under the cap, the floor and the stop files; it never
compacts, resumes, detaches or reads a transcript.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    import termios
except ImportError:                                     # pragma: no cover  (not POSIX)
    termios = None

from . import charter, hooks, launch, ledger, resolver

# §3.1's allowlist; a refused flag is named, and adding one is a one-line change.
ALLOWED = frozenset({
    "--model", "--effort", "--fallback-model", "--permission-mode", "--tools",
    "--allowedTools", "--allowed-tools", "--disallowedTools", "--disallowed-tools",
    "--add-dir", "--plugin-dir", "--settings", "--setting-sources", "--mcp-config",
    "--strict-mcp-config", "--append-system-prompt", "--system-prompt-snapshot", "--name",
    "--verbose"})
# The family that resumes, forks, detaches or prints: never on the allowlist.
FORBIDDEN = ("-p", "--print", "-c", "--continue", "-r", "--resume", "--fork-session",
             "--session-id", "--from-pr", "--teleport", "--bg", "--background", "--tmux",
             "-w")
_BARE = frozenset({"--strict-mcp-config", "--system-prompt-snapshot", "--verbose"})
DEFAULTS = {"cap": 12, "floor": 600, "settle": 60}
_GUARD_SESSION = "respawn-chain"     # the id the guards resolve under; no overlay is read
_LOOP = re.compile(r"^/loop\s+(\d+)\s*([smhd])(?![A-Za-z])")
_EVERY = re.compile(r"\bevery\s+(\d+)\s*([smhd])[a-z]*\s*$", re.I)   # `/loop <p> every 2h`
_MINUTES = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}
_COMPACT = re.compile(r"(?:^|\s)/compact(?:\s|$)")     # the command, never a path's part


def on_tty() -> bool:
    """stdin and stdout are a terminal (§3.1's first refusal)."""
    return os.isatty(0) and os.isatty(1)


def refusal(args, env) -> str | None:
    """The first of §3.1's refusals that `args` (claude's arguments) and `env` meet, as
    one line; None when the chain may start. The TTY, the chain's name and its lock are
    checked by the caller and by `Chain.run`."""
    if env.get(hooks.CHAIN_VAR):
        return (f"refusing to start inside a chain ({hooks.CHAIN_VAR} is set); "
                "a chain never starts another")
    if env.get("CLAUDECODE"):
        return ("refusing to start inside a Claude Code session (CLAUDECODE is set); "
                "run it at a terminal")
    d = launch.depth(env)
    if d is None or d >= 1:
        return (f"refusing to start inside a started session or a relay child "
                f"({launch.DEPTH_VAR}={str(env.get(launch.DEPTH_VAR))[:20]!r})")
    prev = None
    for a in args:
        a = str(a)
        if _COMPACT.search(a):
            return "refusing /compact: every start is a fresh context"
        if not a.startswith("-"):
            prev = None
            continue
        flag = a.split("=", 1)[0]
        if flag not in ALLOWED:
            if prev is not None:
                return (f"refusing {a[:80]!r} after {prev}: a value that begins with '-' "
                        f"reads as a flag; write it as {prev}={a[:80]}")
            why = ("it resumes, forks, detaches or prints" if flag in FORBIDDEN
                   else "it is not on the launcher's allowlist")
            return f"refusing the flag {flag[:80]}: {why}"
        prev = flag if "=" not in a and flag not in _BARE else None
    if shutil.which("claude", path=env.get("PATH")) is None:
        return "no `claude` on PATH; install Claude Code, or put it on PATH"
    return None


def start_line(argv, env) -> str:
    """The launcher's own argv re-quoted, with the profile prefix when it is set: a line
    that runs as printed (§3.4)."""
    line = shlex.join(str(a) for a in argv)
    prof = env.get("CLAUDE_SESSION_PROFILE")
    return f"CLAUDE_SESSION_PROFILE={shlex.quote(prof)} {line}" if prof else line


def default_name(cwd, env) -> str:
    """`<cwd basename>-<profile or none>`, cut to the chain-name alphabet and 64."""
    raw = f"{Path(cwd).name}-{env.get('CLAUDE_SESSION_PROFILE') or 'none'}"
    return re.sub(r"[^A-Za-z0-9._-]", "-", raw)[:64] or "chain"


def guards(cwd, env, flags) -> dict:
    """The resolved `respawn` (§4: the profiles, the repo's config.yaml, then
    config.local.yaml) with `run`'s flags over it. Raises resolver.ResolveError."""
    r = resolver.resolve(cwd, _GUARD_SESSION, env,
                         profile=env.get("CLAUDE_SESSION_PROFILE") or None, overlay={})
    out = {**DEFAULTS, **(r.sections["session"].get("respawn") or {})}
    for k, v in flags.items():
        if k not in DEFAULTS or not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise resolver.ResolveError(f"respawn.{k} must be a non-negative integer")
        out[k] = v
    return out


def long_loop(args) -> float | None:
    """The minutes of a last positional `/loop` of 60 minutes or more, else None
    (packet S20 ruling 6: its question waits at every start)."""
    if not args or str(args[-1]).startswith("-"):
        return None
    last = str(args[-1])
    m = _LOOP.match(last) or (_EVERY.search(last) if last.startswith("/loop") else None)
    if not m:
        return None
    minutes = int(m.group(1)) * _MINUTES[m.group(2).lower()]
    return minutes if minutes >= 60 else None


def _json(path: Path):
    """The file's JSON object; None when it is absent; {} when it is not an object."""
    try:
        d = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _status(rc: int) -> int:
    """A child's status as a shell reports it: a signal N is 128+N (ruling 8)."""
    return 128 - rc if rc < 0 else rc


class Effects:
    """Everything the launcher does to the world, behind one seam (packet S20 ruling 1):
    the clock, the child, the signals it sends, the terminal, its lines and the ledger."""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def uuid(self) -> str:
        return str(uuid.uuid4())

    def environ(self) -> dict:
        return dict(os.environ)

    def spawn(self, argv, env):
        # §3.7: the launcher's own process group and fds 0 to 2; no setsid, no pty.
        return subprocess.Popen(list(argv), env=env)

    def wait(self, proc, timeout: float) -> int | None:
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def send(self, proc, sig: int) -> None:
        try:
            os.kill(proc.pid, sig)
        except ProcessLookupError:
            pass

    def say(self, line: str) -> None:
        print(line, file=sys.stderr, flush=True)

    def tty_save(self):
        try:
            return termios.tcgetattr(0) if termios else None
        except (OSError, termios.error):
            return None

    def tty_restore(self, attrs) -> None:
        if attrs is None:
            return
        try:
            termios.tcsetattr(0, termios.TCSADRAIN, attrs)
        except (OSError, termios.error):
            pass

    def append(self, state: Path, entry: dict) -> Path:
        return ledger.append_chain(state, entry)

    def restarts(self, state: Path, chain: str, now: float) -> int:
        return ledger.restarts_in(state, chain, now)


class Chain:
    """One chain: start, watch, end on a confirmed RESPAWN, restart (respawn-r1 §3.3 to
    §3.7). `guards` is a mapping, or a callable that resolves one, called at the start and
    again before each restart; `poll`, `grace` and `kill_grace` are seconds."""

    def __init__(self, name, args, state, effects, guards, *, poll=2, grace=10,
                 kill_grace=30, argv=None):
        self.name, self.args, self.state, self.fx = name, list(args), Path(state), effects
        self._guards = guards
        self.poll, self.grace, self.kill_grace = poll, grace, kill_grace
        self.argv = list(argv) if argv else ["agentik", "session", "run", "--chain", name,
                                             "--", *self.args]
        self.home = self.state / "respawn" / name
        self.got: list[int] = []        # the signals the launcher took, in order
        self.restarts = 0               # the restarts this launcher made
        self.tally: list[float] = []    # and when (§3.5: a deleted ledger never resets it)
        self.g = dict(DEFAULTS)
        self.started = 0.0
        self.config_error: str | None = None   # a resolve that failed while a child ran

    # ---- the run -----------------------------------------------------------------------

    def run(self) -> int:
        try:
            self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.home / "lock", os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as e:
            self.fx.say(f"error: agentik-session run: the chain's lock cannot be opened: {e}")
            return 2
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.fx.say(f"error: agentik-session run: the chain {self.name} already runs "
                            f"(its lock {self.home / 'lock'} is held)")
                return 2
            try:
                self.g = self.guards()
            except resolver.ResolveError as e:
                self.fx.say(f"error: agentik-session run: {e}")
                return 2
            old = self._trap()
            try:
                return self._chain()
            finally:
                self._untrap(old)
        finally:
            os.close(fd)

    def guards(self) -> dict:
        g = self._guards() if callable(self._guards) else self._guards
        return {**DEFAULTS, **(g or {})}

    def _chain(self) -> int:
        env = self.fx.environ()
        self.env = env
        program = shutil.which("claude", path=env.get("PATH")) or "claude"
        child_env = launch.scrub(env)
        for k in (launch.DEPTH_VAR, "RELAY_ROW"):          # §3.8: never a relay sitting
            child_env.pop(k, None)
        child_env[hooks.CHAIN_VAR] = self.name
        self.started = self.fx.now()
        attrs = self.fx.tty_save()
        sid, n = self.fx.uuid(), 0
        while True:
            n += 1
            start = self.fx.now()
            try:
                proc = self.fx.spawn([program, "--session-id", sid, *self.args], child_env)
            except OSError as e:                 # A-F6: a stop line, never a traceback
                self.fx.tty_restore(attrs)
                self.fx.say(f"{self.name}: claude did not start ({e})")
                self._stop(sid, "spawn", 1, 0)
                return 1
            rc, ended_by, held = self._watch(proc, sid, start)
            cut = len(self.got)                  # the signals taken while the child ran
            self.fx.tty_restore(attrs)                     # §3.7: before anything prints
            seconds = round(self.fx.now() - start)
            reason, code, marker, count = self._decide(sid, start, rc, ended_by, held)
            if reason is None:
                reason = self._grace(n, marker["charter"], count + 1, cut)
            if reason is None:
                nxt = self.fx.uuid()
                entry = {"kind": "restart", "chain": self.name, "seq": self.restarts + 1,
                         "from_session": sid, "to_session": nxt,
                         "profile": env.get("CLAUDE_SESSION_PROFILE") or None,
                         "repo": Path.cwd().name, "charter": marker.get("charter"),
                         "charter_sha256": marker.get("charter_sha256"),
                         "sitting_seconds": seconds, "ended_by": ended_by or "exit",
                         "restarts_24h": count + 1, "cap": self.g["cap"]}
                try:
                    self.fx.append(self.state, entry)       # §3.5: before the successor
                except (OSError, ledger.LedgerError) as e:
                    self.fx.say(f"{self.name}: the restart line was not written ({e}); "
                                "no successor starts")
                    reason = "cap"
                else:
                    self.restarts += 1
                    self.tally.append(self.fx.now())
                    sid = nxt
                    continue
            self._stop(sid, reason, code, seconds)
            return code

    # ---- the watch (§3.3) -------------------------------------------------------------

    def _watch(self, proc, sid, start):
        """Wait for the child; end it only when a confirmed marker passes the checks and
        the turn has ended and stood. Returns (status, ended_by, held reason)."""
        sdir = resolver.session_dir(self.state, sid)
        held = ended_by = term_at = seen = None
        forwarded = False
        while True:
            rc = self.fx.wait(proc, self.poll)
            if rc is not None:
                return rc, ended_by, held
            if signal.SIGTERM in self.got and not forwarded:
                self.fx.send(proc, signal.SIGTERM)          # §3.7: forwarded, the chain stops
                forwarded = True
            now = self.fx.now()
            if term_at is not None:              # §3.3 step 5 holds through a hang-up (A-F4)
                if ended_by == "launcher" and now - term_at >= self.kill_grace:
                    self.fx.send(proc, signal.SIGKILL)
                    ended_by = "kill"
                continue
            if self._stopping():
                continue
            if held is not None:
                continue
            conf = _json(sdir / hooks.CONFIRMED)
            if conf is None:
                continue
            if conf != seen:                                 # a confirmed marker appears
                seen = conf
                held = self._checks(sdir, sid, start, now)
                if held:
                    continue
            if not self._ready(sdir, now):
                continue
            try:
                self.g = self.guards()           # §4: a config edit counts before the signal
            except resolver.ResolveError as e:
                held = "config"                  # §3.7: nothing printed while a child runs;
                self.config_error = str(e)       # the error prints at the stop (N1)
                continue
            held = self._checks(sdir, sid, start, now)       # N4: again, right before
            if held:
                continue
            self.fx.send(proc, signal.SIGTERM)
            term_at, ended_by = now, "launcher"

    def _ready(self, sdir: Path, now: float) -> bool:
        """§3.3 step 3 and ruling 2: the turn ended after the marker, nothing ran since,
        the end has stood `settle`, the helpers are quiet `settle` and none has a call open."""
        settle = self.g["settle"]
        marker, te = _json(sdir / hooks.MARKER) or {}, _json(sdir / hooks.TURN_ENDED) or {}
        written, ended = marker.get("written"), te.get("at")
        if not (_num(written) and _num(ended)) or ended <= written or now - ended < settle:
            return False
        act = _json(sdir / hooks.ACTIVITY)
        if act is not None and not (_num(act.get("at")) and act["at"] <= ended):
            return False
        # calls/ first, then the stamp: a helper's Post stamps before it closes (B-F1), so a
        # close between the two reads leaves a fresh stamp, never a gap.
        try:
            if any(not p.name.startswith(".") for p in (sdir / hooks.CALLS).iterdir()):
                return False
        except FileNotFoundError:
            pass
        except OSError:
            return False
        helper = _json(sdir / hooks.HELPER_ACTIVITY)
        return helper is None or (_num(helper.get("at")) and now - helper["at"] >= settle)

    # ---- the checks (§3.4, §3.5) --------------------------------------------------------

    def _checks(self, sdir: Path, sid: str, start: float, now: float,
                which: str = "abcde") -> str | None:
        """The first of checks (a) to (e) that holds the sitting, by its reason."""
        try:
            raw = (sdir / hooks.MARKER).read_bytes()
            marker = json.loads(raw)
        except (OSError, ValueError):
            raw, marker = b"", None
        if "a" in which:
            conf = _json(sdir / hooks.CONFIRMED) or {}
            if (not isinstance(marker, dict) or marker.get("session") != sid
                    or conf.get("marker_sha256") != hashlib.sha256(raw).hexdigest()):
                return "not-main"
        if "b" in which:
            path = marker.get("charter") if isinstance(marker, dict) else None
            try:
                st = os.stat(path)
                line = charter.next_act_line(Path(path).read_bytes().decode("utf-8", "replace"))
            except (OSError, TypeError, ValueError):
                return "not-respawn"
            if line is None or not charter.RESPAWN.match(line) or st.st_mtime < start:
                return "not-respawn"
        if "c" in which and self._stop_file():
            return "stop-file"
        if "d" in which:
            count = self._count(now)
            if count is None or count >= self.g["cap"]:
                return "cap"
        if "e" in which and now - start < self.g["floor"]:
            return "floor"
        return None

    def _stop_file(self) -> bool:
        """A stop file counts when its mtime is at or after the chain's start (§3.5)."""
        for p in (self.state / "respawn" / "STOP", self.home / "STOP"):
            try:
                if os.stat(p).st_mtime >= self.started:
                    return True
            except OSError:
                pass
        return False

    def _count(self, now: float) -> int | None:
        """The restarts in the past 24 h: the larger of the ledger's count and the
        launcher's own tally (ruling 7); None when the ledger cannot be read."""
        try:
            n = self.fx.restarts(self.state, self.name, now)
        except ledger.LedgerError:
            return None
        return max(n, sum(1 for t in self.tally if t > now - 86400))

    def _decide(self, sid, start, rc, ended_by, held):
        """(reason, exit code, marker, count) at the child's exit; reason None restarts."""
        sdir = resolver.session_dir(self.state, sid)
        code = 0 if ended_by else _status(rc)
        if self._stopping():
            return ("hangup" if signal.SIGHUP in self.got else "terminated"), code, None, 0
        marker = _json(sdir / hooks.MARKER)
        if marker is None:
            return "no-marker", code, None, 0
        if not ended_by and rc != 0:
            return "crash", code, None, 0
        if held:
            if held == "config" and self.config_error:
                self.fx.say(f"{self.name}: {self.config_error}")
            return held, code, None, 0
        if not ended_by:                     # the launcher's own end resolved before it
            try:
                self.g = self.guards()                       # §4: again before each restart
            except resolver.ResolveError as e:
                self.fx.say(f"{self.name}: {e}")
                return "config", code, None, 0
        now = self.fx.now()
        # §3.4: after its own signal only (b) and (c); the cap held right before it.
        reason = self._checks(sdir, sid, start, now, "bc" if ended_by else "abcde")
        count = self._count(now)
        if count is None:
            count = sum(1 for t in self.tally if t > now - 86400)
        return reason, code, marker, count

    # ---- the grace, the stop, the signals (§3.4, §3.7) ---------------------------------

    def _grace(self, n: int, charter_path, k: int, cut: int) -> str | None:
        # A Ctrl-C the child took is dropped; one after the child's exit ends the chain.
        self.got = ([s for s in self.got[:cut] if s not in (signal.SIGINT, signal.SIGQUIT)]
                    + self.got[cut:])
        self.fx.say(f"{self.name}: sitting {n} ended on RESPAWN ({charter_path}); restart {k} "
                    f"of {self.g['cap']} in 24 h in {self.grace:g} s; touch "
                    f"{self.home / 'STOP'} or press Ctrl-C to end the chain")
        end = self.fx.now() + self.grace
        while True:
            if signal.SIGINT in self.got or signal.SIGQUIT in self.got:
                return "interrupted"
            if self._stopping():
                return "hangup" if signal.SIGHUP in self.got else "terminated"
            left = end - self.fx.now()
            if left <= 0:
                break
            self.fx.sleep(min(self.poll, left))
        return "stop-file" if self._stop_file() else None

    def _stop(self, sid: str, reason: str, code: int, seconds: int) -> None:
        env = getattr(self, "env", {})
        entry = {"kind": "stop", "chain": self.name, "session": sid,
                 "profile": env.get("CLAUDE_SESSION_PROFILE") or None,
                 "repo": Path.cwd().name, "reason": reason, "exit_status": code,
                 "sitting_seconds": seconds, "restarts": self.restarts}
        quiet = reason == "hangup"                           # §3.7: nothing more to the tty
        try:
            self.fx.append(self.state, entry)
        except (OSError, ledger.LedgerError) as e:
            if not quiet:
                self.fx.say(f"{self.name}: the stop line was not written ({e})")
        if not quiet:
            self.fx.say(f"{self.name}: the chain stopped ({reason}) after {self.restarts} "
                        "restart(s); to start it again:")
            self.fx.say(start_line(self.argv, env))

    def _stopping(self) -> bool:
        return signal.SIGHUP in self.got or signal.SIGTERM in self.got

    def _trap(self) -> dict:
        """§3.7: SIGINT and SIGQUIT only recorded (never SIG_IGN, which exec would pass
        on); SIGHUP and SIGTERM recorded and acted on."""
        def record(signum, frame):
            self.got.append(signum)
        old = {}
        for s in (signal.SIGINT, signal.SIGQUIT, signal.SIGHUP, signal.SIGTERM):
            try:
                old[s] = signal.signal(s, record)
            except (OSError, ValueError):                   # not the main thread
                pass
        return old

    def _untrap(self, old: dict) -> None:
        for s, h in old.items():
            try:
                signal.signal(s, h)
            except (OSError, ValueError, TypeError):
                pass
