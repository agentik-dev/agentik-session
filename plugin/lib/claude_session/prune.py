"""prune: the old frozen trees an install removes, and the ones it keeps (F8).

`install-cli` freezes the plugin's lib/ under <share>/<tree> and points the launcher at the new
tree. A launcher already running keeps its tree for its whole life, which for a respawn chain is
hours: the new form names it on its command line (`Python -I ... <tree>/agentik-session run`),
the old one in its environment (PYTHONPATH=<tree>), and an old launcher runs for a day or more,
so both count. Deleting every other tree pulled the code out from under it. The prune keeps:

  - the new tree (its mtime set to now, so a re-install of an old tree counts as newest);
  - every entry a running process names in its command line or its environment, read from
    `ps -axwwE -o pid=,command=` (macOS shows the environment of the user's own processes);
    each absolute path there is compared by realpath, so a spelling through a symlink
    (`/tmp` for `/private/tmp`) or with a doubled slash still names its tree;
  - the newest KEEP entries by mtime (default 3): they cover a launcher that read the old
    launcher just before it was replaced and has not yet exec'd python, and any process
    ps could not see;

and removes the rest. An entry whose name starts with a dot is the install's own (its lock, its
staging folder) and no tree: it is neither counted nor removed. It fails safe: when ps cannot
run, exits non-zero, or shows no environment (a probe variable set in ps's own environment is
missing from its output), nothing is removed and it says `keeping every tree`.

The limit: macOS hides the environment of its platform binaries (Apple-signed ones such as
/bin/sleep or /usr/bin/perl) even from their own user, and the probe cannot tell, since ps
shows its own. A tree named only in such a process's environment is not seen, and is
removed unless it is among the newest KEEP. A launcher is seen: the new form by its command
line, the old by its environment, since every python the old install could bake (a venv's,
homebrew's) shows it, and /usr/bin/python3's shows it too (sc3, measured).

Usage: python -m claude_session.prune --share DIR --new NAME [--keep N] [--ps PROGRAM]
Exit 0 when it pruned or kept, 2 on a usage error (NAME is not a directory under DIR).
Stdlib only: `install-cli` runs it with no checkout.
"""
import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

PROBE = "CLAUDE_SESSION_PRUNE_PROBE"


def processes(ps, timeout=60):
    """(every process's command line and environment as one text, None) or (None, why)."""
    token = secrets.token_hex(8)
    try:
        r = subprocess.run([ps, "-axwwE", "-o", "pid=,command="], capture_output=True,
                           text=True, errors="replace", timeout=timeout,
                           env=dict(os.environ, **{PROBE: token}))
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"{ps}: {e}"
    if r.returncode != 0:
        return None, f"{ps} exited {r.returncode}"
    if f"{PROBE}={token}" not in r.stdout:
        return None, "no process environment is visible"
    return r.stdout, None


# An absolute path in ps output: it starts the text, or follows whitespace, `:`, `=` or a
# quote, and runs to the next of those.
PATHS = re.compile(r"(?<![^\s:='\"])/[^\s:'\"]*")


def named(text, share):
    """The entry names right under `share` that a process text names. Each absolute path in
    the text is compared by realpath (a symlink or a doubled slash still names its tree);
    the share's own spellings are matched literally too, so a share path with a space,
    which no path token can hold, still counts."""
    real = os.path.realpath(share).rstrip("/")
    names = set()
    for root in {str(share).rstrip("/"), real}:
        names.update(re.findall(re.escape(root) + r"/([^/:\s'\"]+)", text))
    for token in set(PATHS.findall(text)):
        try:
            resolved = os.path.realpath(token)
        except (OSError, ValueError):
            continue
        if resolved.startswith(real + "/"):
            names.add(resolved[len(real) + 1:].split("/", 1)[0])
    return names


def remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def prune(share, new, keep=3, ps="ps", ps_timeout=60):
    """(exit code, the lines to say). Never removes `new`; on doubt removes nothing."""
    share = Path(share)
    tree = share / new
    if keep < 1 or "/" in new or new in ("", ".", "..") or not tree.is_dir():
        return 2, [f"prune-trees: {new} is not a tree under {share} (or --keep < 1)"]
    os.utime(tree)
    text, why = processes(ps, ps_timeout)
    if text is None:
        return 0, [f"prune-trees: {why}; keeping every tree"]
    live = named(text, share)
    entries = sorted((p for p in share.iterdir() if not p.name.startswith(".")),
                     key=lambda p: (p.lstat().st_mtime_ns, p.name), reverse=True)
    newest = {p.name for p in entries[:keep]} | {new}
    seen = [p for p in entries if p.name in live]
    lines = []
    removed, failed = 0, 0
    for p in entries:
        if p.name in newest or p.name in live:
            continue
        try:
            remove(p)
            removed += 1
        except OSError as e:
            failed += 1
            lines.append(f"prune-trees: {p}: {e}")
    lines.append(f"prune-trees: removed {removed}, kept {len(entries) - removed}"
                 f" ({len(seen)} live, the newest {keep})" + (f", {failed} failed" if failed else ""))
    return 0, lines


def main(argv=None):
    ap = argparse.ArgumentParser(prog="prune-trees", description=__doc__.split("\n")[0])
    ap.add_argument("--share", required=True, type=Path)
    ap.add_argument("--new", required=True)
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--ps", default="ps")
    a = ap.parse_args(argv)
    code, lines = prune(a.share, a.new, a.keep, a.ps)
    for line in lines:
        print(line, file=sys.stdout if line.startswith("prune-trees: removed") else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
