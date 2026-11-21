"""Where a repo's working records are (packet rr5a R2; hq design/28 §3, commons GUIDE §12).

`answer(folder)` gives commons' `agentik.records/1` object for `folder`, read by the synced
`agentik_records.resolve` in a child of its own session, killed with its group at gitinfo's
bound, once a folder a process. None where `folder` stands in no git checkout (or no git is
there): the pin's behaviour. Past the bound, or on any fault, the state is FAILED with `why`
`timeout` or the fault's one line, which every caller reads as `broken` (`state`). Never raises.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys

from . import gitinfo

KEY = "agentik.records"
BOUND = gitinfo._TIMEOUT                  # session's git bound, 5 s
FAILED = "failed"
SET_LINE = f"git config {KEY} <folder>"
_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHILD = ("import json, sys\n"
          "sys.path.insert(0, sys.argv[1])\n"
          "import agentik_records as r\n"
          "try:\n"
          "    a = r.resolve(sys.argv[2])\n"
          "except r.NoRepo:\n"
          "    a = None\n"
          "v = r.values(sys.argv[2]) if a and a['state'] == 'broken' else []\n"
          "print(json.dumps({'answer': a, 'values': v}))\n")
_ANSWERS: dict = {}
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def reset() -> None:
    """Forget every answer (tests)."""
    _ANSWERS.clear()


def _one_line(text) -> str:
    lines = [l.strip() for l in str(text).splitlines() if l.strip()]
    return _CONTROL.sub("?", lines[-1] if lines else str(text))[:200] or "fault"


def _failed(folder: str, why: str) -> dict:
    return {"schema": "agentik.records/1", "repo": folder, "records": None, "holder": None,
            "prefix": None, "state": FAILED, "why": why, "values": []}


def _read(folder: str):
    argv = [sys.executable or "/usr/bin/python3", "-I", "-S", "-c", _CHILD, _LIB, folder]
    try:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 errors="replace", start_new_session=True)
    except OSError as e:
        return _failed(folder, _one_line(e))
    try:
        out, err = child.communicate(timeout=BOUND)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except OSError:
            pass
        child.communicate()
        return _failed(folder, "timeout")
    if child.returncode != 0:
        return _failed(folder, _one_line(err) if err.strip() else f"exit {child.returncode}")
    try:
        got = json.loads(out)
        a = got["answer"]
        if a is None:
            return None
        if a.get("state") not in ("own", "out", "unset", "broken"):
            return _failed(folder, f"state {a.get('state')!r}")
        a = dict(a)
        a["values"] = [str(v) for v in got.get("values") or []]
        return a
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return _failed(folder, _one_line(e))


def answer(folder) -> dict | None:
    """The object for `folder`, or None where it is in no git checkout; one read a folder."""
    if not isinstance(folder, (str, os.PathLike)) or not str(folder):
        return None
    try:
        key = os.path.realpath(folder)
        if not os.path.isdir(key):
            return None
        if key not in _ANSWERS:
            _ANSWERS[key] = _read(key)
        return _ANSWERS[key]
    except Exception as e:                              # noqa: BLE001 - never raises
        return _failed(str(folder), _one_line(e))


def state(a: dict | None) -> str:
    """`own` (also for None, the pin), `out`, `unset` or `broken` (FAILED reads as broken)."""
    if a is None:
        return "own"
    s = a.get("state")
    return "broken" if s == FAILED else s if s in ("own", "out", "unset", "broken") else "broken"


def folder(a: dict | None, d: str) -> str | None:
    """The charter folder `d` under `out`'s records (an absolute `d` stands); None elsewhere."""
    if state(a) != "out" or not a.get("records"):
        return None
    return os.path.join(a["records"], d)


def _shown(v) -> str:
    return _CONTROL.sub(lambda m: "\\u%04x" % ord(m.group()), str(v))


def line(a: dict | None) -> str:
    """The one line of `unset` and `broken`: the key to set, and for `broken` its value and the
    reason; "" in `own` and `out`."""
    s = state(a)
    if s == "unset":
        return (f"this repo keeps its records outside its clone and {KEY} is not set; "
                f"set it: {SET_LINE}")
    if s == "broken":
        vals = ", ".join(_shown(v) for v in a.get("values") or []) or "(unread)"
        return (f"{KEY} does not resolve (value {vals}; reason {_shown(a.get('why'))}); "
                f"set it: {SET_LINE}")
    return ""
