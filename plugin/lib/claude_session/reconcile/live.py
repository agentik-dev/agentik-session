"""The liveness detectors over an hq's charters and its tree's git: `live.goal_unchanged` (the
newest charters keep one goal) and `live.since_landing` (charters opened since the goal's
newest landing).

A charter is `history/sittings/<date>-<n>[-<row>].md`; they are ordered by `(date, n)`, so
`-10` comes after `-9`, never by name."""

from __future__ import annotations

import collections
import os
import re

from .. import charter
from . import finding, sh

NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)(-[A-Za-z0-9._-]+)?\.md$")
NAME_ERE = "[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+(-[A-Za-z0-9._-]+)?[.]md$"
GOAL_LINE = re.compile(r"^\| *goal *\|")
NEWEST = 20


def charters(hq) -> list:
    """The hq's charter paths, oldest first by (date, n, name); OSError when the folder is
    unreadable."""
    d = os.path.join(str(hq), charter.DEFAULT_DIR)
    found = []
    for name in os.listdir(d):
        m = NAME.match(name)
        if m and os.path.isfile(os.path.join(d, name)):
            found.append(((m.group(1), int(m.group(2)), name), os.path.join(d, name)))
    return [p for _, p in sorted(found)]


def goal_row(path):
    """The first goal row's cell, read by `charter._table` as the command's `grep -m1` reads
    it; None when the charter has none."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if GOAL_LINE.match(line):
                return charter._table([line.rstrip("\n")]).get("goal")
    return None


def normal(goal: str) -> str:
    """The goal cut at its first comma, digits dropped, blanks folded."""
    return " ".join(re.sub(r"[0-9]", "", goal.split(",", 1)[0]).split())


def goal_unchanged(ctx) -> dict:
    hq = str(ctx["roots"]["hq"])
    cmd = ("cd %s && ls | grep -E '^%s' | sort -t- -k1,3 -k4,4n | tail -%d"
           " | xargs grep -h -m1 '^| *goal *|' | sed -E 's/^[|] *goal *[|] *//; s/ *[|] *$//;"
           " s/,.*//; s/[0-9]//g; s/[[:space:]]+/ /g; s/^ //; s/ $//'"
           " | sort | uniq -c | sort -rn | head -1"
           % (sh(os.path.join(hq, charter.DEFAULT_DIR)), NAME_ERE, NEWEST))
    try:
        rows = {}
        for p in charters(hq)[-NEWEST:]:
            g = goal_row(p)
            if g is not None:
                rows[p] = normal(g)
    except OSError:
        return finding("live.goal_unchanged", ctx["hq"], None, ctx["threshold"], cmd,
                       {"charters": None, "distinct": None}, [])
    count = collections.Counter(rows.values())
    top, value = count.most_common(1)[0] if count else (None, 0)
    group = [p for p, g in rows.items() if g == top]
    files = group[:1] + group[1:][-1:]                # the group's oldest and newest
    return finding("live.goal_unchanged", ctx["hq"], value, ctx["threshold"], cmd,
                   {"charters": len(rows), "distinct": len(count)}, files)


def since_landing(ctx) -> dict:
    roots, git = ctx["roots"], ctx["readers"].git
    hq = str(roots["hq"])
    newest, where = None, None
    for name in ctx["goal"]:
        repo = os.path.join(str(roots["repos"]), name)
        out = git(repo, "log", "main", "--merges", "--first-parent", "-1", "--format=%ct")
        t = int(out.strip()) if out and out.strip().isdigit() else None
        if t is not None and (newest is None or t > newest):
            newest, where = t, repo
    since = newest if newest is not None else int(ctx["now"] - ctx["window"] * 86400)
    cmd = ("git -C %s log --since=@%d --diff-filter=A --name-only --format= -- %s"
           " | grep -E '/%s' | sort -u | wc -l" % (sh(hq), since, charter.DEFAULT_DIR, NAME_ERE))
    if where is not None:
        cmd = ("git -C %s log main --merges --first-parent -1 --format='landing %%ct %%h'; "
               % sh(where)) + cmd
    added = git(hq, "log", "--since=@%d" % since, "--diff-filter=A", "--name-only", "--format=",
                "--", charter.DEFAULT_DIR)
    commits = git(hq, "log", "--since=@%d" % since, "--format=%h")
    if added is None or commits is None:
        value, opened, n_commits = None, None, None
    else:
        opened = len({p for p in added.splitlines() if NAME.match(p.rsplit("/", 1)[-1])})
        value, n_commits = opened, len([c for c in commits.splitlines() if c.strip()])
    return finding("live.since_landing", ctx["hq"], value, ctx["threshold"], cmd,
                   {"landing_at": newest, "charters": opened, "hq_commits": n_commits},
                   [where] if where else [])
