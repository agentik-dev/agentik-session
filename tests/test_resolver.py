"""The layers, their precedence, and the resolved file as a pure function of its inputs."""

import json
import os

import pytest

from claude_session import SEMVER, resolver
from claude_session.resolver import ResolveError, resolve, write

SID = "test-session"


@pytest.fixture
def world(tmp_path):
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state)}

    def put(layer, text):
        path = {"user": home / ".claude/agentik/profiles.yaml",
                "repo": repo / ".claude/agentik/config.yaml",
                "local": repo / ".claude/agentik/config.local.yaml"}[layer]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return env, repo, put


def run(world, **kw):
    env, repo, _ = world
    return resolve(repo, SID, env, **kw)


def test_defaults_alone(world):
    r = run(world)
    s = r.sections["session"]
    assert s["profile"] == "frontier" and s["model"] == "opus"
    assert s["ceilings"] == {"context": 180000, "turns": 400}
    assert s["push"] == "never" and s["device"] == "never"
    assert r.sections["relay"]["enabled"] == "auto"
    assert r.sections["decisions"] == {"dir": "decisions"}
    # agentik-r1 ruling 5: the section is `relay`, with a copy under the old key until r2
    # S38 ruling 4: `gate` joins the sections, empty until a repo layer sets it
    assert list(r.as_dict()) == ["provider", "session", "respeak", "decisions", "relay",
                                 "gate", "agent-relay"]
    assert r.sections["gate"] == {}
    assert r.as_dict()["agent-relay"] == r.sections["relay"] and r.renamed == []
    assert r.provider["version"] == SEMVER and r.provider["plugin"] == "session"


def test_missing_files_are_listed_with_null(world):
    r = run(world)
    hashes = [h for _, h in r.inputs]
    assert r.inputs[0][0] == str(resolver.SHIPPED) and hashes[0] is not None
    assert hashes[1:] == [None, None, None, None]    # user, repo, local, overlay
    assert [i["path"] for i in r.provider["inputs"]] == [p for p, _ in r.inputs]


def test_every_named_profile_resolves(world):
    env, repo, _ = world
    _, profiles = resolver.load_profiles(env)
    assert {"frontier", "balanced", "local", "local-only", "scratch", "review",
            "packets", "builder"} <= set(profiles)
    for name in profiles:
        assert resolve(repo, SID, env, profile=name).sections["session"]["profile"] == name


# (layers present, the effort that wins): each adjacent pair, lowest first.
PRECEDENCE = [
    ({"user": "profiles:\n  frontier:\n    effort: low\n"}, "low"),
    ({"user": "profiles:\n  frontier:\n    effort: low\n", "repo": "session: {effort: medium}\n"}, "medium"),
    ({"repo": "session: {effort: medium}\n", "local": "session: {effort: max}\n"}, "max"),
]


@pytest.mark.parametrize("layers,want", PRECEDENCE)
def test_layer_precedence(world, layers, want):
    for layer, text in layers.items():
        world[2](layer, text)
    assert run(world).sections["session"]["effort"] == want


def test_launch_profile_sits_above_the_repo_files(world):
    world[2]("local", "session: {posture: signal, effort: max}\n")
    s = run(world, profile="builder").sections["session"]
    assert s["posture"] == "deny"                   # the launch profile's own field
    assert s["effort"] == "high"


def test_repo_names_the_profile_and_launch_overrides_it(world):
    world[2]("repo", "session: {profile: balanced}\n")
    assert run(world).sections["session"]["subagents"] == "sonnet"
    assert run(world, profile="review").sections["session"]["profile"] == "review"


def test_overlay_sits_above_the_launch_profile(world):
    s = run(world, profile="builder",
            overlay={"posture": "ask", "subagent_model": "haiku", "_counter": 3}).sections["session"]
    assert s["posture"] == "ask" and s["subagents"] == "haiku"


def test_overlay_file_is_read_and_hashed(world):
    env, repo, _ = world
    p = resolver.state_dir(env) / "overlays" / f"{SID}.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"effort": "low"}))
    r = resolve(repo, SID, env)
    assert r.sections["session"]["effort"] == "low"
    assert dict(r.inputs)[str(p)] is not None


