"""Packet hw3-machine: the machine's meter as one module (M1 to M5); the verb and the skill
are test_hw3_machine_verb's.

Every reader is fed recorded text through a fake probe: no test reads the live state, runs
a `du` on the live home or reads this machine's own counters. The fixtures' paths and
names are made up."""
import ast
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from claude_session import machine

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "plugin" / "lib" / "claude_session" / "machine.py"

# ---- recorded text ---------------------------------------------------------------------------

MAC_SYSCTL = ("hw.memsize: 137438953472\n"
              "kern.memorystatus_vm_pressure_level: 1\n"
              "hw.perflevel0.physicalcpu: 12\n"
              "hw.perflevel1.physicalcpu: 4\n")
MAC_VM_STAT = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
               "Pages free:                                  4000000.\n"
               "Pages active:                                1500000.\n"
               "Pages inactive:                              1000000.\n"
               "Pages speculative:                             96000.\n"
               "Pages throttled:                                   0.\n"
               "Pages wired down:                             335188.\n"
               "Pages purgeable:                              226080.\n"
               '"Translation faults":                   232929048835.\n')
DF_HEAD = "Filesystem   1024-blocks       Used Available Capacity  Mounted on\n"
DF_DATA = DF_HEAD + "/dev/disk9s5  1948455240 1511228792 139233292    92%    /Volumes/Example Data\n"
DF_CACHE = DF_HEAD + "/dev/disk9s7  1948455240  262144000 139233292    66%    /Volumes/ExampleCache\n"
MAC_PS = ("  28736 /sbin/launchd\n"
          " 204800 /usr/local/bin/go\n"
          "   2048 /usr/bin/make\n"
          "   1024 gmake\n"
          " 409600 /opt/example/Python.app/Contents/MacOS/Python\n"
          " 102400 python3.12\n"
          "1048576 /opt/example/bin/claude\n"
          "  51200 /opt/example/bin/example.test\n"
          "garbage line\n")
LINUX_MEMINFO = ("MemTotal:       65536000 kB\n"
                 "MemFree:         1000000 kB\n"
                 "MemAvailable:   32768000 kB\n"
                 "Buffers:          123456 kB\n")
LINUX_PSI = ("some avg10=0.50 avg60=0.20 avg300=0.10 total=123456\n"
             "full avg10=0.00 avg60=0.00 avg300=0.00 total=1234\n")
LINUX_DF = DF_HEAD + "/dev/sda1      976762584  488381292 488381292      50% /\n"
LINUX_PS = "  10240 java\n  20480 python3\n  4096 bash\n"


class Fake(machine.Probe):
    """Answers each command from recorded text; any command it does not know, and any
    file it was not given, does not answer. It records every call."""

    def __init__(self, answers=None, files=None, cores=16, load=(3.5, 2.0, 1.0), env=None,
                 now=1_800_000_000.0, du=None, real=(), plat="darwin"):
        self.plat = plat
        self.answers = dict(answers or {})
        self.files = dict(files or {})
        self.cores, self.load, self.envs, self.t = cores, load, dict(env or {}), now
        self.du = du                    # a folder every du must be inside, and its kB
        self.real = tuple(real)         # commands run for real (git, on a temp repo)
        self.calls = []

    def run(self, argv, timeout=machine.RUN_BOUND, cwd=None, env=None):
        self.calls.append((list(argv), timeout, cwd, env))
        if argv[0] == "du":
            top, kb = self.du
            assert os.path.realpath(argv[-1]).startswith(os.path.realpath(str(top))), argv
            return 0, f"{kb.get(os.path.basename(argv[-1]), 4)}\t{argv[-1]}\n"
        if argv[0] in self.real:
            return super().run(argv, timeout, cwd, env)
        for key, value in self.answers.items():
            if tuple(argv[:len(key)]) == key:
                return value(argv) if callable(value) else value
        return None

    def read(self, path):
        return self.files.get(path)

    def cpu_count(self):
        return self.cores

    def loadavg(self):
        if self.load is None:
            raise OSError("no load")
        return self.load

    def env(self, name):
        return self.envs.get(name)

    def now(self):
        return self.t

    def platform(self):
        return self.plat


def mac_probe(gocache="/x/cache/go-build", **kw):
    answers = {("sysctl",): (0, MAC_SYSCTL), ("vm_stat",): (0, MAC_VM_STAT),
               ("ps",): (0, MAC_PS),
               ("df",): lambda argv: (0, DF_CACHE if "cache" in argv[-1] else DF_DATA)}
    answers.update(kw.pop("answers", {}))
    return Fake(answers=answers, env={"GOCACHE": gocache}, **kw)


