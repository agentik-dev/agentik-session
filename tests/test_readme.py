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
          "make check", "/session:status", "agentik session report", "PreToolUse", "PreCompact",
          "claude plugin marketplace add agentik-dev/agentik-commons", "session@agentik",
          "make install", "agentik session doctor", "MIT",
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


@pytest.mark.parametrize("doc", [README, SOURCE], ids=["readme", "source"])
def test_the_needs_line_names_the_workflow_refusal(doc):
    # is3 R5: the line that names the Python the plugin needs (its `3.9`, kept byte-identical
    # by the verifier) says that the plugin refuses Claude Code's Workflow tool.
    needs = [l for l in doc.read_text().splitlines() if "Python 3.9" in l]
    assert len(needs) == 1 and "workflow" in needs[0].lower() and "refuse" in needs[0], needs


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


# is3: a render the verifier refuses is tried once more, with the verifier's words (R1 to R4).
# Each case copies the script into a temp repo with a stub renderer and a stub verifier beside
# it; no `claude` process and no real renderer runs.
RENDER_SCRIPT = ROOT / "scripts" / "readme-render"
RETRY_CONTRACT = "Keep every heading.\nProse only.\n"
VERDICTS = ("FAIL (md): 1 invariant violation(s)\n  - inline code spans: lost {'`make check`': 1} gained {}\n",
            "FAIL (md): 1 invariant violation(s)\n  - block structure changed: list items 12 -> 11\n")

# The stub renderer: counts its calls, keeps each call's argv and contract, writes --out,
# exits the code in rexit.<n> (0 when absent).
RENDER = r"""#!/bin/sh
n=$(( $(cat "$STUB_LOG/calls" 2>/dev/null || echo 0) + 1 )); echo $n > "$STUB_LOG/calls"
printf '%s\n' "$@" > "$STUB_LOG/argv.$n"
while [ $# -gt 0 ]; do
  case "$1" in --contract) c="$2"; shift 2 ;; --out) o="$2"; shift 2 ;; *) shift ;; esac
done
cp "$c" "$STUB_LOG/contract.$n"
printf 'rendered %s\n' "$n" > "$o"
exit $(cat "$STUB_LOG/rexit.$n" 2>/dev/null || echo 0)
"""
# The stub verifier, run by the fake python as a shell script: refuses with verdict.<n> and
# the code in vexit.<n> (1 when absent) while verdict.<n> exists, else passes.
VERIFY = r"""n=$(( $(cat "$STUB_LOG/verifies" 2>/dev/null || echo 0) + 1 )); echo $n > "$STUB_LOG/verifies"
if [ -f "$STUB_LOG/verdict.$n" ]; then
  cat "$STUB_LOG/verdict.$n"; exit $(cat "$STUB_LOG/vexit.$n" 2>/dev/null || echo 1)
fi
echo "PASS (md): edit is prose-only; all meaning-carrying content invariant"
"""
FAKE_PY = r"""#!/bin/sh
case "$1" in -) cat >/dev/null; exit 0 ;; -c) exit 0 ;; esac
exec /bin/sh "$@"
"""


def _repo(tmp_path, verdicts=(), rexits=None, vexits=None):
    repo, log, tools, tmp = (tmp_path / n for n in ("repo", "log", "respeak", "tmp"))
    for d in (repo / "scripts", repo / "design" / "readme", repo / ".venv" / "bin", log, tools, tmp):
        d.mkdir(parents=True)
    shutil.copy2(RENDER_SCRIPT, repo / "scripts" / "readme-render")
    (repo / "design" / "readme" / "source.md").write_text(
        "# T\n\nStatus: version `v1`, rendered `2026-01-01`, `1` tests in the suite.\n\nProse.\n")
    (repo / "design" / "readme" / "contract.txt").write_text(RETRY_CONTRACT)
    (repo / "README.md").write_text("the old readme\n")
    for name, text in (("respeak-render.sh", RENDER), ("respeak-verify-edit.py", VERIFY)):
        (tools / name).write_text(text)
    (repo / ".venv" / "bin" / "python").write_text(FAKE_PY)
    for f in (tools / "respeak-render.sh", repo / ".venv" / "bin" / "python"):
        f.chmod(0o755)
    for n, v in enumerate(verdicts, 1):
        (log / ("verdict.%d" % n)).write_text(v)
    for name, codes in (("rexit", rexits or {}), ("vexit", vexits or {})):
        for n, code in codes.items():
            (log / ("%s.%d" % (name, n))).write_text("%d\n" % code)
    env = {"PATH": "/usr/bin:/bin", "RESPEAK_RENDER": str(tools / "respeak-render.sh"),
           "STUB_LOG": str(log), "TMPDIR": str(tmp)}
    return repo, log, tmp, env


def _run(repo, env):
    return subprocess.run([str(repo / "scripts" / "readme-render")], cwd=repo, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)


def _calls(log):
    return int((log / "calls").read_text()) if (log / "calls").exists() else 0


def _argv(log, n):
    return (log / ("argv.%d" % n)).read_text().splitlines()


def _opt(argv, name):
    return argv[argv.index(name) + 1]


def _const(name):
    return int(re.search(r"^%s=(\d+)\b" % name, RENDER_SCRIPT.read_text(), re.M).group(1))


def _sidecar(repo):
    return repo / "design" / "readme" / "rendered.sha256"


def test_a_first_pass_renders_once_with_the_repos_contract(tmp_path):
    # Acceptance 1: one renderer call, its contract the repo's file; README and sidecar written.
    repo, log, tmp, env = _repo(tmp_path)
    run = _run(repo, env)
    assert run.returncode == 0, run.stderr
    assert _calls(log) == 1
    argv = _argv(log, 1)
    assert _opt(argv, "--contract") == "design/readme/contract.txt"
    assert _opt(argv, "--max-rounds") == str(_const("ROUNDS"))
    assert (repo / "README.md").read_text() == "rendered 1\n"
    lines = _sidecar(repo).read_text().splitlines()
    assert [l.split()[1] for l in lines] == ["design/readme/source.md", "README.md"]
    assert "PASS (md)" in run.stdout and "refused" not in run.stderr