def test_dependent_sections_pass_through_unknown_keys(world):
    world[2]("repo", "respeak: {mode: eli5}\nrelay: {enabled: \"off\"}\n")
    r = run(world)
    assert r.sections["respeak"] == {"narrative": "tech", "mode": "eli5"}
    assert r.sections["relay"]["enabled"] == "off"
    assert r.unknown == []


def test_c6_the_old_relay_key_is_read_and_relay_wins(world):
    # agentik-r1 §6.3 c6 (packet ruling 5): the old key alone is read as `relay`, a warning;
    # with both in one layer `relay` wins, a warning naming the old key.
    env, repo, put = world
    put("repo", 'agent-relay: {enabled: "off", queue: q.yaml}\n')
    r = run(world)
    assert r.sections["relay"] == {"enabled": "off", "queue": "q.yaml",
                                   "merge": "merge-on-green"}
    assert r.as_dict()["agent-relay"] == r.sections["relay"]
    assert r.renamed == ["config.yaml: agent-relay is read as relay; rename the key"]
    put("repo", 'relay: {enabled: "on"}\nagent-relay: {enabled: "off"}\n')
    r = run(world)
    assert r.sections["relay"]["enabled"] == "on" and r.unknown == []
    assert r.renamed == ["config.yaml: agent-relay and relay both set; relay wins, "
                         "remove agent-relay"]
    # the user's profiles.yaml: its old key still overrides the shipped `relay`
    put("repo", "")
    put("user", 'profiles:\n  frontier:\n    agent-relay: {enabled: "off"}\n')
    r = run(world)
    assert r.sections["relay"]["enabled"] == "off"
    assert r.renamed == ["profiles.yaml: frontier: agent-relay is read as relay; rename the key"]


def test_c4_c5_the_old_folders_are_read_until_the_new_exist(tmp_path):
    # agentik-r1 §6.3 c4 c5 (packet ruling 1): the new path when it exists, else the old.
    home, repo = tmp_path / "home", tmp_path / "repo"
    env = {"HOME": str(home), "XDG_STATE_HOME": str(tmp_path / "state")}
    old_repo = repo / ".claude/claude-code-session"
    old_user = home / ".claude/claude-code-session"
    for d in (old_repo, old_user):
        d.mkdir(parents=True)
    (old_repo / "config.yaml").write_text("session: {effort: low}\n")
    (old_user / "profiles.yaml").write_text("profiles:\n  mine: {effort: medium}\n")
    r = resolve(repo, SID, env)
    assert r.sections["session"]["effort"] == "low"
    assert resolver.repo_dir(repo) == old_repo
    assert str(old_user / "profiles.yaml") in dict(r.inputs)
    assert resolve(repo, SID, env, profile="mine").sections["session"]["effort"] == "medium"
    (repo / ".claude/agentik").mkdir()
    (repo / ".claude/agentik/config.yaml").write_text("session: {effort: high}\n")
    assert resolve(repo, SID, env).sections["session"]["effort"] == "high"
    assert resolver.repo_dir(repo) == repo / ".claude/agentik"


def test_unknown_keys_are_reported_and_ignored(world):
    world[2]("repo", "session: {colour: blue}\nstranger: {a: 1}\n")
    r = run(world)
    assert "colour" not in r.sections["session"]
    assert r.unknown == ["config.yaml: session.colour", "config.yaml: stranger"]


@pytest.mark.parametrize("layer,text,msg", [
    ("repo", "session: {profile: nope}\n", "unknown profile"),
    ("repo", "session: {posture: loud}\n", "posture"),
    ("local", "session: {ceilings: {context: 0}}\n", "nested flow"),
    ("repo", "session:\n  ceilings: {context: -1}\n", "ceilings.context"),
    ("repo", "session: {checkpoint_at: 2}\n", "checkpoint_at"),
    ("repo", "session: [a]\n", "must be a mapping"),
    ("user", "a: &x 1\n", "anchor"),
])
def test_refusals(world, layer, text, msg):
    world[2](layer, text)
    with pytest.raises(ResolveError, match=msg):
        run(world)