def linux_probe(**kw):
    return Fake(answers={("df",): (0, LINUX_DF), ("ps",): (0, LINUX_PS)},
                files={"/proc/meminfo": LINUX_MEMINFO, "/proc/pressure/memory": LINUX_PSI},
                cores=8, plat="linux", **kw)


# ---- M1: the standard library alone; bounded; never raises ------------------------------------

STDLIB = {"__future__", "math", "os", "random", "re", "subprocess", "sys", "time",
          "concurrent", "concurrent.futures", "json", "shutil", "stat"}


def test_machine_imports_the_standard_library_alone():
    tree = ast.parse(MODULE.read_text())
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            seen |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import reaches the plugin"
            seen.add(node.module)
    assert seen and seen <= STDLIB, seen - STDLIB
    assert not any("claude_session" in s for s in seen)


def test_the_bounds_are_the_ruled_ones():
    assert machine.RUN_BOUND == 5 and machine.DU_BOUND == 20


def test_a_subprocess_past_its_bound_is_none():
    p = machine.Probe()
    assert p.run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3) is None
    assert p.run(["/nonexistent/example-command"]) is None
    assert p.run([sys.executable, "-c", "print('ok')"]) == (0, "ok\n")


def test_every_subprocess_names_a_bound():
    pr = mac_probe(du=("/x", {}))
    machine.snapshot({"home": "/x/home"}, probe=pr, platform="darwin")
    assert pr.calls and all(t == machine.RUN_BOUND for _, t, _, _ in pr.calls)


@pytest.mark.parametrize("plat", ["darwin", "linux", "sunos5"])
def test_a_probe_that_answers_nothing_gives_nulls_and_faults(plat):
    pr = Fake(cores=None, load=None)
    s = machine.snapshot({"home": "/x/home", "state": "/x/state"}, probe=pr, platform=plat)
    assert s["schema"] == machine.SCHEMA
    assert s["cores"]["total"] is None and s["load"] is None
    assert s["memory"] == {"total_mb": None, "free_mb": None, "pressure": "unknown"}
    assert s["disks"] == [] and s["processes"] is None
    assert any(f.startswith("cores") for f in s["faults"])
    assert any(f.startswith("load") for f in s["faults"])
    assert any(f.startswith("memory") for f in s["faults"])
    assert any(f.startswith("disk home") for f in s["faults"])
    assert any(f.startswith("processes") for f in s["faults"])
    json.dumps(s)


def test_consumers_with_nothing_there_is_empty(tmp_path):
    assert machine.consumers({"gate": str(tmp_path / "none"), "repos": [str(tmp_path / "no")]},
                             probe=Fake()) == []


# ---- M2: the snapshot, each platform from recorded text ---------------------------------------

def test_the_mac_snapshot(tmp_path):
    cache = tmp_path / "cache" / "go-build"
    cache.mkdir(parents=True)
    s = machine.snapshot({"home": str(tmp_path), "state": str(tmp_path / "state")},
                         probe=mac_probe(gocache=str(cache)))
    assert s["cores"] == {"total": 16, "performance": 12, "efficiency": 4}
    assert s["load"] == [3.5, 2.0, 1.0]
    assert s["memory"]["total_mb"] == 131072
    assert s["memory"]["free_mb"] == (4000000 + 1000000 + 96000) * 16384 // 1024 ** 2
    assert s["memory"]["pressure"] == "normal"
    assert s["disks"] == [
        {"mount": "/Volumes/Example Data", "total_gb": 1858.2, "free_gb": 132.8,
         "holds": ["home", "state"]},
        {"mount": "/Volumes/ExampleCache", "total_gb": 1858.2, "free_gb": 132.8,
         "holds": ["gocache"]}]
    p = s["processes"]
    assert p["go"] == {"count": 1, "rss_mb": 200}
    assert p["make"] == {"count": 2, "rss_mb": 3}
    assert p["python"] == {"count": 2, "rss_mb": 500}
    assert p["claude"] == {"count": 1, "rss_mb": 1024}
    assert p["java"] == {"count": 0, "rss_mb": 0}
    assert s["paths"]["gocache"] == str(cache)
    assert s["faults"] == []


@pytest.mark.parametrize("level,word", [("1", "normal"), ("2", "warn"), ("4", "critical"),
                                        ("9", "unknown")])
