"""The strict YAML subset the config files are written in (D12).

The tool is stdlib, so it cannot import PyYAML; it reads the subset and refuses
everything outside it by name rather than guessing:

  accepted  mappings nested by indentation; scalars (null, booleans, integers,
            floats, quoted and bare strings); flat lists (`- x` and `[a, b]`);
            `{k: v}` flow mappings one level deep; `#` comments
  refused   anchors and aliases, tags, multi-line scalars, nested lists, tabs,
            duplicate keys, documents markers

`dump` writes the same subset back, keys in the order given, so the `.yaml`
twin of a resolved file is as deterministic as its JSON.
"""

from __future__ import annotations

import json
import re


class YAMLSubsetError(ValueError):
    def __init__(self, line: int, reason: str):
        super().__init__(f"line {line}: {reason}")
        self.line = line
        self.reason = reason


_KEY = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?:\s+(.*))?$")
_INT = re.compile(r"^[-+]?[0-9]+$")
_FLOAT = re.compile(r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?$")
_BARE_REFUSED = ("&", "*", "!", "|", ">", "%", "@", "`")


def _strip_comment(text: str) -> str:
    """Drop a `#` comment that is outside quotes and preceded by space."""
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def _split_flow(body: str, ln: int) -> list[str]:
    """Split `a, b, "c, d"` at top-level commas; refuse nesting."""
    parts, cur, quote = [], "", None
    for ch in body:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[]{}":
            raise YAMLSubsetError(ln, "nested flow collection")
        elif ch == ",":
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if quote:
        raise YAMLSubsetError(ln, "unterminated quote")
    if cur.strip():
        parts.append(cur.strip())
    elif parts:
        raise YAMLSubsetError(ln, "empty flow item")
    return parts


def _scalar(tok: str, ln: int):
    if tok == "":
        return None
    if tok[0] in "\"'":
        q = tok[0]
        if len(tok) < 2 or tok[-1] != q:
            raise YAMLSubsetError(ln, "unterminated quote")
        inner = tok[1:-1]
        if q == '"':
            try:
                return json.loads(tok)
            except json.JSONDecodeError:
                raise YAMLSubsetError(ln, "bad double-quoted string") from None
        return inner.replace("''", "'")
    if tok[0] in _BARE_REFUSED:
        what = {"&": "anchor", "*": "alias", "!": "tag", "|": "multi-line scalar",
                ">": "multi-line scalar"}.get(tok[0], "reserved indicator")
        raise YAMLSubsetError(ln, what)
    if tok.startswith("- ") or tok == "-":
        raise YAMLSubsetError(ln, "nested list")
    if tok in ("null", "~", "Null", "NULL"):
        return None
    if tok in ("true", "True", "TRUE"):
        return True
    if tok in ("false", "False", "FALSE"):
        return False
    if _INT.match(tok):
        return int(tok)
    if _FLOAT.match(tok):
        return float(tok)
    if ": " in tok or tok.endswith(":"):
        raise YAMLSubsetError(ln, "mapping inside a scalar")
    return tok


def _value(tok: str, ln: int):
    """An inline value: a flow list, a flow mapping, or a scalar."""
    if tok.startswith("["):
        if not tok.endswith("]"):
            raise YAMLSubsetError(ln, "unterminated flow list")
        return [_scalar(p, ln) for p in _split_flow(tok[1:-1], ln)]
    if tok.startswith("{"):
        if not tok.endswith("}"):
            raise YAMLSubsetError(ln, "unterminated flow mapping")
        out: dict = {}
        for p in _split_flow(tok[1:-1], ln):
            m = _KEY.match(p)
            if not m:
                raise YAMLSubsetError(ln, f"bad flow mapping item {p!r}")
            if m.group(1) in out:
                raise YAMLSubsetError(ln, f"duplicate key {m.group(1)!r}")
            out[m.group(1)] = _scalar((m.group(2) or "").strip(), ln)
        return out
    return _scalar(tok, ln)


def load(text: str) -> dict:
    """Parse the subset; the top level is always a mapping ({} when empty)."""
    lines: list[tuple[int, int, str]] = []          # (line no, indent, content)
    for ln, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))] or (
                "\t" in raw and not raw.strip().startswith("#")):
            raise YAMLSubsetError(ln, "tab")
        body = _strip_comment(raw)
        if not body.strip():
            continue
        if body.strip() in ("---", "...") or body.startswith("%"):
            raise YAMLSubsetError(ln, "document marker")
        lines.append((ln, len(body) - len(body.lstrip(" ")), body.strip()))

    pos = 0

    def block(indent: int):
        nonlocal pos
        first_ln, _, first = lines[pos]
        if first.startswith("- ") or first == "-":
            return seq(indent)
        return mapping(indent)

    def seq(indent: int) -> list:
        nonlocal pos
        out = []
        while pos < len(lines):
            ln, ind, body = lines[pos]
            if ind < indent:
                break
            if ind > indent:
                raise YAMLSubsetError(ln, "nested list or bad indentation")
            if not (body.startswith("- ") or body == "-"):
                break                   # the enclosing mapping judges this line
            item = body[2:].strip() if body != "-" else ""
            if item.startswith("- "):
                raise YAMLSubsetError(ln, "nested list")
            if item == "" or _KEY.match(item) or item.startswith("["):
                raise YAMLSubsetError(ln, "nested list" if item.startswith("[")
                                      else "list of block mappings")
            # a `{k: v}` item is one flat mapping, the shape of `inputs`
            out.append(_value(item, ln) if item.startswith("{") else _scalar(item, ln))
            pos += 1
        return out

    def mapping(indent: int) -> dict:
        nonlocal pos
        out: dict = {}
        while pos < len(lines):
            ln, ind, body = lines[pos]
            if ind < indent:
                break
            if ind > indent:
                raise YAMLSubsetError(ln, "bad indentation")
            if body.startswith("- "):
                raise YAMLSubsetError(ln, "list item inside a mapping")
            m = _KEY.match(body)
            if not m:
                if body.startswith(("? ", "&", "*", "!")):
                    raise YAMLSubsetError(ln, "complex key, anchor or tag")
                raise YAMLSubsetError(ln, f"not a `key: value` line: {body!r}")
            key, rest = m.group(1), (m.group(2) or "").strip()
            if key in out:
                raise YAMLSubsetError(ln, f"duplicate key {key!r}")
            pos += 1
            if rest:
                out[key] = _value(rest, ln)
                if pos < len(lines) and lines[pos][1] > indent:
                    raise YAMLSubsetError(lines[pos][0], "multi-line scalar")
            elif pos < len(lines) and lines[pos][1] > indent:
                out[key] = block(lines[pos][1])
            elif pos < len(lines) and lines[pos][1] == indent and \
                    lines[pos][2].startswith("- "):
                out[key] = seq(indent)       # `key:\n- a` at the same indent
            else:
                out[key] = None
        return out

    if not lines:
        return {}
    if lines[0][1] != 0:
        raise YAMLSubsetError(lines[0][0], "bad indentation")
    if lines[0][2].startswith("- "):
        raise YAMLSubsetError(lines[0][0], "top level must be a mapping")
    result = mapping(0)
    if pos < len(lines):
        raise YAMLSubsetError(lines[pos][0], "bad indentation")
    return result


