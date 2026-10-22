"""The sitting's charter: open one, check its shape, close it (overhaul-r1 D10).

The port of the `charter-close` shape check (overhaul-r1 D10). The charter has five
parts and nothing else:
  1. the title line        # Sitting <date>-<n>: <repo>, <component>
  2. the table             goal, budget, pin, window, agents
  3. ## Done-ness
  4. ## Handover
  5. ## Next act
Refusals, the part named: a charter of 4,096 bytes or more (doclint's `>=`); a missing part; a table
missing one of its five rows. An empty Done-ness or Handover is not refused
here: `open` seeds the Handover's open-by-level line (none with priority off); `close` fills it.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import rules

CEILING = 4096
TABLE_ROWS = ("goal", "budget", "pin", "window", "agents")
ROW_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TITLE_RE = re.compile(r"^# Sitting (\d{4}-\d{2}-\d{2})-(\d+): (.+)$")
PARTS = ((3, "## Done-ness"), (4, "## Handover"), (5, "## Next act"))
DEFAULT_DIR = "history/sittings"
# A RESPAWN close (respawn-r1 §3.2): the Next act's first non-blank line opens on it.
RESPAWN = re.compile(r"^RESPAWN(?=[:.\s]|$)")
# Waiting on an outside party (S21): `WAITING <n>: <what>; <how to tell>`, n from 1.
WAITING = re.compile(r"^WAITING(?=[:.\s]|$)")
WAITING_LINE = re.compile(r"^WAITING ([1-9][0-9]*): ([^;]*\S[^;]*); (.*\S.*)$")
NEXT_ACT = "## Next act"


class CharterError(ValueError):
    pass


def _table(lines: list[str]) -> dict:
    table = {}
    for line in lines:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = s.strip("|").split("|", 1)
            if len(cells) == 2:
                table[cells[0].strip()] = cells[1].strip()
    return table


def check_text(raw: bytes) -> list[str]:
    """Every refusal for one charter's bytes; empty when the shape holds."""
    out = []
    if len(raw) >= CEILING:
        out.append("charter is %d bytes, at or over the %d-byte ceiling (section 3.1: "
                   "move text out, never widen the ceiling)" % (len(raw), CEILING))
    lines = raw.decode("utf-8", "replace").splitlines()
    if not any(TITLE_RE.match(line.rstrip()) for line in lines):
        out.append("part 1 (the title line '# Sitting <date>-<n>: <repo>, "
                   "<component>') is missing")
    table = _table(lines)
    if not table:
        out.append("part 2 (the table) is missing")
    else:
        out.extend("part 2 (the table) is missing its '%s' row" % row
                   for row in TABLE_ROWS if row not in table)
    heads = {line.rstrip() for line in lines}
    out.extend("part %d (%s) is missing" % (n, h) for n, h in PARTS if h not in heads)
    return out


def next_act_line(text: str) -> str | None:
    """The `## Next act` section's first non-blank line, its trailing blanks cut; None
    without the section or with an empty one. Only this section is read, never `check`."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.rstrip() == NEXT_ACT), None)
    if start is None:
        return None
    for line in lines[start + 1:]:
        if line.startswith("## "):
            return None
        if line.strip():
            return line.rstrip()
    return None


def waiting(line: str | None) -> int | None:
    """n of a Next act line `WAITING <n>: <what>; <how to tell>`; 0 when the line
    opens WAITING misshapen; None when it does not open WAITING."""
    if not line or not WAITING.match(line):
        return None
    m = WAITING_LINE.match(line.rstrip())
    return int(m.group(1)) if m else 0


def warnings(raw: bytes, session: dict) -> list[str]:
    """What `check` and `close` print on stderr, their exit unchanged (S21): no
    `- open by level:` line under Handover (priority on); a Next act opening WAITING
    misshapen, or at n of `pacing.waiting` or more (pacing on), whose line says to wake
    at the cache's idle limit and commit the charter: a wait never stops the loop (S36).
    A well-formed WAITING whose <what> names the usage meter (S29) gets its own line at
    any n, never the idle limit's: a meter wait is not WAITING."""
    text = raw.decode("utf-8", "replace")
    priority, pacing = rules.parts(session)
    out = []
    if priority["enabled"] and not rules.handover_listed(text):
        out.append(f"the Handover has no '{rules.HANDOVER}' line (session.priority is on): "
                   f"list the open items by level, highest first, or '{rules.SEED}'")
    line = next_act_line(text)
    n = waiting(line) if pacing["enabled"] else None
    if n:
        what = WAITING_LINE.match(line.rstrip()).group(2)
        if re.search(r"\b(room for|meter|usage limit|five-hour|5h)", what, re.I):
            out.append("a wait on the usage meter is not WAITING (session.pacing): keep the "
                       "act as the Next act and wake at the band's reset")
            return out
    if n == 0:
        out.append("the Next act opens WAITING but is not "
                   "'WAITING <n>: <what>; <how to tell>' (session.pacing is on)")
    elif n is not None and n >= pacing["waiting"]:
        out.append(f"WAITING {n} is at session.pacing.waiting ({pacing['waiting']}) or past "
                   "it: wake at the cache's idle limit, bring the charter current and commit "
                   "it; a wait never stops the loop or closes the sitting, only the checkpoint "
                   "does")
    return out


