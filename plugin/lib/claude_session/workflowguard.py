"""The Workflow guard (packet wfg): bound a workflow script's agents before it starts.

`check(script, parent)` reads the script's JavaScript without running it and returns the
reasons to deny it, an empty list when it may start. It fails closed: a shape it cannot
bound is a reason, each with the rewrite that passes. It bounds an honest script; it is no
sandbox, and a script written to evade it is the review's matter, not this module's.

The pass is linear in the script's length: one token scan (each regex has one repetition
and none nests), one bracket walk, and one upward walk per `agent(` call.

What it requires:
  1. every `agent(` call's options are an object literal with `model: '<family>'`;
  2. a Fable agent only under a Fable session, labelled `design` or `refute`, FABLE_MAX at most;
  3. every `agent(` call sits at the top level, in an `if`, or in a callback given directly
     to `parallel(`, `pipeline(`, `.map(`, `.flatMap(` or `.then(`: never in a loop, a named
     function, or another call's callback; a thunk (`() => agent(`) is built inside the
     `parallel(` that runs it;
  4. a `.map(`, `.flatMap(` or `pipeline(` over a list multiplies by the list's length, which
     must be a literal: a `const` array never changed, an inline array, or `.slice(0, N)`;
  5. the sum is MAX_AGENTS at most.
"""

from __future__ import annotations

import bisect
import re

MAX_AGENTS = 8            # eight helpers a sitting; the packet's fork Q1
FABLE_MAX = 2
MAX_SCRIPT = 256 * 1024
MAX_REASONS = 3
MAX_SITES = 64            # agent( calls read; more is denied, so the pass stays bounded
FAMILIES = ("opus", "sonnet", "haiku", "fable")
FABLE_LABELS = ("design", "refut")
COMBINATORS = ("parallel", "pipeline", ".map", ".flatMap", ".then")
LOOPS = ("for", "while", "do")
_BANNED = re.compile(r"(?<![\w$.])(?:(workflow|eval|Function|import|require)\s*\(|(globalThis)(?![\w$]))")

_TOK = re.compile(r"//[^\n]*|/\*|'|\"|`|[(){}\[\]]|/")
_SQ = re.compile(r"(?:[^'\\\n]|\\.)*'", re.S)
_DQ = re.compile(r'(?:[^"\\\n]|\\.)*"', re.S)
_RX = re.compile(r"(?:[^/\\\n\[]|\\.|\[(?:[^\]\\\n]|\\.)*\])+/[A-Za-z]*")
_TPL = re.compile(r"`|\$\{|\\")
_RX_BEFORE = "(,=:[!&|?{};+-*%<>~^"
_RX_WORDS = ("return", "typeof", "await", "case", "void", "in", "of", "yield")
_WORD_END = re.compile(r"[\w$]+\Z")
_AGENT = re.compile(r"(?<![\w$.])agent(?![\w$])")
_RAW_AGENT = re.compile(r"(?<![\w$.])agent\s*\(")
_SLICE = re.compile(r"\.slice\(\s*0\s*,\s*(\d{1,4})\s*\)\s*\Z")
_IDENT = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\Z")
_MODEL = re.compile(r"model\s*:\s*(['\"])([A-Za-z0-9_.\[\]-]{1,64})\1\s*[,}]")
_LABEL = re.compile(r"label\s*:\s*['\"`]\s*([A-Za-z]+)")
_KEY = re.compile(r"([A-Za-z_$][\w$]*)\s*:")
_CONT_END = "=>,(?:&|+-*/.<![{"
_CONT_WORDS = ("await", "return", "typeof", "new", "void", "yield", "in", "of", "else", "do",
               "case", "throw", "delete")
_HEADER = re.compile(r"\s*(?:\}\s*)?(?:else\s+)?(?:for|while|if)(?:\s+await)?\s*\(\)\s*\Z")
_READS = ("map", "flatMap", "slice", "filter", "join", "includes", "find", "some", "every",
          "indexOf", "length", "entries", "keys")


def _prev(sk: str, pos: int) -> int:
    """The index of the last non-space character before `pos`, -1 for none."""
    i = pos - 1
    while i >= 0 and sk[i].isspace():
        i -= 1
    return i


class Unbounded(Exception):
    """A shape the guard cannot bound; its text is the reason."""


def family(model) -> str | None:
    low = model.lower() if isinstance(model, str) else ""
    for f in FAMILIES:
        if f in low:
            return f
    return None