# --- dump ---------------------------------------------------------------------

_PLAIN = re.compile(r"^[A-Za-z_./][A-Za-z0-9_./@+-]*$")
_RESERVED = {"null", "~", "true", "false", "yes", "no", "on", "off",
             "Null", "NULL", "True", "TRUE", "False", "FALSE"}


def _dump_scalar(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    s = str(v)
    if _PLAIN.match(s) and s not in _RESERVED:
        return s
    return json.dumps(s, ensure_ascii=False)


def dump(obj: dict) -> str:
    """Block-style, keys in the order given; lists of scalars only."""
    out: list[str] = []

    def emit(d: dict, indent: int) -> None:
        pad = " " * indent
        for k, v in d.items():
            if isinstance(v, dict):
                if not v:
                    out.append(f"{pad}{k}: {{}}")
                else:
                    out.append(f"{pad}{k}:")
                    emit(v, indent + 2)
            elif isinstance(v, (list, tuple)) and any(isinstance(x, dict) for x in v):
                out.append(f"{pad}{k}:")
                for x in v:
                    if not isinstance(x, dict) or any(
                            isinstance(y, (dict, list, tuple)) for y in x.values()):
                        raise ValueError(f"{k}: list items must be flat mappings")
                    out.append(f"{pad}  - {{" + ", ".join(
                        f"{a}: {_dump_scalar(b)}" for a, b in x.items()) + "}")
            elif isinstance(v, (list, tuple)):
                if any(isinstance(x, (list, tuple)) for x in v):
                    raise ValueError(f"{k}: only flat lists are in the subset")
                out.append(f"{pad}{k}: [" + ", ".join(_dump_scalar(x) for x in v) + "]")
            else:
                out.append(f"{pad}{k}: {_dump_scalar(v)}")

    emit(obj, 0)
    return "\n".join(out) + "\n"