def test_the_mac_pressure_levels(level, word):
    text = MAC_SYSCTL.replace("level: 1", "level: " + level)
    s = machine.snapshot({"home": "/x"}, probe=mac_probe(answers={("sysctl",): (1, text)}),
                         platform="darwin")
    assert s["memory"]["pressure"] == word


def test_a_mac_with_no_perflevels_names_the_fault():
    text = "hw.memsize: 8589934592\nkern.memorystatus_vm_pressure_level: 1\n"
    s = machine.snapshot({"home": "/x"}, probe=mac_probe(answers={("sysctl",): (1, text)}),
                         platform="darwin")
    assert s["cores"] == {"total": 16, "performance": None, "efficiency": None}
    assert s["memory"]["total_mb"] == 8192
    assert any("perflevel0" in f for f in s["faults"])


def test_the_linux_snapshot_on_any_machine():
    s = machine.snapshot({"home": "/home/example"}, probe=linux_probe())
    assert s["cores"] == {"total": 8, "performance": None, "efficiency": None}
    assert s["memory"] == {"total_mb": 64000, "free_mb": 32000, "pressure": "normal"}
    assert s["disks"] == [{"mount": "/", "total_gb": 931.5, "free_gb": 465.8, "holds": ["home"]}]
    assert s["processes"]["java"] == {"count": 1, "rss_mb": 10}
    assert s["processes"]["python"] == {"count": 1, "rss_mb": 20}
    assert "gocache" not in s["paths"]
    assert s["faults"] == []


@pytest.mark.parametrize("psi,avail,word", [
    ({"some": 0.5, "full": 0.0}, 50, "normal"),
    ({"some": 12.0, "full": 0.0}, 50, "warn"),
    ({"some": 30.0, "full": 11.0}, 50, "critical"),
    ({}, 8, "warn"),
    ({}, 4, "critical"),
    ({}, None, "unknown"),
])
def test_the_linux_pressure(psi, avail, word):
    info = {"MemTotal": 100} if avail is None else {"MemTotal": 100, "MemAvailable": avail}
    assert machine.linux_pressure(psi, info) == word


def test_the_parsers_read_recorded_text():
    assert machine.parse_psi(LINUX_PSI) == {"some": 0.5, "full": 0.0}
    assert machine.parse_meminfo(LINUX_MEMINFO)["MemAvailable"] == 32768000
    assert machine.parse_df(DF_DATA)[0]["mount"] == "/Volumes/Example Data"
    assert machine.parse_du("123\t/x\n") == 123 and machine.parse_du("") is None
    assert machine.parse_sysctl("sysctl: unknown oid 'hw.x'\nhw.ncpu: 8\n") == {"hw.ncpu": "8"}
    assert machine.parse_vm_stat(MAC_VM_STAT)["page"] == 16384


def test_go_env_runs_from_the_root_with_a_local_toolchain():
    pr = Fake(answers={("go", "env", "GOCACHE"): (0, "/x/cache/go-build\n")})
    assert machine.gocache(pr) == "/x/cache/go-build"
    (argv, _, cwd, env), = pr.calls
    assert cwd == "/" and env["GOTOOLCHAIN"] == "local"
    assert machine.gocache(Fake(env={"GOCACHE": "off"})) is None
    assert machine.gocache(Fake()) is None


# ---- M3: the budget, pure -----------------------------------------------------------------

def _snap(load=3.5, pressure="normal", free_gb=132.8, cores=16, total_mb=131072):
    return {"schema": machine.SCHEMA, "cores": {"total": cores},
            "load": None if load is None else [load, 1.0, 1.0],
            "memory": {"total_mb": total_mb, "free_mb": 9000, "pressure": pressure},
            "disks": [{"mount": "/a", "free_gb": free_gb}, {"mount": "/b", "free_gb": 400.0}]}


def test_the_budget_is_what_the_grants_leave():
    b = machine.budget(_snap(), [machine.DEFAULT_CLASS, machine.DEFAULT_CLASS], {})
    assert b["cores"] == 16 and b["mem_mb"] == 131072 - 16384
    assert b["granted"] == {"count": 2, "cpu": 8, "mem_mb": 4096}
    assert b["free"] == {"cpu": 8, "mem_mb": 131072 - 16384 - 4096}
    assert b["load_ceiling"] == 12.0 and b["disk_floor_gb"] == 25.0
    assert b["disk_free_gb"] == 132.8
    assert "fit" not in b


