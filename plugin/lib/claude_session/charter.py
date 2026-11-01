"""The sitting's charter: open one, check its shape, close it (overhaul-r1 D10).

The port of the `charter-close` shape check (overhaul-r1 D10). The charter has six
parts and nothing else:
  1. the title line        # Sitting <date>-<n>: <repo>, <component>
  2. the table             goal, budget, pin, window, agents
  3. ## Done-ness
  4. ## Handover
  5. ## While waiting      (S40; a charter opened before alpha.24 has none)
  6. ## Next act
Refusals, the part named: a charter of 4,096 bytes or more (doclint's `>=`); a missing part
other than While waiting; a table missing one of its five rows. An empty Done-ness or Handover
is not refused here: `open` seeds the Handover's open-by-level line (none with priority off)
and While waiting's `- none`; `close` fills the Handover. While waiting's lines are
`- ready: <row> (<repo>, S<n>)` (at most three), `- owed: <item>; <what it needs>`, or
`- none` alone; a Next act of WAITING beside any other line is the red (`RED`), which
`charter check` exits 1 on.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from . import rules

CEILING = 4096
# design/05 §6: `open --continue` adopts today's charter under this many bytes; at it, spills.
CONTINUE_BELOW = 3584
TABLE_ROWS = ("goal", "budget", "pin", "window", "agents")
ROW_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TITLE_RE = re.compile(r"^# Sitting (\d{4}-\d{2}-\d{2})-(\d+): (.+)$")
WHILE_WAITING = "## While waiting"
PARTS = ((3, "## Done-ness"), (4, "## Handover"), (5, WHILE_WAITING), (6, "## Next act"))
DEFAULT_DIR = "history/sittings"
# A RESPAWN close (respawn-r1 §3.2): the Next act's first non-blank line opens on it.
RESPAWN = re.compile(r"^RESPAWN(?=[:.\s]|$)")
# Waiting on an outside party (S21): `WAITING <n>: <what>; <how to tell>`, n from 1.
WAITING = re.compile(r"^WAITING(?=[:.\s]|$)")
WAITING_LINE = re.compile(r"^WAITING ([1-9][0-9]*): ([^;]*\S[^;]*); (.*\S.*)$")
NEXT_ACT = "## Next act"
# The While waiting section (S40): its three line shapes, and the red of a WAITING beside it.
NONE = "- none"
READY_LINE = re.compile(r"^- ready: (\S+) \(([^,()]*\S[^,()]*), S([1-9][0-9]*)\)$")
OWED_LINE = re.compile(r"^- owed: ([^;]*\S[^;]*); (.*\S.*)$")
MAX_READY = 3
RED = "WAITING while ready"


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
    out.extend("part %d (%s) is missing" % (n, h) for n, h in PARTS
               if h not in heads and h != WHILE_WAITING)
    return out


def while_waiting(raw: bytes) -> list[str] | None:
    """The While waiting section's non-blank lines, their trailing blanks cut; None when
    the charter has no such section (opened before alpha.24)."""
    lines = raw.decode("utf-8", "replace").splitlines()
    start = next((i for i, l in enumerate(lines) if l.rstrip() == WHILE_WAITING), None)
    if start is None:
        return None
    out = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.strip():
            out.append(line.rstrip())
    return out


def _near_miss(text: str) -> str | None:
    """A heading that is nearly `## While waiting` (its case, or a tail after it), or None."""
    for line in text.splitlines():
        s = line.strip()
        if line.rstrip() != WHILE_WAITING and s.lower().startswith(WHILE_WAITING.lower()):
            return line.rstrip()
    return None


def _while_waiting_shape(lines: list[str] | None, text: str = "") -> list[str]:
    """The section's shape warnings (S40 ruling 1), each naming its line or heading."""
    if lines is None:
        near = _near_miss(text)
        if near is not None:
            return [f"heading '{near}' is not '{WHILE_WAITING}'"]
        return ["no While waiting section (opened before alpha.24): add it with - none"]
    if not lines:
        return ["While waiting is empty: write - none, or the ready rows and owed items"]
    out = []
    if NONE in lines and len(lines) > 1:
        out.append(f"While waiting has '{NONE}' beside other lines: drop '{NONE}' "
                   "or the others")
    shape = ("'- ready: <row> (<repo>, S<n>)', '- owed: <item>; <what it needs>' "
             f"or '{NONE}' alone")
    out.extend(f"While waiting line is not {shape}: {line}" for line in lines
               if line != NONE and not READY_LINE.match(line) and not OWED_LINE.match(line))
    ready = sum(bool(READY_LINE.match(line)) for line in lines)
    if ready > MAX_READY:
        out.append(f"While waiting lists {ready} ready rows, at most {MAX_READY}: keep the "
                   "next three")
    return out


