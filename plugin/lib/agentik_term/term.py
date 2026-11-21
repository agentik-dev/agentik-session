"""term: the one writer. Every byte a person reads leaves through here, by message id.

Each stream is judged alone, by isatty: on a terminal a status is a glyph, colour may be on, and
a table is laid out to the width (`COLUMNS`, else the terminal's own): a long cell wraps inside
its column and a path or a command that does not fit goes whole under its row, so neither is cut; off one a status is a word (ok, warn, FAIL, note), with no escape
byte and no redraw. NO_COLOR set to a value,
TERM=dumb or --no-color turns colour off; the glyphs stay. Columns are left-aligned, two spaces
apart; a name is bold, a path or a hint dim; nothing is told by colour alone.

A stream that is closed, or whose reader has gone, takes nothing more and raises nothing, at a
write or at the interpreter's exit; a character a stream cannot encode is replaced; a value has
its control characters (C0, DEL, C1) removed, so no file or variable puts an escape byte out; a
tab or a line break in it is one space, and the line and direction controls (U+2028, U+2029,
U+202A to U+202E, U+2066 to U+2069) are removed.
"""
import json
import os
import re
import sys
import unicodedata

from . import catalogue

GLYPH = {"ok": "✓", "warn": "!", "fail": "✗", "note": "·"}
WORD = {"ok": "ok", "warn": "warn", "fail": "FAIL", "note": "note"}
MARK_SGR = {"ok": "32", "warn": "33", "fail": "31", "note": "36"}
STYLE_SGR = {"name": "1", "path": "2", "hint": "2"}
GAP = "  "
FALLBACK_WIDTH = 80
LEAST_WIDTH = 40  # a terminal's width under this is taken as this (row sc3-table R1)
LAST_ROOM = 24  # a last column with less room puts a long last cell under its row (R5)
ZERO_WIDTH = ("Mn", "Me", "Cf")
CONTROL = re.compile("[\x00-\x1f\x7f-\x9f]")
JSON_CONTROL = re.compile("[\x00-\x09\x0b-\x1f\x7f-\x9f]")  # a line break survives, escaped


LINE_CONTROL = re.compile("[\u2028\u2029\u202a-\u202e\u2066-\u2069]")  # line and direction controls
BREAK = re.compile("\r\n|[\t\n\x0b\x0c\r\x1c-\x1e\x85]")  # a tab or a line break


def clean(value):
    """The value as text, with its control characters removed: a tab or a line break becomes one
    space, so no value splits a row or glues two words, and the line and direction controls go,
    so no value reorders a row or starts another."""
    return LINE_CONTROL.sub("", CONTROL.sub("", BREAK.sub(" ", str(value))))


