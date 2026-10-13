"""The README is rendered from its source, and the sidecar says from which (S6)."""
import fnmatch
import functools
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.dom.minidom
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "design" / "readme" / "source.md"
SIDECAR = ROOT / "design" / "readme" / "rendered.sha256"
README = ROOT / "README.md"
ALLOW = ROOT / ".hygiene-allow"
MAKEFILE = ROOT / "Makefile"
MANIFEST = ROOT / "plugin" / ".claude-plugin" / "plugin.json"
ICON = ROOT / "assets" / "icon.svg"
ICON_LINE = '<img src="assets/icon.svg" alt="" width="56" align="left">'
# The record tool reads the source by section, so it may grow past a screen (S11).
SOURCE_CEILING = 16384
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
STATUS = re.compile(r"^Status: version `v([^`]+)`, rendered `(\d{4}-\d{2}-\d{2})`, "
                    r"`(\d+)` tests in the suite\.$", re.M)
# The groups the README and its source may be excused from (ADV6-2): no wider.
README_ALLOW_CEILING = {"sibling", "person"}

# The facts the README must carry; fixed strings, not patterns.
TOKENS = ["/session:read", "charter open", "resolved.json", "CLAUDE_CODE_SESSION_ID",
          "make check", "/session:status", "claude-session report", "PreToolUse", "PreCompact",
          "claude plugin marketplace add", "make install", "claude-session doctor", "MIT",
          "scripts/hygiene", "scripts/doclint", "rendered.sha256", "design/overhaul-r1.md"]


def test_sidecar_is_the_shasum_lines_of_the_source_and_the_readme():
    # The full `shasum -a 256` lines, so `shasum -c` checks both from the repo root;
    # the second is the tamper guard on the rendered README (ADV6-2).
    lines = ["%s  %s\n" % (hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(ROOT))
             for p in (SOURCE, README)]
    assert SIDECAR.read_text() == "".join(lines)


def test_make_readme_writes_both_lines():
    # The Makefile's readme target is the render script under a wall (ADV10-6; its size,
    # test_readme_wall_covers_the_renderer_budget); the script writes the sidecar.
    assert re.search(r"^readme:.*\n\t(RESPEAK_RENDER=\"\$\(RESPEAK_RENDER\)\" )?"
                     r"scripts/bounded --wall \d+ --load 4 -- scripts/readme-render\n",
                     MAKEFILE.read_text(), re.M)
    script = (ROOT / "scripts" / "readme-render").read_text()
    assert ("shasum -a 256 design/readme/source.md README.md > design/readme/rendered.sha256"
            in script)


def _check(root):
    return subprocess.run(["shasum", "-c", "--status", "design/readme/rendered.sha256"],
                          cwd=root).returncode


def test_hand_edited_readme_fails_the_check(tmp_path):
    for p in (SOURCE, README, SIDECAR):
        dest = tmp_path / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    assert _check(tmp_path) == 0
    with open(tmp_path / "README.md", "a") as fh:
        fh.write("a hand edit\n")
    assert _check(tmp_path) != 0


def _allow_rows():
    for raw in ALLOW.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            glob, _, groups = line.rpartition(":")
            yield glob.strip(), {g.strip() for g in groups.split(",") if g.strip()}


def _glob_match(path, glob):
    parts, pats = path.split("/"), glob.split("/")
    return len(parts) == len(pats) and all(fnmatch.fnmatchcase(p, g) for p, g in zip(parts, pats))


@pytest.mark.parametrize("path", ["README.md", "design/readme/source.md"])
def test_readme_allow_rows_pinned(path):
    # Every row that excuses the README or its source stays within sibling,person.
    for glob, groups in _allow_rows():
        if _glob_match(path, glob):
            assert groups <= README_ALLOW_CEILING, (glob, sorted(groups))


@pytest.mark.parametrize("token", TOKENS)
@pytest.mark.parametrize("doc", [README, SOURCE], ids=["readme", "source"])
def test_readme_holds_token(doc, token):
    assert token in doc.read_text()


@pytest.mark.parametrize("doc", [README, SOURCE], ids=["readme", "source"])
def test_c1_the_siblings_are_optional_and_unpinned(doc):
    # mod-r1 §9, decided 2026-10-11: no range a sibling's release can break, and the
    # README says a user installs none of them to use this plugin.
    text = doc.read_text()
    assert not re.search(r"\^\d+\.\d+", text), re.search(r".{0,40}\^\d+\.\d+", text)
    assert "optional" in text and "Dependencies, by plugin id and range" not in text


def test_readme_names_no_other_session_variable():
    assert "CLAUDE_SESSION_ID" not in README.read_text()


def test_source_under_ceiling():
    assert 0 < SOURCE.stat().st_size < SOURCE_CEILING