def test_bad_session_id():
    with pytest.raises(ResolveError):
        resolve("/", "../escape", {"HOME": "/nonexistent"})


def test_write_is_byte_stable_and_inputs_track_changes(world, tmp_path):
    env, repo, put = world
    t = tmp_path / "transcript.jsonl"
    t.write_text("{}\n")
    os.utime(t, (1_700_000_000, 1_700_000_000))
    state = resolver.state_dir(env)
    path = write(run(world, transcript_path=t), state)
    first = path.read_bytes()
    assert write(run(world, transcript_path=t), state).read_bytes() == first
    doc = json.loads(first)
    assert doc["provider"]["resolved_at"] == "2023-11-14T22:13:20+00:00"
    assert (path.parent / "resolved.yaml").read_text().startswith("provider:\n  plugin: session\n")

    put("repo", "session: {effort: high}\n")
    doc2 = json.loads(write(run(world, transcript_path=t), state).read_bytes())
    h1 = {i["path"]: i["sha256"] for i in doc["provider"]["inputs"]}
    h2 = {i["path"]: i["sha256"] for i in doc2["provider"]["inputs"]}
    changed = [p for p in h1 if h1[p] != h2[p]]
    assert len(changed) == 1 and changed[0].endswith("config.yaml")


def test_yaml_twin_parses_back_to_the_json(world):
    from claude_session.yamlsubset import load
    env, _, _ = world
    path = write(run(world, profile="review"), resolver.state_dir(env))
    assert load((path.parent / "resolved.yaml").read_text()) == json.loads(path.read_text())


def test_newest_session(world):
    env, _, _ = world
    state = resolver.state_dir(env)
    assert resolver.newest_session(state) is None
    write(run(world), state)
    assert resolver.newest_session(state) == SID


# ---- S19: the respawn key (respawn-r1 §4) ----------------------------------

def test_s19_respawn_defaults(world):
    from claude_session import sessionconfig
    assert run(world).sections["session"]["respawn"] == {"cap": 20, "floor": 600, "settle": 60}
    assert "respawn" in resolver.SESSION_KEYS and "respawn" not in sessionconfig.SETTABLE


S19_LAYERS = [
    ({"user": "defaults:\n  respawn: {cap: 3}\n"}, {"cap": 3, "floor": 600, "settle": 60}),
    ({"user": "defaults:\n  respawn: {cap: 3}\n", "repo": "session:\n  respawn: {floor: 30}\n"},
     {"cap": 3, "floor": 30, "settle": 60}),
    ({"repo": "session:\n  respawn: {settle: 5, cap: 1}\n",
      "local": "session:\n  respawn: {settle: 0}\n"}, {"cap": 1, "floor": 600, "settle": 0}),
]


@pytest.mark.parametrize("layers,want", S19_LAYERS,
                         ids=["user-defaults", "config.yaml", "config.local.yaml"])
def test_s19_respawn_layers(world, layers, want):
    for layer, text in layers.items():
        world[2](layer, text)
    r = run(world)
    assert r.sections["session"]["respawn"] == want and r.unknown == []


@pytest.mark.parametrize("value,key", [
    ("{cap: -1}", "respawn.cap"), ('{floor: "x"}', "respawn.floor"),
    ("{settle: 1.5}", "respawn.settle"), ("{cap: true}", "respawn.cap"),
    ("{cap: 1, colour: 2}", "respawn.colour"),
], ids=["negative", "string", "float", "bool", "stray-key"])
def test_s19_respawn_refuses_bad_values(world, value, key):
    world[2]("repo", "session:\n  respawn: {cap: 0}\n")
    assert run(world).sections["session"]["respawn"]["cap"] == 0      # the positive control
    world[2]("repo", "session:\n  respawn: %s\n" % value)
    with pytest.raises(ResolveError, match=key.replace(".", r"\.")):
        run(world)


# ---- S21: the priority and pacing keys ---------------------------------------

S21_DEFAULT_S3 = "the build order: the goal's next slice, then the repo's pending list"


