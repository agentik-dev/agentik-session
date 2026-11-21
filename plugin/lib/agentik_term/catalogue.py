"""The catalogue: every message a person reads, by id, from messages.md beside this file.

One list item per message, `- `id`: text`. A placeholder is written `{name}` inside backticks;
the loader takes the backticks off a span that is exactly one placeholder and keeps every other
span as written. Lines that are not list items (the title, the note under it) are not messages;
a list item that is not such an item (an id with a capital, no colon) is a ValueError.
"""
import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.md")
ITEM = re.compile(r"^- `([a-z0-9_.]+)`: (.+)$")
LONE = re.compile(r"`(\{[a-z_]+\})`")
SLOT = re.compile(r"\{([a-z_]+)\}")


def load(path=PATH):
    """{id: template}; a ValueError on an id given twice or an item it cannot read."""
    found = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            m = ITEM.match(line)
            if not m:
                if line.startswith("- "):
                    raise ValueError("messages.md: not an item: %s" % line[:80])
                continue
            if m.group(1) in found:
                raise ValueError("messages.md: %s is given twice" % m.group(1))
            found[m.group(1)] = LONE.sub(r"\1", m.group(2))
    return found


def slots(template):
    return SLOT.findall(template)


def fill(template, values):
    """The template with each `{name}` replaced; a KeyError names a value not given."""
    return SLOT.sub(lambda m: str(values[m.group(1)]), template)