def skeleton(src: str) -> str:
    """The script with every string's and template's text, each regex and each comment
    blanked to spaces, offset for offset; quotes and backticks stay, and a template's `${`
    reads ` {`. Raises Unbounded on an open literal."""
    out, i, n = [], 0, len(src)
    stack = []                        # a template's open `${`: the brace depth it closes at
    depth = 0
    tail = ""                         # the last code seen, to tell a regex from a division

    def code(text):
        nonlocal tail
        out.append(text)
        if text.strip():
            tail = (tail + text).rstrip()[-16:]

    def blank(a, b):
        out.append(" " * (b - a))

    def template(j):
        """From inside a template's text at j: blank to its close or its next `${`."""
        nonlocal depth
        k = j
        while True:
            m = _TPL.search(src, k)
            if m is None:
                raise Unbounded("a template literal never closes")
            if m.group() == "\\":
                k = m.end() + 1
                continue
            blank(j, m.start())
            if m.group() == "`":
                out.append("`")
                return m.end()
            out.append(" {")
            stack.append(depth)
            depth += 1
            return m.end()

    while i < n:
        m = _TOK.search(src, i)
        if m is None:
            code(src[i:])
            break
        code(src[i:m.start()])
        t, j = m.group(), m.end()
        if t.startswith("//"):
            blank(m.start(), j)
        elif t == "/*":
            e = src.find("*/", j)
            if e < 0:
                raise Unbounded("a comment never closes")
            j = e + 2
            blank(m.start(), j)
        elif t in "'\"":
            q = (_SQ if t == "'" else _DQ).match(src, j)
            if q is None:
                raise Unbounded("a string never closes")
            j = q.end()
            out.append(t + " " * (j - m.start() - 2) + t)     # the quotes stay: a value, no hole
            tail = '"'
        elif t == "`":
            out.append("`")
            j = template(j)
            tail = "{" if src[j - 1] == "{" else '"'
        elif t == "/":
            w = _WORD_END.search(tail)
            if (not tail or tail[-1] in _RX_BEFORE or (w and w.group() in _RX_WORDS)):
                q = _RX.match(src, j)
                if q is None:
                    raise Unbounded("a regex literal the guard cannot read")
                j = q.end()
                blank(m.start(), j)
                tail = '"'
            else:
                code("/")
        elif t == "{":
            depth += 1
            code("{")
        elif t == "}":
            depth -= 1
            code("}")
            if stack and stack[-1] == depth:
                stack.pop()
                j = template(j)
                tail = "{" if src[j - 1] == "{" else '"'
        else:
            code(t)
        i = j
    if stack:
        raise Unbounded("a template literal never closes")
    return "".join(out)


class _Tree:
    """The skeleton's brackets: for each open, its close and its parent open (-1: none)."""

    def __init__(self, sk: str):
        self.sk = sk
        self.close, self.parent, self.kids, self.open_of = {}, {}, {-1: []}, {}
        stack = []
        pair = {")": "(", "]": "[", "}": "{"}
        for m in re.finditer(r"[(){}\[\]]", sk):
            c, p = m.group(), m.start()
            if c in "([{":
                up = stack[-1] if stack else -1
                self.parent[p] = up
                self.kids[p] = []
                self.kids[up].append(p)
                stack.append(p)
            else:
                if not stack or sk[stack[-1]] != pair[c]:
                    raise Unbounded("the script's brackets do not pair")
                self.open_of[p] = stack[-1]
                self.close[stack.pop()] = p
        if stack:
            raise Unbounded("the script's brackets do not pair")
        self.opens = sorted(self.parent)

    def holder(self, pos: int) -> int:
        """The innermost bracket that holds `pos` (-1: the top level)."""
        i = bisect.bisect_right(self.opens, pos) - 1
        o = self.opens[i] if i >= 0 else -1
        while o != -1 and self.close[o] < pos:
            o = self.parent[o]
        return o

    def flat(self, level: int, a: int, b: int) -> str:
        """sk[a:b] at `level`, each nested bracket group collapsed to its two brackets."""
        parts, i = [], a
        ks = self.kids[level]
        for k in ks[bisect.bisect_left(ks, a):]:
            if k >= b:
                break
            parts.append(self.sk[i:k + 1])
            i = min(self.close[k], b)
        parts.append(self.sk[i:b])
        return "".join(parts)

    def callee(self, o: int) -> str:
        """The word before an open paren, `.word` for a method; '' for none."""
        e = _prev(self.sk, o) + 1
        w = _WORD_END.search(self.sk, max(0, e - 80), e)
        if w is None:
            return ""
        d = _prev(self.sk, w.start())
        return ("." if d >= 0 and self.sk[d] == "." else "") + w.group()

    def kind(self, o: int) -> str:
        sk = self.sk
        if sk[o] == "[":
            return "array"
        if sk[o] == "(":
            c = self.callee(o)
            if sk[self.close[o] + 1:self.close[o] + 12].lstrip().startswith("=>"):
                return "params"
            if c in COMBINATORS:
                return "comb"
            if c in ("for", "while"):
                return "loophead"
            if c in ("if", "switch", "catch", "await", "return", "typeof", "void", ""):
                return "group"
            return "call"
        e = _prev(sk, o)
        head = sk[max(0, e - 11):e + 1]
        if head.endswith("=>"):
            return "arrowbody"
        if head.endswith(")"):
            c = self.callee(self.open_of[e])
            if c in ("for", "while"):
                return "loopbody"
            if c in ("if", "switch", "catch"):
                return "block"
            return "funcbody"
        w = _WORD_END.search(head)
        if w and w.group() == "do":
            return "loopbody"
        return "block"