@functools.lru_cache(maxsize=None)
def _collected():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                          "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True,
                         timeout=120).stdout
    return int(re.search(r"^(\d+) tests? collected", out.strip().splitlines()[-1]).group(1))


@pytest.mark.parametrize("doc", [README, SOURCE], ids=["readme", "source"])
def test_status_line_matches_manifest_and_suite(doc):
    # scripts/readme-render writes the line; the contract keeps code spans byte-identical.
    found = STATUS.findall(doc.read_text())
    assert len(found) == 1, found
    version, _date, count = found[0]
    manifest = json.loads(MANIFEST.read_text())["version"]
    assert SEMVER.match(manifest) and version == manifest
    assert int(count) == _collected()


@pytest.mark.parametrize("doc", [README, SOURCE], ids=["readme", "source"])
def test_icon_line_under_title(doc):
    lines = doc.read_text().splitlines()
    assert lines[0].startswith("# ") and lines[2] == ICON_LINE


def test_icon_is_plain_svg():
    text = ICON.read_text()
    assert len(text.encode()) < 1500
    assert "url(#" not in text and "<script" not in text and "href" not in text
    svg = xml.dom.minidom.parseString(text).documentElement
    assert svg.tagName == "svg" and svg.getAttribute("viewBox") == "0 0 64 64"
    assert svg.getAttribute("role") == "img" and svg.getAttribute("aria-label")
    assert svg.getElementsByTagName("title")[0].firstChild.data == "session"


def test_render_refuses_without_a_renderer_and_leaves_the_readme(tmp_path):
    # A copy in a temp git repo, never the real checkout (ADV10-11).
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "design" / "readme").mkdir(parents=True)
    script = repo / "scripts" / "readme-render"
    shutil.copy2(ROOT / "scripts" / "readme-render", script)
    shutil.copy2(SOURCE, repo / "design" / "readme" / "source.md")
    shutil.copy2(README, repo / "README.md")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)
    before = (repo / "README.md").read_bytes(), SOURCE.read_bytes(), README.read_bytes()
    env = {"PATH": "/usr/bin:/bin", "RESPEAK_RENDER": str(tmp_path / "absent.sh")}
    run = subprocess.run([str(script)], cwd=repo, env=env, capture_output=True, text=True,
                         timeout=120)
    assert run.returncode == 2 and "no respeak renderer" in run.stderr
    assert ((repo / "README.md").read_bytes(), SOURCE.read_bytes(), README.read_bytes()) == before


SITTING_MARKERS = ("RELAY_ROW", "CLAUDE_SESSION_DEPTH", "CLAUDE_SESSION_MAX_TURNS")


def _render_repo(tmp_path):
    # A copy in a temp git repo with a fake status python, a fake renderer that records its
    # env and calls its runner, and a fake `claude` that records its arguments.
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "design" / "readme").mkdir(parents=True)
    (repo / ".venv" / "bin").mkdir(parents=True)
    script = repo / "scripts" / "readme-render"
    shutil.copy2(ROOT / "scripts" / "readme-render", script)
    shutil.copy2(SOURCE, repo / "design" / "readme" / "source.md")
    (repo / "design" / "readme" / "contract.txt").write_text("contract\n")
    shutil.copy2(README, repo / "README.md")
    logs = {k: tmp_path / ("%s.log" % k) for k in ("status", "render", "claude")}
    fake_py = repo / ".venv" / "bin" / "python"
    fake_py.write_text('#!/bin/sh\n[ "$1" = - ] && { cat >/dev/null; env > "%s"; }\nexit 0\n'
                       % logs["status"])
    tools, bin_ = tmp_path / "respeak", tmp_path / "bin"
    tools.mkdir()
    bin_.mkdir()
    render = tools / "respeak-render.sh"
    render.write_text('#!/bin/sh\nenv > "%s"\n"$RESPEAK_RENDER_CMD" -p --model m </dev/null\nexit 1\n'
                      % logs["render"])
    (tools / "respeak-verify-edit.py").write_text("")
    claude = bin_ / "claude"
    claude.write_text('#!/bin/sh\nprintf "%%s\\n" "$@" > "%s"\n' % logs["claude"])
    for f in (fake_py, render, claude):
        f.chmod(0o755)
    env = {"PATH": "%s:/usr/bin:/bin" % bin_, "RESPEAK_RENDER": str(render), "KEEP_ME": "1",
           "RELAY_ROW": "s99-x", "CLAUDE_SESSION_MAX_TURNS": "40"}
    return repo, script, fake_py, env, logs


def _snapshot(repo):
    return sorted((str(f.relative_to(repo)), f.read_bytes()) for f in repo.rglob("*") if f.is_file())