def test_a_request_that_fits():
    fit = machine.budget(_snap(), [], {}, {"cpu": 4, "mem_mb": 2048})["fit"]
    assert fit["ok"] is True and fit["why"].startswith("fits: 4 of 16 cores")


@pytest.mark.parametrize("snap,cfg,grants,word", [
    (_snap(load=12.0), {}, [], "load 12.00 at or over the ceiling 12.00"),
    (_snap(load=5.0), {"load_ceiling": 4}, [], "the ceiling 4.00"),
    (_snap(load=None), {}, [], "the load is unknown"),
    (_snap(pressure="warn"), {}, [], "memory pressure warn"),
    (_snap(pressure="unknown"), {}, [], "memory pressure unknown"),
    (_snap(free_gb=25.0), {}, [], "25 GB free, at or under the floor of 25"),
    (_snap(free_gb=40.0), {"disk_floor_gb": 50}, [], "the floor of 50"),
    (_snap(), {}, [{"cpu": 14, "mem_mb": 0}], "2 and"),
    (_snap(), {}, [{"cpu": 0, "mem_mb": 114000}], "MB not granted"),
])
def test_each_guard_holds_a_request(snap, cfg, grants, word):
    fit = machine.budget(snap, grants, cfg, {"cpu": 4, "mem_mb": 2048})["fit"]
    assert fit["ok"] is False and word in fit["why"], fit["why"]


def test_a_request_over_the_whole_budget_is_clamped_and_runs_alone():
    big = {"cpu": 64, "mem_mb": 10 ** 7}
    alone = machine.budget(_snap(), [], {}, big)["fit"]
    assert alone["ok"] is True and "16 of 16 cores" in alone["why"]
    held = machine.budget(_snap(), [{"cpu": 1, "mem_mb": 1}], {}, big)["fit"]
    assert held["ok"] is False and "clamped to 16 cores and 114688 MB" in held["why"]


def test_the_budget_is_pure_and_takes_an_unknown_snapshot():
    snap, grants = _snap(), [dict(machine.DEFAULT_CLASS)]
    before = copy.deepcopy((snap, grants))
    machine.budget(snap, grants, {}, {"cpu": 1, "mem_mb": 1})
    assert (snap, grants) == before
    fit = machine.budget({"cores": {"total": None}, "memory": {}}, [], None,
                         {"cpu": 1, "mem_mb": 1})["fit"]
    assert fit == {"ok": False, "why": "the budget is unknown: cores did not answer"}


# ---- M4: the disk's consumers ---------------------------------------------------------------

def _git(*argv, cwd):
    subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True)


def _repo(tmp_path):
    repo = tmp_path / "example-repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    (repo / "a.txt").write_text("a\n")
    _git("add", "a.txt", cwd=repo)
    _git("commit", "-q", "-m", "one", cwd=repo)
    wts = repo / ".claude" / "worktrees"
    for name in ("landed", "ahead", "dirty"):
        _git("worktree", "add", "-q", "-b", name, str(wts / name), "main", cwd=repo)
    (wts / "ahead" / "b.txt").write_text("b\n")
    _git("add", "b.txt", cwd=wts / "ahead")
    _git("commit", "-q", "-m", "two", cwd=wts / "ahead")
    (wts / "dirty" / "c.txt").write_text("c\n")
    _git("worktree", "add", "-q", "-b", "outside", str(tmp_path / "elsewhere"), "main", cwd=repo)
    return repo, wts


