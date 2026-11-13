"""Packet g7-one-reader: the strict and the loose reading of a shell line, and a quoted `$(`'s
text, live in one module, `shellreader.py`, and no answer changed.

1 the module imports alone; 2 each of its 54 names lives once, the guard and the loop holding
the module's own objects; 3 one splitter; 4 the lines where the readers differ, pinned as the
pin reads them, so that the next row changes each knowingly; 5 the repo's own packets' lines.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from claude_session import instructionguard, shellreader, unattended

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "plugin" / "lib" / "claude_session"

MOVED = ("_home _tilde _HEREDOC _PH _PH_RE _PUNCT _OPS _MASK _UNMASK _CASE_NEXT _KEY _LEAD "
         "_WRITE_OPS _READ_OPS _ASSIGN _WRAPPERS _SHELLS _CDS _PY _SED_I _PERL_I _LITERAL _TAKES "
         "_heredocs _mask _commands _resolve _py_literals _copy_args _copy_like _git_paths "
         "bash_targets _Bound _Paid _parse _strict _CAP_STATES _STRICT_BOUND _STRICT_READS _move "
         "_states _judge _others _LOOSE_SEP _LOOSE_W _LOOSE_REDIR _LOOSE_COMMENT _LOOSE_SKIP "
         "_LOOSE_HARD _LOOSE_COND _clean _loose loose_targets _substituted").split()
GUARD = {"_Bound", "_home", "_loose", "_resolve", "_strict", "_tilde"}
LOOP = {"_SHELLS", "_commands", "_substituted"}


# ---- 1, 2, 3: the module alone, each name once, one splitter ----------------------------

def test_1_the_module_imports_alone(tmp_path):
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import claude_session.shellreader; "
            "print(sorted(m for m in sys.modules if m.startswith('claude_session')))")
    out = subprocess.run([sys.executable, "-I", "-c", code, str(PKG.parent)], cwd=str(tmp_path),
                         env=dict(os.environ, HOME=str(tmp_path)), capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "['claude_session', 'claude_session.shellreader']"


def test_2_each_name_lives_once():
    assert len(MOVED) == len(set(MOVED)) == 54
    mine = vars(shellreader)
    assert set(MOVED) <= set(mine)
    for n in MOVED:
        if hasattr(mine[n], "__module__") and callable(mine[n]):
            assert mine[n].__module__ == "claude_session.shellreader", n
    guard = {n for n in MOVED if n in vars(instructionguard)}
    assert guard == GUARD
    assert all(vars(instructionguard)[n] is mine[n] for n in guard)
    loop = {n for n in MOVED if n in vars(unattended)}
    assert loop == LOOP | {"_parse"}
    assert all(vars(unattended)[n] is mine[n] for n in LOOP)
    assert unattended._parse is not shellreader._parse
    assert unattended._parse.__module__ == "claude_session.unattended"


def test_3_one_splitter():
    holders = sorted(p.relative_to(PKG).as_posix() for p in PKG.rglob("*.py")
                     if "shlex.shlex" in p.read_text(encoding="utf-8"))
    assert holders == ["shellreader.py"]


# ---- 4: the lines where the readers differ, as the pin reads them -----------------------

M = "make x > CLAUDE.md"
RUNS = "it runs `make`"
SPLIT = "the hook's reader cannot split it"
GATED = ["CLAUDE.md"]
NONE: list = []

# (shape, strict, make): strict is the paths `bash_targets` finds less the folder, a list, or
# the exception it raises; make the start of `unbounded`'s answer, "" when it passes
TABLE = [
    ("{M}", GATED, RUNS),
    ("bash -c '{M}'", GATED, RUNS),
    ("bash -o pipefail -c '{M}'", GATED, RUNS),
    ("/bin/bash -c '{M}'", GATED, RUNS),
    ("echo $({M})", GATED, RUNS),
    ("x=1 env {M}", GATED, RUNS),
    ("sudo {M}", GATED, RUNS),
    ("if true; then {M}; fi", GATED, RUNS),
    ("( {M} )", GATED, RUNS),
    ("{{ {M}; }}", GATED, RUNS),
    ("time -p {M}", GATED, RUNS),
    ("echo make > CLAUDE.md", GATED, RUNS),
    ("git log -- make > CLAUDE.md", GATED, RUNS),
    ("bash -lc '{M}'", GATED, RUNS),
    ("bash -c -e '{M}'", GATED, RUNS),
    ("BASH -c '{M}'", GATED, RUNS),
    ("bash -c \"bash -c '{M}'\"", NONE, RUNS),
    ("echo \"$({M})\"", GATED, RUNS),
    ("sh <<EOF\n{M}\nEOF", GATED, RUNS),
    ("cat <<EOF\n{M}\nEOF", NONE, RUNS),
    ("echo `{M}`", GATED, ""),
    ("./make.sh > CLAUDE.md", GATED, ""),
    ("ksh -c '{M}'", GATED, ""),
    ("eval '{M}'", NONE, ""),
    ("echo '{M}' | sh", NONE, ""),
    ("echo '{M}'", NONE, ""),
    ("git commit -m \"{M}\"", NONE, ""),
    ("echo ok # {M}", NONE, ""),
    ("x=\"$(case a in a) {M};; esac)\"; echo \"$x\"", GATED, ""),
    ("x=\"$(echo ${{y:-a)}} ; {M})\"; echo \"$x\"", GATED, ""),
    ("n=\"$(grep -c ')' f.txt)\"; echo \"$n\" > CLAUDE.md", GATED, SPLIT),
    ("echo \"it's\" 'x > CLAUDE.md", ValueError("No closing quotation"), SPLIT),
]


def _strict(line):
    found = shellreader.bash_targets(line, "/g7/repo", {"HOME": "/g7/home"})
    return sorted({p[len("/g7/repo/"):] for _, p in found if p})


@pytest.mark.parametrize("shape,strict,make", TABLE, ids=[str(i) for i in range(len(TABLE))])
def test_4_where_the_readers_differ(shape, strict, make):
    line = shape.format(M=M)
    if isinstance(strict, Exception):
        with pytest.raises(type(strict)) as e:
            _strict(line)
        assert str(e.value) == str(strict)
    else:
        assert _strict(line) == strict
    assert sorted({w for _, w in shellreader.loose_targets(line)}) == GATED
    why = unattended.unbounded(line)
    assert why.startswith(make) and bool(why) == bool(make), why


def test_4_the_table_is_32_lines():
    assert len(TABLE) == len({s for s, _, _ in TABLE}) == 32


# ---- 5: the repo's own packets ----------------------------------------------------------

def test_5_the_packets_lines_both_sides():
    lines = []
    for p in sorted((ROOT / "design" / "packets").glob("*.md")):
        try:
            lines += [it.shell for it in unattended.acceptance(p.read_text(encoding="utf-8"))]
        except unattended.AcceptanceError:
            continue
    refused = [ln for ln in lines if unattended.unbounded(ln)]
    assert all("make" in ln.split() for ln in refused), refused
    assert refused and len(lines) - len(refused) >= 100, (len(lines), len(refused))