def test_s21_one_text_replaces_one_level(world):
    from claude_session import rules
    world[2]("repo", 'session:\n  priority:\n    levels: {S4: "the rest: polish, only when idle"}\n')
    r = run(world)
    lv = r.sections["session"]["priority"]["levels"]
    assert lv["S4"] == "the rest: polish, only when idle" and lv["S3"] == S21_DEFAULT_S3
    assert list(lv) == list(rules.LEVELS) and r.unknown == []
    assert r.sections["session"]["priority"]["enabled"] is True


def test_s21_local_wins(world):
    world[2]("user", "defaults:\n  pacing: {fallback: 2000}\n")
    world[2]("repo", "session:\n  pacing: {fallback: 2400, waiting: 2}\n")
    world[2]("local", "session:\n  pacing: {fallback: 3000}\n")
    assert run(world).sections["session"]["pacing"] == {"enabled": True, "fallback": 3000,
                                                        "waiting": 2}


def test_s21_not_settable(world):
    from claude_session import cli, sessionconfig
    for key in ("priority", "pacing"):
        assert key in resolver.SESSION_KEYS and key not in sessionconfig.SETTABLE
        with pytest.raises(SystemExit) as e:
            cli.main(["set", key, "off"])
        assert e.value.code != 0


def test_s26_admission_is_a_session_key_merged_by_field(world):
    from claude_session import rules, sessionconfig
    assert "admission" in resolver.SESSION_KEYS and "admission" not in sessionconfig.SETTABLE
    assert run(world).sections["session"]["admission"] is None          # the reader's defaults
    world[2]("repo", "session:\n  admission:\n    ceiling: 90\n    seeds: {life: 20}\n")
    world[2]("local", "session:\n  admission: {margin: 5}\n")
    s = run(world).sections["session"]
    assert s["admission"] == {"ceiling": 90, "seeds": {"life": 20}, "margin": 5}
    got = rules.admission(s)
    assert (got["ceiling"], got["margin"], got["seeds"]["life"], got["mode"]) == (90, 5, 20, "observe")


@pytest.mark.parametrize("key,kept", [("priority", "levels"), ("pacing", "fallback")])
def test_s21_off(world, key, kept):
    world[2]("repo", "session:\n  %s: {enabled: false}\n" % key)
    s = run(world).sections["session"]
    assert s[key]["enabled"] is False and s[key][kept]
    other = "pacing" if key == "priority" else "priority"
    assert s[other]["enabled"] is True


@pytest.mark.parametrize("layer,text,want", [
    ("repo", "session:\n  priority: {colour: blue}\n", ["config.yaml: session.priority.colour"]),
    ("local", 'session:\n  priority:\n    levels: {S5: "x"}\n  pacing: {colour: 1}\n',
     ["config.local.yaml: session.priority.levels.S5", "config.local.yaml: session.pacing.colour"]),
], ids=["priority", "levels-and-pacing"])
def test_s21_unknown_keys_keep_their_layer(world, layer, text, want):
    world[2](layer, text)
    r = run(world)
    s = r.sections["session"]
    assert r.unknown == want
    assert "colour" not in s["priority"] and "colour" not in s["pacing"]
    assert sorted(s["priority"]["levels"]) == ["S1", "S2", "S3", "S4"]


@pytest.mark.parametrize("text,key", [
    ("  priority:\n", "session.priority"),                       # N3: null deletes nothing
    ("  pacing: 5\n", "session.pacing"),
    ("  priority:\n    levels:\n", "priority.levels"),
    ('  priority: {enabled: "yes"}\n', "priority.enabled"),
    ('  priority:\n    levels: {S2: ""}\n', "priority.levels.S2"),
    ('  priority:\n    levels: {S3: "a\\nb"}\n', "priority.levels.S3"),
    ('  priority:\n    levels: {S1: "%s"}\n' % ("x" * 241), "priority.levels.S1"),
    ("  pacing: {fallback: 59}\n", "pacing.fallback"),
    ("  pacing: {fallback: 3601}\n", "pacing.fallback"),       # N1: the block's bound
    ("  pacing: {waiting: 0}\n", "pacing.waiting"),
    ("  pacing: {waiting: 10}\n", "pacing.waiting"),
    ("  pacing: {waiting: true}\n", "pacing.waiting"),
], ids=["priority-null", "pacing-scalar", "levels-null", "enabled-string", "text-empty",
        "text-two-lines", "text-241", "fallback-59", "fallback-3601", "waiting-0",
        "waiting-10", "waiting-bool"])
