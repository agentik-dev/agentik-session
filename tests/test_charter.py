"""charter.py and `agentik session charter`: the shape of D10, open, close."""
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from claude_session import charter, cli, config

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "charters"
SECTION = {"ceilings": {"context": 180000, "turns": 400}, "window": 200000,
           "checkpoint_at": 0.8, "charter": {"dir": "history/sittings"}}


def _doclint():
    loader = importlib.machinery.SourceFileLoader("doclint", str(ROOT / "scripts" / "doclint"))
    spec = importlib.util.spec_from_loader("doclint", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(list(argv))
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    return rc, out.getvalue(), err.getvalue()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_CONFIG", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_PROFILE", raising=False)


@pytest.mark.parametrize("name, part", [
    ("missing-handover", "part 4 (## Handover) is missing"),
    ("over-ceiling", "over the 4096-byte ceiling"),
    ("no-pin-row", "missing its 'pin' row"),
    ("at-ceiling", "the 4096-byte ceiling"),
])
def test_each_refusal_names_its_part(name, part):
    refusals = charter.check(FIX / f"{name}.md")
    assert len(refusals) == 1 and part in refusals[0]
    rc, _, err = run("charter", "check", str(FIX / f"{name}.md"))
    assert rc == 2 and part in err


def test_boundary_4096_refused_by_both():
    """ADV6-9: exactly 4,096 bytes is refused by charter.py as by doclint (`>=`)."""
    raw = (FIX / "at-ceiling.md").read_bytes()
    assert len(raw) == charter.CEILING == _doclint().CHARTER_CEILING == 4096
    assert [r for r in charter.check_text(raw) if "ceiling" in r]
    assert charter.check_text(raw[:-2] + b"\n") == []  # 4,095 bytes pass


def test_close_refuses_to_write_the_boundary(tmp_path):
    """close never writes a charter of exactly 4,096 bytes: the file stays as it was."""
    d = tmp_path / "history" / "sittings"
    p = charter.open(d, "g", SECTION, "abc1234", repo="r")
    before = p.read_bytes()
    exit_text = "x"
    probe = tmp_path / "probe.md"
    probe.write_bytes(before)
    charter.close(probe, exit_text, None)
    grow = 4096 - len(probe.read_bytes())
    p.write_bytes(before.replace(b"## Next act\n", b"## Next act\n" + b"y" * (grow - 1) + b"\n"))
    padded = p.read_bytes()
    with pytest.raises(charter.CharterError):
        charter.close(p, exit_text, None)
    assert p.read_bytes() == padded


def test_missing_title_and_table_are_refused():
    r = charter.check_text(b"## Done-ness\n## Handover\n## Next act\n")
    assert any("part 1" in x for x in r) and any("part 2 (the table) is missing" in x for x in r)


def test_parity_with_doclint_over_fixtures(tmp_path):
    """charter check and doclint agree, over fixtures in a temp tree only (ADV6-7): never
    the live history/sittings/, whose open charters would make the suite a function of
    what a sitting left untracked."""
    dl = _doclint()
    d = tmp_path / "history" / "sittings"
    good = [charter.open(d, "g", SECTION, "abc1234", repo="r"),
            charter.open(d, "h", SECTION, None, repo="r", row="s7")]
    charter.close(good[0], "goal met", {"context": 61234, "turns": 15})
    bad = []
    for p in sorted(FIX.glob("*.md")):
        bad.append(d / f"2000-01-01-{len(bad) + 1}.md")
        bad[-1].write_bytes(p.read_bytes())
    for p in good + bad:
        rel = str(p.relative_to(tmp_path))
        assert bool(dl.check_charters(str(tmp_path), [rel])) == bool(charter.check(p)), p.name
    assert [p for p in good if charter.check(p)] == []
    assert all(charter.check(p) for p in bad)


def test_parity_with_doclint_on_the_fixtures():
    """Every fixture refused by one is refused by the other."""
    dl = _doclint()
    for p in FIX.glob("*.md"):
        text = p.read_bytes()
        assert charter.check_text(text), p.name
        assert dl.CHARTER_TITLE.match(text.decode().splitlines()[0]), p.name


def test_check_usage_and_unreadable():
    assert run("charter", "check")[0] == 1
    assert run("charter", "check", "/nonexistent/x.md")[0] == 1