def _statement(flat: str) -> str:
    """The last statement of a block's flat text: cut at the last `;`, else at the last
    newline that ends a statement. A newline does not end one when the line before ends in
    an operator, a keyword that wants more, or a loop's or an `if`'s header, or when the
    line after starts with anything but a name or `}`."""
    flat = flat[flat.rfind(";") + 1:]
    lines = flat.split("\n")
    i = len(lines) - 1
    while i > 0:
        j = i - 1
        while j > 0 and not lines[j].strip():
            j -= 1
        prev, nxt = lines[j].rstrip(), lines[i].lstrip()
        w = _WORD_END.search(prev)
        cont = (not prev.strip() or prev[-1] in _CONT_END or (w and w.group() in _CONT_WORDS)
                or _HEADER.match(prev) is not None
                or (nxt != "" and not (nxt[0].isalnum() or nxt[0] in "_$}")))
        if not cont and nxt:
            break
        i = j
    return "\n".join(lines[i:])


def _word(text: str, words) -> str | None:
    for w in words:
        if re.search(r"(?<![\w$.])" + w + r"(?![\w$])", text):
            return w
    return None


class _Script:
    def __init__(self, src: str):
        self.src = src
        self.sk = skeleton(src)
        self.t = _Tree(self.sk)
        self._len = {}

    def line(self, pos: int) -> int:
        return self.src.count("\n", 0, pos) + 1

    def elements(self, o: int) -> int:
        """An array literal's element count; a spread makes it unknown."""
        parts = self.t.flat(o, o + 1, self.t.close[o]).split(",")
        if parts and not parts[-1].strip():
            parts.pop()
        if any(p.strip().startswith("...") or not p.strip() for p in parts):
            raise Unbounded("an array with a spread or a hole has no fixed length")
        return len(parts)

    def const_len(self, name: str) -> int:
        """The length of `const NAME = [ ... ]`, declared once at the top level and only
        ever read; anything else is Unbounded."""
        if name in self._len:
            return self._len[name]
        sk, esc = self.sk, re.escape(name)
        fix = f"`{name}` is not a fixed list: declare it once as a top-level `const {name} = [...]` literal and only read it, or cut it with `.slice(0, N)`"
        decl = list(re.finditer(r"(?<![\w$.])const\s+" + esc + r"\s*=\s*\[", sk))
        if len(decl) != 1 or self.t.parent[decl[0].end() - 1] != -1:
            raise Unbounded(fix)
        o = decl[0].end() - 1
        if not re.match(r"[ \t]*(?:;|\n\s*[\w$]|\s*\Z)", sk[self.t.close[o] + 1:]):
            raise Unbounded(fix)
        for m in re.finditer(r"(?<![\w$])" + esc + r"(?![\w$])", sk):
            if decl[0].start() <= m.start() < decl[0].end():
                continue
            e = _prev(sk, m.start())
            before, after = sk[max(0, e - 3):e + 1], sk[m.end():m.end() + 24].lstrip()
            if before.endswith(".") and not before.endswith("..."):
                continue                                  # another object's property
            if after.startswith(":") and before[-1:] in "{,":
                continue                                  # an object's key
            ok = False
            if after.startswith("."):
                w = re.match(r"\.\s*([A-Za-z]+)", after)
                ok = bool(w) and w.group(1) in _READS and not re.match(
                    r"\.\s*length\s*=(?!=)", after)
            elif after.startswith("["):
                c = self.t.close[m.end() + sk[m.end():].index("[")]
                ok = not re.match(r"\s*(?:=(?!=)|\+=|\+\+|--)", sk[c + 1:c + 6])
            elif after.startswith(","):
                h = self.t.holder(m.start())
                ok = (h != -1 and self.t.callee(h) == "pipeline"
                      and not sk[h + 1:m.start()].strip())
            h = self.t.holder(m.start())
            if not ok or before.endswith("...") or (h != -1 and self.t.kind(h) == "params"):
                raise Unbounded(fix)
        self._len[name] = self.elements(o)
        return self._len[name]

    def length(self, end: int) -> int:
        """The length of the list expression that ends at `end` (exclusive)."""
        head = self.sk[max(0, end - 80):end]
        m = _SLICE.search(head)
        if m:
            return int(m.group(1))
        e = _prev(self.sk, end)
        if e >= 0 and self.sk[e] == "]":
            o = self.t.open_of[e]
            b = _prev(self.sk, o)
            if b < 0 or not (self.sk[b].isalnum() or self.sk[b] in "_$)]"):
                return self.elements(o)
        m = _IDENT.search(head)
        if m:
            return self.const_len(m.group(1))
        raise Unbounded("a list known only at run time fans out agents: cut it to a literal, "
                        "`<list>.slice(0, N).map(` (or `pipeline(<list>.slice(0, N), ...`)")

    def multiplier(self, o: int) -> int:
        c = self.t.callee(o)
        if c in (".map", ".flatMap"):
            dot = self.sk.rindex(".", 0, o)
            return self.length(dot)
        if c == "pipeline":
            first = self.t.flat(o, o + 1, self.t.close[o]).split(",")[0]
            return self.length(o + 1 + len(first))
        return 1

    def count(self, site: int) -> int:
        """How many agents the `agent(` at `site` can start; Unbounded when it has no bound."""
        t, mult, pos, pending = self.t, 1, site, False
        level = t.holder(site)
        while True:
            lo = level + 1 if level != -1 else 0
            k = t.kind(level) if level != -1 else "top"
            if k in ("block", "arrowbody", "funcbody", "loopbody", "top"):
                local = _statement(t.flat(level, lo, pos) + "X")[:-1]
            else:
                local = t.flat(level, lo, pos)
                local = local[local.rfind(",") + 1:]
            arrow = "=>" in local
            if _word(local, ("function",)) or k == "funcbody":
                raise Unbounded("an agent( inside a named function cannot be counted: "
                                "write the call inline where it runs")
            if k in ("loopbody", "loophead") or (k in ("block", "arrowbody", "top")
                                                 and _word(local, LOOPS)):
                raise Unbounded("an agent( inside a loop has no bound before launch: "
                                "unroll it, or map a literal list")
            c = t.callee(level) if k == "comb" else ""
            if pending and c == "parallel":
                pending = False                 # the thunks' one consumer runs each once
            elif pending and not (k == "array" or c in (".map", ".flatMap")):
                raise Unbounded("agent thunks (`() => agent(`) must be built inside the "
                                "`parallel(` that runs them, never kept in a name")
            if arrow:
                if k == "array" or (k == "comb" and local.count("=>") > 1):
                    pending = True              # a thunk: something must run it, once
                elif k != "comb":
                    raise Unbounded(
                        "an agent( inside a helper function or another call's callback cannot "
                        "be counted: give the callback directly to parallel(, pipeline(, "
                        ".map( or .then(")
            if k == "comb":
                mult *= self.multiplier(level)
            if level == -1:
                return mult
            pos, level = level, t.parent[level]

    def options(self, site: int):
        """(model family, label word) of the call's options object literal."""
        t = self.t
        o = self.sk.index("(", site)
        args = [k for k in t.kids[o]]
        flat = t.flat(o, o + 1, t.close[o])
        last = flat.rsplit(",", 1)[-1].strip() if "," in flat else ""
        if not args or last != "{}" or self.sk[args[-1]] != "{":
            raise Unbounded("every agent( names its model in an options literal: "
                            "agent(prompt, { label: '...', model: 'opus' })")
        b = args[-1]
        fam = label = None
        inner = t.flat(b, b + 1, t.close[b])
        if "..." in inner:
            raise Unbounded("an agent's options must be a plain literal, no spread: "
                            "write model: 'opus' in each call")
        for km in _KEY.finditer(self.sk, b + 1, t.close[b]):
            if t.holder(km.start()) != b or self.sk[_prev(self.sk, km.start())] not in "{,":
                continue
            if km.group(1) == "model":
                mm = _MODEL.match(self.src, km.start())
                fam = family(mm.group(2)) if mm else None
                if fam is None:
                    raise Unbounded("an agent's model must be a literal family name: "
                                    "model: 'opus' (or sonnet, haiku)")
            elif km.group(1) == "label":
                lm = _LABEL.match(self.src, km.start())
                label = lm.group(1).lower() if lm else ""
        if fam is None:
            raise Unbounded("every agent( names its model in its own options: "
                            "add model: 'opus' (an unnamed agent runs on the session's model)")
        return fam, label