def check(path) -> list[str]:
    """The refusals for the charter at `path`. Raises OSError when unreadable."""
    return check_text(Path(path).read_bytes())


def _one_line(text: str, limit: int) -> str:
    """`text` on one line, pipes made slashes, whitespace collapsed; past `limit` it is
    cut after the last whole word that fits and marked "…", within `limit` with the
    mark, and cut hard only when the window holds no space."""
    s = " ".join(str(text).replace("|", "/").split())
    if len(s) <= limit:
        return s
    k = s.rfind(" ", 0, limit)
    return (s[:k] if k > 0 else s[:limit - 1]) + "…"


def _k(n) -> str:
    try:
        return f"{round(int(n) / 1000)}k"
    except (TypeError, ValueError):
        return "?"


def today() -> str:
    return time.strftime("%Y-%m-%d")


def _numbered(dir: Path, date: str) -> list[tuple[int, Path]]:
    pat = re.compile(r"^%s-(\d+)(-[A-Za-z0-9._-]+)?\.md$" % re.escape(date))
    found = []
    for p in Path(dir).glob(f"{date}-*.md"):
        m = pat.match(p.name)
        if m:
            found.append((int(m.group(1)), p))
    return sorted(found)


def newest_today(dir) -> Path | None:
    found = _numbered(Path(dir), today())
    return found[-1][1] if found else None


def open(dir, goal: str, section: dict, head: str | None,
         repo: str | None = None, row: str | None = None) -> Path:
    """Write `<dir>/<today>-<n>.md`, or `<today>-<n>-<row>.md` when a relay row names
    it (`$RELAY_ROW`), `n` one past today's highest; the table from the resolved
    `session` section. A row outside `[A-Za-z0-9._-]` is ignored. Returns the path."""
    dir = Path(dir)
    dir.mkdir(parents=True, exist_ok=True)
    date = today()
    found = _numbered(dir, date)
    n = found[-1][0] + 1 if found else 1
    suffix = f"-{row}" if row and ROW_RE.match(row) else ""
    goal = _one_line(goal, 300) or "?"
    repo = _one_line(repo or Path.cwd().name, 60) or "?"
    c = section.get("ceilings") or {}
    at = section.get("checkpoint_at")
    at = f"{float(at):.0%}" if isinstance(at, (int, float)) else "80%"
    text = "\n".join([
        f"# Sitting {date}-{n}: {repo}, {_one_line(goal, 60)}",
        "",
        "| item | value |",
        "|---|---|",
        f"| goal | {goal} |",
        f"| budget | {c.get('turns', '?')} turns, {_k(c.get('context'))} context; "
        f"charter current at {at} |",
        f"| pin | {_one_line(head or 'no commit', 40)} |",
        f"| window | {_k(section.get('window'))} |",
        "| agents | 0 |",
        "",
        "## Done-ness",
        "- [x] charter written at open: this file",
        "",
        "## Handover",
        *([rules.SEED] if rules.parts(section)[0]["enabled"] else []),
        "",
        "## Next act",
        "The first act toward the goal; bring this charter current at every commit.",
        "",
    ])
    path = dir / f"{date}-{n}{suffix}.md"
    with path.open("x") as fh:
        fh.write(text)
    return path


def exit_line(exit_text: str, meter: dict | None) -> str:
    text = _one_line(exit_text, 200) or "?"
    try:
        about = f"about {_k(meter['context'])} context, {int(meter['turns'])} turns"
    except (TypeError, KeyError, ValueError):
        about = "meter unknown"
    return f"- exit taken: {text}; {about}"


def close(path, exit_text: str, meter: dict | None) -> None:
    """Append the exit line as the Handover's last line. Raises CharterError when
    `check` refuses or the result would pass the ceiling."""
    path = Path(path)
    raw = path.read_bytes()
    refusals = check_text(raw)
    if refusals:
        raise CharterError(refusals[0])
    lines = raw.decode("utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.rstrip() == "## Handover")
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    last = end
    while last > start + 1 and not lines[last - 1].strip():
        last -= 1
    new = lines[:last] + [exit_line(exit_text, meter), ""] + lines[end:]
    out = ("\n".join(new) + "\n").encode("utf-8")
    if len(out) >= CEILING:
        raise CharterError("charter would be %d bytes, at or over the %d-byte ceiling"
                           % (len(out), CEILING))
    path.write_bytes(out)