def test_open_then_check_passes(tmp_path):
    p = charter.open(tmp_path, "a goal | with a pipe", SECTION, "abc1234", repo="r")
    assert p.name == f"{charter.today()}-1.md"
    assert charter.check(p) == []
    text = p.read_text()
    assert "| pin | abc1234 |" in text and "| agents | 0 |" in text
    assert "400 turns, 180k context" in text and "| window | 200k |" in text
    assert "## Done-ness\n- [x] charter written at open: this file" in text
    assert _doclint().CHARTER_TITLE.match(text.splitlines()[0])
    assert charter.open(tmp_path, "again", SECTION, None, repo="r").name == f"{charter.today()}-2.md"


def test_open_numbers_past_todays_highest(tmp_path):
    (tmp_path / f"{charter.today()}-7.md").write_text("x")
    (tmp_path / "2000-01-01-9.md").write_text("x")
    assert charter.open(tmp_path, "g", SECTION, "h").name == f"{charter.today()}-8.md"


def test_open_names_the_relay_row(tmp_path):
    (tmp_path / f"{charter.today()}-2-s6.md").write_text("x")
    p = charter.open(tmp_path, "g", SECTION, "h", repo="r", row="s7")
    assert p.name == f"{charter.today()}-3-s7.md"
    assert p.read_text().startswith(f"# Sitting {charter.today()}-3: r, g")
    assert charter.newest_today(tmp_path) == p
    assert charter.check(p) == []


def _whole_words_marked(clip, text, limit):
    """`clip` is `text` cut after a whole word, marked with "…", within `limit`."""
    stem = clip[:-1]
    return (clip.endswith("…") and len(clip) <= limit and text.startswith(stem)
            and text[len(stem)] == " ")


def test_open_clips_the_goal_at_a_word_boundary(tmp_path):
    goal = " ".join(f"word{i:05d}x" for i in range(40))   # 10-char words: 60 and 300 fall mid-word
    assert goal[59] != " " and goal[60] != " " and goal[299] != " " and goal[300] != " "
    text = charter.open(tmp_path, goal, SECTION, "h", repo="r").read_text()
    title = text.splitlines()[0].split(": r, ", 1)[1]
    row = next(l for l in text.splitlines() if l.startswith("| goal | "))[len("| goal | "):-len(" |")]
    assert _whole_words_marked(title, goal, 60), title
    assert _whole_words_marked(row, goal, 300), row


def test_one_line_clips_whole_words_and_marks_the_cut():
    assert charter._one_line("  short   goal | here ", 60) == "short goal / here"
    assert charter._one_line("x" * 60, 60) == "x" * 60                 # at the limit: unchanged
    assert charter._one_line("x" * 61, 60) == "x" * 59 + "…"           # no space: the hard cut
    assert charter._one_line("ab " + "x" * 70, 60) == "ab…"
    assert charter._one_line("abc defg", 7) == "abc…"
    assert charter._one_line("abc def gh", 8) == "abc def…"


def test_open_ignores_a_row_outside_the_name_charset(tmp_path):
    assert charter.open(tmp_path, "g", SECTION, "h", row="../x").name == f"{charter.today()}-1.md"