def test_s21_bad_value(world, text, key):
    world[2]("repo", "session:\n  pacing: {fallback: 60, waiting: 9}\n")
    assert run(world).sections["session"]["pacing"]["waiting"] == 9     # the positive control
    world[2]("repo", "session:\n" + text)
    with pytest.raises(ResolveError, match=key.replace(".", r"\.")):
        run(world)


# F8: `make install` deleted the frozen tree under six live launchers; at each respawn the
# shipped profiles read as an empty layer and the chain stopped on `unknown profile
# 'orchestrator'; known: ` (empty). The shipped file is read once, at import, and a missing
# one names itself.

def test_f8_shipped_gone_after_import_still_resolves(tmp_path):
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    tree = tmp_path / "share" / "a-tree"
    shutil.copytree(Path(resolver.__file__).parent, tree / "claude_session",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    home, repo, state = tmp_path / "home", tmp_path / "repo", tmp_path / "state"
    for d in (home, repo, state):
        d.mkdir()
    code = ("import json, shutil, sys\n"
            "from claude_session import resolver\n"
            "shutil.rmtree(sys.argv[1])\n"           # the whole tree goes, as the install did
            "env = json.loads(sys.argv[3])\n"
            "r = resolver.resolve(sys.argv[2], 'sid', env, profile='orchestrator')\n"
            "print(r.sections['session']['profile'], r.inputs[0][1] is not None)\n")
    env = {"HOME": str(home), "XDG_STATE_HOME": str(state)}
    safe = ["-P"] if sys.version_info >= (3, 11) else []   # else the cwd, which holds no package
    r = subprocess.run([sys.executable, *safe, "-c", code, str(tree), str(repo), json.dumps(env)],
                       env=dict(os.environ, PYTHONPATH=str(tree), **env), cwd=str(repo),
                       capture_output=True, text=True, timeout=60)
    assert not tree.exists()
    assert (r.returncode, r.stdout.strip()) == (0, "orchestrator True"), r.stderr


def test_f8_missing_shipped_file_names_itself(world, monkeypatch, tmp_path):
    env, _, put = world
    gone = tmp_path / "gone" / "profiles.yaml"
    monkeypatch.setattr(resolver, "SHIPPED", gone)
    want = f"the shipped profiles.yaml is gone: {gone}; run install-cli"
    with pytest.raises(ResolveError) as e:
        run(world, profile="orchestrator")
    assert str(e.value) == want
    with pytest.raises(ResolveError) as e:
        resolver.load_profiles(env)
    assert str(e.value) == want
    # a missing user or repo layer stays an empty layer: the positive control
    monkeypatch.undo()
    r = run(world, profile="orchestrator")
    assert r.sections["session"]["profile"] == "orchestrator"
    assert [h for _, h in r.inputs][1:4] == [None, None, None]


def test_gate_joins_the_sections_from_the_repo_layers(world):
    _, _, put = world
    assert "gate" in resolver.SECTIONS
    put("repo", "gate:\n  wall: 60\n")
    r = run(world)
    assert r.sections["gate"] == {"wall": 60} and r.unknown == []


def test_gate_config_reads_the_user_layer_alone(world):
    env, _, put = world
    assert resolver.gate_config(env) == {"ntfy_url": None, "ntfy_topic": None, "wall": 5400}
    put("repo", "gate:\n  ntfy_url: https://repo.invalid\n  ntfy_topic: r\n")
    assert resolver.gate_config(env)["ntfy_url"] is None
    put("user", "gate:\n  ntfy_url: https://ntfy.invalid\n  ntfy_topic: gates\n  wall: 600\n")
    assert resolver.gate_config(env) == {"ntfy_url": "https://ntfy.invalid",
                                         "ntfy_topic": "gates", "wall": 600}