def columns(text):
    """The screen columns a text takes: a wide or fullwidth character two, a combining mark or a
    zero-width character none (row sc3-table R2), any other one."""
    return sum(0 if unicodedata.combining(c) or unicodedata.category(c) in ZERO_WIDTH and c != "\xad"
               else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _wrap(text, room):
    """The text in lines of at most `room` columns, broken at spaces; a word longer than the room
    stands whole on a line of its own (row sc3-table R4)."""
    lines, now = [], ""
    for word in text.split():
        if now and columns(now) + 1 + columns(word) <= room:
            now += " " + word
        else:
            if now:
                lines.append(now)
            now = word
    return lines + [now]


def _cut_to(text, room):
    """The text whole where it fits the room, else cut to it with `…` (row sc7 F1)."""
    return text if columns(text) <= room else fit(text, room, "…")


def fit(text, room, mark):
    """The text cut so that it and its mark take at most `room` columns; a combining mark stays
    with the character it follows."""
    room -= columns(mark)
    kept, used = [], 0
    for c in text:
        used += columns(c)
        if used > room:
            break
        kept.append(c)
    return "".join(kept) + mark


def _cleaned(obj):
    """For --json: control characters removed but the line break, which json.dumps writes as
    the two characters of its escape, so a tool's block of lines keeps its shape."""
    if isinstance(obj, str):
        return JSON_CONTROL.sub("", obj)
    if isinstance(obj, dict):
        return {clean(k): _cleaned(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_cleaned(v) for v in obj]
    return obj


def name(text):
    return (text, "name")


def path(text):
    return (text, "path")


def cut(text):
    """A cell that, on a terminal, ends at its room with `…` where it does not fit (row sc7 R2):
    a summary, never a key, a value, a path or a command. Off a terminal it prints whole."""
    return (text, "cut")


def colour_off(env, no_color):
    return bool(no_color or env.get("NO_COLOR") or env.get("TERM") == "dumb")


class _Stream:
    def __init__(self, raw, no_colour, env=None):
        self.raw = raw
        self.env = env if env is not None else {}
        self.gone = raw is None
        try:
            self.tty = raw.isatty()
        except (AttributeError, ValueError, OSError):
            self.tty = False
        self.colour = self.tty and not no_colour
        self.encoding = getattr(raw, "encoding", None) or "ascii"
        try:  # every non-ASCII character this writer itself prints
            "".join(GLYPH.values()).encode(self.encoding)
            self.glyphs = self.tty
        except (LookupError, UnicodeEncodeError):
            self.glyphs = False

    def width(self):
        """On a terminal, `COLUMNS` from the command's environment where it is a whole number
        above 0, else the terminal's own size, else 80, and never under 40; off one, 80, whatever
        `COLUMNS` holds (row sc3-table R1)."""
        if not self.tty:
            return FALLBACK_WIDTH
        given = str(self.env.get("COLUMNS") or "")
        cols = int(given) if re.fullmatch("[0-9]+", given) else 0
        if cols <= 0:
            try:
                cols = os.get_terminal_size(self.raw.fileno()).columns
            except (AttributeError, ValueError, OSError):
                cols = 0
        return max(cols if cols > 0 else FALLBACK_WIDTH, LEAST_WIDTH)

    def paint(self, text, sgr):
        if not self.colour or not sgr or not text:
            return text
        return "\x1b[%sm%s\x1b[0m" % (sgr, text)

    def mark(self, status):
        shown = GLYPH[status] if self.glyphs else WORD[status]
        return shown, self.paint(shown, MARK_SGR[status])

    def write(self, line):
        if self.gone:
            return
        try:
            line = line.encode(self.encoding, "replace").decode(self.encoding)
        except LookupError:
            line = line.encode("ascii", "replace").decode("ascii")
        try:
            self.raw.write(line + "\n")
        except (AttributeError, ValueError, OSError):
            self.drop()

    def flush(self):
        try:
            self.gone or self.raw.flush()
        except (AttributeError, ValueError, OSError):
            self.drop()

    def drop(self):
        """Take nothing more; the stream's descriptor now points at the null device, so the
        interpreter's own flush at exit finds a place for what its buffer still holds."""
        self.gone = True
        try:
            null = os.open(os.devnull, os.O_WRONLY)
            try:
                os.dup2(null, self.raw.fileno())
            finally:
                os.close(null)
        except (AttributeError, ValueError, OSError):
            pass


def _ordered(line):
    """A refusal's line with U+2028, U+2029 and the direction controls (U+202A to U+202E, U+2066
    to U+2069) removed, so a typed word neither starts a line nor reorders one (sc4 review 1 F8)."""
    return re.sub("[  ‪-‮⁦-⁩]", "", line)


def unreadable(path, err=None):  # the one line written with no catalogue to write it from
    _Stream(sys.stderr if err is None else err, True).write(
        "FAIL  cannot read %s; reinstall the plugin to mend it" % path)
    return 2


class Term:
    def __init__(self, no_color=False, quiet=False, env=None, out=None, err=None, messages=None):
        env = os.environ if env is None else env
        off = colour_off(env, no_color)
        self.out = _Stream(out if out is not None else sys.stdout, off, env)
        self.err = _Stream(err if err is not None else sys.stderr, off, env)
        self.quiet = quiet
        self.messages = messages if messages is not None else catalogue.load()

    def text(self, mid, **values):
        return catalogue.fill(self.messages[mid], {k: clean(v) for k, v in values.items()})

    def _stream(self, err):
        return self.err if err else self.out

    def line(self, mid, err=False, style=None, **values):
        stream = self._stream(err)
        stream.write(stream.paint(self.text(mid, **values), STYLE_SGR.get(style)))

    def blank(self, err=False):
        self._stream(err).write("")

    def table(self, rows, err=False, indent=2, mark_at=0):
        """rows: (status or None, [cell...], after or None); a cell is a str or (str, style).
        The status shows as a column at mark_at. `after` is a line under the row, set at the
        last column's start. Columns are measured and padded by `columns`. Off a terminal one row
        is one line (row sc3-table R9); on one the table is laid out to its width (`_laid`).
        Nothing is cut but a `cut` cell on a terminal (row sc7 R2)."""
        stream = self._stream(err)
        if not rows:
            return
        marked = any(r[0] for r in rows)
        grid = []
        for status, cells, after in rows:
            cells = [(clean(c[0]), c[1]) if isinstance(c, tuple) else (clean(c), None) for c in cells]
            if marked:
                shown, painted = stream.mark(status) if status else ("", "")
                cells.insert(mark_at, (shown, painted))
            grid.append((cells, clean(after) if after else after))
        ncols = max(len(cells) for cells, _ in grid)
        widths = [max((columns(cells[i][0]) for cells, _ in grid if i < len(cells)), default=0)
                  for i in range(ncols)]
        if stream.tty:
            return self._laid(stream, grid, widths, indent, marked, mark_at)
        for cells, after in grid:  # off a terminal one row is one line (R9)
            shown = " " * indent
            for i, (text, style) in enumerate(cells):
                is_mark = marked and i == mark_at  # its style slot holds the painted mark
                painted = style if is_mark else stream.paint(text, STYLE_SGR.get(style))
                pad = "" if i == len(cells) - 1 else " " * (widths[i] - columns(text)) + GAP
                shown += painted + pad
            stream.write(shown.rstrip(" "))
            if after:
                start = indent + sum(w + len(GAP) for w in widths[:len(cells) - 1])
                stream.write(" " * start + stream.paint(after, STYLE_SGR["hint"]))

    def _laid(self, stream, grid, widths, indent, marked, mark_at):
        """A table on a terminal of width W (row sc3-table R3 to R8): each column but a row's last
        is as wide as its widest cell and at most a third of W; the last takes what is left. A
        plain cell or a name too wide for its column wraps at spaces inside it, the other cells
        staying on the row's first line. A path that does not fit its column and is not the row's
        last stays whole at its column's start, unpadded, and each cell after it goes under the
        row at its indent plus 4, dim, wrapped to W (review 1 F1); a last path, or an `after`
        line, that does not fit goes whole there; a last cell with under 24 columns left, or with
        a word longer than its room, goes there too and wraps to W. Each line of a cell is
        painted on its own; nothing is cut but a `cut` cell, which ends at its room with `…`
        (row sc7 R2)."""
        width = stream.width()
        widths = [min(w, width // 3) for w in widths]
        fixed = " " * (indent + 4)
        starts = [indent]
        for w in widths:
            starts.append(starts[-1] + w + len(GAP))
        dim = STYLE_SGR["hint"]
        for cells, after in grid:
            blocks, under, rest = [], [], False
            at = indent  # where the next cell starts on the row's first line, as laid
            for i, (text, style) in enumerate(cells):
                last = i == len(cells) - 1
                room = width - starts[i] if last else widths[i]
                if style == "cut" and last:  # from where the row's text really ends (sc7 F2)
                    room = width - at
                if rest and not (marked and i == mark_at):  # after a path that kept its place
                    blocks.append([""])
                    if style == "cut":
                        under.append(_cut_to(text, width - len(fixed)))
                    else:
                        under.extend(_wrap(text, width - len(fixed)) if text.strip() else [])
                elif marked and i == mark_at or columns(text) <= room:
                    blocks.append([text])
                elif style == "path" and not last:  # it keeps the first line (review 1 F1)
                    blocks.append([text])
                    rest = True
                elif style == "path":
                    blocks.append([""])
                    under.append(text)
                elif style == "cut" and last and i and room < LAST_ROOM:  # under its row, cut there
                    blocks.append([""])
                    under.append(_cut_to(text, width - len(fixed)))
                elif style == "cut":  # it ends at its room (row sc7 R2)
                    blocks.append([fit(text, room, "…")])
                elif last and i and (room < LAST_ROOM or max(map(columns, text.split()), default=0) > room):
                    blocks.append([""])
                    under.extend(_wrap(text, width - len(fixed)))
                else:
                    blocks.append(_wrap(text, room))
                at += max(widths[i], columns(blocks[i][0])) + len(GAP)
            for k in range(max(len(b) for b in blocks)):
                shown = " " * indent
                for i, (text, style) in enumerate(cells):
                    piece = blocks[i][k] if k < len(blocks[i]) else ""
                    if marked and i == mark_at:  # the mark keeps its place on the first line (R8)
                        piece, painted = (text, style) if k == 0 else ("", "")
                    else:
                        painted = stream.paint(piece, STYLE_SGR.get(style))
                    pad = "" if i == len(cells) - 1 else " " * (widths[i] - columns(piece)) + GAP
                    shown += painted + pad
                stream.write(shown.rstrip(" "))
            for line in under:
                stream.write(fixed + stream.paint(line, dim))
            if after:
                start = starts[len(cells) - 1]
                lead = " " * start if start + columns(after) <= width else fixed
                stream.write(lead + stream.paint(after, dim))

    def grid(self, status, label, rows, err=False):
        """One part of a status screen (packet su2-screen R4): the mark, or its blank when the
        status is None, two spaces, the label bold and padded to 8, two spaces, then each row at
        the text's column. A row is (text or [cell...], style, whole); a row of cells pads each
        cell but the last to the widest of its column among the part's rows, two spaces apart.
        On a terminal no cell but the last takes more than a third of the width: a longer one
        ends at it with an ellipsis, so one row's long cell never pushes another row's last cell
        off; a row past the width ends at it with an ellipsis, unless it is whole. A width is in
        screen columns (`columns`). No row ends in a space."""
        stream = self._stream(err)
        rows = rows or [("", None, False)]
        try:
            ellipsis = "…"
            ellipsis.encode(stream.encoding)
        except (LookupError, UnicodeEncodeError):
            ellipsis = "..."
        third = stream.width() // 3
        widths, laid = {}, []
        for cells, style, whole in rows:
            if isinstance(cells, (list, tuple)):
                cells = [clean(c) for c in cells]
                if stream.tty and not whole:
                    cells = [fit(c, third, ellipsis) if columns(c) > third else c for c in cells[:-1]] + cells[-1:]
                for i, cell in enumerate(cells[:-1]):
                    widths[i] = max(widths.get(i, 0), columns(cell))
            laid.append((cells, style, whole))
        lead = 1 if stream.glyphs else 4
        label = clean(label)
        for n, (cells, style, whole) in enumerate(laid):
            if isinstance(cells, list):
                line = "".join(c + " " * (widths[i] - columns(c)) + GAP for i, c in enumerate(cells[:-1]))
                line += cells[-1] if cells else ""
            else:
                line = clean(cells)
            line = line.rstrip(" ")
            plain = " " * (lead + len(GAP) + 8 + len(GAP))
            head = plain
            if n == 0:
                shown, painted = stream.mark(status) if status else ("", "")
                head = (painted + " " * (lead - len(shown)) + GAP
                        + stream.paint(label, STYLE_SGR["name"]) + " " * (8 - columns(label)) + GAP)
            room = stream.width() - len(plain)
            if stream.tty and not whole and columns(line) > room:
                line = fit(line, room, ellipsis)
            shown = head + stream.paint(line, STYLE_SGR.get(style))
            stream.write(shown if line else shown.rstrip(" "))

    def hint(self, mid, values=None, **more):
        values = dict(values or {}, **more)
        if not self.quiet:
            self.flush()  # the answer first, where both streams share one pipe
            stream = self.err  # a message that starts `next:` has no mark before it (row sc4 R1)
            text = self.text(mid, **values)
            lead = ""
            if not text.startswith("next:"):  # its mark on a terminal, `next:` off one (review 1 F7)
                lead = stream.mark("note")[1] + GAP if stream.tty else "next: "
            stream.write(lead + stream.paint(text, STYLE_SGR["hint"]))

    def error(self, mid, next_=None, **values):
        """A refusal: the cause behind the fail mark, then, where one mends it, `next: ` and the
        command to paste, with no mark (row sc4 R1); neither line holds a line or direction
        control (sc4 review 1 F8). What stdout holds goes first, where both streams share one pipe
        (row ic1-close R4)."""
        self.out.flush()
        stream = self.err
        shown, painted = stream.mark("fail")
        stream.write(_ordered(painted + GAP + self.text(mid, **values)))
        if next_:  # a value of the cause's own may be called `command`
            stream.write(_ordered(self.text("err.next", command=next_)))

    def marked(self, text, spans, sgr="7"):
        """One line on stdout as it is, each (start, end) of `spans` painted on a terminal; off
        one, or with colour off, the text alone (the issue's draft, packet rp6-verb R4)."""
        stream = self.out
        if CONTROL.search(text):
            text, spans = clean(text), []
        shown, at = "", 0
        for a, b in sorted(spans):
            if a < at:
                continue
            shown += text[at:a] + stream.paint(text[a:b], sgr)
            at = b
        stream.write(shown + text[at:])

    def verbatim(self, text):
        """Text on stdout as the caller made it, a line break after it: a shell script, or the
        completion callback's `name<TAB>summary` lines, each part cleaned by the caller (row
        ak12-polish R5)."""
        self.out.write(text)

    def json(self, obj):
        self.out.write(json.dumps(_cleaned(obj), ensure_ascii=True, sort_keys=False))

    def flush(self):
        for stream in (self.out, self.err):
            stream.flush()


def append(path, text):
    """The one file this package appends to, setup's journal (packet ak3-setup R9)."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)


def keep(path, data, mode=0o600):
    """A file of the issue's drafts written whole, by a rename beside it, so a reader sees the old
    bytes or the new ones (packet rp6-verb R4, R5); a link at the temporary name is not followed."""
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, ".%s.%d.tmp" % (name, os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