def test_cli_open_reads_relay_row(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_ROW", "s7")
    rc, out, _ = run("charter", "open", "--dir", str(tmp_path), "probe")
    assert rc == 0 and out.strip().endswith(f"{charter.today()}-1-s7.md")


def test_s33_open_records_its_file_in_the_session_dir(tmp_path, monkeypatch):
    """S33 ruling 2: `charter open` writes `sessions/<sid>/charter.json` {path}, the file's
    absolute path, which the hook names under a launcher, only when the file's directory is
    `<request.json's cwd>/<charter dir>` (R1); without a session dir, a recorded cwd, that
    directory, or in a helper, it writes nothing and still succeeds."""
    from claude_session import hooks, resolver
    monkeypatch.delenv("CLAUDE_SESSION_HELPER", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s33-sess")
    monkeypatch.chdir(tmp_path)
    sdir = resolver.session_dir(resolver.state_dir(os.environ), "s33-sess")
    rec = sdir / hooks.CHARTER_REC
    assert run("charter", "open", "probe")[0] == 0 and not sdir.exists()
    sdir.mkdir(parents=True)
    assert run("charter", "open", "probe")[0] == 0 and not rec.exists()      # no request.json
    resolver.save_request(sdir, tmp_path, None, None)
    assert run("charter", "open", "--dir", "b", "probe")[0] == 0 and not rec.exists()
    rc, out, _ = run("charter", "open", "probe")
    got = json.loads(rec.read_text())
    assert rc == 0 and got == {"path": str(tmp_path / out.strip())}
    assert Path(got["path"]).is_absolute() and Path(got["path"]).is_file()
    monkeypatch.setenv("CLAUDE_SESSION_HELPER", "1")
    assert run("charter", "open", "probe")[0] == 0
    assert json.loads(rec.read_text()) == got


def test_close_appends_one_line(tmp_path):
    p = charter.open(tmp_path, "g", SECTION, "h", repo="r")
    charter.close(p, "goal met", {"context": 61234, "turns": 15})
    text = p.read_text()
    assert text.count("exit taken") == 1
    # S21 (the observer's ruling N6): SECTION names no priority key, so priority is on and
    # `open` seeds the Handover's open-by-level line above the exit line
    assert ("## Handover\n- open by level: none yet\n- exit taken: goal met; about 61k context, "
            "15 turns\n\n## Next act") in text
    assert charter.check(p) == []
    charter.close(p, "again", None)
    assert p.read_text().splitlines().count("- exit taken: again; meter unknown") == 1
    assert p.read_text().index("again") < p.read_text().index("## Next act")


def test_close_refuses_a_broken_charter(tmp_path):
    p = tmp_path / "broken.md"
    before = (FIX / "missing-handover.md").read_bytes()
    p.write_bytes(before)
    with pytest.raises(charter.CharterError, match="Handover"):
        charter.close(p, "x", None)
    assert p.read_bytes() == before
    rc, _, err = run("charter", "close", str(p))
    assert rc == 2 and "Handover" in err


def test_close_refuses_past_the_ceiling(tmp_path):
    p = charter.open(tmp_path, "g", SECTION, "h", repo="r")
    pad = charter.CEILING - p.stat().st_size - 5
    p.write_text(p.read_text().replace("## Handover\n", "## Handover\n" + "x" * pad + "\n"))
    assert charter.check(p) == []
    with pytest.raises(charter.CharterError, match="ceiling"):
        charter.close(p, "goal met", None)


def test_cli_open_close_in_a_repo(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    monkeypatch.chdir(tmp_path)
    rc, out, _ = run("charter", "open", "a goal")
    assert rc == 0
    path = Path(out.strip())
    assert path.parent == Path("history/sittings")
    assert run("charter", "close", "--exit", "goal met")[0] == 0
    assert "- exit taken: goal met; meter unknown" in path.read_text()
    assert run("charter", "check", str(path))[0] == 0
    assert run("charter", "open")[0] == 1
    assert run("charter", "close", "--dir", "elsewhere")[0] == 2


# ---- S19: the Next act's first line and the RESPAWN pattern (respawn-r1 §3.2) ----

S19_TOP = "# Sitting 2026-10-10-1: r, c\n\n## Done-ness\n- [x] a\n\n"
# Criterion 3's eight Next acts, then a bare RESPAWN: (the section and below, accepted).
S19_NEXT = [
    ("## Next act\nRESPAWN: x\n", True),
    ("## Next act\nRESPAWN. x\n", True),
    ("## Next act\n\nRESPAWN at 80%\n", True),
    ("## Next act\nRespawn: x\n", False),
    ("## Next act\nRESPAWNED\n", False),
    ("## Next act\nNext: RESPAWN\n", False),
    ("## Next act\n\n## Later\nRESPAWN: x\n", False),          # an empty Next act
    ("## Handover\nRESPAWN: x\n", False),                      # no `## Next act`
    ("## Next act\nRESPAWN\n", True),
]


@pytest.mark.parametrize("tail,ok", S19_NEXT,
                         ids=["colon", "dot", "at-80", "Respawn", "RESPAWNED", "later-in-line",
                              "empty", "no-next-act", "bare"])
def test_s19_next_act_respawn_spellings(tail, ok):
    line = charter.next_act_line(S19_TOP + tail)
    assert bool(line is not None and charter.RESPAWN.match(line)) is ok
    if ok:
        assert line.startswith("RESPAWN") and line == line.rstrip()


# ---- S21: the Handover's open-by-level line and WAITING ---------------------

S21_HEAD = ("# Sitting 2026-10-10-4: r, c\n\n| item | value |\n|---|---|\n| goal | g |\n"
            "| budget | b |\n| pin | p |\n| window | 200k |\n| agents | 0 |\n\n"
            "## Done-ness\n- [x] a\n\n")
S21_LISTED = "## Handover\n- open by level: S2 the remedy; S4 a note\n\n"
S21_OFF = "session:\n  priority: {enabled: false}\n  pacing: {enabled: false}\n"
S40_NONE = "## While waiting\n- none\n\n"


def _s21_repo(tmp_path, monkeypatch, config=None):
    from claude_session import resolver
    d = tmp_path / resolver.REPO_DIR
    d.mkdir(parents=True, exist_ok=True)
    if config is not None:
        (d / "config.yaml").write_text(config)
    monkeypatch.chdir(tmp_path)


def _s21_charter(tmp_path, handover=S21_LISTED, next_act="the next act", waiting=S40_NONE):
    p = tmp_path / "c.md"
    p.write_text(S21_HEAD + handover + waiting + "## Next act\n" + next_act + "\n")
    assert charter.check(p) == []
    return p


def test_s21_open_seeds_the_handover_line(tmp_path):
    p = charter.open(tmp_path, "g", SECTION, "h", repo="r")          # N6: no key is on
    assert "## Handover\n- open by level: none yet\n\n## Next act" in p.read_text()
    assert charter.check(p) == [] and charter.warnings(p.read_bytes(), SECTION) == []


def test_s21_open_seeds_nothing_with_priority_off(tmp_path):
    on = charter.open(tmp_path, "g", {**SECTION, "priority": {"enabled": True}}, "h", repo="r")
    assert "## Handover\n- open by level: none yet\n" in on.read_text()     # the control
    p = charter.open(tmp_path, "g", {**SECTION, "priority": {"enabled": False}}, "h", repo="r")
    assert "## Handover\n\n## Next act" in p.read_text() and "open by level" not in p.read_text()


@pytest.mark.parametrize("handover,next_act,config,want", [
    ("## Handover\n- h\n\n", "the next act", None, "open by level"),
    (S21_LISTED, "WAITING: the owner", None, "WAITING <n>: <what>; <how to tell>"),
    (S21_LISTED, "WAITING 3: the owner's word; a reply in OPEN-QUESTIONS.md", None,
     "session.pacing.waiting"),
    ("## Handover\n- h\n\n", "WAITING", S21_OFF, None),
], ids=["no-line", "misshapen", "at-the-stop", "off"])
def test_s21_check_warns(tmp_path, monkeypatch, handover, next_act, config, want):
    _s21_repo(tmp_path, monkeypatch)
    ok = _s21_charter(tmp_path, next_act="WAITING 2: the owner's word; a reply lands")
    assert run("charter", "check", str(ok)) == (0, "", "")             # the control
    p = _s21_charter(tmp_path, handover, next_act)
    assert "warning" in run("charter", "check", str(p))[2]             # on by default
    _s21_repo(tmp_path, monkeypatch, config)
    rc, out, err = run("charter", "check", str(p))
    assert rc == 0 and out == ""
    if want is None:
        assert err == ""
    else:
        assert err.count("\n") == 1 and "warning" in err and want in err


def test_s21_close_warns(tmp_path, monkeypatch):
    _s21_repo(tmp_path, monkeypatch)
    p = _s21_charter(tmp_path, "## Handover\n- h\n\n", "WAITING 4: x; y")
    rc, out, err = run("charter", "close", "--exit", "goal met", str(p))
    assert rc == 0 and out.strip() == str(p) and "- exit taken: goal met" in p.read_text()
    assert err.count("warning") == 2 and "open by level" in err and "WAITING 4" in err


def test_s21_bad_resolve_warns_nothing(tmp_path, monkeypatch):
    _s21_repo(tmp_path, monkeypatch, "session:\n  pacing: {waiting: 2}\n")
    p = _s21_charter(tmp_path, "## Handover\n- h\n\n", "WAITING 2: x; y")
    rc, _, err = run("charter", "check", str(p))
    assert rc == 0 and err.count("warning") == 2                        # the control
    _s21_repo(tmp_path, monkeypatch, "session: {posture: loud}\n")
    assert run("charter", "check", str(p)) == (0, "", "")


@pytest.mark.parametrize("user,repo", [
    ("defaults: [1]\n", None),                    # AttributeError in the merge
    ("profiles:\n  frontier: 5\n", None),         # AttributeError on a scalar profile
    (None, "session:\n  profile: [a]\n"),         # TypeError: a list is no profile name
], ids=["user-defaults-list", "user-profile-scalar", "repo-profile-list"])
@pytest.mark.parametrize("verb", ["check", "close"])
def test_s21_malformed_layer_warns_nothing(tmp_path, monkeypatch, user, repo, verb):
    """Round one F1: a layer of the wrong shape fails the resolve outside ResolveError;
    check and close keep their exit and warn nothing, and close prints its path."""
    import os

    from claude_session import resolver
    _s21_repo(tmp_path, monkeypatch)
    p = _s21_charter(tmp_path, "## Handover\n- h\n\n", "WAITING 2: x; y")
    assert run("charter", "check", str(p))[2].count("warning") == 1     # the control
    if user is not None:
        u = resolver._user_file(os.environ)
        u.parent.mkdir(parents=True, exist_ok=True)
        u.write_text(user)
    _s21_repo(tmp_path, monkeypatch, repo)
    if verb == "check":
        assert run("charter", "check", str(p)) == (0, "", "")
        return
    rc, out, err = run("charter", "close", "--exit", "goal met", str(p))
    assert (rc, out.strip(), err) == (0, str(p), "")
    assert p.read_text().count("- exit taken: goal met") == 1


@pytest.mark.parametrize("line,want", [
    ("WAITING 1: the owner's answer; a line in OPEN-QUESTIONS.md", 1),
    ("WAITING 12: CI; the run's status", 12),
    ("WAITING 3: no how-to-tell", 0),
], ids=["one", "twelve", "misshapen"])
def test_s21_waiting(line, want):
    assert charter.waiting(line) == want
    for bad in ("WAITING", "WAITING: x; y", "WAITING 0: x; y", "WAITING x: y; z",
                "WAITING 2: ; y", "WAITING 2: x; "):
        assert charter.waiting(bad) == 0, bad
    for other in ("RESPAWN: x", "the next act", "WAITINGS 2: x; y", "waiting 2: x; y"):
        assert charter.waiting(other) is None, other


# ---- S29: a wait on the usage meter is not WAITING ---------------------------

S29_METER = ("a wait on the usage meter is not WAITING (session.pacing): keep the act as the "
             "Next act and wake at the band's reset")
S29_STOP = "never stops the loop"


def _s29_warns(next_act, session=SECTION, waiting=S40_NONE):
    raw = (S21_HEAD + S21_LISTED + waiting + "## Next act\n" + next_act + "\n").encode()
    return charter.warnings(raw, session)


@pytest.mark.parametrize("what", [
    "room for 0 on the band", "the usage meter", "a Usage Limit hit", "the five-hour band",
    "the 5h band", "ROOM FOR 0", "the meter's reset",
], ids=["room-for", "meter", "usage-limit", "five-hour", "5h", "upper", "meter-s"])
@pytest.mark.parametrize("n", [1, 3, 9])
def test_s29_meter_wait_warns_at_any_n(what, n):
    """Ruling 3: one line at any n; ruling 1: it never counts toward n (S36)."""
    assert _s29_warns(f"WAITING {n}: {what}; band.json's resetsAt") == [S29_METER]


@pytest.mark.parametrize("next_act,want", [
    ("WAITING 1: the owner's word; a reply in OPEN-QUESTIONS.md", []),
    ("WAITING 3: CI; the run's status", [S29_STOP]),
    ("WAITING 2: the parameter sweep; its log", []),         # a word that only holds "meter"
    ("WAITING: room for 0", ["WAITING <n>: <what>; <how to tell>"]),    # misshapen, not named
    ("WAITING 2: CI; the meter shows room", []),             # the meter in <how to tell> only
    ("the next act names the meter", []),
], ids=["owner", "ci-at-the-stop", "parameter", "misshapen", "how-to-tell", "no-waiting"])
def test_s29_other_waiting_gets_no_meter_line(next_act, want):
    assert _s29_warns("WAITING 1: room for 0; band.json's resetsAt") == [S29_METER]  # control
    got = _s29_warns(next_act)
    assert len(got) == len(want) and all(w in g for w, g in zip(want, got)), got
    assert S29_METER not in got


def test_s29_meter_line_only_with_pacing_on():
    line = "WAITING 3: room for 0; band.json's resetsAt"
    assert _s29_warns(line) == [S29_METER]                                 # the control
    assert _s29_warns(line, {**SECTION, "pacing": {"enabled": False}}) == []
    assert _s29_warns(line, {**SECTION, "pacing": {"waiting": 1}}) == [S29_METER]


@pytest.mark.parametrize("verb", ["check", "close"])
def test_s29_meter_wait_keeps_the_exit(tmp_path, monkeypatch, verb):
    _s21_repo(tmp_path, monkeypatch)
    p = _s21_charter(tmp_path, next_act="WAITING 4: room for 0; band.json's resetsAt")
    argv = ("charter", "check", str(p)) if verb == "check" else (
        "charter", "close", "--exit", "goal met", str(p))
    rc, out, err = run(*argv)
    assert rc == 0 and err.count("\n") == 1 and "warning" in err and S29_METER in err
    assert S29_STOP not in err
    assert out == "" if verb == "check" else out.strip() == str(p)


# ---- S22: close names its commit, and the respawn that follows (F13) --------

def _s22_next(rel):
    """close's `next:` line for a plain path (the fix round: F1 and F2)."""
    import os
    d, name = os.path.split(os.path.abspath(rel))
    return (f"next: git -C {d} add -- {name} && "
            f'git -C {d} commit -m "charter: the exit taken" -- {name}')
S22_THEN = "then: agentik-session checkpoint --respawn --charter "
S22_NEXT = [("RESPAWN: the next act", True), ("The coordinator: review and merge", False)]


def _s22_charter(p, next_act):
    p.write_text(S21_HEAD + "## Handover\n- open by level: none yet\n\n## Next act\n"
                 + next_act + "\n")
    assert charter.check(p) == []
    return p


def test_s22_close_names_the_commit(tmp_path, monkeypatch):
    """In a work tree, close prints its path, then the commit that takes the exit line,
    then (on a RESPAWN Next act only) the checkpoint that marks the respawn."""
    import os
    repo = tmp_path / "repo"
    (repo / "history" / "sittings").mkdir(parents=True)
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                  capture_output=True, text=True).stdout
    g("init", "-q"); g("config", "user.email", "t@" + "e.com"); g("config", "user.name", "T")
    monkeypatch.chdir(repo)
    for i, (next_act, then) in enumerate(S22_NEXT):
        rel = "history/sittings/2026-10-12-%d-s22.md" % (i + 1)
        _s22_charter(repo / rel, next_act)
        g("add", rel); g("commit", "-q", "-m", "charter " + rel)
        rc, out, err = run("charter", "close", "--exit", "RESPAWN", rel)
        assert rc == 0, err
        want = [rel, _s22_next(rel)]
        if then:
            want.append(S22_THEN + os.path.abspath(rel))
        assert out.splitlines() == want
        assert g("status", "--porcelain", "--", rel).startswith(" M ")
        g("commit", "-q", "-m", "charter: the exit taken", "--", rel)    # the line it names


def test_s22_close_outside_a_tree(tmp_path, monkeypatch):
    """Outside a work tree there is no commit to name; a RESPAWN close still names its
    checkpoint, by the charter's absolute path."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    for i, (next_act, then) in enumerate(S22_NEXT):
        p = _s22_charter(tmp_path / ("c%d.md" % i), next_act)
        rc, out, err = run("charter", "close", "--exit", "RESPAWN", p.name)
        assert rc == 0, err
        assert out.splitlines() == [p.name] + ([S22_THEN + str(p.resolve())] if then else [])
        assert "next:" not in out + err



def _s22_init(repo):
    repo.mkdir(parents=True)
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True,
                                  capture_output=True, text=True).stdout
    g("init", "-q"); g("config", "user.email", "t@" + "e.com"); g("config", "user.name", "T")
    g("commit", "-q", "--allow-empty", "-m", "init")
    return g


def _s22_run_next(out, cwd):
    """Run close's `next:` line verbatim through a shell, in the cwd close ran in."""
    lines = [l[len("next: "):] for l in out.splitlines() if l.startswith("next: ")]
    assert len(lines) == 1, out
    r = subprocess.run(["sh", "-c", lines[0]], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_s22_next_line_runs_for_an_untracked_charter(tmp_path, monkeypatch):
    """F1: a charter git has never seen; the printed line adds it, then commits it."""
    repo = tmp_path / "A"
    g = _s22_init(repo)
    rel = "history/sittings/c3.md"
    (repo / "history" / "sittings").mkdir(parents=True)
    _s22_charter(repo / rel, "RESPAWN: y")
    monkeypatch.chdir(repo)
    rc, out, err = run("charter", "close", "--exit", "RESPAWN", rel)
    assert rc == 0, err
    _s22_run_next(out, repo)
    assert g("status", "--porcelain") == ""
    assert g("log", "-1", "--format=%s").strip() == "charter: the exit taken"


def test_s22_next_line_runs_from_a_second_repo(tmp_path, monkeypatch):
    """F2: the cwd lies in repo B, the charter (in a directory with a space) in repo A."""
    a, b = tmp_path / "A", tmp_path / "B"
    ga, gb = _s22_init(a), _s22_init(b)
    (a / "dir with space").mkdir()
    (b / "x").mkdir()
    _s22_charter(a / "dir with space" / "c 1.md", "RESPAWN: x")
    ga("add", "-A"); ga("commit", "-q", "-m", "charter")
    monkeypatch.chdir(b / "x")
    rel = "../../A/dir with space/c 1.md"
    rc, out, err = run("charter", "close", "--exit", "RESPAWN", rel)
    assert rc == 0 and out.splitlines()[0] == rel, err
    _s22_run_next(out, b / "x")
    assert ga("status", "--porcelain") == ""
    assert "- exit taken: RESPAWN" in ga("show", "HEAD:dir with space/c 1.md")
    assert gb("rev-list", "--count", "HEAD").strip() == "1"

def test_s22_docs_say_the_order():
    """Ruling 3: the skill's charter part and the runbook's restart part say the order in
    one sentence (close, commit the charter, then on RESPAWN the checkpoint), and name
    the refusal of a charter not committed."""
    def part(rel, start, end):
        text = (ROOT / rel).read_text()
        i = text.index(start)
        return " ".join(text[i:text.index(end, i)].split())
    for flat in (part("plugin/skills/session/SKILL.md", "## The charter", "## Priority"),
                 part("RUNBOOK.md", "### Restarting a sitting", "`agentik session report")):
        said = [s for s in flat.split(". ") if "commit the charter" in s]
        assert len(said) == 1, said
        s = said[0]
        assert -1 < s.find("close") < s.find("commit the charter") < s.find(
            "checkpoint --respawn"), s
        assert "not committed" in flat


# ---- S36: a wait never stops the loop ---------------------------------------

S36_LINE = ("WAITING {n} is at session.pacing.waiting ({w}) or past it: wake at the cache's "
            "idle limit, bring the charter current and commit it; a wait never stops the loop "
            "or closes the sitting, only the checkpoint does")


@pytest.mark.parametrize("n,w,warned", [(3, 3, True), (9, 3, True), (1, 1, True),
                                        (2, 3, False)], ids=["at", "past", "at-one", "under"])
def test_s36_waiting_at_n_never_stops_the_loop(n, w, warned):
    got = _s29_warns(f"WAITING {n}: CI; the run's status", {**SECTION, "pacing": {"waiting": w}})
    assert got == ([S36_LINE.format(n=n, w=w)] if warned else [])
    assert not any("the loop stops" in g or "close the sitting" in g for g in got)


# ---- S40: the While waiting section, and the red of a WAITING beside it -----

S40_READY = "- ready: r1 (repo, S3)"
S40_OWED = "- owed: the runsheet for r2; a draft, no gate"
S40_OLD = "no While waiting section (opened before alpha.23): add it with - none"


def test_s40_open_writes_the_section(tmp_path):
    p = charter.open(tmp_path, "g", SECTION, "abc1234", repo="r")
    text = p.read_text()
    assert "## Handover\n- open by level: none yet\n\n## While waiting\n- none\n\n## Next act\n" in text
    assert charter.WHILE_WAITING == "## While waiting" and charter.RED == "WAITING while ready"
    assert (5, charter.WHILE_WAITING) in charter.PARTS
    assert [h for _, h in charter.PARTS].index(charter.WHILE_WAITING) == 2
    raw = p.read_bytes()
    assert charter.check_text(raw) == [] and charter.warnings(raw, SECTION) == []
    assert charter.while_waiting(raw) == ["- none"]
    off = charter.open(tmp_path, "g", {**SECTION, "priority": {"enabled": False}}, "h", repo="r")
    assert "## Handover\n\n## While waiting\n- none\n\n## Next act" in off.read_text()


def test_s40_while_waiting_reads_the_section():
    head = (S21_HEAD + S21_LISTED).encode()
    tail = b"## Next act\nthe next act\n"
    assert charter.while_waiting(head + tail) is None
    assert charter.while_waiting(head + S40_NONE.encode() + tail) == ["- none"]
    body = ("## While waiting\n%s\n\n%s  \n\n" % (S40_READY, S40_OWED)).encode()
    assert charter.while_waiting(head + body + tail) == [S40_READY, S40_OWED]
    assert charter.while_waiting(head + b"## While waiting\n\n" + tail) == []


def test_s40_a_charter_before_alpha23_passes_with_one_warning(tmp_path, monkeypatch):
    raw = (S21_HEAD + S21_LISTED + "## Next act\nthe next act\n").encode()
    assert charter.check_text(raw) == []
    assert charter.warnings(raw, SECTION) == [S40_OLD]
    assert charter.warnings(raw, {**SECTION, "pacing": {"enabled": False}}) == []
    _s21_repo(tmp_path, monkeypatch)
    p = _s21_charter(tmp_path, waiting="")
    rc, out, err = run("charter", "check", str(p))
    assert (rc, out) == (0, "") and err.count("\n") == 1 and S40_OLD in err


@pytest.mark.parametrize("lines,want", [
    (["- ready r1"], "- ready r1"),
    (["- ready: r1 (repo)"], "- ready: r1 (repo)"),
    (["- owed: a draft"], "- owed: a draft"),
    (["a line"], "a line"),
    (["- none", S40_READY], "- none"),
    ([S40_READY, "- none"], "- none"),
    ([S40_READY] * 4, "4 ready rows"),
], ids=["no-colon", "no-level", "no-need", "prose", "none-first", "none-after", "four-ready"])
def test_s40_a_line_of_another_shape_warns(lines, want):
    body = "## While waiting\n" + "".join(l + "\n" for l in lines) + "\n"
    got = _s29_warns("the next act", waiting=body)
    assert len(got) == 1 and want in got[0] and charter.RED not in got[0], got
    assert charter.check_text((S21_HEAD + S21_LISTED + body + "## Next act\nx\n").encode()) == []


@pytest.mark.parametrize("lines", [[S40_READY], [S40_READY] * 3, [S40_OWED],
                                   [S40_READY, S40_OWED]], ids=["ready", "three", "owed", "both"])
def test_s40_shapes_without_waiting_warn_nothing(lines):
    body = "## While waiting\n" + "".join(l + "\n" for l in lines) + "\n"
    assert _s29_warns("the next act", waiting=body) == []
    assert _s29_warns("the next act") == []                            # the control


@pytest.mark.parametrize("next_act", [
    "WAITING 1: the owner's word; a reply in OPEN-QUESTIONS.md",
    "WAITING 3: CI; the run's status",
    "WAITING: the owner",
], ids=["one", "at-the-stop", "misshapen"])
@pytest.mark.parametrize("lines,first", [
    ([S40_READY], S40_READY), ([S40_OWED], S40_OWED), ([S40_OWED, S40_READY], S40_OWED),
    (["a line", S40_READY], S40_READY),
], ids=["ready", "owed", "owed-first", "other-then-ready"])
def test_s40_waiting_while_ready_is_red_first(next_act, lines, first):
    body = "## While waiting\n" + "".join(l + "\n" for l in lines) + "\n"
    assert not any(charter.RED in g for g in _s29_warns(next_act))   # the control: - none
    got = _s29_warns(next_act, waiting=body)
    assert got[0] == (f"WAITING while ready: {first}; take it, since WAITING is legal only "
                      "when While waiting reads - none")
    assert sum(charter.RED in g for g in got) == 1


def test_s40_the_meter_wait_stays_exempt():
    body = "## While waiting\n%s\n\n" % S40_READY
    assert _s29_warns("WAITING 2: room for 0; band.json's resetsAt", waiting=body) == [S29_METER]
    assert _s29_warns("WAITING 2: CI; the run's status",
                      {**SECTION, "pacing": {"enabled": False}}, waiting=body) == []


@pytest.mark.parametrize("next_act,want", [
    ("WAITING 1: CI; the run's status", 1), ("the next act", 0),
    ("WAITING 1: room for 0; band.json's resetsAt", 0),
], ids=["red", "no-waiting", "meter"])
def test_s40_check_exits_1_on_the_red(tmp_path, monkeypatch, next_act, want):
    _s21_repo(tmp_path, monkeypatch)
    ok = _s21_charter(tmp_path, next_act=next_act)
    assert run("charter", "check", str(ok))[0] == 0                    # the control: - none
    p = _s21_charter(tmp_path, next_act=next_act, waiting="## While waiting\n%s\n\n" % S40_READY)
    rc, out, err = run("charter", "check", str(p))
    assert (rc, out) == (want, "")
    assert (charter.RED in err) == bool(want)
    bad = tmp_path / "bad.md"
    bad.write_bytes((FIX / "missing-handover.md").read_bytes())
    assert run("charter", "check", str(p), str(bad))[0] == 2           # a refusal wins
    _s21_repo(tmp_path, monkeypatch, S21_OFF)
    assert run("charter", "check", str(p)) == (0, "", "")


def test_s40_close_keeps_its_exit_on_the_red(tmp_path, monkeypatch):
    _s21_repo(tmp_path, monkeypatch)
    p = _s21_charter(tmp_path, next_act="WAITING 1: CI; the run's status",
                     waiting="## While waiting\n%s\n\n" % S40_READY)
    rc, out, err = run("charter", "close", "--exit", "goal met", str(p))
    assert rc == 0 and out.splitlines()[0] == str(p) and charter.RED in err
    assert p.read_text().count("- exit taken: goal met") == 1


def test_s40_docs_say_the_section():
    for rel in ("RUNBOOK.md", "plugin/skills/session/SKILL.md", "README.md",
                "design/readme/source.md"):
        text = (ROOT / rel).read_text()
        assert "While waiting" in text and "- none" in text, rel
    assert "While waiting" in (ROOT / "design" / "overhaul-r1.md").read_text()