def check(script, parent: str | None = None) -> list[str]:
    """The reasons to deny `script`, MAX_REASONS at most; [] when it may start. `parent` is
    the session's model family, None when unknown."""
    return measure(script, parent)[1]


def measure(script, parent: str | None = None) -> tuple[int, list[str]]:
    """(the most agents the counted calls can start, the reasons to deny)."""
    if not isinstance(script, str) or not script.strip():
        return 0, ["the script is empty or not text: pass `script` inline"]
    if len(script) > MAX_SCRIPT:
        return 0, [f"the script is over {MAX_SCRIPT // 1024} KB: put the long text in files "
                   "the agents read"]
    try:
        s = _Script(script)
    except Unbounded as e:
        return 0, [f"the guard cannot read the script ({e}): simplify the quoting"]
    found, total, fables = {}, 0, 0      # a reason's text: the lines it holds on

    def add(text, pos=None):
        lines = found.setdefault(text, [])
        if pos is not None and s.line(pos) not in lines:
            lines.append(s.line(pos))

    w = _BANNED.search(s.sk)
    if w:
        add(f"`{w.group(1) or w.group(2)}` hides agents from the count: inline the child's "
            "calls in this script", w.start())
    sites = []
    for m in _AGENT.finditer(s.sk):
        after = s.sk[m.end():m.end() + 8].lstrip()
        e = _prev(s.sk, m.start())
        before = s.sk[e] if e >= 0 else ""
        if after.startswith("("):
            sites.append(m.start())
        elif not (after.startswith(":") and before[-1:] in "{,"):
            add("`agent` is used other than as a direct call: write agent(prompt, {...}) "
                "where it runs", m.start())
    if len(_RAW_AGENT.findall(script)) != len(sites):
        add("the text `agent(` appears inside a string, template or comment, so the count "
            "is not sure: reword that text")
    if len(sites) > MAX_SITES:
        add(f"the script holds {len(sites)} agent( calls and the guard reads {MAX_SITES}")
        sites = []
    for site in sites:
        fam = label = None
        n = 0
        try:
            fam, label = s.options(site)
        except Unbounded as e:
            add(str(e), site)
        try:
            n = s.count(site)
        except Unbounded as e:
            add(str(e), site)
        total += n
        if fam == "fable":
            fables += n
            if parent != "fable":
                add("a Fable agent starts only under a Fable session"
                    + (": the session's model is not known" if parent is None else
                       f" (this one runs {parent})") + ": name model: 'opus'", site)
            elif not (label or "").startswith(FABLE_LABELS):
                add("a Fable agent needs a label that starts with design or refute; "
                    "any other work names model: 'opus'", site)
    if fables > FABLE_MAX:
        add(f"the script can start {fables} Fable agents and the ceiling is {FABLE_MAX}")
    if total > MAX_AGENTS:
        add(f"the script can start {total} agents and the ceiling is {MAX_AGENTS}: "
            "cut the lists, or split the work across turns")
    reasons = [(f"line{'s' if len(ls) > 1 else ''} {', '.join(map(str, ls[:6]))}: " if ls else "")
               + text for text, ls in found.items()]
    return total, reasons[:MAX_REASONS]


def deny_line(reasons: list[str]) -> str:
    return ("agentik-session: Workflow denied before launch: " + "; ".join(reasons)
            + ". Fix the script and call Workflow again.")