def test_the_consumers_by_kind(tmp_path):
    now = time.time()
    gate = tmp_path / "state" / "example-tool" / "gate"
    old, new = gate / "20260101-000000-1", gate / "20260101-000000-2"
    for d in (old, new):
        d.mkdir(parents=True)
        (d / "log").write_bytes(b"x" * 4096)
    for p in (old / "log", old):
        os.utime(p, (now - 15 * 86400, now - 15 * 86400))
    (gate / "queue").mkdir()
    (tmp_path / "state" / "other-tool").mkdir()
    transcripts, scratch = tmp_path / "claude" / "projects", tmp_path / "scratch"
    transcripts.mkdir(parents=True)
    scratch.mkdir()
    cache = tmp_path / "cache" / "go-build"
    cache.mkdir(parents=True)
    repo, wts = _repo(tmp_path)
    pr = mac_probe(du=(tmp_path, {"projects": 2 * 1024 ** 2, "dirty": 1024 ** 2}), real=("git",),
                   now=now)
    faults = []
    rows = machine.consumers({"gate": str(gate), "gocache": str(cache), "home": str(tmp_path),
                              "repos": [str(repo)], "transcripts": str(transcripts),
                              "state_home": str(tmp_path / "state"), "scratch": str(scratch)},
                             probe=pr, faults=faults)
    by = {os.path.basename(r["path"]): r for r in rows}
    assert rows[0]["path"] == str(cache) and rows[0]["gb"] == 250.0
    assert by["go-build"] == {"path": str(cache), "gb": 250.0, "kind": "idle",
                              "what": "the Go build cache, its volume /Volumes/ExampleCache's use"}
    assert by["gate"]["kind"] == "auto" and by["gate"]["what"] == "1 gate results past 14 days"
    assert by["landed"]["kind"] == "idle" and "merged into main, clean" in by["landed"]["what"]
    assert by["ahead"]["kind"] == "person" and "not merged" in by["ahead"]["what"]
    assert by["dirty"]["kind"] == "person" and "dirty" in by["dirty"]["what"]
    assert by["dirty"]["gb"] == 1.0 and by["projects"]["gb"] == 2.0
    assert "elsewhere" not in by and "example-repo" not in by
    for name in ("projects", "scratch", "example-tool", "other-tool"):
        assert by[name]["kind"] == "person", name
    assert {r["kind"] for r in rows} <= set(machine.KINDS)
    assert all(set(r) == {"path", "gb", "kind", "what"} for r in rows)
    assert old.exists() and (wts / "landed").exists()           # it removes nothing
    assert faults == []
    sums = machine.reclaimable(rows)
    assert sums["idle"]["count"] == 2 and sums["auto"]["count"] == 1


def test_a_go_cache_on_the_homes_volume_is_not_walked(tmp_path):
    cache = tmp_path / "go-build"
    cache.mkdir()
    pr = Fake(answers={("df",): (0, DF_DATA)}, du=(tmp_path, {}))
    (row,) = machine.consumers({"gocache": str(cache), "home": str(tmp_path)}, probe=pr)
    assert row["gb"] is None and "not walked" in row["what"]
    assert not any(argv[0] == "du" for argv, *_ in pr.calls)


def test_a_du_that_does_not_answer_is_null_and_a_fault(tmp_path):
    (tmp_path / "scratch").mkdir()

    class Slow(Fake):
        def run(self, argv, timeout=machine.RUN_BOUND, cwd=None, env=None):
            self.calls.append((list(argv), timeout, cwd, env))
            return None
    pr, faults = Slow(), []
    (row,) = machine.consumers({"scratch": str(tmp_path / "scratch")}, probe=pr, faults=faults)
    assert row["gb"] is None and faults and "du did not answer" in faults[0]
    assert pr.calls[0][1] == machine.DU_BOUND


def test_the_porcelain_reader_skips_a_bare_and_a_prunable_tree():
    text = ("worktree /x/repo\nbare\n\n"
            "worktree /x/repo/.claude/worktrees/a\nHEAD abc\nbranch refs/heads/a\n\n"
            "worktree /x/repo/.claude/worktrees/b\nHEAD def\ndetached\nprunable gone\n")
    assert machine.parse_worktrees(text) == [
        {"path": "/x/repo/.claude/worktrees/a", "head": "abc", "branch": "a"}]


# ---- M5: backoff ----------------------------------------------------------------------------

@pytest.mark.parametrize("attempt,want", [(0, 0.5), (1, 1.0), (3, 4.0), (6, 30.0), (10, 30.0),
                                          (10 ** 6, 30.0), (-2, 0.5)])
def test_backoff_is_full_jitter_under_a_cap(attempt, want):
    assert machine.backoff(attempt, rng=lambda: 0.5) == want


@pytest.mark.parametrize("ra,want", [(30, 30.0), ("12", 12.0), (0, 0.0), (3600, 3600.0),
                                     (3601, 2.0), (-1, 2.0), (True, 2.0), ("soon", 2.0),
                                     (float("nan"), 2.0)])
def test_backoff_honours_a_retry_after_first(ra, want):
    assert machine.backoff(2, retry_after=ra, rng=lambda: 0.5) == want


def test_backoff_takes_base_cap_and_three_attempts():
    assert machine.ATTEMPTS == 3
    assert machine.backoff(2, base=0.1, cap=1.0, rng=lambda: 1.0) == pytest.approx(0.4)
    assert machine.backoff(5, base=0.1, cap=1.0, rng=lambda: 1.0) == 1.0
