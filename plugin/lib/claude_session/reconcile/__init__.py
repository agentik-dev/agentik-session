"""The reconciler's library: three detectors with no model, over facts the tool already holds.

`detect(tree, window, now, roots)` returns one finding per detector, sorted by id, each
`{id, kind, repo, value, threshold, flagged, evidence: {command, numbers, files}}`. The
library reads charters, git and transcripts and writes nothing. It is pure over what it is
given: `roots` names the folders (`hq`, `repos`, `projects`), `now` is the clock and
`readers` the git and transcript readers, so a test injects all of them and nothing reads
the live home. A finding carries numbers, the files it read and a shell command that
reproduces its value, never a transcript's or a charter's text. A detector that cannot read
gives `value` None, unflagged, and never raises.

The detectors: `live.goal_unchanged` and `live.since_landing` (live.py), `eff.idle`
(idle.py). Imports: the standard library and `..gitinfo`, `..rules`, `..charter` alone.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Optional

from .. import gitinfo, rules

# The first value that flags, per detector id; `detect(thresholds=...)` overrides each.
THRESHOLDS = {"eff.idle": 5.0, "live.since_landing": 5, "live.goal_unchanged": 10}


def weights() -> dict:
    """Weighted tokens per token, input = 1: `rules.mix`'s opus prices over their input
    price (output 5, cache_write 1.25, cache_read 0.1: the same ratios for every family)."""
    p = rules.mix({"shares": {"opus": 1}})["prices"]["opus"]
    return {k: v / p["input"] for k, v in p.items()}


def slug(path) -> str:
    """The transcripts' folder name for a cwd: every character outside [A-Za-z0-9] a `-`."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(str(path)))


def sh(word) -> str:
    """One word for `/bin/sh`, single-quoted."""
    return "'" + str(word).replace("'", "'\\''") + "'"


def _git(cwd, *args) -> Optional[str]:
    """git's stdout in `cwd`, None when git fails or is missing (gitinfo's timeout holds)."""
    rc, out = gitinfo._git(str(cwd), *args)
    return out if rc == 0 else None


@dataclass
class Readers:
    """What the detectors read through: `git(cwd, *args) -> stdout | None` and
    `transcripts(project_dir, since) -> [(path, [obj])]` (default `idle.read_transcripts`)."""
    git: Callable[..., Optional[str]] = _git
    transcripts: Optional[Callable] = None

    def __post_init__(self):
        if self.transcripts is None:     # bound late: `-m ...reconcile.idle` imports idle once
            from . import idle
            self.transcripts = idle.read_transcripts


def finding(fid, repo, value, threshold, command, numbers, files) -> dict:
    return {"id": fid, "kind": fid.split(".", 1)[0], "repo": repo, "value": value,
            "threshold": threshold,
            "flagged": value is not None and threshold is not None and value >= threshold,
            "evidence": {"command": command, "numbers": dict(numbers),
                         "files": [str(f) for f in files]}}


def _registry() -> dict:
    from . import idle, live
    return {"eff.idle": idle.detect, "live.goal_unchanged": live.goal_unchanged,
            "live.since_landing": live.since_landing}


def detect(tree, window, now, roots, *, goal=None, thresholds=None, detectors=None,
           readers=None) -> list:
    """Each named detector's finding (all three by default), sorted by id.

    `tree` is suite.json's shape (`{"repos": [{"name": ...}]}`), `window` days, `now` epoch
    seconds, `roots` `{"hq", "repos", "projects"}` paths; `goal` the repo names whose landing
    counts (default: every tree repo but the hq). An unknown detector id is a ValueError."""
    reg = _registry()
    ids = sorted(set(detectors if detectors is not None else reg))
    unknown = [d for d in ids if d not in reg]
    if unknown:
        raise ValueError("unknown detector: %s" % ", ".join(map(str, unknown)))
    hq = os.path.basename(os.path.abspath(str(roots["hq"])))
    if goal is None:
        repos = (tree or {}).get("repos") if isinstance(tree, dict) else None
        goal = [r.get("name") for r in repos or () if isinstance(r, dict)]
        goal = [n for n in goal if n != hq]
    goal = [n for n in goal if isinstance(n, str) and n]
    th = {**THRESHOLDS, **(thresholds or {})}
    ctx = {"hq": hq, "roots": roots, "window": window, "now": now, "goal": goal,
           "readers": readers if readers is not None else Readers()}
    out = []
    for fid in ids:
        try:
            out.append(reg[fid](dict(ctx, threshold=th.get(fid))))
        except Exception:                # the last guard: a detector never raises
            out.append(finding(fid, hq, None, th.get(fid), "false", {}, []))
    return out
