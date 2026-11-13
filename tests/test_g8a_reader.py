"""Packet g8a-reader-parts: the reader's new parts, one walk of a line's commands.

1 the commands of a line, past wrappers, reserved words and substitutions; 2 a shell's script at
level 1; 3 data read as no command; 4 the parts not read, each by its kind; 5 the folder a
command runs in; 6 the words around a substitution kept with their command; 7 git's global
options; 8 real shells run the lines and call what the reader names; 9 the gates and the make
rule read the same commands; 10 the quoted-substitution cutter is gone; 11 (fix of the read)
a shell's `-c` text behind a runner and a heredoc's body are texts not read, a substitution
glued to the command word is read as empty, and the walk returns early on a plain line.
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from claude_session.shellreader import Cmd, Unread, commands, git_words
from claude_session import shellreader, unattended

ROOT = Path(__file__).resolve().parents[1]
G = "git add -A"
HERE = "/g8/repo"
ENV = {"HOME": "/g8/home"}

T1 = ["{G}", "/usr/bin/git add -A", "X=1 {G}", "env -i X=1 {G}", "sudo -u bob {G}",
      "nice -n 5 {G}", "command {G}", "exec {G}", "time -p {G}", "({G})", "{{ {G}; }}",
      "if true; then {G}; fi", "for f in a; do {G}; done", "true && {G}", "! {G}",
      "echo $({G})", "echo \"$({G})\"", "x=\"$({G})\"", "echo `{G}`", "x=`{G}`",
      "echo \"a `{G}` b\"", "echo \"$(echo \"$({G})\")\"", "cat < \"$({G})\"",
      "x=\"$(case a in a) {G};; esac)\"", "n=\"$(grep -c ')' f.txt)\"; {G}",
      "echo `echo \\`{G}\\``", "cat <<EOF\nsee `{G}`\nEOF", "cat <<EOF\n$({G})\nEOF"]
T2 = ["bash -c '{G}'", "bash -lc '{G}'", "bash -c -e '{G}'", "bash -o pipefail -c '{G}'",
      "/bin/zsh -c '{G}'", "BASH -c '{G}'", "ksh -c '{G}'", "bash <<EOF\n{G}\nEOF",
      "bash -s <<'EOF'\n{G}\nEOF", "sh -eu <<EOF\n{G}\nEOF"]
T3 = ["echo '{G}'", "echo \"{G}\"", "git commit -m \"{G}\"", "echo ok # {G}", "echo '$({G})'",
      "echo \"\\$({G})\"", "echo '`{G}`'", "grep -r \"{G}\" .", "cat <<EOF\n{G}\nEOF",
      "cat <<'EOF'\nsee `{G}`\nEOF", "bash run.sh <<EOF\n{G}\nEOF", "command -v git",
      "xargs {G}", "find . -exec {G} {{}} +", "timeout 5 {G}", "runner -- bash -c '{G}'"]
T4 = [("eval '{G}'", "eval"), ("env -S '{G}'", "eval"), ("bash -c \"bash -c '{G}'\"", "below"),
      ("bash -c 'bash <<EOF\n{G}\nEOF'", "below"), ("echo '{G}' | sh", "piped"),
      ("bash <<< '{G}'", "piped"), ("cat <<EOF | sh\n{G}\nEOF", "piped"),
      ("echo \"it's\" '{G}", "split")]


def _read(line):
    return commands(line, HERE, ENV)


def _adds(cmds):
    return [c for c in cmds if c.name == "git" and "add" in c.args]


# ---- 1, 2, 3, 4: what a line runs, and what it does not -----------------------------------

@pytest.mark.parametrize("shape", T1, ids=[str(i) for i in range(len(T1))])
def test_1_the_commands(shape):
    cmds, unread = _read(shape.format(G=G))
    gits = [c for c in cmds if c.name == "git"]
    assert len(gits) == 1, cmds
    assert gits[0].args == ["add", "-A"] and gits[0].level == 0, gits
    assert [u for u in unread if u.why != "data"] == [], unread     # fix: a body is `data`
    assert all(isinstance(c, Cmd) for c in cmds)


@pytest.mark.parametrize("shape", T2, ids=[str(i) for i in range(len(T2))])
def test_2_level_one(shape):
    cmds, unread = _read(shape.format(G=G))
    assert cmds[0].name.lower() in ("bash", "zsh", "ksh", "sh") and cmds[0].level == 0, cmds
    gits = [c for c in cmds if c.name == "git"]
    assert len(gits) == 1 and gits[0].args == ["add", "-A"] and gits[0].level == 1, cmds
    assert unread == [], unread


@pytest.mark.parametrize("shape", T3, ids=[str(i) for i in range(len(T3))])
def test_3_no_command(shape):
    cmds, unread = _read(shape.format(G=G))
    assert _adds(cmds) == [], cmds
    # fix of the read: a heredoc's body is `data`, a runner's `-c` text `runner`; nothing else
    assert all(u.why in ("data", "runner") for u in unread), unread
    assert bool(unread) == ("<<" in shape or "bash -c" in shape), (shape, unread)


def test_3_the_commit_is_one_git():
    cmds, _ = _read("git commit -m \"{G}\"".format(G=G))
    assert [c.name for c in cmds] == ["git"]
    assert git_words(cmds[0].args)[1] == "commit"


@pytest.mark.parametrize("shape,why", T4, ids=[str(i) for i in range(len(T4))])
def test_4_unread(shape, why):
    cmds, unread = _read(shape.format(G=G))
    assert _adds(cmds) == [], cmds
    unread = [u for u in unread if u.why != "data"]     # fix of the read: a body is `data`
    assert len(unread) == 1 and unread[0].why == why, unread
    assert G in unread[0].text and isinstance(unread[0], Unread)


def test_4_the_texts():
    assert _read("cat run.sh | bash")[1] == [Unread("piped", "cat run.sh")]
    assert _read("eval \"$X\"")[1] == [Unread("eval", "$X")]


# ---- 5, 6: the folder, and words kept whole ------------------------------------------------

def _gits(line):
    return [c for c in _read(line)[0] if c.name == "git"]


def test_5_the_folder():
    assert _gits("cd /g8/x && " + G)[0].heres[0] == "/g8/x"
    assert _gits("cd \"$T\" && " + G)[0].heres == [None]
    assert _gits("(cd /g8/x); " + G)[0].heres[0] == HERE
    assert _gits("if t; then cd /g8/x; fi; " + G)[0].heres == ["/g8/x", HERE]
    inner = _gits("bash -c 'cd /g8/x && " + G + "'")
    assert inner[0].heres[0] == "/g8/x" and inner[0].level == 1
    two = _gits("echo \"$(cd /g8/x && " + G + ")\"; " + G)
    assert [g.heres[0] for g in two] == ["/g8/x", HERE]


def test_6_words_kept_whole():
    cmds, _ = _read("git commit -m \"$(cat <<'EOF'\nfix -a\nEOF\n)\" -a")
    gits = [c for c in cmds if c.name == "git"]
    assert len(gits) == 1 and len(gits[0].args) == 4 and gits[0].args[-1] == "-a", cmds
    assert [c.name for c in cmds].count("cat") == 1
    cmds, _ = _read("echo a$(" + G + ")b c")
    echo = [c for c in cmds if c.name == "echo"]
    assert len(echo) == 1 and len(echo[0].args) == 2, cmds
    assert len(_adds(cmds)) == 1 and not [c for c in cmds if c.name == "b"]
    cmds, _ = _read("T=$(mktemp -d); " + G)
    assert [c.name for c in cmds] == ["", "mktemp", "git"], cmds
    assert cmds[0].pre == ["T=$(mktemp -d)"]
    cmds, _ = _read("rm -rf \"$(mktemp -d)\"/x")
    rm = [c for c in cmds if c.name == "rm"]
    assert len(rm) == 1 and len(rm[0].args) == 2 and "$(" in rm[0].args[1], cmds


# ---- 7: git's global options ------------------------------------------------------------

@pytest.mark.parametrize("args,want", [
    ("-C /g8/x add -A", ([("-C", "/g8/x")], "add", ["-A"])),
    ("-c a.b=c add -A", ([("-c", "a.b=c")], "add", ["-A"])),
    ("--no-pager add -A", ([("--no-pager", None)], "add", ["-A"])),
    ("--namespace n add -A", ([("--namespace", "n")], "add", ["-A"])),
    ("--git-dir=/g8/x/.git --work-tree /g8/x add -A",
     ([("--git-dir=/g8/x/.git", None), ("--work-tree", "/g8/x")], "add", ["-A"])),
    ("-C a -C b status", ([("-C", "a"), ("-C", "b")], "status", [])),
])
def test_7_git_words(args, want):
    assert git_words(args.split()) == want


def test_7_no_words():
    assert git_words([]) == ([], "", [])


# ---- 8: real shells ----------------------------------------------------------------------

SHELLS = ("/bin/bash", "/bin/zsh", "/bin/sh")
STUBS = ("git", "rm", "make")
# a runner's command a shell does run (R4 passes it knowingly); a first program the box lacks
# or must not run (sudo; a git named by path; `env -i`, which drops the box's PATH; a login
# shell, whose profile puts the system's folders first)
LEFT_OUT = {"xargs {G}", "find . -exec {G} {{}} +", "timeout 5 {G}", "runner -- bash -c '{G}'",
            "sudo -u bob {G}", "/usr/bin/git add -A", "env -i X=1 {G}", "bash -lc '{G}'"}


def _box(tmp_path):
    stubs, work = tmp_path / "bin", tmp_path / "work"
    stubs.mkdir()
    work.mkdir()
    log = tmp_path / "calls.txt"
    for name in STUBS:
        p = stubs / name
        p.write_text('#!/bin/sh\nprintf "%%s\\n" "%s $*" >> "%s"\n' % (name, log))
        p.chmod(0o755)
    return stubs, work, log


def _run(shell, line, box):
    stubs, work, log = box
    if log.exists():
        log.unlink()
    out = subprocess.run([shell, "-c", line], cwd=str(work), capture_output=True, text=True,
                         timeout=30, env={"PATH": "%s:/usr/bin:/bin" % stubs,
                                          "HOME": str(work)})
    calls = log.read_text().splitlines() if log.exists() else []
    err = out.stderr.lower()
    if out.returncode and not calls and ("syntax" in err or "parse error" in err
                                         or "not found" in err or "unexpected" in err):
        return None
    return calls


def _shells():
    return [s for s in SHELLS if os.path.exists(s)]


def test_8_real_shells(tmp_path):
    box = _box(tmp_path)
    ran = 0
    for shape in T1 + T2:
        if shape in LEFT_OUT:
            continue
        line = shape.format(G=G)
        want = sorted(" ".join([c.name] + c.args) for c in _read(line)[0] if c.name in STUBS)
        for shell in _shells():
            calls = _run(shell, line, box)
            if calls is None:
                continue
            ran += 1
            # as a set: bash 3.2 expands a failed redirection's word again for its message
            assert sorted(set(calls)) == sorted(set(want)), (shell, line, calls, want)
    for shape in T3[:-4]:
        line = shape.format(G=G)
        for shell in _shells():
            calls = _run(shell, line, box)
            if calls is None:
                continue
            ran += 1
            assert not [c for c in calls if c.startswith("git add")], (shell, line, calls)
            if line.startswith("git commit"):
                assert len(calls) == 1 and calls[0].startswith("git commit"), calls
    assert ran >= 60, ran


# ---- 9: the gates and the make rule read the same ------------------------------------------

def test_9_the_gates_read_the_same():
    gated = HERE + "/CLAUDE.md"
    for shape in T1 + T2:
        line = shape.replace("git add -A", "cp a CLAUDE.md").format(G="cp a CLAUDE.md")
        found = [p for _, p in shellreader.bash_targets(line, HERE, ENV)]
        assert gated in found, (line, found)
    for shape in T3:
        line = shape.format(G="cp a CLAUDE.md")
        found = [p for _, p in shellreader.bash_targets(line, HERE, ENV)]
        assert gated not in found, (line, found)


def test_9_the_make_rule_reads_the_same():
    held = [s for s in T1 + T2 + [s for s, _ in T4] if "{G}" in s]
    for shape in held:
        line = shape.format(G="make x")
        assert unattended.unbounded(line), line
    assert unattended.unbounded("cat <<EOF\nmake x\nEOF").startswith("it runs `make`")  # the pin's
    assert unattended.unbounded("echo 'make x'") == ""


# ---- 10: the cutter is gone --------------------------------------------------------------

def test_10_no_cutter():
    hits = []
    for top in ("plugin", "tests"):
        for p in sorted((ROOT / top).rglob("*.py")):
            for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if "_substituted" in ln:
                    hits.append((p.name, n))
    assert len(hits) == 1 and hits[0][0] == "test_g8a_reader.py", hits


# ---- 11: fix of the read (classes A and B, E1, the early returns) -------------------------

M = "make check"
# class A: a shell and its `-c` text behind a command that is no wrapper
RUNNERS = ["scripts/bounded -- sh -c '{M}'", "timeout 60 sh -c '{M}'", "xargs sh -c '{M}'",
           "find . -exec sh -c '{M}' \\;", "ssh host sh -c '{M}'", "/usr/bin/env bash -c '{M}'",
           "doas sh -c '{M}'", "setsid sh -c '{M}'", "stdbuf -oL sh -c '{M}'",
           "flock /tmp/l sh -c '{M}'", "busybox sh -c '{M}'", "nice -n 5 timeout 9 BASH -lc '{M}'",
           "tool gate run /r -- /bin/sh -c \"{M} > $L 2>&1\"", "sh -c 'tool run -- sh -c \"{M}\"'"]
# class B and its kin: a heredoc's body a shell may run, read by the walk as no script
BODIES = ["cat > x.sh <<'EOF'\n{M}\nEOF", "cat > x.sh <<'EOF'\n{M}\nEOF\nbash x.sh",
          "cat > $S/x.sh <<'EOF'\nnice -n 19 {M} > log\nEOF\nbash -eu $S/x.sh",
          "cat > x.sh <<EOF\n{M}\nEOF\nnohup bash ./x.sh &", "tee x.sh <<EOF\n{M}\nEOF\nsh x.sh",
          "ssh host sh <<EOF\n{M}\nEOF", "source /dev/stdin <<EOF\n{M}\nEOF",
          "bash /dev/stdin <<EOF\n{M}\nEOF", "( sh ) <<EOF\n{M}\nEOF", "{{ sh; }} <<EOF\n{M}\nEOF",
          "sh 0<<EOF\n{M}\nEOF", "timeout 9 sh <<EOF\n{M}\nEOF", "sudo -i <<EOF\n{M}\nEOF",
          "cat <<EOF | ssh host sh\n{M}\nEOF", "cat <<EOF | xargs -I{{}} sh -c '{{}}'\n{M}\nEOF",
          "cat <<EOF | (sh)\n{M}\nEOF", "cat <<EOF | timeout 9 sh\n{M}\nEOF",
          "eval \"$(cat <<EOF\n{M}\nEOF\n)\"", "sh -c \"$(cat <<EOF\n{M}\nEOF\n)\"",
          "x=$(cat <<EOF\n{M}\nEOF\n); eval \"$x\"", "bash <(cat <<EOF\n{M}\nEOF\n)",
          "python3 - <<'EOF'\nimport subprocess; subprocess.run('{M}', shell=True)\nEOF"]
# E1: a substitution glued to the command word
GLUED = ["$(true){M}", "$(){M}", "sudo $(true){M}", "x=1 $(true){M}", "`true`{M}",
         "make$(true) check", "make`true` check"]


@pytest.mark.parametrize("shape", RUNNERS, ids=[str(i) for i in range(len(RUNNERS))])
def test_11_a_runner_text_is_not_read(shape):
    assert unattended.unbounded(shape.format(M=M)).startswith("it runs `make` in a text"), shape
    assert unattended.unbounded(shape.format(M="echo hi")) == "", shape
    cmds, unread = _read(shape.format(M=M))
    assert any(u.why == "runner" and M in u.text for u in unread), unread
    assert [c for c in cmds if c.name == "make"] == [], cmds        # R4 stands: no Cmd from it


def test_11_the_runner_texts():
    assert _read("timeout 60 sh -c 'make check'")[1] == [Unread("runner", "make check")]
    assert _read("x sh -c -e 'a' b")[1] == [Unread("runner", "-e a b")]
    assert _read("runner -- bash -c 'make x'")[1] == [Unread("runner", "make x")]
    assert _read("sudo sh -c 'make x'")[1] == []                   # a wrapper: read at level 1
    assert _read("echo sh")[1] == [] and _read("grep -c sh f")[1] == []


@pytest.mark.parametrize("shape", BODIES, ids=[str(i) for i in range(len(BODIES))])
def test_11_a_body_is_not_read(shape):
    assert unattended.unbounded(shape.format(M=M)), shape
    assert unattended.unbounded(shape.format(M="echo hi")) == "", shape


def test_11_the_body_texts():
    assert _read("cat <<'EOF'\nmake x\nEOF")[1] == [Unread("data", "make x")]
    assert _read("cat > x.md <<'EOF'\nit's\nEOF")[1] == [Unread("data", "it's")]
    assert unattended.unbounded("cat > x.md <<'EOF'\nit's\nEOF") == ""
    assert _read("sh <<EOF\nmake x\nEOF")[1] == []                 # the script, read at level 1
    assert _read("cat <<EOF\n$(make x)\nEOF")[1] == [Unread("data", "$(make x)")]


@pytest.mark.parametrize("shape", GLUED, ids=[str(i) for i in range(len(GLUED))])
def test_11_a_glued_substitution_is_read_as_empty(shape):
    line = shape.format(M=M)
    assert unattended.unbounded(line) == "it runs `make`; " + unattended.WHY_MAKE, line
    assert [c.name for c in _read(line)[0]][0] == "make", line


def test_11_a_glued_substitution_in_the_gates():
    gated = HERE + "/CLAUDE.md"
    for line in ("$()cp a CLAUDE.md", "$(true)cp a CLAUDE.md", "x=1 `true`cp a CLAUDE.md"):
        assert gated in [p for _, p in shellreader.bash_targets(line, HERE, ENV)], line


def test_11_the_early_returns(monkeypatch):
    calls = []
    real = shellreader._mask
    monkeypatch.setattr(shellreader, "_mask", lambda *a, **k: calls.append(a) or real(*a, **k))
    for line in ("git add -A && echo $(date)", "x=${y:-1}; cp a b", "echo `date` > f"):
        assert shellreader._parse(line, False, True)[4] == [], line
    assert calls == []
    assert shellreader._parse("x=$(echo ${y:-a)}); cp a b", False, True)[4] != []
    line = "git status --short " * 40
    assert shellreader._here_scan(line)[0] is line
    assert shellreader._subst(line, False, False, 0) == (line, [])
    assert shellreader._subst(line, False, False, 0)[0] is line


# ---- 12: fix of review 1 (R1-F1 to F7, N1), each line also run by real shells over stubs ----

MK = "make check"
# R1-F1: a make word spelled with the shell's quoting in a text the walk does not read
F1 = ["timeout 5 sh -c 'm\\ake check'", "runner -- sh -c 'm\"\"ake check'",
      "timeout 5 sh -c 'ma\\\nke check'", "bash -c \"bash -c 'ma\\ke check'\"",
      "cat > x.sh <<'EOF'\n'ma'ke check\nEOF\nsh x.sh", "cat <<EOF | sh\nm\\ake check\nEOF",
      "eval 'm\\ake check'", "echo 'm\\ake check' | sh"]
# R1-F2: E1's glue at level 1, in a `-c` text or a shell's heredoc
F2 = ["bash -c \"$(true)make check\"", "sh <<EOF\n$(true)make check\nEOF",
      "sh -c \"x=\\$($(true)make check)\"", "bash -c \"bash -c '$(true)make check'\"",
      "bash -c \"make$(true) check\"", "bash -c \"`true`make check\"",
      "sh -c \"ma$(true)ke check\"", "sh <<EOF\n`true`make check\nEOF"]
# R1-F3: `$((` whose closing parens are apart is a substitution holding a subshell
F3 = ["$((make check) )", "echo $((make check) )", "x=$((make check) )",
      "echo \"$((make check) )\""]
# R1-F7: a script fed on standard input by a here-string, or through a pipe from one
F7 = [". /dev/stdin <<< 'make check'", "source /dev/stdin <<< 'make check'",
      "bash /dev/stdin <<< 'make check'", "timeout 5 sh <<< 'make check'",
      "echo 'make check' | timeout 5 sh", "cat <<< 'make check' | sh"]
# R1-F5, R1-F6: a brace group in the command word, an alias defined and used on one line
F5 = ["{make,} check", "{ma,}ke check", "ma{k,}e check"]
F6 = ["shopt -s expand_aliases\nalias m='make check'\nm"]
BASH_ONLY = {"{make,} check", "{ma,}ke check", F6[0],
             "echo 'm\\ake check' | sh"}    # zsh's echo reads `\a` as a bell
# N1 (ii): data sinks, which read a body and run nothing
SINKS = ["cat > notes.md <<'EOF'\nRun make check before landing.\nEOF",
         "cat >> notes.md <<'EOF'\nSee the `make` target.\nEOF",
         "cat > notes.md <<EOF\n# make notes\nEOF", "tee notes.md <<'EOF'\nUse `make check` here.\nEOF",
         "git commit -F - <<'EOF'\ndocs: say \"make check\" in the runbook\nEOF",
         "cat > a.md <<'EOF'\nmake a\nEOF\ncat > b.md <<'EOF'\nmake b\nEOF"]
NOT_SINKS = ["cat <<'EOF'\nmake x\nEOF", "cat > x.sh <<'EOF'\nmake check\nEOF\nsh x.sh",
             "cd d && cat > f.md <<'EOF'\nmake x\nEOF", "cat > f <<EOF\n$(make check)\nEOF",
             "python3 - <<'EOF'\nprint('we make it')\nEOF", "tee >(sh) <<'EOF'\nmake check\nEOF",
             "cat > f <<'EOF' | sh\nmake check\nEOF", "sudo cat > f <<'EOF'\nmake x\nEOF"]


def _box12(tmp_path):
    stubs = tmp_path / "bin"
    stubs.mkdir()
    for name in ("make", "gmake", "gnumake", "git"):
        (stubs / name).write_text('#!/bin/sh\necho "%s $*" >> "$STUBLOG"\n' % name)
    (stubs / "timeout").write_text('#!/bin/sh\nshift\nexec "$@"\n')
    (stubs / "runner").write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ] && [ "$1" != "--" ]; do '
                                  'shift; done\nshift\nexec "$@"\n')
    for p in stubs.iterdir():
        p.chmod(0o755)
    return stubs


def _ran(tmp_path, stubs, line):
    """{shell: the stubs' calls} for bash -c and zsh -fc, each in a fresh folder."""
    got = {}
    for shell, flag in (("/bin/bash", "-c"), ("/bin/zsh", "-fc")):
        if not os.path.exists(shell):
            continue
        work = Path(tempfile.mkdtemp(dir=str(tmp_path)))
        log = work / ".log"
        log.write_text("")
        try:
            subprocess.run([shell, flag, line], cwd=str(work), capture_output=True, timeout=10,
                           stdin=subprocess.DEVNULL, env={"PATH": "%s:/usr/bin:/bin" % stubs,
                                                          "HOME": str(work), "STUBLOG": str(log)})
        except subprocess.TimeoutExpired:
            pass
        got[os.path.basename(shell)] = log.read_text().splitlines()
    return got


ALL12 = F1 + F2 + F3 + F7 + F5 + F6


@pytest.mark.parametrize("line", ALL12, ids=[str(i) for i in range(len(ALL12))])
def test_12_the_shells_run_it_and_the_rule_refuses(line, tmp_path):
    got = _ran(tmp_path, _box12(tmp_path), line)
    want = {"bash"} if line in BASH_ONLY else {"bash", "zsh"}
    for sh in want & set(got):
        assert any(c.startswith("make ") for c in got[sh]), (sh, line, got)
    assert unattended.unbounded(line), line


def test_12_glue_at_level_one_names_the_command():
    for line in F2[:2] + F2[4:]:
        names = [c.name for c in _read(line)[0]]
        assert "make" in names and not [n for n in names if "__g8" in n], (line, names)
    cmds = _read("bash -c \"$(true)git push\"")[0]
    assert [(c.name, c.args, c.level) for c in cmds if c.name == "git"] == [("git", ["push"], 1)]
    gated = HERE + "/CLAUDE.md"
    for line in ("bash -c \"$(true)cp a CLAUDE.md\"", "$((cp a CLAUDE.md) )",
                 "echo \"$((cp a CLAUDE.md) )\""):
        assert gated in [p for _, p in shellreader.bash_targets(line, HERE, ENV)], line


def test_12_arithmetic_only_where_the_shells_read_it():
    assert ("git", ["push"]) in [c[:2] for c in _read("$((git push) )")[0]]
    for line in ("echo $((1+2))", "echo $(( (1+2) * 3 ))", "x=$((y))"):
        assert [c.name for c in _read(line)[0]] in (["echo"], [""]), line
    assert [c.name for c in _read("echo $(( $(git push) + 1 ))")[0]] == ["echo", "git"]


def test_12_a_deep_nest_is_bounded(tmp_path):
    from claude_session import instructionguard as ig
    nests = ["echo " + "$(( " * 1000 + "1" + " ))" * 1000 + "; {X}",
             "echo " + "$(" * 1000 + "true" + ")" * 1000 + "; {X}",
             "(" * 1000 + "{X}" + ")" * 1000, "{ " * 1000 + "{X}; " + "} " * 1000,
             "echo " + "${x:-" * 1000 + "a" + "}" * 1000 + "; {X}",
             "if true; then " * 300 + "{X}" + "; fi" * 300]
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (tmp_path / "home").mkdir()
    env = {"HOME": str(tmp_path / "home")}
    for nest in nests:
        assert unattended.unbounded(nest.replace("{X}", MK)), nest[:40]
        line = nest.replace("{X}", "cp a " + ig.REPO_LIST)
        for f in (lambda: _read(nest.replace("{X}", MK)),
                  lambda: shellreader._strict(line, str(repo), env, 0, False, True, set())):
            try:
                f()
            except shellreader._Bound:
                pass
        out = ig.check({"tool_name": "Bash", "tool_input": {"command": line}, "cwd": str(repo)},
                       env)
        assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny", nest[:40]


def test_12_a_here_string_is_data():
    assert Unread("data", "make check") in _read("timeout 5 sh <<< 'make check'")[1]
    assert _read("cat <<< 'make check' | sh")[1] == [Unread("data", "make check"),
                                                    Unread("piped", "cat make check")]
    assert _read("bash <<< 'git add -A'")[1] == [Unread("piped", "git add -A")]
    assert unattended.unbounded("grep -c x <<< 'a b'") == ""


@pytest.mark.parametrize("line", SINKS, ids=[str(i) for i in range(len(SINKS))])
def test_12_a_data_sink_passes(line, tmp_path):
    got = _ran(tmp_path, _box12(tmp_path), line)
    assert not [c for cs in got.values() for c in cs if c.startswith("make")], (line, got)
    assert unattended.unbounded(line) == "", line


@pytest.mark.parametrize("line", NOT_SINKS, ids=[str(i) for i in range(len(NOT_SINKS))])
def test_12_any_other_command_keeps_the_refusal(line):
    assert unattended.unbounded(line), line


def test_12_the_body_refusal_says_what_is_true():
    why = unattended.unbounded("python3 - <<'EOF'\nprint('we make it')\nEOF")
    assert not why.startswith("it runs") and "could not rule out" in why, why
    assert "editor tool" in why and "keep the word out of the line" in why, why
    assert unattended.unbounded("timeout 5 sh -c 'm\\ake check'").startswith(
        "it runs `make` in a text the reader does not read (runner)")