def test_a_refusal_then_a_pass_renders_again_with_the_verifiers_words(tmp_path):
    # Acceptance 2: two calls; the second's contract is the repo's, then the verifier's words;
    # the joined contract lives outside the repo and is gone afterwards.
    repo, log, tmp, env = _repo(tmp_path, verdicts=VERDICTS[:1])
    run = _run(repo, env)
    assert run.returncode == 0, run.stderr
    assert _calls(log) == 2
    first, second = _argv(log, 1), _argv(log, 2)
    assert _opt(first, "--contract") == "design/readme/contract.txt"
    joined = Path(_opt(second, "--contract"))
    assert joined.is_absolute() and repo not in joined.parents
    assert not joined.exists() and list(tmp.iterdir()) == []
    note = (log / "contract.2").read_text()
    assert note.startswith(RETRY_CONTRACT) and VERDICTS[0].strip() in note
    assert "refused" in note[len(RETRY_CONTRACT):]
    assert _opt(second, "--max-rounds") == str(_const("RETRY_ROUNDS"))
    assert (repo / "design" / "readme" / "contract.txt").read_text() == RETRY_CONTRACT
    assert (repo / "README.md").read_text() == "rendered 2\n"
    assert _sidecar(repo).exists() and VERDICTS[0].strip() in run.stderr
    assert not list(repo.glob(".readme-render.*"))


def test_two_refusals_exit_2_and_leave_the_readme(tmp_path):
    # Acceptance 3: exit 2, README.md untouched, both refusals on stderr, no third call.
    repo, log, tmp, env = _repo(tmp_path, verdicts=VERDICTS)
    run = _run(repo, env)
    assert run.returncode == 2, run.stderr
    assert _calls(log) == 2 and (log / "verifies").read_text().strip() == "2"
    assert (repo / "README.md").read_text() == "the old readme\n"
    assert not _sidecar(repo).exists()
    assert all(v.strip() in run.stderr for v in VERDICTS)
    assert not list(repo.glob(".readme-render.*")) and list(tmp.iterdir()) == []


@pytest.mark.parametrize("rexits,code,calls", [({1: 1}, 1, 1), ({1: 2}, 2, 1), ({1: 4}, 2, 1),
                                               ({2: 1}, 1, 2), ({2: 2}, 2, 2)])
def test_a_renderer_failure_is_not_retried(tmp_path, rexits, code, calls):
    # Acceptance 4 (R4): the renderer's exit 1 is exit 1, any other failure exit 2, with no
    # further call, on the first render or on the retry.
    verdicts = VERDICTS[:1] if calls == 2 else ()
    repo, log, tmp, env = _repo(tmp_path, verdicts=verdicts, rexits=rexits)
    run = _run(repo, env)
    assert run.returncode == code, run.stderr
    assert _calls(log) == calls and "the renderer exited %d" % rexits[calls] in run.stderr
    verifies = int((log / "verifies").read_text()) if (log / "verifies").exists() else 0
    assert verifies == calls - 1
    assert (repo / "README.md").read_text() == "the old readme\n"


def test_the_verifiers_words_are_cut_to_the_bound(tmp_path):
    # Acceptance 4: a verifier output over the bound reaches the note cut to it.
    bound = _const("NOTE_BYTES")
    long = "FAIL (md): 1 invariant violation(s)\n  - " + "".join("x%05d " % i for i in range(bound))
    repo, log, tmp, env = _repo(tmp_path, verdicts=(long,))
    run = _run(repo, env)
    assert run.returncode == 0, run.stderr
    note = (log / "contract.2").read_text()
    assert long[:bound] in note and long[:bound + 1] not in note
    assert len(note.encode()) < len(RETRY_CONTRACT) + bound + 1000


def test_a_verifier_fault_is_not_retried(tmp_path):
    # R4: the verifier's own exit 2 (usage, an unknown type) is a fault, not a refusal.
    repo, log, tmp, env = _repo(tmp_path, verdicts=VERDICTS[:1], vexits={1: 2})
    run = _run(repo, env)
    assert run.returncode == 2 and _calls(log) == 1, run.stderr
    assert (repo / "README.md").read_text() == "the old readme\n"


def test_the_wall_is_the_headers_sum_of_the_scripts_constants():
    # Acceptance 5: the header states the budget as a sum of the script's constants, and the
    # Makefile's --wall is the header's wall and covers the sum.
    text = RENDER_SCRIPT.read_text()
    m = re.search(r"(\d+) \+ \((\d+) \+ (\d+)\) x \((\d+) \+ (\d+)\) \+ (\d+) = (\d+) s", text)
    assert m, "the header states no sum"
    status, rounds, retry, round_wall, grace, tail, total = map(int, m.groups())
    assert status == int(re.search(r"timeout=(\d+)\)", text).group(1))
    assert (rounds, retry, round_wall) == (_const("ROUNDS"), _const("RETRY_ROUNDS"), _const("ROUND_WALL"))
    assert (grace, tail) == (RESPEAK_GRACE, TAIL) and retry == 1
    assert total == status + (rounds + retry) * (round_wall + grace) + tail
    wall = int(re.search(r"^\tRESPEAK_RENDER=.* scripts/bounded --wall (\d+) --load 4 -- "
                         r"scripts/readme-render$", MAKEFILE.read_text(), re.M).group(1))
    assert "a %d s wall" % wall in text and total <= wall < total + 60