def test_renderer_runs_as_a_marked_helper(tmp_path):
    # relay-r1 section 10 (row s16-resync): the renderer keeps RELAY_ROW and
    # CLAUDE_SESSION_MAX_TURNS, runs one level down with CLAUDE_SESSION_HELPER=1, and its
    # `claude -p` carries --max-turns; the status step, the sitting's own work, sees the env as given.
    repo, script, fake_py, env, logs = _render_repo(tmp_path)
    env["CLAUDE_SESSION_DEPTH"] = "1"
    before = (repo / "README.md").read_bytes()
    run = subprocess.run([str(script)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 1 and "the renderer exited 1" in run.stderr, run.stderr
    seen = dict(l.split("=", 1) for l in logs["render"].read_text().splitlines() if "=" in l)
    assert seen["CLAUDE_SESSION_DEPTH"] == "2" and seen["CLAUDE_SESSION_HELPER"] == "1"
    assert seen["RELAY_ROW"] == "s99-x" and seen["CLAUDE_SESSION_MAX_TURNS"] == "40"
    assert seen["KEEP_ME"] == "1" and seen["RESPEAK_PYTHON"] == str(fake_py)
    argv = logs["claude"].read_text().splitlines()
    assert argv[:2] == ["--max-turns", "20"] and "-p" in argv, argv
    status = dict(l.split("=", 1) for l in logs["status"].read_text().splitlines() if "=" in l)
    assert status["CLAUDE_SESSION_DEPTH"] == "1" and "CLAUDE_SESSION_HELPER" not in status
    assert all(m in status for m in SITTING_MARKERS)
    assert (repo / "README.md").read_bytes() == before
    assert not list(repo.glob(".readme-render.*"))
    text = script.read_text()
    assert "env -u" not in text and text.count("CLAUDE_SESSION_DEPTH=$((d + 1)) CLAUDE_SESSION_HELPER=1") == 1
    assert not re.search(r"^\s*(unset|export)\b.*(RELAY_ROW|CLAUDE_SESSION_)", text, re.M)


@pytest.mark.parametrize("depth,why", [("2", "refused past depth 2"), ("3", "refused past depth 2"),
                                       ("99999999999999999999", "refused past depth 2"),
                                       ("x", "not a plain"), ("-1", "not a plain"), ("01", "not a plain")])
def test_renderer_helper_refused_past_depth_2(tmp_path, depth, why):
    # A helper one level below depth d is refused when d + 1 > 2, or d is not a plain
    # non-negative integer: exit 2 in setup, before any write; nothing runs.
    repo, script, _, env, logs = _render_repo(tmp_path)
    env["CLAUDE_SESSION_DEPTH"] = depth
    before = _snapshot(repo)
    run = subprocess.run([str(script)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 2 and why in run.stderr, run.stderr
    assert not any(f.exists() for f in logs.values())
    assert _snapshot(repo) == before


# respeak-render.sh's own defaults, which hold when the caller passes neither: 2 rounds,
# RESPEAK_RENDER_WALL 600 s a round, and respeak-deadline.sh's 2 s grace after each.
RESPEAK_ROUNDS, RESPEAK_ROUND_WALL, RESPEAK_GRACE = 2, 600, 2
# One round of this README, measured from the runner's transcripts: 524 s (2026-10-10) and
# 530 s (2026-10-11), almost all of it the model's thinking; two more were cut at 600 s.
MEASURED_ROUND = 530
# The style gate after each round, the verifier and the move, with room to spare.
TAIL = 60


def test_readme_wall_covers_the_renderer_budget(tmp_path):
    # `make readme`'s wall holds the status step's timeout and every round the renderer may
    # run at its own wall, and a round's wall leaves the measured round half again (F5).
    repo, script, _, env, logs = _render_repo(tmp_path)
    render = Path(env["RESPEAK_RENDER"])
    render.write_text('#!/bin/sh\nprintf "%%s\\n" "$@" > "%s"\nenv > "%s"\nexit 1\n'
                      % (logs["claude"], logs["render"]))
    run = subprocess.run([str(script)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 1 and "the renderer exited 1" in run.stderr, run.stderr
    argv = logs["claude"].read_text().splitlines()
    seen = dict(l.split("=", 1) for l in logs["render"].read_text().splitlines() if "=" in l)
    rounds = int(argv[argv.index("--max-rounds") + 1]) if "--max-rounds" in argv else RESPEAK_ROUNDS
    round_wall = int(seen.get("RESPEAK_RENDER_WALL", RESPEAK_ROUND_WALL))
    status = int(re.search(r"timeout=(\d+)\)", script.read_text()).group(1))
    wall = int(re.search(r"^\tRESPEAK_RENDER=.* scripts/bounded --wall (\d+) --load 4 -- "
                         r"scripts/readme-render$", MAKEFILE.read_text(), re.M).group(1))
    assert round_wall >= MEASURED_ROUND * 3 // 2, round_wall
    budget = status + rounds * (round_wall + RESPEAK_GRACE) + TAIL
    assert wall >= budget, (wall, budget)