def _red(lines: list[str] | None) -> str | None:
    """The red of a WAITING Next act beside a While waiting line other than `- none`."""
    others = [line for line in lines or () if line != NONE]
    if not others:
        return None
    first = next((line for line in others if READY_LINE.match(line) or OWED_LINE.match(line)),
                 None)
    if first is None:
        return f"{RED}: {others[0]} (not a ready or owed shape: fix the line or take it)"
    return (f"{RED}: {first}; take it, since WAITING is legal only when While waiting "
            f"reads {NONE}")


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
    """What `check` and `close` print on stderr (S21): no `- open by level:` line under
    Handover (priority on); a Next act opening WAITING misshapen, or at n of
    `pacing.waiting` or more (pacing on), whose line says to wake at the cache's idle
    limit and commit the charter: a wait never stops the loop (S36). A well-formed
    WAITING whose <what> names the usage meter (S29) gets its own line at any n, never
    the idle limit's: a meter wait is not WAITING. Whatever pacing says (S40): the
    While waiting section's shape. With pacing on, the red, first in the list: a Next
    act of WAITING (n of 1 or more, or misshapen) beside a line other than `- none`.
    `check` exits 1 on the red; every other line, and `close`, leave the exit alone."""
    text = raw.decode("utf-8", "replace")
    priority, pacing = rules.parts(session)
    out = []
    if priority["enabled"] and not rules.handover_listed(text):
        out.append(f"the Handover has no '{rules.HANDOVER}' line (session.priority is on): "
                   f"list the open items by level, highest first, or '{rules.SEED}'")
    line = next_act_line(text)
    n = waiting(line) if pacing["enabled"] else None
    lines = while_waiting(raw)
    out.extend(_while_waiting_shape(lines, text))
    if n:
        what = WAITING_LINE.match(line.rstrip()).group(2)
        if re.search(r"\b(room for|meter|usage limit|five-hour|5h)"
                     r"|\b(week|weekly|7d|seven-day|band)\b", what, re.I):
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
    red = _red(lines) if n is not None else None
    return [red] + out if red else out


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


def _suffix(row: str | None) -> str:
    """The name's suffix as `open` derives it: `-<row>`, or none for a row outside the set."""
    return f"-{row}" if row and ROW_RE.match(row) else ""


def adoptable(dir, row: str | None = None) -> Path | None:
    """`open --continue` (design/05 §6): today's newest charter of `open`'s suffix for `row`,
    when it is under CONTINUE_BELOW bytes; None when there is none or it is at the mark (the
    next sitting spills to n+1). Reads the file's size only, never its bytes."""
    date, suffix = today(), _suffix(row)
    same = [p for n, p in _numbered(Path(dir), date) if p.name == f"{date}-{n}{suffix}.md"]
    if not same:
        return None
    try:
        return same[-1] if same[-1].is_file() and same[-1].stat().st_size < CONTINUE_BELOW \
            else None
    except OSError:
        return None


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
    suffix = _suffix(row)
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
        WHILE_WAITING,
        NONE,
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
